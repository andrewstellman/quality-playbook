#!/usr/bin/env python3
"""Test suite for quality_gate.py.

Uses unittest.TestCase, which both `unittest` and `pytest` can run.
Each test is self-contained: synthetic fixtures in temp directories,
no dependency on any real repo's quality/ folder.

Run from the QPB repo root with either:
    python3 -m pytest .github/skills/quality_gate/tests/test_quality_gate.py
    python3 -m unittest discover .github/skills/quality_gate/tests

Test-architecture convention (v1.5.7 instruction 032 NCF-6):
Most pure gate-logic tests live in this file — each `check_*`
function in `quality_gate.py` has a corresponding `Test<Name>` class
that constructs a synthetic `quality/` fixture and runs the gate as
a subprocess. Two gate functions have their tests in
`bin/tests/test_run_playbook.py::GateResolveArtifactPathTests`
rather than here, by historical convention:

- `check_no_workspace_dir` — exercised end-to-end via the runner's
  Phase 6 flow; the runner-side tests construct the workspace/
  directory state and call the function directly to assert the
  FAIL counter increments correctly.
- `_resolve_artifact_path` (helper, not a `check_*` gate function)
  — tests verify it returns the canonical top-level path
  unconditionally post-F-4a, which is a pure-helper assertion
  better expressed via direct function call than gate subprocess.

The split exists because those two gate behaviors are most
naturally validated through the runner's invocation path rather
than via the gate-script subprocess. See instruction 030's
outputs/030-ship-readiness-fixes.md and instruction 032's
outputs/032-final-report.md for the rationale and history.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PACKAGE_DIR / "quality_gate.py"

# Import the module for direct helper tests.
# Insert the package dir first so `import quality_gate` resolves to the module
# file (quality_gate.py) rather than the package (quality_gate/__init__.py).
sys.path.insert(0, str(PACKAGE_DIR))
import quality_gate  # noqa: E402


def run_gate(repo_dir, args=()):
    """Run the gate script as a subprocess. Return (stdout, returncode)."""
    cmd = [sys.executable, str(SCRIPT_PATH), *args, str(repo_dir)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout, result.returncode


def write_tree(root, files):
    """Create files from a dict: {relative_path: content}.

    content of None means "create as empty directory".
    Parents are created automatically.
    """
    for rel, content in files.items():
        p = Path(root) / rel
        if content is None:
            p.mkdir(parents=True, exist_ok=True)
        else:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)


def today_iso():
    return date.today().isoformat()


def future_iso():
    return (date.today() + timedelta(days=7)).isoformat()


def minimal_zero_bug_tree(version="1.4.4"):
    """Return a dict describing a zero-bug all-pass repo tree."""
    run_metadata = json.dumps({
        "schema_version": "1.0",
        "skill_version": version,
        "project": "testproj",
        "model": "test-model",
        "runner": "test-runner",
        "start_time": "2026-01-01T00:00:00Z",
    })
    return {
        "SKILL.md": f"---\nversion: {version}\n---\n",
        "AGENTS.md": "# Agents\n",
        "main.py": "print('hi')\n",  # a source file so language detection finds py
        "quality/BUGS.md": "# Bugs\n\n## No confirmed bugs\n",
        "quality/REQUIREMENTS.md": (
            "# Requirements\n\n"
            "UC-01 Foo\n"
            "UC-02 Bar\n"
            "UC-03 Baz\n"
        ),
        "quality/QUALITY.md": "# Quality\n",
        "quality/PROGRESS.md": (
            f"# Progress\n\n"
            f"Skill version: {version}\n\n"
            "## Terminal Gate Verification\n"
        ),
        "quality/COVERAGE_MATRIX.md": "# Coverage\n",
        "quality/COMPLETENESS_REPORT.md": (
            "# Completeness\n\n"
            "## Verdict\n\n"
            "PASS\n"
        ),
        "quality/CONTRACTS.md": "# Contracts\n",
        "quality/RUN_CODE_REVIEW.md": "# RCR\n",
        "quality/RUN_SPEC_AUDIT.md": "# RSA\n",
        "quality/RUN_INTEGRATION_TESTS.md": "# RIT\n",
        "quality/RUN_TDD_TESTS.md": "# RTT\n",
        "quality/test_functional.py": "# test\n",
        "quality/EXPLORATION.md": (
            "# Exploration\n\n"
            "## Open Exploration Findings\nstub\n\n"
            "## Quality Risks\nstub\n\n"
            "## Pattern Applicability Matrix\nstub\n\n"
            "## Candidate Bugs for Phase 2\nstub\n\n"
            "## Gate Self-Check\nstub\n"
        ),
        "quality/code_reviews/r.md": "# Review\n",
        "quality/spec_audits/2026-01-01-triage.md": "# Triage\n",
        "quality/spec_audits/2026-01-01-auditor-1.md": "# Auditor\n",
        "quality/spec_audits/triage_probes.sh": "#!/bin/bash\n",
        "quality/results/run-2026-01-01T00-00-00.json": run_metadata,
    }


def add_one_bug(tree, version="1.4.4", bug_id="BUG-001"):
    """Mutate a tree dict to include one confirmed bug with all required artifacts."""
    tree["quality/BUGS.md"] = (
        "# Bugs\n\n"
        f"### {bug_id}: Example bug\n\n"
        "Description of the bug.\n"
    )
    tree[f"quality/patches/{bug_id}-regression-test.patch"] = "--- /dev/null\n+++ b/test\n"
    tree[f"quality/patches/{bug_id}-fix.patch"] = "--- a/f\n+++ b/f\n"
    tree[f"quality/writeups/{bug_id}.md"] = (
        f"# {bug_id}\n\n"
        "## The fix\n\n"
        "```diff\n"
        "- old\n"
        "+ new\n"
        "```\n"
    )
    tree[f"quality/results/{bug_id}.red.log"] = "RED\nCommand: test\nExit code: 1\n"
    tree[f"quality/results/{bug_id}.green.log"] = "GREEN\nCommand: test\nExit code: 0\n"
    tree["quality/test_regression_test.go"] = "package quality\n"
    tree["quality/test_regression.py"] = "# Mirror as test_regression.*\n"
    tree["quality/TDD_TRACEABILITY.md"] = "# Traceability\n"
    tree["quality/results/tdd-results.json"] = json.dumps({
        "schema_version": "1.1",
        "skill_version": version,
        "date": today_iso(),
        "project": "testproj",
        "bugs": [
            {
                "id": bug_id,
                "requirement": "REQ-001",
                "red_phase": "fail",
                "green_phase": "pass",
                "verdict": "TDD verified",
                "fix_patch_present": True,
                "writeup_path": f"quality/writeups/{bug_id}.md",
            }
        ],
        "summary": {
            "total": 1,
            "verified": 1,
            "confirmed_open": 0,
            "red_failed": 0,
            "green_failed": 0,
        },
    }, indent=2)
    return tree


class FixtureBase(unittest.TestCase):
    """Base class: creates a tempdir and provides helpers."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, tree):
        write_tree(self.repo, tree)

    def gate(self, args=()):
        return run_gate(self.repo, args)


# --- JSON helper tests ---


class TestLoadJson(unittest.TestCase):
    def test_missing_file_returns_none(self):
        self.assertIsNone(quality_gate.load_json(Path("/nonexistent/file.json")))

    def test_valid_json_returns_dict(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"a": 1}')
            tmp_path = Path(f.name)
        try:
            self.assertEqual(quality_gate.load_json(tmp_path), {"a": 1})
        finally:
            tmp_path.unlink()

    def test_malformed_json_returns_none(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{not valid json")
            tmp_path = Path(f.name)
        try:
            self.assertIsNone(quality_gate.load_json(tmp_path))
        finally:
            tmp_path.unlink()

    def test_array_returns_list(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('[1, 2, 3]')
            tmp_path = Path(f.name)
        try:
            self.assertEqual(quality_gate.load_json(tmp_path), [1, 2, 3])
        finally:
            tmp_path.unlink()


class TestHasKey(unittest.TestCase):
    def test_dict_with_key(self):
        self.assertTrue(quality_gate.has_key({"a": 1}, "a"))

    def test_dict_without_key(self):
        self.assertFalse(quality_gate.has_key({"a": 1}, "b"))

    def test_none_returns_false(self):
        self.assertFalse(quality_gate.has_key(None, "a"))

    def test_list_returns_false(self):
        self.assertFalse(quality_gate.has_key([], "a"))

    def test_empty_dict(self):
        self.assertFalse(quality_gate.has_key({}, "a"))


class TestGetStr(unittest.TestCase):
    def test_string_value(self):
        self.assertEqual(quality_gate.get_str({"a": "hello"}, "a"), "hello")

    def test_number_value_returns_empty(self):
        self.assertEqual(quality_gate.get_str({"a": 42}, "a"), "")

    def test_bool_value_returns_empty(self):
        self.assertEqual(quality_gate.get_str({"a": True}, "a"), "")

    def test_none_value_returns_empty(self):
        self.assertEqual(quality_gate.get_str({"a": None}, "a"), "")

    def test_missing_key_returns_empty(self):
        self.assertEqual(quality_gate.get_str({"a": "x"}, "b"), "")

    def test_non_dict_returns_empty(self):
        self.assertEqual(quality_gate.get_str(None, "a"), "")
        self.assertEqual(quality_gate.get_str([], "a"), "")


class TestValidateIsoDate(unittest.TestCase):
    def test_valid_today(self):
        self.assertEqual(quality_gate.validate_iso_date(today_iso()), "valid")

    def test_past_date(self):
        self.assertEqual(quality_gate.validate_iso_date("2020-01-01"), "valid")

    def test_future_date(self):
        self.assertEqual(quality_gate.validate_iso_date(future_iso()), "future")

    def test_placeholder_YYYY(self):
        self.assertEqual(quality_gate.validate_iso_date("YYYY-MM-DD"), "placeholder")

    def test_placeholder_zeros(self):
        self.assertEqual(quality_gate.validate_iso_date("0000-00-00"), "placeholder")

    def test_bad_format(self):
        self.assertEqual(quality_gate.validate_iso_date("2026/04/18"), "bad_format")
        self.assertEqual(quality_gate.validate_iso_date("18-04-2026"), "bad_format")
        self.assertEqual(quality_gate.validate_iso_date("not a date"), "bad_format")

    def test_empty(self):
        self.assertEqual(quality_gate.validate_iso_date(""), "empty")


class TestCountPerBugField(unittest.TestCase):
    def test_empty_list(self):
        self.assertEqual(quality_gate.count_per_bug_field([], "id"), 0)

    def test_all_have_field(self):
        bugs = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        self.assertEqual(quality_gate.count_per_bug_field(bugs, "id"), 3)

    def test_some_missing_field(self):
        bugs = [{"id": "a"}, {"foo": "b"}, {"id": "c"}]
        self.assertEqual(quality_gate.count_per_bug_field(bugs, "id"), 2)

    def test_non_dict_items_skipped(self):
        bugs = [{"id": "a"}, "not a dict", None, {"id": "b"}]
        self.assertEqual(quality_gate.count_per_bug_field(bugs, "id"), 2)

    def test_non_list_input(self):
        self.assertEqual(quality_gate.count_per_bug_field(None, "id"), 0)
        self.assertEqual(quality_gate.count_per_bug_field({}, "id"), 0)


# --- fail() format tests (Phase 5 r3) ---


class TestFailHelperFormat(unittest.TestCase):
    """Phase 5 r3: fail() emits grep-parseable lines without a 'FAIL:' prefix."""

    def setUp(self):
        quality_gate.FAIL = 0

    def _capture(self, *args, **kwargs):
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            quality_gate.fail(*args, **kwargs)
        return buf.getvalue().rstrip("\n")

    def test_path_with_line_and_reason(self):
        line = self._capture("quality/INDEX.md", "missing required field 'target'", line=42)
        self.assertEqual(line, "  quality/INDEX.md:42: missing required field 'target'")
        self.assertEqual(quality_gate.FAIL, 1)

    def test_path_with_reason_only(self):
        line = self._capture("quality/INDEX.md", "file missing")
        self.assertEqual(line, "  quality/INDEX.md: file missing")

    def test_legacy_single_arg_still_works(self):
        line = self._capture("BUGS.md missing or not a file")
        self.assertEqual(line, "  BUGS.md missing or not a file")

    def test_no_FAIL_prefix_in_gate_module_source(self):
        """The literal 'FAIL: ' must not appear in gate output per Phase 5 r3
        format contract (grep acceptance criterion)."""
        src = PACKAGE_DIR.joinpath("quality_gate.py").read_text(encoding="utf-8")
        # Allow comments/docstrings to mention the string, but the actual
        # print() calls must not emit it. Scan format literals.
        import re
        offenders = re.findall(r'print\(f?"[^"]*FAIL:\s', src)
        self.assertEqual(offenders, [], f"unexpected FAIL: print in gate: {offenders}")


class TestCompensationAsymmetryPromotion(unittest.TestCase):
    """v1.5.7 instruction 047 Item 3 (A-5): WARN-only net for the
    Phase-1→Phase-2 asymmetry-promotion gap.

    Coverage split (corrected per instruction 048, closing the
    instruction-047 codex Task-4 finding that this docstring
    previously overstated its mutation-verified scope):

    - These tests exercise ``check_compensation_asymmetry_promotion``
      via DIRECT calls. They pin the function's *logic*: the
      compensation-prose regex, the zero-Pattern-tag → WARN branch,
      the with-tag pass, the missing-EXPLORATION.md no-op, and the
      WARN-only (never-FAIL) contract.
      Mutation evidence for the logic (in-tree per
      ai_context/DEVELOPMENT_PROCESS.md:152-160): neutering the
      ``warn(...)`` branch inside
      ``check_compensation_asymmetry_promotion`` makes
      ``test_asymmetry_prose_without_pattern_tag_warns`` fail (WARN
      stays 0); restoring it passes. Bite verified.
    - The WIRING of the check INTO ``check_repo()`` (the path the
      gate actually runs end-to-end) is pinned separately by
      ``TestCompensationAsymmetryPromotionWiring`` below, which
      invokes the gate as a subprocess. These direct-call tests do
      NOT exercise the ``check_repo`` registration and make no claim
      about it.

    Together both surfaces give full mutation-verified coverage:
    revert the function logic → these direct-call tests fail; remove
    the ``check_repo`` registration → the wiring integration test
    fails.
    """

    def setUp(self):
        quality_gate.WARN = 0
        self._tmp = tempfile.TemporaryDirectory()
        self.q = Path(self._tmp.name) / "quality"
        self.q.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _run(self):
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            quality_gate.check_compensation_asymmetry_promotion(self.q)
        return buf.getvalue()

    def _write(self, name, text):
        (self.q / name).write_text(text, encoding="utf-8")

    def test_asymmetry_prose_without_pattern_tag_warns(self):
        self._write(
            "EXPLORATION.md",
            "## Quality Risks\nModern PCI compensates for "
            "VIRTIO_F_RING_RESET; MMIO and vDPA rely entirely on "
            "vring_transport_features().\n",
        )
        self._write(
            "REQUIREMENTS.md",
            "### REQ-001: something\n- References: a.c\nbody\n",
        )
        out = self._run()
        self.assertEqual(
            quality_gate.WARN, 1,
            f"asymmetry prose + zero Pattern:-tagged REQs must WARN. "
            f"Output:\n{out}",
        )
        self.assertIn("compensation-grid BUG-default", out)

    def test_asymmetry_prose_with_pattern_tag_passes(self):
        self._write(
            "EXPLORATION.md",
            "Modern PCI compensates for RING_RESET; MMIO relies "
            "entirely on the generic path.\n",
        )
        self._write(
            "REQUIREMENTS.md",
            "### REQ-010: parity invariant\n"
            "- References: virtio_mmio.c, virtio_pci_modern.c\n"
            "- Pattern: compensation\n",
        )
        self._run()
        self.assertEqual(
            quality_gate.WARN, 0,
            "a Pattern:-tagged REQ satisfies the asymmetry-promotion "
            "net — no WARN",
        )

    def test_no_asymmetry_prose_passes(self):
        self._write(
            "EXPLORATION.md",
            "## Quality Risks\nStraightforward single-site logic; no "
            "cross-transport parity concerns here.\n",
        )
        self._write("REQUIREMENTS.md", "### REQ-001\nbody\n")
        self._run()
        self.assertEqual(
            quality_gate.WARN, 0,
            "no compensation-asymmetry prose → no WARN",
        )

    def test_missing_exploration_is_noop(self):
        # No EXPLORATION.md written.
        self._run()
        self.assertEqual(
            quality_gate.WARN, 0,
            "absent EXPLORATION.md → skipped, never WARN/FAIL",
        )

    def test_never_increments_fail(self):
        """WARN-only contract: this check must NEVER FAIL the gate."""
        quality_gate.FAIL = 0
        self._write(
            "EXPLORATION.md",
            "X compensates for Y; Z relies entirely on W.\n",
        )
        self._write("REQUIREMENTS.md", "### REQ-001\nno pattern\n")
        self._run()
        self.assertEqual(
            quality_gate.FAIL, 0,
            "check_compensation_asymmetry_promotion must be WARN-only",
        )


class TestCompensationAsymmetryPromotionWiring(FixtureBase):
    """v1.5.7 instruction 048 (closes the instruction-047 codex
    Task-4 finding): pin the WIRING of
    ``check_compensation_asymmetry_promotion`` INTO ``check_repo``.

    The sibling ``TestCompensationAsymmetryPromotion`` tests call the
    check function directly, so they do NOT detect a regression that
    disconnects the check from ``check_repo``'s registered-checks
    sequence. This test runs the gate END-TO-END (as a subprocess via
    FixtureBase.gate(), which goes through main() → check_repo()) over
    a synthetic repo whose EXPLORATION.md carries compensation-pattern
    prose and whose REQUIREMENTS.md has zero ``- Pattern:`` tags, and
    asserts the A-5 WARN surfaces in gate output — which can only
    happen if the check is wired into check_repo.

    Mutation-test evidence (in-tree per
    ai_context/DEVELOPMENT_PROCESS.md:152-160): delete the
    ``check_compensation_asymmetry_promotion(q)`` registration line
    from ``check_repo`` in
    ``.github/skills/quality_gate/quality_gate.py`` (the line
    immediately after ``check_run_metadata(q)``). Expected failure:
    ``test_warn_surfaces_through_check_repo`` fails at
    ``assertIn("[Asymmetry promotion (A-5)]", stdout)`` /
    ``assertIn(... "ZERO `Pattern:`-tagged REQs" ..., stdout)``
    because the check no longer runs in the end-to-end path.
    Restoration: re-add the registration line → test passes. Bite
    verified during instruction 048 development. (Clearing
    ``__pycache__`` before the post-restore re-verify is required —
    a stale .pyc otherwise masks the restored state.)
    """

    def _asymmetry_tree(self):
        tree = minimal_zero_bug_tree()
        # Keep all five required EXPLORATION.md sections (so
        # _check_exploration_sections still passes — no unrelated
        # FAIL) and inject compensation-asymmetry prose into one.
        tree["quality/EXPLORATION.md"] = (
            "# Exploration\n\n"
            "## Open Exploration Findings\n"
            "Modern PCI compensates for VIRTIO_F_RING_RESET; MMIO and "
            "vDPA rely entirely on vring_transport_features().\n\n"
            "## Quality Risks\nstub\n\n"
            "## Pattern Applicability Matrix\nstub\n\n"
            "## Candidate Bugs for Phase 2\nstub\n\n"
            "## Gate Self-Check\nstub\n"
        )
        # minimal_zero_bug_tree's REQUIREMENTS.md already has no
        # `- Pattern:` lines — leave it; that's the WARN trigger.
        return tree

    def test_warn_surfaces_through_check_repo(self):
        self.write(self._asymmetry_tree())
        stdout, code = self.gate()
        self.assertIn(
            "[Asymmetry promotion (A-5)]", stdout,
            "the A-5 check section header must appear in end-to-end "
            "gate output — proves check_compensation_asymmetry_promotion "
            "is wired into check_repo",
        )
        self.assertIn(
            "ZERO `Pattern:`-tagged REQs", stdout,
            "the A-5 WARN must fire end-to-end (asymmetry prose + "
            "zero Pattern: tags) — pins the check_repo wiring, not "
            "just the function logic",
        )
        self.assertEqual(
            code, 0,
            "the A-5 check is WARN-only; the otherwise-clean baseline "
            "tree must still exit 0 (WARN does not FAIL the gate)",
        )

    def test_no_warn_when_pattern_tagged_through_check_repo(self):
        """Negative control through the wiring: asymmetry prose WITH a
        Pattern:-tagged REQ must NOT emit the A-5 WARN end-to-end —
        the A-5 check instead emits its PASS line.

        Note: exit code is intentionally NOT asserted here. Adding a
        Pattern:-tagged REQ to the minimal tree legitimately trips the
        UNRELATED v1.5.2 cardinality gate (pattern-tagged REQs require
        quality/compensation_grid.json), so the gate exits 1 for a
        reason orthogonal to A-5. The WARN-only / exit-0 contract for
        the A-5 check is pinned by test_warn_surfaces_through_check_repo
        (clean baseline) and the direct-call
        TestCompensationAsymmetryPromotion.test_never_increments_fail.
        This test pins only the A-5-specific end-to-end behavior:
        section runs, no A-5 WARN when a Pattern tag is present."""
        tree = self._asymmetry_tree()
        tree["quality/REQUIREMENTS.md"] = (
            "# Requirements\n\nUC-01 Foo\nUC-02 Bar\nUC-03 Baz\n\n"
            "### REQ-010: cross-transport parity\n"
            "- References: virtio_mmio.c, virtio_pci_modern.c\n"
            "- Pattern: compensation\n"
        )
        self.write(tree)
        stdout, _code = self.gate()
        self.assertIn("[Asymmetry promotion (A-5)]", stdout)
        self.assertNotIn("ZERO `Pattern:`-tagged REQs", stdout)
        self.assertIn(
            "asymmetry prose present and 1 Pattern:-tagged REQ", stdout,
            "with a Pattern:-tagged REQ the A-5 check must emit its "
            "PASS line, not the WARN — end-to-end through check_repo",
        )


# --- Integration tests per check section ---


class TestAllPassBaseline(FixtureBase):
    """A clean zero-bug run should PASS with no failures."""

    def test_zero_bug_all_pass(self):
        self.write(minimal_zero_bug_tree())
        stdout, code = self.gate()
        self.assertEqual(code, 0, f"Expected PASS, got:\n{stdout}")
        self.assertIn("RESULT: GATE PASSED", stdout)
        # Summary counter shows zero failures on the baseline (Phase 5 r3:
        # individual failure lines are path:line:reason, without a FAIL:
        # prefix — the global counter is the authoritative source).
        self.assertIn("Total: 0 FAIL", stdout)

    def test_one_bug_all_pass(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        self.write(tree)
        stdout, code = self.gate()
        self.assertEqual(code, 0, f"Expected PASS, got:\n{stdout}")
        self.assertIn("RESULT: GATE PASSED", stdout)


class TestFileExistence(FixtureBase):
    def test_missing_bugs_md(self):
        tree = minimal_zero_bug_tree()
        del tree["quality/BUGS.md"]
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("BUGS.md missing", stdout)
        self.assertEqual(code, 1)

    def test_missing_requirements_md(self):
        tree = minimal_zero_bug_tree()
        del tree["quality/REQUIREMENTS.md"]
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("REQUIREMENTS.md missing", stdout)
        self.assertEqual(code, 1)

    def test_missing_agents_md(self):
        tree = minimal_zero_bug_tree()
        del tree["AGENTS.md"]
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("AGENTS.md missing (required at project root)", stdout)
        self.assertEqual(code, 1)

    def test_missing_exploration_md(self):
        tree = minimal_zero_bug_tree()
        del tree["quality/EXPLORATION.md"]
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("EXPLORATION.md missing", stdout)
        self.assertEqual(code, 1)

    def test_missing_code_reviews(self):
        tree = minimal_zero_bug_tree()
        del tree["quality/code_reviews/r.md"]
        self.write(tree)
        # Create empty code_reviews dir
        (self.repo / "quality" / "code_reviews").mkdir(parents=True, exist_ok=True)
        stdout, code = self.gate()
        self.assertIn("code_reviews/ missing or empty", stdout)

    def test_missing_spec_audits_triage(self):
        tree = minimal_zero_bug_tree()
        del tree["quality/spec_audits/2026-01-01-triage.md"]
        # triage_probes.sh also matches '*triage*' glob, so remove it too
        # so the check sees a genuine absence of any triage file.
        del tree["quality/spec_audits/triage_probes.sh"]
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("spec_audits/ missing triage file", stdout)

    def test_missing_auditor_files(self):
        tree = minimal_zero_bug_tree()
        del tree["quality/spec_audits/2026-01-01-auditor-1.md"]
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("spec_audits/ missing individual auditor files", stdout)

    def test_functional_test_scala_variant(self):
        tree = minimal_zero_bug_tree()
        del tree["quality/test_functional.py"]
        del tree["main.py"]
        tree["quality/FunctionalSpec.scala"] = "// spec"
        tree["main.scala"] = "// scala"
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("PASS: functional test file exists", stdout)

    def test_missing_functional_test(self):
        tree = minimal_zero_bug_tree()
        del tree["quality/test_functional.py"]
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("functional test file missing", stdout)


class TestBugsHeading(FixtureBase):
    def test_correct_heading(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree, bug_id="BUG-001")
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("PASS: All 1 bug headings use ### BUG-NNN format", stdout)
        self.assertEqual(code, 0)

    def test_wrong_double_hash(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        tree["quality/BUGS.md"] = "## BUG-001: bad format\n"
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("1 heading(s) use ## instead of ###", stdout)
        self.assertEqual(code, 1)

    def test_deep_heading(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        tree["quality/BUGS.md"] = "#### BUG-001: too deep\n"
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("1 heading(s) use #### or deeper instead of ###", stdout)

    def test_bold_format(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        tree["quality/BUGS.md"] = "**BUG-001**: bold\n"
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("1 heading(s) use **BUG- format", stdout)

    def test_bullet_format(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        tree["quality/BUGS.md"] = "- BUG-001: bullet\n"
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("1 heading(s) use - BUG- format", stdout)

    def test_zero_bug_run(self):
        tree = minimal_zero_bug_tree()
        # Default BUGS.md already says "No confirmed"
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("PASS: Zero-bug run — no headings expected", stdout)

    def test_severity_prefix_heading(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree, bug_id="BUG-H1")
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("PASS: All 1 bug headings use ### BUG-NNN format", stdout)


class TestTDDSidecar(FixtureBase):
    def test_valid_sidecar_passes(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("PASS: tdd-results.json exists (1 bugs)", stdout)
        self.assertIn("PASS: schema_version is '1.1'", stdout)
        self.assertIn("PASS: all verdict values are canonical", stdout)

    def test_missing_sidecar_with_bugs(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        del tree["quality/results/tdd-results.json"]
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("tdd-results.json missing", stdout)
        self.assertEqual(code, 1)

    def test_wrong_schema_version(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        data = json.loads(tree["quality/results/tdd-results.json"])
        data["schema_version"] = "1.0"
        tree["quality/results/tdd-results.json"] = json.dumps(data)
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("schema_version is '1.0', expected '1.1'", stdout)
        self.assertEqual(code, 1)

    def test_placeholder_date(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        data = json.loads(tree["quality/results/tdd-results.json"])
        data["date"] = "YYYY-MM-DD"
        tree["quality/results/tdd-results.json"] = json.dumps(data)
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("tdd-results.json date is placeholder", stdout)

    def test_future_date(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        data = json.loads(tree["quality/results/tdd-results.json"])
        data["date"] = future_iso()
        tree["quality/results/tdd-results.json"] = json.dumps(data)
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("is in the future", stdout)

    def test_bad_date_format(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        data = json.loads(tree["quality/results/tdd-results.json"])
        data["date"] = "2026/04/18"
        tree["quality/results/tdd-results.json"] = json.dumps(data)
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("is not ISO 8601", stdout)

    def test_invalid_verdict(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        data = json.loads(tree["quality/results/tdd-results.json"])
        data["bugs"][0]["verdict"] = "bogus"
        tree["quality/results/tdd-results.json"] = json.dumps(data)
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("1 non-canonical verdict value(s)", stdout)

    def test_non_canonical_field_name(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        data = json.loads(tree["quality/results/tdd-results.json"])
        data["bugs"][0]["bug_id"] = "BUG-001"  # bad field name
        tree["quality/results/tdd-results.json"] = json.dumps(data)
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("non-canonical field 'bug_id' found", stdout)

    def test_missing_summary_subkey(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        data = json.loads(tree["quality/results/tdd-results.json"])
        del data["summary"]["confirmed_open"]
        tree["quality/results/tdd-results.json"] = json.dumps(data)
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("summary missing 'confirmed_open' count", stdout)

    def test_missing_root_key(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        data = json.loads(tree["quality/results/tdd-results.json"])
        del data["project"]
        tree["quality/results/tdd-results.json"] = json.dumps(data)
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("missing root key 'project'", stdout)


class TestTDDLogs(FixtureBase):
    def test_all_logs_present(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("PASS: All 1 confirmed bug(s) have red-phase logs", stdout)
        self.assertIn("PASS: All 1 bug(s) with fix patches have green-phase logs", stdout)
        self.assertEqual(code, 0)

    def test_missing_red_log(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        del tree["quality/results/BUG-001.red.log"]
        self.write(tree)
        stdout, code = self.gate()
        # With only one bug and its red log missing, the "No red-phase logs
        # found" branch fires. With mixed presence, the "N missing" branch
        # fires. Either is a FAIL.
        self.assertTrue(
            "missing red-phase log" in stdout
            or "No red-phase logs found" in stdout,
            stdout,
        )
        self.assertEqual(code, 1)

    def test_invalid_status_tag(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        tree["quality/results/BUG-001.red.log"] = "INVALID_TAG\nstuff\n"
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("missing valid first-line status tag", stdout)

    def test_green_log_not_required_without_fix_patch(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        del tree["quality/patches/BUG-001-fix.patch"]
        del tree["quality/results/BUG-001.green.log"]
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("No fix patches found — green-phase logs not required", stdout)

    def test_sidecar_red_log_mismatch(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        # sidecar says red_phase: "fail" (RED expected in log), but log says GREEN
        tree["quality/results/BUG-001.red.log"] = "GREEN\nactual\n"
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("sidecar red_phase='fail' but log first-line is 'GREEN' (expected RED)", stdout)
        self.assertEqual(code, 1)

    def test_tdd_traceability_required_with_red_logs(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        del tree["quality/TDD_TRACEABILITY.md"]
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("TDD_TRACEABILITY.md missing", stdout)


class TestIntegrationSidecar(FixtureBase):
    def test_absent_benchmark_warns(self):
        tree = minimal_zero_bug_tree()
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("WARN: integration-results.json not present", stdout)
        self.assertEqual(code, 0)  # WARN doesn't fail

    def test_absent_general_info(self):
        tree = minimal_zero_bug_tree()
        self.write(tree)
        stdout, code = self.gate(args=["--general"])
        self.assertIn("INFO: integration-results.json not present (optional in general mode)", stdout)
        self.assertEqual(code, 0)

    def test_valid_sidecar(self):
        tree = minimal_zero_bug_tree()
        tree["quality/results/integration-results.json"] = json.dumps({
            "schema_version": "1.1",
            "skill_version": "1.4.4",
            "date": today_iso(),
            "project": "testproj",
            "recommendation": "SHIP",
            "groups": [{"group": 1, "name": "g", "use_cases": ["UC-01"], "result": "pass"}],
            "summary": {"total_groups": 1, "passed": 1, "failed": 0, "skipped": 0},
            "uc_coverage": {"UC-01": "covered_pass"},
        })
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("PASS: recommendation 'SHIP' is canonical", stdout)
        self.assertIn("PASS: all groups[].result values are canonical", stdout)
        self.assertIn("PASS: all uc_coverage values are canonical", stdout)

    def test_bad_recommendation(self):
        tree = minimal_zero_bug_tree()
        tree["quality/results/integration-results.json"] = json.dumps({
            "schema_version": "1.1",
            "skill_version": "1.4.4",
            "date": today_iso(),
            "project": "t",
            "recommendation": "MAYBE",
            "groups": [],
            "summary": {"total_groups": 0, "passed": 0, "failed": 0, "skipped": 0},
            "uc_coverage": {},
        })
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("recommendation 'MAYBE' is non-canonical", stdout)

    def test_bad_result_value(self):
        tree = minimal_zero_bug_tree()
        tree["quality/results/integration-results.json"] = json.dumps({
            "schema_version": "1.1",
            "skill_version": "1.4.4",
            "date": today_iso(),
            "project": "t",
            "recommendation": "SHIP",
            "groups": [{"group": 1, "name": "g", "use_cases": [], "result": "bogus"}],
            "summary": {"total_groups": 1, "passed": 0, "failed": 0, "skipped": 0},
            "uc_coverage": {},
        })
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("1 non-canonical groups[].result value(s)", stdout)

    def test_bad_uc_coverage_value(self):
        tree = minimal_zero_bug_tree()
        tree["quality/results/integration-results.json"] = json.dumps({
            "schema_version": "1.1",
            "skill_version": "1.4.4",
            "date": today_iso(),
            "project": "t",
            "recommendation": "SHIP",
            "groups": [],
            "summary": {"total_groups": 0, "passed": 0, "failed": 0, "skipped": 0},
            "uc_coverage": {"UC-01": "NOT_A_VALID_STATUS"},
        })
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("1 non-canonical uc_coverage value(s)", stdout)


class TestRecheckSidecar(FixtureBase):
    def test_absent_is_info(self):
        tree = minimal_zero_bug_tree()
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("INFO: recheck-results.json not present", stdout)

    def test_uses_results_key_not_bugs(self):
        """SKILL.md recheck template uses 'results' as array key."""
        tree = minimal_zero_bug_tree()
        tree["quality/results/recheck-results.json"] = json.dumps({
            "schema_version": "1.0",
            "skill_version": "1.4.4",
            "date": today_iso(),
            "project": "t",
            "source_run": {"bugs_md_date": today_iso(), "total_bugs": 1},
            "results": [{"id": "BUG-001", "severity": "HIGH", "status": "FIXED"}],
            "summary": {"total": 1, "fixed": 1, "partially_fixed": 0,
                        "still_open": 0, "inconclusive": 0},
        })
        tree["quality/results/recheck-summary.md"] = "# Recheck\n"
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("PASS: recheck has 'results'", stdout)
        self.assertIn("PASS: recheck schema_version is '1.0'", stdout)

    def test_wrong_schema_version(self):
        tree = minimal_zero_bug_tree()
        tree["quality/results/recheck-results.json"] = json.dumps({
            "schema_version": "1.1",  # wrong, should be 1.0
            "skill_version": "1.4.4",
            "date": today_iso(),
            "project": "t",
            "results": [],
            "summary": {},
        })
        tree["quality/results/recheck-summary.md"] = "# s\n"
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("recheck schema_version is '1.1', expected '1.0'", stdout)

    def test_missing_summary_md(self):
        tree = minimal_zero_bug_tree()
        tree["quality/results/recheck-results.json"] = json.dumps({
            "schema_version": "1.0",
            "skill_version": "1.4.4",
            "date": today_iso(),
            "project": "t",
            "results": [],
            "summary": {},
        })
        # No recheck-summary.md
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("recheck-summary.md missing", stdout)


class TestUseCases(FixtureBase):
    def test_sufficient_ucs_pass(self):
        tree = minimal_zero_bug_tree()
        # Default has UC-01, UC-02, UC-03 and 1 source file → min_uc=3
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("PASS: Found 3 distinct UC identifiers", stdout)

    def test_too_few_ucs_benchmark_fails(self):
        tree = minimal_zero_bug_tree()
        # 10+ source files to trigger min_uc=5
        for i in range(10):
            tree[f"src_{i}.py"] = "pass\n"
        # Requirements has only 3 UCs (from default), need 5
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("Only 3 distinct UC identifiers", stdout)
        self.assertEqual(code, 1)

    def test_too_few_ucs_general_warns(self):
        tree = minimal_zero_bug_tree()
        for i in range(10):
            tree[f"src_{i}.py"] = "pass\n"
        self.write(tree)
        stdout, code = self.gate(args=["--general"])
        self.assertIn("WARN: Only 3 distinct UC identifiers", stdout)
        self.assertEqual(code, 0)

    def test_no_ucs_fails(self):
        tree = minimal_zero_bug_tree()
        tree["quality/REQUIREMENTS.md"] = "# No UCs\n"
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("No canonical UC-NN identifiers", stdout)


class TestTestFileExtension(FixtureBase):
    def test_py_project_py_test_passes(self):
        tree = minimal_zero_bug_tree()
        # Default has main.py and test_functional.py
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("PASS: test_functional.py matches project language (py)", stdout)

    def test_go_project_py_test_fails(self):
        tree = minimal_zero_bug_tree()
        del tree["main.py"]
        tree["main.go"] = "package main\n"
        # test_functional.py remains — mismatch
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("test_functional.py does not match project language (go)", stdout)

    def test_no_language_detected(self):
        tree = minimal_zero_bug_tree()
        del tree["main.py"]
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("INFO: Cannot detect project language", stdout)


class TestTerminalGate(FixtureBase):
    def test_terminal_section_present(self):
        tree = minimal_zero_bug_tree()
        # Default PROGRESS.md has "## Terminal Gate Verification"
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("PASS: PROGRESS.md has Terminal Gate section", stdout)

    def test_terminal_section_missing(self):
        tree = minimal_zero_bug_tree()
        tree["quality/PROGRESS.md"] = "# Progress\n\nSkill version: 1.4.4\n"
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("PROGRESS.md missing Terminal Gate section", stdout)

    def test_terminal_section_case_insensitive(self):
        tree = minimal_zero_bug_tree()
        tree["quality/PROGRESS.md"] = (
            "# Progress\n\nSkill version: 1.4.4\n\n## TERMINAL GATE\n"
        )
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("PASS: PROGRESS.md has Terminal Gate section", stdout)


class TestMechanicalVerification(FixtureBase):
    def test_no_mechanical_dir_is_info(self):
        tree = minimal_zero_bug_tree()
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("INFO: No mechanical/ directory", stdout)

    def test_dir_without_verifier_fails(self):
        # v1.5.7 instruction 080b (F1): W4 makes verify.py the
        # canonical verifier; an empty mechanical/ (no verify.py,
        # no verify.sh, no *_cases.txt) now fails naming verify.py.
        tree = minimal_zero_bug_tree()
        tree["quality/mechanical/placeholder"] = ""
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("mechanical/ exists but verify.py missing", stdout)

    def test_cases_txt_without_verifier_fails_with_sharpened_message(self):
        # 080c (F1): *_cases.txt present but no verifier → the exact
        # required message (instruction-080c Task 1 step 3).
        tree = minimal_zero_bug_tree()
        tree["quality/mechanical/foo_cases.txt"] = "case 1:\n"
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn(
            "verify.py or verify.sh expected but neither found; "
            "cases.txt files exist, so mechanical verification is "
            "required for this project.", stdout)

    def test_verify_py_invoked_exit0_passes(self):
        # 080c (F1): the gate ACTUALLY runs verify.py (real script,
        # exit 0) — not a presence-only check.
        tree = minimal_zero_bug_tree()
        tree["quality/mechanical/verify.py"] = (
            "import sys\nprint('Mechanical verification OK')\n"
            "sys.exit(0)\n")
        tree["quality/results/mechanical-verify.log"] = "Mechanical verification OK\n"
        tree["quality/results/mechanical-verify.exit"] = "0\n"
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("PASS: verify.py exists", stdout)
        self.assertIn("PASS: verify.py ran clean (exit 0)", stdout)
        self.assertIn("PASS: mechanical-verify.exit is 0", stdout)

    def test_verify_py_invoked_exit1_fails_with_diff_surfaced(self):
        """The gate runs verify.py; a non-zero exit FAILs the gate
        and the verifier's stdout (the diff) is surfaced.

        Mutation-test evidence (in-tree per
        ai_context/DEVELOPMENT_PROCESS.md:152-160), instruction-080c —
        BITE EXECUTED during instruction-080c development:
          Mutation: revert quality_gate.py:check_mechanical to the
          080b presence-only form (delete the subprocess.run block;
          keep only the verify.py/verify.sh .is_file() pass_).
          Observed (purged __pycache__ first): this test FAILED —
          'verify.py FAILED (exit 1)' absent from gate stdout (a
          presence-only check never runs verify.py, so a forged
          exit-1 verifier is not caught — the exact 080b-F1 gap).
          Restoration: subprocess.run invocation block restored;
          gate surfaces 'verify.py FAILED (exit 1)' + the diff;
          test PASS again (PASS→FAIL→PASS).
        """
        tree = minimal_zero_bug_tree()
        tree["quality/mechanical/verify.py"] = (
            "import sys\n"
            "print('FAIL: quality/mechanical/foo_cases.txt mismatch')\n"
            "print('--- saved'); print('+++ fresh')\n"
            "print('+  case HALLUCINATED:')\n"
            "print('Mechanical verification FAILED')\n"
            "sys.exit(1)\n")
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("verify.py FAILED (exit 1)", stdout)
        self.assertIn("case HALLUCINATED", stdout)  # diff surfaced

    def test_verify_py_preferred_over_sh_when_both_present(self):
        # Both present → verify.py is RUN, verify.sh is not.
        tree = minimal_zero_bug_tree()
        tree["quality/mechanical/verify.py"] = (
            "import sys\nprint('py-ran')\nsys.exit(0)\n")
        tree["quality/mechanical/verify.sh"] = "#!/bin/bash\nexit 1\n"
        tree["quality/results/mechanical-verify.log"] = "output\n"
        tree["quality/results/mechanical-verify.exit"] = "0\n"
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("PASS: verify.py ran clean (exit 0)", stdout)
        self.assertNotIn("verify.sh exists (pre-W4 back-compat)", stdout)
        self.assertNotIn("verify.sh FAILED", stdout)

    def test_verify_sh_backcompat_invoked_exit0(self):
        tree = minimal_zero_bug_tree()
        tree["quality/mechanical/verify.sh"] = "#!/bin/bash\nexit 0\n"
        tree["quality/results/mechanical-verify.log"] = "output\n"
        tree["quality/results/mechanical-verify.exit"] = "0\n"
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("PASS: verify.sh exists (pre-W4 back-compat)", stdout)
        self.assertIn("PASS: verify.sh ran clean (exit 0)", stdout)
        self.assertIn("PASS: mechanical-verify.exit is 0", stdout)

    def test_verify_sh_backcompat_invoked_exit1_fails(self):
        tree = minimal_zero_bug_tree()
        tree["quality/mechanical/verify.sh"] = (
            "#!/bin/bash\necho 'sh-mismatch'\nexit 1\n")
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("verify.sh FAILED (exit 1)", stdout)
        self.assertIn("sh-mismatch", stdout)

    def test_receipt_exit_nonzero_still_fails(self):
        # The receipt cross-check is retained: even when the live
        # verify.sh exits 0, a receipt exit≠0 still FAILs (the agent
        # must have verified at the Phase-2a gate / Phase 6).
        tree = minimal_zero_bug_tree()
        tree["quality/mechanical/verify.sh"] = "#!/bin/bash\nexit 0\n"
        tree["quality/results/mechanical-verify.log"] = "output\n"
        tree["quality/results/mechanical-verify.exit"] = "1\n"
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("mechanical-verify.exit is '1', expected 0", stdout)

    def test_check_mechanical_invokes_with_correct_argv_and_cwd(self):
        """In-process: assert check_mechanical calls subprocess.run
        with [sys.executable, 'quality/mechanical/verify.py'] and
        cwd = the target repo root (q.parent) — the exact invocation
        contract codex-080b-F1 required."""
        import contextlib
        import io
        from unittest import mock
        tree = minimal_zero_bug_tree()
        tree["quality/mechanical/verify.py"] = "import sys\nsys.exit(0)\n"
        self.write(tree)
        q = self.repo / "quality"
        fake = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch("quality_gate.subprocess.run",
                        return_value=fake) as m:
            with contextlib.redirect_stdout(io.StringIO()):
                quality_gate.check_mechanical(q)
        self.assertTrue(m.called, "check_mechanical never invoked subprocess.run")
        call = m.call_args
        self.assertEqual(call.args[0],
                         [sys.executable, "quality/mechanical/verify.py"])
        self.assertEqual(str(call.kwargs.get("cwd")), str(q.parent))


class TestPatches(FixtureBase):
    def test_both_patches_present(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("PASS: 1 regression-test patch(es) for 1 bug(s)", stdout)
        self.assertIn("PASS: 1 fix patch(es)", stdout)

    def test_missing_regression_patch(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        del tree["quality/patches/BUG-001-regression-test.patch"]
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("FAIL", stdout)
        # Either "1 bug(s) missing regression-test patch" or "No regression-test patches found"
        self.assertTrue(
            "missing regression-test patch" in stdout
            or "No regression-test patches found" in stdout
        )

    def test_missing_test_regression_benchmark_fails(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        del tree["quality/test_regression_test.go"]
        del tree["quality/test_regression.py"]
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("test_regression.* missing", stdout)
        self.assertEqual(code, 1)

    def test_missing_test_regression_general_warns(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        del tree["quality/test_regression_test.go"]
        del tree["quality/test_regression.py"]
        self.write(tree)
        stdout, code = self.gate(args=["--general"])
        self.assertIn("WARN: test_regression.* missing", stdout)


class TestWriteups(FixtureBase):
    def test_all_writeups_with_diffs(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("PASS: 1 writeup(s) for 1 bug(s)", stdout)
        self.assertIn("PASS: All 1 writeup(s) have inline fix diffs", stdout)

    def test_writeup_without_diff_fails(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        tree["quality/writeups/BUG-001.md"] = "# BUG-001\n\nNo diff block here.\n"
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("FAIL", stdout)

    def test_missing_writeup(self):
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        del tree["quality/writeups/BUG-001.md"]
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("No writeups for 1 confirmed bug(s)", stdout)

    def test_writeup_uppercase_diff_fence_passes(self):
        """v1.5.1 Item 2 regression guard: a writeup that opens its fence
        with ```Diff (mixed case) carries a real unified diff and must be
        recognised as such. Both the presence check and the non-empty
        content check pass through the same case-insensitive regex —
        neither can silently skip a drifted-case fence."""
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        tree["quality/writeups/BUG-001.md"] = (
            "# BUG-001\n\n"
            "## The fix\n\n"
            "```Diff\n"
            "- old line\n"
            "+ new line\n"
            "```\n"
        )
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("PASS: All 1 writeup(s) have inline fix diffs", stdout)
        self.assertIn("PASS: All writeup ```diff blocks contain unified-diff content", stdout)

    def test_writeup_empty_uppercase_diff_fence_fails(self):
        """Paired with the test above: an uppercase ```DIFF fence with no
        `+`/`-` body must trip the empty-diff FAIL just like the lowercase
        case. This proves the case-insensitive regex is wired into BOTH
        the presence detection and the content inspection — if one were
        still case-sensitive, this fixture would produce a misleading
        pass/fail combination."""
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        tree["quality/writeups/BUG-001.md"] = (
            "# BUG-001\n\n"
            "## The fix\n\n"
            "```DIFF\n"
            "some context line\n"
            "another context line\n"
            "```\n"
        )
        self.write(tree)
        stdout, _ = self.gate()
        # Fence IS detected — presence check accepts DIFF.
        self.assertIn("PASS: All 1 writeup(s) have inline fix diffs", stdout)
        # Content check fires — no +/- lines inside.
        self.assertIn("writeup(s) have empty ```diff blocks", stdout)

    def test_writeup_with_unfilled_sentinel_fails(self):
        """v1.5.1 Item 5.2 hardening: every one of the five template
        sentinels in _WRITEUP_TEMPLATE_SENTINELS must trigger the
        "contain unfilled template sentinels" FAIL when it appears
        verbatim in a writeup. The writeup is otherwise valid (real
        diff fence with +/- content) so the failure is attributable
        to the sentinel and not to a co-firing check."""
        for sentinel in quality_gate._WRITEUP_TEMPLATE_SENTINELS:
            with self.subTest(sentinel=sentinel):
                # Rebuild a clean tree per subtest so prior iterations
                # don't leak state.
                self.tearDown()
                self.setUp()
                tree = minimal_zero_bug_tree()
                add_one_bug(tree)
                tree["quality/writeups/BUG-001.md"] = (
                    "# BUG-001\n\n"
                    f"{sentinel}\n\n"
                    "## The fix\n\n"
                    "```diff\n"
                    "- old\n"
                    "+ new\n"
                    "```\n"
                )
                self.write(tree)
                stdout, _ = self.gate()
                self.assertIn(
                    "writeup(s) contain unfilled template sentinels",
                    stdout,
                    msg=f"sentinel {sentinel!r} did not trip the FAIL",
                )
                # And the corresponding PASS must NOT appear.
                self.assertNotIn(
                    "PASS: No writeups contain unfilled template sentinels",
                    stdout,
                    msg=f"sentinel {sentinel!r} failed to suppress the PASS line",
                )

    def test_writeup_with_empty_diff_fence_fails(self):
        """A diff fence containing only context lines (no +/- body)
        must trip the "empty ```diff blocks" FAIL and must NOT produce
        the "contain unified-diff content" PASS."""
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        tree["quality/writeups/BUG-001.md"] = (
            "# BUG-001\n\n"
            "## The fix\n\n"
            "```diff\n"
            " context line one\n"
            "\n"
            " context line two\n"
            "```\n"
        )
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("writeup(s) have empty ```diff blocks", stdout)
        self.assertNotIn(
            "PASS: All writeup ```diff blocks contain unified-diff content",
            stdout,
        )

    def test_writeup_diff_with_only_file_headers_is_empty(self):
        """Pins the header-exclusion logic in _writeup_diff_is_non_empty:
        a diff that contains only `--- a/file` and `+++ b/file` header
        lines and no actual hunk content must be flagged as empty.
        Without header exclusion the check would see `-` and `+`
        prefixes on those lines and mis-classify the diff as non-empty."""
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        tree["quality/writeups/BUG-001.md"] = (
            "# BUG-001\n\n"
            "## The fix\n\n"
            "```diff\n"
            "--- a/src/foo.py\n"
            "+++ b/src/foo.py\n"
            "```\n"
        )
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("writeup(s) have empty ```diff blocks", stdout)

    def test_writeup_clean_passes_all_new_checks(self):
        """A hydrated writeup with a real diff body and no sentinels
        must produce all three new PASS messages (presence,
        non-empty content, no sentinels). This explicitly covers the
        sentinel PASS and the non-empty-content PASS that
        test_all_writeups_with_diffs above does not assert."""
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        # Use a clearly hydrated summary so no sentinel phrase fires.
        tree["quality/writeups/BUG-001.md"] = (
            "# BUG-001\n\n"
            "## Summary\n"
            "fetch_stop_arrivals() crashes on naive ExpectedArrivalTime.\n\n"
            "## The fix\n\n"
            "```diff\n"
            "--- a/bus_tracker.py\n"
            "+++ b/bus_tracker.py\n"
            "- eta = parsed - datetime.now(timezone.utc)\n"
            "+ if parsed.tzinfo is None:\n"
            "+     eta = None\n"
            "+ else:\n"
            "+     eta = parsed - datetime.now(timezone.utc)\n"
            "```\n"
        )
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("PASS: All 1 writeup(s) have inline fix diffs", stdout)
        self.assertIn(
            "PASS: All writeup ```diff blocks contain unified-diff content",
            stdout,
        )
        self.assertIn(
            "PASS: No writeups contain unfilled template sentinels", stdout
        )


class TestVerdictShape(FixtureBase):
    """v1.5.7 Fix 8 (instruction 031): check_verdict_shape enforces
    the canonical `## Verdict\\n\\nPASS|FAIL` shape in
    COMPLETENESS_REPORT.md. Model-comparison evidence showed verdict
    prose varying wildly across models — strict shape gives the gate
    something concrete to enforce."""

    def test_canonical_pass_verdict_passes(self):
        """## Verdict / PASS — the canonical shape passes."""
        tree = minimal_zero_bug_tree()
        # Already PASS in the fixture default.
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("[Verdict Shape]", stdout)
        self.assertIn(
            "PASS: COMPLETENESS_REPORT.md verdict shape canonical (PASS)",
            stdout,
        )

    def test_canonical_fail_verdict_passes_shape_check(self):
        """## Verdict / FAIL — shape is canonical even though the
        verdict outcome is FAIL. The gate is checking shape, not
        outcome."""
        tree = minimal_zero_bug_tree()
        tree["quality/COMPLETENESS_REPORT.md"] = (
            "# Completeness\n\n"
            "## Verdict\n\n"
            "FAIL\n"
        )
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn(
            "PASS: COMPLETENESS_REPORT.md verdict shape canonical (FAIL)",
            stdout,
        )

    def test_status_heading_instead_of_verdict_fails(self):
        """`## Status` instead of `## Verdict` → FAIL on missing
        canonical heading."""
        tree = minimal_zero_bug_tree()
        tree["quality/COMPLETENESS_REPORT.md"] = (
            "# Completeness\n\n"
            "## Status\n\n"
            "PASSED\n"
        )
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("[Verdict Shape]", stdout)
        self.assertIn("missing the canonical `## Verdict` heading", stdout)

    def test_passed_instead_of_PASS_fails(self):
        """`Passed` (mixed case) instead of `PASS` → FAIL on
        non-canonical verdict value."""
        tree = minimal_zero_bug_tree()
        tree["quality/COMPLETENESS_REPORT.md"] = (
            "# Completeness\n\n"
            "## Verdict\n\n"
            "Passed\n"
        )
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("[Verdict Shape]", stdout)
        self.assertIn("verdict line is 'Passed'", stdout)
        self.assertIn("must be exactly `PASS` or `FAIL`", stdout)

    def test_placeholder_phrase_fails(self):
        """Stub-phrase detection: `verdict is rendered after Phase 6`
        → FAIL with placeholder diagnostic."""
        tree = minimal_zero_bug_tree()
        tree["quality/COMPLETENESS_REPORT.md"] = (
            "# Completeness\n\n"
            "## Verdict\n\n"
            "verdict is rendered after Phase 6 (TDD verification) "
            "based on the receipts in...\n"
        )
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("[Verdict Shape]", stdout)
        self.assertIn("placeholder stub", stdout)

    def test_missing_completeness_report_fails(self):
        """COMPLETENESS_REPORT.md missing entirely → FAIL."""
        tree = minimal_zero_bug_tree()
        del tree["quality/COMPLETENESS_REPORT.md"]
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("[Verdict Shape]", stdout)
        self.assertIn("quality/COMPLETENESS_REPORT.md", stdout)
        self.assertIn("missing", stdout)

    def test_no_verdict_heading_at_all_fails(self):
        """COMPLETENESS_REPORT.md exists but has no `## Verdict`
        heading at all → FAIL on missing heading."""
        tree = minimal_zero_bug_tree()
        tree["quality/COMPLETENESS_REPORT.md"] = (
            "# Completeness\n\n"
            "Lots of prose but no verdict block.\n"
        )
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("[Verdict Shape]", stdout)
        self.assertIn("missing the canonical `## Verdict` heading", stdout)

    def test_duplicate_verdict_heading_fails(self):
        """v1.5.7 instruction 032 NCF-1/NCF-2: TWO `## Verdict`
        headings → FAIL. Pre-NCF-1 hardening, the gate validated only
        the FIRST `## Verdict` it found, so a stale earlier block
        could silently contradict a later one. NCF-2 specifically
        names the duplicate-heading bite test as the regression pin
        for that branch — this is that test."""
        tree = minimal_zero_bug_tree()
        tree["quality/COMPLETENESS_REPORT.md"] = (
            "# Completeness\n\n"
            "## Verdict\n\n"
            "PASS\n\n"
            "## Verdict\n\n"
            "FAIL\n"
        )
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("[Verdict Shape]", stdout)
        self.assertIn("2 `## Verdict` headings", stdout)
        self.assertIn("duplicate headings can silently disagree", stdout)

    def test_non_terminal_verdict_heading_fails(self):
        """v1.5.7 instruction 032 NCF-1: `## Verdict` followed by
        another `## ` heading (e.g., `## Postmortem`) → FAIL on
        non-terminal position. The verdict block must be the last
        section so an operator can grep the file's tail."""
        tree = minimal_zero_bug_tree()
        tree["quality/COMPLETENESS_REPORT.md"] = (
            "# Completeness\n\n"
            "## Verdict\n\n"
            "PASS\n\n"
            "## Postmortem\n\n"
            "Trailing notes.\n"
        )
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("[Verdict Shape]", stdout)
        self.assertIn("`## Verdict` is not the last level-2 heading", stdout)
        self.assertIn("Postmortem", stdout)

    def test_empty_body_after_verdict_heading_fails(self):
        """v1.5.7 instruction 032 NCF-5: `## Verdict` with NO body
        (heading present, file ends or next content is blank) → FAIL.
        Pre-NCF-5 this branch was implemented but had no bite-test."""
        tree = minimal_zero_bug_tree()
        tree["quality/COMPLETENESS_REPORT.md"] = (
            "# Completeness\n\n"
            "## Verdict\n\n"
            # No verdict value follows — file ends here.
        )
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("[Verdict Shape]", stdout)
        self.assertIn("no verdict value follows", stdout)

    def test_PASSED_uppercase_variant_fails(self):
        """v1.5.7 instruction 032 NCF-8: `PASSED` (all-caps with
        trailing D) → FAIL. The canonical verdict value is exactly
        `PASS` or `FAIL` — `PASSED` is a near-miss the gate must
        catch. Pre-NCF-8 test, the `PASSED` case relied on the
        same code path as `Passed` (NCF test_passed_instead_of_PASS
        _fails) but had no dedicated bite-test."""
        tree = minimal_zero_bug_tree()
        tree["quality/COMPLETENESS_REPORT.md"] = (
            "# Completeness\n\n"
            "## Verdict\n\n"
            "PASSED\n"
        )
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("[Verdict Shape]", stdout)
        self.assertIn("verdict line is 'PASSED'", stdout)
        self.assertIn("must be exactly `PASS` or `FAIL`", stdout)

    def test_markdown_emphasis_PASS_fails(self):
        """v1.5.7 instruction 032 NCF-10: `**PASS**` (markdown
        emphasis around PASS) → FAIL. The canonical value is the
        BARE token `PASS` — the prompt explicitly forbids markdown
        emphasis around it (phase_prompts/phase5.md). Pre-NCF-10,
        the case-sensitive equality check at quality_gate.py:694
        already rejected `**PASS**` but no bite-test pinned it."""
        tree = minimal_zero_bug_tree()
        tree["quality/COMPLETENESS_REPORT.md"] = (
            "# Completeness\n\n"
            "## Verdict\n\n"
            "**PASS**\n"
        )
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("[Verdict Shape]", stdout)
        self.assertIn("verdict line is '**PASS**'", stdout)
        self.assertIn("must be exactly `PASS` or `FAIL`", stdout)


class TestBugsMdPatchesConsistency(FixtureBase):
    """v1.5.7 Fix 7 (instruction 031): check_bugs_md_patches_consistency
    catches the model-comparison failure mode where Phase 3 finalization
    produces patches without updating BUGS.md (claude-haiku-4.5/zod: 14
    patches / 0 bugs; gpt-5.4-mini/axum: 6/0; etc.)."""

    def test_one_bug_with_fix_and_regression_patches_passes(self):
        """Canonical happy path: 1 bug, 2 patches (fix + regression).
        Should pass consistency check."""
        tree = minimal_zero_bug_tree()
        add_one_bug(tree)
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("[BUGS.md / patches consistency]", stdout)
        self.assertIn(
            "PASS: BUGS.md (1 bug(s)) and patches/ (2 patch(es)) are consistent",
            stdout,
        )

    def test_patches_without_bugs_fails(self):
        """The model-comparison failure mode: BUGS.md has zero entries
        but quality/patches/ contains patches. Hard fail."""
        tree = minimal_zero_bug_tree()
        # BUGS.md stays zero-bug (the default from minimal_zero_bug_tree),
        # but patches exist as if a bug had been processed.
        tree["quality/patches/BUG-001-fix.patch"] = "--- a/f\n+++ b/f\n"
        tree["quality/patches/BUG-001-regression-test.patch"] = (
            "--- /dev/null\n+++ b/test\n"
        )
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("[BUGS.md / patches consistency]", stdout)
        self.assertIn("quality/BUGS.md", stdout)
        self.assertIn("lists 0 bug entries", stdout)
        self.assertIn("2 patch file(s)", stdout)

    def test_fix_only_no_regression_passes(self):
        """Edge case allowed by the tolerance window: 3 bugs with only
        fix patches (no regression-test patches). Should still pass
        consistency because the regression-test gate is separate."""
        tree = minimal_zero_bug_tree()
        # 3 bug headings in BUGS.md.
        tree["quality/BUGS.md"] = (
            "# Bugs\n\n"
            "### BUG-001: first\n\n"
            "body\n\n"
            "### BUG-002: second\n\n"
            "body\n\n"
            "### BUG-003: third\n\n"
            "body\n"
        )
        # 3 fix patches only.
        tree["quality/patches/BUG-001-fix.patch"] = "--- a/f\n+++ b/f\n"
        tree["quality/patches/BUG-002-fix.patch"] = "--- a/f\n+++ b/f\n"
        tree["quality/patches/BUG-003-fix.patch"] = "--- a/f\n+++ b/f\n"
        # Other gates will complain about missing regression patches +
        # missing writeups + missing red/green logs, but the
        # consistency check itself should pass.
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("[BUGS.md / patches consistency]", stdout)
        self.assertIn(
            "PASS: BUGS.md (3 bug(s)) and patches/ (3 patch(es)) are consistent",
            stdout,
        )

    def test_orphan_patch_id_fails(self):
        """If BUGS.md has BUG-001 but patches/ has BUG-007-fix.patch,
        the orphan patch ID must be named in the diagnostic."""
        tree = minimal_zero_bug_tree()
        # BUGS.md lists BUG-001 only.
        tree["quality/BUGS.md"] = (
            "# Bugs\n\n"
            "### BUG-001: first\n\n"
            "body\n"
        )
        # patches/ has BUG-001 fix + an orphan BUG-007 fix.
        tree["quality/patches/BUG-001-fix.patch"] = "--- a/f\n+++ b/f\n"
        tree["quality/patches/BUG-007-fix.patch"] = "--- a/f\n+++ b/f\n"
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("[BUGS.md / patches consistency]", stdout)
        self.assertIn("missing entries for patch IDs", stdout)
        self.assertIn("BUG-007", stdout)

    def test_hybrid_named_patch_not_double_counted(self):
        """v1.5.7 instruction 032 NCF-4: a patch file whose name
        matches BOTH `*-fix*.patch` AND `*-regression-test*.patch`
        (e.g., `BUG-001-regression-test-fix.patch`) must be counted
        ONCE, not twice. Pre-NCF-4 the two globs were summed via
        len(a) + len(b), double-counting hybrid-named files."""
        tree = minimal_zero_bug_tree()
        tree["quality/BUGS.md"] = (
            "# Bugs\n\n"
            "### BUG-001: first\n\n"
            "body\n"
        )
        # File name contains both "-fix" and "-regression-test".
        tree["quality/patches/BUG-001-regression-test-fix.patch"] = (
            "--- a/f\n+++ b/f\n"
        )
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("[BUGS.md / patches consistency]", stdout)
        # The diagnostic message should say "1 patch(es)", not "2".
        self.assertIn(
            "BUGS.md (1 bug(s)) and patches/ (1 patch(es)) are consistent",
            stdout,
            "hybrid-named patch file should be counted once via set "
            "union, not double-counted by summing both glob lengths. "
            f"Stdout: {stdout!r}",
        )

    def test_split_patch_workflow_passes(self):
        """v1.5.7 instruction 032 NCF-7: dropped the
        `patches_count <= bug_count * 2` upper bound. Legitimate
        split-patch workflows (one bug fixed across multiple files)
        produce more than 2 patches per bug. Construct a fixture
        with 1 bug and 4 patches (3 fix + 1 regression test) — pre-
        NCF-7 this failed with 'contains 4 patches but BUGS.md lists
        only 1 bug(s)'; post-NCF-7 it passes the consistency
        check (other gates may still complain about specifics)."""
        tree = minimal_zero_bug_tree()
        tree["quality/BUGS.md"] = (
            "# Bugs\n\n"
            "### BUG-001: complex multi-file fix\n\n"
            "body\n"
        )
        # 3 fix patches for the same bug (multi-file split workflow)
        # + 1 regression-test patch.
        tree["quality/patches/BUG-001-fix-server.patch"] = (
            "--- a/server\n+++ b/server\n"
        )
        tree["quality/patches/BUG-001-fix-client.patch"] = (
            "--- a/client\n+++ b/client\n"
        )
        tree["quality/patches/BUG-001-fix-shared.patch"] = (
            "--- a/shared\n+++ b/shared\n"
        )
        tree["quality/patches/BUG-001-regression-test.patch"] = (
            "--- /dev/null\n+++ b/test\n"
        )
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("[BUGS.md / patches consistency]", stdout)
        # The consistency check itself passes (other gates may still
        # complain about red/green logs, writeups, etc. — those
        # aren't the concern of this NCF-7 test).
        self.assertIn(
            "BUGS.md (1 bug(s)) and patches/ (4 patch(es)) are consistent",
            stdout,
            "post-NCF-7: split-patch workflow with 4 patches for 1 "
            "bug must pass the consistency check (upper bound "
            "dropped). Stdout: " + repr(stdout),
        )

    def test_malformed_patch_filename_excluded_and_warned(self):
        """v1.5.7 instruction 033 Halt-5: a patch file matching the
        glob but not the canonical `BUG-NNN` naming convention (e.g.,
        `misc-cleanup-fix.patch`) is excluded from the count and
        surfaced as a WARN, not silently accepted. Pre-Halt-5 the
        malformed name was counted toward `patches_count` but skipped
        by the orphan-ID regex, so it could pass-through alongside
        proper BUG-NNN entries. Post-Halt-5 the filter promotes the
        situation to a visible WARN."""
        tree = minimal_zero_bug_tree()
        tree["quality/BUGS.md"] = (
            "# Bugs\n\n"
            "### BUG-001: real bug\n\n"
            "body\n"
        )
        # One proper BUG-NNN patch + one malformed-name patch matching
        # the glob.
        tree["quality/patches/BUG-001-fix.patch"] = "--- a/f\n+++ b/f\n"
        tree["quality/patches/misc-cleanup-fix.patch"] = (
            "--- a/m\n+++ b/m\n"
        )
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("[BUGS.md / patches consistency]", stdout)
        # WARN names the malformed file by name.
        self.assertIn("misc-cleanup-fix.patch", stdout)
        self.assertIn(
            "not the canonical BUG-NNN naming convention", stdout,
            "malformed-patch WARN message missing or wrong; got: "
            + repr(stdout),
        )
        # Consistency check still runs on the well-named patch only:
        # 1 bug + 1 well-formed fix patch.
        self.assertIn(
            "BUGS.md (1 bug(s)) and patches/ (1 patch(es)) are consistent",
            stdout,
            "malformed file should be excluded from the patches_count; "
            "BUG-001 should still consistency-check cleanly. Stdout: "
            + repr(stdout),
        )


class TestVersionStamps(FixtureBase):
    def test_matching_versions_pass(self):
        tree = minimal_zero_bug_tree()
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("PASS: PROGRESS.md version matches (1.4.4)", stdout)

    def test_mismatched_progress_version(self):
        tree = minimal_zero_bug_tree()
        tree["quality/PROGRESS.md"] = (
            "# Progress\n\nSkill version: 1.3.99\n\n## Terminal Gate Verification\n"
        )
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("PROGRESS.md version '1.3.99' != '1.4.4'", stdout)

    def test_missing_version_in_progress(self):
        tree = minimal_zero_bug_tree()
        tree["quality/PROGRESS.md"] = (
            "# Progress\n\n## Terminal Gate Verification\n"
        )
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("WARN: PROGRESS.md missing Skill version field", stdout)


class TestCrossRunContamination(FixtureBase):
    def test_matching_directory_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            versioned = Path(tmpdir) / "myrepo-1.4.4"
            versioned.mkdir()
            write_tree(versioned, minimal_zero_bug_tree())
            stdout, code = run_gate(versioned, args=["--version", "1.4.4"])
            self.assertIn("PASS: No version mismatch detected", stdout)

    def test_mismatched_directory_version(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            versioned = Path(tmpdir) / "myrepo-1.3.99"
            versioned.mkdir()
            write_tree(versioned, minimal_zero_bug_tree())  # SKILL.md says 1.4.4
            stdout, code = run_gate(versioned, args=["--version", "1.3.99"])
            self.assertIn("possible cross-run contamination", stdout)
            self.assertEqual(code, 1)


class TestStrictnessModes(FixtureBase):
    def test_benchmark_default(self):
        tree = minimal_zero_bug_tree()
        self.write(tree)
        stdout, _ = self.gate()
        self.assertIn("Strictness: benchmark", stdout)

    def test_general_flag(self):
        tree = minimal_zero_bug_tree()
        self.write(tree)
        stdout, _ = self.gate(args=["--general"])
        self.assertIn("Strictness: general", stdout)

    def test_triage_probes_missing_benchmark_fails(self):
        tree = minimal_zero_bug_tree()
        del tree["quality/spec_audits/triage_probes.sh"]
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("No executable triage evidence found", stdout)
        self.assertEqual(code, 1)

    def test_triage_probes_missing_general_warns(self):
        tree = minimal_zero_bug_tree()
        del tree["quality/spec_audits/triage_probes.sh"]
        self.write(tree)
        stdout, code = self.gate(args=["--general"])
        self.assertIn("WARN: No executable triage evidence found", stdout)
        self.assertEqual(code, 0)


class TestExitCodes(FixtureBase):
    def test_all_pass_exit_zero(self):
        tree = minimal_zero_bug_tree()
        self.write(tree)
        _, code = self.gate()
        self.assertEqual(code, 0)

    def test_any_fail_exit_one(self):
        tree = minimal_zero_bug_tree()
        del tree["quality/BUGS.md"]
        self.write(tree)
        _, code = self.gate()
        self.assertEqual(code, 1)

    def test_warn_only_exit_zero(self):
        tree = minimal_zero_bug_tree()
        # absence of integration-results.json is a WARN (benchmark mode)
        self.write(tree)
        stdout, code = self.gate()
        self.assertIn("WARN:", stdout)
        self.assertEqual(code, 0)

    def test_no_args_prints_usage_exit_one(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT_PATH)],
            capture_output=True, text=True
        )
        self.assertIn("Usage:", result.stdout)
        self.assertEqual(result.returncode, 1)


class TestSkillVersionDetection(unittest.TestCase):
    def test_detects_from_frontmatter(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("---\nname: quality-playbook\nversion: 1.5.1\n---\n")
            path = Path(f.name)
        try:
            self.assertEqual(quality_gate.detect_skill_version([path]), "1.5.1")
        finally:
            path.unlink()

    def test_returns_empty_when_no_file(self):
        self.assertEqual(
            quality_gate.detect_skill_version([Path("/nonexistent/SKILL.md")]),
            "",
        )

    def test_first_matching_location_wins(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p1 = Path(tmpdir) / "first.md"
            p2 = Path(tmpdir) / "second.md"
            p1.write_text("---\nversion: 1.1.1\n---\n")
            p2.write_text("---\nversion: 2.2.2\n---\n")
            self.assertEqual(
                quality_gate.detect_skill_version([p1, p2]),
                "1.1.1",
            )


# ---------------------------------------------------------------------------
# v1.5.1 Layer-1 checks — negative fixtures per schemas.md §10 invariants.
# Each test targets one check function directly; fixtures are synthetic trees
# and manifest JSON blobs crafted to exercise one invariant at a time.
# ---------------------------------------------------------------------------


import io
from contextlib import redirect_stdout


V150_VIRTIO_EXCERPT_TEXT = (
    "Intro\n"
    "\n"
    "2.4 Device initialization\n"
    "The driver MUST perform the following steps, in order, before the\n"
    "device is considered operational.\n"
)
V150_VIRTIO_SHA = __import__("hashlib").sha256(V150_VIRTIO_EXCERPT_TEXT.encode("utf-8")).hexdigest()
V150_VIRTIO_EXCERPT = (
    "2.4 Device initialization\n"
    "The driver MUST perform the following steps, in order, before the\n"
    "device is considered operational."
)


def _capture_fail_output(func, *args, **kwargs):
    """Run a gate check function and return (fail_count, full_stdout)."""
    quality_gate.FAIL = 0
    quality_gate.WARN = 0
    buf = io.StringIO()
    with redirect_stdout(buf):
        func(*args, **kwargs)
    return quality_gate.FAIL, buf.getvalue()


class V150FixtureBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.q = self.repo / "quality"
        self.q.mkdir(parents=True)
        quality_gate.FAIL = 0
        quality_gate.WARN = 0

    def tearDown(self):
        self._tmp.cleanup()

    def write_manifest(self, name, records_key, payload, *, schema_version="1.4.6"):
        wrapper = {
            "schema_version": schema_version,
            "generated_at": "2026-04-19T14:30:22Z",
            records_key: payload,
        }
        (self.q / name).write_text(json.dumps(wrapper), encoding="utf-8")

    def write_formal_doc(self):
        (self.repo / "formal_docs").mkdir()
        (self.repo / "formal_docs" / "virtio-excerpt.txt").write_text(
            V150_VIRTIO_EXCERPT_TEXT, encoding="utf-8"
        )
        self.write_manifest(
            "formal_docs_manifest.json",
            "records",
            [
                {
                    "source_path": "formal_docs/virtio-excerpt.txt",
                    "document_sha256": V150_VIRTIO_SHA,
                    "tier": 2,
                }
            ],
        )

    def good_req_record(self, req_id="REQ-001"):
        return {
            "id": req_id,
            "tier": 2,
            "functional_section": "Device initialization",
            "citation": {
                "document": "formal_docs/virtio-excerpt.txt",
                "document_sha256": V150_VIRTIO_SHA,
                "section": "2.4",
                "citation_excerpt": V150_VIRTIO_EXCERPT,
            },
        }


class TestV150PlaintextExtensions(V150FixtureBase):
    def _cite(self):
        folder = self.repo / "reference_docs" / "cite"
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def test_pdf_in_cite_fails(self):
        cite = self._cite()
        (cite / "spec.pdf").write_text("%PDF", encoding="utf-8")
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_cite_extensions, self.repo
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("spec.pdf", out)
        self.assertIn("schemas.md §2", out)

    def test_docx_in_cite_fails(self):
        cite = self._cite()
        (cite / "notes.docx").write_bytes(b"PK")
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_cite_extensions, self.repo
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("notes.docx", out)

    def test_readme_skipped(self):
        cite = self._cite()
        (cite / "README.md").write_text("folder doc")
        fails, _ = _capture_fail_output(
            quality_gate.check_v1_5_0_cite_extensions, self.repo
        )
        self.assertEqual(fails, 0)

    def test_meta_json_sidecar_skipped(self):
        cite = self._cite()
        (cite / "spec.txt").write_text("body\n")
        (cite / "spec.meta.json").write_text('{"tier": 2}')
        fails, _ = _capture_fail_output(
            quality_gate.check_v1_5_0_cite_extensions, self.repo
        )
        self.assertEqual(fails, 0)

    def test_absent_folders_is_noop(self):
        fails, _ = _capture_fail_output(
            quality_gate.check_v1_5_0_cite_extensions, self.repo
        )
        self.assertEqual(fails, 0)


class TestV150ManifestWrappers(V150FixtureBase):
    def test_records_shaped_manifest_missing_schema_version_fails(self):
        (self.q / "formal_docs_manifest.json").write_text(
            json.dumps({"generated_at": "2026-04-19T14:30:22Z", "records": []})
        )
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_manifest_wrappers, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("schema_version", out)

    def test_semantic_check_with_records_instead_of_reviews_fails(self):
        (self.q / "citation_semantic_check.json").write_text(
            json.dumps({
                "schema_version": "1.4.6",
                "generated_at": "2026-04-19T14:30:22Z",
                "records": [],
            })
        )
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_manifest_wrappers, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("reviews", out)
        self.assertIn("schemas.md §9.1", out)

    def test_records_manifest_with_reviews_key_fails(self):
        (self.q / "bugs_manifest.json").write_text(
            json.dumps({
                "schema_version": "1.4.6",
                "generated_at": "2026-04-19T14:30:22Z",
                "records": [],
                "reviews": [],
            })
        )
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_manifest_wrappers, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("reviews", out)

    def test_records_not_an_array_fails(self):
        (self.q / "requirements_manifest.json").write_text(
            json.dumps({
                "schema_version": "1.4.6",
                "generated_at": "2026-04-19T14:30:22Z",
                "records": {"not": "array"},
            })
        )
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_manifest_wrappers, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("'records'", out)


class TestV150RequirementsManifest(V150FixtureBase):
    def test_tier_1_without_citation_fails(self):
        self.write_formal_doc()
        # Re-write formal_docs with tier=1 so binding cross-check succeeds.
        self.write_manifest(
            "formal_docs_manifest.json",
            "records",
            [
                {
                    "source_path": "formal_docs/virtio-excerpt.txt",
                    "document_sha256": V150_VIRTIO_SHA,
                    "tier": 1,
                }
            ],
        )
        self.write_manifest(
            "requirements_manifest.json",
            "records",
            [{"id": "REQ-001", "tier": 1, "functional_section": "Foo"}],
        )
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_requirements_manifest, self.repo, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("REQ-001", out)
        self.assertIn("invariant #1", out)

    def test_tier_3_with_citation_fails(self):
        self.write_manifest(
            "requirements_manifest.json",
            "records",
            [
                {
                    "id": "REQ-042",
                    "tier": 3,
                    "functional_section": "Foo",
                    "citation": {"document": "x", "citation_excerpt": "y"},
                }
            ],
        )
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_requirements_manifest, self.repo, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("REQ-042", out)

    def test_missing_functional_section_fails(self):
        self.write_manifest(
            "requirements_manifest.json",
            "records",
            [{"id": "REQ-010", "tier": 3, "functional_section": ""}],
        )
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_requirements_manifest, self.repo, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("REQ-010", out)
        self.assertIn("functional_section", out)
        self.assertIn("invariant #8", out)

    def test_byte_equality_mismatch_fails(self):
        self.write_formal_doc()
        rec = self.good_req_record()
        rec["citation"]["citation_excerpt"] = "tampered paraphrase that doesn't match"
        self.write_manifest("requirements_manifest.json", "records", [rec])
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_requirements_manifest, self.repo, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("byte-equal", out)
        self.assertIn("invariant #11", out)

    def test_tier_mismatch_with_formal_doc_fails(self):
        self.write_formal_doc()  # FORMAL_DOC tier=2
        rec = self.good_req_record()
        rec["tier"] = 1  # REQ claims Tier 1
        # citation must still exist for Tier 1 REQs
        self.write_manifest("requirements_manifest.json", "records", [rec])
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_requirements_manifest, self.repo, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("invariant #14", out)

    def test_good_tier_2_req_passes(self):
        self.write_formal_doc()
        self.write_manifest(
            "requirements_manifest.json", "records", [self.good_req_record()]
        )
        fails, _ = _capture_fail_output(
            quality_gate.check_v1_5_0_requirements_manifest, self.repo, self.q
        )
        self.assertEqual(fails, 0)

    def test_page_only_locator_fails(self):
        self.write_formal_doc()
        rec = self.good_req_record()
        rec["citation"] = {
            "document": "formal_docs/virtio-excerpt.txt",
            "document_sha256": V150_VIRTIO_SHA,
            "page": 3,  # page alone is insufficient
            "citation_excerpt": "x",
        }
        self.write_manifest("requirements_manifest.json", "records", [rec])
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_requirements_manifest, self.repo, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("section or line", out)

    # --- Phase 5 r5: three negative fixtures flagged by Council B7. -----------

    def test_empty_excerpt_fails_invariant_4(self):
        """Tier-1/2 REQ with citation_excerpt='' fails invariant #4."""
        self.write_formal_doc()
        rec = self.good_req_record()
        rec["citation"]["citation_excerpt"] = ""  # blank excerpt
        self.write_manifest("requirements_manifest.json", "records", [rec])
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_requirements_manifest, self.repo, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("citation_excerpt", out)
        self.assertIn("invariant #4", out)

    def test_unresolvable_location_fails(self):
        """Citation pointing at a section that doesn't exist in the plaintext
        fails via the verifier's CitationResolutionError branch."""
        self.write_formal_doc()
        rec = self.good_req_record()
        rec["citation"]["section"] = "99.99"  # not present in the fixture text
        # Any stored excerpt will not byte-equal extraction since extraction fails.
        self.write_manifest("requirements_manifest.json", "records", [rec])
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_requirements_manifest, self.repo, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("citation location does not resolve", out)
        self.assertIn("invariant #4", out)

    def test_missing_formal_doc_fails_invariant_2(self):
        """Citation referencing a source_path not in formal_docs_manifest.json
        fails invariant #2 (document not in manifest)."""
        self.write_formal_doc()  # adds virtio-excerpt.txt
        rec = self.good_req_record()
        rec["citation"]["document"] = "formal_docs/nonexistent.txt"
        self.write_manifest("requirements_manifest.json", "records", [rec])
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_requirements_manifest, self.repo, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("not in formal_docs_manifest.json", out)
        self.assertIn("invariant #2", out)


class TestV150BugsManifest(V150FixtureBase):
    def test_missing_disposition_fails(self):
        self.write_manifest(
            "bugs_manifest.json",
            "records",
            [{"id": "BUG-001"}],
        )
        fails, out = _capture_fail_output(quality_gate.check_v1_5_0_bugs_manifest, self.q)
        self.assertGreaterEqual(fails, 1)
        self.assertIn("BUG-001", out)
        self.assertIn("disposition", out)

    def test_invalid_disposition_enum_fails(self):
        self.write_manifest(
            "bugs_manifest.json",
            "records",
            [{"id": "BUG-002", "disposition": "rewrite", "fix_type": "code"}],
        )
        fails, out = _capture_fail_output(quality_gate.check_v1_5_0_bugs_manifest, self.q)
        self.assertGreaterEqual(fails, 1)
        self.assertIn("BUG-002", out)
        self.assertIn("rewrite", out)

    def test_illegal_fix_type_disposition_combo_fails(self):
        self.write_manifest(
            "bugs_manifest.json",
            "records",
            [
                {
                    "id": "BUG-003",
                    "disposition": "code-fix",
                    "fix_type": "spec",
                    "disposition_rationale": "because",
                }
            ],
        )
        fails, out = _capture_fail_output(quality_gate.check_v1_5_0_bugs_manifest, self.q)
        self.assertGreaterEqual(fails, 1)
        self.assertIn("BUG-003", out)
        self.assertIn("invariant #12", out)

    def test_missing_rationale_fails(self):
        self.write_manifest(
            "bugs_manifest.json",
            "records",
            [{"id": "BUG-004", "disposition": "mis-read", "fix_type": "code"}],
        )
        fails, out = _capture_fail_output(quality_gate.check_v1_5_0_bugs_manifest, self.q)
        self.assertGreaterEqual(fails, 1)
        self.assertIn("disposition_rationale", out)

    def test_lowercase_severity_warns_not_fails(self):
        """v1.5.7 fix Q3 bite: BUG records with non-canonical-case
        severity ('high', 'Medium', 'low') trigger a WARN, not a
        FAIL. The canonical case per schemas.md §3.3 is uppercase
        (HIGH/MEDIUM/LOW). The gate auto-normalizes for downstream
        checks but surfaces the raw drift as WARN so adopters fix
        the records at the source."""
        self.write_manifest(
            "bugs_manifest.json",
            "records",
            [
                {
                    "id": "BUG-005",
                    "severity": "medium",  # non-canonical
                    "disposition": "code-fix",
                    "fix_type": "code",
                    "disposition_rationale": "demonstrates Q3 WARN path",
                },
                {
                    "id": "BUG-006",
                    "severity": "HIGH",  # canonical (no WARN expected)
                    "disposition": "code-fix",
                    "fix_type": "code",
                    "disposition_rationale": "canonical reference",
                },
            ],
        )
        fails, out = _capture_fail_output(quality_gate.check_v1_5_0_bugs_manifest, self.q)
        # Non-canonical case must NOT fail the gate (Q3 decision: WARN, not FAIL).
        self.assertEqual(
            fails, 0,
            f"non-canonical severity case must produce WARN, not FAIL; "
            f"got fails={fails}; output: {out!r}",
        )
        # WARN message must name the offending bug ID + its raw value.
        self.assertIn("non-canonical severity case", out)
        self.assertIn("BUG-005", out)
        self.assertIn("'medium'", out)
        # The canonical record (BUG-006) must NOT appear in the drift list.
        # The drift report uses `BUG-xxx='value'` form; BUG-006 should
        # be absent from that pattern.
        self.assertNotIn("BUG-006='HIGH'", out)


class TestV150IndexMd(V150FixtureBase):
    def _valid_index(self):
        return (
            "# Run Index — 20260419T143022Z\n\n"
            "```json\n"
            + json.dumps(
                {
                    "run_timestamp_start": "2026-04-19T14:30:22Z",
                    "run_timestamp_end": "2026-04-19T14:45:22Z",
                    "duration_seconds": 900,
                    "qpb_version": "1.4.6",
                    "target_repo_path": ".",
                    "target_repo_git_sha": "abc123",
                    # v1.5.4 Part 1: target_project_type retired in
                    # favour of target_role_breakdown sourced from the
                    # Phase 1 role map. Null is the legitimate value
                    # before Phase 1 has produced the map.
                    "target_role_breakdown": None,
                    "phases_executed": [],
                    "summary": {"requirements": {}, "bugs": {}, "gate_verdict": "pass"},
                    "artifacts": [],
                }
            )
            + "\n```\n"
        )

    def test_missing_index_md_fails_when_v1_5_0_manifests_present(self):
        self.write_manifest("requirements_manifest.json", "records", [])
        fails, out = _capture_fail_output(quality_gate.check_v1_5_0_index_md, self.q)
        self.assertGreaterEqual(fails, 1)
        self.assertIn("INDEX.md", out)
        self.assertIn("invariant #10", out)

    def test_legacy_run_without_manifests_is_noop(self):
        fails, _ = _capture_fail_output(quality_gate.check_v1_5_0_index_md, self.q)
        self.assertEqual(fails, 0)

    def test_missing_required_field_fails(self):
        text = self._valid_index().replace(
            '"duration_seconds": 900,', ""
        )
        (self.q / "INDEX.md").write_text(text, encoding="utf-8")
        fails, out = _capture_fail_output(quality_gate.check_v1_5_0_index_md, self.q)
        self.assertGreaterEqual(fails, 1)
        self.assertIn("duration_seconds", out)

    def test_empty_string_field_fails(self):
        payload = json.loads(self._valid_index().split("```json\n")[1].split("\n```")[0])
        payload["qpb_version"] = ""
        (self.q / "INDEX.md").write_text(
            "# Run Index\n\n```json\n" + json.dumps(payload) + "\n```\n",
            encoding="utf-8",
        )
        fails, out = _capture_fail_output(quality_gate.check_v1_5_0_index_md, self.q)
        self.assertGreaterEqual(fails, 1)
        self.assertIn("qpb_version", out)
        self.assertIn("empty", out)

    def test_valid_index_passes(self):
        (self.q / "INDEX.md").write_text(self._valid_index(), encoding="utf-8")
        fails, _ = _capture_fail_output(quality_gate.check_v1_5_0_index_md, self.q)
        self.assertEqual(fails, 0)

    # ----- v1.5.7 089e (BUG-011) ---------------------------------
    # Pre-089e the gate's `if isinstance(summary, dict)` guard
    # silently skipped the required-keys loop when summary was
    # anything other than a JSON object, and the trailing
    # `pass_("§11 fields present")` fired anyway — soft-passing
    # `summary: "pending"` / `summary: null` / `summary: []`
    # against schemas.md:1128 (`summary | object | yes`). The
    # validator (bin/validate_phase_artifacts._validate_index)
    # already FAILed these — opposite enforcement. The 089e fix
    # tightens the gate to match. These tests pin each non-dict
    # shape; the dict path is covered by `test_valid_index_passes`
    # above.

    def _index_with_summary(self, summary_value):
        """Build a §11 INDEX.md payload but override `summary` to
        the given value (used to cover the 4 non-dict shapes)."""
        payload = json.loads(
            self._valid_index().split("```json\n")[1].split("\n```")[0]
        )
        payload["summary"] = summary_value
        return (
            "# Run Index\n\n```json\n"
            + json.dumps(payload)
            + "\n```\n"
        )

    def test_non_dict_summary_string_fails(self):
        """BUG-011: gate must FAIL when `summary` is a string.

        Mutation-test evidence (ai_context/DEVELOPMENT_PROCESS.md:
        152-160), instruction-089e BUG-011:
          Mutation: revert the new `if not isinstance(summary,
          dict): fail(...); return` block in
          quality_gate.check_v1_5_0_index_md to the pre-089e
          `if isinstance(summary, dict): ...` (positive guard).
          Expected failure: THIS test fails — gate soft-passes
          `summary: "pending"` (`fails == 0` rather than ≥1).
          Restoration: re-add the negative-guard FAIL; passes.
          Bite executed during 089e development; PASS→FAIL→PASS
          confirmed (__pycache__ purged between mutate and restore).
        """
        (self.q / "INDEX.md").write_text(
            self._index_with_summary("pending"), encoding="utf-8",
        )
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_index_md, self.q,
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("'summary' must be a JSON object", out)
        self.assertIn("'str'", out)  # type name in FAIL message
        self.assertIn("schemas.md:1128", out)

    def test_non_dict_summary_null_fails(self):
        """BUG-011: gate must FAIL when `summary` is null."""
        (self.q / "INDEX.md").write_text(
            self._index_with_summary(None), encoding="utf-8",
        )
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_index_md, self.q,
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("'summary' must be a JSON object", out)
        self.assertIn("'NoneType'", out)

    def test_non_dict_summary_list_fails(self):
        """BUG-011: gate must FAIL when `summary` is a list."""
        (self.q / "INDEX.md").write_text(
            self._index_with_summary([]), encoding="utf-8",
        )
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_index_md, self.q,
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("'summary' must be a JSON object", out)
        self.assertIn("'list'", out)


class TestV150IndexMdSchemaRouting(V150FixtureBase):
    """v1.5.4 Round 2 Council finding C1 + C3: INDEX.md schema_version
    routing. Each of the four legitimate routing paths plus the
    "future schema, refuse explicitly" path has its own test, exercising
    check_v1_5_0_index_md directly via on-disk INDEX.md fixtures.

    Path inventory:
      1. schema 2.0 + target_role_breakdown            -> ship
      2. schema 2.0 missing target_role_breakdown       -> FAIL
      3. schema 1.0 + target_project_type               -> legacy WARN
      4. absent schema + target_project_type only       -> legacy WARN (heuristic)
      5. absent schema + neither field                  -> FAIL (current path)
      6. schema 3.0 (future)                            -> explicit FAIL
    """

    _BASE_FIELDS = {
        "run_timestamp_start": "2026-04-29T12:00:00Z",
        "run_timestamp_end": "2026-04-29T12:15:00Z",
        "duration_seconds": 900,
        "qpb_version": "1.5.4",
        "target_repo_path": ".",
        "target_repo_git_sha": "abc123",
        "phases_executed": [],
        "summary": {"requirements": {}, "bugs": {}, "gate_verdict": "pass"},
        "artifacts": [],
    }

    def _write_index(self, payload: dict) -> None:
        text = (
            "# Run Index — routing-test\n\n```json\n"
            + json.dumps(payload)
            + "\n```\n"
        )
        (self.q / "INDEX.md").write_text(text, encoding="utf-8")

    def test_schema_2_0_with_role_breakdown_passes(self) -> None:
        """Path 1: current schema with the v1.5.4 field. FAIL=0, WARN=0."""
        payload = dict(self._BASE_FIELDS)
        payload["schema_version"] = "2.0"
        payload["target_role_breakdown"] = {
            "files_by_role": {"code": 1},
            "size_by_role": {"code": 100},
            "percentages": {
                "skill_share": 0.0, "code_share": 1.0,
                "tool_share": 0.0, "other_share": 0.0,
            },
        }
        self._write_index(payload)
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_index_md, self.q
        )
        self.assertEqual(fails, 0, out)
        self.assertEqual(quality_gate.WARN, 0, out)

    def test_schema_2_0_missing_role_breakdown_fails(self) -> None:
        """Path 2: schema 2.0 with target_role_breakdown absent."""
        payload = dict(self._BASE_FIELDS)
        payload["schema_version"] = "2.0"
        # Note: target_role_breakdown deliberately omitted.
        self._write_index(payload)
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_index_md, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("target_role_breakdown", out)

    def test_schema_1_0_with_project_type_passes_with_warn(self) -> None:
        """Path 3: legacy archive accepted with one WARN."""
        payload = dict(self._BASE_FIELDS)
        payload["schema_version"] = "1.0"
        payload["target_project_type"] = "Code"
        self._write_index(payload)
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_index_md, self.q
        )
        self.assertEqual(fails, 0, out)
        self.assertGreaterEqual(quality_gate.WARN, 1, out)
        self.assertIn("legacy", out.lower())

    def test_schema_absent_with_project_type_passes_with_warn(self) -> None:
        """Path 4: pre-schema-version archive carrying only the legacy
        field. Heuristic fallback routes to legacy + WARN."""
        payload = dict(self._BASE_FIELDS)
        # No schema_version field.
        payload["target_project_type"] = "Code"
        self._write_index(payload)
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_index_md, self.q
        )
        self.assertEqual(fails, 0, out)
        self.assertGreaterEqual(quality_gate.WARN, 1, out)
        self.assertIn("legacy", out.lower())

    def test_schema_absent_with_neither_field_fails(self) -> None:
        """Path 5: ambiguous payload — no schema_version, no
        target_project_type, no target_role_breakdown. The heuristic
        falls through to the current path which then FAILs on the
        missing target_role_breakdown."""
        payload = dict(self._BASE_FIELDS)
        # No schema_version, no target_project_type, no target_role_breakdown.
        self._write_index(payload)
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_index_md, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("target_role_breakdown", out)

    def test_future_schema_version_fails_explicit(self) -> None:
        """Path 6 (Round 2 finding C1 regression pin): a payload from a
        future gate version (schema 3.0) carrying target_role_breakdown
        must NOT be silently misrouted to the legacy path. The gate
        refuses with an explicit "newer than supported" error."""
        payload = dict(self._BASE_FIELDS)
        payload["schema_version"] = "3.0"
        payload["target_role_breakdown"] = {
            "files_by_role": {"code": 1},
            "size_by_role": {"code": 100},
            "percentages": {
                "skill_share": 0.0, "code_share": 1.0,
                "tool_share": 0.0, "other_share": 0.0,
            },
        }
        self._write_index(payload)
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_index_md, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("newer than", out.lower())
        self.assertIn("3.0", out)
        # And specifically: the gate must NOT also FAIL with "missing
        # target_project_type", which would mean it routed to legacy.
        self.assertNotIn("missing required field 'target_project_type'", out)


class TestV150LegacyRunGracefulSkip(V150FixtureBase):
    """A repo with no v1.5.1 manifests should generate zero new FAILs."""

    def test_all_checks_noop_on_legacy_repo(self):
        # No manifests, no formal_docs, no INDEX.md — purely v1.4.x shape.
        fails, _ = _capture_fail_output(
            quality_gate.check_v1_5_0_gate_invariants, self.repo, self.q
        )
        self.assertEqual(fails, 0)


# ---------------------------------------------------------------------------
# Phase 6 — §10 invariant #17 semantic-check enforcement
# ---------------------------------------------------------------------------


def _capture_all_output(func, *args, **kwargs):
    """Run a check function and return (fail_count, warn_count, stdout)."""
    quality_gate.FAIL = 0
    quality_gate.WARN = 0
    buf = io.StringIO()
    with redirect_stdout(buf):
        func(*args, **kwargs)
    return quality_gate.FAIL, quality_gate.WARN, buf.getvalue()


class V150SemanticCheckFixtureBase(V150FixtureBase):
    """Shared scaffolding for Phase 6 invariant #17 fixture tests."""

    def write_reqs(self, tiers):
        """Seed requirements_manifest.json with N Tier 1/2 REQs."""
        records = []
        for idx, tier in enumerate(tiers, start=1):
            records.append({
                "id": f"REQ-{idx:03d}",
                "tier": tier,
                "functional_section": "Test",
                "description": f"Requirement {idx}",
            })
        self.write_manifest("requirements_manifest.json", "records", records)

    def write_reviews(self, reviews):
        """Seed citation_semantic_check.json with the given reviews list."""
        payload = {
            "schema_version": "1.4.6",
            "generated_at": "2026-04-19T14:30:22Z",
            "reviews": reviews,
        }
        (self.q / "citation_semantic_check.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )


class TestV150SemanticCheckHappyPath(V150SemanticCheckFixtureBase):
    def test_three_supports_passes(self):
        self.write_reqs([1])
        reviews = [
            {"req_id": "REQ-001", "reviewer": m, "verdict": "supports", "notes": ""}
            for m in ("claude-opus-4.7", "gpt-5.4", "gemini-2.5-pro")
        ]
        self.write_reviews(reviews)
        fails, warns, _ = _capture_all_output(
            quality_gate.check_v1_5_0_semantic_check, self.q
        )
        self.assertEqual(fails, 0)
        self.assertEqual(warns, 0)

    def test_three_tier12_reqs_nine_supports_passes(self):
        """Phase 6 Council-briefing fixture #1 (Phase 7 r0 carryover):
        3 Tier 1/2 REQs × 3 reviewers = 9 supports, gate passes."""
        self.write_reqs([1, 2, 1])
        reviews = [
            {"req_id": rid, "reviewer": m, "verdict": "supports", "notes": ""}
            for rid in ("REQ-001", "REQ-002", "REQ-003")
            for m in ("claude-opus-4.7", "gpt-5.4", "gemini-2.5-pro")
        ]
        self.write_reviews(reviews)
        fails, warns, _ = _capture_all_output(
            quality_gate.check_v1_5_0_semantic_check, self.q
        )
        self.assertEqual(fails, 0)
        self.assertEqual(warns, 0)

    def test_no_tier_12_reqs_passes(self):
        """Spec Gap: all REQs Tier 3 → invariant vacuously satisfied."""
        self.write_reqs([3, 4, 5])
        self.write_reviews([])
        fails, warns, _ = _capture_all_output(
            quality_gate.check_v1_5_0_semantic_check, self.q
        )
        self.assertEqual(fails, 0)


class TestV150SemanticCheckMajorityOverreach(V150SemanticCheckFixtureBase):
    def test_two_of_three_overreaches_fails(self):
        self.write_reqs([1])
        self.write_reviews([
            {"req_id": "REQ-001", "reviewer": "claude-opus-4.7", "verdict": "overreaches", "notes": "too strong"},
            {"req_id": "REQ-001", "reviewer": "gpt-5.4", "verdict": "overreaches", "notes": "agree"},
            {"req_id": "REQ-001", "reviewer": "gemini-2.5-pro", "verdict": "supports", "notes": ""},
        ])
        fails, _, out = _capture_all_output(
            quality_gate.check_v1_5_0_semantic_check, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("record_id=REQ-001", out)
        self.assertIn("majority overreaches", out)
        self.assertIn("invariant #17", out)

    def test_unanimous_overreaches_fails(self):
        self.write_reqs([2])
        self.write_reviews([
            {"req_id": "REQ-001", "reviewer": m, "verdict": "overreaches", "notes": ""}
            for m in ("claude-opus-4.7", "gpt-5.4", "gemini-2.5-pro")
        ])
        fails, _, out = _capture_all_output(
            quality_gate.check_v1_5_0_semantic_check, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("3/3", out)


class TestV150SemanticCheckSingleOverreachWarns(V150SemanticCheckFixtureBase):
    def test_single_overreaches_warns_but_passes(self):
        self.write_reqs([1])
        self.write_reviews([
            {"req_id": "REQ-001", "reviewer": "claude-opus-4.7", "verdict": "supports", "notes": ""},
            {"req_id": "REQ-001", "reviewer": "gpt-5.4", "verdict": "overreaches", "notes": "concern"},
            {"req_id": "REQ-001", "reviewer": "gemini-2.5-pro", "verdict": "supports", "notes": ""},
        ])
        fails, warns, out = _capture_all_output(
            quality_gate.check_v1_5_0_semantic_check, self.q
        )
        self.assertEqual(fails, 0)
        self.assertGreaterEqual(warns, 1)
        self.assertIn("gpt-5.4", out)
        self.assertIn("1/3", out)

    def test_one_unclear_warns(self):
        self.write_reqs([2])
        self.write_reviews([
            {"req_id": "REQ-001", "reviewer": "claude-opus-4.7", "verdict": "supports", "notes": ""},
            {"req_id": "REQ-001", "reviewer": "gpt-5.4", "verdict": "unclear", "notes": "ambiguous"},
            {"req_id": "REQ-001", "reviewer": "gemini-2.5-pro", "verdict": "supports", "notes": ""},
        ])
        fails, warns, _ = _capture_all_output(
            quality_gate.check_v1_5_0_semantic_check, self.q
        )
        self.assertEqual(fails, 0)
        self.assertGreaterEqual(warns, 1)


class TestV150SemanticCheckMissingReviews(V150SemanticCheckFixtureBase):
    def test_two_reviews_fails(self):
        self.write_reqs([1])
        self.write_reviews([
            {"req_id": "REQ-001", "reviewer": "claude-opus-4.7", "verdict": "supports", "notes": ""},
            {"req_id": "REQ-001", "reviewer": "gpt-5.4", "verdict": "supports", "notes": ""},
        ])
        fails, _, out = _capture_all_output(
            quality_gate.check_v1_5_0_semantic_check, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("fewer than 3 reviews", out)
        self.assertIn("§9.4", out)

    def test_zero_reviews_for_tier_12_req_fails(self):
        self.write_reqs([1])
        self.write_reviews([])
        fails, _, out = _capture_all_output(
            quality_gate.check_v1_5_0_semantic_check, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("fewer than 3 reviews", out)


class TestV150SemanticCheckTierViolations(V150SemanticCheckFixtureBase):
    def test_review_for_tier_3_req_fails(self):
        self.write_reqs([1, 3])  # REQ-001 tier 1, REQ-002 tier 3
        self.write_reviews([
            {"req_id": "REQ-001", "reviewer": "claude-opus-4.7", "verdict": "supports", "notes": ""},
            {"req_id": "REQ-001", "reviewer": "gpt-5.4", "verdict": "supports", "notes": ""},
            {"req_id": "REQ-001", "reviewer": "gemini-2.5-pro", "verdict": "supports", "notes": ""},
            {"req_id": "REQ-002", "reviewer": "claude-opus-4.7", "verdict": "supports", "notes": ""},
        ])
        fails, _, out = _capture_all_output(
            quality_gate.check_v1_5_0_semantic_check, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("REQ-002", out)
        self.assertIn("tier-3", out)

    def test_review_for_unknown_req_fails(self):
        self.write_reqs([1])
        self.write_reviews([
            {"req_id": "REQ-001", "reviewer": "claude-opus-4.7", "verdict": "supports", "notes": ""},
            {"req_id": "REQ-001", "reviewer": "gpt-5.4", "verdict": "supports", "notes": ""},
            {"req_id": "REQ-001", "reviewer": "gemini-2.5-pro", "verdict": "supports", "notes": ""},
            {"req_id": "REQ-999", "reviewer": "claude-opus-4.7", "verdict": "supports", "notes": ""},
        ])
        fails, _, out = _capture_all_output(
            quality_gate.check_v1_5_0_semantic_check, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("REQ-999", out)
        self.assertIn("does not exist", out)


class TestV150SemanticCheckMissingFile(V150SemanticCheckFixtureBase):
    def test_missing_with_tier_12_reqs_fails(self):
        self.write_reqs([1])
        # No semantic-check file written.
        fails, _, out = _capture_all_output(
            quality_gate.check_v1_5_0_semantic_check, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("file missing", out)
        self.assertIn("invariant #17", out)

    def test_missing_without_tier_12_reqs_warns(self):
        """Spec Gap: no Tier 1/2 REQs → missing file is a warning, not a failure."""
        self.write_reqs([3, 4, 5])
        fails, warns, _ = _capture_all_output(
            quality_gate.check_v1_5_0_semantic_check, self.q
        )
        self.assertEqual(fails, 0)
        self.assertGreaterEqual(warns, 1)


class TestV150SemanticCheckShapeValidation(V150SemanticCheckFixtureBase):
    def test_invalid_verdict_enum_fails(self):
        self.write_reqs([1])
        self.write_reviews([
            {"req_id": "REQ-001", "reviewer": "claude-opus-4.7", "verdict": "maybe", "notes": ""},
            {"req_id": "REQ-001", "reviewer": "gpt-5.4", "verdict": "supports", "notes": ""},
            {"req_id": "REQ-001", "reviewer": "gemini-2.5-pro", "verdict": "supports", "notes": ""},
        ])
        fails, _, out = _capture_all_output(
            quality_gate.check_v1_5_0_semantic_check, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("invalid verdict", out)
        self.assertIn("maybe", out)

    def test_duplicate_reviewer_fails(self):
        self.write_reqs([1])
        self.write_reviews([
            {"req_id": "REQ-001", "reviewer": "claude-opus-4.7", "verdict": "supports", "notes": ""},
            {"req_id": "REQ-001", "reviewer": "claude-opus-4.7", "verdict": "overreaches", "notes": ""},
            {"req_id": "REQ-001", "reviewer": "gpt-5.4", "verdict": "supports", "notes": ""},
            {"req_id": "REQ-001", "reviewer": "gemini-2.5-pro", "verdict": "supports", "notes": ""},
        ])
        fails, _, out = _capture_all_output(
            quality_gate.check_v1_5_0_semantic_check, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("duplicate review", out)

    def test_non_object_entry_fails(self):
        self.write_reqs([1])
        payload = {
            "schema_version": "1.4.6",
            "generated_at": "2026-04-19T14:30:22Z",
            "reviews": ["not an object"],
        }
        (self.q / "citation_semantic_check.json").write_text(
            json.dumps(payload), encoding="utf-8"
        )
        fails, _, out = _capture_all_output(
            quality_gate.check_v1_5_0_semantic_check, self.q
        )
        self.assertGreaterEqual(fails, 1)


class TestV150SemanticCheckOutputFormat(V150SemanticCheckFixtureBase):
    def test_failure_format_matches_path_record_id_pattern(self):
        """Regression: every semantic-check failure line fits the
        `<path>: record_id=<id>: <reason>` pattern."""
        self.write_reqs([1])
        self.write_reviews([
            {"req_id": "REQ-001", "reviewer": "claude-opus-4.7", "verdict": "overreaches", "notes": ""},
            {"req_id": "REQ-001", "reviewer": "gpt-5.4", "verdict": "overreaches", "notes": ""},
            {"req_id": "REQ-001", "reviewer": "gemini-2.5-pro", "verdict": "supports", "notes": ""},
        ])
        fails, _, out = _capture_all_output(
            quality_gate.check_v1_5_0_semantic_check, self.q
        )
        self.assertGreaterEqual(fails, 1)
        # Each failure line should match the path: record_id= pattern.
        import re
        failure_lines = [
            line for line in out.splitlines()
            if line.startswith("  citation_semantic_check.json")
            and "PASS:" not in line and "WARN:" not in line
        ]
        self.assertTrue(
            any(re.search(r":\s*record_id=\S+: ", line) for line in failure_lines),
            f"no line matches record_id= pattern: {failure_lines!r}",
        )


class TestChallengeGateCoverage(unittest.TestCase):
    """v1.5.1 Item 5.2: check_challenge_gate_coverage() invariant.

    Fixtures live under tests/fixtures/challenge_coverage/. Each fixture
    mirrors a real quality/ layout (bugs_manifest.json + optional
    challenge/ + optional writeups/). The invariant reads the fixture
    and its outcome is asserted here.
    """

    FIXTURES = Path(__file__).resolve().parent / "fixtures" / "challenge_coverage"

    def _run(self, fixture_name):
        q = self.FIXTURES / fixture_name / "quality"
        return _capture_all_output(quality_gate.check_challenge_gate_coverage, q)

    def test_fixture_a_all_records_present_passes(self) -> None:
        fails, _, out = self._run("fixture_a_pass")
        self.assertEqual(fails, 0, out)
        self.assertIn("PASS:", out)

    def test_virtio_1_4_6_fixture_fails_and_names_missing_bugs(self) -> None:
        """v1.5.1 Item 5.3 — the preserved virtio-1.4.6 reproduction.

        Source: repos/benchmark-1.5.0/virtio-1.4.6/quality/{bugs_manifest.json,
        requirements_manifest.json, challenge/BUG-001..006-challenge.md}.
        The BUG-007/008 challenge records are intentionally absent — that
        asymmetry is the evidence that motivated Item 5.2's invariant.

        Expected: the six preserved records satisfy the verdict-line
        check (legacy form, accommodated in the invariant); BUG-007 and
        BUG-008 are reported as missing. The invariant fails exactly
        twice and the failure lines name those two IDs.
        """
        fails, _, out = self._run("virtio-1.4.6")
        self.assertGreaterEqual(fails, 2)
        self.assertIn("BUG-007", out)
        self.assertIn("BUG-008", out)
        # The 6 existing records must NOT be reported as missing.
        for bug_id in ("BUG-001", "BUG-002", "BUG-003",
                       "BUG-004", "BUG-005", "BUG-006"):
            self.assertNotIn(f"{bug_id}: challenge record missing", out)

    def test_fixture_c_bad_verdict_fails(self) -> None:
        fails, _, out = self._run("fixture_c_bad_verdict")
        self.assertGreaterEqual(fails, 1)
        self.assertIn("BUG-001", out)
        self.assertIn("verdict line", out)

    def test_fixture_d_rejected_verdict_passes(self) -> None:
        fails, _, out = self._run("fixture_d_rejected")
        self.assertEqual(fails, 0, out)
        self.assertIn("PASS:", out)

    def test_fixture_e_iteration_derived_alone_requires_record(self) -> None:
        """Iteration-derived pattern fires on `source` alone; when the
        record exists with a valid verdict, the invariant PASSes even
        though no other pattern matched."""
        fails, _, out = self._run("fixture_e_iteration")
        self.assertEqual(fails, 0, out)
        self.assertIn("PASS:", out)

    def test_fixture_f_absent_manifest_is_na(self) -> None:
        """Absent bugs_manifest.json → invariant returns without emitting
        PASS or FAIL (consistent with quality_gate N/A convention)."""
        fails, _, out = self._run("fixture_f_no_manifest")
        self.assertEqual(fails, 0, out)
        # No PASS line either — the invariant silently no-ops.
        self.assertNotIn("PASS:", out)
        self.assertNotIn("FAIL", out)

    def test_bug_with_no_triggers_does_not_require_record(self) -> None:
        """Direct-call unit check: a bug with severity LOW, a good
        requirement, clean source, and no writeup keywords must not
        require a challenge record."""
        with tempfile.TemporaryDirectory() as tmp:
            q = Path(tmp) / "quality"
            q.mkdir()
            (q / "bugs_manifest.json").write_text(json.dumps({
                "schema_version": "1.5.1",
                "generated_at": "2026-04-21T00:00:00Z",
                "records": [{
                    "id": "BUG-100", "severity": "LOW",
                    "title": "cosmetic label typo",
                    "requirement": "REQ-001",
                    "disposition": "code-fix", "fix_type": "code",
                }],
            }))
            (q / "requirements_manifest.json").write_text(json.dumps({
                "schema_version": "1.5.1",
                "generated_at": "2026-04-21T00:00:00Z",
                "records": [{
                    "id": "REQ-001", "tier": 1,
                    "functional_section": "UI",
                    "description": "Labels match spec",
                    "citation": {
                        "document": "formal_docs/ui.md",
                        "document_sha256": "deadbeef00000000000000000000000000000000000000000000000000000000",
                        "section": "1.1",
                        "citation_excerpt": "Labels shall match the spec verbatim.",
                    },
                }],
            }))
            fails, _, out = _capture_all_output(
                quality_gate.check_challenge_gate_coverage, q
            )
            # No trigger fired → no record required → PASS as "vacuous".
            self.assertEqual(fails, 0, out)
            self.assertIn("vacuous", out)


# ---------------------------------------------------------------------------
# v1.5.3 Phase 2 — schema-extension validation
# ---------------------------------------------------------------------------


class TestV153FormalDocRoleValidation(V150FixtureBase):
    """schemas.md §10 invariant #23 — FORMAL_DOC.role on v1.5.3-shaped manifests."""

    def test_v153_shaped_with_valid_role_passes(self):
        self.write_manifest(
            "formal_docs_manifest.json",
            "records",
            [
                {
                    "source_path": "formal_docs/virtio-excerpt.txt",
                    "document_sha256": V150_VIRTIO_SHA,
                    "tier": 1,
                    "role": "external-spec",
                }
            ],
        )
        fails, warns, out = _capture_all_output(
            quality_gate.check_v1_5_3_formal_doc_role_validation, self.q
        )
        self.assertEqual(fails, 0, out)
        self.assertEqual(warns, 0, out)
        self.assertIn("v1.5.3 role validation complete", out)

    def test_v153_shaped_with_invalid_role_fails(self):
        self.write_manifest(
            "formal_docs_manifest.json",
            "records",
            [
                {
                    "source_path": "formal_docs/virtio-excerpt.txt",
                    "document_sha256": V150_VIRTIO_SHA,
                    "tier": 1,
                    "role": "not-a-real-role",
                }
            ],
        )
        fails, _, out = _capture_all_output(
            quality_gate.check_v1_5_3_formal_doc_role_validation, self.q
        )
        self.assertGreaterEqual(fails, 1, out)
        self.assertIn("invariant #23", out)
        self.assertIn("not-a-real-role", out)

    def test_legacy_manifest_emits_one_warn_and_skips(self):
        # No record carries source_type/divergence_type/role -> legacy.
        self.write_manifest(
            "formal_docs_manifest.json",
            "records",
            [
                {
                    "source_path": "formal_docs/virtio-excerpt.txt",
                    "document_sha256": V150_VIRTIO_SHA,
                    "tier": 1,
                }
            ],
        )
        fails, warns, out = _capture_all_output(
            quality_gate.check_v1_5_3_formal_doc_role_validation, self.q
        )
        self.assertEqual(fails, 0, out)
        self.assertEqual(warns, 1, out)
        self.assertIn("legacy manifest detected", out)


class TestV153SourceTypeValidation(V150FixtureBase):
    """schemas.md §10 invariant #21 (first part) — REQ.source_type on v1.5.3-shaped."""

    def test_v153_shaped_with_valid_source_type_passes(self):
        self.write_manifest(
            "requirements_manifest.json",
            "records",
            [
                {
                    "id": "REQ-001",
                    "tier": 3,
                    "functional_section": "Foo",
                    "source_type": "code-derived",
                }
            ],
        )
        fails, warns, out = _capture_all_output(
            quality_gate.check_v1_5_3_source_type_validation, self.q
        )
        self.assertEqual(fails, 0, out)
        self.assertEqual(warns, 0, out)
        self.assertIn("v1.5.3 source_type validation complete", out)

    def test_v153_shaped_with_invalid_source_type_fails(self):
        # Triggers v1.5.3-shaped detection via the divergence_type field on
        # the *bugs* manifest -- not directly on this REQ -- to exercise
        # the per-manifest detection. Simpler: put an invalid source_type
        # directly so detection AND validation both fire on this manifest.
        self.write_manifest(
            "requirements_manifest.json",
            "records",
            [
                {
                    "id": "REQ-001",
                    "tier": 3,
                    "functional_section": "Foo",
                    "source_type": "invented-source",
                }
            ],
        )
        fails, _, out = _capture_all_output(
            quality_gate.check_v1_5_3_source_type_validation, self.q
        )
        self.assertGreaterEqual(fails, 1, out)
        self.assertIn("invariant #21", out)
        self.assertIn("invented-source", out)

    def test_legacy_manifest_emits_one_warn_and_skips(self):
        self.write_manifest(
            "requirements_manifest.json",
            "records",
            [
                {
                    "id": "REQ-001",
                    "tier": 3,
                    "functional_section": "Foo",
                }
            ],
        )
        fails, warns, out = _capture_all_output(
            quality_gate.check_v1_5_3_source_type_validation, self.q
        )
        self.assertEqual(fails, 0, out)
        self.assertEqual(warns, 1, out)
        self.assertIn("legacy manifest detected", out)


class TestV153SkillSectionConsistency(V150FixtureBase):
    """schemas.md §10 invariant #21 (second part) — skill_section consistency."""

    def test_skill_section_with_skill_section_source_type_passes(self):
        self.write_manifest(
            "requirements_manifest.json",
            "records",
            [
                {
                    "id": "REQ-001",
                    "tier": 1,
                    "functional_section": "Foo",
                    "source_type": "skill-section",
                    "skill_section": "Phase 1: Explore the Codebase",
                }
            ],
        )
        fails, warns, out = _capture_all_output(
            quality_gate.check_v1_5_3_skill_section_consistency, self.q
        )
        self.assertEqual(fails, 0, out)
        self.assertEqual(warns, 0, out)

    def test_empty_skill_section_with_skill_section_source_type_fails(self):
        self.write_manifest(
            "requirements_manifest.json",
            "records",
            [
                {
                    "id": "REQ-001",
                    "tier": 1,
                    "functional_section": "Foo",
                    "source_type": "skill-section",
                    "skill_section": "",
                }
            ],
        )
        fails, _, out = _capture_all_output(
            quality_gate.check_v1_5_3_skill_section_consistency, self.q
        )
        self.assertGreaterEqual(fails, 1, out)
        self.assertIn("invariant #21", out)
        self.assertIn("REQ-001", out)

    def test_populated_skill_section_with_other_source_type_fails(self):
        self.write_manifest(
            "requirements_manifest.json",
            "records",
            [
                {
                    "id": "REQ-001",
                    "tier": 3,
                    "functional_section": "Foo",
                    "source_type": "code-derived",
                    "skill_section": "Should not be set",
                }
            ],
        )
        fails, _, out = _capture_all_output(
            quality_gate.check_v1_5_3_skill_section_consistency, self.q
        )
        self.assertGreaterEqual(fails, 1, out)
        self.assertIn("invariant #21", out)

    def test_legacy_manifest_silently_skips(self):
        # Round 2 Council, item 1: pin the deliberate piggyback. Unlike
        # the other three v1.5.3 invariants, this check emits ZERO WARNs
        # on a legacy manifest -- the soft warn for the same
        # requirements_manifest.json is already emitted by
        # check_v1_5_3_source_type_validation. A future maintainer
        # adding a WARN here for "consistency with the brief" would
        # double-warn for the same file; this test guards that intent.
        self.write_manifest(
            "requirements_manifest.json",
            "records",
            [
                {
                    "id": "REQ-001",
                    "tier": 3,
                    "functional_section": "Foo",
                }
            ],
        )
        fails, warns, out = _capture_all_output(
            quality_gate.check_v1_5_3_skill_section_consistency, self.q
        )
        self.assertEqual(fails, 0, out)
        self.assertEqual(
            warns,
            0,
            "skill_section_consistency must NOT emit its own WARN on legacy "
            "manifests; the source_type check piggybacks the single WARN "
            "for the shared requirements_manifest.json. See the docstring "
            "comment on check_v1_5_3_skill_section_consistency.",
        )

    def test_skill_section_null_with_other_source_type_passes(self):
        self.write_manifest(
            "requirements_manifest.json",
            "records",
            [
                {
                    "id": "REQ-001",
                    "tier": 3,
                    "functional_section": "Foo",
                    "source_type": "code-derived",
                    "skill_section": None,
                }
            ],
        )
        fails, _, out = _capture_all_output(
            quality_gate.check_v1_5_3_skill_section_consistency, self.q
        )
        self.assertEqual(fails, 0, out)


class TestV153DivergenceTypeValidation(V150FixtureBase):
    """schemas.md §10 invariant #22 — BUG.divergence_type on v1.5.3-shaped."""

    def test_v153_shaped_with_valid_divergence_type_passes(self):
        self.write_manifest(
            "bugs_manifest.json",
            "records",
            [
                {
                    "id": "BUG-001",
                    "title": "x",
                    "severity": "LOW",
                    "disposition": "code-fix",
                    "fix_type": "code",
                    "disposition_rationale": "x",
                    "req_id": "REQ-001",
                    "divergence_type": "code-spec",
                }
            ],
        )
        fails, warns, out = _capture_all_output(
            quality_gate.check_v1_5_3_divergence_type_validation, self.q
        )
        self.assertEqual(fails, 0, out)
        self.assertEqual(warns, 0, out)
        self.assertIn("v1.5.3 divergence_type validation complete", out)

    def test_v153_shaped_with_invalid_divergence_type_fails(self):
        self.write_manifest(
            "bugs_manifest.json",
            "records",
            [
                {
                    "id": "BUG-001",
                    "title": "x",
                    "severity": "LOW",
                    "disposition": "code-fix",
                    "fix_type": "code",
                    "disposition_rationale": "x",
                    "req_id": "REQ-001",
                    "divergence_type": "fabricated-kind",
                }
            ],
        )
        fails, _, out = _capture_all_output(
            quality_gate.check_v1_5_3_divergence_type_validation, self.q
        )
        self.assertGreaterEqual(fails, 1, out)
        self.assertIn("invariant #22", out)
        self.assertIn("fabricated-kind", out)

    def test_legacy_manifest_emits_one_warn_and_skips(self):
        self.write_manifest(
            "bugs_manifest.json",
            "records",
            [
                {
                    "id": "BUG-001",
                    "title": "x",
                    "severity": "LOW",
                    "disposition": "code-fix",
                    "fix_type": "code",
                    "disposition_rationale": "x",
                    "req_id": "REQ-001",
                }
            ],
        )
        fails, warns, out = _capture_all_output(
            quality_gate.check_v1_5_3_divergence_type_validation, self.q
        )
        self.assertEqual(fails, 0, out)
        self.assertEqual(warns, 1, out)
        self.assertIn("legacy manifest detected", out)


class TestV153FieldKeysContract(unittest.TestCase):
    """DQ-3 regression test (v1.5.3 Phase 3 / Round 2 Council).

    Pins quality_gate._V153_FIELD_KEYS against a literal so a future
    schema extension that adds a fifth v1.5.3-only field to the helper
    without updating the schema's enum-bearing field list (or vice
    versa) fails this test. The lockstep enforcement is structural:
    refactoring _is_v1_5_3_shaped's body cannot silently change which
    keys trigger v1.5.3-shaped detection because the body now reads
    from _V153_FIELD_KEYS directly.

    If a future schema addition expands the v1.5.3 field set (e.g.,
    REQ.record_provenance), updating _V153_FIELD_KEYS without updating
    this test fails the test. The maintainer must update both the
    constant and the test literal in the same commit, AND surface the
    change for explicit review (the test's update is the visible audit
    trail).

    The schema enum-bearing field list lives across schemas.md §3.6
    (formal_doc_role -> FORMAL_DOC.role), §3.7 (req_source_type ->
    REQ.source_type), §3.8 (bug_divergence_type -> BUG.divergence_type)
    -- three field names total, matching the three keys here. Any
    fourth would require a §3.11+ entry in schemas.md and an update
    to this literal.
    """

    def test_field_keys_match_schema_v1_5_3_field_set(self):
        self.assertEqual(
            quality_gate._V153_FIELD_KEYS,
            frozenset({"source_type", "divergence_type", "role"}),
            "If you added a v1.5.3-only field to the schema, update "
            "_V153_FIELD_KEYS in lockstep with this test's literal AND "
            "with the relevant schemas.md §3.x enum subsection. The "
            "DQ-3 contract requires structural lockstep so a future "
            "field addition cannot silently ship validation-free.",
        )


class TestV153IsShapedHelper(unittest.TestCase):
    """Direct tests of the _is_v1_5_3_shaped detection helper (§3.10)."""

    def test_legacy_manifest_returns_false(self):
        self.assertFalse(
            quality_gate._is_v1_5_3_shaped(
                {"records": [{"id": "REQ-001", "tier": 3}]}
            )
        )

    def test_source_type_present_returns_true(self):
        self.assertTrue(
            quality_gate._is_v1_5_3_shaped(
                {"records": [{"id": "REQ-001", "source_type": "code-derived"}]}
            )
        )

    def test_divergence_type_present_returns_true(self):
        self.assertTrue(
            quality_gate._is_v1_5_3_shaped(
                {"records": [{"id": "BUG-001", "divergence_type": "code-spec"}]}
            )
        )

    def test_role_present_returns_true(self):
        self.assertTrue(
            quality_gate._is_v1_5_3_shaped(
                {"records": [{"source_path": "x", "role": "external-spec"}]}
            )
        )

    def test_empty_records_returns_false(self):
        self.assertFalse(quality_gate._is_v1_5_3_shaped({"records": []}))

    def test_non_dict_returns_false(self):
        self.assertFalse(quality_gate._is_v1_5_3_shaped(None))


class TestV153CouncilInboxValidation(unittest.TestCase):
    """Phase 3b BLOCK-4 + DQ-5: pass_d_council_inbox.json structural
    validation + cross-reference invariant against pass_d_audit.json."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.q = self.repo / "quality"
        self.phase3 = self.q / "phase3"
        self.phase3.mkdir(parents=True)
        quality_gate.FAIL = 0
        quality_gate.WARN = 0

    def tearDown(self):
        self._tmp.cleanup()

    def _write_inbox(self, items: list, schema_version: str = "1.0") -> None:
        (self.phase3 / "pass_d_council_inbox.json").write_text(
            json.dumps({
                "schema_version": schema_version,
                "generated_at": "2026-04-27T00:00:00Z",
                "items": items,
            }),
            encoding="utf-8",
        )

    def _write_audit(self, rejected: list, demoted: list) -> None:
        (self.phase3 / "pass_d_audit.json").write_text(
            json.dumps({
                "schema_version": "1.0",
                "generated_at": "2026-04-27T00:00:00Z",
                "promoted": [],
                "rejected": rejected,
                "demoted_to_tier_5": demoted,
                "rejection_rate": 0.0,
                "rejection_rate_threshold": 0.30,
                "phase4_council_flag": False,
            }),
            encoding="utf-8",
        )

    def _valid_item(self, **overrides) -> dict:
        item = {
            "item_type": "rejected-draft",
            "draft_idx": 0,
            "section_idx": 1,
            "section_heading": "Phase 1",
            "rationale": "structural near-miss",
            "context_excerpt": "x",
            "provisional_disposition": "needs-council-review",
        }
        item.update(overrides)
        return item

    def test_phase3_dir_absent_is_noop(self):
        # Remove phase3/ entirely.
        import shutil
        shutil.rmtree(self.phase3)
        fails, _ = _capture_fail_output(
            quality_gate.check_v1_5_3_council_inbox_validation, self.q
        )
        self.assertEqual(fails, 0)

    def test_valid_inbox_passes(self):
        self._write_inbox([self._valid_item()])
        self._write_audit(
            rejected=[{"draft_idx": 0, "rationale": "x"}],
            demoted=[],
        )
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_3_council_inbox_validation, self.q
        )
        self.assertEqual(fails, 0, out)
        self.assertIn("validation complete", out)

    def test_invalid_item_type_fails(self):
        self._write_inbox(
            [self._valid_item(item_type="invented-kind")]
        )
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_3_council_inbox_validation, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("invented-kind", out)

    def test_missing_required_field_fails(self):
        bad = self._valid_item()
        del bad["rationale"]
        self._write_inbox([bad])
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_3_council_inbox_validation, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("rationale", out)

    def test_cross_reference_audit_rejection_without_inbox_item_fails(self):
        # Audit has 1 rejection, inbox has 0 items -> BLOCK-4 violation.
        self._write_inbox([])
        self._write_audit(
            rejected=[{"draft_idx": 5, "rationale": "x"}],
            demoted=[],
        )
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_3_council_inbox_validation, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("draft_idx=5", out)
        self.assertIn("BLOCK-4", out)

    def test_cross_reference_audit_demotion_without_inbox_item_fails(self):
        self._write_inbox([])
        self._write_audit(
            rejected=[],
            demoted=[{"draft_idx": 3, "rationale": "x"}],
        )
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_3_council_inbox_validation, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("tier-5", out)


class _Phase4FixtureBase(unittest.TestCase):
    """Common setup: a tmpdir with quality/ + phase3/ structure and
    a writable role map (v1.5.4 Part 1 replacement for project_type.json).

    The legacy `classification` argument is preserved on the test
    surface; under the hood we synthesize a role map shape that
    derives the same legacy classification via
    quality_gate._phase4_project_type. This keeps the existing
    test cases readable while migrating their underlying contract."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.q = self.repo / "quality"
        self.phase3 = self.q / "phase3"
        self.phase3.mkdir(parents=True)
        quality_gate.FAIL = 0
        quality_gate.WARN = 0

    def tearDown(self):
        self._tmp.cleanup()

    def _write_project_type(self, classification: str, *,
                             override_applied: bool = False,
                             override_rationale: str = "") -> None:
        # Override flags are no longer represented in the role map (the
        # v1.5.3 override-rationale path moved to the debug-utility
        # classifier). Tests that previously exercised override behaviour
        # have been migrated to assert role-map-shape failures instead.
        del override_applied, override_rationale
        files: list[dict] = []
        if classification in ("Skill", "Hybrid"):
            files.append({
                "path": "SKILL.md",
                "role": "skill-prose",
                "size_bytes": 1000,
                "rationale": "fixture skill prose",
            })
        if classification in ("Code", "Hybrid"):
            files.append({
                "path": "lib/main.py",
                "role": "code",
                "size_bytes": 500,
                "rationale": "fixture code surface",
            })
        total = sum(int(f["size_bytes"]) for f in files) or 1
        skill_size = sum(
            int(f["size_bytes"]) for f in files
            if f["role"] in ("skill-prose", "skill-reference")
        )
        code_size = sum(
            int(f["size_bytes"]) for f in files if f["role"] == "code"
        )
        files_by_role: dict = {}
        size_by_role: dict = {}
        for f in files:
            files_by_role[f["role"]] = files_by_role.get(f["role"], 0) + 1
            size_by_role[f["role"]] = (
                size_by_role.get(f["role"], 0) + int(f["size_bytes"])
            )
        (self.q / "exploration_role_map.json").write_text(
            json.dumps({
                "schema_version": "1.0",
                "timestamp_start": "2026-04-27T00:00:00Z",
                "files": files,
                "breakdown": {
                    "files_by_role": files_by_role,
                    "size_by_role": size_by_role,
                    "percentages": {
                        "skill_share": skill_size / total,
                        "code_share": code_size / total,
                        "tool_share": 0.0,
                        "other_share": max(
                            0.0,
                            1.0 - (skill_size / total) - (code_size / total),
                        ),
                    },
                },
            }),
            encoding="utf-8",
        )


class TestCheckSkillSectionReqCoverage(_Phase4FixtureBase):
    """Phase 4 Part C check_skill_section_req_coverage."""

    def _write_coverage(self, sections: list) -> None:
        (self.phase3 / "pass_d_section_coverage.json").write_text(
            json.dumps({
                "schema_version": "1.0",
                "generated_at": "2026-04-27T00:00:00Z",
                "sections": sections,
                "completeness_gaps": [],
            }),
            encoding="utf-8",
        )

    def test_skill_project_section_with_zero_promoted_fails(self):
        self._write_project_type("Skill")
        self._write_coverage([
            {"section_idx": 1, "document": "SKILL.md",
             "heading": "Phase 1", "section_kind": "operational",
             "drafts_total": 0, "drafts_promoted": 0,
             "drafts_pending_council": 0, "marker": None,
             "skip_reason": None},
        ])
        fails, out = _capture_fail_output(
            quality_gate.check_skill_section_req_coverage, self.repo, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("Phase 1", out)
        self.assertIn("0 promoted REQs", out)

    def test_skill_project_all_sections_covered_passes(self):
        self._write_project_type("Skill")
        self._write_coverage([
            {"section_idx": 1, "document": "SKILL.md",
             "heading": "Phase 1", "section_kind": "operational",
             "drafts_total": 5, "drafts_promoted": 3,
             "drafts_pending_council": 2, "marker": None,
             "skip_reason": None},
        ])
        fails, _ = _capture_fail_output(
            quality_gate.check_skill_section_req_coverage, self.repo, self.q
        )
        self.assertEqual(fails, 0)

    def test_code_project_skips(self):
        self._write_project_type("Code")
        # Don't even write coverage; should skip on Code.
        fails, out = _capture_fail_output(
            quality_gate.check_skill_section_req_coverage, self.repo, self.q
        )
        self.assertEqual(fails, 0)
        self.assertIn("skip", out)

    def test_meta_section_with_zero_promoted_does_not_fail(self):
        self._write_project_type("Skill")
        self._write_coverage([
            {"section_idx": 0, "document": "SKILL.md",
             "heading": "Why This Exists", "section_kind": "meta",
             "drafts_total": 0, "drafts_promoted": 0,
             "drafts_pending_council": 0, "marker": None,
             "skip_reason": "meta-allowlist"},
        ])
        fails, _ = _capture_fail_output(
            quality_gate.check_skill_section_req_coverage, self.repo, self.q
        )
        self.assertEqual(fails, 0)


class TestCheckReferenceFileReqCoverage(_Phase4FixtureBase):
    """Phase 4 Part C check_reference_file_req_coverage."""

    def _make_references(self, refs: dict) -> None:
        ref_dir = self.repo / "references"
        ref_dir.mkdir(parents=True, exist_ok=True)
        for name, head_text in refs.items():
            (ref_dir / name).write_text(head_text, encoding="utf-8")

    def _write_formal(self, records: list) -> None:
        with (self.phase3 / "pass_c_formal.jsonl").open(
            "w", encoding="utf-8"
        ) as fh:
            for rec in records:
                fh.write(json.dumps(rec) + "\n")

    def test_skill_project_uncited_normative_reference_fails(self):
        self._write_project_type("Skill")
        self._make_references({"a.md": "# A\nbody\n"})
        self._write_formal([])
        fails, out = _capture_fail_output(
            quality_gate.check_reference_file_req_coverage, self.repo, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("references/a.md", out)

    def test_non_normative_marker_passes(self):
        self._write_project_type("Skill")
        self._make_references({"a.md": "<!-- non-normative -->\n# A\n"})
        self._write_formal([])
        fails, _ = _capture_fail_output(
            quality_gate.check_reference_file_req_coverage, self.repo, self.q
        )
        self.assertEqual(fails, 0)

    def test_cited_reference_passes(self):
        self._write_project_type("Skill")
        self._make_references({"a.md": "# A\nbody\n"})
        self._write_formal([
            {"id": "REQ-001", "source_document": "references/a.md"},
        ])
        fails, _ = _capture_fail_output(
            quality_gate.check_reference_file_req_coverage, self.repo, self.q
        )
        self.assertEqual(fails, 0)

    def test_code_project_skips(self):
        self._write_project_type("Code")
        fails, out = _capture_fail_output(
            quality_gate.check_reference_file_req_coverage, self.repo, self.q
        )
        self.assertEqual(fails, 0)
        self.assertIn("skip", out)

    def test_missing_pass_c_diagnostic_distinguishes_pass_c_from_phase_3(self):
        """v1.5.7 fix Q4: when `phase3/pass_c_formal.jsonl` is missing,
        the diagnostic must say "skill-derivation Pass C not run yet"
        (precise) and NOT just "Phase 3 not run yet" (ambiguous —
        could mean the playbook's Phase 3 Code Review). The on-disk
        directory is named `phase3/` for historical v1.5.3
        compatibility; the canonical name in current prose is
        skill-derivation Pass C."""
        self._write_project_type("Skill")
        self._make_references({"a.md": "# A\n"})
        # Deliberately do NOT write pass_c_formal.jsonl — that's the
        # condition we're testing.
        fails, out = _capture_fail_output(
            quality_gate.check_reference_file_req_coverage, self.repo, self.q
        )
        self.assertEqual(fails, 0)
        # Diagnostic must name skill-derivation Pass C explicitly.
        self.assertIn(
            "skill-derivation Pass C not run yet", out,
            f"Q4 diagnostic must distinguish skill-derivation Pass C "
            f"from playbook Phase 3 Code Review. Got: {out!r}",
        )
        # Must NOT conflate by saying just "Phase 3 not run yet"
        # without the skill-derivation qualifier. The new diagnostic
        # explicitly contrasts the two so an operator looking at the
        # output can tell which artifact is missing.
        self.assertIn(
            "not the playbook's Phase 3 Code Review", out,
            "Q4 diagnostic must explicitly contrast skill-derivation "
            "Pass C with playbook Phase 3 Code Review",
        )


class TestCheckHybridCrossCuttingReqs(_Phase4FixtureBase):
    """Phase 4 Part C check_hybrid_cross_cutting_reqs."""

    def _write_formal(self, records: list) -> None:
        with (self.phase3 / "pass_c_formal.jsonl").open(
            "w", encoding="utf-8"
        ) as fh:
            for rec in records:
                fh.write(json.dumps(rec) + "\n")

    def test_hybrid_with_triangulated_pair_passes(self):
        self._write_project_type("Hybrid")
        self._write_formal([
            {"id": "REQ-001", "source_type": "code-derived",
             "acceptance_criteria": "bin/quality_gate.py runs the gate"},
            {"id": "REQ-002", "source_type": "skill-section",
             "acceptance_criteria":
                 "the gate at bin/quality_gate.py is invoked from Phase 5"},
        ])
        fails, _ = _capture_fail_output(
            quality_gate.check_hybrid_cross_cutting_reqs, self.repo, self.q
        )
        self.assertEqual(fails, 0)

    def test_hybrid_without_code_derived_skips(self):
        self._write_project_type("Hybrid")
        self._write_formal([
            {"id": "REQ-002", "source_type": "skill-section",
             "acceptance_criteria": "skill prose only"},
        ])
        fails, out = _capture_fail_output(
            quality_gate.check_hybrid_cross_cutting_reqs, self.repo, self.q
        )
        self.assertEqual(fails, 0)
        self.assertIn("no code-derived REQs", out)

    def test_skill_project_skips(self):
        self._write_project_type("Skill")
        fails, out = _capture_fail_output(
            quality_gate.check_hybrid_cross_cutting_reqs, self.repo, self.q
        )
        self.assertEqual(fails, 0)
        self.assertIn("skip", out)

    def test_code_project_skips(self):
        self._write_project_type("Code")
        fails, _ = _capture_fail_output(
            quality_gate.check_hybrid_cross_cutting_reqs, self.repo, self.q
        )
        self.assertEqual(fails, 0)


class TestCheckRoleMapConsistency(_Phase4FixtureBase):
    """Phase 4 Part C check_role_map_consistency (v1.5.4 Part 1
    replacement for check_project_type_consistency).

    Runs for all projects but skips silently on missing
    exploration_role_map.json (pre-Phase-1 fixture)."""

    def test_skill_role_map_passes(self):
        self._write_project_type("Skill")
        fails, _ = _capture_fail_output(
            quality_gate.check_role_map_consistency, self.repo, self.q
        )
        self.assertEqual(fails, 0)

    def test_non_object_fails(self):
        (self.q / "exploration_role_map.json").write_text(
            json.dumps([1, 2, 3]), encoding="utf-8"
        )
        fails, out = _capture_fail_output(
            quality_gate.check_role_map_consistency, self.repo, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("not a valid JSON object", out)

    def test_wrong_schema_version_fails(self):
        (self.q / "exploration_role_map.json").write_text(
            json.dumps({
                "schema_version": "9.9",
                "files": [],
                "breakdown": {
                    "files_by_role": {},
                    "size_by_role": {},
                    "percentages": {
                        "skill_share": 0,
                        "code_share": 0,
                        "tool_share": 0,
                        "other_share": 0,
                    },
                },
            }),
            encoding="utf-8",
        )
        fails, out = _capture_fail_output(
            quality_gate.check_role_map_consistency, self.repo, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("schema_version", out)

    def test_missing_breakdown_keys_fails(self):
        (self.q / "exploration_role_map.json").write_text(
            json.dumps({
                "schema_version": "1.0",
                "files": [],
                "breakdown": {
                    "files_by_role": {},
                    "size_by_role": {},
                    "percentages": {"skill_share": 0},  # only one of four
                },
            }),
            encoding="utf-8",
        )
        fails, out = _capture_fail_output(
            quality_gate.check_role_map_consistency, self.repo, self.q
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("missing keys", out)

    def test_missing_role_map_skips_silently(self):
        # Pre-Phase-1 fixture: exploration_role_map.json absent.
        fails, out = _capture_fail_output(
            quality_gate.check_role_map_consistency, self.repo, self.q
        )
        self.assertEqual(fails, 0)
        self.assertIn("skip", out)


# v1.5.6 (QG-fail-1, QG-fail-2): two self-consistency failures the
# v1.5.6 self-bootstrap surfaced.
#   - QG-fail-1: `.gitkeep` is the documented sentinel for
#     `reference_docs/cite/` but the gate rejected it as
#     "unsupported extension."
#   - QG-fail-2: REQs with `source_type=docs-derived` (REQs derived
#     from operator-supplied target-repo `reference_docs/`) were
#     rejected by §10 invariant #21 because the allowlist didn't
#     include the value, even though shipped Phase 2 LLM output
#     emits it.
class TestV156SelfConsistencyGitkeep(V150FixtureBase):

    def _cite(self):
        c = self.repo / "reference_docs" / "cite"
        c.mkdir(parents=True)
        return c

    def test_gitkeep_in_cite_is_accepted(self):
        """QG-fail-1: `.gitkeep` in reference_docs/cite/ must not
        trigger the unsupported-extension fail."""
        cite = self._cite()
        (cite / ".gitkeep").write_text("", encoding="utf-8")
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_cite_extensions, self.repo
        )
        self.assertEqual(
            fails, 0,
            f".gitkeep should not trigger unsupported-extension fail; "
            f"output: {out}",
        )
        self.assertNotIn("unsupported extension", out)

    def test_gitkeep_alongside_real_doc_still_passes(self):
        """`.gitkeep` plus a real .md citable doc both pass — the
        sentinel is silent and the real doc takes the PASS line."""
        cite = self._cite()
        (cite / ".gitkeep").write_text("", encoding="utf-8")
        (cite / "spec.md").write_text("# spec\n", encoding="utf-8")
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_cite_extensions, self.repo
        )
        self.assertEqual(fails, 0, out)
        self.assertIn("supported extensions", out)

    def test_unsupported_extension_alongside_gitkeep_still_fails(self):
        """`.gitkeep` exempt status MUST NOT mask other unsupported
        files. A `.docx` next to `.gitkeep` still trips the gate."""
        cite = self._cite()
        (cite / ".gitkeep").write_text("", encoding="utf-8")
        (cite / "stale.docx").write_bytes(b"PK\x03\x04binary\n")
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_0_cite_extensions, self.repo
        )
        self.assertGreaterEqual(fails, 1)
        self.assertIn("stale.docx", out)
        self.assertIn("unsupported extension", out)


class TestPhase4ProjectTypeArtifactShapeFallback(unittest.TestCase):
    """v1.5.7 fix Q1/Q5 (option c): when the Phase-1 role map is
    absent, `_phase4_project_type` falls back to artifact-shape
    detection. Returns 'Code' when both skill-indicator paths are
    absent (no root SKILL.md, no references/ directory); returns
    None otherwise so the gate emits an honest "role map not yet
    produced" SKIP rather than guessing Skill/Hybrid."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        self.q = self.repo / "quality"
        self.q.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def test_code_fixture_no_role_map_returns_code(self):
        """Code project: no SKILL.md, no references/, role map absent.
        Pre-fix this returned None and Phase 4 checks emitted
        confusing "project_type=None" SKIP lines. Post-Q1/Q5 the
        artifact-shape fallback returns 'Code' and the SKIP message
        clearly says "not applicable for Code projects"."""
        # Source files only — the realistic Code-project shape.
        (self.repo / "src").mkdir()
        (self.repo / "src" / "main.py").write_text("print('hi')\n", encoding="utf-8")
        result = quality_gate._phase4_project_type(self.q)
        self.assertEqual(
            result, "Code",
            "Code-shaped repo (no SKILL.md, no references/) with no role "
            "map must derive 'Code' via artifact-shape fallback "
            "(v1.5.7 Q1/Q5 option c)",
        )

    def test_hybrid_fixture_with_role_map_returns_hybrid(self):
        """Hybrid project: SKILL.md + source files, role map present.
        Role map takes precedence over artifact-shape fallback."""
        (self.repo / "SKILL.md").write_text(
            "---\nname: quality-playbook\n---\n", encoding="utf-8",
        )
        (self.repo / "src").mkdir()
        (self.repo / "src" / "main.py").write_text("ok\n", encoding="utf-8")
        # Role map with both skill-prose and code roles.
        (self.q / "exploration_role_map.json").write_text(
            json.dumps({
                "files": [
                    {"path": "SKILL.md", "role": "skill-prose"},
                    {"path": "src/main.py", "role": "code"},
                ],
            }),
            encoding="utf-8",
        )
        result = quality_gate._phase4_project_type(self.q)
        self.assertEqual(result, "Hybrid")

    def test_skill_fixture_with_role_map_returns_skill(self):
        """Skill project: SKILL.md + references/, no code, role map
        with skill-prose only."""
        (self.repo / "SKILL.md").write_text(
            "---\nname: quality-playbook\n---\n", encoding="utf-8",
        )
        (self.repo / "references").mkdir()
        (self.q / "exploration_role_map.json").write_text(
            json.dumps({
                "files": [
                    {"path": "SKILL.md", "role": "skill-prose"},
                ],
            }),
            encoding="utf-8",
        )
        result = quality_gate._phase4_project_type(self.q)
        self.assertEqual(result, "Skill")

    def test_ambiguous_no_role_map_with_skill_md_returns_none(self):
        """Ambiguous shape: SKILL.md present but no role map. The
        artifact-shape fallback returns None (not 'Skill' — that
        would be guessing); the gate then emits a "role map absent"
        SKIP rather than a "Code project not applicable" one."""
        (self.repo / "SKILL.md").write_text("---\nfoo: bar\n---\n", encoding="utf-8")
        result = quality_gate._phase4_project_type(self.q)
        self.assertIsNone(
            result,
            "with SKILL.md present and no role map, the fallback must "
            "be conservative (return None, not guess Skill)",
        )


class TestV156SelfConsistencyDocsDerived(V150FixtureBase):

    def test_docs_derived_in_allowlist(self):
        """QG-fail-2: source_type=docs-derived must appear in the
        v1.5.3 source_type allowlist constant."""
        self.assertIn(
            "docs-derived",
            quality_gate._V153_VALID_SOURCE_TYPES,
            "docs-derived must be in the v1.5.3 source_type allowlist "
            "(QG-fail-2 from v1.5.6 self-bootstrap).",
        )

    def test_docs_derived_req_passes_invariant_21(self):
        """End-to-end on a real REQ record: a v1.5.3-shaped requirements
        manifest containing a REQ with source_type=docs-derived must
        pass check_v1_5_3_source_type_validation. Mirrors the
        bootstrap's REQ-015..REQ-018 records."""
        self.write_manifest(
            "requirements_manifest.json",
            "records",
            [
                {
                    "id": "REQ-001",
                    "summary": "Code-derived requirement",
                    "source_type": "code-derived",
                },
                {
                    "id": "REQ-015",
                    "summary": "Derived from target repo's reference_docs/",
                    "source_type": "docs-derived",
                },
            ],
        )
        fails, out = _capture_fail_output(
            quality_gate.check_v1_5_3_source_type_validation, self.q
        )
        self.assertEqual(
            fails, 0,
            f"docs-derived must pass invariant #21 source_type check; "
            f"output: {out}",
        )
        self.assertIn("source_type validation complete", out)


if __name__ == "__main__":
    unittest.main()
