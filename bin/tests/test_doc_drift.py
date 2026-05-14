"""Tests for documentation/help-text drift across the QPB repo.

Regression coverage for v1.5.4 self-audit BUG-005, BUG-006, BUG-007 —
all three are help-text or operator-guidance drift where prose tells
the operator to use one path/invocation but the implementation uses
another. Bundled here because they share a shape: scan a doc/help
string for the wrong token and assert it isn't present.

- BUG-005: pre-v1.5.7, README.md documented `python3 bin/run_playbook.py`
  but the runner exited EX_USAGE=64 on script-style invocation. v1.5.7
  fix F-5a makes script-style work via sys.path injection, so the
  ReadmeRunPlaybookInvocationTests check is inverted: at least one
  module-form example must be documented, and both forms are valid.
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
    """BUG-005 (v1.5.7 fix F-5a update + instruction 031 Phase D consensus
    fixup): both `python -m bin.run_playbook` and `python /path/to/QPB/
    bin/run_playbook.py` are valid invocation forms after F-5a. The
    pre-v1.5.7 ban on script-style invocations is inverted: at least one
    module-form example must be documented (since that's the canonical
    form), AND operator-facing surfaces must NOT claim script-style is
    rejected with `EX_USAGE=64` (the v1.5.4 codex-prevention guard the
    F-5a refactor removed).

    Phase D consensus fixup widened the doc-drift coverage from
    README-only to README + SKILL.md, so stale "EX_USAGE=64" / "never
    invoke script-style" prose in either surface trips the test."""

    # Operator-facing surfaces that document runner invocation.
    # v1.5.7 instruction 032 NCF-12: TOOLKIT.md added — round-2 Council
    # found stale script-ban prose there that Phase D's cleanup missed.
    INVOCATION_SURFACES = (
        "README.md",
        "SKILL.md",
        "ai_context/TOOLKIT.md",
    )

    # Hand-enumerated present-tense rejection phrases. v1.5.7 instruction
    # 032 NCF-12/NCF-13 widened this to also include the
    # _STALE_GUARD_VERB_PATTERN regex below — the hand list catches
    # imperatives ("Never invoke") that the verb regex doesn't, and the
    # regex catches "rejects with" / "refuses with" variants that the
    # hand list missed. Both run.
    #
    # v1.5.7 instruction 033 Halt-4: the match loop now uses
    # `phrase.lower() in text.lower()` so sentence-initial capital-letter
    # variants ("Always invoke it...") match the same phrase entry as
    # mid-sentence variants ("always invoke it..."). Pre-Halt-4 the
    # SKILL.md:96 "Always invoke" prose evaded detection because the
    # phrase list had only the lowercase form and `in` is case-sensitive.
    # All entries are normalized to lowercase here.
    STALE_GUARD_PHRASES = (
        "never invoke it script-style",
        "always invoke it as a package module",
        "always invoke it as a python module",
    )

    # v1.5.7 instruction 032 NCF-13 (widening): regex over the verb
    # family that present-tense rejection prose uses around the
    # EX_USAGE=64 token, allowing intervening text within a sentence
    # window. Catches:
    #   - "exits with EX_USAGE=64"
    #   - "rejects `python3 .../run_playbook.py` with `EX_USAGE=64`"
    #   - "rejects with EX_USAGE=64"
    #   - "refuses with EX_USAGE=64"
    # Past-tense forms ("exited", "rejected", "refused") have an
    # "ed" suffix the verb-stem `\b` boundary explicitly excludes, so
    # legitimate historical retrospectives remain allowed.
    # Sentence-window is "up to 80 same-line characters" between the
    # verb and EX_USAGE=64 — long enough to absorb a single intervening
    # backtick-quoted path (which may contain `.py`), short enough that
    # cross-paragraph false positives are extremely unlikely. `.` in
    # the regex doesn't match `\n` by default, so the window stays on
    # a single line.
    _STALE_GUARD_VERB_PATTERN = re.compile(
        r"(reject|exit|refuse)s\b.{0,80}EX_USAGE=64",
        re.IGNORECASE,
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

    def test_no_operator_surface_claims_script_style_is_rejected(self) -> None:
        """v1.5.7 instruction 031 Phase D + instruction 032 NCF-12/NCF-13.
        No operator-facing surface may claim script-style invocation is
        rejected by the runtime guard — the v1.5.4 EX_USAGE=64 guard was
        removed in F-5a (commit 95f45eb) when sys.path injection made
        script-style work natively.

        Two detection paths run together (instruction 032 NCF-13
        widening):
        - Hand-enumerated `STALE_GUARD_PHRASES` catches imperatives
          like "Never invoke it script-style".
        - `_STALE_GUARD_VERB_PATTERN` regex catches present-tense
          rejection-verb-with-EX_USAGE=64 patterns ("rejects with",
          "exits with", "refuses with"). Past-tense forms ("rejected",
          "exited") are excluded by the verb-stem boundary, so
          legitimate historical retrospectives remain allowed.

        TOOLKIT.md was added to `INVOCATION_SURFACES` because the
        Round-2 Council found stale prose there that Phase D's
        README-only scan missed."""
        offenders: list[tuple[str, str]] = []
        for rel in self.INVOCATION_SURFACES:
            path = REPO_ROOT / rel
            self.assertTrue(
                path.is_file(),
                f"INVOCATION_SURFACES references missing file: {rel}",
            )
            text = path.read_text(encoding="utf-8")
            # v1.5.7 instruction 033 Halt-4: case-insensitive match
            # so sentence-initial capitalized variants ("Always invoke
            # it...") match the lowercase-normalized phrase entries.
            # Mirrors the placeholder-phrase handling in
            # `quality_gate.py::_VERDICT_PLACEHOLDER_PHRASES`.
            lowered = text.lower()
            for phrase in self.STALE_GUARD_PHRASES:
                if phrase in lowered:
                    offenders.append((rel, phrase))
            for match in self._STALE_GUARD_VERB_PATTERN.finditer(text):
                offenders.append((rel, match.group(0)))
        self.assertEqual(
            offenders,
            [],
            "Operator-facing surface(s) still claim script-style "
            "invocation is rejected by the v1.5.4 EX_USAGE=64 guard. "
            "That guard was removed in v1.5.7 fix F-5a (commit "
            "95f45eb); both `python3 -m bin.run_playbook` and "
            "`python3 /path/to/QPB/bin/run_playbook.py` now work. "
            f"Stale prose hits: {offenders}",
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


class SixInstallLayoutsConsistencyTests(unittest.TestCase):
    """v1.5.7 BUG-007: operator-facing surfaces must consistently name
    the six canonical install layouts that SKILL_FALLBACK_GUIDE
    documents. Pre-fix, surfaces variably listed 2, 3, or 4 layouts —
    operators following one surface would miss layouts another surface
    documents, leading to "I followed the docs but the skill isn't
    finding itself" failures.

    The 5 surfaces in scope (per instruction 034 BUG-007 brief):
    - SKILL.md: fallback list under "Locating reference files"
    - ai_context/TOOLKIT.md: SKILL_FALLBACK_GUIDE example block
    - references/verification.md: SKILL.md-locator prose in Benchmark 26
    - references/review_protocols.md: example gh copilot invocation
    - references/challenge_gate.md: example challenge-gate prompt
    """

    # The six canonical install layouts the v1.5.6+ resolver supports,
    # in the same order as SKILL_FALLBACK_GUIDE / SKILL_INSTALL_LOCATIONS.
    SIX_LAYOUTS = (
        ".claude/skills/quality-playbook/",
        ".github/skills/",
        ".cursor/skills/quality-playbook/",
        ".continue/skills/quality-playbook/",
        ".github/skills/quality-playbook/",
    )
    # Note: the root SKILL.md location (`SKILL.md` at target root) is
    # ALSO one of the six but it's the bare-name string — checking for
    # it as a substring would over-match unrelated mentions of
    # "SKILL.md" in prose. The 5 nested forms above are unambiguous
    # substrings to test on each surface.

    OPERATOR_SURFACES = (
        "SKILL.md",
        "ai_context/TOOLKIT.md",
        "references/verification.md",
        "references/review_protocols.md",
        "references/challenge_gate.md",
    )

    def test_every_surface_names_all_five_nested_layouts(self) -> None:
        """Each of the 5 operator-facing surfaces must mention each of
        the 5 nested install-layout substrings somewhere in the file.
        The root `SKILL.md` location is the 6th canonical layout but
        is not substring-checked here (see SIX_LAYOUTS comment)."""
        misses: list[tuple[str, str]] = []
        for rel in self.OPERATOR_SURFACES:
            path = REPO_ROOT / rel
            self.assertTrue(
                path.is_file(),
                f"OPERATOR_SURFACES references missing file: {rel}",
            )
            text = path.read_text(encoding="utf-8")
            for layout in self.SIX_LAYOUTS:
                if layout not in text:
                    misses.append((rel, layout))
        self.assertEqual(
            misses,
            [],
            "Operator-facing surface(s) missing one or more of the 5 "
            "nested canonical install-layout substrings (the 6th is "
            "the bare-root SKILL.md location which we don't substring-"
            "check). Pre-BUG-007 the surfaces variably listed 2-4 of "
            f"6; the fix made all 5 surfaces enumerate all 5 nested "
            f"forms (plus the root). Missing: {misses}",
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
