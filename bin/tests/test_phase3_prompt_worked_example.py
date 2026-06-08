"""Regression test for the Phase 3 worked-example BUGS.md format.

The phase3_prompt() worked example teaches reviewers how to write BUGS.md
entries for a pattern-tagged REQ. If the worked example drifts from the
format that quality_gate.py parses, a first-run LLM following the example
verbatim produces BUGS.md entries that _split_bug_blocks() / _parse_covers()
silently ignore, and the Phase 5 cardinality gate fails with 'uncovered cells'
despite the reviewer having written BUG entries for every cell.

This test locks the worked example to the format quality_gate.py enforces:
- ``### BUG-NNN:`` headings (matched by _BUG_HEADING_RE)
- Standalone ``- Covers: [...]`` lines (matched by _COVERS_RE)
- Standalone ``- Consolidation rationale: ...`` line on multi-cell BUGs
  (matched by _CONSOLIDATION_RE)
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

from bin.run_playbook import phase3_prompt

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


def _extract_worked_example_block(body: str) -> str:
    """Return the substring of phase3_prompt() output containing BUG-001 .. BUG-005.

    The worked example lives inside the Phase 3 prompt; we carve out the
    contiguous region from the first ``### BUG-001:`` heading through the end
    of the final ``### BUG-005:`` block (up to the next non-BUG section).
    """
    start = body.find("### BUG-001:")
    if start == -1:
        raise AssertionError(
            "phase3_prompt() no longer contains the '### BUG-001:' heading; "
            "worked-example format regressed."
        )
    # End at the next top-level section after the BUG block — conventionally
    # the downgrade-record JSON example or the 'Union check:' prose.
    end_markers = [
        "If the reviewer concluded",
        "Union check:",
        "### ITERATION mode",
    ]
    end = len(body)
    for marker in end_markers:
        idx = body.find(marker, start)
        if idx != -1 and idx < end:
            end = idx
    return body[start:end]


class Phase3WorkedExampleFormatTests(unittest.TestCase):

    def setUp(self) -> None:
        self.body = phase3_prompt()
        self.block = _extract_worked_example_block(self.body)
        self.bugs = quality_gate._split_bug_blocks(self.block)

    def test_exactly_five_bug_entries(self) -> None:
        ids = [bug_id for bug_id, _ in self.bugs]
        self.assertEqual(
            ids,
            ["BUG-001", "BUG-002", "BUG-003", "BUG-004", "BUG-005"],
            "Worked example must define BUG-001 through BUG-005 as '### BUG-NNN:' headings.",
        )

    def test_covers_lists_match_expected_cells(self) -> None:
        expected = {
            "BUG-001": ["REQ-010/cell-RING_RESET-MMIO"],
            "BUG-002": ["REQ-010/cell-RING_RESET-vDPA"],
            "BUG-003": ["REQ-010/cell-ADMIN_VQ-vDPA"],
            "BUG-004": ["REQ-010/cell-NOTIF_CONFIG_DATA-MMIO"],
            "BUG-005": [
                "REQ-010/cell-SR_IOV-MMIO",
                "REQ-010/cell-SR_IOV-vDPA",
            ],
        }
        for bug_id, block in self.bugs:
            covers = quality_gate._parse_covers(block)
            self.assertEqual(
                covers,
                expected[bug_id],
                "{} Covers list does not match the worked-example cell IDs".format(bug_id),
            )

    def test_consolidation_rationale_only_on_bug_005(self) -> None:
        for bug_id, block in self.bugs:
            rationale = quality_gate._parse_consolidation_rationale(block)
            if bug_id == "BUG-005":
                self.assertIsNotNone(
                    rationale,
                    "BUG-005 covers two cells; Consolidation rationale must be present.",
                )
                self.assertTrue(rationale and rationale.strip())
            else:
                self.assertIsNone(
                    rationale,
                    "{} covers a single cell; Consolidation rationale must be absent.".format(bug_id),
                )

    def test_every_covered_cell_id_matches_cell_id_regex(self) -> None:
        for bug_id, block in self.bugs:
            for cell_id in quality_gate._parse_covers(block):
                self.assertRegex(
                    cell_id,
                    quality_gate._CELL_ID_RE,
                    "{} cell ID {!r} does not match _CELL_ID_RE".format(bug_id, cell_id),
                )


if __name__ == "__main__":
    unittest.main()
