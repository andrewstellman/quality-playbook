# Spec Audit Triage — Unfiltered Iteration

<!-- Quality Playbook v1.4.1 — Unfiltered Iteration Spec Audit Triage — 2026-04-16 -->

## Council Status

- Auditor A (Strict Compliance): Fresh report received 2026-04-16
- Auditor B (User Experience): Fresh report received 2026-04-16
- Auditor C (Security/Reliability): Fresh report received 2026-04-16
- **Effective council: 3/3**

## Pre-audit docs validation

No `docs_gathered/` directory exists. Auditors relied on in-repo specs (SKILL.md v1.4.1, quality_gate.sh, references/*.md) and code only. No known inaccuracies in the spec documents — findings are code-vs-spec divergences.

---

## Triage

### Finding 1: quality_gate.sh:124 — ls-glob functional test file existence check (CAND-U1)

**Auditors:** A (MISSING), B (DIVERGENT), C (DIVERGENT)
**Confidence:** All three auditors — **Highest confidence**
**Verification probe:** PROBE-U1 below.
**Category:** Real code bug

**Verification probe (PROBE-U1):**
```bash
# Prove the bug: ls-glob at line 124 is NOT find-based
grep -n 'ls ${q}/test_functional\.\*' quality_gate.sh
# Expected output: line 124 with ls glob
# Actual output:
grep -n 'ls ${q}.*test_functional' quality_gate.sh
```
Actual line 124: `if ls ${q}/test_functional.* ${q}/FunctionalSpec.* ${q}/FunctionalTest.* ${q}/functional.test.* &>/dev/null 2>&1; then`
- CONFIRMED: uses `ls` glob, not `find`
- Compare with find-based pattern at lines 449-454 which correctly uses `find "${repo_dir}" ... -print -quit`

**Verdict: CONFIRMED — Real code bug. Severity: MEDIUM**

---

### Finding 2: quality_gate.sh:184,313 — BUG-[0-9]+ regex never matches BUG-H1 format (CAND-U2)

**Auditors:** A (DIVERGENT), B (DIVERGENT), C (PHANTOM)
**Confidence:** All three auditors — **Highest confidence**
**Verification probe:** PROBE-U2 below.
**Category:** Real code bug — HIGH severity

**Verification probe (PROBE-U2):**
```bash
# Prove the bug: regex ^### BUG-[0-9]+ doesn't match BUG-H1 format
echo "### BUG-H1" | grep -cE '^### BUG-[0-9]+'
# Expected output: 1 (if regex matches)
# Actual output:
```
Assertion: `assert $(echo '### BUG-H1' | grep -cE '^### BUG-[0-9]+') = 0`
This assertion PASSES (output is 0), CONFIRMING the bug — regex does NOT match BUG-H1 format.

Consequence verification:
```bash
echo '### BUG-H1' | grep -cE '^### BUG-[0-9]+'  # → 0 (bug present)
echo '### BUG-001' | grep -cE '^### BUG-[0-9]+'  # → 1 (numeric format works)
```
With severity-prefix IDs: `bug_count=0` → ALL downstream validation skipped.

**Verdict: CONFIRMED — Real code bug. Severity: HIGH**

---

### Finding 3: quality_gate.sh — TDD sidecar JSON phase values not cross-validated against log tags (CAND-U3)

**Auditors:** A (MISSING), B (MISSING), C (MISSING)
**Confidence:** All three auditors — **Highest confidence**
**Verification probe:** PROBE-U3 below.
**Category:** Real code bug

**Verification probe (PROBE-U3):**
```bash
# Prove the bug: grep quality_gate.sh for any code that extracts red_phase VALUE and compares with log tag
grep -n 'red_phase\|green_phase' quality_gate.sh
```
Expected result if cross-validation exists: lines showing `json_str_val ... "red_phase"` followed by comparison with log tag.
Actual result: lines showing `json_key_count` (presence check) and log tag validation (format check) — NO comparison between them.

Specific lines found:
- Line 239: `for field in id requirement red_phase green_phase verdict fix_patch_present writeup_path; do` (presence check, not value check)
- Lines 322-325: `red_tag=$(head -1 ...); case "$red_tag" in RED|GREEN|NOT_RUN|ERROR) ;;` (format check only)
- NO code extracts `json_str_val ... "red_phase"` and compares with `$red_tag`

CONFIRMED: The cross-validation mandated by SKILL.md:1589 is entirely absent.

**Verdict: CONFIRMED — Real code bug. Severity: MEDIUM**

---

### Non-code findings (spec-primary fixes):

### Finding 4: SKILL.md:1615 — BUG-001 example vs BUG-H1 practice

**Auditors:** A (DIVERGENT), B (DIVERGENT)
**Confidence:** Two of three — **High confidence**
**Category:** Spec bug — spec example contradicts established QFB practice. Fix: update SKILL.md:1615 to show both formats or standardize to one.

**Verdict: CONFIRMED — Spec bug. Severity: LOW (same root cause as CAND-U2 but fix is in SKILL.md not gate)**

---

## Consolidated Findings

| # | Location | Description | Auditors | Category | Severity |
|---|----------|-------------|----------|----------|----------|
| U1 | quality_gate.sh:124 | ls-glob functional test existence — nullglob vulnerable | 3/3 | Real code bug | MEDIUM |
| U2 | quality_gate.sh:184,313 | BUG-[0-9]+ regex never matches BUG-H1, gate bypassed | 3/3 | Real code bug | HIGH |
| U3 | quality_gate.sh:239-248,307-387 | TDD phase values not cross-validated with log tags | 3/3 | Real code bug | MEDIUM |
| U4 | SKILL.md:1615 | Example BUG-001 conflicts with BUG-H1 practice | 2/3 | Spec bug | LOW |

**Net-new confirmed code bugs this iteration: 3** (U1, U2, U3)
**Net-new spec bugs: 1** (U4 — no regression test needed)

## Assignment to BUG Numbers

| Finding | BUG-NNN | Notes |
|---------|---------|-------|
| CAND-U1 (quality_gate.sh:124) | BUG-M16 | MEDIUM — ls-glob existence check |
| CAND-U2 (quality_gate.sh:184,313) | BUG-H17 | HIGH — regex never matches severity-prefix IDs |
| CAND-U3 (quality_gate.sh phase cross-validation) | BUG-M18 | MEDIUM — TDD sidecar/log cross-validation absent |
