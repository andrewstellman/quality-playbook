# `metrics/regression_replay/` — per-cell regression-replay records

## Status

Active since v1.5.4. Owned by `bin/regression_replay.py`. Consumed by
calibration narrative (`docs/process/Lever_Calibration_Log.md`),
cross-benchmark regression check (Phase 8 of the v1.5.4 design), and
v1.7's SPC machinery.

## File format

JSON. One file per cell. Path convention:

```
metrics/regression_replay/<run_timestamp>/<benchmark>-<version>-<bug_id>.json
```

- `<run_timestamp>` — compact UTC ISO-8601 (`YYYYMMDDTHHMMSSZ`).
- `<benchmark>` — short benchmark name, lowercase, hyphen-free.
- `<version>` — the historical QPB-target version of the benchmark.
- `<bug_id>` — `BUG-NNN` or literal `all` for full-set recall.

Example: `20260501T231500Z/chi-1.3.45-1.3.45-all.json`.

## Schema

Canonical schema documented in `SCHEMA.md` (this directory). Current
schema version: `1.5.4` (with additive v1.7 fields `cycle_design`,
`factor_levels`, `factor_values`, `design_run_index` declared in the
v1.7 design — backward-compatible).

Required top-level fields summarized:

- Identity: `schema_version`, `timestamp`, `benchmark`,
  `qpb_version_under_test`, `historical_qpb_version`.
- Bug measurement: `historical_bug_id`, `historical_bug_count`,
  `current_bug_count`, `current_bug_ids`, `recovered_bug_ids`,
  `missed_bug_ids`, `spurious_bug_ids`, `recall_against_historical`.
- Lever attribution: `lever_under_test`, `lever_change_summary`,
  `before_lever`, `after_lever` (may be `null` for baseline cells).
- Cross-benchmark regression check: `regression_check.{status,
  checked_cells, regressed_cells, noise_floor_threshold}`.
- Apparatus reproducibility: `apparatus.{qpb_commit_sha,
  target_commit_sha, phase_scope, iteration_strategies, runner, model,
  wall_clock_seconds}`.
- Free-form: `noise_floor_source`, `notes`.

See `SCHEMA.md` for the full field reference and the canonical
versioning discipline.

## Append-only

Once `bin/regression_replay.py` finishes writing a `<run_timestamp>/`
directory, the files are **frozen**. Re-runs of the apparatus with
equivalent parameters write a fresh timestamped directory; comparing
across timestamps is how the cross-benchmark regression check works.

Do NOT edit cells in place — that breaks reproducibility and the
cross-benchmark check's mechanical matcher.

## Schema versioning

- v1.5.4.x patch: additive fields with safe defaults. Document the
  addition in `SCHEMA.md` AND bump `schema_version` to `"1.5.4.1"`.
- v1.5.5+ minor: breaking changes (renames, removals, type changes).
  Bump `schema_version`; the cross-benchmark check must read both old
  and new schemas (or operators must re-baseline under the new schema
  before the lever change can ship).
- v1.7 additive fields: `cycle_design`, `factor_levels`,
  `factor_values`, `design_run_index`. v1.5.7 cells that lack these
  fields are valid v1.5.4 cells and pass v1.7 validators with
  defaults.

## Producer / consumer

- **Producer**: `bin/regression_replay.py` (Phase 5 of v1.5.4
  Implementation Plan).
- **Consumers**:
  - `docs/process/Lever_Calibration_Log.md` cites cells by path.
  - The cross-benchmark regression check (Phase 8 of v1.5.4 design)
    reads cells to confirm a lever change didn't degrade unrelated
    benchmarks.
  - v1.7's `bin/spc_lib.py` consumes the cell.json archive as
    individual-observations data for X/MR control charts.

## Reconstruction

`bin/metrics_reconstruction.py` does NOT regenerate this
sub-directory's data. Regeneration would require re-running
`bin/regression_replay.py` against the historical commits, which is
expensive and may produce subtly different results due to non-
determinism in LLM runners. The reconstruction script reads from this
sub-directory (and from `repos/`-level `BUGS.md` heading parses) to
produce aggregates in `bootstrap_recall/` and
`cross_version_trends/`; it does not write to `regression_replay/`.
