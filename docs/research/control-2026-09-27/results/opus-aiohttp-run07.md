# Code review: aiohttp (`aiohttp/` package, excluding tests)

Checkout: `/tmp/control/aiohttp` (pinned e11d2836203a21bec59095498e578d37801027e7)
Reviewer: opus, run07

I reproduced every defect below with a small script against a copy of the package (pure-Python mode, `AIOHTTP_NO_EXTENSIONS=1`). The project's own tests for the touched modules (test_http_parser, test_multipart, test_cookiejar, test_streams, test_web_response, test_web_request, test_helpers, test_client_middleware_digest_auth, test_compression_utils, test_web_urldispatcher, test_http_writer, test_client_request, test_client_response, test_websocket_parser/writer, test_payload, test_formdata) pass apart from a few sandbox failures (dev-mode, blockbuster, and cwd problems). None of the defects below are covered by those tests.

---

## 1. `Forwarded` header: the greedy quoted-string regex merges several pairs into one value

- **File/line:** `aiohttp/web_request.py:137-139` (`_FORWARDED_PAIR`), used by `BaseRequest.forwarded` (~line 366).
- **What goes wrong:** The value alternative is `".*"`, which is greedy. When one forwarded-element has two or more quoted values, the first pair swallows everything up to the last `"`. The `(?:\Z|;)` anchor then matches at end of string.
  - Input: `Forwarded: for="_a";proto=https;by="_b"`
  - Result: `({'for': '_a";proto=https;by="_b'},)`. `proto` and `by` are lost, and `for` holds garbage.
  - RFC 7239's own examples use this shape, e.g. `for="[2001:db8:cafe::17]:4711";by=...`.
- **Why wrong:** The docstring says the property checks that each value is "either a 'token' or a 'quoted-string'" (RFC 7239 §4). A quoted-string cannot contain an unescaped `"`. Anyone using `request.forwarded` for proxy, scheme or host information gets wrong data.
- **Severity:** medium
- **Fix:** Use a real quoted-string pattern, for example `"(?:[\t !#-\[\]-~]|\\[\t !-~])*"`. It cannot run past a closing quote.

## 2. `CookieJar`: a cookie that replaces an expiring one inherits the old expiry and is deleted

- **File/line:** `aiohttp/cookiejar.py:~395-417` (`_update_cookies`, the max-age/expires branch).
- **What goes wrong:** When a cookie has `Max-Age`/`Expires`, `_expire_cookie` records `self._expirations[(domain, path, name)]`. If the server later replaces it with a cookie that has no expiry (a session cookie), nothing clears that entry. When the old time passes, `_do_expiration` deletes the new cookie.
  - Reproduced: `Set-Cookie: a=1; Max-Age=1`, then `Set-Cookie: a=2`.
  - `filter_cookies()` returns `a=2` at first. Five seconds later it returns nothing.
- **Why wrong:** RFC 6265 §5.3 step 11: the new cookie replaces the old one, and a cookie with no Max-Age/Expires is a non-persistent session cookie with no expiry.
- **Severity:** medium (session cookies vanish, e.g. logouts or lost sessions)
- **Fix:** In the branch where neither max-age nor expires applies (and where they fail to parse), call `self._expirations.pop((domain, path, name), None)`. Stale heap entries are already skipped because `_do_expiration` compares against `_expirations`.

## 3. `web.Response` with no body plus `enable_compression()` raises `AssertionError`

- **File/line:** `aiohttp/web_response.py:~720-735` (`Response._do_start_compression`, `assert self._body is not None`).
- **What goes wrong:** Take `web.Response(status=204)` or `web.Response()` (body `None`), call `resp.enable_compression()`, and send it to a request with `Accept-Encoding: gzip`. `prepare()` fails with a bare `AssertionError` instead of sending the response. This hits any compression middleware that calls `enable_compression()` on every response.
- **Why wrong:** `write_eof` in the same class handles `body is None` explicitly, and `StreamResponse.enable_compression` accepts any response. A 204/304 (must-be-empty) response, or an empty one, should just go out uncompressed.
- **Severity:** medium
- **Fix:** In `_do_start_compression`, return early (or call `super()`) when `self._body is None` or `self._must_be_empty_body`.

## 4. `BodyPartReaderPayload.write()` decompresses each chunk with a fresh decompressor, so large compressed parts fail

- **File/line:** `aiohttp/multipart.py:708-711` (`BodyPartReaderPayload.write`), together with `BodyPartReader.decode_iter` / `_decode_content_async` (604-633).
- **What goes wrong:** `write()` reads the part in `DEFAULT_CHUNK_SIZE` pieces and calls `field.decode_iter(chunk)` on each one. Every call builds a new `ZLibDecompressor`, so the second piece of a deflate stream is decoded out of context.
  - Reproduced: a `multipart/mixed` part with `Content-Encoding: deflate` and about 400 KB of compressed data.
  - Result: `zlib.error: Error -3 while decompressing data: invalid block type`.
  - Quoted-printable soft line breaks split across chunks are affected the same way. The base64 case was specifically handled with `_align_base64_chunk`, which shows per-chunk decoding is expected to work.
- **Why wrong:** Content-Encoding covers the whole part body, not independent chunks. Forwarding a received part (the purpose of this payload type) corrupts or fails for any compressed part larger than one chunk.
- **Severity:** medium
- **Fix:** Keep one decompressor per `BodyPartReader`, created lazily and reused across `decode_iter` calls, and flush it at part EOF. Alternatively, stream through a single `ZLibDecompressor` inside `write()`.

## 5. `BodyPartReader.decode()` (sync) silently truncates decompressed output at `max_decompress_size`

- **File/line:** `aiohttp/multipart.py:609-619` (`_decode_content`).
- **What goes wrong:** It returns the single result of `decompress_sync(data, max_length=self._max_decompress_size)` and never drains `unconsumed_tail`.
  - Reproduced: 300,000 bytes deflated, then `part.decode(comp)` returns 262,144 bytes (the 256 KiB default). No error is raised.
  - `decode_iter()` on the same input returns all 300,000 bytes, because the async version loops `while d.data_available`.
- **Why wrong:** The docstring says "Decodes data according the specified Content-Encoding", and the async twin returns the full data. Silent data loss.
- **Severity:** medium
- **Fix:** Loop while `d.data_available`, as `_decode_content_async` does, and raise if a total-size cap is exceeded.

## 6. `MultipartWriter.decode()` produces a malformed multipart body

- **File/line:** `aiohttp/multipart.py:1146-1159`.
- **What goes wrong:** It emits `--boundary\r\n + headers + body` for each part, but leaves out the `\r\n` that must end each part before the next delimiter and the closing `--boundary--\r\n`.
  - Reproduced: two text parts give `...hello--xx\r\n...world`, with no CRLF before the second delimiter and no close delimiter.
  - `as_bytes()` (1161-1186) emits both.
- **Why wrong:** RFC 2046 §5.1.1 requires CRLF before each delimiter and a close-delimiter. `decode()` should give the same content as `as_bytes()`.
- **Severity:** low
- **Fix:** Build the string the way `as_bytes` does: add `"\r\n"` after each part and `"--" + boundary + "--\r\n"` at the end.

## 7. `StreamReader.readuntil()` misses a multi-byte separator that straddles two buffered chunks

- **File/line:** `aiohttp/streams.py:381-420`.
- **What goes wrong:** The search is `self._buffer[0].find(separator, offset)`, which runs on one buffer segment at a time. If the separator is split across segments it is never found, and data is returned past it.
  - Reproduced: `feed_data(b"line1\r")`, `feed_data(b"\nline2\r\n")`, then `readuntil(b"\r\n")` returns `b'line1\r\nline2\r\n'`.
- **Why wrong:** `readuntil(separator)` is public, documented API (`docs/streams.rst:82`). It must return data up to and including the first occurrence of the separator.
- **Severity:** low-medium (the internal `readline` uses a 1-byte separator and is not affected)
- **Fix:** When the buffer segment doesn't contain the separator, keep the last `seplen-1` bytes of `chunk` and search `chunk[-(seplen-1):] + next_segment`. A simpler option is to search the accumulated `chunk` from `max(0, len(chunk_before) - seplen + 1)`.

## 8. `Response.links` drops Link entries whose URI contains a comma

- **File/line:** `aiohttp/client_reqrep.py:489-515` (uses `self.headers.getall("link")`), with the splitter at `aiohttp/helpers.py:~186-198` (`HeadersDictProxy.getall` / `_LIST_ELEMENT_RE`).
- **What goes wrong:** `getall` splits the header on every comma outside quoted-strings and comments, including commas inside `<...>`.
  - Input: `<http://x/a?x=1,2>; rel="next"`
  - Split result: `'<http://x/a?x=1'` and `'2>; rel="next"'`. Neither matches `\s*<(.*)>(.*)`, so the link is silently lost.
- **Why wrong:** RFC 8288 §3: the target is a URI-Reference inside `<>`, and URIs may contain commas.
- **Severity:** low
- **Fix:** In `links`, split on `,(?=\s*<)` (or treat `<...>` as protected in the list splitter) instead of the generic `getall`.

## 9. FileResponse ignores `q=0` in Accept-Encoding when picking a pre-compressed file; StreamResponse does the same

- **File/line:** `aiohttp/web_fileresponse.py:241-243` (`if file_encoding not in accept_encoding`) and `aiohttp/web_response.py:~350-353` (`_start_compression`, `if value in accept_encoding`).
- **What goes wrong:** Both use a substring test.
  - Reproduced: `Accept-Encoding: identity, gzip;q=0` with `f.txt.gz` present. The response is served with `Content-Encoding: gzip`.
  - `enable_compression()` likewise compresses with gzip when the request says `gzip;q=0`.
- **Why wrong:** RFC 9110 §12.5.3: a qvalue of 0 means "not acceptable". The client explicitly refused gzip.
- **Severity:** low-medium (clients that refuse an encoding receive it anyway)
- **Fix:** Parse Accept-Encoding into (coding, q) pairs and only choose codings with q > 0.

## 10. `Range: bytes=-0` returns 206 with the whole file instead of 416

- **File/line:** `aiohttp/web_request.py:682-685` (`http_range`: `start = -end` gives `-0 == 0`), consumed at `aiohttp/web_fileresponse.py:~358-376`.
- **What goes wrong:** A zero-length suffix range becomes `slice(0, None)`, which is indistinguishable from `bytes=0-`.
  - Reproduced: `bytes=-0` on a 10-byte file gives `206`, `Content-Range: bytes 0-9/10`, and the full body.
- **Why wrong:** RFC 9110 §14.1.1/§14.1.2: a suffix-range with suffix-length 0 is unsatisfiable. A byte-range-set is satisfiable only with "a suffix-range with a non-zero suffix-length", so the answer should be 416.
- **Severity:** low
- **Fix:** In `http_range`, raise `ValueError` when `start is None and end == 0`. `FileResponse` already turns that into 416.

## 11. WebSocket reader rejects an uncompressed message of exactly `max_msg_size`

- **File/line:** `aiohttp/_websocket/reader_py.py:552` (`if self._payload_bytes_to_read >= self._max_msg_size - partial_len`).
- **What goes wrong:** With `max_msg_size=10`, a 10-byte binary frame is rejected with `WebSocketError: Message size 10 exceeds limit 10`. The message contradicts itself.
- **Why wrong:** The error text and the compressed path in the same file (line 326, `len(payload_merged) > self._max_msg_size`) both treat `max_msg_size` as an inclusive maximum. So the same message is accepted when compressed and rejected when not.
- **Severity:** low
- **Fix:** Use `>` (i.e. `self._payload_bytes_to_read > self._max_msg_size - partial_len`).

## 12. `TOKEN` set in helpers contains TAB

- **File/line:** `aiohttp/helpers.py:172` (`TOKEN = CHAR ^ CTL ^ SEPARATORS`).
- **What goes wrong:** `SEPARATORS` includes `chr(9)`, which `CTL` has already removed from `CHAR ^ CTL`. The second symmetric difference adds TAB back, so `'\t' in TOKEN` is `True`. As a result:
  - `content_disposition_header()` accepts disposition types and parameter names containing TAB.
  - `parse_content_disposition()` accepts TAB inside "token" values.
- **Why wrong:** RFC 9110 §5.6.2 tchar excludes whitespace and CTLs, and the code clearly intends set subtraction.
- **Severity:** low
- **Fix:** `TOKEN = CHAR - CTL - SEPARATORS`.

## 13. `max_redirects=N` fails a chain of exactly N redirects (lower confidence: the behaviour is locked in by an existing test)

- **File/line:** `aiohttp/client.py:769-777` (`redirects += 1` followed by `if max_redirects and redirects >= max_redirects: raise TooManyRedirects`).
- **What goes wrong:** With `max_redirects=1`, the first redirect response raises `TooManyRedirects`, so zero redirects are followed. In general only N-1 redirects are followed.
- **Why wrong:** `docs/client_reference.rst:481-482`: "Maximum number of redirects to follow. TooManyRedirects is raised if the number is exceeded." N redirects do not exceed N. `tests/test_client_functional.py::test_HTTP_302_max_redirects` asserts the current behaviour, so the docs and the code disagree.
- **Severity:** low
- **Fix:** Either use `redirects > max_redirects` (checked before following) or change the documentation.

---

## Files read

- `aiohttp/client_middleware_digest_auth.py` (whole file)
- `aiohttp/http_parser.py` (whole file)
- `aiohttp/_cookie_helpers.py` (whole file)
- `aiohttp/multipart.py` (whole file)
- `aiohttp/compression_utils.py` (whole file)
- `aiohttp/helpers.py` (lines ~60-1199)
- `aiohttp/web_fileresponse.py` (lines 48-60, 150-438)
- `aiohttp/web_request.py` (lines 60-960, parts)
- `aiohttp/web_response.py` (lines 60-792)
- `aiohttp/streams.py` (whole file)
- `aiohttp/cookiejar.py` (lines 250-653)
- `aiohttp/client.py` (lines 476-1010)
- `aiohttp/client_reqrep.py` (lines 85, 160-240, 485-520, 699-775)
- `aiohttp/client_proto.py` (parser construction, ~260-280)
- `aiohttp/web_protocol.py` (lines 200-300, 460-660)
- `aiohttp/web_urldispatcher.py` (StaticResource)
- `aiohttp/web_middlewares.py` (lines 1-140)
- `aiohttp/web_ws.py` (`_handshake`)
- `aiohttp/_websocket/reader_py.py` (lines 60-634)
- `aiohttp/_websocket/helpers.py` (lines 60-148)
- `aiohttp/http_writer.py` (lines 60-397)
- `aiohttp/payload.py` (lines 340-720)
- `aiohttp/connector.py` (`_DNSCacheTable`)
- For context: `docs/client_reference.rst` (max_redirects), `docs/streams.rst` (readuntil), `tests/test_client_functional.py` (test_HTTP_302_max_redirects), `tests/test_http_parser.py` (two failing dev-mode tests), `tests/test_web_sendfile_functional.py` (one env-failing test)
