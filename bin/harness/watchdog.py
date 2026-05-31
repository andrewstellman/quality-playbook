"""v1.5.7 172: watchdog daemon — auto-spawned alongside the detached
collector. Polls the manifest for orphan runs (manifest says RUNNING,
pid dead on the system, stream.ndjson stale ≥ ``QPB_WATCHDOG_STALE_S``)
and fires :func:`collect_harness_run` under a file lock to self-heal.

The safety-net design: don't trust the collector to always be
correct. Run an independent process that audits and recovers. The
schedule-then-collect contract is end-to-end protected against
collector-side accounting bugs (165's one-shot retry, 171's
collected_indices misuse, and any future entries in the same family).

Lock semantics: ``<harness-run>/.collect.lock``. The watchdog
acquires ``LOCK_EX | LOCK_NB`` — if held it skips the tick. The
original collector acquires blocking ``LOCK_EX`` at the top of
:func:`bin.harness.plan_runner.collect_harness_run` and holds for
the run's lifetime; if the collector dies, the OS releases the lock
(FD close) and the watchdog's next tick can acquire and recovery-
collect.

POSIX-only — ``fcntl.flock``. Windows harness compatibility was
deferred earlier in v1.5.7.
"""
from __future__ import annotations

import fcntl
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import IO, Optional


_DEFAULT_INTERVAL_S = 60.0
_DEFAULT_STALE_S = 30.0


def _interval_s() -> float:
    """Watchdog poll interval. Env: ``QPB_WATCHDOG_INTERVAL_S``."""
    raw = os.environ.get("QPB_WATCHDOG_INTERVAL_S")
    if raw is None:
        return _DEFAULT_INTERVAL_S
    try:
        v = float(raw)
        return v if v > 0 else _DEFAULT_INTERVAL_S
    except (TypeError, ValueError):
        return _DEFAULT_INTERVAL_S


def _stale_s() -> float:
    """Stream-staleness threshold for orphan detection. Env:
    ``QPB_WATCHDOG_STALE_S``."""
    raw = os.environ.get("QPB_WATCHDOG_STALE_S")
    if raw is None:
        return _DEFAULT_STALE_S
    try:
        v = float(raw)
        return v if v > 0 else _DEFAULT_STALE_S
    except (TypeError, ValueError):
        return _DEFAULT_STALE_S


def _pid_alive(pid: int) -> bool:
    """True iff the pid responds to a 0-signal. POSIX."""
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _is_orphan(entry: dict, harness_run_dir: Path,
                stale_threshold_s: float) -> bool:
    """An entry is orphaned when:

    1. manifest still says RUNNING (no ``terminal_state``, state not
       in {DONE, ABORTED_PREP, ABANDONED_STARVED}); AND
    2. ``pid`` is non-None AND not alive on the system; AND
    3. ``stream.ndjson`` mtime is older than ``stale_threshold_s``
       (or the stream is missing entirely).

    The stream-staleness gate avoids racing the collector's own
    pid-death-then-grade window: a fresh stream means the AI-CLI
    may have just exited and the collector is mid-grade; don't fire
    a recovery collect on top of that.
    """
    if entry.get("terminal_state"):
        return False
    state = entry.get("state")
    if state in {"DONE", "ABORTED_PREP", "ABANDONED_STARVED"}:
        return False
    if state != "RUNNING":
        return False
    pid = entry.get("pid")
    if pid is None:
        return False
    try:
        pid_int = int(pid)
    except (TypeError, ValueError):
        return False
    if _pid_alive(pid_int):
        return False
    run_dir = harness_run_dir / Path(
        entry.get("run_dir", "")).name
    stream_path = run_dir / "stream.ndjson"
    if not stream_path.is_file():
        return True
    try:
        age = time.time() - stream_path.stat().st_mtime
    except OSError:
        return True
    return age >= stale_threshold_s


def _all_terminal(manifest: dict) -> bool:
    """True iff every run entry has a terminal_state OR state=DONE.

    The signal for the watchdog to exit cleanly — no work left to
    recover."""
    runs = manifest.get("runs", [])
    if not runs:
        return False
    for entry in runs:
        if entry.get("terminal_state"):
            continue
        if entry.get("state") == "DONE":
            continue
        return False
    return True


def _log(handle: "IO[str]", message: str) -> None:
    ts = datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")
    handle.write(f"[{ts}] {message}\n")
    handle.flush()


def run_watchdog(harness_run_dir: Path) -> int:
    """Main watchdog loop.

    Returns 2 on missing manifest, 0 on clean exit (all runs
    reached terminal state OR SIGTERM/SIGINT received).
    """
    manifest_path = harness_run_dir / "manifest.json"
    if not manifest_path.is_file():
        print(f"ERROR: no manifest.json under {harness_run_dir}",
              file=sys.stderr)
        return 2

    watchdog_pid_path = harness_run_dir / "watchdog.pid"
    watchdog_log_path = harness_run_dir / "watchdog.log"
    lock_path = harness_run_dir / ".collect.lock"

    watchdog_pid_path.write_text(str(os.getpid()),
                                  encoding="utf-8")
    log_fp = open(watchdog_log_path, "a", encoding="utf-8")

    interval = _interval_s()
    stale = _stale_s()

    _stop = [False]

    def _on_signal(signum, frame):  # noqa: ARG001
        _stop[0] = True

    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)

    _log(log_fp,
          f"watchdog started pid={os.getpid()} "
          f"interval={interval}s stale={stale}s")

    no_orphan_ticks = 0
    try:
        while not _stop[0]:
            # interruptible-ish sleep: chunked so SIGTERM lands fast.
            slept = 0.0
            while slept < interval and not _stop[0]:
                chunk = min(1.0, interval - slept)
                time.sleep(chunk)
                slept += chunk
            if _stop[0]:
                break
            try:
                manifest = json.loads(
                    manifest_path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                _log(log_fp, f"manifest read failed: {exc!r}")
                continue
            if _all_terminal(manifest):
                _log(log_fp,
                      "all runs terminal; watchdog exiting")
                break
            orphans = [
                entry for entry in manifest.get("runs", [])
                if _is_orphan(entry, harness_run_dir, stale)
            ]
            if not orphans:
                no_orphan_ticks += 1
                if no_orphan_ticks % 5 == 0:
                    _log(log_fp,
                          f"no orphans; sleeping "
                          f"(tick #{no_orphan_ticks})")
                continue
            no_orphan_ticks = 0
            orphan_names = [
                f"run-{e.get('index'):02d}" for e in orphans
            ]
            _log(log_fp,
                  f"orphan(s) detected: {orphan_names}; "
                  f"probing collect lock")
            # v1.5.7 172 FIX (FINDING-1): the LOCK_NB probe is a
            # "is collect busy?" check — don't HOLD it across the
            # collect_harness_run call. collect_harness_run
            # acquires its own LOCK_EX on the same .collect.lock
            # via a different FD; ``fcntl.flock`` is per open file
            # description, so two FDs in the same process count as
            # independent lock holders. Holding the probe lock here
            # would deadlock the collect_harness_run acquire
            # (blocking LOCK_EX waits for ALL holders to release,
            # including the same-process probe). Release the probe
            # immediately after the success path, then call collect
            # (which acquires its own blocking lock cleanly).
            busy = False
            try:
                with open(lock_path, "w",
                           encoding="utf-8") as probe_fp:
                    try:
                        fcntl.flock(
                            probe_fp.fileno(),
                            fcntl.LOCK_EX | fcntl.LOCK_NB)
                        # Probe succeeded — collect is free.
                        # Release immediately so the upcoming
                        # collect_harness_run call can acquire
                        # its own blocking LOCK_EX on a fresh FD
                        # without deadlocking against this probe.
                        fcntl.flock(
                            probe_fp.fileno(), fcntl.LOCK_UN)
                    except BlockingIOError:
                        busy = True
            except OSError as exc:
                _log(log_fp,
                      f"lock probe failed: {exc!r}")
                continue
            if busy:
                _log(log_fp,
                      "collect already in progress; "
                      "skipping this tick")
                continue
            # Lock was free at probe time. Tiny race window: another
            # process could grab .collect.lock between probe-release
            # and collect's acquire — harmless, collect just blocks
            # briefly until that holder finishes.
            try:
                from bin.harness.plan_runner import (
                    collect_harness_run)
                collect_harness_run(harness_run_dir)
                _log(log_fp, "recovery collect completed")
            except Exception as exc:
                _log(log_fp,
                      f"recovery collect failed: {exc!r}")
    finally:
        _log(log_fp, "watchdog exiting")
        log_fp.close()
        try:
            watchdog_pid_path.unlink()
        except OSError:
            pass
    return 0
