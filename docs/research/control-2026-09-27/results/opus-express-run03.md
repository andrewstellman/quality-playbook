# Code review: express `lib/` (commit 9a34acf03cb818ff3f8bc40e44176e277a25cbb9)

Reviewer: opus-express-run03. All four defects below were reproduced against a copy of `lib/` with production dependencies installed (`npm install --omit=dev`) in the work directory.

---

## 1. `res.send()` corrupts or drops non-`Uint8Array` ArrayBuffer views (`Uint16Array`, `Float32Array`, `DataView`, ...)

- **File/line:** `lib/response.js` lines 151-154 (accepts any view) and 166-178 (length and Buffer conversion)
- **What goes wrong:** Line 151 routes any `ArrayBuffer.isView(chunk)` value into the binary path. Line 167 checks only `Buffer.isBuffer`. With the default `etag` setting (`weak`), line 175 then runs `Buffer.from(chunk, encoding)`. For a typed array whose elements are wider than one byte, `Buffer.from(typedArray)` copies element by element and truncates each element to one byte, so it does not copy the underlying bytes. `DataView` has no `.length`, so it produces an empty buffer.
  - Reproduced: `res.send(new Uint16Array([0x4142, 0x4344]))` responds with 2 bytes, `"BD"`, and `Content-Length: 2`. The payload is 4 bytes (`BADC` on little-endian).
  - Reproduced: `res.send(new DataView(new Uint8Array([65,66]).buffer))` responds with 200 and an empty body (`Content-Length: 0`). The data is silently lost.
  - Reproduced: with `app.set('etag', false)`, the same `Uint16Array` takes the `Buffer.byteLength` branch (line 172) and is passed straight to `res.end()`. Node rejects it (`The "chunk" argument must be ... Buffer or Uint8Array. Received an instance of Uint16Array`), so the request fails with a 500.
- **Why it is wrong:** The code deliberately accepts every ArrayBuffer view (line 151; the fallback `Content-Type` is `bin`). The result is silent data corruption or an error, depending on an unrelated setting (`etag`). A body should never be truncated to one byte per element.
- **Severity:** Medium. This is silent data corruption on a public API, but it only affects callers who pass non-byte typed arrays.
- **Suggested fix:** Normalize views to a byte buffer without copying before the length and ETag logic:
  ```js
  } else if (ArrayBuffer.isView(chunk)) {
    if (!Buffer.isBuffer(chunk)) {
      chunk = Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength)
    }
    ...
  ```

## 2. `res.set('Content-Type', <unknown type>)` sets the header to the literal string `"false"`

- **File/line:** `lib/response.js` lines 677-682
- **What goes wrong:** `mime.contentType(value)` returns `false` when it cannot resolve the value, for example a bare extension it does not know such as `'foo'`, or an empty string. The result is not checked, so `setHeader('Content-Type', false)` sends `Content-Type: false`. Reproduced: `res.set('Content-Type', 'foo'); res.end('x')` produced the response header `content-type: false`.
- **Why it is wrong:** The docblock (lines 660-661) says that for Content-Type, `set` only *expands* the value with a charset. It is not meant to replace the value with an invalid token. The sibling method `res.type()` (lines 509-511) handles the same `false` return explicitly by falling back to `application/octet-stream`. `res.set` does not.
- **Severity:** Low.
- **Suggested fix:** `value = mime.contentType(value) || value` (keep the caller's value), or throw a `TypeError` for an unresolvable type.

## 3. `req.acceptsCharsets()` does not support the comma-delimited list its documentation promises

- **File/line:** `lib/request.js` lines 146-174
- **What goes wrong:** The JSDoc says the argument may be "A comma-delimited list of charsets (e.g., `"utf-8, iso-8859-1"`)". Its example says `req.acceptsCharsets('utf-8, utf-16')` returns `"utf-8"`. The implementation passes the string unchanged to `accepts().charsets()`, which treats it as a single charset named `"utf-8, utf-16"`. Reproduced: with `Accept-Charset: utf-8, iso-8859-1`, `req.acceptsCharsets('utf-8, utf-16')` returns `false`, not `"utf-8"`.
- **Why it is wrong:** The behavior directly contradicts the function's own documentation and example.
- **Severity:** Low. The caller gets a false "not acceptable" result and may send a 406.
- **Suggested fix:** Split string arguments on commas before delegating, for example: `charsets.flatMap(c => typeof c === 'string' ? c.split(',').map(s => s.trim()).filter(Boolean) : c)`. Alternatively, correct the documentation.

## 4. `res.sendFile()` writes into the caller's `options` object

- **File/line:** `lib/response.js` line 404 (`opts.etag = this.app.enabled('etag');`)
- **What goes wrong:** `opts` is the caller's own `options` object (line 380), so each call overwrites the caller's `etag` property. An explicit `{ etag: false }` passed by the user is silently ignored in favor of the app setting. If the caller reuses a shared options object, it keeps the app value afterwards.
- **Why it is wrong:** The docblock (line 350) says "Other options are passed along to `send`". `etag` is a documented `send` option, but the caller's value is discarded. `res.download()` avoids mutating the caller's object by using `Object.create(opts)` (line 476), which shows that the codebase intends not to mutate caller options.
- **Severity:** Low.
- **Suggested fix:** `opts = { ...opts }; if (opts.etag === undefined) opts.etag = this.app.enabled('etag');`. If the app setting is meant to override the caller's value, copying the object before writing still avoids the mutation.

---

## Checked and not reported

These were checked and either behave correctly or I was not confident they are defects:
- `utils.acceptParams` loop termination and handling of parameters without a value.
- `req.host` / `req.hostname` IPv6 handling.
- The trust-proxy inheritance flag on mount.
- The `sendfile` finish/abort state machine.
- `res.download` argument shuffling.
- `res.redirect` with a string status: it throws after the deprecation warning, but that is consistent with the strict `res.status` in v5.
- JSONP callback sanitization.
- `View` lookup and async normalization.

## Files read

- `lib/application.js`
- `lib/express.js`
- `lib/request.js`
- `lib/response.js`
- `lib/utils.js`
- `lib/view.js`
- `package.json`
- `History.md` (grep only)
- test directory listing, plus a grep of `test/res.send.js` for typed-array tests

Scratch scripts (`t1.js`, `t2.js`) were run in the work directory against a copy of `lib/`.
