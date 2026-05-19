# Code Review Protocol: quality-playbook

<!-- Quality Playbook v1.4.1 — generated 2026-04-16 -->

## Bootstrap (Read First)

Before reviewing, read these files for context:

1. `quality/QUALITY.md` — Quality constitution and fitness-to-purpose scenarios
2. `quality/REQUIREMENTS.md` — Testable requirements derived during playbook generation
3. `SKILL.md` — Primary specification and product (all phases, gate definitions, artifact contracts)
4. `quality_gate.sh` — Mechanical validation script
5. `ai_context/DEVELOPMENT_CONTEXT.md` — Architecture, version history, known issues, improvement axes

## Pass 1: Structural Review

Read `SKILL.md` and `quality_gate.sh` and report anything that looks wrong. No requirements, no focus areas — use your own knowledge of code correctness. Look for: internal contradictions, ambiguous instructions, unreachable conditions, error handling gaps, command failures that could produce wrong results silently, and any logic that looks suspicious.

### Guardrails

- **Line numbers are mandatory.** If you cannot cite a specific line, do not include the finding.
- **Read function bodies, not just signatures.** Don't assume a bash function works correctly based on its name.
- **If unsure whether something is a bug or intentional**, flag it as a QUESTION rather than a BUG.
- **Grep before claiming missing.** If you think a feature is absent, search the codebase. If found in a different file, that's a location defect, not a missing feature.
- **Do NOT suggest style changes, refactors, or improvements.** Only flag things that are incorrect or could cause failures.

### Focus Areas for Pass 1

Based on Phase 1 exploration, the following areas are high-risk and must be reviewed:

#### quality_gate.sh

1. **JSON helper functions (lines 75-91):** `json_has_key`, `json_str_val`, `json_key_count` — each has known issues. Verify: do any callers produce incorrect behavior due to these issues?
2. **Array expansion at line 697:** `REPO_DIRS=(${resolved[@]+"${resolved[@]}"})` — trace the effect of this unquoted expansion through downstream callers.
3. **`--all` mode glob at line 678:** What happens when `VERSION` is empty? Trace through to line 700-701.
4. **`set -uo pipefail` without `set -e` (line 32):** Identify all command failures that could produce wrong results silently.
5. **Functional test detection (lines 123-126):** `ls` with unquoted globs — compare with language detection (lines 449-454) which uses `find`.
6. **TDD log validation (lines 308-387):** Verify `bug_count` vs `bug_ids` consistency when headings are malformed.
7. **Date comparison (lines 278-283):** String comparison with `>` — is this documented as intentional?
8. **`&>/dev/null 2>&1` pattern (line 125 area):** Verify this is not producing unintended suppression.

#### SKILL.md

1. **"MANDATORY FIRST ACTION" vs autonomous fallback (lines ~37 and ~376):** Is there a cross-reference? Can an autonomous agent determine which applies?
2. **Phase 0/0b transition (lines 269-307):** When `previous_runs/` exists but is empty, which phase runs? Trace the logic explicitly.
3. **Phase 1 completion gate vs Phase 2 entry gate:** List all 12 Phase 1 checks and the 6 Phase 2 checks. Identify which Phase 1 checks are NOT backstopped.
4. **Version stamp references:** Find every occurrence of the version string. Are they all consistent?
5. **Artifact contract table (lines 88-119) vs gate checks:** For each "Required: Yes" artifact, verify the gate actually fails if it's missing.

### Output

For each file reviewed:

#### quality_gate.sh
- **Line NNN:** [BUG / QUESTION / INCOMPLETE] Description. Expected vs. actual. Why it matters.

#### SKILL.md
- **Line NNN:** [BUG / QUESTION / INCOMPLETE] Description. Expected vs. actual. Why it matters.

---

## Pass 2: Requirement Verification

Read `quality/REQUIREMENTS.md`. For each requirement, check whether the code satisfies it. This is a pure verification pass — your only job is "does the code satisfy this requirement?"

Do NOT also do a general code review. Do NOT look for other bugs. Do NOT evaluate code quality. Just check each requirement.

For each requirement, report one of:
- **SATISFIED**: The code implements this requirement. Quote the specific code.
- **VIOLATED**: The code does NOT satisfy this requirement. Explain what the code does vs. what the requirement says. Quote the code.
- **PARTIALLY SATISFIED**: Some aspects implemented, others missing. Explain both.
- **NOT ASSESSABLE**: Can't be checked from the files under review.

### Minimum evidence rule

Pass 2 must cite at least one code location (file:line or file:function) **per requirement**. Blanket satisfaction claims without per-requirement code citations do not satisfy Pass 2.

### Output

For each requirement:

#### REQ-NNN: [requirement title]
**Status**: SATISFIED / VIOLATED / PARTIALLY SATISFIED / NOT ASSESSABLE
**Evidence**: [file:line] — [code quote]
**Analysis**: [explanation]
[If VIOLATED] **Severity**: [impact description]

---

## Pass 3: Cross-Requirement Consistency

Compare pairs of requirements that reference the same component, function, or behavior. For each pair, check whether their constraints are mutually consistent.

### Pairs to check

Based on the requirements derived for this project, verify consistency between:

1. **REQ-001 vs REQ-007**: Both involve JSON validation helpers. Do they agree on what the helpers should do? Is REQ-001's "must not match string values" consistent with REQ-007's "must distinguish absent from non-string"?

2. **REQ-002 and all requirements referencing quality_gate.sh**: If paths with spaces corrupt the array at line 697, do any other requirements that depend on REPO_DIRS also become violated?

3. **REQ-003 (Phase 2 gate) vs REQ-010 (exploration depth)**: If Phase 2 gate enforces only 6 of 12 Phase 1 checks, does REQ-010's requirement become unenforceable mechanically?

4. **REQ-004 (regression test file) vs REQ-009 (version stamps)**: If a regression test file is missing, would the gate catch it? Is REQ-004 enforced before or after version stamp checks?

5. **REQ-005 (Phase 0b empty dir) vs REQ-003 (Phase 2 gate)**: These are both specification gaps. Are they independent, or does fixing one require fixing the other?

6. **REQ-006 (version consistency) vs REQ-009 (version stamps)**: Are these the same requirement stated differently, or do they cover different failure modes? If the JSON example is stale (REQ-006 failure), does REQ-009 automatically fail too?

7. **REQ-012 (empty VERSION) vs REQ-002 (path handling)**: Both involve the `--all` mode. Are there interactions between empty VERSION and path-with-spaces corruption?

8. **REQ-013 (no empty mechanical/) vs REQ-003 (Phase 2 gate)**: Does the Phase 2 gate check for the mechanical/ directory? Is this consistent with REQ-013's constraint?

### Output

For each pair:

#### Shared Concept: [name]
**Requirements**: REQ-X, REQ-Y
**What REQ-X claims**: [summary]
**What REQ-Y claims**: [summary]
**Consistency**: CONSISTENT / INCONSISTENT
**Code evidence**: [quotes from both locations]
**Analysis**: [explanation]
[If INCONSISTENT] **Impact**: [what happens when the contradiction is triggered]

---

## Combined Summary

| Source | Finding | Severity | Status |
|--------|---------|----------|--------|
| Pass 1 | [structural finding] | [severity] | BUG / QUESTION |
| Pass 2, REQ-N | [requirement violation] | [severity] | VIOLATED |
| Pass 3, REQ-X vs REQ-Y | [consistency issue] | [severity] | INCONSISTENT |

- Total findings by pass and severity
- Overall assessment: SHIP IT / FIX FIRST / NEEDS DISCUSSION

## Output Directory

Write the code review report to: `quality/code_reviews/code_review_<date>.md`

---

## Pre-Run Seed Bug Check

The following bugs were identified in Phase 1 exploration. The code review must check each one and either confirm (CONFIRMED BUG) or reject (NOT REPRODUCED) each finding:

| Bug ID | File:Line | Description | What to Check |
|--------|-----------|-------------|---------------|
| BUG-H1 | quality_gate.sh:75-78, 88-91 | json_has_key matches keys in string values | Run `json_has_key "id"` on a file where "id" appears only in a string value. Does it return true? |
| BUG-H2 | quality_gate.sh:697 | Unquoted array expansion corrupts paths with spaces | Trace `REPO_DIRS=(${resolved[@]+"${resolved[@]}"})` — is the outer expansion unquoted? |
| BUG-M3 | SKILL.md ~line 847/897 | Phase 2 entry gate does not enforce checks 8, 10, 12 | Count and compare Phase 1 gate checks vs Phase 2 gate checks. List exactly which checks are missing. |
| BUG-M4 | quality_gate.sh:480, SKILL.md:94 | test_regression.* not checked by gate | Check if gate_regression test file existence is enforced. Compare with artifact contract table. |
| BUG-M5 | SKILL.md ~lines 269-307 | Phase 0b skips when previous_runs/ exists but empty | Read Phase 0/0b logic. What happens when previous_runs/ exists but has no subdirectories? |
| BUG-L6 | quality_gate.sh:81-85 | json_str_val returns empty for non-string values | What error message does the gate produce when schema_version is a number rather than string? |
| BUG-L7 | SKILL.md lines 6, 39, 129, ~916 | Version hardcoded in multiple locations | Count all occurrences of the version string. Are they all identical? |
