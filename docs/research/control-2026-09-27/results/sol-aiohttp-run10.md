model: gpt-6-sol
repo: aiohttp
pinned commit: e11d2836203a21bec59095498e578d37801027e7
date/time started and finished: started approximately 2026-09-28 21:53:07 UTC; finished 2026-09-28 21:55:54 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; package tests unavailable because multidict is missing
interruptions or errors: missing multidict prevented package tests
network access attempted (yes/no, and what): no attempt reported

# aiohttp package review — e11d2836203a21bec59095498e578d37801027e7

## Findings

1. **Expiring cookie retains its old deadline after replacement by a session cookie** — `aiohttp/cookiejar.py:396-425` — **medium**. Set `sid=old; Max-Age=10`, then before ten seconds pass set `sid=new` with the same domain and path but no `Max-Age` or `Expires`. The second update replaces the morsel at line 422 but never removes the first cookie's entry from `_expirations`. Once the original ten seconds elapse, `_do_expiration()` sees the old deadline at lines 295-309 and deletes the new cookie. The class documents RFC 6265 cookie storage, and the code's own identity comment at line 95 and replacement comment at lines 392-394 establish that the second cookie replaces the first. A replacement with no expiry is a session cookie and should not inherit the previous cookie's deadline. **Fix:** when accepting a replacement, clear its existing `_expirations` entry if the new cookie has no valid expiration; stale heap entries are already ignored when their key no longer appears in `_expirations`.

2. **A cookie with an epoch-zero Expires date is kept instead of deleted** — `aiohttp/cookiejar.py:412-416` — **medium**. `Expires=Thu, 01 Jan 1970 00:00:00 GMT` is a valid date; `_parse_date()` returns Unix timestamp `0` (line 608). The truthiness check at line 413 treats that value as a parse failure, clears the `expires` attribute, and stores the cookie without an expiry. Servers commonly use a past `Expires` date to delete a cookie. The adjacent `Max-Age <= 0` handling at lines 398-408 and the class's RFC 6265 contract both require immediate expiry here. **Fix:** distinguish `None` from a timestamp of zero with `if expire_time is not None`, then schedule that deadline.

3. **Precompressed files are served even when the client gives their coding quality zero** — `aiohttp/web_fileresponse.py:237-243` — **medium**. With both `file.txt` and `file.txt.br` present, `Accept-Encoding: br;q=0` still passes the substring test (`"br" in "br;q=0"`) and selects the Brotli file. The server then emits `Content-Encoding: br` at lines 410-412 although the client explicitly refused Brotli. The comment in `prepare()` at lines 258-260 links RFC 9110's encoding rules, and the response's own `Vary: Accept-Encoding` depends on honoring the negotiated value. **Fix:** parse `Accept-Encoding` into coding tokens and quality values, apply wildcard and identity rules, and choose only a coding with positive quality.

4. **FileResponse returns 304 for matching If-None-Match on non-GET/HEAD requests** — `aiohttp/web_fileresponse.py:215-219` — **medium**. A route that returns `FileResponse` for `POST` or `PUT` with a matching `If-None-Match` receives `_FileResponseResult.NOT_MODIFIED`, which `prepare()` converts to HTTP 304. RFC 9110's conditional request rules (linked by the code at line 215) require HTTP 412 for a false `If-None-Match` condition on methods other than GET and HEAD. A 304 can make a client interpret a failed write precondition as a successful cache validation. **Fix:** choose `NOT_MODIFIED` only for GET/HEAD and `PRE_CONDITION_FAILED` for other methods when the entity tag matches.

## Verification limits

The checkout could not import `aiohttp` because its local Python environment lacks `multidict`; no package tests were run, and no dependencies were fetched. Standard-library checks confirmed that the epoch date maps to timestamp `0`, and a substring check confirmed that `br` matches `br;q=0`. The remaining outcomes follow directly from the cited branches.

## Files read

- `aiohttp/client_middleware_digest_auth.py`
- `aiohttp/cookiejar.py`
- `aiohttp/web_fileresponse.py`
- `tests/test_cookiejar.py`
- `tests/test_web_sendfile_functional.py`
