"""v1.5.7 164 — Mode B per-phase supervisor writes status.json on
phase abort.

The 2026-05-30 04:26 ship-readiness retest exposed a Mode B worker-
lifecycle gap: codex Mode B runs hit Phase 1 ABORT but their pids
stayed alive 4+ hours after the abort. The collector saw a still-
alive PID with no terminal_state and waited forever.

Task A investigation (per the original 164 instruction): all 5
abort sites in ``bin/run_playbook.py`` already log + ``return
False``. The supervisor's outer loop returns; the 4-hour-alive
zombie is a downstream hang (subprocess cleanup, codex retry loop,
or lockfile/summary write). That hang diagnosis is a separate
follow-up.

This commit (164, per the HALT RULING's Option (a)) addresses what
CAN be fixed cleanly today: the missing status.json write. When
``run_playbook.py`` is invoked by the harness (which sets
``QPB_HARNESS_STATUS_PATH``), each of the 5 abort sites now writes
a terminal-shaped status.json BEFORE returning. The collector then
sees ``terminal_state="ABORTED_PHASE"`` (a new TerminalState enum
value) and grades the run appropriately — no more inference from
``pid is dead, no terminal_state`` ⇒ ``FAILED``.

Outside the harness (no env var), behavior is unchanged: log +
return + no status.json write.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bin import run_playbook as RP
from bin.harness.schema import TerminalState


# ---------------------------------------------------------------------------
# TerminalState.ABORTED_PHASE — new enum value
# ---------------------------------------------------------------------------


class AbortedPhaseEnumTests(unittest.TestCase):

    def test_aborted_phase_enum_value_present(self) -> None:
        # Pin the enum value so a future rename / removal is an
        # explicit decision.
        self.assertEqual(
            TerminalState.ABORTED_PHASE.value, "ABORTED_PHASE")

    def test_aborted_phase_is_in_terminal_state_enum(self) -> None:
        # Sanity: ABORTED_PHASE is part of TerminalState.
        self.assertIn(
            "ABORTED_PHASE", [s.value for s in TerminalState])


# ---------------------------------------------------------------------------
# _write_harness_abort_status — the helper
# ---------------------------------------------------------------------------


class WriteHarnessAbortStatusTests(unittest.TestCase):

    def setUp(self) -> None:
        self._prev_env = os.environ.get(
            "QPB_HARNESS_STATUS_PATH")
        if "QPB_HARNESS_STATUS_PATH" in os.environ:
            del os.environ["QPB_HARNESS_STATUS_PATH"]

    def tearDown(self) -> None:
        if self._prev_env is None:
            os.environ.pop("QPB_HARNESS_STATUS_PATH", None)
        else:
            os.environ["QPB_HARNESS_STATUS_PATH"] = self._prev_env

    def test_env_var_absent_no_op(self) -> None:
        # Mutation-bite target: when the env var is absent (operator
        # ran run_playbook.py manually), the abort helper is a
        # no-op. No status.json written, no exception.
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "status.json"
            RP._write_harness_abort_status(
                3, 1, "phase 3 child failed")
            self.assertFalse(path.exists())

    def test_env_var_present_writes_terminal_status(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "status.json"
            os.environ["QPB_HARNESS_STATUS_PATH"] = str(path)
            RP._write_harness_abort_status(
                3, 1, "phase 3 child failed")
            self.assertTrue(path.is_file())
            data = json.loads(path.read_text())
            self.assertEqual(data["terminal_state"], "ABORTED_PHASE")
            self.assertEqual(data["phase_aborted"], 3)
            self.assertEqual(data["exit_code"], 1)
            self.assertIn("phase 3 child failed",
                          data["terminal_reason"])
            self.assertIn("ended_at", data)
            self.assertEqual(data["pid"], os.getpid())

    def test_existing_status_merged_not_overwritten(self) -> None:
        # If the harness pre-wrote status.json with RUNNING + pid +
        # started_at (which it does — runner.py:912 _write_status
        # block), the abort writer MERGES the abort fields onto
        # that, preserving started_at and pid. Mutation-bite:
        # replacing the merge with a fresh write loses the
        # pre-existing fields.
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "status.json"
            path.write_text(json.dumps({
                "state": "RUNNING",
                "pid": 4242,
                "started_at": "2026-05-30T14:00:00Z",
                "heartbeat": "2026-05-30T14:00:00Z",
            }))
            os.environ["QPB_HARNESS_STATUS_PATH"] = str(path)
            RP._write_harness_abort_status(
                4, 1, "phase 4 group failed")
            data = json.loads(path.read_text())
            self.assertEqual(data["terminal_state"], "ABORTED_PHASE")
            # Pre-existing fields preserved via the dict-update
            # merge.
            self.assertEqual(data["started_at"],
                             "2026-05-30T14:00:00Z")
            self.assertEqual(data["heartbeat"],
                             "2026-05-30T14:00:00Z")
            # State changes to DONE (the post-merge update).
            self.assertEqual(data["state"], "DONE")

    def test_phase_group_string_parses_to_first_phase_int(
            self) -> None:
        # The phase group abort site passes a string like "1+2+3"
        # (joined group label). The helper should parse the FIRST
        # phase number (the one the abort was attributed to).
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "status.json"
            os.environ["QPB_HARNESS_STATUS_PATH"] = str(path)
            RP._write_harness_abort_status(
                "4+5+6", 1, "phase group gate failed")
            data = json.loads(path.read_text())
            self.assertEqual(data["phase_aborted"], 4)

    def test_unparseable_phase_falls_back_to_minus_one(
            self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "status.json"
            os.environ["QPB_HARNESS_STATUS_PATH"] = str(path)
            RP._write_harness_abort_status(
                "?", 1, "top-level abort")
            data = json.loads(path.read_text())
            self.assertEqual(data["phase_aborted"], -1)

    def test_filesystem_error_does_not_raise(self) -> None:
        # Best-effort: a path the supervisor can't write to (e.g.,
        # a directory that doesn't exist or is read-only) must NOT
        # crash the abort flow. The supervisor still returns False
        # and the existing collector inference handles it.
        os.environ["QPB_HARNESS_STATUS_PATH"] = (
            "/no/such/dir/that/exists/status.json")
        # Should not raise.
        try:
            RP._write_harness_abort_status(
                1, 1, "phase 1 child failed")
        except OSError:
            self.fail("filesystem error should be swallowed")


# ---------------------------------------------------------------------------
# Runner-side: env var is set on Mode B Popen
# ---------------------------------------------------------------------------


class RunnerSetsStatusPathEnvForModeBTests(unittest.TestCase):
    """v1.5.7 164: bin/harness/runner.py adds
    QPB_HARNESS_STATUS_PATH to the Mode B Popen env. Mode A
    (operator-direct claude/codex/etc CLI) doesn't get the env var
    — the supervisor concept doesn't apply there."""

    def test_env_var_set_in_mode_b_sanitizer_path(self) -> None:
        # Smoke: the env-var addition lives right after
        # _sanitize_mode_b_env(env), at the Mode B-only branch.
        # Direct source inspection.
        from bin.harness import runner as R
        src = Path(R.__file__).read_text(encoding="utf-8")
        self.assertIn('env["QPB_HARNESS_STATUS_PATH"]', src)
        # The line must be inside the `Mode.B` branch (a quick
        # proximity check: the assignment appears within a
        # `if spec.axes.mode == Mode.B:` block).
        snippet = src.split(
            "if spec.axes.mode == Mode.B:")[1].split("\n\n")[0]
        self.assertIn(
            'env["QPB_HARNESS_STATUS_PATH"]', snippet,
            "QPB_HARNESS_STATUS_PATH must be set inside the "
            "Mode B branch only")


# ---------------------------------------------------------------------------
# Abort site coverage — each of the 5 sites calls the writer
# ---------------------------------------------------------------------------


class AbortSiteCoverageTests(unittest.TestCase):
    """The instruction's Task B asks for status.json write at each
    of the 5 abort sites in run_playbook.py. Source-inspection
    smoke test: ``_write_harness_abort_status(`` is called at least
    5 times in the abort-handling sections."""

    def test_abort_sites_call_writer(self) -> None:
        src = Path(RP.__file__).read_text(encoding="utf-8")
        # The helper is called at each abort site. Count call
        # references (definition is the first occurrence; the rest
        # are call sites).
        defs = src.count("def _write_harness_abort_status(")
        calls = src.count("_write_harness_abort_status(")
        self.assertEqual(defs, 1, "helper defined exactly once")
        # Definition + 6 abort-site calls (the 5 enumerated in
        # the ruling + 1 require-docs pre-flight that the worker
        # added for completeness) = 7 occurrences total. Mutation-
        # bite target: removing any abort site's call drops the
        # count below 7.
        self.assertGreaterEqual(
            calls, 7,
            f"expected ≥7 occurrences (1 def + 6 call sites); "
            f"got {calls}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
