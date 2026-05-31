"""v1.5.7 147 — `runner.kill_run` (operator-initiated termination).

Signals the run's process group (if alive), writes a KILLED
status.json, releases the 125 inflight-registry slot. Default
SIGKILL; SIGTERM for `--graceful` (single signal, no escalation,
ruled in 147). Raises KillError if the run is already collected.

`_kill_process_tree` / `_pid_alive` / `release_run_slot` are mocked
so no real process is signalled and no real registry is touched.
"""
from __future__ import annotations

import json
import signal
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bin.harness import runner as R
from bin.harness.schema import TerminalState


def _fixture(tmp: str, *, pid=12345, state="RUNNING",
             with_grading=False) -> Path:
    """A harness-run/run-00 with manifest.json + status.json."""
    hr = Path(tmp) / "20260529T120000Z"
    run_dir = hr / "run-00"
    run_dir.mkdir(parents=True, exist_ok=True)
    (hr / "manifest.json").write_text(json.dumps({
        "harness_run_dir": str(hr),
        "runs": [{"index": 0, "run_dir": str(run_dir),
                  "pid": pid}],
    }) + "\n", encoding="utf-8")
    (run_dir / "status.json").write_text(json.dumps({
        "state": state, "pid": pid,
        "started_at": "2026-05-29T12:00:00Z",
    }) + "\n", encoding="utf-8")
    if with_grading:
        (run_dir / "grading.json").write_text("{}", encoding="utf-8")
    return run_dir


def _read_status(run_dir: Path) -> dict:
    return json.loads((run_dir / "status.json").read_text())


class KillRunTests(unittest.TestCase):

    def test_alive_pid_sends_signal_and_writes_killed_status(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _fixture(tmp, pid=999)
            with mock.patch.object(R, "_pid_alive", return_value=True), \
                 mock.patch.object(R, "_kill_process_tree") as m_kill, \
                 mock.patch.object(R, "_release_slot_for_run_dir"):
                res = R.kill_run(run_dir, grace_poll_s=0.0)
            m_kill.assert_called_once()
            self.assertEqual(m_kill.call_args.args[0], 999)
            self.assertEqual(m_kill.call_args.kwargs["sig"],
                             signal.SIGKILL)
            self.assertTrue(res.was_alive)
            st = _read_status(run_dir)
            self.assertEqual(st["terminal_state"],
                             TerminalState.KILLED.value)
            self.assertEqual(st["state"], "DONE")

    def test_dead_pid_skips_signal_but_records_killed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _fixture(tmp)
            with mock.patch.object(R, "_pid_alive", return_value=False), \
                 mock.patch.object(R, "_kill_process_tree") as m_kill, \
                 mock.patch.object(R, "_release_slot_for_run_dir"):
                res = R.kill_run(run_dir)
            m_kill.assert_not_called()
            self.assertFalse(res.was_alive)
            self.assertEqual(_read_status(run_dir)["terminal_state"],
                             TerminalState.KILLED.value)

    def test_graceful_uses_sigterm(self) -> None:
        """Mutation-bite companion: default is SIGKILL, --graceful is
        SIGTERM — the sig kwarg is load-bearing."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _fixture(tmp)
            with mock.patch.object(R, "_pid_alive", return_value=True), \
                 mock.patch.object(R, "_kill_process_tree") as m_kill, \
                 mock.patch.object(R, "_release_slot_for_run_dir"):
                R.kill_run(run_dir, sig=signal.SIGTERM,
                           grace_poll_s=0.0)
            self.assertEqual(m_kill.call_args.kwargs["sig"],
                             signal.SIGTERM)

    def test_already_collected_raises_killerror(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _fixture(tmp, with_grading=True)
            with mock.patch.object(R, "_pid_alive", return_value=True), \
                 mock.patch.object(R, "_kill_process_tree") as m_kill:
                with self.assertRaises(R.KillError):
                    R.kill_run(run_dir)
            m_kill.assert_not_called()  # never touched a collected run

    def test_release_slot_helper_is_called(self) -> None:
        # v1.5.7 174 Phase 5: pre-174 this asserted that kill_run
        # called inflight_registry.release_run_slot. Post-174 the
        # release semantic is "write KILLED to the manifest entry"
        # — handled by kill_run's status.json write + manifest
        # transition. _release_slot_for_run_dir is now a no-op
        # back-compat stub; we only assert it's still called
        # (so the wiring point remains observable).
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _fixture(tmp)
            with mock.patch.object(R, "_pid_alive", return_value=False), \
                 mock.patch.object(R,
                                    "_release_slot_for_run_dir") as m_rel:
                R.kill_run(run_dir)
            m_rel.assert_called_once_with(run_dir)

    def test_records_negative_signal_as_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = _fixture(tmp)
            with mock.patch.object(R, "_pid_alive", return_value=False), \
                 mock.patch.object(R, "_release_slot_for_run_dir"):
                R.kill_run(run_dir, sig=signal.SIGKILL)
            self.assertEqual(_read_status(run_dir)["exit_code"],
                             -int(signal.SIGKILL))


class KillProcessTreeSigTests(unittest.TestCase):
    """The additive sig kwarg on the shared primitive (Ruling 1)."""

    def test_explicit_sig_sends_once_no_escalation(self) -> None:
        with mock.patch.object(R.os, "killpg") as m_killpg, \
             mock.patch.object(R.time, "sleep") as m_sleep:
            R._kill_process_tree(123, sig=signal.SIGKILL)
        m_killpg.assert_called_once_with(123, signal.SIGKILL)
        m_sleep.assert_not_called()  # no grace period

    def test_default_preserves_escalation(self) -> None:
        with mock.patch.object(R.os, "killpg") as m_killpg, \
             mock.patch.object(R.time, "sleep"):
            R._kill_process_tree(123)  # no sig → timeout-path behavior
        # SIGTERM then SIGKILL (escalation) — 2 killpg calls.
        self.assertEqual(m_killpg.call_count, 2)
        self.assertEqual(m_killpg.call_args_list[0].args,
                         (123, signal.SIGTERM))
        self.assertEqual(m_killpg.call_args_list[1].args,
                         (123, signal.SIGKILL))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
