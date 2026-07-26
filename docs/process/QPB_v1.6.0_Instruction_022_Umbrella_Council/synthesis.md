# Instruction 022 — Integrated umbrella Council over the composed Feature H pipeline

**Terminal verdict: unanimous SHIP**, after one FIX-REQUIRED → fix → re-review cycle.

This is the composition-level review the ten Feature H slices (instructions
012–021) structurally could not run: each slice self-Councilled *in isolation*.
The umbrella Council reviewed the *assembled* flow — persona selection (013) →
orchestration + least-privilege isolation (014) → grounding + candidate bucket
(015) → multi-persona merge + single renumber (016) → apply + review summary +
revert + off-switch (017) → maturity disclosure + target-agnostic seam (018),
with provenance write-restriction (012) throughout, now composed into
`persona_apply.run_feature_h` (021) and bundled adopter-side (020) — asking one
question: does any seam regress a guard when the pieces run in sequence?

Three fresh-context panelists, each in its own git worktree, each RUNNING a real
end-to-end `run_feature_h` pass (stubbed spawn) and mutation-biting the composed
path — not unit tests alone.

## Charters + verdicts

- **A — Security composition: SHIP.** With all guards running together on a real
  end-to-end pass (15/15 adversarial checks, mutation-confirmed): isolation holds
  through the whole pipeline — each staging dir contains ONLY what `provision`
  returns, the spawn gets Read-only/no-bash/no-network, a malicious provision
  staging `operator_confirmations.jsonl` is refused (`IsolationError`), a
  path-traversal name is flattened into the staging root. The provenance
  write-restriction cannot be bypassed by any composed path — no persona module
  imports `run_state_lib` or reaches the ledger writer; `run_feature_h`'s only
  write is `quality/persona_review_summary.json`; `_apply_move` hardcodes
  `agent-validation`, normalizing even a forged `operator-confirmation` move.
  Injection-shaped content is candidate-only at the grounding layer AND never
  laundered into operator-confirmation through the full flow; the poisoning
  fixture lands 0 grounded change. Mutation (feed candidates into the merge)
  fails driver + suite.

- **B — Data-flow integrity end to end: FIX-REQUIRED → (post-fix) SHIP.** Round 1
  confirmed provenance + byte-verified citation survive every hop, the renumber
  remap propagates to BUG cross-refs on composed output, and revert round-trips
  (all + selective) on full-pipeline output. But the seam probe found a real
  composition bug (below). After the fix, B reset to the fixed commit and
  re-verified end-to-end (19/19): the drop applies, the drop-vs-correct conflict
  surfaces (no silent pick), the confirm reaches the merge, `defer` stays
  excluded, no injection bypass opened, persona_id preserved for conflict
  grouping, and round-1 Tasks 1–3 still hold — no regression. SHIP.

- **C — Remediator-not-a-gate + honesty, composed: SHIP.** No gate/verdict/
  calibration emerged from composition — `run_feature_h` returns a manifest +
  review summary, never a pass/fail/score; the only "gate" tokens are the
  self-describing "remediator, not a gate" and the reused "citation gate". The
  review summary lists every applied change (count parity, mutation-confirmed).
  The maturity disclosure fires when composed output rests on the readability
  rubric and is absent otherwise. The FP-ceiling (0 spurious grounded adds) holds
  on composed output. The off-switch disables the entire pass (two guard layers).
  Invocation prose (E.9 / phase2.md / SKILL.md) is consistent, opt-out, no
  prose/code drift.

## The composition bug (found + fixed + re-reviewed)

**Confirm/drop moves were silently lost at the grounding→merge seam.** The
composed `run_feature_h` step 3 forwarded only `gr.grounded` to the merge, but
Guard 1 (`persona_grounding.classify_diff_set`) gates ONLY `add`/`correct`
(`GATED_MOVES`) — `classify_move` returns `None` for `confirm`/`drop`, which then
landed in neither `grounded` nor `candidates`. They never reached the merge.

Consequences vs Design §8b:
- **guard 4** ("grounded add/correct/**drop** moves are applied") — a persona
  `drop` was never applied by the composed pipeline.
- **guard 3** (the conflict check covers `confirm`/`correct`/`add`/`drop`) — an
  add-vs-drop / confirm-vs-drop / correct-vs-drop conflict could never surface, so
  a contested REQ was silently resolved: the exact "silent pick" §8b forbids.

Only the isolated slices' own tests exercised `add`; the seam lived exclusively in
the composition, which is why the umbrella Council was the first to see it.

**Root-cause fix (commit `fc20c2e`)** — the taxonomy had drifted across two
modules (grounding's `GATED_MOVES` vs the composition's implicit assumption that
`grounded` was the complete forward-able set); the fix keeps the taxonomy in one
place:
- `persona_grounding`: `PASS_THROUGH_MOVES = ("confirm","drop")` beside
  `GATED_MOVES`; a `passthrough` bucket on `GroundingResult`; `classify_diff_set`
  collects the ungated persona moves (confirm/drop — NOT operator-only `defer`)
  into it.
- `persona_apply.run_feature_h` forwards `gr.grounded` moves **plus**
  `gr.passthrough` to the merge.
- `persona_merge` docstring corrected — it already handled all four
  `_PERSONA_MOVES`; no guard logic changed. The seam was simply starved of two.
- Regression: `ConfirmDropSeamTests` (3 composed-pipeline tests) —
  mutation-confirmed load-bearing (reverting the forward fails all three, one
  reproducing the original `conflict_count: 0` silent-pick).

## Non-blocking observations (recorded for the orchestrator, not fixed here)

Both panelists gave SHIP with these noted; neither regresses a guard, and the
instruction bars scope creep — so they are recorded, not patched:
1. **A:** `run_personas` computes `fabrication_flags` but `run_feature_h` does not
   consume/halt on them. Design-consistent — §8b names the fabrication-tell an
   explicit backstop; grounding (guard 1) is the load-bearing gate, and a
   fabricated citation independently fails byte-verify, so it cannot reach the
   manifest. A future slice could surface the flags in the review summary.
2. **C:** `candidate_bucket` drops `dimension`/`rubric_dependent`, so a
   rubric-dependent *candidate* does not contribute to the maturity-disclosure
   count, mismatching `build_review_summary`'s comment. No false confidence arises
   (candidates are already surfaced as uncertain; applied + conflict moves retain
   `dimension` and do fire the disclosure). Optional tidy-up: carry the fields in
   `candidate_bucket` or key the candidate contribution off the original move.

## Verification

Full suite green: **2741 / 0 / 14**, Python 3.14.6 (baseline 2738/0/13 + 3 new
seam tests; the skip-count delta is a pre-existing environment-conditional skip,
unrelated to this change). The composed end-to-end pass was exercised by all three
panelists (stubbed spawn); the live spawn is the running agent's Task tool at
pipeline-run time (instruction 019 is the live acceptance).

**Feature H is integration-clean and ready for broader acceptance testing.** The
one composition seam has been closed and re-reviewed to SHIP.
