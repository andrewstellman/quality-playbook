# Dispatch guide — per-mode detail

Three dispatch modes are supported. Each plan entry declares one. Modes mix freely within a plan; the tick handles each entry by its declared mode.

The three modes are documented in the harness SKILL.md § Dispatch modes at a higher level. This file is the concrete-example reference the SKILL.md tells the agent to load.

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

**Pre-flight auth check (Council finding B-1).** BEFORE the dispatch shell-out, run TWO probes against the CLI binary:

1. **Binary present:**
   ```bash
   <cli_command_first_word> --version
   ```
   Example: `copilot --version`. Expected: exit 0 with a version string. Failure → mark job AUTH_OR_LAUNCH_FAILED, skip.

2. **Auth round-trip:**
   ```bash
   <cli_command> -p "echo ok"
   ```
   Example: `copilot --model claude-sonnet-4.6 --allow-all -p "echo ok"`. Expected: roundtrip within 30 sec with output containing "ok" (CLI may wrap it in explanation). Failure → mark AUTH_OR_LAUNCH_FAILED, skip.

Write both probe outcomes to `run-NN/auth_check.log`. If either fails, do NOT dispatch — write `result-NNNNN.json` with `status=FAILED`, `failure_subtype=AUTH_OR_LAUNCH_FAILED`, move manifest queue/ → results/ directly (bypass `claimed/`).

**Dispatch shell-out template:**

```bash
cd <absolute run-NN> && \
  QPB_TASK_ID=<uuid> QPB_HEARTBEAT_PATH=<absolute heartbeat path> \
  <cli_command> -p "$(cat worker_prompt.md)" > worker.log 2>&1 &
WORKER_PID=$!
disown $WORKER_PID
```

- `cd <absolute run-NN>` ensures the worker's `worker.log` and any incidentals land in the run-dir.
- `QPB_TASK_ID` and `QPB_HEARTBEAT_PATH` are exported so the worker's `qpb_heartbeat.py` calls find them.
- `-p` is the headless / one-shot prompt flag (most CLIs support this; codex uses `exec --full-auto`; substitute per-CLI).
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

**Per-CLI examples.**

```
# GitHub Copilot CLI
copilot --model claude-sonnet-4.6 --allow-all -p "$(cat worker_prompt.md)"

# Codex CLI (note: exec subcommand instead of -p)
codex exec --full-auto --model gpt-5.5 -c model_reasoning_effort='"medium"' "$(cat worker_prompt.md)"

# Claude CLI
claude --print --model opus-4.7 --dangerously-skip-permissions "$(cat worker_prompt.md)"
```

The plan entry's `cli_command` field is the verbatim shell command sans the worker prompt — the harness appends `-p "$(cat worker_prompt.md)"` (or the CLI's equivalent flag) at dispatch time.

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

---

*See `STATE_MACHINE.md` for transition table and worked example. Schemas in `../schemas/`. Example plan at `examples/small_plan.json`.*
