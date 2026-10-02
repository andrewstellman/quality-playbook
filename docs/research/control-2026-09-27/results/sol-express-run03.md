model: gpt-6-sol
repo: express
pinned commit: 9a34acf03cb818ff3f8bc40e44176e277a25cbb9
date/time started and finished: started approximately 2026-09-28 22:03:39 UTC; finished 2026-09-28 22:05:16 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran Node snippet; Express suite unavailable
interruptions or errors: Express dependencies absent
network access attempted (yes/no, and what): no attempt reported

# Express `lib/` review — 9a34acf03cb818ff3f8bc40e44176e277a25cbb9

## Finding

### Medium — `res.send()` corrupts non-byte `ArrayBuffer` views

**Location:** `lib/response.js:151-157, 166-178`

`res.send()` classifies every `ArrayBuffer` view as a binary response (`ArrayBuffer.isView(chunk)`), but then passes the view directly to `Buffer.from(chunk)`. That conversion copies each typed-array *element* as one byte, rather than copying the view's underlying bytes. For example, `new Uint16Array([0x1234, 0x5678])` has four bytes but becomes `<Buffer 34 78>`, and a three-byte `DataView` becomes an empty buffer. Express sends the wrong body and computes `Content-Length` and ETag from those wrong bytes. The binary-view branch and the existing `Uint8Array` send test in `test/res.send.js` establish the intent to transmit these views as binary data.

**Suggested fix:** Convert views using their byte range: `Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength)`. If the API is meant to accept only `Uint8Array`, narrow the branch explicitly and reject or JSON-serialize other view types rather than silently corrupting them.

**Verification:** In the checkout's Node runtime, `Buffer.from(new Uint16Array([0x1234, 0x5678]))` produced two bytes for a four-byte view, and `Buffer.from(new DataView(Uint8Array.from([1,2,3]).buffer))` produced zero bytes. The checkout has no `node_modules`, so the Express test suite could not be run without fetching packages.

## Files read

`lib/application.js`, `lib/express.js`, `lib/request.js`, `lib/response.js`, `lib/utils.js`, `lib/view.js`, `test/res.send.js`, `test/app.render.js`, `test/app.listen.js`, `test/req.hostname.js`, `test/req.host.js`, `test/res.download.js`, `test/res.render.js` (search matches only), `README.md` (search matches only), and `package.json`.
