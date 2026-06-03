"""QPB Test Harness — manager daemon (Phase 4).

═══════════════════════════════════════════════════════════════
 TWO FLOWS, ONE HARNESS — read this before reasoning about
 concurrency, because it's an easy place to get confused.
═══════════════════════════════════════════════════════════════

This file is the entry point for the ``qpb_harness manager``
subcommand: a queued-daemon execution flow with command files,
queue snapshots, atomic-rename state writes, and orphan
recovery. Concurrency in THIS flow is governed by
``scheduler.py``'s config object (a per-daemon, in-process
mechanism). The single-daemon-per-folder constraint is enforced
via the ``control/manager.pid`` claim with a cross-platform
liveness check (``_platform.pid_alive``; pre-184 used the
POSIX signal-0 idiom which is broken on Windows).

For the **other** flow — the ``qpb_harness run-plan``
subcommand, which is one-shot detached spawn with a background
collector — see ``plan_runner.py``. That flow's concurrency is
per-plan via the ``pools`` field in the plan JSON +
``.manifest.lock`` (v1.5.7 174). Pre-174 the file-backed
``inflight_registry.py`` provided cross-plan global caps; that
module was deleted along with the pid=0 reservation model.
Operators who want to coordinate multiple ``run-plan``
invocations are expected to run one plan at a time.

The two flows DO NOT share concurrency state. A reviewer
inspecting ``scheduler.py`` alone might conclude "the
concurrency cap is per-daemon"; that is true OF THIS FLOW ONLY.
═══════════════════════════════════════════════════════════════

Owns queue + execution per design "Manager daemon + TUI":

  * Writes ``control/manager.pid`` + heartbeat so the TUI (and
    a restart-protection check) know whether a daemon is live.
  * Consumes ``control/commands.jsonl`` for enqueue / cancel /
    reorder / pause / resume / review commands written by the
    TUI (or an external tool).
  * For each ready run: prepare → launch → extract facts →
    grade → write receipts. Uses ``scheduler.next_ready()``
    for cap/cooldown discipline; the scheduler is a pure state
    object (Phase 3) so the manager is the only place that
    actually spawns subprocesses.
  * **Crash recovery**: on restart, scans
    ``runs/*/*/status.json`` for entries left in state=RUNNING
    whose PID is no longer alive AND no terminal_state was
    written → marks them ``FAILED (orphaned)`` per the design doc
    §6.

The manager is intentionally a SINGLE-THREADED POLL LOOP — N
runs can be in-flight concurrently (via the scheduler's per-
vendor + global caps) because each ``runner.launch_run`` returns
only after the subprocess terminates. To run N truly concurrent
subprocesses, an operator would extend the manager with a worker
pool; for Phase 4 the cap-respecting single-loop is the
minimum that demonstrates the queue + recovery + control-file
contract.

CONTROL FILES (under ``repos/security-test-cases/control/``):

  * ``manager.pid``      — JSON ``{"pid": int, "started_at":
                            iso, "heartbeat": iso}``.
  * ``commands.jsonl``   — append-only NDJSON; each line a
                            command dict ``{"command":
                            "enqueue"/"cancel"/.../"shutdown",
                            "args": {...}}``. The manager
                            tracks a high-water cursor so it
                            doesn't re-process commands.
  * ``queue.json``       — current queue snapshot for the TUI
                            (rebuildable from scheduler.snapshot()).
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from bin.harness.schema import (
    CaseType,
    Runner,
    RunState,
    TerminalState,
)
from bin.harness.scheduler import (
    Scheduler,
    SchedulerConfig,
    Vendor,
    config_from_dict,
    vendor_for_runner,
)


# ---------------------------------------------------------------------------
# Exceptions / dataclasses
# ---------------------------------------------------------------------------


class ManagerError(RuntimeError):
    """Manager could not initialise (e.g. a live PID is already
    in the pid file, or the control dir can't be created)."""


@dataclass
class ManagerState:
    """Snapshot of the manager's live state for the TUI / tests."""
    pid: int
    started_at: str
    heartbeat: str
    paused: bool
    queue: list  # list of {"run_id", "vendor", ...}
    in_flight: list  # list of {"run_id", "case_id", "started_at", ...}
    recent_done: list  # list of recently-completed runs


# ---------------------------------------------------------------------------
# Time / PID helpers
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# v1.5.7 184 FINDING-23: consolidated to _platform.pid_alive.
# Pre-184 the local body used the POSIX signal-0 probe which
# is broken on Windows for the reasons FINDING-20 documented
# in plan_runner. Same FINDING-18 alias pattern; symbol
# preserved so the manager's existing call sites work
# unchanged.
from bin.harness._platform import (
    pid_alive as _pid_alive,
)


# ---------------------------------------------------------------------------
# Control directory layout
# ---------------------------------------------------------------------------


@dataclass
class ControlPaths:
    """Resolves the per-control-dir paths the manager reads/writes.
    The runner-root convention is
    ``repos/security-test-cases/`` per the design's folder
    layout — the operator can override for tests."""
    root: Path

    @property
    def control_dir(self) -> Path:
        return self.root / "control"

    @property
    def pid_file(self) -> Path:
        return self.control_dir / "manager.pid"

    @property
    def commands_file(self) -> Path:
        return self.control_dir / "commands.jsonl"

    @property
    def commands_cursor_file(self) -> Path:
        """Tracks how many lines of commands.jsonl the manager
        has consumed (so a restart picks up where it left off,
        not re-runs the queue)."""
        return self.control_dir / "commands.cursor"

    @property
    def queue_snapshot_file(self) -> Path:
        return self.control_dir / "queue.json"

    @property
    def runs_dir(self) -> Path:
        return self.root / "runs"

    def ensure(self) -> None:
        self.control_dir.mkdir(parents=True, exist_ok=True)
        self.runs_dir.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Crash recovery
# ---------------------------------------------------------------------------


def recover_orphaned_runs(runs_dir: Path) -> list:
    """Scan every ``status.json`` under ``runs_dir`` and find
    entries whose state is RUNNING but whose PID is no longer
    alive AND no terminal_state was written. Rewrite the
    status to ``terminal_state=FAILED`` with the
    ``reason="orphaned"`` note per design §6.

    Returns the list of recovered run_ids — used by the manager's
    boot log + by tests.

    Defensive: a status.json that's missing required fields is
    LEFT ALONE (we don't rewrite ambiguous state into a
    terminal). A run with the PID still alive is left alone.
    """
    recovered: list[str] = []
    if not runs_dir.is_dir():
        return recovered
    for status_path in sorted(runs_dir.rglob("status.json")):
        try:
            data = json.loads(status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        # design §6: the orphan signature is state=RUNNING +
        # terminal_state=None + PID dead.
        if data.get("terminal_state") is not None:
            continue
        if data.get("state") != "RUNNING":
            continue
        pid = data.get("pid")
        if not isinstance(pid, int):
            continue
        if _pid_alive(pid):
            continue
        # All checks passed — this is an orphan. Rewrite.
        data["state"] = "DONE"
        data["terminal_state"] = TerminalState.FAILED.value
        data["exit_code"] = data.get("exit_code") or -1
        data["heartbeat"] = _utc_now_iso()
        data["orphan_recovery"] = {
            "recovered_at": _utc_now_iso(),
            "reason": "manager restart: RUNNING + dead PID + no terminal",
        }
        try:
            tmp = status_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(data, indent=2) + "\n",
                            encoding="utf-8")
            os.replace(tmp, status_path)
            recovered.append(status_path.parent.name)
        except OSError:
            continue
    return recovered


# ---------------------------------------------------------------------------
# Command file consumption
# ---------------------------------------------------------------------------


def read_pending_commands(paths: ControlPaths) -> list:
    """Read commands.jsonl from the persisted cursor onward and
    return the new commands. Advances the cursor as a side-effect
    so subsequent calls don't re-process them.

    Returns a list of dicts (one per command). Malformed JSON
    lines are skipped (logged conceptually; we don't crash on a
    bad TUI write).
    """
    if not paths.commands_file.is_file():
        return []
    # Resume from the persisted cursor (line count consumed so
    # far). A missing cursor file means "start at 0".
    cursor = 0
    if paths.commands_cursor_file.is_file():
        try:
            cursor = int(paths.commands_cursor_file.read_text(
                encoding="utf-8",
            ).strip() or "0")
        except (OSError, ValueError):
            cursor = 0
    new_commands: list = []
    new_cursor = cursor
    try:
        lines = paths.commands_file.read_text(
            encoding="utf-8",
        ).splitlines()
    except OSError:
        return []
    for i, line in enumerate(lines):
        if i < cursor:
            continue
        line = line.strip()
        if not line:
            new_cursor = i + 1
            continue
        try:
            cmd = json.loads(line)
            if isinstance(cmd, dict) and "command" in cmd:
                new_commands.append(cmd)
        except json.JSONDecodeError:
            pass
        new_cursor = i + 1
    # Persist cursor.
    try:
        paths.commands_cursor_file.write_text(
            str(new_cursor) + "\n", encoding="utf-8",
        )
    except OSError:
        pass
    return new_commands


# ---------------------------------------------------------------------------
# PID file management
# ---------------------------------------------------------------------------


def claim_pid_file(paths: ControlPaths, my_pid: int) -> None:
    """Atomically claim the manager.pid file. Raises
    ``ManagerError`` if an existing pid file points at a LIVE
    process (another manager is running). A stale pid file
    (pointing at a dead process) is silently replaced — this is
    the after-crash startup path.
    """
    paths.ensure()
    if paths.pid_file.is_file():
        try:
            existing = json.loads(
                paths.pid_file.read_text(encoding="utf-8"),
            )
            existing_pid = existing.get("pid")
            if isinstance(existing_pid, int) and _pid_alive(existing_pid):
                raise ManagerError(
                    f"manager.pid points at live PID "
                    f"{existing_pid}: another manager is running"
                )
        except (json.JSONDecodeError, OSError):
            # Corrupt pid file — overwrite.
            pass
    now = _utc_now_iso()
    tmp = paths.pid_file.with_suffix(".pid.tmp")
    tmp.write_text(json.dumps({
        "pid": my_pid,
        "started_at": now,
        "heartbeat": now,
    }, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, paths.pid_file)


def update_heartbeat(paths: ControlPaths) -> None:
    """Refresh the heartbeat in manager.pid. Defensive — never
    crashes if the file is missing or partially-written."""
    if not paths.pid_file.is_file():
        return
    try:
        data = json.loads(paths.pid_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    data["heartbeat"] = _utc_now_iso()
    try:
        tmp = paths.pid_file.with_suffix(".pid.tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n",
                        encoding="utf-8")
        os.replace(tmp, paths.pid_file)
    except OSError:
        pass


def release_pid_file(paths: ControlPaths) -> None:
    """Remove the pid file on clean shutdown."""
    try:
        paths.pid_file.unlink(missing_ok=True)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------


class Manager:
    """Single-process manager. The Phase 4 deliverable's primary
    user is the operator running ``python3 -m bin.qpb_harness
    manager start``; tests drive the manager via its individual
    helper methods (init, tick, recover) so the daemon loop
    doesn't have to be exercised end-to-end."""

    def __init__(self, root: Path,
                 config: "SchedulerConfig | None" = None) -> None:
        self.paths = ControlPaths(root=root)
        self.scheduler = Scheduler(config=config)
        self.paused: bool = False
        # Recently-completed runs (for the TUI overview;
        # bounded so a long session doesn't grow without bound).
        self._recent_done: list = []
        self._recent_done_max: int = 50
        self._my_pid: "int | None" = None
        # State tracking for the manager's view of in-flight
        # runs (the scheduler tracks the count; the manager
        # tracks the case_id + started_at).
        self._in_flight_meta: "dict[str, dict]" = {}

    # --- lifecycle ---------------------------------------------------

    def start(self) -> None:
        """Claim the pid file, recover orphans, ready to tick."""
        self._my_pid = os.getpid()
        claim_pid_file(self.paths, self._my_pid)
        recovered = recover_orphaned_runs(self.paths.runs_dir)
        for run_id in recovered:
            self._recent_done.append({
                "run_id": run_id, "outcome": "FAILED (orphaned)",
                "recovered_at": _utc_now_iso(),
            })

    def shutdown(self) -> None:
        release_pid_file(self.paths)

    # --- command handling -------------------------------------------

    def consume_commands(self) -> None:
        """Pull pending commands off commands.jsonl and apply
        them. Each command is a dict with ``"command"`` +
        ``"args"`` keys.

        Supported commands (Phase 4 minimum):
          enqueue   args: {"run_id": str, "runner": str,
                            "case_id": str (recorded only;
                            execution uses the scheduler)}
          cancel    args: {"run_id": str} — removes from queue.
                            (In-flight cancellation is a Phase
                            5 manager-pool extension.)
          pause     args: {} — stop starting new runs (in-flight
                            keep running).
          resume    args: {}
          shutdown  args: {} — clean exit on next tick.
        """
        for cmd in read_pending_commands(self.paths):
            name = cmd.get("command")
            args = cmd.get("args") or {}
            if name == "enqueue":
                run_id = args.get("run_id")
                runner_name = args.get("runner")
                if not run_id or not runner_name:
                    continue
                try:
                    runner = Runner(runner_name)
                    vendor = vendor_for_runner(runner)
                    self.scheduler.enqueue(run_id, vendor)
                except (ValueError, KeyError):
                    continue
            elif name == "cancel":
                run_id = args.get("run_id")
                if not run_id:
                    continue
                # Remove from queue if queued. We don't yet
                # support cancelling in-flight runs.
                queue = self.scheduler._queue
                for i, entry in enumerate(list(queue)):
                    if entry.run_id == run_id:
                        queue.pop(i)
                        break
            elif name == "pause":
                self.paused = True
            elif name == "resume":
                self.paused = False
            elif name == "shutdown":
                self._shutdown_requested = True

    # --- state snapshot ---------------------------------------------

    def snapshot(self) -> dict:
        """Return a JSON-serializable manager-state snapshot for
        the TUI."""
        return {
            "pid": self._my_pid,
            "paused": self.paused,
            "started_at": (
                json.loads(self.paths.pid_file.read_text(
                    encoding="utf-8",
                )).get("started_at")
                if self.paths.pid_file.is_file() else None
            ),
            "heartbeat": _utc_now_iso(),
            "scheduler": self.scheduler.snapshot(),
            "in_flight": list(self._in_flight_meta.values()),
            "recent_done": list(self._recent_done[-self._recent_done_max:]),
        }

    def write_queue_snapshot(self) -> None:
        """Persist the snapshot to ``control/queue.json`` so the
        TUI can read it without IPC."""
        try:
            tmp = self.paths.queue_snapshot_file.with_suffix(
                ".json.tmp",
            )
            tmp.write_text(
                json.dumps(self.snapshot(), indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(tmp, self.paths.queue_snapshot_file)
        except OSError:
            pass


__all__ = [
    "ManagerError",
    "ManagerState",
    "ControlPaths",
    "Manager",
    "recover_orphaned_runs",
    "read_pending_commands",
    "claim_pid_file",
    "update_heartbeat",
    "release_pid_file",
]
