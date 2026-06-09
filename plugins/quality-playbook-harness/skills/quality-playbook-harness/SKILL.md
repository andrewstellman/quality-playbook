---
name: quality-playbook-harness
description: Tick-based orchestration harness that runs Quality Playbook plans across multiple repos with mixed dispatch (in-process Task subagent, cross-CLI shell-out, operator-manual). Reads worker heartbeats from disk; survives session restarts via scheduled-tasks MCP.
version: 1.5.9
license: Apache-2.0
author: Andrew Stellman
dependencies:
  - mcp__scheduled-tasks
---

# Quality Playbook Harness

You are the QPB harness orchestrator. Your job is to run a **plan** (a JSON document listing repos to audit) by dispatching one **worker** per entry, each worker running the `quality-playbook` skill against its assigned repo, and tracking progress via on-disk heartbeats until every entry has a terminal result.

You run as a **tick-based state machine**. Each invocation of this skill is exactly ONE tick. A tick reads state from disk, advances any state-machine transitions that are ready, writes state back to disk, and exits. A scheduled task (registered via the `mcp__scheduled-tasks` MCP) re-invokes this skill at the plan's declared cadence so the state machine keeps stepping forward across operator session restarts, sleeps, and reboots.

> **Why tick-based?** Long-running in-context polling loops drift, leak tokens, hit context limits, and die when the host session ends. The state machine on disk + idempotent stepper + external scheduler pattern (well-trodden — kubernetes controllers, systemd timers, cron) dissolves every one of those concerns by construction. Each tick is fresh-context, bounded, and inherently safe to re-run.

Read this SKILL.md end-to-end. Then load the two reference files (see § Reference loads at the bottom). Then execute the tick.

---

## When to invoke this skill

**First invocation (operator-driven).** The operator says "run this plan" with a path to a `plan.json` file (or hands you one inline). You:

1. Validate the plan against `schemas/plan.schema.json`.
2. Create the run directory `harness_runs/<ISO timestamp>/` (UTC, format `YYYY-MM-DDTHH-MM-SSZ`).
3. Populate `queue/` with one `job-NNNNN.json` per plan entry (each job is a `job_manifest` per `schemas/job_manifest.schema.json`).
4. Snapshot the plan to `<run-dir>/plan.json`.
5. Register a scheduled task via `mcp__scheduled-tasks__create_scheduled_task` that re-invokes this skill with the run-dir as argument. Cadence is `plan.tick_interval_minutes` (default 10).
6. Execute the first tick now (don't wait for the scheduled fire).
7. Exit.

**Subsequent invocations (scheduled task fires OR operator manual force).** The scheduled task re-invokes you with the run-dir argument. You execute one tick and exit. The operator can also manually invoke you with the run-dir to force an immediate tick (idempotent — same code path, no harm if state hasn't changed).

If neither a fresh plan nor a run-dir argument is provided, ask the operator which mode they want.

---

## Tick contract — the single most important thing

**Exactly ONE tick per invocation.** Do not loop. Do not poll. Do not wait on workers. Read state, advance the transitions that are ready RIGHT NOW, write state, exit.

**Idempotency is mandatory.** Every transition begins with "is this already done?" Re-running the same tick must produce no observable change after the first. If a job is already in `claimed/`, do not re-dispatch. If a result is already in `results/`, do not re-move. The Phase 1C test `bin/tests/test_harness_tick_idempotency.py` enforces this at the helper-script layer; the broader state-machine idempotency is your responsibility at every transition.

**Five steps per tick (cite as authoritative: `QPB_v1.5.9_Harness_Skill_Design.md` § Tick-based execution model).**

1. **Read state from disk.** Read `harness_status.json`. Read `plan.json`. Build the authoritative current-state view: which jobs are queued, claimed, completed, failed, stalled.
2. **Tail heartbeats.** For each in-flight (`state=claimed`) job, read the last 50 lines of `run-NN/heartbeat.ndjson` to determine current worker state (running / stalled / terminal).
3. **Apply transitions.** Each transition is enumerated in `references/STATE_MACHINE.md`. Apply every transition that's ready:
   - Pending job in `queue/` + free pool slot → dispatch (via the entry's `dispatch_mode`); move job_manifest `queue/` → `claimed/`; write the worker lock file (see § Worker lock file)
   - `claimed/` job with terminal sentinel in heartbeat → move job_manifest `claimed/` → `results/`, write `result-NNNNN.json`, delete the worker lock file
   - `claimed/` job with heartbeat older than `stall_threshold_minutes` (default 45) → mark `state=stalled`
   - `claimed/` job with no STARTUP heartbeat 60 sec post-dispatch → mark `state=failed`, `failure_subtype=AUTH_OR_LAUNCH_FAILED`
   - `claimed/` job (Mode 2 only) with worker PID gone (`kill -0` returns ESRCH) AND no recent heartbeat AND `start_time` older than 60 sec → mark `state=failed`, `failure_subtype=WORKER_FAILED` (A-5 early-detection path)
   - All entries in `results/` → write final summary, disable scheduled task, exit (see § Self-disable)
4. **Write updated `harness_status.json`.** Single atomic write — write to `harness_status.json.tmp`, fsync, rename onto `harness_status.json`.
5. **Exit.** Do not sleep, do not poll, do not wait. The scheduled task fires you again at the next cadence.

If any step fails partway, do NOT attempt recovery in the same tick — let the next tick re-read disk state and resume. The state machine is the recovery mechanism.

---

## First-tick setup (only on first invocation per plan)

1. Generate the run-dir name: `harness_runs/<UTC ISO timestamp with - separators in time>/`. Example: `harness_runs/2026-06-08T14-30-00Z/`.
2. Create the run-dir and its subdirs: `queue/`, `claimed/`, `results/`, `run-01/`, `run-02/`, …, `run-NN/` (one per plan entry).
3. For each plan entry index `i`:
   - Generate a UUID for `task_id`.
   - Write `queue/job-NNNNN.json` (NNNNN = i zero-padded to 5 digits) matching `schemas/job_manifest.schema.json` with `state=queued`, `task_id=<uuid>`, `repo=<from plan>`, `dispatch_mode=<from plan>`, `cli_command=<from plan if cross_cli>`, `schema_version="1"`.
   - Render the worker prompt to `run-NN/worker_prompt.md` from `plan.worker_prompt_template` (substituting `{repo}`, `{task_id}`, `{heartbeat_path}` placeholders with **absolute paths** — never derive from cwd; Council finding A-2).
4. Snapshot the plan to `<run-dir>/plan.json`.
5. Register the scheduled task. The MCP call is `mcp__scheduled-tasks__create_scheduled_task` with `interval_minutes=plan.tick_interval_minutes` and a prompt that re-invokes this skill with the run-dir as argument.
6. Write the initial `harness_status.json`: `{schema_version: "1", run_dir: "...", plan_task_id: "...", scheduled_task_id: "...", pool_size: N, jobs_queued: <count>, jobs_claimed: 0, jobs_completed: 0, jobs_failed: 0, jobs_stalled: 0}`.
7. Now execute the first tick (the § Tick contract above).

---

## Dispatch modes

Three supported modes; each plan entry declares its mode. Modes mix freely within one plan.

### Worker lock file (Council finding A-5 — applies to ALL modes)

At dispatch time, BEFORE invoking the worker, write a `claimed/job-NNNNN.lock` file (sibling of the job manifest) containing the worker's identity for liveness verification:

```json
{
  "schema_version": "1",
  "task_id": "<uuid>",
  "pid": <process id of the worker, when knowable>,
  "start_time": "<ISO8601 dispatch timestamp>",
  "cwd": "<absolute worker working directory>",
  "dispatch_mode": "subagent|cross_cli|operator_manual"
}
```

- **Mode 1 (subagent):** `pid` is the orchestrator's PID (the subagent runs in the same process tree). Used only for "is the orchestrator still alive?" — if the orchestrator dies, the subagent dies with it, so a lock without a matching live orchestrator means abandon.
- **Mode 2 (cross_cli):** `pid` is the backgrounded worker process PID (captured from `$!` after the shell-out). The harness uses `kill -0 <pid>` to test liveness on each tick. If PID is gone AND no heartbeat in `stall_threshold_minutes` AND `start_time` is more than 60 sec ago, mark `state=failed`, `failure_subtype=WORKER_FAILED` even before the 45-min stall window expires. This is Council A-5's earlier-detection mechanism.
- **Mode 3 (operator_manual):** `pid` is omitted (operator's CLI process is opaque to the harness). `cwd` records where the operator was directed to paste; liveness reverts to the heartbeat-tail check.

The lock file is deleted when the job manifest moves claimed/ → results/ (the same tick that writes `result-NNNNN.json`). The two-phase commit pattern is for the manifest move itself; the lock file deletion happens in the same tick AFTER the manifest is safely in `results/`.

### Mode 1 — in-process Task subagent (Claude Code only)

When `dispatch_mode=subagent`, dispatch by invoking the `Task` tool with the rendered worker prompt. The prompt's literal first paragraph MUST be the absolute-path environment block (Council finding A-2 — never derive from cwd):

```
HEARTBEAT_PATH=<absolute path to run-NN/heartbeat.ndjson>
TASK_ID=<uuid>
RUN_DIR=<absolute path to run-NN/>
TARGET_REPO=<absolute path>
```

After this block, the prompt instructs the subagent to load the `quality-playbook` skill, run the playbook against `TARGET_REPO`, and emit heartbeats via `python3 -m bin.qpb_heartbeat` (with `QPB_TASK_ID` and `QPB_HEARTBEAT_PATH` env vars set to the values from the block).

**Subagent return contract.** Per Council finding A-3 (context bloat), instruct the subagent: "On completion return ONLY a short summary — phase reached, last status, mtime age of heartbeat. Do NOT echo heartbeat content. Do NOT echo file contents." This caps orchestrator context across many ticks.

**Pool cap.** Default `pool_size=3` for in-process subagents. The plan may override but document if going higher: subscription concurrency caps may bite at pool > 3.

### Mode 2 — cross-CLI shell-out

When `dispatch_mode=cross_cli`, dispatch by running the worker as a backgrounded subprocess of a different CLI. Template:

```
cd <absolute run-NN/> && <cli_command> -p "$(cat worker_prompt.md)" > worker.log 2>&1 &
```

…where `<cli_command>` is from the plan entry (e.g. `copilot --model claude-sonnet-4.6 --allow-all`, `codex --model gpt-5.5`, `claude --model opus-4.7 --dangerously-skip-permissions`).

**Pre-flight auth check (Council finding B-1).** BEFORE the dispatch shell-out, run TWO probes:

1. `<cli_command> --version` — must exit 0 (binary installed).
2. `<cli_command> -p "echo ok"` — must round-trip a response within 30 sec (auth healthy).

If either probe fails, mark the job `state=failed`, `failure_subtype=AUTH_OR_LAUNCH_FAILED`, write the diagnostic to `run-NN/auth_check.log`, do NOT dispatch.

**STARTUP heartbeat window.** After dispatch, the worker has 60 sec to emit its first heartbeat (the Phase 1 STARTING line). If the next tick (or the dispatch tick if more than 60 sec has passed) sees `heartbeat.ndjson` is empty or missing, mark `state=failed`, `failure_subtype=AUTH_OR_LAUNCH_FAILED`. This is distinct from STALLED — it captures "the worker never started" vs "the worker started then stopped emitting."

The worker prompt's absolute-path block is rendered identically to Mode 1. The worker sources `QPB_TASK_ID` and `QPB_HEARTBEAT_PATH` from the env-var section the worker_prompt.md template provides (the cross-CLI worker is its own process tree, so the prompt sets env vars inline via the worker's bash invocation).

### Mode 3 — operator-manual dispatch

When `dispatch_mode=operator_manual`, dispatch by writing the worker prompt to `run-NN/operator_prompt.md` and writing an ACTION REQUIRED banner to `harness_status.json` under the `action_required` key:

```json
"action_required": [
  {
    "tag": "MANUAL_DISPATCH_001",
    "message": "Open a new <cli> window, cd to <run-NN/>, paste operator_prompt.md, run it.",
    "ack_file": "run-NN/operator_started"
  }
]
```

The operator acknowledges by creating `run-NN/operator_started` (any contents). Subsequent ticks detect the ack file and proceed normally (the worker is now responsible for emitting heartbeats; the harness only tracks via heartbeat tail).

On Mac, the harness may additionally fire an `osascript` notification at dispatch time so the banner isn't silently missed:

```
osascript -e 'display notification "QPB harness: ACTION REQUIRED for MANUAL_DISPATCH_001" with title "QPB Harness"'
```

Mode 3 is intended for "watch this one interactively." Document as discouraged for `pool_size > 2` (operator can't track more than two manual windows reliably).

---

## Heartbeat reading

For each in-flight run, read the last N (default 50) lines of `run-NN/heartbeat.ndjson` using the `Read` tool with `offset` set to "near EOF." Pseudo-pattern:

1. Stat the file. If absent → worker hasn't started yet (apply the STARTUP heartbeat window rule).
2. Read with offset such that you capture the last ~50 lines (Read tool with line-based offset; if you don't know the line count, Read a large slab and tail).
3. Parse each line as JSON. Skip lines that fail to parse (corrupt or partial write — log a WARN).
4. The most recent line's `ts` is the worker's `last_heartbeat_at`. Compare against `stall_threshold_minutes` (default 45).
5. If the most recent line has `result_file` and `summary` fields, it's the terminal sentinel — apply the terminal transition.
6. If any line has `schema_version != "1"`, emit a WARN to `harness_status.json` under `schema_warnings[]` (Council finding C-3 silent-drift).

The `qpb_heartbeat.py` helper script emits append-only via `O_APPEND` so the tail will never see a torn write under the kernel's POSIX guarantees for small (<PIPE_BUF) writes — one JSON line per call.

---

## Stall detection

**Global threshold:** `stall_threshold_minutes` (default 45). If a claimed job's `last_heartbeat_at` is older than this, mark `state=stalled` and surface in `harness_status.json` under `stalls[]`. The operator decides whether to abandon (`state=failed`, `failure_subtype=STALLED`) or wait longer.

**Mandatory 3-min keepalive.** The QPB worker SKILL.md "Heartbeat emission contract" section commits the worker to emit a heartbeat every ~3 min mid-phase. Absence of any heartbeat for 3+ min is the inner alarm — it means something is wrong before the global 45-min threshold even fires. Surface stall warnings at `last_heartbeat_at > early_warn_minutes` (default 10 per `plan.schema.json` field; midpoint between the 3-min keepalive and 45-min cutoff) so the operator has time to investigate before fast-fail.

The 45-min default + 3-min keepalive pair is from Council finding B-4. Per-phase override is deferred to v1.5.10.

---

## Self-disable

When all plan entries are in `results/` (any combination of `state=completed`, `state=failed`, `state=stalled`):

1. Write a final `harness_status.json` with `state=done` and a `summary` block listing per-entry outcome.
2. Write a human-readable `<run-dir>/SUMMARY.md` (one section per entry: repo, status, result_file pointer, duration_sec, total_heartbeats — fields directly from each `results/result-NNNNN.json`).
3. Call `mcp__scheduled-tasks__delete_scheduled_task` with the scheduled-task ID from `harness_status.json`.
4. Print a final status line to the operator and exit.

Self-disable is idempotent: re-running a tick after self-disable sees `state=done` and exits immediately without re-deleting the (already-deleted) scheduled task.

---

## Schema-version handling

Every artifact this skill writes — `plan.json`, `job_manifest`, `result.json`, `harness_status.json` — includes `schema_version: "1"`. Every heartbeat the worker emits also includes `schema_version: "1"` (enforced by `qpb_heartbeat.py`).

On read:

- If a heartbeat line's `schema_version != "1"`, emit a WARN to `schema_warnings[]` in `harness_status.json` and continue (forward-compatible degradation).
- If a plan or job_manifest's `schema_version != "1"`, abort the tick with a clear operator message — there's no forward-compatible behavior for a schema mismatch at the orchestration layer.

The cross-skill byte-identity contract (the heartbeat schema in `quality-playbook-harness/schemas/` is byte-identical to the one in `quality-playbook/schemas/`) is load-bearing — single source of truth.

**Design-vs-implementation note.** `QPB_v1.5.9_Harness_Skill_Design.md` § Architecture diagram lists only `plan.schema.json`, `job_manifest.schema.json`, `result.schema.json` under the harness `schemas/` (the design framed heartbeat schema as living "in `quality-playbook/schemas/`" with the harness "referencing it from here"). The implementation diverges by additionally duplicating `heartbeat.schema.json` into the harness `schemas/` directory as a byte-identical copy. Rationale: self-contained plugin shipping (each plugin's `schemas/` is complete on its own when installed via the marketplace), and Council finding C-3 cross-skill drift is enforced mechanically by the Phase 1C byte-identity test rather than relying on a single-source convention. The deviation is documented; the contract that matters operationally is byte-identity, which the test guarantees.

The Phase 1C test `bin/tests/test_harness_schemas.py` enforces byte-identity. The `quality_gate.py --schemas-only` invariant adds a second enforcement layer.

---

## Reference loads

Before executing the tick, load these reference files via the `Read` tool:

- `Read references/STATE_MACHINE.md` — full enumeration of every state transition the tick can apply, plus a worked example.
- `Read references/DISPATCH_GUIDE.md` — per-mode dispatch detail with concrete examples.

The example plan at `references/examples/small_plan.json` is also available for reference if you want to see the schema shape concretely. It's a 2-entry plan suitable for validating the harness against `plan.schema.json`.

---

## What this skill does NOT do

- It does NOT run the Quality Playbook itself — that's the `quality-playbook` skill (the worker). The harness only orchestrates.
- It does NOT do cross-machine dispatch — folder-based comm on the local filesystem. A2A migration is a future v1.6.x transport swap (schemas are A2A-ready: `task_id` UUID + `schema_version` string).
- It does NOT implement its own TUI — the host CLI's conversation IS the TUI; operators can also tail `harness_status.json` or `heartbeat.ndjson` in a separate window.
- It does NOT replace the operator's judgment on dispatch mode mixing, pool sizing, or stall handling. It provides defaults and surfaces signals; the operator decides.

---

*v1.5.9 source. Council-reviewed sub-design at `~/Documents/QPB/docs/design/QPB_v1.5.9_Harness_Skill_Design.md`. State transitions in `references/STATE_MACHINE.md`. Dispatch detail in `references/DISPATCH_GUIDE.md`. Heartbeat schema in `schemas/heartbeat.schema.json` (byte-identical to the worker-side copy).*
