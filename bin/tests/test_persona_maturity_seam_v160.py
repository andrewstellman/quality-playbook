"""v1.6.0 Feature H slice 6 (instruction 018) — maturity disclosure + the
target-agnostic harness seam. Two small finishes: disclose when persona output
rests on the not-yet-functional readability rubric (§8b "Honesty about maturity",
à la F-1), and lock in — with a test — the per-target provisioning seam v1.6.1's
Feature B reuses.
"""

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = (
    REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook" / "scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))

import persona_apply as pa  # noqa: E402
import persona_orchestration as po  # noqa: E402


class _MR:
    """A minimal MergeResult stand-in for build_review_summary."""
    def __init__(self, applied, conflicts=None):
        self.applied = applied
        self.conflicts = conflicts or []


def _cit():
    return {"document": "reference_docs/spec.txt", "citation_excerpt": "x"}


class MaturityDisclosureTests(unittest.TestCase):
    def test_no_caveat_when_nothing_rests_on_the_rubric(self):
        mr = _MR([{"move": "add", "title": "grounded", "citation": _cit(),
                   "dimension": "Complete"}])
        s = pa.build_review_summary(mr)
        self.assertIsNone(s["maturity_disclosure"])

    def test_caveat_fires_for_a_rubric_dependent_applied_move(self):
        mr = _MR([{"move": "correct", "req_id": "REQ-001", "citation": _cit(),
                   "dimension": "Well-organized"}])
        s = pa.build_review_summary(mr)
        self.assertIsNotNone(s["maturity_disclosure"])
        self.assertIn("readability", s["maturity_disclosure"].lower())
        self.assertIn("lower confidence", s["maturity_disclosure"].lower())
        self.assertTrue(s["applied"][0]["rubric_dependent"])

    def test_caveat_fires_via_explicit_rubric_dependent_flag(self):
        mr = _MR([{"move": "add", "title": "x", "citation": _cit(),
                   "rubric_dependent": True}])
        s = pa.build_review_summary(mr)
        self.assertIsNotNone(s["maturity_disclosure"])

    def test_caveat_fires_for_a_rubric_dependent_candidate(self):
        mr = _MR([{"move": "add", "title": "grounded", "citation": _cit()}])
        candidates = [{"persona_id": "domain-expert", "move": "add",
                       "shortfall": "not fit", "dimension": "readability"}]
        s = pa.build_review_summary(mr, candidate_bucket=candidates)
        self.assertIsNotNone(s["maturity_disclosure"])

    def test_maturity_disclosure_helper_counts_only_rubric_items(self):
        items = [
            {"dimension": "Complete"},
            {"dimension": "Well-organized"},
            {"rubric_dependent": True},
            {"dimension": "Correct"},
        ]
        text = pa.maturity_disclosure(items)
        self.assertIn("2 of these findings", text)
        self.assertIsNone(pa.maturity_disclosure([{"dimension": "Correct"}]))


class TargetAgnosticSeamTests(unittest.TestCase):
    """Lock in the seam Feature B binds to: the SAME spawn/stage/tool-allowlist
    path serves H's input set and a Feature-B-shaped set — no H-specific input
    hard-coded into the mechanism."""

    def _h_provision(self, persona):
        return [
            po.StagedInput("13_api_reference.md", "# API ref\n\nrouter.Get(p, h)\n"),
            po.StagedInput("REQUIREMENTS.md", "# Requirements\n\n### REQ-001: x\n"),
            po.StagedInput("rubric.md", "# Rubric\n\nComplete Honest Consistent Correct\n"),
        ]

    def _b_provision(self, persona):
        # Feature B's OPPOSITE, more-restrictive isolation: finding + source + REQ + rubric.
        return [
            po.StagedInput("finding.md", "# Finding\n\nBUG-001 claim"),
            po.StagedInput("source_excerpt.go", "func F(){}"),
            po.StagedInput("REQ-001.md", "### REQ-001"),
            po.StagedInput("fp_rubric.md", "# FP rubric"),
        ]

    def test_same_path_serves_H_and_B_input_sets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            def executor(persona, staging_dir, tool_config):
                names = {p.name for p in Path(staging_dir).iterdir()}
                # The tool restriction is identical regardless of target.
                assert tool_config.denies("Bash") and tool_config.denies("fetch")
                return {"persona_id": persona["id"], "moves": [], "_staged": sorted(names)}

            selected = [{"id": "security-reviewer"}]
            h_runs = po.run_personas(selected, self._h_provision, executor, root / "h")
            b_runs = po.run_personas(selected, self._b_provision, executor, root / "b")

        # Same orchestration, DIFFERENT (target-supplied) input sets — proving the
        # provision seam is a per-target parameter, not H-specific.
        self.assertEqual(sorted(h_runs[0].staged_names),
                         ["13_api_reference.md", "REQUIREMENTS.md", "rubric.md"])
        self.assertEqual(sorted(b_runs[0].staged_names),
                         ["REQ-001.md", "finding.md", "fp_rubric.md", "source_excerpt.go"])
        # No H input leaked into the B run (no hard-coding).
        self.assertNotIn("REQUIREMENTS.md", b_runs[0].staged_names)
        self.assertNotIn("finding.md", h_runs[0].staged_names)

    def test_run_personas_signature_takes_provision_as_a_parameter(self):
        # The mechanism accepts context provisioning as a callable parameter —
        # the seam Feature B will bind (it does not reach into H's inputs).
        import inspect
        params = list(inspect.signature(po.run_personas).parameters)
        self.assertIn("provision", params)


class NoGatingScopeTests(unittest.TestCase):
    def test_no_calibration_or_gate_introduced(self):
        src = (SCRIPT_DIR / "persona_apply.py").read_text(encoding="utf-8")
        low = src.lower()
        # No gating/verdict/calibration machinery (H is a remediator).
        for forbidden in ("calibration", "def gate", "verdict", "pass_fail",
                          "score_threshold", "gating"):
            self.assertNotIn(forbidden, low, f"unexpected {forbidden!r} in persona_apply")


if __name__ == "__main__":
    unittest.main()
