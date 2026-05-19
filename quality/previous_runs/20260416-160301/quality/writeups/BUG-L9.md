# BUG-L9: Incompatible auditor report naming formats

**Severity:** LOW  
**File:Line:** `SKILL.md:1548`, `quality/RUN_SPEC_AUDIT.md:143`, `references/spec_audit.md` "Output" section  
**Date confirmed:** 2026-04-16  
**TDD verdict:** confirmed open (no fix patch — spec-primary fix required)

---

## 1. Description

Three incompatible naming formats are specified for individual auditor report files:
1. SKILL.md line 1548 (Phase 4 instructions): `quality/spec_audits/YYYY-MM-DD-auditor-N.md`
2. quality/RUN_SPEC_AUDIT.md line 143 (generated per-project protocol): `quality/spec_audits/auditor_<model>_<date>.md`
3. references/spec_audit.md "Output" section: `quality/spec_audits/YYYY-MM-DD-[model].md`

The gate glob `*auditor*` at quality_gate.sh line 153 matches all three patterns. However, an agent following Phase 4 instructions writes differently-named files than an agent following the generated RUN_SPEC_AUDIT.md. This creates naming inconsistency across runs and sessions, making artifact provenance hard to track.

## 2. Spec Basis

**REQ-011 (Tier 1):** Requirements pipeline must produce traceable artifacts. Naming inconsistency reduces traceability. This is a spec bug — internal inconsistency between SKILL.md Phase 4 and the generated spec audit protocol.

## 3. Code Location

Three conflicting specifications:
- `SKILL.md:1548`: `quality/spec_audits/YYYY-MM-DD-auditor-N.md`
- `quality/RUN_SPEC_AUDIT.md:143`: `quality/spec_audits/auditor_<model>_<date>.md`
- `references/spec_audit.md` Output section: `quality/spec_audits/YYYY-MM-DD-[model].md`

## 4. Regression Test

Function: `test_BUG_L9_auditor_naming_inconsistency` in `quality/test_regression.sh`

```bash
# SKILL.md line 1548 specifies: YYYY-MM-DD-auditor-N.md
skill_format=$(grep -n 'YYYY-MM-DD-auditor-N' "$skill_md" | head -1)
# RUN_SPEC_AUDIT.md line 143 specifies: auditor_<model>_<date>.md
run_format=$(grep -n 'auditor_<model>' "$run_spec_audit" | head -1)
if [ -n "$skill_format" ] && [ -n "$run_format" ]; then
    echo "BUG CONFIRMED: Two incompatible auditor naming formats exist"
fi
```

## 5. Fix Patch

No fix patch provided — the fix is standardizing naming format across all three documents. Recommended fix: standardize on `quality/spec_audits/auditor_N.md` (simple, unambiguous, matches current practice in this run's `auditor_a.md`, `auditor_b.md`, `auditor_c.md`). Update SKILL.md Phase 4 instructions, RUN_SPEC_AUDIT.md template, and references/spec_audit.md Output section to all use the same format.

```diff
--- a/SKILL.md
+++ b/SKILL.md
@@ -1546,3 +1546,3 @@
-**Individual auditor artifacts (mandatory).** The spec audit must produce individual auditor report files at `quality/spec_audits/YYYY-MM-DD-auditor-N.md` (one per auditor)
+**Individual auditor artifacts (mandatory).** The spec audit must produce individual auditor report files at `quality/spec_audits/auditor_N.md` (e.g., `auditor_a.md`, `auditor_b.md`, `auditor_c.md` — one per auditor)
```

## 6. TDD Verification

**Red phase** (`quality/results/BUG-L9.red.log`):
```
BUG CONFIRMED: Two incompatible auditor naming formats exist
SKILL.md (Phase 4 instructions): 1548:...YYYY-MM-DD-auditor-N.md...
RUN_SPEC_AUDIT.md: 143:...auditor_<model>_<date>.md
RESULT: FAIL
```
Exit code: 1. Test fails on unpatched code — confirms incompatible naming formats exist.

**Green phase:** No fix patch — no green phase applicable. Status: confirmed open.
