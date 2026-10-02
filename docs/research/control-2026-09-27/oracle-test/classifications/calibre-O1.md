# calibre, classifier O1 (Claude Opus), blind

### calibre-01
Oracle: RFC 9110 §14.1.1 treats a non-zero suffix range on a zero-length representation as satisfiable. So the 206 status itself can be argued. The resulting `Content-Range: bytes 0--1/0` still violates the Content-Range grammar (RFC 9110 §14.4), and the spec is unclear on what a server should send here.
Type: known-external
Confidence: medium

### calibre-02
Oracle: RFC 9110 §12.4.2 says a qvalue of 0 means "not acceptable". `acceptable_encoding` returns `gzip` even though the client excluded it.
Type: known-external
Confidence: high

### calibre-03
Oracle: RFC 9112 §7.1 defines `chunk = chunk-size [ chunk-ext ] CRLF`, and §7.1.1 says a recipient MUST ignore unrecognized chunk extensions. `int(line.strip(), 16)` rejects them instead.
Type: known-external
Confidence: high

### calibre-04
Oracle: The `create_file_copy` docstring says the cached copy is reused only "if there have been no changes to the data". A partial file left with a fresh mtime passes the `previous_mtime < mt` check and is served as a good cache hit. The unclosed handle is a leak on top of that (implicit).
Type: in-repo
Confidence: high

### calibre-05
Oracle: RFC 9112 §5.2 says a server must either reject obs-fold with 400 or replace each fold with SP before interpreting. The value keeps a raw CRLF because the stored lines still end in `\r\n` when `commit()` joins them with `b' '`.
Type: known-external
Confidence: high

### calibre-06
Oracle: RFC 9112 §7.1 defines `chunk-size = 1*HEXDIG`. Python's `int(x, 16)` also accepts the `0x` prefix, a sign and underscores, which is lenient parsing with request-smuggling potential.
Type: known-external
Confidence: medium

### calibre-07
Oracle: RFC 7616 §3.3 defines `stale=true` for a request whose credentials were valid but whose nonce had expired. The client is expected to retry, so this is not a failed login. The code already computes `nonce_is_stale` so it can send that challenge, yet it still calls `ban_list.failed()`.
Type: known-external
Confidence: medium

### calibre-08
Oracle: A second socket is created, bound and set up while the first is never closed. That is a file-descriptor/socket leak. The double bind also depends on SO_REUSEADDR semantics.
Type: implicit
Confidence: high

### calibre-09
Oracle: Every other mutating path calls `ctx.notify_changes(db.backend.library_path, <event>(...))`, e.g. cdb.py:123 `ctx.notify_changes(..., books_added(ids))`. At convert.py:252 the event from `formats_added(...)` is built and thrown away.
Type: in-repo
Confidence: high

### calibre-10
Oracle: The help text for `max_job_time` in opts.py says "Set to zero for no limit." Zero makes `delta <= 0` for every job, so every job is aborted.
Type: in-repo
Confidence: high

### calibre-11
Oracle: `from_hex_unicode` on non-hex input raises an uncaught exception, so the client gets a 500. The same handlers turn a bad `offset` into `HTTPNotFound`.
Type: implicit
Confidence: high

### calibre-12
Oracle: RFC 9112 §9.6 says a server that receives `Connection: close` MUST close after the final response. `finalize_headers` sets `close_after_response = True` for exactly that case (in-repo intent), and `simple_response` then overwrites it with `e.close_connection` (default False) or with False for TRACE.
Type: known-external
Confidence: high

### calibre-13
Oracle: Nothing. pyproject.toml has `requires-python = ">=3.14"`, and PEP 758 (Python 3.14) allows unparenthesized `except A, B:` without `as`. Behaviour under 3.10 does not apply.
Type: none
Confidence: low

### calibre-14
Oracle: None found; the in-repo code contradicts the finding. `add_extra_file` resolves the path through `path_from_root` (utils/filenames.py:682-684), which raises on any `..` component, so `data/../cover.jpg` returns None and nothing is written. srv/tests/ajax.py covers this traversal case.
Type: none
Confidence: low

### calibre-15
Oracle: `Tag` objects for identifiers and formats are built with `sort=None` (db/fields.py:644, 697). `getattr(y, 'sort', y.name).upper()` then raises `AttributeError`, and the request gets a 500. The loop just above guards the same value with `if not val: val = 'A'`.
Type: implicit
Confidence: high

### calibre-16
Oracle: `GeneratedOutput.content_length` is None, and `None >= int` raises `TypeError` before `acceptable_encoding` is even evaluated. The request fails with a 500.
Type: implicit
Confidence: high

### calibre-17
Oracle: The SMIL 3 timing grammar cited in the function's own comment (`Timecount-val ::= Timecount ("." Fraction)? (Metric)?`) makes the metric optional, with seconds as the default. A bare `12.5` is valid.
Type: known-external
Confidence: high

### calibre-18
Oracle: For hierarchical items, metadata.py:167-168 keeps `original_name` separate from the display `name`. `category_browse_items` itself builds each item's search from `original_name`, which shows these are distinct items. De-duplicating on `name` merges them.
Type: in-repo
Confidence: medium

### calibre-19
Oracle: RFC 9112 §6.2 says a sender MUST NOT send Content-Length in a message that has Transfer-Encoding. Here the `Range` branch of `write_response_body` writes raw bytes under a `chunked` header, so the framing is broken. The line `accept_ranges = not compressible` shows the code meant compression and ranges to be exclusive.
Type: known-external
Confidence: high

### calibre-20
Oracle: SMIL 3 clock values allow a fractional part on the seconds field (`Seconds ::= DIGIT DIGIT` plus optional `.Fraction`, range 00-59), so 59.5 is valid. `min(abs(seconds), 59)` clamps away the fraction. The error is at most half a second.
Type: known-external
Confidence: medium

### calibre-21
Oracle: `is_recipe_fmt` at cdb.py:68-70 blocks both `recipe` and `downloaded_recipe`, and recipe_input.py:20 accepts `downloaded_recipe` as an executable input. cdb.py:226 uses its own list, which leaves out `downloaded_recipe`.
Type: in-repo
Confidence: high

### calibre-22
Oracle: Nothing. The project requires Python 3.14 (pyproject.toml), where PEP 758 makes `except AttributeError, OSError:` valid.
Type: none
Confidence: low

### calibre-23
Oracle: `dynamic_output` and `GeneratedOutput` explicitly set `accept_ranges = False`, but finalize_output tests `output.accept_ranges is not None`, which is always true. The server advertises byte ranges it will not serve.
Type: in-repo
Confidence: high

### calibre-24
Oracle: `self.method` is a string like `'GET'`, so `self.method is HTTP1` is always False. The code elsewhere compares the protocol with `self.response_protocol is HTTP1` (e.g. `simple_response`, http_response.py:460). RFC 9112 §6.1 also forbids sending Transfer-Encoding to an HTTP/1.0 client.
Type: in-repo
Confidence: high

### calibre-25
Oracle: The first loop maps an empty sort value to group `'A'`. The counting loop (and `belongs()` in `opds_categorygroup`) does not apply the same fallback, so those items never appear in any group count.
Type: in-repo
Confidence: medium

### calibre-26
Oracle: RFC 6455 §7.4.2 defines close codes only up to 4999, and an undefined code should be failed as a protocol error. The existing check (`< 1000`, reserved codes, `1011 < code < 3000`) shows the intent to reject invalid codes but has no upper bound.
Type: known-external
Confidence: high

### calibre-27
Oracle: Every other error in `parse_request_line` uses the default `close_after_response=True`. The `parse_uri` failure alone keeps the connection open before the headers are consumed, so the header lines are then parsed as new request lines.
Type: in-repo
Confidence: high

### calibre-28
Oracle: RFC 9112 §7.1 defines `chunked-body = *chunk last-chunk trailer-section CRLF`, so trailer fields after the last chunk are legal. They are rejected here.
Type: known-external
Confidence: high

### calibre-29
Oracle: The endpoint is `/data-files/remove`. The upload side prefixes `DATA_DIR_NAME/`, and `get_data_file` only serves paths matching `DATA_FILE_PATTERN` (`data/**/*`). Remove applies no such restriction and permanently deletes files the database still tracks.
Type: in-repo
Confidence: high

### calibre-30
Oracle: `simple_response`, `send_range_not_satisfiable` and `send_not_modified` all use `self.response_protocol`, while `job_done` hard-codes `HTTP11`. That is an internal inconsistency. However, RFC 9110 §6.2 says a server SHOULD send the highest version it conforms to, so HTTP/1.1 is arguably correct.
Type: in-repo
Confidence: low

### calibre-31
Oracle: The loop is `for x, conn in close_needed: self.close(s, conn)`, so it uses a stale `s`. The sibling loop directly above is `for s, conn in remove: self.close(s, conn)`.
Type: in-repo
Confidence: high

### calibre-32
Oracle: RFC 9112 §6.1 (and RFC 7230 §3.3.1) say a server MUST NOT send Transfer-Encoding unless the request indicates HTTP/1.1 or later. The `output.content_length is None` branch ignores `is_http1`.
Type: known-external
Confidence: high

### calibre-33
Oracle: `build_navigation` itself computes the page as `start..start+num-1`, so a next page exists when `total >= start + num`. The test `total > start + num` is off by one.
Type: in-repo
Confidence: high

### calibre-34
Oracle: RFC 9112 §6.3 says a response without Content-Length or Transfer-Encoding (other than 1xx/204/304) is delimited by connection close. Keeping the connection alive leaves the client unable to find the end of the message. `send_not_modified` next to it does send `Content-Length: 0`.
Type: known-external
Confidence: high

### calibre-35
Oracle: The `add_sandbox_headers` docstring (content.py:199-205) says it exists to stop user content rendered inline from scripting the server's origin. `data_file`, with the same `content_disposition` query handling, calls it; `book_fmt` does not.
Type: in-repo
Confidence: high

### calibre-36
Oracle: RFC 9112 §7.1 allows only HEXDIG in `chunk-size`, so a sign is invalid. The negative value also reduces `bytes_read`, which defeats the `max_request_body_size` check that exists in the same function.
Type: known-external
Confidence: high

### calibre-37
Oracle: With an empty query, `num_books_without_search` is the restricted `total_num`. `number_of_books_in_virtual_library` takes a `search_restriction` parameter that is not passed, so the count includes books outside the user's restriction.
Type: in-repo
Confidence: high

### calibre-38
Oracle: `JobStatus.__init__` carries the comment "sanitize output_fmt to prevent path traversal" but sanitizes only its own copy. `convert_book` builds `output_path` from the raw value. The plumber's validation only looks at the extension (plumber.py:927), so the traversal string passes.
Type: in-repo
Confidence: high

### calibre-39
Oracle: The built-in `rating` branch in the same function converts stars to `rating:N`. Custom rating columns skip that branch and produce `"=★★★"`, which the numeric search raises on (db/search.py:330 "Non-numeric value in query").
Type: in-repo
Confidence: high

### calibre-40
Oracle: `convert.py` `queue_job` gives each job its own `tempfile.mkdtemp(dir=rd.tdir)`. `cdb_add_book` writes to a fixed name in the shared server `tdir` (loop.py:536), so concurrent uploads with the same name collide.
Type: in-repo
Confidence: medium

### calibre-41
Oracle: The pruning loop is clearly meant to drop entries older than `interval`. Walking `reversed()` hits the just-inserted entry first and breaks immediately, so nothing is ever pruned and the dict grows without bound (also an implicit memory leak).
Type: in-repo
Confidence: high

### calibre-42
Oracle: The pruning loop shows the intent that failures older than `interval` are forgotten, which would reset the count. Because pruning never runs (calibre-41), old counts persist. Keeping counts could otherwise be read as a design choice.
Type: in-repo
Confidence: medium

### calibre-43
Oracle: `book_fmt` passes `extra_etag_data=repr(cpb)` precisely so a plugboard change counts as a content change. `create_file_copy`'s cache check uses only mtime, contrary to its docstring ("no changes to the data"), so stale content is served under a new ETag.
Type: in-repo
Confidence: high

### calibre-44
Oracle: `restrictions()` calls `.copy()`, which shows it means to protect the `lru_cache` result. The copy is shallow, so `manage_users_cli.py:191-196` mutates the shared nested dict. The impact is limited to the same process.
Type: in-repo
Confidence: medium

### calibre-45
Oracle: Nothing. Under the project's required Python 3.14 (PEP 758), `except ValueError, UnicodeDecodeError:` is valid syntax.
Type: none
Confidence: low

### calibre-46
Oracle: The upload file and any import-plugin output are never removed and accumulate in the server temp dir until shutdown. That is a disk resource leak.
Type: implicit
Confidence: medium

### calibre-47
Oracle: The same function builds paths with `os.path.join(fdir, x, ...)` for the mtime check, but calls `safe_remove(x)` with the bare name. The wrong directory is removed.
Type: in-repo
Confidence: high

### calibre-48
Oracle: RFC 9112 §5 defines `field-line = field-name ":" OWS field-value OWS`, so a line with no colon is malformed and should get a 400. The parser already raises "Malformed header line" when the key is empty, which shows it means to reject malformed lines.
Type: known-external
Confidence: medium

### calibre-49
Oracle: The function has an explicit `endswith('ms')` branch that can never be reached because `endswith('s')` is tested first. That branch shows the intended behaviour.
Type: in-repo
Confidence: high

### calibre-50
Oracle: RFC 9112 §5.1 says a server MUST reject, with 400, any request containing whitespace between a field name and the colon.
Type: known-external
Confidence: high

### calibre-51
Oracle: RFC 9112 §6.1 says a server receiving an HTTP/1.0 message with Transfer-Encoding MUST treat the framing as faulty and close the connection after processing it. Here the unread body is parsed as the next request.
Type: known-external
Confidence: medium

### calibre-52
Oracle: RFC 6455 §5.5.1 requires the close-frame reason to be UTF-8. The same file validates incoming close reasons as UTF-8, but the byte-level `reason[:123]` can split a multi-byte character.
Type: known-external
Confidence: medium

### calibre-53
Oracle: The tuple unpack of `brange.split('-', 1)` raises `ValueError`, which is uncaught, so the client gets a 500. The rest of `get_ranges` carefully returns None or `continue`s on malformed input.
Type: implicit
Confidence: high

### calibre-54
Oracle: The help text for `max_opds_ungrouped_items` in opts.py says "Set to zero to disable" (grouping). The check `MAX_ITEMS > 0 and ...` makes zero group every category.
Type: in-repo
Confidence: high

### calibre-55
Oracle: The normal path passes `'date'` through `sanitize_sort_field_name`, which maps it to the real field key. The fallback uses the raw `'date'`, and `multisort` raises `KeyError` on it (db/cache.py:1780-1785), giving a 500.
Type: in-repo
Confidence: high

### calibre-56
Oracle: RFC 9110 §14.1.1 says a suffix range is satisfiable only with a non-zero suffix-length, so `bytes=-0` should get a 416. `Content-Range: bytes 100-99/100` is also invalid under §14.4.
Type: known-external
Confidence: high

### calibre-57
Oracle: Other endpoints in the same file check `ctx.has_id(rd, db, book_id)` (code.py:633, 656) to enforce library restrictions. The `extra_books` ids skip that check.
Type: in-repo
Confidence: high

### calibre-58
Oracle: RFC 9110 §12.4.2 defines `weight = OWS ";" OWS "q=" qvalue`, so whitespace after the semicolon is allowed. `p == 'q'` fails on `' q'`.
Type: known-external
Confidence: high

### calibre-59
Oracle: The sibling state-changing FTS endpoints (`/fts/reindex`, `/fts/indexing`) are declared `methods=('POST',)`, and RFC 9110 §9.2.1 says GET must be safe. `/fts/disable` omits the restriction.
Type: in-repo
Confidence: medium

### calibre-60
Oracle: `--5` does not match the RFC 9110 §14.1.1 range grammar, so the header should be ignored. Instead the code emits `Content-Length: -5` and `Content-Range: bytes 105-99/100`, which are impossible values.
Type: known-external
Confidence: high

### calibre-61
Oracle: The next log line in the same function uses `job.job_name`. `job.name` is the Thread name `JobsMonitor{id}` (jobs.py:24). This is cosmetic.
Type: in-repo
Confidence: medium

### calibre-62
Oracle: The non-Expect path sets `self.forwarded_for` from the header. The Expect branch returns before that line, and `write_continue`/`read_request_body` never set it.
Type: in-repo
Confidence: high

### calibre-63
Oracle: The `quicklook_service` docstring says clients may send multiple newline-separated requests and get newline-separated responses. The response block is outside the loop, so only the last request is answered. With no lines, the `except` handler's `req['path']` raises an uncaught `UnboundLocalError` (implicit).
Type: in-repo
Confidence: high

### Hardest to classify

These were the hardest:

- **calibre-13, 22 and 45** are correct as observations about Python 3.10. The checkout targets Python 3.14, where PEP 758 makes the syntax valid, so I classed them as `none` with low confidence.
- **calibre-14** looked like a clear traversal. Reading `path_from_root` and the existing traversal tests shows the path is rejected, so I found no oracle for a defect.
- **calibre-01 and calibre-30** are borderline because the external spec partly allows what the code does. RFC 9110 counts a non-zero suffix range on empty content as satisfiable, and it recommends HTTP/1.1 in the status line. Only the malformed Content-Range and the in-repo inconsistency remain.
- **calibre-42 and calibre-44** needed judgment about design intent. Keeping failure counts could be deliberate. The shared-cache mutation only shows up within a single process.
- **Several HTTP-framing findings** (calibre-12, 19, 24, 32) had both an in-repo and an RFC oracle, so I had to choose which one to rely on.
