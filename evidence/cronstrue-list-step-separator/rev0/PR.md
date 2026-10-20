**Title:** Fix separators in lists with a plain first value and a step

**Cron Expression:** `0 9 * * 5,0-4/2`

**Expected Output:** `At 09:00 AM, only on Friday and every 2 days of the week, Sunday through Thursday`

**Actual Output:** `At 09:00 AMonly on Friday and , every 2 days of the week, Sunday through Thursday`

The expression is valid: it is a standard 5-field expression whose day-of-week field is a comma list of the value `5` (Friday) and the range-with-step `0-4/2` (Sunday to Thursday). The same output appears for `0 0 12 1,15-20/2 * ?` and `0 9 * 1,3-9/2 *`.

**Cause:** In `src/expressionDescriptor.ts` at c08a7d6, the plain-member branch of the multiple-values loop (lines 609-612) removes the leading ", " from every member, including the first, so the first member runs into the time. A later step member (lines 580-596) keeps its own leading ", " after the loop's " and ".

**Fix:** The leading ", " is now removed only from members after the first, in both branches. The step-first case `0 9 * * 0-4/2,5,6` (`test/cronstrue.ts`) is unchanged.

**Documentation relied on:** `README.md:17`, "- Supports all cron expression special characters including * / , - ? L W, #". The README gives no wording for combined lists, so the expected sentence follows the library's own output for a similar list with the step first (`0 9 * * 0-4/2,5,6`).

**Not covered:** A plain range as the first member with a later step, for example `0 9 * * 1-3,*/2`, still prints "AMMonday through Wednesday and every 2 days of the week" (the stray comma is gone, the missing ", " after the time is not). I left that case out to keep this change small.

Full suite: 406 passing (405 before, plus the new test). I compared old and new output over 849,660 list combinations in every locale, verbose on and off. Output changed only in day-of-month, month, day-of-week and year, and only when a later member has a step. In `vi` and `sw` the step text starts with its own comma phrase that was stripped with the comma before; it now stays (`0 0 9 * 5,*/2 * *` in `vi`: "...và  2 tháng" became "...và mỗi ngày 2 tháng"). I did not judge that wording.

Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.
