# Phase 1A spike evidence

## Run setup

- Date/time spike started: 2026-06-11 12:44:04 UTC (08:44 local)
- Host CLI version: Claude Code 2.1.173, model claude-sonnet-4-6 (Sonnet chosen deliberately — stronger prose-following test than Opus)
- Launch: `cd ~/Documents/QPB/testing/bootstrap && claude --dangerously-skip-permissions --model sonnet` (gitignored folder inside the repo; `git rev-parse --show-toplevel` resolved correctly to the QPB root)
- Plan file path: `spike/v1.5.9_phase_1A/spike_plan.json` (1 entry, detached stub, `tick_interval_minutes: 5`)
- Run-dir created by `--init`: `spike/v1.5.9_phase_1A/harness_runs/2026-06-11T12-44-17Z`

## Tick 1 (12:44 UTC, cycle 1)

- Operator prompt that triggered tick 1: the BOOTSTRAP_PROMPT.md below-the-line content, pasted as the first message. No other operator input for the rest of the run.
- Agent's behavior: ran `git rev-parse` → read SKILL → `--init` → tick script → parsed JSON → one note worth recording: the agent paused to check tool schemas and observed "`TaskCreate` is the task-tracker, not a subagent launcher. The SKILL's 'Task tool' maps to `Agent`." It then dispatched correctly via the Agent tool. Subagent returned the single contracted line ("Stub worker launched for task b7dc2966…; heartbeats appending in background (~11 min to terminal COMPLETED).") in 11s / 2 tool uses — no heartbeat content echoed (A-3 honored).
- Status table printed verbatim:
  ```
  Run-Dir: 2026-06-11T12-44-17Z (cycle 1)
  RUN  REPO                      MODE    STATE      PHASE  LAST-HB      HB-AGE
  01   /tmp/qpb-spike-target     subgnt  claimed    -      -            -
  Queue: 0  Claimed: 1  Completed: 0
  ```
- ScheduleWakeup: called; harness confirmed "Next wakeup scheduled for 08:50:00 (in 281s)". Agent ended turn.
- `harness_status.json` after tick 1: cycle 1, `{queued:0, claimed:1, completed:0}`
- `heartbeat.ndjson` after tick 1: `STARTING` line at 12:44:58Z (stub launched and emitting)
- Time of next-tick fire (observed): 12:50 UTC — `✻ Claude resuming /loop wakeup (Jun 11 8:50am)`

## Tick 2 (12:50 UTC, cycle 2) — IDLE TICK

- Agent's stdout: ran tick script, observed "`dispatch_list` is empty, `done` and `stop` are false — idle tick.", printed status table verbatim:
  ```
  Run-Dir: 2026-06-11T12-44-17Z (cycle 2)
  01   /tmp/qpb-spike-target     subgnt  claimed    stub   IN_PROGRESS  0m04s
  Queue: 0  Claimed: 1  Completed: 0
  ```
- `harness_status.json` after tick 2: cycle 2, counts unchanged `{0,1,0}` — **idle**
- `heartbeat.ndjson`: IN_PROGRESS lines accruing (work-1 at 12:47:28Z, work-2 at 12:49:58Z)
- ScheduleWakeup: called; "Next wakeup scheduled for 08:54:00 (in 229s)". Time of next fire (observed): 12:54 UTC.

## Tick 3 (12:54 UTC, cycle 3) — IDLE TICK

- Agent's stdout: status table verbatim, cycle 3, `IN_PROGRESS` HB-AGE 1m34s, counts unchanged `{0,1,0}` — **second idle tick**, rescheduled anyway.
- `heartbeat.ndjson`: work-3 at 12:52:28Z, work-4 at 12:54:58Z
- ScheduleWakeup: called. Time of next fire (observed): 12:58 UTC.

## Tick 4 (12:58 UTC, cycle 4) — REAP → DONE → CLEAN EXIT

- Agent's stdout: status table (cycle 4, run-01 `completed`, `COMPLETED` HB-AGE 2m05s, counts `{0,0,1}`), then: "done: true — run-01 reached COMPLETED. Phase 1A spike finished: 1 run dispatched, 1 completed, 0 remaining. Exiting cleanly."
- **Did NOT call ScheduleWakeup** — session ended at the idle prompt. Clean self-termination confirmed.
- Final disk state (orchestrator-verified independently): `harness_status.json` = `{cycle:4, counts:{queued:0,claimed:0,completed:1}, done:true, run-01 state:"completed"}`; `results/result-00001.json` present with full entry; `run-01/result.txt` = "stub completed at 2026-06-11T12:55:58Z".
- Full heartbeat sequence (verified valid JSON, ordered): STARTING 12:44:58Z → IN_PROGRESS ×4 (12:47:28, 12:49:58, 12:52:28, 12:54:58) → COMPLETED 12:55:58Z with `result_file` + `summary`. The detached stub ran its full ~11-min lifecycle across the subagent turn ending — consistent with the instruction-003 dry-run's pgrep-verified survival finding.

## Idle-tick check

Ticks 2 and 3 were both genuine idle ticks (worker `IN_PROGRESS`, counts unchanged from prior tick, cycle-only bump) and **both ended with a ScheduleWakeup call that subsequently fired on schedule**. This is the load-bearing observation: the watcher death mode (idle tick fails to reschedule) did not occur, twice.

## Idempotency check

Not exercised agent-driven in this run (no forced re-tick was issued). Covered by the instruction-003 dry-run with a real stub: forced re-tick at claimed state produced a cycle-only diff (no double-dispatch, no state/count change). Orchestrator also independently verified the same in the instruction-002 smoke run.

## STOP semantics check

Exercised agent-driven across two additional passes in the same session (operator decision 2026-06-11: run the STOP mini-run before declaring full PASS):

- **Pass 2 (run-dir `2026-06-11T14-26-16Z`) — inconclusive on STOP, second clean autonomy pass otherwise.** The run completed its full lifecycle autonomously (4 ticks, 2 idle, reap → `done:true` → clean exit at 14:39 UTC) before the operator's STOP file was written (mtime 14:52 UTC — 13 min after the loop exited). The script never had a STOP to observe; no defect. Incidentally a second full confirmation of the headline autonomy result.
- **Pass 3 (run-dir `2026-06-11T15-05-39Z`) — STOP PASS.** STOP written at 15:06 UTC, ~1 min after tick 1 and ~5 min before the next wakeup. The 15:11 tick reported `stop: true`; the agent printed the status table, stated "STOP detected — exiting cleanly," and ended **without** calling ScheduleWakeup; no further wakeups fired. Disk verification: `harness_status.json` completely untouched by the stop tick (cycle 1, claimed 1, `done: false` — the read-only contract held, cycle not even bumped). The orphaned detached stub ran out its lifecycle to COMPLETED at 15:17 — expected; the spike has no kill semantics (1B scope).

## Verdict

**PASS.** The single architectural assumption holds: given only the harness SKILL prose and the pasted bootstrap, a fresh Claude Code session (Sonnet) autonomously drove the disk state machine across 4 `ScheduleWakeup` ticks — including 2 genuine idle ticks — carrying the stub job queued → claimed → completed, then self-terminated cleanly on `done=true`, with zero operator re-prompts (pass 1; independently reproduced in pass 2). The agent honors STOP from the prose: stop tick observed, loop halted without rescheduling, state untouched (pass 3). No drift in any pass: the agent never read the heartbeat, never hand-edited state, dispatched only what the script listed. Forced re-tick idempotency was not exercised agent-driven; the script-level behavior was verified twice (instruction-002 smoke run, instruction-003 dry-run with a real stub) and is accepted as covered.

The strict three-state threshold (one dropped reschedule on a non-terminal tick = FAIL) required no tolerance — zero reschedules were dropped across three passes / 9 non-terminal ticks. Post-spike re-evaluation (authorized in the plan): the threshold stands as written for the 1B acceptance contract.

Non-blocking observations for 1B (log alongside the existing carry-forwards):

1. **Dispatch-tool naming.** The SKILL prose says "Task tool"; in the live session the tool is named `Agent`. Sonnet resolved the mapping itself (cost: one extra reasoning step at tick 1, no behavioral deviation). Production harness SKILL.md should name the dispatch tool robustly (e.g., "your session's subagent-dispatch tool — `Task` or `Agent` depending on host version").
2. **Cosmetic:** the tick script prints "Next tick in 5 min" in the status table even on the `done` and `stop` ticks. Suppress or replace on terminal ticks.
3. **No kill semantics for in-flight workers on STOP** — the detached stub keeps running after the loop halts. Already implicit in 1B's full state machine; noting the observed behavior here.
