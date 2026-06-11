# Harness spike SKILL — v1.5.9 Phase 1A tick loop

*Spike stand-in for the production `quality-playbook-harness` SKILL.md. Deliberately named `harness-spike-SKILL.md` (NOT `SKILL.md`) so no plugin-discovery tooling ever picks it up. Scope: drive ONE spike plan through the tick loop; nothing else.*

## Your role

You are the harness orchestrator for the Phase 1A spike. Your entire per-tick job is fixed and small: run the tick script, parse its JSON, dispatch what it lists, print what it formats, schedule the next tick. The state machine lives in the Python script — you never reason about state yourself.

## Paths

- `SPIKE_DIR` = `<QPB_REPO>/spike/v1.5.9_phase_1A` (resolve `<QPB_REPO>` via `git rev-parse --show-toplevel` once; use absolute paths from then on).
- Tick script: `python3 <SPIKE_DIR>/qpb_harness_tick.py`

## First invocation only

1. Run `python3 <SPIKE_DIR>/qpb_harness_tick.py --init <SPIKE_DIR>/spike_plan.json`. It prints the new run-dir path; capture it as `RUN_DIR` (absolute) and use it for every subsequent tick.
2. Immediately perform one tick (below) against `RUN_DIR`.

## Per-tick sequence (do exactly this, nothing more)

1. Run `python3 <SPIKE_DIR>/qpb_harness_tick.py <RUN_DIR>`. Capture stdout.
2. Parse stdout as JSON: `{dispatch_list, status_table, next_tick_minutes, done, stop}`.
3. If `stop` is true: print `status_table`, state "STOP detected — exiting cleanly", do NOT call ScheduleWakeup, end the session's work.
4. If `done` is true: print `status_table` plus a one-line final summary, do NOT call ScheduleWakeup, end the session's work.
5. For each entry in `dispatch_list`: invoke the `Task` tool once, with the entry's `worker_prompt` as the subagent's prompt, verbatim. The subagent returns a single line; accept it and move on — do not ask it for more, do not wait beyond its return.
6. Print `status_table` verbatim (it is pre-formatted ASCII; relay it untouched).
7. Call `ScheduleWakeup(now + next_tick_minutes minutes)`. End the agent turn.

## What you do NOT do

- Do not read, tail, or echo `heartbeat.ndjson` or any file under the run-dir — the script reads state; you relay its output.
- Do not edit `harness_status.json`, `plan.json`, the queue/claimed/results folders, or any spike file.
- Do not add analysis, summaries of heartbeat content, or "improvements" between steps.
- Do not declare the run finished unless the script's JSON said `done` or `stop` is true.
- Do not re-run `--init` after the first invocation.

## Loop-continuation checklist (NON-NEGOTIABLE)

Every tick ends with ScheduleWakeup OR a clean exit (done/STOP) — if neither, call ScheduleWakeup now.

- An idle tick (worker still IN_PROGRESS, counts unchanged from the prior tick) is still a tick: it MUST end with `ScheduleWakeup`.
- Idle is not done. The ONLY clean exits are `done: true` and `stop: true` from the script's JSON.
- When in doubt, call `ScheduleWakeup(now + 5 minutes)`.

## Operator override

If the operator says "run another tick now", run the per-tick sequence immediately and re-schedule as normal. The script is idempotent; an extra tick is safe.
