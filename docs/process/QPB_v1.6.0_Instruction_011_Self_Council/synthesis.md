# Self-Council synthesis — instruction 011 (classification → byte-citable surface)

**Verdict: SHIP after a security FIX-REQUIRED resolved.** Panelist A found a real
poisoned-manifest bypass; it is fixed and pinned. B and C SHIP'd.

Reviewed code: branch `1.6.0`, commits `6667fc6` (wiring + tests), `c4df2f3` (§8a
citability-wiring paragraph). Three panelists, each in its own git worktree, each
writing a full verdict to `reviews/011_self_council/panelist_{A,B,C}_*.md`.

## Charters
- **A — the floor survives the citability wiring** (security-critical): can a
  floored doc acquire a Tier-1/2 FORMAL_DOC record via any path?
- **B — the classification→FORMAL_DOC mapping, non-plaintext record shape, schema**.
- **C — byte-verification unchanged + cite/ unchanged + coherence-fixture honesty**.

## Panelist verdicts
- **A: FIX-REQUIRED → resolved.** The floor holds against every *document-controlled*
  path (top-level CVE, advisory renamed `.proto`/`.json`/`.d.ts`, the sidecar,
  MUST/SHALL bulletins, injection, `.py` logic, cite/-as-laundering, and an
  advisory-that-is-also-a-valid-contract). The mutation bite (make `_formal_tier`
  ignore `promotable`) produced 5 failures incl. the floor-survival test — the
  guards are load-bearing. **The bypass:** a poisoned prior
  `quality/classification_manifest.json` with the advisory's record flipped to
  `promotable: true` (keeping `tier: 4`) survived the instr-010 cache guard (which
  compared only `tier`), and `_formal_tier`'s cite/ branch then re-derived Tier 1
  via `_parse_tier_marker` — a byte-citable FORMAL_DOC for a CVE advisory with no
  hostile LLM.
- **B: SHIP.** The mapping is exactly correct across all seven cases (floored → no
  record; cite/ → `_parse_tier_marker`; top-level Tier 1/2 → that tier; top-level
  Tier 3/4/default-tier4 → no record). Non-plaintext contracts get full valid
  byte-citable records (`.proto`/OpenAPI → non-empty byte-substring excerpt,
  `document_sha256` == file sha == classification content key); `.py` stays floored.
  `_build_record_from_text` is a verbatim extraction of the pre-011 `_build_record`
  body, so cite/ record shape is byte-identical and schemas.md needed no shape
  change. Both mutation spot-checks fire.
- **C: SHIP.** Byte-verification genuinely untouched — `citation_verifier.py` and
  the `quality_gate.py` verification path are not in the diff; citation/gate suites
  green (120 + 309). Positive check: a newly-citable dumped doc's excerpt +
  `document_sha256` passes the *real* `verify_citation` (ok=True, hash-tamper
  rejected). cite/ unchanged (same Tier-2 marker resolution, same 10-field shape).
  Coherence fixtures honest: the goldens at
  `bin/tests/fixtures/render_contract_v160/{chi,express}/quality/REQUIREMENTS.md`
  still render all-Tier-3 and were NOT touched by 011 — no flip faked. The flip
  genuinely requires a live model (CLI-alone yields 0 Tier-1/2 records; the stub-AI
  run reproduces chi 14 / express 13), so the deferral is correctly scoped.

## The FIX-REQUIRED (Panelist A) — resolved (`f69f758`)
Defined `_UNRESCUABLE_FLOOR_RULES = {advisory, injection, background}` (the
implementation floor is EXCLUDED — it is legitimately sidecar/cite-rescuable). On a
cache hit, if the fresh content-only floor fires an unrescuable rule, the cache is
**discarded entirely (both `tier` AND `promotable`)** and the fresh floored
decision wins — closing the promotable-flip poison that the tier-only guard missed.
Note: Panelist A's suggested "also compare `promotable`" would have broken a
legitimate sidecar-rescued impl file on a cache hit (guard-without-sidecar reports
impl-floor/`promotable:false` while the cache correctly holds sidecar-promotion);
scoping the override to the *unrescuable* floors (impl excluded) closes the bypass
without that regression. Pinned by `test_poison_flipping_only_promotable_is_also_
defeated` (module) and `test_poisoned_classification_manifest_cannot_launder_cite_
advisory_end_to_end` (through `ingest()`).

## Recorded for the orchestrator (non-blocking)
- **schemas.md §4 does not document six emitted FORMAL_DOC fields** (`doc_id`,
  `byte_count` — documented as `bytes`, `line_count`, `citation_excerpt`,
  `ingested_at`, `schema_version`). **Pre-existing** (present pre-011 per
  `git show 6667fc6~1`), out of instruction 011's scope. Candidate for a schema
  documentation pass.
- **Coherence-fixture regeneration** (chi/express render `REQUIREMENTS.md`) requires
  a full `run_playbook.py` Phase 1-6 derivation over the dumped corpora with a live
  derivation model (gated benchmark runner), then re-snapshot the goldens. Not a
  code edit; deferred honestly.

## Verification
Full suite green after the fix (see the instruction output for the exact count);
Python 3.14.6. chi 0→14, express 0→13 Tier-1/2 FORMAL_DOC records.

**Terminal verdict: SHIP.** The mapping, record shape, and byte-verification were
solid; the poisoned-manifest bypass Panelist A named is closed with an end-to-end
test.
