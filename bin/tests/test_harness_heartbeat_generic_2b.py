"""v1.5.9 Phase 2B — generic heartbeat helper + demo worker (FR-18..21).

bin/harness_heartbeat.py is the payload-agnostic heartbeat core (phase is a
FREE STRING, no phase_identity / run_state coupling — FR-20) that extracts
to the standalone repo. bin/harness_demo_worker.py is the cross-platform
stub (FR-31). This pins: JSON-encoding of every value (FR-19), free-string
phase, keepalive-reuses-last-phase, the E6 loud-nonzero write-failure path
(FR-21), Mode-A no-op, and the demo lifecycle.

MUTATION-VERIFY EVIDENCE (DEVELOPMENT_PROCESS.md §Mutation-test), instr 009:
  Pin: test_e6_write_failure_exits_nonzero. Mutation: in
    harness_heartbeat._append_or_die, change `return 5` to `return 0` (a
    silent-swallow). Observed: the E6 test FAILs (exit 0 on a write
    failure — a silent worker looks healthy). Restored -> OK.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[2]
_HB = _REPO_ROOT / "bin" / "harness_heartbeat.py"
_DEMO = _REPO_ROOT / "bin" / "harness_demo_worker.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


H = _load("harness_heartbeat_ut", _HB)


def _run_cli(script, *args):
    return subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


class GenericHeartbeatTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.hb = Path(self._tmp.name) / "heartbeat.ndjson"
        for k in ("HARNESS_HEARTBEAT_PATH", "QPB_HEARTBEAT_PATH",
                  "HARNESS_TASK_ID", "QPB_TASK_ID"):
            os.environ.pop(k, None)

    def tearDown(self):
        self._tmp.cleanup()

    def _lines(self):
        return [json.loads(l) for l in self.hb.read_text().splitlines() if l.strip()]

    def test_phase_is_free_string(self):
        # any string is a legal phase — no phase_identity validation
        for ph in ("demo", "build phase", "weird/slug-99", "Phase 1"):
            H.append_line(self.hb, H.build_progress(
                phase=ph, task_id="t", step="s", status="IN_PROGRESS"))
        self.assertEqual([x["phase"] for x in self._lines()],
                         ["demo", "build phase", "weird/slug-99", "Phase 1"])

    def test_values_json_encoded_special_chars(self):
        rc = _run_cli(_HB, "emit", "--phase", "p%x", "--step", "s",
                      "--status", "IN_PROGRESS", "--task-id", "t-1",
                      "--heartbeat-path", str(self.hb),
                      "--message", 'has % and " and \\ chars')
        self.assertEqual(rc.returncode, 0, rc.stderr)
        obj = self._lines()[-1]
        self.assertEqual(obj["message"], 'has % and " and \\ chars')
        self.assertEqual(obj["phase"], "p%x")
        self.assertEqual(obj["schema_version"], "1")

    def test_keepalive_reuses_last_phase(self):
        H.append_line(self.hb, H.build_progress(
            phase="builder", task_id="t", step="s", status="STARTING"))
        rc = _run_cli(_HB, "keepalive", "--task-id", "t",
                      "--heartbeat-path", str(self.hb))
        self.assertEqual(rc.returncode, 0, rc.stderr)
        last = self._lines()[-1]
        self.assertEqual(last["phase"], "builder")
        self.assertEqual(last["status"], "IN_PROGRESS")

    def test_keepalive_noop_when_no_prior_phase(self):
        rc = _run_cli(_HB, "keepalive", "--task-id", "t",
                      "--heartbeat-path", str(self.hb))
        self.assertEqual(rc.returncode, 0)
        self.assertFalse(self.hb.exists() and self.hb.read_text().strip())

    def test_terminal_carries_result_and_summary(self):
        rc = _run_cli(_HB, "terminal", "--status", "COMPLETED",
                      "--result-file", "/tmp/x/SUMMARY.md", "--summary", "ok",
                      "--task-id", "t", "--heartbeat-path", str(self.hb))
        self.assertEqual(rc.returncode, 0, rc.stderr)
        last = self._lines()[-1]
        self.assertEqual(last["status"], "COMPLETED")
        self.assertEqual(last["result_file"], "/tmp/x/SUMMARY.md")
        self.assertEqual(last["summary"], "ok")
        self.assertNotIn("phase", last)

    def test_bad_status_exits_3(self):
        rc = _run_cli(_HB, "emit", "--phase", "p", "--step", "s",
                      "--status", "BOGUS", "--task-id", "t",
                      "--heartbeat-path", str(self.hb))
        self.assertNotEqual(rc.returncode, 0)  # argparse choices reject it

    def test_mode_a_noop(self):
        rc = _run_cli(_HB, "emit", "--phase", "p", "--step", "s",
                      "--status", "STARTING", "--mode-a-noop")
        self.assertEqual(rc.returncode, 0)

    def test_missing_io_exits_2(self):
        rc = _run_cli(_HB, "emit", "--phase", "p", "--step", "s",
                      "--status", "STARTING")
        self.assertEqual(rc.returncode, 2)

    def test_e6_write_failure_exits_nonzero(self):
        # Point the heartbeat path at a directory → O_APPEND open fails.
        blocked = Path(self._tmp.name) / "blocked_dir"
        blocked.mkdir()
        rc = _run_cli(_HB, "emit", "--phase", "p", "--step", "s",
                      "--status", "STARTING", "--task-id", "t",
                      "--heartbeat-path", str(blocked))
        self.assertEqual(rc.returncode, 5, rc.stderr)
        self.assertIn("HEARTBEAT WRITE FAILED", rc.stderr)


class DemoWorkerTests(unittest.TestCase):
    def test_demo_lifecycle_fast(self):
        with tempfile.TemporaryDirectory() as d:
            rd = Path(d) / "run-01"
            rd.mkdir()
            hb = rd / "heartbeat.ndjson"
            rc = _run_cli(_DEMO, "--heartbeat-path", str(hb), "--task-id",
                          "t-demo", "--run-dir", str(rd), "--steps", "3",
                          "--sleep", "0")
            self.assertEqual(rc.returncode, 0, rc.stderr)
            statuses = [json.loads(l)["status"]
                        for l in hb.read_text().splitlines() if l.strip()]
            self.assertEqual(statuses[0], "STARTING")
            self.assertEqual(statuses[-1], "COMPLETED")
            self.assertEqual(statuses.count("IN_PROGRESS"), 3)
            self.assertTrue((rd / "result.txt").is_file())


if __name__ == "__main__":
    unittest.main()
