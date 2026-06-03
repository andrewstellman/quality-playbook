"""v1.5.7 153 — manifest-independent enumeration in
``read_run_status`` + ``read_one_run_status_for_dir``, PENDING/queued
state recognition for run-NN dirs without spawn markers, and the
extended ``RunStatus`` fields (``terminal_state``, ``ended_at``,
``heartbeat``) surfaced by ``format_run_status``.

Empirical motivation: 2026-05-29 21:54 ship-readiness retest. Andrew
Ctrl-C'd a plan before its late-stage manifest write; the harness-run
dir at ``harness_runs/20260529T215456Z/`` had no top-level
manifest.json, 3 spawned runs (run-03/04/06) each with status.json +
stream.ndjson + target/, and 4 queued-never-spawned runs
(run-00/01/02/05) each with only ``artifact_used.json``. The pre-153
``read_run_status`` returned 0 entries; ``kill <TS>`` reported "no
running runs to kill" despite live PIDs; ``status <TS>`` printed
"(empty manifest)" with no per-run detail. 153 makes the on-disk
``run-NN/`` dirs authoritative.

Task D (TUI home-screen detail pane) is SPLIT to a 154 follow-up per
the instruction's Halt #3 authorization (data-layer fix ships clean;
UI polish gets its own scope).
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from bin import qpb_harness as Q
from bin.harness import status as ST


# ---------------------------------------------------------------------------
# Fixtures — explicit shapes per 153's "the dir is authoritative" model
# ---------------------------------------------------------------------------


def _write_json(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc) + "\n", encoding="utf-8")


def _make_spawned_run(rd: Path, *, index: int, state: str = "RUNNING",
                      pid: int = 1, terminal: "str | None" = None,
                      runner: str = "codex", model: str = "gpt-5.4",
                      with_stream: bool = True,
                      with_target: bool = True) -> None:
    """A spawned run-NN dir: invocation.json + status.json (+
    stream.ndjson + target/). Mirrors what the manager writes."""
    rd.mkdir(parents=True, exist_ok=True)
    _write_json(rd / "invocation.json", {
        "run_id": f"r{index}", "case_id": f"plan-{index:02d}",
        "axes": {"runner": runner, "mode": "B", "model": model,
                 "install_channel": "npm-local-tgz"},
        "started_at": "2026-05-29T21:55:00Z",
    })
    status: dict = {
        "state": state, "pid": pid,
        "started_at": "2026-05-29T21:55:00Z",
        "heartbeat": "2026-05-29T21:55:02Z",
    }
    if terminal is not None:
        status["terminal_state"] = terminal
        status["ended_at"] = "2026-05-29T21:56:00Z"
    _write_json(rd / "status.json", status)
    if with_stream:
        (rd / "stream.ndjson").write_text("", encoding="utf-8")
    if with_target:
        (rd / "target").mkdir(exist_ok=True)


def _make_pending_run(rd: Path) -> None:
    """A PENDING/queued run-NN dir: scheduler created the dir +
    pinned an ``artifact_used.json``, then Ctrl-C hit before the
    per-run worker spawned. No status.json, no stream, no target."""
    rd.mkdir(parents=True, exist_ok=True)
    _write_json(rd / "artifact_used.json", {
        "filename": "quality-playbook-1.5.7.tgz"})


def _make_manifest(hr: Path, entries: "list[dict]") -> None:
    """Manifest entries (index/run_dir relative) — mimics the
    plan_runner write. ``entries`` is just the runs list; we wrap it
    in the standard manifest envelope."""
    _write_json(hr / "manifest.json", {
        "harness_run_dir": str(hr),
        "plan": {"pools": {"claude": 1}},
        "runs": entries,
    })


def _manifest_entry(rd: Path, *, index: int,
                    repo: str = "https://github.com/x/r",
                    runner: str = "codex", model: str = "gpt-5.4",
                    pid: "int | None" = None) -> dict:
    return {
        "index": index, "description": f"r{index}",
        "repo": repo, "runner": runner, "model": model,
        "channel": "npm-local-tgz", "mode": "B",
        "target_dir": str(rd / "target"),
        "run_dir": str(rd),
        "run_id": f"r{index}", "pid": pid,
        "started_at": "2026-05-29T21:55:00Z",
        "stream_path": str(rd / "stream.ndjson"),
        "status_path": str(rd / "status.json"),
        "max_duration_s": 60.0, "expect": {},
    }


# ---------------------------------------------------------------------------
# Task A — manifest-independent enumeration
# ---------------------------------------------------------------------------


class ManifestIndependentEnumerationTests(unittest.TestCase):

    def test_read_run_status_includes_runs_not_in_manifest(self) -> None:
        # Manifest lists ONE run; TWO additional run-NN dirs exist on
        # disk with their own status.json. Pre-153: 1 entry returned.
        # Post-153: 3 entries returned. Mutation-bite: dropping the
        # dir-scan fallback collapses back to 1.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T215456Z"
            hr.mkdir()
            for i in (0, 1, 2):
                _make_spawned_run(hr / f"run-{i:02d}", index=i)
            _make_manifest(hr, [_manifest_entry(
                hr / "run-00", index=0)])
            runs = ST.read_run_status(hr)
            self.assertEqual(len(runs), 3)
            indices = sorted(r.index for r in runs)
            self.assertEqual(indices, [0, 1, 2])

    def test_read_run_status_enumerates_when_manifest_absent(
            self) -> None:
        # NO manifest at all; 3 run-NN dirs on disk → 3 entries.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T215456Z"
            hr.mkdir()
            for i in (0, 1, 2):
                _make_spawned_run(hr / f"run-{i:02d}", index=i)
            self.assertEqual(len(ST.read_run_status(hr)), 3)

    def test_read_run_status_returns_empty_for_no_run_dirs(
            self) -> None:
        # The new "empty" condition: not "no manifest" but "no
        # run-NN dirs at all." Manifest absent + only artifacts/
        # subdir.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T215456Z"
            hr.mkdir()
            (hr / "artifacts").mkdir()
            self.assertEqual(ST.read_run_status(hr), [])

    def test_read_one_run_status_for_dir_works_when_manifest_absent(
            self) -> None:
        # The single-run read also falls back to synthesis. Pre-153:
        # returned None when no manifest.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T215456Z"
            hr.mkdir()
            _make_spawned_run(hr / "run-00", index=0)
            rs = ST.read_one_run_status_for_dir(hr / "run-00")
            self.assertIsNotNone(rs)
            self.assertEqual(rs.index, 0)
            self.assertEqual(rs.state, "RUNNING")
            self.assertEqual(rs.runner, "codex")

    def test_manifest_entry_wins_on_metadata_when_present(
            self) -> None:
        # Manifest provides repo; dir-scan only synthesizes "?". When
        # the manifest lists the run, the manifest's repo wins.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T215456Z"
            hr.mkdir()
            _make_spawned_run(hr / "run-00", index=0)
            _make_manifest(hr, [_manifest_entry(
                hr / "run-00", index=0,
                repo="https://github.com/canonical/from-manifest")])
            runs = ST.read_run_status(hr)
            self.assertEqual(len(runs), 1)
            self.assertEqual(runs[0].repo,
                             "https://github.com/canonical/from-manifest")


# ---------------------------------------------------------------------------
# Task B — PENDING/queued state for marker-less run dirs
# ---------------------------------------------------------------------------


class PendingStateRecognitionTests(unittest.TestCase):

    def test_pending_run_dir_recognized_as_PENDING_state(self) -> None:
        # The Bug B fixture: a run-NN dir with only artifact_used.json,
        # no status.json, no stream, no target — the queued-never-
        # spawned state. Synthesizes with state=PENDING, pid=None,
        # terminal_state=None.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T215456Z"
            hr.mkdir()
            _make_pending_run(hr / "run-00")
            rs = ST.read_one_run_status_for_dir(hr / "run-00")
            self.assertIsNotNone(rs)
            self.assertEqual(rs.state, "PENDING")
            self.assertIsNone(rs.pid)
            self.assertIsNone(rs.terminal_state)
            self.assertEqual(rs.runner, "?")

    def test_pending_dir_with_only_artifact_used_still_enumerates(
            self) -> None:
        # Three PENDING dirs + one spawned, no manifest → 4 rows; 3
        # PENDING + 1 RUNNING.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T215456Z"
            hr.mkdir()
            for i in (0, 1, 2):
                _make_pending_run(hr / f"run-{i:02d}")
            _make_spawned_run(hr / "run-03", index=3)
            runs = ST.read_run_status(hr)
            self.assertEqual(len(runs), 4)
            states = sorted(r.state for r in runs)
            self.assertEqual(states,
                             ["PENDING", "PENDING", "PENDING", "RUNNING"])

    def test_status_cmd_on_pending_run_dir_shows_pending_not_error(
            self) -> None:
        # The CLI intercept (qpb_harness.py): pre-153 a PENDING run-NN
        # dir hit the classifier's ValueError → was treated as an
        # empty runs-root → wrong page. Now: ValueError caught, run-NN
        # name fullmatches _RE_RUN_NN, kind forced to RUN_NN, the
        # synthesized PENDING row renders.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T215456Z"
            hr.mkdir()
            _make_pending_run(hr / "run-00")
            buf_out, buf_err = io.StringIO(), io.StringIO()
            with redirect_stdout(buf_out), redirect_stderr(buf_err):
                rc = Q.main(["status", str(hr / "run-00")])
            self.assertEqual(rc, 0)
            combined = buf_out.getvalue() + buf_err.getvalue()
            self.assertIn("PENDING", combined)

    def test_status_cmd_on_harness_run_with_incomplete_manifest(
            self) -> None:
        # Manifest lists 2 of 5 runs; status output should include all
        # 5 rows (with PENDING for the 3 unspawned).
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T215456Z"
            hr.mkdir()
            for i in (0, 1):
                _make_spawned_run(hr / f"run-{i:02d}", index=i)
            for i in (2, 3, 4):
                _make_pending_run(hr / f"run-{i:02d}")
            _make_manifest(hr, [
                _manifest_entry(hr / "run-00", index=0),
                _manifest_entry(hr / "run-01", index=1),
            ])
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(io.StringIO()):
                rc = Q.main(["status", str(hr)])
            self.assertEqual(rc, 0)
            out = buf.getvalue()
            for i in range(5):
                self.assertIn(f"#{i:<2}", out,
                              f"missing #{i} in:\n{out}")

    def test_kill_cmd_on_pending_run_dir_cancels_it_188(
            self) -> None:
        # v1.5.7 188 FINDING-41 + 42: kill on a PENDING dir now
        # CANCELS the entry instead of skipping it (pre-188
        # behavior left PENDING rows queued for the collector
        # to launch — defeating the operator's intent when
        # they ran `kill <harness-run>` to stop the plan).
        # Test now requires a manifest with the PENDING entry
        # so the cancel path can write CANCELLED back.
        import json
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T215456Z"
            hr.mkdir()
            _make_pending_run(hr / "run-00")
            # Synthesize a minimal PENDING manifest entry the
            # 188 cancel helper can locate + transition.
            (hr / "manifest.json").write_text(json.dumps({
                "harness_run_dir": str(hr),
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
                    "description": "row0",
                    "run_dir": str(hr / "run-00"),
                }],
            }) + "\n", encoding="utf-8")
            buf = io.StringIO()
            with redirect_stdout(buf), redirect_stderr(io.StringIO()):
                rc = Q.main(["kill", "-y", str(hr / "run-00")])
            self.assertEqual(rc, 0)
            self.assertIn(
                "Cancelled:", buf.getvalue(),
                "post-188 kill on PENDING must report under "
                "'Cancelled:' header (FINDING-41).")
            # Verify the manifest entry is now CANCELLED.
            on_disk = json.loads(
                (hr / "manifest.json").read_text())
            entry = on_disk["runs"][0]
            self.assertEqual(
                entry.get("terminal_state"), "CANCELLED",
                "manifest entry must be CANCELLED (188 "
                "FINDING-42).")


# ---------------------------------------------------------------------------
# Task C — RunStatus fields + format_run_status output
# ---------------------------------------------------------------------------


class FormatRunStatusFieldsTests(unittest.TestCase):

    def test_format_run_status_includes_terminal_ended_heartbeat(
            self) -> None:
        # Construct a RunStatus with all three new fields populated;
        # the formatter must surface each. Mutation-bite: dropping any
        # one of the f-string interpolations makes the assertion fail.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T215456Z"
            hr.mkdir()
            _make_spawned_run(hr / "run-00", index=0,
                              state="RUNNING", pid=42,
                              terminal="COMPLETED")
            rs = ST.read_one_run_status_for_dir(hr / "run-00")
            line = ST.format_run_status(rs)
            self.assertIn("terminal=COMPLETED", line)
            self.assertIn("ended=2026-05-29T21:56:00Z", line)
            self.assertIn("heartbeat=2026-05-29T21:55:02Z", line)

    def test_format_run_status_shows_dashes_when_unset(self) -> None:
        # Pre-terminal: the three fields render as "—" / dash so the
        # row is still readable.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T215456Z"
            hr.mkdir()
            _make_pending_run(hr / "run-00")
            rs = ST.read_one_run_status_for_dir(hr / "run-00")
            line = ST.format_run_status(rs)
            self.assertIn("terminal=—", line)
            self.assertIn("ended=—", line)
            self.assertIn("heartbeat=—", line)


# ---------------------------------------------------------------------------
# Real-world shape — the 2026-05-29 21:54 retest evidence
# ---------------------------------------------------------------------------


class RealWorldKilledHarnessRunTests(unittest.TestCase):

    def test_synthesized_215456_shape_enumerates_all_seven_runs(
            self) -> None:
        # Synthesizes the EXACT 2026-05-29 21:54 retest shape: NO
        # manifest, 4 PENDING dirs (only artifact_used.json), 3 spawned
        # dirs (status.json + stream + target). The Ctrl-C'd workflow
        # the operator needs to recover from.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T215456Z"
            hr.mkdir()
            for i in (0, 1, 2, 5):
                _make_pending_run(hr / f"run-{i:02d}")
            for i, (runner, pid) in zip(
                    (3, 4, 6),
                    [("codex", 96586), ("codex", 96578),
                     ("copilot", 96558)]):
                _make_spawned_run(hr / f"run-{i:02d}", index=i,
                                  runner=runner, pid=pid)
            runs = ST.read_run_status(hr)
            self.assertEqual(len(runs), 7)
            by_index = {r.index: r for r in runs}
            for i in (0, 1, 2, 5):
                self.assertEqual(by_index[i].state, "PENDING")
                self.assertIsNone(by_index[i].pid)
            for i in (3, 4, 6):
                self.assertEqual(by_index[i].state, "RUNNING")
                self.assertIsNotNone(by_index[i].pid)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
