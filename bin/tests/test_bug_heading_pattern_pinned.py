"""v1.5.7 089d (F22) — cross-module pin: the BUG-NNN heading regex
must be a single string-equal canonical across the three surfaces
that parse `### BUG-NNN:` (and variant) headings from BUGS.md.

Pre-089d the three surfaces diverged:
  - .github/skills/quality_gate/quality_gate.py:286  `^###\\s+BUG-(\\d+):`
    (digit-only, required colon — rejected BUG-H1 / BUG-M1 / BUG-L1
    historical severity-prefixed IDs)
  - bin/archive_lib.py:69     alphanumeric form (accepted historical IDs)
  - bin/run_state_lib.py (two inline duplicates, lines 700 + 830)
    alphanumeric form (matched archive_lib)

The drift meant a `### BUG-H1: title` heading parsed by archive_lib
+ run_state_lib but was invisible to the gate, classifying the same
BUG record differently per surface (opus bootstrap F22). 089d
extracts the canonical form in `bin/run_state_lib.BUG_HEADING_PATTERN_STR`
and consolidates all three surfaces on it.

This test pins the string literals so a future maintainer can't
silently re-introduce drift. archive_lib and run_state_lib resolve
to the same compiled object (since archive_lib re-exports from
run_state_lib); quality_gate.py carries a literal STRING copy
(installed-standalone, can't import bin/) whose value must equal
the canonical string.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
# v1.5.8 instruction 208: quality_gate.py moved to the plugin-native
# skills/quality-playbook/scripts/ location.
_GATE_PY = _REPO_ROOT / "plugins" / "quality-playbook" / "skills" / "quality-playbook" / "scripts" / "quality_gate.py"


class BugHeadingPatternPinTests(unittest.TestCase):

    def test_run_state_lib_canonical_string_is_authoritative(self) -> None:
        """The canonical constant exists, is non-empty, and the
        compiled pattern matches the string."""
        from bin import run_state_lib

        self.assertTrue(
            run_state_lib.BUG_HEADING_PATTERN_STR.startswith(r"^###\s+BUG-"),
            "BUG_HEADING_PATTERN_STR must anchor at line start with "
            "`### BUG-` — the canonical heading shape.",
        )
        self.assertEqual(
            run_state_lib.BUG_HEADING_PATTERN_RE.pattern,
            run_state_lib.BUG_HEADING_PATTERN_STR,
            "BUG_HEADING_PATTERN_RE must be compile() of "
            "BUG_HEADING_PATTERN_STR (re-compile drift caught here).",
        )

    def test_archive_lib_uses_same_object(self) -> None:
        """archive_lib._BUG_HEADING_PATTERN must be the canonical
        compiled pattern, not a local re.compile()."""
        from bin import archive_lib, run_state_lib

        self.assertIs(
            archive_lib._BUG_HEADING_PATTERN,
            run_state_lib.BUG_HEADING_PATTERN_RE,
            "bin/archive_lib._BUG_HEADING_PATTERN must be the same "
            "object as bin/run_state_lib.BUG_HEADING_PATTERN_RE — "
            "if you see this fail, a local re.compile() was "
            "reintroduced; replace it with the import.",
        )

    def test_quality_gate_literal_matches_canonical(self) -> None:
        """quality_gate.py is installed STANDALONE into adopters'
        .github/skills/quality_gate/ and CANNOT import bin/
        (Option-B-additive-duplication constraint; see the
        `_INSTALL_MARKER_DIRS` precedent). Its literal copy must be
        string-equal to the canonical.

        Mutation-test evidence (ai_context/DEVELOPMENT_PROCESS.md:
        152-160), instruction-089d F22:
          Mutation: revert .github/skills/quality_gate/quality_gate.py
          _BUG_HEADING_PATTERN_STR_CANONICAL to the pre-089d
          `r"^###\\s+BUG-(\\d+):"` digit-only form.
          Expected failure: THIS test fails on the
          assertEqual(gate_literal, canonical) — the gate's string
          no longer matches the alphanumeric canonical.
          Restoration: re-set to the alphanumeric form; passes.
          Bite executed during 089d development; PASS→FAIL→PASS
          confirmed (__pycache__ purged between mutate and restore).
        """
        from bin import run_state_lib

        gate_src = _GATE_PY.read_text(encoding="utf-8")
        m = re.search(
            r"^_BUG_HEADING_PATTERN_STR_CANONICAL\s*=\s*\(\s*\n\s*r?(['\"])(.+?)\1\s*\n\s*\)",
            gate_src, re.MULTILINE | re.DOTALL,
        )
        self.assertIsNotNone(
            m,
            "quality_gate.py must define _BUG_HEADING_PATTERN_STR_CANONICAL "
            "as a raw string literal — the canonical the gate's compiled "
            "_BUG_HEADING_RE is built from. If you see this fail, the "
            "constant name or form drifted.",
        )
        gate_literal = m.group(2)
        self.assertEqual(
            gate_literal, run_state_lib.BUG_HEADING_PATTERN_STR,
            "quality_gate.py's _BUG_HEADING_PATTERN_STR_CANONICAL "
            "literal must be string-equal to "
            "bin/run_state_lib.BUG_HEADING_PATTERN_STR (the F22 "
            "cross-surface pin). If you see this fail, the gate's "
            "literal drifted from the canonical — either the literal "
            "was widened/narrowed locally OR the canonical changed "
            "without the gate's literal being updated.",
        )

    def test_canonical_matches_representative_bug_id_shapes(self) -> None:
        """The canonical regex must accept all four BUG-ID shapes
        documented in 089d F22 + the canonical's own docstring:
        BUG-001 (digit), BUG-H1/M1/L1 (severity-prefixed),
        BUG-001-fix-2 (hyphenated suffix), and the title-less form."""
        from bin import run_state_lib

        rx = run_state_lib.BUG_HEADING_PATTERN_RE
        accept = (
            "### BUG-001: title here",
            "### BUG-H1: hi-sev title",
            "### BUG-M2: med title",
            "### BUG-L3: low title",
            "### BUG-001-fix-2: hyphenated suffix",
            "### BUG-001",                 # title-less form
        )
        for line in accept:
            self.assertIsNotNone(
                rx.match(line),
                f"canonical regex should accept {line!r} but didn't",
            )


if __name__ == "__main__":
    unittest.main()
