# Quality Playbook v1.6.1 — Design Document: The Precision Release

*Status: **canonical for Track 2**, created 2026-07-21 by splitting Track 2 out of `QPB_v1.6.0_Design.md`. Features A and B below are moved verbatim from that document, where they had been carried forward unchanged from the 2026-05-24 canonical scope. Nothing in this file is new design; it is the same scope under its own release.*

*Owner: Andrew Stellman. Companion: `QPB_v1.6.1_Implementation_Plan.md`.*

*Depends on: v1.6.0 (Track 1) shipped. See §6 for the coupling.*

---

## 0. Decision Record

1. **(2026-07-21, Andrew) Track 2 splits out of v1.6.0 into its own release.** Rationale: Track 1 (Features C and D) has a complete acceptance story of its own — the coherence oracle, the validation oracle and F-1 — so it can be tested and delivered without waiting on the OpenFGA precision re-run. Shipping it separately gets the requirements work into use sooner. This **partially reverses Decision Record #2 in `QPB_v1.6.0_Design.md`** ("Full merge"), which pulled Features A/B and C/D into one release; the coherence rationale in that decision still holds for C and D, and only the A/B half is undone.

2. **⚠ OPEN — the version number is not settled.** This file is named `v1.6.1` provisionally, per the operator's initial framing. Andrew, 2026-07-21: *"i'm not sure -- we should separate things as much as possible."* The number is deliberately left open because nothing depends on it yet and a rename is free, while deciding it well needs evidence that does not exist yet.

   The case for a point release: the Implementation Plan specifies Feature A's schema extension as backward-compatible, additive and shape-tolerant, never rewriting an existing record's shape. If that holds in practice, a point release is defensible, and it avoids a third version renumber in three days (v1.7.0 became the security line and SPC moved to v1.8.0 on 2026-07-20).

   The case against: Feature B adds a new pipeline pass and four new verdict dispositions, which is feature-sized work rather than a fix.

   **Resolve this before Phase 5 starts, once the schema extension has been attempted and its true blast radius is known.** Renaming these two files and their cross-references is the entire cost of being wrong.

---

## 1. Precision: findings untethered from requirements (the OpenFGA failure)

The 2026-05-23 OpenFGA Mode-A dogfood (v1.5.7, real 548-file Go repo, doc-enriched) reported 3 HIGH "security" findings with **0/3 precision**, unanimously confirmed by the 090i Council: BUG-003 (missed the `tryCache` guard — unreachable), BUG-006 (the filter *is* applied upstream; cited CVE not even in version range), BUG-009 (verbatim advisory restatement, no located code defect). Root cause: QPB derives *functional* REQs rigorously but has **no equivalent rigor for non-functional requirements**, so gathered advisories pattern-match straight into "bugs" with no derived, testable security REQ to check against. v1.5.7 shipped the 090j same-agent triage band-aid; the real fix is requirements-level. *(This is the 2026-05-24 analysis, carried forward unchanged; full detail in this file's git history.)*

*(Section moved from `QPB_v1.6.0_Design.md` §1.1 on 2026-07-21. It is the motivating defect for this release, not for v1.6.0.)*

---

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

**One thing Feature B does NOT inherit — the calibration/gating harness.** v1.6.0 ships Feature H **non-gating** and explicitly defers the accuracy-calibration (precision/recall against a labeled corpus, not run-to-run variance) to post-v1.6.0. So if Feature B needs to *gate* (block a finding's disposition on its verdict), it must build or share that accuracy-calibration itself — it cannot inherit a harness v1.6.0 didn't build. **Implementation note:** confirm which parts of H actually shipped before building B; the orchestration + isolation are inheritable, the gating-calibration is not (it is post-v1.6.0 for both releases). Feature B's OpenFGA acceptance oracle (§4) is a fixed, labeled fixture set, so B has its *own* accuracy ground truth for the specific bugs — that is the calibration B needs, and it is B-local, not inherited from H.

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

---

## 5. Open decisions

- **OD-5 — HIGH-precision acceptance bar. RESOLVED: ≥90% precision on HIGH findings**, adopting Google's Tricorder threshold (an analyzer surfaced in code review may carry at most a **10% effective false positive rate**; above that, developers demonstrably dismiss or disable it — Tricorder's own rate runs just under 5%). Two riders. **(a)** Adopt Tricorder's *effective* false-positive definition: a finding counts as a false positive if the operator does not act on it, even when technically correct — this is precisely BUG-009's failure mode (an accurate advisory restatement with no located defect). **(b)** At the OpenFGA fixture's sample size a rate is not measurable — one FP in six findings is 17%. So ≥90% is the **reporting/policy bar**; the **executable acceptance test** remains §4 criterion 1: 003/006/009 must not stand as confirmed HIGH, 001/002/004 must still surface. Sources: Sadowski et al., *Lessons from Building Static Analysis Tools at Google* (CACM 2018); *Software Engineering at Google* ch. 20. *(Moved here 2026-07-21: it gates this release's Phase 6, so it is no longer a v1.6.0 release-time decision.)*
- **OD-VERSION — the release number.** See Decision Record #2 above. Open.

---

## 6. Coupling to v1.6.0

Track 2's work items are independent of Track 1's, but **Feature A's NFR sections render into Feature C's document architecture** (`QPB_v1.6.0_Design.md` §5.2 item 5). Feature C shipped the render slot specified to degrade gracefully in both directions, and it is already in the tree — `references/phase2_generation_guide.md` carries "Non-functional sections — NFR REQs grouped by `nfr_class`, after the functional sections. Absent until NFR derivation ships; the slot degrades gracefully."

Because Track 1 now lands first by construction, the rule from `QPB_v1.6.0_Design.md` §9 applies in one direction only: **this release runs v1.6.0's fixture suite before merging.**

**Second coupling, added 2026-07-22 (the 2026-07-21 split predates it):** v1.6.0 grew two features — **G (dump-and-go ingest)** and **H (agent-driven persona validation)** — that this release now depends on, not just coexists with:

- **Feature A ← Feature G.** NFR acceptance criteria derive at Tier 1/2 (byte-verified) when the security spec is recognized as citable; Feature G's ingest-time classification supplies that without operator pre-sorting (§2 dependency note).
- **Feature B ← Feature H.** Feature B is a rubric + target binding on top of the *target-agnostic* fresh-context sub-agent-review infrastructure Feature H builds; it should not reimplement the orchestration, independence/isolation discipline, or `agent-validation` provenance (§3 reuse note). **It does not inherit gating-calibration** — v1.6.0 ships H non-gating, so B supplies its own accuracy ground truth (its OpenFGA labeled fixture set, §4) for any gating it does.

Consequence: if v1.6.0 ships G and H, this release is materially smaller than the 2026-05-24 scope assumed — Feature A is mostly the `nfr_class` schema + derivation rules, and Feature B is mostly the FP-audit rubric + findings binding. Re-estimate this release's size once v1.6.0's H infrastructure boundary is known.

**Coupling-vs-split honesty (Council-flagged 2026-07-22).** Decision Record #8 split Track 2 out partly because "Track 1 has a complete acceptance story of its own." These two new couplings mean v1.6.0 is again partly a *substrate* for v1.6.1 — but the coupling is **passive/inheritable**, not a runtime dependency: v1.6.0 still tests and ships on its own oracles (G's tiering fixtures, H's non-gating persona oracle), and v1.6.1 *reuses* H's harness rather than v1.6.0 depending on v1.6.1. The split's core rationale (v1.6.0 delivers and tests independently) holds; what changed is that v1.6.1 got cheaper, which sharpens **OD-VERSION** (§5) toward a point release.

A second consequence of the split, recorded because the release notes depend on it: with Feature B absent from v1.6.0, the retained 090j triage (OD-8) is that release's **only** precision guard rather than a mechanical floor beneath a judgment layer. When this release lands, 090j resumes the role OD-8 describes.

---

## 7. Council review plan

Carried from `QPB_v1.6.0_Design.md` §13 item 4, plus a pre-tag review this release now needs on its own.

1. **Slice 3 landed:** nested 3×3 Council on NFR derivation testability, FP-audit independence (verify the auditor demonstrably lacks skill/writeup context — the fabrication-tell check), the grounding rule, and the OpenFGA regression. Standard acceptance checks on responses (real source reads, three inner verdicts per outer file, convergence flags).
2. **Pre-tag:** whole-surface umbrella Council, standard.

---

## 8. Provenance

Features A and B were authored in the 2026-05-24 canonical scope, carried forward unchanged through the 2026-07-18 rewrite of `QPB_v1.6.0_Design.md`, and moved here verbatim on 2026-07-21. The OpenFGA failure analysis in §1 is the 2026-05-24 analysis, carried unchanged; full detail in the git history of `QPB_v1.6.0_Design.md`.
