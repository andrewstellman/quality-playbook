# O3 round 2: FIX-REQUIRED (high)

Role: O3, correctness. Code and tests are unchanged and I could not break them. One new factual error in PR.md (a commit hash that is not on master). Everything else from round 1 is fixed. The hash fix is a one-token edit.

## What I did
My copy: /work/batch/runs/cron-parser/scratch/panel2-cron-parser-http-date-formats-O3/tip (clone of upstream-check master, `git am` of OUT/0001-*.patch). Fixed clone untouched.

1. `git am` on 5033a31: "Applying: fix: accept the RFC 850 and asctime HTTP date formats as string dates", clean. Diff against the fixed clone's `git diff HEAD~1`: identical. Patch body vs `git format-patch -1` of the fixed clone: identical (diff of everything but the From line). Author Andrew Stellman, no Co-Authored-By or Signed-off-by (grep count 0). Parent of the commit is 5033a312.
2. `bin/run-tests` on patched tip: `Tests: 348 passed, 348 total`. On HEAD~1 (5033a31): `Tests: 346 passed, 346 total`. So "348 tests passed (346 before)" is true. OUT/full-check.log ends `full-check exit 0`, CronDate.ts 100/100/100/100. I did not re-run full-check myself this round (round 1 I did, same code).
3. red.log: `Tests: 2 failed, 47 skipped, 49 total` with "CronDate: unhandled timestamp: Sun Nov  6 08:49:37 1994" at tests/CronDate.test.ts:453; revert.log `2 failed, 47 passed`; green.log `49 passed`. Consistent with the PR sentence.
4. Edge script (t.ts in my scratch, ts-node, TZ=UTC), verbatim excerpts:
```
"Sun Nov  6 08:49:37 1994" Europe/Athens -> 1994-11-06T08:49:37.000Z
"Sun Nov 06 08:49:37 1994" Europe/Athens -> 1994-11-06T08:49:37.000Z
"Mon, 4 Jan 2021 10:00:00" Europe/Athens -> 2021-01-04T08:00:00.000Z
"Sun Nov  6 08:49:37 1994" undefined -> 1994-11-06T08:49:37.000Z
"Sunday, 06-Nov-94 08:49:37 UTC" UTC -> THROWS CronDate: unhandled timestamp: ...
"Sunday, 06-Nov-94 08:49:37 +0200" UTC -> THROWS
"Sun Nov  6 08:49:37 1994 GMT" UTC -> THROWS
"Sun Nov  6 24:00:00 1994" / "08:49:60" / trailing space / trailing newline / 5-digit year / 4-digit RFC 850 year -> THROWS
"Sun Nov 6 08:49:37 1994" UTC -> THROWS   (one space)
athens: new CronDate('Sun Mar 27 01:30:00 2022','Europe/Athens') -> 2022-03-27T01:30:00.000Z, hour 4 (DST day, no error)
```
   Also: `Tue Feb 29 2000` parses, `Sat Feb 29 2000` is rejected (luxon weekday check, same as RFC 2822). IMF form is valid for both fromRFC2822 and fromHTTP (`true true`), so "only works because it is also valid RFC 2822" is true.
5. Parser end to end: `currentDate: 'Sun Nov  6 08:49:37 1994', tz: 'America/New_York'`, `*/30 * * * *` gives 09:00 and 09:30 GMT. `startDate` RFC 850, `endDate` asctime, tz Asia/Tokyo, `0 0 * * *`: 7 dates, 1994-11-06T15:00Z to 1994-11-12T15:00Z. endDate before currentDate gives "Out of the time span range" (existing behaviour). Date, number and luxon DateTime inputs unchanged.
6. Side-effect rule: `fromHTTP` is the last link of an `isValid ||` chain (src/CronDate.ts:54), so any string valid before takes the old branch by construction. OUT/sideeffect.log: `inputs that parsed before and now differ: 0` (26 rows). Round 1 fuzz (48000 mutations, 0 diffs) covers the same code. I did not re-fuzz. No reason to drop. Affected callers: those who relied on a throw for these two formats (very unlikely) and those who pass zone-less asctime meant as local time (low; now stated in PR.md).

## Round 1 findings, fixed in text?
- F1 stale base and counts: fixed. PR.md says "upstream master at 5033a31", "348 tests passed (346 before)", numbers verified above. CONFIRMATION.md has a correction line at the end. (Its body still says "= upstream tip", but the correction is appended; fine, not PR text.)
- F2 ticked boxes: fixed. `npm test`, lint, format, build boxes are unticked. "All tests pass locally" is ticked (jest ran), "rebased" ticked (done). Prettier ran as `--check` in bin/full-check line 11, matching the PR wording.
- F3 placeholders: fixed. "Fixes #" removed, Related Issues is "None.", headings kept. `diff` against .github/pull_request_template.md shows only intended changes.
- F4 asctime zone: now stated twice, with the offer to change. Wording matches what I ran (Athens gives 08:49:37Z, RFC 2822 without offset is read in tz).
- F5 two-digit year: not claimed in the text. Good.
- F6 #446: not checked; I did not read the #446 diff.

## New findings
1. FIX-REQUIRED (high). PR.md cites commit `ef172bd`. That commit is not on master. In upstream-check: `git merge-base --is-ancestor ef172bd master` prints `not-on-master`, and `git for-each-ref --contains ef172bd` gives only `refs/remotes/pr/252`. The merged commit with the same change is `9332e6b9c54ecb93d82ea9b206dd9368d950d979` "readme: switched from moment to luxon (#252)" (Wed Dec 22 2021; same parent 9f890ba; `git log -S'HTTP and RFC2822' -- README.md` lists only 9332e6b). The `git show` diff of the two commits differs only in hash, date and subject suffix "(#252)". The maintainer cannot `git show ef172bd` in a normal clone. CONFIRMATION.md already used 9332e6b. Change: replace "commit ef172bd" with "commit 9332e6b (#252)". The sentence is otherwise true: that diff adds "- [`HTTP and RFC2822`](https://moment.github.io/luxon/#/parsing?id=http-and-rfc2822)". The SYNTHESIS "optional" item that proposed ef172bd should be corrected too.
2. NOTE (low), commit body and PR "ignores the tz option". Commit body: "so the asctime form ignores the tz option." Not exactly true: tz still sets the zone of the resulting CronDate (round 1: `new CronDate('Sun Nov  6 08:49:37 1994','Asia/Kolkata')` has hours 14); only the interpretation of the wall clock ignores tz. PR.md says it more precisely ("reads every HTTP date as GMT"). Suggest the commit body end "so the asctime form is read as GMT, not in the tz option." Optional. Changing it means amending the commit and regenerating the patch; if the operator does that, re-run `git am` check.
3. NOTE (low). PR.md "A caller who passes a zone-less asctime string that was meant as local time now gets a GMT date instead of an error" is true and enough.

## Not checked
Closed issues and PRs on the forge; #446 diff; luxon other than 3.7.2; other Node versions; the npm scripts by name; the operator's Mac command; a fresh fuzz this round; full-check re-run this round (I read the log and ran only the suite).
