# Quality Playbook — Development Context

> This file is for AI assistants helping maintain and improve the quality playbook skill.
> It contains the project's architecture, benchmarking methodology, known issues,
> and improvement axes. Read this when working on the skill files themselves.
>
> The project accompanies the O'Reilly Radar article [AI Is Writing Our Code Faster Than We Can Verify It](https://www.oreilly.com/radar/ai-is-writing-our-code-faster-than-we-can-verify-it/).
> The README was coauthored with Claude Cowork.
>
> *Last updated: 2026-06-03 (v1.5.7 after 180-190 Windows compat + cp1252 trifecta + harness UX). For the full per-release changelog see `CHANGELOG.md`; for the curated evolution narrative (v1.3.13 → present) see `ai_context/VERSION_HISTORY.md`. This file is kept current with the skill's architecture, not its release log. Major changes since 167-177 (the prior currency pass): Windows harness compatibility (180 chain — 10 followups for fork/tmp/start_new_session/fcntl/SIGHUP/SIGKILL/npm/curses/diagnosability/`_pid_alive` divergence), cross-platform design docs (181 + Section O), psutil migration for process management (182 — fixes the latent Windows kill-tree-only-leader bug), CREATE_NO_WINDOW flag swap (183), residual `_pid_alive` divergence sweep (184 — first AUDIT-table invariant test pattern), the **cp1252-on-Windows hazard trifecta** (185 print output + 189 log reads + 190 subprocess stdin write — all closed), removal of the `ABANDONED_STARVED` deadline + addition of `force-run` UX (186), the `include_iterations` opt-in plan field (187), kill cancels PENDING runs + new `CANCELLED` terminal state (188), and the **Worker self-Council protocol** (Protocol 1) which has been load-bearing across 186-followup-1 / 187 / 188 / 189 / 190 — see `ai_context/DEVELOPMENT_PROCESS.md` for the formal definition. The 2026-06-02 Contamination Council audit + v2 docs_gathered methodology rebuild (under `Security Research/CVE_BENCHMARK_METHODOLOGY_v2.md` in the workspace) drove a separate blind-CVE-benchmark methodology hardening — see the v2 doc for the full Mode A/B/C framework and Gate 1 + Gate 2 verification.*

## How to read this doc

This file is the maintainer's map of the project. You rarely need all of it — load the section that matches your task:

- **Changing skill files / navigating the repo** → "Project structure", "How the skill works", "Making changes to the skill".
- **Running the tests / verifying a change** → "Project structure" (the *Running the tests* command block) and "Making changes to the skill".
- **Diagnosing a missed bug** → "Three improvement axes".
- **Running or interpreting benchmarks** → `ai_context/BENCHMARK_PROTOCOL.md` (run protocol, benchmark set, "Why bootstrap is a benchmark target", result interpretation, and the agent-capability table).
- **Release history / why a feature exists** → `ai_context/VERSION_HISTORY.md` (curated arc) and `CHANGELOG.md` (mechanical per-release log).
- **Open problems** → "Current known issues".

Each section is self-contained; jump to the heading you need rather than reading top-to-bottom.

## Project structure

```
quality-playbook/
├── AGENTS.md                          ← AI coding agent entry point (repo root)
├── SKILL.md                           ← The skill — full operational instructions for running the playbook
├── LICENSE.txt                        ← License terms
├── agents/                            ← Orchestrator agent files for autonomous runs
│   ├── quality-playbook-claude.agent.md   ← Claude Code orchestrator (single-level sub-agent model)
│   ├── quality-playbook.agent.md          ← Copilot / generic orchestrator
│   └── calibration_orchestrator.md        ← v1.5.5 spawn-and-resume orchestrator template for calibration cycles (Mode 1 autonomous driver per ai_context/CALIBRATION_PROTOCOL.md)
├── bin/                               ← Standard-library benchmark automation package
│   ├── __init__.py                    ← Package marker
│   ├── benchmark_lib.py               ← Shared helpers (versioned from repos/_benchmark_lib.sh)
│   ├── run_playbook.py                ← Main runner — positional args are target directories (python3 bin/run_playbook.py); v1.5.5 wires validate_no_source_edits into _finalize_iteration as the Phase 5 source-edit guardrail
│   ├── run_state_lib.py               ← v1.5.5 run-state instrumentation: read/parse/validate helpers (read_events, last_in_progress_phase, validate_run_state_file, validate_phase_artifacts, validate_no_source_edits) plus writers (append_event, write_progress_md)
│   ├── visualize_calibration.py       ← v1.5.5 four-chart cycle visualization (per-bug × cycle heatmap, lever × benchmark heatmap, recall trajectory, Mermaid lever-interaction graph)
│   ├── classify_project.py            ← v1.5.3 Phase 0 project-type classifier (Code / Skill / Hybrid)
│   ├── citation_verifier.py           ← v1.5.0 byte-deterministic citation excerpt extractor
│   ├── skill_derivation/              ← v1.5.3 Skill / Hybrid four-pass derivation + divergence detection
│   │   ├── __main__.py                ← CLI entry: `python3 -m bin.skill_derivation --phase {3,4} --part {a1..d,all} <target>`
│   │   ├── pass_a.py / pass_b.py / pass_c.py / pass_d.py   ← Phase 3 four-pass driver modules
│   │   ├── citation_search.py         ← Pass B fuzzy search with token-overlap pre-filter
│   │   ├── sections.py                ← Section enumeration + EXECUTION_MODE_KEYWORDS
│   │   ├── divergence_internal.py     ← Phase 4 Part A.1 internal-prose detection (precision-tuned in v1.5.3 Phase 5)
│   │   ├── divergence_prose_to_code_mechanical.py    ← Phase 4 A.2 Tier 1 mechanical
│   │   ├── divergence_prose_to_code_llm.py           ← Phase 4 A.3 Tier 2 LLM-driven (Hybrid only, resumable)
│   │   ├── divergence_execution.py    ← Phase 4 Part B archived-gate aggregator
│   │   ├── divergence_to_bugs.py      ← Phase 4 Part D.1 BUG production with §8.1 consolidation
│   │   ├── phase4_inbox.py            ← Phase 4 Part D.2 inbox + triage_batch_key backfill
│   │   └── curate_requirements.py     ← v1.5.3 Phase 5 Stage 5A curated REQUIREMENTS.md generator
│   └── tests/                         ← Stdlib-only tests for the runner package (662 tests at v1.5.3)
├── pytest/                            ← Local stdlib-only shim so python3 -m pytest works without installs
├── references/                        ← Reference files read during specific phases
│   ├── challenge_gate.md              ← False-positive detection challenge gate (v1.4.3+)
│   ├── constitution.md                ← Guidance for drafting the quality constitution
│   ├── defensive_patterns.md          ← Forensic inversion of defensive code (try/except, null guards)
│   ├── exploration_patterns.md        ← Pattern library for Phase 1 exploration
│   ├── functional_tests.md            ← Functional-test generation reference (all languages)
│   ├── iteration.md                   ← Iteration strategies (gap, unfiltered, parity, adversarial)
│   ├── orchestrator_protocol.md       ← Shared hardening rules imported by both agent files (v1.4.4+)
│   ├── requirements_pipeline.md       ← Requirements derivation and post-review reconciliation
│   ├── requirements_refinement.md     ← Coverage / completeness refinement pass
│   ├── requirements_review.md         ← Pre-finalization requirements review
│   ├── review_protocols.md            ← Three-pass code review protocol and regression test conventions
│   ├── run_state_schema.md            ← v1.5.5 event taxonomy + cross-validation rules + format invariants for the per-cycle quality/run_state.jsonl event log
│   ├── schema_mapping.md              ← tdd-results.json / recheck-results.json schema reference
│   ├── spec_audit.md                  ← Council of Three spec audit protocol
│   └── verification.md                ← 45 self-check benchmarks for Phase 6
├── .github/                           ← Installed-copy layout used inside target repos
│   └── skills/
│       ├── SKILL.md                   ← Installed skill entry point
│       ├── references/                ← Installed references bundle
│       ├── quality_gate.py            ← Symlink → quality_gate/quality_gate.py (stable invocation path)
│       └── quality_gate/              ← Gate script package (sole mechanical gate since v1.4.5; bash retired)
│           ├── __init__.py            ← Re-exports public API
│           ├── quality_gate.py        ← Mechanical validation (34 check_* functions at v1.5.3, 3000+ lines, Python 3.10+)
│           └── tests/
│               ├── __init__.py
│               ├── README.md          ← v1.5.3: documents `unittest discover` as the canonical runner (DQ-5-8)
│               ├── test_quality_gate.py  ← 215 stdlib-only unit tests at v1.5.3
│               └── test_req_pattern.py   ← 6 stdlib-only unit tests
├── ai_context/                        ← AI-readable context files
│   ├── TOOLKIT.md                     ← For users' AI assistants (setup, run, interpret, recheck)
│   ├── DEVELOPMENT_CONTEXT.md         ← For maintainers' AI assistants (this file)
│   ├── DEVELOPMENT_PROCESS.md         ← How the QPB project itself is developed (mechanical procedures, rationale, open directions)
│   ├── VERSION_HISTORY.md             ← Curated release-evolution narrative (v1.3.13 → present); CHANGELOG.md has the mechanical per-release log
│   ├── IMPROVEMENT_LOOP.md            ← Methodology doc: how QPB applies QE to itself (verification dimensions, lever inventory, regression replay, SPC trajectory)
│   ├── CALIBRATION_PROTOCOL.md        ← 12-step Mode 1 (autonomous) / Mode 2 (operator-driven) protocol for driving a calibration cycle
│   ├── TOOLKIT_TEST_PROTOCOL.md       ← Release-gate review protocol for orientation docs (orientation-doc analog of Council-of-Three)
│   └── BENCHMARK_PROTOCOL.md          ← Clean-folder run protocol for contamination-free benchmarks; benchmark set, "Why bootstrap is a benchmark target", result interpretation, and the agent-capability table
├── repos/                             ← Benchmark repos and setup tooling
│   ├── setup_repos.sh                 ← Copies skill files into target repos
│   ├── _benchmark_lib.sh              ← Shell helpers shared by setup_repos.sh, run_tdd.sh, etc.
│   └── clean/                         ← Clean clones of benchmark repos
├── quality/                           ← Bootstrap artifacts (playbook run against QPB itself)
└── council-reviews/                   ← Council review briefings and responses (not distributed)
```

**Automation note:** benchmark automation lives in `bin/` and uses only the Python standard library so sandboxed AI agents can run it without creating a virtual environment or installing packages. The shell scripts remaining in `repos/` (`setup_repos.sh`, `_benchmark_lib.sh`, `run_tdd.sh`) handle repo setup and TDD plumbing — they no longer include a runner. The **test harness** (`bin/harness/`, run via `python3 -m bin.qpb_harness`) automates multi-repo/multi-runner runs and provides the status TUI — it is dev-only (excluded from the shipped skill); see "The test harness (`bin/harness`) + status TUI" below.

**Running the tests:**

```
# Benchmark runner + skill-derivation modules + run-state lib (1017+ tests at v1.5.5)
python3 -m unittest discover bin/tests
python3 -m pytest bin/tests/                                     # works under both runners

# Quality gate package (221 tests at v1.5.3 — 215 in test_quality_gate.py + 6 in test_req_pattern.py; v1.5.4+ adds gate-side tests for the regression-replay surface)
python3 -m unittest discover -s .github/skills/quality_gate/tests/ -p 'test_*.py'
```

The canonical runner for the gate suite is `unittest discover`,
not pytest — pytest fails on that directory due to a pre-existing
import-shadowing issue (sibling `__init__.py` + same-directory
`quality_gate.py` produces a copy of the FAIL global rather than a
reference). v1.5.3 DQ-5-8 documented this and locked the
acceptance gate to unittest discover; the `bin/tests/` suite
supports both runners. See
`.github/skills/quality_gate/tests/README.md` for the full
explanation. v1.5.4+ may revisit the import architecture
(backlog item B-8).

The local `pytest` package is a minimal shim around `unittest` so
`python3 -m pytest` works on plain Python 3.10+ with no external
dependencies.

## How the skill works

The quality playbook is a long-form instruction document (SKILL.md) that an AI agent reads and follows. It is designed to run one phase at a time, with the user driving each phase forward. Each phase runs in its own session with a clean context window, producing files on disk that the next phase reads.

**Phase 1 (Explore):** The agent explores the codebase using a three-stage approach — open exploration, quality risk analysis, and selected pattern deep-dives. Outputs: EXPLORATION.md with candidate bugs.

**Phase 2 (Generate):** The agent generates the Phase 2 artifact set under `quality/` from the exploration findings: REQUIREMENTS.md, QUALITY.md, CONTRACTS.md, COVERAGE_MATRIX.md, COMPLETENESS_REPORT.md, the four RUN_*.md review/execution protocols (RUN_CODE_REVIEW.md, RUN_INTEGRATION_TESTS.md, RUN_SPEC_AUDIT.md, RUN_TDD_TESTS.md), and a `quality/test_functional.<ext>` functional test file. **AGENTS.md is NOT a Phase 2 output** — it is generated by the orchestrator after Phase 6 completes; writing it during Phase 2 trips the source-edit guardrail.

**Phase 3 (Code Review):** Three-pass code review against HEAD. Regression tests for every confirmed bug. Generates patches.

**Phase 4 (Spec Audit):** Three independent AI auditors review the code against requirements. Triage with verification probes. Regression tests for net-new findings.

**Phase 5 (Reconciliation):** Close the loop — every bug tracked, regression-tested. TDD red-green cycle for all confirmed bugs. Writeups, fix patches, completeness report.

**Phase 6 (Verify):** Mechanical verification and 45 self-check benchmarks.

After each phase, the skill prints a prominent end-of-phase message telling the user what happened and what to say next. The user says "keep going" or "run phase N" to continue. This interactive protocol gives much better results than single-session execution because each phase gets the full context window.

**Iteration mode:** After the baseline run, the agent can run additional iterations using strategies defined in references/iteration.md. Each strategy re-explores the codebase with a different approach, then re-runs Phases 2-6 on the merged findings. Iterations typically add 40-60% more confirmed bugs.

**Recheck mode:** After the user fixes bugs, saying "recheck" triggers a lightweight verification pass. Recheck reads BUGS.md, checks each bug against the current source (reverse-applying fix patches, inspecting cited lines, optionally running regression tests), and writes results to `quality/results/recheck-results.json` and `quality/results/recheck-summary.md`. Takes 2-10 minutes instead of a full re-run. Does not find new bugs — only verifies previously found bugs.

## Three improvement axes

When the playbook misses a bug, the miss falls on one of three axes. Identifying which axis tells you what to fix:

### 1. Exploration rules

**Symptom:** The agent never looked at the code containing the bug.

**What to fix:** Exploration patterns in SKILL.md Phase 1, pattern applicability matrix, domain-knowledge questions. Or add a new iteration strategy that targets the unexplored area.

**Example:** The parity sub-type checklist was added to references/iteration.md because the parity strategy wasn't comparing resource lifecycle (setup vs. teardown) — it was only finding "obvious" parallel-path differences.

### 2. Iteration types

**Symptom:** The agent looked at the code but the bug wasn't found by any existing iteration strategy.

**What to fix:** Add a new iteration strategy to references/iteration.md that targets the failure mode. Each strategy exists because a specific class of bugs was being systematically missed.

**History:**
- **gap** (v1.3.44): Baseline only covered subset of codebase
- **unfiltered** (v1.3.44): Structured approach over-constrained exploration
- **parity** (v1.3.45): No strategy explicitly compared parallel code paths
- **adversarial** (v1.3.44): Conservative triage kept dismissing real bugs

### 3. Triage calibration

**Symptom:** The agent found the code, flagged it as a candidate, but dismissed it during triage.

**What to fix:** Triage rules in SKILL.md (evidentiary standards, "what counts as sufficient evidence"), the Demoted Candidates Manifest in references/iteration.md (tracks dismissed findings with re-promotion criteria), adversarial strategy evidentiary bar.

**Example:** Pydantic's AliasPath bug was found and dismissed THREE times before the adversarial strategy recovered it. The triage kept classifying it as a "design choice" because the behavior was "permissive." The fix was lowering the adversarial evidentiary bar: code-path trace + semantic drift is sufficient.

## Benchmarking methodology

The benchmarking methodology — the clean-folder contamination discipline, the benchmark set, why bootstrap is always a target, how to interpret bug counts, and the per-agent capability table — lives in **`ai_context/BENCHMARK_PROTOCOL.md`**. Read it before running or interpreting any benchmark.

Key points a maintainer should know without opening it:

- **Benchmark runs must be isolated.** No sibling runs visible to the agent, no pre-existing `quality/` in the target — or findings leak between runs and the tuning signal is corrupted.
- **Bootstrap (the playbook auditing QPB itself) is always in the active set.** It's the only target that catches the self-referential class of bug (the gate validating its own artifacts) and the only one we can verify every finding against our own intent. See `BENCHMARK_PROTOCOL.md` → "Why bootstrap is a benchmark target".
- **Model capability dominates results.** A weak model produces clean-looking artifacts and passes gates while finding zero real bugs (the pass-process / fail-recall failure mode). The per-agent capability table and the v1.5.7 `## What just happened` UX contract that surfaces this live in `BENCHMARK_PROTOCOL.md` → "Known agent behavior differences".
- **Bug counts vary between runs** (exploration non-determinism); compare across 5+ runs or use iteration cycles, and spot-check new versions against real source. See `BENCHMARK_PROTOCOL.md` → "Interpreting results".

## The test harness (`bin/harness`) + status TUI

The **test harness** (`bin/harness/`, driven by `python3 -m bin.qpb_harness`) automates running the playbook across multiple repos/runners and recording the results. It is a **dev/maintainer-only tool** — it is *excluded* from the shipped skill (the pip/npm channels and `install_skill.py` deliberately do not bundle `bin/harness/`), so adopters never see it. Open *this* doc (not the adopter-facing TOOLKIT.md) when you want to run or read a harness run.

### What a run is

You write one **plan file** (JSON) and run it. The harness creates one timestamped, self-contained **run folder** under `--runs-root`, clones each target repo into it, installs the skill, launches the AI CLI, re-runs the installed gate, grades against `expect`, and writes a `SUMMARY.md`. The default `--runs-root` is `./harness_runs/` (gitignored), so you usually don't need to pass it. Plan files live in `harness_plans/` (tracked, hand-edited).

```bash
python3 -m bin.qpb_harness run-plan harness_plans/<plan>.json
```

`run-plan` is **fire-and-forget**: it launches every run detached, writes `manifest.json` (with PIDs), spawns a detached background **collector** (reaps each run, runs facts+grade, writes `SUMMARY.md`) **and a `watchdog` daemon (172) that polls every 60s for orphaned RUNNING entries and re-fires `collect_harness_run` under file lock as a safety net**, and **returns immediately**. Check on it with `status`/`tui` (below); no terminal stays tied up. `python3 -m bin.qpb_harness collect <run-dir>` is a safe, idempotent manual reap if both the collector and watchdog ever die.

### Plan file format

Top level: `pools` (per-runner concurrency, e.g. `{"claude": 2, "copilot": 1, "codex": 1}`; runners not listed default to `1` per v1.5.7 174's pool-only model — there is no longer a separate global per-provider cap) and `runs` (an array; the array index identifies a run — there is no `id` field). Per-run fields:

- `repo`, `ref` — git URL + branch/tag/SHA (a SHA pins a bug-present commit).
- `runner` — `claude` / `copilot` / `codex` / `cursor`.
- `model` — e.g. `opus`, `gpt-5.4`, `gpt-5.3-codex`.
- `channel` — how the skill is installed into the target: `clone` (simplest), `pip-local-wheel`, or `npm-local-tgz` (the last two build a fresh local artifact and test the published-package install path).
- `mode` — `A` or `B` (see below; default `A`). **For `runner: codex` or `runner: cursor`, you MUST set `mode: B` explicitly** — Mode A is rejected at plan-parse time with a clear error pointing at this requirement (124 hardened: codex/cursor `exec` is single-turn and incompatible with Mode A's one-session-drives-all-phases shape).
- `parameters` — extra argv. **Mode A:** passed verbatim to the runner CLI (e.g. `["-c", "model_reasoning_effort=\"low\""]` spliced between `codex` and `exec`). **Mode B:** passed to `run_playbook.py`. Note that codex-CLI config overrides like `-c key=value` in a Mode B plan must use `--runner-extra-args "-c key=value"` because run_playbook itself doesn't recognize `-c` directly — this routing trap surfaced in the 2026-06-03 Windows smoke and is now in the gotchas list.
- `include_iterations` — `true` / `false` (default `false`). When `true`, the Mode A launch prompt drops the "Do not run the iteration strategies" exclusion clause so QPB runs all 4 iteration strategies (gap / unfiltered / parity / adversarial) per its documented default. **Empirical caveat from the 2026-06-03 A/B test** (blind CVE benchmark, security_blind_v2): iterations made detection WORSE in 2/2 directly-comparable rows (setuptools went DETECTED → MISSED when the adversarial pass dismissed the target as a false positive). Set `true` only for non-security work where the iteration strategies' "search broader" semantics outweigh the "argue against findings" risk. (187)
- `prompt` — override the Mode A launch prompt entirely (e.g. `"Run quality playbook phase 1."` for one-phase tests). Absent ⇒ the default. When `include_iterations: true` and `prompt` is absent, the iterations-enabled prompt is used; when `prompt` is set, it wins (operator override).
- `workspace_root` — point the run at an existing/shared target instead of cloning fresh (lets several pool=1 runs share one workspace, each running a different phase).
- `max_duration_s` — per-run timeout (default 7200s / 120 min).
- `expect` — a **flat** assertion map (a list value means "one of"); empty `{}` is an observational run (read the SUMMARY/verdicts, don't grade).

### Mode A vs Mode B (and which runner uses which)

- **Mode A** — the AI CLI drives all six phases itself in one session (the default full-pipeline prompt). This works for **claude** (`claude --print` sustains a multi-phase agentic loop). It does **not** work for **codex/cursor**, whose `exec`/`agent` invocations are single-turn and exit after one turn — so a Mode A codex run hedges and quits early.
- **Mode B** — `run_playbook` drives the phases, each phase its own clean-context session (QPB's recommended flow, and the way to run codex/cursor through the full pipeline). Mode B runs `run_playbook` from a **pristine `git worktree` at HEAD** (so an uncommitted/dirty QPB dev tree doesn't trip run_playbook's source-guard). `run_playbook` itself is intentionally not in the shipped bundle, so Mode B always uses the QPB clone's committed `run_playbook`.

### Monitoring a run

- **`python3 -m bin.qpb_harness status [<run-dir>]`** — table of recent runs (default `./harness_runs/`): per-state counts (`R` running / `D` done / `F` failed / `T` timed-out / `B` blocked / `AP` aborted-prep / `C` cancelled / `AB` aborted-phase / `P` pending), `progress` (`P<max>/P6`), last-activity, collector-alive, **watchdog-alive**. The `AS` (ABANDONED_STARVED) column was REMOVED in 186 alongside the deadline removal; the `C` (CANCELLED) column was ADDED in 188 alongside the new terminal state. PENDING rows additionally show `pending Nh Mm` waiting time so operators can decide whether to wait or `force-run` out of pool. (186 / 186-followup-1 / 188)
- **`python3 -m bin.qpb_harness status <run-dir>`** — per-repo drill-down: state, current phase + state + note, result, pid(live?), elapsed, last-activity. Post-175 every entry (RUNNING, PENDING, DONE) shows `repo` + `runner/model` from `plan.json`; per-run `status.json` / `invocation.json` contribute runtime state only.
- **`python3 -m bin.qpb_harness tail <run-dir>/run-NN [-f]`** — follow one run's output (`-f` = tail).
- **`python3 -m bin.qpb_harness tui [<run-dir>]`** — the live **Textual TUI** (optional `textual` dep; `--curses` is a no-dependency fallback). Three levels: runs list → per-repo detail (phase/state) → live output. Keys: ↑/↓ navigate, **Enter** drill in / watch output, **q/Esc** back, **`j`** toggle rendered ↔ raw JSON in the output view, **`c`** copy the current screen to the clipboard, scroll/mouse + follow-tail (jumps to newest; scroll up to read history). All screens auto-refresh every ~2s.
- **`python3 -m bin.qpb_harness tui --dump runs | detail | output [--dump-path <dir>] [--lines N] [--raw]`** — render a TUI page as plain text to stdout (no terminal/textual needed) — useful for scripting, logs, or having an AI inspect a page.

Claude `stream-json` output is rendered Claude-Code-style by default (per v1.5.7 173: `⏺` tool calls, `⎿` tool results with indented continuation, `━━━ session ended` terminal banner, `⟨thinking⟩` blocks, `::QPB::` phase markers preserved both bare-line and inline-in-tool_result); `--raw`/`j` shows the verbatim JSON. codex/copilot/run_playbook output is plain text and passes through unchanged.

### Reading the result

Each run folder holds per-run receipts (`status.json`, `invocation.json`, `facts.json`, `grading.json`, `stream.ndjson`, per-run logs) plus the harness-run `SUMMARY.md` and `manifest.json`. The manifest stores **relative paths**, so a finished run folder is **portable** — run on one machine, copy the folder elsewhere (e.g. Windows → Mac) and `status`/`tui`/`--dump` read it fine. Terminal states: `COMPLETED` is graded (`MET`/`NOT-MET`); `BLOCKED` (an AUP/usage-policy refusal, weekly-limit cutoff, or socket error — read `terminal_reason` to tell which), `TIMED_OUT`, `FAILED`, `ABORTED_PREP`, **`CANCELLED`** (v1.5.7 188: PENDING run cancelled by operator-initiated `kill <harness-run>` before the run ever acquired a pool slot — written via `cancel_pending_run` helper; the collector's PENDING-retry loop and `_try_acquire_pool_slot` both skip CANCELLED entries by checking `state != "PENDING"`), and **`ABORTED_PHASE`** (v1.5.7 164: Mode B supervisor aborted mid-phase) all grade `N/A`. **Post-v1.5.7 174 the manifest's `state` field is updated through PENDING → ACQUIRING → RUNNING → DONE+terminal_state as the entry transitions, so `manifest.json` is the source of truth for liveness; the watchdog reads it directly.** **The pre-186 `ABANDONED_STARVED` terminal state + its 3600s auto-kill deadline (165) were REMOVED in 186** — for sequential `pool=1` plans with long-running rows, that deadline killed runs before the pool could free a slot for them. Replaced with operator-visible signals: status shows `pending Nh Mm` waiting time + collector heartbeat-age health, and an explicit `force-run <run-NN>` CLI subcommand + TUI `E` keybinding launches a PENDING row out of pool when the operator decides the wait is wrong. (186 / 186-followup-1)

### Gotchas

- **Quota.** The claude runs draw on the Anthropic weekly limit; copilot (GitHub) and codex (OpenAI) go through other providers and aren't blocked by Claude quota.
- **`status`/`tui` default to `./harness_runs/`** in the cwd. If you want to read a run from a different location, pass the run-dir as a positional arg.
- **Windows: install harness runtime deps before firing.** The harness needs `build` (PEP 517 wheel builder), `psutil` (post-182 process management), `textual` (TUI), and `windows-curses` (Windows-only). The list lives at `bin/harness/requirements.txt` (force-added; gitignored otherwise) and installs via `python3 -m pip install -r bin/harness/requirements.txt`. Use `python3 -m pip` (not bare `pip`) so the install lands in the Python the harness will actually use — on Windows with multiple Python installs, `pip` can map to a different interpreter than `python3 -m`.
- **Windows: cp1252 hazard surface.** Three sites where Python defaults to cp1252 on Windows have all been closed across 185 + 189 + 190 (see "How the harness works" → "Windows cross-platform contract"): (a) WRITE from Python to stdout/stderr → 185 ASCII output + PYTHONIOENCODING=utf-8 in child env, (b) READ from external log files → 189 errors="replace" at log-read sites, (c) WRITE from Python to subprocess stdin → 190 explicit `encoding="utf-8", errors="replace"` on `subprocess.run(text=True)` calls. Future PR reviewers gating any new `subprocess.run` / `open(text=True)` site should reference Section O's "Windows cp1252 hazard surface" design contract.
- **codex CLI model availability varies by account tier.** As of codex-cli v0.136.0 with a ChatGPT-account auth, `gpt-5.3-codex` returns `"The 'gpt-5.3-codex' model is not supported when using Codex with a ChatGPT account."` — use `gpt-5.5` (default) or `gpt-5.4-mini` (cheaper, smaller-context). Plan files should pick a model the operator's account tier supports; mismatched models surface as an empty `phase1.output.txt` and a fast child-exit, which can look like a harness bug but is a codex auth-side rejection. Acceptance plans in `harness_plans/` use the universally-available models.
- **codex Mode B parameter routing.** `parameters: ["-c", "model_reasoning_effort=low"]` in a Mode B plan gets passed to `run_playbook.py` (which rejects `-c` as unrecognized), NOT to codex directly. To pass codex-CLI config overrides in Mode B, wrap them: `parameters: ["--runner-extra-args", "-c model_reasoning_effort=low"]`. The `--runner-extra-args` flag (129) tells run_playbook to forward the string verbatim to codex.
- **Logs are written by the child OS-locale-default on Windows.** Even after 185 + 189, an external tool (pip install banner, Windows utility) can write cp1252 bytes into the harness's orchestrator log. The 189 fix made the harness's log-read sites use `errors="replace"` so high-bit content surfaces instead of crashing the diagnostic. If you ever do see a cryptic decode error reading a log directly, `python -c "print(open(sys.argv[1], encoding='cp1252', errors='replace').read()[-4000:])"` is the manual workaround.

## Current known issues

Active issues only. Historical issues that have shipped fixes (RING_RESET, v1.5.3.1 deferrals, the v1.5.3 curation-algorithm 171-floor, etc.) live in `VERSION_HISTORY.md` and are not repeated here.

1. **TDD execution compliance.** Only Claude Code reliably creates red/green log files. Copilot and Cursor skip the step despite v1.3.47's six insertion points. The v1.5.7 089m–089q TDD-credibility arc hardened the gate around this — WARN on honest `NOT_RUN`, FAIL on a RED/GREEN receipt that admits non-execution, a probe-first runner-env contract, version-gated for pre-1.5.7 runs. Still doesn't compel the non-claude CLIs to actually run the tests; a post-run script that mechanically runs the TDD cycle remains a possible future fallback.

2. **Rate limits.** Running 6+ repos simultaneously through iteration cycles triggers Copilot's 54-hour cooldown. As of 2026-06 Microsoft has also moved Copilot to usage-based pricing — adopters should expect higher per-run cost than the v1.5.7 acceptance set was authored under. Users need to stagger runs (2-3 repos at a time) or use Claude Code / Cursor / Codex.

3. **Cursor workspace contamination.** Cursor reads sibling directories and imports findings from prior runs. Repos must be isolated in their own parent directory.

4. **Iterations are net-negative for blind-CVE security work.** Empirical evidence from the 2026-06-03 A/B test (security_blind_v2 with vs. without `include_iterations: true`, 7 rows each): the with-iterations arm detected 0/7 target CVEs while the no-iterations arm detected 2/7 (setuptools CASE-001 + evervault-go CASE-009). The adversarial iteration's "argue against findings" pass over-dismisses real findings when the model's call-graph reasoning is shallow — setuptools went DETECTED → MISSED because the adversarial pass dismissed the target as a false positive (it probed `_resolve_download_filename` in isolation and missed the upstream `urllib.parse.unquote` call site). Default `include_iterations: false` for security plans is now the documented recommendation; the 187 field is opt-in for the rare case where breadth-search semantics outweigh the over-dismissal risk.

5. **codex/cursor model availability varies by account tier and CLI version.** No single model is universally available across all auth tiers — plan files should pick a model the operator's account supports. See the "Gotchas" section above for the specific 2026-06 case (`gpt-5.3-codex` restricted on ChatGPT-account Codex tiers as of codex-cli v0.136.0).

6. **`avro` / `spark` scope-selection problem in the v2 blind benchmark.** When the v2-rebuilt docs_gathered corpus describes multiple subsystems with equal depth (per the v2 methodology's "equal subsystem depth" rule), QPB tends to pick ONE subsystem to drill into per run — and may pick the wrong one. avro: QPB ran against Python (`io.py`) instead of Java (`SpecificCompiler.java` — the target). spark: QPB ran against the Python Connect client (`core.py`) instead of the Scala History Server (`JsonProtocol.scala` — the target). This is a methodology-side issue (the corpora are honest; QPB scope-selection is ambiguous) tracked for v1.5.8 — either tighten the corpus to direct attention without leaking CVE details, OR change QPB's Phase 1 to probe ALL major subsystems before drilling.

7. **evervault-go `relay.go` plain-HTTP CA finding surfaced by Gate 2.** The v2 methodology's blind reviewer (Gate 2) for evervault-go pointed at `relay.go::OutboundRelayClient` based on the gatherer's phrase "Fetch the Evervault CA certificate from `Config.EvervaultCaURL` over plain HTTP." Either (a) the gatherer used casual phrasing for "via HTTP protocol" and the default `EvervaultCaURL` is actually HTTPS, in which case the docs should clarify, OR (b) the default is genuinely HTTP and this is a real new side finding worth a writeup. Spot-check at SHA `841dca607a6d` pending — tracked for v1.5.8.

8. **3 missing CASE corpora.** The CVE benchmark has 10 cases in `Security Research/CVE_BENCHMARK_PILOT.md`. Only 7 have v2-rebuilt corpora as of 2026-06-02 (CASE-001 setuptools, -002 jsPDF, -005 avro, -007 spark, -008 dasel, -009 evervault-go, -010 gogs). The missing 3 (CASE-003 keras, -004 CPython tarfile, -006 Budibase) never had docs gathered — fresh blind forward-gathering needed to fill the benchmark to 10. Tracked for v1.5.8.

9. **openfga / casbin / nats-server are NOT in the blind-CVE benchmark.** Per `PORTFOLIO_TRACKER.md` Goal A vs. Goal B framing, these three repos are real-world-runs (opportunistic evidence) not blind benchmarks. Their docs_gathered corpora were quarantined alongside the 2026-06-02 contamination cleanup; rebuilding them is a separate decision contingent on whether the real-world-runs Goal A track wants production-codebase artifacts at all. Tracked for v1.5.8.

10. **Casbin has no real published advisory for its core authorization library.** Panelist C of the 2026-06-02 Contamination Council surfaced this — if the "target CVE" for a benchmark row can't be cited authoritatively from a CVE database, the row doesn't belong in a CVE benchmark. Drop casbin from any future blind-CVE benchmark plans; the existing casbin findings remain valid for the "real-world runs" Goal A track.

11. **Worker self-Council protocol is in workspace AGENTS.md AND now mirrored in `DEVELOPMENT_PROCESS.md`** — see DEVELOPMENT_PROCESS.md "Worker self-Council protocol" section for the canonical definition. The workspace AGENTS.md retains Protocol 2 (external Council across 3 CLI terminals, for fresh-context architectural decisions) which is QPB-adjacent operator tooling, not QPB-project methodology.

## Making changes to the skill

**Always back up before editing.** Copy any file you're about to modify to a `.bak` version first.

**Test on at least 2 repos after changes.** One large (virtio or cobra) and one small (chi). Check both baseline and at least one iteration strategy.

**Update the version.** The `version:` field in SKILL.md metadata must be bumped for every change. All generated artifacts stamp this version, and mismatches cause quality_gate.py failures.

**Run quality_gate.py after testing.** The gate validates artifact conformance mechanically. If it passes on your test repos, the change is safe to commit.

**Update TOOLKIT.md and this file.** If your change affects how users run the playbook or how maintainers work on it, update the relevant context file.

### Release tooling (v1.5.8+)

When the skill is ready to ship a new release, three publish scripts handle the distribution channels. All three live in `bin/` and follow the same `--dry-run` XOR `--publish` (or `--submit`) affirmation pattern — running them with no flag prints intro/help, requiring an explicit choice between safe rehearsal and live publish.

- **`bin/publish_pip.py`** — eight pre-flight checks (clean tree, version parity across pyproject/package/init, tag exists + ancestor, build, parity test, no forbidden contents, twine auth), then two-phase publish: test PyPI → operator confirmation → prod PyPI → `pip index versions` verification. Logs at `~/.qpb/publish_logs/pip_<ver>_<ts>.log`.
- **`bin/publish_npm.py`** — seven pre-flight checks (clean tree, version parity, tag, `npm whoami`, stage bundle, no forbidden contents, `npm pack --dry-run`), then `npm publish --access public` + `npm view` verification. Pre-204 had a UX bug where any non-`--dry-run` flag fell through to live publish; 204 added the explicit `--publish` affirmation. 205 adds `--otp` support for 2FA-enabled accounts (workaround: granular access token with bypass-2FA enabled, deleted immediately after use).
- **`bin/submit_awesome_copilot.py`** — generates a submission packet (trimmed SKILL.md + PR_BODY.md + MANUAL_STEPS.md + submission.json) for github/awesome-copilot. Originally manual-only (operator runs the steps in MANUAL_STEPS.md); 206 adds `--submit` to automate fork-and-PR via `gh` CLI with confirmation gates before destructive actions.

The full release close-out sequence — push branch → tag move → live publishes (pip + npm + awesome-copilot) → README/TOOLKIT install instructions → DEVELOPMENT_CONTEXT refresh → release-specific channel work → merge to main → branch next version — is canonical in `ai_context/DEVELOPMENT_PROCESS.md` § "Release close-out sequence." Read that section before starting any close-out work; the merge-to-main step explicitly moves to the END of close-out (not at tag time) so post-tag publish-channel work lives on the release branch rather than fragmenting onto a patch branch.

The publish-channel hardening arc that produced these scripts: instructions 202 (created the scripts), 203 (fixed `npm pack --dry-run --json` JSON parse failure caused by prepack writing progress to stdout), 204 (added the `--publish` XOR `--dry-run` affirmation), 205 (`--otp` support), 206 (awesome-copilot `--submit` automation). All landed during v1.5.8 close-out.
