"""v1.5.7 107 — per-run `workspace_root` for shared/sequential
phase-by-phase runs.

Andrew's use case: 6 runs, ``pools.copilot=1`` (forces
sequential), all sharing one ``workspace_root``; run 1 → phase
1, run 2 → phase 2 (reading run 1's ``quality/`` artifacts), …
run 6 → phase 6. Recreates QPB's recommended clean-context
phase-per-session flow, harness-driven.

Coverage:
  * Task A: ``workspace_root`` parsing (absent / string /
    invalid → PlanError).
  * Task A: ``workspace_root`` absent ⇒ unchanged clone-into-
    ``run-NN/target`` behavior.
  * Task A: ``workspace_root`` present + empty (or absent on
    disk) ⇒ run clones + installs into it (first-run prep).
  * Task A: ``workspace_root`` present + already-prepared
    (skill installed + ``quality/`` artifacts present) ⇒ run
    reuses it; NO re-clone; NO re-install; NO wipe of the
    existing ``quality/`` tree.
  * Task B sequence: run A preps workspace + writes a phase-1
    artifact; run B (same ``workspace_root``, pool-serialized)
    sees run A's artifact intact at launch.
  * Plan.json round-trip preserves ``workspace_root`` when set.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path

from bin.harness import plan_runner as PR
from bin.harness import runner as RUN
from bin.harness import schema as S


def _make_local_git_repo(parent: Path, *,
                          name: str = "fixture-repo") -> str:
    """Create a tiny local git repo (file:// URL)."""
    repo = parent / name
    repo.mkdir()
    for c in (("git", "init", "--initial-branch=main"),
               ("git", "config", "user.email", "t@e.x"),
               ("git", "config", "user.name", "T")):
        subprocess.run(list(c), cwd=str(repo), check=True,
                       capture_output=True)
    (repo / "README.md").write_text("# fix\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"],
                   cwd=str(repo), check=True,
                   capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"],
                   cwd=str(repo), check=True,
                   capture_output=True)
    return f"file://{repo}"


def _install_qpb_into(target: Path) -> None:
    """Real install_skill into ``target`` — same pattern the
    103/106 tests use to set up a prepared workspace."""
    from bin import install_skill
    install_skill.install(
        into=target, ai_tool="claude", no_smoke=True,
    )


def _capture_launch(spec: RUN.LaunchSpec,
                     *, populated: dict | None = None,
                     ) -> RUN.LaunchResult:
    """Generic patched-launch helper used across the
    workspace tests — records what it saw and returns FAILED
    so the run terminates without grading."""
    if populated is not None:
        populated["target_dir"] = str(spec.target_dir)
        populated["quality_dir_present"] = (
            spec.target_dir / "quality"
        ).is_dir()
    spec.run_dir.mkdir(parents=True, exist_ok=True)
    stream = spec.run_dir / "stream.ndjson"
    stream.write_text("{}\n", encoding="utf-8")
    return RUN.LaunchResult(
        pid=0,
        started_at="2026-05-26T00:00:00Z",
        ended_at="2026-05-26T00:00:01Z",
        exit_code=1,
        terminal_state=S.TerminalState.FAILED,
        cli_command="(patched)",
        cwd=str(spec.target_dir),
        env_snapshot={},
        stream_path=stream,
    )


# ---------------------------------------------------------------------------
# Task A — parsing
# ---------------------------------------------------------------------------


class ParseWorkspaceRootTests(unittest.TestCase):

    def _base(self) -> dict:
        return {
            "description": "x", "repo": "y", "ref": "main",
            "runner": "claude", "model": "opus",
            "channel": "clone", "expect": {},
        }

    def test_workspace_root_absent_defaults_none(self) -> None:
        plan = PR.parse_plan(
            {"pools": {}, "runs": [self._base()]})
        self.assertIsNone(plan.runs[0].workspace_root)

    def test_workspace_root_string_parses(self) -> None:
        raw = self._base()
        raw["workspace_root"] = "/tmp/shared-workspace"
        plan = PR.parse_plan({"pools": {}, "runs": [raw]})
        self.assertEqual(plan.runs[0].workspace_root,
                          "/tmp/shared-workspace")

    def test_workspace_root_empty_string_rejected(self) -> None:
        raw = self._base()
        raw["workspace_root"] = "   "
        with self.assertRaises(PR.PlanError) as ctx:
            PR.parse_plan({"pools": {}, "runs": [raw]})
        self.assertIn("workspace_root", str(ctx.exception))
        self.assertIn("empty", str(ctx.exception))

    def test_workspace_root_wrong_type_rejected(self) -> None:
        raw = self._base()
        raw["workspace_root"] = 42
        with self.assertRaises(PR.PlanError) as ctx:
            PR.parse_plan({"pools": {}, "runs": [raw]})
        self.assertIn("workspace_root", str(ctx.exception))
        self.assertIn("path string", str(ctx.exception))


# ---------------------------------------------------------------------------
# Task A — `_is_workspace_prepared` detector
# ---------------------------------------------------------------------------


class IsWorkspacePreparedTests(unittest.TestCase):

    def test_nonexistent_dir_returns_false(self) -> None:
        self.assertFalse(
            PR._is_workspace_prepared(Path("/nonexistent/x"))
        )

    def test_empty_dir_returns_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(
                PR._is_workspace_prepared(Path(tmp))
            )

    def test_dir_with_installed_skill_returns_true(self) -> None:
        """A real install_skill into a temp dir ⇒ the detector
        sees the skill at one of the 10 canonical layouts."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            _install_qpb_into(target)
            self.assertTrue(
                PR._is_workspace_prepared(target),
                "an install_skill'd target must be detected "
                "as a prepared workspace",
            )

    def test_dir_with_arbitrary_skill_md_not_qpb_returns_false(
            self) -> None:
        """A non-QPB SKILL.md at the root must not be mistaken
        for a prepared workspace."""
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / "SKILL.md").write_text(
                "name: some-other-skill\n", encoding="utf-8",
            )
            self.assertFalse(
                PR._is_workspace_prepared(target),
                "a non-QPB SKILL.md must not be mistaken for "
                "a prepared workspace",
            )


# ---------------------------------------------------------------------------
# Task A — production path: workspace_root absent (unchanged)
# ---------------------------------------------------------------------------


class WorkspaceRootAbsentUnchangedBehaviorTests(unittest.TestCase):

    def test_default_path_clones_into_run_NN_target(
            self) -> None:
        """No workspace_root ⇒ standard clone-into-run-NN/target
        behavior (the 103/105/106 contract preserved)."""
        captured: dict = {}

        def _fake(spec):
            return _capture_launch(spec, populated=captured)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            repo_url = _make_local_git_repo(tmp_p)
            plan_run = PR.PlanRun(
                index=0, description="x",
                repo=repo_url, ref="main",
                runner=S.Runner.CLAUDE, model="opus",
                channel=S.InstallChannel.CLONE,
                expect={},
            )
            harness_run = tmp_p / "harness-run"
            harness_run.mkdir()
            with mock.patch(
                "bin.harness.runner.launch_run",
                side_effect=_fake,
            ):
                PR._execute_one_run(
                    plan_run, harness_run,
                    hooks=PR.PlanRunnerHooks(),
                    artifact_map={},
                )
            # Target is the standard run-NN/target path.
            self.assertEqual(
                Path(captured["target_dir"]).parent.name,
                "run-00",
            )
            self.assertEqual(
                Path(captured["target_dir"]).name, "target",
            )


# ---------------------------------------------------------------------------
# Task A — workspace_root present + empty: first-run preps it
# ---------------------------------------------------------------------------


class WorkspaceRootFirstRunPrepsTests(unittest.TestCase):

    def test_workspace_root_absent_on_disk_clones_into_it(
            self) -> None:
        """workspace_root path doesn't yet exist ⇒ the run
        clones+installs into it. Target dir is the
        workspace_root, NOT run-NN/target."""
        captured: dict = {}

        def _fake(spec):
            return _capture_launch(spec, populated=captured)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            repo_url = _make_local_git_repo(tmp_p)
            # workspace_root doesn't exist yet — prepare must
            # clone into it.
            workspace = tmp_p / "shared"
            plan_run = PR.PlanRun(
                index=0, description="first-prep",
                repo=repo_url, ref="main",
                runner=S.Runner.CLAUDE, model="opus",
                channel=S.InstallChannel.CLONE,
                workspace_root=str(workspace),
                expect={},
            )
            harness_run = tmp_p / "harness-run"
            harness_run.mkdir()
            with mock.patch(
                "bin.harness.runner.launch_run",
                side_effect=_fake,
            ):
                PR._execute_one_run(
                    plan_run, harness_run,
                    hooks=PR.PlanRunnerHooks(),
                    artifact_map={},
                )
            # The launch saw the workspace_root as its target
            # (NOT run-NN/target).
            self.assertEqual(
                Path(captured["target_dir"]).resolve(),
                workspace.resolve(),
            )
            # Workspace got the clone (README from the fixture).
            self.assertTrue(
                (workspace / "README.md").is_file()
            )
            # Workspace got the install (skill present at one
            # of the 10 layouts).
            self.assertTrue(
                PR._is_workspace_prepared(workspace),
                "first-prep run must leave the workspace in a "
                "prepared state for subsequent runs",
            )

    def test_workspace_root_empty_dir_clones_into_it(
            self) -> None:
        """workspace_root exists but is an empty dir ⇒ run
        treats it as 'not yet prepared' and proceeds to
        clone+install. The 105-hardened clone_worktree would
        normally raise on existing dest; 107 handles the
        empty-dir case by rmdir-then-clone."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            repo_url = _make_local_git_repo(tmp_p)
            workspace = tmp_p / "shared-empty"
            workspace.mkdir()  # exists but empty
            plan_run = PR.PlanRun(
                index=0, description="empty-dir-prep",
                repo=repo_url, ref="main",
                runner=S.Runner.CLAUDE, model="opus",
                channel=S.InstallChannel.CLONE,
                workspace_root=str(workspace),
                expect={},
            )
            harness_run = tmp_p / "harness-run"
            harness_run.mkdir()
            with mock.patch(
                "bin.harness.runner.launch_run",
                side_effect=_capture_launch,
            ):
                PR._execute_one_run(
                    plan_run, harness_run,
                    hooks=PR.PlanRunnerHooks(),
                    artifact_map={},
                )
            # Workspace ends up prepared (clone + install).
            self.assertTrue(
                (workspace / "README.md").is_file()
            )
            self.assertTrue(PR._is_workspace_prepared(workspace))


# ---------------------------------------------------------------------------
# Task A — workspace_root already prepared: reuse, don't clobber
# ---------------------------------------------------------------------------


class WorkspaceRootReuseTests(unittest.TestCase):

    def test_already_prepared_workspace_reused_no_clobber(
            self) -> None:
        """The KEY 107 invariant: when workspace_root is a
        prepared workspace AND has a quality/ tree, the run
        reuses it AS-IS — no clone, no install, no wipe of
        quality/ (phase N reads phase N-1's artifacts)."""
        # Spies count prepare.* invocations.
        prep_spy = {"clone_worktree": 0,
                    "_run_install_for_axes": 0}

        from bin.harness import prepare as _prepare_mod
        real_clone = _prepare_mod.clone_worktree
        real_install = _prepare_mod._run_install_for_axes

        def _spy_clone(*a, **kw):
            prep_spy["clone_worktree"] += 1
            return real_clone(*a, **kw)

        def _spy_install(*a, **kw):
            prep_spy["_run_install_for_axes"] += 1
            return real_install(*a, **kw)

        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            repo_url = _make_local_git_repo(tmp_p)
            workspace = tmp_p / "shared-prepared"
            workspace.mkdir()
            # Make it look like a prepared QPB workspace.
            _install_qpb_into(workspace)
            # Write a "phase 1" artifact into quality/.
            quality = workspace / "quality"
            quality.mkdir(exist_ok=True)
            (quality / "EXPLORATION.md").write_text(
                "# Exploration (Phase 1 output)\n",
                encoding="utf-8",
            )
            (quality / "BUGS.md").write_text(
                "# Bugs\n\nBUG-001: example\n",
                encoding="utf-8",
            )
            plan_run = PR.PlanRun(
                index=0, description="reuse-prepared",
                repo=repo_url, ref="main",
                runner=S.Runner.CLAUDE, model="opus",
                channel=S.InstallChannel.CLONE,
                workspace_root=str(workspace),
                expect={},
            )
            harness_run = tmp_p / "harness-run"
            harness_run.mkdir()
            with mock.patch(
                "bin.harness.prepare.clone_worktree",
                side_effect=_spy_clone,
            ), mock.patch(
                "bin.harness.prepare._run_install_for_axes",
                side_effect=_spy_install,
            ), mock.patch(
                "bin.harness.runner.launch_run",
                side_effect=_capture_launch,
            ):
                PR._execute_one_run(
                    plan_run, harness_run,
                    hooks=PR.PlanRunnerHooks(),
                    artifact_map={},
                )
            # Neither clone nor install ran.
            self.assertEqual(
                prep_spy["clone_worktree"], 0,
                "reuse-prepared workspace must NOT re-clone",
            )
            self.assertEqual(
                prep_spy["_run_install_for_axes"], 0,
                "reuse-prepared workspace must NOT re-install",
            )
            # The prior phase 1 artifacts are intact.
            self.assertTrue(
                (workspace / "quality" /
                  "EXPLORATION.md").is_file(),
                "phase N must read phase N-1's quality/ "
                "artifacts — the 107 NO-CLOBBER invariant",
            )
            self.assertIn(
                "Phase 1 output",
                (workspace / "quality" /
                  "EXPLORATION.md").read_text(
                    encoding="utf-8"),
            )


# ---------------------------------------------------------------------------
# Task B — sequence test: run A preps; run B reuses (2 runs)
# ---------------------------------------------------------------------------


class SharedWorkspaceSequenceTests(unittest.TestCase):

    def test_two_runs_shared_workspace_preserves_artifacts(
            self) -> None:
        """Run A preps the shared workspace + writes a phase-1
        artifact via the patched-launch hook. Run B (same
        workspace_root, pool-serialized) sees run A's artifact
        intact when its own launch fires."""
        run_a_artifact_path = None

        def _fake_run_a_writes_phase1(spec):
            """Run A's launch: write a phase-1-style artifact
            into the shared workspace's quality/."""
            spec.run_dir.mkdir(parents=True, exist_ok=True)
            quality = spec.target_dir / "quality"
            quality.mkdir(exist_ok=True)
            (quality / "EXPLORATION.md").write_text(
                "# Phase 1 output (from run A)\n",
                encoding="utf-8",
            )
            stream = spec.run_dir / "stream.ndjson"
            stream.write_text("{}\n", encoding="utf-8")
            return RUN.LaunchResult(
                pid=0, started_at="2026-05-26T00:00:00Z",
                ended_at="2026-05-26T00:00:01Z",
                exit_code=1,
                terminal_state=S.TerminalState.FAILED,
                cli_command="(patched-A)",
                cwd=str(spec.target_dir),
                env_snapshot={}, stream_path=stream,
            )

        run_b_saw: dict = {}

        def _fake_run_b_observes(spec):
            """Run B's launch: assert the phase-1 artifact run A
            wrote is present in the SHARED workspace's quality/.
            Then write a phase-2 artifact (just to demonstrate
            the pattern)."""
            run_b_saw["target_dir"] = str(spec.target_dir)
            run_b_saw["exploration_present"] = (
                spec.target_dir / "quality" / "EXPLORATION.md"
            ).is_file()
            if run_b_saw["exploration_present"]:
                run_b_saw["exploration_content"] = (
                    spec.target_dir / "quality" /
                    "EXPLORATION.md"
                ).read_text(encoding="utf-8")
            spec.run_dir.mkdir(parents=True, exist_ok=True)
            stream = spec.run_dir / "stream.ndjson"
            stream.write_text("{}\n", encoding="utf-8")
            return RUN.LaunchResult(
                pid=0, started_at="2026-05-26T00:00:02Z",
                ended_at="2026-05-26T00:00:03Z",
                exit_code=1,
                terminal_state=S.TerminalState.FAILED,
                cli_command="(patched-B)",
                cwd=str(spec.target_dir),
                env_snapshot={}, stream_path=stream,
            )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            repo_url = _make_local_git_repo(tmp_p)
            workspace = tmp_p / "shared"
            # Don't pre-create — run A will prep.
            harness_run = tmp_p / "harness-run"
            harness_run.mkdir()

            # Run A: workspace doesn't exist yet ⇒ first-prep
            # path (clone + install + write phase-1 artifact).
            run_a = PR.PlanRun(
                index=0, description="run A: phase 1",
                repo=repo_url, ref="main",
                runner=S.Runner.CLAUDE, model="opus",
                channel=S.InstallChannel.CLONE,
                workspace_root=str(workspace),
                expect={},
            )
            with mock.patch(
                "bin.harness.runner.launch_run",
                side_effect=_fake_run_a_writes_phase1,
            ):
                PR._execute_one_run(
                    run_a, harness_run,
                    hooks=PR.PlanRunnerHooks(),
                    artifact_map={},
                )

            # Confirm run A left the workspace prepared + the
            # phase-1 artifact present.
            self.assertTrue(PR._is_workspace_prepared(workspace))
            self.assertTrue(
                (workspace / "quality" /
                  "EXPLORATION.md").is_file()
            )

            # Run B: same workspace_root, different index. The
            # 107 reuse path must NOT clobber run A's artifact.
            run_b = PR.PlanRun(
                index=1, description="run B: phase 2",
                repo=repo_url, ref="main",
                runner=S.Runner.CLAUDE, model="opus",
                channel=S.InstallChannel.CLONE,
                workspace_root=str(workspace),
                expect={},
            )
            with mock.patch(
                "bin.harness.runner.launch_run",
                side_effect=_fake_run_b_observes,
            ):
                PR._execute_one_run(
                    run_b, harness_run,
                    hooks=PR.PlanRunnerHooks(),
                    artifact_map={},
                )

            # Run B targets the shared workspace.
            self.assertEqual(
                Path(run_b_saw["target_dir"]).resolve(),
                workspace.resolve(),
            )
            # Run B sees run A's phase-1 artifact intact.
            self.assertTrue(
                run_b_saw["exploration_present"],
                "107 NO-CLOBBER: run B must see run A's phase-1 "
                "artifact present when its launch fires",
            )
            self.assertIn(
                "from run A",
                run_b_saw["exploration_content"],
                "107 NO-CLOBBER: the artifact CONTENT must be "
                "byte-identical to what run A wrote (no wipe-"
                "and-recreate)",
            )


# ---------------------------------------------------------------------------
# Task A — non-empty workspace with NO installed skill is operator error
# ---------------------------------------------------------------------------


class WorkspaceRootNonEmptyNoSkillErrorsTests(unittest.TestCase):

    def test_non_empty_dir_without_skill_raises_prep_error(
            self) -> None:
        """Edge: workspace_root exists, is non-empty, but has
        NO installed skill ⇒ that's an operator pointing at the
        wrong dir. The 105-hardened ``clone_worktree`` raises;
        the run gets ABORTED_PREP rather than silently clobbering
        the operator's data."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            repo_url = _make_local_git_repo(tmp_p)
            workspace = tmp_p / "stray-data"
            workspace.mkdir()
            # Drop a sentinel file so the dir is non-empty
            # but NOT a prepared workspace.
            (workspace / "operators-other-stuff.txt").write_text(
                "operator data — don't clobber me",
                encoding="utf-8",
            )
            plan_run = PR.PlanRun(
                index=0, description="stray-workspace",
                repo=repo_url, ref="main",
                runner=S.Runner.CLAUDE, model="opus",
                channel=S.InstallChannel.CLONE,
                workspace_root=str(workspace),
                expect={},
            )
            harness_run = tmp_p / "harness-run"
            harness_run.mkdir()
            outcome = PR._execute_one_run(
                plan_run, harness_run,
                hooks=PR.PlanRunnerHooks(),
                artifact_map={},
            )
            # ABORTED_PREP — clone refused.
            self.assertEqual(
                outcome.terminal_state,
                S.TerminalState.ABORTED_PREP.value,
            )
            self.assertEqual(outcome.result, "N/A")
            # Operator's data is intact.
            self.assertTrue(
                (workspace /
                  "operators-other-stuff.txt").is_file(),
                "107 must NOT clobber existing operator data — "
                "clone refuses, run aborts, the data stays",
            )


# ---------------------------------------------------------------------------
# Plan round-trip: workspace_root preserved when set
# ---------------------------------------------------------------------------


class PlanRoundtripPreservesWorkspaceRootTests(unittest.TestCase):

    def test_run_plan_writes_workspace_root_when_set(self) -> None:
        run_with_ws = {
            "description": "shared", "repo": "x", "ref": "main",
            "runner": "claude", "model": "opus",
            "channel": "clone",
            "workspace_root": "/some/shared/path",
            "expect": {},
        }
        run_defaults = {
            "description": "defaults", "repo": "y", "ref": "main",
            "runner": "claude", "model": "opus",
            "channel": "clone", "expect": {},
        }
        plan = PR.parse_plan({
            "pools": {"claude": 1},
            "runs": [run_defaults, run_with_ws],
        })

        def _fake(pr, run_dir):
            return {
                "terminal_state":
                    S.TerminalState.ABORTED_PREP.value,
                "facts": None, "transcript": "",
                "axes": S.RunAxes(
                    runner=pr.runner, mode=pr.mode,
                    install_channel=pr.channel, model=pr.model,
                ),
            }

        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            PR.run_plan(
                plan, runs_root,
                hooks=PR.PlanRunnerHooks(fake_run=_fake),
            )
            harness_run = next(
                d for d in runs_root.iterdir() if d.is_dir()
            )
            written = json.loads(
                (harness_run / "plan.json").read_text(
                    encoding="utf-8")
            )
            # Defaults: workspace_root key absent ⇒ pre-107
            # plans round-trip byte-stable.
            self.assertNotIn(
                "workspace_root", written["runs"][0]
            )
            # Override: present + correct.
            self.assertEqual(
                written["runs"][1]["workspace_root"],
                "/some/shared/path",
            )


if __name__ == "__main__":
    unittest.main()
