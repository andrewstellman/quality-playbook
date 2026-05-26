"""v1.5.7 112 — classify AUP / API-error terminations as BLOCKED
→ N/A (don't grade a refusal as a real failure).

Surfaced on the first live gson run: Claude Code returned an
Anthropic Usage Policy refusal mid-Phase-2 — a ``result`` event
with ``subtype:"success"`` but ``is_error:true`` and body "API
Error: Claude Code is unable to respond to this request …
violate our Usage Policy …". The process exited 0, so the
pre-112 ``COMPLETED if exit_code == 0`` logic mis-marked it
COMPLETED, which then graded the partial ``quality/`` tree as
substantive failures.

112 detects ``is_error:true`` in the LAST ``result`` event of
``stream.ndjson`` and overrides terminal_state to BLOCKED
(regardless of exit code). Records the reason in status.json's
new ``terminal_reason`` field. BLOCKED naturally yields
``result=N/A`` in grading (the schema rule "grade only on
COMPLETED" is already in place; BLOCKED is one of the
non-COMPLETED states that short-circuit to N/A).

Coverage:
  * ``runner._stream_ended_in_api_error`` detects AUP refusals
    (``is_error:true`` in the last ``result`` event); returns
    ``(False, "")`` for a clean stream, no result event, or
    missing file.
  * Synchronous path (``runner.collect_one_process``):
    AUP-terminated stream + exit-0 ⇒ terminal_state=BLOCKED
    (NOT COMPLETED); status.json carries terminal_reason.
    **Mutation-bite**: revert to exit-code-only logic ⇒ the
    BLOCKED test FAILs (gets COMPLETED).
  * Detached collector path
    (``plan_runner._collect_one_run_detached``): AUP-terminated
    orphan stream ⇒ terminal_state=BLOCKED + the partial
    `quality/` tree is NOT graded against `expect`.
  * Normal clean ``result`` (``is_error:false``, exit 0) still
    ⇒ COMPLETED (no regression).
  * TIMED_OUT precedence preserved (max-duration kill wins
    over BLOCKED).
  * BLOCKED ⇒ N/A in grading (no substantive-fail
    counting; `result_label = N/A`).

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock as mock
from pathlib import Path

from bin.harness import plan_runner as PR
from bin.harness import runner as RUN
from bin.harness import schema as S


_AUP_REFUSAL_BODY = (
    "API Error: Claude Code is unable to respond to this "
    "request, which appears to violate our Usage Policy "
    "(see https://www.anthropic.com/aup). Request ID: "
    "req_abc123. (See the AUP page for details.)"
)


def _aup_stream_lines() -> "list[str]":
    """Build a stream.ndjson body that ends in an AUP refusal:
    a couple of normal events + a `result` event with
    `subtype:"success"` but `is_error:true` and the AUP body."""
    return [
        json.dumps({
            "type": "system", "subtype": "init",
            "session_id": "test-session",
        }),
        json.dumps({
            "type": "user", "content": "Run quality playbook…",
        }),
        json.dumps({
            "type": "assistant", "content": "Let me start...",
        }),
        json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": True,
            "result": _AUP_REFUSAL_BODY,
        }),
    ]


def _clean_stream_lines() -> "list[str]":
    """A clean run: result event has `is_error:false`."""
    return [
        json.dumps({
            "type": "system", "subtype": "init",
        }),
        json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "Done.",
        }),
    ]


# ---------------------------------------------------------------------------
# Task A — _stream_ended_in_api_error helper
# ---------------------------------------------------------------------------


class StreamEndedInApiErrorTests(unittest.TestCase):

    def test_aup_refusal_detected_via_is_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / "stream.ndjson"
            stream.write_text(
                "\n".join(_aup_stream_lines()) + "\n",
                encoding="utf-8",
            )
            blocked, reason = RUN._stream_ended_in_api_error(stream)
            self.assertTrue(blocked)
            # AUP body is recorded as the reason.
            self.assertIn("Usage Policy", reason)
            self.assertIn("API Error", reason)

    def test_clean_run_not_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / "stream.ndjson"
            stream.write_text(
                "\n".join(_clean_stream_lines()) + "\n",
                encoding="utf-8",
            )
            blocked, reason = RUN._stream_ended_in_api_error(stream)
            self.assertFalse(blocked)
            self.assertEqual(reason, "")

    def test_no_result_event_not_blocked(self) -> None:
        """A truncated stream with no `result` event ⇒ NOT
        blocked. Don't over-classify — a stream may be still
        live or may have been cut mid-flight."""
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / "stream.ndjson"
            stream.write_text(
                json.dumps({"type": "system", "subtype": "init"})
                + "\n",
                encoding="utf-8",
            )
            blocked, _reason = RUN._stream_ended_in_api_error(stream)
            self.assertFalse(blocked)

    def test_missing_file_not_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            blocked, _reason = RUN._stream_ended_in_api_error(
                Path(tmp) / "does-not-exist.ndjson"
            )
            self.assertFalse(blocked)

    def test_malformed_lines_ignored(self) -> None:
        """Garbage JSON lines are skipped; the helper returns
        based on whatever valid `result` event it finds last."""
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / "stream.ndjson"
            stream.write_text(
                "this is not json\n"
                + json.dumps({
                    "type": "result", "subtype": "success",
                    "is_error": True,
                    "result": _AUP_REFUSAL_BODY,
                }) + "\n"
                + "another non-json line\n",
                encoding="utf-8",
            )
            blocked, reason = RUN._stream_ended_in_api_error(stream)
            self.assertTrue(blocked)
            self.assertIn("Usage Policy", reason)

    def test_last_result_wins_when_multiple_present(self) -> None:
        """If a stream has multiple `result` events (shouldn't
        happen in practice, but be defensive), the LAST one
        determines the outcome."""
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp) / "stream.ndjson"
            stream.write_text(
                json.dumps({
                    "type": "result", "is_error": True,
                    "result": "Early aup",
                }) + "\n"
                + json.dumps({
                    "type": "result", "is_error": False,
                    "result": "Done.",
                }) + "\n",
                encoding="utf-8",
            )
            blocked, _reason = RUN._stream_ended_in_api_error(stream)
            self.assertFalse(
                blocked,
                "the LAST result event must determine the "
                "outcome — a recovered run that ended clean "
                "should not be misclassified as BLOCKED",
            )


# ---------------------------------------------------------------------------
# Task A — synchronous path (collect_one_process)
# ---------------------------------------------------------------------------


def _mk_synchronous_aup_run(parent: Path) -> "tuple[Path, Path]":
    """Spawn a quick no-op subprocess (exit-0) and write an
    AUP-shaped stream into its run_dir. Returns (run_dir,
    stream_path)."""
    run_dir = parent / "run"
    run_dir.mkdir()
    stream = run_dir / "stream.ndjson"
    stream.write_text(
        "\n".join(_aup_stream_lines()) + "\n",
        encoding="utf-8",
    )
    return run_dir, stream


class CollectOneProcessAupBlockedTests(unittest.TestCase):
    """The synchronous path uses ``collect_one_process`` to
    reap. AUP-terminated stream + exit-0 ⇒ BLOCKED, NOT
    COMPLETED. **Mutation-bite**: revert to the exit-code-only
    logic and this test FAILs."""

    def test_aup_terminated_run_yields_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            run_dir, stream = _mk_synchronous_aup_run(tmp_p)
            # Spawn a quick exit-0 subprocess to mimic the
            # AUP refusal's exit pattern (it exits 0).
            proc = subprocess.Popen(
                [sys.executable, "-c",
                  "import sys; sys.exit(0)"]
            )
            proc.wait(timeout=5)
            spawn = RUN.SpawnResult(
                pid=proc.pid,
                started_at="2026-05-26T19:00:00Z",
                cli_command="claude --print …",
                cwd=str(tmp_p),
                env_snapshot={"CLAUDECODE": "1"},
                stream_path=stream,
            )
            spec = RUN.LaunchSpec(
                target_dir=tmp_p, run_dir=run_dir,
                axes=S.RunAxes(
                    runner=S.Runner.CLAUDE, mode=S.Mode.A,
                    install_channel=S.InstallChannel.CLONE,
                    model="opus",
                ),
                case_id="c", run_id="r",
                max_duration_s=10.0,
                prompt="(test)",
            )
            result = RUN.collect_one_process(spec, spawn)
            # **THE 112 MUTATION-BITE**: pre-fix this returned
            # COMPLETED because exit_code == 0. Post-fix the
            # AUP stream overrides.
            self.assertEqual(
                result.terminal_state, S.TerminalState.BLOCKED,
                "112: AUP-terminated stream MUST yield BLOCKED "
                "(not COMPLETED); the exit-code-only pre-112 "
                "logic would mis-mark it COMPLETED and grade "
                "the partial tree.",
            )
            # status.json carries terminal_reason.
            status = json.loads(
                (run_dir / "status.json").read_text(
                    encoding="utf-8")
            )
            self.assertEqual(
                status["terminal_state"], "BLOCKED",
            )
            self.assertIn("Usage Policy",
                            status.get("terminal_reason", ""))

    def test_clean_run_still_completes(self) -> None:
        """Regression pin: a normal clean run (is_error:false,
        exit 0) still yields COMPLETED. 112 only overrides for
        AUP errors."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            run_dir = tmp_p / "run"
            run_dir.mkdir()
            stream = run_dir / "stream.ndjson"
            stream.write_text(
                "\n".join(_clean_stream_lines()) + "\n",
                encoding="utf-8",
            )
            proc = subprocess.Popen(
                [sys.executable, "-c", "import sys; sys.exit(0)"]
            )
            proc.wait(timeout=5)
            spawn = RUN.SpawnResult(
                pid=proc.pid,
                started_at="2026-05-26T19:00:00Z",
                cli_command="claude --print …",
                cwd=str(tmp_p),
                env_snapshot={},
                stream_path=stream,
            )
            spec = RUN.LaunchSpec(
                target_dir=tmp_p, run_dir=run_dir,
                axes=S.RunAxes(
                    runner=S.Runner.CLAUDE, mode=S.Mode.A,
                    install_channel=S.InstallChannel.CLONE,
                    model="opus",
                ),
                case_id="c", run_id="r",
                max_duration_s=10.0, prompt="(test)",
            )
            result = RUN.collect_one_process(spec, spawn)
            self.assertEqual(
                result.terminal_state,
                S.TerminalState.COMPLETED,
            )

    def test_timed_out_precedence_over_blocked(self) -> None:
        """If the run is killed by max-duration, terminal_state
        is TIMED_OUT regardless of stream content. The kill is
        the kill — even if the AI-CLI happened to write an AUP
        refusal before being killed."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            run_dir = tmp_p / "run"
            run_dir.mkdir()
            stream = run_dir / "stream.ndjson"
            # AUP-shaped stream PLUS a killed process.
            stream.write_text(
                "\n".join(_aup_stream_lines()) + "\n",
                encoding="utf-8",
            )
            # Spawn a long sleeper, set max_duration_s very low
            # so collect kills it.
            proc = subprocess.Popen(
                [sys.executable, "-c",
                  "import time; time.sleep(60)"]
            )
            spawn = RUN.SpawnResult(
                pid=proc.pid,
                started_at="2026-05-26T19:00:00Z",
                cli_command="claude …",
                cwd=str(tmp_p),
                env_snapshot={},
                stream_path=stream,
            )
            spec = RUN.LaunchSpec(
                target_dir=tmp_p, run_dir=run_dir,
                axes=S.RunAxes(
                    runner=S.Runner.CLAUDE, mode=S.Mode.A,
                    install_channel=S.InstallChannel.CLONE,
                    model="opus",
                ),
                case_id="c", run_id="r",
                max_duration_s=0.5,  # 500ms — will time out
                prompt="(test)",
            )
            try:
                result = RUN.collect_one_process(spec, spawn)
            except Exception:
                proc.kill()
                proc.wait(timeout=5)
                raise
            self.assertEqual(
                result.terminal_state,
                S.TerminalState.TIMED_OUT,
                "112: TIMED_OUT precedence — max-duration kill "
                "wins over BLOCKED even when the stream ended "
                "in an AUP refusal",
            )


# ---------------------------------------------------------------------------
# Task A — detached collector path (orphan-polling)
# ---------------------------------------------------------------------------


class CollectorOrphanPathAupBlockedTests(unittest.TestCase):
    """The 108 detached collector polls AI-CLI PIDs as orphans
    (can't waitpid) and infers terminal_state from artifacts.
    112 adds the AUP check on top of that inference — if the
    stream ended in an AUP refusal, the collector overrides to
    BLOCKED regardless of artifact presence."""

    def _build_manifest(
            self, harness_run: Path, *,
            run_dir: Path, target_dir: Path,
            stream_lines: "list[str]",
            include_gate_report: bool = False,
    ) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        target_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "stream.ndjson").write_text(
            "\n".join(stream_lines) + "\n",
            encoding="utf-8",
        )
        if include_gate_report:
            results_dir = target_dir / "quality" / "results"
            results_dir.mkdir(parents=True, exist_ok=True)
            (results_dir / "gate-report-latest.json").write_text(
                json.dumps({"verdict": "pass"}),
                encoding="utf-8",
            )
        manifest = {
            "harness_run_dir": str(harness_run),
            "plan": {"pools": {"claude": 1}},
            "runs": [{
                "index": 0,
                "description": "aup-blocked test",
                "repo": "https://github.com/x/y",
                "runner": "claude", "model": "opus",
                "channel": "clone", "mode": "A",
                "target_dir": str(target_dir),
                "run_dir": str(run_dir),
                "run_id": "r", "pid": 88888,
                "started_at": "2026-05-26T19:00:00Z",
                "stream_path": str(run_dir / "stream.ndjson"),
                "status_path": str(run_dir / "status.json"),
                "max_duration_s": 60.0,
                "expect": {"gate_result": "PASS"},
            }],
        }
        (harness_run / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )

    def test_aup_stream_yields_blocked_in_collector(
            self) -> None:
        """AUP-shaped stream + dead PID + a `gate-report-
        latest.json` that WOULD have made the inference say
        COMPLETED ⇒ 112 override forces BLOCKED + the partial
        tree is NOT graded against expect (result=N/A, not
        substantive failure)."""
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp)
            run_dir = harness_run / "run-00"
            target_dir = run_dir / "target"
            self._build_manifest(
                harness_run,
                run_dir=run_dir, target_dir=target_dir,
                stream_lines=_aup_stream_lines(),
                include_gate_report=True,  # would normally ⇒ COMPLETED
            )
            # Drive polling: PID dead immediately.
            with mock.patch(
                "bin.harness.plan_runner._pid_is_alive",
                return_value=False,
            ):
                outcomes = PR.collect_harness_run(harness_run)
            outcome = outcomes[0]
            # **THE 112 LOAD-BEARING ASSERTION**: BLOCKED, not
            # COMPLETED. The pre-fix collector would have used
            # the gate-report-latest.json signal and marked
            # COMPLETED + graded the partial tree.
            self.assertEqual(
                outcome.terminal_state,
                S.TerminalState.BLOCKED.value,
                "112 collector path: AUP-shaped stream MUST "
                "override gate-report-latest.json artifact "
                "inference; BLOCKED, not COMPLETED",
            )
            self.assertEqual(outcome.result, "N/A")
            # No facts.json + no grading.json from a real
            # extract_facts run — the collector short-
            # circuits at the non-COMPLETED branch. The
            # grading.json sentinel IS written by the
            # collector to mark "this run is done; don't
            # re-poll on the next sweep".
            grading_path = run_dir / "grading.json"
            self.assertTrue(grading_path.is_file())
            grading = json.loads(
                grading_path.read_text(encoding="utf-8")
            )
            self.assertEqual(grading["verdict"], "N/A")
            self.assertEqual(
                grading.get("terminal_state"), "BLOCKED",
            )
            # status.json carries terminal_reason.
            status = json.loads(
                (run_dir / "status.json").read_text(
                    encoding="utf-8")
            )
            self.assertEqual(status["terminal_state"],
                              "BLOCKED")
            self.assertIn("Usage Policy",
                            status.get("terminal_reason", ""))

    def test_clean_stream_still_completes_in_collector(
            self) -> None:
        """Regression pin for the orphan collector: a clean
        stream + gate-report-latest.json ⇒ COMPLETED (the 108
        artifact-inference behavior is preserved when the
        stream isn't AUP-terminated)."""
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp)
            run_dir = harness_run / "run-00"
            target_dir = run_dir / "target"
            self._build_manifest(
                harness_run,
                run_dir=run_dir, target_dir=target_dir,
                stream_lines=_clean_stream_lines(),
                include_gate_report=True,
            )
            # Patch facts.extract_facts to skip the real gate
            # re-run (we only care about terminal_state here).
            from bin.harness import facts as F
            from bin.harness.schema import (
                GateFacts, GateResult, VerdictFacts,
                VerdictState, Attribution, RunMetaFacts,
                Phase0Facts, ProvenanceFacts,
                InstallSurfaceFacts, RunFacts,
            )

            def _fake_facts(target_dir, axes, transcript,
                              exit_code, raw_receipt,
                              timings=None, gate_stdout=None):
                return RunFacts(
                    phase0=Phase0Facts(status="ok",
                                          probe_attempts=1,
                                          first_probe_ok=True),
                    verdict=VerdictFacts(
                        verdict_state=VerdictState.SOLID,
                        attribution=Attribution.NONE,
                        recommends_stronger_model=False,
                        bugs_unverified_present=False,
                    ),
                    provenance=ProvenanceFacts(
                        detected_runner="claude-code",
                        selfreport_model_label=None,
                        gate_bug_count=0,
                        reported_bug_count=0,
                        provenance_mismatch=False,
                    ),
                    gate=GateFacts(
                        gate_total="Total: 0 FAIL, 0 WARN",
                        gate_result=GateResult.PASS,
                        cleanup_gaps=0,
                        substantive_fail_count=0,
                        record_keeping_fail_count=0,
                    ),
                    install=InstallSurfaceFacts(
                        banner_rendered=True,
                        gitignore_remediation_followed=True,
                    ),
                    run_meta=RunMetaFacts(
                        blocked=False, stop_reason=None,
                        exit_code=exit_code,
                        timings=timings or {},
                        raw_receipt=raw_receipt,
                    ),
                )

            with mock.patch(
                "bin.harness.plan_runner._pid_is_alive",
                return_value=False,
            ), mock.patch.object(F, "extract_facts",
                                   side_effect=_fake_facts):
                outcomes = PR.collect_harness_run(harness_run)
            self.assertEqual(
                outcomes[0].terminal_state,
                S.TerminalState.COMPLETED.value,
            )
            self.assertEqual(outcomes[0].result, "MET")


# ---------------------------------------------------------------------------
# Task B — BLOCKED ⇒ N/A in grading (no substantive-fail counting)
# ---------------------------------------------------------------------------


class BlockedShortCircuitsGradingTests(unittest.TestCase):
    """The schema rule "grade only on COMPLETED" was already
    in place pre-112 (the synchronous + detached paths both
    have ``if terminal == COMPLETED:`` branches that gate the
    grade step). 112 just adds BLOCKED to the set of terminal
    states that hit the non-COMPLETED branch.

    This test pins that contract by directly invoking the
    grade path with terminal=BLOCKED + asserting the run
    grades N/A (not MET, not NOT-MET, not a substantive
    failure)."""

    def test_blocked_terminal_yields_na_in_synchronous_path(
            self) -> None:
        """Use a fake_run hook that returns terminal=BLOCKED;
        confirm the synchronous _execute_one_run path returns
        result=N/A without trying to grade."""
        plan = PR.parse_plan({
            "pools": {"claude": 1},
            "runs": [{
                "description": "blocked",
                "repo": "x", "ref": "main",
                "runner": "claude", "model": "opus",
                "channel": "clone",
                "expect": {"gate_result": "PASS"},
            }],
        })

        def _fake(pr, run_dir):
            return {
                "terminal_state":
                    S.TerminalState.BLOCKED.value,
                "facts": None,
                "transcript": "",
                "axes": S.RunAxes(
                    runner=pr.runner, mode=pr.mode,
                    install_channel=pr.channel,
                    model=pr.model,
                ),
            }

        with tempfile.TemporaryDirectory() as tmp:
            outcomes = PR.run_plan(
                plan, Path(tmp),
                hooks=PR.PlanRunnerHooks(fake_run=_fake),
            )
            self.assertEqual(len(outcomes), 1)
            self.assertEqual(
                outcomes[0].terminal_state,
                S.TerminalState.BLOCKED.value,
            )
            self.assertEqual(outcomes[0].result, "N/A")
            self.assertEqual(outcomes[0].gate_verdict, "N/A")


# ---------------------------------------------------------------------------
# Bundle-safety: 112 lives under bin/harness/ (excluded)
# ---------------------------------------------------------------------------


class BundleSafety112Tests(unittest.TestCase):

    def test_runner_still_under_harness(self) -> None:
        from bin.install_skill import _bundle_files
        repo_root = (
            Path(__file__).resolve().parents[3]
        )
        bundle = _bundle_files(repo_root)
        for _src, dst in bundle:
            p = str(dst)
            self.assertFalse(
                "harness" in p,
                f"112 must not leak bin/harness/ into the "
                f"bundle; saw {p}",
            )


if __name__ == "__main__":
    unittest.main()
