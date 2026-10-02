# Code review: aiohttp @ e11d2836203a21bec59095498e578d37801027e7

Scope: `aiohttp/` package (tests excluded). Reviewer: Opus.

Each defect below was reproduced against the checkout (pure-Python mode, `AIOHTTP_NO_EXTENSIONS=1`, package on `PYTHONPATH`), except where marked "by inspection".

---

## 1. `Forwarded` quoted values are parsed greedily and swallow later pairs

- **File/line:** `aiohttp/web_request.py:138-141` (`_FORWARDED_PAIR`), used by `BaseRequest.forwarded` at lines 386-410
- **What goes wrong:** The quoted-value alternative is `".*"`, which is greedy and has no qdtext restriction. When a forwarded-element has more than one quoted value, the first value runs on to the last `"` in the element.
  - Input: `Forwarded: for="a";by="b"`
  - Actual: `request.forwarded == ({'for': 'a";by="b'},)`
  - Expected: `({'for': 'a', 'by': 'b'},)`
- **Why it is wrong:** The `forwarded` docstring says the parser "checks that every value has valid syntax in general as specified in section 4: either a 'token' or a 'quoted-string'" (RFC 7239). `.*` is not a quoted-string. The module defines `_QDTEXT` (lines 131-133) for this purpose, but nothing uses it. The `by` pair is lost, and the `for` value contains attacker-shaped text with quotes and `;`. Apps that use `forwarded` for client IP or host/proto decisions get wrong values.
- **Severity:** medium
- **Fix:** Match a real quoted-string, for example `"(?:[^"\\]|\\.)*"`. Because `HeadersDictProxy.getall` has already un-escaped the quoted pairs, `"[^"]*"` is enough. Better still, build it from `_QDTEXT` and the quoted-pair rule.

## 2. Multipart `_charset_` handling leaves the next delimiter unconsumed, so the following part fails to parse

- **File/line:** `aiohttp/multipart.py:805-815` (`MultipartReader.next`)
- **What goes wrong:** When the first form-data part is named `_charset_`, the code reads up to 32 bytes from it and then calls `self.fetch_next_part()` directly. It never releases the part and never reads the boundary line. `BodyPartReader` pushes the `--boundary` line back into the stream, so `_read_headers()` receives `--B` as its first header line.
  - Body: `--B\r\n<CD name="_charset_">\r\n\r\nlatin-1\r\n--B\r\n<CD name="f">\r\n\r\nx\r\n--B--\r\n`
  - Result: `InvalidHeader: 400, Invalid HTTP header: b'--B'`
  - This fails with both a real `StreamReader` and the test-suite `Stream`.
  - The existing test `test_read_form_default_encoding` passes only because its boundary is `:`. The line `--:` happens to parse as a header named `--` with an empty value.
  - Browsers send a hidden `_charset_` field, so real HTML form posts handled by `request.post()` get a 400.
- **Why it is wrong:** RFC 7578 §4.6, which the code cites, defines `_charset_` as an ordinary part. Every other path in `next()` consumes the delimiter via `_maybe_release_last_part()` and `_read_boundary()` before `fetch_next_part()`.
- **Severity:** medium
- **Fix:** After reading the charset, do this before fetching the next part:
  1. `await part.release()`
  2. `self._unread.extend(part._unread)`
  3. `await self._read_boundary()`
  4. `if self._at_eof: return None`

  Also consider validating that the whole part fit in the 32 bytes (`part.at_eof()`).

## 3. Client request construction mutates the per-request header dict and drops a user `Host` on retry/redirect

- **File/line:** `aiohttp/client_reqrep.py:911` (`ClientRequestBase._update_headers`: `headers.popall(hdrs.HOST, (host,))[0]`), with `aiohttp/client.py:606-721` reusing the same `headers` object across loop iterations
- **What goes wrong:** `_update_headers` pops `Host` out of the caller's `CIMultiDict`. `ClientSession._request` builds that dict once and passes the same object to every `ClientRequest` in its `while True` loop. After the first attempt, the user-supplied `Host` is gone.
  - The idempotent-retry path (`ServerDisconnectedError` on a reused keep-alive connection, `continue` at line 721) re-sends the request with the URL's host instead of the caller's header.
  - Reproduced: two GETs with `headers={"Host": "custom.example"}`. The server drops the reused connection on the second request, and the retry arrives with `Host: 127.0.0.1:<port>`.
  - Same-origin redirects lose the custom `Host` the same way.
- **Why it is wrong:** A retry must repeat the same request (RFC 9112 §9.3.1, cited at client.py:604). The user-supplied Host is honoured on the first attempt (`test_host_header_explicit_host`). Silently changing it on retry routes the request to a different virtual host.
- **Severity:** medium
- **Fix:** Don't mutate the input. For example:
  1. `host_vals = headers.getall(hdrs.HOST, (host,))`
  2. `self.headers[hdrs.HOST] = host_vals[0]`
  3. `self.headers.extend((k, v) for k, v in headers.items() if k.lower() != "host")`

  Alternatively, copy `headers` before popping.

## 4. Re-setting a cookie without `Max-Age`/`Expires` keeps the old expiry, so the new cookie is deleted later

- **File/line:** `aiohttp/cookiejar.py:420-436` (`CookieJar._update_cookies`)
- **What goes wrong:** An expiry is only ever added to `self._expirations`. When a cookie that had `Max-Age`/`Expires` is replaced by a session cookie with the same (domain, path, name), the stale deadline stays and `_do_expiration()` later deletes the new cookie.
  - `a=1; Max-Age=1`, then `a=2` (session cookie), then wait 1.2 s: `filter_cookies()` returns nothing. Expected: `a=2`.
- **Why it is wrong:** RFC 6265 §5.3 step 11 says the new cookie replaces the old one. A cookie without Max-Age/Expires has persistent-flag false and expiry "the latest representable date", so it must not inherit the old cookie's deadline. The class docstring claims RFC 6265 adherence.
- **Severity:** medium (session cookies disappear unexpectedly, which causes spurious logouts)
- **Fix:** In the branch where neither `max-age` nor a parseable `expires` applies, clear any existing deadline with `self._expirations.pop((domain, path, name), None)`. Stale heap entries are already ignored by the `self._expirations.get(key) == when` check.

## 5. Generic list splitting of `Link` headers breaks URIs that contain commas

- **File/line:** `aiohttp/client_reqrep.py:492` (`ClientResponse.links` uses `self.headers.getall("link")`), with the splitter in `aiohttp/helpers.py:790-803` / `_LIST_ELEMENT` at lines 76-111
- **What goes wrong:** `HeadersDictProxy.getall` splits on every comma outside quoted-strings and comments. A comma inside `<...>` is a legal URI character (RFC 3986 sub-delims), but the splitter treats it as a separator.
  - `Link: <http://a/x,y>; rel="next", <http://b>; rel="prev"`
  - `getall` returns `('<http://a/x', 'y>; rel="next"', '<http://b>; rel="prev"')`
  - The first element fails the `\s*<(.*)>(.*)` match and is dropped, so `links` loses `rel="next"`. The second element's URL is mangled.
- **Why it is wrong:** RFC 8288 §3 grammar is `link-value = "<" URI-Reference ">" *( OWS ";" OWS link-param )`. The URI-Reference may contain commas.
- **Severity:** low-medium
- **Fix:** For `links`, split only on commas that are followed by `<`, as earlier aiohttp did: `re.split(r",(?=\s*<)", ", ".join(self.headers._md.getall("link", ())))`. Alternatively, teach `_LIST_ELEMENT` to treat `<...>` as an opaque run.

## 6. `Range: bytes=-0` returns the whole file as 206 instead of 416

- **File/line:** `aiohttp/web_request.py:679-685` (`http_range`), consumed at `aiohttp/web_fileresponse.py:334-367`
- **What goes wrong:** A suffix length of 0 produces `start = -0 == 0` and `end = None`. `FileResponse` then treats it as "from byte 0 to end" and sends the full file with `206 Partial Content` and `Content-Range: bytes 0-(n-1)/n`. Found by inspection; the arithmetic is deterministic.
- **Why it is wrong:** RFC 9110 §14.1.1 says a byte-range-set is satisfiable only if it contains a first-byte-pos below the length or "at least one suffix-range with a non-zero suffix-length". `bytes=-0` must yield 416. The comment in `web_fileresponse.py:355-362` quotes that rule, but the code doesn't implement it for suffix ranges.
- **Severity:** low
- **Fix:** In `http_range`, raise `ValueError` (the 416 path) when the suffix length is 0, e.g. `if start is None and end == 0: raise ValueError(...)`.

## 7. `HeadersDictProxy` reports case-variant duplicates as distinct keys

- **File/line:** `aiohttp/helpers.py:813-825` (`__iter__`, `__len__`)
- **What goes wrong:** De-duplication uses the raw key strings from the case-insensitive `CIMultiDict`. Headers `X: 1` and `x: 2` give `len(h) == 2`, `list(h) == ['X', 'x']` and `dict(h) == {'X': '1, 2', 'x': '1, 2'}`, while `h['X'] == h['x']`. Iterating `request.headers.items()` then emits the same combined value twice, and the length disagrees with the number of distinct keys.
- **Why it is wrong:** The comment says "We need to deduplicate keys from MultiDict". `__getitem__` treats keys case-insensitively, so the Mapping contract (iteration yields each key once) is broken.
- **Severity:** low
- **Fix:** Deduplicate on a case-folded key, e.g. `k.lower()` or `istr`, in both `__iter__` and `__len__`.

---

## Checked and not reported

These areas looked suspicious but I'm not confident they are defects, or they are intentional:

- HTTP/1 request/response parser: chunked decoding, trailers, TE/CL conflict, upgrade deferral.
- `StreamReader` buffering and chunk splits.
- `compression_utils` concatenated-member handling and max_length budgeting.
- WebSocket frame reader: masking with folded fragments, control-frame rules, size limits.
- `StreamWriter` header coalescing.
- Static-route path traversal checks.
- Digest auth middleware.
- Redirect credential stripping.
- `CookieJar` domain/path matching.
- `_cookie_helpers` parsing.

## Files read

- `aiohttp/_cookie_helpers.py`
- `aiohttp/helpers.py`
- `aiohttp/http_parser.py`
- `aiohttp/http_writer.py`
- `aiohttp/streams.py`
- `aiohttp/multipart.py` (lines 1-700, 740-1000)
- `aiohttp/compression_utils.py`
- `aiohttp/cookiejar.py`
- `aiohttp/web_fileresponse.py`
- `aiohttp/web_request.py` (lines 115-142, 360-470, 560-1015)
- `aiohttp/web_response.py` (lines 80-792)
- `aiohttp/web_urldispatcher.py` (lines 60-720)
- `aiohttp/web_middlewares.py`
- `aiohttp/web_protocol.py` (lines 380-560)
- `aiohttp/client.py` (lines 440-880, 1228-1255)
- `aiohttp/client_reqrep.py` (lines 470-520, 540-1300)
- `aiohttp/client_middleware_digest_auth.py`
- `aiohttp/connector.py` (lines 1100-1200)
- `aiohttp/_websocket/helpers.py`
- `aiohttp/_websocket/reader_py.py`
- `tests/test_multipart.py` (`Stream` helper and `_charset_` tests, for context only)
