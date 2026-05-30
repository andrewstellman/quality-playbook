"""v1.5.7 158 — orchestrator launch UX banner + stderr/stdout split.

Tasks A + C from the instruction. Task B (`--detach`) is split to a
159 follow-up — Task B requires plumbing a forced run_id through
plan_runner.run_plan so the parent's banner can name the harness-run
dir BEFORE the child creates it, plus subprocess.Popen plumbing for
the fork/log-redirect, and a Popen-mocking test fixture. The
instruction's Halt #4 ("STOP and propose alternative test shapes")
authorized surfacing for a separate scope.

What 158 ships:
  * Task A — done-banner at the end of `run-plan` orchestration with
    the harness-run dir (relative path) + copy-pastable tui/status/
    kill commands + "this shell can close safely" message.
  * Task C — banner to STDERR; STDOUT carries only the single
    relative path for scripted use
    (``HRD=$(python3 -m bin.qpb_harness <plan>)``).

The pre-158 terse output ("harness-run dir: <abs>" + "collector pid
N; check status with `python3 -m bin.qpb_harness status`") is
replaced — no information lost; all of it is folded into the banner.
"""
from __future__ import annotations

import io
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest import mock

from bin import qpb_harness as Q


# ---------------------------------------------------------------------------
# Unit tests for the banner helpers
# ---------------------------------------------------------------------------


class FormatPoolsForBannerTests(unittest.TestCase):

    def test_renders_canonical_three_pool_shape(self) -> None:
        self.assertEqual(
            Q._format_pools_for_banner(
                {"claude": 3, "codex": 2, "copilot": 2}),
            "claude=3 codex=2 copilot=2")

    def test_preserves_insertion_order(self) -> None:
        # The plan author chose the order; the banner echoes it.
        self.assertEqual(
            Q._format_pools_for_banner(
                {"copilot": 1, "claude": 2}),
            "copilot=1 claude=2")

    def test_empty_pools_renders_empty_string(self) -> None:
        self.assertEqual(Q._format_pools_for_banner({}), "")

    def test_non_mapping_input_returns_empty(self) -> None:
        self.assertEqual(Q._format_pools_for_banner(None), "")
        self.assertEqual(Q._format_pools_for_banner("not a dict"), "")


class RelpathForBannerTests(unittest.TestCase):

    def test_relative_when_under_cwd(self) -> None:
        p = Path.cwd() / "harness_runs" / "20260530T042650Z"
        self.assertEqual(
            Q._relpath_for_banner(p),
            "harness_runs/20260530T042650Z")

    def test_absolute_fallback_when_outside_cwd(self) -> None:
        # /tmp is reliably outside the test runner's cwd.
        p = Path("/tmp/test-158-elsewhere/run")
        self.assertEqual(Q._relpath_for_banner(p), str(p))


class RenderLaunchBannerTests(unittest.TestCase):
    """The banner is plain ASCII (no ANSI), copy-pasteable, with the
    harness-run path appearing in EACH next-step command."""

    def _render(self, **kwargs) -> str:
        defaults = dict(
            harness_run_dir=(Path.cwd()
                             / "harness_runs"
                             / "20260530T042650Z"),
            collector_pid=44201, run_count=7,
            pools={"claude": 3, "codex": 2, "copilot": 2})
        defaults.update(kwargs)
        return Q._render_launch_banner(**defaults)

    def test_banner_contains_relative_harness_run_dir(self) -> None:
        # Mutation-bite target: switching to absolute breaks the
        # operator copy-paste UX.
        b = self._render()
        self.assertIn("harness_runs/20260530T042650Z", b)
        self.assertNotIn(str(Path.cwd() / "harness_runs"), b)

    def test_banner_contains_status_command_with_path_filled_in(
            self) -> None:
        b = self._render()
        self.assertIn(
            "python3 -m bin.qpb_harness status "
            "harness_runs/20260530T042650Z", b)

    def test_banner_contains_tui_command_with_path_filled_in(
            self) -> None:
        b = self._render()
        self.assertIn(
            "python3 -m bin.qpb_harness tui "
            "harness_runs/20260530T042650Z", b)

    def test_banner_contains_kill_command_with_path_filled_in(
            self) -> None:
        b = self._render()
        self.assertIn(
            "python3 -m bin.qpb_harness kill "
            "harness_runs/20260530T042650Z", b)

    def test_banner_contains_shell_can_close_message(self) -> None:
        # The whole point of the banner: make "done-ness" explicit
        # so operators don't sit in the shell wondering.
        b = self._render()
        self.assertIn("shell can close safely", b)

    def test_banner_contains_pool_summary(self) -> None:
        b = self._render()
        self.assertIn("claude=3 codex=2 copilot=2", b)

    def test_banner_omits_pool_summary_when_empty(self) -> None:
        # Defensive: empty pools dict produces no "pools:" line.
        b = self._render(pools={})
        self.assertNotIn("pools:", b)

    def test_banner_includes_run_count(self) -> None:
        b = self._render(run_count=12)
        self.assertIn("12 runs", b)

    def test_banner_handles_missing_collector_pid(self) -> None:
        b = self._render(collector_pid=None)
        # The line should still be present and meaningful, just
        # without a numeric pid.
        self.assertIn("collector spawned", b)
        self.assertNotIn("collector pid None", b)


# ---------------------------------------------------------------------------
# Task C — stderr/stdout split via _cmd_run_plan
# ---------------------------------------------------------------------------


def _make_args(plan_file: str, runs_root: str = None) -> object:
    """Build a minimal argparse.Namespace-shaped object for the
    _cmd_run_plan dispatch (we mock plan_runner entirely)."""
    class _A:
        pass
    a = _A()
    a.plan_file = plan_file
    a.runs_root = runs_root
    a.wheel = None
    a.tgz = None
    a.max_per_provider = None
    return a


class CmdRunPlanStderrStdoutSplitTests(unittest.TestCase):
    """End-to-end through _cmd_run_plan with plan_runner.run_plan +
    plan_runner.load_plan mocked. Verifies that the banner goes to
    stderr and the single relative path goes to stdout."""

    def _invoke(self, plan_path: Path, harness_run_dir: Path,
                collector_pid: int = 9999):
        # Mock the plan_runner internals so we don't actually clone
        # repos or spawn processes; we only care about output shape.
        fake_plan = mock.MagicMock(
            pools={"claude": 1, "codex": 1})
        # outcomes shape only matters for len() — render banner.
        outcomes = [object(), object()]

        # The success branch needs runs_root.iterdir() to return our
        # harness_run_dir; the simplest way is to actually create it.
        harness_run_dir.mkdir(parents=True, exist_ok=True)

        with mock.patch.object(Q, "Path", Path), \
             mock.patch("bin.harness.plan_runner.load_plan",
                         return_value=fake_plan), \
             mock.patch("bin.harness.plan_runner.run_plan",
                         return_value=outcomes), \
             mock.patch("bin.harness.plan_runner._LAST_COLLECTOR_PID",
                         {"pid": collector_pid}):
            buf_out, buf_err = io.StringIO(), io.StringIO()
            with redirect_stdout(buf_out), redirect_stderr(buf_err):
                rc = Q._cmd_run_plan(_make_args(
                    str(plan_path),
                    runs_root=str(harness_run_dir.parent)))
            return rc, buf_out.getvalue(), buf_err.getvalue()

    def test_banner_to_stderr_path_to_stdout(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            plan_path = Path(td) / "plan.json"
            plan_path.write_text("{}", encoding="utf-8")
            hrd = Path(td) / "runs" / "20260530T042650Z"
            rc, out, err = self._invoke(plan_path, hrd)
            self.assertEqual(rc, 0)
            # stderr has the banner.
            self.assertIn("Launched:", err)
            self.assertIn("shell can close safely", err)
            self.assertIn("python3 -m bin.qpb_harness", err)
            # stdout has ONLY the path (single line, no banner).
            self.assertNotIn("=====", out)
            self.assertNotIn("Launched:", out)
            # The path the banner shows should match stdout. Use
            # resolved form because _cmd_run_plan resolves runs_root.
            self.assertEqual(out.strip(),
                             Q._relpath_for_banner(hrd.resolve()))

    def test_stdout_is_scripted_callable_just_the_path(self) -> None:
        # Mutation-bite target: extra stdout output (e.g., a stray
        # print() without file=sys.stderr) breaks the
        # ``HRD=$(qpb_harness <plan>)`` scripted use case.
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            plan_path = Path(td) / "plan.json"
            plan_path.write_text("{}", encoding="utf-8")
            hrd = Path(td) / "runs" / "20260530T042650Z"
            _, out, _ = self._invoke(plan_path, hrd)
            # Exactly one non-empty line (the path).
            non_empty = [
                ln for ln in out.splitlines() if ln.strip()]
            self.assertEqual(len(non_empty), 1,
                             f"stdout has extra lines: {out!r}")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
