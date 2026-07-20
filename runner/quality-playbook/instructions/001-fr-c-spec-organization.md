# Instruction 001 — v1.6.0 Track 1 (Phases 0–2): Feature C, spec organization & coherence

## Read first — these ARE the spec
- `docs/design/QPB_v1.6.0_Design.md` — the locked scope. **Feature C** is the headline of this instruction: §1.2 (the seven named defects C-1…C-7, diagnosed from real reads of `repos/{chi,express,virtio}`) and §5 (the fix — tool invariants split to `quality/RUN_CONTRACT.md`, the 8-part architecture modeled on the Haiku benchmark, the six mechanical `quality_gate.py` checks, the intent-form rule).
- `docs/design/QPB_v1.6.0_Implementation_Plan.md` — Phase 0 (base gate) and Track 1 Phases 1–2. Its operating principle stands: *"The design doc is the spec… no per-phase briefs."* **Decompose the work yourself** — this instruction deliberately does not pre-decompose it.
- `ai_context/DEVELOPMENT_PROCESS.md` — process, Council protocol, verify-before-claim, commit hygiene.

## Scope of THIS instruction
**Phase 0 (base gate) + Track 1 Phase 1 (Feature C build) + Phase 2 (regeneration-fixture acceptance + self-Council). Stop there and file your output. Do NOT start Phase 3.**

Why scoped to the Plan's own Ph2 gate rather than all of Track 1: Feature C rewrites the rendering path that Feature D (Ph3) then drives, so the orchestrator verifies C against the regeneration oracle before D builds on top of it.

Note the documented seam (Plan, OD-10): there are **two unreconciled requirements producers** — the code-path pipeline (`references/requirements_pipeline.md`, Phases A–E) and the four-pass skill derivation (`bin/skill_derivation/`). v1.6.0 does not unify them; if a change belongs to both, apply it to both and say so.

## Branch / commit policy
Work on **`1.6.0`** (branched from `main` after the 1.5.10 close-out). **Pre-flight:** confirm `git -C "$QPB_REPO" rev-parse --abbrev-ref HEAD` is `1.6.0`; if not, write a `pre-flight-aborted` output and stop. Focused local commits. **Never push, never merge** — the operator lands.

## Council
Run the self-Council the Plan specifies for Phase 2, to its stated bar. Write artifacts under `RUNNER_ROOT/reviews/001_self_council/`.

**Evidence-durability requirement:** v1.5.10 lost per-item review evidence because the review path was gitignored. Before you finish, confirm your Council artifacts are actually retrievable (`git check-ignore -v <path>` and/or `git ls-files`). If the path is ignored, **say so explicitly in your output** and also place the artifacts somewhere tracked. Do not report a Council verdict whose evidence cannot be found later.

## Acceptance
The Design's own oracle governs: **re-render the `repos/{chi,express,virtio}` manifests and confirm defects C-1…C-7 are absent.**

Report:
- A **per-defect before/after table** for C-1…C-7 — evidence per defect, not a summary verdict.
- The mechanical `quality_gate.py` checks from §5.3: which landed, and a test proving each fires (a check that cannot fail is not a check).
- Confirmation that **the manifest remains the source of truth** and the rendered spec is a contract-checked presentation of it — not a second source.
- Full suite result + counts + your Python version.

## Output
`outputs/001-fr-c-spec-organization.md` per the README schema, plus:
- the C-1…C-7 before/after table;
- what changed in the rendering path vs. the manifest, and whether any change had to be applied to both producers;
- the self-Council verdict + artifact paths (and their gitignore status);
- **anything in the Design you found underspecified, contradictory, or wrong** — you are the first worker to build against this spec; say so plainly rather than papering over it.
