#!/usr/bin/env python3
"""Extract PROTECTED_PREFIXES from bin/benchmark_lib.py and cross-check."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

QPB_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE = QPB_ROOT / "bin" / "benchmark_lib.py"

# CONTRACTS.md C-3 enumerates these four prefixes as CURRENT. REQ-006 desires a
# fifth (AGENTS.md protection); that is not yet in source.
EXPECTED_CURRENT = [
    "quality/",
    "control_prompts/",
    "previous_runs/",
    "docs_gathered/",
]


def extract() -> list[str]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "PROTECTED_PREFIXES" in targets and isinstance(node.value, ast.Tuple):
                return [
                    elt.value for elt in node.value.elts
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                ]
    raise SystemExit("PROTECTED_PREFIXES not found in source")


def main() -> int:
    actual = extract()
    print(f"PROTECTED_PREFIXES (source): {len(actual)} entries")
    for p in actual:
        print(f"  - {p}")
    print(f"Expected (Phase 2 CURRENT claim): {len(EXPECTED_CURRENT)} entries")
    for p in EXPECTED_CURRENT:
        print(f"  - {p}")
    if actual == EXPECTED_CURRENT:
        print("MATCH: source tuple matches Phase 2 CURRENT documentation claim.")
        return 0
    print("DIVERGENCE: source tuple does not match Phase 2 CURRENT claim.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
