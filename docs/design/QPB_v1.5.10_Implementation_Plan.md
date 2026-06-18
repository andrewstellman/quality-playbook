# Quality Playbook v1.5.10 — Implementation Plan

*Companion to `QPB_v1.5.10_Design.md`. **Scope expanded 2026-06-18** from "SKILL.md trim only" to a repo-hygiene release: folder cleanup + SKILL.md relocation to root + the trim + an arunner regression run. Phases below are sequenced so each is independently committable (checkpoint discipline) and so the riskiest step (relocation) lands on its own clean checkpoint.*

*All source mutations are executed by the **Claude Code worker** (which polls `~/Documents/QPB/runner/1.5.9`). Cowork authors this plan, the worker brief, runs Council, and verifies — Cowork does not edit QPB source directly.*

*Branch: `1.5.10`, cut from `1.5.9` HEAD.*

*Council reviewed (2026-06-18, three panels) — all FIX-REQUIRED items folded in below, tagged `[Council X]`. Full synthesis: `~/Documents/AI-Driven Development/Quality Playbook/Reviews/QPB_v1.5.10_Council_Synthesis.md`.*

---

## Sequencing rationale

Cleanup first (lowest risk, shrinks the surface), then the trim (mechanical, pattern proven), then the relocation (highest blast radius — lands last on a known-green base so a regression is unambiguously attributable). The arunner regression run gates the whole thing.

---

## Phase A — Branch + folder cleanup (lowest risk first)

- **A0.** Cut branch `1.5.10` from `1.5.9` HEAD. Confirm `bin/tests/` is green on the fresh branch (baseline).
- **A1.** For each cruft path in the design's audit table, grep the live source tree (exclude `repos/`) to confirm nothing imports/reads it.
- **A2.** **Safety check:** read `bin/build_channel_package.py`; confirm it does NOT stage the repo-root `.github/skills/quality_gate/` into `_bundle/`. *(Council A: PASSES — `stage()` copies from the skill-folder `_bundle_source_root`, never repo-root; 61 files, zero from `.github`. Confirm still true before removing.)* If it does → reclassify as build input, STOP, report.
- **A2a. [Council A1 — FIX-REQUIRED] `quality/audits/` carve-out.** `bin/tests/test_192_audit_log.py:15-16` and `test_schemas_audit_191.py:137-150` read `quality/audits/*.md` at repo root with **no skip guard**. A blanket `git rm --cached quality/` makes both tests FAIL on a fresh clone (NOT in Phase A's own run — working-tree copies persist after `--cached`; the break only surfaces on a clean checkout). **Fix:** keep `quality/audits/` tracked (gitignore `quality/` but un-ignore `!quality/audits/`), OR move those two files to `docs/audits/` and repoint the two tests. Verify by deleting the working-tree copies in a scratch clone and running both tests.
- **A2b. [Council A2 — CONCERN] `.github/skills/quality_gate/` coverage.** Its 9 test files are NOT duplicated in `bin/tests/` (dormant — canonical runner is `unittest discover bin/tests`; `.github/workflows/` empty). Before removal: check whether `bin/tests/` already covers `quality_gate.py` adequately; if the 9 strand unique cases, port them, else **explicitly state the accepted coverage loss in the commit message.**
- **A3.** `git rm -r --cached` the confirmed-cruft paths (`quality/` **except `quality/audits/`**, top-level `previous_runs/`, `spike/`, `.github/skills/quality_gate/`, and `metrics/classifier_verification.log` [Council A3]); add `.gitignore` rules. No history rewrite. *(Council A3: `reviews/` is process-evidence like `spike/`; leaving it tracked is a defensible inconsistency — operator may revisit, not blocking.)*
- **A4.** Run `bin/tests/` — green. **Plus:** run the two carve-out tests against a scratch clone (or after deleting working-tree copies) to prove the fresh-clone case is green, not just the local case.
- **CHECKPOINT COMMIT A:** `chore(v1.5.10): remove committed run-output + orphaned copies from tracking; gitignore (quality/audits carved out)`

## Phase B — SKILL.md content audit + extraction (the trim)

- **B1.** Produce the audit table: each SKILL.md section → STAYS / MOVES (new ref) / CONSOLIDATE (existing ref), with file:line → destination. (Design's token table is the starting point.) **[Council B7 — REQUIRED METHOD]** before tagging any section MOVES, grep `bin/tests/` for that section's distinctive strings; if a test pins inline content, tag the pinned sub-block STAYS and **name the pin test in the audit-table row.**
- **B1a. [Council B1/B2/B3 — FIX-REQUIRED] These blocks are STAYS (pinned), not movable detail — do NOT move them:**
  - **Phase 7 "canonical treatment" paragraph** (pinned by `test_skill_md_consistency_191.py:101-147` — requires "phase 7 is a phase"/"conversational"/"post-phase-6"/"do not skip" inline). Move only Phase 7 Parts 1-3 detail.
  - **Phase 5 end-of-phase block + its inverted STOP boundary** (SKILL.md:892-908; pinned by `test_phase_stop_inversion.py:69-73`, ≥3 inline floor — the others are at :694/:760). Move only the Phase 5 *body* (challenge gate, terminal gate, sub-gates ~777-890). Treat end-of-phase STOP blocks as STAYS for all of Phases 3/4/5.
  - **Mode A self-execution contract block** (SKILL.md:83-122; pinned by `test_mode_a_self_execution_contract.py:64-83`) and the **F21 Mode A/B asymmetry block** (SKILL.md:75-81; pinned by `test_mode_a_b_parity_documented.py:48-77`). Keep inline; move only the surrounding "How to run"/"How to Use" prose detail.
- **B2.** Mechanical extraction per the table. For CONSOLIDATE rows — **only `spec_audit.md` and `run_state_schema.md`** ([Council B4 — FIX-REQUIRED] `phase6_verify_guide.md` is NOT a consolidate target; Phase 6 is already a pointer, nothing to move) — **diff inline vs. existing reference first**, reconcile drift, then point — do not blind-append. Known drift to reconcile: `run_state_schema.md` is missing the Heartbeat/`qpb_phase` sentinel content (net-new) **and carries stale `schema_version` 1.5.6/1.5.7 → refresh to 1.5.8** [Council B6]; `spec_audit.md` has drifted "effective council" wording + is missing the Layer-2 semantic citation check (net-new). For MOVE rows, create new `references/phase5_reconciliation_guide.md`, `phase7_guide.md`, `recheck_mode.md`, `invocation_guide.md`.
- **B3.** Replace extracted sections with one-line pointers in the **existing dialect** ``See `references/<file>.md` `` ([Council B5] — matches `test_skill_md_size.py:135`'s pointer-resolves regex; do NOT introduce a second `Read references/...` dialect). Verify SKILL.md still reads top-to-bottom.
- **CHECKPOINT COMMIT B (one per extracted section is ideal, traceable to the audit table):** `refactor(v1.5.10): extract <section> to references/<file>.md`

## Phase C — Validator + token-ceiling update

- **C1.** `quality_gate.py` gains the reference-resolves invariant: scan SKILL.md's ``See `references/X.md` `` directives ([Council B5] — same regex as `test_skill_md_size.py:135`, NOT a new `Read` dialect), confirm each resolves; cycle detection.
- **C2.** Add a regression test asserting all ``See `references/X.md` `` directives resolve.
- **C3.** `bin/tests/test_skill_md_size.py`: ratchet the ceiling from 32K toward ~12K (empirical post-trim size + small buffer), with the rationale-doc-on-bump policy.
- **C4.** Run `bin/tests/` — green.
- **CHECKPOINT COMMIT C:** `feat(v1.5.10): reference-resolves validator + token-ceiling ratchet`

## Phase D — SKILL.md relocation to root (highest blast radius — lands on a green base)

- **[Council C — FRAMING CORRECTION] Root is ALREADY layout #1** in every runtime resolver (`benchmark_lib.SKILL_INSTALL_LOCATIONS[0]`, `run_playbook.SKILL_FALLBACK_GUIDE`, `test_skill_resolution_order.CANONICAL_ORDER[0]`, the `quality_gate` resolvers). So this is a **source-side resolution change, NOT a "new layout addition."** Do NOT reorder the canonical fallback lists (that breaks `test_skill_resolution_order`). The real change is where QPB's own canonical source physically lives + the source-side `_resolve_bundle_source_root`/`find_source_root` resolution.
- **D1. [Council C2 — re-pointed]** Before moving, verify repo-vs-adopter detection at **`quality_gate.py:6080-6085`** (`_phase4_project_type_from_artifact_shape`, which keys on `(repo_root/"SKILL.md").is_file()` + `references/`) — NOT just `run_playbook.py` bundle_dir. *(Council C: benign for QPB — it only fires when the Phase-1 role map is absent, and QPB self-audit always produces one; and Skill/Hybrid is more correct than Code. But confirm, and require the arunner run (Phase E) to confirm QPB self-audit still classifies Skill/Hybrid.)* Also confirm `run_playbook.py`'s `bundle_dir.name == "skills"` discriminator keys on path-shape, not root-SKILL.md absence (Council C: it does — safe).
- **D2.** `git mv` the real `SKILL.md` + `references/` from `plugins/quality-playbook/skills/quality-playbook/` to repo root. Replace the in-tree locations with **symlinks** back to root.
- **D3.** Source-side resolution update (NOT list-reorder): ensure `_resolve_bundle_source_root` (install_skill.py:259-270), `build_channel_package._bundle_source_root` (171-180), and `find_source_root` (install_skill.py:784) still resolve the now-symlinked in-tree SKILL.md (all gate on `.is_file()`, which follows symlinks — confirm). Touch `bin/run_playbook.py`, `scripts/install_skill.py`, `scripts/benchmark_lib.py`, `scripts/qpb_validate.py` only as resolution requires.
- **D3a. [Council C1 — FIX-REQUIRED] Two omitted `quality_gate.py` path-pin sets** also use `SCRIPT_DIR/".."/SKILL.md` and must be confirmed post-move + given regression assertions: `check_version_stamps` (**quality_gate.py:4331-4336**) and CLI `detect_skill_version` (**quality_gate.py:6584-6591**). (Reads succeed through the symlink; assert it.)
- **D4. [Council C3 — corrected]** `pyproject.toml` needs **NO change** — its globs target the staged `_bundle/` tree, not source. For `bin/build_channel_package.py`: `shutil.copy2` **already dereferences symlinks** (Council C4 verified empirically — staged files are real, not links), so no code change is needed for correctness. **[Council C4 — guardrail]** Add an anti-regression assertion that `_bundle/SKILL.md` is a real file (`not os.path.islink`) with content matching root SKILL.md; and do NOT introduce symlink-preserving copy variants (`copytree(symlinks=True)`, `copy(follow_symlinks=False)`, `cp -P/-a`).
- **D5.** Repoint `bin/tests/test_skill_md_size.py` `_SKILL_DIR` to root. Update only the resolution-order/install-layout tests whose path assertions actually change (`test_skill_resolution_order.py`, `test_install_layouts_pinned.py`, `test_phase0_validator_install_location_aware_090t.py`, `test_doc_drift.py`, `test_run_playbook.py`, `test_benchmark_lib.py`, `test_phase_prompts_externalized.py`) — **without reordering the canonical layout list.**
- **D6.** Build the package (`build_channel_package.py` + `python -m build`); inspect the built artifact contains a **real** SKILL.md (no dangling symlink) — mandatory gate.
- **D7.** Full `bin/tests/` suite green.
- **CHECKPOINT COMMIT D:** `refactor(v1.5.10)!: relocate canonical SKILL.md to repo root; symlink in-tree locations; source-side resolution + packaging guardrails`

## Phase E — arunner regression run

- **E1.** Via the polling worker, launch an arunner run exercising Phases 1–3 on 3–5 standard benchmark repos against the trimmed + relocated skill.
- **E2.** Confirm runtime SKILL.md resolution from the new root layout + per-phase `references/` loads at phase boundaries. **[Council C2]** Confirm QPB self-audit still classifies as Skill/Hybrid (not mis-detected post-relocation).
- **E3.** Compare bug recall + REQUIREMENTS quality + Phase 6 verdict accuracy vs the pre-trim baseline.
- **E4.** If recall drops materially or a reference fails to load: identify the offending extraction; move it back to SKILL.md or strengthen the load directive; re-run.
- **CHECKPOINT COMMIT E:** `test(v1.5.10): arunner regression — <result summary>`

## Ship Gate

- Council Self-Review Protocol 1, three panelists: (1) cleanup + audit-table completeness, (2) extraction + reconciliation correctness, (3) relocation + install-contract-preservation correctness — plus the defensive-sweep charter.
- Trimmed SKILL.md passes validator + ratcheted token test; full suite green; package builds with real files; arunner regression clean.
- **awesome-copilot re-submission:** regenerate the packet shipping the trimmed canonical SKILL.md directly; submit PR; iterate if rejected.
- Release prep: version stamps, CHANGELOG, README/TOOLKIT updates, tag + close-out per `DEVELOPMENT_PROCESS.md`.
- **Verify before claiming shipped:** `git ls-remote origin 1.5.10` (and the tag) per the workspace rule before reporting the release landed.

---

## Open work-items tracker

| # | Item | Phase | Status |
|---|------|-------|--------|
| 1 | Branch `1.5.10` + baseline green | A | PENDING |
| 2 | Folder cleanup (git-rm cruft + gitignore) | A | PENDING — needs build-staging safety check |
| 3 | SKILL.md content audit table | B | PENDING |
| 4 | Mechanical extraction + drift reconciliation | B | PENDING audit |
| 5 | Reference-resolves validator + test | C | PENDING |
| 6 | Token-ceiling ratchet (32K → ~12K) | C | PENDING extraction |
| 7 | SKILL.md relocation to root + rewire | D | PENDING — highest risk; verify repo-vs-adopter detection first |
| 8 | Package build ships real files | D | PENDING relocation |
| 9 | arunner regression run | E | PENDING all source work |
| 10 | Council Self-Review | Ship Gate | PENDING |
| 11 | awesome-copilot re-submission | Ship Gate | PENDING |
| 12 | Release ship steps + push/tag verification | Ship Gate | PENDING |

---

*End of v1.5.10 Implementation Plan. Design in `QPB_v1.5.10_Design.md`. Successor backlog (security) in `QPB_v1.5.11_Design.md` + `QPB_v1.5.11_Implementation_Plan.md`.*
