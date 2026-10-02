# Code review: calibre `src/calibre/srv/` (commit 7691f4f1a155d799afdfec99e2cdc2716c178402)

Reviewer: opus, run03. The checkout at `/tmp/control/calibre` was reviewed read-only. I checked the findings marked "verified" by running the extracted functions under Python 3.10.

---

## 1. SSL connections closed through `close_needed` use the wrong map key: live connections get dropped and leak
- **File/line:** `src/calibre/srv/loop.py:615-616`
  ```python
  for x, conn in close_needed:
      self.close(s, conn)
  ```
- **What goes wrong:** The loop variable is `x`, but the call passes `s`. At this point `s` is a leftover from the earlier `for s, conn in self.connection_map.items()` loop (or from the `remove` loop), so it is the key of some *other* connection. `ServerLoop.close()` (line 705) runs `self.connection_map.pop(s, None)` and then `conn.close()`. As a result:
  - An unrelated live connection is removed from `connection_map` without being closed. Its socket leaks and its client hangs.
  - The connection that is actually dead stays in `connection_map` with a closed socket. On the next tick `drain_ssl_buffer()` fails on it again, it lands in `close_needed` again, and another innocent connection is evicted. This repeats every tick.
- **Trigger:** An SSL-enabled server (`has_ssl`) where `drain_ssl_buffer()` sets `ready = False`. That happens on an `ssl.SSLError` from the client or on ECONNRESET/EPIPE and similar errors. A client that aborts a TLS connection is enough.
- **Why it is wrong:** The intent is to close the connection that was collected in `close_needed`, keyed by its own fd (`close_needed.append((s, conn))` at line 605).
- **Severity:** high
- **Fix:** `for x, conn in close_needed: self.close(x, conn)`

## 2. `extra_books` in the web UI init endpoints bypasses per-user library restrictions
- **File/line:** `src/calibre/srv/code.py:456-464`. This is reached from `/interface-data/books-init` (line 469) and `/interface-data/init` (line 488).
- **What goes wrong:** `get_library_init_data()` parses arbitrary integers from `?extra_books=` and calls `book_as_json(db, book_id)` for each one. It never checks `ctx.has_id(rd, db, book_id)` or `ctx.allowed_book_ids()`. `book_as_json` (`metadata.py:72`) only checks `db.has_id`. A user whose account has a library restriction (`restriction_for`) can therefore read full metadata (title, authors, identifiers, formats, notes links, etc.) of *any* book by requesting `/interface-data/books-init?extra_books=1,2,3,...`.
- **Why it is wrong:** Every other endpoint that returns per-book data enforces the restriction. Examples: `ajax.py:218-222` (`if book_id not in allowed_book_ids: ans[book_id] = None`), `code.py:630` (`book_metadata` → `ctx.has_id`), `content.py:405`, `books.py:156/194/221`. The search result in this same function is already restricted through `ctx.search`, and only the extra IDs escape the check.
- **Severity:** high (authorization bypass / information disclosure for restricted users)
- **Fix:** Intersect with the allowed IDs, for example `allowed = ctx.allowed_book_ids(rd, db)` and `extra_books = {b for b in extra_books if b in allowed}`. Alternatively, call `ctx.has_id(rd, db, book_id)` before `book_as_json` for the extra IDs.

## 3. `is_http1` is always False: HTTP/1.0 clients get chunked/gzip responses
- **File/line:** `src/calibre/srv/http_response.py:561`
  ```python
  output = self.finalize_output(output, data, self.method is HTTP1)
  ```
- **What goes wrong:** `self.method` is the request method (`'GET'`, `'POST'`, …) and `HTTP1` is the string `'HTTP/1.0'`, so the expression is always `False`. `finalize_output` uses `is_http1` to disable compression (line 757, `and not is_http1`) and range advertising (line 759). For an HTTP/1.0 request that sends `Accept-Encoding: gzip` (e.g. `curl --http1.0 --compressed`), the response for any compressible body ≥ `compress_min_size` is sent with `Transfer-Encoding: chunked` (line 793-794). HTTP/1.0 does not support chunked transfer coding, so the client receives chunk-size lines mixed into the body.
- **Why it is wrong:** The parameter is clearly meant to reflect the negotiated protocol. `self.response_protocol` is set to `HTTP1` or `HTTP11` in `http_request.py:326`, and `simple_response` already checks `self.response_protocol is HTTP1` (line 460).
- **Severity:** medium
- **Fix:** Pass `self.response_protocol is HTTP1`. The HTTP/1.0 path should also avoid `Transfer-Encoding: chunked` for `GeneratedOutput` (fall back to close-delimited bodies).

## 4. `BanList.failed()` never evicts expired entries, so failure counts never expire
- **File/line:** `src/calibre/srv/auth.py:52-58`
  ```python
  for old in reversed(self.items):
      previous_fail = self.items[old][0]
      if now - previous_fail > self.interval:
          remove.append(old)
      else:
          break
  ```
- **What goes wrong:** Each failed key is popped and re-inserted at the *end* of the `OrderedDict` (lines 48-51), so the newest entry is last. `reversed()` starts from the entry just inserted with timestamp `now`, so the first comparison is always `0 > interval` → `break`. Nothing is ever removed. Consequences:
  - The dict grows without bound, one entry per client IP that ever failed a login.
  - Failure counts never reset. A user who mistypes a password once a week gets banned for `ban_for` minutes on the `ban_after`-th mistake, however far apart the mistakes were. After any ban expires, a single further failure re-bans immediately because the count is still ≥ `max_failures_before_ban`.
- **Verified:** With `ban_time=0.1s` and `max=2`, I called `failed('a')`, slept 0.2s, then called `failed('b')`. The items were still `['a','b']`. `failed('a')` then produced `is_banned('a') == True`.
- **Why it is wrong:** The loop exists to prune entries older than `interval`, and the `break` assumes iteration from oldest to newest.
- **Severity:** medium
- **Fix:** Iterate forwards (`for old in self.items:`). Also reset the key's own count when its previous failure is older than `interval`, before incrementing: `fail_count = 0 if x is None or now - x[0] > self.interval else x[1]`.

## 5. Render cache cleanup deletes the wrong path, so `srvb/f` grows forever
- **File/line:** `src/calibre/srv/books.py:116`
  ```python
  for x in os.listdir(fdir):
      tm = os.path.getmtime(os.path.join(fdir, x, 'calibre-book-manifest.json'))
      ...
      safe_remove(x)
  ```
- **What goes wrong:** `x` is a bare directory name (the book hash). `safe_remove(x)` resolves it relative to the process CWD, not to `fdir`. Stale rendered books are never deleted from `cache_dir()/srvb/f`. The call would also `rmtree` any same-named directory in the CWD.
- **Why it is wrong:** The comment says "This book has not been accessed for a long time, delete it". The mtime check two lines above correctly uses `os.path.join(fdir, x, ...)`.
- **Severity:** medium (unbounded disk usage on long-running servers)
- **Fix:** `safe_remove(os.path.join(fdir, x), False)`

## 6. `Accept-Encoding` / `Accept-Language` q-values: `q=0` is treated as acceptable, and `; q=` with a space is ignored
- **File/line:** `src/calibre/srv/utils.py:237-248` (`sort_q_values`), used by `http_response.py:101-105` (`acceptable_encoding`) and `111-117` (`preferred_lang`).
- **What goes wrong:**
  - Items with `q=0` are returned (just sorted last), so `acceptable_encoding('gzip;q=0')` returns `'gzip'`. The server then gzip-encodes a response the client explicitly refused. `preferred_lang` likewise picks a language marked `q=0`.
  - `r.partition('=')` is not stripped, so for `"fr; q=0.5"` the parameter name is `' q'` and q stays 1.0. Verified: `sort_q_values('en;q=0.1, fr; q=0.5, de;q=0.9')` → `('fr','de','en')`.
- **Why it is wrong:** RFC 7231 §5.3.1 says `q=0` means "not acceptable", and the weight grammar is `OWS ";" OWS "q=" qvalue`, so whitespace is allowed.
- **Severity:** low-medium
- **Fix:** Strip `p` (`p.strip().lower() == 'q'`) and drop entries whose q is 0.

## 7. `get_ranges` mishandles malformed or zero-length suffix ranges
- **File/line:** `src/calibre/srv/http_response.py:138` and `152-161`
- **What goes wrong:**
  - `start, stop = (x.strip() for x in brange.split('-', 1))` raises `ValueError` when a range spec has no `-` (e.g. `Range: bytes=5`). The exception propagates from `job_done` and becomes a 500 Internal Server Error.
  - `bytes=-0` yields `Range(start=cl, stop=cl-1, size=0)`, and any suffix range on an empty resource yields `Range(0, -1, 0)`. The server then sends 206 with `Content-Range: bytes 100-99/100` and a 0-length body. It should send 416.
- **Verified:** I got exactly those results.
- **Why it is wrong:** The docstring says an empty list means no valid range. RFC 7233 §2.1 says a zero suffix-length is unsatisfiable, and §3.1 says an invalid Range header should be ignored rather than causing a server error.
- **Severity:** low
- **Fix:** Wrap the unpack in the `try` and `continue` on failure. In the suffix branch, skip `stop == 0` or `content_length == 0`.

## 8. `Accept-Ranges: bytes` is advertised for outputs that don't support ranges
- **File/line:** `src/calibre/srv/http_response.py:759`
- **What goes wrong:** The check is `output.accept_ranges is not None`, but `accept_ranges` is always a bool (`True`/`False`, set in `ReadableOutput`/`dynamic_output`/`GeneratedOutput`), so the condition is always true. Dynamic responses, which set `accept_ranges = False` and whose ranges are never honoured (line 760), still get `Accept-Ranges: bytes`. Clients may then issue range requests and get full 200 bodies back.
- **Severity:** low
- **Fix:** Use `output.accept_ranges` (truthiness) instead of `is not None`.

## 9. The `Expect: 100-continue` path drops `X-Forwarded-For`
- **File/line:** `src/calibre/srv/http_request.py:396-399`
- **What goes wrong:** `self.forwarded_for` is assigned only after the `return self.set_state(... write_continue ...)`. Requests that send `Expect: 100-continue` (typical for large uploads through a reverse proxy) are therefore logged without the forwarded client address. `write_continue` → `read_request_body` never sets it.
- **Severity:** low (only affects access logging)
- **Fix:** Move `self.forwarded_for = inheaders.get('X-Forwarded-For')` above the `Expect` check.

## 10. Chunked request bodies with chunk extensions or trailers are rejected
- **File/line:** `src/calibre/srv/http_request.py:426` and `449-450`
- **What goes wrong:** `int(line.strip(), 16)` fails on a chunk-size line such as `5;name=value`, which returns 400. After the last chunk, any trailer field is rejected because `read_chunk_separator` requires exactly `\r\n`.
- **Why it is wrong:** RFC 7230 §4.1.1 says a recipient MUST ignore unrecognized chunk extensions, and §4.1.2 allows a trailer section.
- **Severity:** low
- **Fix:** Parse `line.split(b';', 1)[0].strip()`. For the last chunk, read and discard header lines until the empty line.

## 11. WebSocket CLOSE frames with codes ≥ 5000 are accepted
- **File/line:** `src/calibre/srv/web_socket.py:418`
- **What goes wrong:** The validity check rejects `< 1000`, 1004-1006 and 1012-2999, but accepts any code ≥ 5000 (up to 65535) and echoes it back as a normal close.
- **Why it is wrong:** RFC 6455 §7.4.2 defines only 1000-4999, so codes above 4999 are invalid and should be answered with 1002 (protocol error). The file's own comment at line 553 says it targets the Autobahn suite, which tests codes 5000 and 65535 as invalid.
- **Severity:** low
- **Fix:** Add `or close_code >= 5000` to the condition.

---

## Files read
- `src/calibre/srv/http_request.py` (full)
- `src/calibre/srv/http_response.py` (full)
- `src/calibre/srv/loop.py` (full)
- `src/calibre/srv/web_socket.py` (full)
- `src/calibre/srv/auth.py` (full)
- `src/calibre/srv/utils.py` (full)
- `src/calibre/srv/routes.py` (full)
- `src/calibre/srv/errors.py` (partial)
- `src/calibre/srv/handler.py` (full)
- `src/calibre/srv/content.py` (full)
- `src/calibre/srv/books.py` (full)
- `src/calibre/srv/code.py` (lines 190-245, 380-739, plus grep of the rest)
- `src/calibre/srv/ajax.py` (lines 130-245)
- `src/calibre/srv/fts.py` (lines 1-76)
- `src/calibre/srv/legacy.py` (lines 280-354)
- `src/calibre/srv/pool.py`, `src/calibre/srv/last_read.py` (full)
- `src/calibre/srv/users.py` (lines 60-278)
- `src/calibre/srv/opts.py` (lines 20-120)
- `src/calibre/srv/metadata.py` (`book_as_json`, lines 72-105)
- Context outside scope: `src/calibre/utils/filenames.py` (`path_from_root`), `src/calibre/db/cache.py` (`remove_extra_files`), plus greps across `srv/` and `srv/tests/`.
