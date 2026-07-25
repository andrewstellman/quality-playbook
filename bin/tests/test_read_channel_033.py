"""v1.6.0 instruction 033 — WHERE THE READ LIVES (self-Council panelist B, B-1).

Step 2 makes classification the derivation model's read. Step 4 removed the
`prior_records` cache. Between them the agent was left with no way to get its read
INTO a run: the only input was the Python callable `llm_classifier`, and an agent
acts through files and shell commands, not by passing closures. No production
caller supplied one — every `llm_classifier=` outside the two scripts was in
`bin/tests/`.

So Lane B, the central mechanism of this instruction, could not reach a
byte-citable `FORMAL_DOC` in the shipped flow. There was no ordering that worked:
ingest-then-read leaves `formal_docs_manifest.json` empty (the record is created
during ingest, and the read arrives after), while read-then-ingest has the ingest
regenerate the manifest and destroy the read. Re-ingesting a copy of the real
`repos/chi-1.6.0` corpus took FORMAL_DOC from two Tier-1 records to zero with
`zero_citable` true; express and virtio behaved the same, and virtio's document is
`virtio-spec-behavioral-contracts.md` — the case §8a names as the motivation for
the whole classification review.

The channel is `quality/classification_reads.json`, agent-authored, consumed by the
ingest that follows it. The hard question is why this is not the cache step 4 just
deleted, and the answer has to be mechanical rather than a promise — which is what
`NotTheCacheAgainTests` below is for:

  * a read is CONTENT-KEYED, so it applies to the exact bytes it was made against;
  * a document with no matching entry is UNREAD and LOUD, never quietly defaulted;
  * ingest never writes the file, so no machine judgment persists by itself;
  * and a read is a judgment, not a permission — it reaches Lane B and stops.
"""

import hashlib
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
CVE_SPEC = SPEC + "Security considerations: see CVE-2024-43796.\n"


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ReadChannelTestCase(unittest.TestCase):

    def _tree(self, files=None):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        ref = root / "reference_docs"
        ref.mkdir(parents=True)
        (root / "quality").mkdir()
        for name, text in (files or {"spec.md": SPEC}).items():
            path = ref / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return root, ref

    def _write_reads(self, root, entries):
        (root / "quality" / rdi.READS_NAME).write_text(
            json.dumps(entries, indent=2), encoding="utf-8")

    def _read(self, rel, text, tier=1, **extra):
        entry = {"source_path": rel, "document_sha256": _sha(text),
                 "tier": tier, "category": "specification",
                 "reason": "I read this as the spec the code must match."}
        entry.update(extra)
        return entry

    def _rec(self, root, rel):
        man = rdi.classify_reference_docs(root, write=True)
        return next(r for r in man["records"] if r["source_path"] == rel), man


class TheRegressionItselfTests(ReadChannelTestCase):
    """B-1's acceptance oracle: the read reaches a byte-citable record."""

    def test_a_read_produces_a_byte_citable_formal_doc_in_the_same_run(self):
        root, _ref = self._tree()
        rel = "reference_docs/spec.md"
        self._write_reads(root, [self._read(rel, SPEC)])
        rdi.ingest(root)
        formal = json.loads(
            (root / "quality" / "formal_docs_manifest.json").read_text())["records"]
        self.assertEqual([r["source_path"] for r in formal], [rel],
                         "the read must reach the byte-citable surface")

    def test_the_read_is_disclosed_as_lane_B_and_unconfirmed(self):
        # It is cited AND it is never presented as settled — reworded invariant 1.
        root, _ref = self._tree()
        rel = "reference_docs/spec.md"
        self._write_reads(root, [self._read(rel, SPEC)])
        rec, man = self._rec(root, rel)
        self.assertEqual(rec["floor_rule"], dc.RULE_LLM)
        self.assertEqual(rec["lane"], dc.LANE_MODEL_READ)
        self.assertEqual(rec["confirmation"], dc.UNCONFIRMED)
        self.assertEqual(man["unconfirmed_citable_count"], 1)
        self.assertFalse(man["zero_citable"])
        self.assertEqual(man["classifier_status"], dc.CLASSIFIER_WIRED_OK)

    def test_the_reason_and_category_survive_into_the_record(self):
        root, _ref = self._tree()
        rel = "reference_docs/spec.md"
        self._write_reads(root, [self._read(rel, SPEC, category="api-reference",
                                            reason="It is the published API.")])
        rec, _man = self._rec(root, rel)
        self.assertEqual(rec.get("category"), "api-reference")
        self.assertEqual(rec.get("model_reason"), "It is the published API.")

    def test_a_demotion_read_lands_too(self):
        # Demotion is free (§8a rule 2) through this channel like any other.
        root, _ref = self._tree()
        rel = "reference_docs/spec.md"
        self._write_reads(root, [self._read(rel, SPEC, tier=4, category="chat-log")])
        rec, man = self._rec(root, rel)
        self.assertEqual(rec["tier"], 4)
        self.assertTrue(man["zero_citable"])


class NotTheCacheAgainTests(ReadChannelTestCase):
    """The properties that distinguish a read channel from the deleted cache.

    Step 4 deleted `prior_records` because a persisted machine judgment silently
    substituted for a live one — the 032 footgun, where an unwired first pass froze
    the corpus at `default-tier4` and a later WIRED run reused those records, so the
    classifier never fired and the run reported a silent `zero_citable`. Restoring a
    persisted artifact without restoring that failure mode is the whole design
    problem, so each guard is asserted rather than asserted-about.
    """

    def test_a_read_does_not_apply_to_DIFFERENT_bytes(self):
        # The property the deleted cache is most often confused with. Edit the
        # document and its read stops applying — silently promoting the new bytes on
        # the old read is exactly the swap attack the operator channel refuses.
        root, ref = self._tree()
        rel = "reference_docs/spec.md"
        self._write_reads(root, [self._read(rel, SPEC)])
        rec, _man = self._rec(root, rel)
        self.assertEqual(rec["tier"], 1)
        (ref / "spec.md").write_text(SPEC + "\nAnd something else entirely.\n",
                                     encoding="utf-8")
        rec2, man2 = self._rec(root, rel)
        self.assertEqual(rec2["floor_rule"], dc.RULE_DEFAULT)
        self.assertTrue(man2["zero_citable"])

    def test_an_unread_document_is_loud_not_defaulted_and_forgotten(self):
        # A PARTIALLY read corpus, which is the ordinary case while the agent works
        # through it. The unread document must be distinguishable in the manifest
        # from one the agent read and judged background — `default-tier4` says
        # "nobody looked", `llm` says "I looked and this is context".
        root, _ref = self._tree({"spec.md": SPEC, "other.md": SPEC + "x\n"})
        self._write_reads(root, [self._read("reference_docs/spec.md", SPEC)])
        man = rdi.classify_reference_docs(root, write=True)
        other = next(r for r in man["records"]
                     if r["source_path"] == "reference_docs/other.md")
        self.assertEqual(other["floor_rule"], dc.RULE_DEFAULT)
        # ...and an unread document is NOT a broken classifier. The bite log caught
        # this: mutating the "no matching entry" branch away made the synthesized
        # callable raise, which `classify_documents` correctly reports as
        # `classifier_status: error` — a whole-corpus alarm raised by one ordinary
        # unread file. Silence about the read and a false alarm about the classifier
        # are both misreports; the status has to say which actually happened.
        self.assertEqual(man["classifier_status"], dc.CLASSIFIER_WIRED_OK)
        self.assertNotIn("classifier_error", man)
        read_one = next(r for r in man["records"]
                        if r["source_path"] == "reference_docs/spec.md")
        self.assertEqual(read_one["floor_rule"], dc.RULE_LLM)

    def test_no_reads_at_all_is_the_loud_unwired_path(self):
        # The 032 footgun's signature, preserved: no read means the run SAYS it has
        # no read, rather than presenting an unread corpus as a classified one.
        root, _ref = self._tree()
        man = rdi.classify_reference_docs(root, write=True)
        self.assertEqual(man["classifier_status"], dc.CLASSIFIER_UNWIRED)
        self.assertTrue(man["zero_citable"])

    def test_ingest_never_writes_the_read_file(self):
        # Nothing the machine decides persists here by itself. If ingest could write
        # this file, one run's guess would become the next run's input and it WOULD
        # be the cache again.
        root, _ref = self._tree()
        rdi.ingest(root)
        self.assertFalse((root / "quality" / rdi.READS_NAME).exists())
        rdi.classify_reference_docs(root, write=True)
        self.assertFalse((root / "quality" / rdi.READS_NAME).exists())

    def test_a_SECOND_run_reuses_the_artifact_deliberately(self):
        """Panelist B (B2-2): cross-run reuse was untested, so it was incidental.

        It is intended — the artifact is the agent's read of bytes that have not
        changed, and re-reading an unchanged corpus to reach the same answer is the
        cost step 4 declined to pay in the other direction. What makes it safe is
        not content-keying (the DELETED CACHE was content-keyed too — that was its
        defining feature) but that ingest never writes this file: no run persists
        its own verdict here, so nothing the machine guessed can stand in for
        reading. Pinned so the behaviour is chosen rather than merely observed.
        """
        root, _ref = self._tree()
        rel = "reference_docs/spec.md"
        self._write_reads(root, [self._read(rel, SPEC)])
        for run in range(3):
            rec, man = self._rec(root, rel)
            self.assertEqual(rec["floor_rule"], dc.RULE_LLM, f"run {run}")
            self.assertEqual(man["classifier_status"], dc.CLASSIFIER_WIRED_OK)
        # ...and the artifact is still the agent's, untouched by any of them.
        self.assertEqual(
            json.loads((root / "quality" / rdi.READS_NAME).read_text()),
            [self._read(rel, SPEC)])

    def test_the_corpus_says_how_many_documents_nobody_read(self):
        # Panelist B (B2-3): property 2 held per-record but nothing aggregated it,
        # so a run that read 3 of 10 reported `wired-ok` / `zero_citable: false`
        # with no surface anywhere saying seven were never looked at — the closest
        # of all these gaps to the 032 footgun's actual shape.
        root, _ref = self._tree({"spec.md": SPEC, "a.md": SPEC + "a\n",
                                 "b.md": SPEC + "b\n"})
        self._write_reads(root, [self._read("reference_docs/spec.md", SPEC)])
        man = rdi.classify_reference_docs(root, write=True)
        self.assertEqual(man["unread_count"], 2)
        self.assertEqual(man["classifier_status"], dc.CLASSIFIER_WIRED_OK)
        self.assertFalse(man["zero_citable"])
        # A fully-read corpus reports zero, so the number is signal not noise.
        self._write_reads(root, [
            self._read("reference_docs/spec.md", SPEC),
            self._read("reference_docs/a.md", SPEC + "a\n", tier=4),
            self._read("reference_docs/b.md", SPEC + "b\n", tier=4)])
        self.assertEqual(
            rdi.classify_reference_docs(root, write=True)["unread_count"], 0)

    def test_an_explicit_callable_still_wins(self):
        # The artifact is a shape for the callable, not a replacement for it.
        root, _ref = self._tree()
        rel = "reference_docs/spec.md"
        self._write_reads(root, [self._read(rel, SPEC, tier=1)])
        man = rdi.classify_reference_docs(root, write=False,
                                          llm_classifier=lambda p, t: 4)
        self.assertEqual(man["records"][0]["tier"], 4)


class AReadIsAJudgmentNotAPermissionTests(ReadChannelTestCase):
    """The channel must not become a second consent channel by the back door.

    Instruction 033 step 3 collapsed four override channels into one precisely so
    there would be one place consent lives. A read artifact that could clear a
    backstop signal, or stand in for the operator's word, would quietly make two.
    """

    def test_a_read_cannot_clear_a_backstop_signal(self):
        root, _ref = self._tree({"cve_spec.md": CVE_SPEC})
        rel = "reference_docs/cve_spec.md"
        self._write_reads(root, [self._read(rel, CVE_SPEC, tier=1)])
        rec, man = self._rec(root, rel)
        self.assertEqual(rec["floor_rule"], dc.RULE_CONFIRM_REQUIRED)
        self.assertFalse(rec["promotable"])
        self.assertTrue(man["zero_citable"])

    def test_a_read_is_never_operator_consent(self):
        root, _ref = self._tree()
        rel = "reference_docs/spec.md"
        self._write_reads(root, [self._read(rel, SPEC, tier=1)])
        rec, _man = self._rec(root, rel)
        self.assertNotEqual(rec["floor_rule"], dc.RULE_OPERATOR_AUTHORITATIVE)
        self.assertEqual(rec["confirmation"], dc.UNCONFIRMED)
        self.assertFalse((root / "reference_docs" / rdi.DECISIONS_NAME).exists(),
                         "a read must never author the consent channel")

    def test_a_self_classifying_read_routes_to_the_operator(self):
        root, _ref = self._tree()
        rel = "reference_docs/spec.md"
        self._write_reads(root, [self._read(rel, SPEC, tier=1,
                                            self_classifying=True)])
        rec, man = self._rec(root, rel)
        self.assertEqual(rec["floor_rule"], dc.RULE_CONFIRM_REQUIRED)
        self.assertTrue(man["zero_citable"])

    def test_an_operator_demotion_still_outranks_a_read(self):
        root, ref = self._tree()
        rel = "reference_docs/spec.md"
        self._write_reads(root, [self._read(rel, SPEC, tier=1)])
        (ref / rdi.DECISIONS_NAME).write_text(
            f"background  {rel}  {_sha(SPEC)}  this is just an old draft\n",
            encoding="utf-8")
        rec, _man = self._rec(root, rel)
        self.assertEqual(rec["floor_rule"], dc.RULE_OPERATOR_BACKGROUND)


class MalformedInputTests(ReadChannelTestCase):

    def test_a_malformed_FILE_raises_rather_than_reading_as_empty(self):
        # Treating a stray comma as "nobody read anything" would classify a whole
        # corpus as unread for a reason nobody can see — the quiet failure this
        # instruction exists to end.
        root, _ref = self._tree()
        (root / "quality" / rdi.READS_NAME).write_text("{oops", encoding="utf-8")
        with self.assertRaises(rdi.IngestError):
            rdi.classify_reference_docs(root, write=False)

    def test_incomplete_entries_are_skipped_not_guessed_at(self):
        root, _ref = self._tree()
        rel = "reference_docs/spec.md"
        self._write_reads(root, [
            {"source_path": rel},                       # no sha
            {"document_sha256": _sha(SPEC)},            # no path
            "not an object",
            self._read(rel, SPEC),                      # the good one
        ])
        rec, _man = self._rec(root, rel)
        self.assertEqual(rec["tier"], 1)

    def test_an_out_of_range_tier_is_a_DIAGNOSED_refusal(self):
        """033 fix-up 8, panelist B round 2 (B2-1) — CONFIRMED before the fix.

        `tier: 7` escaped as a bare `ValueError` from `classify_document`, which
        runs outside the classifier's try/except. Three consequences, all verified:
        it was not an `IngestError`, so `main()` printed a traceback rather than its
        exit-1 diagnostic; the message named neither this file nor the document;
        and both manifests kept the PREVIOUS run's contents — a stale byte-citable
        FORMAL_DOC record surviving on disk with `generated_at` unchanged while the
        run appeared to fail.

        A non-integer tier (`"1"`, `1.0`) took the graceful `classifier_status:
        error` path instead: the same agent typo, two paths, and the worse one is
        the one an off-by-one takes.
        """
        root, _ref = self._tree()
        rel = "reference_docs/spec.md"
        for bad in (7, 0, -1, 5):
            with self.subTest(tier=bad):
                self._write_reads(root, [self._read(rel, SPEC, tier=bad)])
                with self.assertRaises(rdi.IngestError) as caught:
                    rdi.classify_reference_docs(root, write=False)
                message = str(caught.exception)
                self.assertIn(rdi.READS_NAME, message, "must name the file")
                self.assertIn(rel, message, "must name the document")
                self.assertIn(repr(bad), message, "must name the bad value")

    def test_a_valid_tier_range_is_accepted_including_absent(self):
        # The control: the refusal above must not have narrowed the channel.
        root, _ref = self._tree()
        rel = "reference_docs/spec.md"
        for good in (1, 2, 3, 4, None):
            with self.subTest(tier=good):
                self._write_reads(root, [self._read(rel, SPEC, tier=good)])
                rdi.classify_reference_docs(root, write=False)

    def test_the_stale_manifest_no_longer_survives_a_bad_read(self):
        # The consequence that made B2-1 a FIX-REQUIRED rather than a message NIT:
        # the run aborted, and the last good run's byte-citable record stayed on
        # disk looking current.
        root, _ref = self._tree()
        rel = "reference_docs/spec.md"
        self._write_reads(root, [self._read(rel, SPEC)])
        rdi.ingest(root)
        formal = root / "quality" / "formal_docs_manifest.json"
        self.assertEqual(len(json.loads(formal.read_text())["records"]), 1)
        self._write_reads(root, [self._read(rel, SPEC, tier=7)])
        with self.assertRaises(rdi.IngestError):
            rdi.ingest(root)

    def test_an_uppercase_digest_still_matches(self):
        # Panelist B's escaped bite (B2-5): dropping `.lower()` makes an
        # uppercase-digest read silently stop applying — grounding lost, suite
        # green. sha256 hex is case-insensitive and an agent that wrote it in caps
        # still read the document.
        # MUTATION BITE: `out[(rel, sha.lower())]` -> `out[(rel, sha)]`.
        root, _ref = self._tree()
        rel = "reference_docs/spec.md"
        entry = self._read(rel, SPEC)
        entry["document_sha256"] = entry["document_sha256"].upper()
        self._write_reads(root, [entry])
        rec, _man = self._rec(root, rel)
        self.assertEqual(rec["floor_rule"], dc.RULE_LLM)
        self.assertEqual(rec["tier"], 1)

    def test_duplicate_entries_for_the_same_bytes_take_the_LAST(self):
        # Panelist B (B2-4): the rule was real but undocumented and unpinned, and
        # the order flips the outcome. Last-wins matches the operator decision
        # channel, so a correction appended to the file supersedes what precedes it.
        root, _ref = self._tree()
        rel = "reference_docs/spec.md"
        self._write_reads(root, [self._read(rel, SPEC, tier=1),
                                 self._read(rel, SPEC, tier=4)])
        rec, man = self._rec(root, rel)
        self.assertEqual(rec["tier"], 4)
        self.assertTrue(man["zero_citable"])
        self._write_reads(root, [self._read(rel, SPEC, tier=4),
                                 self._read(rel, SPEC, tier=1)])
        rec2, man2 = self._rec(root, rel)
        self.assertEqual(rec2["tier"], 1)
        self.assertFalse(man2["zero_citable"])

    def test_the_wrapped_object_form_is_accepted(self):
        root, _ref = self._tree()
        rel = "reference_docs/spec.md"
        (root / "quality" / rdi.READS_NAME).write_text(
            json.dumps({"reads": [self._read(rel, SPEC)]}), encoding="utf-8")
        rec, _man = self._rec(root, rel)
        self.assertEqual(rec["tier"], 1)


if __name__ == "__main__":
    unittest.main()
