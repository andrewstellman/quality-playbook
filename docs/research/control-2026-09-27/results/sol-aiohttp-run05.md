model: gpt-6-sol
repo: aiohttp
pinned commit: e11d2836203a21bec59095498e578d37801027e7
date/time started and finished: started approximately 2026-09-28 21:48:26 UTC; finished 2026-09-28 21:50:17 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; runtime reproduction attempted but unavailable; command details not captured
interruptions or errors: missing yarl prevented runtime reproduction
network access attempted (yes/no, and what): no attempt reported

# aiohttp package review — e11d2836203a21bec59095498e578d37801027e7

## Findings

1. **A replacement session cookie inherits the old cookie's expiration** — `aiohttp/cookiejar.py:396–425` — **Medium**. Set `sid=old; Max-Age=1; Path=/`, then before that second expires set `sid=new; Path=/` from the same host. `_update_cookies` replaces the morsel, but only changes `_expirations` when the new cookie has `Max-Age` or `Expires`. The old deadline remains keyed by `(domain, path, name)`, so `_do_expiration` deletes `sid=new` when `sid=old` would have expired. This contradicts the jar's RFC 6265 behavior: the replacement cookie has no expiry attribute and is a session cookie. Clear any existing expiration for that identity when accepting a replacement without a valid expiry, leaving stale heap entries to be ignored by the existing equality check.

2. **A file is served in an encoding explicitly rejected by the client** — `aiohttp/web_fileresponse.py:241–249` — **Medium**. If `file.txt.gz` exists and the request carries `Accept-Encoding: gzip;q=0`, the substring test sees `gzip` and selects the gzip file; `_prepare_open_file` then sends it with `Content-Encoding: gzip`. The same test also treats an unrelated token containing `gzip` as acceptance. An encoding with quality zero is explicitly unacceptable under HTTP content negotiation; the file response's encoding selection is meant to choose a representation the client accepts. Parse the header as coding tokens with quality values, selecting a precompressed file only when its coding has positive effective quality (including wildcard handling).

3. **A secondary origin can expand digest credentials to further origins** — `aiohttp/client_middleware_digest_auth.py:446–465` — **High**. The middleware's class documentation says other origins may receive credentials only when they fall within a protection space advertised by the *anchor origin*. After the anchor advertises origin B, requests to B enter the middleware. If B replies `401` with `WWW-Authenticate: Digest ... domain="https://origin-c/"`, `_authenticate` replaces `_protection_space` with C's URL. A later request to C then gets a preemptive digest Authorization header (or answers C's challenge), even though the anchor never advertised C. The existing cross-origin test describes the anchor as vouching for secondary URIs; B has no authority to extend that trust. Preserve the anchor-advertised cross-origin allowlist separately and never let a challenge from another origin expand it; scope any secondary challenge to its already authorized portion.

## Validation

I traced the relevant branches and checked the repository's existing tests for the intended cross-origin digest behavior. A direct runtime reproduction was unavailable because this checkout's Python environment lacks `yarl` (`ModuleNotFoundError`); no dependencies were fetched and the checkout was not modified.

## Files read

- `aiohttp/_websocket/reader_py.py`
- `aiohttp/client_middleware_digest_auth.py`
- `aiohttp/cookiejar.py`
- `aiohttp/payload.py`
- `aiohttp/web_fileresponse.py`
- `aiohttp/web_request.py`
- `tests/test_client_middleware_digest_auth.py`
- `tests/test_cookiejar.py` (search results only)
- `tests/test_http_parser.py` (search results only)
