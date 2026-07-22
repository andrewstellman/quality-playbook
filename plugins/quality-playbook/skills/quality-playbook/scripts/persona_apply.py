"""v1.6.0 Feature H slice 5 (Design §8b Guard 4 + Operator controls) — the
safety envelope: auto-apply + review summary + concrete revert + off-switch.

The merge (slice 4) produced a ``MergeResult`` (applied grounded moves + conflicts
+ a renumber ``remap``). This slice makes auto-apply SAFE rather than silent:

- **Auto-apply.** The grounded moves are already written into the manifest by the
  merge, tagged ``source_type: agent-validation`` (Guard 2) with byte-verified
  citations (Guard 1), and flow into Phases 3–6. Conflicts and candidates are NOT
  applied — only surfaced.
- **Remap propagation (traceability).** The single terminal renumber reassigns REQ
  ids; any BUG record that cross-references a REQ id (``req_id``, ``covers[]``) is
  updated via ``remap`` so traceability does not break. (UC carries no REQ ids —
  UC→REQ is render-derived one-way, schemas.md §7 — so it needs no propagation.)
- **Operator-visible review summary.** Every applied agent-validation change with
  its grounding + the surfaced conflicts + the candidate bucket — "surface, don't
  silently apply."
- **Concrete revert.** A real operation: identify the ``agent-validation`` records,
  drop the selected ones (one or all), re-render, re-run the terminal E.6 renumber
  and re-propagate the remap — restoring the pre-persona manifest without
  hand-editing. Round-trips (the snapshot form restores corrects/drops exactly).
- **Off-switch.** A run can disable Feature H entirely — no personas, no
  agent-validation changes; the pipeline proceeds on the base manifest.

**H is a remediator, not a gate:** it applies fixes and shows its work; the review
summary is the backstop, not a pre-approval gate. Stdlib-only bar the two sibling
QPB modules it composes.
"""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from pathlib import Path
import importlib.util as _ilu
import sys as _sys

_HERE = Path(__file__).resolve().parent


def _sibling(mod_name: str, file_name: str):
    try:
        return __import__(f"bin.{mod_name}", fromlist=[mod_name])
    except ImportError:
        spec = _ilu.spec_from_file_location(
            f"_qpb_{mod_name}_via_persona_apply", _HERE / file_name)
        if spec is None or spec.loader is None:
            raise ImportError(f"persona_apply: cannot resolve {file_name}")
        mod = _ilu.module_from_spec(spec)
        _sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        return mod


persona_merge = _sibling("persona_merge", "persona_merge.py")
requirements_render = _sibling("requirements_render", "requirements_render.py")

AGENT_VALIDATION = "agent-validation"
_COVER_RE = re.compile(r"^(REQ-\d+)(/.*)?$")


# ---------------------------------------------------------------------------
# Remap propagation to BUG cross-references.
# ---------------------------------------------------------------------------
def _remap_cover(cover: str, remap: Dict[str, str]) -> str:
    m = _COVER_RE.match(cover or "")
    if not m:
        return cover
    req, rest = m.group(1), m.group(2) or ""
    return f"{remap.get(req, req)}{rest}"


def apply_remap_to_bugs(remap: Dict[str, str], bugs_manifest: dict) -> None:
    """Update every BUG REQ cross-reference (``req_id``, ``covers[]``) via the
    renumber remap, so a renumber never orphans a BUG→REQ link (traceability)."""
    if not remap or not bugs_manifest:
        return
    for bug in bugs_manifest.get("records", []):
        rid = bug.get("req_id")
        if rid in remap:
            bug["req_id"] = remap[rid]
        covers = bug.get("covers")
        if isinstance(covers, list):
            bug["covers"] = [_remap_cover(c, remap) for c in covers]


# ---------------------------------------------------------------------------
# Review summary.
# ---------------------------------------------------------------------------
def build_review_summary(merge_result, candidate_bucket: Optional[Sequence[dict]] = None) -> dict:
    """Operator-visible: every applied agent-validation change with grounding,
    plus the surfaced conflicts and the candidate bucket. Nothing applied is
    omitted."""
    applied = [
        {
            "persona_id": m.get("persona_id"),
            "move": m.get("move"),
            "req_id": m.get("req_id"),
            "section": m.get("section"),
            "title": m.get("title"),
            "reason": m.get("reason"),
            "system_justification": m.get("system_justification"),
            "citation": m.get("citation"),
            "source_type": AGENT_VALIDATION,
        }
        for m in merge_result.applied
    ]
    conflicts = [
        {"target": c.target, "reason": c.reason, "personas": c.personas, "moves": c.moves}
        for c in merge_result.conflicts
    ]
    return {
        "applied": applied,
        "applied_count": len(applied),
        "conflicts": conflicts,
        "conflict_count": len(conflicts),
        "candidates": list(candidate_bucket or []),
    }


# ---------------------------------------------------------------------------
# The persona pass (off-switch + snapshot for revert).
# ---------------------------------------------------------------------------
@dataclass
class PersonaPass:
    enabled: bool
    manifest: dict
    review_summary: Optional[dict]
    remap: Dict[str, str] = field(default_factory=dict)
    merge_result: object = None
    _pre_requirements: Optional[dict] = None
    _pre_bugs: Optional[dict] = None


def run_persona_pass(
    base_manifest: dict,
    grounded_by_persona: Sequence[dict],
    bugs_manifest: Optional[dict] = None,
    *,
    candidate_bucket: Optional[Sequence[dict]] = None,
    enabled: bool = True,
) -> PersonaPass:
    """Apply the merged grounded moves + build the review summary + propagate the
    remap. **Off-switch:** ``enabled=False`` does NOTHING — no merge, no
    agent-validation changes; the base manifest is returned unchanged and the
    pipeline proceeds without the persona pass."""
    if not enabled:
        return PersonaPass(enabled=False, manifest=base_manifest, review_summary=None)

    pre_req = copy.deepcopy(base_manifest)
    pre_bugs = copy.deepcopy(bugs_manifest) if bugs_manifest is not None else None

    mr = persona_merge.merge_personas(grounded_by_persona, base_manifest)
    if bugs_manifest is not None:
        apply_remap_to_bugs(mr.remap, bugs_manifest)
    summary = build_review_summary(mr, candidate_bucket)

    return PersonaPass(
        enabled=True, manifest=base_manifest, review_summary=summary,
        remap=mr.remap, merge_result=mr,
        _pre_requirements=pre_req, _pre_bugs=pre_bugs,
    )


# ---------------------------------------------------------------------------
# Concrete revert.
# ---------------------------------------------------------------------------
def agent_validation_records(manifest: dict) -> List[dict]:
    """The records the revert filters on — REQ records tagged agent-validation."""
    return [r for r in manifest.get("records", []) if r.get("source_type") == AGENT_VALIDATION]


def revert(pass_result: PersonaPass, bugs_manifest: Optional[dict] = None, *, which="all"):
    """Revert agent-validation changes, restoring the pre-persona state.

    ``which="all"`` restores the pre-persona requirements manifest (and BUG
    cross-references) EXACTLY from the snapshot — a full round-trip that also
    undoes corrects and drops. ``which=<sequence of REQ ids>`` drops those
    specific agent-validation records from the current manifest, then re-renders
    (document order), re-runs the terminal E.6 renumber, and re-propagates the
    remap to BUG — the design's "filter by source_type == agent-validation, drop
    the selected records" operation. Returns ``(requirements_manifest,
    bugs_manifest)``; both are new/mutated to the reverted state.
    """
    if which == "all":
        restored = copy.deepcopy(pass_result._pre_requirements)
        restored_bugs = copy.deepcopy(pass_result._pre_bugs) if pass_result._pre_bugs is not None else None
        if bugs_manifest is not None and restored_bugs is not None:
            bugs_manifest.clear()
            bugs_manifest.update(restored_bugs)
            restored_bugs = bugs_manifest
        # Restore the live requirements manifest object too.
        pass_result.manifest.clear()
        pass_result.manifest.update(restored)
        return pass_result.manifest, restored_bugs

    # Selective drop: `which` is a set of REQ ids (agent-validation ADD records).
    drop_ids = set(which)
    manifest = pass_result.manifest
    av_ids = {r.get("id") for r in agent_validation_records(manifest)}
    to_drop = drop_ids & av_ids   # only agent-validation records are revertible
    manifest["records"] = [r for r in manifest.get("records", []) if r.get("id") not in to_drop]
    remap = requirements_render.renumber_to_document_order(manifest)
    if bugs_manifest is not None:
        apply_remap_to_bugs(remap, bugs_manifest)
    return manifest, bugs_manifest
