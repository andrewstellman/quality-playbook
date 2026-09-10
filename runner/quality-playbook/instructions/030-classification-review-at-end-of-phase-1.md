# Instruction 030 — v1.6.0: show + confirm the document classification at the end of exploration

The live virtio run exposed the gap this closes. Classification is an **LLM judgment**, and it varies: the same `virtio-spec-behavioral-contracts.md` classified **Tier 2 citable** in one run and **all-Tier-4 (zero citable)** in another. Today the user only discovers a bad classification via the zero-citable tripwire *after* Phase 2 has already derived 18 code-only requirements. The fix: at the **end of exploration (Phase 1)**, before requirements are derived, **show the operator how each document was classified, and let them confirm or correct it** — because the operator gathered the docs and is the right person to say "that IS my authoritative spec, use it."

This is the mirror image of the requirements interview, and the same principle: **the operator validates a derived judgment before downstream work depends on it.**
- **End of Phase 1:** confirm the *classification* (which docs are authoritative) → Phase 2 derives against the confirmed set.
- **End of Phase 2:** confirm the *requirements* (the existing interview).

## Read first — these ARE the spec
- `~/Documents/AI-Driven Development/Quality Playbook/QPB_v1.6.0_UX_Language_Draft.md` — the plain-language UX standard + the concrete classification-review sketch (the exact voice the operator-facing text must use — **no "Tier", "citable", "floored", "manifest" jargon reaches the operator**).
- `plugins/quality-playbook/skills/quality-playbook/scripts/doc_classification.py` — `classification_playback(manifest)` (built in 024) already renders per-doc status + reasons; this is the **show**. `classify_documents(..., advisory_rescues=...)` + the `Decision` fields.
- `plugins/quality-playbook/skills/quality-playbook/scripts/reference_docs_ingest.py` — `_load_advisory_rescues` / the operator-authored rescue (025) + how `classify_reference_docs` threads promotion + writes `formal_docs_manifest.json` (011). An operator promotion re-runs ingest so the promoted doc gets a byte-citable `FORMAL_DOC` record for Phase 2.
- `references/requirements_interview.md` + `references/what_just_happened.md` (State P1) + `phase_prompts/phase1.md` — the end-of-Phase-1 boundary where the show/confirm is offered, and the opt-in/opt-out + continuous-run pattern to mirror (the interview is the template).
- `docs/design/QPB_v1.6.0_Design.md` §8a — reflect the new operator step in the design.
- `ai_context/DEVELOPMENT_PROCESS.md`.

## The behavior to build

1. **Show the classification at the end of Phase 1 — always, in plain language.** After exploration + classification, before the user continues to Phase 2, present each gathered document as: an **authoritative source your requirements can cite**, or **background context (not cited)**, with a one-line plain reason. Reuse `classification_playback`; render it in the operator's language per the UX draft (describe *what the doc is being used for*, never "Tier N / floored / manifest"). If **nothing** is authoritative, say so prominently — *"none of your documents are being used as authoritative sources this run; every requirement will be drawn from the code. If one of these should be treated as your spec, tell me."*

2. **Confirm or correct — an operator step (opt-out for straight-through).** Ask the operator to confirm or correct the classification: they can name a background/omitted doc to **treat as authoritative** (or the reverse). This is opt-in-to-*correct* but the offer is presented (like the interview). If the operator earlier said **"run straight through / run all phases / don't ask questions,"** skip the pause and continue with the classification as-is — but still **show** it (disclosure is not skippable; only the pause is).

3. **A correction is operator-authored and re-derives citability.** When the operator promotes a document, record it through the **operator-authored** path (the 025 rescue / sidecar — human-only, content-keyed; **document content can never promote itself**), then re-run ingest so the promoted doc becomes a byte-citable `FORMAL_DOC` (011) that Phase 2 can cite. The promotion is the operator explicitly saying "this is authoritative" — the same trust-anchor rescue 025 built, now reachable interactively.

4. **Continue to Phase 2 against the confirmed classification.** Phase 2 derives requirements citing whatever the operator confirmed/promoted — so the virtio case (operator promotes the spec) yields spec-grounded requirements instead of all-code-derived.

## Security invariant (do not weaken)
The correction is **operator-authored only** — no document content, classifier, or persona can promote a doc; only the human operator, at this step, can. Reuse the 025 human-only guarantee. A doc whose *content* asks to be promoted is not promoted; only the operator's explicit instruction at this step promotes it.

## Acceptance oracle
1. **Always shows:** end of Phase 1 renders the per-doc classification in plain language (no Tier/floored/manifest jargon), including the prominent "no authoritative sources" message when citable_count is 0.
2. **Operator can promote:** an operator instruction to treat a background/floored doc as authoritative promotes it via the operator-authored path; a re-run ingest gives it a `FORMAL_DOC` record; Phase 2 can cite it. (Build the virtio case: promote `virtio-spec-behavioral-contracts.md` → it becomes citable.)
3. **Straight-through skips the pause, keeps the show:** a run told to go straight through does not stop for confirmation but still displays the classification.
4. **Security:** document content cannot self-promote; only the operator's explicit promotion at this step works (mutation-bitten).
5. **Symmetry/consistency:** the step mirrors the interview's opt-out + continuous-run handling.
6. Full suite green.

## Fixture discipline
Do NOT hand-edit golden fixtures. New fixtures (the plain-language show, the operator-promotion round-trip to a FORMAL_DOC, the straight-through show-without-pause, the content-self-promotion rejection) are expected.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight; local commits only; **never push/merge**. Touches QPB source (doc_classification / ingest / phase prompts / references) + the design.
- Self-Council per §13 — this adds an operator step that touches the classification-promotion path (security-relevant): (a) the promotion is **operator-authored only** — no content/classifier self-promotion; content-keyed; mutation-bitten; (b) the show is **always present + plain-language** (no jargon leaks) and correct (matches the actual classification); (c) straight-through skips only the pause; corrections correctly flow to a `FORMAL_DOC` and into Phase 2; no scope creep. Artifacts under `RUNNER_ROOT/reviews/030_self_council/` + tracked copy under `docs/process/QPB_v1.6.0_Instruction_030_Self_Council/`.
- Verify the full suite; report counts + Python version.
- Output `outputs/030-classification-review-at-end-of-phase-1.md`: the end-of-Phase-1 show (plain-language sample); the operator-promotion round-trip (virtio spec → citable → Phase-2-citable); the straight-through behavior; the content-self-promotion rejection; the §8a design note; and confirmation the operator-authored security invariant holds.
