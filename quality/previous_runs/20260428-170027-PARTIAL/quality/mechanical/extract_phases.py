#!/usr/bin/env python3
"""Extract the phase-id set from bin/run_playbook.py:161 and cross-check.

The set is an in-function literal, not a module-level constant. Scan AST for
`Set` nodes with exactly six one-character string constants.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

QPB_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE = QPB_ROOT / "bin" / "run_playbook.py"

# CONTRACTS.md C-5 lists six phase IDs: 1..6. (Phase 7 exists as a human-facing
# presentation phase but is not in the phase-dispatch set.)
EXPECTED_CURRENT = {"1", "2", "3", "4", "5", "6"}


def extract() -> set[str]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Set):
            values = {
                elt.value for elt in node.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
            }
            if values and values.issubset({"0", "1", "2", "3", "4", "5", "6", "7"}):
                return values
    raise SystemExit("phase-id set literal not found in source")


def main() -> int:
    actual = extract()
    print(f"Phase IDs (source, run_playbook.py): {sorted(actual)}")
    print(f"Expected (Phase 2 CURRENT claim): {sorted(EXPECTED_CURRENT)}")
    if actual == EXPECTED_CURRENT:
        print("MATCH: phase-id set matches Phase 2 CURRENT documentation claim.")
        return 0
    print("DIVERGENCE: phase-id set does not match Phase 2 CURRENT claim.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
