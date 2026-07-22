"""v1.6.0 Feature H slice 3 (Design §8b Guard 1) — grounding + candidate bucket.

Slice 2's personas emit RAW candidate diff-sets; nothing yet decides which moves
are trustworthy enough to auto-apply. Guard 1 is that discipline — the
false-positive floor of the whole feature. For each `add`/`correct` move it
decides **grounded** (safe for the later merge + auto-apply) vs **candidate**
(surfaced for human attention, never written in as a REQ), by a two-part test
plus an injection-resistance rule:

- **(a) Cited + byte-verified.** The move must cite a document that resolves to a
  Tier-1/2 ``FORMAL_DOC`` record, and the excerpt must byte-verify against that
  source through the EXISTING ``citation_verifier`` (reused, never forked — the
  same path the gate re-invokes). No citation, or a citation that does not
  byte-verify, is **candidate**.
- **(b) Fit-for-this-system.** The move must justify why *this* system needs the
  requirement, not merely that some document mentions it. Absent a this-system
  justification the move is **candidate** ("a serializer should handle circular
  refs" is a candidate unless the docs make it this library's contract).
- **Injection resistance (the security part).** Grounding must not rest *solely*
  on content the ingested document controls. A move whose support is
  injection-shaped (imperatives to the agent, self-authorizing tier claims) is
  **candidate-only, never grounded — even when that text byte-verifies**, because
  byte-verification proves the text exists, not that it is a legitimate contract.
  This closes the poisoning path at the grounding layer (Feature G's floor closes
  it at tiering).

This slice CLASSIFIES only. It does not merge (Guard 3, slice 4) or apply (Guard
4, slice 5). A grounded move retains its ``agent-validation`` provenance (Guard 2)
and byte-verified citation, ready for those slices. Stdlib-only bar the two
sibling QPB modules it composes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence

# Sibling QPB modules — path-loaded the same way reference_docs_ingest loads its
# siblings, so `-m bin.*` and bundled layouts both resolve them.
import importlib.util as _ilu
import sys as _sys

_HERE = Path(__file__).resolve().parent


def _sibling(mod_name: str, file_name: str):
    try:
        return __import__(f"bin.{mod_name}", fromlist=[mod_name])
    except ImportError:
        spec = _ilu.spec_from_file_location(
            f"_qpb_{mod_name}_via_persona_grounding", _HERE / file_name)
        if spec is None or spec.loader is None:
            raise ImportError(f"persona_grounding: cannot resolve {file_name}")
        mod = _ilu.module_from_spec(spec)
        _sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        return mod


citation_verifier = _sibling("citation_verifier", "citation_verifier.py")
doc_classification = _sibling("doc_classification", "doc_classification.py")

GROUNDED = "grounded"
CANDIDATE = "candidate"

# The moves Guard 1 gates. `confirm` rests on docs/intent (not this validator),
# `drop` is a removal, `defer` is operator-only.
GATED_MOVES = ("add", "correct")


@dataclass
class Classification:
    verdict: str                      # GROUNDED or CANDIDATE
    reason: str                       # why (esp. why it fell short, for candidates)
    persona_id: Optional[str] = None
    move: dict = field(default_factory=dict)
    source_type: Optional[str] = None  # 'agent-validation' on grounded moves

    @property
    def is_grounded(self) -> bool:
        return self.verdict == GROUNDED


def _resolve_formal_doc(citation: dict, formal_docs: Sequence[dict]) -> Optional[dict]:
    """Match a citation to a FORMAL_DOC record by document path (or sha256)."""
    doc_ref = citation.get("document")
    sha = citation.get("document_sha256")
    for rec in formal_docs:
        if doc_ref and rec.get("source_path") == doc_ref:
            return rec
        if sha and rec.get("document_sha256") == sha:
            return rec
    return None


def classify_move(
    move: dict,
    formal_docs: Sequence[dict],
    root: Path,
    *,
    persona_id: Optional[str] = None,
) -> Optional[Classification]:
    """Classify one `add`/`correct` move as grounded or candidate.

    Returns None for a non-gated move (confirm/correct... only add/correct are
    gated here; confirm/drop pass through untouched by Guard 1).
    """
    def cand(reason: str) -> Classification:
        return Classification(CANDIDATE, reason, persona_id, move)

    if move.get("move") not in GATED_MOVES:
        return None

    citation = move.get("citation")
    # (a) cited
    if not isinstance(citation, dict) or not (citation.get("citation_excerpt") or "").strip():
        return cand("no citation (or empty excerpt)")

    doc = _resolve_formal_doc(citation, formal_docs)
    if doc is None:
        return cand("citation does not resolve to a FORMAL_DOC record")
    if doc.get("tier") not in (1, 2):
        return cand(f"cited doc is Tier {doc.get('tier')}, not a Tier-1/2 authoritative contract")

    # (a) byte-verified — REUSE the existing citation_verifier, do not fork it.
    result = citation_verifier.verify_citation(citation, doc, Path(root))
    if not getattr(result, "ok", False):
        return cand(f"citation failed byte-verify ({getattr(result, 'error_code', 'error')})")

    # Injection resistance — grounding must not rest solely on doc-controlled,
    # injection-shaped content, even though it byte-verifies.
    excerpt = citation.get("citation_excerpt", "")
    inj = doc_classification.injection_signature(excerpt)
    if inj:
        return cand(f"support is injection-shaped, not a legitimate contract ({inj})")

    # (b) fit-for-this-system — a this-system justification distinct from a bare
    # "some doc mentions it".
    if not (move.get("system_justification") or "").strip():
        return cand("no fit-for-this-system justification (why THIS system needs it)")

    return Classification(
        GROUNDED, "cited + byte-verified + fit-for-this-system",
        persona_id, move, source_type="agent-validation",
    )


@dataclass
class GroundingResult:
    grounded: List[Classification] = field(default_factory=list)
    candidates: List[Classification] = field(default_factory=list)

    @property
    def grounded_add_count(self) -> int:
        return sum(1 for c in self.grounded if c.move.get("move") == "add")


def classify_diff_set(
    diff_set: dict,
    formal_docs: Sequence[dict],
    root: Path,
) -> GroundingResult:
    """Classify every gated move in one persona's diff-set.

    Grounded moves retain their `agent-validation` provenance + byte-verified
    citation (ready for slices 4-5); candidates go to the human-attention bucket
    carrying the persona, the move, and WHY they fell short. `confirm`/`drop`
    moves are not gated here and are not classified.
    """
    persona_id = diff_set.get("persona_id")
    result = GroundingResult()
    for move in diff_set.get("moves", []):
        c = classify_move(move, formal_docs, root, persona_id=persona_id)
        if c is None:
            continue
        (result.grounded if c.is_grounded else result.candidates).append(c)
    return result


def candidate_bucket(results: Sequence[GroundingResult]) -> List[dict]:
    """The first-class candidate/uncertain findings set for human attention.

    Distinct from grounded moves; never applied as a REQ. Each entry: the
    persona, the move (with its interview context), and why it fell short.
    """
    bucket: List[dict] = []
    for r in results:
        for c in r.candidates:
            bucket.append({
                "persona_id": c.persona_id,
                "move": c.move.get("move"),
                "req_id": c.move.get("req_id"),
                "section": c.move.get("section"),
                "reason": c.move.get("reason"),
                "shortfall": c.reason,
            })
    return bucket
