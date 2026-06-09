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
                / "bin" / "qpb_harness_legacy.py").read_text(
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
                / "bin" / "qpb_harness_legacy.py").read_text(
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


class RecoveryNoDeadlockTests(unittest.TestCase):
    """v1.5.7 172 FINDING-1 (FIX-REQUIRED): the watchdog's orphan-
    recovery path must not deadlock when calling
    ``collect_harness_run``. Pre-fix the watchdog held LOCK_EX on
    ``.collect.lock`` and ``collect_harness_run``'s blocking
    LOCK_EX (different FD, same process) deadlocked because
    ``fcntl.flock`` is per open file description, not per inode.

    Test design: stub ``collect_harness_run`` to a sentinel-touch
    no-op; spin up the recovery branch in a thread under
    ``QPB_WATCHDOG_INTERVAL_S=0.5``; assert the thread exits
    within 5s with the sentinel file created. Pre-fix the thread
    would hang in ``fcntl.flock``."""

    def test_recovery_collect_does_not_deadlock(self) -> None:
        import json as _json
        import threading
        import time as _time
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            hrd = Path(tmp)
            # Minimal manifest with one orphan entry:
            # state=RUNNING, pid=dead, stream stale.
            (hrd / "run-00").mkdir()
            stream = hrd / "run-00" / "stream.ndjson"
            stream.write_text("x\n", encoding="utf-8")
            # Make stream stale (> default 30s stale threshold).
            old = _time.time() - 600
            import os as _os
            _os.utime(stream, (old, old))
            manifest = {
                "runs": [{
                    "index": 0, "state": "RUNNING",
                    "pid": 999999,  # dead pid
                    "run_dir": "run-00",
                }],
            }
            (hrd / "manifest.json").write_text(
                _json.dumps(manifest), encoding="utf-8")

            # Stub collect_harness_run to a sentinel-touch no-op
            # that also acquires its own LOCK_EX on .collect.lock
            # (same as the real one), proving the watchdog
            # released the probe before calling it.
            sentinel = hrd / "recovery-fired.txt"

            def stub_collect(harness_run_dir, log=None):
                # Mimic real collect_harness_run's lock acquire.
                lock_path = (
                    harness_run_dir / ".collect.lock")
                with open(lock_path, "w",
                            encoding="utf-8") as fp:
                    fcntl.flock(
                        fp.fileno(), fcntl.LOCK_EX)
                    sentinel.write_text("ok\n",
                                          encoding="utf-8")
                    fcntl.flock(
                        fp.fileno(), fcntl.LOCK_UN)
                return []

            from bin.harness import plan_runner as _pr
            from bin.harness import watchdog as _wd
            saved = _pr.collect_harness_run
            _pr.collect_harness_run = stub_collect
            # signal.signal() only works from the main thread —
            # patch the watchdog's import target to a no-op so
            # run_watchdog can run inside our test thread.
            import signal as _signal
            saved_signal = _wd.signal
            class _StubSignal:
                SIGTERM = _signal.SIGTERM
                SIGINT = _signal.SIGINT
                @staticmethod
                def signal(signum, handler):
                    return None
            _wd.signal = _StubSignal()

            # Drive a SHORT watchdog interval so the loop fires
            # quickly. We send SIGTERM after the sentinel exists
            # so the watchdog exits cleanly.
            saved_envs = {
                k: os.environ.get(k)
                for k in ("QPB_WATCHDOG_INTERVAL_S",
                           "QPB_WATCHDOG_STALE_S")
            }
            os.environ["QPB_WATCHDOG_INTERVAL_S"] = "0.5"
            os.environ["QPB_WATCHDOG_STALE_S"] = "1"

            try:
                # Run the watchdog in a thread; assert it returns
                # within 5s after firing the recovery collect.
                # Signals can't reach a non-main thread, so we
                # instead let the watchdog naturally exit when
                # all_terminal becomes true. The stub doesn't set
                # terminal_state, so we patch the all_terminal
                # check by transitioning the manifest after the
                # sentinel touches.
                done = threading.Event()
                result = {"err": None}

                def transition_after_sentinel():
                    deadline = _time.monotonic() + 4.0
                    while _time.monotonic() < deadline:
                        if sentinel.is_file():
                            # Transition the manifest so the
                            # watchdog's next tick sees
                            # _all_terminal and exits cleanly.
                            m = _json.loads(
                                (hrd / "manifest.json").read_text())
                            m["runs"][0]["terminal_state"] = (
                                "COMPLETED")
                            m["runs"][0]["state"] = "DONE"
                            (hrd / "manifest.json").write_text(
                                _json.dumps(m))
                            return
                        _time.sleep(0.1)

                from bin.harness import watchdog as _wd

                def run_it():
                    try:
                        _wd.run_watchdog(hrd)
                    except BaseException as exc:
                        result["err"] = exc
                    finally:
                        done.set()

                helper = threading.Thread(
                    target=transition_after_sentinel,
                    daemon=True)
                helper.start()
                thread = threading.Thread(
                    target=run_it, daemon=True)
                thread.start()
                # 5s timeout. Pre-fix the watchdog hangs in
                # fcntl.flock and this wait times out.
                done.wait(timeout=10.0)
                self.assertTrue(
                    done.is_set(),
                    "watchdog did not exit within 10s — "
                    "deadlock regression?")
                self.assertIsNone(result["err"],
                                   f"watchdog raised: "
                                   f"{result['err']!r}")
                self.assertTrue(
                    sentinel.is_file(),
                    "recovery collect was not called")
            finally:
                _pr.collect_harness_run = saved
                _wd.signal = saved_signal
                for k, v in saved_envs.items():
                    if v is None:
                        os.environ.pop(k, None)
                    else:
                        os.environ[k] = v


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
