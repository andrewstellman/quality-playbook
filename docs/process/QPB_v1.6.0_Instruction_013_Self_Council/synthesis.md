# Self-review — instruction 013 (Feature H slice 1: persona catalog + anchored selection)

**Verdict: SHIP.** Per the instruction, this mechanical slice (no isolation/provenance/execution
surface) gets a focused self-review, not the full 3-charter security Council (which is reserved for
the isolation/guard/merge/revert slices). The three required checks:

## (a) Catalog shape + anchor-enforcement is mechanical and test-proven
- **Data-first catalog** (`persona_catalog.CATALOG`): a list of dicts — `id`, `anchored`,
  `title`, `select_when` (+ `specialized_per_system`). Adding a lens is a data edit, no code
  surgery. Two anchored lenses (`domain-expert`, `security-reviewer`); the seven §8b-named
  selectable lenses each carry a `select_when` criterion. `catalog()` returns copies so the
  source can't be mutated. Pinned by `CatalogShapeTests` (4 tests).
- **Anchor enforcement is MECHANICAL, not prompt discipline.** `select_personas(proposed)` forces
  both anchors into the result regardless of the LLM's proposal, drops hallucinated (off-catalog)
  lenses, and collapses duplicates. Proven adversarially by `AnchorEnforcementTests` (5 tests):
  a selection omitting security still contains it; omitting domain still contains it; the empty
  selection yields both anchors; a made-up lens is dropped while the anchors persist; and the
  security lens is flagged `anchored` with an "anchored" justification when it was never proposed
  (load-bearing — it's present because of the anchor, not the proposal). This is the load-bearing
  bit §8b calls out (a system's own author under-weights security).

## (b) The selection record matches the organizing-principle precedent
- The precedent is `references/requirements_pipeline.md` § E.5: a **menu with per-lens criteria**,
  a **recorded choice + justification**, operator-validated. Matched two ways:
  - **Menu in-place:** added § **E.8 "Select validation personas"** to `requirements_pipeline.md`,
    structurally parallel to E.5 — the menu, the two mechanical anchors, "choose additional lenses
    and state why", and record-the-choice. Placed in-file (not a new reference) to mirror E.5's
    location and avoid the references-glob bundle-count drift.
  - **Recorded choice:** `build_selection_manifest(selected)` emits a reviewable, content-keyed
    record (`schema_version`, `generated_at`, `selection_sha256`, `records[]` with id/title/
    anchored/justification/specialization) — the same "surface the choice so the operator can
    review it" discipline as the organizing-principle statement and Feature G's classification
    manifest. Pinned by `SelectionRecordTests` (2 tests: shape + content-keyed reproducibility).
- **Sample selection** (`SampleSelectionTests`): a library-shaped system (chi/express) yields
  domain + security anchored + api-consumer with a stated reason, anchors rendering first — a
  sensible set (oracle item 4).

## (c) No persona-execution / isolation / guard scope leaked in
- The module selects and records only. It does NOT spawn sub-agents, enforce tool-allowlist
  isolation, ground/validate adds, merge, revert, or run a persona. `persona_catalog.py` is
  stdlib-only, imports nothing from the harness, and has no I/O beyond building an in-memory
  record. § E.8 explicitly defers execution/isolation/grounding/merge/revert to later slices.
- Not bundled into the install closure yet (deliberate): nothing at adopter runtime imports it
  until the persona-execution slice, so bundling now would be premature and trip no drift guard.
  Recorded for the orchestrator: the slice that wires persona execution must add
  `persona_catalog.py` to the bundle (install_skill._bundle_files, qpb_validate INSTALL_CLOSURE +
  count-pin, run_state_lib._FLAT_LAYOUT_BUNDLED_BIN_FILES, AGENTS.md, setup_repos.sh).

## Verification
Full suite green (see the instruction output for the count); Python 3.14.6. +12 catalog tests.
No existing fixture hand-edited.

**Terminal verdict: SHIP.** Foundational, mechanical, data-first, anchor-enforced, precedent-matched.
