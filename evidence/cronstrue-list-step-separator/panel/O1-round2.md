# O1 round 2: SHIP (medium)

Copy: scratch/panel2-cronstrue-list-step-separator-O1 (clone of upstream-check at c08a7d6, `git am` of OUT/0001-*.patch applied cleanly, one commit b0cbdc2). Probe scripts and outputs are in `o1r2/` there. Nothing pushed or posted.

## C1 re-run by me (the decisive check)

I applied the one-condition change `(i > 0 || !doesExpressionContainIncrement)` on top of the patch. Suite: 406 passing. My own English probe, patch vs patch+C1, verbose on and off (verbatim):
- `0 9 * * 1-3,*/2`: `At 09:00 AMMonday through Wednesday and every 2 days of the week` becomes `At 09:00 AM, Monday through ...` (good).
- Same good change for `0 9 1-3,*/2 * *`, `0 9 * 1-3,*/2 *`, `0 0 9 * * * 2001-2003,*/2`, `0 9 * * 1-3,*/2,5`.
- Regressions, well formed before:
  - `1-3,*/2 9 * * *`: `1 through 3 and every 2 minutes, between ...` becomes `, 1 through 3 and every 2 minutes, ...`
  - `0 1-3,*/2 * * *`: `On the hour, 01:00 AM through ...` becomes `On the hour, , 01:00 AM through ...`
  - Also `0 0 1-3,*/2 * * * *`, `0 1-3,*/2 * * * * *` (leading ", " on output), `1-3,*/2,5 9 * * *`.
- Unchanged by C1: `1-3,5 9 * * *`, `0 1-3,5 * * *`, `0 9 * * 1-3,5`, `0 9 * * 5,1-3,*/2`.

So the fixer was right and my round-1 differential was wrong to call C1 safe: it covered only dom, month and dow. The side-effect rule drops C1 as written. I withdraw FIX-REQUIRED on C1. The PR.md "Not covered" quotes `1-3,*/2 9 * * *` and its before/after, and I reproduced both strings.

## Field-restricted variant (would I insist?)

I tried: `if (isSegmentRangeWithoutIncrement && (i > 0 || !doesExpressionContainIncrement || !getDescriptionFormat(expression).startsWith(", ")))`. It probes the field's format callback to tell dom/month/dow/year (leading ", ") from seconds/minutes/hours. Suite 406 passing; English probe fixes all range-first cases above and leaves minutes/hours identical.

Sweep (48,384 runs: 9 expression templates, 5 members, 2- and 3-member lists with a step, all 42 locales, verbose on and off, patch vs patch+variant): changed rows only in dom, month, dow, year templates (1,280 each), zero in seconds, minutes, hours. But it is not clean: zh_CN gains a double space (`在上午 09:00,  1 号至 3 号 ...`, old `在上午 09:00 1 号至 3 号 ...`). The condition is locale-dependent by construction, it looks at format strings, and it needs its own test and a second look at every locale.

I would NOT insist. It is a hack in a function that does not know its field; the proper fix is passing the field or leading-comma intent in, which is not a small change and CONTRIBUTING.md would want an issue first. Range-first is the same family but a distinct shape. A reasonable follow-up PR or issue, not a condition for this one.

## My round-1 findings

1. C1 (range-first): fairly declined with evidence (above); disclosed in PR.md.
2. Extra tests (month, three-member): not added. Synthesis cites S2 mutation runs that each changed condition already has a failing test; minimal-change rule. I accept, though a month case would be cheap. Not a blocker.
3. Commit body wrapping: fixed. I measured line lengths 71, 70, 67, 46; subject 59; author Andrew Stellman, no trailers.
4. PR length and the 849,660 sentence: replaced by the S3/S7 sentence. I checked it against `sweep/diff3.ts`: 17 members, 17x17x5 = 1,445 lists, 7 fields, 42 locales, 2 = 849,660. I did not rerun it. PR.md is still 28 lines, longer than recent outside PRs, mostly the "Not covered" and `vi` paragraphs. Acceptable because both are disclosures.
5. Template: `**Title:**` line gone, headings now `**Cron Expression**`, `**Expected Output**`, `**Actual Output**` as in `.github/ISSUE_TEMPLATE`. The Prerequisites checkbox is omitted, fine for a PR. Disclosure is the last line, exact. No em dashes.

## Re-check of PR claims (run by me, c08a7d6 vs patch)

- `0 9 * * 5,0-4/2`, `0 0 12 1,15-20/2 * ?`, `0 9 * 1,3-9/2 *`: old and new strings match PR.md and the commit message. `0 9 * * 0-4/2,5,6` unchanged. T2 fix is correct (examples described as the same fault, not same output).
- `vi`: `0 0 9 * 5,*/2 * *` old `Vào 09:00chỉ trong Tháng 5 và  2 tháng`, new `Vào 09:00, chỉ trong Tháng 5 và mỗi ngày 2 tháng`; standalone `*/2` month `Vào 09:00 2 tháng`. Source line 801 in the patched clone (798 at base) is the `commaEveryDay()` removal, so the mechanism sentence is right. Line number is in the PR; it will drift, minor.
- `Not covered` says the stray " , " is gone and the missing ", " remains: matches my output above. The phrase "needs a different change" is true of the one-liner but a different one-liner exists (variant above); wording is still honest.
- Prettier on `src/expressionDescriptor.ts`: passes. The test file warning is pre-existing (lint.log, not rerun).

## Side-effect rule on every behaviour change in the patch

- Changed: dom/month/dow/year lists with a later step member now get ", " after the time and no stray ", " before the step. Old text was visibly malformed; affected inputs rare; no well formed output changed in the sweeps I read or ran.
- Range-first lists with a later step: lose the stray " , " only (`and , every` becomes `and every`). Still glued to the time. Strictly less broken.
- vi/sw: step phrase now survives in a list. `vi` reads "mỗi ngày 2 tháng" (every day 2 months), an existing locale string that already appears in verbose standalone output; the old output was garbled. Disclosed and not judged in PR.md. Passes the rule, but expect a maintainer question.
- ja, ar: unchanged, still malformed (no ", " separator). Pre-existing.
- Minutes, hours, seconds: not touched by the patch (patch-only sweep in `sweep.log` reports f012 = 0).

## Mergeable as scoped, and the title

Yes. 2 files, +11/-1, source plus one case in `test/cronstrue.ts`, no CHANGELOG or dist, around 5 source lines, under the CONTRIBUTING.md non-trivial limit. Title "Fix separators in lists with a plain first value and a step" fits: the change fixes plain-first lists; the range-first remainder is in "Not covered". It also removes the stray " , " from range-first lists, which the title does not mention; harmless.

## Not checked

Full 849,660-run sweep rerun. My variant sweep used 5 members, not the fixer's 17. Locale wording. Year field only by two spot rows. Upstream closed issues and PRs (tracker unreachable); whether draft PR #387 conflicts textually. CI on Node 20/22/24. Seconds-field range-first lists beyond one probe. `npm ci && npm test` on a Mac.
