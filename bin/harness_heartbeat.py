#!/usr/bin/env python3
"""harness_heartbeat  -  generic, payload-agnostic heartbeat emit helper
(v1.5.9 Phase 2B; the standalone harness core).

The GENERIC heartbeat surface (FR-18..21). Unlike QPB's ``qpb_heartbeat.py``
(which resolves a phase NUMBER through ``phase_identity`` and reads the
keepalive position from ``run_state.jsonl``), this helper treats ``label``
as a FREE STRING (FR-18) and has no QPB coupling  -  it is the part that
extracts to the standalone repo verbatim. QPB's vendored integration layers
its phase-identity derivation on top (mapping phase identity into ``label``
e.g. ``2:generation``); that coupling never enters this core.

A worker appends single-line JSON heartbeat records to a known file so the
tick engine can track progress and detect stalls. The contract: ``status``
is the ONLY field the harness interprets; ``label`` is a short free string
it displays (column ACTIVITY) but never reads; ``data`` is an opaque object
it never reads. Subcommands:

  emit       progress record: --label <str>
             --status STARTING|IN_PROGRESS|COMPLETED|FAILED [--message]
             [--data <json-object>]
  keepalive  mid-work liveness ping: reads the CURRENT label from the LAST
             heartbeat line (the canonical position in the generic core  -
             there is no run_state.jsonl) and appends an IN_PROGRESS line,
             so the ping's label can't drift. --label overrides; no-op if
             no prior label and no --label.
  terminal   last line: --status COMPLETED|FAILED|ABANDONED
             --result-file <path> --summary <text>

Disciplines (FR-19): every value is JSON-encoded via ``json.dumps`` (never
printf-interpolated, so %/"/\\ are safe); appends are atomic ``O_APPEND``;
every line carries ``schema_version="2"`` (FR-18). Postel: the harness
READER also accepts v1 lines (``phase``/``step``); this helper only EMITS
v2.

E6 (FR-21): if the append FAILS, the helper exits NONZERO loudly (it never
swallows the error)  -  a silent worker must never look healthy. Worker
guidance: on a nonzero heartbeat exit, abort the job with a FAILED
terminal (the orchestrator will reap it as failed rather than stall).

Mode A: when neither ``--heartbeat-path`` / ``HARNESS_HEARTBEAT_PATH`` (or
the QPB aliases ``QPB_HEARTBEAT_PATH``) nor ``--task-id`` / the TASK_ID
env is set AND ``--mode-a-noop`` is passed, the call silently exits 0.

Exit codes: 0 ok / mode-A no-op; 2 missing heartbeat-path or task-id;
3 bad status; 5 heartbeat write failure (E6); 64 argparse error.

Stdlib only. Cross-platform (NFR-1/3). ASCII-safe diagnostics (NFR-7).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


_NAME = "harness_heartbeat"
_PROGRESS_STATES = ("STARTING", "IN_PROGRESS", "COMPLETED", "FAILED")
_TERMINAL_STATES = ("COMPLETED", "FAILED", "ABANDONED")
SCHEMA_VERSION = "2"

# Env aliases: generic names first, QPB names tolerated for vendored use.
_HB_ENV = ("HARNESS_HEARTBEAT_PATH", "QPB_HEARTBEAT_PATH")
_TID_ENV = ("HARNESS_TASK_ID", "QPB_TASK_ID")


def _utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _env(names) -> Optional[str]:
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return None


def append_line(heartbeat_path: Path, obj: dict) -> None:
    """Atomic O_APPEND of one JSON-encoded NDJSON line. Raises OSError on
    a write failure (the caller turns that into the E6 loud nonzero exit)."""
    line = json.dumps(obj, separators=(",", ":"))
    if "\n" in line:
        raise ValueError("encoded heartbeat line contains a literal newline")
    heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(heartbeat_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        os.write(fd, (line + "\n").encode("utf-8"))
    finally:
        os.close(fd)


def last_label(heartbeat_path: Path) -> Optional[str]:
    """Return the ``label`` of the most recent heartbeat line carrying one
    (the generic 'current position'), or None. Postel: a v1 line carries
    ``phase`` instead of ``label`` — fall back to it so the keepalive reuses
    a v1 position too. Reads with errors='replace' (NFR-7  -  external
    worker content); a malformed line is skipped, never fatal."""
    if not heartbeat_path.is_file():
        return None
    try:
        lines = heartbeat_path.read_text(
            encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for ln in reversed(lines):
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except ValueError:
            continue  # Postel: skip a malformed line, keep scanning
        if isinstance(obj, dict) and (obj.get("label") or obj.get("phase")):
            return str(obj.get("label") or obj.get("phase"))
    return None


def build_progress(*, label: str, task_id: str, status: str,
                   message: Optional[str] = None,
                   data: Optional[dict] = None,
                   ts: Optional[str] = None) -> dict:
    if status not in _PROGRESS_STATES:
        raise ValueError(
            f"status {status!r} must be one of {_PROGRESS_STATES}")
    obj = {"ts": ts or _utc_iso(), "task_id": task_id,
           "schema_version": SCHEMA_VERSION, "label": str(label),
           "status": status}
    if message is not None:
        obj["message"] = message
    if data is not None:
        obj["data"] = data
    return obj


def build_terminal(*, task_id: str, status: str, result_file: str,
                   summary: str, ts: Optional[str] = None) -> dict:
    if status not in _TERMINAL_STATES:
        raise ValueError(
            f"terminal status {status!r} must be one of {_TERMINAL_STATES}")
    return {"ts": ts or _utc_iso(), "task_id": task_id,
            "schema_version": SCHEMA_VERSION, "status": status,
            "result_file": result_file, "summary": summary}


def _resolve_io(args):
    hb = args.heartbeat_path or _env(_HB_ENV)
    tid = args.task_id or _env(_TID_ENV)
    return (hb, tid)


def _require_io(args):
    hb, tid = _resolve_io(args)
    if not hb or not tid:
        if getattr(args, "mode_a_noop", False):
            sys.exit(0)
        missing = []
        if not hb:
            missing.append("--heartbeat-path / HARNESS_HEARTBEAT_PATH")
        if not tid:
            missing.append("--task-id / HARNESS_TASK_ID")
        print(f"{_NAME}: missing required {', '.join(missing)} "
              f"(or pass --mode-a-noop)", file=sys.stderr)
        sys.exit(2)
    return (Path(hb), tid)


def _append_or_die(hb: Path, obj: dict) -> int:
    """E6: append, or exit 5 loudly. Never swallow a heartbeat failure."""
    try:
        append_line(hb, obj)
    except (OSError, ValueError) as exc:
        print(f"{_NAME}: HEARTBEAT WRITE FAILED ({exc})  -  the worker must "
              f"abort this job with a FAILED terminal; a silent worker must "
              f"never look healthy (E6).", file=sys.stderr)
        return 5
    return 0


def _parse_data(raw: Optional[str]):
    """Parse the optional --data JSON-object string. Returns None if unset;
    raises ValueError if it isn't a JSON object."""
    if raw is None:
        return None
    obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("--data must be a JSON object")
    return obj


def _cmd_emit(args) -> int:
    hb, tid = _require_io(args)
    try:
        data = _parse_data(getattr(args, "data", None))
        obj = build_progress(label=args.label, task_id=tid,
                             status=args.status, message=args.message,
                             data=data)
    except ValueError as exc:
        print(f"{_NAME} emit: {exc}", file=sys.stderr)
        return 3
    return _append_or_die(hb, obj)


def _cmd_keepalive(args) -> int:
    hb, tid = _require_io(args)
    label = args.label or last_label(hb)
    if label is None:
        return 0  # nothing to ping yet  -  not an error
    obj = build_progress(label=label, task_id=tid, status="IN_PROGRESS")
    return _append_or_die(hb, obj)


def _cmd_terminal(args) -> int:
    hb, tid = _require_io(args)
    try:
        obj = build_terminal(task_id=tid, status=args.status,
                            result_file=args.result_file, summary=args.summary)
    except ValueError as exc:
        print(f"{_NAME} terminal: {exc}", file=sys.stderr)
        return 3
    return _append_or_die(hb, obj)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog=_NAME, description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd")

    def common(sp):
        sp.add_argument("--task-id", default=None)
        sp.add_argument("--heartbeat-path", default=None)
        sp.add_argument("--mode-a-noop", action="store_true")

    em = sub.add_parser("emit", help="progress heartbeat")
    common(em)
    em.add_argument("--label", required=True,
                    help="free-string activity label (displayed, not interpreted)")
    em.add_argument("--status", required=True, choices=list(_PROGRESS_STATES))
    em.add_argument("--message", default=None)
    em.add_argument("--data", default=None,
                    help="optional opaque JSON object (harness never reads it)")

    ka = sub.add_parser("keepalive", help="liveness ping (reuses last label)")
    common(ka)
    ka.add_argument("--label", default=None,
                    help="override; default = last heartbeat's label")

    tm = sub.add_parser("terminal", help="terminal sentinel (last line)")
    common(tm)
    tm.add_argument("--status", required=True, choices=list(_TERMINAL_STATES))
    tm.add_argument("--result-file", required=True)
    tm.add_argument("--summary", required=True)
    return p


def main(argv=None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list or args_list in (["-h"], ["--help"]):
        print(__doc__.strip())
        return 0
    parser = _build_parser()
    args = parser.parse_args(args_list)
    if args.cmd == "emit":
        return _cmd_emit(args)
    if args.cmd == "keepalive":
        return _cmd_keepalive(args)
    if args.cmd == "terminal":
        return _cmd_terminal(args)
    parser.print_help(sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main())
