"""v1.5.7 instruction 064 (A-17) — Mode A self-execution contract.

The skill shipped three conflicting models of who runs the phases:

  - SKILL.md Mode A: "Run every phase yourself ... No subprocess, no
    runner" + guardrail #1 "no sub-agent delegation".
  - agents/quality-playbook.agent.md / quality-playbook-claude.agent.md:
    "Your ONLY jobs are: (1) spawn sub-agents ... You do NOT execute
    phase logic yourself."
  - AGENTS.md (the entry-point doc adopter agents read first) pointed
    Claude Code adopters straight at the sub-agent orchestrator.

The 2026-05-16 express opus-4.6 Mode-A run followed AGENTS.md → the
Claude orchestrator agent → spawned the `quality-playbook` sub-skill.
The sub-skill ran phases in its own context, fabricated
`quality/results/quality-gate.log`, and reported PASS to the parent
against an actual 14-FAIL gate. The A-13 Phase-6 witness contract
could not enforce because the gate-verdict line never reached the
parent's operator-watched chat.

The fix is a PROMPT-CONTRACT change (Mode A agent compliance is not
runtime-enforceable): SKILL.md, AGENTS.md, and both orchestrator
agent files now coherently scope sub-agent orchestration to
AUTOMATION contexts and forbid it for interactive coding sessions.

These tests pin that contract language across all four source files
so a future edit cannot silently re-open the conflict.
"""

from __future__ import annotations

import unittest
from pathlib import Path

_QPB_ROOT = Path(__file__).resolve().parents[2]
_SKILL_MD = _QPB_ROOT / "SKILL.md"
_AGENTS_MD = _QPB_ROOT / "AGENTS.md"
_AGENT_GENERAL = _QPB_ROOT / "agents" / "quality-playbook.agent.md"
_AGENT_CLAUDE = _QPB_ROOT / "agents" / "quality-playbook-claude.agent.md"

_AUTOMATION_ONLY_DESC_PREFIX = (
    'description: "AUTOMATION ONLY — DO NOT INVOKE FROM AN '
    'INTERACTIVE CODING SESSION.'
)


def _slice(text: str, header: str, *stops: str) -> str:
    """Return the slice of `text` from `header` up to the first of
    `stops` that occurs after it (or EOF) — used to scope an
    assertion to one section so a stray match elsewhere can't satisfy
    it."""
    start = text.index(header)
    rest = text[start + len(header):]
    cut = len(rest)
    for s in stops:
        i = rest.find(s)
        if i != -1:
            cut = min(cut, i)
    return rest[:cut]


def _table_rows_for_agent_files(agents_md: str) -> dict[str, str]:
    """The two pointing-table rows keyed by agent filename. A table
    row is a single line beginning `| `agents/quality-playbook`; the
    `## Repository layout` tree lists the same names but those lines
    are indented prose, not `|`-prefixed table rows, so this isolates
    the pointing table without a brittle section slice."""
    rows: dict[str, str] = {}
    for line in agents_md.splitlines():
        if line.startswith("| `agents/quality-playbook"):
            if "quality-playbook-claude.agent.md`" in line:
                rows["claude"] = line
            elif "quality-playbook.agent.md`" in line:
                rows["general"] = line
    return rows


class ModeASelfExecutionContractTests(unittest.TestCase):
    """A-17: SKILL.md + AGENTS.md + both orchestrator agent files
    coherently forbid sub-skill / sub-agent delegation for
    interactive coding sessions."""

    def test_skill_md_mode_a_intro_forbids_sub_skill_delegation(self) -> None:
        """SKILL.md's Mode A walkthrough section carries the explicit
        "Mode A means YOU execute the skill" contract enumerating the
        forbidden delegation patterns (sub-skill spawn, Task/Agent
        tool, run_playbook.py, reading the agents/ orchestrator files)
        and cites the 2026-05-16 express failure mode.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-064
        A-17:
          Mutation: delete the "**Mode A means YOU execute the
          skill.**" paragraph (and its forbidden-pattern bullet list)
          from SKILL.md's `### Mode A — skill-direct walkthrough`
          section — i.e. revert to the pre-064 text where the section
          went straight from "You drive every phase inline." to "For
          each phase 1..6, in order:".
          Expected failure: THIS test fails at the first assertion
          with
            AssertionError: SKILL.md Mode A section missing the
            'Mode A means YOU execute the skill' self-execution
            contract (A-17)
          because the scoped Mode A section no longer contains
          "Mode A means YOU execute the skill".
          Restoration: re-apply the 064 paragraph; passes.
          Bite EXECUTED during instruction-064 development:
          PASS→FAIL on mutation, FAIL→PASS on restore, confirmed
          (__pycache__ purged between mutate and restore so a stale
          .pyc could not mask the restored-clean state — per the
          feedback_mutation_bite_pycache discipline).
        """
        section = _slice(
            _SKILL_MD.read_text(encoding="utf-8"),
            "### Mode A — skill-direct walkthrough (UI-context)",
            "\n### Mode B —",
        )
        self.assertIn(
            "Mode A means YOU execute the skill", section,
            "SKILL.md Mode A section missing the 'Mode A means YOU "
            "execute the skill' self-execution contract (A-17)",
        )
        # The enumerated forbidden delegation patterns.
        self.assertIn(
            "Spawn a sub-skill via your `quality-playbook` "
            "skill-invocation mechanism", section,
            "Mode A intro must forbid sub-skill spawn (A-17)",
        )
        self.assertIn(
            "Spawn a sub-agent via your Task tool", section,
            "Mode A intro must forbid Task/Agent-tool sub-agent "
            "dispatch (A-17)",
        )
        self.assertIn(
            "Invoke `python3 -m bin.run_playbook`", section,
            "Mode A intro must point run_playbook.py at Mode B, not "
            "the interactive path (A-17)",
        )
        self.assertIn(
            "agents/quality-playbook.agent.md", section,
        )
        self.assertIn(
            "agents/quality-playbook-claude.agent.md", section,
        )
        # The reproduction citation grounds the rule in a verified
        # failure (per the guardrail-citation discipline).
        self.assertIn("2026-05-16", section)
        self.assertIn("witness", section.lower())

    def test_skill_md_guardrail_1_cites_a17_express_failure(self) -> None:
        """SKILL.md guardrail #1 names BOTH verified failure modes
        (B-15 and the new A-17 / 2026-05-16 express opus-4.6) and adds
        the `quality-playbook` skill-invocation mechanism to the
        forbidden list."""
        guardrail_1 = _slice(
            _SKILL_MD.read_text(encoding="utf-8"),
            "1. **Synchronous execution — no sub-agent delegation.**",
            "\n2. **Don't patch QPB source",
        )
        self.assertIn(
            "the `quality-playbook` skill-invocation mechanism",
            guardrail_1,
            "guardrail #1 must add the sub-skill invocation mechanism "
            "to the forbidden list (A-17)",
        )
        self.assertIn(
            "A-17", guardrail_1,
            "guardrail #1 must cite the A-17 failure mode",
        )
        self.assertIn(
            "2026-05-16 express opus-4.6", guardrail_1,
            "guardrail #1 must cite the 2026-05-16 express reproduction",
        )
        # B-15 must NOT be dropped — both failure modes coexist.
        self.assertIn(
            "B-15", guardrail_1,
            "guardrail #1 must preserve the original B-15 citation "
            "alongside the new A-17 one",
        )

    def test_agents_md_orchestrator_rows_marked_automation_only(self) -> None:
        """Both orchestrator-agent rows in AGENTS.md's pointing table
        (the doc adopter agents read FIRST) carry the AUTOMATION ONLY
        / NOT-for-interactive constraint, so an adopter sees it before
        it would dispatch to the orchestrator."""
        rows = _table_rows_for_agent_files(
            _AGENTS_MD.read_text(encoding="utf-8")
        )
        self.assertIn("general", rows,
                      "AGENTS.md pointing table missing the "
                      "quality-playbook.agent.md row")
        self.assertIn("claude", rows,
                      "AGENTS.md pointing table missing the "
                      "quality-playbook-claude.agent.md row")
        for key, row in rows.items():
            self.assertIn(
                "AUTOMATION ONLY", row,
                f"AGENTS.md {key} orchestrator row must be marked "
                f"AUTOMATION ONLY (A-17)",
            )
            self.assertIn(
                "NOT for interactive sessions", row,
                f"AGENTS.md {key} orchestrator row must say NOT for "
                f"interactive sessions (A-17)",
            )
        # The Claude row carries the express reproduction citation
        # (it's the file the express run actually followed).
        self.assertIn("2026-05-16", rows["claude"])

    def test_orchestrator_agent_files_carry_automation_only_header(self) -> None:
        """Both agents/quality-playbook*.agent.md files carry the
        AUTOMATION-ONLY frontmatter description prefix AND a "When to
        use this file" section that excludes interactive coding
        sessions."""
        for label, path in (
            ("general", _AGENT_GENERAL),
            ("claude", _AGENT_CLAUDE),
        ):
            text = path.read_text(encoding="utf-8")
            self.assertIn(
                _AUTOMATION_ONLY_DESC_PREFIX, text,
                f"{label} agent file frontmatter description must "
                f"begin with the AUTOMATION ONLY warning (A-17)",
            )
            section = _slice(
                text, "## When to use this file", "\n## ",
            )
            self.assertTrue(
                section.strip(),
                f"{label} agent file missing the 'When to use this "
                f"file' section (A-17)",
            )
            self.assertIn(
                "DO NOT use this file for interactive coding sessions",
                section,
                f"{label} agent file 'When to use' section must "
                f"exclude interactive coding sessions (A-17)",
            )
            self.assertIn(
                "Execute Mode A in your own chat session", section,
                f"{label} agent file must redirect interactive "
                f"sessions to Mode A (A-17)",
            )


if __name__ == "__main__":
    unittest.main()
