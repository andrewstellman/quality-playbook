"""v1.5.7 110 — CLI status commands (status / status <run> /
tail) over the 108 manifest + 109 phase sentinel.

The data layer the 111 TUI sits on, and what Cowork + an
operator use to check in-flight runs without a blocking
parent.

Coverage (Task C):
  * ``read_run_status`` over a fixture harness-run (hand-built
    manifest + status.json + a stream with a
    ``::QPB:: kind:"phase"`` line) returns the right per-run
    state, result, and parsed **current phase**; a stream with
    NO sentinel degrades to "—" (graceful).
  * ``list_harness_runs`` orders newest-first and counts
    states correctly across a couple of fixture run dirs.
  * PID-liveness uses ``os.kill(pid, 0)`` semantics (patchable);
    a dead pid ⇒ ``pid_alive=False``.
  * ``tail_stream`` renders ``kind:"phase"`` / ``kind:"gate"``
    sentinels human-readably and passes through plain lines.
  * CLI smoke: ``status`` / ``status <dir>`` / ``tail`` exit 0
    over the fixtures; no-args self-describes.

Segregated suite per Implementation Plan §4.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock as mock
from pathlib import Path

from bin.harness import status as ST


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------


def _build_harness_run(
        parent: Path, *, name: str = "20260526T180000Z",
        runs: "list[dict]",
        manifest_extra: "dict | None" = None,
        collector_log_age_s: "float | None" = None,
) -> Path:
    """Build a fixture harness-run directory with the given
    runs. Each ``runs[i]`` dict carries:
      * ``index``, ``description``, ``repo``, ``runner``,
        ``model``, ``channel`` (manifest-entry fields)
      * ``status`` (optional): the ``status.json`` payload to
        write into run-NN/status.json
      * ``grading`` (optional): the ``grading.json`` payload
      * ``stream_lines`` (optional): list of lines to write
        into run-NN/stream.ndjson
      * ``terminal_state`` (optional): set on the manifest
        entry directly (for the ABORTED_PREP-at-launch case).

    Returns the harness_run_dir.
    """
    harness_run = parent / name
    harness_run.mkdir()
    entries = []
    for run in runs:
        idx = run["index"]
        run_dir = harness_run / f"run-{idx:02d}"
        run_dir.mkdir()
        entry = {
            "index": idx,
            "description": run.get("description", f"r{idx}"),
            "repo": run.get("repo",
                              f"https://example.com/r{idx}"),
            "runner": run.get("runner", "claude"),
            "model": run.get("model", "opus"),
            "channel": run.get("channel", "clone"),
            "mode": run.get("mode", "A"),
            "target_dir": str(run_dir / "target"),
            "run_dir": str(run_dir),
            "stream_path": str(run_dir / "stream.ndjson"),
            "status_path": str(run_dir / "status.json"),
            "pid": run.get("pid"),
            "started_at": run.get("started_at",
                                     "2026-05-26T18:00:00Z"),
            "max_duration_s": run.get("max_duration_s", 7200.0),
            "expect": run.get("expect", {}),
        }
        if "terminal_state" in run:
            entry["terminal_state"] = run["terminal_state"]
        entries.append(entry)
        # status.json
        if "status" in run:
            (run_dir / "status.json").write_text(
                json.dumps(run["status"]) + "\n",
                encoding="utf-8",
            )
        # grading.json
        if "grading" in run:
            (run_dir / "grading.json").write_text(
                json.dumps(run["grading"]) + "\n",
                encoding="utf-8",
            )
        # stream.ndjson
        if "stream_lines" in run:
            (run_dir / "stream.ndjson").write_text(
                "\n".join(run["stream_lines"]) + "\n",
                encoding="utf-8",
            )
    manifest = {
        "harness_run_dir": str(harness_run),
        "plan": {"pools": {"claude": 1}},
        "runs": entries,
    }
    if manifest_extra:
        manifest.update(manifest_extra)
    (harness_run / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    if collector_log_age_s is not None:
        log = harness_run / "collector.log"
        log.write_text("collector log\n", encoding="utf-8")
        target_mtime = time.time() - collector_log_age_s
        import os
        os.utime(log, (target_mtime, target_mtime))
    return harness_run


def _phase_sentinel(*, phase: int, name: str, state: str,
                     ts: str = "2026-05-26T18:30:00Z",
                     note: "str | None" = None) -> str:
    """Build a `::QPB:: {kind:"phase"}` line matching the 109
    emit format (compact JSON; no spaces inside the object)."""
    payload = {
        "v": 1, "kind": "phase", "phase": phase,
        "name": name, "state": state, "ts": ts,
    }
    if note is not None:
        payload["note"] = note
    return f"::QPB:: {json.dumps(payload, separators=(',', ':'))}"


def _gate_sentinel(*, gate_result: str, verdict_state: str,
                    ts: str = "2026-05-26T18:35:00Z") -> str:
    payload = {
        "v": 1, "kind": "gate",
        "gate_result": gate_result,
        "verdict_state": verdict_state,
        "ts": ts,
    }
    return f"::QPB:: {json.dumps(payload, separators=(',', ':'))}"


# ---------------------------------------------------------------------------
# Task C — read_run_status: fixtures + current-phase parsing
# ---------------------------------------------------------------------------


class ReadRunStatusTests(unittest.TestCase):

    def test_read_running_run_with_phase_sentinel(self) -> None:
        """A run with status=RUNNING + a `::QPB:: phase:3
        start` in its stream ⇒ state=RUNNING, current_phase=P3
        (code-review), no grading.json ⇒ result=(running)."""
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = _build_harness_run(
                Path(tmp), runs=[{
                    "index": 0,
                    "description": "x",
                    "pid": 12345,
                    "status": {
                        "state": "RUNNING", "pid": 12345,
                        "started_at": "2026-05-26T18:00:00Z",
                        "heartbeat": "2026-05-26T18:30:00Z",
                        "exit_code": None,
                        "terminal_state": None,
                    },
                    "stream_lines": [
                        '{"event": "phase1_complete"}',
                        _phase_sentinel(
                            phase=3, name="code-review",
                            state="start",
                            note="Reviewed dup-key.",
                        ),
                    ],
                }],
            )
            with mock.patch(
                "bin.harness.status.pid_is_alive",
                return_value=True,
            ):
                runs = ST.read_run_status(harness_run)
            self.assertEqual(len(runs), 1)
            rs = runs[0]
            self.assertEqual(rs.state, "RUNNING")
            self.assertEqual(rs.result, "(running)")
            self.assertEqual(rs.current_phase, "P3")
            self.assertEqual(rs.current_phase_name,
                              "code-review")
            self.assertEqual(rs.current_phase_state, "start")
            self.assertEqual(rs.last_note, "Reviewed dup-key.")
            self.assertEqual(rs.pid, 12345)
            self.assertTrue(rs.pid_alive)

    def test_read_completed_run_with_grading(self) -> None:
        """Status terminal=COMPLETED + grading.json present ⇒
        state=COMPLETED, result from grading.verdict."""
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = _build_harness_run(
                Path(tmp), runs=[{
                    "index": 0,
                    "description": "completed run",
                    "pid": 99999,
                    "status": {
                        "state": "DONE", "pid": 99999,
                        "started_at": "2026-05-26T18:00:00Z",
                        "heartbeat": "2026-05-26T18:35:00Z",
                        "ended_at": "2026-05-26T18:35:00Z",
                        "exit_code": 0,
                        "terminal_state": "COMPLETED",
                    },
                    "grading": {
                        "verdict": "MET",
                        "n_passed": 3, "n_failed": 0,
                        "n_total": 3, "assertions": [],
                    },
                    "stream_lines": [
                        _phase_sentinel(
                            phase=6, name="verification",
                            state="done",
                        ),
                        _gate_sentinel(gate_result="PASS",
                                         verdict_state="solid"),
                    ],
                }],
            )
            with mock.patch(
                "bin.harness.status.pid_is_alive",
                return_value=False,
            ):
                runs = ST.read_run_status(harness_run)
            self.assertEqual(runs[0].state, "COMPLETED")
            self.assertEqual(runs[0].result, "MET")
            self.assertEqual(runs[0].current_phase, "P6")
            self.assertEqual(runs[0].current_phase_name,
                              "verification")
            self.assertEqual(runs[0].current_phase_state, "done")

    def test_stream_with_no_sentinel_degrades_to_dash(
            self) -> None:
        """A stream with NO `::QPB::` sentinel line ⇒
        current_phase = "—" (graceful)."""
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = _build_harness_run(
                Path(tmp), runs=[{
                    "index": 0, "description": "no-sentinel",
                    "pid": 11111,
                    "status": {
                        "state": "RUNNING", "pid": 11111,
                        "started_at": "2026-05-26T18:00:00Z",
                        "heartbeat": "2026-05-26T18:30:00Z",
                        "exit_code": None,
                        "terminal_state": None,
                    },
                    "stream_lines": [
                        '{"event": "stuff"}',
                        '{"event": "more stuff"}',
                    ],
                }],
            )
            runs = ST.read_run_status(harness_run)
            self.assertEqual(runs[0].current_phase, "—")
            self.assertEqual(runs[0].current_phase_name, "—")
            self.assertEqual(runs[0].current_phase_state, "—")
            self.assertEqual(runs[0].last_note, "")

    def test_aborted_prep_from_manifest_entry(self) -> None:
        """ABORTED_PREP runs (prep failed at launch) carry the
        terminal_state on the manifest entry directly; no
        status.json. Read still produces a coherent RunStatus."""
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = _build_harness_run(
                Path(tmp), runs=[{
                    "index": 0,
                    "description": "prep-failed",
                    "pid": None,
                    "terminal_state": "ABORTED_PREP",
                }],
            )
            runs = ST.read_run_status(harness_run)
            self.assertEqual(runs[0].state, "ABORTED_PREP")
            self.assertEqual(runs[0].current_phase, "—")
            self.assertFalse(runs[0].pid_alive)

    def test_missing_manifest_returns_empty_list(self) -> None:
        """Read returns [] when the manifest is missing —
        graceful for a mid-launch harness-run."""
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "no-manifest"
            empty.mkdir()
            self.assertEqual(ST.read_run_status(empty), [])

    def test_partial_status_json_does_not_raise(self) -> None:
        """A status.json that's malformed (collector died
        mid-write) ⇒ read returns a coherent RunStatus
        (falling back to manifest entry); never raises."""
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = _build_harness_run(
                Path(tmp), runs=[{
                    "index": 0, "description": "x",
                    "pid": 12345,
                }],
            )
            (harness_run / "run-00" / "status.json").write_text(
                "{this is not valid json",
                encoding="utf-8",
            )
            runs = ST.read_run_status(harness_run)
            self.assertEqual(len(runs), 1)
            # Falls back to PENDING (no terminal_state from
            # manifest, no valid status.json).
            self.assertEqual(runs[0].state, "PENDING")


# ---------------------------------------------------------------------------
# Task C — list_harness_runs: newest-first ordering + state counts
# ---------------------------------------------------------------------------


class ListHarnessRunsTests(unittest.TestCase):

    def test_orders_newest_first(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            # Build two harness-runs with different mtimes.
            older = _build_harness_run(
                tmp_p, name="20260526T100000Z", runs=[
                    {"index": 0, "description": "x",
                      "pid": 1},
                ],
            )
            newer = _build_harness_run(
                tmp_p, name="20260526T200000Z", runs=[
                    {"index": 0, "description": "y",
                      "pid": 2},
                ],
            )
            import os
            # Force older mtime to be older.
            os.utime(older, (time.time() - 1000,
                              time.time() - 1000))
            os.utime(newer, (time.time(), time.time()))
            summaries = ST.list_harness_runs(tmp_p)
            self.assertEqual(len(summaries), 2)
            self.assertEqual(
                summaries[0].harness_run_dir.name,
                "20260526T200000Z",
                "newest-first ordering",
            )

    def test_counts_states_correctly(self) -> None:
        """Build a harness-run with one of each terminal state
        + one RUNNING + one PENDING (no status.json)."""
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = _build_harness_run(
                Path(tmp), runs=[
                    # COMPLETED
                    {"index": 0, "pid": 1, "status": {
                        "state": "DONE", "pid": 1,
                        "started_at": "x", "heartbeat": "y",
                        "ended_at": "z", "exit_code": 0,
                        "terminal_state": "COMPLETED",
                    }},
                    # FAILED
                    {"index": 1, "pid": 2, "status": {
                        "state": "DONE", "pid": 2,
                        "started_at": "x", "heartbeat": "y",
                        "ended_at": "z", "exit_code": 1,
                        "terminal_state": "FAILED",
                    }},
                    # TIMED_OUT
                    {"index": 2, "pid": 3, "status": {
                        "state": "DONE", "pid": 3,
                        "started_at": "x", "heartbeat": "y",
                        "ended_at": "z", "exit_code": -9,
                        "terminal_state": "TIMED_OUT",
                    }},
                    # ABORTED_PREP (from manifest entry)
                    {"index": 3, "pid": None,
                     "terminal_state": "ABORTED_PREP"},
                    # RUNNING
                    {"index": 4, "pid": 5, "status": {
                        "state": "RUNNING", "pid": 5,
                        "started_at": "x", "heartbeat": "y",
                        "exit_code": None,
                        "terminal_state": None,
                    }},
                    # PENDING (no status.json)
                    {"index": 5, "pid": 6},
                ],
            )
            summaries = ST.list_harness_runs(Path(tmp))
            self.assertEqual(len(summaries), 1)
            s = summaries[0]
            self.assertEqual(s.total_runs, 6)
            self.assertEqual(s.completed, 1)
            self.assertEqual(s.failed, 1)
            self.assertEqual(s.timed_out, 1)
            self.assertEqual(s.aborted_prep, 1)
            self.assertEqual(s.running, 1)
            self.assertEqual(s.pending, 1)

    def test_collector_alive_window(self) -> None:
        """collector.log mtime within the liveness window ⇒
        collector_alive=True; older ⇒ False."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_p = Path(tmp)
            alive = _build_harness_run(
                tmp_p, name="alive", runs=[
                    {"index": 0, "pid": 1},
                ],
                collector_log_age_s=5.0,  # 5s old → alive
            )
            dead = _build_harness_run(
                tmp_p, name="dead", runs=[
                    {"index": 0, "pid": 2},
                ],
                collector_log_age_s=999.0,  # 999s → dead
            )
            summaries = {
                s.harness_run_dir.name: s
                for s in ST.list_harness_runs(tmp_p)
            }
            self.assertTrue(summaries["alive"].collector_alive)
            self.assertFalse(summaries["dead"].collector_alive)

    def test_empty_runs_root_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                ST.list_harness_runs(Path(tmp)), [],
            )


# ---------------------------------------------------------------------------
# Task C — pid_is_alive: os.kill(pid, 0) semantics + patchable
# ---------------------------------------------------------------------------


class PidIsAliveTests(unittest.TestCase):

    def test_dead_pid_returns_false(self) -> None:
        self.assertFalse(ST.pid_is_alive(999999999))

    def test_zero_or_negative_returns_false(self) -> None:
        self.assertFalse(ST.pid_is_alive(0))
        self.assertFalse(ST.pid_is_alive(-1))
        self.assertFalse(ST.pid_is_alive(None))

    def test_alive_pid_returns_true(self) -> None:
        proc = subprocess.Popen(
            [sys.executable, "-c",
              "import time; time.sleep(30)"]
        )
        try:
            self.assertTrue(ST.pid_is_alive(proc.pid))
        finally:
            proc.kill()
            proc.wait(timeout=5)


# ---------------------------------------------------------------------------
# Task C — tail_stream: sentinel rendering + pass-through
# ---------------------------------------------------------------------------


class TailStreamTests(unittest.TestCase):

    def test_renders_phase_sentinel_with_note(self) -> None:
        rendered = ST.render_stream_line(_phase_sentinel(
            phase=3, name="code-review", state="done",
            ts="2026-05-26T18:30:00Z",
            note="Found 2 dup-key bugs.",
        ))
        self.assertIn("phase 3", rendered)
        self.assertIn("code-review", rendered)
        self.assertIn("DONE", rendered)
        self.assertIn("Found 2 dup-key bugs.", rendered)

    def test_renders_gate_sentinel(self) -> None:
        rendered = ST.render_stream_line(_gate_sentinel(
            gate_result="PASS", verdict_state="solid",
        ))
        self.assertIn("GATE PASS", rendered)
        self.assertIn("verdict_state=solid", rendered)

    def test_passes_through_non_sentinel(self) -> None:
        rendered = ST.render_stream_line(
            '{"event": "phase1_complete", "files": 42}'
        )
        self.assertEqual(
            rendered,
            '{"event": "phase1_complete", "files": 42}',
        )

    def test_passes_through_malformed_sentinel(self) -> None:
        """A `::QPB:: …` line with garbage JSON passes
        through verbatim (never raises)."""
        rendered = ST.render_stream_line(
            "::QPB:: not-valid-json-here"
        )
        self.assertEqual(
            rendered, "::QPB:: not-valid-json-here",
        )

    def test_tail_stream_no_file_returns_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty_run = Path(tmp) / "run-00"
            empty_run.mkdir()
            lines = list(ST.tail_stream(empty_run))
            self.assertEqual(lines, [])

    def test_tail_stream_reads_existing_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run-00"
            run_dir.mkdir()
            (run_dir / "stream.ndjson").write_text(
                "first line\n" +
                _phase_sentinel(phase=1, name="exploration",
                                 state="start") + "\n" +
                "third line\n",
                encoding="utf-8",
            )
            lines = list(ST.tail_stream(run_dir))
            self.assertEqual(len(lines), 3)
            self.assertEqual(lines[0], "first line")
            self.assertIn("phase 1", lines[1])
            self.assertIn("exploration", lines[1])
            self.assertEqual(lines[2], "third line")


# ---------------------------------------------------------------------------
# Task B — CLI smoke (status / status <dir> / tail / no-args)
# ---------------------------------------------------------------------------


class CliStatusSmokeTests(unittest.TestCase):

    def _run(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "bin.qpb_harness_legacy", *args],
            cwd=str(Path(__file__).resolve().parents[3]),
            capture_output=True, text=True, timeout=30,
        )

    def test_no_args_self_describes(self) -> None:
        """089x: bare qpb_harness prints purpose + exits 0."""
        result = self._run()
        self.assertEqual(result.returncode, 0)
        # Carries the canonical purpose-banner shape.
        self.assertIn("qpb_harness", result.stdout)

    def test_status_no_args_lists_empty_runs_root(self) -> None:
        """`qpb_harness status --runs-root <empty>` exits 0
        with a 'No harness-runs' message (safe over empty
        tree)."""
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run(
                "status", "--runs-root", tmp,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("No harness-runs",
                            result.stderr)

    def test_status_lists_a_fixture_harness_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = _build_harness_run(
                Path(tmp), runs=[
                    {"index": 0, "pid": 1, "status": {
                        "state": "DONE", "pid": 1,
                        "started_at": "x", "heartbeat": "y",
                        "ended_at": "z", "exit_code": 0,
                        "terminal_state": "COMPLETED",
                    }},
                ],
            )
            result = self._run(
                "status", "--runs-root", str(harness_run.parent),
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn(harness_run.name, result.stdout)

    def test_status_drill_down(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            harness_run = _build_harness_run(
                Path(tmp), runs=[{
                    "index": 0,
                    "description": "drill-down test",
                    "pid": 1,
                    "stream_lines": [
                        _phase_sentinel(
                            phase=2, name="generation",
                            state="start",
                        ),
                    ],
                }],
            )
            result = self._run("status", str(harness_run))
            self.assertEqual(
                result.returncode, 0,
                f"stderr:\n{result.stderr}",
            )
            self.assertIn("P2", result.stdout)
            self.assertIn("generation", result.stdout)

    def test_tail_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run-00"
            run_dir.mkdir()
            (run_dir / "stream.ndjson").write_text(
                _phase_sentinel(
                    phase=0, name="validation",
                    state="start") + "\n",
                encoding="utf-8",
            )
            result = self._run("tail", str(run_dir))
            self.assertEqual(result.returncode, 0)
            self.assertIn("phase 0", result.stdout)
            self.assertIn("validation", result.stdout)

    def test_status_with_no_manifest_dir_lists_as_empty_runs_root(
            self) -> None:
        """v1.5.7 135: under the single-positional classifier, an
        existing dir with no manifest / run markers is no longer
        distinguishable (by a flag) from a fresh empty runs-root,
        so ``status`` degrades to the graceful "No harness-runs"
        runs-root view (exit 0) rather than the pre-135 "no
        manifest.json" error. Only a NON-existent path errors."""
        with tempfile.TemporaryDirectory() as tmp:
            bogus = Path(tmp) / "no-manifest"
            bogus.mkdir()
            result = self._run("status", str(bogus))
            self.assertEqual(result.returncode, 0)
            self.assertIn("No harness-runs", result.stderr)

    def test_status_with_nonexistent_dir_errors_clean(self) -> None:
        """A path that doesn't exist still errors cleanly
        (FileNotFoundError → exit 2)."""
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "does-not-exist"
            result = self._run("status", str(missing))
            self.assertEqual(result.returncode, 2)
            self.assertIn("not a directory", result.stderr)


# ---------------------------------------------------------------------------
# Bundle-safety: status.py stays under bin/harness/ (excluded)
# ---------------------------------------------------------------------------


class BundleSafety110Tests(unittest.TestCase):

    def test_status_module_under_harness(self) -> None:
        """The new ``bin/harness/status.py`` is under the
        excluded path. The CLI subcommand wiring in
        ``bin/qpb_harness.py`` is also outside the bundle
        (qpb_harness is harness-only). Re-checks the 091
        invariant."""
        path = (Path(__file__).resolve().parents[3]
                / "bin" / "harness" / "status.py")
        self.assertTrue(path.is_file())
        from bin.install_skill import _bundle_files
        repo_root = path.parents[2]
        bundle = _bundle_files(repo_root)
        for _src, dst in bundle:
            p = str(dst)
            self.assertFalse(
                "harness" in p,
                f"110 must not leak bin/harness/ into the "
                f"bundle; saw {p}",
            )


if __name__ == "__main__":
    unittest.main()
