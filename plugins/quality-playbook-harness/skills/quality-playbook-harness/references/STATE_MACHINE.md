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
