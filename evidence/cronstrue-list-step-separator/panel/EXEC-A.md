# EXEC-A: SHIP (high)

Role: executor. Copy: /work/batch/runs/cronstrue/scratch/panel-cronstrue-list-step-separator-EXEC-A (HEAD~1 = c08a7d6, then patch parts applied by `git show bf44d63 -- <path> | git apply`). The fixed clone was not modified.

## Blind verdict (from patch, PR.md, source, before CONFIRMATION.md)
The code change is correct and small: 2 hunks, +4/-1 lines of source, one test. Base `src/expressionDescriptor.ts` strips a leading ", " in the plain-member branch for every member (including i=0), which glues the first member to the time ("AMonly"). A later step member never had its ", " stripped, which gives "and , every". The patch adds `i > 0` to the plain branch and adds a strip for `i > 0` in the step branch. i=0 is never touched in the step branch, so the step-first case (`0 9 * * 0-4/2,5,6`) cannot change. Within scope (valid 5/6/7-field lists, no locale wording changes, under 30 lines), no CHANGELOG/dist edits, no agent trailers in the patch, disclosure line is last in PR.md, no em dashes in PR.md (grep found none).

## Execution (all at base c08a7d6, test = `0 9 * * 5,0-4/2`)
RED (test part only):
```
1 failing
  AssertionError: expected 'At 09:00 AMonly on Friday and , every 2 days of the week, Sunday through Thursday' to equal 'At 09:00 AM, only on Friday and every 2 days of the week, Sunday through Thursday'
```
The assertion is the claimed one (glued "AMonly" and stray " , "), not a typo or a different cause.
GREEN (test + source): `1 passing`.
Touched file `test/cronstrue.ts`: `184 passing`. Full suite (run-tests, no args): `406 passing` (405 at tip + the new test, matches PR.md).
REVERT (source hunks reverted with `git apply -R`, test kept): `0 passing, 1 failing`, same AssertionError as RED.
REPRO (confirmer's repro.ts copied to my dir, run with ts-node on the fixed tree):
```
"0 9 * * 5,0-4/2" => At 09:00 AM, only on Friday and every 2 days of the week, Sunday through Thursday 
"0 0 12 1,15-20/2 * ?" => At 12:00 PM, on day 1 of the month and every 2 days in a month, between day 15 and 20 of the month 
"0 9 * 1,3-9/2 *" => At 09:00 AM, only in January and every 2 months, March through September 
control At 09:00 AM, every 2 days of the week, Sunday through Thursday, only on Friday, and only on Saturday
exit=0
```
(exit=1 on the unfixed tree, per CONFIRMATION.md.)
Prettier: `[warn] test/cronstrue.ts`, `src/expressionDescriptor.ts` clean. I stashed the patch and re-ran on the base: same warning, so it is pre-existing (lint.log says it is at lines 824-832 and 890; I did not diff those lines myself).

## Side effects (differential, my own, old vs new source)
1. 15 hand-picked expressions (probe.ts): changes only where a plain first member precedes a step member. Controls unchanged: `0 9 * * 0-4/2,5,6`, `0 9 1,15-20 * *`, `5-45/10,*/5,9 * * * *`.
2. 3,456 six-field expressions (seconds x minutes x hours x dom x month x dow, with step lists in each) x 4 option sets (default, verbose, locale de, use24HourTimeFormat) = 13,824 outputs: 12,672 changed. Every changed expression has a step in dom, month or dow; none changed because of seconds/minutes/hours alone. No output that stayed unchanged contains " , ". I did not run the year field in this sweep.
3. Locales via `cronstrue-i18n` (de, fr, vi, sw): the glue and " , " are fixed. vi: `0 0 9 * 5,*/2 * *` old "Vào 09:00chỉ trong Tháng 5 và  2 tháng", new "Vào 09:00, chỉ trong Tháng 5 và mỗi ngày 2 tháng". sw: old "Kwa 09:00kwa Mei tu na , kila mwezi wa 2", new "Kwa 09:00, kwa Mei tu na kila mwezi wa 2". The vi/sw phrase that now appears is the locale's own text (`vi.ts:118` `", mỗi ngày %s tháng"`), previously cut off with the comma. This matches PR.md's disclosure.
Who is affected: users whose expression has a plain first value and a later step in dom/month/dow/year. They previously got visibly broken text ("AMonly", " , "). Only the broken part changes. Likelihood of anyone depending on the old text: very low. Not a side-effect-rule drop.

## Findings
1. (Minor, optional) PR.md "Not covered": `0 9 * * 1-3,*/2` still prints `At 09:00 AMMonday through Wednesday and every 2 days of the week` (I ran it: new output as quoted). Same root cause (the `replace(", ", "")` in the range branch also hits i=0). The PR discloses it and the title says "plain first value", so it is accurate. A maintainer might ask for it in the same change. No change required; if the operator wants it, it needs a third condition (`i > 0 ? replace : keep`) and a test, which also changes wording-neutral output for `1-3,*/2` only.
2. (Minor, text) PR.md says "I compared old and new output over 849,660 list combinations in every locale". I did not re-run that. My smaller sweep (above) supports the claim "only when a later member has a step" for dom/month/dow. Operator should be able to reproduce the number from the fixer's script before keeping it, or drop the number. Suggested replacement if unreproducible: "I compared old and new output over a large set of list combinations in several locales, verbose on and off."
3. (Minor) PR.md "Expected Output" sentence is awkward English ("only on Friday and every 2 days of the week, Sunday through Thursday") but follows the library's own wording; PR.md already says so under "Documentation relied on". No change.
4. Prettier warning on test/cronstrue.ts is pre-existing; do not reformat. PR.md does not mention it; adding nothing is fine.

Not checked: closed upstream issues/PRs (forge unreachable), `npm ci && npm test` on a fresh checkout/Mac, year field in my sweep, native-speaker wording in vi/sw, the 849,660 count, Node 20/22/24 matrix.

## Table
| red | green | revert | suite | repro | verdict |
|---|---|---|---|---|---|
| fail, AMonly/" , " as claimed | 1 passing | fail again, same message | 406 passing (file: 184) | exit 0, 3 expressions fixed | PASS |
