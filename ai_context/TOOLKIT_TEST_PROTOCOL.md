# TOOLKIT.md Test Protocol

> Release-gate review for `TOOLKIT.md` and the orientation docs that reference it. Applies the same empirical-loop discipline that `IMPROVEMENT_LOOP.md` describes for the playbook itself, but to the documentation: surface problems through a panel of independent readers, fix them, re-test until convergence.

*Last updated: 2026-05-03 (v1.5.6 currency pass — adds `bin/install_skill.py` AI-agent-driven install path as the new default install mode in TOOLKIT.md; Persona 19 skill-as-code deep work moves forward to v1.5.7).*

## Purpose

Documentation, like code, can drift. Claims become stale, vocabulary diverges from what's actually in the codebase, and overclaims accumulate when no one is checking. This protocol verifies that TOOLKIT.md accurately communicates what the Quality Playbook does and does not do — through panels of LLM sub-agents reading the doc as different reader personas, with a structured rubric for evaluating their responses.

This is the docs analogue of `IMPROVEMENT_LOOP.md`'s benchmark-driven calibration. There, the Check step is benchmark recovery against ground truth. Here, the Check step is whether the doc supports correct answers across reader personas.

## When to run

Release gate, not CI. Run before each version bump when TOOLKIT.md or related orientation docs (IMPROVEMENT_LOOP.md, README.md, DEVELOPMENT_CONTEXT.md) have changed.

The cost is high — M models × N personas × actual reading + response time — and the doc does not change every commit. Running constantly without acting on findings degrades the signal.

## Test method

A panel of three LLM sub-agents (Task tool sub-agents in the orchestrating Cowork session, or three separate Cowork chats) is given **only TOOLKIT.md** as context — no other QPB source files, no SKILL.md, no benchmarks. Each sub-agent is given one persona prompt and produces a response. The orchestrator (top-level agent or human) evaluates each response against the rubric below.

The "TOOLKIT.md only" constraint is load-bearing: we are testing whether the doc stands alone for an LLM that does not have the source. If the doc is fine but the agent reads source files to answer, the test is invalid — pass it the doc, restrict tool access, no Bash, no Read on other files. Sub-agents can be given the option to read `IMPROVEMENT_LOOP.md` and `TOOLKIT_TEST_PROTOCOL.md` (this file) since these are part of the orientation-doc surface, but must not read SKILL.md, references/, bin/, or any benchmark output.

## Personas

These prompts simulate distinct reader populations. Each is designed to surface a specific failure mode if the doc has one. Add personas as new failure modes are discovered; do not remove personas without recording why.

### Persona 1 — The skeptical adversarial reviewer

> Read TOOLKIT.md as a hostile reviewer. What does the Quality Playbook actually guarantee? Where does the doc overclaim? Cite specific passages where the language outruns the evidence. Be specific about precision-vs-recall, process-vs-outcome, and any quantitative claims you cannot verify from the doc itself.

Tests: overclaiming, unsourced numerics, process-vs-outcome conflation.

### Persona 2 — The Rails adopter

> I'm the lead engineer on a Rails 7 monolith. We have ~80% scaffolded CRUD controllers and a small set of bespoke service modules handling payments and inventory. I'm thinking of running the Quality Playbook against our codebase. Should I? What part should I run it against, and what part should I skip?

Tests: scope-limit awareness; "where this adds little" surfacing.

### Persona 3 — The infrastructure adopter

> We're a Terraform shop with about 50 modules and a small Helm chart. Will the Quality Playbook find misconfigurations and policy violations in our infrastructure code?

Tests: scope-limit awareness; declarative-IaC exclusion.

### Persona 4 — The zero-bug interpreter

> We ran the Quality Playbook on our microservice and it found zero confirmed bugs. Does that mean the code is clean and we can ship?

Tests: process-vs-outcome separation; recall-vs-precision distinction; agent-quality requirement awareness.

### Persona 5 — The mechanical-extraction skeptic

> Walk me through how mechanical extraction proves the code is correct. The doc says it's an anti-hallucination measure — what does it actually prove and what does it not prove?

Tests: shape-vs-semantics distinction.

### Persona 6 — The model-quality challenger

> We've been running the Quality Playbook in Cursor with auto-mode selecting the model. We get clean artifacts, all the gates pass, but no real bugs are found. The codebase is known to have bugs. What's wrong?

Tests: model-requirement awareness; surface-area-as-theater risk articulation; pass-process / fail-recall identification.

### Persona 7 — The TDD-NOT_RUN edge case

> Our test runner doesn't work in our CI environment. The TDD logs show NOT_RUN. Are the bugs still verified? Can I trust the bug reports?

Tests: NOT_RUN-as-acknowledgment-not-verification distinction.

### Persona 8 — The methodology challenger

> How do you know the Quality Playbook works? What evidence supports the claim that it finds real bugs? What's your validation method?

Tests: empirical-loop awareness; benchmark recovery framing; honest "moving toward statistical control" framing rather than overclaiming. A v1.5.5+ correct answer also names where the trajectory is heading (v1.7.0 SPC machinery per `docs/design/QPB_v1.7.0_Design.md` — Shewhart control limits applied to both the improvement loop and QPB's own SDLC) rather than leaving the destination as a generic "multi-year horizon."

### Persona 9 — The vocabulary trap

> Tell me about the two axes of the playbook. What are they and how do they relate?

Tests: vocabulary correctness. The right answer involves the two axes of *improvement* (process compliance + outcome recall) per IMPROVEMENT_LOOP.md — NOT external syntheses (like "structured ↔ freeform" + "recall ↔ rigor") which describe design space, not improvement methodology. If a panelist invents axes that aren't in the doc, the doc has a vocabulary problem; if a panelist correctly distinguishes "improvement methodology axes" from "internal design tensions," the doc is doing its job.

### Persona 10 — The summary overclaim trap

> Summarize what the Quality Playbook guarantees in 100 words.

Tests: overclaim under length pressure. A correct summary names the process-vs-outcome split, names the agent-quality requirement, names the scope limits. A sloppy summary reaches for "finds bugs in any codebase."

### Persona 11 — The iteration-strategy explainer

> Explain the difference between the gap and unfiltered iteration strategies. Why are they separate? What kinds of bugs does each find?

Tests: canonical vocabulary preservation; doc fidelity to the four-strategy taxonomy.

### Persona 12 — The improvement-method asker

> Is the Quality Playbook itself quality-engineered? How is it improved between releases?

Tests: IMPROVEMENT_LOOP.md awareness; honest "moving toward statistical control" framing; benchmark-driven calibration vocabulary.

### Persona 13 — The categorization-asker (deferred to v1.6.0+)

> The bug report has tags like "standout," "confirmed," "probable," "candidate." What do these mean? Which should I prioritize?

Tests: categorization-tier vocabulary correctness; standout-as-earned framing.

(Activate Persona 13 after categorization tagging ships. Originally
scoped for v1.5.3 but deferred — v1.5.3's actual scope shifted to
the skill-as-code feature complete pass per the 2026-04-19 Haiku
demonstration. Re-deferred from v1.5.4 to v1.6.0+ in v1.5.4 Phase
3.6.8: v1.5.5 was scoped out of the v1.5.x lineage per CLAUDE.md
(v1.5.4 is the last v1.5.x release) and v1.5.4's actual scope
covered classification redesign + regression-replay machinery
rather than per-bug categorization. Tracked as v1.5.4 backlog item
B-13 in `Quality Playbook/Reviews/v1.5.4_backlog.md`. Until that
surface ships, panelists asked this question should answer "the
doc does not support this — categorization tagging is not yet
shipped; the operator picks standouts manually by reading the
writeups.")

### Persona 19 — The skill-as-code adopter (v1.5.3)

> I have a Claude Code skill (a SKILL.md plus references/) and I want to know if QPB can find defects IN THE SKILL ITSELF — places where the prose contradicts itself, places where the prose claims a code behavior the implementation doesn't deliver, places where archived runs show the skill underperforming its own promises. Will v1.5.3 do that?

Tests: awareness of the v1.5.3 skill-as-code surface — Phase 0
project-type classifier (Code / Skill / Hybrid); four-pass
generate-then-verify pipeline (Pass A naive coverage; Pass B
mechanical citation extraction; Pass C formal REQ production; Pass
D coverage audit); the three skill-divergence categories
(internal-prose / prose-to-code / execution); skill-project gate
enforcement (4 new gate checks); the curated REQUIREMENTS.md
bootstrap at `previous_runs/v1.5.3/REQUIREMENTS.md`. A correct
answer also surfaces the scope limits — execution divergence
needs archived runs to land any signal; the Council override path
exists for when the classifier is wrong; v1.5.3 also added the
OpenAI codex CLI as a third LLM backend (alongside `claude
--print` and `gh copilot --prompt`) so adopters who prefer the
codex CLI can drive the pipeline via `--runner codex` without
giving up access to the skill-as-code surface.

(Persona 19 deep work moves forward to v1.5.7. v1.5.6 shipped
Pattern 7 cycle execution and adopter-facing install work; the
skill-as-code adopter persona — what an adopter holding a
SKILL.md plus references/ actually does step-by-step to get a
useful run, beyond knowing the surface exists — is the next
major surface to deepen. v1.5.6 cluster A audit confirmed: the
adopter walkthrough did NOT surface skill-as-code-specific
gaps beyond what was already deferred. The adopter-facing
install + invocation work in v1.5.6 (`bin/install_skill.py`
turnkey installer, six-layout fallback resolution across
runtime + docs, layout-agnostic phase prompts, agents/ now
bundled in the install) benefits skill-as-code adopters the
same way it benefits code-targeting adopters; the depth gap
is the same v1.5.7 deferral noted at v1.5.3.)

### Persona 14 — The PR-submitter walkthrough

> I just finished a Quality Playbook run and got a `quality/BUGS.md` with 15 bugs. I want to submit some of them as upstream PRs. Walk me through the workflow: which bugs should I submit first, what evidence do I package with each PR, what do I do with the regression-test patches that QPB already generated, and what's an honest framing of "QPB found this" that a maintainer won't push back on?

Tests: PR-pipeline workflow guidance; standout-tier-as-submission-criterion clarity; honest-attribution framing for AI-assisted findings; regression-test patch portability awareness; how to talk about the playbook to upstream maintainers without overclaiming.

### Persona 17 — The defect-class consolidation reader

> Our Quality Playbook run produced nine BUGS.md entries that all describe the same defect pattern (in our case, "cached wrapper Z doesn't invalidate when mutation X happens"). Should I file nine PRs, or one consolidated PR? Does QPB have a notion of grouping or rolling up bugs that share a root cause?

Tests: recognition of root-cause vs. symptom; whether the doc distinguishes BUGS.md as "individual reports" vs. "a list of distinct defects"; awareness that maintainers prefer one consolidated PR for a defect family over nine individual ones; whether the iteration-strategy taxonomy (gap, unfiltered, parity, adversarial) admits the possibility that multiple iterations re-find the same underlying defect.

(Personas 14 and 17 added at the v1.5.2 release-gate, sourced from the 2026-04-25 cross-repo analysis. Persona 19 added at the v1.5.3 release-gate to test skill-as-code awareness. Personas 15, 16, and 18 from the v1.5.2 source remain queued for later release-gates: P15 deferred to v1.5.4+ (within-version variance language did not land in v1.5.3 — it requires the regression-replay machinery scheduled for v1.5.4); P16 and P18 for v1.6.x once replicate data accumulates and a HIGH-severity operational definition exists.)

### Persona 21 — The AI-agent installer (v1.5.6)

> I want my AI coding agent (Claude Code, Cursor, etc.) to install the Quality Playbook into my repo. Walk me through what the agent should do — what tool to invoke, what arguments to pass, and what to do if my repo doesn't have one of the recognized AI-tool markers.

Tests: awareness of the v1.5.6 `bin/install_skill.py` adopter install script as the new default mode for AI-agent-driven installs; the `--into <target>` argument shape; environment auto-detection via `.claude` / `.github` / `.cursor` / `.continue` markers; the canonical AGENTS.md install-procedure section as the step-by-step procedure; idempotent re-install behavior (operator-edit preservation as `<file>.operator-backup-<UTC-ts>` unless `--force`); cross-platform support (macOS/Linux/Windows). A correct answer also surfaces that manual file-copy install paths remain documented as alternatives in TOOLKIT.md's "Quick start" section for cases where the script can't run or the operator wants direct control, and that "code-only mode" (when `reference_docs/` is empty) is a runtime behavior of the playbook rather than an install-script flag.

### Persona 20 — The calibration-cycle orchestrator (v1.5.5)

> I want to drive a QPB calibration cycle on a benchmark target. The docs mention a `calibration_orchestrator.md` template, a per-cycle `quality/run_state.jsonl` event log, and post-condition checks at each phase boundary. Walk me through what these are, when they fire, and what an executing AI does when one fails.

Tests: awareness of the v1.5.5 orchestration substrate — the `agents/calibration_orchestrator.md` spawn-and-resume template; the per-cycle `run_state.jsonl` event log (event taxonomy in `references/run_state_schema.md`); the post-condition helpers in `bin/run_state_lib.py` (`validate_phase_artifacts` at each phase boundary; `validate_no_source_edits` wired into `bin/run_playbook.py:_finalize_iteration` as the Phase 5 source-edit guardrail); the four cycle visualization charts emitted by `bin/visualize_calibration.py` (per-bug × cycle heatmap, lever × benchmark heatmap, recall trajectory, Mermaid lever-interaction graph). A correct answer also notes the scope limit — the substrate is Mode-1-autonomous orchestration plumbing; it does not itself decide which lever to pull (that's the executing AI's diagnosis per `CALIBRATION_PROTOCOL.md` Steps 4-5).

## Rubric

For each persona response, evaluate on three dimensions:

1. **Correctness.** Does the response make true claims? Does it surface the right caveats? Does it preserve the canonical vocabulary?
2. **Completeness.** Does the response surface the relevant scope limits, edge cases, and prerequisites? Or does it answer at face value without naming what's missing?
3. **Doc-grounded.** Can each claim in the response be traced back to a specific passage in TOOLKIT.md (or IMPROVEMENT_LOOP.md / TOOLKIT_TEST_PROTOCOL.md when in scope)? If a panelist makes a true claim that the doc doesn't actually support, the doc is missing the support.

Each persona response gets one of four verdicts:

- **PASS** — correct, complete, doc-grounded.
- **DOC GAP** — response is correct but the doc doesn't actually support all the claims; doc needs to add the support.
- **DOC WRONG** — response surfaces a claim that conflicts with the doc, or the doc led the panelist to a wrong claim.
- **PANELIST DRIFT** — response goes off the doc into general LLM knowledge; doc is fine but the test setup needs tightening (was the panelist actually restricted to TOOLKIT.md?).

## Convergence criterion

The protocol has converged when, for one full round across all active personas, no new DOC GAP or DOC WRONG verdicts are produced — AND every DOC GAP / DOC WRONG verdict from previous rounds has been demonstrably fixed (re-run the persona prompts that surfaced them; the new responses give a PASS verdict).

Note: convergence is NOT "all panelists agree." Agreement optimizes for plausibility, not correctness. We care about whether the doc supports the right answers, not whether reviewers happen to land on the same answer. A round where all three panelists land on the same wrong answer is a failure, not a convergence.

## Roles and orchestration

The protocol is best run with a top-level agent orchestrating sub-agents:

1. The top-level agent fans out the persona prompts to N sub-agents (Task tool with restricted Read access, separate Cowork sessions, or three Council-of-Three terminals run via `gh copilot --model …`, `claude --print --model …`, or `codex exec --full-auto -m …`). v1.5.3+ supports all three CLIs as runner backends; the panelist-model choice is independent of which CLI fires the prompt.
2. Each sub-agent is given TOOLKIT.md (and optionally IMPROVEMENT_LOOP.md / this file) as context, plus its persona prompt.
3. Sub-agents return responses to the top-level agent.
4. The top-level agent applies the rubric, identifies DOC GAP / DOC WRONG findings, and proposes fixes.
5. The human (Andrew) reviews the proposed fixes, approves or rejects each.
6. The top-level agent applies approved fixes to the relevant orientation doc.
7. Re-run the protocol on the personas that produced findings; verify PASS.
8. Repeat until convergence.

For Council-of-Three execution, the canonical commands follow the workspace `AGENTS.md` Council protocol but with one substantive difference: the working directory should be the orientation-docs surface, not the QPB source repo, since panelists must not have access to source files. Suggested form:

```zsh
cd /Users/andrewstellman/Documents/QPB/ai_context && \
  gh copilot --model <MODEL> --prompt "$(cat ../Reviews/toolkit_test_persona_<N>.md)" \
  | tee "/Users/andrewstellman/Documents/AI-Driven Development/Quality Playbook/Reviews/toolkit_test_runs/<timestamp>/<persona-id>_<MODEL>.md"
```

The acceptance check from Council-of-Three Invocation still applies: each response file should show actual Reads against `TOOLKIT.md`, IMPROVEMENT_LOOP.md, or this file — not against SKILL.md, bin/, or .github/skills/. If a response file shows source-file Reads, the panelist was outside the test envelope and the run is invalid.

## Output artifacts

Each protocol run produces:

- `Quality Playbook/Reviews/toolkit_test_runs/<timestamp>/` directory under the workspace folder (kept out of QPB to avoid polluting the repo with review artifacts; same convention as the code-review responses).
- One `<persona-id>_<panelist-model>.md` file per response.
- One `_rubric.md` file with the verdicts and proposed fixes per persona.
- One `_summary.md` file describing whether the round converged, what was changed, and which personas need re-running.

When the protocol converges, archive the run as the release-gate evidence for that version bump. Cite the convergence run in the release notes.

## Test prompt files

Persona prompts should be saved as standalone files so they can be passed to `gh copilot --prompt "$(cat ...)"` without quoting issues. Suggested location:

`Quality Playbook/Reviews/toolkit_test_personas/persona_<N>_<short_name>.md`

Each file contains:

```markdown
# Toolkit Test — Persona <N>: <short name>

**Reviewers requested:** `gpt-5.4`, `gpt-5.3-codex`, `claude-sonnet-4.6` (each outer model spawns its own three-reviewer panel internally).

**Constraint:** Read only TOOLKIT.md, IMPROVEMENT_LOOP.md, and TOOLKIT_TEST_PROTOCOL.md. Do not Read or Bash into SKILL.md, bin/, .github/skills/, references/, or any benchmark output. If a question requires information beyond the orientation docs, say "the doc does not support this" rather than searching.

<persona prompt body>
```

The nested-panel header is required for the same reason as in code review: each outer model spawns its own three-reviewer panel internally, giving 9 perspectives per persona per round rather than 3. This is non-negotiable; flat-3 mode collapses inter-model diversity.

## First-run notes

The first invocation of this protocol on TOOLKIT.md after the v1.5.2 honesty pass should treat any DOC GAP / DOC WRONG findings as v1.5.2-blocking. After the first convergence, subsequent runs are release-gate (not blocking unless severity warrants).
