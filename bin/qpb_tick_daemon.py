"""qpb_tick_daemon — QPB harness sidecar wakeup daemon (v1.5.9).

Stdlib-only Python. Cross-platform (Unix + Windows). Runs as a
detached process; its single job is to fire the QPB harness skill
via ``claude --print`` (or equivalent host CLI) at the plan's
configured cadence.

The daemon holds zero AI context. It is a dumb wakeup clock with a
``subprocess.run`` attached. The harness skill, invoked fresh each
tick, performs all state-machine work. The daemon never reads or
writes ``harness_status.json``, the queue / claimed / results
directories, or the worker heartbeats.

Design reference:
  ``docs/design/QPB_v1.5.9_Harness_Skill_Design.md``
  § Tick-based execution + § Setup model + § Why a self-spawned
  daemon, not the Cowork scheduled-tasks MCP.

CLI:
  qpb_tick_daemon.py --run-dir <abs path>
                     --interval-minutes <N>
                     --claude-binary <path>
                     [--harness-plugin-dir <path>]

Env-var fallbacks (used when the matching CLI flag is omitted):
  QPB_RUN_DIR
  QPB_TICK_INTERVAL_MINUTES
  QPB_CLAUDE_BINARY
  QPB_HARNESS_PLUGIN_DIR

Lifecycle:

1. **PID-file lock.** Open ``<run-dir>/daemon.pid`` with
   ``O_CREAT | O_EXCL | O_WRONLY``. If the open fails with
   ``FileExistsError``, read the existing PID and check liveness
   via ``os.kill(pid, 0)``. If the PID is alive, exit code 7
   (another daemon owns this run-dir). If not alive, overwrite
   the stale PID file with our own.

2. **Detach.** Detachment is the responsibility of the SPAWN
   caller (the harness skill). On POSIX the harness uses
   ``subprocess.Popen(..., start-new-session)`` which
   invokes the POSIX setsid call in the child before exec.
   On Windows the harness uses
   ``creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP``.
   The daemon script itself just runs the wakeup loop -- the
   spawn-site comment block in SKILL.md is the IS_WINDOWS guard
   (the harness skill chooses one path or the other).
   # Windows-OK -- spawn-site dispatch happens in SKILL.md, not here.

3. **Signal handlers.** SIGTERM and SIGINT trigger a graceful
   shutdown: log the signal, remove the PID file, exit cleanly.

4. **Wakeup loop.** Each iteration:
     - Update mtime on ``<run-dir>/daemon.heartbeat``.
     - Check for ``<run-dir>/done.marker``. If present, log
       "done.marker present" and break (clean exit).
     - Invoke ``claude --print [--plugin-dir <path>]
       -p "tick harness on run-dir <run-dir>"`` with a timeout
       of ``interval_seconds * 0.9`` so a stuck tick can't jam
       the daemon.
     - On invocation success / timeout / error: log the outcome
       and continue. The state machine on disk is the source of
       truth; missing a single tick just delays the next state
       transition by ``interval_minutes``.
     - ``time.sleep(interval_seconds)``.

5. **Logging.** All daemon events (wake, tick fire, tick result,
   sleep, signal, shutdown) go to ``<run-dir>/daemon.log`` with
   ISO timestamps. The harness skill MAY read this log for
   diagnosis but does NOT depend on its content for state-machine
   decisions.

What the daemon does NOT do:
  - Read/write ``harness_status.json``, ``queue/``, ``claimed/``,
    ``results/``, ``heartbeat.ndjson``. Those are the harness
    skill's responsibility.
  - Make state-machine decisions.
  - Touch worker processes directly.
  - Sleep beyond ``interval_minutes`` regardless of conditions.
  - Write ``done.marker``. The harness writes it; the daemon
    only reads it as its exit signal.
"""
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# Exit codes (operator-facing — used by qpb_harness.py + the harness
# skill's spawn site to disambiguate failures from clean exits).
_EXIT_OK = 0
_EXIT_BAD_ARGS = 2
_EXIT_RUN_DIR_MISSING = 5
_EXIT_LOCK_HELD = 7

_DAEMON_NAME = "qpb_tick_daemon"
_DAEMON_SUMMARY = (
    "QPB harness sidecar wakeup daemon (v1.5.9)"
)
_DAEMON_ROLE = (
    "Fires the QPB harness skill via 'claude --print' at the "
    "plan's configured cadence. Detached process, zero AI "
    "context. Holds a PID-file lock per run-dir; exits cleanly "
    "when the harness writes done.marker."
)
_DAEMON_USAGE_HINT = (
    "python3 bin/qpb_tick_daemon.py --run-dir <abs path> "
    "--interval-minutes <N> --claude-binary <path>"
)


def _print_intro_minimal() -> None:
    """Self-describing no-args output (089x convention)."""
    try:
        from bin._purpose import print_command_intro
        print_command_intro(
            name=_DAEMON_NAME,
            summary=_DAEMON_SUMMARY,
            role=_DAEMON_ROLE,
            usage_hint=_DAEMON_USAGE_HINT,
        )
    except ImportError:
        print(f"{_DAEMON_NAME} -- {_DAEMON_SUMMARY}")
        print(_DAEMON_ROLE)
        print(f"Usage: {_DAEMON_USAGE_HINT}")


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(log_path: Path, msg: str) -> None:
    """Append a single ISO-timestamped line to daemon.log.
    Best-effort — a broken log must not break the wakeup loop."""
    try:
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(f"{_iso_now()} {msg}\n")
            fh.flush()
    except OSError:
        pass


def _pid_alive(pid: int) -> bool:
    """True iff sending signal 0 to ``pid`` does not raise
    ProcessLookupError. On Windows, os.kill with signal 0 raises
    OSError(EINVAL) for live processes — handle by treating any
    non-ProcessLookupError exception as 'alive' (conservative)."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # The process exists but we lack permission to signal it.
        # That still means "alive" for liveness purposes.
        return True
    except OSError:
        # Other OSError (e.g. Windows EINVAL on live process) —
        # conservatively assume alive.
        return True


def _acquire_pid_lock(
    pid_path: Path, log_path: Path,
) -> Optional[int]:
    """Acquire the PID-file lock. Returns 0 on success, or an exit
    code (7) on lock-held-by-live-PID failure. Overwrites stale PID
    files (PID not alive)."""
    my_pid = os.getpid()
    try:
        # O_CREAT | O_EXCL | O_WRONLY — atomic create-or-fail.
        fd = os.open(
            str(pid_path),
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            0o644,
        )
        try:
            os.write(fd, f"{my_pid}\n".encode("ascii"))
        finally:
            os.close(fd)
        _log(log_path, f"daemon spawn pid={my_pid} run_dir={pid_path.parent}")
        return _EXIT_OK
    except FileExistsError:
        pass
    # Lock file exists — read existing PID and check liveness.
    try:
        existing_raw = pid_path.read_text(encoding="utf-8").strip()
        existing_pid = int(existing_raw)
    except (OSError, ValueError):
        existing_pid = -1
    if existing_pid > 0 and _pid_alive(existing_pid):
        _log(
            log_path,
            f"daemon spawn refused pid={my_pid}: "
            f"existing PID {existing_pid} is alive in "
            f"{pid_path}",
        )
        sys.stderr.write(
            f"qpb_tick_daemon: lock held — PID {existing_pid} "
            f"alive at {pid_path}. Exiting.\n",
        )
        return _EXIT_LOCK_HELD
    # Stale PID — overwrite.
    _log(
        log_path,
        f"daemon spawn pid={my_pid}: overwriting stale PID "
        f"file (was {existing_pid})",
    )
    try:
        pid_path.write_text(f"{my_pid}\n", encoding="utf-8")
        return _EXIT_OK
    except OSError as exc:
        _log(log_path, f"daemon spawn FAILED to write PID file: {exc}")
        sys.stderr.write(
            f"qpb_tick_daemon: could not overwrite stale PID "
            f"file {pid_path}: {exc}\n",
        )
        return _EXIT_LOCK_HELD


def _remove_pid_file(pid_path: Path, log_path: Path) -> None:
    """Best-effort PID file removal. Safe to call multiple times."""
    try:
        pid_path.unlink()
        _log(log_path, "PID file removed")
    except FileNotFoundError:
        pass
    except OSError as exc:
        _log(log_path, f"PID file removal failed: {exc}")


def _install_signal_handlers(
    pid_path: Path, log_path: Path,
) -> None:
    """Install SIGTERM / SIGINT handlers for graceful exit."""

    def _handler(signum, _frame):
        signame = {
            signal.SIGTERM: "SIGTERM",
            signal.SIGINT: "SIGINT",
        }.get(signum, f"signal {signum}")
        _log(log_path, f"received {signame}; shutting down gracefully")
        _remove_pid_file(pid_path, log_path)
        sys.exit(_EXIT_OK)

    try:
        signal.signal(signal.SIGTERM, _handler)
    except (ValueError, OSError):
        # Not in main thread or unsupported — best-effort.
        pass
    try:
        signal.signal(signal.SIGINT, _handler)
    except (ValueError, OSError):
        pass


def _fire_tick(
    claude_binary: str,
    run_dir: Path,
    harness_plugin_dir: Optional[Path],
    timeout_seconds: float,
    log_path: Path,
) -> None:
    """Fire one ``claude --print`` tick. Best-effort: log success /
    timeout / error and return."""
    cmd = [claude_binary, "--print"]
    if harness_plugin_dir is not None:
        cmd.extend(["--plugin-dir", str(harness_plugin_dir)])
    cmd.extend(["-p", f"tick harness on run-dir {run_dir}"])
    _log(log_path, f"tick fire: cmd={' '.join(cmd)} timeout={timeout_seconds:.1f}s")
    try:
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            timeout=timeout_seconds,
            check=False,
        )
        _log(
            log_path,
            f"tick result: rc={proc.returncode} "
            f"stdout_bytes={len(proc.stdout)} "
            f"stderr_bytes={len(proc.stderr)}",
        )
    except subprocess.TimeoutExpired:
        _log(log_path, f"tick TIMEOUT after {timeout_seconds:.1f}s")
    except FileNotFoundError:
        _log(log_path, f"tick FAILED: claude binary not found at {claude_binary}")
    except OSError as exc:
        _log(log_path, f"tick FAILED: {exc}")


def _run_daemon(
    run_dir: Path,
    interval_minutes: float,
    claude_binary: str,
    harness_plugin_dir: Optional[Path],
) -> int:
    """The wakeup loop. Returns the process exit code."""
    pid_path = run_dir / "daemon.pid"
    log_path = run_dir / "daemon.log"
    heartbeat_path = run_dir / "daemon.heartbeat"
    done_marker = run_dir / "done.marker"

    interval_seconds = max(interval_minutes * 60.0, 1.0)
    # Tick timeout: 90% of the interval (so a stuck tick can't
    # jam the next wake).
    tick_timeout = max(interval_seconds * 0.9, 1.0)

    rc = _acquire_pid_lock(pid_path, log_path)
    if rc != _EXIT_OK:
        return rc
    _install_signal_handlers(pid_path, log_path)

    _log(
        log_path,
        f"daemon loop starting interval={interval_minutes}min "
        f"claude_binary={claude_binary} "
        f"harness_plugin_dir={harness_plugin_dir}",
    )

    try:
        while True:
            # Heartbeat: update mtime so the harness can detect a
            # dead daemon via mtime-age on subsequent operator-
            # manual invocations.
            try:
                heartbeat_path.touch(exist_ok=True)
            except OSError as exc:
                _log(log_path, f"heartbeat touch failed: {exc}")

            if done_marker.exists():
                _log(
                    log_path,
                    "done.marker present -- daemon exiting cleanly",
                )
                break

            _fire_tick(
                claude_binary,
                run_dir,
                harness_plugin_dir,
                tick_timeout,
                log_path,
            )

            _log(log_path, f"sleep {interval_seconds:.1f}s")
            time.sleep(interval_seconds)
    except Exception as exc:  # pragma: no cover -- defensive
        _log(log_path, f"daemon loop CRASHED: {exc!r}")
        _remove_pid_file(pid_path, log_path)
        return 1

    _remove_pid_file(pid_path, log_path)
    _log(log_path, "daemon exited cleanly")
    return _EXIT_OK


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qpb_tick_daemon",
        description=(
            "QPB harness sidecar wakeup daemon (v1.5.9). "
            "Fires the harness skill at a fixed interval. "
            "See SKILL.md for spawn instructions."
        ),
    )
    parser.add_argument(
        "--run-dir",
        type=str,
        default=os.environ.get("QPB_RUN_DIR"),
        help=(
            "Absolute path to the harness run-dir "
            "(harness_runs/<ts>/). Required. Env var: "
            "QPB_RUN_DIR."
        ),
    )
    parser.add_argument(
        "--interval-minutes",
        type=float,
        default=float(
            os.environ.get("QPB_TICK_INTERVAL_MINUTES", "0") or 0,
        ),
        help=(
            "Wake interval in minutes. Required. Env var: "
            "QPB_TICK_INTERVAL_MINUTES. Fractional values are "
            "allowed (e.g. 0.033 for ~2-sec test pace)."
        ),
    )
    parser.add_argument(
        "--claude-binary",
        type=str,
        default=os.environ.get("QPB_CLAUDE_BINARY"),
        help=(
            "Path to the claude CLI binary. Required. Env var: "
            "QPB_CLAUDE_BINARY."
        ),
    )
    parser.add_argument(
        "--harness-plugin-dir",
        type=str,
        default=os.environ.get("QPB_HARNESS_PLUGIN_DIR"),
        help=(
            "Optional --plugin-dir argument forwarded to "
            "claude --print. Env var: QPB_HARNESS_PLUGIN_DIR."
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

    if not args.run_dir:
        sys.stderr.write("ERROR: --run-dir is required\n")
        return _EXIT_BAD_ARGS
    if args.interval_minutes <= 0:
        sys.stderr.write(
            "ERROR: --interval-minutes must be > 0\n",
        )
        return _EXIT_BAD_ARGS
    if not args.claude_binary:
        sys.stderr.write("ERROR: --claude-binary is required\n")
        return _EXIT_BAD_ARGS

    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.is_dir():
        sys.stderr.write(
            f"ERROR: run-dir not found: {run_dir}\n",
        )
        return _EXIT_RUN_DIR_MISSING

    harness_plugin_dir = None
    if args.harness_plugin_dir:
        harness_plugin_dir = (
            Path(args.harness_plugin_dir).expanduser().resolve()
        )

    return _run_daemon(
        run_dir=run_dir,
        interval_minutes=args.interval_minutes,
        claude_binary=args.claude_binary,
        harness_plugin_dir=harness_plugin_dir,
    )


if __name__ == "__main__":
    sys.exit(main())
