"""v1.5.7 124 — fix the codex adapter: ``codex exec`` is
single-turn (can't self-drive Mode A) + ``--full-auto`` is
deprecated.

First real codex Mode A run (cross-runner run-05,
gson/gpt-5.3-codex-low) "FAILED" at ~51s — but the captured
stream showed it didn't crash: codex read SKILL.md, then
replied "I can't truthfully run Phases 1–6 + gate as a single
unattended pipeline … I can proceed with the fallback of
manually executing Mode A phase prompts 1→6", and the
``codex exec`` turn ended. Unlike ``claude --print`` (which
sustains the multi-phase agentic loop), ``codex exec`` is
SINGLE-TURN — so a Mode A "all 6 phases in one session"
expectation is structurally wrong for codex.

Codex v0.133.0+ also deprecated ``--full-auto`` in favor of
``--sandbox workspace-write``.

124 fix:
  * Task A — flag currency: ``_codex_command`` builds
    ``codex exec --sandbox workspace-write …`` instead of
    ``codex exec --full-auto …``. Same semantics, no
    deprecation warning.
  * Task B — Mode B routing: codex Mode A is REJECTED at
    command-build time with a clear, operator-actionable
    message. The right way to drive codex is Mode B —
    run_playbook invokes a FRESH ``codex exec`` per phase
    (matches codex's single-turn nature).
  * The same flag fix is applied to run_playbook's per-phase
    ``codex`` invocation (used by Mode B) so per-phase
    codex driving uses the non-deprecated flag too.

Coverage:
  * ``_codex_command`` builds the post-124 argv (``--sandbox
    workspace-write``); mutation-bite: revert to
    ``--full-auto`` ⇒ test FAILS.
  * ``run_playbook.command_for_runner("codex", model)``
    likewise builds the post-124 argv (Mode B per-phase
    driving uses the updated flag).
  * ``_command_for_axes(codex, Mode.A)`` REJECTS with a
    clear ``RunnerError`` mentioning the single-turn limit
    AND the Mode-B recommendation. **Mutation-bite**:
    remove the rejection and codex Mode A would launch a
    doomed single-exec (the cross-runner run-05 case).
  * ``_command_for_axes(codex, Mode.B)`` works fine —
    routes through ``_mode_b_command`` to invoke
    run_playbook (which drives codex per-phase).
  * claude / copilot adapters unaffected; they still build
    via their own paths.
  * Bundle-safety preserved.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bin.harness import runner as R
from bin.harness import schema as S


# ---------------------------------------------------------------------------
# Task A — _codex_command uses --sandbox workspace-write
# ---------------------------------------------------------------------------


class CodexCommandSandboxFlagTests(unittest.TestCase):
    """**THE 124 TASK-A MUTATION-BITE**: the codex argv MUST
    use ``--sandbox workspace-write`` (codex v0.133.0+) and
    MUST NOT use ``--full-auto`` (deprecated)."""

    def test_codex_command_uses_sandbox_workspace_write(
            self) -> None:
        cmd = R._codex_command("opus")
        # Order: codex → exec → --sandbox → workspace-write →
        # -m → model → -.
        self.assertEqual(cmd[0], "codex")
        self.assertEqual(cmd[1], "exec")
        self.assertEqual(cmd[2], "--sandbox")
        self.assertEqual(cmd[3], "workspace-write")
        self.assertIn("-m", cmd)
        self.assertEqual(cmd[cmd.index("-m") + 1], "opus")
        self.assertEqual(cmd[-1], "-")

    def test_codex_command_does_not_use_full_auto(self) -> None:
        """**The 124 mutation-bite**: revert to
        ``--full-auto`` and this test FAILS. Pre-124 codex
        v0.133.0 printed "warning: --full-auto is deprecated"
        on every invocation — the deprecation is real."""
        cmd = R._codex_command("opus")
        self.assertNotIn(
            "--full-auto", cmd,
            "124: ``_codex_command`` MUST NOT use the "
            "deprecated ``--full-auto`` flag — codex "
            "v0.133.0+ replaces it with "
            "``--sandbox workspace-write``.",
        )

    def test_codex_command_parameters_splice_position(
            self) -> None:
        """The 100 contract: ``-c k=v`` global overrides go
        BETWEEN ``codex`` and ``exec``. Post-124 the suffix
        ``--sandbox workspace-write`` lands BETWEEN ``exec``
        and ``-m``."""
        cmd = R._codex_command(
            "opus",
            parameters=["-c", "model_reasoning_effort=\"low\""],
        )
        self.assertEqual(cmd[0], "codex")
        self.assertEqual(cmd[1], "-c")
        self.assertEqual(
            cmd[2], 'model_reasoning_effort="low"')
        self.assertEqual(cmd[3], "exec")
        self.assertEqual(cmd[4], "--sandbox")
        self.assertEqual(cmd[5], "workspace-write")
        self.assertEqual(cmd[-1], "-")

    def test_run_playbook_codex_command_uses_sandbox(
            self) -> None:
        """v1.5.7 124: the SAME flag fix in
        ``run_playbook.command_for_runner("codex", model)``.
        Mode B drives codex by invoking run_playbook, which
        spawns a fresh ``codex exec`` per phase — that
        invocation must also use the non-deprecated flag."""
        from bin.run_playbook import command_for_runner
        # codex prompt is piped on stdin via the `-` sentinel,
        # so the positional `prompt` arg isn't used in the
        # codex branch — pass an empty string.
        cmd = command_for_runner(
            "codex", "", model="gpt-5-codex")
        self.assertIn("--sandbox", cmd)
        self.assertIn("workspace-write", cmd)
        self.assertNotIn(
            "--full-auto", cmd,
            "124: run_playbook's codex invocation MUST NOT "
            "use deprecated ``--full-auto`` either — Mode B "
            "per-phase driving goes through this code path.",
        )


# ---------------------------------------------------------------------------
# Task B — codex Mode A rejected; codex Mode B routes correctly
# ---------------------------------------------------------------------------


def _mk_axes(runner: S.Runner = S.Runner.CODEX, *,
             mode: S.Mode = S.Mode.A,
             channel: S.InstallChannel = S.InstallChannel.CLONE,
             model: str = "gpt-5-codex") -> S.RunAxes:
    return S.RunAxes(
        runner=runner, mode=mode,
        install_channel=channel, model=model,
    )


class CodexModeARejectionTests(unittest.TestCase):
    """**THE 124 TASK-B MUTATION-BITE**: ``_command_for_axes``
    MUST reject ``(Runner.CODEX, Mode.A)`` at command-build
    time. Pre-124 the cross-runner run-05 launched a doomed
    single-exec that hedged and exited; post-124 the rejection
    surfaces the issue to the plan author with a clear
    message."""

    def test_codex_mode_a_raises_runner_error(self) -> None:
        with self.assertRaises(R.RunnerError) as ctx:
            R._command_for_axes(
                _mk_axes(S.Runner.CODEX, mode=S.Mode.A),
                "(any prompt)",
            )
        msg = str(ctx.exception)
        # Message must point the plan author at Mode B + the
        # single-turn reasoning. Operators reading the error
        # should know exactly what to change.
        self.assertIn("codex Mode A is not supported", msg)
        self.assertIn("single-turn", msg)
        self.assertIn("Mode B", msg)
        self.assertIn("mode: B", msg)

    def test_codex_mode_a_rejection_is_at_command_build_time(
            self) -> None:
        """The rejection fires BEFORE any subprocess is
        spawned — operators see the error immediately,
        not after a 51s codex exec that hedges and exits.
        Verify by passing no target_dir (which Mode B would
        REQUIRE) and confirming the rejection still fires —
        proves it's checked before any other validation."""
        with self.assertRaises(R.RunnerError) as ctx:
            R._command_for_axes(
                _mk_axes(S.Runner.CODEX, mode=S.Mode.A),
                "(any prompt)",
                target_dir=None,
            )
        # The CODEX-Mode-A rejection fires (NOT the
        # "Mode B requires target_dir" rejection — which
        # only applies to Mode B).
        self.assertIn("Mode A is not supported",
                        str(ctx.exception))

    def test_other_runners_mode_a_still_work(self) -> None:
        """**Regression pin — DO NOT BREAK MODE A FOR
        OTHER RUNNERS**: claude / copilot / cursor are
        multi-turn capable, so Mode A still works for
        them. The 124 rejection is codex-ONLY."""
        for runner in (S.Runner.CLAUDE, S.Runner.COPILOT,
                        S.Runner.CURSOR):
            try:
                cmd = R._command_for_axes(
                    _mk_axes(runner, mode=S.Mode.A,
                             model="opus"),
                    "prompt",
                )
                self.assertIsInstance(cmd, list)
                self.assertGreater(len(cmd), 0)
            except R.RunnerError as exc:
                self.fail(
                    f"124: {runner.value} Mode A MUST NOT "
                    f"be rejected — the rejection is "
                    f"codex-only. Got: {exc}"
                )


class CodexModeBRoutingTests(unittest.TestCase):
    """codex Mode B is the SUPPORTED path post-124. It
    routes through ``_mode_b_command`` to invoke
    run_playbook — which drives codex per-phase via fresh
    ``codex exec`` invocations (the right mapping for
    codex's single-turn semantics)."""

    def test_codex_mode_b_routes_through_mode_b_command(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()
            cmd = R._command_for_axes(
                _mk_axes(S.Runner.CODEX, mode=S.Mode.B,
                          model="gpt-5-codex"),
                "(unused-in-mode-b)",
                target_dir=target,
            )
            # Mode B argv: python3 <qpb_clone>/bin/run_playbook.py
            # --codex --model <m> <target>.
            import sys
            self.assertEqual(cmd[0], sys.executable)
            # cmd[1] is the absolute path to run_playbook.py.
            self.assertTrue(cmd[1].endswith(
                "bin/run_playbook.py"))
            self.assertIn("--codex", cmd)
            self.assertEqual(
                cmd[cmd.index("--model") + 1], "gpt-5-codex")
            self.assertEqual(cmd[-1], str(target))

    def test_codex_mode_b_with_pristine_root_works(
            self) -> None:
        """Codex Mode B + 123's pristine worktree path:
        the Mode B argv names the PRISTINE tree's
        run_playbook.py, which itself drives codex
        per-phase via fresh ``codex exec`` (with 124's
        flag fix)."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()
            pristine = Path(tmp) / "pristine"
            (pristine / "bin").mkdir(parents=True)
            (pristine / "bin" / "run_playbook.py").write_text(
                "# pristine\n", encoding="utf-8")
            cmd = R._command_for_axes(
                _mk_axes(S.Runner.CODEX, mode=S.Mode.B,
                          model="gpt-5-codex"),
                "(unused)",
                target_dir=target,
                pristine_root=pristine,
            )
            self.assertEqual(
                cmd[1],
                str(pristine / "bin" / "run_playbook.py"))
            self.assertIn("--codex", cmd)


# ---------------------------------------------------------------------------
# Bundle-safety
# ---------------------------------------------------------------------------


class BundleSafety124Tests(unittest.TestCase):

    def test_changes_stay_under_harness(self) -> None:
        from bin.install_skill import _bundle_files
        repo_root = Path(__file__).resolve().parents[3]
        bundle = _bundle_files(repo_root)
        for _src, dst in bundle:
            p = str(dst)
            self.assertFalse(
                "harness" in p,
                f"124 must not leak bin/harness/ into the "
                f"bundle; saw {p}",
            )


if __name__ == "__main__":
    unittest.main()
