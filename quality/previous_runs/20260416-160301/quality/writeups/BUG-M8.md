# BUG-M8: Systemic nullglob vulnerability with ls | wc -l patterns

**Severity:** MEDIUM  
**File:Line:** `quality_gate.sh:152-153, 331, 567-568, 595`  
**Date confirmed:** 2026-04-16  
**TDD verdict:** TDD verified

---

## 1. Description

Multiple artifact-counting operations use the pattern `ls ${q}/path/*glob* 2>/dev/null | wc -l` with unquoted globs. Under `nullglob` shell option (active by default in many zsh configurations including macOS), an unmatched glob expands to empty words. The `ls` command then receives no arguments and lists the current working directory. The `2>/dev/null` suppresses only `ls`'s error output — it does NOT suppress stdout. `wc -l` counts lines in the current directory listing, producing a nonzero count even when no matching files exist. Affected artifact checks: spec_audits triage file presence (line 152), spec_audits auditor file presence (line 153), patch counting (lines 567-568), writeup counting (line 595). Additionally, line 331 uses `if ls ${q}/patches/${bid}-fix*.patch &>/dev/null` where `&>/dev/null` suppresses all output but under nullglob `ls` with no args returns exit code 0 (success), causing the gate to spuriously require a green-phase log even when no fix patch exists.

## 2. Spec Basis

**REQ-002 (Tier 3)** and **REQ-014 (Tier 3):** Consistent, reliable artifact detection across shell configurations. The gate uses `find ... -print -quit` for language detection at lines 449-454, showing the developer was aware of the robust pattern. The `ls | wc -l` pattern is a systemic technical debt in the counting operations.

## 3. Code Location

Vulnerable locations in `quality_gate.sh`:
```bash
# Line 152 (spec_audits triage):
triage_count=$(ls ${q}/spec_audits/*triage* 2>/dev/null | wc -l | tr -d ' ')
# Line 153 (spec_audits auditor):
auditor_count=$(ls ${q}/spec_audits/*auditor* 2>/dev/null | wc -l | tr -d ' ')
# Line 331 (fix patch check):
if ls ${q}/patches/${bid}-fix*.patch &>/dev/null; then
# Line 567 (regression patches):
reg_patch_count=$(ls ${q}/patches/BUG-*-regression*.patch 2>/dev/null | wc -l | tr -d ' ')
# Line 568 (fix patches):
fix_patch_count=$(ls ${q}/patches/BUG-*-fix*.patch 2>/dev/null | wc -l | tr -d ' ')
# Line 595 (writeups):
writeup_count=$(ls ${q}/writeups/BUG-*.md 2>/dev/null | wc -l | tr -d ' ')
```

## 4. Regression Test

Function: `test_BUG_M8_nullglob_ls_counting` in `quality/test_regression.sh`

```bash
# Check for the specific vulnerable pattern at line 567
line567=$(sed -n '567p' "$gate")
if echo "$line567" | grep -q 'ls \${q}/patches/BUG-\*-regression\*'; then
    echo "BUG CONFIRMED: Unquoted ls-glob counting patterns present"
fi
```

## 5. Fix Patch

```diff
--- a/quality_gate.sh
+++ b/quality_gate.sh
@@ -149,8 +149,10 @@ check_artifacts() {
     if [ -d "${q}/spec_audits" ]; then
         local triage_count auditor_count
-        triage_count=$(ls ${q}/spec_audits/*triage* 2>/dev/null | wc -l | tr -d ' ')
-        auditor_count=$(ls ${q}/spec_audits/*auditor* 2>/dev/null | wc -l | tr -d ' ')
+        triage_count=$(find "${q}/spec_audits" -maxdepth 1 -name '*triage*' 2>/dev/null | wc -l | tr -d ' ')
+        auditor_count=$(find "${q}/spec_audits" -maxdepth 1 -name '*auditor*' 2>/dev/null | wc -l | tr -d ' ')

@@ -329,7 +331,7 @@ check_artifacts() {
-            if ls ${q}/patches/${bid}-fix*.patch &>/dev/null; then
+            if [ -n "$(find "${q}/patches" -maxdepth 1 -name "${bid}-fix*.patch" 2>/dev/null | head -1)" ]; then

@@ -563,9 +565,9 @@ check_artifacts() {
         if [ -d "${q}/patches" ]; then
-            reg_patch_count=$(ls ${q}/patches/BUG-*-regression*.patch 2>/dev/null | wc -l | tr -d ' ')
-            fix_patch_count=$(ls ${q}/patches/BUG-*-fix*.patch 2>/dev/null | wc -l | tr -d ' ')
+            reg_patch_count=$(find "${q}/patches" -maxdepth 1 -name 'BUG-*-regression*.patch' 2>/dev/null | wc -l | tr -d ' ')
+            fix_patch_count=$(find "${q}/patches" -maxdepth 1 -name 'BUG-*-fix*.patch' 2>/dev/null | wc -l | tr -d ' ')

@@ -590,7 +592,7 @@ check_artifacts() {
         if [ -d "${q}/writeups" ]; then
-            writeup_count=$(ls ${q}/writeups/BUG-*.md 2>/dev/null | wc -l | tr -d ' ')
+            writeup_count=$(find "${q}/writeups" -maxdepth 1 -name 'BUG-*.md' 2>/dev/null | wc -l | tr -d ' ')
```

## 6. TDD Verification

**Red phase** (`quality/results/BUG-M8.red.log`):
```
Line 567 (vulnerable): reg_patch_count=$(ls ${q}/patches/BUG-*-regression*.patch 2>/dev/null | wc -l | tr -d ' ')
Line 331 (vulnerable): if ls ${q}/patches/${bid}-fix*.patch &>/dev/null; then
BUG CONFIRMED: Unquoted ls-glob counting patterns present — vulnerable to nullglob
RESULT: FAIL
```
Exit code: 1. Test fails on unpatched code — confirms vulnerable patterns exist at both tested locations.

**Green phase** (`quality/results/BUG-M8.green.log`):
```
BUG FIXED: ls-glob counting patterns replaced with nullglob-safe find/count
RESULT: PASS
```
After applying fix patch, vulnerable ls-glob patterns are replaced with find-based counting that is immune to nullglob expansion.
