model: gpt-6-sol
repo: express
pinned commit: 9a34acf03cb818ff3f8bc40e44176e277a25cbb9
date/time started and finished: started approximately 2026-09-28 22:08:14 UTC; finished 2026-09-28 22:09:41 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran offline Node check
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Express `lib/` review

## Finding 1 — ArrayBuffer views other than byte arrays lose response data

- **File and line:** `lib/response.js:175` (with the view acceptance at line 151).
- **Severity:** Medium.
- **What goes wrong:** With default ETag generation, `res.send(new Uint16Array([0x1234]))` sends one byte (`34`) instead of the view's two bytes (`34 12` on a little-endian host). `res.send(new DataView(Uint8Array.from([1, 2, 3]).buffer))` sends an empty body instead of three bytes. The ETag and `Content-Length` are then calculated for the truncated body. With ETags disabled, the short-view branch at line 170 can also pass a non-byte typed array to `res.end`, which Node rejects.
- **Why it is wrong:** Line 151 deliberately accepts any `ArrayBuffer.isView(chunk)` as a binary body, and `test/res.send.js:207-217` establishes the intended binary-send behavior for `Uint8Array`. But `Buffer.from(view)` reads typed-array *elements* and does not preserve all of a multi-byte view's underlying bytes; for `DataView`, it produces an empty Buffer. An offline Node check confirmed `Buffer.from(new Uint16Array([0x1234])).toString('hex') === '34'` and `Buffer.from(new DataView(Uint8Array.from([1,2,3]).buffer)).length === 0`.
- **Suggested fix:** Normalize non-Buffer `ArrayBuffer` views to a byte Buffer before the length and ETag branches, using the view's `buffer`, `byteOffset`, and `byteLength` (or copy those bytes if required). Add regression cases for `Uint16Array`, `DataView`, and a sliced view with a nonzero offset.

## Files read

- `lib/application.js`
- `lib/express.js`
- `lib/request.js`
- `lib/response.js`
- `lib/utils.js`
- `lib/view.js`
- `package.json`
- `Readme.md` (search matches only)
- `test/res.send.js`
- `test/req.subdomains.js`
- `test/req.host.js` (search matches only)
- `test/app.render.js` (search matches only)
- `test/res.render.js` (search matches only)
