# express, classifier S3 (Claude Sonnet), blind

### express-01
Oracle: In `res.jsonp` (lib/response.js:274-304) the guard `typeof callback === 'string' && callback.length !== 0` runs on the *raw* callback name, and only afterward is the callback sanitized with `callback.replace(/[^\[\]\w$.]/g, '')` (line 291). For `callback = '!!!'` the guard passes (length 3) but sanitization empties it, so the emitted `typeof  === 'function'` snippet is missing its operand — a self-contradiction between the check and the step that runs after it, visible in the same function.
Type: in-repo
Confidence: high

### express-02
Oracle: The docstring for `res.set`/`res.header` (lib/response.js:660-661) says Content-Type "is expanded to include the charset ... using `mime.contentType()`" — it assumes a string result. For an unrecognized type, `mime.contentType('foo')` returns `false`, which is stored verbatim via `this.setHeader(field, value)` (line 681). Separately, `res.send`'s own check `if (!this.get('Content-Type'))` (line 152) treats the stored boolean `false` as "not set," so a later `res.send` silently overwrites it — an inconsistency between two places in the same file about what a "set" Content-Type looks like.
Type: in-repo
Confidence: high

### express-03
Oracle: `res.sendFile` (lib/response.js:403-404) unconditionally does `opts.etag = this.app.enabled('etag');` right after building `opts` from the caller's `options`, with the comment "wire application etag option to send" — the code visibly discards whatever `etag` the caller passed, regardless of the documented `options` parameter implying caller control (line 379 `@public`, and other option fields like `root`/`maxAge` are passed through untouched).
Type: in-repo
Confidence: high

### express-04
Oracle: `res.redirect` builds body text as `statuses.message[status] + '. Redirecting to ' + address` (lib/response.js:843-849) with no validation that `status` is a registered HTTP status code. 399 is not a code in the IANA HTTP status code registry, so `statuses.message[399]` is `undefined`, and that literal string flows into both the text and HTML bodies. I know this from the HTTP status registry, not from anything quotable in the checkout.
Type: known-external
Confidence: medium

### express-05
Oracle: Same line as express-03 (lib/response.js:404): `opts` is the caller's `options` object itself (`var opts = options || {};`, line 379) when `options` is not a function, so `opts.etag = this.app.enabled('etag');` mutates the caller's own object in place — visible directly from the shared reference, no copy is made.
Type: in-repo
Confidence: high

### express-06
Oracle: The docstring immediately above `req.acceptsCharsets` (lib/request.js:145-168) explicitly documents `req.acceptsCharsets('utf-8, utf-16') // => "utf-8"` as supported comma-delimited input, but the implementation (line 172) does `accept.charsets(...charsets)` with no splitting of a single comma-delimited string before delegating to the `accepts` library — the documented example contradicts the actual code path.
Type: in-repo
Confidence: high

### express-07
Oracle: `res.send` treats any `ArrayBuffer.isView(chunk)` the same way but then (lib/response.js:175) falls into `chunk = Buffer.from(chunk, encoding)` for non-Buffer, non-small chunks. `Buffer.from()` on a non-Uint8Array TypedArray (or a DataView) does not copy the underlying bytes — it iterates it as an array-like of numbers (each entry mod 256) for a `Uint16Array`, and treats a `DataView` as array-like with no numeric `.length`, producing an empty buffer. This is Node.js's own documented `Buffer.from()` behavior, which I know from the Node API docs; the express code makes no special case for these view types despite `res.send`'s docstring implying `Buffer`-like input is transferred faithfully.
Type: known-external
Confidence: high

### express-08
Oracle: `req.hostname` (lib/request.js:444-457) keeps the surrounding `[...]` brackets on an IPv6 literal host (its own comment says "IPv6 literal support," but it only strips the trailing `:port`, not the brackets). `req.subdomains` (lib/request.js:382-392) then calls `isIP(hostname)` on that bracketed string; Node's `net.isIP()` returns `0` for a bracketed literal (it expects the bare address), so the code falls into the `.split('.')` domain-name path — visible from the getter's own stated intent ("IPv6 literal support") failing to deliver bracket-free output for the very isIP() check that immediately follows it.
Type: in-repo
Confidence: high

### express-09
Oracle: `req.subdomains` splits `hostname` on `.` and reverses without stripping a trailing root dot. A trailing dot in a hostname is a valid FQDN root-designator per DNS (RFC 1035 §3.1) and is semantically equivalent to the same name without it, but the split produces an extra empty leading element after reversal, shifting the default `offset: 2` slice and dropping "com" instead of nothing. I know the trailing-dot FQDN convention from the DNS spec, not from anything in the checkout.
Type: known-external
Confidence: medium

### express-10
Oracle: In `res.send` (lib/response.js:172-175), the "small chunk" branch computes `len = Buffer.byteLength(chunk, encoding)` for a TypedArray without converting `chunk` to a `Buffer`/string (unlike the "large chunk" branch a few lines below, which does `chunk = Buffer.from(chunk, encoding)`). The raw `Uint16Array` is then passed to `this.end(chunk, encoding)` (line 218), and Node's `http.ServerResponse.end()`/`.write()` only accepts `string | Buffer | Uint8Array`, throwing `ERR_INVALID_ARG_TYPE` for other TypedArrays — an inconsistency between the two branches of the same function, one of which converts and one of which doesn't.
Type: in-repo
Confidence: high

### express-11
Oracle: `res.cookie` (lib/response.js:764-769) sets `opts.expires = new Date(Date.now() + maxAge)` (sub-second precision preserved) but `opts.maxAge = Math.floor(maxAge / 1000)` (truncated to whole seconds), so for `maxAge: 500` the same option value yields a future `Expires` timestamp alongside `Max-Age=0` — two attributes of the same `Set-Cookie` header that assert contradictory lifetimes, visible directly from the two adjacent assignments in the same block. The docstring only says "max-age in milliseconds, converted to expires" and doesn't flag the truncation or the resulting conflict.
Type: in-repo
Confidence: high

Hardest to classify were express-04 and express-09, both because the "wrongness" hinges on an external contract (the HTTP status-message registry, and the DNS trailing-dot convention) that I know from memory but can't quote or verify against anything in the checkout — meaning my confidence rests on recalled spec knowledge rather than an artifact I can point to, and reasonable people could also read them as "undefined behavior for unusual input" rather than defects. express-07 and express-10 were close calls between `known-external` and `in-repo`, since the failure is really Node's `Buffer`/typed-array contract *interacting with* an internal inconsistency between two branches of the same function — either framing is defensible.
