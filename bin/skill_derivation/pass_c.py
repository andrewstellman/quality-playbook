"""pass_c.py — Pass C driver (formal REQ + UC production).

Reads pass_b_citations.jsonl and pass_a_use_case_drafts.jsonl;
produces formal REQ records in pass_c_formal.jsonl and formal UC
records in pass_c_formal_use_cases.jsonl with the v1.5.3 schema
extensions populated.

Disposition table (lifted verbatim from the Phase 3b brief Part B.1
and the original Phase 3 brief Part D.1; six branches must NOT be
collapsed to fewer):

| Pass B citation_status | Source document | Tier | source_type | skill_section | disposition |
|---|---|---|---|---|---|
| verified | SKILL.md | 1 | skill-section | <heading> | accepted |
| verified | reference file | 2 | reference-file | null | accepted |
| unverified | structural ref to SKILL.md | (provisional 1) | skill-section (provisional) | <heading> (provisional) | needs-council-review |
| unverified | structural ref to reference file | (provisional 2) | reference-file | null | needs-council-review |
| unverified | behavioral, project type Hybrid | 5 | code-derived | null | demoted-tier-5 |
| unverified | behavioral, project type Skill | (no Tier 5) | skill-section (best-guess) | <heading> | needs-council-review |

Critical invariants:
  1. Every Pass C record populates source_type (Round 3 process gap).
  2. execution-observation is reserved for Phase 4 -- MUST NOT
     appear in any Pass C record.
  3. skill_section is non-empty when source_type == "skill-section";
     null otherwise (schemas.md invariant #21). Round 5 ND-2: a
     Pass A draft with neither section_heading nor parseable
     proposed_source_ref would otherwise produce an invariant-
     violating record; the guard in _build_formal_req re-routes such
     a record to council-review with a provisional skill_section
     placeholder so the manifest validator does not FAIL.

UCs do NOT get mechanical citations (Phase 3b decision); they pass
through Pass B with citation_status="skipped" and Pass C produces
formal UC records with auto-generated UC-PHASE3-NN IDs and no
citation block. Every UC carries needs_council_review: true.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from bin import role_map as role_map_lib
from bin.skill_derivation import protocol


VALID_SOURCE_TYPES = frozenset(
    {"code-derived", "skill-section", "reference-file"}
)
RESERVED_SOURCE_TYPES = frozenset({"execution-observation"})


@dataclass
class PassCConfig:
    citations_path: Path  # input: pass_b_citations.jsonl
    uc_drafts_path: Optional[Path]  # input: pass_a_use_case_drafts.jsonl
    formal_path: Path  # output: pass_c_formal.jsonl
    formal_use_cases_path: Path  # output: pass_c_formal_use_cases.jsonl
    progress_path: Path  # output: pass_c_progress.json
    pass_b_progress_path: Path  # input: upstream-status check
    role_map_path: Path  # input: quality/exploration_role_map.json (v1.5.4)
    starting_req_idx: int = 1  # REQ-PHASE3-001 ...
    starting_uc_idx: int = 1   # UC-PHASE3-01 ...


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_project_type(role_map_path: Path) -> str:
    """Return the v1.5.3-equivalent project type string ("Code" / "Skill"
    / "Hybrid") derived from the v1.5.4 role map at ``role_map_path``.

    The v1.5.4 redesign replaced the standalone Code/Skill/Hybrid
    classifier with file-by-file role tagging during Phase 1. Pass C's
    six-row disposition table still needs the legacy label internally
    (Branch 5 demotes a behavioral claim to Tier 5 ``code-derived`` only
    when the project has code authority; Branch 6 routes to council
    review when it does not). The mapping lives in
    :func:`bin.role_map.derive_legacy_project_type`.

    Raises FileNotFoundError when the role map is absent — Phase 1 must
    run before Pass C.
    """
    if not role_map_path.is_file():
        raise FileNotFoundError(
            f"Phase 1 role map not found at {role_map_path}; Phase 1 "
            "exploration must produce quality/exploration_role_map.json "
            "before Pass C runs"
        )
    role_map = role_map_lib.load_role_map(role_map_path)
    if role_map is None:
        raise FileNotFoundError(
            f"Phase 1 role map at {role_map_path} could not be parsed as "
            "JSON; rerun Phase 1 to regenerate it"
        )
    return role_map_lib.derive_legacy_project_type(role_map)


def _read_citations(path: Path) -> list[dict]:
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


def _is_skill_md_doc(document: Optional[str]) -> bool:
    return document == "SKILL.md"


def _is_reference_doc(document: Optional[str]) -> bool:
    return isinstance(document, str) and document.startswith("references/")


def _is_behavioral_claim(record: dict) -> bool:
    """Heuristic: behavioral claims have no proposed_source_ref AND
    no cross_references and no source_document. In practice Pass A
    always produces some proposed_source_ref pointing at the section
    that produced the draft, so the heuristic distinguishes between
    'structural reference to a documented section' (proposed_source_ref
    points at a section heading the search step couldn't match
    verbatim) vs 'no documented anchor at all' (the draft was
    inferred from operational behavior with no doc to point at).

    Phase 3b's pragmatic rule: a draft is structural when its
    proposed_source_ref refers to a section/file that exists in the
    iteration set; otherwise it's behavioral. This is approximated
    by: structural iff source_document is set in Pass B (search
    found a candidate location) OR proposed_source_ref names an
    actual document. Since Pass B sets source_document only on
    matches above the similarity threshold, an unverified record
    with source_document set is structural-near-miss; without it,
    behavioral.
    """
    if record.get("source_document"):
        return False  # structural -- search hit a candidate location
    if "proposed_source_ref" in record and record["proposed_source_ref"]:
        # Heuristic: proposed_source_ref pointing at a known heading
        # is structural. A bare phrase like "Phase 1 section" is
        # also structural (the LLM proposed a real anchor that just
        # didn't survive citation match).
        return False
    return True


def _next_req_id(idx: int) -> str:
    return f"REQ-PHASE3-{idx:03d}"


def _next_uc_id(idx: int) -> str:
    return f"UC-PHASE3-{idx:02d}"


def _build_formal_req(
    record: dict,
    *,
    req_idx: int,
    project_type: str,
    section_heading: Optional[str],
) -> dict:
    """Apply the 6-branch disposition table from the brief Part B.1."""
    citation_status = record.get("citation_status")
    source_document = record.get("source_document")
    citation_excerpt = record.get("citation_excerpt")

    formal: dict = {
        "id": _next_req_id(req_idx),
        "title": record.get("title", ""),
        "description": record.get("description", ""),
        "acceptance_criteria": record.get("acceptance_criteria", ""),
        "section_idx": record.get("section_idx"),
        "draft_idx": record.get("draft_idx"),
    }
    # Preserve cross_references from Pass A if set (Phase 3b A.3).
    if record.get("cross_references"):
        formal["cross_references"] = record["cross_references"]

    if citation_status == "verified":
        # Branch 1 or 2: source determines tier and source_type.
        if _is_skill_md_doc(source_document):
            formal["tier"] = 1
            formal["source_type"] = "skill-section"
            formal["skill_section"] = section_heading
            formal["disposition"] = "accepted"
        elif _is_reference_doc(source_document):
            formal["tier"] = 2
            formal["source_type"] = "reference-file"
            formal["skill_section"] = None
            formal["disposition"] = "accepted"
        else:
            # Search returned a hit but document isn't classifiable;
            # route to council-review with provisional skill-section.
            formal["tier"] = 1
            formal["source_type"] = "skill-section"
            formal["skill_section"] = section_heading
            formal["disposition"] = "needs-council-review"
            formal["council_review_rationale"] = (
                f"Pass B verified citation in document "
                f"{source_document!r} which is neither SKILL.md nor a "
                "references/*.md file; provisional Tier 1 / skill-section."
            )
        formal["citation_excerpt"] = citation_excerpt
        formal["source_document"] = source_document
    else:
        # Unverified branches.
        if _is_behavioral_claim(record):
            if project_type == "Hybrid":
                # Branch 5: behavioral + Hybrid -> Tier 5 with code-derived.
                formal["tier"] = 5
                formal["source_type"] = "code-derived"
                formal["skill_section"] = None
                formal["disposition"] = "demoted-tier-5"
                formal["council_review_rationale"] = (
                    "Behavioral claim with no documented anchor; demoted "
                    "to Tier 5 per project_type=Hybrid."
                )
            else:
                # Branch 6: behavioral + Skill -> council-review with
                # provisional skill-section (no Tier 5; pure Skill has no
                # code authority).
                formal["tier"] = None  # provisional; Council assigns
                formal["source_type"] = "skill-section"
                formal["skill_section"] = section_heading
                formal["disposition"] = "needs-council-review"
                formal["council_review_rationale"] = (
                    "Behavioral claim with no documented anchor on a "
                    "pure-Skill project; no code authority for Tier 5 "
                    "demotion. Council should assign tier and verify "
                    "the section assignment."
                )
        else:
            # Branch 3 or 4: structural near-miss.
            if _is_reference_doc(source_document):
                formal["tier"] = 2  # provisional
                formal["source_type"] = "reference-file"
                formal["skill_section"] = None
                formal["disposition"] = "needs-council-review"
                formal["council_review_rationale"] = (
                    "Structural reference to a reference file but "
                    "Pass B's mechanical search did not verify; "
                    "provisional Tier 2."
                )
            else:
                formal["tier"] = 1  # provisional
                formal["source_type"] = "skill-section"
                formal["skill_section"] = section_heading
                formal["disposition"] = "needs-council-review"
                formal["council_review_rationale"] = (
                    "Structural reference to SKILL.md but Pass B's "
                    "mechanical search did not verify; provisional "
                    "Tier 1 / skill-section."
                )

    # Round 5 ND-2 guard: schemas.md invariant #21 requires
    # skill_section to be a non-empty string when source_type ==
    # "skill-section". A Pass A draft with neither a section_heading
    # field nor a parseable proposed_source_ref leaves
    # _section_heading_for returning None, which would emit a record
    # with skill_section None/empty. Re-route that case to
    # council-review with a provisional skill_section placeholder so
    # the manifest validator does not FAIL on the record.
    if formal["source_type"] == "skill-section":
        ss = formal.get("skill_section")
        if ss is None or (isinstance(ss, str) and not ss.strip()):
            formal["skill_section"] = (
                "(unable to resolve from draft; council to assign)"
            )
            formal["disposition"] = "needs-council-review"
            formal["council_review_rationale"] = (
                "skill_section unresolvable from Pass A draft "
                "(neither section_heading nor proposed_source_ref "
                "yielded a non-empty value); routed to council-review "
                "per Round 5 ND-2 guard."
            )

    # Invariant: source_type is in the valid set, NEVER reserved.
    assert formal["source_type"] in VALID_SOURCE_TYPES, (
        f"Pass C produced invalid source_type {formal['source_type']!r} "
        f"for record {formal['id']}"
    )
    return formal


def _build_formal_uc(record: dict, *, uc_idx: int) -> dict:
    """UCs do not get citations. Phase 4's Council reviews them.

    Round 7 Council finding: hand-authored / retroactively-synthesized
    UC drafts carry an `_metadata.phase_3d_synthesized=true` tag in
    pass_a_use_case_drafts.jsonl that Phase 4's Council triage relies
    on to differentiate organic UCs (surfaced via section enumeration)
    from hand-authored ones (which need anchor verification before
    BUGs are generated against them). Pass C must propagate this tag
    to the formal UC record so the discipline holds end-to-end.
    """
    formal: dict = {
        "uc_id": _next_uc_id(uc_idx),
        "section_idx": record.get("section_idx"),
        "title": record.get("title", ""),
        "actors": record.get("actors", []),
        "steps": record.get("steps", []),
        "trigger": record.get("trigger", ""),
        "acceptance": record.get("acceptance", ""),
        "needs_council_review": True,
        "uc_draft_idx": record.get("uc_draft_idx"),
    }
    src_metadata = record.get("_metadata") or {}
    if isinstance(src_metadata, dict) and src_metadata.get("phase_3d_synthesized"):
        formal["_metadata"] = {"phase_3d_synthesized": True}
    return formal


def _read_uc_drafts(path: Optional[Path]) -> list[dict]:
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


def run_pass_c(config: PassCConfig, *, resume: bool = True) -> int:
    """Drive Pass C end-to-end. Returns count of records emitted
    (REQs + UCs).

    B4 upstream-status gate: refuses to start unless Pass B is
    complete.
    """
    protocol.require_upstream_complete(
        config.pass_b_progress_path, downstream_pass_name="Pass C"
    )

    project_type = _load_project_type(config.role_map_path)
    citations = _read_citations(config.citations_path)
    uc_drafts = _read_uc_drafts(config.uc_drafts_path)
    total = len(citations) + len(uc_drafts)

    # Resume cursor uses the formal_path for REQs; UCs are processed
    # as a batch at the end of the REQ phase. Simpler than two
    # cursors at the cost of slightly less granular resume.
    cursor = (
        protocol.verify_and_resume(
            config.formal_path, config.progress_path, idx_field="_pass_c_idx"
        )
        if resume
        else 0
    )

    state = protocol.ProgressState(
        pass_="C",
        unit="citation",
        cursor=cursor,
        total=total,
        status="running",
        last_updated=_utc_now_iso(),
    )
    protocol.write_progress_atomic(config.progress_path, state)

    # REQ index recovers from on-disk count (resume-safe).
    req_idx = config.starting_req_idx + _count_existing_reqs(config.formal_path)
    uc_idx = config.starting_uc_idx + _count_existing_ucs(
        config.formal_use_cases_path
    )

    emitted = 0

    for idx, rec in enumerate(citations):
        if idx < cursor:
            continue
        if rec.get("citation_status") == "skipped":
            # Pass-through marker (skip / no_reqs from Pass A).
            cursor = idx + 1
            state = protocol.ProgressState(
                pass_="C", unit="citation", cursor=cursor, total=total,
                status="running", last_updated=_utc_now_iso(),
            )
            protocol.write_progress_atomic(config.progress_path, state)
            continue
        formal = _build_formal_req(
            rec,
            req_idx=req_idx,
            project_type=project_type,
            section_heading=_section_heading_for(rec),
        )
        formal["_pass_c_idx"] = idx
        protocol.append_jsonl(config.formal_path, formal)
        req_idx += 1
        emitted += 1
        cursor = idx + 1
        state = protocol.ProgressState(
            pass_="C", unit="citation", cursor=cursor, total=total,
            status="running", last_updated=_utc_now_iso(),
        )
        protocol.write_progress_atomic(config.progress_path, state)

    # UC processing.
    uc_offset = len(citations)
    for j, uc_rec in enumerate(uc_drafts):
        global_idx = uc_offset + j
        if global_idx < cursor:
            continue
        formal_uc = _build_formal_uc(uc_rec, uc_idx=uc_idx)
        formal_uc["_pass_c_idx"] = global_idx
        protocol.append_jsonl(config.formal_use_cases_path, formal_uc)
        uc_idx += 1
        emitted += 1
        cursor = global_idx + 1
        state = protocol.ProgressState(
            pass_="C", unit="citation", cursor=cursor, total=total,
            status="running", last_updated=_utc_now_iso(),
        )
        protocol.write_progress_atomic(config.progress_path, state)

    state = protocol.ProgressState(
        pass_="C", unit="citation", cursor=total, total=total,
        status="complete", last_updated=_utc_now_iso(),
    )
    protocol.write_progress_atomic(config.progress_path, state)
    return emitted


def _section_heading_for(record: dict) -> Optional[str]:
    """Best-effort recovery of the section heading from a Pass B
    record. Phase 3b doesn't pin the heading on draft records (it
    pins section_idx); the heading is recovered downstream from
    pass_a_sections.json if needed. For Pass C's source_type='skill-
    section' branch we use proposed_source_ref as a fallback when no
    explicit heading is present on the record.
    """
    if record.get("section_heading"):
        return record["section_heading"]
    if record.get("proposed_source_ref"):
        return record["proposed_source_ref"]
    return None


def _count_existing_reqs(path: Path) -> int:
    if not path.is_file():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict) and rec.get("id", "").startswith("REQ-PHASE3-"):
            count += 1
    return count


def _count_existing_ucs(path: Path) -> int:
    if not path.is_file():
        return 0
    count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict) and rec.get("uc_id", "").startswith("UC-PHASE3-"):
            count += 1
    return count


# v1.5.7 089x: every bin/*.py is safe + self-describing on no-args.
if __name__ == "__main__":
    try:
        from bin._purpose import print_purpose as _print_purpose
    except ImportError:
        from _purpose import print_purpose as _print_purpose  # type: ignore[no-redef]
    _print_purpose(
        name='skill_derivation.pass_c',
        summary=(
            "Skill-derivation pass C — prose-to-code divergence "
            "cross-checking (LLM + mechanical lanes). "
        ),
        role=(
            "Entry point for the skill-derivation `pass_c` stage; called "
            "by the skill-derivation orchestrator. "
        ),
        kind="library",
    )
    import sys as _sys
    _sys.exit(0)
