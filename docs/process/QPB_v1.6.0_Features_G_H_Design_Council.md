# Design-review Council — v1.6.0 Features G & H (2026-07-22)

Council review of the two design additions (Feature G — dump-and-go ingest; Feature H — agent-driven persona validation) and the v1.6.1 couplings. Three adversarial panelists (architecture / safety / scope-implementability), run to convergence. **Final verdict: SHIP.**

## Verdict progression
| Round | Architecture | Safety | Scope/Impl |
|---|---|---|---|
| 1 | SHIP-WITH-FIXES | FIX-REQUIRED | FIX-REQUIRED |
| 2 | SHIP | SHIP-WITH-FIXES | SHIP |
| Confirm | — | **SHIP** | — |

## Blocking findings (round 1) and how they were resolved

**Feature G**
- *No deterministic floor against advisory-poisoning* — a MUST/SHALL security bulletin reads like a contract and could be promoted to citable (the OpenFGA 0/3 failure). Byte-verification was wrongly listed as a safety (BUG-009 byte-matches). → **Deterministic advisory floor** (CVE/GHSA/URL/header + security-genre markers) the LLM cannot override; byte-verification de-listed as a mis-tiering guard; content-keyed manifest for reproducibility.

**Feature H**
- *No input isolation → circular validation.* A persona could read the code and `confirm` against it — validating requirements against implementation, the ground-truth rule's forbidden case. → **Input isolation**: persona receives only docs + rendered spec + rubric, denied the implementation tree; code-reading is a fabrication tell; covers all five moves. Plus a Feature-G source-not-citable rule to close the "code dumped into the docs folder" side door.
- *"Calibration" measured variance (reliability), not accuracy (validity)* — a consistently-wrong persona passes and gates. → Gating **deferred**; H ships **non-gating**; gating requires an accuracy baseline (precision/recall vs. labeled corpus), named post-v1.6.0.
- *Criterion 8 declared victory on the fallback (vacuous).* → Non-gating reframed as a **documented scope of the deliverable**, criterion carries testable sub-claims, release notes must state H shipped un-calibrated for gating.
- *Not implementable:* persona derivation, verdict combination, `agent-validation` schema, false-positive ceiling all unspecified. → Fixed default **3-lens set** (domain / security / API-consumer); defined **merge** (parallel + blind → union grounded moves → surface conflicts → single terminal renumber, reconciled with §6); **`agent-validation` schema** (doc-cited, byte-verified, regenerated-not-persisted, non-coalescing); **false-positive ceiling** in the oracle.

## Non-blocking residuals (round 2), all addressed
1. Advisory floor broadened to security-genre markers + non-signature residual explicitly accepted (bounded blast radius: manifest-visible, non-gating, reviewable).
2. Source-file-shaped docs floored to Tier 4 / non-citable (mechanical).
3. **Non-gating ≠ non-altering** — persona changes update the manifest but the merge emits an **operator-visible agent-validation review summary** (surface, don't silently apply — modeled on G's citable-promotion). Conflict-surfacing covers the full five-move set.

## Standing constraint (carry into the release)
**Non-gating is load-bearing for the v1.6.0/v1.6.1 split rationale.** v1.6.0 stays a "complete acceptance story of its own" only because H does not gate and v1.6.1 merely *reuses* H's harness. If H is ever promoted to gating inside v1.6.0, that claim breaks. The operator decision the Council surfaced (is H a "finish" or its own release?) is resolved in-doc by the non-gating cap; keeping H non-gating in v1.6.0 is the invariant that keeps the split honest.

## What Andrew's original intent preserved
The "have the persona update the requirements" behavior is kept — personas *do* write grounded add/correct moves to the manifest — but the updates are now **surfaced** (agent-validation provenance + operator-visible review summary) rather than silently auto-applied, and **grounded** (byte-verified citation + this-system justification) rather than hallucinable.
