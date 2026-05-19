#!/usr/bin/env python3
"""Extract ALL_STRATEGIES from bin/run_playbook.py and cross-check."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

QPB_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE = QPB_ROOT / "bin" / "run_playbook.py"

# CONTRACTS.md C-4 lists these four strategies in this order.
EXPECTED_CURRENT = ["gap", "unfiltered", "parity", "adversarial"]


def extract() -> list[str]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "ALL_STRATEGIES" in targets and isinstance(node.value, ast.List):
                return [
                    elt.value for elt in node.value.elts
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                ]
    raise SystemExit("ALL_STRATEGIES not found in source")


def main() -> int:
    actual = extract()
    print(f"ALL_STRATEGIES (source): {len(actual)} entries")
    for p in actual:
        print(f"  - {p}")
    print(f"Expected (Phase 2 CURRENT claim): {len(EXPECTED_CURRENT)} entries")
    for p in EXPECTED_CURRENT:
        print(f"  - {p}")
    if actual == EXPECTED_CURRENT:
        print("MATCH: source list matches Phase 2 CURRENT documentation claim.")
        return 0
    print("DIVERGENCE: source list does not match Phase 2 CURRENT claim.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
