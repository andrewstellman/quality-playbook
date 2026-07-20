"""v1.6.0 Feature C — the regeneration fixture (the coherence acceptance oracle).

``QPB_v1.6.0_Design.md`` §5 names the acceptance oracle for Feature C:
re-render the chi, express, and virtio manifests through the new renderer
and confirm defects C-1..C-7 are absent. This module pins that oracle so it
stays satisfied — a later change to the render contract, the reference
docs, or the gate that reintroduces any of the seven defect classes into
the regenerated fixtures fails here.

Fixture layout (``bin/tests/fixtures/render_contract_v160/<target>/quality/``):

    REQUIREMENTS.before.md            the 2026-06-19 v1.5.8 render (the C-1..C-7 evidence)
    requirements_manifest.before.json the manifest that produced it
    REQUIREMENTS.md                   re-rendered through the v1.6.0 contract
    RUN_CONTRACT.md                   the tool-contract split-out (Design §5.1)
    requirements_manifest.json        the same records, renumbered to document order

The ``.before`` artifacts are committed deliberately: they are the evidence
that the seven defects were real, and they make the before/after delta
reproducible without reaching into the gitignored ``repos/`` tree. The
pristine inputs live at ``repos/<target>-1.5.8/quality/`` and are read-only
per the v1.6.0 Implementation Plan Phase 0.

Manifest-unchanged invariant (Plan Phase 1): Feature C is presentation-layer.
The regenerated manifest carries the *same records* as the input manifest,
differing only by the Phase E.6 renumber **plus the two field rewrites the
design itself mandates** — intent-form titles (§5.4) and reassigned
``functional_section`` (§5.2 item 4) — plus ``conditions_of_satisfaction``
growing to absorb normative text a title rewrite displaced.
:class:`ManifestUnchangedInvariantTests` states that precisely and enforces
it record by record; see its docstring for why the Plan's one-line
"unchanged modulo the renumber map" is too strong for the work the design
mandates.
"""

import io
import json
import re
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = (
    REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook" / "scripts"
)
sys.path.insert(0, str(SCRIPT_DIR))

import quality_gate  # noqa: E402

FIXTURE_ROOT = REPO_ROOT / "bin" / "tests" / "fixtures" / "render_contract_v160"

# The three benchmark shapes the design names as the regeneration fixture.
# Deliberately three different repo shapes (Go router / JS framework /
# C kernel subsystem) so the contract is not tuned to one document.
TARGETS = ("chi", "express", "virtio")

# The fixture is rendered as if by this skill version; the C-7 stamp check
# compares against it.
FIXTURE_SKILL_VERSION = "1.6.0"


def _load(target, name):
    return (FIXTURE_ROOT / target / "quality" / name).read_text(
        encoding="utf-8", errors="replace"
    )


def _load_json(target, name):
    return json.loads(_load(target, name))


def _norm(text):
    """Normalize markdown emphasis/backticks and whitespace for comparison."""
    return re.sub(r"\s+", " ", re.sub(r"[`*_]", "", str(text))).strip()


def _run_render_contract(target, skill_version=FIXTURE_SKILL_VERSION):
    """Return (fail_count, warn_count, stdout) for one fixture target."""
    repo = FIXTURE_ROOT / target
    q = repo / "quality"
    quality_gate.FAIL = 0
    quality_gate.WARN = 0
    quality_gate._FAIL_RECORDS = []
    quality_gate._WARN_RECORDS = []
    buf = io.StringIO()
    with redirect_stdout(buf):
        quality_gate.check_render_contract(repo, q, skill_version)
    return quality_gate.FAIL, quality_gate.WARN, buf.getvalue()


def _run_render_contract_on_before(target, skill_version=FIXTURE_SKILL_VERSION):
    """Run the contract against the preserved pre-v1.6.0 render.

    Stages into a temporary tree rather than swapping files inside the
    committed fixture: an in-place swap leaves the fixture corrupted if the
    process dies mid-test, and races any concurrent test run.

    Deliberately evaluates the before-document *as if* it were a v1.6.0
    render (no PROGRESS.md is staged, and the skill version passed is the
    fixture's). The question this harness asks is "does the contract
    discriminate between the old shape and the new one?", which requires
    holding the version constant. Whether a real 1.5.8 run is *obligated*
    to satisfy the contract is a separate question, answered by the version
    predicate and pinned in RenderContractVersionGatingTests.
    """
    src = FIXTURE_ROOT / target / "quality"
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp) / target
        q = repo / "quality"
        q.mkdir(parents=True)
        shutil.copy2(src / "REQUIREMENTS.before.md", q / "REQUIREMENTS.md")
        shutil.copy2(
            src / "requirements_manifest.before.json",
            q / "requirements_manifest.json",
        )
        quality_gate.FAIL = 0
        quality_gate.WARN = 0
        quality_gate._FAIL_RECORDS = []
        quality_gate._WARN_RECORDS = []
        buf = io.StringIO()
        with redirect_stdout(buf):
            quality_gate.check_render_contract(repo, q, skill_version)
        return quality_gate.FAIL, quality_gate.WARN, buf.getvalue()


class FixturePresenceTests(unittest.TestCase):
    """The oracle cannot run against fixtures that are not there."""

    def test_every_target_has_the_full_fixture_set(self):
        for target in TARGETS:
            for name in (
                "REQUIREMENTS.md",
                "RUN_CONTRACT.md",
                "requirements_manifest.json",
                "REQUIREMENTS.before.md",
                "requirements_manifest.before.json",
            ):
                with self.subTest(target=target, artifact=name):
                    path = FIXTURE_ROOT / target / "quality" / name
                    self.assertTrue(path.is_file(), f"missing fixture: {path}")
                    self.assertGreater(
                        path.stat().st_size, 0, f"empty fixture: {path}"
                    )

    def test_fixture_spans_three_distinct_repo_shapes(self):
        self.assertEqual(len(set(TARGETS)), 3)


class RegenerationOracleTests(unittest.TestCase):
    """The acceptance oracle: C-1..C-7 absent from all three re-renders."""

    def test_regenerated_documents_pass_the_render_contract(self):
        for target in TARGETS:
            with self.subTest(target=target):
                fails, _warns, out = _run_render_contract(target)
                self.assertEqual(
                    fails, 0,
                    f"{target}: regenerated REQUIREMENTS.md violates the "
                    f"render contract — the Feature C acceptance oracle "
                    f"(Design §5, §10 criterion 1) is not satisfied:\n{out}",
                )

    def test_regenerated_documents_emit_no_advisory_warnings(self):
        """F-1: every regenerated Overview carries a coverage-and-gaps statement."""
        for target in TARGETS:
            with self.subTest(target=target):
                _fails, warns, out = _run_render_contract(target)
                self.assertEqual(warns, 0, f"{target}:\n{out}")

    def test_before_documents_still_exhibit_the_defects(self):
        """The mutation bite for the whole oracle.

        If the pre-v1.6.0 renders stopped failing the contract, the oracle
        would be vacuous — it would be proving nothing about the fix. Each
        ``.before`` document must still FAIL.
        """
        for target in TARGETS:
            with self.subTest(target=target):
                fails, _warns, out = _run_render_contract_on_before(target)
                self.assertGreater(
                    fails, 0,
                    f"{target}: the pre-v1.6.0 render no longer fails the "
                    "render contract — the regeneration oracle would be "
                    f"vacuous:\n{out}",
                )


class ToolContractSplitTests(unittest.TestCase):
    """C-1: the eight run-layout invariants left the product spec."""

    def test_product_spec_carries_no_quality_only_reqs(self):
        for target in TARGETS:
            with self.subTest(target=target):
                manifest = _load_json(target, "requirements_manifest.json")
                tool_ids = {
                    r["id"] for r in manifest["records"]
                    if r.get("references")
                    and all(str(x).startswith("quality/") for x in r["references"])
                }
                self.assertTrue(
                    tool_ids, f"{target}: fixture has no tool-contract records"
                )
                rendered = _load(target, "REQUIREMENTS.md")
                for rid in sorted(tool_ids):
                    self.assertNotIn(
                        f"### {rid}:", rendered,
                        f"{target}: tool-contract {rid} rendered into the "
                        "product spec (C-1).",
                    )

    def test_run_contract_carries_every_tool_req(self):
        for target in TARGETS:
            with self.subTest(target=target):
                manifest = _load_json(target, "requirements_manifest.json")
                tool_ids = {
                    r["id"] for r in manifest["records"]
                    if r.get("references")
                    and all(str(x).startswith("quality/") for x in r["references"])
                }
                run_contract = _load(target, "RUN_CONTRACT.md")
                for rid in sorted(tool_ids):
                    self.assertIn(
                        f"### {rid}:", run_contract,
                        f"{target}: tool-contract {rid} was dropped rather "
                        "than relocated.",
                    )

    def test_run_contract_states_it_is_not_the_product_spec(self):
        # Normalize whitespace and markdown emphasis before matching: the
        # renderer is free to wrap lines and to bold the disclaimer, so an
        # exact-substring assertion would pin prose style, not meaning.
        for target in TARGETS:
            with self.subTest(target=target):
                raw = _load(target, "RUN_CONTRACT.md").lower()
                text = re.sub(r"[*_`]", "", raw)
                text = re.sub(r"\s+", " ", text)
                self.assertTrue(
                    "not requirements of the audited system" in text
                    or "not a requirement of the audited system" in text,
                    f"{target}: RUN_CONTRACT.md must say plainly that it "
                    "records QPB's own run-layout invariants, so a reader "
                    "cannot mistake it for the product spec.",
                )

    def test_run_contract_points_back_at_the_product_spec(self):
        for target in TARGETS:
            with self.subTest(target=target):
                self.assertIn(
                    "REQUIREMENTS.md", _load(target, "RUN_CONTRACT.md"),
                    f"{target}: RUN_CONTRACT.md must point the reader at the "
                    "product spec.",
                )


# Fields Feature C is allowed to change, and why. Everything else must be
# byte-identical across the render.
#
#   id                  Phase E.6 renumber to document order (Design §5.3 #1)
#   title               intent-form normalization (Design §5.4)
#   functional_section  Phase E.5 reorder/merge (Design §5.2 item 4)
#   conditions_of_satisfaction
#                       may only GROW, by absorbing the normative sentence a
#                       title rewrite displaced — never shrink. Without this
#                       the manifest loses contract text that survives only
#                       in rendered prose, and the FP-audit (which consumes
#                       the manifest, never the render) sees a weaker
#                       requirement than a human reader does.
_MUTABLE_FIELDS = frozenset(
    {"id", "title", "functional_section", "conditions_of_satisfaction"}
)


class ManifestUnchangedInvariantTests(unittest.TestCase):
    """Feature C is presentation-layer, stated precisely.

    The Implementation Plan (:45) says ``requirements_manifest.json`` is
    "unchanged modulo the renumber map". That phrasing is **too strong for
    the work the design itself mandates** — §5.4's intent-form rule rewrites
    titles and §5.2's section merges rewrite ``functional_section``. The
    honest invariant, enforced here, is:

        unchanged modulo (a) the renumber map, (b) title normalization,
        (c) functional_section reassignment, and (d) conditions_of_
        satisfaction growing to absorb displaced title text.

    Every other field is byte-identical, and no record is added, dropped,
    merged, or weakened.

    This class is the safety rail for landing Feature C ahead of the
    FP-audit, so it pairs records through the explicit renumber map and
    compares field by field. The previous version compared a *multiset* of
    reference-lists, which survived rotating every REQ's references onto the
    wrong record — see the mutation tests at the bottom.

    (Divergence reported to the orchestrator: the Plan's one-line invariant
    should be reconciled with this statement. The plan is the Cowork-editable
    planning surface, so this worker did not edit it.)
    """

    def _paired(self, target):
        """Yield (before_record, after_record) through the renumber map."""
        before = {
            r["id"]: r
            for r in _load_json(target, "requirements_manifest.before.json")["records"]
        }
        after = {
            r["id"]: r
            for r in _load_json(target, "requirements_manifest.json")["records"]
        }
        rmap = _load_json(target, "renumber_map.json")
        for old_id, new_id in rmap.items():
            yield old_id, new_id, before[old_id], after[new_id]

    def test_renumber_map_is_a_total_bijection(self):
        """A partial or many-to-one map would let records vanish silently."""
        for target in TARGETS:
            with self.subTest(target=target):
                before = _load_json(
                    target, "requirements_manifest.before.json"
                )["records"]
                after = _load_json(target, "requirements_manifest.json")["records"]
                rmap = _load_json(target, "renumber_map.json")
                self.assertEqual(
                    sorted(rmap), sorted(r["id"] for r in before),
                    f"{target}: renumber map domain != before-manifest ids",
                )
                self.assertEqual(
                    sorted(rmap.values()), sorted(r["id"] for r in after),
                    f"{target}: renumber map range != after-manifest ids",
                )
                self.assertEqual(
                    len(set(rmap.values())), len(rmap),
                    f"{target}: renumber map is not injective — two records "
                    "collapsed onto one id.",
                )

    def test_record_count_is_unchanged(self):
        for target in TARGETS:
            with self.subTest(target=target):
                before = _load_json(
                    target, "requirements_manifest.before.json"
                )["records"]
                after = _load_json(target, "requirements_manifest.json")["records"]
                self.assertEqual(
                    len(before), len(after),
                    f"{target}: record count changed — Feature C must not "
                    "add, drop, or merge requirements.",
                )

    def test_every_immutable_field_is_byte_identical_per_record(self):
        """The real invariant. Kills the 'gut every record' mutation."""
        for target in TARGETS:
            for old_id, new_id, b, a in self._paired(target):
                fields = (set(b) | set(a)) - _MUTABLE_FIELDS
                for field in sorted(fields):
                    with self.subTest(target=target, req=old_id, field=field):
                        self.assertEqual(
                            b.get(field), a.get(field),
                            f"{target}: {old_id}->{new_id} field {field!r} "
                            "changed. Feature C is presentation-layer; only "
                            f"{sorted(_MUTABLE_FIELDS)} may change.",
                        )

    def test_references_stay_attached_to_their_own_record(self):
        """Kills the 'rotate references' mutation.

        A multiset comparison cannot see this: rotating references across
        records preserves the multiset while making every REQ cite the
        wrong source file.
        """
        for target in TARGETS:
            for old_id, new_id, b, a in self._paired(target):
                with self.subTest(target=target, req=old_id):
                    self.assertEqual(
                        b.get("references"), a.get("references"),
                        f"{target}: {old_id}->{new_id} references moved to a "
                        "different record. References are the REQ's "
                        "grounding.",
                    )

    def test_conditions_of_satisfaction_never_shrink(self):
        """Title normalization must not silently drop normative content."""
        for target in TARGETS:
            for old_id, new_id, b, a in self._paired(target):
                before_cos = (b.get("conditions_of_satisfaction") or "").strip()
                after_cos = (a.get("conditions_of_satisfaction") or "").strip()
                if not before_cos:
                    continue
                with self.subTest(target=target, req=old_id):
                    self.assertIn(
                        before_cos, after_cos,
                        f"{target}: {old_id}->{new_id} conditions of "
                        "satisfaction lost content.",
                    )

    def test_displaced_title_text_survives_in_the_manifest(self):
        """A rewritten title must not take its contract text out of the manifest.

        The FP-audit consumes the manifest and never the rendered document,
        so a normative sentence that lives only in rendered prose is
        invisible to it.
        """
        for target in TARGETS:
            for old_id, new_id, b, a in self._paired(target):
                old_title = (b.get("title") or "").strip().rstrip(".")
                if not old_title or old_title == (a.get("title") or "").strip():
                    continue
                haystack = " ".join(
                    str(a.get(f) or "")
                    for f in ("title", "conditions_of_satisfaction", "text",
                              "implementation")
                )
                with self.subTest(target=target, req=old_id):
                    self.assertIn(
                        old_title, haystack,
                        f"{target}: {old_id}->{new_id} was retitled and the "
                        "displaced normative sentence is not anywhere in the "
                        "record — it survives only in rendered prose.",
                    )

    def test_ids_remain_a_dense_sequential_block(self):
        for target in TARGETS:
            with self.subTest(target=target):
                after = _load_json(target, "requirements_manifest.json")["records"]
                ids = sorted(int(r["id"].split("-")[1]) for r in after)
                self.assertEqual(
                    ids, list(range(1, len(ids) + 1)),
                    f"{target}: renumbered manifest ids are not a dense "
                    "REQ-001..REQ-NNN block.",
                )

    def test_manifest_titles_match_the_rendered_titles(self):
        """The two sanctioned mutable fields still have to agree with the render.

        Without this, the mutable-field allowlist is a hole: `title` is
        allowed to change, so every title could be replaced with a
        placeholder and the invariant would still report green. The manifest
        is the source of truth and the render is a presentation of it — they
        must say the same thing.
        """
        for target in TARGETS:
            records = {
                r["id"]: r
                for r in _load_json(target, "requirements_manifest.json")["records"]
            }
            rendered = _load(target, "REQUIREMENTS.md") + _load(
                target, "RUN_CONTRACT.md"
            )
            for m in quality_gate._RENDER_REQ_HEADING_RE.finditer(rendered):
                rid, title = m.group(1), m.group(3).strip()
                rec = records.get(rid)
                if rec is None or "title" not in rec:
                    continue
                with self.subTest(target=target, req=rid):
                    self.assertEqual(
                        _norm(rec["title"]), _norm(title),
                        f"{target}: {rid} manifest title and rendered title "
                        "disagree. The manifest is the source of truth; the "
                        "render is a presentation of it.",
                    )

    def test_no_record_loses_a_field_it_started_with(self):
        """Field *presence*, not just field agreement.

        Every per-record comparison skips a record whose field is missing
        (`if not rec.get(...): continue`), so dropping a single REQ's
        `title` or `functional_section` left the whole invariant green.
        That is the mirror image of the swap defect: the other checks ask
        "does this field agree with the render?" and never "is it there?".
        (Self-Council round 4, Mutation E4.)
        """
        for target in TARGETS:
            for old_id, new_id, b, a in self._paired(target):
                for field in sorted(b):
                    with self.subTest(target=target, req=old_id, field=field):
                        self.assertIn(
                            field, a,
                            f"{target}: {old_id}->{new_id} lost the {field!r} "
                            "field entirely.",
                        )
                        if isinstance(b[field], str) and b[field].strip():
                            self.assertTrue(
                                str(a.get(field) or "").strip(),
                                f"{target}: {old_id}->{new_id} blanked the "
                                f"{field!r} field.",
                            )

    def test_each_req_renders_under_the_section_its_record_names(self):
        """Per-record, not per-set.

        Comparing only the *set* of section names lets two records swap
        labels undetected — the same set-vs-per-record weakness that
        Mutation B exposed in the references check, which is why this
        assertion walks each REQ to the heading it actually renders under.
        (Self-Council round 3, Mutation E3.)
        """
        for target in TARGETS:
            records = {
                r["id"]: r
                for r in _load_json(target, "requirements_manifest.json")["records"]
            }
            for doc in ("REQUIREMENTS.md", "RUN_CONTRACT.md"):
                rendered = _load(target, doc)
                # Walk the document, tracking the most recent level-2
                # heading, and check each REQ against its record.
                current = None
                for line in rendered.splitlines():
                    heading = re.match(r"^##\s+(.+)$", line)
                    if heading:
                        current = _norm(heading.group(1))
                        continue
                    req = re.match(r"^###\s+(REQ-\d+)\s*:", line)
                    if not req:
                        continue
                    rec = records.get(req.group(1))
                    if rec is None or not rec.get("functional_section"):
                        continue
                    with self.subTest(target=target, req=req.group(1)):
                        self.assertEqual(
                            _norm(rec["functional_section"]), current,
                            f"{target}: {req.group(1)} renders under "
                            f"{current!r} but its record names "
                            f"{rec['functional_section']!r}. The manifest is "
                            "the source of truth; the render presents it.",
                        )

    def test_rendered_ids_match_the_manifest_ids(self):
        """The manifest and both renderings must agree on every identifier."""
        for target in TARGETS:
            with self.subTest(target=target):
                manifest_ids = {
                    r["id"] for r in _load_json(target, "requirements_manifest.json")["records"]
                }
                rendered = _load(target, "REQUIREMENTS.md") + _load(
                    target, "RUN_CONTRACT.md"
                )
                rendered_ids = {
                    m.group(1)
                    for m in quality_gate._RENDER_REQ_HEADING_RE.finditer(rendered)
                }
                self.assertEqual(
                    manifest_ids, rendered_ids,
                    f"{target}: manifest ids and rendered ids diverge. The "
                    "manifest is the source of truth; the renderings must be "
                    "faithful presentations of it.",
                )


class ManifestInvariantMutationTests(unittest.TestCase):
    """Mutation bites for :class:`ManifestUnchangedInvariantTests`.

    These run the **real** assertion methods against a mutated fixture tree
    and require them to fail. An earlier version re-implemented the
    comparison inline, which meant gutting every method of the class under
    test left the bites green — a bite that does not exercise the code it
    guards is theatre. (Instruction-001 self-Council round 2.)
    """

    def _run_invariants_against(self, tmpdir):
        """Run ManifestUnchangedInvariantTests against a staged tree.

        Returns the number of failures+errors. Patches the module-level
        FIXTURE_ROOT so the real test methods read the mutated copy.
        """
        module = sys.modules[__name__]
        original = module.FIXTURE_ROOT
        module.FIXTURE_ROOT = Path(tmpdir)
        try:
            suite = unittest.TestLoader().loadTestsFromTestCase(
                ManifestUnchangedInvariantTests
            )
            result = unittest.TextTestRunner(
                stream=io.StringIO(), verbosity=0
            ).run(suite)
            return len(result.failures) + len(result.errors)
        finally:
            module.FIXTURE_ROOT = original

    def _staged(self, tmpdir, mutate):
        """Copy the fixture tree, apply `mutate` to each after-manifest."""
        for target in TARGETS:
            src = FIXTURE_ROOT / target / "quality"
            dst = Path(tmpdir) / target / "quality"
            dst.mkdir(parents=True)
            for name in (
                "REQUIREMENTS.md", "RUN_CONTRACT.md",
                "REQUIREMENTS.before.md",
                "requirements_manifest.before.json", "renumber_map.json",
            ):
                shutil.copy2(src / name, dst / name)
            payload = json.loads(
                (src / "requirements_manifest.json").read_text(encoding="utf-8")
            )
            payload["records"] = mutate(payload["records"])
            (dst / "requirements_manifest.json").write_text(
                json.dumps(payload, indent=2), encoding="utf-8"
            )

    def test_the_bite_harness_passes_on_the_unmutated_fixture(self):
        """Control. Without this, every bite below could be passing for free."""
        with tempfile.TemporaryDirectory() as tmp:
            self._staged(tmp, lambda records: records)
            self.assertEqual(
                self._run_invariants_against(tmp), 0,
                "the invariant class must pass on an unmutated copy of the "
                "fixture — otherwise the mutation bites prove nothing.",
            )

    def test_mutation_a_gutted_records_are_detected(self):
        """Replace every non-id, non-reference field with a placeholder."""
        def gut(records):
            return [
                {k: (v if k in ("id", "references") else "PWNED")
                 for k, v in r.items()}
                for r in records
            ]
        with tempfile.TemporaryDirectory() as tmp:
            self._staged(tmp, gut)
            self.assertGreater(
                self._run_invariants_against(tmp), 0,
                "gutting every record's content did not fail the invariant "
                "class — the invariant is vacuous.",
            )

    def test_mutation_b_rotated_references_are_detected(self):
        """Shift references by one so every REQ cites the wrong file.

        The multiset of reference-lists is unchanged by this mutation, which
        is exactly why the original multiset comparison could not see it.
        """
        def rotate(records):
            refs = [r.get("references") for r in records]
            refs = refs[1:] + refs[:1]
            out = []
            for r, new_refs in zip(records, refs):
                copy = dict(r)
                copy["references"] = new_refs
                out.append(copy)
            return out
        with tempfile.TemporaryDirectory() as tmp:
            self._staged(tmp, rotate)
            self.assertGreater(
                self._run_invariants_against(tmp), 0,
                "rotating references across records was not detected — "
                "per-record attachment is not being checked.",
            )

    def test_mutation_c_stubbed_titles_are_detected(self):
        """Exploit the mutable-field allowlist: stub every title.

        `title` is allowed to change (intent-form normalization), so a naive
        allowlist lets a renderer replace every title with a placeholder and
        still pass. The displaced-title check is what closes it.
        """
        def stub(records):
            out = []
            for r in records:
                copy = dict(r)
                if "title" in copy:
                    copy["title"] = "REQ"
                out.append(copy)
            return out
        with tempfile.TemporaryDirectory() as tmp:
            self._staged(tmp, stub)
            self.assertGreater(
                self._run_invariants_against(tmp), 0,
                "stubbing every title was not detected — the mutable-field "
                "allowlist is being trusted without a content check.",
            )

    def test_mutation_d_flattened_sections_are_detected(self):
        """Exploit the allowlist the other way: collapse every section.

        `functional_section` is allowed to change (Phase E.5 merges), but
        collapsing all of them into one is the degenerate case §5.2 exists
        to reject, and the manifest must agree with the rendered document.
        """
        def flatten(records):
            out = []
            for r in records:
                copy = dict(r)
                if "functional_section" in copy:
                    copy["functional_section"] = "Everything"
                out.append(copy)
            return out
        with tempfile.TemporaryDirectory() as tmp:
            self._staged(tmp, flatten)
            self.assertGreater(
                self._run_invariants_against(tmp), 0,
                "flattening every functional_section was not detected — the "
                "manifest and the rendered document no longer agree.",
            )

    def test_multiset_comparison_alone_would_miss_rotation(self):
        """Documents *why* the per-record check exists, not just that it does."""
        for target in TARGETS:
            with self.subTest(target=target):
                after = _load_json(
                    target, "requirements_manifest.json"
                )["records"]
                refs = [tuple(r.get("references") or []) for r in after]
                rotated = refs[1:] + refs[:1]
                self.assertEqual(
                    sorted(refs), sorted(rotated),
                    "rotation should preserve the multiset — if this fails "
                    "the fixture no longer demonstrates the weakness the "
                    "per-record check was added to close.",
                )


class BeforeAfterDeltaTests(unittest.TestCase):
    """The before/after delta is the evidence the design asks for."""

    def test_every_before_document_fails_more_than_its_after(self):
        for target in TARGETS:
            with self.subTest(target=target):
                before_fails, _bw, _bo = _run_render_contract_on_before(target)
                after_fails, _aw, _ao = _run_render_contract(target)
                self.assertGreater(before_fails, after_fails)
                self.assertEqual(after_fails, 0)

    def test_fixture_files_are_not_mutated_by_the_test_run(self):
        """Guard: the before/after comparison must stage into a temp tree.

        An in-place swap of REQUIREMENTS.md would leave the committed
        fixture corrupted if the process died mid-test.
        """
        digests = {}
        for target in TARGETS:
            q = FIXTURE_ROOT / target / "quality"
            for name in ("REQUIREMENTS.md", "REQUIREMENTS.before.md"):
                digests[(target, name)] = (q / name).read_bytes()
        for target in TARGETS:
            _run_render_contract_on_before(target)
            _run_render_contract(target)
        for (target, name), original in digests.items():
            with self.subTest(target=target, artifact=name):
                current = (FIXTURE_ROOT / target / "quality" / name).read_bytes()
                self.assertEqual(
                    current, original,
                    f"{target}/{name} was mutated by the test run.",
                )


if __name__ == "__main__":
    unittest.main()
