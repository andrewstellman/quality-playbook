# Quality Playbook v1.5.6 — Design Document

*Status: drafted 2026-05-03 immediately following v1.5.5 ship. Implementation begins after operator review of this doc and the companion Implementation Plan.*
*Authored: 2026-05-03*
*Owner: Andrew Stellman*
*Depends on: v1.5.5 shipped (autonomous improvement-loop infrastructure: `quality/run_state.jsonl`, `PROGRESS.md`, phase-boundary cross-validation, Phase 5 source-edit guardrail, `agents/calibration_orchestrator.md`, four matplotlib visualizations).*

> **Where v1.5.6 sits in the arc.** v1.5.5 shipped the orchestration infrastructure for the improvement loop — instrumentation, cross-validation, resume capability, the calibration-cycle orchestrator template, and the visualization pipeline. v1.5.6 is the first release that actually exercises that infrastructure end-to-end, plus two adjacent items that became visible only after v1.5.5 landed: adopters trying to install the playbook hit friction the v1.5.5 install path didn't address, and the orchestrator/worker pattern that emerged during v1.5.5 development is being used in enough places now that it needs to be documented before more sessions take dependencies on it. v1.6 (Requirements Review) and v1.7 (Statistical Process Control) come after v1.5.6; this release is deliberately scoped tight so v1.5.5's infrastructure gets validated against real cycle data before the QI half of the roadmap begins.

---

## Motivation

### Three deliverables, one release, picked together for a reason

v1.5.6 ships three things:

1. **Pattern 7 displacement-recovery cycle execution.** The deferred Item G from v1.5.5. The first end-to-end run of `agents/calibration_orchestrator.md` against a real lever pull, using the v1.5.5 autonomous infrastructure as designed.

2. **Adopter-facing distribution.** Turnkey install path so an operator who wants to try QPB doesn't have to read `ai_context/` to figure out where files go. Includes an install script, opinionated defaults, a friendlier first-run UX, and a README quickstart written for "operator who just heard about QPB" rather than "operator who has been following development."

3. **AI orchestration patterns documentation.** A new `ai_context/AI_ORCHESTRATION_PATTERNS.md` documenting the orchestrator/worker pattern that emerged during v1.5.5 development: a chat-driving AI session (orchestrator) controls a long-lived coding AI session (worker) by exchanging files in a shared directory (`instructions/`, `outputs/`, `STATUS.md`, and a `STOP` sentinel file). The pattern is in active use across multiple workstreams — it was used to refresh v1.5.5's `ai_context/` files mid-ship, is being used by the model-comparison benchmark sweep, and is the implementation approach for v1.5.6's own Pattern 7 cycle execution. Documenting it stabilizes the convention before further work depends on it.

These three are together because they share one property: **each one validates v1.5.5 retroactively**. The Pattern 7 cycle validates the calibration orchestrator. Adopter distribution validates that the playbook is portable beyond Andrew's machine. The orchestration-pattern doc validates that the orchestrator/worker pattern is generalizable, not bespoke to v1.5.5's release ship. Bundling them produces a single release whose theme is "v1.5.5 actually works, here are the proofs," rather than three small uncoordinated point releases.

### Why each was deferred to v1.5.6 rather than landed in v1.5.5

- **Pattern 7 cycle.** Originally Item G in `QPB_v1.5.5_Remaining_Work.md`. The cycle requires hours of background playbook runs against four benchmarks (8+ playbook executions per iteration, up to 24 with the 3-iteration cap). v1.5.5 ship pressure took priority over running the cycle to terminal state; the cycle directory was scaffolded (`_index` + `cycle_start` events written) and execution was deferred per the v1.5.5 published roadmap line.

- **Adopter distribution.** Wasn't in v1.5.5 scope. The need surfaced post-ship from two threads: the v1.5.5 README rewrite that put the "Need help? Just ask your AI" section first under the TOC made the gap between "easy AI-mediated path" and "actual install" visible, and the model-comparison benchmark sweep planning made it clear that an operator running QPB in a fresh environment can't bootstrap from `setup_repos.sh` alone — they need a playbook-install path that doesn't assume they've already cloned QPB.

- **AI orchestration patterns documentation.** The pattern crystallized during v1.5.5 development — too new to document mid-flight without prematurely freezing it. Three sessions in a row used the pattern (the v1.5.5 ai_context-refresh watcher, the v1.5.6 implementation worker plan, the model-comparison benchmark worker plan), each independently re-deriving the convention. By v1.5.6 there's enough usage that documenting it stabilizes the pattern before v1.7's multi-cell calibration cycles take hard dependencies on it.

### What v1.5.6 explicitly does NOT do

It doesn't introduce new playbook capabilities. The skill prose, the phase architecture, the iteration strategies, the quality gate, the divergence model — all of those are stable. v1.5.6 changes only the operator surface (install path, distribution, documentation) and runs one calibration cycle whose lever change is a single number adjustment in `references/exploration_patterns.md`.

It doesn't touch v1.6 scope. Requirements Review is v1.6; v1.5.6 stays out of that surface entirely.

It doesn't ship statistical-control machinery. Control charts, run rules, multi-cell DoE — all v1.7. The Pattern 7 cycle in v1.5.6 produces one more cell of data; v1.7 builds the framework that consumes the accumulated cells.

---

## Scope

### Core deliverables

1. **Pattern 7 displacement-recovery cycle, executed to terminal state.**
   - Cycle directory: `~/Documents/AI-Driven Development/Quality Playbook/Calibration Cycles/2026-05-02-pattern7-displacement-recovery/`. Already scaffolded with `_index` and `cycle_start` events.
   - Lever: lower Pattern 7's budget cap in `references/exploration_patterns.md` from "3-5 highest-impact composition seams per pass" to "2-3 highest-impact composition seams per pass."
   - Benchmarks: chi-1.3.45, chi-1.5.1, virtio-1.5.1, express-1.3.50.
   - Iteration cap: 3.
   - Hypothesis: lowering Pattern 7's budget cap recovers PathRewrite and AllowContentEncoding (the two displacement regressions cycle 1 produced on chi-1.3.45) while preserving Pattern 7's mount-context findings.
   - Mechanism: `agents/calibration_orchestrator.md` Mode 1 (autonomous), unmodified. The cycle exists to validate the orchestrator template, not to test changes to it.
   - Terminal state: one of `ship`, `revert`, `iterate<cap`, or `halt-iterate-cap`.

2. **Turnkey adopter installation: `bin/install_skill.py` + opinionated defaults + revised README quickstart.**
   - `bin/install_skill.py`: a single Python script the adopter runs to copy `SKILL.md`, `quality_gate.py`, `references/`, `phase_prompts/`, `agents/`, and `bin/citation_verifier.py` into the right destination for their AI tool. Detects available tool environments (`.claude/skills/`, `.github/skills/`, `.cursor/skills/` if they exist) and emits a structured `event=detected_env_inside_target` line with the resolved install path; auto-detection by default, with `--target` and `--ai-tool <name>` flags as overrides when the operator wants explicit control or when auto-detection can't find a marker.
   - Opinionated defaults: when `reference_docs/` is empty in the target repo, the playbook proceeds with a documented downgrade rather than failing — Phase 1 produces requirements from code-only signals and the `quality/EXPLORATION.md` flags the missing-documentation state explicitly so the operator knows what they're getting.
   - Revised README quickstart: rewrite the "How to use the Quality Playbook to find bugs in your code" section so Step 1 is "run `bin/install_skill.py`" rather than "manually copy three files." The current Step 1 (provide documentation) becomes Step 2.
   - Preserves the existing manual-copy install paths — turnkey is additive, not a replacement. Adopters who prefer the manual flow keep the manual flow.

3. **`ai_context/AI_ORCHESTRATION_PATTERNS.md` documenting the orchestrator/worker pattern.**
   - Generic folder convention: `Quality Playbook/<runner-name>/{instructions,outputs,STATUS.md,STOP}` for the workspace side; the worker is a separately-launched Claude Code session pointed at that folder.
   - Documents both the pattern's mechanics (instruction-file format, output-file conventions, STATUS.md update cadence, STOP sentinel handling) and the rationale (storing state in the shared directory means each session is stateless across crashes, multiple workers can coexist with separate runner folders without conflict, and the orchestrator and worker can run different LLMs).
   - Includes a worked example showing the v1.5.5 ai_context-refresh runner (`v1.5.5_runner/`) and how the model-comparison and v1.5.6 implementation runners differ.
   - Documents the "diagnosis-then-Claude-Code lane" rule from the workspace CLAUDE.md as the canonical reason this pattern exists for QPB-source edits.
   - Cross-references `agents/calibration_orchestrator.md` (a related but distinct pattern: single session spawning subprocesses, not an orchestrator/worker pair).

### Operating principles

- **Pattern 7 cycle uses CALIBRATION_PROTOCOL Mode 1 unmodified.** No protocol changes; the only change is the lever value in `references/exploration_patterns.md`. If the protocol needs revision, that's a separate work item with its own Council review — not folded into v1.5.6.
- **Adopter distribution is additive.** Manual install paths remain functional. The turnkey path is a shortcut, not a replacement. Adopters who already use QPB don't need to migrate.
- **AI orchestration doc is descriptive.** It documents the pattern as currently used, with citations to the runner folders that demonstrated it. It does not prescribe a future direction or claim the pattern generalizes beyond QPB development.
- **Each phase has a Council review.** Three flat lenses per CALIBRATION_PROTOCOL.md Mode 1 nested-panel rules from the workspace CLAUDE.md.
- **Don't encroach on v1.6 scope.** Requirements Review is v1.6. v1.5.6 doesn't touch the requirements-derivation pipeline, REQ schemas, or the Wiegers-attribute UX surface.
- **Don't preempt v1.7 scope.** v1.5.6 produces one more cell of calibration data; it does not analyze the accumulated data with control charts, build a defect-rate dashboard, or migrate the prose defect catalog to JSON. All of that is v1.7.

### Out of scope (deferred to later releases)

- **Multi-cell calibration cycles** (factorial, Latin square, augmented designs). v1.7.
- **SPC machinery** (control charts, run rules, X/MR analysis on cell.json). v1.7.
- **SDLC defect-rate dashboard** (`bin/sdlc_defect_dashboard.py`, defect catalog migration to JSON). v1.7.
- **Cross-version trend tracking pipeline** (`bin/cross_version_trends.py`). v1.7.
- **Cross-operator workflow** (multi-operator data sharing). v1.8.
- **Requirements Review UX**. v1.6.
- **Skill-as-code adopter persona deep work** (Persona 19 from `TOOLKIT_TEST_PROTOCOL.md`). Possible v1.5.7 if the adopter distribution work surfaces gaps specific to skill-as-code targets.
- **Pattern 7 ordering experiments** (numeric vs. last position in the pattern walk). The v1.7 multi-cell cycle is the natural place to run a 2×2 factorial on budget cap × ordering. v1.5.6 only changes the budget cap.

---

## Design

### Pattern 7 displacement-recovery cycle

**Lever change.** In `references/exploration_patterns.md`, locate Pattern 7 (Composition and Mount-Context Awareness) and change the budget cap line from:

> Budget: 3-5 highest-impact composition seams per pass.

to:

> Budget: 2-3 highest-impact composition seams per pass.

This is a one-line edit. No other prose changes; the pattern's name, description, examples, and trigger conditions remain.

**Hypothesis being tested.** v1.5.4's Pattern 7 introduction measured +0.20 recall on chi-1.3.45 (4/10 → 6/10) but displaced PathRewrite and AllowContentEncoding (both caught by v1.5.3, both missed by v1.5.4). The likely mechanism: Pattern 7 instructs the playbook to inspect 3-5 composition seams per pass, and those inspection slots crowd out other inspections that would have surfaced PathRewrite and AllowContentEncoding. Lowering the cap to 2-3 should free inspection slots for the displaced bugs while keeping enough Pattern 7 coverage to find the mount-context bugs cycle 1 caught. The hypothesis is falsifiable — if the lower cap recovers neither displaced bug, or recovers them but loses Pattern 7's mount-context findings, the lever change is wrong.

**Cycle mechanics.** Per `ai_context/CALIBRATION_PROTOCOL.md` Mode 1 (autonomous):

1. Pre-flight verification (Step 1 already done — cycle directory scaffolded).
2. Pre-lever benchmark runs against all four benchmarks (chi-1.3.45, chi-1.5.1, virtio-1.5.1, express-1.3.50). Capture `quality/BUGS.md` per run.
3. Apply lever change to `references/exploration_patterns.md`.
4. Post-lever benchmark runs against the same four benchmarks.
5. Compute per-bug deltas: did PathRewrite return? AllowContentEncoding? Did Pattern 7's mount-context findings survive? Compute aggregate recall delta per benchmark.
6. Cycle audit at `Calibration Cycles/2026-05-02-pattern7-displacement-recovery/audit.md` with verdict and rationale.
7. Append entry to `docs/process/Lever_Calibration_Log.md`.
8. Generate visualizations via `bin/visualize_calibration.py <cycle-dir>`.
9. Council review of the cycle verdict (three flat lenses: methodology rigor, statistical interpretation honesty, mount-context preservation check).
10. Write `cell.json` per benchmark to `metrics/regression_replay/<timestamp>/`.

**Terminal-state mapping.** Per CALIBRATION_PROTOCOL Mode 1:
- `ship` if the cycle recovers ≥1 displacement bug AND preserves ≥80% of Pattern 7 mount-context findings. The lever change persists; v1.5.6 ships with the new budget cap.
- `revert` if neither displacement bug recovers, OR Pattern 7 mount-context findings drop ≥20%. The lever change is reverted; v1.5.6 ships with the v1.5.4 budget cap and an audit explaining why.
- `iterate` (with iteration<cap) if results are mixed and a different budget cap value is plausible. Adjust lever, rerun. Cap is 3 iterations.
- `halt-iterate-cap` if iteration cap reached without convergence. Audit explains the impasse; v1.5.6 ships at whichever budget cap had the best aggregate verdict.

**What "running cycle 2 end-to-end" actually validates.** v1.5.5 shipped the orchestration infrastructure — phase-boundary cross-validation, resume semantics, the source-edit guardrail (`validate_no_source_edits()`), the cycle orchestrator template. Running the full cycle exercises every piece of that under realistic conditions: long-running playbook subprocesses, intermediate state persisted to `run_state.jsonl`, possible mid-cycle interruptions and resumes, the source-edit guardrail running at end-of-iteration. If something is fragile, it surfaces here, not in someone else's adoption.

### Adopter-facing distribution

**`bin/install_skill.py` design.**

**Default usage mode: invoked by an AI coding agent.** Most adopters today install QPB by asking Claude Code, Cursor, or another AI coding assistant to set it up. The script is designed for that default — its prompts, error messages, and output format are structured so an AI agent reading them can act on them programmatically. Direct human invocation is supported but secondary.

**`AGENTS.md` is the canonical install procedure.** A new section in `AGENTS.md` tells the AI agent doing the install exactly what to do: identify the target repo, choose an install location (using the script's auto-detection, or following operator instructions for a custom location), invoke `bin/install_skill.py` with the right arguments, run the smoke check, report results to the operator. The AI agent handles operator interaction; the script handles the file-copy and validation steps. Adopters who run the script directly without an AI agent get the same behavior; the AGENTS.md section is what makes the agent-driven case reliable.

**Target environments.** The script detects known AI-tool environments and proposes a default install location, in priority order. Initial set:
- `.claude/` present → propose `.claude/skills/quality-playbook/`
- `.github/` present → propose `.github/skills/quality-playbook/`
- `.cursor/` present → propose `.cursor/skills/quality-playbook/`
- `.continue/` present → propose `.continue/skills/quality-playbook/`

The list is open-ended — additional environments are added as the project learns about them. Each entry is a single line in a config table at the top of the script, so adding a new tool is a one-line change without restructuring detection logic.

**Arbitrary folder via `--target <path>`.** A flag lets the agent (or operator) install into any directory, overriding auto-detection. `AGENTS.md` documents when to use this — for adopters using AI tools whose convention isn't yet known to the script, or whose layout is custom.

**Explicit AI-tool selection via `--ai-tool <name>` (added retroactively in v1.5.6).** Auto-detection requires the marker directory (`.claude/`, `.github/`, `.cursor/`, `.continue/`) to already exist in the target. Some AI tools — notably Cursor and GitHub Copilot — don't reliably create that directory on first project open, so adopters who explicitly told their AI agent which tool they're using would still hit `event=detection_failed` and have no clean recovery path beyond `mkdir <marker>` or computing a `--target` path manually. The `--ai-tool <name>` flag accepts `cursor`, `claude`, `copilot` (or `github` as an alias), or `continue`, maps to the canonical skill subdirectory (`.cursor/skills/quality-playbook/`, `.claude/skills/quality-playbook/`, `.github/skills/quality-playbook/`, or `.continue/skills/quality-playbook/`), and creates the marker directory if it doesn't exist. Mutually exclusive with `--target` — the two flags answer different questions (`--ai-tool` is "which tool's canonical layout, under cwd or `--into`"; `--target` is "this literal path"). Auto-detection (no flag) remains the default.

**Install explainer message at run start (added retroactively in v1.5.6).** Before any copy operations, the installer emits an `event=intro` line with a brief explanation: the skill files install into a tool-specific subdirectory (so Claude Code finds them at `.claude/skills/...`, Cursor at `.cursor/skills/...`, etc.), the installer detects which tool by looking for the marker directory, and `--ai-tool` overrides if detection fails. This gives operators (and AI agents reading the structured output) the context they need to understand why detection sometimes fails and what to do about it. The message is informational and does not interfere with the per-event lines (`event=copy`, `event=detected_env`, etc.) that calling agents parse.

**Detection-failure recovery messaging (added retroactively in v1.5.6).** When auto-detection fails AND no `--target` AND no `--ai-tool` are passed, the existing refusal-to-guess behavior is preserved (script exits non-zero), but the failure event now emits a three-option recovery block: (a) re-run with `--ai-tool <name>` to specify the tool explicitly, (b) re-run with `--target <absolute-path>` to install at a literal path, or (c) open the target in the AI tool first to create the marker directory and then re-run auto-detection. AI agents reading the output can pick option (a) directly when the operator already told them which tool they're using.

**Cross-platform: Windows, macOS, Linux.** The script uses `pathlib.Path` throughout (no manual `/` joins or shell-style path manipulation); reads and writes text files with explicit encoding (`utf-8`) and explicit newline handling so Windows CRLF doesn't corrupt diffs; runs on Python 3.9+, which is available on all three platforms. Windows behavior is smoke-tested in Phase 4 validation alongside macOS and Linux.

**Idempotency.** Re-running against an installed location updates files in place, preserving any operator-edited copies as `<file>.operator-backup-<UTC-timestamp>` so the operator's changes aren't silently overwritten. The script reports what it copied, what it preserved as a backup, and what it skipped (already up-to-date).

**Smoke check at install completion.** Three checks: `quality_gate.py` is parsed and compiled but not executed via compile-only AST validation (verifies syntactic correctness without running side effects); `SKILL.md` parses as valid markdown with the expected frontmatter fields; `references/exploration_patterns.md` loads and contains the expected pattern sections. Pass/fail reported per check. `AGENTS.md` tells the agent to surface any failure to the operator along with the diagnostic output.

**Output format aimed at AI consumption.** Default output is structured — one event per line, machine-readable key=value pairs where useful — so the calling agent can parse the result without natural-language interpretation. A `--verbose` flag adds human-friendly prose for direct human invocation.

**Out of scope for the install script.** No package management (no `pip install`), no virtual-environment setup, no IDE configuration, no agent-template generation. `AGENTS.md` may instruct the agent to handle those steps separately if the operator wants them, but they are not the install script's responsibility.

**Opinionated defaults: missing-documentation downgrade.**

Current behavior: when `reference_docs/` is empty in the target repo, Phase 1 still runs but produces a markedly lower-quality `EXPLORATION.md` because it has no informal-source signal to derive requirements from. The operator may not notice until Phase 6 reports few or no defects; tracing the cause back to "no reference docs" requires reading the EXPLORATION output carefully.

New behavior: at Phase 1 start, the playbook checks `reference_docs/` and `reference_docs/cite/`. If both are empty:
- The playbook proceeds (does not abort).
- `quality/EXPLORATION.md` opens with a section: "Documentation status: no reference docs found. This run is operating in code-only mode — see [doc] for the implications."
- A new short doc at `references/code-only-mode.md` explains: what to expect, why bug counts may be lower, where to put docs to improve the next run.
- `quality/PROGRESS.md` and the run-state log capture the downgrade as a `documentation_state` field so the audit trail is searchable.

This is opinionated in that it surfaces the gap explicitly and tells the operator how to close it, rather than silently producing a low-quality run.

**Revised README quickstart.**

Restructure "How to use the Quality Playbook to find bugs in your code" so Step 1 is the install path. Current order: Step 1 (provide documentation) → Step 2+ (run phases). New order: Step 1 (install: run `bin/install_skill.py`), Step 2 (provide documentation, optional but recommended), Step 3+ (run phases).

Step 1's prose makes clear: "If you've already manually copied SKILL.md and quality_gate.py to your skills directory, skip this step." So adopters who use the manual flow aren't told they did it wrong.

### `ai_context/AI_ORCHESTRATION_PATTERNS.md`

**Audience.** Two groups, in priority order:
1. **Adopters** — operators using QPB on their own projects who want to apply the same orchestrator/worker pattern to their own multi-session AI work. An adopter using QPB to review their codebase might want to run several long playbook executions in series, drive them from a chat session that doesn't itself have the patience for hours of subprocess waiting, and end up with a clean audit trail of what was instructed and what was produced. The pattern documented here is exactly that.
2. **AI sessions** invited into a QPB development session as orchestrator or worker — Claude, Cowork, Gemini, ChatGPT, etc. — reading the doc at session start to know what's expected of them.

**Adopter-grade scope.** The doc describes the pattern in terms general enough to lift into any adopter's workflow. Worked examples cite QPB-internal artifacts (the `v1.5.5_runner/` folder, the model-comparison runner) but the pattern itself is portable: an adopter can set up the same folder convention, the same instruction-file format, and the same lifecycle in their own project without reading QPB's source.

**Content outline:**

1. **The pattern, named.** "Orchestrator/worker via shared directory." A chat-driving AI session (the *orchestrator* — Cowork, ChatGPT, Claude.ai, etc.) controls a long-lived coding AI session (the *worker* — Claude Code, Cursor agent, etc.) by exchanging files in a directory both sessions can see. The worker polls the directory, executes instructions, and writes outputs back. Neither session retains in-memory state across crashes — the shared directory is the canonical record, and either session can resume by re-reading it.

2. **Folder convention.**
   ```
   <workspace>/<runner-name>/
     instructions/   # orchestrator writes here; worker reads + processes in order
     outputs/        # worker writes here; orchestrator reads + archives
     STATUS.md       # worker rewrites atomically with current state
     STOP            # orchestrator creates this file to halt the worker cleanly
   ```
   `<runner-name>` is freeform — `v1.5.5_runner`, `model-comparison_runner`, your own `<project>_runner`. Multiple runners coexist by having distinct folders. The workspace path is wherever the adopter wants — for QPB development it's under `~/Documents/AI-Driven Development/Quality Playbook/`, for an adopter's own project it might be under their project root or a separate orchestration directory.

3. **Instruction file format.** Markdown file at `instructions/NNN-<short-description>.md`. `NNN` is a zero-padded sequence number; the worker processes in numerical order. Each instruction file contains: a goal sentence, the work items, expected outputs (with paths relative to the runner folder), success criteria, and any context the worker needs to do the work without additional clarification.

4. **Output file format.** Worker writes to `outputs/NNN-<short-description>.md` matching the instruction's number. Contents: a status field (`completed` / `failed` / `partial`), what was actually done, any artifacts produced (with their paths), any errors encountered, follow-up suggestions for the orchestrator. The worker also rewrites `STATUS.md` to summarize the runner's current state — the most recent instruction, the most recent output, any pending issues.

5. **Lifecycle.** Orchestrator writes instruction → worker reads it → worker executes → worker writes output → orchestrator reads output → orchestrator decides on the next instruction. The loop continues until the orchestrator drops a `STOP` file in the runner folder; the worker sees it on its next poll and exits cleanly after writing a final `STATUS.md` summary.

6. **Why this pattern exists, in QPB's context.** The workspace `CLAUDE.md` establishes a "diagnosis-then-Claude-Code lane" rule: Cowork (chat surface, broad workspace access, NOT authorized to edit QPB source files except orientation docs) proposes diffs; Claude Code (running with QPB source edit authority) applies them. The orchestrator/worker pattern is the file-level realization of that rule — Cowork writes the brief, Claude Code reads it and edits, and the directory contents make the audit trail trivially inspectable. The same architectural reason — separating "decides what to do" from "does the file edits" — applies to many adopter scenarios.

7. **When to use this pattern vs. alternatives.**
   - **Use it when:** work spans more than one chat session; orchestrator and worker should run different LLMs (cost, capability, or trust reasons); the work is long-running (hours) and the chat session might be context-compacted before completion; you want a clean audit trail of what was instructed and what was actually done.
   - **Don't use it when:** the work fits in a single chat session with no compaction risk; orchestrator and worker can plausibly be the same session; you don't need the audit trail.
   - **Compare with `agents/calibration_orchestrator.md`:** that's single-session — one Claude Code session spawns playbook subprocesses and resumes itself across crashes via `run_state.jsonl`. This pattern is multi-session — two separate AI sessions, possibly different LLMs, communicating via files. Use the calibration-orchestrator pattern when the work is one tight coordinated cycle that one session can drive end-to-end; use this pattern when you want a chat-side planner and a coding-side executor working as a pair.

8. **Applying this pattern in your own project (adopter-grade).**
   - Create a runner folder anywhere you control.
   - Set up your orchestrator session (the chat AI you'll plan with).
   - Spin up your worker session (the coding AI that will do file-edit and command-execution work) and point it at the runner folder with a one-paragraph brief: "poll `instructions/`, execute the next file in numeric order, write outputs to `outputs/<same-number>.md`, update `STATUS.md`, halt on `STOP`."
   - Start writing instruction files. Keep each one self-contained.
   - When the work is done, drop a `STOP` file. Both sessions exit cleanly.
   - The runner folder is a complete record you can revisit, hand to a teammate, or use as an audit artifact.

9. **Worked example: the v1.5.5 ai_context-refresh runner.** Walks through the actual instruction file (`v1.5.5_runner/instructions/005-refresh-ai-context.md`), the output, and the `STATUS.md` evolution from the v1.5.5 ship sequence. Shows the resulting commit (`58da0cd`) on the `1.5.5` branch.

10. **Worked example: the model-comparison runner.** Shows how the same pattern handles benchmark sweeps across `gh copilot --model` IDs from a different runner folder (`model-comparison_runner/`), without conflicting with any other runner. Demonstrates the multi-runner case: an adopter (or QPB itself) can have several runners active simultaneously without cross-talk.

11. **Cross-references.**
    - `~/Documents/AI-Driven Development/CLAUDE.md` (workspace) — diagnosis-then-Claude-Code lane rule.
    - `agents/calibration_orchestrator.md` — related single-session orchestration pattern.
    - `ai_context/DEVELOPMENT_PROCESS.md` — broader QPB SDLC context.
    - `AGENTS.md` — install procedure that uses this pattern's premises (an AI agent driving the install).

**File length target:** ~300-450 lines. Long enough to be adopter-grade with the worked examples; short enough that AI sessions reading at start-of-conversation can absorb it.

---

## Validation

v1.5.6 validates by demonstrating each deliverable works against real conditions before tag:

1. **Pattern 7 cycle:** the cycle reaches a terminal state (any of `ship`/`revert`/`iterate<cap`/`halt-iterate-cap`). Audit at `Calibration Cycles/2026-05-02-pattern7-displacement-recovery/audit.md` is committed. `Lever_Calibration_Log.md` has a v1.5.6 entry. Visualizations render. `cell.json` per benchmark is written to `metrics/regression_replay/`. Whichever terminal state the cycle reaches, the verdict is honest about what was observed — not back-fitted to make v1.5.6 look successful.

2. **Adopter distribution:** `bin/install_skill.py` runs end-to-end against three target environments — a fresh repo with `.claude/`, a fresh repo with `.github/`, and a directory with neither (negative test). All three behave per spec. The smoke check at install completion passes for environments 1 and 2 and fails informatively for environment 3. The revised README's Step 1 prose is verified by reading it cold (Andrew or an AI proxy reading it as if seeing QPB for the first time).

3. **Orchestration patterns doc:** an AI session (different from the one that wrote the doc) reads `AI_ORCHESTRATION_PATTERNS.md` cold and can correctly answer: where do instruction files go, what does the worker do when it sees STOP, when should I use this pattern instead of the calibration orchestrator. If the doc is unclear, it's revised before tag.

4. **Test suite:** `python -m unittest discover bin/tests` passes (1017+ tests; no regression). Any new tests added for `bin/install_skill.py` pass.

5. **`setup_repos.sh` compatibility:** running `setup_repos.sh` against the v1.5.6-tagged QPB checkout produces benchmark workspaces equivalent to those produced from v1.5.5, modulo the budget-cap value in the Pattern 7 prose. This is an explicit check because the model-comparison benchmark sweep depends on it.

If any of these fail, fix or revise before tagging. If the Pattern 7 cycle reaches `revert`, that's a successful validation outcome — v1.5.6 still ships, with the lever reverted and the audit explaining the verdict.

---

## Out of Scope

- **Multi-cell calibration cycles** (factorial, Latin square, augmented designs) — v1.7.
- **SPC machinery** (control charts, run rules, X/MR, X-bar/R, p-chart, c-chart) — v1.7.
- **SDLC defect-rate dashboard** and prose-catalog migration — v1.7.
- **Cross-version trend tracking** — v1.7.
- **Cross-operator workflow** — v1.8.
- **Requirements Review UX** — v1.6.
- **Pattern 7 ordering experiment** (numeric vs. last position) — v1.7 multi-cell.
- **Skill-as-code adopter persona deep work** — possible v1.5.7.
- **New iteration strategies, new exploration patterns, new phase architectures** — none of those are in v1.5.6.
- **Modifications to `agents/calibration_orchestrator.md`** other than minor clarifications surfaced during cycle execution — protocol revisions are their own work item.

---

## Dependencies

- v1.5.5 shipped (tag `v1.5.5` on origin; main fast-forwarded; 1.5.6 branch already exists at `0b74054` per the v1.5.5 ship sequence).
- Working `setup_repos.sh` for the four benchmark repos (chi-1.3.45, chi-1.5.1, virtio-1.5.1, express-1.3.50). Confirm before Phase 2 starts.
- `bin/visualize_calibration.py` operational against cycle data (validated in v1.5.5).
- The `2026-05-02-pattern7-displacement-recovery/` cycle directory exists and has not been modified since scaffolding.
- `gh copilot` available if any phase invokes it (Council reviews; not the cycle itself).
- The model-comparison benchmark sweep (a separate Cowork task) and v1.5.6 development do not conflict — model-comparison operates on `repos/model-comparison/` subfolders and uses v1.5.5's tagged state for its initial sweep, while v1.5.6 work happens on the `1.5.6` branch and only touches `1.5.6` until tag.

---

## Resolved Questions

Questions raised during the design draft, resolved by operator review on 2026-05-03:

1. **Should the install script support more than a few target environments?**
   *Resolved: yes.* The script supports as many AI-tool environments as the project knows about (`.claude/`, `.github/`, `.cursor/`, `.continue/`, with new entries added as one-line config additions), plus an explicit `--target <path>` flag for arbitrary folders. The default invocation mode assumes an AI coding agent (Claude Code, Cursor, etc.) is running the script, with `AGENTS.md` carrying the canonical install procedure for the agent to follow. Direct human invocation works the same way; the agent-driven path is what's optimized for.

2. **Does the missing-documentation downgrade need a runtime flag to opt out?**
   *Resolved: no opt-out flag in v1.5.6.* The default behavior — proceed in code-only mode with explicit framing in `EXPLORATION.md` and a `documentation_state` field in the run-state log — is what ships. If operator confusion surfaces post-ship, a `--require-docs` flag is a v1.5.7 candidate.

3. **Should `AI_ORCHESTRATION_PATTERNS.md` be adopter-grade — usable by adopters in their own projects, not only as a QPB-development reference?**
   *Resolved: yes.* The doc is written for adopters first and AI sessions second. It includes a section on applying the pattern in an adopter's own project, with the pattern described in terms general enough to lift without reading QPB source. Worked examples cite QPB-internal artifacts as illustrations of a portable pattern, not as the entire scope.

4. **What if the Pattern 7 cycle's terminal state is `revert`?**
   *Resolved: revert is a valid outcome.* The lever change is reverted; v1.5.6 still ships with the audit and `Lever_Calibration_Log.md` entry. The cycle's purpose is to test the hypothesis, not to confirm it. A reverted cycle validates v1.5.5's orchestration infrastructure equally well.

5. **Does the install script need to handle Windows paths?**
   *Resolved: yes — Windows, macOS, and Linux all supported.* The script uses `pathlib.Path` throughout, explicit `utf-8` encoding with newline handling, and Python 3.9+ which is available on all three platforms. Phase 4 validation smoke-tests the install on Windows alongside macOS and Linux.

6. **Should the "What's new in v1.5.6" README section call out the Pattern 7 cycle outcome explicitly?**
   *Resolved: yes.* Operators reading the release notes see whether the lever shipped or reverted, with a link to the cycle audit. Phase 5 release-notes drafting is responsible for getting the wording right.

These resolutions are baked into the design above and the Implementation Plan that follows.
