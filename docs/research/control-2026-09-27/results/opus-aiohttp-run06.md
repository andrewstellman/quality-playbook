# aiohttp code review: opus, run 06

- Repo: aiohttp at e11d2836203a21bec59095498e578d37801027e7
- Scope: `aiohttp/` (the package, not the tests)
- Checkout: `/tmp/control/aiohttp` (read-only). I ran snippets in `/tmp/control-work/opus-aiohttp-run06/` using `/tmp/aiohttp-venv` with `AIOHTTP_NO_EXTENSIONS=1`, which exercises the pure-Python paths.

I reproduced defects 1–6 and 8 with small scripts. Defect 7 comes from reading the code; I did not run it.

---

## 1. `chunked=False` makes the client send a chunk-encoded body with a `Content-Length` header

- **File/line:** `aiohttp/client_reqrep.py:1450-1451` (`ClientRequest._create_writer`)
  ```python
  if self.chunked is not None:
      writer.enable_chunking()
  ```
- **What goes wrong:** `ClientSession.request(..., chunked=False)` is a valid value (the type is `bool | None`). With `chunked=False`:
  - `_update_body_from_data` sets `Content-Length` from the payload size.
  - `_update_transfer_encoding` does not add `Transfer-Encoding: chunked`.
  - The writer still enables chunking, because `False is not None`.
- **Reproduced:** `s.post(url, data=b"hello", chunked=False)` sent this on the wire:
  `...Content-Length: 5\r\n...\r\n\r\n5\r\nhello\r\n0\r\n\r\n`
- **Why it is wrong:**
  - The server reads 5 bytes of body (`5\r\nhe`), so the body is corrupted.
  - The leftover bytes (`llo\r\n0\r\n\r\n`) are taken as the start of the next request on a keep-alive connection. This is a request-desync condition.
  - Everywhere else in the class, `self.chunked` is tested for truthiness, not `is not None`: lines 1236, 1242, 1257 and 1280.
- **Severity:** medium
- **Fix:** `if self.chunked: writer.enable_chunking()`

## 2. `Forwarded` header parsing: a quoted value swallows the rest of the field-value

- **File/line:** `aiohttp/web_request.py:138-140` (`_FORWARDED_PAIR`), used by `BaseRequest.forwarded` at lines 387-411
  ```python
  rf'[ \t]*({_TOKEN})=({_TOKEN}|".*")(:\d{{1,4}})?[ \t]*(?:\Z|;)'
  ```
- **What goes wrong:** the quoted-string alternative is the greedy `".*"`. It matches up to the *last* `"` that is followed by `;` or end-of-string.
- **Reproduced:** `Forwarded: for="1.2.3.4";proto=https;by="5.6.7.8"` parses to
  `{'for': '1.2.3.4";proto=https;by="5.6.7.8'}`.
  - `proto` and `by` are lost.
  - `for` contains garbage.
- **Why it is wrong:**
  - The docstring says the method checks that each value is a `token` or `quoted-string` per RFC 7239 §4.
  - A quoted-string cannot contain an unescaped `"`.
  - `_QDTEXT` is defined at lines 131-133 for this purpose but is never used.
- **Impact:** code that reads `request.forwarded[...]['proto']` or `['for']` gets wrong data for any common multi-pair header that uses quoted IPv6 or `for` values.
- **Severity:** medium
- **Fix:** use a real quoted-string production, for example
  `_QUOTED_PAIR = r"\\[\t !-~]"` and `_QUOTED_STRING = rf'"(?:{_QUOTED_PAIR}|{_QDTEXT})*"'`, with `({_TOKEN}|{_QUOTED_STRING})`. Then unescape quoted-pairs in the matched value.

## 3. HTTP/1.0 keep-alive request with a streamed response of unknown length: the server never closes, so the client hangs

- **File/line:** `aiohttp/web_response.py:377-380` and `407-408` (`StreamResponse._prepare_headers`)
  ```python
  keep_alive = self._keep_alive
  if keep_alive is None:
      keep_alive = request.keep_alive
  self._keep_alive = keep_alive
  ...
  elif not self._must_be_empty_body:
      keep_alive = False          # only the local is changed
  ```
- **What goes wrong:** for an HTTP/1.0 request with `Connection: keep-alive`, a response with no `Content-Length` cannot be chunked, so the body can only be delimited by closing the connection.
  - The code clears only the local `keep_alive`. That local controls the `Connection` header only.
  - `self._keep_alive` stays `True`.
  - `web_protocol.py:800` does `self._keepalive = bool(resp.keep_alive)`, so the server keeps the socket open after the handler finishes.
- **Reproduced:** a `StreamResponse` handler that writes `b"hello"`, fetched with raw `GET / HTTP/1.0\r\nConnection: keep-alive\r\n\r\n`. No EOF arrived within 3 s, so the client cannot tell where the body ends. It waits until the keepalive timeout.
- **Why it is wrong:** RFC 1945 §7.2.2 / RFC 9112 §6.3: without a length, the body ends when the connection closes. The code's own branch recognises this and sets `keep_alive = False`, but does not apply it to the response state.
- **Severity:** medium
- **Fix:** in that branch, also set `self._keep_alive = False` (or assign `self._keep_alive = keep_alive` after the length/chunking decision).

## 4. CookieJar: re-setting a cookie without `Max-Age`/`Expires` keeps the old expiry, so the new cookie is deleted early

- **File/line:** `aiohttp/cookiejar.py:396-423` (`CookieJar._update_cookies`)
- **What goes wrong:** when a cookie with the same `(domain, path, name)` is stored again with no `max-age` and no `expires`, `self._expirations` is never cleared for that key. `_do_expiration` then deletes the new session cookie at the old deadline.
  - The same happens when the new `max-age`/`expires` is invalid: line 410 blanks `max-age` but leaves the old expiration in place.
- **Reproduced:** `Set-Cookie: a=1; Max-Age=1`, then `Set-Cookie: a=2`:
  - Immediately afterwards, `filter_cookies` returns `a=2`.
  - After 1.2 s it returns nothing.
- **Why it is wrong:** RFC 6265 §5.3:
  - Step 3: a cookie without Max-Age/Expires is non-persistent, with expiry-time "the latest representable date".
  - Step 11: the new cookie replaces the old one entirely, including its expiry.
- **Severity:** medium (session/auth cookies vanish unexpectedly)
- **Fix:** before scheduling a new expiry for a cookie, remove any stale entry. For example, when no valid max-age/expires is found, `self._expirations.pop((domain, path, name), None)`. The stale heap entry is already ignored, because `_do_expiration` compares against `_expirations`.

## 5. WebSocket reader rejects a message of exactly `max_msg_size` bytes

- **File/line:** `aiohttp/_websocket/reader_py.py:552` (the same logic is compiled into the C reader)
  ```python
  if self._payload_bytes_to_read >= self._max_msg_size - partial_len:
  ```
- **What goes wrong:** a message whose total size equals the limit is rejected.
- **Reproduced:** `max_msg_size=10` with a 10-byte binary frame produces:
  `WebSocketError: Message size 10 exceeds limit 10`
  The error message contradicts itself.
- **Why it is wrong:** the decompressed path in the same class uses `len(payload_merged) > self._max_msg_size` (line 326), so it accepts exactly `max_msg_size`. `max_msg_size` is documented as the maximum allowed size, not an exclusive bound.
- **Severity:** low
- **Fix:** use `>` instead of `>=`.

## 6. `MultipartWriter.decode()` produces malformed multipart (missing CRLFs and closing boundary)

- **File/line:** `aiohttp/multipart.py:1147-1160`
- **What goes wrong:** `decode()` joins `"--"+boundary+"\r\n"+headers+body` for each part.
  - It omits the `\r\n` after each part body, so the next delimiter is glued onto the data.
  - It omits the final `--boundary--\r\n`.
- **Reproduced:** two parts `"a"` and `"b"` give `...\r\n\r\na--B\r\n...\r\n\r\nb`. `as_bytes()` gives `...a\r\n--B...b\r\n--B--\r\n`.
- **Why it is wrong:**
  - RFC 2046 §5.1.1 requires the CRLF before each delimiter and a close-delimiter at the end.
  - `as_bytes()`, `write()` and `size` in the same class all include them, so `decode()` disagrees with the class's own serialisation.
- **Impact:** `web.Response(body=MultipartWriter).text` and similar callers get unparseable output.
- **Severity:** low
- **Fix:** mirror `as_bytes()`: append `"\r\n"` after each part and `"--" + self.boundary + "--\r\n"` at the end.

## 7. `Range: bytes=-0` is served as `206` with the full file instead of `416`

- **Files/lines:**
  - `aiohttp/web_request.py:682-685` (`http_range`): `start = -end` gives `start = 0` when `end == 0`.
  - `aiohttp/web_fileresponse.py:358-395` then treats `start=0, end=None` as "from byte 0 to the end" and returns 206 with the whole representation.
- **Why it is wrong:** RFC 9110 §14.1.3/§14.1.1: a suffix-byte-range-spec is satisfiable only with a *non-zero* suffix-length. `bytes=-0` is unsatisfiable and should produce 416 with `Content-Range: bytes */len`. The comment copied at `web_fileresponse.py:381-387` states this rule.
- **Severity:** low
- **Fix:** in `http_range`, raise `ValueError` (which becomes 416) when the suffix length is 0. Alternatively, handle `end == 0` with no start explicitly.

## 8. `helpers.TOKEN` contains TAB, so token validation accepts it

- **File/line:** `aiohttp/helpers.py:148-173`
  ```python
  TOKEN = CHAR ^ CTL ^ SEPARATORS
  ```
- **What goes wrong:** `SEPARATORS` contains `chr(9)`, which is also in `CTL`.
  - `CHAR ^ CTL` removes TAB.
  - `^ SEPARATORS` then adds it back, because symmetric difference toggles membership.
- **Reproduced:**
  - `'\t' in TOKEN` is `True`.
  - `content_disposition_header("form\tdata")` returns `'form\tdata'` instead of raising `ValueError`.
  - `multipart.parse_content_disposition`'s `is_token` also accepts TAB inside tokens.
- **Why it is wrong:** RFC 2616 §2.2 / RFC 9110 §5.6.2: token excludes CTLs and separators, and HT is both.
- **Severity:** low
- **Fix:** `TOKEN = CHAR - CTL - SEPARATORS`

---

## Files read

- `aiohttp/_cookie_helpers.py` (full)
- `aiohttp/helpers.py` (full)
- `aiohttp/http_parser.py` (full)
- `aiohttp/multipart.py` (full)
- `aiohttp/web_fileresponse.py` (full)
- `aiohttp/web_response.py` (full)
- `aiohttp/cookiejar.py` (full)
- `aiohttp/client_reqrep.py` (lines 60-1561)
- `aiohttp/streams.py` (lines 90-745)
- `aiohttp/web_request.py` (lines 100-1015)
- `aiohttp/web_urldispatcher.py` (lines 330-720)
- `aiohttp/client_middleware_digest_auth.py` (lines 30-507)
- `aiohttp/client.py` (lines 520-900, plus grep for `chunked`/redirect handling)
- `aiohttp/http_writer.py` (lines 60-397)
- `aiohttp/web_ws.py` (`_handshake` / `_pre_start`)
- `aiohttp/_websocket/reader_py.py` (lines 100-634)
- `aiohttp/web_protocol.py` (grep for `keep_alive`)
