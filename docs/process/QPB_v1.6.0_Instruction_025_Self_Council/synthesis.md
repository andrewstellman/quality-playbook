# Instruction 025 — operator-rescuable advisory floor: self-Council synthesis

**Terminal verdict: unanimous SHIP** across all three charters, zero FIX-REQUIRED.

This change **reverses a hardened security decision** (the sidecar rescues the
implementation floor only, never advisory) — deliberately, on the Fable review's
reasoning (Q2): the advisory floor was an unrescuable dead-end, and even the hard
signals we kept (CVE/GHSA id, advisory URL) will eventually false-floor a real spec
(any authoritative spec with a security-considerations section carries a CVE id).
The operator is already the trust anchor, so a rescue requiring them to read the
specific floor reason and record a content-keyed, reason-acknowledging confirmation
is *more* scrutiny than the dump that got the doc in — not a hole. Because it
reverses a hardened decision, a full 3-charter self-Council ran (each panelist in
its own worktree reset to `be212a2`, each running an adversarial driver and
mutation-biting).

## The mechanism
An operator-authored file `reference_docs/qpb_advisory_rescue.txt` (the same
human-only-config class as `qpb_promote.txt` — ingest reads it, never writes it; the
classifier / a persona / document content can never add to it). Each honored line is
`<path>  <document_sha256>  <reason being overridden>` (all three required — the
reason enforces acknowledgment). It threads as `advisory_rescues=[(path, sha256)]`
into `classify_documents`, content-keyed, applied to **both** the main classify and
the cache-guard so a legit rescue isn't re-floored — while a non-rescued advisory
doc still trips `RULE_ADVISORY` and its poisoned cache is discarded. A rescued doc is
**un-floored, not force-cited**: it classifies normally (Tier 4 default with no LLM
tier; Tier 1/2 only if tiered). Every rescue is disclosed (`advisory_rescued` /
`rescued_reason` in the manifest record + the `advisory-rescued` playback status +
interview + operator-authoring prose).

## Charters + verdicts

- **A — Human-only rescue authority (anti-poisoning core): SHIP.** The rescue
  authority is single-sourced from `_load_advisory_rescues` (the operator file) —
  grep confirms no writer, and the `rescued` flag is computed solely from `(rel_path,
  its-own-sha) in rescue_set`; no document content / classifier / persona / cached
  record can reach `advisory_rescues`. 12/12 adversarial attacks defended end-to-end:
  poisoned self-rescue via content fails; a poisoned prior manifest (forged
  `advisory_rescued`/tier-1) is discarded on cache-hit (the guard passes the operator
  rescue, never the cached flag). Both human-only guards are mutation-confirmed
  load-bearing.

- **B — Content-keyed binding + default-floor-intact: SHIP.** Exact `(path, own-sha)`
  match — no over-broad match (`a.md` ≠ `sub/a.md`/`a.md.bak`; sha prefix/superstring
  don't match); voids on a one-byte change; a rescue for A cannot promote B. Absent a
  rescue the hard floor still fires under a promote-all classifier — opt-in, no global
  loosening. The sha component is mutation-confirmed load-bearing; the sha is
  normalized (a copy-pasted uppercase sha still matches); the reason is required.

- **C — Disclosed + un-floor-not-force-cite + impl-path-unchanged + scope: SHIP.** A
  rescued doc with no LLM tier is `RULE_DEFAULT` Tier 4, not auto-Tier-1; a rescue on
  a non-advisory doc is a harmless no-op. The rescue is disclosed in the manifest,
  the playback, and both prose surfaces. The impl-floor sidecar rescue has no diff
  hunk and is orthogonal (`advisory_rescue` never rescues the impl floor). Only the 5
  sanctioned files are touched (NOT `quality_gate.py`, NOT `persona_grounding.py`);
  the new fields are additive (reproducibility/poison tests pass); the
  reason-acknowledgment is genuinely enforced. No over-claims.

## Design choice recorded: sidecar-file vs the ledger
The instruction offered two reusable operator-authored primitives (the sidecar's
human-only config; the confirmation ledger's `agent-validation` refusal). The build
used a **new operator-authored sidecar file** — the direct analog of the existing
impl-floor rescue, content-keyed and reason-acknowledging — because a per-doc,
content-keyed rescue is a config statement, not a durable irreproducible confirmation
(the ledger's shape). The human-only guarantee is identical to `qpb_promote.txt`
(the classifier can never add to it), which Panelist A confirmed single-sourced and
un-forgeable. `quality_gate.py` was not touched (the instruction scopes disclosure to
the manifest + interview).

## Non-blocking observation (all three panelists, out of scope)
Once an operator **legitimately** rescues a doc, it becomes non-floored and its cached
tier is then trusted like any non-floored doc (the pre-existing instruction-011
cache-trust model). This requires the operator's explicit rescue of that exact
content and does not forge the rescue authority itself, which remains
operator-file-only. Not introduced by this change; not FIX-REQUIRED.

## Verification
Full suite **2777 / 0 / 14**, Python 3.14.6. Reviewed commit `be212a2`.

**Terminal verdict: SHIP.** The advisory floor is now operator-rescuable — human-only,
content-keyed, reason-acknowledging, un-floor-not-force-cite, disclosed — closing the
unrescuable dead-end while keeping the anti-poisoning property fully intact.
