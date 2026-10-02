# calibre, classifier O2 (Claude Opus), blind

### calibre-01
Oracle: RFC 9110 §14.4 grammar: `Range(0, -1, 0)` produces `Content-Range: bytes 0--1/0`, which is not a valid range-resp. RFC 9110 §14.1.1 does call a non-zero suffix-range against a zero-length representation "satisfiable", so the correct outcome (200, or a 206 in some other form) is less clear-cut than the malformed header.
Type: known-external
Confidence: medium

### calibre-02
Oracle: RFC 9110 §12.4.2 says a qvalue of 0 means "not acceptable". `sort_q_values` (utils.py:232-248) keeps q=0 entries, so `acceptable_encoding` returns an encoding the client refused.
Type: known-external
Confidence: high

### calibre-03
Oracle: RFC 9112 §7.1.1 lets a chunk-size line carry chunk-ext (`chunk-size [ chunk-ext ] CRLF`) and says recipients MUST ignore extensions they don't recognise. `int(line.strip(), 16)` rejects every one of them.
Type: known-external
Confidence: high

### calibre-04
Oracle: The `create_file_copy` docstring (content.py:66-70) says a previous copy is reused only "if there have been no changes to the data". A truncated copy with a fresh mtime is served later as if it were complete. The un-closed handle on the exception path is a secondary, implicit leak.
Type: in-repo
Confidence: medium

### calibre-05
Oracle: RFC 9112 §5.2 says obs-fold must be replaced with one or more SP before the value is interpreted. Here the first line keeps its trailing `\r\n` in `self.lines` (http_request.py:186, 209-213), so the stored value contains a CRLF.
Type: known-external
Confidence: high

### calibre-06
Oracle: RFC 9112 §7.1 defines `chunk-size = 1*HEXDIG`. Python's `int(x, 16)` also accepts `0x`, a sign and `_`, so the parser takes framing that other parsers reject (a request-smuggling concern).
Type: known-external
Confidence: medium

### calibre-07
Oracle: RFC 7616 §3.3 says `stale=true` means the credentials were valid and only the nonce expired, so the client may retry without asking the user again. Counting that as a failure contradicts it. The code itself tells the two cases apart (`nonce_is_stale`) and then treats them the same.
Type: known-external
Confidence: medium

### calibre-08
Oracle: The first listening socket is overwritten without being closed, which is a resource leak. `ServerLoop.serve_forever` (loop.py:555-558) always calls `initialize_socket()` itself, so the early call in embedded.py:95 duplicates it. With a pre-activated socket, the second call also drops it and binds fresh.
Type: implicit
Confidence: medium

### calibre-09
Oracle: Every other caller wraps the event in a notify call: `notify_changes(formats_added({book_id: (fmt,)}))` in db/cli/cmd_add_format.py:28, and `ctx.notify_changes(...)` throughout srv/cdb.py (lines 123, 145, 163, 251). Building the event and discarding it does nothing.
Type: in-repo
Confidence: high

### calibre-10
Oracle: The option help for `max_job_time` in opts.py:81 says "Set to zero for no limit." With 0, every job is aborted as soon as it starts.
Type: in-repo
Confidence: high

### calibre-11
Oracle: `from_hex_unicode` raises an uncaught exception on bad client input, which becomes a 500. The same handlers turn other bad input (such as `offset`) into `HTTPNotFound`, which shows the intended handling.
Type: implicit
Confidence: medium

### calibre-12
Oracle: RFC 9112 §9.6 says a server that receives `Connection: close` MUST close the connection after its response. `finalize_headers` (http_request.py:360-365) sets `close_after_response=True`, and `simple_response` then overwrites it with the exception's default `close_connection=False`.
Type: known-external
Confidence: high

### calibre-13
Oracle: I can find nothing showing this is wrong. pyproject.toml:5 declares `requires-python = ">=3.14"`, and Python 3.14 (PEP 758) accepts `except A, B:` without parentheses when there is no `as`. The Python 3.10 SyntaxError doesn't apply to this project.
Type: none
Confidence: low

### calibre-14
Oracle: The claimed behaviour does not happen. `add_extra_file` resolves the path through `path_from_root` (utils/filenames.py:682-684), which raises on any `..` component, and `add_extra_file` then returns None. srv/tests/ajax.py:100-127 tests exactly this traversal. If the write did happen, that test would be the oracle.
Type: in-repo
Confidence: low

### calibre-15
Oracle: Format and identifier Tags are built with `sort=None` (db/fields.py:644, 697), so `getattr(y, 'sort', y.name)` returns None and `.upper()` raises AttributeError, giving a 500. The first loop, a few lines above, already guards with `if not val: val = 'A'`.
Type: implicit
Confidence: high

### calibre-16
Oracle: `GeneratedOutput.content_length` is None (http_response.py:406), and `None >= int` raises TypeError in Python 3. The result is an unhandled exception and a 500.
Type: implicit
Confidence: high

### calibre-17
Oracle: SMIL 3.0 Timing, cited in the comment at render_book.py:290: a Timecount value with no metric defaults to seconds, so `12.5` means 12.5 s and is well formed.
Type: known-external
Confidence: high

### calibre-18
Oracle: Hierarchical items have distinct `original_name` values and search expressions. `category_browse_search_expression` (code.py:346-349) handles hierarchical items specially, so two different items sharing a display leaf name are distinct entries. De-duplicating on `name` drops one.
Type: in-repo
Confidence: medium

### calibre-19
Oracle: RFC 9112 §6.1 and §6.2: a sender MUST NOT send `Content-Length` together with `Transfer-Encoding`, and a chunked body must be chunk-framed. The raw range bytes are written by `write_buf` with no framing. The code also shows ranges were meant to be off for compressible output (`accept_ranges = not compressible ...`), but `ranges` is computed regardless.
Type: known-external
Confidence: high

### calibre-20
Oracle: The SMIL 3.0 clock-value grammar, cited at render_book.py:290, allows a fraction on the seconds field (`Seconds "." Fraction`), so `00:00:59.5` is 59.5 s. Clamping to 59 loses the fraction.
Type: known-external
Confidence: medium

### calibre-21
Oracle: `is_recipe_fmt` in the same file (cdb.py:68-70) strips the `original_` prefix and rejects both `recipe` and `downloaded_recipe` because they "allow code execution". The `cdb_set_fields` check uses a narrower hard-coded tuple.
Type: in-repo
Confidence: high

### calibre-22
Oracle: Not a defect for this project. pyproject.toml requires Python >=3.14, and PEP 758 makes an unparenthesized `except AttributeError, OSError:` legal there.
Type: none
Confidence: low

### calibre-23
Oracle: `dynamic_output` and `GeneratedOutput` explicitly set `accept_ranges = False` (http_response.py:390, 407). The `is not None` test at line 759 still advertises `Accept-Ranges: bytes`, while the `ranges` line (`if output.accept_ranges`) ignores Range. Per RFC 9110 §14.3 the header is a claim of range support.
Type: in-repo
Confidence: medium

### calibre-24
Oracle: `self.method` is a string such as `'GET'`, so `self.method is HTTP1` is always False. Sibling code in the same class uses `self.response_protocol is HTTP1` (simple_response, http_response.py:460) for the same purpose.
Type: in-repo
Confidence: high

### calibre-25
Oracle: The two loops at opds.py:598-604 disagree. The first maps a falsy sort to `'A'`, the second counts with the raw `''`. The groups' counts then contradict the membership the first loop assigned (and `belongs()` at line 745 would also exclude those items).
Type: in-repo
Confidence: medium

### calibre-26
Oracle: RFC 6455 §7.4.2 assigns close codes only up to 4999, and conformance suites treat codes ≥5000 as a protocol error. The code already rejects other invalid ranges (`< 1000`, reserved codes, 1012-2999) at web_socket.py:418 but has no upper bound. The RFC doesn't spell out "MUST reject ≥5000", which keeps confidence down.
Type: known-external
Confidence: medium

### calibre-27
Oracle: The other error exits in `parse_request_line` use the default `close_after_response=True`. Keeping the connection open without reading the headers and body breaks message framing (RFC 9112 §9.6/§6.3), so leftover bytes are parsed as new requests.
Type: in-repo
Confidence: high

### calibre-28
Oracle: RFC 9112 §7.1 and §7.1.2 define `chunked-body = *chunk last-chunk trailer-section CRLF`, so trailer fields after the zero-size chunk are legal and must be accepted (they may be discarded).
Type: known-external
Confidence: high

### calibre-29
Oracle: The data-files API is scoped to the `data/` directory. `get_data_file` (content.py:611-615) only serves entries matching `DATA_FILE_PATTERN`, and `upload_data_files` prefixes `DATA_DIR_NAME`. `remove_data_files` passes client relpaths unfiltered to a permanent delete of the book directory.
Type: in-repo
Confidence: high

### calibre-30
Oracle: `simple_response`, `send_range_not_satisfiable` and `send_not_modified` all use `self.response_protocol`, and `job_done` hard-codes `HTTP11`. That inconsistency is the only oracle I have. RFC 9110 §6.2 actually recommends answering with the highest version the server supports, so HTTP/1.1 to an HTTP/1.0 client is allowed.
Type: in-repo
Confidence: low

### calibre-31
Oracle: The loop variable is `x`, but the call uses the stale `s`. The sibling loop two lines above, `for s, conn in remove: self.close(s, conn)` (loop.py:610-612), shows the intended pairing.
Type: in-repo
Confidence: high

### calibre-32
Oracle: RFC 9112 §6.1: a server MUST NOT send `Transfer-Encoding` in a response unless the request indicates HTTP/1.1 or later. The `is_http1` parameter exists, but it doesn't gate the chunked path at lines 793-794.
Type: known-external
Confidence: high

### calibre-33
Oracle: The tagline in the same function computes `end = 25 < total = 26` and renders "Books 1 to 25 of 26", yet `total > start + num` (26 > 26) suppresses Next/Last. That is an off-by-one, since the condition should be `end < total`.
Type: in-repo
Confidence: high

### calibre-34
Oracle: RFC 9112 §6.3: a response with neither `Content-Length` nor `Transfer-Encoding` is delimited by connection close, so a kept-alive connection leaves the client waiting. The sibling `send_not_modified` (http_response.py:531-541) does send `Content-Length: 0`.
Type: known-external
Confidence: high

### calibre-35
Oracle: `data_file` (content.py:589-597) takes the same `content_disposition` query parameter and calls `add_sandbox_headers`. That function's docstring (content.py:199-205) says it exists to stop user-supplied content "rendered inline" from scripting the server origin. `book_fmt` skips it.
Type: in-repo
Confidence: high

### calibre-36
Oracle: RFC 9112 §7.1 defines chunk-size as `1*HEXDIG`, which has no sign. The `max_request_body_size` check in http_request.py:430-434 shows the intended limit, and adding a negative size to the counter defeats it.
Type: known-external
Confidence: high

### calibre-37
Oracle: The empty-query branch reports the restricted `total_num`, and `number_of_books_in_virtual_library` has a `search_restriction` parameter (db/cache.py:1889) that isn't passed. The two branches of one field disagree on scope, and the non-empty one leaks a count outside the user's restriction.
Type: in-repo
Confidence: medium

### calibre-38
Oracle: The comment at convert.py:45, "sanitize output_fmt to prevent path traversal", states the intent. The same unsanitized value goes to `convert_book`, where `os.path.abspath('output.' + output_fmt)` resolves outside the job directory. `Plumber` derives the format from `splitext`, so `.epub` still validates.
Type: in-repo
Confidence: high

### calibre-39
Oracle: The built-in `rating` branch (code.py:341-344) converts stars to a number because the rating search needs one. db/search.py:302-330 casts rating queries with `int()` and raises "Non-numeric value in query" otherwise. Custom rating columns skip that conversion.
Type: in-repo
Confidence: high

### calibre-40
Oracle: `rd.tdir` is one directory for the whole server (loop.py:536-537). Elsewhere the code isolates per-request temp data with `tempfile.mkdtemp(dir=rd.tdir)` (convert.py:166). Here a fixed name derived from user input is used, so same-named concurrent uploads collide.
Type: in-repo
Confidence: medium

### calibre-41
Oracle: The pruning loop (auth.py:52-58) is meant to drop entries older than `interval`. The key just re-inserted with timestamp `now` is always last in the dict, so `reversed()` reaches it first and breaks. Nothing is ever pruned.
Type: in-repo
Confidence: high

### calibre-42
Oracle: The pruning loop shows the intent that failures older than `interval` should stop counting, and `is_banned` time-limits bans to `interval`. Because pruning never happens (calibre-41), old counts persist and a single failure re-bans. Only the code's apparent intent supports this. There is no doc or test.
Type: in-repo
Confidence: medium

### calibre-43
Oracle: `book_fmt` puts `repr(cpb)` into `extra_etag_data`, which acknowledges that the plugboard changes the output. The `create_file_copy` docstring promises to reuse a copy only when nothing about the data has changed, but the cache check compares mtime only.
Type: in-repo
Confidence: medium

### calibre-44
Oracle: `restrictions()` returns `.copy()` of the `lru_cache`d result (users.py:236), which shows callers are meant to get an independent dict. The copy is shallow, and manage_users_cli.py:191-197 mutates the nested `library_restrictions` in place.
Type: in-repo
Confidence: medium

### calibre-45
Oracle: Not a defect for this project. `requires-python = ">=3.14"` (pyproject.toml:5), and PEP 758 allows `except ValueError, UnicodeDecodeError:`.
Type: none
Confidence: low

### calibre-46
Oracle: This is a disk resource leak. Every uploaded file, plus any import-plugin output, stays in the server temp dir until the `TemporaryDirectory` is torn down at shutdown (loop.py:536).
Type: implicit
Confidence: medium

### calibre-47
Oracle: Two lines earlier the same loop builds the real path as `os.path.join(fdir, x, 'calibre-book-manifest.json')`. `safe_remove(x)` passes only the bare name, which resolves relative to the CWD.
Type: in-repo
Confidence: high

### calibre-48
Oracle: RFC 9112 §5 defines `field-line = field-name ":" OWS field-value OWS`, so a line with no colon is malformed and should be rejected with 400. The parser raises only when the key is empty.
Type: known-external
Confidence: medium

### calibre-49
Oracle: The `elif x.endswith('ms')` branch (render_book.py:301-302) can never run because `endswith('s')` is tested first. The dead branch shows `ms` was meant to be supported, and SMIL 3.0 lists `ms` as a metric.
Type: in-repo
Confidence: high

### calibre-50
Oracle: RFC 9112 §5.1: "A server MUST reject, with a response status code of 400 (Bad Request), any received request message that contains whitespace between a header field name and colon."
Type: known-external
Confidence: high

### calibre-51
Oracle: RFC 9112 §6.1 says a server that receives an HTTP/1.0 message containing `Transfer-Encoding` MUST treat the framing as faulty and close the connection after processing. The code only looks at TE for HTTP/1.1.
Type: known-external
Confidence: high

### calibre-52
Oracle: RFC 6455 §5.5.1 requires the close reason to be UTF-8. The server itself rejects non-UTF-8 reasons from clients (web_socket.py:413-416), but byte-truncating at 123 can emit one.
Type: known-external
Confidence: medium

### calibre-53
Oracle: Unpacking `brange.split('-', 1)` raises ValueError when there is no `-`. The exception escapes and becomes a 500. Every other malformed form in `get_ranges` is skipped with `continue`, and the test `bytes=a-2` in tests/http.py:139 expects malformed specs to be dropped.
Type: implicit
Confidence: high

### calibre-54
Oracle: The option help for `max_opds_ungrouped_items` (opts.py:105) says "Set to zero to disable" grouping. The code groups everything when the value is 0.
Type: in-repo
Confidence: high

### calibre-55
Oracle: The normal path passes `'date'` through `sanitize_sort_field_name`, which maps it to `timestamp` via `search_term_to_field_key` (field_metadata.py:435). The fallback hands the raw `'date'` to `multisort`, which raises KeyError.
Type: in-repo
Confidence: high

### calibre-56
Oracle: RFC 9110 §14.1.1/§14.1.2: a suffix-range with suffix-length 0 is unsatisfiable, so the correct answer is 416. `bytes 100-99/100` is also not a valid Content-Range.
Type: known-external
Confidence: high

### calibre-57
Oracle: Everywhere else, per-book endpoints check the library restriction with `ctx.has_id(rd, db, book_id)` (for example `get_db_for_data_file`, content.py:600-606). `extra_books` ids go straight to `book_as_json` without that check.
Type: in-repo
Confidence: high

### calibre-58
Oracle: RFC 9110 §12.4.2 defines `weight = OWS ";" OWS "q=" qvalue`, so whitespace after the semicolon is legal. The parser compares `' q'` to `'q'` and ignores the weight.
Type: known-external
Confidence: high

### calibre-59
Oracle: The sibling state-changing endpoints in the same file (`/fts/reindex` at fts.py:85 and `/fts/indexing` at line 103) restrict to `methods=('POST',)`. `/fts/disable` uses the default methods, so a GET changes state (RFC 9110 §9.2.1 safe methods).
Type: in-repo
Confidence: medium

### calibre-60
Oracle: RFC 9110 §14.1.1 defines `suffix-range = "-" suffix-length` with `suffix-length = 1*DIGIT`, so `--5` is invalid and should be ignored. The code produces a negative Content-Length and an impossible Content-Range.
Type: known-external
Confidence: high

### calibre-61
Oracle: `Job` is a Thread named `JobsMonitor{id}` (jobs.py:24), and a few lines later in the same function the other error log uses `job.job_name` (jobs.py:238). This is a cosmetic defect.
Type: in-repo
Confidence: high

### calibre-62
Oracle: On the non-Expect path, `self.forwarded_for` is set from `X-Forwarded-For` before the body is read. Both `RequestData` and `log_access` consume it. The 100-continue branch returns before that line.
Type: in-repo
Confidence: high

### calibre-63
Oracle: The `quicklook_service` docstring (render_book.py:920-930) says clients can send several newline-separated requests and get newline-separated responses. The dedented block answers only the last one. The UnboundLocalError on an empty stream is also an implicit crash.
Type: in-repo
Confidence: high

The hardest to classify were the three `except A, B:` findings (13, 22, 45). They describe a real SyntaxError under 3.10, but the checkout declares Python ≥3.14, where PEP 758 makes that syntax legal. The oracle there shows the behaviour is *not* wrong, and none of the types really fits that. calibre-14 was similar: the traversal it describes is blocked by `path_from_root`, and a repo test covers exactly that case. calibre-01 was awkward because RFC 9110 §14.1.1 calls a non-zero suffix-range on an empty representation satisfiable, yet the 206 the code produces is malformed. calibre-30 had only an in-repo inconsistency, which the RFC itself contradicts. For 23, 40, 42 and 44 the oracle is the code's evident intent (an explicit `.copy()`, an explicit `accept_ranges=False`, a pruning loop) rather than a stated contract, so I held them at medium. In the HTTP-framing findings I often had both an in-repo contrast and an RFC, and I picked whichever I would actually rely on.
