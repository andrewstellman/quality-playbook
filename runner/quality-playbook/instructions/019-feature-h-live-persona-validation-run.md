# Instruction 019 — v1.6.0 Feature H slice 7: live persona-validation run (acceptance oracle 1)

Feature H's mechanical build is complete (slices: Guard 2, catalog, isolation, Guard 1, Guard 3, Guard 4, maturity/seam). This slice is the **empirical acceptance**: run the assembled persona validation **live** (real LLM sub-agents, not stubs) on real repos and confirm it finds the real missing requirements within the false-positive ceiling. This is §8b Verification item 1 and §10 criterion 8's core claim.

## This is a live run, not a code edit
Personas here are **live sub-agents** you spawn (via your Task tool, the same mechanism as the self-Council panel), each under the slice-2 isolation (staged inputs only; Read-confined; no shell/network). Do not stub the model. If a live persona pass genuinely cannot run in your tick, say so precisely and file `partial` — do not fake a run or hand-edit a fixture to simulate one (fixture discipline).

## Scope
Run persona validation on **chi, express, and virtio** (the repos whose real gaps are already known from the 2026-07-22 three-agent test) using the assembled Feature H pipeline, and record results. No new feature code; small glue to invoke the assembled pipeline live is fine.

## Read first
- `docs/design/QPB_v1.6.0_Design.md` **§8b Verification items 1–8** (the oracle) and **§12 OD-9** (the live-repo FP tolerance is open; the *fixture* bound is 0, the live bound is what this run informs).
- The assembled Feature H modules: `persona_catalog.py`, `persona_orchestration.py`, `persona_grounding.py`, `persona_merge.py`, and the Guard-4 apply/review/revert from instruction 017.
- The 2026-07-22 known gaps: chi (regexp route params), express (`req.range`), virtio (indirect-descriptor constraints) — the personas should autonomously surface these.
- `ai_context/DEVELOPMENT_PROCESS.md`.

## What to do
1. For each of chi/express/virtio: run the live persona validation over that repo's gathered docs + rendered `REQUIREMENTS.md` + rubric (Feature G's classified corpus is the doc input). Anchored domain + security personas plus any AI-selected lens, each isolated per slice 2.
2. Record, per repo: which personas were selected + why; the grounded adds/corrects applied (with citations); the candidate bucket; any conflicts; and whether the known real gap was surfaced.
3. Report the **false-positive count**: grounded adds that are NOT real requirements. On these live repos "complete" is unknowable, so surface every add — but flag any that look spurious. This informs OD-9 (do not set the live bound unilaterally; report data for the operator).
4. Confirm the safety envelope held live: no persona read the implementation tree (isolation), every applied change is `agent-validation` + byte-verified (Guards 1/2), the review summary lists them, and the revert round-trips.

## Acceptance
1. On chi/express/virtio the personas autonomously surface the known real gaps.
2. Grounded adds are cited + byte-verified; ungrounded expectations are candidate-only.
3. Isolation held live (no impl-tree reads); provenance + review summary + revert all functioned on live output.
4. A per-repo FP count is reported (data for OD-9; the fixture bound remains 0).
5. Existing suite unchanged and green.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight; local commits only; **never push/merge**.
- Self-Council per §13 if code/glue landed; if this is purely a live run producing a results artifact, a focused review of the results' honesty (did the personas really run live; are the found-gap claims verifiable) suffices. Artifacts under `RUNNER_ROOT/reviews/019_self_council/` + tracked copy under `docs/process/QPB_v1.6.0_Instruction_019_Self_Council/`.
- Verify the full suite; report counts + Python version.
- Output `outputs/019-feature-h-live-persona-validation-run.md`: per-repo selected personas + rationale; gaps found (and whether the known ones were surfaced); grounded vs candidate counts; FP count per repo (OD-9 data); confirmation the safety envelope held live; and — importantly — a clear statement of whether this was a genuine live model run or (if it could not be) exactly why, so the orchestrator can arrange a live vessel. After this, Feature H is functionally complete pending the integrated umbrella Council + the broader 1.6.0 acceptance testing.
