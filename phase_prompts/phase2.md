{skill_fallback_guide}

You are a quality engineer continuing a phase-by-phase quality playbook run. Phase 1 (exploration) is already complete.

Read these files to get context:
1. quality/EXPLORATION.md - your Phase 1 findings (requirements, risks, architecture)
2. quality/PROGRESS.md - run metadata and phase status
3. SKILL.md - read the Phase 2 pointer section (v1.5.7+ Phase 7 trim: the full Phase 2 body now lives at `references/phase2_generation_guide.md`). Resolve SKILL.md and reference files via the documented fallback list above; do NOT assume any single install layout (`.github/skills/`, `.claude/skills/quality-playbook/`, `.cursor/skills/quality-playbook/`, `.continue/skills/quality-playbook/`, or root).
4. references/phase2_generation_guide.md - the complete Phase 2 instructions: instrumentation, required-references list, source-modification guardrail, entry gate, requirements pipeline, generated-artifact templates, completion gate, and end-of-phase message. **READ THIS BEFORE GENERATING ANY ARTIFACTS** — it's the canonical Phase 2 protocol after the v1.5.7 SKILL.md trim.

**Role-map query cookbook (v1.5.7).** When querying `quality/exploration_role_map.json` to enumerate files by role, consult `references/role_map_queries.md` for canonical jq patterns. Do NOT construct jq paths from memory — the role map's list-of-records shape is non-obvious and several intuitively-named paths (e.g., `.roles.source[]`) do not exist. Read the cookbook, copy a canonical query, then adapt extension filters as needed.

**Field preservation rule (v1.5.2, Lever 2).** When transcribing REQ hypotheses from EXPLORATION.md into `quality/REQUIREMENTS.md` and `quality/requirements_manifest.json`, every `- Pattern: <value>` field present on the source hypothesis MUST appear on the corresponding REQ in both output files. Pattern values are `whitelist | parity | compensation`. Phase 1's Cartesian UC rule (confirmation checklist item 6) requires Pattern tagging for every REQ where both UC gates match; Phase 2 must not silently drop these tags. If a hypothesis lacks Pattern but you believe it should have one (per-site UCs emitted with `UC-N.a`/`UC-N.b` suffixes, multi-file `References` suggesting a parallel structure), add Pattern during Phase 2 — do not omit the field. The Phase 5 cardinality gate cannot enforce coverage on a REQ it doesn't know is pattern-tagged; silent omission is a documented v1.4.5-regression vector.

Execute Phase 2: Generate all quality artifacts. Use the exploration findings in EXPLORATION.md as your source - do not re-explore the codebase from scratch. Generate:
- quality/QUALITY.md (quality constitution)
- quality/CONTRACTS.md (behavioral contracts)
- quality/REQUIREMENTS.md (with REQ-NNN and UC-NN identifiers from EXPLORATION.md)
- quality/COVERAGE_MATRIX.md
- Functional tests (quality/test_functional.*)
- quality/RUN_CODE_REVIEW.md (code review protocol)
- quality/RUN_INTEGRATION_TESTS.md (integration test protocol)
- quality/RUN_SPEC_AUDIT.md (spec audit protocol)
- quality/RUN_TDD_TESTS.md (TDD verification protocol)
- quality/COMPLETENESS_REPORT.md (baseline, without verdict)
- If dispatch/enumeration contracts exist: quality/mechanical/ with verify.sh and extraction artifacts. Run verify.sh immediately and save receipts.

**Canonical artifact-location REQs (v1.5.7 fix F-4c).** REQUIREMENTS.md MUST include explicit location requirements for the canonical artifact paths so the gate has concrete REQs to enforce against. Add these REQs verbatim (renumber to slot into your existing REQ-NNN sequence; do not omit any):

- `REQ-NNN: Per-bug writeups are placed at quality/writeups/BUG-<id>.md.`
- `REQ-NNN: Fix patches are placed at quality/patches/BUG-<id>-fix.patch.`
- `REQ-NNN: Regression-test patches are placed at quality/patches/BUG-<id>-regression-test.patch.`
- `REQ-NNN: Code review output is placed at quality/code_reviews/.`
- `REQ-NNN: Spec audit outputs (auditor reports + triage) are placed at quality/spec_audits/.`
- `REQ-NNN: Sidecar JSON results (tdd-results.json, integration-results.json, recheck-results.json) are placed at quality/results/.`
- `REQ-NNN: Mechanical-verification artifacts (verify.sh + *_cases.txt) are placed at quality/mechanical/.`
- `REQ-NNN: quality/workspace/<name>/ is forbidden — top-level quality/<name>/ is the only canonical layout. Phase 6 gate check_no_workspace_dir fails any run with a quality/workspace/ tree present (populated OR empty — empty workspace/ trains future-iteration agents on the wrong layout and is rejected too).`

**v1.5.7 fix Q2 — schemas.md §3.10 v1.5.3 field mandates.** Every BUG record written to `quality/bugs_manifest.json` MUST populate `divergence_type` per schemas.md §3.8 (`code-spec` | `internal-prose` | `cross-source`). Every FORMAL_DOC record in `quality/formal_docs_manifest.json` MUST populate `role` per schemas.md §3.6 (`external-spec` for records from `reference_docs/cite/`; `skill-self-spec` / `skill-reference` only for Skill/Hybrid targets' own documents). The Phase 6 gate (`check_v1_5_3_formal_doc_role_validation`, `check_v1_5_3_bug_divergence_type`) keeps WARN for back-compat with pre-v1.5.7 manifests that lack these fields, but every v1.5.7 run must produce v1.5.3-shaped output. `bin/reference_docs_ingest.py` emits `role: "external-spec"` automatically; BUG records the agent writes must include `divergence_type` explicitly.

These REQs convert artifact-location compliance from prose-only guidance into testable requirements. The Phase 6 gate's `check_no_workspace_dir` enforces the last one mechanically; the others give human reviewers concrete REQs to grep for in compliance audits.

Update PROGRESS.md: mark Phase 2 complete (use the checkbox format `- [x] Phase 2 - Generate` — do NOT switch to a table), update artifact inventory.

IMPORTANT: Do NOT proceed to Phase 3 (code review). Your job is artifact generation only. The next phase will execute the review protocols you generated.
