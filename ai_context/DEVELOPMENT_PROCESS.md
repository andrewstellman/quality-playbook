# QPB Development Process

*Last updated: 2026-05-06 (v1.5.6 cluster G refresh — notes that v1.5.6 was the first release implemented via the orchestrator/worker pattern documented in `AI_ORCHESTRATION_PATTERNS.md`, with Codex used for non-Anthropic-budget phases. v1.5.6 ALSO ran the first complete bootstrap-fixup → audit-then-backlog-cleanup sequence: 8 bootstrap-fixup clusters (instructions 020-027 closing 22 named bugs from the self-bootstrap audit) followed by audit-discovered backlog clusters A-D + F.1 (instructions 029-033 closing GitHub issue #1 + audit-flagged drift items + adopter install polish + cross-platform validation evidence + cycle-execution clarifications). The pattern — bootstrap-fixup, then audit-the-fixup, then close audit-surfaced items — validated end-to-end via the orchestrator/worker runner pattern). Single source of truth for how the Quality Playbook project is developed. Read at session start by any AI agent (Cowork, Claude Code, codex, etc.) orchestrating QPB development.*

This document covers **how QPB is developed** — the mechanical procedures, the rationale behind them, and the open directions for evolving the process itself. It is the parallel for QPB-the-project of what `IMPROVEMENT_LOOP.md` is for QPB-the-skill: the methodology doc.

Versioned historical artifacts (per-release retrospectives, Council syntheses, Bootstrap Findings, Scope Audits) live in `docs/process/QPB_v<X.Y.Z>_*.md` and are immutable once written. This doc is forward-facing and updated as the process evolves.

---

## 1. Mechanical procedures

### Release mechanics

- **Tag format:** `vX.Y.Z` — strict semver. Patch releases (`v1.5.4.1`) are reserved for corrective patches against a tagged release; feature work increments the minor (`v1.5.4` → `v1.6.0`). No date-based tags.
- **When to tag:** at the end of mechanical-release work (Phase 10 in the canonical Implementation Plan), after the Council umbrella review returns a Ship verdict and after every gating test has passed.
- **Who tags:** Andrew. Cowork and Claude Code never tag. The orchestrating AI prepares the mechanical-release commit (version stamps, README, CHANGELOG, schemas.md banner, orientation-doc updates) and STOPs at "ready to tag." Andrew tags + pushes + verifies origin.
- **Verify-before-claiming "shipped":** never declare a tag, push, or merge has landed without observing it directly. Required:
  - `git ls-remote origin <ref>` confirms the SHA on origin matches local
  - For commits: `git log origin/<branch> --oneline -5` shows the commit
  - When the bash sandbox can't authenticate to origin: explicitly say so and ask for confirmation rather than claiming success based on command issuance
  - This rule was born from the 2026-04-26 "v1.5.2 fully shipped" incident where a commit sat dangling locally for hours after a push that never reached origin
- **Merge to main:** at tag time. Feature branch (`1.5.4`) merges into main as part of the release commit chain; subsequent feature work branches off main again.

### Branch model

- One feature branch per minor version (`1.5.4`, `1.6.0`). Long-lived during the release's development arc.
- Branched from main; merged back at tag.
- Patch corrections branch off the tag (`v1.5.4.1` from `v1.5.4`), merge back to main and to any in-flight minor branch.

### Commit hygiene

- **Subject format:** `vX.Y.Z [Phase Y]: <scope>` for phased work; `vX.Y.Z: <scope>` for non-phased.
- **Coherent commit boundaries:** one logical change per commit. F-1..F-4 + Phase 4 + Phase 5 was three commits, not one — three logically distinct units (bootstrap findings, schema, apparatus). Phase 3.9.1 was one commit because it was two related two-line fixes for a single bug class.
- **Body content:** what landed, why, test counts before/after, mutation-verification results for regression-pin tests, Co-Authored-By line for the implementing agent.
- **Commit cadence within a work session:** at coherent boundaries, not "once at the end." A 5-phase work session typically lands 3-5 commits.
- **No commits during STOP-and-ask boundaries:** if the orchestrating AI hits a decision point that needs Andrew, it stops without committing. Andrew commits when ready or instructs the agent to continue and commit.

### Claude Code (or any implementing-AI) handoffs

- **Minimal-prompt pattern.** The handoff prompt is short and points at canonical docs:
  ```
  Read these end-to-end:
    - <canonical design doc>
    - <canonical implementation plan>
    - <relevant findings doc>
    - ~/Documents/AI-Driven Development/CLAUDE.md
  Implement what's in scope per the plan. Decompose as you execute.
  Report at end-of-session or at a STOP-and-ask boundary.
  ```
- **No per-phase briefs.** The canonical design and implementation-plan docs are the spec. Generating per-phase briefs is over-engineering — it pre-decomposes the work in ways that often diverge from what's actually in the canonical docs, creating drift and dropped requirements.
- **Don't pre-decompose for the implementing AI.** It runs the same model class as the orchestrating agent; it can decompose during execution. The orchestrator's job is scope + STOP boundaries + canonical-doc pointers, not work breakdown.
- **STOP-and-ask boundaries** are few and explicit. Typical: end of a phase that requires Andrew's diagnostic input (calibration cycle diagnoses); pre-tag mechanical commit; any encountered bug in QPB source mid-run that's outside the in-scope finding set.
- **Multi-session coordination via shared directory.** For coordinating two AI sessions through a shared directory (a chat-side orchestrator and a coding-side worker exchanging instruction and output files), see `AI_ORCHESTRATION_PATTERNS.md`. This is the file-level realization of the diagnosis-then-Claude-Code-lane rule and the default execution mode for v1.5.6+ work that spans multiple sessions. **v1.5.6 was the first release implemented end-to-end via this pattern**: a `v1.5.6_runner/` runner folder coordinated the chat-side orchestrator and the coding-side worker across the release's full development arc (Pattern 7 cycle execution + adopter-facing install script). When the Anthropic budget became constrained mid-release, Codex was used as the worker for the non-Anthropic-budget phases by switching the runner backend; the file-based instruction/output protocol made the handoff clean. See `AI_ORCHESTRATION_PATTERNS.md` for the pattern itself and section 9's worked example for the v1.5.5/v1.5.6 runner walkthroughs.

### Council protocol

QPB development uses Council-style review on substantial work. Three flavors, scaled to the work:

- **Focused single-panel review** — for small commits (e.g., Phase 3.9.1's two-line fix). The orchestrating AI examines the diff, mutation-tests regression pins, checks scope discipline, writes a brief verdict. Single perspective; quick.
- **Parallel-Agent reviewers** — for larger commits (e.g., Phase 5 apparatus, ~700 LOC). The orchestrating AI spawns 3 Agent reviewers with orthogonal lenses (typically: correctness, scope/discipline, architectural integrity). Each reviews independently; orchestrator synthesizes findings into a single verdict (Ship / Hold-with-fixes / Block).
- **Full nested 9-perspective Council** — for foundational/architectural changes or umbrella reviews before tag. Three outer models (`gpt-5.4`, `gpt-5.3-codex`, `claude-sonnet-4.6`) via `gh copilot --prompt`, each spawning its own three-reviewer panel internally. Protocol details in workspace CLAUDE.md (cd-into-repo discipline; nested-panel trigger header; suspicious-convergence flag).

**Iterate to clean review.** A first review surfacing P0 findings is normal and expected. Fix-up commit → focused re-review → if new findings, fix-up again. Multi-round (Round 1 → Round 2 → Round 3) is the norm, not a sign of trouble.

**Council on landed code.** Run reviews on commits that have landed in the working tree, not on briefs or proposals. Pre-implementation Council review (e.g., reviewing a brief before coding) is over-engineering — the implementing AI is competent enough that pre-review adds bureaucracy without catching what implementation review would catch anyway.

### Mutation-test discipline

For every regression-pin test (a test that exists specifically to prevent a known bug from re-emerging):

1. Revert the specific source line(s) the test pins
2. Run the test; confirm it fails with the expected error message
3. Restore via `git checkout <file>` or `git restore <file>`
4. Re-run; confirm the test passes again

Cite the mutation result in the commit message. Without mutation verification, "regression tests" don't actually pin anything — they could be tautological assertions that pass regardless of the source. Mutation testing is the proof that the test would catch reintroduction.

### Run-state instrumentation and the Phase 5 source-edit guardrail (v1.5.5+)

QPB runs (both adopter-facing and bootstrap/calibration) emit an append-only `quality/run_state.jsonl` event log. The format invariants and event taxonomy live in `references/run_state_schema.md`; the read/parse/write helpers ship at `bin/run_state_lib.py` (`read_events`, `last_in_progress_phase`, `validate_run_state_file`, `validate_phase_artifacts`, `validate_no_source_edits`, `append_event`, `write_progress_md`).

Two post-condition checks are wired in mechanically and matter for development discipline:

- **`validate_phase_artifacts`** fires at each phase boundary; a `phase_completed` event with a failing validation result indicates the phase produced an event but the artifact set was incomplete. Treat such states as malformed runs — diagnose the gap before progressing.
- **`validate_no_source_edits`** is wired into `bin/run_playbook.py:_finalize_iteration` as a mechanical Phase 5 source-edit guardrail. Any file modification outside `<target>/quality/` during finalization is recorded as a `validation_result` event with `status="fail"` and the run is tainted from a recall-comparison standpoint. **Implication for development sessions:** if you're hand-editing QPB source while a calibration cycle is running against the same checkout, the guardrail will fire on the cycle's Phase 5; use `git worktree add` to give each cycle its own checkout per `CALIBRATION_PROTOCOL.md` Pre-flight check #8.

The v1.5.5 substrate also includes the `agents/calibration_orchestrator.md` spawn-and-resume template (the Mode 1 autonomous-loop driver for cycles per `CALIBRATION_PROTOCOL.md`) and `bin/visualize_calibration.py` (four cycle charts: per-bug × cycle heatmap, lever × benchmark heatmap, recall trajectory, Mermaid lever-interaction graph). These are operational deliverables, not just docs — treat them as canonical when working on any cycle-related code.

### Calibrated reporting

When the orchestrating AI reports state to Andrew, each of these rules is about not over-claiming confidence in a specific dimension:

- **No wall-clock time estimates** (don't over-claim confidence about how long something will take). They've been consistently wildly wrong: 4m actual vs "30 minutes" estimated; ~2-3 hour actual vs "14-22 hours" estimated. Useless or actively misleading.
- **Don't claim "100% complete" without an audit** (don't over-claim confidence about scope completeness). When asked "is X complete?" — verify against canonical sources before answering yes. Cowork has a documented pattern of dropping things; never trust the orchestrator's recall as a completeness signal.
- **Don't conflate AI identities** (don't over-claim confidence about which agent did what). Codex desktop, Claude Code, and Cowork are distinct agents with distinct roles; codex desktop is the empirical-bootstrap agent, Claude Code is the development-session agent, Cowork is the orchestrating chat agent. Sloppy attribution causes confusion when reviewing artifacts later.

---

## 2. Rationale

Each rule in Section 1 emerged from a specific incident or recurring pattern. This section pairs the rule with what produced it, so anyone reading the rule later understands what bug the rule is meant to prevent — not just the rule itself, but the failure mode it's a response to.

### Verify-before-claiming "shipped"

**Origin: 2026-04-26 v1.5.2 push incident.**

Cowork told Andrew "v1.5.2 is fully shipped" after issuing a `git push` command, but the README commit (`bcdd08e`) had never actually reached origin. The bash sandbox couldn't authenticate to GitHub via HTTPS; the push command was issued but the orchestrating AI assumed success. The commit sat dangling locally for hours and almost got garbage-collected. Recovery required a multi-branch cherry-pick the next day.

**Failure mode:** confidence-calibration mistake — the orchestrator inferred "command issued = command succeeded" without verifying the resulting state.

**Generalization:** any external-state change requires direct observation, not inference from command issuance. Don't say "the harness is running" without `ps`; don't say "the test passed" without seeing test output; don't say "the file was created" without checking the path.

### Read canonical doc before authoring planning content

**Origin: 2026-04-26 v1.5.3 sequencing-edit misfire.**

Cowork wrote a v1.5.3 sequencing edit to `ai_context/IMPROVEMENT_LOOP.md` (commit `7d5e36c`) plus a C13.11 brief, a Round 9 Council prompt, and a Claude Code launch command — all without ever reading `docs/design/QPB_v1.5.3_Design.md` or `docs/design/QPB_v1.5.3_Implementation_Plan.md`. Those canonical docs documented v1.5.3's actual scope (Phase 0 project-type classifier + four-pass skill-derivation pipeline + skill-divergence taxonomy). The planning content Cowork wrote was approximately unrelated to that scope.

**Failure mode:** the orchestrator treated summary docs (IMPROVEMENT_LOOP.md, prior Council briefs) as if they were specifications. They aren't. Specifications live in `docs/design/<project>_v<X.Y.Z>_*.md`. Summaries describe specifications; they don't replace them.

**Diagnostic signature.** A planning doc that sequences work items with confident structural language but cites only summary-doc references ("per IMPROVEMENT_LOOP.md") rather than `docs/design/` line numbers is the smoking gun. Always cite the canonical doc by line/section reference; if you can't, you didn't read it.

### No per-phase briefs / don't pre-decompose for the implementing AI

**Origin: 2026-04-30 v1.5.x process retrospective.**

The v1.5.4 development arc accumulated per-phase briefs (Phase 3.6 Brief, Phase 3.7 Brief, Phase 3.8 Brief, etc.), each pre-decomposing the work for Claude Code in detail. The retrospective documented two consequences: (a) the briefs became surface area where requirements got dropped (B-18b deferred to "release coordination" framing instead of staying in v1.5.4 scope, until Andrew explicitly called it out); (b) the briefs duplicated content from canonical Implementation Plan + Findings docs, creating drift between the two sources.

**Failure mode:** the orchestrator mistook "showing my work" for "doing useful work." Pre-decomposition felt like rigor but was bureaucratic overhead that the implementing AI didn't need (it runs the same model class; it can decompose during execution) and that introduced errors the canonical docs didn't have.

**Generalization:** the orchestrator's job is scope + STOP boundaries + canonical-doc pointers. The implementing AI does the work breakdown.

### Iterate to clean review

**Origin: 2026-04-30 first and second Councils on v1.5.4 Phase 5 apparatus.**

Both Councils were intended as final pre-Phase-6 reviews. Both surfaced P0 findings the prior round didn't catch. First Council: P0-1 parser bug + P0-2 SHA256-substring-vs-actual-hash bug. Fix-up commit closed both. Second Council: P0-3 H2-heading parser gap + P0-4 `_QPB_SOURCE_PATHS` missing `phase_prompts/`. Same class of bugs (test-coverage shape gaps; architectural-update missing matching-guardrail update) — different specific instances.

**Failure mode:** "review found nothing" is rare on substantial work. Treating a single clean review as evidence the work is done risks missing the next class of similar bug.

**Generalization:** multi-round review is the norm on substantive commits, not a sign of trouble. Each round closes a class of finding; the next round may find the next class. The terminal condition is a clean review, not a single-pass review.

### Council on landed code

**Origin: 2026-04-30 retrospective + repeated experience that pre-implementation Council reviews of briefs add ceremony without catching what implementation review catches anyway.**

Briefs and proposals are abstract; landed code is concrete. Council reviewers reading a brief can flag scope concerns and catch architectural inconsistencies, but they can't catch the kinds of bugs that empirical inspection of the code finds (parser regex shape mismatches, missing guardrail updates, mutation-test gaps). Pre-implementation review duplicates the cheaper "Cowork sanity-checks the brief in chat" step without adding incremental value.

**Generalization:** Council protocol's strength is on landed code. Brief-time review is fine for sanity-checking framing, but the load-bearing review happens after the implementing AI has produced a diff that can be inspected.

### Mutation-test discipline

**Origin: pattern across multiple Council rounds where unit tests passed but real-input behavior failed.**

The v1.5.4 first Council found that the BUGS.md parser had unit tests using synthetic v1.5-era field shapes, but real archive files used different shapes (bold variants, no colon on heading) — synthetic fixtures masked the real-input failure. The fix-up added corpus-real-file tests that loaded BUGS.md directly from `repos/archive/`. The second Council found the same class of bug for H2 headings (`## BUG-NNN` vs `### BUG-NNN`) — same lesson, different specific shape.

A regression-pin test that's never been mutation-verified is a tautology risk: it might pass regardless of source state. Mutation testing (revert the source line; confirm test fails; restore) is the proof that the test would catch reintroduction.

**Generalization:** for any test that exists specifically to prevent a known bug, mutation-verify before declaring the regression "pinned." For corpus tests, fixtures should load from `repos/archive/` directly, not be hand-written from memory.

### Don't claim "100% complete" without an audit

**Origin: 2026-04-30 Remaining Work Brief audit.**

Andrew asked "are you sure this is 100% of the outstanding work?" after Cowork had drafted a v1.5.4 Remaining Work Brief. Initial impulse was to say yes. Audit (against the canonical Design + Implementation Plan + Bootstrap Findings + the v1.6.0 Design's carry-forward section) found 11 gaps including the entire ~22-item v1.6.x carry-forward backlog, several Phase 10 enumerations, F-1 architectural concerns, and the canonical-doc-refresh requirement.

**Failure mode:** completeness-claim without verification is a confident-sounding hallucination. Cowork has a documented pattern of dropping things; never trust the orchestrator's recall as a completeness signal.

**Generalization:** when asked "is X complete?" — verify against canonical sources before answering. The audit tool (parallel Agent reviewers comparing the brief to canonical docs) is fast; not running it is the failure mode.

### No wall-clock time estimates

**Origin: 2026-04-30 Andrew explicit pushback.**

Cowork's wall-clock estimates were repeatedly wildly wrong: a "30 minute" Phase 3.8 fix took 4m20s; a "14-22 hour" Phase 3.6 effort took ~2-3 hours.

**Failure mode:** the orchestrator was generating wall-clock estimates from training-data priors about human software-engineering effort, not from the actual work being done. The priors don't apply when the implementing AI does work in minutes that humans take hours for.

**Generalization:** stop generating time estimates for software work. They're useless when AIs do the work; misleading when humans plan around them.

### Don't conflate AI identities

**Origin: 2026-04-30 F-1 architectural-review identity confusion.**

In a Cowork response to Andrew, Cowork referred to "Codex" when the agent doing the development work was actually Claude Code (resuming a previous session). Codex was the earlier empirical-bootstrap-test agent, not the development-session agent. Andrew corrected: *"the response i gave you earlier was from when i restarted this in claude code resuming my previous session."*

**Failure mode:** the orchestrator was using "Codex" loosely as a synonym for "the implementing AI," which became inaccurate when the implementing AI changed mid-arc.

**Generalization:** distinct agents play distinct roles. **Cowork** is the orchestrating chat agent (this one). **Claude Code** is the development-session agent (committing source, running tests, structuring work via tasks). **codex desktop** is the empirical-bootstrap agent (operator pastes a one-line prompt to validate B-18b). Sloppy attribution causes confusion when reviewing artifacts later — a Council synthesis citing "codex's diagnosis" should not refer to Claude Code's diagnostic reasoning, and vice versa.

---

## 3. Plans / open directions

This section captures directions the development process *might* evolve in. Nothing here is committed work — these are framings for future conversation, not a plan-of-record.

### Bringing the development process under statistical control

QPB-the-skill has `IMPROVEMENT_LOOP.md` documenting the QC/QI methodology for *artifacts under audit*: regression replay measures bug-recall on benchmark targets, calibration cycles diagnose missed-bug classes, lever pulls move recall numbers, the calibration log accumulates evidence over time. That methodology is operational as of v1.5.4 (apparatus) + v1.5.5 (orchestration substrate: per-cycle event log, orchestrator template, post-condition checks, cycle visualization). The protocol that drives a cycle end-to-end lives in `ai_context/CALIBRATION_PROTOCOL.md`.

QPB-the-project (this document's subject — how the project itself is developed) has no parallel measurement apparatus. The development process produces qualitative findings (Council syntheses, retrospectives, scope audits) but no quantitative time series that could be tracked release-over-release and brought under statistical control under the SEI / Humphrey lineage. **The v1.7.0 design (`docs/design/QPB_v1.7.0_Design.md` + `QPB_v1.7.0_Implementation_Plan.md`) closes this gap directly:** it scopes Shewhart control limits applied to **both** the improvement loop (calibration cycles) and the SDLC for QPB itself. The questions in this section that ask "should the dev process be SPC-able at all?" are answered affirmatively in the v1.7.0 design — the trigger has fired.

Candidate metrics if such an apparatus were built:

- **Council-finding recall by round.** Number of P0 findings caught in Round 1 vs Round 2 vs Round N. If Round 2 reliably catches the next class of bug Round 1 missed, the review process is converging. If consecutive Councils each find new P0 classes (the v1.5.4 pattern: synthetic-fixture coverage gaps in two flavors), the review apparatus itself has unmet coverage.
- **Bug-class re-emergence rate.** When the same class of bug appears across consecutive review rounds, the underlying discipline has not yet been internalized. Tracks whether mutation-test discipline, corpus-fixture discipline, and source-unchanged-invariant discipline are actually being learned, or just being applied case-by-case.
- **Spec-vs-actual variance.** How often does what landed match what the canonical Implementation Plan said would land? Frequent drift suggests the plan is stale, the implementation is straying, or the orchestrator is over-engineering scope.
- **Mutation-test pass rate.** What fraction of regression-pin tests actually fail when their target line is reverted? Pins that don't fire are tautologies. A drop in this rate would indicate test-discipline regression.
- **Brief-to-canonical-doc divergence.** Count of references in any handoff brief that don't have matching canonical-doc citations. Tracks the over-engineering pattern — briefs growing detached from canonical scope.

### A possible parallel apparatus

If the metrics above were tracked formally, the apparatus shape might be:

- `metrics/development_process/<release_timestamp>/<event_type>.json` — parallel to `metrics/regression_replay/`. Per-release, per-event records (one per Council round, one per retrospective, one per fix-up commit chain).
- `bin/development_process_replay.py` — parallel to `bin/regression_replay.py`. Reads recorded events, computes metrics, emits a release-summary cell that validates against a `metrics/development_process/SCHEMA.md`.
- The calibration-cycle analog would be: when a dev-process metric regresses release-over-release, identify the dev-process lever to pull (changes to `DEVELOPMENT_PROCESS.md` itself; changes to Council protocol; changes to mutation-test discipline; etc.). The "lever" is a change to how the project is developed; the "recall delta" is the metric's improvement on subsequent releases.

### Open questions

These are real questions, not rhetorical:

- **Should the development process be SPC-able at all?** Some aspects are inherently human-judgment-dependent (whether a commit fixed the right thing; whether a Council finding is real or noise). Hard statistical-control assumptions may not apply across all dimensions. The QPB-the-skill apparatus works because the skill processes large numbers of artifacts (10+ benchmarks, multi-bug per benchmark). The development process processes fewer events per release; SPC needs sample sizes that may not exist.
- **Where's the line between useful measurement and meta-overhead?** SPC-ifying the development process risks adding bureaucracy that costs more than the insights are worth. The QC/QI loop for QPB-the-skill is justified by adopters' bug recall improving; the QC/QI loop for QPB-the-project would have to be justified by the development pace or quality improving in measurable ways. That justification is not yet in evidence.
- **What's the right granularity?** Per-release metrics give a sparse time series (a few releases per quarter). Per-Council-round metrics give a denser series but each round is shorter and less independent. Per-commit metrics give the densest series but most commits are too small to measure meaningfully.
- **Who validates the dev-process metrics?** For QPB-the-skill, recall is mechanically measured — it doesn't depend on operator judgment. For dev-process metrics like "is this Council finding real or noise?", the operator (Andrew) is necessarily in the loop. That makes the loop tighter (faster correction) but also more effortful (every measurement needs human review).
- **Does this duplicate retrospectives?** Versioned retrospectives in `docs/process/` already capture release-by-release lessons qualitatively. Whether quantitative dev-process metrics would add insight beyond what the retrospectives already capture is an open empirical question.

### Disposition

The natural trigger anticipated when this section was written — a release where retrospective lessons feel like they should be measurable but aren't — has fired. The v1.7.0 design (`docs/design/QPB_v1.7.0_Design.md` + `QPB_v1.7.0_Implementation_Plan.md`) scopes the SPC machinery for both the improvement loop and QPB-the-project's SDLC. The questions in this section remain useful as the design context that the v1.7.0 plan answers; treat this section as the historical framing rather than open work.

---

## 4. Cross-references

Docs that inform or are informed by the development process. This is not a navigation guide — for that, see `README.md` and `AGENTS.md`. These are the touchpoints specifically relevant when reasoning about *how QPB is developed*.

### Parallel methodology

- **`ai_context/IMPROVEMENT_LOOP.md`** — the QC/QI methodology for the running skill (QPB-applied-to-skills-and-code-projects). This document is the parallel for QPB-the-project (QPB-applied-to-its-own-development). They cover different objects (skill artifacts vs project process) but the same shape: rules paired with rationale, plus open directions for measurement maturity.

### Versioned artifacts

- **`docs/design/QPB_v<X.Y.Z>_Design.md`** — per-release design specifications. The "what we're building and why" for each release. Read by the orchestrator before authoring any planning content per the read-canonical-doc rule.
- **`docs/design/QPB_v<X.Y.Z>_Implementation_Plan.md`** — per-release work-item enumeration. The "what to build and in what order" for each release. Same read-first rule applies.
- **`docs/process/QPB_v<X.Y.Z>_*.md`** — per-release historical process artifacts (retrospectives, Council syntheses, Bootstrap Findings, Scope Audits). Immutable once written; serve as the audit input that a CMMI-level-3+ review would consume. Naming pattern parallels `docs/design/`.

### Workspace context

- **`~/Documents/AI-Driven Development/CLAUDE.md`** — workspace-level conventions (cross-project navigation, source-edit lanes, verify-before-claiming, Council protocol mechanics including `gh copilot` invocation, the universal Cowork communication style for any conversation in the workspace). When a working convention applies to QPB specifically, the canonical version lives in this `DEVELOPMENT_PROCESS.md` file; the workspace CLAUDE.md may replicate it for orientation but is not the source of truth.

### Peer orientation docs (in `ai_context/`)

- **`TOOLKIT.md`** — adopter-facing toolkit-installation and bare-invocation guide.
- **`TOOLKIT_TEST_PROTOCOL.md`** — release-gate review protocol for orientation docs (the orientation-doc analog of Council-of-Three).
- **`DEVELOPMENT_CONTEXT.md`** — context-gathering recipes and "baseline runs" guidance for development sessions. Operational counterpart to this `DEVELOPMENT_PROCESS.md` (which is the durable conventions doc; `DEVELOPMENT_CONTEXT.md` is the per-session-context doc).
- **`CALIBRATION_PROTOCOL.md`** — the 12-step Mode 1 (autonomous) / Mode 2 (operator-driven) protocol for driving a QPB calibration cycle on a benchmark target. Read when working on any lever-pull release.
- **`IMPROVEMENT_LOOP.md`** — methodology context for the calibration cycles: WHY the lever inventory exists and WHAT each lever controls.
- **`BENCHMARK_PROTOCOL.md`** — clean-folder run protocol for contamination-free benchmarks; v1.5.5+ also documents the `quality/run_state.jsonl` event format and cross-validation rules.

### Top-level orientation

- **`README.md`** — adopter-facing top-level orientation. The first thing any new reader sees.
- **`AGENTS.md`** — operator-facing guide, orchestrator-generated post-Phase 6 in benchmark target repos. NOT the same audience as this development-process doc; AGENTS.md tells an adopter how to operate the skill, this doc tells AI agents how the project itself is developed.
