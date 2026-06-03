"""v1.5.7 120 — a clean terminal `result` event MUST classify
COMPLETED even when the AI-CLI hung at exit and got killed at
max_duration; collector reaps proactively on the terminal
result event.

Found on the AUP-experiment: BOTH Mode A gson runs finished the
full pipeline cleanly — ``RESULT: GATE PASSED``, terminal
``result`` event with ``is_error:false`` — but were recorded
``TIMED_OUT → N/A``. They started 14:59:03 and were killed at
exactly 16:59:07 = 7200s (max_duration). The work completed
well before that; the ``claude --print`` process **hung at
exit** (known issue) and lingered until max-duration.

Root cause: 112/113 made TIMED_OUT take PRECEDENCE over the
stream classifier — so a clean run that hung at exit was
mis-graded N/A. 120 inverts the precedence: a terminal result
event (COMPLETED/BLOCKED) wins over the max-duration kill,
because the kill is just reaping the hung-at-exit process —
it didn't interrupt work that the stream already declared
done.

120 also adds **proactive reap**: the collector poll-loops
check the stream for a terminal result event on each
iteration; when present, they kill any lingering process AND
classify from the stream — instead of burning the full
max_duration on the exit-hang (here, ~75 wasted minutes per
run pre-120).

Coverage:
  * **THE 120 LOAD-BEARING TEST**: a stream ending in a clean
    `result` event (`is_error:false`) + a live process at
    max_duration ⇒ classified COMPLETED (NOT TIMED_OUT).
    Mutation-bite: restore the 112/113 TIMED_OUT-wins
    precedence ⇒ this test FAILS with TIMED_OUT.
  * Proactive reap: a stream with a terminal result event +
    a healthy (long-sleeping) process ⇒ the collector reaps
    + classifies WITHOUT waiting for max_duration. The
    elapsed wall time is bounded; pre-120 it would wait the
    full deadline.
  * Genuine timeout preserved: a process killed at
    max_duration with NO result event ⇒ TIMED_OUT.
  * BLOCKED preserved: AUP-shaped stream + max-duration kill
    ⇒ BLOCKED (NOT TIMED_OUT — same 120 precedence applies).
  * Mode B unchanged: no result event ⇒ artifact heuristic
    + TIMED_OUT (no regression).

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


# ---------------------------------------------------------------------------
# Stream fixtures (mirror the 112/113 forms)
# ---------------------------------------------------------------------------


def _clean_result_stream() -> "list[str]":
    """A clean Claude --print stream: assistant messages plus a
    terminal `result` event with `is_error:false`."""
    return [
        json.dumps({"type": "system", "subtype": "init"}),
        json.dumps({"type": "assistant",
                     "content": "All phases done."}),
        json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": False,
            "result": "RESULT: GATE PASSED",
        }),
    ]


def _aup_result_stream() -> "list[str]":
    """The 112 AUP refusal shape: `is_error:true`."""
    return [
        json.dumps({"type": "system", "subtype": "init"}),
        json.dumps({
            "type": "result",
            "subtype": "success",
            "is_error": True,
            "result": "API Error: violates Usage Policy …",
        }),
    ]


# ---------------------------------------------------------------------------
# Task A — synchronous path (collect_one_process): clean result wins
# ---------------------------------------------------------------------------


class SyncCollectorCleanResultWinsOverTimeoutTests(
        unittest.TestCase):
    """**THE 120 LOAD-BEARING TEST** for the synchronous path
    (``collect_one_process``). The AUP-experiment's
    Mode A gson runs hit this exact case: clean result event
    + claude --print exit-hang + max-duration kill ⇒ pre-120
    recorded TIMED_OUT despite the clean completion."""

    def test_clean_result_wins_when_killed_at_max_duration(
            self) -> None:
        """**THE 120 MUTATION-BITE**: a stream ending in
        ``is_error:false`` + a long-sleeping process (the
        exit-hang simulant) ⇒ COMPLETED. Restore the pre-120
        TIMED_OUT-wins precedence and this test FAILS with
        TIMED_OUT — the exact AUP-experiment misclassification."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            run_dir = tmp_p / "run"
            run_dir.mkdir()
            stream = run_dir / "stream.ndjson"
            stream.write_text(
                "\n".join(_clean_result_stream()) + "\n",
                encoding="utf-8",
            )
            # Simulate the claude --print exit-hang: the
            # process is still alive when collect starts.
            # start_new_session=True so the subprocess is its
            # own process-group leader — `_kill_process_tree`'s
            # `os.killpg(pid, SIGTERM)` only works on groups
            # whose ID equals the subprocess pid. Without this
            # the kill is a no-op and the collector blocks on
            # waitpid until the subprocess sleep ends.
            proc = subprocess.Popen(
                [sys.executable, "-c",
                  "import time; time.sleep(60)"],
                start_new_session=True,
            )
            spawn = RUN.SpawnResult(
                pid=proc.pid,
                started_at="2026-05-27T15:00:00Z",
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
                max_duration_s=0.3,
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
                S.TerminalState.COMPLETED,
                "120: a terminal `result` event with "
                "`is_error:false` MUST classify COMPLETED, "
                "even when the process needed killing at "
                "max_duration (the kill was just reaping the "
                "exit-hang). Pre-120 (112/113) this recorded "
                "TIMED_OUT → N/A for GATE-PASSED runs — the "
                "AUP-experiment Mode A gson misclassification.",
            )
            # And status.json reflects the same.
            status = json.loads(
                (run_dir / "status.json").read_text(
                    encoding="utf-8"))
            self.assertEqual(status["terminal_state"], "COMPLETED")

    def test_genuine_timeout_preserved(self) -> None:
        """120 only inverts precedence WHEN there's a terminal
        result event. A process killed at max_duration with
        NO result event in the stream (genuinely cut off
        mid-work) still records TIMED_OUT."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            run_dir = tmp_p / "run"
            run_dir.mkdir()
            stream = run_dir / "stream.ndjson"
            # No `result` event — just an intermediate event.
            stream.write_text(
                json.dumps({"type": "system",
                              "subtype": "init"}) + "\n"
                + json.dumps({"type": "assistant",
                                "content": "working..."})
                + "\n",
                encoding="utf-8",
            )
            # start_new_session=True so the subprocess is its
            # own process-group leader — `_kill_process_tree`'s
            # `os.killpg(pid, SIGTERM)` only works on groups
            # whose ID equals the subprocess pid. Without this
            # the kill is a no-op and the collector blocks on
            # waitpid until the subprocess sleep ends.
            proc = subprocess.Popen(
                [sys.executable, "-c",
                  "import time; time.sleep(60)"],
                start_new_session=True,
            )
            spawn = RUN.SpawnResult(
                pid=proc.pid,
                started_at="2026-05-27T15:00:00Z",
                cli_command="claude …",
                cwd=str(tmp_p), env_snapshot={},
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
                max_duration_s=0.3, prompt="(test)",
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
                "120: a genuine timeout (no result event) is "
                "still TIMED_OUT — only a terminal `result` "
                "event overrides the deadline kill.",
            )

    def test_proactive_reap_on_result_event(self) -> None:
        """**Task B**: the collector reaps PROACTIVELY when a
        terminal result event is present — instead of waiting
        the full max_duration on the exit-hang. Verify the
        collector exits well before max_duration when a
        clean result event is in the stream from the start."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            run_dir = tmp_p / "run"
            run_dir.mkdir()
            stream = run_dir / "stream.ndjson"
            stream.write_text(
                "\n".join(_clean_result_stream()) + "\n",
                encoding="utf-8",
            )
            # Long-sleeping process (the exit-hang).
            # start_new_session=True so the subprocess is its
            # own process-group leader — `_kill_process_tree`'s
            # `os.killpg(pid, SIGTERM)` only works on groups
            # whose ID equals the subprocess pid. Without this
            # the kill is a no-op and the collector blocks on
            # waitpid until the subprocess sleep ends.
            proc = subprocess.Popen(
                [sys.executable, "-c",
                  "import time; time.sleep(60)"],
                start_new_session=True,
            )
            spawn = RUN.SpawnResult(
                pid=proc.pid,
                started_at="2026-05-27T15:00:00Z",
                cli_command="claude …",
                cwd=str(tmp_p), env_snapshot={},
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
                max_duration_s=30.0,  # would take 30s pre-120
                prompt="(test)",
            )
            t0 = time.monotonic()
            try:
                result = RUN.collect_one_process(spec, spawn)
            except Exception:
                proc.kill()
                proc.wait(timeout=5)
                raise
            elapsed = time.monotonic() - t0
            # Proactive reap: exits in <1s (single poll
            # iteration sees the result event + kills);
            # pre-120 it would wait the full 30s deadline.
            self.assertLess(
                elapsed, 5.0,
                f"120 proactive reap: collector must exit "
                f"quickly when stream has a terminal result "
                f"event; took {elapsed:.2f}s of 30s deadline.",
            )
            self.assertEqual(
                result.terminal_state,
                S.TerminalState.COMPLETED)


# ---------------------------------------------------------------------------
# Task A — detached collector path (orphan): clean result wins
# ---------------------------------------------------------------------------


def _build_orphan_manifest(harness_run: Path, *,
                            run_dir: Path, target_dir: Path,
                            stream_lines: "list[str]",
                            max_duration_s: float = 60.0
                            ) -> None:
    """Set up a minimal harness-run manifest for the orphan
    collector (118 relative-path form)."""
    run_dir.mkdir(parents=True, exist_ok=True)
    target_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "stream.ndjson").write_text(
        "\n".join(stream_lines) + "\n", encoding="utf-8")
    manifest = {
        "harness_run_dir": str(harness_run),
        "plan": {"pools": {"claude": 1}},
        "runs": [{
            "index": 0, "description": "120 test",
            "repo": "https://github.com/x/y",
            "runner": "claude", "model": "opus",
            "channel": "clone", "mode": "A",
            "target_dir": "run-00/target",
            "run_dir": "run-00",
            "run_id": "r", "pid": 88888,
            "started_at": "2026-05-27T15:00:00Z",
            "stream_path": "run-00/stream.ndjson",
            "status_path": "run-00/status.json",
            "max_duration_s": max_duration_s,
            "expect": {},
        }],
    }
    (harness_run / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


class OrphanCollectorCleanResultWinsTests(unittest.TestCase):
    """**Same 120 contract for the detached collector**
    (``_collect_one_run_detached``) — the AUP-experiment's
    failing runs went through this path (run_plan launches
    detached + the orphan-polling collector reaps)."""

    def test_clean_result_wins_when_killed_at_deadline(
            self) -> None:
        """The orphan collector mirror of the synchronous test
        — same precedence: clean result event + live PID +
        deadline = 0 ⇒ COMPLETED, not TIMED_OUT."""
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp)
            run_dir = harness_run / "run-00"
            target_dir = run_dir / "target"
            _build_orphan_manifest(
                harness_run,
                run_dir=run_dir, target_dir=target_dir,
                stream_lines=_clean_result_stream(),
                max_duration_s=0.0,
            )
            # PID stays alive (the exit-hang); deadline=0
            # ⇒ deadline branch fires on the first poll.
            with mock.patch(
                "bin.harness.plan_runner._pid_is_alive",
                return_value=True,
            ), mock.patch(
                "bin.harness.runner._kill_process_tree",
                return_value=None,
            ):
                outcomes = PR.collect_harness_run(harness_run)
            self.assertEqual(
                outcomes[0].terminal_state,
                S.TerminalState.COMPLETED.value,
                "120 orphan path: clean result event MUST win "
                "over the max-duration kill (the AUP-"
                "experiment's exact mis-graded shape).",
            )
            # Status.json + grading.json reflect COMPLETED.
            status = json.loads(
                (run_dir / "status.json").read_text(
                    encoding="utf-8"))
            self.assertEqual(
                status["terminal_state"], "COMPLETED")

    def test_proactive_reap_in_orphan_path(self) -> None:
        """Same proactive-reap test for the orphan collector
        — exits quickly when the stream has a terminal
        result event, instead of waiting the deadline."""
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp)
            run_dir = harness_run / "run-00"
            target_dir = run_dir / "target"
            _build_orphan_manifest(
                harness_run,
                run_dir=run_dir, target_dir=target_dir,
                stream_lines=_clean_result_stream(),
                max_duration_s=10.0,
            )
            t0 = time.monotonic()
            with mock.patch(
                "bin.harness.plan_runner._pid_is_alive",
                return_value=True,
            ), mock.patch(
                "bin.harness.runner._kill_process_tree",
                return_value=None,
            ):
                outcomes = PR.collect_harness_run(harness_run)
            elapsed = time.monotonic() - t0
            # Proactive reap: the result event is present
            # from the start, so the first poll iteration
            # detects it + kills + classifies. Pre-120
            # this would have waited the full 10s deadline.
            self.assertLess(
                elapsed, 3.0,
                f"120 orphan proactive reap: collector must "
                f"exit quickly when stream has terminal "
                f"result; took {elapsed:.2f}s of 10s deadline.",
            )
            self.assertEqual(
                outcomes[0].terminal_state,
                S.TerminalState.COMPLETED.value,
            )

    def test_aup_refusal_still_classifies_blocked(self) -> None:
        """112's BLOCKED behavior preserved by 120 — an AUP
        refusal stream still classifies BLOCKED (with the
        result event winning over the deadline kill)."""
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp)
            run_dir = harness_run / "run-00"
            target_dir = run_dir / "target"
            _build_orphan_manifest(
                harness_run,
                run_dir=run_dir, target_dir=target_dir,
                stream_lines=_aup_result_stream(),
                max_duration_s=0.0,
            )
            with mock.patch(
                "bin.harness.plan_runner._pid_is_alive",
                return_value=True,
            ), mock.patch(
                "bin.harness.runner._kill_process_tree",
                return_value=None,
            ):
                outcomes = PR.collect_harness_run(harness_run)
            self.assertEqual(
                outcomes[0].terminal_state,
                S.TerminalState.BLOCKED.value)

    def test_mode_b_no_result_event_unchanged(self) -> None:
        """**Mode B regression pin**: a stream with NO Claude
        `result` event (run_playbook's output shape) + dead
        PID ⇒ artifact heuristic (no change from 113); no
        gate-report-latest.json ⇒ FAILED. 120 doesn't
        regress Mode B because the proactive-reap branch
        only fires when the stream classifier returns a
        non-None state."""
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = Path(tmp)
            run_dir = harness_run / "run-00"
            target_dir = run_dir / "target"
            target_dir.mkdir(parents=True)
            _build_orphan_manifest(
                harness_run,
                run_dir=run_dir, target_dir=target_dir,
                stream_lines=[
                    "10:59:05   Phase 1/6 (Explore): target",
                    "11:30:00   Phase 2/6 (Generate): target",
                ],
            )
            # PID dies normally (no exit-hang).
            with mock.patch(
                "bin.harness.plan_runner._pid_is_alive",
                return_value=False,
            ):
                outcomes = PR.collect_harness_run(harness_run)
            # Mode B → no result event → artifact heuristic
            # → no gate-report → FAILED.
            self.assertEqual(
                outcomes[0].terminal_state,
                S.TerminalState.FAILED.value)


# ---------------------------------------------------------------------------
# Bundle-safety
# ---------------------------------------------------------------------------


class BundleSafety120Tests(unittest.TestCase):

    def test_changes_stay_under_harness(self) -> None:
        from bin.install_skill import _bundle_files
        repo_root = Path(__file__).resolve().parents[3]
        bundle = _bundle_files(repo_root)
        for _src, dst in bundle:
            p = str(dst)
            self.assertFalse(
                "harness" in p,
                f"120 must not leak bin/harness/ into the "
                f"bundle; saw {p}",
            )


if __name__ == "__main__":
    unittest.main()
