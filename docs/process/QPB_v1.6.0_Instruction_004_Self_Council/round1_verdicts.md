# Instruction 004 self-Council — Round 1 verdicts

Three charters per the instruction, each panelist in its own isolated git worktree
(the 003 phantom-failure hazard). Implementation reviewed: commit **`2c389d1`**.

**Outcome:** A SHIP, B SHIP (one P2), C FIX-REQUIRED (one orphan). Fixed in `cb3d966`.

---

## Panelist A — fail-closed render-contract check → SHIP

- **Product-vs-tool-contract split correct across all edge cases.** `_render_product_req_count` (quality_gate.py:7309-7339): a no-references[] record → counted as product (conservative, fail-closed-safe); mixed refs → product; tool-contract-only → `product_reqs==0` → INFO skip; absent/malformed manifest → `None` → INFO skip (None is neither truthy nor `==0`, correctly falls to `else`). Verified live via the skip tests.
- **Mutation bite (live):** `if product_reqs:` → `if False and product_reqs:` turned `test_populated_manifest_with_bold_markers_fails` + `test_fail_message_names_the_likely_cause` RED; 68 other tests stayed green (scoped). Restored via `shutil.copy2`, `__pycache__` purged, 70/70 green, worktree clean.
- **Version-gate ordering correct:** `_render_run_predates_contract` now runs strictly before the no-headings/fail-closed branch; `test_pre_v160_bold_render_with_manifest_is_skipped_not_failed` exercises the exact regression shape and passes; no prior version-gating test broke.
- **No false positives:** the branch fires only when headings are literally absent AND the manifest proves product REQs exist AND the run is v1.6.0+; the wrong-level WARN is checked first.
- Two out-of-scope pre-existing observations (not defects here): the unterminated-fence check is not version-gated (pre-existing); `_v150_manifest` calls `fail()` as a side effect on non-dict JSON (a separate check, not the render contract).

## Panelist B — format-instruction correctness across the three bound docs → SHIP (one P2)

- **Item 1 (format visible where the generator reads it): PASS.** phase2.md:9 routes the generator to phase2_generation_guide.md; the "Requirement heading format" subsection with a correct worked example lands there, not merely cross-referenced.
- **Item 2 (three-way binding): PASS, symmetric.** pipeline.md, phase2_generation_guide.md, and the quality_gate.py comment each name the other two by file and section; no dangling reference.
- **P2 (doc/mechanism mismatch):** the prohibition list claimed `### REQ-7:` (un-padded) "turns the render contract off", but the regex `REQ-(\d+)` matches it (`int(m.group(2))` discards padding) — the parser reads it as REQ-7, and no downstream check validates padding. The docs asserted a stricter enforcement than the mechanism provides. *(Closed in cb3d966: list split into contract-disabling vs. read-but-nonconforming; zero-padding stated as a generator convention the gate does not enforce.)*
- Suite green including doc-drift/hash guards.

## Panelist C — placement re-sequencing completeness → FIX-REQUIRED (one orphan)

- **Orphan found:** `references/phase1_exploration_guide.md:510` still read "After the pipeline: Phase 7 offers the requirements validation interview … not a Phase 2 artifact, and never auto-started" — the pre-reversal placement, contradicting Design §6, and read by the same agent that runs the pipeline. The only surviving orphan in the implementation tree. *(Closed in cb3d966: rewritten to the Phase 2→3 boundary placement with the one-reminder-at-end fallback.)*
- **Six touched surfaces all correctly re-sequenced and mutually consistent:** what_just_happened.md State P2 (good "why now" messaging), phase2.md (primary offer), phase3.md (demoted, do-not-re-offer), requirements_interview.md (primary at P2→3 + one end reminder; protocol content intact), SKILL.md:270, phase7_guide.md item 1 (demoted to end-of-run reminder). Reminder preserved at four points.
- **Design-doc drift flagged (orchestrator's, not the worker's charter):** Design:174 and Implementation_Plan:87 still carry the pre-reversal "playbook-end summary offers" language; the §5.3/§6 edits are UNCOMMITTED in the working tree (which is why this round, at committed 2c389d1, could not see the §6 placement text). The worker does not edit docs/design/ — surfaced for the orchestrator.
- Suite green; phase-prompt hash guards confirm the phase2/phase3 edits are intentional-edit-pinned.
