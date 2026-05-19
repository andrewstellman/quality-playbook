# BUG-L11: Two incompatible tdd-results.json templates (UC vs REQ format)

**Severity:** LOW  
**File:Line:** `SKILL.md:135` (artifact contract template) vs `SKILL.md:1385` (Phase 5 RUN_TDD_TESTS.md template)  
**Date confirmed:** 2026-04-16  
**TDD verdict:** confirmed open (no fix patch — spec-primary fix required)

---

## 1. Description

Two incompatible tdd-results.json templates exist in SKILL.md. Template 1 (artifact contract section, lines 122-148) shows the `requirement` field as a full description: `"requirement": "UC-03: Description of the requirement violated"`. Template 2 (Phase 5 File 7, lines 1376-1408) shows: `"requirement": "REQ-003"`. Additionally, Template 1's `red_phase` and `green_phase` fields contain narrative text ("Regression test fails on unpatched code"), while Template 2's use enum values ("fail", "pass"). Template 2 also includes 7 optional fields not present in Template 1. An agent following Template 1 generates different JSON than an agent following Template 2. The gate validates required per-bug field PRESENCE but not VALUE FORMAT, so both pass the gate. However, downstream tools that expect the `requirement` field to contain a REQ-NNN identifier (for traceability) would fail on Template 1 output.

## 2. Spec Basis

**REQ-009 (Tier 2):** Generated artifacts must include consistent version stamps and field formats. This is a spec bug — two templates in SKILL.md define different value formats for the same required JSON field.

## 3. Code Location

Template 1 at `SKILL.md:135` (artifact contract):
```json
{
  "id": "BUG-NNN",
  "requirement": "UC-03: Description of the requirement violated",
  "red_phase": "Regression test fails on unpatched code, confirming the bug",
  "green_phase": "After applying fix patch, regression test passes",
  "verdict": "TDD verified",
  "fix_patch_present": true,
  "writeup_path": "quality/writeups/BUG-NNN.md"
}
```

Template 2 at `SKILL.md:1385` (Phase 5 RUN_TDD_TESTS.md):
```json
{
  "id": "BUG-H1",
  "requirement": "REQ-001",
  ...
}
```

## 4. Regression Test

Function: `test_BUG_L11_tdd_results_two_incompatible_templates` in `quality/test_regression.sh`

```bash
# Template 1 uses UC-format for requirement field
template1_uc=$(grep -n '"requirement":.*UC-[0-9][0-9]:' "$skill_md" | head -1)
# Template 2 uses REQ-format
template2_req=$(grep -n '"requirement": "REQ-[0-9]' "$skill_md" | head -1)
if [ -n "$template1_uc" ] && [ -n "$template2_req" ]; then
    echo "BUG CONFIRMED: Two incompatible 'requirement' field formats in SKILL.md"
fi
```

## 5. Fix Patch

No fix patch provided — the fix is standardizing the templates. Recommended fix: use the UC-NN format with description (Template 1 format) as the canonical form, since it provides more context and aligns with the UC identifiers in REQUIREMENTS.md. Update the Phase 5 RUN_TDD_TESTS.md template at line 1385 to match Template 1.

```diff
--- a/SKILL.md
+++ b/SKILL.md
@@ -1383,3 +1383,3 @@
-         "requirement": "REQ-003",
+         "requirement": "UC-03: Description of the requirement violated",
          "red_phase": "Regression test fails on unpatched code, confirming the bug",
          "green_phase": "After applying fix patch, regression test passes",
```

Note: This run's tdd-results.json uses the UC-NN format (Template 1) per the task instructions, which is the richer and more traceable format.

## 6. TDD Verification

**Red phase** (`quality/results/BUG-L11.red.log`):
```
BUG CONFIRMED: Two incompatible 'requirement' field formats in SKILL.md
Template 1 (artifact contract, UC-format): 135:      "requirement": "UC-03: Description..."
Template 2 (Phase 5, REQ-format): 1385:         "requirement": "REQ-003",
RESULT: FAIL
```
Exit code: 1. Test fails on unpatched code — confirms the two incompatible templates exist.

**Green phase:** No fix patch — no green phase applicable. Status: confirmed open.
