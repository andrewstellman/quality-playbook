model: gpt-6-sol
repo: aiohttp
pinned commit: e11d2836203a21bec59095498e578d37801027e7
date/time started and finished: started approximately 2026-09-28 21:48:26 UTC; finished 2026-09-28 21:51:04 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; runtime reproduction attempted but unavailable; command details not captured
interruptions or errors: missing multidict prevented runtime reproduction
network access attempted (yes/no, and what): no attempt reported

# aiohttp review — e11d2836203a21bec59095498e578d37801027e7

## Findings

1. **Medium — A replacement session cookie keeps the previous cookie's expiration.** `aiohttp/cookiejar.py:396–425`. Set `sid` with `Max-Age=1`, then update the same `(domain, path, name)` with a new `sid` that has neither `Max-Age` nor `Expires`. The replacement is stored, but `_expirations` retains the old deadline because this branch only calls `_expire_cookie` when an expiry attribute is present. At the old deadline, `_do_expiration()` deletes the new cookie. This contradicts the jar's RFC 6265 behavior: a cookie without either expiry attribute is a session cookie, and replacement should adopt the new cookie's expiry state. Clear the old `_expirations` entry when replacing a cookie that has no valid expiry; stale heap entries can then be ignored by the existing equality check.

2. **Medium — `FileResponse` serves a compressed representation when the client explicitly disallows it.** `aiohttp/web_fileresponse.py:241–243`. With both `file.txt` and `file.txt.gz` present, `Accept-Encoding: gzip;q=0` still selects the `.gz` file, sets `Content-Encoding: gzip`, and sends compressed bytes. The substring check also treats unrelated tokens containing `br` or `gzip` as acceptance. `Accept-Encoding` quality value zero means the coding is unacceptable; the method's documented purpose is to choose an encoding from the request's accepted encodings. Parse coding tokens and their quality values, matching whole coding names and selecting only those with positive quality (including applicable wildcard handling).

3. **Medium — saving cookies to an existing permissive file exposes session tokens.** `aiohttp/cookiejar.py:166–175`. If the destination already exists with mode `0644`, `save()` opens and truncates it, but `os.open(path, flags, 0o600)` does not change an existing file's permissions. The resulting JSON, which the nearby comment acknowledges can contain authentication/session tokens, remains readable by other users despite the comment's promise of least-privilege access. Create a private temporary file and atomically replace the destination, or otherwise ensure mode `0600` before writing sensitive data.

## Verification note

These findings follow directly from the checked-out code. I could not run package-level reproductions because this checkout's Python environment lacks the `multidict` dependency (`ModuleNotFoundError` on importing `aiohttp`). No network or external code was used.

## Files read

- `aiohttp/client_middleware_digest_auth.py`
- `aiohttp/cookiejar.py`
- `aiohttp/web_fileresponse.py`
- `aiohttp/web_request.py`
- `aiohttp/payload.py`
- `tests/test_cookiejar.py` (relevant expiration test and search matches)
- `tests/test_web_sendfile_functional.py` (relevant compressed-response tests and search matches)
- `tests/test_web_sendfile.py` (search matches)
- `aiohttp/__init__.py` and `aiohttp/hdrs.py` (import traceback only)
