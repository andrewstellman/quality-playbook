# Code Review: express `lib/` (commit 9a34acf03cb818ff3f8bc40e44176e277a25cbb9)

## Summary

No defects found that I am confident are real.

## Method

- Read every file in `lib/` line by line: `application.js` (631 lines), `express.js` (81), `request.js` (527), `response.js` (1049), `utils.js` (271), `view.js` (205) — the full 2,764-line scope.
- For each public method, checked the implementation against its own doc comment (parameter contracts, documented return values, documented edge-case handling such as HEAD requests, 204/304/205 status stripping, trust-proxy inheritance, etc.).
- Ran the project's own test suite from the checkout (installed dependencies with `npm install`, ran `npm test`, which runs `mocha` over `test/` and `test/acceptance/`): **1261 passing, 0 failing**.
- Ran coverage (`nyc`) over the same run: `lib/` overall 98.75% statements / 96.21% branches / 100% functions / 99.61% lines. The only uncovered lines (`request.js:273`, `response.js:826/830/834`, `view.js:53`) are untested branches of otherwise-correct code (e.g. the multi-arg fallback path in `req.is`), not defects.
- Ran `eslint lib/` with the repo's own config: no findings.
- Manually traced a few of the more intricate routines by hand and then verified with small Node snippets, since these are easy to get subtly wrong and aren't fully pinned down by the doc comments alone:
  - `utils.js`'s hand-rolled `acceptParams` (index-based scanner replacing the old regex/`split` version) — traced `"text/html;q=0.9"` and `"text/html;level=1;q=0.9"` by hand, worried the loop's starting `index` (which points at the delimiting `;`, not past it) would include the semicolon in the first extracted key. Re-traced carefully: `String.prototype.indexOf(';', index)` is inclusive of `index` itself, so it immediately re-finds the same `;`, which trips the `splitIndex > endIndex` correction branch and advances `index` past it before the key is ever sliced. Confirmed correct with `normalizeType()` snippets — output matched expectations in all cases tried.
  - `application.js`'s "trust proxy inherit back-compat" logic in the `mount` handler — confirmed by mounting a child app under a parent with `trust proxy` set that the child inherits the parent's compiled `trust proxy fn`.
  - `response.js`'s `res.cookie` `maxAge` → `Expires`/`Max-Age` conversion — confirmed with a snippet that `maxAge: 60000` produces `Max-Age=60` and a correct `Expires` value.

None of these turned up a discrepancy between documented/intended behavior and actual behavior.

## Files read

- `lib/application.js`
- `lib/express.js`
- `lib/request.js`
- `lib/response.js`
- `lib/utils.js`
- `lib/view.js`
- `package.json` (for dependency versions, to check API compatibility assumptions e.g. `content-disposition@^2.0.1`'s `.create()`/`.parse()` API)
- Ran, but did not need to read in full, the existing test suite under `test/` and `test/acceptance/` as a falsification check.

No defects meeting the confidence bar in the task instructions were found in this scope.
