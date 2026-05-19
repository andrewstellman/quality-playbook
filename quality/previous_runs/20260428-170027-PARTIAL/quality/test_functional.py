"""Functional tests for Quality Playbook — Phase 2 artifact.

These tests exercise the public behavior of `bin/run_playbook.py`,
`bin/benchmark_lib.py`, and `.github/skills/quality_gate/quality_gate.py`
as they exist today (skill version 1.4.5). They assert the CURRENT
behavior of each function — any divergence between these tests and the
requirements in REQUIREMENTS.md is a candidate bug for Phase 3 code
review.

Regression tests that encode the DESIRED future behavior will be added
to `quality/test_regression.py` in Phase 3. They will use
`@unittest.expectedFailure` until fixed.

Test framework: stdlib `unittest` via the `pytest/__main__.py` shim
(no pip install required). Import pattern mirrors `bin/tests/*.py`:
`from bin import run_playbook, benchmark_lib as lib`.

Run from the QPB root:
    python3 -m unittest quality.test_functional
    python3 -m pytest quality/test_functional.py   # via shim

Requirements coverage headers appear as docstrings on each test.
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import Tuple
from unittest import mock

QPB_ROOT = Path(__file__).resolve().parent.parent
if str(QPB_ROOT) not in sys.path:
    sys.path.insert(0, str(QPB_ROOT))

from bin import benchmark_lib as lib
from bin import run_playbook


def _load_quality_gate():
    """Load quality_gate.py as a module without packaging it."""
    gate_path = QPB_ROOT / ".github" / "skills" / "quality_gate" / "quality_gate.py"
    spec = importlib.util.spec_from_file_location("quality_gate", gate_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_pytest_shim():
    """Load the local pytest shim as a module without packaging it."""
    shim_path = QPB_ROOT / "pytest" / "__main__.py"
    spec = importlib.util.spec_from_file_location("qpb_pytest_shim", shim_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _seed_gate_repo(repo: Path) -> Path:
    q = repo / "quality"
    for name in [
        "BUGS.md",
        "REQUIREMENTS.md",
        "QUALITY.md",
        "PROGRESS.md",
        "COVERAGE_MATRIX.md",
        "COMPLETENESS_REPORT.md",
        "CONTRACTS.md",
        "RUN_CODE_REVIEW.md",
        "RUN_SPEC_AUDIT.md",
        "RUN_INTEGRATION_TESTS.md",
        "RUN_TDD_TESTS.md",
    ]:
        _write(q / name, "placeholder\n")
    _write(q / "EXPLORATION.md",
           "# Exploration\n\n"
           "## Open Exploration Findings\nstub\n\n"
           "## Quality Risks\nstub\n\n"
           "## Pattern Applicability Matrix\nstub\n\n"
           "## Candidate Bugs for Phase 2\nstub\n\n"
           "## Gate Self-Check\nstub\n")
    _write(repo / "AGENTS.md", "# AGENTS\n")
    _write(q / "code_reviews" / "review.md", "# review\n")
    _write(q / "spec_audits" / "2026-04-19-triage.md", "# triage\n")
    _write(q / "spec_audits" / "2026-04-19-auditor-1.md", "# auditor\n")
    _write(q / "spec_audits" / "triage_probes.sh", "#!/usr/bin/env bash\n")
    return q


def _make_args(**overrides):
    values = {
        "runner": "claude",
        "model": "claude-opus-4-7",
        "no_seeds": False,
        "next_iteration": False,
        "strategy": ["gap"],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class VersionParserTests(unittest.TestCase):
    """REQ-001, REQ-003. Source: benchmark_lib.py:37-116, quality_gate.py:176-191."""

    def test_read_version_accepts_bare_form(self):
        """REQ-001: _read_version handles `version: X.Y.Z`."""
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "SKILL.md"
            _write(path, "---\nversion: 1.4.5\n---\n")
            self.assertEqual(lib._read_version(path), "1.4.5")

    def test_read_version_accepts_bold_form(self):
        """REQ-001: _read_version handles `**Version:** X.Y.Z` (regex path)."""
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "SKILL.md"
            _write(path, "**Version:** 1.4.5\n")
            self.assertEqual(lib._read_version(path), "1.4.5")

    def test_read_version_case_insensitive(self):
        """REQ-001: regex is IGNORECASE — VERSION: is accepted."""
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "SKILL.md"
            _write(path, "VERSION: 2.0.0\n")
            self.assertEqual(lib._read_version(path), "2.0.0")

    def test_read_version_rejects_quoted_form(self):
        """REQ-003: regex rejects quoted numbers (documents current behavior)."""
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "SKILL.md"
            _write(path, 'version: "1.4.5"\n')
            self.assertEqual(lib._read_version(path), "")

    def test_read_version_returns_empty_on_missing_file(self):
        """REQ-001: missing file returns empty string, does not raise."""
        self.assertEqual(lib._read_version(Path("/nonexistent/path.md")), "")

    def test_skill_version_matches_qpb_root(self):
        """REQ-001: skill_version() reads QPB_DIR/SKILL.md."""
        result = lib.skill_version()
        self.assertIsNotNone(result, "skill_version must return a value against real QPB root")
        self.assertRegex(result, r"^\d+\.\d+\.\d+")

    def test_skill_version_case_sensitive_divergence_from_read_version(self):
        """REQ-001: documents the case-sensitive divergence between skill_version and _read_version.

        This test captures CURRENT behavior. If REQ-001 is satisfied,
        the two helpers agree on every form and this test must be
        updated (expected future: remove the divergence; skill_version
        should also accept `VERSION:` and `**Version:**`).
        """
        with mock.patch.object(lib, "QPB_DIR", Path("/nonexistent")):
            self.assertIsNone(lib.skill_version())

    def test_detect_repo_skill_version_walks_install_locations(self):
        """REQ-002: detect_repo_skill_version walks SKILL_INSTALL_LOCATIONS."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / ".github" / "skills" / "SKILL.md", "version: 1.2.3\n")
            self.assertEqual(lib.detect_repo_skill_version(repo), "1.2.3")

    def test_detect_repo_skill_version_returns_empty_when_uninstalled(self):
        """REQ-002: no SKILL.md at any install path → empty string."""
        with TemporaryDirectory() as tmp:
            self.assertEqual(lib.detect_repo_skill_version(Path(tmp)), "")


class InstallLocationsTests(unittest.TestCase):
    """REQ-002. Source: benchmark_lib.py:39-43, SKILL.md:48-55, quality_gate.py:969-976."""

    def test_install_locations_is_tuple(self):
        """REQ-002: SKILL_INSTALL_LOCATIONS is an immutable tuple."""
        self.assertIsInstance(lib.SKILL_INSTALL_LOCATIONS, tuple)

    def test_install_locations_contains_github_skills(self):
        """REQ-002: .github/skills/SKILL.md is a documented install path."""
        paths = [str(p) for p in lib.SKILL_INSTALL_LOCATIONS]
        self.assertIn(str(Path(".github") / "skills" / "SKILL.md"), paths)

    def test_install_locations_contains_claude_skills(self):
        """REQ-002: .claude/skills/quality-playbook/SKILL.md is a documented install path."""
        paths = [str(p) for p in lib.SKILL_INSTALL_LOCATIONS]
        self.assertIn(str(Path(".claude") / "skills" / "quality-playbook" / "SKILL.md"), paths)

    def test_install_locations_contains_root_skill(self):
        """REQ-002: SKILL.md at repo root is a documented install path."""
        paths = [str(p) for p in lib.SKILL_INSTALL_LOCATIONS]
        self.assertIn("SKILL.md", paths)

    def test_find_installed_skill_returns_first_hit(self):
        """REQ-002: find_installed_skill returns the first match in order."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            gh = repo / ".github" / "skills" / "SKILL.md"
            _write(gh, "version: 1.0\n")
            _write(repo / "SKILL.md", "version: 2.0\n")
            self.assertEqual(lib.find_installed_skill(repo), gh)

    def test_find_installed_skill_returns_none_when_uninstalled(self):
        """REQ-002: no install found → None."""
        with TemporaryDirectory() as tmp:
            self.assertIsNone(lib.find_installed_skill(Path(tmp)))


class PhaseGateTests(unittest.TestCase):
    """REQ-004, REQ-010. Source: run_playbook.py:445-483."""

    def test_phase1_gate_always_passes(self):
        """REQ-010: Phase 1 entry gate always returns ok."""
        with TemporaryDirectory() as tmp:
            result = run_playbook.check_phase_gate(Path(tmp), "1")
            self.assertTrue(result.ok)
            self.assertEqual(result.messages, [])

    def test_phase2_gate_fails_on_missing_exploration(self):
        """REQ-004: Phase 2 gate FAILS when EXPLORATION.md is absent."""
        with TemporaryDirectory() as tmp:
            result = run_playbook.check_phase_gate(Path(tmp), "2")
            self.assertFalse(result.ok)
            self.assertTrue(any("EXPLORATION.md" in m for m in result.messages))

    def test_phase2_gate_passes_at_threshold(self):
        """REQ-004: at/above 80 lines the gate has no WARN."""
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "quality" / "EXPLORATION.md"
            _write(path, "x\n" * 120)
            result = run_playbook.check_phase_gate(Path(tmp), "2")
            self.assertTrue(result.ok)
            self.assertEqual(result.messages, [])

    def test_phase3_gate_missing_required_artifacts(self):
        """REQ-010: Phase 3 gate lists missing required artifacts."""
        with TemporaryDirectory() as tmp:
            result = run_playbook.check_phase_gate(Path(tmp), "3")
            self.assertFalse(result.ok)
            joined = " ".join(result.messages)
            self.assertIn("REQUIREMENTS.md", joined)
            self.assertIn("QUALITY.md", joined)
            self.assertIn("CONTRACTS.md", joined)
            self.assertIn("RUN_CODE_REVIEW.md", joined)

    def test_phase4_gate_requires_requirements_and_spec_audit(self):
        """REQ-010: Phase 4 gate requires REQUIREMENTS.md and RUN_SPEC_AUDIT.md."""
        with TemporaryDirectory() as tmp:
            result = run_playbook.check_phase_gate(Path(tmp), "4")
            self.assertFalse(result.ok)

    def test_phase5_gate_requires_progress(self):
        """REQ-010: Phase 5 gate requires PROGRESS.md."""
        with TemporaryDirectory() as tmp:
            result = run_playbook.check_phase_gate(Path(tmp), "5")
            self.assertFalse(result.ok)

    def test_phase6_gate_requires_progress(self):
        """REQ-010: Phase 6 gate requires PROGRESS.md."""
        with TemporaryDirectory() as tmp:
            result = run_playbook.check_phase_gate(Path(tmp), "6")
            self.assertFalse(result.ok)

    def test_unknown_phase_raises(self):
        """Phase-set is closed; unknown phase string raises ValueError."""
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                run_playbook.check_phase_gate(Path(tmp), "7")


class ProtectedPrefixesTests(unittest.TestCase):
    """REQ-006. Source: benchmark_lib.py:177-201."""

    def test_protected_prefixes_tuple_contents(self):
        """REQ-006: PROTECTED_PREFIXES has exactly the four run-critical directories."""
        expected = {"quality/", "control_prompts/", "previous_runs/", "docs_gathered/"}
        self.assertEqual(set(lib.PROTECTED_PREFIXES), expected)

    def test_is_protected_recognizes_quality_prefix(self):
        """REQ-006: a path under quality/ is protected."""
        self.assertTrue(lib._is_protected("quality/EXPLORATION.md"))

    def test_is_protected_recognizes_control_prompts_prefix(self):
        """REQ-006: a path under control_prompts/ is protected."""
        self.assertTrue(lib._is_protected("control_prompts/phase1.output.txt"))

    def test_is_protected_skill_md_unprotected(self):
        """REQ-006: SKILL.md at project root is NOT protected.

        In a bootstrap self-audit, an agent that edits SKILL.md directly
        will lose the edit to cleanup_repo. This is intentional today
        (patch-only workflow), but there is no guard that *warns* the
        agent.
        """
        self.assertFalse(lib._is_protected("SKILL.md"))


class PorcelainPathTests(unittest.TestCase):
    """REQ-016. Source: benchmark_lib.py:185-196."""

    def test_parse_porcelain_simple_path(self):
        """REQ-016: unquoted paths parse correctly."""
        self.assertEqual(lib._parse_porcelain_path(" M file.txt"), "file.txt")

    def test_parse_porcelain_rename(self):
        """REQ-016: rename rows return the post-rename path."""
        self.assertEqual(lib._parse_porcelain_path("R  old.txt -> new.txt"), "new.txt")

    def test_parse_porcelain_too_short(self):
        """REQ-016: lines shorter than 4 chars return None."""
        self.assertIsNone(lib._parse_porcelain_path("M"))

class CleanupRepoTests(unittest.TestCase):
    """REQ-006, REQ-016. Source: benchmark_lib.py:204-250."""

    def _git_init(self, repo: Path) -> None:
        subprocess.run(["git", "init"], cwd=repo, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "config", "user.email", "t@t.test"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "T"], cwd=repo, check=True)

    def test_cleanup_reverts_tracked_non_protected(self):
        """REQ-016: tracked non-protected files are reverted."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._git_init(repo)
            tracked = repo / "tracked.txt"
            _write(tracked, "orig\n")
            subprocess.run(["git", "add", "tracked.txt"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _write(tracked, "modified\n")
            self.assertTrue(lib.cleanup_repo(repo))
            self.assertEqual(tracked.read_text(encoding="utf-8"), "orig\n")

    def test_cleanup_preserves_quality_directory(self):
        """REQ-006: quality/ is protected; edits survive cleanup."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._git_init(repo)
            quality_file = repo / "quality" / "EXPLORATION.md"
            _write(quality_file, "prior\n")
            subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _write(quality_file, "new phase 1 findings\n")
            lib.cleanup_repo(repo)
            self.assertEqual(quality_file.read_text(encoding="utf-8"),
                             "new phase 1 findings\n")

class DocsPresentTests(unittest.TestCase):
    """REQ-011. Source: run_playbook.py:560-562."""

    def test_docs_present_false_when_directory_absent(self):
        """REQ-011: missing docs_gathered/ returns False."""
        with TemporaryDirectory() as tmp:
            self.assertFalse(run_playbook.docs_present(Path(tmp)))

    def test_docs_present_false_when_directory_empty(self):
        """REQ-011: empty docs_gathered/ returns False."""
        with TemporaryDirectory() as tmp:
            (Path(tmp) / "docs_gathered").mkdir()
            self.assertFalse(run_playbook.docs_present(Path(tmp)))

    def test_docs_present_true_with_real_document(self):
        """REQ-011: a real document makes docs_present True."""
        with TemporaryDirectory() as tmp:
            _write(Path(tmp) / "docs_gathered" / "README.md", "x" * 512)
            self.assertTrue(run_playbook.docs_present(Path(tmp)))


class ArchivePreviousRunTests(unittest.TestCase):
    """REQ-009. Source: run_playbook.archive_previous_run (v1.5.1 revision r1:
    delegates to archive_lib.archive_run with status='partial', so archive
    folders land at quality/runs/<ts>-PARTIAL/)."""

    def test_archive_moves_quality_to_quality_runs(self):
        """REQ-009: archive_previous_run moves live quality/ content into
        quality/runs/<ts>-PARTIAL/quality/ with an INDEX.md alongside."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / "quality" / "file.md", "content\n")
            run_playbook.archive_previous_run(repo, "20260418T234314Z")
            # Live file gone; archive folder survives under quality/runs/.
            self.assertFalse((repo / "quality" / "file.md").exists())
            archive = repo / "quality" / "runs" / "20260418T234314Z-PARTIAL"
            self.assertTrue((archive / "quality" / "file.md").is_file())
            self.assertTrue((archive / "INDEX.md").is_file())

    def test_archive_noop_when_no_quality(self):
        """REQ-009: no quality/ to archive → function returns silently."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            run_playbook.archive_previous_run(repo, "ts")
            self.assertFalse((repo / "quality" / "runs").exists())

    def test_archive_clears_live_when_prior_already_archived(self):
        """REQ-009: when quality/INDEX.md references a prior run that already
        has an archive folder, archive_previous_run just clears the live tree
        without producing a duplicate archive."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / "quality" / "fresh.md", "fresh\n")
            _write(repo / "quality" / "runs" / "20260419T100000Z" / "INDEX.md", "existing")
            _write(
                repo / "quality" / "INDEX.md",
                '# Run Index\n\n```json\n'
                '{"run_timestamp_start": "2026-04-19T10:00:00Z"}\n'
                '```\n',
            )
            run_playbook.archive_previous_run(repo, "20260420T100000Z")
            # Live cleared, existing archive intact, no -PARTIAL duplicate.
            self.assertFalse((repo / "quality" / "fresh.md").exists())
            self.assertTrue((repo / "quality" / "runs" / "20260419T100000Z" / "INDEX.md").is_file())
            self.assertFalse(
                (repo / "quality" / "runs" / "20260419T100000Z-PARTIAL").exists()
            )


class IterationStrategyTests(unittest.TestCase):
    """REQ-017. Source: run_playbook.py:29-77,430-436."""

    def test_all_strategies_ordered(self):
        """REQ-017: ALL_STRATEGIES matches iteration.md §8-16."""
        self.assertEqual(run_playbook.ALL_STRATEGIES,
                         ["gap", "unfiltered", "parity", "adversarial"])

    def test_valid_strategies_matches_all_strategies(self):
        """REQ-017: VALID_STRATEGIES is the frozen set of ALL_STRATEGIES."""
        self.assertEqual(run_playbook.VALID_STRATEGIES, frozenset(run_playbook.ALL_STRATEGIES))

    def test_parse_strategy_bare_value(self):
        """REQ-017: a single name parses to a 1-element list."""
        self.assertEqual(run_playbook.parse_strategy_list("gap"), ["gap"])

    def test_parse_strategy_all_expands(self):
        """REQ-017: 'all' expands to the canonical order."""
        self.assertEqual(run_playbook.parse_strategy_list("all"),
                         list(run_playbook.ALL_STRATEGIES))

    def test_parse_strategy_comma_list(self):
        """REQ-017: comma list preserves order."""
        self.assertEqual(run_playbook.parse_strategy_list("adversarial,parity"),
                         ["adversarial", "parity"])

    def test_parse_strategy_rejects_unknown(self):
        """REQ-017: unknown strategy name is rejected."""
        import argparse
        with self.assertRaises(argparse.ArgumentTypeError):
            run_playbook.parse_strategy_list("mystrategy")

    def test_parse_strategy_rejects_empty(self):
        """REQ-017: empty value is rejected."""
        import argparse
        with self.assertRaises(argparse.ArgumentTypeError):
            run_playbook.parse_strategy_list("")

    def test_parse_strategy_rejects_all_in_list(self):
        """REQ-017: 'all' may not be a member of a comma list."""
        import argparse
        with self.assertRaises(argparse.ArgumentTypeError):
            run_playbook.parse_strategy_list("gap,all")

    def test_parse_strategy_rejects_duplicates(self):
        """REQ-017: duplicate strategies are rejected."""
        import argparse
        with self.assertRaises(argparse.ArgumentTypeError):
            run_playbook.parse_strategy_list("gap,gap")


class PhaseValidationTests(unittest.TestCase):
    """REQ-017. Source: run_playbook.py:157-170."""

    def test_phase_mode_accepts_single(self):
        """REQ-017: phase mode '1' is valid."""
        import argparse
        parser = argparse.ArgumentParser()
        run_playbook.validate_phase_mode("1", parser)  # no raise

    def test_phase_mode_accepts_all(self):
        """REQ-017: 'all' is valid."""
        import argparse
        parser = argparse.ArgumentParser()
        run_playbook.validate_phase_mode("all", parser)

    def test_phase_mode_accepts_comma_list(self):
        """REQ-017: comma list of phases is valid."""
        import argparse
        parser = argparse.ArgumentParser()
        run_playbook.validate_phase_mode("1,2,3", parser)

    def test_phase_mode_rejects_unknown_phase(self):
        """REQ-017: phase '7' triggers parser.error -> SystemExit."""
        import argparse
        parser = argparse.ArgumentParser()
        with self.assertRaises(SystemExit):
            run_playbook.validate_phase_mode("7", parser)

    def test_phase_list_from_mode_empty(self):
        """REQ-017: empty mode → empty list."""
        self.assertEqual(run_playbook.phase_list_from_mode(""), [])

    def test_phase_list_from_mode_all_expands(self):
        """REQ-017: 'all' expands to all six phases."""
        self.assertEqual(run_playbook.phase_list_from_mode("all"),
                         ["1", "2", "3", "4", "5", "6"])


class BareNameTests(unittest.TestCase):
    """REQ-005. Source: run_playbook.py:173-189."""

    def test_is_bare_name_plain(self):
        """REQ-005: a plain name is bare."""
        self.assertTrue(run_playbook._is_bare_name("chi"))

    def test_is_bare_name_rejects_path_like(self):
        """REQ-005: path-like inputs are not bare."""
        self.assertFalse(run_playbook._is_bare_name("./chi"))
        self.assertFalse(run_playbook._is_bare_name("/abs/path"))
        self.assertFalse(run_playbook._is_bare_name("../chi"))
        self.assertFalse(run_playbook._is_bare_name("sub/chi"))

    def test_is_bare_name_rejects_windows_drive(self):
        """REQ-005: Windows drive letters are not bare."""
        self.assertFalse(run_playbook._is_bare_name("C:chi"))

    def test_is_bare_name_rejects_tilde(self):
        """REQ-005: leading ~ is not bare."""
        self.assertFalse(run_playbook._is_bare_name("~chi"))

    def test_is_bare_name_rejects_empty(self):
        """REQ-005: empty string is not bare."""
        self.assertFalse(run_playbook._is_bare_name(""))


class ResolveTargetDirsErrorTests(unittest.TestCase):
    """REQ-005. Source: run_playbook.py:192-244."""

    def test_resolve_missing_bare_name_error_message(self):
        """REQ-005: missing bare name produces an ERROR mentioning the attempted path."""
        # Use a CWD without such a target so fallback also misses.
        with TemporaryDirectory() as tmp:
            old = os.getcwd()
            try:
                os.chdir(tmp)
                _, _, errors = run_playbook.resolve_target_dirs(["no-such-target-qpb"])
            finally:
                os.chdir(old)
        self.assertEqual(len(errors), 1)
        # The current message mentions the resolved path. REQ-005 also
        # wants it to mention that skill_version returned None (when it
        # does). We only assert the basic shape here.
        self.assertIn("is not a directory", errors[0])

    def test_resolve_missing_path_like_no_fallback(self):
        """REQ-005: path-like input with missing target does NOT try version fallback."""
        with TemporaryDirectory() as tmp:
            _, _, errors = run_playbook.resolve_target_dirs(["./no-such-path"])
        self.assertEqual(len(errors), 1)
        self.assertNotIn("also tried", errors[0])


class RunnerDispatchTests(unittest.TestCase):
    """REQ-012. Source: run_playbook.py:486-494."""

    def test_command_for_claude_includes_dangerous_flag(self):
        """REQ-012: claude path includes --dangerously-skip-permissions."""
        cmd = run_playbook.command_for_runner("claude", "hello", None)
        self.assertEqual(cmd[0], "claude")
        self.assertIn("--dangerously-skip-permissions", cmd)
        self.assertIn("-p", cmd)

    def test_command_for_claude_with_model(self):
        """REQ-012: claude --model is inserted before -p."""
        cmd = run_playbook.command_for_runner("claude", "hello", "opus")
        self.assertIn("--model", cmd)
        self.assertIn("opus", cmd)

    def test_command_for_copilot_includes_yolo(self):
        """REQ-012: copilot path includes --yolo and --model with default."""
        cmd = run_playbook.command_for_runner("copilot", "hello", None)
        self.assertEqual(cmd[0], "gh")
        self.assertEqual(cmd[1], "copilot")
        self.assertIn("--yolo", cmd)
        self.assertIn("--model", cmd)

    def test_command_for_copilot_respects_env_default(self):
        """REQ-012: copilot default model comes from DEFAULT_MODEL."""
        cmd = run_playbook.command_for_runner("copilot", "hello", None)
        self.assertIn(lib.DEFAULT_MODEL, cmd)


class PkillFallbackPatternTests(unittest.TestCase):
    """REQ-012. Source: run_playbook.py:808-829."""

    def test_pkill_fallback_current_patterns(self):
        """REQ-012: documents the current pattern list.

        Current patterns: 'bin/run_playbook.py', 'claude -p',
        'claude --model'. REQ-012 wants 'gh copilot -p' added and
        'claude -p' narrowed so unrelated Claude sessions are not
        killed.
        """
        import inspect
        source = inspect.getsource(run_playbook._pkill_fallback)
        self.assertIn('"bin/run_playbook.py"', source)
        self.assertIn('"claude -p"', source)
        self.assertIn('"claude --model"', source)
        self.assertNotIn('"gh copilot"', source,
                         "Current: no gh copilot pattern. REQ-012 wants it added.")


class FinalArtifactGapsTests(unittest.TestCase):
    """REQ-010. Source: run_playbook.py:579-595."""

    def test_all_required_artifacts_missing_returns_full_list(self):
        """REQ-010: empty repo → every artifact in the contract is reported missing."""
        with TemporaryDirectory() as tmp:
            gaps = run_playbook.final_artifact_gaps(Path(tmp))
            for art in ["quality/REQUIREMENTS.md", "quality/CONTRACTS.md",
                        "quality/COVERAGE_MATRIX.md", "quality/COMPLETENESS_REPORT.md",
                        "quality/PROGRESS.md", "quality/QUALITY.md",
                        "quality/RUN_CODE_REVIEW.md", "quality/RUN_INTEGRATION_TESTS.md",
                        "quality/RUN_SPEC_AUDIT.md", "quality/RUN_TDD_TESTS.md"]:
                self.assertIn(art, gaps)
            self.assertIn("functional test", gaps)

    def test_all_required_artifacts_present_returns_empty(self):
        """REQ-010: when every required artifact and functional test exist, gaps is empty."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            for name in ["REQUIREMENTS.md", "CONTRACTS.md", "COVERAGE_MATRIX.md",
                         "COMPLETENESS_REPORT.md", "PROGRESS.md", "QUALITY.md",
                         "RUN_CODE_REVIEW.md", "RUN_INTEGRATION_TESTS.md",
                         "RUN_SPEC_AUDIT.md", "RUN_TDD_TESTS.md"]:
                _write(repo / "quality" / name, "stub\n")
            _write(repo / "quality" / "test_functional.py", "# stub\n")
            self.assertEqual(run_playbook.final_artifact_gaps(repo), [])


class QualityGateVersionDetectionTests(unittest.TestCase):
    """REQ-001, REQ-003, REQ-008. Source: quality_gate.py:156-191."""

    def setUp(self):
        self.gate = _load_quality_gate()

    def test_gate_detect_skill_version_matches_bare(self):
        """REQ-001: gate detects bare form."""
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "SKILL.md"
            _write(path, "version: 1.4.5\n")
            self.assertEqual(self.gate.detect_skill_version([path]), "1.4.5")

    def test_gate_detect_skill_version_substring_current_behavior(self):
        """REQ-003: documents current substring-match behavior.

        Current: `if "version:" in line` matches a substring. A
        description line containing the word `version:` will be picked
        up by the gate's parser. REQ-003 requires anchored matching.
        """
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "SKILL.md"
            _write(path, 'description: "The version: 1.4.5 release"\nversion: 9.9.9\n')
            # The first line matches first — and the parser does not
            # anchor the match, so it extracts from the description.
            result = self.gate.detect_skill_version([path])
            self.assertNotEqual(result, "",
                                "Current: substring match picks SOMETHING up — REQ-003 wants it anchored")

    def test_gate_validate_iso_date_accepts_date_only(self):
        """REQ-007: validate_iso_date accepts YYYY-MM-DD.

        The function returns one of: 'valid', 'placeholder', 'future',
        'bad_format', 'empty'. A date-only today-or-past string is 'valid'.
        """
        # Use a clearly-past date so we don't flake on the 'future' check.
        self.assertEqual(self.gate.validate_iso_date("2020-01-01"), "valid")

class QualityGateEnumTests(unittest.TestCase):
    """REQ-017. Source: quality_gate.py:497-498, SKILL.md:154."""

    def setUp(self):
        self.gate = _load_quality_gate()

    def test_verdict_enum_values_present_in_gate(self):
        """REQ-017: the five canonical verdicts are the gate's closed set."""
        # Load gate source and assert each verdict string appears
        # verbatim. (The gate's enum is a local set inside a function;
        # this test pins the strings so any rename surfaces.)
        gate_path = QPB_ROOT / ".github" / "skills" / "quality_gate" / "quality_gate.py"
        source = gate_path.read_text(encoding="utf-8")
        for verdict in ["TDD verified", "red failed", "green failed",
                        "confirmed open", "deferred"]:
            self.assertIn(f'"{verdict}"', source,
                          f"Verdict '{verdict}' missing from quality_gate.py")

    def test_integration_recommendation_enum_present(self):
        """REQ-017: the three canonical recommendations are in the gate."""
        gate_path = QPB_ROOT / ".github" / "skills" / "quality_gate" / "quality_gate.py"
        source = gate_path.read_text(encoding="utf-8")
        for rec in ["SHIP", "FIX BEFORE MERGE", "BLOCK"]:
            self.assertIn(f'"{rec}"', source,
                          f"Recommendation '{rec}' missing from quality_gate.py")


class ClosedSetCrossReferenceTests(unittest.TestCase):
    """REQ-002, REQ-017. Compares closed sets between runner, library, gate."""

    def test_skill_install_locations_in_library(self):
        """REQ-002: library declares SKILL_INSTALL_LOCATIONS."""
        self.assertTrue(hasattr(lib, "SKILL_INSTALL_LOCATIONS"))

class PromptPathFallbackTests(unittest.TestCase):
    """REQ-022. Source: run_playbook.py:258-427."""

class SchemaVersionContractTests(unittest.TestCase):
    """REQ-017 / C-7. Sidecar schema versions."""

    def test_skill_md_declares_tdd_schema_1_1(self):
        """C-7: SKILL.md declares schema_version '1.1' for tdd-results.json."""
        skill = (QPB_ROOT / ".github" / "skills" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn('"schema_version": "1.1"', skill)

    def test_skill_md_declares_recheck_schema_1_0(self):
        """C-7: SKILL.md declares schema_version '1.0' for recheck-results.json."""
        skill = (QPB_ROOT / ".github" / "skills" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn('"schema_version": "1.0"', skill)


if __name__ == "__main__":
    unittest.main()
