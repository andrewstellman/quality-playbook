model: gpt-5.6-terra
repo: express
pinned commit: 9a34acf03cb818ff3f8bc40e44176e277a25cbb9
date/time started and finished: started approximately 2026-09-28 22:50:48 UTC; finished 2026-09-28 22:52:59 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Express `lib/` review — 9a34acf03cb818ff3f8bc40e44176e277a25cbb9

## Finding 1 — `res.send` corrupts non-byte typed-array payloads when ETags are enabled

- **Severity:** medium
- **Location:** `lib/response.js:151`, `lib/response.js:173-177`
- **Trigger:** Call `res.send()` with any `ArrayBuffer` view whose elements are not bytes, such as `new Uint16Array([0x4241, 0x4443])`, or with a `DataView`. The default application setting enables weak ETags.
- **What goes wrong:** The `ArrayBuffer.isView(chunk)` branch explicitly treats every view as a binary response, but the default ETag path converts that view with `Buffer.from(chunk, encoding)`. That overload converts typed-array *elements*, rather than the view's backing byte range: the `Uint16Array` example is reduced to bytes `0x41, 0x43` instead of its four backing bytes (`0x41, 0x42, 0x43, 0x44` on little-endian hosts), and `Buffer.from(new DataView(...))` produces an empty buffer. The corrupted buffer is used both for `Content-Length` and for `end()`, so clients receive truncated/corrupted data. Disabling ETags takes the short-length path and hands the original view to `end`, making the payload depend on the unrelated ETag setting.
- **Why this is wrong:** Lines 151-154 deliberately recognize all `ArrayBuffer` views and assign the binary content type. `ArrayBuffer.isView` includes `DataView` and all typed arrays, so this branch promises to send their binary contents. Lines 173-177 instead use a conversion whose semantics do not preserve those contents.
- **Suggested fix:** Normalize a non-Buffer view from its backing range before calculating length, generating an ETag, or writing it, for example `Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength)`. Retain the existing direct Buffer handling. Add regression cases for a `Uint16Array` and a `DataView`, with default ETags enabled, asserting the exact bytes and `Content-Length`.

## Files read

- `lib/application.js`
- `lib/express.js`
- `lib/request.js`
- `lib/response.js`
- `lib/utils.js`
- `lib/view.js`
- `package.json`
- `test/res.send.js`
- `test/req.query.js`
- `test/res.sendFile.js` (search-result context)
- `test/res.download.js` (search-result context)
- `test/res.links.js` (search-result context)
- `test/config.js` (search-result context)
- `test/utils.js` (search-result context)
