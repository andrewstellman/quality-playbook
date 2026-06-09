# Dispatch guide — per-mode detail

Three dispatch modes are supported. Each plan entry declares one. Modes mix freely within a plan; the tick handles each entry by its declared mode.

The three modes are documented in the harness SKILL.md § Dispatch modes at a higher level. This file is the concrete-example reference the SKILL.md tells the agent to load.

---

## First-tick spawn — the daemon

Before any plan-entry dispatch happens, the very first tick spawns the v1.5.9 sidecar daemon. The spawn is `subprocess.Popen` with platform-appropriate detachment:

**Unix:**

```python
import subprocess, sys
from pathlib import Path

daemon_py = Path("bin/qpb_tick_daemon.py").resolve()
run_dir = Path("harness_runs/2026-06-09T14-30-00Z/").resolve()
claude_binary = "/usr/local/bin/claude"           # absolute path
harness_plugin_dir = Path("plugins/quality-playbook-harness").resolve()

subprocess.Popen(
    [sys.executable, str(daemon_py),
     "--run-dir", str(run_dir),
     "--interval-minutes", "10",
     "--claude-binary", claude_binary,
     "--harness-plugin-dir", str(harness_plugin_dir)],
    start_new_session=True,                       # os.setsid in child
    stdout=open(run_dir / "daemon.log", "ab"),
    stderr=subprocess.STDOUT,
    stdin=subprocess.DEVNULL,
)
```

The `start_new_session=True` flag is critical — it calls `os.setsid()` in the child before exec, detaching the daemon from the orchestrator's terminal session. Without it, the daemon dies when the orchestrator's shell exits.

**Windows:**

```python
subprocess.Popen(
    [sys.executable, str(daemon_py), ...same args...],
    creationflags=(
        subprocess.DETACHED_PROCESS
        | subprocess.CREATE_NEW_PROCESS_GROUP
    ),
    stdout=open(run_dir / "daemon.log", "ab"),
    stderr=subprocess.STDOUT,
    stdin=subprocess.DEVNULL,
)
```

On Windows, `os.setsid` doesn't exist; detachment is achieved via the `creationflags` at spawn time.

**Daemon CLI flags / env vars.** Both invocation paths are equivalent — the daemon prefers the CLI flag when both are present:

| CLI flag | Env var | Required? | Notes |
|---|---|---|---|
| `--run-dir` | `QPB_RUN_DIR` | yes | Absolute path to the harness run-dir. |
| `--interval-minutes` | `QPB_TICK_INTERVAL_MINUTES` | yes | Float minutes between wakes. |
| `--claude-binary` | `QPB_CLAUDE_BINARY` | yes | Absolute path to the host `claude` CLI. |
| `--harness-plugin-dir` | `QPB_HARNESS_PLUGIN_DIR` | no | Forwarded to `claude --print --plugin-dir`. |

**Lifecycle contract.** Once spawned, the daemon:

1. Acquires `<run-dir>/daemon.pid` via `O_EXCL` open. On race-loss it exits code 7 (lock held by another live daemon).
2. Installs SIGTERM / SIGINT handlers (Unix) for graceful exit.
3. Enters the wakeup loop. Each iteration: touch `daemon.heartbeat` (mtime updated), check for `<run-dir>/done.marker` (exit cleanly if present, removing `daemon.pid`), fire `claude --print -p "tick harness on run-dir <run-dir>"` with `timeout = 0.9 × interval_seconds`, sleep `interval_seconds`.
4. Logs every wake / fire / result / sleep / signal / shutdown event to `<run-dir>/daemon.log` with ISO timestamps.

**Operator-facing management.** The operator CLI is `bin/qpb_harness.py`:

```bash
python3 bin/qpb_harness.py status                  # list all active daemons
python3 bin/qpb_harness.py stop <run-dir>          # SIGTERM then SIGKILL after 5s
python3 bin/qpb_harness.py gc                      # sweep stale PID files
```

Exit codes: 0 normal, 2 bad invocation, 5 run-dir not found, 7 PID file present but PID not alive.

**Crash recovery from the harness side.** If the harness skill is invoked manually on a run whose daemon has died (heartbeat mtime > 3× interval OR PID not alive), the harness re-spawns the daemon using the exact same `subprocess.Popen` invocation as above. The daemon's PID-file lock will overwrite the stale lock automatically.

---

## Mode 1 — in-process Task subagent (Claude Code only)

**When to use.** The host CLI is Claude Code and the orchestrator wants the worker to run as a subagent of the same Claude Code session. Lowest latency, simplest auth (same session = same auth). Subject to subscription concurrency caps (Council finding A-3 capped default `pool_size=3`).

**Dispatch mechanism.** Invoke the `Task` tool with the rendered `worker_prompt.md` as the prompt argument.

**Worker prompt header — MANDATORY first paragraph (Council finding A-2).** The very first paragraph of the prompt that the subagent reads MUST be the absolute-path block:

```
HEARTBEAT_PATH=<absolute path to run-NN/heartbeat.ndjson>
TASK_ID=<uuid>
RUN_DIR=<absolute path to run-NN/>
TARGET_REPO=<absolute path to the target repo>

You are a QPB worker. Before any work:
1. Set environment variables QPB_TASK_ID=${TASK_ID} and QPB_HEARTBEAT_PATH=${HEARTBEAT_PATH}.
   In Claude Code these env vars are exported by Bash tool calls; you can also pass --task-id and --heartbeat-path on each qpb_heartbeat.py invocation.
2. cd to TARGET_REPO.
3. Load the quality-playbook skill.
4. Emit STARTING heartbeat for Phase 1 via:
     python3 -m bin.qpb_heartbeat emit --phase "Phase 1" --step "start" --status STARTING \
       --task-id ${TASK_ID} --heartbeat-path ${HEARTBEAT_PATH}
5. Run the playbook (Phase 1 through Phase 6).
6. On terminal, emit:
     python3 -m bin.qpb_heartbeat terminal --status COMPLETED \
       --result-file quality/SUMMARY.md --summary "one-line outcome" \
       --task-id ${TASK_ID} --heartbeat-path ${HEARTBEAT_PATH}

Return to the orchestrator: ONLY a short summary string (phase reached, last status, mtime age of heartbeat). Do NOT echo heartbeat content. Do NOT echo file contents.
```

Per Council finding A-2, absolute paths are mandatory; never derive from cwd. The subagent may run `cd TARGET_REPO` for its phase work, but heartbeat emits MUST point at the absolute `HEARTBEAT_PATH` (different directory).

**Subagent return contract.** The orchestrator's context grows by whatever the subagent returns. Cap it at a short summary string. The orchestrator parses just enough to know "did the dispatch produce a viable worker?" — anything more it reads from disk on the next tick.

**Pool cap rationale (Council finding A-3).** Subscription concurrency caps + orchestrator context bloat are both bounded by capping pool at 3 in-process subagents. The plan schema's `pool_size` field can override, but the harness SKILL.md documents "if going higher, expect subscription throttling and/or orchestrator-context growth."

---

## Mode 2 — cross-CLI shell-out

**When to use.** The orchestrator runs in one CLI (e.g. Claude Code) and dispatches workers to a different CLI (`copilot`, `codex`, another `claude` instance). Maximum dispatch flexibility and bypasses per-CLI concurrency caps (each CLI has its own quota). Most useful when the operator wants to run >3 workers in parallel.

**Pre-flight auth check (Council finding B-1) — TWO probes, BOTH mandatory.** BEFORE the dispatch shell-out, run TWO probes against the CLI binary:

1. **Binary present (`--version` probe):**
   ```bash
   <cli_command_first_word> --version
   ```
   Example: `copilot --version`. Expected: exit 0 within 10 sec with a version string. Failure → mark `state=failed`, `failure_subtype=AUTH_FAILED`, do NOT dispatch.

2. **Auth round-trip (`--print "echo ok"` probe — B-1 ROUNDTRIP):**
   ```bash
   <cli_command> --print "echo ok"
   ```
   (Or the CLI's equivalent one-shot flag. Examples below.) Expected: roundtrip within 30 sec, exit 0, AND stdout must contain the substring "ok" (CLI may wrap it in narrative — substring-match, don't equality-check). Failure → mark `state=failed`, `failure_subtype=AUTH_FAILED`, do NOT dispatch.

Both probe outputs (stdout, stderr, rc) MUST be written to `<run-dir>/run-NN/auth_check.log` AND surfaced in `harness_status.json` under the entry's `auth_check_probes` block for operator diagnosis:

```json
"auth_check_probes": {
  "version": {"rc": 0, "stdout": "claude version 2.1.0\n", "stderr": ""},
  "roundtrip": {"rc": 0, "stdout": "ok\n", "stderr": ""}
}
```

If either probe fails, write `result-NNNNN.json` with `status=FAILED`, `failure_subtype=AUTH_FAILED`, move manifest queue/ → results/ directly (bypass `claimed/`).

**Distinction:** `AUTH_FAILED` (this transition, transition #8) fires PRE-dispatch when either probe fails. `AUTH_OR_LAUNCH_FAILED` (transition #4) fires POST-dispatch when the worker dispatches successfully but never emits a STARTUP heartbeat within 60 sec. They are different failure modes with different diagnostic signals.

**Per-CLI probe examples.**

```bash
# GitHub Copilot CLI
copilot --version
copilot --model claude-sonnet-4.6 --allow-all -p "echo ok"

# Codex CLI (note: exec subcommand, --sandbox workspace-write)
codex --version
codex exec --sandbox workspace-write --model gpt-5.5 "echo ok"

# Claude CLI
claude --version
claude --print --model opus-4.7 --dangerously-skip-permissions "echo ok"
```

**Dispatch shell-out template (after pre-flight passes):**

```bash
cd <absolute run-NN> && \
  QPB_TASK_ID=<uuid> QPB_HEARTBEAT_PATH=<absolute heartbeat path> \
  <cli_command> -p "$(cat worker_prompt.md)" > worker.log 2>&1 &
WORKER_PID=$!
disown $WORKER_PID
```

- `cd <absolute run-NN>` ensures the worker's `worker.log` and any incidentals land in the run-dir.
- `QPB_TASK_ID` and `QPB_HEARTBEAT_PATH` are exported so the worker's `qpb_heartbeat.py` calls find them.
- `-p` is the headless / one-shot prompt flag (most CLIs support this; codex uses `exec --sandbox workspace-write`; substitute per-CLI).
- `> worker.log 2>&1 &` backgrounds and captures both streams.
- `WORKER_PID=$!` captures the backgrounded worker's PID — write this immediately to `claimed/job-NNNNN.lock` per the SKILL.md § Worker lock file section.
- `disown $WORKER_PID` detaches from the orchestrator's job table so the worker survives the orchestrator's exit at end-of-tick.

**Worker lock file (Council A-5).** Right after capturing `WORKER_PID`, write `claimed/job-NNNNN.lock` containing `{schema_version: "1", task_id, pid: <WORKER_PID>, start_time: <ISO8601>, cwd: <absolute run-NN>, dispatch_mode: "cross_cli"}`. The next tick uses this for liveness:

```bash
# Mode 2 liveness check (next tick)
if ! kill -0 <pid_from_lock> 2>/dev/null; then
  # PID is gone. Check if we should fast-fail.
  age=$(( $(date +%s) - $(date -d <start_time_from_lock> +%s) ))
  if [ $age -gt 60 ] && [ <no_heartbeat_in_stall_window> ]; then
    # Fail fast — Council A-5 early-detection
    set state=failed failure_subtype=WORKER_FAILED
  fi
fi
```

This is distinct from STALLED (heartbeats stopped) and AUTH_OR_LAUNCH_FAILED (no STARTUP heartbeat in 60 sec post-dispatch); WORKER_FAILED means the process disappeared after dispatch without a terminal sentinel — usually a worker crash or unexpected exit.

**Worker prompt header.** Same absolute-path block as Mode 1. The worker should read the env vars and write heartbeats to the absolute path. (The block is identical so workers don't need to know which dispatch mode brought them up.)

**STARTUP heartbeat window.** After dispatch, the worker has 60 sec to emit its first heartbeat. The next tick checks: if `heartbeat.ndjson` is empty or missing AND `now - dispatched_at > 60 sec`, mark `failure_subtype=AUTH_OR_LAUNCH_FAILED`. Distinct from STALLED (which means "started then stopped"); this captures "never started."

---

## Mode 3 — operator-manual dispatch

**When to use.** The operator wants to watch one worker interactively, or the host CLI doesn't support shell-out, or auth is interactive (e.g. first-time login). Intended for "one worker the operator runs by hand in a separate window," NOT as a scaling primitive.

**Dispatch mechanism.** Write the rendered `worker_prompt.md` to `run-NN/operator_prompt.md` and announce via `harness_status.json`:

```json
{
  "action_required": [
    {
      "tag": "MANUAL_DISPATCH_001",
      "run_dir": "<absolute run-NN/>",
      "instructions": "Open a new terminal, cd to <run-NN/>, paste operator_prompt.md into your CLI, run it. Then touch operator_started in this directory.",
      "ack_file": "<absolute path to run-NN/operator_started>"
    }
  ]
}
```

**Mac notification.** On macOS, the harness MAY additionally fire an osascript notification so the banner doesn't sit silently:

```bash
osascript -e 'display notification "MANUAL_DISPATCH_001 — see harness_status.json" with title "QPB Harness ACTION REQUIRED"'
```

**Acknowledgment.** The operator creates `run-NN/operator_started` (touch the file, or write any contents). Subsequent ticks detect the ack file and treat the job as "in flight" — the worker is now responsible for emitting heartbeats; the harness only tracks via heartbeat tail (same as Mode 2).

**Stall detection.** Same 45-min global threshold + 3-min keepalive applies. If the operator pasted the prompt but the worker never started emitting heartbeats, the AUTH_OR_LAUNCH_FAILED window fires at 60 sec post-ack.

**Why discouraged for `pool_size > 2`.** Operators can't track more than ~2 manual windows reliably. With pool > 2, the operator misses ack files, forgets which window is which, and the manual dispatch loses its "watch it interactively" benefit. Mix Mode 3 with Mode 1/2 instead: one Mode 3 entry for the run the operator wants to watch, the rest in Mode 1 or 2 for hands-off execution.

---

## Cross-mode invariants

These hold regardless of dispatch mode:

1. **Absolute paths in worker prompt header.** Council finding A-2. Never derive from cwd; the worker may `cd` to TARGET_REPO but heartbeats go to the absolute path.
2. **`qpb_heartbeat.py` is the only allowed emit mechanism.** Workers MUST NOT append to `heartbeat.ndjson` via shell `>>` — Council finding A-1 collision risk. The helper script uses `O_APPEND` directly; shell `>>` semantics vary by host.
3. **One worker per run-NN/ directory.** No two workers share a `heartbeat.ndjson` even within one plan execution. Isolation by construction.
4. **Schema version "1" in every emitted artifact.** Plan, job_manifest, result, heartbeat. Forward-compat is via `schema_warnings[]` on read; drift is caught by the Phase 1C tests.
5. **STARTUP heartbeat within 60 sec post-dispatch.** Otherwise AUTH_OR_LAUNCH_FAILED. Applies to all three modes (Mode 3 measures from ack-file creation, not from prompt write).
6. **Worker lock file at dispatch time (Council A-5).** Every dispatch writes `claimed/job-NNNNN.lock` sibling to the manifest, containing PID (Mode 2) or orchestrator PID (Mode 1) or omitted (Mode 3), start_time, cwd, dispatch_mode. The lock file is deleted when the manifest moves claimed/ → results/. Mode 2 uses the PID for `kill -0` liveness; the other modes treat the lock as informational only. See `STATE_MACHINE.md` § Worker lock file for the liveness algorithm.
7. **Mode 2 B-1 pre-flight is two probes.** `--version` AND `--print "echo ok"`. Both must succeed; one failure → `AUTH_FAILED` (transition #8 in `STATE_MACHINE.md`).

---

*See `STATE_MACHINE.md` for transition table and worked example, plus § Daemon lifecycle invariants for the daemon-side contracts. Schemas in `../schemas/`. Example plan at `examples/small_plan.json`.*
