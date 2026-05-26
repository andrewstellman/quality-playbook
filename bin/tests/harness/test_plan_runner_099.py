"""v1.5.7 099 — simplified plan-runner tests.

Covers ``bin/harness/plan_runner.py`` per instruction 099 Task D.
Per the instruction: use a **fake runner + stub gate**; do NOT
spawn real 30-min QPB runs.

Test surfaces:

  ParsePlanTests — flat shape (pools header + runs array),
    flat ``expect`` map with list⇒membership; no `id`
    (index is identity); unknown assertion names rejected.
  PlanFolderLayoutTests — timestamped harness-run dir,
    `plan.json` copy, per-run `run-NN/` layout.
  PoolConcurrencyTests — `pools:{claude:2, codex:1}` enforces
    ≤2 claude + ≤1 codex concurrent; different runners overlap.
  GradeExpectTests — flat expect → assertion-by-assertion grading
    (incl. list⇒membership; gate-FAILED-but-MET is the
    load-bearing case + mutation bite).
  EndToEndFakeRunnerTests — full run_plan() with a fake runner +
    stub facts; SUMMARY.md renders; MET vs NOT-MET vs N/A; N/M
    rollup.
  RenderSummaryTests — table shape; rollup line; non-COMPLETED
    runs show N/A.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from bin.harness import plan_runner as PR
from bin.harness import schema as S


# ---------------------------------------------------------------------------
# Fixture helpers — fake facts + plan-run constructors
# ---------------------------------------------------------------------------


def _mk_facts(*, gate_result: str = "PASS",
              verdict_state: str = "solid",
              attribution: str = "none",
              recommends_stronger_model: bool = False,
              substantive_fail_count: int = 0,
              record_keeping_fail_count: int = 0,
              banner_rendered: bool = True,
              gitignore_remediation_followed: bool = True,
              first_probe_ok: bool = True,
              detected_runner: str = "claude-code",
              ) -> S.RunFacts:
    return S.RunFacts(
        phase0=S.Phase0Facts(
            status="ok", probe_attempts=1,
            first_probe_ok=first_probe_ok,
        ),
        verdict=S.VerdictFacts(
            verdict_state=S.VerdictState(verdict_state),
            attribution=S.Attribution(attribution),
            recommends_stronger_model=recommends_stronger_model,
            bugs_unverified_present=False,
        ),
        provenance=S.ProvenanceFacts(
            detected_runner=detected_runner,
            selfreport_model_label="opus",
            gate_bug_count=0, reported_bug_count=None,
            provenance_mismatch=False,
        ),
        gate=S.GateFacts(
            gate_total="(synthetic)",
            gate_result=S.GateResult(gate_result),
            cleanup_gaps=0,
            substantive_fail_count=substantive_fail_count,
            record_keeping_fail_count=record_keeping_fail_count,
        ),
        install=S.InstallSurfaceFacts(
            banner_rendered=banner_rendered,
            gitignore_remediation_followed=gitignore_remediation_followed,
        ),
        run_meta=S.RunMetaFacts(
            blocked=False, stop_reason=None, exit_code=0,
            timings={}, raw_receipt="stream.ndjson",
        ),
    )


def _mk_axes(runner: S.Runner = S.Runner.CLAUDE) -> S.RunAxes:
    return S.RunAxes(
        runner=runner, mode=S.Mode.A,
        install_channel=S.InstallChannel.CLONE,
        model="opus",
    )


def _solid_plan_dict() -> dict:
    return {
        "pools": {"claude": 1},
        "runs": [{
            "description": "smoke",
            "repo": "https://github.com/example/repo",
            "ref": "main",
            "runner": "claude",
            "model": "opus",
            "channel": "clone",
            "expect": {
                "gate_result": "PASS",
                "verdict_state": "solid",
            },
        }],
    }


# ---------------------------------------------------------------------------
# Parse the flat plan format
# ---------------------------------------------------------------------------


class ParsePlanTests(unittest.TestCase):

    def test_basic_plan_parses(self) -> None:
        plan = PR.parse_plan(_solid_plan_dict())
        self.assertEqual(plan.pools, {"claude": 1})
        self.assertEqual(len(plan.runs), 1)
        run = plan.runs[0]
        self.assertEqual(run.index, 0)
        self.assertEqual(run.runner, S.Runner.CLAUDE)
        self.assertEqual(run.channel, S.InstallChannel.CLONE)
        self.assertEqual(run.expect, {"gate_result": "PASS",
                                       "verdict_state": "solid"})

    def test_no_id_field_index_is_identity(self) -> None:
        """Per design: no `id` — array index identifies the run.
        `description` is the human justification."""
        raw = {
            "pools": {},
            "runs": [
                {"description": "first", "repo": "a", "ref": "x",
                 "runner": "claude", "model": "m",
                 "channel": "clone", "expect": {}},
                {"description": "second", "repo": "b", "ref": "y",
                 "runner": "codex", "model": "m",
                 "channel": "clone", "expect": {}},
            ],
        }
        plan = PR.parse_plan(raw)
        self.assertEqual(plan.runs[0].index, 0)
        self.assertEqual(plan.runs[1].index, 1)
        self.assertEqual(plan.runs[0].description, "first")

    def test_flat_expect_with_list_value(self) -> None:
        """Per design: a list value means 'one of' (membership)."""
        raw = _solid_plan_dict()
        raw["runs"][0]["expect"] = {
            "gate_result": ["PASS", "CLEANUP"],
        }
        plan = PR.parse_plan(raw)
        self.assertEqual(plan.runs[0].expect["gate_result"],
                         ["PASS", "CLEANUP"])

    def test_unknown_assertion_in_expect_rejected(self) -> None:
        raw = _solid_plan_dict()
        raw["runs"][0]["expect"] = {
            "totally_made_up_assertion": True,
        }
        with self.assertRaises(PR.PlanError) as ctx:
            PR.parse_plan(raw)
        self.assertIn("unknown assertion", str(ctx.exception))

    def test_missing_required_field_rejected(self) -> None:
        raw = _solid_plan_dict()
        del raw["runs"][0]["repo"]
        with self.assertRaises(PR.PlanError) as ctx:
            PR.parse_plan(raw)
        self.assertIn("repo", str(ctx.exception))

    def test_at_version_suffix_split_off(self) -> None:
        """channel with @<version> suffix splits into
        (channel, install_version)."""
        raw = _solid_plan_dict()
        raw["runs"][0]["channel"] = "pip-registry@1.5.7"
        plan = PR.parse_plan(raw)
        self.assertEqual(plan.runs[0].channel,
                         S.InstallChannel.PIP_REGISTRY)
        self.assertEqual(plan.runs[0].install_version, "1.5.7")

    def test_bad_pool_value_rejected(self) -> None:
        raw = _solid_plan_dict()
        raw["pools"] = {"claude": -1}
        with self.assertRaises(PR.PlanError):
            PR.parse_plan(raw)


class LoadPlanFileTests(unittest.TestCase):

    def test_load_plan_from_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "plan.json"
            path.write_text(json.dumps(_solid_plan_dict()))
            plan = PR.load_plan(path)
            self.assertEqual(len(plan.runs), 1)


# ---------------------------------------------------------------------------
# Folder layout
# ---------------------------------------------------------------------------


class PlanFolderLayoutTests(unittest.TestCase):

    def _fake_completed(self, plan_run, run_dir):
        return {
            "terminal_state": "COMPLETED",
            "facts": _mk_facts(),
            "transcript": "",
            "axes": _mk_axes(plan_run.runner),
        }

    def test_creates_timestamped_harness_run_dir(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            runs_root = Path(td)
            plan = PR.parse_plan(_solid_plan_dict())
            hooks = PR.PlanRunnerHooks(fake_run=self._fake_completed)
            PR.run_plan(plan, runs_root, hooks=hooks)
            # Exactly one timestamped subdir was created.
            children = list(runs_root.iterdir())
            self.assertEqual(len(children), 1)
            harness_run_dir = children[0]
            # Name matches YYYYMMDDTHHMMSSZ.
            import re
            self.assertRegex(
                harness_run_dir.name,
                r"^\d{8}T\d{6}Z$",
            )

    def test_copies_plan_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            runs_root = Path(td)
            plan = PR.parse_plan(_solid_plan_dict())
            hooks = PR.PlanRunnerHooks(fake_run=self._fake_completed)
            PR.run_plan(plan, runs_root, hooks=hooks)
            harness_run_dir = next(runs_root.iterdir())
            self.assertTrue((harness_run_dir / "plan.json").is_file())
            copied = json.loads(
                (harness_run_dir / "plan.json").read_text(
                    encoding="utf-8",
                )
            )
            self.assertEqual(copied["pools"], {"claude": 1})
            self.assertEqual(len(copied["runs"]), 1)

    def test_per_run_run_NN_dir_layout(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            runs_root = Path(td)
            raw = _solid_plan_dict()
            # Two runs → run-00 + run-01.
            raw["runs"].append({
                **raw["runs"][0],
                "description": "second",
            })
            plan = PR.parse_plan(raw)
            hooks = PR.PlanRunnerHooks(fake_run=self._fake_completed)
            PR.run_plan(plan, runs_root, hooks=hooks)
            harness_run_dir = next(runs_root.iterdir())
            self.assertTrue(
                (harness_run_dir / "run-00").is_dir())
            self.assertTrue(
                (harness_run_dir / "run-01").is_dir())
            # Each carries facts.json + grading.json.
            for i in (0, 1):
                rd = harness_run_dir / f"run-{i:02d}"
                self.assertTrue((rd / "facts.json").is_file())
                self.assertTrue((rd / "grading.json").is_file())


# ---------------------------------------------------------------------------
# Pool concurrency
# ---------------------------------------------------------------------------


class PoolConcurrencyTests(unittest.TestCase):
    """Pin that `pools` is respected: pools=2 for claude →
    2 claude runs concurrent; pools=1 for codex → 1 codex run at
    a time; different runners overlap."""

    def _make_observation_runner(self, claude_max_obs,
                                   codex_max_obs):
        """Returns a fake runner that records the current
        per-runner in-flight count and updates the max observed."""
        state = {
            "claude_inflight": 0, "codex_inflight": 0,
            "claude_max": 0, "codex_max": 0,
        }
        lock = threading.Lock()

        def _fake(plan_run, run_dir):
            with lock:
                key = f"{plan_run.runner.value}_inflight"
                state[key] += 1
                state[f"{plan_run.runner.value}_max"] = max(
                    state[f"{plan_run.runner.value}_max"],
                    state[key],
                )
            time.sleep(0.15)  # hold the slot long enough to overlap
            with lock:
                state[f"{plan_run.runner.value}_inflight"] -= 1
            return {
                "terminal_state": "COMPLETED",
                "facts": _mk_facts(),
                "transcript": "",
                "axes": _mk_axes(plan_run.runner),
            }

        return _fake, state

    def test_per_runner_cap_respected(self) -> None:
        """5 claude + 3 codex runs with pools={claude:2, codex:1}
        → max observed claude in-flight ≤ 2, max codex ≤ 1."""
        with tempfile.TemporaryDirectory() as td:
            runs_root = Path(td)
            raw = {
                "pools": {"claude": 2, "codex": 1},
                "runs": [],
            }
            for i in range(5):
                raw["runs"].append({
                    "description": f"c{i}", "repo": "r", "ref": "x",
                    "runner": "claude", "model": "m",
                    "channel": "clone", "expect": {},
                })
            for i in range(3):
                raw["runs"].append({
                    "description": f"x{i}", "repo": "r", "ref": "x",
                    "runner": "codex", "model": "m",
                    "channel": "clone", "expect": {},
                })
            plan = PR.parse_plan(raw)
            fake, state = self._make_observation_runner(2, 1)
            hooks = PR.PlanRunnerHooks(fake_run=fake)
            PR.run_plan(plan, runs_root, hooks=hooks)
            self.assertLessEqual(
                state["claude_max"], 2,
                "v1.5.7 099: pools.claude=2 must cap concurrent "
                f"claude runs at 2 — observed {state['claude_max']}",
            )
            self.assertLessEqual(
                state["codex_max"], 1,
                "v1.5.7 099: pools.codex=1 must cap concurrent "
                f"codex runs at 1 — observed {state['codex_max']}",
            )

    def test_different_runners_overlap(self) -> None:
        """1 claude + 1 codex with pools={claude:1, codex:1} →
        the runs overlap (different runners are independent)."""
        with tempfile.TemporaryDirectory() as td:
            runs_root = Path(td)
            raw = {
                "pools": {"claude": 1, "codex": 1},
                "runs": [
                    {"description": "c", "repo": "r", "ref": "x",
                     "runner": "claude", "model": "m",
                     "channel": "clone", "expect": {}},
                    {"description": "x", "repo": "r", "ref": "x",
                     "runner": "codex", "model": "m",
                     "channel": "clone", "expect": {}},
                ],
            }
            plan = PR.parse_plan(raw)
            fake, state = self._make_observation_runner(1, 1)
            hooks = PR.PlanRunnerHooks(fake_run=fake)
            # If they don't overlap, total wall time ≥ 2 *
            # 0.15s = 0.3s. If they do overlap (independent
            # runners), it's ~0.15s. The fake sleep is 0.15s,
            # so we assert the total elapsed is under 0.30s
            # (overlap occurred).
            start = time.time()
            PR.run_plan(plan, runs_root, hooks=hooks)
            elapsed = time.time() - start
            self.assertLess(
                elapsed, 0.30,
                f"v1.5.7 099: claude + codex runs MUST overlap "
                f"(different runners → independent pools). Got "
                f"elapsed {elapsed:.3f}s (should be ~0.15s).",
            )


# ---------------------------------------------------------------------------
# grade_expect — the flat expect map, list⇒membership
# ---------------------------------------------------------------------------


class GradeExpectTests(unittest.TestCase):

    def _mk_run(self, expect: dict) -> PR.PlanRun:
        return PR.PlanRun(
            index=0, description="t", repo="r", ref="x",
            runner=S.Runner.CLAUDE, model="m",
            channel=S.InstallChannel.CLONE,
            expect=expect,
        )

    def test_solid_expect_solid_yields_MET(self) -> None:
        run = self._mk_run({"gate_result": "PASS",
                             "verdict_state": "solid"})
        grading = PR.grade_expect(
            run, _mk_facts(), _mk_axes(),
        )
        self.assertEqual(grading.verdict, "MET")
        self.assertEqual(grading.n_passed, 2)

    def test_list_value_means_one_of(self) -> None:
        """Per design: list ⇒ membership."""
        run = self._mk_run(
            {"gate_result": ["PASS", "CLEANUP", "FAIL"]},
        )
        # All three variants should match.
        for gr in ("PASS", "CLEANUP", "FAIL"):
            grading = PR.grade_expect(
                run, _mk_facts(gate_result=gr,
                                 verdict_state="failed"
                                 if gr == "FAIL" else "solid",
                                 substantive_fail_count=2
                                 if gr == "FAIL" else 0),
                _mk_axes(),
            )
            self.assertEqual(grading.verdict, "MET",
                             f"gate_result={gr} should be MET "
                             f"(in the membership list)")

    def test_gate_failed_but_MET_load_bearing(self) -> None:
        """**LOAD-BEARING (instruction 099 Task D mutation
        bite)**: a run whose ``expect`` says ``gate_result:FAIL``
        is MET when the gate FAILS. The `gate` column shows
        QPB's verdict; the `result` column shows whether QPB
        behaved as predicted.

        Mutation bite: change the predicted gate_result to
        "PASS" → this case becomes NOT-MET (the gate FAILED but
        we expected PASS). The reverse — predicting FAIL,
        getting FAIL — is the load-bearing MET.
        """
        run = self._mk_run({
            "gate_result": "FAIL",
            "attribution": "weak_model",
            "recommends_stronger_model": True,
        })
        facts = _mk_facts(
            gate_result="FAIL",
            verdict_state="failed",
            attribution="weak_model",
            recommends_stronger_model=True,
            substantive_fail_count=3,
        )
        grading = PR.grade_expect(run, facts, _mk_axes())
        self.assertEqual(
            grading.verdict, "MET",
            "v1.5.7 099 LOAD-BEARING: predicting FAIL + getting "
            "FAIL == MET (the harness checks acceptance, not "
            "gate-pass).",
        )

    def test_gate_failed_but_predicted_PASS_is_NOT_MET(self) -> None:
        """Mutation bite companion: predicting PASS + getting
        FAIL = NOT-MET."""
        run = self._mk_run({"gate_result": "PASS"})
        facts = _mk_facts(
            gate_result="FAIL",
            verdict_state="failed",
            substantive_fail_count=3,
        )
        grading = PR.grade_expect(run, facts, _mk_axes())
        self.assertEqual(grading.verdict, "NOT-MET")


# ---------------------------------------------------------------------------
# End-to-end run_plan with fake runner
# ---------------------------------------------------------------------------


class EndToEndFakeRunnerTests(unittest.TestCase):

    def test_solid_run_yields_MET(self) -> None:
        plan = PR.parse_plan({
            "pools": {"claude": 1},
            "runs": [{
                "description": "solid",
                "repo": "r", "ref": "x",
                "runner": "claude", "model": "opus",
                "channel": "clone",
                "expect": {"gate_result": "PASS",
                            "verdict_state": "solid"},
            }],
        })
        def _fake(pr, rd):
            return {
                "terminal_state": "COMPLETED",
                "facts": _mk_facts(),
                "transcript": "",
                "axes": _mk_axes(pr.runner),
            }
        with tempfile.TemporaryDirectory() as td:
            outcomes = PR.run_plan(
                plan, Path(td), PR.PlanRunnerHooks(fake_run=_fake),
            )
            self.assertEqual(len(outcomes), 1)
            o = outcomes[0]
            self.assertEqual(o.result, "MET")
            self.assertEqual(o.gate_verdict, "PASSED")
            self.assertEqual(o.terminal_state, "COMPLETED")

    def test_mismatch_yields_NOT_MET(self) -> None:
        plan = PR.parse_plan({
            "pools": {"claude": 1},
            "runs": [{
                "description": "mismatch",
                "repo": "r", "ref": "x",
                "runner": "claude", "model": "opus",
                "channel": "clone",
                "expect": {"gate_result": "PASS"},
            }],
        })
        def _fake(pr, rd):
            return {
                "terminal_state": "COMPLETED",
                "facts": _mk_facts(gate_result="FAIL",
                                    verdict_state="failed",
                                    substantive_fail_count=1),
                "transcript": "",
                "axes": _mk_axes(pr.runner),
            }
        with tempfile.TemporaryDirectory() as td:
            outcomes = PR.run_plan(
                plan, Path(td), PR.PlanRunnerHooks(fake_run=_fake),
            )
            self.assertEqual(outcomes[0].result, "NOT-MET")
            self.assertEqual(outcomes[0].gate_verdict, "FAILED")

    def test_non_COMPLETED_terminal_yields_NA(self) -> None:
        """A run that ended FAILED/TIMED_OUT/BLOCKED/ABORTED_PREP
        grades N/A, NEVER silently MET."""
        for terminal in ("FAILED", "TIMED_OUT", "BLOCKED",
                          "ABORTED_PREP"):
            plan = PR.parse_plan(_solid_plan_dict())
            def _fake(pr, rd, terminal=terminal):
                return {
                    "terminal_state": terminal,
                    "facts": None,
                    "transcript": "",
                    "axes": _mk_axes(pr.runner),
                }
            with tempfile.TemporaryDirectory() as td:
                outcomes = PR.run_plan(
                    plan, Path(td),
                    PR.PlanRunnerHooks(fake_run=_fake),
                )
                self.assertEqual(
                    outcomes[0].result, "N/A",
                    f"v1.5.7 099: terminal {terminal} must grade "
                    f"N/A, never silently MET.",
                )
                self.assertEqual(outcomes[0].gate_verdict, "N/A")

    def test_summary_md_written(self) -> None:
        plan = PR.parse_plan(_solid_plan_dict())
        def _fake(pr, rd):
            return {"terminal_state": "COMPLETED",
                     "facts": _mk_facts(),
                     "transcript": "",
                     "axes": _mk_axes(pr.runner)}
        with tempfile.TemporaryDirectory() as td:
            PR.run_plan(plan, Path(td),
                          PR.PlanRunnerHooks(fake_run=_fake))
            harness_run_dir = next(Path(td).iterdir())
            summary = (harness_run_dir / "SUMMARY.md").read_text(
                encoding="utf-8",
            )
            self.assertIn("# Harness Run Summary", summary)
            self.assertIn("MET", summary)
            self.assertIn("1/1 MET", summary)


# ---------------------------------------------------------------------------
# render_summary
# ---------------------------------------------------------------------------


class RenderSummaryTests(unittest.TestCase):

    def test_renders_row_per_run_plus_rollup(self) -> None:
        plan = PR.parse_plan(_solid_plan_dict())
        outcomes = [PR.RunOutcome(
            index=0, description="solid", repo="r",
            runner="claude", model="opus",
            phase_yn={f"P{i}": "Y" for i in range(7)},
            gate_verdict="PASSED", result="MET",
            terminal_state="COMPLETED",
        )]
        summary = PR.render_summary(plan, outcomes)
        self.assertIn("# Harness Run Summary", summary)
        self.assertIn("solid", summary)
        self.assertIn("PASSED", summary)
        self.assertIn("MET", summary)
        self.assertIn("1/1 MET — acceptance PASSED", summary)

    def test_mixed_rollup(self) -> None:
        plan = PR.parse_plan({
            "pools": {}, "runs": [
                {"description": "a", "repo": "r", "ref": "x",
                 "runner": "claude", "model": "m",
                 "channel": "clone", "expect": {}},
                {"description": "b", "repo": "r", "ref": "x",
                 "runner": "claude", "model": "m",
                 "channel": "clone", "expect": {}},
            ],
        })
        outcomes = [
            PR.RunOutcome(
                index=0, description="met", repo="r",
                runner="claude", model="opus",
                phase_yn={f"P{i}": "Y" for i in range(7)},
                gate_verdict="PASSED", result="MET",
                terminal_state="COMPLETED",
            ),
            PR.RunOutcome(
                index=1, description="not-met", repo="r",
                runner="claude", model="opus",
                phase_yn={f"P{i}": "N" for i in range(7)},
                gate_verdict="FAILED", result="NOT-MET",
                terminal_state="COMPLETED",
            ),
        ]
        summary = PR.render_summary(plan, outcomes)
        self.assertIn("1/2 MET — acceptance FAILED", summary)


# ---------------------------------------------------------------------------
# Sample acceptance_plan.json parses
# ---------------------------------------------------------------------------


class AcceptancePlanShipsTests(unittest.TestCase):

    def test_acceptance_plan_json_parses(self) -> None:
        """The shipped `bin/harness/acceptance_plan.json` parses
        via parse_plan + carries gson + chi + keto runs."""
        path = (Path(__file__).resolve().parents[3]
                 / "bin" / "harness" / "acceptance_plan.json")
        self.assertTrue(
            path.is_file(),
            f"v1.5.7 099 Task B: acceptance_plan.json must ship "
            f"at {path}",
        )
        plan = PR.load_plan(path)
        repos = [r.repo for r in plan.runs]
        self.assertTrue(any("gson" in r for r in repos),
                        "gson run required (solid)")
        self.assertTrue(any("chi" in r for r in repos),
                        "chi run required (weak_model)")
        self.assertTrue(any("keto" in r for r in repos),
                        "keto run required (honest verdict)")


if __name__ == "__main__":
    unittest.main()
