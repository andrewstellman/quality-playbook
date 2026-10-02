model: gpt-5.6-terra
repo: aiohttp
pinned commit: e11d2836203a21bec59095498e578d37801027e7
date/time started and finished: started approximately 2026-09-28 22:16:06 UTC; finished 2026-09-28 22:19:11 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# aiohttp package review — e11d2836203a21bec59095498e578d37801027e7

## Findings

### 1. `Accept-Encoding` substring matching serves a compressed static representation to clients that reject it

- **Severity:** medium
- **Location:** `aiohttp/web_fileresponse.py:242`
- **Trigger and impact:** If both `asset.js` and `asset.js.br` exist, a request with `Accept-Encoding: br;q=0` receives `asset.js.br` and `Content-Encoding: br`. The same happens for an unrelated token containing the substring, such as `Accept-Encoding: zebra`. A client that explicitly disallows Brotli can therefore receive an undecodable representation.
- **Why this is wrong:** The loop treats an encoding as accepted whenever its spelling occurs anywhere in the header (`if file_encoding not in accept_encoding`). The request header is a comma-separated list of coding tokens with optional quality values; `q=0` means that coding is unacceptable. The nearby comment in `prepare()` says the comparisons must be case-insensitive, which calls for token comparison, not an arbitrary case-insensitive substring match.
- **Suggested fix:** Parse `Accept-Encoding` into coding tokens and quality values. Choose `.br`/`.gz` only for an exact token (or an applicable wildcard) with positive quality, honoring explicit exclusions and preferences. Reuse that parser for dynamic response compression.

### 2. Dynamic response compression ignores `q=0` and matches encoding names inside unrelated tokens

- **Severity:** medium
- **Location:** `aiohttp/web_response.py:348-351`
- **Trigger and impact:** Calling `Response(...).enable_compression()` for a request with `Accept-Encoding: gzip;q=0` still sets `Content-Encoding: gzip` and compresses the body. `Accept-Encoding: xgzip` also selects gzip. Such clients can receive content they declared unacceptable.
- **Why this is wrong:** `_start_compression()` checks `if value in accept_encoding`, so it does not parse token boundaries or quality parameters. The method's own RFC 9110 comment identifies this as `Accept-Encoding` handling, and a coding listed with quality zero is expressly not acceptable.
- **Suggested fix:** Replace the substring test with shared, quality-aware `Accept-Encoding` parsing. Pick only exact supported codings whose quality is greater than zero, and do not select a coding explicitly excluded by the client.

### 3. `TextIOPayload` uses the source file's byte size as the length after re-encoding text

- **Severity:** medium
- **Location:** `aiohttp/payload.py:535-559`, `aiohttp/payload.py:778-787`; used by `aiohttp/client_reqrep.py:1279-1282,1501`
- **Trigger and impact:** Pass a text-mode file as `TextIOPayload(file, encoding="utf-16")` to a request. `size` is the file's on-disk byte count, while `_read_and_available_len()` encodes its characters as UTF-16. `ClientRequest` installs the on-disk count as `Content-Length` and subsequently passes that count to `write_with_length`. For example, a one-byte UTF-8 file containing `"a"` produces a four-byte UTF-16 value but declares one byte; the write path truncates the transmitted value to that one byte. The server sees a malformed, truncated request body.
- **Why this is wrong:** `TextIOPayload` documents that it encodes text before writing (lines 764-775), but inherits `IOBasePayload.size`, which returns `os.fstat(...).st_size` (the original file bytes). `ClientRequest` relies on this value for both `Content-Length` and the write limit, so it must describe the bytes that will actually be sent.
- **Suggested fix:** Do not expose a fixed `size` for a re-encoded text stream unless the exact encoded byte length can be established. Prefer returning `None` so the request is chunked, or pre-encode/buffer the content and use that buffer's byte length. A specialized implementation must also count encoded bytes rather than source characters when enforcing a caller-provided content-length limit.

## Files read

- `aiohttp/_cookie_helpers.py`
- `aiohttp/cookiejar.py`
- `aiohttp/web_fileresponse.py`
- `aiohttp/web_middlewares.py`
- `aiohttp/web_routedef.py`
- `aiohttp/compression_utils.py`
- `aiohttp/http_writer.py`
- `aiohttp/web_response.py`
- `aiohttp/payload.py`
- `aiohttp/client.py`
- `aiohttp/client_reqrep.py`
- `aiohttp/web_protocol.py`
- `aiohttp/client_proto.py`
- `aiohttp/helpers.py`
