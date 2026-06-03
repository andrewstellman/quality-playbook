# Changelog

All notable changes to the Quality Playbook will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.8] — 2026-06-03

Windows ship-readiness + harness UX + methodology hardening. Adds Windows as a first-class supported platform for both Mode A (claude) and Mode B (codex via run_playbook), closes the cp1252-on-Windows hazard surface at all three sites, formalizes the Worker self-Council protocol as load-bearing methodology, graduates the AUDIT-table invariant test pattern to standard mechanism, and lands the v2 blind CVE benchmark methodology under `Security Research/CVE_BENCHMARK_METHODOLOGY_v2.md`. Next is v1.6.0 (Requirements Review — feature-complete).

### Windows compatibility (180 chain, 10 followups)

- **180** Windows harness compatibility — fork/tmp/start_new_session/fcntl substitutions for cross-platform process management.
- **180-followup-2** sys.argv reinvocation broken on Windows — fix.
- **180-followup-3** signal.SIGHUP AttributeError + fail-fast spawn verification.
- **180-followup-4** npm/npx Windows shutil.which lookup + fail-fast scope extension.
- **180-followup-5** TUI curses fallback + comprehensive Windows sweep.
- **180-followup-6** signal.SIGKILL not available on Windows + complete signal sweep + manifest "RUNNING" check.
- **180-followup-7** launch-failure diagnosability — traceback + breadcrumbs + env snapshot in `launch_error.txt`.
- **180-followup-8** diagnosability hardening — reattach + broad swallow + coverage sweep + TUI surfacing.
- **180-followup-9** launch-log consolidation + mtime-cached TUI reads.
- **180-followup-10** `_pid_alive` Windows divergence + git core.longpaths defensive flag.
- **181** Cross-platform support requirements documented in `docs/design/QPB_Test_Harness_1.5.7_Design.md` Section O + `reference_docs/33`.
- **182** psutil migration — pid_alive / kill_process_tree / process_create_time / pid_alive_with_identity / wait_for_process now use psutil instead of platform-specific shims. Fixes the latent Windows kill-tree-only-leader bug where descendant processes were orphaned after a tree-kill.
- **183** CREATE_NO_WINDOW flag swap — `popen_kwargs_detached()` uses `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP` instead of `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP` so background spawns don't flash console windows on Windows. Propagates to child processes inheriting creationflags.
- **184** Residual `_pid_alive` divergence sweep — 4 sibling modules (watchdog.py, runner.py, status.py, manager.py) had local `_pid_alive` definitions using POSIX `os.kill(pid, 0)`; all consolidated to alias `_platform.pid_alive`. First **AUDIT-table invariant test pattern** — `NoResidualPidAliveDivergenceTests` codifies the sweep as a maintenance contract via a runtime `is`-identity check across all 5 alias sites.

### Windows cp1252 hazard surface — all three sites closed

The Windows cp1252 default codec ate three orthogonal failure modes across this release. All three sites now carry explicit `encoding="utf-8", errors="replace"` (or the equivalent), AND each landed with its own AUDIT-table invariant test, AND the three sites together are documented as a design contract in `docs/design/QPB_Test_Harness_1.5.7_Design.md` Section O ("Windows cp1252 hazard surface"). Future PR reviewers reference Section O before approving any new `subprocess.run` / `open(text=True)` site.

- **185** Site (a) — WRITE from Python to stdout/stderr: high-bit Unicode replaced with 7-bit ASCII in QPB print paths (FINDING-27); facts parser accepts BOTH ASCII and emoji verdict markers for backward-compat (FINDING-28); `PYTHONIOENCODING=utf-8` set in child env (FINDING-29).
- **189** Site (b) — READ from external log files: `bin/qpb_harness.py` orchestrator log read + harness.log read gain `errors="replace"` + `UnicodeDecodeError` catch (FINDING-44). 14-site sweep audit across `run_playbook.py` + `install_skill.py` + `harness/{facts,runner,plan_runner,prepare}.py` (FINDING-45).
- **190** Site (c) — WRITE from Python to subprocess stdin: `bin/run_playbook.py:2186-2197` `subprocess.run(text=True)` gains explicit `encoding="utf-8"` + `errors="replace"` for the codex/cursor stdin path (FINDING-46). 14-entry per-file AUDIT table across `bin/run_playbook.py` + `bin/harness/**/*.py` (FINDING-47). Fixes the U+2265 (≥) crash that masked operator-visible Windows codex Mode B failures.

### Harness UX

- **186** Removed `ABANDONED_STARVED` terminal state + the 1-hour PENDING auto-kill deadline introduced in 165. For sequential `pool=1` plans with long-running rows, the deadline killed runs before the pool could free a slot. Replaced with operator-visible signals: status shows `pending Nh Mm` waiting time + collector heartbeat-age health (FINDING-31a/b); explicit `qpb_harness force-run <run-NN>` CLI subcommand bypasses pool acquire (FINDING-33); TUI `E` keybinding force-executes the highlighted PENDING row out of pool after a confirmation modal (FINDING-32).
- **186-followup-1** Pending-duration display gaps in CLI grouped view + TUI detail state cell; force-run drive-bys.
- **187** NEW `include_iterations: bool = False` plan-row field. When `true`, the Mode A launch prompt drops the "Do not run the iteration strategies" exclusion clause so QPB runs all 4 iteration strategies (gap/unfiltered/parity/adversarial) per its documented default. Default-False preserves the 106 acceptance-plan behavior. **Empirical caveat (2026-06-03 blind CVE benchmark A/B):** iterations made detection WORSE in 2/2 directly-comparable rows — the adversarial pass over-dismisses real findings when call-graph reasoning is shallow. Default `include_iterations: false` for security plans is now the documented recommendation.
- **188** `kill <harness-run>` now cancels PENDING runs (previously skipped them). New `CANCELLED` terminal state via `cancel_pending_run` helper; the collector's PENDING-retry loop and `_try_acquire_pool_slot` both check `state != "PENDING"` so cancellations can't silently resurrect. Status / TUI render CANCELLED rows in their own section. `HarnessRunSummary.cancelled` field + `C={cancelled}` column added across CLI status, TUI runs table, and curses TUI summary — same 6-site shape as the 113 BLOCKED-fix pattern.

### Methodology

- **Worker self-Council protocol** (Protocol 1) — formalization of the "Parallel-Agent reviewers" Council flavor with stricter discipline. Documented in `ai_context/DEVELOPMENT_PROCESS.md`. Used since 186-followup-1; has demonstrably caught ship-blockers across 187 / 188 / 189 / 190 that a single-reviewer pass would have shipped (187's manifest round-trip persistence gap, 188's `_try_acquire_pool_slot` race, 188's 6-site `CANCELLED` display gap, 190's em-dash-IS-in-cp1252 boundary distinction). Codifies: 3 panelist charters in parallel via Task tool, each Write-to-file artifact at `Reviews/v<NNN>_self_council/panelist_<X>_<charter>.md`, synthesis to `Reviews/v<NNN>_self_council/synthesis.md`, FIX-REQUIRED iterates in-branch BEFORE filing v1 to Cowork.
- **AUDIT-table invariant test pattern** (v1.5.7 184+) — graduated from "pattern" to "standard mechanism" after 3 confirmed reuses (184 `_pid_alive` divergence, 189 log-read encoding, 190 subprocess stdin encoding). When a defect-class shape is observed for the third time, file an exhaustive-sweep invariant test alongside the targeted fix. Documented in `ai_context/DEVELOPMENT_PROCESS.md`.
- **Blind CVE benchmark methodology v2** — `Security Research/CVE_BENCHMARK_METHODOLOGY_v2.md` extends the v1 framework with three orthogonal failure modes (token-level / structural / training-data contamination), explicit gathering whitelist+blacklist, two-gate verification (regex scan + blind-reviewer localization), baseline calibration requirement, and per-repo audit-trail discipline. Triggered by the 2026-06-02 Contamination Council finding that the v1-gathered `docs_gathered/` corpus was structurally contaminated; the prior cited "wins" (CASE-005 avro, CASE-009 evervault-go) were disqualified for cite until rebuilt. The 7 CVE-benchmark-eligible corpora were rebuilt via parallel blinded forward-gatherers and both gates passed. The 2026-06-03 blind benchmark run produced 2/7 DETECTED (setuptools CASE-001 + evervault-go CASE-009) — first methodologically-trustworthy blind security wins.

### Other

- **Worker queue infrastructure:** `ai_context/DEVELOPMENT_PROCESS.md` adds Worker self-Council protocol + AUDIT-table invariant pattern sections.
- **`ai_context/DEVELOPMENT_CONTEXT.md`** + **`ai_context/TOOLKIT.md`** currency pass for 180-190 work.
- **Plan files:** `harness_plans/security_blind_v2_rebuild.json` (7-row blind CVE benchmark, all `include_iterations: true`) + `security_blind_v2_no_iter.json` (A/B comparison arm, `false` on every row); `windows_codex_smoke.json` (Windows codex Mode B 1-row smoke test).
- **`bin/harness/requirements.txt`** — runtime deps for harness (build + psutil + textual + windows-curses with `sys_platform=='win32'` marker). Install via `python3 -m pip install -r bin/harness/requirements.txt` before firing harness runs on a fresh machine.
- **`Security Research/`** new artifacts: `CVE_BENCHMARK_METHODOLOGY_v2.md`, `Gatherer Prompt Template.md`, `CVE_BENCHMARK_REBUILD_RESULTS_2026-06-02.md`.

### Known issues at ship time

- **Windows codex Mode B with small models** may fail the Phase 1 → Phase 2 gate due to limited reasoning depth (observed with `gpt-5.4-mini` on chi 2026-06-03). The harness behaves correctly — child runs cleanly post-190, abort discipline records `ABORTED_PHASE` with actionable reason — but the model can't produce sufficient Phase 1 artifacts. Use `gpt-5.5` or `gpt-5.4` for actual quality runs. Documented in `ai_context/DEVELOPMENT_CONTEXT.md` "Gotchas" + "Current known issues" sections.
- **codex CLI model availability varies by account tier.** `gpt-5.3-codex` is restricted on ChatGPT-account Codex tiers as of codex-cli v0.136.0; use `gpt-5.5` (universal default) or `gpt-5.4-mini` (cheaper). Plan files now use universally-available models.
- **Iterations are net-negative for blind-CVE security work.** Default `include_iterations: false` for security plans. Opt-in only where breadth-search semantics outweigh the over-dismissal risk.
- **3 CVE benchmark targets missing corpora** (CASE-003 keras, CASE-004 CPython tarfile, CASE-006 Budibase) — fresh blind forward-gathering needed to fill the benchmark to 10. Tracked for v1.5.8.x or v1.6.0.
- **avro / spark scope-selection ambiguity** in the v2 blind benchmark — when the corpus describes multiple subsystems with equal depth, QPB picks one to drill into and may pick the wrong one. Tracked for v1.5.8.x or v1.6.0.
- **evervault-go `relay.go` plain-HTTP CA finding** surfaced by Gate 2 in the v2 corpus rebuild — could be a real new security finding or a gatherer-phrasing artifact. Spot-check pending.

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
- **F-5b** — *(later removed in v1.5.7 089z — the wrapper conflicted with the post-089x "no-args is safe" invariant; the canonical `python3 -m bin.run_playbook <target>` and `python3 bin/run_playbook.py <target>` forms are sufficient. Kept here as historical record of the v1.5.7 development arc.)* `run_playbook.sh` wrapper installed into each target repo via `setup_repos.sh`. Was the third invocation form alongside `python3 -m bin.run_playbook` and direct-script invocation; auto-discovered the QPB clone by walking up from its own location and fell back to `$QPB_HOME`.
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

Test suite at the 089q milestone: **1,661 OK** (dual-env) + gate **298 OK** — up from 1,359 / 257 at the D1-D6 milestone (+343 across the F-fixes, the 089f–089q arc including the TDD-credibility arc, and self-audit + Windows closures). The post-089q polish arc (089s–090a, below) took it to **1,704 OK** + gate **298 OK** at the final pre-tag state.

### 089s–090a — install-doc currency, distribution channels, self-describing scripts, banner

The post-089q arc closed the remaining v1.5.7 polish: adopter-install-doc currency, the pip + npm distribution channels, the self-documenting `bin/` tree, and the attribution-banner placement.

- **089s / 089t — install + launch doc currency.** The install procedure now documents all **8** supported `--ai-tool` values (`cursor`, `claude`, `copilot`/`github`, `continue`, `codex`, `windsurf`, `cline`, `aider` — up from the earlier 4); the installing agent **self-identifies its own tool** and passes `--ai-tool` itself (the adopter's one-line prompt is sufficient — they never name the tool or the target subdirectory); the installed skill is **auto-discovered** by the agent (no need to open `SKILL.md`); and a run can be **scoped to a phase subset** across sessions ("Run phases 1 to 3…").
- **089u / 089v / 089w — pip + npm distribution channels.** The Quality Playbook is now installable without cloning, as an **application / scaffolder** (not an importable library): `uvx quality-playbook install --into <repo> --ai-tool <tool>` / `pipx run quality-playbook …` (ephemeral one-shot) or `pip install quality-playbook` (persistent) on the Python side; `npx quality-playbook init --ai-tool=<tool>` on the Node side (a thin shim over the same Python installer — Python 3.10+ still required at runtime). The channel sets `QPB_CHANNEL` (`pip` / `npm`) so the Phase-0 validator's remediation is channel-aware. The npm surface uses `--ai-tool` (an earlier `--loop` draft was dropped). `bin/build_channel_package.py` stamps the `pyproject.toml` / `package.json` versions from `SKILL.md` so the manifests can't drift.
- **089x — every `bin/**/*.py` script is safe + self-describing on no-args.** Running any `bin` script with no arguments prints a purpose banner (what it is + its role in a playbook run + an attribution footer) and exits 0 with no side effects; `--version` was added to the CLIs; `install_skill.py` no longer auto-installs into cwd and `run_playbook.py` no longer auto-starts a self-audit on a bare invocation (the self-run moved behind an explicit target / `--operator-invoked`). A meta-test enforces the invariant (mutation-bites a removed `__main__`).
- **089y — validator zero-deps + channel hygiene.** Dropped the stale `tiktoken` / `yaml` env-checks from `qpb_validate.py` — adopters need **zero third-party Python packages**, and a properly-scaffolded fresh install now validates `status=ok`. Excluded `__pycache__` / `*.pyc` from both the wheel/sdist and the npm tarball (added `.npmignore` + staging-time exclusion), enforced by a mutation-verified "no compiled artifacts ship" test.
- **089z — `run_playbook.sh` wrapper removed (reverts F-5b).** The per-target shell wrapper `setup_repos.sh` installed was removed: it conflicted with the 089x no-args-safe invariant and was benchmark-harness-only. The canonical run forms (`python3 -m bin.run_playbook <target>` and `python3 bin/run_playbook.py <target>`) are sufficient; `setup_repos.sh` no longer installs it.
- **090a — full attribution banner on CLI no-args + `--help`.** The full 80-wide attribution banner now appears on the no-args invocation and at the top of `--help` for the user-facing CLIs (it had been reserved for install-success + run start/end). Library modules keep the lightweight one-line footer. The 089l banner-drift guard stays green (banner text unchanged).

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
