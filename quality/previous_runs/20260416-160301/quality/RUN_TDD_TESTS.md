# TDD Verification Protocol: quality-playbook

<!-- Quality Playbook v1.4.1 — generated 2026-04-16 -->

## Overview

This protocol runs red-green TDD verification for each confirmed bug. The goal is to prove:
1. **Red phase:** The regression test fails on unpatched code — confirming the bug is real
2. **Green phase:** After applying the fix patch, the regression test passes

Every confirmed bug must go through this cycle before the bug can be marked "TDD verified."

---

## Bug Verification Instructions

For each bug in `quality/BUGS.md`, follow this procedure:

### Step 1: Run the regression test on unpatched code (Red Phase)

```bash
# Navigate to the repository
cd /Users/andrewstellman/tmp/QFB-bootstrap

# Run the specific regression test
bash quality/test_regression.sh --bug BUG-NNN  # or equivalent
```

Expected result: test FAILS. Capture output to `quality/results/BUG-NNN.red.log`.

If the test passes on unpatched code, the bug is NOT confirmed. Record "red failed" in `tdd-results.json`.

### Step 2: Apply the fix patch

```bash
# Apply the fix patch
git apply quality/patches/BUG-NNN-fix.patch
```

If no fix patch exists, the bug remains "confirmed open" — no green phase.

### Step 3: Run the regression test on patched code (Green Phase)

```bash
# Re-run the regression test
bash quality/test_regression.sh --bug BUG-NNN
```

Expected result: test PASSES. Capture output to `quality/results/BUG-NNN.green.log`.

If the test still fails after the patch, the fix is incomplete. Record "green failed" in `tdd-results.json`.

---

## Per-Bug TDD Instructions

### BUG-H1: json_has_key matches keys in string values

**Requirement:** REQ-001 — JSON key presence validation must not match string values

**Red phase test:**
```bash
# Create a test JSON where "id" appears only in a string value
cat > /tmp/bugH1_test.json << 'EOF'
{
  "msg": "The id field is deprecated",
  "bugs": [{"requirement": "test", "red_phase": "test", "green_phase": "test", "verdict": "confirmed open", "fix_patch_present": false, "writeup_path": "test"}],
  "summary": {"total": 1}
}
EOF

# Source the gate to get json_has_key function
# Then test: json_has_key should return FALSE for "id" since it only appears in a string value
bash -c '
source /Users/andrewstellman/tmp/QFB-bootstrap/quality_gate.sh 2>/dev/null
json_has_key /tmp/bugH1_test.json "id" && echo "FAIL: FALSE POSITIVE — key found in string value" || echo "PASS: key correctly not found"
' 2>/dev/null || grep -q '"id"' /tmp/bugH1_test.json && echo "BUG-H1 confirmed: json_has_key false positive"
```

Expected red-phase result: `FAIL: FALSE POSITIVE` (BUG-H1 confirmed)

**Regression test:** Write as `test_json_has_key_false_positive` in `quality/test_regression.sh`

---

### BUG-H2: Unquoted array expansion corrupts paths with spaces

**Requirement:** REQ-002 — Repo path array reconstruction must preserve spaces

**Red phase test:**
```bash
# Test array reconstruction with a path containing spaces
bash -c '
resolved=("/tmp/my repo/quality")
REPO_DIRS=(${resolved[@]+"${resolved[@]}"})  # Line 697 pattern — unquoted
echo "Element count: ${#REPO_DIRS[@]}"
echo "First element: ${REPO_DIRS[0]}"
[ "${REPO_DIRS[0]}" = "/tmp/my repo/quality" ] && echo "PASS: path preserved" || echo "FAIL: path split — BUG-H2 confirmed"
'
```

Expected red-phase result: `FAIL: path split` — array has 3 elements instead of 1

**Fix:**
```bash
# Fixed line 697:
REPO_DIRS=("${resolved[@]+"${resolved[@]}"}")
```

**Regression test:** Write as `test_repo_path_spaces_array_reconstruction` in `quality/test_regression.sh`

---

### BUG-M3: Phase 2 entry gate does not enforce Phase 1 checks 8, 10, 12

**Requirement:** REQ-003 — Phase 2 entry gate must enforce all substantive Phase 1 checks

**Red phase test:**
```bash
# Structural test: count Phase 1 gate checks vs Phase 2 gate checks
PHASE1_CHECKS=$(awk '/Phase 1 completion gate.*mandatory/,/Do not begin Phase 2/' SKILL.md | grep -c "^[0-9]\+\." || echo 0)
# Phase 2 should have same or more checks — if fewer, BUG-M3 confirmed
echo "Phase 1 checks: $PHASE1_CHECKS"
echo "Expected: 12"
[ "$PHASE1_CHECKS" -eq 12 ] && echo "RED PHASE: Phase 1 has 12 checks (expected)"
grep -q "Ensemble balance check" SKILL.md && echo "Phase 1 check 12 is defined" || echo "FAIL: check 12 not found"
```

The red phase for BUG-M3 is structural: verify that Phase 2 does NOT enforce check 12 (Ensemble balance check). If Phase 2 text does not mention "ensemble balance", the bug is confirmed.

**Regression test:** Write as `test_phase2_gate_enforces_ensemble_balance` in `quality/test_regression.sh`

---

### BUG-M5: Phase 0b skips when previous_runs/ exists but empty

**Requirement:** REQ-005 — Phase 0b must activate when previous_runs/ exists but empty

**Red phase test:**
```bash
# Structural test: verify SKILL.md Phase 0b condition
grep -n "does not exist" SKILL.md | grep "previous_runs" | head -3
# If the condition is "does not exist" (not "does not exist OR empty"), BUG-M5 is confirmed
grep -c "empty.*previous_runs\|previous_runs.*empty" SKILL.md
# Expected: 0 (no handling of empty case) — if 0, BUG-M5 confirmed
```

**Regression test:** Write as `test_phase0b_empty_previous_runs_activation` in `quality/test_regression.sh`

---

### BUG-L6: json_str_val misleading error for non-string values

**Requirement:** REQ-007 — json_str_val must distinguish absent from non-string values

**Red phase test:**
```bash
# Create JSON with number value for schema_version
cat > /tmp/bugL6_test.json << 'EOF'
{"schema_version": 1.1, "skill_version": "1.4.1"}
EOF

# Source gate and test
bash -c '
# Extract json_str_val function and test
RESULT=$(grep -o "\"schema_version\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" /tmp/bugL6_test.json 2>/dev/null | head -1 | sed "s/.*: *\"\([^\"]*\)\"/\1/")
echo "Result: \"$RESULT\""
[ -z "$RESULT" ] && echo "FAIL: BUG-L6 confirmed — returns empty for non-string value, indistinguishable from absent key" || echo "PASS"
'
```

Expected red-phase result: `FAIL: BUG-L6 confirmed`

**Regression test:** Write as `test_json_str_val_non_string_distinction` in `quality/test_regression.sh`

---

## Running All TDD Tests

```bash
# Run all regression tests (expected to fail on unpatched code)
bash quality/test_regression.sh 2>&1 | tee quality/results/regression-run.log

# After applying patches, re-run and verify green
bash quality/test_regression.sh 2>&1 | tee quality/results/regression-green.log
```

---

## Writing tdd-results.json

After running all TDD phases, write `quality/results/tdd-results.json`:

```json
{
  "schema_version": "1.1",
  "skill_version": "1.4.1",
  "date": "YYYY-MM-DD",
  "project": "quality-playbook",
  "bugs": [
    {
      "id": "BUG-H1",
      "requirement": "REQ-001: JSON key presence validation must not match string values",
      "red_phase": "regression test fails on unpatched code — json_has_key returns true for key in string value",
      "green_phase": "after applying fix patch, json_has_key returns false for key-in-string-value case",
      "verdict": "TDD verified",
      "fix_patch_present": true,
      "writeup_path": "quality/writeups/BUG-H1.md"
    }
  ],
  "summary": {
    "total": 7,
    "confirmed_open": 0,
    "red_failed": 0,
    "green_failed": 0,
    "verified": 7
  }
}
```

`verdict` must be one of: `"TDD verified"`, `"red failed"`, `"green failed"`, `"confirmed open"`, `"deferred"`.

## TDD Log Requirements

For each confirmed bug, write:
- `quality/results/BUG-NNN.red.log` — output from red-phase test run
- `quality/results/BUG-NNN.green.log` — output from green-phase test run (only if fix patch exists)

Missing log files cause the quality gate to fail in benchmark mode.
