# S3 round 2: FIX-REQUIRED (high)

Scope: slop and claims in PR.md and the commit body. The diff hunks in the patch are identical to rev0 (I diffed them: CODE-IDENTICAL-TO-REV0) and I have no complaint about them. One claim is wrong (finding 1, small fix). The rest is trim, not blocking.

## What I ran (own copy: scratch/panel2-cron-parser-http-date-formats-S3/tip)

- Clone of upstream-check master (`5033a31 chore: bump version`), `git am` of OUT/0001-*.patch: applies cleanly, HEAD = `07a297b fix: accept the RFC 850 and asctime HTTP date formats as string dates`, author `Andrew Stellman <andrew@stellman.com>`, no trailers.
- Fixed clone (read only): `git log` shows one commit on parent `5033a312f1fe04665060eacf4378f16c48ca4ea8`; commit body matches the patch.
- ts-node against `src/` with the patch applied, TZ=UTC (verbatim):
```
Europe/Athens "Sun Nov  6 08:49:37 1994" 1994-11-06T08:49:37.000Z
Europe/Athens "Sun Nov 06 08:49:37 1994" 1994-11-06T08:49:37.000Z
Europe/Athens "Sunday, 06-Nov-94 08:49:37 GMT" 1994-11-06T08:49:37.000Z
Europe/Athens "Mon, 4 Jan 2021 10:00:00" 2021-01-04T08:00:00.000Z
Europe/Athens "Sun Nov  6 08:49:37 1994 GMT" THROWS CronDate: unhandled timestamp: Sun Nov  6 08:49:37 1994 GMT
UTC "Mon, 4 Jan 2021 10:00:00" 2021-01-04T10:00:00.000Z
```
  So the Zone paragraph, the zero-padded-day sentence and "RFC 2822 without offset is read in tz" are all true.
- `README.md:85` is "When using string dates...", `:88` is "- HTTP and RFC2822" (sed on the fixed clone). True.
- full-check.log ends `Tests: 348 passed, 348 total` / `full-check exit 0`; red.log shows the two new tests failing with `CronDate: unhandled timestamp`; revert.log `2 failed, 47 passed`. sideeffect.log ends `inputs that parsed before and now differ: 0`.
- Diff of PR.md against `.github/pull_request_template.md`: all headings kept; ticked boxes are Bug fix, Code coverage, tests added, All tests pass locally, rebased. The four Code Quality / `npm test` boxes are unticked. Disclosure line is last and exact. No em dashes (grep count 0).

## Round-1 findings

1. Stale base and counts: FIXED. 5033a31, 348 (346 before), rebased box ticked after a real rebase.
2. Description out of proportion: PARTLY. The two diff-restating sentences and the "13 inputs" sentence are gone. But the section gained the ef172bd sentence, the "used to throw" paragraph and the zero-padded sentence, so it is still about 13 lines of prose plus a 3-line repro, against 2-10 in merged fixes (POLICY.md). See finding 2.
3. Testing contradicted its ticks: FIXED (ticks removed). The disclaimer is now said twice, see finding 3.
4. "Changes Made" restates the diff: NOT TAKEN; SYNTHESIS lists it as optional. Still true, still minor.
5. Commit body restated the PR: FIXED. The body is now O5's text; every sentence in it was run (see above). Its last sentence states the GMT decision.
6. Framing (README hedge comes last): acceptable as is.

## New findings

1. FIX-REQUIRED. The ef172bd claim names a commit that is not on master. PR.md: "That list came from commit ef172bd, which linked 'HTTP and RFC2822' to luxon's parsing section of the same name." In the fixed clone:
```
merge-base --is-ancestor ef172bd HEAD && echo ef172bd-ancestor   -> (nothing printed)
merge-base --is-ancestor 9332e6b HEAD && echo 9332e6b-ancestor   -> 9332e6b-ancestor
git for-each-ref --contains ef172bd (in upstream-check)           -> ef172bdc0bb7b8ac3c5be79aed62aaf3f9a9fc73 commit	refs/remotes/pr/252
git log --oneline -S'HTTP and RFC2822' -- README.md               -> 9332e6b readme: switched from moment to luxon (#252)
```
   ef172bd is the head commit of PR #252 (same subject and same stat, 8 insertions 3 deletions; I did not diff them line by line); master has the squash 9332e6b. A maintainer who runs `git show ef172bd` in a normal clone may get "bad object", and CONFIRMATION.md already says 9332e6b. The diff does show the link `[HTTP and RFC2822](...parsing?id=http-and-rfc2822)`, so the claim is true, only the hash is wrong. Change "commit ef172bd" to "commit 9332e6b (#252)". SYNTHESIS.md's optional item (from O4) has the same wrong hash; fix it there too.
2. FIX-REQUIRED (minor, trim). The Zone paragraph and the next paragraph say the same thing twice ("this is what fromHTTP does; I did not add zone handling" / "These two formats used to throw..."). "I ran `new CronDate(...)` and it gives" repeats the asctime test. "`DateTime.fromHTTP` is the last attempt (`src/CronDate.ts:54`)" cites a line that exists only in this patch, and restates the diff. The zero-padded day sentence is true but nobody asked and no test covers it. Replace everything from "The README says" through "...say so and I will change it." and the next two paragraphs with:

   > README.md:85-88 says "When using string dates, the following formats are supported:" and lists "- HTTP and RFC2822". That entry came from commit 9332e6b (#252), which linked "HTTP and RFC2822" to luxon's parsing section of the same name.
   >
   > `fromHTTP` is tried last, so inputs that parse today never reach it. It reads every HTTP date as GMT, including asctime, which has no zone: `new CronDate('Sun Nov  6 08:49:37 1994', 'Europe/Athens')` gives `1994-11-06T08:49:37.000Z`, while RFC 2822 without an offset is read in `tz`. That is luxon's behaviour; I did not add zone handling. A caller who passes a zone-less asctime string meant as local time now gets a GMT date instead of an error. If you prefer asctime in `tz`, say so and I will change it.

   Keep the repro block, the "which is what luxon fromHTTP returns" sentence and the closing "If only the RFC 1123 form was meant by "HTTP", the README line is what should change instead." The zero-padded sentence may stay if the operator wants it; I ran it and it is true.
3. FIX-REQUIRED (minor). The npm-scripts disclaimer appears in Testing ("I did not run the npm scripts themselves.") and again in Additional Notes. Say it once. Delete it from Testing and keep Additional Notes as is. Even better, the operator runs `npm run lint` and `npm run build` on the Mac and ticks those two, which removes the Additional Notes paragraph; I did not do this (see not checked).
4. Not a finding. Additional Notes "The change is made on upstream master at 5033a31." is fine and true. "README not changed: it already lists HTTP." under Documentation is a little odd next to a PR that says the README is the thing being matched, but it is true and short.
5. Not a finding. Template prompt lines "Brief description..." and "Any additional information..." were replaced by content; headings are all kept.

## Side-effect rule

Re-checked. Only strings that threw before can change (sideeffect.log: 0 previously-parsing inputs differ; my run above agrees for the inputs I tried). Affected: callers who relied on the throw for RFC 850 or asctime (unlikely), and callers who now pass zone-less asctime meant as local time and get GMT with no error (low). The PR now states the second case. Acceptable, no DROP. No security angle. No CHANGELOG edit.

## Not checked

GitHub tracker and whether the maintainer wants this; the npm scripts by name (`npm run lint/format/build`) and the Mac command (`npm ci --ignore-scripts && TZ=UTC npx jest`); full-check at the tip was read from full-check.log, not rerun by me (I ran only the ts-node cases above); luxon versions other than the installed one; two-digit-year pivot for RFC 850.
