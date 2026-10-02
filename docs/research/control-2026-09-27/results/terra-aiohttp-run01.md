model: gpt-5.6-terra
repo: aiohttp
pinned commit: e11d2836203a21bec59095498e578d37801027e7
date/time started and finished: started approximately 2026-09-28 22:09:54 UTC; finished 2026-09-28 22:12:41 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; local runtime check unavailable
interruptions or errors: missing multidict prevented executable confirmation
network access attempted (yes/no, and what): no attempt reported

# aiohttp package review — terra-aiohttp-run01

## Findings

### 1. Truncated gzip response bodies are accepted as complete

- **Severity:** medium
- **Location:** `aiohttp/http_parser.py:1243-1246`, with the relevant gzip state reset in `aiohttp/compression_utils.py:399-404`.
- **Failure mode:** A response declaring `Content-Encoding: gzip` whose body is cut short after zlib has emitted some plaintext is delivered to the caller as a successful, incomplete response.  `DeflateBuffer.feed_eof()` validates `decompressor.eof` only for `deflate`; gzip never takes that check.  The gzip decompressor has already been reset to a fresh, non-EOF decompressor when the member ended on a chunk boundary, so it cannot provide a completion signal at EOF either.
- **Why this is wrong:** The adjacent `deflate` branch explicitly treats a non-EOF decompressor as invalid content encoding.  Gzip has the same requirement to consume a complete compressed member, including its trailer; accepting a truncated member silently turns a transport/content-integrity failure into a valid response.
- **Suggested fix:** Keep a separate “last gzip member completed” state (or delay resetting the completed decompressor until new input arrives), and reject `gzip` at `feed_eof()` unless the final member completed.  Apply the validation before calling `out.feed_eof()`.

### 2. `FileResponse` serves a precompressed representation that the client explicitly rejected

- **Severity:** medium
- **Location:** `aiohttp/web_fileresponse.py:241-250`.
- **Failure mode:** If both `asset.js` and `asset.js.gz` exist, a request with `Accept-Encoding: gzip;q=0` receives `asset.js.gz` with `Content-Encoding: gzip`.  Similarly, a token such as `xgzip` matches because the code uses a substring check.
- **Why this is wrong:** `q=0` means that an encoding is unacceptable.  The code only checks `if file_encoding not in accept_encoding`, then selects the compressed sibling; it does not parse encoding tokens or quality values.  The caller has already normalized case at lines 256-260, so this routine is the sole acceptance decision.
- **Suggested fix:** Parse `Accept-Encoding` as comma-separated codings with parameters, select only an exact `br`/`gzip` token whose effective quality is greater than zero (respecting wildcard rules), and otherwise fall back to the original file.

### 3. Saving over an existing cookie file leaves its broad permissions intact

- **Severity:** medium
- **Location:** `aiohttp/cookiejar.py:166-175`.
- **Failure mode:** Calling `CookieJar.save()` with the path of an existing mode-0644 cookie file overwrites the contents but leaves the file world-readable.  Those contents may include the session/authentication tokens called out in the preceding comment.
- **Why this is wrong:** `os.open(path, flags, 0o600)` uses the `mode` argument only when the file is created (`O_CREAT`); opening an existing file with `mode="w"` truncates it without changing its mode.  This contradicts the stated intent at lines 166-168 to enforce least-privilege access for credential data.
- **Suggested fix:** Open the file, then call `os.fchmod(f.fileno(), 0o600)` before writing (or write a 0600 temporary file and atomically replace the destination).  The latter also avoids exposing a partially written cookie file.

## Files read

- `aiohttp/cookiejar.py`
- `aiohttp/web_fileresponse.py`
- `aiohttp/compression_utils.py`
- `aiohttp/http_parser.py`
- `aiohttp/client_reqrep.py`
- `aiohttp/client_middleware_digest_auth.py`
- `aiohttp/formdata.py`
- `aiohttp/http_writer.py`
- `aiohttp/streams.py`
- `aiohttp/helpers.py`
- `tests/test_client_middleware_digest_auth.py`
- `tests/test_client_functional.py`
- `tests/test_proxy.py`
