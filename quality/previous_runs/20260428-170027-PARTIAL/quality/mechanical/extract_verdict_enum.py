#!/usr/bin/env python3
"""Extract allowed_verdicts from quality_gate.py and cross-check.

This set is an in-function literal (check_tdd_sidecar). Scan AST for a Set with
string constants that match the documented verdict enum size (5 entries).
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

QPB_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE = QPB_ROOT / ".github" / "skills" / "quality_gate" / "quality_gate.py"

# CONTRACTS.md C-8 and RUN_TDD_TESTS.md §Verdict enum enumerate these 5.
EXPECTED_CURRENT = {
    "TDD verified",
    "red failed",
    "green failed",
    "confirmed open",
    "deferred",
}


def extract() -> set[str]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    best: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Set):
            values = {
                elt.value for elt in node.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
            }
            if values == EXPECTED_CURRENT:
                return values
            # Keep track of near-matches for diagnostics.
            if values and values & EXPECTED_CURRENT:
                best = values
    if best:
        return best
    raise SystemExit("verdict-enum set literal not found in source")


def main() -> int:
    actual = extract()
    print(f"allowed_verdicts (source, quality_gate.py): {sorted(actual)}")
    print(f"Expected (Phase 2 CURRENT claim): {sorted(EXPECTED_CURRENT)}")
    if actual == EXPECTED_CURRENT:
        print("MATCH: verdict enum matches Phase 2 CURRENT documentation claim.")
        return 0
    print("DIVERGENCE: verdict enum does not match Phase 2 CURRENT claim.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
