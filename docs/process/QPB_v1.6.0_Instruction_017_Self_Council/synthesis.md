# Self-Council synthesis — instruction 017 (Feature H Guard 4: apply + review + revert + off-switch)

**Verdict: unanimous SHIP** across all three charters, zero fix-required rounds.
(Panelist C's first run died on an API error mid-stream and was re-run to a clean
SHIP; the two runs' worktrees were both cleaned.)

Reviewed code: branch `1.6.0`, commit `a6879ce` (Guard 4). Three panelists, each in
its own git worktree, each writing a full verdict to
`reviews/017_self_council/panelist_{A,B,C}_*.md`.

## Charters + verdicts
- **A — revert round-trips exactly + remap propagation: SHIP.** A 30-check
  adversarial harness + two mutation bites confirmed `revert(which="all")` restores
  BOTH the requirements AND BUG manifests **byte-exactly** to the pre-persona
  snapshot — including undoing a `correct` (content, source_type, AND the injected
  citation key) and restoring a dropped REQ — because it deep-copies the snapshot
  rather than a fragile forward-undo. Selective revert removes only the named
  agent-validation record, ignores code-derived ids (cannot delete originals),
  re-sequences 1..N with no gaps/dupes, and re-propagates BUG links; the remap
  updates every `req_id`/`covers[]` (mixed/suffixed/bare/malformed/None handled)
  and never touches UC (schemas §7). Both mutation bites (break snapshot-restore;
  no-op `apply_remap_to_bugs`) are caught.
- **B — apply correctness + review-summary completeness: SHIP.** Grounded moves
  land tagged `agent-validation` with citations; conflicts (held out) and candidates
  never reach the manifest. `build_review_summary` iterates the exact applied set,
  so every applied change (incl. applied drops/confirms) is listed with grounding
  (persona, move, reason, system_justification, citation), plus every conflict
  verbatim and the candidate bucket verbatim — no silent-apply gap. Mutation bites
  (zero conflicts; drop one applied entry) each fail a completeness assertion.
- **C — off-switch no-op + attributability/no-coalesce + remediator-not-a-gate: SHIP.**
  `enabled=False` returns before any work; both manifests stay byte-identical; no
  agent-validation records; review_summary None; `enabled` default True (opt-out).
  Applied REQs are `agent-validation`, distinguishable, never coalesced;
  grep found ZERO `operator-confirmation` / `operator_confirmations.jsonl` writes
  (the instr-012 write-restriction holds). No gate/verdict/score/threshold/block/
  calibration logic — the only "gate" hits are "propagate" and the "not a gate"
  disclaimers. No slice-6/7 scope; not bundled adopter-side; the 17 bundle-drift
  guards pass green.

## Non-blocking finding (Panelist A, P8) — design recommendation
Selectively reverting (or a persona `drop` of) a REQ that a live BUG points at
causes the compacting renumber to REUSE that id for a different requirement, so the
stale BUG ref silently **mis-targets** an unrelated REQ rather than dangling. This
is inherent drop semantics (a persona `drop` has the same property), sits outside
this slice's stated revert contract (which round-trips exactly and leaves no
*orphan*), and does not violate the SHIP gate. **Recorded for the design owner:** a
future hardening could scrub/flag BUGs that reference a dropped REQ id before the
compacting renumber, so a stale reference is surfaced rather than silently
re-pointed. Applies equally to Feature D's `drop` move — a general
requirements-pipeline concern, not Feature-H-specific.

## Recorded for the orchestrator
- The 6 Feature H modules (persona_catalog/orchestration/grounding/merge/apply +
  requirements_render) are not bundled adopter-side yet — the execution/live-run
  slice must bundle them.

## Verification
Full suite green (see the instruction output for the count); Python 3.14.6. All 9
Guard-4 tests pass; revert round-trip + BUG remap propagation + off-switch no-op
covered.

**Terminal verdict: SHIP.** The revert round-trips exactly (incl. corrects/drops,
requirements + BUG), the review summary surfaces everything applied, the off-switch
truly no-ops, and no gating/coalesce/later-slice scope crept in.
