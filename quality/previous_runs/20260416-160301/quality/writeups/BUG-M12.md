# BUG-M12: ls-glob in test file extension detection

**Severity:** MEDIUM  
**File:Line:** `quality_gate.sh:479`  
**Date confirmed:** 2026-04-16  
**TDD verdict:** TDD verified

---

## 1. Description

`quality_gate.sh:479` uses `func_test=$(ls ${q}/test_functional.* 2>/dev/null | head -1)` to detect the test functional file for extension checking. This ls-glob pattern is vulnerable to the nullglob shell option (active by default in many zsh/macOS environments). Under nullglob, an unmatched glob expands to empty, so `ls` receives no arguments and lists the current working directory. `head -1` then returns the first filename from the CWD listing — a file with no relationship to the test suite. Downstream, the gate extracts the extension from this wrong filename and compares it to the detected project language, producing a false extension mismatch error even when the actual test file exists and has the correct extension.

The irony is that the correct fix pattern — `find ... -print -quit` — is already used in the same function block at lines 486–495 for language detection, just 7 lines after the vulnerable ls-glob at line 479.

## 2. Spec Basis

**REQ-015 (Tier 3):** Test file extension detection must use find-based methods rather than ls-glob to ensure correct behavior across all shell configurations including zsh nullglob environments.

This is the same vulnerability class as BUG-M8 (lines 152-153, 331, 567-568, 595). BUG-M12 was identified in the gap iteration as a separate instance not covered by BUG-M8's scope.

## 3. Code Location

Vulnerable location in `quality_gate.sh`:
```bash
# Line 479 (test file extension detection):
func_test=$(ls ${q}/test_functional.* 2>/dev/null | head -1)
reg_test=$(ls ${q}/test_regression.* 2>/dev/null | head -1)

# Correct pattern already used 7 lines later at line 486:
if find "${repo_dir}" -maxdepth 3 ... -name '*.go' -print -quit 2>/dev/null | grep -q .; then
```

## 4. Regression Test

Function: `test_BUG_M12_test_file_ext_ls_glob_false_positive` in `quality/test_regression.sh`

```bash
if grep -qE 'func_test=\$\(ls [^)]*test_functional\.\*' "$gate"; then
    echo "BUG CONFIRMED: quality_gate.sh uses ls-glob for func_test assignment"
    return 1
fi
```

## 5. Fix Patch

```diff
--- a/quality_gate.sh
+++ b/quality_gate.sh
@@ -476,8 +476,8 @@ check_repo() {
     echo "[Test File Extension]"
     local func_test reg_test
-    func_test=$(ls ${q}/test_functional.* 2>/dev/null | head -1)
-    reg_test=$(ls ${q}/test_regression.* 2>/dev/null | head -1)
+    func_test=$(find "${q}" -maxdepth 1 -name 'test_functional.*' -print -quit 2>/dev/null)
+    reg_test=$(find "${q}" -maxdepth 1 -name 'test_regression.*' -print -quit 2>/dev/null)
```

## 6. TDD Verification

**Red phase** (`quality/results/BUG-M12.red.log`):
```
BUG CONFIRMED: quality_gate.sh uses ls-glob for func_test assignment (vulnerable to nullglob)
RESULT: FAIL
```
Exit code: 1. Test fails on unpatched code — confirms ls-glob pattern exists at line 479.

**Green phase** (`quality/results/BUG-M12.green.log`):
```
BUG FIXED: func_test assignment uses find-based detection
RESULT: PASS
```
After applying fix patch, find-based detection correctly returns empty when no test file exists, and the actual filename when it does.

## 7. Cross-References

- Related: BUG-M8 (same vulnerability class, different lines)
- Related: BUG-M13 (same vulnerability class, different location)
- Gap iteration triage: `quality/spec_audits/gap_triage.md` — Finding G1
- Code review: `quality/code_reviews/gap_pass1_structural.md`
