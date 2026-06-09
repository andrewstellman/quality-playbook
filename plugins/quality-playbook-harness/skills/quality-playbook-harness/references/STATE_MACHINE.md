# Harness state machine — every transition enumerated

This document enumerates **every** transition the tick can apply. The harness SKILL.md cites this as authoritative. If a behavior isn't listed here, the harness shouldn't be doing it.

## Per-job state values

A job_manifest's `state` field is one of: `queued`, `claimed`, `completed`, `failed`, `stalled`.

- `queued` — job is in `queue/`, not yet dispatched.
- `claimed` — job is in `claimed/`, worker is dispatched or in flight.
- `completed` — job is in `results/`, terminal heartbeat had `status=COMPLETED`.
- `failed` — job is in `results/`, terminal heartbeat had `status=FAILED`, OR the harness detected AUTH_OR_LAUNCH_FAILED, OR the operator marked a stalled job as abandoned.
- `stalled` — job is in `claimed/` with `last_heartbeat_at > stall_threshold_minutes` old. Operator decides whether to wait or abandon.

## Transition table

| # | Pre-state | Trigger condition | Action | Post-state | Idempotency invariant |
|---|-----------|-------------------|--------|------------|------------------------|
| 1 | `queued` job + free pool slot | always (unless paused; pool slot = `pool_size - count(claimed)` > 0) | dispatch via configured `dispatch_mode`; move job_manifest queue/ → claimed/; set `dispatched_at` | `claimed` | Job already in `claimed/` → no-op (the queue lookup wouldn't return it). |
| 2 | `claimed` job with terminal sentinel in heartbeat | last heartbeat line has `result_file` AND `summary` AND `status ∈ {COMPLETED, FAILED, ABANDONED}` | write `results/result-NNNNN.json` from terminal heartbeat + job_manifest + run-dir stats; move job_manifest claimed/ → results/; set `state` to match terminal `status` mapped to manifest enum (`COMPLETED→completed`, `FAILED→failed`, `ABANDONED→failed` with `failure_subtype=WORKER_FAILED`) | `completed` or `failed` | Result file already exists in `results/` → no-op. |
| 3 | `claimed` job with stale heartbeat | `now - last_heartbeat_at > stall_threshold_minutes` (default 45) | set `state=stalled`; surface in `harness_status.json` under `stalls[]` | `stalled` | `state` already `stalled` → no-op. |
| 4 | `claimed` job with no STARTUP heartbeat 60 sec post-dispatch | `heartbeat.ndjson` empty OR missing AND `now - dispatched_at > 60 sec` | set `state=failed`, `failure_subtype=AUTH_OR_LAUNCH_FAILED`; write `result-NNNNN.json` with placeholder fields; move manifest claimed/ → results/; delete lock file | `failed` | Result file already exists in `results/` → no-op. |
| 5 | `stalled` job with operator abandon decision | operator wrote a file `run-NN/abandon` (any contents) | set `state=failed`, `failure_subtype=STALLED`; write `result-NNNNN.json`; move manifest claimed/ → results/; delete lock file | `failed` | Result file already exists in `results/` → no-op. |
| 6 | `claimed` job (Mode 2 only) with worker PID gone | `kill -0 <pid_from_lock>` returns ESRCH AND no heartbeat in `stall_threshold_minutes` AND `now - start_time > 60 sec` | set `state=failed`, `failure_subtype=WORKER_FAILED`; write `result-NNNNN.json`; move manifest claimed/ → results/; delete lock file | `failed` | Result file already exists in `results/` → no-op. Council A-5 early-detection mechanism — fires before the 45-min stall window for cross-CLI workers that crash. |
| 7 | All entries in `results/` (any terminal state combination) | terminal | write `harness_status.json` with `state=done`; write `<run-dir>/SUMMARY.md`; call `mcp__scheduled-tasks__delete_scheduled_task` | `done` | `state` already `done` → no-op (do NOT re-delete the scheduled task). |

**No other transitions exist.** If the tick encounters a state the table doesn't cover (e.g. a manifest in `claimed/` whose `task_id` doesn't match any heartbeat line's `task_id`), surface a WARN in `harness_status.json` under `warnings[]` and leave the job untouched — do not attempt recovery in the same tick.

## Atomicity rules

Each transition that moves a file (manifest from `queue/` to `claimed/`, or `claimed/` to `results/`) MUST use the two-phase commit pattern:

1. Write the updated manifest to a `.tmp` sibling.
2. fsync the `.tmp` file.
3. Rename `.tmp` onto the target path.
4. Rename (or move) the old location's file LAST.

This guarantees that crash-at-any-point either keeps the job in its old state OR advances it cleanly — never duplicates and never loses.

`harness_status.json` writes follow the same pattern: write `.tmp`, fsync, rename.

## Worker lock file (Council finding A-5)

In addition to the manifest move, every dispatch transition (transition #1) writes a `claimed/job-NNNNN.lock` file sibling to the manifest containing:

- `schema_version: "1"`
- `task_id: "<uuid>"`
- `pid: <worker process id>` — orchestrator PID for Mode 1; backgrounded process PID for Mode 2; omitted for Mode 3.
- `start_time: "<ISO8601 dispatch timestamp>"`
- `cwd: "<absolute path>"`
- `dispatch_mode: "<subagent|cross_cli|operator_manual>"`

The lock file's purpose is to allow early failure detection BEFORE the 45-min stall window expires — Council finding A-5's resume / liveness mechanism. The harness checks each tick: if `kill -0 <pid>` (Mode 2) returns ESRCH (no such process) AND no heartbeat has landed in the last `stall_threshold_minutes` AND `start_time` is older than 60 sec, mark `state=failed`, `failure_subtype=WORKER_FAILED` (distinct from STALLED — STALLED means heartbeats stopped; WORKER_FAILED means the process disappeared without a terminal sentinel). Mode 1 (subagent) and Mode 3 (operator_manual) cannot use the PID check (Mode 1 PID is the orchestrator's; Mode 3 PID is opaque); for those modes the lock file is informational only.

Lock file deletion: the same tick that moves the manifest claimed/ → results/ also deletes the lock file AFTER the manifest is safely renamed into `results/`. If the harness crashes between the manifest move and the lock deletion, the next tick sees an orphan lock with no matching `claimed/job-NNNNN.json` — sweep orphan locks by deleting any `claimed/*.lock` without a matching `claimed/*.json`.

Two-phase commit covers the manifest move; the lock file is its own independent artifact — its presence does NOT block transitions (the manifest's location is the state truth, not the lock).

## Worked example — 5-repo plan with mixed dispatch

Plan: 5 entries, 2 subagent + 2 cross_cli (copilot) + 1 cross_cli (codex). `tick_interval_minutes=10`, `pool_size=3`. Operator runs `harness-skill` against the plan at `14:00 UTC`.

### Tick 1 (14:00, first invocation)

- Read plan; validate OK.
- Create `harness_runs/2026-06-08T14-00-00Z/`. Populate `queue/job-00001.json` … `queue/job-00005.json`.
- Register scheduled task at 10-min cadence.
- Pool free slots: 3. Queue: 5. Dispatch first 3 (in plan order):
  - job-00001 (subagent) → Task tool invocation, manifest queue/ → claimed/, `dispatched_at=14:00:05`.
  - job-00002 (subagent) → same.
  - job-00003 (cross_cli copilot) → pre-flight auth check (copilot --version + roundtrip) PASS; shell-out backgrounded; manifest queue/ → claimed/, `dispatched_at=14:00:18`.
- Update `harness_status.json`: `jobs_claimed=3, jobs_queued=2, jobs_completed=0`.
- Exit.

### Tick 2 (14:10, scheduled fire — fresh context)

- Read `harness_status.json`. Read each claimed run's `heartbeat.ndjson` tail:
  - job-00001 (subagent): last line `phase=2, step=generation, status=IN_PROGRESS, ts=14:09:42`. Age 18 sec → healthy.
  - job-00002 (subagent): last line `phase=6, step=verify, status=COMPLETED, result_file=quality/SUMMARY.md, summary=…`. **Terminal sentinel.** Apply transition #2: write `results/result-00002.json` (`status=COMPLETED`), move manifest claimed/ → results/.
  - job-00003 (copilot): last line `phase=1, step=explore, status=IN_PROGRESS, ts=14:09:55`. Healthy.
- Free pool slot. Queue has job-00004 and job-00005. Apply transition #1 to job-00004 (cross_cli copilot): auth check PASS, shell-out, manifest queue/ → claimed/.
- Update `harness_status.json`: `jobs_claimed=3, jobs_queued=1, jobs_completed=1`.
- Exit.

### Tick 3 (14:20, scheduled fire)

- Read state. Tail heartbeats:
  - job-00001 (subagent): last heartbeat `ts=14:19:48`. Healthy.
  - job-00003 (copilot): last heartbeat `ts=14:17:10`. Age 2 min 50 sec → healthy (under 3-min keepalive threshold — borderline, log INFO).
  - job-00004 (copilot): last heartbeat `ts=14:19:30`. Healthy.
- Free pool slot? Pool size 3, claimed count 3 → no. Queue has job-00005 (cross_cli codex) waiting.
- No transitions apply.
- Exit.

### Tick 4 (14:30)

- Tail heartbeats:
  - job-00001: terminal sentinel. Apply #2.
  - job-00003: last heartbeat `ts=14:27:00`. Age 3 min → still healthy but close.
  - job-00004: terminal sentinel. Apply #2.
- Free pool slots: 2. Queue has job-00005. Dispatch (transition #1) job-00005 (cross_cli codex): auth check passes, shell-out, manifest queue/ → claimed/.
- Update state. `jobs_claimed=2, jobs_queued=0, jobs_completed=3`.
- Exit.

### Tick 5 (14:40)

- job-00003 (copilot): last heartbeat `ts=14:39:10`. Healthy.
- job-00005 (codex): last heartbeat `ts=14:39:50`. Healthy.
- No queue. No transitions ready.
- Exit.

### Ticks 6-N: same shape until all 5 are in `results/`.

### Final tick

- All 5 in `results/`. Apply transition #6: write `SUMMARY.md`, mark `state=done`, delete scheduled task.
- Print final operator status. Exit.

## Operator-driven force-tick

The operator can force an immediate tick at any time by invoking the skill manually with the run-dir argument. Same code path as a scheduled fire. Idempotency means this never harms state — if no transitions are ready, the tick is a no-op.

Useful when:
- Operator just acked a Mode 3 dispatch (don't wait 10 min for the next scheduled fire).
- Operator just fixed an auth issue and wants the harness to retry.
- Operator wants to see fresh state without tailing files manually.

## Schema-version drift

If a heartbeat line has `schema_version != "1"`, append to `harness_status.json` under `schema_warnings[]` and continue (forward-compatible degradation). The harness reads the line as-is using best-effort field access.

If `plan.json` or any `job_manifest` has `schema_version != "1"`, abort the tick with a clear message. There's no forward-compatible behavior for an orchestration-layer schema mismatch.

The cross-skill byte-identity contract — the harness-side `schemas/heartbeat.schema.json` byte-matches the worker-side copy at `plugins/quality-playbook/skills/quality-playbook/schemas/heartbeat.schema.json` — is load-bearing. The Phase 1C test `bin/tests/test_harness_schemas.py` enforces this. Per Council finding C-3 (silent drift risk), do NOT modify either copy without modifying the other in the same commit.

---

*See `DISPATCH_GUIDE.md` for per-mode dispatch detail. Schemas: `schemas/plan.schema.json`, `schemas/job_manifest.schema.json`, `schemas/heartbeat.schema.json`, `schemas/result.schema.json`.*
