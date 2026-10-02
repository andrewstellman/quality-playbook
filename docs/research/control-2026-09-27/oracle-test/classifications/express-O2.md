# express, classifier O2 (Claude Opus), blind

### express-01
Oracle: The guard `typeof callback === 'string' && callback.length !== 0` (lib/response.js:~283) shows the intent that an empty callback falls back to plain JSON. Sanitisation runs after that check, so `!!!` becomes empty and the code emits `typeof  === 'function' && (...)`, which is a JavaScript syntax error served as `text/javascript`.
Type: in-repo
Confidence: high

### express-02
Oracle: The sibling `res.type` (lib/response.js:508-510) handles the same `mime.contentType()` → `false` case with `|| 'application/octet-stream'`. The `res.set` docstring says the type "is expanded to include the charset", not replaced. Sending the literal header `Content-Type: false` is also plainly invalid under HTTP (RFC 9110 media-type syntax).
Type: in-repo
Confidence: high

### express-03
Oracle: History.md 5.1.0 lists "Add support for ETag option in `res.sendFile()`". The sendFile docstring says "Other options are passed along to `send`". The unconditional `opts.etag = this.app.enabled('etag')` (lib/response.js:404) throws away the caller's option, so the documented feature does nothing.
Type: in-repo
Confidence: high

### express-04
Oracle: `res.status` accepts any integer from 100 to 999, and `statuses.message[399]` is undefined, so the string `undefined` ends up in the body. Nothing in the repo says what text an unregistered status should produce. I believe a fallback is expected, but I can't point to a spec for it.
Type: none
Confidence: low

### express-05
Oracle: The sibling `res.download` (lib/response.js:~476) deliberately does `opts = Object.create(opts)` before handing options to sendFile, which shows the convention of not mutating the caller's options. `res.cookie` does the same with `{ ...options }`. `res.sendFile` writes `opts.etag` straight into the caller's object.
Type: in-repo
Confidence: medium

### express-06
Oracle: The `req.acceptsCharsets` docstring (lib/request.js:~145-165) says a comma-delimited list is accepted. It gives the example `// Accept-Charset: utf-8, iso-8859-1` → `req.acceptsCharsets('utf-8, utf-16'); // => "utf-8"`. The observed result is `false`.
Type: in-repo
Confidence: high

### express-07
Oracle: The `ArrayBuffer.isView(chunk)` branch in `res.send` (with `this.type('bin')`) shows the intent to send a view's bytes as a binary body. History.md 5.1.0 only claims Uint8Array support. Node's `Buffer.from(typedArray)` copies element values truncated to 0-255, and `Buffer.from(DataView)` gives an empty buffer. The result is silently truncated or empty bodies. The truncation itself comes from Node's Buffer contract (known-external).
Type: in-repo
Confidence: medium

### express-08
Oracle: The `!isIP(hostname) ? split : [hostname]` branch in `req.subdomains` (lib/request.js:389-391) shows that IP hosts are not meant to be split. test/req.subdomains.js:135-136 expects `[::1]` to come back whole. Because `req.hostname` keeps the brackets (test/req.hostname.js:57), `isIP` returns 0 and an IPv4-mapped IPv6 literal gets split on `.`.
Type: in-repo
Confidence: high

### express-09
Oracle: RFC 1034 §3.1 says a trailing dot marks an absolute FQDN, so `tobi.ferrets.example.com.` is the same host as `tobi.ferrets.example.com`. The subdomains docstring says the latter yields `["ferrets", "tobi"]`. The empty label from the trailing dot shifts the offset by one.
Type: known-external
Confidence: medium

### express-10
Oracle: `res.send` throws an uncaught `ERR_INVALID_ARG_TYPE` from `this.end(chunk)` and the request becomes a 500. This happens only when etag is disabled; with etag on, the same input is converted to a Buffer (see express-07). The isView branch accepts input that this path then can't handle.
Type: implicit
Confidence: high

### express-11
Oracle: RFC 6265 §5.3 says Max-Age takes precedence over Expires, and §5.2.2 says a delta-seconds value ≤ 0 means expire immediately. `Math.floor(500/1000) = 0` turns a live cookie into a deletion. The `res.cookie` docstring presents `maxAge` as equivalent to `expires` ("same as above"), which in-repo contradicts the result.
Type: known-external
Confidence: medium

The hardest to classify were express-04, express-07 and express-11. For express-04, printing "undefined" is clearly unintended, but the input is a non-standard status code, and neither the repo nor HTTP says what body text a redirect with an unregistered status should have. So there's no real oracle beyond "this looks wrong". For express-07, the in-repo evidence (the isView/`bin` branch) shows intent, but proving the bytes are wrong depends on Node's `Buffer.from(typedArray)` semantics, and History.md only promises Uint8Array. That makes it partly in-repo, partly known-external, and arguably out of scope. For express-11, the RFC is clear that Max-Age=0 deletes the cookie, but whether flooring a sub-second maxAge is a defect or an acceptable edge depends on how strictly you read the docstring's "same as above" equivalence.
