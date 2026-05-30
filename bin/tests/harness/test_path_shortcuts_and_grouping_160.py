"""v1.5.7 160 — timestamp path shortcuts + grouped status output +
dead-pid warning + kill UX symbols. Post-launch operator UX after
158 made the launch banner copy-pasteable.

Operators currently type ``harness_runs/<TS>`` for every command;
the shortcut lets them type just ``<TS>`` (the timestamp the 158
banner surfaces prominently) or ``<TS>/run-NN``. Conservative: only
triggers when the literal path doesn't exist AND the pattern
matches exactly. Honors an explicit ``--runs-root`` (composes
``<--runs-root>/<TS>`` instead of the default ``harness_runs/``).

Status output now groups by state (RUNNING / PENDING / COMPLETED
/ FAILED) with section counts and a dead-pid warning inline on
RUNNING rows whose pid is no longer alive. Empty groups are
skipped. Inside each group the row format is tight (no repeated
state column).

Kill output gains ✓/✗ symbols so success vs skip is visible at a
glance.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest import mock

from bin import qpb_harness as Q
from bin.harness import status as ST


# ---------------------------------------------------------------------------
# Task A — timestamp path shortcut helper + _resolve_tui_path
# ---------------------------------------------------------------------------


class TimestampShortcutHelperTests(unittest.TestCase):

    def test_ts_alone_matches(self) -> None:
        self.assertTrue(
            Q._looks_like_timestamp_shortcut("20260530T134322Z"))

    def test_ts_with_run_nn_matches(self) -> None:
        self.assertTrue(Q._looks_like_timestamp_shortcut(
            "20260530T134322Z/run-03"))

    def test_ts_with_two_digit_run_matches(self) -> None:
        self.assertTrue(Q._looks_like_timestamp_shortcut(
            "20260530T134322Z/run-12"))

    def test_missing_z_does_not_match(self) -> None:
        # Mutation-bite target: dropping the trailing Z from the
        # regex would make a non-timestamp path match.
        self.assertFalse(
            Q._looks_like_timestamp_shortcut("20260530T134322"))

    def test_wrong_separator_does_not_match(self) -> None:
        self.assertFalse(Q._looks_like_timestamp_shortcut(
            "20260530T134322Z-run-03"))

    def test_extra_path_segments_do_not_match(self) -> None:
        self.assertFalse(Q._looks_like_timestamp_shortcut(
            "20260530T134322Z/run-03/target"))

    def test_prefixed_path_does_not_match(self) -> None:
        # harness_runs/<TS> is already absolute-shape; not a
        # shortcut.
        self.assertFalse(Q._looks_like_timestamp_shortcut(
            "harness_runs/20260530T134322Z"))


class ResolveTuiPathShortcutTests(unittest.TestCase):
    """v1.5.7 160 Task A: _resolve_tui_path expands ``<TS>`` and
    ``<TS>/run-NN`` to ``<runs-root>/<TS>...`` when the literal
    doesn't exist. Honors explicit --runs-root."""

    def _ns(self, **kwargs) -> argparse.Namespace:
        a = argparse.Namespace()
        for k, v in kwargs.items():
            setattr(a, k, v)
        return a

    def test_ts_alone_resolves_to_default_runs_root_prefix(
            self) -> None:
        with tempfile.TemporaryDirectory() as td:
            hrd = Path(td) / "harness_runs" / "20260530T134322Z"
            hrd.mkdir(parents=True)
            cwd = os.getcwd()
            try:
                os.chdir(td)
                rp = Q._resolve_tui_path(
                    self._ns(path="20260530T134322Z"))
            finally:
                os.chdir(cwd)
            self.assertEqual(rp.path.resolve(), hrd.resolve())
            self.assertFalse(rp.from_default)

    def test_ts_with_run_nn_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            hrd = (Path(td) / "harness_runs"
                   / "20260530T134322Z" / "run-03")
            hrd.mkdir(parents=True)
            cwd = os.getcwd()
            try:
                os.chdir(td)
                rp = Q._resolve_tui_path(self._ns(
                    path="20260530T134322Z/run-03"))
            finally:
                os.chdir(cwd)
            self.assertEqual(rp.path.resolve(), hrd.resolve())

    def test_literal_path_used_when_exists(self) -> None:
        # Conservative: if `./20260530T134322Z` exists at cwd
        # (unlikely but possible), the literal wins.
        with tempfile.TemporaryDirectory() as td:
            literal = Path(td) / "20260530T134322Z"
            literal.mkdir()
            (Path(td) / "harness_runs"
             / "20260530T134322Z").mkdir(parents=True)
            cwd = os.getcwd()
            try:
                os.chdir(td)
                rp = Q._resolve_tui_path(
                    self._ns(path="20260530T134322Z"))
            finally:
                os.chdir(cwd)
            # The literal (./20260530T134322Z) wins.
            self.assertEqual(rp.path.resolve(), literal.resolve())

    def test_non_timestamp_path_uses_existing_behavior(
            self) -> None:
        # `harness_runs/<TS>` (already prefixed) goes through the
        # standard explicit-path path; no shortcut interference.
        with tempfile.TemporaryDirectory() as td:
            hrd = Path(td) / "harness_runs" / "20260530T134322Z"
            hrd.mkdir(parents=True)
            rp = Q._resolve_tui_path(
                self._ns(path=str(hrd)))
            self.assertEqual(rp.path.resolve(), hrd.resolve())

    def test_explicit_runs_root_overrides_default(self) -> None:
        # Halt #4: when --runs-root is explicit, the shortcut
        # composes with IT, not the default harness_runs/.
        with tempfile.TemporaryDirectory() as td:
            custom = Path(td) / "my-custom-runs"
            hrd = custom / "20260530T134322Z"
            hrd.mkdir(parents=True)
            rp = Q._resolve_tui_path(self._ns(
                path="20260530T134322Z", runs_root=str(custom)))
            self.assertEqual(rp.path.resolve(), hrd.resolve())

    def test_shortcut_not_triggered_when_target_absent(
            self) -> None:
        # If neither the literal NOR the shortcut path exists, the
        # function falls through to the explicit-literal-resolve
        # branch (existing 135 behavior). Callers catch the
        # FileNotFoundError downstream.
        with tempfile.TemporaryDirectory() as td:
            cwd = os.getcwd()
            try:
                os.chdir(td)
                rp = Q._resolve_tui_path(self._ns(
                    path="20260530T134322Z"))
            finally:
                os.chdir(cwd)
            self.assertFalse(rp.path.exists())


# ---------------------------------------------------------------------------
# Task B + C — status grouping + dead-pid warning
# ---------------------------------------------------------------------------


def _make_rs(*, index: int, state: str, repo: str = "x",
             runner: str = "claude", model: str = "opus",
             pid: int = None, pid_alive: bool = True,
             result: str = "N/A", current_phase: str = "—",
             current_phase_name: str = "—",
             current_phase_state: str = "—",
             terminal_state: str = None,
             ended_at: str = "—",
             elapsed_s: int = None,
             last_note: str = "") -> "ST.RunStatus":
    return ST.RunStatus(
        index=index, description="r",
        repo=repo, runner=runner, model=model, state=state,
        result=result, current_phase=current_phase,
        current_phase_name=current_phase_name,
        current_phase_state=current_phase_state,
        last_note=last_note, pid=pid, pid_alive=pid_alive,
        stream_path=Path("/tmp/s"), run_dir=Path("/tmp/rd"),
        last_activity_iso="2026-05-30T13:46:37Z",
        elapsed_s=elapsed_s,
        terminal_state=terminal_state,
        ended_at=ended_at, heartbeat="—",
    )


class FormatRunsGroupedTests(unittest.TestCase):

    def test_groups_by_state_with_counts(self) -> None:
        runs = [
            _make_rs(index=0, state="RUNNING", pid=42, pid_alive=True),
            _make_rs(index=1, state="RUNNING", pid=43, pid_alive=True),
            _make_rs(index=2, state="PENDING"),
            _make_rs(index=3, state="COMPLETED",
                      result="MET", ended_at="2026-05-30T13:42:00Z"),
        ]
        out = ST.format_runs_grouped(runs)
        self.assertIn("RUNNING (2):", out)
        self.assertIn("PENDING (1):", out)
        self.assertIn("COMPLETED (1):", out)

    def test_empty_groups_skipped(self) -> None:
        runs = [_make_rs(index=0, state="RUNNING",
                          pid=42, pid_alive=True)]
        out = ST.format_runs_grouped(runs)
        # Mutation-bite: emitting an empty `COMPLETED (0):` line
        # would fail this.
        self.assertNotIn("PENDING (0):", out)
        self.assertNotIn("COMPLETED (0):", out)
        self.assertNotIn("FAILED (0):", out)

    def test_running_with_dead_pid_shows_orphan_warning(
            self) -> None:
        # Task C: a RUNNING row whose pid is NOT alive gets a
        # "DEAD — orphan?" warning. Mutation-bite target: changing
        # the format to a quiet "dead" loses the visibility.
        runs = [_make_rs(index=0, state="RUNNING",
                          pid=68733, pid_alive=False)]
        out = ST.format_runs_grouped(runs)
        self.assertIn("DEAD — orphan?", out)

    def test_running_with_live_pid_shows_live(self) -> None:
        runs = [_make_rs(index=0, state="RUNNING",
                          pid=68733, pid_alive=True)]
        out = ST.format_runs_grouped(runs)
        self.assertIn("pid=68733(live)", out)
        self.assertNotIn("DEAD", out)

    def test_failed_bucket_catches_terminal_failure_states(
            self) -> None:
        # All non-COMPLETED terminal states go into the FAILED
        # bucket so operators see one "look at this" pile.
        for term in ("FAILED", "TIMED_OUT", "BLOCKED",
                      "KILLED", "ABORTED_PREP"):
            with self.subTest(terminal_state=term):
                runs = [_make_rs(index=0, state=term,
                                  terminal_state=term)]
                out = ST.format_runs_grouped(runs)
                self.assertIn("FAILED (1):", out)
                self.assertIn(term, out)

    def test_completed_bucket_shows_result(self) -> None:
        runs = [_make_rs(index=0, state="COMPLETED",
                          result="MET",
                          ended_at="2026-05-30T13:42:00Z")]
        out = ST.format_runs_grouped(runs)
        self.assertIn("COMPLETED (1):", out)
        self.assertIn("MET", out)

    def test_pending_with_phase_info_surfaces_phase(self) -> None:
        # The drill-down-110 edge case: a run that's RUNNING in
        # the stream sense (has phase sentinels) but is still
        # state=PENDING in the manifest (status.json hasn't been
        # written yet). The PENDING row format includes phase
        # info when present so the operator sees forward progress.
        runs = [_make_rs(index=0, state="PENDING",
                          current_phase="P2",
                          current_phase_name="generation",
                          current_phase_state="start")]
        out = ST.format_runs_grouped(runs)
        self.assertIn("P2", out)
        self.assertIn("generation", out)

    def test_rows_sorted_by_index_within_group(self) -> None:
        # Determinism: rows within a group are sorted by index.
        runs = [_make_rs(index=2, state="RUNNING",
                          pid=42, pid_alive=True),
                 _make_rs(index=0, state="RUNNING",
                          pid=42, pid_alive=True),
                 _make_rs(index=1, state="RUNNING",
                          pid=42, pid_alive=True)]
        out = ST.format_runs_grouped(runs)
        # The relative order of #0, #1, #2 in the output should be
        # ascending.
        idx0 = out.find("#0 ")
        idx1 = out.find("#1 ")
        idx2 = out.find("#2 ")
        self.assertTrue(0 <= idx0 < idx1 < idx2,
                        f"order wrong: {idx0},{idx1},{idx2}")


# ---------------------------------------------------------------------------
# Task D — kill UX symbols (✓/✗)
# ---------------------------------------------------------------------------


class KillUxSymbolsTests(unittest.TestCase):
    """Smoke tests for the ✓/✗ symbols. We don't drive the full
    kill flow (covered by 147/151); we verify the symbols appear in
    the output by exercising the source-code presence directly."""

    def test_kill_output_uses_check_mark_on_success(self) -> None:
        # Mutation-bite: removing the ✓ glyph from the success
        # branch loses the visual feedback.
        src = Path(Q.__file__).read_text(encoding="utf-8")
        self.assertIn('"  ✓ {label}: {note}"',
                       src.replace("f'", '"').replace("'", '"'))

    def test_kill_output_uses_cross_on_skipped(self) -> None:
        src = Path(Q.__file__).read_text(encoding="utf-8")
        self.assertIn('"  ✗ {label} ({reason})"',
                       src.replace("f'", '"').replace("'", '"'))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
