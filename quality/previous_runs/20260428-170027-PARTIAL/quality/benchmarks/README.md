# Phase 7 Benchmark Runbook

Operator checklist for executing the live benchmark work that closes Phase 7
Tasks 2, 3, and 5. Phase 7 Tasks 0, 1, and 4 landed as commits on `1.5.1`
and gave the tooling its live-LLM hooks; this runbook walks through the
actual runs.

All commands run from the QPB repo root on branch `1.5.1`.

## Prerequisites

- `1.5.1` branch at `1ab8441` or later (Phase 7 r0/r1/r4 landed).
- Benchmark target repos accessible at known paths. QPB's benchmark set:
  virtio, chi, cobra, express, httpx. Only virtio has formal spec
  content that produces Tier 1/2 REQs; the other four are Spec Gap
  repos.
- Access to three Council members. Current roster
  (`bin/council_config.py`):
  - `claude-opus-4.7`
  - `gpt-5.4`
  - `gemini-2.5-pro`
- Full local test suite green:
  `python3 -m pytest bin/tests/ quality/test_functional.py
  quality/test_regression.py .github/skills/quality_gate/tests/` →
  512 passing.

## Task 2 — Virtio live pilot

Virtio is the only benchmark repo with Tier 1/2 content. This is the first
live exercise of the Phase 6 semantic-check pipeline end-to-end with real
LLM responses.

```
python3 -m bin.run_playbook <path-to-virtio-benchmark>
```

Follow the phase-by-phase prompts the orchestrator emits. At the end of
Phase 4, the orchestrator will print the Layer-2 semantic-check steps
(Part B of the new `phase4_prompt`):

1. Run `python3 -m bin.quality_playbook semantic-check plan <repo>`.
2. For each prompt file written to
   `<repo>/quality/council_semantic_check_prompts/`, dispatch to that
   Council member. Capture the JSON-array response to
   `<repo>/quality/council_semantic_check_responses/<member>.json`.
3. Run the assembly:
   `python3 -m bin.quality_playbook semantic-check assemble <repo>
   --member claude-opus-4.7 --response .../claude-opus-4.7.json
   --member gpt-5.4          --response .../gpt-5.4.json
   --member gemini-2.5-pro   --response .../gemini-2.5-pro.json`.
4. Verify `<repo>/quality/citation_semantic_check.json` exists.

Phases 5 and 6 continue. At end of Phase 6 the orchestrator auto-archives
the run under `<repo>/quality/runs/<ts>/`.

### Capture for the comparison report

Collect into `quality/benchmarks/v1.5.1-vs-v1.4.6.md` (see template):

- Run id and timestamp.
- Count of Tier 1/2 REQs.
- Count of review entries in `citation_semantic_check.json` (should be
  `3 × N`).
- Any `overreaches` or `unclear` verdicts (with `record_id` and
  reviewer).
- Gate `Total: N FAIL, M WARN` summary.
- Any v1.5.1-specific bug candidates surfaced by the run (these seed
  `quality/bugs_manifest.json` under the QPB project as the v1.5.1
  backlog).

### Commit

```
git add <path-to-virtio-benchmark>/quality/runs/<ts>*
git commit -m "Phase 7 r2: live virtio pilot run (Phase 6 Task 5 closure)"
```

## Task 3 — Spec Gap repo runs

Run each of chi, cobra, express, httpx the same way:

```
python3 -m bin.run_playbook <path-to-repo>
```

These four repos have no formal spec. Expected behavior:

- Phase 1 derivation produces zero Tier 1/2 REQs.
- `semantic-check plan` detects the Spec Gap and writes an empty
  `citation_semantic_check.json` directly — **no prompt dispatch
  needed**. The operator should see
  `No Tier 1/2 REQs — wrote empty ... (Spec Gap run). Skip dispatch.`
- Gate Phase 5/6 passes cleanly. Invariant #17 reports "vacuously
  satisfied" or emits the Spec Gap WARN.
- Meta-finding recorded in the run's INDEX.md: "0 Tier 1/2
  requirements."

### If a Spec Gap repo surprises you with a Tier 1/2 REQ

That's a stop condition — the REQ extractor is miscategorizing or a
documentation source crept in. Flag to Andrew before continuing. Do NOT
silently file it as a bug.

### Commit

```
git add repos/<repo>/quality/runs/<ts>*
git commit -m "Phase 7 r3: Spec Gap benchmark runs (chi, cobra, express, httpx)"
```

(One commit per repo if the runs happen on different days; one combined
commit if they run in a single session.)

## Task 5 — Comparison report

After Tasks 2 and 3 archive their runs:

1. Open `quality/benchmarks/v1.5.1-vs-v1.4.6.md`. The five repo sections
   are pre-stubbed; fill in the numbers.
2. v1.4.6 baseline data lives under
   `quality/runs/20260418-193542/` (QPB's own v1.4.6 self-audit) and —
   for the per-target repos — in each benchmark repo's archived
   `quality/runs/<ts>/` folder from before the Phase 7 runs. If those
   don't exist yet, the comparison is "v1.5.1 vs nothing"; record that
   explicitly rather than fabricating a baseline.
3. Close with the Decision section. Three legal outcomes:
   - **SHIP v1.5.1** → proceed to Phase 8 (self-audit + version bump).
   - **ITERATE** on a specific issue → new phase with scoped work.
   - **PAUSE** → Andrew review.
4. File any bugs found in v1.5.1 itself under QPB's
   `quality/bugs_manifest.json` (not under the benchmark repo).

### Commit

```
git add quality/benchmarks/v1.5.1-vs-v1.4.6.md quality/bugs_manifest.json
git commit -m "Phase 7 r5: v1.5.1 vs v1.4.6 benchmark comparison"
```

## Environment notes

- The `run_playbook` orchestrator shells out to `claude -p` / `gh copilot
  -p` / etc. A non-interactive environment without LLM access CANNOT
  execute these tasks — that's why Phase 7 commits p7r0, p7r1, p7r4
  land the tooling and p7r2/p7r3/p7r5 are the operator's.
- Budget: each full `run_playbook` cycle on a medium-size target
  takes ~30-60 minutes of LLM time. Virtio is the longest because of
  the Tier 1/2 semantic-check round-trip on top of the regular spec
  audit.
