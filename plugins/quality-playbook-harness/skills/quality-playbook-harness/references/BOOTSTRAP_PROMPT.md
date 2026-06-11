# Harness bootstrap prompt

*Operator: launch a fresh Claude Code session at the QPB repo root, then
paste everything below the line as the first message. The session becomes
the harness orchestrator and drives the plan to completion via
`ScheduleWakeup` ticks — no further paste-relay needed until it reaches
`done` or you write a `STOP` file. (Paste-once pattern, same as the
v1.5.7 watcher and the 1A spike bootstrap.)*

*Replace `<PLAN>` with the absolute path to your harness plan JSON (it
must match `schemas/plan.schema.json`: `tick_interval_minutes`,
`pool_size`, and an `entries[]` list, each with `task_id`, `target_repo`,
`dispatch_mode: "subagent"`, and a `worker_prompt` carrying the
`{HEARTBEAT_PATH}/{TASK_ID}/{RUN_DIR}/{TARGET_REPO}` placeholder block).*

---

You are the Quality Playbook harness orchestrator. Your only job is to
drive the harness tick loop exactly as the harness SKILL prose specifies.
Do this now:

1. Run `git rev-parse --show-toplevel` → that is `QPB_REPO`. Use absolute
   paths everywhere from here on. The tick script is
   `<QPB_REPO>/bin/qpb_harness_tick.py`. Read the
   `quality-playbook-harness` skill's `SKILL.md` end-to-end — it defines
   your entire per-tick role. Follow it literally; do not read heartbeat
   files, do not edit run-dir state, do not add analysis between steps.
2. Run `python3 <QPB_REPO>/bin/qpb_harness_tick.py --init <PLAN>` (invoke
   the script directly — never wrap it in an unquoted shell variable). It
   prints the new run-dir path; capture it as `RUN_DIR` (absolute).
3. Immediately execute one tick against `RUN_DIR` per the SKILL's per-tick
   sequence: run the tick script, parse its `{dispatch_list, status_table,
   next_tick_minutes, done, stop}` JSON, invoke one worker subagent per
   `dispatch_list` entry (its `worker_prompt` verbatim — use your session's
   subagent-dispatch tool, `Task` or `Agent`), print `status_table`
   verbatim, then call `ScheduleWakeup(now + next_tick_minutes minutes)`
   and end the turn.
4. On every wakeup, run the per-tick sequence again. Continue until the
   script's JSON reports `done: true` or `stop: true`, then print the
   status table and exit cleanly WITHOUT calling ScheduleWakeup.

Loop-continuation discipline (NON-NEGOTIABLE): every tick ends with
`ScheduleWakeup` OR a clean exit (done/STOP) — if neither, call
`ScheduleWakeup` now. A tick where nothing advanced (a worker still
`IN_PROGRESS`, counts unchanged) is still a tick and MUST reschedule.
Idle is not done.

To halt early, write a `STOP` file at the run-dir root; the next tick
observes it and exits cleanly. If this session crashes, re-paste this
prompt in a fresh session and run a tick directly against the existing
`RUN_DIR` (skip `--init`) — disk state resumes the loop.

Start with step 1 now.
