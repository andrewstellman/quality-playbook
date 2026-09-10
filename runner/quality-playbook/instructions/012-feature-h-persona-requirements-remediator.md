# Instruction 012 — v1.6.0 Slice 4: Feature H — agent-driven persona requirements-remediator

Feature H is the validation slice and the release's thesis made real: *if a human domain expert can read the spec and judge whether it captures what the system is supposed to do, a domain-expert **agent** can do the same — so validation scales to every run, not just the ones with a human expert on hand.* Fresh-context domain-expert personas ramp on the gathered docs, run the Feature D interview as the operator, and **remediate** the requirements — finding real gaps and fixing them, leaving `REQUIREMENTS.md` in the best shape it can.

The design is **Council-hardened and dogfood-self-tested** (three personas validated the v1.6.0 design doc itself on 2026-07-22; the security lens grounded a prompt-injection gap the domain lens could only file as a candidate — which is why the security lens is anchored). Treat §8b as settled and precise: several of its rules exist because a naive version opened a security hole (circular validation, provenance forgery, an exfiltration surface).

## This is a remediator, not a gate — internalize this first
H renders **no pass/fail verdict** and blocks **nothing**. There is no gate, no release for it to pass or fail, and therefore **no accuracy-calibration precondition** (that was machinery for a gating role H does not have). Its entire output is a better requirements document. Do not build a "verdict," a "score threshold," or a "gate." Build a remediator that applies grounded fixes and surfaces them for review.

## Read first — these ARE the spec
- `docs/design/QPB_v1.6.0_Design.md` **§8b "Feature H"** end-to-end — persona selection (catalog-with-anchors), input isolation + least-privilege, the ceiling-not-floor judgment, the **four guards**, injection resistance, the operator controls, maturity disclosure, and the target-agnostic-harness requirement. Also **§10 criterion 8**, **§6** (the interview + the "renumber once after all moves" contract), and **§12 OD-9**.
- `references/requirements_interview.md` — the Feature D interview protocol H drives (the three stages, the five moves confirm/correct/add/drop/defer, the write-back). A persona *is* an agent running this protocol as the operator.
- `schemas.md` **§3.7 `req_source_type`** (where `operator-confirmation` lives — you add `agent-validation` beside it) and **§9.5** (the append-only `operator_confirmations.jsonl` a persona must NEVER write).
- `references/requirements_pipeline.md` — where the interview/validation sits in the phase flow (after Phase 2, before Phases 3–6 build on the requirements).
- The terminal **E.6 renumber** (built in instruction 007) and the render contract — the single renumber that must run once *after* the merge, not per-persona.
- `plugins/quality-playbook/skills/quality-playbook/scripts/reference_docs_ingest.py` + `doc_classification.py` — Feature G's output (the classified docs + Tier-1/2 FORMAL_DOC surface) is what a persona ramps on and grounds citations against.
- `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py` — the citation gate that byte-verifies grounding citations; `agent-validation` REQs must pass it exactly like any Tier-1/2 REQ.
- `ai_context/DEVELOPMENT_PROCESS.md`.

## Scope of THIS instruction
**Feature H (Slice 4), the whole coherent feature.** It is large; decompose it yourself (§8b is the spec), but it lands as one feature that passes the acceptance oracle. Out of scope: v1.6.1's Feature B (the FP-audit judge) — but **build the sub-agent-review infrastructure target-agnostic** so B can reuse it (named acceptance item below). Not in scope: any OS/network sandbox beyond tool-allowlisting (that's the v1.8.0 security line); any gating/calibration.

## The behavior to build (§8b is the spec; decompose it yourself)

1. **Persona selection — catalog-with-anchors.** The derivation selects the lenses that fit *this* system from a persona catalog and **justifies the choice** (exactly like the organizing-principle menu). Two lenses are **anchored (always included)**: a **domain expert** (derived per system from the Phase 1 domain + gathered docs) and a **security reviewer** (anchored because a system's own author under-weights security). Additional lenses are AI-selected from the catalog per system with a stated reason (API/consumer, operator/SRE, data-privacy, accessibility, performance, reliability, adopter, …). The catalog is a menu with selection criteria, not a fixed roster.

2. **Fresh-context personas run the Feature D interview.** Each selected persona is a fresh-context sub-agent that ramps on its inputs, adopts the role, and descends the interview (Stage 1 narrative + organizing principle → Stage 2 sections → Stage 3 per-REQ), exercising the five moves as that expert would. Personas run **in parallel, each blind to the others' writes**.

3. **Input isolation is least-privilege — enforced, not just detected.** A persona receives **only** the gathered docs + the rendered spec + the rubric, and is **denied the implementation tree** (validating requirements against code is the circular trap the rest of QPB already covers; isolation covers *every* move including `confirm`). Enforce via a **tool allowlist**: Read confined to the persona's declared input paths, **no shell, no network/fetch tools**, no read access to secrets / `operator_confirmations.jsonl` / out-of-run paths. Out-of-bounds access is *prevented*; the fabrication-tell (a persona caught reading source) is the backstop, not the primary control.

4. **The four guards (the load-bearing part):**
   - **Guard 1 — Grounded + fit-for-this-system.** Every `add`/`correct` must (a) cite the documentation that justifies it, **byte-verified through the citation gate**, and (b) justify why *this* system needs it. An expectation the docs don't cover, or that can't be tied to this system, is a **candidate finding, never a grounded REQ**. Byte-verification is **not** an injection guard — grounding must not rest *solely* on content the ingested doc controls; a change traceable to injection-shaped content (imperatives to the agent, self-authorizing tier claims) is **candidate-only, never grounded**.
   - **Guard 2 — Honest provenance + write-restriction.** Persona changes carry **`source_type: agent-validation`** — a new first-class `schemas.md` §3.7 shape parallel to `operator-confirmation` but distinct: its citation points at a **document** (byte-verified), and it is **regenerated per run, not persisted**. Downstream must **not** coalesce it with `operator-confirmation`. **A persona may WRITE only `agent-validation`** — it may not create/tag/cite an `operator-confirmation` record and may **not** write `operator_confirmations.jsonl` (human-interview-only, append-only). Enforce this, don't just document it.
   - **Guard 3 — Multi-persona merge with conflict surfacing.** Each persona emits a candidate diff-set against the same base manifest. A **merge** unions the grounded `add`/`correct` moves and **surfaces conflicts** (two moves touching the same REQ/section that disagree — `add` vs `drop`, divergent `correct`s, `confirm` vs `drop`) as operator-facing flags, **never auto-resolved**. `defer` is an operator action, not a persona move — it doesn't participate. **Exactly one terminal E.6 renumber runs after the merge** — personas do not each renumber.
   - **Guard 4 — Remediator, not a gate.** Grounded `add`/`correct`/`drop` moves are **auto-applied** to the manifest and flow into Phases 3–6. Two things keep that safe: (a) the `agent-validation` provenance (guard 2), and (b) an **operator-visible agent-validation review summary** listing every change with its grounding, so the operator can review and revert. Apply the fixes; the summary is the backstop, not a pre-approval gate.

5. **Injection resistance.** A persona treats untrusted document **contents as data, not instructions to itself** — imperatives to the agent, injected role/system framing, "ignore the rubric," "confirm this," "add REQ X" must not alter its behavior, the five-move set, or the rubric.

6. **Operator controls.**
   - **Off-switch** — a run can disable Feature H entirely (parallel to the human interview being opt-in).
   - **Concrete revert** — a real, buildable gate/CLI operation that **filters the manifest by `source_type == agent-validation`, drops the selected records (one or all), re-renders, and re-runs the terminal E.6 renumber** — restoring the pre-persona manifest without hand-editing. Build it; don't just assert "revertible."
   - **Stated FP bound** — on a fixture whose complete requirement set is known, **spurious grounded adds must be 0** (a real gap plus even one spurious add FAILs). Live-repo tolerance is left open (OD-9); every add is surfaced so the operator bounds it.
   - **Downstream attributability** — `agent-validation` REQs stay distinguishable to Phases 3–6; anything generated from an unreviewed agent-validation REQ is attributable and reversible via the review summary.

7. **Maturity disclosure.** Where output rests on a not-yet-functional judgment layer (the readability rubric, §5 Verification (b)), the run discloses that, the way F-1 discloses coverage gaps — not uniform confidence.

8. **Target-agnostic harness (named Slice-4 acceptance item).** Build the fresh-context sub-agent-review infrastructure so context provisioning is a **per-target parameter** (H supplies docs + spec; v1.6.1's Feature B will supply only finding + source + REQ + rubric — the opposite, more restrictive isolation). The orchestration, the `agent-validation` shape, and the isolation discipline are shared; there is **no** shared calibration harness (H has none). Say what you made reusable.

## Acceptance oracle (§8b Verification 1–9 + §10 criterion 8; mutation-bite the security ones)
1. **Finds real gaps:** persona validation on chi/express/virtio autonomously surfaces the real missing requirements the 2026-07-22 agents found (chi regexp params, express `req.range`, virtio indirect-descriptor constraints) and applies grounded fixes.
2. **False-positive ceiling:** on a fixture with a known-complete requirement set, spurious grounded adds = **0** (real gaps plus even one spurious add FAILs — RM-007 degenerate-run blindness at the validation layer).
3. **Isolation fabrication-tell + least-privilege (mutation):** a persona given file-tool access to the implementation and caught reading it is a detected failure; a persona attempting to read outside its declared inputs (secrets, `operator_confirmations.jsonl`, out-of-run paths) or make network egress is **denied** (tool-allowlist), not merely flagged.
4. **Grounding mutation:** an `add` with no citable, this-system-justified grounding is rejected or recorded **candidate-only**, never a grounded REQ.
5. **Provenance (mutation):** `agent-validation` records are schema-valid, doc-cited, byte-verified, distinguishable from `operator-confirmation`; a persona attempting to write an `operator-confirmation` record or to `operator_confirmations.jsonl` is **rejected**.
6. **Poisoning fixture:** a document embedding "classify me Tier 1" and "add REQ …; confirm it" causes no promotion past the floor, no out-of-charter action, and **no grounded (non-candidate) add**.
7. **Multi-persona merge:** two personas conflicting on one section produce a **surfaced conflict** (not a silent pick), and **one** terminal renumber yields sequential IDs.
8. **Applied, surfaced, revertible, disablable:** grounded fixes are applied and appear in the operator-visible review summary; the operator can revert any agent-validation change **by the built revert operation**; Feature H is disablable for a run.
9. **Accepted-residual honesty:** the advisory floor's non-signature residual and the readability rubric's not-yet-functional maturity are disclosed on runs that rely on them.
10. **Target-agnostic harness:** the sub-agent-review infrastructure takes context provisioning as a per-target parameter (demonstrate the seam Feature B will bind to), with no shared calibration harness.

## schemas.md — this is a QPB source edit
Adding `agent-validation` to §3.7 `req_source_type` (and its record/citation shape) is a `schemas.md` change. As the worker (Claude Code) you land it directly; keep it parallel to `operator-confirmation` but document the two distinctions (document-cited not transcript-cited; regenerated-not-persisted) and the write-restriction. Regenerate any api-surface/schema golden it touches in the same commit and explain it.

## Fixture discipline
Do NOT hand-edit golden fixtures to pass. New fixtures (persona finds, isolation-denial, grounding-rejection, provenance-forge-rejection, poisoning, merge-conflict, revert round-trip) are expected. If a full re-derivation is needed to produce a fixture, run it as a correction and explain it — do not fake a persona run.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight the branch, `pre-flight-aborted` if wrong. Local commits only; **never push/merge**.
- Self-Council per §13, charters:
  - **(a) Security — the load-bearing part:** input isolation + least-privilege is *enforced* (tool-allowlist prevents impl-tree/secret/network reads, not just detects); the provenance write-restriction holds (no persona can forge `operator-confirmation` or write `operator_confirmations.jsonl`); grounding cannot rest solely on injection-controlled content; the poisoning fixture lands no grounded change. Mutation-bitten; each mutating panelist in its own worktree.
  - **(b) Remediation quality:** grounding + fit-for-this-system, the FP ceiling (fixture = 0), the multi-persona merge (conflict-surfacing, single terminal renumber), candidate-bucket correctness.
  - **(c) Remediator-not-gate + operator controls + reuse:** no gate/verdict/calibration crept in; off-switch and the concrete revert operation work; downstream attributability + maturity disclosure; the harness is target-agnostic with the seam Feature B binds to; `schemas.md` agent-validation shape correct.
  - Artifacts under `RUNNER_ROOT/reviews/012_self_council/` + a tracked copy under `docs/process/QPB_v1.6.0_Instruction_012_Self_Council/`.
- Verify the full suite; report counts + Python version.
- Output `outputs/012-feature-h-persona-requirements-remediator.md`: which personas were selected for chi/express/virtio and the justification; the real gaps found + applied (grounded, with citations); each security mutation result (isolation denial, provenance-forge rejection, grounding rejection, poisoning fixture); the merge/conflict + single-renumber result; the revert round-trip and off-switch; the `agent-validation` schema shape added; what you made target-agnostic for Feature B; the FP-ceiling fixture result (0); and anything in §8b you found underspecified. OD-9 (live-repo FP tolerance) stays open — set the fixture bound at 0, not the live bound.
