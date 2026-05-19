# BUG-L6: json_str_val silently returns empty for non-string values

**Severity:** LOW  
**File:Line:** `quality_gate.sh:81-85` (`json_str_val` function); caller at line 236  
**Date confirmed:** 2026-04-16  
**TDD verdict:** TDD verified

---

## 1. Description

`json_str_val()` returns empty string for both "key absent" and "key exists with non-string value." When `schema_version` is a number (`"schema_version": 1.1`), the caller at line 236 reports `"schema_version is 'missing', expected '1.1'"` when the actual problem is a wrong type. A developer debugging this gate failure would search for a missing field when the field exists but has the wrong type.

## 2. Spec Basis

**REQ-007 (Tier 3):** "For `"schema_version": 1.1` (number) → return a value distinguishable from empty string indicating 'key exists, non-string value'."

**CONTRACTS.md item 29:** "`json_str_val` cannot distinguish 'key absent' from 'key with non-string value' — both return empty string."

## 3. Code Location

`quality_gate.sh:81-85`:
```bash
json_str_val() {
    local file="$1" key="$2"
    grep -o "\"${key}\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" "$file" 2>/dev/null \
        | head -1 | sed 's/.*: *"\([^"]*\)"/\1/'
}
```

The grep matches only quoted string values (`"key": "value"`). If the value is a number (`"key": 1.1`), grep finds nothing and the function returns empty — indistinguishable from a missing key.

## 4. Regression Test

Function: `test_BUG_L6_json_str_val_non_string_empty` in `quality/test_regression.sh`

```bash
# JSON with number value for schema_version
cat > "$tmpfile" <<'EOF'
{"schema_version": 1.1, "skill_version": "1.4.1"}
EOF
result=$(json_str_val_buggy "$tmpfile" "schema_version")
[ -z "$result" ] && echo "BUG CONFIRMED — returns empty for non-string value"
```

## 5. Fix Patch

```diff
--- a/quality_gate.sh
+++ b/quality_gate.sh
@@ -80,7 +80,15 @@ json_has_key() {
 # Helper: extract a string value for a key (first occurrence)
+# Returns empty string if key is absent.
+# Returns __NOT_STRING__ if key exists but value is not a quoted string.
 json_str_val() {
     local file="$1" key="$2"
-    grep -o "\"${key}\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" "$file" 2>/dev/null \
-        | head -1 | sed 's/.*: *"\([^"]*\)"/\1/'
+    local quoted_result
+    quoted_result=$(grep -o "\"${key}\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" "$file" 2>/dev/null \
+        | head -1 | sed 's/.*: *"\([^"]*\)"/\1/')
+    if [ -n "$quoted_result" ]; then
+        echo "$quoted_result"
+        return 0
+    fi
+    if grep -q "\"${key}\"[[:space:]]*:" "$file" 2>/dev/null; then
+        echo "__NOT_STRING__"
+    fi
 }
```

## 6. TDD Verification

**Red phase** (`quality/results/BUG-L6.red.log`):
```
BUG CONFIRMED: json_str_val returned empty for number-typed 'schema_version'
Caller would report: "schema_version is 'missing', expected '1.1'"
RESULT: FAIL
```
Exit code: 1. Test fails on unpatched code — confirms json_str_val returns empty for number values.

**Green phase** (`quality/results/BUG-L6.green.log`):
```
Result for number-typed schema_version: "__NOT_STRING__"
PASS: Fixed function returns __NOT_STRING__ for number value
PASS: Returns empty for absent key
PASS: Returns string value correctly
```
After applying fix patch, json_str_val correctly distinguishes: absent (empty), non-string ("__NOT_STRING__"), and string (actual value).
