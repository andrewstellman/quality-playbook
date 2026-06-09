#!/usr/bin/env python3
"""qpb_heartbeat.py — v1.5.9 canonical heartbeat emit helper.

The single source of truth for heartbeat emission. The QPB worker
skill calls this script at phase boundaries, every ~3 min mid-phase
(mandatory keepalive), on any error before re-throwing, and at
terminal. The harness skill (plugins/quality-playbook-harness/) tails
heartbeat.ndjson and applies state-machine transitions per
references/STATE_MACHINE.md.

Per Council finding A-1: the script does an atomic O_APPEND on the
NDJSON file, so concurrent invocations against the same path can't
corrupt each other. Per Council finding C-3: every emitted line
includes schema_version="1"; the harness warns on mismatch.

stdlib-only (no jsonschema dep) — the QPB worker runs under whatever
Python is on the host. Required-field validation is implemented
inline by reading the heartbeat schema and checking the produced dict
against it.

CLI:

    qpb_heartbeat.py emit \\
        --phase <name> --step <name> --status <enum> \\
        [--message <text>] \\
        [--task-id <uuid>] [--heartbeat-path <path>]

    qpb_heartbeat.py terminal \\
        --status <COMPLETED|FAILED|ABANDONED> \\
        --result-file <path> --summary <text> \\
        [--task-id <uuid>] [--heartbeat-path <path>]

Mode A fallback (no env vars, no flags, no harness orchestrating):

    qpb_heartbeat.py emit --mode-a-noop ...

When neither --task-id / --heartbeat-path nor the QPB_TASK_ID /
QPB_HEARTBEAT_PATH env vars are set AND the --mode-a-noop flag is
passed, the script silently exits 0. This matches the QPB SKILL.md
"Heartbeat emission contract" section's Mode A interactive case
where no harness is orchestrating: the worker still calls the script
because the phase prompts say to, but nobody is listening, so the
call no-ops.

Exit codes:
    0  Success (line appended, or Mode A no-op).
    2  Missing required input (--task-id / QPB_TASK_ID, or
       --heartbeat-path / QPB_HEARTBEAT_PATH).
    3  Schema-validation failure (the produced line does not match
       the heartbeat schema).
    64 Bad invocation (argparse error).

Source of truth path resolution: the heartbeat schema is read from
``plugins/quality-playbook/skills/quality-playbook/schemas/heartbeat.schema.json``
relative to the canonical script location (5 parents up; same idiom
as install_skill.py post-209).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


# v1.5.9 instruction 210: canonical script lives at
# plugins/quality-playbook/skills/quality-playbook/scripts/qpb_heartbeat.py
# Repo root is 5 parents up:
#   scripts -> quality-playbook(skill) -> skills -> quality-playbook(plugin) -> plugins -> repo-root
_SCRIPT_DIR = Path(__file__).resolve().parent
_QPB_ROOT = _SCRIPT_DIR.parents[4]
_HEARTBEAT_SCHEMA_PATH = (
    _QPB_ROOT / "plugins" / "quality-playbook"
    / "skills" / "quality-playbook" / "schemas" / "heartbeat.schema.json"
)


_VALID_PROGRESS_STATUSES = {"STARTING", "IN_PROGRESS", "COMPLETED", "FAILED"}
_VALID_TERMINAL_STATUSES = {"COMPLETED", "FAILED", "ABANDONED"}


def _utc_now_iso() -> str:
    """ISO8601 UTC timestamp with second precision, Z suffix."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_schema() -> dict:
    """Read the heartbeat schema for inline required-field validation.

    Returns an empty dict if the schema file is missing — we degrade
    gracefully (still emit, log a stderr WARN) rather than blocking
    the worker. The Phase 1C quality_gate invariant catches missing
    schemas at a different layer.
    """
    if not _HEARTBEAT_SCHEMA_PATH.is_file():
        print(
            f"qpb_heartbeat: WARN heartbeat schema not found at "
            f"{_HEARTBEAT_SCHEMA_PATH}; skipping schema validation",
            file=sys.stderr,
        )
        return {}
    try:
        with open(_HEARTBEAT_SCHEMA_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"qpb_heartbeat: WARN could not read schema "
            f"{_HEARTBEAT_SCHEMA_PATH}: {exc}",
            file=sys.stderr,
        )
        return {}


def _validate_line(line: dict, schema: dict, *, is_terminal: bool) -> "list[str]":
    """Inline required-field check (stdlib-only, no jsonschema).

    Returns a list of validation-failure messages; empty list means
    the line is valid.
    """
    errors: list[str] = []

    # Top-level required fields from the schema's "required" array.
    top_required = schema.get("required", []) if schema else [
        "ts", "task_id", "schema_version", "status",
    ]
    for field in top_required:
        if field not in line:
            errors.append(f"missing required top-level field: {field}")

    # task_id must look like a UUID.
    task_id = line.get("task_id")
    if task_id is not None:
        try:
            uuid.UUID(str(task_id))
        except ValueError:
            errors.append(f"task_id is not a valid UUID: {task_id!r}")

    # schema_version must be "1".
    if line.get("schema_version") not in (None, "1"):
        errors.append(
            f"schema_version must be '1', got {line.get('schema_version')!r}"
        )

    status = line.get("status")
    if is_terminal:
        if status not in _VALID_TERMINAL_STATUSES:
            errors.append(
                f"terminal status must be one of "
                f"{sorted(_VALID_TERMINAL_STATUSES)}, got {status!r}"
            )
        for field in ("result_file", "summary"):
            if field not in line:
                errors.append(f"terminal line missing required field: {field}")
    else:
        if status not in _VALID_PROGRESS_STATUSES:
            errors.append(
                f"progress status must be one of "
                f"{sorted(_VALID_PROGRESS_STATUSES)}, got {status!r}"
            )
        for field in ("phase", "step"):
            if field not in line:
                errors.append(f"progress line missing required field: {field}")

    return errors


def _append_line(path: Path, line: dict) -> None:
    """Append-only NDJSON write via O_APPEND (Council A-1).

    Uses os.open + os.write so the kernel-level O_APPEND flag is
    explicit — guarantees atomic append even under concurrent writers
    against the same file. Each os.write call against an O_APPEND fd
    seeks to EOF atomically before writing (POSIX guarantee on
    sizes <= PIPE_BUF, which one JSON line easily is).

    The line is JSON-serialized with sort_keys=False (preserves the
    field order the caller built) and a trailing newline.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(line, ensure_ascii=False) + "\n").encode("utf-8")
    # O_WRONLY | O_APPEND | O_CREAT — the canonical append-only open
    # mode. mode=0o644 matches what `open(..., "a")` would create.
    fd = os.open(
        str(path),
        os.O_WRONLY | os.O_APPEND | os.O_CREAT,
        0o644,
    )
    try:
        os.write(fd, payload)
    finally:
        os.close(fd)


def _resolve_task_id(args: argparse.Namespace) -> "str | None":
    """Resolve task_id from --task-id, then QPB_TASK_ID env var.

    Returns None if neither is set. Caller decides whether to no-op
    (Mode A) or error (CLI contract).
    """
    if args.task_id:
        return args.task_id
    return os.environ.get("QPB_TASK_ID") or None


def _resolve_heartbeat_path(args: argparse.Namespace) -> "Path | None":
    """Resolve heartbeat path from --heartbeat-path, then
    QPB_HEARTBEAT_PATH env var. Returns None if neither is set.
    """
    if args.heartbeat_path:
        return Path(args.heartbeat_path)
    env_path = os.environ.get("QPB_HEARTBEAT_PATH")
    if env_path:
        return Path(env_path)
    return None


def _emit_or_terminal(
    args: argparse.Namespace,
    *,
    is_terminal: bool,
) -> int:
    """Shared emit/terminal logic. Returns the process exit code.

    Mode A fallback resolution: if --mode-a-noop is passed AND
    neither task_id nor heartbeat_path is resolvable from any source,
    silently exit 0. If --mode-a-noop is NOT passed and either
    required input is missing, exit 2 with a clear message.

    The two behaviors look superficially conflicting; the resolution
    documented in the QPB worker SKILL.md (Heartbeat emission
    contract section) is:

      - Mode B (harness orchestrating): both env vars are set in the
        worker prompt header; the helper script runs normally.
      - Mode A (interactive, no harness): the worker calls the
        helper with --mode-a-noop. With neither env var set, the
        helper silently no-ops.
      - Misconfiguration (partial input): exit 2, surface the
        diagnostic to operator/log. This catches "harness set
        TASK_ID but forgot HEARTBEAT_PATH" mistakes.
    """
    task_id = _resolve_task_id(args)
    heartbeat_path = _resolve_heartbeat_path(args)

    mode_a_noop = getattr(args, "mode_a_noop", False)

    if mode_a_noop and task_id is None and heartbeat_path is None:
        # Mode A no-op path — neither input source set and the caller
        # explicitly opted into no-op. Silent success.
        return 0

    missing: list[str] = []
    if task_id is None:
        missing.append("--task-id (or QPB_TASK_ID env var)")
    if heartbeat_path is None:
        missing.append("--heartbeat-path (or QPB_HEARTBEAT_PATH env var)")
    if missing:
        print(
            f"qpb_heartbeat: ERROR missing required input(s): "
            f"{', '.join(missing)}",
            file=sys.stderr,
        )
        return 2

    line: dict = {
        "ts": _utc_now_iso(),
        "task_id": task_id,
        "schema_version": "1",
        "status": args.status,
    }
    if is_terminal:
        line["result_file"] = args.result_file
        line["summary"] = args.summary
    else:
        line["phase"] = args.phase
        line["step"] = args.step
        if args.message:
            line["message"] = args.message

    schema = _load_schema()
    errors = _validate_line(line, schema, is_terminal=is_terminal)
    if errors:
        print(
            "qpb_heartbeat: ERROR heartbeat line failed schema "
            "validation; not appending:",
            file=sys.stderr,
        )
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print(
            f"  candidate line: {json.dumps(line, ensure_ascii=False)}",
            file=sys.stderr,
        )
        return 3

    try:
        _append_line(heartbeat_path, line)
    except OSError as exc:
        print(
            f"qpb_heartbeat: ERROR could not append to {heartbeat_path}: "
            f"{exc}",
            file=sys.stderr,
        )
        return 1

    print(f"OK {line['ts']}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qpb_heartbeat",
        description=(
            "QPB heartbeat emit helper — canonical single source of "
            "truth for the v1.5.9 worker-side heartbeat contract."
        ),
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--task-id",
        help="UUID for this job. Defaults to QPB_TASK_ID env var.",
    )
    common.add_argument(
        "--heartbeat-path",
        help=(
            "Path to heartbeat.ndjson (append-only). Defaults to "
            "QPB_HEARTBEAT_PATH env var."
        ),
    )
    common.add_argument(
        "--mode-a-noop",
        action="store_true",
        help=(
            "Mode A interactive fallback: if both --task-id and "
            "--heartbeat-path are unresolvable, exit 0 silently "
            "instead of exit 2. Phase prompts pass this when no "
            "harness is orchestrating."
        ),
    )

    emit = sub.add_parser(
        "emit",
        parents=[common],
        help="Emit a progress heartbeat line.",
    )
    emit.add_argument("--phase", required=True, help="QPB phase name.")
    emit.add_argument("--step", required=True, help="Specific step within the phase.")
    emit.add_argument(
        "--status",
        required=True,
        choices=sorted(_VALID_PROGRESS_STATUSES),
        help="Progress status enum.",
    )
    emit.add_argument(
        "--message",
        default=None,
        help="Optional human-readable detail.",
    )

    terminal = sub.add_parser(
        "terminal",
        parents=[common],
        help="Emit the terminal sentinel line (final line of the file).",
    )
    terminal.add_argument(
        "--status",
        required=True,
        choices=sorted(_VALID_TERMINAL_STATUSES),
        help="Terminal status enum.",
    )
    terminal.add_argument(
        "--result-file",
        required=True,
        help="Path to the worker's terminal artifact.",
    )
    terminal.add_argument(
        "--summary",
        required=True,
        help="One-line outcome.",
    )

    return parser


def main(argv: "list[str] | None" = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        # argparse calls sys.exit(2) on bad args; remap to 64.
        if exc.code not in (0, None):
            return 64
        return 0

    if args.cmd == "emit":
        return _emit_or_terminal(args, is_terminal=False)
    if args.cmd == "terminal":
        return _emit_or_terminal(args, is_terminal=True)

    parser.print_help(sys.stderr)
    return 64


if __name__ == "__main__":
    sys.exit(main())
