# Output for 013-feature-h-persona-catalog-and-selection.md
**Status:** completed

## Files created / changed
| Path | Note |
|------|------|
| `plugins/.../scripts/persona_catalog.py` | **New** stdlib-only module: the data-first catalog, `select_personas()` (mechanical anchor enforcement + hallucinated-lens drop), `build_selection_manifest()` (reviewable content-keyed record). |
| `bin/tests/test_persona_catalog_v160.py` | **New** — 12 tests: catalog shape, adversarial anchor enforcement, selection-record shape + reproducibility, sample selection. |
| `references/requirements_pipeline.md` | § E.8 "Select validation personas (Feature H)" — the LLM-facing menu + anchored-selection protocol, structurally parallel to E.5. |
| `docs/process/QPB_v1.6.0_Instruction_013_Self_Council/synthesis.md` | Tracked focused self-review. |
| `runner/.../reviews/013_self_council/synthesis.md` | Gitignored self-review. |

## Commits made (branch `1.6.0`, local only — never pushed)
- `199d84d` — Feature H slice 1: persona catalog + anchored selection (+ E.8 + tests).
- `0f75320` — tracked self-review.

## Acceptance oracle — pass/fail per item
| # | Item | Result |
|---|------|--------|
| 1 | Catalog enumerates anchored + selectable lenses, each with a criterion; data-first | **PASS** — `CatalogShapeTests` |
| 2 | Anchor enforcement: adversarial selection omitting security/domain still yields it (test-proven) | **PASS** — `AnchorEnforcementTests` (5 tests) |
| 3 | Selection recorder produces a reviewable record parallel to the organizing-principle precedent | **PASS** — `build_selection_manifest` + § E.8; precedent = `requirements_pipeline.md` § E.5 |
| 4 | Sample selection over a real repo shape yields a sensible set | **PASS** — `SampleSelectionTests` (library → domain + security + api-consumer) |
| 5 | Existing suite unchanged and green | **PASS** — 2672 / 0 / 14 |

## The catalog contents
**Anchored (always selected, never skippable):**
- `domain-expert` — specialized per system from the Phase 1 domain + gathered docs (e.g. "expert in Go HTTP routing and net/http").
- `security-reviewer` — anchored because security gaps are cross-cutting and chronically under-weighted by a system's own author.

**Selectable (AI-chosen per system with a stated reason), each with a `select_when` criterion:**
`api-consumer` (library / public API), `operator-sre` (deployed service), `data-privacy` (regulated data), `accessibility` (user-facing UI), `performance` (hot path / latency budget), `reliability` (distributed / survives partial failure), `adopter` (users whose abandonment risks matter). The catalog is a list of dicts — **adding a lens is a data edit, no code surgery.**

## How anchor-enforcement is implemented + its test
`select_personas(proposed)` builds the chosen set from the LLM's `proposed` list (dropping any off-catalog/hallucinated lens and collapsing duplicates), then **forces both anchored ids into the result in catalog order regardless of `proposed`**. A selection that omits domain or security is corrected here, mechanically — not left to prompt discipline. The load-bearing test `test_anchor_enforcement_is_load_bearing` proves the security lens is present *because of the anchor* (it was never proposed) by asserting it carries `anchored: true` and an "anchored" justification; `test_selection_omitting_security_still_contains_it` / `..._domain_...` / `test_empty_selection_still_yields_both_anchors` / `test_hallucinated_lens_is_dropped_not_added` cover the adversarial cases.

## The selection-record shape + the precedent it mirrors
**Precedent:** `references/requirements_pipeline.md` § E.5 (organizing principle, instr 006) — a menu with per-lens criteria + a recorded, justified, operator-validated choice. **Mirrored two ways:**
- **Menu in-place** as § E.8 (added to the same file as E.5, not a new reference doc — to match E.5's location and avoid the references-glob bundle-count drift).
- **Recorded choice:** `build_selection_manifest(selected)` → `{schema_version, generated_at, selection_sha256, records[]}`; each record: `id`, `title`, `anchored`, `justification`, optional `specialization`. Content-keyed on lens-ids + justifications (`selection_sha256`), so a re-selection with the same inputs reproduces the same record — the same "surface the choice so the operator can review who validates the spec and why" discipline as the organizing-principle statement and Feature G's classification manifest.

## Sample selection over a real repo
chi/express are consumed-as-a-library systems. A selection `[domain-expert (specialization "expert in Go HTTP routing"), api-consumer ("consumed feature-by-feature as a library")]` resolves to: **domain-expert, security-reviewer (anchored, forced in), api-consumer** — anchors rendering first, a defensible additional lens with a stated reason. (Test `test_library_yields_domain_security_and_api_consumer`.)

## Scope discipline
No persona execution, sub-agent orchestration, tool-allowlist isolation, guards, merge, or revert — those are later Feature H slices. The module has no I/O beyond an in-memory record and imports nothing from the harness. **Not bundled into the install closure yet** (deliberate — nothing at adopter runtime imports it until the persona-execution slice); recorded below so the execution slice adds it.

## §8b selection-paragraph — underspecified / notes
- **Where the selection record is persisted at run time** is left to the caller — §8b specifies the *content* (chosen lenses + justification, reviewable) but not the on-disk path. `build_selection_manifest` returns the record; a natural home is `quality/persona_selection.json` (parallel to `classification_manifest.json`), to be wired when the persona-execution slice lands. Flagged, not decided here.
- **The domain-expert specialization string** is derived by the LLM from the Phase 1 domain; the catalog marks the lens `specialized_per_system` and the selection carries the concrete specialization, but the derivation of that string is the LLM's job (like the organizing-principle rationale).

## For the orchestrator — bundle when execution lands
`persona_catalog.py` must be added to every bundle-enumeration site (install_skill._bundle_files, qpb_validate INSTALL_CLOSURE + count-pin, run_state_lib._FLAT_LAYOUT_BUNDLED_BIN_FILES, AGENTS.md cp recipes, setup_repos.sh) **in the slice that wires persona execution at adopter runtime** — not now, since nothing imports it adopter-side yet.

## Next action expected from orchestrator
Sequence the next Feature H slice — the security core (fresh-context sub-agent orchestration + tool-allowlist least-privilege isolation), which consumes this slice's selected persona set and needs its own worktree-isolated mutation Council (per the 012 decomposition).
