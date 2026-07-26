"""v1.6.0 Feature H slice 1 (instruction 013) — persona catalog + anchored selection.

Covers the slice acceptance oracle: the catalog enumerates anchored + selectable
lenses each with a criterion (data-first); anchor enforcement is mechanical and
test-proven (an adversarial selection omitting a lens still yields it); the
selection recorder produces a reviewable record; a sample selection over a real
repo's shape is sensible.
"""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = (
    REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook" / "scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))

import persona_catalog as pc  # noqa: E402


class CatalogShapeTests(unittest.TestCase):
    def test_two_anchored_lenses_domain_and_security(self):
        anchored = [e["id"] for e in pc.catalog() if e["anchored"]]
        self.assertEqual(set(anchored), {pc.DOMAIN_EXPERT, pc.SECURITY_REVIEWER})
        self.assertEqual(set(pc.anchored_ids()), {pc.DOMAIN_EXPERT, pc.SECURITY_REVIEWER})

    def test_selectable_lenses_present_each_with_a_criterion(self):
        selectable = [e for e in pc.catalog() if not e["anchored"]]
        ids = {e["id"] for e in selectable}
        # The §8b-named additional lenses are all present.
        for expected in ("api-consumer", "operator-sre", "data-privacy",
                         "accessibility", "performance", "reliability", "adopter"):
            self.assertIn(expected, ids)
        # Every catalog entry carries a non-empty select_when criterion.
        for e in pc.catalog():
            self.assertTrue(e["select_when"].strip(), e["id"])

    def test_catalog_is_data_first(self):
        # A lens is a dict entry — adding one is a data edit, no code surgery.
        for e in pc.catalog():
            self.assertEqual(set(e) >= {"id", "anchored", "title", "select_when"}, True, e)

    def test_catalog_copy_is_not_the_source(self):
        c = pc.catalog()
        c[0]["title"] = "MUTATED"
        self.assertNotEqual(pc.catalog()[0]["title"], "MUTATED")


class AnchorEnforcementTests(unittest.TestCase):
    def test_selection_omitting_security_still_contains_it(self):
        # Adversarial: the LLM proposes only the domain lens + an extra.
        proposed = [
            {"id": pc.DOMAIN_EXPERT, "justification": "routing library"},
            {"id": "api-consumer", "justification": "public API"},
        ]
        ids = {e["id"] for e in pc.select_personas(proposed)}
        self.assertIn(pc.SECURITY_REVIEWER, ids)
        self.assertIn(pc.DOMAIN_EXPERT, ids)

    def test_selection_omitting_domain_still_contains_it(self):
        proposed = [{"id": pc.SECURITY_REVIEWER, "justification": "x"}]
        ids = {e["id"] for e in pc.select_personas(proposed)}
        self.assertIn(pc.DOMAIN_EXPERT, ids)
        self.assertIn(pc.SECURITY_REVIEWER, ids)

    def test_empty_selection_still_yields_both_anchors(self):
        ids = {e["id"] for e in pc.select_personas([])}
        self.assertEqual(ids, {pc.DOMAIN_EXPERT, pc.SECURITY_REVIEWER})

    def test_hallucinated_lens_is_dropped_not_added(self):
        proposed = [{"id": "chaos-monkey", "justification": "made up"}]
        ids = {e["id"] for e in pc.select_personas(proposed)}
        self.assertNotIn("chaos-monkey", ids)
        # ...but the anchors are still enforced.
        self.assertEqual(ids, {pc.DOMAIN_EXPERT, pc.SECURITY_REVIEWER})

    def test_anchor_enforcement_is_load_bearing(self):
        # The security lens is present because of the anchor, not because it was
        # proposed — prove it by omitting it and confirming it is flagged anchored.
        selected = pc.select_personas([{"id": "performance", "justification": "hot path"}])
        sec = next(e for e in selected if e["id"] == pc.SECURITY_REVIEWER)
        self.assertTrue(sec["anchored"])
        self.assertIn("anchored", sec["justification"].lower())


class SelectionRecordTests(unittest.TestCase):
    def test_manifest_is_reviewable_and_lists_lenses_with_justification(self):
        selected = pc.select_personas([
            {"id": pc.DOMAIN_EXPERT, "justification": "an HTTP router library",
             "specialization": "expert in Go HTTP routing and net/http"},
            {"id": "api-consumer", "justification": "consumed as a library"},
        ])
        man = pc.build_selection_manifest(selected, generated_at="X")
        self.assertEqual(set(man) >= {"schema_version", "generated_at",
                                      "selection_sha256", "records"}, True)
        by_id = {r["id"]: r for r in man["records"]}
        self.assertIn(pc.SECURITY_REVIEWER, by_id)  # anchored, present
        self.assertTrue(by_id[pc.DOMAIN_EXPERT]["justification"])
        self.assertEqual(by_id[pc.DOMAIN_EXPERT]["specialization"],
                         "expert in Go HTTP routing and net/http")
        for r in man["records"]:
            self.assertIn("anchored", r)

    def test_manifest_is_content_keyed_reproducible(self):
        sel = pc.select_personas([{"id": "performance", "justification": "hot path"}])
        a = pc.build_selection_manifest(sel, generated_at="X")
        b = pc.build_selection_manifest(sel, generated_at="Y")
        self.assertEqual(a["selection_sha256"], b["selection_sha256"])
        self.assertEqual(a["records"], b["records"])


class SampleSelectionTests(unittest.TestCase):
    def test_library_yields_domain_security_and_api_consumer(self):
        # chi/express are consumed-as-a-library systems: domain + security
        # anchored, plus API/consumer with a stated reason — a sensible set.
        selected = pc.select_personas([
            {"id": pc.DOMAIN_EXPERT, "justification": "an HTTP router library",
             "specialization": "expert in Go HTTP routing"},
            {"id": "api-consumer",
             "justification": "chi is consumed feature-by-feature as a library"},
        ])
        ids = [e["id"] for e in selected]
        self.assertIn(pc.DOMAIN_EXPERT, ids)
        self.assertIn(pc.SECURITY_REVIEWER, ids)
        self.assertIn("api-consumer", ids)
        # anchored lenses render first.
        self.assertEqual(ids[0], pc.DOMAIN_EXPERT)
        self.assertEqual(ids[1], pc.SECURITY_REVIEWER)


if __name__ == "__main__":
    unittest.main()
