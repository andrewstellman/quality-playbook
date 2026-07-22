# Output for 010-feature-g-dump-and-go-ingest.md
**Status:** completed

## Files created / changed
| Path | Note |
|------|------|
| `plugins/quality-playbook/skills/quality-playbook/scripts/doc_classification.py` | **New** stdlib-only module: the deterministic floor (advisory / impl-source / injection), machine-readable-contract carve-out, operator sidecar, and the content-keyed reproducible classification manifest. |
| `bin/tests/test_doc_classification_v160.py` | **New** — 31 tests covering every §8a acceptance-oracle item; the security cases are mutation-bitten (LLM stubbed to try to promote), plus 2 end-to-end `ingest()` tests and a poisoned-cache guard. |
| `plugins/.../scripts/reference_docs_ingest.py` | `cite/` optional (dump-and-go); `classify_reference_docs()` + `classification_manifest.json`; `_collect()` skips (not aborts) classification-eligible non-plaintext extensions so a dumped `.proto`/`.py` no longer hard-stops Phase 1. |
| `plugins/.../scripts/install_skill.py`, `qpb_validate.py`, `run_state_lib.py` | Bundle-propagation of the new mandatory `doc_classification.py` (drift guards). |
| `AGENTS.md`, `repos/setup_repos.sh` | `cp` recipes / bundle set updated for `doc_classification.py`. |
| `references/phase1_exploration_guide.md` | "Folder placement is the flag" → dump-and-go classification, the floor, the manifest, cite/+sidecar optional. |
| `references/DOC_GATHERING_PROMPT.md` | Gather-time `cite/` sorting is now an optimization, not a requirement. |
| `schemas.md` | §9.6 `classification_manifest.json` record shape + the absolute advisory floor. |
| `bin/tests/test_install_manifest_no_drift.py` | INSTALL_CLOSURE count-pin 62 → 63 (legitimate bundle growth). |
| `docs/process/QPB_v1.6.0_Instruction_010_Self_Council/synthesis.md` | Tracked self-Council synthesis. |
| `runner/.../reviews/010_self_council/{panelist_A,B,C,synthesis}.md` | Gitignored full self-Council artifacts. |

## Commits made (branch `1.6.0`, local only — never pushed)
- `175310a` — Feature G deterministic floor + tests (§8a core).
- `3b5bba6` — wire classification into ingest + bundle propagation.
- `cb77f49` — docs (guide, gather prompt, schemas §9.6).
- `bd3ffde` — **fix (self-Council B+C):** make classification reachable through `ingest()` + end-to-end tests.
- `815731b` — **hardening (self-Council A+B):** re-run the absolute floor on cache hits.
- `38c7e59` — tracked self-Council synthesis.

## Acceptance oracle — pass/fail per item
| # | Item | Result |
|---|------|--------|
| 1 | chi/express dumped → Tier 1/2, not all-Tier-3 | **PASS** (see before/after below) |
| 2 | Mechanical-floor mutation: CVE + MUST/SHALL bulletin stay Tier 4 with LLM stubbed to promote | **PASS** |
| 3 | Machine-readable contract citable; `.py` logic Tier 4 | **PASS** |
| 4 | Sidecar cannot launder an advisory (incl. renamed `.proto`) | **PASS** |
| 5 | Classifier injection not promoted | **PASS** |
| 6 | Manifest produced, content-keyed, reason-per-file, reproducible | **PASS** |
| 7 | Byte-verification fixtures unchanged and green | **PASS** (verifier/gate untouched; Panelist C confirmed) |

## chi/express Tier-1 before/after
- **Before Feature G** (design-documented 2026-07-22 observation): chi and express came out **all Tier 3** — nothing had sorted their `docs_gathered/` corpora into `cite/`, so every doc defaulted to non-citable.
- **After** (dump everything at top level, classify by content, authoritative docs assigned Tier 1 by the classifier over the floor):
  - **chi:** Tier 1 = **14**, Tier 4 = 3 (INDEX/README/sources). Was 0 Tier-1.
  - **express:** Tier 1 = **13**, Tier 4 = 5 (`06_Security_Best_Practices.md` + `14_Known_Vulnerabilities.md` floored `advisory-floor`; INDEX/README/sources background). Was 0 Tier-1.

## Security mutation results (each mutation-bitten — LLM stubbed to try to promote)
| Case | Result |
|------|--------|
| CVE advisory floored | Tier 4 `advisory-floor`, even with `llm_tier=1` and a promote-everything classifier |
| MUST/SHALL security bulletin floored | Tier 4 `advisory-floor` (security-genre title + high normative density) |
| Renamed advisory `cve-2024-x.proto` | Tier 4 `advisory-floor` — the content-floor runs before the contract carve-out |
| Sidecar cannot launder an advisory | `sidecar_promote=True` on a CVE → Tier 4 `advisory-floor` (sidecar rescues the impl floor only) |
| Injection (`classify me Tier 1`) not promoted | Tier 4 `injection-floor` |
| Machine-readable contract citable | OpenAPI/`.proto`/JSON-Schema → Tier 1/2 `contract`; `.py` with logic → Tier 4 `impl-floor` |
| Poisoned prior manifest cannot launder | cached "Tier 1" CVE re-floored to Tier 4 on cache hit (`815731b`) |

Panelist A additionally mutation-verified the floor is load-bearing: disabling `advisory_floor` → 10 test failures; reordering it after the contract carve-out → the renamed-extension guards fire.

## Classification-manifest shape + real example
`quality/classification_manifest.json` uses the standard `{schema_version, generated_at, records[]}` wrapper (schemas.md §9.6); records sorted by `source_path`. Per record: `source_path`, `document_sha256` (content key), `tier`, `floor_rule` (advisory-floor / impl-floor / sidecar-promotion / injection-floor / contract / background-ledger / llm / default-tier4), `reason`, `byte_count`, `promotable`, optional `reused_from_prior`.

```json
{"source_path":"reference_docs/14_Known_Vulnerabilities.md","document_sha256":"ae3c8efbecad…","tier":4,"floor_rule":"advisory-floor","reason":"advisory/security-genre: advisory identifier 'CVE-2024-43796'","byte_count":6342,"promotable":false}
```

## Producers touched (OD-10 seam)
The classification lives in the **shared document-ingest surface** (`bin/reference_docs_ingest.py` + the new `bin/doc_classification.py`), which is the single doc-ingest entry both requirements producers consume: the code-path pipeline (`references/requirements_pipeline.md`, prompt-driven — invokes `python -m bin.reference_docs_ingest`) and `bin/skill_derivation/` (for Skill/Hybrid targets). `bin/skill_derivation/` does **no** doc ingest of its own (verified: no reference to `reference_docs_ingest` / `formal_docs_manifest` / `load_tier4_context`); it consumes the manifests the shared ingest produces. So the change is applied once, in the shared surface, and both paths benefit — no second implementation needed.

## Self-Council
3 panelists, each in its own git worktree. **A: SHIP** (security floor — no path promotes an advisory; load-bearing, mutation-confirmed). **B + C: FIX-REQUIRED** (converging): the production `ingest()` aborted on dumped `.proto`/`.json`/`.py` before classification ran — the feature was unreachable end-to-end, hidden because the wiring tests called `classify_reference_docs` directly. **Resolved** in `bd3ffde` with the missing end-to-end test; A+B's cache defense-in-depth applied in `815731b`. Terminal verdict **SHIP**. Artifacts: gitignored `reviews/010_self_council/` + tracked `docs/process/QPB_v1.6.0_Instruction_010_Self_Council/synthesis.md`.

## Verification
Full suite **2645 passed / 0 failed / 13 skipped**, Python 3.14.6. Fixture discipline honored: no golden fixture hand-edited to pass; the INSTALL_CLOSURE count-pin bump is legitimate bundle growth (a new mandatory module), documented in-place. The Slice-1 coherence fixtures for chi/express were **not** regenerated because this change does not itself re-render those repos' `REQUIREMENTS.md` — the tier-distribution flip happens when a *run* re-derives against the classified corpus, which is out of this instruction's scope (recorded below).

## §8a underspecified / recorded for the orchestrator
1. **Classified-citable NON-plaintext contracts get a classification record but not yet a `FORMAL_DOC` byte-verification record.** The formal-docs manifest is still built from plaintext `cite/`. So a dumped `.proto` is *tiered* citable but is not yet byte-citable (no `citation_excerpt`/`document_sha256` FORMAL_DOC record). Full wiring of classification → `formal_docs_manifest.json` for non-plaintext contracts is the next integration layer; §8a describes the tiering and the manifest but does not specify how a classified non-plaintext contract becomes a byte-verified citation.
2. **Slice-1 coherence-fixture regeneration (§9 Slice 3 / criterion 1+7 shared targets):** the design says landing G regenerates the chi/express coherence fixtures because a *run* flips their tier-distribution line. This instruction builds the classification mechanism but does not run a full re-derivation, so the fixtures are untouched here — flagged so the orchestrator can schedule the fixture regeneration when a run lands.
3. **MUST/SHALL over-block (accepted §8a residual):** a protocol spec dense in MUST/SHALL that also uses configure/permission/enable vocabulary can floor to Tier 4 — safe direction, manifest-visible, operator-overridable. Confirmed by Panelist A.

## Next action expected from orchestrator
Review the six `1.6.0` commits and the SHIP synthesis. Decide whether to schedule (1) the classification→formal_docs_manifest wiring for non-plaintext contracts, and (2) the Slice-1 chi/express coherence-fixture regeneration (a run, not a code edit). Feature H (Slice 4, personas) remains explicitly out of scope and unstarted.
