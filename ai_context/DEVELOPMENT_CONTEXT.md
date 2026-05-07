# Quality Playbook — Development Context

> This file is for AI assistants helping maintain and improve the quality playbook skill.
> It contains the project's architecture, benchmarking methodology, known issues,
> and improvement axes. Read this when working on the skill files themselves.
>
> The project accompanies the O'Reilly Radar article [AI Is Writing Our Code Faster Than We Can Verify It](https://www.oreilly.com/radar/ai-is-writing-our-code-faster-than-we-can-verify-it/).
> The README was coauthored with Claude Cowork.
>
> *Last updated: 2026-05-07 (v1.5.6 fix-up 055 — v1.5.6 shipped with the Pattern 7 displacement-recovery cycle execution + the `bin/install_skill.py` adopter install script + a complete bootstrap-fixup cycle (clusters 1-8 closed 22 named bugs + 2 quality-gate self-consistency failures) + audit-discovered backlog clusters A, B, C, D, F.1 (install polish, validator mapping reconciliation, `--require-docs` flag, cross-platform validation evidence, calibration_orchestrator.md cycle clarifications). GitHub issue #1 fully closed. Test suite: 1136 pass / 0 fail / 8 skip. Cluster E (chi-1.3.45 docs-backed validation re-run) was dropped in favor of the v1.5.6 cluster 047 architectural fix (`bin.role_map.normalize_role_map_for_gate`) that closes the underlying defect class for all future cycles; cluster F.2a (chi-1.5.1 follow-on pre-lever) ran with claude-opus-4-7 producing 9/16 substantive recall against the v1.5.1 baseline. The cycle is closed at 3 of 4 benchmarks (chi-1.5.1 informs the historical baseline understanding but is not a 4th cell in the cycle's recall table). v1.6 remains the next major release with Requirements Review; v1.7 carries the Statistical Process Control machinery that the REQ-ID-instability methodology asterisk feeds into).*

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
│           ├── quality_gate.py        ← Mechanical validation (34 check_* functions at v1.5.3, 3000+ lines, Python 3.8+)
│           └── tests/
│               ├── __init__.py
│               ├── README.md          ← v1.5.3: documents `unittest discover` as the canonical runner (DQ-5-8)
│               ├── test_quality_gate.py  ← 215 stdlib-only unit tests at v1.5.3
│               └── test_req_pattern.py   ← 6 stdlib-only unit tests
├── ai_context/                        ← AI-readable context files
│   ├── TOOLKIT.md                     ← For users' AI assistants (setup, run, interpret, recheck)
│   ├── DEVELOPMENT_CONTEXT.md         ← For maintainers' AI assistants (this file)
│   ├── DEVELOPMENT_PROCESS.md         ← How the QPB project itself is developed (mechanical procedures, rationale, open directions)
│   ├── IMPROVEMENT_LOOP.md            ← Methodology doc: how QPB applies QE to itself (verification dimensions, lever inventory, regression replay, SPC trajectory)
│   ├── CALIBRATION_PROTOCOL.md        ← 12-step Mode 1 (autonomous) / Mode 2 (operator-driven) protocol for driving a calibration cycle
│   ├── TOOLKIT_TEST_PROTOCOL.md       ← Release-gate review protocol for orientation docs (orientation-doc analog of Council-of-Three)
│   └── BENCHMARK_PROTOCOL.md          ← Clean-folder run protocol for contamination-free benchmarks; v1.5.5+ documents run_state.jsonl format and cross-validation rules
├── repos/                             ← Benchmark repos and setup tooling
│   ├── setup_repos.sh                 ← Copies skill files into target repos
│   ├── _benchmark_lib.sh              ← Shell helpers shared by setup_repos.sh, run_tdd.sh, etc.
│   └── clean/                         ← Clean clones of benchmark repos
├── quality/                           ← Bootstrap artifacts (playbook run against QPB itself)
└── council-reviews/                   ← Council review briefings and responses (not distributed)
```

**Automation note:** benchmark automation lives in `bin/` and uses only the Python standard library so sandboxed AI agents can run it without creating a virtual environment or installing packages. The shell scripts remaining in `repos/` (`setup_repos.sh`, `_benchmark_lib.sh`, `run_tdd.sh`) handle repo setup and TDD plumbing — they no longer include a runner.

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
`python3 -m pytest` works on plain Python 3.8+ with no external
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

### Benchmark repos

The benchmark suite uses open-source codebases across multiple languages. Each repo is cloned once into `repos/clean/` and never modified. For each skill version, `setup_repos.sh` creates a working copy (e.g., `chi-1.4.6`) with the skill files installed.

Active benchmark set (four targets):

- **bootstrap** — the playbook running against its own codebase (self-audit). Bootstrap artifacts live at `quality/` at the QPB repo root, not in `repos/`. Always included; see "Why bootstrap is a benchmark target" below.
- **chi** (Go) — small HTTP router; quick sanity-check runs.
- **cobra** (Go) — larger CLI framework; exercises iteration strategies more heavily.
- **virtio** (C / Linux kernel driver) — hardest repo; reference target for parity strategy and the historical home of the mechanical-verification rules.

60+ additional repos remain in `repos/clean/` for expanded benchmarking when a specific change calls for it (e.g., language-specific regressions, framework-specific exploration patterns). They are not part of the default validation loop for skill changes. `python3 bin/run_playbook.py` treats every positional argument as a directory path (relative or absolute) — no version resolution, no benchmark-folder lookups.

#### Why bootstrap is a benchmark target

Bootstrap is the playbook running against `/Users/andrewstellman/Documents/QPB` itself. It's always included in the active benchmark set because:

1. **Self-referential edge cases.** The gate script validates its own artifacts. SKILL.md is both the instruction set and the subject under audit. Changes to rules about enum validation, heading format, or script-verified closure can break on the very script that enforces them — and only bootstrap catches that class of bug.
2. **Perfect verification.** We wrote the skill and the gate, so we can verify any finding against our own intent quickly. For other repos, we spot-check; for bootstrap, we can confirm every bug.
3. **Reproducibility.** The codebase is stable between runs (our own commits), so convergence trends cleanly across model/runner combinations.

Bootstrap artifacts live at `quality/` at the QPB repo root rather than under `repos/`. To run bootstrap, the agent treats the QPB root as the target directory; the existing `quality/` is the prior-run evidence (phase 0 seed source).

### Running benchmarks

See `ai_context/BENCHMARK_PROTOCOL.md` for the clean-folder run protocol. Benchmark runs must be isolated (no sibling runs visible to the agent) or findings leak between runs and the tuning signal is corrupted.

Positional arguments are directory paths (relative or absolute) — the runner does no short-name resolution and no benchmark-folder lookup. Run from `repos/` so the working-copy directory names produced by `setup_repos.sh` (e.g. `chi-1.4.6`) can be passed as plain relative paths:

```bash
cd repos/
./setup_repos.sh chi cobra virtio                     # copy skill files into the three repo-based targets
python3 ../bin/run_playbook.py chi-1.4.6 cobra-1.4.6 virtio-1.4.6          # baseline runs (Copilot default)
python3 ../bin/run_playbook.py --claude chi-1.4.6 cobra-1.4.6 virtio-1.4.6 # baseline runs (Claude Code)
python3 ../bin/run_playbook.py --codex chi-1.4.6 cobra-1.4.6 virtio-1.4.6  # baseline runs (codex-cli, v1.5.3+)
python3 ../bin/run_playbook.py --next-iteration --strategy all chi-1.4.6 cobra-1.4.6 virtio-1.4.6  # full iteration cycle
```

With no positional args the runner operates on the current directory, which is how bootstrap is invoked:

```bash
cd /Users/andrewstellman/Documents/QPB
python3 bin/run_playbook.py --phase all      # bootstrap: run on the QPB repo itself
```

Bootstrap is the fourth active target but doesn't go through `setup_repos.sh` — the QPB repo already has SKILL.md and references at their canonical locations.

### Interpreting results

**Bug counts vary between runs.** The same skill on the same codebase produces different bug counts due to non-determinism in exploration. A single run isn't definitive. Compare across 5+ runs or use iteration cycles to compensate.

**Baseline vs. iteration yield.** Baseline typically finds 1-3 bugs per repo. Full iteration cycle (gap + unfiltered + parity + adversarial) multiplies by 3-4x. If a skill change doesn't improve baseline yield, it may still improve iteration yield or vice versa.

**Spot-check every new version.** After making skill changes, spot-check 3-5 bugs from the new version against actual source code. Verify the bug is real, the file:line is correct, and the regression test would actually fail. In v1.3.46 benchmarking, 15/15 spot-checked bugs were verified as real.

### Council reviews

For major skill changes, we run a council review: three different AI agents independently analyze the benchmark data, iteration logs, and bug quality, then propose improvements. The agents don't modify code — they write analysis documents.

Council review artifacts go in `council-reviews/`. Each review has:
- `COUNCIL_BRIEFING_VN.md` — data and questions for the council
- `COUNCIL_VN_PROMPTS.md` — prompts for each reviewer (must include "DO NOT modify any code")
- `{AGENT}_RESPONSE_VN.md` — each reviewer's analysis

### Known agent behavior differences

| Agent | Exploration | TDD execution | Known issues |
|-------|------------|---------------|-------------|
| Claude Code / Opus | Strong | Reliable (creates red/green logs) | Expensive (~8% weekly per run) |
| Claude Code / Sonnet | Strong (25 bugs, 3 HIGH) | Reliable | Recommended default (~3% weekly per run) |
| Copilot / gpt-5.4 | Strong | Weak (skips log creation) | 54hr rate limit on heavy use |
| Cursor / Sonnet | Good | Weak first pass, follows up when asked | Workspace scope bleeds to siblings |
| Cursor / Codex 5.3 | Weak (zero bugs) | N/A | Insufficient reasoning depth |
| Codex CLI / `codex exec --full-auto` (v1.5.3+) | TBD — released as a runner option in commit `b6b31f2`; benchmark data accumulates as adopters use it | TBD | Standalone CLI (NOT `gh copilot`); codex picks its model from `~/.codex/config.toml` unless `--model` overrides |

## Version history highlights

- **v1.3.13–v1.3.14:** Early structured approach. Zero bugs found — too rigid.
- **v1.3.21:** Gate hardening. First confirmed bugs (2 total across 10 repos).
- **v1.3.25:** Unfiltered domain-driven exploration. Major breakthrough — 14 bugs.
- **v1.3.40:** Parity patterns. Found 5 virtio bugs using fallback path comparison.
- **v1.3.44:** Iteration mode (gap, unfiltered, adversarial). 3.7x baseline yield.
- **v1.3.45:** references/iteration.md reference file, parity strategy, suggested-next-prompt UX.
- **v1.3.46:** Demoted Candidates Manifest, parity sub-type checklist, adversarial bar adjustment, TDD execution enforcement.
- **v1.3.47:** TDD log enforcement — six insertion points from Cursor diagnostic (artifact contract, closure gate, bash template, progress checkbox, file-existence gate, sidecar contradiction check).
- **v1.4.0** (promoted from v1.3.50)**:** Six-phase interactive architecture (renumbered from 3 phases to 6), interactive phase-by-phase execution with end-of-phase messages, `--phase` flag in runner, quality gate script, four iteration strategies with 40-60% yield boost, TDD enforcement, documentation warning, help system, "keep going" continuation, O'Reilly Radar article, moved ITERATION.md to references/iteration.md, orchestrator agents for Claude Code and Copilot. Benchmarked: Express.js (14 bugs), Gson (9 bugs), Linux virtio (8 bugs) — all with 100% TDD coverage and 0 gate failures.
- **v1.4.1:** Recheck mode for lightweight fix verification (reads BUGS.md, checks each bug against current source, outputs recheck-results.json and recheck-summary.md). Fixed 19 bugs from bootstrap self-audit (second run): eval injection in the gate script (then `quality_gate.sh`, now `quality_gate.py`), bash 3.2 empty array crashes, required artifacts downgraded to WARN, json_key_count false positives, missing artifact checks, documentation inconsistencies. All fixes verified by recheck (19/19 FIXED).
- **v1.4.2:** Fixed 25 bugs from Sonnet 4.6 bootstrap self-audit (3 HIGH, 8 MEDIUM, 14 LOW). Key fixes: nullglob-safe artifact detection (find replaces ls-glob across 7 locations), severity-prefixed bug ID support (BUG-H1/BUG-M3/BUG-L6), TDD sidecar-to-log cross-validation, recheck-results.json gate validation, Phase 5 entry gate, SEED_CHECKS.md in artifact contract table, integration enum validation. Added run metadata JSON spec (`quality/results/run-YYYY-MM-DDTHH-MM-SS.json`) for multi-model comparison — records model, provider, runner, timestamps, phase timings, bug counts, and gate results. All 25 fixes verified by Sonnet recheck (25/25 FIXED). Multi-model comparison: Sonnet found 25 bugs (3 HIGH) at ~3% weekly usage vs Opus's 19 bugs (1 HIGH) at ~8% — Sonnet is the recommended default for playbook runs.
- **v1.4.3:** Challenge gate added for false-positive detection — forces triage to reconsider CRITICAL findings with common-sense review before closure (motivated by edgequake benchmarking where 6/7 "CRITICAL" findings turned out to be documented feature gaps or placeholders). Functional-test reference refactored: split into per-language files, then re-merged into a single `references/functional_tests.md` with import patterns folded in. First pass of orchestrator hardening: `references/orchestrator_protocol.md` extracted as a shared reference imported by both agent files, with critical rules duplicated inline for safety.
- **v1.4.4:** Orchestrator hardening pass — "You are the orchestrator" architecture. Fixes three failure modes observed on casbin benchmarking: (1) single-context collapse (all six phases executed in one context, producing shallow summaries and zero files on disk), (2) `claude -p` subprocess spawning (orchestrator trying to fork fresh CLI processes instead of using the Agent tool), (3) nested Agent-tool stripping (Claude Code strips the Agent tool from nested sub-agents, so the orchestrator must be single-level). The session that reads the agent file IS the orchestrator — it never spawns a new session, only sub-agents. Protocol lives at `references/orchestrator_protocol.md`; critical rules are duplicated inline in each agent file.
- **v1.4.5:** Tooling rebuild plus surface cleanup:
    - **Runner rewritten in Python.** `bin/run_playbook.py` + `bin/benchmark_lib.py` replace the old `repos/run_playbook.sh` (deleted). `repos/_benchmark_lib.sh` remains in use by `setup_repos.sh` and `run_tdd.sh`. Standard library only, Python 3.8+, 36 stdlib-only tests at release (grew to 92 with v1.4.6 regression coverage).
    - **Runner interface redesign.** Positional args are directory paths, not short names. Default is the current directory. No more `DEFAULT_REPO_NAMES`, `REPOS_DIR`, `SHORT_VERSIONED_DIR_PATTERN`, `find_repo_dir`, `resolve_repos`, `repo_short_name`, or version-resolution logic. Missing SKILL.md is a warning rather than a fatal error. Log files live beside each target at `{parent}/{target-name}-playbook-{timestamp}.log` instead of being forced into `repos/`. A narrow **version-append fallback** retries `<name>-<skill_version>` once when a bare name doesn't resolve — lets `cd repos/ && python3 ../bin/run_playbook.py chi` pick up `chi-<version>` without reintroducing the old short-name tables.
    - **Python gate is sole mechanical gate.** `quality_gate.sh` retired; `quality_gate.py` handles JSON via `json.load` instead of grep-style parsing. Moved to `.github/skills/quality_gate/` as a proper package with `__init__.py` and a 108-test `tests/` subdirectory. The stable invocation path `.github/skills/quality_gate.py` is a symlink to the package module.
    - **Benchmark set reduced to four targets.** bootstrap, chi, cobra, virtio — down from 10. Bootstrap runs last because fixes from the first three land before the playbook audits itself. 60+ additional repos remain in `repos/clean/` for expanded benchmarking but aren't part of the default validation loop.
    - **Recheck gate fix.** Root-key check for `recheck-results.json` corrected from `bugs` → `results` to match the SKILL.md schema.
- **v1.4.6:** Lands the 27-bug fix pass from the v1.4.5 self-audit. No structural or behavioral changes beyond the bug fixes themselves; v1.5.1 shipped on this clean baseline (see v1.5.1 below).
    - **27-bug bootstrap self-audit fix batch.** Opus self-audit over the v1.4.5 baseline + four iteration strategies (gap, unfiltered, parity, adversarial) confirmed 27 real defects; all 27 are fixed with passing regression tests in `quality/test_regression.py`. Shipped in seven thematic commits. Material behavior changes: Phase 2 gate now FAILs below 120 lines instead of WARNing at 80 (matches SKILL.md §Phase 1 completion gate); Phase 3 gate checks all nine Phase 2 artifacts instead of four; Phase 5 gate enforces SKILL.md:1663-1667 hard-stop (spec_audits triage + auditor files + Phase 4 `[x]`); `archive_previous_run` stages into a `.partial` subfolder under the runs archive then atomically renames, and preserves the per-phase prompt outputs instead of deleting them (v1.5.1 paths: `quality/runs/<ts>.partial/` and `quality/control_prompts/`; v1.4.x used root-level `previous_runs/` and `control_prompts/`); `cleanup_repo` adds `AGENTS.md` to its protected-path set via `PROTECTED_EXACT`; child-process exit codes propagate through `run_one_phase` / `run_one_singlepass`; missing `docs_gathered/` WARNs and continues with code-only analysis instead of blocking the run; runner prompts front-load a `SKILL_FALLBACK_GUIDE` constant advertising all four install paths; `check_run_metadata` and `_check_exploration_sections` close two long-standing gate gaps; `validate_iso_date` accepts full ISO 8601 datetimes; `_parse_porcelain_path` unwraps Git's quote-wrapped paths for names with spaces; `detect_project_language` skips `repos/` fixtures so the self-audit classifies correctly; the functional-test filename matrix + extension check now recognize the full `functional_test.*` / `FunctionalTest.*` / `FunctionalSpec.*` / `functional.test.ts` set; `FUNCTIONAL_TEST_PATTERNS` / `REGRESSION_TEST_PATTERNS` narrowed to canonical names only; both orchestrator agents list repo-root `SKILL.md` as install-discovery entry 1 and the general agent's Mode 1 now starts a fresh context for Phase 1. Recheck: 27/27 FIXED (`quality/results/recheck-summary.md`).
    - **Bootstrap artifacts tracked in git.** Reverses the earlier untracking now that `cleanup_repo`'s `PROTECTED_PREFIXES` guards `quality/` (which in v1.5.1 covers `quality/runs/` and `quality/control_prompts/`) from `git checkout .`. These trees are the proof-of-work for the self-audit and belong in git history so future iterations can diff against them. v1.5.1's `bin/migrate_v1_5_0_layout.py` moves the legacy root-level `previous_runs/` and `control_prompts/` under `quality/`.
- **v1.5.1:** Phase 5 writeup hardening — `phase5_prompt()` now hydrates writeups from BUGS.md via a MANDATORY HYDRATION STEP with worked BUG-004 example and per-writeup confirmation checklist; `check_writeups` in `quality_gate.py` fails on any of five template-sentinel strings or a ` ```diff ` fence that has no `+` / `-` lines; `_WRITEUP_DIFF_BLOCK_RE` uses case-insensitive matching so mixed-case diff fences (` ```Diff `, ` ```DIFF `) don't produce spurious "no inline fix diffs" FAILs. New unit tests cover sentinel detection and empty-diff-fence detection. Four commits landed on branch `1.5.1` ahead of main: b7b8752 (version bump 1.5.0 → 1.5.1), 9c23059 (case-insensitive regex), d4b4ae8 (tests), 002e3c6 (CHANGELOG). Benchmark results: virtio-1.5.1 found 8 bugs matching the 1.4.6 baseline count with substantial overlap on the core five (MMIO reset, IRQ config, INTx admin queue, slow_virtqueues rejoin, vDPA affinity) and three different bugs in each direction; chi-1.5.1 found 9 bugs versus 5 in chi-1.4.6 and 6 in chi-1.5.0, confirming that the writeup hardening did not regress discovery yield. One coverage gap surfaced in the 1.5.1 runs: the RING_RESET bug family from v1.4.5 (four bugs spanning VIRTIO_F_RING_RESET, VIRTIO_F_NOTIF_CONFIG_DATA, VIRTIO_F_ADMIN_VQ, VIRTIO_F_SR_IOV across MMIO and vDPA transports) was correctly identified by the Phase 2 reviewer — REQ-010 flagged "Modern PCI compensates; MMIO/vDPA do not" — but classified as QUESTION-001 instead of escalated to BUG, so the four bugs never reached BUGS.md. Planned for 1.5.2: Phase 1 cartesian use-case rule (emit one UC per symmetric implementation site) plus Phase 2 mechanical compensation-grid rule (any `pattern: whitelist | parity | compensation` requirement produces a grid where missing cells default to BUG, not QUESTION).
- **v1.5.2:** Bug-family amplification + operational polish. Phase 1 cartesian use-case rule ships (Lever 5 mechanical extraction surface enforces emit-one-UC-per-symmetric-implementation-site); Phase 2 mechanical compensation-grid rule promotes whitelist/parity/compensation cells to BUG-by-default rather than QUESTION (closes the v1.5.1 RING_RESET coverage gap). C13.6–C13.10 lever pulls land: `bin/citation_verifier.py` adds the `reference_docs/cite/` extension check, tier marker semantics, downgrade-record skip handling, present:true evidence enforcement; `_finalize_iteration` in `bin/run_playbook.py` runs `quality_gate.py` as a subprocess after each iteration and writes a structured block to PROGRESS.md mapping the verdict into INDEX.md's `gate_verdict` field; `document_sha256` schema fix in `bin/reference_docs_ingest.py` (producer was writing `sha256` while gate read `document_sha256`, silently disabling stale-citation invariant); `--flag=value` argparse form fix in `_mark_iterations_explicit`; SKILL.md version stamps consistent with `bin/tests/test_run_playbook.py:test_skill_version_matches_release_constant` as CI guard. Two full Council-of-Three nested-panel reviews (Round 7 against C13.6–C13.9 surface, Round 8 against C13.10 release-prep fixes; Round 8 was 8/9 ship + 1 block on a structural test-discipline issue logged for v1.5.3). Three new orientation files: `ai_context/IMPROVEMENT_LOOP.md`, `ai_context/TOOLKIT_TEST_PROTOCOL.md`, and the "How we improve the playbook" section in README.md. Honest "moving toward statistical control" framing across the methodology surface (within-version variance estimation deferred to v1.5.4 replicate harness; ±2 bugs across runs is within noise floor and should not be interpreted as real movement).
- **v1.5.3:** Skill-as-code feature complete. Originating evidence: 2026-04-19 Haiku demonstration showed claude-haiku-4-5 generating a 2,129-line REQUIREMENTS.md against QPB's own SKILL.md from a simple two-turn interaction, exposing that earlier QPB releases were leaving substantial skill-prose coverage on the table because the heuristic pipeline was tuned for code projects.
    - **Phase 0 project-type classifier** (`bin/classify_project.py`). Classifies every target as Code, Skill, or Hybrid based on a SKILL.md-prose-vs-code-LOC ratio; persists output to `<target>/quality/project_type.json`. CLI surface includes `--target` / `--benchmark` / `--write` plus the v1.5.3 Phase 4 `--override` and `--override-rationale` flags for Council triage. Validated against 6 benchmark cells (5 code + QPB self) — `## Overall: PASS`. Council override workflow at `docs/design/QPB_v1.5.3_Phase4_Council_Override_Workflow.md`.
    - **Schema extensions** (`schemas.md` §3.6 / §3.7 / §3.8 / §3.9 / §3.10). Adds `req_source_type` enum (`code-derived` / `skill-section` / `reference-file` / `execution-observation`), `bug_divergence_type` enum (`code-spec` / `internal-prose` / `prose-to-code` / `execution`), `formal_doc_role` enum, the SKILL.md-vs-reference-file precedence rule for default disposition, and v1.5.3 field-presence detection (the validator treats a manifest as v1.5.3-shaped iff any record carries `source_type` / `divergence_type` / `role`).
    - **Four-pass generate-then-verify pipeline** (`bin/skill_derivation/`). Pass A naive coverage section-iterative (`pass_a.py` + LLM prompts under `prompts/`); Pass B mechanical citation extraction with token-overlap pre-filter (`pass_b.py` + `citation_search.py`, ~93× speedup vs full O(n×m) similarity match); Pass C formal REQ + UC production with project-type-aware behavioral routing (`pass_c.py`, including the Round 5 ND-2 skill_section non-empty validation guard); Pass D coverage audit + Council inbox per the DQ-5 schema (`pass_d.py`). Resumability: every pass advances a per-record cursor atomically and rolls back to disk state on restart. Verified by 4 mid-pass-kill exercises during the v1.5.3 self-audit.
    - **Skill-divergence taxonomy** (`bin/skill_derivation/divergence_*.py`). Internal-prose (`divergence_internal.py`) detects within-prose contradictions via three-stage indexing (intra-section + cross-section-countable + un-anchored-uc subtypes); prose-to-code splits into Tier 1 mechanical (`divergence_prose_to_code_mechanical.py`, regex-countable claims) and Tier 2 LLM-driven (`divergence_prose_to_code_llm.py`, Hybrid only, resumable); execution (`divergence_execution.py`) aggregates archived `quality_gate.py` results across `previous_runs/` per-target. Phase 5 detector-precision pass tightened the four-pronged filter (ordinal-context skip; artifact-name proximity for cross-section pairs; hedge / parenthetical claim filter; Stage 3 candidate demotion to a separate `pass_e_internal_candidates.jsonl`) to drop the FP rate from ~70% on internal-prose to plausibly-real on QPB.
    - **Skill-project gate enforcement.** Four new check_* functions in `quality_gate.py`: `check_skill_section_req_coverage`, `check_reference_file_req_coverage`, `check_hybrid_cross_cutting_reqs`, `check_project_type_consistency`. Skill-specific checks SKIP (info, no fail counter increment) for Code projects; `check_project_type_consistency` runs for all projects but SKIP-silently on missing `project_type.json` (pre-Phase-1 fixture).
    - **Bootstrap evidence at `previous_runs/v1.5.3/`** (28 files, ~4.6 MB). Curated REQUIREMENTS.md (171 REQs across 171 sections — over the brief's [80, 110] target; cross-partition consolidation needed to reach the band, tracked as v1.5.4 backlog B-4); full Phase 3 + Phase 4 artifact set; 8 partition-density warnings as v1.5.4 curation signal.
    - **Eight Council-of-Three rounds** drove v1.5.3 development end-to-end (Phase 3a foundations through Phase 4 Round 8 + Round 7 follow-up + Phase 5 release-readiness). Synthesis docs at `Quality Playbook/Reviews/QPB_v1.5.3_Round{1..8}_Synthesis.md`.
    - **Five items deferred to v1.5.3.1 patch** per the brief's wall-clock-budget allowance: full playbook regression sweep on 5 code targets (Stage 4A), cross-model second backend opus run (Stage 4D), optional v1.4.5 cross-version cell (Stage 4E), categorization tagging surface, orientation-doc release-cadence review. Full backlog at `Quality Playbook/Reviews/v1.5.4_backlog.md` (14 items B-1 through B-14).
    - **Post-tag — codex CLI runner added (commit `b6b31f2`).** OpenAI's standalone codex CLI (`https://github.com/openai/codex`, codex-cli 0.125+) joins claude (`claude --print`) and copilot (`gh copilot --prompt`) as a third LLM backend. `bin/skill_derivation/runners.py` ships a `CodexRunner` dataclass alongside `ClaudeRunner` and `CopilotRunner`; the runner factory `make_runner(name, *, model=None)` routes `name="codex"` to `CodexRunner`. CLI plumbing extended in `bin/run_playbook.py` (new `--codex` flag in the runner mutex group; nine dispatch sites updated for three-way runner choice; `ensure_runner_available` checks `shutil.which("codex")`; install hint points at the codex GitHub repo) and `bin/skill_derivation/__main__.py` (`--runner` choices extended to `{claude, copilot, codex}`). Codex's non-interactive mode is `codex exec --full-auto` — sandboxed automatic execution, the codex equivalent of `gh copilot --yolo`. The runner pipes the playbook prompt on stdin (codex `exec` reads stdin when no positional prompt is given), avoiding shell command-line length limits. Default model is empty (codex picks from `~/.codex/config.toml`); `--model gpt-5-codex` (or any model in the user's codex config) overrides. 7 new tests added (3 in `TestSkillDerivationMainArgs` + 3 in `MakeRunnerModelOverrideTests` + 2 in new `CodexRunnerArgvTests` class); bin/tests/ count is now 669 (was 662).
- **v1.5.4:** Regression-replay machinery and cell.json schema. The apparatus that makes the improvement loop quantitative landed: `metrics/regression_replay/SCHEMA.md` defines the per-cycle cell.json format (top-level identity, bug measurement, lever attribution, cross-benchmark regression check, apparatus reproducibility); the lever inventory in `IMPROVEMENT_LOOP.md` carries Lever 1-6; the cycle workflow is operator-driven through the `bin/regression_replay.py` apparatus described in SCHEMA.md (subsequently superseded by the v1.5.5 orchestration substrate per the discrepancies note in `CALIBRATION_PROTOCOL.md`). Canonical design and implementation plan at `docs/design/QPB_v1.5.4_Design.md` and `docs/design/QPB_v1.5.4_Implementation_Plan.md`.
- **v1.5.5:** Calibration-cycle orchestration substrate. Operationalizes the v1.5.4 regression-replay machinery as an autonomous-loop driver. Canonical design and implementation plan at `docs/design/QPB_v1.5.5_Design.md` and `docs/design/QPB_v1.5.5_Implementation_Plan.md`. Deliverables:
    - **Run-state instrumentation** (`bin/run_state_lib.py` + `references/run_state_schema.md`). Append-only `quality/run_state.jsonl` event log opened by an `_index` event. Event taxonomy: `_index`, `run_start`, `phase_start`, `phase_end`, `pattern_walked`, `pass_started`, `pass_ended`, `finding_logged`, `artifact_written`, `gate_check`, `error`, `documentation_state`. Read/parse helpers (`read_events`, `last_in_progress_phase`, `validate_run_state_file`); post-condition helpers (`validate_phase_artifacts`, `validate_no_source_edits`); writers (`append_event`, `write_progress_md`). Format invariants and cross-validation rules at phase boundaries documented in the schema reference.
    - **Calibration orchestrator template** (`agents/calibration_orchestrator.md`). The Mode 1 (autonomous) spawn-and-resume driver for `ai_context/CALIBRATION_PROTOCOL.md`'s 12-step workflow. Reads the per-cycle event log on resume, identifies the last-in-progress phase, continues from that boundary.
    - **Phase 5 source-edit guardrail.** `validate_no_source_edits` is wired into `bin/run_playbook.py:_finalize_iteration` as a mechanical post-condition. Any file modification outside `<target>/quality/` during Phase 5 finalization fires a `validation_result` event with `status="fail"`. The run is tainted from a recall-comparison standpoint and should be re-run from a clean checkout.
    - **Cycle visualization** (`bin/visualize_calibration.py`). Four charts emitted from accumulated cycle data: per-bug × cycle heatmap, lever × benchmark heatmap, recall trajectory, Mermaid lever-interaction graph. Used at release boundaries for cross-cycle review.
    - **Council Round 1 fixes** (commit `c33cc3c`). Five P0 findings closed before tag.
    - **Pattern 7 displacement-recovery cycle directory** at `~/Documents/AI-Driven Development/Quality Playbook/Calibration Cycles/2026-05-02-pattern7-displacement-recovery/`. Cycle scaffolding + lever description in place; lever-pull execution shipped in v1.5.6 (see below).
    - **Test count.** `bin/tests/` reaches 1017 tests / 0 failures / 3 skipped at v1.5.5 ship.
- **v1.5.6:** Pattern 7 displacement-recovery cycle execution + adopter-facing install script. First release implemented end-to-end via the `v1.5.6_runner/` orchestrator/worker runner folder per `ai_context/AI_ORCHESTRATION_PATTERNS.md`. Highlights:
    - **Pattern 7 displacement-recovery cycle ran end-to-end** on the closed 3-benchmark scope (chi-1.3.45 + virtio-1.5.1 + express-1.3.50 — express post-lever cell.json + cycle subdir verified at instruction 041 part 1). chi-1.5.1 was the original time-budget deferral; the v1.5.6 cluster F.2a follow-on pre-lever run with claude-opus-4-7 produced 9/16 substantive recall against the v1.5.1 baseline as a check on the model-quality fix path, but the cycle remains closed at 3 of 4 benchmarks (chi-1.5.1 informs historical baseline understanding rather than contributing a 4th cell to the recall table). Hypothesis: lowering Pattern 7's budget cap from `3-5` to `2-3` highest-impact composition seams should recover the chi-1.3.45 displacement losses (PathRewrite, AllowContentEncoding) while preserving Pattern 7's mount-context findings (BUG-004, BUG-007, BUG-008, BUG-009). Result: AllowContentEncoding recovered, but PathRewrite was lost at the same time and the four mount-context findings were not preserved (0/4); chi-1.3.45 overall recall moved from 5/10 to 4/10. Verdict: **REVERT**. The cap stayed at `3-5`. Cycle audit at `~/Documents/AI-Driven Development/Quality Playbook/Calibration Cycles/2026-05-02-pattern7-displacement-recovery/audit.md`; validation report at `~/Documents/AI-Driven Development/Quality Playbook/Reviews/QPB_v1.5.6_Validation_Report.md` (`pass-with-known-limitations` disposition stands; the chi-1.3.45 docs-backed re-run was dropped in favor of the v1.5.6 cluster 047 architectural fix that closes the underlying defect class).
    - **Methodology asterisk surfaced.** REQ-IDs were unstable across pre/post-lever runs (called out explicitly in worker output 008); the audit fell back to substantive file-path and description-content matching rather than the mechanical `(REQ_id, file)` replay key. Recorded as a v1.7 SPC concern: a stable cross-cycle match key is a precondition for control-chart-grade comparability.
    - **`bin/install_skill.py` adopter install script.** Standard-library Python 3.8+; auto-detects target environment markers (`.claude`, `.github`, `.cursor`, `.continue`); supports `--into <target>` for AI-agent-driven installs, `--target <path>` for literal install paths, `--no-smoke` to skip the post-install smoke check, `--force` to overwrite without backup, and `--verbose` for human-prose alongside the structured event output. Idempotent on re-install: existing files preserved as `<file>.operator-backup-<UTC-ts>` unless `--force`. Cross-platform: verified on macOS, asymptotically equivalent on Linux under stdlib-only constraints (`pathlib` + utf-8 + no platform-specific syscalls); direct Windows execution remained `untested-infrastructure-blocked` for v1.5.6 (pathlib correctness extended via `PathlibCrossPlatformTests.test_install_skill_pathlib_windows_path_handling` walking every bundle destination through `PureWindowsPath`). The canonical AI-agent-driven install procedure lives in `AGENTS.md`.
    - **Orchestrator/worker pattern documented.** `ai_context/AI_ORCHESTRATION_PATTERNS.md` published — adopter-grade documentation of the chat-side-orchestrator + coding-side-worker pattern with a runner-folder shared-directory protocol. v1.5.6 was the first release that used the pattern end-to-end across all release-arc work.
    - **chi-1.5.1 follow-on pre-lever ran at v1.5.6 cluster F.2a.** Pattern 7 re-attempt with chi-1.5.1 added to the cycle scope; playbook subprocess spawned 2026-05-06T21:00:06Z, completed 2026-05-07T04:42:21Z with claude-opus-4-7. Substantive recall against v1.5.1 baseline: 9/16 = 0.5625. The cycle remains closed at 3 of 4 benchmarks for verdict purposes (chi-1.5.1 informs historical baseline understanding but is not a 4th cell in the cycle's per-benchmark recall table — the displacement-recovery story was always concentrated on chi-1.3.45). The express post-lever data from the original 2026-05-02 cycle is intact (cell.json + cycle subdir verified at instruction 041 part 1; the original "interrupted" prose was reconciled in v1.5.6 fix-up 055). Skill-as-code adopter persona deep work continued from the v1.5.3 surface is queued as a future-release item without a pinned version number.

## Current known issues

1. **RING_RESET bug family — fix landed in v1.5.2.** The v1.4.5 run found four feature-negotiation bugs (VIRTIO_F_RING_RESET cleared in MMIO and vDPA, VIRTIO_F_NOTIF_CONFIG_DATA cleared in all transports, VIRTIO_F_ADMIN_VQ and VIRTIO_F_SR_IOV cleared in vDPA) via a mechanical compensation table in the Phase 2 review. v1.4.6 and v1.5.1 runs identified the same architectural asymmetry (REQ-010: "Modern PCI compensates; MMIO/vDPA do not") but downgraded the finding to QUESTION-001 instead of escalating to BUG, so the four bugs never reached BUGS.md. v1.5.2 closed this gap with the Phase 1 cartesian use-case rule + Phase 2 mechanical compensation grid (BUG-default classification on whitelist/parity/compensation cells). Item retained here as historical context.

2. **v1.5.3.1 deferred items.** Five Phase 5 items deferred per wall-clock budget — see `Quality Playbook/Reviews/v1.5.4_backlog.md` B-1 through B-3 for the deferral rationale. The substantive no-regression evidence already shipped (`--benchmark` PASS for all 6 cells; Phase 4 skill-checks SKIP on Code; no `bin/run_playbook.py` changes shipped in v1.5.3); the v1.5.3.1 patch will close the full-playbook-sweep + opus-cross-model gates.

3. **TDD execution compliance.** Only Claude Code reliably creates red/green log files. Copilot and Cursor skip the step despite v1.3.47's six insertion points (not yet tested on v1.3.47). If v1.3.47 doesn't fix it, a post-run script that mechanically runs the TDD cycle may be needed.

4. **Rate limits.** Running 6+ repos simultaneously through iteration cycles triggers Copilot's 54-hour cooldown. Users need to stagger runs (2-3 repos at a time) or use Claude Code / Cursor.

5. **Cursor workspace contamination.** Cursor reads sibling directories and imports findings from prior runs. Repos must be isolated in their own parent directory.

6. **Curation-algorithm 171-floor on QPB self-audit.** The v1.5.3 Phase 5 Stage 5A `curate_requirements.py` algorithm settles at 171 REQs on QPB (above the brief's [80, 110] target). Cause: 1007 accepted REQs collapse to 171 partitions each with ≥1 distinct post-Jaccard REQ; K=1 per partition is the floor. Cross-partition consolidation is needed to land in the band — tracked as v1.5.4 backlog B-4. Acceptable for v1.5.3 ship per the brief's "settle at whatever count the algorithm produces and document the calibration tension" allowance.

## Making changes to the skill

**Always back up before editing.** Copy any file you're about to modify to a `.bak` version first.

**Test on at least 2 repos after changes.** One large (virtio or cobra) and one small (chi). Check both baseline and at least one iteration strategy.

**Update the version.** The `version:` field in SKILL.md metadata must be bumped for every change. All generated artifacts stamp this version, and mismatches cause quality_gate.py failures.

**Run quality_gate.py after testing.** The gate validates artifact conformance mechanically. If it passes on your test repos, the change is safe to commit.

**Update TOOLKIT.md and this file.** If your change affects how users run the playbook or how maintainers work on it, update the relevant context file.
