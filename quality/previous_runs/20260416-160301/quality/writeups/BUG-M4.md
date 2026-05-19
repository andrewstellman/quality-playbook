# BUG-M4: test_regression.* not checked by gate despite artifact contract

**Severity:** MEDIUM  
**File:Line:** `quality_gate.sh:476-533` (`[Test File Extension]` section); artifact contract at `SKILL.md:88-119`  
**Date confirmed:** 2026-04-16  
**TDD verdict:** TDD verified

---

## 1. Description

The gate checks for the existence of `quality/test_regression.*` only incidentally (in the extension check at line 479-480, where it reads the filename to validate the extension). It does not enforce existence as a gate condition when bugs are confirmed. The artifact contract at SKILL.md lines 88-119 designates `quality/test_regression.*` as "Required: If bugs found." The gate at lines 562-588 checks for regression test PATCHES (`quality/patches/BUG-NNN-regression-test.patch`) but not for the regression test SOURCE FILE. A run with confirmed bugs that produces patches but no `test_regression.*` file passes the gate, violating the artifact contract.

## 2. Spec Basis

**REQ-004 (Tier 2):** "Gate must FAIL when `bug_count > 0` and no `quality/test_regression.*` file exists."

Artifact contract table at SKILL.md line 94: `quality/test_regression.*` — "Required: If bugs found."

## 3. Code Location

`quality_gate.sh:562-588` — Patches section. Checks for `BUG-NNN-regression-test.patch` files but has no check for `test_regression.*` source file. The extension check at lines 479-480 incidentally reads the filename but does not enforce existence when bug_count > 0.

## 4. Regression Test

Function: `test_BUG_M4_gate_missing_regression_file_check` in `quality/test_regression.sh`

```bash
# Set up minimal test environment: bugs present but no test_regression.* file
tmpdir=$(mktemp -d)
# Create BUGS.md with one bug, but no test_regression.* file
cat > "${q}/BUGS.md" <<'EOF'
### BUG-001
Description: test bug
Severity: LOW
EOF
# Verify gate does NOT specifically FAIL for missing test_regression.*
gate_output=$(bash "$gate" --general "$tmpdir" 2>&1 || true)
echo "$gate_output" | grep -qiE "FAIL.*test_regression|test_regression.*FAIL" || echo "BUG CONFIRMED"
```

## 5. Fix Patch

```diff
--- a/quality_gate.sh
+++ b/quality_gate.sh
@@ -560,6 +560,18 @@ info() { echo "  INFO: $1"; }
     # --- Patches for confirmed bugs (benchmark 44) ---
     echo "[Patches]"
     if [ "$bug_count" -gt 0 ]; then
+        # Regression test file — required when bugs exist (SKILL.md artifact contract)
+        local reg_test_file
+        reg_test_file=$(ls "${q}"/test_regression.* 2>/dev/null | head -1)
+        if [ -n "$reg_test_file" ]; then
+            pass "test_regression.* exists (${bug_count} confirmed bugs require it)"
+        else
+            if [ "$STRICTNESS" = "benchmark" ]; then
+                fail "test_regression.* missing — required when bugs exist (SKILL.md artifact contract)"
+            else
+                warn "test_regression.* missing — required when bugs exist (SKILL.md artifact contract)"
+            fi
+        fi
+
         local reg_patch_count=0 fix_patch_count=0
```

## 6. TDD Verification

**Red phase** (`quality/results/BUG-M4.red.log`):
```
BUG CONFIRMED: gate did not FAIL for missing test_regression.* when bug_count > 0
Gate exit: 0
RESULT: FAIL
```
Exit code: 1. Test fails on unpatched code — confirms gate does not check for test_regression.* file.

**Green phase** (`quality/results/BUG-M4.green.log`):
```
BUG FIXED: gate correctly FAILs for missing test_regression.*
RESULT: PASS
```
After applying fix patch, the gate explicitly FAILs when bugs exist but no test_regression.* file is present.
