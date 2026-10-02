# Hits: express

| ID | Reports that include it as a finding | Reports that mention it but do not report it |
|---|---|---|
| express-01 | opus-run01, opus-run09 | |
| express-02 | opus-run01, opus-run02, opus-run03, opus-run04, opus-run05, opus-run06, opus-run07, opus-run08, opus-run09, opus-run10, sonnet-run07 | sonnet-run08 |
| express-03 | opus-run02, opus-run04, opus-run08, opus-run10 | sonnet-run06 |
| express-04 | opus-run03 | opus-run01, opus-run02 |
| express-05 | opus-run01 | |
| express-06 | opus-run01, opus-run03, opus-run04, opus-run05, opus-run06, opus-run08, opus-run10, sonnet-run01, sonnet-run04 | sonnet-run09 |
| express-07 | opus-run02 | |
| express-08 | opus-run03, opus-run08 | |
| express-09 | opus-run01, opus-run02, opus-run03, opus-run04, opus-run05, opus-run07, opus-run08, opus-run09, sonnet-run07 | sonnet-run08 |
| express-10 | opus-run03 | |

## Deduplication judgement calls

- **express-02 / express-09 (split).** Every `res.send` typed-array report puts these under one heading. Split because they fail on different code paths: express-02 is the default ETag path (`Buffer.from(chunk)` at line 175 copies element values); express-09 is the ETag-off path (`Buffer.byteLength` at 172, then `res.end` at 218 with the raw view, which throws). opus-run06 and opus-run10 describe only the default path and DataView, so they count for express-02 only.
- **DataView merged into express-02.** A DataView always reaches line 175, ETag on or off, because `undefined < 1000` is false.
- **express-06 follow-on merged.** The later `res.send()` switching to `text/html` follows from the same line-681 value. opus-run08 says `send` throws inside `setCharset`; in the checkout `getHeader` returns boolean `false` so `send` takes the `this.type('html')` branch. Kept opus-run08 as a hit.
- **express-04 / express-10 (split).** Mutation of the caller's object vs. override of the caller's explicit `etag`. opus-run01 and opus-run02 mentions are about mutation only.
- **express-01 / express-05 (split).** Bracketed IPv6 vs. trailing dot need separate fixes.
- **Mention strictness.** Generic "area checked" lists don't count. sonnet-run06 explicitly rejects the redirect "undefined" body (express-03). sonnet-run09 tests an unparsable Content-Type and calls it expected (express-06). sonnet-run08 checks ArrayBufferView handling and the `<1000` path (express-02, express-09). Not counted: sonnet-run10, sonnet-run02, sonnet-run03 on `res.set` (charset cases only); opus-run03/07/10 for express-07 (only list JSONP as checked).
- **Mentioned but never reported, no row:** `req.host` `.trimEnd()` asymmetry (sonnet-run03, sonnet-run06); `res.redirect` old argument order throwing (opus-run01, opus-run03); `res.render` writing `opts._locals` (opus-run01); view cache keyed only by name (opus-run01).
- **Reports with no findings:** sonnet-run02, 03, 05, 06, 08, 09, 10.
