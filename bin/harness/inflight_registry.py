"""QPB Test Harness — machine-global in-flight registry +
per-provider concurrency cap (v1.5.7 instruction 125).

## Why this exists

Pre-125, the harness's ``pools`` were per-plan AND released
at spawn (108 detached launch returns immediately, before
the subprocess terminates). Two consequences:

  (a) **per-plan over-fan-out**: with ``pools={claude:2}``,
      a 4-claude plan launched ALL 4 runs simultaneously.
      The semaphore released as each launch returned, so
      ``pools`` capped the spawn *rate* (microseconds, no-op
      in practice), not concurrent *execution*. Task A.0 of
      the 125 instruction calls this out.

  (b) **cross-plan blindness**: multiple ``run-plan``
      invocations had no shared accounting. Total concurrent
      provider calls could blow through a provider's rate
      limit — and did (the Anthropic weekly-limit incident
      that motivated 125).

## What 125 introduces

A file-backed registry at ``~/.qpb_harness/inflight.json``
(configurable via ``QPB_HARNESS_REGISTRY``). Each run
registers at launch + unregisters at terminal. The registry
is the single source of truth for "what's running right
now, machine-wide" and:

  1. enforces a configurable **global per-provider cap**
     (Task B — the safety valve);
  2. **holds the per-plan pool slot for the run's lifetime**
     (Task A.0 — the lifetime-slot mechanism replaces
     ``_PoolGate``'s release-at-spawn behavior);
  3. feeds the operator-visible global count on
     ``qpb_harness status`` (Task C).

Concurrency-safe via ``fcntl.flock`` (multiple ``run-plan``
invocations + the collector all touch the same file).

## Schema

```
{
  "entries": [
    {
      "pid": <int>,                   # subprocess pid; 0 = reserving (pre-launch); entries older than QPB_HARNESS_PID0_MAX_AGE_S (default 300 s) are reaped as crash-leak phantoms by the next read_active_runs (v1.5.7 126 — recovery is now AUTOMATIC, no manual rm needed)
      "runner": "claude" | "codex" | "copilot" | "cursor",
      "provider": "anthropic" | "openai" | "github" | "cursor",
      "harness_run_dir": "<absolute path>",
      "run_index": <int>,
      "started_at": "<ISO8601 UTC>"
    },
    ...
  ]
}
```

Entries are keyed by ``(harness_run_dir, run_index)`` so a
slot is reserved BEFORE the subprocess is spawned (avoiding
the launch-vs-cap race window), then the ``pid`` field is
updated after ``Popen`` returns. Unregister is
idempotent (no-op if entry doesn't exist).

## Provider mapping

  ``claude``  → ``anthropic``
  ``codex``   → ``openai``
  ``copilot`` → ``github``
  ``cursor``  → ``cursor``

(Centralized here so every consumer agrees. The harness's
schema enum carries the runner name; the registry carries
both runner AND provider so a future split can change one
without touching the other.)
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


PROVIDER_BY_RUNNER: "dict[str, str]" = {
    "claude": "anthropic",
    "codex": "openai",
    "copilot": "github",
    "cursor": "cursor",
}


# v1.5.7 125: conservative defaults — the Anthropic
# weekly-limit incident hit ~5 simultaneous claude runs;
# 2 is comfortably under any reasonable per-account weekly
# cap. Operators with higher quotas raise via
# ``--max-per-provider anthropic=N``. Other providers'
# defaults sized to "reasonable for a dev workstation" —
# operators tune to their account specifics.
DEFAULT_MAX_PER_PROVIDER: "dict[str, int]" = {
    "anthropic": 2,
    "openai": 3,
    "github": 3,
    "cursor": 3,
}


_DEFAULT_REGISTRY_PATH = (
    Path.home() / ".qpb_harness" / "inflight.json"
)


# v1.5.7 126: age-out for ``pid=0`` reservations. The
# legitimate acquire_run_slot→update_pid window is
# microseconds; 5 minutes is conservatively beyond any
# realistic Popen latency (including a heavy
# ``git worktree add --detach`` Mode B preflight). A
# ``pid=0`` entry older than this is a phantom reservation
# left by a launcher HARD-killed (SIGKILL/OOM/power-loss)
# between acquire and update_pid — bypassing the
# ``except BaseException → release_run_slot`` cleanup — so
# it gets reaped on the next ``read_active_runs``. Without
# this, such a phantom over-counts the provider cap FOREVER
# (fails SAFE — blocks launches, never over-fans-out — but
# requires manual ``rm`` of the registry to recover).
# Override per-invocation via ``QPB_HARNESS_PID0_MAX_AGE_S``.
_PID_ZERO_MAX_AGE_S: float = 300.0


# ---------------------------------------------------------------------------
# Path resolution + provider lookup
# ---------------------------------------------------------------------------


def provider_for_runner(runner: str) -> str:
    """Map a runner name (``claude``/``codex``/...) to its
    provider (``anthropic``/``openai``/...). Unknown
    runners pass through (operators with custom runners
    get reasonable defaults — counted under their own
    name)."""
    return PROVIDER_BY_RUNNER.get(runner, runner)


def resolve_registry_path(
        path: "Optional[Path]" = None) -> Path:
    """Resolve the registry path with the priority order:
      1. explicit ``path`` argument (tests),
      2. ``QPB_HARNESS_REGISTRY`` env var (operator override),
      3. default ``~/.qpb_harness/inflight.json``.

    Creates the parent directory if it doesn't exist (so
    a first-run on a fresh machine doesn't FileNotFoundError
    on the parent)."""
    if path is not None:
        p = Path(path)
    else:
        env = os.environ.get("QPB_HARNESS_REGISTRY")
        p = Path(env) if env else _DEFAULT_REGISTRY_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def parse_max_per_provider_spec(
        spec: "Optional[str]") -> "dict[str, int]":
    """Parse a CLI/env spec like
    ``anthropic=1,openai=3,github=2`` into a dict, merging
    with ``DEFAULT_MAX_PER_PROVIDER``. Unknown providers
    pass through (so an operator can cap a custom provider).
    Malformed tokens are skipped silently — the parser is
    permissive so operator typos don't blow up the launch
    site."""
    out = dict(DEFAULT_MAX_PER_PROVIDER)
    if not spec:
        return out
    for part in spec.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, _, v = part.partition("=")
        try:
            out[k.strip()] = int(v.strip())
        except ValueError:
            continue
    return out


# ---------------------------------------------------------------------------
# Liveness probe (patchable for tests)
# ---------------------------------------------------------------------------


def _pid_alive(pid: "int | None") -> bool:
    """``os.kill(pid, 0)`` semantics. ``None`` / 0 / negative
    PIDs are treated as 'not-pid-checkable' — the caller
    handles them per its semantics (the registry treats
    pid=0 entries as 'reserving' — alive — until the pid is
    set post-launch).

    v1.5.7 155 policy: ``PermissionError`` ⇒ NOT alive (entry
    evicted). EPERM from ``os.kill(pid, 0)`` means the pid
    exists but is owned by another user — on the single-user
    harness shape v1.5.7 ships for, that means the pid was
    reused by another process; retaining the entry as 'active'
    would block future harness invocations. Revisit if we
    ship to multi-user shared infra."""
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False
    return True


# ---------------------------------------------------------------------------
# Lock-safe registry I/O
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _locked_registry(path: Path):
    """Open the registry under an exclusive ``fcntl.flock``,
    yielding the loaded dict + a writer callback. The
    writer truncates + rewrites + fsyncs before releasing
    the lock — so a concurrent reader never sees a
    half-written file.

    Creates the file with an empty entries list if it
    doesn't exist yet (so first-call-on-a-fresh-machine
    is a no-op create, not an error)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    # Open in append+read mode so the file is created if
    # missing without truncating. We'll do the actual
    # read+write under lock.
    with open(path, "a+", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.seek(0)
            raw = f.read()
            if not raw.strip():
                data: "dict" = {"entries": []}
            else:
                try:
                    data = json.loads(raw)
                    if (not isinstance(data, dict)
                            or "entries" not in data
                            or not isinstance(
                                data["entries"], list)):
                        data = {"entries": []}
                except json.JSONDecodeError:
                    data = {"entries": []}

            written: "list[bool]" = [False]

            def _write(new_data: dict) -> None:
                f.seek(0)
                f.truncate()
                json.dump(new_data, f, indent=2)
                f.write("\n")
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass
                written[0] = True

            yield data, _write
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def _pid_zero_max_age_s() -> float:
    """v1.5.7 126: resolve the ``pid=0`` age-out threshold.
    Read ``QPB_HARNESS_PID0_MAX_AGE_S`` at CALL time (not
    import) so operators can set it per-invocation. Permissive
    (mirrors ``parse_max_per_provider_spec``): an unset,
    malformed, or non-positive value falls through to the
    ``_PID_ZERO_MAX_AGE_S`` default rather than raising."""
    raw = os.environ.get("QPB_HARNESS_PID0_MAX_AGE_S")
    if raw is None:
        return _PID_ZERO_MAX_AGE_S
    try:
        val = float(raw)
    except (ValueError, TypeError):
        return _PID_ZERO_MAX_AGE_S
    if val <= 0:
        return _PID_ZERO_MAX_AGE_S
    return val


def _parse_iso_utc(value: "object") -> "Optional[datetime]":
    """Parse an ISO-8601 UTC timestamp (the
    ``%Y-%m-%dT%H:%M:%SZ`` shape the harness writes for
    ``started_at``) into an aware ``datetime``. Returns
    ``None`` on any parse failure — the caller treats that
    as 'leave alone', NOT 'reap'."""
    if not isinstance(value, str) or not value:
        return None
    text = value
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _entry_is_active(entry: dict) -> bool:
    """An entry is ACTIVE when:
      - ``pid == 0`` (reserved — slot held during the
        microseconds between ``acquire_run_slot`` and
        ``update_pid``) AND it's younger than the
        ``pid=0`` age-out threshold (v1.5.7 126), OR
      - the pid is alive per ``_pid_alive``.

    A dead-pid entry is INACTIVE and gets pruned on the
    next read_active_runs call.

    v1.5.7 126: a ``pid=0`` entry older than
    ``_pid_zero_max_age_s()`` is a phantom reservation left
    by a launcher HARD-killed between acquire and update_pid
    (bypassing the ``except BaseException`` release). It's
    reaped so the provider cap recovers automatically. A
    missing/malformed ``started_at`` is treated as fresh
    (return True) — never mass-reap on a parse failure."""
    pid = entry.get("pid", 0)
    if pid == 0:
        started = _parse_iso_utc(entry.get("started_at"))
        if started is None:
            return True
        age = (datetime.now(timezone.utc)
               - started).total_seconds()
        return age <= _pid_zero_max_age_s()
    if not _pid_alive(pid):
        return False
    # v1.5.7 155 Task C-zombie: pid is alive per os.kill(pid, 0), but
    # the OS table can hold a defunct (zombie) entry until launchd /
    # init reaps it. ``os.kill`` succeeds on a zombie because the pid
    # is in the table; the existing dead-pid reaper misses it. Cross-
    # check the run's status.json — if the worker has written
    # terminal_state, its work is done regardless of zombie-vs-alive
    # ambiguity, and the registry entry is stale.
    harness_run_dir = entry.get("harness_run_dir")
    run_index = entry.get("run_index")
    if harness_run_dir and isinstance(run_index, int):
        status_path = (Path(harness_run_dir)
                       / f"run-{run_index:02d}" / "status.json")
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
            if isinstance(status, dict) and status.get("terminal_state"):
                return False
        except (OSError, ValueError):
            pass  # missing/malformed status.json ⇒ still potentially in flight
    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def read_active_runs(
        *, registry_path: "Optional[Path]" = None,
        prune_dead: bool = True) -> "list[dict]":
    """Read the registry, optionally pruning entries whose
    PIDs are no longer alive. Returns the list of active
    entries in registration order.

    ``prune_dead=True`` (default) writes the pruned list
    back to disk so subsequent reads are O(active) instead
    of O(all-time)."""
    path = resolve_registry_path(registry_path)
    if not path.exists():
        return []
    with _locked_registry(path) as (data, write):
        entries = list(data.get("entries", []))
        active = [e for e in entries if _entry_is_active(e)]
        if prune_dead and len(active) != len(entries):
            data["entries"] = active
            write(data)
        return active


def counts_by_provider(
        *, registry_path: "Optional[Path]" = None,
        ) -> "dict[str, int]":
    """Return ``{provider: count_of_active_runs}``.
    Operators see this on ``qpb_harness status`` and the
    TUI header. Empty dict when nothing is in flight."""
    counts: "dict[str, int]" = {}
    for entry in read_active_runs(registry_path=registry_path):
        p = entry.get("provider", "?")
        counts[p] = counts.get(p, 0) + 1
    return counts


def acquire_run_slot(
        *,
        runner: str,
        harness_run_dir: Path,
        run_index: int,
        started_at: str,
        max_per_provider: "dict[str, int]",
        plan_pool_cap: "Optional[int]" = None,
        registry_path: "Optional[Path]" = None,
        poll_interval_s: float = 1.0,
        sleep_fn=time.sleep,
        max_wait_s: "Optional[float]" = None) -> None:
    """Wait until BOTH caps have capacity, then atomically
    reserve a slot (pid=0 placeholder). Caller updates the
    pid via ``update_pid`` after ``Popen``, and releases
    via ``release_run_slot`` when terminal.

    Two gates checked under one lock:
      * **Global per-provider cap**: count entries with
        matching provider against ``max_per_provider``.
      * **Per-plan pool cap** (when ``plan_pool_cap`` is
        not None): count entries with matching
        ``harness_run_dir`` AND ``runner`` against
        ``plan_pool_cap``. This is the **Task A.0 fix** —
        the slot is held for the run's lifetime, not just
        through spawn.

    Both caps under the SAME lock means cross-process
    racing is impossible (one process can't see a slot as
    free while another claims it).

    ``max_wait_s`` (default None = wait forever): raise
    ``TimeoutError`` if no slot opens within the budget.
    Useful for tests + operator-side safeguards.
    """
    provider = provider_for_runner(runner)
    global_cap = max_per_provider.get(provider, 1)
    path = resolve_registry_path(registry_path)
    deadline = (time.monotonic() + max_wait_s
                if max_wait_s is not None else None)
    while True:
        with _locked_registry(path) as (data, write):
            entries = [
                e for e in data.get("entries", [])
                if _entry_is_active(e)
            ]
            provider_count = sum(
                1 for e in entries
                if e.get("provider") == provider)
            plan_runner_count = sum(
                1 for e in entries
                if e.get("harness_run_dir")
                    == str(harness_run_dir)
                and e.get("runner") == runner)
            ok_global = provider_count < global_cap
            ok_plan = (plan_pool_cap is None
                        or plan_runner_count < plan_pool_cap)
            if ok_global and ok_plan:
                entries.append({
                    "pid": 0,  # reserving; update via update_pid
                    "runner": runner,
                    "provider": provider,
                    "harness_run_dir": str(harness_run_dir),
                    "run_index": run_index,
                    "started_at": started_at,
                })
                data["entries"] = entries
                write(data)
                return
        if (deadline is not None
                and time.monotonic() >= deadline):
            raise TimeoutError(
                f"125: acquire_run_slot timed out after "
                f"{max_wait_s}s waiting for capacity "
                f"(provider={provider} cap={global_cap} "
                f"in-flight={provider_count}; "
                f"plan-runner={runner} "
                f"plan-cap={plan_pool_cap} "
                f"plan-in-flight={plan_runner_count})"
            )
        sleep_fn(poll_interval_s)


def update_pid(
        *,
        harness_run_dir: Path,
        run_index: int,
        pid: int,
        registry_path: "Optional[Path]" = None) -> None:
    """Set the ``pid`` on the existing reservation. Called
    by the launch site after ``Popen`` returns and we know
    the real PID. Idempotent — silently skips when no
    matching entry exists (the slot was released early or
    the reservation was somehow lost)."""
    path = resolve_registry_path(registry_path)
    if not path.exists():
        return
    with _locked_registry(path) as (data, write):
        entries = list(data.get("entries", []))
        for e in entries:
            if (e.get("harness_run_dir")
                    == str(harness_run_dir)
                    and e.get("run_index") == run_index):
                e["pid"] = pid
                data["entries"] = entries
                write(data)
                return


def release_run_slot(
        *,
        harness_run_dir: Path,
        run_index: int,
        registry_path: "Optional[Path]" = None) -> None:
    """Remove the entry for ``(harness_run_dir, run_index)``.
    Called by the collector when the run reaches a
    terminal state. Idempotent (no-op if no matching
    entry)."""
    path = resolve_registry_path(registry_path)
    if not path.exists():
        return
    with _locked_registry(path) as (data, write):
        entries = list(data.get("entries", []))
        new_entries = [
            e for e in entries
            if not (e.get("harness_run_dir")
                    == str(harness_run_dir)
                    and e.get("run_index") == run_index)
        ]
        if len(new_entries) != len(entries):
            data["entries"] = new_entries
            write(data)


def format_global_summary(
        *, registry_path: "Optional[Path]" = None,
        max_per_provider: "Optional[dict[str, int]]" = None,
        ) -> str:
    """v1.5.7 125 Task C: render a one-line operator-facing
    summary of global in-flight counts per provider, with
    caps when known. Empty registry ⇒ "(no runs in
    flight)".

    Format: ``in-flight: anthropic 2/2  openai 1/3  github
    0/3``. Shown on ``qpb_harness status`` and the TUI
    header."""
    counts = counts_by_provider(registry_path=registry_path)
    if not counts and max_per_provider is None:
        return "in-flight: (no runs in flight)"
    caps = max_per_provider or DEFAULT_MAX_PER_PROVIDER
    parts: list[str] = []
    # Stable ordering for the operator: caps-known providers
    # first (in insertion order), then any in-flight that
    # aren't in the caps map.
    seen: set[str] = set()
    for prov, cap in caps.items():
        count = counts.get(prov, 0)
        parts.append(f"{prov} {count}/{cap}")
        seen.add(prov)
    for prov, count in counts.items():
        if prov in seen:
            continue
        parts.append(f"{prov} {count}/?")
    return "in-flight: " + "  ".join(parts)


__all__ = [
    "PROVIDER_BY_RUNNER",
    "DEFAULT_MAX_PER_PROVIDER",
    "provider_for_runner",
    "resolve_registry_path",
    "parse_max_per_provider_spec",
    "read_active_runs",
    "counts_by_provider",
    "acquire_run_slot",
    "update_pid",
    "release_run_slot",
    "format_global_summary",
    # Internal — exposed for testability:
    "_pid_alive",
    "_entry_is_active",
    "_locked_registry",
    "_pid_zero_max_age_s",
    "_parse_iso_utc",
    "_PID_ZERO_MAX_AGE_S",
]
