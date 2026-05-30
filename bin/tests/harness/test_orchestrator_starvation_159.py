"""v1.5.7 159 — orchestrator must not hang on slot starvation.

The 2026-05-30 04:26 ship-readiness retest hit the deadlock: plan
asked for claude=3 + codex=2 + copilot=2; global anthropic cap was
2; the third claude thread's ``_inflight.acquire_run_slot`` blocked
forever; ``f.result()`` on its ThreadPoolExecutor future blocked
forever; the orchestrator never reached the manifest-write +
collector-spawn code that follows the launch barrier. Six workers
were alive but orphaned (no collector observing them, no manifest
recording them).

Worker pre-flight (see review-request) found ``acquire_run_slot``
already accepts a ``max_wait_s`` parameter that raises
``TimeoutError`` — but ``_wrapped`` in plan_runner called it WITHOUT
the parameter (default None → wait forever). The minimal fix:
``_wrapped`` now passes a defensive timeout
(``_acquire_run_slot_timeout_s()``, env-tunable, default 300s) and
catches ``TimeoutError`` cleanly, leaving the starved run's
manifest_entries slot ``None``. The post-barrier filter
``[e for e in manifest_entries if e is not None]`` drops the
starved run; the orchestrator writes the manifest + spawns the
collector for the runs that DID launch. The collector then observes
the unlaunched run-NN dirs as PENDING (per 153's recognition).

This is Option 2 per the instruction (non-blocking acquire via
timeout); Option 1 (collector-first reordering) requires partial-
state manifest semantics + collector startup tolerance for partial
state that's substantially more code than the timeout approach.
Halt explicitly authorized falling back to Option 2.

Task B (Mode B phase-1 abort cleanup) deferred per the
instruction's explicit "skip if scope grows" authorization — it
touches runner-side phase orchestration in ``bin/run_playbook.py``
or ``bin/harness/runner.py`` and is independent of the orchestrator
deadlock 159 fixes.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from bin.harness import inflight_registry as IR
from bin.harness import plan_runner as PR


# ---------------------------------------------------------------------------
# Helper resolution (Task C — defensive timeout env-var)
# ---------------------------------------------------------------------------


class AcquireRunSlotTimeoutHelperTests(unittest.TestCase):

    def setUp(self) -> None:
        self._prev = os.environ.get(
            "QPB_HARNESS_ACQUIRE_TIMEOUT_S")
        os.environ.pop(
            "QPB_HARNESS_ACQUIRE_TIMEOUT_S", None)

    def tearDown(self) -> None:
        if self._prev is None:
            os.environ.pop(
                "QPB_HARNESS_ACQUIRE_TIMEOUT_S", None)
        else:
            os.environ["QPB_HARNESS_ACQUIRE_TIMEOUT_S"] = self._prev

    def test_default_is_300s(self) -> None:
        self.assertEqual(PR._acquire_run_slot_timeout_s(), 300.0)

    def test_env_var_overrides_default(self) -> None:
        os.environ["QPB_HARNESS_ACQUIRE_TIMEOUT_S"] = "60"
        self.assertEqual(PR._acquire_run_slot_timeout_s(), 60.0)

    def test_non_numeric_env_var_falls_back(self) -> None:
        os.environ["QPB_HARNESS_ACQUIRE_TIMEOUT_S"] = "not-a-number"
        self.assertEqual(PR._acquire_run_slot_timeout_s(), 300.0)

    def test_zero_or_negative_falls_back(self) -> None:
        os.environ["QPB_HARNESS_ACQUIRE_TIMEOUT_S"] = "0"
        self.assertEqual(PR._acquire_run_slot_timeout_s(), 300.0)
        os.environ["QPB_HARNESS_ACQUIRE_TIMEOUT_S"] = "-5"
        self.assertEqual(PR._acquire_run_slot_timeout_s(), 300.0)


# ---------------------------------------------------------------------------
# acquire_run_slot timeout behavior — direct exercise
# ---------------------------------------------------------------------------


def _seed_registry(path: Path, entries: list) -> None:
    path.write_text(
        json.dumps({"entries": entries}) + "\n", encoding="utf-8")


class AcquireRunSlotTimeoutDirectTests(unittest.TestCase):
    """The mechanism the 159 fix relies on: ``max_wait_s`` raises
    ``TimeoutError`` instead of blocking forever when no slot is
    free. This already worked pre-159; pinning here so a future
    "let's make this blocking again" refactor catches the test."""

    def test_acquire_raises_timeout_when_pool_starved(
            self) -> None:
        with tempfile.TemporaryDirectory() as td:
            registry = Path(td) / "inflight.json"
            # Fill the anthropic provider — 2 alive entries make
            # any further claude acquire wait, and our tight
            # timeout makes it TimeoutError.
            _seed_registry(registry, [
                {"pid": os.getpid(), "runner": "claude",
                 "provider": "anthropic",
                 "harness_run_dir": str(td),
                 "run_index": 0,
                 "started_at": "2026-05-30T04:26:00Z"},
                {"pid": os.getpid(), "runner": "claude",
                 "provider": "anthropic",
                 "harness_run_dir": str(td),
                 "run_index": 1,
                 "started_at": "2026-05-30T04:26:00Z"},
            ])
            start = time.monotonic()
            with self.assertRaises(TimeoutError):
                IR.acquire_run_slot(
                    runner="claude",
                    harness_run_dir=Path(td),
                    run_index=99,
                    started_at="2026-05-30T04:26:01Z",
                    max_per_provider={"anthropic": 2},
                    registry_path=registry,
                    poll_interval_s=0.05,
                    max_wait_s=0.5,
                )
            elapsed = time.monotonic() - start
            # Mutation-bite target: dropping max_wait_s would make
            # this test hang. Bound check on elapsed time also
            # catches a wait-too-long regression.
            self.assertLess(elapsed, 5.0,
                            f"timeout took too long: {elapsed}s")


# ---------------------------------------------------------------------------
# _wrapped does not hang the orchestrator when slot is starved
# ---------------------------------------------------------------------------


class WrappedTimeoutBehaviorTests(unittest.TestCase):
    """Black-box: when ``acquire_run_slot`` raises ``TimeoutError``
    (because slot is starved), ``_wrapped`` must return cleanly
    without re-raising, so ``f.result()`` in run_plan's barrier
    doesn't hang OR propagate the error and crash the orchestrator.

    We can't easily drive ``_wrapped`` directly (it's a closure
    inside ``run_plan``), so this test exercises the equivalent
    flow via ``run_plan`` itself with starvation-triggering
    parameters. Tight ``QPB_HARNESS_ACQUIRE_TIMEOUT_S`` makes the
    test run in well under a second.
    """

    def test_run_plan_completes_when_one_run_starves(self) -> None:
        # This is the LOAD-BEARING regression test: pre-159 it
        # would hang. With 159, the starved run is skipped and
        # run_plan completes.
        # We use a minimal mock setup: 2 runs requested but only
        # one slot available. acquire_run_slot is patched to mimic
        # starvation on the second call.
        timeout_calls = [0]

        def fake_acquire(**kwargs):
            timeout_calls[0] += 1
            if timeout_calls[0] >= 2:
                raise TimeoutError("starved (test mock)")
            return None  # first call succeeds (slot reserved)

        # Build a minimal Plan with 2 claude runs.
        from bin.harness.schema import (
            InstallChannel, Mode, RunAxes, Runner)
        # PlanRun is a dataclass per the 099 design; minimal fields.
        runs = [
            PR.PlanRun(
                index=i,
                description=f"r{i}",
                repo="https://github.com/x/y",
                ref="main",
                runner=Runner.CLAUDE,
                model="opus",
                channel=InstallChannel.CLONE,
                mode=Mode.A,
                expect={},
            ) for i in range(2)
        ]
        plan = PR.Plan(pools={"claude": 2}, runs=runs)

        # Mock everything the launch barrier touches so the test
        # doesn't actually spawn workers.
        with tempfile.TemporaryDirectory() as td:
            runs_root = Path(td) / "harness_runs"
            runs_root.mkdir()

            with mock.patch.object(IR, "acquire_run_slot",
                                    side_effect=fake_acquire), \
                 mock.patch.object(PR, "_launch_one_run_detached",
                                    return_value={
                                        "index": 0,
                                        "description": "r0",
                                        "repo": "https://github.com/x/y",
                                        "runner": "claude",
                                        "model": "opus",
                                        "channel": "clone",
                                        "mode": "A",
                                        "target_dir": str(runs_root / "tgt"),
                                        "run_dir": str(runs_root / "rd"),
                                        "run_id": "r0",
                                        "pid": 1,
                                        "started_at":
                                            "2026-05-30T04:26:00Z",
                                        "stream_path":
                                            str(runs_root / "stream"),
                                        "status_path":
                                            str(runs_root / "status"),
                                        "max_duration_s": 1.0,
                                        "expect": {},
                                    }), \
                 mock.patch.object(IR, "update_pid"), \
                 mock.patch.object(IR, "release_run_slot"), \
                 mock.patch.object(PR, "_spawn_collector",
                                    return_value=9999), \
                 mock.patch.object(PR, "_required_local_channels",
                                    return_value=set()):
                start = time.monotonic()
                outcomes = PR.run_plan(plan, runs_root)
                elapsed = time.monotonic() - start

        # Mutation-bite target: removing the try/except TimeoutError
        # in _wrapped would cause f.result() to re-raise
        # TimeoutError → run_plan crashes. Removing the timeout pass
        # at the acquire call would make the test hang.
        self.assertLess(elapsed, 10.0,
                        f"run_plan took too long: {elapsed}s")
        # v1.5.7 161 Task A: starved entries now write a PENDING
        # manifest entry (instead of leaving manifest_entries[idx]
        # None), so outcomes includes BOTH the launched run AND the
        # PENDING one. Pre-161 this was 1; post-161 it's 2.
        self.assertEqual(len(outcomes), 2)
        # The launched outcome is the first; the second is PENDING.
        self.assertEqual(outcomes[1].terminal_state, "RUNNING")


# ---------------------------------------------------------------------------
# Empirical regression — the 04:26 plan shape
# ---------------------------------------------------------------------------


class EmpiricalRegressionTests(unittest.TestCase):
    """Pin the 2026-05-30 04:26 shape: a plan whose pool config
    exceeds the global per-provider cap completes (rather than
    hanging) within 10s. This is the headline regression test for
    the worst v1.5.7 failure mode."""

    def test_three_claude_with_anthropic_cap_two_does_not_hang(
            self) -> None:
        from bin.harness.schema import (
            InstallChannel, Mode, Runner)
        runs = [
            PR.PlanRun(
                index=i, description=f"r{i}",
                repo="https://github.com/x/y", ref="main",
                runner=Runner.CLAUDE, model="opus",
                channel=InstallChannel.CLONE, mode=Mode.A,
                expect={},
            ) for i in range(3)
        ]
        plan = PR.Plan(pools={"claude": 3}, runs=runs)

        call_count = [0]
        def fake_acquire(**kwargs):
            call_count[0] += 1
            if call_count[0] > 2:
                raise TimeoutError(
                    "anthropic cap=2 starved (test mock)")

        def fake_launch(*a, **k):
            return {
                "index": 0, "description": "r",
                "repo": "https://github.com/x/y",
                "runner": "claude", "model": "opus",
                "channel": "clone", "mode": "A",
                "target_dir": "/tmp/x", "run_dir": "/tmp/x",
                "run_id": "x", "pid": 1,
                "started_at": "2026-05-30T04:26:00Z",
                "stream_path": "/tmp/s", "status_path": "/tmp/st",
                "max_duration_s": 1.0, "expect": {},
            }

        with tempfile.TemporaryDirectory() as td:
            runs_root = Path(td) / "harness_runs"
            runs_root.mkdir()
            with mock.patch.object(IR, "acquire_run_slot",
                                    side_effect=fake_acquire), \
                 mock.patch.object(PR, "_launch_one_run_detached",
                                    side_effect=fake_launch), \
                 mock.patch.object(IR, "update_pid"), \
                 mock.patch.object(IR, "release_run_slot"), \
                 mock.patch.object(PR, "_spawn_collector",
                                    return_value=9999), \
                 mock.patch.object(PR, "_required_local_channels",
                                    return_value=set()):
                start = time.monotonic()
                outcomes = PR.run_plan(plan, runs_root)
                elapsed = time.monotonic() - start

        self.assertLess(elapsed, 10.0,
                        f"04:26-shape plan still hangs: {elapsed}s")
        # v1.5.7 161 Task A: starved entries now produce PENDING
        # manifest entries → outcomes includes ALL 3 (2 launched +
        # 1 PENDING). Pre-161 this was 2.
        self.assertEqual(len(outcomes), 3,
                         "expected 2 launched + 1 PENDING")


class PendingManifestEntryTests(unittest.TestCase):
    """v1.5.7 161 Task A: when ``_wrapped`` catches TimeoutError
    (starvation), it now writes a PENDING manifest entry with full
    metadata (repo / runner / model / channel / description / paths)
    instead of leaving manifest_entries[idx]=None. This unblocks
    160 D-prime's manifest-metadata lookup for PENDING rows AND
    gives the upcoming 161 Tasks B+C (collector retry +
    ABANDONED_STARVED) a manifest entry to read.

    Tasks B (collector retry loop) + C (ABANDONED_STARVED deadline)
    are deferred to a 161-followup; Task A here is the foundational
    piece they need."""

    def test_starved_run_writes_pending_manifest_entry_with_full_metadata(
            self) -> None:
        from bin.harness.schema import (
            InstallChannel, Mode, Runner)
        runs = [
            PR.PlanRun(
                index=i, description=f"d{i}",
                repo=f"https://github.com/x/r{i}", ref="main",
                runner=Runner.CLAUDE, model="opus",
                channel=InstallChannel.CLONE, mode=Mode.A,
                expect={},
            ) for i in range(2)
        ]
        plan = PR.Plan(pools={"claude": 2}, runs=runs)

        call_count = [0]
        def fake_acquire(**kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise TimeoutError("starved (test mock)")

        with tempfile.TemporaryDirectory() as td:
            runs_root = Path(td) / "harness_runs"
            runs_root.mkdir()
            with mock.patch.object(IR, "acquire_run_slot",
                                    side_effect=fake_acquire), \
                 mock.patch.object(PR, "_launch_one_run_detached",
                                    return_value={
                                        "index": 0, "description": "d0",
                                        "repo": "https://github.com/x/r0",
                                        "runner": "claude", "model": "opus",
                                        "channel": "clone", "mode": "A",
                                        "target_dir": "/tmp/x",
                                        "run_dir": "/tmp/rd",
                                        "run_id": "r0", "pid": 1,
                                        "started_at":
                                            "2026-05-30T13:43:00Z",
                                        "stream_path": "/tmp/s",
                                        "status_path": "/tmp/st",
                                        "max_duration_s": 1.0,
                                        "expect": {},
                                    }), \
                 mock.patch.object(IR, "update_pid"), \
                 mock.patch.object(IR, "release_run_slot"), \
                 mock.patch.object(PR, "_spawn_collector",
                                    return_value=9999), \
                 mock.patch.object(PR, "_required_local_channels",
                                    return_value=set()):
                outcomes = PR.run_plan(plan, runs_root)

            # Find the harness-run dir + its manifest.
            hr_dirs = list(runs_root.iterdir())
            self.assertEqual(len(hr_dirs), 1)
            manifest_path = hr_dirs[0] / "manifest.json"
            self.assertTrue(manifest_path.is_file())
            manifest = json.loads(manifest_path.read_text())
            runs_in_manifest = manifest.get("runs", [])

        # 2 entries (1 launched + 1 PENDING).
        self.assertEqual(len(runs_in_manifest), 2,
                         "manifest should include the PENDING entry")
        pending_entries = [
            e for e in runs_in_manifest
            if e.get("state") == "PENDING"]
        # Mutation-bite target: removing the
        # ``manifest_entries[idx] = {...}`` write makes this empty.
        self.assertEqual(len(pending_entries), 1)
        pe = pending_entries[0]
        # Full metadata present (160 D-prime requires this for PENDING
        # rows to display correctly + 161 Tasks B+C will read it).
        self.assertEqual(pe["index"], 1)
        self.assertEqual(pe["repo"], "https://github.com/x/r1")
        self.assertEqual(pe["runner"], "claude")
        self.assertEqual(pe["model"], "opus")
        self.assertEqual(pe["channel"], "clone")
        self.assertEqual(pe["description"], "d1")
        self.assertIsNone(pe["pid"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
