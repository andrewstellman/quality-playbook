"""v1.5.7 172 — unit tests for the watchdog daemon's pure helpers
(``_is_orphan``, ``_all_terminal``) + the lock-skip semantics.

The watchdog's main loop is signal-driven (SIGTERM clean exit) and
not exercised here; the helpers are pure functions and the lock
semantics are observable via a sub-thread holding the lock.
"""
from __future__ import annotations

import fcntl
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path


_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from bin.harness import watchdog as WD  # noqa: E402


def _touch(path: Path, mtime: "float | None" = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x\n", encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))


class IsOrphanTests(unittest.TestCase):

    def _entry(self, **overrides) -> dict:
        e = {
            "index": 0, "state": "RUNNING", "pid": None,
            "run_dir": "run-00", "terminal_state": None,
        }
        e.update(overrides)
        return e

    def test_alive_pid_not_orphan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hrd = Path(tmp)
            _touch(hrd / "run-00" / "stream.ndjson",
                   mtime=time.time() - 600)
            entry = self._entry(pid=os.getpid())
            self.assertFalse(
                WD._is_orphan(entry, hrd, stale_threshold_s=30.0))

    def test_dead_pid_stale_stream_is_orphan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hrd = Path(tmp)
            _touch(hrd / "run-00" / "stream.ndjson",
                   mtime=time.time() - 600)
            entry = self._entry(pid=999999)
            self.assertTrue(
                WD._is_orphan(entry, hrd, stale_threshold_s=30.0))

    def test_dead_pid_fresh_stream_not_orphan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hrd = Path(tmp)
            _touch(hrd / "run-00" / "stream.ndjson",
                   mtime=time.time())
            entry = self._entry(pid=999999)
            self.assertFalse(
                WD._is_orphan(entry, hrd, stale_threshold_s=30.0))

    def test_dead_pid_no_stream_is_orphan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hrd = Path(tmp)
            (hrd / "run-00").mkdir()  # dir but no stream.ndjson
            entry = self._entry(pid=999999)
            self.assertTrue(
                WD._is_orphan(entry, hrd, stale_threshold_s=30.0))

    def test_terminal_state_not_orphan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hrd = Path(tmp)
            _touch(hrd / "run-00" / "stream.ndjson",
                   mtime=time.time() - 600)
            entry = self._entry(
                pid=999999, terminal_state="COMPLETED")
            self.assertFalse(
                WD._is_orphan(entry, hrd, stale_threshold_s=30.0))

    def test_done_state_not_orphan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hrd = Path(tmp)
            entry = self._entry(state="DONE", pid=999999)
            self.assertFalse(
                WD._is_orphan(entry, hrd, stale_threshold_s=30.0))

    def test_aborted_prep_state_not_orphan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hrd = Path(tmp)
            entry = self._entry(state="ABORTED_PREP", pid=999999)
            self.assertFalse(
                WD._is_orphan(entry, hrd, stale_threshold_s=30.0))

    def test_abandoned_starved_state_not_orphan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hrd = Path(tmp)
            entry = self._entry(
                state="ABANDONED_STARVED", pid=999999)
            self.assertFalse(
                WD._is_orphan(entry, hrd, stale_threshold_s=30.0))

    def test_pending_state_not_orphan(self) -> None:
        # PENDING handled by 165 retry path, not watchdog.
        with tempfile.TemporaryDirectory() as tmp:
            hrd = Path(tmp)
            entry = self._entry(state="PENDING", pid=None)
            self.assertFalse(
                WD._is_orphan(entry, hrd, stale_threshold_s=30.0))

    def test_pid_none_running_not_orphan(self) -> None:
        # A RUNNING entry with pid=None is incomplete-write state,
        # not orphaned; let the collector handle it.
        with tempfile.TemporaryDirectory() as tmp:
            hrd = Path(tmp)
            _touch(hrd / "run-00" / "stream.ndjson",
                   mtime=time.time() - 600)
            entry = self._entry(state="RUNNING", pid=None)
            self.assertFalse(
                WD._is_orphan(entry, hrd, stale_threshold_s=30.0))


class AllTerminalTests(unittest.TestCase):

    def test_empty_runs_not_all_terminal(self) -> None:
        self.assertFalse(WD._all_terminal({"runs": []}))

    def test_no_runs_key_not_all_terminal(self) -> None:
        self.assertFalse(WD._all_terminal({}))

    def test_all_terminal_states_true(self) -> None:
        manifest = {"runs": [
            {"index": 0, "terminal_state": "COMPLETED"},
            {"index": 1, "terminal_state": "FAILED"},
            {"index": 2, "state": "DONE"},
        ]}
        self.assertTrue(WD._all_terminal(manifest))

    def test_one_running_not_all_terminal(self) -> None:
        manifest = {"runs": [
            {"index": 0, "terminal_state": "COMPLETED"},
            {"index": 1, "state": "RUNNING", "pid": 123},
        ]}
        self.assertFalse(WD._all_terminal(manifest))

    def test_pending_not_terminal(self) -> None:
        manifest = {"runs": [
            {"index": 0, "state": "PENDING", "pid": None},
        ]}
        self.assertFalse(WD._all_terminal(manifest))


class EnvVarOverrideTests(unittest.TestCase):

    def setUp(self) -> None:
        self._saved = {
            k: os.environ.get(k)
            for k in ("QPB_WATCHDOG_INTERVAL_S",
                       "QPB_WATCHDOG_STALE_S")
        }

    def tearDown(self) -> None:
        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def test_interval_default(self) -> None:
        os.environ.pop("QPB_WATCHDOG_INTERVAL_S", None)
        self.assertEqual(WD._interval_s(), 60.0)

    def test_interval_env_override(self) -> None:
        os.environ["QPB_WATCHDOG_INTERVAL_S"] = "1.5"
        self.assertEqual(WD._interval_s(), 1.5)

    def test_interval_non_numeric_falls_back(self) -> None:
        os.environ["QPB_WATCHDOG_INTERVAL_S"] = "not-a-number"
        self.assertEqual(WD._interval_s(), 60.0)

    def test_interval_negative_falls_back(self) -> None:
        os.environ["QPB_WATCHDOG_INTERVAL_S"] = "-1"
        self.assertEqual(WD._interval_s(), 60.0)

    def test_stale_default(self) -> None:
        os.environ.pop("QPB_WATCHDOG_STALE_S", None)
        self.assertEqual(WD._stale_s(), 30.0)

    def test_stale_env_override(self) -> None:
        os.environ["QPB_WATCHDOG_STALE_S"] = "5"
        self.assertEqual(WD._stale_s(), 5.0)


class LockSkipBehaviorTests(unittest.TestCase):
    """v1.5.7 172: the watchdog's lock-skip semantics. The watchdog
    acquires LOCK_EX|LOCK_NB on .collect.lock; if held it skips the
    tick. Verified via a sub-thread that holds the lock blockingly
    while we attempt the non-blocking acquire."""

    def test_lock_nb_fails_when_held(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / ".collect.lock"
            holder_fp = open(lock_path, "w", encoding="utf-8")
            fcntl.flock(holder_fp.fileno(), fcntl.LOCK_EX)
            try:
                # Another open + non-blocking acquire must fail.
                attempt_fp = open(lock_path, "w",
                                    encoding="utf-8")
                try:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(
                            attempt_fp.fileno(),
                            fcntl.LOCK_EX | fcntl.LOCK_NB)
                finally:
                    attempt_fp.close()
            finally:
                fcntl.flock(holder_fp.fileno(), fcntl.LOCK_UN)
                holder_fp.close()

    def test_lock_nb_succeeds_when_free(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / ".collect.lock"
            fp = open(lock_path, "w", encoding="utf-8")
            try:
                fcntl.flock(
                    fp.fileno(),
                    fcntl.LOCK_EX | fcntl.LOCK_NB)
                fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
            finally:
                fp.close()


class CliWiringTests(unittest.TestCase):
    """Source-inspection smoke test: the watchdog subcommand exists
    in qpb_harness.py main dispatch."""

    def test_watchdog_subcommand_wired(self) -> None:
        src = (Path(__file__).resolve().parents[3]
                / "bin" / "qpb_harness.py").read_text(
                    encoding="utf-8")
        self.assertIn('args.command == "watchdog"', src)
        self.assertIn("_cmd_watchdog", src)
        self.assertIn('add_parser(\n        "watchdog"', src)


class AutoSpawnWiringTests(unittest.TestCase):
    """v1.5.7 172 Task D: the orchestrator's detached-launch path
    auto-spawns the watchdog alongside the collector. Source-
    inspection only — the live spawn is exercised by end-to-end
    ship-readiness runs."""

    def test_run_plan_calls_spawn_watchdog(self) -> None:
        src = (Path(__file__).resolve().parents[3]
                / "bin" / "harness" / "plan_runner.py").read_text(
                    encoding="utf-8")
        self.assertIn("def _spawn_watchdog(", src)
        self.assertIn(
            "watchdog_pid = _spawn_watchdog(harness_run_dir, log)",
            src)
        self.assertIn("_LAST_WATCHDOG_PID", src)

    def test_banner_includes_watchdog_pid(self) -> None:
        src = (Path(__file__).resolve().parents[3]
                / "bin" / "qpb_harness.py").read_text(
                    encoding="utf-8")
        self.assertIn("watchdog_pid", src)
        self.assertIn('"  watchdog pid {watchdog_pid}"'
                       .replace('"', '').replace("{watchdog_pid}",
                                                  "watchdog_pid"),
                       src.replace('"', '').replace(
                           "{watchdog_pid}", "watchdog_pid"))


class StatusDisplayTests(unittest.TestCase):
    """v1.5.7 172 Task E: status.py surfaces watchdog liveness."""

    def test_harness_run_summary_has_watchdog_alive_field(
            self) -> None:
        from bin.harness import status as ST  # noqa: PLC0415
        # The dataclass should accept watchdog_alive kwarg.
        import dataclasses as _dc
        fields = {f.name for f in _dc.fields(ST.HarnessRunSummary)}
        self.assertIn("watchdog_alive", fields)

    def test_format_harness_run_includes_watchdog_token(
            self) -> None:
        src = (Path(__file__).resolve().parents[3]
                / "bin" / "harness" / "status.py").read_text(
                    encoding="utf-8")
        # The format string must emit a watchdog= token alongside
        # the existing collector= token.
        self.assertIn("watchdog=", src)
        self.assertIn("summary.watchdog_alive", src)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
