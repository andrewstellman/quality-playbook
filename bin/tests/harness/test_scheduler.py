"""v1.5.7 093 — parallel scheduler tests (segregated harness suite).

Covers ``bin/harness/scheduler.py``:

  VendorMappingTests — runner→vendor mapping per instruction 093:
    claude→anthropic, codex→openai, copilot→github, cursor→cursor.
  ConfigTests — defaults; per-vendor caps + global cap +
    per-vendor cooldown; `config_from_dict` tolerates partial /
    unknown-vendor JSON.
  PerVendorCapTests — same-vendor runs respect the cap;
    different vendors run concurrently up to global cap.
  GlobalCapTests — global cap caps total in-flight regardless of
    per-vendor cap headroom.
  CooldownTests — per-vendor cooldown delays the NEXT same-vendor
    start; other vendors are unaffected.
  SelectionTests — FIFO within a vendor; `next_ready()` skips
    capped vendors and returns the first eligible one.
  LifecycleTests — enqueue/mark_started/mark_finished bookkeeping;
    duplicate-add detection; mark_finished on unknown run raises.
  SnapshotTests — JSON-serializable state for the TUI.

Time injection: tests pass a list-driven ``now_fn`` so cooldown
behavior is deterministic without `time.sleep`.
"""
from __future__ import annotations

import json
import unittest

from bin.harness import scheduler as SCH
from bin.harness.schema import Runner


# ---------------------------------------------------------------------------
# Helper: a list-driven monotonic clock for deterministic tests.
# ---------------------------------------------------------------------------


class _FakeClock:
    """Returns whatever value was last ``set()``. The scheduler
    makes multiple ``now_fn()`` calls per operation (enqueue +
    next_ready + snapshot); a stateful "current time" is simpler
    + matches the monotonic-clock contract."""

    def __init__(self, initial: float = 0.0) -> None:
        self._now = initial

    def __call__(self) -> float:
        return self._now

    def set(self, t: float) -> None:
        self._now = t


# ---------------------------------------------------------------------------
# Vendor mapping
# ---------------------------------------------------------------------------


class VendorMappingTests(unittest.TestCase):

    def test_claude_maps_to_anthropic(self) -> None:
        self.assertEqual(SCH.vendor_for_runner(Runner.CLAUDE),
                         SCH.Vendor.ANTHROPIC)

    def test_codex_maps_to_openai(self) -> None:
        self.assertEqual(SCH.vendor_for_runner(Runner.CODEX),
                         SCH.Vendor.OPENAI)

    def test_copilot_maps_to_github(self) -> None:
        self.assertEqual(SCH.vendor_for_runner(Runner.COPILOT),
                         SCH.Vendor.GITHUB)

    def test_cursor_maps_to_cursor(self) -> None:
        self.assertEqual(SCH.vendor_for_runner(Runner.CURSOR),
                         SCH.Vendor.CURSOR)

    def test_mapping_covers_all_runners(self) -> None:
        """Every Runner has a vendor mapping — no KeyError on a
        new runner addition without map update."""
        for r in Runner:
            self.assertIsInstance(
                SCH.vendor_for_runner(r), SCH.Vendor,
            )


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class ConfigTests(unittest.TestCase):

    def test_defaults_per_vendor_cap_1(self) -> None:
        cfg = SCH.SchedulerConfig()
        for v in SCH.Vendor:
            self.assertEqual(cfg.cap_for(v), 1)

    def test_default_global_cap_4(self) -> None:
        cfg = SCH.SchedulerConfig()
        self.assertEqual(cfg.global_cap, 4)

    def test_default_cooldown_zero(self) -> None:
        cfg = SCH.SchedulerConfig()
        for v in SCH.Vendor:
            self.assertEqual(cfg.cooldown_for(v), 0.0)

    def test_config_from_dict_partial(self) -> None:
        cfg = SCH.config_from_dict({
            "vendor_caps": {"anthropic": 2},
            "global_cap": 8,
        })
        self.assertEqual(cfg.cap_for(SCH.Vendor.ANTHROPIC), 2)
        # Other vendors keep default cap = 1.
        self.assertEqual(cfg.cap_for(SCH.Vendor.OPENAI), 1)
        self.assertEqual(cfg.global_cap, 8)

    def test_config_from_dict_cooldown(self) -> None:
        cfg = SCH.config_from_dict({
            "vendor_cooldown_s": {"github": 30, "openai": 15},
        })
        self.assertEqual(cfg.cooldown_for(SCH.Vendor.GITHUB), 30.0)
        self.assertEqual(cfg.cooldown_for(SCH.Vendor.OPENAI), 15.0)
        # Unset vendors stay at 0.
        self.assertEqual(cfg.cooldown_for(SCH.Vendor.CURSOR), 0.0)

    def test_config_from_dict_unknown_vendor_ignored(self) -> None:
        """Forward-compat: an unknown vendor name in JSON is
        silently ignored (the config loader doesn't crash on a
        future config produced by a later QPB version)."""
        cfg = SCH.config_from_dict({
            "vendor_caps": {"anthropic": 2, "totally_new_vendor": 5},
        })
        self.assertEqual(cfg.cap_for(SCH.Vendor.ANTHROPIC), 2)


# ---------------------------------------------------------------------------
# Per-vendor caps
# ---------------------------------------------------------------------------


class PerVendorCapTests(unittest.TestCase):

    def test_same_vendor_serializes_at_cap_1(self) -> None:
        """Two anthropic runs queued + cap=1 → only one runs at
        a time; the second waits until the first finishes."""
        s = SCH.Scheduler()
        s.enqueue("a1", SCH.Vendor.ANTHROPIC)
        s.enqueue("a2", SCH.Vendor.ANTHROPIC)
        # Pick the first eligible — a1.
        self.assertEqual(s.next_ready(), "a1")
        s.mark_started("a1")
        # a2 must wait (cap=1).
        self.assertIsNone(s.next_ready())
        # Finish a1 → a2 becomes eligible.
        s.mark_finished("a1")
        self.assertEqual(s.next_ready(), "a2")

    def test_different_vendors_run_concurrently(self) -> None:
        """anthropic + openai runs go concurrent (different
        vendors, cap=1 each, global cap=4)."""
        s = SCH.Scheduler()
        s.enqueue("a1", SCH.Vendor.ANTHROPIC)
        s.enqueue("o1", SCH.Vendor.OPENAI)
        first = s.next_ready()
        self.assertIn(first, ("a1", "o1"))
        s.mark_started(first)
        # The other vendor is still eligible.
        second = s.next_ready()
        self.assertIn(second, ("a1", "o1"))
        self.assertNotEqual(first, second)
        s.mark_started(second)
        # Now both in-flight, queue empty.
        self.assertEqual(s.in_flight_total(), 2)

    def test_per_vendor_cap_configurable_to_2(self) -> None:
        """anthropic cap=2 → two same-vendor runs go concurrent."""
        cfg = SCH.SchedulerConfig()
        cfg.vendor_caps[SCH.Vendor.ANTHROPIC] = 2
        s = SCH.Scheduler(config=cfg)
        s.enqueue("a1", SCH.Vendor.ANTHROPIC)
        s.enqueue("a2", SCH.Vendor.ANTHROPIC)
        s.enqueue("a3", SCH.Vendor.ANTHROPIC)
        s.mark_started(s.next_ready())  # a1
        s.mark_started(s.next_ready())  # a2
        # cap=2 reached, a3 must wait.
        self.assertIsNone(s.next_ready())
        self.assertEqual(s.in_flight_for(SCH.Vendor.ANTHROPIC), 2)

    def test_vendor_cap_zero_disables_starts(self) -> None:
        """vendor_caps[X] = 0 → no run for X ever starts."""
        cfg = SCH.SchedulerConfig()
        cfg.vendor_caps[SCH.Vendor.ANTHROPIC] = 0
        s = SCH.Scheduler(config=cfg)
        s.enqueue("a1", SCH.Vendor.ANTHROPIC)
        self.assertIsNone(s.next_ready())


# ---------------------------------------------------------------------------
# Global cap
# ---------------------------------------------------------------------------


class GlobalCapTests(unittest.TestCase):

    def test_global_cap_overrides_per_vendor_headroom(self) -> None:
        """global_cap=2 with 3 different-vendor queued runs →
        only 2 go in-flight even though each vendor has cap=1
        headroom."""
        cfg = SCH.SchedulerConfig()
        cfg.global_cap = 2
        s = SCH.Scheduler(config=cfg)
        s.enqueue("a1", SCH.Vendor.ANTHROPIC)
        s.enqueue("o1", SCH.Vendor.OPENAI)
        s.enqueue("g1", SCH.Vendor.GITHUB)
        s.mark_started(s.next_ready())
        s.mark_started(s.next_ready())
        # global cap hit at 2 — third must wait even though its
        # vendor (github) still has cap=1 headroom.
        self.assertEqual(s.in_flight_total(), 2)
        self.assertIsNone(s.next_ready())


# ---------------------------------------------------------------------------
# Per-vendor cooldown
# ---------------------------------------------------------------------------


class CooldownTests(unittest.TestCase):

    def test_cooldown_delays_next_same_vendor_start(self) -> None:
        """anthropic cooldown=30s → after a1 finishes, a2 must
        wait 30s before it becomes eligible."""
        clock = _FakeClock(0.0)
        cfg = SCH.SchedulerConfig()
        cfg.vendor_cooldown_s[SCH.Vendor.ANTHROPIC] = 30.0
        s = SCH.Scheduler(config=cfg, now_fn=clock)
        # t=0: enqueue + start a1.
        s.enqueue("a1", SCH.Vendor.ANTHROPIC)
        self.assertEqual(s.next_ready(), "a1")
        s.mark_started("a1")
        s.enqueue("a2", SCH.Vendor.ANTHROPIC)
        # t=10: a1 finishes — cooldown starts at t=10.
        clock.set(10.0)
        s.mark_finished("a1")
        # t=20: cooldown not elapsed (30 − 10 = 20s remaining).
        clock.set(20.0)
        self.assertIsNone(s.next_ready())
        # t=39.9: still cooling down.
        clock.set(39.9)
        self.assertIsNone(s.next_ready())
        # t=40.0+: cooldown elapsed.
        clock.set(40.0)
        self.assertEqual(s.next_ready(), "a2")

    def test_cooldown_does_not_block_other_vendors(self) -> None:
        """Anthropic cooling down → openai still starts
        immediately."""
        clock = _FakeClock(0.0)
        cfg = SCH.SchedulerConfig()
        cfg.vendor_cooldown_s[SCH.Vendor.ANTHROPIC] = 60.0
        s = SCH.Scheduler(config=cfg, now_fn=clock)
        s.enqueue("a1", SCH.Vendor.ANTHROPIC)
        s.mark_started(s.next_ready())
        clock.set(5.0)
        s.mark_finished("a1")  # anthropic cooldown until t=65
        # Enqueue an openai run at t=5.5 — must be eligible
        # immediately (cooldown is per-vendor).
        clock.set(5.5)
        s.enqueue("o1", SCH.Vendor.OPENAI)
        self.assertEqual(s.next_ready(), "o1")


# ---------------------------------------------------------------------------
# Selection policy
# ---------------------------------------------------------------------------


class SelectionTests(unittest.TestCase):

    def test_next_ready_returns_None_when_queue_empty(self) -> None:
        s = SCH.Scheduler()
        self.assertIsNone(s.next_ready())

    def test_fifo_within_vendor(self) -> None:
        """Two anthropic runs enqueued in order; the first
        enqueued is the first started."""
        clock = _FakeClock(0.0)
        s = SCH.Scheduler(now_fn=clock)
        s.enqueue("a1", SCH.Vendor.ANTHROPIC)  # ts=0
        clock.set(1.0)
        s.enqueue("a2", SCH.Vendor.ANTHROPIC)  # ts=1
        self.assertEqual(s.next_ready(), "a1")

    def test_skips_capped_vendor_picks_eligible_one(self) -> None:
        """If anthropic is at cap, the scan skips its queued
        runs and picks the next eligible vendor's run."""
        s = SCH.Scheduler()
        s.enqueue("a1", SCH.Vendor.ANTHROPIC)
        s.enqueue("a2", SCH.Vendor.ANTHROPIC)
        s.enqueue("o1", SCH.Vendor.OPENAI)
        s.mark_started(s.next_ready())  # a1 in-flight
        # a2 is queued ahead of o1 but anthropic at cap → o1 wins.
        self.assertEqual(s.next_ready(), "o1")


# ---------------------------------------------------------------------------
# Lifecycle bookkeeping
# ---------------------------------------------------------------------------


class LifecycleTests(unittest.TestCase):

    def test_mark_started_removes_from_queue(self) -> None:
        s = SCH.Scheduler()
        s.enqueue("a1", SCH.Vendor.ANTHROPIC)
        self.assertEqual(s.queue_length(), 1)
        s.mark_started("a1")
        self.assertEqual(s.queue_length(), 0)
        self.assertEqual(s.in_flight_total(), 1)

    def test_mark_finished_decrements(self) -> None:
        s = SCH.Scheduler()
        s.enqueue("a1", SCH.Vendor.ANTHROPIC)
        s.mark_started("a1")
        s.mark_finished("a1")
        self.assertEqual(s.in_flight_total(), 0)
        self.assertEqual(s.in_flight_for(SCH.Vendor.ANTHROPIC), 0)

    def test_duplicate_enqueue_in_queue_raises(self) -> None:
        s = SCH.Scheduler()
        s.enqueue("a1", SCH.Vendor.ANTHROPIC)
        with self.assertRaises(ValueError) as ctx:
            s.enqueue("a1", SCH.Vendor.ANTHROPIC)
        self.assertIn("already in queue", str(ctx.exception))

    def test_duplicate_enqueue_in_flight_raises(self) -> None:
        s = SCH.Scheduler()
        s.enqueue("a1", SCH.Vendor.ANTHROPIC)
        s.mark_started("a1")
        with self.assertRaises(ValueError) as ctx:
            s.enqueue("a1", SCH.Vendor.ANTHROPIC)
        self.assertIn("already in-flight", str(ctx.exception))

    def test_mark_started_unknown_run_raises(self) -> None:
        s = SCH.Scheduler()
        with self.assertRaises(ValueError) as ctx:
            s.mark_started("nonexistent")
        self.assertIn("not in queue", str(ctx.exception))

    def test_mark_finished_unknown_run_raises(self) -> None:
        s = SCH.Scheduler()
        with self.assertRaises(ValueError) as ctx:
            s.mark_finished("nonexistent")
        self.assertIn("not in-flight", str(ctx.exception))


# ---------------------------------------------------------------------------
# Snapshot (TUI / receipt input)
# ---------------------------------------------------------------------------


class SnapshotTests(unittest.TestCase):

    def test_snapshot_json_serializable(self) -> None:
        s = SCH.Scheduler()
        s.enqueue("a1", SCH.Vendor.ANTHROPIC)
        s.enqueue("o1", SCH.Vendor.OPENAI)
        s.mark_started("a1")
        snap = s.snapshot()
        # JSON-serializable end-to-end (the TUI receipt path).
        json.dumps(snap)
        self.assertEqual(snap["queue_length"], 1)
        self.assertEqual(snap["in_flight_total"], 1)
        self.assertEqual(snap["in_flight_by_vendor"]["anthropic"], 1)
        self.assertEqual(snap["in_flight_by_vendor"]["openai"], 0)
        self.assertEqual(snap["vendor_caps"]["anthropic"], 1)
        self.assertEqual(snap["global_cap"], 4)
        self.assertEqual(len(snap["queued"]), 1)
        self.assertEqual(snap["queued"][0]["run_id"], "o1")

    def test_snapshot_reports_cooldown_remaining(self) -> None:
        clock = _FakeClock(0.0)
        cfg = SCH.SchedulerConfig()
        cfg.vendor_cooldown_s[SCH.Vendor.ANTHROPIC] = 30.0
        s = SCH.Scheduler(config=cfg, now_fn=clock)
        s.enqueue("a1", SCH.Vendor.ANTHROPIC)
        s.mark_started(s.next_ready())
        clock.set(10.0)
        s.mark_finished("a1")
        # t=15: cooldown has 25s remaining (30 cooldown − 5s
        # elapsed since finish at t=10).
        clock.set(15.0)
        snap = s.snapshot()
        self.assertIn("anthropic", snap["cooldown_remaining_s"])
        self.assertAlmostEqual(
            snap["cooldown_remaining_s"]["anthropic"], 25.0,
            places=1,
        )


if __name__ == "__main__":
    unittest.main()
