# Quality Playbook v1.5.6 — Implementation Plan

*Companion to: `QPB_v1.5.6_Design.md`*
*Status: drafted 2026-05-03 alongside the v1.5.6 design. Implementation begins after operator review.*
*Depends on: v1.5.5 shipped (tag `v1.5.5` on origin); `1.5.6` branch already open from v1.5.5; the `2026-05-02-pattern7-displacement-recovery/` cycle directory scaffolded.*

---

## Operating Principles

- **One AI session per implementation phase.** Phases proceed sequentially. State lives in the filesystem (`run_state.jsonl` for the cycle phase, the runner folder for the orchestration-pattern phase, `git` for the source-edit phases). No in-memory state survives between phases.
- **Cowork-orchestrator / Claude-Code-worker pattern is the default execution mode.** v1.5.6 work is the first release implemented with this pattern documented in `AI_ORCHESTRATION_PATTERNS.md` (which Phase 1 itself produces). Cowork drives planning and Council coordination; the Claude Code worker (in `Quality Playbook/v1.5.6_runner/`) does the QPB-source edits per the workspace CLAUDE.md "diagnosis-then-Claude-Code lane" rule.
- **`SKILL.md` and the playbook phase architecture are unchanged.** v1.5.6 doesn't modify the divergence model, the six-phase architecture, the iteration strategies, or the quality gate. The single playbook-prose change is one line in `references/exploration_patterns.md` (Pattern 7 budget cap), and only if the cycle's terminal verdict is `ship` or `iterate<cap`.
- **Each phase has a Council review.** Three flat lenses per phase, per CALIBRATION_PROTOCOL.md Mode 1 nested-panel rules from the workspace CLAUDE.md. Lenses vary per phase but always cover correctness, scope discipline, and operator-readability.
- **Honest framing on the Pattern 7 cycle outcome.** Phase 2's audit reports what the data showed, not what makes the release look good. A `revert` verdict is a valid outcome.
- **Backward compatibility on install paths.** Phase 3's `bin/install_skill.py` is additive; the manual-copy install paths in the README and ai_context docs continue to work post-v1.5.6.
- **Don't touch v1.6 surfaces.** Requirements Review work (REQ schemas, Wiegers attributes, targeted re-derivation) is out of scope for every phase.
- **Verify before claiming completion.** Per the workspace CLAUDE.md rule: don't claim a push has shipped, a tag has moved, a test has passed, or a phase has finished without direct observation of the actual end state.

---

## Phase 0 — v1.5.5 Stabilization Confirmation

Goal: confirm v1.5.5 is shipped and stable; the `1.5.6` branch is at the expected commit; the cycle directory is intact; the model-comparison benchmark sweep is not in conflict with planned v1.5.6 work.

Work items:

- `git ls-remote origin v1.5.5 1.5.5 1.5.6 main` returns the expected SHAs (per the v1.5.5 ship verification done immediately before v1.5.6 design authoring).
- Local `1.5.6` branch HEAD matches `origin/1.5.6`.
- `python -m unittest discover bin/tests` passes on the `1.5.6` branch with no regressions vs. v1.5.5 baseline.
- `~/Documents/AI-Driven Development/Quality Playbook/Calibration Cycles/2026-05-02-pattern7-displacement-recovery/` directory exists; `run_state.jsonl` contains `_index` and `cycle_start` events; no other events have been written.
- Confirm with the operator that the model-comparison benchmark sweep, if running, will not require modifying `references/exploration_patterns.md` or `SKILL.md` for the duration of v1.5.6 development. (The sweep operates against the v1.5.5 tag; v1.5.6 work is on the `1.5.6` branch; they should not conflict, but explicit confirmation removes ambiguity.)
- Read `~/Documents/AI-Driven Development/CLAUDE.md` end-to-end (workspace conventions). Confirm "diagnosis-then-Claude-Code lane" rule is current.
- Read `ai_context/DEVELOPMENT_PROCESS.md` end-to-end. Confirm any rule changes since the v1.5.5 docs were authored are noted.

Deliverable: a Phase 0 confirmation note posted to chat with: SHAs verified, test suite green, cycle directory intact, model-comparison non-conflict confirmed, working tree clean.

Gate to Phase 1: all of the above confirmed.

---

## Phase 1 — `ai_context/AI_ORCHESTRATION_PATTERNS.md`

Goal: document the orchestrator/worker pattern as it has been used in QPB development, written for adopters first and AI sessions second. This is the first deliverable to ship because (a) it's doc-only, lowest-risk, easiest to revise post-Council; (b) the pattern is the implementation approach for Phases 2 and 3, so documenting it first means later phases reference an existing canonical doc rather than describing the pattern inline.

Work items:

- Spin up the v1.5.6 worker: a Claude Code session pointed at `~/Documents/AI-Driven Development/Quality Playbook/v1.5.6_runner/`. The runner folder is created with `instructions/`, `outputs/`, and an empty `STATUS.md`. The first instruction file in `instructions/001-author-orchestration-patterns-doc.md` carries the brief.

- The worker drafts `ai_context/AI_ORCHESTRATION_PATTERNS.md` per the content outline in the v1.5.6 Design doc:
  1. The pattern, named.
  2. Folder convention.
  3. Instruction file format.
  4. Output file format.
  5. Lifecycle.
  6. Why this pattern exists, in QPB's context.
  7. When to use this pattern vs. alternatives.
  8. **Applying this pattern in your own project (adopter-grade).** Concrete steps for an adopter to use the pattern outside QPB development — set up the runner folder, brief the worker session, write instruction files, drop a STOP file when done.
  9. Worked example: v1.5.5 ai_context-refresh runner (`v1.5.5_runner/`).
  10. Worked example: model-comparison runner (`model-comparison_runner/`).
  11. Cross-references to workspace CLAUDE.md, `agents/calibration_orchestrator.md`, `ai_context/DEVELOPMENT_PROCESS.md`, `AGENTS.md`.

- Adopter-grade scope means the pattern descriptions stay general enough to lift outside QPB. Worked examples cite QPB-internal artifacts as illustration, but the pattern itself is described in terms an adopter can apply without reading QPB source.

- Worked-example sources to read first:
  - `~/Documents/AI-Driven Development/Quality Playbook/v1.5.5_runner/instructions/005-refresh-ai-context.md` (the actual v1.5.5 instruction file).
  - The corresponding `outputs/` file from that runner.
  - The model-comparison runner's spin-up prompt (drafted in the prior Cowork session). If the model-comparison runner has been launched and has produced its own runner folder, read the early instruction/output files for content; otherwise describe the pattern from the spin-up prompt.

- Worker writes the doc to `ai_context/AI_ORCHESTRATION_PATTERNS.md`. Length target: 300-450 lines (slightly longer than originally planned to accommodate the adopter-grade application section and worked examples).

- Cross-reference updates:
  - `ai_context/DEVELOPMENT_PROCESS.md`: add a one-line pointer in the relevant orchestration section: "For coordinating two AI sessions through a shared directory, see `AI_ORCHESTRATION_PATTERNS.md`."
  - `agents/calibration_orchestrator.md`: add a "Compare with `AI_ORCHESTRATION_PATTERNS.md`" cross-reference clarifying the difference between single-session and multi-session orchestration.
  - `README.md`: a one-line addition to the "Roadmap" / "What's new in v1.5.6" pointing at the new doc as adopter-relevant material (deferred to Phase 5 release-notes drafting).

- Worker commits in two logical commits on the `1.5.6` branch:
  1. The new `ai_context/AI_ORCHESTRATION_PATTERNS.md`.
  2. The cross-reference updates in `DEVELOPMENT_PROCESS.md` and `calibration_orchestrator.md`.

Deliverable: `ai_context/AI_ORCHESTRATION_PATTERNS.md` exists; cross-references consistent; two commits land on `1.5.6`.

Council review (3 flat lenses, nested panel per workspace CLAUDE.md):
- **Pattern fidelity:** does the doc accurately describe how the v1.5.5 runner and model-comparison runner actually used the pattern? Spot-check by comparing doc claims against the actual instruction/output files.
- **Adopter-grade test:** an AI session that hasn't seen QPB development reads the doc and is asked to set up the pattern in a hypothetical adopter project. Does the doc give them enough to do it? Verify by handing the doc + a synthetic adopter task to a fresh sub-agent and checking the output.
- **Scope discipline:** does the doc avoid prescribing speculative future directions or making claims about generalization that the QPB-internal evidence doesn't support? Worked examples are evidence; broader claims need to be hedged accordingly.

Gate to Phase 2: doc committed; cross-references consistent; Council ship verdict (any harsh verdict triggers fix-up commit + second-round Council).

---

## Phase 2 — Pattern 7 displacement-recovery cycle execution

Goal: execute the cycle to terminal state. First end-to-end use of `agents/calibration_orchestrator.md` Mode 1 with v1.5.5's autonomous infrastructure. Validates the orchestration infrastructure.

Work items:

- **Cycle pre-flight (Step 1 of CALIBRATION_PROTOCOL):**
  - Confirm cycle directory `~/Documents/AI-Driven Development/Quality Playbook/Calibration Cycles/2026-05-02-pattern7-displacement-recovery/` is intact (only `_index` and `cycle_start` events).
  - Confirm `references/exploration_patterns.md` Pattern 7 budget cap is currently "3-5 highest-impact composition seams per pass" (the pre-lever value).
  - Confirm benchmark repos (chi-1.3.45, chi-1.5.1, virtio-1.5.1, express-1.3.50) are present under `~/Documents/QPB/repos/archive/` with the historical baselines available.
  - Confirm `claude` CLI is operational and `bin/run_playbook.py` is executable.

- **Pre-lever benchmark runs (Step 2):**
  - For each of chi-1.3.45, chi-1.5.1, virtio-1.5.1, express-1.3.50: run the playbook end-to-end. Capture `quality/BUGS.md`, `quality/EXPLORATION.md`, `quality/REQUIREMENTS.md`, `cell.json`.
  - Subprocess invocation: spawn-and-resume per `agents/calibration_orchestrator.md` (background `nohup`, capture PID, return control, periodic re-invoke to advance).
  - Each run logs to `Calibration Cycles/2026-05-02-pattern7-displacement-recovery/run_state.jsonl` with phase events.
  - Acceptance: four pre-lever `cell.json` files written; per-benchmark `quality/BUGS.md` files captured.

- **Apply lever (Step 3):**
  - Edit `references/exploration_patterns.md`. Pattern 7 budget cap line changes from "3-5 highest-impact composition seams per pass" to "2-3 highest-impact composition seams per pass." One-line edit.
  - Commit on `1.5.6` branch: "v1.5.6 lever: Pattern 7 budget cap 3-5 → 2-3 (displacement-recovery cycle)."

- **Post-lever benchmark runs (Step 4):**
  - For each of the four benchmarks: re-run the playbook with the new lever. Capture the same artifacts.
  - Acceptance: four post-lever `cell.json` files; per-benchmark post-lever `quality/BUGS.md`.

- **Delta computation (Step 5):**
  - For each benchmark, compute per-bug deltas: which pre-lever bugs were missed post-lever, which post-lever bugs were missed pre-lever, which were caught both times.
  - Compute aggregate recall delta per benchmark.
  - Specific check: did PathRewrite return on chi-1.3.45? Did AllowContentEncoding return on chi-1.3.45? Did Pattern 7's mount-context findings (cycle 1) survive?

- **Cycle audit (Step 6):**
  - Write `Calibration Cycles/2026-05-02-pattern7-displacement-recovery/audit.md` with verdict (`ship` / `revert` / `iterate<cap` / `halt-iterate-cap`), supporting evidence, hypothesis disposition.
  - Audit must be honest: report what the data shows, not what makes the release look good.

- **Lever Calibration Log entry (Step 7):**
  - Append entry to `docs/process/Lever_Calibration_Log.md` with cycle metadata, lever change, verdict, link to audit.

- **Visualizations (Step 8):**
  - Run `python -m bin.visualize_calibration ~/Documents/AI-Driven\ Development/Quality\ Playbook/Calibration\ Cycles/2026-05-02-pattern7-displacement-recovery/`.
  - Produces four artifacts (per-bug heatmap, lever heatmap, recall trajectory, Mermaid graph) into the cycle's `visualizations/` directory.

- **Cell.json archival (Step 9):**
  - Each `cell.json` written to `metrics/regression_replay/<timestamp>/` per the v1.5.5 schema (`references/run_state_schema.md`).

- **Iteration handling:**
  - If verdict is `iterate<cap`: adjust lever value (e.g., to "2-4" or revert to "3-5"), log the iteration, return to Step 4 with iteration counter incremented. Cap is 3.
  - If `halt-iterate-cap`: audit explains the impasse; v1.5.6 ships at whichever iteration had the best aggregate verdict.
  - If `ship` or `revert`: proceed to Council review.

- **If the cycle's verdict is `revert`:** revert the lever change with a follow-up commit on `1.5.6`: "v1.5.6 lever revert: Pattern 7 budget cap restored to 3-5 per cycle audit." `references/exploration_patterns.md` returns to its v1.5.5 state. The audit and Lever_Calibration_Log entry are preserved as the cycle's deliverables; v1.5.6 still ships.

Deliverable: cycle reaches terminal state; audit, log entry, visualizations, cell.json files all present; lever change committed (and possibly reverted) on `1.5.6`.

Council review (3 flat lenses, nested panel):
- **Methodology rigor:** were the pre/post-lever runs comparable (same benchmarks, same model, no other prose changes)? Were the deltas computed correctly per CALIBRATION_PROTOCOL?
- **Statistical interpretation honesty:** is the verdict supported by the data, with the small-sample caveats CALIBRATION_PROTOCOL prescribes? No back-fitting to a desired outcome?
- **Mount-context preservation check:** if the cycle's verdict is `ship`, did Pattern 7's cycle-1 mount-context findings survive the lower budget cap? Spot-check by re-reading post-lever `BUGS.md` for the previously-Pattern-7-found mount-context bugs.

Gate to Phase 3: cycle terminal; Council ship verdict on the audit (Council can ship a `revert` audit if the data supports `revert`); v1.5.5's autonomous orchestration infrastructure validated end-to-end.

---

## Phase 3 — Adopter-facing distribution

Goal: AI-agent-driven turnkey install via `bin/install_skill.py` with `AGENTS.md` as the canonical install procedure, opinionated defaults for missing-documentation runs, revised README quickstart, cross-platform support (Windows / macOS / Linux).

Work items:

- **`bin/install_skill.py`:**
  - Implement per the v1.5.6 Design "Adopter-facing distribution" section.
  - **Multi-environment detection** via a config table at the top of the script (one line per known AI-tool environment so adding a new one is a one-line change):
    - `.claude/` → propose `.claude/skills/quality-playbook/`.
    - `.github/` → propose `.github/skills/quality-playbook/`.
    - `.cursor/` → propose `.cursor/skills/quality-playbook/`.
    - `.continue/` → propose `.continue/skills/quality-playbook/`.
    - (Add others as the project learns about them.)
  - **`--target <path>` flag** to install into an arbitrary directory, overriding auto-detection. Required when none of the known environments are present and the agent or operator wants to install anyway.
  - **Cross-platform**: `pathlib.Path` exclusively (no string `/` concatenation), explicit `encoding='utf-8'` and `newline=''` on all text I/O, Python 3.9+ compatible. No platform-specific shell calls.
  - **Idempotency**: re-running updates files in place, preserves operator-edited copies as `<file>.operator-backup-<UTC-timestamp>`.
  - **Smoke check at install completion**: `quality_gate.py` import-and-help-text invocation; `SKILL.md` markdown parses with expected frontmatter; `references/exploration_patterns.md` contains expected pattern sections.
  - **Output format**: structured (key=value per line) by default for AI-agent consumption; `--verbose` flag adds human prose.
  - **Refusal modes**: refuses to run outside any obvious target (no `.git/`, no detected env, no `--target`); refuses if files exist at destination but the install bundle's version is older than what's there (no downgrades).
  - Out of scope: package management, venv setup, IDE configuration, agent-template generation.

- **`AGENTS.md` install-procedure section:**
  - Add a new section: "Installing the Quality Playbook into a target repo." Tells the AI agent doing the install:
    1. Confirm the operator's target repo and the AI tool they use.
    2. Clone QPB to a known location (or confirm an existing clone).
    3. Run `bin/install_skill.py` against the target — auto-detection by default, or `--target <path>` if the operator specifies a custom location.
    4. Inspect the structured output. Surface any `smoke_check_failed=true` lines to the operator with the diagnostic content.
    5. If install succeeds, report the install location and the next steps for invoking the playbook.
  - The section is short (≤30 lines) and factual; the script does the work, AGENTS.md just sequences the agent's actions.

- **Unit tests at `bin/tests/test_install_skill.py`:**
  - Install into tempdir with `.claude/` → smoke check passes.
  - Install into tempdir with `.github/` → smoke check passes.
  - Install into tempdir with `.cursor/` → smoke check passes.
  - Install into tempdir with neither + no `--target` → refuses with helpful error.
  - Install with `--target <arbitrary-path>` overriding auto-detection → installs at the override.
  - Idempotency: run twice; second run preserves operator edits as backup.
  - Smoke check catches a deliberately-broken `quality_gate.py`.
  - Output format: structured key=value lines parseable.
  - Cross-platform sanity: a Windows-style path string passed via `--target` is handled correctly through `pathlib.Path` (use `pathlib.PureWindowsPath` in the test where appropriate to avoid OS dependence in CI).

- **Opinionated defaults: missing-documentation downgrade:**
  - Modify Phase 1 entry in `bin/run_playbook.py` (or wherever the Phase 1 dispatch lives) to check `reference_docs/` and `reference_docs/cite/` at start.
  - If both are empty: log a `documentation_state: code_only` event to `run_state.jsonl`; prepend an opening section to `quality/EXPLORATION.md` explaining the downgrade with a pointer to `references/code-only-mode.md`.
  - Create `references/code-only-mode.md` (new file) explaining: what to expect, why bug counts may be lower, where to put docs to improve the next run. ~50 lines.
  - Run-state schema update at `references/run_state_schema.md`: document the `documentation_state` event field.

- **Unit tests at `bin/tests/test_documentation_state.py`:**
  - Phase 1 with empty `reference_docs/` produces the documentation-state event and the opening section in `EXPLORATION.md`.
  - Phase 1 with populated `reference_docs/` does NOT produce the event (existing behavior preserved).
  - The `code-only-mode.md` doc loads and is reachable from the EXPLORATION pointer.

- **Revised README quickstart:**
  - "How to use the Quality Playbook to find bugs in your code" section: Step 1 becomes "install the skill (have your AI tool run `bin/install_skill.py`, or run it directly)"; current Step 1 (provide documentation) becomes Step 2; following steps renumbered.
  - Step 1 prose makes clear that the AI-tool-driven path is the default — instructs the reader to ask their Claude Code / Cursor / etc. session to read AGENTS.md and run the install procedure.
  - Includes the opt-out: "If you've already manually copied SKILL.md and quality_gate.py to your skills directory, skip this step."
  - "What's new in v1.5.6" subsection added (drafted in Phase 5; placeholder added here).

- Worker commits on `1.5.6` in four logical commits:
  1. `bin/install_skill.py` + tests + smoke-check.
  2. `AGENTS.md` install-procedure section.
  3. Missing-documentation downgrade in `bin/run_playbook.py` + `references/code-only-mode.md` + tests + schema update.
  4. README quickstart restructure.

Deliverable: install script runs against the four detected environments + arbitrary folder; AGENTS.md tells the agent how to install; opinionated default observable via run-state log; README quickstart restructured for AI-tool-driven default.

Council review (3 flat lenses, nested panel):
- **AI-agent-driven install test:** a fresh AI sub-agent reads AGENTS.md cold and is asked to install QPB into a tempdir target with `.cursor/`. Does the agent successfully drive the script and report results? If it gets stuck, AGENTS.md or the script's output format is revised.
- **Backward compatibility:** does the manual-install path still work as documented? Spot-check the `cp` commands the existing ai_context docs prescribe; they should still produce a working install equivalent to `bin/install_skill.py`.
- **Code-only mode framing:** does the `EXPLORATION.md` opening section make clear what the operator is and isn't getting? Or does it sound like a failure when it's a documented mode?

Gate to Phase 4: install script + AGENTS.md + downgrade + README updates committed; Council ship.

---

## Phase 4 — Validation Against Benchmark Repos

Goal: verify the v1.5.6 changes don't break existing benchmark behavior.

Work items:

- Run `setup_repos.sh` (the same script the model-comparison sweep uses) against the v1.5.6 working tree. Confirm benchmark workspaces produced are equivalent to v1.5.5-produced workspaces, modulo:
  - The Pattern 7 budget cap value in the `references/exploration_patterns.md` content (if `ship` verdict).
  - The new `bin/install_skill.py` file present in the install bundle.
  - The new `references/code-only-mode.md` file present.
  - The new `ai_context/AI_ORCHESTRATION_PATTERNS.md` file present.
  - The updated `AGENTS.md` with the install-procedure section.
  - No other diffs.

- Run the playbook against one benchmark (chi-1.3.45 is fastest) on the v1.5.6 branch. Confirm:
  - Phase 1 produces a non-empty `EXPLORATION.md`.
  - If the budget cap was lowered (verdict `ship`), Pattern 7's section in EXPLORATION reflects the new "2-3" cap rather than "3-5."
  - Phase 6 runs to completion; `BUGS.md` is produced.
  - Quality gate passes or fails informatively.

- Run the playbook against one benchmark with `reference_docs/` deleted to validate the missing-documentation downgrade path:
  - `documentation_state: code_only` event in `run_state.jsonl`.
  - Opening section in `EXPLORATION.md` matches spec.
  - Phase 1 still produces an `EXPLORATION.md` (does not abort).
  - `quality/PROGRESS.md` reflects the downgrade.

- Run `python -m unittest discover bin/tests` end-to-end. All pre-v1.5.6 tests pass; new v1.5.6 tests pass. Total green.

- **Cross-platform install validation:**
  - macOS: install script runs end-to-end on the development machine.
  - Linux: install script runs end-to-end in a Linux container or VM (Ubuntu LTS or similar).
  - Windows: install script runs end-to-end on Windows 10/11 (PowerShell or Windows Terminal). Specifically validate `pathlib.Path` handling, CRLF preservation in installed files, and the `--target` flag with a Windows-style path. If a Windows machine isn't available, document the limitation and run a Wine-based or container-based proxy test; if neither is available, defer to a v1.5.7 patch with a clear "Windows untested" note in the v1.5.6 release notes.

- **AI-agent-driven adopter walkthrough:**
  - Pick a fresh tempdir, clone QPB into it.
  - Spin up a fresh Claude Code (or equivalent) session in that tempdir with no v1.5.6 context.
  - Ask it: "I want to use the Quality Playbook on this codebase. Read AGENTS.md and set it up."
  - Verify the agent reads AGENTS.md, runs `bin/install_skill.py`, surfaces the smoke check results, and reports completion to the operator.
  - The operator follows up: "Now do a single playbook run on the chi-1.3.45 benchmark."
  - Verify install + first run completes inside 30 minutes, with the agent driving.
  - Document any friction at any step.

Deliverable: validation report at `Quality Playbook/Reviews/QPB_v1.5.6_Validation_Report.md` covering: setup_repos parity, regular run, code-only run, full test suite, cross-platform install, AI-agent-driven adopter walkthrough. Friction noted at any step is dispositioned: fix in Phase 4.5 (return to Phase 3 for revisions), defer to v1.5.7 with documented carry-forward, or accept as known.

Council review (3 flat lenses, nested panel):
- **Validation completeness:** does the report cover what could realistically break in an adopter run, or does it test only the happy path? Specifically does it cover all three platforms?
- **Honest framing on adopter friction:** does the walkthrough report what actually happened, or what would have happened if everything worked? Quote the actual stuck points. If Windows wasn't truly tested, say so and don't pretend.
- **Regression scan:** any v1.5.5-shipped behavior that v1.5.6 inadvertently changed?

Gate to Phase 5: validation report committed; any blocking friction resolved; Council ship.

---

## Phase 5 — Mechanical Release

Goal: ship v1.5.6.

Work items:

- Bump `RELEASE_VERSION` in `bin/benchmark_lib.py` from `1.5.5` to `1.5.6`.
- Bump `SKILL.md` frontmatter `version:` from `1.5.5` to `1.5.6`. Bump `SKILL.md` banner. Bump every `skill_version` JSON example. Bump every "Generated by Quality Playbook" template. (Same edit pattern as v1.5.5 / v1.5.4.)
- Bump `README.md` version stamp (line 3 of the current README).
- Add "What's new in v1.5.6" section to README covering:
  - Turnkey install via `bin/install_skill.py`.
  - Opinionated defaults: missing-documentation runs proceed in code-only mode with explicit framing.
  - Revised quickstart: install is Step 1.
  - `ai_context/AI_ORCHESTRATION_PATTERNS.md` documenting the orchestrator/worker pattern.
  - Pattern 7 displacement-recovery cycle outcome (ship verdict with new "2-3" budget cap, or revert verdict with "3-5" preserved). Link to the audit.
- Update Roadmap section in README: move v1.5.6 from "Design forthcoming" to "shipped"; populate links to the new design and implementation-plan files.
- Run `python -m unittest discover bin/tests` — must pass (1017+ tests).
- Verify working tree clean except for the version-bump commit content.
- Commit, tag `v1.5.6`. Push branch. Push tag.
- Fast-forward `main` to `v1.5.6`. Push `main`.
- Create `1.5.7` branch from `v1.5.6`. Push.
- **Verify origin via `git ls-remote origin v1.5.6 1.5.6 main 1.5.7` per the workspace CLAUDE.md verify-before-claim rule.** Don't claim shipped without seeing origin SHAs match.

Deliverable: v1.5.6 tagged on origin; `main` at v1.5.6; `1.5.7` branch open.

Gate to v1.6.0 work: all of the above verified.

---

## Risks and Mitigations

- **Pattern 7 cycle takes longer than expected.** Eight playbook runs (4 pre-lever + 4 post-lever) at ~20-30 min each is 3-4 hours minimum, longer with iteration. Mitigation: use the spawn-and-resume pattern in `agents/calibration_orchestrator.md` rather than blocking on each run. The v1.5.5 infrastructure is designed for this; Phase 2 is the first real test.

- **Cycle verdict is `revert` and v1.5.6 ships with no lever change.** This is explicitly OK per the v1.5.6 Design — a reverted cycle is a valid outcome; the deliverable is the audit and Lever_Calibration_Log entry, not the lever change itself. The release notes are clear about the verdict.

- **`bin/install_skill.py` doesn't handle some adopter environment.** Mitigation: scope is intentionally narrow (`.claude/`, `.github/`, operator-supplied path). Other environments are documented as "operator supplies path manually," not "first-class detection." Adopter walkthrough in Phase 4 will surface common failure cases.

- **Missing-documentation downgrade confuses operators who expected the run to abort.** Mitigation: opening section in `EXPLORATION.md` is explicit; the run-state log captures the downgrade for audit; opt-out flag (`--require-docs`) is a documented v1.5.7 candidate if confusion surfaces.

- **`AI_ORCHESTRATION_PATTERNS.md` becomes prescriptive when it's meant to be descriptive.** Mitigation: Council review's plain-language test catches this — if a fresh AI session reads the doc and treats it as a prescription, the doc framing is wrong. Revise.

- **Model-comparison benchmark sweep collides with v1.5.6 cycle work.** Both could try to run playbook subprocesses against benchmark repos simultaneously. Mitigation: model-comparison runs in `repos/model-comparison/round<N>/<repo>-1.5.5/` (separate working directories from v1.5.6 cycle's `repos/archive/<benchmark>/`); the two efforts coordinate via separate orchestrator/worker folders, so each side knows when the other is running a playbook subprocess. Phase 0 explicitly verifies the two are non-conflicting.

- **`setup_repos.sh` parity check fails.** If v1.5.6 changes inadvertently break `setup_repos.sh` against the v1.5.6 tag, the model-comparison sweep is disrupted post-v1.5.6 ship. Mitigation: Phase 4 explicitly tests `setup_repos.sh` against the v1.5.6 working tree before tag.

---

## Out-of-band carry-forward to v1.5.7 / v1.6.0

Anything that surfaces during v1.5.6 development pointing toward a future release goes into a carry-forward note, not absorbed into v1.5.6 scope:

- **Skill-as-code adopter persona deep work** (Persona 19) — if the adopter walkthrough in Phase 4 surfaces gaps specific to skill-as-code targets, document them as v1.5.7 candidates. Don't expand v1.5.6 to absorb them.
- **`--require-docs` opt-out flag** — if missing-documentation downgrade confuses operators in validation, add to v1.5.7.
- **Windows path handling in `bin/install_skill.py`** — if Phase 4 surfaces Windows-specific failures, v1.5.7.
- **Adopter-grade orchestration-patterns doc** — if the v1.5.6 doc is QPB-development-grade, an adopter-facing version that lets adopters use the pattern in their own workflow is v1.5.7.
- **Pattern 7 cycle iteration findings that suggest a different lever change** (e.g., "the budget cap isn't the right lever; ordering is") — capture in `Lever_Calibration_Log.md` as a future cycle proposal. Don't run a different cycle in v1.5.6.
- **Anything pointing at v1.6 (Requirements Review)** — capture as carry-forward in the v1.6 design's pending notes; don't preempt v1.6.

This list is updated as Phase 2-4 progress; the final list is part of the Phase 5 release-notes drafting.
