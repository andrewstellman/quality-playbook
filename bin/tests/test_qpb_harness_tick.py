"""v1.5.9 Phase 1B — unit tests for bin/qpb_harness_tick.py.

Covers the production state machine: --init scaffolding, the
queued→claimed→running→completed/failed lifecycle, pool_size gating,
stall detection, AUTH_OR_LAUNCH_FAILED, terminal-tick cosmetics,
double-tick idempotency, STOP read-only, and the JSON output shape.

Time-dependent transitions (stall, launch grace) are driven by the
QPB_HARNESS_NOW env override the script reads, so no test sleeps.

MUTATION-VERIFY EVIDENCE (in-tree per DEVELOPMENT_PROCESS.md §Mutation-
test discipline), v1.5.9 instruction 005 — regression pins BITE-executed:

  Pin: test_double_tick_is_idempotent (pool_size 3, 2 entries → free slot).
  Mutation: in _dispatch, widen the per-run guard
    `if r["state"] != "queued": continue`  →
    `if r["state"] not in ("queued", "claimed"): continue`
    (lets an already-claimed run be re-dispatched when a slot is free).
  Observed: test_double_tick_is_idempotent FAILs — the second tick re-emits
    a dispatch entry for an already-claimed run. Restored → OK. (The
    `not src.exists()` file guard is defense-in-depth; the state guard is
    the load-bearing idempotency check.)

  Pin: test_stall_detection_marks_stalled.
  Mutation: in _advance, change the stall comparison `(now - mtime) >
    stall_secs` to `< stall_secs`.
  Observed: test_stall_detection_marks_stalled FAILs (run never marked
    stalled with an old heartbeat). Restored → OK.

  Pin: test_reap_guard_records_anomaly_when_claimed_file_absent.
  Mutation: in _move_to_results, delete the `record["anomaly"] = ...`
    branch (silently fabricate clean success).
  Observed: the anomaly-field assertion FAILs. Restored → OK.
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


_REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_tick():
    spec = importlib.util.spec_from_file_location(
        "qpb_harness_tick_under_test", str(_REPO_ROOT / "qpb_harness_tick.py"))
    mod = importlib.util.module_from_spec(spec)
    import sys
    sys.modules["qpb_harness_tick_under_test"] = mod
    spec.loader.exec_module(mod)
    return mod


T = _load_tick()


def _plan(entries, **top):
    p = {"tick_interval_minutes": 5, "pool_size": top.pop("pool_size", 3),
         "entries": entries}
    p.update(top)
    return p


def _entry(tid, repo="/tmp/x"):
    return {"task_id": tid, "target_repo": repo, "dispatch_mode": "subagent",
            "worker_prompt": ("HB={HEARTBEAT_PATH} TID={TASK_ID} "
                              "RD={RUN_DIR} TR={TARGET_REPO}")}


def _shell_entry(tid, repo="/tmp/x"):
    return {"task_id": tid, "target_repo": repo, "dispatch_mode": "shell",
            "worker_prompt": "do work on {TARGET_REPO}",
            "worker_cmd": ["python3", "w.py", "--hb", "{HEARTBEAT_PATH}",
                           "--tid", "{TASK_ID}", "--prompt", "{PROMPT_FILE}"]}


def _hb(run_dir: Path, run: str, **fields):
    line = json.dumps(fields, separators=(",", ":"))
    with (run_dir / run / "heartbeat.ndjson").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _status(run_dir: Path) -> dict:
    return json.loads((run_dir / "harness_status.json").read_text())


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        # Keep all run-dirs hermetic inside the tmp dir.
        os.environ["QPB_HARNESS_RUNS_DIR"] = str(self.tmp / "harness_runs")
        os.environ.pop("QPB_HARNESS_NOW", None)

    def tearDown(self):
        os.environ.pop("QPB_HARNESS_NOW", None)
        os.environ.pop("QPB_HARNESS_RUNS_DIR", None)
        self._tmp.cleanup()

    def _init(self, plan):
        pf = self.tmp / "plan.json"
        pf.write_text(json.dumps(plan))
        return Path(T.init_run(pf))


class InitTests(_Base):
    def test_init_scaffolds_run_dir(self):
        rd = self._init(_plan([_entry("t-1"), _entry("t-2")]))
        self.assertTrue((rd / "plan.json").is_file())
        self.assertTrue((rd / "harness_status.json").is_file())
        self.assertTrue((rd / "queue" / "job-00001.json").is_file())
        self.assertTrue((rd / "queue" / "job-00002.json").is_file())
        for run in ("run-01", "run-02"):
            self.assertTrue((rd / run / "heartbeat.ndjson").is_file())
            self.assertTrue((rd / run / "manifest.json").is_file())
        s = _status(rd)
        self.assertEqual(s["cycle"], 0)
        self.assertEqual(s["counts"]["queued"], 2)
        self.assertFalse(s["done"])

    def test_init_rejects_empty_plan(self):
        pf = self.tmp / "empty.json"
        pf.write_text(json.dumps({"entries": []}))
        with self.assertRaises(ValueError):
            T.init_run(pf)


class TickOutputShapeTests(_Base):
    def test_tick_returns_five_keys(self):
        rd = self._init(_plan([_entry("t-1")]))
        out = T.tick(rd)
        self.assertEqual(set(out), {"dispatch_list", "status_table",
                                    "next_tick_minutes", "done", "stop"})
        self.assertIsInstance(out["dispatch_list"], list)
        self.assertIsInstance(out["status_table"], str)
        self.assertIsInstance(out["next_tick_minutes"], int)

    def test_dispatch_prompt_placeholders_resolved_absolute(self):
        rd = self._init(_plan([_entry("t-1", "/tmp/target-x")]))
        out = T.tick(rd)
        wp = out["dispatch_list"][0]["worker_prompt"]
        self.assertNotIn("{HEARTBEAT_PATH}", wp)
        self.assertNotIn("{TASK_ID}", wp)
        self.assertIn(str(rd / "run-01" / "heartbeat.ndjson"), wp)
        self.assertIn("/tmp/target-x", wp)
        # all paths absolute
        self.assertTrue(str(rd / "run-01").startswith("/"))


class PoolGatingTests(_Base):
    def test_pool_size_one_dispatches_one(self):
        rd = self._init(_plan([_entry("t-1"), _entry("t-2")], pool_size=1))
        out = T.tick(rd)
        self.assertEqual([e["run"] for e in out["dispatch_list"]], ["run-01"])
        s = _status(rd)
        self.assertEqual(s["runs"]["run-01"]["state"], "claimed")
        self.assertEqual(s["runs"]["run-02"]["state"], "queued")

    def test_pool_size_three_dispatches_three(self):
        rd = self._init(_plan([_entry("t-1"), _entry("t-2"), _entry("t-3")],
                              pool_size=3))
        out = T.tick(rd)
        self.assertEqual(len(out["dispatch_list"]), 3)


class LifecycleTests(_Base):
    def test_full_lifecycle_pool_one(self):
        rd = self._init(_plan([_entry("t-1"), _entry("t-2")], pool_size=1))
        T.tick(rd)  # dispatch run-01
        _hb(rd, "run-01", ts="t", task_id="t-1", schema_version="1",
            phase="exploration", step="s", status="STARTING")
        T.tick(rd)
        self.assertEqual(_status(rd)["runs"]["run-01"]["state"], "running")
        self.assertEqual(_status(rd)["runs"]["run-02"]["state"], "queued")
        # run-01 completes → reaped, pool frees, run-02 dispatched
        _hb(rd, "run-01", ts="t", task_id="t-1", schema_version="1",
            status="COMPLETED", result_file="/tmp/x/SUMMARY.md", summary="ok")
        out = T.tick(rd)
        s = _status(rd)
        self.assertEqual(s["runs"]["run-01"]["state"], "completed")
        self.assertTrue((rd / "results" / "result-00001.json").is_file())
        self.assertFalse((rd / "claimed" / "job-00001.json").exists())
        self.assertEqual([e["run"] for e in out["dispatch_list"]], ["run-02"])
        # run-02 fails → reaped failed → all terminal → done
        _hb(rd, "run-02", ts="t", task_id="t-2", schema_version="1",
            status="FAILED", summary="boom")
        out = T.tick(rd)
        s = _status(rd)
        self.assertEqual(s["runs"]["run-02"]["state"], "failed")
        self.assertTrue(out["done"])
        self.assertTrue((rd / "results" / "result-00002.json").is_file())

    def test_result_record_carries_terminal_meta(self):
        rd = self._init(_plan([_entry("t-1")], pool_size=1))
        T.tick(rd)
        _hb(rd, "run-01", ts="t", task_id="t-1", schema_version="1",
            status="COMPLETED", result_file="/tmp/x/SUMMARY.md", summary="done")
        T.tick(rd)
        rec = json.loads((rd / "results" / "result-00001.json").read_text())
        self.assertEqual(rec["terminal_status"], "COMPLETED")
        self.assertEqual(rec["result_file"], "/tmp/x/SUMMARY.md")
        self.assertEqual(rec["summary"], "done")


class StallTests(_Base):
    def test_stall_detection_marks_stalled(self):
        rd = self._init(_plan([_entry("t-1")], pool_size=1,
                              stall_threshold_minutes=45))
        T.tick(rd)
        _hb(rd, "run-01", ts="t", task_id="t-1", schema_version="1",
            phase="generation", step="s", status="IN_PROGRESS")
        T.tick(rd)
        self.assertEqual(_status(rd)["runs"]["run-01"]["state"], "running")
        # jump the clock 46 minutes past the heartbeat mtime
        future = (rd / "run-01" / "heartbeat.ndjson").stat().st_mtime + 46 * 60
        os.environ["QPB_HARNESS_NOW"] = str(future)
        T.tick(rd)
        self.assertEqual(_status(rd)["runs"]["run-01"]["state"], "stalled")

    def test_stalled_recovers_to_running_on_fresh_heartbeat(self):
        rd = self._init(_plan([_entry("t-1")], pool_size=1,
                              stall_threshold_minutes=45))
        T.tick(rd)
        _hb(rd, "run-01", ts="t", task_id="t-1", schema_version="1",
            status="IN_PROGRESS")
        future = (rd / "run-01" / "heartbeat.ndjson").stat().st_mtime + 46 * 60
        os.environ["QPB_HARNESS_NOW"] = str(future)
        T.tick(rd)
        self.assertEqual(_status(rd)["runs"]["run-01"]["state"], "stalled")
        # fresh heartbeat written "now" on the fake clock: in a real run the
        # file mtime IS the worker's write time, so set it to the fake now.
        os.environ["QPB_HARNESS_NOW"] = str(future + 60)
        _hb(rd, "run-01", ts="t", task_id="t-1", schema_version="1",
            status="IN_PROGRESS")
        os.utime(rd / "run-01" / "heartbeat.ndjson", (future + 60, future + 60))
        T.tick(rd)
        self.assertEqual(_status(rd)["runs"]["run-01"]["state"], "running")


class LaunchFailureTests(_Base):
    def test_no_heartbeat_past_grace_marks_auth_or_launch_failed(self):
        rd = self._init(_plan([_entry("t-1")], pool_size=1,
                              launch_grace_minutes=10))
        # dispatch at a fixed clock
        os.environ["QPB_HARNESS_NOW"] = "1000000"
        T.tick(rd)
        self.assertEqual(_status(rd)["runs"]["run-01"]["state"], "claimed")
        # 11 minutes later, still no heartbeat → launch failed
        os.environ["QPB_HARNESS_NOW"] = str(1000000 + 11 * 60)
        out = T.tick(rd)
        s = _status(rd)
        self.assertEqual(s["runs"]["run-01"]["state"], "auth_or_launch_failed")
        self.assertTrue(out["done"])
        rec = json.loads((rd / "results" / "result-00001.json").read_text())
        self.assertTrue(rec.get("synthesized"))


class HardeningTests(_Base):
    """Panelist 1B-Council P2 hardening (A-F4 claimed_at=None, B-F3
    mtime=None) — both latent traps, neither reachable in normal flow."""

    def test_claimed_at_none_self_heals_then_grace_applies(self):
        # A claimed run whose claimed_at was lost (hand-edit/anomaly) must
        # NOT be permanently immune to launch-grace: the tick self-heals
        # claimed_at, and grace then applies from that point.
        rd = self._init(_plan([_entry("t-1")], pool_size=1,
                              launch_grace_minutes=10))
        os.environ["QPB_HARNESS_NOW"] = "1000000"
        T.tick(rd)  # claim run-01
        # corrupt: drop claimed_at
        s = _status(rd)
        s["runs"]["run-01"]["claimed_at"] = None
        (rd / "harness_status.json").write_text(json.dumps(s))
        # a tick with no heartbeat self-heals claimed_at (not failed yet)
        T.tick(rd)
        s = _status(rd)
        self.assertEqual(s["runs"]["run-01"]["state"], "claimed")
        self.assertEqual(s["runs"]["run-01"]["claimed_at"], 1000000)
        # 11 min later, still no heartbeat → grace now applies → failed
        os.environ["QPB_HARNESS_NOW"] = str(1000000 + 11 * 60)
        T.tick(rd)
        self.assertEqual(_status(rd)["runs"]["run-01"]["state"],
                         "auth_or_launch_failed")

    def test_unstateable_heartbeat_does_not_recover_a_stalled_run(self):
        # If a heartbeat file exists but can't be stat'd (mtime=None), a
        # stalled run must NOT be recovered to running off an unknowable
        # mtime — that would mask a genuine stall.
        rd = self._init(_plan([_entry("t-1")], pool_size=1,
                              stall_threshold_minutes=45))
        T.tick(rd)
        _hb(rd, "run-01", ts="t", task_id="t-1", schema_version="1",
            status="IN_PROGRESS")
        future = (rd / "run-01" / "heartbeat.ndjson").stat().st_mtime + 46 * 60
        os.environ["QPB_HARNESS_NOW"] = str(future)
        T.tick(rd)
        self.assertEqual(_status(rd)["runs"]["run-01"]["state"], "stalled")
        # force mtime=None by monkeypatching _hb_observe for one tick
        orig = T._hb_observe
        T._hb_observe = lambda hb: (True, "IN_PROGRESS", "generation", None)
        try:
            T.tick(rd)
        finally:
            T._hb_observe = orig
        # stayed stalled (conservative), not falsely recovered to running
        self.assertEqual(_status(rd)["runs"]["run-01"]["state"], "stalled")


class ShellDispatchTests(_Base):
    """v1.5.9 Phase 2B — dispatch_mode:"shell" (FR-15)."""

    def test_shell_dispatch_writes_prompt_file_and_resolves_cmd(self):
        rd = self._init(_plan([_shell_entry("t-1", "/tmp/target")], pool_size=1))
        out = T.tick(rd)
        e = out["dispatch_list"][0]
        self.assertEqual(e["dispatch_mode"], "shell")
        # prompt written to a file (quoting/arg-length safety)
        pf = Path(e["prompt_file"])
        self.assertTrue(pf.is_file())
        self.assertEqual(pf.read_text(), "do work on /tmp/target")
        # worker_cmd fully resolved to absolute paths, no placeholders left
        joined = " ".join(e["worker_cmd"])
        self.assertNotIn("{", joined)
        self.assertIn(str(rd / "run-01" / "heartbeat.ndjson"), e["worker_cmd"])
        self.assertIn(str(pf), e["worker_cmd"])
        # claim lock carries the mode + a pid placeholder for the spawner
        lock = json.loads(
            (rd / "claimed" / "job-00001.lock").read_text())
        self.assertEqual(lock["dispatch_mode"], "shell")
        self.assertIsNone(lock["pid"])

    def test_subagent_dispatch_still_carries_worker_prompt(self):
        rd = self._init(_plan([_entry("t-1")], pool_size=1))
        e = T.tick(rd)["dispatch_list"][0]
        self.assertEqual(e["dispatch_mode"], "subagent")
        self.assertIn("worker_prompt", e)
        self.assertNotIn("worker_cmd", e)


class PidDeadTests(_Base):
    """A-5: a shell worker whose recorded PID is dead and has no terminal
    heartbeat is failed fast (dead-vs-slow discrimination)."""

    def _claim_with_pid(self, pid):
        rd = self._init(_plan([_shell_entry("t-1")], pool_size=1))
        T.tick(rd)  # claim
        lock_path = rd / "claimed" / "job-00001.lock"
        data = json.loads(lock_path.read_text())
        data["pid"] = pid
        lock_path.write_text(json.dumps(data))
        return rd

    def test_dead_pid_no_terminal_fails(self):
        rd = self._claim_with_pid(999999)  # not a live process
        T.tick(rd)
        self.assertEqual(_status(rd)["runs"]["run-01"]["state"], "failed")
        rec = json.loads((rd / "results" / "result-00001.json").read_text())
        self.assertEqual(rec["terminal_status"], "FAILED")

    def test_live_pid_not_failed(self):
        rd = self._claim_with_pid(os.getpid())  # this test process is alive
        T.tick(rd)
        self.assertIn(_status(rd)["runs"]["run-01"]["state"],
                      ("claimed", "running"))

    def test_dead_pid_but_terminal_heartbeat_reaps_completed(self):
        # terminal reap takes priority over the dead-PID failure path
        rd = self._claim_with_pid(999999)
        _hb(rd, "run-01", ts="t", task_id="t-1", schema_version="1",
            status="COMPLETED", result_file="x", summary="ok")
        T.tick(rd)
        self.assertEqual(_status(rd)["runs"]["run-01"]["state"], "completed")


class WallClockJumpE2Tests(_Base):
    def test_wall_clock_jump_suppresses_stall(self):
        rd = self._init(_plan([_entry("t-1")], pool_size=1,
                              stall_threshold_minutes=45))
        os.environ["QPB_HARNESS_NOW"] = "1000000"
        T.tick(rd)
        hb = rd / "run-01" / "heartbeat.ndjson"
        _hb(rd, "run-01", ts="t", task_id="t-1", schema_version="1",
            phase="p", step="s", status="IN_PROGRESS")
        os.utime(hb, (1000000, 1000000))
        T.tick(rd)  # running; stores last_tick_wall=1000000
        # jump 10h forward — heartbeat age is now huge but it's a sleep jump
        os.environ["QPB_HARNESS_NOW"] = str(1000000 + 10 * 3600)
        T.tick(rd)
        self.assertEqual(_status(rd)["runs"]["run-01"]["state"], "running")

    def test_normal_cadence_stale_heartbeat_still_stalls(self):
        # control: a stale heartbeat WITHOUT a wall-clock jump still stalls
        rd = self._init(_plan([_entry("t-1")], pool_size=1,
                              stall_threshold_minutes=45))
        os.environ["QPB_HARNESS_NOW"] = "2000000"
        T.tick(rd)
        hb = rd / "run-01" / "heartbeat.ndjson"
        _hb(rd, "run-01", ts="t", task_id="t-1", schema_version="1",
            phase="p", step="s", status="IN_PROGRESS")
        os.utime(hb, (2000000, 2000000))
        T.tick(rd)
        # +50 min: > stall threshold but a normal-sized gap (no jump)
        os.environ["QPB_HARNESS_NOW"] = str(2000000 + 50 * 60)
        T.tick(rd)
        self.assertEqual(_status(rd)["runs"]["run-01"]["state"], "stalled")


class TickLockE1Tests(_Base):
    def test_concurrent_tick_lock_blocks_then_releases(self):
        rd = self._init(_plan([_entry("t-1")], pool_size=1))
        l1 = T._TickLock(rd).__enter__()
        try:
            l2 = T._TickLock(rd)
            l2.__enter__()
            try:
                self.assertTrue(l1.acquired)
                self.assertFalse(l2.acquired)  # second is blocked
            finally:
                l2.__exit__()
        finally:
            l1.__exit__()
        # after release, a fresh lock acquires
        l3 = T._TickLock(rd)
        l3.__enter__()
        self.assertTrue(l3.acquired)
        l3.__exit__()

    def test_main_locked_skip_is_clean(self):
        rd = self._init(_plan([_entry("t-1")], pool_size=1))
        held = T._TickLock(rd).__enter__()
        try:
            proc = subprocess.run(
                [sys.executable, str(T.__file__), str(rd)],
                capture_output=True, text=True,
                env={**os.environ}, encoding="utf-8")
            out = json.loads(proc.stdout)
            self.assertTrue(out.get("skipped"))
            self.assertEqual(out["dispatch_list"], [])
            self.assertIn("skipped cleanly", out["status_table"])
        finally:
            held.__exit__()


class ReapGuardTests(_Base):
    def test_reap_guard_records_anomaly_when_claimed_file_absent(self):
        rd = self._init(_plan([_entry("t-1")], pool_size=1))
        T.tick(rd)  # claim run-01
        # externally delete the claimed job file
        (rd / "claimed" / "job-00001.json").unlink()
        _hb(rd, "run-01", ts="t", task_id="t-1", schema_version="1",
            status="COMPLETED", summary="done")
        T.tick(rd)
        rec = json.loads((rd / "results" / "result-00001.json").read_text())
        # GUARD: doesn't silently fabricate clean success — records the anomaly
        self.assertEqual(rec.get("anomaly"), "claimed_job_file_absent_at_reap")
        # but the run still leaves the in-flight set (heartbeat is truth)
        self.assertEqual(_status(rd)["runs"]["run-01"]["state"], "completed")


class IdempotencyTests(_Base):
    def test_double_tick_is_idempotent(self):
        # pool_size 3 with 2 entries leaves a FREE slot, so a broken state
        # guard would actually re-dispatch a claimed run (the mutation this
        # pins) rather than being masked by a saturated pool.
        rd = self._init(_plan([_entry("t-1"), _entry("t-2")], pool_size=3))
        T.tick(rd)
        before = _status(rd)
        before_counts = dict(before["counts"])
        before_states = {n: r["state"] for n, r in before["runs"].items()}
        out2 = T.tick(rd)  # immediate re-tick
        after = _status(rd)
        # no new dispatch, no state/count change — only cycle advances
        self.assertEqual(out2["dispatch_list"], [])
        self.assertEqual(after["counts"], before_counts)
        self.assertEqual({n: r["state"] for n, r in after["runs"].items()},
                         before_states)
        self.assertEqual(after["cycle"], before["cycle"] + 1)

    def test_reap_is_idempotent(self):
        rd = self._init(_plan([_entry("t-1")], pool_size=1))
        T.tick(rd)
        _hb(rd, "run-01", ts="t", task_id="t-1", schema_version="1",
            status="COMPLETED", summary="ok")
        T.tick(rd)
        body1 = (rd / "results" / "result-00001.json").read_text()
        T.tick(rd)  # re-tick after done
        body2 = (rd / "results" / "result-00001.json").read_text()
        self.assertEqual(body1, body2)  # result file not rewritten


class StopTests(_Base):
    def test_stop_is_read_only(self):
        rd = self._init(_plan([_entry("t-1")], pool_size=1))
        T.tick(rd)  # claim
        before = (rd / "harness_status.json").read_text()
        (rd / "STOP").touch()
        out = T.tick(rd)
        self.assertTrue(out["stop"])
        self.assertFalse(out["done"])
        self.assertEqual(out["dispatch_list"], [])
        # status file untouched — not even cycle bumped
        self.assertEqual((rd / "harness_status.json").read_text(), before)
        self.assertIn("No further ticks", out["status_table"])


class TerminalCosmeticsTests(_Base):
    def test_done_tick_omits_next_tick_line(self):
        rd = self._init(_plan([_entry("t-1")], pool_size=1))
        T.tick(rd)
        _hb(rd, "run-01", ts="t", task_id="t-1", schema_version="1",
            status="COMPLETED", summary="ok")
        out = T.tick(rd)
        self.assertTrue(out["done"])
        self.assertNotIn("Next tick in", out["status_table"])
        self.assertIn("DONE", out["status_table"])

    def test_stop_tick_omits_next_tick_line(self):
        rd = self._init(_plan([_entry("t-1")], pool_size=1))
        T.tick(rd)
        (rd / "STOP").touch()
        out = T.tick(rd)
        self.assertNotIn("Next tick in", out["status_table"])

    def test_running_tick_shows_next_tick_line(self):
        rd = self._init(_plan([_entry("t-1")], pool_size=1))
        out = T.tick(rd)
        self.assertIn("Next tick in", out["status_table"])


class HeartbeatV2ReaderTests(_Base):
    """Instruction 010 / FR-18: the reader displays the v2 `label`, and
    still reads v1 `phase` (Postel: liberal in what it accepts)."""

    def test_reads_v2_label_into_activity_column(self):
        rd = self._init(_plan([_entry("t-1")], pool_size=1))
        T.tick(rd)  # claim run-01
        _hb(rd, "run-01", ts="t", task_id="t-1", schema_version="2",
            label="2:generation", status="IN_PROGRESS", data={"step": "s"})
        out = T.tick(rd)
        self.assertIn("ACTIVITY", out["status_table"])
        self.assertIn("2:generation", out["status_table"])

    def test_reads_v1_phase_into_activity_column_postel(self):
        rd = self._init(_plan([_entry("t-1")], pool_size=1))
        T.tick(rd)
        _hb(rd, "run-01", ts="t", task_id="t-1", schema_version="1",
            phase="exploration", step="s", status="IN_PROGRESS")
        out = T.tick(rd)
        self.assertIn("exploration", out["status_table"])

    def test_malformed_line_is_skipped_not_fatal_and_warned(self):
        rd = self._init(_plan([_entry("t-1")], pool_size=1))
        T.tick(rd)
        # a torn / non-JSON line followed by a valid one
        with (rd / "run-01" / "heartbeat.ndjson").open(
                "a", encoding="utf-8") as fh:
            fh.write('{"ts":"t","task_id" TORN\n')
        _hb(rd, "run-01", ts="t", task_id="t-1", schema_version="2",
            label="2:generation", status="IN_PROGRESS")
        out = T.tick(rd)  # must not raise
        # the valid line still drove the state to running
        self.assertEqual(_status(rd)["runs"]["run-01"]["state"], "running")
        # the non-fatal warning is logged
        log = (rd / "harness_tick.log").read_text(encoding="utf-8")
        self.assertIn("malformed heartbeat line", log)


class HarnessBinPlaceholderTests(_Base):
    """FR-21a: {HARNESS_BIN} is substituted MECHANICALLY by the engine
    (never transcribed by a model)."""

    def test_harness_bin_substituted_in_subagent_prompt(self):
        e = _entry("t-1")
        e["worker_prompt"] = "run {HARNESS_BIN}/harness_demo_worker.py"
        rd = self._init(_plan([e], pool_size=1))
        out = T.tick(rd)
        wp = out["dispatch_list"][0]["worker_prompt"]
        self.assertNotIn("{HARNESS_BIN}", wp)
        self.assertIn(T._HARNESS_BIN, wp)
        self.assertIn("/harness_demo_worker.py", wp)

    def test_harness_bin_substituted_in_shell_cmd(self):
        e = _shell_entry("t-1")
        e["worker_cmd"] = ["python3", "{HARNESS_BIN}/harness_demo_worker.py",
                           "--hb", "{HEARTBEAT_PATH}"]
        rd = self._init(_plan([e], pool_size=1))
        out = T.tick(rd)
        cmd = out["dispatch_list"][0]["worker_cmd"]
        self.assertEqual(cmd[1], T._HARNESS_BIN + "/harness_demo_worker.py")


class HeartbeatPathOverrideTests(_Base):
    """FR-20: a plan entry may point the harness at a heartbeat file the
    job already writes (absolute) instead of the run-dir default."""

    def test_override_is_watched_and_substituted(self):
        external = self.tmp / "external_status.ndjson"
        e = _entry("t-1")
        e["heartbeat_path"] = str(external)
        rd = self._init(_plan([e], pool_size=1))
        # the manifest records the override
        mf = json.loads((rd / "run-01" / "manifest.json").read_text())
        self.assertEqual(mf["heartbeat_path"], str(external))
        # dispatch substitutes {HEARTBEAT_PATH} to the override, not default
        out = T.tick(rd)
        wp = out["dispatch_list"][0]["worker_prompt"]
        self.assertIn(str(external), wp)
        self.assertNotIn(str(rd / "run-01" / "heartbeat.ndjson"), wp)
        # the engine reads liveness from the override file
        external.write_text(
            '{"ts":"t","task_id":"t-1","schema_version":"2",'
            '"label":"ext","status":"IN_PROGRESS"}\n', encoding="utf-8")
        T.tick(rd)
        self.assertEqual(_status(rd)["runs"]["run-01"]["state"], "running")


class LaunchFailDisplayTests(_Base):
    """FR-21b: the long state name is abbreviated (no column overflow) and
    the diagnostic hint travels with the table."""

    def test_launch_fail_abbreviated_and_hint_in_table(self):
        rd = self._init(_plan([_entry("t-1")], pool_size=1,
                              launch_grace_minutes=10))
        os.environ["QPB_HARNESS_NOW"] = "1000000"
        T.tick(rd)
        os.environ["QPB_HARNESS_NOW"] = str(1000000 + 11 * 60)
        out = T.tick(rd)
        tbl = out["status_table"]
        self.assertIn("LAUNCH-FAIL", tbl)
        self.assertNotIn("auth_or_launch_failed", tbl)  # abbreviated in display
        self.assertIn("check worker-side launch", tbl)   # FR-21b hint
        # the synthesized result record carries the actionable hint too
        rec = json.loads((rd / "results" / "result-00001.json").read_text())
        self.assertIn("check worker-side launch", rec["summary"])

    def test_table_columns_do_not_overflow(self):
        rd = self._init(_plan([_entry("t-1")], pool_size=1,
                              launch_grace_minutes=10))
        os.environ["QPB_HARNESS_NOW"] = "1000000"
        T.tick(rd)
        os.environ["QPB_HARNESS_NOW"] = str(1000000 + 11 * 60)
        out = T.tick(rd)
        # the data row's STATE field is bounded — find the run-01 row and
        # assert the abbreviated state sits in its 13-wide column.
        for ln in out["status_table"].splitlines():
            if ln.startswith("1 "):  # run-01 → name[4:] == "1"
                # MODE starts at col 35 (5+22+8); STATE at col 35..48.
                self.assertLessEqual(len(ln.split()[3]), 12)
                break


if __name__ == "__main__":
    unittest.main()
