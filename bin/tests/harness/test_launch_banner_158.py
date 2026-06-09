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
import os
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest import mock

from bin import qpb_harness_legacy as Q


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


def _make_args(plan_file: str, runs_root: str = None,
               foreground: bool = True) -> object:
    """Build a minimal argparse.Namespace-shaped object for the
    _cmd_run_plan dispatch (we mock plan_runner entirely). v1.5.7
    158 (revised) test default: ``foreground=True`` skips the
    auto-detach fork so the existing 17 tests exercise the
    single-process path. Tests for the revised behavior set
    ``foreground=False`` explicitly and mock ``os.fork``."""
    class _A:
        pass
    a = _A()
    a.plan_file = plan_file
    a.runs_root = runs_root
    a.wheel = None
    a.tgz = None
    a.max_per_provider = None
    a.foreground = foreground
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


class RenderLaunchBannerRevisedTests(unittest.TestCase):
    """v1.5.7 158-revised (follow-up): the revised banner contract
    adds per-run command lines, a `tail -f` log line (or foreground
    note), and "Whole-suite commands:" / "Per-run commands:" section
    headers."""

    def _render(self, **kwargs) -> str:
        defaults = dict(
            harness_run_dir=(Path.cwd()
                             / "harness_runs"
                             / "20260530T134322Z"),
            collector_pid=None, run_count=3,
            pools={"claude": 1, "codex": 1, "copilot": 1},
            per_run_entries=[
                {"index": 0, "repo": "https://github.com/x/gson",
                 "runner": "claude", "model": "opus"},
                {"index": 1, "repo": "https://github.com/x/chi",
                 "runner": "codex", "model": "gpt-5.4"},
                {"index": 2, "repo": "https://github.com/x/express",
                 "runner": "copilot", "model": "gpt-5.4"},
            ],
            log_file_path=Path(
                "/tmp/qpb-harness-20260530T134322Z.log"),
            foreground=False,
        )
        defaults.update(kwargs)
        return Q._render_launch_banner(**defaults)

    def test_banner_includes_per_run_command_lines(self) -> None:
        # Mutation-bite target: dropping the per-run loop removes
        # the per-run status commands.
        b = self._render()
        for idx in (0, 1, 2):
            self.assertIn(
                f"python3 -m bin.qpb_harness status "
                f"harness_runs/20260530T134322Z/run-{idx:02d}", b)

    def test_banner_has_whole_suite_and_per_run_section_headers(
            self) -> None:
        b = self._render()
        self.assertIn("Whole-suite commands:", b)
        self.assertIn("Per-run commands:", b)

    def test_banner_includes_tail_f_log_line(self) -> None:
        b = self._render()
        self.assertIn(
            "tail -f /tmp/qpb-harness-20260530T134322Z.log", b)

    def test_banner_omits_tail_f_when_foreground(self) -> None:
        b = self._render(foreground=True, log_file_path=None)
        self.assertNotIn("tail -f", b)
        self.assertIn("running in foreground", b)

    def test_per_run_line_shape(self) -> None:
        # Repo tail extracted from URL; runner/model present.
        b = self._render()
        self.assertIn("gson", b)
        self.assertIn("claude/opus", b)
        self.assertIn("copilot/gpt-5.4", b)

    def test_no_per_run_section_when_entries_empty(self) -> None:
        b = self._render(per_run_entries=[])
        self.assertNotIn("Per-run commands:", b)


class CmdRunPlanAutoDetachTests(unittest.TestCase):
    """v1.5.7 158-revised: when ``--foreground`` is NOT passed
    (default), ``_cmd_run_plan`` calls ``os.fork``. The parent
    prints the banner + exits; the child redirects stdio and
    continues. Tests mock os.fork to verify dispatch without
    actually forking the test process."""

    def test_default_behavior_calls_os_fork(self) -> None:
        # foreground=False (revised default) → os.fork called.
        # Mutation-bite target: removing the fork branch makes
        # os.fork not called.
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            plan_path = Path(td) / "plan.json"
            plan_path.write_text("{}", encoding="utf-8")
            fake_plan = mock.MagicMock(
                pools={"claude": 1},
                runs=[mock.MagicMock(
                    index=0,
                    repo="https://github.com/x/r",
                    runner=mock.MagicMock(value="claude"),
                    model="opus")])
            # v1.5.7 180-followup-3 FINDING-4 + followup-4
            # FINDING-6 + followup-6 FINDING-10: the spawn-then-
            # verify path now polls ``predicted_hrd /
            # "manifest.json"`` AND requires at least one
            # state=RUNNING entry, until either both pass OR
            # pid_alive returns False OR the deadline passes.
            # Mock pid_alive → True + Path.is_file → True
            # (manifest detected immediately) + time.sleep →
            # no-op + _at_least_one_running → True (happy
            # path) so the verify returns 0 fast.
            from bin.harness import _platform as _platform_mod
            with mock.patch.object(Q.os, "fork",
                                    return_value=12345) as m_fork, \
                 mock.patch.object(Q, "open",
                                    mock.mock_open(),
                                    create=True), \
                 mock.patch("bin.harness.plan_runner.load_plan",
                             return_value=fake_plan), \
                 mock.patch.object(_platform_mod, "pid_alive",
                                    return_value=True), \
                 mock.patch.object(Path, "is_dir",
                                    return_value=True), \
                 mock.patch.object(Path, "is_file",
                                    return_value=True), \
                 mock.patch("time.sleep", return_value=None), \
                 mock.patch.object(Q, "_at_least_one_running",
                                    return_value=True), \
                 mock.patch.object(Q.sys, "stdout",
                                    new=io.StringIO()), \
                 mock.patch.object(Q.sys, "stderr",
                                    new=io.StringIO()):
                args = _make_args(
                    str(plan_path), str(Path(td) / "runs"),
                    foreground=False)
                rc = Q._cmd_run_plan(args)
            self.assertEqual(rc, 0)
            m_fork.assert_called_once()

    def test_foreground_flag_skips_fork(self) -> None:
        # foreground=True → os.fork NOT called.
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            plan_path = Path(td) / "plan.json"
            plan_path.write_text("{}", encoding="utf-8")
            hrd = Path(td) / "runs" / "20260530T134322Z"
            hrd.mkdir(parents=True)
            fake_plan = mock.MagicMock(
                pools={"claude": 1},
                runs=[mock.MagicMock(
                    index=0,
                    repo="https://github.com/x/r",
                    runner=mock.MagicMock(value="claude"),
                    model="opus")])
            outcomes = [object()]
            with mock.patch.object(Q.os, "fork") as m_fork, \
                 mock.patch("bin.harness.plan_runner.load_plan",
                             return_value=fake_plan), \
                 mock.patch("bin.harness.plan_runner.run_plan",
                             return_value=outcomes), \
                 mock.patch("bin.harness.plan_runner._LAST_COLLECTOR_PID",
                             {"pid": 9999}), \
                 redirect_stdout(io.StringIO()), \
                 redirect_stderr(io.StringIO()):
                rc = Q._cmd_run_plan(_make_args(
                    str(plan_path), str(Path(td) / "runs"),
                    foreground=True))
            self.assertEqual(rc, 0)
            m_fork.assert_not_called()

    def test_detached_env_marker_prevents_re_fork(self) -> None:
        # If QPB_HARNESS_DETACHED is set, _cmd_run_plan skips the
        # fork (treats itself as already-the-child). Prevents
        # infinite recursion if a child somehow re-enters.
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            plan_path = Path(td) / "plan.json"
            plan_path.write_text("{}", encoding="utf-8")
            hrd = Path(td) / "runs" / "20260530T134322Z"
            hrd.mkdir(parents=True)
            fake_plan = mock.MagicMock(
                pools={"claude": 1},
                runs=[mock.MagicMock(
                    index=0,
                    repo="https://github.com/x/r",
                    runner=mock.MagicMock(value="claude"),
                    model="opus")])
            prev = os.environ.get("QPB_HARNESS_DETACHED")
            os.environ["QPB_HARNESS_DETACHED"] = "1"
            try:
                with mock.patch.object(Q.os, "fork") as m_fork, \
                     mock.patch("bin.harness.plan_runner.load_plan",
                                 return_value=fake_plan), \
                     mock.patch("bin.harness.plan_runner.run_plan",
                                 return_value=[object()]), \
                     mock.patch("bin.harness.plan_runner._LAST_COLLECTOR_PID",
                                 {"pid": 9999}), \
                     redirect_stdout(io.StringIO()), \
                     redirect_stderr(io.StringIO()):
                    Q._cmd_run_plan(_make_args(
                        str(plan_path), str(Path(td) / "runs"),
                        foreground=False))
                m_fork.assert_not_called()
            finally:
                if prev is None:
                    os.environ.pop("QPB_HARNESS_DETACHED", None)
                else:
                    os.environ["QPB_HARNESS_DETACHED"] = prev


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
