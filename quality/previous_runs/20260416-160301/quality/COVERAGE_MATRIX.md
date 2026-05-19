# Requirements Coverage Matrix

<!-- Quality Playbook v1.4.1 — generated 2026-04-16 -->

One row per requirement. Maps each REQ-NNN to the contracts that ground it and the test functions that verify it.

| REQ-ID | Summary | Grounding Contracts (CONTRACTS.md) | Test Function(s) | Status |
|--------|---------|-------------------------------------|------------------|--------|
| REQ-001 | JSON key validation must not match string values | C-25, C-27, C-31 | `test_json_has_key_no_false_positive_from_string_value`, `test_json_key_count_no_inflation_from_string_values` | covered |
| REQ-002 | Repo path array reconstruction must preserve spaces | C-41, C-42 | `test_repo_path_with_spaces_survives_array_reconstruction`, `test_array_expansion_space_corruption` | covered |
| REQ-003 | Phase 2 entry gate must enforce all Phase 1 checks | C-3, C-4 | `test_phase2_entry_gate_check_count`, `test_phase1_gate_check_8_not_in_phase2_gate`, `test_phase1_gate_check_10_not_in_phase2_gate`, `test_phase1_gate_check_12_not_in_phase2_gate` | covered |
| REQ-004 | Gate must enforce regression test file when bugs exist | C-9 | `test_gate_requires_regression_test_file_when_bugs_exist`, `test_gate_regression_test_patch_check_present` | covered |
| REQ-005 | Phase 0b must activate when previous_runs/ is empty | C-12, C-13, C-14 | `test_phase0b_activation_condition_explicit`, `test_phase0_empty_previous_runs_gap` | covered |
| REQ-006 | All version references in SKILL.md must match frontmatter | C-5 | `test_skillmd_version_references_consistent`, `test_skillmd_frontmatter_version_matches_json_example` | covered |
| REQ-007 | json_str_val must distinguish absent keys from non-string values | C-28, C-29 | `test_json_str_val_non_string_value_handling`, `test_json_str_val_absent_key` | covered |
| REQ-008 | Mandatory First Action must be scoped to interactive mode | C-6 | `test_mandatory_first_action_has_interactive_scope_qualifier` | covered |
| REQ-009 | Generated artifact version stamps must match frontmatter | C-5, C-11 | `test_version_stamp_format_in_skillmd`, `test_tdd_results_json_example_version_field` | covered |
| REQ-010 | Phase 1 exploration must produce substantive findings | C-21, C-22, C-23, C-24 | `test_phase1_gate_12_checks_defined`, `test_exploration_md_minimum_content_requirements`, `test_candidate_bugs_ensemble_balance` | covered |
| REQ-011 | Requirements pipeline must produce traceable requirements | C-15, C-16, C-17, C-18, C-19 | `test_requirements_pipeline_five_phases`, `test_requirement_mandatory_fields`, `test_coverage_matrix_one_row_per_requirement` | covered |
| REQ-012 | Gate must handle empty VERSION gracefully | C-43 | `test_gate_all_mode_empty_version_behavior`, `test_version_detection_fallback` | covered |
| REQ-013 | Mechanical verification must not be created for non-dispatch contracts | C-10, C-52 | `test_mechanical_verification_not_applicable_documented`, `test_no_mechanical_directory_for_non_dispatch` | covered |
| REQ-014 | Gate functional test detection must be consistent | C-48, C-49 | `test_functional_test_detection_method_consistency` | covered |

## Coverage summary

| Metric | Value |
|--------|-------|
| Total requirements | 14 |
| Requirements with ≥1 test | 14 |
| Requirements with ≥2 tests | 12 |
| Architectural-guidance requirements | 0 |
| Uncovered requirements | 0 |

## Contract coverage

| Contract category | Contracts | Mapped to requirements |
|-------------------|-----------|----------------------|
| INVARIANT | 9 | REQ-001, REQ-002, REQ-003, REQ-005, REQ-009, REQ-010, REQ-011, REQ-013 |
| METHOD | 18 | REQ-001, REQ-007, REQ-010, REQ-011, REQ-012, REQ-014 |
| CONFIG | 5 | REQ-005, REQ-006, REQ-008, REQ-012, REQ-013 |
| ERROR | 7 | REQ-001, REQ-002, REQ-004, REQ-007, REQ-012, REQ-014 |
| LIFECYCLE | 3 | REQ-009, REQ-011, REQ-013 |
| COMPAT | 2 | REQ-006, REQ-009 |
| ORDER | 3 | REQ-010, REQ-011 |
| NULL | 3 | REQ-001, REQ-007 |

## Bidirectional traceability check

| Use Case | Linked Requirements | At least one specific req? |
|----------|--------------------|-----------------------------|
| UC-01 (Developer runs quality audit) | REQ-001, REQ-002, REQ-003, REQ-005, REQ-006, REQ-008, REQ-009, REQ-010, REQ-011 | Yes — REQ-001, REQ-002 are specific |
| UC-02 (Automated benchmark) | REQ-006, REQ-007, REQ-008, REQ-009 | Yes — REQ-006, REQ-007 are specific |
| UC-03 (Developer verifies conformance) | REQ-001, REQ-002, REQ-004, REQ-005, REQ-006, REQ-009 | Yes — all are specific |
| UC-04 (Maintainer updates version) | REQ-006 | Yes — REQ-006 is specific |
| UC-05 (Developer runs iteration) | REQ-003, REQ-007, REQ-009, REQ-011 | Yes — REQ-003 is specific |
