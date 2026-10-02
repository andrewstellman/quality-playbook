# Code review: express `lib/` (pinned 9a34acf03cb818ff3f8bc40e44176e277a25cbb9)

Reviewer: Opus (express control, run 02)

Method: read all six files in `lib/` in full, then ran the project's unit tests (`mocha test/` gave 1153 passing, 0 failing) on a copy in the work directory. Each defect below was confirmed with a small supertest script against that copy.

## Defect 1: `res.send()` corrupts or rejects ArrayBuffer views other than Uint8Array/Buffer

- **File/line:** `lib/response.js` lines 151-178 (the `ArrayBuffer.isView(chunk)` branch, then the length and Buffer conversion block)
- **What goes wrong:** `res.send()` accepts any `ArrayBuffer.isView(chunk)` value as a binary body (line 151) and sets `Content-Type: application/octet-stream`. After that it treats the view as though it held one byte per element:
  - With ETag generation on (the default, `etag` = `weak`), line 175 runs `Buffer.from(chunk, encoding)`. For a `Uint16Array`/`Int32Array`/`Float64Array` etc., `Buffer.from(typedArray)` copies element values truncated to one byte each, so the data is silently corrupted. For example, `res.send(new Uint16Array([0x0102, 0x0304]))` sent `Content-Length: 2` and body `02 04`, but the underlying bytes are `02 01 04 03` (4 bytes).
  - With a `DataView`, `chunk.length` is `undefined`, so line 170 drops through to `Buffer.from(dataView)`, which gives an empty buffer. The response is `200` with `Content-Length: 0` and no body.
  - With ETag disabled (`app.set('etag', false)`) and a small non-Uint8 view, line 172 computes the correct byte length, but the raw `Uint16Array` then reaches `this.end(chunk)`. Node rejects it (`The "chunk" argument must be of type string or an instance of Buffer or Uint8Array`), so the request fails with a 500.
- **Why it is wrong:** line 151 explicitly accepts every ArrayBuffer view as a binary body. The docstring says `res.send` takes a `Buffer`/binary body, and `Content-Length` should match the bytes sent. Right now the result depends on the element type and on the ETag setting.
- **Severity:** medium. Binary bodies are silently corrupted or dropped, and there is no error.
- **Suggested fix:** in the `ArrayBuffer.isView` branch, normalize to a Buffer over the same memory before any length or ETag work:
  `chunk = Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength)`.
  Alternatively, restrict the branch to `Uint8Array` and treat other views as objects.

## Defect 2: `res.jsonp()` emits invalid JavaScript when the sanitized callback name is empty

- **File/line:** `lib/response.js` lines 285-304
- **What goes wrong:** the emptiness check at line 285 runs *before* sanitization at line 290 (`callback.replace(/[^\[\]\w$.]/g, '')`). A callback made only of disallowed characters, such as `?callback=!!!`, passes the check and then becomes `''`. The response is `text/javascript` with body `/**/ typeof  === 'function' && ({"a":1});`, which is a syntax error. Confirmed by request.
- **Why it is wrong:** the check at line 285 exists to fall back to plain JSON when there is no usable callback. Because it tests the unsanitized value, a request can get a broken JS body when it should get JSON.
- **Severity:** low
- **Suggested fix:** sanitize first, then test `callback.length !== 0`. If it is empty, fall through to the plain JSON response.

## Defect 3: `res.redirect()` body says "undefined" for status codes without a standard message

- **File/line:** `lib/response.js` lines 843 and 848-849
- **What goes wrong:** the body text uses `statuses.message[status]` with no fallback. For a valid but non-standard redirect status such as `res.redirect(399, '/x')`, the text body is `undefined. Redirecting to /x`, and the HTML title and paragraph also contain `undefined`. Confirmed by request.
- **Why it is wrong:** `res.status()` accepts any integer from 100 to 999 (lines 55-73). `res.sendStatus` in the same file handles the missing-message case with `statuses.message[statusCode] || String(statusCode)` (line 326). `redirect` does not do the same.
- **Severity:** low
- **Suggested fix:** `var msg = statuses.message[status] || String(status)`, and use `msg` in both bodies.

## Checked and not reported

- `acceptParams` parsing with `;`/`q=` in several orders gave correct results.
- `res.format` with no keys correctly gives a 406.
- `res.download`/`res.sendFile` option handling, the `sendfile` stream events, `req.host`/`hostname`/`protocol`/`ips`/`subdomains`/`fresh`, `app.use` mounting and prototype restore, `app.render`/`View` lookup, and the `compile*` helpers showed no confident defects.
- `res.sendFile` writes `opts.etag` onto the caller's options object (line 404). This is a minor mutation, not reported as a defect.

## Files read

- `lib/application.js`
- `lib/express.js`
- `lib/request.js`
- `lib/response.js`
- `lib/utils.js`
- `lib/view.js`
- `package.json` (for dependencies and the test script)
- The `test/` suite was run but not read file by file.
