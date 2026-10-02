model: gpt-5.6-terra
repo: express
pinned commit: 9a34acf03cb818ff3f8bc40e44176e277a25cbb9
date/time started and finished: started approximately 2026-09-28 22:50:07 UTC; finished 2026-09-28 22:52:15 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Express `lib/` review — 9a34acf03cb818ff3f8bc40e44176e277a25cbb9

## Findings

### Medium — `res.send()` silently sends an empty response for `DataView` bodies

- **File and line:** `lib/response.js:151` (with the loss occurring at `lib/response.js:175`)
- **Trigger:** `res.send(new DataView(Uint8Array.from([0x68, 0x65, 0x79]).buffer))` with the default ETag setting (the normal application default).
- **What goes wrong:** `ArrayBuffer.isView(chunk)` treats a `DataView` as a supported binary body. Since ETag generation is enabled by default, the subsequent length/ETag branch executes `Buffer.from(chunk, encoding)`. `Buffer.from(DataView)` creates an empty buffer because `DataView` has neither indexed elements nor a `length` property. Express consequently emits `Content-Length: 0`, an ETag for the empty body, and sends no bytes instead of `hey`.
- **Why this is wrong:** The release notes and regression test identify the intended addition as support for `Uint8Array` in `res.send()` (`History.md:69`, `test/res.send.js:207`). The broader `ArrayBuffer.isView` predicate also accepts `DataView` and non-byte typed arrays, whose contents do not have the `Uint8Array`/Buffer byte semantics that the later conversion assumes. A body accepted as binary must preserve its bytes; silently converting a three-byte `DataView` into an empty response violates that behavior.
- **Suggested fix:** Restrict the binary branch to `Buffer.isBuffer(chunk) || chunk instanceof Uint8Array` (Buffers are already `Uint8Array` subclasses on supported Node versions), or explicitly convert each accepted view using its byte window: `Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength)`. Add coverage for a non-zero-offset `DataView`; if broader view support is intentional, also specify and test the byte representation for multi-byte typed arrays.

## Files read

- `lib/application.js`
- `lib/express.js`
- `lib/request.js`
- `lib/response.js`
- `lib/utils.js`
- `lib/view.js`
- `test/res.send.js`
- `test/res.sendFile.js`
- `test/res.download.js`
- `test/app.render.js`
- `test/res.render.js`
- `History.md`
- `package.json`
