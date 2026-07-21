# Quality Playbook v1.7.0 — Design Document

*Status: drafted 2026-05-03 as part of the v1.5.5 roadmap pass. Implementation begins after v1.6 ships (Requirements Review feature).*
*Authored: 2026-05-03*
*Owner: Andrew Stellman*
*Depends on: v1.5.4 measurement infrastructure (cell.json schema, recall computation, calibration log), v1.5.5 orchestration infrastructure (run-state instrumentation, calibration cycle orchestrator), v1.6 Requirements Review (defect data feed for SPC over the requirements-derivation process)*

> **Where v1.7 sits in the arc.** v1.5.x shipped quality-control infrastructure: how to find bugs and validate skill prose. v1.6 ships requirements-review infrastructure: how to refine the requirements QPB derives, with operator-driven validation and targeted re-derivation. v1.7 ships the **statistical process control machinery** that turns "we did calibration cycles and tracked deltas" into "we have control limits, we know when a process is in control vs. drifting, and we can detect special-cause variation." It does this for two processes simultaneously: the improvement loop (which lever pulls actually shift recall, and how reliably) and the SDLC itself (the development process for QPB, with its 61+ cataloged defects and 38+ process changes). v1.8+ then begins the cross-operator extensions on top of statistical control.

---

## Motivation

### The improvement loop and the SDLC are both processes whose performance can drift

QPB has been running calibration cycles since v1.5.4 — Pattern 7 was the first lever pull, with one measured cycle producing a +0.20 recall delta and two displacement regressions. That data lives in `metrics/regression_replay/<timestamp>/cell.json` files and `docs/process/Lever_Calibration_Log.md` entries. As the v1.5.5 autonomous-loop infrastructure landed, the cycle cadence becomes regular rather than ad-hoc.

In parallel, the SDLC for QPB itself produces measurable defect data: 61 cataloged defects (D-001 through D-061) and 38 process changes (C-001 through C-038) preserved in `Quality Playbook/Reviews/QPB_Process_Defect_Baseline.md`, with defect-class distributions, defect-to-change ratios stable around 1.3-1.8, and a 55% within-Phase-D recurrence rate of older defect classes. That's process-improvement data with the same shape as classical SEI/Humphrey TSP data: defect rates per release, defect-class trends, recurrence indicators that suggest rules are being lost between sessions.

Both processes have been **measured** (the data exists) but neither has been **statistically controlled** (we don't know which observed variations are signal vs. random noise around a stable mean). The v1.5.4 IMPROVEMENT_LOOP.md explicitly committed to a "moving toward statistical control" framing — instrumented and trend-aware, not yet under formal SPC. v1.7 closes that gap.

### What "statistical process control" means here, plainly

Walter Shewhart's 1931 framing: a process has random variation (common cause) and exceptional variation (special cause). A process is "in statistical control" when only common cause is present — the variation has a stable distribution, control limits can be computed, and any observation outside the limits indicates a special cause worth investigating.

Applied to QPB:
- **Improvement loop:** when we pull a lever and observe a recall delta, is the delta within the random-variation envelope of running the same playbook on the same target twice (no lever change), or is it a real shift? Without the envelope, +0.20 looks meaningful and +0.04 looks like noise — but we haven't measured the within-cell variance to know where the threshold actually is. The current 0.05 noise floor is an estimate, not a measured control limit.
- **SDLC:** when defect-rate goes up release-over-release, is it because the codebase grew (proportional, common-cause), because a new defect class appeared (special-cause, investigate), or because the AI making mistakes is fatigue-correlated (special-cause with a particular pattern)? The defect catalog has the data; the analysis tools don't yet.

v1.7 builds the analysis tools.

### Why this is a v1.7 deliverable, not a v1.6 sub-feature

Three reasons:

1. **The data takes time to accumulate.** Control charts need a base of observations before control limits can be computed. v1.5.4 has one cycle. v1.5.5 will produce more once the Pattern 7 cycle runs in v1.5.6. v1.6 will produce REQ-review-defect data. By the time v1.7 starts, there should be enough cells to compute meaningful baselines. Building the SPC machinery before there's data to feed it is premature.

2. **The orchestration substrate has to be in place first.** v1.5.5 makes calibration cycles routine; v1.7 assumes that routine. If cycles still required heavy operator intervention (the v1.5.4 baseline), the data accumulation rate would be too low to support SPC. v1.5.5 is a prerequisite.

3. **v1.6's Requirements Review produces a new data class.** Inspection-yield numbers from REQ review sessions are a separate data stream from bug-recall numbers. v1.7's SPC framework needs to handle both — different metrics, possibly different control-chart shapes (X-bar/R for measurement, p-chart for proportion, c-chart for counts). Designing the framework to be metric-agnostic from the start is easier than retrofitting after v1.6 has already shipped its own measurement format.

### Multi-cell calibration cycles and cross-version trend tracking are part of the SPC story, not separate features

A "cell" in cell.json is one (lever, benchmark, lever-state, run) tuple. A v1.5.x calibration cycle pulls one lever and runs each of the cycle's benchmarks twice (pre- and post-lever) — that's 2 × N benchmarks = N cells per cycle.

**Multi-cell calibration cycles** generalize this: pull multiple levers in a structured experimental design (full factorial across two or three levers, fractional factorial when the lever count is high, Latin square for time-blocking), measure all combinations, and use the cell.json structured output as the design-of-experiments matrix. The SPC framework reads it and produces variance attribution: how much of the observed delta is from lever 1, lever 2, the interaction, the benchmark, the time of day, etc.

**Cross-version trend tracking** is the other axis: per benchmark, plot recall over the chronological sequence of QPB releases (v1.3.45 → v1.3.46 → ... → v1.5.4 → v1.5.5 → ...) with the historical-baseline bug count as ground truth. Trends are visible in the existing data already (the 2026-04-25 cross-repo analysis cataloged 197 BUGS.md files across 39 QPB versions and noted within-version variance). v1.7 makes the trend-tracking continuous and adds control limits.

These two are both **using the SPC framework** — neither is a separate deliverable. Multi-cell cycles are an experimental-design layer over the existing calibration cycle. Cross-version tracking is a longitudinal view over the cell.json archive. Both are part of how v1.7 actually demonstrates SPC working.

### The framework's first proof point is QPB's own development workflow

This is the recursive part: v1.7 builds an SPC framework, and v1.7's first use of that framework is to evaluate the SPC framework's own implementation under the framework's rules. The 61-defect baseline document is the input data; the SDLC change history (38 process changes) is the intervention timeline; the v1.5.4 Pattern 7 cycle and onward are improvement-loop control-chart points.

If the framework can detect that QPB's Phase D (autonomous AI orchestration regime, ~late April 2026 onward) has a 55% recurrence rate of older defect classes — a statistically detectable special-cause variation — that's the framework's first validated finding. If it can't, the framework needs more data or different chart types.

This isn't dogfooding for its own sake; it's the only way to test whether the framework is calibrated correctly. Adopters running their own calibration cycles in v1.8+ will have less data than QPB has on itself. If the framework produces honest results on QPB's own development data, it'll produce honest results on theirs.

---

## Scope

### Core deliverables

1. **`bin/spc_lib.py`** — pure-stdlib (plus optional numpy/scipy if available) library implementing classical SPC chart types: X-bar/R for measurements with subgroups, p-chart for proportion data, c-chart for counts of defects per unit, X/MR (individuals + moving range) for single observations. Plus a small set of run rules (Western Electric / Nelson) for detecting out-of-control patterns: single point beyond control limits, runs above/below the centerline, trends.

2. **Multi-cell calibration cycle support** in `agents/calibration_orchestrator.md` and the cell.json schema (`metrics/regression_replay/SCHEMA.md`). New cycle types: `single-lever` (current v1.5.5 default), `factorial` (full or fractional), `latin-square` (time-blocked). The orchestrator template gains step variants for each. cell.json gains `cycle_design`, `factor_levels`, `factor_values` fields.

3. **Cross-version trend tracking pipeline** at `bin/cross_version_trends.py`. Reads every `quality/BUGS.md` in `repos/archive/<benchmark>/quality/previous_runs/<version>/` plus every `quality/BUGS.md` in cycle outputs. For each benchmark, produces a recall trajectory (time-series across QPB versions) and a defect-class trajectory (counts per defect category across versions). Outputs a per-benchmark JSON summary plus rendered control charts via `bin/visualize_calibration.py`.

4. **SDLC defect-rate dashboard** at `bin/sdlc_defect_dashboard.py`. Reads `Quality Playbook/Reviews/QPB_Process_Defect_Baseline.md` (or its successor structured-data form, see "Schema work" below) and produces: defect-rate per phase boundary, defect-class distribution per SDLC version, change-event timeline, recurrence-rate moving average, control charts with run-rule annotations.

5. **Schema work**: convert the prose-based defect catalog (`QPB_Process_Defect_Baseline.md`) into structured JSON-LD or similar machine-readable form so the dashboard reads canonical data rather than parsing markdown. Schema lives at `metrics/sdlc_defects/SCHEMA.md`. Migration utility at `bin/migrate_defect_baseline.py` does a one-time conversion preserving the prose narrative as commentary fields.

6. **Two new orientation-doc additions to `ai_context/`**: `STATISTICAL_CONTROL.md` (operator-facing primer on what control charts QPB uses, how to read them, when to investigate special causes) and `SDLC_CONTROL_PROTOCOL.md` (procedure for adding a new defect to the catalog, classifying it, computing whether it's a special-cause signal, and deciding whether to add a process change).

### Operating principles

- **Multiple chart types, no one-size-fits-all.** SPC has different chart types for different data shapes. v1.7 implements the four most common (X-bar/R, p-chart, c-chart, X/MR) and documents which type fits each QPB metric.
- **Run rules are warnings, not blockers.** Special-cause signals trigger investigation, not automatic process change. The SDLC protocol explicitly requires human (or AI orchestrator) judgment before adding a rule.
- **Honest framing on small-sample limits.** Control limits computed from small samples (< 20 observations) are estimates. The dashboard surfaces sample size and confidence-interval width alongside the charts; nothing is presented as more certain than the data supports.
- **Defect catalog is the canonical input.** The 61-defect baseline + ongoing additions is the single source of truth for SDLC SPC. Charts derive from it; the catalog is not derived from charts.
- **Multi-cell cycles use design-of-experiments rigor.** Factorial designs explicitly call out the experimental structure in cell.json. The SPC framework reads the design when computing variance attribution. Mismatched designs (e.g., partial factorial without acknowledging it) are flagged before analysis runs.

### Out of scope (deferred to v1.7.x point releases or v1.8)

- **Cross-operator data sharing.** That's v1.8 — multiple operators contributing to a shared SPC database. v1.7 is single-operator (Andrew's QPB development) only.
- **Real-time SPC dashboards.** v1.7 produces static charts on demand. Live dashboards are v1.7.x.
- **Automated process-change drafting.** v1.7 surfaces special-cause signals and supports human investigation. It doesn't write the next process change for you. v1.8+ may explore that, with appropriate caveats about AI-driven self-modification of the SDLC.
- **Causal inference beyond DoE structure.** v1.7 attributes variance using the experimental design; it doesn't infer causal relationships from observational data alone. That requires a much more careful epistemic stance and is at minimum v1.9.

---

## Design

### Improvement-loop SPC

**The metric:** recall delta per (lever, benchmark) cell, measured against historical baseline.

**The chart type:** X/MR (individuals + moving range) is the natural fit because each cell is one observation, not a subgroup. The moving range across consecutive cells gives the within-process variance estimate.

**Control limits:** computed from the running mean ± 2.66 × MR-bar (the standard X/MR formula). Initial limits are estimated from the first 10-15 cells; recomputed every 5 cells thereafter to account for accumulating data.

**What the framework does with new data:** every cell.json that lands in `metrics/regression_replay/<timestamp>/` triggers a re-evaluation. The dashboard plots the new cell, applies the run rules, and emits a Special-Cause Investigation Note if any rule fires. The note is added to `docs/process/Lever_Calibration_Log.md` for operator review.

**What multi-cell cycles change:** instead of one cell per cycle, a factorial design produces 2^k or 2^(k-p) cells. The SPC framework reads `cycle_design` from cell.json and computes lever main effects, lever interactions, and residual variance. The experimental-design layer is implemented in `bin/multi_cell_doe.py`; the SPC layer in `bin/spc_lib.py`.

### SDLC SPC

**The metrics, plural:**
- **Defect rate per release** (defects-introduced-per-release / commits-per-release) — c-chart shape.
- **Defect-class proportions** per release (proportion of defects that are class X) — p-chart shape per class.
- **Recurrence rate** (proportion of new defects that match an older defect class) — p-chart over a sliding window.
- **Days-between-defects** moving average — X/MR shape on time intervals.
- **Process-change-to-defect ratio** (changes per defect introduced) — X/MR shape.

**The intervention timeline:** 38 process changes (C-001 through C-038) with timestamps. Charts annotate each change as a vertical line with hover-text describing the change. Operator can visually correlate "we added rule C-026, then defect-class X stopped recurring" — the kind of pattern Watts Humphrey calls "process-improvement evidence."

**The catalog migration:** `bin/migrate_defect_baseline.py` parses the existing Markdown table and produces `metrics/sdlc_defects/<version>.json` per SDLC version, with one defect record per JSON object. Schema fields: `id`, `class`, `phase`, `date`, `triggering_event`, `triggered_change_ids`, `severity`, `recurrence_of_class`, `prose_summary`. The migration preserves all narrative as `prose_summary` so the catalog remains human-readable.

### Multi-cell calibration cycles

**Why factorial designs help:** when you suspect two levers might interact (e.g., budget cap and pattern ordering both affect attention budget), running them in a 2×2 factorial costs 4 cells and tells you whether the interaction is additive, multiplicative, or competitive. Running them sequentially as two single-lever cycles costs 4 cells too but loses the interaction information.

**Design types implemented:**
- **2-level factorial** (full or fractional). Up to 5 levers in a fractional design fits within a reasonable cell budget.
- **Latin square** for time-blocking. Useful when LLM model versions or context-cache states might confound observations across long calibration runs.
- **Augmented designs** for adding follow-up cells when the initial design surfaces a surprising interaction.

**cell.json schema additions** (additive; backward-compatible):
- `cycle_design`: one of `"single-lever"`, `"factorial-full"`, `"factorial-fractional"`, `"latin-square"`, `"augmented"`.
- `factor_levels`: array of `{factor_id, level_count, level_labels}`. E.g., `{"factor_id": "lever-1-budget-cap", "level_count": 2, "level_labels": ["low", "high"]}`.
- `factor_values`: object mapping factor_id to the level used in this cell. Required when `cycle_design != "single-lever"`.
- `design_run_index`: integer. Position in the design matrix. Used to detect missing cells.

### Cross-version trend tracking

**The data source:** `repos/archive/<benchmark>/quality/previous_runs/<version>/quality/BUGS.md` for every benchmark × every version. The 2026-04-25 cross-repo analysis already inventoried this (197 BUGS.md files across 39 versions); v1.7 makes it continuous.

**Per-benchmark trajectories:** for each benchmark, plot recall vs. version index (chronological). Recall is computed against a stable reference (typically the most-detailed historical BUGS.md for that benchmark, which becomes the ground truth). Control limits inferred from within-version replicates where available.

**Per-defect-class trajectories:** for each (benchmark, defect-class) pair, plot count vs. version. Helps detect class-level regressions invisible at the recall-aggregate level.

**Output format:** PNG charts via `bin/visualize_calibration.py` extensions, plus per-benchmark JSON summaries at `metrics/cross_version_trends/<benchmark>.json`. A combined multi-benchmark dashboard renders all benchmarks in one view with synchronized x-axis.

### SDLC defect-rate dashboard

**What it shows:** the 61-defect baseline rendered as actionable charts. Defect introduction rate per release. Defect-class distribution. Recurrence rate trending. Process-change events overlaid as interventions. Time-to-detection for each defect (how long between introduction and being cataloged).

**What it doesn't show:** opinions about whether a process is "good." The dashboard surfaces facts; the operator (or an AI doing analysis) interprets them. The dashboard is honest about limits — small-N control charts have wide confidence intervals; some defect-class counts have only 1-2 observations and shouldn't drive policy decisions.

---

## Validation

v1.7 validates by running the framework against QPB's own data:

1. **Improvement-loop SPC:** by v1.7 ship date, expect 5-10 calibration cycles in `metrics/regression_replay/`. The X/MR chart should produce sensible control limits; the dashboard should correctly identify whether any cycle was a special-cause signal vs. common-cause variation.

2. **SDLC SPC:** the 61-defect baseline plus any defects added between v1.5.5 ship and v1.7 ship. The dashboard should render all charts; the recurrence-rate chart should correctly detect Phase D's 55% recurrence as elevated relative to Phases A-C.

3. **Multi-cell calibration cycle:** at least one factorial cycle run end-to-end. Expected use case: a 2×2 factorial pulling Pattern 7 budget cap (low=2-3, high=4-5) × Pattern 7 ordering (numeric=walk-in-order, last=walk-after-others). Four cells per benchmark. The SPC framework computes main effects + interaction effect.

4. **Cross-version trends:** the 197 BUGS.md inventory rendered as multi-benchmark trend chart. Should produce visible per-benchmark recall trajectories with the v1.5.4 Pattern 7 inflection point identifiable.

If the framework can do all four with honest control-limit framing (sample-size caveats, confidence-interval widths), v1.7 ships. If any of these surfaces a fundamental design issue (e.g., the chosen chart type doesn't fit the data shape), the framework is revised before ship.

---

## Out of Scope

- **Cross-operator workflow** — v1.8.
- **Live dashboards** — v1.7.x point release.
- **Automated process-change drafting** — v1.8+ if at all.
- **Causal inference beyond DoE structure** — v1.9 at the earliest, possibly never.
- **Predictive modeling of future defects** — explicitly not pursued. SPC is descriptive (control limits on observed data); predictive modeling requires assumptions QPB's data may not support.
- **Modifying v1.6's Requirements Review feature** to produce SPC-friendly metrics. v1.7 reads what v1.6 produces; v1.6 is fixed by the time v1.7 starts.

---

## Dependencies

- v1.5.5 shipped (autonomous calibration-cycle infrastructure operational).
- v1.5.6 shipped (Pattern 7 displacement-recovery cycle ran, producing additional cell.json data).
- v1.6.0 shipped (Requirements Review feature producing inspection-yield data).
- A few hours of accumulated calibration-cycle data — multiple cycles' worth — by v1.7 implementation start. Without data, the framework can't be validated against itself.
- Defect catalog (`Quality Playbook/Reviews/QPB_Process_Defect_Baseline.md`) maintained as new defects accumulate. Adding to the catalog is the operator's responsibility per `ai_context/DEVELOPMENT_PROCESS.md`.

---

## Open Questions

1. **Which run rules to implement.** Western Electric Rules (4 rules) is the classical choice; Nelson Rules (8) is more comprehensive but more sensitive to false signals. v1.7 starts with the 4 Western Electric rules and adds Nelson rules selectively if false-signal rate is acceptable.

2. **What happens when a special-cause signal fires on a metric the operator doesn't want to act on.** Some signals will be false positives; some will be real but not actionable; some will be real and actionable but blocked by other priorities. The investigation note format needs explicit dispositions: `actionable-now`, `actionable-deferred`, `false-signal`, `accept-as-known`. Default disposition handling lives in the dashboard prose.

3. **Whether to support Bayesian credible intervals as an alternative to frequentist control limits.** Classical SPC is frequentist. Some QPB metrics (especially small-N skill-divergence counts) might be better described in Bayesian terms. v1.7 ships frequentist; Bayesian adapter is v1.7.x or v1.8.

4. **How to handle structural breaks in the data.** When a major change to the playbook (e.g., the v1.5.4 role map redesign) makes pre/post data not directly comparable, the SPC framework needs to know to start fresh control limits. Currently the schema marks this with `cycle_design: "augmented"` plus a `structural_break: true` flag, but the dashboard's handling is rudimentary. Refinement is v1.7.x.

These get resolved during the implementation Council review.
