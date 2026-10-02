# aiohttp, classifier O1 (Claude Opus), blind

### aiohttp-01
Oracle: The `_read` docstring (payload.py ~520) says the chunk is read "respecting the remaining_content_len limit if specified", but `remaining_content_len or DEFAULT_CHUNK_SIZE` treats a specified 0 as unset. The practical harm is small, because `_set_or_restore_start_position` rewinds before any later write.
Type: in-repo
Confidence: medium

### aiohttp-02
Oracle: The sibling `decode_iter`/`_decode_content_async` (multipart.py:593-633) keeps decompressing `while d.data_available`. The sync `decode()` makes one capped `decompress_sync(..., max_length=self._max_decompress_size)` call and silently drops everything after the first 256 KiB.
Type: in-repo
Confidence: high

### aiohttp-03
Oracle: RFC 9110 §11.6.1 (and RFC 7235) allows a 401 to carry several challenges, in separate `WWW-Authenticate` fields or comma-joined. `HeadersDictProxy.__getitem__` joins them with ", ", so partitioning on the first space and checking only the first scheme ignores the valid Digest challenge.
Type: known-external
Confidence: high

### aiohttp-04
Oracle: `StreamWriter.write` (http_writer.py:190-198) truncates each chunk to `self.length`, but `write_eof(chunk)` has no such check. RFC 9112 §6 also says a body longer than the declared Content-Length breaks message framing.
Type: in-repo
Confidence: high

### aiohttp-05
Oracle: The `AccessLogger` class docstring (web_log.py:44) documents `%{FOO}e  os.environ['FOO']` and the `compile_format` docstring names `_format_e`. Neither the `'e'` map entry nor the method exists, so a documented format crashes with KeyError.
Type: in-repo
Confidence: high

### aiohttp-06
Oracle: RFC 8288 §3 defines link-value as `"<" URI-Reference ">"`, and a URI may contain commas. The generic list splitter in `getall` only protects quoted-strings and comments, not `<...>`, so one link gets cut in two and its `rel` is lost.
Type: known-external
Confidence: high

### aiohttp-07
Oracle: docs/client_reference.rst:481-482 says "Maximum number of redirects to follow. TooManyRedirects is raised if the number is exceeded". `redirects >= max_redirects` raises when the count equals the maximum, not when it exceeds it. However, tests/test_client_functional.py:1640-1656 (history length 2 with max_redirects=2) is consistent with the current code.
Type: in-repo
Confidence: medium

### aiohttp-08
Oracle: RFC 9110 §12.5.3 says a coding with qvalue 0 is "not acceptable", and `gzip;q=0` must not be chosen. A substring test `value in accept_encoding` ignores q-values entirely.
Type: known-external
Confidence: high

### aiohttp-09
Oracle: The sibling branch in the same `write_eof` (web_response.py:690-694) wraps Payload writing in `try/finally: await self._body.close()`. The empty-body branch skips that close and leaves the file open, which is also a plain resource leak.
Type: in-repo
Confidence: high

### aiohttp-10
Oracle: docs/streams.rst:82-85 says `readuntil` means "Read until separator". The loop only searches for the separator inside `self._buffer[0]`, so a separator split across two fed chunks is missed and the read runs on to the next occurrence.
Type: in-repo
Confidence: high

### aiohttp-11
Oracle: The temporary jar deliberately copies the session jar's settings (`unsafe=self._cookie_jar.unsafe, quote_cookie=self._cookie_jar.quote_cookie`, client.py:647-649) but leaves out `treat_as_secure_origin` (cookiejar.py:87, 449-453). Per-request cookies therefore follow different Secure rules from session cookies.
Type: in-repo
Confidence: medium

### aiohttp-12
Oracle: I can't point to anything that requires upper-casing. RFC 9110 §9.1 says methods are case-sensitive, both in-repo callers pass `request.method` (already upper-cased), and tests/test_web_exceptions.py only checks that the value passes through.
Type: none
Confidence: low

### aiohttp-13
Oracle: Construction crashes with an uncaught `KeyError`. `FORMAT_RE` (web_log.py:62) explicitly accepts `O`, but there is no map entry or `_format_O`. `%O` is not in the docstring or docs/logging.rst, so the only evidence it was meant to be supported is the regex.
Type: implicit
Confidence: medium

### aiohttp-14
Oracle: The same function closes `tmp` before raising on the mid-read size check (web_request.py:832-837). `_finish()` (946-953) is commented "Release the temp files created within multipart request body". Both show the intent that temp files get closed, and the early-raise path leaks the ones already built.
Type: in-repo
Confidence: medium

### aiohttp-15
Oracle: `EmptyStreamReader.__init__` never sets the `total_compressed_bytes` slot, so the inherited property raises AttributeError.
Type: implicit
Confidence: high

### aiohttp-16
Oracle: An `AssertionError` escapes to the caller for a valid RFC 7578 §4.6 `_charset_` part. `read_chunk(32)` is smaller than the `_read_chunk_from_stream` precondition `size >= self._boundary_len` whenever the boundary is 30 characters or longer.
Type: implicit
Confidence: high

### aiohttp-17
Oracle: Parsing a well-formed body raises `InvalidHeader` or produces garbage headers. The normal path in the same `next()` runs `_maybe_release_last_part()` and `_read_boundary()` before `fetch_next_part()`, and the `_charset_` path skips both.
Type: implicit
Confidence: high

### aiohttp-18
Oracle: An empty body is not valid JSON (RFC 8259), so raising is defensible. The existing test `test_json_no_content` (tests/test_client_response.py:836-858) asserts exactly this `JSONDecodeError`.
Type: none
Confidence: low

### aiohttp-19
Oracle: `MultipartReader._readline` (multipart.py:873-876) exists to honour `self._unread`, and `_read_boundary` pushes lines onto `_unread` "to be handed to the parent". `_read_headers` reads `self._content` directly and bypasses the lines pushed back. The body is valid per RFC 2046 (the CRLF before `--outer` belongs to the outer delimiter).
Type: in-repo
Confidence: high

### aiohttp-20
Oracle: I can't point to a contract. The cache is bounded at 64 entries, and holding middleware objects after a session closes is a design trade-off rather than a demonstrable leak or a documented violation.
Type: none
Confidence: low

### aiohttp-21
Oracle: Every other exit from the redirect loop calls `await req._body.close()` (client.py:774-775, 832-833, 842-843, 861-862). The 303 / POST-302 path drops `data` without closing the old payload, which leaks the file.
Type: in-repo
Confidence: high

### aiohttp-22
Oracle: `prepare()` raises an uncaught `AssertionError` (`assert self._body is not None`, web_response.py:~732), or `TypeError` under `-O`, for an ordinary empty or 204 response with compression enabled.
Type: implicit
Confidence: high

### aiohttp-23
Oracle: docs/client_reference.rst:1554-1555 tells users "To access all cookies ... use response.headers.getall('Set-Cookie')". Splitting at the comma inside `Expires=` breaks that documented use. RFC 9110 §5.3 also exempts Set-Cookie from list combining, and Date is not list-valued.
Type: in-repo
Confidence: high

### aiohttp-24
Oracle: The comment in web_fileresponse.py:381-389 quotes RFC 7233: a byte-range-set is satisfiable only with "at least one suffix-byte-range-spec with a non-zero suffix-length ... Otherwise ... unsatisfiable". `bytes=-0` should therefore get a 416, not a 206 with the full body.
Type: in-repo
Confidence: high

### aiohttp-25
Oracle: RFC 6265 §5.3 (steps 3 and 11) says a replacement cookie with no Max-Age/Expires is a non-persistent cookie and replaces the old one's expiry. The stale `_expirations` entry wrongly expires the new cookie.
Type: known-external
Confidence: high

### aiohttp-26
Oracle: RFC 6265 §5.2.3 says to convert the cookie-domain to lower case, and §5.1.3 domain-matching works on canonicalized (lower-case) strings. `_is_domain_match`'s docstring claims "adhering to RFC 6265".
Type: known-external
Confidence: high

### aiohttp-27
Oracle: RFC 7239 §4 separates elements with commas, but the property's loop never sees one. `headers.getall(FORWARDED)` (helpers.py:788) already splits field-values at top-level commas, so the input described can't reach the loop in practice.
Type: none
Confidence: low

### aiohttp-28
Oracle: The only caller (web_app.py:382-383) invokes the expect handler only `if request.headers.get(hdrs.EXPECT)`. Calling it without an Expect header is outside its contract, and its docstring says it raises when the value is not "100-continue".
Type: none
Confidence: low

### aiohttp-29
Oracle: `HeadersDictProxy` subclasses `collections.abc.Mapping`, whose equality contract compares as `dict(self.items()) == dict(other.items())`. Delegating to `CIMultiDict.__eq__` makes two identical proxies unequal, which violates that contract.
Type: known-external
Confidence: high

### aiohttp-30
Oracle: RFC 9110 §12.5.3 says `gzip;q=0` marks gzip as not acceptable. The substring test `file_encoding not in accept_encoding` ignores q-values, the same flaw as aiohttp-08.
Type: known-external
Confidence: high

### aiohttp-31
Oracle: The loop reuses `headers` across iterations on purpose, and strips only specific headers on a cross-origin redirect (client.py:851-854), so caller headers are meant to persist. `popall(HOST)` in `_update_headers` (client_reqrep.py:913) mutates that shared dict, so a retry silently loses the caller's Host.
Type: in-repo
Confidence: high

### aiohttp-32
Oracle: The docstring says "It un-escapes found escape sequences", but that work is already done upstream: `HeadersDictProxy.getall` runs `_QUOTED_PAIR_SUB` on parameter quoted-strings (helpers.py:797-800). The observation is true of the property's own lines, but I can't show wrong output.
Type: in-repo
Confidence: low

### aiohttp-33
Oracle: The comment in `__iter__` (helpers.py:811) reads "We need to deduplicate keys from MultiDict". Deduplicating with a case-sensitive `set` contradicts the case-insensitive `__getitem__`, yielding the same header twice and a wrong `len`.
Type: in-repo
Confidence: high

### aiohttp-34
Oracle: The error message in `__post_init__` says "Using 0 to disable timeouts is no longer supported". The `== 0` check runs after `total` has been replaced by `max(...)`, so `total=0` slips through whenever another timeout is set.
Type: in-repo
Confidence: high

### aiohttp-35
Oracle: The same parser checks `pos > self._max_line_size` when a CRLF is found (http_parser.py:~1024), and checks `_chunk_tail` length on the next call (1004-1011). Deferring the check lets an over-limit line be buffered first. The limit is still enforced one read later.
Type: in-repo
Confidence: medium

### aiohttp-36
Oracle: docs/streams.rst:95-97 says "`None`, the default, uses the stream's high-water limit". Treating an explicit `0` like `None` via `max_size or` conflates them, but the docs don't say what 0 should mean.
Type: in-repo
Confidence: low

### aiohttp-37
Oracle: `_prepare_headers` sets the local `keep_alive = False` for HTTP/1.0 with unknown length, which shows the intent to close. RFC 9112 §6.3 says a close-delimited body needs the connection closed. Because `self._keep_alive` stays True, the client hangs.
Type: in-repo
Confidence: high

### aiohttp-38
Oracle: A `binascii.Error` would be raised if such a chunk is decoded. However, the comment at multipart.py:425-428 states that returning the chunk unchanged when `cut == 0` is deliberate, and reaching the case needs an unusual whitespace-dominated chunk.
Type: implicit
Confidence: low

### aiohttp-39
Oracle: RFC 7230 §3.2.6 / RFC 7239 §4 define quoted-string as `DQUOTE *(qdtext / quoted-pair) DQUOTE`, so a greedy `".*"` must not span into the next pair. The module even defines `_QDTEXT` (web_request.py:131) but doesn't use it in `_FORWARDED_PAIR`.
Type: known-external
Confidence: high

### aiohttp-40
Oracle: The parent `Domain.match_domain` (web_urldispatcher.py:~806) compares `host.lower() == self._domain`. The `MaskDomain` override drops the lower-casing, so mask matching becomes case-sensitive while exact-domain matching is not.
Type: in-repo
Confidence: high

### aiohttp-41
Oracle: Whether the exception should include the value is a matter of diagnostic taste. Other `InvalidHeader` raises in the same file pass the offending value (http_parser.py:233, 235), but nothing requires it.
Type: none
Confidence: low

### aiohttp-42
Oracle: The code carries its own `# TODO: Save and await this task.` (streams.py:~539). The asyncio docs say to keep a reference to tasks created with `create_task`, or they may be garbage-collected and their exceptions lost.
Type: in-repo
Confidence: medium

### aiohttp-43
Oracle: RFC 6265 §5.2.2 says to ignore a Max-Age attribute whose value is not a valid delta. Under §5.3 step 3, Expires then governs, so this cookie should be expired immediately, not kept.
Type: known-external
Confidence: high

### aiohttp-44
Oracle: Re-raising one shared exception instance keeps adding frames to its `__traceback__`, which keeps every request frame alive. That is unbounded memory growth.
Type: implicit
Confidence: high

### aiohttp-45
Oracle: `SEPARATORS` explicitly lists `chr(9)`, which shows the intent to exclude TAB from tokens. Because the code uses symmetric difference (`CHAR ^ CTL ^ SEPARATORS`) and TAB is in both CTL and SEPARATORS, TAB gets added back. RFC 9110 §5.6.2 tchar also excludes HTAB.
Type: in-repo
Confidence: high

### aiohttp-46
Oracle: `EmptyStreamReader` never sets `_exception`, so the inherited `readuntil` raises AttributeError. The class itself carries `# TODO add async def readuntil` (streams.py:662).
Type: implicit
Confidence: high

### aiohttp-47
Oracle: RFC 9112 §6.1/§6.2 says a sender MUST NOT send Content-Length alongside Transfer-Encoding, and a chunked TE header requires chunk framing. `_update_transfer_encoding` also raises when `chunked` and Content-Length are combined, which shows the same intent.
Type: known-external
Confidence: high

### aiohttp-48
Oracle: docs/web_reference.rst:3208-3210 defines `keepalive_timeout` as "a delay before a TCP connection is closed after a HTTP request". Idle connections before the first request are outside its stated scope. A slow-client DoS concern is plausible, but I can't point to a contract.
Type: none
Confidence: low

### aiohttp-49
Oracle: `_create_writer` tests `if self.chunked is not None`, while everywhere else chunking is decided by truthiness (`if self.chunked:` in `_update_transfer_encoding`). So `chunked=False` enables chunked framing under a Content-Length header, which breaks RFC 9112 §6 framing.
Type: in-repo
Confidence: high

### aiohttp-50
Oracle: A `zlib.error` is raised on the second chunk of a valid compressed part, because each `decode_iter` call builds a fresh `ZLibDecompressor` (multipart.py:627-632) with no state carried between chunks.
Type: implicit
Confidence: high

### aiohttp-51
Oracle: A part whose declared Content-Length disagrees with its content is malformed either way. The only visible difference is which error text is raised, and nothing in the repo specifies it.
Type: none
Confidence: low

### aiohttp-52
Oracle: Same pattern as aiohttp-35. The found-CRLF branch checks `len(line) > self._max_field_size` (http_parser.py:~1115), but a no-CRLF trailer tail is buffered unchecked until the next call.
Type: in-repo
Confidence: medium

### aiohttp-53
Oracle: `read_chunk` already carries a partial quartet forward for base64 (`_b64_carry` / `_align_base64_chunk`, with the comment "every chunk is decoded on its own, so a chunk should not end mid-quartet"). There is no equivalent for quoted-printable, so a split `=41` escape is corrupted.
Type: in-repo
Confidence: high

### aiohttp-54
Oracle: The sibling `MultipartWriter.as_bytes(encoding, errors)` (multipart.py:1162-1178) passes `encoding, errors` to each part. `decode()` passes them only to the headers and calls `part.decode()` with no arguments.
Type: in-repo
Confidence: high

### aiohttp-55
Oracle: The constant is named `REUSE_ADDRESS` but is passed as `reuse_port=`. The Python `socket.create_server` contract says SO_REUSEADDR is already set on POSIX, while `reuse_port` sets SO_REUSEPORT and lets two servers share a port.
Type: known-external
Confidence: medium

### aiohttp-56
Oracle: The comment in `raw_path` promises the result is "exactly as an origin-form target", and RFC 9112 §3.2.1 says an empty path is sent as "/" in origin-form. So `''` and `'?x=1'` are not valid origin-form results.
Type: known-external
Confidence: medium

### aiohttp-57
Oracle: The decompressed-size check in the same reader uses `len(payload_merged) > self._max_msg_size` (reader_py.py:326). The docs call the setting the "maximum size of read websocket message". The resulting error text "Message size 10 exceeds limit 10" contradicts itself.
Type: in-repo
Confidence: high

### aiohttp-58
Oracle: client.py's retry and redirect paths check `req._body.consumed` and fail fast "instead of silently sending an empty body" (client.py:745, 795-801). The digest middleware's retry doesn't check, and sends an empty body under the original headers.
Type: in-repo
Confidence: high

### aiohttp-59
Oracle: The sibling `as_bytes` (multipart.py:1180-1186) appends `\r\n` after each part and a closing `--boundary--\r\n`, as RFC 2046 framing requires. `decode()` emits neither.
Type: in-repo
Confidence: high

### aiohttp-60
Oracle: In Python, a `bytes` value never equals a `str`, so `self._lines[-1] != "\r\n"` is always true. The list holds bytes (`self._lines.append(self._tail)`), so the comparison is a type slip. Its practical effect looks minor.
Type: known-external
Confidence: medium

### aiohttp-61
Oracle: The `AccessLogger` docstring documents `%%  The percent sign`. `CLEANUP_RE` (`%[^s]`) re-escapes the already-escaped `%%` into `%%%`, which makes every log call fail.
Type: in-repo
Confidence: high

### Hardest to classify
Three kinds of finding were hardest:

- **The Forwarded pair (27, 32).** Each observation is literally true of the property's own lines. But `HeadersDictProxy.getall` already splits at commas and unescapes quoted-strings upstream, so I couldn't show wrong output. I scored them low instead of taking the RFC at face value.
- **Documented intent versus the repo's own tests (07, 18).** For 07, the docs say "exceeded" but an existing test matches current behaviour. For 18, a test asserts the very exception the finding reports. I treated the tests as evidence against a defect.
- **Wrong in a technical sense, but no clear required behaviour (13, 36, 38, 48, 20).** For `%O` the only oracle is the regex accepting it. For `max_size=0` the docs never define 0. The base64 `cut == 0` case has a comment saying it is deliberate. For `keepalive_timeout` the docs scope it to after a request. The lru_cache is bounded.

For 13 and 38 the only hard evidence is that an exception is raised, so I typed them `implicit` but with lower confidence.
