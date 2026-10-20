**Cron Expression**
`0 9 * * 5,0-4/2`

**Expected Output**
"At 09:00 AM, only on Friday and every 2 days of the week, Sunday through Thursday"

**Actual Output**
"At 09:00 AMonly on Friday and , every 2 days of the week, Sunday through Thursday"

The expression is valid. It is a standard 5-field expression whose day-of-week field is a comma list of the value `5` (Friday) and the range with step `0-4/2` (Sunday to Thursday). The same fault appears for `0 0 12 1,15-20/2 * ?` (day-of-month, Quartz-style 6 fields with `?`) and `0 9 * 1,3-9/2 *` (month, standard 5 fields). Both are valid.

**Cause**
In the multiple-values loop in `src/expressionDescriptor.ts`, the plain-value branch strips the leading ", " from every member, including the first, so the first member runs into the time. A later step member keeps its own leading ", " after the loop's " and ". Now only members after the first are stripped. The step-first case `0 9 * * 0-4/2,5,6` (`test/cronstrue.ts:753`) is unchanged.

**Documentation relied on**
No documentation gives wording for combined lists. The expected text follows the existing test for `0 9 * * 0-4/2,5,6` (`test/cronstrue.ts:753`).

**Not covered**
A range as the first member with a later step, for example `0 9 * * 1-3,*/2`, still prints "At 09:00 AMMonday through Wednesday and every 2 days of the week" (the stray " , " is gone, the missing ", " after the time is not). I left it out because the obvious one-condition change in the range branch, `if (isSegmentRangeWithoutIncrement && (i > 0 || !doesExpressionContainIncrement))`, fixes it for day-of-month, month and day-of-week but breaks minutes and hours: `1-3,*/2 9 * * *` goes from "1 through 3 and every 2 minutes, between 09:00 AM and 09:59 AM" to ", 1 through 3 and every 2 minutes, ...". Fixing the range case needs a different change.

**Testing**
Full suite: 406 passing (405 before, plus the new test).

I compared old and new output for 1,445 two- and three-member lists built from 17 sample members, placed in each of the 7 fields, in all 42 locales, verbose on and off (849,660 runs; some members are not meaningful in every field and I did not filter them). Output changed in 120,364 runs. It changed only in day-of-month, month, day-of-week and year, and only when a later member has a step.

In `vi` the step phrase begins with the same words as `commaEveryDay()` (", mỗi ngày"), and `src/expressionDescriptor.ts:798` deletes those words when verbose is off. The deletion needs the leading ", ", so the phrase now survives in a list: `0 0 9 * 5,*/2 * *` in `vi` went from "Vào 09:00chỉ trong Tháng 5 và  2 tháng" to "Vào 09:00, chỉ trong Tháng 5 và mỗi ngày 2 tháng". A standalone `*/2` month in `vi` still prints "2 tháng". I did not judge that wording.

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
