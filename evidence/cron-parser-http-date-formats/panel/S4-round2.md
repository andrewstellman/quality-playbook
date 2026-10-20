# S4 round 2: FIX-REQUIRED (medium)

Role S4, QA coverage, round 2. Rules file read first. Everything below was run in my own clone
`/work/batch/runs/cron-parser/scratch/panel2-cron-parser-http-date-formats-S4/` (clone of upstream-check master, tip 5033a31). The fixed clone was only read.

## Verdict
Code and tests are unchanged and sound. One sentence in PR.md is wrong in a way a maintainer can catch in ten seconds: it
cites commit `ef172bd`, which is not in `master`. Change it, then ship.

## Round-1 findings, status
1. Stale base and counts: FIXED. `git am` of the revised patch on 5033a31 applies cleanly (my clone: `51f20b9 fix: accept ... ` on `5033a31 chore: bump version`).
   My `run-tests` there: `Tests:       348 passed, 348 total`. PR.md now says 348 (346 before) and "master at 5033a31".
   Logs regenerated: `full-check.log` ends `Tests: 348 passed, 348 total` / `full-check exit 0`; `suite.log` 348; `green.log` 49 passed in
   CronDate.test.ts; `red.log` and `revert.log` show both new tests failing with `CronDate: unhandled timestamp` (`2 failed, 47 skipped/passed, 49 total`).
   The logs name the fixed clone (HEAD 7e1aa55 on 5033a31, clean `git status`). `diff rev0 patch` of the code part: identical.
   CONFIRMATION.md now carries a correction note for "No newer commits".
2. Test pins the GMT choice that the PR calls open: kept on purpose, test name states the choice, PR text offers to change both. Correctly not adopted.
3. Negative test for near-miss strings: not adopted, correctly. I re-ran near misses on the fixed code (tz undefined and Europe/Athens), all throw
   `CronDate: unhandled timestamp`: `Mon Nov  6 08:49:37 1994` (wrong weekday), `Sunday, 06-Nov-94 08:49:37 PST`, `... +0200`,
   `Sun Nov  6 08:49:37 1994 GMT`, `Sun, 06-Nov-94 08:49:37 GMT`, `Sunday, 06 Nov 1994 ...`, `Sunday, 06-Nov-1994 ...`, `Sun Nov  6 08:49:37.123 1994`.
   Those would test luxon, not this line. Existing 'invalid' test still goes through the new line.
4. Default-zone case: not adopted, correctly. Same result with tz undefined as with Athens (above).
5. luxon reliance: unchanged, fine. 6. Coverage 100% on CronDate.ts in `full-check.log`.

## New findings in the revision
1. MUST CHANGE: PR.md says "That list came from commit ef172bd". `ef172bd` is only on the head of PR 252, not in master:
   `git merge-base --is-ancestor ef172bd master` -> `ef172bd-NOT-in-master`; `git branch -a --contains ef172bd` -> `remotes/pr/252` only.
   The same diff is on master as `9332e6b readme: switched from moment to luxon (#252)` (`git log master -S'HTTP and RFC2822' -- README.md`
   lists only 9332e6b). Its diff adds "- [`HTTP and RFC2822`](https://moment.github.io/luxon/#/parsing?id=http-and-rfc2822)", so the sentence is
   true of the content, but `git show ef172bd` fails in a normal clone of the project. CONFIRMATION.md already says 9332e6b.
   Change to: "That list came from commit 9332e6b (#252), which linked 'HTTP and RFC2822' to luxon's parsing section of the same name."
   Note the current README line 88 has no link; the sentence says what the commit did, so it stays true.
2. Minor, optional: "All tests pass locally" is ticked while "All tests pass (`npm test`)" is not. The closing sentence explains it
   (full check, not the npm scripts). Consistent enough; I would not block.
3. `sideeffect.log` was not regenerated (dated 2026-10-07, run on 5b08cdf). PR.md no longer cites it and the code line is identical at the tip, so no text depends on it.
   The rest of the PR text claims I re-ran: Athens asctime gives `1994-11-06T08:49:37.000Z`; zero-padded `Sun Nov 06 08:49:37 1994` is accepted (above).
   Through the parser: `CronExpressionParser.parse('0 * * * *', {currentDate:'Sun Nov  6 08:49:37 1994', tz:'Europe/Athens'}).next().toISOString()` -> `1994-11-06T09:00:00.000Z`
   (08:49:37Z is 10:49 in Athens, next hour 11:00 Athens = 09:00Z), so the parser path reads it as GMT as stated.

## Side-effect rule
Unchanged from round 1. Affected: callers that relied on the throw for RFC 850 or asctime strings (very unlikely), and callers who pass a zone-less
asctime string meant as local time (now GMT, no error). The revised PR.md states both in one sentence. Inputs that parse today never reach the new line
(last link of the `||` chain). Acceptable; not a drop.

## Not checked
- Whether open PR #446 conflicts at the tip. Closed issues and PRs on the forge. Node versions other than the installed one.
- I did not run `full-check` myself (only `run-tests`); I read `full-check.log` and the logs listed above, not re-ran them.
- luxon versions other than the installed one. The operator's Mac command.
