# BUG-004 (chrono-ref-timezone-calendar): The reference timezone is ignored by "this month/year/week", "last night" and year-less dates

Base: clone HEAD is e925ac7d9a2669ef2ee353275709d39ec445dab9, the same commit as the run. No `git log e925ac7d..HEAD` to read.

## Claim
With a reference `{instant, timezone}` whose calendar date differs from the process timezone's, "this month/week/year", "last night" and year-less dates ("Feb 15", "15 Feb", "2/15", "February") use the process calendar. Expected: the reference timezone's calendar, from src/types.ts:60-61 and README.md:99.

Verdict: CONFIRMED

## Repro source
/work/batch/runs/chrono/scratch/confirm-chrono-ref-timezone-calendar-confirmer/repro.test.ts (my own; jest file, 28 cases, each prints actual and expected, one `expect(bad).toEqual([])` at the end). Core loop:
`chrono.parse(c.text, { instant: new Date(c.instant), timezone: c.tz })[0]`, compare `{year, month, day}` with hand-written expected values.
Run: `TZ=<zone> ./node_modules/.bin/jest --rootDir . repro.test.ts`.
Case groups: A (JST, 2012-07-31T22:00Z = Aug 1 07:00 JST), B (2012-12-31T22:00Z), C (2012-08-04T22:00Z), D and F (year-less, 2021-08-16T20:00Z and 2021-08-02T20:00Z), E (tz "EST", reference behind a Tokyo process).

## Verbatim output (excerpt of `grep ok|FAIL`)
TZ=UTC, tz=JST:
- FAIL A1 this month  actual={"y":2012,"m":7,"d":1} expected={"y":2012,"m":8,"d":1}
- ok   A2 next month (control)  actual={"y":2012,"m":9}
- ok   A3 end of this month (control)  actual={"y":2012,"m":8,"d":31}
- ok   A4 today / A5 tomorrow / A6 yesterday (controls): Aug 1 / Aug 2 / Jul 31
- FAIL A7 last night (07:00 JST)  actual={"y":2012,"m":7,"d":30} expected={"y":2012,"m":7,"d":31}
- FAIL B1 this year  ref=2012-12-31T22:00:00Z  actual={"y":2012} expected={"y":2013}
- FAIL C1 this week  ref=2012-08-04T22:00:00Z  actual={"y":2012,"m":7,"d":29} expected={"y":2012,"m":8,"d":5}
- FAIL D1 Feb 15 (MiddleEndian) / D2 15 Feb (LittleEndian) / D3 2/15 (Slash)  actual y=2021 expected y=2022
- ok   D4 February, D5 Feb 1 (not discriminating: day 1 is far from the year boundary at that date)
- FAIL F1 February (MonthName) / F2 Feb 1 / F3 1 Feb / F4 2/1  ref=2021-08-02T20:00:00Z  actual y=2021 expected y=2022
- FAIL E1-E7 (tz EST, ref behind): e.g. E1 this month actual m=8 expected m=7
TZ=America/New_York, tz=JST: A1, A7, A8, B1, C1, D1-D3, F-group fail the same way; the tz=EST group E prints ok, because New York (EDT, -4) and EST (-5) have the same calendar date at those instants; this is not a same-zone case.
TZ=Asia/Tokyo, tz=JST (reference zone = process zone): every A-D and F case passes; E1-E7 fail (EST is behind the Tokyo process). The jest run exits 1 in Tokyo only because of the E group; I did not run the A-D and F groups as a separate file.
Result date check (ad hoc, file deleted): TZ=UTC ref 2012-07-31T22:00Z JST: "this month" date()=2012-07-01T03:00:00.000Z, "next month" date()=2012-08-31T22:00:00.000Z. TZ=Asia/Tokyo: "this month" date()=2012-08-01T03:00:00.000Z.
Which of the six misbehave: all six. ENMonthNameParser only shows it with a day-1 boundary reference (F1); D4 passes by chance.
With the run's fix patch applied (clone, then reverted): repro passed under UTC, America/New_York and Asia/Tokyo; the whole suite showed `Tests: 719 passed, 719 total` (718 plus my repro). The regression-test patch alone: TZ=UTC `5 failed, 5 total`; TZ=Asia/Tokyo `5 passed, 5 total`.

## Expectation check
- src/types.ts:60-61 (and reference_docs/cite/api_src_types.txt:70-71): "Reference timezone. The timezone where the input is written or mention." and "Date/time implication will account the difference between input timezone and the current system timezone." README.md:99 (cite/README.md:99): "The timezone where the input is written or mentioned."
- Test intent: test/en/en_relative.test.ts:~404-430 ("tomorrow at 5pm" with timezone JST/BST/-420 gives different days from one instant) and test/system_timezone.test.ts:55-69 pin the writer's calendar for "tomorrow".
- Internal inconsistency: same reference, "this month" gives July while "next month", "end of this month" (ENEndOfPeriodRefiner.ts:61, :87), "today", "tomorrow" (casualReferences.ts) use the August calendar. ParsingComponents constructor (results.ts:~73) also implies day/month/year from the adjusted date.
- Intentional? Not found. `git blame`: the six lines come from 2020 to 2025 refactors (991c9b77, 6fbb34ae, 2ad75585, 4a6dd347, be731a7d). Commit 4033a27 (2025-04-06, "Fix/New: Reference date calculation base-on timezone adjusted instant") moved casualReferences.ts to the adjusted date and left these parsers alone; its message gives no reason. No test passes `timezone` with these phrases; no changelog exists. I take it as an incomplete migration, not a decision. Not proven.
- Side effects: with no timezone (Date reference or timezone null) getDateWithAdjustedTimezone returns a plain copy, so results are unchanged. Users passing a timezone that differs from the process zone get different dates for these phrases, in the documented direction. Within-scope sites only; the same pattern exists in other locales (fr, it, de, ...), not checked for behaviour.
- Not checked: the "last night" hour rule (ENCasualDateParser uses `> 6`, casualReferences.lastNight uses `< 6`), a separate question.

## Duplicate search
Closest: none found. `known_open_bugs.md` lists #590 "Concerns & flaws with timezone parsing & handling" and #553 "Timezone parsing reference not working as expected with `forwardDate: true`" (titles only, bodies not readable here), and PR #630 (touches only src/calculation/mergingCalculation.ts, adds `imply("timezoneOffset", null)`). Of the six files, only #648 (year-before-month-name) changes ENMonthNameParser.ts and ENMonthNameLittleEndianParser.ts among PR heads that differ from master (also old merged heads 356, 359, 525); I did not diff whether #648 touches the findYearClosestToRef lines, but its subject is a different change. Merged PRs 583, 650, 654 are in master. pr/584 is a revert of 583's relative-date timezone change (subject only).
dup queries: "this month timezone reference"; "last night timezone"; "reference timezone year-less date"; "getDateWithAdjustedTimezone refDate"; "ParsingReference timezone this week"; "timezone instant wrong month"

Security angle: no - wrong date for ordinary input.

## Likely maintainer pushback
- "Few callers pass `timezone`." Reply: the docs and the "tomorrow" tests cover it; the six phrases disagree with "next month" under the same reference.
- "Fix the other locales too." The fix here is English plus the shared slash parser; other locales have the same lines (not tested).
- "Hour 05:00 and 'last night'." The fix keeps the existing hour rule, now on the reference clock.
- Fix is a six-line swap to `context.reference.getDateWithAdjustedTimezone()`; regression test must be run with a non-JST process zone to fail.

## Parent re-run
Command: `cd /work/batch/runs/chrono/scratch/confirm-chrono-ref-timezone-calendar-confirmer && TZ=UTC ./node_modules/.bin/jest --rootDir . repro.test.ts` (HEAD e925ac7d9a2669ef2ee353275709d39ec445dab9).
Exit code: 1 (bug present). Jest summary: `Tests: 1 failed, 1 total` (the file has one jest test that loops over 28 cases and asserts the failure list is empty).
Key lines (verbatim):
- FAIL A1 this month   ref=2012-07-31T22:00:00Z tz=JST text="this month" actual={"y":2012,"m":7,"d":1} expected={"y":2012,"m":8,"d":1}
- ok   A2 next month (control)   actual={"y":2012,"m":9} expected={"y":2012,"m":9}
- FAIL A7 last night (07:00 JST)   actual={"y":2012,"m":7,"d":30} expected={"y":2012,"m":7,"d":31}
- FAIL B1 this year   ref=2012-12-31T22:00:00Z tz=JST   actual={"y":2012} expected={"y":2013}
- FAIL D1 Feb 15   ref=2021-08-16T20:00:00Z tz=JST   actual={"y":2021,"m":2,"d":15} expected={"y":2022,"m":2,"d":15}
Parent notes:
- Case A8 ("last night" at 05:00 JST, expected Aug 2) looks wrong as an expectation: the hour rule is a separate question and the fixer should not use A8. A1, A7, B1, C1, D1-D3 are the cases that rest on the cited sentence.
- Parent check of the history lead: PR #583 (Feb 2025, "Fix: timezone option for relative dates should affect time") was merged, then reverted by 0d89cb63 (Mar 10 2025, "Revert ..."), then 4033a27 (Apr 2025) re-did the change for casualReferences.ts only. So the maintainer has wanted the writer's calendar in these paths; the six sites were not part of it. The reasons for the March revert are not in the git history I read.
- Not checked: other locales; the open-tracker state of #590 and #553 (titles only).
