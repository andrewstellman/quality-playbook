"""AGENTS.md install-procedure prose-contract tests.

The AGENTS.md file is the canonical contract between the QPB skill
and any AI coding agent driving the install on an operator's behalf.
Specific phrasings in the install-procedure section are load-bearing
— silent reversion to a different contract (e.g., "fall back to a
default tool" instead of "ask the operator") would degrade the
adopter experience without tripping any code-side test.

This module pins the prose surfaces that matter, so an unintentional
edit during a future cleanup is caught at test time.
"""

from __future__ import annotations

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class AgentsMdAsksNotGuessesTests(unittest.TestCase):
    """v1.5.6 fix-up 068: the AGENTS.md install-procedure section
    must teach the agent to ASK the operator when it doesn't know
    which AI tool, not guess. The README install-failure prose was
    simplified to a single sentence ("If auto-detection can't find
    a marker, your AI agent will ask which tool you're using and
    proceed.") in commit a2ffe71; AGENTS.md must keep the same
    contract on the agent side. These tests pin the contract surface
    so silent reversion to "fall back to --ai-tool with whatever the
    agent thinks" is caught at test time.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.agents_md = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    def test_agents_md_teaches_ask_on_detection_failure(self) -> None:
        """The install-procedure section must teach the agent to ASK
        the operator when it doesn't know which AI tool, not guess."""
        self.assertIn(
            "ASK",
            self.agents_md,
            "AGENTS.md must teach the agent to ASK on detection failure",
        )
        self.assertIn(
            "Which AI tool will use this project",
            self.agents_md,
            "AGENTS.md must include the canonical ask-the-operator wording",
        )

    def test_agents_md_forbids_guessing(self) -> None:
        """Anti-guess contract surface — explicit 'Do NOT guess' line
        must appear in the install-procedure section."""
        self.assertIn(
            "Do NOT guess",
            self.agents_md,
            "AGENTS.md must explicitly forbid guessing the AI tool",
        )

    def test_agents_md_does_not_relabel_ai_tool_as_fallback(self) -> None:
        """--ai-tool is the canonical first-attempt invocation when
        the agent knows the tool (which it should, after Step 1).
        The pre-068 wording ('v1.5.6+ recommended fallback when
        auto-detection fails') is no longer correct."""
        self.assertNotIn(
            "recommended fallback when auto-detection fails",
            self.agents_md,
            "AGENTS.md must not relabel --ai-tool as a fallback "
            "(the agent should pass --ai-tool directly once it "
            "knows the tool from Step 1's ask, not 'fall back' "
            "to it after auto-detection fails).",
        )


if __name__ == "__main__":
    unittest.main()
