"""v1.5.7 191 FINDING-54 — git stash fallback safety note.

The `git stash && git apply ... && git checkout . && git stash
pop` fallback in `references/phase2_generation_guide.md` is a
legitimate recovery flow but discards working-tree state without
warning. The safety note prepended in 191 tells the operator
when it's safe to run and what to do if `git stash pop` conflicts.
"""
from __future__ import annotations

import pathlib
import re
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[2]
# v1.5.8 instruction 208: references/ moved into the plugin skill folder.
_SKILL_DIR = _REPO / "skills" / "quality-playbook"


class GitStashCautionTests(unittest.TestCase):

    def test_phase2_generation_guide_git_stash_has_caution(
            self) -> None:
        """The `git stash && git apply ...` fallback line in
        `references/phase2_generation_guide.md` MUST be
        immediately preceded by a **Caution:** paragraph
        warning about discarded working-tree state."""
        text = (
            _SKILL_DIR / "references" / "phase2_generation_guide.md"
        ).read_text(encoding="utf-8")
        # Find the fallback sentence + verify a **Caution:**
        # paragraph precedes it within a short window.
        m = re.search(
            r"\*\*Caution:\*\*[^\n]*?"
            r"(?:\n\n|\n)"
            r"If `git worktree` is unavailable.*?"
            r"git stash && git apply",
            text, re.DOTALL)
        self.assertIsNotNone(
            m, "FINDING-54 caution paragraph missing — the "
               "`git stash && git apply` fallback must be "
               "preceded by a **Caution:** paragraph warning "
               "about discarded working-tree state")

    def test_caution_paragraph_mentions_include_untracked(
            self) -> None:
        """The caution must specifically recommend `git stash
        --include-untracked` as the safer alternative when
        the operator is unsure."""
        text = (
            _SKILL_DIR / "references" / "phase2_generation_guide.md"
        ).read_text(encoding="utf-8")
        m = re.search(
            r"\*\*Caution:\*\*[^\n]*?"
            r"git stash --include-untracked",
            text, re.DOTALL)
        self.assertIsNotNone(
            m, "FINDING-54 caution should mention `git stash "
               "--include-untracked` as the safer alternative")

    def test_caution_warns_about_stash_pop_conflicts(
            self) -> None:
        """The caution must warn about `git stash pop`
        conflicts and tell the operator to resolve manually
        rather than rerun."""
        text = (
            _SKILL_DIR / "references" / "phase2_generation_guide.md"
        ).read_text(encoding="utf-8")
        # Look for both pieces in the caution paragraph
        m = re.search(
            r"\*\*Caution:\*\*([^\n]*?"
            r"stash pop[^\n]*?"
            r"conflicts[^\n]*?"
            r"do NOT rerun)",
            text, re.DOTALL | re.IGNORECASE)
        self.assertIsNotNone(
            m, "FINDING-54 caution should warn that `git "
               "stash pop` conflicts must be resolved manually "
               "and the sequence must NOT be rerun")


if __name__ == "__main__":
    unittest.main()
