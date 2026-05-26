"""v1.5.7 106 — Mode A full-pipeline prompt + per-run Mode B with
run_playbook phase options + configurable max-duration.

Three blockers found triaging the first live 4-repo acceptance
run:

  (Task A) ROOT CAUSE of 0/4 MET: the pre-106 launch prompt was
  bare (``"Run the Quality Playbook on this project."``). That
  doesn't hit SKILL.md:413's "run all phases" trigger, so the
  agent did the DEFAULT single-phase-at-a-time behavior — gson
  stopped after Phase 1; keto stopped after Phase 2. 106 sends
  a prompt that EXPLICITLY requests phases 1-6 in one session
  + the gate, unattended, no iteration strategies.

  (Task B) The harness had no way to launch a Mode B run from
  a plan. 106 adds a per-run ``mode`` field ("A"/"B"), forwards
  the run's ``parameters`` to ``run_playbook`` argv in Mode B
  (so plans can select phases — e.g. ``--phase 3``), and verifies
  Mode B drives the CHANNEL-INSTALLED skill in the target.

  (Task C) 1800s was too short for a full pipeline (express
  timed out on Phase 1+2 alone). 106 raises the default to
  7200s (120 min) and makes it per-run-overridable.

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


# ---------------------------------------------------------------------------
# Task A — the Mode A full-pipeline prompt constant
# ---------------------------------------------------------------------------


class ModeAFullPipelinePromptTests(unittest.TestCase):
    """Pre-106, the harness sent the bare ``"Run the Quality
    Playbook on this project."`` — produced 0/4 MET on the first
    live run because agents stopped after Phase 1. 106 makes the
    prompt hit SKILL.md:413's all-phases trigger AND excludes
    SKILL.md:141's iteration strategies."""

    def test_prompt_constant_requests_all_phases(self) -> None:
        """The prompt must explicitly request phases 1 through 6
        (or 1-6) in one session."""
        prompt = PR._MODE_A_FULL_RUN_PROMPT
        self.assertIn("all phases", prompt.lower())
        # Match either "1 through 6" or "1-6" / similar
        # construction.
        self.assertTrue(
            "1 through 6" in prompt
            or "1-6" in prompt
            or "phases 1" in prompt,
            f"prompt must enumerate phases 1-6 explicitly; "
            f"got: {prompt!r}",
        )

    def test_prompt_constant_excludes_iteration_strategies(
            self) -> None:
        """SKILL.md:141 chains the 4 iteration strategies
        (gap/unfiltered/parity/adversarial) onto a bare full
        run. The acceptance harness wants phases 1-6 + gate
        ONLY — the prompt must explicitly opt out."""
        prompt = PR._MODE_A_FULL_RUN_PROMPT.lower()
        self.assertIn("iteration strategies", prompt)
        for strategy in ("gap", "unfiltered", "parity",
                          "adversarial"):
            self.assertIn(
                strategy, prompt,
                f"prompt must name the {strategy!r} iteration "
                f"strategy in its exclusion list so the agent "
                f"unambiguously knows what NOT to run",
            )

    def test_prompt_constant_unattended(self) -> None:
        """The agent must not pause between phases or wait for
        confirmation — unattended."""
        prompt = PR._MODE_A_FULL_RUN_PROMPT.lower()
        self.assertTrue(
            "unattended" in prompt
            or "do not stop" in prompt,
            f"prompt must declare the run unattended (no pauses "
            f"between phases); got: {prompt!r}",
        )

    def test_prompt_constant_runs_gate(self) -> None:
        """The prompt must end with running the quality gate
        (SKILL.md's Phase 6 is the gate)."""
        prompt = PR._MODE_A_FULL_RUN_PROMPT.lower()
        self.assertIn("gate", prompt)

    def test_production_path_uses_prompt_constant(self) -> None:
        """**Mutation-bite for Task A.** The production launch
        path MUST use the constant — reverting to the bare pre-
        106 prompt ⇒ this test fails. Patches launch_run to
        capture the LaunchSpec.prompt, then runs a Mode A plan."""
        captured: dict = {}

        def _fake_launch(spec):
            captured["prompt"] = spec.prompt
            captured["mode"] = spec.axes.mode
            captured["max_duration_s"] = spec.max_duration_s
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

        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            # Tiny local git fixture so prepare's clone works.
            fixture = tmp_p / "fixture-repo"
            fixture.mkdir()
            for c in (("git", "init", "--initial-branch=main"),
                       ("git", "config", "user.email", "t@e.x"),
                       ("git", "config", "user.name", "T")):
                subprocess.run(list(c), cwd=str(fixture),
                               check=True, capture_output=True)
            (fixture / "README.md").write_text("# fix\n")
            subprocess.run(["git", "add", "README.md"],
                           cwd=str(fixture), check=True,
                           capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"],
                           cwd=str(fixture), check=True,
                           capture_output=True)
            plan_run = PR.PlanRun(
                index=0, description="x",
                repo=f"file://{fixture}", ref="main",
                runner=S.Runner.CLAUDE, model="opus",
                channel=S.InstallChannel.CLONE,
                expect={"gate_result": "PASS"},
            )
            harness_run = tmp_p / "harness-run"
            harness_run.mkdir()
            with mock.patch(
                "bin.harness.runner.launch_run",
                side_effect=_fake_launch,
            ):
                PR._execute_one_run(
                    plan_run, harness_run,
                    hooks=PR.PlanRunnerHooks(),
                    artifact_map={},
                )
            self.assertEqual(
                captured["prompt"], PR._MODE_A_FULL_RUN_PROMPT,
                "production launch path must use "
                "_MODE_A_FULL_RUN_PROMPT (mutation-bite: "
                "revert to the bare pre-106 prompt and this "
                "assertion fails)",
            )


# ---------------------------------------------------------------------------
# Task B — per-run mode field + Mode B parameters forwarding
# ---------------------------------------------------------------------------


class ParseModeFieldTests(unittest.TestCase):

    def _base_run(self) -> dict:
        return {
            "description": "x", "repo": "y", "ref": "main",
            "runner": "claude", "model": "opus",
            "channel": "clone", "expect": {},
        }

    def test_mode_absent_defaults_to_A(self) -> None:
        plan = PR.parse_plan(
            {"pools": {}, "runs": [self._base_run()]})
        self.assertEqual(plan.runs[0].mode, S.Mode.A)

    def test_mode_A_explicit(self) -> None:
        raw = self._base_run()
        raw["mode"] = "A"
        plan = PR.parse_plan({"pools": {}, "runs": [raw]})
        self.assertEqual(plan.runs[0].mode, S.Mode.A)

    def test_mode_B_parses(self) -> None:
        raw = self._base_run()
        raw["mode"] = "B"
        plan = PR.parse_plan({"pools": {}, "runs": [raw]})
        self.assertEqual(plan.runs[0].mode, S.Mode.B)

    def test_mode_invalid_raises_plan_error(self) -> None:
        raw = self._base_run()
        raw["mode"] = "C"
        with self.assertRaises(PR.PlanError) as ctx:
            PR.parse_plan({"pools": {}, "runs": [raw]})
        self.assertIn("runs[0].mode", str(ctx.exception))
        self.assertIn("'A' or 'B'", str(ctx.exception))


class ModeBParametersForwardingTests(unittest.TestCase):
    """In Mode B, the run's ``parameters`` route to
    ``run_playbook`` argv (not the runner CLI). A plan can
    select phases — e.g. ``parameters=["--phase", "3"]``."""

    def test_mode_b_parameters_spliced_before_target_dir(
            self) -> None:
        axes = S.RunAxes(
            runner=S.Runner.COPILOT, mode=S.Mode.B,
            install_channel=S.InstallChannel.CLONE,
            model="gpt-5.4",
        )
        target = Path("/tmp/synthetic-target")
        cmd = RUN._command_for_axes(
            axes, "(unused-in-mode-b)", target_dir=target,
            parameters=["--phase", "3"],
        )
        # Shape: python -m bin.run_playbook --copilot --model X
        # [...parameters...] <target>
        self.assertEqual(cmd[0], sys.executable)
        self.assertEqual(cmd[1:3], ["-m", "bin.run_playbook"])
        self.assertIn("--copilot", cmd)
        self.assertEqual(
            cmd[cmd.index("--model") + 1], "gpt-5.4",
        )
        self.assertIn("--phase", cmd)
        self.assertEqual(
            cmd[cmd.index("--phase") + 1], "3",
        )
        # Target dir trails.
        self.assertEqual(cmd[-1], str(target))
        # And `--phase` lands BEFORE the target positional, not
        # after.
        self.assertLess(cmd.index("--phase"),
                         cmd.index(str(target)))

    def test_mode_b_no_parameters_unchanged_baseline(self) -> None:
        """No parameters ⇒ command identical to the 095
        baseline."""
        axes = S.RunAxes(
            runner=S.Runner.COPILOT, mode=S.Mode.B,
            install_channel=S.InstallChannel.CLONE,
            model="gpt-5.4",
        )
        target = Path("/tmp/synthetic-target")
        cmd = RUN._command_for_axes(
            axes, "(unused)", target_dir=target,
        )
        self.assertEqual(cmd, [
            sys.executable, "-m", "bin.run_playbook",
            "--copilot", "--model", "gpt-5.4", str(target),
        ])

    def test_mode_a_parameters_still_go_to_runner_cli(
            self) -> None:
        """Mode A keeps the 100 contract: ``parameters`` routes
        to the runner CLI (not run_playbook)."""
        axes = S.RunAxes(
            runner=S.Runner.CODEX, mode=S.Mode.A,
            install_channel=S.InstallChannel.CLONE,
            model="gpt-5.2",
        )
        cmd = RUN._command_for_axes(
            axes, "prompt", parameters=["-c", "k=v"],
        )
        # codex spec: codex -c k=v exec --full-auto -m model -
        self.assertEqual(cmd[:1], ["codex"])
        self.assertEqual(cmd[1:3], ["-c", "k=v"])
        self.assertEqual(cmd[3], "exec")


class ModeBChannelInstalledTargetVerificationTests(
        unittest.TestCase):
    """Task B halt-condition check: Mode B's ``run_playbook``
    invocation MUST drive the run's channel-installed target
    (the skill IN ``run-NN/target/.claude/skills/...``), not the
    QPB clone. The audit:

      * ``run_playbook.resolve_target_dirs(<target>)`` calls
        ``lib.find_installed_skill(<target>)`` — which searches
        the 10 canonical install layouts inside the target.
      * ``SKILL_FALLBACK_GUIDE`` (run_playbook.py:1083) directs
        the agent to read SKILL.md from the same 10 layouts
        inside the target.

    Both are observable invariants we can pin so a future
    refactor doesn't silently break the Mode-B-on-channel-
    installed-target contract.
    """

    def test_run_playbook_consults_target_installed_skill(
            self) -> None:
        """The run_playbook entry uses
        ``lib.find_installed_skill`` to validate the target —
        which is the API that searches for an installed skill
        inside the target's canonical layouts. Source-level
        pin: the call must be present."""
        rp_src = (Path(__file__).resolve().parents[3]
                  / "bin" / "run_playbook.py").read_text(
                      encoding="utf-8")
        self.assertIn(
            "lib.find_installed_skill(candidate)", rp_src,
            "Mode B / run_playbook must verify the channel-"
            "installed skill in the target — the source-level "
            "pin caught the call in resolve_target_dirs.",
        )

    def test_skill_fallback_guide_lists_install_layouts(
            self) -> None:
        """run_playbook's SKILL_FALLBACK_GUIDE directs the
        agent at the target's installed skill paths
        (.claude/skills/quality-playbook/SKILL.md and the 9
        sibling layouts)."""
        # Import the module to get the constant.
        import bin.run_playbook as RP
        guide = RP.SKILL_FALLBACK_GUIDE
        self.assertIn(
            ".claude/skills/quality-playbook/SKILL.md", guide,
        )
        self.assertIn(
            ".github/skills/quality-playbook/SKILL.md", guide,
        )


# ---------------------------------------------------------------------------
# Task C — configurable max_duration_s with larger default
# ---------------------------------------------------------------------------


class MaxDurationTests(unittest.TestCase):

    def _base_run(self) -> dict:
        return {
            "description": "x", "repo": "y", "ref": "main",
            "runner": "claude", "model": "opus",
            "channel": "clone", "expect": {},
        }

    def test_default_max_duration_is_large(self) -> None:
        """The default must be substantially larger than the
        pre-106 1800s value (a full Mode A pipeline can run
        well past 30 min). 106 sets it to 7200s (120 min)."""
        self.assertGreaterEqual(
            PR._DEFAULT_MAX_DURATION_S, 5400.0,
            "default max_duration_s must be ≥ 5400s (90 min) "
            "per instruction guidance; pre-106 1800s was too "
            "short for a full pipeline",
        )
        # Sanity upper bound — not pinning the exact value, just
        # catching an accidental 1000× off-by-magnitude.
        self.assertLessEqual(
            PR._DEFAULT_MAX_DURATION_S, 86400.0,
            "default max_duration_s should be < 1 day; the "
            "instruction suggested 5400-7200s",
        )

    def test_default_max_duration_not_pre_106_value(self) -> None:
        """Mutation-bite: revert to the pre-106 1800s default ⇒
        this assertion fails."""
        self.assertNotEqual(
            PR._DEFAULT_MAX_DURATION_S, 1800.0,
            "1800s was the pre-106 default that timed out "
            "express on phase 1+2; 106 raised it",
        )

    def test_per_run_max_duration_parses(self) -> None:
        raw = self._base_run()
        raw["max_duration_s"] = 3000
        plan = PR.parse_plan({"pools": {}, "runs": [raw]})
        self.assertEqual(plan.runs[0].max_duration_s, 3000.0)

    def test_per_run_max_duration_absent_is_none(self) -> None:
        plan = PR.parse_plan(
            {"pools": {}, "runs": [self._base_run()]})
        self.assertIsNone(plan.runs[0].max_duration_s)

    def test_per_run_max_duration_negative_rejected(self) -> None:
        raw = self._base_run()
        raw["max_duration_s"] = -5
        with self.assertRaises(PR.PlanError) as ctx:
            PR.parse_plan({"pools": {}, "runs": [raw]})
        self.assertIn("must be > 0", str(ctx.exception))

    def test_per_run_max_duration_zero_rejected(self) -> None:
        raw = self._base_run()
        raw["max_duration_s"] = 0
        with self.assertRaises(PR.PlanError):
            PR.parse_plan({"pools": {}, "runs": [raw]})

    def test_per_run_max_duration_wrong_type_rejected(
            self) -> None:
        raw = self._base_run()
        raw["max_duration_s"] = "huge"
        with self.assertRaises(PR.PlanError) as ctx:
            PR.parse_plan({"pools": {}, "runs": [raw]})
        self.assertIn("must be a positive number",
                        str(ctx.exception))

    def test_production_path_honors_per_run_max_duration(
            self) -> None:
        """End-to-end: a PlanRun with explicit max_duration_s
        threads through to LaunchSpec.max_duration_s. Capture
        via a patched launch_run; mutation-bite for the wiring."""
        captured: dict = {}

        def _fake_launch(spec):
            captured["max_duration_s"] = spec.max_duration_s
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

        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            fixture = tmp_p / "fixture-repo"
            fixture.mkdir()
            for c in (("git", "init", "--initial-branch=main"),
                       ("git", "config", "user.email", "t@e.x"),
                       ("git", "config", "user.name", "T")):
                subprocess.run(list(c), cwd=str(fixture),
                               check=True, capture_output=True)
            (fixture / "README.md").write_text("# fix\n")
            subprocess.run(["git", "add", "README.md"],
                           cwd=str(fixture), check=True,
                           capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"],
                           cwd=str(fixture), check=True,
                           capture_output=True)
            plan_run = PR.PlanRun(
                index=0, description="x",
                repo=f"file://{fixture}", ref="main",
                runner=S.Runner.CLAUDE, model="opus",
                channel=S.InstallChannel.CLONE,
                expect={"gate_result": "PASS"},
                max_duration_s=4242.0,
            )
            harness_run = tmp_p / "harness-run"
            harness_run.mkdir()
            with mock.patch(
                "bin.harness.runner.launch_run",
                side_effect=_fake_launch,
            ):
                PR._execute_one_run(
                    plan_run, harness_run,
                    hooks=PR.PlanRunnerHooks(),
                    artifact_map={},
                )
            self.assertEqual(
                captured["max_duration_s"], 4242.0,
                "production path must honor PlanRun."
                "max_duration_s; pre-106 it was hardcoded to "
                "1800.0",
            )

    def test_production_path_uses_default_when_absent(
            self) -> None:
        """No per-run override ⇒ falls back to
        _DEFAULT_MAX_DURATION_S."""
        captured: dict = {}

        def _fake_launch(spec):
            captured["max_duration_s"] = spec.max_duration_s
            spec.run_dir.mkdir(parents=True, exist_ok=True)
            stream = spec.run_dir / "stream.ndjson"
            stream.write_text("{}\n", encoding="utf-8")
            return RUN.LaunchResult(
                pid=0, started_at="2026-05-26T00:00:00Z",
                ended_at="2026-05-26T00:00:01Z",
                exit_code=1,
                terminal_state=S.TerminalState.FAILED,
                cli_command="(patched)",
                cwd=str(spec.target_dir),
                env_snapshot={}, stream_path=stream,
            )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            fixture = tmp_p / "fixture-repo"
            fixture.mkdir()
            for c in (("git", "init", "--initial-branch=main"),
                       ("git", "config", "user.email", "t@e.x"),
                       ("git", "config", "user.name", "T")):
                subprocess.run(list(c), cwd=str(fixture),
                               check=True, capture_output=True)
            (fixture / "README.md").write_text("# fix\n")
            subprocess.run(["git", "add", "README.md"],
                           cwd=str(fixture), check=True,
                           capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"],
                           cwd=str(fixture), check=True,
                           capture_output=True)
            plan_run = PR.PlanRun(
                index=0, description="x",
                repo=f"file://{fixture}", ref="main",
                runner=S.Runner.CLAUDE, model="opus",
                channel=S.InstallChannel.CLONE,
                expect={"gate_result": "PASS"},
                # NO max_duration_s override.
            )
            harness_run = tmp_p / "harness-run"
            harness_run.mkdir()
            with mock.patch(
                "bin.harness.runner.launch_run",
                side_effect=_fake_launch,
            ):
                PR._execute_one_run(
                    plan_run, harness_run,
                    hooks=PR.PlanRunnerHooks(),
                    artifact_map={},
                )
            self.assertEqual(
                captured["max_duration_s"],
                PR._DEFAULT_MAX_DURATION_S,
            )


# ---------------------------------------------------------------------------
# Mode B composition (Task B end-to-end via patched launch)
# ---------------------------------------------------------------------------


class ModeBProductionCompositionTests(unittest.TestCase):
    """A composition-level test (à la 103, only the subprocess
    patched) proving Mode B launches ``run_playbook`` with the
    target dir."""

    def test_mode_b_production_launches_run_playbook_with_target(
            self) -> None:
        captured: dict = {}

        def _fake_launch(spec):
            captured["cli_argv"] = (
                spec.axes,  # mode is on axes
            )
            captured["target_dir"] = str(spec.target_dir)
            captured["mode"] = spec.axes.mode
            spec.run_dir.mkdir(parents=True, exist_ok=True)
            stream = spec.run_dir / "stream.ndjson"
            stream.write_text("{}\n", encoding="utf-8")
            return RUN.LaunchResult(
                pid=0, started_at="2026-05-26T00:00:00Z",
                ended_at="2026-05-26T00:00:01Z",
                exit_code=1,
                terminal_state=S.TerminalState.FAILED,
                cli_command="(patched)",
                cwd=str(spec.target_dir),
                env_snapshot={}, stream_path=stream,
            )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            fixture = tmp_p / "fixture-repo"
            fixture.mkdir()
            for c in (("git", "init", "--initial-branch=main"),
                       ("git", "config", "user.email", "t@e.x"),
                       ("git", "config", "user.name", "T")):
                subprocess.run(list(c), cwd=str(fixture),
                               check=True, capture_output=True)
            (fixture / "README.md").write_text("# fix\n")
            subprocess.run(["git", "add", "README.md"],
                           cwd=str(fixture), check=True,
                           capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"],
                           cwd=str(fixture), check=True,
                           capture_output=True)
            plan_run = PR.PlanRun(
                index=0, description="x",
                repo=f"file://{fixture}", ref="main",
                runner=S.Runner.COPILOT, model="gpt-5.4",
                channel=S.InstallChannel.CLONE,
                mode=S.Mode.B,
                parameters=["--phase", "3"],
                expect={"gate_result": "PASS"},
            )
            harness_run = tmp_p / "harness-run"
            harness_run.mkdir()
            with mock.patch(
                "bin.harness.runner.launch_run",
                side_effect=_fake_launch,
            ):
                PR._execute_one_run(
                    plan_run, harness_run,
                    hooks=PR.PlanRunnerHooks(),
                    artifact_map={},
                )
            # The launch spec went through with mode=B.
            self.assertEqual(captured["mode"], S.Mode.B)
            # Target is the run's clone dir (run-NN/target/).
            self.assertIn("run-00", captured["target_dir"])
            self.assertTrue(captured["target_dir"].endswith(
                "target"))


# ---------------------------------------------------------------------------
# Round-trip: plan.json copy preserves mode + max_duration_s
# ---------------------------------------------------------------------------


class PlanRoundtripPreservesNewFieldsTests(unittest.TestCase):

    def test_run_plan_writes_mode_and_max_duration_when_set(
            self) -> None:
        run_with_overrides = {
            "description": "B-mode override",
            "repo": "x", "ref": "main",
            "runner": "copilot", "model": "gpt-5.4",
            "channel": "clone",
            "mode": "B",
            "max_duration_s": 9000,
            "parameters": ["--phase", "3"],
            "expect": {},
        }
        run_defaults = {
            "description": "defaults",
            "repo": "y", "ref": "main",
            "runner": "claude", "model": "opus",
            "channel": "clone", "expect": {},
        }
        plan = PR.parse_plan({
            "pools": {"copilot": 1, "claude": 1},
            "runs": [run_defaults, run_with_overrides],
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
            # Defaults run (no mode / no max_duration_s): keys
            # absent so pre-106 plans round-trip byte-stable.
            self.assertNotIn("mode", written["runs"][0])
            self.assertNotIn(
                "max_duration_s", written["runs"][0])
            # Override run: both keys present + correct.
            self.assertEqual(written["runs"][1]["mode"], "B")
            self.assertEqual(
                written["runs"][1]["max_duration_s"], 9000.0,
            )


if __name__ == "__main__":
    unittest.main()
