# BUG-H1: json_has_key false positive — matches key name in string values

**Severity:** HIGH  
**File:Line:** `quality_gate.sh:75-78` (primary); callers at lines 230, 253, 260  
**Date confirmed:** 2026-04-16  
**TDD verdict:** TDD verified

---

## 1. Description

`json_has_key()` uses `grep -q "\"${key}\""` which matches the key name anywhere in the file, including inside string values. A JSON file like `{"field_type": "id", "schema_version": "1.1"}` returns exit 0 (true) from `json_has_key "id"` even though `id` is not a JSON key. The gate then incorrectly passes conformance checks for required fields in `tdd-results.json` when those fields are mentioned only in string values.

## 2. Spec Basis

**REQ-001 (Tier 3):** `json_has_key()` must verify the key appears as an actual JSON key (preceding `:`), not merely as a substring of a string value anywhere in the file.

**CONTRACTS.md item 27:** "`json_has_key` returns exit 0 (false positive) when the key name appears in a string VALUE rather than as a JSON key."

## 3. Code Location

`quality_gate.sh:75-78`:
```bash
json_has_key() {
    local file="$1" key="$2"
    grep -q "\"${key}\"" "$file" 2>/dev/null
}
```

The `grep -q "\"${key}\""` pattern matches any occurrence of `"keyname"` in the file, including inside string values like `"message": "the id field is deprecated"`.

## 4. Regression Test

Function: `test_BUG_H1_json_has_key_false_positive` in `quality/test_regression.sh`

```bash
# JSON where "id" appears only as a string VALUE, not as a key
cat > "$tmpfile" <<'EOF'
{
  "field_type": "id",
  "schema_version": "1.1",
  "project": "quality-playbook"
}
EOF
# json_has_key "id" should return false — "id" is not a JSON key here
# Buggy behavior: returns true because grep finds "id" in the VALUE
```

Red phase: `BUG_SKIP_H1=0 bash quality/test_regression.sh test_BUG_H1_json_has_key_false_positive` — exits 1 (FAIL), confirming bug.

## 5. Fix Patch

```diff
--- a/quality_gate.sh
+++ b/quality_gate.sh
@@ -74,7 +74,8 @@ info() { echo "  INFO: $1"; }
 # Helper: check if a JSON file contains a key at any nesting level
 json_has_key() {
     local file="$1" key="$2"
-    grep -q "\"${key}\"" "$file" 2>/dev/null
+    grep -q "\"${key}\"[[:space:]]*:" "$file" 2>/dev/null
 }
```

The fix adds `[[:space:]]*:` to require a colon after the key name, which is the JSON syntax for key-value pairs. This prevents matching key names that appear as string values.

## 6. TDD Verification

**Red phase** (`quality/results/BUG-H1.red.log`):
```
BUG CONFIRMED: json_has_key returned true for 'id' appearing only in string value
RESULT: FAIL
```
Exit code: 1. Test fails on unpatched code — bug confirmed real.

**Green phase** (`quality/results/BUG-H1.green.log`):
```
PASS: Fixed version correctly returns false for id in string value
PASS: Fixed version correctly detects actual JSON keys
```
After applying fix patch (`grep -q "\"${key}\"[[:space:]]*:"`), the test passes — fix confirmed working.
