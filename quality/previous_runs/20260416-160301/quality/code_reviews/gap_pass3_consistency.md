# Code Review — Gap Iteration Pass 3: Cross-Requirement Consistency
<!-- Quality Playbook v1.4.1 — Gap Iteration Code Review — 2026-04-16 -->

## Pass 3: Cross-Requirement Consistency

Comparing pairs of requirements that reference the same concepts, checking mutual consistency.

---

### Shared Concept: ls-glob vs find detection methods (REQ-014, REQ-015, REQ-016)

**Requirements:** REQ-014, REQ-015, REQ-016

**What REQ-014 claims:** Gate script functional test detection (lines 123-126) must be consistent and use find-based detection. Already confirmed as VIOLATED (BUG-M8 scope).

**What REQ-015 claims:** Test file extension detection (line 479) must use find, not ls-glob.

**What REQ-016 claims:** code_reviews directory detection (line 143) must use find, not ls-glob.

**Consistency:** CONSISTENT — all three requirements demand the same fix (replace ls-glob with find). The three violations form a coherent bug class: the same nullglob vulnerability pattern appears at lines 124, 143, and 479. REQ-014 was already confirmed via BUG-M8; REQ-015 and REQ-016 extend the same fix requirement to two additional locations.

**Code evidence:**
- Line 124: `ls ${q}/test_functional.* ...` (in BUG-M8 scope)
- Line 143: `ls ${q}/code_reviews/*.md ...` (REQ-016 violation)
- Line 479: `ls ${q}/test_functional.*` (REQ-015 violation)
- Lines 486-495: `find ... -print -quit | grep -q .` (correct implementation in same function)

**Analysis:** The BUG-M8 fix patch covers lines 124, 152-153, 331, 567-568, 595 — but NOT lines 143 and 479. The fix is incomplete. A comprehensive fix should address all six nullglob-vulnerable ls-glob patterns.

---

### Shared Concept: Recommendation enum values (REQ-017 vs quality_gate.sh check)

**Requirements:** REQ-017

**What REQ-017 claims:** All spec documents must agree on `SHIP / FIX BEFORE MERGE / BLOCK`.

**What quality_gate.sh:427 implements:** Validates `SHIP|"FIX BEFORE MERGE"|BLOCK`.

**What SKILL.md:1273 specifies:** `"SHIP"`, `"FIX BEFORE MERGE"`, `"BLOCK"`.

**What references/review_protocols.md:410 specifies:** `SHIP IT / FIX FIRST / NEEDS INVESTIGATION`.

**Consistency:** INCONSISTENT — three documents that should agree do not. Gate and SKILL.md agree; review_protocols.md uses different values. The inconsistency is between the reference file and the gate/spec.

**Impact:** When an agent follows `references/review_protocols.md` (which is explicitly referenced by SKILL.md Phase 2 File 4 as the source for the integration test protocol), it generates gate-failing artifacts. This is a cross-file instruction inconsistency — following one authoritative document correctly causes another to fail.

---

### Shared Concept: Artifact contract enforcement completeness (REQ-018 vs REQ-004)

**Requirements:** REQ-018, REQ-004

**What REQ-004 claims:** Gate must check `quality/test_regression.*` existence when bugs are confirmed. (Already confirmed as BUG-M4.)

**What REQ-018 claims:** Gate must check recheck-results.json when recheck runs.

**Consistency:** CONSISTENT — both requirements address the same failure pattern: documented conditional artifacts in the SKILL.md artifact contract table that the gate does not enforce. REQ-004 was the first instance (test_regression.*); REQ-018 is a second instance (recheck-results.json). The underlying systemic issue (artifact contract table drift) was identified as Risk 3 in the baseline exploration and remains unresolved for multiple artifacts.

**Code evidence:** 
- REQ-004: Gate checks patches (lines 562-588) but not test_regression.* file
- REQ-018: Gate has no recheck section (lines 94-673 of check_repo function)
- SKILL.md artifact contract table: test_regression.* "Required: If bugs found"; recheck-results.json "When recheck runs"

**Analysis:** The gate has a systematic gap: it checks some conditional artifacts (tdd-results.json, patches, writeups) but not others (test_regression.*, recheck-results.json). REQ-004 and REQ-018 both require extending gate enforcement to cover additional documented artifacts.

---

## Combined Summary (Pass 3)

| Shared Concept | Requirements | Consistency | Impact |
|----------------|-------------|-------------|--------|
| ls-glob vs find detection | REQ-014, REQ-015, REQ-016 | CONSISTENT (all require find-based detection) | BUG-M8 fix is incomplete; needs extension to lines 143, 479 |
| Recommendation enum values | REQ-017 | INCONSISTENT (review_protocols.md uses different values from gate + SKILL.md) | Agents following reference file produce gate-failing artifacts |
| Artifact contract enforcement | REQ-004, REQ-018 | CONSISTENT (both require extending gate coverage) | Systematic gate enforcement gap for conditional artifacts |

**3 shared concepts checked: 1 INCONSISTENT, 2 CONSISTENT.**

**Overall assessment:** FIX FIRST — The recommendation enum inconsistency (REQ-017) and the gate enforcement gaps (REQ-015, REQ-016, REQ-018) are the highest-priority fixes. The ls-glob extension to lines 143 and 479 should be included in the BUG-M8 fix patch.
