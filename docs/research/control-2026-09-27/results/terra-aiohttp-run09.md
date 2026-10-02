model: gpt-5.6-terra
repo: aiohttp
pinned commit: e11d2836203a21bec59095498e578d37801027e7
date/time started and finished: started approximately 2026-09-28 22:24:10 UTC; finished 2026-09-28 22:26:32 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# aiohttp package review

Reviewed commit `e11d2836203a21bec59095498e578d37801027e7` in the requested `aiohttp/` package scope.

## Findings

### High — Digest credentials can be sent preemptively to an attacker-controlled origin

- **File:** `aiohttp/client_middleware_digest_auth.py:450-462, 474-495`
- **Trigger:** A server at the middleware's anchor origin responds to a Digest challenge with an absolute `domain` directive such as `domain="https://attacker.example/"`. The application subsequently uses the same `DigestAuthMiddleware` instance for a request to that URL (with the default `preemptive=True`).
- **What goes wrong:** `_authenticate()` accepts every absolute URI in the server-supplied `domain` value and adds it directly to `_protection_space` (line 462), without checking that its origin equals `response.url.origin()`. `_in_protection_space()` then makes the different-origin request pass the guard at lines 474-482, and lines 489-495 attach a Digest `Authorization` response computed from the configured username and password. This sends a credential-derived authorization value to an origin selected by the first server.
- **Why this is wrong:** The middleware documents its guarantee at lines 176-183: credentials are scoped to the first origin and another origin should receive no digest response except through an RFC 7616 `domain` protection space. RFC 7616's `domain` directive requires its URI values to identify the same server; accepting arbitrary absolute origins defeats the stated origin-scoping behavior.
- **Suggested fix:** Resolve each directive URI against `origin`, then retain it only when its `.origin()` equals `origin`. Ignore malformed or cross-origin entries; if none remain, use the default `[str(origin)]` protection space.

### Low — A zero-length suffix range is treated as a full-file partial response

- **File:** `aiohttp/web_request.py:679-685` (observed by `aiohttp/web_fileresponse.py:358-395`)
- **Trigger:** Serve a nonempty `FileResponse` and request `Range: bytes=-0`.
- **What goes wrong:** `http_range` turns the suffix length `0` into `start = -0`, which is Python integer `0`, and clears `end`. `FileResponse` consequently takes the normal non-suffix branch, calculates the entire file length, and returns `206` with the full representation. A zero-length suffix-byte-range is unsatisfiable and must produce `416`; the FileResponse comment at lines 381-387 explicitly says only a suffix range with a *non-zero* suffix length is satisfiable.
- **Suggested fix:** Preserve whether the range was suffix form and reject `bytes=-0` in `BaseRequest.http_range` (raise `ValueError`), or return an explicit representation that lets `FileResponse` identify zero suffix length and send its existing 416 response.

### Low — A WebSocket message exactly equal to `max_msg_size` is rejected

- **File:** `aiohttp/_websocket/reader_py.py:543-557`
- **Trigger:** Configure `max_msg_size=N` and receive an uncompressed TEXT, BINARY, or final fragmented message whose aggregate payload is exactly `N` bytes.
- **What goes wrong:** The early size guard raises when `payload_bytes_to_read >= max_msg_size - partial_len`. Thus a 3-byte unfragmented text frame is rejected for `max_msg_size=3`, although it is not larger than the maximum. The later decompressed-message check at lines 326-330 correctly rejects only `len(payload_merged) > max_msg_size`, so compressed and uncompressed frames disagree at the boundary.
- **Why this is wrong:** The public API describes `max_msg_size` as the “maximum size of read websocket message” (for example `docs/client_reference.rst:854-856`), which includes a message at the limit; the nearby decompression path implements that same inclusive limit.
- **Suggested fix:** Change the early comparison to `>` while retaining the subtraction form used to avoid overflow.

## Files read

- `aiohttp/cookiejar.py`
- `aiohttp/_cookie_helpers.py`
- `aiohttp/client.py`
- `aiohttp/connector.py`
- `aiohttp/client_middleware_digest_auth.py`
- `aiohttp/web_fileresponse.py`
- `aiohttp/web_request.py`
- `aiohttp/web_response.py`
- `aiohttp/streams.py`
- `aiohttp/http_writer.py`
- `aiohttp/_websocket/writer.py`
- `aiohttp/_websocket/reader_py.py`
- `aiohttp/_websocket/reader_c.pxd`
- `docs/client_reference.rst`
- `docs/web_reference.rst`
