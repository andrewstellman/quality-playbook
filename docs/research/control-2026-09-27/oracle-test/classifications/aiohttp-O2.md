# aiohttp, classifier O2 (Claude Opus), blind

### aiohttp-01
Oracle: The `_read` docstring (payload.py:521-522) says "remaining_content_len: Optional maximum number of bytes to read. If None, DEFAULT_CHUNK_SIZE will be used". Only None is meant to fall back to 256 KiB, but `remaining_content_len or DEFAULT_CHUNK_SIZE` also turns a limit of 0 into a full-chunk read. The impact is small: nothing wrong is written, only the file position moves.
Type: in-repo
Confidence: low

### aiohttp-02
Oracle: The sibling `_decode_content_async` (multipart.py:630-632) keeps calling `decompress(b"", max_length=...)` while `d.data_available`, so it returns all the output. The sync `_decode_content` makes one capped call and silently drops the rest. The docs (multipart_reference.rst) say `decode` "Decodes data" and mention no truncation.
Type: in-repo
Confidence: high

### aiohttp-03
Oracle: RFC 9110 §11.6.1 (formerly RFC 7235 §4.1) lets a 401 carry several challenges, in one field or in several fields. A client should pick the scheme it supports, not just the first token of the joined value.
Type: known-external
Confidence: medium

### aiohttp-04
Oracle: The sibling `StreamWriter.write` (http_writer.py:195-203) cuts the chunk to `self.length`, so `write_eof` should apply the same cap. RFC 9112 §6.3 also says a body must not be longer than its declared Content-Length.
Type: in-repo
Confidence: high

### aiohttp-05
Oracle: The `AccessLogger` class docstring (web_log.py:43) documents `%{FOO}e  os.environ['FOO']`, and the `compile_format` docstring names `_format_e`. Neither the `LOG_FORMAT_MAP` entry nor the method exists, so a documented format crashes at construction.
Type: in-repo
Confidence: high

### aiohttp-06
Oracle: RFC 8288 §3 puts a URI-Reference inside `<...>`, and a URI may contain commas, so a comma inside angle brackets does not separate links. The list splitter treats `<` as ordinary text.
Type: known-external
Confidence: high

### aiohttp-07
Oracle: docs/client_reference.rst:481-482 says "max_redirects: Maximum number of redirects to follow. TooManyRedirects is raised if the number is exceeded." With `redirects >= max_redirects` after the increment, the limit is reached, not exceeded, when the exception fires.
Type: in-repo
Confidence: high

### aiohttp-08
Oracle: Under RFC 9110 §12.5.3, a `q=0` weight means the coding is "not acceptable", and a substring check on the header ignores that. Nothing in the repo parses q-values for a comparison.
Type: known-external
Confidence: high

### aiohttp-09
Oracle: The sibling branch in the same method (web_response.py:686-690) always calls `await self._body.close()` in a `finally` for a Payload body. The empty-body branch skips that, which also leaks the file (an implicit resource leak).
Type: in-repo
Confidence: high

### aiohttp-10
Oracle: docs/streams.rst:85 says `readuntil` will "Read until separator". Returning bytes past the first `\r\n` because the separator was split across two buffers breaks that. It also breaks the standard asyncio `readuntil` contract.
Type: in-repo
Confidence: high

### aiohttp-11
Oracle: The temporary jar in client.py:648-651 copies the session jar's `unsafe` and `quote_cookie`, which shows the intent to mirror the session jar's policy. The `treat_as_secure_origin` setting (cookiejar.py:87) is left out, so per-request cookies follow a different secure-origin policy than jar cookies.
Type: in-repo
Confidence: medium

### aiohttp-12
Oracle: The docs (web_exceptions.rst:413-415) say only "Requested but not allowed HTTP method." RFC 9110 §9.1 says methods are case-sensitive, so upper-casing would be the wrong behaviour.
Type: none
Confidence: low

### aiohttp-13
Oracle: Constructing the logger raises an uncaught `KeyError` for a format atom that `FORMAT_RE` explicitly accepts. `%O` is not in the class docstring, so the crash itself is the oracle.
Type: implicit
Confidence: medium

### aiohttp-14
Oracle: The temp files are leaked. The sibling mid-read size check (web_request.py:833-838) closes `tmp` before it raises, and `_finish` says it exists to "Release the temp files created within multipart request body". The top-of-loop raises skip both.
Type: implicit
Confidence: medium

### aiohttp-15
Oracle: Reading a public property on the `EMPTY_PAYLOAD` singleton raises `AttributeError`, because `EmptyStreamReader.__init__` never sets the `total_compressed_bytes` slot.
Type: implicit
Confidence: medium

### aiohttp-16
Oracle: An internal `AssertionError` escapes to the caller on valid input. The RFC 7578 §4.6 `_charset_` path calls `read_chunk(32)`, but form-data parts always use the stream path, which asserts that `size >= boundary_len`.
Type: implicit
Confidence: high

### aiohttp-17
Oracle: The normal path of `MultipartReader.next` (multipart.py:790-797) calls `_maybe_release_last_part()` and `_read_boundary()` before `fetch_next_part()`. The `_charset_` path skips both, so the boundary line gets parsed as headers. The result is an `InvalidHeader` crash or a bogus header.
Type: in-repo
Confidence: high

### aiohttp-18
Oracle: An empty body is not valid JSON (RFC 8259), so raising is correct. The server-side sibling `BaseRequest.json` (web_request.py:754-771) also just calls `loads` on the body. Nothing in the repo promises `None` for an empty body.
Type: none
Confidence: low

### aiohttp-19
Oracle: The comment in `_read_boundary` (multipart.py:908-915) says a line read past the epilogue "should be marked as unread and handed to the parent for processing". `_read_headers` reads from `self._content` directly and ignores `_unread`, so those lines are lost.
Type: in-repo
Confidence: high

### aiohttp-20
Oracle: Credentials held by middleware stay referenced after the session closes. But the cache is deliberate and capped at 64 entries, and nothing in the repo says closed sessions must release their middlewares.
Type: implicit
Confidence: low

### aiohttp-21
Oracle: Every other exit from the redirect loop calls `await req._body.close()` before dropping the request body: TooManyRedirects, InvalidUrlRedirect and NonHttpUrlRedirect (client.py:777, 822, 832, 842). The 302/303 method switch sets `data = None` without closing it, which is a file-handle leak.
Type: in-repo
Confidence: medium

### aiohttp-22
Oracle: `prepare()` raises an uncaught `AssertionError` from `assert self._body is not None` (web_response.py:728), or `TypeError` under `-O`. The trigger is a legal response with no body plus compression enabled.
Type: implicit
Confidence: high

### aiohttp-23
Oracle: docs/client_reference.rst:1555 tells users to call `response.headers.getall('Set-Cookie')` to get all cookies, and splitting a cookie at the comma in `Expires` breaks that. RFC 9110 §5.3 also says Set-Cookie and Date are not comma-separated list headers.
Type: in-repo
Confidence: high

### aiohttp-24
Oracle: The RFC 7233 text quoted in web_fileresponse.py:385-392 makes a suffix range satisfiable only with "a non-zero suffix-length ... Otherwise, the byte-range-set is unsatisfiable". So `bytes=-0` should get a 416, not a 206 with the whole file.
Type: in-repo
Confidence: high

### aiohttp-25
Oracle: RFC 6265 §5.3 (steps 3 and 11) says a new cookie with no Max-Age or Expires is a non-persistent cookie that replaces the old one, including its expiry. The stale `_expirations` entry then expires the new cookie.
Type: known-external
Confidence: high

### aiohttp-26
Oracle: RFC 6265 §5.1.3 domain-matching works on canonicalized, lower-case strings, and §5.2.3 says to lower-case the Domain attribute. The `_is_domain_match` docstring says "adhering to RFC 6265", and `Domain.validation` in web_urldispatcher.py lower-cases domains.
Type: known-external
Confidence: high

### aiohttp-27
Oracle: Commas are split upstream by `HeadersDictProxy.getall`, and the tests show that is intended: test_web_request.py:804-811 and the injection tests check one dict per comma-separated element. So the pair loop may never see a comma in practice. Only RFC 7239 §4 could apply, and only if the loop were fed raw strings.
Type: none
Confidence: low

### aiohttp-28
Oracle: The handler's docstring says to raise `HTTPExpectationFailed` "if value of header is not '100-continue'". web_app.py:382 calls it only when an `Expect` header is present, so the observed behaviour matches the docstring and is never reached normally.
Type: none
Confidence: low

### aiohttp-29
Oracle: tests/test_http_parser.py:2702/2738/2780 compare `msg.headers == HeadersDictProxy(...)`, which shows that two proxies are meant to compare equal. Delegating to `CIMultiDict.__eq__` breaks that as soon as a key repeats, and also breaks the `Mapping` equality contract.
Type: in-repo
Confidence: medium

### aiohttp-30
Oracle: Under RFC 9110 §12.5.3, `gzip;q=0` means gzip is not acceptable. A plain substring check (`file_encoding not in accept_encoding`) serves a coding the client refused.
Type: known-external
Confidence: high

### aiohttp-31
Oracle: On the first pass, `_update_headers` honours a caller-supplied Host (`headers.popall(hdrs.HOST, (host,))[0]`). That shows a custom Host is meant to be sent, but popping it from the shared dict drops it on the retry and same-origin redirect passes of the same loop.
Type: in-repo
Confidence: medium

### aiohttp-32
Oracle: The docstring says the property "un-escapes found escape sequences". That un-escaping happens upstream in `HeadersDictProxy.getall` (`_PROTECTED_RE`/`_QUOTED_PAIR_SUB`), and tests/test_web_request.py:814-818 shows escaped values coming out correctly. I can't point to a wrong output.
Type: none
Confidence: low

### aiohttp-33
Oracle: The comment in `__iter__` says "We need to deduplicate keys from MultiDict", and the mapping is case-insensitive: `p['X'] == p['x']`, both returning '1, 2'. Deduplicating case-sensitively breaks the `Mapping` invariants for `len`, iteration and `dict()`.
Type: in-repo
Confidence: medium

### aiohttp-34
Oracle: The error message in `__post_init__` says "Using 0 to disable timeouts is no longer supported, use None instead". The check runs after `max()` has already raised `total`, so `total=0` is quietly accepted whenever another timeout is set.
Type: in-repo
Confidence: medium

### aiohttp-35
Oracle: The top of `feed_data` (http_parser.py:999-1007) checks `_chunk_tail` against `max_line_size`, so the tail is meant to be bounded. The same bound isn't applied when the tail is stored, so the check only fires one call later. The extra memory is still bounded by one read.
Type: in-repo
Confidence: low

### aiohttp-36
Oracle: docs/streams.rst:95-97 defines only `None` as "uses the stream's high-water limit" and says nothing about 0. A zero limit has no useful meaning, so treating it as "default" is defensible.
Type: none
Confidence: low

### aiohttp-37
Oracle: `_prepare_headers` sets the local `keep_alive = False` for an HTTP/1.0 body of unknown length. That shows the connection is meant to close, which RFC 1945 requires to end such a body. `self._keep_alive` was assigned before the downgrade, so the server keeps the connection open and the client hangs.
Type: in-repo
Confidence: high

### aiohttp-38
Oracle: `binascii.Error` is raised when a chunk with fewer than 4 base64 characters is decoded on its own. The comment at multipart.py:423-426 argues this case is deliberate, which is why confidence is only medium.
Type: implicit
Confidence: medium

### aiohttp-39
Oracle: The docstring says the property "checks that every value has valid syntax ... either a 'token' or a 'quoted-string'" (RFC 7239 §4 / RFC 9110 §5.6.4). The greedy `".*"` runs past the closing quote and swallows the next pair. `_QDTEXT` is defined right above (web_request.py:131) but never used.
Type: in-repo
Confidence: high

### aiohttp-40
Oracle: The parent class `Domain.match_domain` (web_urldispatcher.py:807) does `host.lower() == self._domain`, and `Domain.validation` lower-cases the pattern. `MaskDomain.match_domain` doesn't lower-case the host. Host names are also case-insensitive under RFC 4343.
Type: in-repo
Confidence: high

### aiohttp-41
Oracle: Nothing requires the exception text to include the received value. This is a diagnostics preference.
Type: none
Confidence: low

### aiohttp-42
Oracle: The in-code comment `# TODO: Save and await this task.` (streams.py:539) admits the gap. The asyncio docs also say to keep a reference to tasks from `create_task` or they may be garbage-collected, and the callback's exception goes unretrieved.
Type: in-repo
Confidence: medium

### aiohttp-43
Oracle: RFC 6265 §5.2.2 says a Max-Age value that doesn't start with a digit or "-" should be ignored, and §5.3 step 3 then falls back to Expires. The `elif` skips Expires, so a cookie that has already expired gets stored.
Type: known-external
Confidence: high

### aiohttp-44
Oracle: This is a memory leak. Raising one shared exception instance again and again grows its `__traceback__` chain, which keeps every Request reachable.
Type: implicit
Confidence: high

### aiohttp-45
Oracle: `SEPARATORS` explicitly lists `chr(9)` (helpers.py:171), so TAB is meant to be excluded from `TOKEN`. But TAB is also in `CTL`, and the double XOR (`CHAR ^ CTL ^ SEPARATORS`) adds it back.
Type: in-repo
Confidence: high

### aiohttp-46
Oracle: `readuntil` raises an uncaught `AttributeError` on the `EMPTY_PAYLOAD` singleton. The in-code comment `# TODO add async def readuntil` (streams.py:666) acknowledges the missing override.
Type: implicit
Confidence: high

### aiohttp-47
Oracle: RFC 9112 §6.2 says a sender MUST NOT send Content-Length alongside Transfer-Encoding, and §6.1 requires chunked framing when chunked is declared. In the repo, `_update_transfer_encoding` refuses the `chunked=True` + Content-Length combination, which shows the same intent.
Type: known-external
Confidence: high

### aiohttp-48
Oracle: docs/web_reference.rst:3208-3210 defines keepalive_timeout as "a delay before a TCP connection is closed after a HTTP request". The observed behaviour matches that. Wanting a timeout for idle connections before the first request is a hardening wish I can't tie to anything in the checkout.
Type: none
Confidence: low

### aiohttp-49
Oracle: `chunked` is `bool | None`, and the rest of the class treats it as a truth value (`if self.chunked`, `elif self.chunked`). Only `_create_writer` uses `is not None`, so `chunked=False` turns chunking on. The resulting bytes break RFC 9112 framing: chunk framing under a Content-Length header.
Type: in-repo
Confidence: high

### aiohttp-50
Oracle: `zlib.error` is raised on the second chunk. `_decode_content_async` builds a new `ZLibDecompressor` on every call (multipart.py:627-632), so a stream split across chunks can't be decoded.
Type: implicit
Confidence: high

### aiohttp-51
Oracle: `_align_base64_chunk` (multipart.py:413) uses `self._length is not None`, which shows 0 is meant to count as a real length. The only visible effect is which error message you get on malformed input.
Type: in-repo
Confidence: low

### aiohttp-52
Oracle: Same pattern as 35: the top-of-call check against `_max_field_size` (http_parser.py:1003-1005) shows the trailer tail is meant to be bounded, but the check only runs one call later.
Type: in-repo
Confidence: low

### aiohttp-53
Oracle: `read_chunk` has `_align_base64_chunk`, with the comment that it exists because "every chunk is decoded on its own, so a chunk should not end mid-quartet". Quoted-printable has the same problem with `=XX` escapes and soft breaks, and gets no equivalent handling.
Type: in-repo
Confidence: high

### aiohttp-54
Oracle: The sibling `as_bytes(encoding, errors)` (multipart.py:1178) passes `encoding` and `errors` through to each part (`part.as_bytes(encoding, errors)`). `decode` drops them for the part bodies.
Type: in-repo
Confidence: medium

### aiohttp-55
Oracle: The constant is named `REUSE_ADDRESS` but is passed as `reuse_port=`, which suggests SO_REUSEADDR was intended. On POSIX, Python's `socket.create_server` already sets SO_REUSEADDR by default. Impact is limited to test servers on fixed ports.
Type: in-repo
Confidence: low

### aiohttp-56
Oracle: RFC 9112 §3.2.1 and §3.3 turn an empty path into "/" when the target is rebuilt in origin-form. The code's own comment says to handle it "exactly as an origin-form target", and an origin-form target always starts with "/".
Type: known-external
Confidence: medium

### aiohttp-57
Oracle: The docs (web_reference.rst:1051) describe `max_msg_size` as the "maximum size of read websocket message", so exactly 10 bytes should pass a limit of 10. The sibling decompressed-size check (reader_py.py:326) uses `len(...) > self._max_msg_size`.
Type: in-repo
Confidence: high

### aiohttp-58
Oracle: When a body is already consumed, `ClientSession._request` refuses to replay it: the redirect path raises `ClientPayloadError` "Cannot follow redirect with a consumed request body", and the retry path checks `req._body.consumed` (client.py:747-750, 797-803). The Digest retry does neither and sends an empty body under the original headers.
Type: in-repo
Confidence: high

### aiohttp-59
Oracle: The sibling `as_bytes` (multipart.py:1170-1187) adds `\r\n` after each part and a closing `--B--\r\n`, and so does `write`. `size` also counts those bytes. `decode` leaves them out.
Type: in-repo
Confidence: high

### aiohttp-60
Oracle: In Python a `bytes` never equals a `str`, so `!= "\r\n"` is always true and the check is dead. `_lines` holds bytes (for example `self._lines.append(self._tail)`), so the intended literal is `b"\r\n"`. I can't point to a wrong output that results.
Type: known-external
Confidence: medium

### aiohttp-61
Oracle: The class docstring documents `%%  The percent sign`. `CLEANUP_RE` turns the valid `%%` into `%%%`, so a documented format makes every log call fail.
Type: in-repo
Confidence: high

The hardest findings to classify were the ones around `HeadersDictProxy`: 27, 32, 29, 33 and 23. This checkout has a custom header proxy that splits lists in `getall`, and whether a behaviour is a defect depends on what the proxy is supposed to be. For 27 and 32 the upstream splitter and the tests suggest the reported pair-loop behaviour can't be reached or is handled elsewhere, so I called them "none", but that rests on reading intent from tests. 29 and 33 lean on `Mapping` invariants and a single comment. 35 and 52 were hard to rate for confidence: the code clearly means to bound the tail, but the check only comes one call late, and the extra memory is bounded by a single read. 38 and 36 are cases where the code comment or docs argue for the observed behaviour, so the "defect" is a judgement call. 13 and 20 sat between implicit and none: one is a crash on an undocumented format atom, the other a deliberate, capped cache that happens to hold credentials.
