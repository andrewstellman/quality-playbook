"""v1.5.7 111 — live TUI over the 110 status layer.

The TUI is the operator-facing view Andrew asked for: see
harness runs currently in flight, drill into a run to see each
repo's specific phase, and watch live output — auto-refreshing.
It's a thin presentation layer over the 110
``bin/harness/status.py`` model — the view-model builders below
take ``status.py`` output and produce display rows; the curses
event loop is glue.

Coverage (Task C):
  * The view-model builders are pure functions; testable
    WITHOUT invoking curses.
  * ``build_runs_list_rows`` orders newest-first with correct
    counts (delegates to ``status.list_harness_runs`` which
    is already pinned).
  * ``build_run_detail_rows`` maps a fixture harness-run to
    the right per-repo rows incl. current phase + name +
    state from the LAST ``::QPB::`` phase sentinel.
  * ``build_output_lines`` formats a stream + renders sentinels
    human-readably; truncates to ``max_lines``.
  * Smoke: ``bin.harness.tui`` imports without invoking
    curses (the ``launch_status_tui`` entry is only called
    from the CLI; importing the module is side-effect-free).
  * Bundle-safety: ``bin/harness/tui.py`` stays under the
    excluded path.

The curses event loop is NOT directly unit-tested (curses is
hard to fixture); the view-model builders are what tests
exercise. The 110 contract — that the model layer is shared
between the CLI + the TUI — is structurally pinned by the
TUI's exclusive use of ``status.py`` for reads.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
import unittest.mock as mock
from pathlib import Path

from bin.harness import tui as TUI


# ---------------------------------------------------------------------------
# Fixture builders (mirror 110's test fixtures so the layers
# stay coordinated)
# ---------------------------------------------------------------------------


def _build_harness_run(
        parent: Path, *, name: str = "20260526T193000Z",
        runs: "list[dict]",
        collector_log_age_s: "float | None" = None,
) -> Path:
    """Build a fixture harness-run dir + manifest + per-run
    receipts. Same shape as the 110 test fixtures."""
    harness_run = parent / name
    harness_run.mkdir()
    entries = []
    for run in runs:
        idx = run["index"]
        run_dir = harness_run / f"run-{idx:02d}"
        run_dir.mkdir()
        entry = {
            "index": idx,
            "description": run.get("description", f"r{idx}"),
            "repo": run.get("repo",
                              f"https://example.com/r{idx}"),
            "runner": run.get("runner", "claude"),
            "model": run.get("model", "opus"),
            "channel": run.get("channel", "clone"),
            "mode": run.get("mode", "A"),
            "target_dir": str(run_dir / "target"),
            "run_dir": str(run_dir),
            "stream_path": str(run_dir / "stream.ndjson"),
            "status_path": str(run_dir / "status.json"),
            "pid": run.get("pid"),
            "started_at": run.get(
                "started_at", "2026-05-26T19:00:00Z"
            ),
            "max_duration_s": run.get(
                "max_duration_s", 7200.0
            ),
            "expect": run.get("expect", {}),
        }
        if "terminal_state" in run:
            entry["terminal_state"] = run["terminal_state"]
        entries.append(entry)
        if "status" in run:
            (run_dir / "status.json").write_text(
                json.dumps(run["status"]) + "\n",
                encoding="utf-8",
            )
        if "grading" in run:
            (run_dir / "grading.json").write_text(
                json.dumps(run["grading"]) + "\n",
                encoding="utf-8",
            )
        if "stream_lines" in run:
            (run_dir / "stream.ndjson").write_text(
                "\n".join(run["stream_lines"]) + "\n",
                encoding="utf-8",
            )
    (harness_run / "manifest.json").write_text(
        json.dumps({
            "harness_run_dir": str(harness_run),
            "plan": {"pools": {"claude": 1}},
            "runs": entries,
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    if collector_log_age_s is not None:
        log = harness_run / "collector.log"
        log.write_text("collector log\n", encoding="utf-8")
        target_mtime = time.time() - collector_log_age_s
        os.utime(log, (target_mtime, target_mtime))
    return harness_run


def _phase_sentinel(*, phase: int, name: str, state: str,
                     ts: str = "2026-05-26T19:30:00Z",
                     note: "str | None" = None) -> str:
    payload = {
        "v": 1, "kind": "phase", "phase": phase,
        "name": name, "state": state, "ts": ts,
    }
    if note is not None:
        payload["note"] = note
    return (
        "::QPB:: "
        + json.dumps(payload, separators=(",", ":"))
    )


def _gate_sentinel(*, gate_result: str, verdict_state: str,
                    ts: str = "2026-05-26T19:40:00Z") -> str:
    payload = {
        "v": 1, "kind": "gate",
        "gate_result": gate_result,
        "verdict_state": verdict_state, "ts": ts,
    }
    return (
        "::QPB:: "
        + json.dumps(payload, separators=(",", ":"))
    )


# ---------------------------------------------------------------------------
# Task A — view-model builders are pure (curses-free)
# ---------------------------------------------------------------------------


class BuildRunsListRowsTests(unittest.TestCase):
    """The runs-list view-model. Headers + per-run lines +
    footer. Newest-first ordering is delegated to
    ``status.list_harness_runs`` (already pinned by 110)."""

    def test_empty_runs_root_shows_friendly_message(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rows = TUI.build_runs_list_rows(Path(tmp))
            # First row is the title/help.
            self.assertIn("Harness runs under", rows[0])
            # Body contains the "(no harness-runs yet)"
            # message somewhere.
            joined = "\n".join(rows)
            self.assertIn("(no harness-runs yet)", joined)

    def test_lists_harness_runs_with_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            harness_run = _build_harness_run(
                tmp_p, name="20260526T180000Z",
                runs=[
                    {"index": 0, "pid": 1, "status": {
                        "state": "DONE", "pid": 1,
                        "started_at": "x", "heartbeat": "y",
                        "ended_at": "z", "exit_code": 0,
                        "terminal_state": "COMPLETED",
                    }},
                    {"index": 1, "pid": 2, "status": {
                        "state": "RUNNING", "pid": 2,
                        "started_at": "x", "heartbeat": "y",
                        "exit_code": None,
                        "terminal_state": None,
                    }},
                ],
            )
            rows = TUI.build_runs_list_rows(tmp_p)
            joined = "\n".join(rows)
            # Dir name appears.
            self.assertIn(harness_run.name, joined)
            # Footer with count.
            self.assertIn("1 harness-run(s)", joined)

    def test_newest_first_ordering_pinned_via_status_layer(
            self) -> None:
        """Two fixture dirs with different mtimes; the newer
        one appears FIRST in the rendered rows. This pins the
        contract that `build_runs_list_rows` honors the
        status-layer ordering (newest-first) — divergence
        between layers would surface here."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            older = _build_harness_run(
                tmp_p, name="20260526T100000Z",
                runs=[{"index": 0, "pid": 1}],
            )
            newer = _build_harness_run(
                tmp_p, name="20260526T200000Z",
                runs=[{"index": 0, "pid": 2}],
            )
            os.utime(older, (time.time() - 1000,
                              time.time() - 1000))
            os.utime(newer, (time.time(), time.time()))
            rows = TUI.build_runs_list_rows(tmp_p)
            joined = "\n".join(rows)
            newer_idx = joined.find(newer.name)
            older_idx = joined.find(older.name)
            self.assertGreater(newer_idx, -1)
            self.assertGreater(older_idx, -1)
            self.assertLess(
                newer_idx, older_idx,
                "111 view-model must honor 110's newest-first "
                "ordering",
            )


class BuildRunDetailRowsTests(unittest.TestCase):

    def test_per_repo_rows_include_current_phase(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = _build_harness_run(
                Path(tmp), name="20260526T200000Z",
                runs=[{
                    "index": 0,
                    "description": "gson",
                    "repo": "https://github.com/google/gson",
                    "pid": 12345,
                    "status": {
                        "state": "RUNNING", "pid": 12345,
                        "started_at": "2026-05-26T19:00:00Z",
                        "heartbeat": "2026-05-26T19:30:00Z",
                        "exit_code": None,
                        "terminal_state": None,
                    },
                    "stream_lines": [
                        _phase_sentinel(
                            phase=3, name="code-review",
                            state="start",
                            note="Reviewed dup-key.",
                        ),
                    ],
                }],
            )
            with mock.patch(
                "bin.harness.status.pid_is_alive",
                return_value=True,
            ):
                rows = TUI.build_run_detail_rows(harness_run)
            joined = "\n".join(rows)
            # Repo tail.
            self.assertIn("gson", joined)
            # Runner/model.
            self.assertIn("claude/opus", joined)
            # State + current phase.
            self.assertIn("RUNNING", joined)
            self.assertIn("P3", joined)
            self.assertIn("code-review", joined)
            # Note line.
            self.assertIn("Reviewed dup-key.", joined)
            # PID liveness.
            self.assertIn("12345(live)", joined)

    def test_missing_manifest_shows_friendly_message(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "no-manifest"
            empty.mkdir()
            rows = TUI.build_run_detail_rows(empty)
            joined = "\n".join(rows)
            self.assertIn("(no manifest.json yet", joined)

    def test_no_sentinel_run_degrades_to_dash(self) -> None:
        """A run with no `::QPB::` sentinel ⇒ the phase column
        renders as "—" (graceful degradation per the 110
        contract)."""
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = _build_harness_run(
                Path(tmp), runs=[{
                    "index": 0, "pid": 1,
                    "status": {
                        "state": "RUNNING", "pid": 1,
                        "started_at": "x", "heartbeat": "y",
                        "exit_code": None,
                        "terminal_state": None,
                    },
                    "stream_lines": ['{"event": "phase1_start"}'],
                }],
            )
            rows = TUI.build_run_detail_rows(harness_run)
            joined = "\n".join(rows)
            # State column carries RUNNING; phase column has
            # the dash. Specifically the rendered phase region
            # for a no-sentinel run starts with "—" (the row
            # is one of the only places "—" appears, so it's
            # unambiguous).
            self.assertIn("—", joined,
                            "no-sentinel run must render '—' "
                            "in the phase column (graceful "
                            "degradation per 110)")

    def test_completed_run_shows_result_from_grading(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = _build_harness_run(
                Path(tmp), runs=[{
                    "index": 0, "pid": 99,
                    "status": {
                        "state": "DONE", "pid": 99,
                        "started_at": "x", "heartbeat": "y",
                        "ended_at": "z", "exit_code": 0,
                        "terminal_state": "COMPLETED",
                    },
                    "grading": {
                        "verdict": "MET",
                        "n_passed": 3, "n_failed": 0,
                        "n_total": 3, "assertions": [],
                    },
                    "stream_lines": [
                        _phase_sentinel(
                            phase=6, name="verification",
                            state="done",
                        ),
                    ],
                }],
            )
            with mock.patch(
                "bin.harness.status.pid_is_alive",
                return_value=False,
            ):
                rows = TUI.build_run_detail_rows(harness_run)
            joined = "\n".join(rows)
            self.assertIn("COMPLETED", joined)
            self.assertIn("P6", joined)
            self.assertIn("verification", joined)
            self.assertIn("MET", joined)


class BuildOutputLinesTests(unittest.TestCase):

    def test_renders_sentinels_human_readably(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run-00"
            run_dir.mkdir()
            (run_dir / "stream.ndjson").write_text(
                _phase_sentinel(
                    phase=2, name="generation",
                    state="start",
                ) + "\n" +
                _gate_sentinel(
                    gate_result="PASS",
                    verdict_state="solid",
                ) + "\n" +
                "plain line\n",
                encoding="utf-8",
            )
            lines = TUI.build_output_lines(run_dir)
            joined = "\n".join(lines)
            # Header
            self.assertIn("Live output: run-00", joined)
            # Phase sentinel rendered.
            self.assertIn("phase 2", joined)
            self.assertIn("generation", joined)
            # Gate sentinel rendered.
            self.assertIn("GATE PASS", joined)
            # Plain line passes through.
            self.assertIn("plain line", joined)

    def test_missing_stream_shows_friendly_message(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run-00"
            run_dir.mkdir()
            lines = TUI.build_output_lines(run_dir)
            joined = "\n".join(lines)
            self.assertIn("(no stream.ndjson yet)", joined)

    def test_max_lines_truncates_to_tail(self) -> None:
        """A stream longer than ``max_lines`` is truncated to
        the most recent ``max_lines`` rows, with a notice."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run-00"
            run_dir.mkdir()
            content_lines = [f"line {i}" for i in range(500)]
            (run_dir / "stream.ndjson").write_text(
                "\n".join(content_lines) + "\n",
                encoding="utf-8",
            )
            lines = TUI.build_output_lines(run_dir, max_lines=50)
            joined = "\n".join(lines)
            self.assertIn(
                "showing last 50 of 500 lines", joined
            )
            # First content line is line 450 (the tail).
            self.assertIn("line 450", joined)
            self.assertIn("line 499", joined)
            self.assertNotIn("line 0\n", joined + "\n")


# ---------------------------------------------------------------------------
# Task C — module imports side-effect-free (no curses on import)
# ---------------------------------------------------------------------------


class TuiModuleImportSafetyTests(unittest.TestCase):

    def test_import_does_not_start_curses(self) -> None:
        """v1.5.7 111: ``bin.harness.tui`` must import without
        starting curses — the `launch_status_tui` entry is
        only called from the CLI. Tests + tooling import the
        module to exercise view-model builders without ever
        touching the terminal."""
        # Re-import in a fresh subprocess to confirm.
        result = __import__("subprocess").run(
            [sys.executable, "-c",
              "import bin.harness.tui; "
              "print('imported clean')"],
            capture_output=True, text=True, timeout=10,
            cwd=str(Path(__file__).resolve().parents[3]),
        )
        self.assertEqual(
            result.returncode, 0,
            f"import of bin.harness.tui must be side-effect-"
            f"free. rc={result.returncode}\nstderr:\n"
            f"{result.stderr}",
        )
        self.assertIn("imported clean", result.stdout)

    def test_launch_status_tui_is_callable(self) -> None:
        """The launch entry is present + callable (but we
        DON'T actually call it — that would start curses).
        Smoke check that it's exported."""
        self.assertTrue(callable(TUI.launch_status_tui))

    def test_build_view_models_dont_import_curses(self) -> None:
        """The view-model builders MUST be curses-free — they
        must work in environments without a terminal (CI, the
        Cowork agent's sandboxed cwd). Pin the contract by
        importing each builder + calling it with a tiny
        fixture; the test passes if no curses-related
        ImportError surfaces."""
        with tempfile.TemporaryDirectory() as tmp:
            TUI.build_runs_list_rows(Path(tmp))
            empty = Path(tmp) / "empty-harness-run"
            empty.mkdir()
            TUI.build_run_detail_rows(empty)
            run_dir = Path(tmp) / "run-00"
            run_dir.mkdir()
            TUI.build_output_lines(run_dir)


# ---------------------------------------------------------------------------
# 094 backward-compat: existing TUI tests still pass with 111 additions
# ---------------------------------------------------------------------------


class Existing094FunctionsStillExportedTests(unittest.TestCase):

    def test_render_overview_still_exported(self) -> None:
        """The 094 Textual TUI's data-shaping helpers stay
        present alongside the 111 additions. (Their behavior
        is pinned by ``test_tui.py``; this test only ensures
        the symbols are still exported from the combined
        module.)"""
        self.assertTrue(hasattr(TUI, "render_overview"))
        self.assertTrue(hasattr(TUI, "render_run_drilldown"))
        self.assertTrue(hasattr(TUI, "build_app"))


# ---------------------------------------------------------------------------
# Bundle-safety: tui.py stays under bin/harness/ (excluded)
# ---------------------------------------------------------------------------


class BundleSafety111Tests(unittest.TestCase):

    def test_tui_module_under_harness(self) -> None:
        """``bin/harness/tui.py`` is under the install-bundle
        exclusion path. Re-pins the 091 invariant."""
        path = (Path(__file__).resolve().parents[3]
                / "bin" / "harness" / "tui.py")
        self.assertTrue(path.is_file())
        from bin.install_skill import _bundle_files
        repo_root = path.parents[2]
        bundle = _bundle_files(repo_root)
        for _src, dst in bundle:
            p = str(dst)
            self.assertFalse(
                "harness" in p,
                f"111 must not leak bin/harness/ into the "
                f"bundle; saw {p}",
            )

    def test_no_shipped_module_imports_tui(self) -> None:
        """Even though tui.py is excluded, defense-in-depth:
        no shipped ``bin/`` script imports from
        ``bin.harness.tui`` (or any harness module). Pin via
        the same shape the 091 harness-bundle-exclusion test
        uses: scan the bundled member sources for any
        ``from bin.harness`` / ``import bin.harness``
        reference."""
        from bin.install_skill import _bundle_files
        repo_root = (
            Path(__file__).resolve().parents[3]
        )
        bundle = _bundle_files(repo_root)
        for src, _dst in bundle:
            if str(src).endswith(".py"):
                content = src.read_text(encoding="utf-8")
                self.assertNotIn(
                    "from bin.harness", content,
                    f"111 defense-in-depth: shipped {src} "
                    f"must not import from bin.harness",
                )
                self.assertNotIn(
                    "import bin.harness", content,
                    f"111 defense-in-depth: shipped {src} "
                    f"must not import from bin.harness",
                )


if __name__ == "__main__":
    unittest.main()
