# Model comparison pilot protocol

**Design agreed by Andrew and Fable on 4 October 2026. Versioned planning document, not an execution freeze or preregistration. The listed execution decisions remain to be filled before the pilot starts.**

This is the bounded pilot distilled from Andrew's discussion with Astra, Opus, and Fable. The [paper proposal](MODEL_COMPARISON_PAPER_PROPOSAL.md) retains the broader research ideas; this protocol governs the proposed pilot scope once its open decisions are settled.

## Purpose and size

Measure three things: which supported requirements configurations identify, which real defects they find when given identical requirements, and how consistently they do each across repeated runs. Test whether the measurement procedure is feasible; do not require a model ranking or a significant difference for success.

Use two pinned project scopes, four configurations (Haiku, Luna, Sonnet, Terra), and three fresh repetitions per configuration and scope. This is **24 derivation tasks plus 24 discovery tasks**. These are bounded QPB tasks, not complete audits. Exact model IDs, reasoning settings, harness versions, QPB commit, instructions, tools, and budgets must be recorded before execution. A configuration means model plus harness plus settings.

Compare configurations within providers and across measured costs; provider tier names are not equivalent capability levels. Exact served model identifiers are required, not just the discussion labels above. The pilot does not test a general claim that stronger or more expensive models find more defects.

Choose small scopes with several previously confirmed defects so the pilot exercises scoring. Record this deliberate selection effect and any prior use in QPB prompt development. Known answers remain outside execution inputs. Historical runs inform scope, matching rules, and effort estimates; they do not fill experimental cells. Separate known-defect rediscovery from additional discoveries; do not label the latter previously unreported without a prior-report search.

## Relationship to the full study

**The pilot is independent. Its runs will not count as observations in the full study's model-comparison tables.** Report pilot results separately as feasibility evidence about matching, adjudication effort, execution, and variability. They may inform the full study's design without being pooled into its comparison results.

The full study can add configurations, including Sol and Opus, and more projects after the pilot. Its roster, sample size, and repetition count are not decisions required to start this pilot. Do not add strong-model derivation tasks merely to preserve a pilot reference set for later use.

Freeze requirements within each experiment, not permanently across the research program. The full study will build and freeze its own requirement pool for each selected project snapshot. By default, reuse the pilot's matching procedure and relevant validation evidence, while constructing the full study's pool from its independently generated outputs. If pilot requirements are explicitly used to seed a later pool, declare that before the later runs, identify seeded requirements separately, and state how they affect the denominator. Pinned snapshots support reuse of validation evidence but do not remove selection effects or answer-leakage risks. Keep prior findings, fixes, and adjudication records out of derivation inputs; discovery receives only its declared frozen requirements and supporting sources, not hidden adjudication notes.

## Execution

1. **Derive requirements.** Give each configuration the same code snapshot, scope, evidence corpus, and derivation instructions. Preserve every output. No council, iterations, fixes, or access to other runs.
2. **Build the reference set.** Pool the 12 derivation outputs for each scope. Normalize and adjudicate the requirements with configuration identities hidden. Check them against evidence of intended behavior, combine equivalent requirements, and freeze the resulting set and supporting passages before any discovery task.
3. **Verify requirements against the implementation.** In fresh sessions, give every configuration the same frozen requirements, supporting passages, and code snapshot. Use the single-model requirement-verification instructions, identified and archived at the chosen QPB commit. Generic code review is not a substitute. Preserve findings before any external review; no council, iterations, or fixes during discovery. Reproduction attempts are permitted equally under the declared tool budget.

**Screen the inputs.** Before derivation, check the input snapshot for prior QPB artifacts, including `REQUIREMENTS.md`, `EXPLORATION.md`, other exploration output, generated tests, findings, fixes, and adjudication records; exclude these prior-run artifacts from both tasks. Before freezing discovery inputs, screen every supporting passage for disclosure of a target defect, its reproducer, or its fix. Exclude answer-disclosing material and log the exclusions; retain legitimate statements of expected behavior even when they make a violation easier to detect. A requirement without remaining adequate support cannot enter the validated pool. Do not add or sharpen requirements from the known-defect answer set during screening.

Freeze instruction text and the requirement batching/ordering rule before derivation begins. Specificity follows supporting evidence: do not add bug locations or failing inputs learned from answers, and do not remove legitimate source detail merely because it helps reveal a defect. No universal requirement-count limit is assumed.

Within each stage, interleave configurations in randomized blocks, with one run of each configuration per scope and repetition block. Save the schedule before that stage starts. Use isolated sessions, comparable tool access, and declared execution budgets. Record interruptions, service/version changes, and failed runs. Retain original attempts; apply a predefined retry rule without selecting whichever result looks best.

## Matching and adjudication

A requirement unit is one independently assessable obligation, with conditions and scope preserved. Match semantic coverage rather than wording. Preserve parent-child links and original statements; one broad statement can cover multiple units only when it actually expresses them. Raw statement counts remain descriptive, not the coverage score.

Validate that supporting evidence applies to the requirement and project version. Citation existence alone is insufficient. Apply the same support criteria to singleton and commonly repeated requirements. Unresolved obligations stay outside the validated denominator and are reported separately.

Match defects by triggering conditions, violated obligation, and underlying cause. Validate each distinct defect once per relevant snapshot, then check which reports actually identify it. Record confirmed, rejected, and unresolved claims, with reproduction scope and evidence limitations. A bad fix does not automatically invalidate a defect. Fixing and upstream submission may follow separately.

**Proposed responsibility:** Andrew performs primary adjudication. A second human reviewer independently re-judges a prespecified random sample covering requirement-support decisions, requirement decomposition/equivalence and per-run matching decisions, and defect validity/matching decisions. Sample across accepted, rejected, and unresolved outcomes, using declared strata so requirement judgments are not omitted. Both judge without configuration labels. Record agreement by decision type before resolving disagreements. Name the second reviewer and sampling procedure before the first derivation run. Any assisting model, its role, and its access are disclosed; using a model outside the roster does not by itself establish independence. Configuration blinding cannot guarantee that writing style reveals nothing.

Bound workload through scope first. The initial plan is to adjudicate the complete distinct claim pool. If the predetermined effort cap is exceeded, report feasibility failure or revise the protocol transparently; do not silently introduce convenience sampling or publish exact precision for partially judged outputs.

## Scores

| Dimension | Reported score |
|---|---|
| Requirements discovery | Per-run percentage of the scope's validated pooled obligations covered |
| Defect discovery | Unique confirmed defects per run that violate the frozen requirements, alongside overall precision: confirmed divided by confirmed plus rejected distinct claims |
| Repeatability | Per-obligation and per-defect detection frequency, such as 2 of 3 eligible completed runs |

Report unresolved claims, unsupported requirements, and completion/failure counts alongside scores. Precision is undefined when no claims have been adjudicated, not automatically 100 percent. Report detection conditional on completed runs alongside the scheduled-run denominator so failures cannot improve apparent reliability by disappearing.

**Discoveries outside the frozen requirements:** adjudicate and report them separately as additional discoveries, outside the fixed-requirements defect yield. Record the violated frozen requirement IDs for every defect counted in that yield; unresolved mappings remain separate. Do not expand the frozen set after seeing discovery results. Overall precision includes all adjudicated claims, including additional discoveries and rejected claims without a valid requirement link, so reporting outside the set cannot hide false claims. Label defect detection frequencies by whether they concern the frozen set. Frozen-set membership and prior-known status are separate attributes: a historical anchor can be outside the pool, and a new discovery can violate a frozen requirement.

**Known-defect attribution table:** for each anchor defect, record whether the validated pool expresses the obligation needed to recognize it, the matching requirement IDs, and which derivation runs identified that obligation. Mark full, partial, absent, or unresolved coverage explicitly. Then record each configuration/run's detection of the defect. Report (a) the fraction of anchors whose necessary obligation is fully represented in the pool, and (b) detection conditional on that coverage, with both numerators and denominators. An anchor absent from the pool is not scored as a missed verification of a supplied requirement; detection of it is an additional discovery. Keep partial/unresolved coverage separate. This table is an adjudication output, never an execution input, and cannot be used to repair the frozen requirements after discovery.

Show project-level results and raw numerators/denominators. Report tokens, time, tool use, cost, and adjudication effort separately; no composite score. The pool is an observed, validated reference set, not all requirements or all defects. Its dependence on the roster is a limitation regardless of whether a stronger model participates.

Requirement categories are secondary. Draft a small codebook before the pilot covering behavioral subject, source provenance, and triggering conditions. Preserve parent/decomposed views. Capture–recapture, crossed requirement sets, stronger-model comparisons, and longitudinal experiments are deferred.

## Feasibility and comparison outcomes

Before execution, specify numerical feasibility thresholds for adjudication effort, unresolved matching/support decisions, and independent-review agreement, plus the completion criterion. The pilot may fail these operational criteria even when scores can be calculated. No threshold should be selected after seeing which configuration wins.

For each planned comparison and outcome, define the difference being estimated, a practically meaningful margin, and an interval procedure appropriate to the small repeated sample. Use an interval for the **difference**, not overlap between separate configuration intervals. Do not treat requirements or defects from the same run as independent experimental runs.

- **Different in a practically meaningful direction:** the entire difference interval is above the positive margin or below the negative margin.
- **Similar within the chosen margin:** the entire interval lies within the equivalence band.
- **Inconclusive:** neither condition holds.

These labels concern a specified outcome and margin, not overall model equivalence. Three repetitions will often be inconclusive. A nonsignificant difference is not evidence of equivalence, and precision must accompany any yield comparison. If the pilot cannot support a defensible interval procedure, report descriptive results without declaring difference or equivalence.

## Decisions required before freezing

| Decision | Current state |
|---|---|
| Two scopes, commits, evidence snapshots, known-defect anchors | Unselected |
| Exact four configurations, instruction files, QPB commit, tool budgets, retry and batching rules | Unspecified |
| Second human reviewer, sampling procedure, adjudication effort cap | Unassigned |
| Feasibility thresholds, planned contrasts, outcome margins, interval method | Unspecified |
| Category codebook and stage scheduling procedure | To finalize |

The second human reviewer must be identified and available before the first derivation run. All other rows, including feasibility thresholds and comparison margins, must also be settled before viewing pilot outputs. Selecting scopes and preparing isolated inputs can proceed while arranging the reviewer; experimental runs wait for the execution freeze.

Date and commit the completed protocol before the first derivation run; preserve its commit ID. For an independently timestamped preregistration, deposit that version in a suitable registry or archive before execution. A local commit provides version history but does not eliminate author bias or independently prove timing. Record later amendments and whether outcomes had been inspected. After requirement adjudication, hash and freeze each shared input set before discovery, as specified above.

The design has converged. The next action is to fill the listed pilot decisions and freeze the execution version before running it. This document does not claim that preregistration, blinding, or a reviewer assignment has already happened. Committing the agreed design preserves the discussion's current state; it does not start the pilot or resolve its open choices.
