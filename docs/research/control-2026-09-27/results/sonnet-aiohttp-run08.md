# Code review: aiohttp (`aiohttp/` package, excluding tests)

Repo: aiohttp, pinned commit `e11d2836203a21bec59095498e578d37801027e7`, checkout at `/tmp/control/aiohttp` (read-only).

Method: the package was split into four groups (client-side, web-server-side, HTTP/WebSocket protocol layer, and utility modules) and each group was read in full by a dedicated reviewer, tracing logic rather than skimming. I then independently re-verified each reported finding against the actual source lines before including it here. Findings below are only the ones I could confirm by direct inspection of the code.

---

## 1. `aiohttp/client_reqrep.py:1450` — `chunked=False` is silently treated as `chunked=True`, producing a Content-Length/Transfer-Encoding framing mismatch

```python
if self.chunked is not None:
    writer.enable_chunking()
```

`ClientRequest.__init__` takes `chunked: bool | None` straight from the public `ClientSession.request(..., chunked: bool | None = None, ...)` API (`aiohttp/client.py:479`), and stores it verbatim as `self.chunked = chunked` (`client_reqrep.py:1111`). `False` is a legitimate, distinct value from `None` here — "explicitly do not chunk" vs. "not specified." Every other place in this file treats `self.chunked` as a truthy flag, consistently:

- `_update_transfer_encoding` (`client_reqrep.py:1242`): `elif self.chunked:`
- `_update_body_from_data` (`client_reqrep.py:1280`): `if not self.chunked and hdrs.CONTENT_LENGTH not in self.headers:`

But `_create_writer` (line 1450) checks `is not None` instead of truthiness.

Trace for `session.post(url, data=b"hello", chunked=False)`:
1. `self.chunked = False`.
2. `_update_body_from_data`: `not self.chunked` is `True` → body length is known (5 bytes) → sets `Content-Length: 5`; `self.chunked` remains `False`.
3. `_update_transfer_encoding`: `elif self.chunked:` is `False` → no `Transfer-Encoding` header is added.
4. `_create_writer`: `self.chunked is not None` → `True` (because `False is not None`) → `writer.enable_chunking()` **is called anyway**.

Result: the request declares `Content-Length: 5` in its headers, but `StreamWriter.chunked` is `True`, so the body is actually written on the wire in chunked-transfer-encoding framing (`"5\r\nhello\r\n0\r\n\r\n"`). A server trusting the declared `Content-Length: 5` reads only the first 5 raw bytes (`"5\r\nh"`) as the complete body, and treats the remaining bytes (`"ello\r\n0\r\n\r\n"`) as the start of the next request on a keep-alive connection — a request-framing desync of the kind RFC 7230 §3.3.3 exists specifically to prevent ("a sender MUST NOT send a Content-Length header field in any message that contains a Transfer-Encoding header field" / messages must not be ambiguous about their length).

**Severity:** High — silent wire-level corruption/desync for a documented, reachable public API input (`chunked=False`), not merely a cosmetic mismatch.

**Suggested fix:**
```python
if self.chunked:
    writer.enable_chunking()
```
(matching the truthy checks used everywhere else in the same file).

---

## 2. `aiohttp/_websocket/reader_py.py:552` — off-by-one in the WebSocket message-size limit rejects messages exactly at the configured limit

```python
if self._payload_bytes_to_read >= self._max_msg_size - partial_len:
    raise WebSocketError(
        WSCloseCode.MESSAGE_TOO_BIG,
        f"Message size {int(self._payload_bytes_to_read) + partial_len} "
        f"exceeds limit {self._max_msg_size}",
    )
```
(`WebSocketReader._feed_data`, `READ_PAYLOAD_LENGTH` state, inside `if self._max_msg_size and self._frame_opcode in {OP_CODE_TEXT, OP_CODE_BINARY, OP_CODE_CONTINUATION}:`).

For an uncompressed TEXT/BINARY/CONTINUATION frame whose declared payload length plus any already-buffered partial-message bytes is exactly equal to `max_msg_size`, this raises `WebSocketError(MESSAGE_TOO_BIG)` and aborts the connection, even though the message does not exceed the limit — it equals it. The `>=` should be `>`.

This is confirmed wrong by two things in the same file:
- The error text itself says "exceeds limit," and a size equal to the limit does not exceed it.
- The parallel check for the *decompressed*-payload path a few lines earlier (`reader_py.py:326`) correctly uses strict `>`:
  ```python
  if self._max_msg_size and len(payload_merged) > self._max_msg_size:
      raise WebSocketError(
          WSCloseCode.MESSAGE_TOO_BIG,
          f"Decompressed message exceeds size limit {self._max_msg_size}",
      )
  ```
  So a compressed message that decompresses to exactly `max_msg_size` bytes is accepted, while an uncompressed message of exactly `max_msg_size` bytes is rejected — inconsistent behavior for what is documented as the same limit.

**Trigger:** any peer (client or server, this reader is shared) sending a single-frame TEXT/BINARY message whose payload length is exactly `max_msg_size` (e.g. the configured `WebSocketResponse`/`ClientWebSocketResponse` `max_msg_size`, default 4 MiB).

**Severity:** Medium — not a security hole (it's overly strict, not under-strict), but a real boundary/interop bug: a spec-compliant peer sending a message of precisely the documented maximum size gets its connection closed with 1009 (Message Too Big).

**Suggested fix:**
```python
if self._payload_bytes_to_read > self._max_msg_size - partial_len:
```

---

## 3. `aiohttp/client_reqrep.py:126` — `ClientTimeout.__post_init__`'s "total=0 is unsupported" check is bypassed when another timeout field is set

```python
object.__setattr__(
    self, "total",
    max(self.total, self.connect or 0, self.sock_read or 0, self.sock_connect or 0),
)
if self.total == 0:
    raise ValueError(
        "total timeout must be a positive number or None to disable, "
        "got 0. Using 0 to disable timeouts is no longer supported, "
        "use None instead."
    )
```

The check that rejects an explicit `total=0` only fires if `max(...)` is still `0` after folding in the other timeout fields. `ClientTimeout(total=0, connect=5)` computes `max(0, 5, 0, 0) == 5`, silently rewriting `total` to `5` — the documented `ValueError` ("Using 0 to disable timeouts is no longer supported") never raises, and the caller's `total=0` is silently discarded/overridden rather than rejected as the docstring/error message says it unconditionally will be.

**Severity:** Low — behavior is not incorrect for `connect`/`sock_read`/`sock_connect` themselves, but the stated contract ("total=0 is unsupported, always raises") is not actually enforced whenever any other timeout field is also set, so callers relying on the documented guard to catch a `total=0` mistake can be misled.

**Suggested fix:** check `self.total == 0` before folding in the other fields with `max()`, e.g.:
```python
if self.total == 0:
    raise ValueError(...)
object.__setattr__(self, "total", max(self.total, ...))
```

---

## 4. `aiohttp/payload.py:512,532` (and the equivalent `TextIOPayload` code at ~784/807) — `remaining_content_len or DEFAULT_CHUNK_SIZE` treats an explicit zero-byte content length as "no limit"

```python
return size, self._value.read(
    min(
        DEFAULT_CHUNK_SIZE,
        size or DEFAULT_CHUNK_SIZE,
        remaining_content_len or DEFAULT_CHUNK_SIZE,
    )
)
...
return self._value.read(remaining_content_len or DEFAULT_CHUNK_SIZE)
```

`remaining_content_len: int | None` is documented as "Optional maximum number of bytes to read. If None, DEFAULT_CHUNK_SIZE will be used." `0` is a legitimate, distinct value (a payload whose `write_with_length(writer, content_length=0)` is called), but the `x or DEFAULT_CHUNK_SIZE` idiom treats `0` the same as `None`, so the code performs a real, synchronous, in-executor `file.read()` of up to `DEFAULT_CHUNK_SIZE` (256 KiB) from the underlying file even though 0 bytes were requested.

I traced the call site (`write_with_length`, `payload.py:580-634`): the over-read chunk does get correctly truncated to zero bytes before being written to the wire (`chunk[:remaining_content_len]` with `remaining_content_len == 0`), and the loop terminates after one iteration via `_should_stop_writing`'s `remaining_content_len <= 0` check, so no corrupted bytes reach the network. The effect is purely a wasted blocking disk read (and unnecessary executor round-trip/latency) on every zero-length-capped payload write, not a data-correctness bug.

**Severity:** Low — no output corruption, but a real, deterministic "falsy zero" logic bug with measurable wasted I/O on a reachable code path.

**Suggested fix:** use an explicit `is not None` check at all four sites, e.g. `remaining_content_len if remaining_content_len is not None else DEFAULT_CHUNK_SIZE`.

---

## Lower-confidence observation (not reported as a confirmed defect)

`aiohttp/web_request.py`, `BaseRequest.raw_path`: for an absolute-form request target with no path component (`GET http://example.com HTTP/1.1`), the method returns `""` rather than `"/"`, which is a plausible RFC 3986 §6.2.3 deviation from the documented "raw PATH INFO" contract. I did not include this in the numbered findings above because it requires an unusual absolute-form request with an empty path, and the path-matching code that actually drives routing uses `rel_url`/`path_safe` (derived from `yarl.URL`), not `raw_path`, so I could not confirm real-world impact with the same confidence as the findings above.

---

## Files read

**Client-side:** `aiohttp/client.py`, `aiohttp/client_reqrep.py`, `aiohttp/client_proto.py`, `aiohttp/client_exceptions.py`, `aiohttp/client_ws.py`, `aiohttp/client_middlewares.py`, `aiohttp/client_middleware_digest_auth.py`, `aiohttp/connector.py`, `aiohttp/resolver.py`

**Web server-side:** `aiohttp/web.py`, `aiohttp/web_app.py`, `aiohttp/web_protocol.py`, `aiohttp/web_request.py`, `aiohttp/web_response.py`, `aiohttp/web_runner.py`, `aiohttp/web_server.py`, `aiohttp/web_ws.py`, `aiohttp/web_urldispatcher.py`, `aiohttp/web_middlewares.py`, `aiohttp/web_log.py`, `aiohttp/web_exceptions.py`, `aiohttp/web_fileresponse.py`, `aiohttp/web_routedef.py`, `aiohttp/worker.py`

**HTTP/WebSocket protocol layer:** `aiohttp/http_parser.py`, `aiohttp/http_writer.py`, `aiohttp/http.py`, `aiohttp/http_exceptions.py`, `aiohttp/http_websocket.py`, `aiohttp/streams.py`, `aiohttp/base_protocol.py`, `aiohttp/tcp_helpers.py`, `aiohttp/_websocket/__init__.py`, `aiohttp/_websocket/reader.py`, `aiohttp/_websocket/reader_py.py`, `aiohttp/_websocket/writer.py`, `aiohttp/_websocket/models.py`, `aiohttp/_websocket/helpers.py`

**Utility modules:** `aiohttp/helpers.py`, `aiohttp/multipart.py`, `aiohttp/payload.py`, `aiohttp/formdata.py`, `aiohttp/cookiejar.py`, `aiohttp/_cookie_helpers.py`, `aiohttp/compression_utils.py`, `aiohttp/tracing.py`, `aiohttp/abc.py`, `aiohttp/typedefs.py`, `aiohttp/hdrs.py`, `aiohttp/test_utils.py`, `aiohttp/__init__.py`, `aiohttp/log.py`

**Context-only (read partially, to understand a caller/callee):** `aiohttp/compression_utils.py` (from the protocol-layer review), `aiohttp/web_protocol.py` (grepped from the protocol-layer review)

All findings above were independently re-verified by me directly against the checked-out source (exact line numbers, surrounding call sites, and the public API surface at `aiohttp/client.py`) before being included in this report.
