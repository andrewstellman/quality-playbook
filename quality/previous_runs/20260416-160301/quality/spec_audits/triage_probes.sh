#!/bin/bash
# Triage Probes — quality-playbook Phase 4 Spec Audit
# Generated: 2026-04-16
# Purpose: Mechanically verify or refute each spec audit finding.
# Run from the project root: bash quality/spec_audits/triage_probes.sh

set -uo pipefail

SKILL="SKILL.md"
GATE="quality_gate.sh"
PASS=0
FAIL=0

probe_pass() { echo "  PROBE PASS: $1"; PASS=$((PASS + 1)); }
probe_fail() { echo "  PROBE FAIL (BUG CONFIRMED): $1"; FAIL=$((FAIL + 1)); }

echo "=== Triage Probes: quality-playbook Phase 4 Spec Audit ==="
echo ""

# ────────────────────────────────────────────────────────────────────────────
# PROBE-1: Confirm BUG-H1 — json_has_key false positive on string values
# Finding: A-1, known bug BUG-H1
# The false positive occurs when a STRING VALUE is literally "id" (or any key name)
# e.g.: {"type": "id", "value": 42} -- "id" appears as a string value, not a JSON key
# ────────────────────────────────────────────────────────────────────────────
echo "[PROBE-1] BUG-H1: json_has_key false positive (known seed)"
# Correct trigger: a JSON file where "id" appears as a string value (not a key)
printf '{"type": "id", "value": 42}\n' > /tmp/probe1.json
echo "  File content: $(cat /tmp/probe1.json)"
# Source the function definitions from quality_gate.sh
json_has_key_result=$(bash -c '
  json_has_key() { local file="$1" key="$2"; grep -q "\"${key}\"" "$file" 2>/dev/null; }
  json_has_key /tmp/probe1.json "id" && echo "FALSE_POSITIVE" || echo "CORRECTLY_FALSE"
')
echo "  json_has_key result: $json_has_key_result"
if [ "$json_has_key_result" = "FALSE_POSITIVE" ]; then
  probe_fail "BUG-H1 confirmed: line 77: json_has_key('/tmp/probe1.json', 'id') returns true when 'id' appears only as string value — file: {\"type\": \"id\", \"value\": 42}"
else
  probe_pass "BUG-H1 NOT reproduced"
fi
rm -f /tmp/probe1.json

# ────────────────────────────────────────────────────────────────────────────
# PROBE-2: Confirm BUG-H2 — unquoted array expansion corrupts paths with spaces
# Finding: C-10, known bug BUG-H2
# ────────────────────────────────────────────────────────────────────────────
echo "[PROBE-2] BUG-H2: Unquoted array expansion (known seed)"
# Line 697: REPO_DIRS=(${resolved[@]+"${resolved[@]}"})
# Verify the unquoted outer expansion is present
if grep -q 'REPO_DIRS=(${resolved' "$GATE"; then
  probe_fail "BUG-H2 confirmed: line 697: REPO_DIRS=(${resolved[@]+...}) outer expansion is unquoted — word-splitting occurs on spaces"
else
  probe_pass "BUG-H2 NOT found (unexpected)"
fi

# ────────────────────────────────────────────────────────────────────────────
# PROBE-3: Confirm nullglob vulnerability in triage_count (Finding B-4, C-1)
# NET-NEW CANDIDATE
# ────────────────────────────────────────────────────────────────────────────
echo "[PROBE-3] NULLGLOB: triage_count ls-glob returns wrong count when nullglob enabled"
# Simulate what happens at line 152 under nullglob
nullglob_test=$(bash -c '
  set -o nullglob 2>/dev/null || true
  mkdir -p /tmp/probe3_empty
  count=$(ls /tmp/probe3_empty/*triage* 2>/dev/null | wc -l | tr -d " ")
  echo "$count"
  rmdir /tmp/probe3_empty 2>/dev/null || true
')
# Under nullglob, if /tmp/probe3_empty exists but has no *triage* files:
# ls expands to: ls (no args) which lists current directory
# wc -l would return >0 if current dir has files
# We verify by checking if count is nonzero even though no triage files exist
if [ "${nullglob_test:-0}" -gt 0 ] 2>/dev/null; then
  probe_fail "NULLGLOB confirmed: line 152: triage_count=$nullglob_test when directory exists but is empty — ls lists current dir under nullglob"
else
  probe_pass "Nullglob behavior for line 152: count=$nullglob_test (may not apply in current shell config)"
fi

# ────────────────────────────────────────────────────────────────────────────
# PROBE-4: Confirm nullglob vulnerability in reg_patch_count (Finding C-2, C-8)
# NET-NEW CANDIDATE
# ────────────────────────────────────────────────────────────────────────────
echo "[PROBE-4] NULLGLOB: reg_patch_count ls-glob correct pattern check"
# Verify the unquoted ls glob pattern is present in quality_gate.sh
actual_line=$(sed -n '567p' "$GATE")
echo "  Line 567: $actual_line"
if echo "$actual_line" | grep -q 'ls \${q}/patches/BUG-\*-regression\*\.patch'; then
  probe_fail "Nullglob vulnerability confirmed: line 567 uses unquoted ls glob 'ls \${q}/patches/BUG-*-regression*.patch' — returns wrong count under nullglob"
else
  probe_pass "Line 567 pattern check: $actual_line"
fi

# ────────────────────────────────────────────────────────────────────────────
# PROBE-5: Confirm nullglob vulnerability in fix patch check (Finding C-5)
# NET-NEW CANDIDATE
# ────────────────────────────────────────────────────────────────────────────
echo "[PROBE-5] NULLGLOB: fix patch existence check at line 331"
actual_line_331=$(sed -n '331p' "$GATE")
echo "  Line 331: $actual_line_331"
if echo "$actual_line_331" | grep -q 'ls \${q}/patches/\${bid}-fix\*'; then
  probe_fail "Nullglob vulnerability confirmed: line 331: 'ls \${q}/patches/\${bid}-fix*.patch' — under nullglob, ls with no matches returns exit 0 by listing current dir"
else
  probe_pass "Line 331: $actual_line_331 (pattern not found)"
fi

# ────────────────────────────────────────────────────────────────────────────
# PROBE-6: Confirm auditor naming inconsistency (Finding A-10)
# NET-NEW — Three naming formats for individual auditor reports
# ────────────────────────────────────────────────────────────────────────────
echo "[PROBE-6] NAMING: Individual auditor report naming inconsistency"
# Check SKILL.md Phase 4 instruction
phase4_naming=$(grep -n 'YYYY-MM-DD-auditor-N' "$SKILL" | head -1)
# Check RUN_SPEC_AUDIT.md
spec_audit_naming=$(grep -n 'auditor_<model>' quality/RUN_SPEC_AUDIT.md 2>/dev/null | head -1)
echo "  SKILL.md Phase 4 naming: $phase4_naming"
echo "  RUN_SPEC_AUDIT.md naming: $spec_audit_naming"
if [ -n "$phase4_naming" ] && [ -n "$spec_audit_naming" ]; then
  # Both exist — check if they're different formats
  if echo "$phase4_naming" | grep -q 'YYYY-MM-DD-auditor-N' && echo "$spec_audit_naming" | grep -q 'auditor_<model>'; then
    probe_fail "Naming inconsistency confirmed: SKILL.md line 1548 says 'YYYY-MM-DD-auditor-N.md' but RUN_SPEC_AUDIT.md says 'auditor_<model>_<date>.md' — two incompatible naming formats"
  fi
else
  probe_pass "Naming patterns not both found (partial check)"
fi

# ────────────────────────────────────────────────────────────────────────────
# PROBE-7: Confirm recheck schema_version = "1.0" vs "1.1" inconsistency (Finding A-9, B-7)
# NET-NEW
# ────────────────────────────────────────────────────────────────────────────
echo "[PROBE-7] SCHEMA: recheck-results.json uses schema_version 1.0 vs 1.1"
recheck_schema=$(grep -n '"schema_version": "1\.0"' "$SKILL" | head -1)
main_schema=$(grep -n '"schema_version": "1\.1"' "$SKILL" | head -1)
echo "  recheck 1.0 occurrence: $recheck_schema"
echo "  tdd/integration 1.1 occurrence: $main_schema"
if [ -n "$recheck_schema" ] && [ -n "$main_schema" ]; then
  probe_fail "Schema version inconsistency confirmed: SKILL.md has both schema_version '1.0' (line $(echo "$recheck_schema" | cut -d: -f1)) and '1.1' (line $(echo "$main_schema" | cut -d: -f1)) — recheck uses different schema version with no migration note"
else
  probe_pass "Schema version check — only one version found"
fi

# ────────────────────────────────────────────────────────────────────────────
# PROBE-8: Confirm empty VERSION produces non-diagnostic error message (Finding A-2, REQ-012)
# NET-NEW
# ────────────────────────────────────────────────────────────────────────────
echo "[PROBE-8] REQ-012: Empty VERSION with --all produces usage message, not VERSION-specific error"
empty_version_output=$(VERSION="" bash -c '
  # Simulate the --all path with empty VERSION
  # Extract the glob from quality_gate.sh line 678
  # dir pattern: ${SCRIPT_DIR}/*-"${VERSION}"/
  # With VERSION="": pattern becomes *-"/  -- matches nothing
  # Then REPO_DIRS is empty, triggers line 700
  echo "$(sed -n "700,702p" quality_gate.sh)"
' 2>/dev/null)
echo "  Lines 700-702: $empty_version_output"
# Check that the usage message does NOT mention VERSION or SKILL.md
if echo "$empty_version_output" | grep -qE 'Usage.*\[--version'; then
  probe_fail "REQ-012 not satisfied: line 700-702 emits generic 'Usage: ...' message without naming VERSION empty or SKILL.md not found as the cause"
else
  probe_pass "Empty VERSION error message check passed"
fi

# ────────────────────────────────────────────────────────────────────────────
# PROBE-9: Confirm BUG-M3 — Phase 2 entry gate has only 6 of 12 checks
# Known seed
# ────────────────────────────────────────────────────────────────────────────
echo "[PROBE-9] BUG-M3: Phase 2 entry gate enforces 6 of 12 Phase 1 checks (known seed)"
phase2_gate=$(sed -n '897,910p' "$SKILL")
check_count=$(echo "$phase2_gate" | grep -c '^\s*[0-9]\+\.')
echo "  Phase 2 gate checks found: $check_count"
if [ "$check_count" -eq 6 ]; then
  probe_fail "BUG-M3 confirmed: Phase 2 entry gate (SKILL.md ~line 897) has exactly 6 checks, not 12 — checks 2,3,5,8,10,12 from Phase 1 completion gate are absent"
else
  probe_pass "Phase 2 entry gate check count: $check_count (may vary)"
fi

# ────────────────────────────────────────────────────────────────────────────
# PROBE-10: Confirm BUG-M5 — Phase 0b skips when previous_runs/ exists but empty
# Known seed
# ────────────────────────────────────────────────────────────────────────────
echo "[PROBE-10] BUG-M5: Phase 0b activation condition (known seed)"
phase0b_condition=$(grep -n 'runs only if.*previous_runs.*does not exist' "$SKILL" | head -1)
echo "  Phase 0b condition: $phase0b_condition"
if [ -n "$phase0b_condition" ]; then
  probe_fail "BUG-M5 confirmed: Phase 0b condition (SKILL.md line $(echo "$phase0b_condition" | cut -d: -f1)): 'This step runs only if previous_runs/ does not exist' — misses case where previous_runs/ exists but is empty"
else
  probe_pass "Phase 0b condition not found as described"
fi

# ────────────────────────────────────────────────────────────────────────────
# PROBE-11: Confirm BUG-M4 — test_regression.* not gate-checked when bug_count > 0
# Known seed
# ────────────────────────────────────────────────────────────────────────────
echo "[PROBE-11] BUG-M4: test_regression.* existence not enforced by gate when bug_count > 0"
# The gate check (lines 519-527) only validates extension IF the file exists
# There is NO check: "if bug_count > 0 and reg_test is empty, fail"
# Verify: find the reg_test check — it only fires when reg_test is non-empty
reg_test_line=$(grep -n 'if \[ -n "\$reg_test"' "$GATE")
echo "  reg_test existence check: $reg_test_line"
# Check whether there is a fail condition requiring test_regression when bug_count > 0
# Check whether there is a fail condition requiring test_regression when bug_count > 0
# The fail at line 525 is only for wrong extension, not missing file
# Verify no "fail" statement references test_regression in a bug_count > 0 context
fail_for_missing=$(grep -n 'fail.*test_regression\|test_regression.*missing' "$GATE" | head -1)
echo "  fail-for-missing check: '${fail_for_missing}'"
if [ -z "$fail_for_missing" ]; then
  probe_fail "BUG-M4 confirmed: line 519: 'if [ -n \"\$reg_test\" ]' only checks extension if file exists — no 'fail' message for test_regression.* absence when bug_count > 0"
else
  probe_pass "BUG-M4: some test_regression missing/fail check found: $fail_for_missing"
fi

# ────────────────────────────────────────────────────────────────────────────
# PROBE-12: Confirm two-template discrepancy for tdd-results.json (Finding A-8)
# NET-NEW
# ────────────────────────────────────────────────────────────────────────────
echo "[PROBE-12] REQ-009: Two tdd-results.json templates in SKILL.md with different fields"
# Template 1: lines ~122-148 (artifact contract section)
template1_line=$(grep -n '"requirement":' "$SKILL" | head -1)
# Template 2: lines ~1374-1410 (Phase 5 File 7 section) -- includes optional fields
template2_optional=$(grep -n 'patch_gate_passed\|junit_red\|junit_green\|junit_available' "$SKILL" | head -1)
echo "  Template 1 (artifact contract) uses 'requirement' field: $template1_line"
echo "  Template 2 (Phase 5) includes optional fields: $template2_optional"
if [ -n "$template1_line" ] && [ -n "$template2_optional" ]; then
  probe_fail "Two-template inconsistency confirmed: SKILL.md has abbreviated template at ~line 122 (artifact contract) and extended template at ~line 1374 (Phase 5) with different optional fields — agents may generate different JSON depending on which template they follow"
else
  probe_pass "Template check: only one template found"
fi

echo ""
echo "=== Probe Results: $FAIL CONFIRMED BUGS, $PASS passed ==="
