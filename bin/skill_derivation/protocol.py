"""protocol.py — Per-Pass Execution Protocol primitives for Phase 3.

Implements the "disk is the source of truth" contract documented in
`docs/design/QPB_v1.5.3_Implementation_Plan.md` Phase 3 "Per-Pass
Execution Protocol":

  - Atomic progress-file writes (tmp + os.replace)
  - JSONL append-only artifacts
  - Cursor advances ONLY after the per-unit JSONL record is on disk
  - Recovery on resume: read progress, read last JSONL record, verify
    last_record.idx + 1 == cursor, roll cursor back on discrepancy
  - Recovery preamble template (LLM-prompt-time)

Stdlib-only. The mechanics here are correctness-critical for
long-running passes that survive auto-compaction and process kills.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

# The mandatory recovery preamble that goes at the top of every
# LLM-driven pass prompt. The {pass_spec_path} placeholder is filled
# at prompt-render time with the absolute path to the per-pass spec
# document (so a compacted-context LLM can re-read the spec rather
# than reconstructing it from a summary).
RECOVERY_PREAMBLE_TEMPLATE = """\
If this session has experienced auto-compaction -- you will see a
conversation summary where recent tool-call history should be, or a
continuation banner -- do this before continuing:

1. Re-read the pass specification at {pass_spec_path}. Do not try to
   reconstruct it from the compacted summary.
2. Read the pass's progress file ({progress_file_path}).
3. Read the last record of the pass's JSONL artifact and confirm its
   idx equals (cursor - 1). If not, roll the cursor back to match
   disk state and note the discrepancy in progress.notes.
4. Resume the per-unit workflow from the cursor.

Disk is the source of truth. The conversation is not.
"""


@dataclass
class ProgressState:
    """Mirrors the JSON shape documented in the Implementation Plan.

    Field names match the Plan's literal JSON keys so callers can
    serialize via dataclasses.asdict() without translation.
    """

    pass_: str  # pass_a / pass_b / pass_c / pass_d (renamed to avoid `pass` keyword)
    unit: str   # "section" / "draft" / "citation" / "audit-entry"
    cursor: int  # idx of the next unprocessed unit (0-based)
    total: Optional[int]  # filled once total is known; None until enumeration completes
    status: str  # "running" / "paused" / "complete" / "blocked"
    last_updated: str  # ISO-8601 UTC
    notes: str = ""

    def to_json_dict(self) -> dict:
        out = asdict(self)
        # Plan's JSON key is "pass" (a Python keyword), not "pass_".
        out["pass"] = out.pop("pass_")
        return out

    @classmethod
    def from_json_dict(cls, data: dict) -> "ProgressState":
        if "pass" in data:
            data = dict(data)
            data["pass_"] = data.pop("pass")
        return cls(**data)


def write_progress_atomic(progress_path: Path, state: ProgressState) -> None:
    """Atomic tmp + os.replace write so the file is never half-written.

    The Implementation Plan's correctness invariant: progress is never
    observed in a partial state by a concurrent reader (or by the
    pass's own restart logic if a crash interrupts the write itself).
    """
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = progress_path.with_name(progress_path.name + ".tmp")
    payload = json.dumps(state.to_json_dict(), indent=2, sort_keys=False) + "\n"
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, progress_path)


def read_progress(progress_path: Path) -> Optional[ProgressState]:
    """Return parsed ProgressState, or None if the file is absent/empty.

    Absent file means the pass has not started yet -- callers
    initialize via write_progress_atomic with cursor=0.
    """
    if not progress_path.is_file():
        return None
    raw = progress_path.read_text(encoding="utf-8")
    if not raw.strip():
        return None
    return ProgressState.from_json_dict(json.loads(raw))


def append_jsonl(jsonl_path: Path, record: dict) -> None:
    """Append a single record to a JSONL artifact.

    Append-only by design -- existing records are never rewritten.
    The Plan's recovery protocol relies on this invariant: when the
    progress cursor is ahead of the JSONL's last idx, the cursor is
    rolled back to disk state, NOT the JSONL extended with synthetic
    records.

    Each record is serialized as a single line with a trailing \\n.
    No surrounding pretty-printing -- the JSONL convention is one
    JSON value per line.
    """
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, sort_keys=False) + "\n"
    with jsonl_path.open("a", encoding="utf-8") as fh:
        fh.write(line)


def read_last_jsonl_record(jsonl_path: Path) -> Optional[dict]:
    """Return the last complete JSONL record, or None if file is absent/empty.

    If the file exists but the last line is partial (no trailing
    newline -- typical sign of a crash mid-write), truncates the file
    to the last complete line BEFORE returning the parsed record. The
    truncation is the protocol's "JSONL is append-only and never
    rewound" invariant -- a partial last line was never a complete
    record, so trimming it doesn't violate the invariant.
    """
    if not jsonl_path.is_file():
        return None
    raw = jsonl_path.read_text(encoding="utf-8")
    if not raw:
        return None
    # If the file does NOT end with a newline, the last line is
    # partial. Truncate it.
    if not raw.endswith("\n"):
        last_newline = raw.rfind("\n")
        if last_newline == -1:
            # No complete records at all; truncate to empty.
            jsonl_path.write_text("", encoding="utf-8")
            return None
        truncated = raw[: last_newline + 1]
        jsonl_path.write_text(truncated, encoding="utf-8")
        raw = truncated
    lines = [line for line in raw.splitlines() if line.strip()]
    if not lines:
        return None
    return json.loads(lines[-1])


def count_jsonl_records(jsonl_path: Path) -> int:
    """Return the number of complete JSONL records in the file."""
    if not jsonl_path.is_file():
        return 0
    raw = jsonl_path.read_text(encoding="utf-8")
    if not raw:
        return 0
    if not raw.endswith("\n"):
        last_newline = raw.rfind("\n")
        if last_newline == -1:
            return 0
        raw = raw[: last_newline + 1]
    return sum(1 for line in raw.splitlines() if line.strip())


def verify_and_resume(
    jsonl_path: Path,
    progress_path: Path,
    *,
    idx_field: str,
) -> int:
    """Verify-and-roll-back step from the Per-Pass Execution Protocol.

    Returns the cursor position to resume from. Implements the Plan's
    rule: "Restarting a pass reads the progress file, reads the last
    record in the corresponding JSONL (verifying it matches cursor -
    1), rolls the cursor back to match disk state on any discrepancy,
    and resumes."

    idx_field is the per-record key holding the unit index
    ("section_idx" for Pass A, "draft_idx" for Pass B/C/D).

    If progress is absent: return 0 (start fresh).
    If JSONL is empty: return 0 (start fresh, regardless of progress
        cursor -- progress is presumed stale).
    Otherwise:
        - Read last JSONL record's idx_field value.
        - If progress.cursor == last_idx + 1: agreement, return cursor.
        - Else (progress is ahead OR behind disk): rewrite progress
          cursor to last_idx + 1, log the discrepancy in
          progress.notes, return last_idx + 1.
    """
    state = read_progress(progress_path)
    last_record = read_last_jsonl_record(jsonl_path)

    if last_record is None:
        return 0

    last_idx = last_record.get(idx_field)
    if not isinstance(last_idx, int):
        # Malformed last record -- treat as empty disk and start fresh.
        return 0

    expected_cursor = last_idx + 1

    if state is None:
        # JSONL has data but progress is missing. Initialize progress
        # at the disk-derived cursor so downstream calls see a coherent
        # state.
        return expected_cursor

    if state.cursor != expected_cursor:
        # Discrepancy -- roll cursor back (or forward) to disk state.
        new_state = ProgressState(
            pass_=state.pass_,
            unit=state.unit,
            cursor=expected_cursor,
            total=state.total,
            status="running",
            last_updated=state.last_updated,
            notes=(
                state.notes + f"; verify-and-roll-back: cursor {state.cursor} "
                f"-> {expected_cursor} per disk state"
            ).strip("; "),
        )
        write_progress_atomic(progress_path, new_state)
        return expected_cursor

    return state.cursor


def render_recovery_preamble(*, pass_spec_path: Path, progress_file_path: Path) -> str:
    """Render the recovery preamble for inclusion at the top of an LLM prompt."""
    return RECOVERY_PREAMBLE_TEMPLATE.format(
        pass_spec_path=str(pass_spec_path),
        progress_file_path=str(progress_file_path),
    )


class UpstreamIncompleteError(RuntimeError):
    """Raised by require_upstream_complete when an upstream pass has
    not reached status="complete".

    Round 3 Council B4: every downstream pass MUST verify its upstream
    pass is complete before consuming the upstream artifact, per the
    Implementation Plan's "downstream refuses to start unless upstream
    is complete" gate (Plan line 202). Without this check, a Pass A
    crash that leaves status="running" would silently allow Pass B to
    consume an incomplete pass_a_drafts.jsonl, propagating coverage
    gaps into the formal REQ pipeline.
    """


def require_upstream_complete(
    upstream_progress_path: Path, *, downstream_pass_name: str
) -> None:
    """Raise UpstreamIncompleteError unless the upstream progress file
    exists AND reports status="complete".

    Round 3 Council B4 fix (Implementation Plan line 202): the
    "downstream refuses to start unless upstream is complete" gate
    is method-enforced rather than caller-convention. Three failure
    cases produce a clear diagnostic:

      1. Upstream progress file does not exist -- upstream pass has
         never been run.
      2. Upstream progress file exists but has status="running" or
         "blocked" or "paused" -- upstream crashed or was killed
         mid-pass and never finalized.
      3. Upstream progress file exists but is malformed (cannot be
         parsed) -- treated as not-complete; the maintainer should
         repair the file or re-run upstream from scratch.

    `downstream_pass_name` is included in the error message so the
    diagnostic names which pass refused to start (e.g., "Pass B
    refused to start").
    """
    state = read_progress(upstream_progress_path)
    if state is None:
        raise UpstreamIncompleteError(
            f"{downstream_pass_name} refused to start: upstream progress "
            f"file at {upstream_progress_path} does not exist or is empty. "
            f"Run the upstream pass to completion before starting "
            f"{downstream_pass_name}."
        )
    if state.status != "complete":
        raise UpstreamIncompleteError(
            f"{downstream_pass_name} refused to start: upstream progress "
            f"at {upstream_progress_path} reports status={state.status!r} "
            f"(cursor={state.cursor}, total={state.total}). The upstream "
            f"pass must reach status='complete' before downstream may "
            f"consume its artifact. Resume or re-run the upstream pass "
            f"first."
        )


# v1.5.7 089x: every bin/*.py is safe + self-describing on no-args.
if __name__ == "__main__":
    try:
        from bin._purpose import print_purpose as _print_purpose
    except ImportError:
        from _purpose import print_purpose as _print_purpose  # type: ignore[no-redef]
    _print_purpose(
        name='skill_derivation.protocol',
        summary=(
            "Skill-derivation protocol constants + pass-handoff schemas. "
        ),
        role=(
            "Imported by every skill_derivation pass; defines the data "
            "shapes the passes exchange. "
        ),
        kind="library",
    )
    import sys as _sys
    _sys.exit(0)
