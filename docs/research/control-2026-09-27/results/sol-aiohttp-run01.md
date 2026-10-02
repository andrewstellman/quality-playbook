model: gpt-6-sol
repo: aiohttp
pinned commit: e11d2836203a21bec59095498e578d37801027e7
date/time started and finished: started before 2026-09-28 21:45:47 UTC (exact time not captured); finished 2026-09-28 21:47:12 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; local runtime reproduction was unavailable because multidict is missing; command details not captured
interruptions or errors: missing multidict prevented runtime reproduction
network access attempted (yes/no, and what): no attempt reported

# aiohttp code review — e11d2836203a21bec59095498e578d37801027e7

## Findings

1. **Persistent cookie expiry survives replacement by a session cookie** — `aiohttp/cookiejar.py:396-423` — **Medium**. Set `sid=old; Max-Age=1; Path=/`, then replace it on the same host and path with `sid=new; Path=/`. The second update changes the morsel but never removes the prior `(domain, path, name)` entry from `_expirations` or its heap entry. On the old deadline, `_do_expiration()` deletes `sid=new`. A cookie without `Max-Age` or `Expires` is a session cookie, and the code's own cookie-identity comment at line 95 establishes that the second cookie replaces the first. Clear the old expiration when a replacing cookie has no valid expiry, while allowing stale heap entries to be ignored by the existing timestamp check.

2. **A forbidden content encoding is selected for `FileResponse`** — `aiohttp/web_fileresponse.py:241-243` — **Medium**. If both `index.html` and `index.html.gz` exist, a request with `Accept-Encoding: gzip;q=0` receives the `.gz` file with `Content-Encoding: gzip`. The code only checks whether the encoding name occurs as a substring; it ignores quality weights, including zero, and even matches unrelated tokens such as `xgzip`. The header is an encoding preference list, and a zero weight explicitly rejects that encoding; `prepare()` passes this header to the selector at lines 256-263. Parse the comma-separated coding entries and their weights, and select the compressed variant only when that coding is acceptable with positive quality.

3. **Digest retry leaves the 401 response open** — `aiohttp/client_middleware_digest_auth.py:498-503` — **Medium**. When a server sends a Digest 401 with a response body that has not reached EOF and the connector has `limit_per_host=1`, the middleware immediately calls `handler(request)` again while the first response still holds the connection. The retry waits for a free connection, but the middleware cannot return the first response for its caller to release. `ClientResponse._response_eof()` and `release()` in `aiohttp/client_reqrep.py:569-607` show that the connection is released only at EOF or explicit release; the redirect path in `aiohttp/client.py:807-821` explicitly releases before retrying. Release the challenged response before the retry, including the path where digest encoding raises, and guard any retry exception so the response is closed.

4. **Digest challenges after another authentication scheme are ignored** — `aiohttp/client_middleware_digest_auth.py:418-429` — **Medium**. A 401 with two `WWW-Authenticate` fields, for example `Basic realm="site"` followed by `Digest realm="site", nonce="n"`, returns the first value from `response.headers.get()` and immediately rejects it as non-Digest. The middleware's class docstring says it handles 401 responses containing a Digest challenge, and `parse_header_pairs()` documents that a header can carry multiple challenges. Iterate all `WWW-Authenticate` field values and locate a Digest challenge, including when it follows another scheme in one field, before deciding there is no supported challenge.

## Validation and files read

Runtime reproductions could not run because the local Python environment lacks `multidict` (`ModuleNotFoundError` on importing aiohttp). No checkout files were modified, and no network access was used.

Files read: `aiohttp/client_middleware_digest_auth.py`, `aiohttp/client_reqrep.py`, `aiohttp/client.py`, `aiohttp/cookiejar.py`, `aiohttp/payload.py`, `aiohttp/web_fileresponse.py`, `tests/test_client_middleware_digest_auth.py`, `tests/test_cookiejar.py`, `tests/test_web_sendfile.py`.
