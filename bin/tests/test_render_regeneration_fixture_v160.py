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
The regenerated manifest must carry the *same records* as the input manifest,
differing only by the Phase E.6 renumber — same count, same content, same
references. :class:`ManifestUnchangedInvariantTests` pins that.
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


def _run_render_contract_on_before(target, skill_version="1.5.8"):
    """Run the contract against the preserved pre-v1.6.0 render.

    Stages into a temporary tree rather than swapping files inside the
    committed fixture: an in-place swap leaves the fixture corrupted if the
    process dies mid-test, and races any concurrent test run.
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


class ManifestUnchangedInvariantTests(unittest.TestCase):
    """Feature C is presentation-layer: same records, renumbered only.

    Plan Phase 1 work item — ``requirements_manifest.json`` for a fixed
    input is unchanged modulo the renumber map. This is what makes Feature C
    safe to land ahead of the FP-audit, which consumes the manifest and
    must not be perturbed by render changes.
    """

    def _pairs(self, target):
        before = _load_json(target, "requirements_manifest.before.json")["records"]
        after = _load_json(target, "requirements_manifest.json")["records"]
        return before, after

    def test_record_count_is_unchanged(self):
        for target in TARGETS:
            with self.subTest(target=target):
                before, after = self._pairs(target)
                self.assertEqual(
                    len(before), len(after),
                    f"{target}: the renumber changed the record count — "
                    "Feature C must not add, drop, or merge requirements "
                    "(references/requirements_pipeline.md Phase E rules).",
                )

    def test_reference_sets_are_preserved(self):
        """References are the REQ's grounding; a renumber must not touch them."""
        for target in TARGETS:
            with self.subTest(target=target):
                before, after = self._pairs(target)
                before_refs = sorted(
                    tuple(sorted(str(x) for x in (r.get("references") or [])))
                    for r in before
                )
                after_refs = sorted(
                    tuple(sorted(str(x) for x in (r.get("references") or [])))
                    for r in after
                )
                self.assertEqual(
                    before_refs, after_refs,
                    f"{target}: the set of reference lists changed across the "
                    "renumber — Feature C is presentation-layer.",
                )

    def test_ids_remain_a_dense_sequential_block(self):
        for target in TARGETS:
            with self.subTest(target=target):
                _before, after = self._pairs(target)
                ids = sorted(int(r["id"].split("-")[1]) for r in after)
                self.assertEqual(
                    ids, list(range(1, len(ids) + 1)),
                    f"{target}: renumbered manifest ids are not a dense "
                    "REQ-001..REQ-NNN block.",
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
