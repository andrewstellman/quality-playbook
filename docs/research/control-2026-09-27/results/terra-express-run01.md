model: gpt-5.6-terra
repo: express
pinned commit: 9a34acf03cb818ff3f8bc40e44176e277a25cbb9
date/time started and finished: started approximately 2026-09-28 22:45:42 UTC; finished 2026-09-28 22:48:19 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Express `lib/` review — terra-express-run01

## Findings

### Medium — `res.send()` corrupts or drops binary data from non-`Uint8Array` ArrayBuffer views

- **Location:** `lib/response.js:151` and `lib/response.js:170-177`
- **Situation:** Supplying a `DataView` to `res.send()` produces an empty response. For example, `res.send(new DataView(Uint8Array.from([0x41, 0x42]).buffer))` reaches the `ArrayBuffer.isView` branch at line 151, then falls through to `Buffer.from(chunk)` at line 175 because `DataView` has no `.length`. Node converts that `DataView` to an empty Buffer, so Express emits `Content-Length: 0` instead of `AB`. Other typed-array views are also handled incorrectly: `Buffer.from(new Uint16Array([0x4241]))` creates the one-byte buffer `41` rather than the view's two backing bytes.
- **Why this is wrong:** The code deliberately accepts every `ArrayBuffer` view via `ArrayBuffer.isView`, but the later conversion is only byte-preserving for a `Uint8Array`/Buffer. The repository’s release notes describe this response path as adding binary `Uint8Array` support (`History.md:69`), and the accompanying test (`test/res.send.js:207-218`) establishes that the bytes of a typed-array binary response must be sent intact. Categorizing the broader family as binary and then converting it with `Buffer.from(view)` silently corrupts the accepted body.
- **Suggested fix:** Restrict the special binary path to `Buffer` and `Uint8Array` if those are the supported body types, letting other views use normal JSON handling or throw a clear type error. If all `ArrayBuffer` views are intended to be accepted, convert them with their byte window, e.g. `Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength)`, and calculate length from `byteLength`.

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
- `History.md`
- `package.json`
