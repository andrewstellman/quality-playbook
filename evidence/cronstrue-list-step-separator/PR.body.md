**Cron Expression**
`0 9 * * 5,0-4/2`

**Expected Output**
"At 09:00 AM, only on Friday and every 2 days of the week, Sunday through Thursday"

**Actual Output**
"At 09:00 AMonly on Friday and , every 2 days of the week, Sunday through Thursday"

The expression is valid. It is a standard 5-field expression whose day-of-week field is a comma list of the value `5` (Friday) and the range with step `0-4/2` (Sunday to Thursday). The same fault appears for `0 0 12 1,15-20/2 * ?` (day-of-month, Quartz-style 6 fields with `?`) and `0 9 * 1,3-9/2 *` (month, standard 5 fields). Both are valid.

**Cause**
In the multiple-values loop in `src/expressionDescriptor.ts`, the plain-value branch strips the leading ", " from every member, including the first, so the first member runs into the time. A later step member keeps its own leading ", " after the loop's " and ". Now only members after the first are stripped. The step-first case `0 9 * * 0-4/2,5,6` (`test/cronstrue.ts:767`) is unchanged.

**Not covered**
A range first with a later step, `0 9 * * 1-3,*/2`, still prints "At 09:00 AMMonday through Wednesday and every 2 days of the week". Adding the comma in the range branch also changes well-formed minutes and hours output (`1-3,*/2 9 * * *` would print ", 1 through 3 and every 2 minutes, ..."), so I left it.

**Testing**
Full suite: 409 passing (408 before, plus the new test). I compared old and new output for 1,445 two- and three-member lists in each of the 7 fields, in all 42 locales, verbose on and off. Output changed only in day-of-month, month, day-of-week and year, and only when a later member has a step.

In `vi` the step phrase begins with the same words as `commaEveryDay()` (", mỗi ngày"), and `transformVerbosity()` in `src/expressionDescriptor.ts` deletes those words when verbose is off. The deletion needs the leading ", ", so the phrase now survives in a list. `0 0 9 * 5,*/2 * *` (valid, 7 fields with seconds and year) in `vi` went from "Vào 09:00chỉ trong Tháng 5 và  2 tháng" to "Vào 09:00, chỉ trong Tháng 5 và mỗi ngày 2 tháng". A standalone `*/2` month in `vi` still prints "2 tháng". I did not judge that wording.

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
