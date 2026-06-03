"""v1.5.7 166 — collector respects the supervisor's status.json
write (closes 164's production gap).

Empirical motivation: 2026-05-30 19:42 retest's run-02 (chi
codex/gpt-5.3-codex Mode B). Phase 2 aborted on ChatGPT account
quota; the supervisor's runner.log shows the canonical 164 abort
log line; status.json on disk shows `terminal_state="FAILED"`,
`terminal_reason=""`, `exit_code=-1` — the COLLECTOR's inference
shape, NOT the supervisor's `ABORTED_PHASE` write. The 164 unit
tests passed; production failed.

Investigation finding (Task A): the env var WAS being passed to
Popen (verified at runner.py:908). The helper WAS being called.
The bug was downstream: `_write_terminal_status` in
``bin/harness/plan_runner.py`` unconditionally overwrote
status.json — even when the supervisor's 164 abort writer had
already populated `terminal_state` + `exit_code` +
`phase_aborted`.

Fix (Task B): `_write_terminal_status` now reads status.json
first; if `terminal_state` is already set, it returns without
overwriting. The supervisor's write wins.

This integration test reproduces the production failure chain:
the supervisor writes ABORTED_PHASE; the collector subsequently
tries to write FAILED; the on-disk status preserves the
supervisor's authoritative values.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from bin.harness import plan_runner as PR
from bin.harness.schema import TerminalState


class CollectorRespectsExistingTerminalStateTests(unittest.TestCase):
    """LOAD-BEARING: the collector's _write_terminal_status must
    NOT overwrite an existing terminal_state on disk. The
    supervisor (164) writes ABORTED_PHASE; the collector's
    inference would replace it with FAILED if it overwrote. Test
    asserts the supervisor's write survives."""

    def test_supervisor_aborted_phase_preserved_against_collector_inference(
            self) -> None:
        # Mutation-bite target: removing the "return early when
        # terminal_state is already set" branch makes the
        # collector clobber the supervisor's write.
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run-02"
            run_dir.mkdir()
            status_path = run_dir / "status.json"
            # Supervisor's 164 write (the SHAPE that
            # _write_harness_abort_status produces, captured
            # verbatim from a real Phase-2 abort scenario).
            supervisor_write = {
                "state": "DONE",
                "pid": 90205,
                "started_at": "2026-05-30T19:42:15Z",
                "heartbeat": "2026-05-30T19:42:15Z",
                "ended_at": "2026-05-30T19:50:23Z",
                "exit_code": 1,
                "terminal_state": "ABORTED_PHASE",
                "terminal_reason":
                    "Phase 2 aborted: child runner exited 1",
                "phase_aborted": 2,
            }
            status_path.write_text(
                json.dumps(supervisor_write), encoding="utf-8")

            # Collector now tries to write its inference (FAILED +
            # exit_code=-1 + empty terminal_reason).
            PR._write_terminal_status(
                run_dir,
                pid=90205,
                started_at="2026-05-30T19:42:15Z",
                ended_at="2026-05-30T19:50:24Z",
                terminal=TerminalState.FAILED,
                terminal_reason="",
            )

            # The on-disk status must STILL be the supervisor's
            # ABORTED_PHASE write (not the collector's FAILED).
            on_disk = json.loads(
                status_path.read_text(encoding="utf-8"))
            self.assertEqual(
                on_disk["terminal_state"], "ABORTED_PHASE",
                "collector clobbered the supervisor's write")
            self.assertEqual(on_disk["exit_code"], 1,
                              "collector overwrote exit_code")
            self.assertEqual(
                on_disk["terminal_reason"],
                "Phase 2 aborted: child runner exited 1",
                "collector overwrote terminal_reason")
            self.assertEqual(on_disk["phase_aborted"], 2,
                              "collector dropped phase_aborted")

    def test_collector_writes_inference_when_status_missing(
            self) -> None:
        # Regression guard: when there's NO existing status.json,
        # the collector's write IS the source of truth (pre-166
        # behavior preserved for the orphan-polling path).
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run-00"
            run_dir.mkdir()
            PR._write_terminal_status(
                run_dir,
                pid=42,
                started_at="2026-05-30T19:42:15Z",
                ended_at="2026-05-30T19:50:23Z",
                terminal=TerminalState.FAILED,
                terminal_reason="orphan reaped",
            )
            data = json.loads(
                (run_dir / "status.json").read_text(
                    encoding="utf-8"))
            self.assertEqual(data["terminal_state"], "FAILED")
            self.assertEqual(data["exit_code"], -1)
            self.assertEqual(data["terminal_reason"],
                              "orphan reaped")

    def test_collector_writes_inference_when_terminal_state_absent_from_existing_status(
            self) -> None:
        # If status.json exists but has no terminal_state (pre-
        # terminal RUNNING shape), the collector's inference DOES
        # write — this is the orphan polling path detecting a
        # crashed worker.
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run-00"
            run_dir.mkdir()
            (run_dir / "status.json").write_text(json.dumps({
                "state": "RUNNING", "pid": 42,
                "started_at": "2026-05-30T19:42:15Z",
                "heartbeat": "2026-05-30T19:42:15Z",
                # No terminal_state field — pre-terminal write.
            }), encoding="utf-8")
            PR._write_terminal_status(
                run_dir,
                pid=42,
                started_at="2026-05-30T19:42:15Z",
                ended_at="2026-05-30T19:50:23Z",
                terminal=TerminalState.FAILED,
                terminal_reason="pid died with no status",
            )
            data = json.loads(
                (run_dir / "status.json").read_text(
                    encoding="utf-8"))
            self.assertEqual(data["terminal_state"], "FAILED")
            self.assertEqual(data["exit_code"], -1)

    def test_collector_writes_inference_when_existing_status_unparseable(
            self) -> None:
        # Defensive: an existing-but-unparseable status.json
        # falls through to the inference write (don't lose the
        # collector's record on a corrupted file).
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run-00"
            run_dir.mkdir()
            (run_dir / "status.json").write_text(
                "{not valid json", encoding="utf-8")
            PR._write_terminal_status(
                run_dir,
                pid=42,
                started_at="2026-05-30T19:42:15Z",
                ended_at="2026-05-30T19:50:23Z",
                terminal=TerminalState.FAILED,
                terminal_reason="recovery from corruption",
            )
            data = json.loads(
                (run_dir / "status.json").read_text(
                    encoding="utf-8"))
            self.assertEqual(data["terminal_state"], "FAILED")
            self.assertEqual(data["terminal_reason"],
                              "recovery from corruption")

    def test_collector_preserves_any_existing_terminal_value(
            self) -> None:
        # Generalize: ANY existing terminal_state (KILLED,
        # COMPLETED, ABANDONED_STARVED, ABORTED_PHASE, ...) wins
        # over the collector's would-be FAILED inference.
        with tempfile.TemporaryDirectory() as td:
            for term in ("KILLED", "COMPLETED",
                          "ABANDONED_STARVED", "ABORTED_PHASE",
                          "ABORTED_PREP"):
                run_dir = Path(td) / f"run-{term}"
                run_dir.mkdir()
                (run_dir / "status.json").write_text(json.dumps({
                    "state": "DONE",
                    "pid": 42,
                    "terminal_state": term,
                }), encoding="utf-8")
                PR._write_terminal_status(
                    run_dir, pid=42,
                    started_at="2026-05-30T19:42:15Z",
                    ended_at="2026-05-30T19:50:23Z",
                    terminal=TerminalState.FAILED,
                    terminal_reason="should not win",
                )
                on_disk = json.loads(
                    (run_dir / "status.json").read_text(
                        encoding="utf-8"))
                self.assertEqual(on_disk["terminal_state"], term,
                                  f"{term} clobbered")


# ---------------------------------------------------------------------------
# Empirical real-world: the actual 19:42 run-02 status shape
# ---------------------------------------------------------------------------


_REPO_ROOT = Path(__file__).resolve().parents[3]


class RealWorldRun02EmpiricalShapeTests(unittest.TestCase):
    """The empirical evidence at
    ``harness_runs/20260530T194209Z/run-02/status.json`` is the
    pre-166 broken shape (collector clobbered the supervisor). The
    166 fix won't retroactively fix that on-disk file; this test
    pins the shape we're fixing TOWARDS (the supervisor's
    ABORTED_PHASE write surviving) by replaying the supervisor's
    write + the collector's inference on a fresh file."""

    def test_replay_19_42_shape_post_166_supervisor_wins(
            self) -> None:
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "run-02"
            run_dir.mkdir()
            # The shape the 164 supervisor would write for
            # the actual 19:42 Phase-2 abort:
            (run_dir / "status.json").write_text(json.dumps({
                "state": "DONE",
                "pid": 90205,
                "started_at": "2026-05-30T19:42:15Z",
                "heartbeat": "2026-05-30T19:50:23Z",
                "ended_at": "2026-05-30T19:50:23Z",
                "exit_code": 1,
                "terminal_state": "ABORTED_PHASE",
                "terminal_reason":
                    "Phase 2 aborted: child runner exited 1",
                "phase_aborted": 2,
                "pid_aborter": 90205,
            }), encoding="utf-8")
            # Collector inference (the pre-166 clobber):
            PR._write_terminal_status(
                run_dir, pid=90205,
                started_at="2026-05-30T19:42:15Z",
                ended_at="2026-05-30T19:50:24Z",
                terminal=TerminalState.FAILED,
                terminal_reason="",
            )
            after = json.loads(
                (run_dir / "status.json").read_text(
                    encoding="utf-8"))
            # Post-166: supervisor's authoritative shape survives.
            self.assertEqual(after["terminal_state"],
                              "ABORTED_PHASE")
            self.assertEqual(after["phase_aborted"], 2)
            self.assertEqual(after["exit_code"], 1)
            self.assertTrue(after["terminal_reason"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
