# Quality Playbook v1.5.10 — Implementation Plan

*Companion to `QPB_v1.5.10_Design.md`. **Scope expanded 2026-06-18** from "SKILL.md trim only" to a repo-hygiene release: folder cleanup + SKILL.md relocation to root + the trim + an end-to-end test. Phases below are sequenced so each is independently committable (checkpoint discipline) and so the riskiest step (relocation) lands on its own clean checkpoint.*

*The trim, relocation, and cleanup (Phases A–D) have landed and pushed. The remaining work to actually ship the release is the **Close-out checklist** directly below — that is the authoritative "what's left" view; Phases A–E are the detailed record.*

*Terminology note (2026-06-19): the end-to-end check is a **regression + integration test**, not a "recall run." It integrates arunner with QPB and checks both for regressions in one pass. `run_playbook` is being **retired** and is not used by it. Earlier drafts of this doc used "recall run/baseline" — a misapplied science/public-health term; the correct quality-engineering terms are regression test and integration test.*

*All source mutations are executed by the **Claude Code worker** (which polls `~/Documents/QPB/runner/1.5.9`). Cowork authors this plan, the worker brief, runs Council, and verifies — Cowork does not edit QPB source directly.*

*Branch: `1.5.10`, cut from `1.5.9` HEAD.*

*Council reviewed (2026-06-18, three panels) — all FIX-REQUIRED items folded in below, tagged `[Council X]`. Full synthesis: `~/Documents/AI-Driven Development/Quality Playbook/Reviews/QPB_v1.5.10_Council_Synthesis.md`.*

---

## Close-out checklist (remaining work to ship v1.5.10)

*Plain-language list of everything left, agreed across the 2026-06-18/19 sessions. The trim, relocation, and cleanup (Phases A–D below) already landed.*

1. **Clean working tree** — *[DONE]* all trim/relocation/cleanup/doc changes committed; `git status` clean.

2. **arunner × QPB integration + regression test** — confirm the trimmed/relocated skill still finds bugs *and* that arunner correctly drives QPB's phases, in one test that exercises both systems.
   - **Vehicle: arunner runs QPB's phases natively** (FR-61–65, landed on the arunner `fr-61-65-impl` branch). Each QPB phase is an arunner step; each step's prompt comes from a file in `phase_prompts/`; a **deterministic gate** between steps checks the phase produced its required artifacts (`validate_phase_artifacts`, exit-code only).
   - **`run_playbook` is not used.** It is being retired — we do not use it again.
   - **Repos:** the standard benchmark set (chi / virtio / express), installed fresh via `setup_repos.sh` so the skill under test is exactly v1.5.10.
   - **Grading is mechanical:** the regression-test scorer (`bin/regression_replay.py`) scores the bugs found against the pinned ground truth. The pass/fail verdict does not depend on Claude's judgment.
   - **Independent Council** reviews the result; all evidence (the plan, gate outcomes, the score vs. the pinned ground truth) is pasted. (`run_playbook` is retired, so there is no fresh pre-trim *run* to diff — the baseline is the pinned historical bug list.)
   - If a phase reference fails to load or the score drops materially: identify the extraction at fault, move it back into SKILL.md or strengthen the load pointer, re-run.

3. **Land the three queued worker fixes** (worker instructions, each gated by self-Council):
   - **054** — `.github/workflows/publish.yml` (CI/CD publish-on-tag; see item 7).
   - **055** — lineage / orientation refresh (wakecycle → arunner language).
   - **056** — Clojure quality-gate fix (Design Workstream 6): switch language detection from first-match to dominant-language-by-count; add Clojure to the three tables.

4. **Verify the Clojure fix on a real Clojure project** — the 056 unit tests use file-tree fixtures (no runtime). Separately, run QPB once against the actual Clojure project (operator-run; Clojure toolchain installed) and confirm the gate now detects `clj` and accepts `test_functional.clj`.

5. **Version bump + single source of truth** — bump 1.5.8 → 1.5.10 **and** consolidate where the version is stored to one canonical source (two at most).
   - Today the version appears in several places (SKILL.md frontmatter, `pyproject.toml`, `package.json`, `plugin.json`, `marketplace.json`, `quality_playbook_cli`, README). `build_channel_package.py --stage` already stamps the packaging files **from** SKILL.md frontmatter, so SKILL.md is the de-facto source for those.
   - Make SKILL.md frontmatter the **single canonical source**; have everything else read from it or be stamped from it — including `quality_playbook_cli/__init__.py` and the README header (stop hard-coding the version in either). If the Python package and the skill genuinely cannot share one source, two is the cap.
   - This matters because the CI/CD publish workflow's version-equality guard is only trustworthy when one source feeds every stamp.

6. **CHANGELOG entry** for v1.5.10.

7. **CI/CD finalize (Design Workstream 5)** —
   - publish.yml landed (054) and Council-reviewed.
   - **Get publish.yml onto `origin/main` first** — trusted publishing can't be exercised until the workflow file is on the default branch.
   - One-time operator registration: PyPI trusted publisher, TestPyPI pending publisher, npm trusted publisher, and create the `release` GitHub Environment — names must match exactly.
   - Run the layered test plan from `docs/RELEASE_PUBLISHING.md`: local dry-run → stage-only on CI → TestPyPI → npm.

8. **Fill the README Quick-Start token line with real numbers** from the integration+regression test's token reporting (arunner FR-65). It currently carries a placeholder, which must not ship.

9. **Umbrella Council** on the whole release (Self-Review Protocol 1 panels + the defensive-sweep charter).

10. **Tag v1.5.10 + push + verify** — `git ls-remote origin 1.5.10` and the tag before claiming shipped (workspace rule).

11. **awesome-copilot re-submission** shipping the trimmed canonical SKILL.md directly.

12. **Update CLAUDE.md: add checkable, mechanical gates** to avoid the pitfalls from this release cycle. Not restatements of existing rules (those already existed and were ignored) — gates that can be mechanically checked:
    - Before claiming a deliverable is "what you asked for," paste its literal content and the original request in the same place, so the claim is checkable against the artifact. *(Pitfall: handed over an arunner plan that just wrapped `run_playbook` and described it as native.)*
    - **Disclose substitutions** — whenever a fallback, wrapper, or shim stands in for the real thing, say so explicitly. *(Same pitfall.)*
    - **Treat an on-screen warning as a hard stop**, not advisory. *(Pitfall: the "installed skill is stale" warning printed on every run and I ran past it.)*
    - Before claiming success, **write down and run the exact command that would disprove the claim.** *(This is literally what caught the wrapper: `grep command <plan> | cut` returned `bin.run_playbook`.)*
    - **Honesty rule:** the claim I make about a deliverable must be independently true of its contents.
    - **Correct misapplied terminology early** (e.g. "recall run," "cells") — use real quality/software-engineering terms; the wrong word anchors the wrong concept.
    - *Status: a Council vetted the diagnosis and confirmed aspirational restatements won't bind; wording is drafted; applying to CLAUDE.md awaits operator go-ahead.*

13. **Source terminology cleanup (worker lane).** QPB source bakes in made-up vocabulary the operator has flagged: `bin/regression_replay.py` + `metrics/regression_replay/` ("replay" is not a quality-engineering word), and "cell record" / "recall" (as a test name) inside the scorer and `metrics/regression_replay/SCHEMA.md`. Rename the script + dir (e.g. `regression_test.py` / `metrics/regression_test/`) and purge "replay" / "cell" / "recall-as-test-name" from QPB source, repointing the importers and tests. Worker-lane (it's source) + Council. Low priority but on the list so the clean-base goal is real.

**Adjacent (arunner repo — not the QPB v1.5.10 source release, tracked here for completeness):** FR-61–65 implemented on `fr-61-65-impl` (instruction 002, local) and the spec on `fr-61-65-spec` (001, local), both awaiting operator review/merge to arunner `main`; and committing the arunner `runner/` folder (an earlier sandbox mount restriction blocked it).

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

## Phase E — arunner × QPB integration + regression test (run_playbook retired)

*This is the close-out checklist's item 2, in detail. It is a **regression + integration test**: it checks the trimmed/relocated skill for behavioral regressions and simultaneously integrates QPB with arunner's new native phase orchestration. `run_playbook` is **not** used — it is being retired.*

- **E1. Vehicle.** Use arunner (FR-61–65, landed on `fr-61-65-impl`) to run QPB's phases natively: each phase is an arunner step, prompts come from `phase_prompts/`, and a deterministic gate between steps runs `validate_phase_artifacts` (exit-code only). No `run_playbook`.
- **E2. Environment.** Install the skill fresh into the standard benchmark repos (chi / virtio / express) via `setup_repos.sh` so the skill under test is exactly v1.5.10 (avoids the stale-install failures seen earlier). Confirm runtime SKILL.md resolution from the new **root** layout and per-phase `references/` loads at phase boundaries. **[Council C2]** Confirm QPB self-audit still classifies Skill/Hybrid post-relocation.
- **E3. Mechanical grading.** Score bugs found with the regression-test scorer (`bin/regression_replay.py`) against the pinned ground truth (the recorded historical bug list — there is no fresh pre-trim run, `run_playbook` being retired), and compare REQUIREMENTS quality + Phase 6 verdict accuracy. The verdict is computed, not judged.
- **E4. Independent Council** reviews the result with all evidence pasted (plan, gate outcomes, score, diff vs. baseline).
- **E5. On failure** (a reference fails to load, or the score drops materially): identify the offending extraction; move it back to SKILL.md or strengthen the load pointer; re-run.
- **Dependency:** the arunner-native vehicle requires FR-61–65 (done) plus a follow-up worker instruction that builds the QPB-native plan (phases as steps, `phase_prompts/`, gates = `validate_phase_artifacts`).
- **CHECKPOINT COMMIT E:** `test(v1.5.10): arunner x QPB integration+regression — <result summary>`

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
| 1 | Branch `1.5.10` + baseline green | A | DONE |
| 2 | Folder cleanup (git-rm cruft + gitignore) | A | DONE |
| 3 | SKILL.md content audit table | B | DONE |
| 4 | Mechanical extraction + drift reconciliation | B | DONE |
| 5 | Reference-resolves validator + test | C | DONE |
| 6 | Token-ceiling ratchet (32K → ~12K) | C | DONE |
| 7 | SKILL.md relocation to root + rewire | D | DONE |
| 8 | Package build ships real files | D | DONE |
| **Close-out (remaining):** | | | |
| 9 | arunner × QPB integration + regression test (arunner-native; run_playbook retired) | E / close-out 2 | PENDING — needs follow-up worker instruction (FR-61–65 done) |
| 10 | Land worker fixes 054 (publish.yml) / 055 (lineage) / 056 (Clojure gate) | close-out 3 | PENDING |
| 11 | Verify Clojure fix on a real Clojure project | close-out 4 | PENDING — operator-run, needs toolchain |
| 12 | Version bump 1.5.8→1.5.10 + single source of truth | close-out 5 | PENDING |
| 13 | CHANGELOG entry | close-out 6 | PENDING |
| 14 | CI/CD finalize (publish.yml on main + registration + layered test plan) | close-out 7 | PENDING |
| 15 | README Quick-Start real token numbers | close-out 8 | PENDING — blocked on item 9's token reporting |
| 16 | Umbrella Council (Self-Review) | close-out 9 | PENDING |
| 17 | Tag v1.5.10 + push + verify (`git ls-remote`) | close-out 10 | PENDING |
| 18 | awesome-copilot re-submission | close-out 11 | PENDING |
| 19 | Update CLAUDE.md with checkable mechanical gates | close-out 12 | PENDING — Council-vetted; awaits operator go |
| 20 | Source terminology cleanup (rename replay/cell/recall in source) | close-out 13 | PENDING — worker lane; low priority |

---

*End of v1.5.10 Implementation Plan. Design in `QPB_v1.5.10_Design.md`. Successor backlog (security) in `QPB_v1.5.11_Design.md` + `QPB_v1.5.11_Implementation_Plan.md`.*
