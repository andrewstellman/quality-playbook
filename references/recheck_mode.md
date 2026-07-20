# Recheck Mode — Verify Bug Fixes

*Extracted from SKILL.md in v1.5.10 (instr 052) — loaded on demand when the operator triggers recheck. SKILL.md keeps the `## Recheck Mode` heading + a pointer here.*

Recheck mode is a lightweight verification pass that checks whether bugs from a previous run have been fixed. Instead of re-running the full six-phase pipeline (60-90 minutes), recheck reads the existing `quality/BUGS.md`, checks each bug against the current source tree, and reports which bugs are fixed vs. still open. A typical recheck takes 2-10 minutes.

**When to use recheck mode:** After the user (or another agent) has applied fixes for bugs found by the playbook. The user says "recheck" or "verify the bug fixes" or "check which bugs are fixed."

**Do not use recheck mode** as a substitute for running the full playbook. Recheck only verifies previously found bugs — it does not find new ones.

## Recheck procedure

**Step 1: Read the bug inventory.**

Read `quality/BUGS.md` and parse every `### BUG-NNN` entry. For each bug, extract:
- Bug ID (e.g., BUG-001)
- File path and line number from the `**File:**` field
- Description summary (first sentence of `**Description:**`)
- Severity
- Fix patch path from `**Fix patch:**` field (e.g., `quality/patches/BUG-001-fix.patch`)
- Regression test path from `**Regression test:**` field

**Step 2: Check each bug against the current source.**

For each bug, perform these checks in order:

1. **Fix patch check.** If a fix patch exists at the referenced path, run `git apply --check --reverse quality/patches/BUG-NNN-fix.patch` against the current tree. If the reverse-apply succeeds (exit 0), the fix patch is already applied — the bug is likely fixed. If it fails, the fix has not been applied or the code has changed.

2. **Source inspection.** Open the file at the cited line number. Read the surrounding context (±20 lines). Compare what you see against the bug description. Has the problematic code been changed? Does the fix address the root cause described in the bug report?

3. **Regression test execution.** If a regression test patch exists:
   - Apply it: `git apply quality/patches/BUG-NNN-regression-test.patch`
   - Run the test (using the project's test runner). If the test PASSES, the bug is fixed. If it FAILS, the bug is still present.
   - Reverse the patch: `git apply -R quality/patches/BUG-NNN-regression-test.patch`
   
   If the regression test patch doesn't apply cleanly (because the source has changed), note this and fall back to source inspection alone.

4. **Verdict.** Assign one of these statuses:
   - **FIXED** — Fix patch is applied AND regression test passes (or source inspection confirms the fix if test can't run)
   - **PARTIALLY_FIXED** — The problematic code has changed but the regression test still fails, or the fix addresses some but not all aspects of the bug
   - **STILL_OPEN** — The original problematic code is unchanged, or the regression test still fails
   - **INCONCLUSIVE** — Can't determine status (file moved, code heavily refactored, patches don't apply)

**Step 3: Generate recheck results.**

Write `quality/results/recheck-results.json` with this schema:

Note: The recheck schema uses `"schema_version": "1.0"` (not `"1.1"`) because it has a different structure from the TDD sidecar — the `source_run` and per-bug `status`/`evidence` fields are unique to the recheck schema. The quality gate validates this value as `"1.0"`.

```json
{
  "schema_version": "1.0",
  "skill_version": "<SKILL_VERSION>",
  "date": "YYYY-MM-DD",
  "project": "<project name>",
  "source_run": {
    "bugs_md_date": "<date from BUGS.md header>",
    "total_bugs": <N>
  },
  "results": [
    {
      "id": "BUG-001",
      "severity": "HIGH",
      "summary": "<one-line summary>",
      "status": "FIXED",
      "evidence": "<what confirmed the fix — e.g., 'reverse-apply succeeded + regression test passes'>"
    }
  ],
  "summary": {
    "total": <N>,
    "fixed": <N>,
    "partially_fixed": <N>,
    "still_open": <N>,
    "inconclusive": <N>
  }
}
```

Also write a human-readable summary to `quality/results/recheck-summary.md`:

```markdown
# Recheck Results

> Recheck of quality/BUGS.md from <date>
> Recheck run: <today's date>
> Skill version: <version>

## Summary

| Status | Count |
|--------|-------|
| Fixed | N |
| Partially fixed | N |
| Still open | N |
| Inconclusive | N |
| **Total** | **N** |

## Per-Bug Results

| Bug | Severity | Status | Evidence |
|-----|----------|--------|----------|
| BUG-001 | HIGH | FIXED | Reverse-apply succeeded, regression test passes |
| BUG-002 | MEDIUM | STILL_OPEN | Original code unchanged at quality_gate.py:125 |
| ... | ... | ... | ... |

## Still Open — Details

[For each STILL_OPEN or PARTIALLY_FIXED bug, include a brief explanation of what remains to be fixed.]
```

**Step 4: Print the recheck summary.**

Print the summary table to the user, then STOP. Example:

```
# Recheck Complete

Checked 19 bugs from quality/BUGS.md against current source.

| Status | Count |
|--------|-------|
| Fixed | 17 |
| Still open | 2 |
| **Total** | **19** |

Fixed bugs: BUG-001, BUG-002, BUG-003, BUG-004, BUG-005, BUG-006, BUG-007,
BUG-008, BUG-009, BUG-010, BUG-011, BUG-013, BUG-014, BUG-015, BUG-016,
BUG-017, BUG-018

Still open: BUG-012 (stale .orig file still present), BUG-019 (benchmark 40
artifact list not updated)

Results saved to:
- quality/results/recheck-results.json (machine-readable)
- quality/results/recheck-summary.md (human-readable)
```

## Triggering recheck mode

Recheck mode activates when the user says any of: "recheck", "verify the bug fixes", "check which bugs are fixed", "recheck the bugs", "run recheck mode", or similar phrasing that clearly indicates they want to verify fixes rather than find new bugs. When triggered, skip Phases 1-7 entirely and execute only the recheck procedure above.
