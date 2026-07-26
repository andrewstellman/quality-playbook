# Output for 021-feature-h-wire-persona-pass-into-pipeline.md
**Status:** completed

## Files created / changed
| Path | Note |
|------|------|
| `plugins/.../scripts/persona_apply.py` | `run_feature_h(...)` — the single composed pipeline step (select → stage/spawn isolated → ground → merge → apply + review summary + off-switch); imports the other persona modules via the sibling loader. |
| `plugins/.../scripts/persona_orchestration.py` | Seam fix: `detect_fabrication` now accepts a structured citation dict (its excerpt) as well as a bare string. |
| `references/requirements_pipeline.md` | § E.9 — the composed persona-pass invocation at the post-Phase-2 point. |
| `plugins/.../phase_prompts/phase2.md` | Post-Phase-2 note: run the persona pass automatically after the human-interview offer (opt-out). |
| `SKILL.md` | Top-level flow: the persona pass runs automatically at the Phase 2→3 boundary. |
| `bin/tests/test_persona_pipeline_v160.py` | **New** — 6 composed-step tests (stubbed spawn). |
| `bin/tests/test_persona_orchestration_v160.py` | +1 dict-citation fabrication-tell test. |
| `bin/tests/test_phase_prompts_externalized.py` | phase2 hash-pin recomputed 13004 → 14199 (documented). |
| `docs/process/QPB_v1.6.0_Instruction_021_Self_Council/synthesis.md` | Tracked 3-charter Council synthesis. |

## Commits made (branch `1.6.0`, local only — never pushed)
- `0b2d85d` — wire the persona pass into the pipeline (composed entry point + invocation prose + seam fix + tests).
- `4e591cd` — tracked self-Council synthesis.

## Acceptance oracle — pass/fail per item
| # | Item | Result |
|---|------|--------|
| 1 | Persona pass invoked at the post-Phase-2 point (prose in the flow + SKILL.md), auto-run, opt-out | **PASS** — E.9 + phase2.md + SKILL.md, all at the Phase 2→3 boundary, opt-out |
| 2 | Composed entry point runs selection→stage/spawn→grounding→merge→apply end to end (spawn stubbed), producing an applied manifest + review-summary artifact; provenance + citations intact | **PASS** — `ComposedPassTests` |
| 3 | Off-switch: disabled → no persona step, no agent-validation changes; enabled default | **PASS** — `OffSwitchThroughCompositionTests` (Panelist A: gates before any spawn) |
| 4 | Isolation honored by the composed step (staged inputs only; tool-restricted spawn) | **PASS** — `test_isolation_honored_through_the_composition` (Panelist A: 30 adversarial assertions) |
| 5 | Full suite green | **PASS** — 2738 / 0 / 13 |

## The composed entry point + where it's invoked
`bin/persona_apply.run_feature_h(target_repo, *, base_manifest, proposed_personas, provision, spawn_persona, formal_docs, staging_root, bugs_manifest=None, domain_specialization=None, enabled=True, write=True)` composes the six modules — **reimplementing no guard** (Panelist C confirmed pure glue):
1. **select** — `persona_catalog.select_personas` (anchored domain + security + AI-selected lens).
2. **stage + spawn (isolated)** — `persona_orchestration.run_personas` stages each persona's declared inputs into an isolated per-persona dir and calls `spawn_persona(persona, staging_dir, tool_config)` — the runtime persona sub-agent spawn (the instruction-019 pattern; the running agent's Task tool, Read-confined, no shell/network). `spawn_persona` is an injected seam; tests stub it with canned diff-sets.
3. **ground** — `persona_grounding.classify_diff_set` (grounded vs candidate) + `candidate_bucket`.
4. **merge + apply + review summary** — `run_persona_pass` (→ `persona_merge`, single terminal renumber, apply tagged `agent-validation`, review summary).
5. **write** — the review summary to `quality/persona_review_summary.json`.

**Invoked** at the post-Phase-2 point in three prose surfaces (Panelist B confirmed consistent placement): `references/requirements_pipeline.md` § E.9 (the composed flow), `phase_prompts/phase2.md` (run automatically after the human-interview offer), and `SKILL.md` (top-level announcement) — the same slot as Feature D's human interview, except **opt-out** (auto-run) vs the interview's opt-in.

## The review-summary artifact path
`quality/persona_review_summary.json` — a run artifact the operator sees, written by `run_feature_h` when the pass runs. It lists every applied `agent-validation` change with its grounding (persona, move, citation, why-this-system), the conflicts, the candidate bucket, and the maturity disclosure. Revertible via `persona_apply.revert`.

## The off-switch / opt-out proof
`run_feature_h(..., enabled=False)` short-circuits the **entire** step: no personas selected or spawned, no merge, no `agent-validation` changes (base manifest byte-unchanged), and **no** review-summary artifact written. `enabled=True` is the default (opt-out). Panelist A adversarially confirmed the off-switch gates **before** any spawn/staging (not after). Pinned by `OffSwitchThroughCompositionTests`.

## Confirmation isolation holds through the composition
Panelist A (30 adversarial assertions with a real impl file + secret + `operator_confirmations.jsonl` planted in the run tree): each per-persona staging dir contains **only** what `provision` returns; the spawn receives a Read-only, staging-rooted, no-shell, no-network tool config; a malicious `provision` trying to stage the human ledger is refused (`IsolationError`); the fabrication-tell flags an unstaged excerpt in both string and dict citation shapes. The composition regresses no guard — isolation, off-switch, provenance, and guard-1 grounding all hold, mutation-confirmed load-bearing.

## The seam fix (surfaced by the composition)
Composing the modules exposed a real seam mismatch: slice-2's `detect_fabrication` expected `move["citation"]` to be a **string** (the raw quote for the fabrication-tell), while slice-3+ uses a structured **dict** citation for byte-verification. The fix makes `detect_fabrication` accept both — a dict citation is checked via its `citation_excerpt`. Panelist C confirmed it is a **strictly-additive compat widening** (the string path is byte-identical; an unstaged excerpt of either shape still flags), not a weakening, and not new guard logic. Pinned by `test_dict_citation_is_handled`.

## Self-Council
**Full 3-charter Council, unanimous SHIP** (each panelist own worktree). (a) the composed step preserves isolation + off-switch + provenance + guard-1 at every seam (30 adversarial assertions, mutation-confirmed); (b) the invocation point is correct (post-Phase-2, before 3–6), opt-out, remediator-not-a-gate, consistent across all three surfaces with no prose/code drift; (c) pure reuse (no guard reimplemented) with a correct additive seam fix. Artifacts: gitignored `reviews/021_self_council/` + tracked `docs/process/QPB_v1.6.0_Instruction_021_Self_Council/synthesis.md`.

## Underspecified / notes
- **The runtime `spawn_persona`.** `run_feature_h` takes the persona spawn as an injected callable — at pipeline-run time the running agent supplies it (spawning a fresh-context, tool-restricted Task sub-agent per instruction 019); tests inject a canned stub. The prose (E.9) says the running agent performs the spawn; the function orchestrates. §8b names the substrate (tool-allowlisted sub-agent) but not the exact `spawn_persona` signature — this slice defines it (`(persona, staging_dir, tool_config) -> raw_diff_set`).
- **`provision` at runtime** wires the classified gathered docs (Feature G) + the rendered `REQUIREMENTS.md` + the rubric into `StagedInput`s; the running agent assembles them per E.9. The default doc input is Feature G's classified corpus.

## Feature H status
With this instruction, Feature H is **fully wired**: an adopter's run selects, spawns (isolated), grounds, merges, applies, and surfaces the persona validation automatically at the Phase 2→3 boundary, opt-out. **Remaining before 1.6.0 ship** (not this slice): the **integrated umbrella Council** over the now-wired pipeline, and **broader 1.6.0 acceptance/release testing**.

## Next action expected from orchestrator
Run the integrated umbrella Council over the composed, now-invoked Feature H pipeline, and the broader 1.6.0 acceptance/release testing. Also still open: set OD-9 from instruction 019's data (0 spurious grounded adds); Feature-G non-plaintext-contract → FORMAL_DOC wiring; chi/express Slice-1 coherence-fixture regeneration; the drop/selective-revert BUG-reference re-point hardening.
