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
    contract on the agent side.

    v1.5.6 fix-up 072 expanded the contract from a single ASK rule
    to a three-tier priority order: (a) operator-told,
    (b) agent self-identifies with transparency, (c) ASK the operator
    if neither (a) nor (b) applies. The Cursor install test on
    2026-05-08 surfaced that agents do (and should) self-identify
    when they can confidently identify themselves as the tool that
    will use the project — forcing them to ASK in that case is
    friction without value, but they must be transparent about the
    inference so the operator can correct.

    These tests pin both the asks-not-guesses contract surface (068)
    and the three-tier priority-order contract surface (072), so
    silent reversion is caught at test time.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.agents_md = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")

    def test_agents_md_teaches_ask_on_detection_failure(self) -> None:
        """ASK remains a valid path (case (c) of the priority order)
        when neither operator-told nor self-identification applies."""
        self.assertIn(
            "ASK",
            self.agents_md,
            "AGENTS.md must teach the agent to ASK as case (c) of the "
            "three-tier priority order",
        )
        self.assertIn(
            "Which AI tool will use this project",
            self.agents_md,
            "AGENTS.md must include the canonical ask-the-operator wording",
        )

    def test_agents_md_forbids_blind_default(self) -> None:
        """Anti-guess contract surface. The post-072 contract phrases
        this across two anchors: 'Don't guess' (in case (c) of the
        priority order, applying when the agent doesn't know) plus
        'Do NOT pick a default tool blindly' (in Step 4 detection-failure
        recovery). At least one must be present."""
        forbids_guessing = (
            "Don't guess" in self.agents_md
            or "Do NOT guess" in self.agents_md
            or "Do NOT pick a default" in self.agents_md
        )
        self.assertTrue(
            forbids_guessing,
            "AGENTS.md must explicitly forbid guessing the AI tool "
            "(via 'Don't guess' / 'Do NOT guess' / 'Do NOT pick a default')",
        )

    def test_agents_md_does_not_relabel_ai_tool_as_fallback(self) -> None:
        """--ai-tool is the canonical first-attempt invocation when
        the agent knows the tool (which it should, after Step 1's
        priority order). The pre-068 wording ('v1.5.6+ recommended
        fallback when auto-detection fails') is no longer correct."""
        self.assertNotIn(
            "recommended fallback when auto-detection fails",
            self.agents_md,
            "AGENTS.md must not relabel --ai-tool as a fallback "
            "(the agent should pass --ai-tool directly once it "
            "knows the tool from Step 1's priority order, not "
            "'fall back' to it after auto-detection fails).",
        )

    def test_agents_md_three_tier_priority_order_present(self) -> None:
        """v1.5.6 fix-up 072: Step 1 establishes a three-tier priority
        order for determining the AI tool — (a) operator-told,
        (b) self-identified, (c) ASK. All three markers + the phrase
        'priority order' must be present so the contract is visible
        to any agent reading AGENTS.md."""
        self.assertIn(
            "priority order",
            self.agents_md,
            "AGENTS.md must use the phrase 'priority order' to anchor "
            "the three-tier tool-determination contract",
        )
        for marker in ("(a)", "(b)", "(c)"):
            self.assertIn(
                marker,
                self.agents_md,
                f"AGENTS.md must include priority-order marker {marker} "
                "in the install-procedure section",
            )

    def test_agents_md_blesses_self_identification(self) -> None:
        """v1.5.6 fix-up 072: when an agent can confidently identify
        itself as the AI tool that will use the project (e.g., Cursor
        agent in a Cursor session), passing `--ai-tool <self>`
        directly is a documented contract option, not drift. The
        prose must include either 'your own identity' or
        'identify yourself' as the anchor for case (b)."""
        identification_phrase = (
            "your own identity" in self.agents_md
            or "identify yourself" in self.agents_md
        )
        self.assertTrue(
            identification_phrase,
            "AGENTS.md must include 'your own identity' or "
            "'identify yourself' as the anchor for case (b) of "
            "the priority order — the agent self-identification path",
        )

    def test_agents_md_prefers_ai_tool_over_target(self) -> None:
        """v1.5.6 fix-up 072: --ai-tool is the canonical install
        invocation whenever the tool is known via Step 1's priority
        order. --target is reserved for operator-specified custom
        install locations, not as a detection-failure or
        self-identification fallback (the Cursor agent's drift on
        the 2026-05-08 install test)."""
        self.assertIn(
            "Prefer `--ai-tool` over `--target`",
            self.agents_md,
            "AGENTS.md must explicitly state the preference for "
            "--ai-tool over --target when the tool is known "
            "(prevents agents from defaulting to --target as an "
            "inference-fallback like the Cursor agent did on the "
            "2026-05-08 install test)",
        )


if __name__ == "__main__":
    unittest.main()
