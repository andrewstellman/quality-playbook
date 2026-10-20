# Quality Playbook v1.6.2 — Design Document: The Precision Release

*Status: **canonical for Track 2 (precision)**, created 2026-10-20 by moving Features A and B out of `QPB_v1.6.1_Design.md`. The sections below are moved verbatim from that document; nothing in them is new design. The section numbers are kept so cross-references stay valid. Inside the moved sections (§1 to §7), "this release" and "v1.6.1" refer to the precision release, which is now v1.6.2; outside them, v1.6.1 means the release that shipped on 2026-10-20. Section and decision-record numbers cited without a file name belong to `QPB_v1.6.0_Design.md`, where these sections were first written.*

*Owner: Andrew Stellman. Companion: `QPB_v1.6.2_Implementation_Plan.md`.*

*Depends on: v1.6.1 shipped (Features S, R, W, and the 1.6.1 G and H: gate verdict honesty and persona fixes).*

---

## 0. Decision Record

1. **(2026-10-20, Andrew) Features A and B move from v1.6.1 to v1.6.2.** v1.6.1 ships the features that were built and tested (S, R, W, G and H); the precision work (Features A and B, their OpenFGA acceptance test and the precision Council) was not started and becomes this release. Earlier history of these features is in `QPB_v1.6.1_Design.md` (Decision Records #1 to #3) and, before that, `QPB_v1.6.0_Design.md`.
2. **(2026-10-20) Carried from v1.6.1, not finished there:** the `submit-pr` command (`QPB_v1.6.1_Design.md` §2b, Implementation Plan Phase R2). v1.6.1 shipped the in-skill path (R3), which generates `submit.sh`, `dup-search.sh` and `verify.sh` per bug; the standalone `submit-pr` and its `--dry-run` acceptance were not built. Whether it is still needed alongside the generated scripts is open.

---

## 1. Precision: findings untethered from requirements (the OpenFGA failure)

The 2026-05-23 OpenFGA Mode-A dogfood (v1.5.7, real 548-file Go repo, doc-enriched) reported 3 HIGH "security" findings with **0/3 precision**, unanimously confirmed by the 090i Council: BUG-003 (missed the `tryCache` guard — unreachable), BUG-006 (the filter *is* applied upstream; cited CVE not even in version range), BUG-009 (verbatim advisory restatement, no located code defect). Root cause: QPB derives *functional* REQs rigorously but has **no equivalent rigor for non-functional requirements**, so gathered advisories pattern-match straight into "bugs" with no derived, testable security REQ to check against. v1.5.7 shipped the 090j same-agent triage band-aid; the real fix is requirements-level. *(This is the 2026-05-24 analysis, carried forward unchanged; full detail in this file's git history.)*

*(Section moved from `QPB_v1.6.0_Design.md` §1.1 on 2026-07-21. It is the motivating defect for this release, not for v1.6.0.)*

---

## 2. Feature A — First-class NFR discovery

*Carried forward from the 2026-05-24 canonical scope; substance unchanged, restated compactly. Full original text in the git history of `QPB_v1.6.0_Design.md`.*

**Problem.** No derived, testable non-functional requirements → advisory-primed false positives (§1.1).

**Design.**
- Phase 1/2 derivation (and the skill-derivation passes) derive NFRs as first-class REQ records: same fields plus `nfr_class` (taxonomy per Wiegers / ISO-25010: security, performance/efficiency, reliability, usability, portability, maintainability, integration/interoperability) and **mandatory** `acceptance_criterion` + `verification_method`. An NFR without an acceptance criterion is invalid (the "aspirational NFR" anti-pattern).
- **Grounding rule:** an NFR finding is confirmable only if it traces to a derived NFR and demonstrates a violation of that NFR's acceptance criterion in the audited tree. Advisory/CVE with no derived-NFR violation → `KNOWN-ISSUE`, not `BUG`.
- Slice split: core classes (security, reliability, performance) first; remaining classes in the breadth slice.
- Rendering: NFR REQs render into the Feature C document architecture as their own sections, grouped by `nfr_class`, after the functional sections (`QPB_v1.6.0_Design.md` §5.2).

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

Moved from `QPB_v1.6.1_Design.md` §4 on 2026-10-20 (criteria 1 to 4 and 7, renumbered; criteria 5 and 6 belong to Features S and R and stay in v1.6.1). In that file: criteria 2 and 4 had moved from `QPB_v1.6.0_Design.md` §10, renumbered, and criterion 3 was the precision release's own.

1. **Precision oracle (carried):** OpenFGA re-run — 003/006/009 demoted/reclassified, 001/002/004 surface, advisory-only findings classified KNOWN-ISSUE. *(Corrected 2026-07-20 — this previously read "HIGH precision ≥ the bar (OD-5)," which cannot be evaluated: OD-5's own rider states the ≥90% figure is a reporting/policy bar, not measurable at fixture sample size, where one false positive in six findings is 17%. The named-bug behavior above **is** the executable test.)*
2. NFR REQs derived with acceptance criteria + verification methods; gate rejects aspirational NFRs.
3. **No regression in v1.6.0's surface:** Track 1's fixture suite (coherence + validation oracles) runs green after Track 2 merges, per the track-coupling rule carried in §6. *(2026-10-20: v1.6.1's fixture suite now has to stay green as well.)*
4. No recall collapse anywhere: bin/tests + gate green dual-env; QPB self-audit REQ coverage not reduced.
5. **Additional precision oracle (proposed 2026-10-01):** use the campaign's confirmation ledgers (`docs/research/campaign-2026-09-29/confirm/LEDGER.md` and wave-2 verdicts) as a second labelled set for Feature B, alongside OpenFGA. They record which findings were confirmed, duplicates, unclear or not-a-bug.

---

## 5. Open decisions

- **OD-5 — HIGH-precision acceptance bar. RESOLVED: ≥90% precision on HIGH findings**, adopting Google's Tricorder threshold (an analyzer surfaced in code review may carry at most a **10% effective false positive rate**; above that, developers demonstrably dismiss or disable it — Tricorder's own rate runs just under 5%). Two riders. **(a)** Adopt Tricorder's *effective* false-positive definition: a finding counts as a false positive if the operator does not act on it, even when technically correct — this is precisely BUG-009's failure mode (an accurate advisory restatement with no located defect). **(b)** At the OpenFGA fixture's sample size a rate is not measurable — one FP in six findings is 17%. So ≥90% is the **reporting/policy bar**; the **executable acceptance test** remains §4 criterion 1: 003/006/009 must not stand as confirmed HIGH, 001/002/004 must still surface. Sources: Sadowski et al., *Lessons from Building Static Analysis Tools at Google* (CACM 2018); *Software Engineering at Google* ch. 20. *(Moved here 2026-07-21: it gates this release's Phase 6, so it is no longer a v1.6.0 release-time decision.)*

---

## 6. Coupling to v1.6.0

Track 2's work items are independent of Track 1's, but **Feature A's NFR sections render into Feature C's document architecture** (`QPB_v1.6.0_Design.md` §5.2 item 5). Feature C shipped the render slot specified to degrade gracefully in both directions, and it is already in the tree — `references/phase2_generation_guide.md` carries "Non-functional sections — NFR REQs grouped by `nfr_class`, after the functional sections. Absent until NFR derivation ships; the slot degrades gracefully."

Because Track 1 now lands first by construction, the rule from `QPB_v1.6.0_Design.md` §9 applies in one direction only: **this release runs v1.6.0's fixture suite before merging.**

**Second coupling, added 2026-07-22 (the 2026-07-21 split predates it):** v1.6.0 grew two features — **G (dump-and-go ingest)** and **H (agent-driven persona validation)** — that this release now depends on, not just coexists with:

- **Feature A ← Feature G.** NFR acceptance criteria derive at Tier 1/2 (byte-verified) when the security spec is recognized as citable; Feature G's ingest-time classification supplies that without operator pre-sorting (§2 dependency note).
- **Feature B ← Feature H.** Feature B is a rubric + target binding on top of the *target-agnostic* fresh-context sub-agent-review infrastructure Feature H builds; it should not reimplement the orchestration, independence/isolation discipline, or `agent-validation` provenance (§3 reuse note). **H and B differ in role:** H *remediates* the spec (no verdict, no correctness-measurement needed); B *judges* findings, so B carries its own accuracy ground truth — the OpenFGA labeled fixture set (§4) — which is B-local, not inherited.

Consequence: if v1.6.0 ships G and H, this release is materially smaller than the 2026-05-24 scope assumed — Feature A is mostly the `nfr_class` schema + derivation rules, and Feature B is mostly the FP-audit rubric + findings binding. Re-estimate this release's size once v1.6.0's H infrastructure boundary is known.

**Coupling-vs-split honesty (Council-flagged 2026-07-22).** `QPB_v1.6.0_Design.md` Decision Record #8 split Track 2 out partly because "Track 1 has a complete acceptance story of its own." These two new couplings mean v1.6.0 is again partly a *substrate* for v1.6.1 — but the coupling is **passive/inheritable**, not a runtime dependency: v1.6.0 still tests and ships on its own oracles (G's tiering fixtures, H's remediation oracle), and v1.6.1 *reuses* H's harness rather than v1.6.0 depending on v1.6.1. The split's core rationale (v1.6.0 delivers and tests independently) holds regardless of H's role, since H is a self-contained requirements remediator; what changed is that v1.6.1 got cheaper, which sharpens **OD-VERSION** (`QPB_v1.6.1_Design.md` §5) toward a point release.

A second consequence of the split, recorded because the release notes depend on it: with Feature B absent from v1.6.0, the retained 090j triage (OD-8) is that release's **only** precision guard rather than a mechanical floor beneath a judgment layer. When this release lands, 090j resumes the role OD-8 describes.

---

## 7. Council review plan

Carried from `QPB_v1.6.0_Design.md` §13 item 4, plus a pre-tag review this release now needs on its own.

1. **Slice 3 landed:** nested 3×3 Council on NFR derivation testability, FP-audit independence (verify the auditor demonstrably lacks skill/writeup context — the fabrication-tell check), the grounding rule, and the OpenFGA regression. Standard acceptance checks on responses (real source reads, three inner verdicts per outer file, convergence flags).
2. **Pre-tag:** whole-surface umbrella Council, standard.

---

## 8. Provenance

Features A and B were authored in the 2026-05-24 canonical scope, carried forward unchanged through the 2026-07-18 rewrite of `QPB_v1.6.0_Design.md`, and moved here verbatim on 2026-07-21. The OpenFGA failure analysis in §1 is the 2026-05-24 analysis, carried unchanged; full detail in the git history of `QPB_v1.6.0_Design.md`.

*Moved again on 2026-10-20 from `QPB_v1.6.1_Design.md` to this file, unchanged apart from the dated note on success criterion 3.*
