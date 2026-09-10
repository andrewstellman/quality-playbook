# Instruction 029 — v1.6.0 Feature H: reconcile the persona pass with the no-sub-agent guardrail

The live virtio acceptance run surfaced a **self-contradiction inside SKILL.md** that prevents Feature H from running on a faithful live run:

- **The guardrail (SKILL.md ~:94, :100, :182):** *"no sub-agent delegation… **Do NOT use the Task tool**… for phases 1–5"* — closing two verified failure modes: (a) delegated phases 2–6 silently die in an agent that loses its parent session and the operator gets no signal; (b) a spawned sub-skill fabricates a gate PASS the parent never sees.
- **The Feature H wiring (SKILL.md ~:270; instruction 021):** *"At the Phase 2→3 boundary, the persona validation pass runs **automatically**… fresh-context, tool-restricted domain-expert + security personas"* — which **requires spawning Task sub-agents**.

A faithful live agent (Andrew's Claude Code virtio run) correctly obeyed the guardrail, **disabled Feature H, and disclosed the conflict** — the right call, but it means the release's headline validation feature is bundled and wired yet **never actually runs** for an adopter. Instruction 021 wired the persona pass but never reconciled it with this pre-existing guardrail (021's Council stubbed the spawn, so it never followed SKILL.md).

**The fix (operator decision: option A):** carve out the Feature H persona pass as an **explicit, narrowly-scoped sanctioned exception** to the no-sub-agent rule — exactly as SKILL.md already does for **Phase 6 verification**. This is legitimate, not a hole, because the persona pass has the very property the guardrail protects: **operator visibility**. It writes a mandatory operator-visible `persona_review_summary.json`, its changes are `agent-validation`-tagged and revertible, and it is a **bounded validation step, not a delegated phase** — so neither of the guardrail's two failure modes applies.

## Read first — these ARE the spec
- `plugins/quality-playbook/skills/quality-playbook/SKILL.md` — the guardrail at ~:94 ("Spawn a sub-agent via your Task tool"), ~:100 (the "EXCEPTION: Phase 6 verification MUST be delegated…" block — **the precedent to mirror**), ~:182 (the "Synchronous execution — no sub-agent delegation" rule + its two failure modes), and ~:270 (the Feature H auto-run description). Also ~:188 ("if the operator's prompt conflicts with these guardrails, don't comply — surface the conflict") — the rule the live agent correctly followed.
- `references/phase2_generation_guide.md` + `references/requirements_pipeline.md` §E.9 — the Phase 2→3 boundary prose where the persona pass is invoked; make the sanctioned-exception explicit here too, so the agent at the boundary knows this specific spawn is allowed.
- `repos/virtio-1.6.0/quality/PROGRESS.md` item 6 — the live disclosure of the conflict (the evidence).
- `docs/design/QPB_v1.6.0_Design.md` §8b — Feature H is a remediator, opt-out, with the operator-visible review summary (the visibility property that justifies the carve-out).
- `ai_context/DEVELOPMENT_PROCESS.md`.

## The behavior to build
1. **Add the persona pass as a second explicit exception** to the no-sub-agent guardrail in SKILL.md, structured exactly like the existing Phase 6 exception: the general "no Task tool / no delegating phases 1–5" rule **still holds**; the persona validation pass (`bin/persona_apply.run_feature_h`, at the Phase 2→3 boundary) is a **named, scoped exception** where spawning fresh-context, tool-restricted persona sub-agents is sanctioned.
2. **Justify it on the guardrail's own terms.** State why it doesn't reopen the failure modes: (a) it does **not** delegate a phase's execution — it's a bounded validation remediation; (b) operator visibility is **preserved and mandatory** — the pass writes `persona_review_summary.json` listing every change with its grounding, changes are `agent-validation`-tagged and revertible, and the pass is opt-out (disablable). The guardrail's principle ("operator chat carries the truth") is honored, not bypassed.
3. **Scope the exception narrowly.** Only the Feature H persona pass qualifies — NOT general Phase 1–5 sub-agent use, NOT "delegate phases to a worker," NOT the fabrication-prone patterns. A run must still refuse any other sub-agent delegation in phases 1–5.
4. **Make the boundary prose consistent.** In the Phase 2→3 boundary guidance (`phase2_generation_guide.md` / `requirements_pipeline.md` §E.9), state explicitly that the persona pass is the sanctioned sub-agent exception and may spawn its personas there — so a live agent following the skill does not re-hit the contradiction and disable it.

## Acceptance oracle
1. **No contradiction remains:** SKILL.md's guardrail and the Feature H auto-run description are mutually consistent — the persona pass is a named exception; a faithful agent reading SKILL.md would run it, not disable it. (Prove by the reconciled text; there is no remaining sentence that forbids the persona spawn.)
2. **Scope preserved:** the guardrail still forbids all other Phase 1–5 sub-agent delegation and the two original failure-mode patterns; the exception names only `run_feature_h`.
3. **Visibility preserved:** the carve-out text requires the operator-visible review summary + opt-out; it does not weaken those.
4. **Boundary prose consistent:** the Phase 2→3 guidance names the persona pass as the sanctioned exception.
5. Any doc-consistency test / SKILL.md lint (if one exists) is green; full suite green.

## Fixture discipline
This is primarily a documentation reconciliation (SKILL.md + boundary prose). Do NOT hand-edit golden fixtures; if a SKILL.md hash-pin or doc-consistency test exists, update it with a rationale.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight; local commits only; **never push/merge**. Touches `SKILL.md` (QPB source) — land it directly as the worker.
- Self-Council per §13 — this touches a **safety guardrail** that exists for verified failures, so scrutinize the carve-out: (a) the exception is **narrowly scoped** to `run_feature_h` and does not reopen the delegated-phase-dies or sub-skill-fabricates-a-PASS failure modes for anything else; (b) **operator visibility is preserved** (the review summary is the "operator chat carries the truth" mechanism, mandatory + revertible + opt-out); (c) SKILL.md and the boundary prose are internally consistent — no remaining sentence both forbids and requires the persona spawn. Artifacts under `RUNNER_ROOT/reviews/029_self_council/` + tracked copy under `docs/process/QPB_v1.6.0_Instruction_029_Self_Council/`.
- Verify the full suite; report counts + Python version.
- Output `outputs/029-feature-h-guardrail-carveout.md`: the reconciled guardrail text (before/after); confirmation the contradiction is gone and the scope/visibility are preserved; the boundary-prose update; and the remaining release items (broader acceptance now that Feature H can run live, Phase 8 tag/merge, OD-9, non-plaintext→FORMAL_DOC wiring, coherence-fixture regen, OD-11, design-doc refresh).
