# Output for 011-feature-g-classification-to-citable-wiring.md
**Status:** completed

## Files created / changed
| Path | Note |
|------|------|
| `plugins/.../scripts/reference_docs_ingest.py` | `ingest()` rewritten classification-driven: FORMAL_DOC records built from the classification decisions. New `_formal_tier()` (tier from the Decision, floor read not re-litigated) + `_build_record_from_text()` (generalized from `_build_record`); `ingest()` gains `llm_classifier`. |
| `plugins/.../scripts/doc_classification.py` | Security fix (self-Council A): `_UNRESCUABLE_FLOOR_RULES`; the cache guard discards a prior record entirely (tier AND promotable) whenever an unrescuable floor fires. |
| `bin/tests/test_doc_classification_v160.py` | +10 tests: citability wiring, non-plaintext-contract records, floor-survival mutation (LLM stubbed to promote all), reconciliation, cite/ unchanged, and the two poison tests (promotable-flip + end-to-end through `ingest()`). |
| `docs/design/QPB_v1.6.0_Design.md` | §8a "Citability wiring" paragraph (item 7). |
| `docs/process/QPB_v1.6.0_Instruction_011_Self_Council/synthesis.md` | Tracked self-Council synthesis. |
| `runner/.../reviews/011_self_council/{panelist_A,B,C,synthesis}.md` | Gitignored full self-Council artifacts. |

## Commits made (branch `1.6.0`, local only — never pushed)
- `6667fc6` — wire classification → the byte-citable FORMAL_DOC surface (+ tests).
- `c4df2f3` — §8a citability-wiring paragraph.
- `f69f758` — **security fix (self-Council A):** close the promotable-flip poison in the cache guard.
- `d1350e8` — tracked self-Council synthesis.

## chi/express Tier-1/2 FORMAL_DOC before/after
| Target | FORMAL_DOC Tier-1/2 records BEFORE (010) | AFTER (011) |
|--------|------------------------------------------|-------------|
| chi | **0** | **14** |
| express | **0** | **13** |

(Before this wiring, top-level dumped docs were hardcoded `tier = 4` in `formal_docs_manifest.json` — classified Tier-1 in the classification manifest but not byte-citable. Now they are FORMAL_DOC records the gate can verify. CLI-alone without an AI classifier still yields 0 — the AI assigns the tiers that the wiring honors; Panelist C confirmed no over-claim.)

## Non-plaintext contract citability
A dumped `.proto` / OpenAPI `.json` now gets a full FORMAL_DOC record: non-empty byte-derived `citation_excerpt`, `document_sha256` == the file's sha, `role: external-spec`, `tier ∈ {1,2}`. A REQ citing it passes `citation_verifier` (Panelist C ran the positive `verify_citation` check: ok=True, hash-tamper rejected). A `.py` logic file stays impl-floored — no record.

## Floor-survival mutation results (each with the LLM stubbed to promote everything)
| Case | Tier-1/2 FORMAL_DOC record? |
|------|------|
| top-level CVE advisory | **No** (advisory-floor) |
| renamed `cve-2024-x.proto` advisory | **No** (content-floor before contract carve-out) |
| MUST/SHALL security bulletin | **No** |
| injection self-promoter | **No** |
| `.py` implementation source | **No** |
| operator sidecar naming a CVE `.proto` | **No** (sidecar rescues impl only) |
| cite/ CVE advisory | **No** (cite is sidecar-semantics) |
| **poisoned** classification_manifest (advisory `promotable:true`, end-to-end) | **No** (fix `f69f758`) |
| a genuinely-authoritative dumped spec | **Yes** (not a blanket block) |

Mutation-bite (Panelist A): making `_formal_tier` ignore `promotable` → 5 test failures incl. the floor-survival test, proving the guards are load-bearing.

## Reconciliation
Each FORMAL_DOC record's `document_sha256` equals the classification manifest's content key for the same `source_path` (both `sha256(content)`); a re-run with unchanged docs reproduces the same citable set. Verified by `test_reconciliation_formal_sha_equals_classification_key`.

## The security FIX-REQUIRED (self-Council Panelist A) and its resolution
Panelist A found a poisoned-manifest bypass: a hand-edited `quality/classification_manifest.json` with an advisory record flipped to `promotable: true` (keeping `tier: 4`) slipped the instr-010 cache guard (which compared only `tier`), and `_formal_tier`'s cite/ branch then re-derived Tier 1 via `_parse_tier_marker` — a byte-citable FORMAL_DOC for a CVE advisory with **no hostile LLM**. Fixed (`f69f758`): the cache guard now discards a prior record entirely — both `tier` AND `promotable` — whenever the fresh content-only floor fires an **unrescuable** rule (advisory/injection/background; the implementation floor is excluded because it is legitimately sidecar/cite-rescuable). Panelist A's literal "also compare `promotable`" suggestion would have broken a legitimate sidecar-rescued impl file on a cache hit; scoping to the unrescuable floors closes the bypass without that regression. Pinned by a module test and an end-to-end `ingest()` test.

## `cite/` unchanged
A cite/ plaintext spec still produces the same Tier-1/2 record via `_parse_tier_marker` (Tier-2 marker still resolves). `_build_record_from_text` is a verbatim extraction of the pre-011 `_build_record` body, so cite/ record shape is byte-identical (Panelist B). The one intentional, documented, test-covered change: a cite/-placed advisory is no longer laundered to citable (§8a: cite is sidecar-semantics — rescues impl, never advisory).

## Coherence fixtures — NOT regenerated (a live run is required; not faked)
The Slice-1 coherence goldens at `bin/tests/fixtures/render_contract_v160/{chi,express}/quality/REQUIREMENTS.md` still render all-Tier-3 and were **not touched** by this instruction (Panelist C confirmed via git; no flip faked). The flip genuinely requires a full **`run_playbook.py` Phase 1-6 derivation over the dumped chi/express corpora with a live derivation model** (the gated benchmark runner) — CLI-alone yields 0 Tier-1/2 records, so a code instruction cannot produce the flip. **The exact run needed:** dump each repo's `docs_gathered/` into `reference_docs/` (no `cite/`), run the full playbook with a live model so the AI classifies + assigns tiers, then re-snapshot those two golden `REQUIREMENTS.md` fixtures. Recorded for the orchestrator.

## Byte-verification contract unchanged
`citation_verifier.py` and the `quality_gate.py` verification path are not in the diff (Panelist C: `git show` confirmed); citation + gate suites green. The wiring adds *which* docs are citable, not *how* a citation is verified.

## Producers touched (OD-10 seam)
The wiring is in the shared ingest surface (`reference_docs_ingest.py`), which produces `formal_docs_manifest.json` — consumed by both the code-path pipeline and `bin/skill_derivation/`. One change, both producers benefit; confirmed as in instruction 010.

## §8a wiring paragraph added
Added a "Citability wiring" paragraph to §8a: the classification manifest is the source of truth for top-level tiers; promotable Tier-1/2 → FORMAL_DOC record (incl. machine-readable contracts); floored/background → Tier-4 context; the floor is read from the classification decision, never re-litigated; the two manifests reconcile on `document_sha256`; Verification 1 is now end-to-end (0 → 14 / 0 → 13).

## Verification
Full suite **2655 passed / 0 failed / 13 skipped**, Python 3.14.6.

## Anything underspecified
- **schemas.md §4 does not document six emitted FORMAL_DOC fields** (`doc_id`, `byte_count` — documented as `bytes` — `line_count`, `citation_excerpt`, `ingested_at`, `schema_version`). This is **pre-existing** (present pre-011), out of this instruction's scope, but surfaced by Panelist B — a candidate for a schema-documentation pass.
- **The real-run tier-assignment mechanism** (how the AI's Tier-1/2 assignments reach the classification manifest for a top-level plaintext spec) is: the AI records tiers into `classification_manifest.json` per the phase-1 guide, and the content-keyed reuse (floor-guarded) persists them across ingests. §8a describes the tiering but not this operational round-trip explicitly; the wiring honors whatever tiers the classification decision carries.

## Next action expected from orchestrator
Review the four `1.6.0` commits and the SHIP synthesis. Decide whether to schedule (1) the chi/express coherence-fixture regeneration (a live Phase 1-6 run, not a code edit — exact run specified above), and (2) the pre-existing schemas.md §4 FORMAL_DOC field-documentation gap. Feature H (Slice 4, personas) remains out of scope and unstarted.
