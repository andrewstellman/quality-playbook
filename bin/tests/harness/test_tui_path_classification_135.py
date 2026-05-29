"""v1.5.7 135 — single-positional path arg for tui / status / tail,
classified by directory shape.

Andrew's UX complaint: every TUI/status/tail invocation needed the
`--runs-root` / `--dump-mode` / `--dump-path` flag triple. 135
replaces that with ONE positional path whose page is inferred from
the directory's markers:

  RUNS_ROOT   (a subdir has manifest.json)  → runs-list page
  HARNESS_RUN (manifest.json present)        → detail page
  RUN_NN      (stream.ndjson OR target/)     → output page / single-run

Coverage:
  * `classify_tui_path` — each kind, ambiguous (ValueError),
    non-existent (FileNotFoundError), mixed empty+valid subdirs.
  * `read_one_run_status_for_dir` — single-run block for a RUN_NN dir.
  * CLI dispatch via `qpb_harness.main(...)` for tui/status/tail,
    incl. the boolean `--dump`, the new RUN_NN status level, tail's
    classifier-aware errors, and the deprecated back-compat flags.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

from bin import qpb_harness as Q
from bin.harness import status as ST


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_run_nn(run_dir: Path, *, with_stream: bool = True,
                 with_target: bool = False) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    if with_stream:
        (run_dir / "stream.ndjson").write_text("", encoding="utf-8")
    if with_target:
        (run_dir / "target").mkdir(exist_ok=True)


def _make_harness_run(hr: Path, *, n_runs: int = 1) -> None:
    """A harness-run dir: manifest.json + run-NN subdirs (each with a
    stream.ndjson)."""
    hr.mkdir(parents=True, exist_ok=True)
    runs = []
    for i in range(n_runs):
        rd = hr / f"run-{i:02d}"
        _make_run_nn(rd)
        runs.append({
            "index": i, "description": f"r{i}",
            "repo": f"https://github.com/x/repo{i}",
            "runner": "claude", "model": "opus",
            "channel": "clone", "mode": "A",
            "target_dir": str(rd / "target"),
            "run_dir": str(rd),
            "run_id": f"r{i}", "pid": None, "started_at": "",
            "stream_path": str(rd / "stream.ndjson"),
            "status_path": str(rd / "status.json"),
            "max_duration_s": 60.0, "expect": {},
        })
    (hr / "manifest.json").write_text(
        json.dumps({"harness_run_dir": str(hr),
                    "plan": {"pools": {"claude": 1}},
                    "runs": runs}, indent=2) + "\n",
        encoding="utf-8")


# ---------------------------------------------------------------------------
# classify_tui_path
# ---------------------------------------------------------------------------


class ClassifyTuiPathTests(unittest.TestCase):

    def test_run_nn_via_stream(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rd = Path(td) / "run-00"
            _make_run_nn(rd, with_stream=True)
            self.assertIs(ST.classify_tui_path(rd),
                          ST.TuiPathKind.RUN_NN)

    def test_run_nn_via_target_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rd = Path(td) / "run-00"
            _make_run_nn(rd, with_stream=False, with_target=True)
            self.assertIs(ST.classify_tui_path(rd),
                          ST.TuiPathKind.RUN_NN)

    def test_harness_run_via_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260101T000000Z"
            _make_harness_run(hr, n_runs=2)
            self.assertIs(ST.classify_tui_path(hr),
                          ST.TuiPathKind.HARNESS_RUN)

    def test_runs_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_harness_run(root / "20260101T000000Z", n_runs=1)
            self.assertIs(ST.classify_tui_path(root),
                          ST.TuiPathKind.RUNS_ROOT)

    def test_runs_root_with_mixed_empty_and_valid_subdirs(
            self) -> None:
        # An empty subdir + a target-repo clone should NOT mask the
        # real harness-run subdir.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "empty-dir").mkdir()
            (root / "gson-1.3.14").mkdir()  # benchmark clone, no manifest
            _make_harness_run(root / "20260101T000000Z", n_runs=1)
            self.assertIs(ST.classify_tui_path(root),
                          ST.TuiPathKind.RUNS_ROOT)

    def test_ambiguous_dir_raises_value_error(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            empty = Path(td) / "nothing"
            empty.mkdir()
            with self.assertRaises(ValueError):
                ST.classify_tui_path(empty)

    def test_nonexistent_raises_file_not_found(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                ST.classify_tui_path(Path(td) / "does-not-exist")

    def test_run_nn_checked_before_runs_root(self) -> None:
        # A run-NN dir that also happens to contain a subdir with a
        # manifest.json must still classify as RUN_NN (order matters).
        with tempfile.TemporaryDirectory() as td:
            rd = Path(td) / "run-00"
            _make_run_nn(rd, with_stream=True)
            _make_harness_run(rd / "weird-subdir", n_runs=1)
            self.assertIs(ST.classify_tui_path(rd),
                          ST.TuiPathKind.RUN_NN)


# ---------------------------------------------------------------------------
# read_one_run_status_for_dir
# ---------------------------------------------------------------------------


class SingleRunStatusTests(unittest.TestCase):

    def test_returns_run_status_for_matching_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260101T000000Z"
            _make_harness_run(hr, n_runs=2)
            rs = ST.read_one_run_status_for_dir(hr / "run-01")
            self.assertIsNotNone(rs)
            self.assertEqual(rs.index, 1)
            self.assertEqual(rs.repo,
                             "https://github.com/x/repo1")

    def test_returns_none_when_no_parent_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            rd = Path(td) / "run-00"
            _make_run_nn(rd)  # no parent manifest.json
            self.assertIsNone(ST.read_one_run_status_for_dir(rd))


# ---------------------------------------------------------------------------
# CLI dispatch — tui --dump (boolean, page inferred from path)
# ---------------------------------------------------------------------------


class TuiDumpDispatchTests(unittest.TestCase):

    def _dump(self, *argv) -> str:
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(io.StringIO()):
            rc = Q.main(list(argv))
        self.assertEqual(rc, 0, f"argv={argv}")
        return buf.getvalue()

    def test_dump_runs_root_renders_runs_list(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            _make_harness_run(Path(td) / "20260101T000000Z")
            out = self._dump("tui", td, "--dump")
            self.assertIn("runs-root:", out)

    def test_dump_harness_run_renders_detail(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260101T000000Z"
            _make_harness_run(hr, n_runs=2)
            out = self._dump("tui", str(hr), "--dump")
            self.assertIn("harness-run:", out)

    def test_dump_run_nn_renders_output(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260101T000000Z"
            _make_harness_run(hr, n_runs=1)
            out = self._dump("tui", str(hr / "run-00"), "--dump")
            self.assertIn("output:", out)

    def test_backward_compat_dump_enum_runs(self) -> None:
        # Old form: --runs-root X --dump runs. Still works; path's
        # shape (RUNS_ROOT) is authoritative.
        with tempfile.TemporaryDirectory() as td:
            _make_harness_run(Path(td) / "20260101T000000Z")
            out = self._dump("tui", "--runs-root", td, "--dump",
                              "runs")
            self.assertIn("runs-root:", out)

    def test_backward_compat_dump_path_detail(self) -> None:
        # Old form: --dump detail --dump-path <harness-run>.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260101T000000Z"
            _make_harness_run(hr, n_runs=1)
            out = self._dump("tui", "--dump", "detail",
                              "--dump-path", str(hr))
            self.assertIn("harness-run:", out)


# ---------------------------------------------------------------------------
# CLI dispatch — status (RUN_NN is the new level)
# ---------------------------------------------------------------------------


class StatusDispatchTests(unittest.TestCase):

    def _status(self, *argv) -> "tuple[int, str]":
        buf = io.StringIO()
        with redirect_stdout(buf), redirect_stderr(io.StringIO()):
            rc = Q.main(list(argv))
        return rc, buf.getvalue()

    def test_status_runs_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            _make_harness_run(Path(td) / "20260101T000000Z")
            rc, out = self._status("status", td)
            self.assertEqual(rc, 0)
            self.assertIn("runs-root:", out)

    def test_status_harness_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260101T000000Z"
            _make_harness_run(hr, n_runs=2)
            rc, out = self._status("status", str(hr))
            self.assertEqual(rc, 0)
            self.assertIn("harness-run dir:", out)

    def test_status_run_nn_single_block(self) -> None:
        # v1.5.7 135 NEW: a run-NN path → single-run status block.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260101T000000Z"
            _make_harness_run(hr, n_runs=2)
            rc, out = self._status("status", str(hr / "run-01"))
            self.assertEqual(rc, 0)
            self.assertIn("run: 20260101T000000Z/run-01", out)
            self.assertIn("repo1", out)

    def test_status_backward_compat_runs_root_flag(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            _make_harness_run(Path(td) / "20260101T000000Z")
            rc, out = self._status("status", "--runs-root", td)
            self.assertEqual(rc, 0)
            self.assertIn("runs-root:", out)


# ---------------------------------------------------------------------------
# CLI dispatch — tail classifier-aware errors
# ---------------------------------------------------------------------------


class TailClassifierErrorTests(unittest.TestCase):

    def _tail(self, *argv) -> "tuple[int, str]":
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = Q.main(list(argv))
        return rc, err.getvalue()

    def test_tail_harness_run_errors_with_run_listing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260101T000000Z"
            _make_harness_run(hr, n_runs=2)
            rc, err = self._tail("tail", str(hr))
            self.assertEqual(rc, 2)
            self.assertIn("is a harness-run dir", err)
            self.assertIn("run-00", err)
            self.assertIn("run-01", err)

    def test_tail_runs_root_errors(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            _make_harness_run(Path(td) / "20260101T000000Z")
            rc, err = self._tail("tail", td)
            self.assertEqual(rc, 2)
            self.assertIn("is a runs-root dir", err)

    def test_tail_run_nn_happy_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260101T000000Z"
            _make_harness_run(hr, n_runs=1)
            (hr / "run-00" / "stream.ndjson").write_text(
                "hello line\n", encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out), redirect_stderr(io.StringIO()):
                rc = Q.main(["tail", str(hr / "run-00")])
            self.assertEqual(rc, 0)
            self.assertIn("hello line", out.getvalue())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
