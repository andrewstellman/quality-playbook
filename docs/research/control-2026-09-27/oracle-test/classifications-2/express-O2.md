express-01 | line | Lines 285-304 show that the "non-empty callback" check runs before the `replace()` that strips characters, so a callback that is emptied by sanitising still gets wrapped.
express-02 | trace | The reviewer has to know that `mime.contentType()` in the mime-types dependency returns `false` for an unrecognised type, and that `res.set` stores that `false` without checking it.
express-03 | line | Line 404 assigns `opts.etag` unconditionally, which overwrites any `etag` value the caller passed in.
express-04 | input | The reviewer has to try a status code with no entry in `statuses.message` (for example 399) to see `undefined` spliced into the text and HTML bodies.
express-05 | line | Line 380 aliases `opts` to the caller's `options`, and line 404 writes to it, so the caller's object is changed.
express-06 | nearby | The function's docstring promises a comma-separated list (`'utf-8, utf-16'` → `"utf-8"`), but the body passes the arguments through unchanged; the reviewer compares the two.
express-07 | input | The reviewer has to run a non-byte typed array or a DataView through `Buffer.from(chunk, encoding)` and know how it behaves: it truncates each element to one byte, and a DataView has no `length`, so the body comes out empty.
express-08 | nearby | The reviewer has to read the sibling `hostname` getter, see that IPv6 hosts keep their brackets, and realise `isIP()` in `subdomains` will then fail on them.
express-09 | input | The reviewer has to think of a fully-qualified Host with a trailing dot; `split('.')` then yields an empty first label, and the offset of 2 lands one label off.
express-10 | input | The reviewer has to follow the path etag-disabled → small chunk → `Buffer.byteLength` with a Uint16Array, and know that `res.end()` rejects non-Uint8Array views.
express-11 | input | The reviewer has to try a `maxAge` under 1000 ms: `Math.floor(maxAge/1000)` gives `Max-Age=0`, while `Expires` still reflects the half-second.
