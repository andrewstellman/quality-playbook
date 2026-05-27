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


def launch_status_tui(runs_root: Path) -> int:
    """v1.5.7 111: the curses entry point. Three navigation
    levels: harness-runs list → run detail → live output.

    Side-effect-free import: this function is only called from
    the CLI (``qpb_harness tui --runs-root <DIR>``); importing
    ``bin.harness.tui`` does NOT start curses. The
    ``curses.wrapper`` ensures the terminal is restored on
    exit AND on any uncaught exception.
    """
    import curses

    def _main(stdscr: "curses._CursesWindow") -> int:  # type: ignore[name-defined]
        curses.curs_set(0)
        stdscr.nodelay(True)
        stdscr.timeout(2000)  # auto-refresh ~2s
        return _event_loop(stdscr, runs_root)

    return curses.wrapper(_main)


# Navigation states.
_NAV_LIST = "list"
_NAV_DETAIL = "detail"
_NAV_OUTPUT = "output"


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


def _event_loop(stdscr, runs_root: Path) -> int:
    """v1.5.7 111: the TUI's main loop. NOT directly unit
    tested (curses is hard to fixture); the view-model
    builders ABOVE are what tests exercise. This function is
    a thin glue layer: read keys → update nav state → call a
    view-model builder → render lines."""
    import curses

    nav = _NAV_LIST
    selected_idx = 0
    current_dir: "Optional[Path]" = None
    current_run_dir: "Optional[Path]" = None
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
