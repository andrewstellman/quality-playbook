# Quality Playbook — Improvement Loop

> This document describes **how the Quality Playbook is improved over time** — the methodology QPB uses to find and fix process defects in itself, in the same way `SKILL.md` describes how QPB finds defects in code under review. It is meta. Release-specific scope and work items live in `docs/design/QPB_v<X.Y.Z>_Design.md` and `docs/design/QPB_v<X.Y.Z>_Implementation_Plan.md`, not here.

## QPB applies quality engineering to itself

The Quality Playbook is, at its core, a traditional quality engineering process operationalized as instructions an AI agent can follow. The bones of `SKILL.md` — multi-phase structured review, traceability matrices, evidentiary tier systems, gating criteria, multi-reviewer Council inspection — are 50-year-old practice from Fagan inspections, IEEE-829 verification standards, stage-gate review, and structured peer review. Applying that body of practice to LLM code review produces measurably better defect detection than unstructured prompting because the methodology was always doing the lifting; the LLM is a different substrate for executing it.

Traditional quality engineering has two halves. **Quality control** is finding defects in artifacts (the SKILL.md half — find bugs in the code under review). **Quality improvement** is the second half — measuring the *process* that produces defects and improving it over time. This document operationalizes the second half: QPB applying quality engineering to itself, with QPB itself as the artifact whose defects (missed-bug classes, recall regressions, lever-pull failures) are being measured and reduced.

The methodology is in the Walter Shewhart / W. Edwards Deming / Watts Humphrey / SEI lineage: the Plan-Do-Check-Act cycle, statistical process control, PSP/TSP discipline, CMMI level 4-5 quantitative process management. The thesis: a process that produces defects can itself be measured and improved, and over enough disciplined iterations the *process* comes under statistical control even when individual outcomes vary. This document operationalizes that thesis for QPB.

**The recursion is load-bearing.** QPB applies QE to find bugs in code; QPB applies QE to QPB itself to find process defects in its own bug-finding methodology; the apparatus that makes the second possible (regression replay automation, structured calibration ledgers, pinned benchmarks) is exactly what enables continuous improvement over many releases. The aesthetics are pleasing but they're not the point — the point is that if the first half worked because the methodology was sound, the second half should work for the same reason.

**Honest caveat: the substrate is novel.** Statistical process control was developed for manufacturing processes, where stable underlying causes of variation are the norm. Whether LLM-driven processes produce statistically stable variation is an open empirical question — model versions drift, prompts drift, target codebases vary in heterogeneous ways. The methodology in this doc is being applied because it's the right framework to try on this substrate, not because we know in advance that the substrate will cooperate. The "moving toward statistical control" hedging in the trajectory below isn't humility theatre; it's the genuinely-open empirical question that the calibration cycles described in this doc will answer over time.

## Scope: improvement releases, not feature releases

This document covers the methodology for **improvement releases** — releases motivated by a missed-bug observation in regression replay or benchmark output, where the change is to pull an existing improvement lever and measure the recall delta. Vocabulary: verification dimensions (what we measure to decide a release succeeded), improvement levers (what we change to improve recall), regression replay (the test rig), pinned benchmarks (the ground truth), Council/TTP (the review gates).

This document does NOT cover **feature releases** — releases that add new capabilities to QPB. Feature releases follow design / implementation / Council review on the new surface; their methodology lives in `docs/design/QPB_v<X.Y.Z>_Design.md` and `docs/design/QPB_v<X.Y.Z>_Implementation_Plan.md`. The v1.5.x feature track (v1.5.0 divergence model and tier system, v1.5.1 Phase 5 writeup hardening, v1.5.2 bug-family amplification, v1.5.3 skill-as-code project-type classifier and four-pass derivation pipeline, v1.5.4 regression-replay machinery) is feature work end to end.

The improvement-loop methodology described here becomes operational at v1.6.0, when QPB is feature-complete on the v1.5.x infrastructure and the measurement machinery from v1.5.4 makes lever-pull releases quantifiable. Until v1.6.0, this document is prospective: it describes how QPB *will be* improved once the apparatus is in place. After v1.6.0, every release is governed by the loop described here.

## The methodology: Plan-Do-Check-Act

The improvement loop runs the Deming/Shewhart PDCA cycle with **benchmark recovery against pinned ground truth** as the Check step.

1. **Plan.** A defect or improvement candidate is identified — from a Council-of-Three review, from an empirical regression observed in benchmark output, from an adopter report, or from a regression-replay run. A hypothesis is formed: which **improvement lever** is wrong, and what change should improve which **verification dimension** (process compliance, outcome recall, or both).

2. **Do.** The change is implemented. Source edits go through Claude Code with a written brief. Docs-only edits to orientation files (`TOOLKIT.md`, `IMPROVEMENT_LOOP.md`, `TOOLKIT_TEST_PROTOCOL.md`, `README.md`, `DEVELOPMENT_CONTEXT.md`) may be applied directly per the workspace `AGENTS.md` carve-out. Every code-bearing change is reviewed by a Council-of-Three nested panel before merge; every docs change is reviewed by the Toolkit Test Protocol before release.

3. **Check.** The new release is run against the pinned benchmark repositories with known v1.4.5 ground-truth bug counts. Both **verification dimensions** (next section) are evaluated. The recall delta against the regression-replay set is recorded in the calibration log.

4. **Act.** If both dimensions pass and the calibration delta is positive (recall improved on the targeted bug class without regressing elsewhere), ship. If either regresses, the change is reverted or further iterated before the release lands.

The two pieces of vocabulary that hold this loop together are **verification dimensions** (what we measure to decide whether a release shipped successfully) and **improvement levers** (what we change to make a release better). They are different things; conflating them is the most common vocabulary mistake when describing this methodology, and the rest of this document keeps them strictly separated.

## Verification dimensions

The dimensions we *measure* on every improvement release. There are two, and a release must pass both to ship.

**Process compliance** — Does the run produce artifacts that conform to the expected shape? This is what `quality_gate.py` measures: BUGS.md heading format, regression-test patches, TDD logs, requirements pipeline output, mechanical extraction integrity, finalization summary in PROGRESS.md, writeup hydration completeness.

**Outcome recall** — Does the run actually find the bugs we know are there? This is what benchmark recovery measures: number of confirmed bugs against pinned repos with known ground-truth bug counts, by iteration strategy.

Both dimensions can fail independently. The most pernicious failure mode is **pass-process / fail-recall** — the run produces all the right artifacts and gates green while finding zero real bugs. This was historically observed when an under-powered code-generation model was used (see `TOOLKIT.md` "Cursor" entry). It cannot be detected by the gate alone; only benchmark recovery exposes it.

The opposite mode — **fail-process / pass-recall** — is rare but possible (the run finds real bugs but produces malformed artifacts that fail the gate). When it happens, the bugs are still useful but the release is not shippable until the artifacts are corrected.

These dimensions describe how we *verify* an improvement release; they are not the handles we turn to make the release better. The handles are the **improvement levers** described next.

## Improvement levers

The decoupled surfaces you change to make an improvement release better. Each lever has a known home in the codebase, can be tuned without affecting the others, and is what you reach for when a regression-replay run shows the playbook missing a known bug.

The criterion for "is this a real lever?" — pulling it should produce a change in measured outcome recall (or process compliance) on benchmark replay without simultaneously requiring edits to the homes of other levers. A handle that requires touching three files in three different conceptual surfaces is not yet a clean lever; it's a candidate for refactoring into one.

New levers are added to the inventory when they ship — not when they're planned. A lever that doesn't yet exist as a tunable surface in the codebase belongs in a feature release's design doc, not in this inventory.

### Lever 1 — Exploration breadth/depth

**Home:** `references/exploration_patterns.md`, `references/iteration.md`. The four-strategy taxonomy (gap, unfiltered, parity, adversarial) lives there.

**What it controls:** How the playbook explores the codebase — pattern coverage, iteration strategies, depth-of-trace expectations, and what the agent is told to skip vs. dig into.

**Decoupled?** Yes — pure prompts/markdown, no code touch needed when the lever stays prompt-side.

### Lever 2 — Code-derived vs domain-derived requirements

**Home:** `references/requirements_pipeline.md`, `references/requirements_review.md`, `references/requirements_refinement.md` (the prompts that decide how requirements are sourced and refined); `bin/citation_verifier.py` (the code-side enforcement that prevents code-derived requirements from being laundered into citable spec).

**What it controls:** Whether requirements anchor to an external authoritative source (domain-derived, citable, Tier 1/2) or are extracted from the code itself (Tier 3, prone to laundering existing behavior into the spec).

**Decoupled?** Mostly yes — three reference files for the prompts plus one code module for the citation check.

### Lever 3 — Gate strictness

**Home:** `quality_gate.py` (single file, package at `.github/skills/quality_gate/`).

**What it controls:** What the mechanical gate accepts vs. rejects — regex shape, schema, completeness, evidence presence, writeup hydration, mechanical-extraction integrity, BUGS.md format, TDD log presence.

**Decoupled?** Yes from the other levers; not internally separated by lever (the file is organized by check, not by lever). Pulling this lever is a code edit at a known location.

### Lever 4 — Finalization robustness

**Home:** `bin/run_playbook.py` (`_finalize_iteration` helper).

**What it controls:** Orchestrator-side post-iteration finalization — running the gate as a subprocess, capturing stdout/stderr to `quality/results/quality-gate.log`, appending a structured block to `PROGRESS.md`, and mapping ABORTED status into the INDEX `gate_verdict` field.

**Decoupled?** Yes — orchestrator code, distinct from gate internals (the helper subprocesses the gate rather than reimplementing it).

### Lever 5 — Mechanical extraction surface

**Home:** Today, split across `SKILL.md` (which tells the agent what to extract mechanically) and `bin/run_playbook.py` / `quality_gate.py` (which validate the extraction shape and enforce the integrity check). The underlying surface IS a real lever today — what gets mechanically extracted is tunable now, even if the tuning requires lockstep edits across files.

**What it controls:** What the playbook extracts mechanically (case labels, exception handlers, defensive patterns) versus what it relies on the model to summarize, plus the integrity-check guarantee that no one rewrote the extraction file by hand.

**Decoupled?** **Not cleanly today.** This is the worst-decoupled lever in the inventory. Pulling it means editing both sides in lockstep — change a mechanical-extraction rule in `SKILL.md` and you usually need to update the validator in code, or vice versa. A future feature release may pull the prompt-side rules into a single `references/mechanical_extraction.md` and consolidate validation into a single choke-point in code; that refactor would convert this lever from "tunable but coupled" to "tunable and decoupled" without changing what the lever does.

### Adding new levers

Discovered through regression replay (next section). When a missed-bug investigation cannot be cleanly attributed to one of the existing levers, that's a candidate new lever — name it, find its home in the codebase, document it here, and update the inventory. Levers that are *planned* but not yet built (e.g., a categorization tier policy that would let runs surface standout findings if such a feature existed) belong in feature-release design docs, not in this inventory.

## Regression replay (lever calibration runs)

The methodology that makes improvement levers concrete. To validate that a lever change actually helps, take a pinned benchmark repository, roll back to a commit just before a known QPB-* bug was fixed, and run the playbook against that commit. Two outcomes:

- **The playbook finds the bug.** Positive control. The levers in their current state are sufficient for this class. No change needed.
- **The playbook misses the bug.** Diagnose which lever, if pulled, would have caught it. Pull that lever. Re-run. Verify (a) the bug is now found, and (b) recall on the rest of the same benchmark is preserved (no regression on bugs the prior version was finding).

This gives a clean, decoupled improvement signal. It isolates a specific class of bug behind a specific lever, separates "pulling a lever" from "side effects on unrelated levers," and produces an empirical record of which lever solved which class of miss.

Used informally during v1.5.x development. The measurement infrastructure that makes this loop quantitative — `bin/regression_replay.py` taking a benchmark + bug ID + lever-under-test, running the playbook against the pre-fix commit, recording the before/after recall delta to a structured log — is the v1.5.4 deliverable. Once v1.5.4 lands, the loop becomes operational.

## Pinned benchmarks

The Check step uses three pinned benchmark repos with known v1.4.5 ground-truth bug counts:

- `chi-1.5.1` — Go web framework
- `virtio-1.5.1` — Linux kernel C
- `express-1.5.1` — Node.js

Each is pinned to a specific upstream commit so the ground truth is stable across QPB releases. The bugs found in v1.4.5 form the recovery baseline: a later run on `chi-1.5.1` should find at least as many of the v1.4.5 confirmed bugs as v1.4.5 itself did (recall preservation), with new findings being net improvement.

When a new pinned benchmark version is created (e.g., `chi-1.6.0`), the v1.4.5 ground truth from the older pin is imported as the starting recall floor.

The benchmark repos cover three ecosystems with substantively different failure modes — Go HTTP routing, kernel-C transport variants, JavaScript parser laxity — so a regression that only manifests in one ecosystem is still observable.

## Council-of-Three review and the Toolkit Test Protocol

Every code-bearing change to QPB source goes through a Council-of-Three nested panel review (3 outer × 3 inner = 9 perspectives) before merge. The protocol is documented in the workspace `AGENTS.md` (Council-of-Three Invocation section), including the CLI form, working-directory discipline, and acceptance checks against fabrication.

Docs-only changes to orientation files use the **Toolkit Test Protocol** (`TOOLKIT_TEST_PROTOCOL.md`) instead, which is purpose-built for documentation review through reader personas. This is the docs analogue of benchmark-driven calibration: the Check step is whether the doc supports correct answers across reader personas, where Council's Check step is whether the code passes the gate and recall holds.

## Benchmark replicate harness

Methodology infrastructure for variance estimation. A 24/7-capable batch driver at `repos/replicate/` runs each (qpb_version, pinned_benchmark) cell N times with disciplined operational definitions, producing the within-version variance data that any "moving toward statistical control" claim requires. The harness is benchmark material under `repos/`, not QPB source; plan files at `repos/replicate/plans/*.json` declare which (version, target, N) tuples to run; per-replicate run dirs carry a `quality/replicate_intent.json` marker so future analysis can distinguish deliberate replicates from fix-and-rerun pollution.

The harness is recoverable across machine reboots — state lives in `state/runs.jsonl` (append-only), and resumption is "count completed events per (plan, target) and continue from the next pending replicate." Pacing between runs is configurable per plan to avoid LLM rate limits.

The harness exists so the σ estimates that gate the "Measurement and statistical control" trajectory below have a real empirical basis rather than informal claims. Runs accumulate as compute permits; the data is published to this document when a cell reaches N≥5.

## Measurement and statistical control

The playbook is currently **instrumented and trend-aware**, not yet **under statistical control** in the formal SPC / CMMI level 4 sense. Reaching statistical control is the long-horizon goal of the methodology described in this document.

What this means today:
- Per-release benchmark runs are recorded with bug counts by iteration strategy.
- Trend analysis across releases is possible (does a later release find more bugs than an earlier one on `chi-1.5.1`?).
- Gate failures and process compliance metrics are captured per run.

What this does NOT mean today:
- Within-version variance estimates are still being collected — typically each benchmark is run once per release, but ≥3-5 re-runs per version are needed to estimate variance. The replicate harness exists to close this gap.
- Control charts with statistically meaningful ±3σ limits do not exist yet — typically you want 20-30 stable observations within a single process to compute control limits. Current observations are spread across multiple versions.
- No metric is declared in statistical control today.

The trajectory is staged by precondition, not by release. Each stage has a clear input from the previous one, so they can't be reordered:

**Stage A — Within-version variance estimation.** Run replicates of the same (release × benchmark) cell to produce σ. Precondition: replicate harness operational and at least N runs per cell completed for at least one release. The harness exists; the data accumulates as compute permits. Output: σ estimates land in this section as the empirical floor for any later quantitative claim.

**Stage B — Regression-replay automation.** Build the apparatus to run the playbook against a benchmark commit before a known fix landed, recording the recall delta. Precondition: variance estimates from Stage A exist for at least a baseline cell so the delta can be tested against the noise floor. Output: a structured ledger of lever-calibration cycles where each entry maps a missed bug to a lever pull and the measured recall change. This is the v1.5.4 deliverable.

**Stage C — Continuous lever-pull improvement.** Use the v1.5.4 machinery to do iterative improvement: each release motivated by a regression-replay observation, pulled a single lever, measured recall delta, shipped if positive without regressions elsewhere. Precondition: Stage B machinery operational. Output: an accumulating ledger of improvement releases, each with a documented lever pull and measured outcome. This is the v1.6.0+ workflow.

**Stage D — Control charts and cross-cohort comparison.** Build SPC-style charts on accumulated variance data, including a control-limits scaffold and a regression-detection rule. Compare σ between releases (does a later cohort have tighter variance than an earlier one?). Precondition: ~20-30 stable observations within a single process. The pre-condition count comes from PSP/TSP work at SEI; deviating below that produces charts that look statistical but aren't. Multi-year horizon.

**Stage E — Statistical control claim.** Once enough data has accumulated and a metric is plausibly stable, evaluate whether QPB's process can be honestly said to be in statistical control under that metric. The "honestly" qualifier matters: control isn't declared because we want it; it's declared because the data supports it under the standard SPC criteria. Failing to reach Stage E is also an honest outcome — the LLM substrate may not produce statistically stable variation under any of our current metrics, and discovering that is a finding, not a failure.

The discipline is inspired by Watts Humphrey's PSP/TSP work at SEI and the CMMI level 4 ("quantitatively managed") definition. That discipline took years for SEI to instrument and is rare even at large software organizations that explicitly target it. The honest framing for QPB today is "moving toward statistical control" with a multi-year horizon. Overclaiming today undermines the credibility of the eventual claim.

### Operational definitions (work-in-progress)

For metrics to be meaningful across releases, they need stable operational definitions. Drafted definitions:

- **Bug count (per repo per release per strategy)** — number of `### BUG-NNN` headings in `BUGS.md` after the named iteration strategy, after gate-pass, after categorization. Bugs found in baseline phases count toward the baseline; bugs found in iteration N count toward iteration N.
- **Process gate pass** — `quality_gate.py` exits 0 against the full repo at end-of-run, before any manual remediation. Soft warnings are logged but do not affect pass/fail.
- **False positive rate** — bugs that, on manual review of a sampled subset, are not actual defects. Requires manual sampling; cannot be computed automatically. Expressed as a confidence interval given the sample size.
- **Recall against ground truth** — fraction of v1.4.5-confirmed bugs in the pinned benchmark that are recovered by the current release. Computed automatically by ID matching against the v1.4.5 BUGS.md.
- **Run cost** — total token usage across all phases, plus wall-clock time. Captured per phase in PROGRESS.md.
- **Within-version variance** — standard deviation of bug count across N re-runs of the same release on the same pinned benchmark. Requires ≥3 re-runs per version; collected via the replicate harness.
- **Lever calibration delta (regression replay)** — change in benchmark recall on a pre-fix commit before vs. after a lever change. Captured per regression-replay run via v1.5.4's `bin/regression_replay.py`.

These definitions will be formalized in `metrics/SCHEMA.md` when the metrics pipeline is built.
