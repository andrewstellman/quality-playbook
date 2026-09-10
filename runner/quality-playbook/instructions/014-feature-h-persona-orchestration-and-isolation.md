# Instruction 014 — v1.6.0 Feature H slice 2: persona sub-agent orchestration + least-privilege isolation

This is the **security core** of Feature H and the most security-critical slice of the release. It builds the fresh-context persona sub-agent execution harness and its **least-privilege isolation**. The isolation is what keeps validation *fitness-for-purpose* (against documented intent) instead of collapsing into the circular *fitness-to-implementation* trap — and what closes the exfiltration surface a persona opens by ingesting untrusted documents. Get this wrong and the whole feature is unsafe; treat §8b's isolation rules as settled and precise.

Instruction 012 landed Guard 2 (provenance write-restriction); 013 landed the persona catalog + anchored selection (the selected set is this slice's input). This slice **spawns and isolates** the selected personas and runs them independently in parallel, each producing a **raw candidate diff-set** of interview moves. It does **not** ground/validate those moves (Guard 1 is slice 3), merge them (Guard 3 is slice 4), or apply them (Guard 4 is slice 5).

## The enforcement substrate is now pinned — build exactly this
§8b's "Concrete enforcement substrate — input staging + tool-restricted sub-agent" paragraph (pinned 2026-07-22) is the spec. Two composed mechanisms so out-of-bounds access is **prevented by construction, not detected**:

1. **Input staging (prevention by absence).** Before a persona is spawned, copy its declared inputs — the gathered docs, the rendered spec, the rubric — into an **isolated per-persona staging directory**. The implementation tree, secrets/credentials, `operator_confirmations.jsonl`, and any out-of-run path are **not present** in that directory. A persona cannot read what was never staged.
2. **Tool allowlist (no lateral authority).** Spawn the sub-agent with **Read only, rooted at the staging directory; no Bash/shell; no network/fetch tools.**
3. **Fabrication-tell (backstop, not primary control).** A persona whose output references implementation detail it could only have gotten from source is a detected failure.

## Scope of THIS instruction
**Orchestration + isolation only.** In scope: input staging, the tool-restricted spawn, parallel independent execution of the selected personas over the Feature D interview, each emitting a raw candidate diff-set with per-move interview context, and the fabrication-tell detector. Out of scope: grounding validation (slice 3), the merge + conflict surfacing (slice 4), auto-apply + review summary + revert + off-switch (slice 5), the live gap-finding run (slice 7). Build the orchestration **target-agnostic** (context provisioning as a per-target parameter) so slice 6 can factor it for v1.6.1's Feature B — but the full harness-abstraction acceptance is slice 6; here, just don't hard-code H-specific inputs into the spawn seam.

## Read first — these ARE the spec
- `docs/design/QPB_v1.6.0_Design.md` **§8b** — the isolation paragraphs ("Input isolation — load-bearing", "Isolation is least-privilege", and the pinned "Concrete enforcement substrate"), guard 3's independence ("in parallel, each blind to the others' writes"), and **Verification item 3** (the isolation/least-privilege oracle). Also §8b's "target-agnostic … infrastructure" paragraph.
- `plugins/quality-playbook/skills/quality-playbook/scripts/persona_catalog.py` — slice 1's `select_personas` / selection manifest: this slice's input (which personas to spawn + the domain specialization).
- `references/requirements_interview.md` — the interview a persona descends as the operator (the five moves, the three stages). A persona run *is* this protocol driven by a sub-agent over the staged inputs.
- `plugins/quality-playbook/skills/quality-playbook/scripts/reference_docs_ingest.py` — how the gathered docs + rendered spec are produced/located, so you know what to stage.
- `AGENTS.md` / `references/` on how the QPB skill spawns sub-agents (the self-Council protocol already spawns Task sub-agents — the same mechanism, with a restricted tool set, is the persona spawn).
- `ai_context/DEVELOPMENT_PROCESS.md`.

## The behavior to build (§8b isolation + substrate paragraphs are the spec)

1. **Stage inputs per persona.** Given the selected personas (slice 1) and the run's artifacts, materialize an isolated staging directory per persona containing exactly: the gathered docs (Feature G's classified corpus / the Tier-context the persona ramps on), the rendered spec (`REQUIREMENTS.md`), and the rubric. Nothing else — assert the impl tree, secrets, and `operator_confirmations.jsonl` are absent. Staging is content-keyed / reproducible in the spirit of the other v1.6.0 manifests where sensible.

2. **Spawn tool-restricted persona sub-agents.** Each persona is a fresh-context sub-agent spawned with Read rooted at its staging dir, **no Bash, no network/fetch**. The role prompt adopts the lens (domain specialization from slice 1; the anchored security lens; etc.) and instructs the persona to descend the interview and emit moves. The spawn seam takes context provisioning as a parameter (target-agnostic — don't bake H's specific input set into the mechanism).

3. **Run independently, in parallel, blind to each other.** Personas do not see each other's writes (guard 3 independence). Each emits a **raw candidate diff-set**: its interview moves (`confirm`/`correct`/`add`/`drop` — `defer` is operator-only, not a persona move) against the same base manifest, each move carrying the interview context needed by later slices (which REQ/section, the persona's stated reason, any citation the persona offers). Do **not** validate grounding here — that's slice 3; a move emitted here is a *candidate* until slice 3 grounds it.

4. **Fabrication-tell detector.** Implement the backstop: a persona whose emitted moves reference implementation detail not present in its staged inputs is flagged as an isolation failure. This is the second line behind staging + allowlist.

## Acceptance oracle (§8b Verification 3 is the security oracle; mutation-bite it)
1. **Staging correctness:** the per-persona staging dir contains exactly docs + rendered spec + rubric; the impl tree, secrets, and `operator_confirmations.jsonl` are provably absent — asserted by test.
2. **Least-privilege enforced, not detected (mutation):** a persona sub-agent configured for a run **cannot** read the implementation tree, secrets, `operator_confirmations.jsonl`, or out-of-run paths (they are not in its staging dir and it has no shell/network to reach them). Prove prevention — e.g. a persona instructed to read the impl tree finds nothing there / has no tool to reach it — not merely that a detector fired afterward.
3. **Fabrication-tell fires:** a persona whose output references source it was not given is detected as an isolation failure (the backstop, tested independently of mechanism 1–2).
4. **Independence:** personas run in parallel each blind to the others' candidate diff-sets (no cross-contamination of one persona's moves into another's context).
5. **Raw diff-set shape:** each persona emits a well-formed candidate diff-set of interview moves with the context later slices need; no grounding/merge/apply happens here.
6. **Target-agnostic seam:** the spawn/orchestration takes context provisioning as a parameter (show the seam Feature B will bind to); no H-specific input set is hard-coded into the mechanism.
7. Existing suite unchanged and green.

## Fixture discipline
Do NOT hand-edit golden fixtures to pass. New fixtures (staging assertions, the isolation-prevention mutation, the fabrication-tell, an independence check, a sample raw diff-set) are expected. If exercising a real persona sub-agent needs a live model, isolate that behind a seam and test the **mechanism** (staging + tool restriction + fabrication-tell) deterministically here; the live persona gap-finding run is slice 7, not this slice — do not fake a live run.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight the branch, `pre-flight-aborted` if wrong. Local commits only; **never push/merge**.
- **Full 3-charter self-Council per §13 — this is a security-critical slice, no shortcut.** Charters, each mutating panelist in its own worktree:
  - **(a) Isolation is prevention, not detection:** verify staging omits the impl tree/secrets/`operator_confirmations.jsonl`/out-of-run paths and the tool-allowlist removes shell + network, so out-of-bounds access is impossible-by-construction; the fabrication-tell is only the backstop. Mutation-bite: attempt each out-of-bounds access and confirm it cannot succeed.
  - **(b) Independence + diff-set integrity:** personas are genuinely blind to each other; the raw diff-set shape is well-formed and carries what slices 3–5 need; no grounding/merge/apply leaked in.
  - **(c) Substrate + reuse + scope:** the staging + tool-restricted-spawn matches the §8b pinned substrate; the spawn seam is target-agnostic (Feature B can bind); no OS/network-sandbox scope crept in (that's v1.8.0).
  - Artifacts under `RUNNER_ROOT/reviews/014_self_council/` + a tracked copy under `docs/process/QPB_v1.6.0_Instruction_014_Self_Council/`.
- Verify the full suite; report counts + Python version.
- Output `outputs/014-feature-h-persona-orchestration-and-isolation.md`: the staging layout + the absence assertions; the exact tool-restriction applied at spawn; the isolation-prevention mutation results (each out-of-bounds access proven impossible); the fabrication-tell; the independence check; the raw diff-set shape; the target-agnostic seam; and anything in §8b's isolation/substrate paragraphs you found underspecified.
