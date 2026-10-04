# Comparing models through requirements analysis and defect discovery

**Working abstract · Andrew Stellman · 4 October 2026**

Choosing a language model for software quality work requires understanding what it finds, what it misses, and how consistently it performs. We propose an evaluation method using Quality Playbook, a structured quality-engineering workflow that derives behavioral requirements from project evidence and checks implementations against them. Models first identify requirements from identical code and documentation. We validate and combine equivalent requirements across runs, then measure each model’s coverage of that observed set. In a separate task, every model receives the same requirements, allowing violation detection to be evaluated separately from requirements discovery. Repeated runs across model configurations and projects measure requirement coverage, confirmed defect yield, precision, consistency, and cost. The method provides a basis for identifying when more expensive configurations deliver better results and when lower-cost configurations provide comparable performance. It can be applied to fresh project snapshots, supporting continued evaluation as models change while producing actionable defect reports for software maintainers.

## Study planning note

This abstract describes the intended full study, not the pilot's sample size. Results will be added after evaluation. The pilot is an independent feasibility exercise: its runs will not count in the full study's model-comparison tables. The full study will build and freeze its own requirement pool for each selected project snapshot.

Andrew is willing to fund Sol and Opus runs if the pilot works, extending the proposed Haiku/Luna and Sonnet/Terra roster to three configurations from each provider, and to add projects. The full roster, project count, and repetitions will be decided after the pilot. Exact versions and settings remain to be selected; corresponding tiers are not assumed equivalent across providers. Compare configurations within providers and by measured cost, without presuming a capability ordering. This potential expansion does not change the bounded [pilot protocol](MODEL_COMPARISON_PILOT_PROTOCOL.md). “Comparable performance” requires the declared margins and uncertainty analysis; a nonsignificant difference alone does not establish it.

Companion: [paper proposal](MODEL_COMPARISON_PAPER_PROPOSAL.md).
