# Instruction 005 — bump the skill version to 1.6.0 (activates Feature C) + verify

Small but load-bearing. The render contract (Feature C) is gated on skill version ≥ 1.6.0; the skill still stamps **1.5.10**, so the entire render contract is **inert on every run** — it skips with "run recorded skill version 1.5.10 — the render contract is a v1.6.0+ obligation, skipped." A 2026-07-21 test confirmed this: a fully contract-conformant document (27 `### REQ-NNN:` headings, correct sections, glossary) was NOT checked because the run stamped 1.5.10. Only after forcing the recorded version to 1.6.0 did the contract fire (and pass, 12 checks). The version bump is the activation switch for the release's headline feature.

## Read first
- `plugins/quality-playbook/skills/quality-playbook/SKILL.md` frontmatter (the single version source — instruction 057 consolidated everything to derive from it).
- `plugins/quality-playbook/skills/quality-playbook/scripts/benchmark_lib.py` around line 185–191 (the `RELEASE_VERSION = detect_skill_version()` block + its defensive fallback literal).
- `ai_context/DEVELOPMENT_PROCESS.md`.

## Work items

### 1. Bump the single version source
`SKILL.md` frontmatter: `version: 1.5.10` → `version: 1.6.0`. This is THE canonical source; `quality_playbook_cli.__version__`, `benchmark_lib.RELEASE_VERSION`, and the attribution banner all derive from it at runtime via `_purpose.get_version()`. Confirm that derivation by checking the banner/CLI report 1.6.0 after the change.

### 2. Fix the stale defensive fallback literal
`benchmark_lib.py` ~line 191: the `if RELEASE_VERSION == "unknown": RELEASE_VERSION = "1.5.10"` fallback (reached only in a broken clone) still says `"1.5.10"`. Update to `"1.6.0"` for honesty. This is defensive-only, but leaving it stale is the kind of drift this release exists to eliminate.

### 3. Verify the activation does not break anything
Bumping to 1.6.0 activates the render contract on every run. Confirm:
- **Full suite green at 1.6.0.** `python3 -m unittest discover bin/tests`. Report counts + Python version. Any version-gated test that assumed 1.5.10 behavior must be found and reconciled — a test that silently flips is a finding.
- **The render contract now activates rather than skipping.** Confirm the render-contract fixture tests exercise the *active* path (the fixtures should already stamp ≥1.6.0; verify they aren't relying on the skip branch). If any fixture test only passed because the contract was inert, that is exactly the kind of vacuity to surface.
- **The 004 fail-closed still fires at 1.6.0.** The bold-marker mutation bite (populated manifest + no `### REQ-NNN:` headings → FAIL) must still turn RED when neutered, now with the version gate live.

### 4. CHANGELOG
Add or update the in-progress 1.6.0 CHANGELOG entry to reflect that this is the version the requirements-release features (C, D, F) ship under. Do not fabricate benchmark numbers or a ship date.

## Scope note
Version-string bump + its verification only. Do NOT retag, publish, or touch release automation — publishing is deferred (see `QPB_Carry_Forward_To_1.6.0.md`). Do NOT hand-edit test fixtures to pass.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight the branch, `pre-flight-aborted` if wrong. Local commits only; **never push/merge**.
- Given the size, a **focused single-panel self-Council** suffices, with one charter that specifically checks item 3: that no test flipped behavior silently and no fixture was passing only because the contract was inert. Artifacts under `RUNNER_ROOT/reviews/005_self_council/` + tracked copy under `docs/process/QPB_v1.6.0_Instruction_005_Self_Council/`.
- Output `outputs/005-activate-v160-version.md`: the derivation confirmation (banner/CLI now report 1.6.0), full-suite counts, confirmation the render contract now activates + the fail-closed still fires, any test that had to be reconciled, and anything you found underspecified or wrong.
