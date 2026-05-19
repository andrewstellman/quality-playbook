# BUG-M13: ls-glob in code_reviews directory check

**Severity:** MEDIUM  
**File:Line:** `quality_gate.sh:143`  
**Date confirmed:** 2026-04-16  
**TDD verdict:** TDD verified

---

## 1. Description

`quality_gate.sh:143` uses `[ -n "$(ls ${q}/code_reviews/*.md 2>/dev/null)" ]` to verify that code review files were written to the `code_reviews/` directory. This ls-glob pattern is vulnerable to the nullglob shell option (active by default in many zsh/macOS environments). Under nullglob, an unmatched glob (when `code_reviews/` is empty) expands to empty, so `ls` receives no arguments and lists the current working directory. The subshell returns a non-empty string (the CWD listing), and the `-n` test passes — reporting PASS for a completely empty code_reviews/ directory.

This creates a dangerous false positive: if a playbook session terminates early (context limit, crash) after creating `code_reviews/` but before writing any review content, the gate reports code reviews as present when none exist. The quality artifact appears complete when it is entirely absent.

## 2. Spec Basis

**REQ-016 (Tier 3):** Code reviews directory content detection must use find-based methods rather than ls-glob to ensure correct behavior across all shell configurations including zsh nullglob environments.

This is the same vulnerability class as BUG-M8 (lines 152-153, 331, 567-568, 595). BUG-M13 was identified in the gap iteration as a separate instance not covered by BUG-M8's scope.

## 3. Code Location

Vulnerable location in `quality_gate.sh`:
```bash
# Line 142-147 (code_reviews check):
if [ -d "${q}/code_reviews" ] && [ -n "$(ls ${q}/code_reviews/*.md 2>/dev/null)" ]; then
    pass "code_reviews/ has .md files"
else
    fail "code_reviews/ missing or empty"
fi
```

## 4. Regression Test

Function: `test_BUG_M13_code_reviews_ls_glob_false_pass` in `quality/test_regression.sh`

```bash
if grep -qE '\$\(ls [^)]*code_reviews/\*\.md' "$gate"; then
    echo "BUG CONFIRMED: quality_gate.sh:143 uses ls-glob for code_reviews detection"
    return 1
fi
```

## 5. Fix Patch

```diff
--- a/quality_gate.sh
+++ b/quality_gate.sh
@@ -142,7 +142,7 @@ check_repo() {
-    if [ -d "${q}/code_reviews" ] && [ -n "$(ls ${q}/code_reviews/*.md 2>/dev/null)" ]; then
+    if [ -d "${q}/code_reviews" ] && find "${q}/code_reviews" -maxdepth 1 -name '*.md' -print -quit 2>/dev/null | grep -q .; then
         pass "code_reviews/ has .md files"
     else
         fail "code_reviews/ missing or empty"
```

## 6. TDD Verification

**Red phase** (`quality/results/BUG-M13.red.log`):
```
BUG CONFIRMED: quality_gate.sh:143 uses ls-glob for code_reviews detection (vulnerable to nullglob)
RESULT: FAIL
```
Exit code: 1. Test fails on unpatched code — confirms ls-glob pattern exists at line 143.

**Green phase** (`quality/results/BUG-M13.green.log`):
```
BUG FIXED: code_reviews check uses find-based detection
RESULT: PASS
```
After applying fix patch, the find-based check correctly returns false when code_reviews/ is empty, and true only when .md files are actually present.

## 7. Cross-References

- Related: BUG-M8 (same vulnerability class, different lines)
- Related: BUG-M12 (same vulnerability class, different location)
- Gap iteration triage: `quality/spec_audits/gap_triage.md` — Finding G2
- Code review: `quality/code_reviews/gap_pass1_structural.md`
