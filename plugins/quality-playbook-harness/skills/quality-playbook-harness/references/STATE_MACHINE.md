# QPB harness state machine

The authoritative description of the per-run state machine that
`bin/qpb_harness_tick.py` advances each tick. The orchestrator agent
never reasons about state itself — it runs the tick script, dispatches
what the script lists, prints the script's table, and reschedules. This
doc is for humans (and reviewers) who need to understand what the script
does on disk.

## Run directory layout

`--init <plan>` creates `harness_runs/<UTC-stamp>/`:

```
harness_runs/<stamp>/
├── plan.json              snapshot of the plan
├── harness_status.json    state-machine truth (the script writes; anyone reads)
├── harness_tick.log       append-only per-tick transition log
├── queue/   job-NNNNN.json     not yet claimed
├── claimed/ job-NNNNN.json     in flight (+ job-NNNNN.lock — dispatch metadata)
├── results/ result-NNNNN.json  terminal records
└── run-NN/  manifest.json, heartbeat.ndjson, quality/   (one per plan entry)
```

## States

| State | Meaning | Pool slot? | Terminal? |
|-------|---------|-----------|-----------|
| `queued` | created, not yet dispatched | no | no |
| `claimed` | dispatched (Task launched), no heartbeat yet | yes | no |
| `running` | a STARTING/IN_PROGRESS heartbeat has been seen | yes | no |
| `stalled` | heartbeat mtime older than `stall_threshold_minutes` | yes | no |
| `completed` | terminal heartbeat `COMPLETED` reaped | no | **yes** |
| `failed` | terminal heartbeat `FAILED`/`ABANDONED` reaped | no | **yes** |
| `auth_or_launch_failed` | claimed but no heartbeat within `launch_grace_minutes` | no | **yes** |

`done` is true exactly when every run is terminal.

## Transitions (applied each non-STOP tick, all idempotent)

```
queued ──[free pool slot]──▶ claimed ──[heartbeat STARTING/IN_PROGRESS]──▶ running
   ▲                            │                                            │
   │                            │ [no heartbeat, claimed_age > launch_grace] │ [terminal sentinel
   │                            ▼                                            │  COMPLETED/FAILED/ABANDONED]
   │                   auth_or_launch_failed                                 ▼
   │                                                              completed | failed
   │
running/claimed ──[heartbeat mtime > stall_threshold]──▶ stalled ──[fresh heartbeat]──▶ running
```

- **Dispatch (queued → claimed):** while the count of in-flight runs
  (claimed + running + stalled) is below `pool_size`, the lowest-numbered
  queued run is emitted as a `dispatch_list` entry (its `worker_prompt`
  with absolute `{HEARTBEAT_PATH}/{TASK_ID}/{RUN_DIR}/{TARGET_REPO}`
  substituted), its job file moves `queue/ → claimed/`, and a `.lock` is
  written. The agent invokes one `Task` per dispatch entry.
- **Reap (claimed/running → completed/failed):** any terminal keyword in
  the heartbeat tail moves the job to `results/` and frees the slot.
  **Reap guard:** if the claimed job file is externally absent at reap,
  the result record carries `anomaly: claimed_job_file_absent_at_reap`
  rather than fabricating a clean success — the heartbeat stays the
  terminal authority, but the anomaly is recorded.
- **Stall (claimed/running → stalled):** heartbeat mtime older than
  `stall_threshold_minutes` (default 45). The mandatory ~3-min worker
  keepalive keeps a live run well under the threshold, so a stall means
  the worker has genuinely gone quiet.
- **Recover (stalled → running):** a fresh heartbeat (mtime back within
  threshold) returns a stalled run to running.
- **Launch failure (claimed → auth_or_launch_failed):** a claimed run
  that emits NO heartbeat within `launch_grace_minutes` (default 10) is
  terminal-failed with a synthesized result record — the dispatch never
  started a worker (auth prompt, tool error, etc.).

## Idempotency

Every transition checks "already done?" before mutating disk (job file
already moved, result already present). Running the same tick twice in a
row changes nothing but the `cycle` witness counter. A forced re-tick
("run another tick now") is therefore always safe.

## STOP semantics — and the in-flight orphan behavior (1A carry-forward 7)

A `STOP` file at the run-dir root makes the next tick **fully read-only**:
it reports `stop: true`, prints the final table, and mutates nothing (not
even `cycle`). The orchestrator agent then exits WITHOUT calling
ScheduleWakeup — the polling loop ends.

**The MVP has no kill semantics.** Dispatched workers are detached
subagent-launched processes that outlive their dispatch turn (this is the
architecture's deliberate design, validated in the 1A spike: a
`nohup`-detached worker keeps emitting heartbeats across many ticks). So
when STOP halts the orchestrator, any worker still in flight **keeps
running to its own completion** — it just has no orchestrator watching its
heartbeat. Its terminal sentinel and `quality/` output still land on disk;
they are simply not reaped into `results/` by a tick (because no further
ticks run). This orphan behavior was observed and accepted in the 1A spike
(pass 3): STOP halts the *orchestrator*, not the *workers*. Reaping an
orphan after the fact is possible by removing the STOP file and running
one more tick. Killing in-flight workers on STOP is deferred to a future
release (it needs worker PID tracking + cross-platform signal handling the
in-session model does not naturally own).

## Cadence

`next_tick_minutes` is `tick_interval_minutes` while any run is actively
running/claimed (or the run is done); when nothing is actively running
(all waiting/stalled) it is lengthened by `idle_tick_multiplier`. On
`done`/`stop` ticks the table prints the terminal banner instead of a
"Next tick in N min" line (1A carry-forward 6).

## v1.5.9 Phase 2B additions

### Shell dispatch (`dispatch_mode: "shell"`)

The state machine is identical; only how a worker STARTS changes. On a
shell dispatch the engine: writes the resolved `worker_prompt` to
`queue/job-NNNNN.prompt.txt` (quoting / arg-length safety, FR-15);
resolves the entry's `worker_cmd` argv template (the `{HEARTBEAT_PATH}/
{TASK_ID}/{RUN_DIR}/{TARGET_REPO}` block plus `{PROMPT_FILE}`); and emits
a `dispatch_list` entry carrying `dispatch_mode:"shell"` + the resolved
`worker_cmd`. The **ticker** (rungs 2-4), not the engine, Popens that argv
detached (POSIX `start_new_session=True`; Windows `DETACHED_PROCESS |
CREATE_NEW_PROCESS_GROUP`) and records the child PID in the claim lock.
Subagent mode is unchanged (the entry carries `worker_prompt` for the
agent's Task/Agent tool). cadence rungs 2-4 REQUIRE shell dispatch — an
externally-ticked session's subagents die with its turn.

### Claim locks + PID liveness (Council A-5)

`claimed/job-NNNNN.lock` records `{task_id, claimed_ts, dispatch_mode,
pid}`. The engine writes `pid: null` at claim; the spawning ticker updates
it with the real child PID after Popen. Stall detection then distinguishes
a **dead** worker from a **slow** one: if a shell run's recorded PID is no
longer alive (cross-platform check — `os.kill(pid,0)` POSIX,
`OpenProcess`+exit-code Windows) AND no terminal heartbeat has landed, the
run is failed FAST (no waiting out the launch grace). A terminal heartbeat
always wins over the dead-PID path (reaped completed/failed first). A
`pid: null` (claimed, not yet spawned) is skipped.

### E1 — concurrent-tick lockfile (FR-12)

Each tick acquires a non-blocking advisory lock on `<run-dir>/.tick.lock`
(`fcntl.flock` POSIX / `msvcrt.locking` Windows). If another tick process
holds it (overlapping cron fires, or a ticker loop plus a manual
`--once`), this tick **skips cleanly** — it emits `{skipped: true,
dispatch_list: [], …}` and mutates nothing — rather than racing the
on-disk state. Re-entry next tick is safe by idempotency.

### E2 — wall-clock-jump stall guard (FR-8)

The engine stores `last_tick_wall` (wall-clock seconds) each tick. If the
gap since the last tick is much larger than the cadence (machine slept /
hibernated), heartbeat ages are inflated through no fault of the workers,
so STALLED marking is **suppressed for that one tick** (a fresh heartbeat
the next tick clears it). A normal-sized gap past the stall threshold
still marks STALLED.

## v1.5.9 instruction 010 additions

### The worker contract + Postel's law

*A job is anything that appends JSON lines to a file.* `status` is the
**only** field the harness interprets (it drives the state machine);
everything else is decoration it displays but never reads. The worker need
not be an AI — a shell script, a make target, a CI job, or a human with
`echo >>` all qualify; the heartbeat helper is a convenience, not a
requirement. The contract honors **Postel's law — be conservative in what
the harness emits, liberal in what it accepts**: a worker that never
writes, dies mid-run, or writes garbage degrades to a visible
STALLED/failed/LAUNCH-FAIL row, never to a wedged state machine, and a
**malformed (non-JSON) line is skipped with a non-fatal warning** in the
tick log, never fatal. The reader proves this: it tail-scans on substring
keywords, `json.loads` each candidate line inside a `try`, and counts +
logs the skipped malformed lines (`_count_malformed`) without ever raising
into the tick.

### Heartbeat schema v2 (`label` / `data`) — read both, emit v2

Heartbeat lines are now `schema_version: "2"`: the v1 `phase`/`step` pair
collapses to a single free-form **`label`** (displayed verbatim in the
status-table **ACTIVITY** column — truncated to width and ASCII-sanitized
for *display only*, raw preserved on disk) plus an optional opaque
**`data`** object the harness never reads (the structure escape hatch / A2A
path). Postel on read: the engine still accepts v1 lines, falling back to
`phase` when no `label` is present. QPB's vendored worker maps its phase
identity into `label` as `"<number>:<slug>"` (e.g. `2:generation`) and
stashes the old step under `data.step`; that coupling never enters the
generic core. The gate's C-3 drift check now accepts `"1"` or `"2"` and
warns on anything else.

### Specifiable heartbeat file (FR-20)

By default the engine watches `run-NN/heartbeat.ndjson`. A plan entry MAY
declare an absolute **`heartbeat_path`** to point the harness at a status
file a pre-existing job already writes — recorded in the run's
`manifest.json` at init; `_heartbeat_path` then watches it and
`{HEARTBEAT_PATH}` resolves to it for the worker. The result/manifest
layout is unchanged. *Point the harness at a file your job already writes.*

### No model-transcribed paths (FR-21a) + LAUNCH-FAIL diagnostics (FR-21b)

Every harness-known path a worker needs — `{HEARTBEAT_PATH}`, `{TASK_ID}`,
`{RUN_DIR}`, `{TARGET_REPO}`, and the helper/demo-worker location
**`{HARNESS_BIN}`** (the engine's own bin directory) — is substituted
**mechanically by the engine before dispatch**. A worker prompt must never
ask a model to copy or substitute a literal path: in run
`20260612T005833Z` a hand-copied helper path was transcribed as
`/Users/anthropic/...` (username hallucinated), silently killing every
heartbeat while the job "completed" invisibly. The `<...>` notation that
survives in the **operator** bootstrap (`<PLAN>`, `<QPB_REPO>`, `<RUN_DIR>`)
is operator-supplied input or a value captured mechanically from command
output (`git rev-parse`, `--init`), never a path a model retypes.

`auth_or_launch_failed` covers more causes than auth (a transcribed path, a
missing helper, a bad `worker_cmd`), so its synthesized result record AND
the status table carry an actionable hint — *"no heartbeat received within
launch grace - check worker-side launch: auth, helper availability,
paths"*. The long state name is abbreviated to **`LAUNCH-FAIL`** in the
table so it can never overflow its column (display-only; the on-disk state
is unchanged).
