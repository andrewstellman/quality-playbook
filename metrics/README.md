# `metrics/` — cross-cell aggregate data

The `metrics/` directory is QPB's cross-cell aggregate substrate. Each
sub-directory holds a specific data class produced by, and consumed by,
the scripts named in its own README. v1.7's SPC machinery (X-bar/R,
p-chart, c-chart, X/MR control charts + Western Electric / Nelson run
rules) reads from this tree.

Relationship to other data substrates:

- `quality/run_state.jsonl` (per-cell, event log, append-only) is the
  raw event stream within a single cell. `metrics/` is the
  cross-cell aggregate. Conversion from per-cell event logs to
  cross-cell aggregates is the job of `bin/metrics_reconstruction.py`
  (v1.5.7+) and `bin/cross_version_trends.py` (v1.7+).
- Workspace-side artifacts at
  `~/Documents/AI-Driven Development/Quality Playbook/Calibration Cycles/`
  hold *working-state* calibration material — narrative, deliberation,
  in-flight observations. When a cycle terminates, its summary lands
  in `metrics/calibration/` per the convention documented there.
  Workspace-side material does NOT migrate into the repo automatically;
  the operator promotes a cycle's terminal summary.

## Sub-directory tree

| Sub-directory | Owner | Status | Producer | Consumer |
|---------------|-------|--------|----------|----------|
| `regression_replay/` | v1.5.4+ | active | `bin/regression_replay.py` | calibration narrative, v1.7 SPC |
| `calibration/` | v1.5.7+ | active | operator promotion from workspace | v1.7 SPC, `docs/process/Lever_Calibration_Log.md` |
| `bootstrap_recall/` | v1.5.7+ | active | `bin/metrics_reconstruction.py` | v1.7 SPC trend charts |
| `cross_version_trends/` | v1.5.7+ scaffold; v1.7 populates | scaffolded | `bin/cross_version_trends.py` (v1.7) | v1.7 SPC trajectory charts |
| `sdlc_defects/` | v1.7 | scaffolded (empty home) | `bin/migrate_defect_baseline.py` (v1.7) | v1.7 SPC SDLC dashboard |

See each sub-directory's `README.md` for file format conventions,
schema versioning rules, append-only vs mutable status, and the
canonical producer/consumer scripts.

## Reconstruction

Adopters who maintain their own historical cell roster can regenerate
the cross-cell aggregates in this tree by running
`bin/metrics_reconstruction.py` from the QPB checkout root:

```
python3 bin/metrics_reconstruction.py --target metrics/ --cells-root repos/ --quarter both
```

Flags: `--target` (defaults to `metrics/` in cwd), `--cells-root`
(defaults to `repos/`), `--quarter` (one of `Q1`, `Q2`, `both`).

The script is idempotent: same inputs produce same outputs modulo
timestamp metadata. If the target sub-directory already contains data,
the existing contents are first copied to
`metrics/<sub-directory>/.backup-<UTC-ts>/` before the new
reconstruction writes. Sub-directories the script does not own
(currently `sdlc_defects/`, which v1.7 owns) are skipped.

## v1.7 alignment

The layout above is the input shape v1.7's SPC machinery reads
(`docs/design/QPB_v1.7.0_Design.md` §"What v1.7 ships"). v1.5.7's
contribution is the formalized directory tree + READMEs + the
reconstruction tool; v1.7 contributes the SPC library
(`bin/spc_lib.py`), the cross-version trends pipeline
(`bin/cross_version_trends.py`), the defect-catalog migration
(`bin/migrate_defect_baseline.py`), and the dashboards.

## Schema versioning across the tree

Each sub-directory's data files carry their own `schema_version` field
(or, for directories where the file format is markdown-tabular, the
README states the convention version explicitly). Sub-directory schema
evolution is independent: a `regression_replay/` v1.5.4 → v1.5.5
schema bump does not require any other sub-directory to bump. v1.7's
additive cell.json fields (`cycle_design`, `factor_levels`,
`factor_values`, `design_run_index`) are backward-compatible per the
v1.7 Design (§"cell.json schema additions"); v1.5.7-era cells that
lack them are valid v1.5.4 cells and pass v1.7 validators with
defaults.

## Append-only vs mutable

- `regression_replay/<timestamp>/` directories are **append-only** once
  the producing apparatus invocation finishes. Re-runs write fresh
  timestamped directories.
- `calibration/<cycle-summary>.json` files are **append-only** once
  promoted from workspace.
- `bootstrap_recall/<quarter>.json` and
  `cross_version_trends/<benchmark>.json` files are **regenerable**:
  the reconstruction script may rewrite them, and the prior content
  lands in `.backup-<UTC-ts>/` before the rewrite.
- `sdlc_defects/<version>.json` files are append-only once a SDLC
  version is canonicalized.

## UTC-timestamped ordering convention

Where directories or files carry a timestamp:

- Use compact UTC ISO-8601: `YYYYMMDDTHHMMSSZ` (e.g.,
  `20260512T141500Z`). Lexicographic sort = chronological sort.
- Never use local-time variations; cross-operator data must compose.
- When a file's content carries a separate ISO-8601 timestamp field,
  use the human-readable form: `2026-05-12T14:15:00Z` (per the
  cell.json `timestamp` field convention).
