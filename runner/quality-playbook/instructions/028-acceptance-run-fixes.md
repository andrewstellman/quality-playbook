# Instruction 028 — v1.6.0 acceptance-run fixes: validator flat-layout + three Feature-H wrinkles

Three real acceptance runs of the hardened v1.6.0 pipeline (virtio via Claude Code; chi + express via sonnet sub-agents) all validated the core fixes — authoritative docs classify citable, advisories floor on hard signals only, requirements come out 75–90% Tier 1/2, Feature C/H run correctly. They also surfaced **four defects worth fixing**, all confirmed on disk. This instruction fixes all four. None is a security-floor change; they are correctness + a validator false-positive.

## The four fixes

### 1. Validator false-flags the flat `.github/skills/` layout (recurring, adopter-facing — highest priority)
**Symptom:** every acceptance run hit this. `qpb_validate.py`'s install-path map hard-codes the **nested** location (`.github` → `.github/skills/quality-playbook/`, lines ~92-99). But `setup_repos.sh` (and the `.github` install path per instruction 020) install the skill **flat** at `.github/skills/SKILL.md`. The validator looks one directory too deep, reports the skill "missing," and emits a false finding — `status=remediable` in the `installed` context and escalating to **`status=blocked`** in the `clone` context (verified in `repos/virtio-1.6.0/quality/.qpb_validation_*.txt` and reproduced by the express run). A real adopter who installs to `.github/skills/` could be stopped at Phase 0.
**Fix:** teach the validator to recognize the **flat `.github/skills/SKILL.md`** layout as valid alongside the nested `.github/skills/quality-playbook/SKILL.md` (and the analogous flat form for the other tool dotfolders where the install actually produces flat). Determine from the real install conventions (`install_skill.py` + `setup_repos.sh`) which tools use flat vs nested and make the map/detection accept the layout that is actually installed. After the fix: a flat-layout target validates clean (no false "skill missing" finding, no spurious `blocked`); the nested layout still validates; the genuinely-missing-skill case still fails.

### 2. Feature H: grounded persona-added REQ has no `tier` field (chi run)
**Symptom:** a grounded `add` (cites a Tier-1/2 FORMAL_DOC, byte-verified) produces a synthesized REQ record with **no `tier` value** — Guard 1 checks the *cited doc's* tier (`persona_grounding.py:~193`) but nothing backfills a `tier` onto the new REQ record. Doesn't break the gate (other Tier-1/2 REQs satisfy the has-Tier-1/2 check) but the record is incomplete + inconsistent with derivation-produced REQs.
**Fix:** in the persona add-apply path (`persona_apply` / `persona_merge`), backfill the new REQ's `tier` to equal its cited FORMAL_DOC's tier (the tier the grounding already resolved). Every applied `agent-validation` add ends with a populated `tier` matching its citation.

### 3. Feature H: `REQUIREMENTS.md` not re-rendered after the persona pass (chi run)
**Symptom:** `run_feature_h` applies grounded moves to `requirements_manifest.json` (the source of truth), but `REQUIREMENTS.md` is left in its pre-persona rendered state — so the human-readable doc silently lags the manifest after a persona pass.
**Fix:** after the persona pass applies moves (and the single terminal renumber runs), **re-render `REQUIREMENTS.md`** from the updated manifest so the rendered spec reflects the applied agent-validation changes. (Reuse the existing render path; don't reimplement.) A run with an applied persona add shows that add in the rendered doc.

### 4. Feature H: confirm-move IDs in the review summary reference pre-renumber values (express run)
**Symptom:** the terminal renumber updates BUG cross-references (instruction 017) but not the `req_id` fields of **confirm** moves recorded in `persona_review_summary.json` — so after persona adds shift the numbering, a confirm move points at a stale ID.
**Fix:** apply the renumber remap to the confirm-move `req_id`s in the review summary (the same remap already applied to BUG cross-refs), so every review-summary entry references post-renumber IDs.

## Read first — these ARE the spec
- `plugins/quality-playbook/skills/quality-playbook/scripts/qpb_validate.py` — the install-path map (~:92-99) + the layout detection (~:489 "root for BOTH layouts"). Fix 1.
- `plugins/quality-playbook/skills/quality-playbook/scripts/install_skill.py` + `repos/setup_repos.sh` — the actual install layouts (which tool → flat vs nested). Ground fix 1 in what is really installed.
- `plugins/quality-playbook/skills/quality-playbook/scripts/persona_apply.py` + `persona_merge.py` — `run_feature_h`, the add-apply path, the terminal renumber + remap. Fixes 2, 3, 4.
- `plugins/quality-playbook/skills/quality-playbook/scripts/requirements_render.py` — the render path fix 3 reuses.
- `repos/virtio-1.6.0/quality/.qpb_validation_*.txt` — the real false-flag evidence for fix 1.
- `ai_context/DEVELOPMENT_PROCESS.md`.

## Acceptance oracle
1. **Flat layout validates clean:** a target with the skill at `.github/skills/SKILL.md` produces no "skill missing" finding and no spurious `blocked`/`remediable` from the layout check, in both `installed` and `clone` invocation contexts; the nested layout still validates; a genuinely-absent skill still fails. Build a fixture per layout.
2. **Tier backfilled:** a grounded persona `add` yields a REQ record whose `tier` equals its cited FORMAL_DOC's tier.
3. **Re-rendered:** after a persona pass with an applied add, `REQUIREMENTS.md` contains that add (rendered doc == manifest).
4. **Confirm IDs remapped:** after persona adds trigger a renumber, confirm-move `req_id`s in `persona_review_summary.json` are post-renumber.
5. Full suite green.

## Fixture discipline
Do NOT hand-edit golden fixtures. New fixtures (flat + nested layout validation, tier-backfill, re-render-after-persona, confirm-id remap) are expected.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight; local commits only; **never push/merge**. Touches QPB source (`qpb_validate.py`, persona modules, render).
- Self-Council per §13 — correctness-critical (fix 1 touches the Phase-0 gate; fixes 2-4 the persona apply path), not security-floor: (a) the validator recognizes flat + nested and still fails a truly-missing skill (no over-loosening — a real "skill not installed" must still block); (b) the tier-backfill + re-render are correct and reuse existing paths (no guard/render reimplementation); (c) the confirm-id remap uses the existing renumber remap and no scope creep. Artifacts under `RUNNER_ROOT/reviews/028_self_council/` + tracked copy under `docs/process/QPB_v1.6.0_Instruction_028_Self_Council/`.
- Verify the full suite; report counts + Python version.
- Output `outputs/028-acceptance-run-fixes.md`: each fix before/after + its test; the flat-layout validation proof in both contexts (and that a missing skill still fails); confirmation the persona apply path now backfills tier + re-renders + remaps confirm IDs; and any remaining release items unchanged (broader acceptance, Phase 8, OD-9, non-plaintext→FORMAL_DOC, coherence-fixture regen, OD-11, design-doc refresh).
