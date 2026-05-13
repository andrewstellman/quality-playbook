"""v1.5.7 Phase 7: pin SKILL.md size below the achieved threshold.

Acceptance criteria from instruction 025: SKILL.md BPE token count
below 30K. Achieved at commit 7-pass-3: 26,162 BPE (cl100k_base).
This test pins below achieved + ~1500 token headroom (28,000) so a
future edit that re-bloats SKILL.md fails the test.

If a future SKILL.md edit legitimately grows the file (new
orchestration content), update the pin AND the no-orphaned-pointer
test below to match.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


SKILL_MD = Path(__file__).resolve().parents[2] / "SKILL.md"
REFERENCES_DIR = Path(__file__).resolve().parents[2] / "references"


class SkillMdSizeTests(unittest.TestCase):
    def test_skill_md_bpe_token_count_under_threshold(self) -> None:
        try:
            import tiktoken
        except ImportError:
            self.skipTest("tiktoken not installed")
        enc = tiktoken.get_encoding("cl100k_base")
        text = SKILL_MD.read_text(encoding="utf-8")
        token_count = len(enc.encode(text))
        # v1.5.7 Phase 7 trim achieved 26,162 BPE; pin below 28,000
        # so future edits that add ~1800 BPE worth of content still
        # pass (headroom for legitimate orchestration additions),
        # but a re-bloat to ~35K+ fails.
        self.assertLess(
            token_count, 28000,
            f"SKILL.md is {token_count} BPE tokens — exceeds the "
            f"v1.5.7 Phase 7 trim threshold (28000). If this growth "
            f"is intentional, update this test's pin AND re-check "
            f"the references/*.md tree for further trim opportunities."
        )


class SkillMdPointerTests(unittest.TestCase):
    """For each `See \\`references/<name>.md\\`` pointer in SKILL.md,
    assert the target file exists. Test bites if a future edit removes
    a referenced file without updating SKILL.md."""

    def test_all_skill_md_pointers_resolve(self) -> None:
        text = SKILL_MD.read_text(encoding="utf-8")
        # Match `See `references/X.md`` patterns (the v1.5.7 Phase 7
        # canonical pointer phrasing).
        pattern = re.compile(r"See `(references/[^`]+\.md)`")
        matches = pattern.findall(text)
        self.assertGreater(
            len(matches), 0,
            "SKILL.md should contain at least one `See references/X.md` "
            "pointer (v1.5.7 Phase 7 added Phase 1, 2, 6 pointers).",
        )
        repo_root = SKILL_MD.parent
        missing = [m for m in matches if not (repo_root / m).is_file()]
        self.assertEqual(
            missing, [],
            f"SKILL.md references files that don't exist: {missing}",
        )


class PhasePromptReferenceLoadTests(unittest.TestCase):
    """For each `phase_prompts/<N>.md` reference load (any references/
    file mentioned in the prompt body), assert the file exists."""

    def test_phase_prompts_reference_files_all_exist(self) -> None:
        # Match references/X.md only when it's the direct object of a
        # "read", "consult", or "see" directive — these are real
        # directive references the agent should be able to find. Bare
        # mentions in code-block examples or inline narrative (e.g.,
        # "references/forms.md:section-3" as an illustrative path) are
        # excluded.
        prompts_dir = SKILL_MD.parent / "phase_prompts"
        directive_pattern = re.compile(
            r"(?:read|consult|see|load)\s+`?(references/[\w_.-]+\.md)",
            re.IGNORECASE,
        )
        missing = []
        for prompt in sorted(prompts_dir.glob("phase*.md")):
            text = prompt.read_text(encoding="utf-8")
            for ref in directive_pattern.findall(text):
                target = SKILL_MD.parent / ref
                if not target.is_file():
                    missing.append(f"{prompt.name}: {ref}")
        self.assertEqual(
            missing, [],
            f"phase_prompts/*.md directive references that don't exist: "
            f"{missing}",
        )


if __name__ == "__main__":
    unittest.main()
