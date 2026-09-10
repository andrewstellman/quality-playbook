# Instruction 013 — v1.6.0 Feature H slice 1: persona catalog + anchored selection

Feature H (§8b) is being built across focused slices, mirroring Feature G's 010→011 split. Instruction 012 landed **Guard 2** (agent-validation provenance + the write-restriction — verified: a persona cannot launder a record into the human-only `operator_confirmations.jsonl`). This slice builds the **foundation the persona machinery selects from**: the persona catalog and the anchored selection step. It is deliberately **mechanical and self-contained** — the catalog, the anchor-enforcement, and the selection recorder. The per-system *reasoning* about which lenses fit is the derivation LLM's job at run time; this slice gives it the menu and records its choice, exactly as Feature C gives the organizing-principle menu.

## Scope of THIS instruction
**Persona catalog + selection only.** Do NOT build sub-agent orchestration, isolation, the guards, the merge, the revert, or run a live persona pass — those are later slices. Stop and file when this slice's acceptance passes.

## Read first — these ARE the spec
- `docs/design/QPB_v1.6.0_Design.md` **§8b "Persona selection — chosen from a catalog, with anchors"** (the two anchored lenses + the AI-selected additional lenses + the selection-with-justification pattern). Also the §8b problem statement for why the security lens is anchored (the self-test: the domain persona filed prompt-injection as a mere candidate; the anchored security persona grounded it).
- `references/` — the **organizing-principle selection** built in instruction 006 is the direct structural precedent: a menu with selection criteria, and a recorded choice + rationale. Mirror its shape (catalog module + a recorded selection with justification). Find it and follow the same pattern (record location, schema style, how the rationale is persisted and rendered).
- `references/requirements_pipeline.md` — where persona selection sits (it precedes the persona runs, which are later slices).
- `ai_context/DEVELOPMENT_PROCESS.md`.

## The behavior to build (§8b persona-selection paragraph is the spec)

1. **A persona catalog** — a data-first module enumerating the available lenses, each with the selection criteria that say when it fits:
   - **Anchored (always selected, not skippable):** **domain expert** (the concrete role is derived per system from the Phase 1 domain + gathered docs — the catalog entry is the lens + how it's specialized, e.g. "expert in <the system's domain>"); **security reviewer**.
   - **Selectable (AI-chosen per system with a stated reason):** at least API/consumer-integrator, operator/SRE, data-privacy/compliance, accessibility, performance, reliability/failure-mode, adopter/end-user. Each entry carries a one-line "select when …" criterion. The catalog is a **menu with criteria, not a fixed roster**; adding a lens later is a catalog edit.

2. **Anchor enforcement (mechanical).** The two anchored lenses are always present in the selected set regardless of the LLM's choice — the selection step cannot drop them. A selection that omits domain or security is corrected/rejected mechanically, not left to prompt discipline. (This is the load-bearing bit: a system's own author under-weights security, so the anchor can't be an LLM suggestion.)

3. **A selection recorder.** The chosen lenses + the per-lens justification (why this lens fits this system; for anchored lenses, the specialization) are persisted in a **reviewable record**, the same way the organizing-principle choice is recorded and surfaced — so an operator can see which experts will validate the spec and why. Content-keyed / reproducible in the same spirit as the other v1.6.0 manifests where that applies.

4. **No persona execution here.** This slice selects and records; it does not spawn or run personas. Downstream slices consume the selected set.

## Acceptance oracle
1. The catalog enumerates the anchored + selectable lenses, each with a selection criterion; it is data-first (a lens can be added without code surgery).
2. **Anchor enforcement:** given a stubbed/adversarial selection that omits the security (or domain) lens, the final selected set still contains it — proven by a test, not asserted.
3. The selection recorder produces a reviewable record listing the chosen lenses + justification, structurally parallel to the organizing-principle selection record (point to the precedent you matched).
4. A selection over a sample system (use one of chi/express/virtio's Phase 1 domain + docs) yields a sensible set — domain + security anchored, plus a defensible additional lens with a stated reason.
5. Existing suite unchanged and green.

## Fixture discipline
Do NOT hand-edit golden fixtures to pass. New fixtures (the catalog, the anchor-enforcement test, a sample selection record) are expected.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight the branch, `pre-flight-aborted` if wrong. Local commits only; **never push/merge**.
- Self-Council per §13 — this slice is mechanical (not security-critical like the isolation/provenance slices), so a focused self-review suffices rather than the full 3-charter security Council: verify (a) the catalog shape + anchor-enforcement is mechanical and test-proven, (b) the selection record matches the organizing-principle precedent, (c) no persona-execution/isolation scope leaked in. Save artifacts under `RUNNER_ROOT/reviews/013_self_council/` + a tracked copy under `docs/process/QPB_v1.6.0_Instruction_013_Self_Council/`.
- Verify the full suite; report counts + Python version.
- Output `outputs/013-feature-h-persona-catalog-and-selection.md`: the catalog contents, how anchor-enforcement is implemented + its test, the selection-record shape and the precedent it mirrors, a sample selection over one real repo, and anything in §8b's selection paragraph you found underspecified.
