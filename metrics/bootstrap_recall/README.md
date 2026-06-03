# `metrics/bootstrap_recall/` — per-quarter bootstrap-run bug-recall aggregates

## Status

Active since v1.5.7. Holds per-quarter aggregates of bootstrap-run
bug-recall counts and supporting trend metrics, written by
`bin/metrics_reconstruction.py`.

## File format

JSON. One file per quarter. Path convention:

```
metrics/bootstrap_recall/<YYYY>-<Q>.json
```

Where `<Q>` is `Q1`, `Q2`, `Q3`, or `Q4`. Example:
`metrics/bootstrap_recall/2026-Q1.json`.

## Schema

```json
{
  "schema_version": "1.5.7",
  "reconstruction_timestamp": "2026-05-12T17:00:00Z",
  "quarter": "2026-Q2",
  "qpb_version_at_reconstruction": "1.5.7",
  "per_benchmark": [
    {
      "benchmark": "chi",
      "cells_in_quarter": 4,
      "bug_count_total": 26,
      "bug_count_per_cell": [10, 7, 5, 4],
      "recall_against_pinned_ground_truth": [1.0, 0.7, 0.5, 0.4]
    }
  ],
  "calibration_cycle_count": 2,
  "regression_replay_cell_count": 6,
  "skipped_cells": [
    {"path": "repos/<cell>/quality/BUGS.md", "reason": "could not parse heading"}
  ]
}
```

Required fields:

- `schema_version` — `"1.5.7"` at v1.5.7 ship.
- `reconstruction_timestamp` — ISO-8601 UTC, explicit `Z`. When
  `bin/metrics_reconstruction.py` produced this file.
- `quarter` — `<YYYY>-<Q>` (matches the file basename).
- `qpb_version_at_reconstruction` — read from
  `bin/benchmark_lib.RELEASE_VERSION` at reconstruction time.
- `per_benchmark` — array of objects, one per benchmark with cells in
  the quarter. Sorted by `benchmark` (lexicographic).
- `calibration_cycle_count` — count of `metrics/calibration/*.json`
  files whose `cycle_kicked_off` falls in the quarter.
- `regression_replay_cell_count` — count of
  `metrics/regression_replay/<ts>/*.json` files whose `timestamp`
  field falls in the quarter.
- `skipped_cells` — array of `{path, reason}` objects; empty if no
  cells were skipped during reconstruction.

Per-benchmark object fields:

- `benchmark` — short name, lowercase, hyphen-free.
- `cells_in_quarter` — count of cells (one per
  `repos/<benchmark>*/quality/BUGS.md` or per archived previous_runs
  variant) the script counted in this quarter.
- `bug_count_total` — sum of `### BUG-NNN` heading counts across the
  cells.
- `bug_count_per_cell` — array of int. Same order as the cells the
  script walked (deterministic via sorted path).
- `recall_against_pinned_ground_truth` — array of float in [0, 1]. The
  pinned ground truth is the benchmark's most-detailed historical
  `BUGS.md` (per v1.7 design's cross-version trend convention).
  Computed as `len(matched_bugs) / len(ground_truth_bugs)`.

## Mutability

**Regenerable**: the reconstruction script may rewrite these files.
When it does, the prior content lands in
`metrics/bootstrap_recall/.backup-<UTC-ts>/` before the rewrite (per
the backup-on-write convention in `metrics/README.md`).

Operators should NOT edit `<YYYY>-<Q>.json` files in place — the next
reconstruction run will overwrite them. If you need to annotate a
quarter's data, write a sibling `<YYYY>-<Q>-notes.md` instead; the
script ignores `.md` files in this directory.

## Schema versioning

- v1.5.7.x patch: additive fields with safe defaults.
- v1.6+ minor: breaking changes — bump and update this README.

## Producer / consumer

- **Producer**: `bin/metrics_reconstruction.py` with
  `--quarter <Q1|Q2|both>`.
- **Consumers**:
  - v1.7's `bin/spc_lib.py` reads quarter-aggregate data points for
    trend charts (p-chart for proportion data, X/MR for individual
    observations).
  - `bin/visualize_calibration.py` may render quarter trajectories.

## Reconstruction trigger

Adopters should re-run reconstruction whenever:

- A new quarter ends (calendar-driven; the script's `--quarter both`
  re-aggregates both quarters present in the cell roster).
- A historical cell's `BUGS.md` is corrected.
- A new benchmark is added to `repos/`.
- `metrics/regression_replay/` gains new timestamped directories from
  fresh apparatus runs.
