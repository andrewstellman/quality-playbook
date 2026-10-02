model: gpt-6-sol
repo: aiohttp
pinned commit: e11d2836203a21bec59095498e578d37801027e7
date/time started and finished: started approximately 2026-09-28 21:48:26 UTC; finished 2026-09-28 21:50:10 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; runtime reproduction attempted but unavailable; command details not captured
interruptions or errors: missing multidict prevented package tests
network access attempted (yes/no, and what): no attempt reported

# aiohttp code review — e11d2836203a21bec59095498e578d37801027e7

## Findings

1. **Medium — A replacement session cookie inherits the old cookie's expiration.** `aiohttp/cookiejar.py:396-420`. If a server sends `Set-Cookie: sid=old; Max-Age=1` and then, before that second elapses, sends `Set-Cookie: sid=new` for the same domain and path, `_update_cookies` replaces the morsel but does not clear the existing `_expirations[(domain, path, name)]` entry. When the old deadline arrives, `_do_expiration` (lines 299-307) deletes `sid=new`. A replacement cookie without `Max-Age` or `Expires` is a session cookie; the class promises RFC 6265 cookie storage and its own persistence code distinguishes cookies with and without an absolute deadline. Clear any previous deadline when processing a replacement before scheduling a new one. An invalid expiration attribute should likewise leave no previous deadline.

2. **Medium — `FileResponse` serves an encoding explicitly refused by the client.** `aiohttp/web_fileresponse.py:241-250`. `_get_file_path_stat_encoding` uses substring membership to decide whether a precompressed `.br` or `.gz` file can be served. With `Accept-Encoding: br;q=0, gzip`, a present `.br` file is selected first and emitted with `Content-Encoding: br` (see lines 401-407), even though a quality value of zero makes that coding unacceptable. The method's purpose and `Vary: Accept-Encoding` emission establish that selection should follow the client's accepted encodings; this also contradicts HTTP `Accept-Encoding` quality semantics. Parse the coding tokens and quality values, reject codings with `q=0`, and compare complete coding names rather than substrings.

## Validation limits

I traced both cases through their callers and expiration/response paths. The checkout's Python dependencies are unavailable here (`multidict` import fails), so I could not execute the package or its tests. I did not modify the checkout.

## Files read

- `aiohttp/client_middleware_digest_auth.py`
- `aiohttp/cookiejar.py`
- `aiohttp/web_fileresponse.py`
- `aiohttp/_cookie_helpers.py`
- `tests/test_cookiejar.py` (matching sections/search results)
- `tests/test_web_sendfile_functional.py` (relevant test section)
- `tests/test_client_middleware_digest_auth.py` (relevant test sections)
