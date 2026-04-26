# Quality Playbook v1.6.0 — Design Document

*Status: design captured 2026-04-26; implementation begins after v1.5.4 ships.*
*Authored: April 2026*
*Owner: Andrew Stellman*
*Depends on: `QPB_v1.5.4_Design.md` (regression replay machinery and calibration log shipping in v1.5.4); v1.5.0/v1.5.1/v1.5.2/v1.5.3 complete*

> **Where v1.6.0 sits in the arc.** v1.6.0 is the **transition release** — the moment QPB stops being a feature-development project and starts being an iterative-improvement project. With v1.5.4's regression-replay machinery operational, every change from v1.6.0 forward is a lever-pull motivated by missed-bug observation, with a documented recall delta and a cross-benchmark regression check. The methodology described prospectively in `IMPROVEMENT_LOOP.md` becomes the actual workflow at v1.6.0.

---

## Motivation

### Feature-complete on the v1.5.x infrastructure

By the end of v1.5.4, QPB has accumulated everything it needs to do continuous quality improvement under the SEI / Humphrey lineage:

- **Quality control infrastructure** (v1.5.0–v1.5.3): the divergence model, tier system, citation schema, Phase 5 writeup hardening, bug-family amplification, finalizer robustness, INDEX verdict mapping, the project-type classifier, the four-pass skill-derivation pipeline, the skill-divergence taxonomy. QPB can audit code projects, AI-skill projects, and hybrid projects with operational rigor.
- **Quality improvement infrastructure** (v1.5.4): `bin/regression_replay.py`, the `metrics/regression_replay/` schema, the calibration log, the cross-benchmark regression check, the noise-floor handling. QPB can measure whether a proposed change actually improves recall, against a documented baseline, with cross-benchmark side-effect detection.
- **Measurement substrate** (the benchmark replicate harness in `repos/replicate/`): accumulating within-version σ data so that future "is this metric in statistical control?" questions have an empirical floor to test against.

There's no QC capability left to add for the foreseeable future. There's no QI apparatus left to build. v1.6.0's job is to start *using* what was built.

### What "iterative improvement" actually looks like

The pattern at v1.6.0+:

1. **An observation triggers a release candidate.** Most often: a regression-replay run identifies a class of bugs current QPB misses. Sometimes: a Council review of a benchmark output flags a quality issue. Sometimes: an adopter reports a category of bug QPB systematically misses on their codebase. Each observation is a candidate for a release.
2. **A lever is hypothesized.** Read `IMPROVEMENT_LOOP.md` Levers 1-5; identify which one, when pulled, would be expected to address the observation. The diagnostic reasoning is documented.
3. **The lever is pulled.** Edit the lever's home file (e.g., `references/exploration_patterns.md` for Lever 1) with a focused change.
4. **The release is checked.** Run regression replay on the original observation's cell; record the recall delta. Run cross-benchmark regression check on the other pinned benchmarks; confirm no regression beyond the documented noise floor.
5. **The release is acted on.** If the delta is positive and no regression elsewhere, ship as a v1.6.x point release. If the lever was the wrong diagnosis, document the dead end in the calibration log and try a different lever.

That's PDCA. It's the second half of QPB applying QE to itself, made operational.

### The release cadence shifts

v1.5.x releases were chunked feature work — months between releases, each shipping a coherent package of new capability. v1.6.x releases are smaller and more frequent. Each one closes one calibration cycle, lands one lever pull, ships one quantitative recall improvement (or honestly documents a failed lever-pull attempt). The release cadence is governed by the rate at which the calibration log accumulates entries, which is governed by how fast Andrew can do the diagnostic work and how fast the regression-replay machinery completes runs.

A reasonable expectation: 2-4 v1.6.x point releases per month once the workflow is established, slowing as the improvement loop converges (when most levers are well-tuned and new lever-pull opportunities are rare, releases become sparser by design).

### Honest framing: this may take a long time to converge

The improvement loop is genuinely open-ended. Each release pulls one lever; there are five levers; there might be more lever-pull opportunities than fit in any reasonable release schedule. There also might be diminishing returns — early lever pulls capture the most-obvious calibration deltas, later pulls deliver smaller and noisier improvements until the lever-pull recall delta drops below σ and the apparatus can no longer distinguish "real improvement" from "lucky single run."

That convergence point — when lever-pull deltas drop below the noise floor — is when QPB approaches "in statistical control" territory under SEI / Humphrey definitions. It's the multi-year horizon. v1.6.0 starts the journey; v1.7+ probably reaches it (or honestly falsifies the expectation that LLM-driven processes can reach it under our current measurement substrate).

---

## Design

### What v1.6.0 delivers

v1.6.0 is the **first iterative-improvement release** — meaning the release itself contains exactly ONE lever pull, motivated by ONE missed-bug observation, validated by the v1.5.4 apparatus. The deliverable is structurally small (a single lever change) but methodologically significant (it's the first release shipped under the new workflow).

The specific lever pull for v1.6.0 is to be determined during v1.5.4's calibration cycles. v1.5.4 ships with 3-5 cycles documented; one of those cycles' lever pulls is the natural candidate for the v1.6.0 release. Most likely: the chi-1.3.45 → 1.3.46 collapse cycle's diagnosis (probably a Lever 1 — exploration breadth — adjustment), packaged as a permanent skill change rather than a calibration-log curiosity.

### What v1.6.0 doesn't deliver

- No new features. No new schema fields. No new lever-inventory items. No new benchmark targets. The point of v1.6.0 is to demonstrate the workflow, not to add capability.
- No automated continuous-improvement scheduler. v1.6.0+ releases are still manually initiated by Andrew with each calibration observation. Automating "monitor benchmarks, propose lever pulls, run replay" is a v1.7+ idea (and probably a bad idea — the diagnostic reasoning step is hard to automate without losing the methodology's discipline).
- No control charts. Those need ~20-30 stable observations per process and v1.6.0 has at most a handful. Control charts come later.

### What v1.6.0 establishes

- **The release template for v1.6.x onward.** Each release ships with a calibration-log entry referencing the cell.json that motivated it, a focused lever-pull diff, a benchmark-confirmation run showing recall improvement, and a cross-benchmark regression check showing no harm elsewhere. v1.6.0's release artifacts are the prototype for this template.
- **The IMPROVEMENT_LOOP.md status update.** "Stage C: Continuous lever-pull improvement" gets marked operational. The methodology doc transitions from prospective ("once v1.5.4 lands, the loop becomes operational") to descriptive ("the loop is operational, see calibration log").
- **The cadence baseline.** v1.6.0 establishes a cadence reference: how long does it take from "calibration cycle observation" to "tagged release"? That number anchors expectations for v1.6.x.

---

## Success Criteria

v1.6.0 is successful if:

1. **One lever pull is shipped via the v1.5.4 workflow.** The release contains exactly one focused lever change in one of Levers 1-5's home files. The change has a documented diagnostic reasoning (which calibration cycle motivated it, which lever was hypothesized, why), a regression-replay measurement showing recall improved on the cycle's cell, and a cross-benchmark regression check showing no harm to chi-1.5.1, virtio-1.5.1, express-1.5.1.

2. **The calibration log gains a v1.6.0 release-shipment entry.** The entry references the calibration cycle it derived from, names the lever pulled, documents before/after recall, and links to the cell.json files generated by the v1.5.4 apparatus.

3. **`IMPROVEMENT_LOOP.md` is updated** to mark Stage C operational and note v1.6.0 as the first release shipped under the iterative-improvement workflow.

4. **The release template is documented** at `docs/design/QPB_v1.6.x_Release_Template.md` (or equivalent) so that v1.6.1+ have a structural reference. The template specifies: required calibration-cycle reference, required cell.json links, required cross-benchmark regression check, required diagnostic reasoning, required Council review scope (lever home file plus calibration log).

5. **No regression on code-project benchmarks beyond the documented noise floor.** chi-1.5.1, virtio-1.5.1, express-1.5.1 yields are within ±σ of the v1.5.4 baseline (where σ comes from the replicate harness data).

6. **No regression on QPB self-audit.** The v1.5.3 skill-as-code work continues to produce ≥80 REQ self-audit. v1.6.0's lever pull might tighten the skill prompts but shouldn't reduce coverage.

---

## Provenance

### v1.6.0 is the SEI level-4 transition

The CMMI level 4 ("quantitatively managed") definition: process performance is quantitatively understood, statistical and other quantitative techniques are used to control the process, special causes of variation are identified and addressed. v1.6.0 begins the move toward that state. Each release pulls a lever based on quantitative evidence; cross-benchmark regression checks identify special causes; the calibration log accumulates the historical record.

The CMMI level 5 ("optimizing") definition extends level 4 with continuous improvement. v1.6.0 is on the trajectory to level 5; whether the methodology actually reaches it (and whether the LLM substrate cooperates with statistical-control assumptions) is the open empirical question that the v1.6.x release stream answers over time.

### The framing comes from prior conversation

v1.6.0 was scoped during the 2026-04-26 conversation that recovered from the v1.5.3 IMPROVEMENT_LOOP.md misfire. Key decisions captured during that conversation:

- v1.5.x is feature work. v1.5.3 is the skill-as-code feature. v1.5.4 is the QI machinery. After v1.5.4, QPB is feature-complete.
- v1.6.0 is the transition release. From v1.6.0 onward, every release is a lever pull motivated by missed-bug observation.
- The methodology is in the Shewhart / Deming / Humphrey / SEI lineage, with the honest caveat that LLM-driven processes are a novel substrate for SPC.
- v1.5.5 (originally planned as a naive-review-phase feature) is NOT happening as a feature release. If naive-review framing has methodological value, it's a candidate v1.6.x lever-pull experiment (use replay to measure whether adding a naive phase improves recall against the calibration set), not a separate feature release.

The conversation log is preserved in the AI Chat History export.

### What v1.6.0 inherits from v1.5.4

The full apparatus: `bin/regression_replay.py`, `metrics/regression_replay/SCHEMA.md`, `Lever_Calibration_Log.md`. v1.6.0 doesn't modify these — it uses them. The inherited apparatus is what makes v1.6.0 possible; v1.6.0 wouldn't be coherent as a release before v1.5.4.

---

## Out of Scope for v1.6.0

- Multi-lever releases. v1.6.0 is exactly one lever pull; multi-lever releases are explicitly avoided to keep the recall-delta attribution clean. Multi-lever bundles can come later (v1.7+) once the methodology has demonstrated it can attribute changes to specific levers.
- New levers. The v1.5.x lever inventory (Levers 1-5) is the working set. New levers get added in v1.6.x+ releases when calibration cycles reveal a missed-bug class that doesn't fit any existing lever — but adding a new lever is its own release, distinct from a release that pulls an existing one.
- Naive-review phase. Originally planned as v1.5.5; deferred. May come back as a v1.6.x lever-pull experiment if calibration motivates it.
- Categorization tier policy. Originally listed as Lever 6 in earlier IMPROVEMENT_LOOP.md drafts; that listing was withdrawn because it's feature work for a not-yet-built capability. If categorization becomes valuable, it's a feature release in the v1.7+ track, not a v1.6.x lever pull.
- Control charts / formal SPC limits. Need ~20-30 stable observations per process. v1.6.0 has at most a handful.
- Cross-model replay infrastructure. Originally a v1.5.4 stretch goal; remains deferred.

---

## Dependencies

- v1.5.3 ships first (skill-as-code).
- v1.5.4 ships second (regression-replay machinery + calibration log).
- The benchmark replicate harness has accumulated enough variance data to provide a noise floor for v1.6.0's regression-check threshold. Threshold: at least one (release × benchmark) cell at N≥5.
- The v1.5.4 calibration log has at least one cycle with a clean lever-pull recommendation that can be promoted to a permanent skill change in v1.6.0.

---

## Open Questions

These don't block v1.6.0 design but need answers during implementation:

1. **What's the threshold for σ-aware "no regression"?** The cross-benchmark regression check needs to declare a benchmark "regressed" or "stable" — at what σ-multiple does a measured drop become a regression? Lean: 2σ (consistent with the v1.5.4 design's "real regression" threshold).

2. **What if the calibration cycle identified the wrong lever?** If v1.6.0 ships a lever pull and a v1.6.1 calibration cycle reveals it actually made things worse on a different benchmark class, what's the remediation path? Lean: revert via v1.6.0.1 patch, document in calibration log as a corrected diagnosis.

3. **How is the release template enforced?** v1.6.0 establishes the template; v1.6.1+ should follow it. Is the enforcement by Council convention, by quality_gate.py check, by tooling? Lean: Council convention initially; consider gate enforcement once the template is stable.

4. **When does the v1.6.x stream end and v1.7 start?** Open. Two natural triggers: (a) the lever-pull recall deltas drop below σ (improvement loop has converged within current methodology); (b) a calibration cycle motivates a structural change too large to be one lever pull (e.g., a new gate check, a new phase). Either triggers a v1.7 feature release.
