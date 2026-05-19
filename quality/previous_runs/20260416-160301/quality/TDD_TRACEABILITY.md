# TDD Traceability: quality-playbook

<!-- Quality Playbook v1.4.1 — Phase 5 Reconciliation — 2026-04-16 -->

## Overview

This document maps each confirmed bug to its TDD evidence: the requirement it violates,
the regression test that proves it's real (red phase), and the fix verification (green phase).

---

## Bug-to-Evidence Map

| Bug ID | Requirement | Regression Test | Red Phase Log | Green Phase Log | Verdict |
|--------|-------------|-----------------|---------------|-----------------|---------|
| BUG-H1 | REQ-001 — json_has_key must check key presence, not string values | test_BUG_H1_json_has_key_false_positive | BUG-H1.red.log | BUG-H1.green.log | TDD verified |
| BUG-H2 | REQ-002 — Array expansion must preserve paths with spaces | test_BUG_H2_array_expansion_corrupts_spaces | BUG-H2.red.log | BUG-H2.green.log | confirmed open |
| BUG-M3 | REQ-003 — Phase 2 gate must enforce all Phase 1 checks | test_BUG_M3_phase2_gate_missing_checks | BUG-M3.red.log | BUG-M3.green.log | TDD verified |
| BUG-M4 | REQ-004 — Gate must fail when bugs exist without test_regression.* | test_BUG_M4_gate_missing_regression_file_check | BUG-M4.red.log | BUG-M4.green.log | TDD verified |
| BUG-M5 | REQ-005 — Phase 0b must activate when previous_runs/ exists but empty | test_BUG_M5_phase0b_skips_on_empty_previous_runs | BUG-M5.red.log | BUG-M5.green.log | TDD verified |
| BUG-L6 | REQ-007 — json_str_val must distinguish absent from non-string value | test_BUG_L6_json_str_val_non_string_empty | BUG-L6.red.log | BUG-L6.green.log | TDD verified |
| BUG-L7 | REQ-006 — All SKILL.md version strings must match frontmatter | test_BUG_L7_version_string_consistency | BUG-L7.red.log | (none — no fix patch) | confirmed open |
| BUG-M8 | REQ-002, REQ-014 — Artifact counting must work under nullglob | test_BUG_M8_nullglob_ls_counting | BUG-M8.red.log | BUG-M8.green.log | TDD verified |
| BUG-L9 | REQ-011 — Auditor reports must use consistent naming format | test_BUG_L9_auditor_naming_inconsistency | BUG-L9.red.log | (none — no fix patch) | confirmed open |
| BUG-L10 | REQ-009 — Generated artifacts must use consistent schema version | test_BUG_L10_recheck_schema_version_inconsistency | BUG-L10.red.log | (none — no fix patch) | confirmed open |
| BUG-L11 | REQ-009 — tdd-results.json must use consistent field formats | test_BUG_L11_tdd_results_two_incompatible_templates | BUG-L11.red.log | (none — no fix patch) | confirmed open |

---

## TDD Summary

- **Total confirmed bugs:** 11
- **TDD verified (red fails + green passes):** 6 (BUG-H1, BUG-M3, BUG-M4, BUG-M5, BUG-L6, BUG-M8)
- **Confirmed open (no fix patch available):** 4 (BUG-L7, BUG-L9, BUG-L10, BUG-L11)
- **Confirmed open (environment-dependent):** 1 (BUG-H2)
- **Red failed (test did not fail on unpatched code):** 0
- **Green failed (test did not pass after fix):** 0

---

## Evidence File Locations

### Red Phase Logs (all 11 required)

| Bug ID | Log File | Status Tag |
|--------|----------|------------|
| BUG-H1 | quality/results/BUG-H1.red.log | RED |
| BUG-H2 | quality/results/BUG-H2.red.log | RED |
| BUG-M3 | quality/results/BUG-M3.red.log | RED |
| BUG-M4 | quality/results/BUG-M4.red.log | RED |
| BUG-M5 | quality/results/BUG-M5.red.log | RED |
| BUG-L6 | quality/results/BUG-L6.red.log | RED |
| BUG-L7 | quality/results/BUG-L7.red.log | RED |
| BUG-M8 | quality/results/BUG-M8.red.log | RED |
| BUG-L9 | quality/results/BUG-L9.red.log | RED |
| BUG-L10 | quality/results/BUG-L10.red.log | RED |
| BUG-L11 | quality/results/BUG-L11.red.log | RED |

### Green Phase Logs (7 bugs have fix patches)

| Bug ID | Log File | Status Tag | Fix Patch |
|--------|----------|------------|-----------|
| BUG-H1 | quality/results/BUG-H1.green.log | GREEN | BUG-H1-fix.patch |
| BUG-H2 | quality/results/BUG-H2.green.log | GREEN | BUG-H2-fix.patch |
| BUG-M3 | quality/results/BUG-M3.green.log | GREEN | BUG-M3-fix.patch |
| BUG-M4 | quality/results/BUG-M4.green.log | GREEN | BUG-M4-fix.patch |
| BUG-M5 | quality/results/BUG-M5.green.log | GREEN | BUG-M5-fix.patch |
| BUG-L6 | quality/results/BUG-L6.green.log | GREEN | BUG-L6-fix.patch |
| BUG-M8 | quality/results/BUG-M8.green.log | GREEN | BUG-M8-fix.patch |

---

## Requirement Coverage

| Requirement | Bugs Mapped | Coverage |
|-------------|-------------|---------|
| REQ-001 | BUG-H1 | Full |
| REQ-002 | BUG-H2, BUG-M8 | Full |
| REQ-003 | BUG-M3 | Full |
| REQ-004 | BUG-M4 | Full |
| REQ-005 | BUG-M5 | Full |
| REQ-006 | BUG-L7 | Partial (latent risk only) |
| REQ-007 | BUG-L6 | Full |
| REQ-009 | BUG-L10, BUG-L11 | Full |
| REQ-011 | BUG-L9 | Full |
| REQ-014 | BUG-M8 | Full |

---

## Attestation

All 11 confirmed bugs have:
- [x] A regression test function in quality/test_regression.sh
- [x] A red phase log file (quality/results/BUG-NNN.red.log)
- [x] A bug writeup (quality/writeups/BUG-NNN.md) with inline diff block
- [x] A TDD verdict in quality/results/tdd-results.json

7 of 11 bugs additionally have:
- [x] A fix patch (quality/patches/BUG-NNN-fix.patch)
- [x] A green phase log file (quality/results/BUG-NNN.green.log)
