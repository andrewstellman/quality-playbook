model: gpt-6-sol
repo: express
pinned commit: 9a34acf03cb818ff3f8bc40e44176e277a25cbb9
date/time started and finished: started approximately 2026-09-28 22:08:14 UTC; finished 2026-09-28 22:10:37 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; ran local Node snippet; project suite unavailable
interruptions or errors: dependencies absent
network access attempted (yes/no, and what): no attempt reported

# Express `lib/` review

Checkout: `9a34acf03cb818ff3f8bc40e44176e277a25cbb9`

## Finding

**Medium — `res.send` corrupts non-byte `ArrayBuffer` views** (`lib/response.js:151`, `lib/response.js:170-177`). The `ArrayBuffer.isView(chunk)` branch accepts `Uint16Array`, `Uint32Array`, `DataView`, and other views as binary response bodies, but the normal ETag path converts them with `Buffer.from(chunk)`. That conversion reads typed-array *elements* as byte values rather than copying the view's bytes, and turns a `DataView` into an empty buffer. For example, Node produces `Buffer.from(new Uint16Array([0x1234, 0x5678])) === <Buffer 34 78>` even though the view is four bytes long; `Buffer.from(new DataView(Uint8Array.from([1,2,3]).buffer))` is empty. Thus the response body, `Content-Length`, and ETag all describe the wrong bytes. With ETags disabled, the short-body branch can instead pass a non-`Uint8Array` view to `ServerResponse.end`, which does not accept that body type. The explicit `ArrayBuffer.isView` acceptance and the existing `Uint8Array` response test establish the intended binary handling. Convert views through their underlying buffer, respecting `byteOffset` and `byteLength` (for example, `Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength)`), before calculating length, ETag, or ending the response.

## Verification

I checked the relevant Node `Buffer.from` and `Buffer.byteLength` behavior with a local snippet. The project's dependencies are absent (`require('body-parser')` fails), and the sandbox does not permit a listening socket, so I could not run its HTTP test suite. I did not modify the checkout.

## Files read

- `lib/application.js`
- `lib/express.js`
- `lib/request.js`
- `lib/response.js`
- `lib/utils.js`
- `lib/view.js`
- `package.json`
- `test/req.acceptsCharsets.js`
- `test/res.redirect.js`
- `test/res.send.js`
