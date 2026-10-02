# Code review: express `lib/` (pinned 9a34acf03cb818ff3f8bc40e44176e277a25cbb9)

Reviewer: opus, express run 09. Scope: `lib/` in `/tmp/control/express`.

I copied `lib/`, `index.js` and `package.json` into a scratch directory, ran `npm install --omit=dev`, and reproduced both findings below against a live server before reporting them.

## Defect 1: `res.send()` corrupts or rejects every ArrayBuffer view that is not a `Uint8Array`/`Buffer`

- **File/line:** `lib/response.js:151-178` (the `ArrayBuffer.isView(chunk)` branch at 151, then the length/conversion logic at 166-178, then `this.end(chunk, encoding)` at 218)
- **What goes wrong:** Line 151 accepts any ArrayBuffer view (`Uint16Array`, `Int32Array`, `Float64Array`, `DataView`, ...) as a binary body. The code after that assumes the chunk is byte-oriented:
  - **ETag enabled (the default, `etag: 'weak'`):** line 175 runs `Buffer.from(chunk, encoding)`. When `chunk` is a TypedArray, `Buffer.from` treats it as an array of numbers and truncates each *element* to one byte. It does not copy the underlying bytes. `len` becomes the element count.
    - Reproduced: `res.send(new Uint16Array([0x0102, 0x0304]))` returns `Content-Length: 2`, body `02 04` (should be 4 bytes, `02 01 04 03`).
    - `res.send(new Float64Array([1.5]))` returns 1 byte, `01` (should be 8 bytes).
    - `res.send(new DataView(...4 bytes...))` returns `Content-Length: 0` and an empty body.
  - **ETag disabled:**
    - `Uint16Array` etc.: line 172 computes `Buffer.byteLength(chunk)`, which is the correct byte count. But line 218 passes the raw TypedArray to `res.end()`, and Node rejects it: `TypeError [ERR_INVALID_ARG_TYPE]: The "chunk" argument must be of type string or an instance of Buffer or Uint8Array. Received an instance of Uint16Array`. This error is thrown after the headers have already been set.
    - `DataView`: `chunk.length` is `undefined`, so `undefined < 1000` is false. The code then falls through to `Buffer.from(DataView)`, which gives an empty buffer.
- **Why it is wrong:** The branch deliberately admits all views through `ArrayBuffer.isView` and gives them the `bin` (octet-stream) content type. So the intent is to send the view's bytes. History.md line 69 says "Add support for `Uint8Array` in `res.send()`". The only test, `test/res.send.js:207`, covers `Uint8Array` alone, so this breakage is untested. The result is silent data corruption (wrong bytes with a matching wrong Content-Length) or a thrown exception, depending on the `etag` setting.
- **Severity:** medium. Binary responses are silently corrupted under the default configuration, and no error is raised.
- **Suggested fix:** In the `ArrayBuffer.isView` branch, normalise to a Buffer that shares the view's memory:
  ```js
  } else if (ArrayBuffer.isView(chunk)) {
    if (!Buffer.isBuffer(chunk)) {
      chunk = Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength);
    }
    if (!this.get('Content-Type')) this.type('bin');
  }
  ```
  Alternatively, restrict the check to `chunk instanceof Uint8Array` and let other views fall through to `json()`.

## Defect 2: `req.subdomains` returns bogus subdomains for bracketed IPv6 hosts that contain dots

- **File/line:** `lib/request.js:383-394` (`isIP(hostname)` at 389), combined with `hostname` at 444-458
- **What goes wrong:** The `hostname` getter keeps the square brackets on IPv6 literals (e.g. `Host: [::ffff:1.2.3.4]:80` gives hostname `[::ffff:1.2.3.4]`). `net.isIP('[::ffff:1.2.3.4]')` returns `0`, so the IP guard at line 389 never matches an IPv6 host. The host is then split on `.` as if it were a domain name.
  - Reproduced: a request with `Host: [::ffff:1.2.3.4]:80` gives `req.subdomains === ["2", "[::ffff:1"]`.
- **Why it is wrong:** The `!isIP(hostname) ? ... : [hostname]` guard exists to stop IP addresses being split into "subdomains". The docblock describes subdomains as "the dot-separated parts of the host before the main domain". An IP literal has no subdomains, and IPv4 literals are handled correctly. IPv4-mapped/embedded IPv6 literals escape the guard only because of the brackets.
- **Severity:** low
- **Suggested fix:** Strip the brackets before the IP check:
  ```js
  var bare = hostname[0] === '[' && hostname[hostname.length - 1] === ']'
    ? hostname.slice(1, -1) : hostname;
  var subdomains = !isIP(bare) ? hostname.split('.').reverse() : [hostname];
  ```

## Nothing else found with confidence

I checked the rest of `lib/` and found no other defects I am confident in. That covers application settings/mount inheritance, `app.use`/`render`/`listen`, view lookup/render, the utils (`acceptParams`, `compileTrust`/`ETag`/`QueryParser`, `setCharset`), request getters (`protocol`, `host`, `hostname`, `ips`, `fresh`, `query`), and the response helpers (`json`/`jsonp`, `sendFile`/`download`, `format`, `cookie`/`clearCookie`, `redirect`, `append`/`set`).

## Files read

- `lib/application.js`
- `lib/express.js`
- `lib/request.js`
- `lib/response.js`
- `lib/utils.js`
- `lib/view.js`
- `package.json`
- `test/res.send.js` and `History.md` (grep only, for typed-array coverage and the changelog entry)
