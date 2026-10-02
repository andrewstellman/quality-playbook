# Code review: aiohttp @ e11d2836203a21bec59095498e578d37801027e7

Scope: `aiohttp/` package (tests excluded). Reviewer: Sonnet (Claude).

Method: split the package into four regions (client/connector, web server, HTTP/websocket parsing, helpers/cookies) and had a sub-reviewer read each region end-to-end and diff it against upstream `aio-libs/aiohttp` master to separate injected regressions from pre-existing issues. Every defect below was then independently re-verified by me against the actual checkout: either executed directly (pure-Python import, no C extensions needed) or confirmed by re-reading the cited lines and tracing the control flow by hand. One sub-reviewer's claimed defect (a base64-multipart parsing bug) did not reproduce under a corrected test harness and is recorded at the bottom as disproven rather than reported as a finding.

---

## 1. Idle connections that never send a complete request are never closed (Slowloris-style resource exhaustion)

- **File/line:** `aiohttp/web_protocol.py:243` (`self._keepalive = False` in `__init__`) and `aiohttp/web_protocol.py:393-411` (`connection_made`), together with the wait loop at `aiohttp/web_protocol.py:727-731` (`start()`: `if not self._messages: self._waiter = loop.create_future(); await self._waiter`).
- **What goes wrong:** `RequestHandler.__init__` sets `self._keepalive = False`, and `connection_made()` does not arm any deadline. The only place a keepalive deadline (`self._keepalive_handle = loop.call_at(...)`) is scheduled is at the bottom of the request-handling loop in `start()` (lines 854-860), which runs only *after* a full request/response cycle has completed. `_process_keepalive()` (the sole code path that force-closes an idle connection, line 649-651) bails out immediately when `self._keepalive` is falsy: `if self._force_close or not self._keepalive: return`. Meanwhile, while `self._messages` is empty, `start()` awaits `self._waiter` with **no timeout at all**.
  - Consequence: a client that opens a TCP connection and sends nothing (or sends a partial request line/headers and then stalls) is never subject to `keepalive_timeout`. The connection, its `RequestHandler`, its parser and buffers sit alive indefinitely. Nothing in `web_protocol.py` bounds this wait — I grepped every use of `timeout`/`ceil_timeout` in the file (lines 143, 162-163, 210, 222, 273-275, 340-341, 343, 361, 373, 722, 816, 856) and the only timeouts guard *shutdown* and the *lingering close* of an already-completed request's payload, not the wait for the first byte of a new request.
- **Why it is wrong:** The class docstring for `RequestHandler` documents `keepalive_timeout -- number of seconds before closing [a] ... connection` without qualifying it to "after the first successful request." A server that advertises a keepalive timeout but never enforces any timeout on a connection that hasn't yet sent a request violates that contract and gives an unauthenticated client a way to pin one handler task/parser/transport per open-but-idle socket forever, simply by connecting and staying silent.
- **Severity:** high — unauthenticated, trivially repeatable connection/resource-exhaustion vector with no available server-side mitigation (increasing `keepalive_timeout` doesn't help; it's never armed for this case).
- **Fix:** Arm a keepalive-style deadline in `connection_made()` before the first request is received (i.e., initialize `self._keepalive = True` and schedule `self._keepalive_handle` at `connection_made` time), so `_process_keepalive()` can close a connection that never delivers a complete first request. (Verified this is exactly how upstream `aio-libs/aiohttp` master handles it — `connection_made()` there arms the deadline unconditionally.)

---

## 2. `CookieJar`: an invalid `Max-Age` suppresses a valid `Expires` fallback, so cookies that should already be expired persist forever

- **File/line:** `aiohttp/cookiejar.py:396-416` (`_update_cookies`)
```python
if max_age := cookie["max-age"]:
    try:
        delta_seconds = int(max_age)
        ...
        self._expire_cookie(max_age_expiration, domain, path, name)
    except ValueError:
        cookie["max-age"] = ""
elif expires := cookie["expires"]:
    ...
```
- **What goes wrong:** The `elif` is gated on the truthiness of the raw `Max-Age` *string*, not on whether it parsed successfully. `Set-Cookie: sid=abc; Max-Age=notanumber; Expires=Wed, 09 Jun 2001 10:18:14 GMT` takes the `if` branch (since `"notanumber"` is truthy), `int()` raises `ValueError`, the `except` clears `cookie["max-age"]` — but the `elif` never runs, so the (already-expired) `Expires` value is never consulted and `_expire_cookie()` is never called.
  - Reproduced directly:
    ```
    jar.update_cookies_from_headers(["sid=abc; Max-Age=notanumber; Expires=Wed, 09 Jun 2001 10:18:14 GMT"], URL("http://example.com/"))
    jar._expirations == {}
    jar.filter_cookies(URL("http://example.com/")) -> "Set-Cookie: sid=abc"
    ```
    A cookie whose `Expires` is nine years in the past is treated as a non-expiring session cookie.
- **Why it is wrong:** RFC 6265 §5.2.2 says an invalid `Max-Age` attribute-value must simply be ignored, which per the algorithm in §5.3 lets `Expires` (§5.2.1) govern expiry as if `Max-Age` had never been present. The class's own docstring says `"""Implements cookie storage adhering to RFC 6265."""`.
- **Severity:** medium — any server/proxy/CDN that emits a non-numeric or garbled `Max-Age` alongside a valid `Expires` causes that cookie to silently outlive its intended lifetime indefinitely, which is a correctness/spec violation with real interoperability consequences (stale session/auth cookies never expiring client-side).
- **Fix:** Decouple the two checks so `Expires` is still consulted when `Max-Age` parsing fails, e.g.:
```python
max_age = cookie["max-age"]
if max_age:
    try:
        ...
        self._expire_cookie(max_age_expiration, domain, path, name)
    except ValueError:
        cookie["max-age"] = ""
        max_age = ""
if not max_age and (expires := cookie["expires"]):
    if expire_time := self._parse_date(expires):
        self._expire_cookie(expire_time, domain, path, name)
    else:
        cookie["expires"] = ""
```

---

## 3. `CookieJar`: a non-lower-case `Domain` attribute causes the cookie to be silently dropped

- **File/line:** `aiohttp/cookiejar.py:360-374` (`_update_cookies`), `_is_domain_match` at `aiohttp/cookiejar.py:531-545`.
```python
domain = cookie["domain"]
...
if domain and domain[0] == ".":
    domain = domain[1:]
    cookie["domain"] = domain

if domain and hostname and not self._is_domain_match(domain, hostname):
    # Setting cookies for different domains is not allowed
    continue
```
- **What goes wrong:** `hostname` (from `response_url.raw_host`) is always lower-case, but `domain` (taken verbatim from the `Domain` attribute) is never canonicalized to lower case. `_is_domain_match` does a case-sensitive `hostname.endswith(domain)`, so `Set-Cookie: foo=bar; Domain=EXAMPLE.COM` served from `http://example.com/` fails the match and the cookie is discarded via `continue`.
  - Reproduced directly:
    ```
    jar.update_cookies_from_headers(["foo=bar; Domain=EXAMPLE.COM"], URL("http://example.com/"))
    jar.filter_cookies(URL("http://example.com/")) -> "" (nothing stored)
    ```
- **Why it is wrong:** RFC 6265 §5.2.3 requires the domain-attribute to be "converted to lower case" during canonicalization, and §5.1.3's domain-match algorithm explicitly assumes both strings are already lower-cased. This is the same class that documents RFC 6265 adherence.
- **Severity:** medium — any server that emits a mixed-/upper-case `Domain` value (not unusual; case is not meaningful in DNS names, so nothing stops a server from doing this) has its cookie unconditionally and silently dropped.
- **Fix:** `domain = cookie["domain"].lower()` immediately when read, and write the lower-cased value back to `cookie["domain"]`.

---

## 4. Per-request `cookies=` argument does not honor `treat_as_secure_origin`, unlike session-level cookies

- **File/line:** `aiohttp/client.py:646-656` (`ClientSession._request`)
```python
all_cookies = self._cookie_jar.filter_cookies(url)

if cookies is not None:
    tmp_cookie_jar = CookieJar(
        unsafe=self._cookie_jar.unsafe,
        quote_cookie=self._cookie_jar.quote_cookie,
    )
    tmp_cookie_jar.update_cookies(cookies)
    req_cookies = tmp_cookie_jar.filter_cookies(url)
```
- **What goes wrong:** `CookieJar.__init__` (`aiohttp/cookiejar.py:87-111`) accepts a `treat_as_secure_origin` constructor argument that relaxes the "don't send Secure cookies over plaintext" rule for specific origins (e.g. `http://localhost` in local dev). `filter_cookies()` (`aiohttp/cookiejar.py:449-453`) consults `self._treat_as_secure_origin` when deciding whether to drop a `Secure` cookie for a non-HTTPS request. `_request()` builds a temporary jar to filter the request-scoped `cookies=` kwarg and copies `unsafe` and `quote_cookie` from the session's jar (both of which have public properties, `aiohttp/cookiejar.py:117-122`), but there is no public accessor for `treat_as_secure_origin` at all, so the temp jar always defaults to an empty frozenset. A `Secure`-flagged cookie passed via the per-request `cookies=` argument to a session whose jar was configured with `treat_as_secure_origin=["http://localhost"]` is silently dropped for that same trusted-but-plaintext origin, even though a cookie already stored in the session jar for the same URL would have been sent.
- **Why it is wrong:** This produces two different outcomes for the same request/origin depending only on which of the two supported cookie-input paths (session jar vs. per-request `cookies=`) supplied the cookie — an inconsistency with no way for a caller to work around it (there's no way to make the temp jar aware of the override).
- **Severity:** low/medium — not a security weakening (the behavior is *more* restrictive, not less), but a real, silently inconsistent behavior for a documented feature.
- **Fix:** Add a public `treat_as_secure_origin` property to `CookieJar` (mirroring `unsafe`/`quote_cookie`) and pass it through when constructing `tmp_cookie_jar`.

---

## 5. `StreamResponse.write_eof()` never closes a `Payload` body when the response must have an empty body (file-descriptor leak)

- **File/line:** `aiohttp/web_response.py:690-698`
```python
if body is None or self._must_be_empty_body:
    await super().write_eof()
elif isinstance(self._body, Payload):
    try:
        await self._body.write(self._payload_writer)
    finally:
        await self._body.close()
    await super().write_eof()
else:
    await super().write_eof(cast(bytes, body))
```
- **What goes wrong:** When `self._must_be_empty_body` is true (set in `prepare()` from `must_be_empty_body(request.method, self.status)` — e.g. a `HEAD` request, or a `204`/`304` response), the *first* branch is taken unconditionally, even if `self._body` is a `Payload` (e.g. `IOBasePayload`/`FilePayload` wrapping an open file). The `elif isinstance(self._body, Payload)` branch — the only place `Payload.close()` is ever invoked — is unreachable in that case. `IOBasePayload.close()` (`aiohttp/payload.py:687-693`) closes the underlying file object via an executor; skipping it leaves the file descriptor open.
- **Why it is wrong:** Any handler that does `web.Response(body=FilePayload(...))` (or similar) and is invoked with `HEAD`, or returns `204`/`304`, leaks the underlying file handle on every such response, since the code path that's supposed to close the payload can't run for exactly this combination.
- **Severity:** medium — a genuine resource leak on an easily reachable, non-exceptional path (any `HEAD` request against a payload-backed response).
- **Fix:**
```python
if body is None:
    await super().write_eof()
elif self._must_be_empty_body:
    if isinstance(self._body, Payload):
        await self._body.close()
    await super().write_eof()
elif isinstance(self._body, Payload):
    ...
```

---

## 6. `BaseRequest.post()`: a multipart field that trips the size/field-count limit leaks the temp files of previously-read file fields

- **File/line:** `aiohttp/web_request.py:809-865` (the `while (field := await multipart.next())` loop in `post()`)
- **What goes wrong:** For each iteration, the top-of-loop checks
```python
if 0 < max_size < payload.total_bytes:
    raise HTTPRequestEntityTooLarge(max_size)
if 0 < max_fields <= len(out):
    raise _too_many_fields(max_fields)
```
run *before* processing the current field, using state accumulated from all previously-processed fields. If an earlier file-type field was already spooled to a `SpooledTemporaryFile` and added to `out` as a `FileField`, and a *later* field then trips either check, the exception propagates out of `post()` with no cleanup of the `FileField.file` objects already sitting in `out`. `self._post` is only assigned after the loop completes successfully, so `BaseRequest._finish()` — the only code that closes previously-created `FileField.file` handles — never runs for this request; the open temp files are only reclaimed via GC finalization, not deterministically.
  - (Compare: the *inner* per-field size check, a few lines further down at the `while chunk := await field.read_chunk(...)` loop, does correctly `tmp.close()`/`run_in_executor(None, tmp.close)` for the field currently being read when it individually exceeds the limit — the cleanup gap is specifically for fields collected in *prior* iterations, not the one being read when the limit trips.)
- **Why it is wrong:** Nothing in `post()`'s docstring or the size-limiting code suggests earlier successfully-parsed fields should leak their temp files just because a later field or the field count trips a limit; the intent of the two guards is clearly to bound resource usage, which is undermined if hitting them itself leaks resources.
- **Severity:** low/medium — real fd/tmp-file leak on a client-reachable error path (an oversized or too-numerous multipart upload), though the leak is bounded by GC and not immediately fd-exhausting under light load.
- **Fix:** Wrap the loop body in `try/except`, closing any `FileField.file` already added to `out` (via `run_in_executor` for the ones that rolled to disk) before re-raising `HTTPRequestEntityTooLarge`/`_too_many_fields`.

---

## 7. `Range: bytes=-0` is misparsed as "the entire body" instead of an unsatisfiable range

- **File/line:** `aiohttp/web_request.py:679-685` (`http_range`), consumed by the range logic in `aiohttp/web_fileresponse.py`.
```python
end = int(end) if end else None
start = int(start) if start else None

if start is None and end is not None:
    # end with no start is to return tail of content
    start = -end
    end = None
```
- **What goes wrong:** For `Range: bytes=-0`, the regex captures `start=""`, `end="0"`. `end = int(end) if end else None` treats the non-empty string `"0"` as truthy, so `end` becomes the integer `0` (not `None`). Then, because `start is None and end is not None` (0 is not None), the suffix-range substitution fires: `start = -end == 0`, `end = None`, producing `slice(0, None, 1)` — i.e., "the whole body from byte 0" is returned with `206 Partial Content`.
- **Why it is wrong:** RFC 9110 §14.1.2 defines `suffix-length` semantics such that a suffix-length of 0 selects zero bytes; a range request with no bytes it can satisfy is supposed to be answered `416 Range Not Satisfiable`, not the entire representation with a `206` status.
- **Severity:** low — narrow edge case, no security impact, but a clear, reproducible spec violation (confirmed by tracing the arithmetic by hand; this same bug is independently present upstream, not introduced by this checkout).
- **Fix:** Treat `end == 0` in the suffix-range branch as unsatisfiable (raise the `ValueError` that already drives the existing 416 path in `web_fileresponse.py`) instead of substituting `start = -0`.

---

## 8. Compression negotiation ignores `q=0` (and all qvalues) in `Accept-Encoding`

- **File/line:** `aiohttp/web_response.py:342-352` (`_start_compression`)
```python
accept_encoding = request.headers.get(hdrs.ACCEPT_ENCODING, "").lower()
for value, coding in CONTENT_CODINGS.items():
    if value in accept_encoding:
        await self._do_start_compression(coding)
        return
```
- **What goes wrong:** This does a plain substring test against the raw header value, with no qvalue parsing at all. `Accept-Encoding: gzip;q=0` (explicitly forbidding gzip) still matches `"gzip" in "gzip;q=0"` and is treated as acceptable, so the server compresses the response with an encoding the client said it will not accept.
- **Why it is wrong:** RFC 9110 §12.5.3 specifies that a codings value with `q=0` (or an explicit `identity;q=0`/`*;q=0` with no other match) means that coding is not acceptable. Ignoring qvalues can produce a response the client is contractually allowed to reject/mishandle.
- **Severity:** low — negotiation correctness issue rather than a crash/security bug, and it is a long-standing behavior (also present upstream), but it is a genuine, traceable contradiction of the RFC the header implements.
- **Fix:** Parse `Accept-Encoding` properly (split on commas, parse `;q=` parameters) instead of substring-matching the raw string.

---

## 9. `forwarded` docstring claims escape-sequence un-escaping that the code does not perform

- **File/line:** `aiohttp/web_request.py:366-396` (`BaseRequest.forwarded`)
- **What goes wrong:** The docstring states: *"It un-escapes found escape sequences."* The actual handling is only:
```python
if value[0] == value[-1] == '"':
    value = value[1:-1]
```
which strips a pair of surrounding quotes but does not process backslash escape sequences (`\"`, `\\`) that RFC 7239's `quoted-string` grammar (via RFC 7230 `quoted-pair`) permits inside the value, e.g. `Forwarded: for="a\"b"` yields `a\"b` verbatim rather than the RFC-mandated unescaped `a"b`.
- **Why it is wrong:** The code's own docstring, which describes RFC 7239 conformance ("Makes an effort to parse Forwarded headers as specified by RFC 7239"), explicitly claims a behavior ("un-escapes found escape sequences") the implementation does not provide, so a caller relying on that documented guarantee gets a value with a literal backslash left in it.
- **Severity:** low — narrow, and downstream consumers rarely construct headers with embedded escapes, but it's a direct behavior/documentation mismatch in security-adjacent code (`forwarded` is commonly used to determine client IP/host/proto for access control or logging).
- **Fix:** Either implement quoted-pair unescaping (`re.sub(r'\\(.)', r'\1', value)` after stripping the surrounding quotes) or correct the docstring to state that surrounding quotes are stripped but embedded escapes are left as-is.

---

## Investigated and disproven (recorded for completeness)

A first-pass sub-reviewer reported a "high severity" defect in `aiohttp/multipart.py` (`BodyPartReader.read_chunk`/`_read_chunk_from_stream`/`_align_base64_chunk`), claiming that any `multipart/form-data` part with `Content-Transfer-Encoding: base64` and no `Content-Length` always fails with a spurious `ValueError("Reading after EOF")`. I built a live reproduction against the actual checkout (pure-Python import, no C extensions) using the same construction the sub-reviewer described, and did initially observe the exception — but the reproduction used a `BodyPartReader` boundary argument of `b"boundary123"` instead of the correctly-formatted `b"--boundary123"` (a `MultipartReader` always constructs the boundary with the `--` prefix, `aiohttp/multipart.py:743`). With the boundary corrected, base64-encoded parts decode correctly across a range of payload sizes (1–5000 bytes) and chunk sizes (15–8192 bytes, including sizes that force the base64 carry-over logic to engage on every call), with the decoded output always matching the original payload byte-for-byte. This was a test-harness bug in the sub-reviewer's reproduction, not a defect in aiohttp; it is not included as a finding above.

## Files read

`aiohttp/web_protocol.py`, `aiohttp/web_request.py`, `aiohttp/web_response.py`, `aiohttp/web_fileresponse.py`, `aiohttp/cookiejar.py`, `aiohttp/client.py`, `aiohttp/payload.py`, `aiohttp/multipart.py`, `aiohttp/streams.py`, `aiohttp/base_protocol.py`, `aiohttp/abc.py`, `aiohttp/helpers.py`, plus (via delegated sub-review, subsequently spot-verified against the checkout by me) `client_reqrep.py`, `client_proto.py`, `client_ws.py`, `client_exceptions.py`, `client_middlewares.py`, `client_middleware_digest_auth.py`, `connector.py`, `resolver.py`, `tcp_helpers.py`, `web.py`, `web_app.py`, `web_exceptions.py`, `web_middlewares.py`, `web_routedef.py`, `web_runner.py`, `web_server.py`, `web_urldispatcher.py`, `web_ws.py`, `web_log.py`, `worker.py`, `http_parser.py`, `http_writer.py`, `http_websocket.py`, `http_exceptions.py`, `http.py`, `_websocket/__init__.py`, `_websocket/helpers.py`, `_websocket/models.py`, `_websocket/reader.py`, `_websocket/reader_py.py`, `_websocket/writer.py`, `formdata.py`, `compression_utils.py`, `_cookie_helpers.py`, `tracing.py`, `hdrs.py`, `typedefs.py`, `__init__.py`, `log.py`. No confident, independently-triggerable defects were found in the client/connector region, the HTTP/websocket parser region beyond the disproven multipart item above, or the remaining web-server files not covered by findings 1, 5, 6, 7, 8 above.
