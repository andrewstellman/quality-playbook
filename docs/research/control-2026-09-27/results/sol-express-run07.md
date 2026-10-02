model: gpt-6-sol
repo: express
pinned commit: 9a34acf03cb818ff3f8bc40e44176e277a25cbb9
date/time started and finished: started approximately 2026-09-28 22:06:15 UTC; finished 2026-09-28 22:07:57 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran offline Node snippets; Express suite unavailable
interruptions or errors: Express dependencies absent
network access attempted (yes/no, and what): no attempt reported

# Express `lib/` review — 9a34acf03cb818ff3f8bc40e44176e277a25cbb9

## Finding

**Medium — `res.send()` silently corrupts non-byte `ArrayBuffer` views** (`lib/response.js:151`, `lib/response.js:170–177`). The `ArrayBuffer.isView(chunk)` branch treats every view as binary response data, but the conversion uses `Buffer.from(chunk)`. For `new Uint16Array([0x1234, 0x5678])`, the four underlying bytes become a two-byte buffer (`34 78`); for a `DataView` over three bytes, the buffer is empty. With ETags disabled, the small-view path can instead give Node's `end()` a non-`Uint8Array` view. The intended binary behavior is established by that view branch, which sets `application/octet-stream`, and by `test/res.send.js:207–217`, which verifies that a `Uint8Array` is sent as bytes. Convert an accepted view using `Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength)` before calculating length, generating the ETag, or ending the response. A regression test should cover `DataView` and a multibyte typed array, with ETags both enabled and disabled.

The local checkout has no `node_modules`, so I did not run the project test suite. A local Node snippet confirmed the conversions: `Buffer.from(new Uint16Array([0x1234, 0x5678]))` yields `34 78`, and `Buffer.from(new DataView(Uint8Array.from([1,2,3]).buffer))` yields an empty buffer.

Files read or inspected: `lib/application.js`, `lib/express.js`, `lib/request.js`, `lib/response.js`, `lib/utils.js`, `lib/view.js`, `test/res.send.js`, `test/req.acceptsCharsets.js`, `test/res.sendFile.js`, `test/app.render.js`, `test/res.cookie.js`, `test/res.redirect.js`, `package.json`, `History.md`.
