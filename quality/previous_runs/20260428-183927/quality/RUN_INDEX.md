# QPB RUN_INDEX

Append-only index of every archived run under `quality/runs/`. One row
per archived run. Maintained by `bin/migrate_v1_5_0_layout.py` at
migration time and by the orchestrator's `archive_run()` at run time.
Rows are never rewritten; a run's `INDEX.md` is the authoritative per-run
record.

| Run | QPB version | Project type | Gate verdict | Bug count | Per-run INDEX |
|-----|-------------|--------------|--------------|-----------|----------------|
| 20260418-193542 | 1.4.1 | Code | pass | 25 | [INDEX.md](quality/runs/20260418-193542/INDEX.md) |
| 20260428-131715-PARTIAL | 1.4.5 | Code | partial | 0 | [INDEX.md](quality/runs/20260428-131715-PARTIAL/INDEX.md) |
