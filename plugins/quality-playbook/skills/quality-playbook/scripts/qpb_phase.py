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

Import-discipline clean (090c, amended v1.5.9 1B.0): stdlib only,
PLUS the shared ``phase_identity`` bundled module — the single
source of truth for the phase number→name table and the
``::QPB::`` envelope writer. The number→name table used to live
here as ``_PHASE_NAMES``; v1.5.9 1B.0 extracted it to
``phase_identity`` so the sentinel, the ``run_state.jsonl`` phase
events, and the heartbeat ``phase`` field all read ONE table and
cannot drift. Shipped in BOTH channel closures (the skill calls
this at each phase boundary at adopter runtime).
"""
from __future__ import annotations

import argparse
import importlib.util as _ilu
import sys
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

# Display-only constant for the --note argparse help text. The
# AUTHORITATIVE truncation/sanitization lives in
# ``phase_identity.sanitize_note``; this mirrors only the number
# quoted in the help string (not phase identity).
_NOTE_MAX_CHARS = 240


def _resolve_phase_identity():
    """v1.5.9 1B.0: 3-step anchored resolver for the shared
    ``phase_identity`` module — same pattern qpb_validate /
    qpb_phase use for ``_purpose``. Resolves at ANY install layout
    (package form ``bin.phase_identity`` / flat form / path-load
    from this file's own directory) without ever touching a foreign
    sibling ``bin/``."""
    try:
        from bin import phase_identity as _pi  # type: ignore[import]
        return _pi
    except ImportError:
        pass
    try:
        import phase_identity as _pi  # type: ignore[no-redef, import]
        return _pi
    except ImportError:
        pass
    _pp = Path(__file__).resolve().parent / "phase_identity.py"
    _ps = _ilu.spec_from_file_location(
        "_qpb_phase_identity", _pp,
    )
    if _ps is None or _ps.loader is None:
        raise ImportError(
            f"qpb_phase: cannot resolve phase_identity — path-load "
            f"fallback target {_pp} is missing."
        )
    _pi = _ilu.module_from_spec(_ps)
    sys.modules[_ps.name] = _pi
    _ps.loader.exec_module(_pi)
    return _pi


def format_sentinel(*, phase: int, state: str,
                     note: Optional[str] = None,
                     ts: Optional[str] = None) -> str:
    """Return the ``::QPB:: {json}`` line (no trailing newline).

    Thin delegate over ``phase_identity.build_phase_sentinel`` — the
    phase name and the envelope shape both come from the shared
    definition, so this sentinel can never disagree with the
    run-state events or the heartbeat. Unit-testable; ``main``
    shells out to this then prints. Raises ``ValueError`` on a bad
    phase/state (surfaced from ``phase_identity``).
    """
    return _resolve_phase_identity().build_phase_sentinel(
        phase=phase, state=state, note=note, ts=ts,
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
        "state", choices=list(_resolve_phase_identity().PHASE_STATES),
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
