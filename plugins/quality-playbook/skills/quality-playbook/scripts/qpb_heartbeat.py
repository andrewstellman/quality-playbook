#!/usr/bin/env python3
"""qpb_heartbeat — Quality Playbook worker-side heartbeat emit helper
(v1.5.9 Phase 1B; NET-NEW on this branch).

The worker (loaded with the QPB skill, running a playbook under the
harness) emits heartbeat lines to ``heartbeat.ndjson`` so the harness
orchestrator can track progress and detect stalls. Phase-BOUNDARY
heartbeats already come from the 1B.0 phase-transition facade
(``run_state_lib.emit_phase_transition``); THIS helper covers the
non-boundary moments the design's heartbeat contract names: the
mandatory ~3-min mid-phase keepalive, on-error, and the terminal
sentinel.

Subcommands:
  keepalive  — mid-phase liveness ping. Reads the CURRENT phase from
               ``run_state.jsonl`` (the canonical position, decision 3)
               and appends an IN_PROGRESS line — so even the ping's
               phase derives from the same shared identity and can't
               drift from the sentinel. No-op (exit 0) if no phase is
               open yet.
  emit       — explicit progress heartbeat (STARTING/IN_PROGRESS/
               COMPLETED/FAILED) with an explicit --phase + --step
               (e.g. on-error before re-raising).
  terminal   — the terminal sentinel (last line): COMPLETED/FAILED/
               ABANDONED + --result-file + --summary, no phase/step.

Carry-forwards honored (1A spike Council B-F3/F4): EVERY value is
JSON-encoded via ``json.dumps`` — never ``printf``-interpolated — so a
``%``, ``"`` or ``\\`` in any field can't corrupt the line. Append is
``O_APPEND`` (Council A-1: concurrent appends to one file can't tear).
Every line carries ``schema_version="2"`` (instruction 010 / FR-18: the
generic label/data surface; the harness reader still accepts v1, Postel).

Phase identity comes from the shared ``phase_identity`` module (NEVER a
private copy) — same single source of truth as the sentinel and the
run-state events.

Mode A (no harness orchestrating): when neither ``--heartbeat-path`` /
``QPB_HEARTBEAT_PATH`` nor ``--task-id`` / ``QPB_TASK_ID`` is set AND
``--mode-a-noop`` is passed, the call silently exits 0. The interactive
Mode-A worker still calls the script because the prose says to, but
nobody is listening, so it no-ops.

Exit codes: 0 ok / mode-A no-op; 2 missing required heartbeat-path or
task-id; 3 bad phase/status; 64 argparse error.

Import-discipline: stdlib + the shared ``phase_identity`` / ``run_state_lib``
bundled modules (resolved via the standard 3-step anchored fallback).
Self-describing on no-args / --help (089x). Bundled at adopter runtime.
"""
from __future__ import annotations

import argparse
import importlib.util as _ilu
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_HARNESS_NAME = "qpb_heartbeat"
_HARNESS_SUMMARY = (
    "Emit a Quality Playbook worker heartbeat line "
    "(keepalive / progress / terminal) to heartbeat.ndjson."
)
_HARNESS_USAGE = (
    "qpb_heartbeat (keepalive|emit|terminal) [--task-id ID] "
    "[--heartbeat-path P] ..."
)

_TERMINAL_STATUSES = ("COMPLETED", "FAILED", "ABANDONED")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _anchored_resolve(modname: str, filename: str):
    """3-step anchored resolver (``from bin`` → flat → path-load from
    this file's own directory) — the same pattern qpb_phase uses, so a
    bundled sibling resolves at any install layout without touching a
    foreign ``bin/``."""
    try:
        return __import__("bin." + filename[:-3], fromlist=[filename[:-3]])
    except ImportError:
        pass
    try:
        return __import__(filename[:-3])
    except ImportError:
        pass
    target = Path(__file__).resolve().parent / filename
    spec = _ilu.spec_from_file_location(modname, target)
    if spec is None or spec.loader is None:
        raise ImportError(
            f"qpb_heartbeat: cannot resolve {filename} — path-load "
            f"fallback target {target} is missing.")
    mod = _ilu.module_from_spec(spec)
    sys.modules[modname] = mod
    spec.loader.exec_module(mod)
    return mod


def _phase_identity():
    return _anchored_resolve("_qpb_heartbeat_phase_identity", "phase_identity.py")


def _run_state_lib():
    return _anchored_resolve("_qpb_heartbeat_run_state_lib", "run_state_lib.py")


def _resolve_phase_number(pi, raw: str) -> int:
    """Accept a phase NUMBER (0..6) or a canonical SLUG; return the
    number. Raises ValueError on neither."""
    try:
        n = int(raw)
        if pi.valid_phase(n):
            return n
    except (TypeError, ValueError):
        pass
    for n in pi.PHASE_NUMBERS:
        if pi.phase_slug(n) == raw:
            return n
    raise ValueError(
        f"--phase {raw!r} is neither a phase number 0..6 nor a known "
        f"slug ({sorted(pi.phase_slug(n) for n in pi.PHASE_NUMBERS)})")


def _append(heartbeat_path: Path, obj: dict) -> None:
    """Atomic O_APPEND of one JSON-encoded NDJSON line (Council A-1).
    json.dumps handles all escaping (carry-forward B-F3/F4)."""
    line = json.dumps(obj, separators=(",", ":"))
    if "\n" in line:
        raise ValueError("encoded heartbeat line contains a literal newline")
    heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(heartbeat_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, (line + "\n").encode("utf-8"))
    finally:
        os.close(fd)


def _resolve_io(args):
    """Resolve heartbeat-path + task-id from flags then env. Returns
    (heartbeat_path, task_id) or (None, None) if unresolved."""
    hb = args.heartbeat_path or os.environ.get("QPB_HEARTBEAT_PATH")
    tid = args.task_id or os.environ.get("QPB_TASK_ID")
    return (hb, tid)


def _require_io(args) -> "tuple[Path, str]":
    hb, tid = _resolve_io(args)
    if not hb or not tid:
        if getattr(args, "mode_a_noop", False):
            sys.exit(0)  # Mode A: nobody listening, silent no-op
        missing = []
        if not hb:
            missing.append("--heartbeat-path / QPB_HEARTBEAT_PATH")
        if not tid:
            missing.append("--task-id / QPB_TASK_ID")
        print(f"qpb_heartbeat: missing required {', '.join(missing)} "
              f"(or pass --mode-a-noop for the interactive Mode-A case)",
              file=sys.stderr)
        sys.exit(2)
    return (Path(hb), tid)


def _cmd_keepalive(args) -> int:
    hb, tid = _require_io(args)
    run_state = args.run_state or os.environ.get("QPB_RUN_STATE")
    if not run_state:
        print("qpb_heartbeat keepalive: --run-state / QPB_RUN_STATE required "
              "(the keepalive reads its phase from run_state.jsonl)",
              file=sys.stderr)
        return 2
    rsl = _run_state_lib()
    obj = rsl.emit_keepalive_heartbeat(
        run_state_path=Path(run_state), heartbeat_path=hb,
        task_id=tid, step=args.step or "keepalive")
    if obj is None:
        # No phase open yet — nothing to ping. Not an error.
        return 0
    return 0


def _cmd_emit(args) -> int:
    hb, tid = _require_io(args)
    pi = _phase_identity()
    try:
        phase = _resolve_phase_number(pi, args.phase)
        obj = pi.build_heartbeat_obj(
            phase=phase, task_id=tid, step=args.step,
            status=args.status, message=args.message)
    except ValueError as exc:
        print(f"qpb_heartbeat emit: {exc}", file=sys.stderr)
        return 3
    _append(hb, obj)
    return 0


def _cmd_terminal(args) -> int:
    hb, tid = _require_io(args)
    if args.status not in _TERMINAL_STATUSES:
        print(f"qpb_heartbeat terminal: --status must be one of "
              f"{_TERMINAL_STATUSES}, got {args.status!r}", file=sys.stderr)
        return 3
    obj = {
        "ts": _utc_iso(),
        "task_id": tid,
        "schema_version": "2",
        "status": args.status,
        "result_file": args.result_file,
        "summary": args.summary,
    }
    _append(hb, obj)
    return 0


def _resolve_print_command_intro():
    """089x self-describing banner via the canonical _purpose helper,
    3-step anchored (matches qpb_phase / qpb_validate)."""
    try:
        from bin._purpose import print_command_intro as p  # type: ignore
        return p
    except ImportError:
        pass
    try:
        from _purpose import print_command_intro as p  # type: ignore[no-redef]
        return p
    except ImportError:
        pass
    pp = Path(__file__).resolve().parent / "_purpose.py"
    spec = _ilu.spec_from_file_location("_qpb_heartbeat_purpose", pp)
    if spec is None or spec.loader is None:
        raise ImportError(f"qpb_heartbeat: cannot resolve _purpose at {pp}")
    mod = _ilu.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod.print_command_intro


def _print_intro() -> None:
    _resolve_print_command_intro()(
        name=_HARNESS_NAME,
        summary=_HARNESS_SUMMARY,
        role=(
            "v1.5.9 1B — invoked by the QPB worker SKILL.md heartbeat "
            "section under the harness: the ~3-min keepalive, on-error, "
            "and terminal moments. Phase-boundary heartbeats come from "
            "the 1B.0 facade. Phase identity is read from phase_identity; "
            "every value is JSON-encoded; appends are O_APPEND."),
        usage_hint=_HARNESS_USAGE,
    )


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=_HARNESS_NAME, description=_HARNESS_SUMMARY)
    sub = p.add_subparsers(dest="cmd")

    def _common(sp):
        sp.add_argument("--task-id", default=None)
        sp.add_argument("--heartbeat-path", default=None)
        sp.add_argument("--mode-a-noop", action="store_true")

    ka = sub.add_parser("keepalive", help="mid-phase keepalive (reads phase from run_state)")
    _common(ka)
    ka.add_argument("--run-state", default=None)
    ka.add_argument("--step", default="keepalive")

    em = sub.add_parser("emit", help="explicit progress heartbeat")
    _common(em)
    em.add_argument("--phase", required=True, help="phase number 0..6 or slug")
    em.add_argument("--step", required=True)
    em.add_argument("--status", required=True,
                    choices=["STARTING", "IN_PROGRESS", "COMPLETED", "FAILED"])
    em.add_argument("--message", default=None)

    tm = sub.add_parser("terminal", help="terminal sentinel (last line)")
    _common(tm)
    tm.add_argument("--status", required=True, choices=list(_TERMINAL_STATUSES))
    tm.add_argument("--result-file", required=True)
    tm.add_argument("--summary", required=True)
    return p


def main(argv: "list[str] | None" = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list or args_list in (["--help"], ["-h"]):
        _print_intro()
        return 0
    parser = _build_parser()
    args = parser.parse_args(args_list)
    if args.cmd == "keepalive":
        return _cmd_keepalive(args)
    if args.cmd == "emit":
        return _cmd_emit(args)
    if args.cmd == "terminal":
        return _cmd_terminal(args)
    parser.print_help(sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main())
