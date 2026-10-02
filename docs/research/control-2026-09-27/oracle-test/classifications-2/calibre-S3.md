calibre-01 | input | Reviewer must try a zero-length resource with a suffix range to see Range(0, -1, 0) come out.
calibre-02 | nearby | Reviewer must compare sort_q_values, which clamps q but never filters q=0, with its callers acceptable_encoding and preferred_lang, and know that q=0 means "not acceptable".
calibre-03 | input | Reviewer must think of a chunk extension like `5;x=y` and run it through int(line.strip(), 16).
calibre-04 | nearby | Reviewer must read create_file_copy's write/copy/cleanup flow and see there is no cleanup or close on a copy_func exception.
calibre-05 | input | Reviewer must feed a folded header and notice that lstrip keeps the CRLF before b' '.join.
calibre-06 | input | Reviewer must know that Python's int(..., 16) accepts `0x`, `+` and `_`, and try such input.
calibre-07 | nearby | Reviewer must read the surrounding Digest branch and see that the stale-nonce path falls through to the failed-login log and ban.
calibre-08 | trace | Reviewer must follow Server.start in embedded.py into ServerLoop.serve_forever in loop.py and see both call initialize_socket.
calibre-09 | nearby | Reviewer must compare with other formats_added and notify_changes call sites and see the result here is discarded.
calibre-10 | input | Reviewer must consider max_job_time=0 and evaluate the delta and max_block arithmetic.
calibre-11 | input | Reviewer must send a non-hex id, or know that from_hex_unicode raises, to see the unhandled exception.
calibre-12 | nearby | Reviewer must compare simple_response's close_after_response parameter with how callers and the parsed Connection state set the flag.
calibre-13 | line | The `except A, B:` form is unparenthesized on inspection (valid only on Python 3.14+).
calibre-14 | input | Reviewer must think of a `../` name and follow it through the path join.
calibre-15 | input | Reviewer must realise that getattr's default doesn't apply when the attribute exists with value None, and consider formats/identifiers.
calibre-16 | nearby | Reviewer must know from the GeneratedOutput class that content_length can be None, then see the unguarded comparison in finalize_output.
calibre-17 | line | The single-part branch has no case for a bare number and falls to the raise.
calibre-18 | nearby | Reviewer must compare the dedupe key with how hierarchical category items are identified elsewhere in the file.
calibre-19 | input | Reviewer must combine gzip and Range on a compressible file and trace the flag interplay in the header-setting code.
calibre-20 | line | The min(abs(seconds), 59) clamp on a float seconds field is wrong on inspection.
calibre-21 | nearby | Reviewer must compare against is_recipe_fmt in the sibling cdb_add_book and see the narrower list here.
calibre-22 | line | Unparenthesized multi-exception except, as in 13.
calibre-23 | nearby | Reviewer must read the output classes to see accept_ranges = False, and note that the finalize_output check (`is not None`) doesn't match it.
calibre-24 | nearby | Reviewer must compare `self.method is HTTP1` with the response_protocol comparisons a few lines away in the same class.
calibre-25 | line | The first loop maps an empty sort to 'A' while the second re-reads the raw value, visible within the cited lines.
calibre-26 | nearby | Reviewer must compare the accepted close-code range with the WebSocket spec's valid ranges.
calibre-27 | nearby | Reviewer must compare this simple_response call's close_after_response=False with how other early errors in the parser handle the connection.
calibre-28 | input | Reviewer must think of a chunked request with trailers and trace the final-chunk state.
calibre-29 | input | Reviewer must try relpaths naming the book's own files, since there is no restriction on what may be removed.
calibre-30 | line | HTTP11 is hard-coded in the status line even though response_protocol exists.
calibre-31 | line | The loop variable is `x` but the body uses the stale `s`.
calibre-32 | line | Chunked is set whenever content_length is None, ignoring the is_http1 argument, visible in the cited block.
calibre-33 | input | Reviewer must run the boundary values start=1, num=25, total=26 through the `total > start + num` condition.
calibre-34 | nearby | Reviewer must compare send_range_not_satisfiable with the other response helpers, which set Content-Length.
calibre-35 | nearby | Reviewer must compare inline content disposition handling with where add_sandbox_headers is applied.
calibre-36 | input | Reviewer must try a negative hex chunk size and follow the running byte counter.
calibre-37 | trace | Reviewer must follow number_of_books_in_virtual_library into the db layer to see it ignores the restriction.
calibre-38 | trace | Reviewer must follow output_fmt from the request through JobStatus and queue_job into convert_book's path construction.
calibre-39 | trace | Reviewer must follow the generated search expression into the rating query parser to see why it fails.
calibre-40 | input | Reviewer must picture two concurrent uploads of the same filename sharing the server-wide tdir.
calibre-41 | input | Reviewer must simulate the dict order and reversed() iteration to see the loop breaks immediately on the newest entry.
calibre-42 | input | Reviewer must think about a key that failed long ago and see the count is never aged.
calibre-43 | trace | Reviewer must follow the cache key and validity check across create_file_copy and book_fmt and consider a plugboard change.
calibre-44 | trace | Reviewer must connect the lru_cache in users.py, the shallow copy, and the mutation in manage_users_cli.py.
calibre-45 | line | Unparenthesized multi-exception except, as in 13.
calibre-46 | trace | Reviewer must follow the tdir lifecycle to learn that nothing removes the uploaded file until shutdown.
calibre-47 | line | The next line in the same block builds the full path with os.path.join, but safe_remove(x) is passed the bare name.
calibre-48 | input | Reviewer must try a header line with no colon and see that partition gives an empty value which is accepted.
calibre-49 | line | The `endswith('s')` check precedes the `endswith('ms')` check, so 'ms' never reaches its own branch.
calibre-50 | input | Reviewer must try whitespace before the colon and see that k.strip() hides it.
calibre-51 | nearby | Reviewer must compare the HTTP11-only Transfer-Encoding gate with the request-protocol handling elsewhere in finalize_headers.
calibre-52 | input | Reviewer must try a multibyte reason longer than 123 bytes and see the byte slice split a UTF-8 sequence.
calibre-53 | line | The two-value unpack of brange.split('-', 1) is unguarded.
calibre-54 | input | Reviewer must consider a limit of 0 and evaluate the comparison.
calibre-55 | nearby | Reviewer must compare the fallback 'date' with the valid sort keys defined elsewhere in legacy.py.
calibre-56 | input | Reviewer must try `bytes=-0` and follow it through the negative-subscript branch.
calibre-57 | nearby | Reviewer must compare with the restriction checks other endpoints apply before returning book data.
calibre-58 | input | Reviewer must try `fr; q=0.5` and see that p is unstripped so the comparison with 'q' fails.
calibre-59 | nearby | Reviewer must compare fts_disable's route options with the other state-changing endpoints, which restrict methods.
calibre-60 | input | Reviewer must try `--5` and see that int('-5') passes through the negative branch.
calibre-61 | nearby | Reviewer must read the Job class to see that `name` is the thread name and `job_name` is the display name.
calibre-62 | line | The early return for 100-continue precedes the forwarded_for assignment, visible in the cited lines.
calibre-63 | line | The processing block is dedented outside the for loop, visible on inspection.
