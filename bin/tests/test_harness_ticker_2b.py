"""v1.5.9 Phase 2B — harness_ticker.py (cadence rungs 3-4: FR-24, FR-16,
FR-25, FR-29 / UC-5,6,7).

The ticker drives the plan from a plain window (rung 3, the no-admin floor)
or one tick at a time (--once, rungs 2/4). It spawns dispatch_mode:"shell"
workers detached, records their PIDs, runs the auth pre-flight, warns on
synced folders (E4), and prints the exact continue-command on any
exit-without-done (FR-25). These tests use fast python-cmd workers so the
loop completes deterministically.

MUTATION-VERIFY EVIDENCE (DEVELOPMENT_PROCESS.md §Mutation-test), instr 009:
  Pin: test_auth_preflight_failure_marks_entry_failed. Mutation: in
    harness_ticker._spawn_dispatches, change `if auth_check and not
    _auth_ok(...)` to `if auth_check and _auth_ok(...)` (invert). Observed:
    the auth-fail test FAILs (a failing CLI is treated as OK and the entry
    is spawned/not-failed). Restored -> OK.
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
_TICKER = _REPO_ROOT / "bin" / "harness_ticker.py"
_ENGINE = _REPO_ROOT / "bin" / "qpb_harness_tick.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


TICK = _load("ticker_ut", _TICKER)


# A worker_cmd that immediately writes a COMPLETED terminal heartbeat to
# {HEARTBEAT_PATH} and exits — deterministic, no sleeps.
_FAST_WORKER = [
    sys.executable, "-c",
    ("import json,sys;"
     "open(sys.argv[1],'a').write("
     "json.dumps({'ts':'t','task_id':sys.argv[2],'schema_version':'1',"
     "'status':'COMPLETED','result_file':'x','summary':'done'})+chr(10))"),
    "{HEARTBEAT_PATH}", "{TASK_ID}",
]


def _plan(entries, **top):
    p = {"schema_version": "1", "tick_interval_minutes": 1, "pool_size": 2,
         "entries": entries}
    p.update(top)
    return p


def _shell_entry(tid, cmd=None, auth_check=None):
    e = {"task_id": tid, "target_repo": "/tmp/x", "dispatch_mode": "shell",
         "worker_prompt": "p", "worker_cmd": cmd or list(_FAST_WORKER)}
    if auth_check is not None:
        e["auth_check"] = auth_check
    return e


def _run_ticker(plan_path, *args, runs_dir=None):
    env = dict(os.environ)
    if runs_dir:
        env["QPB_HARNESS_RUNS_DIR"] = str(runs_dir)
    return subprocess.run([sys.executable, str(_TICKER), str(plan_path), *args],
                          capture_output=True, text=True, env=env,
                          encoding="utf-8", errors="replace", timeout=60)


class HelperTests(unittest.TestCase):
    def test_floor_command_is_once_form(self):
        cmd = TICK._floor_command(Path("/tmp/rd"))
        self.assertIn("--once", cmd)
        self.assertIn("/tmp/rd", cmd)
        self.assertIn("harness_ticker.py", cmd)

    def test_synced_folder_warns(self):
        # capture stderr via a subprocess-free direct call
        import io
        from contextlib import redirect_stderr
        buf = io.StringIO()
        with redirect_stderr(buf):
            TICK._warn_synced_folder(Path("/Users/me/Dropbox/runs/x"))
        self.assertIn("E4", buf.getvalue())
        buf2 = io.StringIO()
        with redirect_stderr(buf2):
            TICK._warn_synced_folder(Path("/tmp/local/x"))
        self.assertEqual(buf2.getvalue(), "")

    def test_auth_ok_caches_and_reflects_exit(self):
        cache = {}
        ok = TICK._auth_ok([sys.executable, "-c", "pass"], cache)
        self.assertTrue(ok)
        bad = TICK._auth_ok([sys.executable, "-c", "import sys;sys.exit(1)"], cache)
        self.assertFalse(bad)
        # cached
        self.assertIn((sys.executable, "-c", "pass"), cache)


class OnceModeTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.runs = self.tmp / "hr"

    def tearDown(self):
        self._tmp.cleanup()

    def test_once_inits_spawns_and_prints_floor(self):
        plan = self.tmp / "plan.json"
        plan.write_text(json.dumps(_plan([_shell_entry("t-1")], pool_size=1)))
        # first --once: init + dispatch + spawn (worker writes COMPLETED)
        rc = _run_ticker(plan, "--once", runs_dir=self.runs)
        self.assertEqual(rc.returncode, 0, rc.stderr)
        # not done yet (reap happens next tick) → floor command printed
        self.assertIn("To continue this run", rc.stdout)
        self.assertIn("--once", rc.stdout)
        # a run-dir now exists with a claimed job + a recorded PID
        run_dirs = list(self.runs.iterdir())
        self.assertEqual(len(run_dirs), 1)
        rd = run_dirs[0]
        # second --once against the run-dir: reaps the completed worker
        rc2 = _run_ticker(rd, "--once", runs_dir=self.runs)
        self.assertEqual(rc2.returncode, 0, rc2.stderr)
        status = json.loads((rd / "harness_status.json").read_text())
        self.assertEqual(status["runs"]["run-01"]["state"], "completed")

    def test_loop_runs_to_done(self):
        plan = self.tmp / "plan.json"
        plan.write_text(json.dumps(_plan(
            [_shell_entry("t-1"), _shell_entry("t-2")], pool_size=2)))
        # A small NONZERO interval so each detached worker has time to write
        # its heartbeat before the next tick (a zero interval out-races the
        # workers — unrealistic; real cadence is minutes).
        rc = _run_ticker(plan, "--interval", "0.5", "--max-ticks", "20",
                         runs_dir=self.runs)
        self.assertEqual(rc.returncode, 0, rc.stderr)
        self.assertIn("DONE - all runs terminal", rc.stdout)

    def test_auth_preflight_failure_marks_entry_failed(self):
        plan = self.tmp / "plan.json"
        # auth_check that exits nonzero → entry must NOT spawn; gets FAILED
        plan.write_text(json.dumps(_plan([_shell_entry(
            "t-1", auth_check=[sys.executable, "-c", "import sys;sys.exit(1)"])],
            pool_size=1)))
        rc = _run_ticker(plan, "--once", runs_dir=self.runs)
        self.assertIn("AUTH_OR_LAUNCH_FAILED", rc.stderr)
        rd = next(self.runs.iterdir())
        # the ticker wrote a FAILED terminal heartbeat → next tick reaps failed
        rc2 = _run_ticker(rd, "--once", runs_dir=self.runs)
        status = json.loads((rd / "harness_status.json").read_text())
        self.assertEqual(status["runs"]["run-01"]["state"], "failed")

    def test_subagent_entry_skipped_with_note(self):
        plan = self.tmp / "plan.json"
        plan.write_text(json.dumps(_plan(
            [{"task_id": "t-1", "target_repo": "/tmp/x",
              "dispatch_mode": "subagent", "worker_prompt": "p"}], pool_size=1)))
        rc = _run_ticker(plan, "--once", runs_dir=self.runs)
        self.assertIn("only launches shell workers", rc.stderr)


if __name__ == "__main__":
    unittest.main()
