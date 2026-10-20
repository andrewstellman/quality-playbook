# Synthesis: cronstrue-list-step-separator (BUG-009)

Panel: all fifteen roles ran (Sonnet), each wrote `panel/<ROLE>.md`. I read every file in full. No REJECT, no DROP.

| Item | A | B | O1 | O2 | O3 | O4 | O5 | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cronstrue-list-step-separator | S | S | F | S | S | F | F | S | S | F | S | S | S | F | S |

S = SHIP, F = FIX-REQUIRED, R = REJECT, D = DROP, – = not run. Outcome: REVISE (`panel.outcome`).

What the executors established (both ran independently): the new test fails at base for the claimed reason (`AMonly ... and , every`), passes with the fix, fails again with only the source hunks reverted, suite is 406 passing (405 at tip plus the new test), and the confirmer's repro goes from exit 1 to exit 0. Six reviewers ran old-versus-new sweeps (hundreds to 131,712 runs, many locales, verbose on and off) and none found a changed output that was well formed before. No reviewer found a security angle or a performance cost. The side-effect rule was applied by O1, O2, O3, O4, S4, S5, S7 and S8 and nobody called for a DROP: affected users are those with a list whose first member is plain and a later member has a step, the old text was visibly malformed, likelihood is low.

## Findings that must change

Text (PR.md and commit message; apply, then note in REVIEW.md):

- **T1. The "849,660 list combinations" sentence is wrong and cannot be reproduced.** Raised by EXEC-A, O1, O2, O3, O4, O5, S1, S3, S4, S5, S7 (S6, S8, EXEC-B, S2 said they did not rerun it). S3 and S7 rebuilt the number from the fixer's `scratch/fix-cronstrue-list-step-separator-fixer/diff3.ts`: 1,445 lists x 7 fields x 42 locales x 2 (verbose) = 849,660 runs, not "list combinations". The script is not in the PR, so the maintainer cannot rerun it. S7's own 131,712-run sweep supports "changed only in day-of-month, month, day-of-week and year, and only when a later member has a step". Replace the sentence with (S3/S7 wording): `I compared old and new output for 1,445 two- and three-member lists built from 17 sample members, placed in each of the 7 fields, in all 42 locales, verbose on and off (849,660 runs). Output changed only in day-of-month, month, day-of-week and year, and only when a later member has a step.` If the operator will not stand behind the count, cut the count and keep the second sentence only.
- **T2. "The same output appears for `0 0 12 1,15-20/2 * ?` and `0 9 * 1,3-9/2 *`" is false** (O5, S7). The three strings differ. Replace with: `The same fault appears for `0 0 12 1,15-20/2 * ?` (day-of-month, Quartz-style 6 fields with `?`) and `0 9 * 1,3-9/2 *` (month, standard 5 fields). Both are valid.` (S7 noted validity was only argued for the first expression.)
- **T3. The `vi`/`sw` sentence names the wrong mechanism** (S7; O3 independently points at the same line). Nothing in the list loop strips the step phrase. `src/expressionDescriptor.ts:798` at c08a7d6 (line 801 in the fixed clone) removes `commaEveryDay()` text when verbose is off, and `vi`/`sw` step phrases begin with the same words. That removal needs the leading ", ", so the phrase now survives inside a list. Replace the sentence with S7's text: `In vi and sw the step phrase begins with the same words as commaEveryDay() (", mỗi ngày", ", kila siku"), and expressionDescriptor.ts:798 deletes those words when verbose is off. The deletion needs the leading ", ", so the phrase now survives in a list: `0 0 9 * 5,*/2 * *` in vi went from "...và  2 tháng" to "...và mỗi ngày 2 tháng" (a standalone `*/2` month in vi still prints "2 tháng"). I did not judge that wording.` The operator should know before sending that `vi.ts:118-120` reads "every day %s month" (EXEC-B, S7, O4, S8), so a maintainer may ask about it. It is an existing locale string and the old output was already garbled, so I do not treat it as a DROP.
- **T4. Cut the "Fix:" paragraph, the line numbers and the "Documentation relied on" paragraph** (O5, S3, S1; S7 on the citation form). The "Fix:" paragraph restates the diff. "lines 609-612" and "lines 580-596" will drift (and 580-596 should be 580-597 per S7). S3's replacements: Cause: `In the multiple-values loop in `src/expressionDescriptor.ts`, the plain-value branch strips the leading ", " from every member, including the first, so the first member runs into the time. A later step member keeps its own leading ", " after the loop's " and ". Now only members after the first are stripped. The step-first case `0 9 * * 0-4/2,5,6` (`test/cronstrue.ts:753`) is unchanged.` Documentation: `No documentation gives wording for combined lists. The expected text follows the existing test for `0 9 * * 0-4/2,5,6` (`test/cronstrue.ts:753`).` The README:17 quote can stay if the operator wants a verbatim citation, but O5 and S3 both say it supports no wording, so I would drop it.
- **T5. Drop the `**Title:**` line from the PR body** (O1, S3). The title goes in the title field; the body starts at `**Cron Expression:**`.
- **T6. Commit message body**: lines are 75, 81 and 79 characters, it repeats the title and PR cause, and "ran into the time" is vague (O1, O5, S1, S3, S8 as a nit). Use O5's wrapped body: `` `0 9 * * 5,0-4/2` printed "At 09:00 AMonly on Friday and , every 2 days of the week". The leading ", " was stripped from the first member too, so it ran into the time, and a later step member kept its own ", ". Only members after the first are stripped now.`` (wrap at 72). Regenerating the patch is a step 6 action; the fixed clone is not to be modified here.

Code or scope (a revision, so it needs the focused re-review of both executors plus O1, O3, O4):

- **C1. Range-first lists are still broken in the same loop** (O1, O4 FIX-REQUIRED; O3, EXEC-A, EXEC-B, S5, S8 flagged it as optional). `0 9 * * 1-3,*/2` still prints `At 09:00 AMMonday through Wednesday and every 2 days of the week`. PR.md discloses this and I confirmed from three reviewers' runs that the disclosure is accurate. O1, O3 and O4 each tried the same one-condition change at `src/expressionDescriptor.ts:593`, `if (isSegmentRangeWithoutIncrement && (i > 0 || !doesExpressionContainIncrement)) {`, and each reported `406 passing`, `1-3,5` unchanged, and `1-3,*/2` becoming `At 09:00 AM, Monday through Wednesday and every 2 days of the week`. O1's differential run showed 60 remaining suspect English rows before and 0 after. I did not run it myself. This is a scope call for the operator: either (a) fold the condition in, add `0 9 * * 1-3,*/2` as a second test and delete the "Not covered" paragraph, then re-review (my recommendation, because it is one condition in the same function and the maintainer is likely to ask), or (b) ship as is, keeping the "Not covered" paragraph, which is accurate. Either way the title ("plain first value") stays accurate.

## Findings not worth adopting

- **Add tests for month, day-of-month, three-member lists** (O1, S4, S2 note). S2's mutation runs show each changed condition already has a failing test; the code path is shared; the minimal-change rule says one test. If C1 is adopted, add only that case.
- **Add a sentence that `ar` and `ja` are unchanged and still malformed** (S5, S4). Their separators are not ", ", so the strip never fires. That is locale wording, out of scope by the rules, the fix does not worsen them, and O5 and S3 want the text shorter, not longer. Operator should know it if a maintainer asks.
- **Mention that `prettier --check test/cronstrue.ts` already warns at base** (O2, O3, EXEC-B, optional). It is a tooling fact, recorded in `lint.log` and REVIEW.md, and O5, S1, S2 and S4 say not to put it in the PR. Do not reformat the test file.
- **Duplicate the new comment differently or unify the two strip styles** (S1, S6, O5). The added comment copies the existing one 15 lines below; O5 and S1 call it optional. Unifying the `.replace` and `startsWith` styles would be refactoring. Leave it.
- **Drop the `!` assertion or switch to the `segmentDescription &&` guard** (S1). It matches the neighbouring `!.replace` at line 593. Leave it.
- **Possible textual conflict with draft PR #387** (S5). It touches the same file and is about `W` offsets; nobody checked for a conflict and a conflict would be cheap. Noted for the operator, no change.
- **The 3,358 `newBad` count in the fixer's `diff2.out`** (S8). The examples in that file are `ru`/`bg`/`tg` double-space defects that exist at base. I did not classify all 3,358, so I cannot say they are all pre-existing or range-first. `diff3.out` reports `enNewBad: 0` for English rows that changed. This does not change what PR.md says.
- **Should an issue come first under CONTRIBUTING.md** (O4, S5, S1, S8, O1). All judged the change trivial (about 5 source lines, one test, no locale file edited, under the 30-line limit in the rules). Agreed.
- **Performance** (S6): one extra `i > 0` and a `startsWith` on a short string; measured noise only. No finding.
- **Security** (O2): none; PR text has no security framing.

## Not checked by the panel

Closed upstream issues and PRs (tracker unreachable; PR.md claims no search). A fresh `npm ci && npm test` on a Mac and Node 20/22/24. Native-speaker wording of any locale. Downstream consumers that snapshot the old text. The 849,660-run sweep itself (only S3 and S7 read its script; nobody reran it).

## Round 2

Round 1 outcome was REVISE. Round-1 files are kept in `rev0/` (patch, PR.md, logs). The code and the test are unchanged from round 1. The commit was re-amended (message only) and PR.md rewritten. The patch was regenerated: `0001-*.patch` applies to a clean clone of c08a7d6 and gives the tree of the fixed clone's HEAD (6428d6a, tree dd64a3b); EXEC-A and EXEC-B both checked this. The fixed clone is clean, one commit, author Andrew Stellman, no trailers.

### What was changed, per finding

- **T1 (849,660 sentence):** I reran the fixer's script (`sweep/diff3.ts`, 2m17s): `total 849660, diff 120364, viol 0, f012 0, enNewBad 0` (`sweep.log`). The first rewrite used S3/S7's wording with the counts. O5 and S3 then asked for the counts to go because the maintainer cannot rerun a script that is not in the PR. Final PR text: "1,445 two- and three-member lists in each of the 7 fields, in all 42 locales, verbose on and off. Output changed only in day-of-month, month, day-of-week and year, and only when a later member has a step." Script and log stay in `sweep/` for the operator. S7 and O5 reran the script and got the same numbers.
- **T2:** "same output" replaced by "same fault", with the field and dialect named and both expressions called valid.
- **T3:** mechanism corrected (`commaEveryDay()` removal in `transformVerbosity()`, which needs the leading ", "). Line number dropped (S3 N3). `sw` left out of the sentence: S3 showed the `sw` month phrase does not begin with `commaEveryDay()`, so the mechanism does not apply to it (my own run: sw month `kila mwezi wa 2`). The vi example is now stated to be a valid 7-field expression (S7 nit 2).
- **T4:** "Fix:" paragraph, line numbers and "Documentation relied on" section removed (the last at O5/S3 round-2 request). Cause paragraph uses S3's text.
- **T5:** `**Title:**` line removed; headings match `.github/ISSUE_TEMPLATE/bug_report.md` (no colons).
- **T6:** commit body replaced by O5's wording, wrapped (longest line 71). Subject unchanged.
- **O5/S3 round-2 trims:** "Not covered" cut to its two facts (what still prints, why it was left); sweep counts and the filter caveat cut. PR.md 394 words (round 1: 393, first round-2 draft: 494). The pre-trim draft is `rev1-draft/PR.md`.

### What was not adopted, and why

- **C1 (range-first, one-condition change).** Not adopted. I had a fixer try it. It fixes `0 9 * * 1-3,*/2` but breaks well-formed output in minutes, hours (and seconds, per O4 and EXEC-B): `1-3,*/2 9 * * *` goes from "1 through 3 and every 2 minutes, between 09:00 AM and 09:59 AM" to ", 1 through 3 and every 2 minutes, ...", and `0 1-3,*/2 * * *` from "On the hour, 01:00 AM through 03:00 AM and every 2 hours" to "On the hour, , 01:00 AM ...". I ran both myself. The round-1 reviewers who tried the change (O1, O3, O4) had checked only day-of-month, month and day-of-week. This is the side-effect rule: the change hurts existing users with well-formed output. A variant limited to those three fields would be more than one condition. O1 tried one in round 2 and found a double space in zh_CN; EXEC-B found a range-based alternative but judged declining right. The attempt's logs are in `c1-attempt/` for the record only; they describe a clone state that was discarded. PR.md says plainly what is not covered and why.
- Extra tests (month, three-member), `ar`/`ja` note, prettier note, comment duplication, `!` assertion, draft PR #387 conflict, issue-first, performance, security: as in round 1, not adopted, no new information.
- Minor nits left: "built from 17 sample members" was dropped from the PR so S7's/S3's note on the third-member set no longer applies; "Not covered" does not name seconds (the sentence names what was run: minutes and hours).

### Re-review verdicts (round 2, `panel/<ROLE>-round2.md`)

| Role | EXEC-A | EXEC-B | O1 | O4 | O5 | S3 | S7 |
|---|---|---|---|---|---|---|---|
| Round 2 | S | S | S | S | F (text cuts) | F (text cuts) | S |
| After trim | | | | | F (low): one wording cut, applied | S (round2b) | |

S = SHIP, F = FIX-REQUIRED. O5's and S3's round-2 findings were text cuts only; both were applied. S3 re-checked the trimmed text (`S3-round2b.md`, SHIP, high). O5's re-check (`O5-round2b.md`, FIX-REQUIRED, low) asked for one more wording cut in "Not covered" ("obvious", a restatement); I applied it using O5's own sentence plus "well-formed", and O5 did not see the edited sentence. No reviewer asks for a code change; O1 and O4 withdrew their round-1 scope finding after reproducing the minutes/hours regression.

Executors (full red, green, revert, suite, repro, patch-applies sequence on the amended commit): both PASS, 406 passing.

Not checked in round 2: closed upstream issues and PRs (tracker unreachable); `npm ci && npm test` on a Mac; Node 20/22/24; native-speaker wording; whether the maintainer will want the range-first case in the same PR.

Outcome: SHIP. The code is the round-1 code that every reviewer found correct, the text is the reviewers' own suggested wording and was run, and the one open request left is an applied wording cut. The operator should read the "Not covered" paragraph before sending: a maintainer may ask for the range-first case.
