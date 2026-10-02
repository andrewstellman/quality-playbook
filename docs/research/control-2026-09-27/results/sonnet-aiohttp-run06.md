# Code review: aiohttp

**Repo:** aiohttp (https://github.com/aio-libs/aiohttp)
**Pinned commit:** `e11d2836203a21bec59095498e578d37801027e7`
**Scope:** `aiohttp/` (package source, excluding tests)

All findings below were independently confirmed by direct reading of the pinned checkout (line numbers and quoted code taken from the actual files at that commit).

---

## 1. Idle connections that never complete a first request are never closed by `keepalive_timeout`

**File:** `aiohttp/web_protocol.py`, lines 243 (`RequestHandler.__init__`) and 393–413 (`RequestHandler.connection_made`)

**What goes wrong:** `RequestHandler` starts with:

```python
self._request_count = 0
self._keepalive = False
```

and `connection_made()` does not arm `self._keepalive_handle` at all:

```python
def connection_made(self, transport: asyncio.BaseTransport) -> None:
    super().connection_made(transport)
    real_transport = cast(asyncio.Transport, transport)
    if self._tcp_keepalive:
        tcp_keepalive(real_transport)
    assert self._manager is not None
    self._manager.connection_made(self, real_transport)
    loop = self._loop
    if sys.version_info >= (3, 14):
        ...
    self._task_handler = task
```

`grep` for `_keepalive_handle` in this file confirms it is assigned in exactly one other place, inside the `start()` loop, and only *after* a response has been sent for a completed request:

```python
if self._keepalive and not self._close and not self._force_close:
    # start keep-alive timer
    close_time = loop.time() + keepalive_timeout
    self._next_keepalive_close_time = close_time
    if self._keepalive_handle is None:
        self._keepalive_handle = loop.call_at(close_time, self._process_keepalive)
```

`_process_keepalive()` itself is a no-op unless `self._keepalive` is already `True`:

```python
def _process_keepalive(self) -> None:
    self._keepalive_handle = None
    if self._force_close or not self._keepalive:
        return
    ...
```

Because `_keepalive` starts `False` and nothing schedules `_process_keepalive` before a request completes, there is no timer at all protecting the window between TCP connection establishment and the first complete request. A client that opens a connection and then sends nothing (or a slow/partial request line — classic Slowloris) will have that connection held open indefinitely, bounded only by OS-level TCP timeouts, not by `keepalive_timeout`.

**Why it's wrong:** The class docstring documents the parameter as an unconditional promise:

```
keepalive_timeout -- number of seconds before closing keep-alive connection
```

(`web_protocol.py` line 143). The default value is 3630 seconds (about an hour) — a connection that never sends a complete request is expected to be reaped after that time, not held open forever. Nothing else in the file provides equivalent protection for a connection that never delivers a first request: the only other places that close idle connections (`_process_keepalive`, the post-response keepalive arm in `start()`) are gated on a request having already completed.

**Trigger scenario:** Open a raw TCP connection to an aiohttp web server and send nothing (or an incomplete request line), then hold the socket open. The connection stays alive with no timeout enforced by aiohttp, regardless of `keepalive_timeout`. Many such idle connections (Slowloris-style) accumulate unbounded, exhausting file descriptors / memory on the server.

**Severity:** High (silent availability/DoS issue — no error is raised or logged; the connection is simply never reaped by the mechanism that is documented to reap it).

**Suggested fix:** Initialize `self._keepalive = True` in `__init__`, and in `connection_made()`, arm the keepalive timer immediately (mirroring the pattern already used after each completed request):

```python
if self._keepalive_timeout > 0:
    close_time = loop.time() + self._keepalive_timeout
    self._next_keepalive_close_time = close_time
    self._keepalive_handle = loop.call_at(close_time, self._process_keepalive)
```

---

## 2. Digest-auth retry silently sends a truncated/empty body for non-replayable streaming request bodies

**File:** `aiohttp/client_middleware_digest_auth.py`, `DigestAuthMiddleware.__call__`, lines 473–503 (retry loop), together with `aiohttp/payload.py`, `AsyncIterablePayload.write_with_length` / `as_bytes`, lines 1013–1103.

**What goes wrong:** On a 401 digest challenge, the middleware resends the *same* `ClientRequest` object a second time:

```python
response = None
for retry_count in range(2):
    if retry_count > 0 or (
        self._preemptive
        and self._challenge
        and self._in_protection_space(request.url)
    ):
        request.headers[hdrs.AUTHORIZATION] = await self._encode(
            request.method, request.url, request.body
        )
    response = await handler(request)
    if not self._authenticate(response):
        break
```

For a request body backed by `AsyncIterablePayload` (or `StreamReaderPayload`, e.g. an async generator or a `StreamReader`) and `qop=auth` (not `auth-int`), `_encode()` never calls `body.as_bytes()` — that only happens for `qop == "auth-int"` (`client_middleware_digest_auth.py` lines 310–312). So nothing caches the body before the second send.

`handler(request)` eventually calls `Payload.write_with_length()` to write the body. On the **first** (unauthenticated) send, `write_with_length` drains the async iterator and, since nothing cached it, marks it consumed and exhausted:

```python
# If iterator is exhausted and we don't have cached chunks, nothing to write
if self._iter is None:
    return
...
# Nothing is cached, so advancing the iterator is irreversible: mark the
# payload consumed up front so an interrupted write cannot be replayed
# from a partially drained iterator.
self._consumed = True
try:
    while True:
        chunk = await anext(self._iter)
        ...
except StopAsyncIteration:
    self._iter = None
```

On the **second** (authenticated) send, `write_with_length` is called again on the same payload object. `self._cached_chunks` is still `None` (only `as_bytes()` populates it, and that wasn't called), and `self._iter` is now `None` from the first drain, so the function hits the early return and writes **nothing** — while the request's `Content-Length`/transfer-encoding headers still reflect the original body. The server receives a truncated or empty body with no exception raised on the client side.

**Why it's wrong:** This is the exact "resend a non-replayable body" hazard the codebase elsewhere raises a loud error for. `client.py`'s redirect-following logic explicitly guards against it:

```python
if req._body.consumed:
    resp.close()
    raise ClientPayloadError(
        "Cannot follow redirect with a consumed request "
        "body. Use bytes, a seekable file-like object, "
        "or set allow_redirects=False."
    )
```

The digest-auth middleware performs the same kind of "resend the request" operation (a second `handler(request)` call with the same body object) but has no analogous check, so instead of failing loudly it silently ships a truncated/empty body — data corruption instead of an error.

**Trigger scenario:** `ClientSession` with `DigestAuthMiddleware`, no preemptive auth (or no cached challenge yet), `POST`/`PUT` with an async-generator or `StreamReader`-backed body, against a server requiring digest auth with `qop=auth` (not `auth-int`). The first (401) attempt drains the body; the retried, authenticated attempt sends no body bytes even though `Content-Length` was computed from the real content.

**Severity:** Medium-high. The trigger requires a specific combination (streaming/one-shot body type + digest auth + `qop=auth`), but the failure is silent data loss rather than a visible error, which is worse for callers who won't notice until the server-side effect is wrong.

**Suggested fix:** Before the second `handler(request)` call, check `request.body.consumed` (after the first send) and raise a `ClientPayloadError`/`ClientError` for non-replayable bodies, mirroring the redirect-handling check in `client.py`. Alternatively, always cache the body via `body.as_bytes()` before the first send (as is already done for `auth-int`), so retries are always replayable regardless of `qop`.

---

## 3. WebSocket `max_msg_size` off-by-one rejects uncompressed messages exactly at the configured limit

**File:** `aiohttp/_websocket/reader_py.py`, line 552 (`WebSocketReader._feed_data`, `READ_PAYLOAD_LENGTH` handling, ~lines 543–559)

**What goes wrong:**

```python
if self._max_msg_size and self._frame_opcode in {
    OP_CODE_TEXT,
    OP_CODE_BINARY,
    OP_CODE_CONTINUATION,
}:
    partial_len = len(self._partial)
    if self._payload_bytes_to_read >= self._max_msg_size - partial_len:
        raise WebSocketError(
            WSCloseCode.MESSAGE_TOO_BIG,
            f"Message size {int(self._payload_bytes_to_read) + partial_len} "
            f"exceeds limit {self._max_msg_size}",
        )
```

The comparison uses `>=`, so an uncompressed TEXT/BINARY message whose total size is *exactly equal* to `max_msg_size` is rejected as "too big," even though it does not exceed the limit. For example, with `max_msg_size = 256` and a 256-byte payload, `_payload_bytes_to_read (256) >= max_msg_size (256) - partial_len (0)` is true, so `WebSocketError` is raised with the message `"Message size 256 exceeds limit 256"` — which is self-contradictory (256 does not exceed 256).

**Why it's wrong:** `max_msg_size` documents a maximum allowed size — messages up to and including that size are expected to be accepted. This is confirmed by the equivalent check for the *compressed*-message path a few lines earlier in the same function, which correctly uses strict `>`:

```python
if self._max_msg_size and len(payload_merged) > self._max_msg_size:
    raise WebSocketError(
        WSCloseCode.MESSAGE_TOO_BIG,
        f"Decompressed message exceeds size limit {self._max_msg_size}",
    )
```

So a compressed message of exactly `max_msg_size` bytes is accepted, while an uncompressed message of the identical size is rejected — an inconsistency between two code paths enforcing the same nominal limit within the same reader.

**Trigger scenario:** Configure a `WebSocketReader` (or `ClientWebSocketResponse`/`WebSocketResponse`) with `max_msg_size=N`, and receive an uncompressed TEXT or BINARY message whose payload is exactly `N` bytes. The connection is closed with `WSCloseCode.MESSAGE_TOO_BIG` instead of the message being delivered.

**Severity:** Medium. Not a security issue, but a functional/interoperability bug: a compliant peer sending a message of precisely the configured maximum size has its connection abruptly closed, which is confusing since `max_msg_size` is typically chosen to match an expected maximum payload.

**Suggested fix:** Change the comparison to strict `>`, matching the compressed-message check:

```python
if self._payload_bytes_to_read > self._max_msg_size - partial_len:
```

---

## Areas reviewed with no confirmed defects

The full package was reviewed (client stack, web server stack, HTTP/WebSocket parsing and writing, streams, multipart, compression, cookies, routing, static file serving, middlewares, connector/pooling, resolver, tracing, worker, test utilities). Several areas were scrutinized closely and ruled out after tracing the logic in full:

- Cookie jar RFC 6265 domain-match, path-match, default-path algorithm, `max-age`/`expires` precedence, and the fallback regex parsers for malformed `Set-Cookie`/`Cookie` headers — all verified correct.
- `web_fileresponse.py` RFC 9110 conditional-request precedence (`If-Match` → `If-Unmodified-Since` → `If-None-Match` → `If-Modified-Since`), `If-Range` strong comparison, and `Range` → offset/count conversion including suffix-range and out-of-range (416) handling.
- `StaticResource.resolve()`'s use of a non-normalized path to build `match_dict["filename"]` looks suspicious in isolation, but `_resolve_path_to_response()` independently re-resolves and bounds-checks the final path via `relative_to()`, so path traversal is not actually reachable.
- Redirect handling, connection acquire/release, proxy `CONNECT` tunneling with TLS-in-TLS, and WebSocket handshake/heartbeat/close state machines in the client stack.
- Duplicate `Content-Length` header handling in lax/response parsing — headers are comma-joined by `HeadersDictProxy.get()`, which then fails the digits-only validation in `get_content_length()`, so this is handled correctly rather than being a smuggling vector.
- Pipelined-message buffering/flow-control (`_buffer_paused`, `MAX_MSG_QUEUE_SIZE`, pause/resume thresholds) in `web_protocol.py`.

## Files read

`__init__.py`, `abc.py`, `base_protocol.py`, `client.py`, `client_exceptions.py`, `client_middleware_digest_auth.py`, `client_middlewares.py`, `client_proto.py`, `client_reqrep.py`, `client_ws.py`, `compression_utils.py`, `connector.py`, `cookiejar.py`, `_cookie_helpers.py`, `formdata.py`, `hdrs.py`, `helpers.py`, `http.py`, `http_exceptions.py`, `http_parser.py`, `http_websocket.py`, `http_writer.py`, `log.py`, `multipart.py`, `payload.py`, `resolver.py`, `streams.py`, `tcp_helpers.py`, `test_utils.py`, `tracing.py`, `typedefs.py`, `web.py`, `web_app.py`, `web_exceptions.py`, `web_fileresponse.py`, `web_log.py`, `web_middlewares.py`, `web_protocol.py`, `web_request.py`, `web_response.py`, `web_routedef.py`, `web_runner.py`, `web_server.py`, `web_urldispatcher.py`, `web_ws.py`, `worker.py`, `_websocket/__init__.py`, `_websocket/helpers.py`, `_websocket/models.py`, `_websocket/reader.py`, `_websocket/reader_py.py`, `_websocket/writer.py` (all under `aiohttp/` in the pinned checkout).

All three findings above were independently re-verified by direct inspection of the pinned-commit source (not taken on faith from any external comparison).
