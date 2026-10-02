model: gpt-5.6-terra
repo: express
pinned commit: 9a34acf03cb818ff3f8bc40e44176e277a25cbb9
date/time started and finished: started approximately 2026-09-28 22:46:07 UTC; finished 2026-09-28 22:48:11 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Express `lib/` review

Repository: `expressjs/express`  
Pinned commit: `9a34acf03cb818ff3f8bc40e44176e277a25cbb9`

## Findings

### Medium — `res.send()` corrupts `DataView` and non-byte typed-array response bodies

**Location:** `lib/response.js:151-177`

`res.send()` uses `ArrayBuffer.isView(chunk)` to take every `ArrayBuffer` view down the binary-response path (lines 151-154). It later converts that value with `Buffer.from(chunk)` (line 175) before calculating `Content-Length`, generating an ETag, and ending the response. That conversion does not copy a view's byte range in general: for example, `Buffer.from(new DataView(Uint8Array.from([65, 66, 67, 68]).buffer, 1, 2))` is an empty buffer, although the view represents the bytes `BC`. A multi-byte typed array likewise becomes one byte per element rather than its underlying bytes.

As a result, `res.send(new DataView(...))` sends an empty response with `Content-Length: 0` and an ETag for an empty body; `res.send(new Uint16Array(...))` sends corrupted bytes. This contradicts the branch's treatment of all `ArrayBuffer` views as binary bodies and the `Uint8Array` behavior verified in `test/res.send.js:207-218`. The issue occurs with the default ETag setting and also when ETags are disabled, since both paths eventually use the view incorrectly.

**Suggested fix:** Convert an accepted view by its byte range before the length/ETag/end logic, for example:

```js
chunk = Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength)
```

Alternatively, narrow the branch to `Uint8Array` if that is the only supported view type. Add regression coverage for a `DataView` with a nonzero offset and a multi-byte typed array.

## Verification

The checkout has no installed dependencies, so its Express test suite could not run without fetching packages. An offline Node 26.3.1 check showed the faulty conversion directly:

```text
new DataView(Uint8Array.from([65, 66, 67, 68]).buffer, 1, 2) -> Buffer.from(...) length 0
Buffer.from(view.buffer, view.byteOffset, view.byteLength) -> "BC", length 2
```

## Files read

- `lib/application.js`
- `lib/express.js`
- `lib/request.js`
- `lib/response.js`
- `lib/utils.js`
- `lib/view.js`
- `test/res.send.js`
- `test/res.download.js`
- `test/res.sendFile.js`
- `test/req.host.js`
- `test/req.query.js`
- `test/app.render.js`
- `History.md`
- `package.json`
