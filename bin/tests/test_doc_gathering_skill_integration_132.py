"""v1.5.7 instruction 132 (revised after Round-1 halt) — ship the
doc-gathering protocol + ground its TOOLKIT.md, and teach SKILL.md
how to gather docs.

Round 1 of 132 assumed `DOC_GATHERING_PROMPT.md` already shipped to
adopters. It did not — the install bundle is an explicit allowlist
(`install_skill._bundle_files`), and only `SKILL.md` shipped from the
root. The worker correctly halted. Andrew's revised design (Option 1
+ a structural move): move `DOC_GATHERING_PROMPT.md` into
`references/` (which auto-ships via the `references/*.md` glob) and
explicitly add `ai_context/TOOLKIT.md` to the allowlist (the
protocol's Step 0 option (c) reads it from disk in install mode).
SKILL.md gains a doc-gathering section pointing at the new location;
README.md links to it.

These tests pin the coupling so a future refactor can't silently
break it:
  * `references/DOC_GATHERING_PROMPT.md` ships (via the glob)
  * `ai_context/TOOLKIT.md` ships (via the new allowlist entry)
  * SKILL.md references the new path + carries the trigger language
  * README.md links to the new path
  * no stale bare-root `DOC_GATHERING_PROMPT.md` references remain in
    the adopter-facing docs

Mirrors the publish-safety bundle-test pattern (presence checks
against tracked files; no fixtures).
"""
from __future__ import annotations

import pathlib
import re
import sys
import unittest

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
# v1.5.8 instruction 208: install_skill.py canonical source moved to
# skills/quality-playbook/scripts/. Source root for _bundle_files()
# is the skill folder, not the repo root.
_SKILL_DIR = _REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook"
sys.path.insert(0, str(_SKILL_DIR / "scripts"))

from install_skill import _bundle_files  # noqa: E402


def _bundle():
    return list(_bundle_files(_SKILL_DIR))


def _read(rel: str) -> str:
    """Read a bundle-relative file. ``SKILL.md``/``references/...``/
    ``ai_context/TOOLKIT.md`` etc. now live under the skill folder;
    repo-root files (README.md) live at the repo root. Resolves via
    the skill folder first, falling back to the repo root."""
    p = _SKILL_DIR / rel
    if not p.is_file():
        p = _REPO_ROOT / rel
    return p.read_text(encoding="utf-8")


class DocGatheringBundleTests(unittest.TestCase):

    def test_doc_gathering_prompt_ships_via_references_glob(self) -> None:
        dests = {str(d) for _s, d in _bundle()}
        self.assertIn(
            "references/DOC_GATHERING_PROMPT.md", dests,
            "DOC_GATHERING_PROMPT.md must ship via the references/ "
            "glob after the 132 move")

    def test_toolkit_md_ships_in_bundle(self) -> None:
        dests = {str(d) for _s, d in _bundle()}
        self.assertIn(
            "ai_context/TOOLKIT.md", dests,
            "ai_context/TOOLKIT.md must ship (132 allowlist entry) so "
            "the doc-gathering protocol's Step 0 option (c) resolves "
            "in install mode")

    def test_old_root_path_not_in_bundle(self) -> None:
        # The file moved; the bare root path must no longer be a
        # bundle destination.
        dests = {str(d) for _s, d in _bundle()}
        self.assertNotIn("DOC_GATHERING_PROMPT.md", dests)


class SkillMdCouplingTests(unittest.TestCase):

    def test_skill_md_references_doc_gathering_prompt(self) -> None:
        # Mutation-bite: drop the section or change the path ⇒ fails.
        self.assertIn(
            "references/DOC_GATHERING_PROMPT.md", _read("SKILL.md"),
            "SKILL.md must point at the new references/ path")

    def test_skill_md_doc_gathering_section_names_trigger_language(
            self) -> None:
        # The trigger language is load-bearing — without it an AI tool
        # won't connect a doc-gathering ask to this section.
        skill = _read("SKILL.md").lower()
        triggers = (
            "gather background documentation",
            "prepare `reference_docs/`",
            "doc gathering",
            "gather docs",
        )
        self.assertTrue(
            any(t.lower() in skill for t in triggers),
            f"SKILL.md doc-gathering section must name at least one "
            f"trigger phrase from {triggers}")


class ReadmeCouplingTests(unittest.TestCase):

    def test_readme_links_to_doc_gathering_prompt(self) -> None:
        self.assertIn(
            "references/DOC_GATHERING_PROMPT.md", _read("README.md"),
            "README.md must link to the new references/ path")


class NoStaleRootPathTests(unittest.TestCase):
    """No adopter-facing doc may reference the OLD bare-root
    `DOC_GATHERING_PROMPT.md` (i.e. the literal string NOT preceded by
    `references/`). Catches stale-reference regressions after the
    132 move."""

    # A bare reference = "DOC_GATHERING_PROMPT.md" not immediately
    # preceded by "references/".
    _BARE = re.compile(r"(?<!references/)DOC_GATHERING_PROMPT\.md")

    def test_no_bare_root_reference_in_adopter_docs(self) -> None:
        # v1.5.8 instruction 208: bundled adopter-facing docs (SKILL.md,
        # ai_context/TOOLKIT.md) live under the skill folder; README.md
        # stays at the repo root.
        paths_to_check = (
            _SKILL_DIR / "SKILL.md",
            _REPO_ROOT / "README.md",
            _SKILL_DIR / "ai_context" / "TOOLKIT.md",
        )
        for path in paths_to_check:
            rel = path.name if path.parent in (_REPO_ROOT, _SKILL_DIR) else path.parent.name + "/" + path.name
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            bare = self._BARE.findall(text)
            self.assertEqual(
                bare, [],
                f"{rel} still has {len(bare)} bare-root "
                f"DOC_GATHERING_PROMPT.md reference(s) — should be "
                f"references/DOC_GATHERING_PROMPT.md after the 132 move")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
