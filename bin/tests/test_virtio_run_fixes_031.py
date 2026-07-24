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
# text (the instruction-030 list). The artifact PATH is exempt — the operator has
# to be able to type `quality/persona_review_summary.json` to open the file — so
# the scan runs with that one literal removed.
JARGON = (
    "tier", "citable", "floor", "manifest", "promotable", "persona",
    "feature g", "feature h", "sub-agent", "agent-validation", "grounded",
    "candidate", "mode a", "mode b", "llm", "classifier", "remediator",
)


def _scan_for_jargon(case, text):
    low = text.replace(pa.REVIEW_SUMMARY_PATH, "").lower()
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

    @unittest.skipUnless(CLEAN.is_dir(), "repos/clean/virtio not present")
    def test_an_existing_gitignore_block_is_not_duplicated(self):
        with tempfile.TemporaryDirectory() as tmp:
            dst = Path(tmp) / "virtio-target"
            for _ in range(2):
                proc = subprocess.run(
                    [str(self.SETUP), "--target-folder", str(dst), "--replace",
                     "virtio"],
                    cwd=str(REPO_ROOT / "repos"), capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=600)
                self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
            body = (dst / ".gitignore").read_text(encoding="utf-8")
            self.assertEqual(
                body.count("Quality Playbook — suggested .gitignore additions"), 1)


if __name__ == "__main__":
    unittest.main()
