"""Tests for bin/role_map.py — QPB v1.5.4 Phase 1 file-role-tagging.

The role tagging itself is produced by an LLM agent during Phase 1
exploration; the unit-test surface here is the schema + breakdown
helpers that every consumer (INDEX rendering, pass_c, quality_gate)
shares. Each fixture test handcrafts the role map an LLM SHOULD
produce for a given target shape and asserts the helper functions
process it correctly. The "did the LLM tag the right files" assertion
lives in the wide-test harness, not here.

Fixtures cover the five shapes called out in the v1.5.4 Phase 1 brief:

  1. pdf-style          SKILL.md + reference docs + helper scripts
                        explicitly invoked from SKILL.md (skill-tool).
  2. pure-Markdown      single SKILL.md, no scripts.
  3. pure-code          no SKILL.md, only library/orchestrator code.
  4. QPB-style          SKILL.md + agents/* (skill-prose) + bin/*.py
                        (code, NOT skill-tool — independent contracts).
  5. pre-played         target carrying a quality/ subtree from a
                        prior playbook run; tagged playbook-output so
                        the LOC-pollution failure mode of v1.5.3
                        cannot reoccur.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bin import role_map as rm


def _make_role_map(files: list[dict], *, provenance: str = "git-ls-files") -> dict:
    """Helper: assemble a complete role map from a list of file entries
    with the breakdown computed by the production helper. This is what
    Phase 1 should ultimately emit; the helper makes the fixtures
    declarative.

    v1.5.4 Phase 3.6.1: provenance and summary are required top-level
    fields. The helper supplies sane defaults so existing tests don't
    have to set them explicitly."""
    base = {
        "schema_version": rm.SCHEMA_VERSION,
        "timestamp_start": "2026-04-28T00:00:00Z",
        "provenance": provenance,
        "files": files,
        "breakdown": rm.compute_breakdown(files),
    }
    base["summary"] = rm.summarize_role_map(base)
    return base


def _entry(path: str, role: str, size: int, **extra) -> dict:
    rec = {
        "path": path,
        "role": role,
        "size_bytes": size,
        "rationale": f"fixture entry for {path}",
    }
    rec.update(extra)
    return rec


# ---------------------------------------------------------------------------
# Fixture 1 — pdf-style: SKILL.md + reference + skill-tool scripts
# ---------------------------------------------------------------------------


class PdfStyleFixtureTests(unittest.TestCase):
    """The pdf skill ships SKILL.md + a reference doc + two scripts
    that SKILL.md explicitly tells the agent to invoke. The role map
    must distinguish skill-tool (scripts subordinate to SKILL.md prose)
    from code (independent libraries)."""

    def setUp(self) -> None:
        self.role_map = _make_role_map([
            _entry("SKILL.md", "skill-prose", 6000),
            _entry("references/forms.md", "skill-reference", 2000),
            _entry("references/extraction.md", "skill-reference", 1000),
            _entry(
                "scripts/extract_form_field_info.py",
                "skill-tool",
                500,
                skill_prose_reference="SKILL.md:47",
            ),
            _entry(
                "scripts/render_pdf.py",
                "skill-tool",
                500,
                skill_prose_reference="references/forms.md:20",
            ),
        ])

    def test_validates_clean(self) -> None:
        self.assertEqual(rm.validate_role_map(self.role_map), [])

    def test_breakdown_distinguishes_skill_tool_from_code(self) -> None:
        files_by_role = self.role_map["breakdown"]["files_by_role"]
        self.assertEqual(files_by_role.get("skill-prose"), 1)
        self.assertEqual(files_by_role.get("skill-reference"), 2)
        self.assertEqual(files_by_role.get("skill-tool"), 2)
        # No 'code' bucket should appear at all (not even with count 0).
        self.assertNotIn("code", files_by_role)

    def test_percentages_match_pdf_style_shape(self) -> None:
        pcts = self.role_map["breakdown"]["percentages"]
        # 6000 + 2000 + 1000 = 9000 skill prose; 1000 tool; 0 code; 0 other.
        # Total = 10000.
        self.assertAlmostEqual(pcts["skill_share"], 0.9, places=3)
        self.assertAlmostEqual(pcts["tool_share"], 0.1, places=3)
        self.assertAlmostEqual(pcts["code_share"], 0.0, places=3)
        self.assertAlmostEqual(pcts["other_share"], 0.0, places=3)

    def test_activation_predicates(self) -> None:
        self.assertTrue(rm.has_skill_prose(self.role_map))
        self.assertTrue(rm.has_skill_tools(self.role_map))
        self.assertFalse(rm.has_code(self.role_map))

    def test_legacy_project_type_is_skill(self) -> None:
        # No code surface; pass_c's behavioral-claim branch should
        # route to council-review (Branch 6), not Tier-5 demotion.
        self.assertEqual(rm.derive_legacy_project_type(self.role_map), "Skill")

    def test_skill_tool_carries_prose_reference(self) -> None:
        skill_tool_entries = [
            f for f in self.role_map["files"] if f["role"] == "skill-tool"
        ]
        self.assertEqual(len(skill_tool_entries), 2)
        for entry in skill_tool_entries:
            self.assertIn("skill_prose_reference", entry)
            self.assertRegex(
                entry["skill_prose_reference"], r"^[\w./-]+:\d+$"
            )


# ---------------------------------------------------------------------------
# Fixture 2 — pure-Markdown skill: single SKILL.md
# ---------------------------------------------------------------------------


class PureMarkdownSkillFixtureTests(unittest.TestCase):
    """schedule / consolidate-memory / setup-cowork from the v1.5.4
    Design Part 1 validation set. Pure prose, no scripts."""

    def setUp(self) -> None:
        self.role_map = _make_role_map([
            _entry("SKILL.md", "skill-prose", 4000),
        ])

    def test_validates_clean(self) -> None:
        self.assertEqual(rm.validate_role_map(self.role_map), [])

    def test_breakdown_is_100_percent_skill_prose(self) -> None:
        pcts = self.role_map["breakdown"]["percentages"]
        self.assertAlmostEqual(pcts["skill_share"], 1.0, places=3)
        self.assertAlmostEqual(pcts["code_share"], 0.0, places=3)
        self.assertAlmostEqual(pcts["tool_share"], 0.0, places=3)
        self.assertAlmostEqual(pcts["other_share"], 0.0, places=3)

    def test_has_skill_prose_only(self) -> None:
        self.assertTrue(rm.has_skill_prose(self.role_map))
        self.assertFalse(rm.has_skill_tools(self.role_map))
        self.assertFalse(rm.has_code(self.role_map))

    def test_legacy_project_type_is_skill(self) -> None:
        self.assertEqual(rm.derive_legacy_project_type(self.role_map), "Skill")


# ---------------------------------------------------------------------------
# Fixture 3 — pure-code: chi/virtio/express-style
# ---------------------------------------------------------------------------


class PureCodeProjectFixtureTests(unittest.TestCase):
    """A v1.5.1-pinned code benchmark: no SKILL.md at root, only code
    plus README/test files. Must role-tag as ~100% code with the
    four-pass pipeline gate evaluating to inactive."""

    def setUp(self) -> None:
        self.role_map = _make_role_map([
            _entry("router.go", "code", 12000),
            _entry("middleware.go", "code", 6000),
            _entry("handler.go", "code", 2000),
            _entry("router_test.go", "test", 4000),
            _entry("README.md", "docs", 1500),
            _entry("go.mod", "config", 500),
        ])

    def test_validates_clean(self) -> None:
        self.assertEqual(rm.validate_role_map(self.role_map), [])

    def test_breakdown_dominated_by_code(self) -> None:
        # 20000 code / 26000 total ≈ 0.769
        pcts = self.role_map["breakdown"]["percentages"]
        self.assertGreater(pcts["code_share"], 0.7)
        self.assertEqual(pcts["skill_share"], 0.0)
        self.assertEqual(pcts["tool_share"], 0.0)
        # Test/docs/config bucket into other.
        self.assertGreater(pcts["other_share"], 0.0)

    def test_no_skill_prose(self) -> None:
        self.assertFalse(rm.has_skill_prose(self.role_map))
        self.assertTrue(rm.has_code(self.role_map))

    def test_legacy_project_type_is_code(self) -> None:
        # Four-pass pipeline should NOT activate; existing code-review
        # path runs unchanged.
        self.assertEqual(rm.derive_legacy_project_type(self.role_map), "Code")


# ---------------------------------------------------------------------------
# Fixture 4 — QPB-style: SKILL.md + agents/* + bin/*.py
# ---------------------------------------------------------------------------


class QpbStyleFixtureTests(unittest.TestCase):
    """QPB itself is the sentinel case for "skill-tool vs code." Its
    SKILL.md is large skill-prose; its agents/*.md are also skill-prose;
    its bin/*.py modules carry their own behavior contracts (they're
    NOT subordinate to SKILL.md prose) and must role-tag as code, not
    skill-tool. Misclassifying bin/*.py as skill-tool would explode
    the skill-tool surface area and make the prose-to-code divergence
    check meaningless."""

    def setUp(self) -> None:
        self.role_map = _make_role_map([
            _entry("SKILL.md", "skill-prose", 8000),
            _entry("agents/code-reviewer.md", "skill-prose", 1200),
            _entry("agents/explore.md", "skill-prose", 800),
            _entry("references/exploration_patterns.md", "skill-reference", 3000),
            # bin/*.py must be 'code', NOT 'skill-tool'.
            _entry("bin/run_playbook.py", "code", 90000),
            _entry("bin/archive_lib.py", "code", 24000),
            _entry("bin/citation_verifier.py", "code", 12000),
            _entry("bin/tests/test_archive_lib.py", "test", 8000),
            _entry("docs/design/v1.5.4.md", "docs", 6000),
            _entry(".gitignore", "config", 200),
        ])

    def test_validates_clean(self) -> None:
        self.assertEqual(rm.validate_role_map(self.role_map), [])

    def test_bin_pyfiles_tagged_code_not_skill_tool(self) -> None:
        """The defining QPB invariant: bin/*.py is NEVER skill-tool."""
        for entry in self.role_map["files"]:
            if entry["path"].startswith("bin/") and entry["path"].endswith(".py"):
                if "test" not in entry["path"]:
                    self.assertEqual(
                        entry["role"],
                        "code",
                        msg=(
                            f"{entry['path']} is misclassified as "
                            f"{entry['role']!r} — bin/*.py modules carry "
                            "independent behavior contracts and must "
                            "tag as 'code'"
                        ),
                    )

    def test_no_skill_tool_files(self) -> None:
        # QPB has no skill-tools at all (it has independent code only).
        self.assertFalse(rm.has_skill_tools(self.role_map))

    def test_both_skill_and_code_surfaces_present(self) -> None:
        self.assertTrue(rm.has_skill_prose(self.role_map))
        self.assertTrue(rm.has_code(self.role_map))

    def test_legacy_project_type_is_hybrid(self) -> None:
        # has skill-prose AND has code -> Hybrid (pass_c can demote
        # behavioral claims to Tier 5).
        self.assertEqual(rm.derive_legacy_project_type(self.role_map), "Hybrid")

    def test_breakdown_surfaces_both_sides(self) -> None:
        pcts = self.role_map["breakdown"]["percentages"]
        self.assertGreater(pcts["skill_share"], 0.0)
        self.assertGreater(pcts["code_share"], 0.0)


# ---------------------------------------------------------------------------
# Fixture 5 — pre-played benchmark: target carrying a prior quality/ tree
# ---------------------------------------------------------------------------


class PrePlayedBenchmarkFixtureTests(unittest.TestCase):
    """The v1.5.3 LOC-pollution failure mode: QPB ships its own
    quality_gate.py into a benchmark target's .github/skills/, and
    a prior playbook run leaves a quality/ subtree behind. The v1.5.3
    mechanical classifier counted these as part of the target's code
    LOC and silently flipped the classification.

    In v1.5.4 the role map either omits these paths (Phase 1's ignore
    rules already skip quality/) OR tags them explicitly as
    playbook-output. Either way, the breakdown for the target's
    intrinsic surface is what it is — there's no LOC-denominator math
    that can be polluted. This fixture pins the contract: when
    playbook-output entries appear in the role map, they bucket into
    other_share, never into code_share or skill_share."""

    def setUp(self) -> None:
        self.role_map = _make_role_map([
            # Target's own surface — pure code.
            _entry("src/parser.py", "code", 3000),
            _entry("src/serializer.py", "code", 2000),
            # Prior playbook output that stuck around in the target.
            _entry("quality/EXPLORATION.md", "playbook-output", 4000),
            _entry("quality/REQUIREMENTS.md", "playbook-output", 3000),
            _entry("quality/runs/20260101T000000Z/INDEX.md", "playbook-output", 1000),
            _entry(".github/skills/quality_gate.py", "playbook-output", 50000),
        ])

    def test_validates_clean(self) -> None:
        self.assertEqual(rm.validate_role_map(self.role_map), [])

    def test_playbook_output_does_not_inflate_code_share(self) -> None:
        # If the v1.5.3 bug had reoccurred, the 50000-byte quality_gate.py
        # would be lumped into code_share and dominate. v1.5.4 bucketing
        # routes playbook-output into other_share.
        pcts = self.role_map["breakdown"]["percentages"]
        # 5000 code / 63000 total ≈ 0.079
        self.assertLess(pcts["code_share"], 0.10)
        self.assertEqual(pcts["skill_share"], 0.0)
        self.assertEqual(pcts["tool_share"], 0.0)
        # Playbook output dominates other.
        self.assertGreater(pcts["other_share"], 0.85)

    def test_legacy_project_type_is_code_not_skill(self) -> None:
        # The target itself is pure-code; the playbook artifacts must
        # not flip the legacy-project-type derivation to Skill/Hybrid.
        self.assertEqual(rm.derive_legacy_project_type(self.role_map), "Code")

    def test_no_skill_activation_from_playbook_output(self) -> None:
        # quality_gate.py is technically a Python file but it's NOT the
        # target's code surface; the role map's playbook-output tag
        # ensures has_code() reflects only the target's intrinsic code.
        # In this fixture the target also has src/*.py so has_code is
        # True — but tagging IS what protects: if the target had no
        # intrinsic code, playbook-output would not flip the predicate.
        self.assertTrue(rm.has_code(self.role_map))  # src/*.py
        self.assertFalse(rm.has_skill_prose(self.role_map))
        self.assertFalse(rm.has_skill_tools(self.role_map))

    def test_pure_target_with_only_playbook_output_is_not_skill(self) -> None:
        """Sentinel: a hypothetical target with NO intrinsic surface
        and only playbook leftovers must not classify as anything
        skill-side. playbook-output never activates skill predicates."""
        playbook_only = _make_role_map([
            _entry("quality/EXPLORATION.md", "playbook-output", 4000),
            _entry(".github/skills/quality_gate.py", "playbook-output", 50000),
        ])
        self.assertFalse(rm.has_skill_prose(playbook_only))
        self.assertFalse(rm.has_code(playbook_only))
        self.assertFalse(rm.has_skill_tools(playbook_only))
        self.assertEqual(rm.derive_legacy_project_type(playbook_only), "Code")


# ---------------------------------------------------------------------------
# Schema + helper unit tests
# ---------------------------------------------------------------------------


class ValidateRoleMapTests(unittest.TestCase):
    def test_rejects_non_dict(self) -> None:
        self.assertTrue(rm.validate_role_map([]))

    def test_rejects_missing_top_keys(self) -> None:
        errs = rm.validate_role_map({"schema_version": rm.SCHEMA_VERSION})
        self.assertTrue(any("files" in e for e in errs))
        self.assertTrue(any("breakdown" in e for e in errs))

    def test_rejects_invalid_role(self) -> None:
        bad = _make_role_map([_entry("foo.py", "code", 100)])
        bad["files"][0]["role"] = "not-a-real-role"
        errs = rm.validate_role_map(bad)
        self.assertTrue(any("not-a-real-role" in e for e in errs))

    def test_rejects_duplicate_paths(self) -> None:
        bad = _make_role_map([
            _entry("foo.py", "code", 100),
            _entry("foo.py", "code", 200),
        ])
        errs = rm.validate_role_map(bad)
        self.assertTrue(any("duplicate" in e for e in errs))

    def test_rejects_negative_size(self) -> None:
        bad = _make_role_map([_entry("foo.py", "code", 100)])
        bad["files"][0]["size_bytes"] = -1
        errs = rm.validate_role_map(bad)
        self.assertTrue(any("size_bytes" in e for e in errs))

    def test_rejects_schema_version_mismatch(self) -> None:
        bad = _make_role_map([_entry("foo.py", "code", 100)])
        bad["schema_version"] = "9.9"
        errs = rm.validate_role_map(bad)
        self.assertTrue(any("schema_version" in e for e in errs))

    def test_rejects_percentage_sum_drift(self) -> None:
        bad = _make_role_map([_entry("foo.py", "code", 100)])
        bad["breakdown"]["percentages"]["code_share"] = 0.5  # was 1.0
        errs = rm.validate_role_map(bad)
        self.assertTrue(any("sum to 1.0" in e for e in errs))

    def test_skill_tool_with_empty_prose_reference_rejected(self) -> None:
        bad = _make_role_map([
            _entry(
                "scripts/x.py",
                "skill-tool",
                500,
                skill_prose_reference="",
            ),
        ])
        errs = rm.validate_role_map(bad)
        self.assertTrue(any("skill_prose_reference" in e for e in errs))


class SkillToolProseReferenceRequiredTests(unittest.TestCase):
    """v1.5.4 Round 1 Council finding A2/B2/C1: skill_prose_reference is
    REQUIRED on every skill-tool entry. Without it, the Phase 4
    prose-to-code divergence check cannot anchor against the cited
    prose location."""

    def test_skill_tool_with_valid_prose_reference_passes(self) -> None:
        ok = _make_role_map([
            _entry(
                "scripts/x.py",
                "skill-tool",
                500,
                skill_prose_reference="SKILL.md:42",
            ),
        ])
        self.assertEqual(rm.validate_role_map(ok), [])

    def test_skill_tool_missing_prose_reference_rejected(self) -> None:
        # Construct entry WITHOUT skill_prose_reference at all.
        bad = _make_role_map([
            _entry("scripts/x.py", "skill-tool", 500),
        ])
        errs = rm.validate_role_map(bad)
        self.assertTrue(
            any("skill_prose_reference" in e for e in errs),
            f"expected skill_prose_reference error, got {errs}",
        )
        self.assertTrue(
            any("scripts/x.py" in e for e in errs),
            f"expected error to name the offending path, got {errs}",
        )

    def test_skill_tool_empty_string_prose_reference_rejected(self) -> None:
        bad = _make_role_map([
            _entry(
                "scripts/x.py",
                "skill-tool",
                500,
                skill_prose_reference="",
            ),
        ])
        errs = rm.validate_role_map(bad)
        self.assertTrue(any("skill_prose_reference" in e for e in errs))

    def test_skill_tool_non_string_prose_reference_rejected(self) -> None:
        bad = _make_role_map([
            _entry(
                "scripts/x.py",
                "skill-tool",
                500,
                skill_prose_reference=42,  # int, not string
            ),
        ])
        errs = rm.validate_role_map(bad)
        self.assertTrue(any("skill_prose_reference" in e for e in errs))

    def test_code_entry_without_prose_reference_passes(self) -> None:
        # The skill_prose_reference requirement applies ONLY to
        # skill-tool entries; a code entry has no obligation to carry it.
        ok = _make_role_map([
            _entry("bin/run_playbook.py", "code", 90000),
        ])
        self.assertEqual(rm.validate_role_map(ok), [])


class ComputeBreakdownTests(unittest.TestCase):
    def test_empty_files_yields_zero_shares(self) -> None:
        bd = rm.compute_breakdown([])
        self.assertEqual(bd["files_by_role"], {})
        for v in bd["percentages"].values():
            self.assertEqual(v, 0.0)

    def test_unknown_role_skipped(self) -> None:
        bd = rm.compute_breakdown([
            _entry("a", "code", 100),
            {"path": "b", "role": "garbage", "size_bytes": 100, "rationale": "x"},
        ])
        # Only the legitimate code entry counts; garbage role is dropped.
        self.assertEqual(bd["files_by_role"], {"code": 1})
        self.assertEqual(bd["percentages"]["code_share"], 1.0)

    def test_playbook_output_buckets_into_other(self) -> None:
        bd = rm.compute_breakdown([
            _entry("a", "playbook-output", 100),
            _entry("b", "code", 100),
        ])
        self.assertAlmostEqual(bd["percentages"]["code_share"], 0.5, places=3)
        self.assertAlmostEqual(bd["percentages"]["other_share"], 0.5, places=3)
        self.assertAlmostEqual(bd["percentages"]["skill_share"], 0.0, places=3)


class LoadRoleMapTests(unittest.TestCase):
    def test_load_returns_none_when_absent(self) -> None:
        with TemporaryDirectory() as tmp:
            self.assertIsNone(rm.load_role_map(Path(tmp) / "missing.json"))

    def test_load_returns_none_on_garbage(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "rm.json"
            p.write_text("not json", encoding="utf-8")
            self.assertIsNone(rm.load_role_map(p))

    def test_load_returns_dict_on_valid(self) -> None:
        with TemporaryDirectory() as tmp:
            p = Path(tmp) / "rm.json"
            payload = _make_role_map([_entry("x.py", "code", 100)])
            p.write_text(json.dumps(payload), encoding="utf-8")
            loaded = rm.load_role_map(p)
            self.assertIsInstance(loaded, dict)
            self.assertEqual(rm.validate_role_map(loaded), [])

    def test_default_path_under_quality(self) -> None:
        path = rm.default_path(Path("/tmp/repo"))
        self.assertEqual(
            path, Path("/tmp/repo/quality/exploration_role_map.json")
        )


class IndexBreakdownProjectionTests(unittest.TestCase):
    def test_role_breakdown_for_index_includes_three_subkeys(self) -> None:
        m = _make_role_map([_entry("a.py", "code", 100)])
        out = rm.role_breakdown_for_index(m)
        self.assertIsNotNone(out)
        self.assertIn("files_by_role", out)
        self.assertIn("size_by_role", out)
        self.assertIn("percentages", out)

    def test_role_breakdown_for_index_returns_none_when_absent(self) -> None:
        self.assertIsNone(rm.role_breakdown_for_index(None))
        self.assertIsNone(rm.role_breakdown_for_index({}))


class PromptTaxonomySingleSourceTests(unittest.TestCase):
    """v1.5.4 Round 1 Council finding C3-1: Phase 1 prompt builds its
    role-taxonomy section from bin.role_map.ROLE_DESCRIPTIONS rather
    than enumerating roles in a second place. This test pins that
    contract — adding a role to ROLE_DESCRIPTIONS without rebuilding
    the prompt would be caught here."""

    def test_phase1_prompt_contains_every_valid_role(self) -> None:
        from bin import run_playbook
        prompt = run_playbook.phase1_prompt(no_seeds=False)
        for role in rm.VALID_ROLES:
            self.assertIn(
                f"`{role}`",
                prompt,
                f"role {role!r} from VALID_ROLES is missing from "
                "phase1_prompt — single source of truth broken",
            )

    def test_role_descriptions_keys_match_valid_roles(self) -> None:
        # If someone redefines VALID_ROLES without rebuilding it from
        # ROLE_DESCRIPTIONS, the two will drift; pin them.
        self.assertEqual(set(rm.ROLE_DESCRIPTIONS.keys()), set(rm.VALID_ROLES))

    def test_skill_tool_description_anchors_load_bearing_example(self) -> None:
        """v1.5.4 Round 2 Council finding C3: the skill-tool description
        must include the bin/run_playbook.py worked example.

        This worked example is the load-bearing distinction between
        skill-tool and code: bin/run_playbook.py IS code, NOT skill-tool,
        even though SKILL.md mentions it. test_phase1_prompt_contains_every_valid_role
        only checks role names; a description-trimming refactor that
        drops this example would silently regress role-tagging quality.
        This test pins the example so such a refactor fails here first.
        If you ever change the wording, update both this test and the
        ROLE_DESCRIPTIONS entry together."""
        description = rm.ROLE_DESCRIPTIONS["skill-tool"]
        self.assertIn(
            "bin/run_playbook.py",
            description,
            "skill-tool description must reference the bin/run_playbook.py "
            "worked example as the canonical 'this is code, not skill-tool' "
            "case. If you removed this example, restore it; the role-tagging "
            "prompt loses its load-bearing distinction without it.",
        )
        self.assertIn(
            "code",
            description.lower(),
            "skill-tool description should explicitly contrast skill-tool "
            "with the code role.",
        )


class CodexPreventionDisallowedPathTests(unittest.TestCase):
    """v1.5.4 Phase 3.6.1 Section A.1.a (codex-prevention): the
    role-map validator must reject paths that almost certainly came
    from walking .gitignored content. Codex's 2026-04-29 self-audit
    attempt produced a 5287-entry role map containing .git/ and .venv/
    paths, blowing past Phase 2's context budget. These tests pin the
    rejection so the failure mode can't recur silently."""

    def test_validate_rejects_git_internals(self) -> None:
        bad = _make_role_map([
            _entry("SKILL.md", "skill-prose", 1000),
            _entry(".git/objects/abc123", "code", 100),
        ])
        errs = rm.validate_role_map(bad)
        self.assertTrue(
            any(".git/" in e and "disallowed" in e for e in errs),
            f"expected .git/ rejection, got: {errs}",
        )

    def test_validate_rejects_venv(self) -> None:
        bad = _make_role_map([
            _entry("SKILL.md", "skill-prose", 1000),
            _entry(
                ".venv/lib/python3.13/site-packages/x.py", "code", 100
            ),
        ])
        errs = rm.validate_role_map(bad)
        self.assertTrue(any(".venv/" in e for e in errs))

    def test_validate_rejects_pycache(self) -> None:
        bad = _make_role_map([
            _entry("SKILL.md", "skill-prose", 1000),
            _entry(
                "__pycache__/role_map.cpython-313.pyc", "code", 100
            ),
        ])
        errs = rm.validate_role_map(bad)
        self.assertTrue(any("__pycache__/" in e for e in errs))

    def test_validate_rejects_egg_info_via_suffix(self) -> None:
        """Path components ending in .egg-info / .dist-info are
        rejected via Path.parts inspection — proves the suffix path
        works regardless of where the component sits, not only when
        it's the leading prefix."""
        bad = _make_role_map([
            _entry("SKILL.md", "skill-prose", 1000),
            _entry("src/my_pkg.egg-info/PKG-INFO", "config", 100),
        ])
        errs = rm.validate_role_map(bad)
        self.assertTrue(
            any("egg-info" in e for e in errs),
            f"expected egg-info rejection, got: {errs}",
        )

    def test_validate_rejects_oversized_role_map(self) -> None:
        # 2001 entries — one over the default ceiling.
        files = [
            _entry(f"src/file{i:04d}.py", "code", 10) for i in range(2001)
        ]
        bad = _make_role_map(files)
        errs = rm.validate_role_map(bad)
        self.assertTrue(
            any("entries (limit" in e for e in errs),
            f"expected entry-count ceiling rejection, got: "
            f"{[e for e in errs if 'entries' in e or 'limit' in e]}",
        )

    def test_validate_accepts_clean_role_map(self) -> None:
        ok = _make_role_map([
            _entry("SKILL.md", "skill-prose", 1000),
            _entry("bin/main.py", "code", 500),
            _entry("README.md", "docs", 200),
        ])
        self.assertEqual(rm.validate_role_map(ok), [])

    def test_allow_disallowed_prefix_override(self) -> None:
        """Operator override suppresses the named prefix's rejection
        while leaving other disallowed prefixes still rejected."""
        bad = _make_role_map([
            _entry("SKILL.md", "skill-prose", 1000),
            _entry(".venv/lib/x.py", "code", 100),  # legitimately committed
            _entry(".git/objects/abc", "code", 100),  # not overridden
        ])
        errs = rm.validate_role_map(
            bad, allowed_disallowed_prefixes=frozenset({".venv/"})
        )
        # .venv error suppressed; .git error still fires.
        self.assertFalse(any(".venv/" in e for e in errs))
        self.assertTrue(any(".git/" in e for e in errs))

    def test_max_role_map_entries_override(self) -> None:
        """Operator override raises the entry-count ceiling for
        legitimately-large targets."""
        files = [
            _entry(f"src/file{i:04d}.py", "code", 10) for i in range(2001)
        ]
        bad = _make_role_map(files)
        errs = rm.validate_role_map(bad, max_role_map_entries=3000)
        self.assertFalse(
            any("entries (limit" in e for e in errs),
            f"override must suppress ceiling error, got: "
            f"{[e for e in errs if 'entries' in e]}",
        )

    def test_validate_rejects_missing_provenance(self) -> None:
        bad = _make_role_map([_entry("SKILL.md", "skill-prose", 1000)])
        del bad["provenance"]
        errs = rm.validate_role_map(bad)
        self.assertTrue(any("provenance" in e for e in errs))

    def test_validate_rejects_invalid_provenance(self) -> None:
        bad = _make_role_map([_entry("SKILL.md", "skill-prose", 1000)])
        bad["provenance"] = "made-up-source"
        errs = rm.validate_role_map(bad)
        self.assertTrue(any("provenance" in e for e in errs))

    def test_validate_accepts_filesystem_walk_provenance(self) -> None:
        ok = _make_role_map(
            [_entry("SKILL.md", "skill-prose", 1000)],
            provenance="filesystem-walk-with-skips",
        )
        self.assertEqual(rm.validate_role_map(ok), [])


class CodexPreventionSummaryHelperTests(unittest.TestCase):
    """v1.5.4 Phase 3.6.1 Section A.1.c: ``summarize_role_map`` is the
    single source of truth for cross-artifact agreement. Both the
    role map's ``summary`` field AND EXPLORATION.md's "File inventory"
    section render from this helper. The codex hallucination class
    (narrative cites ~293 files while JSON holds 5287) is impossible
    when both consume the helper."""

    def test_summary_matches_breakdown(self) -> None:
        m = _make_role_map([
            _entry("SKILL.md", "skill-prose", 1000),
            _entry("bin/main.py", "code", 500),
            _entry("README.md", "docs", 200),
        ])
        s = rm.summarize_role_map(m)
        self.assertEqual(s["file_count"], 3)
        self.assertEqual(s["role_breakdown"],
                         {"skill-prose": 1, "code": 1, "docs": 1})
        self.assertEqual(s["provenance"], "git-ls-files")
        # Percentages match the breakdown's percentages exactly.
        self.assertEqual(s["percentages"],
                         m["breakdown"]["percentages"])

    def test_role_map_summary_matches_narrative_render(self) -> None:
        """Cross-artifact agreement test (the regression pin for the
        codex hallucination class). The narrative rendering must
        contain the same file count and the same per-role counts as
        the JSON ``summary`` field."""
        m = _make_role_map([
            _entry("SKILL.md", "skill-prose", 1000),
            _entry("bin/a.py", "code", 100),
            _entry("bin/b.py", "code", 100),
            _entry("README.md", "docs", 200),
        ])
        narrative = rm.render_role_map_narrative(m)
        s = rm.summarize_role_map(m)
        self.assertIn(f"Total files:** {s['file_count']}", narrative)
        for role, count in s["role_breakdown"].items():
            self.assertIn(f"`{role}`: {count}", narrative)
        # Provenance shows up under the same label.
        self.assertIn(f"Provenance:** `{s['provenance']}`", narrative)


class Round8Fix5SummarySelfConsistencyTests(unittest.TestCase):
    """v1.5.4 Phase 3.7 Fix 5 (Round 8 HIGH): validate_role_map now
    enforces summary self-consistency. The codex hallucination class
    was structurally addressed in Section A.1.c (summarize_role_map
    is the single source of truth for both the JSON summary AND the
    EXPLORATION.md narrative), but a hand-fabricated role map could
    still claim {"file_count": 9999, "files": [<2 entries>]} and
    pass validation. Now it doesn't."""

    def test_validate_rejects_summary_mismatch(self) -> None:
        rmap = _make_role_map([
            _entry("SKILL.md", "skill-prose", 1000),
            _entry("bin/main.py", "code", 500),
        ])
        # Hand-fabricate a bogus summary: claims 9999 files when the
        # actual files[] has 2.
        rmap["summary"] = {
            "file_count": 9999,
            "role_breakdown": {"skill-prose": 9999},
            "percentages": {
                "skill_share": 1.0, "code_share": 0.0,
                "tool_share": 0.0, "other_share": 0.0,
            },
            "provenance": "git-ls-files",
        }
        errs = rm.validate_role_map(rmap)
        self.assertTrue(
            any("summary" in e and "does not match" in e for e in errs),
            f"expected summary-mismatch error, got: {errs}",
        )

    def test_validate_accepts_matching_summary(self) -> None:
        # _make_role_map already populates summary via summarize_role_map,
        # so a well-formed map passes by construction. This is the
        # negative control proving the new check doesn't over-fire.
        rmap = _make_role_map([
            _entry("SKILL.md", "skill-prose", 1000),
            _entry("bin/main.py", "code", 500),
        ])
        self.assertEqual(rm.validate_role_map(rmap), [])

    def test_validate_handles_missing_summary(self) -> None:
        """summary is in _REQUIRED_TOP_KEYS (Phase 3.6.1), so a map
        without it fails the early required-key check rather than
        reaching the new self-consistency check. Pin the early-exit
        path so a future refactor can't silently regress it."""
        rmap = _make_role_map([_entry("SKILL.md", "skill-prose", 1000)])
        del rmap["summary"]
        errs = rm.validate_role_map(rmap)
        self.assertTrue(any("summary" in e for e in errs))

    def test_validate_rejects_summary_with_wrong_role_breakdown(self) -> None:
        """Even when file_count is right, mismatched role_breakdown
        counts must still fail (each piece of the summary is
        cross-checked against the helper's output)."""
        files = [
            _entry("SKILL.md", "skill-prose", 1000),
            _entry("bin/main.py", "code", 500),
        ]
        rmap = _make_role_map(files)
        # Correct file_count, wrong role_breakdown.
        rmap["summary"] = {
            "file_count": 2,
            "role_breakdown": {"skill-prose": 2, "code": 0},  # wrong
            "percentages": rmap["breakdown"]["percentages"],
            "provenance": "git-ls-files",
        }
        errs = rm.validate_role_map(rmap)
        self.assertTrue(
            any("summary" in e and "does not match" in e for e in errs)
        )


class NormalizeRoleMapForGateTests(unittest.TestCase):
    """v1.5.6 cluster 047 architectural fix:
    `normalize_role_map_for_gate(path)` recomputes ``breakdown`` and
    ``summary`` from the LLM's ``files[]`` and writes the result back
    to disk. The Phase 2 entry-gate's self-consistency checks then
    pass by construction.

    Pre-cluster-047 the LLM was instructed to produce both
    ``breakdown`` and ``summary``; sonnet-4.6 reliably reverted to
    intuitive summarization that drifted from the strict mechanical
    contract (cluster E retries: 2 attempts, 2 different summary-shape
    failures). Moving the deterministic computation runner-side
    removes the failure mode entirely."""

    def _well_formed_files(self) -> list[dict]:
        return [
            _entry("SKILL.md", "skill-prose", 6000),
            _entry("references/foo.md", "skill-reference", 2000),
            _entry("bin/main.py", "code", 1500),
            _entry("bin/test_main.py", "test", 800),
            _entry(
                "scripts/run.py", "skill-tool", 500,
                skill_prose_reference="SKILL.md:42",
            ),
        ]

    def test_normalize_replaces_wrong_summary_with_canonical(self) -> None:
        """The cluster E failure mode reproduces here: stage a role_map
        with an LLM-style intuitive summary that drifts from
        summarize_role_map(). After normalize, summary equals the
        canonical derivation, NOT the LLM's hand-written version."""
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "exploration_role_map.json"
            files = self._well_formed_files()
            # Stage a role map with a deliberately-wrong summary
            # (mimicking sonnet-4.6's drift: file_count off by N,
            # role_breakdown counts that don't match files).
            wrong_role_map = {
                "schema_version": rm.SCHEMA_VERSION,
                "timestamp_start": "2026-05-07T00:00:00Z",
                "provenance": "git-ls-files",
                "files": files,
                "breakdown": rm.compute_breakdown(files),
                "summary": {
                    "file_count": 999,  # wrong (should be 5)
                    "role_breakdown": {"skill-prose": 99, "code": 99},  # wrong
                    "percentages": {
                        "skill_share": 0.99,
                        "code_share": 0.01,
                        "tool_share": 0.0,
                        "other_share": 0.0,
                    },  # wrong
                    "provenance": "git-ls-files",
                },
            }
            path.write_text(json.dumps(wrong_role_map, indent=2), encoding="utf-8")

            ok, errs = rm.normalize_role_map_for_gate(path)
            self.assertTrue(ok, msg=f"normalize failed: {errs}")
            self.assertEqual(errs, [])

            # The on-disk summary must now equal the canonical derivation.
            normalized = rm.load_role_map(path)
            self.assertIsNotNone(normalized)
            expected = rm.summarize_role_map(normalized)
            self.assertEqual(normalized["summary"], expected)
            # And specifically the file_count is now correct (5, not 999).
            self.assertEqual(normalized["summary"]["file_count"], 5)
            # And the validator passes (this is what makes the Phase 2
            # entry-gate's check succeed by construction).
            validation_errors = rm.validate_role_map(normalized)
            self.assertEqual(validation_errors, [])

    def test_normalize_replaces_wrong_breakdown_with_canonical(self) -> None:
        """Sonnet-4.6's second failure mode (cluster E retry) was a
        wrong breakdown structure (descriptive note-style fields like
        skill_share_pct instead of the required percentages dict).
        Normalize must replace whatever the LLM wrote with the
        canonical compute_breakdown() output."""
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "exploration_role_map.json"
            files = self._well_formed_files()
            wrong_role_map = {
                "schema_version": rm.SCHEMA_VERSION,
                "timestamp_start": "2026-05-07T00:00:00Z",
                "provenance": "git-ls-files",
                "files": files,
                # Sonnet-4.6 cluster-E-retry-style descriptive
                # breakdown — wrong shape, wrong keys.
                "breakdown": {
                    "skill_share_pct": 88.0,
                    "code_share_pct": 12.0,
                    "skill_share_note": "skill prose / total",
                    "key_risk_files": ["bin/main.py"],
                },
                # Summary doesn't matter — normalize recomputes it
                # from the new breakdown.
                "summary": {"file_count": 5, "role_breakdown": {}, "percentages": {}, "provenance": "git-ls-files"},
            }
            path.write_text(json.dumps(wrong_role_map, indent=2), encoding="utf-8")

            ok, errs = rm.normalize_role_map_for_gate(path)
            self.assertTrue(ok, msg=f"normalize failed: {errs}")

            normalized = rm.load_role_map(path)
            assert normalized is not None
            # Breakdown now has the canonical shape.
            self.assertIn("files_by_role", normalized["breakdown"])
            self.assertIn("size_by_role", normalized["breakdown"])
            self.assertIn("percentages", normalized["breakdown"])
            # The descriptive sonnet-style fields are gone.
            self.assertNotIn("skill_share_pct", normalized["breakdown"])
            self.assertNotIn("key_risk_files", normalized["breakdown"])
            # Validator passes.
            self.assertEqual(rm.validate_role_map(normalized), [])

    def test_normalize_idempotent_on_legacy_correct_role_map(self) -> None:
        """Backward compat: a role_map that already has a correct
        LLM-written breakdown + summary recomputes to the same values.
        This is what existing previous_runs/ archives carry; the
        normalize step must not corrupt them."""
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "exploration_role_map.json"
            # _make_role_map produces a canonical role_map by definition.
            role_map = _make_role_map(self._well_formed_files())
            path.write_text(json.dumps(role_map, indent=2), encoding="utf-8")

            ok, errs = rm.normalize_role_map_for_gate(path)
            self.assertTrue(ok, msg=f"normalize failed: {errs}")

            normalized = rm.load_role_map(path)
            assert normalized is not None
            # Files unchanged.
            self.assertEqual(normalized["files"], role_map["files"])
            # Breakdown + summary equal what was already there.
            self.assertEqual(normalized["breakdown"], role_map["breakdown"])
            self.assertEqual(normalized["summary"], role_map["summary"])

    def test_normalize_handles_role_map_without_breakdown_at_all(self) -> None:
        """The cluster 047 fix moves breakdown into the runner's
        responsibility — the LLM may legitimately produce a role_map
        with ONLY files[] and provenance (no breakdown, no summary)
        once the post-cluster-047 phase1.md prompt is in use.
        Normalize must produce a complete canonical role_map from
        that minimal input."""
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "exploration_role_map.json"
            files = self._well_formed_files()
            # Minimal LLM output (post-cluster-047 prompt shape).
            minimal = {
                "schema_version": rm.SCHEMA_VERSION,
                "timestamp_start": "2026-05-07T00:00:00Z",
                "provenance": "git-ls-files",
                "files": files,
            }
            path.write_text(json.dumps(minimal, indent=2), encoding="utf-8")

            ok, errs = rm.normalize_role_map_for_gate(path)
            self.assertTrue(ok, msg=f"normalize failed: {errs}")

            normalized = rm.load_role_map(path)
            assert normalized is not None
            self.assertIn("breakdown", normalized)
            self.assertIn("summary", normalized)
            # Validator now passes.
            self.assertEqual(rm.validate_role_map(normalized), [])
            # And the breakdown is correct.
            self.assertEqual(
                normalized["breakdown"]["files_by_role"]["code"], 1
            )

    def test_normalize_returns_false_on_unloadable_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "missing.json"
            ok, errs = rm.normalize_role_map_for_gate(path)
            self.assertFalse(ok)
            self.assertTrue(errs)
            self.assertTrue(any("could not load" in e for e in errs))

    def test_normalize_returns_false_when_files_is_not_a_list(self) -> None:
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "exploration_role_map.json"
            broken = {
                "schema_version": rm.SCHEMA_VERSION,
                "timestamp_start": "2026-05-07T00:00:00Z",
                "provenance": "git-ls-files",
                "files": "not-a-list",
            }
            path.write_text(json.dumps(broken), encoding="utf-8")
            ok, errs = rm.normalize_role_map_for_gate(path)
            self.assertFalse(ok)
            self.assertTrue(any("'files' must be a list" in e for e in errs))


class CheckPhaseGateNormalizeIntegrationTests(unittest.TestCase):
    """v1.5.6 cluster 047: the Phase 2 entry-gate in
    `bin.run_playbook.check_phase_gate(repo, '2', ...)` calls
    `normalize_role_map_for_gate` before invoking
    `validate_role_map`. The integration test stages a role_map with
    drift-class wrong summary (the sonnet-4.6 failure mode), runs the
    gate, and asserts it now PASSES — pre-cluster-047 it would fail
    on the summary-mismatch check."""

    def test_phase2_gate_passes_after_normalize_overwrites_wrong_summary(self) -> None:
        from bin import run_playbook
        import argparse
        with TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            quality = repo / "quality"
            quality.mkdir()
            # 120-line EXPLORATION.md so the line-count check passes.
            exploration = quality / "EXPLORATION.md"
            body_lines = "\n".join(
                f"line {i}" for i in range(150)
            )
            exploration.write_text(
                "## Open Exploration Findings\n\n" + body_lines + "\n",
                encoding="utf-8",
            )
            # Role map with a sonnet-style wrong summary.
            files = [
                _entry("SKILL.md", "skill-prose", 6000),
                _entry("bin/main.py", "code", 1500),
            ]
            wrong_role_map = {
                "schema_version": rm.SCHEMA_VERSION,
                "timestamp_start": "2026-05-07T00:00:00Z",
                "provenance": "git-ls-files",
                "files": files,
                "breakdown": rm.compute_breakdown(files),
                "summary": {
                    "file_count": 9999,  # wrong
                    "role_breakdown": {},
                    "percentages": {
                        "skill_share": 0.0, "code_share": 0.0,
                        "tool_share": 0.0, "other_share": 0.0,
                    },
                    "provenance": "git-ls-files",
                },
            }
            (quality / rm.DEFAULT_FILENAME).write_text(
                json.dumps(wrong_role_map, indent=2), encoding="utf-8",
            )
            args = argparse.Namespace(
                allow_disallowed_prefix=None,
                max_role_map_entries=None,
            )
            result = run_playbook.check_phase_gate(repo, "2", args=args)
            self.assertTrue(
                result.ok,
                msg=f"Phase 2 gate must pass after normalize. Messages: {result.messages}",
            )

    def test_phase2_gate_passes_with_minimal_post_cluster_047_role_map(self) -> None:
        """The post-cluster-047 phase1.md prompt instructs the LLM to
        produce only files[] + provenance (no breakdown, no summary).
        The Phase 2 gate must still pass after the runner's normalize
        step computes breakdown + summary."""
        from bin import run_playbook
        import argparse
        with TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            quality = repo / "quality"
            quality.mkdir()
            body_lines = "\n".join(f"line {i}" for i in range(150))
            (quality / "EXPLORATION.md").write_text(
                "## Open Exploration Findings\n\n" + body_lines + "\n",
                encoding="utf-8",
            )
            minimal = {
                "schema_version": rm.SCHEMA_VERSION,
                "timestamp_start": "2026-05-07T00:00:00Z",
                "provenance": "git-ls-files",
                "files": [
                    _entry("SKILL.md", "skill-prose", 6000),
                    _entry("bin/main.py", "code", 1500),
                ],
            }
            (quality / rm.DEFAULT_FILENAME).write_text(
                json.dumps(minimal, indent=2), encoding="utf-8",
            )
            args = argparse.Namespace(
                allow_disallowed_prefix=None,
                max_role_map_entries=None,
            )
            result = run_playbook.check_phase_gate(repo, "2", args=args)
            self.assertTrue(
                result.ok,
                msg=f"Phase 2 gate must pass on minimal-LLM-output role map. "
                f"Messages: {result.messages}",
            )


if __name__ == "__main__":
    unittest.main()
