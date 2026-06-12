#!/usr/bin/env python3
"""harness_demo_worker — cross-platform demo/stub worker (v1.5.9 Phase 2B).

The payload-agnostic stub the example plan dispatches (FR-31 / UC-8 demo;
replaces the bash stub so the demo runs identically on Windows, macOS, and
Linux — NFR-1). It does NO real work: it walks the heartbeat lifecycle
STARTING -> IN_PROGRESS xN -> COMPLETED, sleeping between pings, so an
operator watching the status table sees pool-limited dispatch, genuine
idle ticks, staggered dispatch, and a clean reap — the architecture
demonstrated with zero API spend.

Reads its identity from the absolute-path block the harness substitutes
(env HARNESS_HEARTBEAT_PATH / HARNESS_TASK_ID / HARNESS_RUN_DIR, or the QPB
aliases, or --flags). Emits via the generic harness_heartbeat helper
(imported from the same directory). Honours E6: if a heartbeat write
fails, it aborts loudly with a FAILED terminal rather than looking healthy.

Usage (the plan's worker_cmd / worker_prompt fills the absolute paths):
  python3 harness_demo_worker.py \\
      --heartbeat-path <abs>/run-NN/heartbeat.ndjson --task-id <id> \\
      --run-dir <abs>/run-NN [--steps 4] [--sleep 150]

Stdlib only. ASCII-safe.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import time
from pathlib import Path


def _load_heartbeat():
    """Import the sibling generic heartbeat helper by path (works whether or
    not bin/ is on sys.path)."""
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(
        "_harness_heartbeat_demo", here / "harness_heartbeat.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_harness_heartbeat_demo"] = mod
    spec.loader.exec_module(mod)
    return mod


def _env(*names):
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="harness_demo_worker",
                                 description=__doc__.split("\n")[0])
    ap.add_argument("--heartbeat-path", default=None)
    ap.add_argument("--task-id", default=None)
    ap.add_argument("--run-dir", default=None)
    ap.add_argument("--phase", default="demo")
    ap.add_argument("--steps", type=int, default=4)
    ap.add_argument("--sleep", type=float, default=150.0)
    args = ap.parse_args(list(sys.argv[1:] if argv is None else argv))

    hb_path = args.heartbeat_path or _env(
        "HARNESS_HEARTBEAT_PATH", "QPB_HEARTBEAT_PATH")
    task_id = args.task_id or _env("HARNESS_TASK_ID", "QPB_TASK_ID")
    run_dir = args.run_dir or _env("HARNESS_RUN_DIR", "QPB_RUN_DIR")
    if not hb_path or not task_id:
        print("harness_demo_worker: need --heartbeat-path and --task-id "
              "(or the env block)", file=sys.stderr)
        return 2

    hb = Path(hb_path)
    H = _load_heartbeat()

    def emit(step, status, message=None):
        obj = H.build_progress(phase=args.phase, task_id=task_id, step=step,
                               status=status, message=message)
        try:
            H.append_line(hb, obj)
        except (OSError, ValueError) as exc:
            # E6: abort loudly with a FAILED terminal, then exit nonzero.
            print(f"harness_demo_worker: heartbeat write failed ({exc}); "
                  f"aborting with FAILED.", file=sys.stderr)
            try:
                H.append_line(hb, H.build_terminal(
                    task_id=task_id, status="FAILED",
                    result_file="", summary="heartbeat write failure (E6)"))
            except Exception:
                pass
            sys.exit(5)

    emit("start", "STARTING")
    for i in range(1, max(1, args.steps) + 1):
        time.sleep(max(0.0, args.sleep))
        emit(f"work-{i}", "IN_PROGRESS")
    time.sleep(max(0.0, args.sleep))

    result_file = ""
    if run_dir:
        rf = Path(run_dir) / "result.txt"
        try:
            rf.write_text(f"demo worker {task_id} completed\n", encoding="utf-8")
            result_file = str(rf)
        except OSError:
            result_file = ""
    try:
        H.append_line(hb, H.build_terminal(
            task_id=task_id, status="COMPLETED",
            result_file=result_file or "(none)",
            summary="demo stub completed"))
    except (OSError, ValueError) as exc:
        print(f"harness_demo_worker: terminal heartbeat write failed ({exc})",
              file=sys.stderr)
        return 5
    return 0


if __name__ == "__main__":
    sys.exit(main())
