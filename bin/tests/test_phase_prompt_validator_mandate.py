"""v1.5.7 instruction 065 (A-14 + A-15 + A-16) — phase-prompt
validator-mandate contract pins.

A-14/A-15/A-16 are "agent ignores documented contract" defects:
prose-level guidance already existed and opus ignored it. The
structural fix is bin/validate_phase_artifacts.py PLUS a MANDATORY
"run the validator, quote its exit code" mandate wired into the
phase prompts (the A-13 witness pattern, per-phase). These tests pin
that mandate language in every phase prompt + the two reference
guides so a future edit cannot silently drop it (drift between the
phase prompt and its reference guide is the specific regression
class this guards — same shape as test_phase6_gate_witness.py).

Plain contract-pin docstrings (no per-test bite) intentionally
match the established sibling convention in
test_phase1_invocation_documented.py: the executed mutation bite
for instruction 065 lives in test_validate_phase_artifacts.py
(the A-16 null-breakdown bite, PASS->FAIL->PASS); these tests pin
the prose contract that the validated tool is actually invoked.
"""

from __future__ import annotations

import unittest
from pathlib import Path

_QPB_ROOT = Path(__file__).resolve().parents[2]
_PP = _QPB_ROOT / "phase_prompts"
_REF = _QPB_ROOT / "references"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


class PhasePromptValidatorMandateTests(unittest.TestCase):

    def test_phase1_prompt_mandates_validator(self) -> None:
        """phase_prompts/phase1.md MANDATES the --phase 1 validator +
        quote-exit-code witness AND the Mode-A
        normalize_role_map_for_gate step (the A-16 fix — Mode A has
        no runner to normalize breakdown)."""
        t = _read(_PP / "phase1.md")
        self.assertIn("bin.validate_phase_artifacts . --phase 1", t)
        self.assertIn("quote its final `RESULT:` line verbatim", t)
        self.assertIn("normalize_role_map_for_gate", t)
        self.assertIn("A-16", t)

    def test_phase2_prompt_mandates_validator(self) -> None:
        t = _read(_PP / "phase2.md")
        self.assertIn("bin.validate_phase_artifacts . --phase 2", t)
        self.assertIn("quote its final `RESULT:` line verbatim", t)
        self.assertIn("A-14", t)
        self.assertIn("MAY NOT proceed to Phase 3", t)

    def test_phase5_prompt_mandates_index_emission_and_validator(self) -> None:
        """phase_prompts/phase5.md has the explicit A-15 INDEX.md
        emission STEP (real schemas.md §11 field names + the
        role_breakdown_for_index helper, NOT the wrong
        summarize_role_map the instruction prose suggested) AND the
        --phase 5 validator mandate."""
        t = _read(_PP / "phase5.md")
        self.assertIn("STEP — Write quality/INDEX.md", t)
        self.assertIn("bin.validate_phase_artifacts . --phase 5", t)
        self.assertIn("role_breakdown_for_index", t)
        # Real §11 field names (not the instruction's run_id/
        # playbook_version mis-naming).
        for field in ("run_timestamp_start", "qpb_version",
                      "target_role_breakdown", "gate_verdict"):
            self.assertIn(field, t)
        self.assertIn("A-15", t)

    def test_phase6_prompt_mandates_validator_with_verdict(self) -> None:
        t = _read(_PP / "phase6.md")
        self.assertIn("bin.validate_phase_artifacts . --phase 6", t)
        self.assertIn("quote", t.lower())
        # Phase 6 is the stricter gate_verdict-value check.
        for v in ("pass", "partial", "fail"):
            self.assertIn(v, t)
        self.assertIn('"pending"', t)

    def test_reference_guides_coherent_with_phase_prompts(self) -> None:
        """The two reference guides carry the same validator mandate
        as their phase prompts (no prompt/guide drift — the exact
        regression class test_phase6_gate_witness.py also guards)."""
        gen = _read(_REF / "phase2_generation_guide.md")
        self.assertIn("bin.validate_phase_artifacts . --phase 2", gen)
        self.assertIn("keep the two coherent", gen)
        self.assertIn("A-14", gen)

        verify = _read(_REF / "phase6_verify_guide.md")
        self.assertIn("bin.validate_phase_artifacts . --phase 6", verify)
        self.assertIn("keep the two coherent", verify)
        self.assertIn("A-15", verify)


    def test_all_phase_prompts_demand_result_verdict_line_pattern(self) -> None:
        """v1.5.7 instruction 067 F2.4 (closing the 065 codex HALT):
        each phase prompt must demand quoting the validator's
        self-authenticating `RESULT:` line by its literal pattern —
        not the old generic "exit-code line" wording the validator
        could not actually emit. Pins the corrected witness contract
        so a future edit can't silently revert to an unsatisfiable
        mandate."""
        for n in (1, 2, 5, 6):
            with self.subTest(phase=n):
                t = _read(_PP / f"phase{n}.md")
                self.assertIn(
                    "final `RESULT:` line verbatim", t,
                    f"phase{n}.md must demand quoting the validator's "
                    f"final RESULT line verbatim (067 F2)",
                )
                self.assertIn(
                    f"RESULT: VALIDATION PASSED (phase {n})", t,
                    f"phase{n}.md must show the literal quoteable "
                    f"PASSED pattern for phase {n} (067 F2)",
                )
                self.assertIn(
                    f"RESULT: VALIDATION FAILED (phase {n} —", t,
                    f"phase{n}.md must show the literal quoteable "
                    f"FAILED pattern for phase {n} (067 F2)",
                )
                # The stale "exit-code line" wording must be gone.
                self.assertNotIn(
                    "final exit-code line verbatim", t,
                    f"phase{n}.md still carries the pre-067 "
                    f"'final exit-code line verbatim' wording the "
                    f"validator never emitted (065 codex HALT)",
                )

    def test_reference_guides_demand_result_verdict_line_pattern(self) -> None:
        """The two reference guides carry the same corrected
        RESULT-line mandate (no prompt/guide drift — 067 F2)."""
        for name in ("phase2_generation_guide.md",
                     "phase6_verify_guide.md"):
            with self.subTest(guide=name):
                t = _read(_REF / name)
                self.assertIn("final `RESULT:` line verbatim", t)
                self.assertIn("RESULT: VALIDATION PASSED (phase", t)
                self.assertNotIn("final exit-code line verbatim", t)


if __name__ == "__main__":
    unittest.main()
