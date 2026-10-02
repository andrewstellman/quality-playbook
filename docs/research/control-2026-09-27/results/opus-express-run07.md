# Code review: express `lib/` (pinned 9a34acf03cb818ff3f8bc40e44176e277a25cbb9)

Reviewer: opus-express-run07

## Summary

I read all six files in `lib/` and checked the suspicious spots by running snippets against a local copy. The project's own suite passes (1261 passing, after `npm install` in the work copy). I found one defect I'm confident in. Everything else I looked at either matches the documented behaviour or is too speculative to report.

## Defect 1: `res.send()` corrupts or drops the body for `ArrayBuffer` views other than `Uint8Array`/`Buffer`

- **File/line:** `lib/response.js` lines 151-154 (the branch that accepts views) and lines 166-178 (length and Buffer conversion), plus line 218 (`this.end(chunk, encoding)`).
- **What goes wrong:** Line 151 accepts any `ArrayBuffer.isView(chunk)` as a binary body. That covers every TypedArray and `DataView`. After that, the code treats the value as if it were a `Buffer`/`Uint8Array`:
  - **Default settings (ETag enabled, `etag fn` is a function):** control reaches `chunk = Buffer.from(chunk, encoding)` (line 175). With a non-`Uint8Array` TypedArray, `Buffer.from` copies each element and truncates it to one byte, so it does not copy the underlying bytes. `res.send(new Uint16Array([0x1234, 0x5678]))` returns `200` with `Content-Length: 2` and body `34 78`. The correct body is the 4 bytes `34 12 78 56`. `res.send(new Float32Array([1.5]))` sends 1 byte (`0x01`).
  - **`DataView`:** `Buffer.from(dataView)` produces an empty buffer. `res.send(new DataView(new Uint8Array([65,66,67]).buffer))` returns `200` with `Content-Length: 0` and an empty body, so the data is silently lost. This happens whether ETag is enabled or disabled: with ETag off, `chunk.length` is `undefined`, the check `undefined < 1000` is false, and the code still goes through `Buffer.from`.
  - **ETag disabled with a `Uint16Array`:** `Content-Length` is set to 4 (`Buffer.byteLength`), and then `this.end(uint16array)` throws `ERR_INVALID_ARG_TYPE` ("must be of type string or an instance of Buffer or Uint8Array"). The result is a 500 instead of the payload.
- **How I reproduced it:** a small express app with `app.get('/', (req, res) => res.send(<view>))`, requested over a raw socket. The observed responses are the ones listed above.
- **Why it's wrong:** line 151 explicitly accepts all `ArrayBuffer` views as binary bodies and gives them `Content-Type: application/octet-stream` (`this.type('bin')`). That signals the intent to send the view's bytes. What actually happens is truncated content, an empty 200, or a thrown error, depending on the view type and the etag setting. The empty and truncated cases fail silently, and the ETag is computed over the wrong bytes.
- **Severity:** medium. The data is silently corrupted or lost and no error is raised, but only for non-`Uint8Array` views, which are less common than Buffer and strings.
- **Suggested fix:** in the `ArrayBuffer.isView` branch, normalize the view to a Buffer over the same memory, so every later step (length, ETag, `end`) works on the real bytes:
  ```js
  } else if (ArrayBuffer.isView(chunk)) {
    if (!Buffer.isBuffer(chunk)) {
      chunk = Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength)
    }
    if (!this.get('Content-Type')) {
      this.type('bin');
    }
  }
  ```

## Checked and not reported

These areas matched their documentation or the expected semantics. For some, the only concern was too speculative to report.

- `utils.js`: `acceptParams` parameter skipping, `compileTrust`, `compileETag`, `compileQueryParser`, `setCharset`.
- `request.js`: `req.host`, `req.hostname` (including IPv6), `req.protocol`, `req.ips`, `req.subdomains`, `req.fresh`, `req.query`, `req.range`.
- `response.js`: `status`, `links`, `json`/`jsonp` (callback sanitising, U+2028/2029), `sendStatus`, `sendFile`/`download` argument shuffling, `format`, `attachment`, `append`, `set`, `cookie`/`clearCookie`, `redirect`, `render`, the internal `sendfile` completion logic, `stringify`.
- `application.js`: `use` (including mounted apps and prototype restore), `set` and the trust-proxy inheritance, `render` and the view cache, `listen`, `all`.
- `view.js`: engine loading, `lookup`/`resolve`, and the forced-async render callback.

## Files read

- `lib/application.js`
- `lib/express.js`
- `lib/request.js`
- `lib/response.js`
- `lib/utils.js`
- `lib/view.js`
- `package.json` (dependency versions)
