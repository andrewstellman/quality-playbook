#!/usr/bin/env python3
"""qpb_harness_tick — Quality Playbook harness state-machine stepper
(v1.5.9 Phase 1B).

The deterministic Python half of the harness-as-skill. The orchestrator
SKILL.md runs this once per tick; the script reads disk state, advances
the state machine, and prints a JSON envelope the agent acts on. ALL the
state logic lives here — the agent's per-tick prose is small and fixed
(run script, dispatch listed Tasks, print table, ScheduleWakeup).

Usage:
    qpb_harness_tick.py --init <plan-path>   # scaffold a run-dir; print its path
    qpb_harness_tick.py <run-dir>            # run one tick; print JSON to stdout

Tick stdout JSON: {dispatch_list, status_table, next_tick_minutes, done, stop}.

Design: docs/design/QPB_v1.5.9_Harness_Skill_Design.md (§Inter-skill
communication contract, §Tick-based execution model, §Dispatch — Mode 1).
Grew from the validated spike/v1.5.9_phase_1A apparatus (the proven
patterns: atomic writes, state-guarded transitions, cycle-as-witness,
STOP read-only, the {dispatch_list,…} dispatch JSON shape).

State machine (per run-NN; see references/STATE_MACHINE.md):

    queued ── dispatch ──▶ claimed ── heartbeat STARTING/IN_PROGRESS ──▶ running
       │                     │                                            │
       │                     │ no heartbeat past launch_grace             │ terminal sentinel
       │                     ▼                                            ▼
       │            auth_or_launch_failed (terminal)            completed | failed (terminal)
       │                                                                  │
       └── (pool slot frees on any terminal) ◀───────────────────────────┘
                              running/claimed ── heartbeat mtime > stall_threshold ──▶ stalled

`stalled` is NON-terminal and NON-killable in the MVP (no kill semantics —
documented in STATE_MACHINE.md): the slot stays held, the run keeps being
watched, and a late heartbeat can move it back to running. `done` is true
only when every run is terminal (completed / failed / auth_or_launch_failed
/ abandoned-in-results).

Idempotency is mandatory: every transition checks "already done?" before
mutating disk. Running the same tick twice in a row changes nothing but
the `cycle` witness counter. A STOP file makes the tick fully read-only.

Stdlib only. Cross-platform (no os.fork, no signals).
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

# --- defaults (a plan may override any of these top-level keys) -------------
DEFAULT_POOL_SIZE = 3
DEFAULT_TICK_INTERVAL_MINUTES = 10
DEFAULT_STALL_THRESHOLD_MINUTES = 45      # design §Open questions #5 / Risks
DEFAULT_LAUNCH_GRACE_MINUTES = 10         # claimed + no heartbeat past this ⇒ launch failed
DEFAULT_IDLE_TICK_MULTIPLIER = 1          # >1 lengthens cadence when nothing is running

TAIL_LINES = 20
_TERMINAL_HB = ("COMPLETED", "FAILED", "ABANDONED")
_PLACEHOLDERS = ("HEARTBEAT_PATH", "TASK_ID", "RUN_DIR", "TARGET_REPO")

# Terminal run states (occupy no pool slot; count toward `done`).
_TERMINAL_STATES = ("completed", "failed", "auth_or_launch_failed", "abandoned")
# States that hold a pool slot (in-flight).
_INFLIGHT_STATES = ("claimed", "running", "stalled")


def _now() -> float:
    """Wall-clock seconds. Overridable via QPB_HARNESS_NOW (epoch float)
    so stall / launch-grace logic is testable without sleeping."""
    override = os.environ.get("QPB_HARNESS_NOW")
    if override:
        try:
            return float(override)
        except ValueError:
            pass
    return time.time()


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json(path: Path, data) -> None:
    """Atomic whole-file write (temp + rename) so a reader never sees a
    half-written status file."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _log(run_dir: Path, message: str) -> None:
    """Append a line to the per-run-dir tick log (best-effort; never
    raises into the tick)."""
    try:
        with (run_dir / "harness_tick.log").open("a", encoding="utf-8") as fh:
            fh.write(f"{_utc_iso()} {message}\n")
    except OSError:
        pass


# --- plan / config access ---------------------------------------------------

def _cfg(plan: dict, key: str, default):
    val = plan.get(key, default)
    return val if isinstance(val, type(default)) else default


# --- init -------------------------------------------------------------------

def init_run(plan_path: Path) -> Path:
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    entries = plan.get("entries") or []
    if not entries:
        raise ValueError(f"plan {plan_path} has no entries[]")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # Base dir is <repo>/harness_runs by default; QPB_HARNESS_RUNS_DIR
    # overrides it (tests point this at a tmp dir to stay hermetic).
    base = os.environ.get("QPB_HARNESS_RUNS_DIR")
    runs_root = Path(base) if base else Path(__file__).resolve().parent.parent / "harness_runs"
    run_dir = runs_root / stamp
    for sub in ("queue", "claimed", "results"):
        (run_dir / sub).mkdir(parents=True)
    runs: dict[str, dict] = {}
    for i, entry in enumerate(entries, start=1):
        run_name = "run-%02d" % i
        job_id = "job-%05d" % i
        rd = run_dir / run_name
        rd.mkdir()
        (rd / "heartbeat.ndjson").touch()
        _write_json(rd / "manifest.json", {
            "task_id": entry.get("task_id"),
            "target_repo": entry.get("target_repo"),
            "dispatch_mode": entry.get("dispatch_mode", "subagent"),
            "run": run_name,
            "job_id": job_id,
        })
        _write_json(run_dir / "queue" / (job_id + ".json"),
                    {"job_id": job_id, "run": run_name, "entry": entry})
        runs[run_name] = {
            "task_id": entry.get("task_id"),
            "job_id": job_id,
            "target_repo": entry.get("target_repo"),
            "state": "queued",
            "last_hb_status": None,
            "claimed_at": None,
        }
    _write_json(run_dir / "plan.json", plan)
    _write_json(run_dir / "harness_status.json", {
        "cycle": 0,
        "pool_size": _cfg(plan, "pool_size", DEFAULT_POOL_SIZE),
        "counts": _recount(runs),
        "done": False,
        "runs": runs,
    })
    _log(run_dir, f"init: {len(runs)} run(s) from {plan_path}")
    return run_dir


def _recount(runs: dict) -> dict:
    counts = {"queued": 0, "claimed": 0, "running": 0, "stalled": 0,
              "completed": 0, "failed": 0, "auth_or_launch_failed": 0,
              "abandoned": 0}
    for r in runs.values():
        counts[r["state"]] = counts.get(r["state"], 0) + 1
    return counts


# --- heartbeat reading ------------------------------------------------------

def _heartbeat_path(run_dir: Path, run_name: str) -> Path:
    return run_dir / run_name / "heartbeat.ndjson"


def _tail(hb: Path) -> list[str]:
    if not hb.exists():
        return []
    return [ln for ln in hb.read_text(encoding="utf-8").splitlines()[-TAIL_LINES:]
            if ln.strip()]


def _hb_observe(hb: Path):
    """Return (has_any, last_status_keyword, phase, mtime) for a heartbeat
    file. Pure substring matching on the tail — no schema validation here
    (the worker-side qpb_heartbeat.py owns valid emission; the harness only
    reads liveness keywords). last_status is the terminal/progress keyword
    on the LAST non-empty line."""
    lines = _tail(hb)
    if not lines:
        return (False, None, None, None)
    last = lines[-1]
    status = None
    for kw in (*_TERMINAL_HB, "IN_PROGRESS", "STARTING"):
        if kw in last:
            status = kw
            break
    phase = None
    if '"phase":' in last:
        try:
            phase = json.loads(last).get("phase")
        except (ValueError, TypeError):
            phase = None
    try:
        mtime = hb.stat().st_mtime
    except OSError:
        mtime = None
    return (True, status, phase, mtime)


def _terminal_status_of(hb: Path):
    """If any heartbeat line carries a terminal sentinel keyword, return it
    (COMPLETED / FAILED / ABANDONED); else None. Scans the whole tail so a
    terminal line followed by nothing is still caught."""
    for ln in _tail(hb):
        for kw in _TERMINAL_HB:
            if kw in ln:
                return kw
    return None


def _result_meta(hb: Path) -> dict:
    """Best-effort parse of the terminal sentinel line for result_file /
    summary (display + results sidecar). Never raises."""
    for ln in reversed(_tail(hb)):
        if any(kw in ln for kw in _TERMINAL_HB):
            try:
                obj = json.loads(ln)
                return {"result_file": obj.get("result_file"),
                        "summary": obj.get("summary"),
                        "status": obj.get("status")}
            except (ValueError, TypeError):
                return {}
    return {}


# --- the tick ---------------------------------------------------------------

def _dispatch_prompt(entry: dict, run_dir: Path, run_name: str) -> str:
    values = {
        "HEARTBEAT_PATH": str(_heartbeat_path(run_dir, run_name)),
        "TASK_ID": str(entry.get("task_id", "")),
        "RUN_DIR": str(run_dir / run_name),
        "TARGET_REPO": str(entry.get("target_repo", "")),
    }
    prompt = entry.get("worker_prompt", "")
    for key in _PLACEHOLDERS:
        prompt = prompt.replace("{%s}" % key, values[key])
    return prompt


def _move_to_results(run_dir: Path, run: dict, terminal_status: str,
                     hb: Path) -> bool:
    """Move the claimed job file to results/ as a terminal sentinel.
    Idempotent + GUARDED (carry-forward A-F6): if the claimed file is
    externally absent, we DON'T silently pretend success — we synthesize
    the result record from the heartbeat and log the anomaly, but the
    transition still completes (the heartbeat is the source of truth for
    terminal-ness). Returns True if a result file now exists."""
    job_id = run["job_id"]
    result_path = run_dir / "results" / (job_id.replace("job-", "result-") + ".json")
    if result_path.exists():
        return True  # already reaped — idempotent no-op
    src = run_dir / "claimed" / (job_id + ".json")
    meta = _result_meta(hb)
    record = {
        "job_id": job_id,
        "run": run.get("job_id") and run_name_of(run),
        "task_id": run.get("task_id"),
        "terminal_status": terminal_status,
        "result_file": meta.get("result_file"),
        "summary": meta.get("summary"),
        "reaped_ts": _utc_iso(),
    }
    if src.exists():
        # Capture the claimed manifest, then replace the file with the
        # terminal record at the results path.
        try:
            record["claimed"] = json.loads(src.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            record["claimed"] = None
        _write_json(result_path, record)
        src.unlink()
    else:
        # GUARD: claimed file vanished out from under us. Don't fabricate a
        # clean success — record the anomaly, but honor the heartbeat's
        # terminal verdict so the run can still leave the in-flight set.
        record["anomaly"] = "claimed_job_file_absent_at_reap"
        _write_json(result_path, record)
    # best-effort lock cleanup
    lock = run_dir / "claimed" / (job_id + ".lock")
    if lock.exists():
        try:
            lock.unlink()
        except OSError:
            pass
    return True


def run_name_of(run: dict) -> str:
    return run.get("_run_name", "")


def tick(run_dir: Path) -> dict:
    status = json.loads((run_dir / "harness_status.json").read_text(encoding="utf-8"))
    plan = json.loads((run_dir / "plan.json").read_text(encoding="utf-8"))
    runs = status["runs"]
    for name, r in runs.items():
        r["_run_name"] = name  # transient, stripped before write

    pool_size = status.get("pool_size") or _cfg(plan, "pool_size", DEFAULT_POOL_SIZE)
    tick_interval = _cfg(plan, "tick_interval_minutes", DEFAULT_TICK_INTERVAL_MINUTES)
    stall_secs = _cfg(plan, "stall_threshold_minutes",
                      DEFAULT_STALL_THRESHOLD_MINUTES) * 60
    grace_secs = _cfg(plan, "launch_grace_minutes",
                      DEFAULT_LAUNCH_GRACE_MINUTES) * 60
    idle_mult = _cfg(plan, "idle_tick_multiplier", DEFAULT_IDLE_TICK_MULTIPLIER)
    entries = {"run-%02d" % i: e
               for i, e in enumerate(plan.get("entries") or [], start=1)}
    now = _now()

    stop = (run_dir / "STOP").exists()
    dispatch_list: list[dict] = []

    if not stop:
        try:
            _advance(run_dir, runs, now, stall_secs, grace_secs)
            dispatch_list = _dispatch(run_dir, runs, entries, pool_size, now)
        except Exception:  # never let a transition crash the loop
            _log(run_dir, "TICK ERROR:\n" + traceback.format_exc())
        status["counts"] = _recount(runs)
        status["done"] = all(r["state"] in _TERMINAL_STATES for r in runs.values())
        status["cycle"] = status.get("cycle", 0) + 1
        # strip transient field, then persist
        for r in runs.values():
            r.pop("_run_name", None)
        _write_json(run_dir / "harness_status.json", status)
    else:
        for r in runs.values():
            r.pop("_run_name", None)

    done = status["done"]
    table = _format_table(run_dir, status, plan, terminal=(done or stop))
    next_minutes = _next_cadence(status, tick_interval, idle_mult)
    return {
        "dispatch_list": dispatch_list,
        "status_table": table,
        "next_tick_minutes": next_minutes,
        "done": done,
        "stop": stop,
    }


def _advance(run_dir, runs, now, stall_secs, grace_secs):
    """Reap terminals, detect stalls and launch failures. Mutates run
    state + disk. Every transition is guarded for idempotency."""
    for name, r in runs.items():
        state = r["state"]
        if state in _TERMINAL_STATES:
            continue
        hb = _heartbeat_path(run_dir, name)
        has_any, last_status, phase, mtime = _hb_observe(hb)
        if has_any:
            r["last_hb_status"] = last_status
        # 1. terminal sentinel ⇒ reap
        terminal = _terminal_status_of(hb)
        if terminal is not None:
            if _move_to_results(run_dir, r, terminal, hb):
                r["state"] = "failed" if terminal in ("FAILED", "ABANDONED") else "completed"
                _log(run_dir, f"{name}: reaped → {r['state']} ({terminal})")
            continue
        # 2. claimed + no heartbeat past launch grace ⇒ launch failed
        if state == "claimed" and not has_any:
            claimed_at = r.get("claimed_at")
            if claimed_at is not None and (now - claimed_at) > grace_secs:
                _synthesize_failure(run_dir, r,
                                    "auth_or_launch_failed",
                                    "no heartbeat within launch grace")
                r["state"] = "auth_or_launch_failed"
                _log(run_dir, f"{name}: AUTH_OR_LAUNCH_FAILED (no heartbeat)")
            continue
        # 3. heartbeat present ⇒ running; stale heartbeat ⇒ stalled
        if has_any:
            if mtime is not None and (now - mtime) > stall_secs:
                if r["state"] != "stalled":
                    r["state"] = "stalled"
                    _log(run_dir, f"{name}: STALLED (heartbeat mtime "
                                  f"{int(now - mtime)}s > {int(stall_secs)}s)")
            else:
                # fresh heartbeat — (re)mark running (recovers from stalled)
                if r["state"] in ("claimed", "stalled"):
                    r["state"] = "running"


def _dispatch(run_dir, runs, entries, pool_size, now) -> list[dict]:
    """Emit dispatch entries for queued runs while a pool slot is free.
    Guarded: a run already past queued is never re-dispatched."""
    inflight = sum(1 for r in runs.values() if r["state"] in _INFLIGHT_STATES)
    out: list[dict] = []
    for name in sorted(runs):
        r = runs[name]
        if r["state"] != "queued":
            continue
        if inflight >= pool_size:
            break
        src = run_dir / "claimed" / (r["job_id"] + ".json")
        qsrc = run_dir / "queue" / (r["job_id"] + ".json")
        if qsrc.exists() and not src.exists():
            qsrc.replace(src)
            _write_json(run_dir / "claimed" / (r["job_id"] + ".lock"), {
                "task_id": r["task_id"],
                "claimed_ts": _utc_iso(),
                "dispatched_by": "qpb_harness_tick",
            })
        r["state"] = "claimed"
        r["claimed_at"] = now
        inflight += 1
        out.append({
            "run": name,
            "task_id": r["task_id"],
            "worker_prompt": _dispatch_prompt(entries[name], run_dir, name),
        })
        _log(run_dir, f"{name}: dispatched (claimed)")
    return out


def _synthesize_failure(run_dir, r, terminal_state, reason):
    """Write a results sentinel for a run that failed WITHOUT a worker
    terminal heartbeat (e.g. dispatch never launched). Idempotent."""
    job_id = r["job_id"]
    result_path = run_dir / "results" / (job_id.replace("job-", "result-") + ".json")
    if result_path.exists():
        return
    _write_json(result_path, {
        "job_id": job_id,
        "task_id": r.get("task_id"),
        "terminal_status": terminal_state.upper(),
        "result_file": None,
        "summary": reason,
        "reaped_ts": _utc_iso(),
        "synthesized": True,
    })
    for suffix in (".json", ".lock"):
        p = run_dir / "claimed" / (job_id + suffix)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass


# --- presentation -----------------------------------------------------------

def _next_cadence(status, tick_interval, idle_mult) -> int:
    """tick_interval while any run is actively in flight; lengthened by
    idle_tick_multiplier when nothing is running (all waiting/stalled or
    nearly done) so an idle harness polls less often. Never below 1."""
    any_running = any(r["state"] in ("claimed", "running")
                      for r in status["runs"].values())
    if any_running or status.get("done"):
        return max(1, int(tick_interval))
    return max(1, int(tick_interval) * max(1, int(idle_mult)))


def _hb_age_str(run_dir, name) -> str:
    hb = _heartbeat_path(run_dir, name)
    if not hb.exists():
        return "-"
    try:
        age = int(_now() - hb.stat().st_mtime)
    except OSError:
        return "-"
    return "%dm%02ds" % (age // 60, age % 60)


def _format_table(run_dir, status, plan, terminal: bool) -> str:
    bar = "-" * 86
    rows = [
        "Run-Dir: %s (cycle %d)" % (run_dir.name, status.get("cycle", 0)),
        bar,
        "%-5s%-26s%-8s%-20s%-8s%-13s%s" % (
            "RUN", "REPO", "MODE", "STATE", "PHASE", "LAST-HB", "HB-AGE"),
    ]
    for name in sorted(status["runs"]):
        r = status["runs"][name]
        _, _, phase, _ = _hb_observe(_heartbeat_path(run_dir, name))
        rows.append("%-5s%-26s%-8s%-20s%-8s%-13s%s" % (
            name[4:],
            (r.get("target_repo") or "-")[:25],
            "subgnt",
            r["state"],
            (str(phase) if phase is not None else "-")[:7],
            r.get("last_hb_status") or "-",
            _hb_age_str(run_dir, name),
        ))
    c = status["counts"]
    rows.append(bar)
    rows.append(
        "Queue: %d  Claimed: %d  Running: %d  Stalled: %d  "
        "Completed: %d  Failed: %d" % (
            c.get("queued", 0), c.get("claimed", 0), c.get("running", 0),
            c.get("stalled", 0), c.get("completed", 0),
            c.get("failed", 0) + c.get("auth_or_launch_failed", 0)
            + c.get("abandoned", 0)))
    if terminal:
        if status.get("done"):
            rows.append("DONE — all runs terminal. No further ticks.")
        else:
            rows.append("STOP — halting. No further ticks.")
    else:
        rows.append("Next tick in %d min" % _next_cadence(
            status, _cfg(plan, "tick_interval_minutes",
                         DEFAULT_TICK_INTERVAL_MINUTES),
            _cfg(plan, "idle_tick_multiplier", DEFAULT_IDLE_TICK_MULTIPLIER)))
    return "\n".join(rows)


def main(argv) -> int:
    if len(argv) == 3 and argv[1] == "--init":
        print(init_run(Path(argv[2]).resolve()))
        return 0
    if len(argv) == 2 and argv[1] not in ("--init", "-h", "--help"):
        print(json.dumps(tick(Path(argv[1]).resolve()), indent=2))
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
