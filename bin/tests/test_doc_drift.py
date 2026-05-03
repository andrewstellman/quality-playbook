"""Tests for documentation/help-text drift across the QPB repo.

Regression coverage for v1.5.4 self-audit BUG-005, BUG-006, BUG-007 —
all three are help-text or operator-guidance drift where prose tells
the operator to use one path/invocation but the implementation uses
another. Bundled here because they share a shape: scan a doc/help
string for the wrong token and assert it isn't present.

- BUG-005: README.md documented `python3 bin/run_playbook.py` but the
  runner exits EX_USAGE=64 on script-style invocation.
- BUG-006: SKILL.md routed operators to `docs_gathered/` but
  `bin/reference_docs_ingest.py` only reads `reference_docs/`.
- BUG-007: `bin/quality_playbook.py` help text said `quality/runs/`
  but `bin/archive_lib.py:ARCHIVE_DIRNAME == "previous_runs"`.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class ReadmeRunPlaybookInvocationTests(unittest.TestCase):
    """BUG-005: every `python ... bin/run_playbook.py ...` example in
    README.md must use the package-module form, since the runner
    exits EX_USAGE=64 on direct script-style invocation."""

    def test_no_script_style_run_playbook_invocations(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        # Match any "python..." command that ends in run_playbook.py
        # (with anything in the middle: paths, args, etc.). The single
        # exception we tolerate is the exact phrase "bin/run_playbook.py"
        # used as a file reference (not an invocation), which is
        # historical context like "no bin/run_playbook.py changes shipped".
        # We disambiguate by requiring "python" before the path.
        pattern = re.compile(
            r"python\d?\s+[^\n`]*bin/run_playbook\.py",
            re.MULTILINE,
        )
        bad = pattern.findall(readme)
        self.assertEqual(
            bad,
            [],
            "README.md still contains script-style run_playbook.py "
            "invocations that the runner rejects with EX_USAGE=64. Use "
            "`python -m bin.run_playbook ...` instead. Found: " + repr(bad),
        )

    def test_module_form_is_documented(self) -> None:
        """At least one example must show the package-module form so
        adopters can copy a working command."""
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            "python -m bin.run_playbook",
            readme,
            "README.md must document the canonical "
            "`python -m bin.run_playbook` invocation form.",
        )


class SkillReferenceDocsRoutingTests(unittest.TestCase):
    """BUG-006: SKILL.md must route operators to `reference_docs/`,
    not `docs_gathered/`, because that is what
    `bin/reference_docs_ingest.py` actually reads."""

    def test_skill_md_does_not_route_to_docs_gathered(self) -> None:
        skill = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertNotIn(
            "docs_gathered",
            skill,
            "SKILL.md still mentions `docs_gathered/` somewhere; the "
            "ingest implementation only reads `reference_docs/`. Update "
            "all operator-facing references to `reference_docs/`.",
        )

    def test_skill_md_routes_to_reference_docs(self) -> None:
        skill = (REPO_ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn(
            "reference_docs/",
            skill,
            "SKILL.md must route operators to `reference_docs/` "
            "(the directory `bin/reference_docs_ingest.py` actually reads).",
        )

    def test_ingest_module_is_unchanged(self) -> None:
        """Sanity: confirm the ingest module is still the source of truth
        we're aligning to. If someone changes the ingest module's read
        path, this test is the trip wire that surfaces the divergence
        before the prose drifts again."""
        from bin import reference_docs_ingest

        self.assertEqual(
            reference_docs_ingest.REFERENCE_DIR_NAME,
            "reference_docs",
            "If the ingest module's read directory changes, SKILL.md "
            "needs to follow.",
        )


class QualityPlaybookHelpArchivePathTests(unittest.TestCase):
    """BUG-007: bin/quality_playbook.py help text must say
    `quality/previous_runs/`, matching `bin/archive_lib.py:ARCHIVE_DIRNAME`."""

    def test_help_text_uses_previous_runs(self) -> None:
        from bin import quality_playbook, archive_lib

        # The docstring is the help source — it's exposed via -h through
        # argparse's description= or printed directly in usage.
        doc = quality_playbook.__doc__ or ""
        self.assertIn(
            f"quality/{archive_lib.ARCHIVE_DIRNAME}/",
            doc,
            f"bin/quality_playbook.py help text must mention "
            f"`quality/{archive_lib.ARCHIVE_DIRNAME}/` to match "
            f"archive_lib.ARCHIVE_DIRNAME (BUG-007).",
        )

    def test_help_text_does_not_mention_legacy_runs_path(self) -> None:
        """`quality/runs/` is the pre-v1.5.4 legacy location. The
        archive_lib still READS legacy archives (LEGACY_ARCHIVE_DIRNAME)
        but new archives go to `previous_runs/`. The help text must
        document the new location, not the legacy one."""
        from bin import quality_playbook

        doc = quality_playbook.__doc__ or ""
        # Forbid the bare `quality/runs/` form; allow `previous_runs/`.
        forbidden = re.compile(r"quality/runs/")
        self.assertIsNone(
            forbidden.search(doc),
            "bin/quality_playbook.py help text mentions the legacy "
            "`quality/runs/` archive location. Use "
            "`quality/previous_runs/` (BUG-007).",
        )


if __name__ == "__main__":
    unittest.main()
