#!/usr/bin/env python3
"""harness_ticker — foreground / one-shot tick driver (v1.5.9 Phase 2B).

The cadence rung-3 and rung-4 substrate (FR-24): when there is no in-session
scheduling primitive (rung 1) and no OS scheduler rights (rung 2), this
plain stdlib script drives the plan from a single terminal window — THE
no-admin floor for locked-down hosts (UC-5). It replaces the orchestrator
agent: each tick it runs the deterministic tick engine, spawns any shell
dispatches the engine lists (detached, platform-appropriate), records their
PIDs in the claim locks, prints the status table, and either sleeps the
cadence and loops (loop mode) or exits (--once).

Modes:
  harness_ticker.py <plan.json>     loop: --init then tick -> spawn -> sleep
                                    -> repeat until done/stop. (rung 3)
  harness_ticker.py <run-dir>       loop against an existing run (resume).
  harness_ticker.py --once <run-dir>  a single tick (the cron target /
                                    manual floor — rungs 2 and 4).

HONEST semantics (NFR-8), also printed in --help:
  * Loop mode: the window must stay OPEN for the plan's duration — the same
    constraint a rung-1 agent session has. If you CLOSE the window, in-flight
    child workers may die with it; rerun the ticker to resume (state is on
    disk, re-detected from heartbeats + PID locks).
  * Workers are dispatch_mode:"shell" only — an externally-ticked context
    can't launch in-session subagents. A subagent-mode entry is reported and
    skipped with the rung-1 instruction.
  * Every exit-without-done prints the exact command to continue the run in
    another window (FR-25) — the floor is always one copy-paste away.

Stdlib only. Cross-platform (NFR-1/3). ASCII-safe output (NFR-7).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import time
from pathlib import Path


_SYNCED_PATTERNS = ("onedrive", "dropbox", "google drive", "googledrive",
                    "icloud", "box sync")


def _load_engine():
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(
        "_harness_tick_engine", here / "qpb_harness_tick.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_harness_tick_engine"] = mod
    spec.loader.exec_module(mod)
    return mod


def _floor_command(run_dir: Path) -> str:
    return ("python3 %s --once %s"
            % (str(Path(__file__).resolve()), str(run_dir)))


def _warn_synced_folder(run_dir: Path) -> None:
    low = str(run_dir).lower()
    if any(p in low for p in _SYNCED_PATTERNS):
        print("WARNING (E4): the run-dir looks like a synced folder (%s). "
              "Sync clients can corrupt the append-only state; put run-dirs "
              "on plain local disk." % run_dir, file=sys.stderr)


def _resolve_run_dir(engine, arg: str) -> Path:
    """A directory with harness_status.json is an existing run-dir; a .json
    file is a plan to --init."""
    p = Path(arg).resolve()
    if p.is_dir() and (p / "harness_status.json").is_file():
        return p
    if p.is_file() and p.suffix == ".json":
        return Path(engine.init_run(p))
    print("harness_ticker: argument must be a plan .json or an existing "
          "run-dir (a dir with harness_status.json). Got: %s" % arg,
          file=sys.stderr)
    sys.exit(2)


def _detach_kwargs() -> dict:
    if os.name == "nt":
        flags = 0
        for attr in ("DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP"):
            flags |= getattr(subprocess, attr, 0)
        return {"creationflags": flags} if flags else {}
    return {"start_new_session": True}


def _record_pid(run_dir: Path, run_name: str, pid) -> None:
    # run-NN -> job-NNNNN: the lock is keyed by job id; derive it from the
    # run index so the engine's _lock_pid finds the PID (A-5).
    job_id = "job-%05d" % int(run_name.split("-")[1])
    lock = run_dir / "claimed" / (job_id + ".lock")
    try:
        data = json.loads(lock.read_text(encoding="utf-8", errors="replace")) \
            if lock.is_file() else {}
    except (OSError, ValueError):
        data = {}
    data["pid"] = pid
    tmp = lock.with_suffix(".lock.tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(lock)


def _fail_entry(entry: dict, reason: str) -> None:
    """Write a FAILED terminal heartbeat for an entry the ticker could not
    launch (auth/spawn failure), so the next tick reaps it failed with an
    actionable message rather than waiting out the launch grace (FR-16)."""
    hb = entry.get("heartbeat_path")
    if not hb:
        return
    H = _load_heartbeat()
    try:
        H.append_line(Path(hb), H.build_terminal(
            task_id=entry.get("task_id", ""), status="FAILED",
            result_file="", summary=reason))
    except Exception:
        pass


_HEARTBEAT_MOD = None


def _load_heartbeat():
    global _HEARTBEAT_MOD
    if _HEARTBEAT_MOD is None:
        here = Path(__file__).resolve().parent
        spec = importlib.util.spec_from_file_location(
            "_harness_heartbeat_ticker", here / "harness_heartbeat.py")
        _HEARTBEAT_MOD = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_HEARTBEAT_MOD)
    return _HEARTBEAT_MOD


def _auth_ok(auth_check, cache) -> bool:
    """Run a cheap per-CLI auth/availability pre-flight once (FR-16).
    Cached by the argv tuple so it runs once per distinct CLI."""
    key = tuple(auth_check)
    if key in cache:
        return cache[key]
    try:
        rc = subprocess.run(list(auth_check), stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            timeout=60).returncode
        ok = (rc == 0)
    except (OSError, subprocess.SubprocessError):
        ok = False
    cache[key] = ok
    return ok


def _spawn_dispatches(run_dir: Path, dispatch_list, auth_cache) -> None:
    for entry in dispatch_list:
        mode = entry.get("dispatch_mode", "subagent")
        if mode != "shell":
            print("  NOTE: %s is dispatch_mode '%s' — the ticker only launches "
                  "shell workers. Use cadence rung 1 (an agent session) for "
                  "subagent dispatch, or set dispatch_mode:'shell'."
                  % (entry.get("run"), mode), file=sys.stderr)
            continue
        auth_check = entry.get("auth_check")
        if auth_check and not _auth_ok(auth_check, auth_cache):
            print("  AUTH_OR_LAUNCH_FAILED: %s — auth pre-flight (%s) failed; "
                  "is the CLI installed and logged in?"
                  % (entry.get("run"), " ".join(auth_check)), file=sys.stderr)
            _fail_entry(entry, "auth pre-flight failed: %s" % " ".join(auth_check))
            continue
        env = dict(os.environ)
        env["HARNESS_HEARTBEAT_PATH"] = entry.get("heartbeat_path", "")
        env["HARNESS_TASK_ID"] = entry.get("task_id", "")
        env["HARNESS_RUN_DIR"] = entry.get("run_dir", "")
        env["HARNESS_TARGET_REPO"] = entry.get("target_repo", "")
        try:
            proc = subprocess.Popen(
                entry["worker_cmd"], stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=env, cwd=str(run_dir), **_detach_kwargs())
            _record_pid(run_dir, entry["run"], proc.pid)
            print("  spawned %s (pid %d): %s"
                  % (entry["run"], proc.pid, " ".join(entry["worker_cmd"][:3]) + " ..."))
        except (OSError, ValueError) as exc:
            print("  AUTH_OR_LAUNCH_FAILED: %s — spawn failed (%s)"
                  % (entry.get("run"), exc), file=sys.stderr)
            _fail_entry(entry, "spawn failed: %s" % exc)


def _one_tick(engine, run_dir: Path, auth_cache) -> dict:
    """Take the E1 lock, run one engine tick, spawn its shell dispatches."""
    with engine._TickLock(run_dir) as lock:
        if not lock.acquired:
            out = engine._locked_skip_output(run_dir)
            print(out["status_table"])
            return out
        out = engine.tick(run_dir)
        _spawn_dispatches(run_dir, out.get("dispatch_list", []), auth_cache)
        print(out["status_table"])
        return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="harness_ticker",
                                 description=__doc__.split("\n")[0],
                                 epilog=__doc__)
    ap.add_argument("target", help="a plan .json (loop) or a run-dir")
    ap.add_argument("--once", action="store_true",
                    help="run exactly one tick and exit (cron target / floor)")
    ap.add_argument("--interval", type=float, default=None,
                    help="override sleep seconds between ticks (default: the "
                         "plan's tick_interval_minutes); for testing")
    ap.add_argument("--max-ticks", type=int, default=None,
                    help="stop after N ticks (testing safety bound)")
    args = ap.parse_args(list(sys.argv[1:] if argv is None else argv))

    engine = _load_engine()
    run_dir = _resolve_run_dir(engine, args.target)
    _warn_synced_folder(run_dir)
    auth_cache: dict = {}

    if args.once:
        out = _one_tick(engine, run_dir, auth_cache)
        if not (out.get("done") or out.get("stop")):
            print("\nTo continue this run, execute:\n  %s"
                  % _floor_command(run_dir))
        return 0

    ticks = 0
    try:
        while True:
            out = _one_tick(engine, run_dir, auth_cache)
            ticks += 1
            if out.get("done"):
                print("DONE - all runs terminal.")
                return 0
            if out.get("stop"):
                print("STOP - halting.")
                return 0
            if args.max_ticks is not None and ticks >= args.max_ticks:
                print("\n--max-ticks reached. To continue, execute:\n  %s"
                      % _floor_command(run_dir))
                return 0
            sleep_s = (args.interval if args.interval is not None
                       else float(out.get("next_tick_minutes", 10)) * 60)
            time.sleep(max(0.0, sleep_s))
    except KeyboardInterrupt:
        print("\nInterrupted. To continue this run, execute:\n  %s"
              % _floor_command(run_dir))
        return 0


if __name__ == "__main__":
    sys.exit(main())
