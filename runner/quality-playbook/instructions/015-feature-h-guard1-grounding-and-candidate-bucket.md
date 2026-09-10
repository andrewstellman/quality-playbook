# Instruction 015 — v1.6.0 Feature H slice 3: Guard 1 — grounding + fit-for-this-system + candidate bucket

Feature H is being built across focused slices. Landed so far: Guard 2 (provenance write-restriction, 012), the persona catalog + anchored selection (013), and the orchestration + least-privilege isolation (014, security core). Slice 2's personas emit **raw candidate diff-sets** of interview moves — but nothing yet decides which moves are trustworthy enough to *apply*. This slice builds **Guard 1**, the discipline that separates a **grounded** move (safe to auto-apply later) from a **candidate** move (surfaced for human attention, never written in as a REQ). Guard 1 is the false-positive floor of the whole feature: an agent that rewrites requirements can also hallucinate one, and this is what stops it.

## First: commit the pending design edit
Before starting, the working tree carries an **uncommitted `docs/design/QPB_v1.6.0_Design.md` edit** — the §8b "Concrete enforcement substrate — input staging + tool-restricted sub-agent" paragraph the orchestrator pinned (instruction 014 already cites it as canonical). Commit it as its own standalone design-doc commit on `1.6.0` before your slice work, so the branch's §8b matches what 014 was built against. Do not fold it into a code commit.

## Scope of THIS instruction
**Guard 1 only** — a validator over the raw candidate diff-sets from slice 2 that classifies each `add`/`correct` move as **grounded** or **candidate**. Out of scope: the multi-persona merge (Guard 3, slice 4), auto-apply + review summary + revert + off-switch (Guard 4, slice 5), maturity disclosure + harness factoring (slice 6), the live persona run (slice 7). Stop and file when this slice's acceptance passes.

## Read first — these ARE the spec
- `docs/design/QPB_v1.6.0_Design.md` **§8b Guard 1** end-to-end — the two-part test ((a) cite byte-verified documentation + (b) justify why *this* system needs it), the **candidate/uncertain bucket** for anything ungroundable, and the **"byte-verification is not an injection guard"** rule (grounding must not rest *solely* on content the ingested document controls; a change traceable to injection-shaped content — imperatives to the agent, self-authorizing tier claims — is **candidate-only, never grounded**). Also §8b Verification items **2, 4, 6** (this slice feeds all three).
- `plugins/quality-playbook/skills/quality-playbook/scripts/reference_docs_ingest.py` + `doc_classification.py` — Feature G's `formal_docs_manifest.json` (the Tier-1/2 byte-citable surface). A grounded citation must resolve to a FORMAL_DOC record here.
- `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py` — `citation_verifier`, the **byte-verification** path a grounded citation must pass (the same one the gate re-invokes). Reuse it; do not fork it.
- `plugins/quality-playbook/skills/quality-playbook/scripts/persona_orchestration.py` — slice 2's raw candidate diff-set shape (this slice's input: moves + interview context + any citation the persona offered).
- `references/requirements_interview.md` — the five moves (`add`/`correct` are the ones Guard 1 gates; `confirm` rests on docs/intent not code; `drop` is a removal; `defer` is operator-only).
- `ai_context/DEVELOPMENT_PROCESS.md`.

## The behavior to build (§8b Guard 1 is the spec)

1. **Grounding validator.** For each `add`/`correct` move a persona emits, decide **grounded** vs **candidate**:
   - **(a) Cited + byte-verified.** The move must cite a document that resolves to a Tier-1/2 `FORMAL_DOC` record, and the cited excerpt must **byte-verify** against that source through `citation_verifier` (the existing path — a fabricated or non-matching citation fails). A move with no citation, or a citation that doesn't byte-verify, is **candidate**.
   - **(b) Fit-for-this-system.** The move must justify why *this* system needs the requirement, not merely that some document mentions it. A domain expectation the gathered docs don't establish as *this* system's contract is **candidate** ("a serializer should handle circular refs" is a candidate finding unless the docs make it this library's contract).
   - **Injection resistance (the subtle security part).** Grounding must **not rest solely on content the ingested document controls**. A move whose only support is injection-shaped content — imperatives addressed to the agent ("add REQ X", "confirm this", "ignore the rubric"), self-authorizing tier claims — is **candidate-only, never grounded**, even if that text byte-verifies (byte-verification proves the text exists, not that it's a legitimate contract). This closes the poisoning path at the grounding layer (Feature G's floor closes it at tiering).

2. **The candidate bucket.** Ungroundable moves are recorded in a **candidate/uncertain findings** set for human attention — a first-class output, distinct from grounded moves, never applied as a REQ. It carries the persona, the move, the interview context, and *why* it fell short (no citation / citation failed byte-verify / not fit-for-this-system / injection-shaped). Later slices surface it in the review summary; this slice produces it.

3. **Grounded moves stay tagged.** A grounded move retains the `agent-validation` provenance (Guard 2) and its byte-verified citation, ready for the merge (slice 4) and auto-apply (slice 5). Do not apply or merge here — only classify.

## Acceptance oracle (§8b Verification 2/4/6; mutation-bite the security ones)
1. **Grounding mutation (Verification 4):** an `add` with no citation, or a citation that does not byte-verify, is recorded **candidate-only** — never a grounded REQ. Proven by test.
2. **Fit-for-this-system:** a move citing a real doc that merely *mentions* a general expectation, without establishing it as this system's contract, is **candidate**, not grounded.
3. **Injection mutation (Verification 6, the poisoning path):** a move whose support is injection-shaped content ("add REQ …; confirm it" / self-authorizing tier claim) is **candidate-only**, even when that injected text byte-verifies against the (untrusted) source. No grounded add results.
4. **FP-ceiling seam (Verification 2):** on a fixture whose complete requirement set is known, the count of **grounded** adds that are spurious is **0** (a real gap plus even one spurious grounded add fails). The fixture bound is 0; the live-repo bound stays open (OD-9).
5. **Byte-verification reuse:** grounding uses the existing `citation_verifier` path unchanged (no forked verifier); a legitimately grounded add (cites a Tier-1/2 doc, byte-verifies, fit-for-this-system) is classified grounded.
6. Existing suite unchanged and green.

## Fixture discipline
Do NOT hand-edit golden fixtures to pass. New fixtures (grounded vs candidate classification, the injection-shaped-support case, the fit-for-this-system case, the FP-ceiling-0 fixture) are expected.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight the branch, `pre-flight-aborted` if wrong. Local commits only; **never push/merge**.
- Self-Council per §13. Guard 1 feeds the poisoning oracle, so give the **injection-resistance charter** real teeth (charter a); (b) grounding/byte-verify correctness + fit-for-this-system; (c) candidate-bucket completeness + no merge/apply scope leak. Each mutating panelist in its own worktree. Artifacts under `RUNNER_ROOT/reviews/015_self_council/` + a tracked copy under `docs/process/QPB_v1.6.0_Instruction_015_Self_Council/`.
- Verify the full suite; report counts + Python version.
- Output `outputs/015-feature-h-guard1-grounding-and-candidate-bucket.md`: the grounded-vs-candidate decision rule; each mutation result (no-citation → candidate, injection-shaped-support → candidate even when byte-verifying, fit-for-this-system → candidate); the FP-ceiling-0 fixture result; confirmation the existing `citation_verifier` was reused not forked; the candidate-bucket shape; and anything in §8b Guard 1 you found underspecified.
