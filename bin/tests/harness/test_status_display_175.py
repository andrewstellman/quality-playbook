"""v1.5.7 175 — status / TUI display metadata-resolution
regression tests.

Surfaced on harness_runs/20260531T194216Z where:
  * repo shows '?' for ALL entries (invocation.json doesn't carry
    the upstream Git URL).
  * runner/model show '?/?' for PENDING entries (no
    invocation.json exists yet for pre-launch entries).

The display should ALWAYS read plan.json[index] for entry metadata
(description, repo, runner, model, channel, mode); per-run
status.json/invocation.json contribute RUNTIME state only.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


_REPO = Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from bin.harness import status as ST  # noqa: E402


_PLAN_FIXTURE = {
    "pools": {"claude": 2},
    "runs": [
        {
            "index": 0, "description": "gson Phase-1",
            "repo": "https://github.com/google/gson",
            "ref": "main", "runner": "claude",
            "model": "haiku", "channel": "pip-local-wheel",
            "mode": "A",
            "expect": {"final_gate": "PASSED", "facts": {}},
        },
        {
            "index": 1, "description": "express Phase-1",
            "repo": "https://github.com/expressjs/express",
            "ref": "master", "runner": "claude",
            "model": "haiku", "channel": "npm-local-tgz",
            "mode": "A",
            "expect": {"final_gate": "PASSED", "facts": {}},
        },
    ],
}


def _write_plan(harness_run_dir: Path) -> None:
    (harness_run_dir / "plan.json").write_text(
        json.dumps(_PLAN_FIXTURE), encoding="utf-8")


def _write_invocation(run_dir: Path, runner: str = "claude",
                       model: str = "haiku",
                       channel: str = "pip-local-wheel") -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "invocation.json").write_text(
        json.dumps({
            "case_id": "c1", "run_id": "r0",
            "axes": {"runner": runner, "model": model,
                       "install_channel": channel, "mode": "A"},
            # NOTE: no `repo` field in axes — mirrors the
            # production invocation.json shape.
        }), encoding="utf-8")


def _write_status(run_dir: Path, state: str = "RUNNING",
                    pid: int = 12345) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "status.json").write_text(
        json.dumps({
            "state": state, "pid": pid,
            "started_at": "2026-05-31T19:42:16Z",
        }), encoding="utf-8")


class RunningEntryReadsRepoFromPlanTests(unittest.TestCase):
    """Test A1: a RUNNING entry (has invocation.json) shows repo
    from plan.json — invocation.json doesn't carry the upstream
    Git URL."""

    def test_running_entry_repo_from_plan_json(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            hrd = Path(tmp)
            _write_plan(hrd)
            _write_invocation(hrd / "run-00")
            _write_status(hrd / "run-00", state="RUNNING",
                            pid=12345)
            runs = ST.read_run_status(hrd)
            # plan.json has 2 entries → both shown (the second is
            # synthesized as PENDING from plan_meta).
            by_idx = {r.index: r for r in runs}
            self.assertIn(0, by_idx)
            self.assertEqual(
                by_idx[0].repo,
                "https://github.com/google/gson")
            self.assertEqual(by_idx[0].state, "RUNNING")


class PendingEntryReadsAllFromPlanTests(unittest.TestCase):
    """Test A2: a PENDING entry (no invocation.json yet) shows
    runner/model/repo from plan.json. Pre-175 this surfaced as
    `?/?` for runner/model and `?` for repo on the
    `harness_runs/20260531T194216Z` 6-haiku retest."""

    def test_pending_entry_metadata_from_plan_json(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            hrd = Path(tmp)
            _write_plan(hrd)
            # run-00 dir exists but is empty (no invocation.json,
            # no status.json, no stream.ndjson) — mimics a
            # PENDING entry the orchestrator hasn't spawned yet.
            (hrd / "run-00").mkdir()
            runs = ST.read_run_status(hrd)
            by_idx = {r.index: r for r in runs}
            self.assertIn(0, by_idx)
            self.assertEqual(
                by_idx[0].repo,
                "https://github.com/google/gson")
            self.assertEqual(by_idx[0].runner, "claude")
            self.assertEqual(by_idx[0].model, "haiku")


class RuntimeStateStillFromPerRunFilesTests(unittest.TestCase):
    """Test A3: status.json continues to be the source of truth
    for pid + started_at; plan.json contributes only base
    metadata, NOT runtime state."""

    def test_pid_from_status_metadata_from_plan(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            hrd = Path(tmp)
            _write_plan(hrd)
            _write_invocation(hrd / "run-00")
            _write_status(hrd / "run-00", state="RUNNING",
                            pid=99887)
            runs = ST.read_run_status(hrd)
            by_idx = {r.index: r for r in runs}
            self.assertEqual(by_idx[0].pid, 99887)
            self.assertEqual(
                by_idx[0].repo,
                "https://github.com/google/gson")


class TuiDumpSamePathTests(unittest.TestCase):
    """Test A4: TUI ``--dump runs`` (the tui.py code path) uses
    the same display surface and inherits the fix."""

    def test_tui_detail_dump_shows_plan_metadata(self) -> None:
        # The TUI's `--dump detail` (and per-harness-run detail
        # screen) path goes through tui.py's format_detail_as_text
        # which itself consumes read_run_status. As long as
        # read_run_status is fixed, the dump inherits it.
        import tempfile
        from bin.harness import tui as TUI
        with tempfile.TemporaryDirectory() as tmp:
            hrd = Path(tmp)
            _write_plan(hrd)
            (hrd / "run-00").mkdir()  # PENDING (no invocation)
            _write_invocation(hrd / "run-01")
            _write_status(hrd / "run-01", state="RUNNING",
                            pid=98765)
            out = TUI.format_detail_as_text(hrd)
            # Both entries' metadata should appear without ?.
            self.assertIn("gson", out)
            self.assertIn("express", out)
            self.assertIn("claude/haiku", out)


class GracefulMissingPlanTests(unittest.TestCase):
    """Test A5: missing or malformed plan.json — display still
    produces output, just with '?' for the missing fields. No
    crash. Documents the failure-mode bound."""

    def test_missing_plan_falls_back_gracefully(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            hrd = Path(tmp)
            # No plan.json. PENDING entry.
            (hrd / "run-00").mkdir()
            runs = ST.read_run_status(hrd)
            # Either zero runs (no plan, no manifest, no
            # invocation, no stream) or one run with '?' fields
            # — the synthesis function decides which. Whatever
            # the behavior, it must NOT crash.
            for r in runs:
                # Defensive — fields are strings even when '?'.
                self.assertIsInstance(r.runner, str)
                self.assertIsInstance(r.model, str)
                self.assertIsInstance(r.repo, str)

    def test_malformed_plan_falls_back_gracefully(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            hrd = Path(tmp)
            (hrd / "plan.json").write_text(
                "not-json{{{", encoding="utf-8")
            (hrd / "run-00").mkdir()
            runs = ST.read_run_status(hrd)
            # No crash; output is bounded.
            for r in runs:
                self.assertIsInstance(r.runner, str)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
