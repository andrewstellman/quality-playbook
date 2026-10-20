# Requirements Refinement Protocol: zram

## How to use

This protocol reads feedback from `quality/REFINEMENT_HINTS.md` and updates `quality/REQUIREMENTS.md` surgically. It can be run with any AI model.

## Before starting

1. Read `quality/REFINEMENT_HINTS.md`.
2. Read `quality/REQUIREMENTS.md`.
3. Read `quality/CONTRACTS.md`.
4. Read `quality/VERSION_HISTORY.md`.

## Step 1: Backup and version

1. Read the current version from `quality/VERSION_HISTORY.md`.
2. Copy `REQUIREMENTS.md`, `CONTRACTS.md`, `COVERAGE_MATRIX.md`, and `COMPLETENESS_REPORT.md` into `quality/history/vX.Y/`.
3. Bump the minor version.
4. Update the header in `quality/REQUIREMENTS.md`.

## Step 2: Categorize feedback

- **Missing requirement** — add a new REQ entry at the end of the appropriate category.
- **Missing condition** — add a condition of satisfaction to an existing REQ.
- **Use case coverage gap** — update the Use Case's `Requirements:` line.
- **Vague condition** — sharpen the condition into a concrete pass/fail check.
- **Correction** — fix the specific incorrect field or reference.
- **Cross-model audit gap** — add REQs or conditions so the cited domain is truly covered.

## Step 3: Make changes

- Do not delete or weaken existing requirements during automated refinement.
- Do not renumber existing requirements unless you are intentionally re-running the full narrative pass.
- Keep changes traceable to a hint in `quality/REFINEMENT_HINTS.md`.

## Step 4: Report changes

Append a report to `quality/REFINEMENT_HINTS.md`:

```markdown
## Refinement Pass — vX.Y
Date: YYYY-MM-DD
Model: [model]

### Changes made
- REQ-NNN (NEW): ...
- REQ-NNN: Added condition of satisfaction for ...

### Feedback items not addressed
- ...

### Summary
Added N requirements, modified N requirements, updated N use cases.
```

## Step 5: Update version history

Add a row to `quality/VERSION_HISTORY.md` summarizing the pass.

## Step 6: Refresh completeness

If you added or materially changed requirements, update `quality/COVERAGE_MATRIX.md` and `quality/COMPLETENESS_REPORT.md` so the citations stay accurate.
