# aiohttp code review — opus-aiohttp-run02

Scope: `aiohttp/` package at e11d2836203a21bec59095498e578d37801027e7 (tests excluded from scope; read only for context).
Method: manual reading plus small reproduction scripts run against the checkout with `/tmp/aiohttp-venv` (scripts lived in the work directory, which has been deleted). Each finding below marked "Reproduced" was confirmed by running code; the rest are confirmed by reading the code.

---

## 1. `_charset_` form field breaks multipart/form-data parsing for normal boundaries

- **File/line:** `aiohttp/multipart.py:805-816` (`MultipartReader.next`)
- **What goes wrong:** When the first part of a `multipart/form-data` body is the `_charset_` field, the reader reads up to 32 bytes of it with `part.read_chunk(32)` and then calls `self.fetch_next_part()` right away. It never consumes the delimiter line (`--boundary`) between the `_charset_` part and the next part, so `_read_headers()` reads `--boundary` as a header line. With an ordinary boundary such as `XYZ`, uuid hex, or `----WebKitFormBoundary...`, that line has no `:`, and `HeadersParser` raises `InvalidHeader`. The request cannot be parsed. The existing test passes only because it uses the boundary `:`: the line `--:` then parses as a bogus header named `--`, so the test hides the bug.
- **Why it is wrong:** RFC 7578 §4.6 defines `_charset_` as a normal form field, and every other path through `next()` calls `_read_boundary()` before `fetch_next_part()`.
- **Reproduced:** body `--XYZ\r\n` + `_charset_` part `ascii` + `--XYZ\r\n` + a `field1` part + `--XYZ--`, with `Content-Type: multipart/form-data; boundary=XYZ`. `await reader.next()` raises `InvalidHeader: Invalid HTTP header: b'--XYZ'`.
- **Severity:** medium (any client that sends the `_charset_` field, such as an HTML form with a hidden `_charset_` input, gets a failed upload or a 400).
- **Fix:** after reading the charset, drain the part (`await part.release()`), then call `await self._read_boundary()`. If that sets `_at_eof`, return `None`. Only then call `fetch_next_part()`.

## 2. `BodyPartReaderPayload.write` decompresses each chunk with a fresh decompressor

- **File/line:** `aiohttp/multipart.py:709-711`, together with `decode_iter` / `_decode_content_async` at `593-633`
- **What goes wrong:** `write()` loops `field.read_chunk()` and calls `field.decode_iter(chunk)` on each chunk. `_decode_content_async` builds a new `ZLibDecompressor` on every call, so only the first chunk is decoded as the start of a stream. The second chunk of a gzip or deflate part hits a decompressor that expects a new header and fails. How big a chunk `read_chunk` returns depends on how much data has arrived, so the failure can hit even a small part when it arrives over the network in more than one piece.
- **Why it is wrong:** a Content-Encoding applies to the whole part body, not to each read.
- **Reproduced:** a gzip part of 100 KB of random data, fed to the `StreamReader` in 10 KB pieces from a background task. `BodyPartReaderPayload(part).write(w)` raises `zlib.error: Error -3 while decompressing data: incorrect header check`. The same data fed all at once succeeds.
- **Severity:** medium.
- **Fix:** keep one decompressor per `BodyPartReader` for the whole part and reuse it across `decode_iter` calls (and flush at EOF). An alternative is to buffer the part and decode it once.

## 3. `BodyPartReader.decode()` silently truncates compressed content to 256 KiB

- **File/line:** `aiohttp/multipart.py:613-617` (`_decode_content`)
- **What goes wrong:** the sync path calls `decompress_sync(data, max_length=self._max_decompress_size)` once and returns the result. It never loops while `data_available`. Output beyond `max_decompress_size` (default `DEFAULT_CHUNK_SIZE` = 256 KiB) is dropped with no error.
- **Why it is wrong:** `decode()` is documented as "Decodes data according the specified Content-Encoding". The async twin `_decode_content_async` (lines 626-633) does loop on `d.data_available`, which shows that `max_length` is meant to bound each step, not the total.
- **Reproduced:** 1,000,000 bytes deflate-compressed; `BodyPartReader(...).decode(compressed)` returns 262144 bytes.
- **Severity:** medium (silent data loss).
- **Fix:** loop `while d.data_available: out += d.decompress_sync(b"", max_length=...)`. Alternatively, raise if output remains, to keep a bomb guard.

## 4. `MultipartWriter.decode()` produces a malformed body

- **File/line:** `aiohttp/multipart.py:1147-1160`
- **What goes wrong:** the joined string leaves out the `\r\n` after each part body and the closing `--boundary--\r\n`. The result is `--B\r\n<hdrs>hello--B\r\n<hdrs>world`.
- **Why it is wrong:** the docstring says to use `as_bytes().decode()` instead and implies both give the same representation. `as_bytes()` (lines 1162-1187) and `write()` both emit the CRLF and the closing delimiter.
- **Reproduced:** comparing `w.decode()` with `(await w.as_bytes()).decode()` for two string parts shows the missing separators and the missing close delimiter.
- **Severity:** low.
- **Fix:** append `"\r\n"` after each `part.decode()`, and append `"--" + self.boundary + "--\r\n"` at the end.

## 5. CookieJar keeps a stale expiry when a cookie is replaced by a session cookie

- **File/line:** `aiohttp/cookiejar.py:396-424` (`_update_cookies`)
- **What goes wrong:** when the new cookie has neither `Max-Age` nor `Expires`, the code never clears the entry that the previous cookie with the same `(domain, path, name)` left in `self._expirations`. `_do_expiration()` then deletes the *new* cookie at the old cookie's deadline.
- **Why it is wrong:** RFC 6265 §5.3 step 11 says the new cookie replaces the old one entirely. With no expiry attribute it is a non-persistent session cookie.
- **Reproduced:** `Set-Cookie: sid=old; Max-Age=1`, then `Set-Cookie: sid=new`. Right away the jar holds `new`. After 1.2 s the jar is empty.
- **Severity:** medium (sessions get logged out unexpectedly).
- **Fix:** in the branch with no max-age/expires (and when parsing fails), call `self._expirations.pop((domain, path, name), None)`. Stale heap entries are already ignored by the `self._expirations.get(key) == when` check.

## 6. Retrying a request loses a user-supplied `Host` header

- **File/line:** `aiohttp/client_reqrep.py:913` (`ClientRequestBase._update_headers`); retry loop at `aiohttp/client.py:698-713`
- **What goes wrong:** `headers.popall(hdrs.HOST, (host,))` removes `Host` from the caller's `CIMultiDict`. In `ClientSession._request` that is the same `headers` object reused on every loop iteration. When a pooled keep-alive connection turns out to be dead and the request is retried (`retry_persistent_connection`), the retry is sent with `Host` built from the URL, not the header the caller gave.
- **Why it is wrong:** a retry must be the same request (RFC 9112 §9.3.1 retries resend the same idempotent request). Changing `Host` can route the request to a different virtual host.
- **Reproduced:** a local server. First GET with `headers={"Host": "example.com"}`. Then close the server-side keep-alive transport and repeat the GET. The server sees `['example.com', '127.0.0.1:<port>']`. With no forced retry, both requests carry `example.com`.
- **Severity:** medium.
- **Fix:** read without mutating, e.g. `self.headers[HOST] = headers.get(HOST, host)`, then extend with every header except `Host`. Alternatively, copy `headers` before popping.

## 7. `ClientResponse.links` drops links whose URI contains a comma

- **File/line:** `aiohttp/client_reqrep.py:492`, using `HeadersDictProxy.getall` in `aiohttp/helpers.py:787-801`
- **What goes wrong:** `getall("link")` splits the combined header on top-level commas. It protects quoted strings and comments but not `<...>` URI-References. `<https://ex.com/p?a=1,2>; rel="next"` is split into `<https://ex.com/p?a=1` and `2>; rel="next"`. Neither matches `\s*<(.*)>(.*)`, so the `next` link disappears without any error.
- **Why it is wrong:** RFC 8288 `link-value = "<" URI-Reference ">" ...`, and a URI-Reference may contain `,` (a sub-delim). Pagination APIs often put comma lists in query strings.
- **Reproduced:** `getall('Link')` on the header above returns `('<https://ex.com/p?a=1', '2>; rel="next"', '<https://ex.com/q>; rel="last"')`.
- **Severity:** low–medium.
- **Fix:** parse Link with a dedicated splitter that treats `<...>` as atomic (or add a `<[^>]*>` branch to `_LIST_ELEMENT` for this use).

## 8. `HeadersDictProxy` iterates duplicate keys for case-variant header names

- **File/line:** `aiohttp/helpers.py:810-821`
- **What goes wrong:** `__iter__` dedupes with a plain case-sensitive `set`, and `__len__` uses `len(set(self._md.keys()))`. The wrapped dict is a `CIMultiDict` that keeps the original case, so a message with `X-A: 1` and `x-a: 2` yields keys `['X-A', 'x-a']`, `len == 2`, and `dict(h) == {'X-A': '1, 2', 'x-a': '1, 2'}`. The combined value shows up twice.
- **Why it is wrong:** the class is a case-insensitive `Mapping` (`__getitem__` joins all case variants). A Mapping must not yield two keys that compare equal under its own lookup.
- **Reproduced:** exactly as described.
- **Severity:** low (affects `request.headers` / `response.headers` iteration, `items()`, `len()`, and anything that copies them, e.g. proxies or logging).
- **Fix:** dedupe on `k.lower()` (or `istr(k)`) in both `__iter__` and `__len__`.

## 9. Accept-Encoding q-values are ignored (`q=0` codings are still used)

- **File/line:** `aiohttp/web_response.py:349-352` (`_start_compression`); `aiohttp/web_fileresponse.py:241-243` (`_get_file_path_stat_encoding`)
- **What goes wrong:** both use a plain substring test (`value in accept_encoding`). `Accept-Encoding: gzip, deflate;q=0` makes `StreamResponse` pick `deflate`, because it is checked first. `Accept-Encoding: br;q=0, gzip` makes `FileResponse` serve the `.br` sibling.
- **Why it is wrong:** RFC 9110 §12.5.3 says a coding with `q=0` is "not acceptable". The comment on line 345 cites RFC 9110 §8.4.1, but only case-folding is applied.
- **Severity:** low–medium (the client receives an encoding it explicitly refused).
- **Fix:** parse Accept-Encoding into `(coding, q)` pairs, discard `q=0`, and choose by q, falling back to identity.

## 10. `Range: bytes=-0` is served as a 206 of the entire file

- **File/line:** `aiohttp/web_request.py:682-685` (`http_range`); consumed in `aiohttp/web_fileresponse.py:367-389`
- **What goes wrong:** for a suffix range with length 0, `start = -end` gives `0`, and the result is `slice(0, None)`. That cannot be told apart from `bytes=0-`, so `FileResponse` returns 206 with the whole file.
- **Why it is wrong:** RFC 9110 §14.1.3 says a byte-range-set is satisfiable only if it has a first-byte-pos below the length or "a suffix-range with a non-zero suffix-length". `bytes=-0` is unsatisfiable and should get 416.
- **Reproduced:** `make_mocked_request('GET','/',headers={'Range':'bytes=-0'}).http_range == slice(0, None, 1)`.
- **Severity:** low.
- **Fix:** in `http_range`, raise `ValueError` (which leads to 416) when start is empty and `end == 0`.

## 11. WebSocket reader rejects a message of exactly `max_msg_size` bytes

- **File/line:** `aiohttp/_websocket/reader_py.py:552` (the same logic is compiled into the Cython reader)
- **What goes wrong:** the check is `payload_bytes_to_read >= max_msg_size - partial_len`, so a message whose total size equals the limit is refused. The error text shows the contradiction: `Message size 10 exceeds limit 10`. The compressed path (lines 269-273) uses `>` and accepts a message of exactly the limit, so the two paths disagree.
- **Why it is wrong:** docs (`web_reference.rst`: "max_msg_size: maximum size of read websocket message") and the error message both describe an inclusive maximum.
- **Reproduced:** `WebSocketReader(q, 10, False, True).feed_data(b"\x82\x0a" + b"0123456789")` sets `WebSocketError: Message size 10 exceeds limit 10`. A 5+5 fragmented message does the same.
- **Severity:** low.
- **Fix:** use `>` (i.e. `payload_bytes_to_read > max_msg_size - partial_len`).

## 12. `max_redirects=N` follows only N-1 redirects

- **File/line:** `aiohttp/client.py:769-777`
- **What goes wrong:** `redirects` is incremented for the redirect response just received, and the code raises as soon as `redirects >= max_redirects`, before that redirect is followed. With `max_redirects=1`, a single 302 raises `TooManyRedirects` and no redirect is followed at all.
- **Why it is wrong:** `docs/client_reference.rst:481` says "max_redirects: Maximum number of redirects to follow", and line 476 says "redirects are followed (up to `max_redirects` times)". The existing test (`test_HTTP_302_max_redirects`) only checks the history length for a 5-hop chain, so it does not pin down the boundary.
- **Severity:** low.
- **Fix:** raise only when `redirects > max_redirects`, or change the docs to match. This is a behaviour change, so the maintainers would need to pick one.

---

## Files actually read

- `aiohttp/http_parser.py` (whole file)
- `aiohttp/streams.py` (whole file)
- `aiohttp/helpers.py` (whole file)
- `aiohttp/multipart.py` (whole file)
- `aiohttp/compression_utils.py` (whole file)
- `aiohttp/cookiejar.py` (whole file)
- `aiohttp/_cookie_helpers.py` (whole file)
- `aiohttp/web_request.py` (lines ~180-1015)
- `aiohttp/web_fileresponse.py` (whole file)
- `aiohttp/web_response.py` (lines ~56-66, 330-500, 560-720)
- `aiohttp/http_writer.py` (lines ~60-397)
- `aiohttp/client.py` (lines ~470-960)
- `aiohttp/client_reqrep.py` (lines ~480-1300)
- `aiohttp/formdata.py` (whole file)
- `aiohttp/_websocket/helpers.py` (whole file), `aiohttp/_websocket/reader_py.py` (whole file)
- `aiohttp/client_middleware_digest_auth.py` (lines 1-140)
- `aiohttp/web_urldispatcher.py` (lines ~540-720)
- For context only: `tests/test_multipart.py` (charset and decode tests), `tests/test_websocket_parser.py` (grep for max_msg_size), `tests/test_client_functional.py` (max_redirects test), `tests/test_web_request.py` (range tests, via grep), `docs/client_reference.rst` / `docs/web_reference.rst` (grep for max_redirects and max_msg_size)
