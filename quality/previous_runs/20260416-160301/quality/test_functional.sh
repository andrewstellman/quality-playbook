#!/usr/bin/env bash
# Functional Tests: quality-playbook
# Quality Playbook v1.4.1 — generated 2026-04-16
#
# Tests SKILL.md internal consistency, structural completeness,
# and quality_gate.sh behavioral contracts.
#
# Run: bash quality/test_functional.sh
# Requires: bash 3.2+, grep, awk, sed (all standard on macOS/Linux)

set -uo pipefail

SKILLMD="/Users/andrewstellman/tmp/QFB-bootstrap/SKILL.md"
GATE="/Users/andrewstellman/tmp/QFB-bootstrap/quality_gate.sh"
REFS_DIR="/Users/andrewstellman/tmp/QFB-bootstrap/references"

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

pass() { echo "[PASS] $1"; ((PASS_COUNT++)); }
fail() { echo "[FAIL] $1"; ((FAIL_COUNT++)); }
skip() { echo "[SKIP] $1"; ((SKIP_COUNT++)); }

assert_contains() {
    local file="$1" pattern="$2" msg="$3"
    if grep -qE "$pattern" "$file" 2>/dev/null; then
        pass "$msg"
    else
        fail "$msg — pattern '$pattern' not found in $file"
    fi
}

assert_not_contains() {
    local file="$1" pattern="$2" msg="$3"
    if ! grep -qE "$pattern" "$file" 2>/dev/null; then
        pass "$msg"
    else
        fail "$msg — unexpected pattern '$pattern' found in $file"
    fi
}

assert_file_exists() {
    local file="$1" msg="$2"
    if [ -f "$file" ]; then
        pass "$msg"
    else
        fail "$msg — file not found: $file"
    fi
}

assert_line_count_ge() {
    local file="$1" min="$2" msg="$3"
    local count
    count=$(wc -l < "$file" 2>/dev/null || echo 0)
    if [ "$count" -ge "$min" ]; then
        pass "$msg (${count} lines)"
    else
        fail "$msg — expected ≥${min} lines, got ${count}"
    fi
}

assert_count_ge() {
    local count="$1" min="$2" msg="$3"
    if [ "$count" -ge "$min" ]; then
        pass "$msg (found ${count})"
    else
        fail "$msg — expected ≥${min}, got ${count}"
    fi
}

assert_count_between() {
    local count="$1" min="$2" max="$3" msg="$4"
    if [ "$count" -ge "$min" ] && [ "$count" -le "$max" ]; then
        pass "$msg (found ${count})"
    else
        fail "$msg — expected between ${min} and ${max}, got ${count}"
    fi
}

echo "============================================================"
echo "Quality Playbook Functional Tests — quality-playbook v1.4.1"
echo "============================================================"
echo ""

# ============================================================
# GROUP 1: Spec Requirements Tests (SKILL.md structural integrity)
# ============================================================

echo "--- GROUP 1: Spec Requirements ---"
echo ""

# REQ-006: Version consistency — all version refs must match frontmatter
FRONTMATTER_VERSION=$(grep -m1 '^  version:' "$SKILLMD" 2>/dev/null | sed 's/.*version: *//' | tr -d '"' | tr -d ' ')

if [ -z "$FRONTMATTER_VERSION" ]; then
    fail "test_skillmd_frontmatter_version_present — could not extract version from frontmatter"
else
    pass "test_skillmd_frontmatter_version_present — version: $FRONTMATTER_VERSION"

    # All version refs in SKILL.md must match frontmatter
    assert_contains "$SKILLMD" "skill_version.*${FRONTMATTER_VERSION}" \
        "test_skillmd_version_references_consistent — JSON example skill_version matches frontmatter"

    # JSON examples must quote the version
    assert_contains "$SKILLMD" "\"${FRONTMATTER_VERSION}\"" \
        "test_skillmd_json_example_has_frontmatter_version — JSON examples use frontmatter version"
fi

# REQ-010: Phase 1 gate must define exactly 12 checks
# Count numbered list items in the Phase 1 completion gate section
PHASE1_GATE_ITEMS=$(awk '/Phase 1 completion gate.*mandatory/,/Do not begin Phase 2/' "$SKILLMD" 2>/dev/null | grep -c "^[0-9]\+\." || echo 0)
assert_count_ge "$PHASE1_GATE_ITEMS" 12 \
    "test_phase1_gate_12_checks_defined — Phase 1 completion gate defines ≥12 checks"

# REQ-003: Phase 2 entry gate — verify it references 6 items
# The Phase 2 entry gate is described in the Phase 2 section of SKILL.md
PHASE2_GATE_CHECK=$(grep -c "Phase 2 entry gate\|Phase 2.*entry gate\|entry gate.*Phase 2\|If the file does not exist.*120 lines" "$SKILLMD" 2>/dev/null || echo 0)
if [ "$PHASE2_GATE_CHECK" -gt 0 ]; then
    pass "test_phase2_entry_gate_exists — Phase 2 entry gate described in SKILL.md (${PHASE2_GATE_CHECK} references)"
else
    fail "test_phase2_entry_gate_exists — Phase 2 entry gate section not found in SKILL.md"
fi

# REQ-003: Phase 2 gate check count vs Phase 1 — BUG-M3
# Phase 1 has 12 numbered checks; Phase 2 is documented as the "backstop" with 6 checks
PHASE1_COUNT=${PHASE1_GATE_ITEMS:-0}
# Check that the spec acknowledges Phase 2 is a subset of Phase 1 checks
BACKSTOP_REF=$(grep -c "backstop\|6 check\|Phase 2.*backstop" "$SKILLMD" 2>/dev/null || echo 0)
if [ "$BACKSTOP_REF" -gt 0 ]; then
    pass "test_phase1_gate_check_gap_confirmed — Phase 2 is documented as backstop (${BACKSTOP_REF} references) — BUG-M3 acknowledged in spec"
else
    fail "test_phase1_gate_check_gap_confirmed — BUG-M3: Phase 2 gate gap vs Phase 1 (${PHASE1_COUNT} items) not documented in SKILL.md (REQ-003)"
fi

# REQ-008: Mandatory First Action — must exist
assert_contains "$SKILLMD" "MANDATORY FIRST ACTION" \
    "test_mandatory_first_action_present — MANDATORY FIRST ACTION instruction present"

# REQ-008: Autonomous mode handling
assert_contains "$SKILLMD" "[Aa]utonomous" \
    "test_autonomous_mode_documented — autonomous mode is documented in SKILL.md"

# REQ-008: BUG check — Mandatory First Action lacks interactive-only qualifier
# The "Mandatory First Action" section does not say "interactive mode only" explicitly
MANDATORY_LINE=$(grep -n "MANDATORY FIRST ACTION" "$SKILLMD" 2>/dev/null | head -1 | cut -d: -f1)
AUTONOMOUS_LINE=$(grep -n "Autonomous fallback\|autonomous fallback" "$SKILLMD" 2>/dev/null | head -1 | cut -d: -f1)
if [ -n "$MANDATORY_LINE" ] && [ -n "$AUTONOMOUS_LINE" ]; then
    LINE_DIFF=$((AUTONOMOUS_LINE - MANDATORY_LINE))
    if [ "$LINE_DIFF" -gt 50 ]; then
        fail "test_mandatory_first_action_has_interactive_scope_qualifier — BUG: MANDATORY FIRST ACTION (line ${MANDATORY_LINE}) and autonomous fallback (line ${AUTONOMOUS_LINE}) are ${LINE_DIFF} lines apart with no cross-reference (REQ-008)"
    else
        pass "test_mandatory_first_action_has_interactive_scope_qualifier — Mandatory First Action and autonomous fallback are within 50 lines"
    fi
else
    skip "test_mandatory_first_action_has_interactive_scope_qualifier — could not locate both instructions"
fi

# REQ-010: Exploration stage requirements — SKILL.md specifies minimum 8 findings
assert_contains "$SKILLMD" "at least 8 concrete" \
    "test_skillmd_specifies_minimum_8_open_exploration_findings"

# REQ-010: Pattern evaluation — SKILL.md requires all six patterns evaluated
# Exact text (line 856): "evaluates all six patterns from `exploration_patterns.md`"
if grep -q "evaluates all six patterns from" "$SKILLMD" 2>/dev/null; then
    pass "test_skillmd_requires_all_6_patterns_evaluated"
else
    fail "test_skillmd_requires_all_6_patterns_evaluated — text not found in SKILL.md"
fi

# REQ-010: Candidate bugs minimum
# Exact text (line 345): "Minimum: 4 candidate bugs with file:line references"
if grep -q "Minimum: 4 candidate bugs" "$SKILLMD" 2>/dev/null; then
    pass "test_skillmd_requires_minimum_4_candidate_bugs"
else
    fail "test_skillmd_requires_minimum_4_candidate_bugs — text not found in SKILL.md"
fi

# REQ-011: Requirements pipeline — 5 phases defined
PIPELINE_PHASE_A=$(grep -c "Phase A.*[Cc]ontract\|Phase A —.*[Cc]ontract" "$SKILLMD" 2>/dev/null || echo 0)
PIPELINE_PHASE_E=$(grep -c "Phase E.*[Nn]arrative\|Phase E —.*[Nn]arrative" "$SKILLMD" 2>/dev/null || echo 0)
assert_count_ge "$PIPELINE_PHASE_A" 1 \
    "test_skillmd_requirements_pipeline_phase_A_defined"
assert_count_ge "$PIPELINE_PHASE_E" 1 \
    "test_skillmd_requirements_pipeline_phase_E_defined"

# REQ-011: User story "so that" clause is mandatory
assert_contains "$SKILLMD" 'The "so that" clause is mandatory' \
    "test_skillmd_user_story_so_that_is_mandatory"

# REQ-009: Version stamp instruction
# Exact text (line 926): "The version in the stamp must match the `metadata.version` in this skill's frontmatter."
if grep -q "The version in the stamp must match" "$SKILLMD" 2>/dev/null; then
    pass "test_skillmd_version_stamp_instruction_present"
else
    fail "test_skillmd_version_stamp_instruction_present — version stamp instruction not found in SKILL.md"
fi

# REQ-005: Phase 0b described
assert_contains "$SKILLMD" "Phase 0b" \
    "test_skillmd_phase_0b_seed_discovery_present"

# REQ-005: Phase 0b activation condition text
# Exact text (line 297): "**This step runs only if `previous_runs/` does not exist**"
if grep -q "previous_runs.*does not exist" "$SKILLMD" 2>/dev/null; then
    pass "test_phase0b_activation_condition_explicit — Phase 0b activation condition documented"
else
    fail "test_phase0b_activation_condition_explicit — Phase 0b activation condition not found in SKILL.md"
fi

# REQ-005: BUG check — no handling for empty previous_runs/ case
if grep -qE "empty.*previous_runs|previous_runs.*empty|exists but.*empty|no.*conformant.*artifacts" "$SKILLMD" 2>/dev/null; then
    pass "test_phase0_empty_previous_runs_gap — SKILL.md handles empty previous_runs/ case"
else
    fail "test_phase0_empty_previous_runs_gap — BUG-M5: SKILL.md does not handle empty previous_runs/ case — Phase 0b skips when dir exists but empty (REQ-005 violated)"
fi

# REQ-004: Artifact contract table — test_regression.* entry
assert_contains "$SKILLMD" 'test_regression\.\*' \
    "test_artifact_contract_table_includes_regression_tests"

# REQ-004: Regression test required if bugs found
# Artifact contract table: | Regression tests | `quality/test_regression.*` | If bugs found | Phase 3 |
assert_contains "$SKILLMD" 'test_regression\.\*.*If bugs found' \
    "test_artifact_contract_regression_test_required_if_bugs_found"

# REQ-010: EXPLORATION.md minimum line count
# Exact text (line 840): "EXPLORATION.md must contain at least 120 lines of substantive content"
if grep -q "at least 120 lines of substantive" "$SKILLMD" 2>/dev/null; then
    pass "test_skillmd_exploration_minimum_120_lines"
else
    fail "test_skillmd_exploration_minimum_120_lines — minimum 120 lines requirement not found in SKILL.md"
fi

echo ""

# ============================================================
# GROUP 2: Fitness Scenario Tests (QUALITY.md scenario verification)
# ============================================================

echo "--- GROUP 2: Fitness Scenarios ---"
echo ""

# Scenario 1: JSON key validation false positive (BUG-H1, REQ-001)
assert_file_exists "$GATE" "test_gate_file_exists"

# Extract json_has_key implementation and verify it uses grep with just the key name
JSON_HAS_KEY_IMPL=$(awk '/^json_has_key\(\)/,/^}/' "$GATE" 2>/dev/null)
if [ -n "$JSON_HAS_KEY_IMPL" ]; then
    # Check if the regex requires colon after the key (proper JSON key detection)
    if echo "$JSON_HAS_KEY_IMPL" | grep -qE '".*"[[:space:]]*:|\\".*\\":'; then
        pass "test_json_has_key_no_false_positive_from_string_value — json_has_key regex requires colon after key name"
    else
        fail "test_json_has_key_no_false_positive_from_string_value — BUG-H1: json_has_key does not require colon — matches keys in string values (REQ-001 violated)"
    fi
else
    fail "test_json_has_key_no_false_positive_from_string_value — could not extract json_has_key implementation from $GATE"
fi

# Test json_key_count for same false-positive issue — this function DOES use colon pattern
JSON_KEY_COUNT_IMPL=$(awk '/^json_key_count\(\)/,/^}/' "$GATE" 2>/dev/null)
if [ -n "$JSON_KEY_COUNT_IMPL" ]; then
    if echo "$JSON_KEY_COUNT_IMPL" | grep -qE '".*"\[.*\]\*:|\[\[.*\]\]:.*:|grep.*".*"\['; then
        pass "test_json_key_count_no_inflation_from_string_values — json_key_count regex requires colon"
    else
        # The exploration found json_key_count uses: grep -c "\"${key}\"[[:space:]]*:"
        # This DOES include colon but still matches keys in string values: "The 'id' field: deprecated"
        fail "test_json_key_count_no_inflation_from_string_values — BUG-H1: json_key_count cannot distinguish 'key: value' in string content from actual JSON keys (REQ-001 partially violated — colon present but still fragile)"
    fi
else
    fail "test_json_key_count_no_inflation_from_string_values — could not extract json_key_count implementation"
fi

# Scenario 2: Space-in-path array corruption (BUG-H2, REQ-002)
# Find the REPO_DIRS array reconstruction line
REPO_DIRS_LINE=$(grep -n 'REPO_DIRS=(' "$GATE" 2>/dev/null | tail -1)
if [ -n "$REPO_DIRS_LINE" ]; then
    LINE_NUM=$(echo "$REPO_DIRS_LINE" | cut -d: -f1)
    LINE_CONTENT=$(echo "$REPO_DIRS_LINE" | cut -d: -f2-)
    # Check if the outer expansion is properly quoted: ("${resolved[@]...}")
    if echo "$LINE_CONTENT" | grep -qE 'REPO_DIRS=\("'; then
        pass "test_repo_path_with_spaces_survives_array_reconstruction — REPO_DIRS expansion is properly quoted (line ${LINE_NUM})"
    else
        fail "test_repo_path_with_spaces_survives_array_reconstruction — BUG-H2: REPO_DIRS reconstruction at line ${LINE_NUM} is unquoted — paths with spaces will be word-split (REQ-002 violated): $LINE_CONTENT"
    fi
else
    skip "test_repo_path_with_spaces_survives_array_reconstruction — REPO_DIRS pattern not found in gate"
fi

# Also check the loop expansion (line ~686)
LOOP_EXPANSION=$(grep -n 'for name in.*REPO_DIRS' "$GATE" 2>/dev/null | head -1)
if [ -n "$LOOP_EXPANSION" ]; then
    if echo "$LOOP_EXPANSION" | grep -qE '".*REPO_DIRS'; then
        pass "test_array_expansion_loop_quoted — REPO_DIRS loop expansion is quoted"
    else
        fail "test_array_expansion_loop_quoted — REPO_DIRS loop expansion is unquoted (word-splitting risk)"
    fi
fi

# Scenario 3: Shallow EXPLORATION.md bypass (BUG-M3, REQ-003)
# Verify Phase 1 gate checks 8, 10, 12 are defined
# Exact text (line 857): "Between 3 and 4 patterns (inclusive) are marked `FULL`"
if grep -q "Between 3 and 4 patterns (inclusive) are marked" "$SKILLMD" 2>/dev/null; then
    pass "test_phase1_gate_check_8_defined — Phase 1 gate check 8 (3-4 FULL patterns) defined"
else
    fail "test_phase1_gate_check_8_defined — Phase 1 gate check 8 text not found in SKILL.md"
fi

# Exact text (line 859): "10. **Pattern depth check:**"
if grep -q "Pattern depth check:" "$SKILLMD" 2>/dev/null; then
    pass "test_phase1_gate_check_10_defined — Phase 1 gate check 10 (Pattern depth check) defined"
else
    fail "test_phase1_gate_check_10_defined — Phase 1 gate check 10 text not found in SKILL.md"
fi

# Exact text (line 861): "12. **Ensemble balance check:**"
if grep -q "Ensemble balance check:" "$SKILLMD" 2>/dev/null; then
    pass "test_phase1_gate_check_12_defined — Phase 1 gate check 12 (ensemble balance check) defined"
else
    fail "test_phase1_gate_check_12_defined — Phase 1 gate check 12 text not found in SKILL.md"
fi

# Scenario 4: Regression test file not enforced (BUG-M4, REQ-004)
# Gate DOES check for regression test files (lines ~480-525)
REGRESSION_TEST_CHECK=$(grep -n "test_regression" "$GATE" 2>/dev/null | grep -v "patch" | head -1)
if [ -n "$REGRESSION_TEST_CHECK" ]; then
    pass "test_gate_requires_regression_test_file_when_bugs_exist — gate checks test_regression.* existence (${REGRESSION_TEST_CHECK})"
else
    fail "test_gate_requires_regression_test_file_when_bugs_exist — BUG-M4: gate does not check for quality/test_regression.* existence (REQ-004 violated)"
fi

# Gate checks patches too
PATCH_CHECK=$(grep -n "patches.*BUG\|BUG.*patch\|reg_patch_count\|regression.*patch" "$GATE" 2>/dev/null | head -1)
if [ -n "$PATCH_CHECK" ]; then
    pass "test_gate_regression_test_patch_check_present — gate checks regression test patches"
else
    fail "test_gate_regression_test_patch_check_present — gate does not check regression test patches"
fi

# Scenario 5: Phase 0b seed discovery — empty previous_runs/ not handled
# Already tested in Group 1 — test_phase0_empty_previous_runs_gap

# Scenario 6: Version stamp drift (BUG-L7, REQ-006)
if [ -n "${FRONTMATTER_VERSION:-}" ]; then
    VERSION_OCCURRENCES=$(grep -c "$FRONTMATTER_VERSION" "$SKILLMD" 2>/dev/null || echo 0)
    assert_count_ge "$VERSION_OCCURRENCES" 3 \
        "test_version_stamp_multiple_locations — version $FRONTMATTER_VERSION appears in multiple locations"

    # Extract version from tdd-results.json example
    TDD_JSON_VERSION=$(grep -A10 '"skill_version"' "$SKILLMD" 2>/dev/null | grep -o '"[0-9]\+\.[0-9]\+\.[0-9]\+"' | head -1 | tr -d '"')
    if [ -n "$TDD_JSON_VERSION" ]; then
        if [ "$TDD_JSON_VERSION" = "$FRONTMATTER_VERSION" ]; then
            pass "test_skillmd_frontmatter_version_matches_json_example — tdd-results.json example version ($TDD_JSON_VERSION) matches frontmatter ($FRONTMATTER_VERSION)"
        else
            fail "test_skillmd_frontmatter_version_matches_json_example — BUG-L7: JSON example version ($TDD_JSON_VERSION) differs from frontmatter ($FRONTMATTER_VERSION) (REQ-006 violated)"
        fi
    else
        fail "test_tdd_results_json_example_version_field — could not extract version from tdd-results.json example in SKILL.md"
    fi
fi

# Scenario 7: json_str_val misleading error (BUG-L6, REQ-007)
JSON_STR_VAL_IMPL=$(awk '/^json_str_val\(\)/,/^}/' "$GATE" 2>/dev/null)
if [ -n "$JSON_STR_VAL_IMPL" ]; then
    # Check if function distinguishes non-string values — currently it does NOT
    # The regex requires "value" (quoted), non-string values return empty indistinguishable from absent
    if echo "$JSON_STR_VAL_IMPL" | grep -qE 'non.string\|NOT_STRING\|not.*string\|type.*mismatch'; then
        pass "test_json_str_val_non_string_value_handling — json_str_val distinguishes non-string values"
    else
        fail "test_json_str_val_non_string_value_handling — BUG-L6: json_str_val returns empty for both absent key AND non-string value — misleading error messages (REQ-007 violated)"
    fi
else
    fail "test_json_str_val_absent_key — could not extract json_str_val implementation"
fi

# Scenario 8: Mandatory First Action vs autonomous mode
# Test that the autonomous fallback rule exists (line 376: "**Autonomous fallback:**")
if grep -q "Autonomous fallback:" "$SKILLMD" 2>/dev/null; then
    pass "test_autonomous_fallback_rule_present — autonomous fallback rule is present"
else
    fail "test_autonomous_fallback_rule_present — autonomous fallback rule not found in SKILL.md"
fi

echo ""

# ============================================================
# GROUP 3: Boundary and Edge Cases (defensive patterns)
# ============================================================

echo "--- GROUP 3: Boundary and Edge Cases ---"
echo ""

# Boundary: set -uo pipefail (Finding 9)
assert_contains "$GATE" "set -uo pipefail" \
    "test_gate_uses_pipefail — gate uses set -uo pipefail"

# Boundary: set -e absent (Finding 9 — known gap)
if grep -q "^set -e\b" "$GATE" 2>/dev/null; then
    pass "test_gate_no_silent_command_failures — gate uses set -e"
else
    fail "test_gate_no_silent_command_failures — gate does not use set -e — individual command failures silently continue (Finding 9)"
fi

# Boundary: || echo 0 fallbacks (compensating for no set -e)
# json_key_count uses: grep -c ... || echo 0
OR_ECHO_0=$(grep -c '|| echo 0' "$GATE" 2>/dev/null || echo 0)
if [ "$OR_ECHO_0" -gt 0 ]; then
    pass "test_gate_or_echo_0_fallback_present — grep fallbacks use || echo 0 (${OR_ECHO_0} occurrences)"
else
    fail "test_gate_or_echo_0_fallback_present — expected || echo 0 fallbacks in gate"
fi

# Boundary: Date comparison using string comparison (Finding 7)
# quality_gate.sh:279: if [[ "$tdd_date" > "$today" ]]; then
# The pattern uses bash [[ ]] with > which is lexicographic string comparison
if grep -q '"$tdd_date" > "$today"' "$GATE" 2>/dev/null; then
    pass "test_gate_date_comparison_uses_string_comparison — date comparison uses string comparison ([[ > ]])"
else
    skip "test_gate_date_comparison_uses_string_comparison — could not find date comparison pattern in gate"
fi

# Boundary: 2>/dev/null suppressions
DEVNULL_COUNT=$(grep -c "2>/dev/null" "$GATE" 2>/dev/null || echo 0)
assert_count_ge "$DEVNULL_COUNT" 5 \
    "test_gate_stderr_suppression_present — gate suppresses stderr in ${DEVNULL_COUNT} places"

# Boundary: Functional test detection uses ls glob (Finding 3, REQ-014)
LS_FUNCTIONAL=$(grep -n "ls.*test_functional\|ls.*FunctionalSpec\|ls.*FunctionalTest\|ls.*functional\.test" "$GATE" 2>/dev/null | head -1)
FIND_FUNCTIONAL=$(grep -n "find.*test_functional\|find.*FunctionalSpec\|find.*FunctionalTest\|find.*functional\.test" "$GATE" 2>/dev/null | head -1)
if [ -n "$FIND_FUNCTIONAL" ]; then
    pass "test_functional_test_detection_method_consistency — functional test detection uses find (consistent)"
elif [ -n "$LS_FUNCTIONAL" ]; then
    fail "test_functional_test_detection_method_consistency — BUG/Finding 3: functional test detection uses ls glob (fragile), language detection uses find (REQ-014 violated)"
else
    skip "test_functional_test_detection_method_consistency — could not determine detection method"
fi

# Boundary: Redundant redirect pattern (Finding 3)
REDUNDANT_REDIRECT=$(grep -cE "&>/dev/null 2>&1" "$GATE" 2>/dev/null || echo 0)
if [ "$REDUNDANT_REDIRECT" -gt 0 ]; then
    fail "test_no_redundant_redirect_pattern — Found ${REDUNDANT_REDIRECT} occurrence(s) of redundant '&>/dev/null 2>&1' (stdout already redirected by &>)"
else
    pass "test_no_redundant_redirect_pattern — no redundant &>/dev/null 2>&1 patterns"
fi

# Boundary: VERSION detection walks list of paths including SKILL.md
assert_contains "$GATE" "SKILL\.md" \
    "test_version_detection_checks_skillmd — gate VERSION detection looks for SKILL.md"

# Boundary: Verdict enum completeness (5 values must be in gate regex)
# Gate validates: TDD verified, red failed, green failed, confirmed open, deferred
# These appear in the grep -cvE regex pattern at line 296
VERDICT_REGEX_LINE=$(grep 'grep -cvE.*TDD verified\|grep -cvE.*confirmed open' "$GATE" 2>/dev/null | head -1)
if [ -n "$VERDICT_REGEX_LINE" ]; then
    # Count the 5 expected values in the regex
    FOUND_VERDICTS=0
    for v in "TDD verified" "red failed" "green failed" "confirmed open" "deferred"; do
        if echo "$VERDICT_REGEX_LINE" | grep -q "$v"; then
            ((FOUND_VERDICTS++))
        fi
    done
    assert_count_between "$FOUND_VERDICTS" 5 5 \
        "test_verdict_enum_completeness — gate validates all 5 verdict values in regex"
else
    fail "test_verdict_enum_completeness — verdict validation regex not found in gate"
fi

# Boundary: Gate checks mechanical/verify.sh (at line ~163, ~545-547)
if grep -q "mechanical/verify.sh\|verify.sh" "$GATE" 2>/dev/null; then
    pass "test_gate_checks_mechanical_verify_sh — gate checks for mechanical/verify.sh"
else
    fail "test_gate_checks_mechanical_verify_sh — gate does not check for mechanical/verify.sh"
fi

# Boundary: Gate checks EXPLORATION.md
assert_contains "$GATE" "EXPLORATION\.md" \
    "test_gate_checks_exploration_md — gate checks for EXPLORATION.md"

# Boundary: All 13 required artifacts are checked by the gate
REQUIRED_ARTIFACTS="QUALITY.md REQUIREMENTS.md CONTRACTS.md COVERAGE_MATRIX.md COMPLETENESS_REPORT.md BUGS.md RUN_CODE_REVIEW.md RUN_INTEGRATION_TESTS.md RUN_SPEC_AUDIT.md RUN_TDD_TESTS.md AGENTS.md PROGRESS.md"
for artifact in $REQUIRED_ARTIFACTS; do
    if grep -q "$artifact" "$GATE" 2>/dev/null; then
        pass "test_gate_checks_${artifact} — gate references $artifact"
    else
        fail "test_gate_checks_${artifact} — gate does not reference $artifact"
    fi
done

# Boundary: SKILL.md has all 8 phase sections (0-7)
for phase_num in 0 1 2 3 4 5 6 7; do
    if grep -qE "^## Phase ${phase_num}:" "$SKILLMD" 2>/dev/null; then
        pass "test_skillmd_phase_${phase_num}_section — Phase ${phase_num} section present"
    else
        fail "test_skillmd_phase_${phase_num}_section — Phase ${phase_num} section missing"
    fi
done

# Boundary: Reference file resolution order documented
# SKILL.md line 46: "resolve it by checking these paths in order and using the first one that exists"
assert_contains "$SKILLMD" "checking these paths in order and using the first one that exists" \
    "test_reference_file_resolution_order_documented"

# Boundary: Use case UC-NN identifier format documented
# SKILL.md line 263: "derived requirements (REQ-NNN), and derived use cases (UC-NN)"
if grep -q "use cases (UC-NN)" "$SKILLMD" 2>/dev/null; then
    pass "test_use_case_uc_identifier_format_documented"
else
    fail "test_use_case_uc_identifier_format_documented — UC-NN identifier format not found in SKILL.md"
fi

# Boundary: Requirement REQ-NNN identifier format documented
if grep -q "requirements (REQ-NNN)" "$SKILLMD" 2>/dev/null; then
    pass "test_requirement_req_identifier_format_documented"
else
    fail "test_requirement_req_identifier_format_documented — REQ-NNN identifier format not found in SKILL.md"
fi

# Boundary: requirements_pipeline.md documents REQ-NNN heading format rule
# Line 92: "All requirements in REQUIREMENTS.md must use the format `### REQ-NNN: Title`"
if grep -q "format.*REQ-NNN: Title\|REQ-NNN: Title.*format\|use the format" "$REFS_DIR/requirements_pipeline.md" 2>/dev/null; then
    pass "test_requirement_heading_format_documented_in_pipeline_ref"
else
    fail "test_requirement_heading_format_documented_in_pipeline_ref — REQ-NNN heading format not found in requirements_pipeline.md"
fi

# Boundary: Council of Three spec audit
assert_contains "$SKILLMD" "Council of Three" \
    "test_council_of_three_defined"

# Boundary: All four iteration strategies documented
# SKILL.md documents them as code-formatted: `gap`, `unfiltered`, `parity`, `adversarial`
for strategy in gap unfiltered parity adversarial; do
    if grep -q "\`${strategy}\`" "$SKILLMD" 2>/dev/null; then
        pass "test_iteration_strategy_${strategy}_documented"
    else
        fail "test_iteration_strategy_${strategy}_documented — iteration strategy '${strategy}' not found in SKILL.md"
    fi
done

# Boundary: SKILL.md name field present
assert_contains "$SKILLMD" "^name: quality-playbook" \
    "test_skillmd_name_field_present — SKILL.md has name field"

# Boundary: SKILL.md license field present
assert_contains "$SKILLMD" "^license:" \
    "test_skillmd_license_field_present — SKILL.md has license field"

# Boundary: Sidecar JSON schema_version documented
assert_contains "$SKILLMD" '"schema_version".*"1\.' \
    "test_sidecar_json_schema_version_present — sidecar JSON schema_version documented"

# Boundary: integration-results.json recommendation values documented
assert_contains "$SKILLMD" '"SHIP"' \
    "test_integration_results_recommendation_ship_documented"
assert_contains "$SKILLMD" '"FIX BEFORE MERGE"' \
    "test_integration_results_recommendation_fix_documented"
assert_contains "$SKILLMD" '"BLOCK"' \
    "test_integration_results_recommendation_block_documented"

echo ""

# ============================================================
# SUMMARY
# ============================================================

echo "============================================================"
echo "Results: ${PASS_COUNT} passed, ${FAIL_COUNT} failed, ${SKIP_COUNT} skipped"
echo "============================================================"

if [ "$FAIL_COUNT" -gt 0 ]; then
    exit 1
else
    exit 0
fi
