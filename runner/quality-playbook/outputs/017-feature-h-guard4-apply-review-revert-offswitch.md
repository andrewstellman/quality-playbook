# Output for 017-feature-h-guard4-apply-review-revert-offswitch.md
**Status:** completed

## Files created / changed
| Path | Note |
|------|------|
| `plugins/.../scripts/persona_apply.py` | **New** — Guard 4: `run_persona_pass` (apply + off-switch + snapshot), `apply_remap_to_bugs`, `build_review_summary`, `revert`, `agent_validation_records`. |
| `bin/tests/test_persona_apply_v160.py` | **New** — 9 tests: apply+tag, BUG remap propagation, review-summary completeness, revert round-trip (all + selective), off-switch no-op, attributability. |
| `docs/process/QPB_v1.6.0_Instruction_017_Self_Council/synthesis.md` | Tracked 3-charter Council synthesis. |
| `runner/.../reviews/017_self_council/{panelist_A,B,C,synthesis}.md` | Gitignored full Council artifacts. |

## Commits made (branch `1.6.0`, local only — never pushed)
- `a6879ce` — Feature H slice 5: Guard 4 apply + review summary + revert + off-switch (+ 9 tests).
- `59bdc58` — tracked self-Council synthesis.

## Acceptance oracle — pass/fail per item
| # | Item | Result |
|---|------|--------|
| 1 | Applied + tagged agent-validation; conflicts/candidates not applied | **PASS** — `ApplyTaggingTests` |
| 2 | Remap propagation: every BUG cross-ref to a renumbered REQ updated; no orphan | **PASS** — `RemapPropagationTests` |
| 3 | Review summary lists every applied change + conflicts + candidates | **PASS** — `ReviewSummaryTests` (no silent-apply gap, Panelist B) |
| 4 | Revert round-trips (drop-one and drop-all) restoring pre-persona incl. UC/BUG links | **PASS** — `RevertRoundTripTests` (byte-exact, Panelist A) |
| 5 | Off-switch: disabled → no personas, no agent-validation changes, pipeline proceeds | **PASS** — `OffSwitchTests` |
| 6 | Attributability: agent-validation distinguishable, never coalesced with operator-confirmation | **PASS** — Panelist C grep + `test_agent_validation_not_coalesced_...` |
| 7 | Existing suite unchanged and green | **PASS** — 2723 / 0 / 13 |

## The apply + tagging
The merge (slice 4) already writes the grounded moves into the manifest tagged `source_type: agent-validation` (Guard 2) with byte-verified citations (Guard 1). `run_persona_pass` wraps that: it snapshots the pre-persona requirements + BUG manifests, runs the merge, propagates the remap to BUG, and builds the review summary. Conflicts and candidate (ungrounded) moves are **not** applied — surfaced only. Off-switch (`enabled=False`) short-circuits before any of this.

## The remap → BUG propagation + its test
schemas.md §7 is explicit: **UC carries no `requirements[]` field — UC→REQ is render-derived one-way**, so a REQ renumber needs no UC propagation. The REQ-id cross-references live in **BUG**: `req_id` (singular) and `covers[]` ("REQ-N/cell-…"). `apply_remap_to_bugs(remap, bugs_manifest)` updates both (`_remap_cover` remaps the `REQ-N` prefix of each cover, preserving the `/cell-…` suffix; malformed/bare/None covers are handled). `test_bug_cross_refs_updated_after_renumber`: an add into an early section shifts the Errors REQ-003 → REQ-004, and the BUG pointing at REQ-003 (`req_id` + `covers`) follows — no orphaned link (Panelist A verified against mixed/suffixed/bare/malformed covers).

## The review-summary shape
`build_review_summary(merge_result, candidate_bucket)` → `{applied[], applied_count, conflicts[], conflict_count, candidates[]}`. Each `applied` entry carries the grounding an operator needs to review/revert: `persona_id`, `move`, `req_id`/`section`/`title`, `reason`, `system_justification`, `citation`, and `source_type: agent-validation`. Every applied change is present (Panelist B confirmed no silent-apply gap by asserting `applied_count` == records actually applied); every conflict is listed verbatim (target, personas, both moves, reason); the candidate bucket is included verbatim.

## The concrete revert operation + its round-trip proof
`revert(pass, bugs, which="all")` restores the pre-persona requirements **and** BUG manifests **byte-exactly** from the snapshot — a full round-trip that undoes not just adds but **corrects** (original content + source_type + citation restored) and **drops** (the removed REQ restored). `revert(pass, bugs, which=[REQ ids])` is the design's "filter by `source_type == agent-validation`, drop the selected records, re-render, re-run the terminal E.6 renumber" operation: it drops the named agent-validation ADD records (a code-derived id in `which` is **ignored** — revert can never remove an original requirement), re-renders to document order, re-runs the renumber, and re-propagates the remap to BUG. Panelist A's 30-check harness confirmed the byte-exact round-trip and both mutation bites (break snapshot-restore; no-op remap) are caught.

## The off-switch no-op proof
`run_persona_pass(..., enabled=False)` returns immediately with the base manifest unchanged, no review summary, and no agent-validation records — the base requirements and BUG manifests are byte-identical before/after (Panelist C deep-equal proof). The `enabled` default is `True` (opt-out, matching the human interview being opt-in). No personas are spawned (the switch gates before the whole pass).

## Downstream attributability
Applied REQs carry `source_type: agent-validation`, distinguishable from `operator-confirmation` and never coalesced (Guard 2). Nothing in this module writes `operator-confirmation` or `operator_confirmations.jsonl` — the instr-012 write-restriction holds (Panelist C grep). So any code/test/fix Phases 3–6 generate from an unreviewed agent-validation REQ is attributable to it and reversible via the review summary + the revert operation; downstream trust never exceeds an operator-reviewed REQ.

## Self-Council
**Full 3-charter Council, unanimous SHIP** (each panelist own worktree; Panelist C's first run died on an API error mid-stream and was cleanly re-run to SHIP). (a) revert round-trip + remap, (b) apply + review-summary completeness, (c) off-switch no-op + attributability + remediator-not-a-gate. Artifacts: gitignored `reviews/017_self_council/` + tracked `docs/process/QPB_v1.6.0_Instruction_017_Self_Council/synthesis.md`.

## §8b Guard 4 / Operator controls — underspecified / notes
- **Selective-revert / drop of a BUG-referenced REQ silently re-points (Panelist A P8).** Because the terminal renumber compacts ids, dropping a REQ (via selective revert OR a persona `drop`) frees its id, which the renumber then REUSES for a different requirement — so a BUG that referenced the dropped REQ silently mis-targets an unrelated one rather than dangling. This is **inherent drop semantics**, shared with Feature D's `drop`, and outside this slice's revert contract (which round-trips exactly and leaves no *orphan*). **Recorded for the design owner:** a future hardening could scrub/flag BUGs referencing a dropped REQ id before the compacting renumber, so a stale reference is surfaced. A general requirements-pipeline concern, not Feature-H-specific.
- **Revert-all uses a snapshot**, not the design's minimal "filter by source_type and drop" — because that minimal form only round-trips *adds* (a corrected/dropped record needs the original to restore). The snapshot form is the complete, correct round-trip; the selective form implements the design's source_type-filter operation for the common add case.

## For the orchestrator — bundle when execution lands
The six Feature H modules (persona_catalog / persona_orchestration / persona_grounding / persona_merge / persona_apply + requirements_render) are **not bundled adopter-side yet** — the persona-execution/live-run slice must add all six to the five bundle-drift sites.

## Feature H progress
guard 2 (012) + catalog (013) + orchestration/isolation (014) + guard 1 grounding (015) + guard 3 merge (016) + guard 4 apply/review/revert/off-switch (017) done — **all four guards + the full safety envelope are complete.** Remaining: maturity disclosure + target-agnostic harness acceptance (slice 6), and the live gap-finding run (slice 7 — needs a live vessel; also the slice that bundles the modules adopter-side).

## Next action expected from orchestrator
Sequence slice 6 (maturity disclosure — the readability-rubric not-yet-functional + advisory-floor residual disclosed on runs that rely on them, à la F-1; and the target-agnostic-harness acceptance item that funds v1.6.1's Feature B binding to the `run_personas` provisioning seam), then slice 7 (the live persona gap-finding run on chi/express/virtio + bundling the modules adopter-side).
