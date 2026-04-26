# Quality Playbook v1.6.0 — Implementation Plan

*Companion to: `QPB_v1.6.0_Design.md`*
*Status: drafted 2026-04-26; awaiting v1.5.4 ship before implementation begins.*
*Depends on: v1.5.4 complete (regression replay machinery + calibration log operational); v1.5.0–v1.5.3 stable; benchmark replicate harness operational with at least one (release × benchmark) cell at N≥5*

---

## Operating Principles

- v1.6.0 is **one lever pull, no more**. The release contains exactly one focused change to one of Levers 1-5's home files. Multi-lever bundles defeat the recall-delta attribution; if a calibration cycle motivates more than one lever change, ship them as separate v1.6.x releases.
- The deliverable is the workflow, not the change. v1.6.0's value is in establishing how v1.6.x releases work — what artifacts each release ships, what review gates apply, what the calibration log entry looks like. The specific lever pull is the demonstration vehicle.
- The release is governed by the v1.5.4 apparatus. `bin/regression_replay.py` produces the cell.json files that justify the release; they're committed alongside the lever change. The release won't pass review without them.
- Cross-benchmark regression check is mandatory. Every v1.6.x release must show that the lever pull didn't harm recall on benchmarks it wasn't targeting (within the noise floor σ).

---

## Phase 0 — v1.5.4 Stabilization Confirmation

Goal: confirm v1.5.4 is shipped and the apparatus is operational.

Work items:
- v1.5.4 tag exists on origin
- `bin/regression_replay.py` runs end-to-end on a fresh smoke cell (verify with a non-calibration-log cell to confirm reproducibility)
- `Lever_Calibration_Log.md` has 3+ documented cycles (success criterion 3 from v1.5.4 design)
- `metrics/regression_replay/SCHEMA.md` is committed and stable
- The benchmark replicate harness has a (release × benchmark) cell at N≥5; σ data is recorded and consumable as `noise_floor_source` input

Gate to Phase 1: all of the above; no pending v1.5.4 bugs without dispositions; 1.6.0 branch is fresh from main with v1.5.4 tag as base.

---

## Phase 1 — Select the Lever Pull

Goal: pick which calibration-cycle observation gets promoted from "documented cycle" to "shipped release."

Work items:
- Read v1.5.4's `Lever_Calibration_Log.md` end-to-end
- Identify the cycle whose lever-pull diagnosis is (a) most clearly evidenced — large recall delta, far outside noise floor; (b) most cleanly attributable — single lever, no cross-lever interaction; (c) most generalizable — the lever change improves not just the targeted bug but the class of bugs the cycle exposed
- Document the selection rationale in a new file at `Quality Playbook/Reviews/QPB_v1.6.0_Selection_Rationale.md`. This file lives in the workspace alongside other planning artifacts; it records why this cycle was promoted vs. others
- Confirm the selected cycle's lever change is small enough to ship as a focused commit (typically 5-50 lines of prompt-side change in a `references/*.md` file)

Deliverable: selection rationale documented; the calibration-cycle entry in `Lever_Calibration_Log.md` is annotated with "promoted to v1.6.0."

Gate to Phase 2: selection survives Council pre-review (a quick "is this the right cycle to promote?" check); no objections to the rationale.

---

## Phase 2 — Pull the Lever

Goal: apply the lever change as a focused commit on the 1.6.0 branch.

Work items:
- Edit the lever's home file (e.g., `references/exploration_patterns.md` for a Lever 1 change). Keep the diff focused; this is not the time to clean up unrelated content.
- The commit message includes:
  - Reference to the calibration cycle that motivated the change (cite the Lever_Calibration_Log.md entry by section heading)
  - Reference to the cell.json files that captured the before/after recall measurement
  - One-line summary of what the lever does and why this change is expected to improve recall
- Run the existing test suite and benchmark gate to confirm no accidental regressions in the playbook's own machinery (the lever change is prompt-side, but verify the code path is unchanged)

Deliverable: one commit on the 1.6.0 branch with the lever change.

Gate to Phase 3: commit lands; existing tests pass; the diff is reviewable as a self-contained change.

---

## Phase 3 — Validate via Regression Replay

Goal: re-run the v1.5.4 apparatus to confirm the lever change actually improves recall on the targeted cell.

Work items:
- Run `bin/regression_replay.py` against the calibration cycle's cell with the lever change in place
- Confirm the cell.json reports recall improvement vs. the v1.5.4 baseline (the same cell.json that documented the original cycle in v1.5.4's calibration log)
- Run the cross-benchmark regression check: chi-1.5.1, virtio-1.5.1, express-1.5.1 with the lever change. Confirm no regression beyond σ.
- Save the new cell.json files under `metrics/regression_replay/<v1.6.0-timestamp>/` and reference them from the calibration log entry

Deliverable: cell.json files documenting the v1.6.0 lever pull's measurement; updated `Lever_Calibration_Log.md` entry with v1.6.0 release-shipment annotation.

Gate to Phase 4: recall improvement on the targeted cell is real (>2σ above noise floor); cross-benchmark regression check passes; cell.json files validate against SCHEMA.md.

---

## Phase 4 — Document the Release Template

Goal: document the v1.6.x release template so v1.6.1+ have a structural reference.

Work items:
- Create `docs/design/QPB_v1.6.x_Release_Template.md` documenting:
  - Required artifacts: lever-change diff, cell.json files (before and after), calibration-log entry annotation, cross-benchmark regression-check output
  - Required Council review scope: lever home file, calibration log update, cell.json files (the apparatus output is reviewed for "did this lever pull do what was claimed")
  - Required quality_gate behavior: any new check needed to enforce template? Or Council-convention enforcement only?
  - Cadence expectations: 2-4 v1.6.x releases per month is the initial expectation; cadence governed by calibration cycle rate, not by calendar
- Reference this template from `IMPROVEMENT_LOOP.md` (PDCA section) so adopters can navigate to it

Deliverable: release template document committed; IMPROVEMENT_LOOP.md cross-references it.

Gate to Phase 5: template is internally consistent; Council reviews it as a standalone doc; no broken cross-references.

---

## Phase 5 — IMPROVEMENT_LOOP.md Status Update

Goal: update IMPROVEMENT_LOOP.md to reflect that the methodology is now operational.

Work items:
- Mark Stage C ("Continuous lever-pull improvement") as operational in the Measurement and statistical control section
- Update the methodology framing: replace "the loop becomes operational at v1.6.0" with "the loop is operational as of v1.6.0"
- Reference the v1.6.x release template
- Reference the Lever_Calibration_Log.md as the source of truth for active calibration cycles
- Run the Toolkit Test Protocol against the updated doc

Deliverable: IMPROVEMENT_LOOP.md updated, TTP-reviewed, committed.

Gate to Phase 6: TTP returns Pass or Pass-With-Caveats; the doc accurately describes the post-v1.6.0 state.

---

## Phase 6 — Release

Goal: tag and release v1.6.0.

Work items:
- Update `bin/benchmark_lib.py::RELEASE_VERSION` to `"1.6.0"`
- Update SKILL.md `version:` stamps to `1.6.0`
- Update README with v1.6.0 changelog entry that frames v1.6.0 as the transition to iterative improvement
- Run a final Council review on the full v1.6.0 surface: lever change + cell.json + calibration log entry + release template + IMPROVEMENT_LOOP.md update
- Tag v1.6.0 on the 1.6.0 branch; push tag to origin; verify with `git ls-remote origin v1.6.0`
- Update workspace CLAUDE.md to index the v1.6.x release template if helpful

Deliverable: v1.6.0 tagged, pushed, README updated, version stamps refreshed, Council review concluded.

Gate to release: tag confirmed on origin via `git ls-remote`; Council review verdict is Ship; no pending blocking findings.

---

## Council Review Scope

v1.6.0 has heightened review scrutiny because it's setting the template for all v1.6.x releases.

- **Round 1 (after Phase 2):** Review the lever change in isolation. Specifically: is this a focused, single-lever change? Does the diagnostic reasoning in the calibration log actually support this lever as the right diagnosis? Are there alternative levers that might be a better fit?
- **Round 2 (after Phase 3):** Review the regression-replay measurement. Specifically: is the recall improvement >2σ above noise floor? Is the cross-benchmark regression check methodologically sound? Are the cell.json files complete and matching SCHEMA.md?
- **Round 3 (after Phase 5):** Review the release template + IMPROVEMENT_LOOP.md update via TTP for the doc, Council for any code/template content. Specifically: is the template complete enough that v1.6.1 can follow it without further design work? Does the IMPROVEMENT_LOOP.md update accurately describe the new operational state?
- **Round 4 (final, before release):** Whole-release Council review. Verify no scope creep; verify no other lever was changed; verify the release artifacts are coherent.

---

## Out of Scope (Defer)

- Automating any part of the iterative-improvement workflow. Manual trigger from Andrew per cycle is the v1.6.0 model. Automation comes much later (or never, if the diagnostic reasoning step doesn't automate cleanly).
- Multi-lever releases. v1.6.0 is one lever pull; multi-lever bundles are a v1.7+ idea.
- New benchmark targets, new lever inventory items, control charts, cross-model replay. All deferred.
- Documenting v1.6.x release cadence as a hard requirement. The cadence emerges from calibration cycle rate; v1.6.0 establishes the baseline, future releases establish the trend.

---

## Risks and Mitigations

- **Risk: v1.6.0's lever pull turns out to be the wrong diagnosis once it ships.** Mitigation: any v1.6.x release that's revealed to be a misdiagnosis ships a corrective patch (v1.6.0.1) and the calibration log records the diagnostic correction. The methodology accommodates dead ends.
- **Risk: cross-benchmark regression check is too lax and ships a release that harms one benchmark by ~σ.** Mitigation: the regression-check threshold is 2σ for v1.6.0; if practice reveals 2σ is too lax, tighten to 1σ in v1.6.x.
- **Risk: the release template formalized in v1.6.0 turns out to be too rigid for some calibration cycles.** Mitigation: the template is documented as v1.0; updates go to v1.6.1+ as discovered. It's a living document.
- **Risk: the cadence expectation (2-4 v1.6.x per month) is wrong.** Mitigation: the expectation is a baseline, not a commitment. Slower or faster is fine if motivated by actual calibration work.
- **Risk: lever pulls converge to diminishing returns faster than expected, and v1.6.x quickly runs out of obvious cycles.** Mitigation: this is a feature, not a bug. Convergence is the point. When new calibration cycles stop revealing pullable levers, that's evidence the improvement loop has done its job for the current methodology generation.
