"""v1.5.7 191 — SKILL.md prose consistency.

FINDING-52: Phase 0 dual labeling. Pre-191, "Phase 0" referred
to TWO different things — Phase 0 (Prior Run Analysis, the
seed-loading pass) AND Phase 0 install-validator first-probe.
Post-191: the seed-loading pass keeps the "Phase 0 (Prior Run
Analysis)" name; the install-validator first-probe is renamed
"Phase 0 entry contract."

FINDING-53: Phase 7 described three different ways. Post-191:
a single canonical paragraph in the Phase 7 section covers all
four invariants (it IS a phase, Mode A is conversational, Mode B
is post-Phase-6 hand-off, "Do not skip" applies to both).
"""
from __future__ import annotations

import pathlib
import re
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[2]


def _skill_md() -> str:
    # v1.5.8 instruction 209: SKILL.md lives under the standard
    # self-hosted marketplace plugin layout.
    return (
        _REPO / "plugins" / "quality-playbook"
        / "skills" / "quality-playbook" / "SKILL.md"
    ).read_text(encoding="utf-8")


class Phase0NamingTests(unittest.TestCase):
    """FINDING-52 — Phase 0 naming canonical."""

    def test_phase_0_prior_run_analysis_appears_once(
            self) -> None:
        """The "Phase 0 (Prior Run Analysis)" label appears
        exactly once — at the Plan Overview intro. The full
        Phase 0 section header uses "Phase 0: Prior Run
        Analysis" (no parens) so the regex matches the intro
        bullet only."""
        text = _skill_md()
        matches = re.findall(
            r"Phase 0 \(Prior Run Analysis\)", text)
        self.assertEqual(
            len(matches), 1,
            f"expected exactly one 'Phase 0 (Prior Run "
            f"Analysis)' label, found {len(matches)}")

    def test_no_phase_0_install_validator_first_probe_label(
            self) -> None:
        """The legacy overloaded "Phase 0 install validator
        first-probe" label must not appear anywhere — it
        conflicts with the Phase 0 (Prior Run Analysis) name."""
        text = _skill_md()
        legacy = re.findall(
            r"Phase 0 install validator first-probe", text)
        self.assertEqual(
            legacy, [],
            f"legacy overloaded label found: {legacy}")

    def test_phase_0_entry_contract_used_consistently(
            self) -> None:
        """The renamed install-validator first-probe must
        consistently use "Phase 0 entry contract" — appearing
        at multiple SKILL.md sites (asymmetry intro, MANDATORY
        action banner, entry contract heading, first-probe
        prose, gitignore remediation step)."""
        text = _skill_md()
        matches = re.findall(r"Phase 0 entry contract", text)
        self.assertGreaterEqual(
            len(matches), 4,
            f"expected ≥4 'Phase 0 entry contract' references, "
            f"found {len(matches)}")

    def test_phase0_first_probe_grading_assertion_preserved(
            self) -> None:
        """The harness-side assertion identifier
        `phase0_first_probe` is a STABLE test/grading hook
        referenced from other code. The FINDING-52 prose
        rename MUST NOT touch this identifier."""
        text = _skill_md()
        self.assertIn(
            "phase0_first_probe", text,
            "harness grading assertion identifier "
            "`phase0_first_probe` must remain in SKILL.md "
            "prose — it is a stable identifier referenced "
            "by other code")


class Phase7CanonicalParagraphTests(unittest.TestCase):
    """FINDING-53 — Phase 7 consolidated to one canonical
    paragraph in the Phase 7 section."""

    def test_phase_7_canonical_paragraph_exists(self) -> None:
        """The Phase 7 section opens with a `**Canonical
        treatment.**` paragraph that covers all four
        invariants."""
        text = _skill_md()
        m = re.search(
            r"## Phase 7:.*?\n+(\*\*Canonical treatment\.\*\*"
            r"[^\n]+)\n",
            text, re.DOTALL)
        self.assertIsNotNone(
            m, "Phase 7 section missing the canonical-"
               "treatment opening paragraph")

    def test_phase_7_canonical_covers_all_four_invariants(
            self) -> None:
        """The canonical paragraph must mention:
        - Phase 7 IS a phase (operator-visible value)
        - Mode A: conversational
        - Mode B: post-Phase-6 hand-off / runner banner
        - Do not skip applies to both modes"""
        text = _skill_md()
        m = re.search(
            r"\*\*Canonical treatment\.\*\*([^#]+?)(?=\n## |\n### )",
            text, re.DOTALL)
        self.assertIsNotNone(m, "canonical paragraph not found")
        paragraph = m.group(1).lower()
        self.assertIn("phase 7 is a phase", paragraph,
            "canonical paragraph missing 'Phase 7 IS a phase'")
        self.assertIn("conversational", paragraph,
            "canonical paragraph missing Mode A conversational")
        self.assertIn("post-phase-6", paragraph,
            "canonical paragraph missing Mode B post-Phase-6 "
            "hand-off")
        self.assertIn('"do not skip"', paragraph,
            "canonical paragraph missing 'Do not skip' applies "
            "to both modes")

    def test_phase_7_mode_a_asymmetry_bullet_is_backreference(
            self) -> None:
        """The Mode A asymmetry bullet at line ~119 must now
        reference the Phase 7 section rather than re-stating
        the full treatment."""
        text = _skill_md()
        # The asymmetry bullet should reference the Phase 7
        # section's canonical treatment.
        m = re.search(
            r"- \*\*Phase 7 \(interactive Present / Explore"
            r" / Improve\)\.\*\*[^\n]*Phase 7[^\n]*canonical",
            text)
        self.assertIsNotNone(
            m, "Mode A asymmetry bullet for Phase 7 should "
               "back-reference the canonical Phase 7 section")


if __name__ == "__main__":
    unittest.main()
