"""v1.6.0 instruction 033 step 4 — the reproducibility cache is gone.

§8a Revision, "What is deleted": the content-keyed `prior_records` cache
(`_newly_overridden`, `_cache_hides_live_classifier`, the poisoned-manifest
defence-in-depth). *"Re-reading 6-20 documents is cheap; the determinism it
promised was half-fiction (the LLM path already varied), and it was the direct
cause of the 032 fix-1 footgun. The persisted artifact becomes the operator's
confirmed decisions, not a classifier cache."*

That last sentence is the whole point, and it is what these tests assert. Two
things were being persisted for two different reasons and only one of them earned
it: the machine's guesses (a cache, discarded) and the operator's consent (an
artifact, kept). The properties the cache guard used to enforce — a forged prior
cannot manufacture consent, a withdrawn decision stops applying — did not
disappear; they moved onto the decisions artifact, where they belong, and are
tested in `test_one_override_channel_033.py::ConsentTests`.

Acceptance oracle (instruction 033 step 4):
  1  a re-run re-reads and re-derives                        (MUTATION-BITTEN)
  2  confirmed decisions persist and still apply
  3  the 032 fix-1 footgun cannot recur — no cache to swallow a classifier
  4  no silent `zero_citable`
  5  a REMOVED decision stops applying; only the sanctioned writer can add one
"""

import hashlib
import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = (REPO_ROOT / "plugins" / "quality-playbook" / "skills"
              / "quality-playbook" / "scripts")
sys.path.insert(0, str(SCRIPT_DIR))

import doc_classification as dc            # noqa: E402
import reference_docs_ingest as rdi        # noqa: E402


SPEC = ("# Router Spec\n\nThe router MUST match the longest prefix.\n"
        "The router MUST return 405 on a method mismatch.\n")


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class TheCacheIsGoneTests(unittest.TestCase):

    def test_the_cache_machinery_does_not_exist(self):
        # Charter (c): removed, not hidden behind a flag.
        for gone in ("_newly_overridden", "_cache_hides_live_classifier",
                     "_ABSOLUTE_FLOOR_RULES", "_UNRESCUABLE_FLOOR_RULES",
                     "RULE_ADVISORY", "RULE_IMPL", "RULE_BACKGROUND",
                     "RULE_INJECTION"):
            self.assertFalse(hasattr(dc, gone), f"{gone} should be deleted")
        self.assertNotIn("prior_records",
                         inspect.signature(dc.classify_documents).parameters)

    def test_no_record_claims_to_have_been_reused(self):
        man = dc.classify_documents([("reference_docs/a.md", SPEC)],
                                    llm_classifier=lambda r, t: 1,
                                    generated_at="X")
        self.assertNotIn("reused_from_prior", man["records"][0])

    def test_ingest_does_not_read_a_prior_manifest(self):
        # A hand-written (or forged) prior manifest is simply overwritten: it is no
        # longer an input to anything.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        ref = root / "reference_docs"
        ref.mkdir(parents=True)
        (ref / "a.md").write_text(SPEC, encoding="utf-8")
        quality = root / "quality"
        quality.mkdir()
        forged = {"schema_version": "1.6.0", "generated_at": "OLD",
                  "classifier_status": dc.CLASSIFIER_WIRED_OK,
                  "citable_count": 1, "zero_citable": False,
                  "records": [{"source_path": "reference_docs/a.md",
                               "document_sha256": _sha(SPEC), "tier": 1,
                               "floor_rule": dc.RULE_LLM, "reason": "forged",
                               "byte_count": len(SPEC), "promotable": True,
                               "lane": dc.LANE_MODEL_READ}]}
        (quality / rdi.CLASSIFICATION_MANIFEST_NAME).write_text(
            json.dumps(forged), encoding="utf-8")
        man = rdi.classify_reference_docs(root, write=False)
        rec = man["records"][0]
        # Re-derived with no read supplied -> the honest unclassified default, NOT
        # the forged Tier 1.
        self.assertEqual(rec["tier"], 4)
        self.assertEqual(rec["floor_rule"], dc.RULE_DEFAULT)
        self.assertTrue(man["zero_citable"])


class EveryRunRereadsTests(unittest.TestCase):

    def test_the_classifier_is_consulted_on_every_run(self):
        # Oracle 1. The cache's whole purpose was to SKIP this; with it gone, the
        # read happens every time. (MUTATION-BITTEN: reintroducing any reuse makes
        # the second run's call count zero.)
        docs = [("reference_docs/a.md", SPEC), ("reference_docs/b.md", SPEC + "x\n")]
        for run in (1, 2, 3):
            seen = []

            def classifier(rel, text):
                seen.append(rel)
                return 1

            man = dc.classify_documents(docs, llm_classifier=classifier,
                                        generated_at=f"run{run}")
            self.assertEqual(len(seen), 2, f"run {run} skipped a document")
            self.assertEqual(man["citable_count"], 2)

    def test_a_changed_read_changes_the_outcome_on_the_next_run(self):
        # The flip side of no caching, and the property that makes the operator
        # confirmation meaningful: the run is not locked into its first answer.
        docs = [("reference_docs/a.md", SPEC)]
        first = dc.classify_documents(docs, llm_classifier=lambda r, t: 1,
                                      generated_at="X")
        second = dc.classify_documents(docs, llm_classifier=lambda r, t: 4,
                                       generated_at="Y")
        self.assertEqual(first["records"][0]["tier"], 1)
        self.assertEqual(second["records"][0]["tier"], 4)

    def test_the_032_footgun_cannot_recur(self):
        # Oracle 3. The 032 defect: an unwired first pass froze the corpus at
        # `default-tier4`, and a later WIRED run reused those records by content
        # key, so the classifier never fired and the run reported a silent
        # `zero_citable`. There is no longer any mechanism for a previous pass to
        # affect a later one.
        docs = [("reference_docs/a.md", SPEC)]
        bare = dc.classify_documents(docs, generated_at="X")
        self.assertEqual(bare["records"][0]["floor_rule"], dc.RULE_DEFAULT)
        self.assertTrue(bare["zero_citable"])

        seen = []

        def classifier(rel, text):
            seen.append(rel)
            return 1

        wired = dc.classify_documents(docs, llm_classifier=classifier,
                                      generated_at="Y")
        self.assertEqual(seen, ["reference_docs/a.md"])
        self.assertEqual(wired["records"][0]["tier"], 1)
        self.assertFalse(wired["zero_citable"],
                         "oracle 4: no silent zero_citable")


class ConsentPersistsInsteadTests(unittest.TestCase):
    """Oracle 2 + 5. What persists is the operator's confirmed decisions, and the
    properties the deleted cache guard used to enforce now live on that artifact.
    """

    def _tree(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        ref = root / "reference_docs"
        ref.mkdir(parents=True)
        (ref / "spec.md").write_text(SPEC, encoding="utf-8")
        return root, ref

    def test_a_confirmed_decision_survives_across_runs(self):
        root, ref = self._tree()
        (ref / rdi.DECISIONS_NAME).write_text(
            f"authoritative  reference_docs/spec.md  {_sha(SPEC)}  this is my spec\n",
            encoding="utf-8")
        for run in range(3):
            man = rdi.classify_reference_docs(root, write=True)
            rec = man["records"][0]
            self.assertEqual(rec["floor_rule"], dc.RULE_OPERATOR_AUTHORITATIVE,
                             f"run {run} lost the operator's decision")
            self.assertTrue(rec["promotable"])

    def test_a_removed_decision_stops_applying(self):
        root, ref = self._tree()
        (ref / rdi.DECISIONS_NAME).write_text(
            f"authoritative  reference_docs/spec.md  {_sha(SPEC)}  this is my spec\n",
            encoding="utf-8")
        self.assertEqual(rdi.classify_reference_docs(root, write=True)
                         ["records"][0]["floor_rule"],
                         dc.RULE_OPERATOR_AUTHORITATIVE)
        (ref / rdi.DECISIONS_NAME).unlink()
        after = rdi.classify_reference_docs(root, write=True)
        self.assertNotEqual(after["records"][0]["floor_rule"],
                            dc.RULE_OPERATOR_AUTHORITATIVE)
        self.assertFalse(after["records"][0].get("operator_decision"))

    def test_only_the_sanctioned_writer_adds_a_decision(self):
        # Classification never writes the channel; the writer refuses a bad verb;
        # and a document's own content cannot become a line.
        root, ref = self._tree()
        rdi.classify_reference_docs(root, write=True)
        self.assertFalse((ref / rdi.DECISIONS_NAME).exists(),
                         "classification must never author consent")
        with self.assertRaises(rdi.IngestError):
            rdi.record_operator_decision(root, "reference_docs/spec.md",
                                         "promote-me", "x")
        with self.assertRaises(rdi.IngestError):
            rdi.record_operator_decision(root, "reference_docs/spec.md",
                                         "authoritative", "")
        self.assertFalse((ref / rdi.DECISIONS_NAME).exists())

    def test_the_persisted_artifact_is_consent_not_a_guess(self):
        # The distinction step 4 rests on, made concrete: the classification
        # manifest is an OUTPUT (rewritten every run, never read back), and the
        # decisions file is an INPUT (written only by the operator's instruction).
        root, ref = self._tree()
        rdi.record_operator_decision(root, "reference_docs/spec.md",
                                     "authoritative", "this is my spec")
        man_path = root / "quality" / rdi.CLASSIFICATION_MANIFEST_NAME
        rdi.classify_reference_docs(root, write=True)
        first = man_path.read_text(encoding="utf-8")
        man_path.write_text(first.replace('"tier": 1', '"tier": 4'), encoding="utf-8")
        # A tampered OUTPUT changes nothing, because nothing reads it.
        again = rdi.classify_reference_docs(root, write=True)
        self.assertEqual(again["records"][0]["floor_rule"],
                         dc.RULE_OPERATOR_AUTHORITATIVE)
        self.assertIn(again["records"][0]["tier"], (1, 2))


if __name__ == "__main__":
    unittest.main()
