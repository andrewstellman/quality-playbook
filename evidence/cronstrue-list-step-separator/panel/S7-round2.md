# S7 round 2: SHIP (high)

Role: citations. I checked every factual claim in the new PR.md and the commit message against my own clone at c08a7d6 plus the patch (scratch/panel2-cronstrue-list-step-separator-S7, base copy ...-S7-base, throwaway ...-S7-c1, sweep dir ...-S7-sweep). The text is now true and traceable. Two optional wording nits at the end.

## Round 1 findings, status
- T1 (849,660 wording): fixed. See the figures below.
- T2 (false "same output"): fixed. PR now says "the same fault", with field and dialect named, and "Both are valid".
- T3 (vi/sw mechanism): fixed. PR names `src/expressionDescriptor.ts:798` and `commaEveryDay()`; the sw half was dropped, which is fine.
- T4 (Fix paragraph, line ranges, README quote): fixed. Cause is short; `test/cronstrue.ts:753` is cited; README quote removed.
- T5 (Title line): fixed. Body starts at `**Cron Expression**`.
- T6 (commit body): fixed. Longest body line is 71 characters. Author is Andrew Stellman, no trailers, no em dashes.
- My round-1 findings 4 (cite :753) and 5 (580-597) are resolved; the line-range text is gone.

## Claims run (all true)
- Expected and Actual for `0 9 * * 5,0-4/2`: base prints "At 09:00 AMonly on Friday and , every 2 days of the week, Sunday through Thursday"; fix prints "At 09:00 AM, only on Friday and every 2 days of the week, Sunday through Thursday". Both match PR.md exactly.
- `0 0 12 1,15-20/2 * ?` and `0 9 * 1,3-9/2 *` both show the fault at base and are fixed by the patch. Both are valid (Quartz 6-field with `?`; standard 5-field).
- `0 9 * * 0-4/2,5,6` is identical at base and fix. `test/cronstrue.ts:753` is the `it("0 9 * * 0-4/2,5,6"` line at c08a7d6 and in the patched tree.
- `src/expressionDescriptor.ts:798` at c08a7d6 is `description = description.replace(new RegExp(this.i18n.commaEveryDay(), "g"), "");`, inside `transformVerbosity` under `if (!useVerboseFormat)`. vi `commaEveryDay()` is ", mỗi ngày" (vi.ts:73-75) and `commaEveryX0Months()` is ", mỗi ngày %s tháng" (vi.ts:118-120). The mechanism is right: base keeps the step's ", " so the phrase is deleted ("và  2 tháng"); the fix strips it, so it survives.
- vi quotes run verbatim: `0 0 9 * 5,*/2 * *` base "Vào 09:00chỉ trong Tháng 5 và  2 tháng", fix "Vào 09:00, chỉ trong Tháng 5 và mỗi ngày 2 tháng". Standalone `0 0 9 * */2 * *` prints "Vào 09:00 2 tháng" at both.
- "Not covered": `0 9 * * 1-3,*/2` after the fix prints "At 09:00 AMMonday through Wednesday and every 2 days of the week". True. At base it was "...AMMonday through Wednesday and , every 2 days of the week", so the "stray ' , ' is gone" aside is true.
- One-condition change claim: I applied `if (isSegmentRangeWithoutIncrement && (i > 0 || !doesExpressionContainIncrement))` on top of the patch (throwaway copy). Suite 406 passing. Day-of-month, month, day-of-week fixed ("At 09:00 AM, 1 through 3 and every 2 days in a month", "..., January through March and every 2 months", "..., Monday through Wednesday and every 2 days of the week"). Minutes broken: `1-3,*/2 9 * * *` goes from "1 through 3 and every 2 minutes, between 09:00 AM and 09:59 AM" to ", 1 through 3 and every 2 minutes, between 09:00 AM and 09:59 AM", exactly as PR.md quotes. Hours also broken: `0 1-3,*/2 * * *` becomes "On the hour, , 01:00 AM through 03:00 AM and every 2 hours". The claim is true. Matches OUT/sweep/pr-claims.out and c1-attempt/fix.status.
- Suite: base 405 passing, patched 406 passing (run-tests, both clones).
- Sweep: I reran sweep/diff3.ts (src-old = base src, src-new = patched src, node_modules linked, 4m15s wall on a loaded host). Output: `{ total: 849660, diff: 120364, viol: 0, f012: 0, enNewBad: 0 }`. Same as sweep.log. By reading: 17 members, 17x17 = 289 pairs, each plus 4 third members = 289 x 5 = 1,445 lists; x 7 fields x 42 locales x 2 = 849,660. The locales array has 42 entries and `src/i18n/locales` has 42 files. `diff` 120,364 is the PR's figure. `viol: 0` means every changed run had a field index >= 3 (day-of-month, month, day-of-week, year in the 7-field form) and a later member containing "/", which is what "only when a later member has a step" says (necessary condition, not sufficient). `f012: 0` means no change in seconds, minutes, hours.
- PR sentence "some members are not meaningful in every field and I did not filter them" is true (members include `L`, `1W`, `5#2`, `2020` placed in all 7 fields).
- Last PR line is exactly the disclosure, ends with a newline. No em dashes or flag words (grep). No "Title" line. README has no sentence about list wording, so "No documentation gives wording for combined lists" has no counter-example.

## New problems (all minor, none blocks)
1. "built from 17 sample members" is slightly off. The third member of the 1,156 three-member lists comes from `5, 0-4/2, */3, 1-2`, and `*/3` and `1-2` are not among the 17. Suggested wording: "built from 17 sample members (plus 4 more for a third member)". Optional; the counts are right.
2. The vi example `0 0 9 * 5,*/2 * *` is a 7-field expression (seconds, year); PR.md does not say so or say it is valid, unlike the first three. It is valid (7-field with year). One clause would close this.
3. "Fixing the range case needs a different change" is an inference. I only showed that the one-condition change fails; I did not search for another. Acceptable as stated, since the paragraph says "the obvious" change.
4. The `:798` and `:753` citations are at c08a7d6; PR.md does not say so, and they will drift. Both are correct at the tip, so this is only a wording choice.

## Side-effect rule
Unchanged from round 1: affected users have a list with a plain or range-less member first and a later step member; old text was malformed; vi (and sw) users now see "mỗi ngày 2 tháng" where the old text had a double space. The PR discloses it. No DROP.

## Not checked
Closed or open upstream issues and PRs (tracker unreachable; PR.md makes no claim). Wording of any locale. `npm ci && npm test` on a fresh Mac checkout, other Node versions. sw output and the other 40 locales beyond what diff3.ts's own checks cover (viol/f012/enNewBad are structural checks; I did not read changed rows in other locales). Whether another one-condition fix of the range-first case exists.
