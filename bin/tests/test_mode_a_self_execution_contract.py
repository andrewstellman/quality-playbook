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
# v1.5.8 instruction 208: SKILL.md + agents/ moved into the plugin skill folder.
_SKILL_DIR = _QPB_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook"
_SKILL_MD = _SKILL_DIR / "SKILL.md"
_AGENTS_MD = _QPB_ROOT / "AGENTS.md"
_AGENT_GENERAL = _SKILL_DIR / "agents" / "quality-playbook.agent.md"
_AGENT_CLAUDE = _SKILL_DIR / "agents" / "quality-playbook-claude.agent.md"

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
        # The failure mode is described in prose (the SKILL.md trim
        # of 2026-06-04 / commit 45d4520 removed the "2026-05-16"
        # date citation as unactionable; the "witness" anchor still
        # pins the rule's mechanism — Phase 6 witness contract).
        self.assertIn("witness", section.lower())

    def test_skill_md_guardrail_1_cites_a17_express_failure(self) -> None:
        """SKILL.md guardrail #1 names BOTH verified failure-mode
        mechanisms (the delegated-agent-silent-death pattern and the
        sub-skill-fabricated-PASS pattern) and adds the
        `quality-playbook` skill-invocation mechanism to the
        forbidden list.

        v1.5.7 192: trim 45d4520 removed the A-17/B-15 instruction
        codes and the dated `2026-05-16 express opus-4.6` citation
        as unactionable references — the running agent cannot look
        up what 'A-17' means and the date doesn't change the rule.
        Updated to assert on the surviving mechanism descriptions
        instead of the removed codes.
        """
        guardrail_1 = _slice(
            _SKILL_MD.read_text(encoding="utf-8"),
            "1. **Synchronous execution — no sub-agent delegation.**",
            "\n2. **Don't patch QPB source",
        )
        self.assertIn(
            "the `quality-playbook` skill-invocation mechanism",
            guardrail_1,
            "guardrail #1 must add the sub-skill invocation mechanism "
            "to the forbidden list",
        )
        # Failure mode (a) — the delegated-agent silent-death pattern.
        self.assertIn(
            "phases 2", guardrail_1,
            "guardrail #1 must describe the delegated-agent "
            "silent-death failure mode (phases 2-6 die in a delegated "
            "agent)",
        )
        # Failure mode (b) — the sub-skill PASS-fabrication pattern.
        self.assertIn(
            "fabricates", guardrail_1,
            "guardrail #1 must describe the sub-skill PASS-fabrication "
            "failure mode (sub-skill fabricates gate log)",
        )
        # The Phase 6 verification exception (the principled carve-
        # out) must be present in the same guardrail.
        self.assertIn(
            "Phase 6 verification", guardrail_1,
            "guardrail #1 must carry the Phase 6 verification "
            "exception (mandatory sub-agent for verification, "
            "forbidden for execution)",
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


    def test_readme_step_4_claude_code_uses_interactive_pattern(self) -> None:
        """v1.5.7 instruction 067 F1 (closing 066 SA1), updated by
        instruction 073 Item-3 (A-18 re-scoped): README Step 4's
        Claude Code subsection must use the interactive
        read-the-skill pattern, NOT `claude --agent
        agents/quality-playbook.agent.md` as the PRIMARY invocation
        (the orchestrator-agent path is AUTOMATION ONLY per 064 — it
        may appear ONLY in the explicit automation parenthetical).
        073 Item-3 further mandates the prompt be INSTALL-FIRST
        ("install … then read the installed SKILL.md and run the
        playbook"), so the literal pre-073 "Read SKILL.md" string
        was superseded by "read the installed SKILL.md".

        v1.5.7 089q Task 3 reconciliation: the redundant "read the
        installed SKILL.md" clause was dropped — the agent auto-
        discovers the installed skill, so telling it to "read" the
        file read as if the operator opens it. The install-first
        contract is UNCHANGED (the prompt still runs the Phase 0
        validator and blocks until `event=validation_complete
        status=ok`); only the redundant read-the-file imperative
        was removed, and the prompt now says the agent
        "auto-discovers the installed skill". The 067 guarantees
        (no orchestrator-agent primary; automation parenthetical
        retained) are unchanged and still pinned below. Pin
        updated in-commit per the 067 precedent for
        instruction-directed prompt changes (the contract, not the
        literal string, is what's load-bearing).
        """
        readme = (_QPB_ROOT / "README.md").read_text(encoding="utf-8")
        step4 = _slice(readme, "### Step 4: Run the playbook",
                        "\n### ", "\n## ")
        cc = _slice(step4, "**Claude Code:**", "\n**")
        # Install-first interactive pattern present (073 A-18 +
        # 089q): the prompt routes through the Phase 0 validator
        # and references the installed skill the agent auto-
        # discovers (089q dropped the redundant "read the
        # installed SKILL.md" imperative — the install-first
        # contract holds via the validator gate, not a
        # read-the-file instruction).
        self.assertIn(
            "install validator", cc,
            "README Step 4 Claude Code subsection must direct the "
            "agent through the Phase 0 install validator "
            "(install-first interactive pattern — 067 F1 / 066 "
            "SA1 / 073 Item-3 A-18 / 089q)",
        )
        self.assertIn(
            "installed skill", cc,
            "README Step 4 Claude Code subsection must reference "
            "the INSTALLED skill the agent runs against (089q: "
            "'the agent auto-discovers the installed skill')",
        )
        # The orchestrator-agent path must NOT be the primary
        # instruction — only allowed inside the automation
        # parenthetical that starts with "(For automated batch".
        split = cc.split("(For automated batch invocation", 1)
        primary = split[0]
        self.assertNotIn(
            "--agent agents/quality-playbook", primary,
            "README Step 4 Claude Code PRIMARY instruction still "
            "routes interactive sessions into the AUTOMATION-ONLY "
            "orchestrator agent (the exact A-17 path 064 forbids) — "
            "066 SA1 finding must stay closed",
        )
        # The automation parenthetical itself is retained (the
        # automation path has legitimate use — reframed, not removed).
        self.assertEqual(
            len(split), 2,
            "the automation-only parenthetical (orchestrator-agent "
            "path for headless/CI) must be retained, not deleted "
            "(067: reframe, not removal)",
        )


class ModeAInstallStepContractTests(unittest.TestCase):
    """v1.5.7 instruction 072/073 A-18 (re-scoped): Mode A's
    MANDATORY Phase-0 install step. SKILL.md carries a tight
    pointer (size-ceiling constrained); AGENTS.md "Mode A entry
    sequence" is the canonical full protocol; README launch prompts
    include the install step. The 2026-05-17 httpx run skipped
    install_skill entirely → validators/gate unreachable."""

    def test_skill_md_mode_a_has_phase_0_validator_step(self) -> None:
        """SKILL.md Mode A intro carries the tight Phase-0 pointer.
        v1.5.7 instruction 078 (launch-prompt collapse, addendum r3
        §3.5) makes the **validator** the single Phase-0 entry point
        — the pointer now names `qpb_validate` + the
        `event=validation_complete status=ok` gate instead of the raw
        `install_skill` command (the validator's
        `event=remediation_suggestion` emits the platform-correct
        install when needed; 077b F2). The load-bearing CONTRACT is
        unchanged and still pinned: a MANDATORY Phase-0 first action +
        the AGENTS.md "Mode A entry sequence" anchor (+ the httpx
        failure-origin citation, pinned by the sibling test). Only
        the mechanism identity shifts install_skill→qpb_validate,
        which is the entire deliberate point of 078; per
        instruction-078 Task 4.2 the assertion is updated to track
        the new canonical form.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-078 —
        BITE EXECUTED during instruction-078 development:
          Mutation: in SKILL.md:77 change
          `python3 bin/qpb_validate.py <target-repo>` to
          `python3 bin/OTHER.py <target-repo>` (remove the
          `qpb_validate` token from the Phase-0 pointer).
          Observed failure (purged __pycache__ first):
            FAIL: test_skill_md_mode_a_has_phase_0_validator_step
            AssertionError: 'qpb_validate' not found in '<the scoped
            ### Mode A — skill-direct walkthrough slice, now with
            `python3 bin/OTHER.py <target-repo>` in the Phase-0
            pointer>' : the Phase-0 pointer must name the
            qpb_validate entry point (078 §3.5 launch-prompt
            collapse)
          Restoration: token restored; PASS again. rp + SKILL.md
          byte-restored from pristine snapshot; SKILL.md re-
          confirmed at 28,976 BPE (< 29,000) post-restore.
        """
        mode_a = _slice(
            _SKILL_MD.read_text(encoding="utf-8"),
            "### Mode A — skill-direct walkthrough (UI-context)",
            "\n### Mode B —",
        )
        # v1.5.7 191 FINDING-52: "Phase 0" renamed to "Phase 0 entry
        # contract" so the seed-loading and install-validator passes
        # don't share the bare "Phase 0" name.
        self.assertIn(
            "Phase 0 entry contract (MANDATORY first action)", mode_a,
            "SKILL.md Mode A intro must carry the MANDATORY Phase-0 "
            "entry contract pointer",
        )
        self.assertIn(
            "qpb_validate", mode_a,
            "the Phase-0 pointer must name the qpb_validate entry "
            "point (078 §3.5 launch-prompt collapse)",
        )
        self.assertIn(
            "event=validation_complete status=ok", mode_a,
            "the Phase-0 pointer must carry the do-not-proceed-until "
            "status=ok gate (078 §3.5)",
        )
        self.assertIn("AGENTS.md", mode_a)
        self.assertIn(
            '"Mode A entry sequence"', mode_a,
            "the tight SKILL.md pointer must reference the canonical "
            "AGENTS.md 'Mode A entry sequence' full protocol (073 "
            "A-18 re-scope; 078 retains the anchor)",
        )

    def test_skill_md_mode_a_cites_httpx_failure_mode(self) -> None:
        """The Phase-0 pointer must describe the skipped-install
        failure mode that motivates the MANDATORY-first-action rule.

        v1.5.7 192: trim 45d4520 removed the `2026-05-17 httpx`
        date-citation as unactionable; the failure mode itself is
        still described in the surrounding prose
        ("skipped/fabricated validation ... documented adopter
        failure modes"). Updated to assert on the failure-mode
        description rather than the dropped date.
        """
        mode_a = _slice(
            _SKILL_MD.read_text(encoding="utf-8"),
            "### Mode A — skill-direct walkthrough (UI-context)",
            "\n### Mode B —",
        )
        self.assertIn(
            "skipped/fabricated validation", mode_a,
            "the Phase-0 pointer must cite the skipped/fabricated "
            "validation failure mode as rationale",
        )
        self.assertIn(
            "documented adopter failure modes", mode_a,
            "the Phase-0 pointer must label the failure modes as "
            "documented (not theoretical)",
        )

    def test_agents_md_has_mode_a_entry_sequence_full_protocol(self) -> None:
        """AGENTS.md carries the canonical full 'Mode A entry
        sequence' section (the 4-step list + install_skill
        invocation pattern + the httpx citation) — the home of the
        A-18 install protocol after the 073 re-scope."""
        agents = _AGENTS_MD.read_text(encoding="utf-8")
        self.assertIn(
            "## Mode A entry sequence (interactive coding sessions)",
            agents,
            "AGENTS.md must carry the 'Mode A entry sequence' "
            "section (073 A-18 re-scope — canonical install home)",
        )
        seq = _slice(
            agents,
            "## Mode A entry sequence (interactive coding sessions)",
            "\n## ",
        )
        self.assertIn("python3 -m bin.install_skill", seq,
                      "entry sequence must carry the install_skill "
                      "invocation pattern (A-18)")
        self.assertIn("2026-05-17 httpx", seq,
                      "entry sequence must cite the httpx failure (A-18)")
        # The 4-step ordered list (read source → install → cd/read
        # installed → execute) must be present.
        for marker in ("1.", "2.", "3.", "4."):
            self.assertIn(marker, seq)
        self.assertIn("install the skill into your target",
                      seq.lower())

    def test_readme_claude_code_subsection_has_validator_step_in_prompt(self) -> None:
        """README Step 4's Claude Code launch prompt is validator-
        first (v1.5.7 instruction 078, addendum r3 §3.5): it invokes
        `qpb_validate.py`, carries the do-not-proceed-until
        `event=validation_complete status=ok` gate, and still
        references the canonical `install_skill` command as the
        validator's remediation. Same load-bearing contract as the
        pre-078 pin (the CC launch prompt names the deterministic
        MANDATORY Phase-0 action that closes the 2026-05-17 httpx
        bad-launch-prompt root cause) — only the mechanism shifts to
        the validator, per instruction-078 Task 4.2."""
        readme = (_QPB_ROOT / "README.md").read_text(encoding="utf-8")
        step4 = _slice(readme, "### Step 4: Run the playbook",
                        "\n### ", "\n## ")
        cc = _slice(step4, "**Claude Code:**", "\n**")
        self.assertIn(
            "qpb_validate", cc,
            "README Claude Code launch prompt must invoke the "
            "qpb_validate entry point (078 §3.5 launch-prompt "
            "collapse)",
        )
        self.assertIn(
            "event=validation_complete status=ok", cc,
            "README Claude Code launch prompt must carry the "
            "do-not-proceed-until status=ok Phase-0 gate (078 §3.5)",
        )
        self.assertIn(
            "install_skill", cc,
            "README Claude Code launch prompt must still reference "
            "the canonical install_skill command as the validator's "
            "remediation (078 — validator emits the platform-correct "
            "install when status=remediable)",
        )


if __name__ == "__main__":
    unittest.main()
