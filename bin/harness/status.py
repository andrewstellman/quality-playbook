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

import enum
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional


# v1.5.7 121: the set of TerminalState values that indicate
# a run has STOPPED — the phase-state display must NOT show
# the live-state ("running"/"start"/"done"-mid-stride) when
# the run is no longer live. PENDING + RUNNING are the
# non-terminal states.
_TERMINAL_RUN_STATES = frozenset({
    "COMPLETED", "FAILED", "TIMED_OUT", "BLOCKED",
    "ABORTED_PREP", "KILLED",
    # v1.5.7 167 drive-by: 164 + 165 added these terminal states
    # but didn't extend this constant; the 121 phase-state
    # reconciliation test enforces coverage. Without them, a Mode
    # B run that aborted on a phase OR a perpetually-starved
    # run that exceeded the 165 deadline would have its phase-
    # state stuck on "running" in the TUI.
    "ABORTED_PHASE",        # 164
    "ABANDONED_STARVED",    # 165
})


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
    # v1.5.7 172 — watchdog daemon liveness. Same age-based rule
    # as collector_alive: recent watchdog.log mtime ⇒ alive.
    watchdog_alive: bool = False


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
    # v1.5.7 153 — status.json fields the CLI/TUI now surface so
    # operators don't have to read status.json by hand.
    terminal_state: "Optional[str]" = None
    """The explicit terminal state from status.json's
    ``terminal_state`` field (KILLED / COMPLETED / FAILED /
    TIMED_OUT / BLOCKED / ABORTED_PREP). None pre-terminal."""
    ended_at: str = "—"
    """status.json's ``ended_at`` (ISO8601 UTC) — the moment
    the per-run worker reached its terminal state. "—" until
    then."""
    heartbeat: str = "—"
    """status.json's ``heartbeat`` (ISO8601 UTC) — the last
    write by the per-run worker. Useful for diagnosing stuck
    Mode B runs whose pid is alive but quiet between phases."""


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


# v1.5.7 127: canonical phase-number → primary-artifact map.
# The Tier-3 phase fallback (``_infer_phase_from_artifacts``)
# keys on these: when an agent skips ``qpb_phase`` sentinel
# emission in Mode A AND there's no Mode B progress line, the
# presence of a phase's PRIMARY gate artifact under
# ``<target>/quality/`` is evidence that phase finished writing.
# Each value is a TUPLE — some phases land under more than one
# name (the gate accepts any). Source-of-truth: the run_playbook
# gate-check sites that REQUIRE these artifacts.
#
# Intentionally NOT exhaustive: only the PRIMARY phase-boundary
# marker per phase. Secondary artifacts (EXPLORATION_ITER*.md,
# EXPLORATION_MERGED.md, exploration_role_map.json, code_reviews/)
# are deliberately excluded so a half-finished phase that wrote
# an iteration file isn't misclassified as complete.
# v1.5.7 168: the canonical phase→artifact map now lives in
# ``bin/harness/phase_artifacts.py`` (single source of truth across
# this module AND plan_runner.py::capture_phase_yn). The local
# binding is preserved as a backward-compat alias for any external
# import that pinned the old name.
from bin.harness import phase_artifacts as _phase_artifacts_mod
_PHASE_ARTIFACTS = _phase_artifacts_mod.PHASE_ARTIFACTS


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


def _infer_phase_from_artifacts(
        target_dir: "Optional[Path]") -> "Optional[dict]":
    """v1.5.7 127: last-resort phase resolution when no
    sentinel and no Mode-B progress file is available.

    Scans ``<target_dir>/quality/`` for known phase-boundary
    artifacts (per ``_PHASE_ARTIFACTS``). Returns a dict
    matching the sentinel shape used elsewhere in this
    module:
      {"phase": int, "name": str, "state": "done"}
    where ``phase`` is the HIGHEST-numbered phase with at
    least one of its artifacts present, ``name`` is the
    canonical ``_MODE_B_PHASE_NAME_BY_NUM`` slug, and
    ``state`` is always ``"done"`` (the artifact's presence
    means the phase has finished writing its primary output).

    Returns ``None`` when target_dir is None, no ``quality/``
    subdir exists, or no artifacts are present (a brand-new
    run; current_phase stays ``—``).
    """
    if target_dir is None:
        return None
    quality_dir = target_dir / "quality"
    try:
        # v1.5.7 168: delegate to the canonical helper.
        phase = _phase_artifacts_mod.infer_phase_from_artifacts(
            quality_dir)
        if phase is not None:
            return {
                "phase": phase,
                "name": _MODE_B_PHASE_NAME_BY_NUM.get(
                    phase, "—"),
                "state": "done",
            }
    except OSError:
        # A transiently-unreadable target_dir must not crash
        # the status path — degrade to "no signal".
        return None
    return None


def _resolve_manifest_path(
        entry_value: str, harness_run_dir: Path) -> Path:
    """v1.5.7 118: resolve a manifest entry's path field
    against the harness-run dir we were handed, so a copied/
    moved harness-run folder reads correctly on any machine.

    Order:
      1. Empty value ⇒ return ``harness_run_dir`` (caller
         typically derives a sub-path).
      2. Relative path ⇒ ``harness_run_dir / value``. This is
         the 118 default for new manifests.
      3. Absolute path that EXISTS ⇒ use as-is (back-compat
         for legacy 108-117 manifests on their original
         machine — nothing breaks for the unmoved case).
      4. Absolute path that does NOT exist ⇒ a legacy
         manifest whose folder has been moved/copied to a new
         location. Try to extract the part of the absolute
         path AFTER the harness-run dir's name and re-attach
         it under the new ``harness_run_dir``. Example:
         entry ``/Users/foo/qpb/aup-exp/20260527T145902Z/run-00/stream.ndjson``,
         new dir ``/tmp/copied/20260527T145902Z`` ⇒
         ``/tmp/copied/20260527T145902Z/run-00/stream.ndjson``.
      5. Failing that, fall through to ``harness_run_dir /
         basename`` — a polite degradation."""
    if not entry_value:
        return harness_run_dir
    p = Path(entry_value)
    if not p.is_absolute():
        return harness_run_dir / p
    if p.exists():
        return p
    hr_name = harness_run_dir.name
    parts = list(p.parts)
    if hr_name in parts:
        idx = parts.index(hr_name)
        tail_parts = parts[idx + 1:]
        if tail_parts:
            return harness_run_dir.joinpath(*tail_parts)
        return harness_run_dir
    return harness_run_dir / p.name


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


class TuiPathKind(enum.Enum):
    """v1.5.7 135: the three directory levels the TUI/status/tail
    commands navigate, inferred from a single positional path."""
    RUNS_ROOT = "runs_root"      # contains timestamp-shaped harness-run subdirs
    HARNESS_RUN = "harness_run"  # manifest.json OR (152) run-NN children
    RUN_NN = "run_nn"            # contains stream.ndjson OR target/ (per-run artifacts)


# v1.5.7 152: regex markers for the classifier's fallback shapes.
# _RE_RUN_NN matches per-run child dirs ("run-0", "run-00", ...);
# _RE_HARNESS_RUN_NAME matches the timestamp-shaped name every
# harness-run dir has carried since the late-2025 reorg
# (YYYYMMDDTHHMMSSZ). Used with re.fullmatch so legacy `*.bak-<TS>`
# checkpoint dirs in repos/ don't pass.
_RE_RUN_NN = re.compile(r"run-\d+")
_RE_HARNESS_RUN_NAME = re.compile(r"\d{8}T\d{6}Z")


def _dir_is_harness_run_shape(path: Path) -> bool:
    """v1.5.7 152: True iff ``path`` contains at least one
    ``run-NN/`` child with the RUN_NN shape (``stream.ndjson`` OR
    a ``target/`` subdir). Used by ``classify_tui_path`` to
    recognize harness-runs whose orchestrator was killed before
    the late-stage manifest.json write
    (``plan_runner.py:2700–2734``), and to gate the RUNS_ROOT scan
    so infrastructure subdirs like ``artifacts/`` don't false-
    positive on their own bundle manifest.json."""
    try:
        for child in path.iterdir():
            if (child.is_dir()
                    and _RE_RUN_NN.fullmatch(child.name)
                    and ((child / "stream.ndjson").exists()
                         or (child / "target").is_dir())):
                return True
    except OSError:
        pass
    return False


def classify_tui_path(path: Path) -> "TuiPathKind":
    """v1.5.7 135: infer the TUI/status/tail page kind from the
    directory's structure, so the commands take ONE positional
    path instead of the --runs-root / --dump-mode / --dump-path
    flag triple.

    Distinctive markers per kind:
      RUN_NN       → contains ``stream.ndjson`` OR a ``target/``
                     subdir (the per-run artifacts).
      HARNESS_RUN  → contains ``manifest.json`` (the 108 harness-run
                     marker), OR (152 fallback) contains one or more
                     ``run-NN/`` subdirs with the RUN_NN shape. The
                     fallback covers harness-runs whose orchestrator
                     was killed before the late-stage manifest write
                     (``plan_runner.py:2700–2734``).
      RUNS_ROOT    → contains at least one timestamp-shaped subdir
                     (``YYYYMMDDTHHMMSSZ``) that classifies as
                     HARNESS_RUN. Excludes infrastructure subdirs like
                     ``artifacts/`` (which carry their own bundle
                     manifest.json but aren't harness-runs).

    Order matters: RUN_NN is checked FIRST (a run-NN dir might
    coincidentally have a subdir; we don't want to misread it as a
    runs-root), then HARNESS_RUN, then RUNS_ROOT.

    Raises ``FileNotFoundError`` if the path doesn't exist / isn't a
    directory. Raises ``ValueError`` if it exists but matches none of
    the three kinds (caller surfaces the expected markers)."""
    if not path.is_dir():
        raise FileNotFoundError(
            f"classify_tui_path: {path} is not a directory")
    # 1. RUN_NN — per-run artifacts.
    if (path / "stream.ndjson").exists() or (path / "target").is_dir():
        return TuiPathKind.RUN_NN
    # 2. HARNESS_RUN — manifest marker, or (152) run-NN-children fallback.
    if (path / "manifest.json").is_file():
        return TuiPathKind.HARNESS_RUN
    if _dir_is_harness_run_shape(path):
        return TuiPathKind.HARNESS_RUN
    # 3. RUNS_ROOT — at least one timestamp-shaped immediate child
    # classifies as HARNESS_RUN (manifest OR the 152 fallback). The
    # name filter excludes infrastructure subdirs like artifacts/
    # whose own bundle manifest.json used to false-positive here.
    try:
        for child in path.iterdir():
            if not child.is_dir():
                continue
            if not _RE_HARNESS_RUN_NAME.fullmatch(child.name):
                continue
            if ((child / "manifest.json").is_file()
                    or _dir_is_harness_run_shape(child)):
                return TuiPathKind.RUNS_ROOT
    except OSError:
        pass
    raise ValueError(
        f"classify_tui_path: {path} matches none of RUN_NN "
        f"(stream.ndjson / target/), HARNESS_RUN (manifest.json OR "
        f"run-NN children with the RUN_NN shape), or RUNS_ROOT (a "
        f"timestamp-shaped subdir with the harness-run shape). Pass "
        f"a runs-root, a harness-run dir, or a run-NN dir.")


def _synthesize_run_status_from_dir(
        run_dir: Path,
        manifest: "Optional[dict]" = None,
        plan_meta: "Optional[dict[int, dict]]" = None,
        ) -> "Optional[RunStatus]":
    """v1.5.7 153 Task A+B: build a ``RunStatus`` for a ``run-NN/``
    dir directly from its on-disk artifacts (``invocation.json`` +
    ``status.json`` + stream/target presence), without going through
    ``manifest.json``. Used when the parent harness-run was Ctrl-C'd
    before the late-stage manifest write (``plan_runner.py:2700–
    2734``) so the manifest is missing or doesn't list this run.

    v1.5.7 160 D-prime: when the manifest IS available (the caller
    passes it explicitly), synthesis falls back to the manifest
    entry by ``run_index`` for ``repo`` / ``runner`` / ``model`` /
    ``description`` when ``invocation.json`` is absent — the
    expected case for PENDING runs (scheduler created the dir +
    listed the entry, but the worker never spawned). Resolution
    chain: ``invocation.json`` wins ⇒ then manifest entry by index
    ⇒ then ``"?"``. The unparseable-manifest case (parent's
    manifest.json is invalid JSON; caller passes ``manifest=None``
    via ``_safe_json``) degrades gracefully to ``"?"``.

    Returns ``None`` only when the dir has none of the markers a
    real run dir carries — no ``status.json``, no
    ``invocation.json``, no ``stream.ndjson``, no ``target/``. A dir
    that exists with no artifacts at all isn't a real run; it's a
    typo or stray dir. Anything else synthesizes a row, with metadata
    degraded to ``"?"`` when BOTH ``invocation.json`` AND a manifest
    entry are missing — partial information is better than a
    missing row."""
    # v1.5.7 175: if the run-NN/ dir doesn't exist on disk, we
    # may still have plan.json metadata for this index (pre-
    # launch PENDING entry the orchestrator promised but
    # hasn't created on disk). Synthesize a PENDING row when
    # plan_meta covers this index; return None only when there
    # is truly nothing to display.
    dir_exists = run_dir.exists()
    if not dir_exists:
        try:
            _idx = int(run_dir.name.split("-", 1)[1])
        except (IndexError, ValueError):
            return None
        if not plan_meta or _idx not in plan_meta:
            return None
    status = (_safe_json(run_dir / "status.json")
              if dir_exists else None)
    invocation = (_safe_json(run_dir / "invocation.json")
                  if dir_exists else None)
    stream_path = run_dir / "stream.ndjson"
    has_stream = stream_path.exists() if dir_exists else False
    has_target = ((run_dir / "target").is_dir()
                  if dir_exists else False)
    # v1.5.7 153 Task B: a ``run-NN/`` dir created by the scheduler
    # but never spawned (Ctrl-C'd during queueing) carries only
    # ``artifact_used.json`` — no status, no stream, no target. The
    # mere existence of a ``run-NN``-named dir under the harness-run
    # is the PENDING marker; we synthesize a row with degraded
    # metadata so kill/status can address it.

    # Index: parse from "run-NN" name (152's regex already enforces
    # \d+ tail). Fall back to -1 so even an off-pattern dir caller
    # surfaces something rather than nothing.
    try:
        index = int(run_dir.name.split("-", 1)[1])
    except (IndexError, ValueError):
        index = -1

    # Metadata from invocation.json (axes.runner / axes.model /
    # case_id). repo isn't in invocation.json; the harness records
    # it in the manifest entry.
    # 160 D-prime: when the caller passes the parent's parsed
    # manifest, look up the matching entry by index and fall back
    # to its repo/runner/model/description fields. This is the
    # PENDING-run case — the scheduler wrote a manifest entry with
    # the plan's repo/runner/model BEFORE the worker spawned, so
    # the entry has authoritative metadata even when there's no
    # invocation.json yet.
    manifest_entry: "Optional[dict]" = None
    if manifest and isinstance(manifest.get("runs"), list):
        for e in manifest["runs"]:
            if isinstance(e, dict) and e.get("index") == index:
                manifest_entry = e
                break

    runner = "?"
    model = "?"
    case_id = "?"
    repo = "?"
    description = ""
    if invocation:
        axes = invocation.get("axes") or {}
        runner = axes.get("runner") or runner
        model = axes.get("model") or model
        case_id = invocation.get("case_id") or case_id
    if manifest_entry:
        # Fall back to the manifest entry for fields invocation
        # didn't supply (PENDING case: no invocation.json yet, but
        # the scheduler-written manifest entry has full metadata).
        if runner == "?":
            mr = manifest_entry.get("runner")
            if mr:
                runner = str(mr)
        if model == "?":
            mm = manifest_entry.get("model")
            if mm:
                model = str(mm)
        mrepo = manifest_entry.get("repo")
        if mrepo:
            repo = str(mrepo)
        mdesc = manifest_entry.get("description")
        if mdesc:
            description = str(mdesc)
    # v1.5.7 175: plan.json[index] is the third-tier fallback
    # (when invocation AND manifest entry are absent OR don't
    # carry the field — repo is the canonical example, since
    # invocation.json never carries the upstream Git URL).
    # plan.json is written by the orchestrator at the top of
    # the launch path, BEFORE any per-run launches, so it's
    # the authoritative source for PENDING entries.
    if plan_meta and index in plan_meta:
        plan_entry = plan_meta[index]
        if runner == "?":
            pr = plan_entry.get("runner")
            if pr:
                runner = str(pr)
        if model == "?":
            pm = plan_entry.get("model")
            if pm:
                model = str(pm)
        if repo == "?":
            prepo = plan_entry.get("repo")
            if prepo:
                repo = str(prepo)
        if not description:
            pdesc = plan_entry.get("description")
            if pdesc:
                description = str(pdesc)

    # State + pid from status.json. No status.json AND no stream
    # ⇒ PENDING (Task B: dir was created when the run was queued
    # but the worker never spawned; matches the existing
    # ``state = "PENDING"`` sentinel used elsewhere in this file).
    state = "PENDING"
    pid: "Optional[int]" = None
    terminal_state_field: "Optional[str]" = None
    ended_at_field = "—"
    heartbeat_field = "—"
    started_at_iso = ""
    if status:
        if status.get("terminal_state"):
            state = status["terminal_state"]
            terminal_state_field = status["terminal_state"]
        elif status.get("state") == "RUNNING":
            state = "RUNNING"
        # Some recorded state may be neither RUNNING nor a known
        # terminal — surface it verbatim rather than masking.
        elif status.get("state"):
            state = str(status["state"])
        raw_pid = status.get("pid")
        if isinstance(raw_pid, int):
            pid = raw_pid
        if status.get("ended_at"):
            ended_at_field = status["ended_at"]
        if status.get("heartbeat"):
            heartbeat_field = status["heartbeat"]
        if status.get("started_at"):
            started_at_iso = status["started_at"]
    pid_alive = pid_is_alive(pid) if isinstance(pid, int) else False

    # last-activity: stream mtime when present, else the run-dir's
    # own mtime (when the dir was created — useful for PENDING).
    last_activity_iso = "—"
    src_mtime: "Optional[float]" = None
    if has_stream:
        try:
            src_mtime = stream_path.stat().st_mtime
        except OSError:
            pass
    if src_mtime is None:
        try:
            src_mtime = run_dir.stat().st_mtime
        except OSError:
            pass
    if src_mtime is not None:
        last_activity_iso = datetime.fromtimestamp(
            src_mtime, tz=timezone.utc,
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Elapsed: only when started_at is known.
    elapsed_s: "Optional[int]" = None
    if started_at_iso:
        try:
            t0 = datetime.strptime(
                started_at_iso, "%Y-%m-%dT%H:%M:%SZ",
            ).replace(tzinfo=timezone.utc)
            t1: "Optional[datetime]" = None
            if ended_at_field != "—":
                try:
                    t1 = datetime.strptime(
                        ended_at_field, "%Y-%m-%dT%H:%M:%SZ",
                    ).replace(tzinfo=timezone.utc)
                except ValueError:
                    t1 = None
            if t1 is None and src_mtime is not None:
                t1 = datetime.fromtimestamp(
                    src_mtime, tz=timezone.utc)
            if t1 is None:
                t1 = datetime.now(timezone.utc)
            elapsed_s = max(0, int((t1 - t0).total_seconds()))
        except ValueError:
            elapsed_s = None

    # Result: "(running)" while live; otherwise "N/A" (no grading
    # parse in this synthesis path — the caller can add per-row
    # detail if needed for a synthesized row).
    result = "(running)" if state == "RUNNING" else "N/A"

    return RunStatus(
        index=index,
        # 160 D-prime: manifest entry's description (if present)
        # wins over the case_id from invocation.json — manifest is
        # the scheduler-written authoritative source.
        description=description or case_id,
        repo=repo,
        runner=runner,
        model=model,
        state=state,
        result=result,
        current_phase="—",
        current_phase_name="—",
        current_phase_state="—",
        last_note="",
        pid=pid,
        pid_alive=pid_alive,
        stream_path=stream_path,
        run_dir=run_dir,
        last_activity_iso=last_activity_iso,
        elapsed_s=elapsed_s,
        terminal_state=terminal_state_field,
        ended_at=ended_at_field,
        heartbeat=heartbeat_field,
    )


def read_one_run_status_for_dir(
        run_dir: Path) -> "Optional[RunStatus]":
    """v1.5.7 135: build the single-run status block for a RUN_NN
    dir (e.g. ``harness_runs/<TS>/run-00``). Resolves the parent
    harness-run's manifest, finds the entry whose resolved
    ``run_dir`` matches ``run_dir``, and returns its ``RunStatus``.

    v1.5.7 153 Task A: when the manifest is missing OR doesn't list
    this run (Ctrl-C'd-mid-spawn case), fall back to synthesizing a
    row from the run dir's own ``invocation.json`` / ``status.json``
    so kill/status keep working on manifest-incomplete harness-runs.
    Returns None only when the dir has no artifacts at all."""
    harness_run_dir = run_dir.parent
    manifest = _safe_json(harness_run_dir / "manifest.json")
    # v1.5.7 175: plan.json is the third-tier metadata fallback.
    plan_meta = _load_plan_metadata(harness_run_dir)
    if manifest:
        target = run_dir.resolve()
        for entry in manifest.get("runs", []):
            entry_run_dir = _resolve_manifest_path(
                entry.get("run_dir", ""), harness_run_dir)
            if entry_run_dir.resolve() == target:
                return _read_one_run_status(
                    entry, harness_run_dir,
                    plan_meta=plan_meta)
    # 160 D-prime: pass the parent manifest so synthesis can fall
    # back to the manifest entry's repo/runner/model/description
    # for PENDING runs (the scheduler-written manifest entry IS the
    # authoritative metadata source when invocation.json is absent).
    # 175: plan_meta also passed for the pre-launch PENDING case
    # (no manifest entry yet, no invocation.json yet).
    return _synthesize_run_status_from_dir(
        run_dir, manifest=manifest, plan_meta=plan_meta)


def _load_plan_metadata(
        harness_run_dir: Path) -> "dict[int, dict]":
    """v1.5.7 175: load ``plan.json`` and index by run index.

    plan.json is the AUTHORITATIVE source for entry metadata
    (description / repo / runner / model / channel / mode) for
    ALL entries regardless of state. It's written by the
    orchestrator at the top of the launch path
    (``plan_runner.py:2974``) BEFORE any per-run launches, so it
    is present even when the operator inspects an in-progress
    harness-run (PENDING entries that don't yet have
    invocation.json + status.json).

    Per-run ``invocation.json`` carries axes (runner/model/
    install_channel) but NOT the upstream Git URL — relying on it
    for repo silently degrades to "?" for every entry. The
    pre-175 display chain (manifest entry → invocation.json) had
    no plan.json fallback; this helper supplies it.

    Returns an empty dict when plan.json is missing or
    unparseable — callers fall back to "?" gracefully."""
    plan_path = harness_run_dir / "plan.json"
    if not plan_path.is_file():
        return {}
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    runs = plan.get("runs", []) if isinstance(plan, dict) else []
    out: "dict[int, dict]" = {}
    for i, r in enumerate(runs):
        if not isinstance(r, dict):
            continue
        idx = r.get("index", i)
        try:
            out[int(idx)] = r
        except (TypeError, ValueError):
            continue
    return out


def read_run_status(harness_run_dir: Path) -> "list[RunStatus]":
    """Read ``manifest.json`` + per-run ``status.json`` + parse the
    last ``::QPB:: kind:"phase"`` line from each run's
    ``stream.ndjson``.

    v1.5.7 153 Task A: enumeration is manifest-INDEPENDENT. Manifest
    entries provide canonical metadata (repo / runner / model / pid
    seed) when present; for run-NN/ subdirs NOT listed in the
    manifest (Ctrl-C'd-mid-spawn case) we synthesize entries from
    each dir's own ``invocation.json`` + ``status.json``. The single
    result list is sorted by index. Manifest entries win on
    duplicate index (they're authoritative); dir-scan only fills
    gaps. Never raises on partially-written input.

    v1.5.7 175: plan.json is now consulted as a third fallback
    for entry metadata (description / repo / runner / model /
    channel / mode). plan.json is written by the orchestrator
    BEFORE any per-run launches, so an in-progress harness-run
    with PENDING entries (no invocation.json yet) still surfaces
    full per-entry metadata in the operator-facing status /
    --dump output. Resolution chain (highest priority first):
    manifest entry ⇒ invocation.json (axes only) ⇒ plan.json
    ⇒ "?". Runtime state (pid, started_at, terminal_state) still
    comes from status.json only — plan.json contributes BASE
    metadata, never runtime."""
    manifest = _safe_json(harness_run_dir / "manifest.json")
    # v1.5.7 175: load plan.json once and pass it down so each
    # entry's metadata can fall back to plan.json[index] when
    # neither the manifest entry nor invocation.json supplies
    # the field.
    plan_meta = _load_plan_metadata(harness_run_dir)
    by_index: "dict[int, RunStatus]" = {}
    seen_dirs: "set[Path]" = set()
    if manifest:
        for entry in manifest.get("runs", []):
            rs = _read_one_run_status(
                entry, harness_run_dir, plan_meta=plan_meta)
            by_index[rs.index] = rs
            try:
                seen_dirs.add(rs.run_dir.resolve())
            except OSError:
                pass
    # 153 Task A: scan for run-NN/ children not covered by the
    # manifest. Reuses 152's _RE_RUN_NN regex.
    try:
        for child in sorted(harness_run_dir.iterdir()):
            if not (child.is_dir()
                    and _RE_RUN_NN.fullmatch(child.name)):
                continue
            try:
                if child.resolve() in seen_dirs:
                    continue
            except OSError:
                continue
            # 160 D-prime: pass the manifest so synthesis can pull
            # repo/runner/model from the scheduler-written entry
            # when the run's invocation.json is absent (PENDING).
            # 175: also pass plan_meta — for entries the manifest
            # doesn't list yet (pre-manifest PENDING), plan.json
            # is the authoritative metadata source.
            rs = _synthesize_run_status_from_dir(
                child, manifest=manifest, plan_meta=plan_meta)
            if rs is None:
                continue
            # Manifest wins on index conflict (defensive — sorted
            # iterdir means we'd hit a duplicate only if the
            # manifest didn't record the dir but the index
            # collides, which would itself be a harness bug).
            if rs.index not in by_index:
                by_index[rs.index] = rs
    except OSError:
        pass
    # v1.5.7 175: also synthesize PENDING entries that DON'T have
    # a run-NN/ dir yet — pre-launch entries the orchestrator
    # promised in plan.json but hasn't created on disk. Surfaces
    # them as PENDING with full plan.json metadata.
    for idx, plan_entry in plan_meta.items():
        if idx in by_index:
            continue
        synthetic_dir = harness_run_dir / f"run-{idx:02d}"
        rs = _synthesize_run_status_from_dir(
            synthetic_dir, manifest=manifest,
            plan_meta=plan_meta)
        if rs is not None:
            by_index[idx] = rs
    return [by_index[i] for i in sorted(by_index)]


def _read_one_run_status(entry: dict,
                           harness_run_dir: Path,
                           plan_meta: "Optional[dict[int, dict]]" = None,
                           ) -> RunStatus:
    # v1.5.7 118: resolve manifest path entries against the
    # harness-run dir we were handed. New (post-118) manifests
    # store relative paths so the folder is portable; legacy
    # 108-117 manifests stored absolute paths — both work
    # through `_resolve_manifest_path`.
    run_dir = _resolve_manifest_path(
        entry.get("run_dir", ""), harness_run_dir)
    stream_path = _resolve_manifest_path(
        entry.get("stream_path", ""), harness_run_dir,
    ) if entry.get("stream_path") else (
        run_dir / "stream.ndjson")
    status_path = _resolve_manifest_path(
        entry.get("status_path", ""), harness_run_dir,
    ) if entry.get("status_path") else (
        run_dir / "status.json")
    grading_path = run_dir / "grading.json"
    # v1.5.7 127: resolve the target dir for the Tier-3
    # artifact-presence phase fallback (only used if both the
    # sentinel and Mode B tiers come up empty).
    target_dir = _resolve_manifest_path(
        entry.get("target_dir", ""), harness_run_dir,
    ) if entry.get("target_dir") else None

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

    # v1.5.7 127: Tier-3 fallback — scan quality/ artifacts when
    # the agent skipped sentinel emission (Mode A) AND no Mode B
    # progress line was found. Tier 1 (sentinel) and Tier 2 (Mode
    # B) still WIN when present — this only fires when both came
    # up empty, so there's no regression on the happy path. Sits
    # OUTSIDE the `stream_path.is_file()` block: an agent can
    # write quality/ artifacts even when the stream is absent or
    # carries no phase signal.
    if current_phase == "—":
        artifact_inferred = _infer_phase_from_artifacts(target_dir)
        if artifact_inferred is not None:
            current_phase = f"P{artifact_inferred['phase']}"
            current_phase_name = artifact_inferred["name"]
            current_phase_state = artifact_inferred["state"]

    # v1.5.7 121: phase-state reconciliation. When the run is
    # in a TERMINAL state (FAILED / COMPLETED / TIMED_OUT /
    # BLOCKED / ABORTED_PREP), the phase-state must NOT show
    # the live-state — a stopped run should read
    # "P1 exploration stopped", not "P1 exploration running".
    # The 117 Mode B parser ALWAYS reports "running" (run_playbook
    # has no done-state in its banner line); the 109 Mode A
    # sentinels emit start/done/running. If the run has since
    # gone terminal but the last marker is "running" or "start"
    # (started a phase but didn't finish it), override to
    # "stopped". A "done" marker stays as-is (the phase
    # completed — that's correct mid-run AND post-terminal).
    if (state in _TERMINAL_RUN_STATES
            and current_phase != "—"
            and current_phase_state in ("running", "start")):
        current_phase_state = "stopped"

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

    # v1.5.7 153 Task C: status.json fields the operator-grade
    # status/TUI now surface so the worker doesn't have to read
    # status.json by hand.
    terminal_state_field: "Optional[str]" = None
    ended_at_field = "—"
    heartbeat_field = "—"
    if status:
        if status.get("terminal_state"):
            terminal_state_field = status["terminal_state"]
        if status.get("ended_at"):
            ended_at_field = status["ended_at"]
        if status.get("heartbeat"):
            heartbeat_field = status["heartbeat"]
    # Manifest entry can also carry terminal_state (the
    # launch-side ABORTED_PREP path writes it there directly).
    if terminal_state_field is None and entry.get("terminal_state"):
        terminal_state_field = entry["terminal_state"]

    # v1.5.7 175: fall back to plan.json[index] for entry
    # metadata when the manifest entry omits it (rare —
    # well-formed manifest entries carry these). plan.json is
    # the authoritative source AT LAUNCH TIME; the manifest
    # entry is the post-launch view. For metadata-only fields
    # (description / repo / runner / model) prefer the manifest
    # if non-empty, else plan.json, else "".
    entry_index = entry.get("index", -1)
    plan_entry = (plan_meta or {}).get(entry_index, {})

    def _resolve(field: str) -> str:
        m = entry.get(field)
        if m:
            return str(m)
        p = plan_entry.get(field)
        if p:
            return str(p)
        return ""

    return RunStatus(
        index=entry_index,
        description=_resolve("description"),
        repo=_resolve("repo"),
        runner=_resolve("runner"),
        model=_resolve("model"),
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
        terminal_state=terminal_state_field,
        ended_at=ended_at_field,
        heartbeat=heartbeat_field,
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
    # v1.5.7 172: watchdog liveness. Same age-based rule against
    # watchdog.log mtime (the watchdog writes at least every
    # interval, default 60s; plus a status line every 5 ticks
    # when no orphans are found).
    watchdog_alive = False
    watchdog_log = harness_run_dir / "watchdog.log"
    if watchdog_log.is_file():
        try:
            mtime = watchdog_log.stat().st_mtime
            age = datetime.now(timezone.utc).timestamp() - mtime
            watchdog_alive = age < _COLLECTOR_LIVENESS_WINDOW_S
        except OSError:
            watchdog_alive = False
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
        watchdog_alive=watchdog_alive,
    )


# ---------------------------------------------------------------------------
# Stream tailing (CLI tail + TUI live pane both consume this)
# ---------------------------------------------------------------------------


def tail_stream(run_dir: Path, *,
                 follow: bool = False,
                 rendered: bool = True) -> Iterator[str]:
    """Yield rendered lines from ``<run_dir>/stream.ndjson``.

    v1.5.7 122 ``rendered`` toggle (default True):
      * True  ⇒ each line goes through ``render_stream_line``
        — Claude stream-json events become clean log-style
        lines (▶/·/⚙/←/■/↳/⏳ icons); bare ::QPB:: sentinels
        keep their 109/117 human-readable form; non-Claude
        plain text (codex/copilot/run_playbook) passes
        through unchanged.
      * False ⇒ each line is yielded verbatim (the pre-122
        ``tail -f`` raw behavior; for debugging the wire
        format).

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
                .rstrip("\n"),
                rendered=rendered,
            )
        if not follow:
            return
        while True:
            raw = f.readline()
            if raw:
                yield render_stream_line(
                    raw.decode("utf-8", errors="ignore")
                    .rstrip("\n"),
                    rendered=rendered,
                )
            else:
                time.sleep(0.5)


def _format_sentinel_line(payload: dict) -> "str | None":
    """Render a parsed ``::QPB::`` payload as the 109/117
    human-readable log line. Returns None for unknown kinds
    (caller falls back to the verbatim line)."""
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
    return None


# v1.5.7 122: Claude --print --output-format stream-json
# emits a fixed event vocabulary. Templating each known
# (type, subtype) into a clean log line removes the noise
# the raw JSON pours into tail/TUI/--dump output.


def render_stream_line(line: str, *,
                         rendered: bool = True) -> str:
    """v1.5.7 173: delegate to :mod:`bin.harness.stream_render`.

    The 173 port replaced the pre-173 compact-log-line glyphs
    (``▶`` / ``·`` / ``⚙`` / ``←`` / ``■`` / ``↳`` / ``⏳`` /
    ``«…»``) with the Claude-Code-TUI shape (``━━━`` banners /
    ``⏺`` tool_use / ``⎿`` tool_result / ``•`` task / ``⟨…⟩``
    meta). LOAD-BEARING ::QPB:: sentinel preservation (bare-line
    AND inline-in-tool_result variants) is intact — both render
    the phase/gate log line via :func:`_format_sentinel_line`.

    The ``rendered=False`` toggle is unchanged: raw passthrough
    for ``j`` (TUI) / ``--raw`` (tail / dump) flows.
    """
    from bin.harness.stream_render import (
        render_stream_line as _impl)
    return _impl(line, rendered=rendered)


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
    # v1.5.7 172: watchdog token alongside the collector token.
    wd = ("yes" if summary.watchdog_alive else "no")
    return (
        f"{dir_name:30} {summary.started_at:22} "
        f"runs={summary.total_runs:>2}  "
        f"R={summary.running:>2} D={summary.completed:>2} "
        f"F={summary.failed:>2} T={summary.timed_out:>2} "
        f"B={summary.blocked:>2} "
        f"AP={summary.aborted_prep:>2} P={summary.pending:>2}  "
        f"progress={summary.progress:>5} "
        f"active={summary.last_activity_iso}  "
        f"collector={coll} watchdog={wd}"
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
    the live tail. v1.5.7 153 Task C: appends ``terminal=…``,
    ``ended=…``, ``heartbeat=…`` so the status output is
    self-sufficient on manifest-incomplete harness-runs (no
    need to read status.json by hand)."""
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
    terminal_part = rs.terminal_state if rs.terminal_state else "—"
    return (
        f"#{rs.index:<2} {repo_tail:18} "
        f"{rs.runner}/{rs.model:14} "
        f"{rs.state:14} {phase_part:34} "
        f"result={rs.result:10} pid={pid_part} "
        f"elapsed={_format_elapsed(rs.elapsed_s):>7} "
        f"last={rs.last_activity_iso} "
        f"ended={rs.ended_at} terminal={terminal_part} "
        f"heartbeat={rs.heartbeat}"
    )


_TERMINAL_COMPLETED_STATES = {"COMPLETED"}
_TERMINAL_FAILED_STATES = {
    "FAILED", "TIMED_OUT", "BLOCKED", "KILLED", "ABORTED_PREP"}


def _format_run_row_for_group(rs: "RunStatus", group: str) -> str:
    """v1.5.7 160 Task B + C: render a single RunStatus row in the
    tight per-group format. The group header carries the state
    (RUNNING / PENDING / COMPLETED / FAILED) so the row doesn't
    repeat it. Task C: a RUNNING row whose pid is NOT alive (worker
    died but state.json wasn't updated to terminal) gets a
    ``pid=N(DEAD — orphan?)`` warning so operators see the
    inconsistency at a glance."""
    repo_tail = rs.repo.rstrip("/").split("/")[-1] or rs.repo
    runner_model = f"{rs.runner}/{rs.model}"
    if group == "RUNNING":
        # Task C dead-pid warning.
        if rs.pid and not rs.pid_alive:
            pid_part = f"pid={rs.pid}(DEAD — orphan?)"
        elif rs.pid_alive:
            pid_part = f"pid={rs.pid}(live)"
        elif rs.pid:
            pid_part = f"pid={rs.pid}(dead)"
        else:
            pid_part = "pid=—"
        phase_part = (
            f"{rs.current_phase} {rs.current_phase_name} "
            f"{rs.current_phase_state}"
            if rs.current_phase != "—" else "—"
        )
        return (
            f"  #{rs.index:<2} {repo_tail:18} "
            f"{runner_model:22} {pid_part:24} "
            f"{phase_part:30} "
            f"elapsed={_format_elapsed(rs.elapsed_s):>7} "
            f"last={rs.last_activity_iso}"
        )
    if group == "PENDING":
        # If the manifest/stream surfaced phase info (rare but
        # real: a run whose status.json hasn't been written yet
        # but whose stream already has a sentinel), show it so the
        # operator sees forward progress instead of a flat
        # "waiting" line.
        if rs.current_phase != "—":
            phase_part = (
                f"{rs.current_phase} {rs.current_phase_name} "
                f"{rs.current_phase_state}"
            )
            return (
                f"  #{rs.index:<2} {repo_tail:18} "
                f"{runner_model:22} {phase_part:30} "
                f"(waiting for {rs.runner} pool slot)"
            )
        return (
            f"  #{rs.index:<2} {repo_tail:18} "
            f"{runner_model:22} "
            f"(waiting for {rs.runner} pool slot)"
        )
    if group == "COMPLETED":
        return (
            f"  #{rs.index:<2} {repo_tail:18} "
            f"{runner_model:22} {rs.result:14} "
            f"ended={rs.ended_at} "
            f"elapsed={_format_elapsed(rs.elapsed_s):>7}"
        )
    if group == "FAILED":
        reason = rs.terminal_state or rs.state
        return (
            f"  #{rs.index:<2} {repo_tail:18} "
            f"{runner_model:22} {reason:18} "
            f"ended={rs.ended_at} "
            f"elapsed={_format_elapsed(rs.elapsed_s):>7}"
        )
    # Fallback for unanticipated buckets — keep the verbose form.
    return f"  {format_run_status(rs)}"


def _classify_run_for_grouping(rs: "RunStatus") -> str:
    """v1.5.7 160 Task B: bucket a RunStatus into one of four
    operator-facing groups (RUNNING / PENDING / COMPLETED / FAILED).
    FAILED catches all non-COMPLETED terminal states (FAILED,
    TIMED_OUT, BLOCKED, KILLED, ABORTED_PREP) so operators see one
    "things to look at" pile rather than parsing five state names."""
    if rs.state == "RUNNING":
        return "RUNNING"
    if rs.state == "PENDING":
        return "PENDING"
    if rs.state in _TERMINAL_COMPLETED_STATES:
        return "COMPLETED"
    if rs.state in _TERMINAL_FAILED_STATES:
        return "FAILED"
    # An unknown state still surfaces — bucket as FAILED so the
    # operator at least sees the row.
    return "FAILED"


def format_runs_grouped(runs: "list[RunStatus]") -> str:
    """v1.5.7 160 Task B: format the per-run status table grouped
    by state with section headers + counts. Empty groups are
    skipped. Each row uses ``_format_run_row_for_group`` (tight
    per-row format that doesn't repeat the state). Output order is
    operator-prioritized: active first (RUNNING, PENDING), then
    completed (the happy-path snapshot), then failed (the "look at
    this" pile)."""
    by_group: "dict[str, list[RunStatus]]" = {
        "RUNNING": [], "PENDING": [],
        "COMPLETED": [], "FAILED": [],
    }
    for rs in runs:
        by_group[_classify_run_for_grouping(rs)].append(rs)
    sections: "list[str]" = []
    for group in ("RUNNING", "PENDING", "COMPLETED", "FAILED"):
        rows = sorted(by_group[group], key=lambda r: r.index)
        if not rows:
            continue
        sections.append(f"{group} ({len(rows)}):")
        for rs in rows:
            sections.append(
                _format_run_row_for_group(rs, group))
            if rs.last_note:
                sections.append(f"     note: {rs.last_note}")
        sections.append("")  # blank line between groups
    return "\n".join(sections).rstrip()


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
    "format_runs_grouped",
]
