# `metrics/calibration/` — calibration cycle terminal summaries

## Status

Active since v1.5.7. Each file is the terminal summary of one
calibration cycle, promoted from workspace-side material at
`~/Documents/AI-Driven Development/Quality Playbook/Calibration Cycles/<cycle-id>/`
once the cycle reaches a terminal verdict (`ship`, `hold-for-more-
cycles`, `lever-pull-failed`).

## File format

JSON. One file per cycle. Path convention:

```
metrics/calibration/<cycle-id>.json
```

Where `<cycle-id>` matches the workspace folder name (e.g.,
`2026-05-01-chi-1.3.45.json`, `2026-05-02-pattern7-displacement-recovery.json`).

## Schema

```json
{
  "schema_version": "1.5.7",
  "cycle_id": "2026-05-01-chi-1.3.45",
  "cycle_kicked_off": "2026-05-01T08:00:00Z",
  "cycle_terminated": "2026-05-02T17:30:00Z",
  "lever_pulled": "lever-1-exploration-breadth-depth",
  "lever_change_summary": "...",
  "verdict": "ship" | "hold-for-more-cycles" | "lever-pull-failed",
  "recall_delta_summary": "+0.30 on chi-1.3.45; clean cross-benchmark check",
  "cell_records": [
    "metrics/regression_replay/<ts-before>/chi-1.3.45-all.json",
    "metrics/regression_replay/<ts-after>/chi-1.3.45-all.json"
  ],
  "calibration_log_section": "## Cycle 1 — chi-1.3.45 (2026-05-01)",
  "workspace_artifact_path": "~/Documents/AI-Driven Development/Quality Playbook/Calibration Cycles/2026-05-01-chi-1.3.45",
  "prose_summary": "..."
}
```

Required fields:

- `schema_version` — `"1.5.7"` at v1.5.7 ship; bumps per the
  cross-tree versioning convention in `metrics/README.md`.
- `cycle_id` — matches the workspace folder name; lexicographic-
  sortable date prefix.
- `cycle_kicked_off`, `cycle_terminated` — ISO-8601 UTC with explicit
  `Z`. `cycle_terminated` is when the verdict was reached.
- `lever_pulled` — the `IMPROVEMENT_LOOP.md` lever ID, or `null` for
  baseline-only cycles.
- `verdict` — one of three enum values above.
- `cell_records` — paths (relative to repo root) to the
  `regression_replay/` cells the cycle produced. At least one entry;
  before/after pairs typically appear together.

Optional fields:

- `lever_change_summary`, `recall_delta_summary`, `prose_summary` —
  free-form. `calibration_log_section` points at the
  `Lever_Calibration_Log.md` H2 section header for cross-reference.
- `workspace_artifact_path` — informational reference to the
  workspace working-state directory.

## Append-only

Once promoted from workspace and committed, a calibration summary is
**frozen**. Updates to the prose narrative live in
`Lever_Calibration_Log.md`, not by editing the summary in place.

## Schema versioning

- v1.5.7.x patch: additive fields with safe defaults. Bump
  `schema_version` to `"1.5.7.1"`.
- v1.6+ minor: breaking changes — bump and update this README.

## Producer / consumer

- **Producer**: operator promotes from workspace. Specifically: when a
  workspace cycle directory reaches a terminal state, the operator
  authors `<cycle-id>.json` here citing the relevant
  `regression_replay/` cells and the `Lever_Calibration_Log.md`
  section.
- **Consumers**:
  - v1.7's SPC machinery reads cycle outcomes for X/MR control-chart
    points (one cycle = one observation; the chart tracks
    cycle-over-cycle recall deltas).
  - `docs/process/Lever_Calibration_Log.md` cross-references via the
    `calibration_log_section` field.

## Reconstruction

`bin/metrics_reconstruction.py` does NOT generate calibration summary
files — operator promotion from workspace is the only producer (a
mechanical script can't determine the cycle's verdict; that requires
operator judgment per `CALIBRATION_PROTOCOL.md`).

The reconstruction script DOES inventory existing summary files for
trend analysis: it counts cycles per quarter and writes the count into
`bootstrap_recall/<quarter>.json` as a `calibration_cycle_count` field
(see `bootstrap_recall/README.md`).
