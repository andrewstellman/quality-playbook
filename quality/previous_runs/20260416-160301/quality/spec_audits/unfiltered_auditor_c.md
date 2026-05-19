# Spec Audit — Auditor C: Security/Reliability (Unfiltered Iteration)

<!-- Quality Playbook v1.4.1 — Unfiltered Iteration Spec Audit Auditor C — 2026-04-16 -->

**Role:** Security/Reliability auditor — checking for failure modes that could cause silent corruption or missed defects.
**Focus:** What fails silently? What produces wrong answers without any indication?

## Pre-audit docs validation

No supplemental `docs_gathered/` exists. Factual baseline: SKILL.md v1.4.1 and quality_gate.sh source code.

---

## Systemic Analysis: Gate Bypass via ID Format

The most significant reliability finding in this iteration is the COMPLETE gate bypass caused by the BUG ID regex mismatch.

### Lines 184, 223, 309, 564, 592: PHANTOM [Req: formal — SKILL.md artifact contract]

The gate's artifact contract enforcement (TDD logs, patches, writeups) is conditioned on `bug_count > 0`. `bug_count` is set by `grep -cE '^### BUG-[0-9]+'` at line 184. For severity-prefix IDs (`BUG-H1`), this regex always returns 0.

**Phantom behavior:** The gate appears to validate TDD logs, patches, and writeups — it has code sections for each. But for any run using QFB severity-prefix IDs, ALL those sections are bypassed:
- Line 223: `if [ "$bug_count" -gt 0 ]; then` → FALSE → `info "Zero bugs — tdd-results.json not required"`
- Line 309: `if [ "$bug_count" -gt 0 ]; then` → FALSE → `info "Zero bugs — TDD log files not required"`
- Line 564: `if [ "$bug_count" -gt 0 ]; then` → FALSE → patches not checked
- Line 592: `if [ "$bug_count" -gt 0 ]; then` → FALSE → writeups not checked

The gate says "PASS" but has provided ZERO artifact validation. This is the definition of a phantom: "Spec describes it [artifact validation], but it's actually implemented differently than described [all validation bypassed]."

**Reliability impact:** HIGH. The gate is the primary quality assurance mechanism for the Quality Playbook itself. If the gate silently bypasses all validation, agents running the playbook have no mechanical verification that their TDD logs exist, patches are present, or writeups have inline diffs. All 45 benchmarks in references/verification.md that the gate is supposed to verify are unverifiable for QFB-format runs.

### Line 124: DIVERGENT [Req: formal — REQ-019]

`ls`-glob existence check fails under nullglob (already documented). The reliability concern: a CI system running quality_gate.sh on macOS/zsh with nullglob gets false PASSes for artifact existence, then ships artifacts that don't actually exist.

### Lines 307-387: MISSING [Req: formal — REQ-021]

TDD sidecar-to-log consistency check is mandated by SKILL.md:1589 as mandatory. The gate has the components (JSON validation + log validation) but never connects them. A corrupt or fabricated tdd-results.json (where the agent wrote TDD verdicts without actually running tests) passes the gate's log checks because:
1. The JSON verdict is not validated for VALUE
2. The log file tag is validated for FORMAT but not consistency with JSON

A fabricated `"verdict": "TDD verified"` alongside a real log file that says `RED` (the test confirmed the bug is open, not that it was verified fixed) passes all gate checks. This is the reliability gap that SKILL.md:1589 was written to prevent.

---

## Summary

| Finding | Classification | Severity |
|---------|---------------|----------|
| quality_gate.sh:184,223,309,564,592 — phantom validation via bug_count=0 bypass | PHANTOM | HIGH |
| quality_gate.sh:124 — false artifact existence | DIVERGENT | MEDIUM |
| quality_gate.sh:307-387 — TDD consistency check absent | MISSING | MEDIUM |

**All 3 findings are net-new from unfiltered iteration or confirm unfiltered candidates.**
**Most significant:** The phantom validation at lines 184,223,309,564,592 — the gate appears to validate but doesn't.
