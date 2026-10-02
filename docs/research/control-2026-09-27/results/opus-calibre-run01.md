# Code review: calibre `src/calibre/srv/` @ 7691f4f1a155d799afdfec99e2cdc2716c178402

Reviewer: Opus (control run). Checkout: `/tmp/control/calibre` (read-only). Scratch: `/tmp/control-work/opus-calibre/`.

I checked several findings by running the relevant functions on their own (copied out of the source) under Python 3.10: `get_ranges`, `BanList`, `sort_q_values` / `acceptable_encoding` and `int(..., 16)`. I confirmed the others by reading the code paths end to end.

---

## 1. Negative or `0x`-prefixed chunk sizes are accepted and bypass `max_request_body_size`

- **File/line:** `src/calibre/srv/http_request.py:426` (`chunk_size = int(line.strip(), 16)`), with `:429`, `:437` and `:442`.
- **What goes wrong:** Python's `int(x, 16)` accepts a sign, a `0x` prefix and `_` separators. A chunk-size line of `-f4240` parses as -1000000. It passes the size check at line 429, and `read_chunk` returns immediately because `read()` sees `size <= 0`. Line 442 then adds -1000000 to `bytes_read[0]`. A client can send one or more negative "chunks" (each followed by CRLF) and then real chunks up to about `max_request_body_size` plus the accumulated negative total. Each later check compares against the reduced counter, so any total body size gets through.
- **Why it is wrong:** RFC 7230 §4.1 defines `chunk-size = 1*HEXDIG`, with no sign and no prefix. The code's own intent is to enforce `max_request_body_size` on chunked bodies (lines 429–433 and 452–456). The body is read before authentication, so an unauthenticated client can use this to fill the temp directory: the body goes to a `SpooledTemporaryFile` in `tdir`.
- **Verified:** `int(b'-f4240',16) == -1000000`, `int(b'0x10',16) == 16`, `int(b'+1_0',16) == 16`.
- **Severity:** medium (a size limit that can be bypassed, which enables disk exhaustion).
- **Fix:** Validate the token before converting it. For example, take `line.split(b';')[0].strip()`, require it to match `rb'[0-9A-Fa-f]+'`, and then call `int(tok, 16)`. This also lets you accept chunk extensions instead of rejecting them.

## 2. `ServerLoop.tick` closes the wrong connection for SSL connections that fail to drain

- **File/line:** `src/calibre/srv/loop.py:615-616`
  ```python
  for x, conn in close_needed:
      self.close(s, conn)
  ```
- **What goes wrong:** The loop variable is `x`, but the call passes `s`, which is left over from the earlier `for s, conn in self.connection_map.items()` or `for s, conn in remove` loops. `close()` does `self.connection_map.pop(s)` followed by `conn.close()`. As a result:
  - The dead SSL connection's socket is closed, but its entry stays in `connection_map` under its real fd.
  - An unrelated live connection (whichever fd `s` still refers to) is removed from the map without being closed. Its in-flight request is silently abandoned and its socket leaks until garbage collection.
  - On the next tick, the stale entry puts a closed fd into `select()`, which drives the `OSError` fallback path.
- **Why it is wrong:** The intent is plainly to close the connection that was just placed in `close_needed` (`close_needed.append((s, conn))` at line 605).
- **Severity:** medium (only when SSL is enabled, but then it is triggered by any client whose SSL read errors out).
- **Fix:** `for s, conn in close_needed: self.close(s, conn)`.

## 3. HTTP/1.0 detection in `job_done` compares the method, not the protocol

- **File/line:** `src/calibre/srv/http_response.py:561`: `output = self.finalize_output(output, data, self.method is HTTP1)`
- **What goes wrong:** `self.method` is `'GET'`, `'POST'` and so on, while `HTTP1 == 'HTTP/1.0'`, so `is_http1` is always `False`. `finalize_output` relies on this flag to avoid gzip-with-chunked responses and range handling for HTTP/1.0 clients (lines 757 and 759). An HTTP/1.0 client that sends `Accept-Encoding: gzip` for a compressible type therefore gets `Transfer-Encoding: chunked` (line 794), which HTTP/1.0 does not support. The client sees raw chunk-size lines in the body. HTTP/1.0 clients also get `Accept-Ranges` and 206 handling.
- **Why it is wrong:** The parameter is named `is_http1` and is used as "the client speaks HTTP/1.0". The request's protocol is stored in `self.response_protocol`, and that is what `simple_response` checks correctly at line 460.
- **Severity:** medium (HTTP/1.0 clients receive corrupted bodies).
- **Fix:** `self.finalize_output(output, data, self.response_protocol is HTTP1)`.

## 4. `BanList.failed` never prunes old entries, and failure counts never expire

- **File/line:** `src/calibre/srv/auth.py:48-60`
- **What goes wrong:** The entry just inserted for `key` is the newest item in the `OrderedDict`. `for old in reversed(self.items)` visits it first, finds `now - previous_fail > interval` false, and hits `break` straight away. Nothing is ever removed. Two consequences follow:
  - (a) The dict grows without bound, keeping one entry for every IP that has ever failed a login.
  - (b) Line 49 reads `fail_count` from the old entry regardless of its age, so failures accumulate forever. A user who mistypes a password `ban_after` times spread over weeks is banned on the last mistake. After that, every single later failure re-bans them for the full interval.
- **Why it is wrong:** The pruning loop is meant to drop entries older than `interval`, oldest first. Ban windows should be time-bounded.
- **Verified:** With `interval = 0.1 s`, keys `a` and `b` older than the interval survive a later `failed('c')`. A fresh failure for `a` then produces `fail_count == 2` and `is_banned('a') == True`.
- **Severity:** medium.
- **Fix:** Iterate from the oldest end (`for old in self.items:`) and break at the first entry that has not expired. Also treat an expired existing entry as a fresh count, for example `fail_count = 0 if x is None or now - x[0] > self.interval else x[1]`.

## 5. A valid password with a stale digest nonce is counted as a failed login

- **File/line:** `src/calibre/srv/auth.py:297-303`
- **What goes wrong:** When the digest response is correct but `is_nonce_stale` returns true, control falls through to `log_msg = 'Failed login attempt ...'` and `self.ban_list.failed(ban_key)`. A legitimate client with a nonce older than `max_age_seconds` is therefore logged as a failed login and moves toward a ban, even though the server correctly replies `stale="true"` and the client re-authenticates automatically. Combined with finding 4, where counts never decay, long-lived legitimate sessions eventually get banned.
- **Why it is wrong:** RFC 2617 §3.2.1 says `stale=TRUE` means the credentials were valid. The code's own `stale` handling (line 323) acknowledges this.
- **Severity:** low.
- **Fix:** Call `failed()` and set `log_msg` only when validation actually failed, not when `nonce_is_stale` is true.

## 6. `get_ranges` crashes or produces invalid ranges on malformed or edge-case `Range` headers

- **File/line:** `src/calibre/srv/http_response.py:138-161`
- **What goes wrong (verified by running the function):**
  - `Range: bytes=5` (no `-`): the unpack on line 138 raises `ValueError` outside any `try`. The exception propagates out of `finalize_output`/`job_done` and produces a 500 instead of the header being ignored.
  - `Range: bytes=-0`: returns `Range(100, 99, 0)`. The server sends a 206 with `Content-Length: 0` and `Content-Range: bytes 100-99/100`.
  - `Range: bytes=--3`: returns `Range(103, 99, -3)`, which gives a negative `Content-Length`.
  - A suffix range on a zero-length entity (`bytes=-5`, `content_length=0`) returns `Range(0, -1, 0)`.
- **Why it is wrong:** RFC 7233 §2.1 and §4.4: a suffix-length of 0, or any range on an empty representation, is unsatisfiable (416), and syntactically invalid ranges should be ignored. The docstring says an empty list means "no valid range".
- **Severity:** low.
- **Fix:** Wrap the split in a `try` (or `continue` when `'-' not in brange`). For suffix ranges, parse with a strict digit check, and `continue` when `stop <= 0` or `content_length == 0`.

## 7. `Accept-Encoding: gzip;q=0` still gets gzip

- **File/line:** `src/calibre/srv/utils.py:232-248` (`sort_q_values`), used by `http_response.py:101-105` (`acceptable_encoding`).
- **What goes wrong:** Items with `q=0` are kept in the sorted list, and `acceptable_encoding` returns the first allowed token. For `Accept-Encoding: gzip;q=0, identity` it returns `'gzip'` (verified), so the server compresses a response the client explicitly refused. The same applies to `preferred_lang` with `q=0` languages.
- **Why it is wrong:** RFC 7231 §5.3.1: a qvalue of 0 means "not acceptable".
- **Severity:** low.
- **Fix:** Drop items with `q == 0` in `sort_q_values`, or skip them in the consumers.

## 8. `Accept-Ranges: bytes` is advertised for outputs that do not support ranges

- **File/line:** `src/calibre/srv/http_response.py:759`: `accept_ranges = not compressible and output.accept_ranges is not None and ...`
- **What goes wrong:** `accept_ranges` is always a bool (`True` for files, `False` for `dynamic_output` and `GeneratedOutput`), so `is not None` is always true. Dynamic string/bytes responses advertise `Accept-Ranges: bytes`, but line 760 ignores any `Range` request for them (`if output.accept_ranges`).
- **Why it is wrong:** `dynamic_output` explicitly sets `ans.accept_ranges = False` (line 392) to say ranges are not supported. The header contradicts that.
- **Severity:** low.
- **Fix:** Use `output.accept_ranges and ...`.

## 9. A failed `copy_func` leaves a partial file that is then served from cache

- **File/line:** `src/calibre/srv/content.py:105-106` and `:115-116` (`create_file_copy`).
- **What goes wrong:** `open_for_write(fname)` creates the cache file, then `copy_func(ans)` runs. If `copy_func` raises, the truncated or empty file stays on disk with a fresh mtime. Examples: `scale_image` on a corrupt cover, `set_metadata` failing on an unusual EPUB/MOBI/AZW3, or `generate_cover` failing. On the next request `previous_mtime >= mt`, so the cached copy is reused (`used_cache = 'yes'`, line 109-111) and the client downloads a corrupt or empty book or cover with a normal 200. The file handle also leaks.
- **Why it is wrong:** The docstring says the copy is only reused "if there have been no changes". A failed copy is not a valid cache entry.
- **Severity:** medium (silent delivery of corrupt book files).
- **Fix:** Wrap `copy_func` in `try/except`. On failure, close and remove `fname` and re-raise. An alternative is to write to a temp name and `atomic_rename` it into place on success.

## 10. The recipe-format block is incomplete in `/cdb/set-fields` (`added_formats`)

- **File/line:** `src/calibre/srv/cdb.py:226`: `if fmt.lower() in ('recipe', 'original_recipe'):`
- **What goes wrong:** `DOWNLOADED_RECIPE` and `ORIGINAL_DOWNLOADED_RECIPE` are not blocked, so a user with write access can attach a downloaded-recipe format through this endpoint.
- **Why it is wrong:** The same module defines `is_recipe_fmt` (lines 68-70) specifically to cover `downloaded_recipe` and the `original_` prefix, and uses it in `cdb_add_book` with the rationale "as they allow code execution". The two checks disagree, and the narrower one leaves a way around the block.
- **Severity:** medium (a security check that can be bypassed, although write access is required).
- **Fix:** `if is_recipe_fmt(fmt):`.

## 11. `/data-files/remove` can delete any file in the book folder, not just data files

- **File/line:** `src/calibre/srv/content.py:659-668`
- **What goes wrong:** The client-supplied `relpaths` go straight to `db.remove_extra_files(book_id, relpaths, permanent=True)`. The backend (`db/backend.py:2324-2342`) only confines paths to the book directory. A request such as `["cover.jpg"]`, `["metadata.opf"]` or `["Title - Author.epub"]` therefore permanently deletes the cover, OPF or format files behind the database's back. The database still records the format and cover as present.
- **Why it is wrong:** The sibling endpoints treat this API as limited to data files. Upload forces the `DATA_DIR_NAME/` prefix (line 639), and both get (line 612) and list (lines 648 and 669) filter with `pattern=DATA_FILE_PATTERN`.
- **Severity:** medium (library corruption by any user with write access).
- **Fix:** Reject any relpath that does not start with `DATA_DIR_NAME + '/'`, or intersect `relpaths` with `{ef.relpath for ef in db.list_extra_files(book_id, pattern=DATA_FILE_PATTERN)}`.

## 12. OPDS `max_opds_ungrouped_items = 0` forces grouping instead of disabling it

- **File/line:** `src/calibre/srv/opds.py` in `get_navcatalog`: `if MAX_ITEMS > 0 and len(items) <= MAX_ITEMS:` (ungrouped branch) `else:` (grouped branch).
- **What goes wrong:** With the option set to 0, the condition is always false, so every category is grouped by first letter.
- **Why it is wrong:** The option's help text (`opts.py:103-105`) says "Group items ... when there are more than this number of items. Set to zero to disable." With 0, grouping should never happen.
- **Severity:** low.
- **Fix:** `if MAX_ITEMS <= 0 or len(items) <= MAX_ITEMS:`.

## 13. OPDS grouping crashes on categories whose `Tag.sort` is `None`

- **File/line:** `src/calibre/srv/opds.py` in `get_navcatalog`, the grouped branch:
  ```python
  val = getattr(x, 'sort', x.name)   # handles None via `if not val`
  ...
  category_groups[x] = len([y for y in items if getattr(y, 'sort', y.name).upper().startswith(x)])
  ```
- **What goes wrong:** `Tag` always has a `sort` slot, so `getattr(..., x.name)` never falls back. The `formats` and `identifiers` categories create tags with `sort=None` (`db/fields.py:644` and `:697`). When one of these categories has more than `max_opds_ungrouped_items` entries, or the option is 0 (see finding 12), `None.upper()` raises `AttributeError` and the request fails with a 500. Tags whose sort is `''` are counted under no group, even though the first loop put them in `'A'`.
- **Severity:** low.
- **Fix:** Compute `key = (getattr(y, 'sort', None) or y.name or 'A')` once and use it in both places.

## 14. `X-Forwarded-For` is dropped for requests that use `Expect: 100-continue`

- **File/line:** `src/calibre/srv/http_request.py:396-399`. The `100-continue` branch `return`s before `self.forwarded_for = inheaders.get('X-Forwarded-For')` runs.
- **Effect:** Access-log lines (`http_response.py:605-607`) for such requests (typically large POST uploads) are missing the proxied client address.
- **Severity:** low.
- **Fix:** Set `self.forwarded_for` before the `Expect` check.

---

## Files actually read

- `src/calibre/srv/http_request.py` (all)
- `src/calibre/srv/http_response.py` (all)
- `src/calibre/srv/utils.py` (all)
- `src/calibre/srv/auth.py` (all)
- `src/calibre/srv/handler.py` (all)
- `src/calibre/srv/errors.py` (most)
- `src/calibre/srv/routes.py` (all)
- `src/calibre/srv/web_socket.py` (all)
- `src/calibre/srv/loop.py` (all)
- `src/calibre/srv/content.py` (all)
- `src/calibre/srv/users.py` (all)
- `src/calibre/srv/library_broker.py` (all)
- `src/calibre/srv/cdb.py` (all)
- `src/calibre/srv/books.py` (lines ~140-373)
- `src/calibre/srv/opds.py` (lines ~480-640 plus grep of Offsets usage)
- `src/calibre/srv/code.py` (lines ~100-140, 530-640)
- `src/calibre/srv/opts.py` (grep for relevant options)
- Context outside scope: `src/calibre/utils/filenames.py` (`path_from_root`), `src/calibre/db/backend.py` (`remove_extra_files`, `add_extra_file`), `src/calibre/db/cache.py` (`add_extra_files`, `remove_extra_files`), `src/calibre/db/categories.py` (`Tag`), `src/calibre/db/fields.py` (`tag_class` construction sites)

Not reviewed in depth: `ajax.py`, `legacy.py`, `legacy_book_details.py`, `metadata.py`, `render_book.py`, `convert.py`, `fts.py`, `jobs.py`, `pool.py`, `auto_reload.py`, `changes.py`, `last_read.py`, `manage_users_cli.py`, `users_api.py`, `standalone.py`, `embedded.py`, `bonjour.py`, `pre_activated.py`, the C++ sources and `tests/`.
