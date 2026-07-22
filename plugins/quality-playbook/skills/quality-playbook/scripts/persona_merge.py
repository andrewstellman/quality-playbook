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


def _group_conflict(moves: Sequence[dict]) -> Optional[str]:
    """Return a conflict reason if the moves on one target disagree, else None.

    Only moves from >=2 distinct personas can conflict (a persona does not
    conflict with itself). Agreement (two confirms, two identical corrects/adds,
    two drops) is not a conflict."""
    personas = {m.get("persona_id") for m in moves}
    if len(personas) < 2:
        return None
    types = {m.get("move") for m in moves}
    if "drop" in types and (types - {"drop"}):
        return "a drop disagrees with another persona's move on the same target"
    if "confirm" in types and ("correct" in types):
        return "one persona confirms the REQ while another corrects it"
    for t in ("correct", "add"):
        contents = {_content(m) for m in moves if m.get("move") == t}
        if len(contents) > 1:
            return f"divergent {t} moves on the same target"
    return None


def _apply_move(manifest: dict, move: dict) -> None:
    records = manifest.setdefault("records", [])
    mv = move.get("move")
    if mv == "add":
        records.append({
            "id": move.get("id") or f"REQ-ADD-{len(records) + 1:03d}",
            "functional_section": move.get("section") or "Uncategorized",
            "title": move.get("title", ""),
            "conditions_of_satisfaction": move.get("conditions_of_satisfaction", ""),
            "source_type": "agent-validation",   # provenance preserved (guard 2)
            "citation": move.get("citation"),
        })
    elif mv == "correct":
        for r in records:
            if r.get("id") == move.get("req_id"):
                if move.get("conditions_of_satisfaction"):
                    r["conditions_of_satisfaction"] = move["conditions_of_satisfaction"]
                if move.get("title"):
                    r["title"] = move["title"]
                r["source_type"] = "agent-validation"
                r["citation"] = move.get("citation")
                break
    elif mv == "drop":
        manifest["records"] = [r for r in records if r.get("id") != move.get("req_id")]
    # confirm: no structural change (records that a persona validated the REQ).


def merge_personas(grounded_by_persona: Sequence[dict], base_manifest: dict) -> MergeResult:
    """Merge each persona's grounded moves into one manifest.

    ``grounded_by_persona`` is a sequence of ``{"persona_id", "moves": [...]}``
    where every move is already GROUNDED (slice 3) — candidate moves are not
    passed here; they stay in the candidate bucket. Returns a MergeResult with
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
            to_apply.extend(moves)

    # Apply the non-conflicting moves to the base manifest.
    manifest = base_manifest
    for m in to_apply:
        _apply_move(manifest, m)

    # Exactly ONE terminal renumber over the merged manifest.
    remap = requirements_render.renumber_to_document_order(manifest)

    return MergeResult(
        manifest=manifest, conflicts=conflicts, applied=to_apply,
        held_out=held_out, remap=remap, renumber_calls=1,
    )
