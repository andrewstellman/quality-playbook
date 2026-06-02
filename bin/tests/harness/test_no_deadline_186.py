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


if __name__ == "__main__":
    unittest.main()
