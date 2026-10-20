# cRonstrue: lists with a plain first value and a later step lose a separator and print a stray comma

Status: **ready for the operator's review.**

## The project
[cRonstrue](https://github.com/bradymholt/cRonstrue) turns a cron expression into a sentence in English and about 40 other languages: `*/5 * * * *` becomes "Every 5 minutes". It is a TypeScript library. `src/cronParser.ts` normalises the expression, `src/expressionDescriptor.ts` builds the sentence, `src/i18n/locales/*.ts` hold the translations, and the tests are mocha files in `test/`.

## The bug
A cron field can hold a comma list, for example `5,0-4/2` in the day-of-week field: Friday, plus every second day from Sunday to Thursday. When the first item of the list is a plain value and a later item has a step (`/2`), the sentence comes out broken. For `0 9 * * 5,0-4/2` the library prints:

    At 09:00 AMonly on Friday and , every 2 days of the week, Sunday through Thursday

The ", " after the time is missing, so "AM" and "only" run together, and there is a stray " , " after "and". The sentence should read:

    At 09:00 AM, only on Friday and every 2 days of the week, Sunday through Thursday

The expression is valid: it is a standard 5-field expression with a day-of-week list of `5` and `0-4/2`. The same fault appears in the day-of-month field (`0 0 12 1,15-20/2 * ?`, Quartz-style with `?`), the month field (`0 9 * 1,3-9/2 *`) and the year field (`0 0 9 * * * 2020,2022-2030/2`, 7-field form). All are valid for their dialects.

No documentation gives wording for combined lists. `README.md:17` says only "Supports all cron expression special characters including * / , - ? L W, #". The expected text follows the library's own output for the step-first list `0 9 * * 0-4/2,5,6` (`test/cronstrue.ts:753`), which is well formed. CONFIRMATION.md ("Expectation check") found no test, comment or changelog line that makes the glued text intentional. The bug came in with upstream commit 286434e (#374, "remove double commas"), whose test covers only the step-first case, which is why it went unnoticed.

## The fix
In the multiple-values loop of `getSegmentDescription` (`src/expressionDescriptor.ts`), each member's description has its leading ", " removed, because the loop writes its own separators. Two things were wrong:

- A plain member had the ", " removed even when it was the first member, so it ran into the time. Second hunk: add `i > 0`.
- A step member after the first kept its own ", " after the loop's " and ", giving " , ". First hunk: remove the ", " there too, for `i > 0`.

The step-first case is unchanged because the first member keeps its ", ". The patch is 5 source lines and one test.

```diff
diff --git a/src/expressionDescriptor.ts b/src/expressionDescriptor.ts
index aa56b4c..78bc7f6 100644
--- a/src/expressionDescriptor.ts
+++ b/src/expressionDescriptor.ts
@@ -592,6 +592,9 @@ export class ExpressionDescriptor {
 
           if (isSegmentRangeWithoutIncrement) {
             currentDescriptionContent = currentDescriptionContent!.replace(", ", "");
+          } else if (i > 0 && currentDescriptionContent!.startsWith(", ")) {
+            // Strip leading comma since we manage separators in this loop
+            currentDescriptionContent = currentDescriptionContent!.substring(2);
           }
 
           descriptionContent += currentDescriptionContent;
@@ -607,7 +610,7 @@ export class ExpressionDescriptor {
             getDescriptionFormat
           );
           // Strip leading comma since we manage separators in this loop
-          if (segmentDescription && segmentDescription.startsWith(", ")) {
+          if (i > 0 && segmentDescription && segmentDescription.startsWith(", ")) {
             segmentDescription = segmentDescription.substring(2);
           }
           descriptionContent += segmentDescription;
diff --git a/test/cronstrue.ts b/test/cronstrue.ts
index dd3fa87..7fcc7c6 100644
--- a/test/cronstrue.ts
+++ b/test/cronstrue.ts
@@ -757,6 +757,13 @@ describe("Cronstrue", function () {
       );
     });
 
+    it("0 9 * * 5,0-4/2", function () {
+      assert.equal(
+        cronstrue.toString(this.test?.title as string),
+        "At 09:00 AM, only on Friday and every 2 days of the week, Sunday through Thursday"
+      );
+    });
+
     it("* 1-2,22-23 * * *", function () {
       assert.equal(
         cronstrue.toString(this.test?.title as string),
```

Commit message (in the patch, author Andrew Stellman, no trailers):

    Fix separators in lists with a plain first value and a step

    `0 9 * * 5,0-4/2` printed "At 09:00 AMonly on Friday and , every 2 days
    of the week". The leading ", " was stripped from the first member too,
    so it ran into the time, and a later step member kept its own ", ".
    Only members after the first are stripped now.

## Regression test
New case `0 9 * * 5,0-4/2` in the "non-trivial expressions" group of `test/cronstrue.ts`.

- Red (`red.log`, fix not applied): `AssertionError: expected 'At 09:00 AMonly on Friday and , every 2 days of the week, Sunday through Thursday' to equal 'At 09:00 AM, only on Friday and every 2 days of the week, Sunday through Thursday'`
- Green (`green.log`): `184 passing` for `test/cronstrue.ts`; the one new test alone, `1 passing`.
- Revert (`revert.log`, source change reverted, test kept): fails again with the same assertion.
- Full suite (`suite.log`, fixer's clone): `406 passing`. Re-run today on a fresh clone of the tip with the patch applied: `406 passing` (see Review history).
- Prettier (`lint.log`): `src/expressionDescriptor.ts` passes. `test/cronstrue.ts` gets a warning, and the same warning appears on unmodified `c08a7d6`. Re-checked today on both: `[warn] test/cronstrue.ts`. The warning is at existing lines, not at the added test; the file was not reformatted.
- Logs: red.log, green.log, revert.log, suite.log, lint.log.

## Knock-on effects (run 2026-10-07)
- Callers of the changed code. The changed lines are in `ExpressionDescriptor.getSegmentDescription` (`src/expressionDescriptor.ts:537`), in the multiple-values loop that starts at line 566 of the fixed commit. Callers of `getSegmentDescription`, all in `src/expressionDescriptor.ts`: `getSecondsDescription` :222, `getMinutesDescription` :250, `getHoursDescription` :299, `getDayOfWeekDescription` :335, `getMonthDescription` :425, `getDayOfMonthDescription` :488, `getYearDescription` :517, `getWrappingIncrementDescription` :721 (verbose only), and the two recursive calls in the loop itself, :584 and :604. Every public entry (`cronstrue.toString`, `cronstrue-i18n`) reaches it through `ExpressionDescriptor.getFullDescription`.
- Before/after on ordinary and edge inputs, freshly run today with `knock_on.ts` in two scratch clones (base = `c08a7d6`, fixed = `957e54f`). Raw output: `knock_on.base.txt`, `knock_on.fixed.txt`.

| Input | Base | Fixed |
|---|---|---|
| `*/5 * * * *` | Every 5 minutes | same |
| `0 9 * * 1-5` | At 09:00 AM, Monday through Friday | same |
| `0 0 12 1,15 * ?` | At 12:00 PM, on day 1 and 15 of the month | same |
| `0 9 1,15-20 * *` | At 09:00 AM, on day 1 and 15 through 20 of the month | same |
| `0 9 * * 1,3,5` | At 09:00 AM, only on Monday, Wednesday, and Friday | same |
| `5,10,15 * * * *` | At 5, 10, and 15 minutes past the hour | same |
| `0 9 * * 1-3,5` | At 09:00 AM, only on Monday through Wednesday and Friday | same |
| `0 9 * * 0-4/2,5,6` (step first) | At 09:00 AM, every 2 days of the week, Sunday through Thursday, only on Friday, and only on Saturday | same |
| `5-45/10,*/5,9 * * * *` | Every 10 minutes, minutes 5 through 45 past the hour, every 5 minutes, and at 9 minutes past the hour | same |
| `1-3,*/2 9 * * *` | 1 through 3 and every 2 minutes, between 09:00 AM and 09:59 AM | same |
| `0 1-3,*/2 * * *` | On the hour, 01:00 AM through 03:00 AM and every 2 hours | same |
| `0 5,*/2 * * *` | On the hour, at 05:00 AM and every 2 hours | same |
| `0 9 * * 5,0-4/2` | At 09:00 AMonly on Friday and , every 2 days of the week, Sunday through Thursday | At 09:00 AM, only on Friday and every 2 days of the week, Sunday through Thursday |
| `0 0 12 1,15-20/2 * ?` | At 12:00 PMon day 1 of the month and , every 2 days in a month, between day 15 and 20 of the month | At 12:00 PM, on day 1 of the month and every 2 days in a month, between day 15 and 20 of the month |
| `0 9 * 1,3-9/2 *` | At 09:00 AMonly in January and , every 2 months, March through September | At 09:00 AM, only in January and every 2 months, March through September |
| `0 0 9 * * * 2020,2022-2030/2` | At 09:00 AMonly in 2020 and , every 2 years, 2022 through 2030 | At 09:00 AM, only in 2020 and every 2 years, 2022 through 2030 |
| `0 9 * * 1,3,5-6/2` | At 09:00 AMonly on Monday, only on Wednesday, and , every 2 days of the week, Friday through Saturday | At 09:00 AM, only on Monday, only on Wednesday, and every 2 days of the week, Friday through Saturday |
| `0 9 * * 1-3,*/2` (range first) | At 09:00 AMMonday through Wednesday and , every 2 days of the week | At 09:00 AMMonday through Wednesday and every 2 days of the week (stray comma gone, glue remains) |
| `0 9 * * 5,0-4/2`, `verbose` | At 09:00 AMonly on Friday and , every 2 days of the week, Sunday through Thursday | At 09:00 AM, only on Friday and every 2 days of the week, Sunday through Thursday |
| `0 9 * * 5,0-4/2`, `use24HourTimeFormat` | At 09:00only on Friday and , every 2 days of the week, Sunday through Thursday | At 09:00, only on Friday and every 2 days of the week, Sunday through Thursday |
| `0 9 * * 5,0-4/2`, `de` | Um 09:00nur jeden Freitag und , alle 2 Tage der Woche, Sonntag bis Donnerstag | Um 09:00, nur jeden Freitag und alle 2 Tage der Woche, Sonntag bis Donnerstag |
| `0 9 * * 5,0-4/2`, `fr` | À 09:00uniquement le vendredi et , tous les 2 jours de la semaine, de dimanche à jeudi | À 09:00, uniquement le vendredi et tous les 2 jours de la semaine, de dimanche à jeudi |
| `0 0 9 * 5,*/2 * *`, `vi` | Vào 09:00chỉ trong Tháng 5 và  2 tháng | Vào 09:00, chỉ trong Tháng 5 và mỗi ngày 2 tháng |

  Rows 1 to 12 are unchanged. Every changed row is a list whose first member is a plain value (or, for the range-first row, a list with a later step member) in day-of-month, month, day-of-week or year.

- Behaviour changes for existing users, judged under the side-effect rule:
  1. Lists with a plain first member and a later step member get ", " after the time and lose the " , " after "and". Affected: users with such lists in day-of-month, month, day-of-week or year. The old text was visibly malformed ("AMonly"). Acceptable.
  2. Range-first lists with a later step (`1-3,*/2`) lose the stray comma after "and" but keep the glue after the time. The old text was already malformed and is now less so. Acceptable.
  3. In `vi`, the month step phrase begins with the same words as `commaEveryDay()` (`vi.ts:73`, ", mỗi ngày"), and `src/expressionDescriptor.ts:801` deletes those words when verbose is off. The deletion needs the leading ", ", so after this fix the phrase survives inside a list: the sentence now says "mỗi ngày 2 tháng" where the old text said " 2 tháng". The old text was malformed too. The new text uses an existing locale string (`vi.ts:118-120`, ", mỗi ngày %s tháng") and I cannot judge its wording. A standalone `*/2` month in `vi` still prints "2 tháng" (`pr-claims.out` in `sweep/`). Acceptable, but a maintainer may ask about it.
  4. Nobody gets worse output. The panel and the sweep found no changed output that was well formed before (`sweep.log`: `viol: 0, f012: 0, enNewBad: 0`). Anyone who snapshots the old malformed text in their own tests will see a diff.

## Review history
- Confirmed: CONFIRMATION.md (verdict CONFIRMED, `confirm.verdict`).
- Panel: SYNTHESIS.md. Roster: the full panel, fifteen Sonnet reviewers (EXEC-A, EXEC-B, O1 to O5, S1 to S8). Round 1 outcome REVISE (text fixes T1 to T6); round 2 re-review by EXEC-A, EXEC-B, O1, O4, O5, S3, S7; final outcome SHIP (`panel.outcome`). Round-1 files are in `rev0/`.
- Re-review: round 2 covered a text rewrite and an amended commit message. The code and the test were not changed between rounds.
- Text fixes applied: T1 (counts sentence replaced by the sweep description), T2 ("same output" changed to "same fault"), T3 (vi mechanism corrected), T4 (Fix paragraph, line numbers and documentation paragraph cut), T5 (Title line removed from the body), T6 (commit body rewrapped), plus two round-2 trims of "Not covered".
- Upstream check (2026-10-07): `main` at `c08a7d6fe361c2882cec9a511c943c46d1250c16` (2026-10-06, "Version 3.30.0"). In a fresh clone checked out at that commit, `git am` of the patch: applies cleanly (commit `957e54f`, author Andrew Stellman <andrew@stellman.com>). `run-tests` on that clone: `406 passing (123ms)`. Baseline at the tip is 405.
- Pull-request heads that touch the same files, in `upstream-check`: pr/387 (2026-06-11, "Add W offset translations to all locales"; touches `src/expressionDescriptor.ts` at about line 464 and `test/cronstrue.ts`); pr/420 (2026-10-06, "Fix zero-based month step normalization and add regression tests"; `src/cronParser.ts`, `test/cronParser.ts`, `test/cronstrue.ts`, not in `known_open_bugs.md`); pr/419 and pr/414, both merged. `git apply --check` of the patch succeeds on the pr/387 head and on the pr/420 head. Heads that changed the same loop: pr/374 (the origin of the strip, merged) and pr/370, merged. No newer head changes the multiple-values loop.
- Local check, as the operator's Mac command (`npm ci --ignore-scripts && npm test`) on a fresh clone of the patched tree, run on this Linux machine with Node v22.22.0 and the network (`localcheck.log`): `406 passing (164ms)`. Not run on a Mac.

## Things to know before submitting
- **Issue tracker.** `reference_docs/known_open_bugs.md` is the operator's `gh` export of 2026-10-05T23:05:01Z. It lists only what was OPEN then: issue #384 and draft PR #387 (both about day offsets for `W`). Neither is about this bug. Closed issues and closed PRs were not searched, and nothing was searched after 2026-10-05. A closed report of this is possible. `submit-draft-pr.sh` runs the tracker search before it opens anything.
- **Pull requests on the same files.** #387 (draft, W offsets) edits `src/expressionDescriptor.ts` far from this loop and `test/cronstrue.ts`; the patch applies on its head. #420 edits `test/cronstrue.ts` and the parser; the patch applies on its head. Whether #420 is open or closed is not known from here.
- **Panel.** Fifteen Sonnet reviewers, as above. All findings of the panel that were NOT adopted:
  - C1, fix the range-first list `0 9 * * 1-3,*/2` in the same PR (O1 and O4 in round 1; O3, EXEC-A, EXEC-B, S5, S8 optional). A one-condition change did fix it, but it broke well-formed minutes and hours output (`1-3,*/2 9 * * *` would print ", 1 through 3 and every 2 minutes, ..."). Dropped under the side-effect rule; O1 and O4 withdrew the request after reproducing that. The PR text says what is not covered. A maintainer may still ask for it. Logs of the attempt: `c1-attempt/`.
  - Extra tests for month, day-of-month and three-member lists (O1, S4, S2): not added, minimal-change rule; mutation runs showed each changed condition already has a failing test.
  - A note that `ar` and `ja` stay malformed (S5, S4): their separators are not ", ", so the strip never runs; locale wording is out of scope.
  - A note about the prettier warning on `test/cronstrue.ts` (O2, O3, EXEC-B): tooling fact, not in the PR; recorded above.
  - Unify the two strip styles, duplicate comment, the `!` assertion (S1, S6, O5): refactoring or style, left as is.
  - Possible conflict with #387 (S5): checked today, the patch applies on its head.
  - 3,358 `newBad` in the fixer's first sweep (S8): not classified; the later sweep reports `enNewBad: 0` for English rows.
  - Issue first (O4, S5, S1, S8, O1): all judged the change trivial (5 source lines, under the 30-line limit).
  - Performance (S6) and security (O2): no finding.
- **vi wording.** `vi.ts:118-120` reads "every day %s month" (EXEC-B, S7, O4, S8), so a maintainer may question the new `vi` sentence. It is an existing string; the old output was garbled too.
- **Not checked.** Closed tracker items; native-speaker wording of any locale; a Mac or Node 20/24 run (the local check used Node 22 on Linux); downstream snapshots of the old text.
- **Counts in the PR text.** "1,445 two- and three-member lists in each of the 7 fields, in all 42 locales, verbose on and off" is from `sweep/diff3.ts` (rerun in round 2: `{ total: 849660, diff: 120364, viol: 0, f012: 0, enNewBad: 0 }`, `sweep.log`). 1,445 x 7 x 42 x 2 = 849,660. The script is not part of the PR.
- **From POLICY.md, for the operator.** AI policy: silent; no rule found. No CLA or DCO file or sign-off line found; whether a CLA bot runs on the GitHub repository was not checked, so watch the PR for one. No changelog entry (`CHANGELOG.md:1` points to the Releases page). Issue first applies only to non-trivial changes (`CONTRIBUTING.md:5`); this one is small. There is no PR template. The bug template's checkbox "The cron expression being passed in is a valid expression" is for issues; the PR text states validity instead. The commit is authored by Andrew Stellman with no trailers. The expected GitHub login is `andrewstellman`. Marking the draft ready is the operator's action in the web UI.

## Checks by the orchestrating session (Opus, 2026-10-07, after the Sonnet workflow finished)

Everything above this section was written by the Sonnet-only workflow. These are my own runs, finished at 15:40 UTC.

- Why this is the second kit from this run: the first-ranked bug (BUG-011, the month step with `monthStartIndexZero`) was fixed upstream on 2026-10-06 by #419 with the same regex change, before it could be submitted. This bug was the next in the run's ranking and was confirmed, fixed and reviewed against the new upstream tip.
- Upstream `main` refetched: `c08a7d6f` (2026-10-06, "Version 3.30.0"), 249 pull-request heads, newest #420. The patch applies with `git am` to a fresh clone checked out at exactly that commit. Commit author `Andrew Stellman <andrew@stellman.com>`, no trailers, 2 files, 11 insertions, 1 deletion.
- Suite on the patched tip: `406 passing`. With only `src/expressionDescriptor.ts` reverted: `405 passing`, `1 failing`, the new case, with the "AMonly on Friday and , every 2 days" text.
- Every example in the PR text, run on the tip and on the fix: all eight outputs are as the text says (the three faulty lists and their corrected text; the step-first list unchanged; the range-first list `0 9 * * 1-3,*/2` losing its stray comma and keeping the glue; `1-3,*/2 9 * * *` unchanged; both `vi` sentences).
- My own differential test, separate from the workflow's sweep: 880 English expressions, every two- and three-member list from five kinds of member (plain value, range, `*/n`, range with step, start with step) in each of the six fields, in 5-, 6- and 7-field forms. I marked an output malformed if it has a stray comma (" and ,", ", ,"), a time glued to the next word, a doubled space, or "undefined".
  - Tip: 462 malformed. All 462 are in day-of-month, month, day-of-week or year.
  - Fix: the same 462 outputs changed and nothing else did. 432 are now well formed. 30 lost the stray comma and still have the time glued to the next word; all 30 are range-first lists (correction 2026-10-10: this line first said 372 and 90, a counting error; recounted from the saved raw output), the case the PR text lists under "Not covered".
  - No output that was well formed before changed. No minute or hour list changed. Nothing throws before or after.
- Where it came from: commit 286434e, "fix: remove double commas in descriptions with increment ranges and multiple values (#374)", 2026-02-09, first released in v3.12.0. On its parent (v3.11.0) `0 9 * * 5,0-4/2` printed "At 09:00 AM, only on Friday and , every 2 days of the week, ...": the stray comma after "and" was already there, and the glue after the time was not. So the "AMonly" glue is a regression from #374, and the stray comma is older. The range-first glue ("AMMonday through Wednesday") is also older than #374. The PR text does not say any of this, and it does not need to.
- Duplicates: the open items in your export (issue #384, draft #387) are about the `W` character. Of the pull-request heads numbered above 374, three differ from `main` in `src/expressionDescriptor.ts` (#379, #386, #387), and none of the three changes a line of this loop (I grepped each diff for the loop's variable names). The tracker's closed items are not searched until you run the command.
- What I would expect a maintainer to ask: why the range-first case is left out. The answer is in the PR text and in `c1-attempt/`: the one-line change that fixes it puts a leading ", " on 480 minute and hour outputs that are well formed today.

## Re-check by the orchestrating session (Opus, 2026-10-10, before submission)

- Upstream `main` moved to `872fffe` (2026-10-08, "Version 3.31.0"): #421 "Support day offsets on the W (nearest weekday) character" and #422 (publish workflow), both merged. #421 changes `src/expressionDescriptor.ts`, but only the `W` branch of the day-of-month description, not the list loop this patch changes. 251 pull-request heads, newest #422; no head above #418 touches the list loop.
- The patch applies with `git am` to a fresh clone at `872fffe`. Suite: `409 passing`. With only `src/expressionDescriptor.ts` reverted: `408 passing`, `1 failing`, the new test.
- Every example in the PR text, rerun on `872fffe` and on the fix: all outputs are as the text says.
- My differential test, rerun at `872fffe` with four day-of-month members added (`15W`, `15W-2`, `10W+3`, `L`): 1,872 expressions. On the 880 expressions from the first run, the fixed output is identical to the first run's. 552 outputs changed, all of them malformed before; 0 well-formed outputs changed; no minute or hour list changed. Lists with a `W` member throw ("can be specified only when the day-of-month is a single day") on both, so #421 does not meet this code. `L` lists are fixed like the others. The 30 still malformed are the range-first lists named under "Not covered".
- PR text updated: the step-first test is now at `test/cronstrue.ts:767` (was 753), and the suite count is 409 (408 before). The workflow's 42-locale sweep was not rerun at `872fffe`; #421 adds English strings only.

## The PR as it will be submitted
**Title:** Fix separators in lists with a plain first value and a step

> **Cron Expression**
> `0 9 * * 5,0-4/2`
>
> **Expected Output**
> "At 09:00 AM, only on Friday and every 2 days of the week, Sunday through Thursday"
>
> **Actual Output**
> "At 09:00 AMonly on Friday and , every 2 days of the week, Sunday through Thursday"
>
> The expression is valid. It is a standard 5-field expression whose day-of-week field is a comma list of the value `5` (Friday) and the range with step `0-4/2` (Sunday to Thursday). The same fault appears for `0 0 12 1,15-20/2 * ?` (day-of-month, Quartz-style 6 fields with `?`) and `0 9 * 1,3-9/2 *` (month, standard 5 fields). Both are valid.
>
> **Cause**
> In the multiple-values loop in `src/expressionDescriptor.ts`, the plain-value branch strips the leading ", " from every member, including the first, so the first member runs into the time. A later step member keeps its own leading ", " after the loop's " and ". Now only members after the first are stripped. The step-first case `0 9 * * 0-4/2,5,6` (`test/cronstrue.ts:767`) is unchanged.
>
> **Not covered**
> A range first with a later step, `0 9 * * 1-3,*/2`, still prints "At 09:00 AMMonday through Wednesday and every 2 days of the week". Adding the comma in the range branch also changes well-formed minutes and hours output (`1-3,*/2 9 * * *` would print ", 1 through 3 and every 2 minutes, ..."), so I left it.
>
> **Testing**
> Full suite: 409 passing (408 before, plus the new test). I compared old and new output for 1,445 two- and three-member lists in each of the 7 fields, in all 42 locales, verbose on and off. Output changed only in day-of-month, month, day-of-week and year, and only when a later member has a step.
>
> In `vi` the step phrase begins with the same words as `commaEveryDay()` (", mỗi ngày"), and `transformVerbosity()` in `src/expressionDescriptor.ts` deletes those words when verbose is off. The deletion needs the leading ", ", so the phrase now survives in a list. `0 0 9 * 5,*/2 * *` (valid, 7 fields with seconds and year) in `vi` went from "Vào 09:00chỉ trong Tháng 5 và  2 tháng" to "Vào 09:00, chỉ trong Tháng 5 và mỗi ngày 2 tháng". A standalone `*/2` month in `vi` still prints "2 tháng". I did not judge that wording.
>
> Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
## To submit
    bash submit-draft-pr.sh

The workflow script writes that file after this step. It runs the tracker search, asks before continuing, and opens a DRAFT pull request.

## Submission record

- 2026-10-10, about 22:38 UTC: draft pull request https://github.com/bradymholt/cRonstrue/pull/423 opened by Andrew with `submit-draft-pr.sh`. Only the final `gh pr view` output was pasted; the script stops on a failing local check, so the check either passed or was skipped with `SKIP_TESTS=1` (not known from here).
- Duplicate search (`../dup-search.out`, 22:36 UTC): 12 searches, 0 failed, one hit: #370 (closed), "Fix sentence structure for comma-separated day-of-month values with increments". Read from git: #370 is a pull request by copilot-swe-agent[bot] (three commits, 2026-01-29) that reworked the same multiple-values loop; it was closed without merging, and the maintainer merged #374 (286434e, 2026-02-09, "Fixes #194") instead. #374 is the change that introduced the "AMonly" glue this PR fixes. Not a duplicate: #370 is closed and its change is not on `main`.
- Checked after opening (git, sandbox, 22:39 UTC): PR head `4b78257d8df1d28eb9819a77e312ff9cebc042e0`, author Andrew Stellman <andrew@stellman.com>, one commit on `main` `872fffe` (still the tip), tree `b0179f4bbe7fae0145f49360d7afc6ab630993ca`, identical to the reviewed patch; no trailers.
- About 23:09 UTC: Andrew marked it ready for review (his report). The automatic Copilot review then posted "Changes recommended" about the Vietnamese verbose-off output. Analysis given to Andrew: the vi month-step string is ", mỗi ngày %s tháng" and "mỗi ngày" is also `commaEveryDay()`, which `transformVerbosity()` deletes; the standalone `*/2` month in vi prints "Vào 09:00 2 tháng" before and after; the list output was "Vào 09:00chỉ trong Tháng 5 và  2 tháng" and is now "Vào 09:00, chỉ trong Tháng 5 và mỗi ngày 2 tháng". No code change made; a reply was drafted for Andrew to post if he wants.
