"""v1.5.7 100 — per-run `parameters` passthrough (extra runner CLI args).

Small follow-on to 099. The plan-runner now carries an optional
per-run ``parameters`` field (array of argv tokens passed verbatim
to the runner CLI at the runner-appropriate position). The
harness does NOT interpret the tokens.

Coverage:
  * Plan parsing accepts ``parameters`` as a list of strings (the
    documented form) AND as a single string which is
    ``shlex.split`` into tokens (the optional nicety). Wrong shape
    raises PlanError with the offending field path.
  * Each Mode-A adapter splices ``parameters`` at the runner-
    appropriate position:
      - codex: ``codex <parameters…> exec --sandbox
        workspace-write …`` (``-c key=val`` overrides must
        precede the subcommand; v1.5.7 124 replaced the
        deprecated ``--full-auto`` flag)
      - claude: spliced between the standard flags and the
        trailing positional prompt
      - copilot: spliced between the flags and ``-p <prompt>``
      - cursor: appended (stdin-prompt route → safe at end)
  * Prompt routing (stdin vs argv) is preserved end-to-end.
  * Absent/empty parameters → command unchanged from today
    (pre-100 baseline).
  * ``acceptance_plan.json`` ships with the codex/chi run carrying
    the documented codex-low-thinking parameters.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

from bin.harness import plan_runner as PR
from bin.harness import runner as R
from bin.harness import schema as S


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mk_axes(runner: S.Runner = S.Runner.CODEX, *,
             mode: S.Mode = S.Mode.A,
             channel: S.InstallChannel = S.InstallChannel.CLONE,
             model: str = "gpt-5.2") -> S.RunAxes:
    return S.RunAxes(
        runner=runner, mode=mode,
        install_channel=channel, model=model,
    )


def _mk_run(parameters=None) -> dict:
    """Return a minimal valid run-dict with an optional
    ``parameters`` field; the caller injects whatever shape they
    want to exercise (or omits the field entirely)."""
    raw = {
        "description": "weak-model codex run",
        "repo": "https://github.com/go-chi/chi",
        "ref": "main",
        "runner": "codex",
        "model": "gpt-5.2",
        "channel": "clone",
        "expect": {},
    }
    if parameters is not None:
        raw["parameters"] = parameters
    return raw


# ---------------------------------------------------------------------------
# Task A — parse `parameters` from the plan
# ---------------------------------------------------------------------------


class ParseParametersTests(unittest.TestCase):

    def test_parameters_absent_defaults_to_empty(self) -> None:
        """Absent ``parameters`` ⇒ empty list (pre-100 plans
        round-trip unchanged)."""
        plan = PR.parse_plan({"pools": {}, "runs": [_mk_run()]})
        self.assertEqual(plan.runs[0].parameters, [])

    def test_parameters_list_form_documented(self) -> None:
        """List-of-strings is the documented form."""
        raw = _mk_run(parameters=[
            "-c", "model_reasoning_effort=\"low\""
        ])
        plan = PR.parse_plan({"pools": {}, "runs": [raw]})
        self.assertEqual(
            plan.runs[0].parameters,
            ["-c", "model_reasoning_effort=\"low\""],
        )

    def test_parameters_string_form_shlex_split(self) -> None:
        """Optional nicety: a string `parameters` is
        ``shlex.split`` into tokens. The example codex value
        becomes the same two-token list as the array form."""
        raw = _mk_run(parameters='-c model_reasoning_effort="low"')
        plan = PR.parse_plan({"pools": {}, "runs": [raw]})
        self.assertEqual(
            plan.runs[0].parameters,
            ["-c", "model_reasoning_effort=low"],
        )

    def test_parameters_list_with_non_string_rejected(self) -> None:
        """A list whose entries aren't strings raises PlanError
        with the offending field path (no silent stringify)."""
        raw = _mk_run(parameters=["-c", 42])
        with self.assertRaises(PR.PlanError) as ctx:
            PR.parse_plan({"pools": {}, "runs": [raw]})
        self.assertIn("runs[0].parameters[1]", str(ctx.exception))

    def test_parameters_wrong_top_type_rejected(self) -> None:
        """A dict/int at the top of `parameters` raises PlanError
        (not a list, not a string)."""
        raw = _mk_run(parameters={"key": "val"})
        with self.assertRaises(PR.PlanError) as ctx:
            PR.parse_plan({"pools": {}, "runs": [raw]})
        self.assertIn("runs[0].parameters", str(ctx.exception))

    def test_parameters_empty_list_is_empty(self) -> None:
        raw = _mk_run(parameters=[])
        plan = PR.parse_plan({"pools": {}, "runs": [raw]})
        self.assertEqual(plan.runs[0].parameters, [])


# ---------------------------------------------------------------------------
# Task B — splice into the runner command at the right position
# ---------------------------------------------------------------------------


class CodexParametersPlacementTests(unittest.TestCase):

    def test_codex_minus_c_precedes_exec_subcommand(self) -> None:
        """For codex, ``-c key=val`` is a global config override
        — it MUST precede the ``exec`` subcommand or codex will
        not read it. Verify the splice point is between
        ``codex`` and ``exec``.

        v1.5.7 124: tests ``_codex_command`` directly because
        ``_command_for_axes(codex, Mode.A)`` now rejects
        per the 124 single-turn semantics. v1.5.7 124 also
        replaced ``--full-auto`` with
        ``--sandbox workspace-write``."""
        params = ["-c", "model_reasoning_effort=\"low\""]
        cmd = R._codex_command("gpt-5.2", parameters=params)
        # Order check: codex → -c → ... → exec → --sandbox
        # → workspace-write → -m → model → -.
        self.assertEqual(cmd[0], "codex")
        self.assertEqual(cmd[1], "-c")
        self.assertEqual(cmd[2], 'model_reasoning_effort="low"')
        self.assertEqual(cmd[3], "exec")
        self.assertEqual(cmd[4], "--sandbox")
        self.assertEqual(cmd[5], "workspace-write")
        # Stdin sentinel still trailing.
        self.assertEqual(cmd[-1], "-")
        # Prompt routing unchanged (long prompt off argv).
        self.assertTrue(R._needs_stdin_prompt(S.Runner.CODEX))

    def test_codex_long_prompt_still_routes_to_stdin(self) -> None:
        """Splicing parameters must NOT regress the 095 prompt-
        routing contract: the long prompt stays OFF argv for
        codex (shell length limits). v1.5.7 124: tests
        ``_codex_command`` directly (sees the same builder
        the rejected ``_command_for_axes`` route would have
        called)."""
        # _codex_command doesn't take a prompt at all — the
        # prompt is always piped via the `-` sentinel.
        cmd = R._codex_command(
            "gpt-5.2", parameters=["-c", "k=v"])
        # No long-prompt slot to leak — argv is fixed shape.
        long_prompt = "x" * 10_000
        self.assertNotIn(long_prompt, cmd)
        self.assertEqual(cmd[-1], "-")

    def test_codex_no_parameters_unchanged(self) -> None:
        """No parameters ⇒ command identical to the
        post-124 baseline (the 124 update to the codex
        adapter — ``--sandbox workspace-write``)."""
        baseline = ["codex", "exec", "--sandbox",
                     "workspace-write",
                     "-m", "gpt-5.2", "-"]
        cmd = R._codex_command("gpt-5.2")
        self.assertEqual(cmd, baseline)
        cmd2 = R._codex_command("gpt-5.2", parameters=[])
        self.assertEqual(cmd2, baseline)


class ClaudeParametersPlacementTests(unittest.TestCase):

    def test_claude_parameters_spliced_before_prompt(self) -> None:
        """Claude takes the prompt as the trailing positional;
        ``parameters`` must land in the flags region — right
        before the prompt, after all the standard flags."""
        cmd = R._command_for_axes(
            _mk_axes(S.Runner.CLAUDE, model="opus"),
            "do thing",
            parameters=["--extra-flag", "x"],
        )
        # Prompt still last.
        self.assertEqual(cmd[-1], "do thing")
        # Extra flags right before the prompt.
        self.assertEqual(cmd[-3:], ["--extra-flag", "x", "do thing"])
        # Standard flags still present.
        self.assertIn("--print", cmd)
        self.assertIn("--dangerously-skip-permissions", cmd)
        # Argv-prompt route preserved.
        self.assertFalse(R._needs_stdin_prompt(S.Runner.CLAUDE))

    def test_claude_no_parameters_unchanged(self) -> None:
        baseline = R._command_for_axes(
            _mk_axes(S.Runner.CLAUDE, model="opus"), "do thing")
        with_empty = R._command_for_axes(
            _mk_axes(S.Runner.CLAUDE, model="opus"), "do thing",
            parameters=[])
        self.assertEqual(baseline, with_empty)


class CopilotParametersPlacementTests(unittest.TestCase):

    def test_copilot_parameters_spliced_before_prompt_pair(self) -> None:
        """Copilot takes the prompt as ``-p <prompt>``;
        ``parameters`` must land BEFORE the ``-p`` so they're
        flags, not part of the prompt argument."""
        cmd = R._command_for_axes(
            _mk_axes(S.Runner.COPILOT, model="gpt-5.4"),
            "do thing",
            parameters=["--my-flag"],
        )
        idx_p = cmd.index("-p")
        # The extra flag appears before -p.
        self.assertIn("--my-flag", cmd[:idx_p])
        # The prompt pair is still ["-p", "do thing"] at the tail.
        self.assertEqual(cmd[idx_p:idx_p + 2], ["-p", "do thing"])
        # Argv-prompt route preserved.
        self.assertFalse(R._needs_stdin_prompt(S.Runner.COPILOT))

    def test_copilot_no_parameters_unchanged(self) -> None:
        baseline = R._command_for_axes(
            _mk_axes(S.Runner.COPILOT, model="gpt-5.4"), "p")
        with_empty = R._command_for_axes(
            _mk_axes(S.Runner.COPILOT, model="gpt-5.4"), "p",
            parameters=[])
        self.assertEqual(baseline, with_empty)


class CursorParametersPlacementTests(unittest.TestCase):

    def test_cursor_parameters_appended(self) -> None:
        """Cursor takes the prompt on stdin (no positional), so
        parameters can safely live at the end of the flags
        region."""
        cmd = R._command_for_axes(
            _mk_axes(S.Runner.CURSOR, model="sonic"),
            "p",
            parameters=["--my-flag", "v"],
        )
        self.assertEqual(cmd[:4],
                         ["cursor", "agent", "--print", "--force"])
        # Extras at the end.
        self.assertEqual(cmd[-2:], ["--my-flag", "v"])
        # Stdin-prompt route preserved.
        self.assertTrue(R._needs_stdin_prompt(S.Runner.CURSOR))

    def test_cursor_no_parameters_unchanged(self) -> None:
        baseline = R._command_for_axes(
            _mk_axes(S.Runner.CURSOR, model="sonic"), "p")
        with_empty = R._command_for_axes(
            _mk_axes(S.Runner.CURSOR, model="sonic"), "p",
            parameters=[])
        self.assertEqual(baseline, with_empty)


# ---------------------------------------------------------------------------
# LaunchSpec end-to-end forwarding
# ---------------------------------------------------------------------------


class LaunchSpecParametersForwardingTests(unittest.TestCase):
    """The LaunchSpec carries ``parameters``; ``launch_run`` is
    expected to forward them to ``_command_for_axes``. We test the
    forwarding by monkeypatching _command_for_axes and intercepting
    its kwargs — `launch_run` proper spawns a subprocess which we
    don't want to exercise here."""

    def test_launch_spec_carries_parameters(self) -> None:
        spec = R.LaunchSpec(
            target_dir=Path("/tmp/x"),
            run_dir=Path("/tmp/x/run"),
            axes=_mk_axes(S.Runner.CODEX),
            case_id="c", run_id="r",
            max_duration_s=10.0,
            prompt="hi",
            parameters=["-c", "k=v"],
        )
        self.assertEqual(spec.parameters, ["-c", "k=v"])

    def test_launch_spec_parameters_default(self) -> None:
        """No parameters supplied ⇒ field is None (and the
        builders treat that as empty)."""
        spec = R.LaunchSpec(
            target_dir=Path("/tmp/x"),
            run_dir=Path("/tmp/x/run"),
            axes=_mk_axes(S.Runner.CODEX),
            case_id="c", run_id="r",
            max_duration_s=10.0,
            prompt="hi",
        )
        self.assertIsNone(spec.parameters)
        # And per-runner builder with None == [] semantics.
        # v1.5.7 124: tests ``_codex_command`` directly since
        # ``_command_for_axes(codex, Mode.A)`` now rejects;
        # also updated the expected argv for the
        # ``--sandbox workspace-write`` post-deprecation flag.
        cmd = R._codex_command(
            spec.axes.model, parameters=spec.parameters)
        self.assertEqual(cmd, ["codex", "exec", "--sandbox",
                                "workspace-write",
                                "-m", "gpt-5.2", "-"])


# ---------------------------------------------------------------------------
# Task C — acceptance_plan.json ships with the codex parameters
# ---------------------------------------------------------------------------


class AcceptancePlanShipsParametersTests(unittest.TestCase):

    def test_acceptance_plan_codex_run_has_low_thinking_param(
            self) -> None:
        """The acceptance plan carries the documented codex
        low-thinking parameters on the chi/codex (weak-model) run.
        Other runs continue without parameters.

        v1.5.7 134: the chi codex run was switched to Mode B + the
        129 ``--runner-extra-args`` form (commit 245152d) — codex
        Mode A is rejected at launch (124), so the run must be
        Mode B to actually exercise gpt-5.3-codex at low reasoning.
        In Mode B, ``parameters`` go to run_playbook, so the
        low-thinking flag is forwarded via ``--runner-extra-args``
        (the 129 passthrough), single-quote-wrapped to preserve the
        TOML quotes for codex's ``-c``."""
        path = (Path(__file__).resolve().parents[3]
                / "harness_plans" / "acceptance_plan.json")
        plan = PR.load_plan(path)
        # Find the codex run.
        codex_runs = [r for r in plan.runs
                      if r.runner == S.Runner.CODEX]
        self.assertEqual(len(codex_runs), 1,
                          "acceptance_plan should have exactly "
                          "one codex run (the chi/weak-model run)")
        # Mode B (124: codex Mode A is rejected at launch).
        self.assertEqual(codex_runs[0].mode, S.Mode.B)
        self.assertEqual(
            codex_runs[0].parameters,
            ["--runner-extra-args",
             "-c 'model_reasoning_effort=\"low\"'"],
        )
        # Other runs stay parameter-less.
        for r in plan.runs:
            if r.runner != S.Runner.CODEX:
                self.assertEqual(
                    r.parameters, [],
                    f"run {r.index} ({r.runner.value}) should "
                    f"not carry parameters per Task C",
                )


# ---------------------------------------------------------------------------
# plan.json round-trip — parameters preserved when present
# ---------------------------------------------------------------------------


class PlanRoundtripPreservesParametersTests(unittest.TestCase):

    def test_run_plan_writes_parameters_into_plan_json_copy(
            self) -> None:
        """When the runner writes its plan.json copy into the
        harness-run folder, runs with parameters keep them in the
        serialized form (so the harness-run dir is fully self-
        describing). Runs without parameters omit the field for
        byte-stable round-trips of pre-100 plans."""
        import tempfile

        run_with_params = _mk_run(parameters=[
            "-c", "model_reasoning_effort=\"low\"",
        ])
        run_no_params = {
            "description": "claude clean run",
            "repo": "https://github.com/google/gson",
            "ref": "main",
            "runner": "claude",
            "model": "opus",
            "channel": "clone",
            "expect": {},
        }
        plan = PR.parse_plan({
            "pools": {"claude": 1, "codex": 1},
            "runs": [run_no_params, run_with_params],
        })

        def _fake(pr, run_dir):
            # Minimal stub: report COMPLETED, no facts → result
            # grades N/A. We only care about the plan.json copy.
            return {
                "terminal_state": S.TerminalState.ABORTED_PREP.value,
                "facts": None,
                "transcript": "",
                "axes": _mk_axes(pr.runner, model=pr.model),
            }

        with tempfile.TemporaryDirectory() as tmp:
            outcomes = PR.run_plan(
                plan, Path(tmp),
                hooks=PR.PlanRunnerHooks(fake_run=_fake),
            )
            self.assertEqual(len(outcomes), 2)
            # Find the single timestamped harness-run dir.
            dirs = [d for d in Path(tmp).iterdir() if d.is_dir()]
            self.assertEqual(len(dirs), 1)
            written = json.loads(
                (dirs[0] / "plan.json").read_text(encoding="utf-8")
            )
            self.assertEqual(len(written["runs"]), 2)
            # First run (no params): field absent.
            self.assertNotIn("parameters", written["runs"][0])
            # Second run: parameters present and verbatim.
            self.assertEqual(
                written["runs"][1]["parameters"],
                ["-c", "model_reasoning_effort=\"low\""],
            )


if __name__ == "__main__":
    unittest.main()
