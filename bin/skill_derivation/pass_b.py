"""pass_b.py — Pass B driver (mechanical citation extraction).

Reads pass_a_drafts.jsonl, runs citation_search.find_best_match on
each draft's acceptance_criteria text against SKILL.md + reference
files, and -- when a match meets the similarity threshold -- calls
citation_verifier.extract_excerpt to formalize the byte-deterministic
excerpt at the located line. Emits pass_b_citations.jsonl with
citation_status verified/unverified per draft.

Pass B is mechanical (no LLM), but still obeys the per-pass execution
protocol so a crash mid-extraction does not require re-running the
whole corpus.

Skip / no_reqs markers from Pass A pass through unchanged with a
citation_status of "skipped" -- they're not REQs, they're accounting
records, and Pass C/D recognize them by their `skipped` / `no_reqs`
field.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from bin import citation_verifier
from bin.skill_derivation import citation_search, protocol


@dataclass
class PassBConfig:
    drafts_path: Path  # input: pass_a_drafts.jsonl
    citations_path: Path  # output: pass_b_citations.jsonl
    progress_path: Path  # output: pass_b_progress.json
    skill_md_path: Path
    references_dir: Optional[Path]
    document_root: Path  # repo root, used to resolve doc paths
    similarity_threshold: float = citation_search.DEFAULT_SIMILARITY_THRESHOLD
    # Round 3 Council B4: Pass B MUST verify Pass A reached
    # status="complete" before consuming pass_a_drafts.jsonl. Caller
    # passes the path to pass_a_progress.json; require_upstream_complete
    # is called at the start of run_pass_b. Default convention: Pass A
    # progress sits next to Pass A drafts.
    pass_a_progress_path: Optional[Path] = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_drafts(drafts_path: Path) -> list[dict]:
    if not drafts_path.is_file():
        return []
    out: list[dict] = []
    for line in drafts_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


def _extract_excerpt_at(
    document_root: Path, document_rel: str, line: int
) -> Optional[str]:
    """Wrap citation_verifier.extract_excerpt with line-locator input."""
    doc_path = document_root / document_rel
    if not doc_path.is_file():
        return None
    try:
        document_bytes = doc_path.read_bytes()
        return citation_verifier.extract_excerpt(
            document_bytes,
            doc_path.suffix.lower(),
            section=None,
            line=line,
        )
    except citation_verifier.CitationResolutionError:
        return None
    except Exception:  # noqa: BLE001 -- a missing/corrupt doc is unverified, not fatal
        return None


def _draft_to_citation_record(
    draft: dict,
    documents: list[tuple[str, str]],
    config: PassBConfig,
) -> dict:
    """Run search + extraction for one draft; return the Pass B record."""
    if "draft_idx" not in draft:
        # Skip / no_reqs accounting records pass through; cite_status
        # signals to Pass C/D that no citation work was done.
        rec = dict(draft)
        rec["citation_status"] = "skipped"
        return rec

    candidate = draft.get("acceptance_criteria") or draft.get("description") or ""
    if not candidate.strip():
        return {
            **draft,
            "citation_status": "unverified",
            "citation_excerpt": None,
            "source_document": None,
            "source_section_idx": None,
            "source_line_range": None,
            "similarity_score": 0.0,
            "rationale": "no acceptance_criteria / description text to search on",
        }

    hit = citation_search.find_best_match(
        candidate,
        documents,
        similarity_threshold=config.similarity_threshold,
    )
    if hit is None:
        return {
            **draft,
            "citation_status": "unverified",
            "citation_excerpt": None,
            "source_document": None,
            "source_section_idx": None,
            "source_line_range": None,
            "similarity_score": 0.0,
        }

    excerpt = _extract_excerpt_at(
        config.document_root, hit.document, hit.line_start
    )
    if excerpt is None:
        # Search step found a candidate but excerpt extraction failed
        # (e.g., the anchor is blank in the document, or section
        # resolution disagreed). Record as unverified with the search
        # context so Pass C can decide.
        return {
            **draft,
            "citation_status": "unverified",
            "citation_excerpt": None,
            "source_document": hit.document,
            "source_section_idx": draft.get("section_idx"),
            "source_line_range": [hit.line_start, hit.line_end],
            "similarity_score": hit.score,
            "rationale": "search found candidate but extract_excerpt failed",
        }

    return {
        **draft,
        "citation_status": "verified",
        "citation_excerpt": excerpt,
        "source_document": hit.document,
        "source_section_idx": draft.get("section_idx"),
        "source_line_range": [hit.line_start, hit.line_end],
        "similarity_score": hit.score,
    }


def run_pass_b(config: PassBConfig, *, resume: bool = True) -> int:
    """Drive Pass B end-to-end. Returns count of records emitted.

    Round 3 Council B4: refuses to start unless the upstream Pass A
    progress file reports status="complete". If
    config.pass_a_progress_path is None (legacy callers from before the
    B4 fix), defaults to "pass_a_progress.json" next to the drafts
    JSONL. Raises UpstreamIncompleteError on missing / non-complete
    upstream.
    """
    upstream_progress = (
        config.pass_a_progress_path
        if config.pass_a_progress_path is not None
        else config.drafts_path.with_name("pass_a_progress.json")
    )
    protocol.require_upstream_complete(
        upstream_progress, downstream_pass_name="Pass B"
    )

    drafts = _read_drafts(config.drafts_path)
    total = len(drafts)
    documents = citation_search.collect_documents(
        config.skill_md_path, config.references_dir, config.document_root
    )

    cursor = (
        protocol.verify_and_resume(
            config.citations_path, config.progress_path, idx_field="_pass_b_idx"
        )
        if resume
        else 0
    )
    state = protocol.ProgressState(
        pass_="B",
        unit="draft",
        cursor=cursor,
        total=total,
        status="running",
        last_updated=_utc_now_iso(),
    )
    protocol.write_progress_atomic(config.progress_path, state)

    emitted = 0
    for idx, draft in enumerate(drafts):
        if idx < cursor:
            continue
        rec = _draft_to_citation_record(draft, documents, config)
        # Tag with a per-pass index for resume detection. We tag on
        # the record (not on the input draft) so the input artifact
        # stays unchanged.
        rec["_pass_b_idx"] = idx
        protocol.append_jsonl(config.citations_path, rec)
        cursor = idx + 1
        state = protocol.ProgressState(
            pass_="B",
            unit="draft",
            cursor=cursor,
            total=total,
            status="running",
            last_updated=_utc_now_iso(),
        )
        protocol.write_progress_atomic(config.progress_path, state)
        emitted += 1

    state = protocol.ProgressState(
        pass_="B",
        unit="draft",
        cursor=total,
        total=total,
        status="complete",
        last_updated=_utc_now_iso(),
    )
    protocol.write_progress_atomic(config.progress_path, state)
    return emitted


# v1.5.7 089x: every bin/*.py is safe + self-describing on no-args.
if __name__ == "__main__":
    try:
        from bin._purpose import print_purpose as _print_purpose
    except ImportError:
        from _purpose import print_purpose as _print_purpose  # type: ignore[no-redef]
    _print_purpose(
        name='skill_derivation.pass_b',
        summary=(
            "Skill-derivation pass B — citation + divergence detection. "
        ),
        role=(
            "Entry point for the skill-derivation `pass_b` stage; called "
            "by the skill-derivation orchestrator. "
        ),
        kind="library",
    )
    import sys as _sys
    _sys.exit(0)
