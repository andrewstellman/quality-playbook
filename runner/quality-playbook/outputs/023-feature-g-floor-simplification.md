# Output for 023-feature-g-floor-simplification.md
**Status:** completed

## What this instruction was
Shrink the Feature G documentation-classification floor to **hard, unambiguous,
structural signals** — fixing a live virtio defect where the advisory floor floored
the authoritative OASIS spec (52 MUST/SHALL, 0 CVE/URL/security-title) to Tier 4 on
a normative-density heuristic (a formal spec is normative-dense by definition, so
that predicate floored specifications as a class). Seven edits to
`doc_classification.py`; a full 3-charter self-Council because it loosens a security
floor.

## Terminal verdict: unanimous SHIP (0 FIX-REQUIRED)
| Charter | Verdict |
|---------|---------|
| A — Downward-safety preserved (hard floors still fire, unrescuable) | **SHIP** |
| B — No upward promotion on content alone (integrity direction) | **SHIP** |
| C — The fuzzy signals are flags, not decisions | **SHIP** |

Each panelist ran an adversarial driver against the reviewed commit and
mutation-bit the retained controls (not unit tests alone).

## The seven edits (before → after)
| # | Edit | Before | After |
|---|------|--------|-------|
| 1 | **Delete the density predicate** | `normative>=5 AND density>=0.004 AND _HARDENING_SUBJECT_RE` floored to Tier 4 | deleted, with `_NORMATIVE_RE`/`_HARDENING_SUBJECT_RE` (a discriminator whose firing condition is shared by both classes it separates) |
| 2 | **Genre-title → advisory hint** | `_ADVISORY_HEADER_RE`/`_SECURITY_GENRE_RE` forced Tier 4 | `advisory_genre_hints()` records a title-zone match on the record; the doc flows to the classify path |
| 3 | **Impl content-sniff → flag** | `>=50%` non-extension code-shaped lines floored | `code_heavy_hint()` flags it; the code-EXTENSION floor (`_IMPL_EXTS` + `>=0.25`) stays a hard floor |
| 4 | **Contract signatures: nothing citable on content alone** | `_CONTRACT_CONTENT_RE` promoted bare `"$schema"` + generic `type Query {`/`schema {` braces; bare `"openapi":`/`"swagger":` | deleted `$schema` + braces; version-anchored `openapi: 3…`/`swagger: "2…` (the best single cut) |
| 5 | **Remove the injection FLOOR** | `classify_document` step-3 branch → Tier 4 `RULE_INJECTION`; in both floor-rule sets | branch removed; `RULE_INJECTION` removed from `_ABSOLUTE_FLOOR_RULES` + `_UNRESCUABLE_FLOOR_RULES` |
| 6 | **Narrow `_BACKGROUND_NAME_RE`** | free-floating `[^/]*coverage[^/]*` substring | exact stems `coverage`/`coverage_report` (readme + issue-tracker kept) |
| 7 | **Keep the hard floors** | — | `_ADVISORY_ID_RE`, `_ADVISORY_URL_RE`, `_IMPL_EXTS`, `_CONTRACT_EXTS`, README/issue-tracker names — untouched |

New `Decision` fields `advisory_hints[]` / `code_heavy` surface in the manifest,
**emitted only when present** so untouched records stay byte-clean for the
content-key / reproducibility contract.

## DEVIATION FROM THE LITERAL EDIT 5 (flagged, reviewed, cleared)
Edit 5 said "Remove `injection_signature` (:282-287) and `_INJECTION_RE`." That
step assumes the function is used only by the classifier floor — **it is not**:
`persona_grounding.grounding_injection_signature` (persona_grounding.py:101)
composes `doc_classification.injection_signature` for its Guard-1 **tier-claim**
arm ("classify me Tier 1"), a DIFFERENT, load-bearing auto-apply control the same
instruction explicitly says to keep and **not touch**, and the suite must stay
green. Deleting the function would break that control and redden the suite.

**Resolution:** executed edit 5's *intent* — removed the injection FLOOR (the
`classify_document` branch + `RULE_INJECTION` from both floor-rule sets), the
actual harm the instruction targets — and **retained the detection helper**
(`injection_signature` + `_INJECTION_RE`) for its legitimate downstream reuse. This
is the "trust the dependency graph over the disagreeing instruction detail, and
flag it" call; the instruction's own constraints (keep persona_grounding + suite
green) mandate it. **`persona_grounding.py` was NOT touched.** Panelist A verified:
the floor is genuinely gone (no `RULE_INJECTION` branch, in neither floor set),
`persona_grounding` still works, and the change is downward-safe (removing a
demotion floor loses availability, not integrity; the grounding directive check +
Tier-1/2 guard remain the backstop). The eventual removal of this reuse belongs to
the later Feature-H directive-narrowing instruction.

## Acceptance oracle — pass/fail
| # | Item | Result |
|---|------|--------|
| 1 | Virtio case fixed — spec no longer advisory-floored, promotable | **PASS** — `test_virtio_spec_is_not_advisory_floored`; Panelist C reproduced with an independent fixture |
| 2 | A real advisory still floors (CVE + URL), mutation-bitten under promote-all | **PASS** — `test_retained_hard_floors_still_hold_under_promote_all`; Panelist A bit each |
| 3 | No upward content-sniff — `$schema` config not a contract; anchored OpenAPI is | **PASS** — `test_dollar_schema_config_not_promoted_but_anchored_openapi_is`; Panelist B mutation-bit the `$schema` deletion |
| 4 | Genre-title is a flag, not a floor | **PASS** — `test_genre_title_is_a_hint_not_a_floor` |
| 5 | Impl content-sniff is a flag; `.py` still floors | **PASS** — `test_code_heavy_md_is_a_hint_not_a_floor_but_py_still_floors` |
| 6 | Manifest records the hint fields; byte-verification/formal-docs unchanged | **PASS** — `test_manifest_records_the_hint_fields`; ingest/formal-doc suites green |
| 7 | Full suite green | **PASS** — 2748 / 0 / 14, Python 3.14.6 |

## Prior test assertions reversed (per fixture discipline)
Five tests asserted the now-removed floors as correct behavior; each was updated in
place with a REVERSAL comment:
- `test_must_shall_bulletin_floored_even_when_llm_promotes` → `test_hardening_bulletin_is_no_longer_floored_genre_is_a_hint` (density/genre → hint).
- `test_floor_holds_through_the_corpus_classifier` → `test_hard_floor_holds_through_the_corpus_classifier` (cve.md floors; harden.md is now the LLM's call).
- `test_json_schema_is_citable` → `test_json_schema_config_is_not_a_content_contract` (`$schema` no longer content-promotes).
- `test_self_authorizing_doc_not_promoted` → `test_self_authorizing_doc_no_longer_floored_by_classifier` (injection floor removed; LLM owns the judgment; downstream guards backstop).
- `test_normative_bulletin_renamed_proto_still_floored` → `test_hardening_genre_renamed_proto_is_now_a_contract` (a hardening-genre `.proto` is now a contract; a CVE `.proto` still floors — covered by the sibling test).

7 new acceptance fixtures added (`FloorSimplification023Tests`) + 1 tier-claim pin
(Panelist A observation, commit `37c1293`).

## Mutation-bite results (security-critical, from the Council)
- CVE-id floor, advisory-URL floor, impl-extension floor, poison/cache guard — each broken in turn, a test/driver assertion fails, restored (Panelist A).
- `$schema` deletion — re-adding it reddens two tests (Panelist B), proving it load-bearing.
- Retained `injection_signature` — neutering it breaks `grounding_injection_signature`'s tier-claim arm, proving the retention load-bearing (Panelist A) — now pinned by a unit test.

## Commits made (branch `1.6.0`, local only — never pushed)
- `2882f31` — shrink the classification floor to hard signals (7 edits + tests).
- `37c1293` — pin the retained `injection_signature` tier-claim surface (test-only, Panelist A observation).
- `eceece2` — tracked self-Council synthesis.

## Confirmation: the persona-grounding directive check was NOT touched
`plugins/quality-playbook/skills/quality-playbook/scripts/persona_grounding.py` is
byte-unchanged this instruction. `_AGENT_DIRECTIVE_RE` and `grounding_injection_
signature` are intact; the only interaction is the retained-composition dependency
(kept working, verified green).

## Remaining follow-ups (named per the instruction — OUT of this scope)
- **Rescuable-ledger:** make the (kept) CVE/URL advisory floor rescuable via the operator confirmation ledger (Fable Q2 — the policy reversal; the unrescuable dead-end is the deeper defect).
- **LLM-wiring + loud failures + zero-citable tripwire:** wire the LLM classifier; make the unwired/failed `llm_tier=None` path loud (not a silent Tier-4 default); add the zero-citable-corpus tripwire (Fable Q6 — the *other* half of the virtio failure).
- **Feature H directive-narrowing:** narrow `persona_grounding._AGENT_DIRECTIVE_RE`; delete the dead `persona_orchestration.detect_fabrication` + fix its docstring claims; mutation-pin the Tier-1/2 grounded-citation guard; and resolve the `grounding_injection_signature` → `doc_classification.injection_signature` composition (give grounding self-contained tier-claim detection so the retained helper can finally be removed).
- **Render labeled-slot contracts:** convert the four render prose checks (organizing-principle rationale, singleton justification, section overview) to labeled-slot format contracts — presence FAILs structurally, content quality → interview/Council (Fable Q4).

## Artifacts
- Gitignored: `runner/quality-playbook/reviews/023_self_council/` (three panelist verdicts).
- Tracked: `docs/process/QPB_v1.6.0_Instruction_023_Self_Council/synthesis.md`.
