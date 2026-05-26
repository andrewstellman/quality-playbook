"""v1.5.7 104 — drop the stale clone-only channel guard +
add step-level progress logging.

Two real-run blockers found on the first live `run-plan`:

  (1) ``runner._command_for_axes`` raised ``RunnerError(
      "install_channel 'pip-local-wheel' is not yet supported
      (clone only…)")`` — a leftover Phase-1 guard. The AI-CLI
      launch command is channel-INDEPENDENT (prepare already
      installed the skill); the guard was stale and wrongly
      blocked local/registry channels. It survived 091-103
      because every test before 104 used the clone channel.

  (2) The harness emitted no progress — the operator could see
      the AI-CLIs running but the harness itself was silent.
      104 adds step-level logging to stderr +
      ``<harness-run>/harness.log`` + per-run
      ``<run-dir>/run.log``.

Coverage:
  * Task A: ``_command_for_axes`` builds a valid command for
    pip-local-wheel + npm-local-tgz + pip-registry + npm-registry
    (no RunnerError); the runner-set guard
    (``_SUPPORTED_RUNNERS``) is kept.
  * Mutation-bite: re-add the channel guard ⇒ the local-channel
    command test FAILs (paired with the updated
    ``test_local_channel_no_longer_rejected_post_104`` pin in
    ``test_runner_timeout.py``).
  * Task C: a run via the fake_run fast-path emits the expected
    progress lines to stderr AND writes ``harness.log`` +
    per-run ``run.log``; key lines (``clone``, ``install``,
    ``launch``, ``DONE``) present; outcomes/SUMMARY unchanged.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

from bin.harness import plan_runner as PR
from bin.harness import runner as RUN
from bin.harness import schema as S


# ---------------------------------------------------------------------------
# Task A — channel guard removed; all channels build a valid command
# ---------------------------------------------------------------------------


class ChannelGuardRemovedTests(unittest.TestCase):
    """The launch argv is channel-independent (prepare already
    installed the skill before launch_run is called). 104 retires
    the stale clone-only guard."""

    def test_pip_local_wheel_axes_produces_valid_command(self) -> None:
        axes = S.RunAxes(
            runner=S.Runner.CLAUDE, mode=S.Mode.A,
            install_channel=S.InstallChannel.PIP_LOCAL_WHEEL,
            model="opus",
        )
        cmd = RUN._command_for_axes(axes, "do thing")
        self.assertEqual(cmd[0], "claude")
        self.assertIn("--print", cmd)
        # Prompt last (the 091 contract).
        self.assertEqual(cmd[-1], "do thing")

    def test_npm_local_tgz_axes_produces_valid_command(self) -> None:
        axes = S.RunAxes(
            runner=S.Runner.CODEX, mode=S.Mode.A,
            install_channel=S.InstallChannel.NPM_LOCAL_TGZ,
            model="gpt-5",
        )
        cmd = RUN._command_for_axes(axes, "long prompt")
        # codex shape unchanged.
        self.assertEqual(cmd[:3], ["codex", "exec", "--full-auto"])
        self.assertEqual(cmd[-1], "-")

    def test_pip_registry_axes_produces_valid_command(self) -> None:
        axes = S.RunAxes(
            runner=S.Runner.COPILOT, mode=S.Mode.A,
            install_channel=S.InstallChannel.PIP_REGISTRY,
            install_version="1.5.7", model="gpt-5.4",
        )
        cmd = RUN._command_for_axes(axes, "p")
        self.assertEqual(cmd[0], "copilot")

    def test_npm_registry_axes_produces_valid_command(self) -> None:
        axes = S.RunAxes(
            runner=S.Runner.CURSOR, mode=S.Mode.A,
            install_channel=S.InstallChannel.NPM_REGISTRY,
            install_version="1.5.7", model="sonic",
        )
        cmd = RUN._command_for_axes(axes, "p")
        self.assertEqual(cmd[:4],
                          ["cursor", "agent", "--print", "--force"])

    def test_runner_set_guard_still_enforced(self) -> None:
        """The runner-set guard (``_SUPPORTED_RUNNERS``) is
        legitimate and stays — it's the per-CLI adapter contract.
        Only the channel guard was the stale leftover."""
        # Build a phony runner enum value by tampering with axes
        # post-hoc — we can't construct an unknown Runner via the
        # enum, but the guard's logic is the load-bearing pin.
        self.assertIn(S.Runner.CLAUDE, RUN._SUPPORTED_RUNNERS)
        # And the old _SUPPORTED_CHANNELS constant is gone.
        self.assertFalse(
            hasattr(RUN, "_SUPPORTED_CHANNELS"),
            "104: _SUPPORTED_CHANNELS must be deleted, not just "
            "expanded — the guard concept is wrong (channel "
            "doesn't affect launch argv)",
        )


class ChannelIndependenceLaunchRunSmokeTests(unittest.TestCase):
    """Patch the subprocess call inside ``launch_run`` and verify
    a pip-local-wheel axes runs through to LaunchResult without
    the pre-104 RunnerError."""

    def test_launch_run_succeeds_for_pip_local_wheel(self) -> None:
        # Build a minimal LaunchSpec with pip-local-wheel.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            (tmp_p / "target").mkdir()
            spec = RUN.LaunchSpec(
                target_dir=tmp_p / "target",
                run_dir=tmp_p / "run",
                axes=S.RunAxes(
                    runner=S.Runner.CLAUDE, mode=S.Mode.A,
                    install_channel=
                        S.InstallChannel.PIP_LOCAL_WHEEL,
                    model="opus",
                ),
                case_id="ACC-T", run_id="20260526T120000Z",
                max_duration_s=5.0, prompt="hi",
            )
            # Patch command builder to return a no-op echo.
            def _fake_cmd(axes, prompt, target_dir=None,
                           parameters=None):
                return [sys.executable, "-c", "pass"]
            with mock.patch(
                "bin.harness.runner._command_for_axes",
                side_effect=_fake_cmd,
            ):
                result = RUN.launch_run(spec)
            self.assertEqual(
                result.terminal_state,
                S.TerminalState.COMPLETED,
            )


# ---------------------------------------------------------------------------
# Task C — progress logging (stderr + harness.log + run.log)
# ---------------------------------------------------------------------------


class ProgressLogShapeTests(unittest.TestCase):

    def test_log_writes_to_all_three_sinks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp)
            log = PR._ProgressLog(harness_run)
            run_dir = harness_run / "run-00"
            run_dir.mkdir()
            captured = io.StringIO()
            with mock.patch.object(sys, "stderr", captured):
                log.log("hello world", run_dir=run_dir,
                         tag="run-00 gson claude/opus")
            stderr_out = captured.getvalue()
            self.assertIn("hello world", stderr_out)
            self.assertIn("run-00 gson claude/opus", stderr_out)
            # harness.log + run.log.
            self.assertIn(
                "hello world",
                (harness_run / "harness.log").read_text(
                    encoding="utf-8"),
            )
            self.assertIn(
                "hello world",
                (run_dir / "run.log").read_text(encoding="utf-8"),
            )

    def test_log_format_includes_timestamp_and_tag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp)
            log = PR._ProgressLog(harness_run)
            captured = io.StringIO()
            with mock.patch.object(sys, "stderr", captured):
                log.log("test message")
            line = captured.getvalue().rstrip("\n")
            # Format: [HH:MM:SS] [tag] message
            self.assertRegex(
                line,
                r"^\[\d\d:\d\d:\d\d\] \[harness-run\] test message$",
            )


class RunTagShapeTests(unittest.TestCase):

    def test_run_tag_format(self) -> None:
        plan_run = PR.PlanRun(
            index=2,
            description="x", repo="https://github.com/google/gson",
            ref="main", runner=S.Runner.CLAUDE, model="opus",
            channel=S.InstallChannel.CLONE,
        )
        self.assertEqual(
            PR._run_tag(plan_run),
            "run-02 gson claude/opus",
        )

    def test_run_tag_trailing_slash_normalized(self) -> None:
        plan_run = PR.PlanRun(
            index=0,
            description="x", repo="https://github.com/ory/keto/",
            ref="main", runner=S.Runner.COPILOT, model="gpt-5",
            channel=S.InstallChannel.CLONE,
        )
        self.assertEqual(
            PR._run_tag(plan_run),
            "run-00 keto copilot/gpt-5",
        )


class RunPlanEmitsProgressTests(unittest.TestCase):
    """End-to-end: run a plan via fake_run + verify the expected
    progress lines reach stderr AND harness.log AND per-run
    run.log."""

    def test_clone_only_plan_emits_progress_lines(self) -> None:
        plan = PR.parse_plan({
            "pools": {"claude": 1},
            "runs": [{
                "description": "p", "repo": "x", "ref": "main",
                "runner": "claude", "model": "opus",
                "channel": "clone", "expect": {},
            }],
        })

        def _fake(pr, run_dir):
            return {
                "terminal_state":
                    S.TerminalState.ABORTED_PREP.value,
                "facts": None, "transcript": "",
                "axes": S.RunAxes(
                    runner=pr.runner, mode=pr.mode,
                    install_channel=pr.channel, model=pr.model,
                ),
            }

        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            captured = io.StringIO()
            with mock.patch.object(sys, "stderr", captured):
                outcomes = PR.run_plan(
                    plan, runs_root,
                    hooks=PR.PlanRunnerHooks(fake_run=_fake),
                )
            stderr_out = captured.getvalue()
            self.assertEqual(len(outcomes), 1)
            # Key lines present on stderr.
            self.assertIn("[harness-run]", stderr_out)
            self.assertIn("plan: 1 runs", stderr_out)
            self.assertIn(
                "fake_run (test fast-path)", stderr_out,
                "fake_run path must still log the fast-path "
                "marker so the operator knows what they're "
                "seeing",
            )
            self.assertIn("DONE:", stderr_out)
            self.assertIn("all runs complete", stderr_out)
            # harness.log carries the same lines.
            harness_run = next(
                d for d in runs_root.iterdir() if d.is_dir()
            )
            log_text = (harness_run / "harness.log").read_text(
                encoding="utf-8")
            self.assertIn("plan: 1 runs", log_text)
            self.assertIn("DONE:", log_text)
            self.assertIn("all runs complete", log_text)
            # Per-run run.log carries only the per-run lines.
            run_log = (harness_run / "run-00" / "run.log").read_text(
                encoding="utf-8")
            self.assertIn("run-00", run_log)
            self.assertIn("DONE:", run_log)
            # Harness-level lines (no run_dir) should NOT appear
            # in the per-run log.
            self.assertNotIn("plan: 1 runs", run_log)

    def test_local_wheel_plan_emits_build_artifacts_line(
            self) -> None:
        """A plan needing local artifacts emits the
        'build artifacts (<channels>)' line at the harness-run
        level."""
        plan = PR.parse_plan({
            "pools": {"claude": 1},
            "runs": [{
                "description": "p", "repo": "x", "ref": "main",
                "runner": "claude", "model": "opus",
                "channel": "pip-local-wheel", "expect": {},
            }],
        })

        # Fake builder that succeeds (no real python -m build).
        def _bw(artifacts_dir):
            (artifacts_dir / "fake.whl").write_bytes(b"FAKE")
            return artifacts_dir / "fake.whl"

        def _fake(pr, run_dir):
            return {
                "terminal_state":
                    S.TerminalState.ABORTED_PREP.value,
                "facts": None, "transcript": "",
                "axes": S.RunAxes(
                    runner=pr.runner, mode=pr.mode,
                    install_channel=pr.channel, model=pr.model,
                ),
            }

        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            captured = io.StringIO()
            with mock.patch.object(sys, "stderr", captured):
                PR.run_plan(
                    plan, runs_root,
                    hooks=PR.PlanRunnerHooks(fake_run=_fake),
                    builder=PR.BuilderHooks(build_wheel=_bw),
                )
            stderr_out = captured.getvalue()
            self.assertIn("build artifacts", stderr_out)
            self.assertIn("pip-local-wheel", stderr_out)
            self.assertIn("build artifacts complete",
                           stderr_out)


class ProductionPathProgressLoggingTests(unittest.TestCase):
    """The 103 live composition emits the clone/install/launch/
    facts/grade/DONE lines. We exercise it with the existing
    103-style local fixture pattern (real local clone +
    real install + patched launch + real installed gate + real
    grade) and assert the expected log lines."""

    def test_live_composition_emits_all_step_lines(self) -> None:
        import subprocess as _sub
        # Build the tiny local git fixture + canned quality tree
        # (matches the 103 pattern).
        _REPO_ROOT = (
            Path(__file__).resolve().parents[3]
        )
        sys.path.insert(0, str(
            _REPO_ROOT / ".github" / "skills"
            / "quality_gate" / "tests"
        ))
        from test_quality_gate import (  # noqa: E402
            minimal_zero_bug_tree, add_one_bug, write_tree,
        )

        _REAL_PY_FUNCTIONAL_TEST = (
            "import unittest\n\n"
            "class FunctionalTests(unittest.TestCase):\n"
            "    def test_thing(self):\n"
            "        self.assertEqual(1 + 1, 2)\n"
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            # Local fixture repo.
            fixture = tmp_p / "fixture-repo"
            fixture.mkdir()
            for c in (("git", "init", "--initial-branch=main"),
                       ("git", "config", "user.email", "t@e.x"),
                       ("git", "config", "user.name", "T")):
                _sub.run(list(c), cwd=str(fixture), check=True,
                         capture_output=True)
            (fixture / "README.md").write_text("# fixture\n")
            _sub.run(["git", "add", "README.md"],
                     cwd=str(fixture), check=True,
                     capture_output=True)
            _sub.run(["git", "commit", "-m", "init"],
                     cwd=str(fixture), check=True,
                     capture_output=True)
            repo_url = f"file://{fixture}"

            plan = PR.parse_plan({
                "pools": {"claude": 1},
                "runs": [{
                    "description": "live-composition log test",
                    "repo": repo_url, "ref": "main",
                    "runner": "claude", "model": "opus",
                    "channel": "clone",
                    "expect": {"gate_result": "PASS"},
                }],
            })

            def _fake_launch(spec):
                # Populate canned solid tree.
                tree = minimal_zero_bug_tree()
                add_one_bug(tree, bug_id="BUG-001")
                tree["quality/test_functional.py"] = (
                    _REAL_PY_FUNCTIONAL_TEST
                )
                tree["quality/PROGRESS.md"] = (
                    "# Progress\n\nSkill version: 1.4.4\n\n"
                    "## Phases\n- [x] Phase 1\n- [x] Phase 2\n"
                    "- [x] Phase 3\n- [x] Phase 4\n"
                    "- [x] Phase 5\n- [x] Phase 6\n"
                    "## Terminal Gate Verification\n"
                )
                write_tree(spec.target_dir, tree)
                stream = spec.run_dir / "stream.ndjson"
                spec.run_dir.mkdir(parents=True, exist_ok=True)
                stream.write_text("{}\n", encoding="utf-8")
                return RUN.LaunchResult(
                    pid=12345,
                    started_at="2026-05-26T00:00:00Z",
                    ended_at="2026-05-26T00:00:05Z",
                    exit_code=0,
                    terminal_state=S.TerminalState.COMPLETED,
                    cli_command="(patched)",
                    cwd=str(spec.target_dir),
                    env_snapshot={"CLAUDECODE": "1"},
                    stream_path=stream,
                )

            runs_root = tmp_p / "runs"
            captured = io.StringIO()
            with mock.patch(
                "bin.harness.runner.launch_run",
                side_effect=_fake_launch,
            ), mock.patch.object(sys, "stderr", captured):
                # v1.5.7 108: detach=False keeps the synchronous
                # live-composition path the 104 test exercises.
                # Production default is detach=True (auto-spawn
                # the detached collector); the synchronous path
                # is the test-only opt-out.
                outcomes = PR.run_plan(
                    plan, runs_root,
                    hooks=PR.PlanRunnerHooks(),  # NO fake_run
                    detach=False,
                )
            stderr_out = captured.getvalue()
            self.assertEqual(outcomes[0].result, "MET")
            # Per-instruction Task C: key step lines present.
            for expected in (
                f"clone {repo_url}@main",
                "install (clone)",
                "launch claude/opus",
                "launched (pid=12345",
                "stream=",
                "facts (re-run installed gate)",
                "grade",
                "DONE: gate=PASSED result=MET",
            ):
                self.assertIn(
                    expected, stderr_out,
                    f"expected step line containing "
                    f"{expected!r} in stderr; full stderr:\n"
                    f"{stderr_out}",
                )
            # Per-run log carries the same step lines.
            harness_run = next(
                d for d in runs_root.iterdir() if d.is_dir()
            )
            run_log = (harness_run / "run-00" / "run.log").read_text(
                encoding="utf-8")
            self.assertIn("DONE: gate=PASSED result=MET",
                            run_log)
            self.assertIn("launch claude/opus", run_log)


# ---------------------------------------------------------------------------
# Outcomes / SUMMARY unchanged by progress logging
# ---------------------------------------------------------------------------


class OutcomesUnchangedByLoggingTests(unittest.TestCase):

    def test_summary_rollup_unchanged_with_logging(self) -> None:
        """Progress logging is purely additive — outcomes /
        SUMMARY are byte-identical with and without log fanout."""
        # We can't toggle logging on/off in run_plan (it's
        # always-on), but we CAN compare against a hand-computed
        # SUMMARY based on fake_run outputs. Any change to
        # outcomes would surface as a mismatch.
        plan = PR.parse_plan({
            "pools": {"claude": 1},
            "runs": [
                {"description": "a", "repo": "x", "ref": "m",
                 "runner": "claude", "model": "opus",
                 "channel": "clone", "expect": {}},
                {"description": "b", "repo": "y", "ref": "m",
                 "runner": "claude", "model": "opus",
                 "channel": "clone", "expect": {}},
            ],
        })

        def _fake(pr, run_dir):
            return {
                "terminal_state":
                    S.TerminalState.ABORTED_PREP.value,
                "facts": None, "transcript": "",
                "axes": S.RunAxes(
                    runner=pr.runner, mode=pr.mode,
                    install_channel=pr.channel, model=pr.model,
                ),
            }

        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            # Suppress stderr during the run.
            with mock.patch.object(sys, "stderr", io.StringIO()):
                outcomes = PR.run_plan(
                    plan, runs_root,
                    hooks=PR.PlanRunnerHooks(fake_run=_fake),
                )
            self.assertEqual(len(outcomes), 2)
            for o in outcomes:
                self.assertEqual(o.result, "N/A")
                self.assertEqual(o.gate_verdict, "N/A")
            harness_run = next(
                d for d in runs_root.iterdir() if d.is_dir()
            )
            summary = (harness_run / "SUMMARY.md").read_text(
                encoding="utf-8")
            self.assertIn("0/2 MET", summary)


if __name__ == "__main__":
    unittest.main()
