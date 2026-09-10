# Instruction 022 — v1.6.0 Feature H: integrated umbrella Council over the composed pipeline

Every Feature H slice got its own self-Council **in isolation**. This instruction runs the **composition-level review** the slices could not: does the assembled pipeline — persona selection (013) → orchestration + least-privilege isolation (014) → grounding + candidate bucket (015) → multi-persona merge + single renumber (016) → apply + review summary + revert + off-switch (017) → maturity disclosure + target-agnostic seam (018), with provenance write-restriction (012) throughout, and now bundled adopter-side (020) — hold together **end to end**, with no seam that regresses a guard when the pieces run in sequence?

## Scope
An **integrated review**, not new features. It may surface FIX-REQUIRED items; if it does, fix them and re-review to SHIP before filing. No scope creep into v1.6.1 or new capability.

## Read first
- `docs/design/QPB_v1.6.0_Design.md` **§8b** in full (all four guards, isolation, injection resistance, operator controls, maturity, target-agnostic harness) and **§10 criterion 8**.
- The six modules + `run_state_lib.py`'s write-restriction; the outputs of instructions 012–020.
- `ai_context/DEVELOPMENT_PROCESS.md` and §13 (Council protocol).

## What to do — a full 3-charter self-Council over the COMPOSED pipeline
Spawn three fresh-context panelists (each its own worktree), reviewing the assembled flow, not a single slice. Charters:

1. **Security composition.** With all guards running together on a real end-to-end pass: isolation holds through the whole pipeline (no later slice hands a persona the impl tree or out-of-run authority a staged input reintroduces); the provenance write-restriction (012) can't be bypassed by any composed path; injection-shaped content is candidate-only at *both* the grounding layer (015) and never laundered into `operator-confirmation` (012); the poisoning fixture lands no grounded change through the *full* flow, not just the unit. Mutation-bite the composed path.
2. **Data-flow integrity end to end.** A move flows selection → orchestration → grounding → merge → apply with its `agent-validation` provenance + byte-verified citation intact at every hop; the renumber remap propagates to BUG cross-refs on the composed output; the revert round-trips on output produced by the *full* pipeline (not a hand-built manifest); conflicts + candidates surface correctly when all personas run. No data dropped or mistyped across seams.
3. **Remediator-not-a-gate + honesty, composed.** No gate/verdict/calibration emerged from composition; the review summary lists every applied change across the whole pass; the maturity disclosure fires when composed output rests on the readability rubric; the FP-ceiling discipline (fixture bound 0) holds on composed output; the off-switch disables the *entire* pass.

Each panelist writes SHIP / FIX-REQUIRED per charter + citations. Synthesize. If any charter is FIX-REQUIRED, fix and re-run that charter to SHIP before filing v1.

## Acceptance
1. All three charters reach SHIP (after any fixes), demonstrated against a composed end-to-end pass, not unit tests alone.
2. Any composition bug found is fixed and re-reviewed (not just noted).
3. Full suite green.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight; local commits only; **never push/merge**.
- Artifacts under `RUNNER_ROOT/reviews/022_umbrella_council/` + tracked copy under `docs/process/QPB_v1.6.0_Instruction_022_Umbrella_Council/synthesis.md`.
- Verify the full suite; report counts + Python version.
- Output `outputs/022-feature-h-integrated-umbrella-council.md`: the three composed-pipeline verdicts with citations; any composition bug found + the fix + the re-review; confirmation the end-to-end pass was exercised (not just units); and a clear statement of whether Feature H is integration-clean and ready for broader acceptance testing. Note remaining pre-ship items (Feature-G non-plaintext→FORMAL_DOC wiring, coherence-fixture regen, OD-9 live bound, OD-11 hardening, Phase 8 tag/merge) are out of this instruction's scope.
