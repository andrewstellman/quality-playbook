# cron-parser: accept the RFC 850 and asctime HTTP date formats as string dates

Status: **ready for the operator's review.** (updated 2026-10-10)

## The project

[cron-parser](https://github.com/harrisiirak/cron-parser) is a TypeScript library that parses cron expressions and crontab files and computes the dates they match (next, previous, ranges, time zones, DST). It uses luxon for dates. A caller can pass `currentDate`, `startDate` and `endDate` as a string, and `CronDate` (`src/CronDate.ts`) turns that string into a luxon `DateTime`.

## The bug

The README says (`README.md:85`, `README.md:88`):

> When using string dates, the following formats are supported:
> - HTTP and RFC2822

HTTP dates have three forms: the IMF-fixdate (`Sun, 06 Nov 1994 08:49:37 GMT`), the obsolete RFC 850 form (`Sunday, 06-Nov-94 08:49:37 GMT`) and the obsolete asctime form (`Sun Nov  6 08:49:37 1994`). The constructor tries `fromISO`, `fromRFC2822`, `fromSQL` and one `fromFormat`. It never calls luxon's `DateTime.fromHTTP`. The IMF-fixdate form works only because it is also valid RFC 2822. The other two throw `CronDate: unhandled timestamp: ...`. I checked: `git log --all -S"fromHTTP"` in the upstream clone is empty, so it was never called. The README entry came from 9332e6b (#252), which linked "HTTP and RFC2822" to luxon's parsing section of that name (`git show 9332e6b -- README.md`, run today; 9332e6b is an ancestor of master).

No test covers an HTTP string (`git show HEAD~1:tests/CronDate.test.ts | grep -ci http` gives 0). I found no report of it (see "Things to know" for what that rests on).

Repro, run today on the base (`knock_on.base.txt`, zone Europe/Athens):

```
CronDate  tz=Europe/Athens     "Sunday, 06-Nov-94 08:49:37 GMT"         -> THROWS CronDate: unhandled timestamp: Sunday, 06-Nov-94 08:49:37 GMT
CronDate  tz=Europe/Athens     "Sun Nov  6 08:49:37 1994"               -> THROWS CronDate: unhandled timestamp: Sun Nov  6 08:49:37 1994
```

Severity: low, ordinary correctness. It is not a security issue (a clean `Error` on an obsolete date format; no hang, loop, memory or regex case under SECURITY.md).

## The fix

Add `DateTime.fromHTTP` as the last link in the existing chain. Every string that parses today is returned by an earlier link, so only strings that threw can reach the new line. `fromHTTP` reads every HTTP date as GMT, including asctime, which has no zone. I did not add zone handling.

Diff (`0001-fix-accept-the-RFC-850-and-asctime-HTTP-date-formats.patch`, author Andrew Stellman, no trailers):

```diff
diff --git a/src/CronDate.ts b/src/CronDate.ts
index d5e8cad..6da550b 100644
--- a/src/CronDate.ts
+++ b/src/CronDate.ts
@@ -51,6 +51,7 @@ export class CronDate {
       this.#date.isValid || (this.#date = DateTime.fromRFC2822(timestamp, dateOpts));
       this.#date.isValid || (this.#date = DateTime.fromSQL(timestamp, dateOpts));
       this.#date.isValid || (this.#date = DateTime.fromFormat(timestamp, 'EEE, d MMM yyyy HH:mm:ss', dateOpts));
+      this.#date.isValid || (this.#date = DateTime.fromHTTP(timestamp, dateOpts));
     }
 
     // Check for valid DateTime and throw an error if not valid.
diff --git a/tests/CronDate.test.ts b/tests/CronDate.test.ts
index 5627e3c..0572440 100644
--- a/tests/CronDate.test.ts
+++ b/tests/CronDate.test.ts
@@ -444,6 +444,16 @@ describe('CronDate', () => {
       expect(d.toISOString()).toBe('2021-01-04T09:00:00.000Z');
     });
 
+    test('HTTP RFC 850', () => {
+      const d = new CronDate('Sunday, 06-Nov-94 08:49:37 GMT', 'Europe/Athens');
+      expect(d.toISOString()).toBe('1994-11-06T08:49:37.000Z');
+    });
+
+    test('HTTP asctime, read as GMT', () => {
+      const d = new CronDate('Sun Nov  6 08:49:37 1994', 'Europe/Athens');
+      expect(d.toISOString()).toBe('1994-11-06T08:49:37.000Z');
+    });
+
     test('milliseconds', () => {
       const date = DateTime.fromISO('2021-01-04T11:00:00.000+02:00').valueOf();
       const d = new CronDate(date, 'Europe/Athens');
```

## Regression test

Two tests in `tests/CronDate.test.ts`, one per newly accepted format (`HTTP RFC 850`, `HTTP asctime, read as GMT`), next to the other string-format tests. Both use zone `Europe/Athens` so the GMT reading is visible.

- Red (source change reverted, tests kept; `red.log`): `CronDate › parse cron date formats with another timezone › HTTP RFC 850` fails with `CronDate: unhandled timestamp: Sunday, 06-Nov-94 08:49:37 GMT`; the asctime test fails the same way. Summary: `Tests:       2 failed, 47 skipped, 49 total`.
- Green (`green.log`): `Tests:       49 passed, 49 total` for `tests/CronDate.test.ts`. Full suite (`suite.log`): `Tests:       348 passed, 348 total`.
- Revert (`revert.log`): `Tests:       2 failed, 47 passed, 49 total`, same `unhandled timestamp` errors.
- Logs: `red.log`, `green.log`, `revert.log`, `suite.log`, `full-check.log`.

Note: `red.log`, `green.log`, `revert.log` and `suite.log` are from the panel's round 2 (2026-10-10, fix clone rebased onto 5033a31). Today's reruns are below.

## Knock-on effects (run 2026-10-10)

Checked against upstream `master` at 5033a312f1fe04665060eacf4378f16c48ca4ea8 (2026-10-09, "chore: bump version").

Reruns today on that tip:

- `git am` of the patch on a fresh clone at 5033a31: applies cleanly (`Applying: fix: accept the RFC 850 and asctime HTTP date formats as string dates`).
- `bin/run-tests` on the patched clone: `Tests:       348 passed, 348 total`. On the base (`HEAD~1`): `Tests:       346 passed, 346 total`.
- `bin/full-check` on a fresh patched clone (`full-check.log`): ends `full-check exit 0`, 348 passed, coverage table 100% on every file.
- The operator's Mac command on a fresh patched clone (`localcheck.log`): `npm ci --ignore-scripts && TZ=UTC npx jest` ended `Tests:       348 passed, 348 total` (exit 0). `npm ci` printed an `EBADENGINE` warning for node v22.22.0 and "25 vulnerabilities (20 moderate, 5 high)" in the dev dependency tree; neither is related to this change.

**Callers of the changed code.** The only edited code is the string branch of the `CronDate` constructor (`src/CronDate.ts:49-54` in the patched file). Every `new CronDate(...)` with a string reaches it:

- `src/CronExpression.ts:52` `startDate`
- `src/CronExpression.ts:53` `endDate`
- `src/CronExpression.ts:57` and `:65` `currentDate` (constructor)
- `src/CronExpression.ts:321` `reset()`, which falls back to `options.currentDate`
- `src/CronExpression.ts:342` `includesDate()`; its parameter is typed `Date | CronDate`, so a string reaches it only from untyped JavaScript
- `src/CronExpression.ts:132`, `:135`, `:521` copy a `CronDate`/`Date` and do not reach the string branch.
- `src/CronFileParser.ts` and `src/CronExpressionParser.ts` do not construct `CronDate` (grep for `new CronDate` in `src/`).

**Before/after.** `knock_on.ts` (kept in this folder) was run with `TZ=UTC ts-node` in two clones of the tip: base = 5033a31, fixed = base plus the patch (`8d8c336`). Outputs: `knock_on.base.txt`, `knock_on.fixed.txt` (51 lines each; the empty-string input is skipped by the script because `''` means "now"). Result of `diff`: 13 lines differ, 38 are identical. The 13 are the three newly accepted spellings in three zones (9 lines), the same string with no zone (1), and the parser calls (3).

| Input | Base | Fixed | Changed? |
|---|---|---|---|
| `2021-01-04T11:00:00.000+02:00` (ISO) | `2021-01-04T09:00:00.000Z` | same | no |
| `2021-01-04` (ISO date, tz Athens) | `2021-01-03T22:00:00.000Z` | same | no |
| `Mon, 4 Jan 2021 10:00:00 +0100` (RFC 2822) | `2021-01-04T09:00:00.000Z` | same | no |
| `Mon, 4 Jan 2021 10:00:00` (no offset, tz Athens) | `2021-01-04T08:00:00.000Z` | same | no |
| `2021-01-04 10:00:00` (SQL, tz Athens) | `2021-01-04T08:00:00.000Z` | same | no |
| `Sun, 06 Nov 1994 08:49:37 GMT` (IMF-fixdate) | `1994-11-06T08:49:37.000Z` | same | no |
| `1994-11-06T08:49:37Z` | `1994-11-06T08:49:37.000Z` | same | no |
| `Sunday, 06-Nov-94 08:49:37 GMT` (RFC 850) | throws `unhandled timestamp` | `1994-11-06T08:49:37.000Z` | **yes** |
| `Sun Nov  6 08:49:37 1994` (asctime) | throws | `1994-11-06T08:49:37.000Z` | **yes** |
| `Sun Nov 06 08:49:37 1994` (asctime, zero-padded day) | throws | `1994-11-06T08:49:37.000Z` | **yes** |
| `Monday, 06-Nov-94 08:49:37 GMT` (wrong weekday) | throws | throws | no |
| `Sun Nov  6 08:49:37 94` (two-digit year, asctime) | throws | throws | no |
| `Sun Nov  6 25:49:37 1994` (hour 25) | throws | throws | no |
| `Sunday, 31-Feb-94 08:49:37 GMT` (impossible day) | throws | throws | no |
| `not a date` | throws | throws | no |
| parser: `currentDate: 'Sunday, 06-Nov-94 08:49:37 GMT'`, `0 * * * *`, tz Athens, `next()` | throws | `1994-11-06T09:00:00.000Z` | **yes** |
| parser: `startDate` asctime + `endDate` RFC 850, hourly | throws | four dates, `09:00Z` to `12:00Z` | **yes** |

The ISO, RFC 2822 and SQL rows give the same value in UTC, Athens and New York (all three zones are in the output files); only the rows marked "yes" differ.

**Behaviour changes for existing users, judged under the side-effect rule.**

1. RFC 850 and asctime strings used to throw and now return a date. Affected: a caller who used the throw to reject these two forms. Likelihood: very low (the README lists HTTP as supported). Acceptable.
2. A zone-less asctime string (`Sun Nov  6 08:49:37 1994`) is read as GMT whatever `tz` is. A caller who passes such a string meaning local time used to get an error and now gets a date that is off by the zone offset, with no error. Likelihood: low; the form is obsolete and `fromHTTP` defines it as GMT. Acceptable, and PR.md says it plainly and offers to read asctime in `tz` instead.
3. No string that parses today changes: `fromHTTP` is the last link, and the 38 identical lines above include every such input in the script. The panel also fuzzed mutated inputs against the old chain (O3 reported 48000 in round 1; EXEC-A and EXEC-B reported about 4000 and 6000 at the tip in round 2) and reported 0 changed results. I did not rerun those fuzz runs today.

No behaviour change is bad enough to drop the fix.

## Review history

- Confirmed: `CONFIRMATION.md` (verdict CONFIRMED, low severity). Its line "No newer commits" was wrong; a dated correction is in that file.
- Panel: `SYNTHESIS.md`. Roster: full, 15 reviewers, all Sonnet. Round 1: no code objection, 13 FIX-REQUIRED on text and the stale base, no REJECT or DROP.
- Round 2 (2026-10-10): the commit was rebased onto 5033a31, logs regenerated, 13 reviewers re-ran. All code checks passed. Text fixes applied: base and test counts; unticked `npm test`, `npm run lint`, `npm run format`, `npm run build`; the "used to throw" and GMT sentence; template placeholders removed; Description shortened; commit body replaced; a wrong commit hash (`ef172bd`, a PR head, not on master) replaced with `9332e6b`.
- The final PR text was edited by the parent after round 2 and was not re-reviewed by another agent (SYNTHESIS.md says so).
- Upstream check (2026-10-10): `master` at 5033a312f1fe04665060eacf4378f16c48ca4ea8 (2026-10-09, "chore: bump version"); patch applies cleanly: **yes** (`git am` on a clone checked out at that commit); suite there: `Tests:       348 passed, 348 total`.

## Things to know before submitting

- **Issue tracker.** What is known comes from `reference_docs/known_open_bugs.md`, the operator's `gh` export of 2026-10-05T23:05:00Z: it lists what was OPEN then (9 issues, 4 pull requests). None is about string date formats. Closed issues and pull requests, and anything opened after 2026-10-05, were not searched; `gh` and the GitHub site were not reachable from here. `submit-draft-pr.sh` runs the tracker search and asks before it continues.
- **Pull-request heads touching the same files** (from `git` in the upstream clone; git cannot say which are open):
  - Newer than the export: `pr/453` (2026-10-08, "fix: keep addHour moving forward across a fall-back shorter than an hour") edits `src/CronDate.ts` (near line 143) and `tests/CronDate.test.ts`; the patch applies with plain `git am` on top of that head (run today). `pr/454` (2026-10-09) edits only `src/CronExpressionParser.ts` and its test.
  - Open per the export: #446 (`pr/446`) edits `src/CronDate.ts` at about line 342, away from line 54. (Opus check, 2026-10-10: still open, and it merges with the patched tip with no conflict.)
  - Older heads that touch the two files (`pr/405`, `408`, `413`, `435`, and others from 2024 to 2026): state not checked; #435 is a merged fix per POLICY.md.
  - `master` now contains squash commits for #451 and #454 (`git log`), so the export's open list is already out of date.
- **The panel was fifteen Sonnet reviewers**, two rounds (see Review history). Findings raised and not adopted, with the reason in `SYNTHESIS.md`:
  - rename the tests (S2);
  - add a negative test, a default-zone test, or a local-timezone-block test (S4, S1, S2);
  - mention two-digit year pivots (O3, S5, EXEC-B);
  - drop or keep the "13 inputs in three zones" sentence (O5, S3 vs S7; the sentence was deleted in round 2);
  - add a performance sentence (S6);
  - tick more template boxes (O5, S8);
  - add a comment on why `fromHTTP` is last (S1);
  - trim the Description to O5's three paragraphs, drop the repro fence and the zero-padded sentence (O5, S3). The Description is still longer than the 2 to 10 prose lines POLICY.md records for merged outside fixes; cut it if you prefer;
  - cite b5f4194 (S7);
  - `sideeffect.log` (2026-10-07, old base) was not rerun; PR.md no longer cites it.
- **Likely pushback.** "HTTP in the README means the IMF-fixdate, which already works; change the README instead" (O4, `CONFIRMATION.md`). PR.md already offers that. The other likely question is the GMT reading of asctime.
- **Policy items for you** (`POLICY.md`):
  - AI policy: silent. The disclosure line is required by the workflow, not by the project.
  - No CLA or DCO found. No issue needed first for a bug fix (`CONTRIBUTING.md:92-93`); blank issues are disabled.
  - Target branch `master`; Conventional Commits title `fix: ...`; no `CHANGELOG.md` edit (release workflow writes it).
  - Template boxes: ticked are "Bug fix", "Code coverage is maintained or improved", "I have added tests", "All tests pass locally", "I have rebased my branch on the latest master". Left unticked on purpose: `npm test`, `npm run lint`, `npm run format`, `npm run build`, "I have read and followed the CONTRIBUTING.md" and the others. I ran the project's full check and the Mac command (`npx jest`), not the npm scripts by name. Tick any of those you have run yourself on the Mac, and if you tick the four script boxes, delete "I did not run the npm scripts themselves." in Testing.
  - "Rebased on the latest master" is true as of 5033a31 on 2026-10-10. If `master` moves before you submit, `submit-draft-pr.sh` branches from the new tip and `git am` will tell you if it no longer applies.
  - `submit-draft-pr.sh` expects `gh` logged in as `andrewstellman` and opens a draft; marking it ready is yours.

## Checks by the orchestrating session (Opus, 2026-10-10, after the Sonnet workflow finished)

Everything above this section was written by the Sonnet-only workflow. These are my own runs, finished at 21:46 UTC.

- Upstream `master` refetched: `5033a312` (2026-10-09, "chore: bump version"), four commits after the pinned `5b08cdf8` (#451, #454, dev-deps bump, version bump). None touches `src/CronDate.ts` or `tests/CronDate.test.ts`. 191 pull-request heads, newest #454. The patch applies with `git am` to a fresh clone at exactly `5033a312`. Author `Andrew Stellman <andrew@stellman.com>`, no trailers, 2 files, 11 insertions, tree `89ed3826`, the same tree the panel checked.
- Suite on the patched tip: `348 passed, 348 total`. With only `src/CronDate.ts` reverted: `2 failed, 346 passed`, exactly the two new tests, each with `CronDate: unhandled timestamp`.
- Duplicates: no pull-request head and no commit on any ref in the clone contains `fromHTTP`. #446 is still open (`refs/pull/446/merge` exists) and does edit `src/CronDate.ts`; I merged it with the patched tip (`git merge-tree`) and it merges with no conflict.
- My own differential test: 23 date strings (the five HTTP forms the fix targets, ISO, SQL, RFC 2822 with and without an offset, and near misses: wrong weekday, impossible date, `PST` instead of `GMT`, four-digit year in the RFC 850 form, single-space asctime, lower case, a trailing `GMT` on asctime, garbage), each in four zones (`UTC`, `Europe/Athens`, `America/New_York`, none), before and after the fix at `TZ=UTC`. 92 cases. 20 changed, all from a throw to the GMT instant: the RFC 850 and asctime forms (padded and unpadded day) in both test dates. (The empty-string rows also differ, but only because an empty string means "now".) Every string that parsed before gives the same result after, and every near miss still throws.
- Claims in the PR text, each rerun or read: the three repro lines; README.md:85 and :88 at `5033a31`; `9332e6b` is "readme: switched from moment to luxon (#252)" and links "HTTP and RFC2822" to luxon's `#/parsing?id=http-and-rfc2822`; `fromHTTP` is the last link of the chain; `Sun Nov  6 08:49:37 1994` with `Europe/Athens` gives `1994-11-06T08:49:37.000Z`; `Mon, 4 Jan 2021 10:00:00` with `Europe/Athens` gives `2021-01-04T08:00:00.000Z` (read in `tz`); the zero-padded form is accepted; 348 (346 before); `full-check.log` ends `full-check exit 0`; the IMF-fixdate is accepted by `DateTime.fromRFC2822` (luxon 3.7.2, the version installed at the tip). All true.
- The PR text above was edited after round 2 without another agent re-reading it. I read it against `PR.md` (identical) and checked each claim as listed. I found nothing to change.
- Not checked: closed issues and pull requests on GitHub (`submit-draft-pr.sh` searches them with your `gh`).

## The PR as it will be submitted

> **Title:** fix: accept the RFC 850 and asctime HTTP date formats as string dates
>
> ## Description
>
> String dates in the RFC 850 and asctime HTTP formats throw, although the README lists "HTTP and RFC2822" as supported (README.md:88).
>
> ```
> new CronDate('Sunday, 06-Nov-94 08:49:37 GMT', 'UTC')  // Error: CronDate: unhandled timestamp
> new CronDate('Sun Nov  6 08:49:37 1994', 'UTC')        // Error: CronDate: unhandled timestamp
> ```
>
> Both should give `1994-11-06T08:49:37.000Z`, as luxon's `DateTime.fromHTTP` does. The change tries `fromHTTP` last, so strings that parse today are unchanged.
>
> `fromHTTP` reads the asctime form, which has no zone, as GMT rather than in the `tz` option. If you would rather have it read in `tz`, or meant only the RFC 1123 form, say so.
>
> ## Type of Change
>
> Please check the relevant option:
>
> - [x] Bug fix (non-breaking change which fixes an issue)
> - [ ] New feature (non-breaking change which adds functionality)
> - [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
> - [ ] Documentation update (changes to documentation only)
> - [ ] Code refactoring (no functional changes)
> - [ ] Performance improvement
> - [ ] Test improvement or addition
> - [ ] Build/CI/tooling changes
>
> ## Testing
>
> Describe how you've tested your changes:
>
> Two new tests in `tests/CronDate.test.ts` fail without the change and pass with it. The project's full check (eslint, prettier `--check`, build, tsd, jest with coverage) passes with 348 tests. I did not run the npm scripts by name.
>
> - [ ] All tests pass (`npm test`)
> - [x] Code coverage is maintained or improved
>
> ## Changes Made
>
> List the main changes in this pull request:
>
> - `src/CronDate.ts`: try `DateTime.fromHTTP` after the existing string formats.
> - `tests/CronDate.test.ts`: one test per newly accepted format.
>
> ## Related Issues
>
> List any issues that are related to this PR:
>
> None.
>
> ## Documentation
>
> - [ ] Code is self-documenting with clear variable/function names
> - [ ] Complex logic has helpful comments
> - [ ] Public API changes are documented with JSDoc
> - [ ] README updated (if user-facing changes)
>
> README not changed: it already lists HTTP.
>
> ## Performance
>
> If this PR affects performance:
>
> - [ ] Benchmarks were run before and after changes
> - [ ] Performance impact is acceptable or improved
> - [ ] Results are documented in comments or PR description
>
> ## Breaking Changes
>
> If this introduces breaking changes:
>
> - [ ] Breaking changes are clearly documented
> - [ ] Migration guide provided (if needed)
> - [ ] Version bump strategy discussed
> - [ ] Backwards compatibility considered
>
> ## Code Quality
>
> - [ ] Code follows project style guidelines
> - [ ] ESLint checks pass (`npm run lint`)
> - [ ] Prettier formatting applied (`npm run format`)
> - [ ] TypeScript compilation successful (`npm run build`)
> - [ ] No new TypeScript errors or warnings
>
> ## Checklist
>
> - [ ] I have read and followed the [CONTRIBUTING.md](../../CONTRIBUTING.md) guidelines
> - [ ] My code follows the project's coding standards
> - [x] I have added tests for my changes
> - [x] All tests pass locally
> - [ ] I have updated documentation as needed
> - [ ] My commits have clear, descriptive messages
> - [x] I have rebased my branch on the latest master
>
> ## Additional Notes
>
> Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.

Shortened on 2026-10-10 under Andrew's standing rule (short PR text); the template headings and boxes are unchanged. Cut from the prose, all still true and recorded above: the IMF-fixdate line, the `9332e6b` (#252) history, the `Europe/Athens` example, the "used to throw" paragraph, the zero-padded day note, and the base-commit line.

## To submit

    bash submit-draft-pr.sh

The workflow script writes that file after this step. It runs the tracker search, asks before continuing, and opens a DRAFT pull request.

## Submission record

- 2026-10-10: draft pull request https://github.com/harrisiirak/cron-parser/pull/455 opened by Andrew with `submit-draft-pr.sh`, with the shortened PR text. Only the final `gh pr view` output was pasted; the script stops on a failing local check, so the check either passed or was skipped (not known from here).
- Checked after opening (git, sandbox, 23:31 UTC): PR head `f9d25a54a38736030a923d368a5cbb596c344df7`, author Andrew Stellman <andrew@stellman.com>, one commit on `master` `5033a31` (still the tip), tree `89ed3826d21ddaf2f4d8bb3f28476bc2c1c782d5`, identical to the reviewed patch; no trailers.
- Marked ready for review by Andrew; the PR page shows the event at 23:30 UTC. No reviews or comments when read at about 23:35 UTC.
- 2026-10-11 15:14 UTC: merged as squash commit `a70b68e6bb97171a19d7efbd33c06f301e6f2804` on `master` (checked with git against the live repository at 15:23 UTC). Parent `5033a31`, tree `89ed3826d21ddaf2f4d8bb3f28476bc2c1c782d5`, identical to the reviewed patch; the commit message is the reviewed one with `(#455)` appended to the subject. git does not record who pressed merge.
