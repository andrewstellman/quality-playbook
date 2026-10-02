# calibre, classifier S3 (Claude Sonnet), blind

### calibre-01
Oracle: RFC 9110 §14.1.2's suffix-length range handling gives no rule for a zero-length representation, but the resulting `Range(0, -1, 0)` has `stop < start`, and the code still emits a 206 with `Content-Range`/`Content-Length` built from that invalid range object (http_response.py:161).
Type: known-external
Confidence: medium

### calibre-02
Oracle: RFC 9110 §12.5.3 (`Accept-Encoding`): a coding with `q=0` is explicitly "not acceptable." `sort_q_values`/`acceptable_encoding` (utils.py:232-248, http_response.py:101-106) never filter out `q=0` entries, only sort by weight.
Type: known-external
Confidence: high

### calibre-03
Oracle: RFC 9112 §7.1.1 chunk-size grammar permits `chunk-ext`; a compliant server ignores unrecognized extensions rather than rejecting the request. `read_chunk_length` (http_request.py:426) feeds the whole line including `;ext` into `int(line, 16)`.
Type: known-external
Confidence: medium

### calibre-04
Oracle: no oracle needed for the leak — `open_for_write(fname)` (content.py:105) is never closed if `copy_func` raises, and there's no `try/finally`. The docstring's promise ("make sure to only do this copy once... no changes since last copy") is the oracle for the second half: the partial file's new mtime makes the cache logic (lines 88-89) treat it as a valid completed copy and serve it 200 on the next request.
Type: implicit
Confidence: high

### calibre-05
Oracle: RFC 9112 §5.2 requires obs-fold to be replaced by SP (or rejected outright); `commit()` (http_request.py:186-195) joins lines with `b' '.join` and only `.strip()`s the ends, leaving the internal `\r\n` from the folded continuation inside the header value.
Type: known-external
Confidence: high

### calibre-06
Oracle: RFC 9112 §7.1.1 chunk-size = `1*HEXDIG` — no `0x` prefix, sign, or `_` separators. `int(line.strip(), 16)` (http_request.py:426) accepts all of Python's numeric-literal syntax, which is broader than the wire grammar.
Type: known-external
Confidence: medium

### calibre-07
Oracle: the code's own `nonce_is_stale` flag (auth.py:297-303) is computed specifically to distinguish "correct password, stale nonce" from a real auth failure, but the `if not nonce_is_stale: ... return` guard falls through to `self.ban_list.failed(ban_key)` and a "Failed login attempt" log on the stale branch too — contradicting RFC 7616 §3.3, where a stale nonce with a valid credential is answered with a fresh `stale="true"` challenge, not treated as a failed attempt.
Type: known-external
Confidence: high

### calibre-08
Oracle: `Server.start()` (embedded.py:95) calls `self.loop.initialize_socket()`, then the spawned thread calls `serve_forever()` (loop.py:557) which calls `self.initialize_socket()` again; `initialize_socket` (loop.py:503) unconditionally rebinds via `do_bind()` when `pre_activated_socket is None`, and the first `self.socket` is overwritten without being closed.
Type: implicit
Confidence: high

### calibre-09
Oracle: `formats_added({...})` is called for its side effect but its return value is discarded (convert.py:252); the established pattern in this codebase (cdb.py:123,145,163,251 — `ctx.notify_changes(path, <event>)`) shows the event object is supposed to be handed to `ctx.notify_changes`, which never happens here.
Type: in-repo
Confidence: high

### calibre-10
Oracle: `opts.py:81` documents `max_job_time`: "Set to zero for no limit." `JobsManager.__init__` computes `self.max_job_time = max(0, opts.max_job_time*60)`, so 0 stays 0, and `update_max_block`/`abort_hanging_jobs` (jobs.py:198-224) treat `delta <= 0` as "already overdue," aborting every job immediately — the opposite of the documented behaviour.
Type: in-repo
Confidence: high

### calibre-11
Oracle: `opds_navcatalog`/`opds_category`/`opds_categorygroup` (opds.py:664,687,739-745) wrap `int(rd.query.get('offset',0))` in try/except→404 but call `from_hex_unicode()` on the same untrusted path segment with no guard; it raises on non-hex input and propagates to a 500.
Type: implicit
Confidence: high

### calibre-12
Oracle: `simple_response` (http_response.py:468) does `self.close_after_response = close_after_response` unconditionally, overwriting the value `finalize_headers` computed from the request's actual `Connection` header/HTTP version. Callers of `simple_response` that pass a literal default (e.g. `HTTPSimpleResponse.close_connection`) stomp on that decision.
Type: in-repo
Confidence: high

### calibre-13
Oracle: `except KeyboardInterrupt, EOFError:` (standalone.py:209) is Python-2 syntax; under Python 3 (3.10 through 3.14) this is a hard `SyntaxError`, so the module cannot even be imported.
Type: implicit
Confidence: high

### calibre-14
Oracle: `path_from_root` (src/calibre/utils/filenames.py:667-687), which `add_extra_file` (db/backend.py:2374-2379) calls before writing, explicitly rejects any path component equal to `'..'` and raises `ValueError` — caught and turned into a silent no-op (`return None`). Traced through, a `name` of `../cover.jpg` should be rejected, not written — this contradicts the finding's claimed overwrite.
Type: in-repo
Confidence: low

### calibre-15
Oracle: in the same function, the first loop (`starts = set()`) explicitly guards `if not val: val = 'A'` for a `None`/empty sort value, but the second loop's `getattr(y, 'sort', y.name).upper()` (opds.py:598-604) has no such guard and calls `.upper()` directly, raising `AttributeError` when `sort` is `None`.
Type: in-repo
Confidence: high

### calibre-16
Oracle: `output.content_length >= opts.compress_min_size` (http_response.py:748-755) compares `None >= int` when `output` is a `GeneratedOutput` with unknown length, raising `TypeError`.
Type: implicit
Confidence: high

### calibre-17
Oracle: the function's own reference comment (`https://www.w3.org/TR/SMIL3/smil-timing.html#q22`, render_book.py:289) points at the SMIL clock-value grammar, where `Timecount-value` with no `Metric` suffix defaults to seconds; `parse_smil_time` (lines 299-303) only handles that shape when a `s/ms/min/h` suffix is present and otherwise raises.
Type: known-external
Confidence: medium

### calibre-18
Oracle: `category_browse_search_expression` (code.py:346-348) has a comment explicitly distinguishing hierarchical nodes ("History" vs "History.Military"), showing the codebase treats hierarchy as semantically distinct — but `category_browse_items`'s `walk()` (code.py:368-375) dedups purely on the flat display `name`, conflating "History.Military" and "Science.Military".
Type: in-repo
Confidence: medium

### calibre-19
Oracle: traced directly — `compressible` is computed independent of `ranges` (http_response.py:748-761), but the actual gzip conversion only happens `if compressible and not ranges:` (line 784), so a satisfiable Range request on a compressible resource sets `Transfer-Encoding: chunked` (line 793, gated only on `compressible`) while also setting `Content-Length`/`Content-Range` for the 206 (lines 795-798) — two mutually exclusive framings on the same response, which RFC 9112 §6.1 forbids sending together.
Type: known-external
Confidence: high

### calibre-20
Oracle: SMIL clock-value grammar (cited in the code's own comment at render_book.py:289) defines the seconds field as ranging up to but excluding 60 (00-59.999); `min(abs(seconds), 59)` (line 294) clamps a legitimately valid value like 59.5 down to 59, discarding real precision rather than only rejecting out-of-range input.
Type: known-external
Confidence: medium

### calibre-21
Oracle: `is_recipe_fmt()` (cdb.py:68-70) — used correctly in `cdb_add_book` — strips an `original_` prefix and checks against `{'recipe','downloaded_recipe'}`, i.e. blocks all four variants. `cdb_set_fields` (cdb.py:226) reimplements the check inline as `fmt.lower() in ('recipe','original_recipe')`, missing `downloaded_recipe`/`original_downloaded_recipe`.
Type: in-repo
Confidence: high

### calibre-22
Oracle: `except AttributeError, OSError:` (loop.py:570) is Python-2 syntax; under Python 3 it's a `SyntaxError` at parse time.
Type: implicit
Confidence: high

### calibre-23
Oracle: `accept_ranges = ... output.accept_ranges is not None ...` (http_response.py:759) — `dynamic_output`/`GeneratedOutput` set `accept_ranges = False`, and `False is not None` is `True`, so the header gets sent anyway, while the actual range computation `if output.accept_ranges and ...` (a truthiness check, line 760) correctly evaluates `False` and skips ranging — the two checks on the same attribute disagree.
Type: in-repo
Confidence: high

### calibre-24
Oracle: `self.method is HTTP1` (http_response.py:561) compares the request's HTTP verb string (e.g. `'GET'`) against the sentinel `HTTP1 = 'HTTP/1.0'` (utils.py:25) — always `False`. Elsewhere the code correctly uses `self.response_protocol is HTTP1` (e.g. simple_response) for this exact test.
Type: in-repo
Confidence: high

### calibre-25
Oracle: same function as calibre-15 — the first loop places items with falsy `sort` into group `'A'` (`if not val: val = 'A'`), but the second loop's count uses `getattr(y,'sort',y.name).upper().startswith(x)`; for `sort=''`, `''.upper()==''` never starts with `'A'`, so the item is shown in group A's listing but not counted in its total.
Type: in-repo
Confidence: high

### calibre-26
Oracle: RFC 6455 §7.4.1/§7.4.2 define close codes 1000-2999 as protocol-reserved, 3000-3999 registered, 4000-4999 private-use, with nothing defined ≥5000; `ws_control_frame`'s check `close_code < 1000 or close_code in RESERVED_CLOSE_CODES or (1011 < close_code < 3000)` (web_socket.py:418) has no upper bound, so 5000-65535 pass through and get echoed.
Type: known-external
Confidence: medium

### calibre-27
Oracle: the exception-handling branch for a bad URI (http_request.py:328-331) sends its 400 with `close_after_response=False` and does not drain/skip the still-unread header block belonging to that malformed request before returning to `connection_ready`, so the reused connection parses the leftover header lines as a new request line — a classic desync condition that RFC 9112 §11.2 (request smuggling) guards against by requiring an unparseable/undrainable request to close the connection.
Type: known-external
Confidence: medium

### calibre-28
Oracle: `read_chunk_separator` (http_request.py:449-450) rejects any post-terminal-chunk line that isn't a bare CRLF with `'Chunk does not have trailing CRLF'` — but RFC 9112 §7.1.2 defines an optional `trailer-part` in that exact position; the message is also factually wrong (it's not a CRLF problem, it's an unsupported trailer). Rejecting trailers outright is a permitted implementation choice, though.
Type: known-external
Confidence: low

### calibre-29
Oracle: `upload_data_files` prefixes every relpath with `DATA_DIR_NAME` (content.py:632-639), but `remove_data_files` (content.py:659-668) passes client-supplied relpaths straight to `db.remove_extra_files` with no such prefix/pattern restriction, letting relpaths like `cover.jpg` or `metadata.opf` (outside the data dir, core book assets) be deleted through an endpoint documented/used for "extra data files."
Type: in-repo
Confidence: high

### calibre-30
Oracle: `job_done`'s status line is built as `HTTP11 + f' {status_code} ' + ...` (http_response.py:582), a hardcoded literal, while `self.response_protocol` (correctly tracked and used in `simple_response`, `send_range_not_satisfiable`, etc.) is ignored — so an HTTP/1.0 request always gets an `HTTP/1.1` status line.
Type: in-repo
Confidence: high

### calibre-31
Oracle: the `close_needed` loop (loop.py:615-616) reads `for x, conn in close_needed: self.close(s, conn)` — `s` is leftover from the earlier `for s, conn in remove:` loop and never reassigned inside this loop, so the wrong socket/connection-map entry is closed/removed.
Type: in-repo
Confidence: high

### calibre-32
Oracle: `if compressible or output.content_length is None: outheaders.set('Transfer-Encoding', 'chunked', ...)` (http_response.py:793-794) — `compressible` is already forced `False` for HTTP/1.0 via `not is_http1` (line 754), but the second disjunct (`content_length is None`) has no `is_http1` guard, so `Transfer-Encoding: chunked` still gets set for HTTP/1.0. RFC 9112 restricts chunked transfer coding to HTTP/1.1.
Type: known-external
Confidence: high

### calibre-33
Oracle: traced directly — `end = min(start+num-1, total)` gives `end=25` for `total=26`, but the Next/Last condition `total > start + num` (legacy.py:122) evaluates `26 > 26 = False`, so the link needed to reach book 26 (which `end` shows exists beyond the displayed range) is never rendered — an off-by-one against the function's own `end` computation.
Type: in-repo
Confidence: high

### calibre-34
Oracle: RFC 9110 §15.5.17 requires a 416 response to include `Content-Range` (which it does) but says nothing forbidding a missing `Content-Length`; however `send_range_not_satisfiable` (http_response.py:521-529) sends no `Content-Length` while implicitly keeping the connection open (no `close_after_response`/`Connection: close` handling), which per RFC 9112 §6.1 makes response framing on a persistent connection ambiguous without either `Content-Length`, chunked encoding, or connection close.
Type: known-external
Confidence: medium

### calibre-35
Oracle: `add_sandbox_headers` (content.py:199-207) is called at the two other places that can serve arbitrary content-typed data inline (lines 526, 593) specifically, per its own docstring, "to prevent user supplied content that is rendered inline... from being able to script the server's origin" — `book_fmt` (lines 223-263) supports `content_disposition=inline` (line 254) and can serve HTML/XHTML/SVG book formats, but never calls it.
Type: in-repo
Confidence: high

### calibre-36
Oracle: `int(line.strip(), 16)` (http_request.py:426) accepts a leading `-`, so `chunk_size` can be negative; the size-limit check `bytes_read[0] + chunk_size + 2 > max` (same function) can be defeated by adding a negative number, letting cumulative "read" bytes stay under `max_request_body_size` indefinitely. Combined with RFC 9112's `chunk-size = 1*HEXDIG` (no sign), this is both a spec violation and a resource-limit bypass.
Type: known-external
Confidence: high

### calibre-37
Oracle: `total_num` comes from `ids` after `ctx.search(rd, db, query, vl=vl, ...)` (ajax.py:547-552), which applies the user's access restriction; `num_books_without_search` instead calls `db.number_of_books_in_virtual_library(vl)` (ajax.py:554) with no `search_restriction` argument (cache.py:1889-1892 shows that parameter exists and is needed to apply a restriction) — an asymmetric restriction bypass leaking a book count outside what the user is scoped to.
Type: in-repo
Confidence: medium

### calibre-38
Oracle: `JobStatus.__init__` (convert.py:46) has an explicit comment "# sanitize output_fmt to prevent path traversal" for its own `output_path`, but `convert_book` (line 187) is invoked with the raw, unsanitized `conversion_data['output_fmt']` and does `os.path.abspath('output.' + output_fmt.lower())`, which resolves `/../../../../tmp/x.epub` outside the working directory — the sanitization the code documents intending was never applied to the path that's actually written.
Type: in-repo
Confidence: high

### calibre-39
Oracle: `category_browse_search_expression`'s `if field == 'rating':` branch (code.py:337-341) only matches the literal built-in field name `'rating'`; a custom column of datatype `rating` has a field key like `#mycol`, so it falls through to the generic `f'{field}:"={escape_search_value(search_name)}"'` branch and embeds the raw `★` string, which the search parser (per its own "Non-numeric value in query" error) rejects.
Type: in-repo
Confidence: high

### calibre-40
Oracle: traced through `loop.py:537` (`self.tdir = tdir` set once in `serve()`'s `with TemporaryDirectory(...)`) and `loop.py:723` (the same `self.tdir` passed to every new connection's handler), confirming `rd.tdir` (cdb.py:107) is the single server-wide temp dir, not per-request/per-connection; `os.path.join(rd.tdir, sanitized_filename)` lets two concurrent uploads of files with the same client-supplied name collide on one path.
Type: in-repo
Confidence: high

### calibre-41
Oracle: `failed()` (auth.py:44-58) always re-inserts the failing key at the *end* of the (insertion-ordered) dict via `pop`+re-assign, so `reversed(self.items)` (line 52) hits the just-stored `now` timestamp first, computes `now - previous_fail == 0`, fails the `> interval` test, and `break`s immediately — the prune loop can never reach or remove any older entry.
Type: implicit
Confidence: high

### calibre-42
Oracle: `is_banned()` (auth.py:32-42) treats a stored failure as only valid within `self.interval` of `monotonic()`, showing the class's own sliding-window intent, but `failed()` (lines 44-51) carries forward `x[1]` (the previous fail count) unconditionally regardless of how old that entry is, contradicting the windowed semantics `is_banned` relies on.
Type: in-repo
Confidence: high

### calibre-43
Oracle: `book_fmt`'s ETag is `filesystem_file_with_custom_etag(ans, prefix, library_id, book_id, mt, extra_etag_data)` (content.py:262) where `extra_etag_data = repr(cpb)` is recomputed from the *current* live plugboard on every call, while `create_file_copy`'s cache-reuse decision (content.py:88-89) is keyed only on `mt` (mtime) — if the plugboard changes without touching `mt`, the stale cached file (built with the old plugboard) is served under a freshly computed ETag that reflects the new plugboard, so the ETag no longer identifies the bytes actually served.
Type: in-repo
Confidence: high

### calibre-44
Oracle: `restrictions()` (users.py:236) returns `parse_restriction(restriction).copy()`, a shallow copy of an `@lru_cache`d dict (users.py:29); `manage_users_cli.py:430` then does `r['library_restrictions'][library] = plr`, mutating the nested dict in place — since the shallow copy shares that nested object, this silently corrupts the cached entry shared by every user with the same stored restriction string.
Type: in-repo
Confidence: high

### calibre-45
Oracle: `except ValueError, UnicodeDecodeError:` (content.py:358) is Python-2 syntax; a `SyntaxError` under any Python 3 interpreter.
Type: implicit
Confidence: high

### calibre-46
Oracle: no oracle needed beyond reading the function — `cdb_add_book` (cdb.py:107-119) writes the upload to `rd.tdir`, reassigns `path` via `run_import_plugins`, reads and adds it to the DB, but contains no `os.remove`/cleanup call or `try/finally` anywhere in the endpoint; combined with `rd.tdir` being the server-wide temp dir (see calibre-40), uploads accumulate until server shutdown.
Type: implicit
Confidence: high

### calibre-47
Oracle: within the same function, `os.path.getmtime(os.path.join(fdir, x, 'calibre-book-manifest.json'))` (books.py:110-111) correctly joins the full path, but the deletion call two lines later is `safe_remove(x)` (line 116) with the bare directory name — a direct, self-contained inconsistency in the same block.
Type: in-repo
Confidence: high

### calibre-48
Oracle: `commit()` (http_request.py:189-193): `k, v = line.partition(b':')`; with no colon, `k` is the whole line and `v` is empty, and the only validation (`if not key: raise`) doesn't catch a nonempty key with no colon. RFC 9112 §5.1 defines a header field as requiring `field-name ":" ...`; a line with no colon is not a valid field line and RFC 9112 §5.6 requires it be treated as invalid/rejected.
Type: known-external
Confidence: high

### calibre-49
Oracle: traced directly — `parse_smil_time`'s single-token branch (render_book.py:299-306) checks `x.endswith('s')` before `x.endswith('ms')`; since `'500ms'` also ends with `'s'`, the first (wrong) branch fires and computes `float('500m')`, which raises `ValueError` for input that the next `elif` was clearly meant to handle correctly.
Type: implicit
Confidence: high

### calibre-50
Oracle: RFC 9112 §5.1 states "No whitespace is allowed between the header field-name and colon," and RFC 9112 §5.6 requires servers to reject such messages with 400 specifically to prevent request-smuggling ambiguity; `commit()`'s `key = normalize_header_name(k.strip()...)` (http_request.py:189-190) strips that whitespace and accepts the header instead of rejecting it.
Type: known-external
Confidence: high

### calibre-51
Oracle: `finalize_headers`'s Transfer-Encoding handling is entirely gated by `if self.response_protocol is HTTP11:` (http_request.py:373-381); for an HTTP/1.0 request, `te` stays empty regardless of an actual `Transfer-Encoding` header, so the body is never chunk-read and the conflicting-headers check (`if te: if content_length_values: 400`) never triggers — a request-smuggling-relevant gap per RFC 9112 §6.1 concerns around TE/CL ambiguity, applicable defensively even for downgraded protocol versions.
Type: known-external
Confidence: medium

### calibre-52
Oracle: RFC 6455 §7.4.1 requires the Close frame's Reason to be valid UTF-8; `websocket_close`'s `reason = reason[:123]` (web_socket.py:439) is a raw byte slice that can split a multi-byte UTF-8 sequence.
Type: known-external
Confidence: high

### calibre-53
Oracle: `start, stop = (x.strip() for x in brange.split('-',1))` (http_response.py:138) unconditionally unpacks two values; a spec without `-` (`bytes=5`, `bytes=abc`) yields a one-element split, raising `ValueError: not enough values to unpack`, uncaught, producing a 500 instead of RFC 9110 §14.2's prescribed malformed-header handling (ignore the header / treat as unsatisfiable).
Type: implicit
Confidence: high

### calibre-54
Oracle: `opts.py:105`'s own help text for `max_opds_ungrouped_items`: "Group items... by first letter when there are more than this number of items. **Set to zero to disable.**" The code's condition `if MAX_ITEMS > 0 and len(items) <= MAX_ITEMS:` (opds.py:590) treats `0` as "always exceeded," so setting it to 0 always groups — the opposite of "disable."
Type: in-repo
Confidence: high

### calibre-55
Oracle: `sanitize_sort_field_name` (db/view.py:17-20) shows the codebase's own mapping step (e.g. via `field_metadata.search_term_to_field_key`) is required to turn a user-facing sort term into a valid DB field key; the fallback in `mobile()` (legacy.py:270-272) assigns the literal `sort_by = 'date'` directly, bypassing that mapping, and the retry `db.multisort(...)` is unguarded by any further try/except, so a second failure propagates to 500.
Type: in-repo
Confidence: medium

### calibre-56
Oracle: for a suffix range, `Range(content_length - stop, content_length - 1, stop)` (http_response.py:159-161) with `stop=0` on a 100-byte resource gives `Range(100, 99, 0)` — `start == content_length` is out of bounds and `stop < start`, yet this flows into a 206 with `Content-Range: bytes 100-99/100`, an internally inconsistent byte-range per RFC 9110 §14.4 (`last-pos >= first-pos` is required).
Type: known-external
Confidence: medium

### calibre-57
Oracle: `get_library_init_data`'s handling of `extra_books` (code.py:456-464) calls `book_as_json` for each requested id with no check against `ctx.restriction_for`/the user's library restriction — unlike the restriction enforcement applied to normal search/listing paths elsewhere (e.g. ajax.py's `ctx.search(..., vl=...)`), allowing metadata retrieval for arbitrary book ids outside a restricted user's view.
Type: in-repo
Confidence: medium

### calibre-58
Oracle: `sort_q_values`'s `item()` (utils.py:237-248) does `p, v = r.partition('=')`, and only recognizes the weight when `p == 'q'` exactly; `'fr; q=0.5'` partitions to `p=' q'` (leading space preserved), so it's silently treated as `q=1.0` instead of `0.5` — RFC 9110 §5.6.3 permits optional whitespace (OWS) around `;` in parameter lists.
Type: known-external
Confidence: medium

### calibre-59
Oracle: `fts_reindex` (fts.py, sibling endpoint) explicitly declares `methods=('POST',)` for its state-changing action, but `fts_disable` (fts.py:77) declares no `methods=`, defaulting to `default_methods = frozenset(('HEAD','GET'))` (routes.py:28) — letting a safe/cacheable GET (RFC 9110 §9.2.1: GET/HEAD "ought not have the significance of taking an action other than retrieval") disable full-text search as a side effect.
Type: known-external
Confidence: high

### calibre-60
Oracle: for `bytes=--5`, `brange.split('-',1)` on `'--5'` yields `('', '-5')`, so `stop = int('-5') = -5`; the negative-suffix branch (http_response.py:159-161) computes `Range(content_length - stop, content_length - 1, stop)` = `Range(105, 99, -5)`, producing headers `Content-Length: -5` — a negative content length is not a representable value per RFC 9110 §8.6 (`Content-Length` is a non-negative decimal number).
Type: known-external
Confidence: high

### calibre-61
Oracle: the exception-handling branch inside `job_finished`'s callback try/except logs `job.name` (the inherited `Thread.name`, e.g. `JobsMonitor42`), while the very next block in the same method logs `job.job_name` (jobs.py:239) — `Job.__init__` (jobs.py:27) sets `self.job_name = start_event.name` specifically as the human-meaningful name, confirming `.name` is the wrong attribute for a job-identifying log message.
Type: in-repo
Confidence: high

### calibre-62
Oracle: traced directly — `finalize_headers` (http_request.py:396-399) returns early for `Expect: 100-continue` via `self.set_state(...)` before reaching `self.forwarded_for = inheaders.get('X-Forwarded-For')`, which sits after that branch in the same function, so that assignment never runs for such requests.
Type: in-repo
Confidence: high

### calibre-63
Oracle: `handle_quicklook_client` (render_book.py:902-917) — the request-parsing/response block is written *after* the `for line in inf:` loop closes, so it only runs once with whatever `req` held from the last loop iteration (only the final line gets a response, and only once the client closes its write side, since the `for` loop blocks until EOF); if no line is ever sent, `req` is never assigned inside the loop body, and referencing `req['path']` in the `except` handler raises `UnboundLocalError`.
Type: implicit
Confidence: high

---

Hardest to classify: **calibre-14** (path traversal via `../cover.jpg`) — tracing `add_extra_file` → `path_from_root` shows an explicit, already-existing guard against `..` path components that appears to make the claimed overwrite impossible, so I ended up arguing against the finding rather than for it, and I'm not fully certain I haven't missed an earlier code path that bypasses `path_from_root`. **calibre-27** (request-line desync after a bad URI) and **calibre-51** (Transfer-Encoding ignored on HTTP/1.0) were hard because the "wrongness" depends on RFC 9112's request-smuggling defenses, which are contextual/defense-in-depth guidance rather than a single crisp MUST — I'm confident the behavior is off-spec but less confident it's exploitable in this server's specific state machine without tracing the full read/dispatch loop. **calibre-59** (GET disabling FTS) and **calibre-37** (restriction bypass in a book *count*) were easy to name an oracle for but harder to size as defects, since both are "safety"/access-control violations whose real-world impact (CSRF-triggerable toggle; leaking a count rather than content) is modest even though the violated rule is clear.
