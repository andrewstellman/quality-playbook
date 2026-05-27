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
# v1.5.7 109 / 110 bare-line form (anchored). Used by
# ``render_stream_line`` for the tail-output path, where each
# line is rendered individually and the 109 emitter writes
# bare ``::QPB:: {...}`` lines when invoked outside a Claude
# stream-json wrapper (e.g. from a bare run_playbook subprocess
# or 109's own fixtures).
_SENTINEL_RE = re.compile(r"^::QPB:: (\{.+\})$")
# v1.5.7 117: the EMBEDDED form (non-anchored, non-greedy
# braces) so we find ``::QPB:: {...}`` substrings inside text
# content fields of Claude stream-json events. The pre-117
# ``parse_sentinels`` was anchored on ``_SENTINEL_RE`` — it
# matched the 109 fixture bare-line shape but missed every
# real ``claude --print --output-format stream-json`` stream,
# where the sentinel is emitted to stdout, captured by Claude
# as the ``content`` of a ``tool_result`` event, and JSON-
# escaped inside the outer event (no line ever starts with
# ``::QPB::``). 109/110 tests passed because their fixtures
# used clean bare lines — that fixture-vs-reality gap is the
# 117 bug.
_SENTINEL_INLINE_RE = re.compile(r"::QPB:: (\{[^\n]*?\})")
# v1.5.7 117: Mode B run_playbook prints `Phase N/6 (Name)` to
# stdout (NO ::QPB:: sentinel). Parse it the same way the
# operator reads it.
_MODE_B_PHASE_RE = re.compile(
    r"Phase\s+(\d+)/6\s*\(([^)]+)\)")
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
    own column.

    v1.5.7 117: gained ``progress`` (compact summary like
    ``P3/P6`` showing the max current-phase across runs;
    ``—`` when no run has reported a phase yet) and
    ``last_activity_iso`` (newest stream.ndjson mtime across
    runs; ``—`` when no streams exist yet). Both surface in
    the list view so an operator can see liveness at-a-
    glance — Mode B's stream goes quiet BETWEEN phases, so
    the elapsed/last-activity signal is the load-bearing
    indicator that the run is actually progressing."""
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
    # v1.5.7 117 — list-view progress + liveness.
    progress: str = "—"
    last_activity_iso: str = "—"


@dataclass
class RunStatus:
    """One row of the ``qpb_harness status <harness-run>``
    drill-down table.

    v1.5.7 117: gained ``last_activity_iso`` and
    ``elapsed_s`` so the operator can see at-a-glance whether
    a Mode B run (which goes quiet between phases) is alive
    and roughly how far along it is. Both default to ``"—"``
    / ``None`` when no stream / no started_at info."""
    index: int
    description: str
    repo: str
    runner: str
    model: str
    state: str
    """PENDING | RUNNING | terminal (COMPLETED / FAILED /
    TIMED_OUT / ABORTED_PREP / BLOCKED)."""
    result: str
    """MET | NOT-MET | N/A | (running)."""
    current_phase: str  # P0..P6 or "—"
    current_phase_name: str  # validation/exploration/... or "—"
    current_phase_state: str  # start | done | running | "—"
    last_note: str
    pid: Optional[int]
    pid_alive: bool
    stream_path: Path
    run_dir: Path
    # v1.5.7 117 — operator-visibility additions.
    last_activity_iso: str = "—"
    """Newest mtime of stream.ndjson, ISO8601 UTC. "—" when
    the stream file doesn't exist yet."""
    elapsed_s: "Optional[int]" = None
    """Seconds between started_at and last_activity_iso (or
    "now" for a running run). None when the start time is
    unknown."""


# ---------------------------------------------------------------------------
# Sentinel parsing (mirrors qpb_phase.py + quality_gate.py emit format)
# ---------------------------------------------------------------------------


def _walk_strings(obj) -> "Iterator[str]":
    """v1.5.7 117: yield every string value reachable inside a
    JSON-decoded tree (dicts, lists, nested). Used to find the
    sentinel inside Claude stream-json events where the 109
    ``::QPB::`` emission is embedded as the ``content`` of a
    ``tool_result`` (and duplicated in
    ``tool_use_result.stdout``)."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_strings(v)


def _scan_text_for_sentinels(text: str) -> "list[dict]":
    """v1.5.7 117: find every ``::QPB:: {...}`` substring in a
    string and json.loads each payload. Skip malformed
    payloads. Order-preserving."""
    out: list[dict] = []
    for m in _SENTINEL_INLINE_RE.finditer(text):
        try:
            out.append(json.loads(m.group(1)))
        except json.JSONDecodeError:
            continue
    return out


def parse_sentinels(stream_text: str) -> "list[dict]":
    """Parse all ``::QPB:: {json}`` sentinels from a stream
    blob. Returns parsed payloads in stream order.

    v1.5.7 117: handles BOTH the embedded form (sentinel
    inside the ``content`` of a Claude stream-json
    ``tool_result`` event — the REAL shape produced by
    ``claude --print --output-format stream-json``) AND the
    bare-line form (the 109 fixture shape that pre-117 tests
    used). Strategy: for each line, JSON-decode it and walk
    every string in the tree; if not JSON, scan the raw text.

    Defensive on every layer: missing fields, malformed JSON
    payloads, and non-dict outer events all skip silently.
    Duplicate sentinels (same payload appearing in both
    ``tool_result.content`` AND ``tool_use_result.stdout`` of
    the same event) are deduped so a 1-emission ``::QPB::``
    doesn't appear twice in the output."""
    out: list[dict] = []
    seen: set[str] = set()
    for line in stream_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
            # JSON event line — walk every string field and
            # scan for sentinels. Covers the real Claude
            # stream-json form (tool_result.content,
            # tool_use_result.stdout, assistant text blocks).
            for s in _walk_strings(obj):
                if "::QPB::" not in s:
                    continue
                for payload in _scan_text_for_sentinels(s):
                    key = json.dumps(payload, sort_keys=True)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append(payload)
        except json.JSONDecodeError:
            # Non-JSON line (Mode B run_playbook output, the
            # 109 fixture bare-line form, etc.) — scan raw.
            for payload in _scan_text_for_sentinels(stripped):
                key = json.dumps(payload, sort_keys=True)
                if key in seen:
                    continue
                seen.add(key)
                out.append(payload)
    return out


# v1.5.7 117: Mode B phase-name normalization. ``run_playbook``
# uses its own phase names ("Explore", "Generate", "Review",
# etc.); the rest of the harness uses the 109 names
# ("exploration", "generation", "code-review", …). Map them so
# the display surface is consistent across modes.
_MODE_B_PHASE_NAME_BY_NUM: "dict[int, str]" = {
    1: "exploration",
    2: "generation",
    3: "code-review",
    4: "spec-audit",
    5: "reconciliation",
    6: "verification",
}


def _mode_b_phase_from_stream(stream_text: str) -> "Optional[dict]":
    """v1.5.7 117: parse the last ``Phase N/6 (Name)`` line
    from a Mode B run_playbook stream. Returns a phase-shaped
    dict mirroring the 109 sentinel format
    (``{kind, phase, name, state}``) so callers can treat
    both modes uniformly, or ``None`` if no Mode B phase
    line was found.

    Mode B's stream is run_playbook's stdout — no Claude
    JSON envelope, no ``::QPB::`` sentinel. The progress
    signal the operator sees in the real run_playbook output
    is lines like ``10:59:05   Phase 1/6 (Explore): target``."""
    last_match: "Optional[re.Match]" = None
    for line in stream_text.splitlines():
        m = _MODE_B_PHASE_RE.search(line)
        if m is not None:
            last_match = m
    if last_match is None:
        return None
    try:
        phase_num = int(last_match.group(1))
    except (TypeError, ValueError):
        return None
    # Normalize to the 109 canonical name when known; fall back
    # to run_playbook's raw label otherwise.
    canonical_name = _MODE_B_PHASE_NAME_BY_NUM.get(
        phase_num, last_match.group(2).strip().lower())
    return {
        "kind": "phase",
        "phase": phase_num,
        "name": canonical_name,
        # Mode B doesn't distinguish start/done in its phase
        # banner line — use "running" so the display reads
        # "P3 code-review running" instead of an empty state.
        "state": "running",
        "note": "",
    }


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

    # Current phase: try the Mode A ::QPB:: sentinel first
    # (works for any stream that has one — including the rare
    # case of a Mode B run that piped through Claude); fall
    # back to the Mode B `Phase N/6 (Name)` parse for plain
    # run_playbook streams. Degrade gracefully — no signal of
    # either kind ⇒ "—".
    #
    # v1.5.7 117: pre-117 parse_sentinels was anchored on
    # ``^::QPB::`` and missed every real claude stream-json
    # (the sentinel is embedded inside tool_result.content).
    # The 117-rewritten parser now finds it.
    current_phase = "—"
    current_phase_name = "—"
    current_phase_state = "—"
    last_note = ""
    if stream_path.is_file():
        stream_text = _safe_read(stream_path)
        sentinels = parse_sentinels(stream_text)
        for s in reversed(sentinels):
            if s.get("kind") == "phase":
                current_phase = f"P{s.get('phase', '?')}"
                current_phase_name = s.get("name", "—")
                current_phase_state = s.get("state", "—")
                last_note = s.get("note", "")
                break
        # v1.5.7 117: Mode B fallback — run_playbook stdout
        # uses `Phase N/6 (Name)` lines, no ::QPB::.
        if current_phase == "—":
            mode_b = _mode_b_phase_from_stream(stream_text)
            if mode_b is not None:
                current_phase = f"P{mode_b['phase']}"
                current_phase_name = mode_b["name"]
                current_phase_state = mode_b["state"]
                last_note = mode_b.get("note", "")

    # v1.5.7 117: stream-activity + elapsed (operator-facing
    # liveness signal). Last-activity is the stream.ndjson
    # mtime (collector writes to it; the kernel timestamps
    # each write). Elapsed is "now - started_at" for a still-
    # running run, or "ended_at - started_at" for terminal
    # state (both ISO8601). Both degrade to "—" / None on
    # missing input.
    last_activity_iso = "—"
    elapsed_s: "Optional[int]" = None
    if stream_path.is_file():
        try:
            mtime = stream_path.stat().st_mtime
            last_activity_iso = datetime.fromtimestamp(
                mtime, tz=timezone.utc,
            ).strftime("%Y-%m-%dT%H:%M:%SZ")
        except OSError:
            pass
    # Elapsed: parse started_at from status.json (preferred)
    # or manifest entry (fallback).
    started_at_iso = ""
    if status and status.get("started_at"):
        started_at_iso = status["started_at"]
    elif entry.get("started_at"):
        started_at_iso = entry["started_at"]
    if started_at_iso:
        try:
            t0 = datetime.strptime(
                started_at_iso,
                "%Y-%m-%dT%H:%M:%SZ",
            ).replace(tzinfo=timezone.utc)
            # End time: if the run is terminal use ended_at;
            # else use last-activity (stream mtime). If
            # neither, use now.
            t1: "Optional[datetime]" = None
            if status and status.get("ended_at"):
                try:
                    t1 = datetime.strptime(
                        status["ended_at"],
                        "%Y-%m-%dT%H:%M:%SZ",
                    ).replace(tzinfo=timezone.utc)
                except ValueError:
                    t1 = None
            if t1 is None and stream_path.is_file():
                try:
                    t1 = datetime.fromtimestamp(
                        stream_path.stat().st_mtime,
                        tz=timezone.utc,
                    )
                except OSError:
                    t1 = None
            if t1 is None:
                t1 = datetime.now(timezone.utc)
            elapsed_s = max(0, int((t1 - t0).total_seconds()))
        except ValueError:
            elapsed_s = None

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
        last_activity_iso=last_activity_iso,
        elapsed_s=elapsed_s,
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
    # v1.5.7 117: compact list-view progress + last-activity
    # signal so the operator can see at-a-glance whether a
    # harness-run is alive and roughly how far along its runs
    # are. Progress is the max current_phase across all runs
    # (the front of the pack — "we've reached P3 in at least
    # one repo"); last_activity is the NEWEST stream mtime
    # across all runs (any run writing means the harness is
    # alive). Both degrade to "—" when no run has a phase /
    # no stream exists yet.
    max_phase_n: int = -1
    newest_activity_iso = "—"
    newest_activity_mtime = -1.0
    for r in runs:
        if r.current_phase.startswith("P"):
            try:
                p = int(r.current_phase[1:])
                if p > max_phase_n:
                    max_phase_n = p
            except ValueError:
                pass
        if r.stream_path.is_file():
            try:
                mtime = r.stream_path.stat().st_mtime
                if mtime > newest_activity_mtime:
                    newest_activity_mtime = mtime
                    newest_activity_iso = (
                        datetime.fromtimestamp(
                            mtime, tz=timezone.utc,
                        ).strftime("%Y-%m-%dT%H:%M:%SZ")
                    )
            except OSError:
                pass
    progress = (f"P{max_phase_n}/P6"
                if max_phase_n >= 0 else "—")
    return HarnessRunSummary(
        harness_run_dir=harness_run_dir,
        started_at=started_at,
        total_runs=len(runs),
        **counts,
        collector_alive=collector_alive,
        progress=progress,
        last_activity_iso=newest_activity_iso,
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
    BLOCKED run was silently miscounted as pending.

    v1.5.7 117: includes ``progress=<Pmax/P6>`` and
    ``active=<iso>``. Progress is the max current-phase across
    runs ("how far has the front of the pack gotten?");
    active is the newest stream-write ISO timestamp ("is the
    harness still doing anything?"). Both surface liveness for
    Mode B in particular, whose stream goes quiet between
    phases."""
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
        f"progress={summary.progress:>5} "
        f"active={summary.last_activity_iso}  "
        f"collector={coll}"
    )


def _format_elapsed(seconds: "Optional[int]") -> str:
    """v1.5.7 117: human-friendly elapsed for the drill-down
    table — ``1h2m`` / ``3m45s`` / ``42s``. ``None`` ⇒ "—"."""
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def format_run_status(rs: RunStatus) -> str:
    """Render one RunStatus row for the drill-down table.

    v1.5.7 117: includes ``elapsed=...`` + ``last=<iso>`` so
    operators can see per-run liveness without dropping into
    the live tail."""
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
        f"result={rs.result:10} pid={pid_part} "
        f"elapsed={_format_elapsed(rs.elapsed_s):>7} "
        f"last={rs.last_activity_iso}"
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
