# S1 round 2: FIX-REQUIRED (medium)

Role S1, code readability, round 2. Experiments in
/work/batch/runs/cron-parser/scratch/panel2-cron-parser-http-date-formats-S1/ (fresh clone of upstream-check, master 5033a31).
Fixed clone not touched. Nothing pushed, no gh.

One small required change: the commit hash cited in PR.md line 17 is not on master. Everything else is fixed or fine.

## Round-1 findings, status

1. npm-script boxes ticked while the text says they were not run: FIXED. PR.md now ticks only
   "Code coverage is maintained", "I have added tests", "All tests pass locally", "rebased on the latest master"
   and the bug-fix type. `npm test`, `npm run lint`, `npm run format`, `npm run build` are unticked.
   The Additional Notes sentence names the full check as what ran. No tick contradicts the text.
2. Stale base / counts: FIXED. Verified by running:
   ```
   $ git clone -q upstream-check <S1 copy> ; git am 0001-*.patch
   Applying: fix: accept the RFC 850 and asctime HTTP date formats as string dates
   $ git log --oneline -1 (before am)  ->  5033a31 chore: bump version
   $ bin/run-tests <S1 copy>  ->  Tests: 348 passed, 348 total
   ```
   PR.md says "5033a31" and "348 tests passed (346 before)". full-check.log in OUT ends
   `Tests: 348 passed, 348 total` / `full-check exit 0`. suite.log 348. Fixed clone: 7e1aa55 on parent 5033a31,
   `git diff HEAD~1 --stat` = 2 files, 11 insertions. Old (rev0) and new patch diff lines are identical (code and tests unchanged).
3. Placeholders: FIXED. "Fixes #" line gone from Description; Related Issues is "None." with headings kept.
4. README line cite: FIXED. "(README.md:85 and README.md:88)" checked against the tip: line 85 "When using string dates...", line 88 "- HTTP and RFC2822".
5. Alignment row in the repro fence: FIXED. The fence now has three result lines; the "expected" text is a sentence after it.
6. No comment on `fromHTTP` being last: unchanged on purpose (neighbours have none); the commit body says "Try fromHTTP last".
7. Test names: unchanged, consistent with neighbours. Not required.

## New problems in the revision

A. (Required, small) PR.md:17 says "That list came from commit ef172bd". ef172bd is not on master:
   ```
   $ cd upstream-check && git merge-base --is-ancestor ef172bd master && echo anc || echo notanc
   notanc
   $ git for-each-ref --contains ef172bd
   ef172bdc0bb7b8ac3c5be79aed62aaf3f9a9fc73 commit	refs/remotes/pr/252
   $ git merge-base --is-ancestor 9332e6b master && echo 93anc
   93anc
   $ git show 9332e6b --format='%h %an %s'
   9332e6b Vano Devium readme: switched from moment to luxon (#252)
   ```
   ef172bd is the head commit of PR 252; master carries the same change (same stat, 11 lines in README.md) as 9332e6b.
   A maintainer running `git show ef172bd` on a normal clone may get "bad object". CONFIRMATION.md line 26 already uses 9332e6b.
   Change: "That list came from commit 9332e6b (#252), which linked "HTTP and RFC2822" to luxon's parsing section of the same name."
   The "linked ... to luxon's section" part I saw in `git show ef172bd` (+ `[HTTP and RFC2822](https://moment.github.io/luxon/#/parsing?id=http-and-rfc2822)`);
   I did not diff 9332e6b against it line by line beyond the matching stat.
B. Minor, no change needed: the Zone paragraph, the "These two formats used to throw" paragraph and the zero-padded sentence are
   separate short paragraphs; they read fine. Run result for the zero-padded claim and the zone claim:
   ```
   $ TZ=UTC ts-node chk.ts   (tz = Europe/Athens)
   "Sun Nov  6 08:49:37 1994" 1994-11-06T08:49:37.000Z
   "Sun Nov 06 08:49:37 1994" 1994-11-06T08:49:37.000Z
   "Sunday, 06-Nov-94 08:49:37 GMT" 1994-11-06T08:49:37.000Z
   "Mon, 4 Jan 2021 10:00:00" 2021-01-04T08:00:00.000Z
   ```
   All four match PR.md ("RFC 2822 without offset is read in the tz option": 10:00 Athens = 08:00Z).
C. Commit body: matches SYNTHESIS finding 6 text, prose, no trailers, author Andrew Stellman, subject lower-case `fix: `.
   `git log -1 --format=%B` after am shows it unchanged. Body is accurate: asctime form ignores tz (shown above).
D. Style: no em dashes in PR.md (grep -c of the em dash = 0). Last line is exactly the disclosure line.
E. CONFIRMATION.md "No newer commits" line is followed by a dated correction. Acceptable; not part of the PR.

## Side-effect rule

fromHTTP is the last link of the `isValid ||` chain (src/CronDate.ts:54 at the tip), so inputs that parse today never reach it.
sideeffect.log: "inputs that parsed before and now differ: 0", two strings CHANGED from THROWS to a date.
Affected: callers relying on the throw, or passing zone-less asctime meant as local time; PR.md now says so plainly.
No reason to drop.

## Not checked

full-check on my copy (relied on OUT/full-check.log; I ran only the unit suite). The npm scripts by name.
sideeffect.log is dated 2026-10-07 (pre-rebase); not regenerated, and src/CronDate.ts is identical between 5b08cdf and 5033a31
per SYNTHESIS (I did not re-diff). Forge trackers. Operator's Mac command. Whether the maintainer prefers a README change.
