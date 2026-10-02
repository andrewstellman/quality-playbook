calibre-01 | input | They must try a zero-length resource with a suffix range; lines 158-161 look fine for any non-zero length.
calibre-02 | input | They must try an `Accept-Encoding` or `Accept-Language` with `q=0` and remember that q=0 means "not acceptable"; the sort-then-first-match logic looks reasonable otherwise.
calibre-03 | input | They must imagine a chunk-size line with a `;ext` suffix; `int(line.strip(), 16)` looks right for plain sizes.
calibre-04 | input | They must imagine `copy_func` raising after `open_for_write` has created the file, and then follow the mtime cache check on the next request.
calibre-05 | line | Line 203 shows each line keeps its CRLF, and line 186 joins the folded lines with only `lstrip()` applied, so the embedded CRLF is visible right there.
calibre-06 | input | They must know Python's `int(x, 16)` quirks (`0x`, `+`, `_`) and try such chunk-size strings.
calibre-07 | line | Lines 297-303 show that a request with a valid password and a stale nonce falls through to `log_msg` / `ban_list.failed()`.
calibre-08 | trace | They must open `ServerLoop.serve_forever` in loop.py to see that it calls `initialize_socket()` again after `embedded.start()` already did.
calibre-09 | nearby | They must look at changes.py (`formats_added` is the `FormatsAdded` class) or at cdb.py's `ctx.notify_changes(..., books_added(ids))` pattern to see the result is thrown away.
calibre-10 | input | They must try `max_job_time = 0`; then `delta <= 0` holds for every job.
calibre-11 | input | They must feed a non-hex path segment and know that `from_hex_unicode` raises something other than HTTPNotFound.
calibre-12 | nearby | They must compare with `finalize_headers` (http_request.py), which sets `close_after_response = True` earlier, and see that this line overwrites it.
calibre-13 | line | Unparenthesized `except A, B:` is a syntax error on sight.
calibre-14 | trace | They must follow `db.add_extra_files` into the backend to see that the path is resolved against the book directory, not `data/`, so `../` escapes only to the book folder.
calibre-15 | line | Within 598-604, the first loop guards a falsy `val` and the second calls `.upper()` on the same `getattr` result unguarded.
calibre-16 | nearby | They must read `GeneratedOutput` (line 409, `content_length = None`) to see that the `>=` comparison on line 755 can meet None.
calibre-17 | input | They must try a bare numeric timecount such as `'12.5'`, which SMIL allows; the branch chain has no case for it.
calibre-18 | nearby | They must compare the dedupe key `name` with `original_name` on line 376 and the hierarchical handling in `category_browse_search_expression`.
calibre-19 | line | Lines 784/790 guard with `not ranges`, but line 793 sets chunked on `compressible` alone, so compressed and ranged headers can coexist.
calibre-20 | input | They must try fractional seconds of 59.x to see that `min(abs(seconds), 59)` drops them.
calibre-21 | nearby | They must compare with `is_recipe_fmt()` in `cdb_add_book` (line 102), which the hard-coded two-item tuple at line 226 does not match.
calibre-22 | line | Unparenthesized `except A, B:` is a syntax error on sight.
calibre-23 | line | Line 759 tests `accept_ranges is not None` (True for `False`), while line 760 next to it uses truthiness.
calibre-24 | line | `self.method is HTTP1` compares the request method to a protocol constant.
calibre-25 | nearby | They must compare the second (count) loop with the first loop's `if not val: val = 'A'` fallback and imagine an empty sort value.
calibre-26 | input | They must try a close code of 5000 or above and know the valid range ends at 4999; line 418 has no upper bound.
calibre-27 | line | Line 331 passes `close_after_response=False` and returns before line 333 installs the header parser, so the unread headers are left in the stream.
calibre-28 | input | They must imagine a chunked body with trailer fields after the zero chunk.
calibre-29 | trace | They must follow `db.remove_extra_files` into the backend (`path_from_root(bookdir, relpath)`) to see that relpaths are not restricted to `data/`.
calibre-30 | nearby | They must compare line 582's hard-coded `HTTP11` with `simple_response` and the other senders, which use `self.response_protocol`.
calibre-31 | line | The loop binds `x` but calls `self.close(s, conn)` with a stale `s`.
calibre-32 | nearby | They must notice that the other decisions in `finalize_output` (755-759) are gated on `is_http1` but the chunked decision is not.
calibre-33 | input | They must try the boundary `total == start + num`; `>` instead of `>=` only shows there.
calibre-34 | nearby | They must compare with `send_not_modified` right below, which sends `Content-Length: 0`.
calibre-35 | nearby | They must know `add_sandbox_headers` exists in the same file and is applied to data files but not to `book_fmt`.
calibre-36 | input | They must try a negative hex size, which `int(..., 16)` accepts, and follow the running-counter arithmetic.
calibre-37 | trace | They must know that `ctx.search` applies the user's library restriction and `db.number_of_books_in_virtual_library` does not.
calibre-38 | nearby | They must compare the sanitization in `JobStatus.__init__` (line 46) with the raw `output_fmt` passed via `queue_job` (187) into `convert_book` (134).
calibre-39 | input | They must think of a custom column with rating datatype; the special case checks only `field == 'rating'`.
calibre-40 | trace | They must trace `rd.tdir` to learn it is the server-wide temp dir rather than per-request, then imagine two concurrent uploads.
calibre-41 | line | Lines 48-58 pop and reinsert the key, so `reversed()` hits the fresh entry first and breaks at once.
calibre-42 | input | They must play through a ban expiring and a later failure; line 49 reuses the old count with no age check.
calibre-43 | nearby | They must compare `create_file_copy`'s mtime-only cache test with `book_fmt`, where the plugboard feeds only the ETag.
calibre-44 | trace | They must find a caller (`manage_users_cli`) that mutates the nested dict returned by the shallow `.copy()` of an `lru_cache` result.
calibre-45 | line | Unparenthesized `except A, B:` is a syntax error on sight.
calibre-46 | trace | They must trace `rd.tdir`'s lifetime to know that the unremoved upload persists until shutdown.
calibre-47 | line | Line 111 joins `fdir, x`, and line 116 passes bare `x` to `safe_remove`.
calibre-48 | input | They must try a header line with no colon; `partition` then produces key = whole line, value empty, and the `if not key` check passes.
calibre-49 | line | `endswith('s')` is tested before `endswith('ms')`, so the ms branch is unreachable.
calibre-50 | line | `k.strip()` on line 190 accepts whitespace before the colon, which a reviewer who knows the header grammar flags on the line.
calibre-51 | input | They must imagine an HTTP/1.0 keep-alive request that carries `Transfer-Encoding`; the `HTTP11` gate on line 374 looks deliberate otherwise.
calibre-52 | line | Line 439 slices encoded UTF-8 bytes at a fixed 123-byte limit.
calibre-53 | line | Line 138 unpacks `brange.split('-', 1)` into two names without a guard.
calibre-54 | nearby | They must read the option's help text in opts.py ("Set to zero to disable") to see that 0 should mean "never group", not "always group".
calibre-55 | nearby | They must compare the fallback `'date'` with line 268, where the same default goes through `sanitize_sort_field_name` (and know `date` is not a field key).
calibre-56 | input | They must try `bytes=-0`; the suffix branch then builds an inverted range.
calibre-57 | nearby | They must compare with the `ctx.has_id` / allowed-id checks used by the other handlers, which are missing for `extra_books`.
calibre-58 | line | Line 239 compares the raw partition result `p == 'q'` without stripping, while `e` is stripped on 246.
calibre-59 | nearby | They must compare with `/fts/reindex` directly below, which has `methods=('POST',)`.
calibre-60 | input | They must try `bytes=--5`, where `int('-5')` yields a negative suffix length.
calibre-61 | line | Line 235 uses `job.name`, and line 239 in the same function uses `job.job_name`.
calibre-62 | line | Lines 396-399 show the Expect branch returning before `self.forwarded_for` is assigned.
calibre-63 | line | The request handling is dedented out of the `for line in inf` loop, and `req` can be unbound.
