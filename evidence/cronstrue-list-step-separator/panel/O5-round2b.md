# O5 round 2b (trimmed PR.md): FIX-REQUIRED (low)

Scope: slop only. One small edit left, in "Not covered". Everything else is true and proportionate.

## What I ran
Fresh clones in `scratch/panel2-cronstrue-list-step-separator-O5b/` (`o` = c08a7d6, `c` = same plus `git am` of the patch, clean).
- Patched output for the three headline expressions, `0 9 * * 0-4/2,5,6` (unchanged) and `0 9 * * 1-3,*/2` ("At 09:00 AMMonday through Wednesday and every 2 days of the week"): all match PR.md. Old output matches the Actual line.
- Not covered, minutes example: with `(i > 0 || !doesExpressionContainIncrement)` added to the range branch, `1-3,*/2 9 * * *` prints ", 1 through 3 and every 2 minutes, between 09:00 AM and 09:59 AM" (unchanged today). Also `0 1-3,*/2 * * *` gets "On the hour, , 01:00 AM ...". True.
- `vi`: `0 0 9 * 5,*/2 * *` old "Vào 09:00chỉ trong Tháng 5 và  2 tháng" (two spaces), new "Vào 09:00, chỉ trong Tháng 5 và mỗi ngày 2 tháng"; standalone `*/2` month "Vào 09:00 2 tháng". Matches byte for byte. `vi.ts:73` is `commaEveryDay()` (", mỗi ngày"); `transformVerbosity()` removes it globally when verbose is off. The expression has 7 fields with seconds and year, valid.
- Sweep sentence: `sweep/diff3.ts` has 17 members, 17x17 pairs plus 4 third members each = 289 + 1,156 = 1,445 lists; 7 fields; 42 locales; verbose on and off. `sweep.log` shows viol 0, f012 0 (nothing changed in seconds, minutes, hours; all changes in day-of-month and later with a later step member). The sentence without counts is supported.
- `test/cronstrue.ts:753` is the `0 9 * * 0-4/2,5,6` case in the patched tree (the new test is added after it). Suite counts are from the earlier round (405 before, 406 after); not rerun.
- No em dashes or en dashes. Last line exact (checked with od, ends `I reviewed the change.\n`).

## Finding
1. "Not covered" is not the short S3 version. It still has two things I asked to cut in round 2:
   - "The obvious one-condition fix": "obvious" is an opinion word of the banned kind, and "one-condition fix" was only tested in the form above. Say "Adding the comma in the range branch".
   - "The stray " , " is gone; the missing ", " after the time is not." restates the output two lines above it.
   Suggested text (about 45 words, claims all run above):
   "A range first with a later step, `0 9 * * 1-3,*/2`, still prints "At 09:00 AMMonday through Wednesday and every 2 days of the week". Adding the comma in the range branch also changes minutes and hours (`1-3,*/2 9 * * *` would print ", 1 through 3 and every 2 minutes, ..."), so I left it."

## Proportion
PR.md is 417 words (draft 494, my round 2 target about 300). After the edit above it is about 390. Documentation section gone, sweep counts gone, line numbers replaced. The `vi` paragraph is the one user-visible side effect and earns its place. Acceptable for the content.

## Not checked
Prettier, Node versions, `npm ci`; the live tracker; any locale wording; full suite count this round.

## Lead's note
Finding 1 applied as suggested (wording kept "well-formed" because the minutes/hours output it changes was well formed; nothing else changed). Not re-run by O5 after this edit; the sentence is O5's own text plus "well-formed".
