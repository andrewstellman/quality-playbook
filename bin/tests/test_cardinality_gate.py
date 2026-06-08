"""Merge-gate anchor tests for the v1.5.2 cardinality reconciliation gate.

The adversarial test (test_adversarial_three_cells_one_cover_fails) is the
release-blocking merge gate. Until it passes against the current pipeline,
v1.5.2 is not load-bearing.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

# v1.5.8 instruction 209: quality_gate.py now lives under the
# standard self-hosted marketplace layout at
# plugins/quality-playbook/skills/quality-playbook/scripts/. 208
# placed it at skills/quality-playbook/scripts/; that path is
# retained as a fallback for transitional clones.
QPB_ROOT = Path(__file__).resolve().parent.parent.parent
_GATE_DIR_209 = (
    QPB_ROOT / "plugins" / "quality-playbook"
    / "skills" / "quality-playbook" / "scripts"
)
_GATE_DIR_208 = QPB_ROOT / "skills" / "quality-playbook" / "scripts"
GATE_DIR = _GATE_DIR_209 if _GATE_DIR_209.is_dir() else _GATE_DIR_208
sys.path.insert(0, str(GATE_DIR))

import quality_gate  # type: ignore

_MISSING = object()  # sentinel for "key absent" in fixture builders


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _fixture_grid(req_id: str, cells_present: dict) -> dict:
    """Build a minimal compensation_grid.json dict.

    cells_present: dict mapping cell_id → bool (True = present, False = absent).
    """
    return {
        "schema_version": "1.5.2",
        "reqs": {
            req_id: {
                "pattern": "whitelist",
                "items": ["ITEM_A", "ITEM_B", "ITEM_C"],
                "sites": ["SITE"],
                "cells": [
                    {"cell_id": cid, "item": cid.split("-")[-2], "site": cid.split("-")[-1], "present": present}
                    for cid, present in cells_present.items()
                ],
            }
        },
    }


def _requirements_md(req_id: str, pattern: str = "whitelist") -> str:
    return (
        f"# Requirements\n\n"
        f"### {req_id}: test requirement\n"
        f"- Summary: test\n"
        f"- Pattern: {pattern}\n"
    )


def _bugs_md(bug_entries: list) -> str:
    out = ["# Bug Report\n\n"]
    for bug in bug_entries:
        out.append(f"### BUG-{bug['id']}: {bug.get('title', 'test bug')}\n")
        out.append(f"- Primary requirement: {bug['req']}\n")
        if bug.get("covers"):
            out.append(f"- Covers: [{', '.join(bug['covers'])}]\n")
        if bug.get("rationale"):
            out.append(f"- Consolidation rationale: {bug['rationale']}\n")
        out.append("\n")
    return "".join(out)


class CardinalityGateTests(unittest.TestCase):

    # ---- MERGE-GATE ANCHOR ----------------------------------------------
    def test_adversarial_three_cells_one_cover_fails(self):
        """Adversarial fixture: grid has 3 absent cells, reviewer covers 1.

        This is the release-blocking merge gate for v1.5.2. A correctly
        implemented gate MUST fail and name the two uncovered cells.
        """
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            q = repo / "quality"
            cells = {
                "REQ-010/cell-RING_RESET-MMIO": False,
                "REQ-010/cell-RING_RESET-vDPA": False,
                "REQ-010/cell-SR_IOV-MMIO": False,
            }
            _write(q / "compensation_grid.json", json.dumps(_fixture_grid("REQ-010", cells)))
            _write(q / "REQUIREMENTS.md", _requirements_md("REQ-010"))
            _write(q / "BUGS.md", _bugs_md([
                {
                    "id": "001",
                    "req": "REQ-010",
                    "covers": ["REQ-010/cell-RING_RESET-MMIO"],
                },
            ]))

            failures = quality_gate.validate_cardinality_gate(repo)

            self.assertTrue(
                failures,
                "MERGE GATE FAILURE: cardinality gate let a 3-cell/1-cover "
                "adversarial fixture pass. v1.5.2 is not load-bearing.",
            )
            combined = " ".join(failures)
            self.assertIn("REQ-010/cell-RING_RESET-vDPA", combined)
            self.assertIn("REQ-010/cell-SR_IOV-MMIO", combined)
            uncovered_line = next((f for f in failures if "uncovered" in f), "")
            self.assertNotIn("REQ-010/cell-RING_RESET-MMIO", uncovered_line,
                             "covered cell should not appear as uncovered")
    # ---------------------------------------------------------------------

    def test_all_cells_covered_by_bugs_passes(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            q = repo / "quality"
            cells = {
                "REQ-010/cell-A-SITE": False,
                "REQ-010/cell-B-SITE": False,
            }
            _write(q / "compensation_grid.json", json.dumps(_fixture_grid("REQ-010", cells)))
            _write(q / "REQUIREMENTS.md", _requirements_md("REQ-010"))
            _write(q / "BUGS.md", _bugs_md([
                {"id": "001", "req": "REQ-010", "covers": ["REQ-010/cell-A-SITE"]},
                {"id": "002", "req": "REQ-010", "covers": ["REQ-010/cell-B-SITE"]},
            ]))
            self.assertEqual(quality_gate.validate_cardinality_gate(repo), [])

    def test_mix_of_bugs_and_downgrades_passes(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            q = repo / "quality"
            cells = {
                "REQ-010/cell-A-SITE": False,
                "REQ-010/cell-B-SITE": False,
            }
            _write(q / "compensation_grid.json", json.dumps(_fixture_grid("REQ-010", cells)))
            _write(q / "REQUIREMENTS.md", _requirements_md("REQ-010"))
            _write(q / "BUGS.md", _bugs_md([
                {"id": "001", "req": "REQ-010", "covers": ["REQ-010/cell-A-SITE"]},
            ]))
            _write(q / "compensation_grid_downgrades.json", json.dumps({
                "schema_version": "1.5.2",
                "downgrades": [{
                    "cell_id": "REQ-010/cell-B-SITE",
                    "authority_ref": "docs/spec.md:1",
                    "site_citation": "src/thing.py:10-20",
                    "reason_class": "out-of-scope",
                    "falsifiable_claim": "B is not required here because spec scopes it to A-only; falsifiable by showing spec text requiring B.",
                }],
            }))
            self.assertEqual(quality_gate.validate_cardinality_gate(repo), [])

    def test_no_pattern_reqs_skips_gate(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            q = repo / "quality"
            _write(q / "REQUIREMENTS.md", "# Requirements\n\n### REQ-001: plain req\n- Summary: x\n")
            # No grid file, no pattern REQs → gate passes silently.
            self.assertEqual(quality_gate.validate_cardinality_gate(repo), [])

    def test_pattern_req_without_grid_fails(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            q = repo / "quality"
            _write(q / "REQUIREMENTS.md", _requirements_md("REQ-010"))
            # No compensation_grid.json — this should fail.
            failures = quality_gate.validate_cardinality_gate(repo)
            self.assertTrue(any("compensation_grid.json is missing" in f for f in failures))

    def test_downgrade_missing_falsifiable_claim_fails(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            q = repo / "quality"
            cells = {"REQ-010/cell-A-SITE": False}
            _write(q / "compensation_grid.json", json.dumps(_fixture_grid("REQ-010", cells)))
            _write(q / "REQUIREMENTS.md", _requirements_md("REQ-010"))
            _write(q / "BUGS.md", "")
            _write(q / "compensation_grid_downgrades.json", json.dumps({
                "schema_version": "1.5.2",
                "downgrades": [{
                    "cell_id": "REQ-010/cell-A-SITE",
                    "authority_ref": "docs/spec.md:1",
                    "site_citation": "src/x.py:1",
                    "reason_class": "out-of-scope",
                    "falsifiable_claim": "",
                }],
            }))
            failures = quality_gate.validate_cardinality_gate(repo)
            self.assertTrue(any("falsifiable_claim" in f for f in failures))

    def test_downgrade_invalid_reason_class_fails(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            q = repo / "quality"
            cells = {"REQ-010/cell-A-SITE": False}
            _write(q / "compensation_grid.json", json.dumps(_fixture_grid("REQ-010", cells)))
            _write(q / "REQUIREMENTS.md", _requirements_md("REQ-010"))
            _write(q / "BUGS.md", "")
            _write(q / "compensation_grid_downgrades.json", json.dumps({
                "schema_version": "1.5.2",
                "downgrades": [{
                    "cell_id": "REQ-010/cell-A-SITE",
                    "authority_ref": "docs/spec.md:1",
                    "site_citation": "src/x.py:1",
                    "reason_class": "made-up-reason",
                    "falsifiable_claim": "Claim text.",
                }],
            }))
            failures = quality_gate.validate_cardinality_gate(repo)
            self.assertTrue(any("reason_class" in f for f in failures))

    def test_multi_cell_covers_without_consolidation_rationale_fails(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            q = repo / "quality"
            cells = {
                "REQ-010/cell-A-SITE": False,
                "REQ-010/cell-B-SITE": False,
            }
            _write(q / "compensation_grid.json", json.dumps(_fixture_grid("REQ-010", cells)))
            _write(q / "REQUIREMENTS.md", _requirements_md("REQ-010"))
            _write(q / "BUGS.md", _bugs_md([
                {
                    "id": "001",
                    "req": "REQ-010",
                    "covers": ["REQ-010/cell-A-SITE", "REQ-010/cell-B-SITE"],
                },
            ]))
            failures = quality_gate.validate_cardinality_gate(repo)
            self.assertTrue(any("Consolidation rationale" in f for f in failures))

    # ---- Grid-omission cross-check (Round 4 Council convergent finding) ----
    def _two_req_requirements_md(self, reqs):
        """reqs: list of (req_id, pattern_or_None) tuples."""
        out = ["# Requirements\n\n"]
        for req_id, pattern in reqs:
            out.append("### {}: test requirement\n".format(req_id))
            out.append("- Summary: test\n")
            if pattern is not None:
                out.append("- Pattern: {}\n".format(pattern))
            out.append("\n")
        return "".join(out)

    def test_grid_contains_all_pattern_tagged_reqs_passes(self):
        """Positive case: every pattern-tagged REQ appears in the grid."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            q = repo / "quality"
            grid = {
                "schema_version": "1.5.2",
                "reqs": {
                    "REQ-001": {
                        "pattern": "whitelist",
                        "items": ["A"], "sites": ["S"],
                        "cells": [{"cell_id": "REQ-001/cell-A-S", "item": "A", "site": "S", "present": True, "evidence": "src/a.py:10"}],
                    },
                    "REQ-002": {
                        "pattern": "parity",
                        "items": ["B"], "sites": ["S"],
                        "cells": [{"cell_id": "REQ-002/cell-B-S", "item": "B", "site": "S", "present": True, "evidence": "src/b.py:20"}],
                    },
                },
            }
            _write(q / "compensation_grid.json", json.dumps(grid))
            _write(
                q / "REQUIREMENTS.md",
                self._two_req_requirements_md([("REQ-001", "whitelist"), ("REQ-002", "parity")]),
            )
            _write(q / "BUGS.md", "")
            self.assertEqual(quality_gate.validate_cardinality_gate(repo), [])

    def test_pattern_tagged_req_missing_from_grid_fails(self):
        """Grid-omission case: REQ-002 is pattern-tagged in REQUIREMENTS.md
        but missing from compensation_grid.json. Gate must surface exactly one
        failure naming REQ-002 and its pattern."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            q = repo / "quality"
            grid = {
                "schema_version": "1.5.2",
                "reqs": {
                    "REQ-001": {
                        "pattern": "whitelist",
                        "items": ["A"], "sites": ["S"],
                        "cells": [{"cell_id": "REQ-001/cell-A-S", "item": "A", "site": "S", "present": True, "evidence": "src/a.py:10"}],
                    },
                },
            }
            _write(q / "compensation_grid.json", json.dumps(grid))
            _write(
                q / "REQUIREMENTS.md",
                self._two_req_requirements_md([("REQ-001", "whitelist"), ("REQ-002", "parity")]),
            )
            _write(q / "BUGS.md", "")
            failures = quality_gate.validate_cardinality_gate(repo)
            matches = [f for f in failures if "REQ-002" in f and "compensation_grid.json" in f]
            self.assertEqual(
                len(matches), 1,
                "Expected exactly one failure naming REQ-002; got failures: {!r}".format(failures),
            )
            self.assertIn("parity", matches[0])

    def test_req_without_pattern_not_in_grid_passes(self):
        """Not-tagged-not-in-grid case: REQ-001 has no Pattern field; no grid
        entry is required. Gate passes with no failure from the cross-check."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            q = repo / "quality"
            _write(
                q / "REQUIREMENTS.md",
                self._two_req_requirements_md([("REQ-001", None)]),
            )
            # No grid file at all — legitimate when no REQ is pattern-tagged.
            self.assertEqual(quality_gate.validate_cardinality_gate(repo), [])

    def test_invalid_req_pattern_value_fails(self):
        """Invalid pattern case: REQUIREMENTS.md carries ``- Pattern: bogus``.
        ValueError from extract_req_pattern() must be surfaced as a
        REQUIREMENTS.md failure rather than crash the gate."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            q = repo / "quality"
            _write(q / "compensation_grid.json", json.dumps({"schema_version": "1.5.2", "reqs": {}}))
            _write(
                q / "REQUIREMENTS.md",
                self._two_req_requirements_md([("REQ-001", "bogus")]),
            )
            _write(q / "BUGS.md", "")
            failures = quality_gate.validate_cardinality_gate(repo)
            self.assertTrue(
                any("REQUIREMENTS.md:" in f and "bogus" in f for f in failures),
                "Expected a REQUIREMENTS.md failure naming 'bogus'; got: {!r}".format(failures),
            )
    # -----------------------------------------------------------------------

    # ---- Malformed-downgrade reconciliation bypass (Round 5 Finding B1) ----
    def test_downgrade_with_empty_authority_ref_does_not_cover_cell(self):
        """A downgrade record with empty authority_ref must emit a diagnostic
        failure AND leave the cell uncovered — prior to the rec_ok guard, the
        cell was silently counted as covered despite the diagnostic."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            q = repo / "quality"
            cells = {"REQ-010/cell-X-MMIO": False}
            _write(q / "compensation_grid.json", json.dumps(_fixture_grid("REQ-010", cells)))
            _write(q / "REQUIREMENTS.md", _requirements_md("REQ-010"))
            _write(q / "BUGS.md", "")
            _write(q / "compensation_grid_downgrades.json", json.dumps({
                "schema_version": "1.5.2",
                "downgrades": [{
                    "cell_id": "REQ-010/cell-X-MMIO",
                    "authority_ref": "",
                    "site_citation": "src/x.py:1",
                    "reason_class": "out-of-scope",
                    "falsifiable_claim": "placeholder claim",
                }],
            }))
            failures = quality_gate.validate_cardinality_gate(repo)
            # (i) The field-validation diagnostic must appear.
            self.assertTrue(
                any("authority_ref" in f and "missing or empty" in f for f in failures),
                "Expected 'missing or empty field authority_ref' diagnostic; got: {!r}".format(failures),
            )
            # (ii) The uncovered-cells failure must also appear; prior to the
            # rec_ok guard, the malformed record silently added the cell to
            # downgrade_cells_by_req and uncovered ≈ {} — the cell vanished.
            self.assertTrue(
                any("uncovered" in f and "REQ-010/cell-X-MMIO" in f for f in failures),
                "Expected 'uncovered cells' failure naming REQ-010/cell-X-MMIO; got: {!r}".format(failures),
            )

    def test_downgrade_with_invalid_reason_class_does_not_cover_cell(self):
        """Same bypass shape, but via reason_class enum violation instead of
        an empty field."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            q = repo / "quality"
            cells = {"REQ-010/cell-Y-MMIO": False}
            _write(q / "compensation_grid.json", json.dumps(_fixture_grid("REQ-010", cells)))
            _write(q / "REQUIREMENTS.md", _requirements_md("REQ-010"))
            _write(q / "BUGS.md", "")
            _write(q / "compensation_grid_downgrades.json", json.dumps({
                "schema_version": "1.5.2",
                "downgrades": [{
                    "cell_id": "REQ-010/cell-Y-MMIO",
                    "authority_ref": "docs/spec.md:1",
                    "site_citation": "src/y.py:1",
                    "reason_class": "made-up-reason",
                    "falsifiable_claim": "placeholder claim",
                }],
            }))
            failures = quality_gate.validate_cardinality_gate(repo)
            self.assertTrue(
                any("reason_class" in f and "made-up-reason" in f for f in failures),
                "Expected reason_class enum diagnostic; got: {!r}".format(failures),
            )
            self.assertTrue(
                any("uncovered" in f and "REQ-010/cell-Y-MMIO" in f for f in failures),
                "Expected 'uncovered cells' failure naming REQ-010/cell-Y-MMIO; got: {!r}".format(failures),
            )
    # -----------------------------------------------------------------------

    # ---- present:true evidence requirement (Round 5 Finding B2) ----
    def _grid_with_cell(self, cell_spec):
        """Build a compensation_grid.json around one cell spec dict."""
        return {
            "schema_version": "1.5.2",
            "reqs": {
                "REQ-010": {
                    "pattern": "whitelist",
                    "items": ["X"], "sites": ["MMIO"],
                    "cells": [cell_spec],
                },
            },
        }

    def test_present_true_cell_without_evidence_fails(self):
        """Bypass case: {present: true} with no evidence field passes the
        pre-fix gate silently. Post-fix, it must emit the evidence failure."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            q = repo / "quality"
            cell = {"cell_id": "REQ-010/cell-X-MMIO", "item": "X", "site": "MMIO", "present": True}
            _write(q / "compensation_grid.json", json.dumps(self._grid_with_cell(cell)))
            _write(q / "REQUIREMENTS.md", _requirements_md("REQ-010"))
            _write(q / "BUGS.md", "")
            failures = quality_gate.validate_cardinality_gate(repo)
            self.assertTrue(
                any(
                    "REQ-010/cell-X-MMIO" in f and "present:true" in f and "evidence" in f
                    for f in failures
                ),
                "Expected 'present:true requires ... evidence ...' diagnostic naming the cell; got: {!r}".format(failures),
            )

    def test_present_true_cell_with_malformed_evidence_fails(self):
        """Bypass case: evidence is a non-empty string but not file:line form.
        Gate must reject it and name the regex expectation."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            q = repo / "quality"
            cell = {
                "cell_id": "REQ-010/cell-X-MMIO",
                "item": "X", "site": "MMIO", "present": True,
                "evidence": "foo",
            }
            _write(q / "compensation_grid.json", json.dumps(self._grid_with_cell(cell)))
            _write(q / "REQUIREMENTS.md", _requirements_md("REQ-010"))
            _write(q / "BUGS.md", "")
            failures = quality_gate.validate_cardinality_gate(repo)
            self.assertTrue(
                any(
                    "REQ-010/cell-X-MMIO" in f and "file:line" in f and "'foo'" in f
                    for f in failures
                ),
                "Expected 'evidence must be file:line' diagnostic quoting 'foo'; got: {!r}".format(failures),
            )

    def test_present_true_cell_with_valid_evidence_passes(self):
        """Positive case: evidence matches the file:line regex (both single-
        line and line-range forms)."""
        for evidence in ("drivers/virtio/virtio_ring.c:1234", "drivers/virtio/virtio_ring.c:1200-1250"):
            with tempfile.TemporaryDirectory() as d:
                repo = Path(d)
                q = repo / "quality"
                cell = {
                    "cell_id": "REQ-010/cell-X-MMIO",
                    "item": "X", "site": "MMIO", "present": True,
                    "evidence": evidence,
                }
                _write(q / "compensation_grid.json", json.dumps(self._grid_with_cell(cell)))
                _write(q / "REQUIREMENTS.md", _requirements_md("REQ-010"))
                _write(q / "BUGS.md", "")
                failures = quality_gate.validate_cardinality_gate(repo)
                self.assertEqual(
                    failures, [],
                    "Expected clean pass for evidence={!r}; got: {!r}".format(evidence, failures),
                )
    # ----------------------------------------------------------------

    # ---- _EVIDENCE_RE contract (Round 6 Finding 1, C13.8/Fix 1) ----
    def _evidence_fixture(self, evidence_value):
        """Return (repo_path_factory, cell_dict) for the helper to write into."""
        return {
            "cell_id": "REQ-010/cell-X-MMIO",
            "item": "X", "site": "MMIO", "present": True,
            "evidence": evidence_value,
        }

    def _run_gate_with_evidence(self, evidence_value):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            q = repo / "quality"
            cell = self._evidence_fixture(evidence_value)
            _write(q / "compensation_grid.json", json.dumps(self._grid_with_cell(cell)))
            _write(q / "REQUIREMENTS.md", _requirements_md("REQ-010"))
            _write(q / "BUGS.md", "")
            return quality_gate.validate_cardinality_gate(repo)

    def test_evidence_rejects_absolute_unix_path(self):
        """/etc/passwd:10 violates the comment's 'No absolute paths' contract."""
        failures = self._run_gate_with_evidence("/etc/passwd:10")
        self.assertTrue(
            any("file:line" in f and "/etc/passwd:10" in f for f in failures),
            "Expected file:line diagnostic for absolute path; got: {!r}".format(failures),
        )

    def test_evidence_rejects_root_only_path(self):
        """/:1 has no path segment — root + line is not a real citation."""
        failures = self._run_gate_with_evidence("/:1")
        self.assertTrue(
            any("file:line" in f and "/:1" in f for f in failures),
            "Expected file:line diagnostic for root-only path; got: {!r}".format(failures),
        )

    def test_evidence_rejects_multi_slash_path(self):
        """///x:1 leads with the absolute-path rejection regardless of subsequent
        segments."""
        failures = self._run_gate_with_evidence("///x:1")
        self.assertTrue(
            any("file:line" in f and "///x:1" in f for f in failures),
            "Expected file:line diagnostic for multi-slash path; got: {!r}".format(failures),
        )

    def test_evidence_rejects_line_zero(self):
        """Line 0 is not a valid 1-indexed citation."""
        failures = self._run_gate_with_evidence("src/file.c:0")
        self.assertTrue(
            any("file:line" in f and "src/file.c:0" in f for f in failures),
            "Expected file:line diagnostic for line zero; got: {!r}".format(failures),
        )

    def test_evidence_rejects_zero_range_end(self):
        """A range whose end-line is 0 is structurally invalid."""
        failures = self._run_gate_with_evidence("src/file.c:10-0")
        self.assertTrue(
            any("file:line" in f and "src/file.c:10-0" in f for f in failures),
            "Expected file:line diagnostic for zero range endpoint; got: {!r}".format(failures),
        )

    def test_evidence_accepts_relative_with_subdir(self):
        """Positive control: a real relative file:line still passes."""
        failures = self._run_gate_with_evidence("drivers/virtio/virtio.c:123")
        self.assertEqual(
            failures, [],
            "Tightened regex must still accept legitimate relative file:line; got: {!r}".format(failures),
        )

    def test_evidence_accepts_range(self):
        """Positive control: a relative file:line-line range still passes."""
        failures = self._run_gate_with_evidence("drivers/virtio/virtio.c:120-140")
        self.assertEqual(
            failures, [],
            "Tightened regex must still accept legitimate file:line-line ranges; got: {!r}".format(failures),
        )
    # ----------------------------------------------------------------

    # ---- Strict bool 'present' (Round 6 Finding 2, C13.8/Fix 2) ----
    def _run_gate_with_present(self, present_value, include_evidence=False):
        """Build a one-cell grid with the specified 'present' value and run
        the gate. include_evidence=True attaches a valid evidence string so
        bool=True positive controls don't trip Fix 1's evidence requirement."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            q = repo / "quality"
            cell = {"cell_id": "REQ-010/cell-X-MMIO", "item": "X", "site": "MMIO"}
            # Special sentinel: omit the key entirely.
            if present_value is not _MISSING:
                cell["present"] = present_value
            if include_evidence:
                cell["evidence"] = "src/file.c:10"
            _write(q / "compensation_grid.json", json.dumps(self._grid_with_cell(cell)))
            _write(q / "REQUIREMENTS.md", _requirements_md("REQ-010"))
            _write(q / "BUGS.md", "")
            return quality_gate.validate_cardinality_gate(repo)

    def test_present_string_true_fails_with_diagnostic(self):
        """'present': 'true' (string) — bool-only contract violation. Must
        emit the new diagnostic and not slip through evidence/absent checks."""
        failures = self._run_gate_with_present("true")
        self.assertTrue(
            any("'present' must be boolean" in f and "'true'" in f for f in failures),
            "Expected 'present must be boolean' diagnostic naming 'true'; got: {!r}".format(failures),
        )
        # The cell must NOT have leaked into the evidence-check path (no
        # evidence diagnostic) or into absent_cells (no uncovered failure).
        self.assertFalse(
            any("evidence" in f and "REQ-010/cell-X-MMIO" in f for f in failures),
            "String 'true' must not trigger evidence check; got: {!r}".format(failures),
        )
        self.assertFalse(
            any("uncovered" in f for f in failures),
            "String 'true' must not be counted as absent; got: {!r}".format(failures),
        )

    def test_present_int_one_fails_with_diagnostic(self):
        """'present': 1 (int) — bool-only contract violation."""
        failures = self._run_gate_with_present(1)
        self.assertTrue(
            any("'present' must be boolean" in f for f in failures),
            "Expected 'present must be boolean' diagnostic for int 1; got: {!r}".format(failures),
        )

    def test_present_null_fails_with_diagnostic(self):
        """'present': None — non-bool, must be rejected explicitly."""
        failures = self._run_gate_with_present(None)
        self.assertTrue(
            any("'present' must be boolean" in f and "None" in f for f in failures),
            "Expected 'present must be boolean' diagnostic for None; got: {!r}".format(failures),
        )

    def test_present_missing_fails_with_diagnostic(self):
        """No 'present' key at all — same rejection path."""
        failures = self._run_gate_with_present(_MISSING)
        self.assertTrue(
            any("'present' must be boolean" in f for f in failures),
            "Expected 'present must be boolean' diagnostic for missing key; got: {!r}".format(failures),
        )

    def test_present_strict_true_still_requires_evidence(self):
        """Positive control: bool True with NO evidence still triggers Fix 1's
        evidence requirement — proves Fix 2 didn't break Fix 1's path."""
        failures = self._run_gate_with_present(True, include_evidence=False)
        self.assertTrue(
            any("present:true requires non-empty 'evidence'" in f for f in failures),
            "Expected B2's 'requires non-empty evidence' diagnostic for True with no evidence; got: {!r}".format(failures),
        )
        # Must NOT also raise the new bool-check diagnostic.
        self.assertFalse(
            any("'present' must be boolean" in f for f in failures),
            "True is a valid bool — must not trigger bool-check diagnostic; got: {!r}".format(failures),
        )

    def test_present_strict_false_still_counts_as_absent(self):
        """Positive control: bool False is still gathered into absent_cells
        and surfaces as uncovered when no Covers/downgrade exists."""
        failures = self._run_gate_with_present(False, include_evidence=False)
        self.assertTrue(
            any("uncovered" in f and "REQ-010/cell-X-MMIO" in f for f in failures),
            "False must still produce uncovered-cells failure; got: {!r}".format(failures),
        )
        self.assertFalse(
            any("'present' must be boolean" in f for f in failures),
            "False is a valid bool — must not trigger bool-check diagnostic; got: {!r}".format(failures),
        )
    # ----------------------------------------------------------------

    # ---- Per-site UCs imply Pattern (Round 5 Finding C, Fix 2) ----
    def _req_block(self, req_id, uc_refs, pattern=None):
        """Build a REQ block with UC references listed, optional Pattern."""
        lines = [
            "### {}: test requirement".format(req_id),
            "- Summary: test",
            "- Use cases: {}".format(", ".join(uc_refs)),
        ]
        if pattern is not None:
            lines.append("- Pattern: {}".format(pattern))
        return "\n".join(lines) + "\n"

    def test_per_site_ucs_without_pattern_fails(self):
        """REQ-001 cites UC-1.a and UC-1.b but has no Pattern field. The gate
        must emit a failure naming REQ-001 and both UC ids, and the message
        must cross-reference Phase 1 confirmation checklist item 6."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            q = repo / "quality"
            reqs_md = (
                "# Requirements\n\n"
                + self._req_block("REQ-001", ["UC-1.a", "UC-1.b"], pattern=None)
            )
            _write(q / "REQUIREMENTS.md", reqs_md)
            # Grid file absent is legitimate (no pattern-tagged REQs to check
            # against), but per-site UC cross-check runs anyway.
            failures = quality_gate.validate_cardinality_gate(repo)
            matching = [
                f for f in failures
                if "REQ-001" in f and "per-site UCs" in f and "Pattern field" in f
            ]
            self.assertEqual(
                len(matching), 1,
                "Expected exactly one per-site-UC/missing-Pattern failure for REQ-001; got: {!r}".format(failures),
            )
            self.assertIn("UC-1.a", matching[0])
            self.assertIn("UC-1.b", matching[0])
            self.assertIn("phase1_prompt", matching[0])

    def test_per_site_ucs_with_pattern_passes_the_cross_check(self):
        """Same fixture plus Pattern: whitelist on REQ-001, plus a valid grid
        entry. The per-site-UC/missing-Pattern failure must not fire."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            q = repo / "quality"
            reqs_md = (
                "# Requirements\n\n"
                + self._req_block("REQ-001", ["UC-1.a", "UC-1.b"], pattern="whitelist")
            )
            _write(q / "REQUIREMENTS.md", reqs_md)
            grid = {
                "schema_version": "1.5.2",
                "reqs": {
                    "REQ-001": {
                        "pattern": "whitelist",
                        "items": ["A"], "sites": ["S"],
                        "cells": [{"cell_id": "REQ-001/cell-A-S", "item": "A", "site": "S", "present": True, "evidence": "src/a.py:10"}],
                    },
                },
            }
            _write(q / "compensation_grid.json", json.dumps(grid))
            _write(q / "BUGS.md", "")
            failures = quality_gate.validate_cardinality_gate(repo)
            offending = [
                f for f in failures
                if "per-site UCs" in f and "missing the Pattern field" in f
            ]
            self.assertEqual(
                offending, [],
                "Per-site-UC/missing-Pattern check must not fire when Pattern is present; got: {!r}".format(offending),
            )

    def test_single_umbrella_uc_without_pattern_is_unaffected(self):
        """REQ-002 cites UC-2 (no .a suffix) and has no Pattern field. The
        per-site-UC/missing-Pattern check must NOT fire — single-UC REQs are
        legitimately Pattern-optional."""
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            q = repo / "quality"
            reqs_md = (
                "# Requirements\n\n"
                + self._req_block("REQ-002", ["UC-2"], pattern=None)
            )
            _write(q / "REQUIREMENTS.md", reqs_md)
            failures = quality_gate.validate_cardinality_gate(repo)
            offending = [
                f for f in failures
                if "REQ-002" in f and "per-site UCs" in f
            ]
            self.assertEqual(
                offending, [],
                "Single-UC REQ must not trigger per-site-UC check; got: {!r}".format(offending),
            )

    def test_per_site_uc_regex_does_not_mismatch_near_neighbors(self):
        """Regex sanity: _enumerate_per_site_uc_reqs must recognize UC-1.a
        but ignore UC-1 (no suffix) and UC-1.a.bad (over-suffixed)."""
        import quality_gate as qg  # re-import via the test's existing sys.path insertion
        req_text = (
            "### REQ-100: mixed references\n"
            "- Summary: test\n"
            "- Use cases: UC-100, UC-100.a, UC-100.a.bad, UC-100.bb\n"
        )
        result = qg._enumerate_per_site_uc_reqs(req_text)
        # Only UC-100.a (single lowercase letter) is a per-site UC; the others
        # must be filtered out by the regex: UC-100 (no suffix), UC-100.a.bad
        # (over-suffixed), UC-100.bb (multi-letter suffix).
        self.assertIn("REQ-100", result)
        self.assertEqual(result["REQ-100"], ["UC-100.a"])
    # --------------------------------------------------------------


if __name__ == "__main__":
    unittest.main()
