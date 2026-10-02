# Code review: calibre `src/calibre/srv/` (pinned 7691f4f1a155d799afdfec99e2cdc2716c178402)

Reviewer: opus, run07. Checkout: `/tmp/control/calibre` (read-only). I checked suspicions by running snippets of the extracted pure functions under Python 3.10 (see "Verified" notes). The package as a whole can't be imported in this environment, so I didn't run the full test suite.

---

## 1. `self.method is HTTP1` is always False, so the HTTP/1.0 guards in `finalize_output` never fire

- **File/line:** `src/calibre/srv/http_response.py:561`
- **What goes wrong:** `job_done` calls `self.finalize_output(output, data, self.method is HTTP1)`. `self.method` is the request method (`'GET'`, `'POST'`, ...), and `HTTP1` is the string `'HTTP/1.0'`, so the argument is always `False`. `finalize_output` uses `is_http1` (lines 757 and 759) to turn off gzip compression and `Accept-Ranges` for HTTP/1.0 clients. Because the argument is always `False`, an HTTP/1.0 client that sends `Accept-Encoding: gzip` for a compressible resource (≥ `compress_min_size`, default 1024 bytes) gets a gzip body sent with `Transfer-Encoding: chunked` (line 794). HTTP/1.0 has no chunked encoding, so the client cannot frame the body correctly.
- **Why it is wrong:** The `not is_http1` guards exist only to protect HTTP/1.0 peers, and the value that tells you the peer's version is `self.response_protocol` (set at `http_request.py:326`). Elsewhere the code does compare it correctly: `simple_response` at `http_response.py:460` uses `if self.response_protocol is HTTP1`.
- **Severity:** medium
- **Fix:** `output = self.finalize_output(output, data, self.response_protocol is HTTP1)`.

## 2. A range request for a compressible resource says `Transfer-Encoding: chunked` but sends an unchunked body

- **File/line:** `src/calibre/srv/http_response.py:784-808` (specifically 793-794)
- **What goes wrong:** Take a request with `Accept-Encoding: gzip` and `Range: bytes=0-99` for any compressible `ReadableOutput`, for example a `text/css`/`text/html`/JS static file or book file ≥ 1024 bytes. That request produces `compressible=True` and a non-empty `ranges`. Gzip is skipped (`if compressible and not ranges`). Line 793 (`if compressible or output.content_length is None`) still sets `Transfer-Encoding: chunked`, and line 799 also sets `Content-Length`. `write_response_body` then writes the raw byte range with `write_buf`/`write_ranges` (lines 642-648) and no chunk framing. The client tries to parse the raw bytes as chunk-size lines, so the response is corrupted and the keep-alive connection is out of sync. The same thing happens for multi-range (`multipart/byteranges`) responses.
- **Why it is wrong:** The code clearly means ranges to take priority over compression (`compressible and not ranges`), but the Transfer-Encoding decision ignores that. RFC 9112 §6.3 also says a sender must not send `Content-Length` together with `Transfer-Encoding`. The existing range tests (`tests/http.py:437-470`) use Python's `http.client`, which sends `Accept-Encoding: identity`, so they don't cover this path.
- **Severity:** medium
- **Fix:** Settle compression before building the headers, e.g. `if ranges: compressible = False` right after ranges are computed. Or change line 793 to `if (compressible and not ranges) or output.content_length is None:`.

## 3. `ServerLoop.tick` closes connections using the wrong loop variable

- **File/line:** `src/calibre/srv/loop.py:615-616`
- **What goes wrong:**
  ```python
  for x, conn in close_needed:
      self.close(s, conn)
  ```
  The loop variable is `x`, but the code passes `s`, which is left over from the earlier `for s, conn in self.connection_map.items()` loop and holds the last fd iterated. `close()` does `self.connection_map.pop(s, None)` and then `conn.close()`. As a result:
  - the connection that really failed gets its socket closed but stays in `connection_map` under its old fd;
  - a different, healthy connection (the last one iterated) is removed from `connection_map` without being closed. Its socket leaks and the client hangs.
  
  This path runs whenever SSL is enabled and `drain_ssl_buffer()` sets `ready=False` (SSL error or client EOF while waiting to read).
- **Why it is wrong:** `close(s, conn)` requires `s` to be the fd key of `conn`. Every other call site passes the matching pair.
- **Severity:** medium (SSL deployments only; leaks sockets and drops healthy connections)
- **Fix:** `for x, conn in close_needed: self.close(x, conn)`.

## 4. `BanList` never prunes, and a single failure after a ban expires bans the IP again

- **File/line:** `src/calibre/srv/auth.py:44-60`
- **What goes wrong:** `failed()` pops `key` and re-inserts it at the end of the `OrderedDict`. It then prunes by iterating `reversed(self.items)`, i.e. newest first. The first item it sees is always the entry it just inserted, with timestamp `now`, so the loop breaks immediately and nothing is ever pruned. Also, the fail count for `key` carries over (`fail_count = x[1]`) no matter how old the previous failure is. So once an IP has reached `max_failures_before_ban`, the count stays at or above the threshold forever. After the ban expires, the next single failed login (a typo, even days later) bans the IP again for the full interval. The dict also grows by one entry per distinct failing address and is never cleaned up.
- **Verified:** Extracted `BanList` with a fake clock and `max_failures_before_ban=3`, 1 minute ban. After 3 failures the IP is banned. 120 s later it is not banned. One more failure makes it banned again. Entries `a`, `x`, `y` all remain after 1000 s.
- **Why it is wrong:** The pruning loop exists to expire entries older than `interval`. Iterating newest-first defeats it. The ban is documented as time-limited (`ban_time_in_minutes`) and should require `max_failures_before_ban` fresh failures to trigger again.
- **Severity:** medium (legitimate users get re-banned; memory grows without bound)
- **Fix:** In `failed()`, reset the count when `now - x[0] > self.interval`, and prune oldest-first: `for old in self.items: if now - self.items[old][0] > self.interval: remove.append(old) else: break`.

## 5. A stale digest nonce with correct credentials is counted as a failed login

- **File/line:** `src/calibre/srv/auth.py:297-303`
- **What goes wrong:** When the digest response is valid but the nonce is older than `max_age_seconds`, `nonce_is_stale` becomes True and the function doesn't return. Execution then falls through to `log_msg = 'Failed login attempt ...'` and `self.ban_list.failed(ban_key)`. Correctly authenticated clients therefore rack up "failed attempts" every time their nonce expires (hourly by default). Several tabs/clients behind one IP, or any client over a long session, can hit `ban_after` and get the IP banned with a 403 `Too many login attempts`. Combined with finding 4, these failures never expire.
- **Why it is wrong:** RFC 2617 §3.2.1: `stale=TRUE` means the request was rejected because the nonce value was stale, but the digest was valid, so the client should simply retry with the new nonce. The code itself sends `stale="true"` (line 323–324) for exactly this case, so it is not a credential failure.
- **Severity:** medium
- **Fix:** Only log and call `ban_list.failed()` when the credentials were actually wrong, e.g. `if not nonce_is_stale: log_msg = ...; self.ban_list.failed(ban_key)`.

## 6. `simple_response` overrides the client's `Connection: close` / HTTP/1.0 non-keep-alive

- **File/line:** `src/calibre/srv/http_response.py:468` (callers at 557, 493, and `http_request.py:331`)
- **What goes wrong:** `finalize_headers` sets `self.close_after_response = True` when the client sent `Connection: close`, or when it is HTTP/1.0 without `keep-alive` (`http_request.py:365-370`). `simple_response` then unconditionally does `self.close_after_response = close_after_response`. Most error paths pass `False`: every `HTTPSimpleResponse` raised by a handler (404, 401, 400, 405, redirects, where `close_connection` defaults to False), and TRACE. So when a client sends `Connection: close` and the response is a 404 or 401, the server replies without `Connection: close` and keeps the socket open until the idle timeout.
- **Why it is wrong:** RFC 9112 §9.6: a server that receives a `close` connection option must initiate close after sending the response. The normal success path (`job_done` lines 568-576) honours `self.close_after_response`; the error path discards it.
- **Severity:** low
- **Fix:** `self.close_after_response = self.close_after_response or close_after_response` (it is reset to False in `connection_ready`, so OR-ing is safe).

## 7. A bad Request-URI produces a response but leaves the rest of that request to be parsed as a new request

- **File/line:** `src/calibre/srv/http_request.py:328-331`
- **What goes wrong:** If `parse_uri` raises (e.g. `GET /a#b HTTP/1.1`, invalid UTF-8 in the path, or an unparsable query), the code replies with `close_after_response=False` before reading the header block or body. After the response, `reset_state` → `connection_ready` starts parsing a new request line from the unread bytes, which are the rejected request's headers and body. Each header line is then treated as a request line, so a single request gets two or more responses, and bytes in the body can be executed as a pipelined request.
- **Why it is wrong:** Once the server stops parsing a message partway through, it can't find the next message boundary, so it must close the connection. Every other request-line error in the same function uses the default `close_after_response=True`.
- **Severity:** low
- **Fix:** Drop `close_after_response=False` (use the default `True`).

## 8. `get_ranges` raises on a range spec without `-`, and accepts the unsatisfiable suffix range `-0`

- **File/line:** `src/calibre/srv/http_response.py:137-161`
- **What goes wrong:**
  - `Range: bytes=5` (no hyphen): `start, stop = (x.strip() for x in brange.split('-', 1))` raises `ValueError: not enough values to unpack`. This propagates out of `finalize_output` into the loop's unhandled-exception handler and returns a 500 instead of ignoring the invalid Range header.
  - `Range: bytes=-0`: `stop='0'` is a truthy string, so the code returns `Range(start=content_length, stop=content_length-1, size=0)`. That leads to a 206 with `Content-Length: 0` and an invalid `Content-Range: bytes N-(N-1)/N` instead of a 416.
- **Verified:** Extracted `get_ranges`: `get_ranges('bytes=-0', 100)` returned `[Range(start=100, stop=99, size=0)]`, and `get_ranges('bytes=5', 100)` raised `ValueError`.
- **Why it is wrong:** The docstring says an empty list means no valid range, and invalid specs are meant to be skipped (`continue`). RFC 9110 §14.1.1/§14.1.3 says a suffix-length of 0 is unsatisfiable, and a syntactically invalid Range header must be ignored.
- **Severity:** low
- **Fix:** Skip entries without `-` (`if '-' not in brange: continue`), and in the suffix branch `if stop <= 0: continue`.

## 9. `sort_q_values` ignores `q=0` and fails on whitespace before `q`, so gzip is sent when refused

- **File/line:** `src/calibre/srv/utils.py:232-248` (used by `acceptable_encoding`, `http_response.py:101-105`, and `preferred_lang`)
- **What goes wrong:**
  - `q=0` entries are kept, so `acceptable_encoding('gzip;q=0, identity')` returns `'gzip'` and the server compresses even though the client explicitly refused gzip.
  - The parameter name isn't stripped: in `gzip; q=0.1` the part after `;` is `' q=0.1'`, so `p == ' q'` never equals `'q'` and the entry gets q=1.0. As a result `'gzip; q=0.1, br;q=0.5'` ranks gzip first.
- **Verified:** `sort_q_values('gzip;q=0, identity')` → `('identity', 'gzip')`, and `sort_q_values('gzip; q=0.1, br;q=0.5')` → `('gzip', 'br')`.
- **Why it is wrong:** RFC 9110 §12.4.2: a qvalue of 0 means "not acceptable", and optional whitespace is allowed around `;` (`weight = OWS ";" OWS "q=" qvalue`).
- **Severity:** low
- **Fix:** In `item()`, use `p.strip().lower() == 'q'`. In `sort_q_values`, filter out entries with q == 0.

## 10. Folded (obs-fold) header values keep embedded CRLF

- **File/line:** `src/calibre/srv/http_request.py:186-191, 209-213`
- **What goes wrong:** Header lines are stored with their trailing `\r\n`. For a continuation line, `commit()` joins them with `b' '.join(self.lines)` and only strips the ends of the value. `X-Foo: a\r\n b\r\n` therefore becomes the value `'a\r\n b'`. That CRLF ends up in parsed values such as `Authorization`, `Cookie`, `Range`, and in the TRACE echo.
- **Verified:** Fed `HTTPHeaderParser` the lines `b'X-Foo: a\r\n', b' b\r\n', b'\r\n'`; `hdict` was `{'X-Foo': 'a\r\n b'}`.
- **Why it is wrong:** RFC 9112 §5.2: a recipient must either reject obs-fold or replace each obs-fold with one or more SP before interpreting the value.
- **Severity:** low
- **Fix:** Strip the line terminator before appending: `self.lines.append(line.rstrip(b'\r\n'))` (and the same for continuation lines after `lstrip()`).

## 11. WebSocket: close codes ≥ 5000 accepted, and truncated close reason can be invalid UTF-8

- **File/line:** `src/calibre/srv/web_socket.py:418` and `:439`
- **What goes wrong:**
  - The validation `close_code < 1000 or close_code in RESERVED_CLOSE_CODES or (1011 < close_code < 3000)` lets through codes 5000–65535. The server echoes them back as a normal close instead of failing with 1002.
  - `websocket_close` truncates the reason to `reason[:123]` in bytes. Reasons built from handler exceptions (`f'Unexpected error in handler: {as_unicode(err)!r}'`, line 399) can contain non-ASCII text, so the cut can land inside a UTF-8 sequence. The resulting close frame has invalid UTF-8, which RFC 6455 §5.5.1/§8.1 requires the peer to treat as a protocol error.
- **Why it is wrong:** RFC 6455 §7.4.2 defines codes only up to 4999, and the server's own receive path (lines 413-416) treats a close reason with invalid UTF-8 as a protocol error.
- **Severity:** low
- **Fix:** Add `or close_code >= 5000` to the check. Truncate on a character boundary, e.g. `reason = reason[:123].decode('utf-8', 'ignore').encode('utf-8')`.

## 12. `/cdb/add-book` writes uploads to a shared, predictable temp path and never deletes them

- **File/line:** `src/calibre/srv/cdb.py` (in `cdb_add_book`: `path = os.path.join(rd.tdir, sfilename)` … `shutil.copyfileobj`)
- **What goes wrong:** `rd.tdir` is one server-wide temp directory shared by all worker threads (`loop.py:536-537`). Two concurrent uploads with the same filename (e.g. two users uploading `book.epub`) write to the same path. One request can then read the other's bytes during `run_import_plugins`/`get_metadata`/`add_books` and add the wrong book, or a half-written file. The temp file is also never removed, so every upload stays on disk until the server shuts down.
- **Why it is wrong:** Worker threads run handlers concurrently (`pool.py` `ThreadPool`, default 10 workers), and nothing serialises this endpoint.
- **Severity:** low–medium
- **Fix:** Create a unique per-request directory (e.g. `tempfile.mkdtemp(dir=rd.tdir)`), write the file there, and remove the directory in a `finally`.

## 13. `/data-files/remove` can delete any file in the book directory, not just data files

- **File/line:** `src/calibre/srv/content.py:652-673`
- **What goes wrong:** The client-supplied `relpaths` go straight to `db.remove_extra_files(book_id, relpaths, permanent=True)`. The backend (`db/backend.py:2324-2335`) only checks that each path stays inside the book directory. So `["cover.jpg"]`, `["metadata.opf"]` or `["Title - Author.epub"]` permanently deletes the cover or format file behind the database's back, and the DB still reports `has_cover` or the format.
- **Why it is wrong:** This is a data-files endpoint. Its sibling `get_data_file` only serves entries matching `DATA_FILE_PATTERN`, and `upload_data_files` forces the `DATA_DIR_NAME/` prefix. The remove endpoint doesn't apply the same restriction.
- **Severity:** low (requires write access, but causes library/DB inconsistency and permanent data loss)
- **Fix:** Reject any relpath that doesn't start with `f'{DATA_DIR_NAME}/'`, or intersect with `db.list_extra_files(book_id, pattern=DATA_FILE_PATTERN)`.

## 14. `/fts/disable` changes state on GET

- **File/line:** `src/calibre/srv/fts.py:77-82`
- **What goes wrong:** The endpoint uses the default methods (`GET`, `HEAD`) but disables full-text search for the library, which also drops the index. A prefetch, a crawler, or a cross-site `<img src=".../fts/disable">` from a logged-in user's browser (or an anonymous user on a trusted IP, `handler.py:120-124`) triggers it.
- **Why it is wrong:** RFC 9110 §9.2.1 says GET and HEAD are safe methods. The sibling state-changing endpoints `/fts/reindex` and `/fts/indexing` both restrict to `POST`.
- **Severity:** low
- **Fix:** `@endpoint('/fts/disable', needs_db_write=True, methods=('POST',))`.

---

## Files read

- `src/calibre/srv/http_request.py`
- `src/calibre/srv/http_response.py`
- `src/calibre/srv/loop.py`
- `src/calibre/srv/web_socket.py`
- `src/calibre/srv/auth.py`
- `src/calibre/srv/utils.py`
- `src/calibre/srv/routes.py`
- `src/calibre/srv/handler.py`
- `src/calibre/srv/errors.py`
- `src/calibre/srv/users.py`
- `src/calibre/srv/users_api.py`
- `src/calibre/srv/pool.py`
- `src/calibre/srv/content.py`
- `src/calibre/srv/fts.py`
- `src/calibre/srv/books.py` (lines ~180-373)
- `src/calibre/srv/cdb.py` (lines ~20-130)
- `src/calibre/srv/opds.py` (partial: header, `RequestContext`, feed endpoints ~488-790)
- `src/calibre/srv/opts.py` (grep for `compress_min_size`)
- `src/calibre/srv/tests/http.py` (grep for Range/HTTP/1.0 coverage)
- Context outside scope: `src/calibre/db/cache.py` (`add_extra_files`, `remove_extra_files`), `src/calibre/db/backend.py` (`remove_extra_files`, `add_extra_file`), `src/calibre/utils/filenames.py` (`path_from_root`), `src/calibre/db/cli/__init__.py` (`module_for_cmd`)

Not reviewed in depth: `ajax.py`, `code.py`, `legacy.py`, `legacy_book_details.py`, `metadata.py`, `render_book.py`, `convert.py`, `jobs.py`, `library_broker.py`, `last_read.py`, `auto_reload.py`, `bonjour.py`, `manage_users_cli.py`, `standalone.py`, `embedded.py`, `changes.py`, `pre_activated.py`, and the C++ files.
