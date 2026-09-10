# Instruction 024 — v1.6.0 Feature G: wire the LLM classifier + make the silent failures loud

Instruction 023 fixed one half of the virtio failure (the authoritative spec is no longer mis-floored). This instruction fixes the **other half**, which the external review (Fable Q6) flagged as the *bigger* half: in the virtio run, four of six docs came out Tier 4 with *"no classifier tier assigned; Tier 4 on ambiguity"* — because **the LLM classifier was never wired into the pipeline**, so every non-floored doc silently defaulted to Tier 4. Combined with the mis-floor, the entire corpus collapsed to Tier 4 — **zero citable documents** — and the run said nothing. QPB's own house rule is that *a degraded-capability path that silently continues is the failure mode.* So: wire the classifier, and make its absence/failure and a zero-citable corpus **loud**.

## Read first — these ARE the spec
- `~/Documents/AI-Driven Development/Quality Playbook/Reviews/QPB_v1.6.0_Simplification_Fable_Review_Response.md` — **Q6** (the silent `llm_tier=None` default is the bigger half; make it loud) and **Q2 compensations 2 & 3** (zero-citable tripwire; classification manifest surfaced at the interview).
- `plugins/quality-playbook/skills/quality-playbook/scripts/reference_docs_ingest.py` — `ingest(target_repo, *, llm_classifier=None)` (:442) and `classify_reference_docs(..., llm_classifier=None)` (:583) — the callback is optional and defaulted to `None`; that is the gap.
- `plugins/quality-playbook/skills/quality-playbook/scripts/doc_classification.py` — `classify_documents(..., llm_classifier=None)` and the `RULE_DEFAULT` / `llm_tier is None` fallback (:356-360) that emits "Tier 4 on ambiguity". After 023, non-floored docs carry `advisory_hints[]` / `code_heavy` — the classifier must read these as demotion inputs.
- `references/phase1_exploration_guide.md` + `references/requirements_pipeline.md` + the phase prompts — where Phase 1 invokes the ingest; this is where the running agent must be told to perform the classification (the same "the running agent supplies the callback at run time" pattern as the persona pass in instruction 021).
- The preserved virtio run: `repos/virtio-1.6.0/quality/classification_manifest.json` — the six-Tier-4 collapse this must make impossible-to-miss.

## Scope
Wire the classifier + the two loudness mechanisms. **In scope:** (1) the LLM-classifier invocation, (2) loud unwired/failed-classifier signal, (3) the zero-citable-corpus tripwire, (4) surface the classification result at the interview. **Out of scope (later instructions):** the rescuable-advisory-floor ledger change (025); Feature H directive-narrowing (026); render labeled-slots (027).

## The behavior to build

1. **Wire the LLM classifier into the run.** At Phase 1 ingest, the running derivation agent classifies each **non-floored** doc into Tier 1/2 (authoritative contract) vs Tier 4 (background), reading the doc plus its `advisory_hints[]` / `code_heavy` flags (from 023) as inputs — the AI owns the genre judgment the floor no longer attempts. Pass this as the `llm_classifier` callback to `ingest`/`classify_reference_docs` (the callback is the running agent's judgment, exactly as instruction 021 wired the persona spawn — the function orchestrates, the harness performs the call). The floor still runs first and the LLM may only tier the remainder, downward-only (a floored doc stays floored).

2. **Make an unwired / failed classifier LOUD — not a silent Tier-4 default.** Distinguish "the classifier ran and judged this Tier 4" from "no classifier ran." When `llm_classifier` is absent or errors, the run must **announce it prominently** — a distinct manifest status (not the quiet `RULE_DEFAULT` "ambiguity" string), a rendered disclosure in the spec Overview, and a gate WARN — rather than silently defaulting the whole corpus to Tier 4. A degraded classification is a disclosed event, never a quiet fallback.

3. **Zero-citable-corpus tripwire.** If, after floors + classification, the corpus contains **no Tier-1/2 document**, that is a loud, rendered disclosure — *"all requirements will be code-derived; no authoritative contract was found in the gathered docs"* — in the classification manifest, the `REQUIREMENTS.md` Overview (alongside the F-1 coverage-and-gaps statement), and interview Stage 1. This is a purely structural count; it would have caught the virtio collapse on the spot.

4. **Surface the classification at the interview.** Interview Stage 1 plays back which docs became citable and which were floored/defaulted, with reasons — so the "reviewable under-block" the simplification promises actually gets reviewed by a human. (Reuse the existing manifest; this is a surfacing/rendering step, not new classification.)

## Acceptance oracle
1. **Classifier wired:** on a corpus with an authoritative doc and a background doc, the run invokes the LLM classifier and the authoritative doc lands Tier 1/2 (not `RULE_DEFAULT`) — demonstrated with a stubbed classifier callback (deterministic test), and the wiring path shown in the phase flow.
2. **Loud on unwired/failed:** with no classifier / a raising classifier, the run emits the prominent manifest status + Overview disclosure + gate WARN — NOT a silent Tier-4 default. Proven by test.
3. **Zero-citable tripwire:** a corpus that yields no Tier-1/2 doc produces the loud disclosure in manifest + Overview + interview; a corpus with ≥1 citable doc does not.
4. **Hints consumed:** the classifier receives the `advisory_hints`/`code_heavy` flags (a demotion input); a genre-title-hinted doc can be demoted by the LLM but a hint alone doesn't force it.
5. **Floor precedence intact:** a floored doc (CVE/URL/extension) stays Tier 4 regardless of the classifier (downward-only).
6. **Interview playback:** Stage 1 lists citable vs floored/defaulted docs with reasons.
7. Full suite green.

## Fixture discipline
Do NOT hand-edit golden fixtures. New fixtures (wired-classifier promotion, loud-on-unwired, the zero-citable tripwire, hint consumption) are expected. If the virtio Slice-1 coherence fixtures change because a real run now classifies, that regeneration is a separate run — flag it, don't fake it.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight; local commits only; **never push/merge**. This touches phase prompts / pipeline prose (QPB source) — land it directly as the worker.
- Self-Council per §13 — correctness- and honesty-critical: (a) the classifier is genuinely wired at the right phase point, floor precedence and downward-only preserved; (b) **loudness** — an unwired/failed classifier and a zero-citable corpus are impossible to miss (manifest + render + WARN), never a silent default (mutation-bite: disable the classifier, confirm the run screams); (c) no scope creep into the rescuable-ledger or Feature H. Artifacts under `RUNNER_ROOT/reviews/024_self_council/` + tracked copy under `docs/process/QPB_v1.6.0_Instruction_024_Self_Council/`.
- Verify the full suite; report counts + Python version.
- Output `outputs/024-feature-g-wire-classifier-and-loud-failures.md`: where/how the classifier is wired; the loud-failure mechanism (all three surfaces) + the mutation proof; the zero-citable tripwire; the interview playback; confirmation floor precedence + downward-only hold; and the remaining follow-ups (rescuable-ledger, Feature H, render).
