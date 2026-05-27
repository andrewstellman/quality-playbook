"""v1.5.7 114 — Mode B's run_playbook MUST be launched via its
absolute-script-path (not bare ``-m bin.run_playbook``) because
the harness launches with ``cwd=target_dir``.

Surfaced on the AUP-experiment: all three Mode B runs produced
**79-byte streams** containing exactly:

    /opt/homebrew/.../python3: No module named bin.run_playbook

The pre-114 launch command was ``python3 -m bin.run_playbook
--<runner> --model <model> <target>``. The ``-m`` form requires
``bin/`` to be importable from cwd. ``launch_run_async`` launches
with ``cwd=target_dir`` (the channel-installed target, NOT the
QPB clone root), so the import died immediately and Mode B
never ran. This is the real-execution gap behind 106's "MUST
VERIFY Mode B drives the channel-installed target" — 106 pinned
source-level invariants but never actually LAUNCHED a Mode B run
against an installed target, so it slipped through.

114 design note: the instruction's wording assumed
``run_playbook.py`` is installed under the target's skill dir
(``<target>/.claude/skills/.../bin/run_playbook.py``). It is
NOT — the install bundle deliberately excludes run_playbook.py
(``install_skill.py:397-398`` comment: "minus `bin.run_playbook`
(the Mode-B harness invoked from the QPB clone, NOT from
install_root)"). So we resolve the script by its absolute path
in the QPB clone (relative to ``runner.py``'s ``__file__``).
run_playbook.py's own header injects QPB root into ``sys.path``
when invoked as a direct script, so its sibling imports
(``benchmark_lib``, ``archive_lib``, ``copilot_resolver``)
resolve regardless of the subprocess's cwd. This is the
ESSENTIAL invariant the 114 instruction calls out: "the
subprocess MUST be able to import run_playbook's siblings
(no `No module named …`)."

Coverage:
  * ``runner._resolve_run_playbook_script`` returns the
    QPB-clone-relative absolute path to ``bin/run_playbook.py``;
    the returned path actually exists on disk.
  * ``runner._mode_b_command`` argv names that absolute script
    path (NOT ``-m bin.run_playbook``).
  * **THE 114 MUTATION-BITE / REAL LAUNCH TEST**: stand up a
    channel-installed target via the actual installer, build
    the Mode B command, ACTUALLY LAUNCH the subprocess with
    cwd=target_dir, and assert the stream does NOT contain
    ``No module named …``. ``run_playbook --help`` short-
    circuits past phase work after import + arg parsing
    succeed — that's enough to PROVE the import boundary the
    AUP experiment died on now works. Mutation: revert
    ``_mode_b_command`` to ``-m bin.run_playbook`` ⇒ the test
    FAILS with ``No module named bin.run_playbook``.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bin.harness import runner as R
from bin.harness import schema as S


_REPO_ROOT = Path(__file__).resolve().parents[3]
_EXPECTED_SCRIPT = _REPO_ROOT / "bin" / "run_playbook.py"


def _mk_axes(runner: S.Runner = S.Runner.CLAUDE, *,
             mode: S.Mode = S.Mode.B,
             channel: S.InstallChannel = S.InstallChannel.CLONE,
             model: str = "opus") -> S.RunAxes:
    return S.RunAxes(
        runner=runner, mode=mode,
        install_channel=channel, model=model,
    )


def _install_real_skill_into(target_dir: Path) -> Path:
    """Run the actual ``bin/install_skill`` against
    ``target_dir`` (clone channel, claude ai-tool). Returns the
    install root. Skipped via SkipTest on installer failure so
    a sandbox-limited environment doesn't false-fail."""
    target_dir.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [sys.executable, "-m", "bin.install_skill",
              "--into", str(target_dir),
              "--ai-tool", "claude",
              "--no-smoke"],
            cwd=str(_REPO_ROOT),
            check=True, capture_output=True, text=True,
            timeout=60,
        )
    except subprocess.CalledProcessError as exc:
        raise unittest.SkipTest(
            f"install_skill returned non-zero in this "
            f"environment; skipping the 114 launch test "
            f"(stderr={exc.stderr[-400:]!r})"
        )
    except subprocess.TimeoutExpired:
        raise unittest.SkipTest(
            "install_skill timed out in this environment"
        )
    install_root = (target_dir / ".claude" / "skills"
                     / "quality-playbook")
    if not (install_root / "SKILL.md").is_file():
        raise unittest.SkipTest(
            f"install_skill ran but didn't produce SKILL.md "
            f"at {install_root}"
        )
    return install_root


# ---------------------------------------------------------------------------
# Task A — _resolve_run_playbook_script resolver
# ---------------------------------------------------------------------------


class ResolveRunPlaybookScriptTests(unittest.TestCase):
    """Pin the resolver contract: return the absolute path to
    ``bin/run_playbook.py`` inside the QPB clone (where this
    test, runner.py, and run_playbook all live)."""

    def test_returns_absolute_qpb_clone_script_path(
            self) -> None:
        script = R._resolve_run_playbook_script()
        self.assertEqual(script, _EXPECTED_SCRIPT)
        self.assertTrue(script.is_absolute())
        self.assertTrue(script.is_file(),
                          f"expected run_playbook.py at {script}")

    def test_target_dir_arg_is_ignored(self) -> None:
        """The ``target_dir`` parameter is accepted for forward
        compatibility (callers may pass it through generic
        contracts) but the returned script is the same — the
        QPB-clone run_playbook drives any target."""
        with tempfile.TemporaryDirectory() as tmp:
            target_a = Path(tmp) / "a"
            target_b = Path(tmp) / "b"
            target_a.mkdir()
            target_b.mkdir()
            self.assertEqual(
                R._resolve_run_playbook_script(target_a),
                R._resolve_run_playbook_script(target_b),
            )


# ---------------------------------------------------------------------------
# Task A — _mode_b_command argv shape uses absolute script path
# ---------------------------------------------------------------------------


class ModeBCommandArgvShapeTests(unittest.TestCase):
    """Post-114 argv form is ``python3
    <qpb_clone>/bin/run_playbook.py --<runner> --model <model>
    [<params>] <target>`` — NOT the pre-114 ``-m
    bin.run_playbook``."""

    def test_argv_uses_script_path_not_dash_m(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            cmd = R._mode_b_command(
                S.Runner.CLAUDE, target, model="opus",
            )
            self.assertEqual(cmd[0], sys.executable)
            self.assertEqual(cmd[1], str(_EXPECTED_SCRIPT))
            # **THE 114 MUTATION-BITE shape assertion**: ``-m
            # bin.run_playbook`` must NOT appear anywhere in
            # the argv. Pre-114 it did; reverting to that form
            # makes this assertion fail.
            self.assertNotIn("-m", cmd)
            self.assertNotIn("bin.run_playbook", cmd)
            self.assertIn("--claude", cmd)
            self.assertEqual(
                cmd[cmd.index("--model") + 1], "opus",
            )
            self.assertEqual(cmd[-1], str(target))

    def test_argv_with_parameters_spliced_before_target(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            cmd = R._mode_b_command(
                S.Runner.COPILOT, target, model="gpt-5.4",
                parameters=["--phase", "3"],
            )
            self.assertIn("--phase", cmd)
            self.assertEqual(cmd[-1], str(target))
            self.assertLess(cmd.index("--phase"),
                             cmd.index(str(target)))

    def test_argv_each_runner_uses_absolute_script(
            self) -> None:
        """All four runners route through the absolute-script
        form (one resolver, one script form, four flags)."""
        for runner_axis, expected_flag in (
            (S.Runner.CLAUDE, "--claude"),
            (S.Runner.CODEX, "--codex"),
            (S.Runner.COPILOT, "--copilot"),
            (S.Runner.CURSOR, "--cursor"),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                target = Path(tmp)
                cmd = R._mode_b_command(
                    runner_axis, target, model="x",
                )
                self.assertEqual(cmd[1], str(_EXPECTED_SCRIPT))
                self.assertIn(expected_flag, cmd)
                self.assertNotIn("-m", cmd)


# ---------------------------------------------------------------------------
# Task B — THE REAL LAUNCH TEST (THE 114 MUTATION-BITE)
# ---------------------------------------------------------------------------


class ModeBRealLaunchAgainstInstalledTargetTests(
        unittest.TestCase):
    """**THE 114 LOAD-BEARING TEST**: actually launch the
    Mode B command against a channel-installed target.

    The instruction explicitly calls out: "Add a test that
    **actually launches** the Mode B command against a
    **channel/clone-installed** target … and asserts run_playbook
    **actually starts and imports cleanly**." 106 pinned source-
    level invariants but NEVER actually launched a Mode B run,
    which is how the ``No module named bin.run_playbook`` bug
    slipped through. This test exercises the real subprocess
    launch with ``cwd=target_dir`` and asserts the import
    succeeds (the stream does NOT contain ``No module named …``).

    Short-circuit: invoke ``run_playbook --help`` so the
    subprocess exits 0 immediately after argparse — that's
    enough to PROVE the module import + entry point worked.
    A full phase run isn't needed; the bug is at the IMPORT
    boundary."""

    def test_run_playbook_imports_cleanly_with_target_cwd(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            _install_real_skill_into(target)
            axes = _mk_axes(S.Runner.CLAUDE, mode=S.Mode.B,
                              model="opus")
            # The harness's _command_for_axes is what production
            # launch_run_async calls — go through it, not the
            # private _mode_b_command directly.
            cmd = R._command_for_axes(
                axes, "(unused-in-mode-b)", target_dir=target,
                parameters=["--help"],
            )
            # **Reproduce the production launch posture**: cwd
            # is the target_dir, NOT the QPB clone. This is the
            # exact condition that made the pre-114 `-m
            # bin.run_playbook` form die.
            proc = subprocess.run(
                cmd, cwd=str(target),
                capture_output=True, text=True, timeout=30,
            )
            output = proc.stdout + proc.stderr
            # **THE 114 MUTATION-BITE**: the import must not
            # fail. Revert _mode_b_command to ``-m
            # bin.run_playbook`` ⇒ this assertion fails with
            # the very error message the AUP-experiment showed.
            self.assertNotIn(
                "No module named bin.run_playbook", output,
                "114: Mode B's run_playbook must import "
                "cleanly when launched with cwd=target. The "
                "pre-114 `-m bin.run_playbook` form died "
                "here with the AUP-experiment's 79-byte "
                "stream (`No module named bin.run_playbook`).",
            )
            # Sibling imports must also resolve — the script
            # form relies on run_playbook's own sys.path
            # injection (its header inserts QPB-root). If
            # that injection were missing, we'd see something
            # like ``No module named benchmark_lib`` here.
            self.assertNotIn(
                "No module named", output,
                f"Sibling-module import failed: {output[:400]!r}",
            )
            # And --help completed (exit 0 + help text).
            self.assertEqual(
                proc.returncode, 0,
                f"run_playbook --help exited {proc.returncode} "
                f"(expected 0); output: {output[:400]!r}",
            )
            self.assertIn(
                "usage:", output.lower(),
                f"argparse --help output missing — the launch "
                f"didn't reach argument parsing; output: "
                f"{output[:400]!r}",
            )

    def test_argv_form_regression_guard(self) -> None:
        """Document the pre-114 vs post-114 argv difference
        explicitly. The pre-114 argv ``["-m", "bin.run_playbook",
        ...]`` is what produced the 79-byte ``No module named …``
        streams; the post-114 argv names the absolute script
        path. Any future refactor must NOT regress to ``-m``."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            cmd = R._mode_b_command(
                S.Runner.CLAUDE, target, model="opus",
            )
            # Affirmative: cmd[1] is the absolute script path.
            self.assertEqual(
                cmd[1], str(_EXPECTED_SCRIPT),
                "114 post-fix: argv must name the absolute "
                "run_playbook.py path",
            )
            # Negative: the pre-114 `-m bin.run_playbook` form
            # must NOT reappear.
            joined = " ".join(cmd)
            self.assertNotIn(
                "-m bin.run_playbook", joined,
                "114 regression guard: the pre-114 `-m "
                "bin.run_playbook` form must never reappear "
                "in the Mode B argv — it died with `No module "
                "named bin.run_playbook` when launched with "
                "cwd=target_dir on the AUP experiment.",
            )


# ---------------------------------------------------------------------------
# Bundle-safety: 114 lives under bin/harness/ (excluded)
# ---------------------------------------------------------------------------


class BundleSafety114Tests(unittest.TestCase):

    def test_runner_changes_stay_under_harness(self) -> None:
        """114 modifies bin/harness/runner.py +
        bin/tests/harness/test_mode_b_launch_path_114.py. Both
        under the excluded harness path; the bundle must not
        leak them."""
        from bin.install_skill import _bundle_files
        repo_root = Path(__file__).resolve().parents[3]
        bundle = _bundle_files(repo_root)
        for _src, dst in bundle:
            p = str(dst)
            self.assertFalse(
                "harness" in p,
                f"114 must not leak bin/harness/ into the "
                f"bundle; saw {p}",
            )

    def test_run_playbook_remains_excluded_from_bundle(
            self) -> None:
        """The 114 fix DEPENDS on run_playbook.py NOT being
        in the install bundle (we resolve it from the QPB
        clone). If a future refactor adds run_playbook to the
        bundle, the design note in
        ``_resolve_run_playbook_script`` needs updating — this
        test alerts us."""
        from bin.install_skill import _bundle_files
        repo_root = Path(__file__).resolve().parents[3]
        bundle = _bundle_files(repo_root)
        run_playbook_in_bundle = any(
            str(dst).endswith("bin/run_playbook.py")
            or str(dst).endswith("bin\\run_playbook.py")
            for _src, dst in bundle
        )
        self.assertFalse(
            run_playbook_in_bundle,
            "114 design note (in _resolve_run_playbook_script) "
            "claims the install bundle excludes run_playbook.py. "
            "If this test fails, the bundle has changed — "
            "update the design note + consider switching to the "
            "install-path lookup the 114 instruction originally "
            "expected.",
        )


if __name__ == "__main__":
    unittest.main()
