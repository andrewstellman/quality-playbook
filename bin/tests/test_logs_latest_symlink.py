"""Regression test for the v1.5.7 Issue 4 fix (chi-surfaced):
quality/logs/latest must track the newest run-id directory, updated
when each run-id directory is created — not only at successful run
completion.

Reproduction (chi-1.5.1): repeated `--phase N` resumes after an
Anthropic-outage interruption left:
    20260514T233845Z   (first run; interrupted)
    20260515T085051Z   (resume attempt)
    20260515T090742Z   (latest active run)
    latest -> 20260515T085051Z   # WRONG (stale)
because `_update_latest_symlink` ran ONLY at successful completion;
an interrupted/aborted run never reached that call so `latest`
pointed at the last run that happened to finish.

Fix: `_update_latest_symlink` is now also called at run-START (after
the run-id directory is created / run_start emitted) in both
`run_one_phased` and `run_one_singlepass`, in addition to the
idempotent completion-time call.

Mutation-test evidence (in-tree per
`ai_context/DEVELOPMENT_PROCESS.md:152-160`; exercised during
instruction 044 development):

- `test_latest_tracks_newest_run_id_after_each_creation`
  Mutation: make `_update_latest_symlink` `return` immediately
  (simulating the pre-fix "only fires at completion, never reached
  on an interrupted run" behavior). Expected failure: the
  `assertEqual(resolved, run_id)` after the 2nd/3rd creation fires
  because `latest` is missing/stale. Restoration: passes. Bite
  verified.
"""

from __future__ import annotations

import argparse
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from bin import run_playbook


class LogsLatestSymlinkTests(unittest.TestCase):
    """Pins the v1.5.7 Issue 4 invariant: after each new run-id
    directory is created and the symlink update fires, quality/logs/
    latest resolves to that newest run-id."""

    def test_latest_tracks_newest_run_id_after_each_creation(self) -> None:
        run_ids = [
            "20260101T000000Z",
            "20260101T010000Z",
            "20260101T020000Z",
        ]
        # Centralized layout (not --logs-flat) and QPB_LOGS_LEGACY unset
        # so _update_latest_symlink is active rather than a no-op.
        args = argparse.Namespace(logs_flat=False)
        with TemporaryDirectory() as tmp, mock.patch.dict(
            os.environ, {}, clear=False
        ):
            os.environ.pop("QPB_LOGS_LEGACY", None)
            repo = Path(tmp)
            logs_root = repo / "quality" / "logs"
            log_file = repo / "runner.log"

            for run_id in run_ids:
                # Simulate the run-id directory being created at
                # run-start, then the symlink update firing.
                (logs_root / run_id).mkdir(parents=True, exist_ok=True)
                run_playbook._update_latest_symlink(
                    repo, run_id, args, log_file
                )

                latest = logs_root / "latest"
                self.assertTrue(
                    latest.is_symlink(),
                    f"quality/logs/latest must be a symlink after "
                    f"creating run-id {run_id}",
                )
                # Relative symlink: its raw target is just the run-id.
                self.assertEqual(
                    os.readlink(latest), run_id,
                    f"quality/logs/latest must point at the newest "
                    f"run-id {run_id}, not a stale prior one",
                )
                self.assertTrue(
                    (latest / "x").parent.resolve()
                    == (logs_root / run_id).resolve(),
                    "resolved latest/ must be the newest run-id dir",
                )

    def test_legacy_mode_is_noop(self) -> None:
        """--logs-flat (legacy layout) has no logs/ tree, so the
        symlink update must be a safe no-op (no crash, no symlink)."""
        args = argparse.Namespace(logs_flat=True)
        with TemporaryDirectory() as tmp:
            repo = Path(tmp)
            run_playbook._update_latest_symlink(
                repo, "20260101T000000Z", args, repo / "runner.log"
            )
            self.assertFalse(
                (repo / "quality" / "logs" / "latest").exists(),
                "legacy mode must not create a logs/latest symlink",
            )


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
