# Instruction 006 self-Council — synthesis

**Scope:** v1.6.0 Feature C — the derivation chooses the requirements' organizing principle
(Design §5.2 item 4, revised 2026-07-21), replacing the fixed "functional sections" mandate.
**Charters (per the instruction):** (a) the principle-agnostic render contract incl. the
non-functional-grouping fixture and the mutation bites; (b) the selection-pass correctness
across the pipeline doc + generation guide (routing); (c) interview integration + glossary
reconcile completeness.
**Isolation:** each panelist in its own git worktree.

## Verdict trajectory

| Panelist | Charter | Round 1 (`1728ef3`) | Closure |
|----------|---------|---------------------|---------|
| A | principle-agnostic render contract | SHIP (1 P2) | *P2 closed in `2fb7857`* |
| B | selection pass / routing | FIX-REQUIRED (1 P1) | FIX-REQUIRED again (`2fb7857`), then **SHIP** (`edce797`) |
| C | interview + glossary reconcile | SHIP (1 P2 = B's) | *closed with B's P1* |

**Outcome: unanimous SHIP, zero open findings.**

## What A confirmed (contract)

MP-4 (principle named + rationale + per-section overview, presence-only) is correct and
gated behind `if functional:`, never inspects *which* principle (row-4c split preserved).
Mutation-bitten: neutering "no principle" → 10 tests RED; "no rationale" → 1; section
overview → 2. The headline regression `test_non_functional_grouping_is_accepted` (a
use-case-organized document) genuinely PASSES the full unmutated contract. A independently
proved the golden-fixture oracle reconcile still catches real regressions — it injected a
C-2 renumber defect into a fixture copy and confirmed the oracle FAILs on it, so the
`EXPECTED_FIXTURE_FAILS` allowlist admits only the recorded principle gap. AUDIT integrity
(11 rows, MP-4 bite) intact.

## What B drove (routing consistency — the persistent finding)

The mechanical gate cannot check literal section-ordering prose, so a principle-agnostic
render contract can coexist with docs that still command the old "user-facing →
infrastructure" ordering — exactly the drift B's charter targets. B found it in three
places across two rounds: `phase2_generation_guide.md:167`/`:173` (round 1), then
`phase_prompts/phase2.md:50` (closure) — the last being the Phase 2 prompt the executing
agent reads *first*, and missed initially because the worker's sweep grepped the spaced
arrow while that spot used the unspaced one. All three are now reframed to
"most-relevant-to-the-primary-reader first"; B's final exhaustive sweep confirms the only
remaining mentions are deliberate "generalization of the old rule" references.

## What C confirmed (interview + glossary)

Stage 1 plays back the organizing principle with the "right lens / would Z fit" framing (a
change = a `correct` move → re-group + re-render), placed before the coverage-gaps playback.
Stage 2 reads each section overview and validates the theme before descending,
principle-agnostic. Glossary reconcile complete — the guide's part list now matches Design
§5.2 order-for-order with glossary as part 9; the old "reader meets vocabulary first"
rationale is gone; `docs/design/` correctly left untouched (orchestrator-owned, dirty).

## Design findings surfaced (out of the worker's fix scope)

1. **Row 4b (mandatory FAIL) vs. the §5/§10-criterion-1 acceptance oracle.** The golden
   chi/express/virtio fixtures predate the selection pass and state no principle, so a
   mandatory principle-FAIL necessarily makes them fail — but the oracle asserts they pass.
   Reconciled via an `EXPECTED_FIXTURE_FAILS` allowlist (FAIL-side analogue of the glossary
   WARN allowlist) + staleness guard, recorded in `QPB_v1.6.0_Regeneration_Expectations.md`.
   The design should state row-4b compliance is expected only of post-006 renders, or
   schedule the fixture regeneration.
2. **"Section overview" IS the existing intro-prose check**, re-scoped — the matrix would
   read more clearly saying so than implying a second independent check.
3. **`functional_section`** is now a slightly misdescriptive manifest key under a
   non-functional grouping; a one-line schema note would prevent a wrong assumption.

## State at filing

Full suite **2600 tests, 0 failures (14 skipped)**, Python 3.14.6. All mutation bites
restored via `shutil.copy2`, `__pycache__` purged, worktrees clean. Cleared to file.
