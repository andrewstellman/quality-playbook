"""v1.5.7 091 — runner timeout kill test.

Covers ``bin/harness/runner.py::launch_run`` — specifically the
``max_duration_s`` kill path: a subprocess that exceeds the
timeout must be terminated (process group SIGTERM→SIGKILL) and
the run's ``terminal_state`` set to ``TIMED_OUT``.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from bin.harness import runner as R
from bin.harness import schema as S


def _mk_axes(runner: S.Runner = S.Runner.CLAUDE) -> S.RunAxes:
    return S.RunAxes(
        runner=runner, mode=S.Mode.A,
        install_channel=S.InstallChannel.CLONE,
        model="test-model",
    )


class CommandConstructionTests(unittest.TestCase):

    def test_claude_command_carries_expected_flags(self) -> None:
        cmd = R._claude_command("opus", "do thing")
        # Flags pinned: --print, --dangerously-skip-permissions,
        # --model, --output-format stream-json --verbose, and the
        # prompt last.
        self.assertEqual(cmd[0], "claude")
        self.assertIn("--print", cmd)
        self.assertIn("--dangerously-skip-permissions", cmd)
        self.assertIn("--model", cmd)
        self.assertEqual(cmd[cmd.index("--model") + 1], "opus")
        self.assertIn("--output-format", cmd)
        self.assertEqual(cmd[cmd.index("--output-format") + 1],
                         "stream-json")
        self.assertIn("--verbose", cmd)
        self.assertEqual(cmd[-1], "do thing")

    def test_codex_adapter_now_supported_post_095(self) -> None:
        """v1.5.7 095 Phase 5 lifted the Phase 1 claude-only
        restriction; codex / copilot / cursor adapters are now
        supported. The Phase-1 rejection-message tests were
        replaced by the broader-adapter coverage in
        test_runner_adapters_095.py."""
        cmd = R._command_for_axes(_mk_axes(S.Runner.CODEX),
                                    "prompt")
        # codex command starts with 'codex exec --full-auto'
        self.assertEqual(cmd[:3], ["codex", "exec", "--full-auto"])

    def test_local_channel_no_longer_rejected_post_104(
            self) -> None:
        """v1.5.7 104 retired the clone-only channel guard: the
        launch command is channel-independent (prepare already
        installed the skill), so local-wheel / local-tgz /
        registry channels must produce a valid command without
        RunnerError. The pre-104 assertion (`raises RunnerError
        with "Phase 2"`) is the mutation-bite for 104 — re-adding
        the guard would make this test FAIL with a RunnerError
        raise instead of returning a valid command list."""
        for channel in (S.InstallChannel.PIP_LOCAL_WHEEL,
                         S.InstallChannel.NPM_LOCAL_TGZ,
                         S.InstallChannel.PIP_REGISTRY,
                         S.InstallChannel.NPM_REGISTRY):
            axes = S.RunAxes(
                runner=S.Runner.CLAUDE, mode=S.Mode.A,
                install_channel=channel, model="opus",
            )
            cmd = R._command_for_axes(axes, "prompt")
            self.assertEqual(
                cmd[0], "claude",
                f"channel {channel.value} must produce a valid "
                f"claude command, not raise",
            )


@unittest.skipUnless(
    sys.platform != "win32",
    "Process-group signal semantics differ on Windows",
)
class TimeoutKillTests(unittest.TestCase):
    """Patch ``_command_for_axes`` to return a sleep command so we
    can deterministically exercise the timeout path WITHOUT
    needing a real ``claude`` binary on the test runner."""

    def setUp(self) -> None:
        self._orig_command_for_axes = R._command_for_axes
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmp.name)

    def tearDown(self) -> None:
        R._command_for_axes = self._orig_command_for_axes
        self._tmp.cleanup()

    def test_subprocess_killed_on_timeout(self) -> None:
        """A long-running subprocess hits the max-duration timeout
        → process is killed → ``terminal_state=TIMED_OUT``.

        Mutation bite: drop the ``proc.wait(timeout=...)`` /
        ``_kill_process_tree`` branch → the test would hang
        indefinitely.
        """
        # Inject: a sleep 60s command, with a tight max-duration so
        # the kill path is exercised in under 5 seconds.
        def _fake_cmd(axes: S.RunAxes, prompt: str, target_dir=None, parameters=None, **kwargs) -> "list[str]":
            return ["sleep", "60"]

        R._command_for_axes = _fake_cmd  # type: ignore[assignment]
        spec = R.LaunchSpec(
            target_dir=self.tmpdir,
            run_dir=self.tmpdir / "run",
            axes=_mk_axes(),
            case_id="ACC-T",
            run_id="20260525T140000Z",
            max_duration_s=2.0,
            prompt="ignored",
        )
        result = R.launch_run(spec)
        self.assertEqual(result.terminal_state,
                         S.TerminalState.TIMED_OUT)
        # status.json must reflect the terminal state for the
        # external observer (Phase 4 TUI / manager).
        import json
        status = json.loads(
            (self.tmpdir / "run" / "status.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(status["terminal_state"], "TIMED_OUT")

    def test_clean_exit_completes_normally(self) -> None:
        """A subprocess that exits cleanly within the budget →
        ``terminal_state=COMPLETED`` (Phase 1 routes by exit code;
        Phase 2's grader will re-classify by gate-verdict presence).
        """
        def _fake_cmd(axes: S.RunAxes, prompt: str, target_dir=None, parameters=None, **kwargs) -> "list[str]":
            return ["true"]

        R._command_for_axes = _fake_cmd  # type: ignore[assignment]
        spec = R.LaunchSpec(
            target_dir=self.tmpdir,
            run_dir=self.tmpdir / "run",
            axes=_mk_axes(),
            case_id="ACC-T",
            run_id="20260525T140001Z",
            max_duration_s=30.0,
            prompt="ignored",
        )
        result = R.launch_run(spec)
        self.assertEqual(result.terminal_state,
                         S.TerminalState.COMPLETED)
        self.assertEqual(result.exit_code, 0)

    def test_nonzero_exit_routes_to_failed(self) -> None:
        """A subprocess that exits non-zero → ``FAILED``."""
        def _fake_cmd(axes: S.RunAxes, prompt: str, target_dir=None, parameters=None, **kwargs) -> "list[str]":
            return ["false"]

        R._command_for_axes = _fake_cmd  # type: ignore[assignment]
        spec = R.LaunchSpec(
            target_dir=self.tmpdir,
            run_dir=self.tmpdir / "run",
            axes=_mk_axes(),
            case_id="ACC-T",
            run_id="20260525T140002Z",
            max_duration_s=10.0,
            prompt="ignored",
        )
        result = R.launch_run(spec)
        self.assertEqual(result.terminal_state, S.TerminalState.FAILED)
        self.assertNotEqual(result.exit_code, 0)

    def test_stream_file_captured(self) -> None:
        """A subprocess's stdout is captured to
        ``run_dir/stream.ndjson`` (raw — never committed; the
        ``runs/`` gitignore handles that)."""
        def _fake_cmd(axes: S.RunAxes, prompt: str, target_dir=None, parameters=None, **kwargs) -> "list[str]":
            return [sys.executable, "-c",
                     "import sys; sys.stdout.write('hello\\nworld\\n'); sys.stdout.flush()"]

        R._command_for_axes = _fake_cmd  # type: ignore[assignment]
        spec = R.LaunchSpec(
            target_dir=self.tmpdir,
            run_dir=self.tmpdir / "run",
            axes=_mk_axes(),
            case_id="ACC-T",
            run_id="20260525T140003Z",
            max_duration_s=10.0,
            prompt="ignored",
        )
        result = R.launch_run(spec)
        self.assertTrue(result.stream_path.is_file())
        content = result.stream_path.read_text(encoding="utf-8")
        self.assertIn("hello", content)
        self.assertIn("world", content)


if __name__ == "__main__":
    unittest.main()
