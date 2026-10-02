model: gpt-5.6-terra
repo: aiohttp
pinned commit: e11d2836203a21bec59095498e578d37801027e7
date/time started and finished: started approximately 2026-09-28 22:21:01 UTC; finished 2026-09-28 22:23:46 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# aiohttp package review

Reviewed checkout: `e11d2836203a21bec59095498e578d37801027e7`  
Scope: `aiohttp/` (tests not inspected)

## Findings

### 1. `StreamResponse` sends encodings the client explicitly disallows

- **Severity:** medium
- **Location:** `aiohttp/web_response.py:348-351`
- **Trigger and effect:** Call `response.enable_compression()` and send a request with `Accept-Encoding: gzip;q=0` (or `Accept-Encoding: xgzip`). The substring check finds `"gzip"` and applies gzip, setting `Content-Encoding: gzip`, despite the former header explicitly rejecting gzip and the latter not naming the `gzip` coding at all.
- **Why this is wrong:** `Accept-Encoding` is a list of coding tokens with optional quality values; `q=0` means the coding is unacceptable. `_start_compression()` is the normal negotiation path (the forced path is explicitly separate at lines 343-345), but it only lowercases the raw field and performs a substring search. The nearby RFC 9110 reference at lines 346-347 establishes that this is HTTP content-coding handling, not a free-text feature check.
- **Suggested fix:** Parse the field as comma-separated coding ranges, compare exact tokens, discard `q=0` entries, and select an available coding by the highest acceptable quality value (with a deterministic tie-breaker). Do not use substring matching.

### 2. `FileResponse` selects a precompressed sidecar that the client rejects

- **Severity:** medium
- **Location:** `aiohttp/web_fileresponse.py:241-250`
- **Trigger and effect:** If both `asset.js` and `asset.js.gz` exist, a request with `Accept-Encoding: gzip;q=0` receives `asset.js.gz` together with `Content-Encoding: gzip`. `Accept-Encoding: xgzip` has the same erroneous result. Clients that correctly honor their own advertised capabilities cannot decode the response.
- **Why this is wrong:** `_get_file_path_stat_encoding()` is the precompressed-representation negotiation function, but it treats a coding as accepted whenever its spelling appears anywhere in the raw header. Its caller lowercases the field at line 260, so case handling is deliberate, but quality values and coding-token boundaries are ignored. This contradicts the RFC 9110 content-coding negotiation indicated by the code's comments and produces a representation the request says is unacceptable.
- **Suggested fix:** Reuse a shared `Accept-Encoding` parser/selector with `StreamResponse`. Only select `.br` or `.gz` when that exact coding has a positive effective quality value; otherwise serve the uncompressed representation (or another acceptable sidecar).

### 3. A zero-length suffix range is turned into a full-file partial response

- **Severity:** low
- **Location:** `aiohttp/web_request.py:682-685`, consumed by `aiohttp/web_fileresponse.py:358-376`
- **Trigger and effect:** For a nonempty file, `Range: bytes=-0` parses `end` as `0`, then sets `start = -end`, which is integer `0`. FileResponse therefore misses its `start < 0` suffix branch, calculates the range as `[0, file_size)`, and returns the entire file as `206 Partial Content` with `Content-Range: bytes 0-(size-1)/size`.
- **Why this is wrong:** A zero-length suffix range is unsatisfiable. The FileResponse comment at lines 381-385 expressly describes a suffix range as satisfiable only when it has a **non-zero** suffix length. The parser loses the suffix form when it converts `-0` to `0`, so the later satisfiability logic cannot reject it.
- **Suggested fix:** In `BaseRequest.http_range`, reject `bytes=-0` with `ValueError` before assigning `start = -end` (or preserve a distinct suffix-range representation and reject a zero suffix). FileResponse will then use its existing 416 path and emit `Content-Range: bytes */<size>`.

## Files read

- `aiohttp/_cookie_helpers.py`
- `aiohttp/client.py`
- `aiohttp/client_middlewares.py`
- `aiohttp/client_middleware_digest_auth.py`
- `aiohttp/client_reqrep.py`
- `aiohttp/client_ws.py`
- `aiohttp/compression_utils.py`
- `aiohttp/connector.py`
- `aiohttp/cookiejar.py`
- `aiohttp/formdata.py`
- `aiohttp/http_parser.py`
- `aiohttp/http_writer.py`
- `aiohttp/multipart.py`
- `aiohttp/payload.py`
- `aiohttp/streams.py`
- `aiohttp/web_fileresponse.py`
- `aiohttp/web_protocol.py`
- `aiohttp/web_request.py`
- `aiohttp/web_response.py`
- `aiohttp/web_urldispatcher.py`
- `aiohttp/web_ws.py`
