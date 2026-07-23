"""v1.6.0 Feature H (instruction 021) — the composed pipeline step run_feature_h.

Tests the composition deterministically by STUBBING the persona sub-agent spawn
(canned diff-sets), like instruction 019 tests the mechanism without a live model.
Asserts the composed step: selects with anchors, stages ISOLATED inputs + spawns
tool-restricted, classifies grounded/candidate, merges with one renumber, applies
+ writes the review-summary artifact, and the off-switch no-ops the whole step.
"""

import hashlib
import json
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
from bin import citation_verifier as cv  # noqa: E402


_SPEC_TXT = (
    "Router specification\n"
    "\n"
    "Path parameters may use a regular-expression constraint of the form\n"
    "{name:pattern}; the router MUST compile and match the pattern per segment.\n"
)


class PipelineBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "reference_docs").mkdir()
        (self.root / "reference_docs" / "spec.txt").write_text(_SPEC_TXT, encoding="utf-8")
        self.sha = hashlib.sha256(_SPEC_TXT.encode("utf-8")).hexdigest()
        self.formal_docs = [{
            "source_path": "reference_docs/spec.txt",
            "document_sha256": self.sha, "tier": 1, "citation_excerpt": "",
        }]
        self.base = {"records": [
            {"id": "REQ-001", "functional_section": "Routing", "title": "named params",
             "conditions_of_satisfaction": "x", "source_type": "code-derived"},
        ]}

    def _provision(self, persona):
        return [
            po.StagedInput("REQUIREMENTS.md", "# Requirements\n\n### REQ-001: named params\n"),
            po.StagedInput("spec.txt", _SPEC_TXT),
            po.StagedInput("rubric.md", "# Rubric\n\nComplete Honest Consistent Correct\n"),
        ]

    def _grounded_citation(self):
        line = next(i + 1 for i, l in enumerate(_SPEC_TXT.splitlines())
                    if "regular-expression" in l)
        excerpt = cv.extract_excerpt(_SPEC_TXT.encode("utf-8"), ".txt", None, line)
        return {"document": "reference_docs/spec.txt", "document_sha256": self.sha,
                "citation_excerpt": excerpt, "line": line}

    def _spawn(self, records_seen=None):
        """A canned persona spawn: emits one grounded add citing the staged spec."""
        def spawn(persona, staging_dir, tool_config):
            if records_seen is not None:
                names = {p.name for p in Path(staging_dir).iterdir()}
                records_seen.append((persona["id"], names, tool_config.denies("Bash"),
                                     tool_config.denies("fetch")))
            return {"persona_id": persona["id"], "moves": [
                {"move": "add", "section": "Routing", "title": "regexp params",
                 "conditions_of_satisfaction": "params support {name:pattern}",
                 "reason": "documented contract",
                 "system_justification": "this router documents regexp params",
                 "citation": self._grounded_citation()},
            ]}
        return spawn


class ComposedPassTests(PipelineBase):
    def test_run_feature_h_end_to_end(self):
        proposed = [{"id": "domain-expert", "justification": "router",
                     "specialization": "Go HTTP routing"}]
        result = pa.run_feature_h(
            self.root, base_manifest=self.base, proposed_personas=proposed,
            provision=self._provision, spawn_persona=self._spawn(),
            formal_docs=self.formal_docs, staging_root=self.root / "_staging")
        # A grounded add was applied, tagged agent-validation with its citation.
        added = next(r for r in result.manifest["records"] if r.get("title") == "regexp params")
        self.assertEqual(added["source_type"], "agent-validation")
        self.assertTrue(added.get("citation"))
        # The review-summary artifact was written to quality/.
        art = self.root / "quality" / pa.REVIEW_SUMMARY_NAME
        self.assertTrue(art.is_file())
        summary = json.loads(art.read_text(encoding="utf-8"))
        self.assertEqual(summary["applied_count"], 1)
        self.assertTrue(any(a["title"] == "regexp params" for a in summary["applied"]))

    def test_selection_forces_anchors_through_the_composition(self):
        # Only the domain lens was proposed; the security anchor must still run
        # (its spawn is invoked) — proving selection's anchors flow through.
        seen = []
        pa.run_feature_h(
            self.root, base_manifest=self.base,
            proposed_personas=[{"id": "domain-expert", "justification": "r"}],
            provision=self._provision, spawn_persona=self._spawn(seen),
            formal_docs=self.formal_docs, staging_root=self.root / "_staging")
        spawned_ids = {pid for pid, _n, _b, _f in seen}
        self.assertIn("domain-expert", spawned_ids)
        self.assertIn("security-reviewer", spawned_ids)  # anchored, forced in

    def test_isolation_honored_through_the_composition(self):
        seen = []
        pa.run_feature_h(
            self.root, base_manifest=self.base,
            proposed_personas=[{"id": "domain-expert", "justification": "r"}],
            provision=self._provision, spawn_persona=self._spawn(seen),
            formal_docs=self.formal_docs, staging_root=self.root / "_staging")
        for pid, names, denies_bash, denies_fetch in seen:
            # Each spawn got ONLY the staged inputs and a tool-restricted config.
            self.assertEqual(names, {"REQUIREMENTS.md", "spec.txt", "rubric.md"})
            self.assertTrue(denies_bash and denies_fetch)

    def test_ungrounded_move_is_candidate_not_applied(self):
        def spawn_no_citation(persona, staging_dir, tool_config):
            return {"persona_id": persona["id"], "moves": [
                {"move": "add", "section": "Routing", "title": "hunch",
                 "system_justification": "feels right"}]}  # no citation -> candidate
        result = pa.run_feature_h(
            self.root, base_manifest=self.base,
            proposed_personas=[{"id": "domain-expert", "justification": "r"}],
            provision=self._provision, spawn_persona=spawn_no_citation,
            formal_docs=self.formal_docs, staging_root=self.root / "_staging")
        titles = [r.get("title") for r in result.manifest["records"]]
        self.assertNotIn("hunch", titles)  # candidate, not applied
        self.assertTrue(any(c["move"] == "add" for c in result.review_summary["candidates"]))


class OffSwitchThroughCompositionTests(PipelineBase):
    def test_disabled_run_does_nothing_and_writes_no_artifact(self):
        spawned = []
        def spawn(persona, staging_dir, tool_config):
            spawned.append(persona["id"])
            return {"persona_id": persona["id"], "moves": []}
        pre = json.loads(json.dumps(self.base))
        result = pa.run_feature_h(
            self.root, base_manifest=self.base,
            proposed_personas=[{"id": "domain-expert", "justification": "r"}],
            provision=self._provision, spawn_persona=spawn,
            formal_docs=self.formal_docs, staging_root=self.root / "_staging",
            enabled=False)
        self.assertFalse(result.enabled)
        self.assertEqual(spawned, [])                     # no personas spawned
        self.assertEqual(self.base["records"], pre["records"])  # base untouched
        self.assertIsNone(result.review_summary)
        self.assertFalse((self.root / "quality" / pa.REVIEW_SUMMARY_NAME).exists())

    def test_enabled_is_the_default(self):
        import inspect
        sig = inspect.signature(pa.run_feature_h)
        self.assertTrue(sig.parameters["enabled"].default)


if __name__ == "__main__":
    unittest.main()
