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

from bin import qpb_harness_legacy as Q
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


class PendingRunManifestMetadataTests(unittest.TestCase):
    """v1.5.7 160 D-prime (follow-up per the review): PENDING runs
    that have a manifest entry but no invocation.json should surface
    the manifest's repo/runner/model rather than falling back to
    ``?/?``. The scheduler-written manifest entry IS the authoritative
    metadata source for PENDING runs (the worker hasn't spawned yet,
    so invocation.json doesn't exist)."""

    def _write(self, p: Path, doc) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(doc) + "\n", encoding="utf-8")

    def test_pending_run_surfaces_manifest_metadata(self) -> None:
        # Manifest lists run-02 (keto claude/opus). No
        # invocation.json (PENDING — never spawned). Synthesis
        # must pull repo/runner/model from the manifest entry.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260530T134322Z"
            hr.mkdir()
            # Manifest with full metadata for run-02.
            self._write(hr / "manifest.json", {
                "harness_run_dir": str(hr),
                "plan": {"pools": {"claude": 1}},
                "runs": [{
                    "index": 2, "description": "keto-test",
                    "repo": "https://github.com/ory/keto",
                    "runner": "claude", "model": "opus",
                    "channel": "pip-local-wheel", "mode": "A",
                    "target_dir": str(hr / "run-02/target"),
                    "run_dir": str(hr / "run-02"),
                    "run_id": "r2", "pid": 0,
                    "started_at": "2026-05-30T13:43:22Z",
                    "stream_path": str(hr / "run-02/stream.ndjson"),
                    "status_path": str(hr / "run-02/status.json"),
                    "max_duration_s": 60.0, "expect": {},
                }],
            })
            # PENDING run-02 with only artifact_used.json.
            (hr / "run-02").mkdir()
            self._write(hr / "run-02/artifact_used.json",
                        {"filename": "wheel.whl"})
            # The manifest covers run-02 via _read_one_run_status,
            # so read_run_status returns that — but the bug surfaces
            # in the dir-scan SYNTHESIS path. We exercise it
            # directly via the private helper to pin the contract.
            manifest = json.loads(
                (hr / "manifest.json").read_text())
            rs = ST._synthesize_run_status_from_dir(
                hr / "run-02", manifest=manifest)
            self.assertIsNotNone(rs)
            self.assertEqual(rs.runner, "claude",
                             "expected 'claude' from manifest")
            self.assertEqual(rs.model, "opus",
                             "expected 'opus' from manifest")
            self.assertEqual(
                rs.repo, "https://github.com/ory/keto")
            self.assertEqual(rs.description, "keto-test")

    def test_invocation_json_wins_over_manifest_for_axes(
            self) -> None:
        # When BOTH invocation.json and a manifest entry are
        # present, invocation.json's axes.runner/model wins (it's
        # the actual runtime record). Manifest fills in the gaps
        # (repo, description) that invocation doesn't have.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260530T134322Z"
            hr.mkdir()
            self._write(hr / "manifest.json", {
                "runs": [{
                    "index": 0, "description": "manifest-desc",
                    "repo": "https://github.com/x/from-manifest",
                    "runner": "claude", "model": "opus",
                }],
            })
            (hr / "run-00").mkdir()
            self._write(hr / "run-00/invocation.json", {
                "case_id": "invocation-case",
                "axes": {"runner": "codex", "model": "gpt-5.4"},
            })
            manifest = json.loads(
                (hr / "manifest.json").read_text())
            rs = ST._synthesize_run_status_from_dir(
                hr / "run-00", manifest=manifest)
            self.assertEqual(rs.runner, "codex")
            self.assertEqual(rs.model, "gpt-5.4")
            # repo only exists in the manifest entry.
            self.assertEqual(
                rs.repo, "https://github.com/x/from-manifest")

    def test_pending_run_falls_back_to_question_marks_when_no_manifest_entry(
            self) -> None:
        # Manifest exists but doesn't list run-99 — genuine orphan.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260530T134322Z"
            hr.mkdir()
            self._write(hr / "manifest.json", {
                "runs": [{"index": 0, "repo": "x",
                          "runner": "claude", "model": "opus"}],
            })
            (hr / "run-99").mkdir()
            self._write(hr / "run-99/artifact_used.json",
                        {"x": 1})
            manifest = json.loads(
                (hr / "manifest.json").read_text())
            rs = ST._synthesize_run_status_from_dir(
                hr / "run-99", manifest=manifest)
            self.assertEqual(rs.runner, "?")
            self.assertEqual(rs.model, "?")
            self.assertEqual(rs.repo, "?")

    def test_pending_run_falls_back_when_manifest_unparseable(
            self) -> None:
        # manifest=None (caller's _safe_json returned None on
        # invalid JSON). Synthesis still works; metadata is "?".
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260530T134322Z"
            hr.mkdir()
            (hr / "run-00").mkdir()
            self._write(hr / "run-00/artifact_used.json",
                        {"x": 1})
            rs = ST._synthesize_run_status_from_dir(
                hr / "run-00", manifest=None)
            self.assertEqual(rs.runner, "?")
            self.assertEqual(rs.model, "?")

    def test_read_run_status_threads_manifest_to_synthesis(
            self) -> None:
        # End-to-end through read_run_status: manifest lists run-01
        # but the seen_dirs path-resolve doesn't match (e.g., the
        # manifest's relative run_dir points elsewhere) → synthesis
        # fires for run-01 and must surface manifest metadata. This
        # is the empirical D-prime case the reviewer caught.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260530T134322Z"
            hr.mkdir()
            (hr / "run-01").mkdir()
            self._write(hr / "run-01/artifact_used.json",
                        {"x": 1})
            # Manifest with a NON-matching run_dir (so seen_dirs
            # won't include run-01's path → dir-scan fires).
            self._write(hr / "manifest.json", {
                "runs": [{
                    "index": 1, "description": "express-test",
                    "repo": "https://github.com/expressjs/express",
                    "runner": "copilot", "model": "gpt-5.4",
                    "run_dir": str(hr / "OTHER-PATH"),
                }],
            })
            runs = ST.read_run_status(hr)
            # The dir-scan path returns 1 entry via synthesis.
            self.assertEqual(len(runs), 1)
            rs = runs[0]
            self.assertEqual(rs.index, 1)
            self.assertEqual(rs.runner, "copilot")
            self.assertEqual(rs.model, "gpt-5.4")
            self.assertEqual(
                rs.repo, "https://github.com/expressjs/express")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
