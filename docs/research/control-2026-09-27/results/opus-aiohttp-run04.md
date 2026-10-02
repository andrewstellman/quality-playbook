# Code review: aiohttp @ e11d2836203a21bec59095498e578d37801027e7 (scope: `aiohttp/`)

Reviewer: opus, run 04. I confirmed every finding below by running a small snippet against a copy of the checkout, using the project's venv at `/tmp/aiohttp-venv`. Line numbers refer to the pinned checkout.

---

## 1. Every 404 response leaks its Request object (unbounded memory growth). Severity: HIGH

- **File/line:** `aiohttp/web_urldispatcher.py:975` (`HTTP_NOT_FOUND = HTTPNotFound()`), `:1023` (`return MatchInfoError(self.HTTP_NOT_FOUND)`). The exception is raised in `SystemRoute._handle`, `:908-909` (`raise self._http_exception`).
- **What goes wrong:** the router keeps a single class-level `HTTPNotFound` instance and hands it to every unmatched request, and the system route raises that same instance each time. Raising an exception object that already has a `__traceback__` prepends the new frames to the existing traceback chain, so the traceback grows by about 3 entries per 404. The retained frames hold their locals, so every `Request` (and whatever it references) that ever produced a 404 stays alive for the life of the process.
- **Reproduction:** start an app with no routes and send GET `/nope` 3 times. The traceback length on `UrlDispatcher.HTTP_NOT_FOUND` goes 3, 6, 9. After 200 such requests and `gc.collect()`, `sum(type(o) is web.Request for o in gc.get_objects()) == 200`.
- **Why it is wrong:** any unauthenticated client can grow server memory without bound by requesting non-existent paths. A per-request object must not be shared through class state that outlives the request.
- **Fix:** create a fresh exception per request, e.g. `return MatchInfoError(HTTPNotFound())`, and drop the class attribute. Alternatively, clear `__traceback__` before each raise, but a fresh instance is simpler and also avoids shared mutable header state.

## 2. `Response` with no body plus `enable_compression()` crashes on `prepare()`. Severity: MEDIUM

- **File/line:** `aiohttp/web_response.py:720-735` (`Response._do_start_compression`: `assert self._body is not None`). It is reached from `StreamResponse._prepare_headers`, `:388-389`, which calls `_start_compression` without checking for an empty body.
- **What goes wrong:** `web.Response(status=204)` (or any `Response` whose body is `None`) with `enable_compression()` and a request carrying `Accept-Encoding: gzip` raises `AssertionError` from `prepare()`. I confirmed this for status 200 and 204. Under `python -O` it would instead call `compressor.compress(None)` and raise `TypeError`. A common pattern is a middleware that calls `enable_compression()` on every response, and any body-less response then fails with a 500.
- **Why it is wrong:** an empty body needs no compression. The streaming path (`StreamResponse._do_start_compression`) handles it fine. `_must_be_empty_body` responses (204/304/HEAD) should never get `Content-Encoding` at all.
- **Fix:** in `Response._do_start_compression`, return early when `self._body is None`, and skip `_start_compression` entirely when `self._must_be_empty_body`.

## 3. `Forwarded` header: two quoted values in one element merge into one garbage value. Severity: MEDIUM

- **File/line:** `aiohttp/web_request.py:138-139`, `_FORWARDED_PAIR = rf'[ \t]*({_TOKEN})=({_TOKEN}|".*")(:\d{{1,4}})?[ \t]*(?:\Z|;)'`, used in `forwarded` at `:386-411`.
- **What goes wrong:** the quoted-string alternative is the greedy `".*"`, and the pair may end at `\Z`. So `for="_a";by="_b"` matches as a single pair, giving `{'for': '_a";by="_b'}`, and `by` is lost. Any element with two or more quoted parameters (common with IPv6 `for="[::1]:80"` plus a quoted `host`, `by`, or `proto`) is mis-parsed. I confirmed this with `make_mocked_request`.
- **Why it is wrong:** the docstring says it "checks that every value has valid syntax ... either a 'token' or a 'quoted-string'". A quoted-string (RFC 7230 §3.2.6) cannot contain an unescaped `"`. Downstream code that reads `forwarded[0]['for']` (client IP) or `['proto']` gets corrupted values.
- **Fix:** use a proper quoted-string pattern, `"(?:[^"\\]|\\.)*"` (qdtext / quoted-pair), as the old `_QUOTED_STRING` did, and unescape the captured content.

## 4. Nested multipart: a close-delimiter followed directly by the parent delimiter loses the next part's headers. Severity: MEDIUM

- **File/line:** `aiohttp/multipart.py:905-920` (`_read_boundary` puts `[next_line, epilogue]` into `_unread`) together with `:924-936` (`_read_headers` reads straight from `self._content.readline()` and never consumes `self._unread`).
- **What goes wrong:** for the body
  `--outer\r\nContent-Type: multipart/mixed; boundary=inner\r\n\r\n--inner\r\n\r\ndata\r\n--inner--\r\n--outer\r\nContent-Type: text/plain\r\n\r\nhello\r\n--outer--\r\n`
  the inner reader reads `--outer` as its "epilogue" and `Content-Type: text/plain` as `next_line`, then pushes both back through `_unread`. The parent's `_read_boundary` pops `--outer` correctly, but `_read_headers` bypasses `_unread` and reads the blank line from the stream. The next part therefore gets **empty headers**, and the stranded `Content-Type` line is later read as a boundary, giving `ValueError: Invalid boundary b'Content-Type: text/plain'`. With an extra CRLF after `--inner--` the same body parses correctly. I confirmed both cases.
- **Why it is wrong:** under RFC 2046 §5.1.1 the epilogue is optional, and the CRLF before `--outer` belongs to the outer delimiter, so the failing input is the minimal conforming form. The comment at `:916-918` says this case is "handled gracefully".
- **Fix:** make `_read_headers` read through `self._readline()` (honouring `_unread`, with the same max-line-length check), or never push header lines into `_unread` from `_read_boundary`.

## 5. `BodyPartReader.decode()` silently truncates decompressed data at 256 KiB. Severity: MEDIUM

- **File/line:** `aiohttp/multipart.py:609-619` (`_decode_content`): `ZLibDecompressor(...).decompress_sync(data, max_length=self._max_decompress_size)`.
- **What goes wrong:** `max_length` caps the output, but the sync path never loops on `data_available` or `unconsumed_tail`, so the remaining output is discarded. A gzip part that decompresses to 1,000,000 bytes returns 262,144 bytes from `decode()`, while `decode_iter()` returns all 1,000,000. I confirmed this.
- **Why it is wrong:** the docstring says `decode` "Decodes data according the specified Content-Encoding". Returning a silently truncated result corrupts data without any error.
- **Fix:** loop like `_decode_content_async` does (`while d.data_available: out += d.decompress_sync(b"", max_length)`), or raise if data remains.

## 6. `StreamWriter.write_eof(data)` ignores the declared `Content-Length` and writes past it. Severity: MEDIUM

- **File/line:** `aiohttp/http_writer.py:276-352`. The non-compressed paths call `_send_headers_with_payload(chunk, True)` or `_write(chunk)` without applying `self.length`. By contrast, `write()` truncates at `:195-203`.
- **What goes wrong:** with `writer.length = 5`, `write(b"0123456789")` emits `b"01234"` but `write_eof(b"0123456789")` emits all 10 bytes (confirmed). On the server, `StreamResponse` sets `writer.length = self.content_length` at `web_response.py:401`, so `resp.content_length = 5; await resp.prepare(req); await resp.write_eof(b"0123456789")` sends 5 bytes beyond the framed body on a keep-alive connection. The client then parses them as the start of the next response (response desynchronisation).
- **Why it is wrong:** `write()` already enforces the length contract. `write_eof()` is the same stream and must frame the message the same way.
- **Fix:** apply the same `self.length` truncation to `chunk` at the top of `write_eof` (non-compressed path) before any write.

## 7. `CookieJar`: re-setting a cookie without Max-Age/Expires keeps the old cookie's expiry. Severity: MEDIUM

- **File/line:** `aiohttp/cookiejar.py:396-422` (`_update_cookies`). An expiry is only ever added via `_expire_cookie`. When the new Set-Cookie has neither `max-age` nor `expires` (or has an invalid one, `:409-416`), the stale entry in `self._expirations[(domain, path, name)]` and the heap entry are left in place.
- **What goes wrong:** `Set-Cookie: a=1; Max-Age=2` followed by `Set-Cookie: a=2` leaves `_expirations` still holding the 2-second deadline, and 5 seconds later `filter_cookies` returns `{}` (confirmed). A session cookie that replaced a persistent one is deleted on the old schedule.
- **Why it is wrong:** RFC 6265 §5.3 step 3/11: a cookie without Max-Age/Expires is a non-persistent cookie, and replacing an old cookie takes the new cookie's attributes. Only the creation-time is kept from the old cookie.
- **Fix:** when neither a valid `max-age` nor a valid `expires` is present, `self._expirations.pop((domain, path, name), None)`. The stale heap entry is already ignored because `_do_expiration` compares against `_expirations`.

## 8. `max_redirects=N` follows only N-1 redirects (`max_redirects=1` follows none). Severity: MEDIUM

- **File/line:** `aiohttp/client.py:769-777`: `redirects += 1 ... if max_redirects and redirects >= max_redirects: raise TooManyRedirects`.
- **What goes wrong:** the counter is incremented and checked when the redirect *response* arrives, before following it. With `max_redirects=1`, a single `/a -> 302 -> /b (200)` raises `TooManyRedirects` (confirmed). With the default of 10, only 9 redirects are followed.
- **Why it is wrong:** `docs/client_reference.rst:481/975` says "`max_redirects`: Maximum number of redirects to follow", and `:476` says "redirects are followed (up to `max_redirects` times)".
- **Fix:** raise only when `redirects > max_redirects`, i.e. follow exactly `max_redirects` hops. Adjust `test_HTTP_302_max_redirects` accordingly.

## 9. `HeadersDictProxy.getall()` splits Link URIs that contain commas, so `ClientResponse.links` drops them. Severity: MEDIUM

- **File/line:** `aiohttp/helpers.py:72-112` (`_LIST_ELEMENT` splits on every comma outside quoted strings and comments), `:788-802` (`getall`), used by `client_reqrep.py:492` (`for val in self.headers.getall("link")`).
- **What goes wrong:** `Link: <http://e.com/a,b>; rel="next", <http://e.com/c>; rel="prev"` becomes `('<http://e.com/a', 'b>; rel="next"', '<http://e.com/c>; rel="prev"')` (confirmed). Neither fragment matches `\s*<(.*)>(.*)`, so the `next` link disappears silently from `resp.links`.
- **Why it is wrong:** RFC 8288 §3: `link-value = "<" URI-Reference ">" *( OWS ";" OWS link-param )`. A URI-Reference may legally contain `,` (a sub-delim), and the `<...>` brackets delimit it.
- **Fix:** treat `<...>` as an atomic unit in list splitting for Link, e.g. give `links` its own splitter that does not break inside angle brackets (or add a `<[^>]*>` branch to the unquoted-element alternatives).

## 10. `HeadersDictProxy.__eq__` reports two identical multi-valued header sets as unequal. Severity: LOW

- **File/line:** `aiohttp/helpers.py:804-805`: `return self._md.__eq__(other)`.
- **What goes wrong:** for two proxies built from `CIMultiDict([('A','1'),('A','2')])`, `p == q` is `False`, and `p == {'A': '1, 2'}` is also `False`, even though `dict(p) == {'A': '1, 2'}`. With single values it happens to work. `CIMultiDict.__eq__` compares against the other object's Mapping view (joined values) and so never matches its own multi-valued items.
- **Why it is wrong:** the class is a `Mapping[str, str]`, so equality should follow the Mapping semantics its own `__getitem__` and `items()` expose, and it is not even reflexive across equal instances.
- **Fix:** `if isinstance(other, HeadersDictProxy): return self._md == other._md`, otherwise fall back to `Mapping.__eq__` (compare `dict(self.items())`).

## 11. `StreamReader.readuntil()` misses a multi-byte separator split across buffered chunks. Severity: LOW

- **File/line:** `aiohttp/streams.py:396-410`: the separator is searched only within `self._buffer[0]`.
- **What goes wrong:** after `feed_data(b"abc\r")` and `feed_data(b"\ndef\r\nghi")`, `readuntil(b"\r\n")` returns `b'abc\r\ndef\r\n'` (confirmed). The first separator is missed because it spans two buffer entries, so two records are merged. Near `max_size` this can also raise a spurious `LineTooLong`.
- **Why it is wrong:** `docs/streams.rst:82` documents `readuntil(separator=b"\n", ...)` as reading until the separator. Multi-byte separators are explicitly allowed (`seplen` is computed and only `0` is rejected).
- **Fix:** keep `len(separator) - 1` bytes of overlap from the accumulated `chunk` when searching the next buffer, or search in `chunk[-(seplen-1):] + buffer`.

## 12. `EmptyStreamReader` (`EMPTY_PAYLOAD`) raises `AttributeError` for `readuntil()` and `total_raw_bytes`. Severity: LOW

- **File/line:** `aiohttp/streams.py:598-679`. `__init__` does not call `super().__init__`, so the `_exception` and `total_compressed_bytes` slots are unset. `readuntil` (see the `# TODO add async def readuntil` at `:662`) and `total_raw_bytes` (`:260-264`) are inherited.
- **What goes wrong:** `await EMPTY_PAYLOAD.readuntil(b"x")` raises `AttributeError: ... '_exception'`, and `EMPTY_PAYLOAD.total_raw_bytes` raises `AttributeError: ... 'total_compressed_bytes'` (confirmed). `resp.content` / `request.content` is `EMPTY_PAYLOAD` for body-less messages (HEAD, 204, 304, GET without body).
- **Why it is wrong:** both are documented public `StreamReader` APIs (`docs/streams.rst:82`, `:117`). The empty reader is otherwise a drop-in for a reader at EOF.
- **Fix:** override `readuntil` to return `b""`, and set `self.total_compressed_bytes = None` in `EmptyStreamReader.__init__` (or override `total_raw_bytes` to return 0).

## 13. `MultipartWriter.decode()` produces malformed multipart (no CRLF between parts, no close delimiter). Severity: LOW

- **File/line:** `aiohttp/multipart.py:1147-1160`.
- **What goes wrong:** for two string parts it returns `'--B\r\n...\r\n\r\none--B\r\n...\r\n\r\ntwo'`. The CRLF before each delimiter and the final `--B--\r\n` are missing (confirmed). `as_bytes()` (`:1162-1187`) and `write()` (`:1189-1216`) produce the correct `one\r\n--B...two\r\n--B--\r\n`.
- **Why it is wrong:** the docstring says it returns the "string representation of the multipart data", and the sibling serialisers define that representation. RFC 2046 §5.1.1 requires `CRLF` before each delimiter plus a close-delimiter.
- **Fix:** mirror `as_bytes()`: append `"\r\n"` after each part body and `"--" + boundary + "--\r\n"` at the end.

## 14. `MaskDomain.match_domain` is case-sensitive, unlike `Domain`. Severity: LOW

- **File/line:** `aiohttp/web_urldispatcher.py:826-827` (`self._mask.fullmatch(host)`), compared with `Domain.match_domain` at `:807-808` (`host.lower() == self._domain`).
- **What goes wrong:** `MaskDomain('*.example.com').match_domain('api.Example.com')` returns `False`, while `Domain('api.example.com').match_domain('API.example.com')` returns `True` (confirmed). With `app.add_domain('*.example.com', sub)`, a request whose `Host` header has any uppercase letters does not reach the sub-app.
- **Why it is wrong:** host names are case-insensitive (RFC 3986 §3.2.2), `validation()` lowercases the configured pattern, and the base class lowercases the host.
- **Fix:** `return self._mask.fullmatch(host.lower()) is not None`.

## 15. `Range: bytes=-0` is served as 206 with the whole file instead of 416. Severity: LOW

- **File/line:** `aiohttp/web_request.py:679-697` (`http_range`: `start = -end` turns suffix length `0` into `start = 0`, `end = None`), then `aiohttp/web_fileresponse.py:358-395` (a non-negative `start` takes the "from start to end" branch, `count = file_size`, status 206).
- **What goes wrong:** a zero-length suffix range becomes `slice(0, None)`, so the response is `206 bytes 0-(n-1)/n` with the full body.
- **Why it is wrong:** RFC 9110 §14.1.1 / §14.1.2: a byte-range-set is satisfiable only if it has a first-byte-pos below the length **or a suffix-range with a non-zero suffix-length**. `bytes=-0` is unsatisfiable, so the server should send 416 with `Content-Range: bytes */n`. The code's own comment at `web_fileresponse.py:380-387` quotes this rule.
- **Fix:** in `http_range`, raise `ValueError` when `start is None and end == 0`. `FileResponse` then already answers 416.

## 16. Accept-Encoding `q=0` is ignored when choosing a content coding. Severity: LOW

- **File/line:** `aiohttp/web_fileresponse.py:241-243` (`if file_encoding not in accept_encoding: continue`) and `aiohttp/web_response.py:348-352` (`if value in accept_encoding:`).
- **What goes wrong:** both use a substring test on the raw header. `Accept-Encoding: identity, gzip;q=0` still selects gzip: `FileResponse` serves the `.gz` sibling, and `enable_compression()` gzips the body.
- **Why it is wrong:** RFC 9110 §12.5.3: a coding with `q=0` is "not acceptable". The client explicitly refused it.
- **Fix:** parse the header into (coding, q) pairs and pick only codings with `q > 0`.

---

## Files actually read

- `aiohttp/_cookie_helpers.py`
- `aiohttp/client_middleware_digest_auth.py`
- `aiohttp/http_parser.py`
- `aiohttp/helpers.py`
- `aiohttp/web_request.py`
- `aiohttp/web_fileresponse.py`
- `aiohttp/web_response.py`
- `aiohttp/multipart.py`
- `aiohttp/compression_utils.py` (lines 150-529)
- `aiohttp/streams.py`
- `aiohttp/web_urldispatcher.py` (lines 360-1030)
- `aiohttp/web_protocol.py` (lines 380-560)
- `aiohttp/cookiejar.py` (lines 150-653)
- `aiohttp/client.py` (lines 520-890)
- `aiohttp/client_proto.py` (lines 240-330)
- `aiohttp/client_reqrep.py` (lines 470-560, 699-775, 1192-1260)
- `aiohttp/_websocket/reader_py.py`, `aiohttp/_websocket/models.py` (top)
- `aiohttp/http_writer.py`
- `aiohttp/payload.py` (lines 454-725)
- `aiohttp/web_middlewares.py` (lines 30-132)
- Context only: `docs/client_reference.rst` / `docs/streams.rst` (grep for `max_redirects`, `readuntil`, `total_raw_bytes`), `tests/test_client_functional.py:1636-1660`
