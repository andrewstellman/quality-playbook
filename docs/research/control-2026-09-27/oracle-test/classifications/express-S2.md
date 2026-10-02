# express, classifier S2 (Claude Sonnet), blind

### express-01
Oracle: The code checks `callback.length !== 0` (lib/response.js:284) *before* sanitizing with `callback.replace(/[^\[\]\w$.]/g, '')` (line ~290). For `callback='!!!'`, the length check passes on the raw string, but sanitization then reduces it to `''`, so the emitted body still gets wrapped as `typeof  === 'function' && ();` — invalid JavaScript. The check-before-sanitize ordering is the bug; the intent (a non-empty, syntactically valid callback wrapper) is stated by the surrounding comments ("restrict callback charset", "the typeof check is just to reduce client error noise").
Type: in-repo
Confidence: high

### express-02
Oracle: `res.set`'s docstring (lib/response.js ~658-662) says Content-Type "is expanded to include the charset ... using `mime.contentType()`"; it never anticipates `mime.contentType()` returning `false` for an unrecognized type like `'foo'`, yet the code unconditionally does `this.setHeader(field, value)` with that `false`. `res.send`'s string branch (line 141) then does `typeof type === 'string'` to decide whether to preserve the existing Content-Type or default to `text/html` — a boolean `false` fails that check, silently discarding the caller's `res.set` header. Both behaviors follow directly from the code as written but contradict the documented intent that `res.set('Content-Type', ...)` sets a usable header.
Type: in-repo
Confidence: high

### express-03
Oracle: lib/response.js:404 area: `opts.etag = this.app.enabled('etag');` unconditionally overwrites whatever `etag` the caller passed in `options`, right after the docblock's "Options" list (maxAge, root, headers, dotfiles) says "Other options are passed along to `send`" — implying `etag` should flow through, not be force-replaced.
Type: in-repo
Confidence: high

### express-04
Oracle: `statuses.message[status]` (the `statuses` npm package) is only populated for real, registered HTTP status codes; 399 isn't one, so it's `undefined`, and `res.redirect`'s text/html builders (lib/response.js:843, 848-849) concatenate that directly into the body with no guard. There's no validation anywhere in `redirect()` that `status` is a recognized code (only a `typeof status !== 'number'` deprecation warning), so "undefined" leaking into the response body is the direct, traceable result of missing input validation in this function.
Type: in-repo
Confidence: medium

### express-05
Oracle: Same site as express-03 — `var opts = options || {}` makes `opts` the *same object* as the caller's `options` when a non-function object is passed, and the following `opts.etag = ...` mutates it. Functions mutating a caller-supplied options object without documenting it is a widely recognized API-hygiene rule (don't mutate arguments you don't own) that the docblock doesn't override by stating otherwise.
Type: in-repo
Confidence: high

### express-06
Oracle: The function's own docstring (lib/request.js ~162-163) gives the literal example `req.acceptsCharsets('utf-8, utf-16') // => "utf-8"`, i.e. a comma-delimited single string argument is supposed to be split and matched. The implementation (line 172) does `accept.charsets(...charsets)`, passing the whole unsplit string straight to the `accepts` library, so it's matched as one literal charset token and returns `false`, contradicting the documented example word-for-word.
Type: in-repo
Confidence: high

### express-07
Oracle: `res.send` treats any `ArrayBuffer.isView(chunk)` as sendable binary (line ~150), then falls into `chunk = Buffer.from(chunk, encoding)` (line ~176) when it's not a string/Buffer with a small, no-etag-needed length. `Buffer.from()`'s behavior differs by the exact input type — for a `Uint16Array` it iterates the array's *elements* (not its underlying bytes) and coerces each to a byte, which is documented Node.js `Buffer.from()`/TypedArray-iterable behavior, not an Express-authored code path. Express's own logic never distinguishes byte-oriented views (`Uint8Array`/`Buffer`) from element-oriented ones, so this is a real interaction bug, but the actual "wrong output" is explained by Buffer's documented per-type semantics rather than anything Express states about itself.
Type: known-external
Confidence: medium

### express-08
Oracle: `req.hostname`'s own comment says "// IPv6 literal support" (lib/request.js ~449) and intends to strip the `Host` header down to just the bracketed IPv6 literal, but the substring computed still includes the surrounding `[`/`]` characters. `net.isIP()` (Node's documented IP-parsing contract) correctly returns `0` for a bracket-wrapped string since brackets aren't part of the IP text form, so `req.subdomains` (line 389) then treats it as a dotted hostname and mis-splits it. The comment states the intended behavior; the code doesn't deliver it.
Type: in-repo
Confidence: high

### express-09
Oracle: The `subdomains` docstring's worked example (lib/request.js ~373-377) uses `"tobi.ferrets.example.com"` (no trailing dot) and expects `["ferrets","tobi"]` for the default offset of 2. A trailing dot is the DNS convention for an explicit fully-qualified domain name (an "absolute" name, RFC 1035 §3.1) and is conventionally treated as equivalent to the same name without the dot; `req.hostname`/`req.subdomains` never strip it, so `.split('.')` produces an extra empty trailing segment that shifts every subsequent slice by one, matching the given output.
Type: known-external
Confidence: medium

### express-10
Oracle: In the no-etag, small-chunk fast path (lib/response.js ~178-181), `len = Buffer.byteLength(chunk, encoding)` is computed correctly for a `Uint16Array` (byteLength counts bytes), but `chunk` itself is left as the raw `Uint16Array` instead of being converted to a `Buffer`. `this.end(chunk)` at the bottom of `send()` then hands that non-`Uint8Array` typed array straight to Node's HTTP response stream, which only accepts `string`/`Buffer`/`Uint8Array` for `.end()`/`.write()` and throws `ERR_INVALID_ARG_TYPE` — an uncaught crash surfacing as a 500.
Type: implicit
Confidence: high

### express-11
Oracle: `res.cookie`'s docstring (lib/response.js ~726) says `maxAge` is "max-age in milliseconds, converted to `expires`," but the code (lines ~764-768) also independently sets `opts.maxAge = Math.floor(maxAge / 1000)` for the Set-Cookie `Max-Age` attribute, floor-rounding sub-second values to `0`. Per RFC 6265 §5.2.2, `Max-Age=0` (or negative) instructs the user agent to expire/delete the cookie immediately, and Max-Age takes precedence over `Expires` when both are present — so a caller asking for a 500 ms cookie gets one that browsers will treat as already expired, directly contradicting the still-future `Expires` value computed one line above it.
Type: known-external
Confidence: medium

Hardest to classify were express-07 and express-10: both are genuine, reproducible bad outcomes (data corruption / crash) triggered through Express's own `res.send` dispatch logic, but the proximate cause sits inside Node's own `Buffer.from()`/stream `.end()` type contracts rather than anything Express documents about itself — so it's a judgment call whether the oracle is "in-repo" (Express's branch logic never accounts for non-`Uint8Array` typed views) or "known-external" (Buffer/Node stream API behavior). I leaned toward the external oracle for -07 since the byte-mangling is squarely a Buffer.from() quirk, and toward "implicit" for -10 since the crash itself is unambiguous regardless of which side of the boundary "owns" the bug. express-09 (trailing-dot FQDN) was also borderline since the DNS convention is real but the "expected" Express behavior in that exact edge case isn't spelled out anywhere in the repo, making it more a plausible-but-unconfirmed inference than a hard contradiction.
