model: gpt-6-sol
repo: aiohttp
pinned commit: e11d2836203a21bec59095498e578d37801027e7
date/time started and finished: started approximately 2026-09-28 21:50:32 UTC; finished 2026-09-28 21:53:00 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; runtime reproduction unavailable; command details not captured
interruptions or errors: missing multidict prevented runtime verification
network access attempted (yes/no, and what): no attempt reported

# aiohttp package review — e11d2836203a21bec59095498e578d37801027e7

## Findings

### 1. Digest retry can wait forever for its own connection

- **File and line:** `aiohttp/client_middleware_digest_auth.py:499–503`
- **Severity:** High
- **What goes wrong:** When the initial 401 has an unread or streaming response body, the middleware immediately calls `handler(request)` again without releasing the first response. With a connector limit of one, the 401 retains the sole connection and the authenticated retry waits in `BaseConnector.connect()` for a slot that this middleware still holds. The request hangs until its timeout (or indefinitely if no effective timeout applies).
- **Why this is wrong:** The middleware promises to automatically retry Digest challenges. `ClientResponse.release()` is the API that frees the connection (`client_reqrep.py:600–608`), and the redirect retry path explicitly calls it before continuing (`client.py:815`).
- **Suggested fix:** Release the challenged response before the next handler call. Also release it if constructing the retry authorization raises, while preserving the final response returned to the caller.

### 2. Replacing a persistent cookie with a session cookie retains the old deadline

- **File and line:** `aiohttp/cookiejar.py:396–423`
- **Severity:** Medium
- **What goes wrong:** Set a cookie with `Max-Age=60`, then replace the same `(domain, path, name)` with a cookie that has no `Max-Age` or `Expires`. The second update overwrites the morsel but never removes the old entry from `_expirations`. At the original 60-second deadline, `_do_expiration()` deletes the replacement session cookie. The same problem follows a replacement whose expiry attribute is invalid.
- **Why this is wrong:** `CookieJar` says it follows RFC 6265, under which the new cookie replaces the old cookie's attributes, including its persistence. The code stores expiry by cookie identity in `_expirations` and `_do_expiration()` deletes the current cookie whenever that stored deadline is reached (`cookiejar.py:279–312`).
- **Suggested fix:** Clear an existing expiry for the cookie identity before processing the replacement's `Max-Age`/`Expires`, then schedule a new expiry only when the replacement has a valid expiry. Stale heap entries can be ignored by the existing equality check.

### 3. Precompressed file selection ignores `q=0` in Accept-Encoding

- **File and line:** `aiohttp/web_fileresponse.py:241–250`
- **Severity:** Medium
- **What goes wrong:** With an uncompressed file and its `.br` sibling present, `Accept-Encoding: br;q=0, gzip` still selects the Brotli file because the selection checks only whether `"br"` is a substring. A client that explicitly disallows Brotli receives `Content-Encoding: br`. The substring check can also match an unrelated token containing the codec name.
- **Why this is wrong:** This is the HTTP content-coding negotiation implemented by `FileResponse`; a zero quality value means the coding is unacceptable, yet `_prepare_open_file()` emits the selected coding in `Content-Encoding` (`web_fileresponse.py:401–407`).
- **Suggested fix:** Parse `Accept-Encoding` as comma-separated coding tokens with quality values, honoring explicit `q=0` and wildcard rules, then select only an acceptable precompressed variant.

### 4. Digest challenge is missed when another authentication scheme comes first

- **File and line:** `aiohttp/client_middleware_digest_auth.py:418–429`
- **Severity:** Medium
- **What goes wrong:** A valid `WWW-Authenticate: Basic realm="site", Digest realm="site", nonce="n"` response produces no Digest retry. The middleware partitions the header at its first space and returns as soon as that first scheme is not `Digest`. The same issue occurs when Basic and Digest are separate header fields and `.get()` yields Basic.
- **Why this is wrong:** The middleware documents that it handles 401 responses containing a Digest challenge. Its own `parse_header_pairs()` documentation acknowledges that a `WWW-Authenticate` header may carry several challenges (`client_middleware_digest_auth.py:109–119`), but `_authenticate()` considers only the leading one.
- **Suggested fix:** Inspect all `WWW-Authenticate` field values, identify a Digest challenge at challenge boundaries, and parse only that challenge's parameters.

## Verification and files read

The review used static tracing of the checked-out code. A local import check could not run because the checkout environment lacks `multidict`; no packages were installed and the checkout was not changed.

Files read: `aiohttp/client_middleware_digest_auth.py`, `aiohttp/cookiejar.py`, `aiohttp/compression_utils.py`, `aiohttp/web_fileresponse.py`, `aiohttp/_websocket/writer.py`, `aiohttp/payload.py`, `aiohttp/client_reqrep.py`, `aiohttp/client.py`, `aiohttp/connector.py` (searched relevant connection paths), `tests/test_cookiejar.py`, `tests/test_client_middleware_digest_auth.py`, and `tests/test_web_sendfile.py` (searched Accept-Encoding coverage).
