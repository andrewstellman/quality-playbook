calibre-01 | input | Need to try a suffix range against a zero-length resource; the stop > content_length branch looks fine until content_length is 0.
calibre-02 | line | sort_q_values only sorts and never drops q=0 entries, and acceptable_encoding/preferred_lang take the first match; knowing that q=0 means "not acceptable" is enough.
calibre-03 | line | int(line.strip(), 16) on the whole chunk-size line clearly can't handle the `;ext` part HTTP allows.
calibre-04 | input | Need to picture copy_func raising after open_for_write; the happy path has no try/cleanup and nothing looks wrong without that failure case.
calibre-05 | input | Need to walk a folded header through commit(): the raw lines keep their CRLF, get lstripped only, and are joined with a space, and that only shows once you run an example.
calibre-06 | input | Need to know or try Python int(..., 16) quirks (0x prefix, sign, underscores); the parse call looks fine for ordinary hex.
calibre-07 | line | The stale-nonce path visibly falls through to the "Failed login attempt" log and ban_list.failed().
calibre-08 | trace | Need to follow Server.start in embedded.py into ServerLoop.serve_forever in loop.py to see initialize_socket() called a second time.
calibre-09 | nearby | Need to compare with other call sites where formats_added(...) is wrapped in ctx.notify_changes to see that the return value here is dropped.
calibre-10 | nearby | Need the opts.py help text ("Set to zero for no limit") to see that delta <= 0 treats 0 as "abort immediately".
calibre-11 | line | from_hex_unicode on a raw URL segment is unguarded, right next to a guarded int() parse of offset.
calibre-12 | nearby | Need to read finalize_headers in http_request.py (same connection class hierarchy), which set close_after_response from the request, to see simple_response overwrite it.
calibre-13 | line | `except KeyboardInterrupt, EOFError:` is invalid syntax before Python 3.14, visible on the line.
calibre-14 | trace | Need to follow the unsanitized x["name"] into db.add_extra_files in the cache layer to confirm nothing blocks `..` from leaving data/.
calibre-15 | line | Within the cited lines the first loop guards a falsy sort and the second calls .upper() on getattr(y, 'sort', y.name) with no guard.
calibre-16 | nearby | Need to see that GeneratedOutput sets content_length = None (same file), which the >= comparison doesn't allow for.
calibre-17 | nearby | Need the SMIL timing spec linked in the function's comment, where a bare number is a valid seconds value, to see that the else-raise is wrong.
calibre-18 | input | Need a hierarchy where two leaves share a display name to see that deduping on `name` rather than original_name merges them.
calibre-19 | input | Need to picture gzip plus Range on a compressible file: compression is skipped for ranges, but the `compressible or ...` chunked branch still fires.
calibre-20 | input | Need to try a fractional value like 59.5 to see that min(abs(seconds), 59) clamps legitimate sub-minute values.
calibre-21 | nearby | Need to compare with cdb_add_book in the same file, which uses is_recipe_fmt(), against this hardcoded two-item tuple.
calibre-22 | line | `except AttributeError, OSError:` is invalid syntax before Python 3.14, visible on the line.
calibre-23 | nearby | Need to see that dynamic_output/GeneratedOutput set accept_ranges = False (not None), so `is not None` is always true; line 760 right below uses truthiness.
calibre-24 | line | `self.method is HTTP1` compares the HTTP method with a protocol constant.
calibre-25 | line | Same asymmetry in the cited lines: the first loop maps a falsy sort to 'A', the counting loop doesn't.
calibre-26 | line | The close-code validity check has no upper bound (>= 5000), readable directly with RFC 6455 in mind.
calibre-27 | line | The parse_uri failure path explicitly passes close_after_response=False before the headers have been consumed.
calibre-28 | line | With last=True the separator reader demands exactly CRLF, which plainly leaves no room for trailers.
calibre-29 | trace | Need to follow relpaths into db.remove_extra_files to see it resolves them against the whole book directory, not data/.
calibre-30 | nearby | Need to compare with simple_response and the other senders, which use self.response_protocol where job_done hardcodes HTTP11.
calibre-31 | line | `for x, conn in close_needed: self.close(s, conn)` uses the stale loop variable s.
calibre-32 | nearby | Need to see that is_http1 guards compression and ranges elsewhere in finalize_output but not the chunked branch.
calibre-33 | input | Need to plug in start=1, num=25, total=26 to hit the off-by-one in `total > start + num` with 1-based start.
calibre-34 | nearby | Need to compare with send_not_modified right below, which includes Content-Length: 0.
calibre-35 | nearby | Need to see that add_sandbox_headers is applied at other file-serving endpoints in content.py but not in book_fmt.
calibre-36 | input | Need to try a signed chunk size like "-f4240" and follow the negative value through bytes_read.
calibre-37 | trace | Need to know that ctx.search applies the user's library restriction while db.number_of_books_in_virtual_library does not, across the context and db layers.
calibre-38 | nearby | Need to compare JobStatus's sanitized output_fmt with the raw conversion_data['output_fmt'] passed to convert_book in the same file.
calibre-39 | input | Need to think of a custom column whose datatype is rating; only field == 'rating' gets the stars-to-number branch.
calibre-40 | trace | Need to know that rd.tdir is the server-wide temp dir, passed down from the server loop, for the same-filename collision to matter.
calibre-41 | line | Iterating reversed(self.items) hits the just-inserted `now` entry first and breaks, readable in the loop.
calibre-42 | nearby | Need is_banned's interval logic just above to see that failed() reuses the old count without checking its age.
calibre-43 | nearby | Need to compare book_fmt with create_file_copy: extra_etag_data changes the ETag, but cache freshness is decided by mtime alone.
calibre-44 | nearby | Need to read parse_restriction (lru_cache, nested dict) together with restrictions() (.copy()) to see the shallow copy shares the nested dict.
calibre-45 | line | `except ValueError, UnicodeDecodeError:` is invalid syntax before Python 3.14, visible on the line.
calibre-46 | line | The upload is written to rd.tdir and nothing in the function removes it.
calibre-47 | line | safe_remove(x) uses the bare name, while the line above builds os.path.join(fdir, x).
calibre-48 | line | The partition result is used without checking that the colon separator was found.
calibre-49 | line | The endswith('s') branch is ordered before endswith('ms').
calibre-50 | line | k.strip() before the colon quietly accepts whitespace that HTTP forbids.
calibre-51 | input | Need to picture an HTTP/1.0 keep-alive request carrying Transfer-Encoding; the `is HTTP11` guard looks deliberate until then.
calibre-52 | line | reason[:123] slices already-encoded UTF-8 bytes and can cut a multibyte sequence.
calibre-53 | line | `start, stop = ... brange.split('-', 1)` is an unguarded two-value unpack.
calibre-54 | nearby | Need the opts.py help text ("Set to zero to disable" grouping) to see that `MAX_ITEMS > 0 and` inverts it.
calibre-55 | nearby | Need to see that the primary path sends 'date' through sanitize_sort_field_name while the fallback uses raw 'date'.
calibre-56 | input | Need to try `bytes=-0` to see the suffix branch produce an empty, inverted Range.
calibre-57 | trace | Need to know that book_as_json and the db don't enforce the library restriction, while search_result ids were already restricted.
calibre-58 | line | The parameter name p is never stripped while v is, so " q" fails the == 'q' test.
calibre-59 | nearby | Need to compare with sibling state-changing endpoints that pass methods={'POST'} (and know the endpoint default) to see that GET is allowed here.
calibre-60 | input | Need to try `bytes=--5` so split('-', 1) yields a negative stop that int() accepts.
calibre-61 | line | The callback error log uses job.name, while a few lines down the same function uses job.job_name.
calibre-62 | line | The Expect: 100-continue branch returns before self.forwarded_for is assigned.
calibre-63 | line | The try/response block is indented after the `for line in inf` loop instead of inside it.
