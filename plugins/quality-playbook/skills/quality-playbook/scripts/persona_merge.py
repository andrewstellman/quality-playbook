"""v1.6.0 Feature H slice 4 (Design §8b Guard 3) — multi-persona merge.

Personas run in parallel, blind to each other (slice 2), and each emits grounded
moves (slice 3). This slice combines them under the load-bearing §8b rule:

- **Union the grounded moves.** Non-overlapping `add`/`correct`/`drop` moves from
  different personas all land. `confirm` records that a persona validated an
  existing REQ. `defer` is operator-only and never appears.
- **Surface conflicts, never auto-resolve.** Where two personas' moves touch the
  same REQ (or an add's target) and DISAGREE — an `add` vs a `drop`, divergent
  `correct`s, a `confirm` vs a `drop` — that pair is an operator-facing conflict
  flag carrying both moves, both personas, and both reasons. Conflicting moves are
  HELD OUT of the applied set; no heuristic picks a winner.
- **A `confirm` beside a grounded `correct` is a dissent, not a conflict**
  (v1.6.1 [H3]). The `correct` is byte-verified against a cited document; the
  `confirm` cites nothing. Holding both out left a REQ wider than its excerpt
  (QPB 1.6.0 on collective/icalendar, 2026-10-01). The `correct` applies; the
  `confirm` is recorded in ``MergeResult.dissents`` for the review summary.
- **Adds citing the same passage are one cluster** (v1.6.1 [H4]). Adds in the
  same section whose citations name the same document and the same or an
  overlapping excerpt line range (or byte-identical excerpt text) state the same
  requirement. The first in input order applies; the rest go to
  ``MergeResult.duplicates``. The icalendar run applied seven overlapping
  "RECUR range" adds from three personas because only identical content collapsed.
- **A `correct` replaces every prose field it supplies** (v1.6.1 [H2]). Any
  claim-bearing prose field (``PROSE_FIELDS``) the record carries and the move
  does not supply is listed in the record's ``needs_text_review`` and on the
  applied move, so the review summary names it.
- **Exactly one terminal renumber, after the merge.** The union + hold-out is
  applied to the base manifest, then ``requirements_render.renumber_to_document_
  order`` runs ONCE (personas do not each renumber) — the §6 "renumber once after
  all moves" contract for the multi-persona case.
- **Provenance preserved.** Every applied move keeps its `agent-validation`
  provenance + byte-verified citation (Guard 2 / Guard 1) through the merge and
  renumber, so slice 5's review summary + revert can key on it.

This slice produces the merged manifest + the conflict set. It does NOT build the
operator-visible review summary, the auto-apply framing, the revert operation, or
the off-switch — those are Guard 4 (slice 5). Stdlib-only.
"""

from __future__ import annotations

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
            f"_qpb_{mod_name}_via_persona_merge", _HERE / file_name)
        if spec is None or spec.loader is None:
            raise ImportError(f"persona_merge: cannot resolve {file_name}")
        mod = _ilu.module_from_spec(spec)
        _sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        return mod


requirements_render = _sibling("requirements_render", "requirements_render.py")

# Moves a persona can issue (defer is operator-only and excluded).
_PERSONA_MOVES = ("confirm", "correct", "add", "drop")


@dataclass
class Conflict:
    target: str
    reason: str
    moves: List[dict] = field(default_factory=list)   # both/all conflicting moves
    personas: List[str] = field(default_factory=list)


@dataclass
class MergeResult:
    manifest: dict
    conflicts: List[Conflict] = field(default_factory=list)
    applied: List[dict] = field(default_factory=list)   # moves that landed
    held_out: List[dict] = field(default_factory=list)   # moves in a conflict
    remap: Dict[str, str] = field(default_factory=dict)
    renumber_calls: int = 0
    # v1.6.1 [H3]: confirms overruled by a grounded correct on the same REQ.
    # Each: {"target", "confirm": <move>, "corrected_by": [persona ids]}.
    dissents: List[dict] = field(default_factory=list)
    # v1.6.1 [H4]: adds not applied because an earlier add cites the same
    # passage. Each: {"move": <move>, "duplicate_of": <the applied move>}.
    duplicates: List[dict] = field(default_factory=list)


# v1.6.1 [H2]: the REQ prose fields that state the claim. A `correct` that
# narrows the claim must narrow each one the record carries. Field set read
# from the requirements_manifest.json records of the 2026-09-29 campaign runs
# (schemas.md §6.1 `description` plus the Phase 2 narrative fields).
# `implementation_note` is a code locator, not a claim, so it is not listed.
PROSE_FIELDS = ("title", "description", "summary", "user_story",
                "conditions_of_satisfaction", "alternative_paths")


def _move_target(move: dict) -> Optional[str]:
    """The REQ/section the move touches, for conflict grouping.

    correct/confirm/drop target a `req_id`; an `add` targets its `target_req`
    (the REQ it proposes to replace/oppose) when given, else it is a pure new
    addition that cannot conflict (targets nothing existing)."""
    if move.get("move") in ("correct", "confirm", "drop"):
        return move.get("req_id")
    if move.get("move") == "add":
        return move.get("target_req")
    return None


def _content(move: dict) -> str:
    return (move.get("conditions_of_satisfaction") or move.get("title") or "").strip()


def _dedup_key(move: dict):
    """Identity of a move for agreement-dedup: two personas independently
    proposing the SAME move (same type, same target/section, same content) is
    agreement — it must apply ONCE, not once per persona (self-Council C)."""
    return (move.get("move"), _move_target(move) or "",
            (move.get("section") or "").strip(), _content(move))


def _dedup(moves: Sequence[dict]) -> List[dict]:
    seen = set()
    out: List[dict] = []
    for m in moves:
        key = _dedup_key(m)
        if key in seen:
            continue
        seen.add(key)
        out.append(m)
    return out


def _group_conflict(moves: Sequence[dict]) -> Optional[str]:
    """Return a conflict reason if the moves on one target disagree, else None.

    Only moves from >=2 distinct personas can conflict (a persona does not
    conflict with itself). Agreement (two confirms, two identical corrects/adds,
    two drops) is not a conflict. A confirm beside a correct is not a conflict
    either (v1.6.1 [H3]): the grounded correct applies and the confirm becomes a
    dissent (see ``_split_dissents``)."""
    personas = {m.get("persona_id") for m in moves}
    if len(personas) < 2:
        return None
    types = {m.get("move") for m in moves}
    if "drop" in types and (types - {"drop"}):
        return "a drop disagrees with another persona's move on the same target"
    for t in ("correct", "add"):
        contents = {_content(m) for m in moves if m.get("move") == t}
        if len(contents) > 1:
            return f"divergent {t} moves on the same target"
    return None


def _split_dissents(tgt: str, moves: Sequence[dict]):
    """v1.6.1 [H3]: on a non-conflicting target that carries a `correct`, every
    `confirm` from a persona that did not issue that correct is a dissent.
    Returns ``(moves_to_apply, dissents)``."""
    correctors = sorted({m.get("persona_id") for m in moves
                         if m.get("move") == "correct" and m.get("persona_id")})
    if not correctors:
        return list(moves), []
    keep: List[dict] = []
    dissents: List[dict] = []
    for m in moves:
        if m.get("move") == "confirm" and m.get("persona_id") not in correctors:
            dissents.append({"target": tgt, "confirm": m, "corrected_by": correctors})
        else:
            keep.append(m)
    return keep, dissents


def _line_span(citation: dict):
    """The 1-based line range an excerpt covers, or None without a `line`."""
    line = citation.get("line")
    if not isinstance(line, int):
        return None
    excerpt = citation.get("citation_excerpt") or ""
    return (line, line + excerpt.rstrip("\n").count("\n"))


def _same_passage(a: dict, b: dict) -> bool:
    """v1.6.1 [H4]: two add moves cite the same passage — same functional
    section, same document, and overlapping excerpt line ranges or
    byte-identical excerpt text. Keys on citation identity only (no NLP)."""
    if (a.get("section") or "").strip() != (b.get("section") or "").strip():
        return False
    ca, cb = a.get("citation"), b.get("citation")
    if not isinstance(ca, dict) or not isinstance(cb, dict):
        return False
    da = ca.get("document") or ca.get("document_sha256")
    db = cb.get("document") or cb.get("document_sha256")
    if not da or da != db:
        return False
    ea = (ca.get("citation_excerpt") or "").strip()
    eb = (cb.get("citation_excerpt") or "").strip()
    if ea and ea == eb:
        return True
    sa, sb = _line_span(ca), _line_span(cb)
    return bool(sa and sb and sa[0] <= sb[1] and sb[0] <= sa[1])


def _cluster_adds(moves: Sequence[dict]):
    """v1.6.1 [H4]: keep the first add of each same-passage cluster (input
    order), return ``(kept_moves, duplicates)``. Non-add moves pass through."""
    kept: List[dict] = []
    duplicates: List[dict] = []
    kept_adds: List[dict] = []
    for m in moves:
        if m.get("move") == "add":
            first = next((k for k in kept_adds if _same_passage(k, m)), None)
            if first is not None:
                duplicates.append({"move": m, "duplicate_of": first})
                continue
            kept_adds.append(m)
        kept.append(m)
    return kept, duplicates


def _apply_move(manifest: dict, move: dict) -> List[str]:
    """Apply one move. Returns the prose fields a `correct` left unreplaced
    (v1.6.1 [H2]); empty for every other move."""
    records = manifest.setdefault("records", [])
    mv = move.get("move")
    if mv == "add":
        records.append({
            "id": move.get("id") or f"REQ-ADD-{len(records) + 1:03d}",
            "functional_section": move.get("section") or "Uncategorized",
            "title": move.get("title", ""),
            "conditions_of_satisfaction": move.get("conditions_of_satisfaction", ""),
            "source_type": "agent-validation",   # provenance preserved (guard 2)
            # instruction 028 fix 2: backfill the cited FORMAL_DOC's tier (stamped
            # onto the grounded move by classify_move) so the synthesized REQ is
            # tier-complete like a derivation-produced REQ.
            "tier": move.get("tier"),
            "citation": move.get("citation"),
        })
    elif mv == "correct":
        for r in records:
            if r.get("id") == move.get("req_id"):
                # v1.6.1 [H2]: replace every claim-bearing prose field the move
                # supplies; list the ones the record carries but the move left
                # alone, because they may still state the wider claim.
                stale: List[str] = []
                for f in PROSE_FIELDS:
                    if move.get(f):
                        r[f] = move[f]
                    elif r.get(f):
                        stale.append(f)
                if stale:
                    r["needs_text_review"] = stale
                else:
                    r.pop("needs_text_review", None)
                r["source_type"] = "agent-validation"
                r["citation"] = move.get("citation")
                # v1.6.1 [H1]: backfill the cited document's tier, as `add` does
                # (instruction 028 fix 2). Without it a tier-3 REQ kept tier 3
                # and gained a citation block, which the gate FAILs.
                if move.get("tier") is not None:
                    r["tier"] = move["tier"]
                return stale
    elif mv == "drop":
        manifest["records"] = [r for r in records if r.get("id") != move.get("req_id")]
    # confirm: no structural change (records that a persona validated the REQ).
    return []


def merge_personas(grounded_by_persona: Sequence[dict], base_manifest: dict) -> MergeResult:
    """Merge each persona's grounded moves into one manifest.

    ``grounded_by_persona`` is a sequence of ``{"persona_id", "moves": [...]}``
    where every add/correct is already GROUNDED (slice 3) and confirm/drop are
    the ungated pass-through moves (guard 1 does not gate a removal/affirmation) —
    candidate moves are NOT passed here; they stay in the candidate bucket.
    Returns a MergeResult with
    the merged manifest (renumbered ONCE), the surfaced conflict set, the applied
    and held-out moves, the id remap, and the renumber call count (must be 1).
    """
    # Flatten to (persona-tagged) moves.
    all_moves: List[dict] = []
    for entry in grounded_by_persona:
        pid = entry.get("persona_id")
        for move in entry.get("moves", []):
            if move.get("move") not in _PERSONA_MOVES:
                # defer (operator-only) or unknown — never participates.
                continue
            m = dict(move)
            m.setdefault("persona_id", pid)
            all_moves.append(m)

    # Group by target for conflict detection (None-target adds never conflict).
    by_target: Dict[str, List[dict]] = {}
    solo: List[dict] = []
    for m in all_moves:
        tgt = _move_target(m)
        if tgt is None:
            solo.append(m)
        else:
            by_target.setdefault(tgt, []).append(m)

    conflicts: List[Conflict] = []
    held_out: List[dict] = []
    dissents: List[dict] = []
    to_apply: List[dict] = list(solo)
    for tgt, moves in by_target.items():
        reason = _group_conflict(moves)
        if reason:
            conflicts.append(Conflict(
                target=tgt, reason=reason, moves=moves,
                personas=sorted({m.get("persona_id") for m in moves if m.get("persona_id")}),
            ))
            held_out.extend(moves)   # surface, do NOT resolve — hold all of them out
        else:
            keep, group_dissents = _split_dissents(tgt, moves)
            to_apply.extend(keep)
            dissents.extend(group_dissents)

    # Collapse agreement — identical moves from different personas apply ONCE
    # (two blind personas proposing the same missing REQ is agreement, not two
    # duplicate REQ records — self-Council Panelist C).
    to_apply = _dedup(to_apply)
    # v1.6.1 [H4]: then collapse adds that cite the same passage.
    to_apply, duplicates = _cluster_adds(to_apply)

    # Apply the non-conflicting moves to the base manifest.
    manifest = base_manifest
    for m in to_apply:
        stale = _apply_move(manifest, m)
        if stale:
            m["needs_text_review"] = stale   # v1.6.1 [H2]: for the review summary

    # Exactly ONE terminal renumber over the merged manifest.
    remap = requirements_render.renumber_to_document_order(manifest)

    return MergeResult(
        manifest=manifest, conflicts=conflicts, applied=to_apply,
        held_out=held_out, remap=remap, renumber_calls=1,
        dissents=dissents, duplicates=duplicates,
    )
