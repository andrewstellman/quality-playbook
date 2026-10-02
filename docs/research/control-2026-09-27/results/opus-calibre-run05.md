# Code review: calibre `src/calibre/srv/` (pinned 7691f4f1a155d799afdfec99e2cdc2716c178402)

Reviewer: opus, run 05. Checkout: `/tmp/control/calibre` (read-only). Scratch work in `/tmp/control-work/opus-calibre-run05/` (deleted when finished).

Where I could run a check, I extracted the relevant function from the checkout and ran it under Python 3.10 with small stubs. Those checks are marked **(verified by running)**. The rest come from reading the code.

---

## 1. Adding a `DOWNLOADED_RECIPE` format through `/cdb/set-fields` gets past the recipe guard (code execution)

- **File/line:** `src/calibre/srv/cdb.py:226`
- **What goes wrong:** `cdb_set_fields` rejects added formats only when `fmt.lower() in ('recipe', 'original_recipe')`. A client with write access can send `added_formats=[{'ext': 'downloaded_recipe', ...}]` and the format is stored. `/conversion/start` accepts `input_fmt` from the client (`convert.py:207-209`). `RecipeInput` handles `file_types = {'recipe', 'downloaded_recipe'}`, and for `downloaded_recipe` it unzips the file and runs `compile_recipe()` on `download.recipe` (`ebooks/conversion/plugins/recipe_input.py:71-80`). The result is attacker-supplied Python running on the server.
- **Why it is wrong:** The same module defines `is_recipe_fmt()` (`cdb.py:68-70`), which covers `downloaded_recipe` and any `original_` prefix. `cdb_add_book` uses it, with the stated reason "as they allow code execution" (`cdb.py:102-103`). `cdb_set_fields` applies a weaker, hand-written check that misses `downloaded_recipe` and `original_downloaded_recipe`.
- **Severity:** high
- **Fix:** At line 226, use `if is_recipe_fmt(fmt): raise HTTPForbidden(...)`. Also consider rejecting recipe input formats in `start_conversion`.

## 2. `max_job_time = 0` aborts every job at once instead of meaning "no limit"

- **File/line:** `src/calibre/srv/jobs.py:98`, `:198-212`, `:214-224`
- **What goes wrong:** With `max_job_time=0`, `self.max_job_time = 0`. In `update_max_block`, `delta = 0 - (now - job.start_time) <= 0`, so `max_block = 0`. `events.get(timeout=0)` then raises `Empty`, and `abort_hanging_jobs()` sets `abort_event` on every running job. Every book render (`/book-manifest`) and every conversion is aborted as soon as it starts.
- **Why it is wrong:** The option's documentation says: "Maximum amount of time worker processes are allowed to run (in minutes). Set to zero for no limit." (`opts.py:78-81`).
- **Severity:** medium-high. A documented setting breaks the viewer and conversion.
- **Fix:** Treat `max_job_time <= 0` as unlimited. For example, skip the timeout computation in `update_max_block` and `abort_hanging_jobs` when `self.max_job_time == 0`.

## 3. Book metadata is served for any id in `extra_books`, bypassing per-user library restrictions

- **File/line:** `src/calibre/srv/code.py:456-465` (used by `/interface-data/books-init` and `/interface-data/init`)
- **What goes wrong:** `extra_books` comes straight from the query string, and `book_as_json(db, book_id)` is called for each id without `ctx.has_id(rd, db, book_id)` or `allowed_book_ids`. `book_as_json` (`metadata.py:72-87`) only checks `db.has_id`. A user with a library restriction such as `tags:"public"` can request `?extra_books=1,2,3,...` and get full metadata (title, authors, comments, identifiers, formats, notes, data files) for books the restriction hides.
- **Why it is wrong:** Every other metadata path enforces the restriction: `book_metadata` (`code.py:633`), `/ajax/book` (`ajax.py:165`), and `/ajax/books` (`ajax.py:218-222`).
- **Severity:** medium (information disclosure)
- **Fix:** Filter `extra_books` against `ctx.allowed_book_ids(rd, db)` before the loop.

## 4. HTTP/1.0 detection is always False (`self.method is HTTP1`)

- **File/line:** `src/calibre/srv/http_response.py:561`
- **What goes wrong:** `self.finalize_output(output, data, self.method is HTTP1)` compares the request method (`'GET'`, `'POST'`, ...) with `HTTP1 == 'HTTP/1.0'`, so `is_http1` is always False. HTTP/1.0 clients that send `Accept-Encoding: gzip` get gzip output sent with `Transfer-Encoding: chunked` (lines 752-758 and 793-794). HTTP/1.0 has no chunked transfer coding, so these clients cannot parse the body. They are also sent `Accept-Ranges: bytes` (line 759).
- **Why it is wrong:** `finalize_output` clearly means to disable compression and range advertising for HTTP/1.0 (`and not is_http1`). The connection records the negotiated protocol in `self.response_protocol` (`http_request.py:326`).
- **Severity:** medium
- **Fix:** Pass `self.response_protocol is HTTP1`. Separately, a `GeneratedOutput` (unknown length) sent to an HTTP/1.0 client should use close-delimited framing, not chunked.

## 5. A Range request on a compressible file produces a malformed response (both chunked and Content-Length, raw body)

- **File/line:** `src/calibre/srv/http_response.py:751-808`
- **What goes wrong:** Take a request for a filesystem-backed compressible resource (`text/*`, JSON, JS, SVG, at least `compress_min_size` bytes, which is 1024 by default) with both `Accept-Encoding: gzip` and a satisfiable `Range` header. `compressible` is True and `ranges` is non-empty. Line 784 (`compressible and not ranges`) skips compression. Line 793 (`if compressible or ...`) still sets `Transfer-Encoding: chunked`. Lines 796-801 then set `Content-Length` and `Content-Range` and return a `ReadableOutput` with `ranges`. `write_response_body` writes that raw, not chunk-framed. The client sees `Transfer-Encoding: chunked` and tries to parse the raw bytes as chunks, so the response is corrupted or the client errors.
- **(verified by running)** With `finalize_output` extracted and a 5000-byte `.css` file, `Range: bytes=0-9` plus `Accept-Encoding: gzip` gave status 206 with headers `{'Transfer-Encoding': 'chunked', 'Content-Length': '10', 'Content-Range': 'bytes 0-9/5000', ...}` and a raw `ReadableOutput`.
- **Why it is wrong:** RFC 7230 §3.3.2 says a sender must not send Content-Length together with Transfer-Encoding. The body is also not chunk-encoded, which contradicts the header.
- **Severity:** medium (static JS/CSS and text book files are served this way; browsers and media players send Range together with Accept-Encoding)
- **Fix:** Once ranges are selected, set `compressible = False`, or change line 793 to `if (compressible and not ranges) or output.content_length is None`.

## 6. Negative chunk sizes are accepted, which lets a client bypass `max_request_body_size`

- **File/line:** `src/calibre/srv/http_request.py:420-443`
- **What goes wrong:** `chunk_size = int(line.strip(), 16)` accepts `-FFFFFFFF` (Python's `int` takes a sign). For a negative size, the size check at line 429 passes. `read_chunk` gets `end = buf.tell() + chunk_size` (before the current position), so `read()` returns True immediately (`size <= 0`). Then `bytes_read[0] += chunk_size` makes the counter very negative. After that, arbitrarily large real chunks pass the checks at lines 429 and 452, and the body spools to disk (`SpooledTemporaryFile`) with no limit.
- **Why it is wrong:** The chunk-size grammar is `1*HEXDIG` (RFC 7230 §4.1). `max_request_body_size` exists to cap uploads (`http_request.py:257`, and the checks at 429 and 452).
- **Severity:** medium (a remote client can fill the disk; the request is still dispatched)
- **Fix:** Validate the token with `re.fullmatch(rb'[0-9A-Fa-f]+', size_token)` before `int(..., 16)`. Also strip chunk extensions (`line.partition(b';')[0]`) instead of rejecting them. RFC 7230 §4.1.1 says a recipient MUST ignore unrecognized chunk extensions, but the current code returns 400 for `5;foo=bar`.

## 7. The SSL close-needed loop closes and deregisters the wrong socket

- **File/line:** `src/calibre/srv/loop.py:612-613`
- **What goes wrong:**
  ```python
  for x, conn in close_needed:
      self.close(s, conn)
  ```
  This uses `s`, left over from the earlier `for s, conn in self.connection_map.items()` loop, instead of `x`. `self.close` pops `connection_map[s]`, the last socket iterated, and calls `conn.close()` on the correct connection. So the dead connection stays in `connection_map` with a closed socket. Its fd can then be given to `select`, or a new connection can reuse the fd number. The unrelated live connection is dropped from the map and never serviced again, which leaks it.
- **Why it is wrong:** `ServerLoop.close(s, conn)` expects `s` to be the key for `conn` (`loop.py:705-707`).
- **Severity:** medium (only on SSL-enabled servers, when `drain_ssl_buffer` marks a connection not ready)
- **Fix:** `self.close(x, conn)`.

## 8. `BanList` never prunes old entries, and failure counts never reset after a ban expires

- **File/line:** `src/calibre/srv/auth.py:44-60`
- **What goes wrong:** `failed()` inserts the key that just failed at the end of the `OrderedDict` with timestamp `now`, then walks `reversed(self.items)`. The first item it sees is always that new entry (`now - now = 0`), so it hits `break` and removes nothing. The dict grows by one entry per distinct failing IP, forever. Also, `fail_count` is carried over no matter how old the previous failure was. After a ban expires, one more failed login re-bans the IP for the full interval.
- **(verified by running)** 1000 failures from distinct IPs, 100 s apart with a 60 s interval, left 1000 entries. With `ban_after=2`, one failure 10000 s after the ban expired re-banned the IP at once.
- **Why it is wrong:** The pruning code is meant to evict entries older than `interval`, but it iterates newest-first. The option says bans happen after "repeated login failures" (`opts.py:188-199`), not after one failure following an expired ban.
- **Severity:** low-medium (unbounded memory growth when many source IPs fail logins; over-banning)
- **Fix:** Iterate oldest-first (`for old in self.items:`). When the popped entry's `previous_fail` is older than `interval`, restart `fail_count` at 0.

## 9. `clean_final` never removes the rendered-book cache (path not joined)

- **File/line:** `src/calibre/srv/books.py:108-116`
- **What goes wrong:** The loop gets the mtime from `os.path.join(fdir, x, ...)`, but for expired entries it calls `safe_remove(x)` with the bare directory name. `os.path.isfile(x)` is evaluated relative to the server's current working directory, so it is False, and `rmtree(x, ignore_errors=True)` targets `./<hash>` in the CWD. The cache in `cache_dir()/srvb/f` is never cleaned, and a same-named directory in the CWD could be deleted.
- **Why it is wrong:** The comment reads "This book has not been accessed for a long time, delete it", and the mtime is read from `fdir/x`.
- **Severity:** medium (the render cache grows without bound)
- **Fix:** `safe_remove(os.path.join(fdir, x), False)`.

## 10. `create_file_copy` permanently caches a partially written file when `copy_func` fails

- **File/line:** `src/calibre/srv/content.py:89-121`
- **What goes wrong:** `open_for_write(fname)` creates the cache file, then `copy_func(ans)` runs (`db.copy_format_to`, `set_metadata`, cover scaling, ...). If that raises, the truncated or partial file stays on disk with an mtime newer than the library `mtime`. Every later request takes the `else` branch (`previous_mtime >= mt`) and serves the corrupted cached copy, with no error, until the book is modified again.
- **Why it is wrong:** The docstring says the copy is reused only "if there have been no changes to the data"; it assumes the cached copy is complete.
- **Severity:** medium (silently corrupted downloads and covers)
- **Fix:** Write to a temporary name in `base` and `atomic_rename` it into place only after `copy_func` succeeds, or catch the exception, close the file and remove `fname` before re-raising.

## 11. `/data-files/remove` can delete any file in the book directory, not just data files

- **File/line:** `src/calibre/srv/content.py:652-668`
- **What goes wrong:** `relpaths` from the JSON body go straight to `db.remove_extra_files(book_id, relpaths, permanent=True)`. The backend only checks that each path stays inside the book folder (`db/backend.py:2324-2335`, `path_from_root`). A client can therefore permanently delete `cover.jpg`, `metadata.opf` or the book's format files (`Title - Author.epub`) behind the database's back, leaving the library inconsistent.
- **Why it is wrong:** The endpoint belongs to the data-files API. The matching upload endpoint forces the `DATA_DIR_NAME/` prefix (`content.py:639`), and listing uses `pattern=DATA_FILE_PATTERN`.
- **Severity:** medium-low (needs write access, but it corrupts the library)
- **Fix:** Reject any relpath that does not start with `DATA_DIR_NAME + '/'`, or check each one against `db.list_extra_files(book_id, pattern=DATA_FILE_PATTERN)`.

## 12. `/cdb/add-book` writes uploads to a shared, filename-keyed temp path (race and leak)

- **File/line:** `src/calibre/srv/cdb.py:107-119`
- **What goes wrong:** `path = os.path.join(rd.tdir, sanitize_file_name(filename))`, where `rd.tdir` is the server-wide temp dir. Requests run on a 10-thread pool, so two concurrent uploads with the same filename (for example `book.epub` from two clients) overwrite each other. One request can read the other's data and add the wrong book, or read a half-written file. The file (and any import-plugin output) is never deleted, so `tdir` accumulates every uploaded book.
- **Why it is wrong:** `rd.tdir` is shared by all requests (see its use in `content.py:74`, `convert.py:166`). Other code uses per-request `tempfile.mkdtemp(dir=rd.tdir)`.
- **Severity:** medium-low
- **Fix:** Create a unique directory with `tempfile.mkdtemp(dir=rd.tdir)`, write the file into it, and `rmtree` it in a `finally`.

## 13. Malformed Range headers cause a 500, or produce negative or empty ranges

- **File/line:** `src/calibre/srv/http_response.py:137-161`
- **What goes wrong (verified by running `get_ranges(..., 100)`):**
  - `bytes=5` (no dash): `start, stop = (... brange.split('-', 1))` raises `ValueError: not enough values to unpack`. It is not caught, it escapes `finalize_output`/`job_done`, and the server returns 500.
  - `bytes=--5` gives `Range(start=105, stop=99, size=-5)`, so the response has `Content-Length: -5` and `Content-Range: bytes 105-99/100`.
  - `bytes=-0` gives `Range(start=100, stop=99, size=0)` (a 206 with an invalid Content-Range). For an empty file, `bytes=-5` gives `Range(0, -1, 0)`.
- **Why it is wrong:** The docstring says the function returns an empty list when no valid range is found. RFC 7233 §2.1 says a suffix-length of 0 is unsatisfiable, and an invalid byte-range-spec should make the header be ignored, not cause a server error.
- **Severity:** low-medium
- **Fix:** Skip any `brange` that has no `-`. Require `start`/`stop` to be non-negative digit strings (`str.isdigit()`). Skip suffix lengths `<= 0`. Treat `content_length == 0` as unsatisfiable.

## 14. `sort_q_values` ignores `q=0` and misparses `; q=` with whitespace

- **File/line:** `src/calibre/srv/utils.py:232-248` (used by `acceptable_encoding` and `preferred_lang` in `http_response.py:101-117`)
- **What goes wrong (verified by running):** `sort_q_values('gzip;q=0, identity')` returns `('identity', 'gzip')`, so `acceptable_encoding` still picks gzip although the client said it is not acceptable. `sort_q_values('fr; q=0.1, de; q=0.9')` returns `('fr', 'de')`: because `p == ' q'` does not equal `'q'`, both get q=1.0 and the order is wrong.
- **Why it is wrong:** RFC 7231 §5.3.1: a qvalue of 0 means "not acceptable". OWS is allowed around `;` in the weight parameter.
- **Severity:** low
- **Fix:** Strip `p` and `v`, and drop items whose q is 0.

## 15. `Accept-Ranges: bytes` is advertised for responses that ignore Range

- **File/line:** `src/calibre/srv/http_response.py:759`
- **What goes wrong:** `output.accept_ranges is not None` is always True, because `accept_ranges` is always a bool (`True`/`False` at lines 362, 392, 411). Dynamic (`dynamic_output`) and generated (`GeneratedOutput`) responses get `Accept-Ranges: bytes` even though line 760 never applies ranges to them.
- **Why it is wrong:** It advertises a capability the server does not provide for that resource (RFC 7233 §2.3).
- **Severity:** low
- **Fix:** Use `output.accept_ranges` (truthiness) instead of `is not None`.

## 16. A completed conversion never notifies listeners that a format was added

- **File/line:** `src/calibre/srv/convert.py:252`
- **What goes wrong:** `formats_added({job_status.book_id: (fmt,)})` builds a `FormatsAdded` event object (`changes.py:27-34, 64`) and throws it away. `ctx.notify_changes` is never called, so an embedded server's GUI (and any other `notify_changes` consumer) is not told that the book gained a new format.
- **Why it is wrong:** Everywhere else, events are passed to `ctx.notify_changes(db.backend.library_path, <event>)` (for example `cdb.py:123, 145, 163, 251`).
- **Severity:** low
- **Fix:** `ctx.notify_changes(db.backend.library_path, formats_added({job_status.book_id: (fmt,)}))`.

## 17. `/mobile` pagination hides the last page when `total == start + num`

- **File/line:** `src/calibre/srv/legacy.py:117`
- **What goes wrong:** Page `start` shows books `start .. start+num-1` (1-based; `mobile()` slices `[(start-1):(start-1)+num]`). There is a next page whenever `start + num - 1 < total`, that is `total >= start + num`. The code checks `total > start + num`. With `total=26, num=25, start=1`, no Next/Last links are rendered and book 26 can't be reached.
- **Severity:** low
- **Fix:** `if total >= start + num:`.

---

## Items considered and not reported

I did not report these because they are working as intended, or I was not confident they are real defects:
- `set_note` base64 slice including the comma: harmless, because `b64decode` discards non-alphabet characters.
- Icon cache path traversal: blocked by `path_from_root` rejecting `..`.
- Router `msgpack_or_json` exact Accept matching.
- Ordering of the ajax category list.
- Race between `start_job` and the `conversion_jobs` registration in `convert.queue_job`.
- OPDS grouping with `Tag.sort is None`: only reachable for formats/identifiers, and only past `max_opds_ungrouped_items`.

## Files read

In scope (`src/calibre/srv/`):
- Read fully: `http_request.py`, `http_response.py`, `loop.py`, `web_socket.py`, `auth.py`, `utils.py`, `routes.py`, `handler.py`, `errors.py` (top), `content.py`, `code.py`, `ajax.py`, `cdb.py`, `books.py`, `users.py`, `users_api.py`, `last_read.py`, `library_broker.py`, `pool.py`, `jobs.py`, `fts.py`, `convert.py`, `changes.py`, `legacy.py`.
- Read in part: `opts.py`, `opds.py`, `metadata.py`.
- Not read: `render_book.py`, `auto_reload.py`, `manage_users_cli.py`, `standalone.py`, `embedded.py`, `legacy_book_details.py`, `pre_activated.py`, `bonjour.py`.

Tests (checked only whether behaviour is covered): `tests/http.py` (range and gzip sections), `tests/auth.py` (grep).

Outside scope, for context:
- `db/cache.py` (`add_extra_files`, `remove_extra_files`)
- `db/backend.py` (`remove_extra_files`, `add_extra_file`)
- `utils/filenames.py` (`path_from_root`)
- `db/categories.py` (`Tag`)
- `db/fields.py` (`get_categories`)
- `ebooks/conversion/plugins/recipe_input.py`
