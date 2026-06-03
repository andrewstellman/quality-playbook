"""v1.5.7 instruction 129 — `run_playbook --runner-extra-args`
passthrough.

In Mode B the harness splices a run's ``parameters`` into
``run_playbook.py``'s argv (per ``_mode_b_command``'s 106
contract). Run_playbook then builds the runner command
(``codex exec --sandbox workspace-write -m M -``) and Popens it.
Pre-129 there was no way for a Mode B plan to forward a flag to
the runner CLI itself — e.g. codex's ``-c
model_reasoning_effort=low``. A plan that put those tokens in
``parameters`` would feed them to run_playbook's argparse (which
has no ``-c``), failing before codex launched.

129 adds ``--runner-extra-args``: a single shell-quoted string,
shlex-split into argv tokens, spliced into each runner's command
BEFORE the stdin/positional sentinel (codex/claude/cursor) or
before the tool-approval flag (copilot). Run_playbook does NOT
interpret the tokens — they pass through verbatim.

Coverage (argparse + builder, NO subprocess spawn):
  * no flag ⇒ pre-129 command shape (baseline pin)
  * codex: spliced between ``-m M`` and the ``-`` sentinel
    (**load-bearing mutation-bite**)
  * claude / copilot / cursor: analogous splice positions
  * shlex semantics: quoted strings preserved; malformed quoting
    raises ValueError (propagates, not swallowed)
  * empty value ⇒ no-op
  * argparse help documents the v1.5.7 129 source pointer

``_resolve_runner_command`` is patched to identity so command
shapes are asserted independent of host PATH (it would otherwise
``shutil.which``-resolve argv[0]); the copilot subtest patches
``_detect_copilot_cli`` so it's PATH-independent (the 089g
pattern).
"""
from __future__ import annotations

import contextlib
import unittest
from unittest import mock

from bin import run_playbook


# Identity shim so command shapes are PATH-independent.
_IDENTITY = mock.patch(
    "bin.run_playbook._resolve_runner_command",
    side_effect=lambda a: list(a))


class CodexExtraArgsTests(unittest.TestCase):

    def test_no_flag_passes_no_extra_args(self) -> None:
        # Baseline pin: pre-129 codex shape, exactly.
        with _IDENTITY:
            cmd = run_playbook.command_for_runner(
                "codex", "the-prompt", "gpt-5.2")
        self.assertEqual(
            cmd,
            ["codex", "exec", "--sandbox", "workspace-write",
             "-m", "gpt-5.2", "-"])

    def test_codex_extra_args_spliced_before_stdin_sentinel(
            self) -> None:
        # **LOAD-BEARING mutation-bite.** Extra args land between
        # ``-m MODEL`` and the trailing ``-`` stdin sentinel. If the
        # splice goes after ``-`` (or the flag is ignored), this fails.
        #
        # Note shlex's QUOTE-REMOVAL (standard shell semantics): a
        # double-quoted ``"low"`` in the input string yields the bare
        # token ``model_reasoning_effort=low`` — the quotes were shell
        # quoting, stripped exactly as a real shell would before codex
        # sees the arg. (To pass codex a value WITH literal quotes —
        # e.g. a TOML string — single-quote-wrap it: see
        # ``test_preserve_literal_quotes_via_single_quote_wrap``.)
        with _IDENTITY:
            cmd = run_playbook.command_for_runner(
                "codex", "the-prompt", "gpt-5.2",
                runner_extra_args='-c model_reasoning_effort="low"')
        self.assertEqual(
            cmd,
            ["codex", "exec", "--sandbox", "workspace-write",
             "-m", "gpt-5.2",
             "-c", "model_reasoning_effort=low", "-"])
        # The sentinel MUST remain last.
        self.assertEqual(cmd[-1], "-")

    def test_preserve_literal_quotes_via_single_quote_wrap(
            self) -> None:
        # To forward a TOML string value (literal quotes intact) to
        # codex, the plan single-quote-wraps the key=value so shlex
        # preserves the inner double-quotes — same idiom as a shell.
        with _IDENTITY:
            cmd = run_playbook.command_for_runner(
                "codex", "the-prompt", "gpt-5.2",
                runner_extra_args=(
                    "-c 'model_reasoning_effort=\"low\"'"))
        self.assertIn('model_reasoning_effort="low"', cmd)

    def test_codex_extra_args_with_no_model(self) -> None:
        # Splice position is sentinel-relative, not model-relative:
        # still before ``-`` when model is None.
        with _IDENTITY:
            cmd = run_playbook.command_for_runner(
                "codex", "the-prompt", None,
                runner_extra_args="-c x=1")
        self.assertEqual(
            cmd,
            ["codex", "exec", "--sandbox", "workspace-write",
             "-c", "x=1", "-"])


class ClaudeExtraArgsTests(unittest.TestCase):

    def test_claude_extra_args_spliced_correctly(self) -> None:
        # Between ``--model M`` and the ``-p PROMPT`` block.
        with _IDENTITY:
            cmd = run_playbook.command_for_runner(
                "claude", "the-prompt", "opus",
                runner_extra_args="--verbose")
        self.assertEqual(
            cmd,
            ["claude", "--model", "opus", "--verbose",
             "-p", "the-prompt", "--dangerously-skip-permissions"])

    def test_claude_no_flag_baseline(self) -> None:
        with _IDENTITY:
            cmd = run_playbook.command_for_runner(
                "claude", "the-prompt", "opus")
        self.assertEqual(
            cmd,
            ["claude", "--model", "opus",
             "-p", "the-prompt", "--dangerously-skip-permissions"])


class CursorExtraArgsTests(unittest.TestCase):

    def test_cursor_extra_args_spliced_correctly(self) -> None:
        # Cursor has no stdin sentinel (prompt via stdin); extra args
        # append after ``--model M``.
        with _IDENTITY:
            cmd = run_playbook.command_for_runner(
                "cursor", "the-prompt", "sonnet",
                runner_extra_args="--foo bar")
        self.assertEqual(
            cmd,
            ["cursor", "agent", "--print", "--force",
             "--model", "sonnet", "--foo", "bar"])


class CopilotExtraArgsTests(unittest.TestCase):

    def test_copilot_extra_args_spliced_correctly(self) -> None:
        # Splice after ``--model M`` and before the trailing
        # ``--allow-all`` flag. Patch detection so it's PATH-independent.
        with contextlib.ExitStack() as stack:
            stack.enter_context(_IDENTITY)
            stack.enter_context(mock.patch(
                "bin.copilot_resolver._detect_copilot_cli",
                return_value="copilot"))
            cmd = run_playbook.command_for_runner(
                "copilot", "the-prompt", "gpt-5.5",
                runner_extra_args="--foo bar")
        self.assertEqual(
            cmd,
            ["copilot", "-p", "the-prompt", "--model", "gpt-5.5",
             "--foo", "bar", "--allow-all"])
        # Tool-approval flag stays last.
        self.assertEqual(cmd[-1], "--allow-all")


class ShlexSemanticsTests(unittest.TestCase):

    def test_shlex_parsing_handles_quoted_strings(self) -> None:
        # A quoted token preserves its internal space; two tokens out.
        with _IDENTITY:
            cmd = run_playbook.command_for_runner(
                "codex", "p", "m",
                runner_extra_args='"first arg" second')
        self.assertIn("first arg", cmd)
        self.assertIn("second", cmd)
        # The spaced token is ONE argv element, not two.
        self.assertEqual(cmd.count("first arg"), 1)

    def test_shlex_malformed_quoting_propagates_ValueError(
            self) -> None:
        # Malformed quoting must fail loudly, not silently drop.
        with _IDENTITY:
            with self.assertRaises(ValueError):
                run_playbook.command_for_runner(
                    "codex", "p", "m",
                    runner_extra_args='unclosed "')

    def test_empty_value_is_noop(self) -> None:
        with _IDENTITY:
            cmd = run_playbook.command_for_runner(
                "codex", "p", "m", runner_extra_args="")
        self.assertEqual(
            cmd,
            ["codex", "exec", "--sandbox", "workspace-write",
             "-m", "m", "-"])


class ArgparseTests(unittest.TestCase):

    def test_argparse_accepts_flag_single_string(self) -> None:
        parser = run_playbook.build_parser()
        ns = parser.parse_args([
            "--codex", "--runner-extra-args",
            '-c model_reasoning_effort="low"', "target"])
        self.assertEqual(
            ns.runner_extra_args,
            '-c model_reasoning_effort="low"')

    def test_argparse_default_is_none(self) -> None:
        parser = run_playbook.build_parser()
        ns = parser.parse_args(["--codex", "target"])
        self.assertIsNone(ns.runner_extra_args)

    def test_argparse_help_text_documents_v157_129(self) -> None:
        parser = run_playbook.build_parser()
        self.assertIn("129", parser.format_help())
        self.assertIn("--runner-extra-args", parser.format_help())


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
