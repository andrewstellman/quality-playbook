# AI Orchestration Patterns

*Last updated: 2026-05-03 (v1.5.6 Phase 1 — initial publication).*

> This document describes a reusable pattern for coordinating two AI sessions through a shared directory: a chat-driving **orchestrator** session writes instructions into a folder, and a long-lived coding **worker** session polls the folder, executes each instruction, and writes results back. The two sessions never share memory; the directory is the canonical record of what was instructed and what happened.

The pattern is in active use across multiple QPB workstreams. Section 9 walks through a real example end-to-end (the v1.5.5 ai_context-refresh runner). Section 10 describes a second concurrent use case (a model-comparison benchmark sweep). Section 8 explains how to apply the pattern in your own project without reading any QPB source code.

---

## 1. The pattern, named

**Orchestrator/worker via shared directory.**

A chat-driving AI session (the *orchestrator* — Cowork, ChatGPT, Claude.ai, or any chat surface) controls a long-lived coding AI session (the *worker* — Claude Code, Cursor agent, codex CLI, or any tool with file-edit and command-execution authority) by exchanging files in a directory both sessions can read and write.

- The orchestrator produces *instructions* (what to do) as numbered Markdown files.
- The worker polls the directory, processes the next instruction in sequence, and produces an *output* file (what was done) for each one.
- Either side can drop a `STOP` sentinel file to halt the loop cleanly.
- A `STATUS.md` file at the runner root carries the worker's current state; the orchestrator reads it to know where the worker is without opening the full output history.

Neither session retains in-memory state across crashes or context compactions. If the worker is killed and restarted, it reads the directory and resumes from the lowest-numbered instruction whose output file is missing. If the orchestrator's chat session is compacted, the next message can re-orient by reading `STATUS.md` and the latest output.

---

## 2. Folder convention

```
<workspace>/<runner-name>/
  README.md       # one-time: comms convention + project-context list
  instructions/   # orchestrator writes here; worker reads + processes in order
    .processed/   # worker moves completed instruction files here (optional)
  outputs/        # worker writes here; orchestrator reads + archives
  STATUS.md       # worker rewrites atomically with current state
  STOP            # orchestrator (or worker) creates this file to halt cleanly
```

`<runner-name>` is freeform — `v1.5.5_runner`, `model-comparison_runner`, your own `<project>_runner`. Multiple runners coexist by having distinct folders. The workspace path is wherever both sessions can reach: for QPB development it's `~/Documents/AI-Driven Development/Quality Playbook/`; for an adopter it might be a project root, a separate orchestration directory, or anywhere on a shared filesystem both AI sessions can mount.

The optional `.processed/` subdirectory under `instructions/` lets the worker move each instruction after writing the matching output, so the next-instruction lookup is a simple "first file in `instructions/`." Whether to use it is a worker convention, not a hard requirement; the orchestrator does not need to know.

The `README.md` at the runner root is one-time setup: it states the comms convention (the same one this doc describes), names the project context the worker should read at session start, and clarifies any source-edit authority. The worker reads it once when it starts; the orchestrator does not need to update it during normal operation.

---

## 3. Instruction file format

Markdown file at `instructions/NNN-<short-description>.md`. `NNN` is a zero-padded sequence number (`001`, `002`, ...). The worker processes in numerical order. Each instruction file is self-contained: a goal statement, the work items, the expected outputs (with paths relative to the runner folder), success criteria, and any context the worker needs to do the work without additional clarification.

A typical instruction has these sections:

- **Goal** — one paragraph; the outcome the orchestrator wants.
- **Read these first** — files the worker must absorb before acting.
- **Tasks** — the actual work items, in order, each with concrete acceptance criteria.
- **Output you write back** — the schema for the matching output file (status, artifacts, follow-up notes).
- **Out of scope** — explicit boundaries so the worker doesn't drift.

Self-containment is important. The worker may not be the same session that processed the previous instruction (context may have compacted, or a fresh worker may have spun up). Instructions that depend on shared mental state with the orchestrator break this property and should be rewritten to put the context inline.

**A minimal instruction file looks like this:**

```markdown
# Instruction 002 — Add a fast-path for empty inputs to `parse_records()`

**Goal**

When `parse_records()` is called with an empty string, it currently
walks the parse loop and returns `[]` after a no-op. Add an early
return at the top of the function so the empty-input case skips the
loop entirely.

**Read these first**

- `src/parser.py` — the file to edit.
- `tests/test_parser.py` — where the new regression test goes.

**Tasks**

1. Edit `src/parser.py:parse_records()` to return `[]` immediately
   if the input is empty (after the existing input-type check).
2. Add `tests/test_parser.py::test_parse_records_empty_input_fast_path`
   that asserts the function returns `[]` AND does not call the
   tokenizer (use a mock).
3. Run `python -m pytest tests/` and confirm all tests pass.
4. Commit on the current branch with message
   `parser: fast-path empty input in parse_records()`.

**Output schema**

```yaml
status: completed | failed | partial
files_changed:
  - <path>: <one-line summary>
commit_sha: <SHA>
test_result: <pass/fail summary>
notes: |
  <any deviations or follow-up>
```
```

The instruction stays self-contained even if the worker has never seen
the project before — paths are explicit, the acceptance criteria are
unambiguous, and the output schema names exactly what the orchestrator
needs back.

---

## 4. Output file format

Worker writes to `outputs/NNN-<short-description>.md` matching the instruction's number and short description. Contents:

- **status** — `completed` / `failed` / `partial`. Machine-readable.
- **what was done** — concrete: file paths edited, commands run, commits landed (with SHAs).
- **artifacts produced** — list of paths, with line counts or sizes if relevant.
- **errors** — anything that didn't go to plan, even if recovered.
- **follow-up notes** — open questions for the orchestrator, deviations from the instruction, suggestions.

The output is the audit artifact. If a teammate or a future AI session needs to know what happened during a run, they read the output file — not chat scrollback.

The worker also rewrites `STATUS.md` after each instruction completes. `STATUS.md` is a snapshot, not a log: it summarizes the runner's current state (most recent instruction, most recent output, branch HEAD if relevant, any pending issues). The orchestrator polls `STATUS.md` for "where is the worker right now"; the output file series is the historical record.

---

## 5. Lifecycle

```
orchestrator                         worker
------------                         ------
write instructions/001-...md   →     poll instructions/
                                     read 001-...md
                                     execute
                                     write outputs/001-...md
                                     rewrite STATUS.md
                               ←     (orchestrator reads STATUS.md + output)

write instructions/002-...md   →     ... (repeat)
                                     ...

write STOP                     →     poll detects STOP
                                     write final STATUS.md
                                     exit
```

The worker's poll cadence is a worker decision — once every 30 seconds is typical for QPB's runners; an adopter handling shorter or longer instructions might tune up or down. A poll that finds neither a new instruction nor a `STOP` file results in a no-op and another sleep. A poll that finds a `STOP` file results in a final `STATUS.md` rewrite and a clean exit; the worker does not process any pending instructions after seeing `STOP`.

The orchestrator does not need to know the worker's poll interval. It writes an instruction, waits for the matching output file to appear, then writes the next instruction. If the orchestrator wants the worker to halt mid-sequence, dropping `STOP` is the only signal needed.

---

## 6. Why this pattern exists, in QPB's context

The workspace `CLAUDE.md` establishes a **diagnosis-then-Claude-Code lane** rule: Cowork (chat surface, broad workspace access, NOT authorized to edit QPB source files except orientation docs) proposes diffs in chat with file paths, line numbers, and a runnable handoff command; Claude Code (running with QPB source-edit authority in a separate terminal session) applies the diffs. The orchestrator/worker pattern is the file-level realization of that rule.

Concretely:

- The orchestrator (Cowork chat session) writes an instruction file describing what needs to change in QPB source — file paths, line ranges, the diff or the prose intent, the acceptance criteria.
- The worker (Claude Code session running in a terminal under the QPB checkout) reads the instruction file, makes the edits, runs the test suite, and commits.
- The output file records exactly what landed: the SHAs, the test result, anything the orchestrator should know.

The architectural reason — separating "decides what to do" from "does the file edits" — generalizes beyond QPB. It applies whenever:

- The chat surface (orchestrator) and the editing surface (worker) are different LLMs or different installs of the same LLM with different permissions.
- The work is long-running and the chat session might be context-compacted or interrupted before the work completes.
- The audit trail of what was instructed vs. what was done matters more than chat scrollback can preserve.

---

## 7. When to use this pattern vs. alternatives

**Use it when:**

- Work spans more than one chat session.
- Orchestrator and worker should run different LLMs (cost, capability, permissions, or trust reasons).
- The work is long-running (hours) and the chat session might be context-compacted before completion.
- You want a clean audit trail of what was instructed and what was actually done, separate from chat history.
- You want the worker to be killable and resumable without losing progress.

**Don't use it when:**

- The work fits in a single chat session with no compaction risk.
- Orchestrator and worker can plausibly be the same session.
- You don't need the audit trail and the overhead of file-based coordination is wasted.

**Compare with `agents/calibration_orchestrator.md`.** That document describes a single-session pattern: one Claude Code session reads a prompt template, spawns playbook subprocesses, polls their state files, and resumes itself across crashes via `quality/run_state.jsonl`. The contrast with this multi-session pattern:

| Dimension | `calibration_orchestrator.md` (single-session) | `AI_ORCHESTRATION_PATTERNS.md` (this doc; multi-session) |
|---|---|---|
| Sessions | One AI session drives end-to-end | Two AI sessions, coordinating via files |
| State carrier | Per-cycle `run_state.jsonl` event log | Per-runner `instructions/` + `outputs/` directory |
| Crash recovery | Same session reads its own event log on restart | Either session can resume; the directory is the record |
| Typical use | A coordinated cycle that wants one decision-maker | Chat-side planner + coding-side executor as a pair |

Use the calibration-orchestrator pattern when the work is one tight coordinated cycle that one session can drive end-to-end. Use this orchestrator/worker pattern when you want a chat-side planner and a coding-side executor working as a pair — particularly when the chat surface is not authorized to make the edits the work requires.

---

## 8. Applying this pattern in your own project (adopter-grade)

The pattern is portable. You can use it for any multi-session AI work, not just QPB development. Concrete steps:

**Step 1 — Create a runner folder.** Anywhere both your orchestrator and worker AI sessions can read and write. A directory under your project root is fine; a separate orchestration directory under your home folder is fine. Name the folder distinctly (`<project>_runner`) so multiple runners coexist without conflict.

```
mkdir -p my_project_runner/instructions
mkdir -p my_project_runner/outputs
```

**Step 2 — Write a one-page README.md in the runner folder.** The README states the comms convention (cite this doc), names the project context your worker should read at session start, and clarifies any source-edit authority. Example:

```markdown
# my-project runner

This folder coordinates a [chat AI] (orchestrator) and a [coding AI]
(worker) doing work on my-project.

## Comms convention

Per ai_context/AI_ORCHESTRATION_PATTERNS.md (or equivalent reference).

- instructions/NNN-<short>.md — orchestrator drops here in numerical order.
- outputs/NNN-<short>.md — worker writes one matching output per instruction.
- STATUS.md — worker rewrites atomically with current state.
- STOP — either side creates to halt cleanly.

## Worker loop

Every ~30s: check STOP, find lowest-numbered instruction without a
matching output, execute it, write the output, rewrite STATUS.md.

## Project context to read at session start

- README.md
- <other canonical docs the worker needs>
```

**Step 3 — Spin up your worker.** Open the coding AI in a terminal under your project. Hand it a one-paragraph brief: *"poll `instructions/`, execute the next file in numeric order, write outputs to `outputs/<same-number>.md`, update `STATUS.md`, halt on `STOP`."* The worker should also read the runner's README.md once at startup.

**Step 4 — Spin up your orchestrator.** Open a chat session with your planning AI. Tell it where the runner folder is and that it's the orchestrator. Optionally, hand it the same README so both sides agree on the convention.

**Step 5 — Start writing instruction files.** Begin with `instructions/001-<short-description>.md`. Each instruction is self-contained — a goal, the work items, the expected output schema, the acceptance criteria. The worker picks it up on its next poll and produces `outputs/001-<short-description>.md`.

**Step 6 — Read the output.** The orchestrator reads the output file (and `STATUS.md`), decides whether anything needs follow-up, and writes the next instruction. Repeat.

**Step 7 — Drop STOP when done.** Either side can do this. The worker's next poll detects the file, writes a final `STATUS.md` summary, and exits. The runner folder is now a complete record of what happened — you can revisit it, hand it to a teammate, archive it, or use it as an audit artifact.

**Practical considerations:**

- *Concurrency.* Multiple runners can run simultaneously without conflict, as long as their folders are distinct. The orchestrator and worker for runner A are completely independent of those for runner B. If two runners might edit the same files (e.g., both touch your project's source), use branch convention or directory partitioning to keep their working trees disjoint.
- *Permissions.* The pattern works whether the orchestrator and worker are the same LLM with the same permissions, or different LLMs with different permissions. The file boundary is the contract; what's behind each side is up to you. A common setup: the orchestrator runs in a chat session with broad workspace read access but no source-edit authority, and the worker runs in a coding tool with full source-edit authority on the project under review.
- *Audit.* The runner folder, after a run completes, is a self-contained record of every instruction issued and every result produced. No chat scrollback is needed to understand what happened. If you keep the runner folder under version control, the instruction-output pairs become a permanent audit artifact you can revisit months later.
- *Failure modes.* If the worker crashes, restart it; it picks up from the lowest-numbered instruction whose output is missing. If the orchestrator's chat session is compacted, a fresh chat session can re-orient by reading `STATUS.md` and the latest output, then resume writing instructions where the previous session stopped. A failed instruction (output `status: failed`) is read by the orchestrator like any other output — the orchestrator decides whether to retry, revise the instruction, or escalate.
- *Instruction sizing.* An instruction should be a single coherent unit of work that the worker can complete and report back on. Too small (one-line changes) wastes the file-coordination overhead; too large (a multi-day project) defeats the audit-per-instruction property. Empirically, a few hours of worker effort per instruction is a healthy size — the worker stays focused, and the orchestrator can read the output and react before too much divergence accumulates.
- *Idempotence.* Instructions that can be safely re-run (e.g., "ensure file X has property Y") are easier to recover when something goes wrong. Instructions that mutate state irreversibly (commit, push, send) should say so explicitly in the output and should be at the end of an instruction's task list, not the middle, so a partial completion is recoverable.

**A common pitfall: chat-driven shortcuts that bypass the file boundary.** If the orchestrator finds itself dictating commands directly into a worker's chat (or vice versa) instead of writing instruction files, the audit trail is silently broken — the directory record no longer reflects what happened. This is a slow-failure mode: the work proceeds, but a future review of the runner folder will show gaps. The discipline is to put every meaningful instruction in a file, even when it feels overlong; the file is the record.

---

## 9. Worked example: the v1.5.5 ai_context-refresh runner

The QPB repo's `~/Documents/AI-Driven Development/Quality Playbook/v1.5.5_runner/` folder is a complete real-world example of the pattern in use. The runner coordinated a Cowork orchestrator and a Claude Code worker through five instructions during the v1.5.5 ship sequence.

**Setup.** The runner folder contained:

```
v1.5.5_runner/
  README.md
  STATUS.md
  instructions/
    .processed/
  outputs/
```

The README named the comms convention and listed the project context the worker should read at session start. The Cowork orchestrator wrote each instruction file to `instructions/`; the Claude Code worker (running under `~/Documents/QPB`) polled the folder.

**The instruction sequence.** Five instructions landed during the v1.5.5 ship:

| Instruction | Scope | Resulting commit(s) on `1.5.5` |
|---|---|---|
| `001-fix-bug-001-copilot-argv.md` | Fix BUG-001: CopilotRunner uses stdin instead of argv. | one fix-and-test commit |
| `002-fix-bug-002-progress-monitor-encoding.md` | Fix BUG-002: progress_monitor binary mode + byte offsets. | one fix-and-test commit |
| `003-switch-to-autonomous-mode.md` | Mode switch: stop polling instructions/ and work autonomously through the v1.5.5 spec. | (no commit — protocol switch) |
| `004-council-followups-and-version-prep.md` | Apply Council Round 2 P1 findings + bump version stamps + add README "What's new" section. | four commits, one per P1 |
| `005-refresh-ai-context.md` | Refresh all 7 `ai_context/*.md` files for v1.5.5 currency. | `58da0cd v1.5.5 docs: refresh ai_context/ orientation docs for v1.5.5 currency` |

Each instruction had a matching output file at `outputs/NNN-<same-name>.md` recording status, what was done, commits landed (with SHAs), test-suite result, and any deviations. The worker also moved each processed instruction into `instructions/.processed/` so the next-instruction lookup stayed simple.

**The mode-switch instruction (003) is worth highlighting.** Up to instruction 002, the orchestrator was issuing one focused instruction at a time. Instruction 003 told the worker to switch to autonomous mode — read the v1.5.5 spec end-to-end and work through the remaining items without further instructions until reaching a halt boundary. The pattern accommodates both modes naturally: an orchestrator can either drive the worker step-by-step or hand it a larger scope and step back. The worker writes outputs the same way either way.

**The audit trail.** After v1.5.5 shipped, the entire `v1.5.5_runner/` folder remained as a record. Anyone reviewing what happened during the ship can read the five instruction files, the five output files, and the `STATUS.md` evolution to understand exactly what was instructed and what was done. No chat history reconstruction needed.

**Cross-running with other work.** The Cowork orchestrator was simultaneously doing other work in chat (drafting the v1.6.0 reframing, the v1.7.0 design, README rewrites that didn't touch QPB source). The runner folder was the boundary: anything that needed source edits went through `v1.5.5_runner/`; anything else stayed in chat. This is the diagnosis-then-Claude-Code-lane rule operationalized at the file level.

**A wrinkle worth surfacing.** Instruction 005 (the ai_context refresh) ran while the parent Cowork session was also working on the `1.5.6` branch in the same checkout. Between the worker's pre-flight check (which observed `1.5.5` checked out) and the worker's commit, the parent session had switched the working tree to `1.5.6`. The worker's first commit therefore landed on `1.5.6` instead of `1.5.5`. The worker recovered by switching to `1.5.5` and cherry-picking the commit; the original duplicate stayed on `1.5.6` as expected. This is a multi-runner concurrency hazard: two AI sessions sharing a checkout can step on each other's branch state. The mitigation in QPB's case is branch convention (each runner has a designated branch); in your project it might be separate worktrees, separate clones, or explicit branch checks at every commit boundary.

---

## 10. Worked example: the model-comparison runner

A second concurrent use of the pattern handles the QPB model-comparison benchmark sweep. The setup illustrates the multi-runner case — the same convention, a different folder, different scope, no cross-talk with `v1.5.5_runner/` or `v1.5.6_runner/`.

**Goal.** Sweep `gh copilot --model <ID>` against the four pinned benchmarks (chi-1.3.45, chi-1.5.1, virtio-1.5.1, express-1.3.50), one model per instruction. Each instruction's output captures the per-benchmark recall numbers, the wall-clock duration, and any rate-limit observations.

**Why it's a separate runner.** The model-comparison sweep is independent of v1.5.6 implementation work — it operates on `repos/model-comparison/` subfolders and uses v1.5.5's tagged QPB state, not the in-flight `1.5.6` branch. Mixing these instructions into `v1.5.6_runner/` would cause confusion: the worker would not know whether the next instruction expects the `1.5.6` working tree or the `v1.5.5` tag. Separate runner folders make the contract obvious.

**The multi-runner case in general.** An adopter (or QPB itself) can have several runners active simultaneously without conflict:

- Each runner has a distinct folder.
- Each runner has its own worker instance (one terminal session per runner).
- Each runner's orchestrator is independent — could be the same chat session managing both, or different sessions.
- Workers can be different LLMs or the same LLM with different setups; the pattern doesn't care.

The only coordination concern is that two workers shouldn't make conflicting source edits to the same files concurrently. For QPB this is handled by branch convention (`1.5.6_runner/` works on `1.5.6`; the model-comparison runner doesn't edit QPB source at all, only its own `repos/model-comparison/` subtree).

**Status note.** The `model-comparison_runner/` folder is a planned use of the pattern; the runner's instruction files are being authored as a separate Cowork task and may not yet exist on disk in your local checkout. If you don't see the folder, the pattern itself is still illustrated by `v1.5.5_runner/` and the `v1.5.6_runner/` that produced this very document.

---

## 11. Cross-references

- **`~/Documents/AI-Driven Development/CLAUDE.md`** (workspace) — establishes the diagnosis-then-Claude-Code-lane rule that this pattern operationalizes. The QPB-source-is-hands-off-for-Cowork-Claude carve-out is the architectural reason QPB development uses this pattern by default.
- **`agents/calibration_orchestrator.md`** — the related single-session pattern. Use it when one AI session drives an end-to-end calibration cycle and resumes itself across crashes via `quality/run_state.jsonl`. Use this multi-session orchestrator/worker pattern when the work needs a chat-side planner and a separate coding-side executor.
- **`ai_context/DEVELOPMENT_PROCESS.md`** — broader QPB SDLC context, including the Claude Code handoff conventions, the Council protocol, and the run-state instrumentation introduced in v1.5.5. The orchestrator/worker pattern fits inside the development process described there as the default execution mode for any work that requires QPB source edits.
- **`AGENTS.md`** — install procedure that uses this pattern's premises: an AI agent driving the install reads the install commands from AGENTS.md and executes them. The AI agent is acting as the worker; the operator giving the install instruction is acting as the orchestrator.
