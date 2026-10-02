# Code review: calibre `src/calibre/srv/` (pinned 7691f4f1a155d799afdfec99e2cdc2716c178402)

Reviewer: opus, run09. Checkout: `/tmp/control/calibre` (read-only).

Method: I read the HTTP/WebSocket server core (request parsing, response generation, event loop, auth, utils) in full, plus parts of the endpoint modules. Where I could, I checked a suspicion by running the extracted function under Python 3.10 with light stubs. The package itself can't be imported. Findings marked "verified" were reproduced that way. The rest are established by reading the code.

---

## 1. Range request plus `Accept-Encoding: gzip` produces a response with both `Transfer-Encoding: chunked` and `Content-Length`, and the body is not chunked (verified)

- **File/line:** `src/calibre/srv/http_response.py:784-807` (specifically 793)
- **What goes wrong:** Take a response that is compressible (text/css, JS, JSON etc., ≥ `compress_min_size`, client sends `Accept-Encoding: gzip`) and ranged (the client sends `Range:` for a filesystem-backed output such as `/static/...`). Line 784 skips gzip because `ranges` is set. But line 793 still does `if compressible or output.content_length is None: outheaders.set('Transfer-Encoding', 'chunked')`. The range branch (796-801) then also sets `Content-Length`/`Content-Range`, and `write_response_body` sends the raw byte range via `write_buf`/`write_ranges`, with no chunk framing.
  Reproduced: requesting a 5000-byte `.css` file with `Accept-Encoding: gzip`, `Range: bytes=0-99` yields headers `Transfer-Encoding: chunked`, `Content-Length: 100`, `Content-Range: bytes 0-99/5000`.
- **Why it is wrong:** RFC 7230 §3.3.2 says a sender MUST NOT send Content-Length when Transfer-Encoding is present. A client will decode the body as chunked (TE wins), so it gets a corrupted or failed response, and the keep-alive connection desyncs. The code's own intent at 784 (`compressible and not ranges`) shows ranged responses are meant to be uncompressed and unchunked.
- **Severity:** medium
- **Fix:** Resolve the conflict once, e.g. `if ranges: compressible = False` before line 782. Or change 793 to `if (compressible and not ranges) or output.content_length is None:`.

## 2. `is_http1` is always False: the method string is compared to the protocol string (verified by inspection)

- **File/line:** `src/calibre/srv/http_response.py:561`
- **What goes wrong:** `self.finalize_output(output, data, self.method is HTTP1)`. `self.method` is `'GET'`, `'POST'` etc., and `HTTP1` is `'HTTP/1.0'` (`utils.py:25`), so the argument is always False. Inside `finalize_output` (757, 759), `not is_http1` is meant to disable gzip-chunked output and range support for HTTP/1.0 clients. So an HTTP/1.0 client that sends `Accept-Encoding: gzip` gets `Transfer-Encoding: chunked` with a chunked, gzipped body, and 1.0 clients also get `Accept-Ranges`/206 handling.
- **Why it is wrong:** The parameter's clear purpose is to detect an HTTP/1.0 client. RFC 7230 §3.3.1: a server MUST NOT send a response containing Transfer-Encoding unless the request indicates HTTP/1.1 or later. HTTP/1.0 clients can't decode chunked bodies.
- **Severity:** medium
- **Fix:** `self.finalize_output(output, data, self.response_protocol is HTTP1)`.

## 3. A malformed Request-URI gets a 400, but the connection is kept alive with the header block unread, so the headers are parsed as new requests

- **File/line:** `src/calibre/srv/http_request.py:328-331`
- **What goes wrong:** When `parse_uri` raises (for example `GET /%FF HTTP/1.1`, which is invalid UTF-8, or a URI containing `#`), the server calls `simple_response(..., close_after_response=False)`. That happens right after the request line, before any header line or body has been read. After the 400 is written, `reset_state()` → `connection_ready()` goes back to `parse_request_line`. The request's own header lines (and any body) are then read as the next request line(s). A client that sends one request gets two or more responses. A crafted "header" line such as `GET /other HTTP/1.1` is executed as a separate request, which is a response-desync / request-smuggling primitive when calibre sits behind a proxy.
- **Why it is wrong:** Every other error raised during request-line or header parsing uses the default `close_after_response=True`, because the stream position is unknown. Keep-alive is only safe once the full message (headers + body) has been consumed.
- **Severity:** medium
- **Fix:** Drop `close_after_response=False` at line 331, i.e. close after the error. Alternatively, record the error, finish reading headers and body, and only then respond.

## 4. `simple_response` overrides the client's connection-close decision

- **File/line:** `src/calibre/srv/http_response.py:468` (callers at 493 and 557)
- **What goes wrong:** `simple_response` unconditionally does `self.close_after_response = close_after_response`. Two callers pass False:
  - `job_done` passes `e.close_connection`, which is False by default for every `HTTPSimpleResponse`/`HTTPNotFound`/`HTTPRedirect`/`HTTPAuthRequired` (`errors.py:16`).
  - The TRACE path passes False explicitly.

  In both cases a request that asked for `Connection: close`, or an HTTP/1.0 request without `keep-alive` (`finalize_headers`, `http_request.py:366-370`), gets keep-alive behaviour. The server omits `Connection: close` and doesn't close the socket, so a 1.0 client that reads to EOF hangs until the server timeout.
- **Why it is wrong:** `finalize_headers` computes `close_after_response` from the request precisely so the response honours it. The normal success path (`job_done` 568-576) respects it, and the error path should too (RFC 7230 §6.3/§6.6).
- **Severity:** low
- **Fix:** `self.close_after_response = close_after_response or self.close_after_response`. Pair it with fix #3, since that is the one place where forcing a close is required.

## 5. 416 response has no `Content-Length` on a kept-alive connection

- **File/line:** `src/calibre/srv/http_response.py:521-529`
- **What goes wrong:** `send_range_not_satisfiable` emits the status line, `Date` and `Content-Range`, with no `Content-Length`, and then `reset_state()` keeps the connection open. For a 416 (which is not a no-body status such as 1xx/204/304), RFC 7230 §3.3.3 rule 7 says the body extends until the connection closes. The client therefore waits for more body until the server's inactivity timeout.
- **Why it is wrong:** Compare `send_not_modified` right below, which does include `Content-Length: 0`. The message length is otherwise undefined.
- **Severity:** low
- **Fix:** Add `'Content-Length: 0'` to `buf` in `send_range_not_satisfiable`.

## 6. Negative (or `0x`/`+`/`_`-prefixed) chunk sizes are accepted; negative sizes bypass `max_request_body_size`

- **File/line:** `src/calibre/srv/http_request.py:426-442`
- **What goes wrong:** `int(line.strip(), 16)` accepts `-1F`, `+10`, `0x10`, `1_0`. For a negative size, `read_chunk` computes `end = buf.tell() + chunk_size` (below the current position), so `read()` returns True immediately with nothing read. Then `bytes_read[0] += chunk_size` *decreases* the running total. A client can alternate chunks like `-FFFFFF\r\n\r\n` with real data chunks to keep `bytes_read` under the limit, so the size check at 429/452 never fires. The server then spools an unbounded body to disk (the SpooledTemporaryFile in `tdir`).
- **Why it is wrong:** RFC 7230 §4.1 defines `chunk-size = 1*HEXDIG`. The `max_request_body_size` check exists to bound the stored body.
- **Severity:** medium (disk-exhaustion DoS; lower if authentication precedes it, but body reading happens before any endpoint/auth dispatch)
- **Fix:** Validate the token before converting, e.g. strip any `;ext` (see also note below), then require `re.fullmatch(rb'[0-9A-Fa-f]+', token)` before `int(token, 16)`.
  - Related: chunk extensions (`1a;name=val`) are legal per RFC 7230 §4.1.1 but are rejected with 400 here. That's minor.

## 7. `Range` values without a `-` raise an uncaught ValueError (500) (verified)

- **File/line:** `src/calibre/srv/http_response.py:138`
- **What goes wrong:** `start, stop = (x.strip() for x in brange.split('-', 1))` isn't inside the try. `Range: bytes=5` (or `bytes=0-1,5`) raises `ValueError: not enough values to unpack`. That propagates out of `finalize_output`/`job_done` into the loop's generic handler, which logs a traceback and returns 500.
- **Why it is wrong:** The docstring says an empty/None result signals no valid range. Malformed ranges elsewhere in the function are skipped (`continue`), and RFC 7233 §3.1 says an invalid Range header should be ignored.
- **Severity:** low
- **Fix:** `start, sep, stop = brange.partition('-')`, then `if not sep: continue`.
  - Related edge: `bytes=-0` returns `Range(content_length, content_length-1, 0)` instead of being unsatisfiable (RFC 7233 §2.1: a suffix-length of 0 is unsatisfiable). Add `if stop == 0: continue` in the suffix branch.

## 8. `Accept-Ranges: bytes` is advertised for outputs that don't support ranges (verified)

- **File/line:** `src/calibre/srv/http_response.py:759`
- **What goes wrong:** `output.accept_ranges is not None` is always True, because `accept_ranges` is a bool (`False` for `dynamic_output` and `GeneratedOutput`). So dynamic responses (e.g. `b'hello'`) get `Accept-Ranges: bytes`, while line 760 (`if output.accept_ranges`) correctly ignores `Range` for them. Reproduced: a bytes output gives `{'Accept-Ranges': ['bytes'], 'Content-Length': ['5']}`.
- **Why it is wrong:** The header promises byte-range support that line 760 won't honour. Resuming clients will then get 200 full bodies.
- **Severity:** low
- **Fix:** `accept_ranges = not compressible and output.accept_ranges and ...`.

## 9. `q=0` in `Accept-Encoding` is treated as acceptable, so gzip is sent to clients that refused it (verified)

- **File/line:** `src/calibre/srv/utils.py:232-248` (used by `http_response.py:101-105` and `preferred_lang`)
- **What goes wrong:** `sort_q_values` only sorts. It never drops q=0 entries, so `Accept-Encoding: gzip;q=0` still makes `acceptable_encoding` return `'gzip'`. Reproduced: the response gets `Content-Encoding: gzip`. Also, parameters with whitespace (`gzip; q=0.5`, legal OWS) aren't parsed, because `p == 'q'` fails on `' q'`, and they default to q=1.0.
- **Why it is wrong:** RFC 7231 §5.3.1: "a value of 0 means 'not acceptable'".
- **Severity:** low
- **Fix:** In `item()`, use `p.strip() == 'q'`. Filter out entries with `q == 0` before returning.

## 10. Event loop closes the wrong connection when an SSL connection needs closing

- **File/line:** `src/calibre/srv/loop.py:615-616`
- **What goes wrong:**
  ```python
  for x, conn in close_needed:
      self.close(s, conn)
  ```
  The loop variable is `x`, but `s` is passed. `s` is a leftover from the preceding `for s, conn in ...` loops (the last connection-map entry, or the last timed-out socket). `ServerLoop.close` does `self.connection_map.pop(s)` and `conn.close()`. The result is that the dead SSL connection's `conn` is closed but its map entry stays behind (it will be iterated again next tick). Meanwhile some *other*, unrelated live connection is removed from `connection_map` without being closed, which leaks its socket and silently drops its client.
- **Why it is wrong:** An obvious variable mix-up. The intent is to close the connections collected in `close_needed`.
- **Severity:** medium (only with SSL enabled, when a client disconnects during `drain_ssl_buffer`)
- **Fix:** `for s2, conn in close_needed: self.close(s2, conn)`.

## 11. `BanList` never purges expired entries, and a formerly banned IP is re-banned after a single failure (verified)

- **File/line:** `src/calibre/srv/auth.py:44-60`
- **What goes wrong:** The purge loop iterates `reversed(self.items)`, i.e. newest first. The newest entry is always the key just re-inserted (age 0), so the loop breaks immediately and nothing is ever removed. Reproduced: after the interval expires, failing with a new key leaves all 6 entries in the dict. Consequences:
  - Memory grows without bound, with one entry per distinct failing remote address.
  - Because `failed()` reuses the old `fail_count` regardless of age, an IP whose ban has expired is banned again on its very next failed attempt. Reproduced: `fail_count` 3, `is_banned` True after one failure.
- **Why it is wrong:** The purge clearly intends to drop entries older than `interval`, scanning oldest-first until the first fresh one (the `else: break`). That only works when iterating in insertion order.
- **Severity:** low
- **Fix:**
  - Iterate `for old in self.items:` (oldest first).
  - In `failed()`, reset `fail_count` to 0 when `now - x[0] > self.interval`.

## 12. WebSocket close codes ≥ 5000 are accepted from clients

- **File/line:** `src/calibre/srv/web_socket.py:418`
- **What goes wrong:** Validation rejects `< 1000`, 1004-1006 and 1012-2999, but accepts 5000-65535. The server echoes those codes back instead of failing with 1002.
- **Why it is wrong:** RFC 6455 §7.4.2 defines status codes only up to 4999. The code already rejects other undefined ranges, which shows the intent is to reject invalid codes (the Autobahn suite this file is tested against, per line 553, checks 5000/65535 as invalid).
- **Severity:** low
- **Fix:** Add `or close_code >= 5000` to the condition.

## 13. `GeneratedOutput` responses crash in `finalize_output` (verified; latent)

- **File/line:** `src/calibre/srv/http_response.py:751-755`
- **What goes wrong:** For any handler return value that falls through to `GeneratedOutput` (an iterator/generator), `content_length` is None. When the Content-Type is empty or `text/*`, evaluation reaches `output.content_length >= opts.compress_min_size`, which raises `TypeError: '>=' not supported between NoneType and int`. That becomes a 500, whatever `Accept-Encoding` says. Reproduced with `iter([b'a'])`.
- **Why it is wrong:** `GeneratedOutput` / `write_iter` (chunked streaming) exist precisely to support generator outputs of unknown length. No current endpoint in `srv/` returns a generator, so this is latent, but the code path is broken as written.
- **Severity:** low
- **Fix:** `output.content_length is not None and output.content_length >= opts.compress_min_size`. Or treat unknown length as compressible.

---

## Files read

- `src/calibre/srv/http_request.py` (full)
- `src/calibre/srv/http_response.py` (full)
- `src/calibre/srv/utils.py` (full)
- `src/calibre/srv/web_socket.py` (full)
- `src/calibre/srv/auth.py` (full)
- `src/calibre/srv/errors.py` (lines 1-40)
- `src/calibre/srv/loop.py` (ReadBuffer, Connection, and ServerLoop.tick / dispatch sections, ~lines 60-340 and 580-720)
- `src/calibre/srv/routes.py` (lines 280-405)
- `src/calibre/srv/content.py` (lines 1-480)
- `src/calibre/srv/opts.py` (option defaults around compress_min_size / max_opds_items)
- `src/calibre/srv/opds.py` (Offsets call sites, ~525-560, 740-790)
- `src/calibre/srv/tests/http.py` (grep only, to check existing test coverage)
