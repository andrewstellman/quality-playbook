# aiohttp, classifier S2 (Claude Sonnet), blind

Note: this classifier merged some pairs into one block (05/13, 15/46, 16/17, 35/52). The merged block's type and confidence apply to both IDs.

### aiohttp-01
Oracle: `_read()`/`_read_and_available_len()` in aiohttp/payload.py:512,532 use `remaining_content_len or DEFAULT_CHUNK_SIZE`, so a legitimate `remaining_content_len=0` (write exactly 0 bytes) is treated as "no limit given" and reads/writes a full 256 KiB chunk instead of 0.
Type: in-repo
Confidence: high

### aiohttp-02
Oracle: `_decode_content` (sync) calls `ZLibDecompressor(...).decompress_sync(data, max_length=...)` once and returns the result, but the sibling async path `_decode_content_async` loops `while d.data_available: yield await d.decompress(b"", ...)` to drain the rest. The sync path is missing that drain loop, so zlib's silent truncation at `max_length` is never followed up.
Type: in-repo
Confidence: high

### aiohttp-03
Oracle: `_authenticate` does `method, sep, headers = auth_header.partition(" ")` on the single already-comma-joined `www-authenticate` value; it only inspects the first scheme token and returns `False` if it isn't `"digest"`, never scanning for a later Digest challenge in the same joined string.
Type: in-repo
Confidence: high

### aiohttp-04
Oracle: `StreamWriter.write()` (http_writer.py:200-202) truncates outgoing data to `self.length` before writing, but `write_eof()` never consults `self.length` in the uncompressed/non-chunked branch (`if chunk: self._write(chunk)`), so it writes the whole argument regardless of a shorter declared Content-Length.
Type: in-repo
Confidence: high

### aiohttp-05 / aiohttp-13
Oracle: `FORMAT_RE = re.compile(r"%(\{([A-Za-z0-9\-_]+)\}([ioe])|[atPrsbOD]|Tf?)")` accepts atoms `O` and `%{...}e`, but `LOG_FORMAT_MAP` has no `"O"` or `"e"` key, and there is no `_format_O`/`_format_e` method (`grep` confirms only a/t/P/r/s/b/T/Tf/D/i/o are defined) — `compile_format` does `getattr(AccessLogger, "_format_%s" % atom)` unconditionally, raising `KeyError`/`AttributeError` at construction.
Type: in-repo
Confidence: high

### aiohttp-06
Oracle: `HeadersDictProxy.getall` (helpers.py:788-802) splits a header's raw value generically on unescaped commas per RFC 7230 §3.2.2 list-header combining rules; RFC 8288 §3 defines the `Link` header's comma-separated syntax where each element is `<URI-Reference>` and the URI itself is not a quoted-string, so an unescaped comma inside the URI is valid and must not be treated as a list separator.
Type: known-external
Confidence: high

### aiohttp-07
Oracle: docs/client_reference.rst: "`max_redirects`: Maximum number of redirects to follow" — with the loop doing `redirects += 1` then `if max_redirects and redirects >= max_redirects: raise TooManyRedirects` *before* the redirect is followed, `max_redirects=1` follows zero redirects and any N follows at most N-1, contradicting the documented parameter meaning.
Type: in-repo
Confidence: high

### aiohttp-08
Oracle: `_start_compression` picks an encoding via `if value in accept_encoding` substring matching, ignoring qvalues. RFC 9110 §12.5.3 defines `q=0` in an Accept-Encoding token as meaning "not acceptable," so `gzip;q=0` must not select gzip.
Type: known-external
Confidence: high

### aiohttp-09
Oracle: Manual read of `Response.write_eof` — `if body is None or self._must_be_empty_body: await super().write_eof()` — this branch never calls `Payload.close()`; the `elif isinstance(self._body, Payload):` branch a few lines below does call `self._body.close()` in a `finally`, showing close is required for `Payload` bodies but is skipped when `_must_be_empty_body` is true.
Type: implicit
Confidence: high

### aiohttp-10
Oracle: `readuntil` searches for the separator only within `self._buffer[0]` per iteration (`self._buffer[0].find(separator, offset)`), so a multi-byte separator split across two `feed_data` chunks (`\r` at the end of one, `\n` at the start of the next) is not detected at the true boundary; this matches asyncio.StreamReader's contract that a stream reader must not expose internal buffering/chunking to callers.
Type: known-external
Confidence: medium

### aiohttp-11
Oracle: The per-request `cookies=` path builds `tmp_cookie_jar = CookieJar(unsafe=self._cookie_jar.unsafe, quote_cookie=self._cookie_jar.quote_cookie)` (client.py:649-652), omitting `treat_as_secure_origin`, unlike the session's main `self._cookie_jar`, which was constructed with it — the temp jar's `Secure`-cookie filtering therefore doesn't know `http://localhost` is trusted.
Type: in-repo
Confidence: high

### aiohttp-12
Oracle: I can't point to anything requiring `HTTPMethodNotAllowed.__init__` to normalize case; it simply stores whatever string it's given, and its only in-repo callers (`web_urldispatcher.py:939,1021`) pass `request.method`, which is always uppercase coming off the wire.
Type: none
Confidence: low

### aiohttp-14
Oracle: `self._post` (which `_finish()` at web_request.py:946-953 walks to `.close()` each `FileField.file`) is assigned only at the very end of `post()` (`self._post = MultiDictProxy(out)`, line 917), after the loop finishes; when the `max_size`/`max_fields` check raises mid-loop, `_post` stays unset (or None), so the temp files for fields already accumulated in the local `out` are never closed by `_finish()`.
Type: in-repo
Confidence: high

### aiohttp-15 / aiohttp-46
Oracle: `EmptyStreamReader.__init__` (streams.py:601-604) sets only `self._read_eof_chunk` and `self.total_bytes`, never calling the base `StreamReader.__init__`, so attributes the base class defines (`total_compressed_bytes`, `_exception`) don't exist on the instance; `total_raw_bytes` (base class property) reads `self.total_compressed_bytes` and `readuntil` (inherited, since `EmptyStreamReader` doesn't override it — confirmed by the `# TODO add async def readuntil` comment) reads `self._exception`, both raising `AttributeError`.
Type: implicit
Confidence: high

### aiohttp-16 / aiohttp-17
Oracle: `MultipartReader.next()` special-cases a `_charset_` field by calling `part.read_chunk(32)` directly (multipart.py:812), bypassing `_read_chunk_from_stream`'s own precondition `assert size >= self._boundary_len` (line 448-450) — 32 can be smaller than a long boundary. It then calls `fetch_next_part()` immediately without releasing/consuming the rest of that part (including the terminating `--boundary` line), unlike `_readline`'s handling elsewhere in the reader which checks `self._unread` first.
Type: in-repo
Confidence: high

### aiohttp-18
Oracle: `ClientResponse.json()` decodes the body with the caller-supplied `loads` (default `json.loads`), and an empty/whitespace-only string is not valid JSON per the JSON grammar (RFC 8259) — this is exactly `json.loads('')`'s own behavior, so this looks like expected library behavior rather than an aiohttp defect.
Type: known-external
Confidence: low

### aiohttp-19
Oracle: `MultipartReader._readline()` (multipart.py:884-886) checks `self._unread` before reading from the stream, but `_read_headers()` (line ~924) calls `self._content.readline(...)` directly, never consulting `self._unread` — so a line queued into `_unread` by `_read_boundary()`'s nested-multipart epilogue handling (lines 903-920) is skipped by the very next header read.
Type: in-repo
Confidence: high

### aiohttp-20
Oracle: `_cached_build_client_middlewares = lru_cache(maxsize=64)(build_client_middlewares)` (client_middlewares.py:58) caches closures keyed by the middleware tuple; those closures capture the middleware instances (e.g., `DigestAuthMiddleware` holding login/password) and stay referenced from the module-level cache for up to 64 distinct tuples regardless of whether the owning `ClientSession` has been closed — a resource/reference leak.
Type: implicit
Confidence: high

### aiohttp-21
Oracle: In the redirect branch that downgrades method to GET (client.py:781-787), unlike the sibling `TooManyRedirects` branch just above it which explicitly does `if req._body is not None: await req._body.close()` before discarding the body, the GET-downgrade branch sets `data = None` with no corresponding close of `req._body`.
Type: in-repo
Confidence: high

### aiohttp-22
Oracle: `Response._do_start_compression` (web_response.py:720-735) has `assert self._body is not None` right before compressing; when body is `None` (204/no-body response) this assert fires, and since assertions are stripped under `python -O`, the following `compressor.compress(self._body)` receives `None`, raising `TypeError`.
Type: implicit
Confidence: high

### aiohttp-23
Oracle: Same `HeadersDictProxy.getall` mechanism as aiohttp-06 — it splits unquoted commas generically, but RFC 9110's `Date`/`Set-Cookie`/`Expires` grammars contain literal commas inside the value itself (the day-name comma in HTTP-date) that are not list separators; RFC 7230 §3.2.2 notes exactly this exception for headers like `Set-Cookie` that cannot be safely combined/split on commas.
Type: known-external
Confidence: high

### aiohttp-24
Oracle: In `http_range`, `end = int(end) if end else None` treats the parsed suffix-length string `'0'` as truthy (non-empty string) giving `end=0`, but then `start = int(start) if start else None` with `start=''` gives `start=None`; the subsequent `if start is None and end is not None: start = -end` computes `start = -0 = 0`, `end = None`, producing `slice(0, None, 1)` — a full-file range instead of the empty range RFC 9110 §14.1.2 requires for a zero-length suffix-byte-range-spec ("a client can only request a decimal number of bytes... a suffix-length of 0 is not satisfiable" per RFC 7233 discussion of suffix-byte-range-spec).
Type: known-external
Confidence: high

### aiohttp-25
Oracle: `_update_cookies` only calls `_expire_cookie(...)` inside the `if max_age := cookie["max-age"]:` or `elif expires := cookie["expires"]:` branches (cookiejar.py:396-414); when a later `Set-Cookie` for the same name carries neither attribute, neither branch executes, so the `_expirations` entry set by the earlier cookie with the same `(domain, path, name)` key is never cleared, leaving a stale expiry attached to the new session cookie.
Type: in-repo
Confidence: high

### aiohttp-26
Oracle: `_is_domain_match(domain, hostname)` (cookiejar.py:532-545) does plain string `==`/`endswith` comparisons with no case-folding; RFC 6265 §5.1.3 specifies domain matching is case-insensitive (`hostname` and cookie-domain compared "in an ASCII case-insensitive manner").
Type: known-external
Confidence: high

### aiohttp-27
Oracle: `BaseRequest.forwarded`'s own docstring (web_request.py:365-383) says it parses "as specified by RFC 7239" and adds "one dictionary per Forwarded field-value" / "per proxy" (i.e., per comma-separated element), but `_FORWARDED_PAIR` (web_request.py:138-140) only terminates a pair on `\Z` or `;`, so the pair-loop in `forwarded` breaks at the first comma and drops subsequent proxy elements. RFC 7239 §4 defines the comma as the element separator.
Type: known-external
Confidence: high

### aiohttp-28
Oracle: `_default_expect_handler`'s own docstring documents exactly this: "raise HTTPExpectationFailed if value of header is not '100-continue'," and its only real caller, `Application._handle` (web_app.py:381-382), guards the call with `if request.headers.get(hdrs.EXPECT):` — so in normal request handling this function is never invoked without an Expect header present; the reported behavior only occurs when the handler is invoked directly (e.g., a custom expect_handler wiring or unit test), not through the framework's own dispatch path.
Type: in-repo
Confidence: low

### aiohttp-29
Oracle: `HeadersDictProxy.__eq__` delegates to `self._md.__eq__(other)` (the underlying `CIMultiDict`'s own equality, which treats duplicate keys as ordered pairs), while `__getitem__`/`__iter__`/`__len__` on the very same class present it as a `Mapping` that joins duplicate values with `", "` — the two views of the class disagree, breaking the usual Mapping equality contract (`dict(p) == {'A': v}` implies `p == {'A': v}` for a proper Mapping).
Type: in-repo
Confidence: high

### aiohttp-30
Oracle: `Accept-Encoding: identity, gzip;q=0` — same substring-match bug as aiohttp-08 but in `FileResponse._get_file_path_stat_encoding`; RFC 9110 §12.5.3's `q=0` semantics say gzip must not be selected here, yet the `.gz` sibling file is served.
Type: known-external
Confidence: high

### aiohttp-31
Oracle: `_update_headers` (client_reqrep.py:913) `pop`s `Host` out of the headers dict object the caller passed, and `ClientSession._request`'s retry/redirect loop (client.py) reuses that same `headers` object across iterations — after the first send strips `Host`, a later same-loop retry/redirect rebuilds `Host` from the URL instead of honoring the caller's original explicit header, since it's already gone from the shared dict.
Type: in-repo
Confidence: high

### aiohttp-32
Oracle: `forwarded`'s own code at web_request.py:396-399 does `if value[0] == value[-1] == '"': value = value[1:-1]` — strips quotes only, with no backslash-unescape step, even though `_QDTEXT`/quoted-pair comments (web_request.py:131-135) elsewhere in the same file explicitly document `qdtext` and the `\]`-escaping construct, showing the module is aware quoted-strings can contain escapes that this code path ignores.
Type: in-repo
Confidence: medium

### aiohttp-33
Oracle: `HeadersDictProxy.__iter__` only deduplicates on exact string match (`if k in seen`), so differently-cased instances of the same case-insensitive header name (`X` vs `x`) are both yielded and both counted by `__len__`, while `__getitem__`/`dict(h)` (via `_md.getall`, case-insensitive) return the *same* combined `"1, 2"` value under both keys — internally inconsistent representation of what should be one logical header.
Type: in-repo
Confidence: medium

### aiohttp-34
Oracle: `ClientTimeout.__post_init__`'s own error message documents the intended contract: "Using 0 to disable timeouts is no longer supported, use None instead," raised only when `self.total == 0`. But `total` is first silently overwritten to `max(self.total, self.connect or 0, ...)` (comment: "Ensure total is never lower than a more specific timeout") *before* that check, so `ClientTimeout(total=0, connect=5)` becomes `total=5` and never hits the check the comment says should apply to `total=0`.
Type: in-repo
Confidence: high

### aiohttp-35 / aiohttp-52
Oracle: In `HttpPayloadParser.feed_data`'s chunked/trailers parsing, the length check against `max_line_size`/`max_field_size` only runs in the `if self._chunk_tail:` branch at the top of the next `feed_data()` call (http_parser.py:999-1007); when no separator is found in the current call, the code does `self._chunk_tail = chunk; return PAYLOAD_NEEDS_INPUT` with no length check at all for that call, so an oversized single-call block is buffered unchecked until the following call.
Type: in-repo
Confidence: high

### aiohttp-36
Oracle: Same falsy-zero pattern as aiohttp-01/51: `max_size = max_size or self._high_water` treats an explicit `max_size=0` (reachable via `readline(max_line_length=0)`) as "not given," substituting `self._high_water` instead of enforcing a zero-byte limit.
Type: in-repo
Confidence: high

### aiohttp-37
Oracle: `_prepare_headers` computes a local `keep_alive` and sets `self._keep_alive = keep_alive` once near the top (web_response.py:378), but the later HTTP/1.0-with-unknown-length branch (`elif not self._must_be_empty_body: keep_alive = False`) only reassigns the local variable, never re-syncing `self._keep_alive`; the header-writing code further down does use the (correctly updated) local `keep_alive` to omit the `Connection: keep-alive` header, but the connection-management state `self._keep_alive` used elsewhere in the protocol stays stale at `True`.
Type: in-repo
Confidence: high

### aiohttp-38
Oracle: `_align_base64_chunk`'s own comment at the `if not cut:` branch acknowledges the case directly: "No whole quartet to hand back, and carrying the lot would make no progress... holds none to give," and returns the chunk unchanged anyway; a base64 stream passed a chunk that isn't a multiple of 4 characters raises `binascii.Error` when decoded on its own.
Type: in-repo
Confidence: medium

### aiohttp-39
Oracle: `_FORWARDED_PAIR` (web_request.py:138-140) uses `".*"` (regex `.*` is greedy) for the quoted-value alternative with `re.match`, so given `for="a";by="b"` it matches greedily up to the *last* `"` in the whole string, swallowing the semicolon and next pair's key/value into what should be just `for`'s value.
Type: in-repo
Confidence: high

### aiohttp-40
Oracle: `Domain.match_domain` (the base class, web_urldispatcher.py:808-809) does `host.lower() == self._domain` — explicitly case-folds the host before comparing to the already-lowercased stored domain (`Domain.validation` calls `.lower()`) — but the `MaskDomain` subclass overrides `match_domain` with `self._mask.fullmatch(host)` and neither lowercases `host` nor compiles the regex with `re.IGNORECASE`.
Type: in-repo
Confidence: high

### aiohttp-41
Oracle: `InvalidHeader.__init__` (http_exceptions.py:87-91) is constructed with just the header name and formats `f"Invalid HTTP header: {hdr!r}"`, which by construction can never include a received value — this may well be intentional (avoiding raw header-value injection into logs/exceptions) rather than a defect.
Type: none
Confidence: low

### aiohttp-42
Oracle: `read_nowait`'s own comment says it outright: "TODO: Save and await this task" (streams.py:539), directly above `asyncio.create_task(cb(chunk))` with no stored reference — the maintainers' own comment documents the gap the finding describes.
Type: in-repo
Confidence: high

### aiohttp-43
Oracle: `_update_cookies`'s `if max_age := cookie["max-age"]: try: ... except ValueError: cookie["max-age"] = ""` / `elif expires := cookie["expires"]:` structure means that once `max_age` is truthy (present), the `elif` branch for `Expires` is never evaluated even if parsing `max_age` fails inside the `try`/`except` — so a present-but-unparsable Max-Age silently suppresses checking Expires too, per RFC 6265 §5.2.2 which specifies Max-Age should take precedence over Expires only when *both are valid*, not when Max-Age is malformed.
Type: known-external
Confidence: high

### aiohttp-44
Oracle: `UrlDispatcher.HTTP_NOT_FOUND = HTTPNotFound()` is a single class-level instance, and `SystemRoute._handle` does `raise self._http_exception` — reusing one exception object across raises causes CPython to keep appending to its `__traceback__` chain on each raise, and each traceback frame holds references to the local variables of that call (including the `Request`), producing a real reference/memory leak. This is a well-documented Python gotcha with reused exception instances.
Type: implicit
Confidence: high

### aiohttp-45
Oracle: `SEPARATORS` (helpers.py:152 ff.) explicitly lists `chr(9)` (TAB), and `CTL = {chr(i) for i in range(0,32)} | {chr(127)}` also contains `chr(9)`; `TOKEN = CHAR ^ CTL ^ SEPARATORS` uses symmetric difference (XOR) instead of set subtraction, so an element present in all three operand sets (an odd count) — TAB — is *kept* rather than excluded, matching RFC 9110's `tchar`/`token` grammar (§5.6.2) which explicitly excludes CTLs and separators including TAB.
Type: known-external
Confidence: high

### aiohttp-47
Oracle: `_update_transfer_encoding` (client_reqrep.py:1231-1246) only raises/reacts when the internal `self.chunked` flag is set; a user who manually sets `headers={'Transfer-Encoding': 'chunked'}` without also passing `chunked=True` leaves `self.chunked` False, so the method's `if "chunked" in te: if self.chunked: raise` branch is a no-op, and `_update_body_from_data` goes on to add an auto `Content-Length` header since `self.chunked` is still False — the two headers end up contradicting each other with no framing to match either.
Type: in-repo
Confidence: high

### aiohttp-48
Oracle: `RequestHandler.__init__` sets `self._keepalive = False` (web_protocol.py:246), and `_process_keepalive` (line 649-651) returns immediately `if self._force_close or not self._keepalive:` — the keepalive timer is only armed once `self._keepalive` becomes True, which (based on the naming/structure) happens after a request completes; `connection_made` (line 393 ff.) arms no other timer for a connection that never completes a request, so a client that opens and sends nothing has no timeout bound on it via this mechanism.
Type: in-repo
Confidence: medium

### aiohttp-49
Oracle: `self.chunked: bool | None` (client_reqrep.py:1034/1082) is `None` when unset, but `_create_writer`'s check `if self.chunked is not None: writer.enable_chunking()` (line 1450) treats any non-`None` value — including an explicit `chunked=False` — as "enable chunking," conflating "explicitly disabled" with "explicitly enabled."
Type: in-repo
Confidence: high

### aiohttp-50
Oracle: `BodyPartReaderPayload.write` (multipart.py:703-711) calls `field.decode_iter(chunk)` once per chunk in a loop, and `decode_iter`/`_decode_content_async` (lines 593-633) construct a brand-new `ZLibDecompressor` on every call — a streaming (de)compressor must retain its window/state across chunks, so a fresh decompressor per chunk cannot correctly continue decompressing data whose dictionary state was built by the previous chunk.
Type: in-repo
Confidence: high

### aiohttp-51
Oracle: Same falsy-zero pattern again: `read_chunk`'s branch `if self._length:` (multipart.py:389) treats a part with `Content-Length: 0` the same as "length unknown," routing it to `_read_chunk_from_stream` (boundary scanning) instead of `_read_chunk_from_length` (which would correctly read exactly the declared 0 bytes).
Type: in-repo
Confidence: high

### aiohttp-53
Oracle: `_decode_content_transfer` (multipart.py:636-642) calls `binascii.a2b_qp(data)` fresh on each chunk with no carried state, the same per-chunk-statelessness bug as aiohttp-50; a `=41`-style escape or a `=\r\n` soft line break that straddles a chunk boundary (e.g., the 256 KiB read boundary in `request.post()`) is decoded incorrectly because neither half alone is valid quoted-printable.
Type: in-repo
Confidence: high

### aiohttp-54
Oracle: `MultipartWriter.decode(encoding, errors)` (multipart.py:1147-1160) applies `encoding`/`errors` only to `part._binary_headers.decode(encoding, errors)`; the body is produced by `part.decode()` called with no arguments at all, so the caller-supplied `encoding`/`errors` are silently ignored for the part of the output that they'd most obviously be expected to affect (the payload text).
Type: in-repo
Confidence: high

### aiohttp-55
Oracle: `create_server`'s Python stdlib signature accepts `reuse_address`/`reuse_port` as separate keyword parameters with different socket-option semantics (`SO_REUSEADDR` vs `SO_REUSEPORT`); passing `REUSE_ADDRESS`'s value into the `reuse_port=` slot sets the wrong socket option, letting two independent test servers bind the same port and both receive connections — this is test-infrastructure code (`test_utils.py`), which increases the chance it's a known, low-priority utility bug rather than a production concern, but the behavior itself is clearly wrong against the stdlib socket API contract.
Type: known-external
Confidence: medium

### aiohttp-56
Oracle: RFC 9112 §3.2.2 (absolute-form request-target) says that when converting/handling an absolute-form target with no explicit path, it's treated the same as an origin-form target of `"/"` — the code's own comment cites this RFC section, yet the actual slicing (`path[rel:]` where `rel` defaults to `len(path)` when no `/?#` delimiter is found after the authority) returns `""` instead of `"/"`, and similarly `"?x=1"` instead of `"/?x=1"`.
Type: known-external
Confidence: high

### aiohttp-57
Oracle: `if self._payload_bytes_to_read >= self._max_msg_size - partial_len: raise WebSocketError(..., f"Message size {...} exceeds limit {self._max_msg_size}")` — using `>=` means a message exactly equal to `max_msg_size` is rejected as "exceeding" it, though it doesn't; the parameter is documented/named as a maximum (an inclusive bound), not a strict upper bound.
Type: in-repo
Confidence: high

### aiohttp-58
Oracle: The digest-auth retry loop (`for retry_count in range(2): ... response = await handler(request)`, client_middleware_digest_auth.py:483-497) reuses the same `request` object for both the initial (401-triggering) send and the authenticated retry with no guard against a non-replayable body; this is exactly the scenario `client.py`'s redirect handling explicitly guards against elsewhere (`if req._body.consumed: raise ClientPayloadError(...)` before reusing a payload across a retry) — no equivalent check exists here.
Type: in-repo
Confidence: high

### aiohttp-59
Oracle: Sibling comparison within the same class: `MultipartWriter.as_bytes()` (multipart.py:1162-1186) explicitly appends `b"\r\n"` after each part body and a final `b"--" + boundary + b"--\r\n"` closing boundary; `MultipartWriter.decode()` (lines 1147-1160) does neither, producing output that isn't valid multipart wire format.
Type: in-repo
Confidence: high

### aiohttp-60
Oracle: `self._lines` holds `bytes` objects (confirmed by the adjacent `self._lines.append(b"")` and `self._tail` being bytes), but `feed_eof` compares `self._lines[-1] != "\r\n"` against a `str` literal — in Python 3, `bytes != str` is always `True` regardless of content, so the branch always executes.
Type: implicit
Confidence: high

### aiohttp-61
Oracle: `compile_format` first substitutes atoms with `FORMAT_RE.sub(r"%s", log_format)`, then runs `CLEANUP_RE = re.compile(r"(%[^s])")` via `CLEANUP_RE.sub(r"%\1", log_format)`, which re-escapes any leftover `%`-followed-by-non-`s` sequence (like a literal `%%`) by prepending another `%`, turning `"%%  %s"` into `"%%%  %s"`; that string is then invalid as a `%`-format template, so `log()`'s own `%`-formatting call fails and hits its "Error in logging" fallback.
Type: in-repo
Confidence: high

---

The hardest to classify were the ones where the described behavior is real and reproducible but the *oracle for "wrong"* is genuinely ambiguous rather than the code being ambiguous: aiohttp-12 (`HTTPMethodNotAllowed` not uppercasing) and aiohttp-41 (exception message omitting the header value), where nothing in the repo states a contract the behavior violates, so I could only call them low-confidence/`none`; aiohttp-28, where the described crash is real in isolation but the only production call site already guards against it, making the practical severity hard to judge; aiohttp-18, where the "defect" is arguably just `json.loads` behaving exactly as the stdlib always has; and aiohttp-38/aiohttp-55, where the code's own comment (38) or the fact that it's test-only infrastructure (55) suggests the maintainers were aware of the edge case, which cuts against treating it as an accidental defect even though the resulting behavior is still wrong by some standard.
