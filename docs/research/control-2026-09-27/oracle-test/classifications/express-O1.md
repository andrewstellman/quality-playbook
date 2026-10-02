# express, classifier O1 (Claude Opus), blind

### express-01
Oracle: The guard at lib/response.js:287, `typeof callback === 'string' && callback.length !== 0`, shows the author meant an empty callback to fall through to the plain-JSON path (test/res.jsonp.js:130 "should not override previous Content-Types with no callback"). The guard runs before the sanitising `replace`, so `!!!` passes it, gets stripped to `''`, and produces `typeof  === 'function'`, which is a JavaScript syntax error.
Type: in-repo
Confidence: high

### express-02
Oracle: The sibling `res.type` at lib/response.js:510 handles the same `mime.contentType()` miss with `mime.contentType(type) || 'application/octet-stream'`, and its docstring says "When no mapping is found ... the type is set to 'application/octet-stream'". `res.set` has no fallback, so it stores the boolean `false`, which contradicts `res.get`'s `@return {String}`. `res.send` then silently replaces it with text/html.
Type: in-repo
Confidence: high

### express-03
Oracle: The sendFile docstring says "Other options are passed along to `send`" (lib/response.js:350), and History.md 5.1.0 says "Add support for ETag option in `res.sendFile()`". Line 404 overwrites the caller's `etag` option with the app setting without condition, so the option never gets through.
Type: in-repo
Confidence: medium

### express-04
Oracle: The sibling `res.sendStatus` at lib/response.js:326 guards the same lookup with `statuses.message[statusCode] || String(statusCode)`. `res.redirect` uses `statuses.message[status]` bare at lines 843/848-849, so an unnamed code prints the literal text "undefined".
Type: in-repo
Confidence: high

### express-05
Oracle: Sibling methods copy the caller's options instead of writing to them. `res.cookie` does `{ ...options }` and has a test "should not mutate the options object" (test/res.cookie.js:128). `res.download` does `Object.create(opts)` (lib/response.js:~470). `res.sendFile` assigns `opts.etag` straight onto the caller's object.
Type: in-repo
Confidence: medium

### express-06
Oracle: The `req.acceptsCharsets` docstring (lib/request.js:~160-168) says a comma-delimited list is accepted, and gives this exact example: `// Accept-Charset: utf-8, iso-8859-1` → `req.acceptsCharsets('utf-8, utf-16'); // => "utf-8"`. The code returns `false`.
Type: in-repo
Confidence: high

### express-07
Oracle: This is Node's `Buffer.from` contract. `Buffer.from(typedArray)` copies element values truncated to 0-255 instead of the underlying bytes, and a DataView is not array-like, so it yields an empty buffer. Line 175 therefore corrupts or drops any ArrayBuffer view that isn't a Uint8Array, even though line 151 lets them in via `ArrayBuffer.isView`. In the same function, the no-ETag path (`Buffer.byteLength`) counts 6 bytes for similar input, which disagrees with this one.
Type: known-external
Confidence: medium (History.md only advertises Uint8Array support)

### express-08
Oracle: test/req.subdomains.js:125 "should return an array with the whole IPv6" and :35 "should work with IPv6 address" show that IPv6 hosts should not be split into subdomains. The `hostname` getter keeps the brackets, so `isIP()` fails at lib/request.js:389. The existing tests only pass because `[::1]` contains no dot.
Type: in-repo
Confidence: high

### express-09
Oracle: In DNS, a trailing dot marks an absolute name, so `tobi.ferrets.example.com.` is the same host as the undotted form (RFC 1034 §3.1). The docstring example (lib/request.js:~374) gives `["ferrets","tobi"]` for that host. The empty label from the trailing dot uses up one slot of the offset.
Type: known-external
Confidence: medium

### express-10
Oracle: This is an uncaught `ERR_INVALID_ARG_TYPE` thrown by `res.end` for input that passed Express's own `ArrayBuffer.isView` check (lib/response.js:151), and it becomes a 500. Before the throw, Content-Length has already been set from `Buffer.byteLength` without converting the chunk.
Type: implicit
Confidence: high

### express-11
Oracle: RFC 6265 §5.2.2 says Max-Age ≤ 0 means the cookie expires immediately, and Max-Age takes precedence over Expires. `Math.floor(500/1000)` = 0 therefore deletes the cookie, while the Expires attribute says it lives 0.5 s. The docstring says "`maxAge` in milliseconds, converted to `expires`", which the Max-Age attribute contradicts for sub-second values.
Type: known-external
Confidence: medium

Hardest to classify:
- **express-07:** the corruption itself comes from a Node `Buffer.from` contract (external). But the repo also contains its own oracle: two code paths in the same function disagree about the byte count. And it's unclear whether non-Uint8Array views were ever meant to be supported, since History.md mentions only Uint8Array, which is why confidence is only medium.
- **express-03:** the in-repo evidence ("Other options are passed along to send", the History entry) could also be read as "the ETag option means the app setting", so whether this is a bug depends on intent I can't pin down.
- **express-09:** a trailing-dot host is a real edge case, and the oracle is DNS semantics rather than anything Express documents.
- **express-11:** it rests on RFC 6265 precedence rules, and a sub-second maxAge is an unusual input.
