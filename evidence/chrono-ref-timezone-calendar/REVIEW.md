# chrono: "this month", "last night" and year-less dates ignore the reference timezone

Status: **ready for the operator's review.**

## The project

[chrono](https://github.com/wanasit/chrono) (npm `chrono-node`) finds dates and times written in ordinary language inside free text ("next Friday at 3pm", "5 days ago", "2026-10-05") and returns where each one sits in the text, the matched text and the resolved date. The caller can pass a reference: the moment "now" for the text, and optionally the timezone the text was written in.

## The bug

The reference can carry a timezone. `src/types.ts:60-61` says: "Reference timezone. The timezone where the input is written or mention." and "Date/time implication will account the difference between input timezone and the current system timezone." (`README.md:99` says the same in other words.)

What happens: six parsers (five in the English locale, one shared by many locales) read the reference instant directly. They use the calendar of the machine's timezone, not of the reference timezone. "today", "tomorrow" and "next month" already use the reference timezone. So with one reference, "today" can say August, "next month" September and "this month" July.

Example, process at `TZ=UTC`, reference `2012-07-31T22:00:00Z` with timezone JST (it is Aug 1, 07:00 in Tokyo). From `knock_on.base.txt` (base) and `knock_on.fixed.txt` (fix):

- "this month": 2012-7-1 before, 2012-8-1 after.
- "today": 2012-8-1 both. "next month": 2012-9-1 both.

It went unnoticed because no test passes a `timezone` together with these phrases, and the results only differ when the two clocks are on different sides of a day, week, month or year boundary.

## The fix

Six one-line changes: where the code read the raw reference instant, it now calls `context.reference.getDateWithAdjustedTimezone()`, the call that `casualReferences.ts`, `ENEndOfPeriodRefiner.ts` and `ENWeekdayParser.ts` already use. With no timezone on the reference, that method returns a plain copy of the instant, so those callers see no change.

```diff
diff --git a/src/common/parsers/SlashDateFormatParser.ts b/src/common/parsers/SlashDateFormatParser.ts
index 5ea81a4..7c00396 100644
--- a/src/common/parsers/SlashDateFormatParser.ts
+++ b/src/common/parsers/SlashDateFormatParser.ts
@@ -94,7 +94,7 @@ export default class SlashDateFormatParser implements Parser {
             const year = findMostLikelyADYear(rawYearNumber);
             result.start.assign("year", year);
         } else {
-            const year = findYearClosestToRef(context.refDate, day, month);
+            const year = findYearClosestToRef(context.reference.getDateWithAdjustedTimezone(), day, month);
             result.start.imply("year", year);
         }
 
diff --git a/src/locales/en/parsers/ENCasualDateParser.ts b/src/locales/en/parsers/ENCasualDateParser.ts
index 5b22903..40b28d5 100644
--- a/src/locales/en/parsers/ENCasualDateParser.ts
+++ b/src/locales/en/parsers/ENCasualDateParser.ts
@@ -12,7 +12,7 @@ export default class ENCasualDateParser extends AbstractParserWithWordBoundaryCh
     }
 
     innerExtract(context: ParsingContext, match: RegExpMatchArray): ParsingComponents | ParsingResult {
-        let targetDate = context.refDate;
+        let targetDate = context.reference.getDateWithAdjustedTimezone();
         const lowerText = match[0].toLowerCase();
         let component = context.createParsingComponents();
 
diff --git a/src/locales/en/parsers/ENMonthNameLittleEndianParser.ts b/src/locales/en/parsers/ENMonthNameLittleEndianParser.ts
index 259d557..6e3963b 100644
--- a/src/locales/en/parsers/ENMonthNameLittleEndianParser.ts
+++ b/src/locales/en/parsers/ENMonthNameLittleEndianParser.ts
@@ -53,7 +53,7 @@ export default class ENMonthNameLittleEndianParser extends AbstractParserWithWor
             const yearNumber = parseYear(match[YEAR_GROUP]);
             result.start.assign("year", yearNumber);
         } else {
-            const year = findYearClosestToRef(context.refDate, day, month);
+            const year = findYearClosestToRef(context.reference.getDateWithAdjustedTimezone(), day, month);
             result.start.imply("year", year);
         }
 
diff --git a/src/locales/en/parsers/ENMonthNameMiddleEndianParser.ts b/src/locales/en/parsers/ENMonthNameMiddleEndianParser.ts
index c0dd966..e8b3bc2 100644
--- a/src/locales/en/parsers/ENMonthNameMiddleEndianParser.ts
+++ b/src/locales/en/parsers/ENMonthNameMiddleEndianParser.ts
@@ -75,7 +75,7 @@ export default class ENMonthNameMiddleEndianParser extends AbstractParserWithWor
             const year = parseYear(match[YEAR_GROUP]);
             components.assign("year", year);
         } else {
-            const year = findYearClosestToRef(context.refDate, day, month);
+            const year = findYearClosestToRef(context.reference.getDateWithAdjustedTimezone(), day, month);
             components.imply("year", year);
         }
         if (!match[DATE_TO_GROUP]) {
diff --git a/src/locales/en/parsers/ENMonthNameParser.ts b/src/locales/en/parsers/ENMonthNameParser.ts
index cd6e89b..6eaf9c2 100644
--- a/src/locales/en/parsers/ENMonthNameParser.ts
+++ b/src/locales/en/parsers/ENMonthNameParser.ts
@@ -54,7 +54,7 @@ export default class ENMonthNameParser extends AbstractParserWithWordBoundaryChe
             const year = parseYear(match[YEAR_GROUP]);
             result.start.assign("year", year);
         } else {
-            const year = findYearClosestToRef(context.refDate, 1, month);
+            const year = findYearClosestToRef(context.reference.getDateWithAdjustedTimezone(), 1, month);
             result.start.imply("year", year);
         }
 
diff --git a/src/locales/en/parsers/ENRelativeDateFormatParser.ts b/src/locales/en/parsers/ENRelativeDateFormatParser.ts
index b015fa8..90b040d 100644
--- a/src/locales/en/parsers/ENRelativeDateFormatParser.ts
+++ b/src/locales/en/parsers/ENRelativeDateFormatParser.ts
@@ -35,7 +35,7 @@ export default class ENRelativeDateFormatParser extends AbstractParserWithWordBo
         }
 
         const components = context.createParsingComponents();
-        let date = new Date(context.reference.instant.getTime());
+        let date = context.reference.getDateWithAdjustedTimezone();
 
         // This week
         if (unitWord.match(/week/i)) {
diff --git a/test/en/en_relative.test.ts b/test/en/en_relative.test.ts
index a8e736e..c89580b 100644
--- a/test/en/en_relative.test.ts
+++ b/test/en/en_relative.test.ts
@@ -36,6 +36,31 @@ test("Test - 'This' expressions", () => {
     });
 });
 
+test("Test - 'This' and year-less expressions use the calendar of the reference timezone", () => {
+    // The reference timezone is 3 hours ahead of the system timezone, whatever the system timezone is.
+    // The system clock reads `local`, and the clock in the reference timezone reads 3 hours later.
+    const cases = [
+        { phrase: "this month", local: new Date(2012, 7 - 1, 31, 22), expected: [2012, 8, 1] },
+        { phrase: "this year", local: new Date(2012, 12 - 1, 31, 22), expected: [2013, 1, 1] },
+        { phrase: "this week", local: new Date(2012, 8 - 1, 4, 22), expected: [2012, 8, 5] },
+        { phrase: "last night", local: new Date(2012, 8 - 1, 1, 4), expected: [2012, 7, 31] },
+        { phrase: "Feb 15", local: new Date(2021, 8 - 1, 16, 22), expected: [2022, 2, 15] },
+        { phrase: "15 Feb", local: new Date(2021, 8 - 1, 16, 22), expected: [2022, 2, 15] },
+        { phrase: "2/15", local: new Date(2021, 8 - 1, 16, 22), expected: [2022, 2, 15] },
+        { phrase: "February", local: new Date(2021, 8 - 1, 2, 22), expected: [2022, 2, 1] },
+    ];
+
+    for (const { phrase, local, expected } of cases) {
+        const reference = { instant: local, timezone: -local.getTimezoneOffset() + 180 };
+        testSingleCase(chrono, "Deadline is " + phrase, reference, (result) => {
+            expect(result.index).toBe(12);
+            expect(result.text).toBe(phrase);
+            const { start } = result;
+            expect([phrase, start.get("year"), start.get("month"), start.get("day")]).toEqual([phrase, ...expected]);
+        });
+    }
+});
+
 test("Test - End of current month", () => {
     testSingleCase(chrono, "end of the month", new Date(2012, 7, 10), (result, text) => {
         expect(result.text).toBe(text);
```

## Regression test

One test in `test/en/en_relative.test.ts` with eight cases. Each builds a reference whose timezone is 3 hours ahead of whatever the process timezone is, so it fails or passes the same way on any machine.

- Red (`red.log`, `TZ=America/New_York`, source reverted, test kept):
  ```
  Tests:       1 failed, 10 passed, 11 total
      - Expected  - 1
      + Received  + 1
        "this month",
        2012,
    -   8,
    +   7,
  ```
  `red.log` also has the same failure at `TZ=UTC`, `Asia/Tokyo`, `Pacific/Kiritimati` and `Pacific/Pago_Pago`.
- Green (`green.log`, `TZ=America/New_York`): `Tests:       11 passed, 11 total` for `test/en/en_relative.test.ts`.
- Suite (`suite.log`): `Tests:       719 passed, 719 total` at `TZ=America/New_York` and at `TZ=UTC`.
- Revert (`revert.log`, `TZ=America/New_York`, source back to base, test kept): `Tests:       1 failed, 10 passed, 11 total`, same `- 8 / + 7` row.
- Lint (`lint.log`): `lint exit 0`.
- Logs: `red.log`, `green.log`, `revert.log`, `suite.log`, `lint.log`.

## Knock-on effects (run 2026-10-07)

**Callers of the changed code.** The six parsers are registered here:
- `src/locales/en/configuration.ts:39` `ENCasualDateParser`; `:42` `ENMonthNameParser`; `:43` `ENRelativeDateFormatParser`; `:60` `SlashDateFormatParser`; `:62` `ENMonthNameLittleEndianParser`; `:63` `ENMonthNameMiddleEndianParser`.
- `SlashDateFormatParser` is shared code. It is also registered in 12 other locales: `fi/index.ts:46`, `de/index.ts:46`, `es/index.ts:53`, `ru/index.ts:77`, `vi/index.ts:55`, `uk/index.ts:65`, `fr/index.ts:57`, `id/index.ts:64`, `it/configuration.ts:54`, `pt/index.ts:52`, `sv/index.ts:38`, `nl/index.ts:62`. Those locales get the "2/15" change; I did not test them.
- The changed lines call `getDateWithAdjustedTimezone()` (`src/results.ts:33`) and, for the year-less cases, `findYearClosestToRef` (`src/calculation/years.ts:21`). Neither was edited.

**Before/after, freshly run.** Script `knock_on.test.ts` (run by `knock_on.sh`) parses 14 phrases against 12 references, at process `TZ=UTC`, `Asia/Tokyo` and `America/New_York`: 504 rows. Base is `HEAD~1` (upstream `e925ac7`), fixed is `HEAD`, each in its own scratch clone. Outputs: `knock_on.base.txt`, `knock_on.fixed.txt`; the per-reference counts are in `knock_on.summary.txt`. No row threw an exception (`grep -c EXCEPTION` gave 0 for both files).

Process `TZ=UTC`, reference with timezone JST (start date as year-month-day):

| Reference (instant, tz) | Phrase | Base | Fixed |
|---|---|---|---|
| 2012-07-31T22:00Z, JST | this month | 2012-7-1 | 2012-8-1 |
| 2012-07-31T22:00Z, JST | last night | 2012-7-30 | 2012-7-31 |
| 2012-07-31T22:00Z, JST | today / next month | 2012-8-1 / 2012-9-1 | same |
| 2012-12-31T22:00Z, JST | this year | 2012-1-1 | 2013-1-1 |
| 2012-12-31T22:00Z, JST | this month | 2012-12-1 | 2013-1-1 |
| 2012-08-04T22:00Z, JST | this week | 2012-7-29 | 2012-8-5 |
| 2021-08-16T20:00Z, JST | Feb 15, 15 Feb, 2/15 | 2021-2-15 | 2022-2-15 |
| 2021-08-16T20:00Z, JST | last night | 2021-8-15 | 2021-8-17 |
| 2012-08-01T03:00Z, EST (behind the process) | this month | 2012-8-1 | 2012-7-1 |
| 2012-07-31T20:59Z, JST (05:59 in Tokyo) | last night | 2012-7-30 | 2012-8-1 |
| 2012-08-01T12:00Z, JST (same date in both) | all 14 phrases | unchanged | unchanged |

Unchanged in every row of the 504: "Feb 15, 2013" (explicit year), "February" (this probe's references are not near a year boundary for it; the regression test covers it), "end of this month", "next month", "today", "tomorrow at 5pm".

Rows changed, per reference (`knock_on.summary.txt`): 0 of 14 for `Date`, `{instant}` and `{instant, timezone: null}` in all three process zones. 0 of 14 for every JST reference when the process is `Asia/Tokyo`. At `TZ=UTC` each JST reference whose Tokyo date differs from its UTC date changes in 2 to 4 rows of 14 (the mid-day one changes in 0) (this month, this week, this year, last night, the three year-less forms, and "Deadline is this month", where the phrase sits at index 12 and keeps `index=12`). With a process at `Asia/Tokyo` and an EST reference, 3 rows change.

**Behaviour changes for existing users, judged under the side-effect rule.**
1. A caller that passes `{instant, timezone}` with a zone whose calendar date differs from the process zone gets a different day, week, month or year for "this week/month/year", "last night" and year-less dates. It is the result `src/types.ts` documents and the one "today" and "next month" already give. Judged acceptable. Affected: servers that pass a user's timezone. Likelihood: low to moderate. The risk is a caller who worked around the old behaviour by shifting the instant themselves; I have no evidence that anyone does and did not search for it.
2. "last night" tests the hour on the reference clock, not the system clock (unchanged rule, new clock). With JST 05:59 the fixed result is Aug 1, the same as the base gives when the process itself is in Tokyo (checked in `knock_on.*.txt`, `Asia/Tokyo` block). Judged acceptable, and stated in the PR text.
3. `2/15` in the other 12 locales that register `SlashDateFormatParser` changes the same way. Stated in the PR text. Not tested outside English.
4. A reference behind the process zone changes too (EST reference, Tokyo process: this month 2012-8-1 becomes 2012-7-1). Same rule as item 1.
5. Plain `Date` references and `{instant}` or `timezone: null` references: no change in any probe (0 of 14 phrases, in each of the three process zones, for each of those three reference kinds: 126 rows).

No behaviour change was found that I would call bad for existing users. Nothing here is a DROP.

## Review history

- Confirmed: `CONFIRMATION.md` (verdict CONFIRMED, `confirm.verdict`).
- Panel: `SYNTHESIS.md`. Roster: full, fifteen Sonnet reviewers (files in `panel/`). Round 1: REVISE, text changes only. Round 2: eight reviewers re-read the revision (EXEC-A, EXEC-B, O1, O4, O5, S3, S5, S7), all SHIP. `panel.outcome`: SHIP.
- Re-review: round 2 as above. Text fixes applied: the repro block, title and commit subject, commit body, the other-locales sentence, the "this week / this year" sentence, the two behaviour-change sentences, the suite and five-zone claims now backed by logs, the near-tie sentence. Details: `SYNTHESIS.md`, "Round 2". The round-1 files are in `rev0/`.
- Upstream check (2026-10-07): `master` at `e925ac7d9a2669ef2ee353275709d39ec445dab9` (2026-10-04, "Merge pull request #667 from Reggino/master"), the same commit the run used. Patch applies cleanly with `git am`: **yes**. Suite on that tip with the patch, `TZ=UTC` (`upstream-tip-suite.log`): `Tests:       719 passed, 719 total`.
- Pull-request heads that touch the patch's files (`pr-heads-touching.txt`): see "Things to know".

## Things to know before submitting

- **Issue tracker.** Not searched live (no network access to GitHub from here). `reference_docs/known_open_bugs.md` is the operator's `gh` export of 2026-10-05T23:05:04Z, listing 116 open issues and 14 open pull requests. Nothing in it matches this bug by title. Two timezone issues are listed, titles only, bodies not read: #590 "Concerns & flaws with timezone parsing & handling" and #553 "Timezone parsing reference not working as expected with `forwardDate: true` specified". Anything opened or closed after that export is unknown. The generated duplicate search (`dup-search.sh`) has not been run; the draft-PR script runs the tracker search and asks before continuing.
- **Pull-request heads touching the same files** (from the read-only clone, `pr-heads-touching.txt`). Whether each is open is known only for those in the 2026-10-05 export.
  - #648 (open per the export; ENMonthNameParser.ts, ENMonthNameLittleEndianParser.ts, test/en/en_month.test.ts). I merged it into upstream `master` in a scratch clone, with and without this patch: both times `git merge` stops with conflicts in `ENMonthNameLittleEndianParser.ts` and `test/en/en_month.test.ts`. So #648 already conflicts with `master` by itself, and this patch adds no new conflicting file. #648 does not edit the `findYearClosestToRef` lines this patch changes.
  - #662, #663, #665 (open per the export) edit `test/en/en_relative.test.ts`, the file this patch adds a test to. At most an append conflict; I did not try the merges.
  - #356, #359, #525: old heads (2020 to 2023) touching `SlashDateFormatParser.ts`, `ENMonthNameParser.ts`, `ENCasualDateParser.ts`. Not in the export's open list.
  - Newer than the export: `pr/668` (2026-10-07, "fix: roll an overnight time range into the next month") and `pr/666` (2026-09-28, Japanese language support) exist; neither touches these files. `pr/667` is already in `master`.
- **Panel.** Fifteen Sonnet reviewers. Findings raised and not adopted:
  - Move the five non-relative cases (month-name, slash) into their own test files. The run rule says to put cases in the existing file for each parser, so this is a real deviation. Four reviewers called one shared test defensible (one cause). **Likely maintainer pushback.**
  - `test.each` instead of a loop, plain `toBe` assertions, a named constant for `180`, more comments in the test (style).
  - A reference-behind-the-process case in the test (no new site coverage).
  - Moving the `getDateWithAdjustedTimezone()` call in `ENCasualDateParser.ts:15` into the "last night" branch (about 0.4 to 0.8 microseconds per match).
  - The `> 6` against `< 6` "last night" hour rule (`ENCasualDateParser` against `casualReferences`): a separate question, not touched.
  - `ForwardDateRefiner.ts:23` mixes an adjusted date with a true instant: pre-existing, same on base and fixed, tied to the open #553, not part of this PR. A possible separate candidate.
- **History a maintainer may raise.** PR #583 (relative dates and timezone) was merged, reverted by `0d89cb6` (2025-03-10), and redone for `casualReferences.ts` by `4033a27` (2025-04-06). The reason for the revert is not in the git history that was read. Do not say the six sites were an oversight; the PR text does not.
- **Policy (`../POLICY.md`).** AI policy is silent; `AGENTS.md` is written for agents. No CLA, no DCO, no issue-first rule, no PR template, no changelog. Nothing for the operator to sign or tick. The disclosure line is the default. The commit is authored by Andrew Stellman with no trailers. The operator decides whether to submit AI-assisted work to a project whose policy says nothing about it.
- **Not checked:** other locales' behaviour; the live tracker; any rule stated only in the GitHub web UI. The Mac command (`npm ci --ignore-scripts && npx jest --silent`) was run on a fresh copy of the patched clone in this sandbox, not on the operator's Mac. Result (`localcheck.log`, `TZ` as in this sandbox): `Tests:       719 passed, 719 total`, exit 0.

## Checks by the orchestrating session (Opus, 2026-10-07, after the Sonnet workflow finished)

Everything above this section was written by the Sonnet-only workflow. These are my own runs, finished at 21:34 UTC.

- Upstream `master` refetched: still `e925ac7d` (2026-10-04, merge of #667), the commit the run was made on; 230 pull-request heads, newest #668. The patch applies with `git am` to a fresh clone checked out at exactly that commit. Commit author `Andrew Stellman <andrew@stellman.com>`, no trailers, 7 files, 31 insertions, 6 deletions.
- Suite on the patched tip: `719 passed, 719 total`. With only the six source files reverted: `1 failed, 718 passed`, the new test, at its first case ("this month" gives month 7 where 8 is expected).
- My own differential test, with a different oracle from the workflow's. The oracle: when a reference timezone is given, the parsed date must not depend on the timezone of the machine running the code, and it must equal what a machine sitting in the reference timezone answers with no timezone given.
  - 18 phrases (the eight the patch targets, and ten controls such as "today", "tomorrow", "next month", "5 days ago", "Friday", "at 3pm", "Aug 5 2012"), 304 reference instants three hours apart around week, month, year and half-year boundaries, six reference offsets plus no timezone, run under five process timezones (UTC, Asia/Tokyo, Etc/GMT+5, Pacific/Kiritimati, America/New_York). 38,304 parses per run, ten runs.
  - Before the fix: 2,400 of 32,832 cases with a reference timezone give a result that depends on the process timezone. All 2,400 are in the eight target phrases. "last night" depends on it in every one of its 1,824 cases; "this week" in 216, "this month" in 144, "February" in 72, and "this year", "Feb 15", "15 Feb" and "2/15" in 36 each.
  - After the fix: 0 of 32,832.
  - Against the answer of a machine in the reference timezone: 4,148 mismatches before the fix, 0 of 87,552 comparisons after it.
  - What the fix changed, per process timezone: between 1,228 and 1,514 results, all in the eight phrases. No result changed for a reference without a timezone, none changed when the reference offset equals the process offset, and none of the ten control phrases changed.
- One thing the PR text understates: "last night" is the phrase most affected, not "this month". With any reference timezone that differs from the process timezone, the old code picked the day from the process clock, so the day was wrong for a large share of the day (988 of 1,824 cases at `TZ=UTC` in my test), not only near a boundary. The PR text mentions "last night" only in its list and in the hour-rule sentence. It is accurate as written; a maintainer would probably find the "last night" numbers the more persuasive example.
- History, read from git: #583 ("Fix: timezone option for relative dates should affect time", an outside contributor) was merged and reverted on 2025-03-10. On 2025-04-06 the maintainer made his own change, 4033a27 "Fix/New: Reference date calculation base-on timezone adjusted instant", which introduced the adjusted-instant approach in `casualReferences.ts` and `ForwardDateRefiner.ts`. This patch applies that same approach to six parsers that still read the raw instant. So it follows the maintainer's own direction, and it is also an area where he has reverted an outside change before.
- Open issue #590 "Concerns & flaws with timezone parsing & handling": I read the page with my fetch tool, which has misread GitHub pages before, so treat this as probable. It is a design discussion that proposes, among other things, not applying timezone logic to relative expressions at all. That is the opposite direction from this patch and from 4033a27. It is not a duplicate, but a maintainer may connect the two; worth reading before you submit. #553 is about `forwardDate` with an "every 8 weeks" phrase across a daylight-saving change, a different problem.
- Size: this is six one-line source changes in six files, more files than the other kits in this batch. Each line is the same substitution.

## Re-check by the orchestrating session (Opus, 2026-10-10, before submission)

- Upstream `master` moved to `cb0eb6f` (2026-10-10, merge of #668), with #656 (Arabic locale), #657 and #658 (Spanish) and #668 (overnight time range rolls into the next month, in `AbstractTimeExpressionParser.ts`) merged since `e925ac7`. None of the six files this patch changes was touched. `src/types.ts:60-61` still holds the two quoted sentences.
- The patch applies with `git am` to a fresh clone at `cb0eb6f`. Suite: `754 passed, 754 total`. With only the six source files reverted: `1 failed, 753 passed`, the new test.
- The PR's timezone claims, rerun at `cb0eb6f`: the new test file fails before the fix at `TZ=UTC`, `Asia/Tokyo`, `Pacific/Kiritimati`, `Pacific/Pago_Pago` and `America/New_York` (1 failed, 10 passed each), and passes after it at `America/New_York` and `UTC`; the full suite passes (754) at both.
- The PR's repro values, rerun at `TZ=UTC`: "this month" 7 before, 8 after; "today" 8 and "next month" 9 both times; "Feb 15" 2021 before, 2022 after; "this week" Jul 29 before, Aug 5 after; "this year" 2012 before, 2013 after; a plain `Date` reference gives the same result both times.
- My differential test, rerun at `cb0eb6f` in the same five process timezones: the output, before and after the fix, is byte-for-byte identical to the 2026-10-07 run (38,304 parses per timezone). Changed results per timezone: 1,228 to 1,514, all in the eight target phrases.
- Open pull requests: #648 still conflicts with `master` by itself in `ENMonthNameLittleEndianParser.ts` and `test/en/en_month.test.ts`, as before; this patch adds no new conflicting file. #663 (open, "keep the local time for relative dates across a DST change", changes `ReferenceWithTimezone` use in refiners and `src/results.ts`) and #665 merge with the patched tip with no conflict. #669 (open) touches only a French parser.
- PR text updated: the full-suite count is now 754 (was 719). Nothing else in the text depends on the base commit.

## The PR as it will be submitted

> **Title:** fix: use the reference timezone for "this month" and year-less dates
>
> With a reference timezone that differs from the process timezone, "this week/month/year", "last night" and dates without a year ("Feb 15", "15 Feb", "2/15", "February") use the process timezone's calendar. "today" and "next month" already use the reference timezone's.
>
> ```ts
> // process at TZ=UTC
> const ref = { instant: new Date("2012-07-31T22:00:00Z"), timezone: "JST" }  // Aug 1, 07:00 in Tokyo
> chrono.parse("this month", ref)[0].start.get("month")  // 7, expected 8
> ```
>
> These parsers read the reference instant directly. The change makes them call `context.reference.getDateWithAdjustedTimezone()`, as `ENWeekdayParser` and `ENEndOfCurrentMonthParser` already do.
>
> Only references with a `timezone` that differs from the process timezone get different results. A plain `Date` reference behaves as before. `SlashDateFormatParser` is shared, so other locales that use it are affected too. I added a test for English only.
>
> The new test in `test/en/en_relative.test.ts` fails before the change and passes after it. The full suite passes (754 tests).
>
> Found by Quality Playbook, an AI code-review tool, with Claude; I reviewed the change.

Shortened on 2026-10-10 at Andrew's request, after the draft was opened with the longer text (445 words). What was cut, all still true and recorded above: the "this week" and "this year" examples, the "last night" hour-rule note, the per-timezone test list, the `src/types.ts:60-61` quote, and the Finnish and Vietnamese parser examples.

## To submit

    bash submit-draft-pr.sh

The workflow script writes that file after this step; it runs the tracker search, asks before continuing, and opens a DRAFT pull request.

## Submission record

- 2026-10-10, about 23:20 UTC: draft pull request https://github.com/wanasit/chrono/pull/670 opened by Andrew with `submit-draft-pr.sh`, with the longer PR text. Only the final `gh pr view` output was pasted; the script stops on a failing local check, so the check either passed or was skipped (not known from here).
- Duplicate search (`../dup-search.out`): 12 searches, 0 hits, 0 failed.
- Checked after opening (git, sandbox): PR head `609d9f4368f49660811ba1ec5a522856fefac8b0`, author Andrew Stellman <andrew@stellman.com>, one commit on `master` `cb0eb6f` (still the tip), tree `6a45f7d327c0a0fd10fe0ae338d3aab8c3f58095`, identical to the reviewed patch; no trailers.
- PR description shortened to the text above (160 words) and applied by Andrew with `gh pr edit`. Checked on the PR page (23:27 UTC): the description is the short text.
- 2026-10-10 23:26 UTC: Andrew marked it ready for review (shown on the PR page). No reviews or comments at 23:27 UTC.
