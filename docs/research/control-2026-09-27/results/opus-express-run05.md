# Code review: express `lib/` (pinned 9a34acf03cb818ff3f8bc40e44176e277a25cbb9)

Reviewer: opus-express-run05

I read all six files in `lib/` end to end. I copied `lib/`, `index.js` and `package.json` into the work directory, installed the production dependencies there, and ran small HTTP snippets to check each suspicion. Every defect below was reproduced. The work directory was deleted afterwards.

---

## Defect 1: `res.send()` corrupts or drops non-`Uint8Array` ArrayBuffer views (TypedArrays and DataView)

- **File/line:** `lib/response.js:151-154` (the branch that accepts the view) and `lib/response.js:166-178` (length and body handling)
- **What goes wrong:** `res.send` sends any `ArrayBuffer.isView(chunk)` value as a binary body (`this.type('bin')`). That test also accepts `Uint16Array`, `Int32Array`, `Float64Array` and `DataView`. The code after it only works for Buffers or Uint8Arrays:
  - With ETag enabled (the default `'weak'`), the chunk goes through `Buffer.from(chunk, encoding)` (line 175). For a non-byte TypedArray, `Buffer.from` copies **element by element and truncates each element to 0-255**. The body and `Content-Length` are wrong. Reproduced: `res.send(new Uint16Array([0x4142, 0x4344]))` produced `Content-Length: 2` and body `42 44`. The expected result is 4 bytes, `42 41 44 43`.
  - For a `DataView`, `chunk.length` is `undefined`, so the code falls into the same `Buffer.from` branch. That yields an empty buffer: the response went out with `Content-Length: 0` and an empty body, and the data was silently lost.
  - With ETag disabled and a small view, `len` comes from `Buffer.byteLength` (the correct number of bytes). Then `this.end(chunk)` is called with a `Uint16Array`, which Node rejects with `ERR_INVALID_ARG_TYPE`. Reproduced: HTTP 500 with the message 'The "chunk" argument must be of type string or an instance of Buffer or Uint8Array'.
- **Why it is wrong:** the `ArrayBuffer.isView` check says any view is accepted as a binary body and gets `application/octet-stream`. The later code does not keep that promise: output changes with an unrelated setting (`etag`), and it is either silently wrong or throws.
- **Severity:** medium. The response body is silently corrupted, with no error.
- **Suggested fix:** normalise every view to a byte view of the same memory before the length and ETag logic:
  ```js
  } else if (ArrayBuffer.isView(chunk)) {
    if (!Buffer.isBuffer(chunk)) {
      chunk = Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength)
    }
    if (!this.get('Content-Type')) this.type('bin')
  }
  ```

## Defect 2: `res.set('Content-Type', value)` writes the literal header `false` when `mime.contentType()` cannot resolve the value

- **File/line:** `lib/response.js:677-682`
- **What goes wrong:** every Content-Type value goes through `value = mime.contentType(value)`. `mime-types`' `contentType()` returns `false` when it cannot resolve its input. That happens for any value without a `/` that is not a known extension (for example `res.set('Content-Type', 'bogus')`), and for other strings it cannot parse. The boolean `false` is then passed to `setHeader`. Reproduced: `res.set('Content-Type','bogus')` makes `res.get('Content-Type')` return the boolean `false`, and the header on the wire is `Content-Type: false`.

  There is a second effect. If `res.send('...')` runs afterwards, `typeof type === 'string'` at line 140 is now false. `send` then calls `this.type('html')` and silently replaces the caller's explicit content type with `text/html` (reproduced).
- **Why it is wrong:** the doc comment (lines 660-661) says the Content-Type value is only "expanded to include the charset if not present using `mime.contentType()`". It should never replace the value with an unrelated boolean. `res.type()` (line 510) guards the same call with `|| 'application/octet-stream'`; `res.set` has no fallback.
- **Severity:** low to medium. The header is invalid and caller intent is lost, but only for unusual or unrecognised type strings.
- **Suggested fix:** keep the original value when `contentType` fails:
  ```js
  value = mime.contentType(value) || value
  ```

---

## Areas checked where I found no defect I am confident in

- `request.js`: `req.get`, `range`, `query`, `protocol` / `host` / `hostname` with trust proxy, `ips`, `subdomains`, `fresh`.
- `response.js`: `jsonp`, `sendFile`, `download` argument shuffling, `format`, `redirect`, `cookie` / `clearCookie`, `append`, `links`.
- `application.js`: `use` / mount prototype restoration, settings inheritance, `render` / cache, `listen`.
- `utils.js`: `acceptParams` loop termination, `compileTrust`, `compileETag`, `compileQueryParser`.
- `view.js`: lookup and resolve.

## Files read

- `/tmp/control/express/lib/application.js`
- `/tmp/control/express/lib/express.js`
- `/tmp/control/express/lib/request.js`
- `/tmp/control/express/lib/response.js`
- `/tmp/control/express/lib/utils.js`
- `/tmp/control/express/lib/view.js`
- `/tmp/control/express/package.json`
