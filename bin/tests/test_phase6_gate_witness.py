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
verbatim. The witness makes non-compliance DETECTABLE — an adopter
reading the chat can see whether the gate verdict line is present
and matches the claim.

v1.5.7 instruction 089c (F15) — three-state verdict taxonomy —
replaced the old binary "No PASS claim without N=0 FAILs" rule with
"No PASS / PASS WITH CLEANUP NEEDED claim if there are ANY
substantive FAILs" (the gate now distinguishes substantive failure
from audit record-keeping gaps). These tests are reconciled to pin
the NEW three-state contract language: `_NO_PASS_MARKER` is the
load-bearing "PASS WITH CLEANUP NEEDED" string (present in phase6.md
+ phase6_verify_guide.md), and the State B template assertions track
the three-state rule rather than the retired literal `N=0`.

These tests pin that contract language in the source files so a
future edit cannot silently drop it.
"""

from __future__ import annotations

import unittest
from pathlib import Path

_QPB_ROOT = Path(__file__).resolve().parents[2]
# v1.5.8 instruction 208: phase_prompts/ + references/ moved into the plugin skill folder.
_SKILL_DIR = _QPB_ROOT / "skills" / "quality-playbook"
_PHASE6 = _SKILL_DIR / "phase_prompts" / "phase6.md"
_VERIFY_GUIDE = _SKILL_DIR / "references" / "phase6_verify_guide.md"
_WJH = _SKILL_DIR / "references" / "what_just_happened.md"

_WITNESS_MARKER = "MANDATORY gate-verdict witness"
# v1.5.7 089c (F15): the binary "No PASS claim without N=0 FAILs" rule
# was replaced by the three-state taxonomy. The load-bearing marker is
# now the cleanup verdict string, present verbatim in phase6.md +
# phase6_verify_guide.md (and phase6_auditor.md / what_just_happened).
_NO_PASS_MARKER = "PASS WITH CLEANUP NEEDED"
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
        Step 6.2 both carry the MANDATORY gate-verdict-witness + the
        089c F15 three-state verdict contract (`PASS WITH CLEANUP
        NEEDED` named verbatim) — coherent, no requirement-drift
        between the Mode-A prompt and the Phase 6 reference.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-089c
        F15 (reconciling the original instruction-057 A-13 bite to the
        three-state taxonomy):
          Mutation: remove the "MANDATORY gate-verdict witness"
          paragraph from phase_prompts/phase6.md.
          Expected failure: THIS test fails with
            AssertionError: phase_prompts/phase6.md missing the
            MANDATORY gate-verdict-witness contract (A-13)
          (the first assertion below). The verify-guide assertions
          would still pass — proving the test pins each file
          independently.
          Restoration: re-add the paragraph; passes.
          Bite executed during instruction-089c development;
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
            "phase_prompts/phase6.md missing the 089c F15 three-state "
            "'PASS WITH CLEANUP NEEDED' verdict contract",
        )
        self.assertIn(
            _WITNESS_MARKER, guide,
            "references/phase6_verify_guide.md missing the MANDATORY "
            "gate-verdict-witness contract (A-13) — drifted from the "
            "phase6.md prompt",
        )
        self.assertIn(
            _NO_PASS_MARKER, guide,
            "references/phase6_verify_guide.md missing the 089c F15 "
            "three-state 'PASS WITH CLEANUP NEEDED' verdict contract",
        )
        # The gate's literal verdict lines must be named so the agent
        # knows exactly what to quote.
        for needle in ("Total: N FAIL, M WARN", "RESULT: GATE PASSED"):
            self.assertIn(needle, phase6)
            self.assertIn(needle, guide)

    def test_what_just_happened_state_b_requires_gate_witness(self) -> None:
        """The State B template MANDATES quoting the gate's Total: +
        RESULT: lines and carries the 089c F15 three-state rule:
        clean PASS, route a `PASSED WITH CLEANUP NEEDED` gate verdict
        to State CN, and never claim PASS / PASS WITH CLEANUP NEEDED
        when there are any substantive FAILs.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-089c
        F15 (reconciling the instruction-060 Q4 bite to the
        three-state taxonomy — the retired literal `N=0` is replaced
        by the three-state pins below):
          Mutation: in references/what_just_happened.md, delete the
          `RESULT: GATE PASSED WITH CLEANUP NEEDED — N audit
          record-keeping gap(s)` bullet from the State B template.
          Expected failure: THIS test fails at
            assertIn("PASSED WITH CLEANUP NEEDED", state_b) →
            AssertionError
          (and the State-CN-routing assertion also fails).
          Restoration: re-add the bullet; test passes.
          Bite EXECUTED during instruction-089c development:
          PASS→FAIL on mutation, FAIL→PASS on restore, confirmed
          (the State B cleanup bullet was the bite target;
          __pycache__ purged between mutate and restore so a stale
          .pyc could not mask the result).
        """
        wjh = _WJH.read_text(encoding="utf-8")
        state_b = _section(
            wjh, "### State B — Phases 1-6 baseline complete"
        )
        self.assertIn(_TEMPLATE_WITNESS, state_b,
                      "State B template missing the gate-witness block")
        self.assertIn("Total: N FAIL, M WARN", state_b)
        self.assertIn("RESULT: GATE PASSED", state_b)
        # 089c F15 three-state (replaces the retired `N=0` /
        # `You may\nNOT claim PASS` pins — the no-PASS rule now lives
        # inside the substantive-FAIL bullet). State B must show the
        # cleanup verdict variant, the substantive-FAIL variant,
        # forbid a PASS/CLEANUP claim under substantive FAILs, and
        # route a cleanup verdict → State CN.
        self.assertIn("PASSED WITH CLEANUP NEEDED", state_b)
        self.assertIn("substantive issue(s) must be fixed", state_b)
        self.assertIn("NOT claim PASS, PASS WITH CLEANUP NEEDED", state_b)
        self.assertIn("State CN", state_b)

    def test_what_just_happened_state_s_requires_gate_witness(self) -> None:
        """The State S template (pass-process / fail-recall) MANDATES
        quoting the gate's Total: + RESULT: lines and states a GATE
        PASSED there is NOT a successful run.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-060
        Q4 (closing the codex-057 Q4 finding — pre-060 this test
        lacked the discipline-required docstring):
          Mutation: in references/what_just_happened.md, revert the
          State S template — remove the "Gate witness (REQUIRED — do
          not omit, do not paraphrase)" block + the "pass-process /
          fail-recall signal" sentence.
          Expected failure: THIS test fails at
            assertIn(_TEMPLATE_WITNESS, state_s) →
            AssertionError: State S template missing the gate-witness
            block
          (and the Total:/RESULT:/pass-process-fail-recall
          assertions would also fail).
          Restoration: re-add the gate-witness block; test passes.
          The bite for the equivalent State-B test
          (test_what_just_happened_state_b_requires_gate_witness) was
          EXECUTED during instruction-060 development (Q4.2);
          PASS→FAIL→PASS confirmed. State S is structurally identical
          (same `_section`-scoped `assertIn(_TEMPLATE_WITNESS, …)`
          shape on the adjacent template) — the State-B bite
          establishes the family.
        """
        wjh = _WJH.read_text(encoding="utf-8")
        state_s = _section(
            wjh, "### State S — Phases 1-6 all ran"
        )
        self.assertIn(_TEMPLATE_WITNESS, state_s,
                      "State S template missing the gate-witness block")
        self.assertIn("Total: N FAIL, M WARN", state_s)
        self.assertIn("RESULT: GATE PASSED", state_s)
        self.assertIn("pass-process / fail-recall signal", state_s)

    def test_what_just_happened_state_cn_template(self) -> None:
        """v1.5.7 089c (F15): references/what_just_happened.md carries
        a **State CN** template for `RESULT: GATE PASSED WITH CLEANUP
        NEEDED` — the classifier rule, the two adopter-facing sections
        (quality findings complete / audit record-keeping needs
        cleanup), reassuring closing prose, an AI-paste-ready next
        step, NO jargon in the user-facing block, and NO documentation
        onus on the adopter (quality/ IS the record).

        State-letter note: the state is **CN**, not **C** — **C** is
        already the code-only-Phase-1 state (classifier Rule 9);
        instruction 089c suggested "State C" but that label was taken,
        so this is State CN to avoid the collision.

        Mutation-test evidence (ai_context/DEVELOPMENT_PROCESS.md:
        152-160), instruction-089c F15:
          Mutation: in references/what_just_happened.md, reintroduce
          jargon by replacing "audit record-keeping" with "schema
          compliance" inside the State CN block.
          Expected failure: THIS test fails at the no-jargon
          assertion →
            AssertionError: State CN user-facing block contains
            jargon: 'schema' / 'compliance'
          Restoration: revert the wording; test passes.
          Bite EXECUTED during instruction-089c development:
          PASS→FAIL on mutation, FAIL→PASS on restore, confirmed
          (the State CN block was the bite target; __pycache__ purged
          between mutate and restore).
        """
        wjh = _WJH.read_text(encoding="utf-8")
        # Classifier rule present.
        self.assertIn("**State CN**", wjh,
                      "classifier table missing the State CN rule")
        self.assertIn("RESULT: GATE PASSED WITH CLEANUP NEEDED", wjh)

        state_cn = _section(
            wjh, "### State CN — Phases 1-6 complete, PASSED WITH CLEANUP"
        )
        # Two adopter-facing sections.
        self.assertIn("### Quality findings (complete)", state_cn)
        self.assertIn("### Audit record-keeping (needs cleanup)", state_cn)
        # Reassuring closing prose — findings stand on their own.
        self.assertIn("the bug findings stand on their own", state_cn)
        self.assertIn("not about your code's quality", state_cn)
        # AI-paste-ready recommended next step.
        self.assertIn("### Recommended next step", state_cn)
        self.assertIn("Copy-paste this:", state_cn)
        # No documentation onus on the adopter (quality/ IS the
        # record — do not ask them to write prose into BUGS.md).
        self.assertNotIn("document the decision in BUGS.md", state_cn)
        self.assertNotIn("document the decision", state_cn)
        # No jargon in the user-facing State CN block. The scoped
        # `_section` slice is the whole State CN section; the only
        # legitimate concrete uses ("manifest"/"record" as plain
        # nouns) are allowed, but the abstract-jargon set is not.
        for bad in ("compliance", "contract", "mechanical",
                    "invariant", "schema"):
            self.assertNotIn(
                bad, state_cn.lower(),
                f"State CN user-facing block contains jargon: {bad!r} "
                f"(F15 requires adopter-recognizable language only)",
            )


if __name__ == "__main__":
    unittest.main()
