# O4 round 2: SHIP (medium)

Role: not-a-bug advocate. Copy: /work/batch/runs/cronstrue/scratch/panel2-cronstrue-list-step-separator-O4 (clone of upstream-check, HEAD c08a7d6, `git am` of OUT/0001-*.patch applied clean). A second copy with my round-1 condition is in `...-O4-var`. Nothing under OUT was edited except this file.

## 1. My round-1 FIX-REQUIRED finding (range-first, one condition): withdrawn

I applied `if (isSegmentRangeWithoutIncrement && (i > 0 || !doesExpressionContainIncrement))` on top of the patch (`-O4-var`). `run-tests` still gives `406 passing` (no test covers the regression). Output, old patch -> variant, non-verbose:
```
0 9 * * 1-3,*/2     At 09:00 AMMonday through Wednesday and every 2 days of the week
                 -> At 09:00 AM, Monday through Wednesday and every 2 days of the week   (fixed)
0 9 1-3,*/2 * *     ...AM1 through 3 and every 2 days in a month -> AM, 1 through 3 ...  (fixed)
0 9 * 1-3,*/2 *     ...AMJanuary through March... -> AM, January through March ...       (fixed)
0 0 9 * * * 2020-2022,*/2 -> At 09:00 AM, 2020 through 2022 and every 2 years            (fixed)
1-3,*/2 9 * * *     1 through 3 and every 2 minutes, between 09:00 AM and 09:59 AM
                 -> , 1 through 3 and every 2 minutes, between 09:00 AM and 09:59 AM    (REGRESSION)
0 1-3,*/2 * * *     On the hour, 01:00 AM through 03:00 AM and every 2 hours
                 -> On the hour, , 01:00 AM through 03:00 AM and every 2 hours          (REGRESSION)
1-3,*/2 * * * * *   1 through 3 and every 2 seconds -> , 1 through 3 and every 2 seconds   (REGRESSION)
```
The fixer was right and I was wrong: the first member's leading ", " is wanted in dom/month/dow/year (the time comes before it) and unwanted in seconds/minutes/hours (nothing comes before it). A range-first fix needs to know the field, so it is not one condition. `1-3,*/2 9 * * *` is a valid 5-field expression and its old output was well formed, so under the side-effect rule my variant would have to be dropped. Round-1 finding 1 is declined fairly, and my round-1 check indeed never ran minutes/hours.

## 2. Not-a-bug arguments retried against the revision

- Intended or documented: no. `README:17` says nothing on list wording; no test pins "AMonly" or " , ". The only list-with-step test is `0 9 * * 0-4/2,5,6` (unchanged, still passes, output identical at both commits in my run).
- Declined before: I diffed every `refs/remotes/pr/*` head for the multiple-values loop (`Multiple Values`, `isSegmentRangeWithoutIncrement`, `Strip leading comma`). Only pr/370 and pr/374 touch it, both the merged #374 work. Closed issues and PRs: not searched (tracker unreachable).
- Better fixed elsewhere: the only alternative is making the loop emit no leading ", " and have the caller add it per field. That is a restructure of a shared function, bigger than the 30-line guide, and not a reason to refuse the small fix. Not placed better elsewhere for a minimal change.
- Partial fix leaves range-first broken, so the maintainer should decline: no. The patch does not make range-first worse. It removes the stray " , " there (`0 9 * * 1-3,*/2` old "AMMonday through Wednesday and , every 2 days", now "...and every 2 days", my run and `sweep/pr-claims.out`). It fixes one well-defined shape with a test, and the title says "plain first value". A maintainer who wants range-first can ask; the PR already tells them where it stands.
- Invalid input: no. `5,0-4/2`, `1,15-20/2` and `1,3-9/2` are valid lists.

## 3. Round-1 findings, status

- T1 (849,660 sentence): fixed. PR.md now says 1,445 lists, 17 members, 7 fields, 42 locales, verbose on/off, 849,660 runs. `sweep.log` shows `total: 849660, diff: 120364, viol: 0, f012: 0, enNewBad: 0` and `sweep/diff3.ts` matches the description (17 members, 17x17 pairs plus 4 thirds = 1,445, 42 locales, 7 fields). The script itself is not in the PR and I did not rerun the whole sweep.
- T2 (false "same output"): fixed, now "same fault", both expressions called valid. I ran both: dom "At 12:00 PM, on day 1 of the month and every 2 days in a month, ..." and month "At 09:00 AM, only in January and every 2 months, ...".
- T3 (vi/sw mechanism): fixed, now names `commaEveryDay()` and `expressionDescriptor.ts:798`. Quoted vi old/new strings match `sweep/pr-claims.out`. "vi `*/2` month still prints '2 tháng'" matches its output. I did not run `sw` myself.
- T4, T5: fixed (no Fix paragraph, no title line, body starts at Cron Expression).
- T6: commit body wrapped, max line 72, no trailers, author Andrew Stellman, subject unchanged. My `git log` shows exactly that.
- My round-1 findings 2 (849,660) and 3 (vi wording): addressed as above. Finding 4 (issue first): still agree trivial (+11/-1, 2 files, no locale file).

## 4. "Not covered" paragraph, claim by claim

- `0 9 * * 1-3,*/2` "still prints ... AMMonday through Wednesday and every 2 days of the week": true, I ran it.
- "the stray ' , ' is gone, the missing ', ' after the time is not": true.
- The one-condition change "fixes it for day-of-month, month and day-of-week": true (I also saw year). "breaks minutes and hours": true, quoted before/after strings match my run exactly (`1-3,*/2 9 * * *`). It also breaks seconds, which the text does not say; incomplete but not false.
- "Fixing the range case needs a different change": an inference, not run. Consistent with my results (the fix must be field-aware). Acceptable. Optional softening: "needs a field-aware change".
- Operator note: the paragraph quotes a code line the maintainer may try. That is fine and honest.

## 5. New problems

None found. Suite `406 passing` in my copy. Source and test hunks are byte-identical to round 1. Prettier: not rerun by me; `lint.log` shows the same test/cronstrue.ts warning on unmodified HEAD.

Side-effect rule: affected users have a list with a plain first member and a later step member in dom/month/dow/year; the old text was visibly garbled ("AMonly", " , "), so nobody sensibly depends on it. In my 12-expression run nothing well formed changed (`0 9 * * 0-4/2,5,6`, `5,*/2 9 * * *`, `0 5,*/2 * * *` and the minutes/hours cases are identical to base). Not a DROP.

## Not checked

Closed upstream issues and PRs; a fresh `npm ci` on a Mac; Node versions; locale wording; the full 849,660-run sweep (I ran only the cases above in English); `sw`; verbose output beyond the cases shown; possible textual conflict with draft PR #387.
