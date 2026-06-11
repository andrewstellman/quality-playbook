#!/usr/bin/env python3
"""Phase 1A spike: minimal deterministic state-machine stepper for the harness skill.

Usage:
    qpb_harness_tick.py --init <plan-path>   # scaffold a run-dir; print its path
    qpb_harness_tick.py <run-dir>            # run one tick; print JSON to stdout

Tick output JSON keys: dispatch_list, status_table, next_tick_minutes, done, stop.

Spike scope only: queued -> claimed -> completed. No stall detection, no failure
subtypes, no Mode 2, pool fixed at 1. Heartbeat reads are substring matches on
the tail per scope note (C) -- no schema validation. Idempotent: re-running a
tick changes nothing except the `cycle` counter (the on-disk witness that a
tick fired). A STOP file at the run-dir root makes the tick read-only: it
reports stop=true and mutates nothing.
"""
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

POOL_SIZE = 1          # one-entry spike plan; pool_size is a Phase 1B concern
TAIL_LINES = 10        # heartbeat tail window per scope note (C)
PLACEHOLDERS = ("HEARTBEAT_PATH", "TASK_ID", "RUN_DIR", "TARGET_REPO")


def _write_json(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def init_run(plan_path):
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    run_dir = Path(__file__).resolve().parent / "harness_runs" / stamp
    for sub in ("queue", "claimed", "results"):
        (run_dir / sub).mkdir(parents=True)
    runs = {}
    for i, entry in enumerate(plan["entries"], start=1):
        run_name, job_id = "run-%02d" % i, "job-%05d" % i
        (run_dir / run_name).mkdir()
        (run_dir / run_name / "heartbeat.ndjson").touch()
        _write_json(run_dir / "queue" / (job_id + ".json"),
                    {"job_id": job_id, "run": run_name, "entry": entry})
        runs[run_name] = {"task_id": entry["task_id"], "job_id": job_id,
                          "target_repo": entry["target_repo"], "state": "queued"}
    _write_json(run_dir / "plan.json", plan)
    _write_json(run_dir / "harness_status.json",
                {"cycle": 0, "counts": {"queued": len(runs), "claimed": 0,
                 "completed": 0}, "done": False, "runs": runs})
    return run_dir


def _tail(run_dir, run_name):
    hb = run_dir / run_name / "heartbeat.ndjson"
    if not hb.exists():
        return []
    return [ln for ln in hb.read_text(encoding="utf-8").splitlines()[-TAIL_LINES:]
            if ln.strip()]


def _hb_view(run_dir, run_name):
    """(last-status-keyword, phase, age) for display -- substring slicing only."""
    lines = _tail(run_dir, run_name)
    if not lines:
        return "-", "-", "-"
    last = lines[-1]
    status = next((s for s in ("COMPLETED", "IN_PROGRESS", "STARTING")
                   if s in last), "-")
    phase = "-"
    if '"phase": "' in last:
        phase = last.split('"phase": "', 1)[1].split('"', 1)[0]
    age = int(time.time() - (run_dir / run_name / "heartbeat.ndjson").stat().st_mtime)
    return status, phase, "%dm%02ds" % (age // 60, age % 60)


def _dispatch_prompt(entry, run_dir, run_name):
    values = {"HEARTBEAT_PATH": str(run_dir / run_name / "heartbeat.ndjson"),
              "TASK_ID": entry["task_id"],
              "RUN_DIR": str(run_dir / run_name),
              "TARGET_REPO": entry["target_repo"]}
    prompt = entry["worker_prompt"]
    for key in PLACEHOLDERS:
        prompt = prompt.replace("{%s}" % key, values[key])
    return prompt


def _table(run_dir, status, plan):
    bar = "-" * 78
    rows = ["Run-Dir: %s (cycle %d)" % (run_dir.name, status["cycle"]), bar,
            "%-5s%-26s%-8s%-11s%-7s%-13s%s" % ("RUN", "REPO", "MODE", "STATE",
                                               "PHASE", "LAST-HB", "HB-AGE")]
    for run_name in sorted(status["runs"]):
        run = status["runs"][run_name]
        hb_status, phase, age = _hb_view(run_dir, run_name)
        rows.append("%-5s%-26s%-8s%-11s%-7s%-13s%s" % (
            run_name[4:], run["target_repo"], "subgnt", run["state"],
            phase, hb_status, age))
    c = status["counts"]
    rows += [bar, "Queue: %d  Claimed: %d  Completed: %d" % (
             c["queued"], c["claimed"], c["completed"]),
             "Next tick in %d min" % plan.get("tick_interval_minutes", 5)]
    return "\n".join(rows)


def tick(run_dir):
    status = json.loads((run_dir / "harness_status.json").read_text(encoding="utf-8"))
    plan = json.loads((run_dir / "plan.json").read_text(encoding="utf-8"))
    stop = (run_dir / "STOP").exists()
    dispatch_list = []
    if not stop:
        entries = {"run-%02d" % i: e
                   for i, e in enumerate(plan["entries"], start=1)}
        for run_name in sorted(status["runs"]):   # reap claimed -> completed
            run = status["runs"][run_name]
            if run["state"] == "claimed" and any(
                    "COMPLETED" in ln for ln in _tail(run_dir, run_name)):
                src = run_dir / "claimed" / (run["job_id"] + ".json")
                if src.exists():                  # idempotency: move once
                    src.replace(run_dir / "results" /
                                (run["job_id"].replace("job-", "result-") + ".json"))
                run["state"] = "completed"
        claimed = sum(1 for r in status["runs"].values() if r["state"] == "claimed")
        for run_name in sorted(status["runs"]):   # dispatch queued -> claimed
            run = status["runs"][run_name]
            if run["state"] == "queued" and claimed < POOL_SIZE:
                src = run_dir / "queue" / (run["job_id"] + ".json")
                if src.exists():                  # idempotency: claim once
                    src.replace(run_dir / "claimed" / (run["job_id"] + ".json"))
                run["state"] = "claimed"
                claimed += 1
                dispatch_list.append({
                    "run": run_name, "task_id": run["task_id"],
                    "worker_prompt": _dispatch_prompt(entries[run_name],
                                                      run_dir, run_name)})
        status["counts"] = {s: sum(1 for r in status["runs"].values()
                                   if r["state"] == s)
                            for s in ("queued", "claimed", "completed")}
        status["done"] = status["counts"]["completed"] == len(status["runs"])
        status["cycle"] += 1
        _write_json(run_dir / "harness_status.json", status)
    return {"dispatch_list": dispatch_list,
            "status_table": _table(run_dir, status, plan),
            "next_tick_minutes": plan.get("tick_interval_minutes", 5),
            "done": status["done"], "stop": stop}


def main(argv):
    if len(argv) == 3 and argv[1] == "--init":
        print(init_run(Path(argv[2]).resolve()))
        return 0
    if len(argv) == 2 and argv[1] != "--init":
        print(json.dumps(tick(Path(argv[1]).resolve()), indent=2))
        return 0
    print(__doc__.strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
