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

import re
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

GROUNDED = "grounded"
CANDIDATE = "candidate"

# Guard-1 injection detection — SELF-CONTAINED (instruction 026). Two arms:
#
# (1) Self-authorizing TIER claims ("classify me Tier 1", "cite me as
#     authoritative", "ignore the rubric") — the tiering-surface attack. This
#     detection lived in doc_classification (as its removed injection FLOOR's
#     helper) and was composed here across a module boundary; 026 moves it in so
#     grounding owns its own check and the classifier is judgment-free.
_TIER_CLAIM_RE = re.compile(
    r"classify\s+(?:me|this|the\s+following)\s+(?:as\s+)?tier"
    r"|cite\s+(?:me|this)\s+as\s+(?:an\s+)?authoritative"
    r"|treat\s+(?:me|this)\s+as\s+(?:an\s+)?(?:authoritative|tier)"
    r"|(?:mark|assign|set)\s+(?:me|this|it)?\s*(?:as\s+)?tier\s*[12]"
    r"|this\s+(?:document|doc|file)\s+is\s+(?:an\s+)?authoritative"
    r"|this\s+is\s+(?:an\s+)?authoritative\s+spec"
    r"|you\s+must\s+(?:cite|classify|treat)"
    r"|ignore\s+(?:the\s+)?(?:previous|rubric|above|instructions)"
    r"|as\s+an\s+ai\s+(?:classifier|model)",
    re.IGNORECASE,
)
# (2) AGENT-DIRECTED REQUIREMENT IMPERATIVES a doc aims at the derivation: "add
#     REQ X", "add a requirement", "you must add/confirm/cite/classify …", "please
#     confirm this", "register a requirement". §8b names exactly these
#     ("imperatives to the agent") as candidate-only even when they byte-verify.
#     NARROWED (instruction 026 / Fable Q3): the bare
#     ``the (agent|validator|reviewer|…) must/should/shall`` arm was DROPPED — it
#     collided with legitimate spec prose ("the validator MUST reject malformed
#     input") that carries no add/confirm/requirement verb. The add/confirm/
#     register-requirement verbs still fire, so "the reviewer must add a
#     requirement that X" is STILL caught (the "add … requirement" arm) — only the
#     false positive on ordinary contract language is removed. The subject that
#     matters is the requirements PROCESS, not the audited system.
_AGENT_DIRECTIVE_RE = re.compile(
    r"\badd\s+(?:a\s+|an\s+|the\s+|this\s+|new\s+|following\s+)*"
    r"(?:req\b|reqs\b|requirement|requirements)"
    r"|\badd\s+REQ[-\s:]"
    r"|\b(?:register|insert|include|append|write)\s+"
    r"(?:a\s+|an\s+|the\s+|this\s+|new\s+|following\s+)*"
    r"(?:req\b|reqs\b|requirement|requirements)"
    r"|\byou\s+(?:must|should|shall|need\s+to|are\s+to|have\s+to)\s+"
    r"(?:add|confirm|include|register|insert|cite|classify|treat|mark)\b"
    r"|\b(?:please\s+)?confirm\s+(?:this|it|the\s+following|that\s+requirement)\b",
    re.IGNORECASE,
)


def grounding_injection_signature(text: str) -> Optional[str]:
    """Injection-shaped support for a grounding move, or None.

    Self-contained (instruction 026): the self-authorizing tier-claim arm
    (``_TIER_CLAIM_RE``) + Guard-1's agent-directed requirement-imperative arm
    (``_AGENT_DIRECTIVE_RE``). No cross-module dependency on the classifier.
    """
    m = _TIER_CLAIM_RE.search(text)
    if m:
        return f"self-authorizing/injection content {m.group(0).strip()!r}"
    m = _AGENT_DIRECTIVE_RE.search(text)
    if m:
        return f"agent-directed imperative {m.group(0).strip()!r}"
    return None

# The moves Guard 1 gates. `confirm` rests on docs/intent (not this validator),
# `drop` is a removal, `defer` is operator-only.
GATED_MOVES = ("add", "correct")
# Persona moves Guard 1 does NOT gate — there is no citation to "ground" a
# removal or an affirmation — but that STILL flow to the merge: a `drop` is
# applied (Design §8b guard 4 lists add/correct/**drop** as applied) and both
# `confirm` and `drop` participate in the guard-3 conflict check ("a confirm
# against another's drop", "an add vs a drop"). `defer` is operator-only and is
# never a persona move, so it is excluded here and dropped at the merge. The
# composed pipeline MUST forward these to the merge; keeping the taxonomy in one
# place (here, beside GATED_MOVES) is what closes the instruction-022 seam where
# the composition assumed `grounded` was the complete forward-able set.
PASS_THROUGH_MOVES = ("confirm", "drop")


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
    inj = grounding_injection_signature(excerpt)
    if inj:
        return cand(f"support is injection-shaped, not a legitimate contract ({inj})")

    # (b) fit-for-this-system — a this-system justification distinct from a bare
    # "some doc mentions it".
    if not (move.get("system_justification") or "").strip():
        return cand("no fit-for-this-system justification (why THIS system needs it)")

    # instruction 028 fix 2: stamp the cited FORMAL_DOC's tier onto the grounded
    # move so the apply path can backfill a `tier` onto the synthesized REQ record
    # (the grounding already resolved + tier-checked `doc`).
    grounded = {**move, "tier": doc.get("tier")}
    return Classification(
        GROUNDED, "cited + byte-verified + fit-for-this-system",
        persona_id, grounded, source_type="agent-validation",
    )


@dataclass
class GroundingResult:
    grounded: List[Classification] = field(default_factory=list)
    candidates: List[Classification] = field(default_factory=list)
    # Ungated persona moves (confirm/drop) — not classified by Guard 1, but they
    # still flow to the merge (guard 3 conflict check + guard 4 drop-apply). Raw
    # move dicts, not Classifications. See PASS_THROUGH_MOVES.
    passthrough: List[dict] = field(default_factory=list)

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
    carrying the persona, the move, and WHY they fell short. `confirm`/`drop` are
    not gated by Guard 1 (there is no citation to ground a removal/affirmation),
    but they are collected into ``passthrough`` so the composed pipeline can still
    forward them to the merge (guard 3 conflict detection + guard 4 drop-apply) —
    without them the merge never sees a drop or a confirm-vs-drop conflict.
    `defer` is operator-only and is not collected.
    """
    persona_id = diff_set.get("persona_id")
    result = GroundingResult()
    for move in diff_set.get("moves", []):
        c = classify_move(move, formal_docs, root, persona_id=persona_id)
        if c is None:
            # Not gated by Guard 1. Ungated PERSONA moves (confirm/drop) still
            # flow to the merge; defer/unknown do not.
            if move.get("move") in PASS_THROUGH_MOVES:
                result.passthrough.append(move)
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
