# BUG-L19: Summary Sub-Key Check Uses Weak `json_has_key` While Per-Bug Check Uses Stronger `json_key_count`
<!-- Quality Playbook v1.4.1 — Bug Writeup — 2026-04-16 -->

## Summary

The gate's TDD sidecar JSON validation uses two different helper functions for the same logical operation ("does this JSON file contain required field X?"), with different false-positive rates. Summary sub-key presence is checked with `json_has_key` (lines 259-265), which matches a key name anywhere in the file. Per-bug field presence is checked with `json_key_count` (lines 239-248), which uses a colon-anchored pattern that only matches actual JSON keys. This inconsistency means summary key validation is weaker than per-bug key validation, even though they enforce the same type of requirement.

## Spec Reference

REQ-022 (Tier 3): "Gate summary sub-key checks must use `json_key_count` for consistency with per-bug field checks — both enforce the same 'required JSON key present' contract and should use the same validator." Internal gate consistency requirement derived from parity analysis.

Behavioral contract violated: "All JSON field presence checks within the same validation section must use the same helper function to provide uniform false-positive guarantees."

## The Code

```bash
# quality_gate.sh:259-265 — WEAK: uses json_has_key (no colon anchor)
for skey in total verified confirmed_open red_failed green_failed; do
    if json_has_key "$json_file" "$skey"; then
        pass "summary has '${skey}'"
    else
        fail "summary missing '${skey}' count"
    fi
done

# quality_gate.sh:239-248 — STRONG: uses json_key_count (colon-anchored)
for field in id requirement red_phase green_phase verdict fix_patch_present writeup_path; do
    local fcount
    fcount=$(json_key_count "$json_file" "$field")
    if [ "$fcount" -ge "$bug_count" ]; then
        pass "per-bug field '${field}' present (${fcount}x)"
    ...
done
```

The root cause: `json_has_key` (line 77) uses `grep -q "\"${key}\""` while `json_key_count` (line 90) uses `grep -c "\"${key}\"[[:space:]]*:"`. The per-bug check correctly uses the colon-anchored pattern; the summary check uses the bare pattern.

## Observable Consequence

A `tdd-results.json` where summary key names appear in string values (e.g., `"notes": "total confirmed, all verified"`) passes the summary check via `json_has_key` even though no actual `"total":` key exists in the summary object. The gate reports `PASS: summary has 'total'` — spuriously. In normal usage this false positive is unlikely because agents follow the template. But the structural inconsistency means the summary check provides weaker guarantees than the per-bug check, even though they enforce the same "required field present" contract.

## The Fix

```diff
--- a/quality_gate.sh
+++ b/quality_gate.sh
@@ -259,7 +259,10 @@ check_repo() {
             # Summary must include all 5 required keys
             for skey in total verified confirmed_open red_failed green_failed; do
-                if json_has_key "$json_file" "$skey"; then
+                local scount
+                scount=$(json_key_count "$json_file" "$skey")
+                if [ "${scount:-0}" -gt 0 ]; then
                     pass "summary has '${skey}'"
                 else
                     fail "summary missing '${skey}' count"
```

This changes the summary check to use `json_key_count` (colon-anchored), matching the per-bug field check pattern. The stronger validator is already in the same file — this fix just uses it consistently.
