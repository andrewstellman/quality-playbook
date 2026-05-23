# Quality Playbook — Development Context

> This file is for AI assistants helping maintain and improve the quality playbook skill.
> It contains the project's architecture, benchmarking methodology, known issues,
> and improvement axes. Read this when working on the skill files themselves.
>
> The project accompanies the O'Reilly Radar article [AI Is Writing Our Code Faster Than We Can Verify It](https://www.oreilly.com/radar/ai-is-writing-our-code-faster-than-we-can-verify-it/).
> The README was coauthored with Claude Cowork.
>
> *Last updated: 2026-05-23 (v1.5.7). For the full per-release changelog see `CHANGELOG.md`; for the curated evolution narrative (v1.3.13 → present) see `ai_context/VERSION_HISTORY.md`. This file is kept current with the skill's architecture, not its release log.*

## How to read this doc

This file is the maintainer's map of the project. You rarely need all of it — load the section that matches your task:

- **Changing skill files / navigating the repo** → "Project structure", "How the skill works", "Making changes to the skill".
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

## Current known issues

1. **RING_RESET bug family — fix landed in v1.5.2.** The v1.4.5 run found four feature-negotiation bugs (VIRTIO_F_RING_RESET cleared in MMIO and vDPA, VIRTIO_F_NOTIF_CONFIG_DATA cleared in all transports, VIRTIO_F_ADMIN_VQ and VIRTIO_F_SR_IOV cleared in vDPA) via a mechanical compensation table in the Phase 2 review. v1.4.6 and v1.5.1 runs identified the same architectural asymmetry (REQ-010: "Modern PCI compensates; MMIO/vDPA do not") but downgraded the finding to QUESTION-001 instead of escalating to BUG, so the four bugs never reached BUGS.md. v1.5.2 closed this gap with the Phase 1 cartesian use-case rule + Phase 2 mechanical compensation grid (BUG-default classification on whitelist/parity/compensation cells). Item retained here as historical context.

2. **v1.5.3.1 deferred items.** Five Phase 5 items deferred per wall-clock budget — see `Quality Playbook/Reviews/v1.5.4_backlog.md` B-1 through B-3 for the deferral rationale. The substantive no-regression evidence already shipped (`--benchmark` PASS for all 6 cells; Phase 4 skill-checks SKIP on Code; no `bin/run_playbook.py` changes shipped in v1.5.3); the v1.5.3.1 patch will close the full-playbook-sweep + opus-cross-model gates.

3. **TDD execution compliance.** Only Claude Code reliably creates red/green log files. Copilot and Cursor skip the step despite v1.3.47's six insertion points (not yet tested on v1.3.47). If v1.3.47 doesn't fix it, a post-run script that mechanically runs the TDD cycle may be needed. (v1.5.7's TDD-credibility arc 089m–089q hardened the gate around this — WARN on honest `NOT_RUN`, FAIL on a RED/GREEN receipt that admits non-execution, a probe-first runner-env contract — see `VERSION_HISTORY.md` and `CHANGELOG.md`.)

4. **Rate limits.** Running 6+ repos simultaneously through iteration cycles triggers Copilot's 54-hour cooldown. Users need to stagger runs (2-3 repos at a time) or use Claude Code / Cursor.

5. **Cursor workspace contamination.** Cursor reads sibling directories and imports findings from prior runs. Repos must be isolated in their own parent directory.

6. **Curation-algorithm 171-floor on QPB self-audit.** The v1.5.3 Phase 5 Stage 5A `curate_requirements.py` algorithm settles at 171 REQs on QPB (above the brief's [80, 110] target). Cause: 1007 accepted REQs collapse to 171 partitions each with ≥1 distinct post-Jaccard REQ; K=1 per partition is the floor. Cross-partition consolidation is needed to land in the band — tracked as v1.5.4 backlog B-4. Acceptable for v1.5.3 ship per the brief's "settle at whatever count the algorithm produces and document the calibration tension" allowance.

## Making changes to the skill

**Always back up before editing.** Copy any file you're about to modify to a `.bak` version first.

**Test on at least 2 repos after changes.** One large (virtio or cobra) and one small (chi). Check both baseline and at least one iteration strategy.

**Update the version.** The `version:` field in SKILL.md metadata must be bumped for every change. All generated artifacts stamp this version, and mismatches cause quality_gate.py failures.

**Run quality_gate.py after testing.** The gate validates artifact conformance mechanically. If it passes on your test repos, the change is safe to commit.

**Update TOOLKIT.md and this file.** If your change affects how users run the playbook or how maintainers work on it, update the relevant context file.
