express-01 | input | The reviewer has to try a callback made up only of characters the regex at line 290 strips (e.g. `!!!`). The empty-callback check at line 285 runs before the strip, so this case slips past it.
express-02 | trace | The reviewer has to know that `mime.contentType()` in the external mime-types package returns `false` for a value with no slash. They then have to follow that `false` into `res.set`, `setHeader` and `res.send`'s `typeof type === 'string'` check.
express-03 | line | Line 404 assigns `opts.etag` unconditionally from the app setting, so it overwrites any caller-supplied `etag`.
express-04 | input | The reviewer has to try a status code that has no entry in `statuses.message` (e.g. 399), so that lines 843 and 848-849 concatenate `undefined`.
express-05 | line | Line 404 writes to the caller's `opts` object (which is `options` itself, `opts = options || {}`), and the caller is never told.
express-06 | nearby | The docstring at lines 150-152 and 163-164 promises comma-delimited lists work. The reviewer has to compare that with the body at lines 171-174, which never splits the string.
express-07 | input | The reviewer has to try a non-Uint8 typed array or a DataView. `Buffer.from(chunk, encoding)` at line 175 copies elements, not bytes, and this only shows up when the case is tried.
express-08 | input | The reviewer has to try a bracketed IPv6 Host such as `[::ffff:127.0.0.1]`. `isIP` rejects the brackets at line 389, so the host is split on `.`.
express-09 | input | The reviewer has to try a fully-qualified host with a trailing dot. The split at line 390 then yields a leading empty label that shifts the offset.
express-10 | input | The reviewer has to try a non-Uint8 typed array with etag disabled. Line 172 takes the `Buffer.byteLength` branch, and `end()` at line 218 then receives the raw typed array.
express-11 | input | The reviewer has to try a `maxAge` under 1000 ms (e.g. 500). Line 769 floors it to 0, while line 768 gives `expires` sub-second precision.
