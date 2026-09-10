# Instruction 011 — v1.6.0 Slice 3 completion: wire classification → the byte-citable surface

Instruction 010 built Feature G's **classifier** and its reviewable `classification_manifest.json`. But it stopped one seam short of the feature's stated purpose: a top-level dumped doc classified **Tier 1/2** in the classification manifest still gets **`tier = 4`** in `formal_docs_manifest.json` — the manifest the hallucination gate actually reads. So a dumped doc is *labeled* authoritative but is **not byte-citable**. Re-deriving chi from dumped docs today would still produce **Tier-3** requirements.

This instruction closes that seam so dump-and-go delivers what §8a criterion 7 already requires: **"authoritative docs come out Tier-1/2, not all-Tier-3"** — end to end, not just as a label.

## The gap, shown against the code

`plugins/quality-playbook/skills/quality-playbook/scripts/reference_docs_ingest.py`, `_collect()`:

```python
is_cite = _is_under_cite(path, cite_dir)
if is_cite:
    tier = _parse_tier_marker(text)
else:
    tier = 4          # ← every top-level dumped doc, regardless of classification
```

Consequence, verified off disk 2026-07-22: chi dumped → **17 docs classified Tier 1** in `classification_manifest.json`, but **0** FORMAL_DOC records at Tier 1/2 (they're all `tier = 4` in `formal_docs_manifest.json`). And non-plaintext contracts (`.proto`/`.json`/`.yaml`/`.d.ts`) are `continue`-skipped in `_collect()` (line ~312), so they get a classification record but never reach `_build_record()` at all.

## Read first — these ARE the spec
- `docs/design/QPB_v1.6.0_Design.md` **§8a** (esp. Verification item 1 and the advisory/impl-floor rules) and **§10 criterion 7** — the end-to-end Tier-1/2 outcome is the acceptance target; the floor rules constrain how you get there.
- `plugins/quality-playbook/skills/quality-playbook/scripts/reference_docs_ingest.py` — `_collect()` (the seam), `_build_record()` (the FORMAL_DOC shape), `classify_reference_docs()` / `classification_manifest.json` (010's output you're wiring in).
- `plugins/quality-playbook/skills/quality-playbook/scripts/doc_classification.py` — the classifier and `Decision` (`tier`, `promotable`, `floor_rule`). The classification manifest is the **source of truth** for a top-level doc's tier.
- `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py` — `citation_verifier`, the byte-verification path the gate re-invokes. Do NOT change its contract.
- `schemas.md` — the FORMAL_DOC record shape (§3.6/§3.10) and the classification manifest shape (§9.6).
- `ai_context/DEVELOPMENT_PROCESS.md`.

## Scope of THIS instruction
**Wire classification → the byte-citable surface.** No new classifier behavior, no Feature H (personas). Stop and file when the acceptance oracle passes.

## The behavior to build (§8a is the spec; decompose it yourself)

1. **The classification manifest drives top-level tiers.** In the formal-docs pass, a top-level (non-`cite/`) document's tier comes from its classification decision, not a hardcoded `4`:
   - Classified **Tier 1/2 and `promotable`** → emit a **FORMAL_DOC record** (byte-citable: `document_sha256`, `citation_excerpt`, `role: external-spec`, the classification's tier). This is the whole point — these docs must be citable by the gate exactly like a `cite/` doc.
   - Classified **Tier 4** (floored advisory, floored implementation source, background, or LLM-demoted) → **stays Tier-4 context** (loaded for Phase 1, not a citable FORMAL_DOC record). Never a Tier-1/2 record.

2. **Non-plaintext contracts become citable, not skipped.** A classified-citable machine-readable contract (`.proto`/`.json`/`.yaml`/`.d.ts`/OpenAPI/WSDL) must get a FORMAL_DOC record with a byte-verified `citation_excerpt` and `document_sha256`, so a REQ can cite it and the gate can verify it. (Today `_collect()` skips these before `_build_record()`.) Implementation source (`.py`/`.c`/`.go` with logic) stays floored — no record.

3. **The floor survives the new path — this is the security-critical invariant.** The wiring must NOT become a laundering route. A doc the deterministic floor put at Tier 4 (CVE advisory, renamed `cve-2024-x.proto`, MUST/SHALL bulletin, injection-self-promoter, implementation source) must **never** acquire a Tier-1/2 FORMAL_DOC record through this path. Read the tier from the classification `Decision`, which already encodes the floor (`promotable == False` for floored docs); do not re-decide tiers here. The operator sidecar's bound is unchanged: it rescues the implementation floor only, never the advisory floor.

4. **`cite/` still works, unchanged.** An explicit `cite/` doc keeps its `_parse_tier_marker` behavior. `cite/` is now one input path among two (explicit pre-sort vs. dump-and-go classification); both produce FORMAL_DOC records. The existing `cite/`-based byte-verification fixtures must stay green.

5. **Reproducible + content-keyed.** The FORMAL_DOC record's `document_sha256` must match the classification manifest's content key for the same file, so the two manifests reconcile and a re-run with unchanged docs reproduces the same citable set.

6. **Byte-verification contract unchanged.** You are adding *which* docs are citable; you are not changing *how* a citation is verified. The gate still re-invokes `citation_verifier` on every Tier-1/2 citation. Do not touch that path except to confirm it now accepts the newly-citable dumped docs.

7. **Document the wiring in the design.** §8a states the Tier-1/2 outcome (criterion 7) but not the mechanism. Add a short "citability wiring" paragraph to §8a: the classification manifest is the source of truth for top-level tiers; promotable Tier-1/2 → FORMAL_DOC record; floored/background → Tier-4 context; the floor is read from the classification decision, never re-litigated in the formal-docs pass.

## Acceptance oracle (build a fixture for each; mutation-bite the security ones)
1. **End-to-end citability:** chi's and express's `docs_gathered/` dumped into one folder with no `cite/` → the authoritative docs now appear as **Tier-1/2 FORMAL_DOC records** in `formal_docs_manifest.json` (not merely Tier-1 in the classification manifest). Report the FORMAL_DOC Tier-1/2 counts before (0) and after.
2. **Non-plaintext contract is citable:** a dumped OpenAPI/`.proto`/JSON-Schema file gets a FORMAL_DOC record with a byte-verified `citation_excerpt` + `document_sha256`; a REQ citing it passes `citation_verifier`.
3. **Floor survives the wiring (mutation):** a dumped CVE advisory, a renamed `cve-2024-x.proto` advisory, a MUST/SHALL bulletin, an injection self-promoter, and a `.py` logic file each get **no** Tier-1/2 FORMAL_DOC record — even with the LLM classifier stubbed to promote everything. (Bite it: assert no floored `source_path` appears among Tier-1/2 formal-doc records.)
4. **Sidecar bound unchanged:** the operator sidecar cannot produce a Tier-1/2 FORMAL_DOC record for an advisory (incl. the renamed `.proto`); it rescues the implementation floor only.
5. **`cite/` unchanged:** existing `cite/`-based byte-verification fixtures pass untouched.
6. **Reconciliation:** each Tier-1/2 FORMAL_DOC record's `document_sha256` equals the classification manifest's content key for that file; a re-run with unchanged docs reproduces the same citable set.

## The Slice-1 coherence fixtures WILL flip now — regenerate them correctly
010 did not regenerate the chi/express coherence fixtures because it never made the docs citable, so no derivation actually flipped. **This instruction is where the flip happens.** Per §9 Slice 3 (design line ~332), landing real citability changes chi/express from all-Tier-3 to Tier-1/2, which changes the tier-distribution line in their rendered Overview. If a full re-derivation is needed to regenerate those golden coherence fixtures, do it as a **fixture correction** (a run, explained), distinct from hand-editing a fixture to dodge a check. If the regeneration requires a full pipeline run out of scope for a code instruction, **do NOT fake it** — flag precisely what run is needed and leave the fixture, recording it for the orchestrator.

## Note the seam (Plan OD-10)
Two requirements producers consume `formal_docs_manifest.json` (the code-path pipeline and `bin/skill_derivation/`). The wiring lives in the shared ingest surface, so both benefit from one change — confirm and say so, as 010 did.

## Fixture discipline
Do NOT hand-edit existing golden fixtures to pass. New fixtures (the citability + floor-survival cases) are expected. The coherence-fixture regeneration is a correction, not a dodge — explain it.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight the branch, `pre-flight-aborted` if wrong. Local commits only; **never push/merge**.
- Self-Council per §13: charters for (a) **the floor survives the citability wiring** — the security-critical part: verify a floored doc cannot acquire a Tier-1/2 FORMAL_DOC record via any path (classification promotion, non-plaintext contract route, sidecar, or LLM-stubbed-to-promote); mutation-bitten, each panelist in its own worktree; (b) the classification→FORMAL_DOC mapping, the non-plaintext-contract record shape, and `schemas.md`/`_build_record` correctness; (c) byte-verification-unchanged + `cite/`-unchanged + the coherence-fixture regeneration honesty. Artifacts under `RUNNER_ROOT/reviews/011_self_council/` + a tracked copy under `docs/process/QPB_v1.6.0_Instruction_011_Self_Council/`.
- Verify the full suite; report counts + Python version.
- Output `outputs/011-feature-g-classification-to-citable-wiring.md`: the chi/express Tier-1/2 **FORMAL_DOC** before/after (0 → N), the non-plaintext-contract citability result, each floor-survival mutation result, the reconciliation check, whether the coherence fixtures were regenerated (and if not, the exact run needed), which producer(s) you touched, the §8a wiring paragraph you added, and anything you found underspecified.
