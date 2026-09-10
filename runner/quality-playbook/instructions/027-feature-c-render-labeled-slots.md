# Instruction 027 — v1.6.0 Feature C: convert render prose checks to labeled-slot format contracts

The final simplification. Feature C's render-contract gate has four checks that mechanize a *prose-quality* judgment as a hard FAIL — the same smell as the advisory floor, and one of them (`_render_rationale_present`) has already false-FAILed two well-formed specs (chi's bare "so", virtio's "Rationale:" label). Its own code comment admits *"detecting 'is a reason given' with a keyword list is brittle — every widening misses the next valid phrasing."*

The external review (Fable Q4) rejected a plain FAIL→WARN downgrade as too weak and prescribed a better fix: **labeled-slot format contracts.** The generation guide requires a *labeled slot*; the gate FAILs on the slot's **absence** (purely structural — a label is a literal string); the slot's **content quality** goes to the interview + the readability Council. This keeps the gate's teeth (a generator that skips the slot still fails, which a pure WARN would not catch) while deleting every genre regex and magic threshold.

## Read first — these ARE the spec
- `~/Documents/AI-Driven Development/Quality Playbook/Reviews/QPB_v1.6.0_Simplification_Fable_Review_Response.md` — **Q4** (the labeled-slot pattern + the exact three conversions).
- `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py` — the render-contract checks: `_render_rationale_present` + `_RENDER_RATIONALE_CONNECTOR_RE` (~:7288-7345), `_render_organizing_principle_stated` + `_RENDER_PRINCIPLE_RE` (~:7260-7379), the **already-existing** label regex `_RENDER_PRINCIPLE_LABEL_RE` (~:7299), the singleton-section justification keyword scan (~:7904-7921), and the section-overview `len(intro) >= 40` threshold (~:7867-7884). The FAIL emitters are nearby.
- `references/phase2_generation_guide.md` — where the generator is instructed to emit the organizing principle / section overviews; this is where the **labeled-slot requirement** goes so the generator produces the slots the gate now checks.
- `references/requirements_interview.md` + the readability rubric — where *content quality* of the rationale/overview is judged (the checks this moves OUT of the gate).
- `ai_context/DEVELOPMENT_PROCESS.md`.

## Scope
The four render prose checks only. After this, the simplification sweep is complete. **Out of scope:** the broader release items (acceptance, Phase 8, the named carry-forwards).

## The conversions

1. **Organizing-principle + rationale → one labeled slot.** Require, in the generation guide, a literal slot: `Organizing principle: <name> — Rationale: <text>` (reuse `_RENDER_PRINCIPLE_LABEL_RE`, which already exists). The gate **FAILs** only on: the label absent, the principle name empty, or the rationale text empty — all structural string checks. **Delete** `_RENDER_RATIONALE_CONNECTOR_RE` (the 27-alternation connector list), the `≥2-sentences-of-≥4-words` arithmetic, and the prose-phrasing `_RENDER_PRINCIPLE_RE` naming regex. The *rationale's adequacy* (is the reason good?) becomes an interview/readability-rubric judgment, not a gate FAIL.

2. **Singleton-section justification → labeled presence.** A one-REQ section must carry a justification line (a labeled slot or a required non-empty justification field). The gate **FAILs** on its **absence** only. **Delete** the keyword scan (`singleton|stands? alone|only requirement|…`) of the justification's *content*.

3. **Section overview → presence, not length.** A section must have non-empty intro prose between its heading and its first REQ. The gate **FAILs** on **absent/empty** intro. **Delete** the `len(intro) >= 40` magic threshold; overview *adequacy* goes to the rubric/interview.

4. **Update the generation guide** so the generator emits these labeled slots by construction — the format contract only works if the generator produces the slots the gate checks. Keep it minimal and literal.

## Invariants
- The gate still has **teeth**: a rendered spec missing the organizing-principle slot, a singleton justification, or a section overview still **FAILs** (structural) — this is stronger than a WARN, which a generator could skip silently.
- The gate no longer FAILs on **phrasing/length/quality** — the chi bare-"so" and virtio "Rationale:"-label false-FAILs are gone; a terse-but-present rationale passes; a verbose-but-absent one fails.
- Content *quality* is judged by the interview + readability rubric (already their job), not re-litigated mechanically in the gate.

## Acceptance oracle
1. **Present-but-terse passes:** a spec with `Organizing principle: by subsystem — Rationale: each section owns one driver` passes (no connector-word/sentence-count gymnastics); chi's "so" and virtio's "Rationale:" cases no longer false-FAIL — build fixtures from those real cases.
2. **Absent slot FAILs:** a spec missing the principle slot / a singleton justification / a section overview still FAILs (teeth intact).
3. **No quality FAIL:** a present-but-arguably-weak rationale/overview passes the gate (quality → interview); prove the connector regex and the 40-char threshold are gone.
4. **Generator emits the slots:** the generation guide requires the labeled slots.
5. Full suite green (update any test that asserted the deleted phrasing/threshold checks, with a reversal comment).

## Fixture discipline
Do NOT hand-edit golden fixtures to pass. The reversed tests (phrasing/length checks that asserted the old brittle behavior) get updated with reversal comments; new fixtures (labeled-slot present/terse/absent) are expected.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight; local commits only; **never push/merge**.
- Self-Council per §13 — correctness-critical (changes gate FAIL behavior), not security-critical: (a) the gate keeps its teeth — an absent slot/justification/overview still FAILs structurally; (b) no phrasing/length/quality judgment remains in the gate; the two real false-FAIL cases pass; (c) the generator emits the slots + no scope creep. Artifacts under `RUNNER_ROOT/reviews/027_self_council/` + tracked copy under `docs/process/QPB_v1.6.0_Instruction_027_Self_Council/`.
- Verify the full suite; report counts + Python version.
- Output `outputs/027-feature-c-render-labeled-slots.md`: each conversion before/after; the two real false-FAIL cases now passing + the absent-slot cases still FAILing; confirmation the connector regex / sentence-count / keyword-scan / 40-char threshold are deleted; the generation-guide slot requirement; and a note that the simplification sweep (023–027) is complete, listing the remaining release items (broader acceptance, Phase 8 tag/merge, OD-9, non-plaintext→FORMAL_DOC wiring, coherence-fixture regen, OD-11).
