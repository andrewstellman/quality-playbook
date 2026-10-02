model: gpt-5.6-terra
repo: express
pinned commit: 9a34acf03cb818ff3f8bc40e44176e277a25cbb9
date/time started and finished: started approximately 2026-09-28 22:48:16 UTC; finished 2026-09-28 22:49:49 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran local Node 26 check
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Express `lib/` review — terra run 03

## Findings

### Medium — `res.send()` corrupts non-`Uint8Array` ArrayBuffer views

- **File/line:** `lib/response.js:151`, `lib/response.js:175`
- **Failure:** `res.send()` explicitly accepts every `ArrayBuffer` view through
  `ArrayBuffer.isView(chunk)`, but then converts the view with `Buffer.from(chunk)`.
  Node interprets a typed array as an array of numeric *elements*, rather than as
  its underlying byte range, and a `DataView` has no indexed elements at all.
  Consequently, `res.send(new DataView(Uint8Array.from([65, 66, 67]).buffer))`
  emits an empty response (and an ETag for an empty body); a `Uint16Array` or
  other multi-byte typed array is similarly truncated and/or transformed.
- **Why this is wrong:** The branch at line 151 deliberately recognizes the
  broader `ArrayBuffer.isView` class, whose members include `DataView` and all
  typed arrays, then line 175 uses a conversion that does not preserve their
  byte contents. The existing `Uint8Array` test establishes that this path is
  intended to transmit binary views, but it only covers the one view type for
  which `Buffer.from(view)` happens to preserve bytes.
- **Suggested fix:** Convert views from their backing byte span, e.g.
  `Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength)`, before
  calculating length/ETag and calling `end`. Add regression coverage for a
  `DataView` with a non-zero `byteOffset` and a multi-byte typed array.

## Files read

- `lib/application.js`
- `lib/express.js`
- `lib/request.js`
- `lib/response.js`
- `lib/utils.js`
- `lib/view.js`
- `package.json`
- `test/res.clearCookie.js`
- `test/res.links.js`
- `test/res.location.js`
- `test/res.redirect.js`
- `test/res.send.js`
