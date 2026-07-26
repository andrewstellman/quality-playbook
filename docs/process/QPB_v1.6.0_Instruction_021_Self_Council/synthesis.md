# Self-Council synthesis — instruction 021 (wire the persona pass into the pipeline)

**Verdict: unanimous SHIP** across all three charters, zero fix-required rounds.

Reviewed code: branch `1.6.0`, commit `0b2d85d` (compose + invoke Feature H). Three
panelists, each in its own git worktree, each writing a full verdict to
`reviews/021_self_council/panelist_{A,B,C}_*.md`.

## Charters + verdicts
- **A — the composed step preserves isolation + off-switch + provenance end to end
  (no seam regresses a guard): SHIP.** 30 hands-on adversarial assertions (temp
  trees planting a real impl file + secret token + an actual
  `operator_confirmations.jsonl`, driven through a stubbed `spawn_persona`):
  isolation holds — each staging dir contains ONLY what `provision` returns, the
  spawn gets a Read-only/staging-rooted/no-shell/no-network config, a malicious
  `provision` staging `operator_confirmations.jsonl` is refused with
  `IsolationError`, and the instr-021 fabrication-tell flags an unstaged excerpt in
  BOTH string and dict citation shapes; the off-switch no-ops the whole step and
  gates BEFORE any spawn/staging (`enabled=True` default); provenance intact
  (grounded → `agent-validation` + citation, ledger never written); guard 1 still
  bites (an ungrounded hunch AND an injection-shaped-but-byte-verifying add both
  become candidates). Mutation bites (apply raw moves; ignore off-switch) each fail
  the corresponding test.
- **B — the invocation point is correct (post-Phase-2, before 3–6) and opt-out:
  SHIP.** All three prose surfaces (`requirements_pipeline.md` § E.9, `phase2.md`,
  `SKILL.md`) place the pass at the Phase 2→3 boundary — the identical slot as
  Feature D's opt-in human interview — and none puts it in Phase 1 or after Phase
  3. All three frame it opt-out/auto-run with an off-switch (explicitly contrasted
  with the opt-in interview) and "remediator, not a gate" (no verdict, never blocks
  Phase 3). The prose maps 1:1 onto `run_feature_h` with no prose/code drift and no
  over-claim (E.9 attributes the live spawn to the running agent, not the
  function). phase2 hash-pin recomputed + matching; SKILL.md within the token
  ceiling.
- **C — no guard logic reimplemented + seam-fix correctness + scope: SHIP.**
  `run_feature_h` is pure composition — it delegates every guard to the
  already-verified modules and reimplements none; the only in-body logic is
  marshalling glue + the off-switch early return (load-bearing, not a drift-prone
  copy). The `detect_fabrication` seam fix is strictly-additive compat widening
  (string path byte-identical; a dict's `citation_excerpt` now checked; unstaged
  excerpts of either shape still flag; the dropped "source" docstring line
  described behavior never implemented). No umbrella/acceptance scope crept in; no
  new bundled module (run_feature_h lives in the already-bundled persona_apply.py —
  bundle-drift guards unchanged + green); the review-summary artifact is the run
  artifact `quality/persona_review_summary.json`.

## Non-blocking notes
- A: a dual-import `IsolationError` identity artifact in the test harness only
  (not product code).
- C: the commit message said "+8 pipeline tests" but the file has 6 (the "+8" was
  6 pipeline + the dict-citation orchestration test + …) — prose imprecision in the
  commit message, not a defect.

## Verification
Full suite green after the phase2 hash-pin recompute (see the instruction output
for the count); Python 3.14.6. The composition tests exercise the whole flow with a
stubbed spawn; the live spawn is the running agent's Task tool at pipeline-run time
(instruction 019 is the live acceptance).

**Terminal verdict: SHIP.** The persona pass is wired at the correct post-Phase-2
point, opt-out, remediator-not-a-gate; the composition preserves every guard
(isolation / off-switch / provenance / grounding — mutation-confirmed); and it is
pure reuse of the verified modules with a correct additive seam fix. An adopter's
run now actually runs Feature H.
