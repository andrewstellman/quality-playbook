"""v1.5.7 instruction 087 (A-23 + A-24 + A-27 + A-28) regression tests.

Sibling file, consistent with the existing test_install_* split.
NB: install_skill's public in-process entry point is `install(*,
into=, ai_tool=, ...)` — NOT `run_install` (the instruction's
prescribed test snippet named a function that does not exist;
verify-before-claim). `no_smoke=True` keeps these tests fast and
independent of the bundled-module subprocess smoke check.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from bin import install_skill

_QPB_ROOT = Path(__file__).resolve().parents[2]


class SentinelFileCreationTests(unittest.TestCase):
    """v1.5.7 instruction 087 (A-24): install_skill.py creates the
    sentinel files the gitignore-template negation rules require, so
    run_playbook.py's pre-flight does not abort with "Required
    sentinel files missing".

    Mutation-test evidence (in-tree per
    ai_context/DEVELOPMENT_PROCESS.md:152-160) — BITE EXECUTED during
    instruction-087 development:
      Mutation: remove the `_ensure_sentinel_files(...)` call from
        install()'s post-copy flow.
      Observed failure (purged __pycache__ first):
        FAIL: test_install_creates_informal_docs_readme
        AssertionError: False is not true
          (<target>/informal_docs/README.md does not exist)
      Mutation reverted; tests pass.
    """

    def test_install_creates_informal_docs_readme(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            (target / ".github").mkdir()
            install_skill.install(into=target, ai_tool="copilot",
                                  no_smoke=True)
            sentinel = target / "informal_docs" / "README.md"
            self.assertTrue(sentinel.is_file())
            self.assertGreater(sentinel.stat().st_size, 0)

    def test_install_creates_quality_run_index(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            (target / ".github").mkdir()
            install_skill.install(into=target, ai_tool="copilot",
                                  no_smoke=True)
            sentinel = target / "quality" / "RUN_INDEX.md"
            self.assertTrue(sentinel.is_file())
            self.assertGreater(sentinel.stat().st_size, 0)

    def test_install_preserves_existing_sentinel_content(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            (target / ".github").mkdir()
            (target / "informal_docs").mkdir()
            existing = target / "informal_docs" / "README.md"
            existing.write_text("# My Custom Docs\n", encoding="utf-8")
            install_skill.install(into=target, ai_tool="copilot",
                                  no_smoke=True)
            # Existing content preserved (no overwrite).
            self.assertEqual(existing.read_text(), "# My Custom Docs\n")


class FlatLegacyMigrationTests(unittest.TestCase):
    """v1.5.7 instruction 087 (A-23): a coexisting v1.5.6-era flat
    SKILL.md at <marker>/skills/SKILL.md is renamed to
    .legacy-<ts> on a v1.5.7 nested install so a marker-based
    resolver can no longer load the older flat one.

    Mutation-test evidence (in-tree per
    ai_context/DEVELOPMENT_PROCESS.md:152-160) — BITE EXECUTED:
      Mutation: comment out the `_migrate_flat_legacy_install(...)`
        call in install().
      Observed failure (purged __pycache__ first):
        FAIL: test_nested_install_migrates_existing_flat_skill_md
        AssertionError: True is not false : Flat SKILL.md should have
        been migrated
      Mutation reverted; tests pass.
    """

    def test_nested_install_migrates_existing_flat_skill_md(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            marker = target / ".github" / "skills"
            marker.mkdir(parents=True)
            (marker / "SKILL.md").write_text(
                "name: quality-playbook\nversion: 1.5.6\n",
                encoding="utf-8")
            install_skill.install(into=target, ai_tool="copilot",
                                  no_smoke=True)
            self.assertFalse(
                (marker / "SKILL.md").exists(),
                "Flat SKILL.md should have been migrated")
            nested = marker / "quality-playbook" / "SKILL.md"
            self.assertTrue(nested.is_file())
            legacy_files = list(marker.glob("SKILL.md.legacy-*"))
            self.assertEqual(len(legacy_files), 1)

    def test_fresh_install_no_legacy_no_migration(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            marker = target / ".github" / "skills"
            marker.mkdir(parents=True)
            install_skill.install(into=target, ai_tool="copilot",
                                  no_smoke=True)
            legacy_files = list(marker.glob("*.legacy-*"))
            self.assertEqual(len(legacy_files), 0)


class PreShipDocRegressionTests(unittest.TestCase):
    """v1.5.7 instruction 087 (A-27 + A-28): the prose-only fixes have
    no other regression guard; pin the load-bearing strings so a
    future doc edit can't silently revert them. (Instruction Task 5
    recommends these.)"""

    def test_phase6_a27_non_optional_framing_present(self) -> None:
        text = (_QPB_ROOT / "phase_prompts" / "phase6.md").read_text(
            encoding="utf-8")
        self.assertIn("Phase 6 sub-agent delegation is NON-OPTIONAL.",
                      text)
        self.assertIn("You may NOT proceed with in-session "
                      "verification as a fallback.", text)
        self.assertIn("STOP and ask the operator to authorize the "
                      "sub-agent dispatch.", text)

    def test_agents_md_a28_full_pipeline_default_present(self) -> None:
        text = (_QPB_ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(
            'means the FULL six-phase pipeline + four iteration '
            'strategies', text)
        self.assertIn(
            "Phase-1-only as a default is the v1.5.3 legacy", text)


if __name__ == "__main__":
    unittest.main()
