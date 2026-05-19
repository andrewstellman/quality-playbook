# BUG-M15: No recheck-results.json validation in quality_gate.sh

**Severity:** MEDIUM  
**File:Line:** `quality_gate.sh` (entire check_repo function, lines 94-673 — absence finding)  
**Date confirmed:** 2026-04-16  
**TDD verdict:** TDD verified

---

## 1. Description

`quality_gate.sh` has zero validation for `recheck-results.json` or `recheck-summary.md` anywhere in its 723 lines. The SKILL.md artifact contract table (lines 117-118) documents both files as required artifacts when recheck mode runs. An agent that runs recheck mode and writes a `recheck-results.json` with wrong status values, missing required fields, wrong `schema_version`, or partial bug coverage will pass all gate checks without any error or warning.

By contrast, the gate validates `tdd-results.json` exhaustively at lines 221-305: required root keys, enum checks per bug, date validation, summary counts. The same rigor is absent for the structurally similar `recheck-results.json`. Users cannot rely on the gate to detect recheck artifact quality — the gate provides false assurance that recheck artifacts are correct when it simply does not check them at all.

## 2. Spec Basis

**REQ-018 (Tier 3):** The quality gate must validate `recheck-results.json` and `recheck-summary.md` conformance when a recheck mode session has been run, applying the same rigor as `tdd-results.json` validation.

The SKILL.md artifact contract table documents `recheck-results.json` and `recheck-summary.md` as conditional artifacts required when recheck mode runs. The gate enforces all other entries in the artifact contract table but omits the recheck entries entirely.

## 3. Code Location

Absence finding — no recheck validation exists in `quality_gate.sh`:
```bash
# grep -n 'recheck' quality_gate.sh
# (no output — zero matches)
```

Required artifacts per SKILL.md artifact contract table:
- `recheck-results.json` — Required: If recheck mode run; schema_version "1.0"
- `recheck-summary.md` — Required: If recheck mode run

For comparison, tdd-results.json deep validation (present, correct):
```bash
# Lines 221-305 in quality_gate.sh validate:
# - Required root keys (schema_version, skill_version, date, project, bugs, summary)
# - schema_version value ("1.1")
# - Per-bug required fields (id, requirement, red_phase, green_phase, verdict)
# - Date format validation and future-date check
# - Summary count accuracy
```

## 4. Regression Test

Function: `test_BUG_M15_no_recheck_validation` in `quality/test_regression.sh`

```bash
if grep -q 'recheck' "$gate"; then
    echo "BUG FIXED: quality_gate.sh now contains recheck validation"
    return 0
else
    echo "BUG CONFIRMED: quality_gate.sh has no validation for recheck-results.json"
    return 1
fi
```

## 5. Fix Patch

```diff
--- a/quality_gate.sh
+++ b/quality_gate.sh
@@ -436,6 +436,48 @@ check_repo() {
     fi

+    # --- Recheck sidecar JSON — validation (SKILL.md artifact contract) ---
+    echo "[Recheck Sidecar JSON]"
+    local rj="${q}/results/recheck-results.json"
+    local rs="${q}/results/recheck-summary.md"
+    if [ -f "$rj" ]; then
+        pass "recheck-results.json exists"
+        for key in schema_version skill_version date project bugs summary; do
+            json_has_key "$rj" "$key" && pass "recheck has '${key}'" || fail "recheck missing root key '${key}'"
+        done
+        local rsv
+        rsv=$(json_str_val "$rj" "schema_version")
+        [ "$rsv" = "1.0" ] && pass "recheck schema_version is '1.0'" || fail "recheck schema_version is '${rsv:-missing}', expected '1.0'"
+        local rdate
+        rdate=$(json_str_val "$rj" "date")
+        if [ -n "$rdate" ]; then
+            if echo "$rdate" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'; then
+                local today_rck
+                today_rck=$(date +%Y-%m-%d)
+                if [[ "$rdate" > "$today_rck" ]]; then
+                    fail "recheck-results.json date '${rdate}' is in the future"
+                else
+                    pass "recheck-results.json date '${rdate}' is valid"
+                fi
+            else
+                fail "recheck-results.json date '${rdate}' is not ISO 8601 (YYYY-MM-DD)"
+            fi
+        fi
+        if [ -f "$rs" ]; then
+            pass "recheck-summary.md exists"
+        else
+            fail "recheck-summary.md missing (required companion to recheck-results.json)"
+        fi
+    else
+        info "recheck-results.json not present (only required when recheck mode was run)"
+    fi
+
     # --- Use cases in REQUIREMENTS.md (benchmark 43, 48) ---
```

## 6. TDD Verification

**Red phase** (`quality/results/BUG-M15.red.log`):
```
BUG CONFIRMED: quality_gate.sh has no validation for recheck-results.json or recheck-summary.md
RESULT: FAIL
```
Exit code: 1. Test fails on unpatched code — confirms complete absence of recheck validation.

**Green phase** (`quality/results/BUG-M15.green.log`):
```
BUG FIXED: quality_gate.sh now contains recheck validation
RESULT: PASS
```
After applying fix patch, gate validates recheck artifacts with the same rigor as tdd-results.json.

## 7. Cross-References

- Gap iteration triage: `quality/spec_audits/gap_triage.md` — Finding G4
- Code review: `quality/code_reviews/gap_pass2_requirement_verification.md`
- Spec audit: `quality/spec_audits/gap_auditor_c.md` (lists specific recheck validation gaps: wrong status, missing evidence field, wrong schema_version, partial bug coverage)
