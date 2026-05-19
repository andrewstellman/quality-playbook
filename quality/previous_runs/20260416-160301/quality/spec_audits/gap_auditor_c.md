# Spec Audit — Gap Iteration Auditor C (Security/Reliability)
<!-- Quality Playbook v1.4.1 — Gap Iteration Spec Audit — 2026-04-16 -->

## Auditor C Findings (Security/Reliability)

Focusing on: correctness guarantees, silent failures, false confidence scenarios.

### quality_gate.sh

**Line 143:** [DIVERGENT] [Req: inferred — partial session detection]
```bash
if [ -d "${q}/code_reviews" ] && [ -n "$(ls ${q}/code_reviews/*.md 2>/dev/null)" ]; then
    pass "code_reviews/ has .md files"
else
    fail "code_reviews/ missing or empty"
fi
```

This pattern is a reliability violation: it provides false assurance that code reviews exist when they don't (under nullglob + empty directory). The gate's purpose is to mechanically verify artifact conformance. A gate that can be tricked by shell configuration into reporting PASS for missing artifacts is not providing reliable conformance assurance. This is the same class of issue as BUG-M8 — a false positive from shell configuration sensitivity.

Classification: DIVERGENT — behavior diverges from "mechanically verify artifact conformance" contract.

**Line 479:** [DIVERGENT] [Req: formal — REQ-015]
Same vulnerability class: ls-glob captures CWD content under nullglob, producing unreliable extension validation results. A test file with the correct extension can fail the check; a missing test file can pass it. Both failure modes undermine reliability.

**Lines 94-673 (recheck absence):** [MISSING] [Req: formal — artifact contract table]
The absence of recheck validation creates a reliability gap for users who run recheck. A corrupted or incomplete recheck-results.json passes all gate checks. Users cannot rely on the gate to detect recheck artifacts with:
- Wrong status values (e.g., `"FIXED_BY_CHANGE"` instead of `"FIXED"`)
- Missing required fields (e.g., no `evidence` field)
- Wrong schema_version (e.g., `"0.9"` from an old template)
- Missing bugs in the results list (partial recheck)

The gate validates tdd-results.json exhaustively (lines 221-305) with enum checks, per-bug field validation, date validation, and summary validation. The same rigor should apply to recheck-results.json, which is structurally similar.

### references/review_protocols.md

**Line 410:** [DIVERGENT] [Req: formal — SKILL.md:1273]
This is a documentation reliability issue: the reference file that agents use to generate integration artifacts specifies the wrong values. The old values (`SHIP IT`, `FIX FIRST`, `NEEDS INVESTIGATION`) are human-readable prose labels; the canonical values (`SHIP`, `FIX BEFORE MERGE`, `BLOCK`) are machine-readable enum values for the JSON schema. The reference file was not updated when the schema was formalized.

Reliability impact: Agents that rely on reference files (as instructed) will systematically fail the recommendation check. This creates a false failure signal that obscures real failures — a gate that always FAILS for an irrelevant reason (wrong enum value from following instructions) produces alert fatigue that causes real failures to be ignored.

---

## Summary: Auditor C

| Finding | Classification | Reliability Impact |
|---------|---------------|-------------------|
| quality_gate.sh:143 | DIVERGENT | False pass for empty code_reviews/ under nullglob |
| quality_gate.sh:479 | DIVERGENT | Unreliable test file extension detection |
| quality_gate.sh (absence) | MISSING | No validation of recheck artifact conformance |
| references/review_protocols.md:410 | DIVERGENT | Stale enum values produce systematic gate failures |

All 4 findings are real reliability defects. Agreement: All three auditors (A, B, C) confirmed all 4 findings.
