BUG-006: cookie maxAge: 0 is dropped, turning an expiring cookie into a session cookie. CONFIRMED.
Claim: response.cookie('k','v',{maxAge:0}) (and plainCookie/encryptedCookie) emits no Max-Age; expected Max-Age=0. Also overrides config default maxAge:90 and then drops it.
Mechanism: src/helpers.ts:245 `options.maxAge ? ... : undefined` (truthiness). cookie-es serializes 0 as Max-Age=0 fine.
Doc: v6-docs_basics_cookies.md:67 "The maxAge property accepts a string-based time expression, and its value will be converted to seconds." Type is number|string.
Tests: tests/cookies/serializer.spec.ts covers undefined, '1min', 60 only. clearCookie sets maxAge=-1 and expects Max-Age=0 (tests/response.spec.ts:1260), so expired Max-Age is intended to reach the header.
Pushback: clearCookie is the documented delete path; severity LOW. Fix: check undefined/null, not truthiness.
