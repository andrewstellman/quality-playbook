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
            "`python3 -m bin.run_playbook ...` instead. Found: " + repr(bad),
        )

    def test_module_form_is_documented(self) -> None:
        """At least one example must show the package-module form so
        adopters can copy a working command."""
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(
            "python3 -m bin.run_playbook",
            readme,
            "README.md must document the canonical "
            "`python3 -m bin.run_playbook` invocation form.",
        )


class SkillReferenceDocsRoutingTests(unittest.TestCase):
    """BUG-006: every operator-facing surface must route operators to
    `reference_docs/`, not `docs_gathered/`, because that is what
    `bin/reference_docs_ingest.py` actually reads.

    v1.5.5 Council finding (Lens 1): the original BUG-006 fix only
    covered SKILL.md, but the same routing prose lives in agents/,
    references/, and bin/run_playbook.py operator-facing WARN
    messages. The test below scans all of them so a future addition
    to any of those surfaces can't reintroduce the misroute.
    """

    # Operator-facing surfaces. Any new file documenting operator
    # workflow goes here. NOT included on purpose:
    # - bin/benchmark_lib.py / tests — `docs_gathered/` is on the
    #   protected-paths list for benchmark archive curation. That's
    #   internal, not operator-routing.
    # - quality/* — these are QPB's own self-audit artifacts. Updating
    #   them would rewrite history; the regen on the next run will
    #   pick up the corrected prose.
    # - CHANGELOG.md — historical mention of `docs_gathered/01_...md`
    #   as a real file path in the bootstrap snapshot. Real path,
    #   stays.
    OPERATOR_SURFACES = (
        "SKILL.md",
        "agents/quality-playbook.agent.md",
        "agents/quality-playbook-claude.agent.md",
        "references/spec_audit.md",
        "references/review_protocols.md",
    )

    def test_operator_surfaces_do_not_route_to_docs_gathered(self) -> None:
        """No operator-facing prose surface may instruct adding docs to
        `docs_gathered/`. Scans every file in OPERATOR_SURFACES."""
        offenders: list[str] = []
        for rel in self.OPERATOR_SURFACES:
            path = REPO_ROOT / rel
            if not path.is_file():
                self.fail(f"OPERATOR_SURFACES references missing file: {rel}")
            text = path.read_text(encoding="utf-8")
            if "docs_gathered" in text:
                offenders.append(rel)
        self.assertEqual(
            offenders,
            [],
            "Operator-facing surface(s) still route operators to "
            "`docs_gathered/` instead of `reference_docs/`: "
            f"{offenders}. The ingest module only reads "
            "`reference_docs/`, so any operator following these "
            "surfaces would hit the original BUG-006 failure mode.",
        )

    def test_operator_surfaces_route_to_reference_docs(self) -> None:
        """Each operator-facing surface that mentioned `docs_gathered/`
        must now mention `reference_docs/`. (SKILL.md and the agent
        files all describe a docs-discovery step; spec_audit.md and
        review_protocols.md mention the docs directory in their
        protocol prose.)"""
        for rel in self.OPERATOR_SURFACES:
            with self.subTest(file=rel):
                path = REPO_ROOT / rel
                text = path.read_text(encoding="utf-8")
                self.assertIn(
                    "reference_docs",
                    text,
                    f"{rel} must mention `reference_docs/` (BUG-006).",
                )

    def test_run_playbook_warn_messages_use_reference_docs(self) -> None:
        """The operator-facing WARN messages emitted by
        bin/run_playbook.py when no docs are present must mention
        `reference_docs/` so the operator knows where to put files
        the next time around. The legacy `docs_gathered/` may still
        appear as a parenthetical fallback — the load-bearing
        constraint is that `reference_docs/` is named."""
        runner = (REPO_ROOT / "bin" / "run_playbook.py").read_text(encoding="utf-8")
        # Count WARN messages about missing docs.
        warn_lines = [
            line for line in runner.splitlines()
            if "WARN:" in line and "code-only analysis" in line
        ]
        self.assertGreater(
            len(warn_lines), 0,
            "expected at least one operator-facing missing-docs WARN message",
        )
        for line in warn_lines:
            self.assertIn(
                "reference_docs",
                line,
                f"WARN message routes operator to wrong dir: {line!r}",
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
            "and the other operator-facing surfaces need to follow.",
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
