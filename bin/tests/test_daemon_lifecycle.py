"""v1.5.9 instruction 213 H12 — daemon lifecycle tests.

Stdlib-only pytest. Covers:

1. Daemon starts, writes PID file with a valid integer, writes
   heartbeat file, sleeps the configured interval.
2. After done.marker is written, daemon exits within 2 x interval
   and removes PID file.
3. Daemon refuses to start if PID file exists AND PID is alive
   (exits with code 7, no PID file modification).
4. Daemon overwrites stale PID file if PID is not alive.
5. SIGTERM during sleep causes graceful exit + PID cleanup + log
   entry.

For test pace, the daemon is spawned with --interval-minutes 0.04
(~2.4 sec) and a stub claude binary that exits immediately. The
state machine on disk is the source of truth; we observe the
daemon's PID-file + heartbeat + log behavior, not the tick
content.
"""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[2]
DAEMON_PY = REPO_ROOT / "bin" / "qpb_tick_daemon.py"


def _make_stub_claude(run_dir: Path) -> Path:
    """Write a stub `claude` binary into ``run_dir`` that exits
    cleanly. The daemon doesn't care about output — it just logs the
    exit code."""
    stub_path = run_dir / "stub_claude.sh"
    stub_path.write_text(
        "#!/bin/sh\nexit 0\n",
        encoding="utf-8",
    )
    stub_path.chmod(0o755)
    return stub_path


def _spawn_daemon(
    run_dir: Path,
    interval_minutes: float = 0.04,
    claude_binary: "Path | None" = None,
) -> subprocess.Popen:
    """Launch the daemon as a child process. Uses
    ``start_new_session=True`` (Unix only — tests are POSIX-only)
    to mirror the harness's spawn path."""
    if claude_binary is None:
        claude_binary = _make_stub_claude(run_dir)
    cmd = [
        sys.executable, str(DAEMON_PY),
        "--run-dir", str(run_dir),
        "--interval-minutes", str(interval_minutes),
        "--claude-binary", str(claude_binary),
    ]
    return subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


def _wait_for_file(
    path: Path,
    timeout_seconds: float = 10.0,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if path.exists():
            return True
        time.sleep(0.05)
    return False


def _wait_for_no_file(
    path: Path,
    timeout_seconds: float = 10.0,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if not path.exists():
            return True
        time.sleep(0.05)
    return False


def _wait_for_pid_exit(
    pid: int,
    timeout_seconds: float = 10.0,
    proc: "subprocess.Popen | None" = None,
) -> bool:
    """Wait until ``pid`` is no longer alive. When ``proc`` is
    supplied (a Popen handle owning the child), the function also
    reaps the zombie via ``proc.poll()`` — otherwise ``os.kill(pid,
    0)`` would return success against the zombie slot, causing a
    false-negative."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if proc is not None:
            if proc.poll() is not None:
                return True
        else:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return True
        time.sleep(0.05)
    return False


def _read_pid(pid_path: Path) -> "int | None":
    try:
        return int(pid_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


class DaemonLifecycleTests(unittest.TestCase):
    """Five cases per instruction 213 § H12."""

    def setUp(self) -> None:
        self._tmpdir_ctx = TemporaryDirectory(
            prefix="qpb_daemon_lifecycle_",
        )
        self.tmpdir = Path(self._tmpdir_ctx.name)
        self.run_dir = self.tmpdir / "run_dir"
        self.run_dir.mkdir()
        self._spawned: list[subprocess.Popen] = []

    def tearDown(self) -> None:
        for proc in self._spawned:
            if proc.poll() is None:
                try:
                    proc.terminate()
                    proc.wait(timeout=2)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        proc.kill()
                    except OSError:
                        pass
        self._tmpdir_ctx.cleanup()

    def _track(self, proc: subprocess.Popen) -> subprocess.Popen:
        self._spawned.append(proc)
        return proc

    def test_1_starts_writes_pid_and_heartbeat(self) -> None:
        """Case 1: daemon starts, writes valid PID file + heartbeat,
        sleeps the configured interval."""
        proc = self._track(_spawn_daemon(self.run_dir))
        pid_path = self.run_dir / "daemon.pid"
        heartbeat_path = self.run_dir / "daemon.heartbeat"
        log_path = self.run_dir / "daemon.log"

        # NOTE: do NOT read proc.stderr here on failure — the daemon
        # holds stderr open until exit, so a blocking read would hang
        # the test rather than report the failure. If diagnostic is
        # needed, capture stderr to a file at spawn time.
        self.assertTrue(
            _wait_for_file(pid_path, 5.0),
            "daemon.pid not created within 5s (check daemon.log if it exists)",
        )
        pid = _read_pid(pid_path)
        self.assertIsNotNone(pid, "PID file content not parseable")
        self.assertGreater(pid, 0, "PID must be positive")

        self.assertTrue(
            _wait_for_file(heartbeat_path, 5.0),
            "daemon.heartbeat not created within 5s",
        )
        self.assertTrue(
            _wait_for_file(log_path, 5.0),
            "daemon.log not created within 5s",
        )

        # Let one full sleep cycle complete to ensure the wake/sleep
        # loop is running, then clean up.
        time.sleep(3.5)
        log_text = log_path.read_text(encoding="utf-8")
        self.assertIn(
            "daemon loop starting", log_text,
            f"daemon.log missing 'daemon loop starting': {log_text!r}",
        )
        self.assertIn(
            "tick fire", log_text,
            f"daemon.log missing 'tick fire': {log_text!r}",
        )

    def test_2_done_marker_exits_within_2x_interval(self) -> None:
        """Case 2: writing done.marker causes the daemon to exit
        within 2 x interval and remove its PID file."""
        proc = self._track(_spawn_daemon(self.run_dir))
        pid_path = self.run_dir / "daemon.pid"
        self.assertTrue(_wait_for_file(pid_path, 5.0))
        pid = _read_pid(pid_path)
        # 2 x interval = 2 x ~2.4 sec = ~4.8 sec budget.
        done_marker = self.run_dir / "done.marker"
        done_marker.write_text(
            "2026-06-09T14:00:00Z\n", encoding="utf-8",
        )
        # Wait up to 8 sec (generous margin) for the daemon to wake,
        # see done.marker, and exit.
        self.assertTrue(
            _wait_for_pid_exit(pid, 8.0, proc=proc),
            f"daemon (pid={pid}) did not exit within 8s of done.marker",
        )
        self.assertTrue(
            _wait_for_no_file(pid_path, 3.0),
            "daemon.pid not removed after clean exit",
        )
        log_text = (self.run_dir / "daemon.log").read_text(encoding="utf-8")
        self.assertIn(
            "done.marker present", log_text,
            f"daemon.log missing done.marker exit entry: {log_text!r}",
        )

    def test_3_refuses_when_pid_alive(self) -> None:
        """Case 3: daemon refuses to start if PID file exists with a
        live PID. Second spawn exits code 7 without modifying the
        existing PID file."""
        proc1 = self._track(_spawn_daemon(self.run_dir))
        pid_path = self.run_dir / "daemon.pid"
        self.assertTrue(_wait_for_file(pid_path, 5.0))
        original_pid = _read_pid(pid_path)
        original_mtime = pid_path.stat().st_mtime

        # Now spawn a second daemon against the same run-dir.
        proc2 = self._track(_spawn_daemon(self.run_dir))
        try:
            rc = proc2.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc2.kill()
            self.fail("second daemon did not exit within 5s")
        self.assertEqual(
            rc, 7,
            f"second daemon should exit code 7 (lock held); got rc={rc}",
        )
        # PID file should be unchanged.
        self.assertEqual(
            _read_pid(pid_path), original_pid,
            "second daemon clobbered the existing PID file",
        )
        self.assertEqual(
            pid_path.stat().st_mtime, original_mtime,
            "second daemon modified PID file mtime",
        )

    def test_4_overwrites_stale_pid(self) -> None:
        """Case 4: daemon overwrites a stale PID file (PID not
        alive)."""
        pid_path = self.run_dir / "daemon.pid"
        # Use a PID guaranteed not to exist: a very large number
        # (the OS won't have allocated this).
        pid_path.write_text("999999999\n", encoding="utf-8")
        proc = self._track(_spawn_daemon(self.run_dir))
        # Wait for the daemon to overwrite the PID file with its own.
        deadline = time.monotonic() + 5.0
        new_pid = None
        while time.monotonic() < deadline:
            candidate = _read_pid(pid_path)
            if candidate is not None and candidate != 999999999:
                new_pid = candidate
                break
            time.sleep(0.1)
        self.assertIsNotNone(
            new_pid,
            "stale PID file was not overwritten within 5s",
        )
        self.assertNotEqual(new_pid, 999999999)
        self.assertEqual(new_pid, proc.pid)

    def test_5_sigterm_graceful_exit(self) -> None:
        """Case 5: SIGTERM during sleep causes graceful exit + PID
        cleanup + log entry."""
        proc = self._track(_spawn_daemon(self.run_dir))
        pid_path = self.run_dir / "daemon.pid"
        self.assertTrue(_wait_for_file(pid_path, 5.0))
        pid = _read_pid(pid_path)
        # Give the daemon a moment to enter its sleep cycle.
        time.sleep(1.0)
        os.kill(pid, signal.SIGTERM)
        self.assertTrue(
            _wait_for_pid_exit(pid, 5.0, proc=proc),
            f"daemon (pid={pid}) did not exit within 5s of SIGTERM",
        )
        self.assertTrue(
            _wait_for_no_file(pid_path, 3.0),
            "daemon.pid not removed after SIGTERM",
        )
        log_text = (self.run_dir / "daemon.log").read_text(encoding="utf-8")
        self.assertIn(
            "SIGTERM", log_text,
            f"daemon.log missing SIGTERM entry: {log_text!r}",
        )


if __name__ == "__main__":
    unittest.main()
