"""v1.5.7 138 — per-run `prep_timeout_s` override for the install
step.

The 2026-05-29 acceptance run's chi codex case ABORTED_PREP:
`install_skill (npm-local-tgz) timed out after 300.0s`. codex's
npm-local-tgz channel on a cold cache (npm fetch + extract +
dependency resolve) exceeds the 300s default that's fine for
pip-local-wheel. 138 mirrors 106's `max_duration_s` per-run
override: an optional `prep_timeout_s: float` on PlanRun threads
through `prepare` → `_run_install_for_axes` →
`install_skill_channel(timeout_s=…)`.

Covers: parse + validation, the install-step threading
(override set / default absent), the prepare_acceptance forwarding
hop, plan.json round-trip (mirrors the 106 max_duration_s test),
and the ABORTED_PREP message naming the actual timeout.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from bin.harness import plan_runner as PR
from bin.harness import prepare as PREP
from bin.harness import schema as S


def _run(**overrides) -> dict:
    base = {
        "description": "codex npm cold cache",
        "repo": "https://github.com/go-chi/chi", "ref": "master",
        "runner": "codex", "model": "gpt-5.3-codex",
        "channel": "npm-local-tgz", "mode": "B",
        "expect": {},
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# parse + validation
# ---------------------------------------------------------------------------


class ParsePrepTimeoutTests(unittest.TestCase):

    def test_plan_run_default_prep_timeout_is_none(self) -> None:
        plan = PR.parse_plan({"pools": {"codex": 1},
                              "runs": [_run()]})
        self.assertIsNone(plan.runs[0].prep_timeout_s)

    def test_plan_run_explicit_prep_timeout_parses(self) -> None:
        plan = PR.parse_plan({"pools": {"codex": 1},
                              "runs": [_run(prep_timeout_s=900)]})
        self.assertEqual(plan.runs[0].prep_timeout_s, 900.0)
        self.assertIsInstance(plan.runs[0].prep_timeout_s, float)

    def test_plan_run_invalid_prep_timeout_rejected(self) -> None:
        for bad in (0, -1, -900.0, "soon", []):
            with self.subTest(bad=bad):
                with self.assertRaises(PR.PlanError):
                    PR.parse_plan({"pools": {"codex": 1},
                                   "runs": [_run(prep_timeout_s=bad)]})


# ---------------------------------------------------------------------------
# install-step threading (prepare.py)
# ---------------------------------------------------------------------------


class InstallTimeoutThreadingTests(unittest.TestCase):

    def _axes(self) -> S.RunAxes:
        return S.RunAxes(
            runner=S.Runner.CODEX, mode=S.Mode.B,
            install_channel=S.InstallChannel.NPM_LOCAL_TGZ,
            model="gpt-5.3-codex")

    def test_install_step_uses_per_run_override_when_set(self) -> None:
        with mock.patch.object(PREP, "install_skill_channel") as m:
            PREP._run_install_for_axes(
                Path("/tmp/does-not-matter"), axes=self._axes(),
                prep_timeout_s=900.0)
        self.assertEqual(m.call_count, 1)
        self.assertEqual(m.call_args.kwargs.get("timeout_s"), 900.0)

    def test_install_step_uses_default_when_override_absent(
            self) -> None:
        with mock.patch.object(PREP, "install_skill_channel") as m:
            PREP._run_install_for_axes(
                Path("/tmp/does-not-matter"), axes=self._axes(),
                prep_timeout_s=None)
        self.assertEqual(m.call_count, 1)
        # No timeout_s kwarg ⇒ install_skill_channel applies its
        # own 300.0 default (single source of the default).
        self.assertNotIn("timeout_s", m.call_args.kwargs)

    def test_prepare_acceptance_forwards_prep_timeout(self) -> None:
        """The prepare → prepare_acceptance → _run_install_for_axes
        hop forwards the override (no real clone)."""
        case = types.SimpleNamespace(
            type=S.CaseType.ACCEPTANCE,
            inputs=types.SimpleNamespace(
                repo_url="https://github.com/go-chi/chi",
                target_ref="master",
                reference_docs_source=None))
        with mock.patch.object(PREP, "clone_worktree",
                               return_value="deadbeef"), \
             mock.patch.object(PREP, "_run_install_for_axes") as m:
            PREP.prepare_acceptance(
                case, Path("/tmp/dest"), axes=self._axes(),
                prep_timeout_s=900.0)
        self.assertEqual(m.call_args.kwargs.get("prep_timeout_s"),
                         900.0)


# ---------------------------------------------------------------------------
# plan.json round-trip (mirrors the 106 max_duration_s test)
# ---------------------------------------------------------------------------


class PlanJsonRoundtripTests(unittest.TestCase):

    def test_plan_json_roundtrip_preserves_prep_timeout(self) -> None:
        plan = PR.parse_plan({
            "pools": {"codex": 1, "claude": 1},
            "runs": [
                {"description": "default", "repo": "y", "ref": "main",
                 "runner": "claude", "model": "opus",
                 "channel": "clone", "expect": {}},
                _run(prep_timeout_s=900),
            ],
        })

        def _fake(pr, run_dir):
            return {
                "terminal_state": S.TerminalState.ABORTED_PREP.value,
                "facts": None, "transcript": "",
                "axes": S.RunAxes(
                    runner=pr.runner, mode=pr.mode,
                    install_channel=pr.channel, model=pr.model),
            }

        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            PR.run_plan(plan, runs_root,
                        hooks=PR.PlanRunnerHooks(fake_run=_fake))
            harness_run = next(
                d for d in runs_root.iterdir() if d.is_dir())
            written = json.loads(
                (harness_run / "plan.json").read_text(
                    encoding="utf-8"))
            # Default run: field absent (pre-138 byte-stable).
            self.assertNotIn("prep_timeout_s", written["runs"][0])
            # Override run: present + correct.
            self.assertEqual(
                written["runs"][1]["prep_timeout_s"], 900)


# ---------------------------------------------------------------------------
# error message names the actual timeout, not a hardcoded 300
# ---------------------------------------------------------------------------


class TimeoutErrorMessageTests(unittest.TestCase):

    def test_error_message_uses_actual_timeout(self) -> None:
        with mock.patch.object(PREP, "build_install_command",
                               return_value=["true"]), \
             mock.patch.object(
                 PREP.subprocess, "run",
                 side_effect=subprocess.TimeoutExpired(
                     cmd="true", timeout=900.0)):
            with self.assertRaises(PREP.PrepError) as ctx:
                PREP.install_skill_channel(
                    S.InstallChannel.NPM_LOCAL_TGZ,
                    Path("/tmp/dest"), timeout_s=900.0)
        msg = str(ctx.exception)
        self.assertIn("900", msg)
        self.assertNotIn("300", msg)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
