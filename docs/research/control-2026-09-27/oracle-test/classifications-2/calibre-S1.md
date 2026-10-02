calibre-01 | input | Run get_ranges with content_length 0 and `bytes=-5`, so `stop > content_length` falls into the `Range(0, -1, 0)` branch.
calibre-02 | nearby | Compare sort_q_values with its callers acceptable_encoding and preferred_lang, and know that q=0 means "not acceptable", to see that zero-weight entries are never filtered.
calibre-03 | input | Feed a chunk-size line such as `5;ext=1` to `int(line.strip(), 16)`, since the lines look fine until an extension is considered.
calibre-04 | input | Picture copy_func raising after open_for_write, so the partial file's new mtime makes the next request take the cache-hit branch.
calibre-05 | input | Feed a folded header (continuation line) through the parser and see that the join keeps the CRLF inside the value, because only the final strip removes line endings.
calibre-06 | input | Try `0x10`, `+a` or `1_0` in `int(x, 16)`, since Python's lenient int parsing is invisible in the code.
calibre-07 | nearby | Read the stale-nonce handling a few lines away and see that a valid-but-stale response falls through to the failed-login and ban path.
calibre-08 | nearby | Read ServerLoop.serve_forever in loop.py, which calls initialize_socket again, and compare it with Server.start.
calibre-09 | nearby | Compare with other callers of the changes module and see that the constructed event is never passed to `ctx.notify_changes`.
calibre-10 | input | Run the arithmetic with max_job_time = 0, where `delta <= 0` holds immediately for every job.
calibre-11 | input | Request an id that is not valid hex, because from_hex_unicode is unguarded in the handler.
calibre-12 | nearby | Compare with finalize_headers, which sets close_after_response from the Connection header just before simple_response overwrites it with its argument.
calibre-13 | line | `except A, B:` is the old unparenthesized form and is visibly wrong for the target Python version (the project's minimum Python matters here).
calibre-14 | trace | Follow `../` in the upload name through db.add_extra_files to see that nothing sanitizes the relative path.
calibre-15 | nearby | Compare line 598, which guards a falsy `sort`, with line 604, which uses `getattr(..., y.name).upper()` and so breaks when the attribute exists but is None.
calibre-16 | nearby | Compare with the GeneratedOutput class in the same file, whose content_length is None, against the `>=` comparison with an int.
calibre-17 | input | Call parse_smil_time('12.5') and see that the single-part branch requires a unit suffix.
calibre-18 | input | Feed hierarchical items `History.Military` and `Science.Military` into the dedup on display name.
calibre-19 | input | Send Accept-Encoding gzip together with a Range on a compressible file, so the `compressible` and `ranges` branches combine.
calibre-20 | input | Try `00:00:59.5` in the seconds clamp `min(abs(seconds), 59)` to see the fractional part lost.
calibre-21 | nearby | Compare with the `is_recipe_fmt` check in cdb_add_book, which covers more names than the hard-coded pair here.
calibre-22 | line | Same unparenthesized `except A, B:` form, wrong on inspection.
calibre-23 | nearby | Compare `output.accept_ranges is not None` on line 759 with the truthiness test on line 760, and know the classes that set accept_ranges = False.
calibre-24 | line | `self.method is HTTP1` compares an HTTP method string against a protocol constant, so it is always False.
calibre-25 | nearby | Compare the two loops, since the first maps an empty sort to 'A' but the second counts with `getattr(...).upper().startswith(x)`.
calibre-26 | input | Send a close code above 4999, because the range check has no upper bound (this also needs RFC 6455 knowledge).
calibre-27 | nearby | Compare with the other simple_response calls in parse_request_line, which close the connection, and note that the state does not advance to reading headers.
calibre-28 | input | Send a chunked request with a trailer after the zero chunk.
calibre-29 | trace | Follow db.remove_extra_files to see that nothing restricts relpaths to the data directory.
calibre-30 | nearby | Compare with the `response_protocol` uses around it, which contrast with the hard-coded HTTP11 in the status line.
calibre-31 | line | The loop unpacks `x, conn` but calls `self.close(s, conn)` with the stale `s`.
calibre-32 | nearby | Compare with the `not is_http1` guard on the compression path, which the chunked assignment lacks.
calibre-33 | input | Plug in start=1, num=25, total=26 and see the strict `>` on `start + num`.
calibre-34 | nearby | Compare with send_not_modified, which sets Content-Length: 0.
calibre-35 | nearby | Compare with other endpoints in content.py that call add_sandbox_headers.
calibre-36 | input | Send a negative hex chunk size such as `-f4240` and follow the counters.
calibre-37 | trace | Follow db.number_of_books_in_virtual_library to see it ignores the user's restriction while the empty-query branch uses the restricted count.
calibre-38 | nearby | Compare JobStatus's sanitized output_fmt with the raw value passed to convert_book in the same file.
calibre-39 | input | Search a custom rating column, where the `field == 'rating'` check never matches and the star string is used verbatim.
calibre-40 | input | Picture two concurrent uploads with the same filename sharing the same path in the server-wide tdir.
calibre-41 | line | `reversed(self.items)` hits the just-inserted newest entry first and breaks, so the pruning loop can never remove old ones.
calibre-42 | nearby | Compare with the is-banned check just above, which honours the interval, while `failed` reuses the old count with no age test.
calibre-43 | input | Change a plugboard without changing the book mtime, and see that the cache file name and mtime check ignore extra_etag_data.
calibre-44 | trace | Follow the cached dict returned by parse_restriction to a mutating caller such as manage_users_cli.
calibre-45 | line | Same unparenthesized `except A, B:` form, wrong on inspection.
calibre-46 | trace | Follow the lifetime of rd.tdir to see that nothing removes the uploaded file until server shutdown.
calibre-47 | line | `safe_remove(x)` uses the bare name, whereas line 111 in the same loop builds `os.path.join(fdir, x, ...)`.
calibre-48 | line | `partition(b':')` accepts a line with no colon and the code never checks that the separator was found.
calibre-49 | line | The `endswith('s')` branch precedes `endswith('ms')`, so the ordering is wrong on inspection.
calibre-50 | input | Send `Content-Length : 5`, which needs RFC 7230 knowledge that whitespace before the colon is forbidden.
calibre-51 | nearby | Note that `response_protocol` is `min((1,1), rp)` and is set a few lines earlier, so the TE check that uses it skips HTTP/1.0.
calibre-52 | input | Use a non-ASCII reason longer than 123 bytes and cut mid-sequence.
calibre-53 | line | The unpack `start, stop = ... brange.split('-', 1)` is unguarded against a spec with no `-`.
calibre-54 | nearby | Read the option definition in opts.py to learn what 0 means for max_opds_ungrouped_items, then compare with `MAX_ITEMS > 0`.
calibre-55 | nearby | Compare line 268, which sanitizes the sort field name, with the raw `'date'` fallback on line 272.
calibre-56 | input | Try `bytes=-0`, which takes the `elif stop` branch as a truthy string and yields a zero-length range.
calibre-57 | nearby | Compare with the search-result path in the same function, which is restricted, while extra_books goes straight to book_as_json.
calibre-58 | line | `p == 'q'` is unstripped while `v` is stripped, so `; q=` is misparsed.
calibre-59 | nearby | Compare with the neighbouring fts_reindex endpoint, which restricts `methods` to POST.
calibre-60 | input | Try `bytes=--5`, which takes `stop = '-5'` into the negative-subscript branch.
calibre-61 | nearby | Compare `job.name` on line 235 with `job.job_name` on line 239 in the same function.
calibre-62 | line | The `Expect: 100-continue` early return sits before the `forwarded_for` assignment, visible in the function order.
calibre-63 | line | The try block is dedented out of the `for` loop, and `req` is unbound if the loop never runs.
