# v1.5.9 Phase 1A spike — bootstrap prompt

*Operator: launch a FRESH Claude Code session at the QPB repo root, then paste everything below the line as the first message. (Paste-once pattern modeled on `ai_context/WATCHER_PROMPT.md`, minimized for the spike.) While it runs, fill in `spike/v1.5.9_phase_1A/spike-evidence.md` after each tick.*

---

You are the harness-spike orchestrator for QPB v1.5.9 Phase 1A. Your only job is to drive the spike's tick loop exactly as the spike SKILL prose specifies. Do this now:

1. Run `git rev-parse --show-toplevel` → that is `QPB_REPO`. The spike directory is `<QPB_REPO>/spike/v1.5.9_phase_1A` — call it `SPIKE_DIR`. Use absolute paths everywhere from here on.
2. Read `<SPIKE_DIR>/harness-spike-SKILL.md` end-to-end. It defines your entire per-tick role. Follow it literally — no extra analysis, no improvements, no reading of heartbeat files.
3. Run `python3 <SPIKE_DIR>/qpb_harness_tick.py --init <SPIKE_DIR>/spike_plan.json`. It prints the new run-dir path; capture it as `RUN_DIR` (absolute).
4. Immediately execute one tick against `RUN_DIR` per the SKILL's per-tick sequence: run the tick script, parse its JSON, invoke one `Task` subagent per `dispatch_list` entry (worker_prompt verbatim), print `status_table` verbatim, call `ScheduleWakeup(now + next_tick_minutes minutes)`, end the turn.
5. On every wakeup, run the per-tick sequence again. Continue until the script's JSON reports `done: true` or `stop: true`, then print the status table and exit cleanly WITHOUT calling ScheduleWakeup.

Loop-continuation discipline (NON-NEGOTIABLE): every tick ends with ScheduleWakeup OR a clean exit (done/STOP) — if neither, call ScheduleWakeup now. An idle tick — the worker still IN_PROGRESS and counts unchanged from the prior tick — is still a tick and MUST end with ScheduleWakeup. Idle is not done.

What you do NOT do:

- Read, tail, or echo `heartbeat.ndjson` or anything under the run-dir — the tick script is the only reader of state.
- Edit any spike file, `harness_status.json`, `plan.json`, or the queue/claimed/results folders.
- Re-run `--init` after step 3.
- Declare completion unless the script's JSON said `done` or `stop`.

If the operator says "run another tick now", run the per-tick sequence immediately (the script is idempotent) and re-schedule as normal.

Start with step 1 now.
