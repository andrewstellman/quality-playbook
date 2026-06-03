"""v1.5.7 105 — harden `clone_worktree`: `git switch` + skip
redundant default-branch re-checkout.

Found on the first live 4-repo `run-plan`: chi's run hit
`ABORTED_PREP: checkout 'main' failed`. Two issues:

  (1) The plan named chi's ref ``main`` but go-chi/chi's default
      branch is ``master`` (data file fixed in the Cowork lane).
  (2) ``clone_worktree`` did an unconditional ``git checkout
      <ref>`` even when ``<ref>`` was already the checked-out
      branch — wasteful AND a needless failure surface for the
      common "plan names the default branch" case.

105 hardens ``clone_worktree``:
  * If ``target_ref`` equals the cloned default branch → NO
    switch (the common case).
  * Otherwise: ``git switch <ref>`` (preferred — auto-tracks
    origin/<ref>); falls back to ``git switch --detach <ref>``
    for SHAs/tags.
  * Bad refs still raise ``PrepError`` → ``ABORTED_PREP``.

Tests use tiny local fixture repos (real ``git init`` + commits;
no network), the same pattern the 103 live-composition test
uses.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

from bin.harness import prepare as P


def _git(repo: Path, *args: str) -> str:
    """Run a git command inside ``repo`` and return stdout."""
    result = subprocess.run(
        ["git", *args], cwd=str(repo),
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def _make_fixture_repo(parent: Path, *,
                        default_branch: str = "master",
                        extra_commits: int = 0,
                        extra_branches: "list[str] | None" = None,
                        ) -> tuple[str, Path]:
    """Create a fixture git repo with the given default branch +
    a configurable number of commits + optional extra branches.
    Returns ``(file_url, repo_path)``."""
    repo = parent / f"fixture-{default_branch}"
    repo.mkdir()
    _git(repo, "init", f"--initial-branch={default_branch}")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("# fixture\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")
    for i in range(extra_commits):
        (repo / f"f{i}.txt").write_text(f"{i}\n", encoding="utf-8")
        _git(repo, "add", f"f{i}.txt")
        _git(repo, "commit", "-m", f"add f{i}")
    for branch in (extra_branches or []):
        # Create branch at HEAD without switching.
        _git(repo, "branch", branch)
    return f"file://{repo}", repo


# ---------------------------------------------------------------------------
# Task A.1 — default-branch ref ⇒ NO switch (the common case)
# ---------------------------------------------------------------------------


class DefaultBranchNoSwitchTests(unittest.TestCase):

    def test_default_branch_master_skips_switch(self) -> None:
        """A repo whose default is ``master`` + ``target_ref=
        "master"`` ⇒ no `git switch` call; HEAD stays on the
        branch tip (not detached); returned SHA matches HEAD."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            url, repo = _make_fixture_repo(
                tmp_p, default_branch="master"
            )
            dest = tmp_p / "clone"
            # Spy on _git to count switch calls.
            real_git = P._git
            calls: list[list[str]] = []

            def _spy_git(*args, cwd=None, check=True):
                calls.append(list(args))
                return real_git(*args, cwd=cwd, check=check)

            with mock.patch("bin.harness.prepare._git",
                             side_effect=_spy_git):
                sha = P.clone_worktree(url, "master", dest)
            # No `switch` AND no `checkout` calls.
            for c in calls:
                self.assertNotIn(
                    "switch", c,
                    f"105: default-branch ref must NOT switch; "
                    f"saw {c}",
                )
                self.assertNotIn(
                    "checkout", c,
                    f"105: default-branch ref must NOT "
                    f"checkout; saw {c}",
                )
            # HEAD still on master (not detached).
            head_branch = _git(dest, "rev-parse",
                                "--abbrev-ref", "HEAD")
            self.assertEqual(head_branch, "master")
            # Returned SHA matches HEAD.
            head_sha = _git(dest, "rev-parse", "HEAD")
            self.assertEqual(sha, head_sha)

    def test_default_branch_main_skips_switch(self) -> None:
        """Works for any default branch name (not hardcoded to
        master) — the test is purely ``target_ref == current``."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            url, _ = _make_fixture_repo(
                tmp_p, default_branch="main"
            )
            dest = tmp_p / "clone"
            calls: list[list[str]] = []
            real_git = P._git

            def _spy_git(*args, cwd=None, check=True):
                calls.append(list(args))
                return real_git(*args, cwd=cwd, check=check)

            with mock.patch("bin.harness.prepare._git",
                             side_effect=_spy_git):
                P.clone_worktree(url, "main", dest)
            for c in calls:
                self.assertNotIn("switch", c)
                self.assertNotIn("checkout", c)


# ---------------------------------------------------------------------------
# Task A.2 — SHA ref ⇒ detached switch (gson-style case)
# ---------------------------------------------------------------------------


class ShaRefDetachedSwitchTests(unittest.TestCase):

    def test_sha_ref_lands_detached(self) -> None:
        """Pre-105 ``git switch <sha>`` would error without
        ``--detach``. The two-step (plain switch → --detach
        fallback) handles SHAs."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            url, repo = _make_fixture_repo(
                tmp_p, default_branch="main", extra_commits=2,
            )
            # The parent commit (not HEAD).
            parent_sha = _git(repo, "rev-parse", "HEAD~1")
            dest = tmp_p / "clone"
            sha = P.clone_worktree(url, parent_sha, dest)
            # Returned SHA equals the requested parent.
            self.assertEqual(sha, parent_sha)
            # HEAD is detached (no branch).
            head_branch = _git(dest, "rev-parse",
                                "--abbrev-ref", "HEAD")
            self.assertEqual(head_branch, "HEAD",
                              "SHA ref must produce a detached "
                              "HEAD (rev-parse --abbrev-ref HEAD "
                              "returns 'HEAD' when detached)")


# ---------------------------------------------------------------------------
# Task A.3 — non-default branch ⇒ plain switch
# ---------------------------------------------------------------------------


class NonDefaultBranchSwitchTests(unittest.TestCase):

    def test_non_default_branch_switches_cleanly(self) -> None:
        """A second branch at HEAD (default branch isn't its
        branch) ⇒ plain ``git switch`` (auto-tracks the local
        branch); HEAD lands on the second branch."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            url, _ = _make_fixture_repo(
                tmp_p, default_branch="master",
                extra_branches=["feature-branch"],
            )
            dest = tmp_p / "clone"
            P.clone_worktree(url, "feature-branch", dest)
            head_branch = _git(dest, "rev-parse",
                                "--abbrev-ref", "HEAD")
            self.assertEqual(head_branch, "feature-branch")


# ---------------------------------------------------------------------------
# Task A.4 — bad ref ⇒ PrepError preserved
# ---------------------------------------------------------------------------


class BadRefStillRaisesPrepErrorTests(unittest.TestCase):

    def test_unknown_ref_raises_prep_error_aborted_prep(
            self) -> None:
        """A ref that doesn't match anything ⇒ ``PrepError`` (the
        ``ABORTED_PREP`` path in plan-runner is preserved). The
        message says 'switch ... failed' (was 'checkout ...
        failed' pre-105)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            url, _ = _make_fixture_repo(
                tmp_p, default_branch="master",
            )
            dest = tmp_p / "clone"
            with self.assertRaises(P.PrepError) as ctx:
                P.clone_worktree(
                    url, "does-not-exist-anywhere", dest,
                )
            self.assertIn("switch", str(ctx.exception))
            self.assertIn("does-not-exist-anywhere",
                            str(ctx.exception))


# ---------------------------------------------------------------------------
# Task A.5 — falsy target_ref ⇒ no switch (existing contract)
# ---------------------------------------------------------------------------


class FalsyRefNoSwitchTests(unittest.TestCase):

    def test_none_target_ref_skips_switch(self) -> None:
        """``target_ref=None`` ⇒ no switch (existing contract;
        the 105 logic ``if target_ref:`` preserves it)."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            url, repo = _make_fixture_repo(
                tmp_p, default_branch="master",
            )
            dest = tmp_p / "clone"
            calls: list[list[str]] = []
            real_git = P._git

            def _spy_git(*args, cwd=None, check=True):
                calls.append(list(args))
                return real_git(*args, cwd=cwd, check=check)

            with mock.patch("bin.harness.prepare._git",
                             side_effect=_spy_git):
                P.clone_worktree(url, None, dest)
            for c in calls:
                self.assertNotIn("switch", c)
                self.assertNotIn("checkout", c)


if __name__ == "__main__":
    unittest.main()
