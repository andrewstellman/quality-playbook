#!/usr/bin/env python3
"""v1.5.10 instruction 052 (the SKILL.md trim) — reference-resolves invariant.

The trim moves per-phase detail into lazy-loaded `references/*.md` reachable
from SKILL.md via the ``See `references/X.md` `` pointer dialect. This test pins
the runtime validator `quality_gate.validate_skill_reference_resolves` added in
the same release:

  * the SHIPPED SKILL.md's pointers all resolve (no missing file, no cycle);
  * a pointer at a non-existent reference is reported (mutation bite);
  * a reference cycle is detected, not infinite-looped;
  * the `quality_gate.py --check-skill-references` CLI sub-mode exits 0 on the
    real install.

Companion to `test_skill_md_size.test_all_skill_md_pointers_resolve` (which pins
the SKILL.md->references edge); this one pins the gate-side validator + its
transitive/cycle behavior.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_SKILL_DIR = _REPO / "plugins" / "quality-playbook" / "skills" / "quality-playbook"
_GATE = _SKILL_DIR / "scripts" / "quality_gate.py"
sys.path.insert(0, str(_SKILL_DIR / "scripts"))
import quality_gate  # noqa: E402


class ShippedSkillReferencesResolve(unittest.TestCase):

    def test_real_skill_md_pointers_all_resolve(self) -> None:
        problems = quality_gate.validate_skill_reference_resolves(
            _SKILL_DIR / "SKILL.md")
        self.assertEqual(
            problems, [],
            "shipped SKILL.md has unresolved/cyclic `See references/X.md` "
            "pointers: %s" % problems)

    def test_cli_check_skill_references_exits_zero(self) -> None:
        r = subprocess.run(
            [sys.executable, str(_GATE), "--check-skill-references"],
            capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("SKILL reference integrity: PASS", r.stdout)


class ReferenceResolvesBites(unittest.TestCase):
    """Synthetic fixtures — the validator must FLAG a broken/cyclic graph."""

    def _skill(self, tmp, body):
        (tmp / "references").mkdir(exist_ok=True)
        p = tmp / "SKILL.md"
        p.write_text(body, encoding="utf-8")
        return p

    def test_missing_reference_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            sk = self._skill(tmp, "# S\n\nSee `references/nope.md` for detail.\n")
            problems = quality_gate.validate_skill_reference_resolves(sk)
            self.assertTrue(
                any("references/nope.md" in p for p in problems),
                "missing reference not reported: %s" % problems)

    def test_existing_reference_passes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "references").mkdir()
            (tmp / "references" / "ok.md").write_text("ok\n", encoding="utf-8")
            sk = self._skill(tmp, "# S\n\nSee `references/ok.md` for detail.\n")
            self.assertEqual(
                quality_gate.validate_skill_reference_resolves(sk), [])

    def test_cycle_is_detected_not_infinite(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            (tmp / "references").mkdir()
            # a -> b -> a  (cycle), reachable from SKILL.md
            (tmp / "references" / "a.md").write_text(
                "See `references/b.md`\n", encoding="utf-8")
            (tmp / "references" / "b.md").write_text(
                "See `references/a.md`\n", encoding="utf-8")
            sk = self._skill(tmp, "# S\n\nSee `references/a.md`\n")
            problems = quality_gate.validate_skill_reference_resolves(sk)
            self.assertTrue(
                any("cycle" in p.lower() for p in problems),
                "reference cycle not detected: %s" % problems)

    def test_missing_skill_md_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            problems = quality_gate.validate_skill_reference_resolves(
                Path(d) / "SKILL.md")
            self.assertTrue(any("not found" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
