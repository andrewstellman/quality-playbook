"""v1.6.0 — the canonical terminal E.6 renumber (Phase E.6, instruction 007).

Instruction 007 established the E.6 rule: after all interview moves, renumber the
requirements to **strict document order** (section order, then within section)
exactly once, and update the id-carrying cross-references so traceability stays
intact. Before this module the logic lived only inline in the 007 fixture helper;
Feature H's Guard 3 merge (instruction 016) needs the *same* renumber after the
multi-persona merge, so it is extracted here as the single canonical
implementation both call — "reuse, don't reimplement" (the gate's sequential-ID
check, `quality_gate` Check 1 / C-2, verifies the result).

Stdlib-only.
"""

from __future__ import annotations

from typing import Dict, List, Optional


def document_order(records: List[dict]) -> List[dict]:
    """Order records in document order — section first-appearance, then within
    section (stable). Section *order* is decided upstream (the organizing-
    principle step, E.5); this only groups by it before the renumber."""
    seen: List[Optional[str]] = []
    for r in records:
        sec = r.get("functional_section")
        if sec not in seen:
            seen.append(sec)
    ordered: List[dict] = []
    for sec in seen:
        ordered += [r for r in records if r.get("functional_section") == sec]
    return ordered


def renumber_to_document_order(manifest: dict) -> Dict[str, str]:
    """Renumber ``manifest['records']`` to REQ-001..NNN in document order, ONCE.

    Reassigns REQ ids in place, reorders ``records`` to document order, and
    returns the ``{old_id: new_id}`` remap for any id that changed. Also updates
    id-carrying cross-references that live *inside the requirements manifest*
    (a REQ record's ``requirements``/``related_requirements`` REQ→REQ lists, if
    present); UC/BUG manifests are separate files and their REQ references are
    remapped by the caller via the returned remap (traceability contract).
    """
    records = manifest.get("records", [])
    ordered = document_order(records)
    remap: Dict[str, str] = {}
    for i, r in enumerate(ordered, start=1):
        new_id = f"REQ-{i:03d}"
        old_id = r.get("id")
        if old_id and old_id != new_id:
            remap[old_id] = new_id
        r["id"] = new_id
    manifest["records"] = ordered
    if remap:
        _remap_cross_refs(ordered, remap)
    return remap


def _remap_cross_refs(records: List[dict], remap: Dict[str, str]) -> None:
    """Update REQ→REQ id references carried inside REQ records."""
    for r in records:
        for key in ("requirements", "related_requirements"):
            refs = r.get(key)
            if isinstance(refs, list):
                r[key] = [remap.get(x, x) for x in refs]


def apply_remap(refs, remap: Dict[str, str]):
    """Remap a list of REQ ids (for a caller updating UC/BUG cross-references)."""
    return [remap.get(x, x) for x in refs]
