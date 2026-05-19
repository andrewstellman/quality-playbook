# Spec Audit — Auditor A: Strict Compliance (Unfiltered Iteration)

<!-- Quality Playbook v1.4.1 — Unfiltered Iteration Spec Audit Auditor A — 2026-04-16 -->

**Role:** Strict Compliance auditor — checking whether code satisfies every formal requirement exactly as written.
**Source:** EXPLORATION_ITER3.md + code_reviews/unfiltered_pass1.md + code_reviews/unfiltered_pass2.md
**Focus:** REQ-019, REQ-020, REQ-021 — the three new requirements from unfiltered iteration.

## Pre-audit docs validation

No supplemental `docs_gathered/` directory exists. Auditors relied on in-repo specs (SKILL.md, references/*.md) and code only. Factual baseline: SKILL.md v1.4.1, quality_gate.sh, and the iteration exploration findings.

---

## quality_gate.sh

### Line 124: MISSING [Req: formal — REQ-019]
The functional test file existence check must use find-based detection (REQ-019). The code uses:
```bash
ls ${q}/test_functional.* ${q}/FunctionalSpec.* ${q}/FunctionalTest.* ${q}/functional.test.* &>/dev/null 2>&1
```
Spec says: find-based detection not vulnerable to nullglob. Code does: ls-glob that under nullglob lists CWD. Condition is missing: no find-based existence check exists at line 124. The fix is at the same location: replace with `find "${q}" -maxdepth 1 \( -name "test_functional.*" -o -name "FunctionalSpec.*" -o -name "FunctionalTest.*" -o -name "functional.test.*" \) -print -quit 2>/dev/null | grep -q .`

### Lines 184, 188-194, 313: DIVERGENT [Req: formal — REQ-020]
The heading regex must match severity-prefix IDs (`BUG-H1`). Spec says: regex must match `BUG-H1`, `BUG-M3`, `BUG-L6` format. Code does: regex `BUG-[0-9]+` which requires pure numeric suffix — never matches severity-prefix format. This is not a missing feature; the feature EXISTS but with wrong behavior (the regex is present and functioning, just matching the wrong pattern).

Two affected locations:
- Line 184: `grep -cE '^### BUG-[0-9]+'` — sets bug_count to 0 for severity-prefix BUGS.md
- Line 313: `grep -oE 'BUG-[0-9]+'` — produces empty bug_ids list for severity-prefix BUGS.md

### Lines 239-248, 307-387: MISSING [Req: formal — REQ-021]
Cross-validation between tdd-results.json `red_phase` values and log file first-line tags is mandated by REQ-021 and SKILL.md:1589. No such cross-validation code exists in quality_gate.sh. Lines 239-248 validate JSON field PRESENCE. Lines 307-387 validate log tag FORMAT. Neither section compares them. The consistency check is entirely absent.

---

## SKILL.md

### Line 1615: DIVERGENT [Req: formal — REQ-020]
SKILL.md:1615: "Each confirmed bug must use the heading level `### BUG-NNN` (e.g., `### BUG-001`)." The example `BUG-001` uses numeric-suffix format, which is the format the gate enforces. But QFB's own Phase 3 generates severity-prefixed IDs (`BUG-H1`) based on the severity classification. The spec example contradicts QFB practice.

### Line 1965: DIVERGENT [Req: formal — BUG-L10, REQ-018]
Recheck template uses `schema_version: "1.0"` while all other sidecar JSON uses `"1.1"`. (Already confirmed as BUG-L10.)

---

## Summary

| Finding | Classification | Requirement |
|---------|---------------|-------------|
| quality_gate.sh:124 — ls-glob existence check | MISSING | REQ-019 |
| quality_gate.sh:184,313 — BUG-[0-9]+ regex wrong | DIVERGENT | REQ-020 |
| quality_gate.sh — TDD cross-validation absent | MISSING | REQ-021 |
| SKILL.md:1615 — example contradicts practice | DIVERGENT | REQ-020 |
| SKILL.md:1965 — schema_version "1.0" | DIVERGENT | BUG-L10, REQ-018 |

**Total: 5 findings (3 net-new vs prior iterations)**
