# Panel synthesis: chrono-ref-timezone-calendar (BUG-004)

Roster: full panel, fifteen Sonnet reviewers, all fifteen files present in `panel/`. No REJECT, no DROP.

| Item | A | B | O1 | O2 | O3 | O4 | O5 | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| chrono-ref-timezone-calendar | S | S | S | S | S | S | F | S | S | F | S | S | S | F | S |

S = SHIP, F = FIX-REQUIRED, R = REJECT, D = DROP. A = EXEC-A, B = EXEC-B.

Outcome: **REVISE**. The code change stands. Every required change is to the PR text or the commit message.

What the panel agrees on (from their own runs):
- The fix is six one-line swaps to `getDateWithAdjustedTimezone()`, the idiom `casualReferences.ts`, `ENEndOfPeriodRefiner.ts` and `ENWeekdayParser.ts` already use. No in-scope raw-instant calendar read is left (O1, O3, EXEC-B).
- The new test fails for the stated reason and each of the six edits is caught by its own case (EXEC-A, EXEC-B, S2, S3, S4, O5, S7: per-file reverts).
- Plain `Date` and no-timezone references give identical output before and after (EXEC-B, O3 with 360 rows per run, S5, O2).
- O3's independent oracle: 98 to 118 wrong rows of 648 on the old code, 0 on the fixed code, in four process zones.
- Side-effect rule: nobody found a DROP. Affected callers pass `{instant, timezone}` with a zone whose calendar differs from the process zone. They get the documented result, the one "today" and "next month" already give. Judged low likelihood and acceptable (EXEC-A, EXEC-B, O2, O3, O4, S5, S8, S3).
- Performance: about 0.4 to 0.8 microseconds per matched phrase (S6, micro-benchmark, end-to-end numbers noisy).
- Judgement-call rule: passes. The old code gives "this month" July, "next month" September and "today" August for one reference (O3, O4, EXEC-B).

## Findings that must change (text and commit message only)

1. **Suite claim has no log.** PR.md says the suite passes "at `TZ=America/New_York` and at `TZ=UTC`". `suite.log` is New York only. Raised by O4 (marked must change), O5, S5, S7. EXEC-A, O2 and S7 did run the suite at UTC and got 719 passed, so the claim is true but unlogged. Either add a UTC run to `suite.log`, or use: `The full suite passes (719 tests, run at TZ=America/New_York).`
2. **Five-zone red claim has no log.** "fails before the fix in any process timezone I tried (UTC, Asia/Tokyo, Pacific/Kiritimati, Pacific/Pago_Pago, America/New_York)": `red.log` and `revert.log` are New York only and show only the first row. Raised by S7 (must), S3, S1 (could not re-run). O4, O5, S5, S8 and S7 reproduced all five zones, so it is true. Either add the per-zone red runs to the packet, or use: `The new test builds its reference 3 hours ahead of whatever the process timezone is. It fails before the fix at TZ=America/New_York and passes after it.` (S7, S3.)
3. **Repro is not pasteable and the comments are not the printed values.** `ref` is undefined in the first line, and `.start.date()` prints `2012-07-01T03:00:00.000Z`, not `2012-07-01`. Raised by O1, O3, O5, S3, S7, S8. Use S7's block: `const ref = { instant: new Date("2012-07-31T22:00:00Z"), timezone: "JST" }`, `chrono.parse("this month", ref)[0].start.get("month")   // actual 7, expected 8`, `chrono.parse("Feb 15", { instant: new Date("2021-08-16T20:00:00Z"), timezone: "JST" })[0].start.get("year")   // actual 2021, expected 2022`.
4. **Title and commit subject end in "etc."** Raised by O5, S1, S3, S7. Use one subject for both: `fix: use the reference timezone's calendar for "this month" and year-less dates` (S7, O5 variant). S1 and S3 prefer a shorter one under 72 characters (`fix: use the reference timezone for "this month" and year-less dates`). Either is fine; pick one and keep title and subject identical.
5. **"Cause" and "Fix" paragraphs restate the diff and cite pre-fix line numbers.** Raised by O5, S3, S7, S1. Delete both and use: `These parsers read the reference instant directly, so they used the system calendar. "today" and "next month" already use getDateWithAdjustedTimezone(). With the repro above, "this month" gave July and "next month" gave September.` (S3, run by S3 and S7.)
6. **Commit body restates the diff.** Raised by O5, S1, S3. Replace with: `With a reference timezone that differs from the process timezone, "this week/month/year", "last night" and dates without a year ("Feb 15", "15 Feb", "2/15", "February") used the process calendar. "today" and "next month" already used the reference timezone's calendar.` (O5; no trailer). This means amending the commit message and regenerating the patch.
7. **Other-locales sentence is wrong and understates the change.** "I did not check the other locales, which have similar lines" contradicts itself (S3, S8), and `SlashDateFormatParser` is shared code registered by fi, de, ja, es, ru, vi, uk, fr, id, pt, sv and nl, so the `2/15` change reaches those locales (O1, not contradicted by anyone). Use O1's text: `The SlashDateFormatParser change is in shared code, so it also applies to every locale that registers it. I only added a test for English. Other locales have similar lines in their own parsers (for example FIMonthNameLittleEndianParser.ts, VIStandardParser.ts); I did not change them.`
8. **"this week" / "this year" sentence is misleading.** It follows a repro with a different instant; with the JST repro instant "this week" is Jul 29 before and after. Raised by O2, S5, S1, S3. Use O2's text: `"this week" and "this year" show the same fault at other instants. With the instants in the new test (process at TZ=UTC), "this week" gave Jul 29 instead of Aug 5 and "this year" gave 2012 instead of 2013.` (S3 would delete it; I keep it, the numbers were run by O5 and S7.)
9. **State the two behaviour changes the text leaves implicit.** S5: add after "Only references with a `timezone` that differs...": `For those references the result can move to the next or previous day, week, month or year when the two clocks are on different sides of a boundary. A server in UTC that passes a user's timezone is the usual case.` And replace "I did not change the 'last night' hour rule." with `I did not change the 'last night' hour rule. It now tests the hour on the reference clock, not the system clock.` (EXEC-B ran the 05:59 to 07:00 boundary and confirms it.) S3 and O1 wanted the hour-rule sentence removed or left alone; I follow S5 because the charter asks that each change be stated, and the sentence is true.
10. **Quote the docs once.** O5: keep `src/types.ts:60-61`, drop the duplicate `README.md:99` sentence. Optional.
11. **Year-less examples are near ties.** EXEC-A, O4: "Feb 15" differs only near the half-year point. Add: `The year-less examples only differ when the reference falls near the point halfway between the two candidate years, so they matter less than "this month".` Low priority, accurate.

## Findings not adopted

- **Move the five non-relative cases into their own test files (O5 finding 6; S1, S2, S4 flag it as a low-risk question).** The run rule says to put cases in the existing file for that parser, so this is a real deviation. Four reviewers called one shared test defensible because there is one cause, and moving five hunks across five files enlarges a six-line fix. This is a code revision that needs a re-review. I leave it to the operator: note it as likely pushback.
- **`test.each` instead of a loop, plain `toBe` assertions, a named constant for `180`, extra comments on the "this week" and "last night" rows, a comment on why a fixed "JST" instant would not work (O1, S1, S2, S3, O5, EXEC-A/B, O3, S4).** Style only; loops have precedent in the repo (`en_merging_relative_dates.test.ts:62`, `result.test.ts:187`). Not required, and any test edit forces a second panel round. The `[phrase, ...]` label already names the failing case.
- **A reference-behind-the-process-zone case in the test (S4, EXEC-B probed it by hand and it works).** Grows the diff for no new site coverage.
- **Move the `getDateWithAdjustedTimezone()` call in `ENCasualDateParser.ts:15` into the "last night" branch (S6, S1).** About 0.4 to 0.8 microseconds per match; extra diff. Both said leave it.
- **The `>6` against `<6` "last night" hour rule (O1, S3, S2).** A separate question; the patch does not touch it.
- **`ForwardDateRefiner.ts:23` mixing an adjusted date with a true instant (EXEC-B, S4, O3).** Pre-existing, identical on base and fixed, tied to open #553. Not part of this PR; a possible separate candidate.
- **Rename or restructure source lines (S1).** None proposed beyond the above.

## For the operator, not PR text

- PR #583 (relative dates and timezone) was merged and then reverted by 0d89cb6 (2025-03-10) with no reason in the git log; 4033a27 redid it for `casualReferences.ts` and `ForwardDateRefiner.ts` only. Reviewers who read 0d89cb6 (S3, O1, S4, O4) say it touched only `src/results.ts` and `test/en/en.test.ts`, not these six lines. The reason is unknown. A maintainer may ask why these six sites were left on the system calendar. Do not claim it was an oversight.
- Open PR #648 changes `ENMonthNameParser.ts` and `ENMonthNameLittleEndianParser.ts` and conflicts in `test/en/en_month.test.ts`; EXEC-A showed it conflicts the same way on plain e925ac7, and EXEC-B showed the source files auto-merge. #662, #663 and #665 edit `test/en/en_relative.test.ts` (append conflict at most).
- `bin/run-tests <dir> <file>` does not select a single file: the path is swallowed by `--testPathIgnorePatterns` and the whole suite runs minus that file (EXEC-A, O1, S2, S4, S8). Use `--testPathPattern=<file>`. A tooling note, not a patch problem. Several reviewers could not finish a full suite on the loaded machine; the 719 count rests on `suite.log` plus EXEC-A, O2, S7 and O3 runs.
- Not checked by anyone: other locales, the live tracker, `npm ci` on the operator's Mac, Pago_Pago red run by EXEC-A/EXEC-B.

## Round 2 (text-only revision, focused re-review)

Round 1 outcome was REVISE with text findings only, so no fixer sub-agent was needed. The previous round is kept in `rev0/` (patch, PR.md, logs). The diff body of the patch is byte-identical to round 1 (checked by me, EXEC-A, EXEC-B, O1); only the commit message changed. The fixed clone is still one commit by Andrew Stellman with no trailers, `git status --porcelain` empty.

What was changed for each round-1 finding:
1. Suite claim: ran the full suite at `TZ=UTC` (719 passed) and appended it to `suite.log`. The PR now says it passes at both zones, which the log shows.
2. Five-zone red claim: ran the new test with `src/` reverted at UTC, Tokyo, Kiritimati, Pago_Pago and New York and appended them to `red.log` (each `1 failed, 10 passed`, `- 8 / + 7`). The claim stays and is now logged. The PR also says "passes after it at `TZ=America/New_York` and `TZ=UTC`", which `green.log` and the two suite runs back.
3. Repro: replaced with the pasteable block (`ref`, `ref2`, `.get("month")`, `.get("year")`). Values re-run at `TZ=UTC` (`repro-round2.log`).
4. Title and subject: one string for both, `fix: use the reference timezone for "this month" and year-less dates` (68 characters), no "etc.".
5. Cause and Fix paragraphs: deleted. Replaced with three sentences, including "this month" July, "today" August and "next month" September, which I re-ran.
6. Commit body: replaced with the O5 text, no trailer.
7. Locale sentence: replaced with the O1 text. I checked that 13 locale files import the shared `SlashDateFormatParser` and that the two named files still read `context.refDate`.
8. "this week" / "this year": rewritten with their own instants and JST. I re-ran them (Jul 29 against Aug 5; 2012 against 2013). Not S3's deletion, I kept it.
9. Behaviour changes: added the boundary sentence and the "last night" reference-clock sentence. I ran the 05:59, 06:00 and 07:00 JST boundary (Aug 1, Aug 1, Jul 31 on the fixed code). Added the plain `Date` / `{instant}` claim, backed by the eight no-timezone rows in `repro-round2.log` (identical base and fixed).
10. Doc quote: `README.md:99` dropped, `src/types.ts:60-61` kept.
11. Near-tie sentence for year-less examples: added.

Not adopted, unchanged from round 1: moving the five non-relative cases to their own test files (still the likely maintainer pushback; O5 and EXEC reviewers accept one shared test in round 2), `test.each`, extra test comments, the `ENCasualDateParser.ts:15` allocation, the `ForwardDateRefiner.ts:23` pre-existing split.

Wording nits applied after the re-review (no new claims, each narrows or clarifies): "is the usual case" became "For example, a server in UTC that passes a user's timezone." (raised by EXEC-A, EXEC-B, O4, O5, S3, S5, S7); `import * as chrono from "chrono-node"` added to the repro (S7); "With the process at `TZ=UTC` and a JST reference..." in the this-week sentence (S7, O5); "every locale that registers it" became "the other locales that register it" (S3); a note in `red.log` and `suite.log` that the later blocks are excerpts (S7). These were not shown to the reviewers again. Not applied: merging the two "last night" sentences (S3, optional), explicit file:line cites for "today" and "next month" (S7, optional), the "last night can move two days" remark (S5, minor).

Re-review verdicts (round 2):

| Item | A | B | O1 | O4 | O5 | S3 | S5 | S7 |
|---|---|---|---|---|---|---|---|---|
| chrono-ref-timezone-calendar | S | S | S | S | S | S | S | S |

S = SHIP. Roles not re-run (they gave SHIP in round 1 and raised only optional items): O2, O3, S1, S2, S4, S6, S8. Confidence: EXEC-A, EXEC-B, O1, O4, O5, S5, S7 high; S3 medium.

EXEC checks on the amended commit: red fails at eight zones, green passes at five, revert fails (UTC, New York, London, Auckland, Kolkata, and each of the six source files alone), suite 719 passed at New York, UTC and Kolkata. `OUT/0001-*.patch` applies with `git am` to a clean clone of upstream `master` (e925ac7d) and gives tree `7e44c8925ab4224afed78e3c5cb9f9cf582db11d`, the tree at HEAD of the fixed clone. EXEC-B saw 8 failing suites at `TZ=Pacific/Lord_Howe` and the same 8 on base, so they are not from this patch.

Side-effect rule, again: no reviewer found a DROP. Affected callers pass `{instant, timezone}` with a zone whose calendar differs from the process zone; they now get the documented result, and the PR text states it.

Still true for the operator: PR #583 was reverted by 0d89cb6 for an unknown reason; open PR #648 touches two of the same files; `bin/run-tests <dir> <file>` does not select a file (use `--testPathPattern`); the live tracker and `npm ci` on the Mac were not checked.

Outcome after round 2: **SHIP**.
