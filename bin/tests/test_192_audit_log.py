"""v1.5.7 192 — audit-log-completeness tests.

The 192 worker enumerated each of the 13 pre-existing test
failures into `quality/audits/192_trim_failure_enumeration.md`
with a per-row kind A/B/C classification. These tests pin the
audit log's structural integrity so a future maintainer reading
the audit log can trust every row is classified.
"""
from __future__ import annotations

import pathlib
import re
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[2]
_AUDIT = (_REPO / "quality" / "audits"
          / "192_trim_failure_enumeration.md")


class AuditLogCompletenessTest(unittest.TestCase):
    """The 192 enumeration log captures every failure with a
    classification."""

    def test_enumeration_log_exists(self) -> None:
        """The audit log file must exist at the canonical path."""
        self.assertTrue(
            _AUDIT.exists(),
            f"missing 192 audit log at {_AUDIT}")

    def test_enumeration_log_has_13_rows(self) -> None:
        """Exactly 13 row entries (one per failure that 192
        triaged). Each row begins with `| N |` where N is the
        row number 1..13."""
        text = _AUDIT.read_text(encoding="utf-8")
        rows = re.findall(
            r"^\| (\d+) \| ", text, re.MULTILINE)
        # The header + separator rows also start with `| ` but
        # don't have a leading numeric index — filter to numeric.
        self.assertEqual(
            len(rows), 13,
            f"expected 13 numbered rows in audit log, "
            f"found {len(rows)}: {rows}")
        # Indices must be 1..13 contiguously.
        self.assertEqual(
            sorted(int(r) for r in rows), list(range(1, 14)),
            f"audit log row indices not 1..13: {rows}")

    def test_no_unclassified_failures(self) -> None:
        """Every row's final column carries a kind A/B/C tag
        (bolded as **A**, **B**, or **C**)."""
        text = _AUDIT.read_text(encoding="utf-8")
        # Each row is one line starting with `| N |` and ending
        # before the next newline. The last `|`-separated cell
        # holds the classification + justification — must
        # contain `**A**`, `**B**`, or `**C**`.
        row_pattern = re.compile(
            r"^\| \d+ \| .+? \| (.+?) \|\s*$", re.MULTILINE)
        rows = row_pattern.findall(text)
        self.assertGreaterEqual(
            len(rows), 13,
            f"expected ≥13 classified rows, found {len(rows)}")
        for i, last_cell in enumerate(rows[:13], 1):
            self.assertTrue(
                "**A**" in last_cell
                or "**B**" in last_cell
                or "**C**" in last_cell,
                f"row {i} missing classification tag "
                f"(**A** / **B** / **C**) in final cell: "
                f"{last_cell[:160]!r}")

    def test_audit_log_summary_section_present(self) -> None:
        """The audit log carries a `## Summary` section with
        per-kind counts so future maintainers can quickly see
        the distribution without re-counting rows."""
        text = _AUDIT.read_text(encoding="utf-8")
        self.assertIn("## Summary", text,
            "audit log missing ## Summary section")
        # Per-kind counts must appear (lowercased forms vary).
        lowered = text.lower()
        self.assertIn("kind a", lowered,
            "audit log Summary should report Kind A count")
        self.assertIn("kind b", lowered,
            "audit log Summary should report Kind B count")
        self.assertIn("kind c", lowered,
            "audit log Summary should report Kind C count")


if __name__ == "__main__":
    unittest.main()
