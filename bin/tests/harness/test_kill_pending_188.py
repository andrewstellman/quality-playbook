"""v1.5.7 188 — `kill` subcommand cancels PENDING runs.

Andrew's 2026-06-02 22:29 fire (`harness_runs/20260602T222932Z`)
exposed the pre-188 contract gap: `kill <harness-run>` SIGKILLs
RUNNING rows but SKIPS PENDING rows. The collector's PENDING-
retry loop (post-186 FINDING-30 — deadline removed) then auto-
launches the PENDING rows when a slot frees — exactly the
opposite of what the operator wanted when they typed `kill` to
stop the plan.

188 inverts: kill on a harness-run cancels every PENDING entry
in the manifest, writing a new CANCELLED terminal_state. The
collector's `state == "PENDING"` filter naturally skips
CANCELLED entries (their state moves to "DONE" with
terminal_state="CANCELLED"), so no separate guard is needed in
the retry path.

Coverage:
- FINDING-41: kill path branches PENDING into pending_to_cancel.
- FINDING-42: CANCELLED enum value + cancel_pending_run helper.
- FINDING-43: status output renders CANCELLED as its own section.
"""
from __future__ import annotations

import io
import json
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

_REPO = pathlib.Path(__file__).resolve().parents[3]


def _make_pending_manifest(hr: pathlib.Path,
                            indices: "list[int]") -> None:
    """Synthesize a minimal manifest with PENDING entries at
    the given indices. Each gets a sibling run-NN dir so
    read_run_status can find it."""
    runs = []
    for idx in indices:
        run_dir = hr / f"run-{idx:02d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        runs.append({
            "index": idx,
            "state": "PENDING",
            "pid": None,
            "runner": "claude",
            "model": "opus",
            "mode": "A",
            "channel": "pip-local-wheel",
            "repo": f"https://github.com/x/y{idx}",
            "ref": "HEAD",
            "description": f"row{idx}",
            "run_dir": str(run_dir),
        })
    (hr / "manifest.json").write_text(json.dumps({
        "harness_run_dir": str(hr),
        "runs": runs,
    }) + "\n", encoding="utf-8")


class CancelledEnumTests(unittest.TestCase):
    """v1.5.7 188 FINDING-42: TerminalState.CANCELLED is in
    the enum + recognized as terminal across the codebase."""

    def test_cancelled_enum_value_present(self) -> None:
        from bin.harness.schema import TerminalState
        self.assertEqual(
            TerminalState.CANCELLED.value, "CANCELLED")

    def test_cancelled_is_in_terminal_run_states(self) -> None:
        # The status classifier's _TERMINAL_RUN_STATES must
        # include CANCELLED — without it, the 121 phase-state
        # reconciliation logic won't fire for cancelled rows.
        from bin.harness import status as _status
        self.assertIn(
            "CANCELLED", _status._TERMINAL_RUN_STATES,
            "_TERMINAL_RUN_STATES must include CANCELLED "
            "(188 FINDING-42).")

    def test_cancelled_in_terminal_cancelled_set(
            self) -> None:
        from bin.harness import status as _status
        self.assertIn(
            "CANCELLED",
            _status._TERMINAL_CANCELLED_STATES)


class CancelPendingHelperTests(unittest.TestCase):
    """v1.5.7 188 FINDING-42: plan_runner.cancel_pending_run
    transitions a PENDING manifest entry to CANCELLED."""

    def test_helper_exists(self) -> None:
        from bin.harness import plan_runner
        self.assertTrue(
            hasattr(plan_runner, "cancel_pending_run"))
        self.assertTrue(
            hasattr(plan_runner, "CancelPendingError"))

    def test_cancel_writes_cancelled_terminal_state(
            self) -> None:
        from bin.harness import plan_runner
        with tempfile.TemporaryDirectory() as td:
            hr = pathlib.Path(td) / "20260602T000000Z"
            hr.mkdir()
            _make_pending_manifest(hr, [3])
            plan_runner.cancel_pending_run(hr, 3)
            on_disk = json.loads(
                (hr / "manifest.json").read_text())
            entry = on_disk["runs"][0]
            self.assertEqual(entry["state"], "DONE")
            self.assertEqual(
                entry["terminal_state"], "CANCELLED")
            self.assertEqual(
                entry["terminal_reason"],
                "cancelled by operator before launch")
            self.assertIn("ended_at", entry)

    def test_cancel_rejects_non_pending(self) -> None:
        from bin.harness import plan_runner
        with tempfile.TemporaryDirectory() as td:
            hr = pathlib.Path(td) / "20260602T000000Z"
            hr.mkdir()
            (hr / "manifest.json").write_text(json.dumps({
                "harness_run_dir": str(hr),
                "runs": [{
                    "index": 0, "state": "RUNNING",
                    "pid": 99, "runner": "claude",
                    "model": "opus",
                }],
            }) + "\n", encoding="utf-8")
            with self.assertRaises(
                    plan_runner.CancelPendingError) as ctx:
                plan_runner.cancel_pending_run(hr, 0)
            self.assertIn("not PENDING", str(ctx.exception))

    def test_cancel_rejects_unknown_index(self) -> None:
        from bin.harness import plan_runner
        with tempfile.TemporaryDirectory() as td:
            hr = pathlib.Path(td) / "20260602T000000Z"
            hr.mkdir()
            _make_pending_manifest(hr, [0])
            with self.assertRaises(
                    plan_runner.CancelPendingError):
                plan_runner.cancel_pending_run(hr, 999)


class CollectorSkipsCancelledTests(unittest.TestCase):
    """v1.5.7 188 FINDING-42: the collector's PENDING-retry
    loop skips entries whose state has moved to CANCELLED."""

    def test_retry_pending_does_not_pick_up_cancelled(
            self) -> None:
        from bin.harness import plan_runner
        from unittest import mock
        with tempfile.TemporaryDirectory() as td:
            hr = pathlib.Path(td) / "20260602T000000Z"
            hr.mkdir()
            _make_pending_manifest(hr, [0])
            # Cancel the entry first.
            plan_runner.cancel_pending_run(hr, 0)
            # Now run the retry loop and confirm it doesn't
            # try to acquire a slot for the CANCELLED entry.
            with mock.patch.object(
                    plan_runner, "_try_acquire_pool_slot"
            ) as m_acquire:
                transitions = plan_runner._retry_pending_runs_once(
                    hr)
            self.assertEqual(
                transitions, 0,
                "CANCELLED entries must not produce "
                "transitions in the retry pass.")
            m_acquire.assert_not_called()


class KillCmdCancelsPendingTests(unittest.TestCase):
    """v1.5.7 188 FINDING-41: `qpb_harness kill <harness-run>`
    cancels PENDING rows in addition to SIGKILLing RUNNING
    rows. End-to-end CLI test."""

    def test_kill_harness_run_cancels_pending(self) -> None:
        from bin import qpb_harness_legacy as qpb_harness
        with tempfile.TemporaryDirectory() as td:
            hr = pathlib.Path(td) / "20260602T222932Z"
            hr.mkdir()
            # 3 PENDING + 0 RUNNING (RUNNING-kill is tested
            # elsewhere; this test isolates the cancel path).
            _make_pending_manifest(hr, [0, 1, 2])
            buf = io.StringIO()
            with redirect_stdout(buf), \
                 redirect_stderr(io.StringIO()):
                rc = qpb_harness.main(
                    ["kill", "-y", str(hr)])
            self.assertEqual(rc, 0)
            output = buf.getvalue()
            self.assertIn(
                "Cancelled:", output,
                "kill on harness-run with PENDING rows must "
                "report under 'Cancelled:' (188 FINDING-41).")
            # All 3 entries now CANCELLED.
            on_disk = json.loads(
                (hr / "manifest.json").read_text())
            for entry in on_disk["runs"]:
                self.assertEqual(
                    entry.get("terminal_state"), "CANCELLED")

    def test_kill_with_no_pending_or_running_reports_correctly(
            self) -> None:
        # No RUNNING + no PENDING (only a terminal row) ⇒
        # "No running runs to kill and no pending runs to
        # cancel." Replaces the pre-188 "No running runs to
        # kill." message.
        from bin import qpb_harness_legacy as qpb_harness
        with tempfile.TemporaryDirectory() as td:
            hr = pathlib.Path(td) / "20260602T222932Z"
            hr.mkdir()
            (hr / "run-00").mkdir()
            (hr / "manifest.json").write_text(json.dumps({
                "harness_run_dir": str(hr),
                "runs": [{
                    "index": 0,
                    "state": "DONE",
                    "terminal_state": "COMPLETED",
                    "pid": 99,
                    "runner": "claude",
                    "model": "opus",
                    "mode": "A",
                    "channel": "pip-local-wheel",
                    "repo": "https://github.com/x/y",
                    "ref": "HEAD",
                    "description": "row0",
                    "run_dir": str(hr / "run-00"),
                }],
            }) + "\n", encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf), \
                 redirect_stderr(io.StringIO()):
                rc = qpb_harness.main(
                    ["kill", "-y", str(hr)])
            self.assertEqual(rc, 0)
            self.assertIn(
                "no pending runs to cancel",
                buf.getvalue().lower(),
                "no-runnable case must mention pending "
                "cancellation availability (188 FINDING-41).")


class StatusRendersCancelledTests(unittest.TestCase):
    """v1.5.7 188 FINDING-43: format_runs_grouped renders
    CANCELLED rows in their own section between COMPLETED
    and FAILED."""

    def test_cancelled_section_appears(self) -> None:
        from bin.harness import status as _status
        with tempfile.TemporaryDirectory() as td:
            hr = pathlib.Path(td) / "20260602T222932Z"
            hr.mkdir()
            _make_pending_manifest(hr, [0])
            # Cancel it.
            from bin.harness import plan_runner
            plan_runner.cancel_pending_run(hr, 0)
            # Read + render.
            runs = _status.read_run_status(hr)
            rendered = _status.format_runs_grouped(runs)
            self.assertIn(
                "CANCELLED (1):", rendered,
                "format_runs_grouped must render a "
                "'CANCELLED (N):' header (188 FINDING-43).")
            self.assertIn(
                "cancelled by operator before launch",
                rendered,
                "CANCELLED row must surface the operator-"
                "facing reason.")


class AcquirePoolSlotRaceTests(unittest.TestCase):
    """v1.5.7 188 (Panelist A + B Council fix): the race
    where _try_acquire_pool_slot rewrites state=ACQUIRING on
    an entry that cancel_pending_run flipped to CANCELLED
    inside the same lock window. Fix is a one-line re-check
    of state inside the lock before the rewrite."""

    def test_acquire_rejects_cancelled_entry(self) -> None:
        # Synthesize a manifest with a CANCELLED entry.
        # _try_acquire_pool_slot must NOT rewrite it to
        # ACQUIRING; it must return False.
        from bin.harness import plan_runner
        with tempfile.TemporaryDirectory() as td:
            hr = pathlib.Path(td) / "20260602T000000Z"
            hr.mkdir()
            (hr / "manifest.json").write_text(json.dumps({
                "harness_run_dir": str(hr),
                "runs": [{
                    "index": 0,
                    "state": "DONE",
                    "terminal_state": "CANCELLED",
                    "pid": None,
                    "runner": "claude",
                    "model": "opus",
                }],
            }) + "\n", encoding="utf-8")
            manifest_path = hr / "manifest.json"
            acquired = plan_runner._try_acquire_pool_slot(
                manifest_path,
                runner="claude",
                pool_size=1,
                run_index=0,
                started_at="2026-06-02T22:30:00Z")
            self.assertFalse(
                acquired,
                "_try_acquire_pool_slot must return False "
                "when the entry's state is not PENDING "
                "(188 Panelist A/B race fix).")
            # Manifest entry must be unchanged (still
            # CANCELLED, not ACQUIRING).
            on_disk = json.loads(manifest_path.read_text())
            self.assertEqual(on_disk["runs"][0]["state"],
                             "DONE")
            self.assertEqual(
                on_disk["runs"][0]["terminal_state"],
                "CANCELLED")


class HarnessRunSummaryCancelledCountTests(unittest.TestCase):
    """v1.5.7 188 FINDING-43 (Panelist C): HarnessRunSummary
    must have a `cancelled` field + `_summarize_harness_run`
    must increment it on CANCELLED state. Pre-fix CANCELLED
    rows fell through to `pending`, silently miscounting
    operator-cancelled rows as still queued (same shape as
    113's BLOCKED fix)."""

    def test_summary_dataclass_has_cancelled_field(
            self) -> None:
        from bin.harness import status as _status
        import dataclasses
        fields = {
            f.name for f in
            dataclasses.fields(_status.HarnessRunSummary)}
        self.assertIn(
            "cancelled", fields,
            "HarnessRunSummary must have a `cancelled` "
            "int field (188 FINDING-43 Panelist C).")

    def test_summarize_counts_cancelled_separately(
            self) -> None:
        # Synthesize a harness-run with 1 CANCELLED + 1
        # PENDING and verify the summary reports cancelled=1
        # AND pending=1 — NOT pending=2.
        from bin.harness import status as _status
        from bin.harness import plan_runner
        with tempfile.TemporaryDirectory() as td:
            hr = pathlib.Path(td) / "20260602T000000Z"
            hr.mkdir()
            _make_pending_manifest(hr, [0, 1])
            # Cancel index 0.
            plan_runner.cancel_pending_run(hr, 0)
            summary = _status._summarize_harness_run(hr)
            self.assertEqual(
                summary.cancelled, 1,
                "Cancelled row must be counted as cancelled, "
                "not pending (188 FINDING-43 Panelist C).")
            self.assertEqual(
                summary.pending, 1,
                "Remaining PENDING row must NOT be inflated "
                "by miscounted cancelled.")

    def test_format_harness_run_summary_includes_c_column(
            self) -> None:
        # Source-pin: the CLI summary row format string
        # contains `C=` after `P=`.
        from bin.harness import status as _status
        src = (_REPO / "bin" / "harness" / "status.py"
               ).read_text(encoding="utf-8")
        self.assertIn(
            'f"C={summary.cancelled', src,
            "format_harness_run_summary must surface a C= "
            "column (188 FINDING-43 Panelist C).")

    def test_tui_runs_table_includes_c_column(self) -> None:
        from bin.harness import tui
        self.assertIn(
            "C", tui.RUNS_TABLE_COLUMNS,
            "TUI RUNS_TABLE_COLUMNS must include a 'C' "
            "column (188 FINDING-43 Panelist C).")
        # Arity contract from 119: row tuples match column count.
        with tempfile.TemporaryDirectory() as td:
            runs_root = pathlib.Path(td) / "runs"
            runs_root.mkdir()
            hr = runs_root / "20260602T000000Z"
            hr.mkdir()
            (hr / "manifest.json").write_text(json.dumps({
                "harness_run_dir": str(hr),
                "runs": [],
            }) + "\n", encoding="utf-8")
            rows = tui.build_runs_table_rows(runs_root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(
                len(rows[0]), len(tui.RUNS_TABLE_COLUMNS),
                "Arity contract: row matches COLUMNS count")


if __name__ == "__main__":
    unittest.main()
