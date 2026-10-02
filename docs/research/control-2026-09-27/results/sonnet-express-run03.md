# Code review: express `lib/` (commit 9a34acf03cb818ff3f8bc40e44176e277a25cbb9)

## Summary

No defects found that I'm confident are real.

## What I did

- Read every file in the review scope (`lib/application.js`, `lib/express.js`, `lib/request.js`, `lib/response.js`, `lib/utils.js`, `lib/view.js`) line by line, checking each function's behavior against its own doc comment and against the HTTP semantics it claims to implement (status codes, Content-Length/Transfer-Encoding exclusivity, ETag/freshness, Accept negotiation, cookie/host/proxy parsing, view resolution).
- Cross-checked recent changes called out in `History.md`'s "Unreleased" section (Content-Length/Transfer-Encoding conflict fix in `res.send`, QUERY-method freshness support, `res.redirect` HTML structure, `app.render` null-options handling, `content-type`/`content-disposition` upgrades) against the actual code, since newly-landed code is the likeliest place for a regression. All of these matched their described behavior.
- Installed dependencies (`npm install`) and ran the full existing test suite: `npx mocha --require test/support/env --check-leaks test/ test/acceptance/` → **1261 passing, 0 failing**.
- Ran the suite under `nyc` coverage to find any lines/branches in `lib/` that no test exercises (a likely hiding spot for an unnoticed defect): coverage is 98.75% statements / 96.21% branches / 100% functions in `lib/`. The uncovered lines are `request.js:273` (an `Array.isArray` branch in `req.is`), `response.js:826,830,834` (the three `deprecate(...)` calls in `res.redirect` for missing/invalid arguments), and `view.js:53` (`options || {}` default branch). I inspected each by hand — they are defensive/deprecation branches, not logic errors; nothing in them produces incorrect behavior.
- Specifically stress-tested `acceptParams`/`normalizeType` in `utils.js` (a hand-rolled parser, the kind of code most likely to have an off-by-one) with malformed inputs (`"text/plain;invalid"`, `"text/plain;;q=0.5"`, `"text/plain;foo;q=0.9"`, etc.) via `node -e`; all produced correct, non-hanging results, and the loop's index always strictly advances (no infinite-loop risk on adversarial input).
- Checked `mime.contentType()` idempotency for `res.type()` → `res.set()` double-processing (`res.type()` computes a full content-type then `res.set()` recomputes via `mime.contentType()` again) — confirmed idempotent for both extension-based and already-full types, so no double-charset bug.
- Verified `res.send(Buffer.from(...))` forcing `Content-Type: application/octet-stream` when unset is intentional/tested behavior (`test/res.send.js:170-177`), not a regression from unifying `Buffer`/`Uint8Array` handling via `ArrayBuffer.isView`.
- Manually re-derived the `req.ips` getter's `reverse().pop()` logic against `proxyaddr.all()`'s documented ordering and against the doc example in the code — matches.

## Lower-confidence observation (not reported as a defect)

`req.host`'s multi-value `X-Forwarded-Host` handling uses `.trimEnd()` (`lib/request.js:427`) rather than `.trim()` when extracting the first comma-separated value. This only strips trailing whitespace before the comma, not any leading whitespace at the very start of the header value. All three existing tests (`test/req.hostname.js` "should remove OWS around comma", "should strip port number") only exercise trailing-space-before-comma and pass either way, so I can't confirm this diverges from intended behavior on any input a real proxy would send (leading OWS at the very start of a header field is normally stripped by the HTTP parser before it ever reaches this code). I'm not confident this is an actual defect, so I'm not listing it as one.

## Files read

- `lib/application.js`
- `lib/express.js`
- `lib/request.js`
- `lib/response.js`
- `lib/utils.js`
- `lib/view.js`
- `History.md` (top "Unreleased" section, for cross-checking recent changes)
- `package.json`
- `test/utils.js`
- `test/req.range.js`
- `test/req.host.js`, `test/req.hostname.js`
- `test/res.send.js`
- `test/res.render.js`, `test/app.render.js`
- `test/app.use.js`
- Full `test/` and `test/acceptance/` suites (executed, not individually read beyond the files above)
