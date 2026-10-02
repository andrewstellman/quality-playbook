calibre-01 | input | Run `bytes=-5` against a zero-length resource and see that the suffix branch returns `Range(0, -1, 0)` instead of a 416.
calibre-02 | input | Try `Accept-Encoding: gzip;q=0, identity` and see that a q of 0 is clamped and kept rather than dropped.
calibre-03 | input | Feed a chunk-size line with an extension such as `5;ext=v`, which the RFC allows, and see that `int(line.strip(), 16)` rejects it.
calibre-04 | input | Make `copy_func` raise midway and see that the already-created cache file has a fresh mtime, so later requests treat it as a valid cache hit.
calibre-05 | input | Run a folded header through the parser and see that `b' '.join` leaves the inner CRLF in the value.
calibre-06 | input | Try `0x10`, `+a` or `1_0` and know that Python's `int(x, 16)` accepts them, unlike strict hex chunk sizes.
calibre-07 | line | Lines 297-303 show that a valid digest with a stale nonce falls through to the unconditional "Failed login" log and `ban_list.failed()`.
calibre-08 | trace | Notice that `initialize_socket()` is called in `embedded.py` `start()` and again inside `loop.serve_forever()`, which lives in another file.
calibre-09 | line | `formats_added(...)` is a bare expression whose result is discarded, unlike the `ctx.notify_changes(..., books_added(ids))` call in `cdb.py`.
calibre-10 | nearby | Read the `max_job_time` help text in `opts.py` ("zero for no limit") and compare it with the `delta <= 0` logic in `jobs.py`.
calibre-11 | input | Send a non-hex id such as `zz` and know that `from_hex_unicode` raises with no handler around it.
calibre-12 | trace | Follow how `finalize_headers` in `http_request.py` sets `close_after_response`, and see that `simple_response` in `http_response.py` then overwrites it.
calibre-13 | line | The bare `except A, B:` form is visible on inspection, and it fails to parse on Python versions before 3.14.
calibre-14 | trace | See that `x["name"]` goes into the relpath unsanitised, then follow it into `db.add_extra_files` to learn whether it can escape the data directory.
calibre-15 | nearby | Compare line 604 with lines 598-601, where the earlier loop guards falsy `sort` values and this one does not.
calibre-16 | nearby | `GeneratedOutput` can have `content_length` None, as line 793 already tests, so the `>=` comparison at line 755 fails for it.
calibre-17 | nearby | Compare the function with the SMIL clock-value spec linked in its comment, which allows a bare number, and see that no branch handles one.
calibre-18 | input | Build hierarchical items `History.Military` and `Science.Military` and see that both have the leaf name `Military`, so the dedupe on `name` merges them.
calibre-19 | input | Send `Accept-Encoding: gzip` together with a `Range` header and follow the `compressible`, `ranges` and `Transfer-Encoding` logic through to the mixed headers.
calibre-20 | line | The `min(abs(seconds), 59)` clamp on the seconds field is wrong on its face, since fractional seconds below 60 are valid.
calibre-21 | nearby | Compare line 226 with the `is_recipe_fmt(fmt)` check in `cdb_add_book` in the same file, which covers more variants.
calibre-22 | line | The bare `except AttributeError, OSError:` is visible on inspection, and it fails to parse on Python versions before 3.14.
calibre-23 | nearby | Compare line 759, which tests `accept_ranges is not None`, with line 760, which tests truthiness, and know that `dynamic_output` sets it to False.
calibre-24 | line | `self.method is HTTP1` compares an HTTP verb string to a protocol constant, so it is never true.
calibre-25 | nearby | Compare the first loop's `if not val: val = 'A'` with the second loop, which does no equivalent normalisation before `startswith(x)`.
calibre-26 | input | Send a close code of 5000 and see that the range check stops at 3000 and does not reject codes above 4999.
calibre-27 | nearby | Compare the `parse_uri` failure path, which passes `close_after_response=False`, with the other early error returns, and see that the headers are never consumed.
calibre-28 | input | Send a chunked body with a trailer after the zero chunk and see that anything other than a bare CRLF returns 400.
calibre-29 | nearby | Compare `remove_data_files`, which passes relpaths straight to `remove_extra_files`, with `get_data_file`, which filters by `DATA_FILE_PATTERN`.
calibre-30 | nearby | Compare the hardcoded `HTTP11` in the status line at line 582 with `self.response_protocol` used by `simple_response` and the other response builders.
calibre-31 | line | The loop unpacks `x, conn` but calls `self.close(s, conn)` with a stale `s`.
calibre-32 | input | Send an HTTP/1.0 request whose output has unknown length and see that line 793 sets chunked encoding without checking `is_http1`.
calibre-33 | input | Work through `start=1, num=25, total=26` and see that `total > start + num` hides the Next link when one book remains.
calibre-34 | nearby | Compare `send_range_not_satisfiable` with `send_not_modified` and `simple_response`, which set `Content-Length`, and see that it omits one on a kept-alive connection.
calibre-35 | nearby | See that `add_sandbox_headers` and `needs_sandboxing` are defined in `content.py` but `book_fmt` never calls them for inline disposition.
calibre-36 | input | Send a negative chunk size such as `-f4240` and follow how it changes the running byte counter.
calibre-37 | trace | Know that `number_of_books_in_virtual_library` is not subject to the user's restriction while `ctx.search` is, which means reading the db layer and the context.
calibre-38 | nearby | Compare the sanitised `output_fmt` in `JobStatus` with the raw value passed to `convert_book`, both in `convert.py`.
calibre-39 | trace | Learn how custom rating columns present their items in the category data, and how `category_browse_search_expression` receives `field`.
calibre-40 | trace | Know that `rd.tdir` is a server-wide temp dir shared across requests, and see that the upload path uses only the filename.
calibre-41 | line | `reversed(self.items)` on an insertion-ordered dict reaches the just-inserted newest entry first, so `break` fires immediately.
calibre-42 | nearby | Compare `failed()`, which reuses the old count, with `is_banned()` and its interval semantics, and see that old failures are never aged out.
calibre-43 | input | Change a plugboard without changing the book's mtime and see that the cache key (mtime-based filename) ignores `extra_etag_data`.
calibre-44 | trace | Follow `lru_cache`-shared dicts from `users.py` `restrictions()` into `manage_users_cli.py`, which mutates them.
calibre-45 | line | The bare `except ValueError, UnicodeDecodeError:` is visible on inspection, and it fails to parse on Python versions before 3.14.
calibre-46 | trace | Follow the lifetime of `rd.tdir` and the import-plugin output file to see that nothing deletes them per request.
calibre-47 | nearby | Compare `safe_remove(x)` on line 116 with the joined path built at line 111.
calibre-48 | line | `partition(b':')` with no colon yields an empty value and the code never checks that a colon was present.
calibre-49 | line | `endswith('s')` is tested before `endswith('ms')`, so `500ms` never reaches the `ms` branch.
calibre-50 | input | Send `Content-Length : 5` and know that RFC 7230 forbids whitespace before the colon, while the code strips it.
calibre-51 | input | Send an HTTP/1.0 request with `Transfer-Encoding: chunked` and see that the `response_protocol is HTTP11` guard skips it.
calibre-52 | input | Use a multibyte reason string and see that the byte slice `[:123]` can cut a UTF-8 sequence.
calibre-53 | line | `start, stop = (x.strip() for x in brange.split('-', 1))` is an unguarded unpack that fails when there is no `-`.
calibre-54 | nearby | Compare the `opts.py` help ("Set to zero to disable") with `MAX_ITEMS > 0 and ...`, whose else branch groups everything.
calibre-55 | nearby | See that `'date'` is used as a `multisort` key in the fallback, while the sort fields elsewhere come from field metadata and `'date'` may not be one.
calibre-56 | input | Send `bytes=-0` and see that the suffix branch treats `stop=0` as a valid range of size 0.
calibre-57 | trace | See that `extra_books` skips the restriction check that `search_result` applies, which means knowing `book_as_json` does not enforce it.
calibre-58 | line | `p` is compared to `'q'` without `.strip()` while `v` is stripped, so `q` preceded by whitespace is not recognised.
calibre-59 | nearby | Compare `fts_disable` with the sibling `fts_reindex`, which restricts `methods=('POST',)`, to see that disable is a state change reachable by GET.
calibre-60 | input | Send `bytes=--5` and see that `int('-5')` slips through the suffix branch and produces a negative size.
calibre-61 | nearby | Compare `job.name` at line 235 with `job.job_name` at line 239 of the same function.
calibre-62 | line | The early `return` on `Expect: 100-continue` comes before `self.forwarded_for = ...` on the next lines.
calibre-63 | line | The `try/except` and response block are dedented out of the `for line in inf` loop, and `req` is only bound inside it.
