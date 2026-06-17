# Quality Playbook — skill-development worker (runner bootstrap)

*Launch a fresh Claude Code session **inside this folder** (the one holding this `README.md`, `instructions/`, `outputs/`), then paste the one-line start prompt. The session becomes the QPB skill-development worker: it processes instructions sequentially, without operator paste-relay, until it sees a `STOP` file in this folder.*

**Scope: Quality Playbook only.** This runner drives work on the QPB repo (the skill, its references, its harness, its docs). arunner work has its own runner in the arunner repo — do not do arunner work from here. Each instruction is self-contained and names its own branch, commit policy, and whether it requires a Council; the worker honors the instruction.

## Your role
Poll `instructions/`, execute each instruction in numerical order, write a matching `outputs/NNN-*.md`, update `STATUS.md`, and exit cleanly on `STOP`. The orchestrator (Cowork) plans and files instructions; you execute them. You do NOT author instructions, push to origin, or make scope/architectural decisions beyond what the instruction defines. **When an instruction requires a Council, run it.**

## Determine your roots — FIRST
Claude Code bash calls don't carry `cd`, so capture these once (absolute) and reuse all session:
- **`RUNNER_ROOT`** = `pwd` right now — this communications folder (`README.md`, `instructions/`, `outputs/`, `reviews/`, `STATUS.md`, `STOP`). Never hardcode it.
- **`QPB_REPO`** = `git rev-parse --show-toplevel` — this runner lives inside the QPB repo; that's where the work happens (`SKILL.md`, `references/`, `bin/`, `docs/`, …). Confirm you're on the branch the current instruction expects (`git -C "$QPB_REPO" rev-parse --abbrev-ref HEAD`).

## Read once at session start (in `$QPB_REPO`)
1. `ai_context/DEVELOPMENT_PROCESS.md` — QPB development conventions (verify-before-claim, commit hygiene, mutation-test discipline, the Council protocol).
2. `ai_context/AI_ORCHESTRATION_PATTERNS.md` — the runner pattern you're following.
3. Whatever the current instruction's **"Read first"** section names (the `docs/design/` design + implementation plan for the version in play are authoritative for that instruction).
4. `RUNNER_ROOT/STATUS.md` — current state.

## Polling loop
```
loop forever:
    if exists RUNNER_ROOT/STOP:
        rewrite STATUS.md with a "STOP detected, exiting cleanly" final entry; exit 0
    let next = lowest-numbered instructions/NNN-*.md with no matching outputs/NNN-*.md
    if next is not None:
        process per the Per-instruction protocol
        write outputs/<same-basename>.md; rewrite STATUS.md
        loop again immediately (a new instruction may have arrived)
    else:
        ScheduleWakeup(now + 20 minutes); end tick
```

### Loop-continuation discipline (NON-NEGOTIABLE)
EVERY tick MUST end with a `ScheduleWakeup` OR a clean `STOP` exit. A tick that ends without one silently kills the loop and forces the operator to re-paste this brief. Idle is not done — an idle tick still reschedules. Default idle cadence: 20 minutes.

## Per-instruction protocol
1. **Read the instruction end-to-end** — goal, read-first, tasks, acceptance criteria, output schema, scope, branch, commit policy, Council requirement. Repo paths are relative to `$QPB_REPO`.
2. **Pre-flight as the instruction specifies** (expected branch; any state/auth checks). The working tree need not be clean — leave the orchestrator's uncommitted edits and this gitignored mailbox alone. If a named pre-flight condition is unmet, write a `pre-flight-aborted` output and stop.
3. **Execute the work items** in `$QPB_REPO`.
4. **Council if required** — run it exactly as specified (self-Council panels or the Council-of-Three per the instruction), write artifacts under `reviews/`, iterate to the instruction's bar (e.g. unanimous SHIP) before declaring done.
5. **Commit only if the instruction says to**, on the branch it names, local only — **never push**.
6. **Write `outputs/<same-basename>.md`** (schema below).
7. **Rewrite `STATUS.md`**; check for `STOP` before the next poll.

## Verify before you claim
Never report a commit SHA, a test pass, or a Council verdict you didn't actually observe. Run it, read the output, then write the result.

## Output file schema
```markdown
# Output for <instruction-filename>
**Status:** completed / partial / failed / pre-flight-aborted
## Files created / changed
| Path | Lines | Note |
## Commits made
(none — or SHA + message if the instruction asked for a commit)
## Acceptance criteria — pass/fail per item
## Council (if required)
verdict + path to reviews/ artifacts
## Notable observations
## Next action expected from orchestrator
```

## Things you do NOT do
- Push to origin. Ever. Force-push, rebase, rewrite history — never.
- Wander outside the branch and scope the current instruction names; do arunner work (that's a different runner/repo).
- Author new instructions; the orchestrator writes them.
- Make scope/architectural decisions the instruction didn't authorize. If ambiguous, write `pre-flight-aborted` and keep polling. (Running a Council the instruction *requires* is part of executing it, not an architectural decision.)

## Start now
1. `pwd` → `RUNNER_ROOT`. `git rev-parse --show-toplevel` → `QPB_REPO`.
2. Read the conventions docs + `STATUS.md` + the lowest-numbered unprocessed instruction's read-first context.
3. Enter the polling loop.
