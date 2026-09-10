# Instruction 021 — v1.6.0 Feature H: wire the persona pass into the pipeline invocation

Instruction 020 bundled the six persona modules adopter-side, but flagged the gap this instruction closes: **the modules are installed but nothing invokes them.** SKILL.md, the phase prompts, and the run flow do not call the persona pass, so Feature H ships but never *runs* during a QPB pipeline. This instruction makes the persona validation an actual pipeline step — auto-run after Phase 2, opt-out via the off-switch — so an adopter's run (and the eventual live end-to-end test) actually exercises Feature H.

## Design intent (so the invocation point is right)
Per §8b guard 4, persona validation is a **remediator that auto-applies grounded fixes** and is **opt-out** (the off-switch, default enabled — §8b Operator controls). Per §6, this sits at the **post-Phase-2 point**: after the requirements are complete, before Phases 3–6 build tests/reviews on them — the same placement as Feature D's human interview, except Feature H runs automatically (the human interview is opt-in; the agent persona pass is opt-out). So: **after Phase 2 requirements finalize, the pipeline runs the persona pass automatically unless Feature H is disabled for the run.**

## Scope
Wire the invocation only — compose the existing six modules into a single pipeline step and call it at the right point. No new guard logic (the guards exist and are verified). Out of scope: the integrated umbrella Council (next instruction), broader acceptance testing.

## Read first — these ARE the spec
- `docs/design/QPB_v1.6.0_Design.md` **§8b** (guard 4 auto-apply + off-switch; the composed flow selection→orchestration→grounding→merge→apply) and **§6** (post-Phase-2 placement; the interview/validation sits between requirements-complete and Phases 3–6).
- The six modules: `persona_catalog` (select) → `persona_orchestration` (stage + spawn isolated sub-agents) → `persona_grounding` (classify grounded/candidate) → `persona_merge` (union + conflicts + single renumber) → `persona_apply` (`run_persona_pass`: apply + review summary + revert + off-switch) → `requirements_render`.
- `references/requirements_pipeline.md` and the phase prompts (`phase_prompts/phase2.md`, the post-Phase-2 flow) — where the invocation prose goes.
- `references/requirements_interview.md` — Feature D's post-Phase-2 placement (mirror the *position*, not the opt-in trigger).
- `SKILL.md` — the pipeline's top-level flow, where the persona step is announced.
- Instruction 019's output — the live persona spawn pattern (Task sub-agents, staged inputs, tool-restricted, `tool_uses: 0`); this is the runtime spawn the wiring drives.

## The behavior to build
1. **A single composed entry point** that, given a run's artifacts — the classified gathered-docs corpus (Feature G), the rendered `REQUIREMENTS.md`, the rubric — runs the full persona pass: select personas (catalog + anchors) → stage isolated inputs + spawn the tool-restricted persona sub-agents (the slice-2 mechanism / 019 pattern) → classify grounded vs candidate (guard 1) → merge (guard 3) → apply + emit the operator-visible review summary (guard 4), honoring the **off-switch** (default enabled). The composed step reuses the existing modules; it does not reimplement them.
2. **Invocation prose in the pipeline flow** at the post-Phase-2 point: `requirements_pipeline.md` / the relevant phase prompt / SKILL.md instruct the running agent to run the persona pass automatically after Phase 2 requirements finalize (before Phases 3–6), unless Feature H is disabled for the run. The live persona sub-agents are spawned by the running agent via its Task/Agent tool (the substrate), exactly as 019 did — the entry point orchestrates; the harness performs the spawn.
3. **The review summary is a run artifact** the operator sees (written to the run's `quality/` area), listing every applied `agent-validation` change with grounding + conflicts + candidates + the maturity disclosure — so an adopter run surfaces what the personas changed and can revert it.
4. **Off-switch + opt-out** honored end to end: a run with Feature H disabled spawns no personas, writes no agent-validation changes, and proceeds; enabled is the default.

## Test discipline (separate mechanism from live model, like 019)
The live persona spawn needs a live model, so **test the orchestration deterministically** by stubbing the persona-spawn step (inject canned persona diff-sets), and assert the composed step: selects with anchors, stages isolated inputs, classifies grounded/candidate, merges with one renumber, applies + emits the review summary, and the off-switch no-ops the whole step. Do not fake a live run; the genuine live end-to-end is the operator's separate test.

## Acceptance oracle
1. The persona pass is invoked at the post-Phase-2 point (prose wiring present in the pipeline flow + SKILL.md), auto-run, opt-out.
2. The composed entry point runs selection→stage/spawn→grounding→merge→apply end to end (spawn stubbed), producing an applied manifest + a review-summary artifact; provenance + citations intact through the composition.
3. Off-switch: a disabled run produces no persona step, no agent-validation changes; enabled is default.
4. Isolation honored by the composed step (staged inputs only; the spawn is tool-restricted per slice 2).
5. Full suite green.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight; local commits only; **never push/merge**. This touches QPB source (SKILL.md / phase prompts / a composed entry point) — land it directly as the worker.
- Self-Council per §13 — the invocation seam is security-relevant (a wrong invocation could hand a persona un-staged inputs or skip the off-switch): (a) the composed step preserves isolation + off-switch + provenance end to end (no seam regresses a guard); (b) the invocation point is correct (post-Phase-2, before 3–6) and opt-out; (c) no guard logic reimplemented — the existing modules are reused. Each mutating panelist its own worktree. Artifacts under `RUNNER_ROOT/reviews/021_self_council/` + tracked copy under `docs/process/QPB_v1.6.0_Instruction_021_Self_Council/`.
- Verify the full suite; report counts + Python version.
- Output `outputs/021-feature-h-wire-persona-pass-into-pipeline.md`: the composed entry point + where it's invoked in the flow; the review-summary artifact path; the off-switch/opt-out proof; confirmation isolation holds through the composition; and anything underspecified. Note that after this, the integrated umbrella Council (over the now-wired pipeline) and broader acceptance testing remain.
