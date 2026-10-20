# EXEC-B: FIX-REQUIRED (high)

Code change and tests are sound. The PR text is stale and has tick-box claims that were not run. Fix the text, rebase the patch onto the tip, then SHIP. Not a security finding.

## Table (my copy: scratch/panel-cron-parser-http-date-formats-EXEC-B, base = HEAD~1 = 5b08cdf)

| red | green | revert | suite | repro | PASS/FAIL |
|---|---|---|---|---|---|
| tests only on base: 2 failed, 47 skipped, 49 total; both "CronDate: unhandled timestamp: ..." thrown at src/CronDate.ts:58 from the `new CronDate(...)` line in the test (tests/CronDate.test.ts:448, :453) | + src hunk: `Tests: 49 passed, 49 total` | `git apply -R` src hunk: `Tests: 2 failed, 47 passed, 49 total` (same two HTTP tests) | base 338 passed; fixed 340 passed, 340 total | base: RFC 850 and asctime THROW, exit=1; fixed: all three `actual=1994-11-06T08:49:37.000Z`, exit=0 | PASS |

Assertion read: `new CronDate('Sunday, 06-Nov-94 08:49:37 GMT', 'Europe/Athens').toISOString()` must be `1994-11-06T08:49:37.000Z`. Same for `'Sun Nov  6 08:49:37 1994'`. Athens is non-UTC, so the GMT reading is really tested (a tz-local reading would give 06:49:37Z). Red fails for the claimed reason (throw), not an assertion typo. Used `--runTestsByPath <abs path>` as in red.log; a relative path ran 291 tests and was useless, so I redid it.

Rebase check (rule 18): I cloned upstream-check master (5033a31), `git am` of the packet patch applied cleanly. Test file 49 passed; full suite `Tests: 348 passed, 348 total`; `full-check` on that clone ends `full-check exit 0`. Tip vs 5b08cdf touches src/CronExpressionParser.ts and src/CronFileParser.ts only, not src/CronDate.ts. #446 (open) edits src/CronDate.ts but its diff has no fromISO/fromRFC/fromHTTP lines; I did not try a textual merge.

## 3 edge sets, base vs fixed (TZ=UTC, ts-node; scripts edge.ts, edge2.ts in my dir)

1. Strictness (all identical on base and fixed, all THROW, so no loosening): wrong weekday `Monday, 06-Nov-94 ...`, `Mon Nov  6 ... 1994`; `... 08:49:37 PST`; `... +0100`; lowercase `sunday, 06-nov-94 08:49:37 gmt`; padded `" Sun Nov  6 08:49:37 1994 "`; `Sun Nov  6 08:49:37 1994 GMT`; `24:00:00`; `08:49:60`; `Tue Feb 29 12:00:00 1994`. Only well-formed GMT forms are newly accepted.
2. Correct-weekday dates (base THROWS, fixed parses, tz Europe/Athens): `Wednesday, 16-Nov-94 ...` and `Wed Nov 16 ...` -> 1994-11-16T08:49:37.000Z (two-digit day ok); `Tuesday, 29-Feb-00` / `Tue Feb 29 ... 2000` -> 2000-02-29T08:49:37.000Z; `Thu Jan  1 ... 1970`; `Saturday, 10-Oct-26` -> 2026-10-10. Two-digit year pivot is luxon's: `06-Nov-69` -> 1969, `06-Nov-49` -> 2049, `06-Nov-50` -> 2050. This is luxon behaviour, not new code; RFC 9110 says a 50-year-ahead date should read as past, so 50 and 49 differ from the RFC. Not a reason to hold the PR; do not claim RFC-exact year handling.
3. Through the parser (base THROWS, fixed works): `CronExpressionParser.parse('0 * * * *', {currentDate: 'Sun Nov  6 08:49:37 1994', tz: 'Europe/Athens'})` -> first next() = 1994-11-06T09:00:00.000Z (= 11:00 Athens, the next hour after 10:49:37 local); RFC 850 string gives the same. `startDate`/`endDate` asctime strings 08:49:37..11:49:37 UTC gave `09:00Z 10:00Z 11:00Z`. Also `Sun Nov  6 01:30:00 1994` with America/New_York -> 01:30:00Z (read as GMT, not NY local, so NOT the NY repeated hour). `tz` undefined also works. Already-working IMF string unchanged in all zones.

Side effect rule: inputs that parsed before parse to the same instant (sideeffect.log: "inputs that parsed before and now differ: 0"; the new call is last in the `||` chain, so it runs only after four failures). Affected: someone who relied on the constructor/`currentDate` throwing for exactly an RFC 850 or asctime GMT string, e.g. as validation. Likelihood: very low. Nobody is hurt silently; they now get a date instead of an Error. Not a drop.

## Findings

1. PR.md:111 (Additional Notes) says "The change is made on upstream master at 5b08cdf." Master is now 5033a31 and the rules require the tip as base. Replace the sentence with: `The change applies cleanly on upstream master at 5033a31.` And rebase the patch (`git am` onto 5033a31 works; I did it, parent becomes 5033a31, new hash). CONFIRMATION.md ("upstream tip. No newer commits") is stale too, but it is not part of the PR.
2. PR.md Testing paragraph: "ended `full-check exit 0` with 340 tests passed (338 before)". At the tip the numbers are 348 passed (I ran full-check on the rebased clone: `Tests: 348 passed, 348 total`, `full-check exit 0`); base at the tip is 346 by subtraction, which I did NOT run. Replace with: `... ended full-check exit 0 with 348 tests passed on upstream master at 5033a31 with this change (the two new tests included).` Do not give a "before" count unless it is run.
3. PR.md ticks vs the rules ("tick only the boxes that are true and were checked by a command you ran"). The text itself says "I did not run the npm scripts themselves", yet it ticks `[x] All tests pass (`npm test`)`, `[x] ESLint checks pass (`npm run lint`)`, `[x] Prettier formatting applied (`npm run format`)`, `[x] TypeScript compilation successful (`npm run build`)`. The box labels name npm commands that were not run (`npm run format` also writes files; the check was `prettier --check`). Either untick those four and keep `[x] I have added tests for my changes` and `[x] Code coverage is maintained or improved` (full-check enforces the thresholds, 100%), or append to each box a plain note such as `(ran via full-check: eslint)`. Simplest: untick the four, and let the Testing sentence carry the facts.
4. PR.md Description has the template placeholder `Fixes # (issue number if applicable)` left unchanged. Replace with `No issue filed.` (policy: issue not required for a bug fix; I found no duplicate, but the tracker was not searched beyond known_open_bugs.md, so do not write "no duplicate").
5. PR.md: "`Mon, 4 Jan 2021 10:00:00` (RFC 2822 without offset), which is read in the `tz` option" is true (sideeffect.log Athens: 08:00:00Z). Keep. "13 inputs in three zones" matches sideeffect.log. Keep. The README quote lines (85, 88) match README.md in the clone. Keep.
6. Optional, not required: asctime is read as GMT by luxon, and RFC 9110 requires HTTP dates in GMT, so the PR's "read as GMT" is defensible. Test name `HTTP asctime, read as GMT` is fine.

## Risks that remain (maintainer pushback, not defects)
- Maintainer may say "docs only": README "HTTP" may mean only the IMF form that already works. The PR already offers this at the end; keep it. Low value, one line of code, two tests.

## Not checked
- GitHub tracker, closed issues/PRs (not reachable). Textual merge with open #446 and #444. Behaviour under a non-UTC `TZ` env (all runs TZ=UTC). The `dist` build output. Base test count at the tip (346) was not run. Commit trailers/author in the packet patch: seen "Andrew Stellman <andrew@stellman.com>", no Co-Authored-By/Signed-off-by in the shown header; I did not re-run the script check.
