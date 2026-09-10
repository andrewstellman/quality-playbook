# Instruction 025 — v1.6.0 Feature G: make the advisory floor operator-rescuable via the ledger

Instructions 023–024 shrank the floor to hard signals (CVE/GHSA ids, advisory URLs) and made classification honest. But the external review (Fable Q2) identified the *deeper* defect the virtio incident exposed: **the advisory floor is an unrescuable dead-end.** Even the hard signals we kept will eventually false-floor a legitimate spec — *any* authoritative spec with a security-considerations section contains a CVE id. Today there is no way for the operator to say "I've read this, it's the real spec, cite it." That's the disease; the density heuristic was just the symptom.

The fix reverses an earlier security decision (the sidecar rescues the implementation floor only, never advisory) — deliberately, on the review's reasoning: **the operator is already the trust anchor** (they supplied the dump), so a rescue that requires them to read the specific floor reason and record an explicit, durable confirmation is *more* scrutiny than the dump that got the doc in, not a hole. This closes the dead-end while keeping the anti-poisoning property intact.

## Read first — these ARE the spec
- `~/Documents/AI-Driven Development/Quality Playbook/Reviews/QPB_v1.6.0_Simplification_Fable_Review_Response.md` — **Q2** (the rescuable-ledger reasoning) and the disposition-table row "Advisory-floor override policy → rescuable-with-ledger — policy reversal."
- `plugins/quality-playbook/skills/quality-playbook/scripts/doc_classification.py` — the advisory floor + `_UNRESCUABLE_FLOOR_RULES` (:75-77) + `classify_document`'s `sidecar_promote` path (the existing impl-floor rescue). The advisory floor must become rescuable by an operator-authored, content-keyed confirmation.
- `plugins/quality-playbook/skills/quality-playbook/scripts/reference_docs_ingest.py` — `_load_sidecar` (:522-536) (the operator-authored `qpb_promote.txt`, writable only by the human) and how `classify_reference_docs` threads promotion.
- `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py` — the append-only operator-confirmation ledger checks (`check_operator_confirmations_append_only`, ~:8087-8238) and `run_state_lib.append_confirmation`, which **already refuses any `agent-validation` record** (Guard 2, instruction 012) — that write-restriction is the security primitive this reuses: the rescue ledger must be human-only by the same mechanism.
- `ai_context/DEVELOPMENT_PROCESS.md`.

## Scope
The rescuable-advisory-floor mechanism only. **Out of scope (later):** Feature H directive-narrowing (026); render labeled-slots (027).

## The behavior to build

1. **An operator-authored advisory-floor rescue.** The operator can promote a *specific* advisory-floored document past the advisory floor. The record of that decision is:
   - **Operator-authored only** — writable exclusively by the human, never by the classifier, a persona, or ingested document content. Reuse the existing operator-authored surfaces: the sidecar (`qpb_promote.txt`) is already human-only config, and the confirmation ledger already **refuses `agent-validation`** writes (Guard 2). A poisoned document must be unable to rescue itself — this is the whole point.
   - **Content-keyed** — the rescue names the doc by its `document_sha256`, so it applies to exactly that content. If the document changes, the rescue no longer applies (a swapped-in advisory can't inherit a rescue).
   - **Reason-acknowledging** — the rescue records *which floor reason* the operator is overriding (the specific advisory signal), so the decision is auditable, not a blanket bypass.
2. **Un-floor, don't force-cite.** A rescued doc is lifted *past the advisory floor* so classification can proceed — it does not auto-become Tier 1; the classifier/operator then tiers it normally. (The rescue removes the barrier; it doesn't fabricate authority.)
3. **Disclosed.** Every advisory-floor rescue is surfaced in the classification manifest and the interview Stage-1 playback (extending instruction 024's playback) — *"advisory floor on `<doc>` overridden by operator; reason: `<floor reason>`"* — so the override is visible and reviewable, never silent.
4. **The implementation floor rescue is unchanged** (it already works). This instruction *adds* advisory-floor rescue under the same operator-authored guarantees; it does not weaken the impl-floor path.

## The security invariants the Council must confirm (this reverses a hardened decision)
- **Human-only:** no classifier, persona, or document content can create or influence a rescue. Mutation-bite: an ingested doc containing "promote me / rescue this" text, and an `agent-validation`-shaped ledger entry, both fail to rescue.
- **Per-doc, content-keyed:** a rescue for doc A cannot promote doc B; editing a rescued doc voids its rescue (sha mismatch).
- **Reason-scoped + disclosed:** the rescue records the overridden floor reason and appears in the manifest + interview.
- **The hard floor still fires by default:** absent an explicit operator rescue, a CVE/URL doc still floors to Tier 4 (the rescue is opt-in per doc, never a global loosening).

## Acceptance oracle (mutation-bite the security ones)
1. **Rescue works:** an operator rescue entry (content-keyed to a CVE-bearing legitimate spec) lifts it past the advisory floor; it then classifies normally (citable if the classifier tiers it 1/2).
2. **Poisoned self-rescue fails:** a document whose *content* asks to be promoted/rescued is NOT rescued; an `agent-validation`/non-operator ledger entry is NOT honored.
3. **Content-keyed:** a rescue for doc A does not promote a different doc B; mutating a rescued doc's bytes voids the rescue.
4. **Default floor intact:** without a rescue, CVE/URL docs still floor (instruction 023/024 behavior unchanged).
5. **Disclosed:** the rescue appears in the manifest + interview Stage-1 playback with the overridden reason.
6. **Impl-floor rescue unchanged.**
7. Full suite green.

## Fixture discipline
Do NOT hand-edit golden fixtures. New fixtures (a valid rescue, the poisoned-self-rescue rejection, content-key voiding, the disclosure) are expected.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight; local commits only; **never push/merge**. Touches QPB source (doc_classification / ingest / quality_gate ledger).
- **Full 3-charter self-Council per §13 — this reverses a hardened security decision, no shortcut.** Charters, each mutating panelist its own worktree:
  - **(a) Human-only rescue authority:** prove no classifier/persona/document-content path can create or influence a rescue; the ledger write-restriction (Guard 2) and sidecar operator-authorship hold; the poisoned-self-rescue fixture lands nothing. This is the anti-poisoning core — scrutinize hardest.
  - **(b) Content-keyed + default-floor-intact:** a rescue is bound to one doc's bytes and voids on change; absent a rescue the hard floor still fires; no global loosening.
  - **(c) Disclosed + un-floor-not-force-cite + impl-path unchanged:** every rescue is surfaced; a rescue removes the barrier without fabricating Tier-1; the impl-floor rescue is untouched.
  - Artifacts under `RUNNER_ROOT/reviews/025_self_council/` + tracked copy under `docs/process/QPB_v1.6.0_Instruction_025_Self_Council/`.
- Verify the full suite; report counts + Python version.
- Output `outputs/025-feature-g-rescuable-advisory-floor.md`: the rescue mechanism + where the operator authors it; the human-only + content-keyed mutation proofs; the disclosure; confirmation the default floor and impl-path are unchanged; and the remaining follow-ups (Feature H 026, render 027).
