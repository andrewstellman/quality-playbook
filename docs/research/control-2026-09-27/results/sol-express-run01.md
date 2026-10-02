model: gpt-6-sol
repo: express
pinned commit: 9a34acf03cb818ff3f8bc40e44176e277a25cbb9
date/time started and finished: started approximately 2026-09-28 22:01:48 UTC; finished 2026-09-28 22:03:26 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran Node Buffer conversion check; attempted Express tests
interruptions or errors: Express tests unavailable because dependencies are absent
network access attempted (yes/no, and what): no attempt reported

# Express `lib/` review — `9a34acf03cb818ff3f8bc40e44176e277a25cbb9`

## Finding 1 — `res.send()` corrupts non-byte `ArrayBuffer` views (medium)

**File and line:** `lib/response.js:151`, `lib/response.js:175`.

**What goes wrong:** `res.send(new Uint16Array([0x1234, 0x5678]))` takes the binary-body branch, but with the default ETag setting it converts the view using `Buffer.from(chunk)`. That produces bytes `34 78`, rather than the view's four underlying bytes. `res.send(new DataView(Uint8Array.from([1, 2]).buffer))` produces an empty Buffer, so the response silently loses the entire body. A slice/view over a larger buffer can likewise send the wrong bytes. Node's built-in Buffer behavior confirms these results (`Buffer.from(new Uint16Array([0x1234, 0x5678]))` is `<Buffer 34 78>`; `Buffer.from(new DataView(Uint8Array.from([1, 2]).buffer))` is `<Buffer >`).

**Why wrong:** Line 151 deliberately accepts **all** `ArrayBuffer` views as binary bodies, and the adjacent comment on line 174 says the conversion is to calculate length. The existing `test/res.send.js` `should accept Uint8Array` test also establishes that views are sent as raw binary data. The conversion instead changes their contents. This can corrupt files or protocol payloads supplied as typed arrays.

**Suggested fix:** Normalize each accepted view to a Buffer over its exact underlying byte range, for example `Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength)`, before calculating length, generating an ETag, or ending the response. Preserve the current Buffer fast path. Add cases for `Uint16Array`, `DataView`, and nonzero `byteOffset`.

**Verification limit:** The checkout has no installed dependencies (`require('./')` fails on missing `body-parser`), so I verified the conversion using Node's built-in Buffer API rather than running the Express test suite. No checkout files were modified.

## Files read

- `lib/application.js`
- `lib/express.js`
- `lib/request.js`
- `lib/response.js`
- `lib/utils.js`
- `lib/view.js`
- `index.js`
- `package.json`
- `test/res.send.js`
