# BUG-M5: Phase 0b skips when previous_runs/ exists but is empty

**Severity:** MEDIUM  
**File:Line:** `SKILL.md:271` (Phase 0a activation), `SKILL.md:295-297` (Phase 0b activation)  
**Date confirmed:** 2026-04-16  
**TDD verdict:** TDD verified

---

## 1. Description

Phase 0a activates only when `previous_runs/` exists AND contains prior quality artifacts. Phase 0b activates only when `previous_runs/` does NOT exist. When `previous_runs/` exists but is empty: Phase 0a skips (no artifacts), Phase 0b also skips (directory exists). No seeding occurs and no warning is emitted. The developer who created an empty `previous_runs/` directory expecting sibling-run seed discovery gets silent no-op behavior instead.

## 2. Spec Basis

**REQ-005 (Tier 2):** "Phase 0b seed discovery must run when `previous_runs/` exists but contains no conformant quality artifacts."

**CONTRACTS.md item 14:** "[ERROR] contract: 'This creates a gap: empty `previous_runs/` causes both Phase 0a and 0b to skip with no warning.'"

## 3. Code Location

`SKILL.md:295-297` — Phase 0b activation condition:
```
**This step runs only if `previous_runs/` does not exist** (i.e., Phase 0a has nothing to 
work with) **and** the project directory is versioned...
```

The condition "does not exist" does not cover the case where the directory exists but is empty.

## 4. Regression Test

Function: `test_BUG_M5_phase0b_skips_on_empty_previous_runs` in `quality/test_regression.sh`

```bash
# Extract Phase 0b activation condition
phase0b_condition=$(grep -A5 'Phase 0b: Sibling-Run' "$skill_md" | grep -E 'runs only if|This step runs' | head -1)
# Check if fixed condition includes empty-directory case
if echo "$phase0b_condition" | grep -qiE 'OR.*empty|empty.*OR|no conformant|is empty'; then
    echo "BUG FIXED"; else echo "BUG CONFIRMED"
fi
```

## 5. Fix Patch

```diff
--- a/SKILL.md
+++ b/SKILL.md
@@ -293,8 +293,10 @@ perform their own sibling-run seeding without an explicit `previous_runs/` archi
 ### Phase 0b: Sibling-Run Seed Discovery (Automatic)

-**This step runs only if `previous_runs/` does not exist** (i.e., Phase 0a has nothing to work with) **and** the project directory is versioned...
+**This step runs only if `previous_runs/` does not exist OR `previous_runs/` exists but contains no conformant quality artifacts** (i.e., Phase 0a has nothing to work with) **and** the project directory is versioned...
+
+**If `previous_runs/` exists but is empty or contains only non-conformant subdirectories**, emit a warning: "Phase 0b: `previous_runs/` exists but contains no conformant artifacts — consulting sibling versioned directories for seeds." Then proceed with the sibling discovery below.
```

## 6. TDD Verification

**Red phase** (`quality/results/BUG-M5.red.log`):
```
Phase 0b activation: **This step runs only if `previous_runs/` does not exist**...
BUG CONFIRMED: Phase 0b says 'does not exist' — empty dir creates gap
RESULT: FAIL
```
Exit code: 1. Test fails on unpatched code — confirms the gap in Phase 0b activation.

**Green phase** (`quality/results/BUG-M5.green.log`):
```
Fixed Phase 0b activation: ...does not exist OR previous_runs/ exists but contains no conformant quality artifacts
PASS: Fixed Phase 0b condition covers empty previous_runs/ case
```
After applying fix patch, Phase 0b correctly activates when previous_runs/ exists but is empty.
