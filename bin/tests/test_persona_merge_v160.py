"""v1.6.0 Feature H slice 4 (instruction 016) — Guard 3 multi-persona merge.

Covers §8b Verification 7: union of grounded moves; conflict SURFACED not
resolved (per shape); exactly ONE terminal renumber (reusing the instr-007
renumber) yielding sequential IDs; defer excluded; provenance preserved.
"""

import copy
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = (
    REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook" / "scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))

import persona_merge as pm  # noqa: E402
import requirements_render  # noqa: E402


def _base():
    return {"records": [
        {"id": "REQ-001", "functional_section": "Routing", "title": "A",
         "conditions_of_satisfaction": "a"},
        {"id": "REQ-002", "functional_section": "Routing", "title": "B",
         "conditions_of_satisfaction": "b"},
        {"id": "REQ-003", "functional_section": "Errors", "title": "C",
         "conditions_of_satisfaction": "c"},
    ]}


def _cit():
    return {"document": "reference_docs/spec.txt", "citation_excerpt": "x"}


class UnionTests(unittest.TestCase):
    def test_non_overlapping_grounded_moves_all_land(self):
        grounded = [
            {"persona_id": "domain-expert", "moves": [
                {"move": "add", "section": "Routing", "title": "regexp params",
                 "conditions_of_satisfaction": "params support {name:pattern}",
                 "citation": _cit()}]},
            {"persona_id": "security-reviewer", "moves": [
                {"move": "add", "section": "Errors", "title": "no stack leak",
                 "conditions_of_satisfaction": "errors do not leak traces",
                 "citation": _cit()}]},
        ]
        r = pm.merge_personas(grounded, _base())
        titles = [rec["title"] for rec in r.manifest["records"]]
        self.assertIn("regexp params", titles)
        self.assertIn("no stack leak", titles)
        self.assertEqual(r.conflicts, [])
        self.assertEqual(len(r.applied), 2)

    def test_two_identical_corrects_are_agreement_not_conflict(self):
        grounded = [
            {"persona_id": "a", "moves": [
                {"move": "correct", "req_id": "REQ-001",
                 "conditions_of_satisfaction": "same fix", "citation": _cit()}]},
            {"persona_id": "b", "moves": [
                {"move": "correct", "req_id": "REQ-001",
                 "conditions_of_satisfaction": "same fix", "citation": _cit()}]},
        ]
        r = pm.merge_personas(grounded, _base())
        self.assertEqual(r.conflicts, [])


class ConflictSurfacingTests(unittest.TestCase):
    def _conflict(self, moves_a, moves_b):
        grounded = [
            {"persona_id": "domain-expert", "moves": moves_a},
            {"persona_id": "security-reviewer", "moves": moves_b},
        ]
        return pm.merge_personas(grounded, _base())

    def test_confirm_vs_drop_is_surfaced_not_resolved(self):
        r = self._conflict(
            [{"move": "confirm", "req_id": "REQ-001", "reason": "looks right"}],
            [{"move": "drop", "req_id": "REQ-001", "reason": "obsolete", "citation": _cit()}],
        )
        self.assertEqual(len(r.conflicts), 1)
        c = r.conflicts[0]
        self.assertEqual(c.target, "REQ-001")
        self.assertEqual(sorted(c.personas), ["domain-expert", "security-reviewer"])
        self.assertEqual(len(c.moves), 2)  # BOTH moves carried
        # Neither is applied: REQ-001 still present (not dropped), not confirmed-away.
        self.assertIn("REQ-001", [rec["id"] for rec in r.manifest["records"]])
        self.assertEqual(len(r.held_out), 2)

    def test_divergent_corrects_are_surfaced(self):
        r = self._conflict(
            [{"move": "correct", "req_id": "REQ-002",
              "conditions_of_satisfaction": "fix one way", "citation": _cit()}],
            [{"move": "correct", "req_id": "REQ-002",
              "conditions_of_satisfaction": "fix a different way", "citation": _cit()}],
        )
        self.assertEqual(len(r.conflicts), 1)
        self.assertIn("divergent correct", r.conflicts[0].reason)
        # REQ-002 keeps its ORIGINAL content — neither correction silently won.
        req2 = next(rec for rec in r.manifest["records"]
                    if rec.get("title") == "B")
        self.assertEqual(req2["conditions_of_satisfaction"], "b")

    def test_add_vs_drop_on_same_target_is_surfaced(self):
        # An add proposing to replace REQ-003 vs a drop of REQ-003.
        r = self._conflict(
            [{"move": "add", "target_req": "REQ-003", "section": "Errors",
              "title": "replacement", "conditions_of_satisfaction": "new",
              "citation": _cit()}],
            [{"move": "drop", "req_id": "REQ-003", "citation": _cit()}],
        )
        self.assertEqual(len(r.conflicts), 1)
        # Neither applied: REQ-003 still there, replacement not added.
        self.assertIn("REQ-003", [rec["id"] for rec in r.manifest["records"]])
        self.assertNotIn("replacement", [rec.get("title") for rec in r.manifest["records"]])


class SingleRenumberTests(unittest.TestCase):
    def test_exactly_one_terminal_renumber_reusing_007(self):
        grounded = [
            {"persona_id": "a", "moves": [
                {"move": "add", "section": "Routing", "title": "new-early",
                 "conditions_of_satisfaction": "x", "citation": _cit()}]},
        ]
        with mock.patch.object(
            requirements_render, "renumber_to_document_order",
            wraps=requirements_render.renumber_to_document_order,
        ) as spy:
            # persona_merge composes requirements_render via its own reference;
            # patch that reference too.
            with mock.patch.object(pm.requirements_render, "renumber_to_document_order",
                                   spy):
                r = pm.merge_personas(grounded, _base())
        self.assertEqual(spy.call_count, 1)  # ONCE, not per-persona
        self.assertEqual(r.renumber_calls, 1)
        ids = [rec["id"] for rec in r.manifest["records"]]
        self.assertEqual(ids, [f"REQ-{i:03d}" for i in range(1, len(ids) + 1)])

    def test_renumber_is_document_order_over_the_merged_set(self):
        # An add into an early section renumbers so IDs are sequential in doc order.
        grounded = [
            {"persona_id": "a", "moves": [
                {"move": "add", "section": "Routing", "title": "inserted",
                 "conditions_of_satisfaction": "x", "citation": _cit()}]},
        ]
        r = pm.merge_personas(grounded, _base())
        ids = [rec["id"] for rec in r.manifest["records"]]
        self.assertEqual(ids, ["REQ-001", "REQ-002", "REQ-003", "REQ-004"])
        # The Routing section (3 records now) precedes Errors in document order.
        sections = [rec["functional_section"] for rec in r.manifest["records"]]
        self.assertEqual(sections, ["Routing", "Routing", "Routing", "Errors"])


class ExclusionAndProvenanceTests(unittest.TestCase):
    def test_defer_never_participates(self):
        grounded = [{"persona_id": "a", "moves": [
            {"move": "defer", "req_id": "REQ-001"},
            {"move": "add", "section": "Routing", "title": "kept",
             "conditions_of_satisfaction": "x", "citation": _cit()},
        ]}]
        r = pm.merge_personas(grounded, _base())
        self.assertEqual(len(r.applied), 1)
        self.assertIn("kept", [rec.get("title") for rec in r.manifest["records"]])

    def test_applied_moves_retain_agent_validation_provenance(self):
        grounded = [{"persona_id": "a", "moves": [
            {"move": "add", "section": "Routing", "title": "grounded add",
             "conditions_of_satisfaction": "x", "citation": _cit()},
            {"move": "correct", "req_id": "REQ-001",
             "conditions_of_satisfaction": "corrected", "citation": _cit()},
        ]}]
        r = pm.merge_personas(grounded, _base())
        added = next(rec for rec in r.manifest["records"] if rec.get("title") == "grounded add")
        self.assertEqual(added["source_type"], "agent-validation")
        self.assertEqual(added["citation"], _cit())
        corrected = next(rec for rec in r.manifest["records"]
                         if rec.get("conditions_of_satisfaction") == "corrected")
        self.assertEqual(corrected["source_type"], "agent-validation")

    def test_no_scope_leak_no_review_summary_or_revert(self):
        # This slice produces manifest + conflicts only — no review summary,
        # off-switch, or revert (those are slice 5).
        self.assertFalse(hasattr(pm, "build_review_summary"))
        self.assertFalse(hasattr(pm, "revert"))
        self.assertFalse(hasattr(pm, "off_switch"))


if __name__ == "__main__":
    unittest.main()
