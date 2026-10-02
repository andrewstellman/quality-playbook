# Code review: express `lib/` (commit 9a34acf03cb818ff3f8bc40e44176e277a25cbb9)

Reviewer: opus-express-run10

## Defect 1: `res.send()` corrupts non-byte TypedArray / DataView bodies

- **File/line:** `lib/response.js` 151-154 (accepts any `ArrayBuffer.isView(chunk)`), 166-178 (length/Buffer conversion)
- **What goes wrong:** `res.send()` accepts any ArrayBuffer view as a binary body (line 151). But with the default `etag` setting (`'weak'`, so `generateETag` is true), line 175 runs `Buffer.from(chunk, encoding)`. For a view that is not a `Uint8Array`, `Buffer.from(typedArray)` copies *element values*, truncated to 0-255. It does not copy the underlying bytes. A `DataView` has no `.length`, so it becomes an empty buffer.
  Reproduced against this checkout, with default settings:
  - `res.send(new Uint16Array([0x0102, 0x0304]))` gives `Content-Length: 2`, body `02 04`. The expected result is 4 bytes, `02 01 04 03`.
  - `res.send(new Float32Array([1.5]))` gives `Content-Length: 1`, body `01`. The expected result is 4 bytes.
  - `res.send(new DataView(new ArrayBuffer(4)))` gives `Content-Length: 0` and an empty body.
  The ETag is also computed over the corrupted bytes.
- **Why it is wrong:** The code explicitly routes every ArrayBuffer view down the binary path, with Content-Type `bin` (line 151-153). This contrasts with plain objects, which go to `json()`. That tells us the bytes of the view are meant to be sent. Instead the client silently gets truncated, wrong data.
- **Severity:** medium. This is silent data corruption for a supported input type.
- **Fix:** Normalise views to a byte-accurate Buffer before computing the length, e.g.
  ```js
  } else if (ArrayBuffer.isView(chunk)) {
    if (!Buffer.isBuffer(chunk)) chunk = Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength);
    ...
  ```

## Defect 2: `res.set('Content-Type', <unknown bare type>)` sets the header to the literal string `"false"`

- **File/line:** `lib/response.js` 677-682
- **What goes wrong:** For Content-Type, the value is replaced by `mime.contentType(value)`. That function returns `false` when it cannot resolve the value, for example a bare token with no `/` that is not a known extension. The code does not check for this, so `setHeader('Content-Type', false)` sends `Content-Type: false`. This was reproduced with `res.set('Content-Type', 'bogus')`.
- **Why it is wrong:** The doc comment (lines 660-661) says the type is only "expanded to include the charset if not present". It does not say the value can be replaced with a boolean. By contrast, `res.type()` (line 509-511) guards the same call with `|| 'application/octet-stream'`.
- **Severity:** low
- **Fix:** Use `value = mime.contentType(value) || value`.

## Defect 3: `res.redirect()` produces "undefined. Redirecting to ..." bodies for non-standard status codes

- **File/line:** `lib/response.js` 843, 848-849
- **What goes wrong:** The body is built from `statuses.message[status]`. For a valid status that has no registered message, this is `undefined`. For example, `res.redirect(399, '/x')` or a custom 3xx code both produce the text `undefined. Redirecting to /x`, and the HTML version has `<title>undefined</title>`.
- **Why it is wrong:** `res.sendStatus()` in the same file (line 326) handles exactly this case with `statuses.message[statusCode] || String(statusCode)`. `res.status()` accepts any integer from 100 to 999.
- **Severity:** low
- **Fix:** Compute `var msg = statuses.message[status] || String(status)` once and use it in both bodies.

## Other areas checked, nothing confidently wrong found

- `acceptParams`/`normalizeType`, `compileETag`/`compileQueryParser`/`compileTrust`, `setCharset` (utils.js)
- The request getters in request.js: protocol, host, hostname (including IPv6), subdomains, ips, fresh, and query
- `app.use`/mount prototype restore, `app.set` trust-proxy inheritance, `app.render` cache, and `View` lookup/resolve
- `res.jsonp` callback sanitisation, `res.cookie`/`clearCookie`, `res.download` argument juggling, `res.format`, and `sendfile` stream event handling

## Files read

- lib/application.js
- lib/express.js
- lib/request.js
- lib/response.js
- lib/utils.js
- lib/view.js
- package.json (dependency versions)

I copied lib/, index.js and package.json into the work directory and ran a small script there to reproduce defects 1 and 2.
