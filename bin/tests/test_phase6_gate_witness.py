"""v1.5.7 instruction 057 (A-13) — Phase 6 gate-PASS credibility
defect closure.

In the virtio opus-4.6 Mode-A run (2026-05-16) the agent's final
chat output claimed "Gate: PASS" while `quality/results/
quality-gate.log` was 0 bytes and the gate actually returned 19
FAIL, 3 WARN — GATE FAILED. The agent fabricated the verdict.

The fix is a PROMPT-CONTRACT change (not a code change — Mode A
agent compliance is not runtime-enforceable): the Phase 6 prompt +
the Phase 6 reference + the State B / State S chat-emit templates
now require quoting the gate's `Total:` and `RESULT:` lines
verbatim, and forbid a PASS claim without `N=0` FAILs. The witness
makes non-compliance DETECTABLE — an adopter reading the chat can
see whether the gate verdict line is present and matches the claim.

These tests pin that contract language in the four source files so a
future edit cannot silently drop it.
"""

from __future__ import annotations

import unittest
from pathlib import Path

_QPB_ROOT = Path(__file__).resolve().parents[2]
_PHASE6 = _QPB_ROOT / "phase_prompts" / "phase6.md"
_VERIFY_GUIDE = _QPB_ROOT / "references" / "phase6_verify_guide.md"
_WJH = _QPB_ROOT / "references" / "what_just_happened.md"

_WITNESS_MARKER = "MANDATORY gate-verdict witness"
_NO_PASS_MARKER = "No PASS claim without N=0 FAILs"
_TEMPLATE_WITNESS = "Gate witness (REQUIRED — do not omit, do not paraphrase)"


def _section(text: str, header: str, next_prefix: str = "### State ") -> str:
    """Return the slice of `text` from `header` up to the next
    `next_prefix` heading (or EOF) — used to scope an assertion to a
    single State template."""
    start = text.index(header)
    rest = text[start + len(header):]
    nxt = rest.find("\n" + next_prefix)
    return rest if nxt == -1 else rest[:nxt]


class Phase6GateWitnessContractTests(unittest.TestCase):
    """A-13: the gate-verdict-witness contract is present in the
    Phase 6 prompt, the Phase 6 reference, and the State B / State S
    chat-emit templates."""

    def test_phase6_prompt_requires_gate_verdict_witness(self) -> None:
        """phase_prompts/phase6.md AND references/phase6_verify_guide.md
        Step 6.2 both carry the MANDATORY gate-verdict-witness +
        "No PASS claim without N=0 FAILs" contract (coherent, no
        requirement-drift between the Mode-A prompt and the Phase 6
        reference).

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-057
        A-13:
          Mutation: remove the "MANDATORY gate-verdict witness"
          paragraph from phase_prompts/phase6.md Step 6.2.
          Expected failure: THIS test fails with
            AssertionError: phase_prompts/phase6.md missing the
            MANDATORY gate-verdict-witness contract (A-13)
          (the first assertion below). The verify-guide assertions
          would still pass — proving the test pins each file
          independently.
          Restoration: re-add the paragraph; passes.
          Bite executed during instruction-057 development;
          PASS→FAIL→PASS confirmed (__pycache__ purged between
          mutate and restore).
        """
        phase6 = _PHASE6.read_text(encoding="utf-8")
        guide = _VERIFY_GUIDE.read_text(encoding="utf-8")

        self.assertIn(
            _WITNESS_MARKER, phase6,
            "phase_prompts/phase6.md missing the MANDATORY "
            "gate-verdict-witness contract (A-13)",
        )
        self.assertIn(
            _NO_PASS_MARKER, phase6,
            "phase_prompts/phase6.md missing the 'No PASS claim "
            "without N=0 FAILs' rule (A-13)",
        )
        self.assertIn(
            _WITNESS_MARKER, guide,
            "references/phase6_verify_guide.md missing the MANDATORY "
            "gate-verdict-witness contract (A-13) — drifted from the "
            "phase6.md prompt",
        )
        self.assertIn(
            _NO_PASS_MARKER, guide,
            "references/phase6_verify_guide.md missing the 'No PASS "
            "claim without N=0 FAILs' rule (A-13)",
        )
        # The gate's literal verdict lines must be named so the agent
        # knows exactly what to quote.
        for needle in ("Total: N FAIL, M WARN", "RESULT: GATE PASSED"):
            self.assertIn(needle, phase6)
            self.assertIn(needle, guide)

    def test_what_just_happened_state_b_requires_gate_witness(self) -> None:
        """The State B template MANDATES quoting the gate's Total: +
        RESULT: lines and forbids a PASS claim without N=0 FAILs."""
        wjh = _WJH.read_text(encoding="utf-8")
        state_b = _section(
            wjh, "### State B — Phases 1-6 baseline complete"
        )
        self.assertIn(_TEMPLATE_WITNESS, state_b,
                      "State B template missing the gate-witness block")
        self.assertIn("Total: N FAIL, M WARN", state_b)
        self.assertIn("RESULT: GATE PASSED", state_b)
        self.assertIn("You may\nNOT claim PASS", state_b)
        self.assertIn("N=0", state_b)

    def test_what_just_happened_state_s_requires_gate_witness(self) -> None:
        """The State S template (pass-process / fail-recall) MANDATES
        quoting the gate's Total: + RESULT: lines and states a GATE
        PASSED there is NOT a successful run."""
        wjh = _WJH.read_text(encoding="utf-8")
        state_s = _section(
            wjh, "### State S — Phases 1-6 all ran"
        )
        self.assertIn(_TEMPLATE_WITNESS, state_s,
                      "State S template missing the gate-witness block")
        self.assertIn("Total: N FAIL, M WARN", state_s)
        self.assertIn("RESULT: GATE PASSED", state_s)
        self.assertIn("pass-process / fail-recall signal", state_s)


if __name__ == "__main__":
    unittest.main()
