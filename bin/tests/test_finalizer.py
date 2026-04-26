"""Tests for bin/run_playbook.py::_finalize_iteration (C13.9).

The finalizer subprocesses quality_gate.py against a target repo, captures
its real output to quality/results/quality-gate.log (preserving the existing
artifact contract), and appends a structured ## Run finalization block to
quality/PROGRESS.md. Mocks subprocess.run so tests don't depend on the live
gate script being installed.
"""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bin.run_playbook import _finalize_iteration


class _FakeCompleted:
    def __init__(self, returncode: int, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _make_repo(tmp: Path, *, with_gate: bool = True, with_progress: str = None,
               bug_writeup_count: int = 0) -> Path:
    """Build a minimal repo at ``tmp`` with quality/ dir and optional fixtures."""
    repo = tmp / "repo"
    repo.mkdir()
    (repo / "quality").mkdir()
    if with_gate:
        gate = repo / ".github" / "skills"
        gate.mkdir(parents=True)
        (gate / "quality_gate.py").write_text("# stub\n", encoding="utf-8")
    if with_progress is not None:
        (repo / "quality" / "PROGRESS.md").write_text(with_progress, encoding="utf-8")
    if bug_writeup_count > 0:
        writeups = repo / "quality" / "writeups"
        writeups.mkdir()
        for i in range(1, bug_writeup_count + 1):
            (writeups / f"BUG-{i:03d}.md").write_text(f"# BUG-{i:03d}\n", encoding="utf-8")
    return repo


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def _run_phase6(finalizer_status, gate_log_text):
    """Drive _log_phase_completion for phase 6 and return the gate_verdict
    that would be written to INDEX. Used by Test 15 and the Round 7 Finding B
    regression test."""
    from bin import run_playbook

    with tempfile.TemporaryDirectory() as d:
        repo = Path(d) / "repo"
        repo.mkdir()
        (repo / "quality").mkdir()
        (repo / "quality" / "results").mkdir()
        (repo / "quality" / "results" / "quality-gate.log").write_text(
            gate_log_text, encoding="utf-8"
        )
        args = _Args()
        with mock.patch.object(run_playbook, "_finalize_iteration",
                               return_value=finalizer_status), \
             mock.patch.object(run_playbook, "write_live_index_final") as mock_index, \
             mock.patch.object(run_playbook, "archive_lib"):
            run_playbook._log_phase_completion(
                repo, "6", repo / "run.log", args, "20260425-120000",
            )
        if mock_index.call_args is None:
            return None
        return mock_index.call_args.kwargs.get("gate_verdict")


class FinalizerUnitTests(unittest.TestCase):

    # ---- Test 1 ----
    def test_finalizer_writes_log_on_clean_gate_run(self):
        with tempfile.TemporaryDirectory() as d:
            repo = _make_repo(Path(d))
            log_file = repo / "run.log"
            with mock.patch("bin.run_playbook.subprocess.run",
                            return_value=_FakeCompleted(0, stdout="GATE PASSED\n")):
                status = _finalize_iteration(repo, "post-test", log_file)
            self.assertEqual(status, "pass")
            log = _read(repo / "quality" / "results" / "quality-gate.log")
            self.assertIn("GATE PASSED", log)

    # ---- Test 2 ----
    def test_finalizer_writes_log_on_failing_gate(self):
        with tempfile.TemporaryDirectory() as d:
            repo = _make_repo(Path(d))
            log_file = repo / "run.log"
            with mock.patch("bin.run_playbook.subprocess.run",
                            return_value=_FakeCompleted(1, stdout="GATE FAILED: uncovered cells\n")):
                status = _finalize_iteration(repo, "post-test", log_file)
            self.assertEqual(status, "fail")
            log = _read(repo / "quality" / "results" / "quality-gate.log")
            self.assertIn("GATE FAILED: uncovered cells", log)

    # ---- Test 3 ----
    def test_finalizer_returns_aborted_regardless_of_gate_exit(self):
        with tempfile.TemporaryDirectory() as d:
            repo = _make_repo(Path(d))
            log_file = repo / "run.log"
            with mock.patch("bin.run_playbook.subprocess.run",
                            return_value=_FakeCompleted(0, stdout="GATE PASSED\n")):
                status = _finalize_iteration(
                    repo, "abort-during-adversarial", log_file,
                    aborted=True, abort_reason="runner exited 2",
                )
            self.assertEqual(status, "aborted")
            progress = _read(repo / "quality" / "PROGRESS.md")
            self.assertIn("Gate status: ABORTED", progress)
            self.assertIn("Abort reason: runner exited 2", progress)
            # The gate ran; its output is captured but not authoritative.
            log = _read(repo / "quality" / "results" / "quality-gate.log")
            self.assertIn("GATE PASSED", log)

    # ---- Test 4 ----
    def test_finalizer_appends_to_progress_md(self):
        original = "# Progress\n\n## Phase 1 complete\n\n2026-04-25T12:00:00Z\n"
        with tempfile.TemporaryDirectory() as d:
            repo = _make_repo(Path(d), with_progress=original)
            log_file = repo / "run.log"
            with mock.patch("bin.run_playbook.subprocess.run",
                            return_value=_FakeCompleted(0, stdout="GATE PASSED\n")):
                _finalize_iteration(repo, "post-phase-6", log_file)
            progress = _read(repo / "quality" / "PROGRESS.md")
            self.assertTrue(progress.startswith(original),
                            "Original PROGRESS.md content must be preserved verbatim.")
            self.assertIn("## Run finalization (post-phase-6)", progress)

    # ---- Test 5 ----
    def test_finalizer_creates_progress_md_when_absent(self):
        with tempfile.TemporaryDirectory() as d:
            repo = _make_repo(Path(d))  # no PROGRESS.md
            log_file = repo / "run.log"
            self.assertFalse((repo / "quality" / "PROGRESS.md").exists())
            with mock.patch("bin.run_playbook.subprocess.run",
                            return_value=_FakeCompleted(0, stdout="GATE PASSED\n")):
                _finalize_iteration(repo, "post-singlepass", log_file)
            progress = _read(repo / "quality" / "PROGRESS.md")
            self.assertIn("## Run finalization (post-singlepass)", progress)

    # ---- Test 6 ----
    def test_finalizer_idempotent_call_appends_second_block(self):
        with tempfile.TemporaryDirectory() as d:
            repo = _make_repo(Path(d))
            log_file = repo / "run.log"
            with mock.patch("bin.run_playbook.subprocess.run",
                            return_value=_FakeCompleted(0, stdout="GATE PASSED\n")):
                _finalize_iteration(repo, "post-test", log_file)
                _finalize_iteration(repo, "post-test", log_file)
            progress = _read(repo / "quality" / "PROGRESS.md")
            # Two blocks, both with the same label.
            self.assertEqual(progress.count("## Run finalization (post-test)"), 2)
            # Log got overwritten — only one copy of the gate output.
            log = _read(repo / "quality" / "results" / "quality-gate.log")
            self.assertEqual(log.count("GATE PASSED"), 1)

    # ---- Test 7 ----
    def test_finalizer_handles_missing_gate_script(self):
        with tempfile.TemporaryDirectory() as d:
            repo = _make_repo(Path(d), with_gate=False)
            log_file = repo / "run.log"
            with mock.patch("bin.run_playbook.subprocess.run") as mock_run:
                status = _finalize_iteration(repo, "post-test", log_file)
            self.assertEqual(status, "fail")
            mock_run.assert_not_called()
            progress = _read(repo / "quality" / "PROGRESS.md")
            self.assertIn("Gate status: FAIL", progress)
            self.assertIn("not produced — gate script not found", progress)

    # ---- Test 8 ----
    def test_finalizer_handles_subprocess_timeout(self):
        with tempfile.TemporaryDirectory() as d:
            repo = _make_repo(Path(d))
            log_file = repo / "run.log"
            timeout_exc = subprocess.TimeoutExpired(cmd=["python3"], timeout=120)
            with mock.patch("bin.run_playbook.subprocess.run", side_effect=timeout_exc):
                status = _finalize_iteration(repo, "post-test", log_file)
            self.assertEqual(status, "fail")
            log = _read(repo / "quality" / "results" / "quality-gate.log")
            self.assertIn("gate timed out after 120s", log)

    # ---- Test 9 ----
    def test_finalizer_skips_when_quality_missing(self):
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d) / "repo"
            repo.mkdir()
            # Deliberately no quality/ directory.
            log_file = repo / "run.log"
            with mock.patch("bin.run_playbook.subprocess.run") as mock_run:
                status = _finalize_iteration(repo, "post-test", log_file)
            self.assertEqual(status, "pass")
            mock_run.assert_not_called()
            self.assertFalse((repo / "quality").exists(),
                             "Finalizer must not create quality/ when it doesn't exist.")

    # ---- Test 10 ----
    def test_finalizer_bug_count_matches_count_bug_writeups(self):
        with tempfile.TemporaryDirectory() as d:
            repo = _make_repo(Path(d), bug_writeup_count=5)
            log_file = repo / "run.log"
            with mock.patch("bin.run_playbook.subprocess.run",
                            return_value=_FakeCompleted(0, stdout="GATE PASSED\n")):
                _finalize_iteration(repo, "post-test", log_file)
            progress = _read(repo / "quality" / "PROGRESS.md")
            self.assertIn("Bug count: 5", progress)

    # ---- Test 11 ----
    def test_finalizer_does_not_overwrite_progress_with_synthetic_receipt(self):
        """The receipt is the gate's real output, written to quality-gate.log
        only. PROGRESS.md must NOT mirror that output (regression guard
        against the rev-1 design that wrote synthetic schema there)."""
        gate_output = "GATE PASSED\nDistinctive marker line for assertion\n"
        with tempfile.TemporaryDirectory() as d:
            repo = _make_repo(Path(d))
            # Pre-seed log with a fixture string we expect to be overwritten.
            (repo / "quality" / "results").mkdir(parents=True, exist_ok=True)
            (repo / "quality" / "results" / "quality-gate.log").write_text(
                "OLD STALE CONTENT", encoding="utf-8",
            )
            log_file = repo / "run.log"
            with mock.patch("bin.run_playbook.subprocess.run",
                            return_value=_FakeCompleted(0, stdout=gate_output)):
                _finalize_iteration(repo, "post-test", log_file)
            log = _read(repo / "quality" / "results" / "quality-gate.log")
            self.assertNotIn("OLD STALE CONTENT", log)
            self.assertIn("Distinctive marker line for assertion", log)
            progress = _read(repo / "quality" / "PROGRESS.md")
            self.assertNotIn("Distinctive marker line for assertion", progress,
                             "PROGRESS.md must not mirror gate output (rev-1 regression guard).")


class _Args:
    """Lightweight argparse.Namespace stand-in for integration tests."""
    def __init__(self, **kwargs):
        defaults = {
            "runner": "claude",
            "model": None,
            "no_stdout_echo": True,  # silence orchestrator banner output
            "no_formal_docs": True,
            "verbose": False,
            "quiet": True,
            "progress_interval": 60,
            "pace_seconds": 0,
            "next_iteration": False,
            "strategy": None,
            "_iterations_explicit": False,
            "no_seeds": False,
        }
        defaults.update(kwargs)
        for k, v in defaults.items():
            setattr(self, k, v)


def _make_iteration_repo(tmp: Path) -> Path:
    """Build a repo with quality/EXPLORATION.md so run_one_iterations
    doesn't bail early."""
    repo = _make_repo(tmp, with_gate=True, with_progress="# Progress\n")
    (repo / "quality" / "EXPLORATION.md").write_text("# Exploration\n", encoding="utf-8")
    return repo


class FinalizerCallSiteIntegrationTests(unittest.TestCase):
    """Integration tests for the four call sites the finalizer is wired into.

    Mock run_prompt so no real LLM is invoked; mock subprocess.run so no real
    gate is invoked. Assert _finalize_iteration is called with the right
    label/aborted parameters at each site.
    """

    # ---- Test 12: run_one_iterations success path (site 1) ----
    def test_run_one_iterations_calls_finalizer_after_each_iteration(self):
        from bin import run_playbook
        with tempfile.TemporaryDirectory() as d:
            repo = _make_iteration_repo(Path(d))
            # _iterations_explicit=True bypasses the diminishing-returns
            # early-stop so both strategies actually run under the mock
            # (which produces 0 bugs both before and after).
            args = _Args(_iterations_explicit=True)
            with mock.patch.object(run_playbook, "run_prompt", return_value=0), \
                 mock.patch.object(run_playbook, "_finalize_iteration", return_value="pass") as mock_fin, \
                 mock.patch.object(run_playbook, "configure_logging", return_value=repo / "run.log"), \
                 mock.patch.object(run_playbook, "print_startup_banner"), \
                 mock.patch.object(run_playbook, "docs_present", return_value=True):
                exit_code = run_playbook.run_one_iterations(
                    repo, ["gap", "unfiltered"], args, "20260425-120000",
                )
            self.assertEqual(exit_code, 0)
            labels = [call.kwargs.get("label") for call in mock_fin.call_args_list]
            self.assertEqual(labels, ["post-gap", "post-unfiltered"])
            for call in mock_fin.call_args_list:
                self.assertFalse(call.kwargs.get("aborted", False))

    # ---- Test 15: Phase 6 finalizer status maps to INDEX verdict (site 5) ----
    def test_phase6_finalizer_status_maps_to_index_verdict(self):
        """The C13.9 brief mapping: finalizer 'pass' → 'pass',
        'fail' → 'fail', 'aborted' → 'partial' (INDEX schema accepts
        only pass/fail/partial). Verified by intercepting
        write_live_index_final and checking gate_verdict."""
        # finalizer pass + clean log → pass
        self.assertEqual(_run_phase6("pass", "RESULT: GATE PASSED\n"), "pass")
        # finalizer fail + failure log → fail
        self.assertEqual(_run_phase6("fail", "RESULT: GATE FAILED — 3 check(s) must be fixed\n"), "fail")
        # finalizer aborted (regardless of gate log content) → partial
        self.assertEqual(_run_phase6("aborted", "RESULT: GATE PASSED\n"), "partial")
        # finalizer pass but log doesn't pass _gate_pass — falls to fail/partial
        # branch; warn → partial (preserves historical fallback)
        self.assertEqual(_run_phase6("pass", "RESULT: 0 FAIL, 5 WARN\n"), "partial")

    # ---- Round 7 Finding B: fail must not be demoted to partial on warn substring ----
    def test_phase6_fail_with_warn_in_log_maps_to_fail_not_partial(self):
        """A definite gate failure must not be demoted to 'partial' just
        because the gate log's last line contains the substring 'warn'."""
        self.assertEqual(
            _run_phase6("fail", "Total: 5 FAIL, 3 WARN\n"),
            "fail",
        )
        self.assertEqual(
            _run_phase6("fail", "WARN: quality/REQUIREMENTS.md: missing section\n"),
            "fail",
        )

    # ---- Round 8 Finding 6: truth-table cell (pass, gate_passed=False, no warn) ----
    def test_phase6_pass_with_gate_failure_no_warn_maps_to_fail(self):
        """Round 8 truth-table completion: (pass, gate_passed=False, no warn) → fail.

        The Round 7 Finding B fix guarded the warn-substring demotion to require
        finalizer_status == "pass". The orthogonal cell — finalizer reports
        "pass" but the gate log shows a hard failure with no warn substring —
        must fall through to the else branch and produce "fail". This cell
        is correctly implemented at bin/run_playbook.py:2165 but had no
        explicit test before this commit; a future refactor could regress
        it silently."""
        self.assertEqual(
            _run_phase6("pass", "RESULT: GATE FAILED — 3 check(s) must be fixed\n"),
            "fail",
        )
        self.assertEqual(
            _run_phase6("pass", "FAIL: quality/BUGS.md: heading missing\n"),
            "fail",
        )

    # ---- Test 14a: run_one_singlepass iteration branch success (site 3) ----
    def test_run_one_singlepass_iteration_branch_calls_finalizer_on_success(self):
        """The rev-1-missed call site. --next-iteration --strategy adversarial
        goes through run_one_singlepass (not run_one_iterations) and must also
        finalize."""
        from bin import run_playbook
        with tempfile.TemporaryDirectory() as d:
            repo = _make_iteration_repo(Path(d))
            args = _Args(next_iteration=True, strategy=["adversarial"])
            with mock.patch.object(run_playbook, "run_prompt", return_value=0), \
                 mock.patch.object(run_playbook, "_finalize_iteration", return_value="pass") as mock_fin, \
                 mock.patch.object(run_playbook, "configure_logging", return_value=repo / "run.log"), \
                 mock.patch.object(run_playbook, "print_startup_banner"), \
                 mock.patch.object(run_playbook, "docs_present", return_value=True), \
                 mock.patch.object(run_playbook.lib, "cleanup_repo", lambda d: None), \
                 mock.patch.object(run_playbook, "final_artifact_gaps", return_value=[]):
                exit_code = run_playbook.run_one_singlepass(repo, args, "20260425-120000")
            self.assertEqual(exit_code, 0)
            self.assertEqual(mock_fin.call_count, 1)
            call = mock_fin.call_args_list[0]
            self.assertEqual(call.kwargs.get("label"), "post-adversarial")
            self.assertFalse(call.kwargs.get("aborted", False))

    # ---- Test 14b: run_one_singlepass iteration branch abort (site 4) ----
    def test_run_one_singlepass_iteration_branch_calls_finalizer_on_abort(self):
        from bin import run_playbook
        with tempfile.TemporaryDirectory() as d:
            repo = _make_iteration_repo(Path(d))
            args = _Args(next_iteration=True, strategy=["adversarial"])
            with mock.patch.object(run_playbook, "run_prompt", return_value=2), \
                 mock.patch.object(run_playbook, "_finalize_iteration", return_value="aborted") as mock_fin, \
                 mock.patch.object(run_playbook, "configure_logging", return_value=repo / "run.log"), \
                 mock.patch.object(run_playbook, "print_startup_banner"), \
                 mock.patch.object(run_playbook, "docs_present", return_value=True):
                exit_code = run_playbook.run_one_singlepass(repo, args, "20260425-120000")
            self.assertEqual(exit_code, 2)
            self.assertEqual(mock_fin.call_count, 1)
            call = mock_fin.call_args_list[0]
            self.assertEqual(call.kwargs.get("label"), "abort-during-adversarial")
            self.assertTrue(call.kwargs.get("aborted"))
            self.assertEqual(call.kwargs.get("abort_reason"), "runner exited 2")

    # ---- Test 14c: run_one_singlepass baseline branch (no --next-iteration) ----
    def test_run_one_singlepass_baseline_branch_calls_finalizer_with_singlepass_label(self):
        """--phase all goes through this function with next_iteration=False;
        finalizer label must be 'post-singlepass', not strategy-specific."""
        from bin import run_playbook
        with tempfile.TemporaryDirectory() as d:
            repo = _make_iteration_repo(Path(d))
            args = _Args(next_iteration=False, strategy=None)
            with mock.patch.object(run_playbook, "run_prompt", return_value=0), \
                 mock.patch.object(run_playbook, "_finalize_iteration", return_value="pass") as mock_fin, \
                 mock.patch.object(run_playbook, "configure_logging", return_value=repo / "run.log"), \
                 mock.patch.object(run_playbook, "print_startup_banner"), \
                 mock.patch.object(run_playbook, "docs_present", return_value=True), \
                 mock.patch.object(run_playbook, "archive_previous_run"), \
                 mock.patch.object(run_playbook, "write_live_index_stub"), \
                 mock.patch.object(run_playbook.lib, "cleanup_repo", lambda d: None), \
                 mock.patch.object(run_playbook, "final_artifact_gaps", return_value=[]):
                exit_code = run_playbook.run_one_singlepass(repo, args, "20260425-120000")
            self.assertEqual(exit_code, 0)
            self.assertEqual(mock_fin.call_count, 1)
            call = mock_fin.call_args_list[0]
            self.assertEqual(call.kwargs.get("label"), "post-singlepass")

    # ---- Test 13: run_one_iterations abort path (site 2) ----
    def test_run_one_iterations_calls_finalizer_on_abort(self):
        from bin import run_playbook
        with tempfile.TemporaryDirectory() as d:
            repo = _make_iteration_repo(Path(d))
            args = _Args()
            with mock.patch.object(run_playbook, "run_prompt", return_value=2), \
                 mock.patch.object(run_playbook, "_finalize_iteration", return_value="aborted") as mock_fin, \
                 mock.patch.object(run_playbook, "configure_logging", return_value=repo / "run.log"), \
                 mock.patch.object(run_playbook, "print_startup_banner"), \
                 mock.patch.object(run_playbook, "docs_present", return_value=True):
                exit_code = run_playbook.run_one_iterations(
                    repo, ["adversarial"], args, "20260425-120000",
                )
            self.assertEqual(exit_code, 2)
            self.assertEqual(mock_fin.call_count, 1)
            call = mock_fin.call_args_list[0]
            self.assertEqual(call.kwargs.get("label"), "abort-during-adversarial")
            self.assertTrue(call.kwargs.get("aborted"))
            self.assertEqual(call.kwargs.get("abort_reason"), "runner exited 2")


if __name__ == "__main__":
    unittest.main()
