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

# The two run artifacts this module writes under the target's ``quality/``. They
# live up here because the operator-facing disclosure (instruction 031 fix 2)
# points the operator at the review summary by path.
#
# The name is deliberately JARGON-FREE (instruction 032 fix 3). Every other
# operator-facing surface of this pass says "expert reviewers"; the filename was
# the last place the internal word "persona" reached an operator — and it reached
# them in the disclosure, which asks them to open the file by name. The internal
# vocabulary stays in the code (this module, its symbols, the design docs); the
# artifact an operator types is in their language.
REVIEW_SUMMARY_NAME = "expert_review_summary.json"
REQUIREMENTS_MANIFEST_NAME = "requirements_manifest.json"
# The pre-pass snapshot (instruction 031 fix 2). The revert has always restored
# from ``PersonaPass._pre_requirements`` — an IN-MEMORY field. The agent runs the
# pass in a scripted Python invocation that exits before the operator ever reads
# the end-of-Phase-2 message, so by the time they can say "undo" the snapshot is
# gone, and a dropped requirement's text and a corrected requirement's original
# wording exist nowhere on disk (instr 031 self-Council, Panelist B: reproduced —
# a rebuilt pass raised ``TypeError`` on revert). Disclosing "I can put your
# requirements back exactly as they were" REQUIRES that to be true, so the pass
# now persists the pre-pass manifest beside the two artifacts it already writes.
PRE_REVIEW_MANIFEST_NAME = "requirements_manifest.pre_review.json"
# Where the review summary goes when the operator undoes the pass. Renamed, not
# deleted: the candidate findings it lists were never applied, and the operator
# was told they are "listed for you to judge" (instr 031 self-Council round 2,
# Panelist B).
UNDONE_REVIEW_SUMMARY_NAME = "expert_review_summary.undone.json"

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
# The operator-facing disclosure (instruction 031 fix 2).
#
# The pass AUTO-APPLIES changes to the operator's requirements, so the standard
# end-of-Phase-2 message has to say so. Before this, the only trace was the
# review-summary artifact — an operator reading the normal message never learned
# their spec had been changed unless they opened that file on their own. That is
# the "surface, don't silently apply" principle failing at the surface that
# actually reaches the operator.
#
# Plain language is a hard contract here, exactly as it is for the end-of-Phase-1
# classification show (instruction 030): NO internal label reaches the operator —
# no "Feature H", no "persona", no "sub-agent", no "agent-validation", no
# "grounded", no "manifest". Per the v1.6.0 plain-language key: persona ->
# "expert reviewer", sub-agent -> "separate helper agent", grounded/cited +
# byte-verified -> "backed by your documentation". That now holds for the literal
# artifact PATH too — the operator has to type it to open the file, so it is an
# operator-facing string like any other and was renamed to match (instruction 032
# fix 3); the internal vocabulary lives in the code, not in their file tree.
# ---------------------------------------------------------------------------
REVIEW_SUMMARY_PATH = f"quality/{REVIEW_SUMMARY_NAME}"


def _plural(n: int, singular: str, plural: str) -> str:
    return f"{n} {singular if n == 1 else plural}"


def persona_review_disclosure(review_summary: Optional[dict]) -> Optional[str]:
    """The plain-language end-of-Phase-2 disclosure that the expert-reviewer pass
    ran and what it did — or ``None`` when it did not run.

    ``review_summary`` is ``PersonaPass.review_summary`` (equivalently the loaded
    ``quality/expert_review_summary.json``). It is ``None`` whenever the pass did
    not run — disabled for the run, or no operator/harness ran it — and then this
    returns ``None`` and the end-of-Phase-2 message gains nothing: a run that had
    no expert review must not claim one.

    Returns Markdown ready to print in chat, carrying no internal labels.
    """
    if not review_summary:
        return None

    applied = list(review_summary.get("applied") or [])
    stated = review_summary.get("applied_count")
    if isinstance(stated, int) and stated != len(applied):
        # A LOSSY summary — the count and the list disagree (a truncated or
        # hand-built `expert_review_summary.json`, an older shape, anything
        # passed through an intermediate). Saying "did not change anything" on
        # evidence that says otherwise is a positive false claim, which is worse
        # than the silence this feature replaced (instr 031 self-Council,
        # Panelist B). Say only what is certain: the review ran, the record is
        # over there, and it can be undone.
        return "\n".join([
            "### I had expert reviewers check your requirements", "",
            "Before moving on, I brought in expert reviewers — one who knows this "
            "kind of system and one who reviews for security — to read your "
            "requirements against the documents you gave me.", "",
            "**The record of what they did is incomplete here, so I won't "
            f"summarize it.** Open `{REVIEW_SUMMARY_PATH}` to see what they "
            "changed. If you would rather not keep their changes, say **undo the "
            "expert review changes** and I will put your requirements back "
            "exactly as they were before this step.",
        ])

    moves = [str(m.get("move") or "").lower() for m in applied]
    added = moves.count("add")
    reworded = moves.count("correct")
    removed = moves.count("drop")
    confirmed = moves.count("confirm")
    set_aside = len(review_summary.get("candidates") or [])
    disagreements = len(review_summary.get("conflicts") or [])
    changed = added + reworded + removed

    lines: List[str] = ["### I had expert reviewers check your requirements", ""]
    lines.append(
        "Before moving on, I brought in expert reviewers — one who knows this kind "
        "of system and one who reviews for security — to read your requirements "
        "against the documents you gave me. They only add or rewrite a "
        "requirement when they can point to the documentation that backs it up."
    )
    lines.append("")

    if not (changed or confirmed or set_aside or disagreements):
        lines.append(
            "They read through your requirements and did not change anything. "
            f"Their notes are in `{REVIEW_SUMMARY_PATH}` if you want to see them."
        )
        return "\n".join(lines)

    lines.append("Here's what they did:")
    if added:
        lines.append(f"- Added {_plural(added, 'requirement', 'requirements')} "
                     "your documentation calls for but the list was missing.")
    if reworded:
        lines.append(f"- Rewrote {_plural(reworded, 'requirement', 'requirements')} "
                     "to match what your documentation actually says.")
    if removed:
        # NOT "…your documentation does not support": a removal is a
        # pass-through move — the grounding guard checks additions and rewrites
        # against your documents, never a removal — so claiming documentary
        # support for it asserts a check the pipeline does not perform, for the
        # most destructive move there is (instr 031 self-Council, Panelist B).
        lines.append(f"- Removed {_plural(removed, 'requirement', 'requirements')} "
                     f"they judged {'does' if removed == 1 else 'do'} not belong. "
                     "(A removal isn't checked against your documents the way an "
                     "addition is — worth a look.)")
    if confirmed:
        lines.append(f"- Read {_plural(confirmed, 'requirement', 'requirements')} "
                     f"and agreed with {'it' if confirmed == 1 else 'them'} as "
                     "written — nothing changed there.")
    if set_aside:
        lines.append(
            f"- Set aside {_plural(set_aside, 'suggestion', 'suggestions')} they "
            f"could not back up with your documents. **I did not act on "
            f"{'it' if set_aside == 1 else 'those'}** — "
            f"{'it is' if set_aside == 1 else 'they are'} listed for you to judge."
        )
    if disagreements:
        lines.append(
            f"- Hit {_plural(disagreements, 'place', 'places')} where the reviewers "
            f"wanted different things. **I left {'it' if disagreements == 1 else 'those'} "
            f"alone** for you to settle."
        )

    lines.append("")
    if changed:
        lines.append(
            f"**Your requirements were changed by this — {_plural(changed, 'change', 'changes')} "
            f"in all.** Every one of them is listed in `{REVIEW_SUMMARY_PATH}` with "
            "what it is based on, so you can check the reasoning. Requirement "
            "numbers were put back in order afterwards, so some of them shifted. "
            "If you would rather not keep any of this, say **undo the expert "
            "review changes** and I will put your requirements back exactly as "
            "they were before this step."
        )
    else:
        lines.append(
            "**Nothing was changed in your requirements.** What they raised is "
            f"listed in `{REVIEW_SUMMARY_PATH}` for you to look over."
        )
    return "\n".join(lines)


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

    **Known limitation of the selective path** (instr 031 self-Council, Panelist
    B — the behavior predates instruction 031, which no longer invites it): a
    ``correct`` move RETAGS the operator's own record ``agent-validation``, so
    naming that id here DELETES their requirement instead of restoring its
    pre-correction wording. Until that is fixed, the operator-facing undo offers
    the whole-pass restore only (``which="all"`` in-process, ``revert_from_disk``
    afterwards), which is exact for adds, corrects and drops alike.
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
# (REVIEW_SUMMARY_NAME / REQUIREMENTS_MANIFEST_NAME are defined at the top of the
# module — the disclosure renderer above needs them.)


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
    to ``quality/expert_review_summary.json`` when ``write`` is True. Returns a
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
        # instruction 031 fix 2: the PRE-pass manifest, so the undo the operator
        # is told about survives the process that ran the pass. Written last and
        # only when the pass actually applied itself — an absent snapshot is the
        # honest signal that there is nothing to undo.
        if result._pre_requirements is not None:
            (quality_dir / PRE_REVIEW_MANIFEST_NAME).write_text(
                json.dumps(result._pre_requirements, indent=2, sort_keys=True) + "\n",
                encoding="utf-8")
    return result


def revert_from_disk(target_repo, *, write: bool = True) -> dict:
    """Undo the whole pass in a LATER process, from the artifacts on disk.

    This is what the end-of-Phase-2 disclosure's *"say **undo the expert review
    changes**"* resolves to. It restores ``quality/requirements_manifest.json``
    from the pre-pass snapshot ``quality/requirements_manifest.pre_review.json``
    — which restores adds, corrects AND drops exactly, because it is the whole
    prior manifest rather than a replay — and returns the restored manifest. The
    caller (the running agent) then RE-RENDERS ``quality/REQUIREMENTS.md`` from
    it, the same write-back step the pass itself and the human interview use.

    Refuses rather than guessing, in three distinguishable states (instr 031
    self-Council round 2, Panelist B):

    * **No snapshot and no review summary** — no pass ran. ``FileNotFoundError``
      saying exactly that: there is nothing to undo.
    * **No snapshot but a review summary IS present** — a pass ran and its
      pre-pass state was not kept (it predates this snapshot). That is NOT
      "nothing to undo": the requirements *were* changed. ``FileNotFoundError``
      says so and points at the summary, which lists every change, for a manual
      restore. Telling the operator "nothing happened" here would be a lie about
      a state where something did.
    * **BUG records already exist** — Phases 3+ have run and BUG records
      cross-reference REQ ids. Restoring the manifest underneath them would
      orphan those links (the in-process ``revert`` re-maps them via
      ``apply_remap_to_bugs``; from disk the remap is gone). ``ValueError``,
      because a silent orphaning is worse than a refusal.

    Otherwise: the whole prior manifest is restored — exact for adds, corrects
    AND drops, because it is the prior state rather than a replay. The review
    summary is RENAMED (``…undone.json``), not deleted: the candidates it lists
    were never applied, the disclosure told the operator they are "listed for you
    to judge", and undoing the applied changes is no reason to destroy them. The
    canonical name is freed so a later render cannot re-disclose an undone pass.
    """
    quality_dir = Path(target_repo) / "quality"
    snapshot = quality_dir / PRE_REVIEW_MANIFEST_NAME
    summary = quality_dir / REVIEW_SUMMARY_NAME
    undone = quality_dir / UNDONE_REVIEW_SUMMARY_NAME
    if not snapshot.is_file():
        if summary.is_file():
            raise FileNotFoundError(
                f"an expert-review pass ran here but its pre-pass snapshot was "
                f"not kept ({snapshot} is absent), so this cannot restore it "
                f"automatically. The requirements WERE changed: every change is "
                f"listed in {summary} and can be undone by hand."
            )
        if undone.is_file():
            # A SECOND undo. Saying "the pass did not run here" would be
            # confusing with the undone record sitting right there (instr 031
            # self-Council round 3, Panelist B).
            raise FileNotFoundError(
                f"the expert review here has already been undone — the "
                f"requirements are back to their pre-review state and the "
                f"reviewers' notes are kept at {undone}."
            )
        raise FileNotFoundError(
            f"no pre-review snapshot at {snapshot} and no review summary — the "
            f"expert-review pass did not run here. There is nothing to undo."
        )
    bugs = quality_dir / "bugs_manifest.json"
    if bugs.is_file():
        try:
            data = json.loads(bugs.read_text(encoding="utf-8"))
            # Only a mapping that actually HAS `records` is a shape we can read.
            # A list / null / anything else would escape this handler as an
            # AttributeError and refuse by traceback rather than by the designed
            # message; and a dict keyed `bugs` instead of `records` — the
            # documented 2026-05-16 express defect (`phase_prompts/phase2.md`) —
            # would read as "no bugs" and let a late undo orphan real BUG→REQ
            # links (instr 031 self-Council rounds 3 + 4, Panelist B). Unreadable
            # means assume the risk is real, in every direction.
            readable = isinstance(data, dict) and "records" in data
            has_bugs = bool(data["records"]) if readable else True
        except (OSError, ValueError):
            readable, has_bugs = False, True   # unreadable: assume risk is real
        if has_bugs:
            # Say which of the two it is. Refusing is right either way, but
            # "BUG records already exist" is only ESTABLISHED in the first case,
            # and State P2 tells the agent to report the refusal it got (instr
            # 031 self-Council round 5, Panelist B).
            if readable:
                raise ValueError(
                    f"BUG records already exist ({bugs}); they cross-reference "
                    f"REQ ids that restoring the pre-review requirements would "
                    f"orphan. Undo the expert review at the Phase 2 -> 3 "
                    f"boundary, before Phase 3 builds on the requirements."
                )
            raise ValueError(
                f"cannot read the bug manifest at {bugs}, so whether BUG records "
                f"cross-reference the requirements is unknown — assuming the risk "
                f"is real rather than orphaning them. Fix or remove that file, or "
                f"undo the expert review at the Phase 2 -> 3 boundary."
            )
    restored = json.loads(snapshot.read_text(encoding="utf-8"))
    if write:
        (quality_dir / REQUIREMENTS_MANIFEST_NAME).write_text(
            json.dumps(restored, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if summary.is_file():
            # Never clobber an earlier undone record: a second pass + undo would
            # otherwise erase the first review's set-aside findings, which is the
            # very loss the rename exists to prevent (instr 031 self-Council
            # round 4, Panelist B).
            dest = quality_dir / UNDONE_REVIEW_SUMMARY_NAME
            n = 2
            while dest.exists():
                dest = quality_dir / UNDONE_REVIEW_SUMMARY_NAME.replace(
                    ".undone.json", f".undone.{n}.json")
                n += 1
            summary.replace(dest)
        snapshot.unlink(missing_ok=True)
    return restored
