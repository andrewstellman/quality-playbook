# Changelog

All notable changes to the Quality Playbook will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.7] — 2026-05-13

Research-grade hardening release. Last v1.5.x; next is v1.6.0 (Requirements Review).

### Six deliverables shipped

- **D1 — Phase 2 gate-failure artifact preservation.** When the Phase 2 gate aborts a run (EXPLORATION.md too short, role-map violation, schema mismatch), the cell's `quality/` directory is renamed to `quality.gate-failed-<UTC-ts>/` instead of being rolled into `previous_runs/`. A `GATE_FAILURE.md` marker captures the violation message, phase group, cell name, timestamp, runner version, and model identifier. Adopters running benchmark sweeps now retain partial Phase 1-3 artifacts for diagnostic inspection. Scoped to Phase 2 gate failures only (Phase 3+ gate failures don't trigger preservation). Composes cleanly with v1.5.6 cluster 049 role-map auto-recovery.
- **D2 — Role-map query cookbook.** New `references/role_map_queries.md` documents the v1.5.6 role-map schema's actual shape (list-of-records with top-level `files` array, not `roles` keyed-by-role object) plus canonical jq queries for the four common operations (filter by role, count by extension, list skill-tools with `skill_prose_reference`, find disallowed-prefix violations). Phase 2 prompt cites the cookbook; agents no longer construct jq paths from memory.
- **D3 — Centralized log emission at `quality/logs/<run-id>/`.** Runner-owned log artifacts (playbook log, `run_state.jsonl`, `RUN_MODE.md`, control_prompts transcripts) now land at `quality/logs/<run-id>/`, with a `quality/logs/latest` symlink updated at run completion. `--logs-flat` CLI flag (or `QPB_LOGS_LEGACY=1` env var) restores v1.5.6 byte-identical paths for adopter tooling that hasn't migrated. `bin/run_state_lib.resolve_run_state_path` provides a three-source fallback chain (latest symlink → most-recent timestamp → legacy). The `run_start` event now carries `run_id` + `log_layout` discriminator fields. Agent-emitted (`quality/results/run-<ts>.json`) and gate-emitted (`quality/results/quality-gate.log`) artifacts remain at legacy locations as v1.5.7.x carry-forward (FS-2 + FS-3); the runner subset is centralized.
- **D4 — `metrics/` directory formalization.** New `metrics/` sub-directories (`regression_replay/`, `calibration/`, `bootstrap_recall/`, `cross_version_trends/`, `sdlc_defects/`) each with a `README.md` documenting file-format conventions, schema versioning, and producer/consumer scripts. New `bin/metrics_reconstruction.py` walks the cell roster and emits per-quarter aggregates (`bootstrap_recall/<YYYY>-<Q>.json`) + per-benchmark trajectories (`cross_version_trends/<benchmark>.json`). Provides forward-compat scaffolding for v1.7 SPC machinery.
- **D5 — `SKILL.md` trim.** Pure-move of Phase 1, Phase 2, and Phase 6 body content from `SKILL.md` to new `references/phase1_exploration_guide.md`, `references/phase2_generation_guide.md`, `references/phase6_verify_guide.md`. `SKILL.md` falls from 66,332 BPE → 26,162 BPE (60.6% reduction; below the <30K target with 3,838 BPE margin). Body content preserved verbatim — no rewording, no consolidation. Phase prompts (`phase_prompts/phase[126].md`) updated to load the new reference files. 3 new regression tests pin the trim invariants (token-count under threshold, all pointers resolve, phase-prompt reference-load).
- **D6 — Council resilience: roster, persistence, adopter doc.** Active Council roster updated to `(claude-opus-4.7, gpt-5.5, claude-sonnet-4.6)` (was `(claude-opus-4.7, gpt-5.4, gemini-2.5-pro)`; gemini-2.5-pro was silently dropped by `gh copilot` during the v1.5.6 sweep). New `bin/qpb_config.py` provides `~/.qpb/config.json` per-operator persistence (stdlib `json` — no PyYAML dep) with `qpb config show/set-runner/set-roster/unset` sub-commands. New `--council-roster` CLI flag with three-source resolution (CLI → config file → built-in default). New `references/runners_and_models.md` adopter doc explains the four runners, why the Council-of-Three exists, and how to override the roster. Council launch architecture refactor (resilience under runner-detected unavailability) deferred to v1.5.7.x as sub-phases 6b + 6d.

### Tests and infrastructure

- Test suite: **1,324 tests OK** (up from 1,231 at v1.5.6, +93 net new across D1-D6).
- New test files: `bin/tests/test_phase2_abort_preservation.py` (D1), `bin/tests/test_metrics_reconstruction.py` (D4), `bin/tests/test_run_playbook_log_layout.py` (D3), `bin/tests/test_council_config.py` (D6a), `bin/tests/test_runners_and_models_doc.py` (D6e), `bin/tests/test_qpb_config.py` (D6c), `bin/tests/test_skill_md_size.py` (D5).

### v1.5.7.x carry-forwards (documented in phase synthesis docs)

- **Phase 4 F-1**: `qpb_version` inference Source-ordering spec clarification.
- **Phase 5 FS-1**: end-to-end test for the centralized-layout migration (current FS-1 tests bite at helper level only; end-to-end via `run_one_phased` against a synthetic cell is deferred).
- **Phase 5 FS-2**: agent-written `run_metadata.json` path migration (requires SKILL.md edit which Phase 7 D5 has now done; FS-2 update can land cleanly as a v1.5.7.x patch).
- **Phase 5 FS-3**: coordinated gate-log writer + runner-read-path migration (requires `.github/skills/quality_gate/quality_gate.py` + `phase_prompts/phase6.md` + runner-read changes as one atomic refactor).
- **Phase 6 sub-phase 6b**: Council launch architecture refactor — Council launches are currently agent-owned (per `phase_prompts/phase4.md`), not runner-owned; resilience requires multi-instruction refactor.
- **Phase 6 sub-phase 6d**: failure-recovery template wiring (paired with 6b's hard-fail path).
- **Phase 7 trim**: further reduction (Phase 3/4/5 + Recheck/Convergence sections; estimated achievable floor ~18-20K BPE).
- **Phase 7 Council non-blocking notes**: heading duplication in references files, tiktoken-absent silent-skip message, mechanical byte-equality test pinning move-fidelity.

## [1.5.1] — 2026-04-22

### Fixed

- **Phase 5 writeup stub regression.** `bin/run_playbook.py::phase5_prompt` now carries a MANDATORY HYDRATION STEP with a BUGS.md → writeup field map, a worked BUG-004 example, and a per-writeup confirmation checklist that prohibits empty backticks, empty diff fences, and angle-bracket placeholders. This closes the Phase 5 failure mode observed on `bus-tracker-1.5.0`, where the playbook produced skeletal writeups that passed the legacy gate.

### Added

- **Quality-gate writeup hydration checks.** `check_writeups` now fails when any writeup contains one of five template-sentinel strings (``"is a confirmed code bug in ``"``, ``"The affected implementation lives at ``"``, ``"Patch path: ``"``, ``"- Regression test: ``"``, ``"- Regression patch: ``"``) or when a ` ```diff ` fence is present but contains no `+` / `-` lines other than file headers.

### Changed

- **Case-insensitive diff fence detection.** Quality gate recognises ` ```diff `, ` ```Diff `, and ` ```DIFF ` uniformly, so inline-diff presence and content checks can't disagree on whether a fence exists. Previously a writeup with a mixed-case fence would trip a confusing "no inline fix diffs" FAIL despite containing a visible unified diff.

## [1.5.0] — baseline

Initial release under Semantic Versioning. Features include the formal-docs pipeline (plaintext + `.meta.json` sidecars), the phase orchestrator, the quality gate with §10 mechanical checks, the Council-of-Three semantic citation check, the tier taxonomy, and the challenge-gate iteration-coverage invariant. Pre-1.5.0 history lives in `docs_gathered/01_README_project.md` under "What's new in v1.4.x".
