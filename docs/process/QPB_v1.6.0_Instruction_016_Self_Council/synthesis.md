# Self-Council synthesis — instruction 016 (Feature H Guard 3: merge + single renumber)

**Verdict: SHIP after a correctness FIX-REQUIRED resolved.** Panelist C found a
real double-apply bug; it is fixed and pinned. Panelists A and B SHIP'd.

Reviewed code: branch `1.6.0`, commit `f5405c8` (Guard 3 merge). Three panelists,
each in its own git worktree, each writing a full verdict to
`reviews/016_self_council/panelist_{A,B,C}_*.md`.

## Charters + verdicts
- **A — conflict detection complete + never auto-resolves: SHIP.** All three
  design-enumerated disagreement shapes (add-vs-drop, divergent corrects,
  confirm-vs-drop) plus confirm-vs-correct, divergent-adds, drop-vs-{correct,add}
  are surfaced as operator-facing Conflicts carrying both moves/personas/reason;
  every agreement form (two confirms / identical corrects / identical adds / two
  drops / two pure adds) is correctly NOT flagged. The never-auto-resolve invariant
  held under every probe — a fired conflict holds ALL participating moves out and
  leaves the base manifest unchanged for that target; no ordering/target-key/self-
  conflict path lets a side silently win. Mutation bites (return-None; drop the
  drop-branch) fail 3/2 tests. Two unflagged pairwise shapes (correct-vs-add(target),
  confirm-vs-add(target)) noted as observations for the design owner — not in §8b's
  enumerated set, both fully union (no silent resolution), non-blocking.
- **B — exactly one renumber, reusing 007: SHIP.** `requirements_render.py` is a
  clean extraction of the instr-007 E.6 renumber; the 007 fixture helper's inline
  renumber was deleted and now CALLS it (one implementation; 007 tests stay green).
  A call-count spy shows the renumber runs exactly once for 1/3/multi-move persona
  sets (never per-persona); IDs come out contiguous REQ-001..NNN in document order;
  intra-manifest REQ→REQ refs are remapped. Mutating to renumber twice fails the
  once-only test. Non-blocking notes: `MergeResult.renumber_calls` is an
  informational literal (the real guard is the single call site); UC/BUG cross-ref
  remap is the caller's responsibility (documented slice-4 boundary; watch in slice 5).
- **C — union + exclusions + scope: FIX-REQUIRED → resolved.** Disjoint 3-persona
  add/correct/drop all land; `defer` and unknown moves excluded; candidate moves
  have no path in; provenance (`agent-validation` + citation) preserved on applied
  add/correct; no slice-5 scope leak (in-memory MergeResult only — no disk write /
  review-summary / revert / off-switch / spawn); not bundled adopter-side. **The
  defect:** two blind personas independently proposing the SAME missing requirement
  produced TWO duplicate REQ records — identical adds (no target) both landed. The
  commit claimed "agreement (dedup)" but only corrects were deduped via the
  non-conflict path, and the identical-corrects test only asserted `conflicts==[]`,
  not non-double-application.

## The FIX-REQUIRED (Panelist C) — resolved (`a7a493e`)
`_dedup` collapses identical moves (same move type + target + section + content)
before apply, so agreement applies ONCE while different adds to the same section
still both land. Pinned by `test_two_identical_adds_from_blind_personas_apply_once`
(one record, not a duplicate), `test_different_adds_to_same_section_both_land`, and
the strengthened `test_two_identical_corrects_are_agreement_applied_once`.

## Recorded for the orchestrator (non-blocking)
- **UC/BUG cross-reference remap** on renumber is left to the caller (this slice
  remaps REQ→REQ refs inside the requirements manifest; UC.requirements[] /
  BUG.requirement live in separate manifests). Slice 5's apply must propagate the
  returned remap to those — a latent integration point.
- **correct-vs-add(target) and confirm-vs-add(target)** are not currently surfaced
  as conflicts (both moves union). Not in §8b's enumerated set; for the design owner
  to decide whether to add.
- `persona_merge.py` (+ `requirements_render.py` + the other Feature H modules) are
  not bundled adopter-side yet — the execution/live-run slice must bundle them.

## Verification
Full suite green after the fix (see the instruction output for the count); Python
3.14.6. 007 fixture tests stay green after the shared-renumber refactor.

**Terminal verdict: SHIP.** Conflict surfacing and the single reused renumber were
solid; the identical-add double-apply Panelist C named — which would have degraded
the very requirements doc Feature H exists to improve — is fixed and tested.
