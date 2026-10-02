# Code review: aiohttp @ e11d2836203a21bec59095498e578d37801027e7 (scope: `aiohttp/`)

Reviewer: opus, run 10. I only report defects I either reproduced with a small script against the checkout (marked **Reproduced**) or that follow directly from the code and a cited standard. The scripts ran with `/tmp/aiohttp-venv/bin/python` and `sys.path` pointed at `/tmp/control/aiohttp`.

---

## 1. Client sends a chunk-encoded body under a `Content-Length` header when `chunked=False` is passed

- **File/line:** `aiohttp/client_reqrep.py:1450-1451` (`_create_writer`), together with `1280-1284` (`_update_body_from_data`).
- **What goes wrong:** `_update_body_from_data` treats `chunked=False` as "not chunked" and adds `Content-Length`. `_create_writer` then checks `if self.chunked is not None: writer.enable_chunking()`, so `False` turns chunking on anyway.
- **Reproduced:** `session.post(url, data=b"hello", chunked=False)` puts this on the wire:
  `...Content-Length: 5\r\n...\r\n\r\n5\r\nhello\r\n0\r\n\r\n`
  The header declares 5 bytes, but 15 bytes of chunk framing follow. A server reads `5\r\nh` as the body and then parses `ello\r\n0\r\n\r\n` as the next request on a keep-alive connection. This is message desynchronisation, the same class of problem as request smuggling.
- **Why it is wrong:** RFC 9112 §6.2/§6.3 requires the framing to match the declared length. `chunked` is typed `bool | None` in `client.py:479`, and `False` is a legitimate value meaning "don't chunk". Every other place in `ClientRequest` tests truthiness (`if self.chunked:`); only this one tests `is not None`.
- **Severity:** high.
- **Fix:** `if self.chunked: writer.enable_chunking()`.

## 2. A caller-supplied `Transfer-Encoding: chunked` header produces both TE and CL, with an unchunked body

- **File/line:** `aiohttp/client_reqrep.py:1280-1284` and `1231-1248` (`_update_transfer_encoding`), `1450`.
- **What goes wrong:** `self.chunked` stays `None` when the user sets the header `Transfer-Encoding: chunked` without passing `chunked=True`. So:
  - `_update_body_from_data` adds `Content-Length`.
  - `_update_transfer_encoding` accepts the TE header without complaint (it only raises when `self.chunked` is truthy).
  - The writer never enables chunking.
- **Reproduced:** `session.post(url, data=b"hello", headers={"Transfer-Encoding": "chunked"})` sends:
  `Transfer-Encoding: chunked ... Content-Length: 5 ... \r\n\r\nhello`
  The request carries both headers, which RFC 9112 §6.1 says a sender MUST NOT do, and the body is not chunk-framed even though TE says it is. aiohttp's own server parser (`http_parser.py:637-640`) rejects this exact combination.
- **Severity:** medium.
- **Fix:** In `_update_transfer_encoding`, when `"chunked" in te`, set `self.chunked = True` and drop or refuse any `Content-Length`. Alternatively, have `_update_body_from_data` skip adding `Content-Length` when a TE header is present and enable chunking on the writer.

## 3. `MultipartReader.next()` breaks on a form-data `_charset_` field: it never consumes the boundary

- **File/line:** `aiohttp/multipart.py:808-816`.
- **What goes wrong:**
  - After reading the `_charset_` part's value, the code calls `self.fetch_next_part()` directly. That skips `_read_boundary()`, so the `--boundary` line that follows is parsed as a header line.
  - With a normal boundary such as `abc`, parsing fails with `InvalidHeader: b'--abc'`.
  - With a boundary that happens to contain `:`, parsing silently yields a bogus header. For boundary `:` the header is `'--': ''`; for `a:b` it is `'--a': 'b'`. The existing test (`tests/test_multipart.py::test_read_form_default_encoding`, boundary `":"`) passes only by this accident.
  - Separately, `part.read_chunk(32)` trips the assertion at `multipart.py:450-452` (`size >= self._boundary_len`) for any boundary of 29 characters or more. Browsers typically use 38-character boundaries such as `----WebKitFormBoundary...`.
- **Reproduced:** with a two-field body where the first field is `name="_charset_"`:
  - boundary `abc`: `InvalidHeader`
  - boundary `----WebKitFormBoundary7MA4YWxkTrZu0gW`: `AssertionError: Chunk size must be greater or equal than boundary length + 2`
  - boundary `:`: succeeds, but the next part's headers contain `{'--': ''}`
- **Why it is wrong:** RFC 7578 §4.6 defines `_charset_` as an ordinary form part whose value is the default charset, and the code comment cites that section. The following part must still be delimited by a boundary.
- **Severity:** medium. Any standards-following client that sends `_charset_` makes `request.post()` and `request.multipart()` fail with a 400 or 500.
- **Fix:**
  - Read the charset with a size of at least `part._boundary_len`, or use `await part.read()` capped at 32 bytes.
  - Then `await part.release()`, merge `part._unread`, and `await self._read_boundary()`.
  - If `_at_eof` is now set, return `None`; otherwise call `fetch_next_part()`.

## 4. Replacing a persistent cookie with a session cookie keeps the old expiry, so the new cookie is deleted

- **File/line:** `aiohttp/cookiejar.py:396-416` (`_update_cookies`), together with `_expirations` / `_expire_cookie`.
- **What goes wrong:** An expiry is only ever added or updated. When a cookie with the same `(domain, path, name)` is set again without `Max-Age` or `Expires`, the stale entry in `self._expirations` is not removed. When the old deadline passes, `_do_expiration()` deletes the new session cookie.
- **Reproduced:** `a=1; Max-Age=1`, then `a=2`. `filter_cookies` returns `{'a': 2}` immediately and `{}` after 1.2 s.
- **Why it is wrong:** RFC 6265 §5.3 step 11 says the new cookie replaces the old one, and step 3 says a cookie without Max-Age/Expires is a non-persistent cookie that expires only at the end of the session. The old expiry must not carry over.
- **Severity:** medium. Session or login cookies silently disappear.
- **Fix:** When neither `max-age` nor a parseable `expires` is present, run `self._expirations.pop((domain, path, name), None)`. Stale heap entries are already ignored by the `self._expirations.get(cookie_key) == when` check.
- **Related, low severity (same block):** an unparseable `Max-Age` (e.g. `Max-Age=abc`) blanks the attribute, but because of the `elif` the `Expires` attribute is then ignored as well. Reproduced: `b=1; Max-Age=abc; Expires=Thu, 01 Jan 1970 00:00:00 GMT` is stored as a live cookie. RFC 6265 §5.2.2 says to ignore only the invalid Max-Age; Expires should then apply. Fix: fall through to the `expires` handling when Max-Age parsing fails.

## 5. `BodyPartReader.decode()` silently truncates decompressed data to 256 KiB

- **File/line:** `aiohttp/multipart.py:609-619` (`_decode_content`), called from `decode()` at `579-591`.
- **What goes wrong:** `ZLibDecompressor(...).decompress_sync(data, max_length=self._max_decompress_size)` returns at most `max_decompress_size` bytes (`DEFAULT_CHUNK_SIZE` = 256 KiB). The rest is left in the decompressor, which is then discarded. No error is raised.
- **Reproduced:** a 1,000,000-byte payload deflated and passed to `part.decode(comp)` returns 262,144 bytes. The same input through `decode_iter()` returns all 1,000,000 bytes.
- **Why it is wrong:** The docstring says it "Decodes data according the specified Content-Encoding". Silent data loss is worse than either returning the full data or raising. The async sibling `_decode_content_async` loops on `data_available` for exactly this reason.
- **Severity:** medium, since `decode()` is public API.
- **Fix:** Loop while `d.data_available` (as the async path does) and enforce an explicit size limit that raises. At minimum, raise if `d.data_available` is still true after the call.

## 6. `Range: bytes=-0` returns 206 with the whole file instead of 416

- **File/line:** `aiohttp/web_request.py:682-685` (`http_range`) and `aiohttp/web_fileresponse.py:358-395`.
- **What goes wrong:** For `bytes=-0`, `end=0` and `start = -end = 0`. The suffix range becomes `slice(0, None)`, which is indistinguishable from `bytes=0-`. `FileResponse` then serves the full file with status 206 and `Content-Range: bytes 0-(n-1)/n`.
- **Reproduced:** `make_mocked_request(..., Range="bytes=-0").http_range` gives `slice(0, None, 1)`, the same as `bytes=0-`.
- **Why it is wrong:** RFC 9110 §14.1.1: a byte-range-set is satisfiable only if it contains a first-byte-pos below the length, or a suffix-range with a **non-zero** suffix-length. The comment at `web_fileresponse.py:380-387` quotes this very rule. So `bytes=-0` must get 416 with `Content-Range: bytes */n`.
- **Severity:** low.
- **Fix:** In `http_range`, raise `ValueError` (which leads to 416) when the suffix length is 0.

## 7. Response compression and pre-compressed static file selection ignore `q=0` in `Accept-Encoding`

- **File/line:** `aiohttp/web_response.py:348-352` (`_start_compression`) and `aiohttp/web_fileresponse.py:241-243` (`_get_file_path_stat_encoding`).
- **What goes wrong:** Both use a substring test (`value in accept_encoding` / `file_encoding not in accept_encoding`). A client sending `Accept-Encoding: gzip;q=0, identity` still gets a gzip-encoded response or the `.gz` sibling file.
- **Why it is wrong:** RFC 9110 §12.4.2/§12.5.3: a qvalue of 0 means "not acceptable". Sending a coding the client explicitly refused yields a body it cannot or will not decode.
- **Severity:** low to medium.
- **Fix:** Parse `Accept-Encoding` into (coding, q) pairs and only choose codings with q > 0, ideally ordered by q.

## 8. `MultipartWriter.decode()` produces malformed multipart text

- **File/line:** `aiohttp/multipart.py:1147-1160`.
- **What goes wrong:** It omits the CRLF after each part body and the closing `--boundary--` delimiter. `write()` and `as_bytes()` emit both.
- **Reproduced:** with two parts, `decode()` gives `'...\r\n\r\none--b\r\n...two'`, while `as_bytes().decode()` gives `'...one\r\n--b\r\n...two\r\n--b--\r\n'`.
- **Why it is wrong:** The docstring says it returns the "string representation of the multipart data" and points to `as_bytes().decode()` as the async-safe equivalent. The two disagree, and `decode()` output is not valid multipart (RFC 2046 §5.1.1). It is reachable through `Response.text` when a `MultipartWriter` is the body.
- **Severity:** low.
- **Fix:** Append `"\r\n"` after each `part.decode()` and `"--" + self.boundary + "--\r\n"` at the end. Also pass `encoding, errors` to `part.decode()`.

## 9. `MaskDomain` host matching is case-sensitive

- **File/line:** `aiohttp/web_urldispatcher.py:826-827`.
- **What goes wrong:** `Domain.match_domain` lowercases the Host header (line 808), but the `MaskDomain` override does `self._mask.fullmatch(host)` on the raw header. The mask is built from the lowercased domain, so `app.add_domain("*.example.com", sub)` does not route a request with `Host: API.Example.com`.
- **Why it is wrong:** Host names are case-insensitive (RFC 3986 §3.2.2, RFC 9110 §4.2.3). The parent class already normalises case; the subclass loses that.
- **Severity:** low.
- **Fix:** `return self._mask.fullmatch(host.lower()) is not None`.

---

## Considered and not reported

These looked suspicious but are either intentional or I could not confirm them:
- `HttpParser.feed_eof` compares `bytes` to `"\r\n"`. The comparison is always unequal, but the only effect is appending `b""`, which is harmless.
- The WebSocket reader uses `>=` in the uncompressed max_msg_size check (`reader_py.py:552`) but `>` in the decompressed check (`:326`). This is an exact-boundary inconsistency, and the intended inclusivity is undocumented.
- The `StreamReader.readuntil` limitation with multi-byte separators split across buffer chunks. It only affects callers using multi-byte separators; the in-tree callers use `\n`.

## Files actually read

- `aiohttp/_cookie_helpers.py` (full)
- `aiohttp/helpers.py` (full)
- `aiohttp/http_parser.py` (full)
- `aiohttp/web_fileresponse.py` (lines 120-438)
- `aiohttp/web_request.py` (lines 150-1015)
- `aiohttp/web_response.py` (lines 60-792)
- `aiohttp/web_exceptions.py` (HTTPRequestEntityTooLarge)
- `aiohttp/multipart.py` (full)
- `aiohttp/compression_utils.py` (full)
- `aiohttp/streams.py` (full)
- `aiohttp/web_urldispatcher.py` (lines 90-1256)
- `aiohttp/web_protocol.py` (lines 170-959)
- `aiohttp/cookiejar.py` (lines 60-653)
- `aiohttp/client_reqrep.py` (lines 430-1561)
- `aiohttp/client.py` (lines 520-960, plus grep for `chunked` / `proxy_headers`)
- `aiohttp/connector.py` (lines 560-860)
- `aiohttp/http_writer.py` (lines 60-397)
- `aiohttp/_websocket/reader_py.py` (lines 90-634)
- `aiohttp/payload.py` (lines 340-460, 840-925, plus the def index)
- `aiohttp/formdata.py` (full)
- `aiohttp/web_middlewares.py` (lines 40-140)
- For context only: `tests/test_multipart.py` (lines 1150-1230) and a grep of `tests/test_websocket_parser.py` / `docs/*.rst` for `max_msg_size`.
