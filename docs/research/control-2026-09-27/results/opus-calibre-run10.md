# Code review: calibre `src/calibre/srv/` (pinned 7691f4f1a155d799afdfec99e2cdc2716c178402)

Reviewer: opus, run10. Checkout: `/tmp/control/calibre` (read-only). I confirmed findings 1-6 and 8 by running the affected functions, lightly stubbed, from the checkout on Python 3.10 (scratch dir `/tmp/control-work/opus-calibre-run10/`, deleted afterwards). Findings 7, 9 and 10 come from reading the code only.

---

## 1. Negative chunk sizes are accepted, which bypasses `max_request_body_size`

- **File/line:** `src/calibre/srv/http_request.py:426` (`chunk_size = int(line.strip(), 16)`), plus lines 429, 437 and 442.
- **What goes wrong:** `int(x, 16)` accepts a sign, so a chunk-size line of `-100000` gives `chunk_size = -100000`. The limit check at line 429 (`bytes_read[0] + chunk_size + 2 > max`) passes. `read_chunk` gets `end = buf.tell() + chunk_size`, which is behind the current position. `read()` then returns True immediately because `size <= 0`. Line 442 adds the negative size to `bytes_read[0]`, which drives the running total negative. The client can then send real chunks of any size, and every later size check (lines 429 and 452) passes.
  - `int(..., 16)` also accepts `0x1F4`, `+1F4` and `1_F4`, none of which are valid `chunk-size = 1*HEXDIG` (RFC 9112 §7.1). A front-end proxy may read those lines differently, which is a request-smuggling risk.
- **Reproduced:** with `max_request_body_size = 100`, this body completed with `prepare_response` and a 500-byte request body:

  ```
  -100000\r\n\r\n1F4\r\n<500 bytes>\r\n0\r\n\r\n
  ```

- **Why it is wrong:** lines 429-433 and 452-456 are meant to enforce `max_request_body_size` on chunked bodies, and non-chunked bodies are rejected at line 390. The body is spooled to a `SpooledTemporaryFile` on disk, so an unauthenticated client can fill the server's temp directory.
- **Severity:** high (unauthenticated resource exhaustion; parsing that differs from the RFC).
- **Fix:** strip chunk extensions, then require the size field to match `^[0-9A-Fa-f]+$` before calling `int(..., 16)`. Otherwise return 400.

## 2. `is_http1` is always False, so HTTP/1.0 clients get chunked responses, gzip and ranges

- **File/line:** `src/calibre/srv/http_response.py:561`: `output = self.finalize_output(output, data, self.method is HTTP1)`
- **What goes wrong:** `self.method` is the request method (`'GET'`, `'POST'`, ...) and `HTTP1` is `'HTTP/1.0'`, so the expression is always False. `finalize_output` uses `is_http1` to turn off compression (line 757) and range support (line 759) for HTTP/1.0. Those guards never fire, so an HTTP/1.0 request gets:
  - `Transfer-Encoding: chunked` plus a chunk-encoded body whenever the output is compressible or has unknown length (lines 793-794).
  - `Accept-Ranges`.
- **Reproduced:** an HTTP/1.0 request with `Accept-Encoding: gzip` for a 3.5 KB JSON body got `Content-Encoding: gzip` and `Transfer-Encoding: chunked`.
- **Why it is wrong:** chunked transfer coding does not exist in HTTP/1.0. The author meant to guard against this; `simple_response` (line 460) correctly tests `self.response_protocol is HTTP1`. An HTTP/1.0 client, or a 1.0 proxy such as a default nginx `proxy_pass`, will read the raw chunk framing as part of the body.
- **Severity:** medium.
- **Fix:** pass `self.response_protocol is HTTP1`.

## 3. A range request on a compressible response sends `Transfer-Encoding: chunked` with an un-chunked body

- **File/line:** `src/calibre/srv/http_response.py:751-758`, 784, 790, 793-794 and 796-801.
- **What goes wrong:** `compressible` is decided before ranges are considered. For a compressible resource, `ranges` is still computed (line 760), because `output.accept_ranges` is True for files and readable outputs. The rest then plays out like this:
  - Line 784 (`compressible and not ranges`) skips gzip.
  - Line 793 (`if compressible or output.content_length is None`) still adds `Transfer-Encoding: chunked`.
  - Lines 796-801 add `Content-Length` and `Content-Range` and return a `ReadableOutput`.
  - `write_response_body` writes that output raw, not chunk-framed.
- **Reproduced:** a 5000-byte `text/css` file requested with `Accept-Encoding: gzip` and `Range: bytes=0-9` returned 206 with `Transfer-Encoding: chunked`, `Content-Length: 10` and `Content-Range: bytes 0-9/5000`, and the body was written raw.
- **Why it is wrong:** the headers do not describe the body. A client tries to parse the 10 raw bytes as chunk framing and fails. Sending both TE and CL is also forbidden (RFC 9112 §6.2). The code's own intent is that ranges and compression are exclusive (`accept_ranges = not compressible ...`, `if compressible and not ranges`).
- **Severity:** medium. Static JS/CSS, OPF/XML and similar files trigger it whenever a client sends both headers.
- **Fix:** after computing `ranges`, set `compressible = compressible and not ranges` and use that value everywhere. Alternatively, don't compute ranges when compressible is True.

## 4. `BanList.failed()` never prunes old entries, so bans do not reset and memory grows without bound

- **File/line:** `src/calibre/srv/auth.py:53-58`.
- **What goes wrong:** `self.items` is an `OrderedDict` with the newest entry at the end. The loop iterates `reversed(self.items)`, which starts with the key that was just inserted with `now`. `now - previous_fail > interval` is False for that key, so the loop `break`s on the first iteration and never removes anything. Two effects follow:
  - (a) Every failing remote address stays in memory forever, which is unbounded growth.
  - (b) An address's failure count is never reset. After the ban interval expires, a single further failed attempt bans the address again for the full interval, instead of allowing `max_failures_before_ban` attempts.
- **Reproduced:** with `max_failures_before_ban=3`, address `a` was banned after three failures. After the interval it was unbanned. One more failure banned it again immediately, and the stale entry for `a` was still present after a failure from a different address.
- **Why it is wrong:** the pruning loop exists only to drop entries older than `interval`. Iterating from newest to oldest makes it dead code.
- **Severity:** medium (memory growth driven by the remote side; incorrect ban semantics).
- **Fix:** iterate oldest-first: `for old in self.items:` (or `iter(self.items)`), keeping the same break condition.

## 5. `Accept-Encoding: gzip;q=0` still gets gzip, and q-values after `; ` are ignored

- **File/line:** `src/calibre/srv/utils.py:237-248` (`sort_q_values`) and `src/calibre/srv/http_response.py:101-105` (`acceptable_encoding`). `preferred_lang` at `http_response.py:111` is affected too.
- **What goes wrong:**
  - (a) Items with `q=0` are kept (only sorted last). `acceptable_encoding` returns the first allowed item, so `Accept-Encoding: gzip;q=0, identity` gives `'gzip'` and the response is compressed.
  - (b) In `item()`, `p` is not stripped. For `en; q=0.1`, `p` is `' q'`, which is not equal to `'q'`, so q is treated as 1.0.
- **Reproduced:**
  - `sort_q_values('gzip;q=0, identity')` returns `('identity', 'gzip')`.
  - `sort_q_values('en; q=0.1, fr; q=0.9')` returns `('en', 'fr')`.
- **Why it is wrong:** RFC 9110 §12.4.2 says `q=0` means "not acceptable", and optional whitespace is allowed around `;` in weighted lists. The docstring says the function handles `a;q=0.5, b;q=0.7`-style headers.
- **Severity:** low.
- **Fix:** strip `p` and `v` and compare case-insensitively. In `sort_q_values`, drop items whose q is 0.

## 6. Malformed `Range` values cause a 500, and `bytes=-0` gives an invalid 206

- **File/line:** `src/calibre/srv/http_response.py:138` and 152-161.
- **What goes wrong:**
  - (a) `start, stop = (x.strip() for x in brange.split('-', 1))` is not inside the `try`. `Range: bytes=5`, or any range spec without a `-`, raises `ValueError`. That propagates out of `finalize_output`/`job_done` and becomes a 500 Internal Server Error.
  - (b) For a suffix range of `0` (`bytes=-0`), the code appends `Range(content_length, content_length-1, 0)` and returns `206` with `Content-Range: bytes 100-99/100` and `Content-Length: 0`. The same happens for any suffix range when the content length is 0.
- **Reproduced:** both cases.
- **Why it is wrong:** RFC 9110 §14.2 says a server should ignore a syntactically invalid Range header, and §14.1.3 says a suffix-length of 0 is unsatisfiable. The function's own docstring says an empty list means "no valid range" (which leads to a 416), not a crash.
- **Severity:** low. Any client can trigger error responses and tracebacks in the log.
- **Fix:** move the split inside the `try` and `continue` on failure. Skip suffix ranges where `stop == 0` or `content_length == 0`.

## 7. Book formats can be served inline without the sandbox headers used for other user content

- **File/line:** `src/calibre/srv/content.py:258-263` (`book_fmt`). Compare lines 179-208 and 589-597.
- **What goes wrong:** `book_fmt` accepts `?content_disposition=inline`. `sanitize_content_disposition` keeps letters, so `inline` passes. The file is served from `fcache/.../fmt-<lib>-<id>.<fmt>`, and `finalize_output` derives `Content-Type` from that extension (`http_response.py:729-737`). For formats such as `HTML`, `XHTML` or `SVG`, `/get/html/<id>?content_disposition=inline` renders book-supplied HTML/script on the content server's origin. `add_sandbox_headers()` is never called on this path.
- **Why it is wrong:** the module added `add_sandbox_headers` specifically so that "user supplied content that is rendered inline by the browser" cannot script the server's origin (docstring at lines 200-205). It applies it to data files (line 593), which accept the same `content_disposition` parameter, and to note resources (line 526), but not to book formats.
- **Severity:** medium (stored XSS via a crafted book plus a crafted link; it needs a book with such a format in the library).
- **Fix:** in `book_fmt`, call `add_sandbox_headers(rd, guess_type('x.' + fmt)[0] or '')`, or force `attachment` for scriptable types.

## 8. `Accept-Ranges: bytes` is advertised for responses that ignore `Range`

- **File/line:** `src/calibre/srv/http_response.py:759`: `accept_ranges = not compressible and output.accept_ranges is not None and ...`
- **What goes wrong:** `accept_ranges` is always a bool (`True`/`False`, lines 362, 392 and 411), never `None`, so that sub-condition is always true. Dynamic `str`/`bytes` and generated outputs set `accept_ranges = False`, yet still get `Accept-Ranges: bytes`. Their `Range` requests are then silently answered with a full 200.
- **Reproduced:** a `bytes` output with `Range: bytes=0-1` returned 200 with `Accept-Ranges: bytes`.
- **Severity:** low.
- **Fix:** use `output.accept_ranges` (truthiness) instead of `is not None`.

## 9. `X-Forwarded-For` is dropped for requests with `Expect: 100-continue`

- **File/line:** `src/calibre/srv/http_request.py:396-399`.
- **What goes wrong:** the `Expect: 100-continue` branch returns before `self.forwarded_for = inheaders.get('X-Forwarded-For')`. For those requests (typically uploads through a reverse proxy), the access log records the proxy's address without the forwarded client address.
- **Severity:** low.
- **Fix:** assign `forwarded_for` before the `Expect` check.

## 10. WebSocket close codes of 5000 and above are accepted

- **File/line:** `src/calibre/srv/web_socket.py:418`.
- **What goes wrong:** the validity check rejects `<1000`, the reserved codes 1004-1006, and 1012-2999. It accepts any value of 5000 or more (up to 65535) and echoes it back.
- **Why it is wrong:** RFC 6455 §7.4.2 defines codes only up to 4999, and the Autobahn suite that this file refers to (line 553) treats codes of 5000 and above as a protocol error.
- **Severity:** low.
- **Fix:** add `or close_code >= 5000` to the condition.

---

## Files read

- `src/calibre/srv/http_request.py` (full)
- `src/calibre/srv/http_response.py` (full)
- `src/calibre/srv/web_socket.py` (full)
- `src/calibre/srv/auth.py` (full)
- `src/calibre/srv/utils.py` (full)
- `src/calibre/srv/loop.py` (lines 40-380; exception handling around lines 540-670 via grep)
- `src/calibre/srv/routes.py` (full)
- `src/calibre/srv/handler.py` (full)
- `src/calibre/srv/errors.py` (full)
- `src/calibre/srv/content.py` (full)
- `src/calibre/srv/books.py` (lines 120-373)
- `src/calibre/srv/cdb.py` (lines 1-120)
- `src/calibre/srv/opts.py` (grep: `compress_min_size`, `use_sendfile`)
- `src/calibre/srv/tests/auth.py` (grep: ban tests)
- `src/calibre/utils/filenames.py` (`path_from_root`)
- `src/calibre/db/cli/main.py` (grep: `Accept` header)
