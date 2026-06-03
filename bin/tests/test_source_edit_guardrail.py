"""Regression tests for the v1.5.7 Issue 1 fix (chi-surfaced):
the QPB source-edit guardrail must distinguish a legitimate
mid-run *committed* change from an autonomous *uncommitted* agent
patch.

The reproduction (chi-1.5.1 sonnet run): Phase 5 aborted with
"QPB source files modified during run:
['bin/tests/test_archive_preservation.py']" because instruction
042/043 commits (b76de20, 1cffa66) touched that file *during* the
long-running playbook. `_verify_qpb_source_unchanged` ran
`git diff --name-only <baseline_sha>` which diffs the baseline
commit against the *working tree*, so a fully-committed change
since baseline was flagged identically to an uncommitted agent
patch.

The function under test is `bin.run_playbook._verify_qpb_source_unchanged`
(NOT `run_state_lib.validate_no_source_edits`, which is a separate
git-status-based run-end guardrail — instruction 044 anticipated the
implementation differing from its pseudocode and directed adapting
the fix to the real function). The test names retain the
instruction's `validate_no_source_edits` phrasing because they pin
the *behavior* the instruction specified.

Mutation-test evidence (in-tree per
`ai_context/DEVELOPMENT_PROCESS.md:152-160`; each bite was
exercised during instruction 044 development with the stated
red→green outcome before the fix landed):

- `test_validate_no_source_edits_passes_for_committed_change`
  Mutation: delete the `if head_chk ... continue` HEAD-match filter
  in `_verify_qpb_source_unchanged` (reverts to the pre-fix
  baseline-vs-worktree behavior). Expected failure:
  `assertEqual(violations, [])` fires — the committed file is
  wrongly reported. Restoration: passes. Bite verified.
- `test_validate_no_source_edits_fires_for_unstaged_modification`
  Mutation: drop the `violations.append(f)` for dirty candidates.
  Expected failure: `assertIn("bin/sample.py", violations)` fires
  (empty list). Restoration: passes. Bite verified.
- `test_validate_no_source_edits_fires_for_new_untracked_file`
  Mutation: delete the `git ls-files --others --exclude-standard`
  block. Expected failure: `assertIn("bin/rogue.py", violations)`
  fires (untracked file undetected). Restoration: passes. Bite
  verified.
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bin import run_playbook


def _init_git(repo: Path) -> None:
    subprocess.run(
        ["git", "init"], cwd=repo, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)


def _commit(repo: Path, message: str) -> None:
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


class SourceEditGuardrailTests(unittest.TestCase):
    """Pins the v1.5.7 Issue 1 invariant: committed mid-run changes
    PASS; uncommitted modifications and new untracked source files
    FIRE the guardrail."""

    def _seed_repo(self, repo: Path) -> str:
        """Create a git repo with a tracked bin/ source file, commit
        it, and return the baseline SHA captured the way execute_run
        captures it."""
        _init_git(repo)
        _write(repo / "bin" / "sample.py", "# v1 baseline\n")
        _commit(repo, "baseline")
        baseline = run_playbook._qpb_source_baseline_sha(repo)
        self.assertIsInstance(baseline, str)
        return baseline  # type: ignore[return-value]

    def test_validate_no_source_edits_passes_for_committed_change(self) -> None:
        """A source file changed AND committed during the run window
        (the legitimate orchestrator-driven-commit case) must NOT be
        flagged. This is the chi-1.5.1 false positive."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            baseline = self._seed_repo(repo)

            # Mid-run: modify the source file AND commit it (a tracked
            # commit landing on the branch during the playbook).
            _write(repo / "bin" / "sample.py", "# v2 committed mid-run\n")
            _commit(repo, "authorized mid-run fix")

            violations = run_playbook._verify_qpb_source_unchanged(
                repo, baseline
            )
            self.assertEqual(
                violations, [],
                "a fully-committed mid-run source change must NOT be "
                "flagged as an autonomous patch (Issue 1 false positive)",
            )

    def test_validate_no_source_edits_fires_for_unstaged_modification(self) -> None:
        """An uncommitted (unstaged) modification to a tracked source
        file is the autonomous-agent-patch case — must fire."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            baseline = self._seed_repo(repo)

            # Mid-run: modify the source file WITHOUT committing.
            _write(repo / "bin" / "sample.py", "# unstaged agent patch\n")

            violations = run_playbook._verify_qpb_source_unchanged(
                repo, baseline
            )
            self.assertIn(
                "bin/sample.py", violations,
                "an uncommitted source modification must fire the "
                "guardrail",
            )

    def test_validate_no_source_edits_fires_for_new_untracked_file(self) -> None:
        """A brand-new untracked file under a source path is the
        autonomous-agent-creates-source case — conservative default:
        must fire (git diff never surfaces untracked paths, so the
        fix detects them explicitly)."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            baseline = self._seed_repo(repo)

            # Mid-run: agent drops a brand-new untracked source file.
            _write(repo / "bin" / "rogue.py", "# autonomous new source\n")

            violations = run_playbook._verify_qpb_source_unchanged(
                repo, baseline
            )
            self.assertIn(
                "bin/rogue.py", violations,
                "a new untracked source file must fire the guardrail "
                "(conservative default)",
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
