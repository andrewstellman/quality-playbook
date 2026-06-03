"""v1.5.7 180-followup-8 FINDING-17: launch.log reader helpers.

Standalone module so ``status.py`` / ``tui.py`` can surface
the last in-flight step for RUNNING entries without
re-importing ``plan_runner`` (avoids a renderer → plan-runner
back-edge that risks circular imports).

Public API:
  - ``read_last_breadcrumb(log_path)`` — returns the full last
    breadcrumb dict (step + t_relative + t_absolute + kwargs)
    or ``None`` on missing / empty / non-JSON last line.
    v1.5.7 180-followup-9 FINDING-19: mtime-keyed cached.
  - ``read_last_step(log_path)`` — convenience: just the
    ``step`` string from the last breadcrumb, or ``None``.
  - ``format_inflight_step(log_path)`` — render-ready cell.
  - ``clear_cache()`` — test helper / debugging escape hatch.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


# v1.5.7 180-followup-9 FINDING-19: mtime-keyed cache for
# launch.log reads. TUI redraws can re-read every RUNNING
# entry's launch.log on every refresh; mtime check short-
# circuits the re-parse when the file is unchanged.
# Key: str(path). Value: (mtime_ns, parsed_entry_or_None).
_LAUNCH_LOG_CACHE: "dict[str, tuple[int, Optional[Dict[str, Any]]]]" = {}


def _read_last_breadcrumb_uncached(
        log_path: Path) -> "Optional[Dict[str, Any]]":
    """v1.5.7 180-followup-9 FINDING-19: the uncached read
    body, extracted so the cached wrapper can fall through
    when mtime indicates the file changed (or stat fails)."""
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            lines = [ln for ln in f.read().splitlines()
                      if ln.strip()]
    except OSError:
        return None
    if not lines:
        return None
    try:
        entry = json.loads(lines[-1])
    except (json.JSONDecodeError, ValueError):
        return None
    return entry if isinstance(entry, dict) else None


def read_last_breadcrumb(
        log_path: Path) -> "Optional[Dict[str, Any]]":
    """v1.5.7 180-followup-8 FINDING-17 + 180-followup-9
    FINDING-19: cached read of the last breadcrumb. Cache key
    is ``str(log_path)``; cache value is
    ``(mtime_ns, entry-or-None)``. Cache hit when the file's
    current mtime matches the cached entry; otherwise (or on
    stat error) falls through to the uncached read.

    Best-effort throughout — any ``OSError`` from ``os.stat``
    silently triggers an uncached read; the uncached reader
    returns None for missing/unreadable files."""
    key = str(log_path)
    try:
        mtime_ns = os.stat(log_path).st_mtime_ns
    except OSError:
        # File missing / unreadable — bypass cache; uncached
        # reader returns None. Do NOT cache the miss because a
        # subsequent stat success would still need a fresh read.
        return _read_last_breadcrumb_uncached(log_path)
    cached = _LAUNCH_LOG_CACHE.get(key)
    if cached is not None and cached[0] == mtime_ns:
        return cached[1]
    entry = _read_last_breadcrumb_uncached(log_path)
    _LAUNCH_LOG_CACHE[key] = (mtime_ns, entry)
    return entry


def clear_cache() -> None:
    """v1.5.7 180-followup-9 FINDING-19: test helper +
    debugging escape hatch. Renderers shouldn't need this in
    production, but tests that re-write the same path across
    cases need a clean slate."""
    _LAUNCH_LOG_CACHE.clear()


def read_last_step(log_path: Path) -> "Optional[str]":
    """Convenience: ``read_last_breadcrumb``'s ``step`` field
    or None. Kept for callers that only need the step name
    and don't want to unpack the dict themselves. Inherits
    FINDING-19's mtime-keyed caching via the underlying call."""
    entry = read_last_breadcrumb(log_path)
    if entry is None:
        return None
    step = entry.get("step")
    return step if isinstance(step, str) else None


def format_inflight_step(
        log_path: Path) -> "Optional[str]":
    """v1.5.7 180-followup-8 FINDING-17: a render-ready string
    for a RUNNING entry's "in-flight step" cell. Format:
    ``<step> (T+<seconds>s)`` when t_relative is available;
    just ``<step>`` otherwise. None when no breadcrumbs exist
    yet (let the renderer show "—"). Inherits FINDING-19's
    mtime-keyed caching via ``read_last_breadcrumb``."""
    entry = read_last_breadcrumb(log_path)
    if entry is None:
        return None
    step = entry.get("step")
    if not isinstance(step, str):
        return None
    t_rel = entry.get("t_relative")
    if isinstance(t_rel, (int, float)):
        return f"{step} (T+{t_rel:.1f}s)"
    return step
