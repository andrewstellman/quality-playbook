"""Regression tests for Quality Playbook v1.4.5 — Phase 3 TDD Red Phase.

Every test in this file is decorated with @unittest.expectedFailure.
Each test encodes the DESIRED future behavior for a confirmed bug. All
tests must fail (xfail) against the current codebase. When a bug is
fixed, the decorator is removed and the test becomes a passing green test.

Import pattern mirrors test_functional.py:
    from bin import run_playbook
    from bin import benchmark_lib as lib

For quality_gate: use importlib.util.spec_from_file_location.

Run from the QPB root:
    python3 -m unittest quality.test_regression -v
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
from unittest import mock

QPB_ROOT = Path(__file__).resolve().parent.parent
if str(QPB_ROOT) not in sys.path:
    sys.path.insert(0, str(QPB_ROOT))

from bin import benchmark_lib as lib
from bin import run_playbook

_GATE_PATH = QPB_ROOT / ".github" / "skills" / "quality_gate" / "quality_gate.py"


def _load_quality_gate():
    """Load quality_gate.py as a module without packaging it."""
    spec = importlib.util.spec_from_file_location("quality_gate", _GATE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _load_pytest_shim():
    """Load the local pytest shim without packaging it."""
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


class RegressionTests(unittest.TestCase):
    """Phase 3 TDD red-phase regression tests.

    All tests are @unittest.expectedFailure — they encode desired future
    behavior that the current code does not yet satisfy. When each bug
    is fixed, remove the decorator and the test becomes a green test.
    """

    # ------------------------------------------------------------------ #
    # BUG-001 / REQ-001: skill_version() must accept bold Version form
    # ------------------------------------------------------------------ #

    def test_reg_cb1_version_parser_divergence(self):
        """BUG-001 / REQ-001: skill_version() must return "1.4.5" for SKILL.md
        with `**Version:** 1.4.5` bold form.

        Source: bin/benchmark_lib.py:106 — startswith("version:") rejects bold form.
        Current: returns None. Desired: returns "1.4.5".
        """
        with TemporaryDirectory() as tmp:
            skill_path = Path(tmp) / "SKILL.md"
            _write(skill_path, "---\n**Version:** 1.4.5\n---\n# Quality Playbook\n")
            with mock.patch.object(lib, "QPB_DIR", Path(tmp)):
                result = lib.skill_version()
        # Desired: bold form is accepted, version returned.
        self.assertEqual(result, "1.4.5",
                         "skill_version() must return '1.4.5' for bold **Version:** form")

    # ------------------------------------------------------------------ #
    # BUG-002 / REQ-002: SKILL_INSTALL_LOCATIONS must have all 4 paths
    # ------------------------------------------------------------------ #

    def test_reg_cb2_missing_fourth_install_path(self):
        """BUG-002 / REQ-002: SKILL_INSTALL_LOCATIONS must contain all 4 paths
        documented in SKILL.md §Locating reference files (lines 48-55).

        Source: bin/benchmark_lib.py:39-43 — 3-tuple; missing fourth entry.
        Current: 3 entries. Desired: 4 entries including quality-playbook variant.
        """
        paths_str = [str(p) for p in lib.SKILL_INSTALL_LOCATIONS]
        fourth_path = str(Path(".github") / "skills" / "quality-playbook" / "SKILL.md")
        self.assertIn(fourth_path, paths_str,
                      f"SKILL_INSTALL_LOCATIONS must include {fourth_path!r} (the fourth documented install path)")

    # ------------------------------------------------------------------ #
    # BUG-013 / REQ-003: detect_skill_version must reject substring matches
    # ------------------------------------------------------------------ #

    def test_reg_version_parser_substring_reject(self):
        """BUG-013 / REQ-003: detect_skill_version must not match version: inside
        a description field.

        Source: quality_gate.py:182-187 — `if "version:" in line` matches substring.
        Current: picks up description line. Desired: only anchored `version:` at
        line start.
        """
        qg = _load_quality_gate()
        with TemporaryDirectory() as tmp:
            skill_path = Path(tmp) / "SKILL.md"
            # description line comes first; real version line follows
            _write(skill_path,
                   'description: "The version: 1.4.5 release of the skill"\n'
                   'version: 9.9.9\n')
            result = qg.detect_skill_version([skill_path])
        # Desired: anchored match skips description, returns "9.9.9"
        self.assertEqual(result, "9.9.9",
                         "detect_skill_version must skip description fields and return version from anchored line")

    # ------------------------------------------------------------------ #
    # BUG-003 / REQ-004: Phase 2 gate must FAIL at 119 lines
    # ------------------------------------------------------------------ #

    def test_reg_cb3_line_count_threshold_drift(self):
        """BUG-003 / REQ-004: check_phase_gate("2") must return ok=False for a
        119-line EXPLORATION.md. SKILL.md:906 requires 120 as the FAIL threshold.

        Source: run_playbook.py:455-457 — threshold is 80 with WARN, not 120 with FAIL.
        Current: ok=True (WARN only). Desired: ok=False.
        """
        with TemporaryDirectory() as tmp:
            quality = Path(tmp) / "quality"
            exploration = quality / "EXPLORATION.md"
            # Write exactly 119 lines — one below the required 120
            _write(exploration, "line content\n" * 119)
            result = run_playbook.check_phase_gate(Path(tmp), "2")
        # Desired: gate fails at 119 lines
        self.assertFalse(result.ok,
                         "check_phase_gate('2') must return ok=False for 119-line EXPLORATION.md")
        self.assertTrue(any("FAIL" in m for m in result.messages),
                        "Gate message must say FAIL not WARN")

    # ------------------------------------------------------------------ #
    # REQ-005: version-append fallback diagnostic
    # ------------------------------------------------------------------ #

    @unittest.expectedFailure
    def test_reg_fallback_skipped_diagnostic(self):
        """REQ-005: When skill_version returns None and bare name fails, the error
        message must mention "skill_version" or equivalent diagnostic.

        Source: run_playbook.py:234 — emits generic "is not a directory" message.
        Current: no mention of skill_version or parser failure. Desired: diagnostic
        in error message.
        """
        with TemporaryDirectory() as tmp:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                # QPB_DIR has no SKILL.md → skill_version() returns None
                with mock.patch.object(lib, "QPB_DIR", Path(tmp)):
                    _, _, errors = run_playbook.resolve_target_dirs(["no-such-target-qpb"])
            finally:
                os.chdir(old_cwd)
        self.assertEqual(len(errors), 1)
        # Desired: error mentions skill_version returned None
        self.assertTrue(
            any("skill_version" in e.lower() or "no version" in e.lower()
                for e in errors),
            f"Error must mention skill_version diagnostic; got: {errors}"
        )

    # ------------------------------------------------------------------ #
    # BUG-005 / REQ-006: _is_protected must return True for AGENTS.md
    # ------------------------------------------------------------------ #

    def test_reg_cb5_agents_md_cleanup_reversion(self):
        """BUG-005 / REQ-006: lib._is_protected("AGENTS.md") must return True.
        AGENTS.md is a required artifact that cleanup_repo must not revert.

        Source: bin/benchmark_lib.py:177-182 — AGENTS.md not in PROTECTED_PREFIXES.
        Current: returns False. Desired: returns True.
        """
        result = lib._is_protected("AGENTS.md")
        self.assertTrue(result,
                        "lib._is_protected('AGENTS.md') must return True; AGENTS.md is a required artifact")

    # ------------------------------------------------------------------ #
    # BUG-014 / REQ-007: validate_iso_date must accept ISO 8601 datetimes
    # ------------------------------------------------------------------ #

    def test_reg_iso_datetime_grammar(self):
        """BUG-014 / REQ-007: validate_iso_date("2026-04-18T23:43:14Z") must
        return "valid". Run-metadata start_time uses datetime form.

        Source: quality_gate.py:156-173 — regex \\d{4}-\\d{2}-\\d{2} rejects datetime.
        Current: returns "bad_format". Desired: returns "valid".
        """
        qg = _load_quality_gate()
        result = qg.validate_iso_date("2026-04-18T23:43:14Z")
        self.assertEqual(result, "valid",
                         "validate_iso_date must accept ISO 8601 datetime form '2026-04-18T23:43:14Z'")

    # ------------------------------------------------------------------ #
    # BUG-010 / REQ-008: quality_gate must have check_run_metadata attribute
    # ------------------------------------------------------------------ #

    def test_reg_cb10_run_metadata_ungated(self):
        """BUG-010 / REQ-008: quality_gate must have attribute check_run_metadata.
        Run-metadata JSON must be validated by the gate.

        Source: quality_gate.py:1027-1053 — check_run_metadata function does not exist.
        Current: hasattr → False. Desired: function exists and check_repo calls it.
        """
        qg = _load_quality_gate()
        self.assertTrue(
            hasattr(qg, "check_run_metadata"),
            "quality_gate must expose check_run_metadata function (currently missing)"
        )

    # ------------------------------------------------------------------ #
    # BUG-004 / REQ-009: archive must preserve control_prompts/
    # ------------------------------------------------------------------ #

    def test_reg_cb4_archive_not_atomic(self):
        """BUG-004 / REQ-009: After archive_previous_run, control_prompts/ must
        exist in the archive directory.

        Historical source: run_playbook.py — shutil.rmtree(control_prompts_dir)
        used to delete control_prompts/ from repo root instead of archiving it.
        v1.5.1 update: control_prompts/ now lives under quality/, so the
        quality/ copytree captures it naturally into the archive subtree at
        quality/runs/<ts>/quality/control_prompts/.
        """
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / "quality" / "file.md", "q\n")
            _write(repo / "quality" / "control_prompts" / "phase1.output.txt", "diagnostic data\n")
            run_playbook.archive_previous_run(repo, "20260418T234314Z")
            archived_cp = (
                repo / "quality" / "runs" / "20260418T234314Z-PARTIAL"
                / "quality" / "control_prompts"
            )
            archived_file = archived_cp / "phase1.output.txt"
            self.assertTrue(
                archived_cp.is_dir(),
                "control_prompts/ must be archived to "
                "quality/runs/<ts>-PARTIAL/quality/control_prompts/",
            )
            self.assertTrue(
                archived_file.is_file(),
                "Archived control_prompts/ must contain the original files",
            )

    # ------------------------------------------------------------------ #
    # BUG-006 / REQ-010: Phase 3 gate must fail without COVERAGE_MATRIX.md
    # ------------------------------------------------------------------ #

    def test_reg_cb6_phase3_gate_incomplete(self):
        """BUG-006 / REQ-010: check_phase_gate("3") must fail when
        COVERAGE_MATRIX.md is absent. Only the currently-checked 4 files are
        present; 5 required Phase 2 artifacts are missing.

        Source: run_playbook.py:459-463 — only 4 files checked.
        Current: ok=True with only 4 files. Desired: ok=False (missing 5 artifacts).
        """
        with TemporaryDirectory() as tmp:
            quality = Path(tmp) / "quality"
            # Write only the 4 currently-checked files
            for name in ["REQUIREMENTS.md", "QUALITY.md", "CONTRACTS.md", "RUN_CODE_REVIEW.md"]:
                _write(quality / name, "stub\n")
            # COVERAGE_MATRIX.md, COMPLETENESS_REPORT.md, RUN_INTEGRATION_TESTS.md,
            # RUN_SPEC_AUDIT.md, RUN_TDD_TESTS.md are intentionally absent.
            result = run_playbook.check_phase_gate(Path(tmp), "3")
        self.assertFalse(result.ok,
                         "check_phase_gate('3') must fail when COVERAGE_MATRIX.md and others are absent")

    # ------------------------------------------------------------------ #
    # BUG-007 / REQ-011: docs_present must reject .DS_Store-only directory
    # ------------------------------------------------------------------ #

    def test_reg_cb7_docs_present_noise(self):
        """BUG-007 / REQ-011: docs_present must return False for a directory
        containing only ".DS_Store".

        Source: run_playbook.py:560-562 — any(iterdir()) is True for .DS_Store.
        Current: returns True. Desired: returns False.
        """
        with TemporaryDirectory() as tmp:
            docs_dir = Path(tmp) / "docs_gathered"
            docs_dir.mkdir()
            # Write a .DS_Store file — macOS filesystem noise
            _write(docs_dir / ".DS_Store", "bplist00\n")
            result = run_playbook.docs_present(Path(tmp))
        self.assertFalse(result,
                         "docs_present must return False for a docs_gathered/ containing only .DS_Store")

    # ------------------------------------------------------------------ #
    # BUG-009 / REQ-012: _pkill_fallback patterns must include gh copilot
    # ------------------------------------------------------------------ #

    def test_reg_cb9_pkill_misses_copilot(self):
        """BUG-009 / REQ-012: _pkill_fallback patterns must include "gh copilot -p".
        Copilot workers are orphaned after parent crash without this pattern.

        Source: run_playbook.py:808-829 — patterns list has 3 entries, no gh copilot.
        Current: "gh copilot" pattern absent. Desired: pattern present in pkill calls.
        """
        pkill_calls = []

        def mock_subprocess_run(cmd, **kwargs):
            if cmd and cmd[0] == "pkill":
                pkill_calls.append(cmd)
            result = mock.MagicMock()
            result.returncode = 1
            return result

        with mock.patch("subprocess.run", side_effect=mock_subprocess_run):
            run_playbook._pkill_fallback()

        # Extract the -f pattern arguments from each pkill call
        patterns_used = []
        for call in pkill_calls:
            if "-f" in call:
                idx = call.index("-f")
                if idx + 1 < len(call):
                    patterns_used.append(call[idx + 1])

        self.assertTrue(
            any("gh copilot" in p for p in patterns_used),
            f"_pkill_fallback must include 'gh copilot' in pkill patterns; got: {patterns_used}"
        )

    # ------------------------------------------------------------------ #
    # BUG-011 / REQ-013: gate must FAIL when EXPLORATION.md lacks ## Quality Risks
    # ------------------------------------------------------------------ #

    def test_reg_cb11_exploration_structure_ungated(self):
        """BUG-011 / REQ-013: quality_gate must FAIL when EXPLORATION.md lacks
        required section "## Quality Risks".

        Source: quality_gate.py:310-313 — only checks existence, not structure.
        Current: passes when EXPLORATION.md exists but lacks required sections.
        Desired: FAIL count > 0 for missing section.
        """
        qg = _load_quality_gate()
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            quality = repo / "quality"

            # Write a minimal EXPLORATION.md without ## Quality Risks
            _write(quality / "EXPLORATION.md",
                   "# Exploration\n\n"
                   "## Open Exploration Findings\nSome findings.\n\n"
                   "## Pattern Applicability Matrix\nNA\n\n"
                   "## Candidate Bugs for Phase 2\nNone.\n\n"
                   "## Gate Self-Check\nOK\n")

            # Write other required artifacts to focus the test on structure
            for name in ["REQUIREMENTS.md", "QUALITY.md", "CONTRACTS.md",
                         "RUN_CODE_REVIEW.md", "COVERAGE_MATRIX.md",
                         "COMPLETENESS_REPORT.md", "RUN_INTEGRATION_TESTS.md",
                         "RUN_SPEC_AUDIT.md", "RUN_TDD_TESTS.md", "BUGS.md",
                         "PROGRESS.md", "test_functional.py"]:
                _write(quality / name, "stub\n")

            qg._reset_counters()
            qg.check_file_existence(repo, quality, "strict")

        self.assertGreater(
            qg.FAIL, 0,
            "check_file_existence must FAIL when EXPLORATION.md is missing ## Quality Risks"
        )

    # ------------------------------------------------------------------ #
    # BUG-008 / REQ-014: Suggestion must NOT print after failure
    # ------------------------------------------------------------------ #

    def test_reg_cb8_suggest_after_failure(self):
        """BUG-008 / REQ-014: When run fails (failures > 0), output must NOT
        contain the normal iteration suggestion. A failure-specific message
        should appear instead.

        Source: run_playbook.py:930-946 — print_suggested_next_command called
        unconditionally regardless of failures.
        Current: suggestion always printed. Desired: suppressed on failure.
        """
        # We test the conditional logic by examining the print_suggested_next_command
        # signature — it currently has no failures parameter.
        import inspect
        sig = inspect.signature(run_playbook.print_suggested_next_command)
        params = list(sig.parameters.keys())
        # Desired: function has a failures_occurred or similar parameter
        self.assertTrue(
            any("fail" in p.lower() for p in params),
            f"print_suggested_next_command must accept a failures parameter; "
            f"current signature: {params}. The function cannot suppress suggestion on failure."
        )

    # ------------------------------------------------------------------ #
    # BUG-012 / REQ-015: Zero-bug sentinel must not match free prose "zero"
    # ------------------------------------------------------------------ #

    def test_reg_cb12_zero_bug_loose_regex(self):
        """BUG-012 / REQ-015: A BUGS.md with prose "the zero analysis shows no
        problems" and no BUG headings must NOT pass the zero-bug sentinel.

        Source: quality_gate.py:397 — re.search("zero") matches anywhere in prose.
        Current: zero-bug path passes (sentinel matched). Desired: structural check
        only passes when an anchored zero-bug heading is present.
        """
        qg = _load_quality_gate()

        bugs_content = (
            "# Bugs\n\n"
            "The zero analysis of this project shows no obvious problems.\n"
            "We found zero issues during review.\n"
        )

        with TemporaryDirectory() as tmp:
            quality = Path(tmp) / "quality"
            quality.mkdir(parents=True, exist_ok=True)
            _write(quality / "BUGS.md", bugs_content)

            qg._reset_counters()
            captured = io.StringIO()
            with mock.patch("sys.stdout", captured):
                qg.check_bugs_heading(quality)
            output = captured.getvalue()

        self.assertNotIn(
            "Zero-bug run", output,
            "Zero-bug sentinel must not match free prose 'zero'; "
            "anchored '## No confirmed bugs' heading is required"
        )
        self.assertIn(
            "No ### BUG-NNN headings found", output,
            "Loose-prose 'zero' should fall through to the WARN branch"
        )

    # ------------------------------------------------------------------ #
    # BUG-015 / REQ-016: _parse_porcelain_path must strip surrounding quotes
    # ------------------------------------------------------------------ #

    def test_reg_porcelain_quoted_paths(self):
        """BUG-015 / REQ-016: _parse_porcelain_path(' M "file with space.txt"')
        must return 'file with space.txt' (no surrounding quotes).

        Source: bin/benchmark_lib.py:185-196 — returns rest.strip() without
        removing Git's surrounding double-quotes.
        Current: returns '"file with space.txt"' with quotes.
        Desired: returns 'file with space.txt' without quotes.
        """
        result = lib._parse_porcelain_path(' M "file with space.txt"')
        self.assertEqual(
            result, "file with space.txt",
            f"_parse_porcelain_path must strip surrounding quotes; got: {result!r}"
        )

    # ------------------------------------------------------------------ #
    # BUG-002 / REQ-017: All 4 install paths must be in SKILL_INSTALL_LOCATIONS
    # ------------------------------------------------------------------ #

    def test_reg_closed_set_drift(self):
        """BUG-002 / REQ-017: All 4 install paths documented in SKILL.md must
        be present in lib.SKILL_INSTALL_LOCATIONS.

        Source: bin/benchmark_lib.py:39-43 — 3-tuple missing 4th path.
        Current: fourth path absent. Desired: all 4 paths present.
        """
        fourth_path = ".github/skills/quality-playbook/SKILL.md"
        present = any(
            fourth_path in str(loc)
            for loc in lib.SKILL_INSTALL_LOCATIONS
        )
        self.assertTrue(
            present,
            f"lib.SKILL_INSTALL_LOCATIONS must include path containing "
            f"'.github/skills/quality-playbook/SKILL.md'; "
            f"current paths: {[str(p) for p in lib.SKILL_INSTALL_LOCATIONS]}"
        )


class TestSpecAuditRegressions(unittest.TestCase):
    """Regression tests for Phase 4 spec-audit confirmed bugs."""

    # ------------------------------------------------------------------ #
    # BUG-016 / REQ-010: Phase 5 gate must enforce Phase 4 completion
    # ------------------------------------------------------------------ #

    def test_reg_sa16_phase5_gate_missing_triage(self):
        """BUG-016 / REQ-010: check_phase_gate("5") must return ok=False when
        spec_audits/ directory exists but contains no triage file.

        SKILL.md:1663-1667 mandates a hard-stop if spec_audits/ lacks a triage
        file. Current code returns ok=True in this scenario.

        Source: bin/run_playbook.py:473-478
        Current: ok=True even with empty spec_audits/. Desired: ok=False.
        """
        with TemporaryDirectory() as td:
            repo = Path(td)
            q = repo / "quality"
            q.mkdir()
            (q / "PROGRESS.md").write_text(
                "- [x] Phase 1\n- [x] Phase 2\n- [x] Phase 3\n- [ ] Phase 4\n",
                encoding="utf-8"
            )
            (q / "BUGS.md").write_text("# Bugs\n### BUG-001 — some bug\n", encoding="utf-8")
            (q / "spec_audits").mkdir()  # exists but empty — no triage file
            result = run_playbook.check_phase_gate(repo, "5")
            self.assertFalse(
                result.ok,
                "Phase 5 gate must return ok=False when spec_audits/ has no triage file; "
                f"got ok={result.ok}, messages={result.messages}"
            )

    def test_reg_sa16_phase5_gate_missing_phase4_checkbox(self):
        """BUG-016 / REQ-010: check_phase_gate("5") must return ok=False when
        PROGRESS.md Phase 4 line is not marked [x].

        SKILL.md:1667 requires Phase 4 '[x]' in PROGRESS.md before Phase 5.
        Current code never checks this checkbox.

        Source: bin/run_playbook.py:473-478
        Current: ok=True even when Phase 4 not marked. Desired: ok=False.
        """
        with TemporaryDirectory() as td:
            repo = Path(td)
            q = repo / "quality"
            q.mkdir()
            (q / "PROGRESS.md").write_text(
                "- [x] Phase 1\n- [x] Phase 2\n- [x] Phase 3\n- [ ] Phase 4\n",
                encoding="utf-8"
            )
            sa = q / "spec_audits"
            sa.mkdir()
            (sa / "2026-04-18-triage.md").write_text("# Triage\n", encoding="utf-8")
            (sa / "2026-04-18-auditor-1.md").write_text("# Auditor 1\n", encoding="utf-8")
            result = run_playbook.check_phase_gate(repo, "5")
            self.assertFalse(
                result.ok,
                "Phase 5 gate must return ok=False when PROGRESS.md Phase 4 not [x]; "
                f"got ok={result.ok}, messages={result.messages}"
            )

    def test_reg_sa16_phase5_gate_passes_when_complete(self):
        """BUG-016 / REQ-010: check_phase_gate("5") must return ok=True when all
        Phase 4 completion conditions are satisfied.

        This is the positive guard — the BUG-016 fix must not over-restrict.
        All three required conditions met → gate must return ok=True (both on
        unpatched and patched code).
        """
        with TemporaryDirectory() as td:
            repo = Path(td)
            q = repo / "quality"
            q.mkdir()
            (q / "PROGRESS.md").write_text(
                "- [x] Phase 1\n- [x] Phase 2\n- [x] Phase 3\n- [x] Phase 4\n",
                encoding="utf-8"
            )
            (q / "BUGS.md").write_text("# Bugs\n### BUG-001 — some bug\n", encoding="utf-8")
            sa = q / "spec_audits"
            sa.mkdir()
            (sa / "2026-04-18-triage.md").write_text("# Triage\n", encoding="utf-8")
            (sa / "2026-04-18-auditor-1.md").write_text("# Auditor 1\n", encoding="utf-8")
            result = run_playbook.check_phase_gate(repo, "5")
            self.assertTrue(
                result.ok,
                "Phase 5 gate must return ok=True when Phase 4 complete with triage+auditor files; "
                f"got ok={result.ok}, messages={result.messages}"
            )


class GapIterationRegressions(unittest.TestCase):
    """Regression tests for gap-iteration net-new bugs (BUG-017..BUG-019)."""

    def test_reg_gap17_agents_support_repo_root_skill(self):
        """BUG-017 / REQ-018: both orchestrator agents must list repo-root
        `SKILL.md` as a setup location for source-checkout launches.

        Source: agents/quality-playbook.agent.md:35-43 and
        agents/quality-playbook-claude.agent.md:45-55.
        Current: both omit plain `SKILL.md`. Desired: both include it.
        """
        general = (QPB_ROOT / "agents" / "quality-playbook.agent.md").read_text(encoding="utf-8")
        claude = (QPB_ROOT / "agents" / "quality-playbook-claude.agent.md").read_text(encoding="utf-8")
        self.assertIn("`SKILL.md`", general)
        self.assertIn("`SKILL.md`", claude)

    def test_reg_gap18_general_agent_keeps_context_ownership_consistent(self):
        """BUG-018 / REQ-019: the general orchestrator must not both forbid and
        require in-session phase execution.

        Source: agents/quality-playbook.agent.md:11-14 and 77-81.
        Current: both statements coexist. Desired: only one ownership model remains.
        """
        source = (QPB_ROOT / "agents" / "quality-playbook.agent.md").read_text(encoding="utf-8")
        self.assertFalse(
            "You do NOT execute phase logic yourself." in source
            and "Run Phase 1 in the current session." in source,
            "general orchestrator must not contradict its own phase-execution ownership"
        )

    def test_reg_gap19_collect_only_does_not_execute_tests(self):
        """BUG-019 / REQ-020: `python -m pytest --collect-only` must not execute
        the unittest runner.

        Source: pytest/__main__.py:16-34.
        Current: TextTestRunner.run() is still called. Desired: collection-only path
        avoids suite execution.
        """
        shim = _load_pytest_shim()
        fake_result = mock.Mock()
        fake_result.wasSuccessful.return_value = True
        with mock.patch("unittest.TextTestRunner.run", return_value=fake_result) as run_mock:
            exit_code = shim.main(["--collect-only", ".github/skills/quality_gate/tests/test_quality_gate.py"])
        self.assertEqual(exit_code, 0)
        run_mock.assert_not_called()

    def test_reg_gap19_nodeid_is_handled_without_importerror(self):
        """BUG-019 / REQ-020: pytest node IDs must be handled explicitly instead of
        crashing inside unittest discovery.

        Source: pytest/__main__.py:26-31 plus SKILL.md TDD examples using `::`.
        Current: ImportError escapes. Desired: no ImportError reaches the caller.
        """
        shim = _load_pytest_shim()
        try:
            shim.main([
                ".github/skills/quality_gate/tests/test_quality_gate.py::"
                "TestValidateIsoDate::test_valid_today"
            ])
        except ImportError as exc:
            self.fail(f"node-id path must be handled explicitly, not crash with ImportError: {exc}")


class UnfilteredIterationRegressions(unittest.TestCase):
    """Regression tests for unfiltered-iteration net-new bugs (BUG-020..BUG-023)."""

    def test_reg_unfiltered20_phase_mode_warns_not_skips(self):
        """BUG-020 / REQ-021: phase mode must continue with code-only analysis when
        docs are absent.
        """
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            args = _make_args()
            with mock.patch.object(run_playbook, "run_prompt", return_value=0) as run_prompt_mock, \
                 mock.patch.object(run_playbook, "archive_previous_run"), \
                 mock.patch.object(lib, "cleanup_repo"):
                exit_code = run_playbook.run_one_phased(repo, ["1"], args, "2026-04-19T12-00-00")
        self.assertEqual(exit_code, 0)
        run_prompt_mock.assert_called_once()

    def test_reg_unfiltered20_single_pass_warns_not_skips(self):
        """BUG-020 / REQ-021: single-pass mode must also continue code-only."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            args = _make_args()
            with mock.patch.object(run_playbook, "run_prompt", return_value=0) as run_prompt_mock, \
                 mock.patch.object(run_playbook, "archive_previous_run"), \
                 mock.patch.object(lib, "cleanup_repo"):
                exit_code = run_playbook.run_one_singlepass(repo, args, "2026-04-19T12-00-00")
        self.assertEqual(exit_code, 0)
        run_prompt_mock.assert_called_once()

    def test_reg_unfiltered21_phase_prompt_mentions_fallback_layouts(self):
        """BUG-021 / REQ-022: phase prompts must describe repo-root and Claude
        fallback layouts.
        """
        prompt = run_playbook.phase1_prompt(no_seeds=False)
        self.assertIn(".claude/skills/quality-playbook/SKILL.md", prompt)
        self.assertIn(".github/skills/quality-playbook/SKILL.md", prompt)

    def test_reg_unfiltered21_single_pass_prompt_mentions_fallback_layouts(self):
        """BUG-021 / REQ-022: single-pass and iteration prompts must stop naming only
        `.github/skills/SKILL.md`.
        """
        single_pass = run_playbook.single_pass_prompt(no_seeds=False)
        iteration = run_playbook.iteration_prompt("unfiltered")
        self.assertIn(".claude/skills/quality-playbook/SKILL.md", single_pass)
        self.assertIn("documented install-location fallback list", iteration)

    def test_reg_unfiltered22_run_one_phase_propagates_child_failure(self):
        """BUG-022 / REQ-023: `run_one_phase()` must return False on child failure."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            args = _make_args()
            log_file = repo / "phase.log"
            with mock.patch.object(run_playbook, "run_prompt", return_value=31):
                result = run_playbook.run_one_phase(
                    repo, "1", ["1"], args, log_file, "20260419T120000Z"
                )
        self.assertFalse(result)

    def test_reg_unfiltered22_run_one_singlepass_propagates_child_failure(self):
        """BUG-022 / REQ-023: single-pass mode must return non-zero on child failure."""
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "docs_gathered").mkdir()
            _write(repo / "docs_gathered" / "README.md", "real docs\n")
            args = _make_args()
            with mock.patch.object(run_playbook, "run_prompt", return_value=41), \
                 mock.patch.object(run_playbook, "archive_previous_run"), \
                 mock.patch.object(lib, "cleanup_repo"):
                exit_code = run_playbook.run_one_singlepass(repo, args, "2026-04-19T12-00-00")
        self.assertNotEqual(exit_code, 0)

    def test_reg_unfiltered23_language_detection_ignores_fixture_repos(self):
        """BUG-023 / REQ-024: language detection must ignore nested fixture repos."""
        qg = _load_quality_gate()
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / "main.py", "print('root python')\n")
            _write(repo / "repos" / "fixture" / "main.go", "package main\n")
            detected = qg.detect_project_language(repo)
        self.assertEqual(detected, "py")


class ParityIterationRegressions(unittest.TestCase):
    """Regression tests for parity-iteration net-new bugs (BUG-024..BUG-025)."""

    def test_reg_parity24_file_existence_accepts_functional_test_go(self):
        """BUG-024 / REQ-025: `functional_test.go` must satisfy the file-existence gate."""
        qg = _load_quality_gate()
        qg._reset_counters()
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            q = _seed_gate_repo(repo)
            _write(repo / "main.go", "package main\n")
            _write(q / "functional_test.go", "package quality\n")
            with mock.patch("sys.stdout", new_callable=io.StringIO):
                qg.check_file_existence(repo, q, "benchmark")
        self.assertEqual(qg.FAIL, 0)

    def test_reg_parity25_extension_check_accepts_functionaltest_java(self):
        """BUG-025 / REQ-026: `FunctionalTest.java` must be extension-validated, not skipped."""
        qg = _load_quality_gate()
        qg._reset_counters()
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            q = repo / "quality"
            q.mkdir(parents=True, exist_ok=True)
            _write(repo / "App.java", "class App {}\n")
            _write(q / "FunctionalTest.java", "class FunctionalTest {}\n")
            with mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
                qg.check_test_file_extension(repo, q)
                output = stdout.getvalue()
        self.assertEqual(qg.FAIL, 0)
        self.assertEqual(qg.WARN, 0)
        self.assertIn("FunctionalTest.java matches project language (java)", output)


class AdversarialIterationRegressions(unittest.TestCase):
    """Regression tests for adversarial-iteration net-new bugs (BUG-026..BUG-027)."""

    def test_reg_adv26_final_artifact_gaps_rejects_test_functional_test_alias(self):
        """BUG-026 / REQ-027: helper artifact discovery must reject undocumented
        `test_functional_test.*` aliases.
        """
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            for name in ["REQUIREMENTS.md", "CONTRACTS.md", "COVERAGE_MATRIX.md",
                         "COMPLETENESS_REPORT.md", "PROGRESS.md", "QUALITY.md",
                         "RUN_CODE_REVIEW.md", "RUN_INTEGRATION_TESTS.md",
                         "RUN_SPEC_AUDIT.md", "RUN_TDD_TESTS.md"]:
                _write(repo / "quality" / name, "stub\n")
            _write(repo / "quality" / "test_functional_test.py", "# undocumented alias\n")
            missing = run_playbook.final_artifact_gaps(repo)
        self.assertIn("functional test", missing,
                      "final_artifact_gaps() must still report a missing functional test when only test_functional_test.py exists")

    def test_reg_adv27_summary_ignores_noncanonical_regression_aliases(self):
        """BUG-027 / REQ-028: helper summaries must not count `RegressionTest.java`
        as canonical regression coverage.
        """
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _write(repo / "quality" / "REQUIREMENTS.md", "### REQ-001\n[Tier 1]\n")
            _write(repo / "quality" / "RegressionTest.java", "class RegressionTest {}\n")
            row = lib.build_summary_rows([repo])[0]
        self.assertEqual(row.regression, ".",
                         "build_summary_rows() must leave REGR unset when only non-canonical regression aliases exist")


if __name__ == "__main__":
    unittest.main()
