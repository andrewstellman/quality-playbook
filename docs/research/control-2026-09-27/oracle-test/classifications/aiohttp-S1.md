# aiohttp, classifier S1 (Claude Sonnet), blind

### aiohttp-01
Oracle: `write_with_length(writer, 0)` should write exactly 0 bytes for a length of 0, but `_read_and_available_len`/`_read` use `remaining_content_len or DEFAULT_CHUNK_SIZE`, which treats the valid value `0` the same as `None` (no limit) because `0` is falsy in Python.
Type: in-repo
Confidence: high

### aiohttp-02
Oracle: `_decode_content` decompresses with `ZLibDecompressor(...).decompress_sync(data, max_length=self._max_decompress_size)` but silently returns whatever the decompressor gives back (up to `max_length`) instead of raising or looping to get the rest; `decode()`'s docstring says it returns fully decoded content, not a truncated prefix.
Type: in-repo
Confidence: medium

### aiohttp-03
Oracle: `_authenticate` does `method, sep, headers = auth_header.partition(" ")` and checks `method.lower() != "digest"` on the whole joined `WWW-Authenticate` value. RFC 7235 §4.1 allows multiple challenges in one header (comma-separated or repeated), so the first scheme token is not necessarily the applicable one; a real Digest challenge later in the same value is missed.
Type: known-external
Confidence: medium

### aiohttp-04
Oracle: `writer.length` is meant to cap output to the declared Content-Length (as `write()` does, confirmed by that codepath truncating to 5). `write_eof(chunk)`'s no-compression/no-chunked branch does `if chunk: self._write(chunk)` with no length check, so it writes the full chunk regardless of `self.length`, inconsistent with `write()`'s own behavior on the same object.
Type: in-repo
Confidence: high

### aiohttp-05
Oracle: The class docstring at aiohttp/web_log.py:41 explicitly documents `%{FOO}e` as `os.environ['FOO']`, and `FORMAT_RE` matches it, but `LOG_FORMAT_MAP` has no `'e'` entry and there's no `_format_e` method, so `compile_format` raises `KeyError` for a format the class's own docs advertise as supported.
Type: in-repo
Confidence: high

### aiohttp-06
Oracle: `HeadersDictProxy.getall` at aiohttp/helpers.py:788 uses `_LIST_ELEMENT_RE` to split a header value on top-level commas per RFC 9110 §5.6.3 list syntax, but the `Link` header (RFC 8288) uses commas to separate link-values while a single link-value's target URI can itself contain a comma inside `<...>`; the naive comma split breaks the URI apart, and `ClientResponse.links` (client_reqrep.py:490) then produces a malformed `next` entry.
Type: known-external
Confidence: high

### aiohttp-07
Oracle: `max_redirects` is documented/named as the maximum number of redirects to follow; the code at client.py:769-770 does `redirects += 1; ... if max_redirects and redirects >= max_redirects: raise TooManyRedirects` before the redirect is followed, so with `max_redirects=1` zero redirects are ever followed and at most N-1 are followed for larger N — off-by-one against the parameter's own name/contract.
Type: in-repo
Confidence: high

### aiohttp-08
Oracle: `_start_compression` at web_response.py:349 does `if value in accept_encoding`, a plain substring test, ignoring RFC 9110 §12.5.3 `q=0` semantics where `gzip;q=0` explicitly forbids that coding. The comment right above it ("Encoding comparisons should be case-insensitive... RFC 9110") shows the author was referencing the RFC but the q-value parsing was never implemented.
Type: known-external
Confidence: high

### aiohttp-09
Oracle: In `Response.write_eof` (web_response.py:681-698), when `_must_be_empty_body` is true the first branch calls only `super().write_eof()` and returns, skipping the `elif isinstance(self._body, Payload)` branch that calls `self._body.close()`. A `Payload` such as a file payload is never closed, leaking the underlying file descriptor.
Type: implicit
Confidence: high

### aiohttp-10
Oracle: `readuntil` scans for `separator` using `self._buffer[0].find(separator, offset)` against only the current buffer chunk, not across chunk boundaries; with `feed_data(b'abc\r')` then `feed_data(b'\ndef\r\nxyz')`, the split `\r`/`\n` should still be found, so returning `b'abc\r\ndef\r\n'` looks correct — but the function's job is exactly "read until separator, no more, no less," and the sibling `read_nowait` chunk-search logic is the in-repo reference for how buffer-spanning reads are supposed to work.
Type: in-repo
Confidence: low

### aiohttp-11
Oracle: `ClientSession._request`'s per-request cookie handling builds a temporary jar copying only `unsafe` and `quote_cookie` from the session jar, dropping `treat_as_secure_origin`; `CookieJar.filter_cookies`/`update_cookies` (cookiejar.py) uses `treat_as_secure_origin` to decide whether `Secure` cookies may be sent over plain HTTP, so the temp jar silently reverts to the default (empty) list.
Type: in-repo
Confidence: high

### aiohttp-12
Oracle: HTTP methods are case-sensitive tokens per RFC 9110 §9.1, and aiohttp's own request-side normalizes methods to uppercase (`request.method` is uppercase, `hdrs.METH_*` constants are uppercase); `HTTPMethodNotAllowed.__init__` stores whatever case was passed without upper-casing, inconsistent with that convention.
Type: known-external
Confidence: low

### aiohttp-13
Oracle: `FORMAT_RE` at web_log.py:62 matches the literal char class `[atPrsbOD]` which includes `O`, but `LOG_FORMAT_MAP` has no `'O'` entry (only `a,t,P,r,s,b,T,Tf,D,i,o` — lowercase `o`) and there's no `_format_O` method, so the regex's own declared alphabet is internally inconsistent with the map it feeds into.
Type: in-repo
Confidence: high

### aiohttp-14
Oracle: `BaseRequest.post` (web_request.py:810-852) opens `SpooledTemporaryFile` per file field inside the multipart loop; when a later field trips `max_size`/`max_fields` it raises immediately without closing the earlier fields' temp files, and there's no `try/finally` or cleanup in `_finish()` to close them — a straightforward file-descriptor leak on the error path.
Type: implicit
Confidence: high

### aiohttp-15
Oracle: `EmptyStreamReader` (streams.py:598-679) does not define `total_compressed_bytes`, so the inherited `total_raw_bytes` property (streams.py:261, `if self.total_compressed_bytes is None`) raises `AttributeError` when accessed on `EMPTY_PAYLOAD` — a plain missing-attribute crash.
Type: implicit
Confidence: high

### aiohttp-16
Oracle: `_read_chunk_from_stream`'s own assertion (multipart.py:443-445) `assert size >= self._boundary_len` documents the precondition that callers must request at least a boundary-length-sized chunk; `MultipartReader.next`'s `_charset_` special case calls `part.read_chunk(32)` unconditionally, violating that precondition whenever the boundary is longer than 32 bytes (as in the WebKit example).
Type: in-repo
Confidence: high

### aiohttp-17
Oracle: `_read_boundary`/`_read_until_first_boundary` in the same file show the established pattern of consuming the `--boundary` line before parsing the next part's headers via `fetch_next_part`/`_read_headers`; the `_charset_` special case in `MultipartReader.next` (multipart.py:809-816) calls `fetch_next_part()` a second time without first consuming the intervening boundary line, producing an `InvalidHeader`/malformed-headers result that the sibling boundary-handling code would have prevented.
Type: in-repo
Confidence: high

### aiohttp-18
Oracle: An empty or whitespace-only body with `Content-Type: application/json` is a client/server sending an empty JSON document, and `ClientResponse.json()` (client_reqrep.py:747-773) just calls `loads(self._body.decode(...))` with no empty-body guard, so `json.JSONDecodeError` propagates uncaught as an implementation detail rather than a documented aiohttp exception (contrast with the `content_type` check just above it, which *is* turned into an aiohttp `ContentTypeError`).
Type: in-repo
Confidence: medium

### aiohttp-19
Oracle: `_read_headers` (multipart.py) reads via `self._content.readline(...)`, i.e. straight from the underlying stream, while `_readline` (used by `_read_until_first_boundary`/`_read_boundary`) checks `self._unread` first; the finding shows `_read_headers` ignoring a previously-unread line that a nested-boundary sequence pushed back, which is exactly the mismatch between the two read paths in the same class.
Type: in-repo
Confidence: medium

### aiohttp-20
Oracle: `_cached_build_client_middlewares` wraps `build_client_middlewares` in a module-level `functools.lru_cache(maxsize=64)`; `lru_cache` keeps strong references to its cached arguments/results for the life of the process (or until evicted), so closed-over middleware instances (which may hold credentials) are kept alive past `ClientSession.close()` — a straightforward reference/resource leak inherent to `lru_cache`'s documented behavior.
Type: known-external
Confidence: high

### aiohttp-21
Oracle: In the redirect-handling loop (client.py:778-786), when the method is downgraded to GET, `data = None` is set but there is no call to `req._body.close()`/`req._body = None` for the old file-object body, unlike the `TooManyRedirects` branch a few lines above (client.py:770-771) which does call `await req._body.close()`. The same file's own code shows the expected cleanup call is being skipped on this path.
Type: in-repo
Confidence: high

### aiohttp-22
Oracle: `Response._do_start_compression` (web_response.py:720-735) does `assert self._body is not None` unconditionally before compressing; for a 204/None-body response this assertion fails under normal `python -O`-disabled runs, and with `-O` (assertions stripped) it falls through to `compressor.compress(None)`, which raises `TypeError` — a plain crash on legitimate input (empty-body responses with compression enabled are a normal combination).
Type: implicit
Confidence: high

### aiohttp-23
Oracle: `HeadersDictProxy.getall` (helpers.py:788) splits header values purely on RFC 9110 §5.6.3 list syntax (top-level commas), but HTTP-date values (RFC 9110 §5.6.7 / RFC 7231) and `Set-Cookie`'s `Expires` attribute contain commas that are not list separators; `Date` and `Set-Cookie` are documented exceptions to comma-list splitting.
Type: known-external
Confidence: high

### aiohttp-24
Oracle: RFC 9110 §14.1.2 (byte-range spec `suffix-length`) requires a non-zero suffix length for `suffix-byte-range-spec`; `bytes=-0` is a zero suffix-length and should be treated as an unsatisfiable/invalid range (or ignored), not as "whole file." `http_range` (web_request.py:682-685) and `FileResponse` (web_fileresponse.py:358-395) instead treat it as `slice(0, None, 1)`, i.e. the entire file, contradicting the spec's suffix-length rule.
Type: known-external
Confidence: medium

### aiohttp-25
Oracle: RFC 6265 §5.3 requires that when a new cookie with the same (name, domain, path) is set, its own `Max-Age`/`Expires` (or absence thereof, meaning session cookie) governs; `CookieJar._update_cookies` (cookiejar.py:396-416) only calls `_expire_cookie` when the *new* cookie carries a parseable `max-age`/`expires`, leaving a stale entry from the *previous* cookie's `_expirations` in place when the new `Set-Cookie` omits or fails to parse an expiry.
Type: known-external
Confidence: high

### aiohttp-26
Oracle: RFC 6265 §5.2.3/§5.1.3 requires case-insensitive domain matching; `_is_domain_match` (cookiejar.py:532-545) does `hostname.endswith(domain)` with no case normalization, so a mixed-case `Domain=EXAMPLE.COM` never matches lower-case `example.com` hosts, and the cookie is dropped entirely at store time.
Type: known-external
Confidence: high

### aiohttp-27
Oracle: RFC 7239 §4 defines the `Forwarded` header's `forwarded-element` as comma-separated pairs of `;`-separated `forwarded-pair`s; the pair loop in `BaseRequest.forwarded` (web_request.py:386-411) only recognizes `;` as a terminator via `_FORWARDED_PAIR_RE`'s `(?:\Z|;)` anchor and has no comma-handling in the pair-matching branch, so it stops at the first comma and drops the remaining pairs (and the second element) of that field-value.
Type: known-external
Confidence: high

### aiohttp-28
Oracle: RFC 9110 §10.1.1 says a server should only reject a request with `417 Expectation Failed` when the client actually sent an `Expect` header it cannot satisfy; `_default_expect_handler`'s own docstring says "raise HTTPExpectationFailed if value of header is not '100-continue'", but with no `Expect` header at all, `expect` defaults to `''` and the `else` branch still raises `HTTPExpectationFailed`, contradicting both the RFC and the handler's own docstring (which implies the check is only meaningful when a header is present).
Type: in-repo
Confidence: high

### aiohttp-29
Oracle: `HeadersDictProxy.__eq__` (helpers.py:804) delegates to `self._md.__eq__(other)`, comparing the underlying `CIMultiDict` (which treats repeated keys as separate entries) against another `HeadersDictProxy` or a plain `dict` (which has one value per key); this means two proxies that produce identical `getall`/`__getitem__` (comma-joined) views compare unequal, and `dict(p) == {...}` (which uses `__getitem__`, i.e. the joined view) disagrees with `p == {...}`. This is an internal inconsistency between the class's own `__eq__`, `__getitem__`, and `dict()` conversion behavior.
Type: in-repo
Confidence: medium

### aiohttp-30
Oracle: RFC 9110 §12.5.3 `q=0` means "not acceptable"; `_get_file_path_stat_encoding` (web_fileresponse.py:241-243) checks `if file_encoding not in accept_encoding`, a substring test that doesn't parse q-values, so `gzip;q=0` (explicitly disallowed) is treated as accepted — same class of bug as aiohttp-08, same file family.
Type: known-external
Confidence: high

### aiohttp-31
Oracle: `_update_headers` (client_reqrep.py:912-913) does `headers.popall(hdrs.HOST, (host,))[0]`, mutating the caller-supplied `headers` dict in place by removing its `Host` entry; `ClientSession._request`'s retry loop reuses the same `headers` object across iterations (visible in the redirect/retry code path at client.py), so the caller's explicit `Host` override is gone by the second send and the URL-derived host is used instead.
Type: in-repo
Confidence: high

### aiohttp-32
Oracle: RFC 7239 §4 (and the generic RFC 9110 quoted-string ABNF) requires backslash-unescaping (`quoted-pair`) after stripping the surrounding DQUOTEs; `BaseRequest.forwarded` (web_request.py:396-399) only does `value[1:-1]` and performs no unescaping of `\"`/`\\`, so an escaped quote inside a quoted `Forwarded` value is passed through literally instead of being decoded.
Type: known-external
Confidence: medium

### aiohttp-33
Oracle: RFC 9110 §5.3 requires field names to be treated case-insensitively for header semantics (so `X` and `x` are the *same* field and should combine into one list value); `HeadersDictProxy.__iter__`/`__len__` (helpers.py:810-825) deduplicate using the raw (case-sensitive) key string `k`, so `X: 1` and `x: 2` are counted and iterated as two distinct headers rather than one combined `X: 1, 2`.
Type: known-external
Confidence: high

### aiohttp-34
Oracle: `ClientTimeout.__post_init__` (client_reqrep.py:109-130) itself documents the intent in its comment ("Ensure total is never lower than a more specific timeout... total=0 ... is no longer supported, use None instead") but computes `object.__setattr__(self, "total", max(self.total, self.connect or 0, ...))` *before* checking `if self.total == 0: raise ValueError`. When `connect=5` bumps `total` from 0 to 5 first, the explicit `total=0` disable-attempt is silently overridden instead of raising — contradicting the method's own stated purpose in the very next lines.
Type: in-repo
Confidence: high

### aiohttp-35
Oracle: In `HttpPayloadParser.feed_data` (http_parser.py:999-1007), the `max_line_size`/`max_field_size` length check for `_chunk_tail` only runs on entry to the chunked-parsing branch (`if self._chunk_tail: ... raise LineTooLong`), i.e. on the *next* `feed_data()` call; the current call that first stores an oversized line into `_chunk_tail` (~line 1062, the `no b"\n" in chunk` branch) performs no length check at all, so an arbitrarily large single block is buffered without error until the following call.
Type: in-repo
Confidence: high

### aiohttp-36
Oracle: `readuntil`'s own signature documents `max_size: int | None = None` where `None` means "use the default limit," but the code (streams.py:394) does `max_size = max_size or self._high_water`, which folds the valid explicit value `0` into that same "use default" branch because `0` is falsy — same falsy/`None` conflation pattern as aiohttp-01, in the same class.
Type: in-repo
Confidence: high

### aiohttp-37
Oracle: `StreamResponse._prepare_headers` (web_response.py:377-408), in the HTTP/1.0-with-no-Content-Length branch, only reassigns the local variable `keep_alive = False` and never calls `self.set_keep_alive` (or otherwise writes back to `self._keep_alive`); the connection's actual state (`self._keep_alive`, checked elsewhere to decide whether to close the socket after the response) stays `True`, so the local computation has no effect — an internal read/write mismatch within the same method.
Type: in-repo
Confidence: high

### aiohttp-38
Oracle: `_align_base64_chunk`'s own logic is a back-walk to find a whole trailing base64 quartet to carry forward; when fewer than 4 base64 chars exist in the chunk, `cut` reaches `0` and the method's `if not cut: return chunk` branch (its own comment: "a part that holds no quartet ... holds none to give") hands back a chunk that is not a multiple of 4 base64 characters, which `base64.b64decode` (Python stdlib contract: input length must be a multiple of 4) then rejects with `binascii.Error`.
Type: in-repo
Confidence: medium

### aiohttp-39
Oracle: `_FORWARDED_PAIR`'s quoted-value alternative is `".*"`, a greedy match to the *last* `"` in the remaining string rather than the nearest closing quote; RFC 7239's `quoted-string` ABNF (borrowed from RFC 7230/9110) requires matching to the first unescaped closing DQUOTE, so a value containing another `"`-delimited pair later in the string gets absorbed into the first value.
Type: known-external
Confidence: high

### aiohttp-40
Oracle: DNS hostnames are case-insensitive (RFC 1035 §2.3.3, reinforced by RFC 4343), and RFC 9110's `Host` header is compared as such; `MaskDomain.__init__` (web_urldispatcher.py:815-820) compiles `self._mask` from the domain pattern with plain `re.compile(mask)` (no `re.IGNORECASE`), so `match_domain` fails on any case difference between the configured wildcard domain and the incoming `Host`.
Type: known-external
Confidence: high

### aiohttp-41
Oracle: `InvalidHeader`'s constructor (used elsewhere in http_parser.py) commonly renders messages that help debugging; the finding is about the *content* of the message omitting the offending value. There's no in-repo convention requiring the value be included (other `InvalidHeader` call sites in the file are similarly terse), so this reads as a usability/diagnostics gap rather than a defect against any stated contract.
Type: none
Confidence: low

### aiohttp-42
Oracle: `read_nowait`'s `asyncio.create_task(cb(chunk))` (streams.py:523-541) creates a task and discards the reference without awaiting or storing it; per the `asyncio` documentation's own "Important: Save a reference to the result of this function" warning, an un-awaited, unreferenced task can be garbage-collected and any exception it raises becomes an unretrievable/unhandled-task-exception logged by the loop rather than surfaced to the caller of `read_nowait()`.
Type: known-external
Confidence: high

### aiohttp-43
Oracle: `_update_cookies` (cookiejar.py:402-416) uses `if max_age: ... except ValueError: cookie["max-age"] = ""` then `elif expires := cookie["expires"]:`, so when `Max-Age` is present but unparseable, the `if` branch is taken (and fails), and the `elif` for `Expires` is never evaluated even though `Max-Age` should have been ignored/fallen back per RFC 6265 §5.2.2 (unparseable Max-Age must be ignored, not treated as "Max-Age was absent" for the elif purposes — but the code's own branching structure means Expires is skipped whenever Max-Age was present at all, valid or not).
Type: in-repo
Confidence: medium

### aiohttp-44
Oracle: `UrlDispatcher.HTTP_NOT_FOUND = HTTPNotFound()` (web_urldispatcher.py:975) is a single class-level singleton reused across every unmatched request via `SystemRoute._handle`; each time it's raised, its `__traceback__` frame chain grows and pins whatever objects (including `web.Request`) are referenced in those frames, since the same exception object is never replaced — a straightforward reference leak from reusing one exception instance as a control-flow singleton.
Type: implicit
Confidence: high

### aiohttp-45
Oracle: RFC 9110 §5.6.2 `token` ABNF excludes `TAB` and other CTL characters; `TOKEN` (helpers.py:173) is built as `CHAR ^ CTL ^ SEPARATORS` — a symmetric-difference (XOR) construction rather than `CHAR - CTL - SEPARATORS` (set difference), so any character present in both `CTL` and `SEPARATORS` gets added back into `TOKEN` instead of excluded; TAB (`chr(9)`) is in both sets (it's a `SEPARATORS` member per the code right above and a `CTL` character), so it survives into `TOKEN` and is then accepted as valid in tokens like Content-Disposition parameter values.
Type: known-external
Confidence: high

### aiohttp-46
Oracle: `EmptyStreamReader` (streams.py:598-679) overrides `read`, `readline`, `readany`, `readchunk`, `readexactly`, `read_nowait` to safely return empty results, but has a `# TODO add async def readuntil` comment and no override for `readuntil`; calling it falls through to the base `StreamReader.readuntil`, which accesses `self._exception` — a slot `EmptyStreamReader.__init__` never sets (its `__slots__` only has `_read_eof_chunk`) — raising `AttributeError`. The TODO comment is itself the in-repo acknowledgment that this method was left unhandled.
Type: in-repo
Confidence: high

### aiohttp-47
Oracle: `_update_transfer_encoding` (client_reqrep.py:1231-1248) only sets `self.chunked = True` from its own flag, never from a caller-supplied `headers={'Transfer-Encoding': 'chunked'}` dict entry; `_update_body_from_data` then checks `if not self.chunked and hdrs.CONTENT_LENGTH not in self.headers` and, since `self.chunked` is still `False`, adds `Content-Length` — while the raw header the caller set still says `chunked`. The two code paths read different sources of truth (the `self.chunked` flag vs. the raw `headers` dict) for the same semantic property.
Type: in-repo
Confidence: high

### aiohttp-48
Oracle: `RequestHandler.__init__` sets `self._keepalive = False` initially (web_protocol.py:243), and `_process_keepalive` (web_protocol.py:649-651) returns early `if ... not self._keepalive`; the keep-alive timer is only armed after a request completes (elsewhere in the same class), so a connection that never completes a first request (idle or partial request line) is not subject to `keepalive_timeout` at all — leaving it open indefinitely, a resource-exhaustion path with no explicit spec citation needed beyond "the timeout is supposed to bound idle connections," which is this class's own evident purpose.
Type: in-repo
Confidence: medium

### aiohttp-49
Oracle: `_create_writer` calling code sends `Content-Length: 3` yet writes the body wrapped in chunk framing (`3\r\nabc\r\n0\r\n\r\n`) — the two length-indication mechanisms (RFC 9112 §6.1, Content-Length vs. Transfer-Encoding: chunked framing) are mutually exclusive by spec; declaring a fixed Content-Length while actually writing chunk-encoded bytes on the wire produces a message a compliant peer cannot parse correctly.
Type: known-external
Confidence: high

### aiohttp-50
Oracle: `_decode_content_transfer`/`decode_iter` construct a fresh `ZLibDecompressor` per call (multipart.py:593-633, called anew each time from `BodyPartReaderPayload.write`'s per-chunk loop at 703-711); a gzip/deflate stream is inherently stateful across chunks (RFC 1950/1951), so decompressing chunk 2 with a brand-new decompressor (no state carried from chunk 1) breaks the stream and `zlib` raises `Error -3` — the streaming contract of `zlib`/`ZLibDecompressor` itself is the oracle.
Type: known-external
Confidence: high

### aiohttp-51
Oracle: `read_chunk`'s branch condition `if self._length:` (multipart.py:389) treats a declared `Content-Length: 0` the same as "length unknown" (both falsy), routing to `_read_chunk_from_stream` (boundary-scanning) instead of `_read_chunk_from_length` even though the header explicitly states a known length of zero — the same `0`-vs-`None` falsy conflation as aiohttp-01/aiohttp-36, this time against the part's own declared `Content-Length` header value.
Type: in-repo
Confidence: high

### aiohttp-52
Oracle: Same pattern as aiohttp-35: the `_chunk_tail` length check for `PARSE_TRAILERS` in `feed_data` (http_parser.py:999-1007, ~1112) is only evaluated on the *next* call after a trailer line is first stored via `self._chunk_tail = chunk` (no CRLF found yet); the call that does the initial storing performs no `max_field_size` check, so an over-long trailer line is buffered unchecked for one round-trip.
Type: in-repo
Confidence: high

### aiohttp-53
Oracle: `_decode_content_transfer` (multipart.py:636-642) decodes quoted-printable via `binascii.a2b_qp(data)` independently per chunk with no carry-over buffer; RFC 2045 §6.7 quoted-printable escape sequences (`=XX`, `=\r\n` soft breaks) are three-byte units that can straddle a chunk boundary, and `a2b_qp` has no notion of "incomplete escape, wait for more data" across separate calls — each call treats a truncated `=4` (missing the second hex digit) as literal text rather than buffering it, per `a2b_qp`'s own documented per-call behavior.
Type: known-external
Confidence: medium

### aiohttp-54
Oracle: `MultipartWriter.decode(encoding, errors)`'s own signature and docstring say it decodes with the given `encoding`/`errors`; the implementation (multipart.py:1147-1160) only applies them to `part._binary_headers.decode(encoding, errors)` and calls `part.decode()` (the part's own no-argument `decode`) for the body, ignoring the caller-supplied encoding/errors for the actual content — contradicts the method's own parameter contract.
Type: in-repo
Confidence: high

### aiohttp-55
Oracle: `socket.create_server`'s own documentation states `reuse_port=True` sets `SO_REUSEPORT`, which explicitly allows multiple independent sockets to bind the same address/port and receive connections (load-balanced) — different from `SO_REUSEADDR`'s (address-reuse-after-close) semantics that `REUSE_ADDRESS` is named for; the socket factory passes the `REUSE_ADDRESS` value into the `reuse_port` parameter, giving `SO_REUSEPORT` behavior under a name suggesting `SO_REUSEADDR`, and test servers silently share a port instead of erroring on collision.
Type: known-external
Confidence: high

### aiohttp-56
Oracle: RFC 9112 §3.2.3 / RFC 7230 define the absolute-form request-target as including the full URI; `raw_path`'s own purpose (web_request.py:515-541) is to expose "path[?query]" of the request line, and for `GET http://example.com HTTP/1.1` (a valid absolute-form request-target with empty path) it returns `''` — dropping the distinction between "no path component parsed" and "the actual path is `/`" that the RFC's URI-normalization rules would otherwise resolve (an empty path in an absolute-URI is equivalent to `/`).
Type: known-external
Confidence: low

### aiohttp-57
Oracle: The comparison `self._payload_bytes_to_read >= self._max_msg_size - partial_len` (reader_py.py:552) rejects a message whose size *equals* `max_msg_size`, but the exception text it raises literally says `"Message size {X} exceeds limit {max_msg_size}"` — when X equals the limit, it has not exceeded it, only reached it; the error message's own wording contradicts the `>=` (should-be `>`) comparison used to trigger it.
Type: in-repo
Confidence: medium

### aiohttp-58
Oracle: `DigestAuthMiddleware.__call__` (client_middleware_digest_auth.py:470-503) sends the same `request` object twice (once unauthenticated to get the 401 challenge, then again with the Authorization header) via `handler(request)`; for an async-generator body, `AsyncIterablePayload.write_with_length` (payload.py) consumes the generator on the first send, leaving nothing to yield on the retry, while the request's `Content-Length`/headers still describe the original body size — the payload class's single-consumption nature (generators can't be replayed) is the oracle, and the middleware's own retry design assumes replayability it doesn't verify.
Type: in-repo
Confidence: high

### aiohttp-59
Oracle: `MultipartWriter.decode` (multipart.py:1147-1160) joins `"--" + boundary + "\r\n" + headers + part.decode()` per part with no trailing `\r\n` after each body and no closing `--boundary--\r\n`; RFC 2046 §5.1.1's multipart body syntax requires a CRLF before each boundary delimiter and a final close-delimiter (`--boundary--`), which `as_bytes()` (the async sibling method in the same class, referenced in its own docstring as the non-blocking equivalent) presumably gets right by comparison — the `decode()` output is not valid multipart framing per that RFC.
Type: known-external
Confidence: high

### aiohttp-60
Oracle: `self._lines[-1] != "\r\n"` (http_parser.py:324) compares a `bytes` element of `self._lines` (the file's `_lines` are appended from `self._tail`, a bytes buffer, and other bytes sources) against the `str` literal `"\r\n"`; in Python 3, `bytes != str` is always `True` regardless of content, so the condition can never correctly detect "last line already is the CRLF terminator" — a language-level type-mismatch bug, not a logic error requiring external spec knowledge.
Type: implicit
Confidence: medium

### aiohttp-61
Oracle: `CLEANUP_RE = re.compile(r"(%[^s])")` combined with `log_format = self.FORMAT_RE.sub(r"%s", log_format); log_format = self.CLEANUP_RE.sub(r"%\1", log_format)` is meant to re-escape literal `%` signs left after atom substitution (per the docstring's `%%` = "the percent sign" entry) but doubles them incorrectly when a literal `%` sits next to a substituted `%s`: `'%%  %a'` → after FORMAT_RE substitution `'%%  %s'` → CLEANUP_RE matches `%%`... producing `'%%%  %s'`, an extra `%` that breaks Python's `%`-style string formatting at `log()` time (caught only by the surrounding try/except that logs "Error in logging").
Type: in-repo
Confidence: high

---

The hardest ones to classify were aiohttp-41 (message omitting the received value — I couldn't find any in-repo convention or external contract requiring it, so it landed at `none`/low rather than a real defect), aiohttp-56 (the RFC 9112 absolute-form request-target rule doesn't unambiguously say what `raw_path` specifically should return for an empty-path absolute-URI, so I could only reason to `known-external`/low rather than cite a concrete section), and aiohttp-10 (the readuntil buffer-boundary case actually produces what looks like the *correct* answer given the two `feed_data` calls, so I could not point to anything that makes it wrong beyond a vague appeal to "should span chunks," landing at `in-repo`/low — this may in fact be a `none`). aiohttp-53 and aiohttp-43 were also close calls between `in-repo` and `known-external`, since the correct behavior is visible from both the stdlib/RFC contract and the code's own branch structure, and I had to pick which one I'd actually rely on.
