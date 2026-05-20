"""Tests for bin/skill_derivation/runners.py — runner transport invariants.

Regression coverage for BUG-001 (CopilotRunner used argv instead of stdin)
and the broader anti-pattern previously seen in CursorRunner (--print
--force - sent '-' as a literal prompt). Both defects share the same
shape: a runner that builds a subprocess invocation without piping the
prompt through stdin. For prompts approaching ARG_MAX (~256KB on macOS,
~131KB on Linux) the argv path silently truncates or fails with
'Argument list too long', so all runners must transport the prompt via
stdin (subprocess.run(..., input=prompt)).
"""

from __future__ import annotations

import inspect
import unittest

from bin.skill_derivation import runners


class TestRunnerStdinTransport(unittest.TestCase):
    """All runners must transport the prompt via stdin, not argv."""

    def test_copilot_runner_uses_stdin_not_argv(self):
        """CopilotRunner.run() passes prompt via input=prompt (BUG-001)."""
        source = inspect.getsource(runners.CopilotRunner.run)
        self.assertIn(
            "input=prompt",
            source,
            "CopilotRunner.run() must pass prompt via stdin (input=prompt), "
            "not as a positional command-line argument, to avoid ARG_MAX "
            "truncation for large prompts.",
        )
        # Defensive: argv list must not contain a bare `prompt` element
        # passed via the literal `"--prompt", prompt,` pattern. The
        # BUG-001 fix removed that pattern from the legacy
        # ["gh", "copilot", "--prompt", "--model", ...] list. After
        # v1.5.7 089f's gh-copilot → copilot migration, CopilotRunner
        # routes through bin/copilot_resolver and the prompt arrives
        # on argv via the resolver's `["copilot", "-p", prompt, ...]`
        # form — the literal `"--prompt", prompt,` pattern this assert
        # forbids still cannot appear in source (the resolver returns
        # a list; CopilotRunner.run() doesn't write that exact literal).
        self.assertNotIn(
            '"--prompt", prompt,',
            source,
            "CopilotRunner.run() must not pass prompt as a positional argv "
            "element with the literal `\"--prompt\", prompt,` shape; "
            "it should route through bin/copilot_resolver instead.",
        )

    def test_all_runners_use_stdin_transport(self):
        """Every runner class transports the prompt via stdin.

        Generalizes BUG-001's check across all four runners. The Cursor
        runner had the same shape in v1.5.4 ('--print --force -' sent
        '-' as a literal prompt). A loop here prevents the third
        recurrence in whatever runner someone adds next.
        """
        runner_classes = [
            runners.ClaudeRunner,
            runners.CodexRunner,
            runners.CopilotRunner,
            runners.CursorRunner,
        ]
        for runner_class in runner_classes:
            with self.subTest(runner=runner_class.__name__):
                source = inspect.getsource(runner_class.run)
                self.assertIn(
                    "input=prompt",
                    source,
                    f"{runner_class.__name__}.run() must use stdin "
                    f"transport (input=prompt). All runners must have "
                    f"behaviorally equivalent long-prompt handling.",
                )


if __name__ == "__main__":
    unittest.main()
