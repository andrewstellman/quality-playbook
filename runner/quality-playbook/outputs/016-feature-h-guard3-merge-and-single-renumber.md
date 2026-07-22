# Output for 016-feature-h-guard3-merge-and-single-renumber.md
**Status:** completed

## Files created / changed
| Path | Note |
|------|------|
| `plugins/.../scripts/persona_merge.py` | **New** — Guard 3: `merge_personas` (union + conflict surfacing + `_dedup` + single renumber), `_group_conflict`, `_move_target`, `Conflict`, `MergeResult`. |
| `plugins/.../scripts/requirements_render.py` | **New** — the canonical E.6 renumber extracted from the 007 fixture helper (`renumber_to_document_order`, `document_order`) so it is reused, not reimplemented. |
| `bin/tests/test_persona_merge_v160.py` | **New** — 12 tests: union, each conflict shape surfaced-not-resolved, single-renumber (call-count spy), defer/candidate exclusion, provenance, dedup. |
| `bin/tests/test_feature_d_interview_fixture_v160.py` | Refactored `_render_requirements_md` to call the canonical renumber (de-dup; 007 tests stay green). |
| `docs/process/QPB_v1.6.0_Instruction_016_Self_Council/synthesis.md` | Tracked 3-charter Council synthesis. |
| `runner/.../reviews/016_self_council/{panelist_A,B,C,synthesis}.md` | Gitignored full Council artifacts. |

## Commits made (branch `1.6.0`, local only — never pushed)
- `f5405c8` — Feature H slice 4: Guard 3 merge + conflict surfacing + single renumber (+ 10 tests + the 007-renumber extraction/refactor).
- `a7a493e` — **fix (self-Council C):** dedup identical grounded moves (+ 2 tests).
- `f1d6ca2` — tracked self-Council synthesis.

## Acceptance oracle — pass/fail per item
| # | Item | Result |
|---|------|--------|
| 1 | Union: non-overlapping grounded moves from multiple personas all appear | **PASS** — `UnionTests` |
| 2 | Conflict surfaced, not resolved (per shape); both moves/personas/reasons carried; neither applied | **PASS** — `ConflictSurfacingTests` (add-vs-drop, divergent corrects, confirm-vs-drop) |
| 3 | Exactly one terminal renumber, sequential IDs; renumber invoked once | **PASS** — `SingleRenumberTests` (call-count spy == 1) |
| 4 | `defer` excluded | **PASS** — `test_defer_never_participates` |
| 5 | Candidate bucket untouched (grounded-only input) | **PASS** — interface takes grounded moves only |
| 6 | Provenance preserved (`agent-validation` + citation through merge + renumber) | **PASS** — `test_applied_moves_retain_agent_validation_provenance` |
| 7 | Existing suite unchanged and green | **PASS** — 2714 / 0 / 13 |

## The merge / union rule
`merge_personas(grounded_by_persona, base_manifest)` flattens each persona's grounded `add`/`correct`/`drop`/`confirm` moves (a `defer` or unknown move is dropped — never participates), groups them by target for conflict detection, **dedups identical moves** (two blind personas proposing the same requirement apply once), applies the non-conflicting moves to the base manifest, then runs **exactly one** terminal renumber. Returns `MergeResult(manifest, conflicts, applied, held_out, remap, renumber_calls)`.

## Conflict-detection rule + a surfaced-conflict example per shape
Two moves from **different personas** on the **same target** that disagree are an operator-facing `Conflict` (both moves + both personas + reason), **held out** of the applied set — no heuristic winner. Agreements (two confirms / two identical corrects/adds / two drops) are not flagged. Shapes:
- **add vs drop** (add targeting REQ-003 vs a drop of REQ-003) → conflict; REQ-003 stays, the replacement is not added.
- **divergent corrects** (two different corrections of REQ-002) → conflict; REQ-002 keeps its ORIGINAL content (neither correction silently won).
- **confirm vs drop** (one confirms REQ-001, another drops it) → conflict; REQ-001 stays, neither move applied.
Panelist A confirmed completeness across all shapes and that no path ever auto-resolves.

## Proof the terminal renumber runs exactly once (and reuses 007)
The instruction-007 E.6 renumber lived only inline in the 007 fixture helper. This slice **extracted** it into `requirements_render.renumber_to_document_order` (the canonical, single implementation) and **refactored** the 007 helper to call it (the 007 `TerminalRenumberTests` + deferred-renumber mutation stay green — Panelist B verified via `git show --stat`). `merge_personas` calls it **once** for the whole multi-persona pass (not per-persona), verified by a `mock.patch` call-count spy (`spy.call_count == 1`) across 1/3/multi-move persona sets; the result is contiguous REQ-001..NNN in document order (an add into an early section gets an early id).

## The `defer` / candidate exclusions
`defer` (operator-only) and unknown move types are dropped from the merge entirely (`test_defer_never_participates`). Candidate (ungrounded) moves from slice 3 are never passed here — the interface consumes only the **grounded** set; candidates stay in slice 3's `candidate_bucket`.

## The merged-output shape + the seam to slice 5
`MergeResult` is in-memory: `manifest` (merged + renumbered once), `conflicts` (the operator-facing set), `applied` / `held_out` moves, `remap` (old→new REQ ids), `renumber_calls`. This slice does **not** write the manifest to disk, build the operator-visible review summary, or provide revert/off-switch — those are Guard 4 (slice 5), which consumes this `MergeResult`: it renders the review summary from `applied` + `conflicts`, keys revert on `source_type == agent-validation`, and propagates `remap` to the UC/BUG cross-references (see below).

## §8b Guard 3 — underspecified / notes (recorded for the orchestrator)
- **UC/BUG cross-reference remap.** The renumber remaps REQ→REQ references *inside* the requirements manifest, and returns the `{old_id: new_id}` remap. But `UC.requirements[]` and `BUG.requirement` live in **separate** manifests — propagating the remap to them is left to the caller. **Slice 5's apply must apply `remap` to the UC and BUG manifests** or traceability breaks after a merge that renumbers. Flagged by Panelist B; the seam (`requirements_render.apply_remap`) is provided.
- **correct-vs-add(target) and confirm-vs-add(target)** are not currently surfaced as conflicts (both moves union). Not in §8b's enumerated conflict set (line 314); for the design owner to decide whether to add.
- The identical-move dedup keys on (move, target, section, content) — a near-duplicate with cosmetically different wording is not deduped (both land or, if divergent corrects/adds on the same target, surface as a conflict). This is the correct conservative behavior (don't collapse things that aren't provably identical).

## The self-Council FIX-REQUIRED and its resolution
Panelist C found that **identical grounded `add` moves from two blind personas were double-applied** (two duplicate REQ records) — the commit claimed dedup but only corrects were deduped via the non-conflict path, and the test only checked `conflicts==[]`, not non-double-application. **Fixed (`a7a493e`):** `_dedup` collapses identical moves (same type + target + section + content) before apply — agreement applies once, different adds to the same section still both land. Pinned by the new identical-adds and different-adds tests + the strengthened identical-corrects test.

## For the orchestrator — bundle when execution lands
`persona_merge.py`, `requirements_render.py`, `persona_grounding.py`, `persona_orchestration.py`, `persona_catalog.py` are **not bundled adopter-side yet** — the persona-execution/live-run slice must add all five to the bundle-drift sites.

## Feature H progress
guard 2 (012) + catalog (013) + orchestration/isolation (014) + guard 1 grounding (015) + guard 3 merge (016) done. Remaining: guard 4 auto-apply + review summary + revert + off-switch (slice 5, consumes this `MergeResult` + must propagate `remap` to UC/BUG), maturity disclosure + target-agnostic harness acceptance (slice 6), and the live gap-finding run (slice 7 — needs a live vessel).

## Next action expected from orchestrator
Sequence slice 5 (Guard 4 — auto-apply + operator-visible review summary + the concrete revert operation + off-switch), which consumes this slice's `MergeResult`, renders the review summary from `applied` + `conflicts`, builds the `source_type == agent-validation` revert (drop selected records, re-render, re-run the terminal renumber), and propagates the renumber `remap` to the UC/BUG cross-references.
