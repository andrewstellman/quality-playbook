"""QPB Test Harness — parallel scheduler (Phase 3).

NOTE FOR REVIEWERS: this module governs the ``qpb_harness
manager`` flow's concurrency (per-daemon, in-process). The
``qpb_harness run-plan`` flow uses a DIFFERENT mechanism:
``inflight_registry.py`` (machine-global, file-backed,
fcntl.flock). See ``manager.py``'s banner for the full two-flow
map. The v1.5.7 125 cross-host per-provider cap is in
``inflight_registry.py``, NOT here — this scheduler's caps are
PURE STATE for the daemon flow only.

Concurrency-aware scheduler per design §H:

  * **Per-vendor caps** (anthropic / openai / github / cursor —
    default 1 each, configurable in ``config.json``). Different
    vendors have different rate limits; cap concurrency per
    vendor, not globally-serial.
  * **Global cap** for machine resources (one cap across ALL
    in-flight runs regardless of vendor).
  * **Per-vendor cooldown** — minimum seconds between same-vendor
    runs (replaces the design's single global inter-run delay).
  * **Selection policy**: pick the next QUEUED run whose vendor
    has free capacity AND has passed cooldown AND global cap is
    not exhausted. FIFO within a vendor.

Safe because each run already gets a pristine worktree + a
receipt-dir source of truth (no shared-file races). The
scheduler is a PURE STATE OBJECT — it doesn't spawn processes
or write files. The manager (Phase 4) owns subprocess
orchestration and just queries the scheduler for "next ready run
to start".

Time injection: the scheduler accepts an optional `now_fn`
callable so tests are deterministic. Production passes
``time.monotonic`` (or omits — default is `time.monotonic`).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

from bin.harness.schema import Runner


# ---------------------------------------------------------------------------
# Vendor mapping (per instruction 093 Scope)
# ---------------------------------------------------------------------------


class Vendor(str, Enum):
    """Per-vendor cap groups. Each Runner maps to exactly one
    vendor; the scheduler tracks in-flight counts per vendor."""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GITHUB = "github"
    CURSOR = "cursor"


# Per-instruction 093: claude→anthropic, codex→openai,
# copilot→github, cursor→cursor.
_RUNNER_VENDOR_MAP: "dict[Runner, Vendor]" = {
    Runner.CLAUDE: Vendor.ANTHROPIC,
    Runner.CODEX: Vendor.OPENAI,
    Runner.COPILOT: Vendor.GITHUB,
    Runner.CURSOR: Vendor.CURSOR,
}


def vendor_for_runner(runner: Runner) -> Vendor:
    """Vendor for a given runner — the mapping is fixed per
    instruction 093 Scope."""
    return _RUNNER_VENDOR_MAP[runner]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass
class SchedulerConfig:
    """Operator-tunable scheduler knobs (loaded from
    ``repos/security-test-cases/config.json``)."""
    # Per-vendor cap (default 1). A value of 0 effectively
    # disables that vendor (the scheduler will never start a
    # run for it).
    vendor_caps: "dict[Vendor, int]" = field(default_factory=lambda: {
        Vendor.ANTHROPIC: 1,
        Vendor.OPENAI: 1,
        Vendor.GITHUB: 1,
        Vendor.CURSOR: 1,
    })
    # Hard cap across ALL vendors (machine resource limit).
    # Defaults to 4 so a fully-parallel run across all 4 vendors
    # works out of the box; the operator raises it for beefier
    # boxes via config.json.
    global_cap: int = 4
    # Per-vendor cooldown in seconds — minimum time between the
    # end of one same-vendor run and the start of the next.
    # 0 = no cooldown.
    vendor_cooldown_s: "dict[Vendor, float]" = field(default_factory=lambda: {
        Vendor.ANTHROPIC: 0.0,
        Vendor.OPENAI: 0.0,
        Vendor.GITHUB: 0.0,
        Vendor.CURSOR: 0.0,
    })

    def cap_for(self, vendor: Vendor) -> int:
        return self.vendor_caps.get(vendor, 1)

    def cooldown_for(self, vendor: Vendor) -> float:
        return self.vendor_cooldown_s.get(vendor, 0.0)


def load_config(runner_root: "Path | None" = None) -> SchedulerConfig:
    """v1.5.7 098: load the harness scheduler config with the
    live → example fallback.

    Resolution order:
      1. ``<runner_root>/config.json`` (the live, gitignored
         operator config — when present).
      2. ``bin/harness/config.example.json`` (the tracked
         sanitized template — fallback).
      3. ``SchedulerConfig()`` defaults (when neither file is
         present or readable).

    Returns a populated ``SchedulerConfig``. Tolerant of
    missing files, partial JSON, and unknown vendor names
    (forward-compat per ``config_from_dict``).
    """
    import json
    candidates: list[Path] = []
    if runner_root is not None:
        candidates.append(Path(runner_root) / "config.json")
    example = (Path(__file__).resolve().parent
               / "config.example.json")
    candidates.append(example)
    for p in candidates:
        if not p.is_file():
            continue
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        # The doc may carry top-level metadata ($schema_note,
        # channels, paths) alongside the "scheduler" subobject —
        # config_from_dict reads from the scheduler subobject if
        # present, otherwise falls through to the top level.
        sched_section = (raw.get("scheduler")
                          if isinstance(raw, dict) else None)
        return config_from_dict(sched_section or raw or {})
    return SchedulerConfig()


def config_from_dict(raw: dict) -> SchedulerConfig:
    """Parse the scheduler portion of a JSON ``config.json``
    document. Tolerates partial documents (uses defaults for
    absent keys). Example shape::

        {
          "vendor_caps": {"anthropic": 2, "openai": 1},
          "global_cap": 4,
          "vendor_cooldown_s": {"anthropic": 30}
        }
    """
    cfg = SchedulerConfig()
    vc = raw.get("vendor_caps") or {}
    for name, n in vc.items():
        try:
            cfg.vendor_caps[Vendor(name)] = int(n)
        except (ValueError, TypeError):
            # Unknown vendor name → ignore (forward-compat).
            continue
    if "global_cap" in raw:
        try:
            cfg.global_cap = int(raw["global_cap"])
        except (ValueError, TypeError):
            pass
    vcd = raw.get("vendor_cooldown_s") or {}
    for name, s in vcd.items():
        try:
            cfg.vendor_cooldown_s[Vendor(name)] = float(s)
        except (ValueError, TypeError):
            continue
    return cfg


# ---------------------------------------------------------------------------
# Scheduler state
# ---------------------------------------------------------------------------


@dataclass(order=True)
class _QueueEntry:
    """Internal queue entry — ordered by (enqueue_ts, run_id)
    so FIFO-within-vendor is deterministic."""
    enqueue_ts: float
    run_id: str = field(compare=True)
    vendor: Vendor = field(compare=False)


class Scheduler:
    """Pure-state scheduler. The manager (Phase 4) drives it by
    calling ``enqueue`` / ``next_ready`` / ``mark_started`` /
    ``mark_finished`` and using the returned ``run_id`` to spawn
    the actual subprocess (via ``bin.harness.runner.launch_run``).

    ``next_ready(now)`` returns ``None`` when no queued run is
    eligible (all vendors at cap, or in cooldown, or global cap
    hit). The caller polls; there's no event/callback machinery
    here (Phase 4 manager owns the event loop).
    """

    def __init__(self, config: "SchedulerConfig | None" = None,
                 now_fn: "Callable[[], float] | None" = None) -> None:
        self.config = config or SchedulerConfig()
        self._now: Callable[[], float] = now_fn or time.monotonic
        # Queue: a list of _QueueEntry (small N — linear scans
        # are fine; Phase 4 manager re-creates the scheduler on
        # daemon restart anyway).
        self._queue: list[_QueueEntry] = []
        # In-flight counts per vendor.
        self._in_flight: dict[Vendor, int] = {v: 0 for v in Vendor}
        # Per-run vendor mapping for in-flight runs (so
        # mark_finished decrements the right counter).
        self._in_flight_vendors: dict[str, Vendor] = {}
        # Last-finished timestamp per vendor (for cooldown).
        # None means "no run has ever finished for this vendor"
        # — cooldown does NOT apply on the first start (otherwise
        # a non-zero default would make the cooldown active from
        # boot, blocking every initial run).
        self._last_finish: dict[Vendor, "float | None"] = {
            v: None for v in Vendor
        }

    # --- queue ops ---------------------------------------------------

    def enqueue(self, run_id: str, vendor: Vendor) -> None:
        """Append a run to the queue. ``run_id`` is the caller's
        identity (typically the design §2 ``YYYYMMDDTHHMMSSZ``
        token); the scheduler treats it as opaque."""
        # Duplicate-add detection — a run already in queue or
        # in-flight raises so the caller's bookkeeping doesn't
        # silently drift.
        if any(e.run_id == run_id for e in self._queue):
            raise ValueError(
                f"run_id {run_id!r} already in queue"
            )
        if run_id in self._in_flight_vendors:
            raise ValueError(
                f"run_id {run_id!r} already in-flight"
            )
        self._queue.append(_QueueEntry(
            enqueue_ts=self._now(),
            run_id=run_id,
            vendor=vendor,
        ))

    def queue_length(self) -> int:
        return len(self._queue)

    def in_flight_total(self) -> int:
        return sum(self._in_flight.values())

    def in_flight_for(self, vendor: Vendor) -> int:
        return self._in_flight[vendor]

    # --- selection ---------------------------------------------------

    def _vendor_eligible(self, vendor: Vendor,
                          now: float) -> bool:
        """True iff a run for ``vendor`` could start RIGHT NOW
        (vendor cap not hit + global cap not hit + cooldown
        elapsed)."""
        if self._in_flight[vendor] >= self.config.cap_for(vendor):
            return False
        if self.in_flight_total() >= self.config.global_cap:
            return False
        last = self._last_finish[vendor]
        if last is not None:
            cooldown_until = last + self.config.cooldown_for(vendor)
            if now < cooldown_until:
                return False
        return True

    def next_ready(self) -> "str | None":
        """Return the run_id of the next queued run whose vendor
        has free capacity AND has passed cooldown AND the global
        cap is not exhausted. Returns ``None`` if nothing is
        currently startable.

        FIFO within a vendor (the queue is appended in order;
        the scan picks the first eligible match)."""
        if not self._queue:
            return None
        now = self._now()
        # Sort by enqueue order — defensive; the queue is
        # already FIFO, but a future caller-facing reorder API
        # would invalidate that.
        self._queue.sort()
        for entry in self._queue:
            if self._vendor_eligible(entry.vendor, now):
                return entry.run_id
        return None

    # --- lifecycle hooks --------------------------------------------

    def mark_started(self, run_id: str) -> None:
        """Caller has just spawned the subprocess for ``run_id``.
        Removes the entry from the queue and increments
        per-vendor + global in-flight counters."""
        idx = None
        for i, entry in enumerate(self._queue):
            if entry.run_id == run_id:
                idx = i
                break
        if idx is None:
            raise ValueError(
                f"mark_started: run_id {run_id!r} not in queue"
            )
        entry = self._queue.pop(idx)
        self._in_flight[entry.vendor] += 1
        self._in_flight_vendors[entry.run_id] = entry.vendor

    def mark_finished(self, run_id: str) -> None:
        """Caller's subprocess for ``run_id`` has terminated.
        Decrements in-flight + records the finish time so the
        per-vendor cooldown starts now."""
        vendor = self._in_flight_vendors.pop(run_id, None)
        if vendor is None:
            raise ValueError(
                f"mark_finished: run_id {run_id!r} is not in-flight"
            )
        self._in_flight[vendor] -= 1
        self._last_finish[vendor] = self._now()

    # --- snapshot for the TUI / receipts ----------------------------

    def snapshot(self) -> dict:
        """Return a JSON-serializable view of scheduler state for
        the Phase 4 TUI / receipts. Includes queued + in-flight
        counts per vendor + global, plus the per-vendor cooldown
        countdown if any vendor is currently throttled."""
        now = self._now()
        cooldown_remaining: dict[str, float] = {}
        for vendor in Vendor:
            last = self._last_finish[vendor]
            if last is None:
                continue
            cooldown_until = last + self.config.cooldown_for(vendor)
            remaining = cooldown_until - now
            if remaining > 0:
                cooldown_remaining[vendor.value] = remaining
        return {
            "queue_length": len(self._queue),
            "queued": [
                {"run_id": e.run_id, "vendor": e.vendor.value}
                for e in sorted(self._queue)
            ],
            "in_flight_total": self.in_flight_total(),
            "in_flight_by_vendor": {
                v.value: self._in_flight[v] for v in Vendor
            },
            "vendor_caps": {
                v.value: self.config.cap_for(v) for v in Vendor
            },
            "global_cap": self.config.global_cap,
            "cooldown_remaining_s": cooldown_remaining,
        }


__all__ = [
    "Vendor",
    "vendor_for_runner",
    "SchedulerConfig",
    "config_from_dict",
    "load_config",
    "Scheduler",
]
