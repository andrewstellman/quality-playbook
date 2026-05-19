# Spec Audit Triage — Gap Iteration
<!-- Quality Playbook v1.4.1 — Gap Iteration Triage — 2026-04-16 -->

## Council Status

- Auditor A (Strict Compliance): Fresh report received (2026-04-16)
- Auditor B (User Experience): Fresh report received (2026-04-16)
- Auditor C (Security/Reliability): Fresh report received (2026-04-16)
- Effective council: 3/3

## Pre-audit docs validation

No supplemental docs provided. Auditors relied on SKILL.md, references/*.md, quality_gate.sh, and EXPLORATION_ITER2.md as spec sources.

---

## Triage — Finding G1: quality_gate.sh:479 — ls-glob in test file extension detection

**Found by:** All three auditors (3/3 — Highest confidence)

**Claim:** `func_test=$(ls ${q}/test_functional.* 2>/dev/null | head -1)` produces a wrong filename under nullglob.

**Verification probe:**
```bash
# Assertion: Under nullglob, ls with unmatched glob lists CWD (not empty)
cd /tmp && mkdir -p test_nullglob_dir && cd test_nullglob_dir
(set +o nullglob 2>/dev/null; shopt -s nullglob 2>/dev/null
 result=$(ls *.nonexistent 2>/dev/null | head -1)
 if [ -n "$result" ]; then
   echo "CONFIRMED: ls lists CWD under nullglob (result: $result)"
 else
   echo "PASS: result is empty (nullglob not active or ls behavior differs)"
 fi)
```

**Actual code at quality_gate.sh:479:**
```bash
func_test=$(ls ${q}/test_functional.* 2>/dev/null | head -1)
```
Line 479 contains exactly this ls-glob pattern. The vulnerability is confirmed by the same mechanism as BUG-M8 (lines 152-153, 331, 567-568, 595). 

**Comparison with fix at lines 486-495 (7 lines later):**
```bash
if find "${repo_dir}" -maxdepth 3 -not -path '*/vendor/*' ... -name '*.go' -print -quit 2>/dev/null | grep -q .; then
```
The correct pattern (find-based) is already used in the same function block.

**Verdict:** CONFIRMED — Real code bug. Line 479 uses ls-glob; correct approach is find-based as shown at line 486.

**Category:** Real code bug
**New BUG:** BUG-M12

---

## Triage — Finding G2: quality_gate.sh:143 — ls-glob in code_reviews directory check

**Found by:** All three auditors (3/3 — Highest confidence)

**Claim:** `[ -n "$(ls ${q}/code_reviews/*.md 2>/dev/null)" ]` passes when directory is empty under nullglob.

**Verification probe:**
```bash
# Assertion: same nullglob pattern causes false pass for empty directory
# Direct code inspection at quality_gate.sh:143:
grep -n 'code_reviews.*\.md' quality_gate.sh
# Expected output: line 143 contains: ls ${q}/code_reviews/*.md
```

**Actual code at quality_gate.sh:143:**
```bash
if [ -d "${q}/code_reviews" ] && [ -n "$(ls ${q}/code_reviews/*.md 2>/dev/null)" ]; then
    pass "code_reviews/ has .md files"
```
Confirmed ls-glob pattern. Under nullglob: empty directory → ls lists CWD → non-empty → FALSE PASS.

**Verdict:** CONFIRMED — Real code bug. Line 143 uses ls-glob for directory content detection.

**Category:** Real code bug
**New BUG:** BUG-M13

---

## Triage — Finding G3: references/review_protocols.md:410 — Wrong recommendation enum

**Found by:** All three auditors (3/3 — Highest confidence)

**Claim:** Template specifies `SHIP IT / FIX FIRST / NEEDS INVESTIGATION` but gate requires `SHIP / FIX BEFORE MERGE / BLOCK`.

**Verification probe:**
```bash
# Check review_protocols.md line 410
grep -n 'SHIP IT\|FIX FIRST\|NEEDS INVESTIGATION\|FIX BEFORE MERGE\|BLOCK' references/review_protocols.md
# Expected: line 410 contains SHIP IT / FIX FIRST / NEEDS INVESTIGATION
grep -n 'SHIP.*FIX.*MERGE\|canonical.*SHIP' quality_gate.sh
# Expected: line 427 contains SHIP|"FIX BEFORE MERGE"|BLOCK
```

**Actual text at references/review_protocols.md:410:**
```
[SHIP IT / FIX FIRST / NEEDS INVESTIGATION]
```
**Actual code at quality_gate.sh:427:**
```bash
SHIP|"FIX BEFORE MERGE"|BLOCK) pass "recommendation '${rec}' is canonical" ;;
```
**SKILL.md:1273:** `"SHIP"`, `"FIX BEFORE MERGE"`, `"BLOCK"`.

The discrepancy is definitively confirmed. An agent following references/review_protocols.md will produce `"FIX FIRST"` which fails the gate.

**Verdict:** CONFIRMED — Real spec bug (reference file has stale values that contradict canonical values in gate and SKILL.md).

**Category:** Real code bug (fix references/review_protocols.md:410 to use canonical values)
**New BUG:** BUG-L14

---

## Triage — Finding G4: quality_gate.sh — No recheck-results.json validation

**Found by:** All three auditors (3/3 — Highest confidence)

**Claim:** Gate has no validation section for recheck-results.json despite artifact contract table documenting it as required.

**Verification probe:**
```bash
# Check: does quality_gate.sh contain any reference to recheck?
grep -n 'recheck' quality_gate.sh
# Expected: NO OUTPUT (zero matches)
```

**Actual result:** No matches for "recheck" in quality_gate.sh. The gate has zero validation for recheck artifacts. SKILL.md artifact contract table lines 117-118 documents both `recheck-results.json` and `recheck-summary.md` as required artifacts. The gate enforces neither.

**Verdict:** CONFIRMED — Real code bug. Gate is missing mandatory recheck artifact validation.

**Category:** Real code bug (add recheck validation section to quality_gate.sh)
**New BUG:** BUG-M15

---

## Confirmed New Bugs (Gap Iteration)

| Bug | File:Line | Description | Severity | Category |
|-----|-----------|-------------|----------|----------|
| BUG-M12 | quality_gate.sh:479 | ls-glob in test file extension detection | MEDIUM | Real code bug |
| BUG-M13 | quality_gate.sh:143 | ls-glob in code_reviews directory check | MEDIUM | Real code bug |
| BUG-L14 | references/review_protocols.md:410 | Wrong recommendation enum values | LOW | Spec bug (doc fix) |
| BUG-M15 | quality_gate.sh (absence) | No recheck-results.json validation | MEDIUM | Real code bug |

**Net-new bugs from gap iteration: 4** (BUG-M12, BUG-M13, BUG-L14, BUG-M15)

**Total confirmed bugs after gap iteration: 15** (11 from baseline + 4 from gap)

---

## Cross-artifact consistency check

Comparing gap iteration triage against baseline code review findings:
- BUG-M8 (baseline) covers lines 124, 152-153, 331, 567-568, 595 of quality_gate.sh
- BUG-M12 (gap) covers line 479 — NOT in BUG-M8's scope
- BUG-M13 (gap) covers line 143 — NOT in BUG-M8's scope

The gap iteration's ls-glob findings (BUG-M12, BUG-M13) are confirmed as SEPARATE from BUG-M8. The BUG-M8 fix patch must be extended to cover all 6 vulnerable locations (original 4 + lines 143 and 479) for a complete fix. However, for tracking purposes, BUG-M12 and BUG-M13 are new confirmed bugs.

No conflicts between code review and spec audit. All three auditors agree on all four findings.
