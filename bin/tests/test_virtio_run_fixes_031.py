"""v1.6.0 instruction 031 — the three defects a sonnet virtio phases 1–3 run surfaced.

The run confirmed instruction 030's end-of-Phase-1 classification review works
end-to-end (plain-language show, zero-authoritative surfaced, operator promotion
recovers the spec). It also surfaced three real defects, one per fix below.

Acceptance oracle map (instruction 031):
  1  the worked example never names a document that isn't plausibly a spec
     -> WorkedExampleTests, SpecNameSignalTests, VirtioCorpusTests
  2  the end-of-Phase-2 message discloses the expert-review pass when-and-only-
     when it ran, in plain language
     -> ReviewDisclosureTests, DisclosureProseContractTests
  3  a setup_repos.sh target validates Phase 0 clean, validator unchanged
     -> BenchmarkInstallTests
  4  full suite green (the suite itself)
"""

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook"
SCRIPT_DIR = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

import doc_classification as dc            # noqa: E402
import persona_apply as pa                 # noqa: E402
import persona_orchestration as po         # noqa: E402
import qpb_validate as qv                  # noqa: E402
from bin import citation_verifier as cv    # noqa: E402


# The virtio corpus in miniature: the real specification is SMALL (7.8 KB in the
# live corpus) and the largest background document is a Linux STYLE GUIDE
# (45 KB). Size ordering therefore points at exactly the wrong file.
VIRTIO_SPEC = (
    "# VIRTIO Behavioral Contracts\n\n"
    "A transport MUST honor VIRTIO_F_RING_RESET negotiation.\n"
    "The driver SHALL poll the status register after writing zero.\n"
)
STYLE_GUIDE = (
    "# Linux kernel coding style\n\n"
    "Tabs are 8 characters. Do not put multiple statements on a single line.\n"
) * 60


def _all_tier4(rel, text):
    """The virtio failure, as a stub: the classifier reads everything as background."""
    return 4


def _manifest(docs, classifier=_all_tier4):
    return dc.classify_documents(docs, llm_classifier=classifier, generated_at="X")


def _example_in(out):
    """The document the show's worked example names, or None when it names none."""
    if "treat `" not in out:
        return None
    return out.split("treat `")[1].split("`")[0]


# ---------------------------------------------------------------------------
# Fix 1 — the worked example must not name a document that isn't a spec.
# ---------------------------------------------------------------------------
class WorkedExampleTests(unittest.TestCase):

    def test_example_names_the_spec_not_the_larger_style_guide(self):
        # THE 031 DEFECT, reproduced: the example picked the largest promotable
        # background document. On virtio that is `linux-coding-style.rst` — so
        # the feature built to help the operator recover a mis-classified spec
        # was telling them to promote a STYLE GUIDE as their specification.
        man = _manifest([
            ("reference_docs/linux-coding-style.rst", STYLE_GUIDE),
            ("reference_docs/virtio-spec-behavioral-contracts.md", VIRTIO_SPEC),
        ])
        # The fixture really does have the defect's shape: the wrong file is the
        # biggest one, so a size-only pick would name it.
        by_size = sorted(man["records"], key=lambda r: -r["byte_count"])
        self.assertEqual(by_size[0]["source_path"],
                         "reference_docs/linux-coding-style.rst")
        for out in (dc.classification_review(man),
                    dc.classification_review(man, offer=False)):
            self.assertEqual(_example_in(out),
                             "reference_docs/virtio-spec-behavioral-contracts.md")
            self.assertNotIn("linux-coding-style.rst` as my specification", out)

    def test_no_spec_like_document_uses_a_neutral_placeholder(self):
        # Nothing here is plausibly a specification. Naming the biggest one
        # anyway is the defect; the example uses a placeholder instead, so the
        # operator still learns the phrasing without being told a wrong answer.
        man = _manifest([
            ("reference_docs/linux-coding-style.rst", STYLE_GUIDE),
            ("reference_docs/release-notes.md", "# Release notes\n\nv2 shipped.\n"),
        ])
        for out in (dc.classification_review(man),
                    dc.classification_review(man, offer=False)):
            self.assertEqual(_example_in(out), "<the-file>")
            self.assertNotIn("linux-coding-style.rst` as my", out)
            self.assertNotIn("release-notes.md` as my", out)
            # The invitation is still there — only the file name is withheld.
            self.assertIn("as my specification", out)

    def test_the_placeholder_is_not_a_real_path_in_the_corpus(self):
        man = _manifest([("reference_docs/notes.md", "# Notes\n\nbackground\n")])
        out = dc.classification_review(man)
        example = _example_in(out)
        self.assertEqual(example, "<the-file>")
        self.assertNotIn(example, [r["source_path"] for r in man["records"]])

    def test_no_promotable_document_still_names_nothing(self):
        # instr 030 regression: when every background document is absolutely
        # barred (advisory / README), there is nothing to promote at this step,
        # so the show asks the open question rather than offering an example —
        # placeholder included. 031 must not turn that into a suggestion.
        man = _manifest([
            ("reference_docs/README.md", "# Readme\n\nbg\n"),
            ("reference_docs/advisory.md",
             "# Advisory\n\nCVE-2024-43796 affects the router.\n"),
        ])
        for out in (dc.classification_review(man),
                    dc.classification_review(man, offer=False)):
            self.assertIsNone(_example_in(out))
            self.assertIn("should be used differently", out)

    def test_spec_like_candidate_still_prefers_the_substantive_one(self):
        # instr 030 Panelist B's finding survives: among SPEC-LIKE candidates the
        # bigger one wins, so a 40-byte stub named `spec.md` does not beat the
        # real specification.
        man = _manifest([
            ("reference_docs/api-spec.md", "# API spec\n"),
            ("reference_docs/virtio-spec-behavioral-contracts.md", VIRTIO_SPEC * 40),
        ])
        self.assertEqual(_example_in(dc.classification_review(man)),
                         "reference_docs/virtio-spec-behavioral-contracts.md")

    def test_a_documentation_candidate_still_beats_a_source_file(self):
        # instr 030 Panelist B round 3: source files are promotable but are often
        # the biggest thing in the corpus. A spec-like .md outranks a spec-like
        # .py even when the .py is larger.
        man = _manifest([
            ("reference_docs/protocol.py", "def handshake():\n    return 1\n" * 200),
            ("reference_docs/protocol-reference.md", "# Protocol reference\n"),
        ])
        self.assertEqual(_example_in(dc.classification_review(man)),
                         "reference_docs/protocol-reference.md")

    def test_a_source_file_is_never_named_over_a_document(self):
        # 031 self-Council round 1 (Panelist A, P1): sweeping the name signal
        # across documents AND source files together inverted the rule above —
        # a spec-NAMED `.c` beat an ordinary document, so the show said "treat
        # `engine-protocol.c` as my specification" one line after saying that
        # file "shows what the software already does, not what it's supposed to
        # do". Documents are their own stratum: when one exists and none of them
        # looks like a spec, the answer is the placeholder, not the source file.
        man = _manifest([
            ("reference_docs/engine-protocol.c", "int main(void) { return 0; }\n" * 80),
            ("reference_docs/design-notes.md", "# Notes\n\nShort design notes.\n"),
        ])
        out = dc.classification_review(man)
        self.assertEqual(_example_in(out), "<the-file>")
        self.assertNotIn("engine-protocol.c` as my", out)

    def test_a_source_file_is_still_nameable_when_no_document_is_promotable(self):
        # ...but the instr-030 affordance survives: a code-shaped contract is
        # exactly what the operator promotion exists for, so when there is no
        # promotable document at all the source file is named.
        man = _manifest([
            ("reference_docs/iface-protocol.py", "import os\n\ndef f():\n    return 1\n"),
            ("reference_docs/README.md", "# Readme\n\nbg\n"),
        ])
        self.assertEqual(_example_in(dc.classification_review(man)),
                         "reference_docs/iface-protocol.py")

    def test_a_document_the_operator_demoted_is_never_the_example(self):
        # 031 self-Council round 2 (Panelist A, P1): an operator's own instr-030
        # demotion ("that one is just background") landed back in the candidate
        # pool — and since operators demote precisely the files that LOOK
        # spec-shaped, the name signal sought it out. The block then contradicted
        # itself four lines apart.
        spec_path = "reference_docs/virtio-spec-behavioral-contracts.md"
        sha = hashlib.sha256(VIRTIO_SPEC.encode("utf-8")).hexdigest()
        man = dc.classify_documents(
            [(spec_path, VIRTIO_SPEC),
             ("reference_docs/system-overview.md", "# Overview\n\nbig\n" * 400)],
            llm_classifier=_all_tier4,
            operator_decisions=[(spec_path, sha, dc.OPERATOR_BACKGROUND)],
            generated_at="X")
        out = dc.classification_review(man)
        self.assertIn("you told me to treat this one as background only", out)
        self.assertNotEqual(_example_in(out), spec_path)
        self.assertNotIn("virtio-spec-behavioral-contracts.md` as my specification", out)

    def test_an_already_authoritative_document_is_never_the_example(self):
        # 031 self-Council round 3 (Panelist A, NIT) + round 4 (unpinned): with a
        # stale `formal_records` an already-authoritative document can appear on
        # the background side, and inviting the operator to promote what they
        # already promoted reads as the system not listening. Round 4 found the
        # guard had no test at all.
        spec_path = "reference_docs/virtio-spec-behavioral-contracts.md"
        sha = hashlib.sha256(VIRTIO_SPEC.encode("utf-8")).hexdigest()
        promoted = dc.classify_documents(
            [(spec_path, VIRTIO_SPEC),
             ("reference_docs/system-overview.md", "# Overview\n\nbig\n" * 400)],
            llm_classifier=_all_tier4,
            operator_decisions=[(spec_path, sha, dc.OPERATOR_AUTHORITATIVE)],
            generated_at="X")
        # A STALE ground truth: the pipeline's formal records predate the
        # promotion, so the show puts the promoted document on the background
        # side. It must still not be offered up for promotion.
        out = dc.classification_review(promoted, formal_records=[])
        self.assertNotEqual(_example_in(out), spec_path)
        # Same for a machine-readable contract, which is citable without any
        # operator action.
        contract = dc.classify_documents(
            [("reference_docs/api.proto", 'syntax = "proto3";\n\nmessage M {}\n'),
             ("reference_docs/system-overview.md", "# Overview\n\nbig\n" * 400)],
            llm_classifier=_all_tier4, generated_at="X")
        out = dc.classification_review(contract, formal_records=[])
        self.assertNotEqual(_example_in(out), "reference_docs/api.proto")

    def test_a_version_word_does_not_demote_a_real_spec(self):
        # 031 self-Council round 2 (Panelist A, NIT): a veto is a demotion, so
        # vetoing `release` handed the example to a tiny stub instead — the
        # instr-030 substantive-over-stub finding, one door over.
        man = _manifest([
            ("reference_docs/virtio-spec-release-1.2.md", VIRTIO_SPEC * 30),
            ("reference_docs/api-contract-stub.md", "# stub\n"),
        ])
        self.assertEqual(_example_in(dc.classification_review(man)),
                         "reference_docs/virtio-spec-release-1.2.md")

    def test_a_genre_word_vetoes_a_spec_word(self):
        # 031 self-Council round 1 (Panelist A, P1): `linux-coding-standards.rst`
        # is ONE RENAME from the file that caused this instruction, and it
        # matches `standards` — with size still breaking ties, it would have been
        # named over the real 7.8 KB spec. The genre veto is what stops the fix
        # from being a rename away from useless.
        man = _manifest([
            ("reference_docs/linux-coding-standards.rst", STYLE_GUIDE),
            ("reference_docs/virtio-spec-behavioral-contracts.md", VIRTIO_SPEC),
        ])
        self.assertEqual(_example_in(dc.classification_review(man)),
                         "reference_docs/virtio-spec-behavioral-contracts.md")

    def test_genre_documents_fall_through_to_the_placeholder(self):
        for name in ("linux-coding-standards.rst", "api-migration-guide.md",
                     "quick-reference-card.md", "protocol-tutorial.md",
                     "api-changelog.md", "spec-release-notes.md"):
            man = _manifest([("reference_docs/" + name, "# doc\n\nbody\n" * 20)])
            out = dc.classification_review(man)
            self.assertEqual(_example_in(out), "<the-file>", name)


class SpecNameSignalTests(unittest.TestCase):
    """The name signal itself: whole-token, on the filename only."""

    def test_spec_like_names(self):
        for path in ("reference_docs/virtio-spec-behavioral-contracts.md",
                     "reference_docs/api-reference.md",
                     "reference_docs/rfc793.txt",
                     "reference_docs/HTTP_PROTOCOL.md",
                     "reference_docs/behavioral_contracts.rst",
                     "reference_docs/posix.standard.md",
                     "docs/specification.md"):
            self.assertTrue(dc._spec_like_name(path), path)

    def test_not_spec_like_names(self):
        for path in ("reference_docs/linux-coding-style.rst",
                     "reference_docs/index.rst",
                     "reference_docs/writing_virtio_drivers.rst",
                     "reference_docs/virtio-community-development-history.md",
                     "reference_docs/release-notes.md",
                     "reference_docs/CHANGELOG.md"):
            self.assertFalse(dc._spec_like_name(path), path)

    def test_the_practice_domain_class_is_closed_not_just_one_filename(self):
        # 031 self-Council round 3 (Panelist A, P1): round 2 closed
        # `linux-coding-standards.rst` but not the CLASS it stood for — the same
        # document wearing different words. "How the team works" is not "what
        # the software must do", whatever spec word sits beside it.
        for path in ("reference_docs/documentation-standards.md",
                     "reference_docs/naming-standards.md",
                     "reference_docs/formatting-standards.md",
                     "reference_docs/engineering-standards.md",
                     "reference_docs/commit-message-contract.md",
                     "reference_docs/code-review-reference.md",
                     "reference_docs/contributing-standards.md",
                     "reference_docs/workflow-protocol.md"):
            self.assertFalse(dc._spec_like_name(path), path)

    def test_the_stub_genre_stays_vetoed(self):
        # 031 self-Council round 3 (Panelist A, NIT): `index`/`toc` are the
        # instr-030 toctree-stub genre, not version words, so the round-2 trim
        # took them off the veto by the wrong rule.
        for path in ("reference_docs/spec-index.md", "reference_docs/api-toc.md",
                     "reference_docs/protocol-contents.md"):
            self.assertFalse(dc._spec_like_name(path), path)

    def test_a_genre_token_vetoes_the_spec_token(self):
        for path in ("reference_docs/linux-coding-standards.rst",
                     "reference_docs/api-migration-guide.md",
                     "reference_docs/quick-reference-card.md",
                     "reference_docs/protocol-tutorial.md",
                     "reference_docs/spec-changelog.md",
                     "reference_docs/api-examples.md",
                     "reference_docs/spec-release-notes.md",
                     "reference_docs/protocol-faq.md"):
            self.assertFalse(dc._spec_like_name(path), path)

    def test_a_backslash_path_does_not_make_the_directory_the_signal(self):
        # 031 self-Council round 1 (Panelist A, NIT): splitting on "/" alone left
        # a backslash path as one basename, so `reference_docs` became the
        # signal — the exact no-op the directory rule exists to prevent.
        # The fixture must be a name the veto does NOT already reject, or the
        # test passes with the split reverted (031 self-Council round 2, Panelist
        # A: the first fixture used `notes.md`, which the genre veto killed
        # before the split mattered — a tautology).
        self.assertFalse(dc._spec_like_name(r"reference_docs\design.md"))
        self.assertTrue(dc._spec_like_name(r"docs\wire-protocol.md"))

    def test_a_dotfile_keeps_its_name(self):
        # `.spec` is all name and no extension; stripping the "extension" left
        # nothing to match (031 self-Council round 1, Panelist A, NIT).
        self.assertTrue(dc._spec_like_name("reference_docs/.spec"))

    def test_the_signal_is_whole_token_not_substring(self):
        # "inspector" contains "spec"; "capital" contains "api". A substring
        # match would call both of these specifications.
        for path in ("reference_docs/inspector-notes.md",
                     "reference_docs/capital-planning.md",
                     "reference_docs/unspecified.md",
                     "reference_docs/standardization-history.md"):
            self.assertFalse(dc._spec_like_name(path), path)

    def test_the_reference_docs_directory_is_not_the_signal(self):
        # Every gathered document lives under `reference_docs/`. If the match ran
        # on the whole path, "reference" would make the entire corpus spec-like
        # and the fix would be a no-op.
        self.assertFalse(dc._spec_like_name("reference_docs/notes.md"))
        self.assertTrue(dc._spec_like_name("notes/reference.md"))

    def test_empty_and_missing_paths_are_not_spec_like(self):
        for path in (None, "", "reference_docs/"):
            self.assertFalse(dc._spec_like_name(path), repr(path))


class VirtioCorpusTests(unittest.TestCase):
    """The acceptance case on the REAL preserved virtio corpus."""

    CORPUS = REPO_ROOT / "repos" / "virtio-1.6.0" / "reference_docs"

    @unittest.skipUnless(CORPUS.is_dir(), "virtio corpus not present in this checkout")
    def test_real_corpus_example_is_the_spec_never_the_style_guide(self):
        docs = []
        for p in sorted(self.CORPUS.iterdir()):
            # The operator control files are not gathered documentation.
            if p.is_file() and not p.name.startswith("qpb_"):
                docs.append(("reference_docs/" + p.name,
                             p.read_text(encoding="utf-8", errors="replace")))
        self.assertTrue(any(d[0].endswith("linux-coding-style.rst") for d in docs))
        man = _manifest(docs)
        example = _example_in(dc.classification_review(man))
        self.assertEqual(example,
                         "reference_docs/virtio-spec-behavioral-contracts.md")


# ---------------------------------------------------------------------------
# Fix 2 — the end-of-Phase-2 message discloses the expert-review pass.
# ---------------------------------------------------------------------------
_SPEC_TXT = (
    "Router specification\n"
    "\n"
    "Path parameters may use a regular-expression constraint of the form\n"
    "{name:pattern}; the router MUST compile and match the pattern per segment.\n"
)

# Every internal label the v1.6.0 plain-language key forbids in operator-facing
# text (the instruction-030 list).
#
# The artifact PATH used to be exempt from this scan — it carried "persona", and
# the operator has to be able to type it to open the file. Instruction 032 fix 3
# removed the reason for the exemption by renaming the artifact
# (`quality/expert_review_summary.json`), so the carve-out is gone and the scan
# now covers the path like any other operator-facing string. Keeping the strip
# would have permanently blinded this test to whatever the path was named
# (instr 032 self-Council, Panelist C).
JARGON = (
    "tier", "citable", "floor", "manifest", "promotable", "persona",
    "feature g", "feature h", "sub-agent", "agent-validation", "grounded",
    "candidate", "mode a", "mode b", "llm", "classifier", "remediator",
)


def _scan_for_jargon(case, text):
    low = text.lower()
    for word in JARGON:
        case.assertNotIn(word, low, f"internal label {word!r} leaked to the operator")


class ReviewDisclosureTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "reference_docs").mkdir()
        (self.root / "reference_docs" / "spec.txt").write_text(
            _SPEC_TXT, encoding="utf-8")
        self.sha = hashlib.sha256(_SPEC_TXT.encode("utf-8")).hexdigest()
        self.formal_docs = [{
            "source_path": "reference_docs/spec.txt",
            "document_sha256": self.sha, "tier": 1, "citation_excerpt": "",
        }]
        self.base = {"records": [
            {"id": "REQ-001", "functional_section": "Routing",
             "title": "named params", "conditions_of_satisfaction": "x",
             "source_type": "code-derived"},
        ]}

    # -- the real pipeline, so the disclosure is rendered from a real summary --
    def _citation(self):
        line = next(i + 1 for i, l in enumerate(_SPEC_TXT.splitlines())
                    if "regular-expression" in l)
        excerpt = cv.extract_excerpt(_SPEC_TXT.encode("utf-8"), ".txt", None, line)
        return {"document": "reference_docs/spec.txt", "document_sha256": self.sha,
                "citation_excerpt": excerpt, "line": line}

    def _provision(self, persona):
        return [
            po.StagedInput("REQUIREMENTS.md",
                           "# Requirements\n\n### REQ-001: named params\n"),
            po.StagedInput("spec.txt", _SPEC_TXT),
            po.StagedInput("rubric.md", "# Rubric\n\nComplete Honest\n"),
        ]

    def _spawn(self, persona, staging_dir, tool_config):
        return {"persona_id": persona["id"], "moves": [
            {"move": "add", "section": "Routing", "title": "regexp params",
             "conditions_of_satisfaction": "params support {name:pattern}",
             "reason": "documented contract",
             "system_justification": "this router documents regexp params",
             "citation": self._citation()},
        ]}

    def _run_pass(self, enabled=True):
        return pa.run_feature_h(
            self.root, base_manifest=self.base, proposed_personas=[],
            provision=self._provision, spawn_persona=self._spawn,
            formal_docs=self.formal_docs, staging_root=self.root / "staging",
            domain_specialization="web routing", enabled=enabled, write=True)

    def test_pass_that_applied_changes_is_disclosed(self):
        result = self._run_pass()
        self.assertTrue(result.review_summary["applied_count"] >= 1)
        out = pa.persona_review_disclosure(result.review_summary)
        self.assertIsNotNone(out)
        # It ran, what it did, where to read it, and that it can be undone.
        self.assertIn("expert reviewers", out.lower())
        self.assertIn("Added", out)
        self.assertIn("Your requirements were changed", out)
        self.assertIn(pa.REVIEW_SUMMARY_PATH, out)
        self.assertIn("undo the expert review changes", out)

    def test_the_disclosure_matches_the_summary_on_disk(self):
        # The operator-facing counts must be the artifact's counts — the whole
        # point is that the message stands in for opening the file.
        self._run_pass()
        summary = json.loads(
            (self.root / "quality" / pa.REVIEW_SUMMARY_NAME).read_text(
                encoding="utf-8"))
        out = pa.persona_review_disclosure(summary)
        adds = sum(1 for m in summary["applied"] if m["move"] == "add")
        self.assertIn(f"Added {adds} requirement", out)

    def test_a_run_without_the_pass_discloses_nothing(self):
        # Disabled for the run, or simply never run: the end-of-Phase-2 message
        # must not claim an expert review that did not happen.
        off = self._run_pass(enabled=False)
        self.assertIsNone(off.review_summary)
        self.assertIsNone(pa.persona_review_disclosure(off.review_summary))
        self.assertIsNone(pa.persona_review_disclosure(None))
        self.assertIsNone(pa.persona_review_disclosure({}))

    def test_disclosure_carries_no_internal_labels(self):
        out = pa.persona_review_disclosure(self._run_pass().review_summary)
        _scan_for_jargon(self, out)
        # ...and the summary it is rendered from really does carry them, so the
        # test has teeth (the same structure as the instr-030 no-jargon test).
        raw = json.dumps(self._run_pass().review_summary).lower()
        self.assertIn("agent-validation", raw)

    def test_every_move_kind_is_reported(self):
        summary = {
            "applied": [{"move": "add"}, {"move": "add"}, {"move": "correct"},
                        {"move": "drop"}, {"move": "confirm"}],
            "conflicts": [{"target": "REQ-002"}],
            "candidates": [{"move": "add"}, {"move": "correct"}],
        }
        out = pa.persona_review_disclosure(summary)
        self.assertIn("Added 2 requirements", out)
        self.assertIn("Rewrote 1 requirement", out)
        self.assertIn("Removed 1 requirement", out)
        self.assertIn("Read 1 requirement", out)
        self.assertIn("Set aside 2 suggestions", out)
        self.assertIn("Hit 1 place", out)
        # 2 adds + 1 correct + 1 drop == 4 changes; a confirm changes nothing,
        # and neither a candidate nor a conflict is applied.
        self.assertIn("4 changes in all", out)
        _scan_for_jargon(self, out)

    def test_singular_phrasing(self):
        out = pa.persona_review_disclosure({"applied": [{"move": "add"}]})
        self.assertIn("Added 1 requirement your", out)
        self.assertIn("1 change in all", out)

    def test_a_pass_that_changed_nothing_says_so_and_promises_no_undo(self):
        out = pa.persona_review_disclosure(
            {"applied": [], "applied_count": 0, "conflicts": [], "candidates": []})
        self.assertIsNotNone(out)
        self.assertIn("did not change anything", out)
        self.assertNotIn("undo", out.lower())
        self.assertIn(pa.REVIEW_SUMMARY_PATH, out)
        _scan_for_jargon(self, out)

    def test_the_undo_the_message_promises_survives_the_process(self):
        # 031 self-Council round 1 (Panelist B, P0): `revert(which="all")`
        # restores from an IN-MEMORY field on the PersonaPass. The agent runs the
        # pass in a scripted invocation that exits before the operator can read
        # the message, so the promise "I will put your requirements back exactly
        # as they were" was unkeepable — and a dropped requirement's text existed
        # NOWHERE on disk. The pass now persists the pre-pass manifest.
        base = {"records": [
            {"id": "REQ-001", "functional_section": "Routing",
             "title": "named params",
             "conditions_of_satisfaction": "THE OPERATOR'S ORIGINAL WORDING",
             "source_type": "code-derived"},
            {"id": "REQ-002", "functional_section": "Routing", "title": "doomed",
             "conditions_of_satisfaction": "THE TEXT THE REVIEWERS REMOVED",
             "source_type": "code-derived"},
        ]}

        def spawn(persona, staging_dir, tool_config):
            return {"persona_id": persona["id"], "moves": [
                {"move": "add", "section": "Routing", "title": "regexp params",
                 "conditions_of_satisfaction": "params support {name:pattern}",
                 "reason": "documented contract",
                 "system_justification": "this router documents regexp params",
                 "citation": self._citation()},
                {"move": "correct", "req_id": "REQ-001",
                 "conditions_of_satisfaction": "REWRITTEN BY THE REVIEWERS",
                 "reason": "documented contract",
                 "system_justification": "matches the documented contract",
                 "citation": self._citation()},
                {"move": "drop", "req_id": "REQ-002", "reason": "not documented"},
            ]}

        pa.run_feature_h(
            self.root, base_manifest=base, proposed_personas=[],
            provision=self._provision, spawn_persona=spawn,
            formal_docs=self.formal_docs, staging_root=self.root / "staging",
            domain_specialization="web routing", enabled=True, write=True)

        post = json.loads((self.root / "quality" /
                           pa.REQUIREMENTS_MANIFEST_NAME).read_text(encoding="utf-8"))
        bodies = [r.get("conditions_of_satisfaction") for r in post["records"]]
        self.assertNotIn("THE TEXT THE REVIEWERS REMOVED", bodies)   # really gone
        self.assertNotIn("THE OPERATOR'S ORIGINAL WORDING", bodies)  # really rewritten

        # The undo, in a later process: nothing but the files on disk.
        restored = pa.revert_from_disk(self.root)
        back = [r.get("conditions_of_satisfaction") for r in restored["records"]]
        self.assertIn("THE TEXT THE REVIEWERS REMOVED", back)
        self.assertIn("THE OPERATOR'S ORIGINAL WORDING", back)
        self.assertEqual(len(restored["records"]), 2)   # the persona's add is gone
        on_disk = json.loads((self.root / "quality" /
                              pa.REQUIREMENTS_MANIFEST_NAME).read_text(encoding="utf-8"))
        self.assertEqual(on_disk, restored)
        # An undone review must not be re-disclosed on the next render.
        self.assertFalse((self.root / "quality" / pa.REVIEW_SUMMARY_NAME).is_file())

    def test_undo_without_a_pass_refuses_rather_than_guesses(self):
        (self.root / "quality").mkdir(exist_ok=True)
        with self.assertRaises(FileNotFoundError) as ctx:
            pa.revert_from_disk(self.root)
        self.assertIn("did not run here", str(ctx.exception))

    def test_the_undo_keeps_the_findings_it_told_the_operator_to_judge(self):
        # 031 self-Council round 2 (Panelist B, P1): the same paragraph says the
        # set-aside suggestions "are listed for you to judge" AND offers the
        # undo — and the undo deleted the list. The candidates were never
        # applied, so undoing the applied changes is no reason to destroy them.
        self._run_pass()
        pa.revert_from_disk(self.root)
        quality = self.root / "quality"
        self.assertFalse((quality / pa.REVIEW_SUMMARY_NAME).is_file())
        undone = quality / pa.UNDONE_REVIEW_SUMMARY_NAME
        self.assertTrue(undone.is_file())
        self.assertIn("applied", json.loads(undone.read_text(encoding="utf-8")))

    def test_a_pass_that_predates_the_snapshot_is_not_called_nothing_to_undo(self):
        # 031 self-Council round 2 (Panelist B, P1): "there is nothing to undo"
        # was also the answer for a tree whose pass ran BEFORE the snapshot
        # existed — where the requirements really were changed.
        self._run_pass()
        (self.root / "quality" / pa.PRE_REVIEW_MANIFEST_NAME).unlink()
        with self.assertRaises(FileNotFoundError) as ctx:
            pa.revert_from_disk(self.root)
        msg = str(ctx.exception)
        self.assertIn("ran here", msg)
        self.assertNotIn("nothing to undo", msg)
        self.assertIn(pa.REVIEW_SUMMARY_NAME, msg)

    def test_a_late_undo_refuses_rather_than_orphaning_bug_links(self):
        # 031 self-Council round 2 (Panelist B, P1): in-process `revert` re-maps
        # BUG→REQ cross-references (`apply_remap_to_bugs`); from disk the remap
        # is gone, and the offer carried no time bound.
        self._run_pass()
        (self.root / "quality" / "bugs_manifest.json").write_text(
            json.dumps({"records": [{"id": "BUG-001", "req_id": "REQ-002"}]}),
            encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            pa.revert_from_disk(self.root)
        self.assertIn("BUG records", str(ctx.exception))
        # ...and it changed nothing on the way out.
        self.assertTrue((self.root / "quality" / pa.REVIEW_SUMMARY_NAME).is_file())

    def test_an_empty_bug_manifest_still_permits_the_boundary_undo(self):
        # 031 self-Council round 3 (Panelist B): `bugs_manifest.json` is a
        # REQUIRED Phase 2 artifact, so at the 2→3 boundary it always exists with
        # `records: []`. A guard keyed on the file's presence rather than its
        # contents would block every undo — including the one the disclosure
        # offers — and no test caught that mutation.
        self._run_pass()
        (self.root / "quality" / "bugs_manifest.json").write_text(
            json.dumps({"records": []}), encoding="utf-8")
        restored = pa.revert_from_disk(self.root)
        self.assertEqual(len(restored["records"]), 1)

    def test_a_second_undo_says_it_is_already_undone(self):
        # 031 self-Council round 3 (Panelist B, NIT): the second undo fell into
        # "the pass did not run here" with the undone record sitting right there.
        self._run_pass()
        pa.revert_from_disk(self.root)
        with self.assertRaises(FileNotFoundError) as ctx:
            pa.revert_from_disk(self.root)
        self.assertIn("already been undone", str(ctx.exception))

    def test_a_malformed_bug_manifest_refuses_by_message_not_traceback(self):
        # 031 self-Council round 3 (Panelist B, NIT): a JSON list / null escaped
        # the fail-safe as an AttributeError.
        # 031 self-Council round 5 (Panelist B, NIT): both situations refused
        # under one message, and "BUG records already exist" is established only
        # for a manifest we could actually read — while State P2 tells the agent
        # to report the refusal it got.
        for body, established in (("[]", False), ("null", False),
                                  ('{"records": [{"id": "BUG-001"}]}', True),
                                  ("not json", False), ('{"bugs": []}', False)):
            with self.subTest(body=body):
                self._run_pass()
                (self.root / "quality" / "bugs_manifest.json").write_text(
                    body, encoding="utf-8")
                with self.assertRaises(ValueError) as ctx:
                    pa.revert_from_disk(self.root)
                msg = str(ctx.exception)
                if established:
                    self.assertIn("BUG records already exist", msg)
                else:
                    self.assertIn("cannot read the bug manifest", msg)
                    self.assertNotIn("BUG records already exist", msg)
                (self.root / "quality" / "bugs_manifest.json").unlink()

    def test_a_wrong_key_bug_manifest_is_not_read_as_no_bugs(self):
        # 031 self-Council round 4 (Panelist B): a manifest keyed `bugs` instead
        # of `records` is the documented 2026-05-16 express defect
        # (phase_prompts/phase2.md) — it read as "no bugs" and let a late undo
        # orphan real BUG→REQ links.
        for body in ('{"bugs": [{"id": "BUG-001"}]}', '{}'):
            with self.subTest(body=body):
                self._run_pass()
                (self.root / "quality" / "bugs_manifest.json").write_text(
                    body, encoding="utf-8")
                with self.assertRaises(ValueError):
                    pa.revert_from_disk(self.root)
                (self.root / "quality" / "bugs_manifest.json").unlink()

    def test_a_second_undo_does_not_clobber_the_first_ones_notes(self):
        # 031 self-Council round 4 (Panelist B): pass → undo → pass → undo
        # overwrote the first review's record — the very loss the rename exists
        # to prevent.
        self._run_pass()
        first = self.root / "quality" / pa.REVIEW_SUMMARY_NAME
        marker = json.loads(first.read_text(encoding="utf-8"))
        marker["marker"] = "THE FIRST REVIEW"
        first.write_text(json.dumps(marker), encoding="utf-8")
        pa.revert_from_disk(self.root)
        self._run_pass()
        pa.revert_from_disk(self.root)
        kept = sorted(p.name for p in (self.root / "quality").iterdir()
                      if ".undone" in p.name)
        self.assertEqual(len(kept), 2, kept)
        bodies = [json.loads((self.root / "quality" / n).read_text(encoding="utf-8"))
                  for n in kept]
        self.assertIn("THE FIRST REVIEW", [b.get("marker") for b in bodies])

    def test_the_documentary_claim_does_not_cover_removals(self):
        # 031 self-Council round 2 (Panelist B, NIT): "they only add or CHANGE a
        # requirement when they can point to the documentation" still covered
        # removals, which are not checked that way.
        out = pa.persona_review_disclosure({"applied": [{"move": "drop"}]})
        self.assertIn("only add or rewrite a requirement", out)
        self.assertNotIn("only add or change a requirement", out)

    def test_a_disabled_pass_leaves_no_snapshot(self):
        self._run_pass(enabled=False)
        self.assertFalse((self.root / "quality" /
                          pa.PRE_REVIEW_MANIFEST_NAME).is_file())

    def test_a_lossy_summary_never_claims_nothing_changed(self):
        # 031 self-Council round 1 (Panelist B, P1): `{"applied_count": 3}` with
        # no `applied` list rendered "did not change anything" — a positive false
        # claim, strictly worse than the silence this feature replaced.
        out = pa.persona_review_disclosure({"applied_count": 3})
        self.assertNotIn("did not change anything", out)
        self.assertIn("incomplete", out)
        self.assertIn(pa.REVIEW_SUMMARY_PATH, out)
        self.assertIn("undo the expert review changes", out)
        _scan_for_jargon(self, out)

    def test_removals_do_not_claim_a_check_the_pipeline_never_ran(self):
        # 031 self-Council round 1 (Panelist B, P1): a `drop` is a pass-through
        # move — the grounding guard gates only add/correct — so "Removed N
        # requirements your documentation does not support" asserted documentary
        # support for the most destructive move type.
        out = pa.persona_review_disclosure({"applied": [{"move": "drop"}]})
        self.assertNotIn("your documentation does not support", out)
        self.assertIn("isn't checked against your documents", out)

    def test_the_message_does_not_invite_the_destructive_selective_undo(self):
        # 031 self-Council round 1 (Panelist B, P0): naming a REWRITTEN id in the
        # selective revert deletes the operator's own requirement instead of
        # restoring its wording (a `correct` retags it agent-validation). The
        # operator-facing undo offers the whole-pass restore only.
        out = pa.persona_review_disclosure(
            {"applied": [{"move": "add"}, {"move": "correct"}]})
        self.assertIn("undo the expert review changes", out)
        self.assertNotIn("the ones you name", out)
        self.assertNotIn("added ones you name", out)

    def test_surfaced_but_unapplied_findings_are_not_reported_as_changes(self):
        # Candidates and conflicts are surfaced, never applied. Saying the
        # requirements changed because of them would be a false disclosure.
        out = pa.persona_review_disclosure(
            {"applied": [], "candidates": [{"move": "add"}],
             "conflicts": [{"target": "REQ-001"}]})
        self.assertIn("Nothing was changed in your requirements", out)
        self.assertIn("I did not act on it", out)
        self.assertNotIn("undo", out.lower())


class DisclosureProseContractTests(unittest.TestCase):
    """The prose that makes a faithful agent actually print it."""

    def test_state_p2_carries_the_disclosure_and_the_ordering_rule(self):
        text = (REPO_ROOT / "references" / "what_just_happened.md").read_text(
            encoding="utf-8")
        p2 = text.split("### State P2")[1].split("### State P3")[0]
        self.assertIn("persona_review_disclosure", p2)
        self.assertIn("expert-review disclosure", p2)
        # Run the pass FIRST — a block emitted before the pass cannot report it.
        self.assertIn("run the pass FIRST", p2)
        # ...and no disclosure at all when the pass did not run.
        self.assertIn("When the pass did NOT run, nothing is added", p2)
        # The interview offer lives in this block, so the ordering rule has to
        # say where the offer lands (031 self-Council round 1, Panelist B: the
        # three surfaces described a cycle no order could satisfy).
        self.assertIn("The interview offer travels inside this block", p2)
        # ...and the undo the disclosure promises has a documented procedure.
        self.assertIn("revert_from_disk", p2)

    def test_every_surface_states_the_same_boundary_order(self):
        phase2 = (SKILL_ROOT / "phase_prompts" / "phase2.md").read_text(encoding="utf-8")
        pipeline = (REPO_ROOT / "references" / "requirements_pipeline.md").read_text(
            encoding="utf-8")
        guide = (REPO_ROOT / "references" / "phase2_generation_guide.md").read_text(
            encoding="utf-8")
        for text, name in ((phase2, "phase2.md"), (pipeline, "requirements_pipeline.md")):
            self.assertIn("The one order for this boundary is", text, name)
        # phase2.md must no longer order the pass AFTER the interview offer while
        # the offer itself rides in the post-pass block.
        self.assertNotIn("(and after the human-interview offer)", phase2)
        # The guide's own mandatory end-of-phase message is ordered too — it was
        # a second operator-facing message still firing before the pass.
        self.assertIn("means after the Feature H persona validation pass", guide)

    def test_the_undo_procedure_is_documented_where_the_agent_reads_it(self):
        for path in (SKILL_ROOT / "phase_prompts" / "phase2.md",
                     REPO_ROOT / "references" / "requirements_pipeline.md",
                     REPO_ROOT / "references" / "what_just_happened.md"):
            self.assertIn("revert_from_disk", path.read_text(encoding="utf-8"),
                          str(path))

    def test_phase2_prompt_orders_the_pass_before_the_message(self):
        text = (SKILL_ROOT / "phase_prompts" / "phase2.md").read_text(encoding="utf-8")
        self.assertIn("persona_review_disclosure", text)
        self.assertIn("AFTER the persona validation pass", text)

    def test_pipeline_and_guide_document_the_disclosure(self):
        pipeline = (REPO_ROOT / "references" / "requirements_pipeline.md").read_text(
            encoding="utf-8")
        self.assertIn("persona_review_disclosure", pipeline)
        guide = (REPO_ROOT / "references" / "phase2_generation_guide.md").read_text(
            encoding="utf-8")
        self.assertIn("persona_review_disclosure", guide)


# ---------------------------------------------------------------------------
# Fix 3 — a setup_repos.sh benchmark target validates Phase 0 clean.
# ---------------------------------------------------------------------------
class BenchmarkInstallTests(unittest.TestCase):

    SETUP = REPO_ROOT / "repos" / "setup_repos.sh"
    CLEAN = REPO_ROOT / "repos" / "clean" / "virtio"
    # `setup_repos.sh` is force-tracked, but the `_benchmark_lib.sh` it sources
    # is not (all of `repos/` is gitignored), so on a fresh clone the script
    # aborts with "No such file or directory" — every script-executing test
    # below FAILED rather than skipping, contradicting this file's
    # degrade-to-skip convention (031 self-Council round 2, Panelist C,
    # reproduced from a `git archive` extraction).
    BENCH_LIB = REPO_ROOT / "repos" / "_benchmark_lib.sh"

    def test_the_validator_is_not_weakened(self):
        # The fix completes the INSTALL; it must not relax what Phase 0 requires.
        closure = {e["path"] for e in qv.INSTALL_CLOSURE}
        self.assertIn("skill-template.gitignore", closure)
        self.assertIn("ai_context/TOOLKIT.md", closure)
        self.assertIn(".gitignore",
                      {e["path"] for e in qv.INSTALL_SCAFFOLDING})
        self.assertEqual(qv._GITIGNORE_SENTINEL, "quality/")

    def test_setup_script_stages_the_three_scaffolding_items(self):
        # A static guard that does not depend on a populated repos/clean/.
        text = self.SETUP.read_text(encoding="utf-8")
        self.assertIn(".github/skills/skill-template.gitignore", text)
        self.assertIn(".github/skills/ai_context/TOOLKIT.md", text)
        self.assertIn('cat "${QPB_SKILL_SRC}/skill-template.gitignore" >> '
                      '"${dst}/.gitignore"', text)
        # The gitignore block's `!quality/RUN_INDEX.md` negation makes
        # run_playbook's pre-flight require that file — create it, exactly as
        # install_skill.py's _ensure_sentinel_files does, or completing the
        # install trades three Phase 0 findings for a sentinel abort.
        self.assertIn("quality/RUN_INDEX.md", text)

    @unittest.skipUnless(CLEAN.is_dir(), "repos/clean/virtio not present")
    @unittest.skipUnless(BENCH_LIB.is_file(), "repos/_benchmark_lib.sh not present")
    def test_a_freshly_set_up_target_validates_phase_0_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "virtio-target"
            proc = subprocess.run(
                [str(self.SETUP), "--target-folder", str(dst), "--replace", "virtio"],
                cwd=str(REPO_ROOT / "repos"), capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=600)
            self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])

            skill_root, bin_root = qv._resolve_install_layout(dst, ".github")
            findings = (qv.check_closure(skill_root, bin_root)
                        + qv.check_scaffolding(dst)
                        + qv.check_stale_quality_dir(dst))
            self.assertEqual(findings, [], f"Phase 0 findings: {findings}")

            # The three specific items the run was blocking on.
            self.assertTrue((skill_root / "skill-template.gitignore").is_file())
            self.assertTrue((skill_root / "ai_context" / "TOOLKIT.md").is_file())
            self.assertIn(qv._GITIGNORE_SENTINEL,
                          (dst / ".gitignore").read_text(encoding="utf-8"))
            # ...and the sentinel the appended block's negation demands.
            sys.path.insert(0, str(REPO_ROOT))
            from bin.run_playbook import _verify_sentinels   # noqa: E402
            self.assertEqual(_verify_sentinels(dst), [])

    # ---- the `--from-prior` lane: the one path that re-runs the install over a
    # target that already carries the block, and the only place the idempotence
    # guard is reachable. It needs no `repos/clean/` entry, so unlike the two
    # tests above it does not skip on a fresh clone (031 self-Council round 1,
    # Panelist C: the previous idempotence test was a tautology — `--replace`
    # `rm -rf`s the destination, so the guard was never reached, and the test
    # passed with the guard deleted).
    PRIOR_SHORT = "qpbtest031"

    def _prior_target(self, gitignore_body):
        """A synthetic prior-version target under repos/ for the from-prior lane."""
        import shutil
        prior = REPO_ROOT / "repos" / f"{self.PRIOR_SHORT}-99.0.0"
        shutil.rmtree(prior, ignore_errors=True)
        (prior / "src").mkdir(parents=True)
        (prior / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
        (prior / ".gitignore").write_text(gitignore_body, encoding="utf-8")
        self.addCleanup(shutil.rmtree, prior, ignore_errors=True)
        return prior

    def _run_from_prior(self, dst):
        proc = subprocess.run(
            [str(self.SETUP), "--from-prior", "--target-folder", str(dst),
             "--replace", self.PRIOR_SHORT],
            cwd=str(REPO_ROOT / "repos"), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=600)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        return proc

    @unittest.skipUnless(BENCH_LIB.is_file(), "repos/_benchmark_lib.sh not present")
    def test_an_existing_gitignore_block_is_not_duplicated(self):
        template = (SKILL_ROOT / "skill-template.gitignore").read_text(encoding="utf-8")
        self._prior_target("build/\n" + template)
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "target"
            self._run_from_prior(dst)
            body = (dst / ".gitignore").read_text(encoding="utf-8")
            self.assertEqual(
                body.count("Quality Playbook — suggested .gitignore additions"), 1)
            self.assertIn("build/", body)

    @unittest.skipUnless(BENCH_LIB.is_file(), "repos/_benchmark_lib.sh not present")
    def test_appending_never_destroys_the_last_existing_rule(self):
        # 031 self-Council round 1 (Panelist C, P1): six repos under
        # repos/clean/ have a `.gitignore` with NO trailing newline. `cat >>`
        # glued the template's first line onto the last rule — on agentscope it
        # produced `uv.lock# Quality Playbook — …`, silently un-ignoring uv.lock
        # in the repo under audit.
        self._prior_target("build/\nuv.lock")          # deliberately unterminated
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "target"
            self._run_from_prior(dst)
            lines = (dst / ".gitignore").read_text(encoding="utf-8").splitlines()
            self.assertIn("uv.lock", lines)
            self.assertTrue(any(l.startswith("# Quality Playbook") for l in lines))

    def test_the_install_sentinel_is_not_read_as_a_prior_run(self):
        # 031 self-Council round 1 (Panelist C, P1): the new quality/RUN_INDEX.md
        # made `archive_previous_run` archive a `partial` prior run on a target
        # that had never been run — a phantom previous_runs/ cell that
        # metrics_reconstruction and skill_derivation read as a real
        # observation, plus a fabricated row in the append-only run index.
        sys.path.insert(0, str(REPO_ROOT))
        from bin import run_playbook   # noqa: E402
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "target"
            (target / "quality").mkdir(parents=True)
            (target / "quality" / "RUN_INDEX.md").write_text(
                "# Run Index\n", encoding="utf-8")
            run_playbook.archive_previous_run(target, "20260101T000000Z")
            self.assertEqual(
                sorted(p.name for p in (target / "quality").iterdir()),
                ["RUN_INDEX.md"])
            # ...and a real prior run still archives.
            (target / "quality" / "BUGS.md").write_text("### BUG-001\n", encoding="utf-8")
            run_playbook.archive_previous_run(target, "20260101T000001Z")
            self.assertTrue(any(p.name != "RUN_INDEX.md" and p.is_dir()
                                for p in (target / "quality").iterdir()))

    def test_the_installed_gitignore_is_protected_from_the_tidy(self):
        # 031 self-Council round 1 (Panelist C, P1): on the three git-carrying
        # clean repos the appended `.gitignore` is a TRACKED modification, and
        # `cleanup_repo` reverted it — the install silently un-did itself and
        # Phase 0 went back to reporting scaffolding_missing_gitignore.
        sys.path.insert(0, str(REPO_ROOT))
        from bin import benchmark_lib   # noqa: E402
        self.assertIn(".gitignore", benchmark_lib.PROTECTED_EXACT)
        self.assertTrue(benchmark_lib._is_protected(".gitignore"))
        self.assertFalse(benchmark_lib._is_protected("src/main.py"))


if __name__ == "__main__":
    unittest.main()
