# Code review: express `lib/` (pinned commit 9a34acf03cb818ff3f8bc40e44176e277a25cbb9)

## Scope
`lib/application.js`, `lib/express.js`, `lib/request.js`, `lib/response.js`, `lib/utils.js`, `lib/view.js`.

## Method

1. Read all six files in full.
2. Copied the checkout into the work directory, ran `npm install`, and ran the project's own test suite: `mocha --require test/support/env --reporter dot --check-leaks test/ test/acceptance/` → **1261 passing, 0 failing**.
3. Pulled the published `express@5.2.1` tarball from npm (`npm pack express@5.2.1`) and diffed its `lib/` against the checkout to see exactly how this pinned commit differs from the last tagged release.
4. Cross-checked every diff against this repo's own `History.md` "Unreleased Changes" section, which documents each change with a PR reference (Transfer-Encoding/Content-Length conflict fix, QUERY-method freshness support, `res.redirect()` HTML body changes, `app.render(name, null, cb)` handling, `content-type`/`content-disposition` dependency upgrades, the `res.send()` string-handling micro-optimization, and the CVE-2024-51999 revert for the extended query parser). Every diff matched its changelog description; none looked like it deviated from the stated intent.
5. Wrote and ran small standalone scripts (real `http` requests against a live `express()` app) to directly exercise the four riskiest recent changes:
   - `res.send()` with `Transfer-Encoding: chunked` set beforehand → confirmed `Content-Length` is *not* added (only `Transfer-Encoding` present).
   - `app.render('view', null, cb)` → confirmed no throw and correct locals merge.
   - A `QUERY` request with a matching `If-None-Match` → confirmed `304` is returned.
   - `res.attachment('user.html')` → confirmed the `Content-Disposition` filename is unquoted for a valid HTTP token, matching the `content-disposition@^2` upgrade note.
   - Setting an unparsable `Content-Type` value → confirmed no throw, and observed the expected fallback behavior in `res.send()`/`res.set()`.

## Findings

No defects found. I read every function in scope, exercised the four areas most recently touched (Content-Length/Transfer-Encoding interaction, QUERY-method freshness, `app.render` null-options handling, and attachment/content-type header generation) with live requests, and ran the full upstream test suite (1261/1261 passing, no leak warnings). The code in `lib/` matches its own documented intent in `History.md` line-for-line for every recent change, and I found no logic errors, edge-case mishandling, error-handling mistakes, concurrency issues, or API misuse that I'm confident is a real, reportable defect.

I did look closely at several spots that are easy to get wrong in this kind of code and confirmed they are correct as written:
- `res.send()`'s string/Buffer branching and Content-Length calculation (`lib/response.js:126-222`) — correctly buffers only when needed (ETag generation or length ≥ 1000) and correctly skips `Content-Length` when `Transfer-Encoding` is present.
- `req.host`/`req.hostname`/`req.ip`/`req.ips`/`req.protocol` trust-proxy getters (`lib/request.js:297-458`) — consistent use of `trust proxy fn` and correct IPv6-literal handling in `hostname`.
- `app.use()`'s path/fn disambiguation and mounted-app prototype restoration (`lib/application.js:190-244`) — correctly restores `req`/`res` prototypes after a nested app's `handle()` completes, including on error.
- `utils.acceptParams()` (`lib/utils.js:89-120`) — the semicolon/equals scanning loop handles values containing `=`/`;` inside quoted-less params correctly for the tested cases.
- `View.prototype.resolve`/`lookup` (`lib/view.js:104-187`) — directory-vs-file resolution and the array-of-roots iteration look correct.

## Files read

- `/tmp/control/express/lib/application.js`
- `/tmp/control/express/lib/express.js`
- `/tmp/control/express/lib/request.js`
- `/tmp/control/express/lib/response.js`
- `/tmp/control/express/lib/utils.js`
- `/tmp/control/express/lib/view.js`
- `/tmp/control/express/package.json`
- `/tmp/control/express/History.md`
- `/tmp/control/express/test/` (directory listing, and executed the full suite)
- Published `express@5.2.1` tarball's `lib/` (fetched via `npm pack`, used only as a diff baseline, not treated as ground truth over the checkout)
