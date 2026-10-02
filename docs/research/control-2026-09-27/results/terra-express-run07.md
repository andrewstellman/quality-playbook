model: gpt-5.6-terra
repo: express
pinned commit: 9a34acf03cb818ff3f8bc40e44176e277a25cbb9
date/time started and finished: started approximately 2026-09-28 22:52:26 UTC; finished 2026-09-28 22:54:26 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Express `lib/` review — `9a34acf03cb818ff3f8bc40e44176e277a25cbb9`

## Finding 1 — `res.send` drops the bytes of `DataView` and corrupts wider typed arrays

- **Severity:** Low
- **Location:** `lib/response.js:151-153, 175`
- **Trigger:** Pass an `ArrayBuffer` view other than a `Uint8Array` to `res.send`, for example `res.send(new DataView(new Uint8Array([1, 2, 3]).buffer))` or `res.send(new Uint16Array([0x0102, 0x0304]))`.
- **What goes wrong:** The branch explicitly accepts all views through `ArrayBuffer.isView(chunk)`, then later turns the view into a `Buffer` with `Buffer.from(chunk)`. Node treats a `DataView` as an array-like object with no indexed elements, producing an empty buffer; it treats a `Uint16Array` as an array of numeric elements and truncates each to one byte. Thus the first example returns a zero-length response instead of `01 02 03`, and the second loses every high byte.
- **Why this is wrong:** `ArrayBuffer.isView` is the condition that classifies the value as a binary response (rather than sending it as JSON), and the immediately adjacent code sets a binary content type for that path. Having selected the binary representation, it must transmit the bytes represented by the view, including its `byteOffset` and `byteLength`. The existing Uint8Array regression test in `test/res.send.js:207-218` establishes that this path is intended to send the supplied view's binary payload.
- **Suggested fix:** In the `ArrayBuffer.isView` branch, convert to the view's bytes before length/ETag processing, for example:

  ```js
  chunk = Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength);
  ```

  Keep the existing content-type logic and add regressions for a `DataView` with a non-zero offset and a wider typed array.

## Files read

- `lib/application.js`
- `lib/express.js`
- `lib/request.js`
- `lib/response.js`
- `lib/utils.js`
- `lib/view.js`
- `test/res.send.js`
- `package.json`
