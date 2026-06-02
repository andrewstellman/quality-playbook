"""v1.5.7 186 FINDING-30: source-pin sweeps that prove the
ABANDONED_STARVED deadline + auto-kill path is gone from
plan_runner.py. The 1-hour PENDING deadline killed legitimate
pool=1 sequential plans (run 20260602T051446Z fire: 7 ×
~45min rows; rows #3-#6 hit the deadline before they could
start). Replacement: pending-duration display + collector
heartbeat (FINDING-31) + force-run UX (FINDING-32 / 33).

The TerminalState.ABANDONED_STARVED enum value is preserved
for backward-compat with existing harness_runs/ folders that
were written before 186 — they may have entries with that
terminal_state and the parser/renderer must still recognize
the value. The DEFAULT auto-kill that wrote it is what's
removed."""
from __future__ import annotations

import pathlib
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[3]


class NoDeadlineDeathTests(unittest.TestCase):
    """v1.5.7 186 FINDING-30: PENDING runs do NOT get marked
    ABANDONED_STARVED on any deadline. The collector keeps
    retrying when slots free; deadline auto-kill is gone."""

    def test_no_pending_deadline_function_in_plan_runner(
            self) -> None:
        # Source-pin: plan_runner.py NO LONGER defines
        # `_PENDING_DEADLINE_DEFAULT_S` constant or the
        # `_pending_deadline_s` function. Catches a future
        # regression that re-introduces the deadline path.
        src = (_REPO / "bin" / "harness" / "plan_runner.py"
               ).read_text(encoding="utf-8")
        self.assertNotIn(
            "_PENDING_DEADLINE_DEFAULT_S", src,
            "_PENDING_DEADLINE_DEFAULT_S re-introduced; "
            "the 186 FINDING-30 deletion is being reverted.")
        self.assertNotIn(
            "def _pending_deadline_s(", src,
            "_pending_deadline_s function re-introduced; "
            "the 186 FINDING-30 deletion is being reverted.")

    def test_no_pending_deadline_env_var_in_plan_runner(
            self) -> None:
        # Source-pin: `QPB_HARNESS_PENDING_DEADLINE_S` env var
        # is no longer parsed in plan_runner.py.
        src = (_REPO / "bin" / "harness" / "plan_runner.py"
               ).read_text(encoding="utf-8")
        self.assertNotIn(
            "QPB_HARNESS_PENDING_DEADLINE_S", src,
            "QPB_HARNESS_PENDING_DEADLINE_S env var "
            "parsing re-introduced; the 186 FINDING-30 "
            "deletion is being reverted.")

    def test_no_abandoned_starved_write_in_plan_runner(
            self) -> None:
        # Source-pin: plan_runner.py does NOT contain
        # ``"terminal_state": "ABANDONED_STARVED"`` (the
        # specific write that the deleted path emitted). The
        # enum value itself stays in schema.py for
        # backward-compat with pre-186 harness_runs/ folders.
        src = (_REPO / "bin" / "harness" / "plan_runner.py"
               ).read_text(encoding="utf-8")
        self.assertNotIn(
            '"terminal_state": "ABANDONED_STARVED"', src,
            "plan_runner.py still writes "
            "terminal_state=ABANDONED_STARVED; the 186 "
            "FINDING-30 auto-kill path is being reverted.")

    def test_pending_run_past_old_deadline_stays_pending(
            self) -> None:
        # Behavioral check: synthesize a manifest with a
        # PENDING entry whose starved_since is 5 hours ago,
        # mock the slot-acquire to fail, then call the retry
        # helper. The entry must stay PENDING (no
        # ABANDONED_STARVED transition).
        from bin.harness import plan_runner
        from unittest import mock
        from datetime import datetime, timezone, timedelta
        import tempfile, json
        from pathlib import Path
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260602T051446Z"
            hr.mkdir()
            way_past = (datetime.now(timezone.utc)
                        - timedelta(hours=5)).strftime(
                            "%Y-%m-%dT%H:%M:%SZ")
            mp = hr / "manifest.json"
            mp.write_text(json.dumps({
                "harness_run_dir": str(hr),
                "plan": {"pools": {"claude": 1}},
                "runs": [{
                    "index": 0,
                    "state": "PENDING",
                    "pid": None,
                    "runner": "claude",
                    "model": "opus",
                    "mode": "A",
                    "channel": "pip-local-wheel",
                    "repo": "https://github.com/x/y",
                    "ref": "HEAD",
                    "description": "synthetic",
                    "run_dir": str(hr / "run-00"),
                    "starved_since": way_past,
                }],
            }) + "\n", encoding="utf-8")
            (hr / "run-00").mkdir()
            # Pool full — slot-acquire fails. Pre-186 the
            # deadline path would have transitioned to
            # ABANDONED_STARVED; post-186 nothing happens.
            with mock.patch.object(
                    plan_runner, "_try_acquire_pool_slot",
                    return_value=False):
                transitions = plan_runner._retry_pending_runs_once(
                    hr)
            self.assertEqual(transitions, 0)
            data = json.loads(mp.read_text())
            self.assertEqual(
                data["runs"][0]["state"], "PENDING",
                "Entry must stay PENDING — pre-186 it would "
                "have been ABANDONED_STARVED.")
            self.assertNotIn(
                "terminal_state", data["runs"][0],
                "No terminal_state may be written.")


class PendingDurationDisplayTests(unittest.TestCase):
    """v1.5.7 186 FINDING-31a: status / TUI surface
    ``pending Nh Mm`` for PENDING rows so the operator sees
    how long a row has waited — replaces the pre-186
    deadline auto-kill with explicit information."""

    def test_format_pending_duration_renders_hours_minutes(
            self) -> None:
        from bin.harness import status as _status
        from datetime import datetime, timezone, timedelta
        past = (datetime.now(timezone.utc)
                - timedelta(hours=4, minutes=12)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
        rendered = _status._format_pending_duration(past)
        self.assertEqual(rendered, "pending 4h12m")

    def test_format_pending_duration_renders_minutes_only(
            self) -> None:
        from bin.harness import status as _status
        from datetime import datetime, timezone, timedelta
        past = (datetime.now(timezone.utc)
                - timedelta(minutes=45)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ")
        rendered = _status._format_pending_duration(past)
        self.assertEqual(rendered, "pending 45m")

    def test_format_pending_duration_handles_none_and_garbage(
            self) -> None:
        from bin.harness import status as _status
        self.assertEqual(
            _status._format_pending_duration(None), "")
        self.assertEqual(
            _status._format_pending_duration("not iso"), "")
        # Negative age (clock skew) → empty.
        self.assertEqual(
            _status._format_pending_duration("2099-01-01T00:00:00Z"),
            "")

    def test_run_status_dataclass_carries_pending_duration(
            self) -> None:
        # The dataclass must have a `pending_duration` field
        # with empty-string default (only populated for
        # PENDING rows).
        from bin.harness import status as _status
        import dataclasses
        rs_fields = {
            f.name: f for f in
            dataclasses.fields(_status.RunStatus)}
        self.assertIn("pending_duration", rs_fields)
        self.assertEqual(
            rs_fields["pending_duration"].default, "")


class CollectorHeartbeatHealthTests(unittest.TestCase):
    """v1.5.7 186 FINDING-31b: status surfaces collector +
    watchdog heartbeat age (`last heartbeat 2s ago (alive)`
    / `last heartbeat 8h2m ago (DIED?)`) so the operator
    sees the actual signal the pre-186 ABANDONED_STARVED
    deadline was implicitly proxying for."""

    def test_format_heartbeat_health_alive(self) -> None:
        from bin.harness import status as _status
        out = _status.format_heartbeat_health(2.5)
        self.assertEqual(out, "last heartbeat 2s ago (alive)")

    def test_format_heartbeat_health_died_long(self) -> None:
        from bin.harness import status as _status
        out = _status.format_heartbeat_health(8 * 3600 + 120)
        self.assertEqual(
            out, "last heartbeat 8h02m ago (DIED?)")

    def test_format_heartbeat_health_died_minutes(
            self) -> None:
        from bin.harness import status as _status
        # 5 minutes (300s) > 60s window → DIED.
        out = _status.format_heartbeat_health(300)
        self.assertEqual(out, "last heartbeat 5m ago (DIED?)")

    def test_format_heartbeat_health_not_started(
            self) -> None:
        from bin.harness import status as _status
        self.assertEqual(
            _status.format_heartbeat_health(None),
            "not started")

    def test_harness_run_summary_carries_heartbeat_ages(
            self) -> None:
        # The dataclass gained two optional Float fields for
        # collector + watchdog heartbeat age in seconds.
        from bin.harness import status as _status
        import dataclasses
        s_fields = {
            f.name: f for f in
            dataclasses.fields(_status.HarnessRunSummary)}
        self.assertIn("collector_heartbeat_age_s", s_fields)
        self.assertIn("watchdog_heartbeat_age_s", s_fields)


class ForceRunHelperTests(unittest.TestCase):
    """v1.5.7 186 FINDING-33: force_launch_pending_run +
    force_launch_all_pending_in_dir helpers launch PENDING
    rows OUT OF POOL (bypassing _try_acquire_pool_slot)."""

    def test_force_run_helper_exists(self) -> None:
        from bin.harness import plan_runner
        self.assertTrue(hasattr(
            plan_runner, "force_launch_pending_run"))
        self.assertTrue(hasattr(
            plan_runner, "force_launch_all_pending_in_dir"))
        self.assertTrue(hasattr(plan_runner, "ForceRunError"))

    def test_force_run_raises_on_missing_manifest(
            self) -> None:
        from bin.harness import plan_runner
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            hr = pathlib.Path(td) / "20260602T000000Z"
            hr.mkdir()
            with self.assertRaises(plan_runner.ForceRunError):
                plan_runner.force_launch_pending_run(hr, 0)

    def test_force_run_raises_on_unknown_index(self) -> None:
        from bin.harness import plan_runner
        import tempfile, json
        with tempfile.TemporaryDirectory() as td:
            hr = pathlib.Path(td) / "20260602T000000Z"
            hr.mkdir()
            (hr / "manifest.json").write_text(json.dumps({
                "harness_run_dir": str(hr),
                "runs": [{"index": 0, "state": "PENDING"}],
            }) + "\n", encoding="utf-8")
            with self.assertRaises(plan_runner.ForceRunError):
                plan_runner.force_launch_pending_run(hr, 999)

    def test_force_run_raises_on_non_pending_entry(
            self) -> None:
        from bin.harness import plan_runner
        import tempfile, json
        with tempfile.TemporaryDirectory() as td:
            hr = pathlib.Path(td) / "20260602T000000Z"
            hr.mkdir()
            (hr / "manifest.json").write_text(json.dumps({
                "harness_run_dir": str(hr),
                "runs": [{
                    "index": 0,
                    "state": "RUNNING",
                    "pid": 12345,
                }],
            }) + "\n", encoding="utf-8")
            with self.assertRaises(
                    plan_runner.ForceRunError) as ctx:
                plan_runner.force_launch_pending_run(hr, 0)
            self.assertIn("not PENDING", str(ctx.exception))

    def test_force_run_bypasses_pool_acquire(self) -> None:
        # Functional: synthesize a PENDING entry with pool=1
        # AND a RUNNING entry already consuming the slot.
        # force_launch_pending_run should launch the PENDING
        # without calling _try_acquire_pool_slot.
        from bin.harness import plan_runner
        from unittest import mock
        import tempfile, json
        with tempfile.TemporaryDirectory() as td:
            hr = pathlib.Path(td) / "20260602T000000Z"
            hr.mkdir()
            (hr / "run-00").mkdir()
            (hr / "run-01").mkdir()
            (hr / "manifest.json").write_text(json.dumps({
                "harness_run_dir": str(hr),
                "plan": {"pools": {"claude": 1}},
                "runs": [
                    {"index": 0, "state": "RUNNING",
                     "pid": 7777, "runner": "claude",
                     "model": "opus",
                     "repo": "https://github.com/x/y0",
                     "run_dir": str(hr / "run-00")},
                    {"index": 1, "state": "PENDING",
                     "pid": None, "runner": "claude",
                     "model": "opus",
                     "mode": "A", "channel": "pip-local-wheel",
                     "repo": "https://github.com/x/y1",
                     "ref": "HEAD",
                     "description": "force-run target",
                     "run_dir": str(hr / "run-01")},
                ],
            }) + "\n", encoding="utf-8")
            # Mock the spawn helper so we don't actually spawn.
            mock_spawn_result = {
                "index": 1, "pid": 9999,
                "runner": "claude", "model": "opus",
                "repo": "https://github.com/x/y1",
                "channel": "pip-local-wheel",
                "mode": "A", "run_dir": str(hr / "run-01"),
            }
            with mock.patch.object(
                    plan_runner, "_launch_one_run_detached",
                    return_value=mock_spawn_result) as m_spawn, \
                 mock.patch.object(
                    plan_runner, "_try_acquire_pool_slot"
                 ) as m_acquire:
                result = plan_runner.force_launch_pending_run(
                    hr, 1)
            # CRITICAL: _try_acquire_pool_slot must NOT have
            # been called — that's the whole point of force-run.
            m_acquire.assert_not_called()
            m_spawn.assert_called_once()
            self.assertEqual(result["index"], 1)
            self.assertEqual(result["pid"], 9999)
            # Manifest should now show the entry as RUNNING.
            on_disk = json.loads(
                (hr / "manifest.json").read_text())
            entry = next(
                e for e in on_disk["runs"]
                if e["index"] == 1)
            self.assertEqual(entry["state"], "RUNNING")
            # Live count after = 2 (the pre-existing RUNNING
            # + the force-launched one).
            self.assertEqual(result["live_count_after"], 2)

    def test_force_run_all_pending_ignores_non_pending(
            self) -> None:
        # Mixed manifest: 1 RUNNING + 2 PENDING + 1 DONE.
        # force_launch_all should launch ONLY the 2 PENDING.
        from bin.harness import plan_runner
        from unittest import mock
        import tempfile, json
        with tempfile.TemporaryDirectory() as td:
            hr = pathlib.Path(td) / "20260602T000000Z"
            hr.mkdir()
            for i in range(4):
                (hr / f"run-{i:02d}").mkdir()
            (hr / "manifest.json").write_text(json.dumps({
                "harness_run_dir": str(hr),
                "plan": {"pools": {"claude": 1}},
                "runs": [
                    {"index": 0, "state": "RUNNING",
                     "pid": 1, "runner": "claude",
                     "model": "opus",
                     "repo": "https://github.com/x/y0",
                     "run_dir": str(hr / "run-00")},
                    {"index": 1, "state": "PENDING",
                     "pid": None, "runner": "claude",
                     "model": "opus", "mode": "A",
                     "channel": "pip-local-wheel",
                     "repo": "https://github.com/x/y1",
                     "ref": "HEAD",
                     "description": "row1",
                     "run_dir": str(hr / "run-01")},
                    {"index": 2, "state": "PENDING",
                     "pid": None, "runner": "claude",
                     "model": "opus", "mode": "A",
                     "channel": "pip-local-wheel",
                     "repo": "https://github.com/x/y2",
                     "ref": "HEAD",
                     "description": "row2",
                     "run_dir": str(hr / "run-02")},
                    {"index": 3, "state": "DONE",
                     "terminal_state": "COMPLETED",
                     "runner": "claude", "model": "opus",
                     "repo": "https://github.com/x/y3",
                     "run_dir": str(hr / "run-03")},
                ],
            }) + "\n", encoding="utf-8")
            call_count = [0]
            def _spawn_mock(pr, *a, **kw):
                call_count[0] += 1
                return {
                    "index": pr.index, "pid": 9000 + pr.index,
                    "runner": "claude", "model": "opus",
                    "repo": f"https://github.com/x/y{pr.index}",
                    "channel": "pip-local-wheel",
                    "mode": "A",
                    "run_dir": str(hr / f"run-{pr.index:02d}"),
                }
            with mock.patch.object(
                    plan_runner, "_launch_one_run_detached",
                    side_effect=_spawn_mock):
                results = (
                    plan_runner.force_launch_all_pending_in_dir(
                        hr))
            # Only the 2 PENDING rows attempted.
            self.assertEqual(call_count[0], 2)
            self.assertEqual(len(results), 2)
            self.assertEqual(
                {r["index"] for r in results},
                {1, 2})


class TuiForceExecuteKeybindingTests(unittest.TestCase):
    """v1.5.7 186 FINDING-32: TUI 'E' keybinding pushes a
    force-execute confirmation modal for the highlighted
    PENDING row, then invokes
    ``plan_runner.force_launch_pending_run`` on confirm."""

    def test_tui_has_e_force_run_binding(self) -> None:
        # Source-pin: tui.py BINDINGS list contains the
        # ``Binding("e", "force_run", ...)`` entry.
        src = (_REPO / "bin" / "harness" / "tui.py"
               ).read_text(encoding="utf-8")
        self.assertIn(
            'Binding("e", "force_run"', src,
            "tui.py BINDINGS must include 'e' force-run "
            "keybinding (186 FINDING-32).")

    def test_tui_has_action_force_run_handler(self) -> None:
        # Source-pin: the action method exists.
        src = (_REPO / "bin" / "harness" / "tui.py"
               ).read_text(encoding="utf-8")
        self.assertIn(
            "def action_force_run(self)", src,
            "tui.py must define action_force_run (186 "
            "FINDING-32).")

    def test_tui_force_run_calls_helper(self) -> None:
        # Source-pin: the action invokes the headless
        # ``plan_runner.force_launch_pending_run`` helper.
        src = (_REPO / "bin" / "harness" / "tui.py"
               ).read_text(encoding="utf-8")
        self.assertIn(
            "force_launch_pending_run(", src,
            "tui.py must call "
            "plan_runner.force_launch_pending_run (186 "
            "FINDING-32 — reuses the FINDING-33 helper).")

    def test_tui_force_run_only_on_pending_state(
            self) -> None:
        # Source-pin: the action checks `rs.state == "PENDING"`
        # before pushing the modal. Catches a regression where
        # the keybinding becomes always-active.
        src = (_REPO / "bin" / "harness" / "tui.py"
               ).read_text(encoding="utf-8")
        # Look for the state check within the
        # action_force_run body.
        import re
        m = re.search(
            r"def action_force_run.*?(?=\n        def )",
            src, re.DOTALL)
        self.assertIsNotNone(m)
        body = m.group(0)
        self.assertIn(
            'rs.state != "PENDING"', body,
            "action_force_run must gate on rs.state == "
            "PENDING (186 FINDING-32 — the keybinding is "
            "only available on PENDING rows).")


class PendingDurationDisplaySurfacingTests(unittest.TestCase):
    """v1.5.7 186 followup-1 FINDING-34 + FINDING-35: the
    ``pending Nh Mm`` duration must appear in BOTH the CLI
    grouped view (status output operators actually use) AND
    the TUI detail table — not just the single-run drill-
    down. The pre-followup commit landed the data layer
    (RunStatus.pending_duration) but missed the display
    surface."""

    def _make_pending_runstatus(self, hours_ago: float = 4.2):
        from bin.harness import status as _status
        from datetime import datetime, timezone, timedelta
        from pathlib import Path as _P
        starved = (datetime.now(timezone.utc)
                   - timedelta(hours=hours_ago)).strftime(
                       "%Y-%m-%dT%H:%M:%SZ")
        return _status.RunStatus(
            index=3,
            description="setuptools",
            repo="https://github.com/x/setuptools",
            runner="claude",
            model="opus",
            state="PENDING",
            result="N/A",
            current_phase="—",
            current_phase_name="—",
            current_phase_state="—",
            last_note="",
            pid=None,
            pid_alive=False,
            stream_path=_P("/dev/null"),
            run_dir=_P("/tmp/x/run-03"),
            pending_duration=_status._format_pending_duration(
                starved),
        )

    def test_pending_group_renderer_shows_pending_duration(
            self) -> None:
        from bin.harness import status as _status
        rs = self._make_pending_runstatus(hours_ago=4.2)
        rendered = _status._format_run_row_for_group(
            rs, "PENDING")
        self.assertIn("pending 4h", rendered,
            f"PENDING-group renderer must surface "
            f"pending_duration (186 FINDING-34). Got: "
            f"{rendered!r}")

    def test_tui_detail_state_cell_includes_pending_duration(
            self) -> None:
        # Functional: synthesize a manifest with a PENDING
        # row + starved_since; build the detail-table rows;
        # assert the state cell contains both 'PENDING' and
        # 'pending'.
        from bin.harness import tui
        from datetime import datetime, timezone, timedelta
        import tempfile, json
        with tempfile.TemporaryDirectory() as td:
            hr = pathlib.Path(td) / "20260602T000000Z"
            run_dir = hr / "run-03"
            run_dir.mkdir(parents=True)
            starved = (datetime.now(timezone.utc)
                       - timedelta(hours=2, minutes=7)
                       ).strftime("%Y-%m-%dT%H:%M:%SZ")
            (hr / "manifest.json").write_text(json.dumps({
                "harness_run_dir": str(hr),
                "plan": {"pools": {"claude": 1}},
                "runs": [{
                    "index": 3,
                    "state": "PENDING",
                    "pid": None,
                    "runner": "claude",
                    "model": "opus",
                    "mode": "A",
                    "channel": "pip-local-wheel",
                    "repo": "https://github.com/x/setuptools",
                    "ref": "HEAD",
                    "description": "row3",
                    "run_dir": str(run_dir),
                    "starved_since": starved,
                }],
            }) + "\n", encoding="utf-8")
            rows = tui.build_detail_table_rows(hr)
            self.assertEqual(len(rows), 1)
            cells = rows[0]
            # State cell is the 4th column (index 3) per
            # DETAIL_TABLE_COLUMNS.
            state_cell = cells[3]
            self.assertIn(
                "PENDING", state_cell,
                f"state cell must still include 'PENDING' "
                f"(state-name preserved). Got: "
                f"{state_cell!r}")
            self.assertIn(
                "pending", state_cell,
                f"state cell must include the pending-"
                f"duration prefix for PENDING rows "
                f"(186 FINDING-35). Got: {state_cell!r}")
            self.assertIn(
                "2h", state_cell,
                f"state cell should include the duration "
                f"value (2h07m here). Got: {state_cell!r}")
            # Arity contract: row matches column count.
            self.assertEqual(
                len(cells), len(tui.DETAIL_TABLE_COLUMNS),
                "row arity must match COLUMNS (no schema "
                "change; in-state-cell augment)")


if __name__ == "__main__":
    unittest.main()
