# BUG-L20: Patch Existence Uses Aggregate Count Instead of Per-Bug Iteration
<!-- Quality Playbook v1.4.1 — Bug Writeup — 2026-04-16 -->

## Summary

The gate enforces two parallel contracts ("every confirmed bug must have a TDD log" and "every confirmed bug must have a regression-test patch") using different implementation strategies. The TDD log check correctly iterates per bug ID, verifying each specific bug has its log. The patch check counts all patches in aggregate, only verifying the total count matches `bug_count`. The aggregate approach allows a wrong set of patches (e.g., duplicates for some bugs, missing for others) to pass the gate check.

## Spec Reference

REQ-023 (Tier 3): "Patch existence check must iterate per-bug ID to match the per-bug iteration pattern used by TDD log checks — aggregate count allows wrong-set patches to produce false PASS." SKILL.md artifact contract table: `quality/patches/BUG-NNN-regression-test.patch` required for every confirmed bug.

## The Code

```bash
# quality_gate.sh:316-345 — TDD log check: CORRECT per-bug iteration
for bid in $bug_ids; do
    if [ -f "${q}/results/${bid}.red.log" ]; then
        red_found=$((red_found + 1))
        ...

# quality_gate.sh:562-588 — Patch check: INCORRECT aggregate count
reg_patch_count=$(ls ${q}/patches/BUG-*-regression*.patch 2>/dev/null | wc -l | tr -d ' ')
...
if [ "$reg_patch_count" -ge "$bug_count" ]; then
    pass "${reg_patch_count} regression-test patch(es) for ${bug_count} bug(s)"
```

## Observable Consequence

Concrete false-pass scenario: 2 confirmed bugs (BUG-H1, BUG-M3). Patches present: `BUG-H1-regression-test.patch` and `BUG-H1-regression-test-v2.patch` (duplicate due to agent error). `BUG-M3-regression-test.patch` absent.

- `reg_patch_count = 2` (two patches found, even though both are for BUG-H1)
- `bug_count = 2`
- `[ "$reg_patch_count" -ge "$bug_count" ]` → `2 >= 2` → **PASS**

The gate reports "2 regression-test patch(es) for 2 bug(s)" — BUG-M3 has no patch, but the gate doesn't detect this.

## The Fix

```diff
--- a/quality_gate.sh
+++ b/quality_gate.sh
@@ -562,13 +562,20 @@ check_repo() {
     echo "[Patches]"
     if [ "$bug_count" -gt 0 ]; then
-        local reg_patch_count=0 fix_patch_count=0
-        if [ -d "${q}/patches" ]; then
-            reg_patch_count=$(ls ${q}/patches/BUG-*-regression*.patch 2>/dev/null | wc -l | tr -d ' ')
-            fix_patch_count=$(ls ${q}/patches/BUG-*-fix*.patch 2>/dev/null | wc -l | tr -d ' ')
-        fi
-        if [ "$reg_patch_count" -ge "$bug_count" ]; then
-            pass "${reg_patch_count} regression-test patch(es) for ${bug_count} bug(s)"
+        local reg_patch_count=0 fix_patch_count=0 reg_patch_missing=0
+        for bid in $bug_ids; do
+            if find "${q}/patches" -name "${bid}-regression*.patch" -print -quit 2>/dev/null | grep -q .; then
+                reg_patch_count=$((reg_patch_count + 1))
+            else
+                reg_patch_missing=$((reg_patch_missing + 1))
+            fi
+        done
+        if [ "$reg_patch_missing" -eq 0 ] && [ "$reg_patch_count" -gt 0 ]; then
+            pass "${reg_patch_count} regression-test patch(es) for ${bug_count} bug(s)"
```

This changes the patch section to iterate `bug_ids` per-bug, matching the TDD log check pattern. Each specific bug's regression-test patch is verified by name, eliminating the false-pass from duplicate or misnamed patches.
