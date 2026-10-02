# calibre, classifier S1 (Claude Sonnet), blind

### calibre-01
Oracle: RFC 7233 §2.1 defines a suffix-length range on a zero-length resource as unsatisfiable; get_ranges (http_response.py:157-159) treats any stop > content_length as "return the whole resource" without special-casing content_length==0, producing a nonsensical Range(0,-1,0) that is then sent as a 206.
Type: known-external
Confidence: high

### calibre-02
Oracle: RFC 7231 §5.3.1 states a qvalue of 0 means "not acceptable"; sort_q_values (utils.py:232-248) never filters q=0 entries out, and acceptable_encoding/preferred_lang (http_response.py:101-117) just take the first sorted entry regardless of q.
Type: known-external
Confidence: high

### calibre-03
Oracle: RFC 7230 §4.1.1 explicitly allows chunk extensions after `;` in a chunk-size line; read_chunk_length (http_request.py:426) does `int(line.strip(), 16)` on the whole line including the extension, so any chunk with an extension is rejected as invalid.
Type: known-external
Confidence: high

### calibre-04
Oracle: create_file_copy's own docstring ("make sure to only do this copy once... if there have been no changes") implies the cached file is only valid once copy_func fully completes; if copy_func raises after open_for_write (content.py:105-106), the exception propagates with `ans` never closed (resource leak) and the half-written file's fresh mtime makes the next request's `previous_mtime < mt` check false, so it gets served from "cache" as a complete 200 response.
Type: implicit
Confidence: high

### calibre-05
Oracle: RFC 7230 §3.2.4 requires obsolete line folding to be replaced with SP, not retained with embedded CRLF; HTTPHeaderParser.commit (http_request.py:186-193) joins raw lines (which still carry their trailing `\r\n`) with `b' '` and only `.strip()`s the outer ends of the combined value, leaving the internal CRLF intact — a header/response-splitting risk.
Type: known-external
Confidence: high

### calibre-06
Oracle: RFC 7230 §4.1 defines chunk-size as `1*HEXDIG` only; read_chunk_length (http_request.py:426) uses Python's `int(line.strip(), 16)`, which per Python's grammar also accepts a `0x` prefix, leading `+`, and `_` digit separators — all outside the wire grammar.
Type: known-external
Confidence: medium

### calibre-07
Oracle: RFC 7616 §3.3 (and RFC 2617 before it) treats a stale-nonce response to an otherwise-valid credential as a request to retry with a fresh nonce, not an authentication failure. do_http_auth (auth.py:297-303) computes `nonce_is_stale` after validating the password, but falls through to `log_msg = 'Failed login attempt...'` and `ban_list.failed(ban_key)` whenever nonce_is_stale is true, contradicting the log message's own wording (the login didn't fail).
Type: known-external
Confidence: high

### calibre-08
Oracle: embedded.py's `Server.start()` (line 95) calls `self.loop.initialize_socket()` directly, then spawns a thread running `serve_forever()`, which itself calls `self.initialize_socket()` again before `serve()` (loop.py:555-557). Since `pre_activated_socket` is None after the first call, the second call re-enters the `do_bind()` branch and overwrites `self.socket` without closing the first one.
Type: in-repo
Confidence: high

### calibre-09
Oracle: every sibling mutation endpoint in cdb.py (e.g. lines 123, 145, 163, 251) passes the change-event object it builds (`books_added(...)`, `metadata(...)`, etc.) into `ctx.notify_changes(...)`; conversion_status (convert.py:252) builds the same kind of event via `formats_added(...)` but never passes it to `ctx.notify_changes`, so the returned event is discarded.
Type: in-repo
Confidence: high

### calibre-10
Oracle: opts.py:80-81's own option description says "Set to zero for no limit" for max_job_time; update_max_block/abort_hanging_jobs (jobs.py:98, 198-224) instead compute `delta = self.max_job_time - (now - job.start_time)`, which is `<= 0` immediately when max_job_time is 0, aborting every job right after it starts — the opposite of "no limit."
Type: in-repo
Confidence: high

### calibre-11
Oracle: in the same functions, the `offset` query parameter is parsed inside a `try/except` that raises HTTPNotFound on failure (opds.py:657-660, 679-682, 706-709); `from_hex_unicode(which)`/`(category)` immediately below is not wrapped the same way, so a malformed hex id propagates an uncaught exception straight out of the handler.
Type: in-repo
Confidence: high

### calibre-12
Oracle: simple_response (http_response.py:468, `self.close_after_response = close_after_response`) sets the connection-keepalive flag purely from its caller-supplied default (True), ignoring the actual request's Connection header/HTTP version, unlike job_done's normal path which derives Connection handling from `self.close_after_response`/`self.response_protocol` together (http_response.py:568-574).
Type: in-repo
Confidence: medium

### calibre-13
Oracle: it raises — `except KeyboardInterrupt, EOFError:` (standalone.py:209) is Python 2 exception syntax, removed in Python 3; parsing this file under Python 3.14 raises `SyntaxError: multiple exception types must be parenthesized`.
Type: implicit
Confidence: high

### calibre-14
Oracle: add_extra_file (db/backend.py:2374-2379) resolves the relpath via `path_from_root(bookdir, relpath, ...)`, and path_from_root (utils/filenames.py:682-683) explicitly rejects any path component equal to `'..'` with `ValueError`, which add_extra_file catches and turns into a silent no-write (`return None`). A name of `../cover.jpg` under `data/` therefore cannot actually escape the `data/` subdir via this code path as described.
Type: in-repo
Confidence: low

### calibre-15
Oracle: the first loop in get_navcatalog (opds.py:596-599) explicitly guards `val = getattr(x, 'sort', x.name); if not val: val = 'A'` before using it, but the second loop three lines later (opds.py:602) calls `getattr(y, 'sort', y.name).upper()` with no such guard — since `sort` is present but `None` (not absent), getattr returns `None` and `.upper()` raises AttributeError.
Type: in-repo
Confidence: high

### calibre-16
Oracle: finalize_output (http_response.py:753) computes `output.content_length >= opts.compress_min_size`; for a GeneratedOutput (from a generator/iterable handler return) `content_length` is None, and `None >= int` raises TypeError whenever the content type is compressible/empty and status is 200.
Type: implicit
Confidence: high

### calibre-17
Oracle: the SMIL clock-value grammar cited in the code's own comment (render_book.py:289, linking SMIL3 §q22) allows a bare Timecount with no unit metric (defaulting to seconds); parse_smil_time's single-part branch (render_book.py:298-307) only recognizes explicit `s`/`ms`/`min`/`h` suffixes and raises ValueError for a plain number like `'12.5'`.
Type: known-external
Confidence: medium

### calibre-18
Oracle: category_browse_items' walk() (code.py:368-375) dedups purely on the leaf `name` field (`if name and ... and name not in seen`), with no path/parent component in the dedup key, so two hierarchical items with the same leaf label but different parents (`History.Military`, `Science.Military`) collide into one entry.
Type: in-repo
Confidence: high

### calibre-19
Oracle: finalize_output (http_response.py:759-760) computes `ranges` from `output.accept_ranges` independent of the `compressible` flag; when both are true for the same request, the function still hits `if compressible or output.content_length is None: outheaders.set('Transfer-Encoding','chunked')` (line ~789) as well as the `if ranges:` block that sets Content-Length and Content-Range (line ~792-796) — sending Transfer-Encoding and Content-Length together, which RFC 7230 §3.3.3 forbids.
Type: known-external
Confidence: high

### calibre-20
Oracle: the cited SMIL clock-value grammar permits a fractional seconds field up to (but not including) 60; parse_smil_time (render_book.py:294-299) clamps with `min(abs(seconds), 59)`, so any valid fractional value between 59 and 60 (e.g. `59.5`) is truncated to the integer 59, discarding the fraction and misrepresenting the timestamp.
Type: known-external
Confidence: medium

### calibre-21
Oracle: the sibling helper `is_recipe_fmt` in the same file (cdb.py:68-70) explicitly treats `'recipe'` and `'downloaded_recipe'` (with an `original_` prefix stripped) as forbidden; cdb_set_fields's inline check (cdb.py:226) instead hardcodes `fmt.lower() in ('recipe', 'original_recipe')`, missing `downloaded_recipe`/`original_downloaded_recipe` and not reusing the existing helper.
Type: in-repo
Confidence: high

### calibre-22
Oracle: it raises — `except AttributeError, OSError:` (loop.py:570) is Python 2 syntax; under Python 3.14 parsing raises `SyntaxError: multiple exception types must be parenthesized`.
Type: implicit
Confidence: high

### calibre-23
Oracle: finalize_output (http_response.py:759) computes `accept_ranges = not compressible and output.accept_ranges is not None and ...` — for GeneratedOutput/dynamic_output, `output.accept_ranges` is `False` (http_response.py:392, 411), and `False is not None` is True, so the header gets set even though the output type declares it does not support ranges.
Type: in-repo
Confidence: high

### calibre-24
Oracle: job_done (http_response.py:561) calls `finalize_output(output, data, self.method is HTTP1)`; `self.method` is the HTTP verb string ('GET'/'POST'/etc), never the HTTP1 sentinel, so this comparison is always False regardless of the actual request protocol — every other protocol check in the file correctly compares `self.response_protocol is HTTP1`/`HTTP11` (e.g. http_response.py:460, 477, 572).
Type: in-repo
Confidence: high

### calibre-25
Oracle: the first loop (opds.py:596-599) places any item with falsy `sort` (including `''`) into group `'A'` via the `if not val: val = 'A'` fallback; the second loop's count (opds.py:602) uses `getattr(y,'sort',y.name).upper().startswith(x)`, and for `sort=''` this is `''.upper().startswith('A')` which is False, so that item is never counted in any group despite being placed under 'A'.
Type: in-repo
Confidence: high

### calibre-26
Oracle: RFC 6455 §7.4.2 defines valid WebSocket close codes only up to 4999 (1000-2999 protocol-reserved, 3000-3999 registered, 4000-4999 private use); ws_control_frame's validation (web_socket.py:417) only checks `close_code < 1000`, membership in RESERVED_CLOSE_CODES, and `1011 < close_code < 3000`, leaving codes ≥5000 entirely unchecked and accepted.
Type: known-external
Confidence: high

### calibre-27
Oracle: parse_request_line (http_request.py:328-331) catches a failed `parse_uri` and calls `simple_response(e.http_code, ..., close_after_response=False)` before the header-reading state is ever entered; because the connection stays open and the header lines the client already sent were never consumed, the connection's state machine re-parses those bytes as a new request line.
Type: in-repo
Confidence: high

### calibre-28
Oracle: RFC 7230 §4.1.2 permits an optional trailer-part (trailer fields) between the last-chunk and the final CRLF; read_chunk_separator (http_request.py:449-450), used identically for both between-chunk CRLFs and the post-trailer terminator, rejects any line that isn't exactly `b'\r\n'` with a 400, so a legitimate trailer field is treated as a protocol error.
Type: known-external
Confidence: medium

### calibre-29
Oracle: remove_extra_files (db/backend.py:2324-2330) resolves `relpath` via `path_from_root(bookdir, relpath, ...)` against the whole book directory, not scoped to the `data/` subdirectory that the `/data-files/remove` endpoint (content.py:659-668) is meant to operate on, so a relpath of `cover.jpg`/`metadata.opf`/`<book>.epub` resolves to (and, called with `permanent=True`, deletes) the book's real cover/metadata/format file while the database still references it.
Type: in-repo
Confidence: high

### calibre-30
Oracle: every other status-line construction in this file uses `self.response_protocol` (http_response.py:472, 523, 533), but job_done's normal-response path (http_response.py:582) hardcodes the literal `HTTP11` instead, so the status line always reads HTTP/1.1 even for an HTTP/1.0 request.
Type: in-repo
Confidence: high

### calibre-31
Oracle: `self.close(s, conn)` in the close_needed loop (loop.py:615-616) uses `s`, which is unpacked from the earlier `for s, conn in remove:` loop and is stale by the time `close_needed` is iterated as `for x, conn in close_needed:` — `self.close` (loop.py:705-707) pops `connection_map[s]` and calls `conn.close()`, so the wrong map key is removed while the correct connection's socket is actually closed.
Type: in-repo
Confidence: high

### calibre-32
Oracle: `if compressible or output.content_length is None: outheaders.set('Transfer-Encoding','chunked')` (http_response.py:~789) is not gated by `is_http1` at all, unlike the `compressible`/`accept_ranges` computations a few lines above which explicitly `and not is_http1` (http_response.py:753-759); HTTP/1.0 has no chunked transfer coding (RFC 1945 has no such mechanism), so an HTTP/1.0 GeneratedOutput response still gets Transfer-Encoding: chunked.
Type: known-external
Confidence: high

### calibre-33
Oracle: build_navigation's Next/Last condition `if total > start + num:` (legacy.py:122) is off by one: with start=1, num=25, total=26, `26 > 26` is False, so no Next/Last link is generated even though book 26 (outside the current page) exists and is otherwise unreachable.
Type: in-repo
Confidence: high

### calibre-34
Oracle: send_range_not_satisfiable (http_response.py:521-528) builds its header buffer without a Content-Length entry and never sets `close_after_response`, unlike simple_response which always includes Content-Length (http_response.py:472) — RFC 7230 §3.3.2/§3.3.3 requires a length-carrying response to declare its length (or use another framing mechanism) so the recipient knows when the message ends on a persistent connection.
Type: known-external
Confidence: medium

### calibre-35
Oracle: two sibling inline-serving code paths in the same file call `add_sandbox_headers(...)` before serving content inline (content.py:526, 593), matching the function's own docstring purpose ("Prevent user supplied content that is rendered inline by the browser from being able to script the server's origin," content.py:200-204); book_fmt (content.py:223-265), which also supports `content_disposition=inline` for arbitrary book formats including HTML/XHTML/SVG, never calls it.
Type: in-repo
Confidence: high

### calibre-36
Oracle: RFC 7230 §4.1 defines chunk-size as unsigned hex digits only (no sign); read_chunk_length (http_request.py:426) does `int(line.strip(), 16)`, which Python happily parses with a leading `-` into a negative int, and that negative value is then added into `bytes_read[0]` (http_request.py:443) and used to compute `end = buf.tell() + chunk_size` (http_request.py:436), corrupting the running body-size accounting used for the `max_request_body_size` check.
Type: known-external
Confidence: high

### calibre-37
Oracle: handler.py's `Context.search` (handler.py:169-171) computes `restrict_to_ids` via `get_effective_book_ids`, which folds in both `vl` and the user's per-library restriction, and that's what populates `total_num` for the empty-query branch; search_result's non-empty-query branch (ajax.py:554) instead calls `db.number_of_books_in_virtual_library(vl)`, which only applies `vl` and ignores the user restriction — a different (unrestricted) count leaks through `num_books_without_search` whenever a query is present.
Type: in-repo
Confidence: high

### calibre-38
Oracle: JobStatus.__init__ (convert.py:46) sanitizes `output_fmt` with `.replace('/', '').replace('\\', '')` before building `self.output_path`, explicitly commented "sanitize output_fmt to prevent path traversal," but `queue_job` (convert.py:134, 187) passes the raw, unsanitized `conversion_data['output_fmt']` as an argument to the separate worker's `convert_book`, which computes `os.path.abspath('output.' + output_fmt.lower())` with no sanitization at all, allowing `../../../../tmp/x.epub` to resolve outside the job's temp directory.
Type: in-repo
Confidence: high

### calibre-39
Oracle: category_browse_search_expression only special-cases the built-in field by name — `if field == 'rating':` (code.py:337, 342-344) — converting the star-glyph display name into a numeric `rating:{stars}` search; a custom column of datatype 'rating' has a different `field` (its lookup key, e.g. `#mycol`) so it falls through to the generic branch (code.py:351) and embeds the raw star-glyph string in a quoted comparison, which the search parser then rejects as "Non-numeric value in query."
Type: in-repo
Confidence: high

### calibre-40
Oracle: cdb_add_book (cdb.py:107) writes the uploaded file to `os.path.join(rd.tdir, sfilename)`; `rd.tdir` is the single server-wide TemporaryDirectory created once in ServerLoop.serve (loop.py:537) and handed to every connection (loop.py:723), not a per-request directory, so two concurrent uploads with the same sanitized filename collide on the same path.
Type: in-repo
Confidence: high

### calibre-41
Oracle: BanList.failed's pruning loop (auth.py:52-58) does `self.items.pop(key, None)` then reinserts the same key at the end before iterating `reversed(self.items)`, so the very first entry reached is the one just stored with `previous_fail == now`; `now - previous_fail` is 0, which is not `> self.interval`, so the loop hits `break` on its first iteration and never prunes any older entry.
Type: in-repo
Confidence: high

### calibre-42
Oracle: `failed()` (auth.py:48-51) computes `fail_count = 0 if x is None else x[1]`, carrying forward the previous fail count for a key with no check on how long ago it was recorded or whether an earlier ban already expired; combined with the pruning bug (calibre-41) that never actually removes stale entries, `self.max_failures_before_ban`-worth of accumulated failures over any span of time keeps the key banned/re-bannable indefinitely, contrary to what the `ban_time_in_minutes`/sliding-window naming implies.
Type: in-repo
Confidence: high

### calibre-43
Oracle: create_file_copy's cache-reuse decision (content.py:88, `previous_mtime < mt`) depends only on the book file's mtime, never on `extra_etag_data`; book_fmt (content.py:228-243) recomputes `extra_etag_data = repr(cpb)` fresh from the current plugboard on every call and passes it only to `filesystem_file_with_custom_etag` (content.py:121) for the ETag, so a plugboard change with no mtime change serves the old cached body under a new ETag that doesn't match it.
Type: in-repo
Confidence: high

### calibre-44
Oracle: parse_restriction is `@lru_cache`d (users.py:29) and `UserManager.restrictions` (users.py:236) returns only a shallow `.copy()` of it, so `r['library_restrictions']` is the same nested dict object shared by every cache hit; manage_users_cli.py mutates that nested dict in place (`r['library_restrictions'][library] = plr` / `.pop(library, None)`, manage_users_cli.py:430,432), so the edit is visible to every other user whose stored restriction string produced the same cache key.
Type: in-repo
Confidence: high

### calibre-45
Oracle: it raises — `except ValueError, UnicodeDecodeError:` (content.py:358) is Python 2 syntax; under Python 3.14 parsing raises `SyntaxError: multiple exception types must be parenthesized`.
Type: implicit
Confidence: high

### calibre-46
Oracle: cdb_add_book (cdb.py:107-119) writes the upload to `rd.tdir` (and any import-plugin output alongside it) but there is no corresponding cleanup call anywhere in the function after `db.add_books` succeeds or fails; since `rd.tdir` is the server-wide temp dir (per calibre-40's trace) rather than a per-request one that gets torn down, these files simply accumulate until server shutdown.
Type: implicit
Confidence: high

### calibre-47
Oracle: the line directly above in the same function computes `os.path.join(fdir, x, 'calibre-book-manifest.json')` to check the mtime, but `safe_remove(x)` (books.py:116) is called with the bare `x` (an `os.listdir` entry), never joined with `fdir`, so it resolves relative to the process's current working directory instead of the intended `srvb/f/<x>` path.
Type: in-repo
Confidence: high

### calibre-48
Oracle: HTTPHeaderParser.commit (http_request.py:189-193) only raises when the parsed key is empty (`if not key: raise ValueError(...)`); a line with no colon at all makes `k` equal to the whole line and `v` empty via `line.partition(b':')`, and since `k.strip()` is non-empty this passes the check and is accepted as a header with an empty value, though RFC 7230's header-field grammar requires a field-name followed by a colon.
Type: known-external
Confidence: medium

### calibre-49
Oracle: parse_smil_time's single-part branch checks `x.endswith('s')` before `x.endswith('ms')` (render_book.py:299-301); since `'500ms'` also ends with `'s'`, it matches the first branch and evaluates `float(x[:-1])` = `float('500m')`, which raises ValueError instead of reaching the correct millisecond branch.
Type: in-repo
Confidence: high

### calibre-50
Oracle: RFC 7230 §3.2.4 states a server MUST reject a request containing whitespace between a header field-name and the colon (to prevent request-smuggling ambiguity); HTTPHeaderParser.commit (http_request.py:189-190) partitions on the first `:` and then `.strip()`s the key, silently accepting `Content-Length : 5` as header `Content-Length`.
Type: known-external
Confidence: high

### calibre-51
Oracle: finalize_headers (http_request.py:373-381) only inspects `Transfer-Encoding` inside `if self.response_protocol is HTTP11:`; for an HTTP/1.0 request `te` stays empty regardless of an actual Transfer-Encoding header, so the Transfer-Encoding/Content-Length conflict check is skipped and `chunked_read` stays False, causing the chunked body bytes on the wire to be left unread and then misparsed as the next request — the classic request-smuggling pattern RFC 7230 §3.3.3 is designed to prevent.
Type: known-external
Confidence: high

### calibre-52
Oracle: RFC 6455 §7.4.1 requires the Close frame's Reason to be valid UTF-8 text; websocket_close (web_socket.py:439) truncates with a byte-count slice `reason[:123]` with no awareness of UTF-8 character boundaries, which can split a multi-byte sequence and produce an invalid-UTF-8 reason.
Type: known-external
Confidence: high

### calibre-53
Oracle: it raises — get_ranges (http_response.py:138) does `start, stop = (x.strip() for x in brange.split('-', 1))`, and for a range spec with no `-` (`bytes=5`) `brange.split('-', 1)` yields a single-element list, so the two-target unpack raises `ValueError: not enough values to unpack`, propagating out as a 500 instead of being treated as an unparseable Range header.
Type: implicit
Confidence: high

### calibre-54
Oracle: opts.py:105's own description says "Set to zero to disable" grouping for max_opds_ungrouped_items; get_navcatalog's condition `if MAX_ITEMS > 0 and len(items) <= MAX_ITEMS:` (opds.py:589) means MAX_ITEMS=0 makes this always False, so every category is always grouped — the opposite of "disable."
Type: in-repo
Confidence: high

### calibre-55
Oracle: sanitize_sort_field_name (db/view.py:17-21) maps only 'title'/'authors' specially and otherwise passes the field through `search_term_to_field_key` unchanged; the actual db field key for date-added is `'timestamp'`, not `'date'` (db/cache.py uses `self.fields['timestamp']` throughout, e.g. cache.py:419, 3042), so multisort's fallback `sort_by = 'date'` (legacy.py:271-272) itself raises inside `self.fields['date']` and, since that second call isn't wrapped in its own try/except, the exception propagates as a 500.
Type: in-repo
Confidence: high

### calibre-56
Oracle: RFC 7233 §2.1's suffix-range semantics for `bytes=-N` require N>0 (a suffix length of zero bytes describes nothing satisfiable); get_ranges (http_response.py:152-161) treats the string `'0'` as truthy in `elif stop:` and computes `Range(content_length - 0, content_length - 1, 0)`, i.e. start > stop, which is then rendered as `Content-Range: bytes 100-99/100` with `Content-Length: 0` — an internally contradictory range.
Type: known-external
Confidence: high

### calibre-57
Oracle: `ans['search_result']['book_ids']` is populated via a search that already applies the user's access restriction (per handler.py's `get_effective_book_ids`, same mechanism traced for calibre-37), but `extra_books` (code.py:456-459) is parsed straight from the raw `extra_books` query parameter and iterated (code.py:459-464) with no restriction check at all before calling `book_as_json(db, book_id)` (metadata.py:72-90), which itself performs no access check either.
Type: in-repo
Confidence: high

### calibre-58
Oracle: sort_q_values' item() parser (utils.py:237-241) does `p, v = r.partition('=')[::2]` without stripping `p`, so `' q'` (from `fr; q=0.5`) never equals the literal `'q'`, silently falling back to the default `q = 1.0` instead of the intended 0.5 — visible directly by tracing the given example.
Type: in-repo
Confidence: high

### calibre-59
Oracle: the sibling endpoint fts_reindex in the same file explicitly restricts itself to `methods=('POST',)` (fts.py:85) for a state-changing operation; fts_disable (fts.py:77) has `needs_db_write=True` but no `methods=` override, so it falls back to `default_methods = frozenset(('HEAD','GET'))` (routes.py:28), letting a plain GET (or even a prefetch/CSRF-style `<img>` request) disable full-text search — contrary to RFC 7231 §4.2.1's requirement that GET be a safe method.
Type: known-external
Confidence: high

### calibre-60
Oracle: get_ranges' negative-suffix branch (http_response.py:152-161) parses `stop = int('-5') = -5` from `bytes=--5` and computes `Range(content_length - (-5), content_length - 1, -5)` = `Range(105, 99, -5)` with no validation that the parsed suffix length is non-negative, producing `Content-Length: -5` and `Content-Range: bytes 105-99/100`, both of which are malformed under RFC 7233's range-spec grammar (which permits only a non-negative decimal suffix-length).
Type: known-external
Confidence: high

### calibre-61
Oracle: `Job` subclasses `Thread` and sets the thread's `name` to `f'JobsMonitor{start_event.job_id}'` while storing the human-readable name separately as `self.job_name` (jobs.py:24-27); job_finished's callback-error log (jobs.py:234) references `job.name` (the Thread name) while the adjacent traceback-failure log three lines later (jobs.py:238) correctly uses `job.job_name`.
Type: in-repo
Confidence: high

### calibre-62
Oracle: finalize_headers (http_request.py:396-399) returns early for `Expect: 100-continue` requests via `return self.set_state(...)` before reaching `self.forwarded_for = inheaders.get('X-Forwarded-For')`, the very next line for every other request — directly visible from the function's control flow.
Type: in-repo
Confidence: high

### calibre-63
Oracle: handle_quicklook_client's `try/except` request-handling block (render_book.py:902 onward) is indented at the same level as, not inside, the preceding `for line in inf:` loop (render_book.py:902-906), so it only runs once after the loop exhausts all input (i.e. after the client's write side closes) using whichever `req` the loop last assigned; if the loop body never executes at all, `req` is referenced unassigned in the except block, which is an UnboundLocalError.
Type: implicit
Confidence: high

---

Hardest to classify: **calibre-14** was the hardest, because tracing `add_extra_file` → `path_from_root` showed the code actually rejects `..` path components, seemingly contradicting the finding as stated — I classified it in-repo/low rather than assuming the finding was simply correct. **calibre-17** and **calibre-20** (SMIL clock-value parsing) were hard because my confidence in the exact SMIL3 grammar (whether a bare number is valid, the precise upper bound for the seconds field) is real but not certain enough to call "high" — I know the shape of the spec but would want to check it against the actual grammar to be sure. **calibre-34** was ambiguous on how strong an oracle "should send Content-Length" is for a 416 response with no body, since RFC 7230 allows some framing flexibility; I settled on medium rather than high. Findings resting on cross-file tracing (calibre-37, 38, 40, 44, 55, 57) took the most code-reading to pin down but were unambiguous once the call chain was followed, so confidence there was high despite the effort.
