model: gpt-5.6-terra
repo: express
pinned commit: 9a34acf03cb818ff3f8bc40e44176e277a25cbb9
date/time started and finished: started approximately 2026-09-28 22:55:04 UTC; finished 2026-09-28 22:57:25 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Express `lib/` review — 9a34acf03cb818ff3f8bc40e44176e277a25cbb9

## Findings

### Medium — `res.send()` silently corrupts non-`Uint8Array` `ArrayBuffer` views

- **Location:** `lib/response.js:151-156, 175-177`
- **Failure:** `res.send()` classifies every `ArrayBuffer` view as binary via
  `ArrayBuffer.isView(chunk)`, but it subsequently converts the value with
  `Buffer.from(chunk, encoding)`. That conversion only preserves elements for
  typed arrays and has no byte-view conversion semantics for arbitrary views:
  `Buffer.from(new DataView(Uint8Array.from([0x41, 0x42, 0x43]).buffer))` is an
  empty buffer. It also corrupts multi-byte typed arrays: an
  `Int16Array([0x4142, 0x4344])` becomes bytes `42 44` rather than the view's
  bytes `42 41 44 43` on the test host. With the default ETag configuration,
  lines 161-177 take this conversion path before sending, so the client gets
  an empty or truncated/corrupted response and an ETag for that wrong body.
- **Why this is wrong:** the branch at lines 151-154 explicitly elects to send
  every `ArrayBuffer` view as binary, rather than JSON-serializing it. Once it
  makes that choice, the response must contain the selected view's bytes. The
  nearby `res.send()` documentation promises binary `Buffer` support, and the
  repository history records support for `Uint8Array`; the generalized
  `ArrayBuffer.isView` predicate includes `DataView` and all typed arrays but
  the later conversion does not implement those types correctly.
- **Suggested fix:** either restrict the predicate to `Uint8Array` (the type
  actually supported) or convert views by their backing range, for example
  `Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength)`. The latter
  handles `DataView`, respects subarray offsets, and sends the raw bytes of all
  typed-array views. Add regression tests for a `DataView` and a non-byte typed
  array, including a nonzero `byteOffset`.

## Files read

- `lib/application.js`
- `lib/express.js`
- `lib/request.js`
- `lib/response.js`
- `lib/utils.js`
- `lib/view.js`
- `package.json`
- `History.md`
- `test/app.js`
- `test/app.render.js`
- `test/app.use.js`
- `test/res.cookie.js`
- `test/res.download.js`
- `test/res.links.js`
- `test/res.redirect.js`
- `test/res.send.js`
