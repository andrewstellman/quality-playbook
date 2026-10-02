# aiohttp, classifier S3 (Claude Sonnet), blind

### aiohttp-01
Oracle: The sibling `BytesPayload.write_with_length` (aiohttp/payload.py:580-596) shows content_length=0 handled by pure slicing with no I/O; `IOBasePayload._read_and_available_len`/`_read` instead do `remaining_content_len or DEFAULT_CHUNK_SIZE`, which folds explicit 0 into "no limit" and forces an actual file read.
Type: in-repo
Confidence: high

### aiohttp-02
Oracle: `_decode_content` (sync path) calls `decompress_sync(data, max_length=...)` once with no continuation, while `_decode_content_async` explicitly loops `while d.data_available: yield await d.decompress(b"", ...)` to drain the rest — the sync path is missing that loop, so output silently truncates at `_max_decompress_size` (default 256 KiB).
Type: in-repo
Confidence: high

### aiohttp-03
Oracle: RFC 7235 §4.1 says multiple `WWW-Authenticate` challenges cannot be safely comma-combined and must be examined individually, but `_authenticate` (line 418) does `response.headers.get("www-authenticate", "")`, taking only the first challenge/value.
Type: known-external
Confidence: medium

### aiohttp-04
Oracle: `StreamWriter.write()` (http_writer.py:195-201) truncates to `self.length`; `write_eof()` never consults `self.length` at all and writes the full `chunk` argument.
Type: in-repo
Confidence: high

### aiohttp-05
Oracle: `FORMAT_RE` matches `%{name}e`, but `LOG_FORMAT_MAP` has no `'e'` entry and there is no `_format_e` method; the class's own docstring at line 102 ("Exceptions are `_format_e`, `_format_i` and `_format_o` methods") asserts `_format_e` should exist.
Type: in-repo
Confidence: high

### aiohttp-06
Oracle: `getall()` (helpers.py:788) is a generic RFC 7230 comma-list splitter with no awareness of RFC 8288 angle-bracket-protected URIs, so a comma inside `<...>` in a Link value is treated as a list separator.
Type: known-external
Confidence: medium

### aiohttp-07
Oracle: docs/client_reference.rst:481 documents `max_redirects` as "Maximum number of redirects to follow," but the check `redirects >= max_redirects` fires after `redirects += 1`, so the Nth redirect trips before it's followed — max_redirects=1 follows zero.
Type: in-repo
Confidence: high

### aiohttp-08
Oracle: RFC 9110 §12.5.3 defines `q=0` as "not acceptable," but `_start_compression` uses a bare substring test `value in accept_encoding`, so `gzip;q=0` still matches on the substring "gzip".
Type: known-external
Confidence: high

### aiohttp-09
Oracle: `Response.write_eof` only calls `self._body.close()` inside the `elif isinstance(self._body, Payload)` branch; when `_must_be_empty_body` is true it takes the first branch (`await super().write_eof()`) and the file payload is never closed — a resource leak.
Type: implicit
Confidence: high

### aiohttp-10
Oracle: `readuntil` searches for the separator only within `self._buffer[0]` (`self._buffer[0].find(separator, offset)`), never across a chunk boundary, so a separator split between two `feed_data()` calls is invisible at its true position — contradicts the general readuntil contract (return up to the first occurrence) shared with `asyncio.StreamReader.readuntil`.
Type: known-external
Confidence: high

### aiohttp-11
Oracle: The per-request `cookies=` code path builds `tmp_cookie_jar = CookieJar(unsafe=..., quote_cookie=...)` (client.py ~649) without passing `treat_as_secure_origin`, so the temp jar's `_treat_as_secure_origin` is empty and `Secure` cookies get filtered for what the main jar would treat as secure.
Type: in-repo
Confidence: high

### aiohttp-12
Oracle: No docstring or spec promises method normalization; `self._method = method` stores exactly what's passed, symmetric with how `allowed_methods` also stores its argument verbatim. I can't point to anything establishing this as wrong.
Type: none
Confidence: low

### aiohttp-13
Oracle: `FORMAT_RE`'s alternation `[atPrsbOD]` includes `O`, but `LOG_FORMAT_MAP` has no `'O'` entry and no `_format_O` method exists anywhere in the class.
Type: in-repo
Confidence: high

### aiohttp-14
Oracle: `post()`'s multipart loop raises on the `max_size`/`max_fields` check with no `try/finally` or cleanup path that closes the temp files already created for earlier `FileField`s — a resource leak.
Type: implicit
Confidence: high

### aiohttp-15
Oracle: `EmptyStreamReader.__init__` (streams.py:598) deliberately skips `super().__init__()` and only sets `total_bytes`/`_read_eof_chunk`; it never sets `total_compressed_bytes`, which the inherited `total_raw_bytes` property (line 261) reads.
Type: in-repo
Confidence: high

### aiohttp-16
Oracle: `fetch_next_part`'s hardcoded `read_chunk(32)` (multipart.py:812) collides with the `assert size >= self._boundary_len` in `_read_chunk_from_stream` (line 447) whenever the boundary is ≥32 bytes.
Type: in-repo
Confidence: high

### aiohttp-17
Oracle: Every other call site pairs one `_read_boundary()` with one `fetch_next_part()` per `next()` invocation (multipart.py:789-797); the `_charset_` special case calls `fetch_next_part()` a second time without an intervening `_read_boundary()`, leaving the boundary line unconsumed.
Type: in-repo
Confidence: high

### aiohttp-18
Oracle: `json()` just does `loads(self._body.decode(encoding))` with no empty-body guard; an empty/whitespace string is not valid JSON per the JSON grammar, so this is arguably expected stdlib `json` behavior rather than an aiohttp defect.
Type: known-external
Confidence: low

### aiohttp-19
Oracle: `_readline()` (multipart.py:884-886) checks `self._unread` first; `_read_headers()` (line 924) calls `self._content.readline()` directly, bypassing `_unread` entirely, so a line stashed there by `_read_boundary()` for the parent gets skipped.
Type: in-repo
Confidence: high

### aiohttp-20
Oracle: `_cached_build_client_middlewares = lru_cache(maxsize=64)(...)` (client_middlewares.py:58) is a module-level cache; `functools.lru_cache` holds strong references to all cached arguments (including closures like `DigestAuthMiddleware`) until evicted, independent of the `ClientSession`'s lifetime.
Type: implicit
Confidence: high

### aiohttp-21
Oracle: Every other exit from the redirect block (`TooManyRedirects`, `NonHttpUrlRedirectClientError`, `InvalidUrlRedirectClientError`) explicitly does `await req._body.close()` before continuing; the GET/303-downgrade path sets `data = None` and falls straight into `continue`, dropping the old `req` without closing its body.
Type: in-repo
Confidence: high

### aiohttp-22
Oracle: `_do_start_compression` (web_response.py:720) has `assert self._body is not None`, but `_prepare_headers` calls `_start_compression` unconditionally whenever `self._compression` is set, with no guard for `_must_be_empty_body`/`body is None`.
Type: in-repo
Confidence: high

### aiohttp-23
Oracle: RFC 7230 §3.2.2 explicitly excludes `Set-Cookie` from comma-combining (and `Date`'s value itself contains an unquoted, unprotected comma); `getall()`'s generic comma splitter has no special-casing for either.
Type: known-external
Confidence: high

### aiohttp-24
Oracle: `bytes=-0` parses to `start=-0=0` via `start = -end` when `end=0`... actually the docstring/RFC 9110 §14.1.2 defines `suffix-length` "-0" as a valid-but-unsatisfiable range (must yield 416, not the full file); code produces `slice(0, None, 1)` and `FileResponse` serves the whole file as a satisfied 206.
Type: known-external
Confidence: medium

### aiohttp-25
Oracle: RFC 6265 §5.3 says replacing a cookie with a new one that has no explicit `Max-Age`/`Expires` makes it a session cookie, effectively clearing any prior expiration; here neither the `if max_age :=` nor `elif expires :=` branch runs for the new cookie, so `_expire_cookie` is never called and the old `_expirations` entry survives.
Type: known-external
Confidence: high

### aiohttp-26
Oracle: RFC 6265 §5.1.3 defines domain matching as case-insensitive, but `_is_domain_match` does `hostname.endswith(domain)` with the raw (non-lowercased) `Domain=` value against an already-lowercase hostname.
Type: known-external
Confidence: high

### aiohttp-27
Oracle: RFC 7239 §4 defines `Forwarded` field-values as a comma-separated list of forwarded-elements; the pair-parsing loop in `forwarded` (web_request.py:386-411) only recognizes `;` as a terminator and `break`s the moment it can't find one, silently dropping everything after the first comma.
Type: known-external
Confidence: high

### aiohttp-28
Oracle: The only call site, `Application._handle` (web_app.py:382), guards the call with `if request.headers.get(hdrs.EXPECT):` — the handler is never invoked without an Expect header in normal operation, and the docstring says it should raise "if value of header is not '100-continue'," which technically covers "absent." Calling it directly, out of that guarded context, isn't shown to be wrong.
Type: none
Confidence: low

### aiohttp-29
Oracle: `__eq__` (helpers.py:804) delegates straight to `self._md.__eq__(other)` on the raw multidict, while `__getitem__`/`items()` on the same class (line 807) join duplicate values with `", "` — the class's own comparison logic is inconsistent with its own iteration/lookup semantics.
Type: in-repo
Confidence: medium

### aiohttp-30
Oracle: Same substring bug as aiohttp-08 — `_get_file_path_stat_encoding` does `if file_encoding not in accept_encoding: continue`, so `gzip;q=0` still contains "gzip" and the q=0 exclusion (RFC 9110 §12.5.3) is ignored.
Type: known-external
Confidence: high

### aiohttp-31
Oracle: `_update_headers` (client_reqrep.py:912) does `headers.popall(hdrs.HOST, ...)`, mutating the caller's `headers` dict in place; `ClientSession._request`'s retry/redirect loop reuses that same `headers` object across `continue` iterations, so a custom `Host` is only honored on the first attempt.
Type: in-repo
Confidence: high

### aiohttp-32
Oracle: The `forwarded` property's own docstring (web_request.py:377) states "It un-escapes found escape sequences," but the code only does `value = value[1:-1]` (strip surrounding quotes) with no backslash-unescaping anywhere.
Type: in-repo
Confidence: high

### aiohttp-33
Oracle: `__len__`/`__iter__` (helpers.py:810-825) treat differently-cased keys (`X`, `x`) as distinct entries via `set(self._md.keys())`, while `__getitem__` uses the case-insensitive `self._md.getall(key)` — self-inconsistent within the same class, and contrary to RFC 7230 §3.2's case-insensitive field-name rule.
Type: in-repo
Confidence: high

### aiohttp-34
Oracle: `__post_init__` (client_reqrep.py:109) computes `total = max(total, connect, sock_read, sock_connect)` *before* checking `if self.total == 0: raise` — so `ClientTimeout(total=0, connect=5)` gets `total` overwritten to 5 first, bypassing the very guard whose comment says "0 to disable is no longer supported."
Type: in-repo
Confidence: high

### aiohttp-35
Oracle: The `len(self._chunk_tail) > max_line_length` check (http_parser.py:1000) only runs when `feed_data` is entered with a pre-existing `_chunk_tail`; the call that first creates an oversized `_chunk_tail` (`self._chunk_tail = chunk; return NEEDS_INPUT`) exits before that check ever runs.
Type: in-repo
Confidence: high

### aiohttp-36
Oracle: `max_size = max_size or self._high_water` (streams.py:394) treats an explicit `0` the same as `None` because `0` is falsy in Python, contradicting the `int | None` signature that implies `0` is a distinct, valid explicit value.
Type: in-repo
Confidence: high

### aiohttp-37
Oracle: `_prepare_headers` computes a local `keep_alive = False` override (web_response.py:408) for the HTTP/1.0-no-content-length case, but never writes it back to `self._keep_alive` — contrast with the earlier `keep_alive = self._keep_alive; ...; self._keep_alive = keep_alive` sync pattern just above, which the override breaks.
Type: in-repo
Confidence: high

### aiohttp-38
Oracle: `_align_base64_chunk`'s back-walk (multipart.py:408-434) explicitly gives up when `cut` reaches 0 — `if not cut: return chunk` — returning the unaligned chunk with nothing carried forward, by the code's own design, not by accident.
Type: in-repo
Confidence: high

### aiohttp-39
Oracle: `_FORWARDED_PAIR` regex's quoted-value alternative is `".*"` (greedy) (web_request.py:139), which backtracks to the *last* `"` in the field-value rather than the nearest one — directly traceable from the regex itself, and inconsistent with RFC 7230's quoted-string grammar it's meant to implement.
Type: in-repo
Confidence: high

### aiohttp-40
Oracle: The base `Domain.match_domain` (web_urldispatcher.py:807) does `host.lower() == self._domain`, explicitly normalizing case; the `MaskDomain` subclass override (line 826) does `self._mask.fullmatch(host)` with no lowercasing at all — a direct parallel-implementation mismatch.
Type: in-repo
Confidence: high

### aiohttp-41
Oracle: `InvalidHeader.__init__(hdr)` (http_exceptions.py:87) is only ever given the header *name* here (`InvalidHeader(CONTENT_LENGTH)`), and its message format `f"Invalid HTTP header: {hdr!r}"` has no parameter for a value — this looks like an intentional (if unhelpful) API shape rather than a functional defect.
Type: none
Confidence: low

### aiohttp-42
Oracle: `read_nowait` (streams.py:534-540) does `asyncio.create_task(cb(chunk))` with a `# TODO: Save and await this task` comment acknowledging the task reference (and therefore its exception) is discarded.
Type: in-repo
Confidence: high

### aiohttp-43
Oracle: The `elif expires := cookie["expires"]:` (cookiejar.py:407) is attached to the outer `if max_age := ...:`, not to the inner `try/except`, so when `int(max_age)` raises and is caught, the `elif` is already structurally skipped for this pass — directly visible from the control flow.
Type: in-repo
Confidence: high

### aiohttp-44
Oracle: `HTTP_NOT_FOUND = HTTPNotFound()` (web_urldispatcher.py:975) is a single class-level instance raised via `raise self._http_exception` for every unmatched request; reusing one exception object across raises is a well-known CPython pattern for `__traceback__`-mediated reference retention (frames, and therefore locals like the `Request`, stay reachable).
Type: implicit
Confidence: medium

### aiohttp-45
Oracle: RFC 7230 §3.2.6 defines `tchar` to exclude separators (including TAB) from valid HTTP tokens; `TOKEN = CHAR ^ CTL ^ SEPARATORS` (helpers.py:173) uses symmetric difference instead of subtraction, so characters present in *two* of the three sets (TAB is in both CHAR and CTL, cancelling there, then XORed back in by SEPARATORS) end up wrongly included.
Type: known-external
Confidence: high

### aiohttp-46
Oracle: `EmptyStreamReader` has an explicit `# TODO add async def readuntil` comment (streams.py:653) acknowledging the method isn't overridden, so it falls through to the base `StreamReader.readuntil`, which accesses `self._exception` — an attribute `EmptyStreamReader.__init__` never sets because it skips `super().__init__()`.
Type: in-repo
Confidence: high

### aiohttp-47
Oracle: RFC 9112 §6.1 forbids sending both `Content-Length` and `Transfer-Encoding: chunked`; `_update_transfer_encoding` (client_reqrep.py:1231) only raises when `self.chunked` is *also* True, so a user-set `Transfer-Encoding: chunked` header with a plain bytes body (chunked flag False) sails through, and `_update_body_from_data` then adds a `Content-Length` on top.
Type: known-external
Confidence: high

### aiohttp-48
Oracle: The class docstring (web_protocol.py:143) describes `keepalive_timeout` as "number of seconds before closing," but the keepalive timer is only armed inside `start()` after a completed request/response (line ~854, gated on `self._keepalive`), so a connection that never completes a request is never subject to it.
Type: in-repo
Confidence: high

### aiohttp-49
Oracle: `self.chunked: bool | None` is explicitly tri-state (client_reqrep.py:1034), but `_create_writer`'s `if self.chunked is not None: writer.enable_chunking()` (line 1449) treats `False` the same as `True` — only the default `None` skips chunking — contradicting the type's own tri-state design.
Type: in-repo
Confidence: high

### aiohttp-50
Oracle: `_decode_content_async` (multipart.py:619) instantiates a fresh `ZLibDecompressor` on every call; `BodyPartReaderPayload.write` (line 708) calls `field.decode_iter(chunk)` once per chunk in a loop, so each chunk after the first is decompressed with a brand-new decompressor holding no window state from prior chunks.
Type: in-repo
Confidence: high

### aiohttp-51
Oracle: `read_chunk`'s dispatch (multipart.py:389, inferred) is `if self._length:`, a truthiness check that treats `Content-Length: 0` the same as "length unknown," routing to boundary-scanning (`_read_chunk_from_stream`) instead of the length-based reader — a literal `0` vs `None` conflation visible in the branch condition itself.
Type: in-repo
Confidence: high

### aiohttp-52
Oracle: Same code path as aiohttp-35 — the trailer-length check in `feed_data` (http_parser.py:1000-1007) only runs on entry when `_chunk_tail` is already populated, not on the call that first stores an over-length trailer line into `_chunk_tail`.
Type: in-repo
Confidence: high

### aiohttp-53
Oracle: `_decode_content_transfer` (multipart.py:636) calls `binascii.a2b_qp(data)` independently per chunk with no cross-chunk buffer, the same per-chunk-fresh-state pattern as the compression bug (aiohttp-50), so an escape sequence split across the 256 KiB chunk boundary can't be reassembled.
Type: in-repo
Confidence: high

### aiohttp-54
Oracle: `MultipartWriter.decode(encoding, errors)` (multipart.py:1147) calls `part.decode()` with no arguments for each part body, discarding the `encoding`/`errors` parameters its own signature accepts and documents.
Type: in-repo
Confidence: high

### aiohttp-55
Oracle: `BaseTestServer`'s socket factory (test_utils.py:78) passes the `REUSE_ADDRESS`-named variable into `socket.create_server(..., reuse_port=REUSE_ADDRESS)` — the variable's own name announces the intended (and different) parameter, `reuse_address`, that it should have been passed as.
Type: in-repo
Confidence: high

### aiohttp-56
Oracle: For an absolute-form request-target with an empty path component, RFC 9112's origin-form/authority handling implies a default `/`; `raw_path` here strips everything up through the authority and returns whatever's left, including an empty string, but the docstring only promises "raw... may contain non-valid URL characters," not path normalization — plausibly by design for a "raw" accessor.
Type: known-external
Confidence: low

### aiohttp-57
Oracle: The condition `self._payload_bytes_to_read >= self._max_msg_size - partial_len` (reader_py.py:552) rejects a message exactly equal to `max_msg_size`, yet the raised message itself says "Message size 10 exceeds limit 10" — the wording contradicts an equal-size message actually "exceeding" the limit, pointing to an off-by-one (`>=` vs `>`).
Type: in-repo
Confidence: high

### aiohttp-58
Oracle: `AsyncIterablePayload` (payload.py:976-996) stores a single `self._iter = value.__aiter__()` with a comment claiming `_consumed` "stays False to allow reuse," but no caching actually occurs for a plain async generator — iterating it once exhausts it, so `DigestAuthMiddleware`'s two `handler(request)` calls (client_middleware_digest_auth.py:495) reuse the same drained iterator on retry.
Type: in-repo
Confidence: high

### aiohttp-59
Oracle: The sibling `as_bytes()` method (multipart.py:1163-1186) appends a trailing `b"\r\n"` after each part and a closing `b"--boundary--\r\n"`; the sync `decode()` (line 1147) omits both, producing malformed multipart output — a direct parallel-implementation mismatch.
Type: in-repo
Confidence: high

### aiohttp-60
Oracle: `self._lines: list[bytes] = []` is explicitly typed (http_parser.py:284), and a sibling comparison at line 392 correctly uses the bytes constant `EMPTY`; `feed_eof`'s `self._lines[-1] != "\r\n"` (line 324) compares against a `str` literal, which is always unequal to a `bytes` element in Python 3.
Type: in-repo
Confidence: high

### aiohttp-61
Oracle: `CLEANUP_RE = re.compile(r"(%[^s])")` (web_log.py:63) is meant to re-escape literal `%` characters left after `FORMAT_RE.sub` converts atoms to `%s`, but `%%` collapses to a single `%` before this substitution runs its match against `[^s]`, over-escaping and leaving a format string that breaks at `%`-format time.
Type: in-repo
Confidence: medium

---

Hardest to classify were the ones straddling "obviously wrong by direct code trace" versus "wrong only relative to an external contract I have to take on faith": aiohttp-24 (Range `bytes=-0`) and aiohttp-56 (`raw_path` for an empty absolute-form path) both hinge on exactly how strictly RFC 9110/9112 pin down the expected normalized value, which I know well enough to reason about but not well enough to quote chapter and verse with full confidence. aiohttp-28 and aiohttp-41 were hard in the other direction — the code looks locally "wrong" in isolation, but once I traced the actual call site (aiohttp-28) or the class's own narrow constructor contract (aiohttp-41), the behavior turned out to be unreachable or arguably intentional, so I downgraded both to `none`/low. aiohttp-18 and aiohttp-12 were similarly borderline: plausible ergonomic complaints rather than demonstrable defects, since no docstring, sibling implementation, or spec establishes what "should" happen instead.
