model: gpt-6-sol
repo: aiohttp
pinned commit: e11d2836203a21bec59095498e578d37801027e7
date/time started and finished: started before 2026-09-28 21:45:47 UTC (exact time not captured); finished 2026-09-28 21:47:22 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; local runtime reproduction was unavailable because multidict is missing; command details not captured
interruptions or errors: missing multidict prevented runtime reproduction
network access attempted (yes/no, and what): no attempt reported

# aiohttp package review

Checkout: `e11d2836203a21bec59095498e578d37801027e7`  
Scope: `aiohttp/` (excluding tests)

## Findings

1. **Medium — Replacing an expiring cookie with a session cookie retains the old deadline.** `aiohttp/cookiejar.py:396-425`. For example, after `sid=old; Max-Age=60`, receiving `sid=new` for the same domain and path changes the stored morsel but never removes its entry from `_expirations`. When the original 60 seconds pass, `_do_expiration()` deletes the new session cookie. `CookieJar` says it follows RFC 6265, and its own storage model identifies a cookie by `(domain, path, name)` (`aiohttp/cookiejar.py:87`); a replacement cookie without `Max-Age` or `Expires` is a session cookie with no scheduled expiry. Remove any prior expiration for the identity before scheduling the replacement's valid deadline. Leave stale heap entries to be ignored by the existing equality check.

2. **Medium — `FileResponse` sends a precompressed file when the client explicitly rejects that encoding.** `aiohttp/web_fileresponse.py:241-250`. With a `file.gz` present and `Accept-Encoding: gzip;q=0`, the substring test finds `gzip` and serves `file.gz` with `Content-Encoding: gzip` (`aiohttp/web_fileresponse.py:410-415`). The same applies to `br;q=0`. A zero quality value means the encoding is unacceptable under the HTTP content negotiation semantics that this function implements. Parse `Accept-Encoding` into coding tokens and quality values; choose a sidecar only when its coding has positive quality (including an applicable wildcard), and then honor preference among candidates.

3. **Medium — Digest middleware retries a consumed streaming request body.** `aiohttp/client_middleware_digest_auth.py:484-502`. On a normal first request with an `AsyncIterablePayload`, `write_with_length()` drains the iterator, sets `_iter = None`, and marks it consumed (`aiohttp/payload.py:1046-1072`). If the server replies with a Digest challenge, the middleware calls the same handler with the same request again. The second send writes no body; for `qop=auth-int`, `_encode()` calls `as_bytes()` and hashes empty bytes (`aiohttp/client_middleware_digest_auth.py:310-316`; `aiohttp/payload.py:1087-1093`). This contradicts the middleware's documented automatic retry and `auth-int` support (`aiohttp/client_middleware_digest_auth.py:160-170`) and can silently turn a nonempty POST into an empty one. Before retrying, detect a consumed, nonreplayable payload and raise an explicit error; supporting this case requires buffering the body before its first send or obtaining a fresh payload for the retry.

## Verification limit

The checkout's Python environment lacks `multidict`, so importing `aiohttp` for a runtime reproduction fails with `ModuleNotFoundError`. These findings follow directly from the cited control flow and were checked against the adjacent payload and response code.

## Files read

`aiohttp/cookiejar.py`, `aiohttp/client_middleware_digest_auth.py`, `aiohttp/web_fileresponse.py`, `aiohttp/web_request.py`, `aiohttp/payload.py`, `aiohttp/client.py`, `aiohttp/client_reqrep.py`, `aiohttp/helpers.py`, `aiohttp/multipart.py`, `tests/test_cookiejar.py`, `tests/test_client_middleware_digest_auth.py`, `tests/test_web_sendfile_functional.py`.
