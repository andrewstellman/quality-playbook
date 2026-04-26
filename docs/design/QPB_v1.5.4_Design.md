# Quality Playbook v1.5.4 — Design Document

*Status: design captured 2026-04-26; ready for implementation after v1.5.3 ships.*
*Authored: April 2026*
*Owner: Andrew Stellman*
*Depends on: `QPB_v1.5.3_Design.md` (skill-as-code project-type classifier and four-pass derivation pipeline shipping in v1.5.3); v1.5.0/v1.5.1/v1.5.2 complete*

> **Where v1.5.4 sits in the arc.** v1.5.4 is the **statistical-control machinery release** — the release that puts in place the measurement infrastructure QPB needs to do continuous quality improvement under the Walter Shewhart / W. Edwards Deming / Watts Humphrey / SEI lineage. After v1.5.4, QPB is feature-complete on the v1.5.x quality-control infrastructure and has the apparatus to make every subsequent change quantifiable. v1.6.0 then begins the QI half — using this machinery for continuous lever-pull improvement. See `ai_context/IMPROVEMENT_LOOP.md` for the QC/QI framing and the lineage.

---

## Motivation

### The improvement loop is methodology without a measurement substrate

`IMPROVEMENT_LOOP.md` describes the methodology QPB uses to improve itself: pull an improvement lever based on a missed-bug observation, measure the recall delta on the same benchmark target, ship the change if recall improves and process compliance holds, otherwise iterate or revert. The methodology is in the SEI / Humphrey / CMMI level 4-5 tradition — quantitative process management, statistical control, continuous improvement.

The methodology has been *described* through v1.5.x. It has not been *operationalized*. The lever inventory exists (Levers 1-5), the verification dimensions are defined (process compliance, outcome recall), the regression-replay concept is named — but there is no apparatus that takes "I think pulling Lever 1 will recover this missed bug" and produces a quantitative answer. Lever pulls during v1.5.x development have been informal: change a prompt, run a benchmark once, eyeball the result, ship if it looks better. That's not statistical process control; it's craft.

v1.5.4 builds the apparatus. After v1.5.4, every proposed lever pull has a measurement framework: regression replay against a pre-fix benchmark commit, recall delta computed against a documented baseline, cross-benchmark side-effect check, structured ledger entry. The framework is the prerequisite for any honest "is this metric in statistical control?" question, which is the multi-year horizon goal of the methodology.

### Why this is one release, not many

Three reasons v1.5.4 stands alone as a release rather than being woven into v1.5.5+ as scope creep:

1. **The apparatus is itself a deliverable.** `bin/regression_replay.py` plus a structured schema plus a calibration log is enough engineering work to deserve its own design, implementation, Council review, and tag. Slipping it into a future release alongside other work would conflate apparatus-building with apparatus-using, which is the same conceptual error that mixed feature releases with improvement releases earlier in the project's history.

2. **The data already exists.** 197 BUGS.md files in `~/Documents/QPB/repos/` from prior versions provide the historical regression record. The benchmark replicate harness has been accumulating within-version variance data in `repos/replicate/` since v1.5.2. v1.5.4 doesn't need new data collection — it needs to read the existing data and prove the apparatus works on it.

3. **The validation is part of the release.** Building `bin/regression_replay.py` without using it on real regressions is half a deliverable. v1.5.4 ships the apparatus AND 3-5 worked historical calibration cycles documented in a new `Lever_Calibration_Log.md`. That dual deliverable is the definition of "the apparatus has been validated to work."

### The 197 BUGS.md provenance is real ground truth

A 2026-04-25 cross-repo analysis (preserved at `~/Documents/AI-Driven Development/Quality Playbook/Cross-Repo Analysis/`) catalogued every BUGS.md across QPB's repo subtree. The trend tables identified specific historical regressions where bug yield dropped between adjacent versions of the same benchmark target — chi-1.3.45 → 1.3.46 (10 → 0 bugs), virtio-1.3.47 → 1.3.50 (17 → 8 bugs), express-1.3.50 (single-version 17-bug peak), express's "options-mutation" bug found by naive review but missed by structured QPB review in cross_v1.5.2, casbin-1.4.4 (51-bug outlier).

Each of these is a candidate calibration cycle for v1.5.4. The trend tables alone establish "something in QPB's process changed between these versions, in a direction that hurt recall" — the calibration cycle's job is to diagnose *which lever* changed and verify pulling it back recovers the missed bugs without harming recall elsewhere.

### Honest framing: the substrate may not cooperate

`IMPROVEMENT_LOOP.md` flags an open empirical question: SPC was developed for manufacturing processes with stable underlying causes of variation. Whether LLM-driven processes produce statistically stable variation is unsettled. v1.5.4 doesn't presume the answer — it builds the apparatus that lets the question be answered honestly over time.

If the calibration cycles consistently show that pulling a lever produces measurable, replicable recall improvements, QPB is on the SPC trajectory. If they show that lever pulls produce inconsistent results, or that the benchmark variance dominates the lever effect, that's also a finding — it tells us the substrate isn't statistically stable enough for the SEI/Humphrey methodology to apply directly, and we either need (a) tighter measurement (more replicates per cell), (b) different levers (the current inventory may not be granular enough), or (c) a different methodology entirely.

v1.5.4's success is the apparatus, not a particular outcome from running it. The cycles might validate the methodology; they might falsify it; they might leave it ambiguous and require more data. Any of those is a real result.

---

## Design

### Three deliverables

**Deliverable 1: `bin/regression_replay.py`** — single-cell replay automation. Takes a benchmark name, a QPB version under test, and a bug ID (or "all bugs from this version's run"). Checks out the benchmark target at the commit immediately before the bug's fix landed, copies in the current QPB skill installation, runs the playbook with reduced scope (likely `--phase 1,2,3` only — full iterations are overkill for replay), parses the resulting BUGS.md, and reports recall against the original bug ID.

Output: structured JSON record at `metrics/regression_replay/<timestamp>/<benchmark>-<version>-<bug>.json` recording the cell, the lever-under-test (if any), recall percentage on the original bug, recall percentage on a benchmark of related bugs (if any), cross-benchmark recall snapshot (chi/virtio/express) before and after the lever change.

**Deliverable 2: `metrics/regression_replay/SCHEMA.md`** — the structured schema for cell records. Versioned (`schema_version: "1.0"` initially) so future schema changes are explicit. Fields include the cell identification, the lever under test, the lever change summary in human-readable form, before/after recall measurements, the regression check (cross-benchmark side-effect detection), and the timestamp.

**Deliverable 3: 3-5 worked historical calibration cycles** documented in a new `Quality Playbook/Reviews/Lever_Calibration_Log.md`. Each cycle documents one historical regression, the lever pulled to address it, before/after recall on the regression-replay set AND on the broader benchmark set, and a one-paragraph narrative of the diagnostic reasoning. The cycles are validation that the apparatus works AND a reference for future calibration work — adopters can read the log to see how the methodology is actually applied, not just described.

### Schema sketch for `metrics/regression_replay/<timestamp>/cell.json`

```json
{
  "schema_version": "1.0",
  "timestamp": "2026-MM-DDTHH:MM:SSZ",
  "benchmark": "chi",
  "qpb_version_under_test": "v1.5.4",
  "historical_qpb_version": "v1.3.45",
  "historical_bug_id": "BUG-007",
  "historical_bug_count": 10,
  "current_bug_count": 7,
  "recall_against_historical": 0.7,
  "lever_under_test": "exploration_patterns",
  "lever_change_summary": "added explicit prompt guidance for HTTP middleware order-of-operations patterns",
  "before_lever": {"benchmark_recall": {"chi": 0.5, "virtio": 0.9, "express": 0.7}},
  "after_lever":  {"benchmark_recall": {"chi": 0.7, "virtio": 0.9, "express": 0.7}},
  "regression_check": "passed (no benchmark dropped beyond noise floor)",
  "noise_floor_source": "v1.5.2_pinned_variance σ=1.4 bugs"
}
```

The `noise_floor_source` field is load-bearing: it records the empirical basis for declaring a recall delta meaningful versus declaring it within noise. Without it, the apparatus would let cherry-picked single-run improvements masquerade as real lever effects. With it, the apparatus refuses to declare a 0.5 → 0.7 recall improvement as real if σ on that cell is 0.3.

### Calibration cycle candidates

The five most diagnostic candidates from the trend-table analysis:

- **Cycle 1: chi-1.3.45 → 1.3.46 collapse (10 → 0 bugs).** The cross-repo analysis flagged this as a real regression (recall delta is far outside any plausible noise floor). Run current QPB against chi at the v1.3.46-era target commit, see what we miss vs. v1.3.45's 10-bug list, diagnose which lever needs adjustment.
- **Cycle 2: virtio-1.3.47 → 1.3.50 drop (17 → 8 bugs).** Same pattern, different benchmark. Tests whether the lever adjustment from Cycle 1 generalizes.
- **Cycle 3: express-1.3.50 single-version peak (17 bugs).** Single-version peak; can current QPB recover all 17 against the same target commit? Or does the current methodology miss bugs that the v1.3.50 era found?
- **Cycle 4: express's "options-mutation" bug** that the naive review caught but QPB missed in cross_v1.5.2. Use this as a lever calibration: which lever needs adjustment for QPB to find this class of bug? The naive-review experiment is preserved at `repos/replicate/naive-review/targets/express/quality/`.
- **Cycle 5: casbin-1.4.4 outlier (51 bugs).** Most likely diagnostic for "are we missing something the v1.4.4 methodology found that we no longer have?"

Pick the 3-5 most diagnostic; not all are required. The release ships when 3+ cycles document a successful (or honestly-falsified) lever calibration.

### What v1.5.4 is not

- Not a replacement for the playbook's existing run loop. The regression-replay machinery sits beside `bin/run_playbook.py`, not inside it.
- Not a continuous-improvement workflow. v1.5.4 builds the apparatus; v1.6.0 starts using it for ongoing improvement.
- Not control charts or formal SPC limits. Those need replicate data we don't yet have at scale (~20-30 stable observations per process). v1.5.4 produces calibration cycles, not control charts.
- Not new lever discovery as a primary deliverable. The cycles work the existing five levers (1-5 in `IMPROVEMENT_LOOP.md`); if a cycle requires a new lever, document it as a v1.6.x candidate but don't expand the inventory in this release.
- Not new benchmark targets. The five pinned benchmarks (chi, virtio, express, plus cobra and casbin from the broader cross-repo set) are the working set.

---

## Success Criteria

v1.5.4 is successful if:

1. **`bin/regression_replay.py` runs end-to-end on a fresh cell.** Pick any (benchmark, version, bug_id) tuple not in the calibration log; the apparatus completes the replay and produces a valid `cell.json` matching `SCHEMA.md`.

2. **The schema is stable.** `metrics/regression_replay/SCHEMA.md` documents every field, every field's type and semantics, and the schema version. Changes to the schema after v1.5.4 follow semver-style versioning rather than breaking existing cell records.

3. **3+ calibration cycles are documented in `Lever_Calibration_Log.md`.** Each cycle has: bug missed, lever pulled (or "lever-under-test was not the right diagnosis" with notes), before/after recall on the regression-replay set, before/after recall on the broader benchmark set (must not regress elsewhere beyond the documented noise floor), and a diagnostic-reasoning narrative.

4. **Cross-benchmark regression check is operational.** The apparatus catches the case where a lever pull improves recall on the targeted benchmark but harms recall on another. Validated by deliberately running a "bad" lever pull on a fixture cell and confirming the regression check flags it.

5. **`IMPROVEMENT_LOOP.md` updated to reflect operational status.** The methodology section's reference to v1.5.4 as the operationalization milestone is updated to "operational as of v1.5.4 release"; Stage B in the trajectory subsection is marked complete; Stage C (the v1.6.0 continuous-improvement workflow) becomes the next target.

6. **No regression on code-project benchmarks.** chi-1.5.1, virtio-1.5.1, express-1.5.1 all produce yields within ±10% of the v1.5.3 baseline. v1.5.4 is apparatus work, not a feature change to the playbook itself, so a regression on these benchmarks would indicate either an accidental scope leak or a measurement artifact that needs investigation.

---

## Provenance

The methodology comes from the SEI / Humphrey / CMMI level 4-5 tradition (quantitative process management, statistical control, continuous improvement). The specific apparatus shape (single-cell replay, structured cell records, calibration cycles documented as worked examples) is adapted from the regression-test-replay practice in test-driven development plus the "design of experiments" framing from Deming.

The 197 BUGS.md provenance comes from QPB's own repo subtree, accumulated since the project's start. The cross-repo analysis at `~/Documents/AI-Driven Development/Quality Playbook/Cross-Repo Analysis/` produced trend tables documenting the regressions that motivate the cycle candidates.

The benchmark replicate harness (`repos/replicate/`) is the source of σ data that the apparatus uses as its noise floor. The harness has been accumulating data since v1.5.2 ship.

---

## Out of Scope for v1.5.4

- Control charts / formal SPC limits (need ~20-30 stable observations per process; v1.5.4 produces calibration cycles, not control limits).
- New benchmark targets beyond the pinned five.
- New lever discovery as a primary deliverable; if a cycle reveals a new lever, log it as a v1.6.x candidate but don't expand the inventory in v1.5.4.
- Fully automated continuous-improvement workflow (that's v1.6.0).
- LLM evaluation harness for semantic divergence (parked from v1.5.3; remains parked).
- Cross-model replay (running the same cycle against multiple LLM backends to measure model-specific variance). Defer to v1.6.x.

---

## Dependencies

- **v1.5.3 must ship first.** The skill-as-code feature work in v1.5.3 (project-type classifier, four-pass derivation pipeline) doesn't directly enable v1.5.4, but they're sequential because v1.5.3 closes out the QC half of the project. v1.5.4 is the first QI release.
- **v1.5.2_pinned_variance σ data is helpful but not blocking.** Calibration cycles can use single-run measurements as long as the recall delta is large (e.g., chi 10 → 0 is far outside any plausible noise floor). σ becomes critical when the cycles want to declare smaller deltas significant.
- **Naive-review results** at `repos/replicate/naive-review/targets/<target>/quality/` are useful as Cycle 4 input — concrete examples of bugs that an unstructured naive review caught and structured QPB review missed.
