model: gpt-5.6-terra
repo: express
pinned commit: 9a34acf03cb818ff3f8bc40e44176e277a25cbb9
date/time started and finished: started approximately 2026-09-28 22:53:10 UTC; finished 2026-09-28 22:54:51 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Express `lib/` review — terra run 08

## Findings

### Medium — `res.send()` silently drops every byte from a `DataView`

- **Location:** `lib/response.js:151-177`
- **Trigger:** `res.send(new DataView(arrayBuffer))`, including a view with a nonzero `byteOffset` or any nonempty byte range.
- **What goes wrong:** The `ArrayBuffer.isView(chunk)` branch explicitly classifies a `DataView` as binary data. `DataView` has no `length`, so it bypasses the short-chunk calculation and reaches `Buffer.from(chunk, encoding)` at line 175. In Node, `Buffer.from(new DataView(new Uint8Array([65, 66, 67]).buffer))` is an empty buffer. Express therefore calculates `Content-Length: 0`, makes an ETag for an empty body, and sends an empty response rather than the view's bytes.
- **Why this is wrong:** The code's own `ArrayBuffer.isView` check at line 151 intentionally handles every ECMAScript ArrayBuffer view as binary instead of JSON. `DataView` is an ArrayBuffer view, and the data it exposes is its `byteOffset` / `byteLength` slice, neither of which is preserved by `Buffer.from(DataView)`.
- **Suggested fix:** Convert non-Buffer views using their backing-buffer range, e.g. `Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength)`, before length / ETag processing. Keep the existing Buffer path unchanged. This also makes the byte representation of all typed-array views consistent with their actual view range.

## Files read

- `lib/application.js`
- `lib/express.js`
- `lib/request.js`
- `lib/response.js`
- `lib/utils.js`
- `lib/view.js`
- `test/res.send.js`
- `package.json`
