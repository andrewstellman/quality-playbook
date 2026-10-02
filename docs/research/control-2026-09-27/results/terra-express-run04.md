model: gpt-5.6-terra
repo: express
pinned commit: 9a34acf03cb818ff3f8bc40e44176e277a25cbb9
date/time started and finished: started approximately 2026-09-28 22:48:30 UTC; finished 2026-09-28 22:50:38 UTC
tools the sub-agent used (read files, ran commands, ran tests): read files; command and test details not reported
interruptions or errors: none reported
network access attempted (yes/no, and what): no attempt reported

# Express `lib/` review — 9a34acf03cb818ff3f8bc40e44176e277a25cbb9

## Findings

### Medium — `res.send()` silently discards `DataView` payloads

**File:** `lib/response.js:151` (conversion at line 172)

`res.send()` categorizes every `ArrayBuffer` view as a binary response using
`ArrayBuffer.isView(chunk)`. That predicate includes `DataView`, but the later
`Buffer.from(chunk, encoding)` conversion does not preserve a `DataView`'s
backing bytes: in Node it produces an empty buffer. Consequently, an application
that calls, for example,

```js
res.send(new DataView(Uint8Array.from([0x68, 0x69]).buffer));
```

returns an empty response with `Content-Length: 0` (and an ETag for an empty
body), rather than `hi`. The same conversion can also throw for BigInt typed
arrays, despite their satisfying the same `ArrayBuffer.isView` branch.

This is incorrect because the branch explicitly treats all `ArrayBuffer` views
as binary bodies, and the adjacent test/history support for `Uint8Array` shows
that the branch is meant to carry binary view data rather than serialize it as
JSON. The selected conversion only implements that promise for a subset of
views.

**Suggested fix:** normalize a non-Buffer view through its backing range before
length calculation and ETag generation, e.g.

```js
chunk = Buffer.from(chunk.buffer, chunk.byteOffset, chunk.byteLength)
```

in the `ArrayBuffer.isView(chunk)` branch. This preserves the exact bytes for
`DataView` and every typed-array kind.

## Files read

- `lib/application.js`
- `lib/express.js`
- `lib/request.js`
- `lib/response.js`
- `lib/utils.js`
- `lib/view.js`
- `test/app.render.js`
- `test/app.request.js`
- `test/app.use.js`
- `test/req.host.js`
- `test/req.hostname.js`
- `test/req.protocol.js`
- `test/req.query.js`
- `test/res.download.js`
- `test/res.redirect.js`
- `test/res.send.js`
- `test/res.sendFile.js`
- `package.json`
- `History.md`
