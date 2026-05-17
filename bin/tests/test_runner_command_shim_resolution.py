"""v1.5.7 instruction 078 (addendum r3 §4 — W2) — bare-name AI CLI
subprocess invocations must be resolved via shutil.which so Windows
`.cmd`/`.bat` shims work (`subprocess.run` without shell=True only
auto-resolves `.exe`).

`_resolve_runner_command()` exists in two modules by deliberate
design (instruction-078 Task 3 sanctions a local copy over a
cross-module import — importing the large bin.run_playbook module
from the lightweight bin.skill_derivation.runners module is awkward
and import-order fragile). These tests pin BOTH copies' behavior and
that the live call sites route through the resolver.

Site-count reconciliation (verify-before-claim): the addendum §4.1
prose and instruction-078 variously say "5"/"9" sites, but a
grep of the live tree shows exactly 4 bare-name command
constructions in bin/run_playbook.py:command_for_runner
(claude/codex/cursor/gh) + 4 in bin/skill_derivation/runners.py
(Claude/Copilot/Codex/Cursor runners) = 8 real sites, all covered.
No un-enumerated site exists (the halt-condition is a *missed*
site, not instruction over-count); the addendum, which wins on
disagreement, enumerates these 4+4.
"""

from __future__ import annotations

import unittest
from unittest import mock

from bin import run_playbook
from bin.skill_derivation import runners


class ResolveRunnerCommandBehaviorTests(unittest.TestCase):

    def test_resolve_runner_command_unix_no_op(self) -> None:
        """which() returns the full path; argv[0] is replaced, the
        rest is preserved.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-078 —
        BITE EXECUTED during instruction-078 development:
          Mutation: in bin/run_playbook.py:_resolve_runner_command,
          change `resolved = shutil.which(argv[0])` to
          `resolved = argv[0]`.
          Observed failure (purged __pycache__ first):
            FAIL: test_resolve_runner_command_unix_no_op
            AssertionError: Lists differ: ['claude', '-p', 'hi'] !=
            ['/usr/local/bin/claude', '-p', 'hi']
          Restoration: shutil.which call restored; PASS again.
        """
        with mock.patch("bin.run_playbook.shutil.which",
                         return_value="/usr/local/bin/claude"):
            self.assertEqual(
                run_playbook._resolve_runner_command(["claude", "-p", "hi"]),
                ["/usr/local/bin/claude", "-p", "hi"])

    def test_resolve_runner_command_windows_cmd_shim(self) -> None:
        win = r"C:\Users\op\AppData\Local\AnthropicClaude\claude.cmd"
        with mock.patch("bin.run_playbook.shutil.which", return_value=win):
            self.assertEqual(
                run_playbook._resolve_runner_command(["claude", "-p", "x"]),
                [win, "-p", "x"])

    def test_resolve_runner_command_not_found_falls_back(self) -> None:
        """Unresolvable name -> bare argv unchanged (preserves the
        existing FileNotFoundError surface to the operator)."""
        with mock.patch("bin.run_playbook.shutil.which", return_value=None):
            self.assertEqual(
                run_playbook._resolve_runner_command(["nonexistent", "-p"]),
                ["nonexistent", "-p"])

    def test_resolve_runner_command_empty_argv(self) -> None:
        self.assertEqual(run_playbook._resolve_runner_command([]), [])

    def test_runners_copy_behaves_identically(self) -> None:
        with mock.patch("bin.skill_derivation.runners.shutil.which",
                         return_value="/opt/bin/codex"):
            self.assertEqual(
                runners._resolve_runner_command(["codex", "exec"]),
                ["/opt/bin/codex", "exec"])
        with mock.patch("bin.skill_derivation.runners.shutil.which",
                         return_value=None):
            self.assertEqual(
                runners._resolve_runner_command(["codex"]), ["codex"])

    def test_two_copies_have_identical_body(self) -> None:
        """The deliberate duplication must not drift: the two
        functions' source bodies are byte-identical."""
        import inspect
        import textwrap

        def body(fn):
            src = textwrap.dedent(inspect.getsource(fn))
            # drop the def line + docstring; compare executable body
            lines = src.splitlines()
            # strip leading def + any docstring block
            start = 1
            joined = "\n".join(lines[start:])
            # remove the (differing) docstring
            import re
            joined = re.sub(r'""".*?"""', "", joined, count=1,
                            flags=re.DOTALL)
            return "\n".join(s.rstrip() for s in joined.splitlines()
                             if s.strip())
        self.assertEqual(
            body(run_playbook._resolve_runner_command),
            body(runners._resolve_runner_command),
            "the two _resolve_runner_command copies have drifted; "
            "keep their bodies byte-identical (078 Task 3)")


class RunPlaybookSitesUseResolverTests(unittest.TestCase):

    def test_command_for_runner_routes_every_runner_through_resolver(self) -> None:
        """All four bin/run_playbook.py:command_for_runner branches
        (claude/codex/cursor/gh) pass through _resolve_runner_command.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-078 —
        BITE EXECUTED during instruction-078 development:
          Mutation: in bin/run_playbook.py:command_for_runner, change
          the claude branch `return _resolve_runner_command(command)`
          back to `return command`.
          Observed failure (purged __pycache__ first):
            FAIL: test_command_for_runner_routes_every_runner_through_resolver
            (runner='claude')
            AssertionError: False is not true : resolver not called
            for runner 'claude'
          Restoration: wrapper restored; PASS again.
        """
        for runner in ("claude", "codex", "cursor", "copilot"):
            with self.subTest(runner=runner):
                with mock.patch(
                    "bin.run_playbook._resolve_runner_command",
                    side_effect=lambda a: ["RESOLVED"] + list(a[1:])
                ) as m:
                    out = run_playbook.command_for_runner(
                        runner, "the-prompt", None)
                self.assertTrue(
                    m.called,
                    f"resolver not called for runner {runner!r}")
                self.assertEqual(
                    out[0], "RESOLVED",
                    f"command_for_runner({runner!r}) did not route "
                    f"through _resolve_runner_command")


if __name__ == "__main__":
    unittest.main()
