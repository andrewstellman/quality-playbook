# Code Review — Gap Iteration Pass 2: Requirement Verification
<!-- Quality Playbook v1.4.1 — Gap Iteration Code Review — 2026-04-16 -->

## Pass 2: Requirement Verification

Verifying the four new requirements (REQ-015 through REQ-018) from the gap iteration against the current code.

---

### REQ-015: Gate Script Test File Extension Detection Must Use find, Not ls-glob

**Status:** VIOLATED

**Evidence:** `quality_gate.sh:479`
```bash
func_test=$(ls ${q}/test_functional.* 2>/dev/null | head -1)
reg_test=$(ls ${q}/test_regression.* 2>/dev/null | head -1)
```

**Analysis:** The requirement specifies that under nullglob (zsh default), when no test_functional.* exists, func_test must be empty. The current code uses `ls` glob which, under nullglob, lists CWD when the glob matches nothing. This violates the condition "Under nullglob, when no test_functional.* file exists: func_test variable must be empty."

**Contrast:** Lines 486–495 in the SAME function use `find ... -print -quit 2>/dev/null | grep -q .` — the correct approach is already used 7 lines below the bug.

**Severity:** MEDIUM

---

### REQ-016: Gate Script Code Reviews Directory Detection Must Use find, Not ls-glob

**Status:** VIOLATED

**Evidence:** `quality_gate.sh:143`
```bash
if [ -d "${q}/code_reviews" ] && [ -n "$(ls ${q}/code_reviews/*.md 2>/dev/null)" ]; then
```

**Analysis:** The requirement specifies that under nullglob, when code_reviews/ exists but is empty, the gate must FAIL. The current `ls` glob under nullglob produces a non-empty CWD listing, making the check PASS spuriously. This violates the condition "Under nullglob, when code_reviews/ exists but is empty: gate must FAIL 'code_reviews/ missing or empty'."

**Severity:** MEDIUM

---

### REQ-017: Recommendation Enum Values Must Be Consistent Across All Spec Documents

**Status:** VIOLATED

**Evidence:** `references/review_protocols.md:410`
```
### Recommendation
[SHIP IT / FIX FIRST / NEEDS INVESTIGATION]
```
vs. `quality_gate.sh:427`:
```bash
SHIP|"FIX BEFORE MERGE"|BLOCK) pass "recommendation '${rec}' is canonical" ;;
```
vs. `SKILL.md:1273`:
```
Valid `recommendation` values: `"SHIP"` ... `"FIX BEFORE MERGE"` ... `"BLOCK"`.
```

**Analysis:** The requirement specifies all three documents must agree. They do not. The reference file uses stale human-readable values that differ from the canonical machine-readable enum values. This violates "SKILL.md, references/review_protocols.md, and quality_gate.sh must all agree on the same three values."

**Severity:** MEDIUM

---

### REQ-018: Gate Script Must Validate recheck-results.json When Recheck Mode Runs

**Status:** VIOLATED (by absence)

**Evidence:** `quality_gate.sh` (entire check_repo function, lines 94–673) — searched for "recheck":
- No `[Recheck]` section exists
- No reference to `recheck-results.json` in any gate check
- No validation of recheck status enum values

**Analysis:** The requirement specifies that when recheck-results.json exists, the gate must check schema_version, status enum values, and required per-result fields. No such check exists. The artifact contract table documents both recheck files as required artifacts, but the gate enforces neither.

**Severity:** MEDIUM

---

### Verification of Existing Requirements REQ-001 through REQ-014

For previously-confirmed requirements, checking for regressions in the gap areas:

**REQ-002 (Array reconstruction must preserve paths with spaces):** STILL VIOLATED (BUG-H2, confirmed open). No change.

**REQ-009 (Version stamps consistent):** The TOOLKIT.md phase count discrepancy (6 vs 8 phases) does not affect version stamp generation. PARTIALLY SATISFIED (as before).

**REQ-014 (Gate functional test detection consistent):** Lines 123-124 (already in BUG-M8 scope). The NEW violation at line 479 is now captured by REQ-015. STILL VIOLATED.

---

## Combined Summary (Pass 2)

| Requirement | Status | Evidence |
|-------------|--------|----------|
| REQ-015: Test file extension uses find | VIOLATED | quality_gate.sh:479 uses ls-glob |
| REQ-016: code_reviews detection uses find | VIOLATED | quality_gate.sh:143 uses ls-glob |
| REQ-017: Recommendation enum consistent | VIOLATED | references/review_protocols.md:410 uses stale values |
| REQ-018: Gate validates recheck-results.json | VIOLATED | No recheck validation in check_repo |

All 4 new requirements violated. Consistent with findings from Pass 1.
