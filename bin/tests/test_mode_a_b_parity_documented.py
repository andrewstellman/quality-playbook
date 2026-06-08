"""v1.5.7 089d (F21) — pin the documented Mode A vs Mode B asymmetries.

The opus self-bootstrap surfaced three by-design behavior differences
between Mode A (skill-direct adopter walkthrough) and Mode B
(`run_playbook.py` runner): Phase 0 install-validator, end-of-run
archive, and Phase 6 auditor sub-agent dispatch. The instruction
F21 framed these as "parity broken" but architectural reading is
that they're intentional (Mode A is adopter-facing, Mode B is the
QPB-internal benchmark runner). Worker (089d) aligned DOWN by
explicitly documenting the asymmetries in SKILL.md + adding a
Mode-B routing header to phase6_auditor.md.

This test pins the documentation so a future edit that silently
drops the rationale gets caught. If a future change wants to align
the modes functionally instead (add a Phase 0 step to Mode B, or
add a Mode A archive step), update the pin assertions here
alongside the behavior change.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
# v1.5.8 instruction 208: SKILL.md + phase_prompts/ moved into
# skills/quality-playbook/.
_SKILL_DIR = _REPO_ROOT / "skills" / "quality-playbook"
_SKILL_MD = _SKILL_DIR / "SKILL.md"
_PHASE6_AUDITOR = _SKILL_DIR / "phase_prompts" / "phase6_auditor.md"


class ModeABParityDocumentedTests(unittest.TestCase):

    def test_skill_md_documents_three_mode_asymmetries(self) -> None:
        """SKILL.md carries the F21 asymmetry block naming all three
        behaviors + their architectural rationale.

        Mutation-test evidence (ai_context/DEVELOPMENT_PROCESS.md:
        152-160), instruction-089d F21:
          Mutation: in SKILL.md, delete the "Documented Mode A vs
          Mode B asymmetries" paragraph.
          Expected failure: THIS test fails at the marker `assertIn`.
          Restoration: re-add the paragraph; passes. Bite executed
          during 089d development; PASS→FAIL→PASS confirmed.
        """
        s = _SKILL_MD.read_text(encoding="utf-8")
        self.assertIn(
            "Documented Mode A vs Mode B asymmetries", s,
            "SKILL.md must carry the F21 asymmetry section header — "
            "if removed, adopters/maintainers won't see the rationale "
            "for the three by-design behavior differences.",
        )
        # All three named:
        # v1.5.7 191 FINDING-52: "Phase 0 install-validator" renamed
        # to "Phase 0 entry contract — install validator" so the seed-
        # loading "Phase 0 (Prior Run Analysis)" pass and the install
        # validator first-probe pass don't share the bare "Phase 0" name.
        self.assertIn("Phase 0 entry contract", s,
                      "F21 asymmetry #1 (Phase 0 entry contract) missing")
        self.assertIn("End-of-run archive", s,
                      "F21 asymmetry #2 (archive step) missing")
        self.assertIn(
            "Phase 6 auditor-prompt sub-agent dispatch", s,
            "F21 asymmetry #3 (auditor dispatch) missing",
        )
        # The pin test is referenced from SKILL.md as the lock —
        # a future maintainer reading SKILL.md sees how to update
        # this test alongside any behavior change.
        self.assertIn(
            "bin/tests/test_mode_a_b_parity_documented.py", s,
            "SKILL.md asymmetry block must reference this pin test "
            "as the lock-step file to update on behavior changes.",
        )

    def test_phase6_auditor_md_has_mode_b_routing_header(self) -> None:
        """phase6_auditor.md's header explicitly states the prompt
        is Mode-A-only, with the architectural rationale (Mode B
        per-phase CLI subprocess IS already a fresh context — the
        very property the auditor exists to provide).

        Mutation-test evidence (ai_context/DEVELOPMENT_PROCESS.md:
        152-160), instruction-089d F21:
          Mutation: in phase_prompts/phase6_auditor.md, delete the
          "Routing (v1.5.7 089d F21)" paragraph.
          Expected failure: THIS test fails at the marker `assertIn`.
          Restoration: re-add; passes. Bite executed during 089d
          development; PASS→FAIL→PASS confirmed.
        """
        s = _PHASE6_AUDITOR.read_text(encoding="utf-8")
        self.assertIn(
            "Routing (v1.5.7 089d F21)", s,
            "phase6_auditor.md must carry the F21 routing header "
            "stating it is the Mode A spawn target (Mode B handles "
            "Phase 6 inline per phase6.md:5-7).",
        )
        # The file is markdown — line wrap can split phrases across
        # `\n` (e.g. "Mode B does not\nload this file"). Match
        # whitespace-tolerantly.
        self.assertTrue(
            re.search(r"Mode B does not\s+load this file", s),
            "phase6_auditor.md routing header must be explicit that "
            "Mode B does not invoke this prompt (the asymmetry is "
            "by design — Mode B subprocess IS the fresh context).",
        )


if __name__ == "__main__":
    unittest.main()
