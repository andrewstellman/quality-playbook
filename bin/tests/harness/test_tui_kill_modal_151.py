"""v1.5.7 151 — TUI kill-confirm modal: REAL interaction tests via
Textual's `App.run_test()` headless pilot.

147 shipped the `k` kill behind a status-bar y/N prompt; real use
found it broken three ways (A: the 2s refresh overwrote the prompt;
B: a second `k` silently cancelled; C: runs-list `k` was a no-op).
147's source-grep tests passed for the wrong reason — they never
exercised the runtime. 151 replaces the flow with a `ModalScreen`
and adds these pilot-driven tests that actually press keys and
inspect the screen stack / kill_run calls.

Textual-gated (skip cleanly without the `harness` extra). Uses
`IsolatedAsyncioTestCase` since `run_test()` is async. The app is
built via `tui._build_textual_app` (151's build/run split) so the
closure-local App can be driven without `app.run()`.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bin.harness import tui as TUI
from bin.harness import runner as RUNNER
from bin.harness.status import TuiPathKind


def _textual_available() -> bool:
    try:
        import textual  # noqa: F401
        return True
    except ImportError:
        return False


def _make_harness_run(root: Path, states: "list[str]") -> Path:
    """A harness-run with one run-NN per `states` entry; each gets a
    status.json (state + pid) + stream.ndjson + manifest entry."""
    hr = root / "20260529T120000Z"
    entries = []
    for i, state in enumerate(states):
        rd = hr / f"run-{i:02d}"
        (rd / "target").mkdir(parents=True, exist_ok=True)
        (rd / "stream.ndjson").write_text("hello\n", encoding="utf-8")
        pid = 10000 + i
        (rd / "status.json").write_text(json.dumps({
            "state": state, "pid": pid,
            "started_at": "2026-05-29T12:00:00Z",
        }) + "\n", encoding="utf-8")
        entries.append({
            "index": i, "description": f"r{i}",
            "repo": f"https://github.com/x/repo{i}",
            "runner": "claude", "model": "sonnet", "channel": "clone",
            "mode": "A", "target_dir": str(rd / "target"),
            "run_dir": str(rd), "run_id": f"r{i}", "pid": pid,
            "started_at": "2026-05-29T12:00:00Z",
            "stream_path": str(rd / "stream.ndjson"),
            "status_path": str(rd / "status.json"),
            "max_duration_s": 60.0, "expect": {},
        })
    (hr / "manifest.json").write_text(json.dumps({
        "harness_run_dir": str(hr),
        "plan": {"pools": {"claude": 1}}, "runs": entries,
    }) + "\n", encoding="utf-8")
    return hr


def _kill_result(rd):
    return RUNNER.KillResult(run_dir=rd, pid=111, was_alive=True,
                             signal_sent=9, terminal_state="KILLED")


def _modal_name(app) -> str:
    return type(app.screen).__name__


@unittest.skipUnless(_textual_available(), "textual not installed")
class KillModalInteractionTests(unittest.IsolatedAsyncioTestCase):

    def _app_at_output(self, tmp):
        hr = _make_harness_run(Path(tmp), ["RUNNING"])
        run = hr / "run-00"
        app = TUI._build_textual_app(
            Path(tmp), initial_focus=(TuiPathKind.RUN_NN, run))
        return app, run

    async def test_k_on_output_pushes_kill_modal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, _run = self._app_at_output(tmp)
            async with app.run_test() as pilot:
                await pilot.press("k")
                await pilot.pause()
                self.assertEqual(_modal_name(app), "_KillConfirmScreen")

    async def test_y_calls_kill_run_once_with_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, run = self._app_at_output(tmp)
            with mock.patch.object(RUNNER, "kill_run",
                                   return_value=_kill_result(run)) as m:
                async with app.run_test() as pilot:
                    await pilot.press("k")
                    await pilot.pause()
                    await pilot.press("y")
                    await pilot.pause()
            m.assert_called_once()
            self.assertEqual(m.call_args.args[0].name, "run-00")

    async def test_n_does_not_call_kill_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, _run = self._app_at_output(tmp)
            with mock.patch.object(RUNNER, "kill_run") as m:
                async with app.run_test() as pilot:
                    await pilot.press("k")
                    await pilot.pause()
                    await pilot.press("n")
                    await pilot.pause()
            m.assert_not_called()

    async def test_esc_does_not_call_kill_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app, _run = self._app_at_output(tmp)
            with mock.patch.object(RUNNER, "kill_run") as m:
                async with app.run_test() as pilot:
                    await pilot.press("k")
                    await pilot.pause()
                    await pilot.press("escape")
                    await pilot.pause()
            m.assert_not_called()

    async def test_second_k_while_modal_open_no_new_arm(self) -> None:
        """Bug-B regression: a second `k` while the modal is up must
        NOT stack a new modal or arm a new kill."""
        with tempfile.TemporaryDirectory() as tmp:
            app, _run = self._app_at_output(tmp)
            with mock.patch.object(RUNNER, "kill_run") as m:
                async with app.run_test() as pilot:
                    await pilot.press("k")
                    await pilot.pause()
                    depth1 = len(app.screen_stack)
                    await pilot.press("k")
                    await pilot.pause()
                    depth2 = len(app.screen_stack)
                    await pilot.press("n")
                    await pilot.pause()
            self.assertEqual(depth1, depth2)  # no second modal stacked
            m.assert_not_called()

    async def test_k_on_runs_list_running_pushes_modal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _make_harness_run(Path(tmp), ["RUNNING", "COMPLETED"])
            app = TUI._build_textual_app(Path(tmp))  # runs-list
            async with app.run_test() as pilot:
                await pilot.press("k")
                await pilot.pause()
                self.assertEqual(_modal_name(app), "_KillConfirmScreen")
                self.assertIn("RUNNING run(s) in", app.screen._prompt)

    async def test_k_on_runs_list_no_running_shows_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _make_harness_run(Path(tmp), ["COMPLETED", "FAILED"])
            app = TUI._build_textual_app(Path(tmp))
            with mock.patch.object(RUNNER, "kill_run") as m:
                async with app.run_test() as pilot:
                    await pilot.press("k")
                    await pilot.pause()
                    # No modal pushed (still the base App screen).
                    self.assertNotEqual(_modal_name(app),
                                        "_KillConfirmScreen")
            m.assert_not_called()

    async def test_y_on_runs_list_kills_all_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _make_harness_run(
                Path(tmp), ["RUNNING", "COMPLETED", "RUNNING"])
            app = TUI._build_textual_app(Path(tmp))
            with mock.patch.object(
                    RUNNER, "kill_run",
                    side_effect=lambda rd, **k: _kill_result(rd)) as m:
                async with app.run_test() as pilot:
                    await pilot.press("k")
                    await pilot.pause()
                    await pilot.press("y")
                    await pilot.pause()
            self.assertEqual(m.call_count, 2)  # the 2 RUNNING runs
            killed = {c.args[0].name for c in m.call_args_list}
            self.assertEqual(killed, {"run-00", "run-02"})


class KillModalSourceTests(unittest.TestCase):
    """Structural sanity (runs without textual) — pairs with the
    runtime pilot tests above."""

    _SRC = (Path(__file__).resolve().parents[2]
            / "harness" / "tui.py").read_text(encoding="utf-8")

    def test_modal_screen_class_defined(self) -> None:
        self.assertIn("class _KillConfirmScreen(ModalScreen",
                      self._SRC)

    def test_build_app_factory_exists(self) -> None:
        # The build/run split that makes run_test() possible.
        self.assertIn("def _build_textual_app", self._SRC)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
