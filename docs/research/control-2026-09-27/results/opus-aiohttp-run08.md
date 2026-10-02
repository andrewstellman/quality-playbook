# Code review: aiohttp @ e11d2836203a21bec59095498e578d37801027e7

Scope: `aiohttp/` (package, excluding tests). Checkout: `/tmp/control/aiohttp` (read-only).
Every defect below was reproduced with a small script run against the checkout (pure-Python code paths, `/tmp/aiohttp-venv`), unless noted otherwise.

---

## 1. `chunked=False` produces a chunk-encoded body under a `Content-Length` header (request framing corruption)

- **File/line:** `aiohttp/client_reqrep.py:1450` (`ClientRequest._create_writer`)
- **What goes wrong:** `_create_writer` enables chunked framing whenever `self.chunked is not None`:
  ```python
  if self.chunked is not None:
      writer.enable_chunking()
  ```
  If a caller passes `chunked=False` (a legal value; the type is `bool | None`), `_update_body_from_data` treats it as "not chunked" and sets `Content-Length` (lines 1280-1284). No `Transfer-Encoding` header is added (line 1242). The writer still chunk-encodes the body anyway.
  Reproduced with `session.post(url, data=b"abc", chunked=False)`. The wire bytes were:
  ```
  POST / HTTP/1.1 ... Content-Length: 3 ... \r\n\r\n3\r\nabc\r\n0\r\n\r\n
  ```
  The server reads the first 3 bytes (`3\r\n`) as the body. It then treats `abc\r\n0\r\n\r\n` as the start of the next request on a keep-alive connection. The same thing happens with `data=None` on POST: `Content-Length: 0` is sent, followed by a stray `0\r\n\r\n`.
- **Why it is wrong:** The docs (`docs/client_reference.rst:493`) say chunked encoding is used only "if chunking is enabled". Every other place in the class treats the flag as a boolean (`if self.chunked:` at lines 1236, 1242, 1257, 1280). RFC 9112 §6 requires the message framing to match the headers. This is a request-desync / smuggling-class bug.
- **Severity:** high
- **Fix:** Use `if self.chunked: writer.enable_chunking()`.

## 2. `Forwarded` parsing merges multiple quoted parameters into one value

- **File/line:** `aiohttp/web_request.py:138-141` (`_FORWARDED_PAIR`), used at `:385-409` (`BaseRequest.forwarded`)
- **What goes wrong:** The quoted-string alternative is the greedy `".*"`. `re.match` anchors at `pos` and the pattern ends with `(?:\Z|;)`, so `.*` runs to the last `"` in the element. Examples:
  - `Forwarded: for="192.0.2.1";by="10.0.0.1"` gives `{'for': '192.0.2.1";by="10.0.0.1'}`. The `for` value is corrupted and `by` is lost.
  - `for="[2001:db8::1]";proto=https` works only because there is a single quoted value.
  - Any element with two or more quoted parameters is mis-parsed, and RFC 7239 requires quoting IPv6 and ports. Proxies and apps that read `request.forwarded[...]["for"]` get garbage.
  - The pattern also accepts control characters inside the quotes.
- **Why it is wrong:** The docstring says it "checks that every value has valid syntax ... either a 'token' or a 'quoted-string'". `_QDTEXT` (lines 131-133) is defined for exactly this, but it is never used. RFC 7239 §4 uses `forwarded-pair = token "=" value` with `value = token / quoted-string`.
- **Severity:** medium
- **Fix:** Replace `".*"` with a proper quoted-string, e.g. `rf'"(?:{_QDTEXT}|\\[\t !-~])*"'` (qdtext / quoted-pair), and unescape quoted-pairs in the extracted value.

## 3. A session cookie that replaces a persistent cookie is later deleted at the old expiry

- **File/line:** `aiohttp/cookiejar.py:396-416` (`CookieJar._update_cookies`)
- **What goes wrong:** An expiry is only ever added with `_expire_cookie(...)`. It is never cleared when the same `(domain, path, name)` is replaced by a cookie that has no `Max-Age`/`Expires`, so the stale entry in `self._expirations` and the heap survives. Repro:
  ```
  a=1; Max-Age=1   → then  a=2   (session cookie)
  immediately: {'a': a=2}; after 1.2 s: {}   (a=2 deleted)
  ```
- **Why it is wrong:** RFC 6265 §5.3 step 3 says a cookie without Max-Age/Expires gets `persistent-flag = false` and expiry "the latest representable date". Step 11 says the new cookie replaces the old one, including its expiry. The class docstring claims RFC 6265 adherence.
- **Severity:** medium (session state silently vanishes)
- **Fix:** When neither a valid Max-Age nor a valid Expires is present, drop the previous deadline, e.g. `self._expirations.pop((domain, path, name), None)`. The heap entries are already filtered by the `self._expirations.get(key) == when` check.

## 4. An invalid `Max-Age` suppresses a valid `Expires`

- **File/line:** `aiohttp/cookiejar.py:396-416`
- **What goes wrong:** Expires is checked in an `elif` that only runs when Max-Age is empty. If Max-Age is present but not an integer, the `ValueError` handler blanks it, but the `Expires` branch is skipped. Repro: `b=1; Max-Age=abc; Expires=Thu, 01 Jan 1970 00:00:00 GMT` is stored and sent as a live cookie, when it should be expired or deleted.
- **Why it is wrong:** RFC 6265 §5.2.2 says an invalid Max-Age is ignored ("ignore the cookie-av"). Expires must then govern (§5.3 step 3).
- **Severity:** low
- **Fix:** Fall through to the Expires handling when Max-Age parsing fails. For example, compute `max_age_valid` first and use `if max_age_valid: ... elif expires: ...`.

## 5. WebSocket reader rejects a message whose size equals `max_msg_size`

- **File/line:** `aiohttp/_websocket/reader_py.py:552` (also compiled into the Cython reader via `reader_c.pxd`)
- **What goes wrong:** `if self._payload_bytes_to_read >= self._max_msg_size - partial_len:` rejects a message of exactly `max_msg_size` bytes. Repro with `max_msg_size=10`:
  - an unfragmented 10-byte binary frame fails with `Message size 10 exceeds limit 10`
  - a 5+5 fragmented message fails the same way
- **Why it is wrong:** The error text itself says "exceeds limit". The compressed path allows `len(payload_merged) == max_msg_size` (line 326, `>`). The docs call `max_msg_size` the "maximum size of read websocket message". The two paths behave differently at the boundary.
- **Severity:** low
- **Fix:** Use `>` (i.e. `if self._payload_bytes_to_read > self._max_msg_size - partial_len`). The subtraction form still avoids overflow.

## 6. Access-log format: documented `%%` breaks every log line, and documented `%{FOO}e` raises at construction

- **File/line:** `aiohttp/web_log.py:62-63, 110-123`
- **What goes wrong:**
  - `CLEANUP_RE = r"(%[^s])"` turns `%%` into `%%%`. `'%a %% x'` compiles to `'%s %%% x'`, and formatting then raises `TypeError: not enough arguments`. `log()` catches this, so every request logs "Error in logging" instead of the access line. `'100%% %s'` raises `ValueError`.
  - `FORMAT_RE` accepts `([ioe])` and `O`, but `LOG_FORMAT_MAP` has no `"e"`/`"O"` and there is no `_format_e`/`_format_O`. `AccessLogger(logger, '%{HOME}e')` raises `KeyError: 'e'`, and `'%O'` raises `KeyError: 'O'`.
- **Why it is wrong:** `docs/logging.rst:71` documents ``%%`` as "The percent sign". The class docstring (line 43) documents `%{FOO}e  os.environ['FOO']`.
- **Severity:** low
- **Fix:** Translate literal `%%` to `%%` (do not re-escape it). For example, run a single `re.sub` with a callback over `%%|FORMAT_RE|%` that emits `%%` for literals and `%s` for atoms. Either implement `_format_e` (and `O`) or remove them from `FORMAT_RE` and the docstring.

## 7. `MultipartWriter.decode()` output is not the multipart body

- **File/line:** `aiohttp/multipart.py:1147-1160`
- **What goes wrong:** `decode()` omits the `\r\n` after each part body and the closing `--boundary--\r\n`. For two parts `a` and `b`, it returns `'...\r\n\r\na--B\r\n...\r\n\r\nb'`, while `as_bytes()` returns `'...a\r\n--B...b\r\n--B--\r\n'`.
- **Why it is wrong:** The docstring says it returns the "string representation of the multipart data" and recommends `as_bytes().decode()` as the equivalent. `Response(body=MultipartWriter).text` and any `Payload.decode()` consumer get a malformed body.
- **Severity:** low
- **Fix:** Mirror `as_bytes()`: append `"\r\n"` after each part and `"--" + boundary + "--\r\n"` at the end.

## 8. `Range: bytes=-0` is served as a 206 of the whole file instead of 416

- **File/line:** `aiohttp/web_request.py:681-685` (`http_range`), consumed at `aiohttp/web_fileresponse.py:358-395`
- **What goes wrong:** Suffix length 0 becomes `start = -0 = 0`, `end = None`. `FileResponse` then takes the `else` branch and sends `206` with `Content-Range: bytes 0-(n-1)/n` and the entire file.
- **Why it is wrong:** RFC 9110 §14.1.1 / §15.5.17 say a byte-range-set is satisfiable only with a first-byte-pos below the length "or at least one suffix-range with a non-zero suffix-length". `bytes=-0` must yield 416. The code's own comment at `web_fileresponse.py:381-387` quotes this rule.
- **Severity:** low
- **Fix:** In `http_range`, raise `ValueError` (which becomes a 416) when `start is None and end == 0`.

---

## Items examined and not reported (judged correct or not confidently defective)

- Digest auth middleware: parsing, protection space, origin pinning.
- HTTP request/response parser: chunked parsing, trailers, CL/TE conflict, lax mode.
- `StreamReader` flow control.
- Compression member handling.
- Static route traversal checks.
- Redirect credential stripping.
- Connector pooling/limits.
- WebSocket extension negotiation. The client branch using `client_max_window_bits` is RFC 7692-correct for the client's compressor.

One minor oddity was not reported: `HttpParser.feed_eof` (`http_parser.py:324`) compares bytes to the str `"\r\n"`, so the comparison is always true. It has no observable effect.

## Files actually read

- aiohttp/client_middleware_digest_auth.py
- aiohttp/helpers.py
- aiohttp/_cookie_helpers.py
- aiohttp/cookiejar.py
- aiohttp/http_parser.py
- aiohttp/streams.py
- aiohttp/multipart.py
- aiohttp/compression_utils.py (lines 150-529)
- aiohttp/web_fileresponse.py (lines 100-438)
- aiohttp/web_request.py (lines 95-930)
- aiohttp/web_response.py
- aiohttp/web_urldispatcher.py (lines 60-80, 340-860, 973-1256)
- aiohttp/client.py (lines 440-945, 1090-1180)
- aiohttp/client_reqrep.py (lines 60-110, 484-520, 600-760, 815-1561)
- aiohttp/connector.py (lines 600-925, 1125-1340, 1515-1690)
- aiohttp/http_writer.py
- aiohttp/_websocket/helpers.py
- aiohttp/_websocket/reader_py.py (lines 180-634)
- aiohttp/web_ws.py (lines 200-420)
- aiohttp/web_middlewares.py
- aiohttp/web_log.py (lines 40-224)
- aiohttp/web_protocol.py (lines 380-700)
- aiohttp/payload.py (lines 150-720)
- aiohttp/formdata.py
- aiohttp/resolver.py (lines 1-140)
- Context only: tests/test_websocket_parser.py (lines 740-915), docs/client_reference.rst (chunked param), docs/logging.rst (format table)
