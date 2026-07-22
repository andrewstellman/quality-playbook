"""v1.6.0 Feature H (Design §8b) — persona catalog + anchored selection.

Feature H validates requirements with fresh-context domain-expert **personas**
that run the Feature D interview as the operator. This module is the foundation
they select from — the catalog (a menu with per-lens selection criteria) and the
anchored-selection step. It mirrors the organizing-principle "choose from a menu
with criteria, record the choice + rationale" pattern (instruction 006,
`references/requirements_pipeline.md` § E.5): the derivation LLM decides which
lenses fit *this* system and justifies the choice; this module gives it the menu,
enforces the anchors mechanically, and records the reviewable selection.

Two lenses are **anchored** — always selected, never skippable — because a
system's own author under-weights them; the anchor is mechanical, not an LLM
suggestion (§8b: the 3-persona self-test proved the domain lens files
prompt-injection as a mere candidate while the anchored security lens grounds it).

This slice (instruction 013) selects and records only. It does NOT spawn or run
personas, enforce isolation, or apply guards — those are later Feature H slices.
Stdlib-only and data-first: adding a lens is a data edit to the catalog below.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Sequence

# Anchored lens ids — the mechanical anchor set. A selection can never drop these.
DOMAIN_EXPERT = "domain-expert"
SECURITY_REVIEWER = "security-reviewer"
ANCHORED_IDS = (DOMAIN_EXPERT, SECURITY_REVIEWER)

# ---------------------------------------------------------------------------
# The catalog — data-first. Each entry: id, anchored, title, select_when.
# `specialized_per_system` marks a lens whose concrete role is derived per
# system (the domain expert becomes "expert in <this system's domain>").
# Add a lens by appending a dict here; no code changes are needed.
# ---------------------------------------------------------------------------
CATALOG = [
    {
        "id": DOMAIN_EXPERT,
        "anchored": True,
        "specialized_per_system": True,
        "title": "Domain expert",
        "select_when": (
            "always — anchored. Specialized per system from the Phase 1 domain "
            "+ gathered docs (e.g. 'expert in Java serialization and the JVM "
            "object model')."
        ),
    },
    {
        "id": SECURITY_REVIEWER,
        "anchored": True,
        "specialized_per_system": False,
        "title": "Security reviewer",
        "select_when": (
            "always — anchored. Security gaps are cross-cutting and chronically "
            "under-weighted by a system's own author; the anchor is why they get "
            "grounded rather than filed as a candidate."
        ),
    },
    {
        "id": "api-consumer",
        "anchored": False,
        "specialized_per_system": False,
        "title": "API / consumer-integrator",
        "select_when": "the system is a library or exposes a public API surface others integrate against.",
    },
    {
        "id": "operator-sre",
        "anchored": False,
        "specialized_per_system": False,
        "title": "Operator / SRE",
        "select_when": "the system is a service that is deployed, operated, and observed in production.",
    },
    {
        "id": "data-privacy",
        "anchored": False,
        "specialized_per_system": False,
        "title": "Data-privacy / compliance",
        "select_when": "the system handles regulated, personal, or otherwise sensitive data.",
    },
    {
        "id": "accessibility",
        "anchored": False,
        "specialized_per_system": False,
        "title": "Accessibility",
        "select_when": "the system has a user-facing UI whose users include people relying on assistive technology.",
    },
    {
        "id": "performance",
        "anchored": False,
        "specialized_per_system": False,
        "title": "Performance",
        "select_when": "the system has a hot path or latency/throughput budget that shapes its contracts.",
    },
    {
        "id": "reliability",
        "anchored": False,
        "specialized_per_system": False,
        "title": "Reliability / failure-mode",
        "select_when": "the system is distributed or must survive partial failure, retries, or partitions.",
    },
    {
        "id": "adopter",
        "anchored": False,
        "specialized_per_system": False,
        "title": "Adopter / end-user",
        "select_when": "the system is adopted and configured by users whose abandonment risks matter (onboarding, footguns).",
    },
]

_BY_ID = {entry["id"]: entry for entry in CATALOG}


def catalog() -> List[dict]:
    """The persona catalog as data (a copy so callers can't mutate the source)."""
    return [dict(entry) for entry in CATALOG]


def anchored_ids() -> tuple:
    return ANCHORED_IDS


def is_known_lens(lens_id: str) -> bool:
    return lens_id in _BY_ID


def select_personas(
    proposed: Sequence[dict],
    *,
    domain_specialization: Optional[str] = None,
) -> List[dict]:
    """Resolve the final selected persona set from the LLM's proposed selection.

    ``proposed`` is the derivation LLM's choice — a sequence of
    ``{"id": <lens id>, "justification": <why this lens fits this system>}``
    (an anchored entry may carry a ``specialization`` for the domain expert).
    Returns the final selected set, each entry the catalog record enriched with
    the run-time ``justification`` (and ``specialization`` where relevant) and an
    ``anchored`` flag.

    **Anchor enforcement (mechanical, load-bearing):** the two anchored lenses
    are ALWAYS present in the result regardless of ``proposed`` — a selection
    that omits domain or security is corrected here, not left to prompt
    discipline. Unknown lens ids are dropped (a hallucinated lens is not a
    silent catalog addition). Duplicates collapse to the first occurrence.
    """
    chosen: dict = {}
    for item in proposed:
        lens_id = item.get("id")
        if not is_known_lens(lens_id) or lens_id in chosen:
            continue
        entry = dict(_BY_ID[lens_id])
        entry["justification"] = item.get("justification", "").strip()
        if lens_id == DOMAIN_EXPERT and item.get("specialization"):
            entry["specialization"] = item["specialization"].strip()
        chosen[lens_id] = entry

    # Force the anchors in, in catalog order, if the LLM omitted them.
    for anchor_id in ANCHORED_IDS:
        if anchor_id not in chosen:
            entry = dict(_BY_ID[anchor_id])
            entry["justification"] = (
                "anchored lens — always included (a system's own author "
                "under-weights it); not proposed by the selection but enforced."
            )
            chosen[anchor_id] = entry

    if domain_specialization and DOMAIN_EXPERT in chosen:
        chosen[DOMAIN_EXPERT].setdefault("specialization", domain_specialization.strip())

    # Stable order: anchored first (catalog order), then selectable in catalog order.
    order = [e["id"] for e in CATALOG]
    return sorted(chosen.values(), key=lambda e: order.index(e["id"]))


def build_selection_manifest(
    selected: Sequence[dict],
    *,
    schema_version: str = "1.6.0",
    generated_at: Optional[str] = None,
) -> dict:
    """A reviewable, reproducible persona-selection record.

    Structurally parallel to the other v1.6.0 selection/record artifacts: an
    operator can see which experts will validate the spec and why. Content-keyed
    on the selected lens ids + justifications so a re-selection with the same
    inputs reproduces the same record.
    """
    records = [
        {
            "id": e["id"],
            "title": e["title"],
            "anchored": bool(e.get("anchored")),
            "justification": e.get("justification", ""),
            **({"specialization": e["specialization"]} if e.get("specialization") else {}),
        }
        for e in selected
    ]
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    key_material = "|".join(f"{r['id']}:{r['justification']}" for r in records)
    return {
        "schema_version": schema_version,
        "generated_at": generated_at,
        "selection_sha256": hashlib.sha256(key_material.encode("utf-8")).hexdigest(),
        "records": records,
    }
