"""v1.5.7 103 — live ``_execute_one_run`` (real composition).

101 wired ``BuilderHooks``; 102 wired live default builders;
neither exercised the REAL per-run composition because
``_execute_one_run``'s production path was a ``raise
NotImplementedError`` stub. 103 wires the real composition
(clone → install → launch → facts → grade). These tests
exercise that real composition with **only** ``runner.launch_run``
patched — the only stub-able piece per the instruction:
  * ``prepare`` does a real local `git clone` from a tiny
    fixture repo + a real `install_skill`.
  * ``facts.extract_facts`` re-runs the INSTALLED gate over the
    canned ``quality/`` tree the patched launch wrote.
  * ``grade_expect`` runs for real against the plan's ``expect``.

Mutation-bite: revert ``_execute_one_run``'s production path to
the NotImplementedError stub and ``test_solid_run_grades_MET``
errors — the test exercises the live path, not a fake_run
shortcut.

Segregated suite per Implementation Plan §4. These tests are
slower than parse-fixture tests (~5-10s) because they install
the skill + re-run the real gate; they land in the segregated
suite so they're CI'd but don't block the release gate.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

from bin.harness import plan_runner as PR
from bin.harness import runner as RUN
from bin.harness import schema as S


# Reuse the canonical fixture builders from the gate test suite
# (same approach as test_facts_real_gate_integration.py — keeps
# fixture drift coordinated with the gate).
_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / ".github" / "skills"
                        / "quality_gate" / "tests"))
from test_quality_gate import (  # noqa: E402
    minimal_zero_bug_tree,
    add_one_bug,
    write_tree,
)


_REAL_PY_FUNCTIONAL_TEST = """\
import unittest

class FunctionalTests(unittest.TestCase):
    def test_thing(self):
        self.assertEqual(1 + 1, 2)
"""


def _make_local_git_repo(parent: Path) -> str:
    """Create a tiny local git repo and return a ``file://`` URL
    so ``prepare.clone_worktree`` does a real clone (no network)."""
    repo = parent / "fixture-repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=str(repo), check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=str(repo), check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(repo), check=True, capture_output=True,
    )
    (repo / "README.md").write_text("# fixture\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", "README.md"],
        cwd=str(repo), check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(repo), check=True, capture_output=True,
    )
    return f"file://{repo}"


def _mk_plan_run(*, repo_url: str, expect: dict,
                  index: int = 0) -> PR.PlanRun:
    """Build a PlanRun directly (skips parse_plan so the test is
    explicit about the shape it's exercising)."""
    return PR.PlanRun(
        index=index,
        description=f"live-composition test run-{index}",
        repo=repo_url,
        ref="main",
        runner=S.Runner.CLAUDE,
        model="opus",
        channel=S.InstallChannel.CLONE,
        prep="acceptance",
        docs="gather",
        expect=expect,
    )


def _patched_launch_factory(populate_quality_tree,
                              *, exit_code: int = 0,
                              terminal: S.TerminalState
                                  = S.TerminalState.COMPLETED):
    """Build a fake `launch_run` that, on call: populates the
    target's ``quality/`` tree via ``populate_quality_tree`` and
    returns a LaunchResult with the requested terminal."""

    def _fake_launch(spec: RUN.LaunchSpec) -> RUN.LaunchResult:
        spec.run_dir.mkdir(parents=True, exist_ok=True)
        # Write a stub stream.ndjson so the transcript-read path
        # in _execute_one_run_production has something to read.
        stream_path = spec.run_dir / "stream.ndjson"
        stream_path.write_text(
            "{\"event\":\"phase1_ingest_invocation_hint\"}\n",
            encoding="utf-8",
        )
        # Populate the canned quality/ tree into the cloned
        # target, so the real installed gate has something to
        # grade.
        populate_quality_tree(spec.target_dir)
        return RUN.LaunchResult(
            pid=99999,
            started_at="2026-05-26T00:00:00Z",
            ended_at="2026-05-26T00:00:05Z",
            exit_code=exit_code,
            terminal_state=terminal,
            cli_command="(patched-launch)",
            cwd=str(spec.target_dir),
            env_snapshot={"CLAUDECODE": "1"},
            stream_path=stream_path,
        )
    return _fake_launch


def _populate_solid(target: Path) -> None:
    """Canned solid ✅ PASS quality/ tree (one confirmed bug +
    real assertion + complete TDD evidence)."""
    tree = minimal_zero_bug_tree()
    add_one_bug(tree, bug_id="BUG-001")
    tree["quality/test_functional.py"] = _REAL_PY_FUNCTIONAL_TEST
    tree["quality/PROGRESS.md"] = (
        "# Progress\n\nSkill version: 1.4.4\n\n"
        "## Phases\n- [x] Phase 1\n- [x] Phase 2\n- [x] Phase 3\n"
        "- [x] Phase 4\n- [x] Phase 5\n- [x] Phase 6\n"
        "## Terminal Gate Verification\n"
    )
    write_tree(target, tree)


# ---------------------------------------------------------------------------
# Task A.1 — the real composition runs end-to-end
# ---------------------------------------------------------------------------


class LiveExecuteOneRunSolidTests(unittest.TestCase):
    """The mutation-bite: revert ``_execute_one_run``'s
    production path to the NotImplementedError stub and these
    tests error — they exercise the live composition, not a
    fake_run shortcut."""

    def test_solid_run_grades_MET(self) -> None:
        """End-to-end: real local clone + real install + patched
        launch (writes solid tree) + REAL installed-gate re-run +
        REAL grade_expect against ``expect={gate_result: PASS}``
        ⇒ result=MET; receipts written; gate column PASSED."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            repo_url = _make_local_git_repo(tmp_p)
            plan_run = _mk_plan_run(
                repo_url=repo_url,
                expect={"gate_result": "PASS"},
            )
            harness_run = tmp_p / "harness-run"
            harness_run.mkdir()
            with mock.patch(
                "bin.harness.runner.launch_run",
                side_effect=_patched_launch_factory(_populate_solid),
            ):
                outcome = PR._execute_one_run(
                    plan_run, harness_run,
                    hooks=PR.PlanRunnerHooks(),  # NO fake_run
                    artifact_map={},
                )
            run_dir = harness_run / "run-00"
            # Real receipts landed.
            self.assertTrue(
                (run_dir / "invocation.json").is_file(),
                "live path must write invocation.json",
            )
            self.assertTrue(
                (run_dir / "facts.json").is_file(),
                "COMPLETED + real gate re-run ⇒ facts.json",
            )
            self.assertTrue(
                (run_dir / "grading.json").is_file(),
                "COMPLETED ⇒ grading.json",
            )
            # Real clone happened (target/ has the README from
            # the fixture repo + the installed skill).
            target = run_dir / "target"
            self.assertTrue(
                (target / "README.md").is_file(),
                "clone must have produced the fixture's README",
            )
            self.assertTrue(
                (target / ".claude" / "skills"
                  / "quality-playbook").is_dir(),
                "install_skill must have produced the installed "
                "skill tree under .claude/skills/",
            )
            # Real grade.
            facts = json.loads(
                (run_dir / "facts.json").read_text(
                    encoding="utf-8")
            )
            self.assertEqual(facts["gate"]["gate_result"], "PASS")
            self.assertEqual(outcome.gate_verdict, "PASSED")
            self.assertEqual(outcome.result, "MET")
            self.assertEqual(
                outcome.terminal_state,
                S.TerminalState.COMPLETED.value,
            )

    def test_invocation_json_carries_local_artifact_when_present(
            self) -> None:
        """The 101 artifact_used.json wiring is preserved AND
        invocation.json carries the same local_artifact dict
        when the run's channel matches an artifact_map entry —
        so the production receipt absorbs the 101 provenance
        per 103 Task A.4."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            repo_url = _make_local_git_repo(tmp_p)
            # Plan run with channel=pip-local-wheel + matching
            # artifact_map entry (we stub the wheel file).
            wheel = tmp_p / "fake.whl"
            wheel.write_bytes(b"FAKE WHEEL")
            plan_run = PR.PlanRun(
                index=0,
                description="invocation-records-artifact",
                repo=repo_url, ref="main",
                runner=S.Runner.CLAUDE, model="opus",
                channel=S.InstallChannel.PIP_LOCAL_WHEEL,
                prep="acceptance", docs="gather",
                expect={"gate_result": "PASS"},
            )
            artifact_map = {
                S.InstallChannel.PIP_LOCAL_WHEEL: {
                    "path": str(wheel),
                    "filename": "fake.whl",
                    "sha256": "deadbeef",
                },
            }
            harness_run = tmp_p / "harness-run"
            harness_run.mkdir()
            # install_skill on a pip-local-wheel channel will
            # try to uvx install — patch that out too so this
            # test doesn't depend on uvx + a real wheel format.
            # We patch _run_install_for_axes so prepare's
            # install step is a no-op.
            with mock.patch(
                "bin.harness.prepare._run_install_for_axes",
                return_value=None,
            ), mock.patch(
                "bin.harness.runner.launch_run",
                side_effect=_patched_launch_factory(_populate_solid),
            ):
                PR._execute_one_run(
                    plan_run, harness_run,
                    hooks=PR.PlanRunnerHooks(),
                    artifact_map=artifact_map,
                )
            run_dir = harness_run / "run-00"
            # Both receipts carry the local_artifact entry.
            artifact_used = json.loads(
                (run_dir / "artifact_used.json").read_text(
                    encoding="utf-8")
            )
            self.assertEqual(artifact_used["sha256"], "deadbeef")
            self.assertEqual(artifact_used["filename"], "fake.whl")
            inv = json.loads(
                (run_dir / "invocation.json").read_text(
                    encoding="utf-8")
            )
            self.assertIsNotNone(inv["local_artifact"])
            self.assertEqual(
                inv["local_artifact"]["sha256"], "deadbeef",
            )
            self.assertEqual(
                inv["local_artifact"]["filename"], "fake.whl",
            )


# ---------------------------------------------------------------------------
# Task B — terminal-state handling: ABORTED_PREP + non-COMPLETED → N/A
# ---------------------------------------------------------------------------


class LiveExecuteOneRunAbortedPrepTests(unittest.TestCase):

    def test_clone_failure_yields_aborted_prep_and_NA(self) -> None:
        """``prepare.PrepError`` ⇒ terminal=ABORTED_PREP,
        result=N/A; invocation.json records the prep_error
        reason."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            # Bogus repo URL — clone will fail.
            plan_run = _mk_plan_run(
                repo_url="file:///path/that/does/not/exist",
                expect={"gate_result": "PASS"},
            )
            harness_run = tmp_p / "harness-run"
            harness_run.mkdir()
            with mock.patch(
                "bin.harness.runner.launch_run",
                # Should never be called — prep aborts first.
                side_effect=AssertionError(
                    "launch_run must not run on ABORTED_PREP"
                ),
            ):
                outcome = PR._execute_one_run(
                    plan_run, harness_run,
                    hooks=PR.PlanRunnerHooks(),
                    artifact_map={},
                )
            self.assertEqual(
                outcome.terminal_state,
                S.TerminalState.ABORTED_PREP.value,
            )
            self.assertEqual(outcome.result, "N/A")
            self.assertEqual(outcome.gate_verdict, "N/A")
            run_dir = harness_run / "run-00"
            self.assertTrue(
                (run_dir / "invocation.json").is_file(),
                "invocation.json must land even on ABORTED_PREP",
            )
            inv = json.loads(
                (run_dir / "invocation.json").read_text(
                    encoding="utf-8")
            )
            self.assertEqual(
                inv["terminal_state"],
                S.TerminalState.ABORTED_PREP.value,
            )
            self.assertIn("prep_error", inv)
            # No facts.json / grading.json on prep abort.
            self.assertFalse(
                (run_dir / "facts.json").exists()
            )
            self.assertFalse(
                (run_dir / "grading.json").exists()
            )


class LiveExecuteOneRunNonCompletedTests(unittest.TestCase):

    def test_failed_launch_yields_NA_no_grading(self) -> None:
        """Non-COMPLETED terminal (FAILED) ⇒ result=N/A,
        no grading.json. Invocation receipt still written so the
        operator can debug; transcript still capturable."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            repo_url = _make_local_git_repo(tmp_p)
            plan_run = _mk_plan_run(
                repo_url=repo_url,
                expect={"gate_result": "PASS"},
            )
            harness_run = tmp_p / "harness-run"
            harness_run.mkdir()
            with mock.patch(
                "bin.harness.runner.launch_run",
                side_effect=_patched_launch_factory(
                    _populate_solid,
                    exit_code=1,
                    terminal=S.TerminalState.FAILED,
                ),
            ):
                outcome = PR._execute_one_run(
                    plan_run, harness_run,
                    hooks=PR.PlanRunnerHooks(),
                    artifact_map={},
                )
            self.assertEqual(
                outcome.terminal_state,
                S.TerminalState.FAILED.value,
            )
            self.assertEqual(outcome.result, "N/A")
            self.assertEqual(outcome.gate_verdict, "N/A")
            run_dir = harness_run / "run-00"
            self.assertTrue(
                (run_dir / "invocation.json").is_file()
            )
            self.assertFalse(
                (run_dir / "facts.json").exists(),
                "non-COMPLETED ⇒ no facts.json",
            )
            self.assertFalse(
                (run_dir / "grading.json").exists(),
                "non-COMPLETED ⇒ no grading.json",
            )


# ---------------------------------------------------------------------------
# Task A.5 — fake_run remains an optional fast-path for unit tests
# ---------------------------------------------------------------------------


class FakeRunHookStillWorksTests(unittest.TestCase):

    def test_fake_run_short_circuits_production_path(self) -> None:
        """The 099/100/101 fake_run fast-path is preserved: when
        a hook is supplied, the real composition is NOT invoked
        (no clone, no install, no real launch). Pre-103 tests
        all rely on this — the suite-wide green status confirms
        the short-circuit, but this test pins it explicitly."""
        # If the production path leaked through, prepare's
        # real clone would try to use an invalid repo URL and
        # raise. With the hook in place, neither prepare nor
        # launch is called.
        called: dict[str, bool] = {}

        def _fake_run(plan_run, run_dir):
            called["fake_run"] = True
            return {
                "terminal_state":
                    S.TerminalState.ABORTED_PREP.value,
                "facts": None,
                "transcript": "",
                "axes": S.RunAxes(
                    runner=plan_run.runner,
                    mode=plan_run.mode,
                    install_channel=plan_run.channel,
                    model=plan_run.model,
                ),
            }

        plan_run = _mk_plan_run(
            repo_url="file:///path/does/not/exist",
            expect={"gate_result": "PASS"},
        )
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp)
            with mock.patch(
                "bin.harness.runner.launch_run",
                side_effect=AssertionError(
                    "launch_run must not run when fake_run is set"
                ),
            ):
                outcome = PR._execute_one_run(
                    plan_run, harness_run,
                    hooks=PR.PlanRunnerHooks(fake_run=_fake_run),
                    artifact_map={},
                )
            self.assertTrue(called.get("fake_run"))
            self.assertEqual(
                outcome.terminal_state,
                S.TerminalState.ABORTED_PREP.value,
            )


if __name__ == "__main__":
    unittest.main()
