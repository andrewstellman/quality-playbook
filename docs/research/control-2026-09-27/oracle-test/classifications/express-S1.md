# express, classifier S1 (Claude Sonnet), blind

### express-01
Oracle: The code's own comment says `/**/` and the `typeof` check exist "to reduce client error noise," implying the emitted snippet is meant to be syntactically valid JS. The length check `callback.length !== 0` (lib/response.js) runs on the *unsanitized* callback before the sanitizing `.replace(/[^\[\]\w$.]/g, '')` executes, so a callback that is entirely disallowed characters (`!!!`) passes the "non-empty" gate but becomes `''` after sanitization, producing malformed output (`typeof  === 'function'`).
Type: in-repo
Confidence: high

### express-02
Oracle: `res.get`'s own JSDoc declares `@return {String}` (lib/response.js:697-701), but `res.set('Content-Type','foo')` stores the boolean `false` (returned by `mime.contentType('foo')` for an unrecognized type) via `setHeader`, so `res.get('Content-Type')` returns `false`, contradicting its documented return type. The second half (falls back to `text/html`) is explained by `res.send`'s `!this.get('Content-Type')` check treating that stored `false` as "not set."
Type: in-repo
Confidence: high

### express-03
Oracle: The `res.sendFile` docstring (lib/response.js:~335-346) states "Other options are passed along to `send`," but the code unconditionally does `opts.etag = this.app.enabled('etag')` (lib/response.js:404) before calling `send()`, overwriting whatever `etag` the caller passed — contradicting the documented pass-through behavior.
Type: in-repo
Confidence: high

### express-04
Oracle: The sibling function `res.sendStatus` (lib/response.js, a few lines above) explicitly guards against unknown codes with `statuses.message[statusCode] || String(statusCode)`. `res.redirect` uses the bare `statuses.message[status]` (lines 843, 848-849) with no such fallback, so an unregistered code like 399 yields `undefined`, which leaks into both the title and body text.
Type: in-repo
Confidence: high

### express-05
Oracle: Same code as express-03 — `var opts = options || {}` (lib/response.js:~380) keeps `opts` as the same object reference as the caller's `options` when one is passed, and the subsequent `opts.etag = this.app.enabled('etag')` (line 404) mutates that shared object. Nothing in the docstring says the caller's options object will be mutated as a side effect.
Type: in-repo
Confidence: high

### express-06
Oracle: The function's own JSDoc example (lib/request.js, directly above the implementation) states `req.acceptsCharsets('utf-8, utf-16') // => "utf-8"`, i.e. it documents comma-delimited-string support. The implementation (line 172-174) just forwards `accept.charsets(...charsets)` without splitting on commas, so the documented example does not hold (observed `false`).
Type: in-repo
Confidence: high

### express-07
Oracle: `res.send` sets `Content-Type: bin` when `ArrayBuffer.isView(chunk)` is true (lib/response.js:~205), showing intent to treat typed arrays as binary payloads, but it then relies on `Buffer.from(chunk, encoding)`/`Buffer.byteLength` to convert. Node's documented `Buffer.from()` contract treats a non-Uint8Array TypedArray as a generic array of octet values (each entry coerced/truncated to 0-255), not as a byte-accurate view of the underlying buffer — this is a documented Node.js Buffer API behavior, not an Express-authored spec.
Type: known-external
Confidence: medium

### express-08
Oracle: `req.hostname`'s own inline comment "IPv6 literal support" (lib/request.js:449-452) shows the code's declared intent to correctly handle bracketed IPv6 hosts, but it only uses the bracket offset to find the port colon — `host.substring(0, index)` still returns the string with its brackets intact. `req.subdomains` (line ~389) then calls `isIP(hostname)` on that bracketed string, which Node's `net.isIP()` (a well-known API contract) reports as `0` for a bracketed literal, so the code falls through to splitting it on `.` as if it were a domain name.
Type: in-repo
Confidence: high

### express-09
Oracle: The `req.subdomains` docstring's own worked example (lib/request.js, directly above line 389) states that for domain `tobi.ferrets.example.com` with default offset, subdomains are `["ferrets","tobi"]`. The implementation just does `hostname.split('.').reverse().slice(offset)` with no trimming of empty trailing labels, so a trailing dot (a standard FQDN notation, RFC 1035 §3.1) adds an extra empty element that shifts the slice boundary, pulling `"example"` into the result — contradicting the documented example for that same domain.
Type: in-repo
Confidence: medium

### express-10
Oracle: This throws (`ERR_INVALID_ARG_TYPE`) and the request ends in an uncaught-error 500 — a crash needs no external spec. Root cause is visible by comparing the two branches at lib/response.js:172-178: the `!generateETag && chunk.length < 1000` branch only computes `Buffer.byteLength(chunk, encoding)` without reassigning `chunk` to an actual `Buffer`, while the sibling `else` branch does `chunk = Buffer.from(chunk, encoding)`. The un-converted `Uint16Array` is then passed straight to `this.end(chunk, encoding)`, which requires a string/Buffer/Uint8Array.
Type: implicit
Confidence: high

### express-11
Oracle: RFC 6265 §5.2.2 specifies that a `Max-Age` of zero (or negative) means the user agent must expire the cookie immediately. `res.cookie` (lib/response.js:764-769) computes `opts.maxAge = Math.floor(maxAge / 1000)`, so any `maxAge` under 1000ms floors to `0`, while `opts.expires` is simultaneously set to `Date.now() + maxAge` (still ~0.5s in the future) — the two directives in the same `Set-Cookie` header contradict each other per the RFC's semantics for `Max-Age: 0`.
Type: known-external
Confidence: medium

Hardest to classify: express-07 and express-10, because the "wrongness" hinges on Node's own `Buffer`/`TypedArray` semantics rather than anything Express states about itself — Express's `ArrayBuffer.isView` branch shows intent to support typed-array bodies, but whether silently truncating/corrupting the payload (07) versus throwing (10) counts as an Express defect or "garbage in, well-documented Buffer behavior out" is a judgment call. express-09 was also hard: the docstring's own example is contradicted once a trailing dot is added, but a trailing-dot FQDN is an edge case the docs never explicitly promise to handle, so it sits between "docstring contradiction" and "undocumented edge case."
