# calibre, classifier S2 (Claude Sonnet), blind

### calibre-01
Oracle: Per RFC 7233 §2.1, a suffix-byte-range-spec selects the last N bytes of the representation; for a zero-length resource there is nothing to select, so the range is unsatisfiable — it should not produce a satisfiable `Range(0,-1,0)` that triggers a 206.
Type: known-external
Confidence: medium

### calibre-02
Oracle: RFC 7231 §5.3.1 defines `q=0` as "not acceptable" for that value; `sort_q_values` (utils.py:232-248) never filters q=0 entries, so callers that just take the top of the sorted list treat a rejected encoding/language as acceptable.
Type: known-external
Confidence: high

### calibre-03
Oracle: RFC 7230 §4.1's chunked-encoding grammar (`chunk = chunk-size [ chunk-ext ] CRLF`) explicitly allows chunk extensions after `;`; `read_chunk_length` (http_request.py:426) feeds the whole line including the extension straight into `int(line, 16)`, so a syntactically valid chunk line is rejected as "not a valid chunk size".
Type: known-external
Confidence: high

### calibre-04
Oracle: `create_file_copy`'s own docstring ("we make sure to only do this copy once... if there have been no changes") assumes the copy either fully succeeds or isn't cached; there's no try/except around `copy_func(ans)` (content.py:105-116), so a mid-write failure leaves a partial file with a fresh mtime that the next request's `previous_mtime < mt` check treats as valid and serves with 200, and `ans` is never closed.
Type: in-repo
Confidence: medium

### calibre-05
Oracle: RFC 7230 §3.2.4 requires a server that unfolds an obsolete line-fold to replace it with SP, producing a field-value with no embedded CR/LF; `HTTPHeaderParser.commit` (http_request.py:186-213) joins raw, un-stripped lines with `b' '.join`, so the interior CRLF from the original wire line survives into the stored header value.
Type: known-external
Confidence: high

### calibre-06
Oracle: RFC 7230 §4.1 defines chunk-size as `1*HEXDIG` only — no `0x` prefix, sign, or digit-group separators. `int(line.strip(), 16)` (http_request.py:426) inherits Python's own liberal `int()` grammar (which accepts `0x`, `+`/`-`, and `_` separators), so non-conformant chunk-size lines are silently accepted.
Type: known-external
Confidence: high

### calibre-07
Oracle: The function's own `stale="true"` challenge (auth.py:322-323) exists specifically to tell a client with the *correct* password to just retry with a fresh nonce, not to fail the login; but the code above it (line ~297) falls through into the same `log_msg`/`ban_list.failed()` path used for genuinely wrong credentials whenever `nonce_is_stale` is true, so a legitimate client gets logged/banned as if it had failed authentication.
Type: in-repo
Confidence: high

### calibre-08
Oracle: `embedded.py Server.start()` calls `self.loop.initialize_socket()` directly, then starts a thread running `serve_forever`, which calls `self.loop.serve_forever()` — and `ServerLoop.serve_forever` (loop.py:555) itself calls `self.initialize_socket()` again before `self.serve()`. The second call re-binds/re-wraps `self.socket` without closing the one created by the first call.
Type: in-repo
Confidence: high

### calibre-09
Oracle: Every other library-mutating handler in this package (cdb.py:123,145,163,251) follows the mutation with `ctx.notify_changes(db.backend.library_path, <event>)`; `conversion_status` (convert.py:252) builds the same kind of event (`formats_added(...)`) but discards the return value instead of passing it to `ctx.notify_changes`.
Type: in-repo
Confidence: high

### calibre-10
Oracle: The option's own help text in opts.py:81 states "Set to zero for no limit," but `update_max_block`/`abort_hanging_jobs` (jobs.py:98,198-224) treat `max_job_time == 0` as "already past deadline," aborting every job immediately — the opposite of the documented behavior.
Type: in-repo
Confidence: high

### calibre-11
Oracle: All three OPDS handlers (opds.py:664,687,739-745) wrap the `offset` query-param parse in try/except and convert failures to `HTTPNotFound`, establishing the local convention of turning bad user input into a 4xx — but the adjacent `from_hex_unicode(which)` call is left unguarded, so invalid hex propagates out as an unhandled exception (500).
Type: in-repo
Confidence: high

### calibre-12
Oracle: `finalize_headers` computes `self.close_after_response` from the client's `Connection` header / HTTP version (http_request.py:373-381), but `simple_response` (http_response.py:468) unconditionally overwrites `self.close_after_response` with its `close_after_response` argument; call sites for 404/401/redirect (`HTTPSimpleResponse` subclasses, errors.py:16-62) default `close_connection=False`, and `prepare_response`'s TRACE branch passes `close_after_response=False` explicitly — both clobber the correctly-computed client-requested close.
Type: in-repo
Confidence: high

### calibre-13
Oracle: `except KeyboardInterrupt, EOFError:` (standalone.py:209) is not valid Python 3 grammar; CPython 3's parser rejects a bare comma in an `except` clause with exactly `SyntaxError: multiple exception types must be parenthesized`, which also applies under 3.14.
Type: known-external
Confidence: high

### calibre-14
Oracle: `path_from_root` (utils/filenames.py:667-688) explicitly raises `ValueError` for any path containing a `'.'` or `'..'` component ("invalid path component"), and `add_extra_file` (db/backend.py:2374) calls it and returns `None` on `ValueError` without writing anything. A relpath of `data/../cover.jpg` is rejected by this existing guard before any write happens, so the described overwrite does not occur in this checkout.
Type: in-repo
Confidence: low

### calibre-15
Oracle: The sibling loop four lines above in the same function (opds.py:596-599) explicitly guards this exact case — `val = getattr(x, 'sort', x.name); if not val: val = 'A'` — precisely because `getattr(obj, 'sort', default)` only falls back when the attribute is *missing*, not when it's present and `None`. The second loop (line 602) omits that guard and calls `.upper()` directly on the possibly-`None` `sort` attribute.
Type: in-repo
Confidence: high

### calibre-16
Oracle: For `GeneratedOutput`, `content_length` is `None` (per its construction from an iterable); `finalize_output` (http_response.py:748-755) computes `output.content_length >= opts.compress_min_size` with no None-guard, so comparing `None >= int` raises `TypeError` in Python 3, an uncaught exception surfacing as 500.
Type: implicit
Confidence: high

### calibre-17
Oracle: The function's own cited spec, SMIL 3.0 Timing §q22 (linked in the comment at render_book.py:290), defines a bare `Timecount-value` (a plain number with no unit suffix) as seconds by default; `parse_smil_time`'s `elif len(parts) == 1:` branch (289-312) only recognizes `s`/`ms`/`min`/`h` suffixes and raises for an unsuffixed number.
Type: known-external
Confidence: medium

### calibre-18
Oracle: The comment two lines above in the same function (`walk`, code.py:368-375) — "so an intermediate node (e.g. 'History') matches both 'History' and its children" — shows hierarchical items are represented by leaf `name` only (not the full dotted path); deduping on that bare `name` in the `seen` set collapses distinct hierarchical entries that merely share a leaf label.
Type: in-repo
Confidence: medium

### calibre-19
Oracle: The `compressible`/`accept_ranges` variables in `finalize_output` (http_response.py:759-784) are deliberately built to be mutually exclusive (`accept_ranges = not compressible and ...`), showing intent that ranged and gzip-compressed responses can't coexist; but `ranges = get_ranges(...) if output.accept_ranges and ...` reads the raw `output.accept_ranges` object attribute instead of the locally-computed `accept_ranges`, so a compressible, range-satisfiable request slips past that exclusion, ending up with both `Transfer-Encoding: chunked` (set because `compressible` is true) and `Content-Length`/`Content-Range` (set by the ranges branch) while the body is written unchunked.
Type: in-repo
Confidence: high

### calibre-20
Oracle: In `parse_smil_time`'s 3-field branch (render_book.py:294-299), `min(abs(seconds), 59)` discards the fractional part of any seconds value ≥ 59 (e.g. 59.5 → 59), even though the same grammar (cited SMIL spec) allows a fractional seconds component; the clamp is meant to bound the integer range, not truncate sub-second precision.
Type: known-external
Confidence: medium

### calibre-21
Oracle: `is_recipe_fmt` (cdb.py:68-70), used by the sibling add-book endpoint, treats `recipe` and `downloaded_recipe` as equally dangerous formats that "allow code execution." `cdb_set_fields` (cdb.py:226) uses a separately hand-written check — `fmt.lower() in ('recipe', 'original_recipe')` — that omits `downloaded_recipe`/`original_downloaded_recipe`, so those variants reach this path unblocked.
Type: in-repo
Confidence: high

### calibre-22
Oracle: `except AttributeError, OSError:` (loop.py:570) is the same invalid Python-2-only comma syntax as calibre-13/calibre-45; CPython 3 raises `SyntaxError: multiple exception types must be parenthesized` for it, true under 3.14 as well.
Type: known-external
Confidence: high

### calibre-23
Oracle: `accept_ranges = ... output.accept_ranges is not None ...` (http_response.py:759) treats `False` as "acceptable" because `False is not None` — contradicting the very next range-computation line (`ranges = ... if output.accept_ranges and ...`, using plain truthiness) in the same function, which correctly excludes objects with `accept_ranges = False`. The header gets advertised even though the object explicitly declared it doesn't support ranges.
Type: in-repo
Confidence: high

### calibre-24
Oracle: `self.method` is the HTTP verb string set at http_request.py:314 (`self.method = method.decode('ascii').upper()`), and `HTTP1` is the literal string `'HTTP/1.0'` (utils.py:25) — `self.method is HTTP1` (http_response.py:561) can never be true. The surrounding code (e.g. the `Connection` header logic two lines later, `if self.response_protocol is HTTP11:`) shows `self.response_protocol` is the variable that should have been compared, not `self.method`.
Type: in-repo
Confidence: high

### calibre-25
Oracle: The first loop building `starts` (opds.py:596-599) explicitly remaps a falsy `sort`/`name` to group `'A'` (`if not val: val = 'A'`); the second loop computing per-group counts (line 602) re-derives the value via `getattr(y, 'sort', y.name).upper().startswith(x)` without that same remap, so an item with `sort == ''` is placed in group `'A'` by the first loop but never matches `''.startswith('A')` in the second.
Type: in-repo
Confidence: high

### calibre-26
Oracle: RFC 6455 §7.4.2 defines the WebSocket close-code space: 1000-2999 reserved for the protocol, 3000-3999 for libraries/frameworks (IANA-registered), 4000-4999 for private use, with nothing defined above 4999; `ws_control_frame`'s validity check (web_socket.py:418, `close_code < 1000 or ... or (1011 < close_code < 3000)`) accepts anything ≥ 3000 including the undefined 5000-65535 range.
Type: known-external
Confidence: medium

### calibre-27
Oracle: Every other rejection in `parse_request_line` (e.g. "Malformed Request-Line", http_request.py:317) uses `simple_response`'s default `close_after_response=True`, closing the connection because the rest of the request was never read off the socket. The `parse_uri` failure branch (328-331) explicitly overrides this to `close_after_response=False` without ever consuming the pending header/body bytes, so those bytes are subsequently parsed as a new request line.
Type: in-repo
Confidence: high

### calibre-28
Oracle: RFC 7230 §4.1.1's `trailer-part = *( header-field CRLF )` explicitly permits trailer fields after the last chunk; `read_chunk_separator` (http_request.py:449-450) rejects any post-final-chunk line that isn't a bare CRLF with 400, refusing valid trailers. (This may be a deliberate, defensible simplification rather than an oversight, since trailers are rarely used and are a known smuggling risk if mishandled.)
Type: known-external
Confidence: medium

### calibre-29
Oracle: `upload_data_files` (content.py:632-639) always prefixes client-supplied names with `f'{DATA_DIR_NAME}/{name}'`, constraining writes to the book's `data/` subtree; `remove_data_files` (content.py:659-668) passes the client's raw `relpaths` list straight to `db.remove_extra_files` with no such prefix, and `remove_extra_files`/`path_from_root` only check that the resolved path stays inside the book directory, not that it's under `data/` — so a relpath like `cover.jpg` or the book's own `.epub` resolves to, and deletes, the book's actual cover/format file while the database still records it as present.
Type: in-repo
Confidence: high

### calibre-30
Oracle: `job_done`'s status line (http_response.py:582) hardcodes `HTTP11 + f' {data.status_code} '...`, whereas the sibling `simple_response` method (line ~471) correctly emits `f'{self.response_protocol} {status_code} ...'` using the negotiated protocol — showing the intended pattern that `job_done` doesn't follow for HTTP/1.0 requests.
Type: in-repo
Confidence: high

### calibre-31
Oracle: The `close_needed` loop (`for x, conn in close_needed: self.close(s, conn)`, loop.py:615-616) declares loop variable `x` but calls `self.close(s, conn)` using `s`, the stale variable from the earlier, unrelated `for s, conn in self.connection_map.items():` loop in the same function — visibly inconsistent with the correctly-matched loop immediately above it (`for s, conn in remove: ... self.close(s, conn)`).
Type: in-repo
Confidence: high

### calibre-32
Oracle: Same root cause as calibre-24 — `is_http1` is computed from the always-false `self.method is HTTP1` comparison, so the `compressible`/chunked logic in `finalize_output` (http_response.py:759-793) never special-cases HTTP/1.0, and any `GeneratedOutput` (unknown length) gets `Transfer-Encoding: chunked` regardless of protocol, which HTTP/1.0 doesn't support.
Type: in-repo
Confidence: high

### calibre-33
Oracle: Within the same function, `end = min((start + num - 1), total)` (legacy.py:113) shows the current page covers items through `start+num-1`; the "more pages remain" check (`if total > start + num:`, line 122) should therefore be `total > start + num - 1` (equivalently `total >= start + num`) to catch the boundary case, but uses strict `>` against `start+num`, so `start=1, num=25, total=26` (26 > 26 is false) omits Next/Last even though book 26 is unreachable.
Type: in-repo
Confidence: high

### calibre-34
Oracle: The sibling bodyless-response methods in the same class, `simple_response` (http_response.py:468-488) and `send_not_modified` (~540), both explicitly set `Content-Length` (including `Content-Length: 0`); `send_range_not_satisfiable` (521-529) omits any Content-Length while also not forcing `close_after_response`, leaving the response's framing ambiguous on a persistent HTTP/1.1 connection.
Type: in-repo
Confidence: medium

### calibre-35
Oracle: Two structurally similar inline-servable endpoints in the same file, `get_note_resource` (content.py:526) and `data_file` (content.py:593), both call `add_sandbox_headers(rd, content_type)` before returning content that a browser might render inline; `book_fmt` (223-263), which also supports `content_disposition=inline` and can serve HTML/XHTML/SVG formats, never calls it.
Type: in-repo
Confidence: high

### calibre-36
Oracle: RFC 7230 §4.1's chunk-size grammar (`1*HEXDIG`) never allows a sign; `int(line.strip(), 16)` (http_request.py:426) accepts Python's `-`-prefixed hex literals, producing a negative `chunk_size` that is then added into the `bytes_read[0]` running total used by the `> self.max_request_body_size` check two lines above — letting a negative chunk silently offset that counter so later legitimate chunks can push the true body size past the configured limit without tripping it.
Type: known-external
Confidence: high

### calibre-37
Oracle: `number_of_books_in_virtual_library` (db/cache.py:1889) accepts an optional `search_restriction` parameter specifically to apply the user's library restriction; `search_result`'s query-present branch (ajax.py:554, `db.number_of_books_in_virtual_library(vl)`) doesn't pass it, while the query-absent branch uses `total_num`, which comes from `ctx.search` (handler.py:169) applying the restriction via `get_effective_book_ids`. The query-present count is therefore unrestricted, unlike every other count on the same response.
Type: in-repo
Confidence: high

### calibre-38
Oracle: The comment at convert.py:45 ("sanitize output_fmt to prevent path traversal") states the intent, and that sanitization is applied only to `JobStatus.output_path`; the unsanitized `conversion_data['output_fmt']` is separately passed as an argument all the way into `convert_book`, which builds `output_path = os.path.abspath('output.' + output_fmt.lower())` (line 134) from the raw value, defeating the stated protection.
Type: in-repo
Confidence: high

### calibre-39
Oracle: `category_browse_search_expression` (code.py:337-352) special-cases `field == 'rating'` to translate star glyphs into a numeric search, but it's only ever called with the top-level category `field` key (code.py:382), not the item's `datatype` (which is tracked and available at line 304 but unused here) — so a custom column whose `field` is e.g. `#mycol` but `datatype == 'rating'` falls through to the generic branch and gets a literal `★★★` embedded in the search expression.
Type: in-repo
Confidence: medium

### calibre-40
Oracle: `rd.tdir` traces back to a single `TemporaryDirectory` created once per server lifetime in `ServerLoop.serve()` (loop.py:537, `with TemporaryDirectory(...) as tdir: self.tdir = tdir`) and shared by every connection via the handler constructor (loop.py:723); `cdb_add_book` (cdb.py:107) writes uploads to `os.path.join(rd.tdir, sfilename)` in that shared directory keyed only by the sanitized client-supplied filename, so two concurrent uploads with the same name collide on the same path.
Type: in-repo
Confidence: high

### calibre-41
Oracle: `BanList.failed` (auth.py:48-58) re-inserts the touched key at the end of the `OrderedDict` before pruning, then iterates `reversed(self.items)` — starting from that just-touched, always-fresh (`now - previous_fail == 0`) entry — and `break`s on the first non-stale item, so the loop always terminates on its very first iteration and never reaches genuinely stale entries further toward the front.
Type: in-repo
Confidence: high

### calibre-42
Oracle: `is_banned` (auth.py:32-39) treats a ban as expired once `monotonic() - previous_fail >= self.interval`, but `failed` (48-51) reuses `x[1]` (the prior fail count) unconditionally on the next failure regardless of how stale `x[0]` is — there's no check mirroring `is_banned`'s staleness test before carrying the count forward, so counts accumulate across arbitrarily long gaps instead of resetting once a ban has lapsed.
Type: in-repo
Confidence: medium

### calibre-43
Oracle: `create_file_copy`'s cache filename (content.py:78, `f'{prefix}-{library_id}-{book_id:x}.{ext}'`) doesn't include `extra_etag_data`, but `book_fmt` derives `extra_etag_data = repr(cpb)` from the current plugboard (228-243) and passes it only into the returned ETag, not the cache key; if the plugboard changes without the underlying mtime changing, the cache-hit branch (`previous_mtime >= mt`) serves the stale, previously-generated file while computing a fresh ETag that implies different content.
Type: in-repo
Confidence: medium

### calibre-44
Oracle: `UserManager.restrictions` (users.py:233-235) does `parse_restriction(restriction).copy()` — a shallow copy of an `lru_cache`d dict — leaving the nested `library_restrictions` dict object shared with the cache entry; `manage_users_cli.py` (lines 430, 432) mutates that nested dict in place (`r['library_restrictions'][library] = plr` / `.pop(...)`), so the edit lands in the shared cached object and is visible to every other user whose restriction string parses to the same cache entry.
Type: in-repo
Confidence: high

### calibre-45
Oracle: `except ValueError, UnicodeDecodeError:` (content.py:358) is the same invalid Python-2-only syntax as calibre-13/calibre-22; parsed under Python 3 (including 3.14) this raises `SyntaxError: multiple exception types must be parenthesized`.
Type: known-external
Confidence: high

### calibre-46
Oracle: `cdb_add_book` (cdb.py:107-119) writes the upload and any import-plugin output into `rd.tdir`, which — per calibre-40's tracing — is the single server-lifetime temp directory (loop.py:537), not a per-request scratch dir; there is no `os.remove`/cleanup call anywhere in the handler after `db.add_books` succeeds, so the file persists until the server-wide `TemporaryDirectory` context exits at shutdown.
Type: in-repo
Confidence: medium

### calibre-47
Oracle: Two lines above in the same loop (books.py:110, `os.path.getmtime(os.path.join(fdir, x, 'calibre-book-manifest.json'))`), the code correctly builds the full path; the deletion call `safe_remove(x)` (line 115) uses the bare directory-entry name instead of `os.path.join(fdir, x)`, so it resolves relative to the process's current working directory rather than the intended `srvb/f` cache directory.
Type: in-repo
Confidence: high

### calibre-48
Oracle: RFC 7230 §3.2 defines a header field as `field-name ":" OWS field-value OWS` — a colon is mandatory. `HTTPHeaderParser.commit` (http_request.py:189-193) does `k, v = line.partition(b':')[::2]`; when there's no colon, `partition` yields `(whole_line, b'', b'')`, so `k` is non-empty and the "no key" guard (`if not key: raise`) never fires, silently accepting the malformed line as a header with an empty value.
Type: known-external
Confidence: medium

### calibre-49
Oracle: Within `parse_smil_time`'s single-part branch (render_book.py:294-299), the `x.endswith('s')` check is evaluated before `x.endswith('ms')`, but `'500ms'.endswith('s')` is also true, so it's routed to the seconds branch and `float(x[:-1])` is called on `'500m'`, raising `ValueError` — even though the function has a dedicated, unreachable `elif x.endswith('ms')` branch two lines below written specifically to handle this input.
Type: in-repo
Confidence: high

### calibre-50
Oracle: RFC 7230 §3.2.4 states a server "MUST reject" (or close the connection on) any message with whitespace between a header field-name and the colon, specifically to prevent request-smuggling ambiguity between front-end/back-end parsers; `HTTPHeaderParser.commit` (http_request.py:189-190) strips the field-name (`k.strip()`) before checking it, silently normalizing `Content-Length : 5` into a well-formed `Content-Length` header instead of rejecting it.
Type: known-external
Confidence: high

### calibre-51
Oracle: RFC 7230 §3.3.3's message-framing precedence requires Transfer-Encoding to always be honored/examined and forbids the combination of TE and Content-Length (to prevent request smuggling); `finalize_headers` (http_request.py:373-381) only inspects `Transfer-Encoding` `if self.response_protocol is HTTP11:`, so an HTTP/1.0 request with `Transfer-Encoding: chunked` skips chunk decoding entirely (body bytes are left in the stream and reparsed as the next request) and the "can't specify both TE and Content-Length" check is bypassed.
Type: known-external
Confidence: high

### calibre-52
Oracle: A UTF-8 sequence's continuation bytes are only valid as a unit; `websocket_close` (web_socket.py:439) truncates the reason with a fixed byte slice, `reason[:123]`, with no awareness of character boundaries, which can split a multi-byte sequence and leave invalid UTF-8 in the close frame — violating RFC 6455 §5.5.1's requirement that the Reason be valid UTF-8.
Type: known-external
Confidence: high

### calibre-53
Oracle: `get_ranges` (http_response.py:138) does `start, stop = (x.strip() for x in brange.split('-', 1))` with no surrounding try/except; a range spec with no `-` (e.g. `bytes=5`) produces a single-element generator, and unpacking it into two names raises `ValueError: not enough values to unpack`, propagating uncaught out of the function.
Type: implicit
Confidence: high

### calibre-54
Oracle: The option's own help text (opts.py:105, "Group items ... by first letter when there are more than this number of items. Set to zero to disable.") states 0 should turn grouping off; `get_navcatalog`'s condition (opds.py:588-590, `if MAX_ITEMS > 0 and len(items) <= MAX_ITEMS:`) is false whenever `MAX_ITEMS == 0`, which routes every request into the `else` (grouped) branch — the opposite of "disable."
Type: in-repo
Confidence: high

### calibre-55
Oracle: The initial sort field is computed via `sanitize_sort_field_name(db.field_metadata, rd.query.get('sort') or 'date')` (legacy.py, just above the fallback), which translates the search-term `'date'` into the real internal field key before use; the `except` fallback (line 271, `sort_by = 'date'`) skips that same translation and passes the raw search term straight to `db.multisort`, so it fails the same way the original bad value did.
Type: in-repo
Confidence: medium

### calibre-56
Oracle: The adjacent branch of the same function (http_response.py:147-149, `if stop < start: continue`) shows the intended invariant that a `Range` must never have `stop < start`; the suffix-range `elif stop:` branch (152-161) has no equivalent check, so `bytes=-0` (stop=0, not `> content_length`) falls into the `else` producing `Range(content_length, content_length-1, 0)`, i.e. start > stop.
Type: in-repo
Confidence: high

### calibre-57
Oracle: `content.py`'s `get` handler establishes the codebase's access-control convention by calling `ctx.has_id(rd, db, book_id)` (raising `BookNotFound` otherwise) before returning any book data; `get_library_init_data` (code.py:456-464) reads client-supplied `extra_books` ids and passes each straight to `book_as_json(db, book_id)` with no equivalent restriction/ownership check.
Type: in-repo
Confidence: high

### calibre-58
Oracle: `sort_q_values`'s `item()` helper (utils.py:237-248) strips whitespace from the entry name (`e.strip()`) but not from the parameter name `p` before comparing `p == 'q'`; for `'fr; q=0.5'`, `partition(';')` gives `r = ' q=0.5'` and `partition('=')` gives `p = ' q'`, which fails the exact `'q'` comparison, so the weight is silently ignored and defaults to 1.0.
Type: in-repo
Confidence: high

### calibre-59
Oracle: The sibling write endpoint in the same file, `fts_reindex` (fts.py:84, `methods=('POST',)`), explicitly restricts itself to POST because it mutates state; `fts_disable` (fts.py:76-77, `needs_db_write=True`) has no `methods=` override, so it falls back to `routes.py`'s `default_methods = {'HEAD', 'GET'}`, making a state-changing operation reachable via a safe/idempotent HTTP method (RFC 7231 §4.2.1) and thus CSRF-able via a plain `<img>`-style GET.
Type: in-repo
Confidence: high

### calibre-60
Oracle: Same missing invariant as calibre-56 — the suffix-range branch (http_response.py:152-161) has no `stop < start` guard analogous to the one in the sibling branch three lines above; `bytes=--5` parses to `stop = int('-5') = -5`, which isn't `> content_length`, so it falls to `else: Range(content_length - stop, content_length - 1, stop)` = `Range(105, 99, -5)`, a range with negative size and start > stop.
Type: in-repo
Confidence: high

### calibre-61
Oracle: The very next log statement in the same method (jobs.py:239, `f'The job: {job.job_name} failed...'`) correctly uses `job.job_name`, the human-readable name set at `Job.__init__` (jobs.py:27, `self.job_name = start_event.name`); the callback-exception log two lines earlier (line 235) uses `job.name`, which is `Thread`'s own name set to `f'JobsMonitor{start_event.job_id}'` (jobs.py:23) — an internal thread identifier, not the job's description.
Type: in-repo
Confidence: high

### calibre-62
Oracle: `self.forwarded_for` is initialized to `None` at connection setup (http_request.py:258,293) and set from the request's `X-Forwarded-For` header in exactly one place, `finalize_headers` line 399 — which sits after the `Expect: 100-continue` early return (396-397); no other code on the `write_continue → read_request_body → prepare_response` path sets it, so it stays `None` for any request using `Expect: 100-continue`.
Type: in-repo
Confidence: high

### calibre-63
Oracle: The module-level docstring for `quicklook_service` (render_book.py, just above) describes a per-connection request/response protocol ("send JSON... In response, the service will..."); the implementation in `handle_quicklook_client` (902-917) places the request-processing/response block *after* (not inside) the `for line in inf:` loop, so it only runs once, using whichever `req` was last assigned, after the client's write side closes — and if the client sends zero lines, `req` is referenced unassigned, raising `UnboundLocalError`.
Type: in-repo
Confidence: high

---

The hardest ones to classify were the WebSocket close-code range (calibre-26) and the trailer-rejection behavior (calibre-28), because RFC 6455/7230 leave real room for a server to be more conservative than the letter of the grammar without that being a "defect" — I couldn't cleanly separate spec deviation from a deliberate, defensible security-motivated restriction, so I kept confidence at medium rather than high. The SMIL-time findings (calibre-17, calibre-20) were similarly awkward: I'm relying on a spec I know well but haven't verified word-for-word from a live copy, and the clamping bug in particular reads as a genuine bug but has narrow real-world impact. calibre-14 was hardest in a different way — the finding describes a traversal that the code I actually read (`path_from_root`) appears to already block, so I had to downgrade confidence sharply based on directly contradicting evidence rather than the usual gap-in-coverage reasoning.
