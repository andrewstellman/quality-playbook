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

    # Panelist C, C-3: 14 of these assertions matched on Markdown EMPHASIS, so the
    # sensitivity was inverted — changing `**bold**` to `*italic*` failed two tests
    # while C's counter-bite, which wrote the provenance bar back INTO the guide by
    # qualification and kept every pinned substring, passed 28/28. Matching is now
    # emphasis-insensitive: the tests guard the RULE, not the typography.
    #
    # Stated limit, because it matters and no assertion closes it: substring tests
    # detect DELETION, not CONTRADICTION. A future editor can satisfy every needle
    # here and still reintroduce the defect by adding qualifying prose around it.
    # That is what the Council is for; these pins only stop silent removal.
    @classmethod
    def setUpClass(cls):
        cls.text = GUIDE.read_text(encoding="utf-8")
        cls.lower = cls.text.lower()
        cls.plain = cls._plainly(cls.text)

    @staticmethod
    def _plainly(needle):
        """Emphasis-, dash- and whitespace-insensitive view of the guidance."""
        out = needle.lower().replace("*", "").replace("_", "")
        for dash in ("\u2014", "\u2013"):          # em dash, en dash
            out = out.replace(dash, "-")
        return " ".join(out.split())

    def test_it_says_provenance_is_not_the_bar(self):
        self.assertIn(self._plainly("content-authority, not authorship provenance"), self.plain)
        self.assertIn(self._plainly("never** a reason to demote"), self.plain)
        self.assertIn(self._plainly("third-party-compiled **by construction**"), self.plain)

    def test_it_says_what_the_bar_IS(self):
        # Spelled out rather than matched loosely: the bar has to name the CONCRETE
        # evidence, because "is it authoritative?" is the question the model already
        # got wrong. §8a's own wording, so the two cannot drift apart silently.
        for phrase in ("concrete signatures", "options, defaults",
                       "behavioral contracts"):
            self.assertIn(self._plainly(phrase), self.plain, phrase)

    def test_it_routes_authoritative_genre_but_uncertain_to_lane_B(self):
        self.assertIn(self._plainly("lane b `unconfirmed`"), self.plain)
        self.assertIn(self._plainly("background is for documents that are background **in genre**"), self.plain)

    def test_it_says_a_spotted_inaccuracy_does_not_demote(self):
        self.assertIn(self._plainly("inaccuracy does not demote an authoritative-genre document"), self.plain)
        # ...and carries §8a's limiter, so this is not read as "accuracy never
        # matters": a pervasively-wrong document, or one describing a DIFFERENT
        # project, is background because of what it IS. (Panelist A, N1.)
        # Both places the limiter lives, pinned independently. A bare "*minor*"
        # substring matched either one, so dropping it from the RULE still passed
        # while the explanation below carried it — an assertion that cannot fail for
        # the thing it names.
        self.assertIn(self._plainly("a spotted *minor* inaccuracy does not demote"), self.plain)
        self.assertIn(self._plainly("the limit is *minor*"), self.plain)
        self.assertIn(self._plainly("different project"), self.plain)

    def test_it_requires_BOTH_genre_and_content(self):
        # Panelist A, F1 — the over-correction guard. The operative one-liner
        # originally stated the bar as content-shape ALONE, with the genre conjunct
        # in a following paragraph that opens "So:" and parses as a consequence. A
        # model reading only the headline could route a tutorial with precise code
        # samples to Lane B, and express's own manifest shows content-shape already
        # overriding a background genre in a live run.
        self.assertIn(self._plainly("both halves have to hold"), self.plain)
        self.assertIn(self._plainly("a tutorial with precise code samples is still a tutorial"), self.plain)
        self.assertIn(self._plainly("does not replace the *genre*"), self.plain)

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
        self.assertIn(self._plainly("the genre is what a document is *for*"), self.plain)
        self.assertIn(self._plainly("not what it is *titled*"), self.plain)
        self.assertIn(self._plainly("read the body"), self.plain)
        # The two WORKED EXAMPLES, pinned separately (panelist A, N9 — its bite
        # deleting the first of them left 21/21 green). Third instance in this
        # review of one shape: the abstract rule pinned, the concrete case loose.
        # The examples are the half that does the work — the first is literally the
        # express artifact this finding came from, and the second works the rule in
        # the promote-BLOCKING direction so it cannot be read as "titles never
        # matter, promote freely".
        # Decomposed rather than pinned verbatim (panelist C): a semantics-
        # preserving reword of a worked example should not fail a test about the
        # RULE. What must survive is that each example is present and points the way
        # it points — a migration guide reaching `api-reference`, a `SPEC.md`
        # reaching tutorial.
        migration = self.plain.split("migration guide whose body", 1)
        self.assertEqual(len(migration), 2, "the migration-guide example is gone")
        self.assertIn("api-reference", migration[1][:120])
        spec_md = self.plain.split("`spec.md`", 1)
        self.assertEqual(len(spec_md), 2, "the SPEC.md counter-example is gone")
        self.assertIn("tutorial", spec_md[1][:120])

    def test_the_promote_side_example_reason_drops_published_too(self):
        # Panelist A, N8: "published" survived in the example `reason` string the
        # model is invited to copy — the promote side of the same trigger word, and
        # not caught by the line-43 assertion.
        self.assertNotIn(self._plainly("published API the code"), self.plain)
        # The word survives nowhere in a document-classification sense.
        self.assertNotIn(self._plainly("published API reference"), self.plain)
        self.assertNotIn(self._plainly("published API contract"), self.plain)

    def test_it_closes_the_genre_relabelling_back_door(self):
        # Panelist A, N6: nothing stopped reaching the same tier 4 by re-labelling
        # an api-reference as `guide`, which makes the whole rule optional.
        # Anchored on the clause itself rather than a fixed-width window from a
        # heading — inserting one sentence upstream silently pushed the second
        # assertion out of a 900-char window and failed for the wrong reason.
        self.assertIn(self._plainly("not a back door"), self.plain)
        window = self.plain.split("not a back door", 1)[1][:400]
        self.assertIn("the lane is still b", window)

    def test_it_says_to_SURFACE_and_where(self):
        # Panelist A's escaped mutation bite (N2): the "surface" half was unpinned —
        # deleting "*and* surface it" left all 14 tests green — and operationally
        # unspecified, since the guide never told the model where the note goes.
        self.assertIn(self._plainly("cite it *and* surface it"), self.plain)
        self.assertIn(self._plainly("`reason`"), self.plain)

    def test_depth_is_not_reusable_as_a_citation_bar(self):
        # Panelist A, F3: Step 1b's Deep/Moderate/Shallow ladder ties depth to
        # "deriving requirements", a second bar on the same axis 160 lines away. The
        # failing run cited it by name — "read as Deep per Step 1b, but ... not
        # chi's own published spec" — and borrowed its words ("API catalog",
        # "marketing-style") in two more demotion reasons.
        self.assertIn(self._plainly("depth is a scoping judgment, not a citation judgment"), self.plain)
        self.assertIn(self._plainly("can be a perfectly good lane b cite"), self.plain)

    def test_the_citable_definition_drops_the_word_published(self):
        # Panelist A, F2: line 43 defined the citable set as "spec, RFC, PUBLISHED
        # API reference" — the exact adjective two chi demotions reached for ("not
        # chi's own published reference"). The trigger word sat twelve lines above
        # the paragraph written to kill that reading.
        self.assertIn(self._plainly("(spec, RFC, API reference,"), self.plain)
        self.assertNotIn(self._plainly("published API reference"), self.plain)

    def test_the_conservative_direction_is_PRESERVED_not_just_narrowed(self):
        # Panelist B's bite T2 deleted the whole conservative direction —
        # `candidate-spec`, "call it background", and the recoverable/poisons
        # rationale — and the fixture stayed 21/21 green. Task 2 says narrow it AND
        # preserve it; the fixture pinned only the narrowing, so the half being
        # preserved was unguarded.
        # Scoped to the conservative rule itself. A bare "`candidate-spec`" also
        # matches the category list ~60 lines up, so deleting it from THIS rule left
        # 24/24 green — the sixth instance in this review of an assertion whose
        # pass/fail was not tied to the clause it named.
        window = self.plain.split("on genuine ambiguity of genre", 1)[1][:700]
        self.assertIn("`candidate-spec`", window)
        self.assertIn("call it background", window)
        self.assertIn(self._plainly("a missed grounding is recoverable, a false authoritative "
                      "source poisons the derivation"), self.plain)

    def test_a_mixed_document_goes_UP_not_down(self):
        # Panelist B, B-1: both worked examples cover a title/body MISMATCH; neither
        # covers a body that is genuinely both. Express's 07_Static_Files_Serving.md
        # is exactly that — walkthrough sections wrapped around an options-and-
        # defaults section — and it is one of the three live Lane B citables
        # acceptance criterion 4 protects.
        self.assertIn(self._plainly("when the body is genuinely both"), self.plain)
        self.assertIn(self._plainly("the contract content decides it"), self.plain)
        self.assertIn("upward", self.plain)
        self.assertIn(self._plainly("a section a requirement could be written against"), self.plain)

    def test_a_mixed_promotion_must_name_the_contract_section(self):
        """Panelist B, B-7 — the justification was FALSE about the mechanics.

        The rule said "you are not certifying the whole document; you are saying it
        contains something quotable". Driven through the real ingest, promoting a
        mixed document yields a FORMAL_DOC record with `line_count: 269`,
        `byte_count` equal to the whole file, NO line_start/line_end/section/scope
        key of any kind, and `citation_excerpt` set to the document title. The whole
        file becomes quotable at that tier. Citability is per FILE.

        The guide cannot invent scoping mechanics, so the honest version became an
        obligation instead: say which section carries the contract, in the one field
        the operator actually reads.
        """
        self.assertIn(self._plainly("citability is recorded per file, not per section"), self.plain)
        self.assertIn(self._plainly("makes **the whole file** quotable"), self.plain)
        self.assertIn(self._plainly("name the contract section in your `reason`"), self.plain)
        # Panelist C, C-8 — the THIRD false-mechanics claim in three rounds. The
        # replacement for B-7 said the reason is "carried into the requirements
        # interview"; `model_reason` is on the record and returned by
        # `classification_playback()`, but `requirements_interview.md` mandates
        # playing back `floor_rule`'s reason and `rescued_reason` only. Reachable,
        # not routed.
        self.assertIn(self._plainly("where the requirements interview and Phase 4 "
                                    "can reach it"), self.plain)
        self.assertNotIn(self._plainly("carried into the requirements interview"),
                         self.plain)
        # ...and the false claim is gone.
        self.assertNotIn(self._plainly("you are not certifying the whole document"), self.plain)

    def test_a_superseded_version_has_a_route_to_background(self):
        """Panelist B, B-8 — the inverse of why express 08 earns Lane B.

        A v4 API reference in a v5 corpus cleared every clause: authoritative genre,
        contract-shaped, same project, and the "pervasively wrong" floor was
        unreachable because classification never verifies claims against code — a
        model that merely RECOGNISES "these are the v4 docs" has checked zero. So
        recognition is carved out of the evidence bar for exactly the two cases
        where recognition is sufficient.
        """
        self.assertIn(self._plainly("superseded version"), self.plain)
        self.assertIn(self._plainly("you do not have to check any claim"), self.plain)
        # Panelist C, C-4 (revised): C proposed cutting this route, checked the
        # unattended path — phase1.md says "The show prints in every mode. The pause
        # does not", so on a headless run Lane B means CITED with nobody to object —
        # and withdrew the cut. What survived was the contradiction with the
        # per-document isolation rule nine paragraphs above, reconciled in place.
        self.assertIn(self._plainly("the one comparison per-document isolation does "
                                    "not forbid"), self.plain)

    def test_the_accuracy_carve_out_does_not_retire_the_content_half(self):
        # Panelist B, B-9: "only being *wrong* counts against it, and then only
        # pervasively" read as retiring the content half of "both halves have to
        # hold". Scoped to accuracy.
        self.assertIn(self._plainly("counts against its **accuracy**"), self.plain)
        self.assertIn(self._plainly("the content half of the bar"), self.plain)

    def test_pervasively_wrong_has_an_evidentiary_floor(self):
        # Panelist B, B-4/B-5: without a floor, chi's "one inaccuracy on the first
        # page checked" fits through "pervasively wrong"; and chi 14's "matches
        # source at a summary level" left §8a's own canonical Lane B example
        # demotable on the content half.
        self.assertIn(self._plainly("not that you checked one page and found one error"), self.plain)
        self.assertIn(self._plainly("is a reason to **cite** a reference, not to demote it"), self.plain)

    def test_the_ambiguity_rule_is_scoped_to_GENRE(self):
        self.assertIn(self._plainly("on genuine ambiguity of genre, background"), self.plain)
        # ...and explicitly disclaims the two readings that caused the defect.
        # Sized to the paragraph it is about (674 chars), not 1200 — an
        # over-long window silently starts asserting about the NEXT paragraph,
        # which is the inverse of the too-short window found earlier.
        window = self.plain.split("on genuine ambiguity of genre", 1)[1][:700]
        self.assertIn("not license to demote", window)
        self.assertIn("who compiled it", window)
        self.assertIn("lane b `unconfirmed`", window)

    def test_the_bar_guidance_renders_as_prose_not_a_code_block(self):
        """Panelist B, B-11 — four characters, and mine.

        I inserted the B-7 paragraph with four leading spaces, which in Markdown is
        an indented code block. It was the only indented prose line in the file —
        the other three 4-space blocks are the reads-JSON sample, the decisions-file
        format and a shell command — so the indent reads, in this file's own
        vocabulary, as "this is a sample, not an instruction". Round 2 had merged
        the back-door and provenance clauses into that same paragraph, so THREE of
        034's core claims were rendering as monospace with literal asterisks.

        Rendering-only (the classifier reads raw bytes), but the guide is read by
        humans too, and a rule that looks like sample output is not a rule.
        """
        lines = self.text.split("\n")
        for phrase in ("name the contract section in your `reason`",
                       "the genre call is not a back door",
                       "who compiled a document is never a reason to demote it",
                       "the bar is content-authority, not authorship provenance",
                       "when the body is genuinely both"):
            # Emphasis-insensitive: this test is about INDENTATION, so re-styling a
            # claim must not fail it (panelist C, C-3).
            hits = [ln for ln in lines if self._plainly(phrase) in self._plainly(ln)]
            self.assertTrue(hits, f"claim vanished: {phrase}")
            for ln in hits:
                indent = len(ln) - len(ln.lstrip(" "))
                self.assertEqual(indent, 0,
                                 f"claim renders as a code block (indent={indent}): {phrase}")

    def test_lane_C_guidance_is_untouched(self):
        """No regression: all THREE backstop signals, inside the Lane C bullet.

        Panelist B's bite T1 deleted the implementation-source signal from all three
        places it appears and left 21/21 green — this test never asserted it, and
        matched the other two anywhere in an 800-line file ("cve/ghsa identifier"
        occurs 7 times). Scoped to the bullet so the assertions are about the rule
        rather than about the word appearing somewhere.
        """
        raw = next(ln for ln in self.text.split("\n")
                   if ln.lstrip().startswith("- **Lane C"))
        bullet = self._plainly(raw)
        for signal in ("cve/ghsa identifier", "advisory-site url",
                       "implementation-source file", "operator-confirmation-required"):
            self.assertIn(signal, bullet, f"Lane C bullet lost: {signal}")
        self.assertIn("never cited until the operator says so", bullet)


if __name__ == "__main__":
    unittest.main()
