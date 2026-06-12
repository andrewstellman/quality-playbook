#!/usr/bin/env python3
"""phase_identity — Quality Playbook shared phase-identity definition
(v1.5.9 Phase 1B.0).

**Single source of truth for the phase number→name mapping.** Three
surfaces expose the worker's current phase — the ``::QPB:: kind:"phase"``
stdout sentinel (``qpb_phase.py``), the ``phase_start`` / ``phase_end``
events in ``quality/.../run_state.jsonl`` (``run_state_lib``), and the
``heartbeat.ndjson`` ``phase`` field (v1.5.9 harness). If each derived
the phase name from its own copy of the table they would drift, and a
drifted heartbeat would make the harness state machine act on the wrong
fact. This module holds the ONE table everyone reads.

"Single source of truth" here means one shared *definition* that the
emitters import — NOT one function that does everything. The emitters
stay separate code (``qpb_phase`` prints the sentinel, ``run_state_lib``
writes events + heartbeats); they just read their phase identity from
here so the ``(number, name)`` pair matches by construction.

Two name forms per phase:
  * **slug** — the deterministic identity used by the ``::QPB::``
    sentinel ``name`` field and the heartbeat ``phase`` field
    (``code-review`` etc.). This is THE phase identity the harness keys
    off.
  * **display** — the human-readable label used by
    ``run_state_lib.write_progress_md`` for ``quality/PROGRESS.md``
    (``Code Review`` etc.). A presentation projection of the same row.

This module ALSO owns the single ``::QPB:: {json}`` envelope writer
(``format_qpb_envelope``) so the one-line sentinel shape has exactly one
producer. The ``kind:"phase"`` and ``kind:"gate"`` payloads stay each
emitter's own concern (different payloads, same envelope) — per the
v1.5.9 harness design's phase-identity contract, decision 4.

Import-discipline clean: stdlib only, no imports from other bundled
``bin/`` scripts. Shipped in the adopter bundle (the skill's sentinel /
run-state / heartbeat emitters all import it at adopter runtime).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Optional


# v1.5.9 1B.0: the ONE phase-number → (slug, display) table.
# Extracted from qpb_phase.py's _PHASE_NAMES (slugs) and
# run_state_lib.write_progress_md's phase_names (display labels), which
# were independent copies before this step. Slugs are sourced from
# SKILL.md's phase headings ("Phase 0: Prior Run Analysis" / validation,
# "Phase 1: Explore the Codebase" / exploration, ..., "Phase 6: Verify"
# / verification). Display labels match the shipped pipeline documented
# in SKILL.md and references/orchestrator_protocol.md (v1.5.6 cluster B).
# The model only ever supplies the phase NUMBER; everything downstream
# derives the name from THIS table, so they cannot drift from each other.
_PHASES: dict[int, tuple[str, str]] = {
    0: ("validation", "Validation"),      # Mode A install validator / Phase 0
    1: ("exploration", "Explore"),        # Phase 1: Explore the Codebase
    2: ("generation", "Generate"),        # Phase 2: Generate the Quality Playbook
    3: ("code-review", "Code Review"),    # Phase 3: Code Review + Regression Tests
    4: ("spec-audit", "Spec Audit"),      # Phase 4: Spec Audit and Triage
    5: ("reconciliation", "Reconciliation"),  # Phase 5: Post-Review Reconciliation
    6: ("verification", "Verify"),        # Phase 6: Verify
}

# Public, frozen view of the legal phase numbers (0..6).
PHASE_NUMBERS = frozenset(_PHASES)

# Heartbeat NDJSON schema version (v1.5.9 harness design §Heartbeat).
# v2 (instruction 010 / FR-18): the generic surface carries a single free
# `label` string + an opaque `data` object instead of the v1 `phase`/`step`
# pair. QPB maps its phase identity into `label` (e.g. "2:generation") and
# stashes the legacy step under `data.step`. The harness reader still
# accepts v1 lines (Postel).
HEARTBEAT_SCHEMA_VERSION = "2"

# Legal phase-boundary states (public — qpb_phase's argparse reads it).
PHASE_STATES = ("start", "done")
_VALID_STATES = PHASE_STATES
_NOTE_MAX_CHARS = 240


def valid_phase(phase: object) -> bool:
    """True iff ``phase`` is a legal phase number (0..6)."""
    return phase in _PHASES


def phase_slug(phase: int) -> str:
    """Canonical slug identity for ``phase`` (the sentinel/heartbeat
    name). Raises ``ValueError`` for an out-of-range phase."""
    _require_phase(phase)
    return _PHASES[phase][0]


def phase_display(phase: int) -> str:
    """Human-readable display label for ``phase`` (PROGRESS.md).
    Raises ``ValueError`` for an out-of-range phase."""
    _require_phase(phase)
    return _PHASES[phase][1]


def phase_identity(phase: int) -> "tuple[int, str]":
    """The ``(number, name)`` pair the harness keys off — the unit the
    1B.0 regression test pins identical across sentinel / run-state /
    heartbeat. ``name`` is the slug."""
    _require_phase(phase)
    return (phase, _PHASES[phase][0])


def _require_phase(phase: object) -> None:
    if phase not in _PHASES:
        raise ValueError(
            f"phase {phase!r} not in 0..{max(_PHASES)}; "
            f"legal: {sorted(_PHASES)}"
        )


def utc_now_iso() -> str:
    """UTC ISO-8601 (Zulu suffix, no microseconds) — the timestamp
    format every QPB surface uses."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_qpb_envelope(payload: dict) -> str:
    """Return the single ``::QPB:: {json}`` line (no trailing newline)
    for ``payload``. The ONE writer of that line shape — the phase
    sentinel and the gate sentinel both go through here so the envelope
    can never drift. Compact separators keep the whole payload on one
    line so the parser's "split on the prefix" stays trivial."""
    return f"::QPB:: {json.dumps(payload, separators=(',', ':'))}"


def sanitize_note(note: Optional[str]) -> Optional[str]:
    """Collapse all whitespace runs to a single space; truncate to
    ``_NOTE_MAX_CHARS``. None / empty-after-collapse ⇒ None (caller
    omits the key)."""
    if note is None:
        return None
    cleaned = " ".join(note.split())
    if not cleaned:
        return None
    if len(cleaned) > _NOTE_MAX_CHARS:
        cleaned = cleaned[:_NOTE_MAX_CHARS - 1] + "…"
    return cleaned


def build_phase_payload(*, phase: int, state: str,
                        note: Optional[str] = None,
                        ts: Optional[str] = None) -> dict:
    """Build the ``kind:"phase"`` sentinel payload dict from the shared
    identity. ``name`` is always ``phase_slug(phase)`` — never
    model-supplied. Raises ``ValueError`` on a bad phase/state."""
    _require_phase(phase)
    if state not in _VALID_STATES:
        raise ValueError(
            f"state {state!r} must be one of {_VALID_STATES}"
        )
    payload = {
        "v": 1,
        "kind": "phase",
        "phase": phase,
        "name": _PHASES[phase][0],
        "state": state,
        "ts": ts or utc_now_iso(),
    }
    clean_note = sanitize_note(note)
    if clean_note is not None:
        payload["note"] = clean_note
    return payload


def build_phase_sentinel(*, phase: int, state: str,
                         note: Optional[str] = None,
                         ts: Optional[str] = None) -> str:
    """The ``::QPB:: kind:"phase"`` line for a boundary, keyed off the
    shared identity. ``qpb_phase`` delegates here."""
    return format_qpb_envelope(
        build_phase_payload(phase=phase, state=state, note=note, ts=ts)
    )


# Heartbeat status enum (v1.5.9 harness design §Heartbeat line schema).
HEARTBEAT_STATES = ("STARTING", "IN_PROGRESS", "COMPLETED", "FAILED")


def build_heartbeat_obj(*, phase: int, task_id: str, step: str,
                        status: str, ts: Optional[str] = None,
                        message: Optional[str] = None,
                        schema_version: str = HEARTBEAT_SCHEMA_VERSION
                        ) -> dict:
    """Build one heartbeat NDJSON object (schema v2). QPB maps its phase
    IDENTITY into the generic ``label`` field — ``"<number>:<slug>"`` (e.g.
    ``"2:generation"``) — derived from the SAME shared table as the
    sentinel, so a heartbeat's phase still matches the sentinel by
    construction. The legacy ``step`` is preserved under the opaque
    ``data.step`` escape hatch (the harness never reads ``data``). Callers
    keep passing ``phase``/``step``; only the on-disk shape generalized.
    Raises ``ValueError`` on a bad phase/status."""
    _require_phase(phase)
    if status not in HEARTBEAT_STATES:
        raise ValueError(
            f"status {status!r} must be one of {HEARTBEAT_STATES}"
        )
    obj = {
        "ts": ts or utc_now_iso(),
        "task_id": task_id,
        "schema_version": schema_version,
        "label": "%d:%s" % (phase, _PHASES[phase][0]),
        "status": status,
        "data": {"step": step},
    }
    if message is not None:
        obj["message"] = message
    return obj
