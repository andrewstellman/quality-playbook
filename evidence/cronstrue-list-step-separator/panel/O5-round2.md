# O5 round 2: FIX-REQUIRED (medium)

Scope: slop only. Code, test and commit message are fine. PR.md is true but too long for a 5-line fix. Every fix below is a cut.

## What I ran (fresh clone `scratch/panel2-cronstrue-list-step-separator-O5`, HEAD c08a7d6, `git am` of the patch clean)
- Author is Andrew Stellman, no trailers, subject unchanged, body lines are 71, 70, 67 and 46 characters. Suite: `406 passing`; an unpatched clone gives `405 passing`.
- Every quoted output string in PR.md reproduced exactly (old clone, patched clone, scripts in `scratch/panel2-...-O5-scripts/run.ts`): the three Expected/Actual pairs, `0 9 * * 0-4/2,5,6` unchanged, the `vi` before and after strings (two spaces after "và" before, one after), standalone `*/2` month in `vi` is "Vào 09:00 2 tháng", and `0 9 * * 1-3,*/2` new is "At 09:00 AMMonday through Wednesday and every 2 days of the week".
- The "Not covered" counter-example is true. With `if (isSegmentRangeWithoutIncrement && (i > 0 || !doesExpressionContainIncrement))` applied, `1-3,*/2 9 * * *` prints ", 1 through 3 and every 2 minutes, between 09:00 AM and 09:59 AM", `0 1-3,*/2 * * *` prints "On the hour, , 01:00 AM through 03:00 AM and every 2 hours", and day-of-month, month and day-of-week get the comma. So declining C1 is fair and the reason is real.
- Reran `sweep/diff3.ts` (own copy, 4 minutes): `{ total: 849660, diff: 120364, viol: 0, f012: 0, enNewBad: 0 }`. The script builds 17 members, 1,445 lists, 7 fields, 42 locales (`src/i18n/locales` has 42 files), verbose on and off. All three numbers and "only in day-of-month, month, day-of-week and year, only when a later member has a step" are supported. The "some members are not meaningful in every field" caveat is true (e.g. `L` in year).
- `commaEveryDay()` is ", mỗi ngày" in `vi.ts:73` and ", kila siku" in `sw.ts:73`; `transformVerbosity` deletes it globally (c08a7d6 line 798). The mechanism sentence is correct.
- No em dashes, no banned adjectives, last line is the exact disclosure sentence.

## Round 1 findings
- Fix paragraph and `609-612` / `580-596`: fixed.
- "849,660 list combinations" and the sweeping claim: fixed in wording and now true. Declined to cut. Fair, but see cut 3: the maintainer cannot rerun it because the script is not in the PR.
- "The same output appears": fixed ("same fault", fields named, both valid).
- Documentation section: shortened, not cut. Still a section whose content is "none". Cut it (cut 2).
- Commit body: adopted, wrapped. Fixed.
- Duplicate comment in the new branch: declined in synthesis as optional. Fair.
- "Not covered" "shorten it": went the other way. 50 words became about 110 plus a code snippet. Not fixed (cut 1).
- Title line removed: fixed.

## Proportion
PR.md grew from 393 to 494 words. POLICY.md says recent outside PR bodies are "empty or a short cause paragraph". The bug-template fields, validity, cause and disclosure earn their place. These do not:

1. "Not covered". The parenthesis "(the stray ' , ' is gone, the missing ', ' after the time is not)" restates the output two lines above it. "obvious" and "Fixing the range case needs a different change" are opinion, and the last one was not run (R8). The 2-line version below keeps the one fact a maintainer will ask about (why not fix it too).
2. "Documentation relied on". A header over "No documentation gives wording". The test reference is already in Cause. Delete the section.
3. Sweep sentence. Keep one sentence, drop "(849,660 runs; some members are not meaningful in every field and I did not filter them)" and "Output changed in 120,364 runs". Those are noise a maintainer cannot check. If the operator wants the numbers, put the script in a comment, otherwise leave them out.
4. The `vi` paragraph is the only side effect a user could notice, so it stays, but it can lose the line reference (it moves to 801 after this patch) and one clause.
5. "Testing" header is two paragraphs of which the second is a locale aside. Merge under one short paragraph.

## Proposed PR.md body (about 300 words, every claim run above)

```
**Cron Expression**
`0 9 * * 5,0-4/2`

**Expected Output**
"At 09:00 AM, only on Friday and every 2 days of the week, Sunday through Thursday"

**Actual Output**
"At 09:00 AMonly on Friday and , every 2 days of the week, Sunday through Thursday"

The expression is valid. It is a standard 5-field expression whose day-of-week field is a comma list of the value `5` (Friday) and the range with step `0-4/2` (Sunday to Thursday). The same fault appears for `0 0 12 1,15-20/2 * ?` (day-of-month, Quartz-style 6 fields with `?`) and `0 9 * 1,3-9/2 *` (month, standard 5 fields). Both are valid.

**Cause**
In the multiple-values loop in `src/expressionDescriptor.ts`, the plain-value branch strips the leading ", " from every member, including the first, so the first member runs into the time. A later step member keeps its own leading ", " after the loop's " and ". Now only members after the first are stripped. The step-first case `0 9 * * 0-4/2,5,6` (`test/cronstrue.ts:753`) is unchanged.

**Not covered**
A range first with a later step, `0 9 * * 1-3,*/2`, still prints "At 09:00 AMMonday through Wednesday and every 2 days of the week". Adding the missing comma in that branch also changes minutes and hours (`1-3,*/2 9 * * *` would print ", 1 through 3 and every 2 minutes, ..."), so I left it.

**Testing**
Full suite: 406 passing (405 before, plus the new test). I compared old and new output for 1,445 lists of two or three members, placed in each of the 7 fields, in all 42 locales, verbose on and off. Output changed only in day-of-month, month, day-of-week and year, and only when a later member has a step.

In `vi` the step phrase begins with the same words as `commaEveryDay()` (", mỗi ngày"), and `transformVerbosity` deletes those words when verbose is off. The deletion needs the leading ", ", so the phrase now survives in a list: `0 0 9 * 5,*/2 * *` in `vi` went from "Vào 09:00chỉ trong Tháng 5 và  2 tháng" to "Vào 09:00, chỉ trong Tháng 5 và mỗi ngày 2 tháng". A standalone `*/2` month in `vi` still prints "2 tháng". I did not judge that wording.

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
```
Shorter still, if the operator wants it: drop the sweep sentence's list shape and write only "I compared old and new output for two- and three-member lists in every field and all 42 locales; it changed only in day-of-month, month, day-of-week and year, and only when a later member has a step." Same claims, no counts to defend.

## Not checked
- The live tracker, and whether a maintainer wants the range-first case in this PR.
- The 17 sample members as a representative set (the "only when" claim is for those members only; PR.md says "lists", which is accurate for the lists tried).
- Locales other than `vi` and `sw` by eye; wording of any locale.
- Prettier, Node 20/22/24, `npm ci` on a Mac.
- I did not read other round-2 reviewers' files.
