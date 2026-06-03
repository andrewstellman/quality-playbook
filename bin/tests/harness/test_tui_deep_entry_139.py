"""v1.5.7 139 — interactive TUI deep-entry (closes 135 FLAG 3).

`tui repos/<TS>/run-NN` now opens the per-run OUTPUT screen (not the
top-level runs-list); `tui repos/<TS>` opens the DETAIL screen. The
fix is an optional `initial_focus=(TuiPathKind, Path)` kwarg on both
entry points (`launch_textual_tui` / `launch_status_tui`), whose
initial nav state is derived by the shared, pure
`_resolve_initial_nav_state` — the textual App and the curses loop
both consume it, so the deep-entry screen AND the q/esc back-nav
parent targets are identical across the two backends.

The textual `QPBHarnessApp` is a CLOSURE-LOCAL class inside
`launch_textual_tui` (it must stay there so `bin.harness.tui` imports
cleanly without `textual` — the 119 invariant), so it is not directly
constructable in a test. `_resolve_initial_nav_state` is therefore the
testable seam: the App's `__init__` sets `(_nav, _current_dir,
_current_run_dir)` straight from it, and `on_mount` → `refresh_view`
dispatches the initial screen by `_nav`. The load-bearing
mutation-bite is on the helper.
"""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest import mock

from bin import qpb_harness as Q
from bin.harness import tui as T
from bin.harness.status import TuiPathKind


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def _make_harness_run(hr: Path, n_runs: int = 2) -> None:
    hr.mkdir(parents=True, exist_ok=True)
    runs = []
    for i in range(n_runs):
        rd = hr / f"run-{i:02d}"
        rd.mkdir(parents=True, exist_ok=True)
        (rd / "stream.ndjson").write_text("", encoding="utf-8")
        runs.append({
            "index": i, "description": f"r{i}",
            "repo": f"https://github.com/x/repo{i}",
            "runner": "claude", "model": "opus", "channel": "clone",
            "mode": "A", "target_dir": str(rd / "target"),
            "run_dir": str(rd), "run_id": f"r{i}", "pid": None,
            "started_at": "", "stream_path": str(rd / "stream.ndjson"),
            "status_path": str(rd / "status.json"),
            "max_duration_s": 60.0, "expect": {},
        })
    (hr / "manifest.json").write_text(
        json.dumps({"harness_run_dir": str(hr),
                    "plan": {"pools": {"claude": 1}},
                    "runs": runs}, indent=2) + "\n",
        encoding="utf-8")


# ---------------------------------------------------------------------------
# _resolve_initial_nav_state — the shared seam (load-bearing)
# ---------------------------------------------------------------------------


class ResolveInitialNavStateTests(unittest.TestCase):

    def test_none_is_runs_list(self) -> None:
        self.assertEqual(
            T._resolve_initial_nav_state(None),
            (T._NAV_LIST, None, None))

    def test_runs_root_kind_is_runs_list(self) -> None:
        p = Path("/x/repos")
        self.assertEqual(
            T._resolve_initial_nav_state((TuiPathKind.RUNS_ROOT, p)),
            (T._NAV_LIST, None, None))

    def test_harness_run_opens_at_detail(self) -> None:
        p = Path("/x/repos/TS")
        self.assertEqual(
            T._resolve_initial_nav_state((TuiPathKind.HARNESS_RUN, p)),
            (T._NAV_DETAIL, p, None))

    def test_run_nn_opens_at_output_with_parent_as_back_target(
            self) -> None:
        """LOAD-BEARING: RUN_NN ⇒ OUTPUT screen, current_run_dir =
        the run, current_dir = its parent harness-run (so q/esc back
        lands on the parent's detail page). Mutation-bite: if
        initial_focus is ignored (returns LIST/None/None), this
        assertion fails."""
        run = Path("/x/repos/TS/run-01")
        nav, current_dir, current_run_dir = (
            T._resolve_initial_nav_state((TuiPathKind.RUN_NN, run)))
        self.assertEqual(nav, T._NAV_OUTPUT)
        self.assertEqual(current_run_dir, run)
        self.assertEqual(current_dir, run.parent)  # back-nav target


# ---------------------------------------------------------------------------
# _cmd_tui dispatch — initial_focus wired by classified kind
# ---------------------------------------------------------------------------


class CmdTuiInitialFocusTests(unittest.TestCase):

    def _run_tui_capture_focus(self, *argv):
        """Invoke `qpb_harness tui ...` with BOTH entry points
        mocked; return (entry_point_name, initial_focus) for whichever
        was called, or (None, None) if neither (e.g. --dump)."""
        with mock.patch.object(T, "launch_textual_tui",
                               return_value=0) as m_tx, \
             mock.patch.object(T, "launch_status_tui",
                               return_value=0) as m_cur:
            with redirect_stdout(io.StringIO()), \
                 redirect_stderr(io.StringIO()):
                rc = Q.main(list(argv))
            self.assertEqual(rc, 0, f"argv={argv}")
            if m_tx.called:
                return ("textual", m_tx.call_args.kwargs.get("initial_focus"))
            if m_cur.called:
                return ("curses", m_cur.call_args.kwargs.get("initial_focus"))
            return (None, None)

    def test_harness_run_path_opens_at_detail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hr = Path(tmp) / "TS"
            _make_harness_run(hr)
            who, focus = self._run_tui_capture_focus("tui", str(hr))
            self.assertIsNotNone(who)
            self.assertEqual(focus, (TuiPathKind.HARNESS_RUN, hr.resolve()))

    def test_run_nn_path_opens_at_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hr = Path(tmp) / "TS"
            _make_harness_run(hr)
            run = hr / "run-01"
            who, focus = self._run_tui_capture_focus("tui", str(run))
            self.assertIsNotNone(who)
            self.assertEqual(focus, (TuiPathKind.RUN_NN, run.resolve()))

    def test_runs_root_opens_at_top(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _make_harness_run(Path(tmp) / "TS")
            who, focus = self._run_tui_capture_focus("tui", tmp)
            self.assertIsNotNone(who)
            self.assertIsNone(focus)

    def test_back_compat_runs_root_flag_opens_at_top(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _make_harness_run(Path(tmp) / "TS")
            who, focus = self._run_tui_capture_focus(
                "tui", "--runs-root", tmp)
            self.assertIsNotNone(who)
            self.assertIsNone(focus)

    def test_curses_flag_also_gets_initial_focus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hr = Path(tmp) / "TS"
            _make_harness_run(hr)
            run = hr / "run-00"
            who, focus = self._run_tui_capture_focus(
                "tui", str(run), "--curses")
            self.assertEqual(who, "curses")  # --curses forces this path
            self.assertEqual(focus, (TuiPathKind.RUN_NN, run.resolve()))

    def test_dump_path_does_not_launch_interactive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hr = Path(tmp) / "TS"
            _make_harness_run(hr)
            who, focus = self._run_tui_capture_focus(
                "tui", str(hr / "run-00"), "--dump")
            self.assertIsNone(who)  # headless dump, neither launcher
            self.assertIsNone(focus)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
