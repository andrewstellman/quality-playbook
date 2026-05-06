# Calibration Protocol — How to drive a QPB calibration cycle

*Self-contained operational protocol. Designed to be paste-able to any AI agent (Cowork, Claude Code, codex, claude CLI, Cursor agent, etc.) that has read access to a QPB repository. The AI executes the steps below as the **executing AI**; the **operator** (Andrew) provides inputs, runs subprocesses the AI cannot run, and gates the STOP boundaries; a **Council of Three** review gates the final lever change.*

*Last updated: 2026-05-06 (v1.5.6 cluster G refresh — the v1.5.6 Pattern 7 displacement-recovery cycle exercised this protocol end-to-end and surfaced lessons about session-lifetime constraints, API budget as a binding constraint on express post-lever orchestration, and REQ-ID instability across runs. CALIBRATION_PROTOCOL.md remains the methodology doc; the cluster F.1 commit (`ba64584`) folded three concrete operational learnings into the executable orchestrator template (`agents/calibration_orchestrator.md`): API-budget-exhausted recovery path, reduced-scope option's three preconditions (named in audit, flagged for follow-up, NOT the benchmark most directly tied to the hypothesis), mid-benchmark post-lever interruption failure mode. Cross-reference there for the operational mechanics; this protocol stays focused on the methodology).*

*Methodology context (read first if unfamiliar): `~/Documents/QPB/ai_context/IMPROVEMENT_LOOP.md` describes WHY the lever inventory exists and WHAT each lever controls. This protocol describes HOW to actually run a calibration cycle.*

*Schema for the structured cell.json output: `~/Documents/QPB/metrics/regression_replay/SCHEMA.md`. NOTE: SCHEMA.md was authored before this protocol and has known discrepancies (it documents a `bin/regression_replay.py` apparatus that this protocol supersedes; it lists Lever 1-5 but `IMPROVEMENT_LOOP.md` carries Lever 1-6; it specifies a "mechanical matcher" by spec basis where this protocol uses AI-orchestrated semantic matching). The discrepancies are tracked for an additive SCHEMA update; until then, this protocol is the canonical operational guide.*

*v1.5.5 substrate (referenced from multiple steps below; collected here for orientation):*
- *`agents/calibration_orchestrator.md` — the spawn-and-resume orchestrator template that wraps Steps 1-12 in an autonomous-loop driver.*
- *`references/run_state_schema.md` — event taxonomy for the per-cycle `quality/run_state.jsonl` log, including phase boundaries, validation results, and format invariants.*
- *`bin/run_state_lib.py` — read/parse/validate helpers (`read_events`, `last_in_progress_phase`, `validate_run_state_file`, `validate_phase_artifacts`, `validate_no_source_edits`) plus writers (`append_event`, `write_progress_md`).*
- *`bin/visualize_calibration.py` — emits four cycle charts: per-bug × cycle heatmap, lever × benchmark heatmap, recall trajectory, and a Mermaid lever-interaction graph.*
- *`validate_no_source_edits` is wired into `bin/run_playbook.py:_finalize_iteration` as a mechanical Phase 5 source-edit guardrail — any file modification outside `<target>/quality/` during finalization is recorded as a `validation_result` event with `status="fail"` and tainted runs should be re-run from a clean checkout.*

*Discipline shared with the rest of QPB development: `~/Documents/QPB/ai_context/DEVELOPMENT_PROCESS.md` (Council protocol, mutation-test discipline, calibrated reporting, AI-identity discipline).*

*Edit lane: this is a QPB orientation doc per the workspace `~/Documents/AI-Driven Development/CLAUDE.md` orientation-doc carve-out. Direct edits by Cowork are permitted; release-gate review is the Toolkit Test Protocol, not Council-of-Three.*

---

## Lessons from v1.5.6 use

The v1.5.6 Pattern 7 displacement-recovery cycle was the first cycle to drive this protocol end-to-end through the v1.5.5 orchestration machinery. It produced a REVERT verdict (lever pull did not recover the targeted displacement bugs without losing others), but more importantly it surfaced operational lessons that don't change Mode 1 itself but do inform how future cycles should be scheduled and budgeted:

- **Session lifetime is a binding constraint on multi-day cycles.** The v1.5.6 cycle ran across 2026-05-02 through 2026-05-04 and could not be driven from a single continuous executing-AI session. Instead, the cycle was structured as per-benchmark instructions issued through a runner folder (`v1.5.6_runner/`) using the orchestrator/worker pattern documented in `ai_context/AI_ORCHESTRATION_PATTERNS.md`. Each instruction was self-contained enough that a fresh worker session could resume from the runner folder's state without losing cycle context. The protocol's Mode 1 description still applies — autonomous loop, no operator intervention between Steps 1-12 — but for a multi-day cycle in practice, "Mode 1" maps onto a sequence of worker sessions coordinated through a runner folder, not one continuous session.
- **API budget can become a binding constraint that interrupts cycle work.** The v1.5.6 cycle's express-1.3.50 post-lever orchestration was interrupted at the API budget limit before producing a replayable cell snapshot. Express therefore appeared in the audit only as pre-lever context, not as a completed before/after replay cell, and the cycle ran on a 2-of-3 reduced scope (chi-1.3.45 + virtio-1.5.1 post-lever). When budgeting future cycles, plan for the possibility that API budget may exhaust mid-cycle on a benchmark; the orchestrator/worker pattern lets a follow-up cycle pick up the interrupted benchmark cleanly without redoing the unaffected ones.
- **REQ-ID instability across runs requires substantive matching.** Recall measurement assumes a stable match key between historical and fresh BUGS.md. In the v1.5.6 cycle, REQ-IDs were renumbered per Phase 4 run, so the file-basename overlap between pre/post-lever runs was around 50% and the `(REQ_id, file)` mechanical replay key did not produce a clean comparison. The audit fell back to substantive file-path and description-content matching (per Step 3's "match identification is the executing AI's qualitative judgment" guidance). This worked, but it means the executing AI cannot rely on REQ-ID stability when computing recall — Step 3's instruction to use semantic equivalence is required, not optional.

These lessons live here for future cycle planners; the protocol's 12-step structure is unchanged.

---

## Roles

The protocol involves four distinct roles. Keeping them straight is critical for the STOP boundaries to make sense:

- **Executing AI** — the agent reading this protocol and executing it. Performs Steps 1-12 (or hands subprocess invocations to the operator). Could be Cowork, Claude Code, codex, claude CLI, Cursor agent, etc.
- **Operator** — Andrew Stellman. Provides inputs at the top, runs any subprocess the executing AI cannot run from its tool environment (e.g., long-running playbook invocations the AI's session cannot block on; Council `gh copilot` invocations across three terminals), and gates STOP boundaries.
- **Council of Three** — three-reviewer panel run via `gh copilot --prompt --model <X>` from three terminals on the operator's machine. The executing AI drafts the Council prompt; the operator runs the three CLI commands; the executing AI synthesizes the responses.
- **Committing agent** — a fresh Claude Code session (separate from the executing AI) that lands the canonical commit after Council Ship. Per `DEVELOPMENT_PROCESS.md`'s "fresh session for canonical commit" discipline.

---

## Execution modes

The protocol supports two modes, selected by whether `<runner>` is specified in Inputs:

- **Mode 1: Fully autonomous (default; no `<runner>` specified).** The executing AI runs the entire cycle without operator intervention between Steps 1-12. It walks Phases 1-3 of the playbook inline (reading canonical phase prompts from `~/Documents/QPB/phase_prompts/phase1.md`, `phase2.md`, `phase3.md`), spawns sub-agents for the Council review (Step 7), runs validation and cross-benchmark checks via inline phase execution or sub-agent fan-out, and reports a terminal-state outcome to the operator. Sub-agents are the executing AI's environment-specific mechanism for parallel independent work (Cowork's Agent tool; claude CLI invocations spawned from bash; the equivalent in any AI tool). Operator's role: provide initial inputs, review the terminal-state report, approve the ship (or direct dead-end remediation). Cost lives in the executing AI's session token budget.
- **Mode 2: Runner-driven, operator-in-the-loop (`<runner>` specified).** The executing AI surfaces commands for the operator to run, including `python3 -m bin.run_playbook --<runner> ...` for playbook runs and `gh copilot --prompt ...` for Council. Operator runs subprocess commands, pastes back results. Right mode when the executing AI's environment can't drive Phases 1-3 inline (e.g., a UI tool with no bash access) or when the operator wants the orchestrator off the critical path (debugging; cost containment in their separate billing account).

**Default to Mode 1.** Mode 1 is the v1.5.5 activation criterion (now satisfied): an AI tool given just the protocol + target + expected-bug list can autonomously run the full improvement loop and converge on a ship-or-dead-end verdict, using `agents/calibration_orchestrator.md` as the spawn-and-resume template. Mode 2 is documented as an alternative for environments that can't support Mode 1 fully.

The steps below describe Mode 1 as canonical with Mode 2 noted at each step where the mechanics differ.

## Autonomous-loop convergence and circuit-breakers

Mode 1 runs to terminal state without operator intervention. Terminal states:

**Success:**
- Council Ship verdict (Step 7) → validation passes (Step 8) → cross-benchmark check clean (Step 9) → calibration log + cell.json written (Steps 10-11) → reported to operator (Step 12). Operator approves ship.

**Dead end (lever pull doesn't work):**
- Council Block verdict (Step 7), or
- Validation `recall_after - recall_before <= noise_floor_threshold` (Step 8), or
- Cross-benchmark regression beyond noise_floor_threshold (Step 9).

In any dead-end case, the executing AI auto-reverts the lever change (working-tree edits discarded), writes the dead end to the calibration log + cell.json with the disposition recorded, and reports to the operator.

**Iteration limit reached:**
- Step 6 revision count hits 5 (default; configurable) → executing AI halts, surfaces all iterations to operator, reports the loop didn't converge.

**Operator interrupt:**
- The executing AI's environment is interruptible at every turn-boundary; the operator can stop the loop at any time and direct.

The autonomous loop runs until one terminal state is reached. The executing AI does NOT poll for operator input mid-loop; the only operator interactions are (a) initial inputs, (b) terminal-state report, (c) any operator-initiated interrupt.

## When to use this protocol

A calibration cycle is triggered when one of the following observations is in hand:

- A regression-replay run against a historical benchmark target identifies bugs current QPB misses that the historical version found
- A Council review of a recent benchmark output flags a quality issue
- An adopter reports a category of bug QPB systematically misses on their codebase
- Routine periodic regression-replay run identifies a measurable recall drop

Each observation is a candidate for one cycle, which produces (at most) one lever-change release. Multi-lever releases are out of scope; if a cycle motivates more than one lever pull, run them as separate cycles.

---

## Required capabilities

**Both modes need:**

- Read access to the QPB repository (`~/Documents/QPB/`)
- Read access to the workspace orientation doc (`~/Documents/AI-Driven Development/CLAUDE.md`)
- File-system write access to the QPB working tree (for Step 6 lever-change drafts)
- File-system write access to the workspace `Quality Playbook/` (for audit-trail and Council prompt files)
- Bash shell with `git`, `python3`, `which`

**Mode 1 (AI-orchestrated) additionally needs:**

- Ability to read large files (Phase prompts + target source — total ~1-3 MB depending on target size)
- Ability to write target artifacts (`<target>/quality/EXPLORATION.md`, `BUGS.md`, `REQUIREMENTS.md`, etc.)
- Optional: ability to spawn sub-agents for parallel work (e.g., concurrent Step 9 pinned-benchmark validation). Without sub-agent capability, Mode 1 still works; it just runs serially.

**Mode 2 (runner-driven) additionally needs:**

- Runner CLI installed and on PATH (`<runner>` from Inputs)
- Operator availability to run subprocess commands and paste back results

**Neither mode needs:** ability to spawn long-running background processes, ability to run `gh copilot` against three concurrent terminals (the operator does this for Council), ability to commit (commits are delegated to the committing agent).

---

## Inputs

The operator provides:

- **`<target>`** — Path to the benchmark target repo. Must be a directory inside `repos/archive/<benchmark>-<version>/` (or equivalent structure). Example: `repos/archive/chi-1.3.45/`.
- **`<historical_bugs>`** — Path to the historical ground-truth `BUGS.md`. Default convention: `<target>/quality/BUGS.md` as committed in QPB's git tree.
- **`<focus_bugs>`** *(optional)* — A list of specific historical `BUG-NNN` IDs to focus the cycle on. If omitted, all historical bugs are in scope.
- **`<pinned_benchmarks>`** *(optional)* — Pinned benchmarks for the cross-regression check. Defaults: `chi-1.5.1`, `virtio-1.5.1`, `express-1.5.1`.
- **`<runner>`** *(optional)* — Selects execution mode. **If unspecified: Mode 1 (AI-orchestrated)** — the executing AI does everything itself, optionally spawning sub-agents for parallelism. **If specified: Mode 2 (runner-driven)** — the executing AI shells out to `python3 -m bin.run_playbook --<runner> ...` via the operator. Mode 2 valid values: `claude`, `copilot`, `codex`, `cursor`. **In Mode 2, use the same runner across all steps of one cycle** — runner choice affects both bug discovery and recall comparison; mixing runners conflates lever effect with runner variance.

---

## Pre-flight

Before launching the cycle, verify all of the following. STOP and surface to the operator if any check fails. Record each check's result in the audit trail (see Step 7's audit-trail-location guidance).

1. **QPB working tree is clean.** Run `git status -s` in the QPB repo. List any non-empty output to the operator before declaring clean. Acceptable: empty output, OR only `??` entries that are gitignored (e.g., `quality/previous_runs/<TS>/` from prior cycles). If anything else is dirty, ask the operator whether to commit, stash, or restore before proceeding.
2. **`<target>` is accessible.** Directory exists; contains source code to run the playbook against.
3. **`<historical_bugs>` is tracked at HEAD.** Run `git ls-files --error-unmatch <historical_bugs>`. If this errors, the historical baseline is untracked — STOP and ask the operator whether to commit it first or pick a different target.
4. **`<historical_bugs>` is the historical baseline, not a fresh-run output.** If `git diff --name-only HEAD <historical_bugs>` shows a difference, the file has been mutated by a prior run; restore via `git restore <historical_bugs>` before starting.
5. **`<historical_bugs>` contains at least one bug.** Grep for `^### BUG-` and `^## BUG-` (the protocol must handle both heading depths). If `historical_bug_count == 0`, recall is undefined; STOP.
6. **Runner CLI is available.** `which <runner>` returns a valid path.
7. **QPB tests pass.** Run `python -m unittest discover -s bin/tests -p "test_*.py"`. All tests must pass. A failing test suite means the apparatus or supporting code has a regression that needs fixing first.
8. **No concurrent cycle is in flight.** Check `Quality Playbook/Reviews/Calibration Cycles/` for any in-flight audit trail (a directory whose `audit.md` has no "Cycle complete" or "Cycle aborted" closing entry). If yes, STOP — concurrent cycles in the same QPB checkout will collide on `references/` edits and `<target>/quality/` state. If you need to run cycles in parallel, use `git worktree add` to give each cycle its own checkout.
9. **`IMPROVEMENT_LOOP.md` is readable.** The orchestrator must be able to read it to identify levers in Step 5.

If all nine checks pass: proceed to Step 1. If any fails: STOP, surface the failure clearly with the specific check number and observed output, ask the operator how to proceed.

---

## Cost notice

A single cycle costs approximately **5 full playbook runs** in the success path:

- Step 1: 1 run (target, current methodology)
- Step 8: 1 run (target, post-lever-pull)
- Step 9: 3 runs (default 3 pinned benchmarks)

Each playbook run is a multi-phase LLM-driven exploration that consumes substantial tokens (Phases 1-3 against a non-trivial target produce ~10-30 KB of artifacts and consume substantially more tokens than that on the LLM side).

**Cost lives differently in each mode:**

- **Mode 1:** the executing AI's session token budget. The cycle's full LLM cost charges to whatever account hosts the executing AI session. Sub-agent fan-out can run benchmarks in parallel without extra cost (one parent budget, distributed work).
- **Mode 2:** the runner's subprocess token budget (typically the operator's separate billing account for the chosen CLI). The executing AI session burns minimal tokens — mostly the orchestration prose surfaced back and forth.

**Fail-fast in Step 9** to limit cost on dead ends: stop after the first regressing pinned benchmark; don't run remaining ones.

**Fail-fast in Step 4**: if the missed-bug class is obviously a runner failure (CLI crash, output truncation, source-unchanged abort) rather than a methodology gap, STOP before Step 5 — don't burn a lever pull on apparatus / runner debt.

---

## Steps

### Step 1 — Run the playbook against the target

The playbook's Phase 1-3 work needs to happen against `<target>`. Phases 1-3 (Explore, Generate, Code Review) are sufficient for bug discovery; Phase 4-6 (Spec Audit, Reconciliation, Verify) produce skill-derivation artifacts irrelevant to bug-recall measurement and would burn tokens unnecessarily.

**Mode 1 (AI-orchestrated):**

1. Archive the target's existing `quality/` tree before starting: `mv <target>/quality <target>/quality.<TIMESTAMP>.bak`, then `mkdir <target>/quality`. (This mirrors the runner's archive-on-startup behavior; the historical baseline is preserved at the `.bak` path. Alternatively: `git restore <target>/quality/` before starting and let the historical live at HEAD; capture it in memory before any writes.)
2. Read `~/Documents/QPB/phase_prompts/phase1.md`, substitute any `{...}` placeholders with their canonical values (e.g., `{seed_instruction}` is the no-seeds-mode seed instruction for a calibration cycle), execute the phase against `<target>`'s source. Write `EXPLORATION.md`, `exploration_role_map.json` to `<target>/quality/`.
3. Read `phase_prompts/phase2.md`, execute against the Phase 1 outputs. Write `REQUIREMENTS.md`, `QUALITY.md`, `CONTRACTS.md`, `COVERAGE_MATRIX.md`, `test_functional.py`, `RUN_*.md`, the manifests to `<target>/quality/`.
4. Read `phase_prompts/phase3.md`, execute against Phase 1+2 outputs. Write `BUGS.md` to `<target>/quality/`.

The executing AI may spawn sub-agents for any phase if useful (e.g., a Phase 3 sub-agent that does deep code review while the parent continues to monitor); each sub-agent inherits the canonical phase prompt.

**Mode 2 (runner-driven):**

The executing AI surfaces this command for the operator to run in their terminal:

```bash
python3 -m bin.run_playbook --<runner> --phase 1,2,3 <target>
```

The runner archives the target's existing `quality/` tree to `<target>/quality/previous_runs/<TIMESTAMP>/` and writes a fresh artifact set under `<target>/quality/`. The operator pastes back the exit code and the path to the run log (`<target>/QPB-playbook-*.log`) when the run completes.

**Common to both modes:**

On completion: confirm that `<target>/quality/BUGS.md` exists and contains at least one `### BUG-` (or `## BUG-`) heading. If not, the run failed; STOP and surface the failure (likely cause: phase prompt produced no bug findings, source-unchanged invariant aborted, etc.).

Record in the audit trail: the mode used (Mode 1 / Mode 2), the runner used (Mode 2 only), the run start/end timestamps (for cell.json's `wall_clock_seconds`), the QPB commit SHA at run start (`git rev-parse HEAD` in QPB), the target's commit SHA at run start (`git rev-parse HEAD` in `<target>` if it's tracked).

### Step 2 — Locate both BUGS.md files

- **Fresh:** `<target>/quality/BUGS.md` — current QPB output
- **Historical:** the path the operator provided in `<historical_bugs>`. If the runner archived it, the archived copy lives at `<target>/quality/previous_runs/<TIMESTAMP>/quality/BUGS.md` (the most recent timestamp directory).

Read both files in full. They are markdown documents with structured per-bug sections; the executing AI reads the content semantically, not via regex pattern-matching.

### Step 3 — Compute recall semantically

For each bug in the historical baseline, determine whether the same bug — or substantively the same defect — appears in the fresh output. The match criterion is **semantic equivalence**, not field-equality. Two bugs match if:

- They cite the same file (file basename match), AND
- They describe the same underlying defect (same function or feature, same defect class)

Match identification is the executing AI's qualitative judgment. REQ-IDs are NOT a reliable match key — each run produces its own REQUIREMENTS.md numbering. Bug-IDs are similarly unreliable. The right signal is the bug's *content*: what file, what function, what defect.

**Output of this step (markdown table format, written to the audit trail):**

```markdown
## Step 3 — Recall measurement

| Historical | Fresh (matched) | Match basis |
|---|---|---|
| BUG-001 (matchAcceptEncoding q-values) | BUG-001 (matchAcceptEncoding) | file=compress.go + function match |
| BUG-002 (RouteHeaders Host) | BUG-002 + BUG-003 | both cite RouteHeaders dispatch |
| BUG-003 (ReadFrom byte-doubling) | (missed) | no fresh bug cites wrap_writer.go ReadFrom |
| ... | ... | ... |

- **Recovered:** [BUG-001, BUG-002, BUG-004, BUG-005, BUG-006, BUG-007, BUG-010] (7 / 10)
- **Missed:** [BUG-003, BUG-008, BUG-009] (3 / 10)
- **Spurious:** [BUG-005, BUG-006, BUG-013, ...] (fresh bugs not in historical — bonus findings, not counted toward recall)
- **Recall:** 7/10 = 0.70
- **Runner:** copilot
- **Notes:** runner produced 17 fresh bugs vs 10 historical; current methodology found 7 of the 10 historical bugs in similar form, missed 3 (one byte-counting, two mounted-middleware match logic).
```

**On non-determinism:** if a re-measurement of recall against the same fresh BUGS.md produces a different recovered/missed split, document both measurements in the audit trail and use the more conservative (lower) recall as `recall_before`.

### Step 4 — Diagnose the missed-bug class

If `recall == 1.0` (or `recall == 1.0` over `<focus_bugs>` if specified): no calibration needed. The current methodology already addresses everything in the historical baseline. STOP and report to the operator. Do not proceed.

If `recall < 1.0`:

- Examine the `missed` set. Read each missed bug's full description in the historical BUGS.md.
- Identify the common pattern, if any. Examples of patterns:
  - All missed bugs are in mounted/composed middleware (Phase 1 enumeration didn't enumerate composition contexts)
  - All missed bugs involve numeric accounting (Phase 1 didn't audit accumulator state)
  - All missed bugs are in a specific subsystem the exploration prompt didn't direct attention to
  - All missed bugs involve a specific failure mode (e.g., off-by-one, error-path neglect)

If the missed bugs have no common pattern — they're heterogeneous and individually distinct — the cycle has no clean lever-pull diagnosis. STOP, **but still write a Step 4 audit-trail entry capturing the heterogeneous-bugs analysis** (the analysis is reusable in future cycles or when the cycle is split). Surface to the operator that the cycle should be split into multiple cycles, one per missed bug class.

The diagnosis output is a short paragraph characterizing the missed-bug class and citing 2-3 representative `BUG-NNN` IDs from `missed_ids` that exemplify the class. Write to the audit trail.

### Step 5 — Hypothesize the lever

Read `~/Documents/QPB/ai_context/IMPROVEMENT_LOOP.md` end-to-end (re-read each cycle; the lever inventory may have changed since the last cycle).

**Lever home file:** each lever has a "home file" — the canonical reference doc whose prose, when extended, executes the lever pull. The home-file mapping is in `IMPROVEMENT_LOOP.md`'s lever inventory section.

For each lever (1-6), assess: *if this lever were pulled (in the appropriate direction), would the missed-bug class be addressed?* The criterion is the lever's **scope of effect**: does the lever's home file (e.g., `references/exploration_patterns.md` for Lever 1) contain prose that, if extended or refined, would direct the methodology to find this class of bugs?

Pick one lever. If multiple plausibly fit, prefer the one with the cleanest scope match — the lever whose home file's *primary purpose* aligns with the missed-bug class. Multi-lever pulls are out of scope; if no single lever fits, surface the question to the operator before proceeding.

The hypothesis output cites:

- The lever number and name (e.g., "Lever 1 — Exploration breadth/depth")
- The lever's home file (e.g., `references/exploration_patterns.md`)
- The specific section/subsection of the home file that would change
- A one-paragraph rationale: why this lever, in this direction, would catch the missed-bug class

Write to the audit trail.

### Step 6 — Draft the lever change

Edit the lever's home file directly in the QPB working tree. The change should be:

- **Minimal and focused.** Add/extend ONE section or pattern. Do not rewrite the whole file.
- **Targeted at the missed-bug class.** The new prose should give the methodology specific instructions or examples that would catch the class.
- **Consistent in style with the existing file.** Match section structure, voice, and example density.
- **Reference-able.** Future cycles should be able to point at this section and say "Lever N was pulled in cycle X by adding section Y."

Do NOT commit. Do NOT run the playbook again yet. The change exists only in the working tree.

**Iteration limit:** if the executing AI revises the draft more than 5 times in response to operator or Council feedback within a single cycle, STOP and escalate to the operator — repeated revisions suggest the diagnosis or lever choice is wrong, not just the prose.

### Step 7 — Council review of the lever-change draft

This step is **continuous work for the executing AI**, not a halt. The AI drafts the Council prompt, synthesizes the responses, and produces a verdict. The only operator-blocking sub-step is the `gh copilot` invocation in 7.3 (which requires three terminals on the operator's machine). The actual halt points are the failure modes (Council Block verdict; iteration-limit reached) — those are tracked in the failure-modes table at the bottom.

**Iteration policy:** by default, keep working-tree edits and refine on top across iterations. Reset (`git restore <home_file>`) only when the orchestrator or Council requests a fresh attempt. Capture each iteration's diff + feedback in the audit trail.

**Audit trail location and format.** During the cycle, the audit trail lives at:

```
~/Documents/AI-Driven Development/Quality Playbook/Calibration Cycles/<YYYY-MM-DD>-<benchmark>-<version>/
  audit.md                — running log
  council_prompt.md       — drafted by executing AI for operator to run
  council_response_<model>.md  — pasted back by operator (3 files)
  council_synthesis.md    — written by executing AI from the responses
```

The `audit.md` running log has sections: Inputs, Pre-flight results, Step 1-12 results (filled as we go), Iteration history, Council outcome, Cycle verdict.

In addition to the human-readable `audit.md`, the v1.5.5 substrate emits a structured per-cycle `<target>/quality/run_state.jsonl` event log (event taxonomy in `references/run_state_schema.md`). The orchestrator (`agents/calibration_orchestrator.md`) appends one event per phase boundary plus one `validation_result` event per post-condition check (`validate_phase_artifacts` at each phase boundary; `validate_no_source_edits` at Phase 5 finalization). Use the helpers in `bin/run_state_lib.py` to read/append events rather than parsing the JSONL by hand.

At a release boundary (v1.5.6 or later), the cycle directory migrates to `~/Documents/QPB/docs/process/QPB_v<X.Y.Z>_Calibration_Cycle_<benchmark>-<version>/` per the versioned-historical-artifact pattern in `DEVELOPMENT_PROCESS.md`. The first cycle directory under this convention — `~/Documents/AI-Driven Development/Quality Playbook/Calibration Cycles/2026-05-02-pattern7-displacement-recovery/` (Pattern 7 displacement-recovery, deferred to v1.5.6 per the published Roadmap) — exists with the lever description and audit-trail scaffolding in place; the lever-pull execution lands in v1.5.6.

**7.1 — Final draft check (self-review).** Before launching the Council, the executing AI does a quick self-review:

- `git diff` — the exact change as a unified diff
- The diagnosis from Step 4 + lever hypothesis from Step 5 + recall measurement from Step 3
- The audit trail of any iterations that produced this final draft

If the executing AI's own pass surfaces issues, return to Step 6 with feedback (counts toward iteration limit). Otherwise proceed to 7.2.

**7.2 — Draft the Council prompt.** Write the prompt file at `~/Documents/AI-Driven Development/Quality Playbook/Calibration Cycles/<...>/council_prompt.md`. The prompt body covers: the diagnosis, the lever hypothesis, the recall measurement, the diff, and explicit review questions:

- Is the diagnosis sound (does the missed-bug class characterization match the missed bugs)?
- Does the lever change actually address the missed-bug class (would Phase 1, applied with this updated reference, find the missed bugs)?
- Is the prose consistent with the home file's existing style and structure?
- Does the change risk regression elsewhere (does it shift Phase 1's attention away from things it currently catches)?

**7.3 — Run the Council.** The executing AI conducts the Council itself. Mechanics depend on the mode:

**Mode 1 (autonomous):** the executing AI spawns three parallel sub-agents with orthogonal review lenses. The sub-agent mechanism is environment-specific:

- In Cowork: use the Agent tool (`general-purpose` subagent_type, three parallel calls in one message) with prompts directing each agent to review the draft from a specific lens (correctness/diagnosis-soundness; scope/style/regression-risk; integration/cross-pattern-consistency).
- In claude CLI from bash: spawn three `claude --print` subprocess invocations in parallel, each with a different lens prompt.
- In any environment with sub-agent capability: equivalent parallel fan-out with three independent perspectives.

The three lenses by default (the executing AI may adapt per cycle):
1. **Diagnosis correctness** — does the lever change actually address the missed-bug class? Is the missed-bug class characterization right?
2. **Scope and style** — is the change minimal and focused? Is the prose consistent with the home file's existing patterns? Does it stay within the home file?
3. **Regression risk** — would this change harm Phase 1's coverage of bugs it currently catches? Does it overspecify and crowd out other patterns?

Each sub-agent reads the canonical docs (CALIBRATION_PROTOCOL.md, IMPROVEMENT_LOOP.md, the home file at HEAD, the draft diff, the chi-1.3.45 / target's BUGS.md history) and produces an independent verdict and finding list. Sub-agents do NOT see each other's output — independence is the point.

**Mode 2 (operator-in-the-loop):** the executing AI surfaces three `gh copilot --prompt --model <X>` commands for the operator to run from three terminals (per workspace CLAUDE.md's nested-panel Council protocol). The operator pastes back the response file paths.

In either mode, three independent perspectives are produced. Cowork's parallel-Agent fan-out is NOT a fully nested 9-perspective Council (each Agent is a single perspective, not an Agent that itself spawns three reviewers). For most calibration cycles three independent perspectives are sufficient; if a cycle is high-stakes (e.g., a foundational architectural change, not a typical lever pull), the executing AI may choose to fan out further or escalate to Mode 2 for the full nested 9-perspective gh-copilot Council.

**7.4 — Synthesize.** The executing AI reads all three sub-agent responses (or operator-pasted Council outputs in Mode 2), produces a `council_synthesis.md` with:

- Per-finding analysis (which findings appear across multiple perspectives — high-confidence; which appear in only one — possible bias or per-lens artifact)
- Composite verdict: **Ship**, **Hold-with-fixes**, or **Block**

**7.5 — Apply the verdict.**

- **Ship** — proceed to Step 8 (autonomous in Mode 1; operator-approval-blocking in Mode 2 if you set that gate)
- **Hold-with-fixes** — return to Step 6 with Council findings; revise; re-review (counts toward iteration limit)
- **Block** — fundamental issue with the diagnosis or lever choice; halt and report to operator (this is a real terminal state per the convergence section above)

In Mode 1, Ship → Step 8 happens autonomously without operator confirmation. Mode 1's gate IS the Council; once the executing AI's own multi-perspective review ships, the cycle proceeds to validation. Operator visibility into the Ship verdict happens at Step 12's terminal-state report.

Do NOT proceed past this step without an explicit Council Ship verdict.

### Step 8 — Validation run (post-Council)

After Council ships, the lever change moves from working tree to a committed state. **Source-unchanged invariant requires this be committed before re-running the playbook.** Sub-steps:

**8.0 — Commit delegation.** The executing AI does NOT commit. Compose a Claude Code launch prompt containing:
- The approved diff (from `git diff`)
- The diagnosis + lever hypothesis + Council Ship verdict
- Instruction to commit on the QPB feature branch with subject `v<release>: lever pull — <one-line description>`
- Instruction to return the new commit SHA when done

The operator runs the Claude Code prompt; the executing AI captures the returned commit SHA into the audit trail (`apparatus.qpb_commit_sha` in the cell.json).

**8.1 — Pre-validation cleanup.** Before re-running the playbook against the target:

- `git status -s` in QPB — confirm clean working tree (the lever change is now in HEAD; nothing else dirty)
- Reset the target's `quality/` tree to its pre-cycle state: `git restore <target>/quality/`
- Remove the cycle's `quality/previous_runs/` archives ONLY:
  ```bash
  git clean -fd <target>/quality/previous_runs/
  ```
  Do NOT run bare `git clean -fd` from the QPB repo root — that would wipe other untracked files including audit-trail scratch.

**8.2 — Validation run.** Re-run Phase 1-3 against `<target>` with the new lever in place.

- **Mode 1:** the executing AI re-walks Phases 1-3 inline against `<target>` (same procedure as Step 1's Mode 1 sub-steps).
- **Mode 2:** surface the command for the operator: `python3 -m bin.run_playbook --<runner> --phase 1,2,3 <target>`. Use the SAME runner as Step 1. Operator pastes back exit code and log path on completion.

**8.3 — Compute recall_after.** Read the new `<target>/quality/BUGS.md`. Apply the same Step 3 procedure to compute `recall_after`. **Lock `recall_before` to the Step 3 measurement** — do not re-measure against a re-run of Step 1; the comparison is Step 3's recall vs Step 8.3's recall, not a fresh re-measurement.

**8.4 — Success criterion.** `recall_after - recall_before > noise_floor_threshold` (default 0.05 = 5 percentage points). The lever pull recovered enough missed bugs to be statistically meaningful.

If `recall_after - recall_before <= noise_floor_threshold`: the lever pull is inside the noise floor or worse. Document the dead end (Step 10), revert via Step 8.5, surface to the operator. Do not proceed to Step 9.

**8.5 — Revert (if dead end).** Compose a Claude Code launch prompt for the committing agent: revert the lever-change commit via `git revert <commit-SHA>` (a new commit; do NOT branch-reset). Capture the revert SHA in the audit trail.

### Step 9 — Cross-benchmark regression check

**Fail-fast.** Run pinned benchmarks and stop after the first regression. Do not finish all three if any regresses.

**Parallelism in Mode 1:** the executing AI may spawn one sub-agent per pinned benchmark to run them concurrently. Sub-agents share the parent's lever-pull state (it's at HEAD post-Step 8). Each sub-agent reports its `recall_after_pinned` measurement. Parent stops the cohort and triggers revert if any sub-agent reports regression.

**Mode 2:** run pinned benchmarks one at a time (serial, since the operator runs each subprocess and pastes back).

For each `<pinned_benchmark>` in `<pinned_benchmarks>`:

1. Run Phase 1-3 against the pinned benchmark with the new lever in place:
   - **Mode 1:** executing AI (or sub-agent) walks Phases 1-3 inline against `<pinned_benchmark>`.
   - **Mode 2:** surface for operator: `python3 -m bin.run_playbook --<runner> --phase 1,2,3 <pinned_benchmark>` (using the same runner as Steps 1 and 8).
2. Compute `recall_after_pinned` against the pinned benchmark's historical baseline (use `<pinned_benchmark>/quality/BUGS.md` as the historical, restored to HEAD if it's been mutated).
3. Verify: `recall_after_pinned >= recall_before_pinned - noise_floor_threshold`. The pinned benchmark's recall is allowed to drop by less than the noise floor; any larger drop is a regression.
4. If regression: STOP. REVERT the lever change (Step 8.5). Document the dead end (Step 10).

If all pinned benchmarks hold: proceed.

### Step 10 — Document in calibration log

Append a new entry to `~/Documents/QPB/docs/process/Lever_Calibration_Log.md` (create the file if not present). The replicated workspace copy lives at `~/Documents/AI-Driven Development/Quality Playbook/Reviews/Lever_Calibration_Log.md` per `DEVELOPMENT_PROCESS.md`'s replicate-not-source-of-truth pattern; canonical is in QPB.

NOTE: SCHEMA.md as of this writing names a different path; SCHEMA.md is being updated to match. Use the QPB path `docs/process/Lever_Calibration_Log.md`.

The entry follows the calibration-log entry template in SCHEMA.md (with QPB-path reconciliation noted above):

```markdown
## Cycle: <YYYY-MM-DD> — <benchmark>-<version>

**Symptom:** <one-paragraph description of the observation that triggered the cycle>

**Diagnosis:** <the missed-bug class identified in Step 4, with citation to 2-3 representative BUG-NNN IDs>

**Lever pulled:** Lever <N> (<name>). <One-paragraph description of the change in the home file. Cite the home file path and section.>

**Runner:** <runner>. (Cycle runner-pinned; cross-cycle comparison requires same runner.)

**Before:** recall = <X>/<Y> = <Z>%. Recovered: [<list of historical IDs>]. Missed: [<list>].

**After:** recall = <X'>/<Y> = <Z'>%. Recovered: [<list>]. Missed: [<list>].

**Cross-benchmark:** <pass/regress per pinned benchmark, with deltas>

**Verdict:** <Ship / Dead end (with rationale) / Reverted (with rationale)>

**Cell:** [path to cell.json]
**Commit:** [<commit-SHA>] (or [<revert-SHA>] for dead ends)
```

Even on a dead end, write the entry — dead-end cycles are first-class data for understanding which lever-pull hypotheses don't work.

### Step 11 — Emit cell.json

Hand-write a schema-conforming cell.json to `~/Documents/QPB/metrics/regression_replay/<TIMESTAMP>/<benchmark>-<version>-all.json` (create directory tree as needed). Use the timestamp of the cycle's completion (UTC, ISO-8601 compact format: `20260501T231500Z`).

Required top-level fields per SCHEMA.md (read SCHEMA.md before this step for the canonical reference; some fields documented as "mechanical matcher output" are populated by the executing AI's semantic match instead — note this in `notes`):

**Top-level identity:**
- `schema_version`, `benchmark`, `historical_version`, `historical_qpb_version`, `qpb_version_under_test`, `run_timestamp`, `historical_bug_id` (or `"all"` for full-set cells)

**Bug measurement:**
- `historical_bug_count`, `recovered_bug_ids`, `missed_bug_ids`, `recall_against_historical` (the float, e.g., `0.70`)

**Lever attribution:**
- `lever_under_test` — string: `lever-1-exploration-breadth-depth`, `lever-2-...`, `lever-3-...`, `lever-4-...`, `lever-5-...`, OR `null` for baseline cells. NOTE: SCHEMA.md as of this writing only documents Lever 1-5; Lever 6 (skill-derivation pipeline, added in v1.5.3) requires an additive SCHEMA.md update before it can appear here. Use `null` if the cycle pulls Lever 6 and the SCHEMA hasn't been updated yet — record the discrepancy in `notes`.
- `lever_change_summary` — one-paragraph description
- `lever_home_file` — path

**Cross-benchmark regression check:**
- `regression_check.status` — `"clean"`, `"regressed"`, or `"skipped"`
- `regression_check.checked_cells` — array of paths to the pinned-benchmark cell.json files (this cycle creates them too)
- `regression_check.regressed_cells` — subset that fell beyond noise_floor_threshold (empty when status==`clean`)
- `regression_check.noise_floor_threshold` — the float (default 0.05)

**Apparatus reproducibility:**
- `apparatus.qpb_commit_sha` — `git rev-parse HEAD` in QPB at cycle start
- `apparatus.target_commit_sha` — analog for `<target>` if tracked
- `apparatus.runner` — string (`copilot`/`claude`/`codex`/`cursor`)
- `apparatus.runner_model` — model identifier if specified
- `apparatus.wall_clock_seconds` — for the cycle's primary playbook run (Step 1)

**Free-form:**
- `noise_floor_source` — describes how this cell's recall measurement should be interpreted in noise terms (e.g., `"single-run point estimate; matched semantically by executing AI"`)
- `notes` — any relevant caveats, including the "Lever 6 / SCHEMA additive update needed" note if applicable, and any drift between Step 3 and Step 8.3 measurements

**Validation:** there is no JSON Schema validator CLI as of v1.5.5. The executing AI does a manual field-by-field check against SCHEMA.md before declaring the cell written. (The v1.5.5 substrate validates the *event log* shape via `bin/run_state_lib.py:validate_run_state_file`, but the cell.json schema validator is separate work and not yet shipped.)

If the cycle was a dead end (Step 8 failure or Step 9 regression), still emit the cell with the dead-end disposition recorded — set `recall_against_historical` to `recall_after`, set `regression_check.status` to `regressed` (with the regressing pinned cell paths), and put the verdict explanation in `notes`.

### Step 12 — Final reporting and operator handoff

The executing AI surfaces the full cycle artifacts. This is reporting work, not a halt — the AI keeps working through it. The actual halt is at the tag-push (operator-only action).

Artifacts to surface:

- The committed lever change (commit SHA, files modified) — or revert SHA for dead ends
- The calibration log entry (path)
- The cell.json path
- The audit trail directory (workspace path; will migrate to `docs/process/` at version-ship)
- The recall delta and cross-benchmark verdict

**Operator handoff (only operator-blocking sub-step):** the operator is the final gate. If this cycle is the basis of a v<X.Y.Z> release, the operator tags the version, pushes, and **runs `git ls-remote origin v<X.Y.Z>` to verify the SHA matches** before declaring the cycle shipped (per `DEVELOPMENT_PROCESS.md`'s verify-before-claiming rule).

The executing AI does NOT tag, push, or claim the cycle is shipped until the operator's verification confirms origin's state. Cycle complete only when origin verification matches the expected SHA.

---

## Outputs

A successful cycle produces:

- **Updated lever home file** — committed via the committing agent (Claude Code session)
- **Calibration log entry** — appended to `~/Documents/QPB/docs/process/Lever_Calibration_Log.md`
- **Cell.json** — written to `~/Documents/QPB/metrics/regression_replay/<TIMESTAMP>/<benchmark>-<version>-all.json`, plus one cell.json per pinned benchmark in the cross-regression check
- **Per-cycle event log** — `<target>/quality/run_state.jsonl` (v1.5.5+), one event per phase boundary plus per-post-condition `validation_result` events; format invariants in `references/run_state_schema.md`
- **Audit trail** — workspace-side directory `~/Documents/AI-Driven Development/Quality Playbook/Calibration Cycles/<YYYY-MM-DD>-<benchmark>-<version>/`; migrates to `docs/process/QPB_v<X.Y.Z>_Calibration_Cycle_*` at next version ship
- **Cycle visualization charts (optional, post-cycle)** — `bin/visualize_calibration.py` reads accumulated cycle data and emits four charts (per-bug × cycle heatmap, lever × benchmark heatmap, recall trajectory, Mermaid lever-interaction graph). Useful for cross-cycle review at release boundaries.

A dead-end cycle produces the same artifacts with the dead-end disposition recorded and the lever change reverted (revert commit on record).

---

## Failure modes and STOP boundaries

The executing AI must STOP and surface to the operator at the following points. STOP means: do not proceed; emit the current state to the audit trail, write a "STOP report" with (a) which boundary fired, (b) the cycle's state-so-far snapshot, (c) the recommended next operator action, and wait for explicit operator guidance. The operator may approve continuation, redirect to a different lever, or abort the cycle.

| Boundary | Trigger | Action |
|---|---|---|
| Pre-flight failure | Any of the nine pre-flight checks fails | STOP; surface the specific check + observed output |
| Phase-1-3 run failed | Step 1's playbook invocation aborted or wrote no `### BUG-` / `## BUG-` entries | STOP; surface the run log |
| Recall is 100% | Step 3 produces `recall == 1.0` (or 1.0 over `<focus_bugs>`) | STOP; report no calibration needed |
| Heterogeneous missed bugs | Step 4 can't characterize a class | STOP; capture the heterogeneous-bugs analysis in audit trail; surface for cycle splitting |
| Apparatus / runner debt | Step 4 finds the missed-bug "class" is actually a runner failure (CLI crash, truncation) | STOP before Step 5; don't burn a lever pull on apparatus debt |
| No lever fits | Step 5's hypothesis can't pick one lever | STOP; surface the question to the operator |
| Multi-lever motivation | At any step, the missed-bug class clearly requires changes in two+ lever home files | STOP; surface; cycle should be split |
| Iteration limit | Step 6 iteration count reaches 5 | STOP; escalate to operator |
| Orchestrator review identifies issues | Step 7's first-pass review wants revisions | Return to Step 6 with feedback; iterate (until iteration limit) |
| Council holds | Step 7's Council verdict is Hold-with-fixes | Return to Step 6 with Council findings; iterate |
| Council blocks | Step 7's Council verdict is Block | STOP; reassess the diagnosis or lever choice |
| Source-unchanged abort during validation | Step 8.2's run aborts because working tree isn't clean | STOP; check Step 8.0 commit + Step 8.1 cleanup were performed correctly |
| Validation failure | Step 8.4's `recall_after - recall_before <= noise_floor_threshold` | REVERT (Step 8.5); document dead end (Step 10); STOP |
| Cross-benchmark regression | Step 9's any pinned benchmark drops beyond threshold | REVERT; document dead end; STOP |
| SCHEMA validation failure on cell.json | Step 11 manual field check finds a required field missing or type-wrong | STOP; surface the field + observed value; ask operator |
| Tag-push verification failure | Step 12's `git ls-remote origin v<X.Y.Z>` doesn't match expected SHA | STOP; do not declare shipped (per DEVELOPMENT_PROCESS.md's verify-before-claiming) |

The executing AI must NEVER:

- Run the playbook against pinned benchmarks before Council Ship verdict (wastes runner cost on un-validated changes)
- Edit files outside the lever's home file in Step 6 (scope discipline)
- Commit changes itself (committing is the committing agent's job, not the executing AI's)
- Pull a different lever than the one Council approved (silent scope creep)
- Skip the cross-benchmark check (Step 9 is mandatory; a lever that improves one target while harming another is a net negative)
- Run bare `git clean -fd` from the QPB repo root (would wipe audit-trail scratch and other untracked files)

---

## Cross-references

- **`~/Documents/QPB/ai_context/IMPROVEMENT_LOOP.md`** — methodology context: why levers exist, what each lever controls, the lever inventory (1-6)
- **`~/Documents/QPB/metrics/regression_replay/SCHEMA.md`** — cell.json schema and the calibration-log entry template (with the discrepancies noted at top of this document; the SCHEMA additive update remains tracked)
- **`~/Documents/QPB/references/run_state_schema.md`** — v1.5.5 event taxonomy for the per-cycle `quality/run_state.jsonl` log: event kinds (`phase_started` / `phase_completed` / `phase_aborted` / `validation_result`), required fields, and cross-validation rules at phase boundaries
- **`~/Documents/QPB/agents/calibration_orchestrator.md`** — v1.5.5 spawn-and-resume orchestrator template that operationalizes Mode 1 (autonomous) execution of this protocol
- **`~/Documents/QPB/bin/run_state_lib.py`** — v1.5.5 read/parse/validate helpers + writers for the event log; use these rather than hand-parsing the JSONL
- **`~/Documents/QPB/bin/visualize_calibration.py`** — v1.5.5 cycle visualization (four charts: per-bug × cycle heatmap, lever × benchmark heatmap, recall trajectory, Mermaid lever-interaction graph)
- **`~/Documents/QPB/ai_context/DEVELOPMENT_PROCESS.md`** — Council protocol invocation, mutation-test discipline, calibrated reporting, AI-identity discipline, fresh-Claude-Code-session-for-canonical-commit
- **`~/Documents/AI-Driven Development/CLAUDE.md`** — Council protocol mechanics (the actual `gh copilot` invocation discipline, cd-into-repo requirement, nested-panel header), source-edit lanes, verify-before-claiming
- **`~/Documents/QPB/docs/process/Lever_Calibration_Log.md`** — the historical record of all cycles; canonical home (workspace `Quality Playbook/Reviews/Lever_Calibration_Log.md` is a replica per DEVELOPMENT_PROCESS.md)
- **`~/Documents/QPB/docs/design/QPB_v1.5.5_Design.md`** and **`QPB_v1.5.5_Implementation_Plan.md`** — canonical home for the v1.5.5 orchestration substrate that this protocol uses
- **`~/Documents/QPB/docs/design/QPB_v1.6.x_Requirements_Review_Proposal.md`** — canonical scope for v1.6.0 (Requirements Review feature; the prior "first iterative-improvement release" framing is now satisfied by v1.5.5 + v1.5.6)
- **`~/Documents/QPB/docs/design/QPB_v1.7.0_Design.md`** and **`QPB_v1.7.0_Implementation_Plan.md`** — Statistical Process Control machinery: Shewhart control limits applied to both the improvement loop and QPB's own SDLC; the long-horizon target for accumulated calibration-cycle data
