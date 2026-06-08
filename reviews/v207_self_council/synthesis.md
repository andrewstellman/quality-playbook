# Synthesis — 207 Worker self-Council (3-panelist)

**SHIP recommendation: YES** — after applying C's FIX-REQUIRED defensive-sweep findings pre-push.

## Panel summary

| Panelist | Charter | Initial verdict | After remediation |
|----------|---------|----------------|-------------------|
| A | Content correctness against canonical sources | **SHIP** | (unchanged) |
| B | Terminology consistency | **SHIP** | (unchanged) |
| C | Tests + regression-safety + defensive sweep | **FIX-REQUIRED** | **SHIP** (4 fixes applied: 3 content + 2 new tests) |

## Panelist A verdict — content correctness clean

All 6 in-scope fixes from instruction 207 match their canonical sources empirically:

| # | Fix | Canonical source | Match |
|---|-----|------------------|-------|
| 1 | `Python 3.10+` | `README.md:47`, `ai_context/TOOLKIT.md:49,54,221` | ✓ |
| 2 | `npx quality-playbook install --into <repo> --ai-tool <tool>` | `README.md:159` | ✓ |
| 3 | `quality-playbook install` entry point | `pyproject.toml:46-47` `[project.scripts]` (no `qpb` entry exists) | ✓ |
| 4 | `Phase 5 (Reconcile)` | `README.md:59,599` | ✓ |
| 5 | `Phase 6 (Verify)` | `README.md:59,599` | ✓ |
| 6 | 5 directories: `agents/`, `ai_context/`, `bin/`, `phase_prompts/`, `references/` | actual `ls quality_playbook_cli/_bundle/` | ✓ |

Empirical dry-run shows all six fixes present in rendered SKILL.md and PR_BODY.md. All 8 `TrimTemplateContentTests` pass.

### Panelist A NITs (out-of-scope, not blocking)
- A-NIT1: SKILL.md line 19 still says "seven phase-prompt directories" (pre-existing, same defect class as fix #6)
- A-NIT2: `quality_gate.py` referenced as top-level (closer to correct than pre-207, but still loose)
- A-NIT3: SKILL.md singles out `bin/citation_verifier.py` from a `bin/` directory containing 17 files

## Panelist B verdict — terminology consistency clean

- Extended residual-error grep (6 pre-207 patterns) returns ZERO matches in `/tmp/qpb-207-empirical/`
- Phase names in template Phase 1-6 align with README line 599's canonical verb-form set
- Trigger phrases preserved verbatim (SKILL.md line 3 source vs template line 3 — identical)
- PR_BODY.md says "five support directories" with correct enumeration; Checklist contains neither "five" nor "seven"
- All 37 tests pass

### Panelist B NITs (out-of-scope, not blocking)
- B-NIT1: SKILL.md line 19 still says "seven phase-prompt directories" (echoes A-NIT1 — same class)
- B-NIT2: minor Phase-name surface variance README vs SKILL.md

## Panelist C verdict — FIX-REQUIRED → SHIP after defensive-sweep remediation

### Test-coverage audit (8/8, mutation-resistant)

- All 8 `TrimTemplateContentTests` present at lines 687-780; tests 1-7 pair positive+negative assertions; test 8 positive-only (sub-NIT)
- Mutation independently re-performed: snapshot to `/tmp/qpb_207_panelC_snapshot.py`, revert Python version, observe FAIL, restore via shutil.copy2, pycache purge, 8/8 PASS, `git diff` clean
- Regression: full `test_submit_awesome_copilot.py` (37 passed) + `test_release_affirmation_sweep_206.py` (6 passed) all green

### Defensive-sweep findings (the FIX-REQUIRED)

C identified the same defect class extending beyond the 8 specific fixes in the instruction. **Both A and B noted the SKILL.md line 19 "seven phase-prompt directories" miss as a NIT, but C correctly identified it as in-scope** because the whole point of the instruction is "fix trim-template factual errors before shipping to awesome-copilot users." Leaving an identical defect in the artifact-that-adopters-read (SKILL.md) while fixing it in the artifact-that-only-maintainers-read (PR_BODY) is incoherent.

C surfaced 4 issues:

| # | Site | Issue | Fix applied? |
|---|------|-------|--------------|
| 1 | SKILL.md line 197 (Installation prose) | "seven phase-prompt directories, the citation verifier, the Council runner, ..." — same staleness as PR_BODY error #6 | ✅ Applied: rewrote to mirror PR_BODY's "five support directories" form |
| 2 | SKILL.md line 217 (install output list) | "bin/citation_verifier.py" — C claimed install_skill.py copies all of `bin/` | ⏸ DEFERRED: README install scripts (lines 260, 306, 348) copy `bin/citation_verifier.py` SPECIFICALLY, matching the template's current claim. Disputable without further verification of `install_skill.py` runtime behavior; not fixed to avoid introducing a fresh error in the opposite direction. |
| 3 | SKILL.md line 244 (workflow duration) | "30-90 minutes" — README:410 canonical is "15-90 minutes" | ✅ Applied: → "15-90 minutes depending on project size" |
| 4 | Module docstring lines 11-13 | Same "seven support directories" miscount | ✅ Applied: rewrote to "five support directories (...) plus SKILL.md and quality_gate.py — a ~64-file bundle" |

### New regression tests (2 added)

- `test_skill_md_installation_prose_lists_actual_bundle_dirs` — asserts "five support directories" in SKILL.md AND NOT-in "seven phase-prompt directories"/"seven support directories"
- `test_skill_md_workflow_duration_is_canonical_15_90_minutes` — asserts "15-90 minutes" in SKILL.md AND NOT-in "30-90 minutes"

Both pair positive + negative assertions per the defect-class regression-pinning pattern.

10/10 `TrimTemplateContentTests` pass (8 from initial + 2 from defensive sweep). 39-test publish suite + 6-test AUDIT sweep + 41-test submit suite all pass.

### Panelist C NITs (deferred)
- C-NIT1: test 8 (AI-tool list) is positive-only — could add NotIn assertion
- C-NIT2: deferred SKILL.md line 217 citation_verifier finding — needs deeper investigation of install_skill.py runtime; out of scope for content-fix instruction
- C-NIT3: future enhancement — add a sweep test that grep's residual error patterns across the regenerated artifacts (like B's empirical grep, but in CI form)

## Key panel agreements

1. **All 6 in-scope fixes from instruction match canonical sources** (A confirmed against README + pyproject.toml + bundle listing)
2. **Zero residual error patterns** in regenerated artifacts post-fix (B's extended grep)
3. **Defensive sweep correctly elevated** by C — the SKILL.md line 197 miss was the same defect class as PR_BODY error #6, and SKILL.md is the artifact adopters actually read
4. **3 of C's 4 findings fixed pre-push** (1, 3, 4); 1 deferred with documented rationale (#2)
5. **2 new regression tests added** following the defect-class regression-pinning pattern
6. **Mutation-bite verified twice** (orchestrator + Panelist C independent)
7. **39+6+41 tests pass** across publish + AUDIT + submit suites

## Methodology echo

C's defensive sweep is the right shape for a content-fix instruction: ask whether the same defect class extends beyond the specific sites named in the spec. The instruction explicitly enumerated 8 fixes; C found 4 additional sites of the same class. **Fixing only the called-out sites while leaving identical defects in the same template ships a half-fixed artifact.** The fix-required call correctly forces the worker back through the template with the same lens — "what else is hardcoded that might be stale?" — rather than mechanically applying just the listed diffs.

This pattern echoes the 199 → 199-followup-1 mock-reality divergence (test mocks + production agreed with each other while disagreeing with reality). Here it's a different shape: an instruction's enumerated fix list + the worker's mechanical application agreed with each other while leaving identical defects elsewhere in the same template. Panel C's defensive sweep is the structural fix for this class of incomplete remediation.

## Recommendation

**SHIP** — after applying C's defensive-sweep fixes pre-push.

Push to origin/1.5.8 requires **operator confirmation** per instruction's "Done definition": "No push to origin without operator approval."

After 207 lands on origin, Andrew re-runs `bin/submit_awesome_copilot.py --submit`. The regenerated SKILL.md + PR_BODY.md will have factually correct content across BOTH artifacts. The PR can land cleanly against `github/awesome-copilot:staged`.
