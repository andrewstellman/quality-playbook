# Quality Playbook v1.6.1 — Design Document

*Status (2026-10-20): Features A and B (Track 2, precision) moved to `QPB_v1.6.2_Design.md` (Decision Record #4); this file now covers Features S and R. Original status (historical; the sections it describes are now in `QPB_v1.6.2_Design.md`): **canonical for Track 2**, created 2026-07-21 by splitting Track 2 out of `QPB_v1.6.0_Design.md`. Features A and B below are moved verbatim from that document, where they had been carried forward unchanged from the 2026-05-24 canonical scope. Nothing in this file is new design; it is the same scope under its own release.*

*Owner: Andrew Stellman. Companion: `QPB_v1.6.1_Implementation_Plan.md`.*

*2026-10-01: scope widened. Besides the precision features A and B, v1.6.1 now carries Feature S (§2a, subagent execution guarded by the parent's own gate run) and Feature R (§2b, the open-source review and submission process, including `submit-pr`). See Decision Record #3.*

*Depends on: v1.6.0 (Track 1) shipped. See §6 for the coupling.*

---

## 0. Decision Record

1. **(2026-07-21, Andrew) Track 2 splits out of v1.6.0 into its own release.** Rationale: Track 1 (Features C and D) has a complete acceptance story of its own — the coherence oracle, the validation oracle and F-1 — so it can be tested and delivered without waiting on the OpenFGA precision re-run. Shipping it separately gets the requirements work into use sooner. This **partially reverses Decision Record #2 in `QPB_v1.6.0_Design.md`** ("Full merge"), which pulled Features A/B and C/D into one release; the coherence rationale in that decision still holds for C and D, and only the A/B half is undone.

2. **⚠ OPEN — the version number is not settled.** This file is named `v1.6.1` provisionally, per the operator's initial framing. Andrew, 2026-07-21: *"i'm not sure -- we should separate things as much as possible."* The number is deliberately left open because nothing depends on it yet and a rename is free, while deciding it well needs evidence that does not exist yet.

   The case for a point release: the Implementation Plan specifies Feature A's schema extension as backward-compatible, additive and shape-tolerant, never rewriting an existing record's shape. If that holds in practice, a point release is defensible, and it avoids a third version renumber in three days (v1.7.0 became the security line and SPC moved to v1.8.0 on 2026-07-20).

   The case against: Feature B adds a new pipeline pass and four new verdict dispositions, which is feature-sized work rather than a fix.

   **Resolve this before Phase 5 starts, once the schema extension has been attempted and its true blast radius is known.** Renaming these two files and their cross-references is the entire cost of being wrong.

   **RESOLVED 2026-10-01 (Andrew): v1.6.1, with the scope widened (Decision Record #3).** Andrew: *"it's stupid to add a new version when we have work that's tested."*

3. **(2026-10-01, Andrew) v1.6.1 also carries two features from the 2026-09 open-source bug campaign:**
   - **Feature S:** subagent execution, on condition that the parent agent re-runs the quality gate itself (§2a).
   - **Feature R:** the open-source review and submission process, including a rewritten `submit-pr` (§2b).

   **State at decision time:**
   - **S:** the prose change and its evidence come from the icalendar cloud run (in progress).
   - **R:** the process has been used for real in the campaign; `submit-pr` is not built.
   - **A and B:** designed, not built.

   **Later additions on 2026-10-01:**
   - **Feature W:** claims and copywriting rules for QPB's own output (`references/claims_rules.md`).
   - **Feature R generates external script files** (`submit.sh`, `dup-search.sh`, `verify.sh`) for `gh` and other credentialed binaries, so the operator doesn't have to approve each call.

   **Who builds what:**
   - **S, W and R:** the cloud chat implements them per `QPB_v1.6.1_Cloud_Implementation_Spec.md`, and tests R on the icalendar run.

   **Ordering inside the release:**
   - S and R can land and be reviewed on the 1.6.1 branch first.
   - **Nothing is tagged until Features A and B pass their acceptance test (now `QPB_v1.6.2_Design.md` §4 criterion 1).** *(Superseded by Decision Record #4.)*

4. **(2026-10-20, Andrew) v1.6.1 ships without Features A and B; they move to v1.6.2.** This reverses the rule in Decision Record #3 that nothing is tagged until A and B pass. v1.6.1 is tagged with the features that are built and tested: S, R, W (claims rules), and the 1.6.1 G (gate verdict honesty: commits c69e1ec and dfc7bb0, `bin/tests/test_gate_verdict_honesty_v161.py`) and H (persona fixes: commit a51d949, `bin/tests/test_persona_fixes_v161.py`), two letters this record reuses from v1.6.0 for different features. G and H were added on 2026-10-02 during the feature merge and have no design section of their own; `CHANGELOG.md` [1.6.1] describes them. Features A and B, their acceptance test, the precision Council, the unbuilt `submit-pr`, and three open backlog items move to `QPB_v1.6.2_Design.md` and `QPB_v1.6.2_Implementation_Plan.md`. The release acceptance in `QPB_v1.6.1_Implementation_Plan.md` ("the test is real upstream merges", with Andrew deciding when enough have merged) is the basis for shipping now; on 2026-10-20 the README's Merged bugs leaderboard lists 11 merged fixes, 8 of them from the campaign that began in September (gson, zram and virtio predate it).

---

## 1. Precision, and Features A and B: moved to v1.6.2

Sections 1, 2 (Feature A) and 3 (Feature B), the precision success criteria, OD-5, the coupling notes and the Slice 3 Council plan moved to `QPB_v1.6.2_Design.md` on 2026-10-20 (Decision Record #4). This file keeps Features S and R.

---

## 2a. Feature S: subagent execution, guarded by the parent's own gate run

**Problem.** `SKILL.md` Mode A forbids running Phases 1–5 in subagents. The only automated per-phase pattern is labelled "AUTOMATION ONLY" (`agents/quality-playbook-claude.agent.md`). The rule exists because of the 2026-05-16 express failure: a delegated run hand-wrote a `quality-gate.log` reading PASS while the real gate failed, and the parent trusted it. The rule closes that hole by forbidding delegation altogether. That also rules out long runs that need context isolation, such as a full baseline plus four iterations in one session, or a cloud session.

**Design.**
- **New rule:** an agent may run phases in per-phase subagents, under the orchestrator pattern, as long as the parent agent itself does two things after every Phase 6:
  - (a) runs `quality_gate.py` itself and pastes the verdict lines verbatim in its own chat;
  - (b) compares that output with `quality/results/quality-gate.log`, and stops on any mismatch.

  The parent's own run is the witness, so a subagent cannot fabricate the verdict the operator sees.
- **Text changes:**
  - **`SKILL.md`, Mode A section:** replace the "DO NOT … spawn a sub-agent" bullet with the conditional rule above. Keep the Phase 6 fresh-context auditor exception.
  - **`agents/quality-playbook-claude.agent.md`:** replace the "AUTOMATION ONLY" header with the condition.
  - **`references/orchestrator_protocol.md`:** add the parent's gate re-run to the mandatory post-phase verification gate for Phase 6.
- **Nesting.** Subagents cannot spawn subagents. The Feature H persona pass and the Phase 6 auditor must therefore be spawned by the parent (the orchestrator), not from inside a phase subagent. State this explicitly.

**Verification.**
- **Pin test:** update the pin test for the Mode A/B asymmetries (`bin/tests/test_mode_a_b_parity_documented.py`).
- **New test:** a fixture where the subagent-written `quality-gate.log` says PASS and the real gate fails. The documented parent procedure must detect the mismatch. Where a check is prose, a doc check that the rule text is present in all three files.
- **Acceptance evidence:** the icalendar cloud run (`docs/research/HANDOFF-2026-10-01-cloud.md` §5). It records parent gate output next to the subagent log for the baseline and all four iterations, with zero mismatches, or every mismatch caught.

## 2b. Feature R: the open-source review and submission process

**Problem.** The 2026-09 campaign turned QPB findings into upstream fixes: merged in calibre, virtio-pci, Gson and zram, with more open. The process that did it exists only as one-off briefs in `/tmp`, `evidence/` and `docs/research/`. It isn't reproducible by an adopter, or by a fresh session.

**Design.**
- **Process documentation**, as an orientation doc plus templates (location to be decided: `ai_context/` or `docs/`):
  - selection: requirement-anchored bugs only; security-angle bugs set aside;
  - the confirmer brief;
  - the fixer brief: minimal fix, red / green / revert;
  - the review panel brief: 2 executors plus 13 roles, blind-first verdicts, synthesis, a focused re-review for code revisions;
  - the side-effect rule: a correct fix that would hurt existing users unexpectedly is dropped;
  - the per-project contribution checks: AI policy, CLA or DCO, issue-first, PR template;
  - `evidence/SUBMISSION-PROTOCOL.md`;
  - the `REVIEW.md` template;
  - the per-bug `STATUS.md` with `evidence/build_index.py`.
- **`submit-pr`.** This rewrites `QPB_v1.6.x_Bug_Report_PR_Automation_Proposal.md` around the protocol, and supersedes that proposal's batch features (`--all`, multi-bug PRs, its throughput rationale). It is one bug per invocation and draft-only. It does all the mechanical work:
  - fork and clone;
  - apply the patch;
  - verify red, green and revert;
  - run the touched suite;
  - push to the operator's fork;
  - `gh pr create --draft`, or issue-first for projects that require it.

  It writes or updates the bug's `REVIEW.md` Submission record. It never marks a PR ready and never posts comments.

**In the skill itself (Andrew, 2026-10-01).** The process moves into the skill, not just operator docs: *"we've proven that it works, so we can ask the skill to analyze the findings, suggest bugs for review, run the review, and then prepare the PRs and guide through them."* The natural home is a new Phase 7 improvement path, "Prepare upstream submissions", with a reference file (e.g. `references/upstream_submission.md`) that carries the briefs. The steps:

1. **Analyze and suggest.** Read `BUGS.md` and the manifest, and shortlist requirement-anchored, non-security bugs. Run the per-project contribution-policy check first. If the project bans AI contributions, stop and say so.
2. **Confirm.** One fresh confirmer subagent per shortlisted bug; it searches for duplicates in issues and open PRs.
3. **Operator picks.** The operator chooses which bugs go to review.
4. **Fix.** Minimal fix with red / green / revert.
5. **Review panel.**
   - The parent spawns 2 executors and 13 roles; that's Feature S's parent-spawns rule, because subagents can't nest.
   - Blind-first verdicts, then a synthesis.
   - The side-effect rule applies.
   - Any code revision gets a focused re-review.
6. **Prepare, one bug at a time.** Write the `REVIEW.md` explanation and the issue or PR text, check the upstream head, and hand `submit-pr` to the operator. **The skill never submits, never marks a PR ready, and never comments upstream.**
7. **Record.** After the operator submits, verify the submission and fill in the `REVIEW.md` Submission record and `STATUS.md`.

Guardrails stay in the skill text, not only in docs:

- one bug at a time;
- no schedules;
- draft only;
- a project's AI policy is checked first and wins;
- the disclosure line on every submission;
- security-angle findings go to a private-disclosure note, not a PR.

**Cost.** A full panel is 15 subagents per bug. The default is the full roster; a smaller roster is an explicit operator choice, recorded in `REVIEW.md`.

**Why it's in the skill.** The 2026-09 campaign showed the panel catching real defects before submission:
- a false claim in a PR text, refuted by five reviewers who ran it;
- a fix that made a URL parser throw on a colon, plus a new quadratic regex;
- two fixes with bad side effects (javalin out-of-memory, setuptools sdist bloat).

Those were caught *before* any maintainer saw them.

**Verification.** `submit-pr --dry-run` against an existing evidence folder (e.g. `cobra-complete-after-dashdash`) reproduces red / green / revert and the PR body. One real draft submission is made through it under the protocol.

## 4. Success criteria

Criteria 1 to 4 and 7 (precision) moved to `QPB_v1.6.2_Design.md` §4 on 2026-10-20. The two below are this release's.

5. **Feature S (added 2026-10-01):** the parent's own gate output matches every subagent-written gate log in the icalendar cloud run, or catches every mismatch. The rule text is present in `SKILL.md`, the Claude agent file and `orchestrator_protocol.md`. The pin test is updated.
6. **Feature R (added 2026-10-01):** the process doc and templates are in the tree. `submit-pr --dry-run` reproduces an existing evidence folder's red/green/revert and PR body. One real draft submission is made through it, with its `REVIEW.md` record filled.

Status at the release (2026-10-20): Feature R shipped as the in-skill path (Phase 7 path 5 with `upstream_scripts.py`); the standalone `submit-pr` and its `--dry-run` check in criterion 6 were not built and moved to v1.6.2. Criterion 5 (the icalendar witness evidence) was not re-checked for this record.

---

## 5. Open decisions

- **OD-5 (HIGH-precision acceptance bar):** moved to `QPB_v1.6.2_Design.md` §5 on 2026-10-20.
- **OD-VERSION — the release number. RESOLVED 2026-10-01: v1.6.1**, with Features S and R added (Decision Record #3).

---

## 6. Coupling to v1.6.0

Moved to `QPB_v1.6.2_Design.md` §6 on 2026-10-20; it describes how Features A and B build on v1.6.0.

---

## 7. Council review plan

1. The Slice 3 Council (NFR derivation and FP-audit) moved to `QPB_v1.6.2_Design.md` §7 on 2026-10-20.
2. **Pre-tag:** whole-surface umbrella Council, standard.

---

## 8. Provenance

Features S and R were added to this release on 2026-10-01 (Decision Record #3); the 1.6.1 G and H on 2026-10-02 (Decision Record #4). Features A and B, their success criteria and the OpenFGA failure analysis that motivated them were in this file from 2026-07-21 to 2026-10-20 and are now in `QPB_v1.6.2_Design.md`, whose §8 carries their provenance.

