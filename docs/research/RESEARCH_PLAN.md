# Quality Playbook publication research plan

Working plan, 27 September 2026. Companion to [the one-page prospectus](PAPER_PROSPECTUS.md).

## Working arrangement

Andrew selects publication goals, approves substantive study choices, and owns upstream communication. Astra (the planning assistant in Codex) maintains the research plan, evidence ledger, comparison protocol, and manuscript drafts; it checks execution outputs against the protocol. Claude Code can execute bounded inventory, reconstruction, and experiment tasks from written briefs. Each brief should identify inputs, permitted access, outputs, completion criteria, and unresolved questions. Execution agents must not see held-out answers or other arms’ findings.

This document is the durable handoff for future sessions. It does not schedule runs or authorize sending messages to maintainers. New experiments under this plan have not begun; Claude reports a historical April comparison to recover and assess. Claude is preparing the catalog, according to the feedback supplied by Andrew.

## 1. Build the catalog before choosing success stories

Inventory local run artifacts, benchmark manifests, previous reports, and existing upstream links. Record the search scope so that “all identifiable runs” has an auditable meaning. Missing logs or model identities stay unknown. A configured target is not evidence of an actual run.

Start with [evidence/README.md](../../evidence/README.md), the per-defect evidence folders, and `repos/linux/_runs/*/REPORT.md`, as well as the README and archived conversations. The first two locations exist in this checkout and contain reproduction and run records; they are not merely future collection targets. Preserve model identity separately for discovery, reproduction, and review, with provenance for each: an identity stated in a later method summary is different from one recorded in the original run log.

Use linked records rather than one row per repository trying to represent every event:

| Record | Required information |
|---|---|
| Project | Stable ID, upstream URL, language, reviewed subsystem, local evidence locations |
| Run | Stable ID, project ID, target commit, date, QPB commit/version, agent/CLI and model identities, full model roster, phases/iterations, prompts, documentation snapshot, available tools, resource usage, human interventions, completion status, artifact paths |
| Finding | Stable ID, run IDs, distinct defect identity, behavior and impact, evidence supporting expected behavior, exact source excerpts/links, prior-disclosure status, validation basis, tested implementation/commit/environment, reproduction and red/green logs, validation decision and reviewer |
| Submission | Finding IDs, issue/PR/patch-series URL, submission date, current disposition, maintainer response, merge commit and tree/branch, last verification date |

Deduplicate a defect across runs, patch revisions, and backports. Count Linux once as an upstream project while retaining separate subsystem targets. Multiple findings can share a submission; one finding can have multiple submission revisions. Avoid adding these counts together.

Keep technical validity separate from upstream disposition. Suggested validity values: unverified, verified, rejected, unresolved. Suggested upstream states: not submitted, pending, changes requested, accepted awaiting merge, merged, declined, withdrawn, superseded. Record reasons: a declined implementation does not automatically invalidate a defect, and a pending patch does not imply rejection.

Record a separate **validation basis** rather than treating a run's “confirmed” label as proof:

| Basis | What the evidence establishes |
|---|---|
| Source inspection only | A source-based argument; no execution establishes the claimed behavior |
| Modeled-harness execution | A reproducer executes a reimplementation or simplified model of target logic; transfer to the real implementation remains to be established |
| Actual-implementation execution | The identified project code executes and demonstrates the claimed behavior; record build, environment, test scope, and red/green evidence where available |
| Unknown | The surviving evidence does not establish which basis applies |

An actual-implementation unit test or a kernel running in a VM can qualify for the third category; neither proves all configurations are affected. A standalone C program that copies kernel logic belongs in the second category. Keep the expected-behavior argument and adjudication decision alongside the execution evidence. Historical “confirmed” counts must be reclassified before publication. Claude reports 122 findings in a preliminary survey, including substantial nonexecuted or modeled evidence; this is an inventory lead, not an audited total to cite.

Publish dated totals with denominators: projects reviewed; attempted/completed runs; distinct adjudicated and verified defects; distinct defects submitted; distinct defects with merged fixes. Preserve unsuccessful runs and rejected findings. Freeze a reporting cutoff for the paper so review delays cannot keep the manuscript open indefinitely.

### Initial leads, not a verified catalog

The repository README currently lists:

| Project / subsystem | Finding | Existing evidence pointer |
|---|---|---|
| Gson | Duplicate keys accepted when the first value is null | [PR #3006](https://github.com/google/gson/pull/3006) |
| Linux / virtio-pci | Configuration interrupt consumed but reported as unhandled | [Commit 93fa0945](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=93fa09455fb1a9624b73d42ac1f83771f4818e80) |
| Linux / zram | Unrecognized recompression `type=` silently accepted | [Commit 2f529e73](https://git.kernel.org/pub/scm/linux/kernel/git/torvalds/linux.git/commit/?id=2f529e73d72048743b6eaa241da6ac2bcb28099e) |

Source: [README, Merged upstream](../../README.md#merged-upstream), inspected 27 September 2026. Links have not been independently checked for this draft. The two additional submissions are identified in local evidence READMEs:

- [nvmet ANAGRPID](../../evidence/nvmet-anagrpid/README.md): group ID 128 clamped to 0; sent 10 September 2026; Message-ID `20260910154849.66095-1-astellman@stellman-greene.com`.
- [nvmet CRTO](../../evidence/nvmet-crto/README.md): property computed from CSTS instead of CAP; sent 10 September 2026; Message-ID `20260910180056.81257-1-astellman@stellman-greene.com`.

The local evidence READMEs describe both as awaiting review, but Andrew supplied a newer status update in this conversation on 27 September 2026:

| Submission | Latest user-reported state | Interpretation |
|---|---|---|
| nvmet CRTO / CAP | Reviewer requested a shorter commit explanation | Changes requested (commit-message wording); no explicit acceptance, rejection, or merge established |
| nvmet ANAGRPID | No response received | Pending; silence is not rejection |

The CRTO association follows the quoted register names, not the order Andrew called the submissions “first” and “second.” The supplied response reads:

> This is a very long explanation for a simple protocol fix. Just say
> something like "The NVME_CAP_TIMEOUT requires the value from the CAP
> register, not CSTS." Short and to the point.

Provenance: Andrew's pasted reply, received here on 27 September; the reply's original date, author, and Message-ID were not supplied. Preserve those fields as unknown until the reply is archived. No revised submission is recorded here. A dated upstream check remains outstanding.

Their folders include runbooks, reports, captures, and reviewer outputs; inventory and assess those artifacts rather than treating their existence as verification of every claim. Do not infer that “the three we already have” means three separate repositories; clarify the intended pilot targets after inventory.

## 2. Reconstruct the Gson case and review related work

Locate the original QPB run, exact source revision, gathered issue discussions, derived requirement, reproduction, proposed fix, and maintainer response. Establish which issue text was available to the agent and whether it expressed a broader expectation or explicitly disclosed this defect. Preserve the chain even if it weakens the original narrative.

### Historical evidence reported by Claude

Andrew supplied Claude's feedback on 27 September 2026. Claude corrected its initial inference from the current `repos/docs_gathered/gson/` corpus: the April run reportedly used a different corpus under `repos/gson-1.2.15/retrieved_documentation/github_issues/`. The current corpus cannot establish what that earlier run read.

Claude identifies the surviving source as `AI Chat History/Cowork export 2026-06-08-124832/Cowork-2026-04-03-Convert playbook to open-source skill.md`. That chat-history directory is not present at this checkout's root, so Astra has not independently inspected it. Retrieve the transcript from Claude's catalog evidence pointers or Andrew's archive, preserve a copy and hash, and distinguish command output, contemporaneous observations, and later assistant explanations within it.

Claims to verify against that transcript:

- A code-only `quality_baseline/` and documentation-enriched `quality/` comparison reportedly used GPT-5.4. Check prompts, model records, commit, tools, budgets, order, and context isolation before describing documentation as the sole changed variable. Claude points to lines 2932 and 3244 for model choice and the report of five additional requirements.
- Issues #676, #913, and #948 reportedly supported a class of null-handling contracts leading to REQ-033. Claude points to line 3993 for the session's explanation connecting those requirements to the duplicate-key defect. Audit that mechanism; the narrative is evidence of the agent's explanation, not by itself a causal demonstration.
- Claude reports 13 issue files but enumerates 12 issue numbers in its feedback. Recover the actual inventory rather than filling in the missing entry by inference.
- Issue #647 and PR #649 reportedly document related duplicate-key behavior and the introducing change. Verify their content and dates, and distinguish related prior reports from prior disclosure of the null bypass. A historical session's “unreported” conclusion is not an exhaustive novelty search.
- The original checkout, issue corpus, baseline artifacts, and `EXPERIMENT.md` are reportedly lost. If confirmed, mark evidence as transcript-preserved. Newly fetched issues form a dated reconstruction, not the original experimental corpus; a fresh run is a new experiment.

This comparison would be useful pilot evidence for documentation enrichment. It is **not the full proposed factorial comparison**: code-only versus enriched QPB does not independently vary conventional review versus QPB, nor isolate issue discussions from other added documentation. Recover it before designing new runs, then identify precisely which comparisons remain missing.

For each documentation-derived requirement, assess relevance, authority, version applicability, and whether the cited text supports the claimed behavior. Record conflicts and unsupported inferences. A verified defect does not establish that every requirement in the generated document is sound. For the pilot, audit all requirement links; use a predefined sampling procedure if the later corpus is too large.

Conduct a focused related-work search covering specification mining, requirements-based testing, issue-informed testing, LLM code review, and agentic quality assurance. Build a contribution comparison from the papers themselves. Until that review is complete, treat the claim that ordinary code reviews cannot use issue evidence as a hypothesis about workflow effectiveness, not a universal capability claim.

## 3. Freeze a small pilot protocol

Select tractable targets with reconstructable source and documentation snapshots. The pilot estimates feasibility, variance, and cost; it is not the final held-out evaluation. Record any method changes it motivates.

Use this proposed factorial design:

| | Official documentation | Official documentation + eligible issue discussions |
|---|---|---|
| Conventional AI-assisted review | A | B |
| QPB | C | D |

Within each documentation condition, both approaches get identical evidence and tool access. Source code and existing tests are also identical. The conventional review prompt should be competent, explicitly permit documentation use, and require actionable defects with evidence; it must not be deliberately weak. Freeze prompts before scored runs. If documentation gathering itself is evaluated, make that a separate end-to-end comparison with gathering cost and corpus provenance recorded.

Pin the target commit and remove later history, fixes, target-defect disclosures, prior QPB artifacts, sibling-run access, and answer-revealing network access from discovery environments. Preserve general issue discussions that establish expectations without disclosing the target defect. If a case cannot satisfy this separation, classify it as assisted verification or historical reconstruction rather than blind discovery. Isolation reduces experiment leakage but cannot establish absence from model training data.

Use the same exact model configuration in each paired comparison. If unavailable, rerun both arms on a documented replacement; do not combine an old QPB run and a new-model baseline as a controlled pair. Resolve Council scope before execution: existing benchmark guidance warns that the full pipeline mixes models. A single-model QPB variant is an explicitly modified treatment; a full-system comparison needs matched model access and transparent total resource accounting. Do not silently describe a phases-1–3 run as full QPB.

Predeclare repetition count, budget caps, stopping rules, eligibility rules, and handling of failed runs. As a provisional pilot, plan at least three independent runs per cell on a small target set, then use observed variance and cost to design the final study. Treat projects and defects as clustered observations, not every finding from every repetition as independent evidence. Record completion rates and failures alongside completed-run results; do not silently discard failures.

Judge both arms’ findings using the same criteria and verification effort. Remove method labels from adjudication where feasible, preserve rejected and unresolved claims, and identify who actually reviewed them. A model Council is not a substitute for independent human assessment. Tests must demonstrate the claimed behavior, with a separate source for why that behavior is defective.

## 4. Grow upstream evidence and run held-out evaluation

After inventory and pilot, select additional projects using explicit criteria: language/subsystem diversity, build feasibility, available behavioral evidence, active maintenance, and independence from QPB tuning targets. Record every attempted target and selection reason. Diversify the portfolio without treating likelihood of patch acceptance as evidence of defect validity.

Freeze QPB, prompts, corpora, and scoring rules before the held-out study. Keep development benchmarks and historical success cases in separate result groups. Collect genuinely prospective discoveries where feasible. If the method changes during evaluation, version it and start a new cohort rather than blend results.

Prepare verified patches with clear reproductions and source-based explanations of expected behavior. Andrew can submit them through each project's normal process. Track feedback and patch revisions while experiments continue. At the paper cutoff, report pending cases as pending and include submission age; do not wait for every maintainer decision.

## 5. Analyze and write

Report paired detection outcomes, shared and exclusive verified defects, precision with unresolved claims visible, known-defect recall with its denominator, run variability, resource use, and human effort. “Missed” means not found in specified runs and budgets, not impossible for that model to find. Upstream acceptance provides a separate practical outcome; it does not establish comparative superiority.

Draft around the Gson evidence chain, the reusable method, the comparison results, and limitations. Choose the final strength of the claim after examining held-out results. If evidence supports practical usefulness but not superiority, write an appropriately bounded experience report.

## First execution handoff: inventory only

Claude reports that inventory is in progress. Use this brief for remaining work or handoff, avoiding a duplicate catalog:

> Read `docs/research/PAPER_PROSPECTUS.md`, `docs/research/RESEARCH_PLAN.md`, and applicable repository instructions. Continue the QPB run and defect inventory in this checkout and archive locations supplied by Andrew. Produce linked project, run, finding, and submission records plus a concise gaps report under `docs/research/catalog/`. Record search scope, provenance, and unknown fields. Include `evidence/`, `repos/linux/_runs/`, README upstream links, and the April Gson transcript. Preserve the transcript and distinguish historical narrative from original tool output and reconstructed artifacts. Classify validation basis separately from validity and upstream status. Do not assume every configured benchmark ran or every reported finding was verified. Record model identity per role with its evidence source. Do not run new audits, modify historical artifacts, submit patches, or infer missing results. End with deduplicated totals by evidence level, gaps in the historical A/B, and evidence needed for pilot selection.

## Current state and next decisions

- Completed: initial prospectus and research plan; incorporated Claude's corrected feedback with provenance limits; located the two pending Linux submission records and local evidence folders.
- In progress, per Claude: catalog of available runs and findings.
- Next: review that catalog, inspect the April transcript, and audit the reported Gson A/B before commissioning additional experiments.
- Needed after catalog review: access to any uncopied transcript/archive sources and clarification of which three existing cases Andrew intends for the pilot. The two pending Linux patch identities are now known.
- Before experiments: settle review baseline, Council treatment, pilot targets, repetition count, and execution budget.
- Before submission: complete related-work assessment, upstream verification, held-out evaluation or explicitly bounded experience-report scope, and publication-specific formatting checks.
