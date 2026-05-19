# QPB v1.5.2 Self-Audit Bootstrap

## Scope

Phase 11 of the v1.5.2 implementation runs the v1.5.2 machinery against the
QPB repo itself. The three Levers (Cartesian UC rule, compensation grid,
cardinality gate) are not exercised on QPB's own quality artifacts because
QPB's `quality/REQUIREMENTS.md` carries no pattern-tagged REQs — the
cardinality gate is therefore a no-op for this self-audit and exits clean.

## Results

```
python3 .github/skills/quality_gate/quality_gate.py .
```

- **Cardinality gate (v1.5.2 Lever 3):** PASS (0 cells to reconcile; no
  pattern-tagged REQs in `quality/REQUIREMENTS.md`).
- **File existence, BUGS.md formatting, TDD sidecar JSON, integration
  sidecar, use cases, mechanical verification, patches, writeups:** all PASS.
- **Terminal gate, cross-run contamination, run metadata:** all PASS.

### Pre-existing open findings (deferred to v1.5.3 backlog)

Three FAILs surface against stale v1.4.5 artifacts from a historical
bootstrap run:

| Finding | Artifact | Current value | Expected |
|---------|----------|---------------|----------|
| Version stamp mismatch | `quality/PROGRESS.md` | `1.4.5` | matches `SKILL.md` |
| Version stamp mismatch | `quality/results/tdd-results.json` | `skill_version: 1.4.5` | matches `SKILL.md` |
| Version stamp mismatch | same as above, cross-check | `1.4.5 != 1.5.1` | same |

These are not new regressions caused by v1.5.2 work. They are pre-existing
residues of the v1.4.5 QPB self-audit bootstrap that never got re-run under
the current skill version. C14 bumps SKILL.md to `1.5.2`; after the bump the
mismatch widens mechanically. The fix is a fresh self-audit run against the
QPB repo post-C14 under the v1.5.2 SKILL, which regenerates the stamps.

Tracked for v1.5.3:
- Re-run self-audit against QPB repo under the v1.5.2 (or newer) SKILL.
- Replace stale `PROGRESS.md` and `tdd-results.json` stamps with fresh ones.

## Test suite

All static test suites pass under v1.5.2:

- `python3 -m unittest discover bin/tests` → 375 tests pass.
- `python3 -m unittest discover .github/skills/quality_gate/tests` → 177 tests pass.
- `python3 -m unittest bin.tests.test_cardinality_gate
  .CardinalityGateTests.test_adversarial_three_cells_one_cover_fails` (MERGE-GATE
  ANCHOR) → OK.

## Deferred: full Phase-1-through-6 playbook re-run

A full v1.5.2 bootstrap run of the playbook against the QPB repo itself
(Phases 1–6 with live Claude / Copilot calls) belongs to the same
operator-driven window as the v1.5.2 benchmark re-run documented in
`quality/benchmark_history.md`. It slots between C13 and C14, alongside
Council-of-Three review.
