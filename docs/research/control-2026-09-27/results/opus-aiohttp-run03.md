# Code review: aiohttp (`aiohttp/` package, commit e11d2836)

Reviewer: opus, run 03. I checked every finding below by running a small script against a copy of the checkout, using `AIOHTTP_NO_EXTENSIONS=1` so the pure-Python code paths were exercised.

I found 3 defects I am confident in.

---

## 1. `BaseRequest.forwarded`: a quoted value swallows the rest of the element

- **File/line:** `aiohttp/web_request.py:138-140` (the `_FORWARDED_PAIR` pattern), used at `web_request.py:392-399`
- **What goes wrong:** The value alternative is `({_TOKEN}|".*")`. It is greedy and not limited to qdtext. When a forwarded-element holds more than one quoted value, the first `"` matches up to the last `"` in the element, followed by `\Z`. The first pair then takes the rest of the element as its value, and the later pairs are lost.

  Reproduced:
  ```
  Forwarded: for="a";by="b", for=c;proto=https
  -> ({'for': 'a";by="b'}, {'for': 'c', 'proto': 'https'})
  ```
  The expected first element is `{'for': 'a', 'by': 'b'}`. The same happens with the common RFC 7239 form `for="[2001:db8::1]";proto=https`, where `proto` is dropped and gets folded into `for`.
- **Why it is wrong:** The docstring says the property "checks that every value has valid syntax in general as specified in section 4: either a 'token' or a 'quoted-string'". A quoted-string ends at the first unescaped `"`. The module even defines `_QDTEXT` (lines 131-133) for this purpose, but nothing uses it.
- **Severity:** medium. Applications that read `request.forwarded` to get the client address or protocol from a proxy get corrupted values: `for` can contain `";proto=...`, and `proto`/`by`/`host` go missing.
- **Suggested fix:** Match a real quoted-string instead of `".*"`, for example `"(?:[^"\\]|\\.)*"` (or build it from `_QDTEXT` plus quoted-pair). Keep the `(?:\Z|;)` terminator. If the goal of `.*` was to accept values that `HeadersDictProxy.getall()` already unescaped, do the parsing on the raw header, or stop pre-unescaping for this header, so that `"` inside a value stays unambiguous.

---

## 2. `ClientRequest`: `chunked=False` still sends a chunk-encoded body with `Content-Length`

- **File/line:** `aiohttp/client_reqrep.py:1450-1451` (`_create_writer`)
  ```python
  if self.chunked is not None:
      writer.enable_chunking()
  ```
- **What goes wrong:** `self.chunked` is `None`, `True` or `False`. When the caller passes `chunked=False` explicitly:
  - `_update_body_from_data` leaves it `False` and sets `Content-Length` from the payload size.
  - `_update_transfer_encoding` adds no `Transfer-Encoding` header.
  - But `False is not None`, so the writer still frames the body as chunked.

  Reproduced with `session.post(url, data=b"abc", chunked=False)`. The bytes on the wire were:
  ```
  ...Content-Length: 3\r\nContent-Type: application/octet-stream\r\n\r\n3\r\nabc\r\n0\r\n\r\n
  ```
  The body is `3\r\nabc\r\n0\r\n\r\n` (13 bytes), while `Content-Length: 3` promises 3 bytes. The server reads `3\r\n` as the body, and the remaining 10 bytes are left on the connection as the start of the next request.
- **Why it is wrong:** Everywhere else, chunking is decided by the truthiness of `self.chunked`: line 1229, line 1242 (`elif self.chunked:` before adding the `Transfer-Encoding: chunked` header), and line 1280. The writer must frame the body the same way the headers describe it. RFC 9112 §6 requires the message framing to match `Content-Length` / `Transfer-Encoding`.
- **Severity:** high. The request body is corrupted, and leftover bytes on a persistent connection can be parsed as a new request (request-smuggling class).
- **Suggested fix:** `if self.chunked: writer.enable_chunking()`.

---

## 3. `MultipartWriter.decode()` produces malformed multipart

- **File/line:** `aiohttp/multipart.py:1147-1160`
- **What goes wrong:** Each part is emitted as `"--" + boundary + "\r\n" + headers + part.decode()`. Two things are missing:
  - the CRLF after each part body, which is required before the next delimiter
  - the closing delimiter `--boundary--\r\n`

  Reproduced with two string parts. `decode()` returned:
  ```
  '--B\r\n...\r\n\r\nhello--B\r\n...\r\n\r\nworld'
  ```
  `as_bytes()` on the same writer returned the correct:
  ```
  '...hello\r\n--B\r\n...world\r\n--B--\r\n'
  ```
- **Why it is wrong:** The docstring says it returns the "string representation of the multipart data". `as_bytes()` (lines 1162-1187) and `write()` (lines 1189-1216) both emit `\r\n` after each part and the closing boundary. RFC 2046 §5.1.1 requires the delimiter to be preceded by CRLF and the body to end with the close-delimiter. As written, `hello--B` would not be recognised as a boundary by a parser, including aiohttp's own `MultipartReader`.
- **Severity:** low. The wire path uses `write()`, but anything that calls `decode()` (for example `Response.text` on a response whose body is a `MultipartWriter`, or user code) gets an unparseable document.
- **Suggested fix:** Append `"\r\n"` after `part.decode()` for each part, and append `"--" + self.boundary + "--\r\n"` after the loop, matching `as_bytes()`.

---

## Things I looked at and did not report

Each of these either behaves as intended or I could not confirm a defect:

- `HttpRequestParser`/`HttpResponseParser`: chunked parsing, trailers, and the `max_msg_queue_size` backpressure path.
- Websocket frame reader: size limits, control-frame rules, close-code validation.
- `CookieJar`: domain/path matching and expiry.
- `FileResponse`: range, If-Range and conditional handling.
- `StaticResource`: traversal checks.
- Redirect credential stripping in `ClientSession._request`.
- `DigestAuthMiddleware`.
- `StreamReader`.
- `HeadersDictProxy.getall` (tested with several quoted/comment inputs; correct).

## Files read

- `aiohttp/client_middleware_digest_auth.py`
- `aiohttp/http_parser.py`
- `aiohttp/helpers.py`
- `aiohttp/multipart.py`
- `aiohttp/streams.py`
- `aiohttp/web_fileresponse.py`
- `aiohttp/web_request.py`
- `aiohttp/_cookie_helpers.py`
- `aiohttp/cookiejar.py`
- `aiohttp/web_urldispatcher.py` (resources, static, dispatcher)
- `aiohttp/client.py` (`_request`)
- `aiohttp/client_reqrep.py` (`ClientResponse` and `ClientRequest` parts)
- `aiohttp/web_response.py`
- `aiohttp/http_writer.py`
- `aiohttp/web_middlewares.py`
- `aiohttp/_websocket/reader_py.py`
- `aiohttp/_websocket/helpers.py`
- `aiohttp/_websocket/models.py` (partial)
- `aiohttp/_websocket/writer.py`
- `aiohttp/payload.py` (`Payload`, `BytesPayload`, `StringPayload`, `IOBasePayload`)
- `aiohttp/compression_utils.py` (decompressors/compressor)
- `aiohttp/web_protocol.py` (`RequestHandler` data path and `start`/`finish_response`)
- `aiohttp/connector.py` (`BaseConnector` pool/limit logic)
- `aiohttp/formdata.py`
- `aiohttp/client_ws.py` (heartbeat, close, receive)
