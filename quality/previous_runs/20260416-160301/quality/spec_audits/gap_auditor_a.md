# Spec Audit — Gap Iteration Auditor A (Strict Compliance)
<!-- Quality Playbook v1.4.1 — Gap Iteration Spec Audit — 2026-04-16 -->

## Council Status
- Auditor A (Strict Compliance): Fresh report — 2026-04-16
- Auditor B (User Experience): See gap_auditor_b.md
- Auditor C (Security/Reliability): See gap_auditor_c.md

## Pre-audit docs validation

No `docs_gathered/` directory. Auditors rely on in-repo specs (SKILL.md, references/*.md, quality_gate.sh) and gap iteration findings (EXPLORATION_ITER2.md). Context: baseline run confirmed 11 bugs; this audit focuses on 4 new candidates from gap exploration.

---

## Auditor A Findings (Strict Compliance)

### quality_gate.sh

**Line 479:** [DIVERGENT] [Req: inferred — from BUG-M8 fix pattern]
```bash
func_test=$(ls ${q}/test_functional.* 2>/dev/null | head -1)
```
Spec says: Gate must reliably detect functional test files under all shell configurations (REQ-015). SKILL.md and BUG-M8 fix establish that `find`-based detection is the required pattern.
Code does: Uses ls-glob, which under nullglob captures a CWD filename instead of empty. The function uses `find` for language detection (lines 486-495) but `ls` for test file detection (line 479) — 7 lines of inconsistency within the same function block.
Classification: DIVERGENT — code behavior diverges from the requirement to return empty when no file exists.

**Line 143:** [DIVERGENT] [Req: inferred — from BUG-M8 fix pattern]
```bash
if [ -d "${q}/code_reviews" ] && [ -n "$(ls ${q}/code_reviews/*.md 2>/dev/null)" ]; then
```
Spec says: Gate must correctly detect whether code review files were written (REQ-016).
Code does: Under nullglob, ls-glob listing returns CWD content, making the check pass even when code_reviews/ is empty.
Classification: DIVERGENT — false pass under nullglob.

**Lines 94-673 (entire check_repo):** [MISSING] [Req: formal — SKILL.md artifact contract table]
No validation section for `recheck-results.json` or `recheck-summary.md`.
Spec says: SKILL.md artifact contract table lines 117-118 documents both files as required when recheck runs. Gate must validate conditional artifacts.
Code does: Checks tdd-results.json, integration-results.json, patches, writeups, TDD logs — but not recheck artifacts.
Classification: MISSING — feature documented as required in spec, absent from code.

### references/review_protocols.md

**Line 410:** [DIVERGENT] [Req: formal — quality_gate.sh:427 enforcement]
```
### Recommendation
[SHIP IT / FIX FIRST / NEEDS INVESTIGATION]
```
Spec says: quality_gate.sh:427 validates `SHIP|"FIX BEFORE MERGE"|BLOCK`. SKILL.md:1273 specifies `"SHIP"`, `"FIX BEFORE MERGE"`, `"BLOCK"`.
Code does: Reference file specifies stale values that the gate rejects.
Classification: DIVERGENT — reference file specifies values that are invalid per gate enforcement.

---

## Summary: Auditor A

| Finding | Classification | Severity |
|---------|---------------|----------|
| quality_gate.sh:479 — ls-glob in extension detection | DIVERGENT | MEDIUM |
| quality_gate.sh:143 — ls-glob in code_reviews detection | DIVERGENT | MEDIUM |
| quality_gate.sh (absence) — no recheck validation | MISSING | MEDIUM |
| references/review_protocols.md:410 — wrong enum values | DIVERGENT | MEDIUM |

All 4 findings confirmed as real code/spec bugs. No false positives detected.
