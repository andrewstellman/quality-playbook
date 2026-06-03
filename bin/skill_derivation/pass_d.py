"""pass_d.py — Pass D driver (coverage audit + council inbox).

Reads pass_a_drafts.jsonl (and optionally pass_a_use_case_drafts.jsonl)
plus pass_c_formal.jsonl (and optionally pass_c_formal_use_cases.jsonl);
emits:

  - pass_d_audit.json              Consolidated {promoted, rejected,
                                   demoted_to_tier_5} per-draft
                                   classification with rationale.
  - pass_d_section_coverage.json   Per-section accounting: drafts
                                   produced, drafts promoted, pending
                                   council review. Operational
                                   sections (NOT in the meta allowlist)
                                   with zero promoted REQs flagged
                                   as completeness gaps.
  - pass_d_council_inbox.json      Items needing human adjudication
                                   per the DQ-5 schema (rejected
                                   drafts, tier-5 demotions,
                                   zero-req-section flags, council
                                   reviews from Pass C).
  - pass_d_progress.json           Cursor + status.

B4 upstream-status gate: refuses to start unless Pass C is complete.
Pass D does NOT need to verify Pass A; that's transitively
guaranteed via Pass B -> Pass C.

If rejection rate > 30% the audit output includes a
phase4_council_flag entry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from bin.skill_derivation import protocol


REJECTION_RATE_FLAG_THRESHOLD = 0.30

VALID_COUNCIL_INBOX_ITEM_TYPES = frozenset({
    "rejected-draft",
    "tier-5-demotion",
    "zero-req-section",
    "weak-rationale",
})


@dataclass
class PassDConfig:
    drafts_path: Path  # input: pass_a_drafts.jsonl
    uc_drafts_path: Optional[Path]  # input: pass_a_use_case_drafts.jsonl
    formal_path: Path  # input: pass_c_formal.jsonl
    formal_use_cases_path: Optional[Path]  # input: pass_c_formal_use_cases.jsonl
    sections_path: Path  # input: pass_a_sections.json (for section_kind)
    audit_path: Path  # output: pass_d_audit.json
    section_coverage_path: Path  # output: pass_d_section_coverage.json
    council_inbox_path: Path  # output: pass_d_council_inbox.json
    progress_path: Path  # output: pass_d_progress.json
    pass_c_progress_path: Path  # input: upstream-status check


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_jsonl(path: Optional[Path]) -> list[dict]:
    if path is None or not path.is_file():
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


def _read_sections(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("sections", [])


def _classify_drafts(
    pass_a_drafts: list[dict],
    pass_c_formal: list[dict],
) -> tuple[list[dict], list[dict], list[dict]]:
    """Cross-reference Pass A drafts against Pass C formal records.
    Returns (promoted, rejected, demoted_to_tier_5).

    A Pass A draft is `promoted` if a Pass C record exists with the
    same `draft_idx` AND disposition='accepted'. It's `demoted` if
    Pass C disposition is 'demoted-tier-5'. It's `rejected` if Pass
    C disposition is 'needs-council-review' OR if the draft has no
    Pass C counterpart at all (Pass C decided not to emit a record
    for it -- shouldn't happen in normal flow, but Pass D records
    the case).
    """
    formal_by_draft_idx = {
        rec.get("draft_idx"): rec
        for rec in pass_c_formal
        if rec.get("draft_idx") is not None
    }

    promoted: list[dict] = []
    rejected: list[dict] = []
    demoted: list[dict] = []

    for draft in pass_a_drafts:
        if "draft_idx" not in draft:
            continue  # skip / no_reqs accounting markers
        idx = draft["draft_idx"]
        formal = formal_by_draft_idx.get(idx)
        if formal is None:
            rejected.append({
                "draft_idx": idx,
                "section_idx": draft.get("section_idx"),
                "title": draft.get("title", ""),
                "rationale": (
                    "No Pass C record was produced for this draft; "
                    "Pass A overreach not picked up by Pass B / C."
                ),
            })
            continue
        disposition = formal.get("disposition")
        if disposition == "accepted":
            promoted.append({
                "draft_idx": idx,
                "section_idx": draft.get("section_idx"),
                "req_id": formal["id"],
                "tier": formal["tier"],
            })
        elif disposition == "demoted-tier-5":
            demoted.append({
                "draft_idx": idx,
                "section_idx": draft.get("section_idx"),
                "req_id": formal["id"],
                "rationale": formal.get(
                    "council_review_rationale",
                    "Behavioral claim demoted to Tier 5.",
                ),
            })
        elif disposition == "needs-council-review":
            rejected.append({
                "draft_idx": idx,
                "section_idx": draft.get("section_idx"),
                "title": draft.get("title", ""),
                "req_id": formal["id"],
                "rationale": formal.get(
                    "council_review_rationale",
                    "Pass C flagged for council review.",
                ),
            })
        else:
            rejected.append({
                "draft_idx": idx,
                "section_idx": draft.get("section_idx"),
                "title": draft.get("title", ""),
                "rationale": (
                    f"Pass C produced disposition {disposition!r} -- "
                    "not in the recognized {accepted, demoted-tier-5, "
                    "needs-council-review} set"
                ),
            })

    return promoted, rejected, demoted


def _build_section_coverage(
    sections_data: list[dict],
    pass_a_drafts: list[dict],
    promoted_set: set[int],
) -> dict:
    """Per-section accounting + completeness-gap flags."""
    drafts_by_section: dict[int, list[dict]] = {}
    skip_markers_by_section: dict[int, dict] = {}
    for d in pass_a_drafts:
        section_idx = d.get("section_idx")
        if section_idx is None:
            continue
        if d.get("skipped") or d.get("no_reqs"):
            skip_markers_by_section[section_idx] = d
            continue
        drafts_by_section.setdefault(section_idx, []).append(d)

    sections_report: list[dict] = []
    completeness_gaps: list[dict] = []
    for section in sections_data:
        section_idx = section["section_idx"]
        section_kind = section.get("section_kind", "operational")
        drafts = drafts_by_section.get(section_idx, [])
        marker = skip_markers_by_section.get(section_idx)
        promoted_in_section = sum(
            1 for d in drafts if d.get("draft_idx") in promoted_set
        )
        report = {
            "section_idx": section_idx,
            "document": section["document"],
            "heading": section["heading"],
            "section_kind": section_kind,
            "skip_reason": section.get("skip_reason"),
            "drafts_total": len(drafts),
            "drafts_promoted": promoted_in_section,
            "drafts_pending_council": len(drafts) - promoted_in_section,
            "marker": marker,
        }
        sections_report.append(report)
        # Completeness-gap flagging: operational section, ZERO drafts
        # produced (not just zero promoted), and no skip-rationale.
        # A section that produced drafts that all got rejected /
        # demoted is visible in this per-section report but is NOT a
        # completeness gap -- the section WAS visited and DID produce
        # something. The gap signal is for sections the LLM silently
        # under-produced on (no drafts at all from a real
        # operational section).
        if (
            section_kind == "operational"
            and len(drafts) == 0
            and marker is None
        ):
            completeness_gaps.append({
                "section_idx": section_idx,
                "document": section["document"],
                "heading": section["heading"],
            })

    return {
        "schema_version": "1.0",
        "generated_at": _utc_now_iso(),
        "sections": sections_report,
        "completeness_gaps": completeness_gaps,
    }


def _build_council_inbox(
    rejected: list[dict],
    demoted: list[dict],
    completeness_gaps: list[dict],
    sections_data: list[dict],
    pass_a_drafts: list[dict],
    pass_c_formal_ucs: list[dict],
) -> dict:
    """DQ-5 council inbox shape."""
    sections_by_idx = {s["section_idx"]: s for s in sections_data}
    drafts_by_idx = {d.get("draft_idx"): d for d in pass_a_drafts}

    items: list[dict] = []

    for entry in rejected:
        draft = drafts_by_idx.get(entry.get("draft_idx"), {})
        section = sections_by_idx.get(entry.get("section_idx"), {})
        items.append({
            "item_type": "rejected-draft",
            "draft_idx": entry.get("draft_idx"),
            "section_idx": entry.get("section_idx"),
            "section_heading": section.get("heading"),
            "rationale": entry.get("rationale", ""),
            "context_excerpt": draft.get("acceptance_criteria", "")[:200],
            "provisional_disposition": "needs-council-review",
        })

    for entry in demoted:
        draft = drafts_by_idx.get(entry.get("draft_idx"), {})
        section = sections_by_idx.get(entry.get("section_idx"), {})
        items.append({
            "item_type": "tier-5-demotion",
            "draft_idx": entry.get("draft_idx"),
            "section_idx": entry.get("section_idx"),
            "section_heading": section.get("heading"),
            "rationale": entry.get("rationale", ""),
            "context_excerpt": draft.get("acceptance_criteria", "")[:200],
            "provisional_disposition": "demoted-tier-5",
        })

    for gap in completeness_gaps:
        items.append({
            "item_type": "zero-req-section",
            "draft_idx": None,
            "section_idx": gap["section_idx"],
            "section_heading": gap["heading"],
            "rationale": (
                f"Operational section {gap['heading']!r} produced no "
                "promoted REQs and was not marked as skipped. Council "
                "should review whether the section was correctly "
                "iterated and whether the LLM under-produced."
            ),
            "context_excerpt": "",
            "provisional_disposition": "needs-council-review",
        })

    # UCs: every formal UC carries needs_council_review=True.
    for uc in pass_c_formal_ucs:
        section_idx = uc.get("section_idx")
        section = sections_by_idx.get(section_idx, {})
        items.append({
            "item_type": "weak-rationale",
            "draft_idx": uc.get("uc_draft_idx"),
            "section_idx": section_idx,
            "section_heading": section.get("heading"),
            "rationale": (
                f"UC {uc.get('uc_id')} requires Council review (UCs "
                "are not mechanically cited; verification path is "
                "Council)."
            ),
            "context_excerpt": uc.get("title", "")[:200],
            "provisional_disposition": "needs-council-review",
        })

    return {
        "schema_version": "1.0",
        "generated_at": _utc_now_iso(),
        "items": items,
    }


def run_pass_d(config: PassDConfig, *, resume: bool = True) -> dict:
    """Drive Pass D end-to-end. Returns a dict with summary counts."""
    protocol.require_upstream_complete(
        config.pass_c_progress_path, downstream_pass_name="Pass D"
    )

    state = protocol.ProgressState(
        pass_="D",
        unit="audit-entry",
        cursor=0,
        total=None,
        status="running",
        last_updated=_utc_now_iso(),
    )
    protocol.write_progress_atomic(config.progress_path, state)

    pass_a_drafts = _read_jsonl(config.drafts_path)
    pass_c_formal = _read_jsonl(config.formal_path)
    pass_c_formal_ucs = _read_jsonl(config.formal_use_cases_path)
    sections_data = _read_sections(config.sections_path)

    promoted, rejected, demoted = _classify_drafts(pass_a_drafts, pass_c_formal)
    promoted_set = {p["draft_idx"] for p in promoted}

    section_coverage = _build_section_coverage(
        sections_data, pass_a_drafts, promoted_set
    )
    council_inbox = _build_council_inbox(
        rejected, demoted, section_coverage["completeness_gaps"],
        sections_data, pass_a_drafts, pass_c_formal_ucs,
    )

    total_decisions = len(promoted) + len(rejected) + len(demoted)
    rejection_rate = (
        (len(rejected) + len(demoted)) / total_decisions
        if total_decisions
        else 0.0
    )
    phase4_flag = rejection_rate > REJECTION_RATE_FLAG_THRESHOLD

    audit_payload = {
        "schema_version": "1.0",
        "generated_at": _utc_now_iso(),
        "promoted": promoted,
        "rejected": rejected,
        "demoted_to_tier_5": demoted,
        "rejection_rate": rejection_rate,
        "rejection_rate_threshold": REJECTION_RATE_FLAG_THRESHOLD,
        "phase4_council_flag": phase4_flag,
    }

    _write_json_atomic(config.audit_path, audit_payload)
    _write_json_atomic(config.section_coverage_path, section_coverage)
    _write_json_atomic(config.council_inbox_path, council_inbox)

    state = protocol.ProgressState(
        pass_="D",
        unit="audit-entry",
        cursor=total_decisions,
        total=total_decisions,
        status="complete",
        last_updated=_utc_now_iso(),
    )
    protocol.write_progress_atomic(config.progress_path, state)

    return {
        "promoted_count": len(promoted),
        "rejected_count": len(rejected),
        "demoted_count": len(demoted),
        "rejection_rate": rejection_rate,
        "phase4_council_flag": phase4_flag,
        "completeness_gap_count": len(section_coverage["completeness_gaps"]),
        "council_inbox_items": len(council_inbox["items"]),
    }


def _write_json_atomic(path: Path, payload: dict) -> None:
    import os
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


# v1.5.7 089x: every bin/*.py is safe + self-describing on no-args.
if __name__ == "__main__":
    try:
        from bin._purpose import print_purpose as _print_purpose
    except ImportError:
        from _purpose import print_purpose as _print_purpose  # type: ignore[no-redef]
    _print_purpose(
        name='skill_derivation.pass_d',
        summary=(
            "Skill-derivation pass D — divergence-to-bug-candidate "
            "conversion (final stage). "
        ),
        role=(
            "Entry point for the skill-derivation `pass_d` stage; called "
            "by the skill-derivation orchestrator. "
        ),
        kind="library",
    )
    import sys as _sys
    _sys.exit(0)
