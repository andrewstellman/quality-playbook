# Code review: express @ 9a34acf (scope: `lib/`)

Reviewer: opus (control run). Checkout `/tmp/control/express`, read-only. For testing, `lib/`, `index.js` and `package.json` were copied to `/tmp/control-work/opus-express/`, `npm install --omit=dev` was run there, and small Node scripts (`t1.js`, `t2.js`) sent real HTTP requests to check each finding below. Every finding was reproduced.

---

## 1. `res.send()` corrupts or rejects non-`Uint8Array` typed arrays and `DataView`

- **File/line:** `lib/response.js:151-178` (the `ArrayBuffer.isView(chunk)` branch, then the length/ETag block)
- **What goes wrong:** `res.send()` accepts any `ArrayBuffer` view as a binary body (`ArrayBuffer.isView(chunk)`, line 151). After that, the code treats the chunk as if it were a Buffer or a string:
  - If ETag generation is on (the default `etag: 'weak'`), `Buffer.from(chunk, encoding)` runs at line 175. For a `Uint16Array`, `Float32Array` and similar types, `Buffer.from(typedArray)` copies **element values truncated to bytes**, not the underlying bytes. Observed: `res.send(new Uint16Array([0x4142, 0x4344]))` returns `Content-Length: 2` and the body `42 44` ("BD"). The correct result is 4 bytes, `42 41 44 43`. For a `DataView`, `chunk.length` is `undefined`, so the result is an empty body with `Content-Length: 0`. The client gets a truncated or corrupted payload with a 200 status and a matching (wrong) ETag.
  - If ETag is disabled (`app.set('etag', false)`), line 172 computes `Buffer.byteLength` correctly. However, `this.end(chunk)` then throws `ERR_INVALID_ARG_TYPE` ("must be of type string or an instance of Buffer or Uint8Array. Received an instance of Uint16Array"), and the request ends in a 500.
- **Why it is wrong:** the branch at line 151 accepts every ArrayBuffer view as a binary body and sets `application/octet-stream`. So the intent is to send the view's bytes. `Buffer.from(TypedArray)` has different semantics from `Buffer.from(view.buffer, view.byteOffset, view.byteLength)`. Only `Buffer` and `Uint8Array` behave correctly today.
- **Severity:** medium. The data is corrupted silently, with a success status.
- **Suggested fix:** normalize every non-Buffer view to a Buffer over the same memory before the length and ETag logic:
  ```js
  } else if (ArrayBuffer.isView(chunk)) {
    if (!Buffer.isBuffer(chunk)) chunk = Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength);
    if (!this.get('Content-Type')) this.type('bin');
  }
  ```

## 2. `res.set('Content-Type', <unknown extension>)` sends a literal `Content-Type: false` header

- **File/line:** `lib/response.js:677-684`
- **What goes wrong:** for a Content-Type field, the value goes through `mime.contentType(value)`. If the value has no `/`, `mime-types` treats it as an extension. For an unknown extension it returns `false`, and `this.setHeader(field, false)` stores that boolean. Observed:
  - `res.set('Content-Type', 'foo'); res.end('x')` sends the header `content-type: false`.
  - If `res.send('x')` follows, `send()` sees a non-string Content-Type (line 140) and silently replaces it with `text/html`.
- **Why it is wrong:** the doc comment (lines 660-661) says the type is only "expanded to include the charset if not present". It says nothing about replacing it with a boolean. `res.type()` (lines 509-511) guards the same call with `|| 'application/octet-stream'`, which shows the intended fallback.
- **Severity:** low
- **Suggested fix:** `value = mime.contentType(value) || value;` (or fall back to `'application/octet-stream'`, as `res.type()` does).

## 3. `req.subdomains` returns garbage for bracketed IPv6 hosts that contain dots, and for fully qualified hostnames with a trailing dot

- **File/line:** `lib/request.js:383-394`
- **What goes wrong:**
  - **Bracketed IPv6 hosts:** `req.hostname` keeps the brackets for IPv6 literals (lines 449-457 deliberately skip past `]`). `isIP('[::ffff:127.0.0.1]')` returns 0, so the address is split on `.`. With `Host: [::ffff:127.0.0.1]:80`, `req.subdomains` returns `["0","[::ffff:127"]`. The expected result is `[]`, which is what an IP hostname produces through the `[hostname]` branch.
  - **Trailing dot:** a fully qualified hostname with a trailing dot is valid in a Host header. With `Host: tobi.ferrets.example.com.`, the split creates an empty last label, so the result is `["example","ferrets","tobi"]` instead of `["ferrets","tobi"]`.
- **Why it is wrong:** the doc comment (lines 369-380) defines subdomains as the labels before the app's domain, which is "the last two parts of the host". The code explicitly means to return no subdomains for IP addresses (the `isIP` check).
- **Severity:** low
- **Suggested fix:** strip the brackets before the IP check, e.g. `var h = hostname[0] === '[' ? hostname.slice(1, -1) : hostname; if (isIP(h)) return [];`. Also strip a single trailing `.` before splitting.

---

## Considered and not reported

- `res.redirect(url, status)` (the old argument order) prints two deprecation warnings and then throws inside `res.status()`, after setting `Location`. Express 5 deliberately removed that signature, so this is intended.
- `res.sendFile` writes `opts.etag` into the caller's options object, and `res.render` writes `opts._locals` into it. These are side effects on caller objects, but the behaviour is long-standing and documented by use.
- The view cache in `app.render` is keyed only by `name`. That is the documented, long-standing behaviour.

## Files read

- `lib/application.js`
- `lib/express.js`
- `lib/request.js`
- `lib/response.js`
- `lib/utils.js`
- `lib/view.js`
- `package.json`

Dependency behaviour (`mime-types`, `Buffer.from`) was checked by running code, not by reading the dependency source.
