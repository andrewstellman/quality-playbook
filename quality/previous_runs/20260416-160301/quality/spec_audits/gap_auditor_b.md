# Spec Audit — Gap Iteration Auditor B (User Experience)
<!-- Quality Playbook v1.4.1 — Gap Iteration Spec Audit — 2026-04-16 -->

## Auditor B Findings (User Experience)

Focusing on: what do agents experience when following instructions? Where do the spec documents send agents down wrong paths?

### references/review_protocols.md

**Line 410:** [DIVERGENT] [Req: formal — SKILL.md:1273 canonical enum]
The integration test reporting template specifies three recommendation values that are wrong:
- `SHIP IT` → gate expects `SHIP`
- `FIX FIRST` → gate expects `FIX BEFORE MERGE`
- `NEEDS INVESTIGATION` → gate expects `BLOCK`

An agent that reads `references/review_protocols.md` (which is explicitly instructed in SKILL.md Phase 2) and follows its template exactly will produce a gate-failing `integration-results.json`. The agent has done everything correctly by following the instruction document, but the instruction document has stale values.

User experience impact: The agent sees a gate FAIL with "recommendation 'FIX FIRST' is non-canonical." The agent has no way to know the reference file is wrong — it followed its instructions. This creates a trust breakdown between the quality system's components.

### quality_gate.sh

**Line 479:** [DIVERGENT] [Req: inferred — from BUG-M8 fix]
In a zsh environment with nullglob enabled, the gate can emit extension mismatch errors for a functional test file that exists and has the correct extension. This happens when the ls-glob at line 479 captures a CWD filename with a different extension.

User experience impact: The developer sees "test_functional.sh does not match project language (bash)" when it does. Confusing false failure that undermines confidence in the gate.

**Line 143:** [DIVERGENT] [Req: inferred — from BUG-M8 fix]
If a playbook session terminates early (context limit, crash) after creating code_reviews/ but before writing any review content, the gate passes "code_reviews/ has .md files" when the directory is empty.

User experience impact: Developer thinks reviews were written when they weren't. Quality artifact appears present when absent.

**Recheck validation (absence):** [MISSING] [Req: formal — artifact contract table]
When an agent runs recheck mode and writes recheck-results.json, there is no gate validation. An incorrectly generated recheck-results.json (wrong status values, missing fields, wrong schema_version) goes undetected.

User experience impact: Developer cannot use the gate to verify recheck artifact quality. The gate that validates TDD results and integration results does not validate recheck results — inconsistent quality assurance coverage.

---

## Summary: Auditor B

| Finding | Classification | User Experience Impact |
|---------|---------------|----------------------|
| references/review_protocols.md:410 | DIVERGENT | Agent follows instructions but produces gate-failing artifact |
| quality_gate.sh:479 | DIVERGENT | False extension mismatch errors in zsh/nullglob environments |
| quality_gate.sh:143 | DIVERGENT | Empty code_reviews/ passes gate check — partial run undetected |
| quality_gate.sh (absence) | MISSING | Recheck artifacts not validated by gate |

All 4 findings confirmed. All affect agent and user experience negatively.
