model: gpt-5.6-terra
repo: aiohttp
pinned commit: e11d2836203a21bec59095498e578d37801027e7
date/time started and finished: started approximately 2026-09-28 22:17:02 UTC; finished 2026-09-28 22:20:47 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# aiohttp package review — e11d2836203a21bec59095498e578d37801027e7

## Findings

### 1. A session-cookie replacement retains the old cookie's expiry

- **Severity:** medium
- **Location:** `aiohttp/cookiejar.py:396-416`
- **Trigger:** Receive `Set-Cookie: sid=old; Max-Age=60; Path=/`, then, before
  that minute elapses, receive `Set-Cookie: sid=new; Path=/` from the same host
  and path (the same applies to an invalid `Max-Age` or `Expires`).
- **What goes wrong:** The second response correctly replaces the stored morsel
  with a session cookie, but it never removes the previous
  `("host", "path", "sid")` entry from `_expirations`. When the first
  response's deadline arrives, `_do_expiration()` deletes the new session
  cookie. A session cookie must not inherit a superseded cookie's persistence
  deadline; RFC 6265's replacement algorithm derives the new cookie's
  persistent flag and expiry from the new attributes.
- **Why:** This branch only creates or changes an entry by calling
  `_expire_cookie()` when the incoming morsel has a valid `Max-Age` or
  `Expires`. Neither the no-attribute path nor the invalid-attribute paths
  remove an existing entry, even though lines 418-423 replace the stored cookie.
- **Suggested fix:** For every replacement that does not yield a valid expiry,
  call `self._expirations.pop((domain, path, name), None)`. The stale heap item
  can remain and will be ignored/compacted because it no longer matches the map.
  Add a regression test that advances time past the first response's `Max-Age`
  after storing the second session cookie.

### 2. Digest middleware ignores Digest when another challenge is first

- **Severity:** medium
- **Location:** `aiohttp/client_middleware_digest_auth.py:418-429`
- **Trigger:** A server sends a 401 with more than one `WWW-Authenticate`
  field, such as `WWW-Authenticate: Basic realm="legacy"` followed by
  `WWW-Authenticate: Digest realm="api", nonce="n", qop="auth"`.
- **What goes wrong:** `response.headers.get()` returns only the first field.
  The subsequent scheme check sees `Basic` and returns `False`, so the
  middleware never retries with Digest despite a valid Digest challenge being
  present. The same failure occurs when a combined field lists Basic before
  Digest.
- **Why:** HTTP authentication permits multiple challenges. The parser's own
  comment at lines 122-125 explicitly recognizes that a single header can
  carry several challenges, yet `_authenticate()` selects one field and rejects
  it before looking for another Digest challenge.
- **Suggested fix:** Iterate all `WWW-Authenticate` field values (for example,
  `headers.getall(hdrs.WWW_AUTHENTICATE, [])`) and select a Digest challenge;
  parse combined challenges without treating a preceding non-Digest scheme as a
  terminal failure. Add coverage for Basic-then-Digest in separate fields and
  in one field.

### 3. A Digest `domain` directive can authorize credential responses to an arbitrary origin

- **Severity:** high
- **Location:** `aiohttp/client_middleware_digest_auth.py:450-462`, consumed at
  `470-495`
- **Trigger:** After the middleware has been used against `https://service.example`,
  that server replies with a valid Digest challenge containing
  `domain="https://attacker.example/"`. A later request to the attacker origin
  receives a preemptive Digest Authorization header.
- **What goes wrong:** The code places every absolute URI from the untrusted
  `domain` directive into `_protection_space` without checking its origin.
  Lines 481-495 then treat that URI as authorized and compute an Authorization
  response using the configured password for the attacker-controlled server.
- **Why:** RFC 7616 section 3.3 requires an absolute URI in the `domain`
  directive to be on the same server as the challenged URI. The implementation
  accepts a different host verbatim at line 462. This also defeats the class
  documentation's origin-scoping guarantee at lines 176-183: the server that
  first receives the credentials can expand the scope to any origin.
- **Suggested fix:** Parse each absolute URI and retain it only if it has the
  same origin (at minimum the same host, as required by RFC 7616) as
  `response.url.origin()`; retain path-absolute URIs by resolving them against
  that origin. Add a test that a cross-origin URI in `domain` does not receive
  preemptive authentication.

## Files read

Source files: `aiohttp/_cookie_helpers.py`, `aiohttp/abc.py`,
`aiohttp/client.py`, `aiohttp/client_middleware_digest_auth.py`,
`aiohttp/client_reqrep.py`, `aiohttp/cookiejar.py`, `aiohttp/helpers.py`,
`aiohttp/http_parser.py`, `aiohttp/multipart.py`, `aiohttp/web_fileresponse.py`,
`aiohttp/web_protocol.py`, and `aiohttp/web_request.py`.

Context files: `tests/test_client_functional.py`,
`tests/test_client_middleware_digest_auth.py`, `tests/test_cookie_helpers.py`,
`tests/test_cookiejar.py`, `docs/abc.rst`, and `docs/client_reference.rst`.

## Verification note

I attempted a small runtime probe for the cookie-expiry scenario, but this
checkout cannot import its package because the locally available interpreter is
missing the checkout's `multidict` dependency. The finding follows directly
from the retained `_expirations` entry and was not dependent on a network fetch
or on modifying the checkout.
