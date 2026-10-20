# S3 round 2b (trimmed PR.md): SHIP (high)

Scope: slop only. Fresh clone of upstream-check (c08a7d6) in scratch/panel2-cronstrue-list-step-separator-S3b/c, patch applied with `git am`.

## Re-run for changed or risky sentences
- `git am` clean; author Andrew Stellman, no trailers; commit body no line over 72 chars. `run-tests`: `406 passing` (405 + the new test).
- vi sentence: `0 0 9 * 5,*/2 * *` with `cronstrue-i18n` locale vi prints "Vào 09:00, chỉ trong Tháng 5 và mỗi ngày 2 tháng" (new). Old string "Vào 09:00chỉ trong Tháng 5 và  2 tháng" is in sweep/pr-claims.out (base run). `0 0 9 * */2 * *` prints "Vào 09:00 2 tháng". The expression has 7 fields (sec, min, hr, dom, month, dow, year), is valid, and seconds and year are present: "(valid, 7 fields with seconds and year)" is true.
- Not covered: `0 9 * * 1-3,*/2` still prints "At 09:00 AMMonday through Wednesday and every 2 days of the week". With the one-condition change in a copy: "At 09:00 AM, Monday through Wednesday ..." and `1-3,*/2 9 * * *` gives ", 1 through 3 and every 2 minutes, ...". Hours case also changes (`0 1-3,*/2 * * *` gives "On the hour, , 01:00 AM ..."), so "minutes and hours output" is true; the hours form is not shown, only minutes, which is fine.
- `test/cronstrue.ts:753` is the title line of `0 9 * * 0-4/2,5,6`; that test passes unchanged. Cause paragraph matches the code at `src/expressionDescriptor.ts` 593-615 (step/range branch not stripped before, plain branch stripped for every i).
- `transformVerbosity()` name and the vi `commaEveryDay()` mechanism: confirmed in round 2, unchanged.

## Sweep sentence vs sweep/diff3.ts
- Members 17; lists = 17x17 pairs + 17x17x4 triples = 1,445. Fields loop 0..6 (7). Locales array has 42 entries. verbose false/true. Log: `{ total: 849660, diff: 120364, viol: 0, f012: 0 }`.
- "changed only in day-of-month, month, day-of-week and year": f012 = 0 counts changes in fields 0-2 (seconds, minutes, hours), so changes are confined to fields 3-6. True.
- "only when a later member has a step": viol 0 where pred2 = field >= 3 and some later member contains "/". True (a necessary condition, which is all the sentence claims). The sentence no longer states counts, so no stale number. Script is not attached and the text does not say it is.

## Style
- Em dash count in PR.md: 0. No banned adjective ("obvious" is plain, not a praise word). No restating of the diff beyond the one Cause paragraph. Last line exact: `Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.`
- Length 417 words (round 2: 494; my target about 380). The excess over target is the Not covered paragraph (about 75 words vs my 60) which keeps the minutes example. Acceptable; every clause checked above.
- Round-2 items: N1 applied (shorter, condition quote gone), N2 section deleted, N3 name used, N5 caveat and counts dropped. N4 (label for vi paragraph) left as is; optional.

## Not checked
Tracker search (unreachable), sweep rerun (read script and log only), locales other than en and vi, Mac `npm ci`, native-speaker wording.
