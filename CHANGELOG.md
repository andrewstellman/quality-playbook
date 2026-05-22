# Changelog

All notable changes to the Quality Playbook will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.7] — 2026-05-21

Research-grade hardening release. Last v1.5.x; next is v1.6.0 (Requirements Review — feature-complete).

### Six deliverables shipped

- **D1 — Phase 2 gate-failure artifact preservation.** When the Phase 2 gate aborts a run (EXPLORATION.md too short, role-map violation, schema mismatch), the cell's `quality/` directory is renamed to `quality.gate-failed-<UTC-ts>/` instead of being rolled into `previous_runs/`. A `GATE_FAILURE.md` marker captures the violation message, phase group, cell name, timestamp, runner version, and model identifier. Adopters running benchmark sweeps now retain partial Phase 1-3 artifacts for diagnostic inspection. Scoped to Phase 2 gate failures only (Phase 3+ gate failures don't trigger preservation). Composes cleanly with v1.5.6 cluster 049 role-map auto-recovery.
- **D2 — Role-map query cookbook.** New `references/role_map_queries.md` documents the v1.5.6 role-map schema's actual shape (list-of-records with top-level `files` array, not `roles` keyed-by-role object) plus canonical jq queries for the four common operations (filter by role, count by extension, list skill-tools with `skill_prose_reference`, find disallowed-prefix violations). Phase 2 prompt cites the cookbook; agents no longer construct jq paths from memory.
- **D3 — Centralized log emission at `quality/logs/<run-id>/`.** Runner-owned log artifacts (playbook log, `run_state.jsonl`, `RUN_MODE.md`, control_prompts transcripts) now land at `quality/logs/<run-id>/`, with a `quality/logs/latest` symlink updated at run completion. `--logs-flat` CLI flag (or `QPB_LOGS_LEGACY=1` env var) restores v1.5.6 byte-identical paths for adopter tooling that hasn't migrated. `bin/run_state_lib.resolve_run_state_path` provides a three-source fallback chain (latest symlink → most-recent timestamp → legacy). The `run_start` event now carries `run_id` + `log_layout` discriminator fields. Agent-emitted (`quality/results/run-<ts>.json`) and gate-emitted (`quality/results/quality-gate.log`) artifacts remain at legacy locations as v1.5.7.x carry-forward (FS-2 + FS-3); the runner subset is centralized.
- **D4 — `metrics/` directory formalization.** New `metrics/` sub-directories (`regression_replay/`, `calibration/`, `bootstrap_recall/`, `cross_version_trends/`, `sdlc_defects/`) each with a `README.md` documenting file-format conventions, schema versioning, and producer/consumer scripts. New `bin/metrics_reconstruction.py` walks the cell roster and emits per-quarter aggregates (`bootstrap_recall/<YYYY>-<Q>.json`) + per-benchmark trajectories (`cross_version_trends/<benchmark>.json`). Provides forward-compat scaffolding for v1.7 SPC machinery.
- **D5 — `SKILL.md` trim.** Pure-move of Phase 1, Phase 2, and Phase 6 body content from `SKILL.md` to new `references/phase1_exploration_guide.md`, `references/phase2_generation_guide.md`, `references/phase6_verify_guide.md`. `SKILL.md` falls from 66,332 BPE → 26,162 BPE at the Phase 7 trim (60.6% reduction). Post-trim, instruction 058 (A-11) added the layout-aware `PYTHONPATH=<install_root>` Phase 1 invocation guidance to `SKILL.md`, re-growing it to **27,943 BPE (cl100k_base)** — still below the <30K design target, with a ~2,057 BPE margin (the trim-time figure was 26,162 / 3,838-margin; this corrects it for the A-11 re-growth, per the instruction-061 Council Lens-1 dissent). Body content preserved verbatim — no rewording, no consolidation. Phase prompts (`phase_prompts/phase[126].md`) updated to load the new reference files. 3 new regression tests pin the trim invariants (token-count under the 29,000 BPE ceiling — widened from 28,000 in instruction 062 to restore meaningful headroom; all pointers resolve; phase-prompt reference-load).
- **D6 — Council resilience: roster, persistence, adopter doc.** Active Council roster updated to `(claude-opus-4.7, gpt-5.5, claude-sonnet-4.6)` (was `(claude-opus-4.7, gpt-5.4, gemini-2.5-pro)`; gemini-2.5-pro was silently dropped by the Copilot CLI during the v1.5.6 sweep — observed under the then-active `gh copilot` extension, still missing under the new standalone `copilot` CLI per 089f). New `bin/qpb_config.py` provides `~/.qpb/config.json` per-operator persistence (stdlib `json` — no PyYAML dep) with `qpb config show/set-runner/set-roster/unset` sub-commands. New `--council-roster` CLI flag with three-source resolution (CLI → config file → built-in default). New `references/runners_and_models.md` adopter doc explains the four runners, why the Council-of-Three exists, and how to override the roster. Council launch architecture refactor (resilience under runner-detected unavailability) deferred to v1.5.7.x as sub-phases 6b + 6d.

### Ship-readiness fixes (F-1 through F-8)

Surfaced by a Council-of-Three root-cause review on the D1-D6 surface; all 8 landed before tag-move:

- **F-1** — Install/version detection now uses canonical six-layout markers (e.g., `.github/skills/SKILL.md`, `.claude/skills/quality-playbook/SKILL.md`) instead of accepting any root `SKILL.md` as proof of install. Closes the v1.5.6 bootstrap failure mode where an unrelated root SKILL.md hijacked install detection.
- **F-2** — D1 abort-preservation log ordering: the preserved-location hint now fires AFTER the directory rename, not before, so operators see an actionable path.
- **F-3** — `setup_repos.sh` archives existing target directories as `.tar.gz` with a `--replace` opt-in flag rather than silently deleting them. Adopters re-running setup no longer lose prior `quality.gate-failed-*/` directories or local edits.
- **F-4 amendment** — `check_no_workspace_dir` gate check also fires on EMPTY `workspace/` directories (not just populated ones); closes a Phase 5 finalization gap.
- **F-5b** — `run_playbook.sh` wrapper installed into each target repo via `setup_repos.sh`. Third invocation form alongside `python3 -m bin.run_playbook` and direct-script invocation; auto-discovers the QPB clone by walking up from its own location and falls back to `$QPB_HOME`. Adopters invoking from inside their target repo no longer need to know the QPB clone path.
- **F-6** — Runner hint clarity on gate-failure-preservation state. When the preservation directory exists, the runner surfaces its path explicitly at exit.
- **F-7** — Phase 3 BUGS.md / patches consistency gate check. Catches Phase 3 finalization where BUGS.md lists confirmed bugs without matching regression-test or fix patches.
- **F-8** — Phase 5 prompt + gate enforce exact `## Verdict\n<PASS|FAIL>` shape. Closes a verdict-emission inconsistency observed in earlier benchmark runs.

### "What just happened" UX contract (adopter-visible)

New behavior at every phase boundary. The playbook now ends every phase (and every full run) with a Markdown-rendered chat block of this shape:

```
## What just happened

<plain-English interpretation of what the agent just did — NOT a copy
of quality/PROGRESS.md, but an interpretive layer over it>

### What to do next

<concrete next prompt or shell command>
```

The decision tree mapping run state → block content lives at `references/what_just_happened.md` (13 run states: Phase 1-5 individual, code-only, Phase 2 abort, error-state, pass-process / fail-recall, baseline complete, iteration N, all iterations, recheck). Adopters running on weak models (Cursor auto-mode, etc.) will see explicit "pass-process / fail-recall" framing surfacing the documented "your model is too weak for real three-pass review" failure mode in plain English, rather than having to derive that diagnosis from gate WARNs.

### Tests and infrastructure

- Test suite: **1,359 tests OK** (up from 1,231 at v1.5.6, +128 net new across D1-D6 + F-fixes + "What just happened" contract + self-audit closures).
- Gate tests: **257 OK** (unchanged from v1.5.6 baseline).
- New test files: `bin/tests/test_phase2_abort_preservation.py` (D1), `bin/tests/test_metrics_reconstruction.py` (D4), `bin/tests/test_run_playbook_log_layout.py` (D3), `bin/tests/test_council_config.py` (D6a), `bin/tests/test_runners_and_models_doc.py` (D6e), `bin/tests/test_qpb_config.py` (D6c), `bin/tests/test_skill_md_size.py` (D5), `bin/tests/test_what_just_happened.py` (UX contract).
- New combined-test surface: `test_progress_md_two_form_architecture_not_in_drift` gives both PROGRESS.md schemas (automation form via `write_progress_md`; deliverable form agent-maintained) a single shared test for future drift detection.

### Self-audit closures (ship-validation)

Three independent ship-validation runs (Codex bootstrap on a fresh clone of the post-D1-D6 `v1.5.7` tag + chi/cobra Copilot benchmarks) surfaced 12 self-defects; all 12 closed before final tag-move:

- **BUG-001 + BUG-002**: install/version detection hijacked by unrelated root `SKILL.md` (closed by F-1 hardening).
- **BUG-003**: installer smoke check ignored new bundle members (now mirrors the install-bundle list as a single source of truth).
- **BUG-004**: missing-install warning omitted 3 of 6 canonical fallback locations (now lists all six).
- **BUG-005**: `write_progress_md()` schema vs `references/phase1_exploration_guide.md` "drift" reframed as **two distinct schema forms** sharing the same filename (automation form vs. deliverable form) — closed via the combined two-form not-in-drift test.
- **BUG-006**: iteration prompt omitted `references/iteration.md` load directive.
- **BUG-007**: operator guidance inconsistently narrowed the six-layout fallback across SKILL.md / TOOLKIT.md / verification / review_protocols / challenge_gate (now consistent).
- **Q1 + Q5**: gate now detects Code projects from artifact shape when role map absent; SKIP diagnostics distinguish "Code-not-applicable" from "role-map-missing".
- **Q2**: Phase 2/3 prompts now explicitly require schemas.md §3.10 fields (`role`, `divergence_type`) in manifests.
- **Q3**: severity case canonical (uppercase `HIGH` / `MEDIUM` / `LOW`); Phase 3 prompt + schema + gate now agree.
- **Q4**: gate diagnostic distinguishes playbook phases from skill-derivation passes.

### Integration Council validation

Final release-gate review (instruction 040) substituted for the canonical Council-of-Three Council with three independent reviewers (Codex CLI + Cursor + Claude Code sub-agent) reviewing the cumulative `main..1.5.7` diff (84 commits, ~78 files, ~12K insertions). 2-of-3 reviewers completed (Cursor skipped by operator); strict-consensus floor adjusted to 2-of-2. 6 strict-consensus findings closed across orientation-doc currency (Cowork-direct), source-file fixups (instruction 041), and a P0 schemas.md §11.2 disclaimer removing the no-longer-canonical `workspace/` layout from the data contract. Synthesis at `Quality Playbook/v1.5.7_runner/outputs/040-integration-council.md`.

### Known limitations

- **Phase validator-invocation contracts are prose-enforced (Phase 1 + Phase
  6 observed empirically; Phase 2 + Phase 5 same structural shape).** Phase
  1/2/5 require the agent to invoke `validate_phase_artifacts` and quote the
  verbatim `RESULT: VALIDATION PASSED (phase N)` line; Phase 6 requires the
  `quality_gate.py` + fresh-context auditor verdict. Agents are prose-required
  to comply but it is not mechanically enforced. Empirically: codex desktop
  performed in-session Phase 6 verification rather than dispatching the
  mandated fresh-context sub-agent (2026-05-18), and reported Phase 1 PASS
  while producing an EXPLORATION.md the validator would have FAILed
  (2026-05-18 self-bootstrap — validator not invoked, or its FAIL ignored).
  Claude Code Task-tool dispatch + the Copilot CLI Mode B (then the
  deprecated `gh copilot` extension, now the standalone `copilot` CLI
  per 089f — both shapes have been observed compliant) comply correctly.
  Operators should check for the verbatim verdict lines; if absent, do not
  treat the verdict as load-bearing. Structural enforcement is v1.6.x scope
  (Slice 0 for Phase 1/2/5 subprocess attestation; Slices 1+2 for Phase 6) —
  see `docs/design/QPB_v1.6.x_Phase6_Structural_Enforcement_Proposal.md`.

### 089f — Copilot CLI migration (GitHub deprecated `gh copilot` 2025-10-25)

Migrated all five Copilot CLI subprocess sites + the Phase 0 validator remediation advice from the deprecated `gh copilot` extension to the standalone `copilot` CLI ([github/copilot-cli](https://github.com/github/copilot-cli)). Both CLIs work during the GitHub-announced deprecation grace period; the new `bin/copilot_resolver.py` auto-detects which is on `PATH` and routes accordingly (preference: standalone `copilot` first, deprecated `gh copilot` fallback, fail-fast remediation message if neither). Flag mapping shimmed transparently (`--allow-all` vs `--yolo`; `-p`/`--prompt`/`--model` unchanged). Phase 0 validator remediation advice updated to recommend the new install routes per platform (`brew install copilot-cli` on macOS, `winget install GitHub.Copilot` on Windows, `curl -fsSL https://gh.io/copilot-install | bash` on Linux, npm `npm install -g @github/copilot`) with the legacy `gh extension install github/gh-copilot` form retained as fallback. Adopter impact: zero behavior change for users still on `gh copilot`; users with `copilot` installed transparently route there. Active prose (README, AGENTS.md, ai_context/, references/, agents/, v1.5.7 design docs) reflects the new canonical form with parenthetical legacy-form notes for the grace period.

### 089g–089j — resolver hardening, Windows portability, pre-tag cleanup, install banner

Four close-out changes after the 089f migration:

- **089g — resolver test PATH-independence.** The `copilot_resolver` routing test no longer depends on a Copilot CLI being on the host `PATH` (mocks detection so the suite passes under a hermetic `PATH`). Test-only; no production change.
- **089h — portable `latest.txt` run pointer (Windows symlink, W-B).** `quality/logs/` always writes a cross-platform `latest.txt` (the current run-id) alongside the best-effort `latest` symlink. On Windows the symlink needs elevated privilege / Developer Mode; on failure the runner writes `latest.txt`, emits an informational note (not a warning), and `resolve_run_state_path` reads `latest.txt` as a resolution source. Run resolution is unaffected with or without the symlink. Refines D3.
- **089i — pre-tag cleanup (4 fixes).**
  - **W-A — layout-aware install freshness check.** No more false "installed bundle stale" warning on a correct `install_skill.py` install. The check now validates against only the detected layout's manifest (previously it unioned the `install_skill` + `setup_repos` manifests, flagging every adopter install for benchmark-only files it legitimately lacks). Genuinely-incomplete installs are still flagged.
  - **True-UTC run-ids.** The run-id directory name is now true UTC (matching the archive dir + `run_state.jsonl` `ts`); the `Z` suffix is now honest (previously local time stamped with `Z`).
  - **Python 3.10+ floor.** Documented as the minimum; the one `assertNoLogs` test guarded with `skipUnless`.
  - **Doc-currency.** Finding-catalog count comment corrected and now self-guarding (a test asserts it equals `len(FINDING_CATALOG)`).
- **089j–089l — install attribution banner.** `install_skill.py` prints an 80-wide Quality Playbook / Andrew Stellman / GitHub-URL / tagline / Apache-2.0 banner at the **end** of a successful install, on stderr, leaving the stdout `event=` stream untouched (the `event=intro` / `event=install_complete` contract is intact; banner is success-path only). The AGENTS.md install procedure instructs the AI agent to **close its install reply by displaying the banner verbatim**, so the attribution is visible in the primary agent-driven install flow — not only to terminal users (089k closed the gap where an agent relayed stdout and never surfaced the stderr banner). A drift-guard test keeps the banner identical between `install_skill.py` and `AGENTS.md`. Tagline: *"AI code review is good. Quality engineering is better. Because code that looks right can still do the wrong thing."*

### 089m–089q — TDD-credibility arc + benchmark-parity + install-message wording

The 089m-089q sequence closes a credibility gap surfaced by the 2026-05-21 benchmark runs: a run could record `RESULT: GATE PASSED` with **zero empirically-executed** TDD red→green cycles — the regression tests reasoned about, not actually run — and the gate gave it the same verdict as a fully-proven run. The arc turns "GATE PASSED on inspection-only TDD" into "the gate requires real execution evidence."

- **089m — gate WARN on `NOT_RUN` receipts (#326 cheap half).** When one or more TDD red/green receipts are first-line `NOT_RUN`, the gate emits a WARN naming the count and pointing at `quality/RUN_TDD_TESTS.md`. `NOT_RUN` is an honest, legitimate state (an environment that genuinely cannot build) so this is WARN, never FAIL — the gate still PASSES; the WARN just surfaces that the empirical red→green proof did not happen.
- **089n — `setup_repos.sh` bundle parity.** `repos/setup_repos.sh` (the benchmark-harness installer) is brought into parity with `install_skill.py::_bundle_files()`: removed three adopter-parity over-bundles (`AGENTS.md`, `ai_context/AI_ORCHESTRATION_PATTERNS.md`, `LICENSE.txt` — files a real adopter never gets pre-placed) and added the three under-bundled A-26 modules (`run_state_lib.py`, `validate_phase_artifacts.py`, `qpb_config.py`). The benchmark now tests the same bundle adopters get. A parse-based parity guard test prevents future drift.
- **089o — TDD overclaim FAIL + probe-first env contract (#329).** A `RED`/`GREEN` first-line tag asserts the test was actually executed; a receipt body that admits non-execution under that tag is an **overclaim** and now FAILs. A run with confirmed bugs must capture a test-runner probe (`<tool> --version`, exit code) to `quality/results/phase5_env.log`; a missing probe FAILs, and a `NOT_RUN` receipt contradicted by a probe that shows the runner *was* available also FAILs. This closes the `NOT_RUN` loophole 089m's WARN could not catch (the gson run mislabeled 15 by-inspection receipts `RED`/`GREEN`).
- **089p — recap "TDD execution status" augmentation + online-resolution steer.** `references/what_just_happened.md` gains a cross-cutting augmentation: regardless of run state, if the gate log carries a TDD-not-executed signal the recap surfaces it in plain English ("verdicts reasoned, not observed") with an in-chat retry hint. The phase prompts gain an online-resolution steer — run the test runner in default online mode (no pre-emptive `--offline`), retry online before concluding `NOT_RUN`.
- **089q — scope + narrow the overclaim markers, require execution evidence, version-gate the probe contract.** Council fix-up: the 089o overclaim markers are narrowed to unambiguous self-admissions and scanned only in the agent-authored summary region — a legitimately-executed `RED` whose runner transcript genuinely says "cannot compile" (the canonical red-phase case) no longer false-FAILs. A `RED`/`GREEN` receipt must carry a positive execution signature (a `Command:`/`Exit code:` line or runner transcript) when the probe shows the runner available, else it FAILs as overclaim-by-omission. The `phase5_env.log` requirement is version-gated so pre-1.5.7 archived/replayed runs (which never produced it) WARN rather than FAIL.
- **AGENTS.md install next-step wording.** The post-install next-step now tells the operator to launch by saying *"Run the Quality Playbook on this project"* rather than to open the installed `SKILL.md` themselves — the agent auto-discovers the skill; the operator never needs to read `SKILL.md`.

### Cross-platform validation (macOS + Windows; real RED→GREEN across Java/Go/Python)

v1.5.7 was **directly validated** with genuine, empirically-executed TDD across three language/runner stacks: **Java/Maven** (gson, macOS), **Go** (chi, macOS, codex), and **Python/pytest** (click, Windows). Every cell probed its test runner, ran it for real, and produced real RED→GREEN evidence (Maven `BUILD FAILURE`→`BUILD SUCCESS`, `go test`, pytest) with the gate PASSED. This supersedes the earlier "Windows untested / infrastructure-blocked" framing — Windows is now a directly-validated platform, not a future-release candidate. Mode A (Claude Code — natural-language install + run) and Mode B (`run_playbook.py` + the `copilot` CLI) both reach Phase 6 verdicts; the fresh-context Phase 6 auditor enforces the no-fabrication contract on Windows. Known Windows note: the `quality/logs/latest` symlink needs Developer Mode — handled gracefully via the portable `latest.txt` pointer (089h).

Test suite at tag: **1,661 OK** (dual-env) + gate **298 OK** — up from 1,359 / 257 at the D1-D6 milestone (+343 across the F-fixes, the 089-series including the TDD-credibility arc, and self-audit + Windows closures).

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
