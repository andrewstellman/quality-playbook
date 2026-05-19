# BUG-L23: integration-results.json groups[].result Enum Not Validated
<!-- Quality Playbook v1.4.1 — Bug Writeup — 2026-04-16 -->

## Summary

The quality gate validates `tdd-results.json` verdict values at lines 294-296 (checking "TDD verified" vs "confirmed open") but performs NO equivalent validation for `integration-results.json` groups[].result enum values. SKILL.md:1273 defines four valid result values ("pass", "fail", "skipped", "error") and SKILL.md:1277 mandates post-write validation. An agent generating `"result": "PASS"` (uppercase), `"result": "OK"`, or any non-canonical value passes gate validation, providing false conformance assurance to CI tools that depend on the machine-readable contract.

## Spec Reference

REQ-026 (Tier 3): "Gate must validate integration-results.json groups[].result values against the enum defined in SKILL.md:1273 — valid values are 'pass', 'fail', 'skipped', 'error' — consistent with how tdd-results.json verdict values are validated at quality_gate.sh:294-296."

SKILL.md:1273: Defines valid result values as "pass", "fail", "skipped", "error"; also defines uc_coverage values as "covered_pass", "covered_fail", "not_mapped".

SKILL.md:1275: "Runner scripts and CI tools should read the sidecar JSON for results rather than grepping the Markdown report." (Machine-readable contract expectation.)

SKILL.md:1277: "After writing, re-read the file and validate it conforms to the schema above."

## The Code

```bash
# quality_gate.sh:294-296 — tdd verdict enum IS validated
if [[ "$verdict" != "TDD verified" && "$verdict" != "confirmed open" ]]; then
    gate_fail "tdd-results.json bug $bug_id: verdict must be 'TDD verified' or 'confirmed open'"
fi
```

```bash
# quality_gate.sh:389-436 — integration JSON validation block (ABSENT)
# groups[].result enum values: NOT CHECKED
# uc_coverage value enum: NOT CHECKED
# Only checked: root key presence, recommendation enum, date format, schema_version
```

The asymmetry is systematic: tdd-results.json gets deep per-bug validation including enum checks; integration-results.json gets shallow root-key validation only.

## Observable Consequence

1. Agent writes `"result": "PASS"` (wrong case). Gate passes. CI tool checks `if result == "pass"` — fails silently.
2. Agent writes `"result": "OK"` (wrong value). Gate passes. Aggregation script expecting canonical values breaks.
3. Agent writes `"uc_coverage": {"UC-01": "fail"}` instead of `"covered_fail"`. Gate passes. Downstream tooling cannot distinguish "test exists but code broken" from "test missing."

## The Fix

```diff
--- a/quality_gate.sh
+++ b/quality_gate.sh
@@ integration validation block @@
+# Validate groups[].result enum values (BUG-L23 fix)
+# SKILL.md:1273: valid values are "pass", "fail", "skipped", "error"
+valid_result_values=("pass" "fail" "skipped" "error")
+int_result_check=$(grep -oE '"result"[[:space:]]*:[[:space:]]*"[^"]*"' "$int_json" | \
+    grep -oE '"[^"]*"$' | tr -d '"')
+while IFS= read -r result_val; do
+    [ -z "$result_val" ] && continue
+    valid=0
+    for v in "${valid_result_values[@]}"; do
+        [ "$result_val" = "$v" ] && valid=1 && break
+    done
+    if [ "$valid" -eq 0 ]; then
+        gate_fail "integration-results.json: groups[].result value '$result_val' not in valid enum (pass, fail, skipped, error)"
+    fi
+done <<< "$int_result_check"
```

Full patch in `quality/patches/BUG-L23-fix.patch`.
