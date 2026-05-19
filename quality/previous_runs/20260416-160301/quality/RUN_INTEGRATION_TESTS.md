# Integration Test Protocol: quality-playbook

<!-- Quality Playbook v1.4.1 — generated 2026-04-16 -->

## Overview

This protocol runs end-to-end tests of the quality-playbook system — verifying that `quality_gate.sh` correctly validates artifact sets, and that SKILL.md's phase pipeline produces conformant artifacts when followed exactly.

**Note:** Because the primary product is a Markdown AI instruction document, "integration testing" here means:
1. Running `quality_gate.sh` against known-good and known-bad artifact sets to verify gate accuracy
2. Verifying that generated artifacts (this quality run itself) pass the gate
3. Checking SKILL.md structural completeness and internal consistency end-to-end

---

## Group 1: Gate Conformance on Known-Good Artifacts

**Linked use cases:** UC-03 (Developer verifies conformance)
**Linked requirements:** REQ-001, REQ-002, REQ-004, REQ-006, REQ-009

### Setup

```bash
# Run the gate on this quality playbook run
bash quality_gate.sh /Users/andrewstellman/tmp/QFB-bootstrap
```

### Expected outcome

- Gate reports PASS (0 failures) in general mode
- All required artifacts are found and checked
- Version stamps match SKILL.md frontmatter v1.4.1

### Test steps

1. Run `bash quality_gate.sh .` from the repository root
2. Verify exit code 0
3. Verify output contains "GATE PASSED" or no FAIL lines
4. Verify version stamp in EXPLORATION.md matches frontmatter
5. Check that all 14 required artifacts are found

---

## Group 2: Gate Failure on Missing Artifacts

**Linked use cases:** UC-03 (Developer verifies conformance)
**Linked requirements:** REQ-004, REQ-009

### Setup

```bash
# Create a temporary test directory with minimal artifacts
mkdir -p /tmp/qp-test-missing/quality
cp quality/PROGRESS.md /tmp/qp-test-missing/quality/
# Intentionally omit QUALITY.md, REQUIREMENTS.md, etc.
```

### Expected outcome

- Gate reports FAIL with specific messages for each missing artifact
- QUALITY.md, REQUIREMENTS.md, CONTRACTS.md should each generate a FAIL line

### Test steps

1. Create minimal artifact directory (only PROGRESS.md)
2. Run `bash quality_gate.sh /tmp/qp-test-missing`
3. Verify exit code non-zero (gate failed)
4. Verify FAIL lines reference missing artifacts

---

## Group 3: JSON Validation with Malformed tdd-results.json

**Linked use cases:** UC-03 (Developer verifies conformance)
**Linked requirements:** REQ-001, REQ-007

### Setup

```bash
# Create a malformed tdd-results.json where a required field appears only in a string value
mkdir -p /tmp/qp-test-json/quality/results
cat > /tmp/qp-test-json/quality/results/tdd-results.json << 'EOF'
{
  "schema_version": "1.1",
  "skill_version": "1.4.1",
  "date": "2026-04-16",
  "project": "test",
  "bugs": [
    {
      "id": "BUG-001",
      "requirement": "UC-01: test",
      "red_phase": "The 'green_phase' field is tested here",
      "verdict": "confirmed open",
      "fix_patch_present": false,
      "writeup_path": "quality/writeups/BUG-001.md"
    }
  ],
  "summary": {"total": 1, "confirmed_open": 1, "red_failed": 0, "green_failed": 0, "verified": 0}
}
EOF
```

Note: The above JSON has `"green_phase"` appearing only in the `"red_phase"` string value, not as an actual field. This tests whether `json_has_key` produces false positives (BUG-H1: it does).

### Expected outcome

- Gate SHOULD fail because `green_phase` field is missing from the bug entry
- Gate WILL fail (pass the test) if BUG-H1 is confirmed: `json_has_key` returns true from the string value match

### Test steps

1. Create the malformed JSON as above
2. Run the gate with this JSON
3. Record whether gate reports FAIL for missing `green_phase` or incorrectly reports PASS
4. Document BUG-H1 confirmation or rejection

---

## Group 4: Path With Spaces in Repo Argument

**Linked use cases:** UC-03 (Developer verifies conformance)
**Linked requirements:** REQ-002

### Setup

```bash
# Create a quality directory with spaces in the path
mkdir -p "/tmp/my repo with spaces/quality"
cp -r quality/* "/tmp/my repo with spaces/quality/"
```

### Expected outcome (current behavior — BUG-H2 present)

- Gate should correctly check `/tmp/my repo with spaces/quality/`
- Current behavior (BUG-H2): array reconstruction at line 697 splits the path, causing checks to run against `/tmp/my` instead

### Test steps

1. Create artifacts in a path containing spaces
2. Run `bash quality_gate.sh "/tmp/my repo with spaces"`
3. Verify gate checks the correct path (not word-split fragments)
4. Document BUG-H2 confirmation or rejection

---

## Group 5: Version Stamp Consistency End-to-End

**Linked use cases:** UC-04 (Maintainer updates version)
**Linked requirements:** REQ-006, REQ-009

### Setup

No special setup — use the existing SKILL.md and generated artifacts.

### Expected outcome

- SKILL.md frontmatter version (1.4.1) must match all generated artifacts
- Version stamp in each artifact must be parseable by the gate

### Test steps

1. Extract `metadata.version` from SKILL.md frontmatter
2. Check `quality/PROGRESS.md` "Skill version:" field
3. Check header comments in each generated artifact
4. Run `bash quality_gate.sh .` and verify version mismatch is not reported
5. Manually count occurrences of version string in SKILL.md and verify all are identical

---

## Group 6: Phase 0b Activation Condition Test

**Linked use cases:** UC-05 (Developer runs iteration)
**Linked requirements:** REQ-005

### Setup

```bash
mkdir -p /tmp/qp-test-phase0b/previous_runs
# Intentionally leave previous_runs/ empty
mkdir -p /tmp/qp-test-phase0b-sibling-1.4.0/quality
# Create a sibling with a BUGS.md
cat > /tmp/qp-test-phase0b-sibling-1.4.0/quality/BUGS.md << 'EOF'
# Bug Tracker

### BUG-001: Test bug from sibling run
**Severity:** HIGH
EOF
```

### Expected outcome

- With empty `previous_runs/`, Phase 0b SHOULD consult sibling directory
- Current behavior (BUG-M5): Phase 0b skips because `previous_runs/` exists
- Document whether SKILL.md instructions produce correct behavior in this scenario

### Test steps

1. Create the directory structure above
2. Simulate Phase 0 execution following SKILL.md instructions exactly
3. Verify whether Phase 0b activates or silently skips
4. Document BUG-M5 confirmation or rejection

---

## Group 7: Functional Tests Pass

**Linked use cases:** All
**Linked requirements:** All

### Setup

All artifacts must be generated (Phase 2 complete).

### Expected outcome

- `bash quality/test_functional.sh` exits 0
- All tests pass OR only known-bug tests fail with expected FAIL messages

### Test steps

1. Run `bash quality/test_functional.sh`
2. Count pass/fail/skip
3. Verify all FAILs correspond to confirmed bugs (BUG-H1, BUG-H2, BUG-M5, BUG-L6, Finding 9, Finding 3, REQ-008)
4. Report test count and pass rate

---

## Integration Results Template

After running all groups, write results to `quality/results/integration-results.json`:

```json
{
  "schema_version": "1.1",
  "skill_version": "1.4.1",
  "date": "YYYY-MM-DD",
  "project": "quality-playbook",
  "recommendation": "SHIP | FIX BEFORE MERGE | BLOCK",
  "groups": [
    {"group": 1, "name": "Gate Conformance on Known-Good Artifacts", "use_cases": ["UC-03"], "result": "pass|fail|skipped", "tests_passed": 0, "tests_failed": 0, "notes": ""},
    {"group": 2, "name": "Gate Failure on Missing Artifacts", "use_cases": ["UC-03"], "result": "pass|fail|skipped", "tests_passed": 0, "tests_failed": 0, "notes": ""},
    {"group": 3, "name": "JSON Validation with Malformed tdd-results.json", "use_cases": ["UC-03"], "result": "pass|fail|skipped", "tests_passed": 0, "tests_failed": 0, "notes": ""},
    {"group": 4, "name": "Path With Spaces in Repo Argument", "use_cases": ["UC-03"], "result": "pass|fail|skipped", "tests_passed": 0, "tests_failed": 0, "notes": ""},
    {"group": 5, "name": "Version Stamp Consistency End-to-End", "use_cases": ["UC-04"], "result": "pass|fail|skipped", "tests_passed": 0, "tests_failed": 0, "notes": ""},
    {"group": 6, "name": "Phase 0b Activation Condition Test", "use_cases": ["UC-05"], "result": "pass|fail|skipped", "tests_passed": 0, "tests_failed": 0, "notes": ""},
    {"group": 7, "name": "Functional Tests Pass", "use_cases": ["UC-01", "UC-02", "UC-03", "UC-04", "UC-05"], "result": "pass|fail|skipped", "tests_passed": 0, "tests_failed": 0, "notes": ""}
  ],
  "summary": {"total_groups": 7, "passed": 0, "failed": 0, "skipped": 0},
  "uc_coverage": {
    "UC-01": "covered_pass|covered_fail|not_mapped",
    "UC-02": "covered_pass|covered_fail|not_mapped",
    "UC-03": "covered_pass|covered_fail|not_mapped",
    "UC-04": "covered_pass|covered_fail|not_mapped",
    "UC-05": "covered_pass|covered_fail|not_mapped"
  }
}
```
