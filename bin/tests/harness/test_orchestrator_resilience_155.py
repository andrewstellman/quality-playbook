"""v1.5.7 155 — orchestrator SIGHUP resilience + inflight registry
zombie cross-check + PermissionError policy.

Surfaced by the 2026-05-29 23:20 ship-readiness retest: the operator
launched the harness in a foreground shell, then closed it; the
orchestrator died (no SIGHUP handler); 5 of 6 children eventually
showed as defunct in ``ps``; ``~/.qpb_harness/inflight.json`` retained
all 6 entries claiming live state.

Worker's pre-flight (see
``reviews/155-orchestrator-sighup-resilience-HALT-RULING.md``) found:

- ``start_new_session=True`` already at every Popen site
  (``runner.py:925``, ``plan_runner.py:2378``) — fork→setsid race is
  closed atomically.
- Stdio already file-redirected at every spawn site (stdout to
  ``stream.ndjson`` / ``collector.log`` / ``<run-dir>``; stdin to
  ``DEVNULL`` / ``PIPE``; stderr merged via ``STDOUT``). The
  SIGPIPE-via-inherited-TTY hypothesis ruled out by code reading —
  nothing inherits the orchestrator's TTY FDs.
- The inflight registry's existing ``_entry_is_active`` →
  ``_pid_alive`` ⇒ dead-pid reaping already fires on every read
  (empirical: a copy of the 23:20 stale registry → ``read_active_runs``
  evicted all 6 + wrote ``entries: []`` back).

What's still real (and what 155 fixes):

- **Task A** — install ``signal.signal(SIGHUP, SIG_IGN)`` in the
  orchestrator so shell-close doesn't kill it.
- **Task C-zombie** — augment ``_entry_is_active`` with a
  ``terminal_state`` cross-check. ``os.kill(pid, 0)`` succeeds on
  zombies (pid still in the OS table until ``wait()``); the
  ``terminal_state`` check evicts entries whose worker has finished
  regardless.
- **PermissionError policy** — ``_pid_alive``'s
  ``PermissionError → True`` becomes ``→ False``. EPERM means the
  pid is owned by another user / has been reused; on the single-
  user harness shape, retaining the entry would block future runs.
"""
from __future__ import annotations

import json
import os
import signal
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bin.harness import inflight_registry as IR
from bin.harness import plan_runner as PR


# ---------------------------------------------------------------------------
# Task A — SIGHUP handler installation
# ---------------------------------------------------------------------------


class OrchestratorSighupHandlerTests(unittest.TestCase):
    """The orchestrator's run_plan installs SIGHUP=SIG_IGN early so
    closing the launching shell doesn't take it down. Test installs
    in-process and checks ``signal.getsignal``; subprocess-level
    "does it actually survive SIGHUP" verification belongs in a stress
    test, not unit coverage."""

    def setUp(self) -> None:
        # Snapshot + restore the SIGHUP disposition so other tests
        # don't inherit our SIG_IGN.
        self._prev = signal.getsignal(signal.SIGHUP)

    def tearDown(self) -> None:
        try:
            signal.signal(signal.SIGHUP, self._prev)
        except (ValueError, OSError, TypeError):
            pass

    def test_install_sets_sighup_to_sig_ign(self) -> None:
        # Reset to default first so we can observe the change.
        signal.signal(signal.SIGHUP, signal.SIG_DFL)
        self.assertEqual(
            signal.getsignal(signal.SIGHUP), signal.SIG_DFL)
        PR._install_orchestrator_signal_handlers()
        # Mutation-bite: removing the signal.signal call leaves
        # disposition at SIG_DFL → assertion fails.
        self.assertEqual(
            signal.getsignal(signal.SIGHUP), signal.SIG_IGN)

    def test_install_is_idempotent(self) -> None:
        PR._install_orchestrator_signal_handlers()
        PR._install_orchestrator_signal_handlers()
        PR._install_orchestrator_signal_handlers()
        self.assertEqual(
            signal.getsignal(signal.SIGHUP), signal.SIG_IGN)


# ---------------------------------------------------------------------------
# PermissionError policy — pid owned by another user ⇒ stale
# ---------------------------------------------------------------------------


class PidAlivePermissionErrorPolicyTests(unittest.TestCase):

    def test_permission_error_treated_as_dead(self) -> None:
        # Mutation-bite: reverting the catch to
        # `except PermissionError: return True` makes this fail.
        with mock.patch.object(IR.os, "kill",
                                side_effect=PermissionError):
            self.assertFalse(IR._pid_alive(12345))

    def test_process_lookup_error_treated_as_dead(self) -> None:
        # Regression guard — the original behavior.
        with mock.patch.object(IR.os, "kill",
                                side_effect=ProcessLookupError):
            self.assertFalse(IR._pid_alive(12345))

    def test_kill_succeeds_treated_as_alive(self) -> None:
        with mock.patch.object(IR.os, "kill", return_value=None):
            self.assertTrue(IR._pid_alive(12345))


# ---------------------------------------------------------------------------
# Task C-zombie — terminal_state cross-check in _entry_is_active
# ---------------------------------------------------------------------------


def _write_status(run_dir: Path, doc: dict) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "status.json").write_text(
        json.dumps(doc) + "\n", encoding="utf-8")


def _entry(harness_run_dir: Path, *, run_index: int = 0,
           pid: int = 12345) -> dict:
    return {
        "pid": pid,
        "runner": "claude",
        "provider": "anthropic",
        "harness_run_dir": str(harness_run_dir),
        "run_index": run_index,
        "started_at": "2026-05-29T23:20:56Z",
    }


class EntryIsActiveZombieCrossCheckTests(unittest.TestCase):

    def test_zombie_with_terminal_state_evicted(self) -> None:
        # Mock pid as ALIVE (the zombie symptom), but write a
        # terminal_state to the run dir's status.json. The augmented
        # _entry_is_active must return False. Mutation-bite: removing
        # the status.json cross-check returns True (entry retained).
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T232053Z"
            _write_status(hr / "run-00",
                          {"state": "DONE", "terminal_state": "KILLED",
                           "pid": 12345})
            with mock.patch.object(IR, "_pid_alive",
                                    return_value=True):
                self.assertFalse(IR._entry_is_active(_entry(hr)))

    def test_zombie_without_terminal_state_preserved(self) -> None:
        # Live pid, status.json exists but no terminal_state yet → in
        # flight; preserve.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T232053Z"
            _write_status(hr / "run-00",
                          {"state": "RUNNING", "pid": 12345,
                           "terminal_state": None})
            with mock.patch.object(IR, "_pid_alive",
                                    return_value=True):
                self.assertTrue(IR._entry_is_active(_entry(hr)))

    def test_alive_pid_with_missing_status_json_preserved(self) -> None:
        # Live pid, no status.json at all → trust the pid liveness;
        # entry preserved (we don't reap purely on file-missing).
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T232053Z"
            (hr / "run-00").mkdir(parents=True)
            with mock.patch.object(IR, "_pid_alive",
                                    return_value=True):
                self.assertTrue(IR._entry_is_active(_entry(hr)))

    def test_alive_pid_with_malformed_status_json_preserved(
            self) -> None:
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T232053Z"
            (hr / "run-00").mkdir(parents=True)
            (hr / "run-00" / "status.json").write_text(
                "{not valid json", encoding="utf-8")
            with mock.patch.object(IR, "_pid_alive",
                                    return_value=True):
                self.assertTrue(IR._entry_is_active(_entry(hr)))

    def test_dead_pid_still_evicted_without_status_check(
            self) -> None:
        # Regression guard: dead-pid reaping still works (the
        # zombie augmentation only kicks in AFTER _pid_alive
        # returns True).
        with mock.patch.object(IR, "_pid_alive", return_value=False):
            self.assertFalse(IR._entry_is_active(_entry(Path("/tmp"))))


# ---------------------------------------------------------------------------
# Empirical regression — 23:20 stale registry, including zombie case
# ---------------------------------------------------------------------------


class StaleRegistryEmpiricalRegressionTests(unittest.TestCase):
    """Synthesize a 6-entry inflight.json mirroring the 2026-05-29
    23:20 retest shape: 5 entries with pids that read_active_runs
    must reap (mix of dead pids + zombies-with-terminal-state) + 1
    live in-flight entry. Asserts the reaper evicts the 5 stale
    entries on first read."""

    def test_six_entry_stale_registry_reaped_to_one(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T232053Z"
            hr.mkdir()
            # 3 dead-pid entries (PIDs that don't exist; OS kill -0
            # would raise ProcessLookupError).
            # 2 zombie-with-terminal-state entries (live pid +
            # status.json says KILLED → augmentation evicts).
            for i in (3, 4):
                _write_status(hr / f"run-{i:02d}",
                              {"state": "DONE",
                               "terminal_state": "KILLED",
                               "pid": 12345})
            # 1 genuinely-in-flight entry (live pid, no
            # terminal_state) — must be preserved.
            _write_status(hr / "run-06",
                          {"state": "RUNNING", "pid": 12345,
                           "terminal_state": None})

            registry = Path(td) / "inflight.json"
            registry.write_text(json.dumps({"entries": [
                # 3 dead pids — picked unlikely-to-exist numbers.
                _entry(hr, run_index=0, pid=99999991),
                _entry(hr, run_index=1, pid=99999992),
                _entry(hr, run_index=2, pid=99999993),
                # 2 zombies — pid is "alive" (mocked) + status has
                # terminal_state.
                _entry(hr, run_index=3, pid=12345),
                _entry(hr, run_index=4, pid=12345),
                # 1 in-flight — pid is "alive" + no terminal_state.
                _entry(hr, run_index=6, pid=12345),
            ]}) + "\n", encoding="utf-8")

            # _pid_alive only returns True for pid == 12345; the
            # 99999... pids fall through to the real os.kill which
            # will raise ProcessLookupError → return False.
            real_pid_alive = IR._pid_alive
            def _selective(pid):
                if pid == 12345:
                    return True
                return real_pid_alive(pid)
            with mock.patch.object(IR, "_pid_alive",
                                    side_effect=_selective):
                active = IR.read_active_runs(registry_path=registry)
            self.assertEqual(len(active), 1)
            self.assertEqual(active[0]["run_index"], 6)
            # Verify the write-back happened — registry on disk now
            # has just the one in-flight entry.
            on_disk = json.loads(registry.read_text())
            self.assertEqual(len(on_disk["entries"]), 1)
            self.assertEqual(on_disk["entries"][0]["run_index"], 6)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
