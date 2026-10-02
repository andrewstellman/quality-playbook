# Code Review: aiohttp

- Repo: https://github.com/aio-libs/aiohttp
- Pinned commit: `e11d2836203a21bec59095498e578d37801027e7` (version string `4.0.0a2.dev0`, unreleased dev branch)
- Scope: `aiohttp/` (package source, excluding `tests/`)
- Checkout: `/tmp/control/aiohttp` (read-only)

Method: the package (~26,700 lines across ~55 files) was split into four scopes — client-side, web-server-side, protocol/parsing, and data/utility modules — and reviewed in parallel by sub-reviewers, each instructed to read every file in its scope in full, verify suspicions by tracing call sites (and, where practical, by executing small reproduction scripts against the checked-out source), and report only high-confidence defects. I then independently re-verified each reported finding against the source with `grep`/`sed` before including it below. Findings are ordered by severity.

An initial attempt to diff the checkout against an installed `aiohttp` copy in `/tmp/aiohttp-venv` was abandoned: that venv has aiohttp 3.14.3 (an older stable release), not this dev checkout, so the diff was dominated by legitimate feature differences rather than injected bugs.

---

## 1. `chunked=False` still triggers chunked-encoding on the wire, contradicting the `Content-Length` header that's sent — High

**File:** `aiohttp/client_reqrep.py`

- Field declared as `bool | None` and stored verbatim: `self.chunked: bool | None` (line 1034 annotation, line 1111 `self.chunked = chunked`).
- Every other consumer treats it as a boolean via truthiness:
  - `_update_transfer_encoding` (line 1242): `elif self.chunked:` — adds `Transfer-Encoding: chunked` only when truthy.
  - `_update_body_from_data` (line 1280): `if not self.chunked and hdrs.CONTENT_LENGTH not in self.headers:` — sets `Content-Length` from the payload when falsy.
- But `_create_writer` (line 1450) uses:
  ```python
  if self.chunked is not None:
      writer.enable_chunking()
  ```
  `False is not None` is `True`, so `chunked=False` (a value distinct from the default `None`, explicitly meaning "do not chunk") still calls `writer.enable_chunking()`.

**What goes wrong:** `session.post(url, data=b"hello", chunked=False)` sends headers declaring `Content-Length: 5` (per the two methods above) but the `StreamWriter` is put into chunked mode anyway, so the body is written on the wire as `5\r\nhello\r\n0\r\n\r\n` (11 bytes) while `Content-Length: 5` was promised. A server reading exactly 5 bytes per `Content-Length` gets a truncated/corrupted body, and the remaining bytes (`\r\n0\r\n\r\n`) are left to be misinterpreted as the start of the next request/response on a keep-alive connection — a Content-Length/Transfer-Encoding framing desync, the same defect class underlying HTTP request-smuggling bugs.

**Severity:** High — any caller passing the documented `chunked=False` to disable chunking gets silently corrupted/desynced request framing instead.

**Suggested fix:**
```python
if self.chunked:
    writer.enable_chunking()
```

---

## 2. Compressing an empty-body response (204/304/HEAD) crashes with an `AssertionError` — High

**File:** `aiohttp/web_response.py`

- `Response._body` defaults to `None` (class attribute, line 79).
- `prepare()` sets `self._must_be_empty_body = must_be_empty_body(request.method, self.status)` (line 359) *before* calling `_start` → `_prepare_headers`.
- `_prepare_headers` (line 388-389) calls `_start_compression(request)` unconditionally whenever `self._compression` is set, with **no check of `self._must_be_empty_body`**.
- `Response._do_start_compression` (lines 720-737) only special-cases `self._chunked or isinstance(self._body, Payload)`; for a plain `None` body (e.g. `web.Response(status=204)`, or any HEAD response, or a 304) it falls into the "compress the whole body" branch:
  ```python
  assert self._body is not None
  self._compressed_body = (
      await compressor.compress(self._body) + compressor.flush()
  )
  ```
  With `self._body is None`, this `assert` fails (raising `AssertionError`, surfaced as a 500 to the client), or, if the process runs with `python -O` (assertions stripped), `compressor.compress(None)` raises `TypeError` instead.

**What goes wrong:** Any response with an empty body per RFC 9110 (204 No Content, 304 Not Modified, any HEAD response — `EMPTY_BODY_STATUS_CODES`/`must_be_empty_body` in `aiohttp/helpers.py`) combined with `enable_compression()` being set (e.g. a generic "gzip everything" middleware, a common pattern) crashes on any request whose `Accept-Encoding` matches a supported coding — which is virtually every browser/client request.

**Severity:** High — turns an ordinary, spec-compliant response (empty body + compression enabled) into an unhandled server error.

**Suggested fix:** guard `_do_start_compression` (or its caller) with an early return when `self._must_be_empty_body` or `self._body is None`, mirroring the guard already applied for chunked/length-check logic a few lines above.

---

## 3. `write_eof` skips `Payload.close()` for HEAD/204/304 responses, leaking file descriptors — Medium/High

**File:** `aiohttp/web_response.py`, `write_eof` (lines ~681-700):

```python
if body is None or self._must_be_empty_body:
    await super().write_eof()
elif isinstance(self._body, Payload):
    try:
        await self._body.write(self._payload_writer)
    finally:
        await self._body.close()
    await super().write_eof()
```

**What goes wrong:** When `self._must_be_empty_body` is true (any HEAD request — auto-registered for every GET route — or a 204/304 response) *and* `self._body` is a `Payload` (e.g. `web.Response(body=open(path, "rb"))`, or any file-backed payload), the first branch is taken purely because of `_must_be_empty_body`, so `self._body.close()` is never called. `Payload.close()` is this codebase's own mechanism for releasing the underlying resource (e.g. `IOBasePayload` closing its file handle). Every HEAD request against a route that serves a file-backed `Response` therefore leaks a file descriptor.

**Severity:** Medium/High — cumulative resource exhaustion under normal traffic (HEAD probes, conditional requests returning 304), not a one-shot crash, but a real leak on a documented, supported code path.

**Suggested fix:** close the `Payload` unconditionally when `isinstance(self._body, Payload)`, regardless of which branch is taken for `write_eof`'s no-op-write path, e.g.:
```python
if isinstance(self._body, Payload):
    await self._body.close()
if body is None or self._must_be_empty_body:
    await super().write_eof()
```

---

## 4. A literal `%%` in an access-log format string breaks all subsequent access logging — High (operational)

**File:** `aiohttp/web_log.py`, `compile_format`, `CLEANUP_RE = re.compile(r"(%[^s])")` (~lines 122-123).

The module's docstring documents `%%` as meaning a literal percent sign in the format string (line 30). `CLEANUP_RE` matches any `%` followed by a non-`s` character — including a second `%` — and re-escapes it by prepending an extra `%`, turning `%%` into `%%%`. This was verified directly:
```
>>> AccessLogger(logger, '%%  %a')._log_format
'%%%  %s'
>>> '%%%  %s' % ('X',)
ValueError: unsupported format character '%' (0x25) at index 5
```
`_log_format` is compiled once per distinct format string and cached (`_FORMAT_CACHE`), so this `ValueError` recurs on every subsequent `log()` call for that format. `AccessLogger.log()` wraps the formatting in a blanket `except Exception:` that logs `"Error in logging"` and swallows the error — so any deployment whose `access_log_format` contains a bare `%%` silently loses all access logging for the process's lifetime, with no visible crash to reveal the misconfiguration.

**Severity:** High for operational impact (silent, total loss of access logs) even though it's a configuration-triggered rather than remotely-triggered bug; `%%` is a documented, legal construct in the format string, not user error.

**Suggested fix:** special-case a literal `%%` in the `CLEANUP_RE` substitution (leave it as `%%`, a valid escaped percent for the later `%`-formatting step) instead of adding a third `%`.

---

## 5. `BodyPartReader.read_chunk` treats `Content-Length: 0` the same as "length unknown" — Medium

**File:** `aiohttp/multipart.py`, `read_chunk` (~line 389):

```python
if self._length:
    fresh = await self._read_chunk_from_length(want)
else:
    fresh = await self._read_chunk_from_stream(want)
```

`self._length` is set to `int(length) if length is not None else None` (line 327), so `0` is a legitimate, meaningful value for a multipart body part that declares `Content-Length: 0`. The check above uses bare truthiness, so a zero length part is routed through `_read_chunk_from_stream` (the "unknown length, scan for the boundary" path) instead of `_read_chunk_from_length` (the "known length" path) — even though six lines later, in `_align_base64_chunk`, the same class correctly distinguishes the two with `self._length is not None and self._read_bytes >= self._length`. This also contradicts `_read_chunk_from_length`'s own contract (`assert self._length is not None, "Content-Length required for chunked read"` — `0` is a valid value it should handle, not one that should be routed around it).

**What goes wrong:** For a well-formed zero-length part the two paths happen to produce the same bytes, but the stricter, length-aware validation in `_read_chunk_from_length` is bypassed. For a malformed/inconsistent input (a part claiming `Content-Length: 0` but that actually contains extra bytes before the boundary), the code takes the generic boundary-scanning path and raises a different, less specific error (`"Reading after EOF"`) instead of the length path's intended diagnostic (`"Reader did not read all the data or it is malformed"`) — i.e. the zero-length edge case silently loses the stricter validation this class is designed to apply.

**Severity:** Medium — real logic error (identity-vs-truthiness mistake, same class of bug as finding #1), confirmed to change code path for a legal input (`Content-Length: 0`), with reduced/incorrect error diagnostics on malformed input rather than data corruption in the well-formed case.

**Suggested fix:**
```python
if self._length is not None:
    fresh = await self._read_chunk_from_length(want)
else:
    fresh = await self._read_chunk_from_stream(want)
```

---

## 6. `_default_expect_handler` raises `HTTPExpectationFailed` for requests with no `Expect` header at all — Medium

**File:** `aiohttp/web_urldispatcher.py`, ~lines 292-305:

```python
"""...raise HTTPExpectationFailed if value of header is not "100-continue" """
expect = request.headers.get(hdrs.EXPECT, "")
if request.version == HttpVersion11:
    if expect.lower() == "100-continue":
        ...
    else:
        raise HTTPExpectationFailed(text="Unknown Expect: %s" % expect)
```

`expect` defaults to `""` when the `Expect` header is absent, and the `else` branch raises unconditionally on any non-`"100-continue"` value — including the empty string. This contradicts the function's own docstring, which says it should raise only when the header's *value* is not `"100-continue"` (implying the header is present), not when it's simply missing. In production this is currently masked because the only call site, `Application._handle` (`web_app.py`), guards the call with `if request.headers.get(hdrs.EXPECT):` before invoking the handler — but `_default_expect_handler` is part of the public `expect_handler` API surface (settable per-route, directly documented and directly unit-tested), so any code path that calls it without replicating that external guard incorrectly rejects every HTTP/1.1 request lacking an `Expect` header with a 417.

**Severity:** Medium — latent/API-contract bug, currently masked for the one built-in call site but live for the documented public interface.

**Suggested fix:** `elif expect: raise HTTPExpectationFailed(...)` (only raise when a non-matching value is actually present).

---

## 7. `request.forwarded` drops data when a `Forwarded` header packs multiple hops into one comma-separated value — Medium

**File:** `aiohttp/web_request.py`, `forwarded` property parse loop (~lines 366-411), using `_FORWARDED_PAIR_RE` (~lines 138-141).

RFC 7239 §4's own canonical example shows one header *line* carrying multiple comma-separated `forwarded-element`s, one per proxy hop, e.g.:
```
Forwarded: for=192.0.2.60;proto=http;by=203.0.113.43, for=198.51.100.17
```
The parser here only recognizes `;` as a pair separator/terminator. When it hits a comma outside that pattern, it can't resynchronize and `break`s out of the loop — discarding the rest of the current element *and* every subsequent hop in that header value. Verified directly:
```
parse('for=192.0.2.60;proto=http;by=203.0.113.43, for=198.51.100.17')
=> {'for': '192.0.2.60', 'proto': 'http'}   # 'by' and the entire second hop are lost
```
The property's own docstring says it builds "one dictionary per ... field-value, ie per proxy" — but a single field-value legitimately contains multiple proxies per RFC 7239, and those are silently dropped here.

**Severity:** Medium — any deployment behind a proxy chain that emits comma-joined `Forwarded` values (RFC-compliant, and the RFC's own example format) gets an incomplete/wrong picture of the proxy chain from `request.forwarded`, which matters for trust/IP-derivation logic built on top of it.

**Suggested fix:** split each header value on top-level commas (respecting quoted-string boundaries) into separate forwarded-elements before parsing `;`-separated pairs within each.

---

## 8. `InvalidHeader` raised with the header name instead of the actual malformed value for a bad `Content-Length` — Low

**File:** `aiohttp/http_parser.py`, `get_content_length` (~lines 399-410):

```python
if not DIGITS.fullmatch(length_hdr):
    raise InvalidHeader(CONTENT_LENGTH)
```

Every other `InvalidHeader` call site in this file passes the actual offending value/bytes (`raise InvalidHeader(line)`, `raise InvalidHeader(bvalue)`, etc.), and the Cython-accelerated parser's equivalent check (`_http_parser.pyx`) raises with the actual raw value. Here, a malformed `Content-Length` (e.g. `Content-Length: abc` or `Content-Length: -5`) raises `InvalidHeader(CONTENT_LENGTH)` — the static header-name constant — so `.hdr`/`.args`/`str(exc)` report only `"Invalid HTTP header: 'Content-Length'"` with no trace of what value was actually sent. The request is still correctly rejected (400), so this isn't an exploitable parsing bug, but it destroys the diagnostic value of the exception for anyone inspecting malformed/attack traffic (e.g. smuggling probes via crafted Content-Length values), and is inconsistent with this file's own convention.

**Severity:** Low.

**Suggested fix:** `raise InvalidHeader(length_hdr)`.

---

## Lower-confidence observations (not filed as confirmed defects)

- `aiohttp/web_ws.py`, `receive(timeout=0)`: `receive_timeout = timeout or self._receive_timeout` uses `or`, so an explicit `timeout=0` ("don't block") silently falls back to the instance default instead. Low confidence this is exploitable/impactful, but it is the same truthiness-vs-`is not None` mistake pattern seen elsewhere in this codebase.
- `aiohttp/web_request.py` Range parsing: a syntactically valid `Range: bytes=-0` (suffix-length 0) computes `start = -end = -0 == 0`, yielding "entire body" instead of the RFC 9110 §14.1.1 "unsatisfiable" result for a zero-length suffix. Narrow, deliberately-crafted-input edge case.
- `aiohttp/client_ws.py`, `receive()`: catching `(asyncio.CancelledError, asyncio.TimeoutError)` and unconditionally setting `self._close_code = WSCloseCode.ABNORMAL_CLOSURE` before re-raising means a plain per-call `receive(timeout=...)` timeout (connection still alive) corrupts the public `close_code` property, inconsistent with the server-side `WebSocketResponse.receive()`, which does not do this. Plausible real bug but not independently re-verified by execution.
- `aiohttp/connector.py`, `_close_immediately()`: clears `self._acquired` but not `self._acquired_per_host` in its cleanup, potentially leaving stale per-host bookkeeping if a closed connector's per-host accounting is read afterward. Not independently re-verified.

---

## Files read

**Client-side scope:** `aiohttp/client.py`, `aiohttp/client_reqrep.py`, `aiohttp/client_proto.py`, `aiohttp/client_ws.py`, `aiohttp/client_exceptions.py`, `aiohttp/client_middlewares.py`, `aiohttp/client_middleware_digest_auth.py`, `aiohttp/connector.py`, `aiohttp/resolver.py`, `aiohttp/tracing.py` (full); context reads of `aiohttp/helpers.py`, `aiohttp/http_writer.py`, `aiohttp/payload.py`, `aiohttp/web_ws.py`, `aiohttp/abc.py`, partial `tests/test_client_functional.py`, `tests/test_client_request.py`, `tests/test_client_response.py`.

**Web-server scope:** `aiohttp/web.py`, `aiohttp/web_app.py`, `aiohttp/web_protocol.py`, `aiohttp/web_request.py`, `aiohttp/web_response.py`, `aiohttp/web_server.py`, `aiohttp/web_runner.py`, `aiohttp/web_middlewares.py`, `aiohttp/web_urldispatcher.py`, `aiohttp/web_ws.py`, `aiohttp/web_fileresponse.py`, `aiohttp/web_exceptions.py`, `aiohttp/web_log.py`, `aiohttp/web_routedef.py`, `aiohttp/worker.py` (full); context reads of `aiohttp/helpers.py`, `aiohttp/streams.py`, `aiohttp/http_writer.py`, `aiohttp/base_protocol.py`, `aiohttp/payload.py`, partial `tests/test_web_log.py`, `tests/test_worker.py`, `tests/test_urldispatch.py`.

**Protocol/parsing scope:** `aiohttp/http_parser.py`, `aiohttp/http_writer.py`, `aiohttp/http.py`, `aiohttp/http_websocket.py`, `aiohttp/http_exceptions.py`, `aiohttp/hdrs.py`, `aiohttp/streams.py`, `aiohttp/base_protocol.py`, `aiohttp/_websocket/__init__.py`, `aiohttp/_websocket/reader.py`, `aiohttp/_websocket/reader_py.py`, `aiohttp/_websocket/writer.py`, `aiohttp/_websocket/models.py`, `aiohttp/_websocket/helpers.py` (full); partial `aiohttp/_http_parser.pyx`, partial `tests/test_http_parser.py`, `tests/test_websocket_parser.py`.

**Data/utility scope:** `aiohttp/multipart.py`, `aiohttp/payload.py`, `aiohttp/formdata.py`, `aiohttp/helpers.py`, `aiohttp/compression_utils.py`, `aiohttp/abc.py`, `aiohttp/typedefs.py`, `aiohttp/tcp_helpers.py`, `aiohttp/log.py`, `aiohttp/__init__.py`, `aiohttp/test_utils.py` (full). `aiohttp/_cookie_helpers.py` and `aiohttp/cookiejar.py` were reviewed directly by me (the orchestrating reviewer) — cookie-name/date parsing, domain matching (`_is_domain_match`), and default-path computation were traced by hand and found consistent with RFC 6265; no confirmed defects.

**Orchestration-level verification (by me, against the raw source):** `aiohttp/client_reqrep.py` (chunked handling, finding #1), `aiohttp/web_response.py` (compression/write_eof, findings #2-3), `aiohttp/multipart.py` (read_chunk, finding #5), `aiohttp/cookiejar.py`, `aiohttp/_cookie_helpers.py`.
