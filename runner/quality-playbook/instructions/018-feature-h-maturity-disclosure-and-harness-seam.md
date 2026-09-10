# Instruction 018 — v1.6.0 Feature H slice 6: maturity disclosure + target-agnostic harness seam

Two small, self-contained finishes to Feature H's mechanical build. Neither is new machinery: (1) make the run honest about the confidence of output that leans on a not-yet-functional judgment layer; (2) lock in — with a test — the target-agnostic seam the earlier slices already built, so v1.6.1's Feature B can reuse the harness without a rewrite.

## Scope of THIS instruction
**Maturity disclosure + the harness-seam assertion only.** Out of scope: the live persona run (slice 7); the acceptance/benchmark runs. Stop and file when acceptance passes.

## Read first — these ARE the spec
- `docs/design/QPB_v1.6.0_Design.md` **§8b "Honesty about maturity"** and the **"Relationship to Feature D and to v1.6.1"** paragraph (the target-agnostic-harness requirement — "context provisioning is a per-target parameter"; "no shared calibration harness"). Also **§5 Verification (b)** (the readability rubric "not yet a functional drift detector").
- `plugins/quality-playbook/skills/quality-playbook/scripts/persona_orchestration.py` — `StagedInput` / the spawn seam already made per-target ("H: docs/spec/rubric; B: finding/source/REQ/rubric"). This slice asserts that seam holds; it does not rebuild it.
- The F-1 gaps-disclosure precedent (instruction 008) — the model for how a run discloses a limitation (the maturity disclosure mirrors it).
- `ai_context/DEVELOPMENT_PROCESS.md`.

## The behavior to build

1. **Maturity disclosure.** When a persona's validation output rests on the readability rubric (which the release itself calls not-yet-functional, §5 Verification (b)), the run **discloses** that — the same way F-1 discloses coverage gaps — instead of presenting persona-validated, rubric-checked output with uniform confidence. Concretely: any run summary / review summary that surfaces rubric-dependent findings carries an explicit maturity caveat; output not resting on the rubric is unaffected. Keep it mechanical and honest, not decorative.

2. **Target-agnostic harness seam — assert it, don't rebuild it.** Add a test that proves the persona sub-agent orchestration takes **context provisioning as a per-target parameter**: the same spawn/stage/tool-allowlist path serves H's input set (docs + rendered spec + rubric) and a *different, more restrictive* set (a Feature-B-shaped finding + source + REQ + rubric) without H-specific inputs being hard-coded into the mechanism. Demonstrate the seam Feature B will bind to. Do **not** build Feature B; do **not** introduce any shared "calibration harness" (H has none).

## Acceptance oracle
1. A run whose persona output depends on the readability rubric emits the maturity caveat; a run that does not depend on it does not. Proven by test.
2. The orchestration spawns a persona from a Feature-B-shaped input set through the same seam as an H-shaped set — no H-specific input hard-coded — proven by test.
3. No calibration harness / gating / verdict introduced (this remains a remediator).
4. Existing suite unchanged and green.

## Fixture discipline
Do NOT hand-edit golden fixtures to pass. New fixtures (the maturity-caveat case, the per-target-seam test) are expected.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight the branch, `pre-flight-aborted` if wrong. Local commits only; **never push/merge**.
- Self-Council per §13 — mechanical slice, focused review: (a) the maturity disclosure fires exactly when rubric-dependent and not otherwise; (b) the per-target seam test genuinely exercises a non-H input set through the same path; (c) no gating/calibration/Feature-B scope leaked in. Artifacts under `RUNNER_ROOT/reviews/018_self_council/` + a tracked copy under `docs/process/QPB_v1.6.0_Instruction_018_Self_Council/`.
- Verify the full suite; report counts + Python version.
- Output `outputs/018-feature-h-maturity-disclosure-and-harness-seam.md`: how/when the maturity caveat fires; the per-target-seam test + the non-H input set it exercised; confirmation no calibration/gating crept in; and anything underspecified. Note in the output that after this slice, Feature H's mechanical build is complete and only the live persona run (slice 7) + the integrated Council + acceptance testing remain.
