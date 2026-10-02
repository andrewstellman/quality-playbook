express-01 | input | The reviewer has to try a callback made only of characters the sanitizer strips (such as `!!!`). The length check at line 285 runs before the strip at line 290, so the empty result is only visible with that input.
express-02 | trace | The reviewer has to know that `mime.contentType()` in an external library returns `false` for a type with no known mapping. Line 681 looks fine until that behaviour is followed.
express-03 | line | Line 404 unconditionally overwrites `opts.etag` with the app setting, which discards any caller-supplied value.
express-04 | input | The reviewer has to try a status code with no entry in the `statuses.message` table, such as 399. The code reads fine for the usual codes.
express-05 | line | Line 404 assigns to the caller's `opts` object, so it mutates an argument. This is visible on inspection.
express-06 | nearby | The docstring just above (lines 152 and 163) promises comma-delimited lists work, but the implementation at lines 171-174 passes the string through unsplit.
express-07 | input | The reviewer has to try a typed array with elements wider than one byte, or a DataView. Line 175 relies on `Buffer.from(view)` semantics, which the lines alone don't reveal.
express-08 | input | The reviewer has to try a bracketed IPv6 Host header. `hostname` keeps its brackets, so `isIP` fails and the getter splits on dots.
express-09 | input | The reviewer has to try a fully-qualified Host with a trailing dot. The split-and-reverse at line 389 then yields an empty leading label that shifts the offset.
express-10 | input | The reviewer has to try a multi-byte typed array with etag disabled. Line 172 then computes a length from element count, and `this.end` receives a non-Buffer view. Etag-on takes a different path, so the case needs a specific input and setting.
express-11 | input | The reviewer has to try a `maxAge` under 1000 ms. Lines 764-769 look correct until a sub-second value shows the floor turning `Max-Age` into 0.
