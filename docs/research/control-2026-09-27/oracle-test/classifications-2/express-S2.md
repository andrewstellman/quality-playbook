express-01 | input | The reviewer has to run a callback made only of stripped characters such as `!!!`, because the length check at 285 runs before the strip at 290 and only that case leaves an empty name.
express-02 | input | The reviewer has to try a Content-Type value with no slash, such as `'foo'`, and know that `mime.contentType` returns `false` for it, which line 681 assigns straight to the header.
express-03 | nearby | The reviewer has to compare line 404 with the option list in the docblock and the caller's `opts`, to see that a caller-supplied `etag` is silently overridden by the app setting.
express-04 | input | The reviewer has to try a status code with no entry in `statuses.message` (such as 399), so that the lookups at 843 and 848-849 give `undefined`.
express-05 | line | The unconditional `opts.etag = ...` at line 404 mutates the caller's `options` object, which is visible from the line alone.
express-06 | nearby | The docblock in the same file promises comma-delimited lists are accepted, while the code passes the string through unsplit, so the reviewer must compare the doc and the code.
express-07 | input | The reviewer has to send a non-Uint8 typed array or a DataView, because `Buffer.from(chunk, encoding)` at 175 copies element values rather than raw bytes, and the `ArrayBuffer.isView` branch at 151 hides the difference.
express-08 | input | The reviewer has to try a bracketed IPv6 Host such as `[::ffff:127.0.0.1]:80` and know that `isIP` rejects the brackets, which the `!isIP(hostname)` line does not reveal.
express-09 | input | The reviewer has to try a fully qualified host with a trailing dot, since the plain `split('.')` at 389-390 yields an empty last element that shifts the offset.
express-10 | input | The reviewer has to combine a multi-byte typed array, `etag` set to false and a chunk under 1000 elements, so that `byteLength` is taken at 172 but the raw view is passed to `end` at 218.
express-11 | input | The reviewer has to try a sub-second `maxAge` such as 500, where the `Math.floor` at 769 yields `Max-Age=0` while `expires` is still in the future.
