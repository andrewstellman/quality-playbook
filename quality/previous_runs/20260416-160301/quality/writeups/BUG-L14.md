# BUG-L14: Wrong recommendation enum values in references/review_protocols.md

**Severity:** LOW  
**File:Line:** `references/review_protocols.md:410`  
**Date confirmed:** 2026-04-16  
**TDD verdict:** TDD verified

---

## 1. Description

`references/review_protocols.md:410` specifies the integration test reporting template with placeholder values `[SHIP IT / FIX FIRST / NEEDS INVESTIGATION]` for the `recommendation` field. These are stale human-readable prose labels from an earlier version of the playbook. The canonical machine-readable enum values in `quality_gate.sh:427` are `SHIP`, `FIX BEFORE MERGE`, and `BLOCK`. An agent that reads `references/review_protocols.md` (which is explicitly instructed in SKILL.md Phase 2) and follows its template exactly will produce a `integration-results.json` with a non-canonical `recommendation` value, causing the gate to fail with "recommendation 'FIX FIRST' is non-canonical."

The discrepancy is a three-way mismatch: the reference file (old values), the gate (canonical values), and SKILL.md:1273 (canonical values). The reference file was not updated when the recommendation schema was formalized.

## 2. Spec Basis

**REQ-017 (Tier 3):** Recommendation enum values must be consistent across all spec documents (SKILL.md, references/*.md, quality_gate.sh). The canonical values are `SHIP`, `FIX BEFORE MERGE`, and `BLOCK` as specified in SKILL.md:1273 and enforced at quality_gate.sh:427.

## 3. Code Location

Stale values in `references/review_protocols.md`:
```
# Line 94 (combined summary template):
- Overall assessment: SHIP IT / FIX FIRST / NEEDS DISCUSSION

# Line 392 (example):
**Recommendation:** FIX FIRST — Rate limit handling needs investigation.

# Line 410 (integration test template placeholder):
[SHIP IT / FIX FIRST / NEEDS INVESTIGATION]
```

Canonical enforcement in `quality_gate.sh:427`:
```bash
SHIP|"FIX BEFORE MERGE"|BLOCK) pass "recommendation '${rec}' is canonical" ;;
*) [ -n "$rec" ] && fail "recommendation '${rec}' is non-canonical (must be SHIP/FIX BEFORE MERGE/BLOCK)" || fail "recommendation missing" ;;
```

## 4. Regression Test

Function: `test_BUG_L14_recommendation_enum_inconsistency` in `quality/test_regression.sh`

```bash
if grep -q 'SHIP IT' "$ref" && grep -q 'FIX FIRST' "$ref"; then
    echo "BUG CONFIRMED: references/review_protocols.md contains stale enum values"
    return 1
fi
```

## 5. Fix Patch

```diff
--- a/references/review_protocols.md
+++ b/references/review_protocols.md
@@ -91,7 +91,7 @@ Combined Review Summary template:
-  - Overall assessment: SHIP IT / FIX FIRST / NEEDS DISCUSSION
+  - Overall assessment: SHIP / FIX BEFORE MERGE / BLOCK

@@ -389,7 +389,7 @@ Example integration results:
-**Recommendation:** FIX FIRST — Rate limit handling needs investigation.
+**Recommendation:** FIX BEFORE MERGE — Rate limit handling needs investigation.

@@ -407,7 +407,7 @@ Integration test reporting template:
-[SHIP IT / FIX FIRST / NEEDS INVESTIGATION]
+[SHIP / FIX BEFORE MERGE / BLOCK]
```

## 6. TDD Verification

**Red phase** (`quality/results/BUG-L14.red.log`):
```
BUG CONFIRMED: references/review_protocols.md contains stale enum values (SHIP IT / FIX FIRST)
Gate expects: SHIP | FIX BEFORE MERGE | BLOCK
RESULT: FAIL
```
Exit code: 1. Test fails on unpatched document — confirms stale enum values at multiple locations.

**Green phase** (`quality/results/BUG-L14.green.log`):
```
BUG FIXED: review_protocols.md uses canonical enum values
RESULT: PASS
```
After applying fix, all recommendation enum values in the reference file match the canonical values enforced by the gate.

## 7. Cross-References

- Gap iteration triage: `quality/spec_audits/gap_triage.md` — Finding G3
- Code review: `quality/code_reviews/gap_pass1_structural.md`
- Spec audit: `quality/spec_audits/gap_auditor_b.md` (user experience impact — alert fatigue)
- Spec audit: `quality/spec_audits/gap_auditor_c.md` (reliability impact — systematic gate failure)
