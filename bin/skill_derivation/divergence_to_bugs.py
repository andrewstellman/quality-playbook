"""divergence_to_bugs.py — Phase 4 Part D.1: convert detected
divergences into formal BUG records.

Reads:
  quality/phase3/pass_e_internal_divergences.jsonl
  quality/phase3/pass_e_prose_to_code_divergences.jsonl
  quality/phase3/pass_e_execution_divergences.jsonl

Emits:
  quality/phase3/pass_e_bugs.jsonl

Per the Phase 4 brief Part D.1, the BUG record carries the v1.5.3-
extended schema fields: bug_id, divergence_type, disposition
(provisional from divergence; Council can override), description
(auto-generated), affected_artifacts, severity (default "medium"),
tier (per v1.5.0 BUG schema convention; we default to 1 for
internal-prose against SKILL.md, 2 for reference-file inputs, 3 for
prose-to-code, 5 for execution where the gate failure is the
authority), triage_batch_key (propagated from the divergence).

The fields the v1.5.0 BUG manifest invariant #21+#22 requires
(req_id, divergence_description, documented_intent, code_behavior,
disposition_rationale, fix_type, proposed_fix) are populated to the
extent the divergence record carries them; the "description" field
is the human-readable summary the Council uses for triage. The
output is a *seed* for Phase 5's bugs_manifest.json — it carries
just enough to index back to the divergence; Phase 5's curation
pass owns the full manifest shape.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


@dataclass
class DivergenceToBugsConfig:
    internal_path: Path
    prose_to_code_path: Path
    execution_path: Path
    output_path: Path
    starting_bug_idx: int = 1


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


def _bug_id(idx: int) -> str:
    return f"BUG-PHASE4-{idx:03d}"


def _disposition_to_fix_type(disposition: Optional[str]) -> str:
    """schemas.md §3.4: legal disposition × fix_type matrix.

    code-fix     -> fix_type ∈ {code, both}; default "code"
    spec-fix     -> fix_type ∈ {spec, both}; default "spec"
    upstream-spec-issue -> fix_type ∈ {spec, both}; default "spec"
    mis-read     -> fix_type ∈ {code, spec}; default "spec"
    deferred     -> any; default "spec"
    None         -> default "spec" (Council assigns)
    """
    if disposition == "code-fix":
        return "code"
    if disposition == "spec-fix":
        return "spec"
    if disposition == "upstream-spec-issue":
        return "spec"
    if disposition == "mis-read":
        return "spec"
    return "spec"


def _bug_for_internal(div: dict, idx: int) -> dict:
    disposition = div.get("provisional_disposition")
    description = (
        f"Internal-prose divergence ({div.get('subtype', 'unknown')}): "
        f"{div.get('rationale', '')}"
    )
    affected = [div.get("source_document") or "SKILL.md"]
    if div.get("provisional_disposition_target"):
        affected.append(div["provisional_disposition_target"])
    return {
        "bug_id": _bug_id(idx),
        "divergence_type": "internal-prose",
        "subtype": div.get("subtype"),
        "divergence_id": div.get("divergence_id"),
        "req_id": div.get("req_a_id"),
        "secondary_req_id": div.get("req_b_id"),
        "disposition": disposition,
        "fix_type": _disposition_to_fix_type(disposition),
        "description": description,
        "documented_intent": div.get("excerpt_a") or "",
        "code_behavior": div.get("excerpt_b") or "",
        "disposition_rationale": div.get("rationale") or "",
        "affected_artifacts": affected,
        "severity": "MEDIUM",
        "tier": 1,
        "triage_batch_key": div.get("triage_batch_key"),
        "section_idx": div.get("section_idx"),
        "section_heading": div.get("section_heading"),
        "generated_at": _utc_now_iso(),
    }


def _bug_for_prose_to_code(div: dict, idx: int) -> dict:
    disposition = div.get("provisional_disposition")
    subtype = div.get("subtype")
    if subtype == "mechanical-countable":
        description = (
            f"Prose-to-code divergence (mechanical): claimed "
            f"{div.get('claimed_count')!r} vs actual "
            f"{div.get('actual_count')!r} for "
            f"{div.get('code_artifact')!r} via "
            f"{div.get('code_count_pattern')!r}."
        )
        documented_intent = div.get("excerpt", "")
        code_behavior = (
            f"{div.get('code_artifact')} matches "
            f"{div.get('actual_count')} via "
            f"{div.get('code_count_pattern')}"
        )
        affected = [
            div.get("source_document") or "SKILL.md",
            div.get("code_artifact") or "",
        ]
    else:  # llm-judged
        description = (
            f"Prose-to-code divergence (LLM-judged "
            f"{div.get('llm_verdict')!r}): "
            f"{div.get('llm_rationale', '')}"
        )
        documented_intent = div.get("excerpt", "")
        code_behavior = (
            f"LLM verdict on {div.get('code_artifact')}: "
            f"{div.get('llm_verdict')!r}"
        )
        affected = [
            div.get("source_document") or "SKILL.md",
            div.get("code_artifact") or "",
        ]
    return {
        "bug_id": _bug_id(idx),
        "divergence_type": "prose-to-code",
        "subtype": subtype,
        "divergence_id": div.get("divergence_id"),
        "req_id": div.get("req_id"),
        "disposition": disposition,
        "fix_type": _disposition_to_fix_type(disposition),
        "description": description,
        "documented_intent": documented_intent,
        "code_behavior": code_behavior,
        "disposition_rationale": div.get("rationale") or "",
        "affected_artifacts": [a for a in affected if a],
        "severity": "MEDIUM",
        "tier": 3,
        "triage_batch_key": div.get("triage_batch_key"),
        "section_idx": div.get("section_idx"),
        "section_heading": div.get("section_heading"),
        "generated_at": _utc_now_iso(),
    }


def _bug_for_execution(div: dict, idx: int) -> dict:
    disposition = div.get("provisional_disposition")
    description = (
        f"Execution divergence: REQ {div.get('req_id')} associated "
        f"gate checks failed in {div.get('fail_count')} of "
        f"{div.get('total_runs_considered')} archived runs "
        f"({div.get('confidence')} confidence)."
    )
    return {
        "bug_id": _bug_id(idx),
        "divergence_type": "execution",
        "divergence_id": div.get("divergence_id"),
        "req_id": div.get("req_id"),
        "disposition": disposition,
        "fix_type": _disposition_to_fix_type(disposition),
        "description": description,
        "documented_intent": "",
        "code_behavior": (
            f"failed runs: {div.get('failed_run_ids', [])}"
        ),
        "disposition_rationale": div.get("rationale") or "",
        "affected_artifacts": [
            "SKILL.md",
            ".github/skills/quality_gate/quality_gate.py",
        ],
        "severity": "MEDIUM" if div.get("confidence") in ("high", "medium") else "LOW",
        "tier": 5,
        "triage_batch_key": div.get("triage_batch_key"),
        "gate_check_ids": div.get("gate_check_ids", []),
        "failed_run_ids": div.get("failed_run_ids", []),
        "confidence": div.get("confidence"),
        "generated_at": _utc_now_iso(),
    }


def _consolidate_prose_to_code(divs: list[dict]) -> list[list[dict]]:
    """Round 8 Finding 2 / schemas.md §8.1: prose-to-code divergence
    records that share the same (code_artifact, claimed_count,
    actual_count, code_count_pattern) tuple represent the same
    underlying prose-vs-code mismatch surfaced from multiple REQs (the
    same prose phrase repeated across sections). Consolidate them into
    a single BUG with a `covers` array per the cell-identity rules.

    Returns a list of groups; each group is a list of divergence dicts
    that share the consolidation key. Single-divergence groups are
    preserved (they emit a normal BUG without `covers`).

    llm-judged divergences are kept ungrouped — the LLM verdict +
    rationale is per-call, not per-prose-phrase.
    """
    groups: dict = {}
    standalone: list[dict] = []
    for div in divs:
        if div.get("subtype") != "mechanical-countable":
            standalone.append(div)
            continue
        key = (
            div.get("code_artifact"),
            div.get("claimed_count"),
            div.get("actual_count"),
            div.get("code_count_pattern"),
        )
        groups.setdefault(key, []).append(div)
    out: list[list[dict]] = []
    for key in groups:
        out.append(groups[key])
    for div in standalone:
        out.append([div])
    return out


def _consolidated_bug_for_prose_to_code(
    group: list[dict], idx: int,
) -> dict:
    """Build a single BUG record covering all divergences in `group`.
    When len(group) == 1 the result is the normal per-divergence BUG.
    When len(group) >= 2 the BUG carries `covers` (the list of
    DIV-P2C-* IDs in the group) and `consolidation_rationale` per
    schemas.md §8.1."""
    if len(group) == 1:
        return _bug_for_prose_to_code(group[0], idx)
    primary = group[0]
    bug = _bug_for_prose_to_code(primary, idx)
    covers = [d.get("divergence_id") for d in group if d.get("divergence_id")]
    bug["covers"] = covers
    bug["consolidation_rationale"] = (
        f"{len(group)} prose-to-code divergence records share the "
        f"same (code_artifact={primary.get('code_artifact')!r}, "
        f"claimed_count={primary.get('claimed_count')}, "
        f"actual_count={primary.get('actual_count')}, "
        f"code_count_pattern={primary.get('code_count_pattern')!r}) "
        "tuple — the same prose-vs-code mismatch surfaced via multiple "
        "REQs. Per schemas.md §8.1 cell-identity rules, consolidated "
        "into one BUG."
    )
    # Aggregate the secondary REQ ids so triage can see every site.
    secondary_req_ids = []
    for d in group[1:]:
        rid = d.get("req_id")
        if rid and rid != bug.get("req_id"):
            secondary_req_ids.append(rid)
    if secondary_req_ids:
        bug["secondary_req_ids"] = secondary_req_ids
    return bug


def run_divergence_to_bugs(config: DivergenceToBugsConfig) -> dict:
    """Drive Part D.1 end-to-end. Returns summary dict.

    Round 8 Finding 2: prose-to-code divergence records sharing
    (code_artifact, claimed_count, actual_count, code_count_pattern)
    consolidate into one BUG with a `covers` array.
    """
    internals = _read_jsonl(config.internal_path)
    prose_to_codes = _read_jsonl(config.prose_to_code_path)
    executions = _read_jsonl(config.execution_path)

    output_lines: list[str] = []
    bug_idx = config.starting_bug_idx
    consolidated_groups = 0

    for div in internals:
        bug = _bug_for_internal(div, bug_idx)
        output_lines.append(json.dumps(bug, sort_keys=False))
        bug_idx += 1
    for group in _consolidate_prose_to_code(prose_to_codes):
        if len(group) >= 2:
            consolidated_groups += 1
        bug = _consolidated_bug_for_prose_to_code(group, bug_idx)
        output_lines.append(json.dumps(bug, sort_keys=False))
        bug_idx += 1
    for div in executions:
        bug = _bug_for_execution(div, bug_idx)
        output_lines.append(json.dumps(bug, sort_keys=False))
        bug_idx += 1

    config.output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = config.output_path.with_name(config.output_path.name + ".tmp")
    tmp.write_text(
        ("\n".join(output_lines) + "\n") if output_lines else "",
        encoding="utf-8",
    )
    os.replace(tmp, config.output_path)

    prose_to_code_bug_count = sum(
        1 for g in _consolidate_prose_to_code(prose_to_codes)
    )
    return {
        "bugs_emitted": len(output_lines),
        "internal_bugs": len(internals),
        "prose_to_code_bugs": prose_to_code_bug_count,
        "prose_to_code_divergences_in": len(prose_to_codes),
        "prose_to_code_groups_consolidated": consolidated_groups,
        "execution_bugs": len(executions),
    }


# v1.5.7 089x: every bin/*.py is safe + self-describing on no-args.
if __name__ == "__main__":
    try:
        from bin._purpose import print_purpose as _print_purpose
    except ImportError:
        from _purpose import print_purpose as _print_purpose  # type: ignore[no-redef]
    _print_purpose(
        name='skill_derivation.divergence_to_bugs',
        summary=(
            "Divergence-to-bug-candidate converter — turns the divergence "
            "detectors' raw output into Phase 2-style bug candidates. "
        ),
        role=(
            "Imported by skill_derivation pass D as the final stage of "
            "the bug-generation pipeline. "
        ),
        kind="library",
    )
    import sys as _sys
    _sys.exit(0)
