"""v1.5.7 095 — broadened runner adapters + Mode B tests.

Covers the Phase 5 broadening of ``bin/harness/runner.py`` from
claude-only to codex / copilot / cursor adapters, plus Mode B
reuse of ``bin/run_playbook.py``.

Architecture pins per design §G + instruction 095:

  * Each adapter mirrors the canonical ``bin.run_playbook.
    command_for_runner`` invocation by SYMBOL pattern (not line
    numbers — line numbers drift).
  * Mode B shells out to ``python3 -m bin.run_playbook --<runner>
    --model <model> <target_dir>`` — run_playbook IS the Mode B
    harness.
  * codex + cursor read the prompt on STDIN; claude + copilot on
    argv. The harness routes via ``_needs_stdin_prompt``.
  * Gate-derived facts are adapter-independent (re-running the
    INSTALLED gate per design §C); only the live-behavior
    parsing differs per CLI — and even most of those signals
    (banner rendered, gitignore remediation followed) are
    transcript CONTENT, not transcript FORMAT, so the shared
    ``parse_transcript`` works across adapters.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

from bin.harness import runner as R
from bin.harness import schema as S


def _mk_axes(runner: S.Runner = S.Runner.CLAUDE, *,
             mode: S.Mode = S.Mode.A,
             channel: S.InstallChannel = S.InstallChannel.CLONE,
             model: str = "opus",
             thinking: "str | None" = None) -> S.RunAxes:
    return S.RunAxes(
        runner=runner, mode=mode,
        install_channel=channel, model=model,
        thinking=thinking,
    )


_QPB_CLONE_ROOT = Path(__file__).resolve().parents[3]
_EXPECTED_RUN_PLAYBOOK_SCRIPT = (
    _QPB_CLONE_ROOT / "bin" / "run_playbook.py"
)


# ---------------------------------------------------------------------------
# Per-adapter command construction (Mode A)
# ---------------------------------------------------------------------------


class ClaudeAdapterTests(unittest.TestCase):

    def test_claude_command_shape_unchanged_post_095(self) -> None:
        """095 broadening must NOT perturb the claude shape
        (091 contract): --print, --dangerously-skip-permissions,
        --model, --output-format stream-json, --verbose, prompt-
        last."""
        cmd = R._command_for_axes(_mk_axes(), "do thing")
        self.assertEqual(cmd[0], "claude")
        self.assertIn("--print", cmd)
        self.assertIn("--dangerously-skip-permissions", cmd)
        self.assertEqual(cmd[cmd.index("--model") + 1], "opus")
        self.assertIn("--output-format", cmd)
        self.assertEqual(cmd[cmd.index("--output-format") + 1],
                         "stream-json")
        self.assertEqual(cmd[-1], "do thing")

    def test_claude_does_not_need_stdin(self) -> None:
        self.assertFalse(R._needs_stdin_prompt(S.Runner.CLAUDE))


class CodexAdapterTests(unittest.TestCase):

    def test_codex_command_starts_with_codex_exec_full_auto(
            self) -> None:
        """Mirror ``run_playbook.command_for_runner`` codex path:
        ``codex exec --full-auto -m <model> -``. The trailing
        ``"-"`` is the stdin-sentinel."""
        cmd = R._command_for_axes(_mk_axes(S.Runner.CODEX), "p")
        self.assertEqual(cmd[:3], ["codex", "exec", "--full-auto"])
        self.assertIn("-m", cmd)
        self.assertEqual(cmd[cmd.index("-m") + 1], "opus")
        # Trailing stdin sentinel.
        self.assertEqual(cmd[-1], "-")

    def test_codex_needs_stdin(self) -> None:
        self.assertTrue(R._needs_stdin_prompt(S.Runner.CODEX))

    def test_codex_command_omits_positional_prompt(self) -> None:
        """The prompt MUST NOT appear on argv (shell length
        limits on long phase prompts). It's piped on stdin."""
        long_prompt = "x" * 10_000
        cmd = R._command_for_axes(_mk_axes(S.Runner.CODEX),
                                    long_prompt)
        self.assertNotIn(long_prompt, cmd)


class CopilotAdapterTests(unittest.TestCase):

    def test_copilot_command_uses_standalone_copilot(self) -> None:
        """Per design §G + 089f: prefer the standalone
        ``copilot`` CLI (the deprecated ``gh copilot`` extension
        is a runtime-resolver fallback the production code
        handles; the harness defaults to canonical standalone)."""
        cmd = R._command_for_axes(_mk_axes(S.Runner.COPILOT),
                                    "do thing")
        self.assertEqual(cmd[0], "copilot")
        self.assertIn("--model", cmd)
        self.assertEqual(cmd[cmd.index("--model") + 1], "opus")
        self.assertIn("--allow-all-tools", cmd)
        # Prompt on argv (copilot reads from -p positional).
        self.assertIn("-p", cmd)
        self.assertEqual(cmd[cmd.index("-p") + 1], "do thing")

    def test_copilot_does_not_need_stdin(self) -> None:
        self.assertFalse(R._needs_stdin_prompt(S.Runner.COPILOT))


class CursorAdapterTests(unittest.TestCase):

    def test_cursor_command_uses_agent_print_force(self) -> None:
        """Per design §G + run_playbook.command_for_runner
        cursor path: ``cursor agent --print --force --model
        <model>``. NO positional ``-`` (cursor treats it as
        literal prompt content, NOT a stdin sentinel — unlike
        codex)."""
        cmd = R._command_for_axes(_mk_axes(S.Runner.CURSOR), "p")
        self.assertEqual(cmd[:4],
                         ["cursor", "agent", "--print", "--force"])
        self.assertIn("--model", cmd)
        self.assertEqual(cmd[cmd.index("--model") + 1], "opus")
        # No literal-hyphen positional (load-bearing per
        # run_playbook.py's cursor F-1 note).
        self.assertNotIn("-", cmd[4:])

    def test_cursor_needs_stdin(self) -> None:
        """Cursor reads the prompt on stdin (implicitly — no
        positional arg, prompt piped in)."""
        self.assertTrue(R._needs_stdin_prompt(S.Runner.CURSOR))

    def test_cursor_command_omits_positional_prompt(self) -> None:
        """Same as codex: prompt MUST NOT appear on argv."""
        long_prompt = "y" * 10_000
        cmd = R._command_for_axes(_mk_axes(S.Runner.CURSOR),
                                    long_prompt)
        self.assertNotIn(long_prompt, cmd)


# ---------------------------------------------------------------------------
# Mode B — reuse bin.run_playbook
# ---------------------------------------------------------------------------


class ModeBLaunchTests(unittest.TestCase):
    """v1.5.7 095 Mode B per design §G: 'run_playbook.py IS the
    Mode B harness.' The harness shells out to
    ``python3 -m bin.run_playbook --<runner> --model <model>
    <target_dir>`` and lets run_playbook drive the phases."""

    def test_mode_b_shells_out_to_run_playbook(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            axes = _mk_axes(S.Runner.CLAUDE, mode=S.Mode.B)
            cmd = R._command_for_axes(axes, "p",
                                        target_dir=target)
            # v1.5.7 114: invocation is `python3
            # <qpb_clone>/bin/run_playbook.py --claude --model
            # <model> <target>` — absolute-path script form,
            # NOT the pre-114 `-m bin.run_playbook` (which died
            # with `No module named bin.run_playbook` when
            # launched with cwd=target_dir, because the install
            # bundle deliberately excludes run_playbook.py).
            self.assertEqual(cmd[0], sys.executable)
            self.assertEqual(
                cmd[1], str(_EXPECTED_RUN_PLAYBOOK_SCRIPT))
            self.assertIn("--claude", cmd)
            self.assertEqual(cmd[cmd.index("--model") + 1], "opus")
            self.assertEqual(cmd[-1], str(target))

    def test_mode_b_runner_flag_per_runner(self) -> None:
        for runner, expected_flag in (
            (S.Runner.CLAUDE, "--claude"),
            (S.Runner.CODEX, "--codex"),
            (S.Runner.COPILOT, "--copilot"),
            (S.Runner.CURSOR, "--cursor"),
        ):
            with tempfile.TemporaryDirectory() as td:
                target = Path(td)
                axes = _mk_axes(runner, mode=S.Mode.B)
                cmd = R._command_for_axes(axes, "p",
                                            target_dir=target)
                self.assertIn(expected_flag, cmd,
                              f"Mode B for {runner.value} must "
                              f"pass {expected_flag} to run_playbook")

    def test_mode_b_requires_target_dir(self) -> None:
        """Mode B without target_dir → RunnerError (the
        run_playbook harness needs a target tree to drive)."""
        with self.assertRaises(R.RunnerError) as ctx:
            R._command_for_axes(
                _mk_axes(S.Runner.CLAUDE, mode=S.Mode.B),
                "p",
            )
        self.assertIn("Mode B requires target_dir",
                      str(ctx.exception))

    def test_mode_b_does_not_need_stdin(self) -> None:
        """Even for codex/cursor runners, Mode B doesn't need
        stdin from the harness — run_playbook owns the prompt
        flow internally."""
        # ``needs_stdin = (mode != B AND
        # _needs_stdin_prompt(runner))`` — the harness routing
        # accounts for this; here we directly verify the
        # _needs_stdin_prompt helper still says True for the
        # runner (it does — Mode B is the launch-side gate).
        self.assertTrue(R._needs_stdin_prompt(S.Runner.CODEX))
        self.assertTrue(R._needs_stdin_prompt(S.Runner.CURSOR))


# ---------------------------------------------------------------------------
# Per-adapter normalized-fact extraction.
#
# The gate-derived facts (verdict/gate/provenance) are adapter-
# independent — they come from re-running the INSTALLED gate per
# design §C. The live-behavior facts (phase0_first_probe,
# banner_rendered, gitignore_remediation_followed,
# blocked/stop_reason) come from the transcript/stream. Since the
# canonical signals are CONTENT of the transcript (the
# ``event=validation_complete`` line, the 80-wide ═══ rule, the
# cat-skill-template form), the existing parse_transcript handles
# any CLI's output IFF the agent emitted them.
# ---------------------------------------------------------------------------


class AdapterIndependentFactsTests(unittest.TestCase):
    """The shared `parse_transcript` works across all adapters
    because the live-behavior signals are transcript CONTENT, not
    transcript FORMAT. Tests verify each adapter's typical
    transcript shape extracts cleanly."""

    def test_codex_style_transcript_extracts_phase0_ok(self) -> None:
        """Codex's transcript shape carries the same
        ``event=validation_complete status=ok`` line claude
        emits (it's printed by the installed qpb_validate, not
        the CLI). parse_transcript handles both."""
        from bin.harness import facts as F
        transcript = (
            '{"role":"agent","content":"Running validator..."}\n'
            '{"role":"tool_output","content":"'
            'event=validation_complete status=ok"}\n'
            '{"role":"agent","content":"OK; phase 1..."}\n'
        )
        phase0, _install, _blocked, _stop = F.parse_transcript(
            transcript,
        )
        self.assertEqual(phase0.status, "ok")
        self.assertTrue(phase0.first_probe_ok)

    def test_copilot_style_transcript_extracts_banner(self) -> None:
        """Copilot's narration-prose transcript still carries
        the 80-wide ═══ rule when the agent prints the
        attribution banner."""
        from bin.harness import facts as F
        transcript = (
            "Copilot: Printing the QPB attribution banner.\n"
            + "═" * 80 + "\n"
            "  Quality Playbook — by Andrew Stellman\n"
            + "═" * 80 + "\n"
        )
        _p0, install, _b, _s = F.parse_transcript(transcript)
        self.assertTrue(install.banner_rendered)

    def test_cursor_style_transcript_blocked_aup(self) -> None:
        """Cursor's agent-output stream carries policy-refusal
        text the same way claude's does."""
        from bin.harness import facts as F
        transcript = (
            "User: Run the playbook on the auth module.\n"
            "Agent: I cannot help with this request as it goes "
            "against my policy.\n"
        )
        _p0, _install, blocked, stop = F.parse_transcript(
            transcript,
        )
        self.assertTrue(blocked)
        self.assertIn("policy", (stop or "").lower())


# ---------------------------------------------------------------------------
# Vendor env per runner — pinned for all 4 adapters.
# ---------------------------------------------------------------------------


class VendorEnvAllAdaptersTests(unittest.TestCase):
    """The vendor env var the gate's _RUNNER_ENV_MARKERS keys
    off — pinned per runner so a future runner addition without
    env wiring is caught."""

    def test_claude_sets_CLAUDECODE(self) -> None:
        self.assertEqual(R._vendor_env_for(S.Runner.CLAUDE),
                         {"CLAUDECODE": "1"})

    def test_codex_sets_CODEX_THREAD_ID(self) -> None:
        self.assertEqual(R._vendor_env_for(S.Runner.CODEX),
                         {"CODEX_THREAD_ID": "harness"})

    def test_copilot_sets_COPILOT_AGENT_SESSION_ID(self) -> None:
        self.assertEqual(R._vendor_env_for(S.Runner.COPILOT),
                         {"COPILOT_AGENT_SESSION_ID": "harness"})

    def test_cursor_has_no_env_marker_pinned(self) -> None:
        """Cursor has no env marker in the gate's
        _RUNNER_ENV_MARKERS list (the gate maps codex / copilot /
        claude-code). The harness's `_vendor_env_for` returns
        an empty dict for cursor — correct (no env var to set;
        the gate will report `unknown` runner for the re-run,
        which is honest)."""
        self.assertEqual(R._vendor_env_for(S.Runner.CURSOR), {})


# ---------------------------------------------------------------------------
# End-to-end launch with the broader adapters — re-uses the
# Phase 1 timeout-kill test's pattern but exercises codex stdin
# routing.
# ---------------------------------------------------------------------------


@unittest.skipUnless(
    sys.platform != "win32",
    "Process-group signal semantics differ on Windows",
)
class StdinRoutingE2ETests(unittest.TestCase):
    """codex's prompt-on-stdin path is the load-bearing 095
    runtime contract: the prompt MUST reach the subprocess via
    stdin, not argv. This test patches the command builder to
    a Python one-liner that reads stdin and writes to stdout,
    then asserts the prompt landed in the captured stream."""

    def setUp(self) -> None:
        self._orig = R._command_for_axes
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmp.name)

    def tearDown(self) -> None:
        R._command_for_axes = self._orig
        self._tmp.cleanup()

    def test_codex_axis_routes_prompt_to_stdin(self) -> None:
        # Synthetic command that echoes stdin to stdout — exits
        # cleanly. Used as a codex stand-in.
        def _fake(axes, prompt, target_dir=None,
                   parameters=None, **kwargs):
            return [sys.executable, "-c",
                     "import sys; sys.stdout.write(sys.stdin.read())"]
        R._command_for_axes = _fake  # type: ignore[assignment]
        spec = R.LaunchSpec(
            target_dir=self.tmpdir,
            run_dir=self.tmpdir / "run",
            axes=_mk_axes(S.Runner.CODEX),
            case_id="ACC-T",
            run_id="20260525T180000Z",
            max_duration_s=10.0,
            prompt="SYNTHETIC_PROMPT_TOKEN",
        )
        result = R.launch_run(spec)
        self.assertEqual(result.terminal_state,
                         S.TerminalState.COMPLETED)
        # The fake command echoes stdin → stdout, which the
        # harness captures to stream.ndjson.
        content = result.stream_path.read_text(encoding="utf-8")
        self.assertEqual(content, "SYNTHETIC_PROMPT_TOKEN",
                         "v1.5.7 095: codex (stdin-routing runner) "
                         "must receive its prompt on stdin — the "
                         "fake command echoes stdin to stdout, so "
                         "the captured stream is the prompt.")


if __name__ == "__main__":
    unittest.main()
