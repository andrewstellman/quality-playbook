# quality/

Everything the Quality Playbook writes lives under this directory. v1.5.1
consolidates the layout: `control_prompts/` and the prior-run archive
(`runs/`) are both subtrees of `quality/`, not repo-root siblings.

## Layout

```
quality/
  BUGS.md                     current-run bug report
  REQUIREMENTS.md             current-run requirements
  CONTRACTS.md                behavioral contracts
  COVERAGE_MATRIX.md          traceability
  COMPLETENESS_REPORT.md      baseline + post-reconciliation verdict
  EXPLORATION.md              Phase 1 findings
  QUALITY.md                  quality constitution
  RUN_CODE_REVIEW.md          three-pass code review protocol
  RUN_INTEGRATION_TESTS.md    integration test protocol
  RUN_SPEC_AUDIT.md           Council-of-Three spec audit protocol
  RUN_TDD_TESTS.md            TDD red-green verification protocol
  formal_docs_manifest.json   v1.5.1 FORMAL_DOC records
  requirements_manifest.json  v1.5.1 REQ records
  use_cases_manifest.json     v1.5.1 UC records
  bugs_manifest.json          v1.5.1 BUG records (when bugs exist)
  citation_semantic_check.json  Phase 4 Council Layer-2 output
  INDEX.md                    current-run metadata (schemas.md §11)
  code_reviews/               per-pass code review reports
  spec_audits/                Council of Three auditor reports + triage
  writeups/                   per-bug writeups (BUG-NNN.md)
  patches/                    regression-test + fix patches
  mechanical/                 dispatch-function extraction artifacts
  results/                    sidecar JSON + per-bug red/green logs
  control_prompts/            per-phase prompt captures (v1.5.1+)
  runs/                       archived prior runs (v1.5.1+)
    <timestamp>/              one folder per archived run
      quality/                full snapshot of that run's quality/ tree
      INDEX.md                per-run metadata (schemas.md §11)
    <timestamp>-FAILED/       failed run archived via explicit CLI
    <timestamp>-PARTIAL/      partial run archived via explicit CLI
  RUN_INDEX.md                append-only index over runs/; one row per archive
```

## Per-run `INDEX.md`

Written at end of every run (success or explicit archive) by
`bin/archive_lib.archive_run` (end-of-Phase-6 hook on a clean pass) or
`bin/migrate_v1_5_0_layout.py` (backfill for pre-v1.5.1 archives). The
required fields match schemas.md §11 and are enforced by the gate:

- `run_timestamp_start`, `run_timestamp_end`, `duration_seconds`
- `qpb_version`, `target_repo_path`, `target_repo_git_sha`,
  `target_project_type`
- `phases_executed[]` — one entry per phase that ran, with `phase_id`,
  `model`, `start`, `end`, `exit_status`
- `summary.requirements` — counts by tier (1–5, plus `"unknown"` for
  legacy REQs without a `**Tier**` marker)
- `summary.bugs` — counts by severity (HIGH/MEDIUM/LOW) and disposition
  (code-fix, spec-fix, upstream-spec-issue, mis-read, deferred)
- `summary.gate_verdict` — one of `pass` / `fail` / `partial`
- `artifacts[]` — relative paths produced by the run

The file format is markdown with a fenced `json` block carrying the
structured fields (the gate parses the JSON block, not the surrounding
prose).

## Top-level `RUN_INDEX.md`

Append-only. One row per archived run: run id, QPB version, project
type, gate verdict, bug count, and a relative link to that run's
`INDEX.md`. Prior rows are never rewritten — `archive_run` appends a
new row on each invocation and is idempotent when a row for the run id
already exists.

## `results/` and timestamped files

Files written via `bin/archive_lib.write_timestamped_result` land at
`quality/results/<basename>-YYYYMMDDTHHMMSSZ.<ext>` alongside a
`<basename>-latest.<ext>` pointer (symlink on POSIX, copy on
non-symlink-capable filesystems). The `-latest` pointer always resolves
to the newest file so naive consumers can read it without scanning the
directory.

This pattern applies to recheck results, gate reports, and any other
artifact that can be regenerated multiple times during a run.

## Tracking `quality/runs/` in git — project choice

Archived runs can grow large (per-phase prompts + LLM outputs + patches
across many iterations). Whether to track `quality/runs/` is a
project-level decision:

- **Skill-template default** (`skill-template.gitignore` at the QPB
  repo root): `quality/runs/` is ignored with a `!quality/RUN_INDEX.md`
  exception. New adopters who `cat skill-template.gitignore >>
  .gitignore` don't accidentally commit bulk history while still
  tracking the top-level index for reviewers.
- **QPB's own repo**: `quality/runs/` IS tracked. The archived runs
  are canonical self-audit / bootstrap evidence — proof of work for the
  playbook itself. QPB's `.gitignore` deliberately omits the
  `quality/runs/` rule.

The template default errs on the side of small repos. If you track
runs, plan for repo size; if you ignore runs, the gate and orchestrator
still work — only the historical record moves out of version control.

## Pointers

- Data contract: `schemas.md` §11 (per-run `INDEX.md` fields) + §9
  (Council-of-Three `citation_semantic_check.json`) + §1.6 (manifest
  wrapper).
- Orchestrator: `bin/run_playbook.py` (phase execution, gate hook).
- Migration: `bin/migrate_v1_5_0_layout.py` (pre-v1.5.1 → v1.5.1 move).
- Archival: `bin/archive_lib.py` (`archive_run`,
  `write_timestamped_result`). Operator CLI:
  `python -m bin.quality_playbook archive [--status=failed|partial]`
  (dispatches to `archive_lib.main`).
- Gate: `.github/skills/quality_gate/quality_gate.py` (§10
  mechanical invariants; Layer-1 hallucination mitigation).
