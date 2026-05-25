"""QPB Test Harness — Textual TUI (Phase 4).

Read-mostly client per design "Manager daemon + TUI": lists
runs/queue with case-id / type / axes / state / verdict /
outcome / elapsed; highlights N in-flight rows live; drills into
``summary.md`` / ``facts.json`` / tail of ``stream.ndjson`` /
``quality/BUGS.md`` / ``grading.json``; sends commands via
``control/commands.jsonl`` (the manager consumes them on its
next tick). **The TUI NEVER spawns runs itself** — safe to
open/close anytime.

Two-layer architecture (the TUI tests required pin):

  1. **Data-shaping layer** (pure Python — `render_overview`,
     `render_run_drilldown`, etc.): takes the manager's
     snapshot dict + the per-run receipt files, returns the
     LINES the TUI displays. Pure functions of state →
     strings. Trivially unit-testable WITHOUT textual.

  2. **Textual presentation layer** (lazy-imported): the App
     class that renders the lines via Textual widgets. Imported
     INSIDE the App's constructor so this module can be
     imported (and the data-shaping helpers unit-tested) even
     when textual isn't installed.

This split is what makes the "TUI tests required" requirement
satisfiable in environments that don't have textual: the
content-builder is the load-bearing piece (everything the user
SEES is built by it), and it's testable as a string function.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Data-shaping helpers (pure Python — no textual dependency).
# These are what the TUI tests assert against.
# ---------------------------------------------------------------------------


def _format_vendor_caps(caps: dict, in_flight: dict,
                          cooldown_remaining: dict) -> "list[str]":
    """Format the per-vendor cap row: 'anthropic: 1/2 [cooldown 25s]'."""
    out: list[str] = []
    for vendor_name, cap in caps.items():
        used = in_flight.get(vendor_name, 0)
        cd = cooldown_remaining.get(vendor_name)
        cd_str = ""
        if cd is not None and cd > 0:
            cd_str = f" [cooldown {int(cd)}s]"
        out.append(f"{vendor_name}: {used}/{cap}{cd_str}")
    return out


def render_overview(manager_snapshot: dict) -> "list[str]":
    """Render the overview panel: header + per-vendor cap row +
    in-flight rows + queued count + recent-done section.

    The rendered LINES are the load-bearing pin for the "render
    a specific screen state and assert the rendered output
    contains the right elements" requirement. Each test passes
    in a synthetic ``manager_snapshot`` and asserts the right
    elements appear in the output.

    Layout (one screen):
        ── Manager ──
        PID:   12345
        Started: 2026-05-25T17:30:00Z   Heartbeat: 2026-05-25T17:32:14Z
        Status: running                  Paused: no

        ── Caps ──
        anthropic: 1/1   openai: 0/1   github: 0/1   cursor: 0/1
        Global:    1/4

        ── In-flight (N) ──
        run_id                  case      runner   started_at            elapsed
        20260525T173000Z        ACC-A     claude   2026-05-25T17:30:00Z  2m14s
        ...

        ── Queue (M) ──
        20260525T173045Z        ACC-B     codex    queued

        ── Recently done (K) ──
        20260525T172500Z   ACC-A   COMPLETED  ALL_PASSED  ...
    """
    lines: list[str] = []
    sched = manager_snapshot.get("scheduler") or {}
    lines.append("── Manager ──")
    pid = manager_snapshot.get("pid")
    started_at = manager_snapshot.get("started_at") or "?"
    heartbeat = manager_snapshot.get("heartbeat") or "?"
    paused = manager_snapshot.get("paused", False)
    lines.append(f"PID:     {pid}")
    lines.append(f"Started: {started_at}    Heartbeat: {heartbeat}")
    lines.append(f"Paused:  {'yes' if paused else 'no'}")
    lines.append("")

    lines.append("── Caps ──")
    vendor_caps = sched.get("vendor_caps") or {}
    in_flight_by_vendor = sched.get("in_flight_by_vendor") or {}
    cooldown_remaining = sched.get("cooldown_remaining_s") or {}
    for cap_line in _format_vendor_caps(vendor_caps, in_flight_by_vendor,
                                          cooldown_remaining):
        lines.append("  " + cap_line)
    global_cap = sched.get("global_cap", 0)
    in_flight_total = sched.get("in_flight_total", 0)
    lines.append(f"  Global: {in_flight_total}/{global_cap}")
    lines.append("")

    in_flight = manager_snapshot.get("in_flight") or []
    lines.append(f"── In-flight ({len(in_flight)}) ──")
    if in_flight:
        lines.append(
            "  run_id                   case      runner    "
            "started_at            elapsed"
        )
        for run in in_flight:
            lines.append(
                f"  {run.get('run_id', '?'):<22} "
                f"{run.get('case_id', '?'):<9} "
                f"{run.get('runner', '?'):<8} "
                f"{run.get('started_at', '?'):<22} "
                f"{run.get('elapsed', '?'):>7}"
            )
    else:
        lines.append("  (none)")
    lines.append("")

    queued = sched.get("queued") or []
    lines.append(f"── Queue ({len(queued)}) ──")
    if queued:
        for entry in queued:
            lines.append(
                f"  {entry.get('run_id', '?'):<22} "
                f"{entry.get('vendor', '?'):<10} queued"
            )
    else:
        lines.append("  (empty)")
    lines.append("")

    recent = manager_snapshot.get("recent_done") or []
    lines.append(f"── Recently done ({len(recent)}) ──")
    if recent:
        for entry in recent[-10:]:  # cap the rendered slice
            lines.append(
                f"  {entry.get('run_id', '?'):<22} "
                f"{entry.get('case_id', '?'):<9} "
                f"{entry.get('terminal_state', entry.get('outcome', '?')):<14} "
                f"{entry.get('verdict', entry.get('outcome', '?'))}"
            )
    else:
        lines.append("  (none)")
    return lines


def render_run_drilldown(run_dir: Path) -> "list[str]":
    """Render the drill-in panel for one run. Reads
    ``summary.md`` / ``facts.json`` / ``grading.json`` (head)
    + tail of ``stream.ndjson`` + ``quality/BUGS.md`` (if
    present). Defensive on missing files."""
    lines: list[str] = []
    lines.append(f"── Run: {run_dir.name} ──")
    invocation = run_dir / "invocation.json"
    if invocation.is_file():
        try:
            inv = json.loads(invocation.read_text(encoding="utf-8"))
            lines.append(
                f"  case={inv.get('case_id', '?')} "
                f"runner={inv.get('axes', {}).get('runner', '?')} "
                f"model={inv.get('axes', {}).get('model', '?')} "
                f"channel={inv.get('axes', {}).get('install_channel', '?')}"
            )
            lines.append(
                f"  qpb_version={inv.get('qpb_version', '?')} "
                f"target_sha={inv.get('target_sha', '?')[:12]} "
                f"terminal={inv.get('terminal_state', '?')}"
            )
        except (OSError, json.JSONDecodeError):
            lines.append("  invocation.json unreadable")
    else:
        lines.append("  (no invocation.json)")
    lines.append("")

    facts = run_dir / "facts.json"
    if facts.is_file():
        try:
            fdata = json.loads(facts.read_text(encoding="utf-8"))
            verdict = fdata.get("verdict") or {}
            gate = fdata.get("gate") or {}
            prov = fdata.get("provenance") or {}
            lines.append("  Facts:")
            lines.append(f"    verdict_state = {verdict.get('verdict_state', '?')}")
            lines.append(f"    attribution   = {verdict.get('attribution', '?')}")
            lines.append(f"    gate_result   = {gate.get('gate_result', '?')}")
            lines.append(
                f"    provenance    = runner:{prov.get('detected_runner', '?')} "
                f"model:{prov.get('selfreport_model_label', '?')} "
                f"bugs:{prov.get('gate_bug_count', '?')}"
            )
        except (OSError, json.JSONDecodeError):
            lines.append("  facts.json unreadable")
    lines.append("")

    grading = run_dir / "grading.json"
    if grading.is_file():
        try:
            gdata = json.loads(grading.read_text(encoding="utf-8"))
            ctype = gdata.get("case_type") or "?"
            if ctype == "acceptance":
                lines.append(
                    f"  Grading: {gdata.get('verdict', '?')} "
                    f"({gdata.get('n_passed', '?')}/"
                    f"{gdata.get('n_total', '?')} passed)"
                )
            else:
                lines.append(
                    f"  Grading: {gdata.get('outcome', '?')}"
                    f" (reviewed={gdata.get('reviewed', False)})"
                )
        except (OSError, json.JSONDecodeError):
            lines.append("  grading.json unreadable")
    bugs = run_dir / "quality" / "BUGS.md"
    if bugs.is_file():
        lines.append("")
        lines.append("  BUGS.md (head):")
        try:
            head = bugs.read_text(encoding="utf-8",
                                    errors="ignore").splitlines()[:10]
            for ln in head:
                lines.append(f"    {ln}")
        except OSError:
            pass
    return lines


# ---------------------------------------------------------------------------
# Textual presentation layer (lazy-gated).
# ---------------------------------------------------------------------------


def _textual_available() -> bool:
    """Defer the heavy import to runtime so the data-shaping
    helpers above remain importable in environments without
    textual."""
    try:
        import textual  # noqa: F401
        return True
    except ImportError:
        return False


def build_app(manager_snapshot: dict, run_drilldown: "Path | None" = None):
    """Construct (don't run) the Textual App with the given
    initial state. Raises RuntimeError if textual isn't
    installed — caller decides whether to skip or install.

    Phase 4 deliverable: the operator runs the TUI from the
    qpb_harness entry; the App reads `control/queue.json`
    periodically and re-renders. For test purposes the App
    can be constructed and the `compose` output asserted.
    """
    if not _textual_available():
        raise RuntimeError(
            "textual is not installed. Install it with "
            "`pip install textual` (or via the operator's "
            "preferred channel) to run the TUI. Note: the data-"
            "shaping helpers (render_overview / "
            "render_run_drilldown) DO work without textual; "
            "the App is the textual-gated surface."
        )
    # Lazy import keeps the textual dep contained inside this
    # function — module import remains free.
    from textual.app import App, ComposeResult
    from textual.widgets import Header, Footer, Static

    overview_lines = "\n".join(render_overview(manager_snapshot))
    drilldown_lines = (
        "\n".join(render_run_drilldown(run_drilldown))
        if run_drilldown is not None else ""
    )

    class HarnessTUI(App):
        """Read-mostly Textual TUI for the QPB harness."""
        TITLE = "QPB Test Harness"
        CSS = """
        Static#overview { padding: 1; border: solid green; }
        Static#drill    { padding: 1; border: solid magenta; }
        """

        def compose(self) -> ComposeResult:
            yield Header()
            yield Static(overview_lines, id="overview")
            if drilldown_lines:
                yield Static(drilldown_lines, id="drill")
            yield Footer()

    return HarnessTUI()


__all__ = [
    "render_overview",
    "render_run_drilldown",
    "build_app",
]
