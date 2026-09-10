# Instruction 016 — v1.6.0 Feature H slice 4: Guard 3 — multi-persona merge + conflict surfacing + single terminal renumber

Feature H runs several personas **in parallel, each blind to the others** (slice 2), and each emits grounded moves (slice 3). This slice combines them. The design's rule is precise and load-bearing: **union the grounded moves, surface conflicts rather than auto-resolving them, and run exactly one terminal renumber after the merge** — personas do not each renumber. Getting the "surface, don't resolve" and the "renumber once" contracts right is what keeps the multi-persona output coherent and honest.

## Scope of THIS instruction
**Guard 3 only** — the merge over the per-persona grounded move-sets: union, conflict detection + surfacing, and the single terminal E.6 renumber over the merged manifest. Out of scope: the operator-visible review summary, the auto-apply framing, the concrete revert operation, and the off-switch (all Guard 4, slice 5); maturity disclosure + harness factoring (slice 6); the live persona run (slice 7). Stop and file when this slice's acceptance passes.

## Read first — these ARE the spec
- `docs/design/QPB_v1.6.0_Design.md` **§8b Guard 3** end-to-end — "in parallel, each blind to the others' writes"; the merge **unions the grounded `add`/`correct` moves**; **surfaces conflicts rather than auto-resolving** (two moves touching the same REQ/section that disagree — `add` vs `drop`, divergent `correct`s, `confirm` vs `drop`); the conflict check covers `confirm`/`correct`/`add`/`drop` (**`defer` is operator-only, not a persona move — it does not participate**); and **"only after the merge does a single terminal E.6 renumber run"**, resolving the §6 "renumber once after all moves" contract for the multi-persona case. Also §8b Verification item **7**.
- **§6** and the **terminal E.6 renumber built in instruction 007** — the single renumber this slice invokes exactly once after the merge. Reuse it; do not reimplement renumbering.
- `plugins/quality-playbook/skills/quality-playbook/scripts/persona_grounding.py` — slice 3's grounded vs candidate classification: the merge consumes the **grounded** moves per persona (candidate moves do not merge; they stay in the candidate bucket).
- `plugins/quality-playbook/skills/quality-playbook/scripts/persona_orchestration.py` — slice 2's per-persona diff-set shape (the input to grounding, then to the merge).
- `references/requirements_interview.md` — the five moves and how they write back to the manifest.
- `ai_context/DEVELOPMENT_PROCESS.md`.

## The behavior to build (§8b Guard 3 is the spec)

1. **Union the grounded moves.** Take each persona's **grounded** `add`/`correct`/`drop` moves (from slice 3) against the same base manifest and combine them into one merged move-set. Non-overlapping moves from different personas all land. `confirm` records that a persona validated an existing REQ; `defer` is not a persona move and never appears here.

2. **Detect + surface conflicts — never auto-resolve.** Where two personas' moves touch the **same REQ or section and disagree** — an `add` vs a `drop`, two divergent `correct`s on the same REQ, a `confirm` against another's `drop` — that pair is an **operator-facing conflict flag**, not a silently-picked winner. A conflict carries both moves, both personas, and both stated reasons. Conflicting moves are **held out of the applied set** and surfaced; do not merge one and drop the other by any heuristic. Non-conflicting grounded moves proceed.

3. **Exactly one terminal renumber, after the merge.** After the union + conflict hold-out, run the **terminal E.6 renumber once** over the merged manifest (the instruction-007 renumber). Personas must **not** each renumber; there is exactly one renumber for the whole multi-persona pass, producing sequential IDs over the final merged set. This is the concrete resolution of §6's "renumber once after all moves."

4. **Provenance preserved.** Every merged move keeps its `agent-validation` provenance + byte-verified citation (Guard 2 / Guard 1) through the merge and renumber, so slice 5's review summary and revert can key on it.

## Boundary with slice 5
This slice produces the **merged manifest + the conflict set + the (still-separate) candidate bucket**. It does **not** build the operator-visible review summary, the off-switch, or the revert operation — those are Guard 4 (slice 5). Whether this slice writes the merged manifest to disk or emits a merged diff for slice 5 to apply is your call for the cleanest seam; either way, the invariants above (surface-not-resolve, one terminal renumber) must hold and be tested.

## Acceptance oracle (§8b Verification 7)
1. **Union:** non-overlapping grounded moves from multiple personas all appear in the merged set.
2. **Conflict surfaced, not resolved:** two personas conflicting on one REQ/section (`add` vs `drop`, divergent `correct`s, `confirm` vs `drop`) produce an **operator-facing conflict flag** carrying both moves/personas/reasons; neither is silently applied — proven by test.
3. **Single terminal renumber:** exactly one E.6 renumber runs after the merge (not per-persona), yielding sequential IDs over the merged set. Assert the renumber is invoked once.
4. **`defer` excluded:** a `defer` never participates in the merge (it is operator-only).
5. **Candidate bucket untouched:** candidate (ungrounded) moves from slice 3 are not merged or applied — they remain in the candidate set.
6. **Provenance preserved:** merged moves retain `agent-validation` + citation through merge + renumber.
7. Existing suite unchanged and green.

## Fixture discipline
Do NOT hand-edit golden fixtures to pass. New fixtures (a multi-persona union, a conflict-surfacing case per conflict shape, a single-renumber assertion) are expected.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight the branch, `pre-flight-aborted` if wrong. Local commits only; **never push/merge**.
- Self-Council per §13 — this slice is correctness-critical (coherence of the multi-persona output) more than security-critical, so a focused review with charters: (a) conflict detection is complete across the four move-shapes and **never auto-resolves**; (b) exactly one terminal renumber, reusing instruction 007's renumber (not a reimplementation), sequential IDs correct; (c) union correctness + candidate-bucket/`defer` exclusion + no auto-apply/review-summary scope leak (that's slice 5). Artifacts under `RUNNER_ROOT/reviews/016_self_council/` + a tracked copy under `docs/process/QPB_v1.6.0_Instruction_016_Self_Council/`.
- Verify the full suite; report counts + Python version.
- Output `outputs/016-feature-h-guard3-merge-and-single-renumber.md`: the merge/union rule; the conflict-detection rule + a surfaced-conflict example per shape; proof the terminal renumber runs exactly once (and reuses 007); the `defer`/candidate exclusions; the merged-output shape and the seam to slice 5; and anything in §8b Guard 3 you found underspecified.
