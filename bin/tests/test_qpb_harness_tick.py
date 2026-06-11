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


if __name__ == "__main__":
    unittest.main()
