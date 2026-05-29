"""v1.5.7 149 — plan-file shortcut: `qpb_harness <plan.json>
[<runs-root>] [flags]` dispatches to `run-plan` (single-positional
UX, parallel to 135's path classifier).

`_maybe_plan_file_shortcut` is a conservative pre-argparse rewrite —
it fires ONLY when argv[0] is not a known subcommand, ends `.json`,
is an existing file, AND parses as a valid plan via load_plan.
Anything else falls through to argparse's normal error handling.
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
from unittest import mock

from bin import qpb_harness as Q

VALID_PLAN = {
    "pools": {"claude": 1},
    "runs": [{
        "description": "x", "repo": "https://github.com/google/gson",
        "ref": "main", "runner": "claude", "model": "sonnet",
        "channel": "clone", "expect": {},
    }],
}


def _plan_file(tmp: str, doc=None) -> Path:
    p = Path(tmp) / "plan.json"
    p.write_text(json.dumps(doc if doc is not None else VALID_PLAN),
                 encoding="utf-8")
    return p


class MaybeShortcutTests(unittest.TestCase):

    def test_explicit_run_plan_unchanged(self) -> None:
        argv = ["run-plan", "p.json", "--runs-root", "r"]
        self.assertEqual(Q._maybe_plan_file_shortcut(argv), argv)

    def test_known_subcommand_takes_precedence(self) -> None:
        # status takes a path positional — the shortcut must NOT
        # catch a .json arg to a real subcommand.
        argv = ["status", "p.json"]
        self.assertEqual(Q._maybe_plan_file_shortcut(argv), argv)

    def test_all_subcommands_take_precedence(self) -> None:
        for sub in ("run", "run-plan", "collect", "status", "tail",
                    "manager", "tui", "kill"):
            self.assertEqual(
                Q._maybe_plan_file_shortcut([sub, "p.json"]),
                [sub, "p.json"], sub)

    def test_plan_with_runs_root_synthesizes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = _plan_file(tmp)
            self.assertEqual(
                Q._maybe_plan_file_shortcut([str(p), "repos/"]),
                ["run-plan", str(p), "--runs-root", "repos/"])

    def test_plan_without_runs_root_synthesizes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = _plan_file(tmp)
            self.assertEqual(
                Q._maybe_plan_file_shortcut([str(p)]),
                ["run-plan", str(p)])

    def test_plan_with_runs_root_and_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = _plan_file(tmp)
            self.assertEqual(
                Q._maybe_plan_file_shortcut(
                    [str(p), "r", "--max-per-provider", "anthropic=1"]),
                ["run-plan", str(p), "--runs-root", "r",
                 "--max-per-provider", "anthropic=1"])

    def test_plan_with_flag_immediately_after(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = _plan_file(tmp)
            self.assertEqual(
                Q._maybe_plan_file_shortcut(
                    [str(p), "--max-per-provider", "anthropic=1"]),
                ["run-plan", str(p),
                 "--max-per-provider", "anthropic=1"])

    def test_json_file_not_a_plan_falls_through(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = _plan_file(tmp, doc={"random": "stuff"})
            self.assertEqual(
                Q._maybe_plan_file_shortcut([str(p)]), [str(p)])

    def test_json_file_does_not_exist_falls_through(self) -> None:
        self.assertEqual(
            Q._maybe_plan_file_shortcut(["nope.json"]), ["nope.json"])

    def test_non_json_first_arg_falls_through(self) -> None:
        self.assertEqual(
            Q._maybe_plan_file_shortcut(["foo.txt", "bar"]),
            ["foo.txt", "bar"])

    def test_empty_argv_unchanged(self) -> None:
        self.assertEqual(Q._maybe_plan_file_shortcut([]), [])


class MainDispatchTests(unittest.TestCase):
    """End-to-end: main() routes the shortcut form to _cmd_run_plan
    with the synthesized args."""

    def _run(self, argv):
        with mock.patch.object(Q, "_cmd_run_plan",
                               return_value=0) as m_rp:
            with redirect_stdout(io.StringIO()), \
                 redirect_stderr(io.StringIO()):
                rc = Q.main(argv)
        return rc, m_rp

    def test_main_shortcut_dispatches_to_run_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = _plan_file(tmp)
            rc, m_rp = self._run([str(p), tmp])
            self.assertEqual(rc, 0)
            m_rp.assert_called_once()
            args = m_rp.call_args.args[0]
            self.assertEqual(args.plan_file, str(p))
            self.assertEqual(args.runs_root, tmp)

    def test_main_explicit_run_plan_still_works(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = _plan_file(tmp)
            rc, m_rp = self._run(
                ["run-plan", str(p), "--runs-root", tmp])
            self.assertEqual(rc, 0)
            self.assertEqual(m_rp.call_args.args[0].plan_file, str(p))
            self.assertEqual(m_rp.call_args.args[0].runs_root, tmp)


class RunsRootDefaultUnificationTests(unittest.TestCase):
    """v1.5.7 149 Task A0 — unify the runs-root default to
    ./harness_runs/ (underscore) across run-plan + _default_runs_root
    + .gitignore."""

    def test_run_plan_default_runs_root_is_harness_runs(self) -> None:
        # A0.1: --runs-root default is None → _cmd_run_plan resolves
        # it to ./harness_runs/. Assert the EFFECTIVE default.
        parser = Q._build_parser()
        args = parser.parse_args(["run-plan", "x.json"])
        self.assertIsNone(args.runs_root)  # argparse default
        effective = Path(args.runs_root or "harness_runs")
        self.assertEqual(effective.name, "harness_runs")

    def test_default_runs_root_helper_returns_harness_runs(
            self) -> None:
        # A0.2: unconditional ./harness_runs/ (no repos/ chain).
        self.assertEqual(Q._default_runs_root(),
                         Path("harness_runs"))

    def test_gitignore_contains_harness_runs_rule(self) -> None:
        # A0.3: .gitignore excludes harness_runs/.
        gitignore = (Path(__file__).resolve().parents[2]
                     / ".gitignore")
        lines = [ln.strip()
                 for ln in gitignore.read_text(
                     encoding="utf-8").splitlines()]
        self.assertIn("harness_runs/", lines)


class GracefulAbsentDefaultTests(unittest.TestCase):
    """v1.5.7 149 A0 (Option 1) — the read commands fall back to
    ./harness_runs/ when no path is given; when that DEFAULT dir is
    absent they degrade to a soft "No harness-runs" (exit 0), not a
    hard "is not a directory" (exit 2). An EXPLICIT absent path still
    errors exit 2 (covered by the 110/135 suites). Pinned to a clean
    temp cwd so a stray ./harness_runs/ on the dev box can't flake it."""

    def test_no_arg_tui_dump_graceful_when_default_absent(
            self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as tmp:
            # No harness_runs/ in this cwd → the default resolves to a
            # nonexistent dir, exercising the from_default soft path.
            self.assertFalse((Path(tmp) / "harness_runs").exists())
            env = dict(os.environ, PYTHONPATH=str(repo_root))
            proc = subprocess.run(
                [sys.executable, "-m", "bin.qpb_harness",
                 "tui", "--dump", "detail"],
                cwd=tmp, env=env,
                capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(
                proc.returncode, 0,
                f"stdout={proc.stdout[:300]!r} "
                f"stderr={proc.stderr[:300]!r}")
            combined = proc.stdout + proc.stderr
            # Mutation-bite: dropping the from_default special-case
            # sends this down the explicit-path branch → exit 2 +
            # "is not a directory", failing BOTH assertions below.
            self.assertIn("No harness-runs under", combined)
            self.assertNotIn("is not a directory", combined)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
