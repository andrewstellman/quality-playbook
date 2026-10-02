model: gpt-6-sol
repo: aiohttp
pinned commit: e11d2836203a21bec59095498e578d37801027e7
date/time started and finished: started approximately 2026-09-28 21:51:19 UTC; finished 2026-09-28 21:53:05 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; runtime reproduction unavailable; command details not captured
interruptions or errors: missing multidict prevented runtime verification
network access attempted (yes/no, and what): no attempt reported

# aiohttp package review

1. **Medium — Replacing an expiring cookie with a session cookie leaves the old deadline.** `aiohttp/cookiejar.py:396-425` schedules an expiration when the new cookie has `Max-Age` or `Expires`, but never removes an existing entry from `_expirations` when a replacement with the same `(domain, path, name)` has neither attribute. For example, set `sid=old; Max-Age=60`, then `sid=new` on the same URL: the new session cookie is deleted 60 seconds later. This contradicts the class's RFC 6265 cookie-storage contract (`aiohttp/cookiejar.py:45`): a replacement cookie's attributes determine its lifetime. **Fix:** clear the prior expiration for the identity before applying the replacement's lifetime; stale heap entries can be ignored by `_do_expiration`.

2. **Medium — A rejected encoding can still select a compressed file.** `aiohttp/web_fileresponse.py:241-250` tests whether an encoding string occurs anywhere in the raw `Accept-Encoding` value. A request with `Accept-Encoding: gzip;q=0` therefore receives the `.gz` file with `Content-Encoding: gzip` if it exists, despite the client's explicit zero quality for gzip. The module says this value controls selection (`aiohttp/web_fileresponse.py:237-260`) and labels the response with that encoding (`aiohttp/web_fileresponse.py:410-412`). **Fix:** parse encoding tokens and quality values, selecting only encodings with positive quality (and respecting wildcard and identity preferences).

3. **Medium — `If-None-Match` produces 304 for non-GET methods.** `aiohttp/web_fileresponse.py:215-219` returns `NOT_MODIFIED` for every matching request, and `_not_modified` sets status 304 (`aiohttp/web_fileresponse.py:163-172`). If a `FileResponse` handles a POST or PUT request with a matching `If-None-Match`, RFC 9110 conditional request semantics require 412 Precondition Failed; 304 applies to GET and HEAD. The method's nearby RFC 9110 citation establishes the intended semantics. **Fix:** branch on `request.method`, returning `PRE_CONDITION_FAILED` for methods other than GET and HEAD.

4. **Medium — Digest retry can retain a large 401 response and its connection.** `aiohttp/client_middleware_digest_auth.py:498-505` calls the handler again after a digest challenge without releasing the first `ClientResponse`. For a 401 with a large or streaming body, its payload may never reach EOF because its buffer fills, so the first connection remains occupied while the retry tries to acquire another. With a connector limit of one, this can hang until timeout. The main client redirect loop explicitly releases a response before following it (`aiohttp/client.py:806-815`), and `ClientResponse.release()` exists to free that connection (`aiohttp/client_reqrep.py:600-607`). **Fix:** release the challenged response before the retry, preferably in a `finally` path that also covers digest computation errors.

5. **Low — Saving over an existing permissive cookie file does not secure its mode.** `aiohttp/cookiejar.py:166-175` passes mode `0o600` to `os.open`, which only sets permissions when creating a new file. If `file_path` already exists with mode `0o644`, `save()` truncates and writes authentication or session cookies while leaving it readable by others. This contradicts the adjacent comment that the save operation enforces least-privilege access. **Fix:** explicitly set the file descriptor's mode to `0o600` (or write to a newly created private temporary file and atomically replace the destination).

Files read: `aiohttp/client_middleware_digest_auth.py`, `aiohttp/client_middlewares.py`, `aiohttp/cookiejar.py`, `aiohttp/web_fileresponse.py`, `aiohttp/payload.py`, `aiohttp/client.py`, `aiohttp/client_reqrep.py`, `tests/test_cookiejar.py`, `tests/test_client_middleware_digest_auth.py`, `tests/test_web_sendfile.py`.

Runtime reproduction was unavailable because the checkout's Python environment lacks `multidict`; findings above follow directly from the reviewed branches and call paths.
