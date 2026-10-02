model: gpt-5.6-terra
repo: aiohttp
pinned commit: e11d2836203a21bec59095498e578d37801027e7
date/time started and finished: started approximately 2026-09-28 22:11:02 UTC; finished 2026-09-28 22:15:55 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# aiohttp package review — terra run 02

## Findings

### 1. Precompressed static files can be sent when the client explicitly rejects that encoding

- **Severity:** medium
- **Location:** `aiohttp/web_fileresponse.py:241-243`
- **Trigger and result:** If both `asset.js` and `asset.js.gz` exist, a request with `Accept-Encoding: gzip;q=0` receives `asset.js.gz` with `Content-Encoding: gzip`. The same happens for an unrelated token containing the substring, such as `Accept-Encoding: xgzip`. If both Brotli and gzip sidecars exist, `Accept-Encoding: br;q=0, gzip;q=1` selects the rejected Brotli representation because `.br` is checked first.
- **Why this is wrong:** `prepare()` identifies this value as the `Accept-Encoding` header and says that encoding comparisons follow RFC 9110 (`aiohttp/web_fileresponse.py:256-260`), but `_get_file_path_stat_encoding()` merely tests whether the coding name is a substring. `q=0` means a content coding is unacceptable, and a coding token must be matched as a token rather than as arbitrary text.
- **Suggested fix:** Parse `Accept-Encoding` into case-insensitive coding tokens and quality values. Consider a sidecar only when its exact token is acceptable (`q > 0`), and choose the supported sidecar with the greatest acceptable quality (using a documented tie-breaker).

### 2. `Range: bytes=-0` is treated as a satisfiable full-file range

- **Severity:** low
- **Location:** `aiohttp/web_request.py:679-685` (manifested by `aiohttp/web_fileresponse.py:358-395`)
- **Trigger and result:** For a nonempty file, `Range: bytes=-0` is parsed as `start = -0`, which is integer `0`. It therefore bypasses the suffix-range branch, sets `count` to the whole file, and returns `206` with `Content-Range: bytes 0-(size-1)/size`. A zero-length suffix range is unsatisfiable and should return `416` with `Content-Range: bytes */size`.
- **Why this is wrong:** The parser converts an omitted first position with a supplied final position to a suffix range at lines 682-685, but does not reject a zero suffix length. The response code itself states that only a suffix range with a **non-zero** suffix length is satisfiable (`web_fileresponse.py:381-387`).
- **Suggested fix:** In `BaseRequest.http_range`, reject the `start is None and end == 0` form with `ValueError`, or preserve a suffix-length-zero sentinel and make `FileResponse` return `416` for it. Add a functional regression test for `bytes=-0`.

### 3. FileResponse returns 304 for unsafe methods whose conditional request failed

- **Severity:** medium
- **Location:** `aiohttp/web_fileresponse.py:215-226`, consumed at `282-285`
- **Trigger and result:** A handler that returns `FileResponse` for `POST` (or another non-GET/HEAD method) responds to a matching `If-None-Match` with `304 Not Modified`. It does the same for an applicable `If-Modified-Since`. For a non-GET/HEAD request, a false `If-None-Match` precondition must produce `412 Precondition Failed`; `If-Modified-Since` is only evaluated for GET or HEAD.
- **Why this is wrong:** The code cites RFC 9110 conditional-request semantics immediately before the `If-None-Match` branch, but loses the request-method distinction and always maps the outcome to `_FileResponseResult.NOT_MODIFIED`, which `prepare()` always renders as 304. A direct `FileResponse` is not limited to `StaticResource`, whose routes happen to be GET/HEAD.
- **Suggested fix:** When a matching `If-None-Match` occurs, return `NOT_MODIFIED` only for GET/HEAD and `PRE_CONDITION_FAILED` otherwise. Evaluate `If-Modified-Since` only for GET/HEAD, matching the conditional-request rules.

### 4. Digest-auth retry silently resends an exhausted async request body

- **Severity:** medium
- **Location:** `aiohttp/client_middleware_digest_auth.py:484-503`
- **Trigger and result:** Send a POST using an async generator as `data` through `DigestAuthMiddleware` to a server that first returns a Digest 401 challenge. The first request drains the generator. The middleware invokes `handler(request)` again with the same `ClientRequest`, so the authenticated retry has an empty chunked body rather than the original content. The server can authenticate but process an empty upload.
- **Why this is wrong:** `AsyncIterablePayload.write_with_length()` explicitly marks an advanced iterator as consumed because it is irreversible (`aiohttp/payload.py:1050-1055`), and after exhaustion it returns without writing bytes (`1046-1048`). `ClientRequest` sends that payload through `write_with_length()` (`aiohttp/client_reqrep.py:1500-1501`). The normal redirect path recognizes this exact condition and raises `ClientPayloadError` rather than silently replaying an empty body (`aiohttp/client.py:795-803`); the digest retry does neither a replayability check nor a body cache.
- **Suggested fix:** Before retrying after a 401, detect `request.body.consumed` and raise a clear `ClientPayloadError`, as the redirect code does. If replaying async bodies is desired, buffer the body before the initial send (with a documented memory limit) and replace it with a replayable payload for both sends.

## Files read

- `aiohttp/cookiejar.py`
- `aiohttp/web_fileresponse.py`
- `aiohttp/client_middleware_digest_auth.py`
- `aiohttp/payload.py`
- `aiohttp/client_reqrep.py`
- `aiohttp/client.py`
- `aiohttp/web_request.py`
- `aiohttp/web_urldispatcher.py`
- `aiohttp/_cookie_helpers.py`
- `aiohttp/client_middlewares.py`
- `aiohttp/http_writer.py`
- `tests/test_client_middleware_digest_auth.py` (context)
- `tests/test_cookiejar.py` (context)
- `tests/test_web_sendfile.py` (context)
- `tests/test_web_sendfile_functional.py` (context)
- `tests/test_web_request.py` (context)
- `tests/test_web_urldispatcher.py` (context)
