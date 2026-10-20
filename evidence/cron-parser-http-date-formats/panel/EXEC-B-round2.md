# EXEC-B round 2: SHIP (high)

Code and tests are unchanged and behave as claimed at upstream tip 5033a31. Every round-1 finding (1-6) and the adopted optional items are fixed. Every behavioural claim in the new PR.md was run and is true. No new problem blocks submission. Two nits below, neither required.

My copy: scratch/panel2-cron-parser-http-date-formats-EXEC-B/ (c = tip clone, test part then src part applied with `git apply --include`; pristine = untouched tip; base = `git am` result). Fixed clone not touched: `git status --porcelain` there is empty (0 lines), HEAD 7e1aa55, one commit above 5033a31, upstream-check master still 5033a31.

## Steps (verbatim key lines)
- red (tests only, tip): `HTTP RFC 850` and `HTTP asctime, read as GMT` fail with `CronDate: unhandled timestamp: Sunday, 06-Nov-94 08:49:37 GMT` / `... Sun Nov  6 08:49:37 1994`, thrown at src/CronDate.ts:58. `Tests: 2 failed, 47 passed, 49 total`. Athens is non-UTC, so the GMT reading is really asserted.
- green (+ src hunk): `Tests: 49 passed, 49 total`.
- revert (`git apply -R` src only): `Tests: 2 failed, 47 passed, 49 total`, same two tests.
- suite: tip without patch `Tests: 346 passed, 346 total`; with patch `Test Suites: 7 passed, 7 total / Tests: 348 passed, 348 total`. So "348 (346 before)" in PR.md is true, and I ran the 346.
- full-check on my copy: eslint, prettier --check, build+tsd, jest --coverage all ran; `Tests: 348 passed, 348 total`, `full-check exit 0`.
- repro (confirmer's repro.ts, TZ=UTC): pristine tip exit=1, RFC 850 and asctime `actual=THROWS: CronDate: unhandled timestamp: ...`. Fixed exit=0, all three `actual=1994-11-06T08:49:37.000Z`.
- patch applies: `git am OUT/0001-*.patch` on a clean tip clone: `Applying: fix: accept the RFC 850 and asctime HTTP date formats as string dates`. Tree `89ed3826d21ddaf2f4d8bb3f28476bc2c1c782d5` equals the tree of HEAD in the fixed clone. Commit message identical. Hash differs (2bee142 vs 7e1aa55) only because my committer identity and date differ; the patch header names 7e1aa55 as the fixed clone's HEAD. Author `Andrew Stellman <andrew@stellman.com>`; 0 lines match signed-off/co-authored/assisted. Subject is 69 chars.

## Round-1 findings, checked
1. Stale base and counts: fixed. PR.md says "upstream master at 5033a31", "348 tests passed (346 before)". Patch parent is 5033a31. Logs are dated 2026-10-10 and show 348 / 49 / 2-failed. CONFIRMATION.md carries a correction note. The rebased box is ticked and true.
2. Ticks naming unrun commands: fixed. Unticked: `npm test`, `npm run lint`, `npm run format`, `npm run build`. Ticked: bug fix, coverage (full-check enforces thresholds), tests added, "All tests pass locally", rebased. The sentence "I did not run the npm scripts themselves." stays with the four boxes unticked, as SYNTHESIS allows.
3. Behaviour change stated: fixed. "These two formats used to throw. A caller who passes a zone-less asctime string that was meant as local time now gets a GMT date instead of an error." and the zero-padded sentence are present.
4. Placeholders: fixed. No `Fixes #` or "(issue number" in PR.md; Related Issues says `None.`; the `##` headings are identical to .github/pull_request_template.md (diff of the heading lists is empty).
5. Description length: fixed. The two diff-restating sentences are gone. Prose is about 220 words with the repro block, still above the 2-10 lines of the merged fixes (nit 1).
6. Commit body: identical to the SYNTHESIS text. Subject unchanged.
Optional adopted: ef172bd sentence present and true (`git show ef172bd`: README line "+- [`HTTP and RFC2822`](https://moment.github.io/luxon/#/parsing?id=http-and-rfc2822)"). "Expected" row moved out of the repro fence. "This is what `DateTime.fromHTTP` does; I did not add zone handling." present. Last line is exactly the disclosure line; no em dashes (0).

## PR.md claims, run
- README.md:85 "When using string dates, the following formats are supported:", :88 "- HTTP and RFC2822". src/CronDate.ts:54 is `this.#date.isValid || (this.#date = DateTime.fromHTTP(timestamp, dateOpts));`, the last link of the chain.
- Zero-padded day: `"Sun Nov 06 08:49:37 1994" UTC => 1994-11-06T08:49:37.000Z` (tip throws). True.
- Athens asctime: `"Sun Nov  6 08:49:37 1994" Europe/Athens => 1994-11-06T08:49:37.000Z`. True. Contrast `"Mon, 4 Jan 2021 10:00:00" Europe/Athens => 2021-01-04T08:00:00.000Z` (read in tz). True.
- "Inputs that parse today never reach it": structural (`isValid ||` chain) plus my own differential fuzz, 6000 mutated strings of 12 seeds x 3 zones, tip vs fixed: 271 valid on base, 5 changed, 0 changed where base was valid (all 5 are THROWS -> the asctime GMT date).

## 3 edge sets of my own, tip vs fixed (TZ=UTC; scripts claims.ts, fuzz.ts in my dir)
1. Near-misses stay rejected, same on both: `"   "`, `784111777`, `now`, trailing newline, `Sunday, 06-Nov-94 08:49:37 GMT+0200`, `Sun Nov 6 08:49:37 1994` (single space, unpadded day), `Sun Nov  6 8:49:37 1994`, `Sun Nov  6 08:49:37 94`, `Sunday, 06-Nov-1994 ...`, wrong weekday `Sat Feb 29 12:00:00 2000`, `Tue Feb 29 12:00:00 1900`. Invalid zone `Not/AZone` with either new form still throws the same error. (`""` returns now() on both; existing behaviour.)
2. Zones: asctime or RFC 850 with Asia/Kolkata, `UTC+5`, undefined tz, America/New_York `Sun Nov  6 01:30:00 1994` -> 01:30:00Z (GMT, not the NY repeated hour), Europe/London `Sun Mar 27 01:30:00 2022` -> 01:30:00Z, Pacific/Auckland `Thu Jan  1 00:00:00 1970` -> 1970-01-01T00:00:00Z. All newly parse as GMT; all threw on the tip.
3. Boundaries and parser: `Fri Dec 31 23:59:59 9999` -> 9999-12-31T23:59:59Z; `Tue Feb 29 12:00:00 2000` -> 2000-02-29T12:00:00Z. `CronExpressionParser.parse('0 * * * *', {currentDate: <asctime or RFC 850>, tz: 'Europe/Athens'})` -> `1994-11-06T09:00:00.000Z 1994-11-06T10:00:00.000Z` for both (tip throws).

## Side-effect rule
Affected: callers relying on a throw for an RFC 850 or asctime GMT string (very unlikely), and callers passing a zone-less asctime string meant as local time, who get GMT with no error (low; PR.md now says so). No existing working input changes (fuzz). Acceptable, not a drop.

## Nits (not required)
1. Description plus repro is longer than the 2-10 prose lines POLICY.md records. Every sentence is anchored, so I would not block on it.
2. Repro block prints `Error: CronDate: ...`, while the repro script prints `THROWS: CronDate: ...`. The message text is the same; `Error:` is the standard string form. Cosmetic.

## Not checked
GitHub tracker and closed items; the npm scripts by name; the operator's Mac command (`npm ci --ignore-scripts && TZ=UTC npx jest`); non-UTC `TZ` env; luxon versions other than the installed one; a textual merge with open PR #446; sideeffect.log is dated 2026-10-07 (old base) and PR.md no longer cites it, so I did not rerun it, I ran my own fuzz instead. Whether the maintainer prefers a README change.

| red | green | revert | suite | repro | edge | patch-applies | PASS/FAIL |
|---|---|---|---|---|---|---|---|
| 2 failed, 47 passed, 49 total (unhandled timestamp) | 49 passed, 49 total | 2 failed, 47 passed, 49 total | 346 base, 348 fixed; full-check exit 0 | tip exit=1, fixed exit=0 | 3 sets + 6000-string fuzz: 0 changed where base valid | yes, tree 89ed382 = fixed HEAD tree, 1 commit, author OK, no trailers | PASS |
