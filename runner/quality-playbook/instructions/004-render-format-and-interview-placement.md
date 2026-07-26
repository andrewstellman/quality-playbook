# Instruction 004 — v1.6.0: close the render-format fail-open + move the validation offer to post-Phase-2

Four changes, all diagnosed from a 2026-07-21 smoke test (Haiku on `repos/bus-tracker-*`). The design docs were updated to match before this instruction was filed — **read them first, they are the spec.**

## Read first — these ARE the spec
- `docs/design/QPB_v1.6.0_Design.md` **§5.3** "The render contract must fail closed on a manifest-vs-render marker mismatch" (added 2026-07-21) and **§6** "Placement — offered after Phase 2, before Phase 3" (added 2026-07-21). Both are new; both drive this instruction.
- `docs/design/QPB_v1.6.0_Implementation_Plan.md` Phase 2/Phase 3 boundary.
- `references/phase2_generation_guide.md`, `references/requirements_pipeline.md`, `references/requirements_interview.md`, `plugins/quality-playbook/skills/quality-playbook/phase_prompts/{phase2,phase3}.md`, `plugins/quality-playbook/skills/quality-playbook/SKILL.md`.
- `ai_context/DEVELOPMENT_PROCESS.md`.

## The evidence (so you can reproduce, not just trust)
On `repos/bus-tracker-1.6.0` and `repos/bus-tracker-smoke`, two Haiku runs rendered requirements as `**REQ-001:**` (bold) instead of `### REQ-001:` headings. Consequence chain, all verified:
1. `quality_gate.check_render_contract` found no `### REQ-NNN:` headings → hit the INFO "not a contract-shaped render, render contract skipped" branch → **checked nothing**.
2. The document carried 5 single-REQ sections with no justification — the C-3 defect Feature C exists to catch — plus missing cross-cutting and traceability parts. None flagged, because the whole contract skipped.
3. Root cause: the `### REQ-NNN: Title` rule is stated in `references/requirements_pipeline.md:92` (and explicitly forbids `**REQ-NNN**: Title`), but the Phase 2 generator is routed to `references/phase2_generation_guide.md` (`phase2.md:50`), which describes the whole architecture yet **never states the marker format and never shows a rendered REQ example**. The writer never saw the rule the checker enforces.

## Work items

### 1. Put the REQ marker format where the generator actually reads it
In `references/phase2_generation_guide.md` § "Canonical document architecture" (the part that lists the nine document parts), add the literal render format for a requirement, including a short worked example block showing `### REQ-NNN: Title` followed by its sub-fields. State plainly: requirements render as `### REQ-NNN: Title` headings (zero-padded three-digit NNN); **never** `**REQ-NNN**:`, `### REQ-NNN — Title`, or `### REQ-NNN. Title`. This is the exact prohibition already in `requirements_pipeline.md:92` — the generator just wasn't being shown it. Do not merely cross-reference the other file; the format must be visible in the doc the generator is routed to.

### 2. Bind the three docs so the format can't drift again
The format rule now lives in `requirements_pipeline.md` AND `phase2_generation_guide.md`, and is enforced by `quality_gate.py`. Add a one-line cross-reference in each of the three pointing at the others ("the canonical marker format is `### REQ-NNN:`; kept in sync with <the other two>"), so a future edit to one is visibly incomplete without the others. This is the same spec-vs-implementation binding the §5.2↔§5.3 traceability matrix applies one level up.

### 3. Make the render contract fail closed (Design §5.3, new subsection)
In `check_render_contract` (`plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py`), the branch that currently emits INFO "not a contract-shaped render, render contract skipped" must instead:
- Read `requirements_manifest.json` and count **product** REQ records (the same product-vs-tool-contract split the contract already uses elsewhere — a tool-contract-only manifest is not a product-render failure).
- **If ≥1 product REQ records exist but the render carries zero `### REQ-NNN:` headings → FAIL**, with a message naming the likely cause (wrong marker format, e.g. `**REQ-NNN**:` instead of `### REQ-NNN:`) and pointing at the format rule. This mirrors the existing unterminated-fence FAIL ("refuse to certify rather than pass by default").
- **If the manifest has zero product REQ records → keep the INFO skip** (genuinely nothing to render; correctly not applicable).
- Leave the existing wrong-*level* WARN (`## REQ-NNN:`) unchanged.
- **Mutation-bite it:** a fixture with a populated manifest and a bold-marker render must FAIL; a fixture with an empty product manifest must still skip; the three conformant fixtures must stay green. A check that cannot fire is not a check.

### 4. Move the validation-interview offer to the Phase 2 → Phase 3 boundary (Design §6)
Currently the interview is offered at "Phase 7 / playbook-end" (`SKILL.md:270`). Move the **primary** offer to immediately after Phase 2 completes and before Phase 3 begins:
- After Phase 2 writes `REQUIREMENTS.md` + `requirements_manifest.json`, the playbook presents a clear operator-facing offer: the requirements are complete; they can be validated now, before Phases 3–6 build tests/reviews/audits on them; the interview is opt-in and never auto-starts. Good messaging is a named acceptance criterion here — the operator must understand *what* is being offered and *why now* (validate the spec before downstream work depends on it).
- Keep discoverability: a run that declines gets one end-of-run reminder that validation is still available. Do not keep the end-of-run slot as the primary offer.
- Update `SKILL.md`, `phase_prompts/phase2.md`, `phase_prompts/phase3.md`, and `references/requirements_interview.md` (its `:22` "playbook-end summary" line) consistently. The interview protocol content (three stages, five moves, narrative-first) does not change — only where it is offered.

## Note on a related finding (NOT in scope, record it)
The same smoke test showed the live run going straight to per-REQ enumeration instead of the narrative-first Stage 1 → 2 → 3 the protocol specifies (`requirements_interview.md:67` "Depth is never pushed. Breadth-first by default"). Whether that is model weakness or an entry-point that doesn't steer narrative-first is unresolved. **Do not fix it here** — flag it in your output so the orchestrator can decide. This instruction is format + placement only.

## Fixture constraint (unchanged from 002/003)
Do **not** hand-edit `bin/tests/fixtures/**/REQUIREMENTS.md`. New fixtures for item 3's mutation bites are fine; editing existing golden fixtures to pass is not.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight the branch, `pre-flight-aborted` if wrong. Local commits only; **never push/merge**.
- Self-Council per §13: charters for (a) the fail-closed check incl. its mutation bites and the empty-manifest skip path, (b) format-instruction correctness across the three bound docs, (c) placement re-sequencing completeness (no path still offers the interview only at the end; no orphaned Phase-7 offer). Artifacts under `RUNNER_ROOT/reviews/004_self_council/` **and** a tracked copy under `docs/process/QPB_v1.6.0_Instruction_004_Self_Council/` (the `reviews/` path is gitignored at any depth). Give each mutating panelist its own worktree (the 003 phantom-failure hazard).
- Verify the full suite; report counts + Python version.
- Output `outputs/004-render-format-and-interview-placement.md`: the fail-closed mutation results (populated→FAIL, empty→skip, conformant→green), the three bound docs, the placement re-sequencing surfaces touched, the narrative-first finding flagged, and anything in the updated §5.3/§6 you found underspecified or wrong.
