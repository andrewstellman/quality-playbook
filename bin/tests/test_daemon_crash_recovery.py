"""v1.5.9 instruction 213 H13 — daemon crash recovery tests.

Stdlib-only pytest. Covers the harness's DETECTION logic for
daemon liveness — the actual re-spawn step is mocked, since H12
(test_daemon_lifecycle.py) already covers the real spawn round-
trip.

Cases:

1. kill -9 detection — PID file present with a PID that does not
   correspond to any live process → harness detects stale PID,
   would re-spawn.
2. heartbeat-mtime detection — PID file points at a live PID, but
   the heartbeat mtime is older than 3 x interval → harness
   detects stale daemon, would re-spawn.
3. Current heartbeat → harness leaves daemon alone.
4. Healthy daemon (live PID + fresh heartbeat) → harness leaves
   daemon alone (no double-spawn).

The detection logic is the contract the harness skill (SKILL.md
§ Daemon crash recovery + STATE_MACHINE.md § Daemon lifecycle
invariants) commits to. These tests pin it.
"""
from __future__ import annotations

import os
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import NamedTuple


_INTERVAL_MINUTES = 10.0
_STALE_THRESHOLD_SECONDS = _INTERVAL_MINUTES * 60 * 3.0  # 30 min


class DaemonHealthResult(NamedTuple):
    """The detection logic's output shape."""

    healthy: bool
    reason: str


def _check_daemon_health(
    run_dir: Path,
    interval_minutes: float = _INTERVAL_MINUTES,
    now: "float | None" = None,
) -> DaemonHealthResult:
    """Detection logic the harness skill applies on manual
    invocation. Mirrors the SKILL.md § Daemon crash recovery
    semantics:

      - If daemon.pid missing → not healthy.
      - If daemon.pid contents not parseable → not healthy.
      - If PID is not alive (os.kill(pid, 0) raises
        ProcessLookupError) → not healthy.
      - If daemon.heartbeat mtime is older than 3 x
        interval_minutes → not healthy.
      - Else → healthy.
    """
    if now is None:
        now = time.time()
    pid_path = run_dir / "daemon.pid"
    heartbeat_path = run_dir / "daemon.heartbeat"
    threshold_seconds = interval_minutes * 60 * 3.0
    if not pid_path.is_file():
        return DaemonHealthResult(
            healthy=False, reason="daemon.pid missing",
        )
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return DaemonHealthResult(
            healthy=False,
            reason="daemon.pid content not parseable as integer",
        )
    if pid <= 0:
        return DaemonHealthResult(
            healthy=False, reason=f"PID {pid} non-positive",
        )
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return DaemonHealthResult(
            healthy=False, reason=f"PID {pid} not alive",
        )
    except PermissionError:
        # Live but we can't signal — treat as alive (conservative).
        pass
    except OSError:
        pass
    if not heartbeat_path.is_file():
        return DaemonHealthResult(
            healthy=False, reason="daemon.heartbeat missing",
        )
    try:
        heartbeat_mtime = heartbeat_path.stat().st_mtime
    except OSError as exc:
        return DaemonHealthResult(
            healthy=False,
            reason=f"daemon.heartbeat stat failed: {exc}",
        )
    age = now - heartbeat_mtime
    if age > threshold_seconds:
        return DaemonHealthResult(
            healthy=False,
            reason=(
                f"heartbeat mtime stale (age {age:.0f}s > "
                f"{threshold_seconds:.0f}s)"
            ),
        )
    return DaemonHealthResult(healthy=True, reason="all checks pass")


class DaemonCrashRecoveryTests(unittest.TestCase):
    """Four cases per instruction 213 § H13."""

    def setUp(self) -> None:
        self._tmpdir_ctx = TemporaryDirectory(
            prefix="qpb_daemon_recovery_",
        )
        self.tmpdir = Path(self._tmpdir_ctx.name)
        self.run_dir = self.tmpdir / "run_dir"
        self.run_dir.mkdir()

    def tearDown(self) -> None:
        self._tmpdir_ctx.cleanup()

    def _write_pid_file(self, pid: int) -> Path:
        pid_path = self.run_dir / "daemon.pid"
        pid_path.write_text(f"{pid}\n", encoding="utf-8")
        return pid_path

    def _touch_heartbeat(self, age_seconds: float = 0.0) -> Path:
        heartbeat_path = self.run_dir / "daemon.heartbeat"
        heartbeat_path.touch()
        if age_seconds > 0:
            mtime = time.time() - age_seconds
            os.utime(heartbeat_path, (mtime, mtime))
        return heartbeat_path

    def test_1_kill9_detection(self) -> None:
        """Case 1: PID file points at a dead PID (kill -9 simulated
        via a synthetic non-existent PID). Detection MUST report
        not-healthy with reason 'PID not alive'."""
        # Use a PID guaranteed not to exist on this system.
        synthetic_dead_pid = 999_999_999
        self._write_pid_file(synthetic_dead_pid)
        # Fresh heartbeat — to prove the PID check is what catches
        # this, not the mtime check.
        self._touch_heartbeat(age_seconds=0)
        result = _check_daemon_health(self.run_dir)
        self.assertFalse(result.healthy, result.reason)
        self.assertIn(
            "not alive", result.reason,
            f"Expected 'not alive' in reason; got {result.reason!r}",
        )

    def test_2_heartbeat_mtime_detection(self) -> None:
        """Case 2: PID file points at a live PID, but heartbeat
        mtime is older than 3 x interval → detection reports
        not-healthy with reason 'heartbeat mtime stale'."""
        # Use this test's own PID — guaranteed live for the test's
        # duration.
        live_pid = os.getpid()
        self._write_pid_file(live_pid)
        # Heartbeat is 4 x interval old (> 3 x threshold).
        self._touch_heartbeat(age_seconds=_STALE_THRESHOLD_SECONDS + 60)
        result = _check_daemon_health(self.run_dir)
        self.assertFalse(result.healthy, result.reason)
        self.assertIn(
            "stale", result.reason,
            f"Expected 'stale' in reason; got {result.reason!r}",
        )

    def test_3_current_heartbeat_leaves_daemon_alone(self) -> None:
        """Case 3: live PID + fresh heartbeat → detection reports
        healthy. Harness MUST leave the daemon alone (no re-spawn)."""
        live_pid = os.getpid()
        self._write_pid_file(live_pid)
        self._touch_heartbeat(age_seconds=0)
        result = _check_daemon_health(self.run_dir)
        self.assertTrue(
            result.healthy,
            f"Expected healthy; got {result.reason!r}",
        )

    def test_4_healthy_daemon_no_double_spawn(self) -> None:
        """Case 4: healthy daemon (live PID + fresh heartbeat, even
        a bit old but under 3 x threshold). Detection reports
        healthy → harness does NOT re-spawn. This guards against
        the double-spawn race the daemon's O_EXCL lock would catch
        anyway but the harness can short-circuit earlier."""
        live_pid = os.getpid()
        self._write_pid_file(live_pid)
        # Heartbeat 1 interval old — well under the 3x threshold.
        self._touch_heartbeat(
            age_seconds=_INTERVAL_MINUTES * 60,
        )
        result = _check_daemon_health(self.run_dir)
        self.assertTrue(
            result.healthy,
            f"Expected healthy at 1 x interval age; got "
            f"{result.reason!r}",
        )

    def test_5_missing_pid_file_is_not_healthy(self) -> None:
        """Bonus pin: no PID file → not healthy (re-spawn warranted).
        Mirrors first-tick semantics."""
        result = _check_daemon_health(self.run_dir)
        self.assertFalse(result.healthy, result.reason)
        self.assertIn(
            "missing", result.reason,
            f"Expected 'missing' in reason; got {result.reason!r}",
        )

    def test_6_garbage_pid_file_is_not_healthy(self) -> None:
        """Bonus pin: malformed PID file content → not healthy."""
        pid_path = self.run_dir / "daemon.pid"
        pid_path.write_text("not-a-pid\n", encoding="utf-8")
        self._touch_heartbeat(age_seconds=0)
        result = _check_daemon_health(self.run_dir)
        self.assertFalse(result.healthy, result.reason)
        self.assertIn(
            "parseable", result.reason,
            f"Expected 'parseable' in reason; got {result.reason!r}",
        )


if __name__ == "__main__":
    unittest.main()
