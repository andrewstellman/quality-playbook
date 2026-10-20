# EXEC-A round 2: SHIP (high)

Fresh clone `scratch/panel2-cronstrue-list-step-separator-EXEC-A` at c08a7d6 (HEAD checked). Helper clones for old, C1 and `git am` are in `...-EXEC-A-aux/`. The fixed clone was only read.

## Steps 1-4 (red, green, revert, suite)
- Red: `git apply --include='test/*'` of `0001-*.patch`, then `run-tests ... test/cronstrue.ts -g "5,0-4/2"`: 0 passing, 1 failing. Assertion: actual `At 09:00 AMonly on Friday and , every 2 days of the week, Sunday through Thursday`, expected `At 09:00 AM, only on Friday and every 2 days of the week, Sunday through Thursday`. This is the claimed reason (glued "AMonly" and the stray " , ").
- Green: applied the `src/*` hunks: 1 passing.
- Revert: reversed only the source diff: 1 failing with the same message.
- Touched file `test/cronstrue.ts`: 184 passing. Full suite: 406 passing.
- Source and test hunks are byte-identical to round 1 (diffed `rev0/*.patch` against the new patch: only the From hash, date and commit message differ).

## Step 5 (repro and every quoted string)
Ran old (c08a7d6), fixed, and a C1 copy with `isSegmentRangeWithoutIncrement && (i > 0 || !doesExpressionContainIncrement)`.
- Expected/Actual for `0 9 * * 5,0-4/2`: old and new match PR.md character for character.
- `0 0 12 1,15-20/2 * ?` and `0 9 * 1,3-9/2 *`: old is glued and has " , ", new is fixed. Matches T2 wording ("same fault", not "same output").
- `0 9 * * 0-4/2,5,6`: unchanged, as the Cause paragraph says.
- vi: `0 0 9 * 5,*/2 * *` old `Vào 09:00chỉ trong Tháng 5 và  2 tháng`, new `Vào 09:00, chỉ trong Tháng 5 và mỗi ngày 2 tháng`; `0 0 9 * */2 * *` stays `Vào 09:00 2 tháng`. Both match. `vi.ts:73` commaEveryDay is ", mỗi ngày"; `vi.ts:118-120` commaEveryX0Months is ", mỗi ngày %s tháng". `expressionDescriptor.ts:798` at c08a7d6 is the `commaEveryDay()` removal (801 in the fixed tree). Mechanism is right.
- Not covered, `0 9 * * 1-3,*/2`: new prints `At 09:00 AMMonday through Wednesday and every 2 days of the week`. Matches.
- C1 claim, checked myself: with the C1 condition `1-3,*/2 9 * * *` goes from `1 through 3 and every 2 minutes, between 09:00 AM and 09:59 AM` to `, 1 through 3 and every 2 minutes, ...`. Also `0 1-3,*/2 * * *` goes from `On the hour, 01:00 AM through 03:00 AM and every 2 hours` to `On the hour, , 01:00 AM ...`. Dom/month/dow gain the missing ", " (`At 09:00 AM, Monday through Wednesday and every 2 days of the week`). The claim is true, and the old minutes/hours text was well formed.
- Sweep: reran `sweep/diff3.ts` with my own src-old/src-new copies (3m37s): `{ total: 849660, diff: 120364, viol: 0, f012: 0, enNewBad: 0 }`. This matches PR.md (849,660 runs, 120,364 changed, only dom/month/dow/year, only with a later step member). 17 members give 17x17x5 = 1,445 lists; 1,445 x 7 x 42 x 2 = 849,660; the locale list has 42 entries.
- My own check: for en/de/fr/es, verbose on and off, 12,112 changed rows; 0 had an old output that passed a malformation filter (" , ", ", ,", glued AM/PM, double space, leading ",", trailing ", "). So no well-formed output changed in those locales.

## Step 6 (patch applies)
- `git am` on a clean clone at c08a7d6: ok. Tree `dd64a3b5...` equals `fix-cronstrue-list-step-separator` `HEAD^{tree}`. The fixed commit is 6428d6a, which matches the patch From line.
- Author and committer in the fixed clone are Andrew Stellman <andrew@stellman.com>. No Signed-off-by, Co-Authored-By or Assisted-by in the message. Body lines are all <= 72 chars (awk check). `git status --porcelain` in the fixed clone: empty.
- Prettier: `test/cronstrue.ts` warns at base too (pre-existing, recorded in `lint.log`); `src/expressionDescriptor.ts` passes.

## Step 7 (round-1 findings in scope)
- T1 fixed: the 849,660 sentence is now accurate, defined, and sourced to a run I reproduced. The sweep script is still not in the PR (fine, the sentence no longer implies a rerunnable artifact).
- T2 fixed. T3 fixed and verified, `sw` claim removed. T4 fixed: no Fix paragraph, README quote gone. T5 fixed: no Title line. T6 fixed: body wrapped, no PR-cause repetition.
- C1 declined: reason is true (verified above) and sufficient. Folding it in would change minutes/hours output that was well formed, which the side-effect rule forbids. The disclosure is accurate. Residual: "Fixing the range case needs a different change" is an inference I did not test. It is reasonable, but "would need a field-specific change" claims less.

## Step 8 (new problems, side-effect rule)
No blocker. Nits, none required:
- The commit body quotes the actual output cut off after "week" (the real output continues ", Sunday through Thursday"). The quote reads as complete.
- PR.md still has two line numbers (`:798`, `:753`). `:753` is correct in the fixed tree; `:798` is the c08a7d6 line and shifts to 801 after the patch.
- Side-effect rule: affected users have a list whose first member is plain and a later member has a step. The old text was malformed in every sampled row. vi text now reads "mỗi ngày 2 tháng" (the existing locale string, disclosed in PR.md). No DROP.

## Not checked
Fresh `npm ci && npm test` on a Mac and Node 20/22/24. Closed or open upstream issues and PRs (tracker unreachable). Native-speaker wording of any locale. Non-en/de/fr/es locales for well-formed-to-changed rows beyond the shared `viol`/`enNewBad` counters. Whether a field-aware fix for range-first lists exists. Textual conflict with other open PRs.

| red | green | revert | suite | repro | patch-applies | PASS/FAIL |
|---|---|---|---|---|---|---|
| fails (actual `AMonly ... and , every`) | 1 passing | fails again | 184 file / 406 full | all PR.md strings match, C1 claim true | git am ok, tree equal | PASS |
