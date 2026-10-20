# Requirements Review Protocol: zram

## How to use

This protocol helps review `quality/REQUIREMENTS.md` for completeness and correctness. Run it with any AI model after reading the Project Overview and Use Cases.

### Choose a review mode

**Mode 1 — Self-guided review.** Pick one use case at a time from REQUIREMENTS.md and inspect its linked REQ numbers.

**Mode 2 — Fully guided review.** Walk Use Cases 1-6 in order, then review cross-cutting concerns.

**Mode 3 — Cross-model audit.** Read `quality/COMPLETENESS_REPORT.md` and confirm that each cited REQ actually covers the domain it claims to cover.

All findings should be written into `quality/REFINEMENT_HINTS.md`.

## Use cases in REQUIREMENTS.md

1. [ ] Use Case 1: Provision a new zram device
2. [ ] Use Case 2: Tune compression behavior
3. [ ] Use Case 3: Attach and use a backing device
4. [ ] Use Case 4: Recompress cold or huge pages
5. [ ] Use Case 5: Serve block I/O
6. [ ] Use Case 6: Reset or remove a zram device

## Review prompts

### For a use case
1. Read the use case and its linked requirements.
2. Ask: "Does this capture the right kernel/user contract? Which step is most likely to regress?"
3. Record any missing requirement, vague condition, or wrong assumption in `quality/REFINEMENT_HINTS.md`.

### For an individual requirement
1. Show the full REQ entry.
2. Ask: "Does this requirement describe desired behavior or merely the current implementation?"
3. Ask: "Would a new contributor know how to test this from the conditions of satisfaction?"

### For cross-model audit
1. For each domain in `quality/COMPLETENESS_REPORT.md`, read the cited REQ numbers.
2. Verify that the cited requirements truly cover the domain.
3. Flag orphaned REQs, use-case gaps, and cross-cutting concerns that cite the wrong REQ numbers.

## What to pay extra attention to in this project

- Pre-init vs post-init sysfs ordering (`disksize`, `comp_algorithm`, `algorithm_params`, `backing_dev`, `compressed_writeback`)
- Slot-flag transitions (`SAME`, `HUGE`, `WB`, `IDLE`, `INCOMPRESSIBLE`)
- Writeback/recompression races and budget accounting
- Block-I/O completion guarantees for partial and discard requests
- Where documentation appears stricter than the code
