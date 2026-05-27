"""v1.5.7 110 — read-only model layer for harness status + tail.

Pure functions consumed by:
  * the 110 CLI subcommands (``qpb_harness status``,
    ``qpb_harness status <harness-run>``,
    ``qpb_harness tail <run-NN> [--follow]``);
  * the 111 live TUI (same data; different rendering).

Reads the 108 ``manifest.json`` + per-run ``status.json`` +
parses the 109 ``::QPB:: {kind:"phase"}`` sentinels from each
run's stream to report the current phase.

Design contract:
  * **Never raise** on a partially-written tree (a run mid-
    launch, a collector that died mid-write). Missing fields
    fall back to safe defaults ("—" for unknown phase, "(running)"
    for ungraded outcome, ``pid_alive=False`` for missing-PID).
  * **Never mutate state.** Pure read; safe to call concurrently
    with the collector.
  * **Generalizes to the TUI**: same dataclasses, same parsing
    helpers — the TUI just renders them differently.
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional


_SENTINEL_PREFIX = "::QPB:: "
_SENTINEL_RE = re.compile(r"^::QPB:: (\{.+\})$")
# Collector-liveness window: if collector.log was modified within
# this many seconds, treat the collector as live. The collector
# polls every ~0.25s, so 60s is conservative (a quiet collector
# that's still polling will easily touch its log inside that
# window). Tunable later.
_COLLECTOR_LIVENESS_WINDOW_S = 60.0


@dataclass
class HarnessRunSummary:
    """One row of the ``qpb_harness status`` table.

    v1.5.7 113: gained ``blocked``. Pre-113 a BLOCKED run
    (112's AUP / API-error terminal state) fell through to
    ``pending`` in ``_summarize_harness_run`` (no explicit
    branch), so the AUP experiment's blocked run-00 showed
    as ``P`` instead of being surfaced. Now counted on its
    own column."""
    harness_run_dir: Path
    started_at: str
    total_runs: int
    pending: int
    running: int
    completed: int
    failed: int
    timed_out: int
    aborted_prep: int
    blocked: int
    collector_alive: bool


@dataclass
class RunStatus:
    """One row of the ``qpb_harness status <harness-run>``
    drill-down table."""
    index: int
    description: str
    repo: str
    runner: str
    model: str
    state: str
    """PENDING | RUNNING | terminal (COMPLETED / FAILED /
    TIMED_OUT / ABORTED_PREP)."""
    result: str
    """MET | NOT-MET | N/A | (running)."""
    current_phase: str  # P0..P6 or "—"
    current_phase_name: str  # validation/exploration/... or "—"
    current_phase_state: str  # start | done | "—"
    last_note: str
    pid: Optional[int]
    pid_alive: bool
    stream_path: Path
    run_dir: Path


# ---------------------------------------------------------------------------
# Sentinel parsing (mirrors qpb_phase.py + quality_gate.py emit format)
# ---------------------------------------------------------------------------


def parse_sentinels(stream_text: str) -> "list[dict]":
    """Parse all ``::QPB:: {json}`` lines from a stream blob.
    Skips non-sentinel lines + malformed sentinel payloads
    (a sentinel line whose JSON doesn't parse is dropped, not
    raised). Returns parsed payloads in stream order."""
    out: list[dict] = []
    for line in stream_text.splitlines():
        m = _SENTINEL_RE.match(line.rstrip())
        if not m:
            continue
        try:
            out.append(json.loads(m.group(1)))
        except json.JSONDecodeError:
            continue
    return out


def _safe_read(path: Path) -> str:
    """Read a file, returning '' on any OSError. Used to swallow
    races against a half-written file (collector writing while
    we read)."""
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _safe_json(path: Path) -> "Optional[dict]":
    text = _safe_read(path)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# PID liveness (patchable for tests)
# ---------------------------------------------------------------------------


def pid_is_alive(pid: "Optional[int]") -> bool:
    """``os.kill(pid, 0)`` semantics. Wrapped so tests can patch
    cleanly. Returns False for None/0/negative pids."""
    if pid is None or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


# ---------------------------------------------------------------------------
# Per-run status read
# ---------------------------------------------------------------------------


def read_run_status(harness_run_dir: Path) -> "list[RunStatus]":
    """Read ``manifest.json`` + per-run ``status.json`` + parse
    the last ``::QPB:: kind:"phase"`` line from each run's
    ``stream.ndjson``.

    Returns an empty list when the manifest is missing or
    unparseable. Never raises on partially-written input.
    """
    manifest = _safe_json(harness_run_dir / "manifest.json")
    if not manifest:
        return []
    return [
        _read_one_run_status(entry, harness_run_dir)
        for entry in manifest.get("runs", [])
    ]


def _read_one_run_status(entry: dict,
                           harness_run_dir: Path) -> RunStatus:
    run_dir = Path(entry.get("run_dir", ""))
    stream_path = Path(entry.get("stream_path",
                                   str(run_dir / "stream.ndjson")))
    status_path = run_dir / "status.json"
    grading_path = run_dir / "grading.json"

    # State + pid: status.json wins; manifest entry is the
    # fallback (the launch-side ABORTED_PREP case writes the
    # terminal_state into the manifest entry directly).
    state = "PENDING"
    pid = entry.get("pid")
    if entry.get("terminal_state"):
        state = entry["terminal_state"]
    status = _safe_json(status_path)
    if status:
        if status.get("terminal_state"):
            state = status["terminal_state"]
        elif status.get("state") == "RUNNING":
            state = "RUNNING"
        pid = status.get("pid", pid)

    pid_alive = (pid_is_alive(pid) if isinstance(pid, int)
                  else False)

    # Result from grading.json (collector wrote it on terminal).
    if state == "RUNNING":
        result = "(running)"
    else:
        result = "N/A"
    grading = _safe_json(grading_path)
    if grading and isinstance(grading, dict):
        result = grading.get("verdict", result)

    # Current phase from the last `::QPB:: kind:"phase"` line
    # in the stream. Degrade gracefully — no sentinel ⇒ "—".
    current_phase = "—"
    current_phase_name = "—"
    current_phase_state = "—"
    last_note = ""
    if stream_path.is_file():
        sentinels = parse_sentinels(_safe_read(stream_path))
        for s in reversed(sentinels):
            if s.get("kind") == "phase":
                current_phase = f"P{s.get('phase', '?')}"
                current_phase_name = s.get("name", "—")
                current_phase_state = s.get("state", "—")
                last_note = s.get("note", "")
                break

    return RunStatus(
        index=entry.get("index", -1),
        description=entry.get("description", ""),
        repo=entry.get("repo", ""),
        runner=entry.get("runner", ""),
        model=entry.get("model", ""),
        state=state,
        result=result,
        current_phase=current_phase,
        current_phase_name=current_phase_name,
        current_phase_state=current_phase_state,
        last_note=last_note,
        pid=pid if isinstance(pid, int) else None,
        pid_alive=pid_alive,
        stream_path=stream_path,
        run_dir=run_dir,
    )


# ---------------------------------------------------------------------------
# Harness-run summary list
# ---------------------------------------------------------------------------


def list_harness_runs(runs_root: Path) -> "list[HarnessRunSummary]":
    """Scan ``runs_root`` for harness-run directories. Returns
    NEWEST FIRST (operator wants the in-flight ones at the top).

    Robust to a runs_root that doesn't exist (empty list) and to
    harness-run dirs without manifest.json (counts as 0 runs).
    """
    if not runs_root.is_dir():
        return []
    dirs = sorted(
        (d for d in runs_root.iterdir() if d.is_dir()),
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    return [_summarize_harness_run(d) for d in dirs]


def _summarize_harness_run(harness_run_dir: Path) -> HarnessRunSummary:
    runs = read_run_status(harness_run_dir)
    counts = {
        "pending": 0, "running": 0, "completed": 0,
        "failed": 0, "timed_out": 0, "aborted_prep": 0,
        "blocked": 0,
    }
    for r in runs:
        if r.state == "RUNNING":
            counts["running"] += 1
        elif r.state == "COMPLETED":
            counts["completed"] += 1
        elif r.state == "FAILED":
            counts["failed"] += 1
        elif r.state == "TIMED_OUT":
            counts["timed_out"] += 1
        elif r.state == "ABORTED_PREP":
            counts["aborted_prep"] += 1
        # v1.5.7 113: BLOCKED is its own column. Pre-113 this
        # branch was missing, so 112's AUP/API-error runs fell
        # through to the `else` (counted as pending) — the
        # AUP-experiment's run-00 showed `P=1` for a finished-
        # BLOCKED run.
        elif r.state == "BLOCKED":
            counts["blocked"] += 1
        else:
            counts["pending"] += 1
    # Collector liveness: the collector polls every ~0.25s and
    # writes to collector.log; recent mtime ⇒ alive.
    collector_alive = False
    collector_log = harness_run_dir / "collector.log"
    if collector_log.is_file():
        try:
            mtime = collector_log.stat().st_mtime
            age = datetime.now(timezone.utc).timestamp() - mtime
            collector_alive = age < _COLLECTOR_LIVENESS_WINDOW_S
        except OSError:
            collector_alive = False
    started_at = "—"
    try:
        started_at = datetime.fromtimestamp(
            harness_run_dir.stat().st_mtime, tz=timezone.utc,
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
    except OSError:
        pass
    return HarnessRunSummary(
        harness_run_dir=harness_run_dir,
        started_at=started_at,
        total_runs=len(runs),
        **counts,
        collector_alive=collector_alive,
    )


# ---------------------------------------------------------------------------
# Stream tailing (CLI tail + TUI live pane both consume this)
# ---------------------------------------------------------------------------


def tail_stream(run_dir: Path, *,
                 follow: bool = False) -> Iterator[str]:
    """Yield rendered lines from ``<run_dir>/stream.ndjson``.

    Sentinel lines (both ``kind:"phase"`` and ``kind:"gate"``)
    are rendered human-readably; non-sentinel lines pass through
    verbatim.

    ``follow=False`` (default): emit everything currently in the
    file and stop. ``follow=True``: emit current content, then
    poll for new content every 0.5s (tail -f semantics).
    Caller is responsible for stopping the iteration (Ctrl-C
    or break).

    If ``stream.ndjson`` doesn't exist (run hasn't launched
    yet), emits nothing.
    """
    stream_path = run_dir / "stream.ndjson"
    if not stream_path.is_file():
        return
    with open(stream_path, "rb") as f:
        for raw in f:
            yield render_stream_line(
                raw.decode("utf-8", errors="ignore")
                .rstrip("\n")
            )
        if not follow:
            return
        while True:
            raw = f.readline()
            if raw:
                yield render_stream_line(
                    raw.decode("utf-8", errors="ignore")
                    .rstrip("\n")
                )
            else:
                time.sleep(0.5)


def render_stream_line(line: str) -> str:
    """Render one stream line. Sentinels become human-readable
    one-liners; everything else passes through unchanged."""
    if not line.startswith(_SENTINEL_PREFIX):
        return line
    m = _SENTINEL_RE.match(line)
    if not m:
        return line
    try:
        payload = json.loads(m.group(1))
    except json.JSONDecodeError:
        return line
    kind = payload.get("kind", "?")
    ts = payload.get("ts", "")
    if kind == "phase":
        phase_num = payload.get("phase", "?")
        name = payload.get("name", "?")
        state = payload.get("state", "?")
        note = payload.get("note", "")
        note_part = f" — {note}" if note else ""
        return (f"[{ts}] phase {phase_num} ({name}) "
                f"{state.upper()}{note_part}")
    if kind == "gate":
        gate_result = payload.get("gate_result", "?")
        verdict_state = payload.get("verdict_state", "?")
        return (f"[{ts}] GATE {gate_result} "
                f"(verdict_state={verdict_state})")
    return line


# ---------------------------------------------------------------------------
# Rendering helpers (shared between CLI + TUI; pure formatters)
# ---------------------------------------------------------------------------


def format_harness_run_summary(
        summary: HarnessRunSummary) -> str:
    """Render one HarnessRunSummary as a one-line table row.

    v1.5.7 113: includes ``B=<blocked>`` between ``T`` and
    ``AP``. The B column makes 112's BLOCKED terminal state
    visible in the per-harness-run summary; pre-113 a
    BLOCKED run was silently miscounted as pending."""
    dir_name = summary.harness_run_dir.name
    coll = ("yes" if summary.collector_alive
            else "no")
    return (
        f"{dir_name:30} {summary.started_at:22} "
        f"runs={summary.total_runs:>2}  "
        f"R={summary.running:>2} D={summary.completed:>2} "
        f"F={summary.failed:>2} T={summary.timed_out:>2} "
        f"B={summary.blocked:>2} "
        f"AP={summary.aborted_prep:>2} P={summary.pending:>2}  "
        f"collector={coll}"
    )


def format_run_status(rs: RunStatus) -> str:
    """Render one RunStatus row for the drill-down table."""
    repo_tail = rs.repo.rstrip("/").split("/")[-1] or rs.repo
    pid_part = (
        f"{rs.pid}(live)" if rs.pid_alive
        else (f"{rs.pid}(dead)" if rs.pid else "—")
    )
    phase_part = (
        f"{rs.current_phase} {rs.current_phase_name} "
        f"{rs.current_phase_state}"
        if rs.current_phase != "—" else "—"
    )
    return (
        f"#{rs.index:<2} {repo_tail:18} "
        f"{rs.runner}/{rs.model:14} "
        f"{rs.state:14} {phase_part:34} "
        f"result={rs.result:10} pid={pid_part}"
    )


__all__ = [
    "HarnessRunSummary",
    "RunStatus",
    "list_harness_runs",
    "read_run_status",
    "tail_stream",
    "render_stream_line",
    "parse_sentinels",
    "pid_is_alive",
    "format_harness_run_summary",
    "format_run_status",
]
