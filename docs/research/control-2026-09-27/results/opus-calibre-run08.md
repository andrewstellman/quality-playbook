# Code review: calibre `src/calibre/srv/` (pinned 7691f4f1a155d799afdfec99e2cdc2716c178402)

Reviewer run: opus-calibre-run08. Checkout: `/tmp/control/calibre` (read-only). Paths below are relative to `src/calibre/srv/`.

Method: I read the HTTP stack (http_request, http_response, loop, utils, routes, handler, auth, web_socket), the main content endpoints, and user/library management by hand. I also checked suspicious functions in isolation with Python 3.10 (get_ranges, BanList, int() chunk parsing). Two helper passes covered the remaining handler modules. I re-read the cited code for every finding from those passes that is listed below. Findings marked "(verified by reading only)" were not executed.

---

## High

### 1. cdb.py:226: the recipe block in `/cdb/set-fields` misses `downloaded_recipe`
- **What goes wrong:** `cdb_set_fields` rejects an added format only when `fmt.lower() in ('recipe', 'original_recipe')`. A user with write access can POST an `added_formats` entry whose `ext` is `downloaded_recipe` or `original_downloaded_recipe`, and it is stored.
- **Why it's wrong:** the same file defines `is_recipe_fmt()` (lines 68–70) to cover both `recipe` and `downloaded_recipe`, and `cdb_add_book` uses it. The error message gives the reason for the block: recipes "allow code execution". Recipe input compiles and runs the recipe's Python, so a later conversion of that format runs attacker code on the server.
- **Fix:** `if is_recipe_fmt(fmt): raise HTTPForbidden(...)`.

### 2. convert.py:46 vs 131/187: `output_fmt` is sanitised for the status path but not for the actual conversion
- **What goes wrong:** `JobStatus.__init__` strips `/` and `\` from `output_fmt`; its comment says this is "to prevent path traversal". But `queue_job` passes the raw `conversion_data['output_fmt']` to `convert_book`, which computes `os.path.abspath('output.' + output_fmt.lower())`.
- **Input:** a write-enabled client sends `"output_fmt": "/../../../../tmp/x.epub"`. The worker writes its output to `/tmp/x.epub`.
- **Status:** the helper pass checked this by evaluating `abspath` on that input. Whether conversion goes on to finish with such a value was not run end to end.
- **Fix:** validate `output_fmt` against the known output plugin names (e.g. `^[a-z0-9_]+$`) in `start_conversion`/`queue_job`, and pass the validated value to `convert_book`.

---

## Medium

### 3. http_response.py:561: HTTP/1.0 detection compares the method, not the protocol
- **Code:** `output = self.finalize_output(output, data, self.method is HTTP1)`
- **What goes wrong:** `self.method` is `'GET'`, `'POST'`, and so on, never `HTTP1` (`'HTTP/1.0'`). So `is_http1` is always False, and the `not is_http1` guards on compression (line 757) and on Accept-Ranges and range handling (line 759) never apply.
- **Effect:** an HTTP/1.0 client that sends `Accept-Encoding: gzip` gets `Transfer-Encoding: chunked` for compressible bodies. RFC 7230 §3.3.1 says a server MUST NOT send chunked encoding to an HTTP/1.0 client, so the client reads chunk-size lines as body.
- **Fix:** `self.response_protocol is HTTP1`.

### 4. http_response.py:750–801: a Range request on a compressible body produces a malformed response
- **What goes wrong:** when `compressible` is True and `ranges` is non-empty:
  - Line 784 (`compressible and not ranges`) skips gzip, so the output stays a raw `ReadableOutput`.
  - Line 793 still sets `Transfer-Encoding: chunked` because `compressible` is true.
  - Lines 799–800 then set `Content-Length`/`Content-Range`, and `write_response_body` writes the raw bytes unchunked.
- **Input:** `GET` of any text/JS/JSON/XML/SVG file of at least 1 KB (`compress_min_size` defaults to 1024), such as a `.txt`/`.html` book, `/static/*.js` or an OPF, with both `Range: bytes=0-99` and `Accept-Encoding: gzip`. Resumed downloads send exactly this combination.
- **Effect:** the response carries both TE: chunked and Content-Length (RFC 7230 §3.3.3), and its body is not actually chunked, so the client mis-parses it.
- **Fix:** compute `compressible = compressible and not ranges`, or ignore ranges when compressing, before headers are chosen.

### 5. http_request.py:426: negative chunk sizes are accepted and bypass `max_request_body_size`
- **What goes wrong:** `int(line.strip(), 16)` accepts `-5` (it also accepts `0x10` and `1_0`). A negative size passes the limit check. `read()` returns immediately because `size <= 0`, and `read_chunk` then adds the negative value to `bytes_read[0]`.
- **Input:** a chunked POST that repeats `-FFFFFFF\r\n\r\n` drives `bytes_read` far negative. After that, arbitrarily large real chunks pass the `bytes_read + chunk_size + 2 > max_request_body_size` check (lines 429 and 452).
- **Effect:** the size limit is defeated and the spooled temp file can fill the disk. No authentication is needed, because the body is read before dispatch.
- **Fix:** require `re.fullmatch(rb'[0-9a-fA-F]+', size_token)` (after stripping any `;ext`) and reject everything else with 400.

### 6. auth.py:52–60: BanList never prunes, so failure counts never expire
- **What goes wrong:** `failed()` re-inserts the current key at the end, then walks `reversed(self.items)`, newest first, and `break`s at the first entry that is not old. That entry is always the key just inserted (`now - now == 0`), so nothing is ever removed.
- **Effects:**
  - Memory grows by one entry per distinct failing IP, without bound.
  - Old failures are never forgotten. A user who mistypes once a week is banned for `ban_for` minutes on the Nth mistake.
- **Checked by:** running it with interval 60 s and failures at t = 0, 1000 and 2000 s (max 3). The count reached 3, and one more failure at t = 10000 s banned the key immediately. No entries were pruned.
- **Fix:** iterate oldest-first (`for old in self.items:` … `break` at the first recent one), and reset the count when the previous failure is older than `interval`.

### 7. auth.py:297–303: a valid Digest response with a stale nonce is counted as a failed login
- **What goes wrong:** when the password is correct but `is_nonce_stale()` is true, the code falls through to `log_msg = 'Failed login attempt…'` and `self.ban_list.failed(ban_key)`.
- **Why it's wrong:** a stale nonce is normal protocol flow. The server answers `stale="true"` exactly so the client retries without it counting as an error (RFC 7616 §3.3). With finding 6 this adds up: a long-lived browser session collects a "failure" every `MAX_AGE_SECONDS` and is eventually banned.
- **Fix:** only call `ban_list.failed` and set `log_msg` when the digest does not validate.

### 8. content.py:632–668: data-file upload/remove endpoints aren't confined to the `data/` directory
- **What goes wrong:**
  - `upload_data_files` builds `relpath = f'{DATA_DIR_NAME}/{x["name"]}'` from client input. `remove_data_files` passes client-supplied `relpaths` through unchanged.
  - The backend only checks `path_from_root(bookdir, relpath)` (db/backend.py:2329 and 2377), which keeps paths inside the *book* directory, not inside `data/`.
- **Input:** `name = "../cover.jpg"`, or `"../<Title> - <Author>.epub"`, or `relpaths = ["metadata.opf", "cover.jpg"]`.
- **Effect:** the "data files" API overwrites or permanently deletes the book's cover, OPF or format files behind the database's back (`has_cover` and the formats table go stale).
- **Why it's wrong:** these endpoints exist for `DATA_FILE_PATTERN` files only; `get_data_file` restricts lookups to that pattern.
- **Fix:** reject names containing `/`, `\` or `..`. For remove, only accept relpaths that start with `DATA_DIR_NAME + '/'` and are listed by `list_extra_files(book_id, pattern=DATA_FILE_PATTERN)`.

### 9. books.py:116: `clean_final()` deletes the wrong path
- **What goes wrong:** `x` comes from `os.listdir(fdir)`, but the code calls `safe_remove(x)`, which is relative to the process CWD. Line 111 correctly uses `os.path.join(fdir, x, …)`.
- **Effect:** expired rendered books in `srvb/f/` are never removed, so the cache grows without bound. A same-named entry in the CWD may be deleted instead.
- **Fix:** `safe_remove(os.path.join(fdir, x), False)`.

### 10. loop.py:615–616: the SSL close loop uses a stale variable
- **Code:** `for x, conn in close_needed: self.close(s, conn)`
- **What goes wrong:** `s` is left over from the previous loop, so the wrong `connection_map` key is popped.
- **Effect:** the SSL connection that should be closed stays in the map with a closed socket, and an unrelated live connection is orphaned, so it is never selected or closed.
- **Fix:** `self.close(x, conn)`.

### 11. jobs.py:98, 204–222: `max_job_time = 0` ("no limit") aborts every job immediately
- **What goes wrong:** opts.py:81 documents "Set to zero for no limit", but `delta = 0 - elapsed <= 0` gives `max_block = 0`, and `abort_hanging_jobs` sets `abort_event` on every running job.
- **Fix:** when `max_job_time <= 0`, set `max_block = None` and skip `abort_hanging_jobs`.

### 12. embedded.py:95 and 135: the listening socket is initialised twice
- **What goes wrong:** `start()` calls `self.loop.initialize_socket()`, then calls `self.loop.serve_forever()`, which calls `initialize_socket()` again (loop.py:557). `ServerLoop.serve()` exists for exactly this split.
- **Effects:**
  - The first bound socket leaks.
  - With a pre-activated (systemd) socket, the first call consumes it. The second `do_bind()` then conflicts with it and fails.
  - A failure in the second bind lands in `self.exception` instead of the `start()` failure path.
- **Fix:** call `self.loop.serve()` at line 135.

### 13. render_book.py:902–917: `handle_quicklook_client` has the request processing outside the read loop
- **What goes wrong:** the `try`/response block is dedented out of `for line in inf`. Only the last request is answered, and only after the client closes its write side. A client that sends one request and waits deadlocks. An empty connection raises `UnboundLocalError` on `req`.
- **Fix:** indent the processing and response block into the loop.

### 14. render_book.py:289–312: `parse_smil_time` mis-parses valid clock values
- **What goes wrong:**
  - `x.endswith('s')` is tested before `endswith('ms')`, so `"500ms"` raises `ValueError` from `float('500m')`.
  - A bare timecount such as `"12.5"` (seconds by default, per the SMIL clock-value grammar that the function's own comment links) raises "Malformed SMIL time".
  - `min(abs(seconds), 59)` cuts 59.5 down to 59.
- **Effect:** the exception propagates and aborts rendering of the whole book.
- **Fix:** test `ms` (and `min`) before `s`, treat a bare number as seconds, and clamp with `< 60`.

### 15. code.py:337–352: browse searches for custom rating columns always fail (verified by reading only)
- **What goes wrong:** only `field == 'rating'` is turned into a numeric search. Custom rating columns (datatype `rating`, which are categories) produce `#col:"=★★★"`. Their search goes to the numeric matcher, which raises "Non-numeric value in query".
- **Fix:** test `fm[field]['datatype'] == 'rating'` instead of the field name.

---

## Low

### 16. http_response.py:138: a Range header with no `-` causes a 500
- **Input:** `Range: bytes=5`.
- **What goes wrong:** `start, stop = (x.strip() for x in brange.split('-', 1))` raises `ValueError` (confirmed by running it). The exception escapes `job_done` and becomes an Internal Server Error, when it should be ignored or answered with 416.
- **Fix:** wrap the unpack in the existing `try`/`continue`.

### 17. http_response.py:152–161: suffix range `bytes=-0` returns a bogus 206
- **What goes wrong:** the result is `Range(start=len, stop=len-1, size=0)`, which produces `Content-Range: bytes 100-99/100`. For an empty file with `bytes=-5` it produces `Range(0,-1,0)`. RFC 7233 §2.1 says a suffix-length of 0 is unsatisfiable.
- **Fix:** `continue` when `stop == 0` (or when `content_length == 0`).

### 18. http_response.py:759: `Accept-Ranges: bytes` is sent for outputs that don't support ranges
- **What goes wrong:** the check is `output.accept_ranges is not None`, but `accept_ranges` is a bool that is never None. Dynamic outputs set it to `False` (line 392), yet they still advertise byte ranges, while line 760 correctly refuses to honour them.
- **Fix:** `and output.accept_ranges`.

### 19. http_request.py:396–399: `X-Forwarded-For` is lost on `Expect: 100-continue` requests
- **What goes wrong:** the 100-continue branch returns before `self.forwarded_for = inheaders.get('X-Forwarded-For')`, and `connection_ready()` had reset it to None. Access-log entries for those requests (typically large uploads) lack the client address behind a proxy.
- **Fix:** set `forwarded_for` before the Expect check.

### 20. content.py:65–121 with 228–243: a plugboard change doesn't invalidate the cached download
- **What goes wrong:** the cached file name is `fmt-{library}-{book}.{ext}` and is rebuilt only when `previous_mtime < mt`. A plugboard change alters `extra_etag_data` (so the ETag changes) but not `mtime`, so the old file, with metadata from the previous plugboard, is served under a new ETag.
- **Fix:** include a hash of `extra_etag_data` in `bname`, or compare it on reuse.

### 21. users.py:29–40, 236: the lru-cached `parse_restriction` returns a shared mutable dict
- **What goes wrong:** `restrictions()` returns only a shallow `.copy()`, so `r['library_restrictions']` is the cached dict itself. `manage_users_cli.py:191–197` and `:430–432` mutate it in place.
- **Effect:** in the interactive `manage_users` loop, users whose stored restriction string is identical (e.g. the default `{"library_restrictions": {}}`) share that dict. Editing user A's per-library restrictions and then user B's shows A's entries for B and saves them for B.
- **Fix:** deep-copy in `restrictions()`/`create_user_data`, or return immutable structures from `parse_restriction`.

### 22. ajax.py:554: `num_books_without_search` ignores the user's library restriction
- **What goes wrong:** with an empty query it equals `total_num`, which respects the restriction. With a query it is `db.number_of_books_in_virtual_library(vl)`, which does not. The same field is inconsistent, and a restricted user learns the size of the unrestricted library.
- **Fix:** use `len(ctx.get_effective_book_ids(db, rd, vl))`.

### 23. code.py:374: browse items deduplicated by display name drop distinct hierarchical items
- **What goes wrong:** `seen` is keyed on `item['name']`, which for hierarchical nodes is only the last segment. `History.Military` and `Science.Military` collapse into one entry.
- **Fix:** key on `original_name or name`.

### 24. legacy.py:122: the `/mobile` pager hides the last page on the boundary
- **What goes wrong:** with start=1, num=25 and total=26, `total > start + num` is false. Books 1–25 are shown, and there is neither a Next nor a Last link to reach book 26.
- **Fix:** `if start + num <= total:`.

### 25. legacy.py:270–272: the fallback sort field `'date'` is not a sort key
- **What goes wrong:** the fallback bypasses `sanitize_sort_field_name`, which maps `date` to `timestamp`. So `/mobile?sort=<invalid>` raises again inside the `except` and returns a 500.
- **Fix:** `sort_by = 'timestamp'`.

---

## Checked, no confident defect found
- ReadBuffer (random-tested by a helper pass)
- WebSocket frame parsing and close handling
- Router matching and `url_for`
- MultiDict
- The HTTP header parser
- Content-Length parsing
- Multipart byterange size arithmetic (worked through by hand; correct)
- library_broker.py
- opds.py, metadata.py, changes.py, bonjour.py, pre_activated.py, pool.py, auto_reload.py, fts.py, last_read.py

## Files read
- **By me, in full:**
  - srv/http_request.py
  - srv/http_response.py
  - srv/utils.py
  - srv/auth.py
  - srv/web_socket.py
  - srv/routes.py
  - srv/handler.py
  - srv/content.py
  - srv/ajax.py
  - srv/library_broker.py
  - srv/users.py
  - srv/users_api.py
- **By me, in part:**
  - srv/loop.py (ReadBuffer.readline, Connection, ServerLoop socket setup, 600–620)
  - srv/errors.py
  - srv/opts.py
  - srv/code.py (1–200, 330–410)
  - srv/cdb.py (64–72, 218–232)
  - srv/books.py (105–120)
  - srv/convert.py (40–50, 110–210)
  - srv/embedded.py (88–140)
  - srv/jobs.py (96–225)
  - srv/render_book.py (286–313, 885–920)
  - srv/legacy.py (110–130, 262–276)
  - srv/manage_users_cli.py (160–215, 370–480)
  - srv/tests/http.py (grep)
  - db/backend.py (add_extra_file, remove_extra_files)
  - db/cache.py (add/remove/list_extra_files)
  - db/view.py (sanitize_sort_field_name)
- **By helper passes:**
  - srv/code.py, books.py, cdb.py, legacy.py, legacy_book_details.py, fts.py, last_read.py
  - srv/opds.py, metadata.py, render_book.py, convert.py, jobs.py, pool.py, changes.py, standalone.py, auto_reload.py, embedded.py, bonjour.py, pre_activated.py, loop.py
  - For context: db/search.py, db/fields.py, db/categories.py, ebooks/conversion/plumber.py, ebooks/conversion/config.py, ebooks/conversion/plugins/recipe_input.py, utils/ipc/simple_worker.py, pyj/book_list/search.pyj, pyj/book_list/nav_list.pyj
