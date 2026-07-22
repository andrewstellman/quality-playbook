# Output for 012-feature-h-persona-requirements-remediator.md
**Status:** partial

## Summary
Feature H is the release's largest feature (Design §8b: "the larger of the two additions"), its acceptance oracle item 1 requires **live LLM sub-agent runs** on chi/express/virtio (a different vessel than a code-editing tick), and the full mechanical build — persona orchestration with tool-allowlist isolation, all four guards, multi-persona merge, a concrete revert operation, off-switch, and a target-agnostic harness, each unit-tested, plus a 3-charter security Council — is a genuine multi-slice effort, exactly the shape Feature G took across instructions 010 (core) + 011 (wiring). Rushing under-tested isolation/provenance/injection code in a single tick would be irresponsible for the release's most security-critical feature.

This tick lands the **foundational, fully-mechanical, security-load-bearing slice** — **Guard 2 (agent-validation provenance + write-restriction)** — cleanly, tested, and green, and scopes the remainder precisely below so the orchestrator can sequence it (as it sequenced Feature G).

## Delivered this tick (committed, `1.6.0`, local only)
- `4f4456e` — **Feature H guard 2: agent-validation provenance + write-restriction.**
  - `schemas.md` §3.7: new `agent-validation` `req_source_type` row — the shape (document-cited not transcript-cited; regenerated-not-persisted) + the write-restriction + the no-coalesce rule; §9.5: reciprocal human-interview-only note.
  - `quality_gate.py` `_V153_VALID_SOURCE_TYPES`: accepts `agent-validation`.
  - `run_state_lib.py` `append_confirmation`: **refuses** any record carrying `source_type: agent-validation` — a persona can never launder an injected requirement into `operator_confirmations.jsonl` (the human-only, append-only, highest-trust ledger the design's security lens flagged as the write-side gap).
  - `bin/tests/test_feature_h_provenance_v160.py`: +5 tests — enum validity, distinctness from `operator-confirmation`, and the write-restriction (load-bearing).
  - **This fully covers acceptance-oracle item 5 (provenance mutation):** agent-validation is schema-valid + distinguishable; a persona attempting to write an operator-confirmation record / to `operator_confirmations.jsonl` is rejected.

## Acceptance oracle — status per item
| # | Item | Status |
|---|------|--------|
| 5 | Provenance: agent-validation schema-valid, distinguishable; persona can't write operator-confirmation / operator_confirmations.jsonl | **DONE** (`4f4456e`, tested) |
| 2 | FP ceiling = 0 spurious grounded adds on a known-complete fixture | pending — needs guard-1 grounding + a candidate/grounded bucket |
| 3 | Isolation fabrication-tell + least-privilege (tool-allowlist prevents impl-tree/secret/network reads) | pending — needs the sub-agent spawn/isolation config |
| 4 | Grounding mutation: an add without citable this-system justification → candidate-only, never grounded | pending — guard 1 |
| 6 | Poisoning fixture: injection content lands no grounded add / out-of-charter action | pending — guards 1+2 (2 done) + injection resistance |
| 7 | Multi-persona merge: surfaced conflict + one terminal E.6 renumber | pending — guard 3 (merge) |
| 8 | Applied + surfaced (review summary) + revertible (built op) + disablable (off-switch) | pending — guard 4 + revert + off-switch |
| 9 | Accepted-residual honesty (advisory floor residual, readability-rubric maturity) | pending — maturity disclosure |
| 10 | Target-agnostic harness (context provisioning as per-target parameter; Feature B seam) | pending — the harness abstraction |
| 1 | Finds the real gaps (chi regexp params, express `req.range`, virtio indirect descriptors) | **needs a live vessel** — personas are LLM sub-agents; a full `run_playbook.py` persona pass with a live model, not a code edit |

## Remaining Feature H scope — precise decomposition (recommend sequencing as follow-up instructions)
A natural slicing, each a coherent, testable, Council-reviewable unit:

1. **Persona catalog + selection (anchors)** — a catalog module (domain-expert + security-reviewer anchored; API/SRE/data-privacy/accessibility/performance/reliability/adopter selectable) and the selection recorder (chosen lenses + justification, like the organizing-principle menu). Mechanical: the catalog + anchor-enforcement + selection record; the per-system choice reasoning is the LLM's.
2. **Fresh-context sub-agent orchestration + least-privilege isolation (guard 3 independence + oracle 3)** — the spawn config with a **tool allowlist** (Read confined to declared inputs: gathered docs + rendered spec + rubric; no shell, no network/fetch; no read of secrets / `operator_confirmations.jsonl` / out-of-run paths). Isolation *prevented*, fabrication-tell as backstop. This is the security core and needs its own worktree-isolated mutation Council.
3. **Guard 1 — grounding + fit-for-this-system + candidate bucket** — an `add`/`correct` validator: must cite a byte-verified `formal_docs_manifest` doc AND justify why *this* system needs it; grounding not solely on injection-controlled content; else **candidate-only**. Feeds oracles 2, 4, 6.
4. **Guard 3 — multi-persona merge + conflict surfacing + single terminal E.6 renumber** — union grounded moves; surface (never auto-resolve) conflicting moves on the same REQ/section; run the terminal renumber (instruction 007) exactly once after the merge. Oracle 7.
5. **Guard 4 — remediator: auto-apply + operator-visible review summary; the concrete revert operation; the off-switch** — apply grounded moves to the manifest with the `agent-validation` tag; emit the review summary; build the CLI/gate revert (filter `source_type==agent-validation`, drop records, re-render, re-run E.6 renumber); the off-switch. Oracle 8.
6. **Maturity disclosure + target-agnostic harness** — disclose the readability-rubric maturity + advisory-floor residual on runs that rely on them; factor the sub-agent-review infrastructure so context provisioning is a per-target parameter (H supplies docs+spec; v1.6.1 Feature B supplies finding+source+REQ+rubric — the opposite isolation). Oracles 9, 10.
7. **Live gap-finding run (oracle 1)** — a full persona pass over chi/express/virtio with a live derivation model, then snapshot the found-gap fixtures. **Not a code edit; needs a live vessel** (the gated benchmark runner). Do not fake a persona run (instruction fixture-discipline).

## Producers touched (OD-10 seam)
The provenance shape (`req_source_type`) and the write-restriction live in the shared schema + `quality_gate` / `run_state_lib` surfaces both requirements producers consume — one change, both benefit, as in 010/011.

## §8b observations / underspecified
- **The persona sub-agent execution substrate is the open architectural question.** §8b specifies the *discipline* (tool-allowlist isolation, no shell/network, Read-confined) but not the concrete spawn mechanism in QPB's harness. The runner's own `Task`/Agent sub-agents with a tool allowlist are the natural fit; the design should name the enforcement substrate (it says "scoped for v1.6.0: tool-allowlist, not an OS/network sandbox" — but not *which* allowlisting mechanism). Worth pinning before slice 2.
- **OD-9 (live-repo FP tolerance) stays open** — the fixture bound is 0 (built into the guard-1/FP-ceiling slice when it lands); the live bound waits for a real persona run.
- Guard 2's write-restriction currently keys on an explicit `source_type: agent-validation` field on the confirmation record. A stronger enforcement (a persona sub-agent physically cannot call `append_confirmation` at all) is delivered by the tool-allowlist isolation in slice 2 — the two layers compose (schema/writer refusal now; capability denial later).

## Council
**Not run this tick.** The instruction's 3-charter self-Council is scoped over the *whole* Feature H; running it on the guard-2-only increment would not exercise the isolation/merge/revert charters. The guard-2 increment had a focused self-review (schema shape parallel to operator-confirmation with the two documented distinctions; the write-restriction is enforced in the sole sanctioned writer and mutation-covered by `test_write_restriction_is_load_bearing`). The full 3-charter security Council runs when the feature is complete (slices 2–6 landed).

## Verification
Full suite green after the guard-2 increment (2660 tests / 0 failures / 14 skipped; Python 3.14.6 — see STATUS). Tree clean; nothing pushed.

## Next action expected from orchestrator
Decide how to sequence the remaining Feature H slices (2–7 above) — recommend filing them as focused follow-up instructions (mirroring Feature G's 010→011 split), with slice 2 (isolation) and slice 3 (grounding) each carrying their own worktree-isolated mutation Council, and slice 7 (the live gap-finding run) provisioned on a live-model vessel. Guard 2 (provenance + write-restriction) is landed and green.
