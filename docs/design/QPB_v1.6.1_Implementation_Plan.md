# Quality Playbook v1.6.1 — Implementation Plan

*Companion to: `QPB_v1.6.1_Design.md`. Created 2026-07-21 by splitting Track 2 out of `QPB_v1.6.0_Implementation_Plan.md`; the phase content below is moved verbatim.*
*Version number resolved 2026-10-01: v1.6.1, with Features S and R added. See `QPB_v1.6.1_Design.md` Decision Record #3. S and R land first; nothing is tagged until Phases 5–7 (precision) pass.* *(That rule was superseded on 2026-10-20 by Design Decision Record #4; see the next line.)*
*2026-10-20: the precision phases (5 to 8) moved to `QPB_v1.6.2_Implementation_Plan.md`, and v1.6.1 is tagged without them (`QPB_v1.6.1_Design.md` Decision Record #4).*
*Phase numbering is deliberately continued from the v1.6.0 plan (5, 6, 7) rather than restarted at 1, so landed commits and cross-references stay valid.*

---

## Operating Principles

Carried unchanged from the v1.6.0 plan:

- **The design doc is the spec.** This plan sequences and gates; it does not pre-decompose. The implementing AI reads `QPB_v1.6.1_Design.md` end-to-end and decomposes during execution, per `ai_context/DEVELOPMENT_PROCESS.md` (no per-phase briefs).
- **The manifest stays the source of truth.** The FP-audit consumes the manifest, never the rendered document.
- **Independence is load-bearing for the FP-audit:** the audit sub-agent gets finding + cited source + relevant derived REQ + rubric — never the running skill, phase prompts, or writeup reasoning.
- **Source edits go through the diagnosis→Claude Code lane** per workspace CLAUDE.md; this plan and the design doc are the Cowork-editable planning surface.
- **Branch + ship discipline:** never push from a sandbox; verify every remote claim with `git ls-remote`; no wall-clock estimates anywhere.

New for this release:

- **v1.6.0 must be shipped before Phase 5 starts.** The tracks were independent by design, but the split makes the ordering concrete.
- **This release runs v1.6.0's fixture suite before merging** (the track-coupling rule, now one-directional).

---

## Phase 0 — Base confirmation (operator gate)

- v1.6.0 tagged, merged, and its branch closed out; `1.6.1` (or its resolved number) branched from it, base SHA recorded in the branch's first commit message.
- The OpenFGA run fixtures preserved read-only as the precision oracle inputs.
- **Resolve the version number** (`QPB_v1.6.1_Design.md` Decision Record #2) and rename these two documents if it changes.

---

# Features S and R (added 2026-10-01; land first, tag waits for Track 2 *(superseded 2026-10-20, Design Decision Record #4)*)

## Phase S: subagent execution guarded by the parent's gate run (Design §2a)

- **Prerequisite:** the icalendar cloud run's `CLOUD-LOG.md` "Evidence for the subagent-execution change" section, plus its proposal. This is the acceptance evidence. Read it before drafting the text.
- **Edits:** `SKILL.md` Mode A, `agents/quality-playbook-claude.agent.md` and `references/orchestrator_protocol.md`, through the Claude Code lane. Cowork proposes the diff.
- **Tests:** update the pin test; add the mismatch fixture (subagent log says PASS, real gate FAILs, and the parent procedure must catch it).
- **Gate:** worker self-Council (Protocol 1). This is a small surface; escalate to the nested external Council only if the self-Council splits.

## Phase R: the open-source review process and `submit-pr` (Design §2b)

- **R1, documentation and templates.**
  - Contents: the process doc; templates for each brief (selector, confirmer, fixer, panel, re-review, synthesis); the `REVIEW.md` template; the `STATUS.md` schema and `build_index.py`; the contribution-policy checklist; the side-effect rule.
  - Sources: the campaign's working copies (`docs/research/campaign-2026-09-29/confirm/`, `evidence/review-*/PANEL*.md`, `evidence/SUBMISSION-PROTOCOL.md`).
  - Placement: orientation docs (`ai_context/`), so they can be edited directly per the workspace convention once Andrew has seen the diff.
- **R2, `submit-pr`.** Rewrite the 2026-05-29 proposal as one bug per invocation, draft-only, protocol-aware, with no `--all` and no multi-bug PRs. Then build it (harness placement per that proposal's open question 1). Use the existing `evidence/SUBMIT/submit-*.sh` scripts as the reference behaviour.
- **R3, the in-skill path (added 2026-10-01; Design §2b "In the skill itself").**
  - Add the Phase 7 "Prepare upstream submissions" path and its reference file: analyze, then confirm, then operator pick, then fix, then panel, then prepare one bug at a time, then record.
  - This is a skill source change: Claude Code lane, nested Council.
  - R1's templates become the reference file's content; there's no separate copy.
- **Gate:** R2's `--dry-run` matches one existing evidence folder; one real draft submission made through it, with its `REVIEW.md` record filled. **R3:** one target taken end to end through the in-skill path, from `BUGS.md` to a prepared draft, with the operator submitting. The cloud icalendar run can be that target if R3 lands in time; otherwise the next new project.

## Release acceptance and cutover (Andrew, 2026-10-01)

- **The test is real upstream merges.** The 1.6.1 acceptance evidence is bugs found by QPB in the new open-source projects (icalendar first, from the cloud run), submitted under `evidence/SUBMISSION-PROTOCOL.md`, and **merged by their maintainers**. A merge is independent confirmation that the bug was real, the fix was right, and the process works. Track each in `evidence/<slug>/STATUS.md`; `build_index.py` gives the running count.
- **When enough have merged** (Andrew decides how many), the sequence is:
  1. merge the 1.6.1 branch into `main`. The precision gate stays: Features A and B are built and pass their acceptance test before the tag. Andrew, 2026-10-01: the cloud chat may do the precision build work; *(superseded 2026-10-20, Design Decision Record #4: v1.6.1 is tagged without A and B)*
  2. bring `ai_context/DEVELOPMENT_CONTEXT.md` up to date;
  3. switch fully to the cloud chat.
- **Cutover.** The Mac Cowork session and the cloud chat exchange follow-up prompts, relayed by Andrew, until the cloud chat's picture matches this session's. Cover campaign state, open PRs, held and decision items, and process rules. Verify by asking the cloud chat specific questions whose answers are on disk, not by trusting a summary.

---

# Track 2 — Precision: moved to v1.6.2

Phases 5 to 8 (Features A and B, the OpenFGA re-run, the precision Council and the precision release) moved to `QPB_v1.6.2_Implementation_Plan.md` on 2026-10-20 (`QPB_v1.6.1_Design.md` Decision Record #4).

## Release (v1.6.1)

- Version stamps from the single version source (`SKILL.md` frontmatter) and the tracked build-stamped files; `CHANGELOG.md` [1.6.1].
- Whole-surface umbrella Council; then the standard close-out sequence per `DEVELOPMENT_PROCESS.md` (Andrew tags; scripted publish gates; verify-before-claiming on every remote ref).

---

## Risks and mitigations

The Track 2 risks moved to `QPB_v1.6.2_Implementation_Plan.md` on 2026-10-20.

---

## Decisions recorded 2026-10-02 (Andrew)

- **SKILL.md size ceiling raised 20,000 → 21,000 BPE.** This puts all six upstream-submission guardrails inline in SKILL.md (Phase 7 path 5). *(As landed in dd35160, five of the six are inline; the side-effect rule stayed in `references/upstream_submission.md`.)* Andrew: "it's arbitrary."
- **The "35%" claim is unchanged for now, and gets re-measured after the open-source runs.** The SKILL.md description and both agent files say QPB "Finds the 35% of real defects that structural code review alone cannot catch".
  - **Where it comes from:** `benchmarks/EXPERIMENT.md`, commit `209c4bc` (2026-04-03). One repo (NSQ), 58 known defects, GPT-5.4; the no-playbook control missed 20 of 58 (34.5%).
  - **What was never measured:** "finds the 35%". The playbook was not run on those missed defects.
  - **What replaces it:** after the 1.6.1 open-source runs, replace the sentence with a claim measured on them, e.g. QPB-found bugs merged upstream and the control-arm hit rate from `docs/research/control-*`.

## Backlog — additional 1.6.1 candidates (not Track 2)

*Status of this backlog at the v1.6.1 release (2026-10-20): the `AGENTS.md` circular dependency is fixed in v1.6.1 (a missing `AGENTS.md` is a WARN); publish-on-tag is closed by `.github/workflows/publish.yml`, which publishes to PyPI and npm through OIDC when a GitHub Release is published (it does not run the `bin/publish_*.py` scripts, so their TestPyPI phase and tag-is-ancestor pre-flight are not part of it; the manual scripts remain for high-stakes releases); the other three items moved to `QPB_v1.6.2_Implementation_Plan.md`.*

- **End-of-Phase-2 must always disclose the agent (Feature H) review in full and present the opt-in human-interview offer.** *(Flagged 2026-07-26; moved to `QPB_v1.6.2_Implementation_Plan.md` on 2026-10-20, where the full text now lives.)*

- **Observable auditor sessions: stream a spawned `claude` CLI auditor's output so the orchestrator can monitor it live.** *(Flagged 2026-07-26; moved to `QPB_v1.6.2_Implementation_Plan.md` on 2026-10-20.)*

- **Push the model to write the correct NOT_RUN disposition marker the first time.** *(Flagged 2026-07-26; moved to `QPB_v1.6.2_Implementation_Plan.md` on 2026-10-20.)*

- **Resolve the `AGENTS.md` circular gate dependency so a genuinely-clean run can actually pass.** *(Flagged 2026-07-26 from the same run.)* The gate FAILs on `AGENTS.md missing (required at project root)`, but `AGENTS.md` is generated by the orchestrator **only after Phase 6 passes** — so any run that fails Phase 6 for any other reason *also* fails on missing `AGENTS.md`, compounding one root failure into two and making a would-be-clean run structurally unable to pass. Options to evaluate: don't gate `AGENTS.md` generation on Phase 6 success (generate it on the final pass attempt); OR have the gate suppress the `missing_artifact` FAIL for `AGENTS.md` when Phase 6 itself failed (don't double-count a cascade); OR emit a provisional `AGENTS.md`. Pick one so the artifact contract isn't self-blocking.

- **Automatic publish-on-tag (CI) for npm + PyPI.** *(Deferred from 1.6.0, 2026-07-26, operator decision.)* 1.6.0 ships via the manual `bin/publish_npm.py` / `bin/publish_pip.py` scripts (the designed path: pre-flights, two-phase test-PyPI→prod, `--publish` affirmation, verify-before-claiming). For 1.6.1, add a CI workflow that runs those same scripts automatically when a `v*` tag is pushed — reusing the existing pre-flight/verify logic, with npm + PyPI tokens as repo secrets. Keep the manual path available for high-stakes releases; auto-on-tag is for routine patches. Must not weaken the two-phase PyPI gate or the tag-is-ancestor pre-flight.
