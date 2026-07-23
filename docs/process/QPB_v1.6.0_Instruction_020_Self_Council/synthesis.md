# Self-review — instruction 020 (bundle the six Feature H modules adopter-side)

**Verdict: SHIP.** Mechanical bundle propagation, focused review per the
instruction (like the 013/018 mechanical slices). The three checks:

## (a) Every drift site updated — no adopter-install gap
Mirroring instruction 010's `doc_classification.py` bundling, the six modules
(`persona_catalog`, `persona_orchestration`, `persona_grounding`, `persona_merge`,
`persona_apply`, `requirements_render`) were added at **every** site that
enumerates the mandatory skill modules:
1. `install_skill.py` `_bundle_files` — a `_require_bundle_file` loop for the six
   (the canonical enumerator `install()` uses; mandatory, so a missing module
   fails the install).
2. `install_skill.py` `_bundle_files_soft` `_mod` list.
3. `qpb_validate.py` `INSTALL_CLOSURE` — six `bundled_module` entries.
4. `run_state_lib.py` `_FLAT_LAYOUT_BUNDLED_BIN_FILES` — six entries.
5. `AGENTS.md` — six `cp` lines in BOTH layout blocks (.github and .claude).
6. `repos/setup_repos.sh` — six `cp` lines.
The full bundle-drift guard suite (57 tests: install_manifest_no_drift,
install_skill, install_skill_bundle_completeness, installed_skill_guardrail,
setup_repos_bundle_parity) is green — proving no site was missed (the guards
cross-check the sites against each other).

## (b) The count-pin bump matches exactly six new modules
`test_install_manifest_no_drift.py` INSTALL_CLOSURE count-pin: **63 → 69** (+6).
Documented in place as genuine bundle growth (six new mandatory Feature H modules),
not a fixture dodge. Empirically confirmed: a fresh `install_skill.install()` into
a throwaway target reports `files_copied=69`, its smoke check passes, and all
**6/6** persona modules are present in the installed `bin/`.

## (c) No feature logic touched
`git status` shows only the six drift sites + the count-pin test changed. **None of
the six `persona_*.py` / `requirements_render.py` source files was modified** — pure
bundle enumeration + cp recipes + the count-pin. (The orchestrator's uncommitted
`docs/design` edit sits in the tree, left alone.)

## Verification
Fresh install ships all six (6/6, files_copied=69). Full suite green (see the
instruction output for the count); Python 3.14.6.

**Terminal verdict: SHIP.** An adopter who installs the skill now actually receives
Feature H. After this, only the integrated umbrella Council + broader 1.6.0
acceptance testing remain before ship.
