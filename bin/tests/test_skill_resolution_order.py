"""Tests for canonical skill-resolution-order consistency across surfaces.

Regression coverage for BUG-004 (v1.5.4 self-audit): the Claude agent
file listed `.github/skills/quality-playbook/SKILL.md` BEFORE
`.github/skills/SKILL.md`, while the canonical order in
`bin/run_playbook.py:SKILL_FALLBACK_GUIDE` puts the flat layout first.
A user with both layouts installed could have resolved the wrong skill
version.

The canonical order is:
    1. SKILL.md
    2. .claude/skills/quality-playbook/SKILL.md
    3. .github/skills/SKILL.md
    4. .github/skills/quality-playbook/SKILL.md

Three sites must agree:
    - bin/run_playbook.py SKILL_FALLBACK_GUIDE constant
    - agents/quality-playbook.agent.md install-locations list
    - agents/quality-playbook-claude.agent.md install-locations list
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent

CANONICAL_ORDER = [
    "SKILL.md",
    ".claude/skills/quality-playbook/SKILL.md",
    ".github/skills/SKILL.md",
    ".github/skills/quality-playbook/SKILL.md",
]


class SkillResolutionOrderTests(unittest.TestCase):
    """All surfaces that document skill-resolution order must list the
    four locations in the canonical order (BUG-004)."""

    def test_run_playbook_skill_fallback_guide_lists_canonical_order(self) -> None:
        """bin/run_playbook.py:SKILL_FALLBACK_GUIDE is the source of
        truth — every documented location appears in canonical order."""
        from bin import run_playbook

        guide = run_playbook.SKILL_FALLBACK_GUIDE
        positions = [(loc, guide.find(loc)) for loc in CANONICAL_ORDER]
        for loc, pos in positions:
            self.assertGreaterEqual(
                pos, 0, f"{loc!r} not present in SKILL_FALLBACK_GUIDE"
            )
        ordered = sorted(positions, key=lambda lp: lp[1])
        self.assertEqual(
            [lp[0] for lp in ordered],
            CANONICAL_ORDER,
            "SKILL_FALLBACK_GUIDE locations are not in canonical order",
        )

    def test_claude_agent_install_locations_match_canonical(self) -> None:
        """agents/quality-playbook-claude.agent.md must list the four
        locations as numbered items in canonical order. Regression for
        BUG-004 (positions 3 and 4 were swapped in v1.5.4)."""
        order = self._read_numbered_skill_list(
            REPO_ROOT / "agents" / "quality-playbook-claude.agent.md"
        )
        self.assertEqual(
            order,
            CANONICAL_ORDER,
            "agents/quality-playbook-claude.agent.md install-location order "
            "diverges from bin/run_playbook.py SKILL_FALLBACK_GUIDE — see "
            "BUG-004.",
        )

    def test_general_agent_install_locations_match_canonical(self) -> None:
        """agents/quality-playbook.agent.md was already correct in v1.5.4
        but is checked here so any future drift in EITHER agent file is
        caught immediately."""
        order = self._read_numbered_skill_list(
            REPO_ROOT / "agents" / "quality-playbook.agent.md"
        )
        self.assertEqual(
            order,
            CANONICAL_ORDER,
            "agents/quality-playbook.agent.md install-location order "
            "diverges from canonical.",
        )

    def _read_numbered_skill_list(self, path: Path) -> list[str]:
        """Parse the first numbered list of SKILL.md install paths from a
        markdown file. Tolerant of trailing parenthetical annotations
        like '(Copilot, flat layout)'."""
        text = path.read_text(encoding="utf-8")
        pattern = re.compile(
            r"^\s*([1-4])\.\s+`([^`]*SKILL\.md)`",
            re.MULTILINE,
        )
        matches = pattern.findall(text)
        # Take the first contiguous 1-2-3-4 sequence.
        result: list[str] = []
        expected_num = 1
        for num_str, loc in matches:
            num = int(num_str)
            if num == expected_num:
                result.append(loc)
                expected_num += 1
                if expected_num > 4:
                    break
            elif num == 1:
                # Restart sequence
                result = [loc]
                expected_num = 2
        return result


if __name__ == "__main__":
    unittest.main()
