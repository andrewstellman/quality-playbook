#!/usr/bin/env python3
"""Extract SKILL_INSTALL_LOCATIONS from bin/benchmark_lib.py and cross-check.

Exit 0 if the live tuple matches the Phase 2 documentation claim; exit 1 otherwise.
Phase 2 documents the CURRENT state (3 entries); REQ-002 tracks the fourth entry
as a desired change. This extractor validates the CURRENT claim only.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

QPB_ROOT = Path(__file__).resolve().parent.parent.parent
SOURCE = QPB_ROOT / "bin" / "benchmark_lib.py"

# All four documented install paths (REQ-002). After the BUG-002 fix,
# SKILL_INSTALL_LOCATIONS carries this full set.
EXPECTED_CURRENT = [
    ".github/skills/SKILL.md",
    ".claude/skills/quality-playbook/SKILL.md",
    "SKILL.md",
    ".github/skills/quality-playbook/SKILL.md",
]


def extract() -> list[str]:
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "SKILL_INSTALL_LOCATIONS" in targets and isinstance(node.value, ast.Tuple):
                return [_render_path(elt) for elt in node.value.elts]
    raise SystemExit("SKILL_INSTALL_LOCATIONS not found in source")


def _render_path(node: ast.AST) -> str:
    """Render a Path(...) / Path(...) chain as a forward-slash string."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Path":
        parts = [a.value for a in node.args if isinstance(a, ast.Constant)]
        return "/".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _render_path(node.left)
        right = _render_path(node.right)
        return f"{left}/{right}"
    raise SystemExit(f"Unrecognized AST node in SKILL_INSTALL_LOCATIONS: {ast.dump(node)}")


def main() -> int:
    actual = extract()
    print(f"SKILL_INSTALL_LOCATIONS (source): {len(actual)} entries")
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
