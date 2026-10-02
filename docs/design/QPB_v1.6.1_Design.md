# Quality Playbook v1.6.1 — Design Document: The Precision Release

*Status: **canonical for Track 2**, created 2026-07-21 by splitting Track 2 out of `QPB_v1.6.0_Design.md`. Features A and B below are moved verbatim from that document, where they had been carried forward unchanged from the 2026-05-24 canonical scope. Nothing in this file is new design; it is the same scope under its own release.*

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
   - **Nothing is tagged until Features A and B pass their acceptance test (§4 criterion 1).**

---

## 1. Precision: findings untethered from requirements (the OpenFGA failure)

The 2026-05-23 OpenFGA Mode-A dogfood (v1.5.7, real 548-file Go repo, doc-enriched) reported 3 HIGH "security" findings with **0/3 precision**, unanimously confirmed by the 090i Council: BUG-003 (missed the `tryCache` guard — unreachable), BUG-006 (the filter *is* applied upstream; cited CVE not even in version range), BUG-009 (verbatim advisory restatement, no located code defect). Root cause: QPB derives *functional* REQs rigorously but has **no equivalent rigor for non-functional requirements**, so gathered advisories pattern-match straight into "bugs" with no derived, testable security REQ to check against. v1.5.7 shipped the 090j same-agent triage band-aid; the real fix is requirements-level. *(This is the 2026-05-24 analysis, carried forward unchanged; full detail in this file's git history.)*

*(Section moved from `QPB_v1.6.0_Design.md` §1.1 on 2026-07-21. It is the motivating defect for this release, not for v1.6.0.)*

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

## 2. Feature A — First-class NFR discovery

*Carried forward from the 2026-05-24 canonical scope; substance unchanged, restated compactly. Full original text in git history.*

**Problem.** No derived, testable non-functional requirements → advisory-primed false positives (§1.1).

**Design.**
- Phase 1/2 derivation (and the skill-derivation passes) derive NFRs as first-class REQ records: same fields plus `nfr_class` (taxonomy per Wiegers / ISO-25010: security, performance/efficiency, reliability, usability, portability, maintainability, integration/interoperability) and **mandatory** `acceptance_criterion` + `verification_method`. An NFR without an acceptance criterion is invalid (the "aspirational NFR" anti-pattern).
- **Grounding rule:** an NFR finding is confirmable only if it traces to a derived NFR and demonstrates a violation of that NFR's acceptance criterion in the audited tree. Advisory/CVE with no derived-NFR violation → `KNOWN-ISSUE`, not `BUG`.
- Slice split: core classes (security, reliability, performance) first; remaining classes in the breadth slice.
- Rendering: NFR REQs render into the Feature C document architecture as their own sections, grouped by `nfr_class`, after the functional sections (§5.2).

**Verification.** Gate FAILs an NFR REQ lacking acceptance criterion / verification method (mutation-bitten both ways). Derivation fixture: the OpenFGA contextual-tuple restriction yields a derived `REQ-SEC` with an acceptance criterion. Acceptance oracle shared with Feature B (§4).

**Dependencies.** `schemas.md` REQ record extension; categorization-tier state must be confirmed in code before extending (the Lever-6 withdraw/return history — carried open question). Backlog B-13 (per-bug categorization tagging, v1.5.4 backlog) is partially subsumed by `nfr_class` — reconcile during implementation, per the 2026-05-24 doc's note.

**Builds on v1.6.0 Feature G (dump-and-go ingest, added 2026-07-22).** An NFR's mandatory `acceptance_criterion` is only as authoritative as the spec it is grounded in — a security NFR derived from a Tier-1 spec (e.g. an RFC's MUST) is a real requirement; one inferred from code is Tier 3 and weaker evidence for the grounding rule. Feature G's AI-classified tiering means a security spec dumped into the docs folder is recognized as citable without the operator pre-sorting it, so more NFRs derive at Tier 1/2 with byte-verified acceptance criteria. Feature A should assume Feature G's classification is available; the "advisory is not a contract" rule Feature G enforces is the *same* rule that keeps a CVE advisory from becoming a derived NFR here.

## 3. Feature B — Fresh-context, requirements-grounded false-positive audit

*Carried forward; substance unchanged, restated compactly.*

**Problem.** Findings confirmed by the producing context inherit its confirmation bias and advisory priming (§1.1); the failure mode is class-agnostic, not security-specific.

**Reuses v1.6.0 Feature H's infrastructure (added 2026-07-22).** Feature B and v1.6.0's Feature H are the *same architecture pointed at different targets*: a fresh-context sub-agent, given a **target-specific** constrained input set and a compact rubric, producing graded verdicts with honest provenance and multi-seat independence — Feature H validates *requirements against intent* (input: gathered docs + rendered spec + rubric), Feature B audits *findings against requirements* (input: finding + cited source + REQ + rubric — the *more restrictive* isolation). v1.6.0 builds the harness **target-agnostic** (a named Feature-H acceptance item): context provisioning is a per-target parameter, while the orchestration, the independence/isolation discipline, and the `agent-validation` provenance shape are shared. Feature B is therefore mostly **a new rubric + target binding**, not new plumbing — it inherits the orchestration and independence machinery and supplies the FP-audit rubric and the findings target.

**The one real difference: H remediates, B judges.** *(Clarified 2026-07-22.)* Feature H is a **requirements remediator** — it *fixes* the spec (grounded add/correct/drop, auto-applied with an operator-visible review summary) and produces a better document, not a verdict. It does not gate, and it has no accuracy-calibration project, because there is nothing to gate on. Feature B is a **judge**: its verdict (CONFIRMED / DEMOTED / RECLASSIFIED) changes a finding's disposition, so B *does* need to be right in a measurable way. B therefore supplies its **own** accuracy ground truth — the OpenFGA labeled fixture set (§4), where the correct disposition of each bug is known — and that is B-local, not something inherited from H. What B inherits from H is the **shared harness**: fresh-context sub-agent orchestration, the input-isolation discipline (B's is stricter — finding + source + REQ + rubric only), and the `agent-validation` provenance shape. **Implementation note:** confirm which parts of H's harness shipped before building B; the orchestration + isolation + provenance are inheritable, the correctness-measurement is B's own (against its labeled fixtures).

**Design.**
- A fresh-context sub-agent pass over each *confirmed* finding, post Phase 3/4 triage, at/before Phase 5 finalization — the productionized 090i Council shape. **Independence is load-bearing:** the auditor receives only finding + cited source + relevant derived REQ + compact rubric; never the running skill, phase prompts, or writeup reasoning.
- Rubric (precision core, Slice 3): reachability (BUG-003 class), applicability incl. CVE version-range (BUG-006 class), source-of-truth (BUG-009 class), requirements-traceability. The breadth slice (Slice 4) adds design-intent, compensation, severity-justification. Security is the highest-scrutiny tier, not a separate detector.
- Verdicts: CONFIRMED / DEMOTED / RECLASSIFIED-KNOWN-ISSUE / UNCERTAIN, with reasoning; audit transcript preserved as a run artifact; precision metrics updated. New dispositions get plain-English narration via the shipped 090v verdict-explanation framework (proposal item E3).
- The `confirmed-open (integration-harness-required)` disposition (pulled 090r) becomes admissible **only** when the FP-audit independently CONFIRMs — carried unchanged.
- **Cross-link to Feature C (new):** the FP-audit's requirements-traceability check consumes the *manifest*, not the rendered document — so Feature C's render changes cannot perturb it. Where the audit demotes/reclassifies, Feature C's traceability appendix (§5.2) reflects the final disposition.

**Verification.** OpenFGA fixture set: BUG-003 → DEMOTED, BUG-006 → DEMOTED/RECLASSIFIED, BUG-009 → RECLASSIFIED-KNOWN-ISSUE, BUG-001/002/004 → CONFIRMED. One non-security fixture demoted, proving generality. Independence verified as a gate item (a writeup-fed audit is a fabrication tell).

**Dependencies.** Feature A (traceability check needs derived NFRs). Runner/model choice and cost scope are carried open questions.

---

## 4. Success criteria

Criteria 2 and 4 moved here from `QPB_v1.6.0_Design.md` §10, renumbered; criterion 3 is this release's own.

1. **Precision oracle (carried):** OpenFGA re-run — 003/006/009 demoted/reclassified, 001/002/004 surface, advisory-only findings classified KNOWN-ISSUE. *(Corrected 2026-07-20 — this previously read "HIGH precision ≥ the bar (OD-5)," which cannot be evaluated: OD-5's own rider states the ≥90% figure is a reporting/policy bar, not measurable at fixture sample size, where one false positive in six findings is 17%. The named-bug behavior above **is** the executable test.)*
2. NFR REQs derived with acceptance criteria + verification methods; gate rejects aspirational NFRs.
3. **No regression in v1.6.0's surface:** Track 1's fixture suite (coherence + validation oracles) runs green after Track 2 merges, per the track-coupling rule carried in §6.
4. No recall collapse anywhere: bin/tests + gate green dual-env; QPB self-audit REQ coverage not reduced.
5. **Feature S (added 2026-10-01):** the parent's own gate output matches every subagent-written gate log in the icalendar cloud run, or catches every mismatch. The rule text is present in `SKILL.md`, the Claude agent file and `orchestrator_protocol.md`. The pin test is updated.
6. **Feature R (added 2026-10-01):** the process doc and templates are in the tree. `submit-pr --dry-run` reproduces an existing evidence folder's red/green/revert and PR body. One real draft submission is made through it, with its `REVIEW.md` record filled.
7. **Additional precision oracle (proposed 2026-10-01):** use the campaign's confirmation ledgers (`docs/research/campaign-2026-09-29/confirm/LEDGER.md` and wave-2 verdicts) as a second labelled set for Feature B, alongside OpenFGA. They record which findings were confirmed, duplicates, unclear or not-a-bug.

---

## 5. Open decisions

- **OD-5 — HIGH-precision acceptance bar. RESOLVED: ≥90% precision on HIGH findings**, adopting Google's Tricorder threshold (an analyzer surfaced in code review may carry at most a **10% effective false positive rate**; above that, developers demonstrably dismiss or disable it — Tricorder's own rate runs just under 5%). Two riders. **(a)** Adopt Tricorder's *effective* false-positive definition: a finding counts as a false positive if the operator does not act on it, even when technically correct — this is precisely BUG-009's failure mode (an accurate advisory restatement with no located defect). **(b)** At the OpenFGA fixture's sample size a rate is not measurable — one FP in six findings is 17%. So ≥90% is the **reporting/policy bar**; the **executable acceptance test** remains §4 criterion 1: 003/006/009 must not stand as confirmed HIGH, 001/002/004 must still surface. Sources: Sadowski et al., *Lessons from Building Static Analysis Tools at Google* (CACM 2018); *Software Engineering at Google* ch. 20. *(Moved here 2026-07-21: it gates this release's Phase 6, so it is no longer a v1.6.0 release-time decision.)*
- **OD-VERSION — the release number. RESOLVED 2026-10-01: v1.6.1**, with Features S and R added (Decision Record #3).

---

## 6. Coupling to v1.6.0

Track 2's work items are independent of Track 1's, but **Feature A's NFR sections render into Feature C's document architecture** (`QPB_v1.6.0_Design.md` §5.2 item 5). Feature C shipped the render slot specified to degrade gracefully in both directions, and it is already in the tree — `references/phase2_generation_guide.md` carries "Non-functional sections — NFR REQs grouped by `nfr_class`, after the functional sections. Absent until NFR derivation ships; the slot degrades gracefully."

Because Track 1 now lands first by construction, the rule from `QPB_v1.6.0_Design.md` §9 applies in one direction only: **this release runs v1.6.0's fixture suite before merging.**

**Second coupling, added 2026-07-22 (the 2026-07-21 split predates it):** v1.6.0 grew two features — **G (dump-and-go ingest)** and **H (agent-driven persona validation)** — that this release now depends on, not just coexists with:

- **Feature A ← Feature G.** NFR acceptance criteria derive at Tier 1/2 (byte-verified) when the security spec is recognized as citable; Feature G's ingest-time classification supplies that without operator pre-sorting (§2 dependency note).
- **Feature B ← Feature H.** Feature B is a rubric + target binding on top of the *target-agnostic* fresh-context sub-agent-review infrastructure Feature H builds; it should not reimplement the orchestration, independence/isolation discipline, or `agent-validation` provenance (§3 reuse note). **H and B differ in role:** H *remediates* the spec (no verdict, no correctness-measurement needed); B *judges* findings, so B carries its own accuracy ground truth — the OpenFGA labeled fixture set (§4) — which is B-local, not inherited.

Consequence: if v1.6.0 ships G and H, this release is materially smaller than the 2026-05-24 scope assumed — Feature A is mostly the `nfr_class` schema + derivation rules, and Feature B is mostly the FP-audit rubric + findings binding. Re-estimate this release's size once v1.6.0's H infrastructure boundary is known.

**Coupling-vs-split honesty (Council-flagged 2026-07-22).** Decision Record #8 split Track 2 out partly because "Track 1 has a complete acceptance story of its own." These two new couplings mean v1.6.0 is again partly a *substrate* for v1.6.1 — but the coupling is **passive/inheritable**, not a runtime dependency: v1.6.0 still tests and ships on its own oracles (G's tiering fixtures, H's remediation oracle), and v1.6.1 *reuses* H's harness rather than v1.6.0 depending on v1.6.1. The split's core rationale (v1.6.0 delivers and tests independently) holds regardless of H's role, since H is a self-contained requirements remediator; what changed is that v1.6.1 got cheaper, which sharpens **OD-VERSION** (§5) toward a point release.

A second consequence of the split, recorded because the release notes depend on it: with Feature B absent from v1.6.0, the retained 090j triage (OD-8) is that release's **only** precision guard rather than a mechanical floor beneath a judgment layer. When this release lands, 090j resumes the role OD-8 describes.

---

## 7. Council review plan

Carried from `QPB_v1.6.0_Design.md` §13 item 4, plus a pre-tag review this release now needs on its own.

1. **Slice 3 landed:** nested 3×3 Council on NFR derivation testability, FP-audit independence (verify the auditor demonstrably lacks skill/writeup context — the fabrication-tell check), the grounding rule, and the OpenFGA regression. Standard acceptance checks on responses (real source reads, three inner verdicts per outer file, convergence flags).
2. **Pre-tag:** whole-surface umbrella Council, standard.

---

## 8. Provenance

Features A and B were authored in the 2026-05-24 canonical scope, carried forward unchanged through the 2026-07-18 rewrite of `QPB_v1.6.0_Design.md`, and moved here verbatim on 2026-07-21. The OpenFGA failure analysis in §1 is the 2026-05-24 analysis, carried unchanged; full detail in the git history of `QPB_v1.6.0_Design.md`.
