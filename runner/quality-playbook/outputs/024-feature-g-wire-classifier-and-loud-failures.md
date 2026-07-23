# Output for 024-feature-g-wire-classifier-and-loud-failures.md
**Status:** completed

## What this instruction was
Fix the *bigger* half of the virtio failure (Fable Q6): the LLM classifier was
never wired into the pipeline, so every non-floored doc silently defaulted to Tier
4, and — with the 023 mis-floor — the whole corpus collapsed to **zero citable
docs, silently**. Wire the classifier and make its absence/failure and a
zero-citable corpus **loud**.

## Terminal verdict: unanimous SHIP (0 FIX-REQUIRED)
| Charter | Verdict |
|---------|---------|
| A — Classifier genuinely wired; floor precedence + downward-only preserved | **SHIP** |
| B — Unwired/failed classifier + zero-citable corpus impossible to miss | **SHIP** |
| C — No scope creep + no regression | **SHIP** |

Each panelist ran a driver against the reviewed commit and mutation-bit the loud
surfaces (including the instruction's demanded "disable the classifier → confirm
the run screams").

## Where/how the classifier is wired
`doc_classification.classify_documents` calls the derivation AI's per-file tier
callback — `llm_classifier(rel, text)`, or `llm_classifier(rel, text, hints)` when
it accepts a third argument, where `hints = {"advisory_hints": [...],
"code_heavy": ...}` from the floor (a **demotion input** — the AI owns the genre
judgment the floor no longer attempts). The floor runs **first** and the classifier
may only tier the remainder, **downward-only** (a floored doc stays floored).
`reference_docs_ingest.classify_reference_docs`/`ingest` already thread the callback
(byte-unchanged) and now write the new fields to `quality/classification_manifest.json`.

**The skill-flow wiring (behavior 1)** is prose in `references/phase1_exploration_
guide.md`: the agent **is** the classifier — it reviews the floor-only manifest,
assigns Tier 1/2 to authoritative docs marking `floor_rule: "llm"`, and **re-runs
ingest** so the manifest reflects its tiers. A **record-derived upgrade** keeps this
honest: a no-callback run whose reused, agent-refined records carry a `RULE_LLM`
tier reads `classifier_status="wired-ok"`, so the loud WARN fires only on a
genuinely floor-only corpus, not every run.

## The loud-failure mechanism (all three surfaces + mutation proof)
A degraded classification is a **disclosed event, never a quiet fallback**:
1. **Manifest** — `classify_documents` writes top-level `classifier_status`
   (`wired-ok` / `unwired` / `error`, + `classifier_error`) and a `zero_citable`
   tripwire. `classification_disclosure(manifest)` is the single source of the loud
   wording.
2. **Gate WARN** — `quality_gate.check_classification_manifest(q)` WARNs (never
   FAILs, inert when the manifest is absent) on `classifier_status != "wired-ok"`
   or `zero_citable`.
3. **Render + interview (prose)** — the `REQUIREMENTS.md` Overview disclosure
   (`phase2_generation_guide.md`, beside the F-1 coverage-and-gaps statement) and
   the interview Stage-1 classification playback (`requirements_interview.md`).

**Mutation proof (Panelist B):** each loud surface is load-bearing — silencing the
status field, the disclosure branch, or the gate WARN reddens a test; a healthy
run is genuinely silent (no false alarm); "disable the classifier → the run
screams" verified.

## The zero-citable tripwire
`zero_citable` = no Tier-1/2 record after floors + classification — a purely
structural count, surfaced in the manifest, the gate WARN, the Overview, and the
interview. This is the exact virtio collapse (6/6 Tier 4), now impossible to miss;
the disclosure says plainly *"all requirements will be code-derived; no
authoritative contract was found."*

## The interview playback
`classification_playback(manifest)` + the Stage-1 prose list every doc as
**citable** / **floored-tier4** / **defaulted-tier4** with its reason — so the
"reviewable under-block" the simplification promises actually gets reviewed, and a
mis-tiered spec (same signature as a correct code-only run) is caught by the human.

## Acceptance oracle — pass/fail
| # | Item | Result |
|---|------|--------|
| 1 | Classifier wired — stubbed callback lands authoritative doc Tier 1/2; wiring in the phase flow | **PASS** — `test_wired_classifier_promotes...` + 2 ingest end-to-end tests; phase1 guide prose (Panelist A verified the thread) |
| 2 | Loud on unwired/failed — manifest status + Overview + gate WARN, not silent | **PASS** — `test_unwired_is_loud...`, `test_failed_classifier_is_loud`, gate tests; Panelist B mutation-confirmed |
| 3 | Zero-citable tripwire in manifest + Overview + interview | **PASS** — `test_zero_citable_tripwire` + gate `test_zero_citable_warns` + prose |
| 4 | Hints consumed (demotion input; hint alone doesn't force) | **PASS** — `test_hints_are_passed_to_a_hint_aware_classifier` |
| 5 | Floor precedence intact (downward-only) | **PASS** — `test_floor_precedence_intact_downward_only`; Panelist A mutation-bit it |
| 6 | Interview playback lists citable/floored/defaulted with reasons | **PASS** — `test_playback_lists...` + Stage-1 prose |
| 7 | Full suite green | **PASS** — 2766 / 0 / 14, Python 3.14.6 |

## Confirmation: floor precedence + downward-only hold
Panelist A mutation-bit it: making the classifier win over the floor reddens 8
floor tests. A floored doc (CVE id, advisory URL, `.py` impl, README background)
stays Tier 4 under a promote-all classifier. The record-derived status upgrade
**never changes a tier** — a poisoned `RULE_LLM` prior on a CVE doc is re-floored
by the unrescuable-floor guard.

## Files changed
| File | Change |
|------|--------|
| `plugins/.../scripts/doc_classification.py` | `CLASSIFIER_*` constants; `_accepts_hints` arity shim; `classify_documents` status/hints/error + zero-citable + record-derived upgrade; `classification_disclosure` + `classification_playback` |
| `plugins/.../scripts/quality_gate.py` | `check_classification_manifest` (WARN-only, inert-when-absent) + registered once in `check_repo` |
| `references/phase1_exploration_guide.md` | classifier-wiring + loud-disclosure prose; **+ a stale pre-023 floor line fixed** (Panelist A observation, commit `07b5473`) |
| `references/phase2_generation_guide.md` | Overview classification disclosure (F-1 area) |
| `references/requirements_interview.md` | Stage-1 classification playback |
| `bin/tests/test_doc_classification_v160.py` | `WireClassifier024Tests` (9) + 2 ingest tests + `test_manifest_shape` → superset |
| `bin/tests/test_classification_gate_v160.py` | **New** — 8 gate tests |

`reference_docs_ingest.py` byte-unchanged (the new fields flow through automatically).

## Commits made (branch `1.6.0`, local only — never pushed)
- `0c06e80` — wire the classifier + loud failures (code + prose + tests).
- `07b5473` — fix a stale pre-023 floor claim in the Phase-1 guide (Panelist A, prose-only).
- `58aa9a3` — tracked self-Council synthesis.

## Remaining follow-ups (named per the instruction — OUT of this scope)
- **Rescuable-advisory-floor ledger (025):** make the CVE/URL advisory floor rescuable via the operator confirmation ledger (Fable Q2).
- **Feature H directive-narrowing (026):** narrow `persona_grounding._AGENT_DIRECTIVE_RE`; delete the dead `detect_fabrication`; mutation-pin the Tier-1/2 grounded-citation guard; give grounding self-contained tier-claim detection so the retained `doc_classification.injection_signature` can finally be removed.
- **Render labeled-slots (027):** convert the render prose checks to labeled-slot format contracts (Fable Q4).
- Also open: broader 1.6.0 acceptance + Phase 8 tag/merge; OD-9 live FP bound; Feature-G non-plaintext-contract → FORMAL_DOC wiring; chi/express Slice-1 coherence-fixture regen (now that a real run classifies); OD-11 hardening.

## Artifacts
- Gitignored: `runner/quality-playbook/reviews/024_self_council/` (three panelist verdicts).
- Tracked: `docs/process/QPB_v1.6.0_Instruction_024_Self_Council/synthesis.md`.
