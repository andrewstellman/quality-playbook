# Output for 020-feature-h-bundle-modules-adopter-side.md
**Status:** completed

## Files created / changed
| Path | Note |
|------|------|
| `plugins/.../scripts/install_skill.py` | `_bundle_files`: a mandatory `_require_bundle_file` loop for the six modules; `_bundle_files_soft` `_mod` list: the six added. |
| `plugins/.../scripts/qpb_validate.py` | `INSTALL_CLOSURE`: six new `bundled_module` entries. |
| `plugins/.../scripts/run_state_lib.py` | `_FLAT_LAYOUT_BUNDLED_BIN_FILES`: six added. |
| `AGENTS.md` | `cp` recipes: six lines in BOTH layout blocks (.github + .claude). |
| `repos/setup_repos.sh` | `cp` recipes: six lines. |
| `bin/tests/test_install_manifest_no_drift.py` | `INSTALL_CLOSURE` count-pin **63 → 69** (documented as genuine growth). |
| `docs/process/QPB_v1.6.0_Instruction_020_Self_Council/synthesis.md` | Tracked focused self-review. |

## Commits made (branch `1.6.0`, local only — never pushed)
- `a5de30e` — bundle the six Feature H persona modules adopter-side (six drift sites + count-pin).
- `04fd4b8` — tracked self-review.

## Acceptance oracle — pass/fail per item
| # | Item | Result |
|---|------|--------|
| 1 | No-drift / install-manifest test green with all six present (count-pin bump documented) | **PASS** — 57-guard suite green; count-pin 63→69 |
| 2 | A fresh install / bundle contains all six modules (not just the source tree) | **PASS** — `install_skill.install()` into a temp target shipped **6/6** (`files_copied=69`, smoke check passed) |
| 3 | No feature logic changed — only bundle enumeration + count-pin + cp recipes | **PASS** — `git status` shows only the six drift sites + the count-pin test; no `persona_*.py` source touched |
| 4 | Full suite green | **PASS** — 2731 / 0 / 14 |

## Which drift sites were updated
Mirroring instruction 010's `doc_classification.py` bundling exactly, the six modules — `persona_catalog.py`, `persona_orchestration.py`, `persona_grounding.py`, `persona_merge.py`, `persona_apply.py`, `requirements_render.py` — were added at **every** bundle-drift site:
1. **`install_skill.py` `_bundle_files`** (the canonical enumerator `install()` uses): a `_require_bundle_file` loop for the six — mandatory, so a missing module fails the install.
2. **`install_skill.py` `_bundle_files_soft` `_mod` list** (the soft-fallback enumerator).
3. **`qpb_validate.py` `INSTALL_CLOSURE`**: six `bundled_module` entries.
4. **`run_state_lib.py` `_FLAT_LAYOUT_BUNDLED_BIN_FILES`**: six entries.
5. **`AGENTS.md`**: six `cp` lines in **both** layout blocks (`.github/skills/bin/` and `.claude/skills/quality-playbook/bin/`).
6. **`repos/setup_repos.sh`**: six `cp` lines.

The full 57-test bundle-drift guard suite (`test_install_manifest_no_drift`, `test_install_skill`, `test_install_skill_bundle_completeness`, `test_installed_skill_guardrail`, `test_setup_repos_bundle_parity_089n`) is green — the guards cross-check the sites against each other, so their passing proves **no site was missed**.

## Count-pin before/after (legitimate growth)
`INSTALL_CLOSURE` count-pin: **63 → 69** (+6). This is genuine bundle growth — six new mandatory Feature H modules — documented in place in the test, not a fixture dodge. The prior value (63) came from instruction 010's `doc_classification.py` addition (62 → 63).

## Confirmation a fresh install ships all six
A `install_skill.install(source_root=<repo>, target=<temp>)` into a throwaway directory reported `event=install_complete status=success files_copied=69` with `event=smoke_check check=bundled_modules status=passed`, and all **6/6** persona modules were present in the installed `bin/`:
```
persona_catalog.py OK · persona_orchestration.py OK · persona_grounding.py OK
persona_merge.py OK · persona_apply.py OK · requirements_render.py OK
```
So an adopter who installs the skill now actually receives Feature H.

## Dependency closure note
The six are dependency-closed at the install root: `persona_grounding` imports `doc_classification` + `citation_verifier` (both already bundled); `persona_merge` and `persona_apply` import `requirements_render` (bundled here); the others are stdlib-only. All resolve via the bundled `bin/` closure, so a bundled persona pass imports cleanly at the adopter install root.

## Underspecified / notes
- The six modules are not yet *invoked* by any adopter-facing entry point (SKILL.md / phase_prompts / run_playbook do not yet call the persona pass) — bundling makes them *available*; wiring the persona pass into the pipeline invocation is a separate concern (the interview/validation invocation), out of this bundling slice's scope. Flagged so the orchestrator knows bundling ≠ pipeline-invocation.

## Next action expected from orchestrator
After this, only the **integrated umbrella Council** across the composed Feature H pipeline and the **broader 1.6.0 acceptance/release testing** remain before ship. Also still open (earlier-recorded): wiring the persona pass into the pipeline invocation; setting OD-9 from instruction 019's data (0 spurious grounded adds); Feature-G non-plaintext-contract → FORMAL_DOC wiring; chi/express Slice-1 coherence-fixture regeneration; the drop/selective-revert BUG-reference re-point hardening.
