# BUG-009 cronstrue-list-step-separator: list with a step member loses its separator and prints a stray comma

Claim: for a comma list in day-of-month, month, day-of-week or year whose FIRST member is a plain value and a LATER member has a step (e.g. `0 9 * * 5,0-4/2`), the output is "At 09:00 AMonly on Friday and , every 2 days ..." where the expected form has ", " after the time and no " , " after "and". Source of "expected": README:17 "Supports all cron expression special characters including * / , - ? L W, #" (general), plus the library's own step-first output for the same kind of list (test/cronstrue.ts:753) which is well formed. The README does not state a wording.

Verdict: CONFIRMED

## Repro
Source: /work/batch/runs/cronstrue/scratch/confirm-cronstrue-list-step-separator-confirmer/repro.ts (my own; imports ./src/cronstrue; exits 1 if the output matches AM|PM glued to "only/on/in" or contains " , "). Clone at c08a7d6 (3.30.0 tip). Output verbatim:
```
"0 9 * * 5,0-4/2" => At 09:00 AMonly on Friday and , every 2 days of the week, Sunday through Thursday   [BROKEN]
"0 0 12 1,15-20/2 * ?" => At 12:00 PMon day 1 of the month and , every 2 days in a month, between day 15 and 20 of the month   [BROKEN]
"0 9 * 1,3-9/2 *" => At 09:00 AMonly in January and , every 2 months, March through September   [BROKEN]
expected: ', ' before first list member, no ' , ' after 'and' (e.g. 'At 09:00 AM, only on Friday and every 2 days of the week, Sunday through Thursday')
control At 09:00 AM, every 2 days of the week, Sunday through Thursday, only on Friday, and only on Saturday
exit=1
```
Extra probes (probe.ts): `0 9 * * 1,3-5/2`, `0 9 * * MON,WED-FRI/2`, `0 0 9 * * * 2020,2022-2030/2` and `0 9 * * 5,*/2` all show the same glue and " , ". `0 9 1,15-20 * *` (no step) is fine.
Validity: all are lists of items, each a value or `range/step` or `*/step`; crontab(5) (Vixie) allows a step on a range and comma lists of such items. `5,0-4/2` and `1,3-9/2` are 5-field (DOW 0-4 is Sun-Thu, month 1-12). `1,15-20/2` is in the 6-field Quartz-style form with seconds and `?` in day-of-week (DOM and DOW not both set), as the library accepts. The year case is the 7-field-with-seconds form. I did not use the invalid `N,M/step` shape.

## Expectation check
- README.md:17 (also reference_docs/cite/README.md:17): "- Supports all cron expression special characters including * / , - ? L W, #". It is general, not a wording spec.
- `git log -S"Strip leading comma since we manage separators"` gives only 286434e (2026-02-09, #374, Fixes #194). Its message and test cover only `0 9 * * 0-4/2,5,6`. Blame of the lines involved (609-612 strip; 589-596 loop) points to 286434e and older (a9d85f5b, 51a20659).
- grep of tests for "AMonly", "PMon", " , ": no hits. No test, comment, README or CHANGELOG line makes the glued text intentional. Nearby tests (test/cronstrue.ts:739 `5-45/10,*/5,9 * * * *`, :753 step-first) only pin the minutes and step-first shapes, which are fine.
- Cause (read in src/expressionDescriptor.ts ~589-613): the strip of the leading ", " runs for the first member too (no `i > 0` check), and a later step member keeps its own leading ", " after the loop's " and ".
- Intent: #374 aimed to remove double commas; the glue and stray comma look like a side effect, not a decision.

## Upstream movement (8ff1002e..c08a7d6)
Two commits: c65e887 (#419, month step values with monthStartIndexZero; touches src/cronParser.ts and test/cronstrue.ts only) and c08a7d6 (version bump). Neither touches src/expressionDescriptor.ts. Bug reproduces at the tip (output above). The run's fix patch (quality/patches/BUG-009-fix.patch) applies cleanly at the tip: my repro exits 0 and the suite shows 405 passing (I reverted it afterwards; clone source is unmodified).

## Duplicate search
known_open_bugs.md (operator `gh` export, 2026-10-05): only #387 (W day offsets, draft PR) and #384 (same, issue). Neither is about this. In scratch/upstream-check, no unmerged PR head changes the multiple-value loop; the heads touching it are merged ones: pr/374 241a076 "fix: remove double commas in descriptions with increment ranges and multiple values" (the origin of the strip) and pr/370 64ba927 "Address code review feedback: null checks, Unicode support, and i18n test coverage". Closest match: #374 (introduced it, does not fix it). Closed issues and PRs were not searched (the forge is unreachable), so a closed report of this is possible.
dup queries:
- "AMonly"
- "stray comma list step"
- "comma-separated values with increments"
- "day of week list range step 5,0-4/2"
- "double comma increment multiple values"
- "missing comma after AM"

## Security
No (output formatting only).

## Likely maintainer pushback
- Wording of the combined sentence ("only on Friday and every 2 days of the week, Sunday through Thursday") is awkward even when fixed; the claim is only the missing ", " and the stray " , ".
- Mixed lists with steps are rare, and the library does not validate input.
- A plain range as FIRST member (`0 9 * * 1-3,*/2`) still glues "AMMonday" with the 2-hunk fix (run's BUG-018); a maintainer may want that fixed together. I did not run that case.
- A fix touching the separator logic may be wanted via an issue first (CONTRIBUTING); it is about 3 lines.

## Not checked
Non-English locales (the same code path, so likely the same), the verbose option, the BUG-018 case, prettier, the run's regression-test patch, closed tracker items, and whether the fixed wording reads well in every field.

## Parent re-run

`cd <clone> && ./node_modules/.bin/ts-node repro.ts` at c08a7d6, source unmodified:

```
"0 9 * * 5,0-4/2" => At 09:00 AMonly on Friday and , every 2 days of the week, Sunday through Thursday   [BROKEN]
"0 0 12 1,15-20/2 * ?" => At 12:00 PMon day 1 of the month and , every 2 days in a month, between day 15 and 20 of the month   [BROKEN]
"0 9 * 1,3-9/2 *" => At 09:00 AMonly in January and , every 2 months, March through September   [BROKEN]
expected: ', ' before first list member, no ' , ' after 'and' (e.g. 'At 09:00 AM, only on Friday and every 2 days of the week, Sunday through Thursday')
control At 09:00 AM, every 2 days of the week, Sunday through Thursday, only on Friday, and only on Saturday
exit=1
```
