# Code review: calibre `src/calibre/srv/` (pinned 7691f4f1a155d799afdfec99e2cdc2716c178402)

Reviewer: opus, run06. I worked only from the checkout at `/tmp/control/calibre`. I confirmed the pure-Python findings marked "verified" by copying the relevant functions into a scratch directory and running them under Python 3.10. I confirmed the others by tracing the code.

---

## 1. `extra_books` query parameter bypasses per-user book restrictions (information disclosure)

- **File/line:** `src/calibre/srv/code.py:456-465` (`get_library_init_data`), reached from `/interface-data/books-init` (line 469) and `/interface-data/init` (line 488)
- **What goes wrong:** Book ids in `?extra_books=1,2,3` are passed straight to `book_as_json(db, book_id)` and added to the `metadata` map in the response. Nothing checks them against the user's library restriction. A user whose account has a per-library search restriction (`library_restrictions`) can request `/interface-data/books-init?extra_books=<any id>` and get the full metadata of books the restriction is supposed to hide. `book_as_json` (`metadata.py:72-97`) only checks `db.has_id`.
- **Why it is wrong:** Every other endpoint that accepts book ids from the client enforces the restriction: `ctx.has_id` in `content.get`, `books.book_manifest`, `books.book_file`, `code.book_metadata` and `legacy.legacy_book`, and `ctx.allowed_book_ids` in `ajax.books`, `books.get_last_read_positions` and `books.get_annotations`. `Context.has_id` (`handler.py:91-98`) exists for this purpose. The `search_result` ids in the same function are already restricted, so only `extra_books` gets through.
- **Severity:** high (breaks an access-control feature)
- **Fix:** Filter the ids first, for example `allowed = ctx.allowed_book_ids(rd, db)` and then `extra_books = {i for i in extra_books if i in allowed}`, or call `ctx.has_id(rd, db, book_id)` before `book_as_json`.

## 2. `max_job_time = 0` ("no limit") aborts every worker job immediately

- **File/line:** `src/calibre/srv/jobs.py:98`, `198-212` (`update_max_block`), `214-224` (`abort_hanging_jobs`)
- **What goes wrong:** When `opts.max_job_time` is 0, `self.max_job_time` is 0. Then `delta = self.max_job_time - (now - job.start_time)` is `<= 0` for every running job:
  - `update_max_block` sets `max_block = 0`.
  - The `run()` loop's `events.get(timeout=0)` raises `Empty`.
  - `abort_hanging_jobs` then sets `abort_event` on every job.

  So every book render (`books.py` `queue_job`) and conversion job is aborted as soon as it starts.
- **Why it is wrong:** The option's help text (`opts.py:79-81`) says: "Maximum amount of time worker processes are allowed to run (in minutes). Set to zero for no limit."
- **Severity:** high when the documented setting is used (the viewer and conversion stop working)
- **Fix:** Treat 0 as unlimited. In `update_max_block`, set `self.max_block = None` and return when `self.max_job_time == 0`. In `abort_hanging_jobs`, return early when `self.max_job_time == 0`.

## 3. HTTP/1.0 detection uses the wrong attribute, so HTTP/1.0 clients get chunked or gzip responses

- **File/line:** `src/calibre/srv/http_response.py:561`
- **What goes wrong:** The code is `output = self.finalize_output(output, data, self.method is HTTP1)`. `self.method` is the request method (`'GET'`, `'POST'`, …) and `HTTP1` is `'HTTP/1.0'`, so `is_http1` is always `False`. The `and not is_http1` guards in `finalize_output` (lines 757 and 759) therefore never apply. An HTTP/1.0 client that sends `Accept-Encoding: gzip` gets a gzip body with `Transfer-Encoding: chunked` (line 794). It also gets `Accept-Ranges` and 206 range responses.
- **Why it is wrong:** The `is_http1` parameter exists to switch these HTTP/1.1-only features off for HTTP/1.0 peers. RFC 7230 §3.3.1 says a server must not send `Transfer-Encoding` to an HTTP/1.0 client, which cannot decode chunked framing.
- **Severity:** medium
- **Fix:** Use `self.response_protocol is HTTP1`. Separately, `GeneratedOutput` with `content_length is None` is still sent chunked to HTTP/1.0 clients even after this fix. For those clients it should instead close the connection and send the body without framing.

## 4. A Range request on a compressible response sends `Transfer-Encoding: chunked` with a body that is not chunked

- **File/line:** `src/calibre/srv/http_response.py:784-808`
- **What goes wrong:** Take a response that is compressible: text/*, JS, JSON, XML or SVG, or no Content-Type, at least `compress_min_size` bytes (default 1024), status 200, and the client sent `Accept-Encoding: gzip`. If the request also has a satisfiable `Range` header:
  - Gzip is skipped (`if compressible and not ranges`).
  - Line 793 `if compressible or output.content_length is None:` still adds `Transfer-Encoding: chunked`.
  - Lines 796-801 add `Content-Length`/`Content-Range` and set `output.ranges`.
  - `write_response_body` (lines 642-648) writes the raw byte range with no chunk framing.

  The client sees `Transfer-Encoding: chunked`, which takes precedence over `Content-Length` under RFC 7230 §3.3.3. It tries to parse the raw bytes as chunks, and the transfer fails. Example trigger: a download manager resuming `/get/txt/<id>` or `/static/*.js` with `Accept-Encoding: gzip` and `Range: bytes=100-`.
- **Why it is wrong:** The body is only chunk-encoded on the `GeneratedOutput` path, and range output is never a `GeneratedOutput`.
- **Severity:** medium
- **Fix:** Use `if (compressible and not ranges) or output.content_length is None:` on line 793. Clearer still: set `compressible = False` as soon as `ranges` is non-empty.

## 5. SSL close path closes the wrong connection (uses a stale loop variable)

- **File/line:** `src/calibre/srv/loop.py:615-616`
- **What goes wrong:**

  ```python
  for x, conn in close_needed:
      self.close(s, conn)
  ```

  This passes `s`, which is left over from the earlier `for s, conn in self.connection_map.items()` loop (or the `remove` loop), instead of `x`. `ServerLoop.close` does `self.connection_map.pop(s)` and then `conn.close()`. The effect is:
  - The dead SSL connection's socket is closed but its entry stays in `connection_map`. The next `select()` then gets a closed fd.
  - An unrelated, possibly live connection is removed from the map without its socket being closed. Its client hangs and the fd leaks.
- **Why it is wrong:** `close_needed` is built as `(s, conn)` pairs specifically so that each pair can be closed together.
- **Severity:** medium (only when SSL is enabled, but it affects other clients)
- **Fix:** `for x, conn in close_needed: self.close(x, conn)`.

## 6. `BanList` never expires entries, so login-failure counts build up forever (verified)

- **File/line:** `src/calibre/srv/auth.py:52-60`
- **What goes wrong:** `failed()` moves the key to the end of the `OrderedDict` (newest last) and then prunes with `for old in reversed(self.items)`. That loop looks at the newest entry first, which was just stamped `now`, so it breaks straight away and removes nothing. As a result:
  - The dict grows without bound, one entry per client IP that ever failed.
  - A client's failure count never resets. Five mistyped passwords spread over weeks still ban the IP.

  Verified with a copy of the class (`ban_after=2`, 0.5 s interval): after two failures 0.6 s apart the key was banned, and entries older than the interval were still present.
- **Why it is wrong:** The pruning loop exists to drop entries whose last failure is older than `interval` (`now - previous_fail > self.interval`). Those entries are at the front of the dict, not the back.
- **Severity:** medium (only when `ban_for` > 0; default is 0)
- **Fix:** Iterate oldest-first with `for old in self.items:` and `break` at the first entry that is not expired.

## 7. A stale but otherwise correct Digest nonce is counted as a failed login

- **File/line:** `src/calibre/srv/auth.py:293-303`
- **What goes wrong:** When the password and digest are correct but `is_nonce_stale()` is true, the code falls through to `log_msg = 'Failed login attempt …'` and `self.ban_list.failed(ban_key)`. Nonces go stale after `MAX_AGE_SECONDS` (1 h). Nonces from before a server restart are also rejected because the secret is regenerated at startup. So a browser that reuses cached Digest credentials (typically several parallel requests) builds up "failures" and gets banned, even though it sent the right password.
- **Why it is wrong:** The `stale="true"` response (line 323-324) tells the client to retry with a fresh nonce without asking the user again (RFC 2617 §3.2.1). It is not an authentication failure. Counting it towards `ban_after` contradicts the ban's purpose ("repeated login failures", `opts.py:189-199`).
- **Severity:** medium (only when banning is enabled)
- **Fix:** Call `ban_list.failed()` only when validation actually failed, not when the nonce is merely stale. Consider treating nonces that fail `validate_nonce` the same way and responding with `stale=true`.

## 8. `clean_final()` never deletes anything, so the rendered-book cache grows without limit

- **File/line:** `src/calibre/srv/books.py` `clean_final`, the `safe_remove(x)` call inside the `for x in os.listdir(fdir)` loop
- **What goes wrong:** `x` is just the directory entry name (a hash), not a path. `safe_remove(x)` calls `os.path.isfile(x)` and `rmtree(x, ignore_errors=True)` relative to the process's current directory. It silently does nothing, or deletes a same-named entry in the current directory. The rendered book directories under `books_cache_dir()/f` are never removed.
- **Why it is wrong:** The comment says "This book has not been accessed for a long time, delete it". The mtime check just above correctly uses `os.path.join(fdir, x, ...)`.
- **Severity:** medium (unbounded disk growth on long-running servers)
- **Fix:** `safe_remove(os.path.join(fdir, x), False)`.

## 9. The chunked request-body parser accepts invalid chunk sizes (signs, `0x`, `_`) and rejects valid chunk extensions (verified)

- **File/line:** `src/calibre/srv/http_request.py:426`
- **What goes wrong:** `chunk_size = int(line.strip(), 16)` accepts `-5`, `+a`, `0x10`, `1_0` and surrounding whitespace (verified: they parse to -5, 10, 16, 16). A negative size makes `read_chunk` compute `end = buf.tell() - 5`. `read()` then returns immediately, `bytes_read` goes down, and parsing continues at a position the sender did not intend. Meanwhile a legal `1a;name=value` chunk extension is rejected with 400.
- **Why it is wrong:** RFC 7230 §4.1 defines `chunk-size = 1*HEXDIG` with optional `chunk-ext`, which must be ignored if not understood. Parsing chunk framing more loosely than a front-end proxy does can cause request smuggling or desync.
- **Severity:** medium
- **Fix:** Strip any `;…` extension, then require the remaining token to match `[0-9A-Fa-f]+` before calling `int(tok, 16)`.

## 10. `get_ranges` crashes on a malformed Range header and returns negative or empty ranges (verified)

- **File/line:** `src/calibre/srv/http_response.py:137-161`
- **What goes wrong:**
  - `Range: bytes=5` has no `-`, so `start, stop = (... for x in brange.split('-', 1))` raises `ValueError`. That escapes `finalize_output`, which runs in the server loop, and the client gets a 500 instead of the header being ignored.
  - `bytes=--5` produces `Range(start=105, stop=99, size=-5)`, which is served as a 206 with `Content-Length: -5`.
  - `bytes=-0` produces `Range(100, 99, 0)`.
  - Any suffix range on an empty file produces `Range(0, -1, 0)`.

  All four verified with `content_length=100`, or 0 for the empty-file case.
- **Why it is wrong:** The docstring says an empty list means no valid range was found (→ 416). RFC 7233 §2.1 says a suffix-length of 0 is unsatisfiable, and syntactically invalid ranges must be ignored.
- **Severity:** low
- **Fix:** Skip parts without `-`. Reject a negative or zero suffix length with `if stop <= 0: continue`. Skip suffix ranges when `content_length == 0`.

## 11. `cdb_set_fields` recipe-format check misses `downloaded_recipe`

- **File/line:** `src/calibre/srv/cdb.py:226`
- **What goes wrong:** `if fmt.lower() in ('recipe', 'original_recipe')` blocks only two names. Adding a format with `ext` of `downloaded_recipe` or `original_downloaded_recipe` through `/cdb/set-fields` succeeds.
- **Why it is wrong:** The same file defines `is_recipe_fmt()` (lines 68-70), which treats `downloaded_recipe` (and any `original_` prefix) as a recipe. `cdb_add_book` blocks those names with the message "as they allow code execution". The two write paths disagree.
- **Severity:** medium (requires write access, but defeats an explicit code-execution guard)
- **Fix:** Use `if is_recipe_fmt(fmt):` in `cdb_set_fields`.

## 12. `cdb_add_book` writes uploads to a fixed name in the shared server temp dir

- **File/line:** `src/calibre/srv/cdb.py:107-113`
- **What goes wrong:** `path = os.path.join(rd.tdir, sfilename)`. `rd.tdir` is the single `TemporaryDirectory` shared by the whole server loop (`loop.py:536-537`). Two concurrent uploads with the same filename, such as two users adding `book.epub`, run on different worker threads and overwrite each other's file between the write and the read. One user's book is added with the other user's content. The file is also never deleted, so every upload stays on disk until the server shuts down.
- **Why it is wrong:** Requests run concurrently on the `ThreadPool` (`pool.py`), and nothing serializes this path.
- **Severity:** medium-low
- **Fix:** Create a unique per-request directory or file (`tempfile.mkdtemp(dir=rd.tdir)`), then remove it after `add_books`.

## 13. After a Request-URI parse error the connection stays open with the headers unread

- **File/line:** `src/calibre/srv/http_request.py:328-331`
- **What goes wrong:** When `parse_uri` fails (fragment in the URI, authority-form target, bad query string), the code sends a 400 with `close_after_response=False`. It does this before the header block (and any body) has been read. `reset_state()` → `connection_ready()` then parses the leftover header lines as the next request line. So one request gets two responses: the first 400, then a "Malformed Request-Line" 400. If there were no headers, the request body is parsed as a new request.
- **Why it is wrong:** Every other early error in the request-line and header phase uses the default `close_after_response=True`, precisely because the rest of the message was not consumed.
- **Severity:** low
- **Fix:** Drop `close_after_response=False` on line 331.

## 14. `Accept-Encoding` q=0 is treated as acceptable

- **File/line:** `src/calibre/srv/http_response.py:101-105` together with `src/calibre/srv/utils.py:232-248`
- **What goes wrong:** `sort_q_values` keeps items whose q is 0 and only sorts them last. `acceptable_encoding` returns the first allowed item, so `Accept-Encoding: gzip;q=0` still returns `'gzip'` and the response is gzip-compressed.
- **Why it is wrong:** RFC 7231 §5.3.1 says q=0 means "not acceptable".
- **Severity:** low
- **Fix:** In `sort_q_values`, or in `acceptable_encoding`/`preferred_lang`, drop items with q == 0.

## 15. `X-Forwarded-For` is lost for requests with `Expect: 100-continue`

- **File/line:** `src/calibre/srv/http_request.py:396-399`
- **What goes wrong:** The `Expect: 100-continue` branch returns before `self.forwarded_for = inheaders.get('X-Forwarded-For')` runs. For those requests (typically large POST uploads from curl and similar clients) the access log and `RequestData.forwarded_for` show no forwarded address.
- **Severity:** low
- **Fix:** Move the `forwarded_for` assignment above the `Expect` check.

---

## Files actually read

- `/tmp/control/TASK-calibre.md`
- `src/calibre/srv/http_request.py`
- `src/calibre/srv/http_response.py`
- `src/calibre/srv/utils.py`
- `src/calibre/srv/web_socket.py`
- `src/calibre/srv/auth.py`
- `src/calibre/srv/loop.py`
- `src/calibre/srv/routes.py`
- `src/calibre/srv/handler.py`
- `src/calibre/srv/errors.py`
- `src/calibre/srv/users.py`
- `src/calibre/srv/library_broker.py`
- `src/calibre/srv/content.py`
- `src/calibre/srv/code.py`
- `src/calibre/srv/ajax.py`
- `src/calibre/srv/last_read.py`
- `src/calibre/srv/pool.py`
- `src/calibre/srv/jobs.py`
- `src/calibre/srv/cdb.py`
- `src/calibre/srv/fts.py` (lines 1-76)
- Partial reads:
  - `src/calibre/srv/books.py` (lines 55-150, 190-210, 345-373, plus grep over endpoints)
  - `src/calibre/srv/opds.py` (lines 520-615, 674-790)
  - `src/calibre/srv/convert.py` (lines 190-240)
  - `src/calibre/srv/legacy.py` (lines 320-354)
  - `src/calibre/srv/metadata.py` (`book_as_json`)
  - `src/calibre/srv/opts.py` (option defaults and help for `max_job_time`, `ban_for`, `ban_after`, `compress_min_size`, `timeout`)
- Tests: `src/calibre/srv/tests/http.py` (lines 124-147, 340-470) and `src/calibre/srv/tests/auth.py` (lines 295-330)
- `src/polyglot/urllib.py`
