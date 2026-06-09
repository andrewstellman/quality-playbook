"""qpb_harness — QPB harness operator CLI (v1.5.9 daemon mode).

Operator-facing CLI for managing the v1.5.9 harness sidecar
daemon (``bin/qpb_tick_daemon.py``). Three commands:

    qpb_harness.py status
        Walk ``harness_runs/*/daemon.pid``. For each, read PID,
        check liveness via ``os.kill(pid, 0)``, report
        ``<run-dir>: PID <N> [alive|stale]`` and the
        ``daemon.heartbeat`` mtime age.

    qpb_harness.py stop <run-dir>
        Read PID from ``<run-dir>/daemon.pid``, send SIGTERM,
        wait up to 5 sec, then SIGKILL if still alive. Remove
        the PID file. Useful for "stop this run."

    qpb_harness.py gc
        Sweep ``harness_runs/*/daemon.pid``. For each, remove the
        PID file when the PID is not alive OR ``done.marker``
        exists OR the heartbeat mtime is older than 3x the
        observed tick interval. Useful for cleaning up after
        crashes / forgotten runs.

Exit codes (instruction 213 § H2 detail):

    0  normal completion (including gc/status with nothing to do)
    2  bad invocation
    5  run-dir not found (for ``stop``)
    7  PID file present but PID not alive (``stop`` -- gc would
       have caught it)

This replaces the legacy v1.5.7 ``bin/qpb_harness.py`` (renamed
to ``bin/qpb_harness_legacy.py`` for the v1.5.9 buffer period;
the legacy module + the ``bin/harness/`` library it depends on
are scheduled for deletion after the v1.5.9 release tag).

Design reference:
  ``docs/design/QPB_v1.5.9_Harness_Skill_Design.md`` § Setup
  model + the H2 detail in instruction 213.
"""
from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional


_EXIT_OK = 0
_EXIT_BAD_ARGS = 2
_EXIT_RUN_DIR_MISSING = 5
_EXIT_PID_STALE = 7

_HARNESS_CLI_NAME = "qpb_harness"
_HARNESS_CLI_SUMMARY = (
    "QPB harness operator CLI (v1.5.9 daemon mode)"
)
_HARNESS_CLI_ROLE = (
    "Manage the v1.5.9 sidecar daemon lifecycle: list active "
    "daemons (status), terminate a specific run (stop), sweep "
    "stale PID files (gc). Replaces the legacy v1.5.7 launcher "
    "CLI; the legacy module lives at bin/qpb_harness_legacy.py "
    "during the buffer period and is scheduled for deletion "
    "after the v1.5.9 release tag."
)
_HARNESS_CLI_USAGE_HINT = (
    "python3 bin/qpb_harness.py status | "
    "stop <run-dir> | gc [--runs-root <dir>]"
)


def _print_intro_minimal() -> None:
    """Self-describing no-args output (089x convention)."""
    try:
        from bin._purpose import print_command_intro
        print_command_intro(
            name=_HARNESS_CLI_NAME,
            summary=_HARNESS_CLI_SUMMARY,
            role=_HARNESS_CLI_ROLE,
            usage_hint=_HARNESS_CLI_USAGE_HINT,
        )
    except ImportError:
        print(f"{_HARNESS_CLI_NAME} -- {_HARNESS_CLI_SUMMARY}")
        print(_HARNESS_CLI_ROLE)
        print(f"Usage: {_HARNESS_CLI_USAGE_HINT}")


def _default_runs_root() -> Path:
    """The v1.5.9 convention: ``./harness_runs/`` from cwd."""
    return Path("harness_runs")


def _pid_alive(pid: int) -> bool:
    """True iff sending signal 0 to ``pid`` does not raise
    ProcessLookupError. Mirrors qpb_tick_daemon._pid_alive."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return True


def _read_pid(pid_path: Path) -> Optional[int]:
    """Read a single integer PID from a daemon.pid file. Returns
    None if the file is missing / malformed."""
    try:
        raw = pid_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _heartbeat_age_seconds(
    heartbeat_path: Path,
) -> Optional[float]:
    """Return wall-clock age of the daemon.heartbeat file in
    seconds, or None if the file is missing."""
    try:
        stat = heartbeat_path.stat()
    except OSError:
        return None
    return max(0.0, time.time() - stat.st_mtime)


def _iter_daemon_pids(
    runs_root: Path,
) -> list[tuple[Path, Path]]:
    """Yield ``(run_dir, pid_path)`` tuples for every
    ``<runs-root>/*/daemon.pid`` file. Returns empty list if
    runs-root doesn't exist."""
    if not runs_root.is_dir():
        return []
    results: list[tuple[Path, Path]] = []
    for child in sorted(runs_root.iterdir()):
        if not child.is_dir():
            continue
        pid_path = child / "daemon.pid"
        if pid_path.is_file():
            results.append((child, pid_path))
    return results


def _cmd_status(args: argparse.Namespace) -> int:
    """List every active daemon (PID file present) under
    runs-root."""
    runs_root = (
        Path(args.runs_root).expanduser().resolve()
        if args.runs_root
        else _default_runs_root().resolve()
    )
    entries = _iter_daemon_pids(runs_root)
    if not entries:
        print(
            f"No daemon.pid files under {runs_root}",
            file=sys.stderr,
        )
        return _EXIT_OK
    print(f"runs-root: {runs_root}")
    print(
        "run-dir                                "
        "pid      state    heartbeat-age",
    )
    for run_dir, pid_path in entries:
        pid = _read_pid(pid_path)
        if pid is None:
            state = "bad-pid"
            pid_display = "?"
        else:
            state = "alive" if _pid_alive(pid) else "stale"
            pid_display = str(pid)
        age = _heartbeat_age_seconds(
            run_dir / "daemon.heartbeat",
        )
        if age is None:
            age_display = "(no heartbeat)"
        elif age < 60:
            age_display = f"{age:.0f}s"
        elif age < 3600:
            age_display = f"{age / 60:.1f}m"
        else:
            age_display = f"{age / 3600:.1f}h"
        run_name = run_dir.name
        print(
            f"{run_name:<40} {pid_display:<8} "
            f"{state:<8} {age_display}",
        )
    return _EXIT_OK


def _cmd_stop(args: argparse.Namespace) -> int:
    """Send SIGTERM (then SIGKILL after 5 sec) to the daemon
    owning ``<run-dir>/daemon.pid``. Remove the PID file after
    termination."""
    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.is_dir():
        sys.stderr.write(
            f"ERROR: run-dir not found: {run_dir}\n",
        )
        return _EXIT_RUN_DIR_MISSING
    pid_path = run_dir / "daemon.pid"
    if not pid_path.is_file():
        sys.stderr.write(
            f"No daemon.pid in {run_dir}; nothing to stop.\n",
        )
        return _EXIT_OK
    pid = _read_pid(pid_path)
    if pid is None:
        sys.stderr.write(
            f"ERROR: {pid_path} is malformed; removing.\n",
        )
        try:
            pid_path.unlink()
        except OSError:
            pass
        return _EXIT_PID_STALE
    if not _pid_alive(pid):
        sys.stderr.write(
            f"PID {pid} is not alive; removing stale PID "
            f"file (gc would have caught this).\n",
        )
        try:
            pid_path.unlink()
        except OSError:
            pass
        return _EXIT_PID_STALE

    # Send SIGTERM, wait up to 5 sec, escalate to SIGKILL.
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        sys.stderr.write(
            f"ERROR: SIGTERM to PID {pid} failed: {exc}\n",
        )
        return _EXIT_OK
    print(f"Sent SIGTERM to PID {pid}; waiting up to 5s...")
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        if not _pid_alive(pid):
            print(f"PID {pid} exited cleanly.")
            break
        time.sleep(0.2)
    else:
        # SIGKILL escalation.
        kill_sig = getattr(signal, "SIGKILL", None)
        if kill_sig is None:
            # Windows fallback: SIGTERM was already sent;
            # try TerminateProcess via os.kill again.
            kill_sig = signal.SIGTERM
        try:
            os.kill(pid, kill_sig)
            print(
                f"PID {pid} did not exit within 5s; sent "
                f"{'SIGKILL' if kill_sig != signal.SIGTERM else 'SIGTERM(again)'}.",
            )
        except OSError as exc:
            sys.stderr.write(
                f"ERROR: kill escalation failed: {exc}\n",
            )

    try:
        pid_path.unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        sys.stderr.write(
            f"WARNING: could not remove {pid_path}: {exc}\n",
        )
    return _EXIT_OK


def _max_known_interval_seconds(run_dir: Path) -> float:
    """Best-effort: read ``plan.json`` and return
    ``tick_interval_minutes * 60``. Defaults to 600 sec (10 min)
    if anything fails."""
    plan_path = run_dir / "plan.json"
    if not plan_path.is_file():
        return 600.0
    try:
        import json
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        interval = float(plan.get("tick_interval_minutes", 10))
        return max(interval * 60.0, 60.0)
    except (OSError, ValueError):
        return 600.0


def _cmd_gc(args: argparse.Namespace) -> int:
    """Sweep stale PID files across runs-root."""
    runs_root = (
        Path(args.runs_root).expanduser().resolve()
        if args.runs_root
        else _default_runs_root().resolve()
    )
    entries = _iter_daemon_pids(runs_root)
    if not entries:
        print(
            f"No daemon.pid files under {runs_root}; nothing "
            f"to gc.",
            file=sys.stderr,
        )
        return _EXIT_OK
    removed: list[Path] = []
    kept: list[Path] = []
    for run_dir, pid_path in entries:
        pid = _read_pid(pid_path)
        done_marker = run_dir / "done.marker"
        heartbeat_age = _heartbeat_age_seconds(
            run_dir / "daemon.heartbeat",
        )
        max_interval = _max_known_interval_seconds(run_dir)
        stale_threshold = max_interval * 3.0
        should_remove = False
        reason = ""
        if pid is None or not _pid_alive(pid):
            should_remove = True
            reason = f"PID {pid!r} not alive"
        elif done_marker.exists():
            should_remove = True
            reason = "done.marker present"
        elif (
            heartbeat_age is not None
            and heartbeat_age > stale_threshold
        ):
            should_remove = True
            reason = (
                f"heartbeat age {heartbeat_age:.0f}s > "
                f"{stale_threshold:.0f}s "
                f"(3x {max_interval / 60:.1f}min interval)"
            )
        if should_remove:
            try:
                pid_path.unlink()
                removed.append(pid_path)
                print(
                    f"REMOVED {pid_path}: {reason}",
                )
            except OSError as exc:
                sys.stderr.write(
                    f"WARNING: could not remove "
                    f"{pid_path}: {exc}\n",
                )
        else:
            kept.append(pid_path)
            print(
                f"kept    {pid_path}: PID {pid} alive, "
                f"no done.marker, heartbeat fresh",
            )
    print(
        f"\nsummary: removed={len(removed)} kept={len(kept)}",
    )
    return _EXIT_OK


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qpb_harness",
        description=(
            "QPB harness operator CLI (v1.5.9 daemon mode). "
            "See SKILL.md for the full lifecycle."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=False)

    status_p = sub.add_parser(
        "status",
        help="List every active daemon under runs-root.",
    )
    status_p.add_argument(
        "--runs-root",
        type=str,
        default=None,
        help=(
            "Override the default ./harness_runs/ root."
        ),
    )

    stop_p = sub.add_parser(
        "stop",
        help="SIGTERM (then SIGKILL after 5s) the daemon for "
             "a specific run-dir.",
    )
    stop_p.add_argument(
        "run_dir",
        type=str,
        help="Absolute or relative path to the run-dir.",
    )

    gc_p = sub.add_parser(
        "gc",
        help="Sweep stale daemon.pid files across runs-root.",
    )
    gc_p.add_argument(
        "--runs-root",
        type=str,
        default=None,
        help=(
            "Override the default ./harness_runs/ root."
        ),
    )

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        _print_intro_minimal()
        return _EXIT_OK
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "status":
        return _cmd_status(args)
    if args.cmd == "stop":
        return _cmd_stop(args)
    if args.cmd == "gc":
        return _cmd_gc(args)
    parser.print_help(sys.stderr)
    return _EXIT_BAD_ARGS


if __name__ == "__main__":
    sys.exit(main())
