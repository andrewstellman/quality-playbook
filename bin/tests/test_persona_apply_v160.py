"""v1.6.0 Feature H slice 5 (instruction 017) — Guard 4: apply + review summary +
concrete revert + off-switch. Covers §8b Verification 8: applied+tagged; remap
propagation to BUG cross-refs; review-summary completeness; revert round-trip;
off-switch no-op; downstream attributability.
"""

import copy
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = (
    REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook" / "scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))

import persona_apply as pa  # noqa: E402


def _base():
    return {"records": [
        {"id": "REQ-001", "functional_section": "Routing", "title": "A",
         "conditions_of_satisfaction": "a", "source_type": "code-derived"},
        {"id": "REQ-002", "functional_section": "Routing", "title": "B",
         "conditions_of_satisfaction": "b", "source_type": "code-derived"},
        {"id": "REQ-003", "functional_section": "Errors", "title": "C",
         "conditions_of_satisfaction": "c", "source_type": "code-derived"},
    ]}


def _bugs():
    return {"records": [
        {"id": "BUG-001", "req_id": "REQ-003", "covers": ["REQ-003/cell-1-1"]},
    ]}


def _cit():
    return {"document": "reference_docs/spec.txt", "citation_excerpt": "x"}


def _grounded_add_into_routing():
    return [{"persona_id": "domain-expert", "moves": [
        {"move": "add", "section": "Routing", "title": "regexp params",
         "conditions_of_satisfaction": "params support {name:pattern}",
         "reason": "real contract", "system_justification": "chi exposes it",
         "citation": _cit()}]}]


class ApplyTaggingTests(unittest.TestCase):
    def test_grounded_moves_applied_as_agent_validation(self):
        p = pa.run_persona_pass(_base(), _grounded_add_into_routing(), _bugs())
        added = next(r for r in p.manifest["records"] if r.get("title") == "regexp params")
        self.assertEqual(added["source_type"], "agent-validation")
        self.assertEqual(added["citation"], _cit())

    def test_agent_validation_not_coalesced_with_operator_confirmation(self):
        p = pa.run_persona_pass(_base(), _grounded_add_into_routing(), _bugs())
        av = pa.agent_validation_records(p.manifest)
        self.assertEqual(len(av), 1)
        self.assertNotEqual(av[0]["source_type"], "operator-confirmation")


class RemapPropagationTests(unittest.TestCase):
    def test_bug_cross_refs_updated_after_renumber(self):
        # The add into Routing shifts the Errors REQ-003 to REQ-004; the BUG
        # pointing at REQ-003 must follow the remap — no orphaned link.
        base, bugs = _base(), _bugs()
        p = pa.run_persona_pass(base, _grounded_add_into_routing(), bugs)
        self.assertIn("REQ-003", p.remap)  # the Errors REQ moved
        new_id = p.remap["REQ-003"]
        bug = bugs["records"][0]
        self.assertEqual(bug["req_id"], new_id)
        self.assertEqual(bug["covers"], [f"{new_id}/cell-1-1"])
        # ...and the Errors requirement actually carries that new id now.
        errors_req = next(r for r in p.manifest["records"] if r["title"] == "C")
        self.assertEqual(errors_req["id"], new_id)

    def test_no_orphaned_bug_link(self):
        base, bugs = _base(), _bugs()
        pa.run_persona_pass(base, _grounded_add_into_routing(), bugs)
        live_ids = {r["id"] for r in base["records"]}
        self.assertIn(bugs["records"][0]["req_id"], live_ids)  # points at a live REQ


class ReviewSummaryTests(unittest.TestCase):
    def test_summary_lists_every_applied_change_plus_conflicts_and_candidates(self):
        grounded = [
            {"persona_id": "domain-expert", "moves": [
                {"move": "add", "section": "Routing", "title": "add1",
                 "conditions_of_satisfaction": "x", "citation": _cit(),
                 "system_justification": "j"}]},
            # a conflict pair on REQ-001
            {"persona_id": "security-reviewer", "moves": [
                {"move": "drop", "req_id": "REQ-001", "citation": _cit()}]},
            {"persona_id": "operator-sre", "moves": [
                {"move": "confirm", "req_id": "REQ-001", "reason": "fine"}]},
        ]
        candidates = [{"persona_id": "security-reviewer", "move": "add",
                       "shortfall": "no citation"}]
        p = pa.run_persona_pass(_base(), grounded, _bugs(), candidate_bucket=candidates)
        s = p.review_summary
        # every applied change is listed with grounding
        self.assertEqual(s["applied_count"], len(s["applied"]))
        self.assertTrue(any(a["title"] == "add1" and a["system_justification"] == "j"
                            for a in s["applied"]))
        # the drop/confirm conflict on REQ-001 is surfaced (not applied)
        self.assertGreaterEqual(s["conflict_count"], 1)
        self.assertTrue(any(c["target"] == "REQ-001" for c in s["conflicts"]))
        # the candidate bucket is included
        self.assertEqual(s["candidates"], candidates)
        # REQ-001 was NOT dropped (conflict held out)
        self.assertIn("REQ-001", [r["id"] for r in p.manifest["records"]])


class RevertRoundTripTests(unittest.TestCase):
    def test_revert_all_restores_pre_persona_including_correct_and_drop(self):
        base, bugs = _base(), _bugs()
        pre_req = copy.deepcopy(base)
        pre_bugs = copy.deepcopy(bugs)
        grounded = [{"persona_id": "domain-expert", "moves": [
            {"move": "add", "section": "Routing", "title": "new", "citation": _cit(),
             "conditions_of_satisfaction": "n", "system_justification": "j"},
            {"move": "correct", "req_id": "REQ-001",
             "conditions_of_satisfaction": "CORRECTED", "citation": _cit()},
            {"move": "drop", "req_id": "REQ-002", "citation": _cit()},
        ]}]
        p = pa.run_persona_pass(base, grounded, bugs)
        # sanity: the pass changed things.
        self.assertNotEqual(base["records"], pre_req["records"])
        req, rb = pa.revert(p, bugs, which="all")
        # Full round-trip: requirements + bugs restored to pre-persona state.
        self.assertEqual(req["records"], pre_req["records"])
        self.assertEqual(rb["records"], pre_bugs["records"])

    def test_revert_selected_drops_one_agent_validation_add(self):
        base, bugs = _base(), _bugs()
        grounded = [{"persona_id": "a", "moves": [
            {"move": "add", "section": "Routing", "title": "keep", "citation": _cit(),
             "conditions_of_satisfaction": "k"},
            {"move": "add", "section": "Errors", "title": "remove-me", "citation": _cit(),
             "conditions_of_satisfaction": "r"},
        ]}]
        p = pa.run_persona_pass(base, grounded, bugs)
        remove_id = next(r["id"] for r in p.manifest["records"] if r["title"] == "remove-me")
        req, _ = pa.revert(p, bugs, which=[remove_id])
        titles = [r.get("title") for r in req["records"]]
        self.assertNotIn("remove-me", titles)
        self.assertIn("keep", titles)  # the other add stays
        # still sequential after the re-renumber
        ids = [r["id"] for r in req["records"]]
        self.assertEqual(ids, [f"REQ-{i:03d}" for i in range(1, len(ids) + 1)])

    def test_revert_selected_cannot_drop_a_non_agent_validation_req(self):
        # Only agent-validation records are revertible — a code-derived REQ id
        # in `which` is ignored (revert cannot remove original requirements).
        base, bugs = _base(), _bugs()
        p = pa.run_persona_pass(base, _grounded_add_into_routing(), bugs)
        req, _ = pa.revert(p, bugs, which=["REQ-001"])  # REQ-001 is code-derived
        self.assertTrue(any(r.get("title") == "A" for r in req["records"]))


class OffSwitchTests(unittest.TestCase):
    def test_disabled_pass_does_nothing(self):
        base, bugs = _base(), _bugs()
        pre = copy.deepcopy(base)
        p = pa.run_persona_pass(base, _grounded_add_into_routing(), bugs, enabled=False)
        self.assertFalse(p.enabled)
        self.assertIsNone(p.review_summary)
        # No agent-validation changes; the base manifest is untouched.
        self.assertEqual(base["records"], pre["records"])
        self.assertEqual(pa.agent_validation_records(base), [])


if __name__ == "__main__":
    unittest.main()
