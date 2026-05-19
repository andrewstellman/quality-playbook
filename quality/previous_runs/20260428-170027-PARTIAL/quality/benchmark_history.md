# QPB Benchmark History

## v1.5.2 — reference_docs refactor + Levers 1–3

### Migration validation (executed in C4)

The four v1.5.1 benchmark repos that carried `formal_docs/` content were
migrated in place to the new `reference_docs/cite/` layout, re-ingested with
`bin/reference_docs_ingest.py`, and re-run against `quality_gate.py`:

| Repo                  | Records ingested | Gate result |
|-----------------------|------------------|-------------|
| virtio-1.5.1          | 6                | PASS (0 FAIL, 2 WARN) |
| chi-1.5.1             | 17               | PASS (0 FAIL, 1 WARN) |
| casbin-1.5.1          | 8                | PASS (0 FAIL, 0 WARN) |
| bus-tracker-1.5.0     | 9                | PASS (0 FAIL, 0 WARN) |

The virtio-1.5.1 manifest required three REQs (REQ-003, REQ-006, REQ-007) to
be re-tiered from 2→1 because the `.meta.json` sidecar mechanism that assigned
Tier 2 is gone in v1.5.2; `cite/` contents now default to Tier 1 absent an
explicit `<!-- qpb-tier: 2 -->` marker. The retier preserves the gate contract
while the folder rename propagates.

### Full v1.5.2 benchmark re-run (operator-driven)

Before v1.5.2 ships, an operator must run the full playbook against freshly
regenerated benchmark repos at the new version. The steps are:

1. After C14 bumps `SKILL.md` to `version: 1.5.2`, regenerate benchmark
   scaffolds:

       ./repos/setup_repos.sh virtio chi cobra

2. Drop the preserved `reference_docs/` content into each new target (copy
   from the v1.5.1 directories migrated in C4, or freshly curate).

3. Run the playbook end-to-end with all four iteration strategies:

       python3 bin/run_playbook.py repos/virtio-1.5.2 repos/chi-1.5.2 repos/cobra-1.5.2 --full-run

4. Record the acceptance checks here:

   - **virtio-1.5.2** RING_RESET-family cell coverage target: ≥6 via Covers +
     downgrades. Cardinality gate must pass.
   - **chi-1.5.2** / **cobra-1.5.2** bug counts within ±15 % of the v1.5.1
     baselines.

The operator-driven step is gated to C14 because:

- The SKILL.md version bump in C14 is what makes `setup_repos.sh` emit
  `virtio-1.5.2`, `chi-1.5.2`, `cobra-1.5.2` directories.
- The full playbook run depends on live Claude / Copilot model access and
  takes 30–90 minutes per repo — not a Claude Code inline operation.
- Council-of-Three review (Phase 10, per the handoff) slots between C13 and
  C14 and consumes whatever benchmark evidence the operator generates.

## v1.5.1 — see `quality/benchmarks/README.md`

Phase 7 benchmark runbook.

## v1.5.0 — see `quality/benchmarks/v1.5.0-vs-v1.4.6.md`

v1.5.0 vs v1.4.6 comparative benchmark.
