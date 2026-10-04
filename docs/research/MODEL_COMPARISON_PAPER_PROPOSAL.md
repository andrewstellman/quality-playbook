# Comparing models through requirements analysis and defect discovery

**Andrew Stellman · Second paper proposal · 4 October 2026**

**Status:** Abstract and bounded pilot design agreed by Andrew and Fable on 4 October 2026. Execution choices listed in the protocol remain open. The broader ideas below remain proposals, not finalized experiments or results. Venue remains open.

**Current abstract:** [Working abstract](MODEL_COMPARISON_ABSTRACT.md), revised with Andrew on 4 October 2026. It describes the full study without pilot-specific counts and records the possible later addition of Sol and Opus.

**Pilot scope after review:** The [bounded pilot protocol](MODEL_COMPARISON_PILOT_PROTOCOL.md) consolidates the subsequent Andrew, Astra, Opus, and Fable discussion. The agreed design uses two scopes, four configurations, and three repetitions of two isolated tasks. Complete-workflow, crossed-set, and longitudinal comparisons below remain possible later studies, not pilot commitments. Explicit decisions remain to be filled before the execution freeze.

**Independent pilot:** Pilot runs will be reported as feasibility evidence and excluded from the full study's model-comparison tables. The full study can add Sol and Opus and more projects, and will build its own requirement pools for its selected snapshots. Its roster, project count, and repetitions will be decided after the pilot. Reuse of pilot validation or matching work must follow the protocol's provenance and isolation rules; it is not automatic reuse of experimental observations.

## Purpose and relationship to the first paper

Use Quality Playbook as a repeatable experimental framework to compare models on two related capabilities: deriving supported behavioral requirements and discovering implementation defects against those requirements. Its phase boundaries make it possible to vary the model performing one task while holding the other task's inputs constant. Repeated runs can reveal differences in detection frequency, requirement coverage, defect classes, and cost.

This is distinct from the first paper's claim: QPB finds particular defects that standard review with the same model misses, with additional information contributing to some discoveries. Andrew does not claim that QPB generally outperforms standard review; standard review is itself a QPB phase. The second paper asks how different models perform within a common quality-engineering process, and where their differences arise.

The potential contribution is an evaluation method that connects requirements analysis to verified defect discovery, rather than only reporting an aggregate model ranking. Whether that contribution is sufficiently novel remains to be established against related work.

## Observations motivating the study

Andrew reports that recent Sonnet experiments suggest a less expensive model can carry out substantial portions of the work. Across repeated QPB runs, models often rediscover the same defects, but not on every run. He has observed changes in discovery profiles as models changed, and his experience suggests stronger reasoning models tend to find more bugs. These are motivating observations, not established causal results.

The study should test several possible explanations: stronger models may identify more relevant requirements; they may recognize violations more reliably given the same requirements; cheaper models may approach their yield through additional attempts; or different models may discover complementary defect classes. Repeated runs characterize observed variability without assuming that sampling entropy alone explains it. Tool failures, context handling, budgets, and model revisions can also change outcomes.

Record model identity, model version, and reasoning configuration separately. “Sonnet,” “Sol,” “Terra,” and “Astra” are discussion labels; execution records need exact served model identifiers and settings. Neither cost nor a model name establishes a reasoning level.

## Research questions

1. Which supported requirements do different models derive from the same project and evidence, and how does coverage vary by requirement class?
2. Given identical requirements, which confirmed defects does each model find, how often, and in which classes?
3. How much do requirements derivation and violation detection each contribute to complete-workflow results?
4. What additional discoveries do repeated attempts or combinations of models provide at comparable cost?
5. How do these profiles change across model versions while project inputs remain fixed?

## Experimental design

| Comparison | Fixed inputs | Varied factor | Main observation |
|---|---|---|---|
| Requirements derivation | Code commit, evidence corpus, instructions, tool access | Derivation model and repeated run | Supported requirements, omissions, unsupported requirements, decomposition patterns |
| Defect discovery | Code commit, shared frozen requirements, permitted evidence, discovery instructions and tools | Discovery model and repeated run | Confirmed defects, misses within the pooled set, rejected claims, variability |
| Complete workflow | Starting code, available evidence, QPB version and declared resource policy | Model carrying out derivation and discovery | Combined effectiveness and cost before council review |

The fixed-requirements comparison is central. It distinguishes failing to identify an expectation from failing to detect a violation of an expectation already supplied. Every model should receive the same supporting source passages as well as the same requirement statements in that arm.

Construct and adjudicate the shared requirements before the discovery experiment, then freeze them. Preserve their provenance and ensure they do not contain defect locations, failing examples, or fixes derived from the target answers. Do not automatically designate one model's requirements as ground truth. State whether the common set was independently authored or pooled and adjudicated; both choices have limitations.

An optional follow-up crosses requirements produced by model A with discovery performed by model B. This could show whether inexpensive derivation is sufficient, whether stronger derivation helps every downstream model, or whether an apparent advantage depends on a model's own wording. The fully crossed design is an extension, not a prerequisite for the first pilot.

Select projects before inspecting which model wins. Use identical clean snapshots within each comparison, isolated sessions without access to other runs, and a frozen QPB implementation. Keep harness behavior and tool permissions comparable. When provider-specific tools differ, describe the evaluated unit as the model plus its agent configuration rather than attributing every difference to the model alone.

Separate a common execution-budget comparison from an equal-cost comparison. Equal token counts across providers need not represent equal computation or price. Record tokens, elapsed time, tool calls, actual or estimated cost, and the budget/stopping rule. Do not silently give a weaker run extra attempts. Interleave configurations where practical to reduce time-dependent service effects.

## Requirements and defects as comparison units

Normalize requirements into independently assessable behavioral obligations, using conventional requirements decomposition. Preserve parent-child relationships and source links. Ten narrower statements should not automatically outrank one complete statement covering the same obligations. Score supported coverage and unsupported additions, not just statement counts. Code requirement classes such as input validity, state transitions, protocol obligations, configuration semantics, and user workflows; finalize the codebook after a pilot and before the main analysis.

A defect has a stable identity across model descriptions and repeated runs. Match findings by triggering conditions, violated requirement, and underlying cause. Preserve the original reports and record adjudicated equivalences, splits, and merges. Several failing tests or affected locations may represent one defect; similar symptoms can have different causes.

This is the useful sense in which bugs are interchangeable comparison units: the same bug can be recognized across outputs. Different bugs are not equal in difficulty, impact, or evidence burden. Keep those attributes alongside counts. Code defect mechanism, requirement class, source of expected behavior, and discovery phase separately so the study can examine patterns instead of assuming a single hierarchy of models.

## Stop discovery before council and validate separately

Freeze each run's independent findings before council review. This preserves attribution to the tested configuration and avoids paying for a full council for every discovery run. Specify the exact QPB phases, iterations, and stopping artifact; label this as an experimental variant, not a completed full QPB audit.

Pool and deduplicate findings, then validate each distinct claim separately from discovery. Hide the discovering model's identity from adjudicators where feasible. Use supported expected behavior, executable reproduction, and red/green evidence as appropriate; retain source-only and limited-harness evidence as distinct categories. Council agreement or a model's “confirmed” label is not sufficient evidence by itself.

Validation of a shared defect can be reused across runs on the same snapshot, while checking that each report actually identified it. Record confirmed, rejected, and unresolved claims separately. A patch failure does not automatically refute the original defect. Upstream acceptance adds evidence but is not required to count a reproducible, well-grounded defect; submission delays and contribution policies should not determine model scores.

## Measurements and analysis

| Measure | Interpretation |
|---|---|
| Supported requirement coverage | Coverage of adjudicated obligations, with decomposition normalized |
| Unsupported requirement share | Invented or unjustified obligations among adjudicated requirements |
| Unique confirmed defects per run | Discovery yield, with evidence level retained |
| Detection frequency per defect | Fraction of completed eligible runs reporting that particular defect |
| Overlap and additional discoveries | Shared and exclusive findings across models and accumulated attempts |
| Confirmed and rejected claim shares | Precision and false-discovery proportion among adjudicated claims; unresolved claims reported separately |
| Yield and verification effort by cost | Confirmed discoveries per dollar plus human/adjudicator effort and absolute yield |
| Results by coded class | Differences associated with requirement types, defect mechanisms, and evidence sources |

The confirmed union across models and runs is an observed reference set, not the complete set of bugs in the project. Any coverage measure against that union must be labeled accordingly. A newly verified discovery is added to the union, not scored false merely because it was absent from an earlier answer key. “False positive rate” conventionally requires a negative-opportunity denominator; use rejected-claim share or false-discovery proportion when only submitted findings are enumerated.

Report results per project and model as well as pooled totals. Repeated observations of the same bug are not independent new bugs, and defects within a repository may be correlated. Choose uncertainty estimates and comparisons that respect that structure. The pilot should establish variance and validation cost before selecting the main study size. Freeze primary outcomes and the classification procedure before evaluating the main sample.

## Freshness and related work

Andrew's motivation is that fixed public tasks can be trained against, whereas a reusable QPB procedure can evaluate fresh projects and defects. Use fresh prospective snapshots for generalization and retain frozen anchor snapshots for comparisons across model versions. Freshness reduces some leakage risks without proving absence from training data. Keep historical rediscovery separate from prospective discovery, and archive exactly what documentation and issue information each run could access. Issue discussions supplying general user expectations differ from reports revealing the target bug itself.

Two directly relevant sources were checked on 4 October 2026:

- [SWE-bench Goes Live](https://arxiv.org/abs/2505.23419) proposes a continuously updatable evaluation built from real issue-resolution tasks. Freshness and refreshable benchmarks are therefore not sufficient novelty claims on their own.
- [TestExplora](https://proceedings.mlr.press/v306/liu26ct.html) evaluates proactive bug discovery using documentation-derived intent and proposes continuous, time-aware collection. Its overlap with this proposal is substantial enough to require a detailed methods comparison before making novelty claims.

The candidate distinction is the explicit separation and recombination of requirements derivation and violation detection, linked to repeated observations of individual defects, requirement and defect classes, and resource use. This is a proposed contribution, not a claim that prior work lacks these features. The related-work check so far is preliminary, not a systematic review.

## Existing evidence and a proposed pilot

The [October 4 evidence tally](tally-2026-10-04/FINDINGS-TALLY.md) and [GPT control scoring](tally-2026-10-04/CONTROL-SCORING.md) provide candidate cases, identity-matching examples, and observations of repeated discovery/misses. They do not constitute this experiment: those controls used standard review, historical discovery models are not fully matched, and requirements were not frozen across the proposed arms.

First inventory the recent Sonnet runs Andrew mentioned and recover exact configurations, inputs, phase outputs, costs, and dates. Then select a small set of projects spanning more than one language/domain and run every selected model configuration on every selected project with repeated fresh sessions. Model roster, project count, repetitions, budgets, requirement-set construction, and exact phase boundaries remain to be decided. Prefer a pilot that tests the identity and adjudication procedures over a large launch with unstable scoring.

The pilot should produce linked project, run, requirement, finding, and adjudication records; a requirements codebook; a defect identity ledger; and a cost/coverage summary. Preserve negative outcomes and run failures. Decide the larger study after inspecting feasibility and variance, without tuning the protocol on the eventual evaluation projects.

## Review requested from Fable

Please review this as a proposed second paper, using the first paper's corrected claim above and the linked evidence tally for context. Distinguish defects in the design from optional extensions. In particular:

1. Is the contribution distinct enough from TestExplora, live coding benchmarks, and requirements-engineering model comparisons? What further literature must be checked?
2. Do the fixed-requirements and derivation comparisons isolate the intended capabilities? How should the shared requirement set be constructed without bias or answer leakage?
3. Are the proposed requirement normalization, defect identity rules, and validity categories defensible and affordable to adjudicate?
4. Which measurements and pilot choices are essential, and which would unnecessarily expand the paper? How should repeated runs and repository-level dependence be analyzed?
5. Can the Sonnet observations motivate a useful cost-effectiveness question without assuming cheaper models are intrinsically lower-reasoning or that stronger models must win?

Requested review output: a recommendation on scope and positioning, the most serious methodological risks, and concrete revisions to settle before executing a pilot. No model ranking, general-superiority claim, or contamination-free claim is assumed.
