express-01 | line | The length check at line 285 runs before the character stripping at line 290, so a callback made entirely of disallowed characters becomes empty after it has already passed the check.
express-02 | trace | The reviewer must know that `mime.contentType()` (from the mime-types package) returns `false` for a type it doesn't recognise; nothing in `res.set` checks for that before calling `setHeader`.
express-03 | line | Line 404 overwrites `opts.etag` with the app setting without checking whether the caller already set it.
express-04 | input | The reviewer has to think of a numeric status that has no entry in `statuses.message` (such as 399); for normal redirect codes the string building at 843/848-849 looks fine.
express-05 | line | Line 380 takes `opts` straight from the caller's `options` without copying it, and line 404 writes to it, so the caller's object is changed.
express-06 | nearby | The JSDoc just above (lines 149-164) promises comma-delimited lists and gives `'utf-8, utf-16'` as an example, but the body passes the arguments to `accepts` without splitting them.
express-07 | input | The reviewer has to try a typed array that isn't byte-sized (Uint16Array) or a DataView and know how `Buffer.from` handles each, since `ArrayBuffer.isView` lets both through to line 175.
express-08 | input | The reviewer has to try an IPv4-mapped IPv6 host and follow it through the `hostname` getter, which keeps the brackets, so `isIP` fails; plain `[::1]` has no dots and happens to give the right result.
express-09 | input | The reviewer has to think of a fully qualified hostname with a trailing dot, which makes `split('.')` produce an empty last label that uses up one place of the offset.
express-10 | input | The reviewer needs both etag disabled and a non-Uint8 typed array: then line 172 measures the byte length but line 218 passes the raw typed array to `res.end`, which only accepts string, Buffer or Uint8Array.
express-11 | input | The reviewer has to try a `maxAge` under 1000 ms: `expires` keeps the milliseconds while `Math.floor(maxAge/1000)` gives Max-Age=0, which tells the browser to delete the cookie immediately.
