# Output for 004-render-format-and-interview-placement.md
**Status:** completed

## Files created / changed
| Path | Note |
|------|------|
| `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py` | Item 3: `_render_product_req_count` helper; `check_render_contract` no-headings branch now fails closed on a populated-manifest/zero-heading mismatch; version-gate reordered before the no-headings branch; Item 2 binding comment on `_RENDER_REQ_HEADING_RE`. |
| `references/phase2_generation_guide.md` | Item 1: new "Requirement heading format" subsection (worked `### REQ-NNN:` example + prohibition list) in § Canonical document architecture; Item 2 binding line. |
| `references/requirements_pipeline.md` | Item 2: binding line on the existing "Requirement heading format" section. |
| `references/what_just_happened.md` | Item 4: State P2 now carries the primary interview offer (why-now messaging) at the Phase 2→3 boundary. |
| `plugins/quality-playbook/skills/quality-playbook/phase_prompts/phase2.md` | Item 4: primary offer instruction at end of Phase 2. |
| `plugins/quality-playbook/skills/quality-playbook/phase_prompts/phase3.md` | Item 4: notes the interview was offered at end of Phase 2; do not re-offer as blocking. |
| `references/requirements_interview.md` | Item 4: placement paragraph rewritten (primary at P2→3, one reminder at end). |
| `SKILL.md` | Item 4: :270 placement line updated. |
| `references/phase7_guide.md` | Item 4: improvement-menu item 1 demoted to the end-of-run reminder. |
| `references/phase1_exploration_guide.md` | Fix round (Council C): the orphaned "Phase 7 offers … not a Phase 2 artifact" line rewritten to the Phase 2→3 boundary placement. |
| `bin/tests/test_render_contract_v160.py` | New `RenderContractFailClosedTests` (6 tests); the pre-v160 inertness test made faithful to `minimal_zero_bug_tree` (no manifest). |
| `bin/tests/test_phase_prompts_externalized.py` | phase2/phase3 hash baseline recomputed (intentional-edit acknowledgement). |

## Commits made
- `2c389d1` — v1.6.0 [instr 004]: fail-closed render contract + interview offer at Phase 2→3 (implementation).
- `cb3d966` — v1.6.0 [instr 004]: close self-Council findings (C's orphan + B's marker-list accuracy P2).
- `ad47bc4` — v1.6.0 [instr 004]: tracked self-Council artifacts + synthesis.
- `<this commit>` — runner: output for instruction 004.

## Acceptance criteria — pass/fail per item
| Criterion | Result |
|-----------|--------|
| Fail-closed mutation: populated manifest + bold-marker render → **FAIL** | **PASS** — `test_populated_manifest_with_bold_markers_fails`; mutation-bitten (neutering the FAIL turns it RED, restored). |
| Empty product manifest → still **skip** | **PASS** — `test_empty_product_manifest_still_skips` (tool-contract-only). |
| Absent manifest → still **skip** | **PASS** — `test_absent_manifest_still_skips`. |
| Three conformant fixtures stay **green** | **PASS** — `test_conformant_fixtures_stay_green`; chi/express/virtio render-contract tests unchanged and green. |
| Pre-v1.6.0 archived run not retroactively failed | **PASS** — `test_pre_v160_bold_render_with_manifest_is_skipped_not_failed` (version-gate-first ordering). |
| Marker format visible in the generator's routed doc | **PASS** — phase2_generation_guide.md § "Requirement heading format" worked example. |
| Three-doc binding present in all three | **PASS** — pipeline / generator-guide / quality_gate.py each cross-reference the other two. |
| Interview primary offer at Phase 2→3 boundary | **PASS** — what_just_happened.md State P2 + phase2.md; end-of-run reminder preserved (phase7_guide.md). |
| Full suite + counts + Python version | **2592 tests, 0 failures (14 skipped)**, Python 3.14.6. |

## Council (if required)
**Verdict: unanimous SHIP** (Round 2 closure). Three charters per the instruction, each
panelist in its own git worktree (the 003 phantom-failure hazard).

| Panelist | Charter | Round 1 (`2c389d1`) | Round 2 (`cb3d966`) |
|----------|---------|---------------------|---------------------|
| A | fail-closed check (+ mutation bites, empty-manifest skip) | **SHIP** | *stands (surface untouched by fix round)* |
| B | format-instruction correctness across the three bound docs | SHIP (1 P2) | **SHIP** |
| C | placement re-sequencing completeness | FIX-REQUIRED (1 orphan) | **SHIP** |

- **C's blocking finding:** an orphaned Phase-7-as-primary offer survived at
  `references/phase1_exploration_guide.md:510` ("Phase 7 offers … not a Phase 2 artifact")
  — not in the instruction's named surface list, but read by the same agent that runs the
  pipeline. Fixed; a full skill-tree sweep (mine) and C's independent nine-surface closure
  sweep both confirm no orphan survives and all surfaces agree on the Phase 2→3 placement.
- **B's P2:** the worked-example prohibition list wrongly claimed the un-padded `### REQ-7:`
  form "turns the render contract off"; the regex actually matches it. Fixed by splitting
  contract-disabling from read-but-nonconforming forms; B re-ran the regex and confirmed
  the doc now matches the mechanism exactly.
- **A confirmed** the fail-closed check with a live mutation bite (neutering the FAIL turns
  the bold-marker test RED), correct across all manifest edge cases, version-gate ordering
  correct, no false positives.

Artifacts: `RUNNER_ROOT/reviews/004_self_council/` (gitignored) and the tracked mirror
`docs/process/QPB_v1.6.0_Instruction_004_Self_Council/` — `round1_verdicts.md`,
`round2_closure.md`, `synthesis.md`.

## Notable observations

### The fail-closed mutation results (the headline acceptance)
The exact 2026-07-21 smoke-test shape is now caught. `RenderContractFailClosedTests._BOLD_RENDER` is a document rendering two requirements as `**REQ-001:**` / `**REQ-002:**` (bold, no `### REQ-NNN:` headings), with the base fixture's 5-product-REQ manifest:
- **populated manifest + bold render → FAIL** (message names the likely cause — `**REQ-NNN:**` bold instead of `### REQ-NNN:` — and points at both `requirements_pipeline.md` and `phase2_generation_guide.md`). Mutation-bitten: `if product_reqs:` → `if False and product_reqs:` turns the test RED.
- **tool-contract-only (zero product REQ) manifest → INFO skip** ("no product REQ records — nothing to render").
- **absent manifest → INFO skip** ("requirements_manifest.json is unavailable — cannot FAIL without evidence").
- **conformant base fixture (### headings) → green.**

### The three bound docs
The canonical marker `### REQ-NNN:` is now authored in `references/requirements_pipeline.md` § "Requirement heading format" AND `references/phase2_generation_guide.md` § "Requirement heading format" (with a worked example — the doc the Phase 2 generator is actually routed to via `phase_prompts/phase2.md`), and enforced by `_RENDER_REQ_HEADING_RE` in `quality_gate.py`. Each of the three carries a one-line cross-reference to the other two, so an edit to one is visibly incomplete without the others.

### The placement re-sequencing surfaces touched
Primary offer moved from playbook-end to the Phase 2→3 boundary: `what_just_happened.md` State P2 (the operator-facing "why now" message), `phase_prompts/phase2.md` (primary-offer instruction), `phase_prompts/phase3.md` (already-offered note), `references/requirements_interview.md` (placement paragraph), `SKILL.md` (:270), `references/phase7_guide.md` (item 1 demoted to end-of-run reminder). Protocol content (three stages, five moves, narrative-first) unchanged.

### Flagged for the orchestrator (NOT fixed here, per the instruction)
The same smoke test showed the live run going **straight to per-REQ enumeration** instead of the narrative-first Stage 1 → 2 → 3 the protocol specifies (`requirements_interview.md` "Depth is never pushed. Breadth-first by default"). This instruction is format + placement only, so I did not touch it. Whether it is model weakness (Haiku not honoring the breadth-first instruction) or an entry-point that doesn't steer narrative-first is unresolved — recording it for the orchestrator to decide. One hypothesis worth the orchestrator's attention: the new Phase 2→3 primary offer is the natural place to *seed* the narrative-first framing (the State P2 message already leads with "I play back what I understood the system to be"), so the entry-point steering and the placement change are related surfaces.

### Anything in §5.3/§6 found underspecified or wrong
1. **§5.3 does not state the version-gate-first ordering, and the naive implementation is a regression.** The design mandates "populated manifest + zero headings → FAIL" but says nothing about *when* the version gate runs relative to it. The obvious placement (fail-closed check in the existing no-headings branch, which sat *after* the version gate in source but the gate only `return`s for predates) is fine — but the fail-closed branch had to be moved to run only *after* the version gate, or a genuine pre-v1.6.0 archived run (old PROGRESS version + populated v1.5.x manifest + old-format render) would newly FAIL, retroactively failing archived runs. I reordered `_render_run_predates_contract` to run before the no-headings branch. **Recommend §5.3 state that the fail-closed check is gated by the same v1.6.0+ obligation as the rest of the contract** — it is not a universal invariant, it is a v1.6.0+ one.
2. **§5.3's "product REQ records" leaves the no-references[] record unclassified.** The product-vs-tool-contract split keys on "references[] point exclusively into quality/." A record with an *empty or absent* references[] is neither all-quality/ nor clearly product. The existing `_render_tool_contract_ids` treats a no-refs record as NOT tool-contract (it `continue`s past empty refs), so I count it as a product REQ — meaning a manifest of only no-refs records would FAIL a zero-heading render. That is the safe direction (a real requirement with no citations still needs rendering), but §5.3 should say so rather than leave it to the implementer.
3. **§6 is well-specified.** The messaging requirement ("what is offered and why now") is a clear, testable acceptance bar; no defect found. The one latent tension: §6 says a corrected requirement at the end leaves downstream stale, but does not say what happens if the operator validates at the P2→3 boundary and *then* a Phase 3–5 bug reveals a requirement error — i.e. validation is a one-shot gate, not a loop. That is consistent with the MVP boundary (QI-loop closure is deferred), so it is a scoping note, not a defect.

4. **The design spec §5.3 and §6 are UNCOMMITTED — a process gap, not a content one.** The instruction says "The design docs were updated to match before this instruction was filed — read them first, they are the spec." They *were* updated, but only in the working tree: `git show HEAD:docs/design/QPB_v1.6.0_Design.md` at commit `2c389d1` contains neither the §5.3 "fail closed" subsection nor the §6 "Placement — offered after Phase 2, before Phase 3" text; both exist only as uncommitted modifications. Two consequences. (a) My round-1 Council panelists, reviewing committed state in isolated worktrees, could not see the spec they were validating against — Panelist C grepped for the §6 placement text and found none, and correctly flagged it. My implementation is still correct (I read the spec from the working tree), but the review was weaker than intended. (b) The uncommitted design doc now internally contradicts itself: the new §6 placement bullet coexists with the old pre-reversal "playbook-end summary offers it" language at `Design.md:174` and `Implementation_Plan.md:87` (Panelist C's design-drift finding). `docs/design/` is orchestrator-owned, so I did not touch it — but **the orchestrator should commit §5.3/§6 and remove the contradicting old lines**, or the next instruction that "reads the design as the spec" inherits a spec that disagrees with itself and isn't in git.

5. **Zero-padding is documented as mandatory but not mechanically enforced (Panelist B P2).** `requirements_pipeline.md` and the new worked example both say REQ IDs are zero-padded three-digit, but `_RENDER_REQ_HEADING_RE` (`REQ-(\d+)`) matches `### REQ-7:` and `_render_req_headings` does `int(m.group(2))`, discarding padding; the sequential-ID check compares int values, not string widths. So an un-padded ID is read as a valid REQ and passes the gate. I corrected the generator guide to stop claiming the un-padded form disables the contract and to state plainly that padding is a generator convention the checker does not enforce. Whether the gate *should* enforce padding (it would make IDs sortable/diffable, but risks retroactively flagging archived runs) is a scoping call for the orchestrator — I did not expand the check.

## Next action expected from orchestrator
Land the instruction-004 commits on `1.6.0` (worker never pushes/merges). Decide on the flagged narrative-first entry-point finding (model weakness vs. entry-point steering). Track 2 broad-repo validation remains the orchestrator's.
