model: gpt-6-sol
repo: aiohttp
pinned commit: e11d2836203a21bec59095498e578d37801027e7
date/time started and finished: started before 2026-09-28 21:45:47 UTC (exact time not captured); finished 2026-09-28 21:47:20 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; local runtime reproduction was unavailable because multidict is missing; command details not captured
interruptions or errors: missing multidict prevented runtime reproduction
network access attempted (yes/no, and what): no attempt reported

# aiohttp package review

Checkout: `e11d2836203a21bec59095498e578d37801027e7`  
Scope: `aiohttp/` (excluding tests)

## Findings

1. **Persistent cookie expiry survives replacement by a session cookie** — `aiohttp/cookiejar.py:396-425` — **medium**. If a server first sets `sid=old; Max-Age=60` and later sets `sid=new` for the same domain and path, the second cookie replaces the morsel at line 422 but does not remove the earlier entry from `_expirations`. Once the first deadline passes, `_do_expiration()` sees the still-matching deadline and deletes the new session cookie. This contradicts the cookie jar's RFC 6265 storage behavior and the replacement behavior documented by the adjacent comment at lines 392-394: the newly received cookie supersedes the old cookie's attributes, including its lifetime. **Fix:** when a replacement has no valid `Max-Age` or `Expires`, remove that cookie identity from `_expirations` (stale heap entries can remain until normal cleanup); likewise clear any prior deadline when invalid expiry attributes are treated as absent.

2. **An `Expires` date at the Unix epoch becomes a session cookie** — `aiohttp/cookiejar.py:413-416` — **medium**. `_parse_date("Thu, 01 Jan 1970 00:00:00 GMT")` returns the valid timestamp `0`, but `if expire_time := ...` treats zero as a parse failure, clears the `expires` attribute, and stores the cookie indefinitely. Servers commonly expire cookies by setting a past `Expires` date; RFC 6265 requires a past expiry to remove the cookie. **Fix:** test `expire_time is not None` rather than its truth value, then schedule expiration at `0`.

3. **A forbidden content encoding can still select a compressed file** — `aiohttp/web_fileresponse.py:241-249` — **medium**. With both `asset.js` and `asset.js.gz` present, `Accept-Encoding: gzip;q=0` still passes the substring test `"gzip" in accept_encoding`, so `FileResponse` sends the gzip file with `Content-Encoding: gzip`. Under HTTP content negotiation, `q=0` means that coding is unacceptable; the client may be unable to decode the response. The same substring check can match tokens that merely contain an encoding name. **Fix:** parse `Accept-Encoding` as comma-separated coding tokens with quality values, and select a compressed variant only when that coding is acceptable (including applicable wildcard rules).

The package could not be imported for runtime checks in this checkout because `multidict` is absent (`ModuleNotFoundError`); these findings follow directly from the cited control flow. No checkout files were modified.

## Files read

- `aiohttp/client_middleware_digest_auth.py`
- `aiohttp/web_fileresponse.py`
- `aiohttp/cookiejar.py`
- `aiohttp/payload.py`
- `tests/test_cookiejar.py`
