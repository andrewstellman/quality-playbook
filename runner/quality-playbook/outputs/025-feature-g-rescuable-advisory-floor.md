# Output for 025-feature-g-rescuable-advisory-floor.md
**Status:** completed

## What this instruction was
Fix the *deeper* defect the virtio incident exposed (Fable Q2): the advisory floor
was an **unrescuable dead-end**. Even the hard signals 023–024 kept (CVE/GHSA id,
advisory URL) will eventually false-floor a legitimate spec — any authoritative spec
with a security-considerations section carries a CVE id — with no way for the
operator to say "I've read this, it's the real spec, cite it." This **reverses** the
earlier hardened decision (the sidecar rescues the impl floor only, never advisory),
deliberately, on the review's reasoning: the operator is already the trust anchor.

## Terminal verdict: unanimous SHIP (0 FIX-REQUIRED)
| Charter | Verdict |
|---------|---------|
| A — Human-only rescue authority (anti-poisoning core) | **SHIP** |
| B — Content-keyed binding + default-floor-intact | **SHIP** |
| C — Disclosed + un-floor-not-force-cite + impl unchanged + scope | **SHIP** |

Each panelist ran an adversarial driver against the reviewed commit and mutation-bit
the security-critical properties (Panelist A defended 12/12 attacks).

## The rescue mechanism + where the operator authors it
A **new operator-authored file** `reference_docs/qpb_advisory_rescue.txt` — the same
human-only-config class as `qpb_promote.txt` (ingest reads it, never writes it; the
classifier / a persona / document content can never add to it). Each honored line is
**content-keyed and reason-acknowledging**:
```
<target-relative-path>  <document_sha256>  <the advisory reason being overridden>
```
The operator copies the `document_sha256` + reason from the doc's record in
`quality/classification_manifest.json` (a line missing any of the three is ignored —
the acknowledgment is mandatory). Threaded via `reference_docs_ingest._load_advisory_
rescues` → `classify_reference_docs` → `doc_classification.classify_documents(
advisory_rescues=[(path, sha256)])`, applied per-doc to both the main classify and
the cache-guard.

**Why a sidecar file, not the ledger:** the instruction offered both operator-authored
primitives. A per-doc, content-keyed rescue is a config statement (the sidecar's
shape), not a durable irreproducible confirmation (the ledger's shape) — so the build
used the direct analog of the existing impl-floor rescue. The human-only guarantee is
identical to `qpb_promote.txt` (Panelist A confirmed it single-sourced + un-forgeable).
`quality_gate.py` was not touched (disclosure is manifest + interview, per the
instruction).

## The security invariants — proofs (mutation-bitten)
- **Human-only (A):** the rescue authority is single-sourced from the operator file;
  no document content / classifier / persona / cached record can reach
  `advisory_rescues`. A poisoned self-rescue via content fails; a poisoned prior
  manifest (forged `advisory_rescued`/tier-1) is discarded on cache-hit (the guard
  passes the operator rescue, never the cached flag). **Mutation-bites:** making the
  rescue derivable from doc content, or from the cached flag, each reddens a test.
- **Content-keyed (B):** exact `(path, own-sha)` match — no over-broad match
  (`a.md` ≠ `sub/a.md`/`a.md.bak`; sha prefix/superstring don't match); voids on a
  one-byte change; a rescue for A cannot promote B. **Mutation-bite:** keying on path
  only (ignoring sha) reddens `test_content_keyed_wrong_sha_does_not_rescue`.
- **Default floor intact (B):** absent a rescue, CVE/URL docs still floor under a
  promote-all classifier — opt-in per doc, never a global loosening. `_UNRESCUABLE_
  FLOOR_RULES` unchanged.

## Un-floor, not force-cite (confirmation)
A rescued doc with no classifier tier defaults to Tier 4 (`RULE_DEFAULT`), not
auto-Tier-1 — it reaches Tier 1/2 only if the classifier tiers it there. A rescue on
a non-advisory doc is a harmless no-op (not disclosed as rescued). The rescue removes
the barrier; it never fabricates authority.

## Disclosed
Every rescue is surfaced: the manifest record carries `advisory_rescued: true` +
`rescued_reason` (the overridden signal); `classification_playback` reports status
`advisory-rescued` with the reason; the interview Stage-1 prose (`requirements_
interview.md`) and the operator-authoring prose (`phase1_exploration_guide.md`)
instruct the disclosure. Never silent.

## Impl-floor rescue unchanged (confirmation)
The `sidecar_promote` impl-floor rescue has **no diff hunk** and is orthogonal —
`advisory_rescue` never rescues the impl floor (a `.py` logic file with
`advisory_rescue=True` still floors `RULE_IMPL`). Panelist C confirmed.

## Acceptance oracle — pass/fail
| # | Item | Result |
|---|------|--------|
| 1 | Rescue works — lifts a CVE-bearing spec past the advisory floor; classifies normally | **PASS** — `test_rescue_lifts_advisory_and_classifies_normally` + ingest end-to-end |
| 2 | Poisoned self-rescue fails (content / non-operator ledger) | **PASS** — `test_poisoned_self_rescue_via_content_fails`, `test_poisoned_prior_manifest_cannot_forge_a_rescue`; Panelist A 12/12 |
| 3 | Content-keyed — A ≠ B; mutating bytes voids | **PASS** — `test_content_keyed_wrong_sha...`, `test_rescue_for_A_does_not_promote_B`; Panelist B |
| 4 | Default floor intact without a rescue | **PASS** — `test_default_floor_intact_without_rescue` |
| 5 | Disclosed in manifest + interview playback | **PASS** — `test_disclosed_in_manifest_and_playback` + prose |
| 6 | Impl-floor rescue unchanged | **PASS** — `test_impl_floor_rescue_unchanged_and_orthogonal`; Panelist C (no diff hunk) |
| 7 | Full suite green | **PASS** — 2777 / 0 / 14, Python 3.14.6 |

## Files changed
| File | Change |
|------|--------|
| `plugins/.../scripts/doc_classification.py` | `Decision.advisory_rescued`/`rescued_reason`; `classify_document`/`_classify` take `advisory_rescue` (lift the floor + record the override); `classify_documents` takes `advisory_rescues` (content-keyed, applied to main classify + cache-guard); `_record` + `classification_playback` surface rescues |
| `plugins/.../scripts/reference_docs_ingest.py` | `ADVISORY_RESCUE_NAME` + `_load_advisory_rescues` (content-keyed, reason-required, operator-authored) threaded into `classify_reference_docs`; rescue file excluded from classification |
| `references/phase1_exploration_guide.md` | operator rescue-authoring instructions |
| `references/requirements_interview.md` | Stage-1 rescue disclosure |
| `bin/tests/test_doc_classification_v160.py` | `AdvisoryRescue025Tests` (10) + 2 ingest end-to-end tests |

## Commits made (branch `1.6.0`, local only — never pushed)
- `be212a2` — the rescue mechanism (code + prose + tests).
- `e870457` — tracked self-Council synthesis.

## Non-blocking observation (all three panelists, out of scope)
Once an operator **legitimately** rescues a doc, its cached tier is then trusted like
any non-floored doc (the pre-existing instruction-011 cache-trust model). This
requires the operator's explicit rescue of that exact content and does not forge the
rescue authority. Not introduced by this change.

## Remaining follow-ups (named per the instruction — OUT of this scope)
- **Feature H directive-narrowing (026):** narrow `persona_grounding._AGENT_DIRECTIVE_RE`; delete the dead `detect_fabrication` + fix its docstring; mutation-pin the Tier-1/2 grounded-citation guard; give grounding self-contained tier-claim detection so the retained `doc_classification.injection_signature` can finally be removed.
- **Render labeled-slots (027):** convert the render prose checks to labeled-slot format contracts (Fable Q4).
- Also open: broader 1.6.0 acceptance + Phase 8 tag/merge; OD-9 live FP bound; Feature-G non-plaintext-contract → FORMAL_DOC wiring; chi/express Slice-1 coherence-fixture regen; OD-11 hardening.

## Artifacts
- Gitignored: `runner/quality-playbook/reviews/025_self_council/` (three panelist verdicts).
- Tracked: `docs/process/QPB_v1.6.0_Instruction_025_Self_Council/synthesis.md`.
