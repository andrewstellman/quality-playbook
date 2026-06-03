"""v1.5.7 147 — `qpb_harness kill <path>` CLI + TUI `k` binding.

CLI: classifies the path (RUN_NN → one; HARNESS_RUN → all RUNNING;
RUNS_ROOT → error), prompts unless -y, reports killed/skipped.
TUI: pure `_confirm_kill_decision` (the testable seam) + the `k`
binding registration (the closure-local key-event wiring is
operator-confirmable per the 119/139 invariant).

`runner.kill_run` + the status-layer reads are mocked so no real
process is signalled.
"""
from __future__ import annotations

import io
import json
import tempfile
import types
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest import mock

from bin import qpb_harness as Q
from bin.harness import status as ST
from bin.harness import runner as R
from bin.harness import tui as T


def _harness_run(tmp: str, n_runs: int = 1) -> Path:
    hr = Path(tmp) / "20260529T120000Z"
    runs = []
    for i in range(n_runs):
        rd = hr / f"run-{i:02d}"
        rd.mkdir(parents=True, exist_ok=True)
        (rd / "stream.ndjson").write_text("", encoding="utf-8")
        runs.append({"index": i, "run_dir": str(rd)})
    (hr / "manifest.json").write_text(
        json.dumps({"harness_run_dir": str(hr), "runs": runs}) + "\n",
        encoding="utf-8")
    return hr


def _rs(run_dir: Path, *, state="RUNNING", pid=111, index=0):
    """A RunStatus-like for _cmd_kill (only the fields it reads)."""
    return types.SimpleNamespace(
        index=index, run_dir=run_dir, repo="https://github.com/x/gson",
        runner="claude", model="sonnet", state=state, pid=pid,
        elapsed_s=125.0)


def _fake_kill_result(run_dir, *, was_alive=True, still=False):
    return R.KillResult(
        run_dir=run_dir, pid=111, was_alive=was_alive,
        signal_sent=9, terminal_state="KILLED",
        still_alive_after_grace=still)


class ConfirmDecisionTests(unittest.TestCase):

    def test_confirm_kill_decision(self) -> None:
        self.assertTrue(T._confirm_kill_decision("y"))
        self.assertTrue(T._confirm_kill_decision("Y"))
        self.assertFalse(T._confirm_kill_decision("n"))
        self.assertFalse(T._confirm_kill_decision(""))
        self.assertFalse(T._confirm_kill_decision("yes"))  # exact y only


class CliKillTests(unittest.TestCase):

    def _run(self, *argv, stdin_text=None):
        out, err = io.StringIO(), io.StringIO()
        ctx = mock.patch("builtins.input",
                         side_effect=(lambda _p="": stdin_text)) \
            if stdin_text is not None else mock.patch(
                "builtins.input", return_value="y")
        with ctx, redirect_stdout(out), redirect_stderr(err):
            rc = Q.main(list(argv))
        return rc, out.getvalue(), err.getvalue()

    def test_kill_run_nn_path_invokes_kill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hr = _harness_run(tmp, 1)
            run = hr / "run-00"
            with mock.patch.object(
                    ST, "read_one_run_status_for_dir",
                    return_value=_rs(run)), \
                 mock.patch.object(
                    R, "kill_run",
                    return_value=_fake_kill_result(run)) as m_kill:
                rc, out, _ = self._run("kill", str(run), "-y")
            self.assertEqual(rc, 0)
            m_kill.assert_called_once()
            self.assertEqual(m_kill.call_args.args[0].name, "run-00")
            self.assertIn("Killed:", out)

    def test_kill_harness_run_iterates_only_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hr = _harness_run(tmp, 3)
            statuses = [
                _rs(hr / "run-00", state="RUNNING", index=0),
                _rs(hr / "run-01", state="ABORTED_PREP", index=1),
                _rs(hr / "run-02", state="RUNNING", index=2),
            ]
            with mock.patch.object(ST, "read_run_status",
                                   return_value=statuses), \
                 mock.patch.object(
                    R, "kill_run",
                    side_effect=lambda rd, **k: _fake_kill_result(rd)
                 ) as m_kill:
                rc, out, _ = self._run("kill", str(hr), "-y")
            self.assertEqual(rc, 0)
            killed_dirs = {c.args[0].name for c in m_kill.call_args_list}
            self.assertEqual(killed_dirs, {"run-00", "run-02"})
            self.assertIn("Skipped:", out)
            self.assertIn("run-01", out)

    def test_kill_runs_root_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _harness_run(tmp, 1)
            with mock.patch.object(R, "kill_run") as m_kill:
                rc, _out, err = self._run("kill", tmp, "-y")
            self.assertEqual(rc, 2)
            self.assertIn("too broad", err)
            m_kill.assert_not_called()

    def test_yes_flag_skips_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hr = _harness_run(tmp, 1)
            run = hr / "run-00"
            with mock.patch.object(
                    ST, "read_one_run_status_for_dir",
                    return_value=_rs(run)), \
                 mock.patch.object(
                    R, "kill_run",
                    return_value=_fake_kill_result(run)), \
                 mock.patch("builtins.input",
                            side_effect=AssertionError(
                                "prompt must not be read with -y")):
                with redirect_stdout(io.StringIO()), \
                     redirect_stderr(io.StringIO()):
                    rc = Q.main(["kill", str(run), "-y"])
            self.assertEqual(rc, 0)

    def test_without_yes_cancels_on_n(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hr = _harness_run(tmp, 1)
            run = hr / "run-00"
            with mock.patch.object(
                    ST, "read_one_run_status_for_dir",
                    return_value=_rs(run)), \
                 mock.patch.object(R, "kill_run") as m_kill:
                rc, out, _ = self._run("kill", str(run),
                                       stdin_text="n")
            self.assertEqual(rc, 0)
            m_kill.assert_not_called()
            self.assertIn("no runs killed", out)

    def test_graceful_passes_sigterm(self) -> None:
        import signal as _signal
        with tempfile.TemporaryDirectory() as tmp:
            hr = _harness_run(tmp, 1)
            run = hr / "run-00"
            with mock.patch.object(
                    ST, "read_one_run_status_for_dir",
                    return_value=_rs(run)), \
                 mock.patch.object(
                    R, "kill_run",
                    return_value=_fake_kill_result(run)) as m_kill:
                self._run("kill", str(run), "-y", "--graceful")
            self.assertEqual(m_kill.call_args.kwargs["sig"],
                             _signal.SIGTERM)


class TuiKillBindingTests(unittest.TestCase):
    """The textual App + its BINDINGS are closure-local (119
    no-textual invariant), so assert the binding + handler
    registration at the source level (introspection-style)."""

    _TUI_SRC = (Path(__file__).resolve().parents[2]
                / "harness" / "tui.py").read_text(encoding="utf-8")

    def test_k_binding_registered(self) -> None:
        self.assertIn('Binding("k", "kill_run"', self._TUI_SRC)

    def test_kill_action_and_confirm_wiring_present(self) -> None:
        # v1.5.7 151: the y/N confirm is now a ModalScreen pushed by
        # action_kill_run (the 147 on_key/_kill_pending flow was
        # replaced — fixes Bugs A/B). _confirm_kill_decision is kept
        # (vestigial) so 147's unit tests still import it.
        self.assertIn("def action_kill_run", self._TUI_SRC)
        self.assertIn("push_screen", self._TUI_SRC)
        self.assertIn("_confirm_kill_decision", self._TUI_SRC)

    def test_runs_list_kill_scoped_to_highlighted_harness_run(
            self) -> None:
        # v1.5.7 151 (Bug C): runs-list `k` now kills all RUNNING in
        # the HIGHLIGHTED harness run (no longer a no-op); a harness
        # run with none shows "no RUNNING runs to kill".
        self.assertIn("no RUNNING runs to kill", self._TUI_SRC)
        self.assertIn("_do_kill_many", self._TUI_SRC)
        # The old 147 "not available on the runs list" no-op is gone.
        self.assertNotIn("kill is not available on the runs list",
                         self._TUI_SRC)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
