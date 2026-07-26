"""v1.6.0 instruction 034 — the classifier bar is content-authority, not provenance.

A Phase-1 acceptance run over `repos/chi-1.6.0` came out `zero_citable: true` with
eighteen documents on disk. Two of them were categorized `api-reference` — a citable
category — and then assigned tier 4 anyway. The recorded reasons say why:

    "Third-party API catalog, not chi's own published reference."
    "compiled by an unnamed third party from 56 unspecified sources, not chi's own
     maintainers -- background context, not an authoritative contract."

The second document had no accuracy problem at all; its own read records that it
matches the source. So authorship provenance was doing all the work. Meanwhile the
express corpus — whose docs carry the same third-party-compiled provenance, down to
its own `sources.md` — promoted three `api-reference` documents to Lane B
`unconfirmed`. Same genre, same provenance, opposite outcome.

WHAT THIS FILE CAN AND CANNOT PIN. The defect was a model judgment, and a model
judgment cannot be unit-tested. What can be tested is the pair of things that judgment
rests on:

  * the LANE MECHANICS — that an authoritative-genre read, including one taken on a
    visibly third-party-compiled document and one taken despite a spotted inaccuracy,
    actually routes to Lane B `unconfirmed` and reaches the citable surface. If the
    mechanics did not support the guidance, the guidance would be unfollowable.
  * the GUIDANCE TEXT itself — that the four claims instruction 034 requires are
    present in the file the model reads. This is the half that pins the judgment, and
    it is a real test rather than a formality: the whole defect was that the bar was
    not written down anywhere, so the model invented one. A prose fix with nothing
    holding it can be edited away in a later pass by someone who does not know what it
    cost to learn.
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

GUIDE = REPO_ROOT / "references" / "phase1_exploration_guide.md"


# A compiled third-party API reference, in the shape the chi corpus actually ships:
# precise signatures and behavioural statements, with its provenance stated openly.
COMPILED_API_REF = """# Router API Reference

*Compiled from 56 sources. See sources.md for the full list.*

## Router

### `Use(middlewares ...func(http.Handler) http.Handler)`

Appends middleware to the stack. Middleware MUST be declared before any route is
registered; declaring one afterwards panics.

### `With(middlewares ...func(http.Handler) http.Handler) Router`

Returns a new Router with the given middleware appended, leaving the receiver
unchanged.

### `Route(pattern string, fn func(r Router)) Router`

Mounts a sub-router at `pattern`. The pattern MUST NOT contain a trailing slash.
"""

# The same document with ONE signature wrong — `Use` shown returning a Router when it
# returns nothing. This is the real error the chi run found, and the question this
# fixture settles is what finding it should DO.
COMPILED_API_REF_WITH_ERROR = COMPILED_API_REF.replace(
    "### `Use(middlewares ...func(http.Handler) http.Handler)`",
    "### `Use(middlewares ...func(http.Handler) http.Handler) Router`",
)

TUTORIAL = """# Getting started with the router

Let's build a small service together. First, install the package, then create a
router and add a route or two. You'll see how the pieces fit as we go.
"""

CVE_API_REF = COMPILED_API_REF + "\nSecurity note: see CVE-2024-43796 for details.\n"


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class LaneMechanicsTests(unittest.TestCase):
    """An authoritative-genre read reaches Lane B, whatever its provenance."""

    def _classify(self, path, text, tier, category, reason):
        man = dc.classify_documents(
            [(path, text)],
            llm_classifier=lambda p, t: {"tier": tier, "category": category,
                                         "reason": reason},
            generated_at="X")
        return man["records"][0], man

    def test_a_compiled_api_reference_routes_to_lane_B_not_background(self):
        rec, man = self._classify(
            "reference_docs/13_api_reference.md", COMPILED_API_REF, 2,
            "api-reference",
            "Compiled by a third party, but it states concrete signatures and "
            "behavioural contracts.")
        self.assertEqual(rec["floor_rule"], dc.RULE_LLM)
        self.assertEqual(rec["lane"], dc.LANE_MODEL_READ)
        self.assertEqual(rec["confirmation"], dc.UNCONFIRMED)
        self.assertIn(rec["tier"], (1, 2))
        self.assertFalse(man["zero_citable"])
        self.assertEqual(man["unconfirmed_citable_count"], 1)

    def test_a_spotted_inaccuracy_still_routes_to_lane_B(self):
        # The chi run demoted on this. It is a Lane B cite: the operator sees the
        # note, and Phases 3-4 check the docs against the code anyway — the
        # discrepancy may itself be the finding.
        rec, man = self._classify(
            "reference_docs/13_api_reference.md", COMPILED_API_REF_WITH_ERROR, 2,
            "api-reference",
            "Precise reference; note `Use` is shown returning Router and does not.")
        self.assertEqual(rec["floor_rule"], dc.RULE_LLM)
        self.assertEqual(rec["confirmation"], dc.UNCONFIRMED)
        self.assertIn(rec["tier"], (1, 2))
        self.assertFalse(man["zero_citable"])
        # The reason the operator sees carries the caveat rather than losing it.
        self.assertIn("does not", rec.get("model_reason", ""))

    def test_the_operator_is_told_it_is_the_models_call(self):
        _rec, man = self._classify(
            "reference_docs/13_api_reference.md", COMPILED_API_REF, 2,
            "api-reference", "Precise contract-shaped reference.")
        show = dc.classification_review(man, offer=False)
        self.assertIn("That was my own call", show)
        self.assertNotIn("unconfirmed", show.lower())   # no jargon to the operator

    def test_the_read_reaches_the_byte_citable_surface(self):
        # End to end through the real channel: the mechanics have to carry a Lane B
        # read all the way to something Phase 2 can quote, or the guidance is moot.
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        ref = root / "reference_docs"
        ref.mkdir(parents=True)
        (root / "quality").mkdir()
        (ref / "13_api_reference.md").write_text(COMPILED_API_REF, encoding="utf-8")
        (root / "quality" / rdi.READS_NAME).write_text(json.dumps([{
            "source_path": "reference_docs/13_api_reference.md",
            "document_sha256": _sha(COMPILED_API_REF),
            "tier": 2, "category": "api-reference",
            "reason": "Third-party compiled, but a precise contract-shaped reference.",
        }]), encoding="utf-8")
        rdi.ingest(root)
        formal = json.loads(
            (root / "quality" / "formal_docs_manifest.json").read_text())["records"]
        self.assertEqual([r["source_path"] for r in formal],
                         ["reference_docs/13_api_reference.md"])


class TheFixtureIsNotVacuousTests(unittest.TestCase):
    """The mechanics must still be able to say NO, or the test above proves nothing.

    A fixture that routes everything to Lane B would pass the assertions above while
    telling us nothing. Each of these is a case that must NOT come out Lane B, on the
    identical machinery.
    """

    def _classify(self, path, text, tier, category, **kw):
        man = dc.classify_documents(
            [(path, text)],
            llm_classifier=lambda p, t: {"tier": tier, "category": category,
                                         "reason": "r"},
            generated_at="X", **kw)
        return man["records"][0], man

    def test_a_background_genre_read_does_land_background(self):
        rec, man = self._classify("reference_docs/02_getting_started.md",
                                  TUTORIAL, 4, "tutorial")
        self.assertEqual(rec["tier"], 4)
        self.assertTrue(man["zero_citable"])
        self.assertNotEqual(rec.get("confirmation"), dc.UNCONFIRMED)

    def test_lane_C_still_outranks_an_authoritative_read(self):
        # The backstop is untouched by instruction 034. An api-reference carrying a
        # CVE identifier is the operator's call however precise its content is.
        rec, man = self._classify("reference_docs/13_api_reference.md",
                                  CVE_API_REF, 2, "api-reference")
        self.assertEqual(rec["floor_rule"], dc.RULE_CONFIRM_REQUIRED)
        self.assertFalse(rec["promotable"])
        self.assertTrue(man["zero_citable"])
        self.assertEqual(man["awaiting_confirmation_count"], 1)

    def test_an_operator_demotion_still_outranks_the_read(self):
        rec, _man = self._classify(
            "reference_docs/13_api_reference.md", COMPILED_API_REF, 2,
            "api-reference",
            operator_decisions=[("reference_docs/13_api_reference.md",
                                 _sha(COMPILED_API_REF), dc.OPERATOR_BACKGROUND)])
        self.assertEqual(rec["floor_rule"], dc.RULE_OPERATOR_BACKGROUND)

    def test_an_unread_document_is_still_reported_unread(self):
        man = dc.classify_documents([("reference_docs/13_api_reference.md",
                                      COMPILED_API_REF)], generated_at="X")
        self.assertEqual(man["records"][0]["floor_rule"], dc.RULE_DEFAULT)
        self.assertEqual(man["unread_count"], 1)


class TheGuidanceSaysItTests(unittest.TestCase):
    """Instruction 034 acceptance criteria 1 and 2, pinned against the actual file.

    The defect was that the bar existed nowhere, so the model invented one. Fixing
    that in prose and leaving nothing to hold it invites the same failure the next
    time someone tightens this section — this project has already watched a docstring
    drift byte-identical through four steps of rewriting. These assertions are the
    cheapest available guard on text whose absence cost a whole acceptance run.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = GUIDE.read_text(encoding="utf-8")
        cls.lower = cls.text.lower()

    def test_it_says_provenance_is_not_the_bar(self):
        self.assertIn("content-authority, not authorship provenance", self.lower)
        self.assertIn("never** a reason to demote", self.text)
        self.assertIn("third-party-compiled **by construction**", self.text)

    def test_it_says_what_the_bar_IS(self):
        # Spelled out rather than matched loosely: the bar has to name the CONCRETE
        # evidence, because "is it authoritative?" is the question the model already
        # got wrong. §8a's own wording, so the two cannot drift apart silently.
        for phrase in ("concrete signatures", "options, defaults",
                       "behavioral contracts"):
            self.assertIn(phrase, self.lower, phrase)

    def test_it_routes_authoritative_genre_but_uncertain_to_lane_B(self):
        self.assertIn("lane b `unconfirmed`", self.lower)
        self.assertIn("background is for documents that are background **in genre**",
                      self.lower)

    def test_it_says_a_spotted_inaccuracy_does_not_demote(self):
        self.assertIn("inaccuracy does not demote an authoritative-genre document",
                      self.lower)
        # ...and carries §8a's limiter, so this is not read as "accuracy never
        # matters": a pervasively-wrong document, or one describing a DIFFERENT
        # project, is background because of what it IS. (Panelist A, N1.)
        # Both places the limiter lives, pinned independently. A bare "*minor*"
        # substring matched either one, so dropping it from the RULE still passed
        # while the explanation below carried it — an assertion that cannot fail for
        # the thing it names.
        self.assertIn("a spotted *minor* inaccuracy does not demote", self.lower)
        self.assertIn("the limit is *minor*", self.lower)
        self.assertIn("different project", self.lower)

    def test_it_requires_BOTH_genre_and_content(self):
        # Panelist A, F1 — the over-correction guard. The operative one-liner
        # originally stated the bar as content-shape ALONE, with the genre conjunct
        # in a following paragraph that opens "So:" and parses as a consequence. A
        # model reading only the headline could route a tutorial with precise code
        # samples to Lane B, and express's own manifest shows content-shape already
        # overriding a background genre in a live run.
        self.assertIn("both halves have to hold", self.lower)
        self.assertIn("a tutorial with precise code samples is still a tutorial",
                      self.lower)
        self.assertIn("does not replace the *genre*", self.lower)

    def test_the_genre_is_judged_from_the_BODY_not_the_title(self):
        # Panelist A, F4 — the other direction of the same over-correction. "A
        # tutorial with precise code samples is still a tutorial" gives an
        # affirmative reason to demote on FRAMING, and the back-door clause only
        # covers provenance and accuracy doubt. Express's shipped manifest has
        # 08_Migration_Guide_v4_to_v5.md — titled a migration guide, opening with an
        # Overview and `npm install` — at tier 2 `api-reference` precisely because
        # its body states current behavioral contracts. The guide says twice that a
        # title is not a genre; making the genre label a hard gate without saying
        # where the label comes from hands the title back its authority.
        self.assertIn("the genre is what a document is *for*", self.lower)
        self.assertIn("not what it is *titled*", self.lower)
        self.assertIn("read the body", self.lower)

    def test_the_promote_side_example_reason_drops_published_too(self):
        # Panelist A, N8: "published" survived in the example `reason` string the
        # model is invited to copy — the promote side of the same trigger word, and
        # not caught by the line-43 assertion.
        self.assertNotIn("published API the code", self.text)
        # The word survives nowhere in a document-classification sense.
        self.assertNotIn("published API reference", self.text)
        self.assertNotIn("published API contract", self.text)

    def test_it_closes_the_genre_relabelling_back_door(self):
        # Panelist A, N6: nothing stopped reaching the same tier 4 by re-labelling
        # an api-reference as `guide`, which makes the whole rule optional.
        # Anchored on the clause itself rather than a fixed-width window from a
        # heading — inserting one sentence upstream silently pushed the second
        # assertion out of a 900-char window and failed for the wrong reason.
        self.assertIn("not a back door", self.lower)
        window = self.lower.split("not a back door", 1)[1][:400]
        self.assertIn("the lane is still b", window)

    def test_it_says_to_SURFACE_and_where(self):
        # Panelist A's escaped mutation bite (N2): the "surface" half was unpinned —
        # deleting "*and* surface it" left all 14 tests green — and operationally
        # unspecified, since the guide never told the model where the note goes.
        self.assertIn("cite it *and* surface it", self.lower)
        self.assertIn("`reason`", self.text)

    def test_depth_is_not_reusable_as_a_citation_bar(self):
        # Panelist A, F3: Step 1b's Deep/Moderate/Shallow ladder ties depth to
        # "deriving requirements", a second bar on the same axis 160 lines away. The
        # failing run cited it by name — "read as Deep per Step 1b, but ... not
        # chi's own published spec" — and borrowed its words ("API catalog",
        # "marketing-style") in two more demotion reasons.
        self.assertIn("depth is a scoping judgment, not a citation judgment",
                      self.lower)
        self.assertIn("can be a perfectly good lane b cite", self.lower)

    def test_the_citable_definition_drops_the_word_published(self):
        # Panelist A, F2: line 43 defined the citable set as "spec, RFC, PUBLISHED
        # API reference" — the exact adjective two chi demotions reached for ("not
        # chi's own published reference"). The trigger word sat twelve lines above
        # the paragraph written to kill that reading.
        self.assertIn("(spec, RFC, API reference,", self.text)
        self.assertNotIn("published API reference", self.text)

    def test_the_ambiguity_rule_is_scoped_to_GENRE(self):
        self.assertIn("on genuine ambiguity of genre, background", self.lower)
        # ...and explicitly disclaims the two readings that caused the defect.
        window = self.lower.split("on genuine ambiguity of genre", 1)[1][:1200]
        self.assertIn("not** license to demote", window)
        self.assertIn("who compiled it", window)
        self.assertIn("lane b `unconfirmed`", window)

    def test_lane_C_guidance_is_untouched(self):
        # No regression: the backstop's three signals still read as never-auto-cited.
        self.assertIn("cve/ghsa identifier", self.lower)
        self.assertIn("advisory-site url", self.lower)
        self.assertIn("operator-confirmation-required", self.lower)


if __name__ == "__main__":
    unittest.main()
