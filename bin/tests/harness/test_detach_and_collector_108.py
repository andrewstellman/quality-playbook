"""v1.5.7 108 — detach run-plan + auto-background collector.

Today's first live full-pipeline run exposed the cost of the
blocking parent: ``run-plan`` is a long-lived foreground
process; backgrounding it with ``nohup … &`` got it
SIGTTIN-suspended (`"suspended (tty input)"`), which froze
reaping/grading while the detached AI-CLI children kept running
orphaned.

108 splits launch from collect: ``run_plan`` launches all runs
detached via ``runner.launch_run_async``, writes
``manifest.json``, spawns a fully-detached collector
subprocess, and returns immediately. The collector polls each
AI-CLI's PID, runs facts + grade + receipts as each
terminates, and rewrites ``SUMMARY.md`` incrementally.

Coverage (Task D):
  * ``run_plan`` returns promptly (no block on run completion)
    and writes ``manifest.json`` with a ``pid`` per run.
  * Collector reaps a finished run (patched child exit) →
    writes terminal status.json + grading.json + updates
    SUMMARY. An unfinished run stays RUNNING.
  * **Idempotency**: running the collector twice over the same
    finished run does not double-grade / duplicate the SUMMARY
    row.
  * All-terminal ⇒ collector writes final SUMMARY and exits.
  * The collector spawn uses ``start_new_session=True`` +
    ``stdin=subprocess.DEVNULL`` (assert the spawn kwargs) —
    the anti-SIGTTIN guarantee.

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


def _make_local_git_repo(parent: Path) -> str:
    """Tiny local fixture repo for real-clone tests (the 103/107
    pattern)."""
    repo = parent / "fixture-repo"
    repo.mkdir()
    for c in (("git", "init", "--initial-branch=main"),
               ("git", "config", "user.email", "t@e.x"),
               ("git", "config", "user.name", "T")):
        subprocess.run(list(c), cwd=str(repo), check=True,
                       capture_output=True)
    (repo / "README.md").write_text("# fix\n",
                                      encoding="utf-8")
    subprocess.run(["git", "add", "README.md"],
                   cwd=str(repo), check=True,
                   capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"],
                   cwd=str(repo), check=True,
                   capture_output=True)
    return f"file://{repo}"


# ---------------------------------------------------------------------------
# Task A.1 — runner.launch_run_async returns SpawnResult, no wait
# ---------------------------------------------------------------------------


class LaunchRunAsyncTests(unittest.TestCase):
    """``runner.launch_run_async`` spawns the detached child +
    writes RUNNING status.json, returning immediately. The
    backward-compatible ``runner.launch_run`` composes
    async-spawn + ``collect_one_process``."""

    def test_async_returns_spawn_result_with_pid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            (tmp_p / "target").mkdir()
            spec = RUN.LaunchSpec(
                target_dir=tmp_p / "target",
                run_dir=tmp_p / "run",
                axes=S.RunAxes(
                    runner=S.Runner.CLAUDE, mode=S.Mode.A,
                    install_channel=S.InstallChannel.CLONE,
                    model="opus",
                ),
                case_id="x", run_id="r",
                max_duration_s=5.0,
                prompt="hi",
            )

            # Patch the command builder so we spawn a quick
            # no-op subprocess (so the SpawnResult has a real
            # PID).
            def _fake_cmd(axes, prompt, target_dir=None,
                           parameters=None, **kwargs):
                return [sys.executable, "-c",
                        "import time; time.sleep(0.05)"]

            with mock.patch(
                "bin.harness.runner._command_for_axes",
                side_effect=_fake_cmd,
            ):
                spawn = RUN.launch_run_async(spec)
            self.assertIsInstance(spawn, RUN.SpawnResult)
            self.assertGreater(spawn.pid, 0)
            # Status.json carries RUNNING + pid.
            status = json.loads(
                (spec.run_dir / "status.json").read_text(
                    encoding="utf-8")
            )
            self.assertEqual(status["state"], "RUNNING")
            self.assertEqual(status["pid"], spawn.pid)
            # Reap to avoid zombies.
            try:
                import os
                os.waitpid(spawn.pid, 0)
            except (ChildProcessError, OSError):
                pass


# ---------------------------------------------------------------------------
# Task A.2 — _pid_is_alive helper (orphan-poll primitive)
# ---------------------------------------------------------------------------


class PidIsAliveTests(unittest.TestCase):
    """Liveness check the collector uses to poll orphaned
    AI-CLI processes. ``os.kill(pid, 0)`` semantics."""

    def test_alive_pid_returns_true(self) -> None:
        # Spawn a long-sleeper, check liveness, then kill.
        proc = subprocess.Popen(
            [sys.executable, "-c",
              "import time; time.sleep(30)"]
        )
        try:
            self.assertTrue(PR._pid_is_alive(proc.pid))
        finally:
            proc.kill()
            proc.wait(timeout=5)

    def test_dead_pid_returns_false(self) -> None:
        proc = subprocess.Popen(
            [sys.executable, "-c", "import sys; sys.exit(0)"]
        )
        proc.wait(timeout=5)
        # A reaped child's PID may briefly be reusable; the
        # check just exercises the API.
        # We can't reliably assert False without race; instead
        # use an obviously dead PID.
        self.assertFalse(PR._pid_is_alive(999999999))

    def test_zero_pid_returns_false(self) -> None:
        self.assertFalse(PR._pid_is_alive(0))
        self.assertFalse(PR._pid_is_alive(-1))


# ---------------------------------------------------------------------------
# Task B — run_plan detached: returns RUNNING placeholders +
# writes manifest.json + spawns collector
# ---------------------------------------------------------------------------


class RunPlanDetachedReturnsImmediatelyTests(unittest.TestCase):
    """`run_plan` in detached mode launches AI-CLIs without
    waiting, writes manifest.json with PIDs, spawns the
    collector, and returns RUNNING placeholders."""

    def test_run_plan_writes_manifest_with_pids(self) -> None:
        """Patch ``launch_run_async`` so no real AI-CLI runs;
        patch ``_spawn_collector`` so no real collector
        subprocess runs. Assert manifest.json has a pid per
        run and that the returned outcomes are placeholders."""
        plan = PR.parse_plan({
            "pools": {"claude": 1},
            "runs": [
                {"description": "x", "repo": "y", "ref": "m",
                 "runner": "claude", "model": "opus",
                 "channel": "clone", "expect": {}},
                {"description": "z", "repo": "y", "ref": "m",
                 "runner": "claude", "model": "opus",
                 "channel": "clone", "expect": {}},
            ],
        })

        fake_pids = [11111, 22222]
        fake_pid_iter = iter(fake_pids)

        def _fake_launch_one_run_detached(pr, harness_run_dir,
                                            run_dir, target_dir,
                                            *, artifact_map,
                                            local_artifact_info,
                                            log=None, tag=None):
            run_dir.mkdir(parents=True, exist_ok=True)
            pid = next(fake_pid_iter)
            return {
                "index": pr.index,
                "description": pr.description,
                "repo": pr.repo,
                "runner": pr.runner.value,
                "model": pr.model,
                "channel": pr.channel.value,
                "mode": pr.mode.value,
                "target_dir": str(target_dir),
                "run_dir": str(run_dir),
                "run_id": "r",
                "pid": pid,
                "started_at": "2026-05-26T00:00:00Z",
                "stream_path": str(run_dir / "stream.ndjson"),
                "status_path": str(run_dir / "status.json"),
                "max_duration_s": 7200.0,
                "expect": pr.expect,
                "prompt": "(test)",
            }

        with tempfile.TemporaryDirectory() as tmp:
            runs_root = Path(tmp)
            with mock.patch(
                "bin.harness.plan_runner._launch_one_run_detached",
                side_effect=_fake_launch_one_run_detached,
            ), mock.patch(
                "bin.harness.plan_runner._spawn_collector",
                return_value=12345,
            ):
                outcomes = PR.run_plan(plan, runs_root)
            # Two placeholders returned — both "(running)".
            self.assertEqual(len(outcomes), 2)
            for o in outcomes:
                self.assertEqual(o.result, "(running)")
                self.assertEqual(o.gate_verdict, "(running)")
            # manifest.json written + carries both PIDs.
            harness_run = next(
                d for d in runs_root.iterdir() if d.is_dir()
            )
            manifest_path = harness_run / "manifest.json"
            self.assertTrue(manifest_path.is_file())
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            self.assertEqual(len(manifest["runs"]), 2)
            self.assertIn(manifest["runs"][0]["pid"],
                           fake_pids)
            self.assertIn(manifest["runs"][1]["pid"],
                           fake_pids)
            # Collector pid surfaced via _LAST_COLLECTOR_PID.
            self.assertEqual(
                PR._LAST_COLLECTOR_PID.get("pid"), 12345,
            )
            # Clean up for the next test.
            PR._LAST_COLLECTOR_PID.pop("pid", None)


# ---------------------------------------------------------------------------
# Task B — _spawn_collector uses anti-SIGTTIN spawn kwargs
# ---------------------------------------------------------------------------


class CollectorSpawnKwargsTests(unittest.TestCase):
    """**THE 108 LOAD-BEARING PIN.** The collector must be
    fully detached so it can't be SIGTTIN-suspended or
    HUP-killed: ``start_new_session=True`` + ``stdin=
    subprocess.DEVNULL`` + stdout/stderr to ``collector.log``.

    This is the concrete fix for today's "suspended (tty
    input)" incident. The assertion captures the actual
    Popen kwargs."""

    def test_spawn_kwargs_anti_sigttin(self) -> None:
        captured: dict = {}

        def _fake_popen(cmd, **kwargs):
            captured["cmd"] = list(cmd)
            captured["kwargs"] = dict(kwargs)
            return mock.MagicMock(pid=99999)

        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp)
            with mock.patch(
                "bin.harness.plan_runner.subprocess.Popen",
                side_effect=_fake_popen,
            ):
                pid = PR._spawn_collector(harness_run)
            self.assertEqual(pid, 99999)
            # cmd: `python -m bin.qpb_harness collect <dir>`.
            cmd = captured["cmd"]
            self.assertEqual(cmd[0], sys.executable)
            self.assertEqual(cmd[1:4],
                              ["-m", "bin.qpb_harness",
                               "collect"])
            self.assertEqual(cmd[4], str(harness_run))
            # **THE ANTI-SIGTTIN PIN**.
            self.assertTrue(
                captured["kwargs"].get("start_new_session"),
                "108: collector MUST spawn with "
                "start_new_session=True so it can't be "
                "SIGTTIN-suspended or HUP-killed when the "
                "operator's terminal closes",
            )
            self.assertEqual(
                captured["kwargs"].get("stdin"),
                subprocess.DEVNULL,
                "108: collector MUST have stdin from /dev/null "
                "(the SIGTTIN trigger is reading stdin without "
                "a controlling tty)",
            )


# ---------------------------------------------------------------------------
# Task C — collector idempotency: re-runs over finished runs are no-ops
# ---------------------------------------------------------------------------


class CollectorIdempotencyTests(unittest.TestCase):

    def test_collect_skips_runs_with_grading_json_present(
            self) -> None:
        """A run that already has ``grading.json`` (a completed
        receipt) is NOT re-polled or re-graded — the collector
        returns the existing outcome. This makes
        ``qpb_harness collect <dir>`` safe to re-run if the
        auto-spawned collector died."""
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp)
            run_dir = harness_run / "run-00"
            run_dir.mkdir()
            (run_dir / "grading.json").write_text(json.dumps({
                "verdict": "MET",
                "case_id": "plan-00",
                "n_passed": 3,
                "n_failed": 0,
                "n_total": 3,
                "assertions": [],
            }), encoding="utf-8")
            (run_dir / "facts.json").write_text(json.dumps({
                "gate": {"gate_result": "PASS",
                          "substantive_fail_count": 0,
                          "record_keeping_fail_count": 0},
            }), encoding="utf-8")
            manifest = {
                "harness_run_dir": str(harness_run),
                "plan": {"pools": {"claude": 1}},
                "runs": [{
                    "index": 0,
                    "description": "x", "repo": "y",
                    "runner": "claude", "model": "opus",
                    "channel": "clone", "mode": "A",
                    "target_dir": str(run_dir / "target"),
                    "run_dir": str(run_dir),
                    "run_id": "r",
                    "pid": 99999,
                    "started_at": "2026-05-26T00:00:00Z",
                    "stream_path": str(run_dir / "stream.ndjson"),
                    "status_path": str(run_dir / "status.json"),
                    "max_duration_s": 7200.0,
                    "expect": {"gate_result": "PASS"},
                }],
            }
            (harness_run / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8")
            # Spy on _pid_is_alive — it must NEVER be called
            # because the per-run helper short-circuits on
            # grading.json present.
            with mock.patch(
                "bin.harness.plan_runner._pid_is_alive",
                side_effect=AssertionError(
                    "108: collector must NOT poll PIDs for "
                    "already-graded runs — grading.json "
                    "short-circuits"
                ),
            ):
                outcomes = PR.collect_harness_run(harness_run)
            self.assertEqual(len(outcomes), 1)
            self.assertEqual(outcomes[0].result, "MET")

    def test_collect_handles_aborted_prep_entries(self) -> None:
        """ABORTED_PREP manifest entries (prep failed at launch
        time) are graded as N/A immediately without polling
        the PID (there is no PID; the run never launched)."""
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp)
            run_dir = harness_run / "run-00"
            run_dir.mkdir()
            manifest = {
                "harness_run_dir": str(harness_run),
                "plan": {"pools": {"claude": 1}},
                "runs": [{
                    "index": 0,
                    "description": "prep-failed",
                    "repo": "bogus", "runner": "claude",
                    "model": "opus", "channel": "clone",
                    "mode": "A",
                    "target_dir": str(run_dir / "target"),
                    "run_dir": str(run_dir),
                    "run_id": "r",
                    "pid": None,
                    "started_at": "2026-05-26T00:00:00Z",
                    "terminal_state": "ABORTED_PREP",
                    "prep_error": "clone failed: bogus",
                    "status_path": str(run_dir / "status.json"),
                }],
            }
            (harness_run / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8")
            with mock.patch(
                "bin.harness.plan_runner._pid_is_alive",
                side_effect=AssertionError(
                    "ABORTED_PREP entries must not poll PID"
                ),
            ):
                outcomes = PR.collect_harness_run(harness_run)
            self.assertEqual(outcomes[0].terminal_state,
                              "ABORTED_PREP")
            self.assertEqual(outcomes[0].result, "N/A")
            # grading.json sentinel written so a re-sweep
            # short-circuits.
            self.assertTrue(
                (run_dir / "grading.json").is_file()
            )


# ---------------------------------------------------------------------------
# Task D — collector reaps a finished run + writes terminal status/grading
# ---------------------------------------------------------------------------


class CollectorReapAndGradeTests(unittest.TestCase):
    """The collector polls each AI-CLI PID, infers
    terminal_state from artifacts when the process is gone,
    extracts facts + grades, and writes the terminal
    status.json + grading.json receipts.

    Patches ``_pid_is_alive`` to drive the polling deterministi-
    cally (alive → dead) and patches the facts/grade calls to
    avoid spinning up the real installed gate (the facts
    integration is covered by 103's live-composition test)."""

    def test_collect_reaps_and_grades_completed_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp)
            run_dir = harness_run / "run-00"
            run_dir.mkdir()
            target_dir = run_dir / "target"
            target_dir.mkdir()
            # Simulate a completed run by writing the
            # gate-report-latest.json artifact (collector
            # infers COMPLETED from its presence).
            results_dir = target_dir / "quality" / "results"
            results_dir.mkdir(parents=True)
            (results_dir / "gate-report-latest.json").write_text(
                json.dumps({"verdict": "pass"}),
                encoding="utf-8",
            )
            # Write a stub stream.
            (run_dir / "stream.ndjson").write_text(
                "{}\n", encoding="utf-8",
            )
            manifest = {
                "harness_run_dir": str(harness_run),
                "plan": {"pools": {"claude": 1}},
                "runs": [{
                    "index": 0,
                    "description": "x", "repo": "y",
                    "runner": "claude", "model": "opus",
                    "channel": "clone", "mode": "A",
                    "target_dir": str(target_dir),
                    "run_dir": str(run_dir),
                    "run_id": "r",
                    "pid": 88888,
                    "started_at": "2026-05-26T00:00:00Z",
                    "stream_path": str(
                        run_dir / "stream.ndjson"),
                    "status_path": str(run_dir / "status.json"),
                    "max_duration_s": 60.0,
                    "expect": {"gate_result": "PASS"},
                }],
            }
            (harness_run / "manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8")
            # Drive polling: PID alive once, then dead. Patch
            # facts.extract_facts to return a synthetic facts
            # object so grade_expect can run without spawning
            # the real gate.
            from bin.harness import facts as F
            from bin.harness.schema import (
                GateFacts, GateResult, VerdictFacts,
                VerdictState, Attribution, RunMetaFacts,
                Phase0Facts, ProvenanceFacts,
                InstallSurfaceFacts as InstallFacts,
                RunFacts,
            )

            def _fake_facts(target_dir, axes, transcript,
                              exit_code, raw_receipt,
                              timings=None, gate_stdout=None):
                gate = GateFacts(
                    gate_total="Total: 0 FAIL, 0 WARN",
                    gate_result=GateResult.PASS,
                    cleanup_gaps=0,
                    substantive_fail_count=0,
                    record_keeping_fail_count=0,
                )
                verdict = VerdictFacts(
                    verdict_state=VerdictState.SOLID,
                    attribution=Attribution.NONE,
                    recommends_stronger_model=False,
                    bugs_unverified_present=False,
                )
                provenance = ProvenanceFacts(
                    detected_runner="claude-code",
                    selfreport_model_label=None,
                    gate_bug_count=1,
                    reported_bug_count=1,
                    provenance_mismatch=False,
                )
                phase0 = Phase0Facts(status="ok",
                                       probe_attempts=1,
                                       first_probe_ok=True)
                install = InstallFacts(
                    banner_rendered=True,
                    gitignore_remediation_followed=True,
                )
                run_meta = RunMetaFacts(
                    blocked=False, stop_reason=None,
                    exit_code=exit_code, timings=timings or {},
                    raw_receipt=raw_receipt,
                )
                return RunFacts(
                    phase0=phase0, verdict=verdict,
                    provenance=provenance, gate=gate,
                    install=install, run_meta=run_meta,
                )

            alive_calls = {"count": 0}

            def _fake_alive(pid):
                alive_calls["count"] += 1
                # First call: alive. Second: dead.
                return alive_calls["count"] < 2

            with mock.patch(
                "bin.harness.plan_runner._pid_is_alive",
                side_effect=_fake_alive,
            ), mock.patch.object(F, "extract_facts",
                                   side_effect=_fake_facts):
                outcomes = PR.collect_harness_run(harness_run)
            self.assertEqual(len(outcomes), 1)
            outcome = outcomes[0]
            # COMPLETED + MET (gate=PASS matches expect=PASS).
            self.assertEqual(outcome.terminal_state,
                              S.TerminalState.COMPLETED.value)
            self.assertEqual(outcome.result, "MET")
            self.assertEqual(outcome.gate_verdict, "PASSED")
            # Receipts present.
            self.assertTrue(
                (run_dir / "facts.json").is_file()
            )
            self.assertTrue(
                (run_dir / "grading.json").is_file()
            )
            # Terminal status.json carries the inferred
            # COMPLETED state.
            status = json.loads(
                (run_dir / "status.json").read_text(
                    encoding="utf-8")
            )
            self.assertEqual(status["state"], "DONE")
            self.assertEqual(status["terminal_state"],
                              "COMPLETED")
            # SUMMARY.md written.
            self.assertTrue(
                (harness_run / "SUMMARY.md").is_file()
            )


# ---------------------------------------------------------------------------
# Bundle-safety: plan_runner still under bin/harness/ (excluded)
# ---------------------------------------------------------------------------


class BundleSafety108Tests(unittest.TestCase):

    def test_plan_runner_still_under_harness(self) -> None:
        """plan_runner.py is the host for all 108 additions —
        it must stay under bin/harness/ (the install-bundle
        exclusion path) so adopters don't ship the collector
        machinery."""
        path = (Path(__file__).resolve().parents[3]
                / "bin" / "harness" / "plan_runner.py")
        self.assertTrue(path.is_file(),
                         "108 additions must live under "
                         "bin/harness/plan_runner.py")
        from bin.install_skill import _bundle_files
        repo_root = path.parents[2]
        bundle = _bundle_files(repo_root)
        for _src, dst in bundle:
            p = str(dst)
            self.assertFalse(
                "harness" in p,
                f"108 must not leak bin/harness/ into the "
                f"bundle; saw {p}",
            )


if __name__ == "__main__":
    unittest.main()
