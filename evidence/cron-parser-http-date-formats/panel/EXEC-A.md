# EXEC-A: FIX-REQUIRED (high)

Code and test are correct and the mechanics all pass. The PR text is stale against the current upstream tip and needs three text edits. No source or test change is needed.

Copy used: /work/batch/runs/cron-parser/scratch/panel-cron-parser-http-date-formats-EXEC-A (cp -a of the fix clone; base HEAD~1 = 5b08cdf, fix = b09b6a6). Tip clone with the patch applied by `git am`: .../panel-cron-parser-http-date-formats-EXEC-A/tipclone (upstream-check master 5033a31).

## Executed steps (verbatim excerpts)

RED (test part only: `git checkout HEAD~1 -- src/CronDate.ts`, tests kept; run-tests with --runTestsByPath tests/CronDate.test.ts):
  ● CronDate › parse cron date formats with another timezone › HTTP RFC 850
    CronDate: unhandled timestamp: Sunday, 06-Nov-94 08:49:37 GMT
  ● ... › HTTP asctime, read as GMT
    CronDate: unhandled timestamp: Sun Nov  6 08:49:37 1994
  Tests:       2 failed, 47 passed, 49 total
Reason is the claimed one: the constructor throws at src/CronDate.ts:58. The assertions (tests/CronDate.test.ts:447-455) expect '1994-11-06T08:49:37.000Z' with tz Europe/Athens, so they also pin the "read as GMT" choice. Not a wrong-reason failure.

GREEN (source restored): `Tests: 49 passed, 49 total`
REVERT (only src/CronDate.ts reverted): same 2 failures, `Tests: 2 failed, 47 passed, 49 total`
SUITE at fix base: `Tests: 340 passed, 340 total`
SUITE at upstream tip 5033a31 + patch (git am applied cleanly, author Andrew Stellman, no trailers): `Tests: 348 passed, 348 total`
FULL-CHECK at tip + patch: ends `full-check exit 0`, coverage 100/100/100/100.

REPRO (confirmer's repro.ts copied to probe/repro.ts, import path changed to ../src, TZ=UTC ts-node):
  RFC 850: actual=1994-11-06T08:49:37.000Z expected=1994-11-06T08:49:37.000Z
  asctime: actual=1994-11-06T08:49:37.000Z expected=1994-11-06T08:49:37.000Z
  exit=0. With src/CronDate.ts reverted: 2 lines THROWS (grep -c THROWS = 2).

Extra probes (my own, probe/p.ts, probe/q.ts):
  fromRFC2822 on the three forms: true false false (so IMF form works only through RFC 2822, as the PR says).
  'Sun Nov  6 08:49:37 1994' tz Europe/Athens -> 1994-11-06T08:49:37.000Z; tz America/New_York -> same instant.
  'Sun Nov 06 08:49:37 1994' (zero-padded day) also parses; trailing space throws; 'Monday, 06-Nov-94 ...' (wrong weekday) throws; '... 08:49:37 UTC' and no zone on RFC 850 throw.
  CronExpressionParser.parse('0 0 * * *', {currentDate:'Sun Nov  6 08:49:37 1994', tz:'America/New_York'}).next() -> Mon Nov 07 1994 05:00:00 GMT (midnight New York), no error.

## Side-effect rule
Inputs reach fromHTTP only after fromISO, fromRFC2822, fromSQL and fromFormat all returned invalid, so any string that parsed before is unchanged. sideeffect.log: "inputs that parsed before and now differ: 0". Changed behaviour: only strings that threw now return a date. Affected: callers who relied on a throw for RFC 850 or asctime strings (catch and fall back, or validate input by trying). Likelihood: very low; no report in about 5 years. The one real semantic choice is that asctime (no zone) is read as GMT, not in `tz`, unlike RFC 2822 without offset. The PR names this and offers to change it. That is honest; I rate it acceptable, since luxon fromHTTP defines it. Not a drop.

## Findings

1. PR.md "Additional Notes": "The change is made on upstream master at 5b08cdf." is stale. Upstream tip is 5033a31 (4 newer commits, including src/CronExpressionParser.ts and src/CronFileParser.ts changes). The patch applies cleanly and passes there, but the sentence is false for today. Replace with:
   "The change is made on upstream master at 5033a31."
   (rebase the branch on that tip before the commit hash is quoted anywhere.)

2. PR.md "Testing": "...it ended `full-check exit 0` with 340 tests passed (338 before)." The 340/338 counts come from the old base. At the tip I ran: 348 passed (346 before), full-check exit 0. Replace with:
   "...it ended `full-check exit 0` with 348 tests passed (346 before)."
   The operator's own full-check.log and suite.log in OUT are from 5b08cdf too (340); re-run at the tip and replace them, or the log will contradict the text. (script-check-round1.txt already shows 348 at the tip.)

3. PR.md box "- [x] All tests pass (`npm test`)" and "- [x] ESLint checks pass (`npm run lint`)", "- [x] Prettier ... (`npm run format`)", "- [x] TypeScript compilation ... (`npm run build`)": the same PR says "I did not run the npm scripts themselves." Rule: tick only boxes true and checked by a command you ran. The box labels name commands that were not run. Minimum change: keep the ticks only if the operator runs those npm scripts on the Mac before submitting (`npm run lint`, `npm run format` is a write command, check git diff after), otherwise untick the four named boxes and keep the Testing sentence. I did not run the npm scripts either. Also the unticked-by-design boxes are fine.

4. (Minor, optional) Leftover template placeholders: Description ends with "Fixes # (issue number if applicable)" and Related Issues has "Closes #", "Related to #", "Fixes #". GitHub ignores empty ones, but "Fixes #" in the body is noise. The rules say keep headings; the placeholder bullet text may stay. If edited, replace the Description line with nothing and the Related Issues list with "- None known. Searched the open-report export of 2026-10-05 (known_open_bugs.md); nothing about string date formats." Only keep that sentence if the operator accepts that the search was limited to that export (closed issues were not searched; CONFIRMATION says so).

## Weak points not blocking
- Value: IMF-fixdate (what servers send now) already works; a maintainer may answer "docs only". PR.md already says "If only the RFC 1123 form was meant by 'HTTP', the README line is what should change instead." Good.
- README is read, not changed. README.md:85-88: "When using string dates, the following formats are supported:" / "- HTTP and RFC2822". Quote and line numbers in PR.md are correct (87-89 list, 88 is HTTP).
- Commit body wraps at 80 and has no trailers; matches the rules.

## Not checked
- npm scripts (`npm test`, `npm run lint`) on a fresh `npm ci` checkout (rules forbid npm install here).
- The operator's Mac command `npm ci --ignore-scripts && TZ=UTC npx jest`.
- Any luxon version other than the installed 3.7.2 (package.json "^3.7.2").
- Closed issues or PRs on the forge; whether a maintainer wants this at all.
- Other time zones with DST for asctime beyond Europe/Athens, America/New_York, UTC.

## Table
| red | green | revert | suite | repro | PASS/FAIL |
|---|---|---|---|---|---|
| 2 failed, "unhandled timestamp", correct reason | 49/49 | 2 failed again | 340/340 at base; 348/348 and full-check exit 0 at tip 5033a31 | exit 0 with fix; 2 THROWS without | PASS (code); PR text FAIL until findings 1-3 are fixed |
