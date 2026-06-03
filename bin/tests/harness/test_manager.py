"""v1.5.7 094 — manager daemon tests (segregated harness suite).

Covers ``bin/harness/manager.py``:

  PidFileTests — claim, heartbeat update, release; another live
    PID in the pid file raises ManagerError; stale (dead-PID)
    files are silently replaced.
  CommandsConsumeTests — commands.jsonl consumed in order;
    cursor persists so a restart doesn't re-run; malformed JSON
    lines skipped without crashing.
  CommandHandlingTests — enqueue/cancel/pause/resume routed
    through the scheduler.
  CrashRecoveryTests — `recover_orphaned_runs` rewrites
    RUNNING+dead-PID+no-terminal status files to
    `terminal_state=FAILED` with the `orphan_recovery` note;
    LEAVES live-PID + already-terminal entries ALONE.
  SnapshotTests — snapshot is JSON-serializable; carries
    scheduler state + in-flight metadata + recent-done buffer.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from bin.harness import manager as M
from bin.harness import scheduler as SCH
from bin.harness.schema import Runner, TerminalState


# ---------------------------------------------------------------------------
# PID file management
# ---------------------------------------------------------------------------


class PidFileTests(unittest.TestCase):

    def test_claim_writes_pid_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            paths = M.ControlPaths(root=Path(td))
            paths.ensure()
            M.claim_pid_file(paths, my_pid=os.getpid())
            self.assertTrue(paths.pid_file.is_file())
            data = json.loads(paths.pid_file.read_text())
            self.assertEqual(data["pid"], os.getpid())
            self.assertIn("started_at", data)
            self.assertIn("heartbeat", data)

    def test_claim_rejects_existing_live_pid(self) -> None:
        """A live PID in manager.pid → ManagerError. Defends
        against two managers running simultaneously."""
        with tempfile.TemporaryDirectory() as td:
            paths = M.ControlPaths(root=Path(td))
            paths.ensure()
            paths.pid_file.write_text(json.dumps({
                "pid": os.getpid(), "started_at": "x",
                "heartbeat": "x",
            }))
            with self.assertRaises(M.ManagerError) as ctx:
                M.claim_pid_file(paths, my_pid=os.getpid())
            self.assertIn("another manager", str(ctx.exception))

    def test_claim_overwrites_stale_pid(self) -> None:
        """A dead PID (e.g. a crashed previous manager) is
        silently overwritten — this is the load-bearing
        restart path."""
        with tempfile.TemporaryDirectory() as td:
            paths = M.ControlPaths(root=Path(td))
            paths.ensure()
            # PID 999999 is essentially guaranteed to be dead.
            paths.pid_file.write_text(json.dumps({
                "pid": 999999, "started_at": "x", "heartbeat": "x",
            }))
            # Should NOT raise.
            M.claim_pid_file(paths, my_pid=os.getpid())
            data = json.loads(paths.pid_file.read_text())
            self.assertEqual(data["pid"], os.getpid())

    def test_claim_overwrites_corrupt_pid_file(self) -> None:
        """A malformed pid file is silently overwritten — no
        crash on corrupt state."""
        with tempfile.TemporaryDirectory() as td:
            paths = M.ControlPaths(root=Path(td))
            paths.ensure()
            paths.pid_file.write_text("not json")
            M.claim_pid_file(paths, my_pid=os.getpid())
            data = json.loads(paths.pid_file.read_text())
            self.assertEqual(data["pid"], os.getpid())

    def test_heartbeat_updates_in_place(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            paths = M.ControlPaths(root=Path(td))
            paths.ensure()
            M.claim_pid_file(paths, my_pid=os.getpid())
            d1 = json.loads(paths.pid_file.read_text())
            # Force a different timestamp by waiting a fraction.
            import time
            time.sleep(1.1)
            M.update_heartbeat(paths)
            d2 = json.loads(paths.pid_file.read_text())
            self.assertEqual(d1["pid"], d2["pid"])
            self.assertNotEqual(d1["heartbeat"], d2["heartbeat"])

    def test_release_removes_pid_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            paths = M.ControlPaths(root=Path(td))
            paths.ensure()
            M.claim_pid_file(paths, my_pid=os.getpid())
            M.release_pid_file(paths)
            self.assertFalse(paths.pid_file.is_file())


# ---------------------------------------------------------------------------
# Commands.jsonl consumption
# ---------------------------------------------------------------------------


class CommandsConsumeTests(unittest.TestCase):

    def _write_cmds(self, paths, lines):
        paths.commands_file.write_text("\n".join(lines) + "\n")

    def test_reads_commands_advances_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            paths = M.ControlPaths(root=Path(td))
            paths.ensure()
            self._write_cmds(paths, [
                json.dumps({"command": "pause"}),
                json.dumps({"command": "enqueue",
                              "args": {"run_id": "r1",
                                        "runner": "claude"}}),
            ])
            cmds = M.read_pending_commands(paths)
            self.assertEqual(len(cmds), 2)
            self.assertEqual(cmds[0]["command"], "pause")
            self.assertEqual(cmds[1]["command"], "enqueue")
            # Second call returns empty — cursor advanced.
            cmds2 = M.read_pending_commands(paths)
            self.assertEqual(cmds2, [])

    def test_cursor_persists_across_restart(self) -> None:
        """A simulated restart (drop in-memory state, call
        `read_pending_commands` again) should resume from the
        persisted cursor, NOT re-process the queue."""
        with tempfile.TemporaryDirectory() as td:
            paths = M.ControlPaths(root=Path(td))
            paths.ensure()
            self._write_cmds(paths, [
                json.dumps({"command": "pause"}),
            ])
            cmds1 = M.read_pending_commands(paths)
            self.assertEqual(len(cmds1), 1)
            # Simulate restart: new ControlPaths instance.
            paths2 = M.ControlPaths(root=Path(td))
            cmds2 = M.read_pending_commands(paths2)
            self.assertEqual(cmds2, [])

    def test_appended_commands_picked_up(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            paths = M.ControlPaths(root=Path(td))
            paths.ensure()
            self._write_cmds(paths, [
                json.dumps({"command": "pause"}),
            ])
            M.read_pending_commands(paths)
            # Append a new command.
            with open(paths.commands_file, "a") as f:
                f.write(json.dumps({"command": "resume"}) + "\n")
            cmds = M.read_pending_commands(paths)
            self.assertEqual(len(cmds), 1)
            self.assertEqual(cmds[0]["command"], "resume")

    def test_malformed_lines_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            paths = M.ControlPaths(root=Path(td))
            paths.ensure()
            self._write_cmds(paths, [
                "this is not json",
                json.dumps({"command": "pause"}),
                json.dumps({"not_a_command": "x"}),  # missing key
            ])
            cmds = M.read_pending_commands(paths)
            # Only the well-formed pause survives.
            self.assertEqual(len(cmds), 1)
            self.assertEqual(cmds[0]["command"], "pause")


# ---------------------------------------------------------------------------
# Command handling (manager → scheduler)
# ---------------------------------------------------------------------------


class CommandHandlingTests(unittest.TestCase):

    def _write_cmds(self, paths, *cmds) -> None:
        paths.commands_file.write_text(
            "\n".join(json.dumps(c) for c in cmds) + "\n",
        )

    def test_enqueue_routes_to_scheduler(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr = M.Manager(root=Path(td))
            mgr.paths.ensure()
            self._write_cmds(
                mgr.paths,
                {"command": "enqueue",
                 "args": {"run_id": "r1", "runner": "claude"}},
                {"command": "enqueue",
                 "args": {"run_id": "r2", "runner": "codex"}},
            )
            mgr.consume_commands()
            self.assertEqual(mgr.scheduler.queue_length(), 2)
            # And the vendor routing is correct.
            snap = mgr.scheduler.snapshot()
            vendors = {e["vendor"] for e in snap["queued"]}
            self.assertEqual(vendors, {"anthropic", "openai"})

    def test_cancel_removes_from_queue(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr = M.Manager(root=Path(td))
            mgr.paths.ensure()
            self._write_cmds(
                mgr.paths,
                {"command": "enqueue",
                 "args": {"run_id": "r1", "runner": "claude"}},
                {"command": "cancel", "args": {"run_id": "r1"}},
            )
            mgr.consume_commands()
            self.assertEqual(mgr.scheduler.queue_length(), 0)

    def test_pause_and_resume(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr = M.Manager(root=Path(td))
            mgr.paths.ensure()
            self._write_cmds(
                mgr.paths,
                {"command": "pause"},
            )
            mgr.consume_commands()
            self.assertTrue(mgr.paused)
            # Append a resume.
            with open(mgr.paths.commands_file, "a") as f:
                f.write(json.dumps({"command": "resume"}) + "\n")
            mgr.consume_commands()
            self.assertFalse(mgr.paused)

    def test_enqueue_bad_runner_ignored(self) -> None:
        """An enqueue with an unknown runner name is silently
        ignored — the manager doesn't crash on TUI typos."""
        with tempfile.TemporaryDirectory() as td:
            mgr = M.Manager(root=Path(td))
            mgr.paths.ensure()
            self._write_cmds(
                mgr.paths,
                {"command": "enqueue",
                 "args": {"run_id": "r1", "runner": "notarunner"}},
            )
            mgr.consume_commands()
            self.assertEqual(mgr.scheduler.queue_length(), 0)


# ---------------------------------------------------------------------------
# Crash recovery (RUNNING + dead PID + no terminal → FAILED orphaned)
# ---------------------------------------------------------------------------


class CrashRecoveryTests(unittest.TestCase):
    """The load-bearing manager-restart pin per SCHEMA.md §6."""

    def _write_status(self, runs_dir: Path, run_id: str,
                       **fields) -> Path:
        run_dir = runs_dir / "ACC-T" / run_id
        run_dir.mkdir(parents=True)
        status = run_dir / "status.json"
        defaults = {
            "state": "RUNNING",
            "pid": 999999,  # essentially-guaranteed-dead PID
            "started_at": "2026-05-25T12:00:00Z",
            "heartbeat": "2026-05-25T12:01:00Z",
            "exit_code": None,
            "terminal_state": None,
        }
        defaults.update(fields)
        status.write_text(json.dumps(defaults, indent=2))
        return status

    def test_recovers_orphan_RUNNING_dead_PID(self) -> None:
        """v1.5.7 094 LOAD-BEARING PIN: RUNNING + dead PID + no
        terminal → FAILED with orphan_recovery note.

        Mutation bite: drop the orphan rewrite branch → this
        test FAILs because the orphan stays in state=RUNNING
        forever (the manager would never re-attempt or grade it).
        """
        with tempfile.TemporaryDirectory() as td:
            runs = Path(td)
            self._write_status(runs, "20260525T120000Z")
            recovered = M.recover_orphaned_runs(runs)
            self.assertEqual(len(recovered), 1)
            self.assertEqual(recovered[0], "20260525T120000Z")
            # The status file is rewritten.
            status = json.loads(
                (runs / "ACC-T" / "20260525T120000Z"
                 / "status.json").read_text(encoding="utf-8")
            )
            self.assertEqual(status["state"], "DONE")
            self.assertEqual(
                status["terminal_state"],
                TerminalState.FAILED.value,
            )
            self.assertIn("orphan_recovery", status)
            self.assertIn("dead PID", status["orphan_recovery"]["reason"])

    def test_LEAVES_live_PID_alone(self) -> None:
        """A run with a LIVE PID is NOT recovered — that's a
        legitimately in-flight run (e.g. the manager restart
        was fast)."""
        with tempfile.TemporaryDirectory() as td:
            runs = Path(td)
            self._write_status(runs, "20260525T120000Z",
                                 pid=os.getpid())
            recovered = M.recover_orphaned_runs(runs)
            self.assertEqual(recovered, [])
            # Status file unchanged.
            status = json.loads(
                (runs / "ACC-T" / "20260525T120000Z"
                 / "status.json").read_text(encoding="utf-8")
            )
            self.assertEqual(status["state"], "RUNNING")
            self.assertIsNone(status["terminal_state"])

    def test_LEAVES_already_terminal_alone(self) -> None:
        """A run with a non-None terminal_state is NOT touched
        even if its PID happens to be dead — it's already
        graded (or otherwise complete)."""
        with tempfile.TemporaryDirectory() as td:
            runs = Path(td)
            self._write_status(
                runs, "20260525T120000Z", state="DONE",
                terminal_state="COMPLETED", pid=999999,
            )
            recovered = M.recover_orphaned_runs(runs)
            self.assertEqual(recovered, [])
            status = json.loads(
                (runs / "ACC-T" / "20260525T120000Z"
                 / "status.json").read_text(encoding="utf-8")
            )
            self.assertEqual(status["terminal_state"], "COMPLETED")

    def test_handles_corrupt_status_files_without_crashing(
            self) -> None:
        """A malformed status.json is silently skipped — the
        manager doesn't crash recovering a corrupt receipt."""
        with tempfile.TemporaryDirectory() as td:
            runs = Path(td)
            bad = runs / "ACC-T" / "20260525T120000Z"
            bad.mkdir(parents=True)
            (bad / "status.json").write_text("not json")
            recovered = M.recover_orphaned_runs(runs)
            self.assertEqual(recovered, [])

    def test_missing_runs_dir_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            recovered = M.recover_orphaned_runs(
                Path(td) / "nonexistent_runs",
            )
            self.assertEqual(recovered, [])

    def test_manager_start_recovers_orphans(self) -> None:
        """End-to-end: Manager.start() invokes
        recover_orphaned_runs and records the recovered set in
        recent_done so the TUI surfaces it."""
        with tempfile.TemporaryDirectory() as td:
            mgr = M.Manager(root=Path(td))
            mgr.paths.ensure()
            self._write_status(mgr.paths.runs_dir,
                                 "20260525T120000Z")
            mgr.start()
            try:
                self.assertGreater(len(mgr._recent_done), 0)
                self.assertEqual(
                    mgr._recent_done[0]["outcome"],
                    "FAILED (orphaned)",
                )
            finally:
                mgr.shutdown()


# ---------------------------------------------------------------------------
# Manager snapshot
# ---------------------------------------------------------------------------


class SnapshotTests(unittest.TestCase):

    def test_snapshot_json_serializable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr = M.Manager(root=Path(td))
            mgr.paths.ensure()
            mgr.start()
            try:
                snap = mgr.snapshot()
                json.dumps(snap)  # raises if not serializable
                self.assertIn("scheduler", snap)
                self.assertIn("in_flight", snap)
                self.assertIn("recent_done", snap)
                self.assertEqual(snap["pid"], os.getpid())
                self.assertFalse(snap["paused"])
            finally:
                mgr.shutdown()

    def test_write_queue_snapshot_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            mgr = M.Manager(root=Path(td))
            mgr.paths.ensure()
            mgr.start()
            try:
                mgr.write_queue_snapshot()
                self.assertTrue(mgr.paths.queue_snapshot_file.is_file())
                data = json.loads(
                    mgr.paths.queue_snapshot_file.read_text(
                        encoding="utf-8",
                    ),
                )
                self.assertIn("scheduler", data)
            finally:
                mgr.shutdown()


if __name__ == "__main__":
    unittest.main()
