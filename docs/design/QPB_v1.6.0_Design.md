# Quality Playbook v1.6.0 — Design Document: The Requirements Release

*Status: **canonical**, rewritten 2026-07-18; simplicity pass applied 2026-07-19 (Decision Record #4-6). Supersedes the 2026-05-24 "NFR discovery + FP-audit" framing of this file — which is **carried forward in full as Features A and B below**, not discarded — and closes the 2026-06-21 slot re-assessment (see Decision Record). Prior framings preserved in version-control history of this file and summarized in the Historical Appendix.*
*Owner: Andrew Stellman. Authored: Cowork session 2026-07-18, from a two-agent dossier over the QPB repo, workspace Reviews, and chat archive, plus direct reads of the canonical docs and three generated specs.*
*Depends on: the v1.5.10 close-out (in-flight as of this writing; last tag = v1.5.8). Companion: `QPB_v1.6.0_Implementation_Plan.md` (**stale as of this rewrite** — reflects the 2026-05-24 scope only; needs a rewrite before implementation starts).*

---

## 0. Decision Record (2026-07-18)

Three decisions taken by Andrew in the commissioning session for this rewrite:

1. **The 2026-06-21 slot re-assessment is closed: v1.6.0 is the requirements release.** The security line stays in v1.5.11 (its design doc is written; the secmode/gen-003/gen-004 experiments are its substrate). The re-assessment banner this doc carried since 2026-06-21 is removed. `QPB_v1.6.x_Skill_Surface_Routing_Proposal.md` still carries its companion banner and should be updated to point here.
2. **Full merge:** v1.6.0 covers NFR discovery + the FP-audit (the prior canonical scope, Features A/B) **plus** spec organization/coherence (Feature C) **plus** the requirements review/interview (Feature D). This explicitly reverses the 2026-05-24 repositioning of the Requirements Review out of v1.6.0. Rationale: the three empirical defect classes below all live in the requirements pipeline; shipping them together makes v1.6.0 one coherent story — *QPB's specs become precise, readable, and confirmed against operator intent*.
3. **The coherence problem is grounded in operator observation across many runs** ("just read the specs, you can see they're not well organized — there are a lot in the repos/ folder"), now backed by the enumerated defects in §1.2, which were verified by direct reads of the 2026-06-19 chi/express/virtio specs.

Three more, from the 2026-07-19 simplicity pass:

4. **The release's organizing frame is the Juran requirements chain — fitness for use.** QPB already does requirements *derivation* (from docs, code, and forensic inversion of error handling) and requirements *verification* (the code conforms to the derived REQs — divergence detection, TDD, the gate). It has never done requirements *validation*: nothing asks whether the derived requirements are the *right* requirements. v1.6.0 closes that link. The validation interview (Feature D) is the point of the release, not an add-on; Feature C exists partly because a progressive interview needs a coherently structured document to walk.
5. **Feature E dropped from v1.6.0.** The B-4/B-5/B-6/B-7 curation and derivation fixes serve coverage mechanics, not organization or validation. All four move back to opportunistic point-release candidates, B-4 first in line.
6. **F-1 slimmed.** The coverage signal ships as a derivation-emitted "coverage and known gaps" statement in the Overview, not mechanical per-language surface enumerators (deferred as later hardening).
7. **(2026-07-19, pre-handoff)** OD-2 resolved: the interview is a **skill-protocol chat** (a protocol reference the agent follows in a normal session; no new interactive Python surface). OD-3 resolved: **transcript-as-citable-source** (existing citation machinery applies). OD-7 defaulted: **`quality/RUN_CONTRACT.md`**. Remaining open at implementation start: OD-5 (precision bar) and OD-8 (090j disposition) — both Slice 3/release-time decisions.

---

## 1. Why v1.6.0 — three empirically observed defect classes

QPB releases are motivated by concrete observed defects, not speculative features. v1.6.0 is motivated by three, all in the requirements pipeline.

### 1.1 Precision: findings untethered from requirements (the OpenFGA failure)

The 2026-05-23 OpenFGA Mode-A dogfood (v1.5.7, real 548-file Go repo, doc-enriched) reported 3 HIGH "security" findings with **0/3 precision**, unanimously confirmed by the 090i Council: BUG-003 (missed the `tryCache` guard — unreachable), BUG-006 (the filter *is* applied upstream; cited CVE not even in version range), BUG-009 (verbatim advisory restatement, no located code defect). Root cause: QPB derives *functional* REQs rigorously but has **no equivalent rigor for non-functional requirements**, so gathered advisories pattern-match straight into "bugs" with no derived, testable security REQ to check against. v1.5.7 shipped the 090j same-agent triage band-aid; the real fix is requirements-level. *(This is the 2026-05-24 analysis, carried forward unchanged; full detail in this file's git history.)*

### 1.2 Coherence: the generated spec is not a well-organized document

Direct reads of the three 2026-06-19 benchmark runs (`repos/chi-1.5.8/quality/REQUIREMENTS.md`, `repos/express-1.5.8/…`, `repos/virtio-1.5.8/…`) show seven recurring structural defects:

- **C-1 — Tool-process contamination.** Every product spec ends with ~8 REQs about QPB's own run layout ("Per-bug writeups are placed at `quality/writeups/BUG-<id>.md`" — chi:130-152, express:140-188, virtio:197-249). These are QPB run-contract invariants, not requirements of the audited system. In express they are **half the document** (8 of 16 REQs). This is precisely the "process-prose-as-requirements" contamination `QPB_v1.6.0_Test_Fixtures.md` Fixture 2 was designed to guard against adopters introducing — QPB introduces it itself, in every run.
- **C-2 — Scrambled identifiers.** REQ IDs do not follow document order (chi sections run REQ-001/004/005, then 002, then 003/006; express runs 001/007, then 002…). `references/requirements_pipeline.md` Phase E.6 specifies a final sequential renumber; it demonstrably does not fire.
- **C-3 — Degenerate sections.** express has six functional sections holding one REQ each — the grouping does nothing, matching the degeneracy `schemas.md` (§6, functional_section notes) already warns about.
- **C-4 — Narrative inconsistency.** virtio rendered a Project overview + Cross-cutting concerns (Phase E.1/E.3 fired); chi and express rendered neither. The Phase E narrative pass — the pipeline's designed answer to "flat list → coherent document" (`requirements_pipeline.md` Phase E; lineage back to `QPB_v1.3.1_Design.md` "turn a pile of source code into a coherent set of testable requirements") — fires unpredictably, and nothing in the gate checks for it (the gate validates the manifest, never the rendered document — `schemas.md` §6).
- **C-5 — Pipeline internals leak into the render.** "Asymmetry-promotion: Finding 7 prose asymmetry … is promoted here" (chi:35); `<!-- cluster: heterogeneous -->` HTML comments on UCs (chi:182, virtio:285). Derivation metadata belongs in the manifest, not the adopter-facing spec.
- **C-6 — Bug-shaped requirements.** chi REQ-004's conditions of satisfaction embed the diagnosed defect ("`Find` … does NOT perform the wildcard-URLParam reset — so a `Find` against a mounted route leaves a stale `*` URLParam"). A requirement should state intended behavior; the observed divergence belongs in BUGS.md. Sentence-length REQ titles (chi REQ-001's title is a full normative sentence) compound this.
- **C-7 — Stale generator stamp.** chi's header says "Generated by Quality Playbook v1.5.3" on a 2026-06-19 run under v1.5.8 (express/virtio correctly say v1.5.8) — the render template carries a hardcoded version somewhere on at least one path.

*(Honesty note: the workspace archive contains no prior written "jumbled" complaint — the documented adjacent complaints are coverage/skimpiness (2026-04-02, nsq: "they look very skimpy") and unwieldy-at-scale (v1.5.3 Council: "1369 raw REQs … either the document is unwieldy at 5K-20K lines, or Phase 5 needs a curation/merge pass that doesn't exist"). The C-1…C-7 enumeration above is this document's contribution: it converts the operator's cross-run observation into named, checkable defects.)*

### 1.3 Coverage and curation: skimpy at the small end, unwieldy at the large end

- Small end: express yields **8 product REQs for all of Express** — the 2026-04-02/03 "skimpy" complaint shape (nsq, gson), never resolved with a measurable floor. RM-007 in `Requirements_Miss_Archeology.md`: a degenerate run is indistinguishable from a good run on a small target.
- Large end: the curated QPB self-derivation settled at **171 REQs against an [80,110] target** because `bin/skill_derivation/curate_requirements.py` caps per-partition but never merges across partitions (backlog B-4, `Quality Playbook/Reviews/v1.5.4_backlog.md`); the Pass A/C disposition table collapses to 2 reachable branches of 6 (B-5).

---

## 2. Feature inventory

| # | Feature | Class | Origin | Status of design |
|---|---------|-------|--------|------------------|
| A | NFR discovery as first-class REQs | precision | 2026-05-24 canonical scope | carried forward, grounded |
| B | Fresh-context requirements-grounded FP-audit | precision | 2026-05-24 canonical scope | carried forward, grounded |
| C | Spec organization & coherence (document architecture + render contract) | coherence | this rewrite; operator observation + §1.2 evidence | new, grounded |
| D | Requirements validation interview (progressive, fitness-for-purpose) | validation | `QPB_v1.6.x_Requirements_Review_Proposal.md` (2026-04-29), pulled back into v1.6.0; Juran framing 2026-07-19 | new synthesis, grounded |
| ~~E~~ | ~~Curation & derivation fixes (B-4, B-5, B-6/B-7)~~ | — | **dropped 2026-07-19** (Decision Record #5) → point-release candidates, B-4 first | see §7 |
| F | Coverage-and-gaps statement (slim) + operator-confirmed evidence | coverage/validation | this rewrite; F-1 slimmed and F-3 dropped 2026-07-19 | new, grounded |

**Backlog-numbering disambiguation (required):** "B-4/B-5/B-6" in this doc always means the *v1.5.4 requirements backlog* (`Reviews/v1.5.4_backlog.md`). `QPB_v1.5.11_Design.md` independently uses B-4/B-5/B-6 for *security* work items. Any cross-doc citation must name the source doc.

---

## 3. Feature A — First-class NFR discovery

*Carried forward from the 2026-05-24 canonical scope; substance unchanged, restated compactly. Full original text in git history.*

**Problem.** No derived, testable non-functional requirements → advisory-primed false positives (§1.1).

**Design.**
- Phase 1/2 derivation (and the skill-derivation passes) derive NFRs as first-class REQ records: same fields plus `nfr_class` (taxonomy per Wiegers / ISO-25010: security, performance/efficiency, reliability, usability, portability, maintainability, integration/interoperability) and **mandatory** `acceptance_criterion` + `verification_method`. An NFR without an acceptance criterion is invalid (the "aspirational NFR" anti-pattern).
- **Grounding rule:** an NFR finding is confirmable only if it traces to a derived NFR and demonstrates a violation of that NFR's acceptance criterion in the audited tree. Advisory/CVE with no derived-NFR violation → `KNOWN-ISSUE`, not `BUG`.
- Slice split: core classes (security, reliability, performance) first; remaining classes in the breadth slice.
- Rendering: NFR REQs render into the Feature C document architecture as their own sections, grouped by `nfr_class`, after the functional sections (§5.2).

**Verification.** Gate FAILs an NFR REQ lacking acceptance criterion / verification method (mutation-bitten both ways). Derivation fixture: the OpenFGA contextual-tuple restriction yields a derived `REQ-SEC` with an acceptance criterion. Acceptance oracle shared with Feature B (§4).

**Dependencies.** `schemas.md` REQ record extension; categorization-tier state must be confirmed in code before extending (the Lever-6 withdraw/return history — carried open question). Backlog B-13 (per-bug categorization tagging, v1.5.4 backlog) is partially subsumed by `nfr_class` — reconcile during implementation, per the 2026-05-24 doc's note.

## 4. Feature B — Fresh-context, requirements-grounded false-positive audit

*Carried forward; substance unchanged, restated compactly.*

**Problem.** Findings confirmed by the producing context inherit its confirmation bias and advisory priming (§1.1); the failure mode is class-agnostic, not security-specific.

**Design.**
- A fresh-context sub-agent pass over each *confirmed* finding, post Phase 3/4 triage, at/before Phase 5 finalization — the productionized 090i Council shape. **Independence is load-bearing:** the auditor receives only finding + cited source + relevant derived REQ + compact rubric; never the running skill, phase prompts, or writeup reasoning.
- Rubric (precision core, Slice 3): reachability (BUG-003 class), applicability incl. CVE version-range (BUG-006 class), source-of-truth (BUG-009 class), requirements-traceability. The breadth slice (Slice 4) adds design-intent, compensation, severity-justification. Security is the highest-scrutiny tier, not a separate detector.
- Verdicts: CONFIRMED / DEMOTED / RECLASSIFIED-KNOWN-ISSUE / UNCERTAIN, with reasoning; audit transcript preserved as a run artifact; precision metrics updated. New dispositions get plain-English narration via the shipped 090v verdict-explanation framework (proposal item E3).
- The `confirmed-open (integration-harness-required)` disposition (pulled 090r) becomes admissible **only** when the FP-audit independently CONFIRMs — carried unchanged.
- **Cross-link to Feature C (new):** the FP-audit's requirements-traceability check consumes the *manifest*, not the rendered document — so Feature C's render changes cannot perturb it. Where the audit demotes/reclassifies, Feature C's traceability appendix (§5.2) reflects the final disposition.

**Verification.** OpenFGA fixture set: BUG-003 → DEMOTED, BUG-006 → DEMOTED/RECLASSIFIED, BUG-009 → RECLASSIFIED-KNOWN-ISSUE, BUG-001/002/004 → CONFIRMED. One non-security fixture demoted, proving generality. Independence verified as a gate item (a writeup-fed audit is a fabrication tell).

**Dependencies.** Feature A (traceability check needs derived NFRs). Runner/model choice and cost scope are carried open questions.

## 5. Feature C — Spec organization & coherence (the headline)

**Problem.** §1.2: the rendered REQUIREMENTS.md is structurally incoherent in seven named, recurring ways, because (a) the document architecture is under-specified (one line in `references/phase2_generation_guide.md`: organized by `functional_section`, intro paragraph, ordered by REQ id), (b) the Phase E narrative pass is optional in practice and unchecked, and (c) the gate validates the manifest only and never the rendered document, so render defects are invisible to every mechanical check QPB has.

**Design principle.** *The manifest stays the source of truth; the rendered spec becomes a contract-checked presentation.* Two layers, matching QPB's house style: a mechanical **render contract** enforced by `quality_gate.py`, plus an LLM-judgment **coherence rubric** enforced by the Phase 4 Council charter. Wherever a defect class can be checked mechanically, it is; prose quality stays with the Council.

### 5.1 Separate the product spec from the tool contract (fixes C-1)

- The ~8 artifact-layout invariants move out of REQUIREMENTS.md into a new run artifact, `quality/RUN_CONTRACT.md` (name resolved per Decision Record #7), rendered from the same records. They remain gate-enforced per-run — they were never wrong as *invariants*, only mislocated as *product requirements*.
- Render-contract check: REQUIREMENTS.md contains **zero** REQs whose References point exclusively into `quality/` — mechanically checkable; mutation-bite by re-adding one.

### 5.2 Canonical document architecture (fixes C-3, C-4; argued)

Target shape — deliberately the shape of the Haiku benchmark (`Haiku QPB requirements analysis/REQUIREMENTS.md`, 2,129 lines, 95 REQs), which is the project's own "coherent document" reference standard (RM-014: it beat QPB's self-audit 3× on coverage *and* reads top-down):

1. **Header** — accurate generator stamp from the single version source (fixes C-7).
2. **Overview** — mandatory on every run regardless of size: what the system is, derivation scope and evidence base, tier distribution, and the F-1 coverage-and-gaps statement. (Phase E.1 becomes unconditional; the express-class omission becomes a gate failure.)
3. **Actors & roles** — who the requirements serve (Haiku-benchmark shape; also the natural organizer for Feature D's interview).
4. **Functional sections** — ordered **user-facing → infrastructure** (Phase E.5's existing rule, now enforced; ordering rationale stated in one line at the top of the section list). Each section: ≥2 REQs or an explicit one-line singleton justification, else merged (fixes C-3); intro prose states the section's contract theme.
5. **Non-functional sections** — Feature A's NFR REQs grouped by `nfr_class`.
6. **Cross-cutting concerns** — Phase E.3, mandatory when >1 functional section.
7. **Use cases** — unchanged content, cleaned render (no HTML comments — C-5).
8. **Traceability appendix** — rendered reverse index UC→REQ, plus REQ→BUG links carrying final FP-audit dispositions. One-way REQ→UC in the manifest is unchanged; the appendix is render-time derivation, which `schemas.md` already sanctions.

*Why argue for user-facing→infrastructure rather than architectural layering:* the spec's first consumer is an operator deciding whether the derivation captured intent (Feature D); operators recognize user-visible behavior before internals. Architectural ordering optimizes for implementers, who read the References fields anyway. (Resolved 2026-07-19 — user-facing→infrastructure, no override flag; see §12.)

### 5.3 Render contract — mechanical checks in `quality_gate.py` (fixes C-2, C-5, C-7 and pins 5.1/5.2)

1. REQ IDs strictly sequential in document order (Phase E.6 renumber becomes enforced, not aspirational).
2. No REQ whose References point exclusively into `quality/` (5.1).
3. Overview section present and non-empty; every functional section has intro prose; singleton sections carry a justification line.
4. No HTML comments; no derivation-internal vocabulary in the rendered body (deny-list seeded with `Asymmetry-promotion`, `cluster:`, pass names — the metadata lives in the manifest).
5. REQ title ≤ 120 characters, no terminal period (mechanical proxy for noun-phrase discipline; the real judgment lives in the Council rubric).
6. Generator stamp equals the single-source version (C-7 regression pin, mutation-bitten by hardcoding a stale stamp).

Every check lands with the AUDIT-table invariant-test pattern (`DEVELOPMENT_PROCESS.md` §"AUDIT-table"): sweep the render path, document verdicts, pin with mutation tests.

### 5.4 Intent-form requirements (fixes C-6)

Phase B/C derivation and the render both enforce: a REQ states **intended behavior**; observed divergence text moves to the BUG record with a link from the traceability appendix. Mechanically, the renderer rejects conditions-of-satisfaction text matching divergence-report shapes only via Council rubric (this is judgment, not regex); the *pipeline* change is a prompt-level rule in Phase B/C plus a Phase 4 Council rubric item: "does any REQ narrate a defect rather than state a contract?"

**Verification (Feature C overall).** (a) Unit: each render-contract check mutation-bitten. (b) **Regeneration fixture — the acceptance oracle:** re-render the chi, express, and virtio manifests through the new renderer; acceptance = C-1…C-7 all absent (mechanically: contract checks pass; judgment: focused Council on the three rendered docs). (c) No manifest semantic change: `requirements_manifest.json` for a fixed input is unchanged modulo the renumber map (proving Feature C is presentation-layer except where explicitly specified).

**Dependencies.** None on A/B (render slots for NFR sections degrade gracefully to absent). Feature D consumes the new render. Touches `references/requirements_pipeline.md` (Phase E hardening), `references/phase2_generation_guide.md`, the renderer path, `quality_gate.py` — all via the diagnosis→Claude Code lane.

## 6. Feature D — The requirements validation interview (fitness-for-purpose)

**Problem.** QPB verifies that code conforms to derived requirements but never validates that the derived requirements are the right ones — the missing link in the Juran chain (§0 #4). Nothing confirms the derived requirements against what the operator actually intended. The 2026-05-02 worked example (`Reviews/QPB_v1.6.x_Requirements_Review_Worked_Example_2026-05-02.md`) proved a 10-minute interactive session surfaces real defects (projected-vs-measured mismatch, glossary drift, benchmark double-count, hardcoded-enumeration coupling) that no autonomous pass caught. The 8-dimension proposal (`QPB_v1.6.x_Requirements_Review_Proposal.md`) designed the full system but was repositioned out of v1.6.0; meanwhile a lighter walkthrough **already shipped** in v1.5.7 (`quality/REVIEW_REQUIREMENTS.md` + `REFINE_REQUIREMENTS.md`, guided/self-guided/cross-model modes, progress in `REFINEMENT_HINTS.md`) — which the proposal never acknowledges. v1.6.0 reconciles the two.

**Design — MVP slice of the 8-dimension proposal, superseding the shipped walkthrough.**

- **Shape — progressive, broad strokes first, drill-down on demand.** The Feature C document architecture is the interview's outline; the interview descends it:
  - **Stage 1 — validate the narrative.** The agent plays back its understanding at the top of the document: "here's what I think this system is, who it serves, and what its major behavioral areas are — is that right?" (Overview, actors & roles, section themes, and the F-1 coverage-and-gaps statement: "here's what I believe I did not cover — intentional?"). Most fitness-for-purpose defects (wrong system, wrong actor, missing area) surface here, cheapest.
  - **Stage 2 — validate sections and use cases.** Per functional/NFR section: the contract theme and its use cases, in user-facing order. "This section says the system guarantees X under Y — is that what it's *supposed* to do?"
  - **Stage 3 — per-REQ drill-down, operator-pulled.** Individual REQs are examined only where Stage 1/2 surfaced doubt or where the operator steers ("show me the redirect requirements"). Breadth-first by default; depth is never pushed.
  - Three moves at every stage, in the operator's control: **confirm** (recorded as evidence — see F-2), **correct** (operator states what it should say — covers merges, splits, and rewording; the derivation absorbs the correction), **add** (operator names behavior the derivation missed). Plus **drop** and **defer**. *(The proposal's six structural dispositions — `tighten-prose`, `merge-with-related-REQ`, `split-into-multiple-REQs`, etc. — are folded into **correct**; per-attribute disposition taxonomy was inspection-tool ceremony for an MVP.)*
- **Elicitation content:** questions drawn from the 34 catching questions in `Reviews/Requirements_Miss_Archeology.md` (highest-yield five first: artifact-category fit, artifact-shape, judgment-vs-comparison, self-encoding, operator-vs-gate success) and the four worked-example question classes (outcome verification, terminology disambiguation, identity/independence, dependency tracing) — mapped to stages: category/shape questions belong to Stage 1, dependency/identity questions to Stages 2-3.
- **Write-back is the point:** corrections and additions land in the **manifest** (not just the render) as new/updated REQ records carrying `source_type: operator-confirmation` (F-2), then the Feature C renderer re-renders — so the spec absorbs corrections coherently instead of accreting patch notes. A surgical re-derivation of a corrected REQ (the proposal's iterate-until-clean, Dimension 3) is in scope only as "re-run derivation for this REQ with the operator's correction as evidence"; full loop tooling waits.
- **Artifacts:** `quality/REQUIREMENTS_REVIEW.md` defect log (by Wiegers attribute + disposition); transcript preserved to `quality/review_sessions/<TIMESTAMP>-<topic>.md` behind an explicit operator save-gate (the proposal's privacy concern). Inspection metrics (Dimension 8) and the QI-loop synthesis (lessons-learned → calibration hypotheses) stay in the later slice, as the proposal already sequenced.
- **Deferred from the proposal to post-v1.6.0:** Dimension 2 (multi-perspective lens), Dimension 5's informal-source corpus + `informal-spec` role tag, Dimension 8 metrics, the QI-loop closure.
- **Supersession:** the interview replaces `REVIEW_REQUIREMENTS.md`/`REFINE_REQUIREMENTS.md` generation (one system, not two); their guided/self-guided/cross-model modes are preserved as interview entry modes. Discoverability stays: the playbook-end summary offers the interview but never auto-starts it.

**Verification.** Fixture session against the QPB self-derivation: a scripted operator (test double) issues one confirm, one correct, one add, one merge; acceptance = manifest updated with correctly-shaped records, re-render passes the Feature C contract, defect log and transcript artifacts present and gate-validated. The 2026-05-02 worked example is re-run as a semi-scripted acceptance walkthrough. Mutation: a correction that never reaches the manifest must fail the fixture.

**Dependencies.** Feature C (renders the interview's input and output; without it the interview walks a jumbled document). Feature A optional but valuable (NFR sections get interviewed too). Delivery shape resolved (Decision Record #7): **skill-protocol chat** — a protocol reference (`references/requirements_interview.md` or equivalent) the agent follows in a normal session, writing session artifacts to `quality/`; no new interactive Python surface; the shipped walkthrough's guided/self-guided/cross-model modes carry over as entry modes.

## 7. Feature E — dropped from v1.6.0 (2026-07-19)

The B-4 (171-floor curation), B-5 (disposition-table degeneracy), and B-6/B-7 (resolver heuristic, partition-density tuning) fixes from `Reviews/v1.5.4_backlog.md` serve coverage mechanics on the skill-derivation path, not this release's goals (organization + validation). Per Decision Record #5 they return to opportunistic point-release candidates, **B-4 first in line** (its 171-REQ output is an at-scale readability problem and the natural next pull after Feature C ships). The 2026-07-18 revision of this file (git history) preserves the full per-item problem/design/verification text.

## 8. Feature F — New in this rewrite

### F-1 — Coverage-and-gaps statement (slimmed 2026-07-19)

**Problem.** "Skimpy" is invisible: express ships 8 product REQs and passes every gate (RM-007's degenerate-output blindness, at the spec level), and the operator has no rendered signal of what the derivation chose not to cover.
**Design (slim).** The derivation emits an honest **"coverage and known gaps" statement** into the Overview (Feature C §5.2 item 2): what the derivation covered, what it deliberately or knowingly did not (areas explored but not REQ'd, files skimmed, surfaces out of reach), stated in prose by the pass that knows. Advisory, never a gate FAIL. Its consumer is interview Stage 1, which plays it back: "here's what I believe I did not cover — intentional?" The mechanical version — per-language public-surface enumerators joined against REQ References ("41 of 87 exported symbols") — is **deferred as later hardening**, not designed here.
**Verification.** Render-contract check: Overview contains a non-empty gaps statement. Interview fixture (Feature D) exercises the Stage-1 gap question against it. Honesty of the statement is a Phase 4 Council rubric item (LLM judgment, not regex).
**Dependencies.** Feature C (render slot); Feature D (consumer).

### F-2 — Operator confirmation as first-class evidence (grounded; makes Feature D durable)

**Problem.** Interview outcomes have nowhere to live in the evidence model: `source_type` today covers formal docs, code, informal docs, inference — not "the owner said so."
**Design.** New evidence shape `operator-confirmation`: records the session, the operator's statement, and the date; attachable as the citation-equivalent for REQs confirmed/corrected/added in a Feature D session. Resolved (Decision Record #7): **transcript-as-citable-source** — the preserved session transcript is the citable document (`source_type: operator-confirmation` + a citation into the transcript file/line range), so the existing §5.4 byte-citation machinery applies nearly unchanged and no new tier is invented.
**Verification.** Gate validates the new evidence shape; a Feature D fixture correction round-trips into a citable record.
**Dependencies.** Feature D; `schemas.md` extension.

### F-3 — Re-run spec diff (**dropped from v1.6.0**, 2026-07-19)

Dropped per the simplicity pass (resolves former OD-6). The problem is real — re-runs can silently drop operator-confirmed REQs — but REQ identity across runs is its own hard design problem (RM-008's cardinality-loss lesson applies) and serves neither organization nor validation directly. One narrow obligation survives into Feature D's scope: **a re-derivation must not silently discard an `operator-confirmation`-backed REQ within the same run** (the interview's write-back is durable for the run that produced it). Cross-run protection waits for its own design doc; sketch preserved in the 2026-07-18 revision (git history).

---

## 9. Slices and sequencing — two independent tracks

**Track 1 — the release's goal (organization → validation), strictly ordered:**

- **Slice 1 — Coherence (Feature C + 5.1's RUN_CONTRACT split + F-1's Overview slot).** First because it is self-contained, has a crisp acceptance oracle (the chi/express/virtio regeneration fixture), and the interview walks its output — a progressive interview over a jumbled document is not possible. *(Resolves former OD-1: coherence-first, by dependency rather than preference.)*
- **Slice 2 — Validation (Feature D MVP + F-2).** The interview fixture + the re-run 2026-05-02 worked example.

**Track 2 — carried precision scope (independent of Track 1; can run in parallel or after):**

- **Slice 3 — Precision core (Features A + B, core NFR classes + slice-1 rubric).** The OpenFGA re-run acceptance oracle, carried unchanged: BUG-003/006/009 cannot stand as confirmed HIGH; BUG-001/002/004 still surface.
- **Slice 4 — Precision breadth (remaining NFR classes, full FP-audit rubric).**

Post-v1.6.0 (unchanged from prior planning): interview Dimensions 2/5/8, QI-loop closure (needs calibration infra), Feature E's B-4 (first point-release candidate), mechanical F-1 hardening, cross-run spec diff, SPC (v1.7.0 — whose design docs are stale and need a rewrite; they still describe v1.6 as the Requirements Review release).

## 10. Success criteria

1. **Coherence oracle:** chi/express/virtio manifests re-rendered through the new renderer exhibit none of C-1…C-7; all render-contract checks pass and are mutation-bitten; a focused Council on the three rendered documents returns Ship on readability.
2. **Precision oracle (carried):** OpenFGA re-run — 003/006/009 demoted/reclassified, 001/002/004 surface, HIGH precision ≥ the bar (OD-5), advisory-only findings classified KNOWN-ISSUE.
3. **Validation oracle:** the Feature D fixture session runs all three stages, round-trips confirm/correct/add into the manifest and a clean re-render; artifacts (defect log, transcript) gate-validated.
4. NFR REQs derived with acceptance criteria + verification methods; gate rejects aspirational NFRs.
5. F-1 coverage-and-gaps statement present in the Overview on every run, and exercised by interview Stage 1.
6. No recall collapse anywhere: bin/tests + gate green dual-env; QPB self-audit REQ coverage not reduced.

## 11. Out of scope for v1.6.0

Interview Dimensions 2/5/8 and QI-loop closure; Feature E (B-4/B-5/B-6/B-7 — point-release candidates, B-4 first); mechanical F-1 surface enumerators; F-3 cross-run spec diff; control charts / SPC (v1.7.0); new benchmark targets or runners; skill-surface routing (`--surface`, own proposal); bug-report PR automation (own proposal); Phase-6 structural enforcement (own proposal).

## 12. Open decisions

**Still open** (both Slice 3 / release-time; neither blocks the Track 1 handoff):

- **OD-5 — HIGH-precision acceptance bar** (carried from the 2026-05-24 doc). Resolve before the Phase-gate on the OpenFGA re-run.
- **OD-8 — 090j band-aid disposition** (carried): retire / retain as cheap first pass / fold into FP-audit rubric. Resolve at release notes time.

**Resolved** (recorded for traceability):

- *2026-07-19 simplicity pass:* former OD-1 → coherence-first, by dependency (§9); OD-4 → deleted with F-1's slimming; OD-6 → F-3 dropped; OD-9 → user-facing→infrastructure ordering, no override flag (a flag is complexity with no observed demand); OD-10 → defer unification, document the seam in the Implementation Plan (B-5's departure removes the immediate pressure on it).
- *2026-07-19 pre-handoff (Decision Record #7):* OD-2 → skill-protocol chat; OD-3 → transcript-as-citable-source; OD-7 → `quality/RUN_CONTRACT.md`.

## 13. Council review plan

Per `DEVELOPMENT_PROCESS.md`, pre-implementation Council of briefs is over-engineering; the load-bearing reviews run on landed code. Proposed review points:

1. **This design doc (optional, cheap):** a focused single-panel sanity pass on §5's render contract and §6's write-back model — the two places a wrong design decision is expensive to unwind. Not a nested Council.
2. **Slice 1 landed:** worker self-Council (3 panelists: render-contract correctness incl. mutation coverage; regeneration-fixture fidelity against C-1…C-7; regression safety on manifest semantics) + a focused readability review of the three regenerated fixture docs.
3. **Slice 2 landed:** worker self-Council on manifest write-back correctness, interview-artifact gate compliance, and supersession completeness (no orphaned REVIEW_REQUIREMENTS.md generation path left behind).
4. **Slice 3 landed:** the carried Phase-4 plan — nested 3×3 Council on NFR derivation, FP-audit independence (verify the auditor demonstrably lacks skill/writeup context — the fabrication-tell check), grounding rule, OpenFGA regression.
5. **Pre-tag:** whole-surface umbrella Council, standard.

## 14. Provenance

- 2026-07-18 commissioning session (this rewrite): slot decision, full-merge decision, operator observation on spec organization; direct reads of `repos/{chi,express,virtio}-1.5.8/quality/REQUIREMENTS.md` producing C-1…C-7.
- Two-agent dossier (2026-07-18): QPB repo sweep (release state: last tag v1.5.8, 1.5.10 in-flight untagged; pipeline file map; B-4/B-5 backlog; stale-doc flags for `IMPROVEMENT_LOOP.md` and the v1.7.0 docs) + workspace/chat-archive sweep (skimpy-complaint lineage 2026-04-02/03; the shipped v1.5.7 walkthrough; the 2026-05-02 worked example; the secmode/security-line chats 2026-06-19/21).
- Carried provenance from the 2026-05-24 framing: the OpenFGA dogfood, the 090i Council, the 090j band-aid, `QPB_v1.6.0_Test_Fixtures.md`.
- Feature D lineage: `QPB_v1.6.x_Requirements_Review_Proposal.md` (Wiegers/Fagan/Humphrey + ASPM Ch. 5/6), `Reviews/Requirements_Miss_Archeology.md` (14 misses, 34 catching questions), the v1.2.15 Step 7a elicitation ancestor.

---

## Historical Appendix (superseded framings, summarized)

1. **April 2026 — "first lever pull."** Absorbed by v1.5.5/v1.5.6. (Detail in git history.)
2. **2026-05-03 → 2026-05-24 — "Requirements Review UX as v1.6.0."** Repositioned out on 2026-05-24; pulled back in (as Feature D, MVP-sliced) by the 2026-07-18 decision record.
3. **2026-05-24 → 2026-07-18 — "NFR discovery + FP-audit" as the whole of v1.6.0.** Not superseded in substance — carried forward as Features A and B; superseded only as the *complete* scope. The 2026-06-21 slot re-assessment banner it carried is closed per §0.
4. The v1.5.4 carry-forward backlog list (B-2/B-3/B-8…B-14 etc.) remains valid as opportunistic point-release candidates; the requirements-relevant items (B-4/B-5/B-6/B-7) were briefly promoted into Feature E (2026-07-18), then returned to point-release candidates by the 2026-07-19 simplicity pass (§7), B-4 first in line. The full list lives in the 2026-05-24 revision of this file (git history) and `Reviews/v1.5.4_backlog.md`.
