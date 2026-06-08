# Synthesis — 208 Worker self-Council (3-panelist)

**SHIP recommendation: YES** — after applying A's FIX-REQUIRED (5 test files) + C's HIGH-priority CONCERN (10 README links) pre-push. C's orientation-doc bare-prose drift correctly deferred per `[[feedback_orientation_docs_release_gate]]` (TOOLKIT_TEST_PROTOCOL-gated, not Council).

## Panel summary

| Panelist | Charter | Initial verdict | After remediation |
|----------|---------|----------------|-------------------|
| A | Layout correctness + defensive sweep | **FIX-REQUIRED** (5 test files) | **SHIP** (all 5 swept) |
| B | Build + install path correctness | **SHIP** | (unchanged) |
| C | Plugin marketplace + test sufficiency + defensive sweep | **CONCERN** (10 README links + orientation drift) | **SHIP** (10 README links fixed; orientation drift deferred) |

## Panelist A verdict — layout clean (with 5-test FIX-REQUIRED resolved)

- **`_bundle_files()` audit**: All 57 enumerated source paths resolve under `skills/quality-playbook/...`. `_resolve_bundle_source_root()` + `_scripts_dirname()` correctly handle both post-208 nested clone AND flat bundle layouts.
- **No-duplicates**: Every old root path (`SKILL.md`, `references/`, `phase_prompts/`, `agents/`, `quality_gate.py`, `ai_context/TOOLKIT.md`, `skill-template.gitignore`, `.github/skills/quality_gate/quality_gate.py`) absent at root. Legacy `.github/skills/quality_gate/__init__.py` is a re-export shim.
- **`_bundle/` internal layout**: Flat layout preserved bit-for-bit (57 destination files).
- **`marketplace.json`**: Valid JSON; `skills` ABSENT; `strict` ABSENT. `plugin.json` is the new metadata file, version 1.5.8.

### Panelist A FIX-REQUIRED — RESOLVED PRE-PUSH

**Issue**: 5 `bin/tests/*.py` files hardcode the OLD `.github/skills/quality_gate/` path for `import quality_gate`. Full `unittest discover` runs masked the failure because an earlier-loaded test primes `sys.modules['quality_gate']` — but single-file TDD on each file independently raises `ModuleNotFoundError: No module named 'quality_gate'`.

**Resolution**: Updated all 5 files to use `skills/quality-playbook/scripts/` path (mirroring the correct pattern already in `test_phase7_variations.py:36-42`):
- `bin/tests/test_cardinality_gate.py:16-19`
- `bin/tests/test_citation_stale.py:36-40`
- `bin/tests/test_phase3_prompt_worked_example.py:26-28`
- `bin/tests/test_phase6_integration.py:34-38`
- `bin/tests/test_quality_gate_language_detection.py:53-56`

Each fix also adds the v1.5.8-instruction-208 provenance comment for traceability. Verified empirically:

```bash
$ for f in test_cardinality_gate test_citation_stale test_phase3_prompt_worked_example test_phase6_integration test_quality_gate_language_detection; do python3 -m unittest bin.tests.$f 2>&1 | tail -1; done
OK
OK
OK
OK
OK
```

All 5 pass in single-file isolation.

## Panelist B verdict — build + install paths clean

| Probe | Expected | Actual |
|-------|----------|--------|
| `publish_pip --dry-run` | 8/8 preflights pass; wheel + sdist build | ✓ |
| Wheel `_bundle/SKILL.md` + `_bundle/bin/citation_verifier.py` flat | ✓ | ✓ |
| `publish_npm --dry-run` | 7/7 preflights pass | 3/7 pass through; halts at `npm whoami` (operator env, not a code issue) |
| `build_channel_package --stage` | OK | OK (59 staged files) |
| `npm pack --dry-run --json` | Stdout starts with `[` (no 203 regression) | ✓ |
| Clone-install file count | 57 | ✓ (exact bit-for-bit match) |
| Shim delegation (`python3 -m bin.install_skill`) | works | ✓ (78-line thin shim) |
| `from bin import install_skill` re-exports | `main`/`install`/`_BANNER_NAME`/`_BANNER_URL`/`_bundle_files`/`_resolve_bundle_source_root`/`_scripts_dirname` | ✓ all present |

### Panelist B NITs (deferred)
- B-NIT1: npm preflight ordering ergonomics — `npm whoami` could be deferred until just before publish
- B-NIT2: shim internal module name choice (load-bearing for sys.modules; cosmetic)

## Panelist C verdict — Plugin marketplace + AUDIT + defensive sweep

### Test coverage audit (15/15)

`bin/tests/test_plugin_layout_208.py` (228 lines, 15 layout invariants, all pass) covers every invariant the instruction's § Tests bullet enumerated. `test_plugin_json_version_matches_pyproject` is the AUDIT-table invariant the build agent flagged.

### Mutation verification (independently re-performed)

C re-performed: snapshot via `shutil.copy2` to `/tmp/qpb_208_panelC_snapshot.py`, mutation (moved SKILL.md to root), failing test confirmed (`AssertionError: False is not true : SKILL.md must live at ...`), restore via `shutil.copy2` per `[[feedback_mutation_bite_pycache]]`, scoped `bin/__pycache__` purge, all 15 tests pass, working tree byte-clean. Orchestrator's report reproduced.

### AUDIT-table extension verification

`stamp_channel_manifest_versions()` is correctly written to stamp 4 sites (pyproject.toml, package.json, marketplace.json, plugin.json), but in practice only 3 get stamped because the current `marketplace.json` has no top-level `version` field (silent-skip is the active path — intentional per the marketplace schema). Build agent's "4 sites" claim is slightly misleading; reality is 3 stamped + 1 schema-correct skip.

### Panelist C CONCERN (C-C1) — RESOLVED PRE-PUSH

**Issue**: Defensive sweep per the 207-codified Council charter (`DEVELOPMENT_PROCESS.md § Defensive-sweep Council charter for content-fix instructions`) surfaced 10 broken inline markdown links / raw URLs in README.md pointing at OLD root paths. **3 HIGH-priority** (lines 51, 186 link, 186 raw URL) — first-page user-facing recipes that will produce visible 404s on the GitHub render of v1.5.8. The remaining 7 are in CHANGELOG-style sections (lines 630, 669, 676, 967, 971, 992) but ARE the same defect class.

**Resolution**: All 10 broken README links fixed pre-push:
- `references/DOC_GATHERING_PROMPT.md` → `skills/quality-playbook/references/DOC_GATHERING_PROMPT.md` (and the raw-URL variant)
- `references/role_map_queries.md` → `skills/quality-playbook/references/role_map_queries.md`
- `references/code-only-mode.md` → `skills/quality-playbook/references/code-only-mode.md`
- `agents/calibration_orchestrator.md` → `skills/quality-playbook/agents/calibration_orchestrator.md` (×2)
- `references/run_state_schema.md` → `skills/quality-playbook/references/run_state_schema.md`
- `bin/run_state_lib.py` → `skills/quality-playbook/scripts/run_state_lib.py`
- `references/exploration_patterns.md` → `skills/quality-playbook/references/exploration_patterns.md`

Verified via re-grep: zero residual broken-link patterns in README.md.

### Orientation-doc drift — DEFERRED per [[feedback_orientation_docs_release_gate]]

C also surfaced ~40 bare-prose mentions of `references/...`, `agents/...`, `bin/run_state_lib.py` across `AGENTS.md` + 5 `ai_context/*.md` orientation docs. Not markdown links so not visibly broken on GitHub, but they mislead maintainer AIs following these as navigational hints.

Per `[[feedback_orientation_docs_release_gate]]` memory: "version bumps touching TOOLKIT/IMPROVEMENT_LOOP/README/DEVELOPMENT_CONTEXT.md run `ai_context/TOOLKIT_TEST_PROTOCOL.md`. Council patterns are for code changes only." Orientation-doc bare-prose drift is TOOLKIT_TEST_PROTOCOL-gated, NOT Council. **Deferred to TOOLKIT-Test-Protocol-driven follow-up sweep** as C explicitly recommended.

### Panelist C NITs (deferred)
- C-NIT1: docstring-style file paths in module docstrings could also drift; lower priority
- C-NIT2: README's `Repository structure` ASCII tree could be regenerated programmatically

## Key panel agreements

1. **File moves all correct** (A confirmed `_bundle_files()` audit + no-duplicates)
2. **All 3 install paths work** (B verified pip + npm-up-to-auth + clone-install + shim)
3. **Bundle file count preserved** 57 = 57 bit-for-bit (A + B both confirmed)
4. **Bundle internal layout flat** (`_bundle/SKILL.md`, `_bundle/bin/...` — A + B both confirmed)
5. **`_bundle/` internal layout unchanged** = PyPI/npm v1.5.8 backward-compat preserved
6. **Shim delegation works** end-to-end (B + C both confirmed)
7. **Mutation-bite verified twice** (orchestrator + Panelist C independent)
8. **A's FIX-REQUIRED** was a real bug (single-file TDD broken on 5 files); fixed
9. **C's CONCERN** correctly elevated per the 207-codified defensive-sweep charter; HIGH-priority README links fixed; orientation drift deferred per memory
10. **AUDIT-table extension** stamps 4 sites correctly (3 active + 1 schema-correct skip)

## Recommendation

**SHIP** — after the 2 pre-push remediations applied (A's 5 test files + C's 10 README links).

Push to origin/1.5.8 requires **operator confirmation** per instruction's Done definition: "No push to origin without operator approval."

Current local state on 1.5.8 ahead of origin (post-208):
- `bfea8a1` (208 build)
- (this commit — Council + A FIX-REQUIRED + C HIGH-priority CONCERN)
- + 17 prior 202-207 + operator commits

## v1.5.x polish backlog (additional NITs from 208 Council)

- A: (none beyond the FIX-REQUIRED already resolved)
- B-NIT1: npm preflight `npm whoami` ordering
- B-NIT2: shim internal module name cosmetic
- C-NIT1: docstring-style file paths in module docstrings
- C-NIT2: README's Repository structure ASCII tree programmatic regen
- **DEFERRED to TOOLKIT_TEST_PROTOCOL sweep**: orientation-doc bare-prose drift (AGENTS.md + 5 ai_context/*.md, ~40 occurrences)

## Methodology echo

The 208 review demonstrates two patterns now codified in `DEVELOPMENT_PROCESS.md`:

1. **The 207-codified defensive-sweep charter for content-fix instructions** — C found 10 README links the instruction's enumerated deliverables didn't name, but they were the same defect class (OLD root paths). The charter mandates extending the analysis beyond the instruction's enumerated sites; C did exactly that.

2. **The `[[feedback_orientation_docs_release_gate]]` distinction** — orientation docs (AGENTS.md + ai_context/IMPROVEMENT_LOOP.md / DEVELOPMENT_CONTEXT.md / TOOLKIT.md / README) follow TOOLKIT_TEST_PROTOCOL, NOT Council. C correctly applied this distinction: fix the user-facing README links via Council remediation; defer the orientation-doc drift to TOOLKIT_TEST_PROTOCOL.

**Both patterns are visible methodology improvements that compound across the 202-208 publish-channel hardening arc.** Each instruction's Council surfaces something the instruction didn't explicitly name; the charter for "expand beyond the named sites" is now load-bearing.
