"""phase4_inbox.py — Phase 4 Part D.2: Council inbox extension and
triage_batch_key backfill.

Two responsibilities:

1. Build a fresh Phase 4 council inbox file
   (quality/phase3/pass_e_council_inbox.json) listing one item per
   detected divergence (internal-prose, prose-to-code, execution).
   Schema per the brief Part D.2; does NOT mutate Phase 3's
   pass_d_council_inbox.json.

2. Backfill triage_batch_key on Phase 3's
   pass_d_council_inbox.json. Each of its 379 items has section_idx
   and section_heading but no document field. To recover the
   document context, we JOIN on draft_idx against pass_c_formal.jsonl
   (or pass_c_formal_use_cases.jsonl for UCs). source_document=None
   defaults to "SKILL.md". Then triage_batch_key = "{document}::
   {section_idx}". The verification step grep's for the literal
   string "None" in any triage_batch_key value and errors if any are
   found.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class Phase4InboxConfig:
    internal_path: Path  # pass_e_internal_divergences.jsonl
    prose_to_code_path: Path  # pass_e_prose_to_code_divergences.jsonl
    execution_path: Path  # pass_e_execution_divergences.jsonl
    bugs_path: Path  # pass_e_bugs.jsonl (Part D.1 output)
    phase4_inbox_path: Path  # output: pass_e_council_inbox.json
    phase3_inbox_path: Path  # input + backfill target: pass_d_council_inbox.json
    formal_path: Path  # input: pass_c_formal.jsonl (for backfill JOIN)
    formal_use_cases_path: Path  # input: pass_c_formal_use_cases.jsonl


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Phase 4 inbox build.
# ---------------------------------------------------------------------------


def _bug_id_by_divergence_id(bugs: list[dict]) -> dict:
    return {
        b.get("divergence_id"): b.get("bug_id")
        for b in bugs
        if b.get("divergence_id")
    }


def _phase4_item(div: dict, item_type: str, bug_id: Optional[str]) -> dict:
    """Single Phase 4 inbox item per the brief schema."""
    if item_type == "divergence-internal-prose":
        excerpts = [
            div.get("excerpt_a") or "",
            div.get("excerpt_b") or "",
        ]
    elif item_type == "divergence-prose-to-code":
        excerpts = [div.get("excerpt") or ""]
        if div.get("code_artifact"):
            excerpts.append(div["code_artifact"])
    else:  # divergence-execution
        excerpts = [str(div.get("failed_run_ids", []))]
    return {
        "item_type": item_type,
        "divergence_id": div.get("divergence_id"),
        "bug_id": bug_id,
        "auto_disposition": div.get("provisional_disposition"),
        "rationale": div.get("rationale", ""),
        "context_excerpts": [e for e in excerpts if e],
        "council_action_required": True,
        "triage_batch_key": div.get("triage_batch_key"),
    }


def build_phase4_inbox(config: Phase4InboxConfig) -> dict:
    """Build pass_e_council_inbox.json from the three divergence
    JSONL files and the Part D.1 BUG records. Returns summary dict."""
    internals = _read_jsonl(config.internal_path)
    prose_to_codes = _read_jsonl(config.prose_to_code_path)
    executions = _read_jsonl(config.execution_path)
    bugs = _read_jsonl(config.bugs_path)
    bug_by_div = _bug_id_by_divergence_id(bugs)

    items = []
    for div in internals:
        items.append(_phase4_item(
            div, "divergence-internal-prose",
            bug_by_div.get(div.get("divergence_id")),
        ))
    for div in prose_to_codes:
        items.append(_phase4_item(
            div, "divergence-prose-to-code",
            bug_by_div.get(div.get("divergence_id")),
        ))
    for div in executions:
        items.append(_phase4_item(
            div, "divergence-execution",
            bug_by_div.get(div.get("divergence_id")),
        ))

    payload = {
        "schema_version": "1.0",
        "generated_at": _utc_now_iso(),
        "phase": "4",
        "phase_3_inbox_ref": "pass_d_council_inbox.json",
        "items": items,
    }
    _atomic_write_json(config.phase4_inbox_path, payload)
    return {
        "phase4_inbox_items": len(items),
        "internal_items": len(internals),
        "prose_to_code_items": len(prose_to_codes),
        "execution_items": len(executions),
    }


# ---------------------------------------------------------------------------
# Phase 3 inbox triage_batch_key backfill.
# ---------------------------------------------------------------------------


class TriageBatchKeyVerificationError(RuntimeError):
    """Raised when the post-backfill grep finds a literal 'None' in
    any triage_batch_key value."""


def backfill_triage_batch_key(config: Phase4InboxConfig) -> dict:
    """Backfill triage_batch_key on Phase 3's pass_d_council_inbox.json.

    Per the brief Part D.2:
      1. For each inbox item, read draft_idx.
      2. Look up the corresponding record in pass_c_formal.jsonl
         (REQ items) or pass_c_formal_use_cases.jsonl (UC items by
         uc_draft_idx).
      3. Read source_document from the formal record. If None or
         missing, default to "SKILL.md".
      4. Compute triage_batch_key = "{source_document}::{section_idx}".
      5. Atomic write back to pass_d_council_inbox.json.
      6. Verification: grep the file for "None" in any
         triage_batch_key value. If any are found, raise
         TriageBatchKeyVerificationError.
    """
    if not config.phase3_inbox_path.is_file():
        return {"backfilled": 0, "skipped_no_inbox": True}
    inbox = json.loads(config.phase3_inbox_path.read_text(encoding="utf-8"))
    if not isinstance(inbox, dict):
        raise TriageBatchKeyVerificationError(
            f"{config.phase3_inbox_path} is not a JSON object"
        )

    # Build draft_idx -> source_document index from Pass C formal REQs.
    formal = _read_jsonl(config.formal_path)
    draft_idx_to_doc: dict = {}
    for rec in formal:
        di = rec.get("draft_idx")
        if di is None:
            continue
        sd = rec.get("source_document")
        if sd is None or not isinstance(sd, str) or not sd.strip():
            sd = "SKILL.md"
        draft_idx_to_doc[di] = sd

    # UC records partition under SKILL.md (no source_document field).
    ucs = _read_jsonl(config.formal_use_cases_path)
    uc_draft_idx_to_doc: dict = {}
    for uc in ucs:
        udi = uc.get("uc_draft_idx")
        if udi is not None:
            uc_draft_idx_to_doc[udi] = "SKILL.md"

    items = inbox.get("items", []) or []
    backfilled = 0
    for item in items:
        if not isinstance(item, dict):
            continue
        section_idx = item.get("section_idx")
        item_type = item.get("item_type")
        draft_idx = item.get("draft_idx")
        if item_type == "weak-rationale":
            # UC items: lookup via uc_draft_idx (the inbox's
            # draft_idx field is the uc_draft_idx for UC items per
            # Phase 3d pass_d.py:_build_council_inbox).
            document = uc_draft_idx_to_doc.get(draft_idx, "SKILL.md")
        else:
            document = draft_idx_to_doc.get(draft_idx, "SKILL.md")
        # Section_idx may be None (zero-req-section items always
        # have section_idx); use a string-safe fallback.
        section_part = (
            str(section_idx) if section_idx is not None else "unknown"
        )
        item["triage_batch_key"] = f"{document}::{section_part}"
        backfilled += 1

    _atomic_write_json(config.phase3_inbox_path, inbox)

    # Verification step (mandatory per brief): grep for literal
    # "None" in triage_batch_key values.
    raw = config.phase3_inbox_path.read_text(encoding="utf-8")
    bad_lines = []
    for line in raw.splitlines():
        if '"triage_batch_key"' in line and "None" in line:
            bad_lines.append(line.strip())
    if bad_lines:
        raise TriageBatchKeyVerificationError(
            "Post-backfill verification failed: triage_batch_key "
            "contains literal 'None' in the following lines:\n"
            + "\n".join(bad_lines)
        )

    return {"backfilled": backfilled}


# v1.5.7 089x: every bin/*.py is safe + self-describing on no-args.
if __name__ == "__main__":
    try:
        from bin._purpose import print_purpose as _print_purpose
    except ImportError:
        from _purpose import print_purpose as _print_purpose  # type: ignore[no-redef]
    _print_purpose(
        name='skill_derivation.phase4_inbox',
        summary=(
            "Phase 4 inbox helpers for the skill-derivation pipeline — "
            "queue + dispatch glue between passes. "
        ),
        role=(
            "Imported by skill_derivation passes that hand off candidates "
            "to Phase 4 verification. "
        ),
        kind="library",
    )
    import sys as _sys
    _sys.exit(0)
