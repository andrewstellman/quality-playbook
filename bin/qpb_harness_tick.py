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

Stdlib only. Cross-platform (no process forking, no signals).
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
# FR-21a (instruction 010): EVERY harness-known path a worker needs is
# substituted MECHANICALLY by the engine before dispatch — a worker prompt
# must NEVER ask a model to transcribe a literal path. {HARNESS_BIN} (the
# engine's own bin directory) is the placeholder for the demo-worker /
# helper location, replacing the hand-copied <HARNESS_BIN> that silently
# killed run-02 in 20260612T005833Z (username hallucinated on transcription).
_PLACEHOLDERS = ("HEARTBEAT_PATH", "TASK_ID", "RUN_DIR", "TARGET_REPO",
                 "HARNESS_BIN")
# v1.5.9 Phase 2B: shell dispatch adds {PROMPT_FILE} (the per-job prompt
# written to queue/job-NNNNN.prompt.txt for quoting/arg-length safety).
_SHELL_PLACEHOLDERS = _PLACEHOLDERS + ("PROMPT_FILE",)
# The engine knows its own bin directory (FR-21a {HARNESS_BIN}); a worker
# never transcribes it.
_HARNESS_BIN = str(Path(__file__).resolve().parent)
# Heartbeat lines: current emit is "2" (label/data); the reader still
# accepts "1" (phase/step) — Postel (FR-18/19).
SCHEMA_VERSION = "2"
# A wall-clock jump larger than this multiple of the tick interval means the
# machine slept/hibernated (E2): heartbeat ages are inflated, so stall
# marking is suppressed for one tick rather than false-STALLING.
_WALLCLOCK_JUMP_FACTOR = 4

# Terminal run states (occupy no pool slot; count toward `done`).
_TERMINAL_STATES = ("completed", "failed", "auth_or_launch_failed", "abandoned")
# States that hold a pool slot (in-flight).
_INFLIGHT_STATES = ("claimed", "running", "stalled")

# FR-21b: AUTH_OR_LAUNCH_FAILED covers more causes than auth (transcribed
# path, missing helper, bad worker_cmd) — the synthesized result + the table
# footnote carry this actionable hint, not a bare "auth failed".
_LAUNCH_FAIL_HINT = ("no heartbeat received within launch grace - check "
                     "worker-side launch: auth, helper availability, paths")
# FR-21b: long internal state names must not overflow the status-table
# column. Display-only abbreviation (the on-disk state is unchanged).
_STATE_DISPLAY = {"auth_or_launch_failed": "LAUNCH-FAIL"}


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


def _pid_alive(pid) -> bool:
    """Cross-platform 'is this PID still running?' (Council A-5: lets stall
    detection tell a dead shell-worker process from a slow one). POSIX:
    os.kill(pid, 0). Windows: OpenProcess + exit-code probe. Unknown/bad
    pid ⇒ treated as NOT alive (conservative — a vanished process should
    free its slot)."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if pid <= 0:
        return False
    if os.name == "nt":  # Windows
        try:
            import ctypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            STILL_ACTIVE = 259
            k = ctypes.windll.kernel32
            h = k.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not h:
                return False
            try:
                code = ctypes.c_ulong()
                if not k.GetExitCodeProcess(h, ctypes.byref(code)):
                    return False
                return code.value == STILL_ACTIVE
            finally:
                k.CloseHandle(h)
        except Exception:
            return False
    # POSIX
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by another user
    except OSError:
        return False


def _lock_pid(run_dir: Path, job_id: str):
    """Return the PID recorded in claimed/<job>.lock (shell dispatch),
    or None. The lock is written by the tick engine at claim and updated
    with the real PID by the spawning tier (ticker) per A-5."""
    lock = run_dir / "claimed" / (job_id + ".lock")
    if not lock.is_file():
        return None
    try:
        return json.loads(lock.read_text(encoding="utf-8", errors="replace")).get("pid")
    except (OSError, ValueError):
        return None


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
        manifest = {
            "task_id": entry.get("task_id"),
            "target_repo": entry.get("target_repo"),
            "dispatch_mode": entry.get("dispatch_mode", "subagent"),
            "run": run_name,
            "job_id": job_id,
        }
        # FR-20: a plan entry MAY point the harness at a heartbeat file the
        # job already writes (absolute). Recorded here so _heartbeat_path
        # watches it instead of the run-dir default.
        if entry.get("heartbeat_path"):
            manifest["heartbeat_path"] = entry["heartbeat_path"]
        _write_json(rd / "manifest.json", manifest)
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
    """The file the engine watches for this run. Default: the run-dir's own
    ``run-NN/heartbeat.ndjson``. FR-20 (specifiable heartbeat file): if the
    plan entry declared an absolute ``heartbeat_path`` (recorded in the
    per-run manifest at init), watch THAT file instead — so the harness can
    point at a status file a pre-existing job already writes, with no change
    to the job. The result/manifest layout is unaffected."""
    default = run_dir / run_name / "heartbeat.ndjson"
    mf = run_dir / run_name / "manifest.json"
    if mf.is_file():
        try:
            override = json.loads(
                mf.read_text(encoding="utf-8", errors="replace")
            ).get("heartbeat_path")
        except (OSError, ValueError):
            override = None
        if override:
            return Path(override)
    return default


def _tail(hb: Path) -> list[str]:
    # v1.5.9 [Phase 2 prep] / 189-class: heartbeat.ndjson is EXTERNAL
    # content (worker-written), so the read uses errors="replace" — a
    # stray non-UTF-8 byte from a worker must not crash the tick on a
    # Windows cp1252 host (the 185/189/190 hazard chain). The substring
    # liveness matching downstream is unaffected by a replacement char.
    if not hb.exists():
        return []
    return [ln for ln in hb.read_text(encoding="utf-8", errors="replace")
            .splitlines()[-TAIL_LINES:]
            if ln.strip()]


def _hb_observe(hb: Path):
    """Return (has_any, last_status_keyword, activity, mtime) for a
    heartbeat file. Pure substring matching on the tail — no schema
    validation here (the worker owns valid emission; the harness only reads
    liveness keywords + the display label). last_status is the terminal/
    progress keyword on the LAST non-empty line. ``activity`` is the v2
    ``label`` of that line, falling back to the v1 ``phase`` (Postel: read
    both) — it is display-only and never interpreted."""
    lines = _tail(hb)
    if not lines:
        return (False, None, None, None)
    last = lines[-1]
    status = None
    for kw in (*_TERMINAL_HB, "IN_PROGRESS", "STARTING"):
        if kw in last:
            status = kw
            break
    activity = None
    if '"label":' in last or '"phase":' in last:
        try:
            obj = json.loads(last)
            activity = obj.get("label") or obj.get("phase")
        except (ValueError, TypeError):
            activity = None
    try:
        mtime = hb.stat().st_mtime
    except OSError:
        mtime = None
    return (True, status, activity, mtime)


def _count_malformed(hb: Path) -> int:
    """Count non-empty heartbeat lines that aren't valid JSON. The reader
    SKIPS these (Postel: liberal in what it accepts; a malformed line is
    never fatal) — this is only for the non-fatal warning in _advance."""
    bad = 0
    for ln in _tail(hb):
        try:
            json.loads(ln)
        except ValueError:
            bad += 1
    return bad


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
        "HARNESS_BIN": _HARNESS_BIN,
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

    # E2: a wall-clock gap since the last tick much larger than the cadence
    # means the machine slept/hibernated — heartbeat ages are inflated, so
    # suppress STALLED marking for this one tick.
    last_wall = status.get("last_tick_wall")
    suppress_stall = bool(
        last_wall is not None
        and (now - last_wall) > max(stall_secs, tick_interval * 60)
        * _WALLCLOCK_JUMP_FACTOR)

    if not stop:
        try:
            _advance(run_dir, runs, now, stall_secs, grace_secs, suppress_stall)
            dispatch_list = _dispatch(run_dir, runs, entries, pool_size, now)
        except Exception:  # never let a transition crash the loop
            _log(run_dir, "TICK ERROR:\n" + traceback.format_exc())
        if suppress_stall:
            _log(run_dir, f"E2: wall-clock jump ({int(now - last_wall)}s since "
                          f"last tick) — stall marking suppressed this tick")
        status["counts"] = _recount(runs)
        status["done"] = all(r["state"] in _TERMINAL_STATES for r in runs.values())
        status["cycle"] = status.get("cycle", 0) + 1
        status["last_tick_wall"] = now
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


def _advance(run_dir, runs, now, stall_secs, grace_secs, suppress_stall=False):
    """Reap terminals, detect stalls and launch failures. Mutates run
    state + disk. Every transition is guarded for idempotency.

    ``suppress_stall`` (E2): set when this tick detected a wall-clock jump
    (machine slept/hibernated) — heartbeat ages are inflated this tick, so
    STALLED marking is skipped to avoid false stalls."""
    for name, r in runs.items():
        state = r["state"]
        if state in _TERMINAL_STATES:
            continue
        hb = _heartbeat_path(run_dir, name)
        has_any, last_status, _activity, mtime = _hb_observe(hb)
        if has_any:
            r["last_hb_status"] = last_status
        # Postel: a malformed (non-JSON) heartbeat line is SKIPPED by the
        # reader, never fatal — but surface it as a non-fatal warning so an
        # operator can see a worker is writing garbage (FR-19).
        bad = _count_malformed(hb)
        if bad:
            _log(run_dir, f"{name}: WARN {bad} malformed heartbeat line(s) "
                          f"skipped (Postel: liberal accept, non-fatal)")
        # 1. terminal sentinel ⇒ reap
        terminal = _terminal_status_of(hb)
        if terminal is not None:
            if _move_to_results(run_dir, r, terminal, hb):
                r["state"] = "failed" if terminal in ("FAILED", "ABANDONED") else "completed"
                _log(run_dir, f"{name}: reaped → {r['state']} ({terminal})")
            continue
        # 1b. shell dispatch with a recorded-but-dead PID and no terminal
        #     heartbeat ⇒ the worker process died without finishing (A-5).
        #     Checked BEFORE the time-based grace/stall paths so a dead
        #     process is failed fast and precisely (no waiting out the
        #     launch grace). A recorded pid of None (just claimed, not yet
        #     spawned) is skipped.
        pid = _lock_pid(run_dir, r["job_id"])
        if pid is not None and not _pid_alive(pid):
            _synthesize_failure(run_dir, r, "failed",
                                f"shell worker process {pid} exited without a "
                                f"terminal heartbeat")
            r["state"] = "failed"
            _log(run_dir, f"{name}: FAILED (dead shell PID {pid}, no terminal)")
            continue
        # 2. claimed + no heartbeat past launch grace ⇒ launch failed
        if state == "claimed" and not has_any:
            claimed_at = r.get("claimed_at")
            if claimed_at is None:
                # Self-heal a claimed run with no claimed_at (hand-edit /
                # partial-advance anomaly, panelist A-F4): start the grace
                # clock now instead of being permanently immune to it.
                r["claimed_at"] = now
            elif (now - claimed_at) > grace_secs:
                _synthesize_failure(run_dir, r,
                                    "auth_or_launch_failed",
                                    _LAUNCH_FAIL_HINT)
                r["state"] = "auth_or_launch_failed"
                _log(run_dir, f"{name}: AUTH_OR_LAUNCH_FAILED (no heartbeat)")
            continue
        # 3. heartbeat present ⇒ running; stale heartbeat ⇒ stalled
        if has_any:
            if mtime is None:
                # Heartbeat exists but couldn't be stat'd (transient OS
                # race, panelist B-F3). Be CONSERVATIVE: never recover to
                # running off an unknowable mtime — leave the state as-is so
                # a genuine stall isn't masked. The next tick re-evaluates.
                pass
            elif (now - mtime) > stall_secs and not suppress_stall:
                if r["state"] != "stalled":
                    r["state"] = "stalled"
                    _log(run_dir, f"{name}: STALLED (heartbeat age "
                                  f"{int(now - mtime)}s > stall threshold "
                                  f"{int(stall_secs)}s)")
            else:
                # fresh heartbeat (or stall suppressed by an E2 wall-clock
                # jump this tick) — (re)mark running, recovering from stalled
                if r["state"] in ("claimed", "stalled"):
                    r["state"] = "running"


def _resolve_template(tpl: str, values: dict) -> str:
    out = tpl
    for key, val in values.items():
        out = out.replace("{%s}" % key, val)
    return out


def _dispatch(run_dir, runs, entries, pool_size, now) -> list[dict]:
    """Emit dispatch entries for queued runs while a pool slot is free.
    Guarded: a run already past queued is never re-dispatched.

    dispatch_mode == "subagent" (default): the entry carries a resolved
    ``worker_prompt`` for the orchestrator agent to launch via its
    subagent tool. dispatch_mode == "shell": the prompt is written to
    queue/job-NNNNN.prompt.txt (quoting/arg-length safety, FR-15) and the
    entry carries a resolved ``worker_cmd`` argv for the ticker to Popen
    detached; the placeholder block adds {PROMPT_FILE}."""
    inflight = sum(1 for r in runs.values() if r["state"] in _INFLIGHT_STATES)
    out: list[dict] = []
    for name in sorted(runs):
        r = runs[name]
        if r["state"] != "queued":
            continue
        if inflight >= pool_size:
            break
        entry = entries[name]
        mode = entry.get("dispatch_mode", "subagent")
        values = {
            "HEARTBEAT_PATH": str(_heartbeat_path(run_dir, name)),
            "TASK_ID": str(entry.get("task_id", "")),
            "RUN_DIR": str(run_dir / name),
            "TARGET_REPO": str(entry.get("target_repo", "")),
            "HARNESS_BIN": _HARNESS_BIN,
        }
        src = run_dir / "claimed" / (r["job_id"] + ".json")
        qsrc = run_dir / "queue" / (r["job_id"] + ".json")
        if qsrc.exists() and not src.exists():
            qsrc.replace(src)
            _write_json(run_dir / "claimed" / (r["job_id"] + ".lock"), {
                "task_id": r["task_id"],
                "claimed_ts": _utc_iso(),
                "dispatched_by": "qpb_harness_tick",
                "dispatch_mode": mode,
                "pid": None,
            })
        r["state"] = "claimed"
        r["claimed_at"] = now
        r["dispatch_mode"] = mode
        inflight += 1
        prompt = _resolve_template(entry.get("worker_prompt", ""), values)
        if mode == "shell":
            # Write the prompt to a file (quoting/arg-length safety) and
            # resolve the worker_cmd template; the ticker Popens it detached.
            prompt_file = run_dir / "queue" / (r["job_id"] + ".prompt.txt")
            prompt_file.write_text(prompt, encoding="utf-8")
            sh_values = dict(values, PROMPT_FILE=str(prompt_file))
            worker_cmd = [_resolve_template(tok, sh_values)
                          for tok in (entry.get("worker_cmd") or [])]
            out.append({
                "run": name, "task_id": r["task_id"],
                "dispatch_mode": "shell",
                "worker_cmd": worker_cmd,
                "prompt_file": str(prompt_file),
                "heartbeat_path": values["HEARTBEAT_PATH"],
                "run_dir": values["RUN_DIR"],
                "target_repo": values["TARGET_REPO"],
                "auth_check": entry.get("auth_check"),
            })
        else:
            out.append({
                "run": name, "task_id": r["task_id"],
                "dispatch_mode": "subagent",
                "worker_prompt": prompt,
            })
        _log(run_dir, f"{name}: dispatched (claimed, {mode})")
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


def _ascii_trunc(value, width: int) -> str:
    """Display-only: ASCII-sanitize (cp1252 console safety, NFR-7) and
    truncate a free-form field to the column width. The raw value is
    untouched on disk (FR-18)."""
    s = "-" if value is None else str(value)
    s = s.encode("ascii", "replace").decode("ascii")
    return s[:width]


def _format_table(run_dir, status, plan, terminal: bool) -> str:
    bar = "-" * 86
    # FR-21b: STATE narrowed + abbreviated (LAUNCH-FAIL) so it can't
    # overflow; ACTIVITY (the free-form label) widened and sanitized.
    fmt = "%-5s%-22s%-8s%-13s%-16s%-13s%s"
    rows = [
        "Run-Dir: %s (cycle %d)" % (run_dir.name, status.get("cycle", 0)),
        bar,
        fmt % ("RUN", "REPO", "MODE", "STATE", "ACTIVITY", "LAST-HB",
               "HB-AGE"),
    ]
    any_launch_fail = False
    for name in sorted(status["runs"]):
        r = status["runs"][name]
        _, _, activity, _ = _hb_observe(_heartbeat_path(run_dir, name))
        st = r["state"]
        if st == "auth_or_launch_failed":
            any_launch_fail = True
        rows.append(fmt % (
            name[4:],
            _ascii_trunc(r.get("target_repo") or "-", 21),
            {"subagent": "subgnt", "shell": "shell"}.get(
                r.get("dispatch_mode"), "-"),
            _STATE_DISPLAY.get(st, st)[:12],
            _ascii_trunc(activity, 15),
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
    if any_launch_fail:
        # FR-21b: the diagnostic hint travels with the table, not just the
        # result record — LAUNCH-FAIL covers more than auth.
        rows.append("LAUNCH-FAIL: " + _LAUNCH_FAIL_HINT + ".")
    if terminal:
        # ASCII only (no em-dash / box-drawing / arrows) — the status
        # table prints on Windows cp1252 consoles (185 print-path lesson).
        if status.get("done"):
            rows.append("DONE - all runs terminal. No further ticks.")
        else:
            rows.append("STOP - halting. No further ticks.")
    else:
        rows.append("Next tick in %d min" % _next_cadence(
            status, _cfg(plan, "tick_interval_minutes",
                         DEFAULT_TICK_INTERVAL_MINUTES),
            _cfg(plan, "idle_tick_multiplier", DEFAULT_IDLE_TICK_MULTIPLIER)))
    return "\n".join(rows)


_HARNESS_NAME = "qpb_harness_tick"
_HARNESS_SUMMARY = (
    "Advance the Quality Playbook harness state machine by one tick "
    "(deterministic; the orchestrator SKILL.md runs it per tick).")
_HARNESS_USAGE = "qpb_harness_tick (--init <plan-path> | <run-dir>)"


def _resolve_print_command_intro():
    """089x self-describing banner via the canonical bin/_purpose helper,
    3-step anchored. qpb_harness_tick lives directly in bin/ (orchestrator-
    side, not bundled), so the path-load anchor is this file's own dir."""
    try:
        from bin._purpose import print_command_intro as p  # type: ignore
        return p
    except ImportError:
        pass
    try:
        from _purpose import print_command_intro as p  # type: ignore[no-redef]
        return p
    except ImportError:
        pass
    import importlib.util as _ilu
    pp = Path(__file__).resolve().parent / "_purpose.py"
    spec = _ilu.spec_from_file_location("_qpb_harness_tick_purpose", pp)
    if spec is None or spec.loader is None:
        raise ImportError(f"qpb_harness_tick: cannot resolve _purpose at {pp}")
    mod = _ilu.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod.print_command_intro


def _print_intro() -> None:
    _resolve_print_command_intro()(
        name=_HARNESS_NAME,
        summary=_HARNESS_SUMMARY,
        role=(
            "v1.5.9 1B — the deterministic Python half of the harness-as-"
            "skill. `--init <plan>` scaffolds a run-dir; `<run-dir>` runs "
            "one tick (reads disk state, advances the state machine, prints "
            "the {dispatch_list,…} JSON the orchestrator agent acts on). "
            "Orchestrator-side; not bundled to adopter installs."),
        usage_hint=_HARNESS_USAGE,
    )


class _TickLock:
    """E1 (FR-12): a per-run-dir advisory lock that serializes concurrent
    tick processes (overlapping cron fires / a ticker + a manual --once).
    Non-blocking: ``acquired`` is False if another process holds it, and the
    caller skips the tick cleanly. Stdlib both platforms (fcntl / msvcrt)."""

    def __init__(self, run_dir: Path):
        self._path = run_dir / ".tick.lock"
        self._fh = None
        self.acquired = False

    def __enter__(self):
        try:
            self._fh = open(self._path, "a+")
        except OSError:
            self.acquired = True  # can't lock (read-only dir) — don't block
            return self
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.acquired = True
        except OSError:
            self.acquired = False
        return self

    def __exit__(self, *exc):
        if self._fh is not None:
            try:
                if self.acquired and os.name != "nt":
                    import fcntl
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
            self._fh.close()


def _locked_skip_output(run_dir: Path) -> dict:
    return {
        "dispatch_list": [],
        "status_table": ("Run-Dir: %s - another tick is already in progress; "
                         "this tick skipped cleanly (E1)." % run_dir.name),
        "next_tick_minutes": 1,
        "done": False,
        "stop": False,
        "skipped": True,
    }


def main(argv) -> int:
    args = list(argv[1:])
    if not args or args in (["-h"], ["--help"]):
        _print_intro()
        return 0
    if len(args) == 2 and args[0] == "--init":
        print(init_run(Path(args[1]).resolve()))
        return 0
    if len(args) == 1 and args[0] != "--init":
        run_dir = Path(args[0]).resolve()
        with _TickLock(run_dir) as lock:
            if not lock.acquired:
                print(json.dumps(_locked_skip_output(run_dir), indent=2))
                return 0
            print(json.dumps(tick(run_dir), indent=2))
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main(sys.argv))
