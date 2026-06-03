# `metrics/sdlc_defects/` — SDLC defect catalog (v1.7-populated)

## Status

**Empty home, scaffolded at v1.5.7. v1.7 populates.**

This directory exists at v1.5.7 ship to give v1.7's
`bin/migrate_defect_baseline.py` (and the SDLC SPC dashboard) a
documented home to write into. v1.5.7's
`bin/metrics_reconstruction.py` **does not write here** — defect
catalog migration is a v1.7-owned operation that depends on the v1.7
defect-class taxonomy + the canonical prose baseline at
`docs/process/QPB_Process_Defect_Baseline.md`.

If you see no `.json` files here in a v1.5.7 checkout, that is
correct. v1.7 ship populates `<version>.json` files for each SDLC
version.

## File format (when v1.7 populates)

JSON. One file per SDLC version. Path convention:

```
metrics/sdlc_defects/<version>.json
```

Where `<version>` is the QPB SDLC version label (e.g., `1.5.7.json`,
`1.6.0.json`).

## Schema (v1.7-owned)

Per `docs/design/QPB_v1.7.0_Design.md` ("The catalog migration"
subsection):

```json
{
  "schema_version": "1.7.0",
  "qpb_version": "1.5.7",
  "defects": [
    {
      "id": "DEFECT-001",
      "class": "<one of the v1.7 defect taxonomy classes>",
      "phase": "<one of the SDLC phase classes>",
      "date": "2026-05-12",
      "triggering_event": "<short prose>",
      "triggered_change_ids": ["commit-sha-1", "commit-sha-2"],
      "severity": "<low|medium|high>",
      "recurrence_of_class": false,
      "prose_summary": "<verbatim prose from the canonical baseline>"
    }
  ]
}
```

Field semantics per `QPB_v1.7.0_Design.md` ("The catalog migration").
`prose_summary` is the verbatim narrative from
`docs/process/QPB_Process_Defect_Baseline.md` — the migration
preserves the human-readable catalog as-is and exposes the structured
fields alongside.

## Append-only

Once a SDLC version is canonicalized, its `<version>.json` file is
**frozen**. New defects discovered against an already-shipped version
append to that version's file (per v1.7's migration tool's contract);
defects discovered against an in-flight version land in the current
in-progress file.

## Producer

- **v1.7**: `bin/migrate_defect_baseline.py` does the one-time
  conversion from `docs/process/QPB_Process_Defect_Baseline.md` to
  the structured JSON form. Ongoing defects are added to the current
  in-progress `<version>.json` as they are cataloged.

## Consumer

- v1.7's SDLC SPC dashboard renders:
  - Defect introduction rate per release.
  - Defect-class distribution.
  - Recurrence rate trending.
  - Process-change events as interventions.
  - Time-to-detection per defect.

## v1.5.7 contract

- `bin/metrics_reconstruction.py` SKIPS this directory — it does not
  write, does not read for aggregation, does not produce any
  derivative artifact from this sub-directory.
- The directory's existence + this README is the entire v1.5.7
  contribution. It tells v1.7 where to write; it tells adopters why
  the directory is empty.
