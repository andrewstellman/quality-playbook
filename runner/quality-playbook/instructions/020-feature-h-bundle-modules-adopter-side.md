# Instruction 020 — v1.6.0 Feature H: bundle the six persona modules adopter-side

Feature H's code is complete and verified, but the six modules it comprises are **not yet in the adopter-side bundle** — so an adopter who installs the skill does not actually receive Feature H. This slice closes that gap. It is **mechanical bundle propagation**, no new feature logic: add the six modules to every bundle-drift site so a fresh install ships them and the drift guards pass.

## The six modules to bundle
`persona_catalog.py`, `persona_orchestration.py`, `persona_grounding.py`, `persona_merge.py`, `persona_apply.py`, and `requirements_render.py` (the E.6-renumber module extracted in instruction 016) — all under `plugins/quality-playbook/skills/quality-playbook/scripts/`.

## Scope
**Bundle propagation only.** No feature-logic changes. Stop and file when a fresh install contains all six and the no-drift test is green.

## Read first — these ARE the spec
- **Instruction 010's output** (`outputs/010-feature-g-dump-and-go-ingest.md`) and its commits — it bundled `doc_classification.py` across the drift sites; **mirror exactly that pattern** for the six modules. That is the precedent to follow.
- The bundle-drift sites (confirm the current set — 010 touched these): `plugins/.../scripts/install_skill.py`, `qpb_validate.py`, `run_state_lib.py` (the mandatory-module lists / drift guards); `AGENTS.md` and `repos/setup_repos.sh` (the `cp` recipes / bundle set); and `bin/tests/test_install_manifest_no_drift.py` (the `INSTALL_CLOSURE` count-pin).
- `ai_context/DEVELOPMENT_PROCESS.md`.

## The behavior
1. Add all six modules to every bundle-drift site that enumerates the mandatory skill modules, exactly as `doc_classification.py` was added in 010.
2. Bump the `INSTALL_CLOSURE` count-pin in `test_install_manifest_no_drift.py` by the legitimate module count (six new modules — state the before/after count and that it is genuine bundle growth, not a fixture dodge).
3. Update the `cp` recipes in `AGENTS.md` / `setup_repos.sh` so a from-scratch install stages all six.
4. Confirm: a fresh install (or the install-manifest test) contains all six modules; the no-drift guards pass; nothing else changed.

## Acceptance oracle
1. The no-drift / install-manifest test is green with all six modules present (count-pin bump documented as legitimate growth).
2. A fresh install / bundle contains all six modules (not just the source tree).
3. No feature logic changed — only bundle enumeration + the count-pin + cp recipes.
4. Full suite green.

## Fixture discipline
The `INSTALL_CLOSURE` count-pin bump is legitimate growth (six new mandatory modules) — document it in place; it is NOT a fixture dodge. Do not hand-edit any other golden fixture to pass.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight; local commits only; **never push/merge**.
- Self-Council per §13 — mechanical, focused review: (a) every drift site updated (no site missed → no adopter-install gap); (b) the count-pin bump matches exactly six new modules; (c) no feature logic touched. Artifacts under `RUNNER_ROOT/reviews/020_self_council/` + tracked copy under `docs/process/QPB_v1.6.0_Instruction_020_Self_Council/`.
- Verify the full suite; report counts + Python version.
- Output `outputs/020-feature-h-bundle-modules-adopter-side.md`: which drift sites you updated, the count-pin before/after, confirmation a fresh install ships all six, and anything underspecified. Note that after this, only the integrated umbrella Council and broader acceptance testing remain before ship.
