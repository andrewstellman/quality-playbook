# AI Orchestration Patterns

*Last updated: 2026-05-03 (v1.5.6 currency pass — initial publication in v1.5.6 Phase 1; this pass adds a "Lessons from v1.5.6 use" section reflecting the first end-to-end use of the pattern through a release).*

> This document describes a reusable pattern for coordinating two AI sessions through a shared directory: a chat-driving **orchestrator** session writes instructions into a folder, and a long-lived coding **worker** session polls the folder, executes each instruction, and writes results back. The two sessions never share memory; the directory is the canonical record of what was instructed and what happened.

The pattern is in active use across multiple QPB workstreams. Section 9 walks through a real example end-to-end (the v1.5.5 ai_context-refresh runner) and notes how additional runners coexist alongside it. Section 8 explains how to apply the pattern in your own project without reading any QPB source code.

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
  <brief>         # one-time: comms convention + project-context list (see below)
  instructions/   # orchestrator writes here; worker reads + processes in order
    .processed/   # archive of completed instruction files (see below)
  outputs/        # worker writes here; orchestrator reads + archives
  STATUS.md       # worker rewrites atomically with current state
  STOP            # orchestrator (or worker) creates this file to halt cleanly
```

`<runner-name>` is freeform — `v1.5.5_runner`, `model-comparison_runner`, your own `<project>_runner`. Multiple runners coexist by having distinct folders. The workspace path is wherever both sessions can reach: for QPB development it's `~/Documents/AI-Driven Development/Quality Playbook/`; for an adopter it might be a project root, a separate orchestration directory, or anywhere on a shared filesystem both AI sessions can mount.

The brief file at the runner root is one-time setup: it states the comms convention (the same one this doc describes), names the project context the worker should read at session start, and clarifies any source-edit authority. By convention this file is `README.md` (v1.5.6+ form); QPB's v1.5.5 runner used `WATCHER_PROMPT.md` for the same purpose. Either filename works as long as both sessions agree. The worker reads it once when it starts; the orchestrator does not need to update it during normal operation.

The `.processed/` subdirectory under `instructions/` archives completed instructions. QPB's v1.5.5 runner used a required `.processed/` step (the worker moved each instruction into `.processed/` after writing the matching output, leaving `instructions/` containing only unprocessed work); v1.5.6's runner makes the same step optional and the worker uses an "instruction file with no matching output" lookup instead. Adopters can choose either form — the protocol works as long as the worker has a deterministic way to find the next unprocessed instruction.

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

Worker writes to `outputs/NNN-<short-description>.md` matching the instruction's number and short description. (QPB's v1.5.5 runner used an older form, `outputs/NNN-<short-description>.md.out.md`, where the `.out.md` suffix was appended to the full instruction filename; section 9's worked example reflects that historical convention. The v1.5.6+ form drops the suffix.) Contents:

- **status** — `completed` / `failed` / `partial`. Machine-readable.
- **what was done** — concrete: file paths edited, commands run, commits landed (with SHAs).
- **artifacts produced** — list of paths, with line counts or sizes if relevant.
- **errors** — anything that didn't go to plan, even if recovered.
- **follow-up notes** — open questions for the orchestrator, deviations from the instruction, suggestions.

The output is the audit artifact. If a teammate or a future AI session needs to know what happened during a run, they read the output file — not chat scrollback.

The worker also rewrites `STATUS.md` after each instruction completes. `STATUS.md` is a snapshot, not a log: it summarizes the runner's current state (most recent instruction, most recent output, branch HEAD if relevant, any pending issues). The orchestrator polls `STATUS.md` for "where is the worker right now"; the output file series is the historical record.

**A minimal STATUS.md looks like this** (modeled on `v1.5.6_runner/STATUS.md`):

```markdown
# my-project runner — STATUS

**State:** idle (awaiting next instruction)
**Last instruction:** 003-add-fast-path-for-empty-input.md
**Last output:** outputs/003-add-fast-path-for-empty-input.md (status: completed)
**Started:** 2026-05-03T20:05:00Z
**Last update:** 2026-05-03T20:13:00Z

**Branch:** `main`. HEAD: `aef574d <subject>`. 2 commits since branch base.

**Test suite:** 1017 / 0 failures / 5 skipped.

**Polling:** active for new instructions in `instructions/` or a `STOP` file.
```

State values are worker-defined; common values are `idle`, `executing instruction NNN`, `halted (STOP)`, `failed (see outputs/<NNN>)`. The orchestrator reads `State:` and `Last output:` to decide whether to wait, write a follow-up instruction, or intervene.

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

The same architectural separation applies outside QPB. It's useful when:

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

The pattern is reusable — you can adapt it for multi-session AI work in your own project. Concrete steps:

**Step 1 — Create a runner folder.** Anywhere both your orchestrator and worker AI sessions can read and write. A directory under your project root is fine; a separate orchestration directory under your home folder is fine. Name the folder distinctly (`<project>_runner`) so multiple runners coexist without conflict.

```
mkdir -p my_project_runner/instructions
mkdir -p my_project_runner/outputs
# Optional: archive completed instructions instead of leaving them in place.
mkdir -p my_project_runner/instructions/.processed
```

The `.processed/` archive is optional — see section 2's note on the v1.5.5-vs-v1.5.6 variation. If you skip it, your worker uses an "instruction file with no matching output" lookup; if you create it, your worker can simply look for the lowest-numbered file in `instructions/`.

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

**Step 3 — Spin up your worker.** Open the coding AI in a terminal under your project. Hand it a one-paragraph brief:

> *"Poll `instructions/` every ~30 seconds for the lowest-numbered file with no matching `outputs/<same-name>.md`; execute it; write the output; update `STATUS.md`; loop. On every poll, also check for a `STOP` file at the runner root — if present, write a final `STATUS.md` summary and exit cleanly without processing any pending instructions."*

The worker should also read the runner's README (or `WATCHER_PROMPT.md` — whichever name you chose) once at startup.

**Step 4 — Spin up your orchestrator.** Open a chat session with your planning AI. Tell it where the runner folder is and that it's the orchestrator. Optionally, hand it the same README so both sides agree on the convention.

**Step 5 — Start writing instruction files.** Begin with `instructions/001-<short-description>.md`. Each instruction is self-contained — a goal, the work items, the expected output schema, the acceptance criteria. The worker picks it up on its next poll and produces `outputs/001-<short-description>.md`.

**Step 6 — Read the output.** The orchestrator reads the output file (and `STATUS.md`), decides whether anything needs follow-up, and writes the next instruction. Repeat.

**Step 7 — Drop STOP when done.** Either side can do this. The worker's next poll detects the file, writes a final `STATUS.md` summary, and exits. The runner folder is now a complete record of what happened — you can revisit it, hand it to a teammate, archive it, or use it as an audit artifact.

**Practical considerations:**

- *Concurrency.* Multiple runners can run simultaneously without conflict, as long as their folders are distinct. The orchestrator and worker for runner A are completely independent of those for runner B. If two runners might edit the same files (e.g., both touch your project's source), use branch convention or directory partitioning to keep their working trees disjoint. **Branch-state hazard.** Two AI sessions sharing the same git checkout can step on each other's branch state — one session's `git checkout other-branch` will surprise the other session's next commit. QPB hit this during the v1.5.5 ai_context refresh: the worker observed `1.5.5` checked out at pre-flight, and a separate Cowork session switched the working tree to `1.5.6` before the worker's commit landed. Mitigations include separate worktrees per runner (`git worktree add`), separate clones, or an explicit `git branch --show-current` check immediately before every commit so the worker can refuse to commit on the wrong branch.
- *Permissions.* The pattern works whether the orchestrator and worker are the same LLM with the same permissions, or different LLMs with different permissions. The file boundary is the contract; what's behind each side is up to you. A common setup: the orchestrator runs in a chat session with broad workspace read access but no source-edit authority, and the worker runs in a coding tool with full source-edit authority on the project under review.
- *Audit.* The runner folder, after a run completes, is a self-contained record of every instruction issued and every result produced. No chat scrollback is needed to understand what happened. If you keep the runner folder under version control, the instruction-output pairs become a permanent audit artifact you can revisit months later.
- *Failure modes.* If the worker crashes, restart it; it picks up from the lowest-numbered instruction whose output is missing. If the orchestrator's chat session is compacted, a fresh chat session can re-orient by reading `STATUS.md` and the latest output, then resume writing instructions where the previous session stopped. A failed instruction (output `status: failed`) is read by the orchestrator like any other output — the orchestrator decides whether to retry, revise the instruction, or escalate.
- *Instruction sizing.* An instruction should be a single coherent unit of work that the worker can complete and report back on. Too small (one-line changes) wastes the file-coordination overhead; too large (a multi-day project) defeats the audit-per-instruction property. In QPB's runners, a few hours of worker effort per instruction has been a comfortable size — the worker stays focused, and the orchestrator can read the output and react before too much divergence accumulates.
- *Idempotence.* Instructions that can be safely re-run (e.g., "ensure file X has property Y") are easier to recover when something goes wrong. Instructions that mutate state irreversibly (commit, push, send) should say so explicitly in the output and should be at the end of an instruction's task list, not the middle, so a partial completion is recoverable.

**A common pitfall: chat-driven shortcuts that bypass the file boundary.** If the orchestrator finds itself dictating commands directly into a worker's chat (or vice versa) instead of writing instruction files, the audit trail is silently broken — the directory record no longer reflects what happened. This is a slow-failure mode: the work proceeds, but a future review of the runner folder will show gaps. The discipline is to put every meaningful instruction in a file, even when it feels overlong; the file is the record.

---

## 9. Worked example: the v1.5.5 ai_context-refresh runner

The QPB repo's `~/Documents/AI-Driven Development/Quality Playbook/v1.5.5_runner/` folder is a complete real-world example of the pattern in use. The runner coordinated a Cowork orchestrator and a Claude Code worker through five instructions during the v1.5.5 ship sequence.

**Setup.** The runner folder contained:

```
v1.5.5_runner/
  WATCHER_PROMPT.md     # the brief — v1.5.5 used this filename; v1.5.6+ uses README.md
  STATUS.md
  instructions/
    .processed/         # required move-after-completion archive in this runner
  outputs/
```

The brief (`WATCHER_PROMPT.md`) named the comms convention and listed the project context the worker should read at session start. The Cowork orchestrator wrote each instruction file to `instructions/`; the Claude Code worker (running under `~/Documents/QPB`) polled the folder.

**The instruction sequence.** Five instructions landed during the v1.5.5 ship:

| Instruction | Scope | Resulting commit(s) on `1.5.5` |
|---|---|---|
| `001-fix-bug-001-copilot-argv.md` | Fix BUG-001: CopilotRunner uses stdin instead of argv. | one fix-and-test commit |
| `002-fix-bug-002-progress-monitor-encoding.md` | Fix BUG-002: progress_monitor binary mode + byte offsets. | one fix-and-test commit |
| `003-switch-to-autonomous-mode.md` | Mode switch: stop polling instructions/ and work autonomously through the v1.5.5 spec. | (no commit — protocol switch) |
| `004-council-followups-and-version-prep.md` | Apply Council Round 2 P1 findings + bump version stamps + add README "What's new" section. | four commits, one per P1 |
| `005-refresh-ai-context.md` | Refresh all 7 `ai_context/*.md` files for v1.5.5 currency. | `58da0cd v1.5.5 docs: refresh ai_context/ orientation docs for v1.5.5 currency` |

Each instruction had a matching output file at `outputs/NNN-<same-name>.md.out.md` recording status, what was done, commits landed (with SHAs), test-suite result, and any deviations. (This `.md.out.md` suffix is the v1.5.5-era form; v1.5.6+ runners use the cleaner `outputs/NNN-<same-name>.md` per section 4.) The worker also moved each processed instruction into `instructions/.processed/` per the v1.5.5 protocol's required archive step, so the next-instruction lookup was always "first file in `instructions/`."

**The mode-switch instruction (003) is worth highlighting.** Up to instruction 002, the orchestrator was issuing one focused instruction at a time. Instruction 003 told the worker to switch to autonomous mode — read the v1.5.5 spec end-to-end and work through the remaining items without further instructions until reaching a halt boundary. The pattern accommodates both modes naturally: an orchestrator can either drive the worker step-by-step or hand it a larger scope and step back. The worker writes outputs the same way either way.

**The audit trail.** After v1.5.5 shipped, the entire `v1.5.5_runner/` folder remained as a record. Anyone reviewing what happened during the ship can read the five instruction files, the five output files, and the `STATUS.md` evolution to understand exactly what was instructed and what was done. No chat history reconstruction needed.

**Cross-running with other work.** The Cowork orchestrator was simultaneously doing other work in chat (drafting the v1.6.0 reframing, the v1.7.0 design, README rewrites that didn't touch QPB source). The runner folder was the boundary: anything that needed source edits went through `v1.5.5_runner/`; anything else stayed in chat. This is the diagnosis-then-Claude-Code-lane rule operationalized at the file level.

**Additional runners can coexist.** Beyond `v1.5.5_runner/` and `v1.5.6_runner/`, QPB plans a `model-comparison_runner/` for benchmark sweeps across `gh copilot --model` IDs (operating on `repos/model-comparison/` subfolders and using v1.5.5's tagged state rather than an in-flight branch). The pattern accommodates this naturally: each runner has its own folder, its own worker instance, its own scope, and no cross-talk with the others. The only coordination concern is that two workers shouldn't make conflicting source edits to the same files concurrently — for QPB that's handled by branch convention (each runner has a designated branch) and by some runners not editing QPB source at all.

---

## 9.5. Lessons from v1.5.6 use

v1.5.6 was the first release implemented end-to-end through the orchestrator/worker pattern documented in this file. The release covered Pattern 7 cycle execution (a multi-day calibration cycle across three benchmarks), the `bin/install_skill.py` adopter install script, and the v1.5.6 currency pass on this orientation-doc surface. Lessons that are worth surfacing for adopters considering the pattern for similarly-shaped work:

- **The autonomous worker correctly self-halted at the long-running cycle instruction.** When the v1.5.6 cycle instruction told the worker to drive the Pattern 7 cycle end-to-end through the v1.5.5 orchestration machinery, the worker began the cycle and reached a natural halt boundary (per-benchmark playbook run completion) rather than spinning indefinitely on an unbounded task. The worker's halt-and-report behavior at boundaries kept the audit trail clean and let the orchestrator decide whether to issue a follow-up instruction. **Lesson:** instructions should name a clear halt boundary even when the work is long-running; the worker will self-halt at the boundary and report.
- **Cowork-style orchestration handed off cleanly to Codex when the Anthropic budget became constrained.** Mid-release, the orchestrator hit the Anthropic API budget limit. The runner-folder pattern made the handoff to a Codex-backed worker trivial: switch the worker backend, point Codex at the same instruction file the previous worker had been processing, let Codex pick up from where the previous worker had logged its last output. **Lesson:** the file-based instruction/output protocol is backend-agnostic by construction; switching workers across LLM backends mid-release is straightforward when the protocol is followed.
- **The runner folder pattern proved robust under multi-day, multi-tool execution.** v1.5.6 spanned three calendar days, two LLM backends (Claude Code + Codex), and at least three distinct work surfaces (cycle execution, install-script implementation, orientation-doc currency pass). The runner folder remained the canonical record across all of it; no chat scrollback was needed to reconstruct what happened. **Lesson:** the pattern scales across multi-day windows and tool switches without modification; the file boundary is the contract.
- **Be explicit about the polling loop pattern in the worker brief.** The original `until` polling loop the worker chose for v1.5.5 was a one-shot construct (check once, exit if no instruction found) rather than a continuous loop. This worked for the v1.5.5 instruction sequence because the orchestrator dropped instructions in immediately-readable batches, but it would have failed on a workflow that required the worker to wait for an instruction to appear later. **Lesson:** the worker brief should specify "loop forever, polling at <interval>, until STOP" rather than leaving the loop pattern implicit. Section 8's adopter-facing brief now spells this out explicitly; for QPB's own runners this was an undocumented assumption that happened to work.

These lessons are operational; the pattern itself is unchanged. If you're adopting the pattern for your own project, the section 8 brief incorporates the explicit-loop guidance; the cycle and multi-day evidence above are the empirical case for the pattern's robustness.

---

## 10. Cross-references

- **`~/Documents/AI-Driven Development/CLAUDE.md`** (workspace) — establishes the diagnosis-then-Claude-Code-lane rule that this pattern operationalizes. The QPB-source-is-hands-off-for-Cowork-Claude carve-out is the architectural reason QPB development uses this pattern by default.
- **`agents/calibration_orchestrator.md`** — the related single-session pattern. Use it when one AI session drives an end-to-end calibration cycle and resumes itself across crashes via `quality/run_state.jsonl`. Use this multi-session orchestrator/worker pattern when the work needs a chat-side planner and a separate coding-side executor.
- **`ai_context/DEVELOPMENT_PROCESS.md`** — broader QPB SDLC context, including the Claude Code handoff conventions, the Council protocol, and the run-state instrumentation introduced in v1.5.5. The orchestrator/worker pattern fits inside the development process described there as the default execution mode for any work that requires QPB source edits.
- **`AGENTS.md`** — install procedure that uses this pattern's premises: an AI agent driving the install reads the install commands from AGENTS.md and executes them. The AI agent is acting as the worker; the operator giving the install instruction is acting as the orchestrator.
