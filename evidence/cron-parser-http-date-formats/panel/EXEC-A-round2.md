# EXEC-A round 2: FIX-REQUIRED (high)

Code, tests, patch and logs are all correct at the tip. One text fix is needed: PR.md cites commit ef172bd, which is not in master's history (the merged commit is 9332e6b, #252). Everything else from round 1 is fixed.

Scratch: /work/batch/runs/cron-parser/scratch/panel2-cron-parser-http-date-formats-EXEC-A/ (work = tip + test part, then source part applied with `git apply --include`; am = tip + `git am`; chk = pristine tip). Fixed clone not modified.

## Executed steps (verbatim excerpts)

RED (tests only, `git apply --include='tests/*'`, then run-tests --runTestsByPath tests/CronDate.test.ts):
  ● CronDate › parse cron date formats with another timezone › HTTP RFC 850
    CronDate: unhandled timestamp: Sunday, 06-Nov-94 08:49:37 GMT
    > 58 |       throw new Error(`CronDate: unhandled timestamp: ${timestamp}`);
      at Object.<anonymous> (tests/CronDate.test.ts:448:17)
  ● ... › HTTP asctime, read as GMT
    CronDate: unhandled timestamp: Sun Nov  6 08:49:37 1994
  Tests:       2 failed, 47 passed, 49 total
  The failure is the constructor throw at src/CronDate.ts:58, before the toBe assertion. Claimed reason.
GREEN (`git apply --include='src/*'`): Tests: 49 passed, 49 total
REVERT (`git checkout -- src/CronDate.ts`, tests kept): same two "unhandled timestamp" failures, Tests: 2 failed, 47 passed, 49 total
SUITE (work, run-tests): Tests: 348 passed, 348 total. Pristine tip (chk): Tests: 346 passed, 346 total.
FULL-CHECK on the am clone (clean tree): ends `full-check exit 0`, coverage 100/100/100/100, Tests: 348 passed, 348 total.
REPRO (confirmer's repro.ts copied unchanged into each clone, TZ=UTC ts-node):
  fixed: IMF, RFC 850, asctime all actual=1994-11-06T08:49:37.000Z, exit=0
  base:  RFC 850 and asctime "THROWS: CronDate: unhandled timestamp: ...", base-exit=1

## Patch and commit
- `git am OUT/0001-*.patch` on a clean clone of upstream-check master (5033a31): applies; `git apply --check` also ok.
- Tree of am clone 89ed3826d21ddaf2f4d8bb3f28476bc2c1c782d5 = tree of fixed-clone HEAD (same hash). Commit messages identical (cmp). `git format-patch -1 --stdout` of the fixed clone is byte-identical to OUT/0001-*.patch.
- Fixed clone: HEAD~1 = 5033a312f1fe04665060eacf4378f16c48ca4ea8 = upstream-check master; 1 commit above it; author and committer Andrew Stellman <andrew@stellman.com>; 0 lines matching signed-off|co-authored|assisted; `git status --porcelain` prints nothing (0 lines).
- Subject is 69 characters, same as the PR title. No non-ASCII in PR.md or the commit message. Last line of PR.md is the exact disclosure line.
- OUT logs: suite.log 348/348, green.log 49/49, red.log and revert.log show the two failures, full-check.log ends `full-check exit 0` (348). All from the tip.

## Round-1 findings (SYNTHESIS) checked
1. Stale base and counts: FIXED. PR.md says "upstream master at 5033a31" and "348 tests passed (346 before)"; I measured 348 and 346. "Rebased" box ticked, true. CONFIRMATION.md keeps its old "No newer commits" line but now has a dated correction at the bottom; acceptable (not PR text).
2. Unticked npm boxes: FIXED. `npm test`, lint, format, build boxes are unticked; "I did not run the npm scripts themselves." stays; no contradiction. Ticked: bug fix, tests added, "All tests pass locally" (run-tests), coverage (full-check thresholds), rebased. All backed by a command I re-ran.
3. Behaviour sentence: FIXED and true. "These two formats used to throw..." is correct (base throws, fixed returns 1994-11-06T08:49:37.000Z for Europe/Athens and America/New_York). Zero-padded day `Sun Nov 06 08:49:37 1994` throws at base, parses on fix (UTC and Athens).
4. Placeholders: FIXED. "Fixes #" gone, Related Issues says "None." All template headings and all template checkbox lines are present (diffed against .github/pull_request_template.md).
5. Description length: FIXED. 8 prose lines outside the code block; the two diff-restating sentences are gone.
6. Commit body: FIXED. Matches the O5 text in SYNTHESIS exactly; GMT decision present; no trailers.
Optional items taken: repro block now has only actual lines; "This is what DateTime.fromHTTP does; I did not add zone handling." present; ef172bd sentence present (see problem below).

## Behavioural claims in PR.md, each run
- Three repro lines: IMF ok; RFC 850 and asctime throw at base with the quoted message; fixed gives the date (output above).
- luxon: `DateTime.fromHTTP` of both strings (zone UTC and Europe/Athens, then toUTC) = 1994-11-06T08:49:37.000Z.
- `new CronDate('Sun Nov  6 08:49:37 1994','Europe/Athens')` = 1994-11-06T08:49:37.000Z. Same instant for America/New_York.
- `Mon, 4 Jan 2021 10:00:00` with Europe/Athens = 2021-01-04T08:00:00.000Z, so it is read in tz. True.
- Parser: CronExpressionParser.parse('0 0 * * *', {currentDate:'Sun Nov  6 08:49:37 1994', tz:'America/New_York'}).next() = Mon Nov 07 1994 05:00:00 GMT (NY midnight). Throws at base.
- README.md:85 "When using string dates, the following formats are supported:" and README.md:88 "- HTTP and RFC2822": grep -n confirms. `src/CronDate.ts:54` is the fromHTTP line, last in the chain. Test names and the 2 new tests match the text.
- Side effect: my differential run, base vs fixed, 3 zones x about 4000 mutated strings (12057 results, the empty string excluded because it means "now"): 39 results differ, all of them "THROWS" at base; 0 differ where base returned a value. The code order (fromHTTP last) says the same.

## New problem
1. PR.md Description: "That list came from commit ef172bd". `git merge-base --is-ancestor ef172bd master` says not an ancestor; `git for-each-ref --contains ef172bd` in upstream-check gives only refs/remotes/pr/252. The commit on master is 9332e6b "readme: switched from moment to luxon (#252)"; `git log -S'HTTP and RFC2822' -- README.md` lists only 9332e6b, and its README diff has the line ``+- [`HTTP and RFC2822`](https://moment.github.io/luxon/#/parsing?id=http-and-rfc2822)``. A maintainer running `git show ef172bd` on master may not find it. Change to: "That list came from commit 9332e6b (#252), which linked "HTTP and RFC2822" to luxon's parsing section of the same name." (or delete the sentence; it is optional).

## Side-effect rule
Only strings that threw now return a date. Affected: callers who rely on the throw for RFC 850 or asctime input, and callers who pass zone-less asctime meant as local time (now read as GMT, no error). The PR states both. Likelihood low. Acceptable, not a drop.

## Not checked
npm scripts by name, and the Mac command (`npm ci --ignore-scripts && TZ=UTC npx jest`); luxon other than the installed one; closed issues and PRs on the forge; whether upstream master moved after the last refetch (upstream-check master is 5033a31); whether a maintainer prefers a README change; RFC 850 two-digit-year pivot.

| red | green | revert | suite | repro | patch-applies | PASS/FAIL |
|---|---|---|---|---|---|---|
| 2 failed, "unhandled timestamp", right reason | 49/49 | 2 failed again | 348/348 (346 at tip); full-check exit 0 | exit 0 fixed, exit 1 base | yes, tree and message identical to fixed HEAD | code PASS; PR text FAIL until the ef172bd citation is changed to 9332e6b |
