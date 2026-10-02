"""v1.6.1 Feature H fixes (brief H) + reference-doc ingest nested-folder WARN.

Each test pins one defect seen on QPB 1.6.0 against collective/icalendar
(2026-10-01): H1 correct drops the tier, H2 correct leaves wider prose, H3
confirm-vs-correct held out, H4 overlapping RECUR-range adds all applied, H5 no
shipped persona prompt, H6 renumber not written to bugs_manifest.json, H7 the
disclosure names two reviewers and promises an unconditional undo, I1 nested
reference_docs/ folders skipped silently.
"""

import contextlib
import io
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
import persona_merge as pm  # noqa: E402
import persona_orchestration as po  # noqa: E402
import reference_docs_ingest as rdi  # noqa: E402

# The plain-language contract the 031 disclosure tests enforce.
JARGON = (
    "tier", "citable", "floor", "manifest", "promotable", "persona",
    "feature g", "feature h", "sub-agent", "agent-validation", "grounded",
    "candidate", "mode a", "mode b", "llm", "classifier", "remediator",
)


def _cit(line=10, excerpt="A RECUR rule part MUST NOT occur more than once.",
         doc="reference_docs/cite/rfc5545.txt"):
    return {"document": doc, "document_sha256": "0" * 64, "line": line,
            "citation_excerpt": excerpt}


def _tier3_base():
    return {"records": [
        {"id": "REQ-001", "functional_section": "Recurrence", "tier": 3,
         "title": "RECUR parsing accepts every rule part and validates ranges",
         "description": "Parses all RECUR parts and validates BYxxx ranges.",
         "user_story": "As a caller I get every RECUR part validated.",
         "conditions_of_satisfaction": "All parts parse; all ranges checked.",
         "source_type": "code-derived"},
        {"id": "REQ-002", "functional_section": "Recurrence", "tier": 3,
         "title": "B", "conditions_of_satisfaction": "b",
         "source_type": "code-derived"},
    ]}


def _correct(**extra):
    m = {"move": "correct", "req_id": "REQ-001", "tier": 1, "citation": _cit(),
         "title": "A RECUR rule part occurs at most once",
         "conditions_of_satisfaction": "A repeated rule part is rejected.",
         "system_justification": "icalendar parses RECUR", "reason": "narrow"}
    m.update(extra)
    return m


class H1CorrectBackfillsTier(unittest.TestCase):
    def test_tier3_req_corrected_with_tier1_citation_becomes_tier1(self):
        r = pm.merge_personas([{"persona_id": "domain-expert", "moves": [_correct()]}],
                              _tier3_base())
        rec = next(x for x in r.manifest["records"] if x["title"].startswith("A RECUR"))
        self.assertEqual(rec["tier"], 1)
        self.assertIsNotNone(rec["citation"])


class H2CorrectNarrowsEveryProseField(unittest.TestCase):
    def test_unsupplied_prose_fields_are_flagged_and_surfaced(self):
        r = pm.merge_personas([{"persona_id": "domain-expert", "moves": [_correct()]}],
                              _tier3_base())
        rec = next(x for x in r.manifest["records"] if x["title"].startswith("A RECUR"))
        # The two fields the move did not supply still state the wider claim.
        self.assertEqual(rec["needs_text_review"], ["description", "user_story"])
        summary = pa.build_review_summary(r)
        self.assertEqual(summary["needs_text_review"],
                         [{"req_id": rec["id"], "fields": ["description", "user_story"]}])
        applied = next(a for a in summary["applied"] if a["move"] == "correct")
        self.assertEqual(applied["needs_text_review"], ["description", "user_story"])
        out = pa.persona_review_disclosure(summary)
        self.assertIn("Left other wording unchanged on 1 rewritten requirement", out)

    def test_supplied_prose_fields_are_replaced_and_not_flagged(self):
        move = _correct(description="A repeated rule part is an error.",
                        user_story="As a caller I get an error for a repeated part.")
        r = pm.merge_personas([{"persona_id": "domain-expert", "moves": [move]}],
                              _tier3_base())
        rec = next(x for x in r.manifest["records"] if x["title"].startswith("A RECUR"))
        self.assertEqual(rec["description"], "A repeated rule part is an error.")
        self.assertNotIn("needs_text_review", rec)
        self.assertEqual(pa.build_review_summary(r)["needs_text_review"], [])


class H3ConfirmVersusCorrectIsADissent(unittest.TestCase):
    def test_grounded_correct_applies_and_confirm_is_recorded_as_dissent(self):
        grounded = [
            {"persona_id": "domain-expert", "moves": [_correct()]},
            {"persona_id": "security-reviewer", "moves": [
                {"move": "confirm", "req_id": "REQ-001", "reason": "looks right"}]},
        ]
        r = pm.merge_personas(grounded, _tier3_base())
        self.assertEqual(r.conflicts, [])
        titles = [x["title"] for x in r.manifest["records"]]
        self.assertIn("A RECUR rule part occurs at most once", titles)
        self.assertEqual(len(r.dissents), 1)
        self.assertEqual(r.dissents[0]["corrected_by"], ["domain-expert"])
        # The overruled confirm is not reported as "agreed with it as written".
        self.assertFalse(any(m["move"] == "confirm" for m in r.applied))
        summary = pa.build_review_summary(r)
        self.assertEqual(summary["dissents"][0]["confirmed_by"], "security-reviewer")
        self.assertEqual(summary["dissents"][0]["req_id"], "REQ-001")
        self.assertIn("Applied 1 rewrite that another reviewer would have left",
                      pa.persona_review_disclosure(summary))

    def test_divergent_corrects_and_drop_are_still_conflicts(self):
        r = pm.merge_personas([
            {"persona_id": "a", "moves": [_correct()]},
            {"persona_id": "b", "moves": [_correct(conditions_of_satisfaction="other")]},
            {"persona_id": "c", "moves": [{"move": "confirm", "req_id": "REQ-001"}]},
        ], _tier3_base())
        self.assertEqual(len(r.conflicts), 1)
        self.assertEqual(r.dissents, [])
        r2 = pm.merge_personas([
            {"persona_id": "a", "moves": [_correct()]},
            {"persona_id": "b", "moves": [{"move": "drop", "req_id": "REQ-001"}]},
        ], _tier3_base())
        self.assertEqual(len(r2.conflicts), 1)


class H4SamePassageAddsCluster(unittest.TestCase):
    def _recur_adds(self):
        # The icalendar shape: three personas, overlapping "RECUR range" adds
        # citing the same RFC 5545 paragraph (lines 10-12) with varied wording.
        para = ("BYSECOND, BYMINUTE and BYHOUR ranges are 0-60, 0-59, 0-23.\n"
                "BYMONTHDAY is -31..-1 and 1..31.\nBYMONTH is 1..12.")
        return [
            {"persona_id": "domain-expert", "moves": [
                {"move": "add", "section": "Recurrence", "title": "RECUR ranges A",
                 "conditions_of_satisfaction": "x", "citation": _cit(10, para)},
                {"move": "add", "section": "Recurrence", "title": "RECUR ranges B",
                 "conditions_of_satisfaction": "y",
                 "citation": _cit(11, para.split("\n", 1)[1])}]},
            {"persona_id": "security-reviewer", "moves": [
                {"move": "add", "section": "Recurrence", "title": "RECUR ranges C",
                 "conditions_of_satisfaction": "z", "citation": _cit(12, "BYMONTH is 1..12.")}]},
            {"persona_id": "api-consumer", "moves": [
                {"move": "add", "section": "Recurrence", "title": "RECUR ranges D",
                 "conditions_of_satisfaction": "w", "citation": _cit(10, para)},
                # A different paragraph of the same document: its own REQ.
                {"move": "add", "section": "Recurrence", "title": "COUNT and UNTIL",
                 "conditions_of_satisfaction": "v",
                 "citation": _cit(40, "COUNT and UNTIL MUST NOT occur together.")}]},
        ]

    def test_overlapping_adds_apply_once_and_rest_are_duplicates(self):
        r = pm.merge_personas(self._recur_adds(), _tier3_base())
        titles = [x["title"] for x in r.manifest["records"]]
        self.assertEqual([t for t in titles if t.startswith("RECUR ranges")],
                         ["RECUR ranges A"])
        self.assertIn("COUNT and UNTIL", titles)
        self.assertEqual(len(r.duplicates), 3)
        summary = pa.build_review_summary(r)
        self.assertEqual(sorted(d["title"] for d in summary["duplicates"]),
                         ["RECUR ranges B", "RECUR ranges C", "RECUR ranges D"])
        self.assertTrue(all(d["duplicate_of"]["title"] == "RECUR ranges A"
                            for d in summary["duplicates"]))

    def test_same_passage_in_a_different_section_is_not_clustered(self):
        r = pm.merge_personas([
            {"persona_id": "a", "moves": [
                {"move": "add", "section": "Recurrence", "title": "one",
                 "conditions_of_satisfaction": "x", "citation": _cit()}]},
            {"persona_id": "b", "moves": [
                {"move": "add", "section": "Validation", "title": "two",
                 "conditions_of_satisfaction": "y", "citation": _cit()}]},
        ], _tier3_base())
        self.assertEqual(r.duplicates, [])

    def test_different_documents_are_not_clustered(self):
        r = pm.merge_personas([
            {"persona_id": "a", "moves": [
                {"move": "add", "section": "Recurrence", "title": "one",
                 "conditions_of_satisfaction": "x", "citation": _cit()}]},
            {"persona_id": "b", "moves": [
                {"move": "add", "section": "Recurrence", "title": "two",
                 "conditions_of_satisfaction": "y",
                 "citation": _cit(doc="reference_docs/cite/rfc7529.txt")}]},
        ], _tier3_base())
        self.assertEqual(r.duplicates, [])


class H5ShippedPersonaBrief(unittest.TestCase):
    def test_brief_exists_and_carries_the_passage_rule(self):
        path = REPO_ROOT / "references" / "persona_brief.md"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("A requirement may state only what its quoted passage states.", text)
        self.assertIn("A `correct` must supply every prose field it narrows.", text)
        self.assertEqual(po.persona_brief_path().resolve(), path.resolve())

    def test_brief_is_referenced_where_persona_prompts_are_composed(self):
        e9 = (REPO_ROOT / "references" / "requirements_pipeline.md").read_text(encoding="utf-8")
        self.assertIn("references/persona_brief.md", e9)
        self.assertIn("persona_orchestration.persona_prompt(persona)", e9)
        prompt = po.persona_prompt({"id": "security-reviewer", "title": "Security reviewer"})
        self.assertTrue(prompt.startswith("Your lens: Security reviewer"))
        self.assertIn(po.load_persona_brief(), prompt)

    def test_run_feature_h_stages_the_brief_for_every_persona(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        seen = {}

        def spawn(persona, staging_dir, cfg):
            seen[persona["id"]] = (Path(staging_dir) / "persona_brief.md").read_text(
                encoding="utf-8")
            return {"persona_id": persona["id"], "moves": []}

        pa.run_feature_h(root, base_manifest={"records": []}, proposed_personas=[],
                         provision=lambda p: [po.StagedInput("REQUIREMENTS.md", "# R\n")],
                         spawn_persona=spawn, formal_docs=[],
                         staging_root=root / "_staging", write=False)
        self.assertEqual(set(seen), {"domain-expert", "security-reviewer"})
        self.assertTrue(all(t == po.load_persona_brief() for t in seen.values()))


class H6RemapPropagatesToDisk(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.q = self.root / "quality"
        self.q.mkdir()
        self.base = {"records": [
            {"id": "REQ-001", "functional_section": "A", "title": "a",
             "conditions_of_satisfaction": "x"},
            {"id": "REQ-002", "functional_section": "B", "title": "b",
             "conditions_of_satisfaction": "y"},
            {"id": "REQ-003", "functional_section": "B", "title": "c",
             "conditions_of_satisfaction": "z"},
        ]}
        # An add in section A shifts REQ-002 -> REQ-003 and REQ-003 -> REQ-004.
        self.moves = [{"move": "add", "section": "A", "title": "new",
                       "conditions_of_satisfaction": "n", "tier": 1, "citation": _cit()}]

    def _run(self):
        moves = self.moves
        # Drive the merge directly through run_persona_pass + the disk step,
        # the same two calls run_feature_h makes after grounding.
        res = pa.run_persona_pass(self.base, [{"persona_id": "p", "moves": moves}])
        return res, pa.propagate_remap_on_disk(self.q, res.remap)

    def test_bugs_and_semantic_check_are_remapped_and_map_is_written(self):
        (self.q / "bugs_manifest.json").write_text(json.dumps({"records": [
            {"id": "BUG-001", "req_id": "REQ-002",
             "covers": ["REQ-003/cell-a-b"], "requirement": "REQ-003"},
            {"id": "BUG-002", "req_id": "REQ-003", "requirements": ["REQ-002", "REQ-001"]},
        ]}), encoding="utf-8")
        (self.q / "citation_semantic_check.json").write_text(json.dumps({"reviews": [
            {"req_id": "REQ-002", "reviewer": "x", "verdict": "supports", "notes": ""},
        ]}), encoding="utf-8")
        res, record = self._run()
        # (The add's provisional id REQ-ADD-004 also maps, to REQ-002.)
        self.assertEqual(res.remap["REQ-002"], "REQ-003")
        self.assertEqual(res.remap["REQ-003"], "REQ-004")
        bugs = json.loads((self.q / "bugs_manifest.json").read_text(encoding="utf-8"))["records"]
        # Simultaneous remap, not chained: REQ-002 -> REQ-003, not -> REQ-004.
        self.assertEqual(bugs[0]["req_id"], "REQ-003")
        self.assertEqual(bugs[0]["covers"], ["REQ-004/cell-a-b"])
        self.assertEqual(bugs[0]["requirement"], "REQ-004")
        self.assertEqual(bugs[1]["req_id"], "REQ-004")
        self.assertEqual(bugs[1]["requirements"], ["REQ-003", "REQ-001"])
        sc = json.loads((self.q / "citation_semantic_check.json").read_text(encoding="utf-8"))
        self.assertEqual(sc["reviews"][0]["req_id"], "REQ-003")
        on_disk = json.loads((self.q / "req_id_remap.json").read_text(encoding="utf-8"))
        self.assertEqual(on_disk["remap"], res.remap)
        self.assertTrue(on_disk["generated_at"])
        self.assertEqual(on_disk["files"], {"bugs_manifest.json": "updated",
                                            "citation_semantic_check.json": "updated"})

    def test_absent_and_unreadable_files_are_left_alone(self):
        (self.q / "bugs_manifest.json").write_text("{not json", encoding="utf-8")
        _res, record = self._run()
        self.assertEqual(record["files"], {"bugs_manifest.json": "unreadable",
                                           "citation_semantic_check.json": "absent"})
        self.assertEqual((self.q / "bugs_manifest.json").read_text(encoding="utf-8"),
                         "{not json")
        self.assertFalse((self.q / "citation_semantic_check.json").exists())

    def test_run_feature_h_writes_the_remap_and_updates_bugs_on_disk(self):
        import hashlib
        spec = ("Router specification\n\nPath parameters may use a regular-expression "
                "constraint of the form\n{name:pattern}; the router MUST compile it.\n")
        (self.root / "reference_docs").mkdir()
        (self.root / "reference_docs" / "spec.txt").write_text(spec, encoding="utf-8")
        sha = hashlib.sha256(spec.encode("utf-8")).hexdigest()
        from bin import citation_verifier as cv
        excerpt = cv.extract_excerpt(spec.encode("utf-8"), ".txt", None, 3)
        (self.q / "bugs_manifest.json").write_text(json.dumps({"records": [
            {"id": "BUG-001", "req_id": "REQ-002"}]}), encoding="utf-8")

        def spawn(persona, staging_dir, cfg):
            if persona["id"] != "domain-expert":
                return {"persona_id": persona["id"], "moves": []}
            return {"persona_id": persona["id"], "moves": [
                {"move": "add", "section": "A", "title": "regexp params",
                 "conditions_of_satisfaction": "params support {name:pattern}",
                 "reason": "r", "system_justification": "this router documents it",
                 "citation": {"document": "reference_docs/spec.txt",
                              "document_sha256": sha, "line": 3,
                              "citation_excerpt": excerpt}}]}

        pa.run_feature_h(
            self.root, base_manifest=self.base, proposed_personas=[],
            provision=lambda p: [po.StagedInput("REQUIREMENTS.md", "# R\n")],
            spawn_persona=spawn,
            formal_docs=[{"source_path": "reference_docs/spec.txt",
                          "document_sha256": sha, "tier": 1}],
            staging_root=self.root / "_staging", write=True)
        bugs = json.loads((self.q / "bugs_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(bugs["records"][0]["req_id"], "REQ-003")
        remap = json.loads((self.q / "req_id_remap.json").read_text(encoding="utf-8"))
        self.assertEqual(remap["remap"]["REQ-002"], "REQ-003")


class H7DisclosureNamesWhoRanAndTheUndoLimit(unittest.TestCase):
    def _summary(self, personas):
        return {"applied": [{"move": "add"}], "applied_count": 1, "conflicts": [],
                "candidates": [], "personas": personas}

    def test_three_reviewers_are_counted_and_described(self):
        out = pa.persona_review_disclosure(self._summary([
            {"id": "domain-expert", "title": "Domain expert"},
            {"id": "security-reviewer", "title": "Security reviewer"},
            {"id": "api-consumer", "title": "API / consumer-integrator"},
        ]))
        self.assertIn("three expert reviewers", out)
        self.assertIn("one who looks at it as a developer calling its API", out)
        self.assertNotIn("one who knows this kind of system and one who reviews "
                         "for security —", out)
        low = out.lower()
        for word in JARGON:
            self.assertNotIn(word, low, word)

    def test_summary_written_by_run_feature_h_lists_the_personas(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        res = pa.run_feature_h(
            root, base_manifest={"records": []},
            proposed_personas=[{"id": "api-consumer", "justification": "a library"}],
            provision=lambda p: [], spawn_persona=lambda p, d, c: {"moves": []},
            formal_docs=[], staging_root=root / "_s", write=False)
        self.assertEqual([p["id"] for p in res.review_summary["personas"]],
                         ["domain-expert", "security-reviewer", "api-consumer"])

    def test_undo_offer_states_the_bug_record_limit(self):
        out = pa.persona_review_disclosure(self._summary(
            [{"id": "domain-expert"}, {"id": "security-reviewer"}]))
        self.assertIn("undo the expert review changes", out)
        self.assertIn("works only until I record the first bug", out)
        # ...which is the rule revert_from_disk enforces.
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        q = Path(tmp.name) / "quality"
        q.mkdir()
        (q / pa.PRE_REVIEW_MANIFEST_NAME).write_text('{"records": []}', encoding="utf-8")
        (q / "bugs_manifest.json").write_text('{"records": [{"id": "BUG-001"}]}',
                                              encoding="utf-8")
        with self.assertRaises(ValueError):
            pa.revert_from_disk(Path(tmp.name))

    def test_summary_without_personas_claims_no_count(self):
        out = pa.persona_review_disclosure({"applied": [{"move": "add"}]})
        self.assertIn("I brought in expert reviewers to read", out)
        self.assertNotIn("two expert reviewers", out)


class I1NestedReferenceDocsWarn(unittest.TestCase):
    def test_nested_files_are_listed_in_a_warn(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        ref = root / "reference_docs"
        (ref / "cite" / "rfcs").mkdir(parents=True)
        (ref / "notes" / "deep").mkdir(parents=True)
        (ref / "top.md").write_text("top\n", encoding="utf-8")
        (ref / "cite" / "spec.md").write_text("spec\n", encoding="utf-8")
        (ref / "cite" / "rfcs" / "rfc5545.txt").write_text("rfc\n", encoding="utf-8")
        (ref / "notes" / "deep" / "n.md").write_text("n\n", encoding="utf-8")
        (ref / "notes" / ".hidden").write_text("h\n", encoding="utf-8")
        skipped = rdi.nested_skipped_files(root)
        self.assertEqual(skipped, ["reference_docs/cite/rfcs/rfc5545.txt",
                                   "reference_docs/notes/deep/n.md"])
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            rdi.ingest(root)
        text = err.getvalue()
        self.assertIn("WARN: reference_docs_ingest skipped 2 file(s) in nested folders", text)
        self.assertIn("reference_docs/cite/rfcs/rfc5545.txt", text)

    def test_flat_layout_emits_no_warn(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "reference_docs" / "cite").mkdir(parents=True)
        (root / "reference_docs" / "cite" / "spec.md").write_text("s\n", encoding="utf-8")
        self.assertEqual(rdi.nested_skipped_files(root), [])
        self.assertIsNone(rdi.nested_skip_warning([]))

    def test_long_lists_are_capped(self):
        msg = rdi.nested_skip_warning([f"reference_docs/x/{i:03d}.md" for i in range(121)])
        self.assertIn("skipped 121 file(s)", msg)
        self.assertIn("... and 71 more", msg)


if __name__ == "__main__":
    unittest.main()
