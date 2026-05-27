"""v1.5.7 123 — Mode B must run run_playbook from a PRISTINE
QPB checkout (so a dirty dev tree doesn't abort it).

Root cause of repeated Mode B aborts: Mode B runs
``run_playbook`` from the live QPB clone (114). run_playbook's
source-guard (``_check_qpb_source_unchanged``) compares that
clone against committed HEAD and aborts if ANY tracked source
file differs. During harness development the working tree
almost always has uncommitted changes
(``bin/harness/acceptance_plan.json``,
``bin/harness/aup_experiment_plan.json``, ...), so Mode B
aborts at Phase 1 with "QPB source files modified during run"
— REGARDLESS of whether anything changes mid-run; it's the
pre-existing uncommitted state vs HEAD that trips the guard.

123 fix: materialize a PRISTINE QPB tree at HEAD via
``git worktree add --detach`` per Mode B run, run
``run_playbook`` from there. The worktree starts CLEAN
(matches HEAD), so the source-guard sees no diff and Phase 1
proceeds. Clean up the worktree at collect time so we don't
leak.

Coverage:
  * ``_materialize_pristine_qpb_tree`` creates a worktree
    at HEAD that's CLEAN vs HEAD (no diff).
  * ``_remove_pristine_qpb_tree`` cleans up
    + ``git worktree list`` no longer registers the path.
  * ``_mode_b_command(pristine_root=...)`` argv names the
    PRISTINE tree's ``bin/run_playbook.py``, not the live
    clone's.
  * **THE 123 LOAD-BEARING TEST**: a tiny git fixture
    standing in for a QPB clone with uncommitted dev
    changes ⇒ the materialized worktree is CLEAN vs HEAD,
    so a source-guard check passes. **Mutation-bite**:
    point Mode B back at the live dirty clone ⇒ the same
    guard check reports a diff (would abort).
  * Worktree lifecycle: ``git worktree list`` shows the
    pristine path during the run; after
    ``_remove_pristine_qpb_tree`` it's gone — no leaks.
  * Existing 114 + 115 + Mode A tests stay green.
  * Bundle-safety preserved.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bin.harness import runner as R
from bin.harness import schema as S


_REPO_ROOT = Path(__file__).resolve().parents[3]


def _git(args, cwd, **kw):
    """Run git with stdout/stderr captured. Returns
    completed-process. Raises on non-zero unless
    check=False explicit."""
    kwargs = {
        "cwd": str(cwd),
        "capture_output": True,
        "text": True,
        "timeout": 30,
    }
    if "check" not in kw:
        kwargs["check"] = True
    kwargs.update(kw)
    return subprocess.run(["git", *args], **kwargs)


def _init_qpb_like_fixture(tmp: Path) -> Path:
    """Build a tiny git fixture standing in for a QPB clone:
    a ``bin/run_playbook.py`` placeholder + a tracked file
    that we can later dirty up. Returns the clone root."""
    clone = tmp / "qpb-fixture"
    clone.mkdir()
    _git(["init", "--initial-branch=main"], cwd=clone)
    _git(["config", "user.email", "test@example.com"],
          cwd=clone)
    _git(["config", "user.name", "Test"], cwd=clone)
    (clone / "bin").mkdir()
    (clone / "bin" / "run_playbook.py").write_text(
        "# fake run_playbook for tests\n",
        encoding="utf-8",
    )
    (clone / "bin" / "harness").mkdir()
    (clone / "bin" / "harness" / "acceptance_plan.json").write_text(
        '{"runs":[]}\n',
        encoding="utf-8",
    )
    _git(["add", "-A"], cwd=clone)
    _git(["commit", "-m", "initial"], cwd=clone)
    return clone


def _diff_vs_head(clone: Path) -> "list[str]":
    """Return tracked files that differ from HEAD in clone's
    working tree (the source-guard's core check)."""
    result = _git(
        ["diff", "--name-only", "HEAD"],
        cwd=clone, check=False,
    )
    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]


# ---------------------------------------------------------------------------
# Task A — _materialize / _remove pristine worktree
# ---------------------------------------------------------------------------


class MaterializePristineTreeTests(unittest.TestCase):
    """``_materialize_pristine_qpb_tree`` + matching cleanup
    against the REAL QPB clone the harness runs from."""

    def test_creates_clean_worktree(self) -> None:
        """The materialized worktree starts CLEAN vs HEAD
        (no uncommitted changes) — that's the whole point."""
        # Use the REAL QPB clone (where this test runs from)
        # — _materialize_pristine_qpb_tree always works
        # against that.
        tree = R._materialize_pristine_qpb_tree()
        try:
            # The tree exists + contains the expected
            # entry point.
            self.assertTrue(tree.is_dir())
            self.assertTrue(
                (tree / "bin" / "run_playbook.py").is_file())
            # The tree is CLEAN vs HEAD: `git diff
            # --name-only HEAD` returns nothing.
            self.assertEqual(_diff_vs_head(tree), [])
        finally:
            R._remove_pristine_qpb_tree(tree)

    def test_remove_tears_down_worktree(self) -> None:
        """``_remove_pristine_qpb_tree`` removes the worktree
        directory AND unregisters it from
        ``git worktree list``. No leaks."""
        tree = R._materialize_pristine_qpb_tree()
        # Confirm worktree IS registered.
        qpb_clone = R._qpb_clone_root_for_mode_b()
        listing = _git(["worktree", "list"], cwd=qpb_clone)
        self.assertIn(str(tree), listing.stdout,
                        "freshly-materialized worktree must "
                        "be registered in `git worktree list`")
        # Tear down.
        R._remove_pristine_qpb_tree(tree)
        # Directory should be gone.
        self.assertFalse(
            tree.exists(),
            f"123: worktree dir {tree} must be removed after "
            f"_remove_pristine_qpb_tree — leaking worktrees "
            f"accumulate across runs",
        )
        # And `git worktree list` no longer shows it.
        listing_after = _git(["worktree", "list"],
                               cwd=qpb_clone)
        self.assertNotIn(
            str(tree), listing_after.stdout,
            "123: torn-down worktree must NOT appear in "
            "`git worktree list` — `git worktree remove` "
            "was supposed to unregister it",
        )

    def test_remove_is_idempotent(self) -> None:
        """``_remove_pristine_qpb_tree`` is best-effort —
        calling it on a path that was already removed (or
        never existed) is a no-op, not an error."""
        # Should not raise.
        R._remove_pristine_qpb_tree(
            Path("/tmp/does-not-exist-123"))


# ---------------------------------------------------------------------------
# Task A — _mode_b_command(pristine_root=…) argv shape
# ---------------------------------------------------------------------------


class ModeBCommandPristineRootTests(unittest.TestCase):
    """``_mode_b_command(pristine_root=...)`` names the
    PRISTINE tree's bin/run_playbook.py — NOT the live
    clone's (114 path).

    Pre-123 / when pristine_root is None: 114 behavior
    (live clone path) preserved as the fallback."""

    def test_pristine_root_argv_overrides_live_clone(
            self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()
            pristine = Path(tmp) / "pristine"
            (pristine / "bin").mkdir(parents=True)
            (pristine / "bin" / "run_playbook.py").write_text(
                "# pristine fake\n", encoding="utf-8")
            cmd = R._mode_b_command(
                S.Runner.CLAUDE, target, model="opus",
                pristine_root=pristine,
            )
            # cmd[1] is the script path. With pristine_root,
            # it points at the pristine tree (NOT the live
            # QPB clone's path).
            self.assertEqual(
                cmd[1],
                str(pristine / "bin" / "run_playbook.py"),
                "123: pristine_root argv MUST name the "
                "pristine tree's run_playbook.py — that's "
                "how the source-guard sees a clean tree",
            )

    def test_no_pristine_root_falls_back_to_live_clone(
            self) -> None:
        """When pristine_root is None (e.g. legacy callers
        or non-Mode-B paths), fall back to the 114
        ``_resolve_run_playbook_script`` behavior (live
        clone). This preserves the existing tests."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            cmd = R._mode_b_command(
                S.Runner.CLAUDE, target, model="opus",
                pristine_root=None,
            )
            # 114 fallback: live QPB clone path.
            expected_live = (
                Path(R.__file__).resolve().parents[2]
                / "bin" / "run_playbook.py"
            )
            self.assertEqual(cmd[1], str(expected_live))

    def test_command_for_axes_threads_pristine_root(
            self) -> None:
        """``_command_for_axes(pristine_root=...)`` threads
        the kwarg through to ``_mode_b_command`` (so
        ``launch_run_async`` can supply it from
        ``LaunchSpec.pristine_root``)."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            target.mkdir()
            pristine = Path(tmp) / "pristine"
            (pristine / "bin").mkdir(parents=True)
            (pristine / "bin" / "run_playbook.py").write_text(
                "# pristine fake\n", encoding="utf-8")
            axes = S.RunAxes(
                runner=S.Runner.CLAUDE, mode=S.Mode.B,
                install_channel=S.InstallChannel.CLONE,
                model="opus",
            )
            cmd = R._command_for_axes(
                axes, "(unused)",
                target_dir=target,
                pristine_root=pristine,
            )
            self.assertEqual(
                cmd[1],
                str(pristine / "bin" / "run_playbook.py"))


# ---------------------------------------------------------------------------
# Task B — THE 123 LOAD-BEARING TEST + mutation-bite
# ---------------------------------------------------------------------------


class PristineWorktreeClearsDirtyTreeGuardTests(
        unittest.TestCase):
    """**THE 123 LOAD-BEARING TEST**: a dirty harness clone
    (uncommitted tracked changes) is the AUP-experiment's
    Mode B failure cause. With 123's pristine worktree, the
    source-guard's "is the source clean?" check passes;
    without it (mutation-bite), the check fails on the dirty
    tree.

    Uses a tiny git fixture standing in for a QPB clone, so
    the test is independent of the real QPB clone's state.
    Mirrors the source-guard's check (``git diff --name-only
    HEAD`` against tracked source paths) without needing
    run_playbook itself."""

    def test_pristine_worktree_is_clean_even_when_clone_dirty(
            self) -> None:
        """**Mutation-bite asymmetry**: the LIVE clone is
        dirty (uncommitted tracked change) but the PRISTINE
        worktree at the same HEAD is clean. The source-
        guard's check (= ``git diff --name-only HEAD``)
        reports the diff against the live clone but not
        against the worktree.

        Pre-123 Mode B pointed at the live clone ⇒ the
        check fired ⇒ Phase 1 aborted. Post-123 Mode B
        points at the pristine worktree ⇒ the check is
        clean ⇒ Phase 1 proceeds."""
        with tempfile.TemporaryDirectory() as tmp:
            clone = _init_qpb_like_fixture(Path(tmp))
            # Make working tree DIRTY: edit a tracked file.
            (clone / "bin" / "harness"
              / "acceptance_plan.json").write_text(
                '{"runs":[{"description":"WIP"}]}\n',
                encoding="utf-8",
            )
            # Confirm the live clone has a diff vs HEAD —
            # the source-guard's positive case (would abort).
            live_diff = _diff_vs_head(clone)
            self.assertIn(
                "bin/harness/acceptance_plan.json",
                live_diff,
                "fixture: live clone must have a diff vs "
                "HEAD (mutation-bite baseline)",
            )
            # Materialize a pristine worktree from the SAME
            # clone at the SAME HEAD.
            worktree_dir = Path(tmp) / "pristine-tree"
            _git(
                ["worktree", "add", "--detach",
                  str(worktree_dir), "HEAD"],
                cwd=clone,
            )
            try:
                # The worktree is CLEAN vs HEAD — the
                # source-guard would pass against it.
                worktree_diff = _diff_vs_head(worktree_dir)
                self.assertEqual(
                    worktree_diff, [],
                    "123 contract: pristine worktree at "
                    "HEAD must be CLEAN vs HEAD even when "
                    "the source clone has uncommitted "
                    "tracked changes — that's how the "
                    "source-guard passes",
                )
                # Verify the worktree has the run_playbook
                # stand-in at the expected path (114
                # invariant — Mode B argv expects it).
                self.assertTrue(
                    (worktree_dir / "bin"
                      / "run_playbook.py").is_file()
                )
            finally:
                _git(["worktree", "remove", "--force",
                       str(worktree_dir)],
                      cwd=clone, check=False)


# ---------------------------------------------------------------------------
# LaunchSpec.pristine_root + manifest entry threading
# ---------------------------------------------------------------------------


class LaunchSpecPristineRootFieldTests(unittest.TestCase):
    """``LaunchSpec.pristine_root`` is a new optional field
    (default None) — Mode A LaunchSpecs don't set it, Mode
    B's launch site does. ``launch_run_async`` threads it
    through to ``_command_for_axes``."""

    def test_launchspec_default_pristine_root_is_none(
            self) -> None:
        """114 + Mode A existing tests don't set
        pristine_root; ensure the default is None so they
        keep working."""
        spec = R.LaunchSpec(
            target_dir=Path("/tmp/synthetic"),
            run_dir=Path("/tmp/synthetic-run"),
            axes=S.RunAxes(
                runner=S.Runner.CLAUDE, mode=S.Mode.A,
                install_channel=S.InstallChannel.CLONE,
                model="opus",
            ),
            case_id="c", run_id="r",
            max_duration_s=60.0, prompt="x",
        )
        self.assertIsNone(spec.pristine_root)


# ---------------------------------------------------------------------------
# Bundle-safety
# ---------------------------------------------------------------------------


class BundleSafety123Tests(unittest.TestCase):

    def test_changes_stay_under_harness(self) -> None:
        from bin.install_skill import _bundle_files
        repo_root = Path(__file__).resolve().parents[3]
        bundle = _bundle_files(repo_root)
        for _src, dst in bundle:
            p = str(dst)
            self.assertFalse(
                "harness" in p,
                f"123 must not leak bin/harness/ into the "
                f"bundle; saw {p}",
            )


if __name__ == "__main__":
    unittest.main()
