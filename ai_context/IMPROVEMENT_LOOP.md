# Quality Playbook — Improvement Loop

> This document is the canonical reference for **how the Quality Playbook is improved over time**. It is meta — it describes how we change the playbook between releases, what evidence we require before a change ships, and how we measure whether a release is better than the one before. The playbook's own internal mechanisms are described in `TOOLKIT.md` and `SKILL.md`.

## The methodology: benchmark-driven calibration

The Quality Playbook is a quality engineering tool, and it is itself engineered through the same discipline it advocates. Each release goes through a Plan-Do-Check-Act loop with **benchmark recovery against pinned ground truth** as the Check step.

1. **Plan.** A defect or improvement candidate is identified — from a Council-of-Three review, from an empirical regression observed in benchmark output, from an adopter report, or from a regression-replay run (see below). A hypothesis is formed: which **improvement lever** is wrong, and what change should improve which **verification dimension** (process compliance, outcome recall, or both).

2. **Do.** The change is implemented. Source edits go through Claude Code with a written brief. Docs-only edits to orientation files (TOOLKIT.md, IMPROVEMENT_LOOP.md, TOOLKIT_TEST_PROTOCOL.md, README.md, DEVELOPMENT_CONTEXT.md) may be applied directly per the workspace AGENTS.md carve-out. Every code-bearing change is reviewed by a Council-of-Three nested panel before merge; every docs change is reviewed by the Toolkit Test Protocol before release.

3. **Check.** The new release is run against the pinned benchmark repositories with known v1.4.5 ground-truth bug counts. Both **verification dimensions** (next section) are evaluated.

4. **Act.** If both dimensions pass, ship. If either regresses, the change is reverted or further iterated before the release lands.

The two pieces of vocabulary that hold this loop together are **verification dimensions** (what we measure to decide whether a release shipped successfully) and **improvement levers** (what we change to make a release better). They are different things; conflating them is the most common vocabulary mistake when describing this methodology, and the rest of this document keeps them strictly separated.

## Verification dimensions

The dimensions we *measure* on every release. There are two, and a release must pass both to ship.

**Process compliance** — Does the run produce artifacts that conform to the expected shape? This is what `quality_gate.py` measures: BUGS.md heading format, regression-test patches, TDD logs, requirements pipeline output, mechanical extraction integrity, finalization summary in PROGRESS.md, writeup hydration completeness.

**Outcome recall** — Does the run actually find the bugs we know are there? This is what benchmark recovery measures: number of confirmed bugs against pinned repos with known ground-truth bug counts, by iteration strategy.

Both dimensions can fail independently. The most pernicious failure mode is **pass-process / fail-recall** — the run produces all the right artifacts and gates green while finding zero real bugs. This was historically observed when an under-powered code-generation model was used (see TOOLKIT.md "Cursor" entry). It cannot be detected by the gate alone; only benchmark recovery exposes it.

The opposite mode — **fail-process / pass-recall** — is rare but possible (the run finds real bugs but produces malformed artifacts that fail the gate). When it happens, the bugs are still useful but the release is not shippable until the artifacts are corrected.

These dimensions describe how we *verify* a release; they are not the handles we turn to make the release better. The handles are the **improvement levers** described next.

## Improvement levers

The decoupled surfaces you change to make a release better. Each lever has a known home in the codebase, can be tuned without affecting the others, and is what you reach for when a regression-replay run (below) shows the playbook missing a known bug.

The criterion for "is this a real lever?" — pulling it should produce a change in measured outcome recall (or process compliance) on benchmark replay without simultaneously requiring edits to the homes of other levers. A handle that requires touching three files in three different conceptual surfaces is not yet a clean lever; it's a candidate for refactoring into one.

### Lever 1 — Exploration breadth/depth

**Home:** `references/exploration_patterns.md`, `references/iteration.md`. The four-strategy taxonomy (gap, unfiltered, parity, adversarial) lives there.

**What it controls:** How the playbook explores the codebase — pattern coverage, iteration strategies, depth-of-trace expectations, and what the agent is told to skip vs. dig into.

**Decoupled?** Yes — pure prompts/markdown, no code touch needed when the lever stays prompt-side.

**Exercised in:** v1.5.2 — when the playbook missed a known bug in benchmark replay, tightening the exploration prompts in `iteration.md` recovered it without touching gate internals or requirements logic.

### Lever 2 — Code-derived vs domain-derived requirements

**Home:** `references/requirements_pipeline.md`, `references/requirements_review.md`, `references/requirements_refinement.md` (the prompts that decide how requirements are sourced and refined); `bin/citation_verifier.py` (the code-side enforcement that prevents code-derived requirements from being laundered into citable spec).

**What it controls:** Whether requirements anchor to an external authoritative source (domain-derived, citable, Tier 1/2) or are extracted from the code itself (Tier 3, prone to laundering existing behavior into the spec).

**Decoupled?** Mostly yes — three reference files for the prompts plus one code module for the citation check.

**Exercised in:** v1.5.2 C13.6 (citation verifier with `reference_docs/cite/` extension check, tier marker semantics, downgrade-record skip, and `present:true` evidence).

### Lever 3 — Gate strictness

**Home:** `quality_gate.py` (single file, package at `.github/skills/quality_gate/`).

**What it controls:** What the mechanical gate accepts vs. rejects — regex shape, schema, completeness, evidence presence, writeup hydration, mechanical-extraction integrity, BUGS.md format, TDD log presence.

**Decoupled?** Yes from the other levers; not internally separated by lever (the file is organized by check, not by lever). Pulling this lever is a code edit at a known location.

**Exercised in:** v1.5.1 writeup hydration checks; v1.5.2 C13.8 (evidence regex tightening, strict bool validation on `present`, tier-marker body-mention exemption).

### Lever 4 — Finalization robustness

**Home:** `bin/run_playbook.py` (`_finalize_iteration` helper, introduced v1.5.2 C13.9).

**What it controls:** Orchestrator-side post-iteration finalization — running the gate as a subprocess, capturing stdout/stderr to `quality/results/quality-gate.log`, appending a structured block to `PROGRESS.md`, and mapping ABORTED status into the INDEX `gate_verdict` field.

**Decoupled?** Yes — orchestrator code, distinct from gate internals (the helper subprocesses the gate rather than reimplementing it).

**Exercised in:** v1.5.2 C13.9. Root cause of the issue addressed: the orchestrator's success path was taking the LLM's word for finalization rather than running the gate itself, producing stale `quality-gate.log` files (chi: 13 vs actual 15 bugs after parity) and silent half-state PROGRESS.md (express: started without a matching complete line).

### Lever 5 — Mechanical extraction surface

**Home:** Today, split across `SKILL.md` (which tells the agent what to extract mechanically) and `bin/run_playbook.py` / `quality_gate.py` (which validate the extraction shape and enforce the integrity check).

**What it controls:** What the playbook extracts mechanically (case labels, exception handlers, defensive patterns) versus what it relies on the model to summarize, plus the integrity-check guarantee that no one rewrote the extraction file by hand.

**Decoupled?** **Not cleanly today.** This is the worst-decoupled lever in the inventory. Pulling it means editing both sides in lockstep — change a mechanical-extraction rule in `SKILL.md` and you usually need to update the validator in code, or vice versa.

**Status:** **Cleanup is a v1.5.3 work item** (see "v1.5.3 work items" below). The cleanup pulls extraction rules into a single `references/mechanical_extraction.md` and consolidates validation into a single choke-point in code.

### Lever 6 — Categorization tier policy

**Home:** Not yet built. Lands in v1.5.3 — `references/categorization.md` for the prompt-side rules, plus a tagging step at the end of synthesis.

**What it will control:** The standout/confirmed/probable/candidate evidentiary tiers — what a finding has to demonstrate to earn each, including the `standout_justification` field for promotions to the standout tier.

**Decoupled?** Will be, by design — single reference file plus single tagging step. Designing the lever decoupled from the start avoids the lockstep-edit problem that Lever 5 has today.

### Adding new levers

Discovered through regression replay (next section). When a missed-bug investigation cannot be cleanly attributed to one of the existing levers, that's a candidate new lever — name it, find its home in the codebase, document it here, and update the inventory.

## Regression replay (lever calibration runs)

The methodology that makes improvement levers concrete. To validate that a lever change actually helps, take a pinned benchmark repository, roll back to a commit just before a known QPB-* bug was fixed, and run the playbook against that commit. Two outcomes:

- **The playbook finds the bug.** Positive control. The levers in their current state are sufficient for this class. No change needed.
- **The playbook misses the bug.** Diagnose which lever, if pulled, would have caught it. Pull that lever. Re-run. Verify (a) the bug is now found, and (b) recall on the rest of the same benchmark is preserved (no regression on bugs the prior version was finding).

This gives a clean, decoupled improvement signal. It isolates a specific class of bug behind a specific lever, separates "pulling a lever" from "side effects on unrelated levers," and produces an empirical record of which lever solved which class of miss. The output of a regression replay is a one-line entry in the lever's "Exercised in" list above.

Used informally during v1.5.x development. **Automation is the v1.5.4 theme** — see `Quality Playbook/Reviews/QPB_v1.5.4_Plan.md`. The v1.5.4 deliverable is `bin/regression_replay.py` plus a structured schema at `metrics/regression_replay/SCHEMA.md` and 3-5 worked lever-calibration cycles documented in `Quality Playbook/Reviews/Lever_Calibration_Log.md`. Once the automation lands, every change in v1.5.5+ carries a before/after recall delta on the regression-replay set.

## Pinned benchmarks

The Check step uses three pinned benchmark repos with known v1.4.5 ground-truth bug counts:

- `chi-1.5.1` — Go web framework
- `virtio-1.5.1` — Linux kernel C
- `express-1.5.1` — Node.js

Each is pinned to a specific upstream commit so the ground truth is stable across QPB releases. The bugs found in v1.4.5 form the recovery baseline: a v1.5.2 run on `chi-1.5.1` should find at least as many of the v1.4.5 confirmed bugs as v1.4.5 itself did (recall preservation), with new findings being net improvement.

When a new pinned benchmark version is created (e.g., `chi-1.6.0`), the v1.4.5 ground truth from the older pin is imported as the starting recall floor.

The benchmark repos cover three ecosystems with substantively different failure modes — Go HTTP routing, kernel-C transport variants, JavaScript parser laxity — so a regression that only manifests in one ecosystem is still observable.

## Council-of-Three review and the Toolkit Test Protocol

Every code-bearing change to QPB source goes through a Council-of-Three nested panel review (3 outer × 3 inner = 9 perspectives) before merge. The protocol is documented in the workspace `AGENTS.md` (Council-of-Three Invocation section), including the CLI form, working-directory discipline, and acceptance checks against fabrication.

Docs-only changes to orientation files use the **Toolkit Test Protocol** (`TOOLKIT_TEST_PROTOCOL.md`) instead, which is purpose-built for documentation review through reader personas. This is the docs analogue of benchmark-driven calibration: the Check step is whether the doc supports correct answers across reader personas, where Council's Check step is whether the code passes the gate and recall holds.

## v1.5.3 work items

Three changes planned for v1.5.3, in landing order:

1. **C13.11 cleanup pass** — Round 8 non-blocking hardening, lands first against the simplest baseline. Brief at `Quality Playbook/Reviews/QPB_v1.5.3_C13_11_Brief.md`.
2. **Mechanical extraction lever cleanup** — Lever 5 decoupling. No new behavior; refactor only.
3. **Bug categorization tagging** — Lever 6 (new). The most consequential v1.5.3 change for adopters.

The regression-replay automation that previously lived here as an "optional, may slip" item has been pulled forward into v1.5.4 as that release's theme (see `Quality Playbook/Reviews/QPB_v1.5.4_Plan.md`). The benchmark replicate harness now lives in `repos/replicate/` as benchmark material, not a v1.5.x work item.

### C13.11 cleanup pass — Round 8 non-blocking hardening

The Round 8 Council review (`Quality Playbook/Reviews/QPB_v1.5.2_Council_Round8_Synthesis.md`) cleared v1.5.2 to ship (8 of 9 panelists Ship/Merge, 1 Block on a structural test-discipline issue). It surfaced six small hardening items that didn't block the tag but cluster naturally into a single C13.11 cleanup commit during v1.5.3 release-prep. Full brief at `Quality Playbook/Reviews/QPB_v1.5.3_C13_11_Brief.md`. Six fixes:

1. **Centralize release version constant** in `bin/benchmark_lib.py` and route the version-stamp test through it (closes the codex/Panel-3 Round 8 Block).
2. **`detect_repo_skill_version()` coverage** in `bin/tests/test_run_playbook.py` to catch root↔installed-copy stamp drift in CI.
3. **`_mark_iterations_explicit` audit comment** at `bin/run_playbook.py:420` documenting the hardcoded prefix tuple.
4. **Mutation-integration scenario** for `bin/tests/test_citation_stale.py` — exercise the actual mutation→hash-divergence path, not just the round-trip.
5. **`sys.path` cleanup** in `test_citation_stale.py:36-39` — replace manipulation with proper test-import mechanism.
6. **Phase 6 verdict-matrix completion** — add the `(pass, gate_passed=False, no warn)` → `"fail"` cell test to `bin/tests/test_finalizer.py`.

These are intentionally batched as one cleanup commit set rather than scattered fixes. None affects shipped behavior; all improve maintainability or test discipline. Lands first so the categorization-tagging and mechanical-extraction work goes in against a clean baseline.

### Mechanical extraction lever cleanup

Pull Lever 5 (mechanical extraction surface) into a cleanly decoupled state. Today the lever is split across `SKILL.md` and the validator code in `bin/run_playbook.py` / `quality_gate.py`, so changing how mechanical extraction works requires lockstep edits across multiple surfaces. The cleanup:

1. **New `references/mechanical_extraction.md`.** Single home for the prompt-side rules: what gets mechanically extracted (case labels, exception handlers, defensive patterns), what shape the extraction artifact must take, what the agent is forbidden from writing by hand, how the integrity check is described to the agent. Today this content is scattered through SKILL.md alongside operational instructions; pulling it out makes it editable as a single lever.

2. **Single validation choke-point.** Consolidate the integrity check into a single function (likely `quality_gate.py::check_mechanical_extraction` or a dedicated module). Today the integrity check is invoked from multiple places with subtly different framing; one choke-point means one place to edit when the rule changes, and one place for unit tests to cover.

3. **Backward compatibility.** The existing `quality/mechanical/` artifact contract (the saved extraction files plus `verify.sh`) is preserved. Only the source-side rules and the validation module are restructured; downstream artifact consumers do not change.

Outcome: a future change to mechanical extraction (e.g., adding a new extraction class for switch-on-string dispatch, or tightening the integrity check to detect more sophisticated tampering) becomes a one-file edit on the prompt side and a one-function edit on the validation side, rather than a distributed change across `SKILL.md`, `bin/run_playbook.py`, and `quality_gate.py`.

The cleanup is scoped as a refactor — no new behavior, no new gate, no recall-relevant changes. The verification dimensions check that nothing regressed: process compliance is unchanged on benchmark replay, outcome recall is unchanged on benchmark replay.

### Bug categorization tagging

A new tagging pass at the end of synthesis annotates each confirmed bug along a confidence/material dimension. The tagging is not a new gate — it does not gate-fail a run that has zero standouts, and it does not block a release if the distribution is unusual. Adopters use the tags to prioritize which findings to triage first.

The four tiers, in descending evidentiary strength:

- **standout** — bugs an experienced engineer would describe as "huh, didn't see that." Earned, not required in every run. Most valuable for open-source upstream submissions and showcase findings. A run can ship with zero standouts; a run cannot promote a finding to standout without explicit justification in the bug record (the `standout_justification` field, required for any standout-tagged bug). The test: what would a senior maintainer of this project say if shown this finding? Surprise plus actionable specificity is the bar.
- **confirmed** — solid evidence, normal severity, the run's reliable findings. The default tier for bugs that pass the standard evidentiary bar.
- **probable** — code-path trace supports the finding but evidence is partial; an experienced reviewer would likely accept after a closer look. Worth surfacing but not load-bearing.
- **candidate** — adversarial-iteration findings with the lower evidentiary bar; flagged as worth review but not promoted. Often correct, but the "is this actually wrong or is it a design choice?" question is genuinely open.

The standout tier is the most consequential change for adopters who plan to submit upstream PRs. The new lever (Lever 6 above) sits behind this work item.

## v1.5.4 theme

**Improvement-protocol shakedown via historical regression replay.** Full plan at `Quality Playbook/Reviews/QPB_v1.5.4_Plan.md`. Three deliverables: `bin/regression_replay.py`, `metrics/regression_replay/SCHEMA.md`, and 3-5 worked lever-calibration cycles in `Quality Playbook/Reviews/Lever_Calibration_Log.md`. After v1.5.4, every release carries an empirical before/after recall measurement on a defined regression set.

## v1.5.5 theme

**Naive-review phase.** Full plan at `Quality Playbook/Reviews/QPB_v1.5.5_Plan.md`. Adds Phase 7 (one-shot naive code review running after the iteration strategies) and writes its findings to a separate `quality/NAIVE_FINDINGS.md` artifact (Option B in the plan; reconciliation into BUGS.md is deferred to v1.6.x). Empirical motivation: cross-target naive review found 33-57% of QPB's bug count, with non-trivial overlap and a few genuine novel finds — partial complementarity that becomes a built-in feature of the playbook in v1.5.5.

Both v1.5.4 and v1.5.5 are downstream of v1.5.3's lever cleanup and categorization vocabulary; do not start them until v1.5.3 has tagged.

## Benchmark replicate harness

A 24/7-capable batch driver at `repos/replicate/` runs each (qpb_version, pinned_benchmark) cell N times with disciplined operational definitions, producing the variance data that "moving toward statistical control" needs. The harness is benchmark material under `repos/`, not QPB source; plan files at `repos/replicate/plans/*.json` declare which (version, target, N) tuples to run; per-replicate run dirs carry a `quality/replicate_intent.json` marker so future analysis can distinguish deliberate replicates from fix-and-rerun pollution.

Initial plans:

- `v1.5.2_pinned_variance.json` — N=5 per pinned benchmark at v1.5.2. Primary deliverable: defensible σ for chi-1.5.1, virtio-1.5.1, express-1.5.1, casbin-1.5.1.
- `v1.5.1_pinned_backfill.json` — N=3 at v1.5.1 to compare against v1.5.2 σ.
- `v1.3_regression_spotcheck.json` — N=3 against the three historical cells (chi-1.3.46, virtio-1.3.50, httpx-1.3.46) where the trend table showed surprising drops; tells us whether each drop was real signal or N=1 noise.
- `v1.5.3_expanded_roster.json` — single baseline run per new benchmark target (gorilla-mux, fastapi, clap, opa, rack). After vetting, targets are promoted into the pinned-benchmark plans for full replicate batches.

The harness is recoverable across machine reboots — state lives in `state/runs.jsonl` (append-only), and resumption is "count completed events per (plan, target) and continue from the next pending replicate." Pacing between runs is configurable per plan to avoid LLM rate limits.

The harness produces the empirical floor that the "Measurement and statistical control" section's σ claims need. Once `v1.5.2_pinned_variance` completes, the σ estimates land in that section as the data backing the "within-version variance is large" public-facing language.

## Measurement and statistical control

The playbook is currently **instrumented and trend-aware**, not yet **under statistical control** in the formal SPC / CMMI level 4 sense.

What this means today:
- Per-release benchmark runs are recorded with bug counts by iteration strategy.
- Trend analysis across releases is possible (does v1.5.2 find more bugs than v1.5.1 on chi-1.5.1?).
- Gate failures and process compliance metrics are captured per run.

What this does NOT mean today:
- We do not have within-version variance estimates (we typically run each benchmark once per release; ≥3-5 re-runs per version are needed to estimate variance).
- We do not have control charts with statistically meaningful ±3σ limits (you typically want 20-30 stable observations within a single process to compute control limits; we have ~30 observations spread across 4-5 versions).
- We do not yet declare any metric to be "in statistical control."

The trajectory:

- **v1.5.3:** Lever cleanup (mechanical extraction) + categorization vocabulary (standout/confirmed/probable/candidate). Within-version variance estimation continues running in the background via `repos/replicate/`; first σ data lands as `v1.5.2_pinned_variance` completes. Initial target is N=5 per (v1.5.2, pinned-benchmark) cell.
- **v1.5.4:** Regression-replay automation. `bin/regression_replay.py` plus `metrics/regression_replay/SCHEMA.md` plus 3-5 worked calibration cycles. The improvement protocol stops being a methodology claim and starts being a procedure with empirical backing.
- **v1.5.5:** Naive-review phase added as Phase 7. Empirically validated against the regression-replay set built in v1.5.4 (does the new phase improve recall, and at what false-positive cost?).
- **v1.6.x:** Categorization-promoted reconciliation between BUGS.md and NAIVE_FINDINGS.md (Option C from the v1.5.5 plan). Build control charts on top of accumulated variance data. Evaluate whether any metric has sufficient statistical power to be declared in control.
- **v1.7+:** Once 6-12 months of consistent data have accumulated, evaluate whether control charts on key metrics (bugs per benchmark per strategy, gate pass rate, false-positive rate, recall against ground truth) have sufficient statistical power to be meaningful.

The discipline is inspired by Watts Humphrey's PSP/TSP work at SEI and the CMMI level 4 ("quantitatively managed") definition. That discipline took years for SEI to instrument and is rare even at large software organizations that explicitly target it. The honest framing for QPB today is "moving toward statistical control" with a multi-year horizon. Overclaiming today undermines the credibility of the eventual claim.

### Operational definitions (work-in-progress)

For metrics to be meaningful across releases, they need stable operational definitions. Drafted definitions:

- **Bug count (per repo per release per strategy)** — number of `### BUG-NNN` headings in `BUGS.md` after the named iteration strategy, after gate-pass, after categorization. Bugs found in baseline phases count toward the baseline; bugs found in iteration N count toward iteration N.
- **Process gate pass** — `quality_gate.py` exits 0 against the full repo at end-of-run, before any manual remediation. Soft warnings are logged but do not affect pass/fail.
- **False positive rate** — bugs that, on manual review of a sampled subset, are not actual defects. Requires manual sampling; cannot be computed automatically. Expressed as a confidence interval given the sample size.
- **Recall against ground truth** — fraction of v1.4.5-confirmed bugs in the pinned benchmark that are recovered by the current release. Computed automatically by ID matching against the v1.4.5 BUGS.md.
- **Run cost** — total token usage across all phases, plus wall-clock time. Captured per phase in PROGRESS.md.
- **Within-version variance** — standard deviation of bug count across N re-runs of the same release on the same pinned benchmark. Requires ≥3 re-runs per version; not yet collected systematically.
- **Lever calibration delta (regression replay)** — change in benchmark recall on a pre-fix commit before vs. after a lever change. Captured per regression-replay run when the automation lands.

These definitions will be formalized in `metrics/SCHEMA.md` when the metrics pipeline is built.
