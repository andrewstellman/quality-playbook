# Quality Playbook v1.8.0 — Implementation Plan

> **⚠ STALE — NEEDS A REWRITE BEFORE USE.** This document is out of date for two independent reasons and should not be used to plan or implement work as written:
>
> 1. **v1.6.0 scope has changed.** This doc describes v1.6 throughout as "the Requirements Review release" (see e.g. Phase 0's goal). v1.6.0 shipped (or is shipping) as the requirements-review release, but with a different, specific scope (Features A–D) than assumed here — see `QPB_v1.6.0_Design.md` for the actual v1.6.0 scope before relying on any v1.6-dependency claim in this document.
> 2. **A stated dependency is unsatisfiable.** This doc's header declares a dependency on "v1.5.5" (orchestration infrastructure) and Phase 0 references "the v1.5.5 convention." **v1.5.5 was cancelled** — the 1.5.x line ended at v1.5.4 and the next release was v1.6.0. That dependency cannot be satisfied as written and needs to be re-derived against whatever actually shipped between v1.5.4 and v1.6.0.
>
> *(Renumbering note, added during the 2026-07-20 mechanical sweep: this document also still refers to itself as "v1.7" throughout its body text, references "v1.6.0" as its immediate predecessor branch point, and its own Phase 8 release steps reference a forward "1.8.0" branch that now collides with this document's own new v1.8.0 number — e.g. Phase 8's deliverable line still reads "main at v1.8.0; 1.8.0 branch open" after the mechanical title/companion-reference update below. That collision was left unresolved by the sweep, since untangling it requires deciding real content questions — e.g. whether this release still branches directly off v1.6.0, given the security work now occupies v1.7.0 in between, and what the correct next-branch number is — rather than a mechanical string replacement. Treat it as part of the reason for the rewrite above, not yet fixed.)*

*Companion to: `QPB_v1.8.0_Design.md`*
*Status: drafted 2026-05-03 alongside the v1.7 design. Implementation begins after v1.6.0 ships.*
*Depends on: v1.5.5, v1.5.6, v1.6.0 all shipped; defect catalog maintained as new defects accumulate; ≥10 calibration cycles' worth of cell.json data on disk.*

---

## Operating Principles

- **One AI session per implementation phase** (same model as v1.5.5 calibration cycles). State lives in the filesystem (`run_state.jsonl` + `PROGRESS.md`), not in any in-memory or external-process structure.
- **Validate the framework against QPB's own data before declaring it ready.** v1.7 doesn't ship until the SPC framework has been run against the existing 61-defect baseline AND ≥10 cells of calibration-cycle data, with operator-reviewed control-chart output.
- **Discipline on `SKILL.md`.** SPC is operator-facing analysis machinery; SKILL.md doesn't change. Orientation docs (`ai_context/STATISTICAL_CONTROL.md`, `ai_context/SDLC_CONTROL_PROTOCOL.md`) are new.
- **Each phase has a Council review.** Sub-agent fan-out per CALIBRATION_PROTOCOL.md Mode 1; three flat lenses (statistical correctness, schema/data fidelity, dashboard usability).
- **Backward compatibility on cell.json.** All schema additions are optional fields. Pre-v1.7 cell.json files remain readable.
- **Honest framing on small-sample limits.** Every chart in the dashboard surfaces sample size and confidence-interval width. No chart is shipped with a misleadingly tight control limit on under-sampled data.

---

## Phase 0 — v1.6.0 Stabilization Confirmation

Goal: confirm v1.6.0 is shipped, tagged, validated; the `1.7.0` branch is fresh from the v1.6.0 tag; `RELEASE_VERSION` bumped to `1.7.0-pre`. Confirm calibration-cycle data accumulation is sufficient to validate the framework.

Work items:
- v1.6.0 tag exists on origin.
- main fast-forwarded to v1.6.0.
- 1.7.0 branch created from v1.6.0 tag.
- `RELEASE_VERSION` bumped (only when tagging — kept at `1.6.0` during dev per the v1.5.5 convention).
- `metrics/regression_replay/` contains ≥ 10 cycle directories.
- `Quality Playbook/Reviews/QPB_Process_Defect_Baseline.md` is current as of v1.6 ship.
- Any v1.6 self-audit findings dispositioned.

Gate to Phase 1: all of the above confirmed; sufficient data for SPC framework validation.

---

## Phase 1 — Defect Catalog Schema + Migration

Goal: convert the prose-based defect catalog into structured machine-readable form so the SDLC dashboard reads canonical data rather than parsing markdown.

Work items:

- **Create `metrics/sdlc_defects/SCHEMA.md`** defining:
  - One JSON file per SDLC version (e.g., `phase-A.json`, `phase-B.json`, ..., `phase-D.json`).
  - Each file contains an array of defect records.
  - Required fields per record: `id` (e.g., `D-007`), `class` (e.g., `count-discipline`, `terminology-drift`, `verify-before-claim-violation`), `phase` (which SDLC phase introduced it), `date` (ISO 8601 date of introduction or detection), `severity` (low / medium / high), `recurrence_of_class` (string or null — if this defect is a recurrence of an older class, name the class).
  - Optional fields: `triggering_event` (commit SHA, conversation timestamp, etc.), `triggered_change_ids` (array of change IDs like `C-026`), `prose_summary` (the markdown narrative preserved from the source catalog).
  - Schema versioning: `_index` field at the top of each JSON file (matching v1.5.5 convention).

- **Create `bin/migrate_defect_baseline.py`** (one-time migration utility):
  - Parse `Quality Playbook/Reviews/QPB_Process_Defect_Baseline.md`.
  - Extract each defect record's fields from the markdown table + prose.
  - Group records by SDLC phase.
  - Write `metrics/sdlc_defects/phase-<X>.json` files.
  - Preserve the original markdown as `prose_summary` per record.
  - Validate: count of records in JSON output matches count in input markdown; all 38 process changes are referenced from at least one defect's `triggered_change_ids`.

- **Add unit tests** in `bin/tests/test_sdlc_defect_catalog.py`:
  - Migration round-trip preserves record count.
  - Schema-validator helper rejects malformed records.
  - The 61-defect baseline and 38 process changes correctly migrate.

- **Add `bin/sdlc_defect_lib.py`** with helpers for the dashboard: `read_defects(phase=None)`, `defect_class_distribution()`, `recurrence_rate(window_size)`, `defects_per_release()`, `change_event_timeline()`.

Deliverable: schema documented; migration utility produces canonical JSON; unit tests pass.

Council review (3 flat lenses):
- Schema fidelity: does the structured form preserve everything the prose form had?
- Migration correctness: does round-trip produce identical content?
- Schema versioning: is forward compatibility preserved if future defect records add new fields?

Gate to Phase 2: schema published; migration utility committed; unit tests pass; smoke test produces machine-readable defect data matching the prose baseline.

---

## Phase 2 — `bin/spc_lib.py` Core SPC Library

Goal: implement the core SPC chart types and run rules.

Work items:

- **Create `bin/spc_lib.py`** with:
  - **Chart types** (functions that take observations + config, return `ChartResult`):
    - `xbar_r_chart(subgroups, subgroup_size)` — X-bar/R for measurements with subgroups.
    - `p_chart(numerator, denominator, subgroup_sizes)` — proportion data.
    - `c_chart(counts, sample_sizes)` — counts of defects per unit.
    - `xmr_chart(observations)` — individuals + moving range, single-observation case.
  - **`ChartResult` dataclass** with fields: `chart_type`, `centerline`, `upper_control_limit`, `lower_control_limit`, `data_points`, `sample_size`, `confidence_interval_width`, `out_of_control_points` (indices), `pattern_signals` (list of run-rule violations).
  - **Run rules** (functions that take a `ChartResult`, return list of `RunRuleViolation`):
    - Western Electric rules 1-4 (single point beyond 3σ; 2/3 beyond 2σ; 4/5 beyond 1σ; 8 in a row on one side).
    - Nelson rules added selectively if false-signal rate is acceptable (defer to v1.7.x if so).
  - **Control-limit recomputation policy:** initial limits from first 10-15 observations; recomputed every N observations thereafter (configurable).
  - **Small-sample handling:** when sample size < 20, control limits are flagged as `provisional` in `ChartResult`; the dashboard renders them with a wide-CI band.

- **Add unit tests** in `bin/tests/test_spc_lib.py`:
  - Each chart type with synthetic in-control data → no run-rule violations.
  - Each chart type with synthetic out-of-control data (deliberate special cause) → expected violations detected.
  - Edge cases: zero observations, single observation, all-identical observations.
  - Sample-size flagging: < 20 observations correctly flagged as provisional.

- **Add `bin/tests/test_spc_lib_against_qpb_data.py`** as an integration test:
  - Reads `metrics/regression_replay/*/cell.json` files.
  - Computes X/MR chart on the recall-delta sequence.
  - Asserts the chart's centerline and limits are computed without error.
  - Doesn't assert specific values — those depend on accumulated data — just that the framework runs end-to-end on real data.

Deliverable: `bin/spc_lib.py` published; unit tests pass; integration test confirms the framework operates on real cell.json data.

Council review (3 flat lenses):
- Statistical correctness: are the control-limit formulas correct? Are the run rules implemented per the canonical definitions (Western Electric Handbook, Montgomery, etc.)?
- API design: is the `ChartResult` dataclass the right shape for downstream dashboards?
- Edge-case coverage: are zero-observation, single-observation, and all-identical-observation cases handled gracefully?

Gate to Phase 3: SPC core library committed; unit + integration tests pass; Council ship verdict.

---

## Phase 3 — Multi-Cell Calibration Cycle Support

Goal: extend the calibration orchestrator and cell.json schema to support factorial and Latin-square experimental designs.

Work items:

- **Extend `metrics/regression_replay/SCHEMA.md`** with the additive fields from the v1.7 Design ("Multi-cell calibration cycles" section):
  - `cycle_design`: enum.
  - `factor_levels`: array.
  - `factor_values`: object.
  - `design_run_index`: integer.
  - All fields are optional; pre-v1.7 cell.json files remain valid.

- **Create `bin/multi_cell_doe.py`** with:
  - `factorial_design(factors, levels, fractional=False)` — generates the design matrix for a factorial experiment.
  - `latin_square(factors, treatments)` — generates a Latin square design.
  - `augment_design(existing_cells, new_factor_values)` — produces follow-up cells when the initial design surfaces an interaction.
  - `validate_design(cells)` — checks that the cells in a directory match the declared `cycle_design`. Catches missing cells, off-design cells, etc.

- **Update `agents/calibration_orchestrator.md`** to handle `cycle_design` variants:
  - Step 2 (pre-lever runs) becomes Step 2 (run all cells in the design matrix in `design_run_index` order).
  - Step 4 (post-lever runs) merges with Step 2 since multi-cell designs don't have a strict pre/post split — the design matrix encodes the structure.
  - Step 5 (delta computation) becomes "compute main effects + interactions" using DoE analysis.

- **Add unit tests** in `bin/tests/test_multi_cell_doe.py`:
  - Full factorial 2² produces 4 cells with correct factor combinations.
  - Fractional factorial 2^(5-2) produces 8 cells with correct aliasing.
  - Latin square 4×4 produces 16 cells with the expected balance.
  - `validate_design` catches missing cells.

- **Add integration test:** dry-run a factorial cycle (no actual playbook subprocess) to confirm the orchestrator template handles the multi-cell flow correctly.

Deliverable: schema extended (backward-compatible); DoE library + tests; orchestrator template updated.

Council review:
- Are the experimental designs implemented correctly per DoE methodology (Montgomery, *Design and Analysis of Experiments*)?
- Does the orchestrator template correctly handle the multi-cell flow without losing v1.5.5's resume semantics?
- Is backward compatibility actually preserved? Can a pre-v1.7 cell.json round-trip through `validate_design` without errors?

Gate to Phase 4: multi-cell cycle support committed; tests pass; Council ship.

---

## Phase 4 — Cross-Version Trend Tracking Pipeline

Goal: produce per-benchmark recall trajectories across QPB releases, plus per-defect-class trajectories.

Work items:

- **Create `bin/cross_version_trends.py`**:
  - Inputs: `repos/archive/<benchmark>/quality/previous_runs/<version>/quality/BUGS.md` for every benchmark × every version, plus current cycle outputs.
  - Outputs: `metrics/cross_version_trends/<benchmark>.json` with per-benchmark recall trajectory, per-defect-class trajectory, version metadata (date, QPB version), and per-version replicate counts where available.
  - Uses `bin/spc_lib.xmr_chart()` to compute control limits on the recall trajectory.

- **Extend `bin/visualize_calibration.py`** with two new chart types:
  - `cross_version_recall_trajectory(benchmarks)` — multi-line plot, X = QPB version chronological, Y = recall, one line per benchmark, control limits as bands.
  - `cross_version_defect_class_trajectory(benchmark, classes)` — heatmap or stacked-area chart showing defect-class counts over versions.

- **Add unit tests** in `bin/tests/test_cross_version_trends.py`:
  - Reads a synthetic three-version archive and produces correct trajectory data.
  - Handles missing versions gracefully (gaps in the chronological sequence).
  - Replicate-aware: when a version has multiple BUGS.md (replicate runs), uses the mean and computes within-version variance.

- **Run against real data**: validate the pipeline produces the multi-benchmark trend chart for chi-1.3.45/chi-1.5.1/virtio-1.5.1/express-1.3.50 across the v1.3.x → v1.5.x QPB release series.

Deliverable: pipeline runs end-to-end; charts render against real archive data.

Council review:
- Trajectory correctness: does the recall computation match prior cell.json values?
- Chart design: do the trajectories communicate the trend clearly without misleading the operator about confidence?
- Missing-data handling: does the pipeline handle the gaps in the historical archive gracefully?

Gate to Phase 5: pipeline committed; charts validated against real data; Council ship.

---

## Phase 5 — SDLC Defect-Rate Dashboard

Goal: render the structured defect catalog as actionable charts.

Work items:

- **Create `bin/sdlc_defect_dashboard.py`**:
  - Reads `metrics/sdlc_defects/*.json` via `bin/sdlc_defect_lib.py`.
  - Computes: defects-per-release rate (c-chart), defect-class proportions (p-chart per class), recurrence rate (p-chart over sliding window), days-between-defects (X/MR), process-change-to-defect ratio (X/MR).
  - Renders charts via `bin/visualize_calibration.py` extensions.
  - Produces a single multi-chart dashboard PNG plus a per-chart JSON summary.
  - Annotates process-change events as vertical lines on each chart.

- **Add unit tests** in `bin/tests/test_sdlc_defect_dashboard.py`:
  - Dashboard renders against the migrated 61-defect catalog without errors.
  - Recurrence-rate chart correctly identifies Phase D's elevated rate.
  - Process-change events appear at correct X-axis positions.

- **Validate against the cataloged data**: the dashboard's output should match the manual analysis in `Quality Playbook/Reviews/QPB_Process_Defect_Baseline.md` (defect-class distribution, defect-to-change ratios stable around 1.3-1.8, Phase D 55% recurrence rate). If the dashboard's numbers don't match the prose, one of them is wrong.

Deliverable: dashboard runs; output validated against manual analysis.

Council review:
- Chart appropriateness: is each metric using the right chart type per the v1.7 design?
- Honest framing: does the dashboard correctly surface sample-size caveats and confidence-interval widths?
- Operator usability: is the dashboard actionable, or is it pretty but not useful?

Gate to Phase 6: dashboard committed; output validated; Council ship.

---

## Phase 6 — Orientation Docs + Operator Protocols

Goal: make SPC operator-usable. Two new orientation docs.

Work items:

- **Create `ai_context/STATISTICAL_CONTROL.md`**:
  - What SPC is, in plain SE/QE terms (no jargon).
  - Which chart types QPB uses for which metrics.
  - How to read a control chart (centerline, limits, run-rule violations).
  - When to investigate a special-cause signal vs. accept it as known.
  - The honest caveats: small-sample limits, structural-break handling, what SPC can and can't tell you.
  - Pointer to `bin/spc_lib.py` and `bin/sdlc_defect_dashboard.py` for the implementation.

- **Create `ai_context/SDLC_CONTROL_PROTOCOL.md`**:
  - Procedure for adding a new defect to `metrics/sdlc_defects/<phase>.json`.
  - Classification rules (what counts as `count-discipline` vs. `terminology-drift` vs. new class).
  - Recurrence detection: how to determine `recurrence_of_class` correctly.
  - Process-change protocol: when a special-cause signal merits a process change, how to draft it, where it lands in the catalog.
  - Cross-reference to the existing `ai_context/CALIBRATION_PROTOCOL.md` (improvement-loop side) and `ai_context/DEVELOPMENT_PROCESS.md` (general SDLC rules).

- **Update `ai_context/IMPROVEMENT_LOOP.md`** with the v1.7 SPC additions:
  - Replace "moving toward statistical control" with "under statistical control via the v1.7 framework."
  - Add a "How to read the control charts" section pointing to `STATISTICAL_CONTROL.md`.

Deliverable: orientation docs published; cross-references consistent.

Council review:
- Plain-language test: can a non-expert operator read these docs and understand the system?
- Cross-reference consistency: do the new docs and the existing `CALIBRATION_PROTOCOL.md` / `DEVELOPMENT_PROCESS.md` agree?
- Completeness: are there steps an operator would need but can't find?

Gate to Phase 7: orientation docs committed; Council ship.

---

## Phase 7 — Validation Against QPB's Own Data

Goal: prove the framework works by running it against QPB's existing data and validating the output.

Work items:

1. **Improvement-loop validation:** run `bin/spc_lib.xmr_chart()` against all `metrics/regression_replay/*/cell.json` files (≥ 10 cells expected by v1.7). Confirm the chart renders, control limits compute, run rules fire correctly on any out-of-control points. If a special-cause signal fires, run the investigation note workflow and add the disposition to the calibration log.

2. **SDLC validation:** run the dashboard against the migrated 61-defect catalog. Confirm:
   - Phase D's 55% recurrence rate appears as a special-cause signal on the recurrence-rate chart.
   - Defect-class distribution matches the prose analysis.
   - Defect-to-change ratio (1.3-1.8) appears stable across Phases B and C, then breaks during Phase D.

3. **Multi-cell cycle validation:** run a 2×2 factorial cycle on Pattern 7 budget-cap × Pattern 7 ordering. Use `bin/multi_cell_doe.py` to generate the design, run the orchestrator, analyze with `bin/spc_lib.py`. The output should attribute variance to budget cap, ordering, and their interaction.

4. **Cross-version validation:** run `bin/cross_version_trends.py` against the historical archive. Confirm the chi-1.3.45 / chi-1.5.1 / virtio-1.5.1 / express-1.3.50 trajectories render correctly with v1.5.4's Pattern 7 inflection point identifiable.

5. **Operator readability check:** Andrew (or an AI proxy) reads `STATISTICAL_CONTROL.md` and the dashboard output cold. Can the framework be understood without context from the design doc?

If any of these fail, fix or revise before tagging.

Deliverable: validation report at `Quality Playbook/Reviews/QPB_v1.7.0_Validation_Report.md` documenting all four validations + the operator readability check.

Council review (final pre-tag):
- Are the validation results honest? Any cherry-picking of charts that look good while suppressing ones that don't?
- Did any validation surface a framework defect not yet addressed?
- Is the framework ready for adopters to use in v1.8+?

Gate to Phase 8: validation report committed; framework demonstrably works; Council ship.

---

## Phase 8 — Mechanical Release

Goal: ship v1.7.0.

Work items:
- Bump `RELEASE_VERSION` in `bin/benchmark_lib.py` from `1.6.0` to `1.7.0`.
- Bump SKILL.md frontmatter, banner, JSON examples, generated-by templates (same pattern as v1.5.5 / v1.5.4 release prep).
- Bump README version stamp.
- Add "What's new in v1.7" section to README covering: SPC machinery for both improvement loop and SDLC, multi-cell calibration cycles, cross-version trend tracking, defect-catalog migration to structured form, two new orientation docs.
- Update Roadmap section in README: move v1.7 from "future" to "shipped"; expand v1.8 description if v1.8 design has progressed in parallel.
- Run final test suite — must pass.
- Commit, tag `v1.7.0`, push branch, push tag.
- Fast-forward main, push main.
- Create `1.8.0` branch, push.
- Verify origin via `git ls-remote`.

Deliverable: v1.7.0 tagged on origin; main at v1.7.0; 1.8.0 branch open.

Gate to v1.8.0: all of the above verified.

---

## Risks and Mitigations

- **Insufficient data for SPC validation.** If by v1.7 implementation start there aren't enough cells, the framework can be implemented but not validated. Mitigation: explicitly schedule additional calibration cycles between v1.6 and v1.7 to accumulate data. If still insufficient, ship v1.7 framework with a "validation deferred" note and revisit in v1.7.x.

- **Run rules produce too many false-positive signals.** If Western Electric rules fire constantly on QPB data, operators will start ignoring them. Mitigation: ship with a permissive default (rules 1 and 2 only); operator can enable rules 3 and 4 selectively.

- **Defect catalog migration loses information.** Prose narrative includes context that's hard to capture in structured fields. Mitigation: preserve all narrative as `prose_summary`; treat the JSON as a queryable index over the prose, not a replacement for it.

- **Multi-cell DoE adds operator complexity.** Factorial designs are unfamiliar to operators not trained in DoE. Mitigation: orientation doc includes a one-page "common designs and when to use them" section. Single-lever cycles remain the default.

- **Cross-version trends are confounded by changes in the playbook itself.** When v1.5.4 changed the role-map architecture, the comparison to v1.5.3 isn't apples-to-apples. Mitigation: schema's `structural_break` flag; charts visually indicate breaks; operator interpretation is required.

---

## Out-of-band carry-forward to v1.8

Anything that surfaces during v1.7 development pointing toward v1.8 (multi-operator workflow) goes into `docs/design/QPB_v1.8.0_Design.md`'s carry-forward section. Don't expand v1.7's scope to absorb v1.8 ideas.
