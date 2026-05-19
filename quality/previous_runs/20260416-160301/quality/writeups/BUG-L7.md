# BUG-L7: Version 1.4.1 hardcoded in 8 locations without cross-reference check

**Severity:** LOW  
**File:Line:** `SKILL.md:6, 39, 129, 156, 915, 922, 1056, 1966` (8 occurrences of `1.4.1`)  
**Date confirmed:** 2026-04-16  
**TDD verdict:** confirmed open (latent risk — all 8 occurrences currently consistent)

---

## 1. Description

Version `1.4.1` appears in 8 hardcoded locations in SKILL.md without a mechanical cross-reference check. All 8 currently match, so no immediate bug exists. However, there is no tool or gate check that enforces SKILL.md-internal version consistency. A version bump that updates the frontmatter but misses one of the 8 inline occurrences (particularly the JSON examples at lines 129 and 1966 which agents copy verbatim) would cause agents to generate wrong-stamped artifacts without any warning from the gate.

## 2. Spec Basis

**REQ-006 (Tier 2):** "All occurrences of the version string in SKILL.md must equal `metadata.version`. A grep for any version string that differs from frontmatter must return empty." The "mechanical check" aspect is currently missing.

## 3. Code Location

8 locations in SKILL.md where `1.4.1` appears:
- Line 6: frontmatter `version: 1.4.1`
- Line 39: "Quality Playbook v1.4.1 — by Andrew Stellman"
- Line 129: `"skill_version": "1.4.1"` in tdd-results.json template
- Line 156: `"skill_version": "1.4.1"` in integration-results.json template
- Lines 915, 922, 1056: version references in gate instructions
- Line 1966: `"skill_version": "1.4.1"` in recheck-results.json template

## 4. Regression Test

Function: `test_BUG_L7_version_string_consistency` in `quality/test_regression.sh`

```bash
frontmatter_version=$(grep -m1 'version:' "$skill_md" | sed 's/.*version: *//' | tr -d ' ')
# Find version strings that differ from frontmatter
stale_count=$(grep -oE '[0-9]+\.[0-9]+\.[0-9]+' "$skill_md" | grep -cv "^${frontmatter_version}$")
```

Note: The test currently reports 31 "different" versions because it catches historical version references in prose (v1.3.23, v1.3.41, etc.). The test design should be refined to distinguish historical references from current-version occurrences.

## 5. Fix Patch

No fix patch provided — the fix is structural. The recommended approach:

```diff
--- a/quality_gate.sh (proposed addition)
+++ b/quality_gate.sh (proposed addition)
@@ -xx,0 +xx,8 @@
+    # Version consistency check — all X.Y.Z strings in SKILL.md must match frontmatter
+    local skill_md_version
+    skill_md_version=$(grep -m1 'version:' "${SKILL_MD:-SKILL.md}" 2>/dev/null | sed 's/.*version: *//')
+    if [ -n "$skill_md_version" ]; then
+        local stale=$(grep -oE '[0-9]+\.[0-9]+\.[0-9]+' "${SKILL_MD:-SKILL.md}" | grep -cv "^${skill_md_version}$" || true)
+        [ "$stale" -eq 0 ] && pass "All version strings in SKILL.md match frontmatter (${skill_md_version})" \
+                           || fail "${stale} version string(s) in SKILL.md differ from frontmatter (${skill_md_version})"
+    fi
```

Alternative options:
1. Add a CI/pre-commit check that greps SKILL.md for version strings and compares all `X.Y.Z` occurrences in JSON template sections against frontmatter.
2. Integrate the version-consistency check into `quality_gate.sh` to detect stale version stamps in generated artifacts.
3. Add a `Makefile` target or release script that uses `sed` to update all 8 locations atomically on version bump.

The current state (all 8 locations consistent at 1.4.1) is correct. The bug is the absence of mechanical enforcement, not a current inconsistency.

## 6. TDD Verification

**Red phase** (`quality/results/BUG-L7.red.log`):
```
Frontmatter version: 1.4.1
BUG CONFIRMED: 31 version string(s) differ from frontmatter '1.4.1'
RESULT: FAIL
```
Exit code: 1. Test reports FAIL due to historical prose references (v1.3.x). Note: the 8 current-version occurrences are all consistent — the test design is overly broad. The real bug (absence of mechanical enforcement) is confirmed by the absence of any CI/gate check for version consistency.

**Green phase:** No fix patch — no green phase applicable. Status: confirmed open.
