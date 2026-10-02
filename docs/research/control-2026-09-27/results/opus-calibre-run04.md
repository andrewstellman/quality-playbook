# Code review: calibre `src/calibre/srv/` (pinned 7691f4f1a155d799afdfec99e2cdc2716c178402)

Reviewer: opus, run04. Checkout at `/tmp/control/calibre` (read-only). Suspicions marked "verified" were checked by running the extracted code under Python 3.10 in the work directory.

---

## 1. Negative (and non-canonical) chunk sizes bypass `max_request_body_size`

- **File/line:** `src/calibre/srv/http_request.py:426-442` (`read_chunk_length` / `read_chunk`)
- **What goes wrong:** `chunk_size = int(line.strip(), 16)` accepts a sign, a `0x` prefix and underscores. For example, `int(b'-5',16) == -5`, `int(b'0x10',16) == 16` and `int(b'1_0',16) == 16` (verified). With a negative size such as `-FFFFFF`:
  - the size check `bytes_read[0] + chunk_size + 2 > max_request_body_size` passes;
  - `read_chunk` gets `end = buf.tell() + chunk_size`, which is below the current position, so `read()` returns True immediately;
  - `bytes_read[0] += chunk_size` then *subtracts* from the running total.

  A client can alternate negative chunks with large positive chunks and stream an unbounded body into the `SpooledTemporaryFile` on disk. That defeats the only request-size limit.
- **Why it's wrong:** RFC 7230 §4.1 defines `chunk-size = 1*HEXDIG`, with no sign, prefix or separators. The code's own intent is to cap chunked bodies (`'Chunked request is larger than ... bytes'`).
- **Severity:** high (unauthenticated resource exhaustion; the body is read before routing or auth).
- **Fix:** validate the size token strictly before converting, e.g. `tok = line.strip(); if not tok or not re.fullmatch(rb'[0-9A-Fa-f]+', tok.split(b';',1)[0].strip()): 400`. Parse only the part before `;` so that chunk extensions are ignored as the RFC requires.

## 2. `finalize_output` is passed `self.method is HTTP1` (always False), so HTTP/1.0 clients get chunked/gzip/range responses

- **File/line:** `src/calibre/srv/http_response.py:561`
- **What goes wrong:** `self.finalize_output(output, data, self.method is HTTP1)` compares the request *method* (`'GET'`, `'POST'`, …) with the string `'HTTP/1.0'`, so `is_http1` is never true.
  - The `and not is_http1` guards on `compressible` (line 757) and `accept_ranges` (line 759) are dead code.
  - An HTTP/1.0 client that sends `Accept-Encoding: gzip` for a text/JSON resource of at least `compress_min_size` bytes gets `Transfer-Encoding: chunked` (line 794) with chunked framing.
  - HTTP/1.0 cannot decode chunked framing, so the client sees a corrupt body.
- **Why it's wrong:** the parameter name and its uses show that the protocol version was intended. RFC 7230 §3.3.1 says a server MUST NOT send a Transfer-Encoding to an HTTP/1.0 client.
- **Severity:** medium.
- **Fix:** `self.finalize_output(output, data, self.response_protocol is HTTP1)`.

## 3. Obs-folded header values keep the embedded CRLF

- **File/line:** `src/calibre/srv/http_request.py:186` and `:213`
- **What goes wrong:** each stored line still ends in `\r\n`, and continuation lines are joined with `b' '.join(self.lines)`. `X-A: one\r\n` followed by `  two\r\n` therefore produces the value `'one\r\n two'` (verified). Raw CR/LF then flows into:
  - header consumers such as `Authorization`, `Content-Type` and `X-Forwarded-For`;
  - the access log (`forwarded_for` is written verbatim at `http_response.py:605-607`), which allows log-line injection;
  - the TRACE echo.
- **Why it's wrong:** RFC 7230 §3.2.4 says a recipient MUST replace each obs-fold with one or more SP before interpreting or forwarding the value.
- **Severity:** medium (log injection and malformed header values).
- **Fix:** strip the line terminator before storing each line (`self.lines.append(line.rstrip(b'\r\n'))`, and likewise for continuation lines), or reject obs-fold with 400.

## 4. Header lines without a colon, or with whitespace before the colon, are accepted

- **File/line:** `src/calibre/srv/http_request.py:189-193`
- **What goes wrong:**
  - `line.partition(b':')` on `NoColonHere\r\n` yields the header `Nocolonhere` with an empty value instead of an error.
  - `k.strip()` silently accepts `Content-Length : 5` as `Content-Length` (both verified).
- **Why it's wrong:** RFC 7230 §3.2.4 says a server MUST reject a request with whitespace between the field-name and the colon with 400, because proxies disagree on how to treat such lines (request smuggling). The class docstring says malformed headers raise `ValueError`.
- **Severity:** low/medium.
- **Fix:** raise `ValueError` if there is no `:`, or if the name contains whitespace or is otherwise not a token (`k != k.strip()`).

## 5. Stale-but-valid digest nonce is counted as a failed login and can get a legitimate user banned

- **File/line:** `src/calibre/srv/auth.py:297-303`
- **What goes wrong:** when the credentials validate but `is_nonce_stale()` is True, execution falls through to `log_msg = 'Failed login attempt ...'` and `self.ban_list.failed(ban_key)`. The server then correctly sends `stale="true"`, and the browser retries silently. Each such retry, however, is recorded as a failure.
  - Typical case: several tabs or requests after more than an hour idle.
  - With banning enabled, a correctly authenticated user reaches `max_failures_before_ban` and gets `403 Too many login attempts`.
- **Why it's wrong:** per RFC 2617 §3.2.1, `stale=TRUE` means the digest was valid and only the nonce expired. It is not an authentication failure, and the code already distinguishes the case with `nonce_is_stale`.
- **Severity:** medium.
- **Fix:** only set `log_msg` and call `ban_list.failed()` when validation actually failed, e.g. `if not nonce_is_stale: log_msg = ...; self.ban_list.failed(ban_key)`.

## 6. `BanList.failed` never prunes expired entries (iterates newest-first)

- **File/line:** `src/calibre/srv/auth.py:53-58`
- **What goes wrong:**
  - `self.items` is an `OrderedDict` with the newest entry appended last (pop + reinsert).
  - `for old in reversed(self.items)` starts at the newest entry, which is the key just inserted with `now`. That entry is never older than `interval`, so the loop breaks on its first iteration and nothing is removed.
  - Result: one entry per distinct failing IP is kept forever, an unbounded-memory problem on an internet-facing server. Verified: after an interval elapsed, `failed('c')` left `['a','b','c']` in place.
- **Why it's wrong:** the loop is clearly meant to drop entries whose last failure is older than `interval`, stopping at the first fresh one. That only works when iterating oldest-first.
- **Severity:** low/medium.
- **Fix:** iterate `for old in self.items:` (oldest first) and break on the first non-expired entry.

## 7. Malformed `Range` header produces 500 instead of being ignored

- **File/line:** `src/calibre/srv/http_response.py:137-138`
- **What goes wrong:** `start, stop = (x.strip() for x in brange.split('-', 1))` raises `ValueError` when a range spec has no `-`. Examples are `Range: bytes=5`, `bytes=` and `bytes=0-1,,2-3` (verified). The exception is outside every `try` in `get_ranges`, so it propagates out of `finalize_output` to the loop's unhandled-exception path and returns 500. It also logs a traceback for every such request.
- **Why it's wrong:** the docstring says an empty list means no valid range, and other malformed pieces are skipped with `continue`. RFC 7233 §3.1 says a server MAY ignore a Range header it can't parse; that is not a server error.
- **Severity:** low.
- **Fix:** `if '-' not in brange: continue` (or wrap the unpack in the existing try/continue).

## 8. Zero-length suffix range / zero-length resource yields a bogus 206

- **File/line:** `src/calibre/srv/http_response.py:152-161`
- **What goes wrong:**
  - `Range: bytes=-0` yields `Range(start=content_length, stop=content_length-1, size=0)`.
  - For an empty file, `bytes=-5` yields `Range(0, -1, 0)` (both verified).
  - The server then sends `206` with `Content-Range: bytes 100-99/100` (an invalid range) and `Content-Length: 0`.
- **Why it's wrong:** RFC 7233 §2.1: a suffix-byte-range-spec with a suffix-length of zero is unsatisfiable, and the server should respond 416. The same applies when the representation is empty.
- **Severity:** low.
- **Fix:** in the suffix branch, `continue` when `stop == 0` or `content_length == 0`.

## 9. `q=0` is treated as acceptable in content negotiation

- **File/line:** `src/calibre/srv/utils.py:232-248` (`sort_q_values`), used by `http_response.py:101-105` (`acceptable_encoding`) and `111-117` (`preferred_lang`)
- **What goes wrong:** items with `q=0` are still returned, only sorted last. `Accept-Encoding: gzip;q=0` therefore returns `'gzip'` from `acceptable_encoding`, and the server sends gzip to a client that explicitly refused it.
- **Why it's wrong:** RFC 7231 §5.3.1: a weight of 0 means "not acceptable".
- **Severity:** low.
- **Fix:** drop items with `q == 0` in `sort_q_values` (or in the two callers).

## 10. `Accept-Ranges: bytes` advertised for outputs that never honour ranges

- **File/line:** `src/calibre/srv/http_response.py:759`
- **What goes wrong:** `output.accept_ranges is not None` is always true, because `accept_ranges` is a bool (`True`/`False`) on both `ReadableOutput` and `GeneratedOutput`. Dynamic string/bytes responses (`dynamic_output` sets `accept_ranges = False`) and generated outputs therefore still send `Accept-Ranges: bytes`. Line 760 then ignores any `Range` request against them.
- **Why it's wrong:** the header tells clients that range requests are supported for this resource, but the code explicitly marks these outputs as not supporting ranges.
- **Severity:** low.
- **Fix:** `accept_ranges = not compressible and output.accept_ranges and ...`.

## 11. HTTP/1.0 requests ignore `Transfer-Encoding` entirely while keeping the connection alive

- **File/line:** `src/calibre/srv/http_request.py:373-381`
- **What goes wrong:** `Transfer-Encoding` is examined only when `response_protocol is HTTP11`. Suppose an HTTP/1.0 request carries `Connection: keep-alive` and `Transfer-Encoding: chunked`:
  - the chunked body is not consumed and is parsed as the next request on the same connection;
  - if `Content-Length` is also present, the TE/CL conflict check is skipped.

  This is a classic request-smuggling desync when calibre sits behind a proxy.
- **Why it's wrong:** RFC 9112 §6.1 says a server receiving an HTTP/1.0 message with Transfer-Encoding MUST treat the framing as faulty and close the connection after processing the message.
- **Severity:** low/medium.
- **Fix:** if `Transfer-Encoding` is present on an HTTP/1.0 request, either respond 400 or set `close_after_response = True` and ignore the body.

## 12. `GeneratedOutput` responses crash in the compression check

- **File/line:** `src/calibre/srv/http_response.py:748-755`
- **What goes wrong:** for any handler return value that falls into the generic `else: output = GeneratedOutput(output)` branch (an iterable of chunks), `content_length` is `None`. If the content type is compressible (including an empty Content-Type) and `compress_min_size > -1` (the default), `output.content_length >= opts.compress_min_size` raises `TypeError` on Python 3, producing a 500. The chunked-streaming path at line 793 (`output.content_length is None`) is then unreachable for those responses.
- **Why it's wrong:** `finalize_output` explicitly supports generated output and chunked streaming, and `GeneratedOutput.content_length = None` is by design.
- **Severity:** low. I found no current in-tree endpoint that returns a bare iterable, so this is a latent defect in the documented output path.
- **Fix:** `(opts.compress_min_size > -1 and output.content_length is not None and output.content_length >= opts.compress_min_size)`, or treat `None` as "large enough".

---

## Checked and not reported

These were checked and appear correct or intentional:

- `ReadBuffer` ring-buffer logic
- multipart byterange `Content-Length` arithmetic
- WebSocket frame-header parsing and close-code validation
- `Router.find_route` / `Route.matches`
- `path_from_root` usage in `/static` and `/icon`
- digest `request_digest` computation
- `Offsets`
- nonce synthesis and validation

## Files read

- `src/calibre/srv/http_request.py` (full)
- `src/calibre/srv/http_response.py` (full)
- `src/calibre/srv/web_socket.py` (full)
- `src/calibre/srv/auth.py` (full)
- `src/calibre/srv/utils.py` (full)
- `src/calibre/srv/routes.py` (full)
- `src/calibre/srv/loop.py` (lines 1-370 and grep for exception handling)
- `src/calibre/srv/content.py` (lines 265-370)
- `src/calibre/srv/code.py` (selected: 385-400, 660-685)
- `src/calibre/srv/opds.py` (lines 520-615, 640-790)
- `src/calibre/srv/ajax.py` (lines 25-40, grep)
- `src/calibre/srv/opts.py` (grep)
- `src/calibre/srv/tests/http.py` (lines 360-470, grep)
- `src/calibre/db/categories.py` (lines 18-80, for context)
