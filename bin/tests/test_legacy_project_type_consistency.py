"""Cross-check: derive_legacy_project_type duplication between
bin/role_map.py and the gate's stdlib-only inline copy at
.github/skills/quality_gate/quality_gate.py.

This test pins the duplication. The gate ships into target repos as a
self-contained stdlib-only script and CANNOT import bin/role_map; the
small amount of role-map awareness it needs is inlined inside
quality_gate.py (`_phase4_project_type` + `_role_map_has_role`). The
two implementations must agree on every input, otherwise the legacy
"project type" label drifts between the bin-side derivation (used by
pass_c's 6-row disposition table) and the gate-side derivation (used
by the four Phase 4 skill-side checks).

If you change one implementation, change both, then re-run this test.

v1.5.4 Round 1 Council finding B3/C2.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bin import role_map as rm


REPO_ROOT = Path(__file__).resolve().parents[2]
# v1.5.8 instruction 208: quality_gate.py moved to skills/quality-playbook/scripts/.
GATE_PATH = (
    REPO_ROOT / "skills" / "quality-playbook" / "scripts" / "quality_gate.py"
)


def _load_gate_module():
    """Import the gate file from its filesystem path. The gate ships as
    a stdlib-only script and is not a member of any Python package, so
    `from bin.x import y` style imports won't work."""
    spec = importlib.util.spec_from_file_location(
        "qpb_quality_gate_for_drift_test", GATE_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _entry(path: str, role: str, size: int, **extra) -> dict:
    rec = {"path": path, "role": role, "size_bytes": size, "rationale": "x"}
    rec.update(extra)
    return rec


def _make_role_map(files: list[dict]) -> dict:
    return {
        "schema_version": rm.SCHEMA_VERSION,
        "timestamp_start": "2026-04-29T00:00:00Z",
        "files": files,
        "breakdown": rm.compute_breakdown(files),
    }


class DeriveLegacyProjectTypeDriftTests(unittest.TestCase):
    """For every role-map shape, both implementations must agree."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.gate = _load_gate_module()

    def _bin_side(self, role_map: dict) -> str:
        return rm.derive_legacy_project_type(role_map)

    def _gate_side(self, role_map: dict) -> str:
        # The gate's _phase4_project_type reads from quality/ on disk;
        # write the role map to a temp quality/ first.
        with TemporaryDirectory() as tmp:
            q = Path(tmp) / "quality"
            q.mkdir()
            (q / "exploration_role_map.json").write_text(
                json.dumps(role_map), encoding="utf-8"
            )
            return self.gate._phase4_project_type(q)

    def _assert_agree(self, role_map: dict, expected: str) -> None:
        bin_label = self._bin_side(role_map)
        gate_label = self._gate_side(role_map)
        self.assertEqual(
            bin_label,
            expected,
            f"bin/role_map disagreed with expected: got {bin_label!r}, "
            f"expected {expected!r}",
        )
        self.assertEqual(
            gate_label,
            expected,
            f"quality_gate disagreed with expected: got {gate_label!r}, "
            f"expected {expected!r}",
        )
        self.assertEqual(
            bin_label,
            gate_label,
            "DRIFT: bin/role_map.derive_legacy_project_type and "
            "quality_gate._phase4_project_type returned different "
            f"labels ({bin_label!r} vs {gate_label!r}) for the same "
            "role map. Update both implementations in lockstep.",
        )

    def test_pure_skill_only_skill_prose(self) -> None:
        rmap = _make_role_map([_entry("SKILL.md", "skill-prose", 1000)])
        self._assert_agree(rmap, "Skill")

    def test_pure_skill_skill_prose_plus_skill_reference(self) -> None:
        rmap = _make_role_map([
            _entry("SKILL.md", "skill-prose", 1000),
            _entry("references/exp.md", "skill-reference", 500),
        ])
        self._assert_agree(rmap, "Skill")

    def test_pure_skill_with_skill_tools(self) -> None:
        # skill-tool alone (no code) keeps the project Skill — there's
        # no code authority for Tier 5 demotion.
        rmap = _make_role_map([
            _entry("SKILL.md", "skill-prose", 1000),
            _entry(
                "scripts/x.py", "skill-tool", 100,
                skill_prose_reference="SKILL.md:42",
            ),
        ])
        self._assert_agree(rmap, "Skill")

    def test_pure_code_no_skill_prose(self) -> None:
        rmap = _make_role_map([
            _entry("src/a.py", "code", 1000),
            _entry("src/b.py", "code", 500),
        ])
        self._assert_agree(rmap, "Code")

    def test_hybrid_50_50(self) -> None:
        rmap = _make_role_map([
            _entry("SKILL.md", "skill-prose", 500),
            _entry("src/a.py", "code", 500),
        ])
        self._assert_agree(rmap, "Hybrid")

    def test_hybrid_skill_dominant(self) -> None:
        rmap = _make_role_map([
            _entry("SKILL.md", "skill-prose", 9000),
            _entry("src/a.py", "code", 100),
        ])
        self._assert_agree(rmap, "Hybrid")

    def test_hybrid_code_dominant(self) -> None:
        rmap = _make_role_map([
            _entry("SKILL.md", "skill-prose", 100),
            _entry("src/a.py", "code", 9000),
        ])
        self._assert_agree(rmap, "Hybrid")

    def test_hybrid_with_all_three_role_families(self) -> None:
        rmap = _make_role_map([
            _entry("SKILL.md", "skill-prose", 1000),
            _entry("references/exp.md", "skill-reference", 500),
            _entry(
                "scripts/x.py", "skill-tool", 200,
                skill_prose_reference="SKILL.md:1",
            ),
            _entry("bin/main.py", "code", 5000),
            _entry("README.md", "docs", 800),
            _entry(".gitignore", "config", 50),
        ])
        self._assert_agree(rmap, "Hybrid")

    def test_only_other_roles_classifies_as_code(self) -> None:
        # No skill-prose, no code — only docs/test/config. The legacy
        # mapping treats anything without skill-prose as "Code".
        rmap = _make_role_map([
            _entry("README.md", "docs", 1000),
            _entry("test_x.py", "test", 500),
        ])
        self._assert_agree(rmap, "Code")

    def test_playbook_output_does_not_count_as_either_surface(self) -> None:
        rmap = _make_role_map([
            _entry(
                "quality/EXPLORATION.md", "playbook-output", 2000
            ),
            _entry(
                ".github/skills/quality_gate.py",
                "playbook-output",
                40000,
            ),
        ])
        # No intrinsic skill-prose AND no intrinsic code.
        self._assert_agree(rmap, "Code")

    def test_index_schema_version_current_pinned_across_bin_and_gate(
        self,
    ) -> None:
        """v1.5.4 Round 2 Council Step 5 polish: the INDEX
        schema_version constant is duplicated across the bin/gate
        boundary (the gate ships as a stdlib-only script and cannot
        import bin.role_map). Pin them equal so a v1.5.5+ schema bump
        cannot land on one side without the other."""
        self.assertEqual(
            rm.INDEX_SCHEMA_VERSION_CURRENT,
            self.gate.SCHEMA_VERSION_CURRENT,
            "DRIFT: bin.role_map.INDEX_SCHEMA_VERSION_CURRENT and "
            "quality_gate.SCHEMA_VERSION_CURRENT disagree. Both must "
            "bump in lockstep when the INDEX schema is versioned up.",
        )

    def test_drift_assertion_fires_on_synthetic_disagreement(self) -> None:
        """Negative control (Round 2 Step 5 polish): prove that the
        agreement-checking machinery actually catches drift. We
        monkey-patch the gate's _phase4_project_type to deliberately
        return a wrong label for a known input, then call
        _assert_agree and confirm it raises AssertionError. Without
        this control, the agreement tests above could be vacuously
        correct (e.g. if both implementations had the same bug)."""
        rmap = _make_role_map([_entry("SKILL.md", "skill-prose", 1000)])
        # Sanity: real implementations agree on this fixture.
        self.assertEqual(self._bin_side(rmap), "Skill")
        self.assertEqual(self._gate_side(rmap), "Skill")
        # Inject drift on the gate side and confirm _assert_agree
        # catches it.
        real_phase4 = self.gate._phase4_project_type
        self.gate._phase4_project_type = lambda q: "Hybrid"
        try:
            with self.assertRaises(AssertionError):
                self._assert_agree(rmap, "Skill")
        finally:
            self.gate._phase4_project_type = real_phase4
        # Sanity: after restoring, the real check passes again.
        self._assert_agree(rmap, "Skill")


if __name__ == "__main__":
    unittest.main()
