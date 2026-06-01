"""v1.5.7 180-followup-8 FINDING-17: launch.log reader helpers.

Standalone module so ``status.py`` / ``tui.py`` can surface
the last in-flight step for RUNNING entries without
re-importing ``plan_runner`` (avoids a renderer → plan-runner
back-edge that risks circular imports).

Public API:
  - ``read_last_breadcrumb(log_path)`` — returns the full last
    breadcrumb dict (step + t_relative + t_absolute + kwargs)
    or ``None`` on missing / empty / non-JSON last line.
  - ``read_last_step(log_path)`` — convenience: just the
    ``step`` string from the last breadcrumb, or ``None``.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional


def read_last_breadcrumb(
        log_path: Path) -> "Optional[Dict[str, Any]]":
    """v1.5.7 180-followup-8 FINDING-17: return the most recent
    breadcrumb entry from ``launch.log`` as a dict (step +
    t_relative + t_absolute + any kwargs). The TUI/status
    renderers use this to surface "currently at step X
    (T+Ys)" for RUNNING entries.

    Returns ``None`` when the file is missing, empty, the
    last non-empty line is not valid JSON, or the parsed
    object isn't a dict. Best-effort — callers must tolerate
    None and render a fallback (typically ``"—"`` or empty).
    """
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


def read_last_step(log_path: Path) -> "Optional[str]":
    """Convenience: ``read_last_breadcrumb``'s ``step`` field
    or None. Kept for callers that only need the step name
    and don't want to unpack the dict themselves."""
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
    yet (let the renderer show "—")."""
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
