# Code review: express @ 9a34acf03cb818ff3f8bc40e44176e277a25cbb9, scope `lib/`

Reviewer: opus (express run 04)

All findings below were reproduced against a copy of the checkout with production dependencies installed (`npm install --omit=dev`) in the work directory.

---

## 1. `res.send()` corrupts or rejects typed-array bodies other than `Uint8Array`/`Buffer`

- **File/line:** `lib/response.js` lines 151-154 (accepts any `ArrayBuffer.isView`) and 166-178 (length/Buffer conversion), 218 (`this.end(chunk, encoding)`)
- **What goes wrong:** `res.send()` explicitly accepts any ArrayBuffer view (`ArrayBuffer.isView(chunk)`, line 151). This covers `Uint16Array`, `Int32Array`, `Float32Array`, `DataView`, and so on. It sets `Content-Type: application/octet-stream` and treats them as binary bodies. The later code then handles them as if they were Buffers or strings:
  - **With ETag enabled (the default, `etag: 'weak'`):** control reaches `chunk = Buffer.from(chunk, encoding)` (line 175). For a non-`Uint8Array` typed array, `Buffer.from(typedArray)` copies element values truncated to bytes instead of the underlying memory. Reproduced: `res.send(new Uint16Array([256, 513, 1]))` responds with `Content-Length: 3` and body `00 01 01`. The correct response is the 6 underlying bytes. For a `DataView`, `Buffer.from(dataView)` gives an empty buffer, so the response is 200 with `Content-Length: 0` and no body. Both are silent data corruption.
  - **With ETag disabled:** `Buffer.byteLength(chunk)` sets `Content-Length` correctly (6). Then `this.end(uint16Array)` throws `ERR_INVALID_ARG_TYPE`, because Node only accepts string, Buffer or Uint8Array. The request errors with a 500 whose body is truncated to the stale Content-Length. Reproduced: `res.send(new Uint16Array([256,513,1]))` gives a 500 with body `ERR Th`.
- **Why it is wrong:** Line 151 deliberately routes all ArrayBuffer views to the binary branch rather than to `res.json`. That branch then sends wrong bytes or throws. The two code paths also disagree on the byte length of the same input: `byteLength` gives 6, `Buffer.from` gives 3.
- **Severity:** medium (silent wrong response bodies for a type the code claims to handle)
- **Fix:** Normalise views to a Buffer over the same memory before computing the length, for example:
  ```js
  } else if (ArrayBuffer.isView(chunk)) {
    if (!Buffer.isBuffer(chunk)) chunk = Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength);
    if (!this.get('Content-Type')) this.type('bin');
  }
  ```

## 2. `res.set('Content-Type', value)` writes the literal header `Content-Type: false` for values mime-types cannot resolve

- **File/line:** `lib/response.js` line 681 (`value = mime.contentType(value)`)
- **What goes wrong:** `mime.contentType()` returns `false` when it cannot resolve its argument. Examples are a bare token with no `/` that is not a known extension (`'custom'`, `'bogus'`) and the empty string. The result is passed straight to `setHeader`, so the response carries `Content-Type: false`. Reproduced: `res.set('Content-Type', 'bogus')` followed by `res.get('Content-Type')` returns `false`, and the client receives `content-type: false`.
- **Why it is wrong:** The doc comment (lines 660-661) says the type is only "expanded to include the charset if not present". It is not supposed to be replaced with a non-media-type. `res.type()` in the same file (lines 509-511) already guards the identical call with `|| 'application/octet-stream'`, which shows the `false` return is known and meant to be handled.
- **Severity:** low
- **Fix:** Fall back to the caller's value, or throw, when `mime.contentType` returns false:
  ```js
  value = mime.contentType(value) || value
  ```

## 3. `res.redirect()` produces "undefined. Redirecting to ..." bodies for status codes without a standard reason phrase

- **File/line:** `lib/response.js` lines 843, 848-849
- **What goes wrong:** The body is built from `statuses.message[status]`. For any valid but unregistered code, that lookup is `undefined`. `res.status()` accepts 100-999, so codes such as 399 or 309 pass. Reproduced: `res.redirect(399, '/x')` sends the body `undefined. Redirecting to /x`, and the HTML variant has `<title>undefined</title>`.
- **Why it is wrong:** `res.sendStatus` in the same file (line 326) handles the same lookup with `statuses.message[statusCode] || String(statusCode)`. `res.redirect` misses that fallback.
- **Severity:** low
- **Fix:** `var message = statuses.message[status] || String(status)`, and use `message` in both body builders.

---

I did not confirm anything else in `lib/application.js`, `lib/request.js`, `lib/utils.js`, `lib/view.js` or `lib/express.js`.

## Files read

- lib/application.js
- lib/express.js
- lib/request.js
- lib/response.js
- lib/utils.js
- lib/view.js
- package.json
- Behaviour of `mime-types.contentType` was checked by running it, not by reading its source.
