# Panelist C — Marketplace + Test Sufficiency + Defensive Sweep

Reviewing instruction 208 (plugin-native repo restructure) at HEAD `bfea8a1` on branch `1.5.8` per Protocol 1 self-Council.

## 1. Charter recap

Verify `test_plugin_layout_208.py` covers the instruction's enumerated layout invariants, independently re-perform the mutation bite (snapshot → move-to-root → run failing test → restore via `shutil.copy2` → re-verify), defensive-sweep docs/JSON for OTHER content-fix-style hardcoded path sites not enumerated in the instruction's deliverables, and verify `stamp_channel_manifest_versions()` now stamps the marketplace.json + plugin.json sites alongside pyproject.toml + package.json.

## 2. test_plugin_layout_208.py coverage audit (15 invariants vs instruction's enumerated list)

`bin/tests/test_plugin_layout_208.py` — 228 lines, 15 `def test_` methods, all 15 pass under the as-shipped tree (`python3 -m unittest test_plugin_layout_208` → `Ran 15 tests in 0.014s OK`).

Cross-referenced against the commit message's § Tests bullet (instruction 208's enumerated test contract):

| Instruction-enumerated invariant | Test method(s) | Status |
|---|---|---|
| SKILL.md at canonical plugin location | `test_skill_md_at_canonical_plugin_location` | covered |
| no legacy SKILL.md at the repo root | `test_skill_md_not_at_repo_root_anymore` + `test_no_legacy_skill_md_at_repo_root` | covered (2 backstops; one uses `is_file()` direct check, the other enumerates `repo_root.iterdir()` — different code paths so a single-mode false positive can't hide drift) |
| marketplace.json drops inline `skills` + `strict` fields | `test_marketplace_json_drops_inline_skills_field` (subTests both fields) | covered |
| plugin.json version matches pyproject.toml | `test_plugin_json_version_matches_pyproject` | covered (AUDIT-table pattern — the version-stamping invariant) |
| bundle internal layout stays flat (no `skills/` prefix on `_bundle_files()` dst) | `test_bundle_internal_layout_frozen` | covered (imports `bin.install_skill._bundle_files`, asserts no `dst_rel` starts with `"skills/"`) |

Bonus coverage beyond the enumerated list (8 additional invariants — all reasonable backstops, none over-broad):

- `test_skills_quality_playbook_directory_exists` — root assertion the rest of the suite depends on
- `test_references_directory_in_skill_folder` — references/ moved + non-empty
- `test_phase_prompts_directory_in_skill_folder` — explicitly subTests `phase1.md`…`phase6.md` (load-bearing for Mode A + Mode B)
- `test_agents_directory_in_skill_folder` — subTests both bundled agent files
- `test_quality_gate_in_scripts_folder` — `scripts/quality_gate.py` (canonical Phase 5 gate)
- `test_toolkit_md_in_skill_ai_context_folder` — adopter-facing `ai_context/TOOLKIT.md`
- `test_claude_plugin_marketplace_json_exists` / `test_claude_plugin_plugin_json_exists` — both manifests present
- `test_legacy_dirs_not_at_repo_root` — subTests `references` / `phase_prompts` / `agents` are all gone from root (catches a partial revert)

Verdict: **coverage matches the instruction's enumeration; no gaps**. The `test_bundle_internal_layout_frozen` test in particular is a strong defensive backstop — it imports the actual `_bundle_files()` function and checks destination paths, so a future refactor that re-layers the bundle would fail loudly. The plugin.json↔pyproject.toml version-lockstep test is the right shape for an AUDIT-table invariant.

## 3. Mutation verification — re-performed independently

Per `[[feedback_mutation_bite_pycache]]`: snapshot via `shutil.copy2` to `/tmp/qpb_208_panelC_snapshot.py`, mutate, purge bin pycache, run failing test, restore via `shutil.copy2`, re-verify clean.

```
1. shutil.copy2(skills/quality-playbook/SKILL.md, /tmp/qpb_208_panelC_snapshot.py)   # 132613 bytes
2. mv skills/quality-playbook/SKILL.md SKILL.md                                       # move back to root
3. python3 -m unittest test_plugin_layout_208.PluginLayoutTests.test_skill_md_at_canonical_plugin_location
   → FAILED (failures=1)
     AssertionError: False is not true : SKILL.md must live at
     /Users/andrewstellman/Documents/QPB/skills/quality-playbook/SKILL.md for the plugin
     marketplace mechanism to auto-discover the skill
4. Also ran the 2 backstops:
   - test_skill_md_not_at_repo_root_anymore  → FAILED (catches root-side residue)
   - test_no_legacy_skill_md_at_repo_root    → FAILED (catches root-side residue)
   All three fire correctly under mutation.
5. shutil.copy2(/tmp/qpb_208_panelC_snapshot.py, skills/quality-playbook/SKILL.md)    # 132613 bytes restored
   os.unlink(SKILL.md)                                                                # remove root copy
6. find bin -name __pycache__ -prune -exec rm -rf {} +                                # purge stale .pyc
7. python3 -m unittest test_plugin_layout_208  → Ran 15 tests in 0.019s OK
8. git status → working tree clean (snapshot restored bit-for-bit)
```

Mutation correctly fails the canonical-location test AND both backstops. Restore verified by working-tree-clean git state. Orchestrator's report (worker step 5) reproduced; **mutation bite holds**.

## 4. Defensive sweep results — load-bearing finding

Per DEVELOPMENT_PROCESS.md § Defensive-sweep Council charter: "identify any OTHER content-fix-style hardcoded path that wasn't enumerated in the instruction's deliverables but represents the same defect class."

The same defect class is **prose references (markdown links or bare path mentions) that still point to root-level `references/`, `agents/`, `phase_prompts/`, or moved `bin/*.py` paths after the 208 move**. The instruction's deliverables list says "README.md — Repository structure section rewritten; install-recipe cp blocks updated" but stops there. I verified the install-recipe cp blocks ARE updated (they correctly use `QPB_SKILL_SRC=skills/quality-playbook`). The instruction did NOT enumerate the inline narrative markdown links elsewhere in README.md, AGENTS.md, or `ai_context/*.md`. Sweep results:

### 4a. README.md — broken markdown links (FIX-REQUIRED class)

These are `[text](path)` links that render as 404s on GitHub because the destination file moved to `skills/quality-playbook/...`. Verified each target file is **missing** at the old root path:

| Site | Current value | Should-be | Priority |
|---|---|---|---|
| README.md:51 | `[…](references/DOC_GATHERING_PROMPT.md)` | `skills/quality-playbook/references/DOC_GATHERING_PROMPT.md` | HIGH — Step 1 user instruction; the very first recipe a new adopter encounters |
| README.md:186 (link) | `[…](references/DOC_GATHERING_PROMPT.md)` | same | HIGH — Step 2 "easiest way" recipe |
| README.md:186 (raw URL) | `https://raw.githubusercontent.com/andrewstellman/quality-playbook/refs/heads/main/references/DOC_GATHERING_PROMPT.md` | `…/refs/heads/main/skills/quality-playbook/references/DOC_GATHERING_PROMPT.md` | HIGH — operator copy-paste fetch URL, will 404 once main moves past 1.5.7 |
| README.md:630 | `[…](references/role_map_queries.md)` | `skills/quality-playbook/references/role_map_queries.md` | MEDIUM — changelog block (still public-facing) |
| README.md:669 | `[…](references/code-only-mode.md)` | `skills/quality-playbook/references/code-only-mode.md` | MEDIUM |
| README.md:676 | `[…](agents/calibration_orchestrator.md)` | `skills/quality-playbook/agents/calibration_orchestrator.md` | MEDIUM |
| README.md:967 (link 1) | `[…](references/run_state_schema.md)` | `skills/quality-playbook/references/run_state_schema.md` | MEDIUM |
| README.md:967 (link 2) | `[…](bin/run_state_lib.py)` | `skills/quality-playbook/scripts/run_state_lib.py` | MEDIUM (`bin/run_state_lib.py` no longer exists; module moved to `scripts/`) |
| README.md:971 | `[…](agents/calibration_orchestrator.md)` | `skills/quality-playbook/agents/calibration_orchestrator.md` | MEDIUM |
| README.md:992 | `[…](references/exploration_patterns.md)` | `skills/quality-playbook/references/exploration_patterns.md` | MEDIUM |

Confirmed not-broken (path still exists at old location):
- README.md:643 `[…](bin/install_skill.py)` → `bin/install_skill.py` is the thin shim, still at this path. OK.
- README.md:972 `[…](bin/visualize_calibration.py)` → still at `bin/` (dev-only, not bundled). OK.
- ai_context/* and Readme link to `ai_context/TOOLKIT_TEST_PROTOCOL.md` and `ai_context/IMPROVEMENT_LOOP.md` paths — both still exist (TOOLKIT.md moved into the skill folder; the orientation docs stayed). OK.

That's **10 broken inline markdown links in README.md** (8 markdown links + 1 raw URL + 1 sibling link on line 967). These will display as broken hyperlinks on the GitHub render of the v1.5.8 tag.

### 4b. AGENTS.md and ai_context/*.md — bare prose path references (CONCERN class)

These are `\`references/foo.md\`` or `\`bin/run_state_lib.py\`` mentions in prose — not markdown links, but readers (especially AI agents being onboarded via these orientation docs) will look for them at the cited path and not find them.

| File | Approx count | Examples |
|---|---|---|
| AGENTS.md | 4+ | line 14 `references/iteration.md`; line 20 `references/runners_and_models.md`; line 29 `references/run_state_schema.md`; line 230 `phase_prompts/phase6.md`, `phase_prompts/phase6_auditor.md`, `references/what_just_happened.md` |
| ai_context/IMPROVEMENT_LOOP.md | 8+ | `agents/calibration_orchestrator.md`, `bin/run_state_lib.py`, `bin/visualize_calibration.py` (the visualize one is fine), `references/exploration_patterns.md`, `references/iteration.md`, `references/run_state_schema.md`, `references/requirements_pipeline.md`, `references/requirements_review.md`, `references/requirements_refinement.md`, `bin/citation_verifier.py` |
| ai_context/CALIBRATION_PROTOCOL.md | 10+ | `agents/calibration_orchestrator.md` (5+ occurrences), `references/run_state_schema.md` (multiple), `references/exploration_patterns.md`, `bin/run_state_lib.py` |
| ai_context/BENCHMARK_PROTOCOL.md | 5+ | `references/run_state_schema.md` (2x), `references/exploration_patterns.md`, `references/defensive_patterns.md`, `references/what_just_happened.md` |
| ai_context/VERSION_HISTORY.md | 8+ | `references/iteration.md`, `references/functional_tests.md`, `references/orchestrator_protocol.md`, `bin/run_state_lib.py`, `references/run_state_schema.md`, `agents/calibration_orchestrator.md`, `references/role_map_queries.md` |
| ai_context/TOOLKIT_TEST_PROTOCOL.md | 5+ | `agents/calibration_orchestrator.md`, `references/run_state_schema.md`, `bin/run_state_lib.py`, `bin/visualize_calibration.py`, `bin/run_playbook.py:_finalize_iteration` (the runner one is fine) |

Verified: every `references/<name>.md`, `agents/<name>.md`, `phase_prompts/<name>.md`, and `bin/run_state_lib.py` mention in this set has moved to `skills/quality-playbook/...`. `bin/visualize_calibration.py`, `bin/citation_verifier.py` (wait — citation_verifier moved), `bin/install_skill.py`, `bin/run_playbook.py` remain at `bin/`.

Spot-check: `bin/citation_verifier.py` — referenced from `ai_context/IMPROVEMENT_LOOP.md:73`. The file `bin/citation_verifier.py` does NOT exist (moved to `skills/quality-playbook/scripts/citation_verifier.py`). Same defect class as bin/run_state_lib.py.

**Priority assessment:** these bare prose references are NOT markdown links — they don't render as broken hyperlinks — but they are the **primary navigational hints** maintainer AIs follow when working through these orientation docs. The orientation-doc release gate is the Toolkit Test Protocol (per `[[feedback_orientation_docs_release_gate]]`), so this should land in a docs-only follow-up commit; it isn't strictly blocking 208 itself (208's deliverable scope was "Repository structure section rewritten" — surgically narrow).

### 4c. AUDIT-table extension verification (separate from defensive sweep)

Verified `bin/build_channel_package.py::stamp_channel_manifest_versions()` (lines 453-559) stamps all four declared sites:

- `pyproject.toml` — raises if regex misses (mandatory)
- `package.json` — raises if regex misses (mandatory)
- `.claude-plugin/marketplace.json` — **silent skip** if regex misses (intentional: marketplace.json may legitimately omit a version field under strict-mode resolution where plugin.json carries it)
- `.claude-plugin/plugin.json` — raises if regex misses (mandatory)

Current `.claude-plugin/marketplace.json` has NO `version` field — it carries only `name`, `description`, `owner`, and `plugins[]`. So the marketplace.json branch hits the silent-skip path on every build. That's correct per the Anthropic marketplace schema (the inner plugin in `plugins[]` gets its metadata from plugin.json). **The build agent's note that 4 sites are stamped is misleading — only 3 are actually stamped on the current shape (the marketplace.json branch is dormant).** This is a documentation/messaging gap in the commit message, not a code defect. The silent-skip pass-through means a future marketplace.json shape that DOES carry an inline `"version"` field would auto-pick-up stamping without code changes. Good defensive shape.

Verified `test_plugin_layout_208::test_plugin_json_version_matches_pyproject` is the AUDIT invariant — it reads both files, regexes the pyproject.toml version, and asserts `plugin.json::version == pyproject.toml::version`. Currently both are `1.5.8`. Idempotent stamp run on the current tree returns `[]` (no changes needed). The test will catch the (likely) common drift mode where someone bumps pyproject.toml but forgets plugin.json.

## 5. Per-finding narrative

**FINDING C-1 (CONCERN, not FIX-REQUIRED-for-208):** README.md has 10 broken inline markdown links/raw URLs pointing to the old root-level `references/`, `agents/`, and `bin/run_state_lib.py` paths after 208's move. These will display as broken hyperlinks on the v1.5.8 GitHub render. Sites enumerated in § 4a above.

*Why CONCERN not FIX-REQUIRED:* the instruction's deliverables list named "README.md — Repository structure section rewritten; install-recipe cp blocks updated" as the scope. The install-recipe cp blocks ARE correctly updated. The inline narrative markdown links elsewhere in the README were not enumerated — this is the **defensive-sweep finding** the v207 defensive-sweep Council charter explicitly asks Panelist C to surface beyond the instruction's enumerated sites. Per the v207 charter the orchestrator should land these in a follow-up commit. Two of these (lines 51 and 186) are HIGH priority because they're in the first-page user-facing recipe — a brand-new v1.5.8 adopter clicking the link will hit a 404 on the first useful step. The raw URL on line 186 is the worst case (it'll be a hard 404 once `main` moves past the v1.5.7 tag).

**FINDING C-2 (CONCERN):** AGENTS.md and 5 of the `ai_context/*.md` orientation docs (IMPROVEMENT_LOOP, CALIBRATION_PROTOCOL, BENCHMARK_PROTOCOL, VERSION_HISTORY, TOOLKIT_TEST_PROTOCOL) carry ~40+ bare path mentions like `\`references/run_state_schema.md\`` or `\`bin/run_state_lib.py\`` that no longer resolve. Not markdown links so not visibly broken on GitHub, but they're the primary navigational hints maintainer AIs follow. Per `[[feedback_orientation_docs_release_gate]]` the Toolkit Test Protocol is the gate for orientation docs — this would belong in a docs-only follow-up driven by that protocol, not in 208 itself, since 208's scope was code+structure not orientation prose. Sites enumerated in § 4b.

**FINDING C-3 (NIT, not blocking):** the 208 commit message states `stamp_channel_manifest_versions()` "now stamps 4 sites (was 2)". In practice only 3 of the 4 sites currently receive a stamp because marketplace.json has no top-level `version` field. The code is correct (it gracefully silent-skips marketplace.json); the commit message's "4 sites" framing is slightly aspirational.

## 6. Optional NITs

- The test file's class docstring (line 26) reads "Layout-invariant assertions for the plugin-native restructure." — clear. The module docstring (lines 1-16) is thorough. No NIT here.
- `test_plugin_json_version_matches_pyproject` reads pyproject.toml with a regex; would be slightly stronger as a `tomllib.loads(...)['project']['version']` parse on Python 3.11+. Not blocking — the current regex is simple and matches the `_PYPROJECT_VERSION_RE` shape used by `build_channel_package.py` itself, so they drift in lockstep.
- The mutation snapshot/restore feedback memo (`[[feedback_mutation_bite_pycache]]`) cites a 20-min hang risk from walking `repos/` for `__pycache__`. I scoped the pycache purge to `bin/` only and it completed in <1s. Worth noting for any future panelist re-running the mutation.
- Orchestrator's report (worker step 5) said `cp` was used for the snapshot during the build; this works for the binary-equal restore but loses metadata. Mine used `shutil.copy2` for both directions and the working tree is byte-clean afterward. No change needed; just a heads-up.

## 7. Verdict scope reasoning

The two CONCERN findings are docs-prose-only and do not block the plugin marketplace mechanism, the bundle install, the build channels, or any test. The marketplace.json + plugin.json files are correct; the version-stamping function works on the 3 mandatory sites + silently-skips the 4th by design; the 15 layout-invariant tests pass; the mutation bite is reproducible; the bundle internal layout stays flat. Per the v207-codified defensive-sweep Council charter, surfacing the broken README links + bare prose path drift is the load-bearing deliverable for Panelist C — surfaced. Whether the orchestrator lands the README fix as a follow-up commit alongside 208, or defers it to a docs-only commit driven by the Toolkit Test Protocol, is the orchestrator's call.

I'd lean toward landing the README HIGH-priority fixes (lines 51, 186 link + 186 raw URL) before the v1.5.8 tag because they're in the first-page user instruction. Everything else can wait for the TOOLKIT_TEST_PROTOCOL-gated orientation-doc sweep.

## Final block

```
VERDICT: CONCERN
```

Reason: defensive sweep surfaced 10 broken inline markdown links in README.md (3 HIGH priority — first-page recipes) and ~40+ bare-prose stale path mentions across AGENTS.md + 5 `ai_context/` orientation docs. The 208 charter itself (plugin-native restructure, marketplace manifests, layout-invariant tests, AUDIT-table extension, mutation verification) is correctly delivered and tests pass. Orchestrator should land the README HIGH-priority link fixes in a follow-up commit on this branch before v1.5.8 tag; the orientation-doc bare-prose drift can be deferred to a Toolkit-Test-Protocol-driven sweep per `[[feedback_orientation_docs_release_gate]]`.
