# Quality Playbook v1.6.0 — Design Document

*Status: scope reframed **2026-05-24** to the **Non-Functional Requirements discovery + requirements-grounded false-positive audit** feature. This supersedes the 2026-05-03 "Requirements Review UX" framing (now repositioned to a later v1.6.x point release — see "v1.6.x track map" below) and the original April-2026 "single lever pull" framing (absorbed by v1.5.5/v1.5.6). v1.6.0's actual scope is now: make QPB derive **non-functional requirements as first-class, testable REQs**, and add a **fresh-context, requirements-grounded false-positive audit** over confirmed findings. Both pieces are motivated by a concrete, just-observed defect (the 2026-05-23 OpenFGA dogfood), not by abstract planning. The pre-2026-05-24 narrative is preserved at the bottom as historical context and is no longer canonical.*
*Owner: Andrew Stellman. Reframed: 2026-05-24. Depends on: v1.5.7 (shipping — incl. the 090j triage band-aid this feature supersedes at the requirements level).*

---

## ⚠️ Read this first — why v1.6.0 is the NFR feature

v1.6.0 is **empirically motivated**, which is the QPB way: a release driven by a concrete missed/false finding, not a speculative feature. The 2026-05-23 OpenFGA Mode-A dogfood (QPB v1.5.7, npm-channel install, real 548-file Go repo, doc-enriched) reported 9 bugs including 3 HIGH "security" findings — and a unanimous 3-model Council review of those findings (instruction 090i) confirmed **0/3 HIGH precision**:

- **BUG-003** (HIGH, cache consistency): FALSE POSITIVE — missed the `tryCache` guard that already bypasses the cache for `HIGHER_CONSISTENCY`.
- **BUG-006** (HIGH, contextual-tuples / "CVE-2025-48371 class"): FALSE POSITIVE on two grounds — the `userType` filter *is* applied and `validateCtxTupleInModel` enforces type restrictions upstream; *and* the cited CVE affects ≥1.8.0, so v1.5.7 isn't even in range.
- **BUG-009** (HIGH, "CVE-2024-42473 unpatched"): DOC-RESTATEMENT — verbatim from a gathered advisory, not a located code defect.

Strict precision was 3/9 (the genuine finds — BUG-001/002/004 — were the non-security code-analysis ones). v1.5.7 shipped a **band-aid** (instruction 090j: same-agent triage rules — reachability note, KNOWN-ISSUE classification, security-HIGH bar) to stop the worst of it in the shipping version.

**The root cause is a requirements asymmetry, which is why the real fix belongs in v1.6.0 (a requirements-focused release):** QPB derives *functional* REQs rigorously (code-derived behavioral contracts → a bug is a concrete deviation with file:line + a test), but it has **no equivalent rigor for non-functional requirements** (security, performance, reliability, …). So when an adopter feeds security advisories, the agent has no derived, testable security REQ to check a finding against — it pattern-matches advisories straight into "bugs." BUG-006 is the proof: had QPB *derived* `REQ-SEC: contextual tuples MUST be filtered by allowedUserTypeRestrictions [acceptance: a disallowed-type contextual tuple does not contribute; verify: <test>]`, the agent would have had to test it against the code and found `validateCtxTupleInModel` already enforces it — no bug.

So v1.6.0 fixes it where the problem lives: derive NFRs as first-class requirements, then verify findings against them.

---

## v1.6.x track map (so nothing is lost)

v1.6.0 is the **NFR discovery + requirements-grounded FP-audit** release. The other v1.6.x candidates remain open and independent; they ship as later v1.6.x point releases in motivation-driven order (no hard sequence between them):

- **v1.6.0 (this doc): NFR discovery + requirements-grounded FP-audit.** First, because it's motivated by a known issue, is self-contained, and is a *prerequisite* for meaningful requirements review (you can't review requirements that aren't being derived).
- **Requirements Review UX** (`QPB_v1.6.x_Requirements_Review_Proposal.md`) — repositioned from v1.6.0 to a later v1.6.x point release. It is the operator-facing post-playbook interactive REQ-review system; it **builds on** v1.6.0's NFR discovery (it reviews the derived REQs, now including NFRs). Its Slice 3 (QI-loop closure) shares machinery with this feature's lessons-learned synthesis.
- **Phase Validator Structural Enforcement** (`QPB_v1.6.x_Phase6_Structural_Enforcement_Proposal.md`) — independent; subprocess-attestation for the prose-only phase-boundary validator contracts.
- **Operator Verdict-Explanation Layer** (`QPB_v1.6.x_Verdict_Explanation_Proposal.md`) — plain-English gate output (lead ✅/⚠️/❌ verdict line, why-it-failed + remediation, three-bucket "weak-model / environment / real-finding" attribution, benign-WARN demotion). **Orthogonal to v1.6.0's findings work**: v1.6.0 changes *which* findings are confirmed; this layer changes *how* they're explained — they compose, no collision. The **framework + high-frequency content slice ships in v1.5.7** (instruction 090v, additive end-of-`main()` block, load-bearing `total_line`/`result_line`/`exit_code` untouched). **v1.6.0 integration point:** when this release adds new finding dispositions (`KNOWN-ISSUE` from the grounding rule, `DEMOTED`/`RECLASSIFIED` from the FP-audit, `confirmed-open (integration-harness-required)`), the verdict layer gains a plain-English explanation for each (proposal item E3) — additive over the 090v framework, the operator-facing narration of the FP-audit's per-finding verdicts. The remaining expansion (E1 full per-check coverage, E2 WARN-severity taxonomy, E4 named fabrication tells, E5 machine-readable verdict, E6 severity-aware lead line) sequences across v1.6.x.
- **Verdict-fidelity track** — the TDD-not-executed verdict qualifier (#326 fuller half) + probe-heuristic hardening (089q finding D4). Independent.
- **Bug-Report PR Automation** (`QPB_v1.6.x_Bug_Report_PR_Automation_Proposal.md`) — opened **2026-05-29**. Automates the two-commit red-then-green PR workflow from a QPB run: take one or more confirmed bugs, create a branch (on the operator's fork by default), apply each bug's regression-test patch + verify RED → commit → apply fix patch + verify GREEN + no regressions → commit; push the branch; open a PR via `gh`. Multi-bug mode rolls 2N commits into a single PR with a commit-to-bug-ID mapping table. Independent of v1.6.0's NFR/FP-audit work (consumes v1.5.7's `BUGS.md` + `quality/patches/` artifacts; doesn't touch the shipped skill). Motivated by the 2026-05-29 12-repo / six-language bug-report campaign — the friction of doing this by hand caps the campaign's throughput. The handwritten workflow it automates is at `Quality Playbook/v1.5.7_runner/BUG_REPORT_WORKFLOW.md`.
- **Carry-forward backlog from v1.5.4** (B-4 … B-14 + Round-8a/8b items) — opportunistic point-release candidates, sequenced by calibration cycles, not a fixed list (preserved verbatim at the bottom).
- **Done early:** the pip+npm distribution channels (`QPB_v1.6.x_Distribution_Channels_Proposal.md`) shipped in v1.5.7.

---

## What v1.6.0 delivers

Two coupled pieces. (A) is the new capability; (B) is the precision mechanism — kept **general**, not NFR-only, so it covers every finding class while (A) closes the NFR-specific gap.

### A — First-class non-functional-requirement discovery & documentation

QPB's Phase 1/2 derivation gains explicit NFR coverage: alongside functional REQs, it derives **non-functional requirements as first-class records** with the same rigor — each carrying an **acceptance criterion** and a **verification method** (how you'd observe the REQ is met), so an NFR is testable, not aspirational.

- **NFR taxonomy** (the classes to derive, drawn from Wiegers / ISO-25010): **security, performance/efficiency, reliability, usability, portability, maintainability, integration/interoperability** (compatibility). Functional requirements are unchanged.
- **First-class REQ shape:** an NFR REQ has the same record fields as a functional REQ plus an `nfr_class` tag and a mandatory `acceptance_criterion` + `verification_method`. It traces to evidence (code, formal docs, exploration) the same way functional REQs do. It is **not** valid to assert an NFR with no acceptance criterion (the "aspirational NFR" anti-pattern QPB must avoid).
- **Categorization tie-in:** `nfr_class` extends the existing REQ categorization. (The "Lever 6 categorization tier" was *withdrawn* in earlier framings as speculative; here it returns concretely, scoped to the NFR taxonomy — confirm the current categorization implementation during the design-doc-to-code step rather than assuming the earlier withdraw/return state.)
- **Grounding rule (the precision fix at the requirements level):** an NFR finding (e.g. a security bug) may only be confirmed if it traces to a derived NFR and demonstrates a violation of that NFR's acceptance criterion in the audited tree. A gathered advisory/CVE with no derived-NFR violation is a `KNOWN-ISSUE`, not a `BUG`.

### B — Fresh-context, requirements-grounded false-positive audit

A QPB-spun **fresh-context sub-agent pass** that adversarially re-verifies each *confirmed* finding (functional and NFR) against the derived requirements — the productionized form of the 090i Council shape. It is **general** (not NFR- or security-only): the failure mode it guards (a finding contradicted by something the producing agent didn't check) is class-agnostic.

- **Independence is the point.** The audit sub-agent does NOT load the running QPB skill, the phase prompts, or the writeup's reasoning — it gets only the finding + the cited source + the relevant derived REQ + a compact rubric. That independence removes the producing agent's confirmation bias and advisory-priming (the exact bias that produced the OpenFGA FPs). It also makes the pass context-cheap.
- **Class-agnostic rubric (each confirmed finding):** **reachability** (is there an upstream guard/filter/early-return that makes the cited defect unreachable? — the BUG-003 class); **compensation** (is it handled elsewhere — cache, retry, default, validation?); **applicability** (does it apply to this tree/version/config? incl. CVE version-range — the BUG-006 class); **source-of-truth** (real located code defect vs advisory/doc restatement → `KNOWN-ISSUE` — the BUG-009 class); **design-intent** (documented/intentional choice? — the BUG-007/008 class); **severity-justification** (does the claimed severity match a demonstrated impact path?); **requirements-traceability** (does it violate a *derived* REQ — functional or NFR — or is it untethered?).
- **Security is the highest-scrutiny tier**, not a separate detector: a HIGH security/auth-bypass finding needs a demonstrated reachable path + (if a CVE is cited) a verified version match — or it's downgraded/reclassified.
- **Output:** a per-finding verdict (CONFIRMED / DEMOTED / RECLASSIFIED-KNOWN-ISSUE / UNCERTAIN) with reasoning; the confirmed-bug set + precision metrics updated accordingly; the audit transcript preserved as a run artifact.
- **Integration-harness-required disposition (FP-audit-gated; deferred here from v1.5.7's pulled instruction 090r).** A confirmed bug whose red/green TDD cannot run in-tree because it needs an integration / in-memory harness absent from the audited tree (the 2026-05-24 OpenFGA run4 BUG-002 case — a stale-cache `ListObjects` bug needing a running server + datastore + cache controller) may be accepted as `confirmed-open (integration-harness-required)` — *not a gate FAIL* — **but only when the fresh-context FP-audit independently CONFIRMs it.** This was deliberately pulled from v1.5.7 (090r, reverted 2026-05-25, HEAD left at 090q `ebf1776`): accepting a *not-runtime-tested* bug on static evidence alone (a mechanical probe + Council convergence) re-opens the FP risk, because that is the same signal class that produced the original OpenFGA false positives — a runtime red→green is the strongest FP disproof, and this case skips it. The FP-audit is the mechanism that can vet such a bug; until v1.6.0 ships it, an integration-harness bug honestly FAILs the v1.5.7 gate (conservative + honest — the run4 auditor confirmed that FAIL is accurate). The 090r guard is retained as a *floor* (fix patch + regression-test patch present; probe + Council evidence; a documented structural reason why no in-tree harness) and an environment/setup failure (090p) can never qualify — but the FP-audit confirmation is the *additional* gate that makes it safe. Pulled instruction preserved at `AI-Driven Development/Quality Playbook/v1.5.7_runner/deferred/090r-gate-integration-harness-notrun-disposition.md`.

### What v1.6.0 does NOT deliver

- The full Requirements Review operator UX (the 8-dimension interactive session) — the repositioned later v1.6.x point release. v1.6.0 derives NFRs and audits findings; it does not add the interactive review-session UX.
- Control charts / formal SPC. Still needs ~20-30 stable observations.
- New benchmark targets or runners.

---

## How NFR discovery + the FP-audit fit the pipeline

- **NFR discovery** is a Phase 1/2 derivation extension — the same passes that derive functional REQs gain NFR-class derivation with acceptance criteria. (Skill-derivation: Pass A/C produce NFR records; the gate validates the new fields.)
- **The FP-audit** runs **after** findings are confirmed (post Phase 3/4 triage, at/before Phase 5 finalization) as a fresh-context pass over the confirmed set — analogous to QPB's existing fresh-context auditors (the Phase 6 A-13 hybrid; the Phase 4 Council). It is a precision gate on the *findings*, distinct from the Phase-6 *artifact* gate.

This pairing is the architecture: NFR discovery prevents the FPs at the requirements layer; the FP-audit catches anything that slips through, independent of the producing context.

---

## Implementation slices (independently shippable, sequenced)

**Slice 1 — the v1.6.0 release (must make the OpenFGA re-run come out right):**
- NFR discovery for the **core classes (security, reliability, performance)** with mandatory acceptance criterion + verification method; the `nfr_class` REQ field + gate validation; the grounding rule (advisory-only → KNOWN-ISSUE).
- FP-audit fresh-context pass implementing the **reachability + applicability + source-of-truth + requirements-traceability** checks (the three that map to BUG-003/006/009 + traceability), security highest-scrutiny.
- **Acceptance:** re-running QPB Mode-A on OpenFGA, BUG-003/006/009 cannot stand as confirmed HIGH bugs (demoted/reclassified by the audit and/or never confirmed because they violate no derived NFR), while the genuine BUG-001/002/004 still surface. HIGH-severity precision ≥ a defined bar.

**Slice 2 — breadth + completeness:**
- Remaining NFR classes (usability, portability, maintainability, integration/interoperability).
- Full FP-audit rubric (design-intent, compensation, severity-justification).
- Inspection/precision metrics emitted per run.

**Slice 3 — QI-loop closure (depends on regression-replay/calibration being operational):**
- FP-audit + NFR-derivation defect patterns feed calibration cycles (Phase 1/2 prompt tuning). Shares machinery with the Requirements Review proposal's Slice 3; sequence after the calibration infrastructure.

---

## Success criteria

1. QPB derives NFRs as first-class REQs (core classes in Slice 1) with acceptance criteria + verification methods; the gate rejects an NFR REQ lacking them.
2. The fresh-context FP-audit runs over confirmed findings, independent of the producing context, and emits per-finding verdicts with reasoning.
3. **OpenFGA regression (the proof point):** BUG-003 (FP), BUG-006 (FP), BUG-009 (doc-restatement) do not survive as confirmed HIGH bugs on a re-run; BUG-001/002/004 still surface. No genuine finding is suppressed (precision up without recall collapse).
4. The FP-audit is **general** — it demotes a reachability/applicability/design-intent FP in a non-security class too (validated by a fixture or a second run), not only security.
5. Advisory/CVE-only findings are classified `KNOWN-ISSUE`, excluded from the confirmed-bug count.
6. bin/tests + gate green dual-env; no regression on the QPB self-audit REQ coverage.

**Test fixtures** for the above (known-input/known-answer cases) are catalogued in `QPB_v1.6.0_Test_Fixtures.md`: Fixture 1 is the OpenFGA run (primary acceptance oracle, criterion #3); Fixture 2 is a candidate synthetic *negative* fixture — the orchestrator bootstrap doc fed as gathered documentation — that tests whether the grounding rule resists **process-prose-as-requirements** contamination (a genre the OpenFGA fixture doesn't cover; correct answer = zero bugs traceable only to that doc).

---

## Out of scope for v1.6.0

- The interactive Requirements Review operator UX (repositioned v1.6.x point release).
- Autonomous/continuous improvement scheduling (v1.7+).
- Control charts / SPC limits.
- New levers, benchmark targets, or runners.

---

## Open questions (resolve during the design-doc-to-code step)

- **NFR record schema:** exact `nfr_class` enum + how `acceptance_criterion`/`verification_method` are represented in `schemas.md` and the manifests; backward-compat with existing REQ records.
- **FP-audit invocation:** which runner/model drives the fresh-context sub-agent; cost/latency budget; scope (all confirmed findings, or HIGH/MED only, like 090j).
- **Relationship to the 090j band-aid:** v1.6.0 supersedes the same-agent triage rules with requirements-grounding + the fresh-context audit; decide whether 090j's rules are retired, retained as a cheap first pass, or folded into the FP-audit rubric.
- **Categorization-tier reconciliation:** confirm the current categorization implementation/state before extending it with `nfr_class` (the earlier withdraw/return history needs grounding in code, not assumption).
- **Acceptance bar number** for HIGH-severity precision on the regression set.

---

## Provenance

- **2026-05-23 OpenFGA Mode-A dogfood** — the concrete observation (0/3 HIGH precision; advisory-primed NFR over-claiming).
- **Instruction 090i Council** (gpt-5.4 / gpt-5.3-codex / claude-sonnet-4.6, each reading the OpenFGA source) — unanimous confirmation; recommended the three guardrail directions that became 090j (v1.5.7 band-aid) and inform this feature's FP-audit rubric. Synthesis under `…/Reviews/v1.5.7_responses/` + the 090i outputs.
- **2026-05-23/24 conversation** — owner decision to make NFR discovery + the requirements-grounded FP-audit the v1.6.0 feature, repositioning the Requirements Review UX to a later v1.6.x point.
- Requirements-quality lineage (Wiegers attributes; ISO-25010 NFR classes) carries over from the Requirements Review proposal's source material.

---
---

# Historical context (superseded — preserved for reference)

*The framings below are no longer canonical. They are kept so the doc's lineage is legible.*

## Superseded framing 2 — "Requirements Review UX as v1.6.0" (2026-05-03 → 2026-05-24)

From 2026-05-03 to 2026-05-24, v1.6.0's canonical scope was the interactive Requirements Review operator UX (`QPB_v1.6.x_Requirements_Review_Proposal.md`). On 2026-05-24 that UX was **repositioned to a later v1.6.x point release** and v1.6.0 became the NFR discovery + FP-audit feature (above), because the NFR work is a prerequisite for meaningful requirements review and is motivated by the concrete OpenFGA precision failure. The Requirements Review proposal remains the canonical scope for that later release.

## Superseded framing 1 — "first iterative-improvement release / single lever pull" (April 2026)

The original April-2026 framing cast v1.6.0 as the first iterative-improvement release shipping one lever pull validated by the v1.5.4 apparatus. That goal was absorbed by v1.5.5 (run-state instrumentation + autonomous orchestrator) and v1.5.6 (Pattern 7 displacement-recovery cycle). The detailed historical text for that framing is preserved in version-control history (pre-2026-05-24 revisions of this file).

## Carry-forward backlog from v1.5.4 (still valid — opportunistic v1.6.x point-release candidates)

Dispositioned `defer-to-v1.6.0` during v1.5.4 Phase 3.6.8 (`Quality Playbook/Reviews/v1.5.4_backlog.md` Section E); sequenced by calibration cycles, not a fixed list:

- **Algorithmic / curation:** B-4 (171-floor curation — cross-partition merging / recalibrated band), B-5 (disposition-table degeneracy — Pass A/C redesign), B-6 (A.3 resolver heuristic broadening), B-7 (partition-density → curation tuning), B-9 (detector-precision FP analysis / candidate-confidence scoring), B-10 (UC anchor threshold fixtures).
- **Architectural / hygiene:** B-8 (pytest import architecture for the gate suite), B-11 (Phase 4 5-of-5 prose-to-code BUG consolidation — document or remove), B-12 (calibration-anchor refresh cadence in `classify_project.py`).
- **Cross-model / cross-version:** B-2 (cross-model second backend, opus), B-3 (v1.4.5 cross-version cell).
- **Categorization tagging:** B-13 (per-bug categorization tagging surface) — partially subsumed by v1.6.0's `nfr_class` work; reconcile.
- **Documentation cadence:** B-14 (formal orientation-doc release-cadence review + 18-persona TTP run).
- **Round-8 deferred MEDIUM/LOW:** sentinel re-verification at phase boundaries; source-unchanged check on phase failure (not only `exit_code==0`); `--strategy <X>` bare-invocation escalation; `_finalize_quality_layout` partial-move logging; dead helper `_runs_exclude_ignore` deletion; Phase 6 hardcoded `results/` read comment; AGENTS.md preservation-warning via `lib.log`.
