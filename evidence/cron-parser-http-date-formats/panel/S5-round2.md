# S5 round 2: SHIP (medium)

Role: S5 compat. Scope: every behaviour change for existing users; are the new PR.md claims true; were my round-1 findings fixed.
Experiments in /work/batch/runs/cron-parser/scratch/panel2-cron-parser-http-date-formats-S5/ (clone of the fixed clone, plus s5/r.ts and s5/diff.ts). Fixed clone not modified.

## State checked
- Fixed clone HEAD 7e1aa55, parent 5033a312f1fe04665060eacf4378f16c48ca4ea8 (upstream tip). `git diff HEAD~1 --stat`: src/CronDate.ts +1, tests/CronDate.test.ts +10.
- `git format-patch -1 --stdout` of the fixed clone vs OUT/0001-*.patch: identical (diff printed nothing).
- Commit author Andrew Stellman, no trailers. Body matches SYNTHESIS finding 6.

## Round-1 findings, one by one
1. Wrong base / stale counts: FIXED. PR.md says "upstream master at 5033a31" and "348 tests passed (346 before)".
   I ran `run-tests` on my clone: "Tests: 348 passed, 348 total". With src/CronDate.ts reverted to HEAD~1 and tests kept:
   "Tests: 2 failed, 346 passed, 348 total" (the two failures are the new HTTP tests). So 348/346 is true.
   full-check.log tail: "Tests: 348 passed, 348 total ... full-check exit 0" (read, not re-run by me).
   CONFIRMATION.md now has a "Correction (round 2)" line for "No newer commits". The original wrong line is still in the file above it; the correction is below.
2. Boxes vs text: FIXED. npm test, lint, format, build boxes are now unticked; the Testing paragraph and Additional Notes say the full check ran instead.
3. Behaviour change not stated: FIXED for the case that matters. PR.md now says "These two formats used to throw. A caller who passes a
   zone-less asctime string that was meant as local time now gets a GMT date instead of an error." and "The zero-padded day form (`Sun Nov 06 08:49:37 1994`) is accepted too."
   Both run (below). Not stated, and I do not require it: callers who use the constructor error as an input validator now accept these two formats; two-digit year rule is luxon's.
4. "13 inputs" sentence overstated: moot, the sentence is gone from PR.md (still in rev0/PR.md only).
5. Empty template lines: FIXED. "Fixes #" removed, Related Issues says "None."
6. Closing README offer kept.

## Claims in new PR.md, run (TZ=UTC, ts-node --transpile-only s5/r.ts, output verbatim)
"Sun, 06 Nov 1994 08:49:37 GMT" UTC -> 1994-11-06T08:49:37.000Z
"Sunday, 06-Nov-94 08:49:37 GMT" UTC -> 1994-11-06T08:49:37.000Z
"Sun Nov  6 08:49:37 1994" UTC -> 1994-11-06T08:49:37.000Z
"Sun Nov  6 08:49:37 1994" Europe/Athens -> 1994-11-06T08:49:37.000Z      (PR claim "I ran ... Europe/Athens ... gives 1994-11-06T08:49:37.000Z": true)
"Sun Nov  6 08:49:37 1994" America/New_York -> 1994-11-06T08:49:37.000Z
"Sun Nov 06 08:49:37 1994" UTC -> 1994-11-06T08:49:37.000Z                (zero-padded claim: true)
"Mon, 4 Jan 2021 10:00:00" Europe/Athens -> 2021-01-04T08:00:00.000Z      (RFC 2822 without offset is read in tz: true, 10:00 EET = 08:00Z)
"Sun Mar 29 02:30:00 2026" Europe/Athens -> 2026-03-29T02:30:00.000Z      (a local-time-looking asctime string is read as GMT, no error)
"Mon Nov  6 08:49:37 1994" UTC -> THROW CronDate: unhandled timestamp: Mon Nov  6 08:49:37 1994
Old chain (re-implemented, s5/diff.ts) vs new CronDate, 22 inputs x 4 zones: the only CHANGED rows are throw -> date for
"Sunday, 06-Nov-94 ... GMT", "Sun Nov  6 ... 1994", "Sun Nov 06 ... 1994", "Sunday, 06-Nov-50 ... GMT", "Sun Mar 29 02:30:00 2026"
(plus the "" row, a harness artefact: empty string means "now"). No input that parsed before changed. Same as round 1.
`README.md:85` is "When using string dates, the following formats are supported:" and `README.md:88` is "- HTTP and RFC2822": true.
`src/CronDate.ts:54` is the fromHTTP line in the patch: true.

## Side-effect rule
Affected: (a) callers who relied on the throw for these two formats, e.g. as an input validator: very unlikely, they now accept two more formats, no wrong schedule.
(b) callers who pass zone-less asctime strings from local-time tools: they now get a silent GMT instant instead of an error. Low likelihood, and PR.md now says it.
(c) callers of strings that already parsed: nobody, fromHTTP is the last link of the `isValid ||` chain.
Acceptable. Not breaking. Not a drop. The "Breaking change" box is correctly unticked.

## One issue left (minor, one token)
PR.md line 17: "That list came from commit ef172bd". ef172bd is not an ancestor of the tip: `git merge-base --is-ancestor ef172bd 5033a31` printed
"ef_not_ancestor" (`git show -s` still finds it: "ef172bd Vano Devium readme: switched from moment to luxon"; `git branch -a --contains ef172bd` printed nothing, so it is a PR-branch commit, not on master).
The squash commit on master is 9332e6b "readme: switched from moment to luxon (#252)",
which is in tip history and whose diff contains "+- [`HTTP and RFC2822`](https://moment.github.io/luxon/#/parsing?id=http-and-rfc2822)". The sentence is true of both.
Change: write "9332e6b (#252)" instead of "ef172bd", so `git show` works on a plain clone of master. Also note the current README lines 85-89 were last
rewritten by b5f41940 (git blame), which dropped the link; "came from" is about the origin of the list, not the current line. Optional.
Also note: CONFIRMATION.md line 26 already cites 9332e6b, PR.md cites ef172bd; make them agree.

## Not checked
- I did not re-run bin/full-check; I read the tail of full-check.log.
- Forge: closed issues/PRs, whether a maintainer prefers a README change.
- luxon versions other than the installed one; non-UTC process TZ (all runs TZ=UTC).
- Open PR #446 (touches src/CronDate.ts) for conflicts.
- I did not verify how GitHub resolves ef172bd; I only checked git ancestry locally.
