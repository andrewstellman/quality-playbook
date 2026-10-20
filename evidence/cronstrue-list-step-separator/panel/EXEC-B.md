# EXEC-B: SHIP (medium)

Role: executor. Own copy: /work/batch/runs/cronstrue/scratch/panel-cronstrue-list-step-separator-EXEC-B (base-source copy: ...-EXEC-B-base). I did not read EXEC-A or any other panel file. Fixed clone not modified.

## Blind verdict (from patch, PR.md, source)
The change is 2 source hunks (+4/-1 lines) and one test. It adds `i > 0` to the plain-member strip and an `else if (i > 0 && startsWith(", "))` strip for step members. Logic reads right: the first member keeps the ", " that links it to the time, later members lose theirs because the loop adds the separators. Test title doubles as the expression, as the other tests do. No dist or CHANGELOG edits. PR.md has the expression, expected, actual, a validity statement, and the exact disclosure last line. Concerns before running anything: (a) the range-first case still glues, (b) locale side effects.

## Results table (EXEC-A job, done independently)
| red | green | revert | suite | repro | verdict |
|---|---|---|---|---|---|
| FAIL for the claimed reason | pass | FAIL again | 406 passing | broken->fixed | PASS |

- red (HEAD source restored to HEAD~1, new test kept), `test/cronstrue.ts -g "5,0-4/2"`:
  `1 failing` ... `AssertionError: expected 'At 09:00 AMonly on Friday and , every 2 days of the week, Sunday through Thursday' to equal 'At 09:00 AM, only on Friday and every 2 days of the week, Sunday through Thursday'` at test/cronstrue.ts:761. The assertion is the claimed glue plus stray " , ".
- green (fix restored), same filter: `1 passing`.
- revert (source part only reverted, whole test/cronstrue.ts run): `183 passing` `1 failing`.
- suite (fix, whole `run-tests`): `406 passing` (PR.md says 406; baseline 405). git status clean apart from my own scratch scripts.
- repro: the confirmer's three expressions give, on base, the glued output quoted in CONFIRMATION.md; on fix, I ran my own script (below). The three expressions from PR.md at fix:
  `0 9 * * 5,0-4/2` -> `At 09:00 AM, only on Friday and every 2 days of the week, Sunday through Thursday`
  `0 0 12 1,15-20/2 * ?` -> `At 12:00 PM, on day 1 of the month and every 2 days in a month, between day 15 and 20 of the month`
  `0 9 * 1,3-9/2 *` -> `At 09:00 AM, only in January and every 2 months, March through September`
  I did not execute the confirmer's repro.ts file itself (did not copy it); I reproduced the same inputs with my own script, so "repro" is equivalent, not identical.
- prettier: `./node_modules/.bin/prettier --check src/expressionDescriptor.ts test/cronstrue.ts` warns on test/cronstrue.ts only. lint.log shows the same warning on unmodified HEAD at other lines (824-832, 890) and that the added lines are not among them. I did not re-diff prettier output line by line.
- Line refs in PR.md ("lines 609-612") match HEAD~1 of this clone.

## My 3 edge inputs, base vs fixed
1. All locales (src/i18n/allLocales, 42 locales x 5 list expressions, base vs fix, 210 lines each; 200 lines differ). The fix removes the glue and the " , " in almost every locale. Examples: `de` `Um 09:00, nur jeden Freitag und alle 2 Tage der Woche, Sonntag bis Donnerstag`; `ko` base `오전 09:00금요일에만, , 주 중 2일마다` -> fixed `오전 09:00, 금요일에만, 주 중 2일마다`. No new double comma, no new glue found. Not fixed, and pre-existing in base: `ru`/`bg`/`tg` `и  каждые` (double space), `id` `setiap hari 2  dalam`, `zh_CN` double spaces, `ja` (no ", " format, unchanged).
   Side effect, locale `vi` month list `0 9 * 1,3-9/2 *`: base `Vào 09:00chỉ trong Tháng 1 và  2 tháng, ...` -> fixed `Vào 09:00, chỉ trong Tháng 1 và mỗi ngày 2 tháng, ...`. The locale string is `vi.ts:119` `", mỗi ngày %s tháng"` ("every day %s months"), so the step text now says "every day" for a month step. Standalone `0 9 * */2 *` in `vi` prints `Vào 09:00 2 tháng` (the phrase is dropped there). This matches what PR.md says it did not judge. Under submit_rules rule 12 this is a locale string with a wrong unit that the fix newly exposes. Affected: Vietnamese users with a month list like `1,*/2` (very unlikely, previously also garbled). `sw` day-of-week now `kila siku 2 ya wiki` (reads fine).
2. Options on the list case: `monthStartIndexZero:true` `0 9 * 0,2-8/2 *` -> `At 09:00 AM, only in January and every 2 months, March through September`; `dayOfWeekStartIndexZero:false` `0 9 * * 5,1-4/2` -> `At 09:00 AM, only on Thursday and every 2 days of the week, Sunday through Wednesday`; `use24HourTimeFormat` (with verbose, in a separate run) `At 09:00, only on ...`. All fixed, none regress. Base had the glue in each.
3. Neighbours that must not change (minutes, hours, step-first, step-middle, three-member, Quartz `L`, `#`): `5,10-30/5 * * * *`, `5,*/10 * * * *`, `7,8,*/5 * * * *`, `*/5,7 * * * *`, `0 5,10-20/2 * * *`, `0 9 * * 0-4/2,5,6`, `0 9 * * */2,5` identical base vs fix. Changed and now well formed: `0 9 * * 5,0-4/2,6` -> `At 09:00 AM, only on Friday, every 2 days of the week, Sunday through Thursday, and only on Saturday` (base had `Friday, , every 2`); `0 9 L,15-20/2 * *` -> `At 09:00 AM, on day the last day of the month and every 2 days ...` (the "day the last day" wording is older and unrelated); `0 9 * * 1#2,3-6/2`, `0 9 * * 5L,0-4/2`, `0 9 ? * 5,0-4/2`, `0 0 0 * * * 2020,*/2` fixed. All my expressions are valid for their dialect (lists of values, `range/step`, `*/step`).
   Still broken (same loop, not touched): `0 9 * * 1-3,*/2` -> `At 09:00 AMMonday through Wednesday and every 2 days of the week` (base had also " , "); `0 9 * * 1-3,5,*/2` -> `At 09:00 AMMonday through Wednesday, only on Friday, and every 2 days of the week`. Cause: `replace(", ", "")` on the range-without-increment branch at i=0.

## Findings
1. (Low, optional) Partial fix of one visible class. Plain-range first member with a later step still prints `AMMonday` after this patch; PR.md "Not covered" says so honestly and gives a correct example. A maintainer may ask for it in the same PR. It is a different branch (range, not plain value), so leaving it out is defensible under "minimal change". No change required. If the operator wants it, the one-line change is `if (isSegmentRangeWithoutIncrement) { currentDescriptionContent = i > 0 ? currentDescriptionContent!.replace(", ", "") : currentDescriptionContent; }`, but I did NOT test that and it needs the no-step range-list case checked (`1-3,5` uses the other format path); do not add it without running the suite.
2. (Low) Vietnamese month-step side effect above (`mỗi ngày 2 tháng`). PR.md already discloses the `vi` example and says it did not judge the wording. Suggest keeping that sentence. The side-effect rule is not triggered: the previous output was already broken for that input, the audience is tiny.
3. (Nit) PR.md lists "lines 580-596" and "609-612" for c08a7d6; the 609-612 range is right at HEAD~1, I did not verify 580-596 exactly. The first sentence of the Cause paragraph is accurate against my run.
4. (Nit) PR.md does not mention that prettier warns on test/cronstrue.ts at unrelated lines (lint.log says so). Add only if the operator wants it; it is not a defect of this patch.
5. No trailer in the commit message (checked with `cat -A`: author Andrew Stellman, no Co-Authored-By). Disclosure line is the last line of PR.md and exact.

## Not checked
- The 849,660-combination comparison claimed in PR.md (I ran 210 + 62 + a few dozen inputs, not that sweep).
- The confirmer's own repro.ts file, closed tracker items, upstream tip after c08a7d6 (upstream-check main is c08a7d6 locally; I did not fetch).
- Native-speaker wording in any locale.
- Whether the maintainer likes the combined sentence wording ("only on Friday and every 2 days of the week, ...").

## After reading CONFIRMATION.md
Confirmation agrees with my red/green results. Its probes (`0 9 * * 1,3-5/2`, `5,*/2`, year case) match what I saw; its claim that the glued output on `0 9 * * 1-3,*/2` is BUG-018 matches my "still broken" case. It said the verbose option and non-English locales were not checked; I checked both (edge 1, edge 2) with no regression. No reason found to change the blind verdict.
