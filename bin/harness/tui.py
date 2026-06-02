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
    # v1.5.7 111 — live status TUI on top of 110's status.py.
    "build_runs_list_rows",
    "build_run_detail_rows",
    "build_output_lines",
    "launch_status_tui",
    # v1.5.7 116 — exported for the cursor-clamp unit tests.
    "_clamp_cursor",
    # v1.5.7 119 — Textual rebuild: view-model builders +
    # launch entry. Textual is a dev/harness-only optional
    # dependency; the launch fn lazy-imports it.
    "build_runs_table_rows",
    "build_detail_table_rows",
    "build_rendered_output_lines",
    "RUNS_TABLE_COLUMNS",
    "DETAIL_TABLE_COLUMNS",
    "launch_textual_tui",
    # v1.5.7 121 — pure text formatters (used by `c` copy
    # AND `--dump <page>`; no textual dependency).
    "format_runs_list_as_text",
    "format_detail_as_text",
    "format_output_as_text",
]


# ---------------------------------------------------------------------------
# v1.5.7 111 — live status TUI (stdlib curses) over 110's status.py
# ---------------------------------------------------------------------------
#
# The TUI is a thin presentation layer: all data reads go through
# `bin/harness/status.py` (the pure read-model layer from 110).
# The view-model builders below produce strings that the curses
# event loop renders verbatim — keeps the testable boundary
# unambiguous (the view-models are pure functions; the curses
# entry is only called from the CLI).
#
# Three navigation levels:
#   1. Harness-runs list — newest first; per run: dir/age,
#      R/D/F/T/AP/P counts, collector-live?
#   2. Run detail — per-repo rows: index, repo, runner/model,
#      state, current phase + name + state, result, pid(live?).
#   3. Live output — `status.tail_stream` on the selected run.
#
# Auto-refresh ~2s at list + detail levels; `r` forces refresh;
# `q`/Esc goes back / quits; arrows navigate. Read-only —
# never mutates run state. Curses `wrapper(...)` guarantees
# terminal restore on exit/exception.


def build_runs_list_rows(runs_root: Path) -> "list[str]":
    """v1.5.7 111: view-model for the top-level harness-runs
    list. Returns the lines the TUI renders verbatim. Reads
    via ``status.list_harness_runs``.

    Header row + one line per harness-run (newest first) +
    a footer with the count. Returns just a header + footer
    message when ``runs_root`` is empty/missing.
    """
    from bin.harness import status as _status

    summaries = _status.list_harness_runs(runs_root)
    lines: list[str] = []
    lines.append(
        f"Harness runs under {runs_root}  "
        f"(↑/↓ navigate · Enter drill in · q quit · r refresh)"
    )
    lines.append("")
    if not summaries:
        lines.append("(no harness-runs yet)")
        return lines
    lines.append(
        f"{'harness-run':30}  {'started-at':22}  "
        f"{'runs':>4}  {'R':>2} {'D':>2} {'F':>2} "
        f"{'T':>2} {'AP':>2} {'P':>2}  {'collector':9}"
    )
    for s in summaries:
        coll = "live" if s.collector_alive else "—"
        lines.append(
            f"{s.harness_run_dir.name:30}  "
            f"{s.started_at:22}  "
            f"{s.total_runs:>4}  "
            f"{s.running:>2} {s.completed:>2} "
            f"{s.failed:>2} {s.timed_out:>2} "
            f"{s.aborted_prep:>2} {s.pending:>2}  "
            f"{coll:9}"
        )
    lines.append("")
    lines.append(f"{len(summaries)} harness-run(s)")
    return lines


def build_run_detail_rows(harness_run_dir: Path) -> "list[str]":
    """v1.5.7 111: view-model for the drill-down of one
    harness-run. Per-repo state + current phase + result +
    pid(live?). Returns the lines the TUI renders verbatim.

    Degrades gracefully: missing/empty manifest ⇒ a single
    "(no manifest)" line so the renderer always has content.
    """
    from bin.harness import status as _status

    runs = _status.read_run_status(harness_run_dir)
    lines: list[str] = []
    lines.append(
        f"Harness run: {harness_run_dir.name}  "
        f"(↑/↓ navigate · Enter watch output · "
        f"q/Esc back · r refresh)"
    )
    lines.append("")
    if not runs:
        lines.append(
            "(no manifest.json yet — run mid-launch, "
            "or run-plan hasn't completed launch)"
        )
        return lines
    lines.append(
        f"{'#':>3}  {'repo':18}  "
        f"{'runner/model':22}  "
        f"{'state':14}  {'phase':28}  "
        f"{'result':10}  {'pid':12}"
    )
    for rs in runs:
        repo_tail = (
            rs.repo.rstrip("/").split("/")[-1] or rs.repo
        )
        phase_part = (
            f"{rs.current_phase} "
            f"{rs.current_phase_name} "
            f"{rs.current_phase_state}"
            if rs.current_phase != "—"
            else "—"
        )
        pid_part = (
            f"{rs.pid}(live)" if rs.pid_alive
            else (f"{rs.pid}(dead)" if rs.pid else "—")
        )
        lines.append(
            f"{rs.index:>3}  {repo_tail[:18]:18}  "
            f"{(rs.runner + '/' + rs.model)[:22]:22}  "
            f"{rs.state[:14]:14}  {phase_part[:28]:28}  "
            f"{rs.result[:10]:10}  {pid_part[:12]:12}"
        )
        if rs.last_note:
            # Indented note line — operator-friendly.
            lines.append(f"     note: {rs.last_note[:80]}")
    return lines


def build_output_lines(run_dir: Path,
                        max_lines: int = 200) -> "list[str]":
    """v1.5.7 111: view-model for the live-output pane.
    Returns up to ``max_lines`` lines from
    ``<run_dir>/stream.ndjson`` (newest at the end), each
    rendered via ``status.render_stream_line`` so sentinels
    are human-readable.

    Robust to missing stream.ndjson — returns a header + a
    "(no stream yet)" line. The TUI tails the file; if it
    grows during render, a subsequent refresh picks up new
    lines.
    """
    from bin.harness import status as _status

    lines: list[str] = []
    lines.append(
        f"Live output: {run_dir.name}  "
        f"(q/Esc back · auto-refreshes)"
    )
    lines.append("")
    stream_path = run_dir / "stream.ndjson"
    if not stream_path.is_file():
        lines.append("(no stream.ndjson yet)")
        return lines
    # Use tail_stream with follow=False; cap at max_lines.
    rendered = list(_status.tail_stream(run_dir, follow=False))
    if not rendered:
        lines.append("(stream.ndjson is empty)")
        return lines
    if len(rendered) > max_lines:
        lines.append(
            f"(showing last {max_lines} of {len(rendered)} "
            f"lines)"
        )
        rendered = rendered[-max_lines:]
    lines.extend(rendered)
    return lines


def launch_status_tui(
        runs_root: Path,
        *,
        initial_focus: "Optional[tuple]" = None,
) -> int:
    """v1.5.7 111: the curses entry point. Three navigation
    levels: harness-runs list → run detail → live output.

    Side-effect-free import: this function is only called from
    the CLI (``qpb_harness tui --runs-root <DIR>``); importing
    ``bin.harness.tui`` does NOT start curses. The
    ``curses.wrapper`` ensures the terminal is restored on
    exit AND on any uncaught exception.

    v1.5.7 139: ``initial_focus`` (``(TuiPathKind, Path)`` or None)
    opens the loop at a deeper screen — see
    ``_resolve_initial_nav_state``. None ⇒ pre-139 runs-list.

    v1.5.7 180-followup-5 FINDING-7: ``curses`` is not part of
    the Python stdlib on Windows (the ``_curses`` C extension
    isn't shipped). When the import fails AND we're on Windows,
    print an install hint (``pip install textual`` or
    ``pip install windows-curses``) and degrade gracefully to
    the ``--dump runs`` non-interactive renderer. On POSIX the
    ImportError is re-raised — curses is part of stdlib there
    and a missing ``_curses`` is a real installation problem.
    """
    import sys
    from bin.harness import _platform as _platform_mod
    try:
        import curses
    except ImportError:
        if _platform_mod.IS_WINDOWS:
            print(
                "qpb_harness tui: 'curses' is not available on "
                "this Windows Python installation (_curses C "
                "extension not shipped).\n"
                "Install one of the following:\n"
                "  pip install textual          # recommended — "
                "richer UI\n"
                "  pip install windows-curses   # smaller — "
                "provides _curses\n"
                "\nFalling back to `tui --dump runs` output:\n",
                file=sys.stderr,
            )
            print(format_runs_list_as_text(runs_root))
            return 0
        # POSIX: curses should be present. Re-raise so the
        # operator sees the real install error.
        raise

    def _main(stdscr: "curses._CursesWindow") -> int:  # type: ignore[name-defined]
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.timeout(2000)  # auto-refresh ~2s
        return _event_loop(stdscr, runs_root,
                            initial_focus=initial_focus)

    return curses.wrapper(_main)


# Navigation states.
_NAV_LIST = "list"
_NAV_DETAIL = "detail"
_NAV_OUTPUT = "output"


def _resolve_initial_nav_state(
        initial_focus: "Optional[tuple]" = None,
) -> "tuple[str, Optional[Path], Optional[Path]]":
    """v1.5.7 139: derive the initial ``(nav, current_dir,
    current_run_dir)`` for a deep-entry, shared by the textual App
    (``on_mount``) and the curses ``_event_loop`` so both open at
    the same screen AND wire the same back-nav parent targets.

    ``initial_focus`` is ``(TuiPathKind, Path)`` or None:
      * None / RUNS_ROOT      → ``(LIST, None, None)`` — pre-139.
      * (HARNESS_RUN, path)   → ``(DETAIL, path, None)``.
      * (RUN_NN, path)        → ``(OUTPUT, path.parent, path)`` —
        ``current_dir`` is the parent harness-run so q/esc from the
        output page lands on its detail page (then runs-list, then
        exit), exactly as a manual drill-down would.
    """
    if initial_focus is None:
        return (_NAV_LIST, None, None)
    from bin.harness.status import TuiPathKind
    kind, path = initial_focus
    if kind is TuiPathKind.RUN_NN:
        return (_NAV_OUTPUT, path.parent, path)
    if kind is TuiPathKind.HARNESS_RUN:
        return (_NAV_DETAIL, path, None)
    return (_NAV_LIST, None, None)


def _should_pause_follow(
        scroll_y: int, max_scroll_y: int, *,
        manual_scroll_event: bool, currently_paused: bool,
        user_pressed_f: bool) -> bool:
    """v1.5.7 140: pure follow-pause decision for the output
    screen. Shared, unit-testable seam — the textual integration
    that calls it (focus + scroll capture/restore) is
    operator-confirmable via a TTY, per the 139 pattern.

    The 'less +F' / chat-log idiom: follow the tail until the
    operator scrolls up, then pause (preserve their viewport) until
    they return to the bottom or press ``f``.

      * ``user_pressed_f`` → explicit toggle (the manual override).
      * paused AND back at the bottom (``scroll_y >= max_scroll_y``)
        → resume (return False).
      * following AND a manual scroll-up (``scroll_y <
        max_scroll_y``) → pause (return True).
      * otherwise → unchanged.
    """
    if user_pressed_f:
        return not currently_paused
    at_bottom = scroll_y >= max_scroll_y
    if currently_paused and at_bottom:
        return False
    if (not currently_paused and manual_scroll_event
            and scroll_y < max_scroll_y):
        return True
    return currently_paused


def _confirm_kill_decision(input_char: str) -> bool:
    """v1.5.7 147: pure confirm decision for the TUI `k` kill flow —
    True iff the operator pressed ``y`` (case-INsensitive). Any
    other key cancels. The testable seam; the textual key-event
    wiring that calls it is closure-local (119 no-textual invariant,
    per 139/140)."""
    return input_char.strip().lower() == "y"


def _clamp_cursor(idx: int, n_rows: int) -> int:
    """v1.5.7 116: clamp the TUI selection cursor to the
    selectable range ``[0, max(0, n_rows - 1)]``.

    Pure helper extracted so the curses event loop's nav math
    can be unit-tested without spinning up curses. Used both at
    KEY_DOWN/KEY_UP press time (so the cursor doesn't visibly
    overshoot) and at the top of each event-loop iteration
    after the row count is recomputed (so a refresh that
    SHRINKS the list — a run dir disappearing, a view switch —
    can't leave the cursor pointing past the new last row).

    ``n_rows == 0`` ⇒ return 0 (no-selection sentinel; the
    render layer's ``i == selectable_first_row + selected_idx``
    check still has nothing to highlight when ``n_data_rows``
    is also 0). Negative ``idx`` ⇒ return 0 (KEY_UP guard
    sanity-check).

    Pre-116 KEY_DOWN incremented unconditionally; pressing ↓
    past the last row made the cursor drift off the end and
    the highlight disappear until KEY_UP brought it back into
    range one press at a time.
    """
    if n_rows <= 0:
        return 0
    return max(0, min(idx, n_rows - 1))


def _event_loop(stdscr, runs_root: Path,
                *, initial_focus: "Optional[tuple]" = None) -> int:
    """v1.5.7 111: the TUI's main loop. NOT directly unit
    tested (curses is hard to fixture); the view-model
    builders ABOVE are what tests exercise. This function is
    a thin glue layer: read keys → update nav state → call a
    view-model builder → render lines.

    v1.5.7 139: ``initial_focus`` seeds the initial nav state via
    the shared ``_resolve_initial_nav_state`` (same semantics as
    the textual App), so q/esc back-nav from a deep-entry walks up
    to the parent screens identically."""
    import curses

    nav, current_dir, current_run_dir = _resolve_initial_nav_state(
        initial_focus)
    selected_idx = 0
    # v1.5.7 116: tracked across loop iterations so KEY_DOWN /
    # KEY_UP can clamp using the row count from the just-
    # rendered view. Re-set to the live count after each view's
    # row-build step below.
    n_data_rows = 0

    while True:
        try:
            stdscr.erase()
            max_y, max_x = stdscr.getmaxyx()
            if nav == _NAV_LIST:
                from bin.harness import status as _status
                summaries = _status.list_harness_runs(runs_root)
                lines = build_runs_list_rows(runs_root)
                n_data_rows = len(summaries)
                # v1.5.7 116: re-clamp BEFORE render so a
                # refresh-shrink (a run dir disappeared since
                # the last tick) can't leave the cursor
                # pointing past the new last row.
                selected_idx = _clamp_cursor(
                    selected_idx, n_data_rows)
                # Visual selection cursor on data rows
                # (skip the 3 header rows: title, blank,
                # column header).
                _render_lines(stdscr, lines, max_x, max_y,
                                selectable_first_row=3,
                                selected_idx=selected_idx,
                                n_data_rows=n_data_rows)
            elif nav == _NAV_DETAIL and current_dir is not None:
                from bin.harness import status as _status
                runs = _status.read_run_status(current_dir)
                lines = build_run_detail_rows(current_dir)
                n_data_rows = len(runs)
                # v1.5.7 116: same re-clamp for the DETAIL view.
                selected_idx = _clamp_cursor(
                    selected_idx, n_data_rows)
                # Header: 3 lines (title, blank, column hdr);
                # each run row has an optional indented note
                # line after it, so we can't just pick rows by
                # index — for simplicity, the cursor advances
                # by 1 per arrow press, clamped to n_data_rows.
                _render_lines(stdscr, lines, max_x, max_y,
                                selectable_first_row=3,
                                selected_idx=selected_idx,
                                n_data_rows=n_data_rows)
            elif nav == _NAV_OUTPUT and current_run_dir is not None:
                lines = build_output_lines(current_run_dir)
                n_data_rows = 0
                _render_lines(stdscr, lines, max_x, max_y,
                                selectable_first_row=0,
                                selected_idx=0,
                                n_data_rows=0)
            stdscr.refresh()
            ch = stdscr.getch()
            if ch == -1:
                continue
            if ch in (ord("q"), 27):  # q, Esc
                if nav == _NAV_OUTPUT:
                    nav = _NAV_DETAIL
                    selected_idx = 0
                elif nav == _NAV_DETAIL:
                    nav = _NAV_LIST
                    current_dir = None
                    selected_idx = 0
                else:
                    return 0
                continue
            if ch == ord("r"):
                continue  # falls through to next refresh
            if ch == curses.KEY_UP:
                # v1.5.7 116: clamp on press so the cursor
                # doesn't visibly under-run on row 0. (Pre-116
                # the `> 0` guard prevented under-run but
                # KEY_DOWN had no upper guard.)
                selected_idx = _clamp_cursor(
                    selected_idx - 1, n_data_rows)
                continue
            if ch == curses.KEY_DOWN:
                # v1.5.7 116: clamp on press so the cursor
                # doesn't overrun past the last row. Pre-116
                # the unclamped `+= 1` made the highlight
                # disappear when the cursor exceeded
                # n_data_rows; KEY_UP only clamped the low
                # end, so the user had to press ↑ several
                # extra times to bring the cursor back.
                selected_idx = _clamp_cursor(
                    selected_idx + 1, n_data_rows)
                continue
            if ch in (curses.KEY_ENTER, 10, 13):
                if nav == _NAV_LIST:
                    from bin.harness import status as _status
                    summaries = _status.list_harness_runs(
                        runs_root
                    )
                    if 0 <= selected_idx < len(summaries):
                        current_dir = summaries[
                            selected_idx
                        ].harness_run_dir
                        nav = _NAV_DETAIL
                        selected_idx = 0
                    continue
                if nav == _NAV_DETAIL and current_dir:
                    from bin.harness import status as _status
                    runs = _status.read_run_status(
                        current_dir
                    )
                    if 0 <= selected_idx < len(runs):
                        current_run_dir = runs[
                            selected_idx
                        ].run_dir
                        nav = _NAV_OUTPUT
                    continue
        except KeyboardInterrupt:
            return 0


def _render_lines(stdscr, lines: "list[str]",
                   max_x: int, max_y: int, *,
                   selectable_first_row: int,
                   selected_idx: int,
                   n_data_rows: int) -> None:
    """v1.5.7 111: blit a list of strings to the curses screen,
    truncating to terminal width. Highlights the selected data
    row (when there is one) via curses A_REVERSE.

    Terminal-resize tolerant: redraws every event-loop cycle
    so a SIGWINCH between iterations is handled by the next
    pass.
    """
    import curses
    for i, line in enumerate(lines):
        if i >= max_y - 1:
            break
        truncated = line[:max_x - 1]
        try:
            if (n_data_rows > 0
                    and i == selectable_first_row + selected_idx
                    and i < selectable_first_row + n_data_rows):
                stdscr.attron(curses.A_REVERSE)
                stdscr.addstr(i, 0, truncated)
                stdscr.attroff(curses.A_REVERSE)
            else:
                stdscr.addstr(i, 0, truncated)
        except curses.error:
            # Hit the bottom-right corner; harmless.
            pass


# ---------------------------------------------------------------------------
# v1.5.7 119 — Textual rebuild (scroll/mouse/follow-tail + auto-refresh)
# ---------------------------------------------------------------------------
#
# Architecture:
#   * **Pure view-model builders** (this section, immediately
#     below) shape the status.py model output into the table-
#     row tuples + rendered output lines the Textual widgets
#     consume. They have no textual dependency — testable
#     independently.
#   * **Textual App** (``launch_textual_tui`` at the bottom) is
#     a thin presentation layer with lazy textual import. The
#     module import stays side-effect-free + textual-optional
#     (111 invariant preserved); only the launch entry pulls
#     textual in.
#
# Dependency hygiene: `textual` is an OPTIONAL harness extra
# (`pip install quality-playbook[harness]`). The shipped
# channel closure excludes `bin/harness/` entirely (091
# invariant + a 119 bundle-safety re-pin), so no shipped
# module ever imports textual. Adopters who only consume the
# skill don't pay for it.


# Column headers for the Textual DataTable widgets. Exported so
# tests can pin their shape without instantiating the app.
RUNS_TABLE_COLUMNS = (
    "dir", "started", "total",
    "R", "D", "F", "T", "B", "AP", "P",
    "progress", "last_activity", "collector",
)

DETAIL_TABLE_COLUMNS = (
    "#", "repo", "runner/model", "state",
    "phase", "name", "phase-state", "result",
    "pid", "elapsed", "last_activity",
    # v1.5.7 180-followup-8 FINDING-17: in-flight launch step
    # for RUNNING entries (from run-NN/launch.log). Cell is
    # "—" for terminal entries (DONE/FAILED/etc.) — the
    # launch.log is forensic at that point, not status.
    "step",
)


def build_runs_table_rows(runs_root: Path) -> "list[tuple[str, ...]]":
    """v1.5.7 119: build the per-harness-run table rows for
    the Textual ``DataTable`` widget. Each row is a tuple of
    string cells matching ``RUNS_TABLE_COLUMNS`` 1:1.

    Pure transform over ``status.list_harness_runs`` — the
    same model layer the curses TUI + CLI ``status``
    consume. Surfaces 113's BLOCKED column and 117's
    ``progress`` + ``last_activity_iso`` so the operator
    sees the same data through both TUI implementations.
    """
    from bin.harness import status as _status
    summaries = _status.list_harness_runs(runs_root)
    rows: "list[tuple[str, ...]]" = []
    for s in summaries:
        rows.append((
            s.harness_run_dir.name,
            s.started_at,
            str(s.total_runs),
            str(s.running),
            str(s.completed),
            str(s.failed),
            str(s.timed_out),
            str(s.blocked),
            str(s.aborted_prep),
            str(s.pending),
            s.progress,
            s.last_activity_iso,
            "yes" if s.collector_alive else "no",
        ))
    return rows


def _format_pid_for_table(pid: "Optional[int]",
                            pid_alive: bool) -> str:
    if pid is None:
        return "—"
    return f"{pid}(live)" if pid_alive else f"{pid}(dead)"


def build_detail_table_rows(
        harness_run_dir: Path) -> "list[tuple[str, ...]]":
    """v1.5.7 119: build the per-run drill-down table rows
    matching ``DETAIL_TABLE_COLUMNS``. Includes 117's
    ``current_phase`` / ``current_phase_name`` / phase state
    AND 117's ``elapsed_s`` / ``last_activity_iso`` columns so
    operators see live phase progress + liveness without
    dropping into the output view."""
    from bin.harness import status as _status
    from bin.harness import _launch_log as _ll
    runs = _status.read_run_status(harness_run_dir)
    rows: "list[tuple[str, ...]]" = []
    for r in runs:
        repo_tail = (r.repo.rstrip("/").split("/")[-1]
                     or r.repo)
        # v1.5.7 180-followup-8 FINDING-17: surface the last
        # launch breadcrumb's step for RUNNING entries so
        # operators see "where am I" for hangs without
        # opening launch.log.
        step_cell = "—"
        if r.state in ("RUNNING", "PENDING"):
            inflight = _ll.format_inflight_step(
                r.run_dir / "launch.log")
            if inflight is not None:
                step_cell = inflight
        # v1.5.7 186 FINDING-35: augment the state cell with the
        # pending-duration string for PENDING rows. The state
        # cell already exists; this in-cell augment avoids a
        # column-arity change (which would break the 119
        # rebuild test's `len(rows[0]) == len(COLUMNS)` pin).
        state_cell = (
            f"{r.state} {r.pending_duration}"
            if r.state == "PENDING" and r.pending_duration
            else r.state
        )
        rows.append((
            str(r.index),
            repo_tail,
            f"{r.runner}/{r.model}",
            state_cell,
            r.current_phase,
            r.current_phase_name,
            r.current_phase_state,
            r.result,
            _format_pid_for_table(r.pid, r.pid_alive),
            _status._format_elapsed(r.elapsed_s),
            r.last_activity_iso,
            step_cell,
        ))
    return rows


# v1.5.7 119: a generous default cap so a long run's stream
# (~10k lines for a 4-repo Mode A run) renders without
# blowing memory or rendering latency. Operators who need
# the full stream can `qpb_harness tail` it.
_DEFAULT_OUTPUT_MAX_LINES = 5000


def build_rendered_output_lines(
        run_dir: Path,
        *,
        max_lines: int = _DEFAULT_OUTPUT_MAX_LINES,
        rendered: bool = True,
) -> "list[str]":
    """v1.5.7 119: read ``run_dir/stream.ndjson``, render each
    line via ``status.render_stream_line`` (so 109 sentinels
    show human-readably instead of as raw JSON), and return
    the last ``max_lines`` lines.

    v1.5.7 122 ``rendered`` toggle (default True):
      * True ⇒ each line goes through
        ``render_stream_line`` (Claude stream-json events
        templated into clean log lines via the 122 renderer;
        ::QPB:: sentinels rendered human-readably; non-Claude
        plain text passes through).
      * False ⇒ each line verbatim (raw debugging mode; the
        TUI `j` toggle and CLI `--raw` flag set this).

    Returns ``[]`` when the stream doesn't exist yet —
    callers should display "(no output yet)" rather than
    erroring.

    Bottom-anchored by construction: the last entry of the
    returned list is the newest. The Textual ``RichLog``
    widget then auto-scrolls to it under follow-mode.
    """
    from bin.harness import status as _status
    stream = run_dir / "stream.ndjson"
    if not stream.is_file():
        return []
    try:
        text = stream.read_text(
            encoding="utf-8", errors="ignore")
    except OSError:
        return []
    lines = text.splitlines()
    if rendered:
        out = [_status.render_stream_line(ln) for ln in lines]
    else:
        out = list(lines)
    if max_lines is not None and len(out) > max_lines:
        out = out[-max_lines:]
    return out


# v1.5.7 121: pure text formatters used by BOTH the Textual
# `c` (copy current screen) action AND the `--dump <page>`
# CLI form. textual is NOT required — these are plain text
# transforms over the status.py model. The `--dump` form is
# the testability hook: cowork / the worker can dump a page
# headlessly and verify rendering without an interactive
# terminal.


def _format_table_as_text(headers: "tuple[str, ...]",
                            rows: "list[tuple[str, ...]]") -> str:
    """Render a header + rows tuple as an aligned plain-text
    table (one column per element, padded to the widest cell
    in that column). Used by ``format_runs_list_as_text`` +
    ``format_detail_as_text``."""
    if not rows:
        return " | ".join(headers) + "\n(no rows)"
    widths = [len(h) for h in headers]
    for r in rows:
        for i, cell in enumerate(r):
            if i >= len(widths):
                break
            widths[i] = max(widths[i], len(str(cell)))
    fmt = " | ".join(f"{{:<{w}}}" for w in widths)
    lines: list[str] = [
        fmt.format(*headers),
        " | ".join("-" * w for w in widths),
    ]
    for r in rows:
        lines.append(fmt.format(
            *[str(c) for c in r[:len(widths)]]))
    return "\n".join(lines)


def format_runs_list_as_text(runs_root: Path) -> str:
    """v1.5.7 121: render the runs-list view as plain text.
    Used by the TUI's `c` (copy current screen) action AND
    by the `qpb_harness tui --dump runs` CLI form. Both call
    this so a screenshot-via-clipboard matches what `--dump`
    prints — single text representation.

    NO textual dependency."""
    rows = build_runs_table_rows(runs_root)
    header = f"runs-root: {runs_root}"
    return header + "\n" + _format_table_as_text(
        RUNS_TABLE_COLUMNS, rows)


def format_detail_as_text(harness_run_dir: Path) -> str:
    """v1.5.7 121: render the detail view as plain text.
    Mirror of format_runs_list_as_text for the drill-down
    page."""
    rows = build_detail_table_rows(harness_run_dir)
    header = f"harness-run: {harness_run_dir.name}"
    return header + "\n" + _format_table_as_text(
        DETAIL_TABLE_COLUMNS, rows)


def format_output_as_text(run_dir: Path, *,
                            max_lines: int = _DEFAULT_OUTPUT_MAX_LINES,
                            rendered: bool = True,
                            ) -> str:
    """v1.5.7 121 + 122: render the live-output view as plain
    text. v1.5.7 122 ``rendered`` toggle (default True): when
    True, lines go through ``status.render_stream_line``
    (Claude stream-json templated into clean log lines; 109
    sentinels human-readable; non-Claude plain text
    passthrough). When False, lines verbatim — the ``--raw``
    CLI / TUI ``j``-toggle mode."""
    lines = build_rendered_output_lines(
        run_dir, max_lines=max_lines, rendered=rendered)
    mode = "" if rendered else " [RAW]"
    header = f"output: {run_dir.name}{mode}"
    if not lines:
        return header + "\n(no output yet)"
    return header + "\n" + "\n".join(lines)


def launch_textual_tui(
        runs_root: Path,
        *,
        initial_focus: "Optional[tuple]" = None,
) -> int:
    """v1.5.7 119: launch the Textual TUI (build via
    ``_build_textual_app`` + run the event loop).

    Lazy-imports textual (via the factory) so this module's import
    stays clean when textual isn't installed (111 invariant). The
    CLI's ``_cmd_tui`` catches ImportError and falls back to curses.

    v1.5.7 151: the build/run split lets ``App.run_test()`` drive
    the app headlessly in interaction tests (the factory returns the
    constructed App; this wrapper runs it)."""
    return _build_textual_app(
        runs_root, initial_focus=initial_focus).run() or 0


def _build_textual_app(
        runs_root: Path,
        initial_focus: "Optional[tuple]" = None,
):
    """v1.5.7 151: construct (but do NOT run) the Textual app.
    Lazy-imports textual inside the function so importing
    ``bin.harness.tui`` stays clean without textual (119 invariant).
    Returns the ``QPBHarnessApp`` instance — production runs it via
    ``launch_textual_tui``; tests drive it via ``app.run_test()``.

    v1.5.7 139: ``initial_focus`` (``(TuiPathKind, Path)`` or None)
    opens the app at a deeper screen than the runs-list.
    """
    # Lazy imports — textual is dev/harness-optional.
    from textual.app import App, ComposeResult
    from textual.binding import Binding
    from textual.containers import Vertical, Center, Middle
    from textual.screen import ModalScreen
    from textual.widgets import (
        Header, Footer, DataTable, RichLog, Static, Label,
    )

    class _KillConfirmScreen(ModalScreen):
        """v1.5.7 151: modal y/N confirm for the kill action. Owns
        the screen until dismissed, so the 2s ``refresh_view`` (whose
        renderers update the status bar on the screen BEHIND it)
        cannot paint over the prompt — fixes 147's Bug A. A second
        `k` while it's up is swallowed by the modal (not re-armed) —
        fixes Bug B. ``y`` → dismiss(True); ``n``/Esc/other →
        dismiss(False). Caller wires push_screen(..., callback=...)."""

        BINDINGS = [
            Binding("y", "confirm", "Kill", show=True),
            Binding("Y", "confirm", "Kill", show=False),
            Binding("n", "cancel", "Cancel", show=True),
            Binding("N", "cancel", "Cancel", show=False),
            Binding("escape", "cancel", "Cancel", show=False),
        ]

        CSS = """
        _KillConfirmScreen {
            align: center middle;
        }
        _KillConfirmScreen Label {
            width: auto;
            min-width: 40;
            padding: 1 4;
            border: thick $warning;
            background: $surface;
        }
        """

        def __init__(self, prompt: str) -> None:
            super().__init__()
            self._prompt = prompt

        def compose(self) -> "ComposeResult":
            yield Middle(Center(Label(self._prompt)))

        def action_confirm(self) -> None:
            self.dismiss(True)

        def action_cancel(self) -> None:
            self.dismiss(False)

    _NAV_LIST = "list"
    _NAV_DETAIL = "detail"
    _NAV_OUTPUT = "output"

    class QPBHarnessApp(App):
        """v1.5.7 119: live status TUI.

        Three navigable screens (re-using one DataTable +
        one RichLog widget — cheaper than a full screen
        stack). All reads go through status.py. Auto-refresh
        on a 2s timer. Follow-mode tail in the output view
        (toggleable via End / f)."""

        BINDINGS = [
            Binding("q", "quit_app", "Quit"),
            Binding("escape", "back", "Back"),
            Binding("r", "refresh", "Refresh"),
            Binding("end", "follow", "Follow"),
            Binding("f", "toggle_follow", "Toggle follow"),
            # v1.5.7 121: copy the active screen's rendered
            # text to the system clipboard via OSC 52
            # (Textual's `App.copy_to_clipboard`). Works over
            # SSH and most modern terminals — no new
            # dependency. OPERATOR NOTE: some terminals require
            # OSC-52 clipboard-write to be enabled (iTerm2:
            # Prefs → General → "Applications in terminal may
            # access clipboard"; xterm: `allowWindowOps`).
            Binding("c", "copy_screen", "Copy"),
            # v1.5.7 122: toggle output-view rendering mode
            # (rendered ⇔ raw). Default is RENDERED (the 122
            # Claude stream-json templating); raw shows the
            # wire-format JSON for debugging.
            Binding("j", "toggle_rendered", "Raw/Render"),
            # v1.5.7 147: kill the focused run (output page) or the
            # highlighted run (detail page) — SIGKILL, with an inline
            # y/N confirm. No-op on the runs-list (too broad).
            Binding("k", "kill_run", "Kill"),
            # v1.5.7 186 FINDING-32: force-execute the highlighted
            # PENDING row OUT OF POOL. y/N confirm modal. Only
            # activates on PENDING rows in the detail page.
            Binding("e", "force_run", "Force-run"),
        ]

        CSS = """
        DataTable {
            height: 1fr;
        }
        RichLog {
            height: 1fr;
            border: solid $accent;
        }
        .status-bar {
            dock: bottom;
            height: 1;
            color: $text-muted;
        }
        """

        def __init__(self,
                      app_runs_root: Path,
                      app_initial_focus: "Optional[tuple]" = None,
                      ) -> None:
            super().__init__()
            self._runs_root = app_runs_root
            # v1.5.7 139: deep-entry initial nav state (shared
            # derivation with the curses loop). None ⇒ runs-list.
            (self._nav,
             self._current_dir,
             self._current_run_dir) = _resolve_initial_nav_state(
                app_initial_focus)
            # Follow-mode default: tail at bottom, auto-scroll
            # on refresh. Operator toggles with f / End.
            self._follow_mode = True
            # v1.5.7 122: output-view render mode. True =
            # human-readable (Claude stream-json templated);
            # False = raw wire-format lines. Operator toggles
            # with `j`. Default True.
            self._rendered_mode = True
            # v1.5.7 151: the kill y/N confirm is now a ModalScreen
            # (action_kill_run → push_screen), so there's no
            # _kill_pending / on_key state to track — the modal owns
            # the flow until dismissed (fixes 147's Bugs A/B).

        def compose(self) -> ComposeResult:
            yield Header(show_clock=True)
            self._table = DataTable(
                zebra_stripes=True,
                cursor_type="row",
                id="runs-table",
            )
            self._log = RichLog(
                highlight=False,
                markup=False,
                wrap=False,
                auto_scroll=False,
                id="run-log",
            )
            self._log.display = False
            yield self._table
            yield self._log
            self._status_bar = Static(
                "", classes="status-bar", id="status-bar")
            yield self._status_bar
            yield Footer()

        def on_mount(self) -> None:
            # v1.5.7 139: open at the screen the initial nav state
            # indicates (deep-entry) — default is the runs-list.
            # refresh_view already dispatches by ``self._nav``.
            self.refresh_view()
            # v1.5.7 119 Task C: ~2s auto-refresh on ALL
            # screens. set_interval fires on the App's main
            # event loop; refresh_view dispatches to the
            # active screen's renderer.
            self.set_interval(2.0, self.refresh_view)

        # -- screen renderers -----------------------------------

        def _render_runs_list(self) -> None:
            self._table.display = True
            self._log.display = False
            prior_cursor = (self._table.cursor_row
                            if self._table.row_count else 0)
            self._table.clear(columns=True)
            self._table.add_columns(*RUNS_TABLE_COLUMNS)
            rows = build_runs_table_rows(self._runs_root)
            for r in rows:
                self._table.add_row(*r)
            if self._table.row_count and 0 <= prior_cursor < self._table.row_count:
                try:
                    self._table.move_cursor(row=prior_cursor)
                except Exception:
                    pass
            self._status_bar.update(
                f"runs root: {self._runs_root}   "
                f"Enter: detail   r: refresh   q: quit"
            )

        def _render_run_detail(self) -> None:
            if self._current_dir is None:
                return
            self._table.display = True
            self._log.display = False
            prior_cursor = (self._table.cursor_row
                            if self._table.row_count else 0)
            self._table.clear(columns=True)
            self._table.add_columns(*DETAIL_TABLE_COLUMNS)
            rows = build_detail_table_rows(self._current_dir)
            for r in rows:
                self._table.add_row(*r)
            if self._table.row_count and 0 <= prior_cursor < self._table.row_count:
                try:
                    self._table.move_cursor(row=prior_cursor)
                except Exception:
                    pass
            self._status_bar.update(
                f"detail: {self._current_dir.name}   "
                f"Enter: live output   Esc: back   r: refresh"
            )

        def _render_output_tail(
                self, *, auto_follow_check: bool = False) -> None:
            if self._current_run_dir is None:
                return
            self._table.display = False
            self._log.display = True
            # v1.5.7 140: focus the log so arrow / page / home keys
            # scroll it (built-in ScrollView actions). Idempotent —
            # a no-op once focused, so it just grabs focus on the
            # first output render. End stays App-bound to
            # `action_follow` (jump to live).
            if not self._log.has_focus:
                self._log.focus()
            # v1.5.7 140: on the periodic timer refresh
            # (auto_follow_check), auto-update follow state from the
            # scroll position BEFORE the rewrite: if the operator
            # scrolled up (not at the bottom), pause so the refresh
            # doesn't yank them back; when they return to the
            # bottom, resume. Explicit actions (f / End / entry)
            # pass auto_follow_check=False so they aren't
            # immediately re-paused before the scroll-to-bottom
            # lands. `_follow_mode` True == NOT paused.
            prior_scroll_y = self._log.scroll_y
            if auto_follow_check:
                paused = _should_pause_follow(
                    self._log.scroll_y, self._log.max_scroll_y,
                    manual_scroll_event=(
                        self._log.scroll_y < self._log.max_scroll_y),
                    currently_paused=not self._follow_mode,
                    user_pressed_f=False,
                )
                self._follow_mode = not paused
            else:
                paused = not self._follow_mode
            lines = build_rendered_output_lines(
                self._current_run_dir,
                rendered=self._rendered_mode,
            )
            # Rewrite the buffer each tick so we don't leak
            # duplicated lines across refreshes. RichLog's
            # write() is cheap enough for ~5k lines (the
            # default cap).
            self._log.clear()
            if not lines:
                self._log.write("(no output yet)")
            else:
                for line in lines:
                    self._log.write(line)
            if self._follow_mode:
                # Pin the viewport to the newest line —
                # tail -f semantics.
                self._log.scroll_end(animate=False)
            else:
                # v1.5.7 140: paused — preserve the operator's
                # viewport across the clear+rewrite (the snap-back
                # bug was the rewrite resetting scroll then
                # scroll_end re-anchoring). Restore the prior
                # offset (validate_scroll_y clamps to the new
                # content height).
                self._log.scroll_y = prior_scroll_y
            mode = ("FOLLOW" if self._follow_mode
                    else "PAUSED ⏸")
            render_mode = ("RENDERED" if self._rendered_mode
                            else "RAW")
            # v1.5.7 140: distinct hint when paused so the operator
            # sees they're scrolled back off the live tail. (Plain
            # text — no Rich markup — to avoid any literal-bracket
            # display; the mode field already shows PAUSED ⏸.)
            follow_hint = ("»f/End: resume live«" if paused
                           else "f: toggle follow")
            self._status_bar.update(
                f"output [{mode}|{render_mode}]: "
                f"{self._current_run_dir.name}   "
                f"{follow_hint}   j: rendered/raw   "
                f"End: follow+bottom   Esc: back"
            )

        # -- timer dispatch -------------------------------------

        def refresh_view(self) -> None:
            if self._nav == _NAV_LIST:
                self._render_runs_list()
            elif self._nav == _NAV_DETAIL:
                self._render_run_detail()
            elif self._nav == _NAV_OUTPUT:
                # v1.5.7 140: the periodic refresh evaluates
                # auto-pause from the operator's scroll position.
                self._render_output_tail(auto_follow_check=True)

        # -- actions --------------------------------------------

        def action_quit_app(self) -> None:
            self.exit(0)

        def action_back(self) -> None:
            if self._nav == _NAV_OUTPUT:
                self._nav = _NAV_DETAIL
                self._render_run_detail()
            elif self._nav == _NAV_DETAIL:
                self._nav = _NAV_LIST
                self._current_dir = None
                self._render_runs_list()
            else:
                self.exit(0)

        def action_refresh(self) -> None:
            self.refresh_view()

        def action_follow(self) -> None:
            """End key: re-engage follow + scroll to bottom."""
            self._follow_mode = True
            if self._nav == _NAV_OUTPUT:
                self._render_output_tail()

        def action_toggle_follow(self) -> None:
            """f key: explicit follow on/off override (v1.5.7 140 —
            routed through the shared `_should_pause_follow` so the
            toggle semantics live in one place)."""
            paused = _should_pause_follow(
                self._log.scroll_y, self._log.max_scroll_y,
                manual_scroll_event=False,
                currently_paused=not self._follow_mode,
                user_pressed_f=True,
            )
            self._follow_mode = not paused
            if self._nav == _NAV_OUTPUT:
                # auto_follow_check=False: honor the explicit choice
                # (if now following, the render scroll_end's to live).
                self._render_output_tail()

        def action_toggle_rendered(self) -> None:
            """v1.5.7 122 — `j` key: flip the output view
            between RENDERED (clean log lines via
            ``render_stream_line``) and RAW (wire-format
            JSON, for debugging). Only meaningful on
            NAV_OUTPUT; on other screens it's a no-op."""
            self._rendered_mode = not self._rendered_mode
            if self._nav == _NAV_OUTPUT:
                self._render_output_tail()

        def action_kill_run(self) -> None:
            """v1.5.7 147 + 151: `k` — push a modal y/N confirm.
            Output page → the focused run; detail page → the
            highlighted run; runs-list → all RUNNING runs in the
            highlighted harness run. The modal owns the screen (no
            status-bar overwrite, no second-`k` re-arm — fixes 147's
            Bugs A/B)."""
            from bin.harness import status as _status

            if (self._nav == _NAV_OUTPUT
                    and self._current_run_dir is not None):
                run_dir = self._current_run_dir
                self.push_screen(
                    _KillConfirmScreen(f"Kill {run_dir.name}? (y/N)"),
                    callback=lambda ok, rd=run_dir: (
                        self._do_kill(rd) if ok else None))
                return

            if (self._nav == _NAV_DETAIL
                    and self._current_dir is not None):
                runs = _status.read_run_status(self._current_dir)
                idx = (self._table.cursor_row
                       if self._table.row_count else -1)
                if 0 <= idx < len(runs):
                    rs = runs[idx]
                    self.push_screen(
                        _KillConfirmScreen(
                            f"Kill {rs.run_dir.name} "
                            f"({rs.runner}/{rs.model})? (y/N)"),
                        callback=lambda ok, rd=rs.run_dir: (
                            self._do_kill(rd) if ok else None))
                return

            # v1.5.7 151: runs-list — kill all RUNNING runs in the
            # HIGHLIGHTED harness run (the cursor scopes it to one
            # harness run, NOT the whole runs-root; matches the CLI's
            # `kill <HARNESS_RUN>` semantic). Bug C fix.
            if self._nav == _NAV_LIST:
                summaries = _status.list_harness_runs(self._runs_root)
                idx = (self._table.cursor_row
                       if self._table.row_count else -1)
                if not (0 <= idx < len(summaries)):
                    return
                hr_dir = summaries[idx].harness_run_dir
                running = [rs for rs in _status.read_run_status(hr_dir)
                           if rs.state == "RUNNING"]
                if not running:
                    self._status_bar.update(
                        f"{hr_dir.name}: no RUNNING runs to kill")
                    return
                self.push_screen(
                    _KillConfirmScreen(
                        f"Kill {len(running)} RUNNING run(s) in "
                        f"{hr_dir.name}? (y/N)"),
                    callback=lambda ok, rl=running: (
                        self._do_kill_many(rl) if ok else None))

        def _do_kill(self, run_dir: "Path") -> None:
            from bin.harness import runner as _runner
            try:
                _runner.kill_run(run_dir)
                self._status_bar.update(
                    f"killed {run_dir.name} (SIGKILL)")
            except Exception as exc:  # pragma: no cover - terminal
                self._status_bar.update(f"kill failed: {exc}")
            self.refresh_view()

        def _do_kill_many(self, run_statuses) -> None:
            """v1.5.7 151: kill each RUNNING run in a harness run
            (runs-list `k`). Accumulates a killed/failed count."""
            from bin.harness import runner as _runner
            killed = failed = 0
            for rs in run_statuses:
                try:
                    _runner.kill_run(rs.run_dir)
                    killed += 1
                except Exception:  # pragma: no cover - terminal
                    failed += 1
            msg = f"killed {killed} run(s)"
            if failed:
                msg += f", {failed} failed"
            self._status_bar.update(msg)
            self.refresh_view()

        def action_force_run(self) -> None:
            """v1.5.7 186 FINDING-32: 'E' — force-execute the
            highlighted PENDING row OUT OF POOL. Only
            activates on PENDING rows in the detail page
            (other states / pages no-op with a status-bar
            note). Pushes a y/N confirmation modal whose
            prompt shows the row's runner/repo + the
            current live count + the post-launch live count
            so the operator sees exactly how far they're
            exceeding the pool."""
            from bin.harness import status as _status
            if self._nav != _NAV_DETAIL or self._current_dir is None:
                self._status_bar.update(
                    "E (force-run): only available on the "
                    "detail page over a PENDING row")
                return
            runs = _status.read_run_status(self._current_dir)
            idx = (self._table.cursor_row
                   if self._table.row_count else -1)
            if not (0 <= idx < len(runs)):
                return
            rs = runs[idx]
            if rs.state != "PENDING":
                self._status_bar.update(
                    f"E (force-run): row is {rs.state}, not "
                    f"PENDING")
                return
            # Compute the current + post-launch live count for
            # rs.runner so the operator sees the consequence.
            live_now = sum(
                1 for r in runs
                if r.state in ("RUNNING", "ACQUIRING")
                and r.runner == rs.runner)
            prompt = (
                f"Force-run row #{rs.index} "
                f"({rs.runner}/{rs.model} "
                f"{rs.repo.rsplit('/', 1)[-1]}) OUT OF POOL? "
                f"Current live {rs.runner} count: {live_now}; "
                f"post-launch: {live_now + 1}. (y/N)"
            )
            self.push_screen(
                _KillConfirmScreen(prompt),
                callback=lambda ok, run_dir=rs.run_dir, idx=rs.index: (
                    self._do_force_run(run_dir, idx)
                    if ok else None))

        def _do_force_run(self, run_dir: "Path",
                            run_index: int) -> None:
            """v1.5.7 186 FINDING-32: invoke the headless
            force-launch helper for the confirmed row.
            Reports outcome via the status bar."""
            from bin.harness import plan_runner as _pr
            harness_run_dir = run_dir.parent
            try:
                result = _pr.force_launch_pending_run(
                    harness_run_dir, run_index)
            except _pr.ForceRunError as exc:
                self._status_bar.update(
                    f"force-run failed: {exc}")
                self.refresh_view()
                return
            except Exception as exc:  # pragma: no cover
                self._status_bar.update(
                    f"force-run failed: {exc}")
                self.refresh_view()
                return
            self._status_bar.update(
                f"force-launched run-{run_index:02d} "
                f"({result['runner']}/{result['model']}); "
                f"pid={result['pid']}; live "
                f"{result['runner']} count now "
                f"{result['live_count_after']}")
            self.refresh_view()

        def action_copy_screen(self) -> None:
            """v1.5.7 121: copy the current screen's rendered
            text to the system clipboard via OSC 52
            (Textual's ``App.copy_to_clipboard``).

            Uses the same pure formatters the ``--dump <page>``
            CLI uses, so what's on screen matches what gets
            copied. Flashes a brief confirmation in the
            status bar; the next 2s refresh tick restores
            the normal status line."""
            text = self._assemble_current_screen_text()
            line_count = len(text.splitlines())
            try:
                # Textual's App.copy_to_clipboard emits OSC 52.
                self.copy_to_clipboard(text)
                self._status_bar.update(
                    f"copied {line_count} lines to clipboard "
                    f"(OSC 52; next refresh restores status)"
                )
            except Exception as exc:  # pragma: no cover - terminal-specific
                self._status_bar.update(
                    f"copy failed: {exc} "
                    f"(terminal may not support OSC 52)"
                )

        def _assemble_current_screen_text(self) -> str:
            """v1.5.7 121: build the plain-text representation
            of the active screen. Used by ``action_copy_screen``.
            Delegates to the same formatters the ``--dump <page>``
            CLI uses so the two views agree."""
            if self._nav == _NAV_LIST:
                return format_runs_list_as_text(self._runs_root)
            if (self._nav == _NAV_DETAIL
                    and self._current_dir is not None):
                return format_detail_as_text(self._current_dir)
            if (self._nav == _NAV_OUTPUT
                    and self._current_run_dir is not None):
                # v1.5.7 122: `c` copy reflects the active
                # render mode — copying RAW gives the wire-
                # format JSON; copying RENDERED gives the
                # log-style lines.
                return format_output_as_text(
                    self._current_run_dir,
                    rendered=self._rendered_mode,
                )
            return "(empty)"

        # -- navigation (row selection) -------------------------

        def on_data_table_row_selected(self, event) -> None:
            row_idx = event.cursor_row
            from bin.harness import status as _status
            if self._nav == _NAV_LIST:
                summaries = _status.list_harness_runs(
                    self._runs_root)
                if 0 <= row_idx < len(summaries):
                    self._current_dir = (
                        summaries[row_idx].harness_run_dir)
                    self._nav = _NAV_DETAIL
                    self._render_run_detail()
            elif self._nav == _NAV_DETAIL and self._current_dir:
                runs = _status.read_run_status(
                    self._current_dir)
                if 0 <= row_idx < len(runs):
                    self._current_run_dir = (
                        runs[row_idx].run_dir)
                    self._nav = _NAV_OUTPUT
                    # Default to follow on entry; operator can
                    # toggle with f / End.
                    self._follow_mode = True
                    self._render_output_tail()

    return QPBHarnessApp(runs_root, initial_focus)
