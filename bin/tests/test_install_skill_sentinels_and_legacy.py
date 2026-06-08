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
    sentinel file(s) the gitignore-template negation rules require,
    so run_playbook.py's pre-flight does not abort with "Required
    sentinel files missing".

    v1.5.7 instruction 090h: `informal_docs/` retired (nothing
    ingests it; misleading "place context here" README caused the
    2026-05-23 OpenFGA dogfood to nearly run doc-blind). Install
    now creates only `quality/RUN_INDEX.md`. The pre-090h
    `test_install_creates_informal_docs_readme` test was removed and
    replaced with the reverse-direction
    `test_install_does_not_create_informal_docs_directory` below.

    Mutation-test evidence (in-tree per
    ai_context/DEVELOPMENT_PROCESS.md:152-160) — BITE EXECUTED:
      Pre-090h bite (instruction-087): remove the
        `_ensure_sentinel_files(...)` call from install() →
        test_install_creates_quality_run_index FAILs with
        "<target>/quality/RUN_INDEX.md does not exist".
      Post-090h bite (this instruction): re-add
        `("informal_docs/README.md", ...)` to install_skill
        `_SENTINEL_FILES` →
        test_install_does_not_create_informal_docs_directory FAILs
        because the directory IS created. Mutation reverted; tests
        pass.
    """

    def test_install_creates_quality_run_index(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            (target / ".github").mkdir()
            install_skill.install(into=target, ai_tool="copilot",
                                  no_smoke=True)
            sentinel = target / "quality" / "RUN_INDEX.md"
            self.assertTrue(sentinel.is_file())
            self.assertGreater(sentinel.stat().st_size, 0)

    def test_install_does_not_create_informal_docs_directory(
            self) -> None:
        """v1.5.7 090h: install must NOT create informal_docs/ — the
        directory is retired. This is the reverse-direction pin for
        the pre-090h `test_install_creates_informal_docs_readme`
        test (now removed). Mutation bite: re-adding the
        `informal_docs/README.md` entry to install_skill
        `_SENTINEL_FILES` fires this test."""
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            (target / ".github").mkdir()
            install_skill.install(into=target, ai_tool="copilot",
                                  no_smoke=True)
            self.assertFalse(
                (target / "informal_docs").exists(),
                "v1.5.7 090h: informal_docs/ is retired — install "
                "must not create the directory.")

    def test_install_preserves_existing_run_index_content(
            self) -> None:
        """The `_ensure_sentinel_files` no-overwrite-when-non-empty
        contract (A-24 Things-to-NOT-do) must hold for the remaining
        RUN_INDEX.md sentinel. Pre-090h this test guarded
        informal_docs/README.md; the contract applies identically to
        the RUN_INDEX.md sentinel."""
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            (target / ".github").mkdir()
            (target / "quality").mkdir()
            existing = target / "quality" / "RUN_INDEX.md"
            existing.write_text("# My Custom Index\n", encoding="utf-8")
            install_skill.install(into=target, ai_tool="copilot",
                                  no_smoke=True)
            # Existing content preserved (no overwrite).
            self.assertEqual(existing.read_text(),
                             "# My Custom Index\n")

    def test_install_hint_names_reference_docs_as_doc_location(
            self) -> None:
        """v1.5.7 090h Task E: the `phase1_ingest_invocation_hint`
        prose must point adopters at `reference_docs/` (+ cite/) as
        the doc location and clarify `docs_gathered/` is benchmark
        tooling. Mutation bite: drop the new paragraph from the
        `prose=` block → this test fires."""
        import io
        # Capture install output via verbose stream so we can grep
        # the emitted hint prose.
        buf = io.StringIO()
        with tempfile.TemporaryDirectory() as td:
            target = Path(td)
            (target / ".github").mkdir()
            install_skill.install(into=target, ai_tool="copilot",
                                  no_smoke=True, verbose=True,
                                  stream=buf)
        out = buf.getvalue()
        # The hint MUST point at reference_docs/ + cite/ and call
        # out docs_gathered as benchmark-only.
        self.assertIn("reference_docs/", out)
        self.assertIn("reference_docs/cite/", out)
        self.assertIn("docs_gathered/", out)
        self.assertIn("NOT ingested by an adopter install", out)
        # informal_docs/ must NOT appear in the hint (retired in
        # 090h).
        self.assertNotIn("informal_docs/", out)


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
        text = (_QPB_ROOT / "skills" / "quality-playbook"
                / "phase_prompts" / "phase6.md").read_text(
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
