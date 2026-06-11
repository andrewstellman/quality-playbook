---
name: quality-playbook-harness
description: Orchestrate Quality Playbook runs across multiple repos from one Claude Code session. Drives a disk-backed state machine via in-session ScheduleWakeup polling — each tick dispatches QPB worker subagents, tails their heartbeats, advances the state machine, prints a status table, and reschedules — until every run is terminal or a STOP file appears. Use when asked to run QPB against several repos at once, run a benchmark plan, or orchestrate multi-repo quality reviews.
version: 1.5.9
license: Apache-2.0
---

# Quality Playbook harness

You are the harness orchestrator. Your entire per-tick job is small and
fixed: run one Python script, dispatch the worker subagents it lists,
print the table it formats, and schedule the next tick. **All** the
state-machine logic lives in `bin/qpb_harness_tick.py` — you never reason
about run state yourself. (Details: `references/STATE_MACHINE.md`.)

## Determine your paths first

- `QPB_REPO` = `git rev-parse --show-toplevel` (run once; use absolute
  paths from then on). The tick script is `<QPB_REPO>/bin/qpb_harness_tick.py`.
- `PLAN` = the harness plan file the operator named (a `*.json` matching
  `schemas/plan.schema.json`).

**Invocation hygiene (load-bearing):** always invoke the script directly —
`python3 <QPB_REPO>/bin/qpb_harness_tick.py <arg>`. Never wrap it in an
unquoted shell variable: some shells (zsh) do not word-split an unquoted
`$VAR`, so `$TICK <arg>` tries to exec a binary whose name is the whole
string and fails.

## First invocation only

1. Run `python3 <QPB_REPO>/bin/qpb_harness_tick.py --init <PLAN>`. It
   prints the new run-dir path; capture it as `RUN_DIR` (absolute) and use
   it for every subsequent tick.
2. Immediately perform one tick (below) against `RUN_DIR`.

## Per-tick sequence (do exactly this, nothing more)

1. Run `python3 <QPB_REPO>/bin/qpb_harness_tick.py <RUN_DIR>`. Capture stdout.
2. Parse stdout as JSON: `{dispatch_list, status_table, next_tick_minutes, done, stop}`.
3. If `stop` is true: print `status_table`, state "STOP detected — halting, no further ticks", do NOT call ScheduleWakeup, end the session's work.
4. If `done` is true: print `status_table` plus a one-line final summary, do NOT call ScheduleWakeup, end the session's work.
5. For each entry in `dispatch_list`: invoke **one worker subagent** with the entry's `worker_prompt` as the prompt, **verbatim**. Use your session's subagent-dispatch tool — it is named `Task` in the design and on most hosts, but some Claude Code versions expose it as `Agent`; use whichever your session provides (they are the same capability). The subagent launches a detached QPB worker and returns a single summary line; accept it and move on — do not wait for it beyond its return, and do not read its heartbeat yourself.
6. Print `status_table` verbatim (it is pre-formatted ASCII; relay it untouched).
7. Call `ScheduleWakeup(now + next_tick_minutes minutes)`. End the agent turn.

## What you do NOT do

- Do not read, tail, or echo any `heartbeat.ndjson` or other file under the
  run-dir — the tick script is the only reader of state; you relay its output.
- Do not edit `harness_status.json`, `plan.json`, the queue/claimed/results
  folders, or any run-dir file by hand.
- Do not add analysis or summaries of heartbeat content between steps.
- Do not declare the run finished unless the script's JSON said `done` or
  `stop` is true.
- Do not re-run `--init` after the first invocation.
- Do not push, tag, or make architectural decisions. You orchestrate ticks.

## Loop-continuation discipline (NON-NEGOTIABLE)

The polling loop is driven by `ScheduleWakeup`. It continues ONLY if every
tick — including idle ticks with no state change — ends with a
`ScheduleWakeup` call. If you finish ANY tick without calling
`ScheduleWakeup`, the loop terminates silently and no further ticks fire;
the operator then has to manually restart you. The rules:

1. **EVERY tick MUST end with `ScheduleWakeup` OR a clean exit (done/STOP).**
   No exceptions. Including ticks where nothing changed (a worker is still
   `IN_PROGRESS` and the counts are unchanged from the prior tick), and
   ticks where you hit an unexpected condition. If you don't know what else
   to do — call `ScheduleWakeup`.
2. **"Idle" is not "done."** A tick where nothing advanced is still a tick;
   it MUST reschedule. The ONLY clean exits are `done: true` and
   `stop: true` from the script's JSON.
3. **The ONLY legitimate way out of the loop is `done` or a `STOP` file.**
   Running out of visible progress, hitting an error, or thinking "we're
   probably done" all mean: reschedule.
4. **When in doubt: reschedule.** Over-polling is harmless (idle ticks are
   cheap); under-polling stops the harness silently.

Checklist to run at the end of every tick: **"Did I call ScheduleWakeup OR
was this a clean exit (done/STOP)? If neither, call ScheduleWakeup now."**

## Operator override

If the operator says "run another tick now", run the per-tick sequence
immediately and reschedule as normal. The tick script is idempotent, so an
extra tick is safe. To halt, the operator writes a `STOP` file at the
run-dir root; the next tick observes it and exits cleanly.

## If the session crashes mid-run

State lives entirely on disk. Re-paste `references/BOOTSTRAP_PROMPT.md`
into a fresh session and, instead of `--init`, run a tick directly against
the existing `RUN_DIR` — the script re-reads disk state and the next tick
picks up exactly where the last one left off.
