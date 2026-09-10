# Instruction 017 — v1.6.0 Feature H slice 5: Guard 4 — auto-apply + review summary + concrete revert + off-switch

This slice completes the **safety envelope** around Feature H's remediation. The merge (slice 4) produced a `MergeResult` (applied grounded moves + conflicts + a renumber `remap`). This slice **applies** those grounded moves so they flow into Phases 3–6, and builds the three operator controls that make auto-apply safe rather than silent: an **operator-visible review summary**, a **concrete revert operation**, and an **off-switch**. Remember the frame: **H is a remediator, not a gate** — it applies fixes and shows its work; the review summary is the backstop, not a pre-approval gate.

## Scope of THIS instruction
**Guard 4 + the operator controls** — apply the merged grounded moves (with the remap propagated to cross-referencing manifests), emit the review summary, build the revert operation, and the off-switch. Out of scope: maturity disclosure + target-agnostic harness factoring (slice 6); the live persona run (slice 7). Stop and file when this slice's acceptance passes.

## Read first — these ARE the spec
- `docs/design/QPB_v1.6.0_Design.md` **§8b Guard 4** ("A remediator, not a gate" — grounded moves auto-applied + the operator-visible review summary) and the **"Operator controls"** paragraph (off-switch; the **concrete revert** — "filter the manifest by `source_type == agent-validation`, drop the selected records, re-render, and re-run the terminal E.6 renumber"; the stated FP bound; downstream attributability). Also §8b Verification item **8**.
- `plugins/quality-playbook/skills/quality-playbook/scripts/persona_merge.py` — slice 4's `MergeResult` (`applied`, `conflicts`, `held_out`, `remap`, `manifest`): this slice's input. The **`remap`** (old REQ id → new id from the single terminal renumber) is load-bearing for cross-manifest traceability below.
- `plugins/quality-playbook/skills/quality-playbook/scripts/requirements_render.py` — the extracted terminal E.6 renumber (slice 4) the revert operation re-runs.
- `schemas.md` — the `UC` and `BUG` record shapes and **how they cross-reference REQ ids** (the traceability that the renumber remap must preserve), plus the `agent-validation` `req_source_type` (Guard 2).
- `references/requirements_pipeline.md` — where apply sits and how Phases 3–6 consume the manifest (so `agent-validation` REQs stay attributable downstream).
- `ai_context/DEVELOPMENT_PROCESS.md`.

## The behavior to build (§8b Guard 4 + Operator controls are the spec)

1. **Auto-apply the merged grounded moves.** The `MergeResult.applied` moves are written into the manifest tagged `source_type: agent-validation` (Guard 2) with their byte-verified citations (Guard 1), and flow into Phases 3–6. Conflicts and candidate (ungrounded) findings are **not** applied — they are surfaced only (below).

2. **Propagate the renumber remap to cross-referencing manifests (traceability — the worker's slice-4 flag).** The single terminal renumber reassigns REQ ids; any `UC`/`BUG` record (separate manifests) that cross-references a REQ id **must be updated via `MergeResult.remap`** so traceability does not break. This is a correctness requirement, not optional: a renumber that silently orphans UC→REQ / BUG→REQ links is a defect. Test the propagation.

3. **Operator-visible review summary.** Emit a summary listing **every** applied `agent-validation` change with its grounding (persona, move, citation, why-this-system), **plus** the surfaced conflicts and the candidate bucket — the "surface, don't silently apply" discipline (modeled on Feature G's citable-promotion manifest). This is what the operator reviews after an auto-applied run.

4. **Concrete revert operation — build it, don't just assert "revertible".** A real gate/CLI operation that: **filters the manifest by `source_type == agent-validation`, drops the selected records (one, or all), re-renders, and re-runs the terminal E.6 renumber** — and **re-propagates the remap to UC/BUG** — restoring the pre-persona manifest without hand-editing. All ingredients exist (the provenance tag, the content-keyed manifest, the terminal renumber, the remap); compose them into one operation. A full revert must round-trip: manifest after revert == manifest before the persona pass (modulo deterministic renumber).

5. **Off-switch.** A run can disable Feature H entirely (parallel to the human interview being opt-in) — no personas spawned, no agent-validation changes, the pipeline proceeds without the persona pass. Prove the disabled path does nothing.

6. **Downstream attributability.** `agent-validation` REQs stay distinguishable to Phases 3–6, so any code/test/fix generated from an as-yet-unreviewed agent-validation REQ is attributable to it and reversible via the review summary; downstream trust in an agent-validation REQ never exceeds an operator-reviewed one (do not coalesce it with `operator-confirmation` — Guard 2).

## Acceptance oracle (§8b Verification 8; test the revert round-trip and the remap propagation hard)
1. **Applied + tagged:** merged grounded moves are applied to the manifest as `source_type: agent-validation` and appear in Phases 3–6 input; conflicts/candidates are not applied.
2. **Remap propagation:** after the terminal renumber, every UC/BUG cross-reference to a renumbered REQ is updated via `remap` — no orphaned/dangling REQ link. Proven by a test with UC/BUG records pointing at REQs that get renumbered.
3. **Review summary:** lists every applied agent-validation change with grounding + the conflicts + the candidate bucket; nothing applied is missing from it.
4. **Revert round-trips:** the revert operation drops agent-validation records (one and all), re-renders, re-runs the renumber + remap, and restores the pre-persona manifest (and UC/BUG links) — asserted by an equality/round-trip test, not just "records dropped."
5. **Off-switch:** a run with Feature H disabled spawns no personas and produces no agent-validation changes; the pipeline proceeds.
6. **Attributability:** agent-validation REQs are distinguishable downstream and never coalesced with operator-confirmation.
7. Existing suite unchanged and green.

## Fixture discipline
Do NOT hand-edit golden fixtures to pass. New fixtures (apply + tag, the UC/BUG remap-propagation case, the review summary, the revert round-trip, the off-switch no-op) are expected.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight the branch, `pre-flight-aborted` if wrong. Local commits only; **never push/merge**.
- Self-Council per §13 — correctness-critical (a botched revert or a dropped cross-reference silently corrupts the manifest H exists to improve). Charters: (a) the **revert round-trips** exactly (drop-one and drop-all both restore pre-persona state incl. UC/BUG links) and the **remap propagation** leaves no orphaned cross-reference; (b) apply correctness + review-summary completeness (every applied change surfaced, conflicts + candidates included); (c) off-switch truly no-ops + downstream attributability/no-coalesce + no gating/verdict crept in (remediator, not a gate). Each mutating panelist in its own worktree. Artifacts under `RUNNER_ROOT/reviews/017_self_council/` + a tracked copy under `docs/process/QPB_v1.6.0_Instruction_017_Self_Council/`.
- Verify the full suite; report counts + Python version.
- Output `outputs/017-feature-h-guard4-apply-review-revert-offswitch.md`: the apply + tagging; the remap→UC/BUG propagation + its test; the review-summary shape; the revert operation + its round-trip proof; the off-switch no-op proof; downstream attributability; and anything in §8b Guard 4 / Operator controls you found underspecified.
