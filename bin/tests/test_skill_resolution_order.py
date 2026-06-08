"""Tests for canonical skill-resolution-order consistency across surfaces.

Regression coverage for BUG-004 (v1.5.4 self-audit): the Claude agent
file listed `.github/skills/quality-playbook/SKILL.md` BEFORE
`.github/skills/SKILL.md`, while the canonical order in
`bin/run_playbook.py:SKILL_FALLBACK_GUIDE` puts the flat layout first.
A user with both layouts installed could have resolved the wrong skill
version.

The canonical order is:
    1. SKILL.md
    2. .claude/skills/quality-playbook/SKILL.md
    3. .github/skills/SKILL.md
    4. .github/skills/quality-playbook/SKILL.md

Three sites must agree:
    - bin/run_playbook.py SKILL_FALLBACK_GUIDE constant
    - agents/quality-playbook.agent.md install-locations list
    - agents/quality-playbook-claude.agent.md install-locations list
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent

CANONICAL_ORDER = [
    "SKILL.md",
    ".claude/skills/quality-playbook/SKILL.md",
    ".github/skills/SKILL.md",
    # v1.5.6 BUG-008: .cursor and .continue were supported by the
    # installer's KNOWN_ENVIRONMENTS but missing from every runtime
    # fallback list. Adopters using those AI tools installed
    # successfully but the runtime never resolved the installed skill.
    ".cursor/skills/quality-playbook/SKILL.md",
    ".continue/skills/quality-playbook/SKILL.md",
    ".github/skills/quality-playbook/SKILL.md",
    # v1.5.7 instruction 046 (A-3): 6 → 10 layouts. codex / windsurf /
    # cline / aider. Order matches SKILL_FALLBACK_GUIDE +
    # _GATE_INSTALL_LOCATIONS + benchmark_lib.SKILL_INSTALL_LOCATIONS.
    ".codex/skills/quality-playbook/SKILL.md",
    ".windsurf/skills/quality-playbook/SKILL.md",
    ".cline/skills/quality-playbook/SKILL.md",
    ".aider/skills/quality-playbook/SKILL.md",
]


class SkillResolutionOrderTests(unittest.TestCase):
    """All surfaces that document skill-resolution order must list the
    ten canonical locations in the canonical order (BUG-004 v1.5.5
    + BUG-008 v1.5.6)."""

    def test_run_playbook_skill_fallback_guide_lists_canonical_order(self) -> None:
        """bin/run_playbook.py:SKILL_FALLBACK_GUIDE is the source of
        truth — every documented location appears in canonical order."""
        from bin import run_playbook

        guide = run_playbook.SKILL_FALLBACK_GUIDE
        positions = [(loc, guide.find(loc)) for loc in CANONICAL_ORDER]
        for loc, pos in positions:
            self.assertGreaterEqual(
                pos, 0, f"{loc!r} not present in SKILL_FALLBACK_GUIDE"
            )
        ordered = sorted(positions, key=lambda lp: lp[1])
        self.assertEqual(
            [lp[0] for lp in ordered],
            CANONICAL_ORDER,
            "SKILL_FALLBACK_GUIDE locations are not in canonical order",
        )

    def test_claude_agent_install_locations_match_canonical(self) -> None:
        """agents/quality-playbook-claude.agent.md must list the four
        locations as numbered items in canonical order. Regression for
        BUG-004 (positions 3 and 4 were swapped in v1.5.4)."""
        order = self._read_numbered_skill_list(
            REPO_ROOT / "skills" / "quality-playbook" / "agents" / "quality-playbook-claude.agent.md"
        )
        self.assertEqual(
            order,
            CANONICAL_ORDER,
            "agents/quality-playbook-claude.agent.md install-location order "
            "diverges from bin/run_playbook.py SKILL_FALLBACK_GUIDE — see "
            "BUG-004.",
        )

    def test_general_agent_install_locations_match_canonical(self) -> None:
        """agents/quality-playbook.agent.md was already correct in v1.5.4
        but is checked here so any future drift in EITHER agent file is
        caught immediately."""
        order = self._read_numbered_skill_list(
            REPO_ROOT / "skills" / "quality-playbook" / "agents" / "quality-playbook.agent.md"
        )
        self.assertEqual(
            order,
            CANONICAL_ORDER,
            "agents/quality-playbook.agent.md install-location order "
            "diverges from canonical.",
        )

    def _read_numbered_skill_list(self, path: Path) -> list[str]:
        """Parse the first contiguous numbered list of SKILL.md install
        paths from a markdown file. Tolerant of trailing parenthetical
        annotations like '(Copilot, flat layout)'. v1.5.6 widened the
        regex from [1-4] to [1-9] for the .cursor/.continue additions;
        v1.5.7 instruction 046 widened it again to \\d{1,2} because
        CANONICAL_ORDER is now 10 items (item 10 is two digits — a
        single-digit class would mis-parse '10.' as '1')."""
        text = path.read_text(encoding="utf-8")
        pattern = re.compile(
            r"^\s*(\d{1,2})\.\s+`([^`]*SKILL\.md)`",
            re.MULTILINE,
        )
        matches = pattern.findall(text)
        # Take the first contiguous 1-2-3-...-N sequence.
        result: list[str] = []
        expected_num = 1
        for num_str, loc in matches:
            num = int(num_str)
            if num == expected_num:
                result.append(loc)
                expected_num += 1
                if expected_num > len(CANONICAL_ORDER):
                    break
            elif num == 1:
                # Restart sequence
                result = [loc]
                expected_num = 2
        return result


class BenchmarkLibFallbackOrderTests(unittest.TestCase):
    """v1.5.6 BUG-002 + BUG-003: bin/benchmark_lib.SKILL_INSTALL_LOCATIONS
    must contain the same ten entries as CANONICAL_ORDER in the same
    order. Pre-fix the helper started with .github/skills/SKILL.md
    while the runtime started with SKILL.md (root) — helper code
    could pick a different installed copy than the runtime. The
    existing fallback-order test surface only covered the runtime
    fallback per BUG-003; this class extends coverage to the helper."""

    def test_skill_install_locations_match_canonical(self) -> None:
        from bin import benchmark_lib

        actual = [str(p).replace("\\", "/") for p in benchmark_lib.SKILL_INSTALL_LOCATIONS]
        self.assertEqual(
            actual,
            CANONICAL_ORDER,
            "bin/benchmark_lib.SKILL_INSTALL_LOCATIONS diverges from "
            "CANONICAL_ORDER. The helper and runtime resolution surfaces "
            "must agree on order so a multi-install repo doesn't get "
            "different copies from each surface (BUG-002).",
        )


class GateInstallLocationsResolutionTests(unittest.TestCase):
    """v1.5.6 BUG-013: bin/run_playbook._GATE_INSTALL_LOCATIONS must
    include .cursor/skills/quality-playbook/quality_gate.py and
    .continue/skills/quality-playbook/quality_gate.py so the
    finalizer's gate-script resolver finds the gate when those AI
    tools are the install target. Pre-fix it returned None for valid
    Cursor/Continue installs."""

    EXPECTED_GATE_LOCATIONS = [
        "quality_gate.py",
        ".claude/skills/quality-playbook/quality_gate.py",
        ".github/skills/quality_gate.py",
        ".cursor/skills/quality-playbook/quality_gate.py",
        ".continue/skills/quality-playbook/quality_gate.py",
        ".github/skills/quality-playbook/quality_gate.py",
        # v1.5.7 instruction 046 (A-3): 6 → 10 layouts.
        ".codex/skills/quality-playbook/quality_gate.py",
        ".windsurf/skills/quality-playbook/quality_gate.py",
        ".cline/skills/quality-playbook/quality_gate.py",
        ".aider/skills/quality-playbook/quality_gate.py",
    ]

    def test_gate_install_locations_match_skill_canonical_order(self) -> None:
        """Each gate path mirrors a SKILL.md fallback path so the two
        constants stay aligned. A future SKILL.md addition that
        forgets the matching gate path is caught here."""
        from bin import run_playbook

        actual = list(run_playbook._GATE_INSTALL_LOCATIONS)
        self.assertEqual(actual, self.EXPECTED_GATE_LOCATIONS)
        # And every gate path corresponds to a SKILL.md path in
        # CANONICAL_ORDER (modulo the trailing filename).
        derived = [
            p.replace("/quality_gate.py", "/SKILL.md") if p.startswith(".") else "SKILL.md"
            for p in actual
        ]
        # Special-case the flat-Copilot quality_gate.py entry (it lives
        # at .github/skills/quality_gate.py — sibling to .github/skills/SKILL.md).
        derived = [
            p.replace("/skills/SKILL.md", "/skills/SKILL.md") for p in derived
        ]
        self.assertEqual(
            derived, CANONICAL_ORDER,
            "_GATE_INSTALL_LOCATIONS does not parallel CANONICAL_ORDER; "
            "a SKILL.md path was added without a matching quality_gate.py "
            "path (or vice versa).",
        )

    def test_finalizer_resolves_cursor_gate(self) -> None:
        """End-to-end: stage a temp repo with ONLY a .cursor install,
        and confirm _resolve_gate_script finds it (BUG-013 reproducer)."""
        import tempfile
        from bin import run_playbook

        with tempfile.TemporaryDirectory() as tmp_str:
            repo = Path(tmp_str)
            gate = repo / ".cursor" / "skills" / "quality-playbook" / "quality_gate.py"
            gate.parent.mkdir(parents=True)
            gate.write_text("# stub\n", encoding="utf-8")
            resolved = run_playbook._resolve_gate_script(repo)
            self.assertIsNotNone(
                resolved,
                "BUG-013 regression: finalizer cannot resolve "
                "quality_gate.py from a Cursor-only install.",
            )
            self.assertEqual(resolved, gate)

    def test_finalizer_resolves_continue_gate(self) -> None:
        """Same guarantee for .continue/skills/quality-playbook/."""
        import tempfile
        from bin import run_playbook

        with tempfile.TemporaryDirectory() as tmp_str:
            repo = Path(tmp_str)
            gate = repo / ".continue" / "skills" / "quality-playbook" / "quality_gate.py"
            gate.parent.mkdir(parents=True)
            gate.write_text("# stub\n", encoding="utf-8")
            resolved = run_playbook._resolve_gate_script(repo)
            self.assertIsNotNone(
                resolved,
                "BUG-013 regression: finalizer cannot resolve "
                "quality_gate.py from a Continue-only install.",
            )
            self.assertEqual(resolved, gate)


class CrossSurfaceDriftDetectionTests(unittest.TestCase):
    """One assertion that pins ALL fallback surfaces to CANONICAL_ORDER
    in the same order. A future drift in any surface — agent files,
    benchmark_lib, runtime fallback prose, gate locations — fails
    here with a single clear diff."""

    def test_all_fallback_surfaces_share_canonical_order(self) -> None:
        from bin import benchmark_lib, run_playbook

        # Surface 1: benchmark_lib.SKILL_INSTALL_LOCATIONS
        bench = [str(p).replace("\\", "/") for p in benchmark_lib.SKILL_INSTALL_LOCATIONS]

        # Surface 2: run_playbook.SKILL_FALLBACK_GUIDE prose order
        guide = run_playbook.SKILL_FALLBACK_GUIDE
        guide_positions = sorted(
            ((loc, guide.find(loc)) for loc in CANONICAL_ORDER),
            key=lambda lp: lp[1],
        )
        guide_order = [lp[0] for lp in guide_positions]

        # Surface 3: agent files (parsed via the existing helper).
        helper = SkillResolutionOrderTests()
        claude_agent = helper._read_numbered_skill_list(
            REPO_ROOT / "skills" / "quality-playbook" / "agents" / "quality-playbook-claude.agent.md"
        )
        general_agent = helper._read_numbered_skill_list(
            REPO_ROOT / "skills" / "quality-playbook" / "agents" / "quality-playbook.agent.md"
        )

        for name, surface in (
            ("CANONICAL_ORDER (test reference)", CANONICAL_ORDER),
            ("benchmark_lib.SKILL_INSTALL_LOCATIONS", bench),
            ("run_playbook.SKILL_FALLBACK_GUIDE prose", guide_order),
            ("agents/quality-playbook-claude.agent.md", claude_agent),
            ("agents/quality-playbook.agent.md", general_agent),
        ):
            self.assertEqual(
                surface, CANONICAL_ORDER,
                f"{name} diverges from CANONICAL_ORDER. All fallback "
                f"surfaces MUST contain the same six entries in the "
                f"same order.",
            )


if __name__ == "__main__":
    unittest.main()
