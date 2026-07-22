# Quality Playbook v1.6.0 — Design Document: The Requirements Release

> **Scope reduced 2026-07-21: this release is Track 1 only (Features C, D, F).** Track 2 — Features A and B, the precision scope — split out to `QPB_v1.6.1_Design.md` (version number provisional; see that file's Decision Record #2). Decision Record #8 below records the split and what it reverses.

*Status: **canonical**, rewritten 2026-07-18; simplicity pass applied 2026-07-19 (Decision Record #4-6). Supersedes the 2026-05-24 "NFR discovery + FP-audit" framing of this file — which is **carried forward in full as Features A and B below**, not discarded — and closes the 2026-06-21 slot re-assessment (see Decision Record). Prior framings preserved in version-control history of this file and summarized in the Historical Appendix.*
*Owner: Andrew Stellman. Authored: Cowork session 2026-07-18, from a two-agent dossier over the QPB repo, workspace Reviews, and chat archive, plus direct reads of the canonical docs and three generated specs.*
*Depends on: the v1.5.10 close-out — **complete as of 2026-07-19**: `v1.5.10` tagged, merged to `main`, `1.6.0` branched from it. (v1.5.10 was deliberately **not** published to PyPI/npm; publishing resumes at 1.6.0.) Companion: `QPB_v1.6.0_Implementation_Plan.md` — **current**, rewritten 2026-07-19 and carrying 2026-07-20 corrections; read it alongside this document.*

---

## 0. Decision Record (2026-07-18)

Three decisions taken by Andrew in the commissioning session for this rewrite:

1. **The 2026-06-21 slot re-assessment is closed: v1.6.0 is the requirements release.** The security line is **v1.7.0** (its design doc is written; the secmode/gen-003/gen-004 experiments are its substrate). *(Renumbered 2026-07-20 from v1.5.11 — operator decision; the 1.5.x line ended at 1.5.10, so a 1.5.11 point release no longer fits, and the security scope is feature-sized. SPC moved 1.7.0 → 1.8.0 to make room; see §9.)* The re-assessment banner this doc carried since 2026-06-21 is removed. `QPB_v1.6.x_Skill_Surface_Routing_Proposal.md` still carries its companion banner and should be updated to point here.
2. **Full merge:** v1.6.0 covers NFR discovery + the FP-audit (the prior canonical scope, Features A/B) **plus** spec organization/coherence (Feature C) **plus** the requirements review/interview (Feature D). This explicitly reverses the 2026-05-24 repositioning of the Requirements Review out of v1.6.0. Rationale: the three empirical defect classes below all live in the requirements pipeline; shipping them together makes v1.6.0 one coherent story — *QPB's specs become precise, readable, and confirmed against operator intent*.
3. **The coherence problem is grounded in operator observation across many runs** ("just read the specs, you can see they're not well organized — there are a lot in the repos/ folder"), now backed by the enumerated defects in §1.2, which were verified by direct reads of the 2026-06-19 chi/express/virtio specs.

Three more, from the 2026-07-19 simplicity pass:

4. **The release's organizing frame is the Juran requirements chain — fitness for use.** QPB already does requirements *derivation* (from docs, code, and forensic inversion of error handling) and requirements *verification* (the code conforms to the derived REQs — divergence detection, TDD, the gate). It has never done requirements *validation*: nothing asks whether the derived requirements are the *right* requirements. v1.6.0 closes that link. The validation interview (Feature D) is the point of the release, not an add-on; Feature C exists partly because a progressive interview needs a coherently structured document to walk.
5. **Feature E dropped from v1.6.0.** The B-4/B-5/B-6/B-7 curation and derivation fixes serve coverage mechanics, not organization or validation. All four move back to opportunistic point-release candidates, B-4 first in line.
6. **F-1 slimmed.** The coverage signal ships as a derivation-emitted "coverage and known gaps" statement in the Overview, not mechanical per-language surface enumerators (deferred as later hardening).
7. **(2026-07-19, pre-handoff)** OD-2 resolved: the interview is a **skill-protocol chat** (a protocol reference the agent follows in a normal session; no new interactive Python surface). OD-3 resolved: **transcript-as-citable-source** (existing citation machinery applies). OD-7 defaulted: **`quality/RUN_CONTRACT.md`**. Remaining open at implementation start: OD-5 (precision bar) and OD-8 (090j disposition) — both Slice 3/release-time decisions.

8. **(2026-07-21, Andrew) Track 2 split out into its own release.** Features A and B — NFR discovery and the fresh-context FP-audit — move to `QPB_v1.6.1_Design.md`. **This partially reverses Decision Record #2 above.** #2's "full merge" pulled A/B and C/D into one release on the argument that all three defect classes live in the requirements pipeline; that argument still holds for C and D, and only the A/B half is undone. Rationale for undoing it: Track 1 has a complete acceptance story of its own (§10 criteria 1, 3, 5), so it can be tested and delivered without waiting on the OpenFGA precision re-run, and the precision work has never been able to start until the coherence work finished anyway. Consequence to carry into the release notes: with Feature B absent, the retained 090j triage is this release's **only** precision guard (see OD-8).

---

## 1. Why v1.6.0 — two empirically observed defect classes

QPB releases are motivated by concrete observed defects, not speculative features. v1.6.0 is motivated by three, all in the requirements pipeline.

### 1.1 Precision — **moved to v1.6.1**

The OpenFGA 0/3-precision failure that motivated Features A and B now motivates `QPB_v1.6.1_Design.md` §1, where the analysis lives in full. It is named here only so the numbering below stays stable against landed commits and so a reader of this file knows the defect class exists and is not addressed by this release.

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
| ~~A~~ | ~~NFR discovery as first-class REQs~~ | — | **moved to v1.6.1 (2026-07-21)** | see `QPB_v1.6.1_Design.md` §2 |
| ~~B~~ | ~~Fresh-context requirements-grounded FP-audit~~ | — | **moved to v1.6.1 (2026-07-21)** | see `QPB_v1.6.1_Design.md` §3 |
| C | Spec organization & coherence (document architecture + render contract) | coherence | this rewrite; operator observation + §1.2 evidence | new, grounded |
| D | Requirements validation interview (progressive, fitness-for-purpose) | validation | `QPB_v1.6.x_Requirements_Review_Proposal.md` (2026-04-29), pulled back into v1.6.0; Juran framing 2026-07-19 | new synthesis, grounded |
| ~~E~~ | ~~Curation & derivation fixes (B-4, B-5, B-6/B-7)~~ | — | **dropped 2026-07-19** (Decision Record #5) → point-release candidates, B-4 first | see §7 |
| F | Coverage-and-gaps statement (slim) + operator-confirmed evidence | coverage/validation | this rewrite; F-1 slimmed and F-3 dropped 2026-07-19 | new, grounded |

**Backlog-numbering disambiguation (required):** "B-4/B-5/B-6" in this doc always means the *v1.5.4 requirements backlog* (`Reviews/v1.5.4_backlog.md`). `QPB_v1.7.0_Design.md` (the security design; renumbered from v1.5.11 on 2026-07-20) independently uses B-4/B-5/B-6 for *security* work items. Any cross-doc citation must name the source doc.

---

## 3-4. Features A and B — **moved to v1.6.1**

Both moved verbatim to `QPB_v1.6.1_Design.md` (§2 Feature A, §3 Feature B) on 2026-07-21. Section numbers 3 and 4 are retained here as a stub so §5's numbering stays stable against landed commits and cross-references.

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
4. **Requirement sections — grouped by an organizing principle the derivation *chooses* per system** *(revised 2026-07-21; see "Choosing the organizing principle" below).* The sections are no longer required to be "functional." The derivation selects the organizing principle that best fits *this* system from the IEEE 830 §5.3 menu — by feature/capability, use case/journey, user class/stakeholder, mode/state, object/entity, stimulus-response/interface, or functional hierarchy — states which principle it chose and a one-paragraph rationale at the top of the section list, and orders the sections **most-relevant-to-the-primary-reader first** (the generalization of the old user-facing → infrastructure rule; for a functional grouping the two coincide). Each section carries a **section overview** stating the theme that unifies its requirements under the chosen principle (not a restatement of its REQ titles), and holds **≥2 REQs or a one-line singleton justification, else merged** (fixes C-3). Feature grouping remains the safe **default** when no principle clearly fits — but the choice, and its rationale, must be stated even then.
5. **Non-functional sections** — Feature A's NFR REQs grouped by `nfr_class`.
6. **Cross-cutting concerns** — Phase E.3, mandatory when >1 functional section.
7. **Use cases** — unchanged content, cleaned render (no HTML comments — C-5).
8. **Traceability appendix** — rendered reverse index UC→REQ, plus REQ→BUG links carrying final FP-audit dispositions. One-way REQ→UC in the manifest is unchanged; the appendix is render-time derivation, which `schemas.md` already sanctions.
9. **Glossary / definitions** — *advisory, added 2026-07-20.* Terms of art used by the requirements, defined once. Modeled on IEEE 830 §1.3 (superseded by ISO/IEC/IEEE 29148; cited as lineage, **not** as a conformance claim), which carries a glossary because terminology drift is a top requirements-defect class — and terminology stability is exactly what the readability rubric's *Consistent* dimension scores. **WARN only, never a gate FAIL**, on the F-1 precedent: a missing glossary is a signal, not a failure.

#### §5.2 ↔ enforcement traceability

*Added 2026-07-20. Every part above maps to the mechanism that enforces it, or is marked judgment-only. **A part may not be added to §5.2 without adding a row here.*** This exists because prose-that-should-agree is not a binding: §5.3 enumerated six checks while §5.2 mandated eight parts, nothing connected them, and a structurally flat document passed three self-Council rounds. The glossary reproduced the drift within hours of the first fix — landing in the generation guide while this section still listed eight parts. This matrix is the same spec-versus-implementation control `QPB_v1.6.0_Requirements_Readability_Rubric.md` argues for, applied to §5.2↔§5.3.

| §5.2 part | Enforced by | Severity |
|---|---|---|
| 1. Header / generator stamp | §5.3 check 6 (stamp == single version source) | FAIL |
| 2. Overview | §5.3 check 3 (Overview present) | FAIL |
| 2a. — F-1 coverage-and-gaps statement | F-1 check (non-empty gaps statement) | **WARN** (§8: never a gate FAIL) |
| 3. Actors & roles | MP-1 (mandatory-part presence) | FAIL |
| 4. Functional sections — singleton merge-or-justify; section intro prose | §5.3 check 3 | FAIL |
| 4a. — requirements live inside functional sections | MP-2 | FAIL |
| 4b. — **organizing principle named + rationale present + per-section unifying overview** | render contract (presence only, not quality) | FAIL if absent |
| 4c. — **ordering most-relevant-first; whether the *chosen* principle is optimal** | **judgment-only** — Feature D Stage 1 + rubric *Well-organized* | none |
| 5. Non-functional sections | **not yet enforced** — Feature A (Track 2); render slot degrades gracefully until then | none |
| 6. Cross-cutting concerns | §5.3 check 3 (cross-cutting present) | FAIL |
| 7. Use cases | MP-1 | FAIL |
| 8. Traceability appendix | MP-1 | FAIL |
| 9. Glossary / definitions | glossary check | **WARN** (structurally incapable of FAIL; source-guarded + mutation-bitten) |

Supporting checks not tied to a single part: §5.3 check 1 (REQ IDs sequential), check 2 (tool-contract split — no `quality/`-only REQ here, all in `RUN_CONTRACT.md`), check 4 (no HTML comments / derivation vocabulary), check 5 (title ≤120 chars, no terminal period), MP-3 (quoted headings are not structure).

#### The render contract must fail closed on a manifest-vs-render marker mismatch *(added 2026-07-21)*

Every check above reads `### REQ-NNN:` headings in `REQUIREMENTS.md`. If the render carries **no** such headings, the contract currently goes inert (INFO, "not a contract-shaped render, render contract skipped"). That is **fail-open**, and a 2026-07-21 smoke test showed the consequence: two independent weak-model runs rendered requirements as `**REQ-NNN:**` (bold) instead of `### REQ-NNN:` headings, the whole contract skipped, and a document carrying the exact C-3 singleton-section defect Feature C exists to catch shipped **unflagged**.

The root cause was an instruction-architecture gap (the format rule lived in `requirements_pipeline.md` but the generator is routed to `phase2_generation_guide.md`, which never stated it — fixed separately). But the contract must not depend on the generator getting the marker right, because the manifest already proves whether requirements exist:

- **If `requirements_manifest.json` holds ≥1 product REQ records but `REQUIREMENTS.md` carries zero `### REQ-NNN:` headings, that is not "not applicable" — it is a render that failed to present its requirements in contract shape. FAIL, not INFO-skip.** This follows the contract's own existing precedent: an unterminated code fence already FAILs with "refuse to certify rather than pass by default." A populated manifest with an unparseable render is the same situation.
- The existing wrong-heading-*level* WARN (`## REQ-NNN:` etc.) stays. The new rule closes the remaining fail-open path: markers absent entirely while the manifest says they should exist.
- A genuinely empty manifest (zero product REQs) still skips — there is nothing to render, and that is correctly "not applicable."

**Two rows are deliberately unenforced and should stay visible rather than be quietly closed:** 4b (section ordering) is judgment the rubric scores, and 5 (NFR sections) lands with Feature A. Anything else appearing without a mechanism is a defect in this matrix.

*Why order most-relevant-to-the-primary-reader first:* the spec's first consumer is an operator deciding whether the derivation captured intent (Feature D); they recognize what matters to them before internals. Implementers, who prefer architectural ordering, read the References fields anyway. (The 2026-07-19 resolution fixed this as literal "user-facing → infrastructure"; the 2026-07-21 revision generalizes it — see §12 and the reversal record.)

#### Choosing the organizing principle (a Phase E reorganization pass)

*Added 2026-07-21. This is the substance of item 4 above.* A requirements document is only as legible as its grouping, and **there is no single right grouping** — IEEE 830 §5.3 lists a menu of organizing principles and states plainly that the best one depends on the system, not on a house style. The pre-2026-07-21 design imposed one principle (functional sections) on every target; a 2026-07-21 smoke test showed the cost — on `bus-tracker` the derivation mixed four grouping axes (functional, interface, cross-cutting, architectural) without ever *choosing* one, because it was slotting requirements into a mandated scheme rather than deciding how this system's requirements should be organized.

**The pass.** After the requirements exist but **before Phase 2 ends**, the derivation runs an explicit reorganization step (an enrichment of `references/requirements_pipeline.md` Phase E, ahead of the E.6 renumber):

1. **Assess the system** — what kind of thing is it? A workflow (favours use-case/journey grouping), a multi-actor system (user-class/stakeholder), a protocol or API surface (stimulus-response/interface), a capability library (feature), a stateful device (mode/state), a domain model (object/entity).
2. **Choose one organizing principle** from the IEEE 830 §5.3 menu (feature · use case · user class · mode · object · stimulus-response/interface · functional hierarchy · a justified combination). Default to **feature** only when no principle clearly fits.
3. **Regroup** the requirement records under that principle. Records do not change shape — only their `functional_section` assignment and the section grouping change (this is the same manifest-write-back the renumber already performs; extend it to the regrouping).
4. **Write a section overview per section** — one short paragraph naming the theme that unifies that section's requirements under the chosen principle. This is what Feature D's Stage 2 validates section by section.
5. **State the choice** — at the top of the section list, name the principle and give a one-paragraph rationale ("organized by *user journey* because this is a workflow system whose requirements cluster around the stages a user moves through").
6. **Order + renumber** — sections most-relevant-to-the-primary-reader first, then the E.6 sequential renumber.

**Mechanical vs. judgment.** The render contract (§5.3) checks only that a principle is *named*, that a *rationale* is present, and that each section carries a unifying *overview* — it does **not** judge whether the choice is optimal. Whether the derivation picked the *right* principle is a Feature D interview question (Stage 1 plays the choice back to the operator) and a Phase 4 Council *Well-organized* rubric item. Mechanical checks structure; judgment checks quality — the same division the rest of Feature C uses.

### 5.3 Render contract — mechanical checks in `quality_gate.py` (fixes C-2, C-5, C-7 and pins 5.1/5.2)

> **This list is not the complete check set** *(clarified 2026-07-20)*. The six checks below cover C-2, C-5, C-7 and the 5.1/5.2 pins. They do **not** cover every mandatory part §5.2 requires: Actors & roles, Use cases, and the Traceability appendix have no check here. Implementing only this section leaves a structurally flat document passing the gate — which is exactly what happened during instruction 001, where a flat document survived three self-Council rounds before the omission was caught. The landed implementation therefore adds MP-1/MP-2/MP-3 (mandatory-part presence, requirements-live-inside-functional-sections, quoted-headings-are-not-structure) beyond the six. Treat §5.2 as the authority on *what must exist* and this section as a partial enumeration of *what is mechanically checked*. **The binding between them is the §5.2↔enforcement traceability matrix**, added 2026-07-20 — consult it rather than reconciling these two prose lists by eye, and add a row there whenever a part or a check changes.

1. REQ IDs strictly sequential in document order (Phase E.6 renumber becomes enforced, not aspirational).
2. No REQ whose References point exclusively into `quality/` (5.1).
3. Overview section present and non-empty; every functional section has intro prose; singleton sections carry a justification line.
4. No HTML comments; no derivation-internal vocabulary in the rendered body (deny-list seeded with `Asymmetry-promotion`, `cluster:`, pass names — the metadata lives in the manifest).
5. REQ title ≤ 120 characters, no terminal period (mechanical proxy for noun-phrase discipline; the real judgment lives in the Council rubric).
6. Generator stamp equals the single-source version (C-7 regression pin, mutation-bitten by hardcoding a stale stamp).

Every check lands with the AUDIT-table invariant-test pattern (`DEVELOPMENT_PROCESS.md` §"AUDIT-table"): sweep the render path, document verdicts, pin with mutation tests.

### 5.4 Intent-form requirements (fixes C-6)

Phase B/C derivation and the render both enforce: a REQ states **intended behavior**; observed divergence text moves to the BUG record with a link from the traceability appendix. Mechanically, the renderer rejects conditions-of-satisfaction text matching divergence-report shapes only via Council rubric (this is judgment, not regex); the *pipeline* change is a prompt-level rule in Phase B/C plus a Phase 4 Council rubric item: "does any REQ narrate a defect rather than state a contract?"

**Verification (Feature C overall).** *(b) and (c) corrected 2026-07-20 — both previously over-claimed; see the notes.*

(a) Unit: each render-contract check mutation-bitten.

(b) **Coherence acceptance oracle.** Two halves, and **there is no deterministic regeneration regression test**: (i) mechanical — the render-contract checks pass on the chi, express, and virtio fixtures with C-1…C-7 absent; (ii) judgment — a scored cross-family readability Council per `QPB_v1.6.0_Requirements_Readability_Rubric.md`.

> *Correction.* This previously read "re-render … through the new renderer," which presumed a deterministic renderer. **None exists and none is being built** — `REQUIREMENTS.md` is agent-authored prose following `references/`, which is QPB's premise, not a gap. The consequence must be stated rather than glossed: **the fixtures are golden files, so a regression in the reference-doc prose cannot fail the suite.** The rubric's drift-scoring is the compensating control — but it is **not yet functional as one**: it has exactly one scored run, in which one of six dimensions returned unusable scores (a four-point spread on a single cell) and had to be respecified. It needs a variance baseline before it can detect drift. Until then the honest claim is "mechanical checks pass and a Council read it," not "the coherence oracle passed."

(c) **Manifest-change invariant.** For a fixed input, `requirements_manifest.json` changes **only** in the fields this Design mandates — `id` (E.6 renumber), `title` (§5.4 intent-form), `functional_section` (§5.2 merge), and `conditions_of_satisfaction` where a title rewrite displaces normative text into it. Record count, and each record's `references` list and its attachment to its own record, are preserved exactly, enforced field-by-field through a committed `renumber_map.json`.

> *Correction.* This previously read "unchanged modulo the renumber map … proving Feature C is presentation-layer." That is **measurably false** — records identical modulo `id` are chi 11/16, virtio 8/17, **express 0/16** — and it contradicts §5.2 and §5.4, which mandate title and section rewrites. Feature C is presentation-layer **plus mandated title/section/CoS rewrites**; the earlier phrasing overstated the safety of the change. The formulation above is authoritative and matches the Implementation Plan Phase 1 and the enforcing test.

**Dependencies.** None on A/B (render slots for NFR sections degrade gracefully to absent). Feature D consumes the new render. Touches `references/requirements_pipeline.md` (Phase E hardening), `references/phase2_generation_guide.md`, the renderer path, `quality_gate.py` — all via the diagnosis→Claude Code lane.

## 6. Feature D — The requirements validation interview (fitness-for-purpose)

**Problem.** QPB verifies that code conforms to derived requirements but never validates that the derived requirements are the right ones — the missing link in the Juran chain (§0 #4). Nothing confirms the derived requirements against what the operator actually intended. The 2026-05-02 worked example (`Reviews/QPB_v1.6.x_Requirements_Review_Worked_Example_2026-05-02.md`) proved a 10-minute interactive session surfaces real defects (projected-vs-measured mismatch, glossary drift, benchmark double-count, hardcoded-enumeration coupling) that no autonomous pass caught. The 8-dimension proposal (`QPB_v1.6.x_Requirements_Review_Proposal.md`) designed the full system but was repositioned out of v1.6.0; meanwhile a lighter walkthrough **already shipped** in v1.5.7 (`quality/REVIEW_REQUIREMENTS.md` + `REFINE_REQUIREMENTS.md`, guided/self-guided/cross-model modes, progress in `REFINEMENT_HINTS.md`) — which the proposal never acknowledges. v1.6.0 reconciles the two.

**Design — MVP slice of the 8-dimension proposal, superseding the shipped walkthrough.**

- **Shape — progressive, broad strokes first, drill-down on demand.** The Feature C document architecture is the interview's outline; the interview descends it:
  - **Stage 1 — validate the narrative *and the organizing principle*.** The agent plays back its understanding at the top of the document: "here's what I think this system is, who it serves, and what its major behavioral areas are — is that right?" (Overview, actors & roles, section themes, and the F-1 coverage-and-gaps statement: "here's what I believe I did not cover — intentional?"). **It also plays back the organizing principle it chose** (§5.2): "I organized these requirements by *user journey* because this is a workflow system — is that the right lens, or would grouping by *stakeholder* fit how you think about it?" The organizing choice is itself a high-yield fitness-for-purpose question — a wrong lens makes every section feel slightly off — and it is cheapest to correct here, before Stage 2 descends the sections. Most fitness-for-purpose defects (wrong system, wrong actor, missing area, **wrong organizing lens**) surface here.
  - **Stage 2 — validate sections and use cases.** Section by section, in reader-relevance order: the agent reads the section's **unifying overview** (§5.2 item 4) and asks whether that theme is a real, cohesive concern of the system — "this section groups everything about X; is X how you'd carve up the problem?" — then its use cases. "This section says the system guarantees X under Y — is that what it's *supposed* to do?" The section overviews exist precisely so this stage has a coherent unit to validate rather than a bare list.
  - **Stage 3 — per-REQ drill-down, operator-pulled.** Individual REQs are examined only where Stage 1/2 surfaced doubt or where the operator steers ("show me the redirect requirements"). Breadth-first by default; depth is never pushed.
  - Three moves at every stage, in the operator's control: **confirm** (recorded as evidence — see F-2), **correct** (operator states what it should say — covers merges, splits, and rewording; the derivation absorbs the correction), **add** (operator names behavior the derivation missed). Plus **drop** and **defer**. *(The proposal's six structural dispositions — `tighten-prose`, `merge-with-related-REQ`, `split-into-multiple-REQs`, etc. — are folded into **correct**; per-attribute disposition taxonomy was inspection-tool ceremony for an MVP.)*
- **Elicitation content:** questions drawn from the 34 catching questions in `Reviews/Requirements_Miss_Archeology.md` (highest-yield five first: artifact-category fit, artifact-shape, judgment-vs-comparison, self-encoding, operator-vs-gate success) and the four worked-example question classes (outcome verification, terminology disambiguation, identity/independence, dependency tracing) — mapped to stages: category/shape questions belong to Stage 1, dependency/identity questions to Stages 2-3.
- **Write-back is the point:** corrections and additions land in the **manifest** (not just the render) as new/updated REQ records carrying `source_type: operator-confirmation` (F-2), then the Feature C renderer re-renders — so the spec absorbs corrections coherently instead of accreting patch notes. A surgical re-derivation of a corrected REQ (the proposal's iterate-until-clean, Dimension 3) is in scope only as "re-run derivation for this REQ with the operator's correction as evidence"; full loop tooling waits.
- **Renumber is the interview's terminal step, not a deferral** *(added 2026-07-21).* An `add` move inserts a REQ into an existing section; keeping document-order IDs sequential (the §5.3 contract) would then renumber REQs the operator just confirmed *by ID*, mid-conversation. The resolution is **not** to defer the renumber (a 2026-07-21 test showed all three targets deferred it and shipped out-of-order IDs — e.g. express rendered `…013, 035, 014…`): it is to run the Phase E.6 renumber **once, as the final step after the operator finishes all moves**, atomically updating every cross-reference in the same pass — `use_cases[]`, UC `requirements[]`, and **`operator_confirmations.jsonl` `req_id` fields** included. The operator never sees IDs shift during the conversation; the final document is sequential and every confirmation still resolves. (F-2a already keys cross-*run* durability on requirement content, not ID, precisely because E.6 renumbers each run — the same principle applies within the interview.)
- **Artifacts:** `quality/REQUIREMENTS_REVIEW.md` defect log (by Wiegers attribute + disposition); transcript preserved to `quality/review_sessions/<TIMESTAMP>-<topic>.md` behind an explicit operator save-gate (the proposal's privacy concern). Inspection metrics (Dimension 8) and the QI-loop synthesis (lessons-learned → calibration hypotheses) stay in the later slice, as the proposal already sequenced.
- **Deferred from the proposal to post-v1.6.0:** Dimension 2 (multi-perspective lens), Dimension 5's informal-source corpus + `informal-spec` role tag, Dimension 8 metrics, the QI-loop closure.
- **Supersession:** the interview replaces `REVIEW_REQUIREMENTS.md`/`REFINE_REQUIREMENTS.md` generation (one system, not two); their guided/self-guided/cross-model modes are preserved as interview entry modes.
- **Placement — offered after Phase 2, before Phase 3** *(operator decision 2026-07-21; reverses the earlier "playbook-end summary offers it" placement).* The requirements are complete at the end of Phase 2. Phases 3–6 then *consume* them — tests, code review focus, spec audit, and TDD are all derived from the requirements. Offering validation only at the end (the slot inherited from the superseded v1.5.7 walkthrough, which was a review-*after*-the-run tool) means every downstream artifact was built on unvalidated requirements, so an operator correction at the end leaves them stale. Validation is a fitness-for-purpose gate on the spec, and a spec is validated *before* you build on it. So the playbook offers the interview at the Phase 2 → Phase 3 boundary, with explicit operator-facing messaging: the requirements are done, they can be validated now before the rest of the run depends on them, and the offer is opt-in (never auto-started). A run that declines is reminded once at playbook-end that validation is still available — discoverability is preserved without moving the primary offer back to the end. *Why this is safe for the fitness-for-purpose purpose:* the interview validates the requirement text (Complete / Consistent / Verifiable), which needs no downstream evidence; the only thing an early offer forgoes is REQ→BUG context in the traceability appendix (bugs are found in Phases 3–5), which is not load-bearing for "are these the right requirements."

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

#### F-2a — Cross-run durability of operator confirmations *(added 2026-07-20)*

**The hazard, stated plainly.** Interview corrections land in `requirements_manifest.json`. QPB re-derives that manifest on every run. With F-3 dropped, the only surviving obligation is that a re-derivation must not discard an `operator-confirmation`-backed REQ **within the same run** — across runs, nothing protects it. Concretely: an operator spends thirty minutes correcting a spec, re-runs QPB the following week, and the corrections are silently gone. That is a bad product outcome sitting inside the release's headline feature, and the Design should not ship it unremarked.

**Decision (operator, 2026-07-20): persist without resolving identity.** Losing the operator's work and solving cross-run REQ identity are *different problems*, and only the first needs solving now.

- **Artifact:** `quality/operator_confirmations.jsonl` — **append-only**. Derivation never rewrites it; a run that would delete or truncate it fails the gate.
- **Each record carries** the REQ's *content* at time of confirmation (title + conditions of satisfaction, not merely an identifier), the operator's statement verbatim, an ISO date, and a citation into the preserved session transcript per F-2's transcript-as-citable-source machinery.
- **Deliberately not keyed on REQ id.** Phase E.6 renumbers every run, so an id is meaningless across runs — this run's REQ-005 is not last run's REQ-005. Any later matching is content-based and **advisory**.
- **Read path:** where a later run finalizes the manifest, it reads the file and reports — *"N operator-confirmed requirements from prior sessions; K appear absent from this derivation"* — quoting the operator's original words.
- **Surface, never auto-merge.** Automatic re-application would require exactly the cross-run identity resolution this defers. The goal is to convert **silent data loss into a prompt**.

**What this explicitly does not solve.** Cross-run REQ identity (RM-008's cardinality-loss problem) stays deferred with F-3, and needs its own design doc. This is the cheap 80%: the operator's work survives and is surfaced, but re-applying it is a human decision.

**Verification.** A fixture run that confirms a REQ, then re-derives, must (a) still have the `.jsonl` intact and (b) report the prior confirmation. Mutation: a derivation path that truncates or overwrites the file fails the fixture.

**Consequence for Feature D's build:** this changes *where the interview writes* — manifest **and** the append-only artifact — so it is in scope for the Feature D slice, not a later retrofit.

### F-3 — Re-run spec diff (**dropped from v1.6.0**, 2026-07-19)

Dropped per the simplicity pass (resolves former OD-6). The problem is real — re-runs can silently drop operator-confirmed REQs — but REQ identity across runs is its own hard design problem (RM-008's cardinality-loss lesson applies) and serves neither organization nor validation directly. One narrow obligation survives into Feature D's scope: **a re-derivation must not silently discard an `operator-confirmation`-backed REQ within the same run** (the interview's write-back is durable for the run that produced it). Cross-run protection waits for its own design doc; sketch preserved in the 2026-07-18 revision (git history).

---

## 9. Slices and sequencing — two independent tracks

**Track 1 — the release's goal (organization → validation), strictly ordered:**

- **Slice 1 — Coherence (Feature C + 5.1's RUN_CONTRACT split + F-1's Overview slot).** First because it is self-contained, has a crisp acceptance oracle (the chi/express/virtio regeneration fixture), and the interview walks its output — a progressive interview over a jumbled document is not possible. *(Resolves former OD-1: coherence-first, by dependency rather than preference.)*
- **Slice 2 — Validation (Feature D MVP + F-2).** The interview fixture + the re-run 2026-05-02 worked example.

**Track 2 — moved out 2026-07-21.** Slices 3 and 4 (Features A + B) are now `QPB_v1.6.1_Design.md`. This release is Track 1 only, so the two-track structure below reduces to a single ordered track.

Post-v1.6.0 (unchanged from prior planning): interview Dimensions 2/5/8, QI-loop closure (needs calibration infra), Feature E's B-4 (first point-release candidate), mechanical F-1 hardening, cross-run spec diff, SPC (**v1.8.0** — renumbered from v1.7.0 on 2026-07-20 to free that slot for the security line; its design docs are stale twice over and need a rewrite before use: they still describe v1.6 as the Requirements Review release, **and** they declare a dependency on "v1.5.5 orchestration infrastructure," a release that was cancelled — the 1.5.x line ended at 1.5.4 before jumping to 1.6.0).

**Track-coupling note (now one-directional).** Feature A's NFR sections render into Feature C's document architecture (§5.2 item 5). Feature C ships the render slot specified to degrade gracefully in both directions, and it is already in the tree. Because Track 1 now lands first by construction, the "whichever lands second runs the other's fixture suite" rule applies only to v1.6.1, which runs this release's fixture suite before merging.

## 10. Success criteria

1. **Coherence oracle:** the chi/express/virtio fixtures exhibit none of C-1…C-7; all render-contract checks pass and are mutation-bitten; the cross-family readability Council returns Ship with no rubric dimension ≤2 on any document. *(Corrected 2026-07-20 — no deterministic re-render exists; see §5 Verification (b). This criterion is satisfied by mechanical checks plus scored judgment, not by a regression test.)*
2. *(Precision oracle — moved to `QPB_v1.6.1_Design.md` §4 on 2026-07-21. Numbering held so landed references stay valid.)*
3. **Validation oracle:** the Feature D fixture session runs all three stages, round-trips confirm/correct/add into the manifest and a clean re-render; artifacts (defect log, transcript) gate-validated.
4. *(NFR acceptance criteria — moved to `QPB_v1.6.1_Design.md` §4 on 2026-07-21.)*
5. F-1 coverage-and-gaps statement present in the Overview on every run, and exercised by interview Stage 1.
6. No recall collapse anywhere: bin/tests + gate green dual-env; QPB self-audit REQ coverage not reduced.

## 11. Out of scope for v1.6.0

**Features A and B (Track 2 precision scope)** — moved to `QPB_v1.6.1_Design.md`, 2026-07-21. Everything below is unchanged from the 2026-07-19 pass.

Interview Dimensions 2/5/8 and QI-loop closure; Feature E (B-4/B-5/B-6/B-7 — point-release candidates, B-4 first); mechanical F-1 surface enumerators; F-3 cross-run spec diff; control charts / SPC (v1.7.0); new benchmark targets or runners; skill-surface routing (`--surface`, own proposal); bug-report PR automation (own proposal); Phase-6 structural enforcement (own proposal).

## 12. Open decisions

**Still open:** none for this release. OD-5 moved to `QPB_v1.6.1_Design.md` §5 on 2026-07-21 (it gates that release's Phase 6). OD-8 is resolved and stays here, with its framing corrected for the split — see below.

- **OD-5 — moved to `QPB_v1.6.1_Design.md` §5** (2026-07-21). It gates that release's Phase 6 and is no longer a v1.6.0 release-time decision.
- **OD-8 — 090j band-aid disposition. RESOLVED: retain, as a mechanical backstop beneath Feature B.** Not retired, not folded away. Rationale: **(a)** it is empirically proven — the 2026-05-24 OpenFGA channel Mode-A run recorded four confirmed bugs each carrying `reachability_analysis`, two FP-class candidates demoted via reachability, and zero confident-HIGH security false positives; **(b)** it is deterministic and free (gate checks, no LLM call), whereas Feature B's FP-audit is LLM judgment and therefore variable — a mechanical floor under a judgment layer is the correct architecture, not redundancy; **(c)** it is defense in depth: if the fresh-context audit is skipped, degraded, or unavailable, D1/D2/D3 still catch advisory-only findings. Feature B's rubric restates D1/D2/D3's substance (reachability, CVE version-range applicability, source-of-truth), so the two overlap by design; the `check_v1_5_7_090j_triage_precision` gate checks and the `reachability_analysis` field requirement **stay**. Release notes should describe 090j as a retained mechanical guardrail rather than a superseded band-aid. **Framing correction, 2026-07-21:** this resolution was written for a release containing Feature B, and describes 090j as a floor *beneath* a judgment layer. With Track 2 moved to v1.6.1, there is no layer above it — 090j is v1.6.0's **only** precision guard. The resolution to retain it holds and is strengthened by the split; the release notes must not describe a layer this release does not ship.

**Resolved** (recorded for traceability):

- *2026-07-19 simplicity pass:* former OD-1 → coherence-first, by dependency (§9); OD-4 → deleted with F-1's slimming; OD-6 → F-3 dropped; OD-9 → user-facing→infrastructure ordering, no override flag (a flag is complexity with no observed demand); OD-10 → defer unification, document the seam in the Implementation Plan (B-5's departure removes the immediate pressure on it).
- *2026-07-21 revision (partial reversal of the OD-9-era "functional sections" mandate):* §5.2 item 4 no longer imposes functional grouping on every target. The derivation now **chooses** the organizing principle from the IEEE 830 §5.3 menu and states its rationale (see "Choosing the organizing principle"). What is *kept* from the 2026-07-19 resolution: the ordering rule (now generalized from "user-facing → infrastructure" to "most-relevant-to-the-primary-reader first"), and "no override flag" — the derivation chooses, the operator validates the choice in the Feature D interview rather than setting a flag. **Rationale:** a 2026-07-21 smoke test showed a single mandated principle produces mixed-axis grouping because the derivation slots rather than decides; IEEE 830 §5.3 explicitly holds that the best organizing principle is system-dependent. This is a deliberate scope addition to Feature C, recorded here so it does not read as contradicting OD-9 silently. Implemented via runner instruction 006.
- *2026-07-19 pre-handoff (Decision Record #7):* OD-2 → skill-protocol chat; OD-3 → transcript-as-citable-source; OD-7 → `quality/RUN_CONTRACT.md`.

## 13. Council review plan

Per `DEVELOPMENT_PROCESS.md`, pre-implementation Council of briefs is over-engineering; the load-bearing reviews run on landed code. Proposed review points:

1. **This design doc (optional, cheap):** a focused single-panel sanity pass on §5's render contract and §6's write-back model — the two places a wrong design decision is expensive to unwind. Not a nested Council.
2. **Slice 1 landed:** worker self-Council (3 panelists: render-contract correctness incl. mutation coverage; regeneration-fixture fidelity against C-1…C-7; regression safety on manifest semantics) + a focused readability review of the three regenerated fixture docs.
3. **Slice 2 landed:** worker self-Council on manifest write-back correctness, interview-artifact gate compliance, and supersession completeness (no orphaned REVIEW_REQUIREMENTS.md generation path left behind).
4. *(Slice 3 Council — moved to `QPB_v1.6.1_Design.md` §7 on 2026-07-21.)*
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
