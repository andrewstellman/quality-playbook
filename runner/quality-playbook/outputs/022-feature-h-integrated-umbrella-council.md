# Output for 022-feature-h-integrated-umbrella-council.md
**Status:** completed

## What this instruction was
The composition-level self-Council the ten Feature H slices (012–021) could not
run — each slice was Councilled *in isolation*. This reviewed the **assembled**
pipeline end-to-end and asked: does any seam regress a guard when the pieces run in
sequence? An integrated review, not new features. It surfaced one FIX-REQUIRED,
which was fixed and re-reviewed to SHIP before filing.

## Terminal verdict: unanimous SHIP (after one FIX-REQUIRED → fix → re-review)
| Charter | Round 1 | Post-fix |
|---------|---------|----------|
| A — Security composition | **SHIP** | — |
| B — Data-flow integrity end to end | **FIX-REQUIRED** | **SHIP** (re-review of `fc20c2e`) |
| C — Remediator-not-a-gate + honesty, composed | **SHIP** | — |

Three fresh-context panelists, each in its own git worktree, each **RUNNING** a
real end-to-end `run_feature_h` pass (stubbed spawn) and mutation-biting the
composed path — **not unit tests alone** (acceptance item 1 + the output's "exercise
the end-to-end pass" requirement).

## The composition bug found + fixed + re-reviewed (acceptance item 2)
**Confirm/drop moves were silently lost at the grounding→merge seam.**
`run_feature_h` step 3 forwarded only `gr.grounded` to the merge, but Guard 1
(`persona_grounding.classify_diff_set`) gates ONLY `add`/`correct` — `classify_move`
returns `None` for `confirm`/`drop`, which then landed in neither `grounded` nor
`candidates` and never reached the merge.

Consequences vs Design §8b:
- **guard 4** ("grounded add/correct/**drop** moves are applied") — a persona
  `drop` was never applied by the composed pipeline.
- **guard 3** (conflict check covers confirm/correct/add/drop) — an
  add/confirm/correct-vs-drop conflict could never surface → a contested REQ was
  silently resolved (the "silent pick" §8b forbids).

The seam lived only in the composition — the isolated slices' tests exercised only
`add`, which is why the umbrella Council was the first to see it.

### Root-cause fix (commit `fc20c2e`)
The move taxonomy had drifted across two modules; the fix keeps it in one place.
| File | Change |
|------|--------|
| `plugins/.../scripts/persona_grounding.py` | `PASS_THROUGH_MOVES = ("confirm","drop")` beside `GATED_MOVES`; a `passthrough` bucket on `GroundingResult`; `classify_diff_set` collects ungated persona moves (confirm/drop — NOT operator-only `defer`) into it. |
| `plugins/.../scripts/persona_apply.py` | `run_feature_h` step 3 forwards `[c.move for c in gr.grounded] + list(gr.passthrough)` to the merge. |
| `plugins/.../scripts/persona_merge.py` | Docstring corrected — it already handled all four `_PERSONA_MOVES`; **no guard logic changed**. The seam was simply starved of two moves. |
| `bin/tests/test_persona_pipeline_v160.py` | **New** `ConfirmDropSeamTests` (3 composed-pipeline tests): a drop applies through `run_feature_h`; a drop-vs-correct pair surfaces a conflict (not a silent pick); a confirm reaches the merge and is surfaced. |

**Mutation-confirmed load-bearing:** reverting the `+ list(gr.passthrough)` forward
fails all three new tests (one reproducing the original `conflict_count: 0`
silent-pick and "drop not applied"); restored → all pass. Panelist B independently
re-verified end-to-end (19/19) on the fixed commit: drop applies, conflict surfaces,
confirm reaches merge, `defer` stays excluded (and is additionally rejected by
`_validate_diff_set`), no injection bypass opened, persona_id preserved for conflict
grouping, and round-1 Tasks 1–3 (grounding, provenance/citation, revert round-trip)
still hold — no regression.

## Commits made (branch `1.6.0`, local only — never pushed)
- `fc20c2e` — fix confirm/drop lost at the grounding→merge seam (+ `ConfirmDropSeamTests`).
- `e5baf41` — tracked umbrella-Council synthesis.

## Acceptance oracle — pass/fail
| # | Item | Result |
|---|------|--------|
| 1 | All three charters SHIP, demonstrated against a composed end-to-end pass (not unit tests alone) | **PASS** — A/C SHIP round 1; B SHIP on re-review; all ran real `run_feature_h` end-to-end + mutation-bit |
| 2 | Any composition bug found is fixed and re-reviewed (not just noted) | **PASS** — confirm/drop seam fixed (`fc20c2e`), Panelist B re-review SHIP |
| 3 | Full suite green | **PASS** — 2741 / 0 / 14, Python 3.14.6 |

## Verification
Full suite **2741 / 0 / 14**, Python 3.14.6 (baseline 2738/0/13 + 3 new seam
tests; the skip-count delta 13→14 is a pre-existing environment-conditional skip —
`no quality/ directory` + metrics_reconstruction global-skip variance — unrelated
to this change, which touches only the persona modules). The composed end-to-end
pass was exercised by all three panelists via a stubbed spawn; the live spawn is
the running agent's Task tool at pipeline-run time (instruction 019 is the live
acceptance).

## Is Feature H integration-clean?
**Yes.** The assembled pipeline holds together end to end: isolation, provenance
write-restriction, injection-candidate-only, and the poisoning fixture hold
composed (A); a move's agent-validation provenance + byte-verified citation survive
every hop, the renumber remap reaches BUG cross-refs, and revert round-trips on
full-pipeline output (B); no gate/verdict emerged, the review summary lists every
applied change, the maturity disclosure fires on rubric-resting output, and the
off-switch disables the whole pass (C). The one composition seam is closed and
re-reviewed. **Feature H is ready for broader acceptance testing.**

## Non-blocking observations (recorded for the orchestrator, NOT fixed here)
Per the instruction's "no scope creep" bound; neither regresses a guard and both
panelists SHIP'd with them noted:
1. **A:** `run_personas` computes `fabrication_flags` but `run_feature_h` doesn't
   consume/halt on them — design-consistent (the fabrication-tell is an explicit
   backstop; grounding is the load-bearing gate; a fabricated citation fails
   byte-verify regardless). A future slice could surface the flags in the review
   summary.
2. **C:** `candidate_bucket` drops `dimension`/`rubric_dependent`, so a
   rubric-dependent *candidate* doesn't contribute to the maturity-disclosure
   count, mismatching `build_review_summary`'s comment. No false confidence arises
   (candidates are surfaced as uncertain; applied + conflict moves fire the
   disclosure). Optional tidy-up: carry the fields in `candidate_bucket`.

## Out of scope (per the instruction — remaining pre-ship items for the orchestrator)
Feature-G non-plaintext-contract → FORMAL_DOC wiring; chi/express Slice-1
coherence-fixture regen; OD-9 live FP bound from instr-019 data; OD-11
(drop/selective-revert BUG-reference re-point) hardening; Phase 8 tag/merge; the
deeper design question of whether an injected `drop` should be injection-screened
(the design currently scopes injection candidate-bucketing to add/correct and makes
drops applied+surfaced+revertible — implementing per the existing design was correct
for this seam fix; extending the drop threat model would be new capability).

## Artifacts
- Gitignored: `runner/quality-playbook/reviews/022_umbrella_council/` (four
  panelist verdicts — A, B round 1, B re-review, C).
- Tracked: `docs/process/QPB_v1.6.0_Instruction_022_Umbrella_Council/synthesis.md`.
