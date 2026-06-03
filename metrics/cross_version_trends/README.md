# `metrics/cross_version_trends/` — per-benchmark cross-version recall + defect-class trajectories

## Status

Scaffolded at v1.5.7. The reconstruction script
(`bin/metrics_reconstruction.py`) seeds initial per-benchmark
trajectory files from current cell-roster data. v1.7's
`bin/cross_version_trends.py` is the canonical producer once it ships
— it consumes the same input shape and writes additional fields per
the v1.7 design.

The directory naming aligns with v1.7's `bin/cross_version_trends.py`
output naming (Phase 1 of v1.5.7 renamed an earlier
`cross_version_recall/` proposal to match v1.7 — see
`docs/design/QPB_v1.5.7_Design.md` Deliverable 4).

## File format

JSON. One file per benchmark. Path convention:

```
metrics/cross_version_trends/<benchmark>.json
```

Example: `metrics/cross_version_trends/chi.json`.

## Schema

```json
{
  "schema_version": "1.5.7",
  "reconstruction_timestamp": "2026-05-12T17:00:00Z",
  "qpb_version_at_reconstruction": "1.5.7",
  "benchmark": "chi",
  "ground_truth": {
    "version": "1.3.45",
    "bug_count": 10,
    "path": "repos/chi-1.3.45/quality/BUGS.md"
  },
  "versions_observed": [
    {
      "version": "1.3.45",
      "qpb_version": "1.5.4",
      "cell_count": 1,
      "bug_count_avg": 10,
      "recall_against_ground_truth": 1.0,
      "cells": ["metrics/regression_replay/20260501T231500Z/chi-1.3.45-1.3.45-all.json"]
    },
    {
      "version": "1.5.1",
      "qpb_version": "1.5.7",
      "cell_count": 1,
      "bug_count_avg": 7,
      "recall_against_ground_truth": 0.7,
      "cells": ["repos/chi-1.5.1/quality/BUGS.md"]
    }
  ],
  "per_defect_class": [
    {
      "class": "mounted-middleware composition",
      "by_version": [
        {"version": "1.3.45", "count": 4},
        {"version": "1.5.1", "count": 2}
      ]
    }
  ]
}
```

Required fields:

- `schema_version` — `"1.5.7"` at v1.5.7 ship.
- `reconstruction_timestamp` — ISO-8601 UTC, explicit `Z`.
- `qpb_version_at_reconstruction` — from `bin/benchmark_lib.RELEASE_VERSION`.
- `benchmark` — short name, lowercase, hyphen-free.
- `ground_truth.{version, bug_count, path}` — the most-detailed
  historical `BUGS.md` for the benchmark (per v1.7 design's stable-
  reference convention). Determined as the version with the highest
  `### BUG-NNN` count when the script runs; ties broken by lowest
  version string (lexicographic).
- `versions_observed` — array of objects, one per observed historical
  version. Sorted by `version` (lexicographic).

Optional fields:

- `per_defect_class` — populated by v1.7's
  `bin/cross_version_trends.py`. v1.5.7's reconstruction script
  leaves the array empty (defect-class extraction requires the v1.7
  defect catalog at `metrics/sdlc_defects/`, which v1.7 owns).

Versions-observed object fields:

- `version` — the benchmark's historical version label.
- `qpb_version` — the QPB release that produced the cell(s) (from
  cell.json `qpb_version_under_test` when available; from
  `repos/<benchmark>-<version>` directory naming otherwise).
- `cell_count` — number of cells aggregated for this version.
- `bug_count_avg` — average `### BUG-NNN` heading count across cells.
- `recall_against_ground_truth` — `bug_count_avg / ground_truth.bug_count`.

## Mutability

**Regenerable**: the reconstruction script may rewrite these files.
Backup-on-write per the `metrics/README.md` convention. Do NOT edit in
place.

## Schema versioning

- v1.5.7.x patch: additive fields with safe defaults.
- v1.7 populates `per_defect_class` — additive, backward-compatible.
- v1.6+ minor: breaking changes — bump and update this README.

## Producer / consumer

- **Producer (v1.5.7)**: `bin/metrics_reconstruction.py` with any
  `--quarter` flag (cross-version trends are recomputed on every
  invocation; not quarter-scoped).
- **Producer (v1.7)**: `bin/cross_version_trends.py` (per v1.7 Design)
  consumes the same input shape and adds `per_defect_class`
  trajectories.
- **Consumers**:
  - v1.7's `bin/spc_lib.py` reads per-version trajectories for recall
    control charts.
  - v1.7's combined multi-benchmark dashboard renders all
    benchmark trajectories on a synchronized x-axis.

## Reconstruction trigger

Re-run reconstruction whenever a new benchmark version is added to
`repos/`, a `BUGS.md` is corrected, or a benchmark is added/removed
from `repos/`.
