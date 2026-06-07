"""v1.5.7 192 — trim-regression-prevention source-pins.

For each kind-B substance restoration the 192 work made to
SKILL.md, a source-pin test asserting the restored substance is
present. This prevents a future trim pass from re-removing the
same substance.

Same shape as 189's `test_no_unguarded_external_log_reads_remain`
and 190's `test_every_text_true_subprocess_run_has_explicit_utf8`
— the structural invariant codified as a maintained test.

192 triage classified exactly ONE failure as kind-B:

  Row #13 — `test_skill_md_self_encoding.SkillMdSelfEncodingTests::
            test_skill_md_names_role_map_artifact`
  Trim commit `a58f51e` removed the entire "### v1.5.4 mechanics"
  section that defined `target_role_breakdown`. That field is the
  load-bearing JSON payload of `exploration_role_map.json` / INDEX.md
  role-counts. The trim accidentally dropped the only place SKILL.md
  named it. 192 restored the substance as cleaner prose in the
  artifact-contract section.
"""
from __future__ import annotations

import pathlib
import unittest

_REPO = pathlib.Path(__file__).resolve().parents[2]
_SKILL = _REPO / "SKILL.md"


class TrimRegressionPreventionTest(unittest.TestCase):
    """Source-pin substance restored by 192 kind-B fixes."""

    def setUp(self) -> None:
        self.skill_md = _SKILL.read_text(encoding="utf-8")

    def test_target_role_breakdown_named_in_skill_md(
            self) -> None:
        """Kind-B restoration (row #13). The
        `target_role_breakdown` JSON field name MUST appear in
        SKILL.md prose — it's the JSON-payload key that downstream
        artifacts (exploration_role_map.json, INDEX.md role-counts)
        rely on, and a future trim must NOT remove it again."""
        self.assertIn(
            "target_role_breakdown", self.skill_md,
            "192 kind-B regression: SKILL.md no longer names "
            "the `target_role_breakdown` JSON field that "
            "exploration_role_map.json / INDEX.md role-counts "
            "rely on. Trim commit a58f51e removed it once; "
            "192 restored it; a re-trim removed it again.")

    def test_exploration_role_map_artifact_named(
            self) -> None:
        """Companion to the row-#13 kind-B pin: the
        `exploration_role_map.json` artifact name MUST also be
        present (it's the file that CARRIES the
        target_role_breakdown payload). Both names form the
        artifact-contract pair the running skill emits."""
        self.assertIn(
            "exploration_role_map.json", self.skill_md,
            "SKILL.md must name `exploration_role_map.json` — "
            "the run artifact carrying the role-counts payload "
            "downstream phases consume.")

    def test_schema_version_field_present_with_role_map(
            self) -> None:
        """The schema_version wrapper invariant is named in
        SKILL.md prose. The row-#13 test
        `test_skill_md_names_role_map_artifact` pins all three
        of (exploration_role_map.json, schema_version,
        target_role_breakdown) together — this regression test
        captures the third leg of that contract."""
        self.assertIn(
            "schema_version", self.skill_md,
            "SKILL.md must mention `schema_version` — the "
            "manifest-wrapper invariant the gate enforces.")


if __name__ == "__main__":
    unittest.main()
