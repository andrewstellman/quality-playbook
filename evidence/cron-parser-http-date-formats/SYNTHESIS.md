# Synthesis: cron-parser-http-date-formats (BUG-023)

Roster: full panel, 15 reviewers, all Sonnet. All 15 files exist in `panel/`. No REJECT, no DROP.

| Item | A | B | O1 | O2 | O3 | O4 | O5 | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cron-parser-http-date-formats | F | F | F | S | F | F | F | F | F | F | F | F | S | F | F |

S = SHIP, F = FIX-REQUIRED, R = REJECT, D = DROP, – = not run.

Outcome: **REVISE**. The code change (one line in `src/CronDate.ts`, two tests) is not criticised by anyone. Every FIX-REQUIRED is about the PR text, the commit body, or the stale base. Several reviewers (EXEC-A, O3, S8, S7, S1, S4) applied the patch to the upstream tip 5033a31 with `git am`: it applies cleanly, the unit suite gives 348 passed, and EXEC-A, O3 and S8 report `full-check exit 0` there. `src/CronDate.ts` and `tests/CronDate.test.ts` are identical between 5b08cdf and 5033a31 (O4, S6, S2), and the bug still reproduces at the tip.

Side-effect rule: no reviewer found a reason to drop. Strings that parse today never reach `fromHTTP` (last link of the `isValid ||` chain, `src/CronDate.ts:54`); O3 fuzzed 48000 mutated inputs and found 0 changed results; S5 compared 22 inputs in 4 zones. Affected: callers who relied on the throw for RFC 850 or asctime strings (very unlikely), and callers who start passing zone-less asctime strings meant as local time (read as GMT, no error; low). Both acceptable.

## Findings that must change

1. **Stale base and stale counts (all 15 reviewers raised it; O2 and S6 as a side note).** `PR.md` Additional Notes says "The change is made on upstream master at 5b08cdf." and Testing says "340 tests passed (338 before)". The tip is 5033a31 and the counts there are 348 (346 before). Also `CONFIRMATION.md` says "No newer commits", which is wrong. Change: rebase the commit onto 5033a31, regenerate the patch with `git format-patch`, rerun `bin/full-check` on that clone, replace `full-check.log`, `suite.log`, `lint.log`, `red.log`, `green.log`, `revert.log` with the tip runs, then use the counts from that run. Replacement sentences (S7, S8, EXEC-A, adapted): Additional Notes: "The change is made on upstream master at 5033a31." Testing: "... it ended `full-check exit 0` with 348 tests passed (346 before)." Use the numbers the rerun prints. The "rebased on latest master" box may be ticked only after the rebase.
2. **Ticked boxes name commands that were not run (EXEC-A, EXEC-B, O1, O2, O3, O4, O5, S1, S2, S3, S5, S7 minor, S8).** `PR.md` ticks `npm test`, `npm run lint`, `npm run format`, `npm run build` and also says "I did not run the npm scripts themselves." `npm run format` is `prettier --write`; only `--check` ran. Change: untick those four boxes and keep the sentence naming what ran (full-check). Alternative the panel allows: run the four scripts in the rebased clone and keep the ticks, then delete the disclaiming sentence. Do not leave both.
3. **Behaviour change not stated plainly (S5, O2, O5; O3 and O4 as notes).** Text says the zone differs from RFC 2822 but never says that strings that threw now return a date, or that a zone-less asctime string meant as local time is now read as GMT without an error. Change: add one sentence after the Zone paragraph: "These two formats used to throw. A caller who passes a zone-less asctime string that was meant as local time now gets a GMT date instead of an error." Do not name `ctime` or Python output formats; O2 said that was not run. Also add (S5, EXEC-A ran it): "The zero-padded day form (`Sun Nov 06 08:49:37 1994`) is accepted too."
4. **Empty template placeholders (EXEC-A, EXEC-B, O1, O3, O5, S1, S2, S3, S5, S8).** "Fixes # (issue number if applicable)" in Description and the three empty bullets in Related Issues. Keep every heading. Change: delete the Description "Fixes #" line; under Related Issues write `None.` Do not write "no duplicate": the tracker was checked only against `known_open_bugs.md` (open items, 2026-10-05) and `pr/*` heads.
5. **Description is longer than merged fixes and partly restates the diff (O5, S3).** POLICY.md records 2-10 lines of prose for merged outside fixes. Change: delete the two sentences that restate the diff ("The constructor tries `fromISO` ... and never `DateTime.fromHTTP`" and "The fix adds `DateTime.fromHTTP` as the last attempt"), keep the repro, the README quote with line numbers, the "inputs that parse today never reach it" sentence, the Zone paragraph and the closing README alternative. O5 and S3 each gave full replacement text in their files; the operator may use O5's three-paragraph version.
6. **Commit body restates the diff and omits the GMT decision (O5, S3).** Change the body to (O5): `README lists HTTP as a supported string format, but CronDate never called DateTime.fromHTTP, so "Sunday, 06-Nov-94 08:49:37 GMT" and "Sun Nov  6 08:49:37 1994" threw "unhandled timestamp". Try fromHTTP last so inputs that parse today are unchanged. fromHTTP reads all HTTP dates as GMT, so the asctime form ignores the tz option.` Subject stays. No trailers.

## Optional, worth doing (cheap)

- **Where "HTTP" in the README came from (O4).** Add after the README quote: "That list came from commit ef172bd, which linked 'HTTP and RFC2822' to luxon's parsing section of the same name." O4 checked this with `git show ef172bd`. The operator should repeat that command before using the sentence. It answers the likeliest reply ("IMF-fixdate already works, docs only").
- **Repro block (S1).** Move the hand-aligned "expected for the last two" row out of the fence into a sentence.
- **Inherited behaviour (O4).** Add to the Zone paragraph: "This is what `DateTime.fromHTTP` does; I did not add zone handling."
- **CONFIRMATION.md (O1, O3, S5, S7, S8).** Correct its "clone HEAD = 5b08cdf = upstream tip" line in REVIEW.md's review history. It is not part of the PR text.

## Findings not adopted

- **Rename the tests** to `HTTP RFC 850 with GMT` / `HTTP asctime without zone, read as GMT` (S2). Optional by the reviewer's own words; the current names match the neighbours and the asctime one states the GMT decision.
- **Add a negative test** for a near-miss string such as `Mon Nov  6 08:49:37 1994` (S4), or a default-zone test (S4), or a local-timezone-block test (S1, S2 advises against). The patch is meant to be one test per new format; these would test luxon, not this change. S4 itself says it would not require it.
- **Mention two-digit year pivots** (O3, S5, EXEC-B). EXEC-B and O3 say not to claim RFC-exact years; O4 says leave it out. Adding it widens the text for an obsolete format and a luxon rule.
- **Drop or keep the "13 inputs in three zones" sentence.** O5 and S3 want it dropped; S7 says it is true (`sideeffect.log`) and should stay. Either is acceptable; the operator's choice. Not a required change.
- **Add a performance sentence** (S6). S6 says it is not needed and the Performance boxes are correctly unticked.
- **Tick more boxes** (O5: "No new TypeScript errors"; S8: "read CONTRIBUTING", "rebased"). The operator ticks what they have checked. Only "rebased" follows from finding 1.
- **Comment explaining why `fromHTTP` is last** (S1 finding 6). S1 itself says no: neighbours have none.
- **Rewrite "Changes Made" bullets** (O5, S3). Minor padding; take it only if the operator is already editing that section.
- **Append "(not npm test)" to each ticked box** (O4). Superseded by finding 2.
- **Process worry about "issue first"** (O4 finding 5). POLICY.md says no issue is needed for a bug fix; O4 wrote no text change.
- **Open PR #446 touches `src/CronDate.ts`** (EXEC-B, O3). Both judged a textual conflict unlikely; neither read the diff. Not a change to the PR; note for REVIEW.md "Things to know".

## Not checked by anyone

Closed issues and PRs on the forge; the npm scripts by name; the operator's Mac command (`npm ci --ignore-scripts && TZ=UTC npx jest`); luxon versions other than 3.7.2; whether the maintainer would rather change the README than the code (PR.md already offers that).

## Round 2 (2026-10-10)

Round 1 is kept in `rev0/` (patch, PR.md, logs). The revision is text-only apart from the rebase: `src/CronDate.ts` and `tests/CronDate.test.ts` are unchanged (patch hunks identical to rev0, checked by S1, S3, S5, S8, EXEC-A). A fixer sub-agent rebased the single commit onto 5033a31 and reran the logs; the parent then made two text edits (below).

**What was changed, per finding**

1. Stale base and counts: commit rebased onto 5033a312. `red.log` (2 failed, 47 skipped, 49 total), `green.log` (49 passed), `revert.log` (2 failed, 47 passed), `suite.log` and `full-check.log`/`lint.log` (348 passed; `full-check exit 0`) rewritten. PR.md now says 5033a31 and "348 tests passed (346 before)"; the "rebased" box is ticked. `CONFIRMATION.md` got a dated correction line under its wrong "No newer commits".
2. Boxes naming commands not run: `npm test`, `npm run lint`, `npm run format`, `npm run build` unticked; "I did not run the npm scripts themselves." kept once in Testing. The same sentence in Additional Notes was deleted (S3 finding 3).
3. Behaviour change: added "These two formats used to throw, so a caller who passes a zone-less asctime string that was meant as local time now gets a GMT date instead of an error." and the zero-padded day sentence. Both run by EXEC-A, EXEC-B, S3, S4, S5, O4.
4. Placeholders: "Fixes #" line removed, Related Issues says `None.`; all headings kept.
5. Description: the two diff-restating sentences and the "13 inputs" sentence deleted; the Zone paragraph and the "used to throw" paragraph were merged (S3 finding 2, in part); the `src/CronDate.ts:54` citation was dropped because it is true only in the patched file (S7).
6. Commit body replaced (O5 text). After round 2 (O3, S7) the last sentence now reads "so the asctime form is read as GMT, not in the tz option." Patch regenerated; tree unchanged (`89ed3826d21ddaf2f4d8bb3f28476bc2c1c782d5`), checked by `git am` on a clean clone of 5033a31.
7. Optional items taken: repro block cleaned, "inherited behaviour" sentence, ef172bd sentence.

**New finding in round 2 (10 of 13 re-reviewers raised it: the eight F verdicts, O4 and S5)**: PR.md cited `ef172bd`, which exists only as the head of PR #252 (`refs/remotes/pr/252`) and is not an ancestor of master. The merged commit is `9332e6b` "readme: switched from moment to luxon (#252)"; I ran `git show 9332e6b -- README.md` and it adds the `HTTP and RFC2822` luxon link. PR.md now cites 9332e6b (#252). The error came from the round-1 optional item (O4's hash), which I adopted without checking ancestry. Note for the operator: the round-1 text above (optional items) still carries the wrong hash.

**Not adopted in round 2**

- O5 and S3 trims: replacing the Description with O5's three paragraphs, dropping the repro fence and the zero-padded sentence, shortening Testing and Changes Made. The Description is still longer than the 2-10 prose lines POLICY.md records (EXEC-B nit; O5, S3). Every sentence in it was run; the operator may cut further.
- O5 and S3: run `npm test`, `npm run lint`, `npm run build` on the Mac and tick those boxes, then delete the disclaimer. That is the operator's call; O5 ran the four scripts in a scratch copy (all exit 0, 348 passed) but the PR must not tick what the operator has not run. Left unticked.
- S7: cite b5f4194 (the TypeScript rewrite that wrote the current README lines). The sentence says the entry was added in 9332e6b, which is true; not widened.
- S2 test renames, S4 negative/default-zone tests, S1 comment on order: not adopted (same reasons as round 1).
- `sideeffect.log` was not rerun (dated 2026-10-07, old base); PR.md no longer cites it and the code line is identical. EXEC-B and EXEC-A reran their own differential fuzz at the tip (6000 and about 4000 strings): 0 changes where the old chain returned a value.

**Re-review row** (13 roles run: EXEC-A, EXEC-B and every round-1 FIX-REQUIRED; O2 and S6 were SHIP and were not rerun)

| Item | A | B | O1 | O2 | O3 | O4 | O5 | S1 | S2 | S3 | S4 | S5 | S6 | S7 | S8 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cron-parser-http-date-formats (round 2) | F | S | F | – | F | S | F | F | S | F | F | S | – | F | S |

Every code check passed: red, green, revert, suite 348/346, repro, `full-check exit 0` (EXEC-A, S8, S7, EXEC-B on their own copies), patch applies to a clean 5033a31 and gives the tree at HEAD. No reviewer found a code problem or a reason to drop. All eight F verdicts rest on text points: the wrong ef172bd hash (all eight), plus the "ignores the tz option" wording (O3, S7), the `src/CronDate.ts:54` citation (S7), description length and duplicated disclaimer (O5, S3). Those were fixed or consciously not adopted, as listed above. I applied the fixes myself and verified them (`git show 9332e6b`, `git merge-base --is-ancestor`, `git am` tree id, grep for em dashes); the final text was not re-reviewed by another agent.

Process note: my first EXEC-A call was launched with an unfinished prompt (no rules file read, scratch in the session scratchpad instead of the run directory, no round-2 file). I discarded that run and relaunched EXEC-A with the full prompt; only the second run counts.

Outcome: **SHIP**.
