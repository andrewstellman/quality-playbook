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


def _make_harness_run(hr: Path, *, n_runs: int = 1,
                      with_manifest: bool = True) -> None:
    """A harness-run dir: manifest.json + run-NN subdirs (each with a
    stream.ndjson). v1.5.7 152: ``with_manifest=False`` simulates the
    Ctrl-C'd state where the orchestrator was killed before its
    late-stage manifest write — the 152 fallback should still
    classify the dir as HARNESS_RUN via the run-NN children."""
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
    if with_manifest:
        (hr / "manifest.json").write_text(
            json.dumps({"harness_run_dir": str(hr),
                        "plan": {"pools": {"claude": 1}},
                        "runs": runs}, indent=2) + "\n",
            encoding="utf-8")


def _make_artifacts_subdir(hr: Path) -> None:
    """v1.5.7 152 fixture: write the ``artifacts/manifest.json`` bundle
    manifest that caused the original 135 RUNS_ROOT scan to
    false-positive when a Ctrl-C'd harness-run had no top-level
    manifest. Mirrors the real 573-byte manifest at
    ``harness_runs/<TS>/artifacts/manifest.json``."""
    (hr / "artifacts").mkdir(parents=True, exist_ok=True)
    (hr / "artifacts" / "manifest.json").write_text(
        json.dumps({"wheel": "quality_playbook-1.5.7.whl",
                    "tgz": "quality-playbook-1.5.7.tgz"}) + "\n",
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


class ClassifyTuiPath152FallbackTests(unittest.TestCase):
    """v1.5.7 152 — two precise classifier fixes surfaced by the
    2026-05-29 ship-readiness retest, where Andrew Ctrl-C'd a plan
    before its late-stage manifest write and ``qpb_harness kill
    harness_runs/<TS>`` was wrongly rejected as "too broad":

    Task A — HARNESS_RUN fallback: a manifest-less but otherwise
    harness-run-shaped dir (timestamp name, run-NN children with
    stream.ndjson OR target/) now classifies as HARNESS_RUN.

    Task B — RUNS_ROOT name-and-shape guard: only timestamp-shaped
    children (``\\d{8}T\\d{6}Z``) with the harness-run shape trigger
    RUNS_ROOT, so infrastructure subdirs like ``artifacts/`` (which
    carry their own 573-byte bundle manifest) can't false-positive."""

    def test_harness_run_classified_when_manifest_present(
            self) -> None:
        # 152 happy-path regression guard: manifest still wins.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T214937Z"
            _make_harness_run(hr, n_runs=1, with_manifest=True)
            self.assertIs(ST.classify_tui_path(hr),
                          ST.TuiPathKind.HARNESS_RUN)

    def test_harness_run_classified_via_run_nn_children_when_manifest_absent(
            self) -> None:
        # Task A bite: no manifest.json, but a run-00/stream.ndjson
        # child → still HARNESS_RUN. Removing the
        # _dir_is_harness_run_shape fallback → falls through to the
        # RUNS_ROOT scan (the child name is "run-00" not a timestamp,
        # so the scan finds nothing) → ValueError.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T214937Z"
            _make_harness_run(hr, n_runs=1, with_manifest=False)
            self.assertIs(ST.classify_tui_path(hr),
                          ST.TuiPathKind.HARNESS_RUN)

    def test_harness_run_via_target_subdir_in_run_nn_child(
            self) -> None:
        # The empirical run-04 shape: a run-NN child with target/ but
        # no stream.ndjson still counts as the RUN_NN marker for the
        # parent's HARNESS_RUN fallback.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T214937Z"
            hr.mkdir()
            _make_run_nn(hr / "run-04",
                         with_stream=False, with_target=True)
            self.assertIs(ST.classify_tui_path(hr),
                          ST.TuiPathKind.HARNESS_RUN)

    def test_harness_run_with_only_artifacts_subdir_is_not_classifiable(
            self) -> None:
        # Task B bite: a TS-named dir with ONLY artifacts/manifest.json
        # (no run-NN children) is NOT a harness-run — it has no run
        # markers — so it shouldn't classify as anything. Dropping the
        # _RE_RUN_NN name check in _dir_is_harness_run_shape would
        # accept artifacts/ as a "RUN_NN-shaped" child and the dir would
        # wrongly become HARNESS_RUN. Dropping the TS-name guard in the
        # RUNS_ROOT scan would let artifacts/manifest.json trigger
        # RUNS_ROOT.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T214937Z"
            hr.mkdir()
            _make_artifacts_subdir(hr)
            with self.assertRaises(ValueError):
                ST.classify_tui_path(hr)

    def test_runs_root_via_child_with_run_nn_only(self) -> None:
        # Task A+B together: parent has a TS-named child that itself is
        # manifest-less but contains run-NN with the RUN_NN shape →
        # parent is RUNS_ROOT. Dropping either the TS-name guard or the
        # _dir_is_harness_run_shape recursion breaks this.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_harness_run(root / "20260529T214937Z",
                              n_runs=1, with_manifest=False)
            self.assertIs(ST.classify_tui_path(root),
                          ST.TuiPathKind.RUNS_ROOT)

    def test_runs_root_ignores_sibling_artifacts_subdir(
            self) -> None:
        # Task B bite: an `artifacts/` sibling of a real TS-named child
        # doesn't matter — the TS child triggers RUNS_ROOT, the
        # artifacts dir is filtered out by name.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_artifacts_subdir(root)
            _make_harness_run(root / "20260529T214937Z",
                              n_runs=1, with_manifest=True)
            self.assertIs(ST.classify_tui_path(root),
                          ST.TuiPathKind.RUNS_ROOT)

    def test_parent_with_only_artifacts_is_not_runs_root(
            self) -> None:
        # Task B bite (strengthen): a parent whose ONLY non-empty
        # subdir is artifacts/manifest.json must NOT classify as
        # RUNS_ROOT. Without the TS-name filter, this is the original
        # bug — the scan would happily accept artifacts/.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_artifacts_subdir(root)
            with self.assertRaises(ValueError):
                ST.classify_tui_path(root)

    def test_runs_root_excludes_non_timestamp_named_children(
            self) -> None:
        # Task B bite: a child with manifest.json but a non-TS name
        # ("something_random") shouldn't trigger RUNS_ROOT. Dropping
        # the _RE_HARNESS_RUN_NAME guard makes this wrongly classify.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _make_harness_run(root / "something_random",
                              n_runs=1, with_manifest=True)
            with self.assertRaises(ValueError):
                ST.classify_tui_path(root)

    def test_real_world_killed_harness_run_shape(self) -> None:
        # Synthesizes the exact 2026-05-29 21:49 retest shape: TS name,
        # NO top-level manifest.json, artifacts/manifest.json present
        # (573-byte bundle manifest), seven run-NN children — most
        # without stream.ndjson or target/, one (run-04) with target/.
        # Per Task A's "at least one run-NN child with the RUN_NN
        # shape" rule, the parent classifies as HARNESS_RUN.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260529T214937Z"
            hr.mkdir()
            _make_artifacts_subdir(hr)
            # six run-NN children that lack the RUN_NN markers (just
            # invocation.json etc.), plus run-04 with target/ — the
            # marker-bearing child that unlocks the HARNESS_RUN fallback.
            for i in (0, 1, 2, 3, 5, 6):
                child = hr / f"run-{i:02d}"
                child.mkdir()
                (child / "invocation.json").write_text(
                    "{}", encoding="utf-8")
            _make_run_nn(hr / "run-04",
                         with_stream=False, with_target=True)
            self.assertIs(ST.classify_tui_path(hr),
                          ST.TuiPathKind.HARNESS_RUN)


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

    def test_returns_synthesized_when_no_parent_manifest(self) -> None:
        # v1.5.7 153 Task A — contract change: a run-NN dir without a
        # parent manifest.json now synthesizes a RunStatus from the
        # dir's own on-disk artifacts (was: returned None pre-153,
        # which broke kill/status on Ctrl-C'd harness-runs). The
        # synthesized entry surfaces partial metadata rather than
        # leaving the row invisible.
        with tempfile.TemporaryDirectory() as td:
            rd = Path(td) / "run-00"
            _make_run_nn(rd)  # has stream.ndjson; no parent manifest
            rs = ST.read_one_run_status_for_dir(rd)
            self.assertIsNotNone(rs)
            self.assertEqual(rs.index, 0)
            # No manifest ⇒ repo unknown; synthesized "?" sentinel.
            self.assertEqual(rs.repo, "?")
            # No status.json ⇒ default to the PENDING sentinel.
            self.assertEqual(rs.state, "PENDING")

    def test_returns_none_when_run_dir_does_not_exist(self) -> None:
        # The new "None" case in 153: only when the run-NN dir itself
        # is absent. A queued-but-empty dir still synthesizes.
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(
                ST.read_one_run_status_for_dir(Path(td) / "run-99"))


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
