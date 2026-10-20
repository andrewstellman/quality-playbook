# O1 round 2: FIX-REQUIRED (high)

One wrong sentence in PR.md must change. Code, tests, commit and everything else I checked are fine. After the one-sentence edit below I would merge it.

## What I did
- Read the rules, SYNTHESIS.md, PR.md, the patch, rev0/, CONFIRMATION.md, panel/O1.md, POLICY.md, the PR template.
- Fresh clone of the fixed clone at /work/batch/runs/cron-parser/scratch/panel2-cron-parser-http-date-formats-O1/ (fixed clone not touched). `git log` there: `7e1aa55 fix: accept the RFC 850 and asctime HTTP date formats as string dates` on top of `5033a31 chore: bump version`. `git diff 5033a31 HEAD --stat`: `src/CronDate.ts | 1 +`, `tests/CronDate.test.ts | 10 ++++++++++`, 2 files, 11 insertions.
- `git format-patch -1 --stdout` of the fixed clone, minus the "From <sha>" line, is identical to OUT/0001-*.patch (diff printed nothing).
- `bin/run-tests` on my clone: `Tests: 348 passed, 348 total`.
- Ran a script (ts-node, TZ=UTC) over 5 inputs in UTC and Europe/Athens. Verbatim, Athens: `"Sunday, 06-Nov-94 08:49:37 GMT" 1994-11-06T08:49:37.000Z`, `"Sun Nov  6 08:49:37 1994" 1994-11-06T08:49:37.000Z`, `"Sun Nov 06 08:49:37 1994" 1994-11-06T08:49:37.000Z`, `"Mon, 4 Jan 2021 10:00:00" 2021-01-04T08:00:00.000Z`. UTC gives the same GMT results and `2021-01-04T10:00:00.000Z` for the zone-less RFC 2822 string. So the Zone paragraph, the asymmetry claim and the zero-padded-day sentence are true.
- Read the logs: full-check.log ends `Tests:       348 passed, 348 total` / `full-check exit 0`; red.log `Tests:       2 failed, 47 skipped, 49 total` with `CronDate: unhandled timestamp` at tests/CronDate.test.ts:453; revert.log `2 failed, 47 passed`; green.log `49 passed`; sideeffect.log ends `inputs that parsed before and now differ: 0`. They match "348 tests passed (346 before)" in PR.md (346 = 348 minus the two new tests).

## Findings

1. MUST FIX. PR.md:17 cites the wrong commit. It says "That list came from commit ef172bd". I ran the command SYNTHESIS told the operator to repeat:
   - `git log --format='%h %ad %s' --date=short -S'HTTP and RFC2822' -- README.md` prints only `9332e6b 2021-12-22 readme: switched from moment to luxon (#252)`.
   - `git merge-base --is-ancestor ef172bd HEAD` fails (no output for ef172bd, while `9332e6b-in-history` printed for 9332e6b). `git branch -a --contains ef172bd` prints nothing.
   - ef172bd (2021-12-07, same subject, same 8+/3- README stat) is a pre-squash commit of PR #252, not in master's history. The hash is not reachable from master, and `git log`/`git blame` on README.md show 9332e6b, so a maintainer following the hash will not find it in their history (I did not test a fresh clone of the forge). CONFIRMATION.md also named 9332e6b, so this was right in round 1 and became wrong when O4's hash was adopted.
   Replace the sentence in PR.md:17 with:
   `That list came from commit 9332e6b (#252), which linked "HTTP and RFC2822" to luxon's parsing section of the same name.`
   Check the "linked ... to luxon's parsing section" part with `git show 9332e6b -- README.md`: I read the same change in ef172bd (`+- [`HTTP and RFC2822`](https://moment.github.io/luxon/#/parsing?id=http-and-rfc2822)`); I did not print 9332e6b's diff line by line, only its stat, which equals ef172bd's.

2. Verified fixed from SYNTHESIS (my round-1 findings 1-4 and the others):
   - Stale base: PR.md Additional Notes says "upstream master at 5033a31"; commit sits on 5033a31; logs regenerated (348). Fixed.
   - Counts: "348 tests passed (346 before)" matches full-check.log. Fixed.
   - Ticked npm boxes: `npm test`, `npm run lint`, `npm run format`, `npm run build` are now unticked; the Testing text and Additional Notes say the full check ran, not the npm scripts. No contradiction left. (`bin/full-check` runs eslint, prettier --check, tsc + tsd, jest --coverage; `npm run format` is `prettier --write`, so leaving it unticked is right.)
   - Placeholders: "Fixes #" line gone, Related Issues is `None.`, all template headings kept.
   - Behaviour change: now stated ("These two formats used to throw. A caller who passes a zone-less asctime string that was meant as local time now gets a GMT date instead of an error.").
   - Description length and diff restatement: trimmed; the commit body matches the SYNTHESIS finding 6 text and has no trailers (author `Andrew Stellman <andrew@stellman.com>`). Subject starts `fix: `, lower case.
   - README line numbers in PR.md (85, 88): `grep -n` gives `85:When using string dates, the following formats are supported:` and `88:- HTTP and RFC2822`. src/CronDate.ts:54 is the new line. Both correct.
   - CONFIRMATION.md "No newer commits" line is corrected at the foot of the file.

3. New-problem check on the revision: none besides finding 1. Disclosure line is last. The ticked boxes (bug fix, coverage maintained, tests added, all tests pass locally, rebased) each match a command that ran. "All tests pass (`npm test`)" unticked while "All tests pass locally" ticked reads slightly odd but both are true as written. Not worth a change.

4. Side-effect rule: no reason to drop. The new call is the last link of an `isValid ||` chain, so a string that any earlier parser accepts never reaches it (sideeffect.log: 0 changed among inputs that parsed before). Affected callers: those relying on a throw for RFC 850 or asctime input (unlikely), and zone-less asctime input meant as local time, now read as GMT without an error. The PR text says both. Acceptable.

## Not checked
- Whether PR #252's branch still exists on GitHub (no network); finding 1 is based on master's local history only.
- Open PR #446 touching src/CronDate.ts: not read (carried over).
- Tracker, closed issues and PRs; luxon versions other than the installed one; the operator's Mac command; I did not rerun full-check myself (I read the log and ran only the unit suite, 348 passed, and my script).
- Whether the maintainer prefers a README change; PR.md already offers it.
