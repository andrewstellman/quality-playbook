# Instruction 006 — v1.6.0 Feature C: the derivation chooses the requirements' organizing principle

The design was updated 2026-07-21 to make the requirements' **organizing principle a per-system choice** rather than a fixed "functional sections" mandate. Read the design first — it is the spec.

## Read first — these ARE the spec
- `docs/design/QPB_v1.6.0_Design.md` **§5.2 item 4** ("Requirement sections — grouped by an organizing principle the derivation *chooses*") and the subsection **"Choosing the organizing principle (a Phase E reorganization pass)"** — both new 2026-07-21. Also §5.2 the **§5.2↔enforcement traceability matrix** (rows 4b/4c changed), **§6 Stages 1–2** (the interview now plays back the organizing principle and uses section overviews), and **§12** the 2026-07-21 reversal record.
- `references/requirements_pipeline.md` Phase E (E.5 ordering, E.6 renumber — the reorg pass is an enrichment of Phase E, ahead of E.6).
- `references/phase2_generation_guide.md` § "Canonical document architecture" (item currently reading "Functional sections").
- `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py` `check_render_contract` and its mandatory-part / section checks.
- `references/requirements_interview.md` (Stage 1 / Stage 2).
- `ai_context/DEVELOPMENT_PROCESS.md`.

## Why (the evidence)
A 2026-07-21 smoke test on `repos/bus-tracker-test`: a capable model produced a well-formed document but mixed four grouping axes (functional, interface, cross-cutting, architectural) without choosing one — because the pipeline mandated "functional sections" and the model slotted rather than decided. IEEE 830 §5.3 holds that the best organizing principle is system-dependent and lists the menu. Feature C should have the derivation choose, state the choice, and let the operator validate it in the interview.

## Work items

### 1. The organizing-principle selection pass (`references/requirements_pipeline.md` + `phase2_generation_guide.md`)
Add to Phase E, ahead of the E.6 renumber, the six-step pass from Design §5.2 "Choosing the organizing principle": assess the system → choose one principle from the IEEE 830 §5.3 menu (feature · use case · user class/stakeholder · mode/state · object/entity · stimulus-response/interface · functional hierarchy · justified combination; **feature is the default only when none clearly fits**) → regroup records (update `functional_section` assignments; records keep their shape — same manifest write-back the renumber already does) → write a section overview per section → state the chosen principle + one-paragraph rationale at the top of the section list → order sections most-relevant-first, then renumber.

Put this where the generator actually reads it (the generation guide), not only in the pipeline doc — the same routing lesson as instruction 004. Rename the architecture's "Functional sections" part to "Requirement sections (organized by the chosen principle)" and describe the section-overview requirement.

### 2. Render contract goes principle-agnostic (`quality_gate.py`)
The section checks currently assume "functional sections." Generalize to check **structure, not principle choice**:
- An organizing principle is **named** and a **rationale** is present at the top of the section list → else FAIL.
- Each requirement section carries a **section-overview** paragraph (the unifying theme, not a REQ-title restatement) → else FAIL (this generalizes the existing intro-prose check).
- The existing **≥2 REQs or one-line singleton justification** rule per section is unchanged.
- Do **not** add a check that judges whether the chosen principle is *optimal* — that is Feature D + the Phase 4 rubric (judgment, not regex). A check that tried to would be wrong by construction.
- Keep all other mandatory-part checks (Overview, Actors, Use cases, Traceability, Glossary) exactly as they are.
- **Mutation-bite the new checks:** a document with sections but no stated principle/rationale must FAIL; a section with no unifying overview must FAIL; a conformant multi-principle document (e.g. a use-case-organized one) must PASS. Add a fixture organized by a **non-functional** principle (use case or stakeholder) so the suite proves the contract accepts a correctly-organized non-functional grouping — this is the regression that proves the principle-agnostic behavior.

### 3. Interview integration (`references/requirements_interview.md`)
- **Stage 1** additionally plays back the organizing principle: "I organized these by X because Y — is that the right lens, or would Z fit better?" (Design §6). A change of principle here is a `correct` move that triggers a re-group + re-render.
- **Stage 2** reads each section's unifying overview and validates the theme before its requirements.

### 4. Reconcile the glossary-placement drift (while you are in these files)
Design §5.2 lists the glossary as part **9** (end); `phase2_generation_guide.md` places it as part **4** (after Actors). Pick one and make both agree — this is exactly the spec-drift this release fights. Recommend the generation guide's placement (glossary after Actors, before the requirement sections: the reader meets the vocabulary before the requirements that use it) and fix the design to match, or vice-versa. State which you chose.

## Scope / fixture discipline
Organizing-principle selection + its contract generalization + interview hooks + the glossary reconcile. Do NOT hand-edit existing golden fixtures to pass; new fixtures (the non-functional-grouping one) are expected. Do NOT touch Track 2 / NFR work.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight, `pre-flight-aborted` if wrong. Local commits only; **never push/merge**.
- Self-Council per §13: charters for (a) the principle-agnostic render contract incl. the non-functional-grouping fixture and the mutation bites, (b) the selection-pass correctness across pipeline doc + generation guide (routing: the format/menu is where the generator reads), (c) interview-integration + glossary-reconcile completeness. Artifacts under `RUNNER_ROOT/reviews/006_self_council/` + tracked copy under `docs/process/QPB_v1.6.0_Instruction_006_Self_Council/`. Each mutating panelist gets its own worktree.
- Verify the full suite; report counts + Python version.
- Output `outputs/006-organizing-principle-selection.md`: the non-functional-grouping fixture result (contract accepts it), the mutation results (no principle → FAIL, no section overview → FAIL), which glossary placement you standardized on, and anything in the updated §5.2/§6 you found underspecified or wrong.
