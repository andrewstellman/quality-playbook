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
import json
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
persona_catalog = _sibling("persona_catalog", "persona_catalog.py")
persona_orchestration = _sibling("persona_orchestration", "persona_orchestration.py")
persona_grounding = _sibling("persona_grounding", "persona_grounding.py")

AGENT_VALIDATION = "agent-validation"
_COVER_RE = re.compile(r"^(REQ-\d+)(/.*)?$")

# v1.6.0 Feature H slice 6 (§8b "Honesty about maturity"). A persona finding that
# rests on the readability rubric — the Well-organized / readable dimension the
# release itself calls "not yet a functional drift detector" (§5 Verification b) —
# must be disclosed with a maturity caveat, the way F-1 discloses coverage gaps,
# rather than presented with uniform confidence. A finding is rubric-dependent
# when it carries `rubric_dependent: True` or a readability `dimension`.
_RUBRIC_DIMENSIONS = frozenset({
    "well-organized", "well organized", "wellorganized",
    "readability", "readable", "readability-rubric",
})
_MATURITY_DISCLOSURE = (
    "Maturity: {n} of these findings rest on the readability (Well-organized) "
    "rubric, which v1.6.0 does not yet treat as a functional drift detector "
    "(Design §5 Verification b). Treat them with lower confidence than the "
    "byte-verified grounded changes; findings that do not depend on the rubric "
    "are unaffected."
)


def _is_rubric_dependent(item: dict) -> bool:
    if item.get("rubric_dependent"):
        return True
    dim = (item.get("dimension") or "").strip().lower()
    return dim in _RUBRIC_DIMENSIONS


def maturity_disclosure(items: Sequence[dict]) -> Optional[str]:
    """The maturity caveat string when any of *items* is rubric-dependent, else
    None (a run with no rubric-dependent finding carries no caveat)."""
    n = sum(1 for it in items if _is_rubric_dependent(it))
    return _MATURITY_DISCLOSURE.format(n=n) if n else None


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
    # instruction 028 fix 4: the terminal renumber remaps REQ ids, but the moves
    # recorded in the review summary still carry PRE-renumber `req_id`s (a confirm
    # move points at a stale id after persona adds shift the numbering). Apply the
    # SAME remap already used for BUG cross-refs so every summary entry references
    # post-renumber ids.
    remap = getattr(merge_result, "remap", None) or {}

    def _rid(v):
        return remap.get(v, v) if v is not None else v

    applied = [
        {
            "persona_id": m.get("persona_id"),
            "move": m.get("move"),
            "req_id": _rid(m.get("req_id")),
            "section": m.get("section"),
            "title": m.get("title"),
            "reason": m.get("reason"),
            "system_justification": m.get("system_justification"),
            "citation": m.get("citation"),
            "source_type": AGENT_VALIDATION,
            # Carried so the maturity disclosure can key on rubric-dependence.
            "dimension": m.get("dimension"),
            "rubric_dependent": bool(m.get("rubric_dependent") or
                                     (m.get("dimension") or "").strip().lower() in _RUBRIC_DIMENSIONS),
        }
        for m in merge_result.applied
    ]
    conflicts = [
        {"target": _rid(c.target), "reason": c.reason, "personas": c.personas,
         "moves": [{**mv, "req_id": _rid(mv.get("req_id"))} if mv.get("req_id") is not None
                   else mv for mv in c.moves]}
        for c in merge_result.conflicts
    ]
    candidates = list(candidate_bucket or [])
    # §8b "Honesty about maturity": disclose over everything surfaced (applied +
    # candidates + the moves inside conflicts).
    all_items = applied + candidates
    for c in conflicts:
        all_items.extend(c.get("moves", []))
    return {
        "applied": applied,
        "applied_count": len(applied),
        "conflicts": conflicts,
        "conflict_count": len(conflicts),
        "candidates": candidates,
        "maturity_disclosure": maturity_disclosure(all_items),
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


# ---------------------------------------------------------------------------
# The composed Feature H pipeline step (instruction 021).
# ---------------------------------------------------------------------------
REVIEW_SUMMARY_NAME = "persona_review_summary.json"
REQUIREMENTS_MANIFEST_NAME = "requirements_manifest.json"


def run_feature_h(
    target_repo,
    *,
    base_manifest: dict,
    proposed_personas: Sequence[dict],
    provision,
    spawn_persona,
    formal_docs: Sequence[dict],
    staging_root,
    bugs_manifest: Optional[dict] = None,
    domain_specialization: Optional[str] = None,
    enabled: bool = True,
    write: bool = True,
) -> "PersonaPass":
    """The single composed Feature H pipeline step (Design §8b guard 4, §6
    post-Phase-2 placement). Runs the full persona pass by REUSING the six
    modules — it reimplements no guard:

      select personas (catalog + anchors)            [persona_catalog]
        -> stage isolated inputs + spawn tool-restricted persona sub-agents
                                                       [persona_orchestration]
        -> classify each raw diff-set grounded/candidate (guard 1)
                                                       [persona_grounding]
        -> merge grounded moves, surface conflicts, one renumber (guard 3)
                                                       [persona_merge, via run_persona_pass]
        -> apply + emit the operator-visible review summary (guard 4)
                                                       [run_persona_pass, this module]

    ``spawn_persona(persona, staging_dir, tool_config) -> raw_diff_set`` is the
    runtime persona sub-agent spawn (the instruction-019 pattern — the running
    agent's Task tool, tool-restricted per slice 2); tests inject a canned stub.
    ``provision(persona) -> [StagedInput]`` is the per-target context (Feature H:
    gathered docs + rendered spec + rubric). Honors the **off-switch**: with
    ``enabled=False`` NOTHING runs — no personas spawned, no agent-validation
    changes, the base manifest is returned unchanged. Writes the review summary
    to ``quality/persona_review_summary.json`` when ``write`` is True. Returns a
    PersonaPass carrying the applied manifest + review summary.

    Call this AFTER Phase-2 requirements finalize and BEFORE Phases 3-6.
    """
    target_repo = Path(target_repo)
    if not enabled:
        return PersonaPass(enabled=False, manifest=base_manifest, review_summary=None)

    # 1. Select — catalog + mechanical anchors (domain + security always present).
    selected = persona_catalog.select_personas(
        proposed_personas, domain_specialization=domain_specialization)

    # 2. Stage isolated inputs + spawn the tool-restricted persona sub-agents.
    #    run_personas enforces prevention-by-absence staging + Read-rooted config
    #    and returns each persona's RAW candidate diff-set.
    runs = persona_orchestration.run_personas(
        selected, provision, spawn_persona, Path(staging_root))

    # 3. Ground each raw diff-set (guard 1): grounded vs candidate. Forward the
    #    grounded add/correct moves AND the ungated pass-through moves
    #    (confirm/drop) to the merge — a drop is applied (guard 4) and a
    #    confirm/drop participates in the guard-3 conflict check. Forwarding only
    #    `grounded` here would silently drop every confirm/drop at the seam
    #    (instruction-022 umbrella-Council fix).
    grounded_by_persona: List[dict] = []
    grounding_results = []
    for run in runs:
        gr = persona_grounding.classify_diff_set(run.diff_set, formal_docs, target_repo)
        grounding_results.append(gr)
        grounded_by_persona.append({
            "persona_id": run.persona_id,
            "moves": [c.move for c in gr.grounded] + list(gr.passthrough),
        })
    candidates = persona_grounding.candidate_bucket(grounding_results)

    # 4-5. Merge (guard 3) + apply + review summary (guard 4). run_persona_pass
    #      snapshots for revert and honors provenance.
    result = run_persona_pass(
        base_manifest, grounded_by_persona, bugs_manifest,
        candidate_bucket=candidates, enabled=True)

    # 6. Persist the updated requirements manifest (the source of truth) + write
    #    the operator-visible review summary as run artifacts.
    if write and result.review_summary is not None:
        quality_dir = target_repo / "quality"
        quality_dir.mkdir(parents=True, exist_ok=True)
        # instruction 028 fix 3 (persist-manifest + prose re-render): the persona
        # pass mutated the manifest (adds/corrects/drops + the terminal renumber),
        # so write it back to quality/requirements_manifest.json — the source of
        # truth. REQUIREMENTS.md itself is AI-authored (the "Feature C renderer"
        # is the agent, requirements_interview.md § Write-back), so the running
        # agent re-renders it from this updated manifest after the pass, exactly
        # as the human interview write-back does (prose in requirements_interview
        # § persona playback + requirements_pipeline § E.9). There is no Python
        # markdown renderer to call here — persisting the manifest is the Python
        # half; the re-render is the same AI step the human interview uses.
        (quality_dir / REQUIREMENTS_MANIFEST_NAME).write_text(
            json.dumps(result.manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        (quality_dir / REVIEW_SUMMARY_NAME).write_text(
            json.dumps(result.review_summary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
    return result
