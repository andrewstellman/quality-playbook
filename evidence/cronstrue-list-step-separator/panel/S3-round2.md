# S3 round 2: FIX-REQUIRED (medium)

Scope: slop only (proportion, claims, restating the diff, tone). Text-only trims, no code change. Every quoted string and number I checked is true. The PR text got longer, not shorter.

## What I ran (clone: scratch/panel2-cronstrue-list-step-separator-S3, HEAD c08a7d6, patch applied with `git am`; base copy panel2-...-S3-base; scratch panel2-S3-cond)
- `git am` clean. Author Andrew Stellman, no trailers. `run-tests`: `406 passing`.
- Commit body: no line over 72 characters (awk check). Subject unchanged. No em dashes in PR.md (grep 0). Disclosure line is last and exact.
- Old (base) vs new output for every expression in PR.md, English: `0 9 * * 5,0-4/2`, `0 0 12 1,15-20/2 * ?`, `0 9 * 1,3-9/2 *`, `0 9 * * 0-4/2,5,6` (unchanged), `0 9 * * 1-3,*/2`. All Actual and Expected strings match character for character.
- `vi` via cronstrue-i18n: `0 0 9 * 5,*/2 * *` old "Vào 09:00chỉ trong Tháng 5 và  2 tháng", new "Vào 09:00, chỉ trong Tháng 5 và mỗi ngày 2 tháng". Standalone `0 0 9 * */2 * *` is "Vào 09:00 2 tháng" in both. Matches PR.md.
- Mechanism: `vi.ts:73-74` `commaEveryDay()` is ", mỗi ngày"; `vi.ts:118-120` month step phrase is ", mỗi ngày %s tháng"; base `expressionDescriptor.ts:798` is the `commaEveryDay()` replace in `transformVerbosity`. The T3 mechanism is now correct.
- "Not covered" claim: I applied the one-condition change (`isSegmentRangeWithoutIncrement && (i > 0 || !doesExpressionContainIncrement)`) in a copy. `0 9 * * 1-3,*/2` becomes "At 09:00 AM, Monday through Wednesday and every 2 days of the week"; `1-3,*/2 9 * * *` becomes ", 1 through 3 and every 2 minutes, between 09:00 AM and 09:59 AM" (base has no leading comma). The quoted before/after is true. The suite still passes (406), so no existing test guards this. The "not adopted" decision for C1 stands.
- Sweep numbers: read `sweep/diff3.ts`. 17 members, 17x17 pairs + 17x17x4 triples = 1,445 lists; x7 fields x 42 locales (matches `ls src/i18n/locales`) x 2 = 849,660. `sweep.log` shows diff 120,364, viol 0, f012 0. All numbers in PR.md match.
- `prettier --check`: same single warning on `test/cronstrue.ts` as base (lint.log); source file passes.

## Round-1 findings (S3.md)
1. "Fix:" paragraph: removed. FIXED.
2. "Documentation relied on": text replaced as I proposed, but the heading stayed. See N2. PARTLY FIXED.
3. Sweep sentence (my T1): FIXED. "1,445 two- and three-member lists built from 17 sample members, placed in each of the 7 fields, in all 42 locales, verbose on and off (849,660 runs)" is correct. Nit: the third member of a triple comes from a 4-item set (`5`, `0-4/2`, `*/3`, `1-2`), two of which are not in the 17, so "built from 17 sample members" is slightly loose. Not worth a change.
4. Cause paragraph (T4 cuts): FIXED. Line ranges 609-612 and 580-596 are gone. One line number remains, see N3.
5. "Not covered": kept (fair), but it grew instead of shrinking. See N1.
6. vi/sw paragraph (T3): FIXED on mechanism and facts. Dropping `sw` is correct: the `sw` month phrase is "kila mwezi wa 2", which does not begin with ", kila siku", so the mechanism does not apply to it.
7. Title line (T5): FIXED, body starts at `**Cron Expression**`.
8. Commit body (T6): FIXED. Wrapped, shorter, no restating of the PR cause beyond one sentence. Old/new strings in it are true.

## New problems
- N1 (main). PR.md is 494 words; round 1 was 393. I asked for about half. The growth is the "Not covered" paragraph (about 110 words), which now narrates a rejected diff, quotes the condition `if (isSegmentRangeWithoutIncrement && (i > 0 || !doesExpressionContainIncrement))` and a minutes example. A maintainer does not need a patch that is not in the PR. Exact replacement:
  `**Not covered**`
  `A range as the first member with a later step, for example `0 9 * * 1-3,*/2`, still prints "At 09:00 AMMonday through Wednesday and every 2 days of the week". The stray " , " is gone; the missing ", " after the time is not. The obvious one-condition fix in the range branch also changes the minutes and hours output, so I left it out.`
  (Every clause is backed by my run above. About 60 words.)
- N2. "Documentation relied on" says no documentation was relied on, and repeats `test/cronstrue.ts:753`, already cited in Cause. Delete the whole section. Nothing is lost.
- N3. `src/expressionDescriptor.ts:798` is the one line number left. It is right at c08a7d6 (and 801 in the patched tree), but it drifts. Use "in `transformVerbosity()` in `src/expressionDescriptor.ts`" instead (exact name, same anchor value).
- N4. The vi paragraph and the sweep paragraph sit under the bold heading "Testing" with no label. The vi paragraph is a behaviour change, not a test. Either give it its own bold label (for example `**Side effect in vi**`) or leave it; the reader can follow it. Low importance.
- N5. The sweep paragraph's parenthesis "(some members are not meaningful in every field and I did not filter them)" is honest but is extra length. Optional cut. Also the script is not attached, so the maintainer cannot rerun it; the first person "I compared" is true and acceptable. If the operator wants zero doubt, add "script not attached".

With N1 to N3 applied PR.md is about 380 words, back under round 1 and about the size of the cut I wanted.

## Side-effect rule
Unchanged from round 1: only lists with a plain first member and a later step member change; old text was malformed; vi month text now reads "mỗi ngày 2 tháng" in such lists and is disclosed. No DROP.

## Not checked
Closed upstream issues and PRs (tracker unreachable; PR.md claims no search). The 849,660-run sweep itself (read the script and log, did not rerun). Locales other than en, vi, sw. A fresh `npm ci && npm test` on a Mac. Native-speaker wording.
