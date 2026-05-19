# Recheck Results

> Recheck of quality/BUGS.md from 2026-04-18
> Recheck run: 2026-04-19
> Skill version: 1.4.5

## Summary

| Status          | Count |
|-----------------|-------|
| Fixed           | 27    |
| Partially fixed | 0     |
| Still open      | 0     |
| Inconclusive    | 0     |
| **Total**       | **27**|

All 27 bugs from the 2026-04-18 self-audit are FIXED. Every bug's companion regression test in `quality/test_regression.py` passes without its `@unittest.expectedFailure` marker, and each fix's target file reflects the writeup's intended change.

## Per-Bug Results

| Bug     | Severity | Status | Evidence |
|---------|----------|--------|----------|
| BUG-001 | HIGH     | FIXED  | `skill_version` uses shared VERSION_PATTERN regex; regression test passes |
| BUG-002 | HIGH     | FIXED  | `SKILL_INSTALL_LOCATIONS` tuple has 4 entries; regression + closed-set tests pass; mechanical extractor agrees |
| BUG-003 | HIGH     | FIXED  | Phase 2 gate returns `ok=False` with `expected 120+` below threshold; `orchestrator_protocol.md` prose updated to 120 |
| BUG-004 | HIGH     | FIXED  | `archive_previous_run` stages to `.partial/`, `os.rename`s atomically, preserves `control_prompts/` |
| BUG-005 | MEDIUM   | FIXED  | `PROTECTED_EXACT = ("AGENTS.md",)`; `_is_protected` checks path equality + prefix |
| BUG-006 | MEDIUM   | FIXED  | Phase 3 gate checks all 9 required Phase 2 artifacts |
| BUG-007 | MEDIUM   | FIXED  | `docs_present` requires is_file + non-hidden + non-zero size |
| BUG-008 | MEDIUM   | FIXED  | `print_suggested_next_command(args, failures_occurred=...)`; inspect/re-run hint on failure |
| BUG-009 | MEDIUM   | FIXED  | `_pkill_fallback` patterns include `gh copilot -p` |
| BUG-010 | LOW      | FIXED  | `check_run_metadata()` validates `run-*.json` filename + JSON + required fields; wired into `check_repo` |
| BUG-011 | LOW      | FIXED  | `_check_exploration_sections` validates 5 required Phase 1 section headings |
| BUG-012 | LOW      | FIXED  | Zero-bug sentinel requires anchored `## No confirmed bugs` heading |
| BUG-013 | MEDIUM   | FIXED  | `detect_skill_version` uses anchored VERSION_PATTERN regex |
| BUG-014 | MEDIUM   | FIXED  | `validate_iso_date` accepts both date-only and full ISO 8601 datetime forms |
| BUG-015 | MEDIUM   | FIXED  | `_parse_porcelain_path` strips surrounding double quotes and unescapes `\"` |
| BUG-016 | MEDIUM   | FIXED  | Phase 5 gate enforces spec_audits/ contents + Phase 4 `[x]` checkbox |
| BUG-017 | MEDIUM   | FIXED  | Both agent prompts list `SKILL.md` as install-discovery entry 1 |
| BUG-018 | MEDIUM   | FIXED  | General agent Mode 1 now starts a fresh context instead of running Phase 1 in-place |
| BUG-019 | MEDIUM   | FIXED  | pytest shim parses `--collect-only`; node IDs error cleanly (exit 2) instead of ImportError |
| BUG-020 | HIGH     | FIXED  | Missing docs WARN + continue with code-only analysis |
| BUG-021 | MEDIUM   | FIXED  | `SKILL_FALLBACK_GUIDE` constant enumerates all 4 install paths in runner prompts |
| BUG-022 | HIGH     | FIXED  | `run_one_phase` / `run_one_singlepass` capture + propagate `run_prompt` exit code |
| BUG-023 | MEDIUM   | FIXED  | `detect_project_language` excluded set includes `repos` |
| BUG-024 | MEDIUM   | FIXED  | File-existence gate accepts `functional_test.*` alongside the other 4 patterns |
| BUG-025 | MEDIUM   | FIXED  | Extension checker walks full documented naming matrix |
| BUG-026 | MEDIUM   | FIXED  | `FUNCTIONAL_TEST_PATTERNS` no longer includes `test_functional_test.*` |
| BUG-027 | LOW      | FIXED  | `REGRESSION_TEST_PATTERNS` narrowed to canonical `test_regression.*` only |

## Still Open — Details

None. All 27 bugs are fixed.

## Verification Notes

- Every regression test for every bug in this inventory passes with its xfail marker removed (34 tests across 27 bugs, since BUG-002, BUG-016, BUG-019, BUG-020, BUG-021, BUG-022 each have multiple companion tests).
- `.github/skills/quality_gate/quality_gate.py .` returns **GATE PASSED** (0 FAIL, 0 WARN).
- `quality/mechanical/verify.sh` exits 0 (all 5 extractors agree with the documented closed-set claims).
- `SKILL.md` version deliberately left at 1.4.5 pending review of the fix batch before a version bump.
