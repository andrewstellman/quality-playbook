# Instruction 007 — v1.6.0 Feature C: fix section-hierarchy detection, sequential-ID enforcement, and interview renumber

Three related structural defects found by a 2026-07-21 parallel test (Opus on chi / express / virtio, all v1.6.0, Feature C active). The requirements came out well-organized (three different organizing principles, correct `### REQ-NNN:` format), which is what let these bugs hide: the render contract *passed* documents whose section structure it could not actually parse.

## Read first — these ARE the spec
- `docs/design/QPB_v1.6.0_Design.md` **§5.2** (the architecture + "Choosing the organizing principle"), **§5.3** (render contract + the fail-closed subsection), **§6** the new bullet **"Renumber is the interview's terminal step, not a deferral"** (added 2026-07-21).
- `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py` `check_render_contract` and its section-parsing helpers (`_render_classify_sections`, `_render_named_section_body`, the "level 2 = functional section" logic ~line 6881, and the REQ-ID-sequential check).
- `references/phase2_generation_guide.md` § "Canonical document architecture".
- `references/requirements_interview.md` (write-back / re-render).
- `ai_context/DEVELOPMENT_PROCESS.md`.

## The evidence (reproduce, don't trust)
On `repos/{chi,express,virtio}-test/quality/REQUIREMENTS.md`:
1. **Section headers rendered at H3 (`### Route Registration & Pattern Matching`), the same level as `### REQ-NNN:` headings** — sections and requirements are siblings, not requirements nested under sections. The contract treats level-2 (`##`) as the section level, so it saw only the one `## …Sections` container: chi's gate output reads *"all **1** requirement section(s) carry a section overview"* for a 7-section document. The per-section checks (overview-present, ≥2-REQs, singleton-justification) are therefore **vacuous** — they cannot fail regardless of the real section structure.
2. **`express` rendered REQ-035 between REQ-013 and REQ-014** (interview `add` with a deferred renumber) and the contract PASSED with 0 FAIL. The "REQ IDs strictly sequential in document order" check is only verifying set-completeness (001..N present, no gaps), **not** ascending document order.
3. **All three deferred the E.6 renumber** after an interview `add`, shipping out-of-order IDs — the design now forbids this (§6).

## Work items

### 1. Establish and enforce the section/REQ heading hierarchy
Decide and document the canonical hierarchy: **requirement sections at `##` (H2), `### REQ-NNN:` requirements nested under them (H3)** — this is what the contract already assumes (line ~6881) and what makes sections and requirements structurally distinct rather than siblings.
- In `references/phase2_generation_guide.md` § "Canonical document architecture", **show the literal hierarchy with a worked example** (`## Section Name` → section overview → `### REQ-001: …`), the same routing fix as instruction 004: the writer must see the heading *levels*, not infer them. The three test docs flattened sections to `###` precisely because the guide never showed the level.
- This must be consistent with the top-level parts (Overview, Actors, etc. are also `##`); state how a requirement section is distinguished from those (it contains `### REQ-` headings — the existing `_render_classify_sections` intent).

### 2. Make the section checks fail-closed on a flattened document (`quality_gate.py`)
Mirror the 004 fail-closed principle at the section level:
- If the manifest has ≥2 `functional_section` values (i.e. the requirements are meant to be grouped into multiple sections) but the render exposes **only one parseable section** (the flattened-to-H3 case), that is a structural failure the contract must **FAIL or WARN**, naming the likely cause (section headers rendered at the REQ heading level instead of one level up). It must not silently report "1 section" and pass the per-section checks vacuously.
- After the fix, re-running the contract on the three test docs as they stand should surface the flattening (they are genuinely flat); a correctly-nested document must pass.
- **Mutation-bite it:** a multi-section manifest rendered flat → FAIL/WARN; a correctly-nested multi-section doc → the per-section checks actually evaluate each section (verify by a fixture with one section missing its overview → FAIL).

### 3. Fix the sequential-ID check to enforce ascending document order
The check must FAIL when REQ IDs are not strictly ascending in the order they appear (express's `…013, 035, 014…` must FAIL), not merely when the set has gaps. Keep the no-gaps check too; add the ascending-order check. Mutation-bite: a doc with a set-complete-but-out-of-order ID sequence must FAIL.

### 4. Interview renumber as the terminal step (`requirements_interview.md` + the re-render path)
Per Design §6's new bullet: the interview must run the **E.6 renumber once, as the final step after all operator moves**, atomically updating cross-references — including **`operator_confirmations.jsonl` `req_id` fields** — so the final document is sequential and every confirmation still resolves. Do NOT defer the renumber (the failure all three test runs exhibited). Make the interview protocol state this explicitly, and ensure the re-render actually performs it.
- Fixture: an interview that `add`s a REQ into an early section must produce a final document with sequential document-order IDs AND an `operator_confirmations.jsonl` whose `req_id`s match the renumbered IDs. Mutation: a deferred renumber (out-of-order IDs surviving to the final render) must fail the fixture.

## Also observed (record, don't fix here)
- **F-1 coverage-and-gaps statement was omitted by 2 of 3 runs** (chi, express — WARN each; bus-tracker earlier also omitted it). It is advisory (correctly WARN), but the recurrence suggests the generation guide's F-1 instruction isn't salient enough. Flag in your output whether a prominence fix (like the format fix) is worth a follow-up; do not implement it here.
- The Phase-0 double-marker block (`.claude` + `.github`) and the Phase-2 validator requiring `bugs_manifest.json` to exist at Phase 2 both caused friction in all three runs. Out of scope; note them for the orchestrator.

## Scope / fixture discipline
Section hierarchy + sequential-ID + interview renumber. Do NOT hand-edit existing golden fixtures to pass; new/corrected fixtures are expected (the existing render-contract fixtures may need their section headers moved to H2 — that is a legitimate fixture correction to match the now-explicit hierarchy, distinct from editing a fixture to dodge a check; explain each fixture change in your output). Do NOT touch Track 2.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight, `pre-flight-aborted` if wrong. Local commits only; **never push/merge**.
- Self-Council per §13: charters for (a) the fail-closed section-detection incl. the flattened-doc mutation and the per-section-check-now-evaluates proof, (b) the sequential-ascending-order check, (c) the interview terminal-renumber incl. the operator_confirmations reference-update. Each mutating panelist gets its own worktree. Artifacts under `RUNNER_ROOT/reviews/007_self_council/` + tracked copy under `docs/process/QPB_v1.6.0_Instruction_007_Self_Council/`.
- Verify the full suite; report counts + Python version.
- Output `outputs/007-section-hierarchy-and-renumber.md`: the flattened-doc FAIL/WARN now firing, the out-of-order-ID FAIL now firing, the terminal-renumber fixture (sequential IDs + updated confirmations), every fixture you changed and why, the F-1-prominence recommendation, and anything in §5.2/§5.3/§6 you found underspecified or wrong.
