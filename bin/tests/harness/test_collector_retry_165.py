"""v1.5.7 165 — collector retry loop for starved PENDING +
ABANDONED_STARVED deadline. 161 Tasks B+C follow-up.

161 Task A (commit e62ee42 CLOSED) wrote PENDING manifest entries
for runs whose `acquire_run_slot` timed out at the launch barrier.
165 builds on that: the collector now retries PENDING entries on
each invocation. When a slot frees, the collector spawns the worker
via `_launch_one_run_detached` and updates the manifest entry in
place. When a PENDING entry has been starved past
`QPB_HARNESS_PENDING_DEADLINE_S` (default 3600s), it becomes
terminal as `ABANDONED_STARVED` — no more silent forever-PENDING.

Per the 161 Task A REVIEW-RESULT halt ruling, the `artifact_map`
is resolved from `<harness-run>/artifacts/manifest.json` on disk
(the canonical artifact-bundle manifest that `_build_artifacts`
writes at run startup).
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from bin.harness import plan_runner as PR
# v1.5.7 174 Phase 6: inflight_registry deleted; tests now
# mock PR._try_acquire_pool_slot directly.
from bin.harness.schema import (
    InstallChannel, Mode, Runner, TerminalState)


# ---------------------------------------------------------------------------
# TerminalState.ABANDONED_STARVED enum value
# ---------------------------------------------------------------------------


class AbandonedStarvedEnumTests(unittest.TestCase):

    def test_abandoned_starved_enum_value_present(self) -> None:
        self.assertEqual(
            TerminalState.ABANDONED_STARVED.value,
            "ABANDONED_STARVED")


# ---------------------------------------------------------------------------
# _pending_deadline_s helper
# ---------------------------------------------------------------------------


class PendingDeadlineHelperTests(unittest.TestCase):

    def setUp(self) -> None:
        self._prev = os.environ.get(
            "QPB_HARNESS_PENDING_DEADLINE_S")
        os.environ.pop("QPB_HARNESS_PENDING_DEADLINE_S", None)

    def tearDown(self) -> None:
        if self._prev is None:
            os.environ.pop(
                "QPB_HARNESS_PENDING_DEADLINE_S", None)
        else:
            os.environ[
                "QPB_HARNESS_PENDING_DEADLINE_S"] = self._prev

    def test_default_is_3600s(self) -> None:
        self.assertEqual(PR._pending_deadline_s(), 3600.0)

    def test_env_var_overrides_default(self) -> None:
        os.environ["QPB_HARNESS_PENDING_DEADLINE_S"] = "10"
        self.assertEqual(PR._pending_deadline_s(), 10.0)

    def test_non_numeric_falls_back(self) -> None:
        os.environ[
            "QPB_HARNESS_PENDING_DEADLINE_S"] = "not-a-number"
        self.assertEqual(PR._pending_deadline_s(), 3600.0)

    def test_zero_or_negative_falls_back(self) -> None:
        os.environ["QPB_HARNESS_PENDING_DEADLINE_S"] = "0"
        self.assertEqual(PR._pending_deadline_s(), 3600.0)


# ---------------------------------------------------------------------------
# _resolve_artifact_map_from_disk
# ---------------------------------------------------------------------------


class ArtifactMapFromDiskTests(unittest.TestCase):

    def test_returns_dict_when_manifest_present(self) -> None:
        # Per the 161-A halt ruling, the artifact_map is the same
        # shape `_build_artifacts` writes. The 152-evidence
        # directory at harness_runs/20260530T134322Z/artifacts/
        # has the canonical 2-channel shape.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260530T134322Z"
            (hr / "artifacts").mkdir(parents=True)
            (hr / "artifacts" / "manifest.json").write_text(
                json.dumps({
                    "pip-local-wheel": {
                        "path": "/x/quality_playbook.whl",
                        "filename": "quality_playbook.whl",
                        "sha256": "deadbeef",
                    },
                    "npm-local-tgz": {
                        "path": "/x/quality-playbook.tgz",
                        "filename": "quality-playbook.tgz",
                        "sha256": "cafebabe",
                    },
                }), encoding="utf-8")
            am = PR._resolve_artifact_map_from_disk(hr)
            self.assertIn("pip-local-wheel", am)
            self.assertIn("npm-local-tgz", am)

    def test_returns_empty_when_manifest_absent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260530T134322Z"
            hr.mkdir()
            self.assertEqual(
                PR._resolve_artifact_map_from_disk(hr), {})

    def test_returns_empty_when_manifest_unparseable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260530T134322Z"
            (hr / "artifacts").mkdir(parents=True)
            (hr / "artifacts" / "manifest.json").write_text(
                "{not valid json", encoding="utf-8")
            self.assertEqual(
                PR._resolve_artifact_map_from_disk(hr), {})


# ---------------------------------------------------------------------------
# _entry_to_plan_run reconstruction
# ---------------------------------------------------------------------------


class EntryToPlanRunTests(unittest.TestCase):

    def test_reconstructs_plan_run_from_manifest_entry(self) -> None:
        entry = {
            "index": 2,
            "description": "keto-test",
            "repo": "https://github.com/ory/keto",
            "ref": "main",
            "runner": "claude",
            "model": "opus",
            "channel": "pip-local-wheel",
            "mode": "A",
            "expect": {},
        }
        pr = PR._entry_to_plan_run(entry)
        self.assertEqual(pr.index, 2)
        self.assertEqual(pr.runner, Runner.CLAUDE)
        self.assertEqual(pr.model, "opus")
        self.assertEqual(pr.channel, InstallChannel.PIP_LOCAL_WHEEL)


# ---------------------------------------------------------------------------
# _retry_pending_runs_once — Task A retry + Task B deadline
# ---------------------------------------------------------------------------


def _write_manifest(hr: Path, entries: list) -> Path:
    """Helper: write a harness-run manifest."""
    hr.mkdir(parents=True, exist_ok=True)
    mp = hr / "manifest.json"
    mp.write_text(
        json.dumps({
            "harness_run_dir": str(hr),
            "plan": {"pools": {"claude": 1}},
            "runs": entries,
        }, indent=2) + "\n", encoding="utf-8")
    return mp


def _pending_entry(idx: int = 0, **overrides) -> dict:
    entry = {
        "index": idx,
        "description": f"d{idx}",
        "repo": f"https://github.com/x/r{idx}",
        "ref": "main",
        "runner": "claude",
        "model": "opus",
        "channel": "clone",
        "mode": "A",
        "target_dir": f"<hr>/run-{idx:02d}/target",
        "run_dir": f"run-{idx:02d}",
        "run_id": f"r{idx}",
        "pid": None,
        "started_at": "",
        "stream_path": f"<hr>/run-{idx:02d}/stream.ndjson",
        "status_path": f"<hr>/run-{idx:02d}/status.json",
        "max_duration_s": 0.0,
        "expect": {},
        "state": "PENDING",
    }
    entry.update(overrides)
    return entry


class RetryPendingRunsOnceTests(unittest.TestCase):

    def test_no_pending_entries_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260530T134322Z"
            _write_manifest(hr, [{
                "index": 0, "pid": 1, "state": "RUNNING"}])
            self.assertEqual(
                PR._retry_pending_runs_once(hr), 0)

    def test_no_manifest_returns_zero(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260530T134322Z"
            hr.mkdir()
            self.assertEqual(
                PR._retry_pending_runs_once(hr), 0)

    def test_pending_run_starved_again_sets_starved_since(
            self) -> None:
        # v1.5.7 174: pool full ⇒ _try_acquire_pool_slot returns
        # False ⇒ no spawn; entry gets `starved_since` so the
        # deadline clock starts. (Pre-174 used
        # acquire_run_slot+TimeoutError; pool-only model returns
        # False directly.)
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260530T134322Z"
            mp = _write_manifest(hr, [_pending_entry(0)])
            with mock.patch.object(PR, "_try_acquire_pool_slot",
                                    return_value=False):
                transitions = PR._retry_pending_runs_once(hr)
            self.assertEqual(transitions, 0)
            on_disk = json.loads(mp.read_text())
            self.assertIsNotNone(
                on_disk["runs"][0].get("starved_since"))

    def test_pending_run_past_deadline_marked_abandoned_starved(
            self) -> None:
        # LOAD-BEARING (Task B): a PENDING entry whose
        # starved_since is older than the deadline becomes
        # terminal as ABANDONED_STARVED — mutation-bite target.
        # Set deadline very low + use a past starved_since.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260530T134322Z"
            past = (datetime.now(timezone.utc)
                    - timedelta(hours=2)).strftime(
                        "%Y-%m-%dT%H:%M:%SZ")
            mp = _write_manifest(hr, [
                _pending_entry(0, starved_since=past)])
            # Default deadline = 3600s; 2 hours past is well over.
            transitions = PR._retry_pending_runs_once(hr)
            self.assertEqual(transitions, 1)
            on_disk = json.loads(mp.read_text())
            self.assertEqual(
                on_disk["runs"][0]["terminal_state"],
                "ABANDONED_STARVED")
            self.assertIn(
                "deadline",
                on_disk["runs"][0]["terminal_reason"])

    def test_pending_deadline_env_var_overrides_default(
            self) -> None:
        # QPB_HARNESS_PENDING_DEADLINE_S=1 + starved_since 5s ago
        # → past deadline → abandoned.
        prev = os.environ.get("QPB_HARNESS_PENDING_DEADLINE_S")
        os.environ["QPB_HARNESS_PENDING_DEADLINE_S"] = "1"
        try:
            with tempfile.TemporaryDirectory() as td:
                hr = Path(td) / "20260530T134322Z"
                past = (datetime.now(timezone.utc)
                        - timedelta(seconds=5)).strftime(
                            "%Y-%m-%dT%H:%M:%SZ")
                mp = _write_manifest(hr, [
                    _pending_entry(0, starved_since=past)])
                transitions = PR._retry_pending_runs_once(hr)
                self.assertEqual(transitions, 1)
                on_disk = json.loads(mp.read_text())
                self.assertEqual(
                    on_disk["runs"][0]["terminal_state"],
                    "ABANDONED_STARVED")
        finally:
            if prev is None:
                os.environ.pop(
                    "QPB_HARNESS_PENDING_DEADLINE_S", None)
            else:
                os.environ[
                    "QPB_HARNESS_PENDING_DEADLINE_S"] = prev

    def test_pending_run_spawned_when_slot_acquired(self) -> None:
        # LOAD-BEARING (Task A): slot acquired → spawn → manifest
        # entry updated with pid + RUNNING state. Mutation-bite
        # target: removing the spawn branch fails this test.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260530T134322Z"
            mp = _write_manifest(hr, [_pending_entry(0)])
            spawned_entry = {
                "index": 0, "pid": 4242, "state": "RUNNING",
                "runner": "claude", "model": "opus",
                "repo": "https://github.com/x/r0",
            }
            with mock.patch.object(PR, "_try_acquire_pool_slot",
                                    return_value=True), \
                 mock.patch.object(PR,
                                    "_launch_one_run_detached",
                                    return_value=spawned_entry):
                transitions = PR._retry_pending_runs_once(hr)
            self.assertEqual(transitions, 1)
            on_disk = json.loads(mp.read_text())
            self.assertEqual(on_disk["runs"][0]["pid"], 4242)
            self.assertEqual(
                on_disk["runs"][0]["state"], "RUNNING")

    def test_launch_failure_marks_entry_terminal_failed(
            self) -> None:
        # v1.5.7 174: launch fails after slot acquisition →
        # _finalize_pool_slot_failed marks entry DONE+FAILED.
        with tempfile.TemporaryDirectory() as td:
            hr = Path(td) / "20260530T134322Z"
            mp = _write_manifest(hr, [_pending_entry(0)])
            with mock.patch.object(PR, "_try_acquire_pool_slot",
                                    return_value=True), \
                 mock.patch.object(
                    PR, "_launch_one_run_detached",
                    side_effect=RuntimeError("test failure")):
                transitions = PR._retry_pending_runs_once(hr)
            self.assertEqual(transitions, 1)
            on_disk = json.loads(mp.read_text())
            self.assertEqual(
                on_disk["runs"][0]["terminal_state"], "FAILED")
            self.assertIn(
                "test failure",
                on_disk["runs"][0]["terminal_reason"])


# ---------------------------------------------------------------------------
# Integration — collect_harness_run wires the retry call
# ---------------------------------------------------------------------------


class CollectHarnessRunWiringTests(unittest.TestCase):
    """The collector entry point now calls
    ``_retry_pending_runs_once`` BEFORE the parallel collect.
    Source-inspection smoke test (the full collect_harness_run is
    covered by 108's existing tests; here we just verify the wire-
    up call site exists)."""

    def test_collect_harness_run_calls_retry_helper(self) -> None:
        src = Path(PR.__file__).read_text(encoding="utf-8")
        self.assertIn(
            "_retry_pending_runs_once(harness_run_dir, log)",
            src)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
