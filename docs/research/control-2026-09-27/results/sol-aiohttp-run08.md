model: gpt-6-sol
repo: aiohttp
pinned commit: e11d2836203a21bec59095498e578d37801027e7
date/time started and finished: started approximately 2026-09-28 21:50:32 UTC; finished 2026-09-28 21:52:57 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; runtime reproduction unavailable; command details not captured
interruptions or errors: missing multidict prevented runtime verification
network access attempted (yes/no, and what): no attempt reported

# aiohttp package review — e11d2836203a21bec59095498e578d37801027e7

## Findings

1. **Medium — Replacing a persistent cookie with a session cookie retains the old deadline.** `aiohttp/cookiejar.py:396–425`. Set `sid=old; Max-Age=60` from `https://example.com/`, then set `sid=new` from the same URL before the minute expires. The second update replaces the morsel but never removes the `(domain, path, name)` entry from `_expirations`. When the old deadline arrives, `_do_expiration()` sees the still matching heap entry and deletes `sid=new`. A replacement session cookie should survive until the jar/session ends; the file's own comment at line 95 identifies `(domain, path, name)` as the cookie identity, and `update_cookies()` explicitly replaces the morsel at lines 418–423. Clear any existing expiry for that identity before processing the replacement's `Max-Age`/`Expires`, then schedule a new deadline only if the replacement specifies one. Stale heap entries are already handled by the `_expirations` equality check.

2. **Medium — A prohibited content encoding can be served by `FileResponse`.** `aiohttp/web_fileresponse.py:241–250`. With `foo.txt.gz` present, `Accept-Encoding: gzip;q=0` still satisfies `file_encoding in accept_encoding`, so the response contains gzip bytes and `Content-Encoding: gzip`. The same happens with `br;q=0` and a `.br` variant. An HTTP quality of zero means that coding is unacceptable; the method's purpose is to select a variant accepted by the request, as shown by the fallback comment at line 252 and the `Accept-Encoding` handling in `prepare()` at lines 256–264. Parse coding tokens and quality values, and select only codings with positive effective quality (including the wildcard rule).

3. **Low — An invalid `Max-Age` prevents a valid `Expires` fallback.** `aiohttp/cookiejar.py:396–416`. For a Set-Cookie value such as `sid=x; Max-Age=bogus; Expires=Wed, 21 Oct 2030 07:28:00 GMT`, `int(max_age)` raises, the code clears the invalid attribute, and the `elif expires` branch is skipped. The cookie becomes a session cookie even though it has a valid expiry. The class documents RFC 6265 behavior; under that parsing model an invalid Max-Age attribute is ignored, leaving Expires to determine persistence. Parse Max-Age first, and if it is invalid, continue to the Expires branch.

I could not run package tests in this checkout: importing `aiohttp` fails because `multidict` is absent from the local environment. These findings follow directly from the code paths above.

## Files read

- `aiohttp/cookiejar.py`
- `aiohttp/_cookie_helpers.py`
- `aiohttp/web_fileresponse.py`
- `aiohttp/web_request.py`
- `tests/test_cookiejar.py`
- `tests/test_web_sendfile_functional.py`
