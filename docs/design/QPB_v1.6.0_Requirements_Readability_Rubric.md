# QPB v1.6.0 — Requirements Quality Rubric (Wiegers)

*Specified 2026-07-20. Canonical. This rubric defines the **judgment half** of the Slice 1 acceptance oracle (Implementation Plan, Phase 2) and supplies the shared vocabulary for Phase 4's `quality/REQUIREMENTS_REVIEW.md` defect log and Feature D's validation interview. One rubric, three consumers — do not derive a second vocabulary.*

## Why a rubric and not a verdict

The mechanical render contract (Feature C, Design §5.3) decides structural questions: ID sequence, title length, required sections, absence of derivation internals. It cannot decide whether a requirement set is *good*. That judgment is unmechanizable and needs a reader.

A plain Council verdict — SHIP or FIX — is insufficient for the job, because the acceptance fixtures are golden files. A verdict cannot detect **drift**: "still ships" is equally true of a document that scored 4.6 last quarter and 3.4 today. Scored dimensions produce a comparable number across runs, which a pass/fail cannot.

The dimensions are **Karl Wiegers' requirements quality attributes**, the standard set in requirements engineering, rather than invented criteria. QPB already commits to this vocabulary: Design §6 and the Implementation Plan both specify the interview defect log as organized "by Wiegers attribute."

## Ground truth — documentation, never implementation

**Judge requirements against the project's documentation and stated intent. Never against its code.**

This is load-bearing, not stylistic. QPB exists to validate code against requirements. If requirements are judged by whether they match the code, the reasoning is circular: every bug becomes a requirement, coverage is perfect by construction, and the tool finds nothing. A requirement describing what the code *does* rather than what it *should do* is a defect, not a match.

- **Legitimate ground truth:** README, design docs, API documentation, protocol specifications, changelogs, published contracts, documented conventions.
- **Permitted use of source:** checking whether a requirement is *stated in a verifiable way*.
- **Prohibited use of source:** deciding whether a requirement is *correct*.

## The dimensions

Score each document on each dimension, **1–5**, with a one-sentence justification and at least one `REQ-NNN` citation or direct quotation per cell.

| Score | Meaning |
|---|---|
| **5** | No instances found after deliberate search |
| **4** | Isolated minor instances; no reader would be misled |
| **3** | Several instances; a reader would need to ask a clarifying question |
| **2** | Frequent instances; the document misleads on a material point |
| **1** | Pervasive; the document cannot be relied on for this dimension |

1. **Complete** — Does the requirement set cover the behavior described in the project's documentation? Name documented capabilities no requirement addresses. Highest-value dimension; weight effort here.
2. **Consistent** — Do any two requirements contradict? Is terminology stable (one concept never named two ways; one name never covering two concepts)?
3. **Unambiguous** — Could two competent engineers implement different things from the same requirement? Flag vague quantifiers ("fast", "appropriate", "as needed", "properly") and undefined terms.
4. **Verifiable** — Could a test be written that objectively passes or fails? A requirement nobody can check is not a requirement. Downstream QPB phases write real tests from these, so failures here degrade everything after Phase 2.
5. **Well-organized** — Do sections group coherently, does the order aid comprehension, does it read as one specification rather than an assembled list?
6. **Honest about gaps** — Does the Overview's F-1 coverage-and-gaps statement accurately describe what was and was not covered? An inaccurate gaps statement is **worse than a missing one** because it manufactures false confidence. Score 1 if it claims something is out of scope that is demonstrably in scope.

*Dimension 6 is not a classical Wiegers attribute. It is included because the instruction-001 self-Council found virtio's document asserting the per-device drivers were "outside the checkout entirely" when eight were present in `drivers/virtio/` and uncovered by any REQ.*

## Reviewer composition

**Cross-family reviewers are mandatory.** `REQUIREMENTS.md` is agent-authored; a judge drawn from the generating model's family inflates scores through documented self-enhancement bias. Use the external three-terminal Council (`gpt-5.4`, `gpt-5.3-codex`, `claude-sonnet-4.6`) per `ai_context/DEVELOPMENT_PROCESS.md` — never worker sub-agents grading worker output.

Each outer model spawns three inner panelists on differentiated seats, scoring independently before comparison:

- **The operator** — owns the codebase; checks the spec says what the system is supposed to do.
- **The newcomer** — has never seen the codebase; must understand the system from this document alone.
- **The test author** — must write verification tests from these requirements and nothing else; weights *verifiable* heaviest.

Disagreement between seats is signal. Do not average it away.

## Thresholds

- Any dimension scoring **≤2** on any document forces at least SHIP-WITH-FIXES.
- Phase 2 gate: Ship with no dimension ≤2 on any of chi / express / virtio.
- Scores are recorded per run so drift is visible across releases. Before scores can gate anything beyond the ≤2 rule, they need a variance baseline — LLM judges are nondeterministic, and chasing judge noise instead of real regressions is the predictable failure mode.

## Provenance

Wiegers attributes are the field standard. The scoring-and-anchoring approach follows established LLM-as-a-judge practice (Prometheus, ICLR 2024 — rubric-scored evaluation reaching Pearson 0.897 with human raters; G-Eval), including its documented cautions: behavioral rather than evaluative level descriptions, no shared model family between generator and judge, one rubric per use case, and human calibration before scores are trusted at scale.

## Spec and implementation, not duplication

This file is the **specification**. A Council prompt that embeds the rubric — for Slice 1, `~/Documents/AI-Driven Development/Quality Playbook/Reviews/QPB_v1.6.0_Slice1_Readability_Council_Prompt.md` — is an **implementation** of it. The two stating the same thing is not redundancy to be eliminated; it is the same relationship this entire tool is built on, where requirements and code independently express one intent and disagreement between them is a findable defect.

So prompts **should** embed the rubric rather than cite this file. An embedded prompt is self-contained: the run reproduces from a single artifact, and no reviewer can silently read a different version or skip the reference. Citation would trade a checkable divergence for an invisible one.

The control is the same one QPB applies everywhere else: **verify the implementation against the spec.** When a prompt is written or revised, check its embedded rubric against this file — dimensions, anchors, ground-truth rule, thresholds — and treat any difference as either a spec change to land here or a prompt defect to fix there. Never as an acceptable drift.

*(Distinct from the manifest→render relationship in Feature C, which is genuinely a derived view: `requirements_manifest.json` is the single source of truth and `REQUIREMENTS.md` is a contract-checked presentation of it, not a second source. Both relationships exist in this release and they take different controls — derivation is enforced mechanically, spec-versus-implementation is verified by review.)*
