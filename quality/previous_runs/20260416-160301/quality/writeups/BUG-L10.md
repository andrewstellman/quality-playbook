# BUG-L10: recheck-results.json uses schema_version 1.0 vs 1.1

**Severity:** LOW  
**File:Line:** `SKILL.md:1965` (recheck template) vs `SKILL.md:128` (tdd template) vs `SKILL.md:156` (integration template)  
**Date confirmed:** 2026-04-16  
**TDD verdict:** confirmed open (no fix patch — spec-primary fix required)

---

## 1. Description

The recheck mode JSON artifact template at SKILL.md line 1965 uses `"schema_version": "1.0"` while all other sidecar JSON artifacts (tdd-results.json at line 128, integration-results.json at line 156) use `"schema_version": "1.1"`. There is no migration note or documentation explaining why recheck uses a different schema version. `quality_gate.sh` does not validate `recheck-results.json` at all (confirmed by grep — no `recheck-results` in the gate script), so there is no mechanical enforcement of conformance.

## 2. Spec Basis

**REQ-009 (Tier 2):** Generated artifacts must include consistent version stamps. Schema version is part of the artifact conformance contract. This is a spec bug — recheck template uses a different schema version with no documented rationale.

## 3. Code Location

`SKILL.md:1965`:
```json
{
  "schema_version": "1.0",
  ...
}
```

vs `SKILL.md:128` (tdd-results.json):
```json
{
  "schema_version": "1.1",
  ...
}
```

vs `SKILL.md:156` (integration-results.json):
```json
{
  "schema_version": "1.1",
  ...
}
```

## 4. Regression Test

Function: `test_BUG_L10_recheck_schema_version_inconsistency` in `quality/test_regression.sh`

```bash
recheck_schema=$(grep -n '"schema_version": "1\.0"' "$skill_md" | head -1)
main_schema=$(grep -n '"schema_version": "1\.1"' "$skill_md" | head -1)
if [ -n "$recheck_schema" ] && [ -n "$main_schema" ]; then
    echo "BUG CONFIRMED: SKILL.md contains both schema_version '1.0' and '1.1'"
fi
```

## 5. Fix Patch

No fix patch provided — the fix is either of the following:

```diff
--- a/SKILL.md
+++ b/SKILL.md
@@ -1963,3 +1963,3 @@
 {
-  "schema_version": "1.0",
+  "schema_version": "1.1",
   "skill_version": "1.4.1",
```

Options:
1. Update recheck template at SKILL.md:1965 to use `"schema_version": "1.1"` (if recheck is the same schema family)
2. Add a documentation note explaining why recheck uses "1.0" (if it's intentionally different)

Option 1 is recommended for consistency. If the recheck schema has genuinely different structure, use a distinct schema name (e.g., `"schema": "recheck-v1.0"`) rather than a version number collision.

## 6. TDD Verification

**Red phase** (`quality/results/BUG-L10.red.log`):
```
BUG CONFIRMED: SKILL.md contains both schema_version '1.0' and '1.1'
Recheck template (1.0): 1965:  "schema_version": "1.0",
TDD/integration template (1.1): 128:  "schema_version": "1.1",
No migration note explains the version discrepancy
RESULT: FAIL
```
Exit code: 1. Test fails on unpatched code — confirms the schema version discrepancy.

**Green phase:** No fix patch — no green phase applicable. Status: confirmed open.
