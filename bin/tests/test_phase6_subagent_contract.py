"""v1.5.7 instruction 071 (A-13 hybrid) — Phase 6 verification MUST
run in a fresh-context sub-agent (principled A-17 exception).

Three prompt-level A-13 rounds (057, 067, 069) failed to stop the
same-context executor from fabricating Phase 6 PASS verdicts
against failing gates (virtio + express 2026-05-16, httpx
2026-05-17). The fix is structural: Phase 6 verification is
delegated to a fresh-context sub-agent (the auditor) that has none
of the executor's memory / anchoring / completion-reward bias.
A-17 (no sub-agent delegation in Mode A) gets a principled
exception scoped strictly to Phase 6 verification — visibility for
execution, isolation for verification.

These tests pin the structural contract across phase6.md, the new
phase6_auditor.md, and SKILL.md so a future edit cannot silently
revert to same-context Phase 6 verification.
"""

from __future__ import annotations

import unittest
from pathlib import Path

_QPB_ROOT = Path(__file__).resolve().parents[2]
# v1.5.8 instruction 208: phase_prompts/ + SKILL.md moved into the plugin skill folder.
_SKILL_DIR = _QPB_ROOT / "skills" / "quality-playbook"
_PHASE6 = _SKILL_DIR / "phase_prompts" / "phase6.md"
_AUDITOR = _SKILL_DIR / "phase_prompts" / "phase6_auditor.md"
_SKILL_MD = _SKILL_DIR / "SKILL.md"


def _slice(text: str, header: str, *stops: str) -> str:
    """Slice from `header` to the first of `stops` after it (or EOF)
    — scopes an assertion to one section so a stray match elsewhere
    cannot satisfy it."""
    start = text.index(header)
    rest = text[start + len(header):]
    cut = len(rest)
    for s in stops:
        i = rest.find(s)
        if i != -1:
            cut = min(cut, i)
    return rest[:cut]


class Phase6SubAgentContractTests(unittest.TestCase):
    """A-13 hybrid: the Phase 6 sub-agent delegation contract is
    present and coherent across phase6.md / phase6_auditor.md /
    SKILL.md."""

    def test_phase6_prompt_mandates_subagent_delegation(self) -> None:
        """phase_prompts/phase6.md MANDATES the fresh-context
        sub-agent for verification (not merely recommends) and cites
        the three benchmark fabrication failures.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-071 —
        BITE EXECUTED during instruction-071 development:
          Mutation: delete the "STRUCTURAL: Phase 6 verification
          MUST run in a fresh-context sub-agent, not your current
          session." sentence from phase_prompts/phase6.md.
          Observed failure: THIS test fails at the first assertion
            self.assertIn("STRUCTURAL: Phase 6 verification MUST run
            in a fresh-context sub-agent", phase6) →
            AssertionError ... : phase6.md missing the STRUCTURAL
            sub-agent-delegation mandate (A-13 hybrid)
          Restoration: re-add the sentence; test passes.
          Bite EXECUTED PASS→FAIL→PASS, __pycache__ purged between
          mutate and restore (feedback_mutation_bite_pycache — a
          stale .pyc could mask the restored-clean state).
        """
        phase6 = _PHASE6.read_text(encoding="utf-8")
        self.assertIn(
            "STRUCTURAL: Phase 6 verification MUST run in a "
            "fresh-context sub-agent", phase6,
            "phase6.md missing the STRUCTURAL sub-agent-delegation "
            "mandate (A-13 hybrid)",
        )
        self.assertIn(
            "non-negotiable", phase6,
            "phase6.md must frame the delegation as non-negotiable, "
            "not a recommendation (A-13 hybrid)",
        )
        # The three benchmark fabrication failures must be cited so a
        # reader knows the rule is grounded in verified incidents.
        for needle in ("virtio", "express", "httpx"):
            self.assertIn(
                needle, phase6,
                f"phase6.md must cite the {needle} fabrication "
                f"failure (A-13 hybrid evidence)",
            )
        # The principled A-17 exception framing must be explicit.
        self.assertIn("principled A-17 exception", phase6)
        # Part B: the parent pastes the auditor's verbatim verdict.
        self.assertIn("AUDITOR VERDICT", phase6)
        self.assertIn("verbatim", phase6.lower())

    def test_phase6_prompt_provides_fallback_for_tools_without_subagent_primitives(self) -> None:
        """phase6.md provides the fresh-chat fallback for runtimes
        that lack a Task/Agent sub-agent primitive (so the structural
        contract degrades to operator-mediated isolation, never to
        same-context verification)."""
        phase6 = _PHASE6.read_text(encoding="utf-8")
        self.assertIn(
            "If your runtime lacks sub-agent primitives", phase6,
            "phase6.md must provide a fallback path for tools "
            "without sub-agent primitives (A-13 hybrid)",
        )
        self.assertIn(
            "fresh chat session", phase6,
            "the fallback must direct the operator to a fresh chat "
            "session (isolation preserved without a Task primitive)",
        )
        self.assertIn("phase_prompts/phase6_auditor.md", phase6,
                      "the fallback must point at the auditor prompt")

    def test_phase6_auditor_prompt_exists_and_has_verdict_contract(self) -> None:
        """phase_prompts/phase6_auditor.md carries the AUDITOR-role
        framing (not executor-style) AND the structured verdict
        contract (GATE WITNESS + VALIDATOR WITNESS + AUDITOR VERDICT),
        now in the v1.5.7 089c F15 three-state form (PASS / PASS WITH
        CLEANUP NEEDED / FAIL).

        Mutation-test evidence (ai_context/DEVELOPMENT_PROCESS.md:
        152-160), instruction-089c F15 (reconciling the retired
        binary "No PASS claim without N=0 FAILs" pin to the
        three-state contract):
          Mutation: delete the "**No PASS / PASS WITH CLEANUP NEEDED
          claim if there are ANY substantive" sentence from
          phase_prompts/phase6_auditor.md.
          Expected failure: THIS test fails at
            assertIn("No PASS / PASS WITH CLEANUP NEEDED claim if "
            "there are ANY substantive", auditor) → AssertionError.
          Restoration: re-add the sentence; test passes.
          Bite executed during 089c development; PASS→FAIL→PASS
          confirmed (__pycache__ purged between mutate and restore).
        """
        self.assertTrue(
            _AUDITOR.is_file(),
            "phase_prompts/phase6_auditor.md must exist (A-13 hybrid "
            "auditor prompt)",
        )
        auditor = _AUDITOR.read_text(encoding="utf-8")
        self.assertIn("INDEPENDENT AUDITOR", auditor,
                      "auditor prompt must use audit-role framing")
        self.assertIn(
            "find discrepancies", auditor,
            "auditor reward shape must be discrepancy-finding, not "
            "completion-reporting",
        )
        # The structured verdict the parent pastes verbatim.
        for needle in ("GATE WITNESS (verbatim):",
                       "VALIDATOR WITNESS (verbatim):",
                       "AUDITOR VERDICT:"):
            self.assertIn(
                needle, auditor,
                f"auditor prompt missing the {needle!r} structured "
                f"verdict section (A-13 hybrid)",
            )
        # The auditor genuinely runs the gate + the phase-6 validator
        # and carries the A-13 witness contract.
        self.assertIn("MANDATORY gate-verdict witness", auditor)
        # v1.5.7 089c F15: the binary "No PASS claim without N=0
        # FAILs" rule is retired; pin the three-state contract +
        # the substantive-FAILs-block rule + the AUDITOR VERDICT
        # cleanup state instead.
        self.assertIn("Three-state verdict (v1.5.7 089c F15)", auditor)
        self.assertIn(
            "No PASS / PASS WITH CLEANUP NEEDED claim if there are "
            "ANY substantive", auditor,
            "auditor prompt missing the 089c F15 substantive-FAILs "
            "block rule (replaces the retired N=0 binary rule)",
        )
        self.assertIn("AUDITOR VERDICT: PASS WITH CLEANUP NEEDED", auditor)
        self.assertIn("bin.validate_phase_artifacts . --phase 6", auditor)
        # Audit-only: must NOT fix FAILs (that is the executor's bias).
        self.assertIn("you will not", auditor.lower())

    def test_skill_md_a17_has_verification_exception(self) -> None:
        """SKILL.md carries the principled verification exception
        in BOTH the Mode A intro AND guardrail #1 (execution = no
        sub-agent; verification = mandatory sub-agent; same
        principle, opposite mechanism).

        v1.5.7 192: trim 45d4520 removed instruction codes (A-17,
        B-15, A-13 hybrid) and the dated `2026-05-16 express` /
        `2026-05-17 httpx` citations as unactionable. The structural
        contract (exception is MANDATED, scoped to Phase 6
        verification, points at phase6_auditor.md) is preserved in
        cleaner prose. Assertions updated to the current canonical
        wording.
        """
        skill = _SKILL_MD.read_text(encoding="utf-8")
        mode_a = _slice(
            skill,
            "### Mode A — skill-direct walkthrough (UI-context)",
            "\n### Mode B —",
        )
        self.assertIn(
            "EXCEPTION:", mode_a,
            "SKILL.md Mode A intro must carry the verification "
            "EXCEPTION callout",
        )
        self.assertIn(
            "MANDATED for VERIFICATION", mode_a,
            "Mode A exception must MANDATE (not merely allow) "
            "sub-agent delegation for Phase 6 verification",
        )
        self.assertIn("phase_prompts/phase6_auditor.md", mode_a)
        # Guardrail #1 must distinguish execution vs verification.
        guardrail_1 = _slice(
            skill,
            "1. **Synchronous execution — no sub-agent delegation.**",
            "\n2. **Don't patch QPB source",
        )
        self.assertIn(
            "Phase 6 verification — mandatory sub-agent delegation",
            guardrail_1,
            "guardrail #1 must distinguish Phase 1-5 execution "
            "(no sub-agent) from Phase 6 verification (mandatory "
            "sub-agent)",
        )
        # The principled-exception framing (execution forbidden,
        # verification mandated) must survive as descriptive prose.
        self.assertIn(
            "opposite mechanism", guardrail_1,
            "guardrail #1 must frame the verification exception as "
            "the same principle but opposite mechanism (visibility "
            "for execution; isolation for verification)",
        )
        # Both failure modes the rule closes must be described in
        # the surviving prose (the trim collapsed instruction codes
        # but kept the mechanism descriptions).
        self.assertIn(
            "phases 2", guardrail_1,
            "guardrail #1 must describe the phases-2-6-silent-death "
            "failure mode (originally cited as B-15)",
        )
        self.assertIn(
            "fabricates", guardrail_1,
            "guardrail #1 must describe the sub-skill "
            "PASS-fabrication failure mode (originally cited as A-17)",
        )


if __name__ == "__main__":
    unittest.main()
