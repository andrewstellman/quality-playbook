#!/usr/bin/env python3
"""qpb_phase — Quality Playbook phase sentinel emitter (v1.5.7 109).

Prints a single ``::QPB::`` line to stdout marking a phase
boundary (start or done). The Test Harness status layer
(107/108) parses these lines to track which phase a run is in.

Format: ``::QPB:: {json}`` where ``json`` is a single-line JSON
object:
  * ``v``: 1 — format version (parser can evolve safely).
  * ``kind``: "phase" — always for this emitter.
  * ``phase``: int (0..6).
  * ``name``: deterministic slug from the table below
    (NOT model-supplied; the model only ever supplies the phase
    number, the state, and the optional note).
  * ``state``: "start" | "done".
  * ``ts``: UTC ISO-8601 (Zulu suffix, no microseconds).
  * ``note``: optional model-supplied free-text (display-only,
    never parsed for a decision). Newlines collapsed to spaces;
    truncated to ~240 chars; absent ⇒ no key.

Usage:
  qpb_phase <phase:int> <start|done> [--note "1-3 sentences"]

Self-describing on no-args / --help (089x).

Import-discipline clean (090c): stdlib only, no imports from
other ``bin/`` scripts. Shipped in BOTH channel closures (the
skill calls it at each phase boundary at adopter runtime).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_HARNESS_NAME = "qpb_phase"
_HARNESS_SUMMARY = (
    "Emit a Quality Playbook phase sentinel "
    "(::QPB:: phase-boundary marker)."
)
_HARNESS_USAGE = (
    "qpb_phase <phase:int> <start|done> [--note '...']"
)


# v1.5.7 109: deterministic phase-number → canonical-name table.
# Sourced from SKILL.md's phase headings ("Phase 0: Prior Run
# Analysis", "Phase 1: Explore the Codebase", ..., "Phase 6:
# Verify"). The model only ever supplies the phase NUMBER — the
# harness status layer (107/108) uses THIS table's slugs as the
# phase identity, so they never drift from model output.
_PHASE_NAMES = {
    0: "validation",      # Mode A install validator / Phase 0
    1: "exploration",     # Phase 1: Explore the Codebase
    2: "generation",      # Phase 2: Generate the Quality Playbook
    3: "code-review",     # Phase 3: Code Review + Regression Tests
    4: "spec-audit",      # Phase 4: Spec Audit and Triage
    5: "reconciliation",  # Phase 5: Post-Review Reconciliation
    6: "verification",    # Phase 6: Verify
}

_VALID_STATES = ("start", "done")
_NOTE_MAX_CHARS = 240


def _utc_now_iso() -> str:
    """UTC ISO-8601 in the format the harness uses elsewhere
    (Zulu suffix, no microseconds)."""
    return datetime.now(timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _sanitize_note(note: Optional[str]) -> Optional[str]:
    """Collapse all whitespace runs (newlines, tabs, multiple
    spaces) to a single space; truncate to ``_NOTE_MAX_CHARS``.
    None or empty-after-collapse ⇒ None (the JSON object omits
    the key)."""
    if note is None:
        return None
    cleaned = " ".join(note.split())
    if not cleaned:
        return None
    if len(cleaned) > _NOTE_MAX_CHARS:
        # Reserve one char for the ellipsis.
        cleaned = cleaned[:_NOTE_MAX_CHARS - 1] + "…"
    return cleaned


def format_sentinel(*, phase: int, state: str,
                     note: Optional[str] = None,
                     ts: Optional[str] = None) -> str:
    """Return the ``::QPB:: {json}`` line (no trailing newline).

    Unit-testable; ``main`` shells out to this then prints.
    """
    if phase not in _PHASE_NAMES:
        raise ValueError(
            f"phase {phase!r} not in 0..{max(_PHASE_NAMES)}; "
            f"legal: {sorted(_PHASE_NAMES)}"
        )
    if state not in _VALID_STATES:
        raise ValueError(
            f"state {state!r} must be one of {_VALID_STATES}"
        )
    payload = {
        "v": 1,
        "kind": "phase",
        "phase": phase,
        "name": _PHASE_NAMES[phase],
        "state": state,
        "ts": ts or _utc_now_iso(),
    }
    clean_note = _sanitize_note(note)
    if clean_note is not None:
        payload["note"] = clean_note
    # Compact separators keep the entire payload on one line so
    # the parser's "split on the prefix" stays trivial.
    return (
        f"::QPB:: "
        f"{json.dumps(payload, separators=(',', ':'))}"
    )


def _resolve_print_command_intro():
    """v1.5.7 089x + 090e: 3-step anchored fallback for the
    ``_purpose.print_command_intro`` import. Same pattern used in
    qpb_validate.py / validate_phase_artifacts.py /
    reference_docs_ingest.py so the canonical purpose banner
    resolves at ANY install layout (package form / flat form /
    path-load from this file's directory) without ever touching
    a foreign sibling ``bin/``.
    """
    try:
        from bin._purpose import (  # type: ignore[import]
            print_command_intro as _print_command_intro,
        )
        return _print_command_intro
    except ImportError:
        pass
    try:
        from _purpose import (  # type: ignore[no-redef, import]
            print_command_intro as _print_command_intro,
        )
        return _print_command_intro
    except ImportError:
        pass
    import importlib.util as _ilu
    _pp = Path(__file__).resolve().parent / "_purpose.py"
    _ps = _ilu.spec_from_file_location(
        "_qpb_purpose_via_qpb_phase", _pp,
    )
    if _ps is None or _ps.loader is None:
        raise ImportError(
            f"qpb_phase: cannot resolve _purpose — path-load "
            f"fallback target {_pp} is missing."
        )
    _purpose_mod = _ilu.module_from_spec(_ps)
    sys.modules[_ps.name] = _purpose_mod
    _ps.loader.exec_module(_purpose_mod)
    return _purpose_mod.print_command_intro


def _print_intro() -> None:
    """089x self-describing no-args output via the canonical
    ``_purpose.print_command_intro`` (carries the
    ``Quality Playbook v<ver>`` line + ``Role in a playbook
    run:`` label + ``by Andrew Stellman`` attribution footer the
    089x meta-test pins for every shipped script)."""
    _print_command_intro = _resolve_print_command_intro()
    _print_command_intro(
        name=_HARNESS_NAME,
        summary=_HARNESS_SUMMARY,
        role=(
            "v1.5.7 109 — invoked by SKILL.md at each phase "
            "boundary so the Test Harness status layer "
            "(107/108) can parse which phase a run is in. "
            "Emits one ``::QPB:: {json}`` line per call; never "
            "changes phase output, gate verdict, or grading."
        ),
        usage_hint=_HARNESS_USAGE,
    )


def main(argv: "list[str] | None" = None) -> int:
    argv_list = list(sys.argv[1:] if argv is None else argv)
    if not argv_list or argv_list in (["--help"], ["-h"]):
        _print_intro()
        return 0
    parser = argparse.ArgumentParser(
        prog=_HARNESS_NAME,
        description=_HARNESS_SUMMARY,
        add_help=True,
    )
    parser.add_argument(
        "phase", type=int,
        help="Phase number (0..6).",
    )
    parser.add_argument(
        "state", choices=list(_VALID_STATES),
        help="Phase boundary state.",
    )
    parser.add_argument(
        "--note", default=None,
        help=(
            "Optional 1-3 sentence summary (single line; "
            "newlines collapsed; truncated to "
            f"{_NOTE_MAX_CHARS} chars)."
        ),
    )
    args = parser.parse_args(argv_list)
    try:
        line = format_sentinel(
            phase=args.phase, state=args.state, note=args.note,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
