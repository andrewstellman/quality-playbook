# Code review: express `lib/` (pinned 9a34acf03cb818ff3f8bc40e44176e277a25cbb9)

Reviewer: opus-express-run06

Method: read every file in `lib/`, compared behaviour against the in-code documentation and History.md, copied the checkout to a work directory, ran `npm install` and the full test suite (1261 passing), then wrote small supertest scripts to confirm each suspicion below. Both findings were reproduced.

---

## Defect 1: `res.send()` corrupts or drops the body for ArrayBuffer views other than `Uint8Array`/`Buffer`

- **File/line:** `lib/response.js` 151-154 (type branch), 166-178 (length/buffer conversion)
- **What goes wrong:** the branch is gated on `ArrayBuffer.isView(chunk)`, which is true for every typed array and for `DataView`. The code after that assumes a byte-per-element array. With the default settings (`etag` = `weak`, so `generateETag` is true) the chunk goes through `Buffer.from(chunk, encoding)`:
  - `Uint16Array`/`Int32Array`/`Float64Array` etc. go through Node's array-like path, so each element is **truncated to one byte**. `res.send(new Uint16Array([0x4142, 0x4344]))` responds with `Content-Length: 2`, body `"BD"`. The 4 real bytes are lost, and there is no error.
  - `DataView` has no `.length`, so `Buffer.from(dataView)` returns an **empty buffer**. `res.send(new DataView(buf))` responds 200 with `Content-Length: 0` and an empty body. This also happens with ETag disabled: `chunk.length < 1000` is `undefined < 1000`, which is false, so the code takes the same `Buffer.from` path.
  - Reproduced: `/u16 -> 200 application/octet-stream len=2 "BD"`, `/dv -> 200 application/octet-stream len=0 ""`.
- **Why it's wrong:** the ETag/length code gives a `Buffer` or `Uint8Array` the right byte length, but it isn't byte-correct for any other kind of view. The branch still sends these views down the binary path: it sets `Content-Type: application/octet-stream`, which says "raw bytes". History.md 5.1.0 describes the added support as "`Uint8Array` in `res.send()`", and `ArrayBuffer.isView` is a much wider check than that. The result is silent data corruption.
- **Severity:** medium (silent data loss or corruption and a success status; needs a non-Uint8 view to trigger)
- **Suggested fix:** normalise any view to bytes before the length/ETag logic, for example:
  ```js
  } else if (ArrayBuffer.isView(chunk)) {
    if (!Buffer.isBuffer(chunk)) {
      chunk = Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength)
    }
    if (!this.get('Content-Type')) this.type('bin')
  }
  ```
  Alternatively, narrow the check to `chunk instanceof Uint8Array` and route other views elsewhere or reject them.

## Defect 2: `res.set('Content-Type', <unrecognised value>)` writes the literal header `Content-Type: false`

- **File/line:** `lib/response.js` 677-682
- **What goes wrong:** `value = mime.contentType(value)` is used without a fallback. `mime-types`' `contentType()` returns `false` when it can't resolve its input (for example a bare word with no known extension mapping, such as `res.set('Content-Type', 'bogus')`). `String` coercion then happens in `setHeader`, so the response carries `Content-Type: false`. Reproduced: `res.set('Content-Type','bogus'); res.get('Content-Type')` gives `"false"`, and the client receives `content-type: false`.
- **Why it's wrong:** the JSDoc (lines 660-661) says the value is only "expanded to include the charset if not present". It should never be replaced by an invalid token. The sibling `res.type()` (lines 509-511) guards the same call with `|| 'application/octet-stream'`, which shows the library knows about the `false` return.
- **Severity:** low (needs caller input that mime-types doesn't recognise, but it produces an invalid header and there's no error)
- **Suggested fix:** `value = mime.contentType(value) || value`. This keeps the caller's value when no charset expansion is possible. An alternative is to throw a `TypeError` for invalid input.

---

No other defects I'm confident in. The remaining logic in `application.js`, `request.js`, `utils.js`, `view.js` and `express.js` matched its documentation in my reading and in the passing test suite.

## Files read

- lib/application.js
- lib/express.js
- lib/request.js
- lib/response.js
- lib/utils.js
- lib/view.js
- package.json
- History.md (top section)
- test/req.fresh.js, test/res.sendFile.js (grep only, for QUERY/etag context)
