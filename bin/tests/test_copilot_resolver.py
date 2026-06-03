"""v1.5.7 089f — regression tests for ``bin/copilot_resolver.py``.

The resolver is the load-bearing seam for the gh-copilot → copilot
CLI migration (GitHub deprecated ``gh copilot`` on 2025-10-25). All
five subprocess call sites route through ``resolve_copilot_command``;
this file pins:

  1. Preference order: ``copilot`` wins over ``gh copilot`` when
     both are on PATH (the new CLI is the canonical form; adopters
     with both installed are mid-migration and should land on the
     new tool).
  2. Each single-CLI case: only ``copilot``, only ``gh copilot``.
  3. Neither-available raises :class:`CopilotCLIUnavailable` with
     the documented remediation message body (both install routes
     referenced).
  4. The ``allow_all=True`` flag maps to ``--allow-all`` for
     ``copilot`` and ``--yolo`` for ``gh copilot`` (the verified
     mapping per ``copilot --help`` on copilot-cli 0.x; the new CLI
     accepts ``--yolo`` as an alias but the resolver emits the
     canonical ``--allow-all`` for the new path).
  5. Model + prompt strings pass through unchanged (no rewriting).

All cases also exercise :func:`require_copilot_cli` to confirm its
return shape stays in sync with detection.

Mutation-bite evidence (ai_context/DEVELOPMENT_PROCESS.md:152-160),
instruction-089f Task 1: each detection test ran PASS→FAIL→PASS via
the bites documented in the corresponding test docstring. The bites
were executed during 089f development; pycache purged between
mutate and restore per the worker's mutation-bite-discipline memory.
"""

from __future__ import annotations

import unittest
from unittest import mock

from bin import copilot_resolver


class CopilotResolverDetectionTests(unittest.TestCase):
    """Detection order: copilot > gh-copilot > none."""

    def setUp(self) -> None:
        # Each test starts with an empty cache; detection runs fresh.
        copilot_resolver.reset_cache()

    def tearDown(self) -> None:
        # Don't leak cached state into other tests in the suite.
        copilot_resolver.reset_cache()

    def test_both_available_prefers_copilot(self) -> None:
        """When both `copilot` and `gh copilot` are on PATH, the
        resolver MUST prefer `copilot` — the new standalone CLI is
        the canonical form; `gh copilot` is deprecated.

        Mutation: flip the detection order in
        ``_detect_copilot_cli`` (probe gh-copilot first).
        Expected failure: this test fails because the returned
        argv starts with ``"gh"`` instead of ``"copilot"``.
        Restoration: re-set canonical preference order; passes.
        Bite executed during 089f Task 1; PASS→FAIL→PASS confirmed.
        """
        with mock.patch.object(
            copilot_resolver.shutil, "which",
            side_effect=lambda name: "/usr/local/bin/copilot" if name == "copilot" else None,
        ):
            # gh-copilot probe shouldn't run when copilot wins, but
            # mock it anyway so an accidental call doesn't shell out.
            with mock.patch.object(
                copilot_resolver, "_probe_gh_copilot", return_value=True,
            ):
                cmd = copilot_resolver.resolve_copilot_command(
                    "hello", "claude-sonnet-4.6",
                )
                available, which = copilot_resolver.require_copilot_cli()

        self.assertEqual(cmd[0], "copilot",
                         "copilot must win over gh-copilot when both available")
        self.assertNotIn("gh", cmd,
                         "the returned argv must not invoke gh at all")
        self.assertTrue(available)
        self.assertEqual(which, "copilot")

    def test_only_copilot_available(self) -> None:
        """Only the new standalone `copilot` CLI is on PATH.
        Returns the `copilot ...` form.
        """
        with mock.patch.object(
            copilot_resolver.shutil, "which",
            side_effect=lambda name: "/usr/local/bin/copilot" if name == "copilot" else None,
        ):
            with mock.patch.object(
                copilot_resolver, "_probe_gh_copilot", return_value=False,
            ):
                cmd = copilot_resolver.resolve_copilot_command(
                    "say hello", "claude-sonnet-4.6",
                )
                available, which = copilot_resolver.require_copilot_cli()

        self.assertEqual(
            cmd,
            ["copilot", "-p", "say hello", "--model", "claude-sonnet-4.6"],
        )
        self.assertTrue(available)
        self.assertEqual(which, "copilot")

    def test_only_gh_copilot_available(self) -> None:
        """Only the legacy `gh copilot` extension is on PATH (no
        standalone `copilot`). Returns the `gh copilot ...` form.

        Mutation: in ``_detect_copilot_cli`` skip the ``elif`` branch
        (return "" when copilot is missing).
        Expected failure: this test fails — the resolver raises
        ``CopilotCLIUnavailable`` instead of returning the gh-copilot
        argv.
        Restoration: re-enable the ``elif _probe_gh_copilot()``
        branch; passes.
        Bite executed during 089f Task 1; PASS→FAIL→PASS confirmed.
        """
        with mock.patch.object(
            copilot_resolver.shutil, "which", return_value=None,
        ):
            with mock.patch.object(
                copilot_resolver, "_probe_gh_copilot", return_value=True,
            ):
                cmd = copilot_resolver.resolve_copilot_command(
                    "say hello", "claude-sonnet-4.6",
                )
                available, which = copilot_resolver.require_copilot_cli()

        self.assertEqual(
            cmd,
            ["gh", "copilot", "-p", "say hello", "--model", "claude-sonnet-4.6"],
        )
        self.assertTrue(available)
        self.assertEqual(which, "gh-copilot")

    def test_neither_available_raises(self) -> None:
        """Neither CLI is available — the resolver raises
        :class:`CopilotCLIUnavailable` with a remediation message
        that references BOTH install routes (the standalone CLI's
        per-platform install commands AND the legacy
        ``gh extension install`` fallback).

        Mutation: replace the ``raise CopilotCLIUnavailable(...)``
        with ``return []``.
        Expected failure: this test fails on
        ``assertRaises(CopilotCLIUnavailable)`` — no exception fires.
        Restoration: restore the raise; passes.
        Bite executed during 089f Task 1; PASS→FAIL→PASS confirmed.
        """
        with mock.patch.object(
            copilot_resolver.shutil, "which", return_value=None,
        ):
            with mock.patch.object(
                copilot_resolver, "_probe_gh_copilot", return_value=False,
            ):
                available, which = copilot_resolver.require_copilot_cli()
                with self.assertRaises(copilot_resolver.CopilotCLIUnavailable) as ctx:
                    copilot_resolver.resolve_copilot_command(
                        "p", "claude-sonnet-4.6",
                    )

        self.assertFalse(available)
        self.assertEqual(which, "")
        msg = str(ctx.exception)
        # Both install routes referenced — adopters with `gh`
        # already installed can keep using the extension during the
        # grace period; new installers see the standalone CLI first.
        self.assertIn("brew install copilot-cli", msg)
        self.assertIn("winget install GitHub.Copilot", msg)
        self.assertIn("gh extension install github/gh-copilot", msg)
        self.assertIn("https://github.com/github/copilot-cli", msg)


class CopilotResolverFlagMappingTests(unittest.TestCase):
    """allow_all=True maps to --allow-all for copilot, --yolo for
    gh copilot. Model + prompt strings pass through unchanged."""

    def setUp(self) -> None:
        copilot_resolver.reset_cache()

    def tearDown(self) -> None:
        copilot_resolver.reset_cache()

    def test_allow_all_emits_allow_all_for_new_cli(self) -> None:
        """The new ``copilot`` CLI's canonical flag is ``--allow-all``
        (per ``copilot --help`` on copilot-cli 0.x). The new CLI also
        accepts ``--yolo`` as an alias, but the resolver emits the
        canonical form so adopters reading subprocess argv in logs
        see the documented spelling.

        Mutation: change ``cmd.append("--allow-all")`` to
        ``cmd.append("--yolo")`` in the copilot branch.
        Expected failure: this test fails on the
        ``assertIn("--allow-all", cmd)`` assertion.
        Restoration: restore ``--allow-all``; passes.
        Bite executed during 089f Task 1; PASS→FAIL→PASS confirmed.
        """
        with mock.patch.object(
            copilot_resolver.shutil, "which",
            side_effect=lambda name: "/usr/local/bin/copilot" if name == "copilot" else None,
        ):
            with mock.patch.object(
                copilot_resolver, "_probe_gh_copilot", return_value=False,
            ):
                cmd = copilot_resolver.resolve_copilot_command(
                    "p", "gpt-5.5", allow_all=True,
                )

        self.assertEqual(cmd[0], "copilot")
        self.assertIn("--allow-all", cmd)
        self.assertNotIn("--yolo", cmd,
                         "resolver must emit the canonical --allow-all "
                         "for the new CLI, not the --yolo alias")

    def test_allow_all_emits_yolo_for_legacy_extension(self) -> None:
        """The legacy ``gh copilot`` extension uses ``--yolo`` (not
        ``--allow-all``). Adopters on the fallback path must see the
        flag spelling their CLI accepts.

        Mutation: change ``cmd.append("--yolo")`` to
        ``cmd.append("--allow-all")`` in the gh-copilot branch.
        Expected failure: this test fails on the
        ``assertIn("--yolo", cmd)`` assertion.
        Restoration: restore ``--yolo``; passes.
        Bite executed during 089f Task 1; PASS→FAIL→PASS confirmed.
        """
        with mock.patch.object(
            copilot_resolver.shutil, "which", return_value=None,
        ):
            with mock.patch.object(
                copilot_resolver, "_probe_gh_copilot", return_value=True,
            ):
                cmd = copilot_resolver.resolve_copilot_command(
                    "p", "gpt-5.5", allow_all=True,
                )

        self.assertEqual(cmd[:2], ["gh", "copilot"])
        self.assertIn("--yolo", cmd)
        self.assertNotIn("--allow-all", cmd,
                         "resolver must emit --yolo (the flag the "
                         "legacy gh-copilot extension accepts), not "
                         "the new CLI's --allow-all")

    def test_allow_all_default_false_omits_flag(self) -> None:
        """Without ``allow_all=True`` neither auto-approve flag
        appears — the resolver doesn't silently opt callers in.
        """
        with mock.patch.object(
            copilot_resolver.shutil, "which",
            side_effect=lambda name: "/usr/local/bin/copilot" if name == "copilot" else None,
        ):
            with mock.patch.object(
                copilot_resolver, "_probe_gh_copilot", return_value=False,
            ):
                cmd_new = copilot_resolver.resolve_copilot_command(
                    "p", "gpt-5.5",
                )

        copilot_resolver.reset_cache()
        with mock.patch.object(
            copilot_resolver.shutil, "which", return_value=None,
        ):
            with mock.patch.object(
                copilot_resolver, "_probe_gh_copilot", return_value=True,
            ):
                cmd_legacy = copilot_resolver.resolve_copilot_command(
                    "p", "gpt-5.5",
                )

        self.assertNotIn("--allow-all", cmd_new)
        self.assertNotIn("--yolo", cmd_new)
        self.assertNotIn("--allow-all", cmd_legacy)
        self.assertNotIn("--yolo", cmd_legacy)

    def test_model_and_prompt_pass_through_unchanged(self) -> None:
        """The resolver must not rewrite, escape, or reorder the
        model or prompt strings — they pass through verbatim. The
        regression risk: a "helpful" string transform that breaks
        whatever the caller actually wanted."""
        with mock.patch.object(
            copilot_resolver.shutil, "which",
            side_effect=lambda name: "/usr/local/bin/copilot" if name == "copilot" else None,
        ):
            with mock.patch.object(
                copilot_resolver, "_probe_gh_copilot", return_value=False,
            ):
                cmd = copilot_resolver.resolve_copilot_command(
                    "multi\nline\nprompt with 'quotes' and spaces",
                    "claude-sonnet-4.6",
                )

        # The prompt is positional after -p; the model is positional
        # after --model. Both should be string-equal to what was
        # passed in.
        prompt_idx = cmd.index("-p")
        self.assertEqual(cmd[prompt_idx + 1],
                         "multi\nline\nprompt with 'quotes' and spaces")
        model_idx = cmd.index("--model")
        self.assertEqual(cmd[model_idx + 1], "claude-sonnet-4.6")


class CopilotResolverCacheTests(unittest.TestCase):
    """Detection is once-per-process; ``reset_cache`` clears it."""

    def setUp(self) -> None:
        copilot_resolver.reset_cache()

    def tearDown(self) -> None:
        copilot_resolver.reset_cache()

    def test_detection_cached_between_calls(self) -> None:
        """A second resolve_copilot_command call must NOT re-probe
        — the cache lets all five subprocess sites share the
        detection cost.
        """
        call_count = {"which": 0}

        def counting_which(name):
            call_count["which"] += 1
            return "/usr/local/bin/copilot" if name == "copilot" else None

        with mock.patch.object(
            copilot_resolver.shutil, "which", side_effect=counting_which,
        ):
            with mock.patch.object(
                copilot_resolver, "_probe_gh_copilot", return_value=False,
            ):
                copilot_resolver.resolve_copilot_command("p1", "m")
                copilot_resolver.resolve_copilot_command("p2", "m")
                copilot_resolver.resolve_copilot_command("p3", "m")

        # Detection probes `copilot` once; subsequent calls hit cache.
        self.assertEqual(
            call_count["which"], 1,
            "shutil.which must be called exactly once for the "
            "lifetime of the process — detection is cached.",
        )

    def test_reset_cache_forces_redetection(self) -> None:
        """After reset_cache, the next call re-probes — needed
        for tests that switch between detection scenarios."""
        with mock.patch.object(
            copilot_resolver.shutil, "which",
            side_effect=lambda name: "/usr/local/bin/copilot" if name == "copilot" else None,
        ):
            with mock.patch.object(
                copilot_resolver, "_probe_gh_copilot", return_value=False,
            ):
                copilot_resolver.resolve_copilot_command("p", "m")
                # Cached as "copilot".

        copilot_resolver.reset_cache()

        with mock.patch.object(
            copilot_resolver.shutil, "which", return_value=None,
        ):
            with mock.patch.object(
                copilot_resolver, "_probe_gh_copilot", return_value=True,
            ):
                cmd = copilot_resolver.resolve_copilot_command("p", "m")

        self.assertEqual(cmd[:2], ["gh", "copilot"],
                         "after reset_cache, detection re-runs and "
                         "the new scenario wins")


class ProbeGhCopilotTests(unittest.TestCase):
    """Internal ``_probe_gh_copilot`` returns False on
    FileNotFoundError (preserves benchmark_lib.require_copilot
    semantics)."""

    def setUp(self) -> None:
        copilot_resolver.reset_cache()

    def tearDown(self) -> None:
        copilot_resolver.reset_cache()

    def test_probe_returns_false_when_gh_not_installed(self) -> None:
        """``gh`` not on PATH → ``subprocess.run`` raises
        FileNotFoundError → probe returns False (not an
        exception). The skill must be able to be installed on hosts
        without ``gh`` at all."""
        with mock.patch.object(
            copilot_resolver.subprocess, "run",
            side_effect=FileNotFoundError("gh"),
        ):
            self.assertFalse(copilot_resolver._probe_gh_copilot())

    def test_probe_returns_false_on_nonzero_exit(self) -> None:
        """``gh`` exists but ``gh copilot --help`` returns non-zero
        (e.g., the extension was uninstalled) → probe returns False.
        """
        mock_result = mock.Mock(returncode=1)
        with mock.patch.object(
            copilot_resolver.subprocess, "run", return_value=mock_result,
        ):
            self.assertFalse(copilot_resolver._probe_gh_copilot())

    def test_probe_returns_true_on_zero_exit(self) -> None:
        """``gh copilot --help`` returns 0 → probe returns True."""
        mock_result = mock.Mock(returncode=0)
        with mock.patch.object(
            copilot_resolver.subprocess, "run", return_value=mock_result,
        ):
            self.assertTrue(copilot_resolver._probe_gh_copilot())


if __name__ == "__main__":
    unittest.main()
