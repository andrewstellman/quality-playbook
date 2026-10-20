# EXEC-B round 2: SHIP (high)

Blind: I read only SYNTHESIS.md, rev0/, the revision files, sweep/ and c1-attempt/ (as told). I did not open other files in panel/. My clone: `scratch/panel2-cronstrue-list-step-separator-EXEC-B` at c08a7d6 (HEAD checked). Helper clones: `...-EXEC-B-alt`, `...-EXEC-B-am`. I did not touch the fixer clone except `git rev-parse` on it.

## Steps 1-4 (my own runs)
- Red (test hunk only): 0 passing, 1 failing. `AssertionError: expected 'At 09:00 AMonly on Friday and , every 2 days of the week, Sunday through Thursday' to equal 'At 09:00 AM, only on Friday and every 2 days of the week, Sunday through Thursday'` at test/cronstrue.ts:761. This is the claimed fault (glued "AMonly", stray " , ").
- Green (source hunks added): 1 passing.
- Revert (source hunks removed, test kept): same assertion text, 1 failing. Source hunks restored afterwards.
- Touched file test/cronstrue.ts: 184 passing. Full suite: 406 passing.
- Prettier: `--check` warns on test/cronstrue.ts both with the change and with it stashed (base), so the warning is not from this change; src passes.

## Step 5: repro and PR.md strings
I ran old (c08a7d6 src) against new (fixed src) in `chk/r.ts`. Every output string quoted in PR.md matches verbatim:
- `0 9 * * 5,0-4/2` actual and expected: match.
- `0 0 12 1,15-20/2 * ?` and `0 9 * 1,3-9/2 *` both go from glued text plus " , " to a clean sentence. PR.md says "the same fault", which is accurate, and no longer says "same output". Validity: 6-field Quartz with `?`, and 5-field. Both fine.
- `0 9 * * 0-4/2,5,6` is [SAME] old/new (step-first claim true; test is at test/cronstrue.ts:753 at base, checked).
- `0 9 * * 1-3,*/2` new = "At 09:00 AMMonday through Wednesday and every 2 days of the week": matches "Not covered".
- vi: `0 0 9 * 5,*/2 * *` old "Vào 09:00chỉ trong Tháng 5 và  2 tháng", new "Vào 09:00, chỉ trong Tháng 5 và mỗi ngày 2 tháng"; standalone `0 0 9 * */2 * *` still "Vào 09:00 2 tháng". Match.
- vi.ts:73-74 `commaEveryDay` is ", mỗi ngày"; vi.ts:118-119 month step is ", mỗi ngày %s tháng"; expressionDescriptor.ts:798 at tip is the `commaEveryDay()` removal. Checked. PR.md names only `vi`; `sw` is right to leave out (sw month step is ", kila mwezi wa %s", not the commaEveryDay words; sw output has no leftover phrase).
- Sweep numbers: I reran `sweep/diff3.ts` (old/new src copies) and got `{ total: 849660, diff: 120364, viol: 0, f012: 0, enNewBad: 0 }`. 17 x 17 x 5 = 1,445 lists, 7 fields, 42 locales, 2 verbosities = 849,660. Matches the "1,445 / 17 / 849,660 / 120,364 / only dom, month, dow, year, only with a later step" sentences. The script is not in the PR (fine, the PR describes it).

## Three edge inputs of my own (old vs new, `chk/r.ts`, `chk/m.ts`)
1. `30 17 * * 5,1-5/2` with `use24HourTimeFormat: true`: old "At 17:30only on Friday and , every 2 days of the week, Monday through Friday"; new "At 17:30, only on Friday and every 2 days of the week, Monday through Friday". Good.
2. `0 0 9 * * 2,*/2 2020,2022-2030/2` (two list fields at once, 7 fields): old "...of the weekonly in 2020 and , every 2 years, ..."; new "At 09:00 AM, only on Tuesday and every 2 days of the week, only in 2020 and every 2 years, 2022 through 2030". Both fields fixed, fields separated.
3. Non-English: de `0 9 * * 5,0-4/2` old "Um 09:00nur jeden Freitag und , alle 2 Tage der Woche, ..." new "Um 09:00, nur jeden Freitag und alle 2 Tage der Woche, Sonntag bis Donnerstag". Also fr verbose, es `0 9 15 5,*/3 *` ("el día 15 del mes, sólo en mayo y cada 3 meses"): clean.
Extra: `monthStartIndexZero: true` `0 9 * 1,*/2 *` fixed; `0 9 * * 5,0-4/2,6` fixed; `dayOfWeekStartIndexZero: false` with `6,0-4/2` throws the same error old and new (0 is invalid there, my input was wrong); `ja` `5,0-4/2` is [SAME] and still malformed (its separators are not ", "), as SYNTHESIS already notes. Minutes/hours plain-first lists (`5,*/2 9 * * *`, `0 5,*/2 * * *`, `5,*/2 5,*/2 * * * *`) are [SAME].

## Step 6: git am
`git am` of 0001-*.patch on a clean clone of c08a7d6 succeeded; `HEAD^{tree}` = `dd64a3b59a3457497ccbe8bbfb0654a1090ab472`, equal to the fixer clone's. Author Andrew Stellman, no Signed-off-by / Co-Authored-By. Body lines 71, 70, 67, 46 chars (wrapped at 72). Note: the commit has no disclosure line; POLICY.md puts the disclosure in PR text only (line 11), and rules forbid trailers.

## Step 7: round-1 findings in my scope
- T1 (849,660 wording): fixed, and now reproduced by me (round 1 EXEC-B had not rerun it).
- T3 (vi mechanism, vi.ts "every day %s month"): fixed; the mechanism sentence is true and disclosed, and the garbled-then-different vi wording is flagged "I did not judge that wording".
- T2, T4, T5, T6: fixed (no Title line, no Fix paragraph, no line ranges except test:753 and expressionDescriptor.ts:798 which are correct at c08a7d6, commit body rewrapped).
- Round-1 EXEC-B note on prettier: already out of the PR, recorded in lint.log; I reconfirmed.
- C1: see below.

## C1 claim check and the alternative
- The one-condition change `(i > 0 || !doesExpressionContainIncrement)` at line 593, tested in `chk/c1`: `1-3,*/2 9 * * *` becomes ", 1 through 3 and every 2 minutes, between 09:00 AM and 09:59 AM"; `0 1-3,*/2 * * *` becomes "On the hour, , 01:00 AM through 03:00 AM and every 2 hours"; `1-3,*/2 * * * * *` becomes ", 1 through 3 and every 2 seconds". So PR.md's claim is true, and it also hits seconds (PR says "minutes and hours", so it understates, not wrong). My sweep (129,472 runs, 8 locales): 5,040 changed vs shipped, 2,184 of them in seconds/minutes/hours. Declining C1 as a one-condition add-on was right.
- A different small fix does exist: `isSegmentRangeWithoutIncrement && (i > 0 || range || !doesExpressionContainIncrement)`. `range` is passed only by seconds/minutes/hours (lines 241, 275, 319), so those keep stripping. Mine, in `chk/alt`: 0 changes in seconds/minutes/hours (2,856 changed runs, all dom/month/dow/year), `0 9 * * 1-3,*/2` gives "At 09:00 AM, Monday through Wednesday and every 2 days of the week", `1-3,5` unchanged, suite 405 passing (no new test added in that clone). It reuses `range` as a "time field" marker, which is implicit. Judgement: declining was still right for this PR (scope, fixer-visible hack, extra test and review). A maintainer who asks can be told a follow-up is possible. PR.md "Fixing the range case needs a different change" is true.

## Step 8: new problems in the revision
None blocking. Nits only: (a) "Not covered" says "minutes and hours", seconds also change; optional to add "seconds". (b) "(the stray " , " is gone, ...)" is a little dense; optional. Side-effect rule: affected users are lists with a plain first member and a later step member in dom/month/dow/year; old text was visibly malformed; vi users get "mỗi ngày 2 tháng" inside lists (disclosed); low likelihood. Not a DROP. Last line of PR.md is the exact disclosure line; no em dashes; no Title line.

## Not checked
Closed upstream issues and PRs (tracker unreachable). A fresh `npm ci && npm test` on a Mac or Node 20/22/24. Native-speaker wording. The conflict with draft PR #387. Locales outside the 42 in the sweep. Whether a maintainer would accept the `range`-based alternative.

| red | green | revert | suite | repro | patch-applies | PASS/FAIL |
|---|---|---|---|---|---|---|
| fails, glued "AMonly ... and , every" (test:761) | 1 passing; file 184 passing | fails again, same text | 406 passing | all PR.md strings and 849,660/120,364 reproduced | yes, tree dd64a3b5... matches | PASS |
