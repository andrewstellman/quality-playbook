# Quality Playbook v1.6.0 — Implementation Plan

*Companion to: `QPB_v1.6.0_Design.md` (canonical, rewritten 2026-07-18, simplicity pass + pre-handoff decisions 2026-07-19).*
*Status: rewritten **2026-07-19** to match the current design. Supersedes the 2026-05-24 plan (NFR+FP-audit-only scope, old slice order — preserved in git history) and the original lever-pull plan before it.*
*All open decisions that gate implementation are resolved (Design §0 Decision Record #7); the two remaining ODs (OD-5 precision bar, OD-8 090j disposition) are release-time and marked at their phase gates below.*

---

## Operating Principles

- **The design doc is the spec.** This plan sequences and gates; it does not pre-decompose. The implementing AI (Claude Code / Opus-class worker) reads `QPB_v1.6.0_Design.md` end-to-end and decomposes during execution, per `ai_context/DEVELOPMENT_PROCESS.md` (no per-phase briefs).
- **Two independent tracks.** Track 1 (Phases 1-4: coherence → validation) is the release's goal and is strictly ordered by dependency. Track 2 (Phases 5-7: precision, Features A+B) is independent and may run in parallel with Track 1 or after it. Phase 8 (release) requires both.
- **The manifest stays the source of truth.** Feature C is presentation-layer except where explicitly specified; Phase 1 carries a manifest-unchanged invariant. The FP-audit consumes the manifest, never the rendered document.
- **Three acceptance oracles, all fixture-grounded:** the chi/express/virtio regeneration fixture (coherence, Design §5), the scripted interview fixture + re-run 2026-05-02 worked example (validation, Design §6), the OpenFGA re-run (precision, Design §4 — carried unchanged).
- **Independence is load-bearing for the FP-audit** (carried): the audit sub-agent gets finding + cited source + relevant derived REQ + rubric — never the running skill, phase prompts, or writeup reasoning.
- **Source edits go through the diagnosis→Claude Code lane** per workspace CLAUDE.md; this plan and the design doc are the Cowork-editable planning surface.
- **Branch + ship discipline carries over:** fresh `1.6.0` branch, base SHA recorded; never push from a sandbox; verify every remote claim with `git ls-remote`; no wall-clock estimates anywhere.

---

## Phase 0 — Base confirmation (operator gate)

Goal: a clean, explicit base for the `1.6.0` branch.

- **Satisfied 2026-07-19.** The prior release line is closed out: `v1.5.10` is tagged (`4cb6781`), merged to `main` (`646b703`), and `1.6.0` is branched from it — all verified on origin. v1.5.10 was deliberately **not** published to PyPI/npm (the GitHub↔registry trusted-publisher interop was never wired); publishing resumes at 1.6.0, gated on the P1–P12 carry-forwards in `~/Documents/AI-Driven Development/Quality Playbook/QPB_Carry_Forward_To_1.6.0.md`. The security line is design-only and renumbered **v1.7.0** (from v1.5.11, 2026-07-20); SPC moved to v1.8.0.
- `1.6.0` branch cut from that base; base SHA recorded in the branch's first commit message.
- The three coherence fixture inputs preserved read-only: the `repos/{chi,express,virtio}-1.5.8/quality/` manifests + rendered REQUIREMENTS.md (the C-1…C-7 evidence). The OpenFGA run fixtures per the 2026-05-24 plan remain the precision oracle inputs.

Gate to Phase 1 (and Phase 5): branch cut confirmed; fixture trees preserved; worker session launched with the minimal-prompt handoff pointing at the design doc, this plan, and workspace CLAUDE.md.

---

# Track 1 — Coherence → Validation

## Phase 1 — Slice 1: spec organization & coherence (Feature C + F-1 slot)

Goal: the rendered REQUIREMENTS.md becomes a contract-checked, coherent document; tool-contract REQs relocate; the coverage-and-gaps statement gets its Overview slot.

Work items (worker decomposes; Design §5 is the spec):

- **RUN_CONTRACT split (Design §5.1):** artifact-layout invariants render to `quality/RUN_CONTRACT.md`; REQUIREMENTS.md contains zero REQs whose References point exclusively into `quality/`. Gate enforces both (presence there, absence here).
- **Document architecture (Design §5.2):** the eight-part canonical shape (header with accurate stamp / Overview incl. F-1 gaps statement / actors & roles / functional sections user-facing→infrastructure, ≥2 REQs or justified / NFR sections slot (degrades gracefully until Track 2 lands) / cross-cutting concerns / use cases / traceability appendix). Phase E of `references/requirements_pipeline.md` becomes unconditional; E.5 ordering and E.6 renumber become enforced. `references/phase2_generation_guide.md` updated to carry the architecture.
- **Render contract in `quality_gate.py` (Design §5.3):** the six mechanical checks, each landed with the AUDIT-table invariant-test pattern and mutation-bitten. Plus the F-1 check: Overview contains a non-empty coverage-and-gaps statement.
- **Intent-form rule (Design §5.4):** prompt-level rule in the derivation passes + Phase 4 Council rubric item; no new mechanical check (judgment, not regex).
- **Manifest-change invariant** *(corrected 2026-07-20 — the original wording said "unchanged modulo the renumber map", which Design §5.2 and §5.4 directly contradict by mandating title and section rewrites; measured, records identical modulo `id` are chi 11/16, virtio 8/17, **express 0/16**)*: for a fixed input, `requirements_manifest.json` changes **only** in the fields the Design mandates — `id` (E.6 renumber), `title` (§5.4 intent-form), `functional_section` (§5.2 merge), and `conditions_of_satisfaction` where a title rewrite displaces normative text into it. Record count, and each record's `references` list and their attachment to their own record, are preserved exactly. Enforced field-by-field through a committed `renumber_map.json`, never by a set comparison (a set check survives both gutting every record and rotating `references` onto the wrong records). Test pins it.

Tests: mutation-bite every render-contract check (re-introduce each defect class; gate must FAIL); manifest-unchanged test; fixture re-render smoke test.

Gate to Phase 2: all checks land dual-env green; SKILL.md token ceiling respected (architecture detail lives in references/, not SKILL.md).

## Phase 2 — Slice 1 acceptance + Council

- **Regeneration fixture (the coherence oracle):** re-render the chi, express, and virtio manifests. Acceptance: C-1…C-7 all absent — mechanically (contract checks pass on all three) and by judgment (the readability Council below).

  *Note (2026-07-20): "through the new renderer" presumed a deterministic renderer that does not exist and is not being built. `REQUIREMENTS.md` is agent-authored prose following `references/` — that is QPB's premise, not a gap. Consequence, recorded: the fixtures are golden files, so a regression in the reference-doc prose cannot fail the suite. Mitigation is the readability Council plus prevention at source in the generation guide — landed via **runner instruction 002** (render-contract hardening), not Phase 3 and not a renderer. **The Council is not yet a functional drift detector:** one scored run exists, one of its six dimensions returned unusable scores and was respecified, and a variance baseline is required before scores can gate. Until that baseline exists, the honest claim is "checks pass and a Council read it."*
- **Worker self-Council** (3 panelists, per Design §13): render-contract correctness incl. mutation coverage; regeneration-fixture fidelity against C-1…C-7; regression safety on manifest semantics. FIX-REQUIRED iterates in-branch before the review-request files.
- **Readability Council — the judgment half of the oracle** *(specified 2026-07-20; the Design required it but never defined it)*. Scored against **Wiegers requirements quality attributes**, not an ad-hoc scale, so Phase 4's `REQUIREMENTS_REVIEW.md` defect log and Feature D's interview inherit one vocabulary: **complete / consistent / unambiguous / verifiable / well-organized**, plus **honest-about-gaps** (F-1 statement accuracy; a gaps statement that misdescribes scope is worse than none, per the virtio "outside the checkout entirely" finding). Each dimension scored 1–5 with behavioral anchors and a `REQ-NNN` citation per cell. Rubric: `docs/design/QPB_v1.6.0_Requirements_Readability_Rubric.md`.

  **Ground truth is the project's documentation, never its implementation.** Judging requirements against code is circular — every bug becomes a requirement and coverage is perfect by construction, which defeats the tool's purpose. Source may be read to check whether a requirement is *stated verifiably*, never to decide whether it is *correct*.

  **Cross-family reviewers required.** The fixtures are agent-authored; a judge from the generating model family inflates scores (documented self-enhancement bias). Run the external three-terminal Council (`gpt-5.4`, `gpt-5.3-codex`, `claude-sonnet-4.6`), not worker sub-agents.

Gate to Phase 3: oracle satisfied; self-Council synthesis SHIP; readability Council returns Ship, with no dimension ≤2 on any document.

## Phase 3 — Slice 2: the validation interview (Feature D + F-2)

Goal: the fitness-for-purpose interview, as a skill-protocol chat, with durable write-back.

Work items (Design §6 + §8 F-2 are the spec; delivery shape and evidence shape resolved per Design §0 #7):

- **Interview protocol reference** (`references/requirements_interview.md` or worker-chosen equivalent name in references/): the three-stage progressive protocol (narrative → sections/use-cases → per-REQ on demand), the five moves (confirm/correct/add/drop/defer), elicitation content mapped from the 34 catching questions + the four worked-example question classes, the Stage-1 gaps-statement playback. Entry modes carry over from the shipped walkthrough (guided / self-guided / cross-model).
- **Write-back:** corrections/additions land in the manifest as REQ records; re-render through the Feature C renderer after the session. A re-derivation within the run must not silently discard an `operator-confirmation`-backed REQ.
- **Evidence (F-2):** `source_type: operator-confirmation` + citation into the preserved transcript (transcript-as-citable-source; §5.4 machinery applies). `schemas.md` extended; gate validates the shape.
- **Artifacts:** `quality/REQUIREMENTS_REVIEW.md` defect log (by Wiegers attribute + move); transcripts to `quality/review_sessions/<TIMESTAMP>-<topic>.md` behind an explicit operator save-gate.
- **Supersession:** the interview replaces `REVIEW_REQUIREMENTS.md`/`REFINE_REQUIREMENTS.md` generation — no orphaned generation path remains; the playbook-end summary offers the interview, never auto-starts it.

Tests: scripted fixture session against the QPB self-derivation (test-double operator issues one confirm, one correct, one add) — manifest updated with correctly-shaped records, re-render passes the render contract, artifacts gate-validated. Mutation: a correction that never reaches the manifest fails the fixture. Sweep test: no remaining generator of the superseded walkthrough files.

Gate to Phase 4: fixture green dual-env; schemas + gate green.

## Phase 4 — Slice 2 acceptance + Council

- Re-run the **2026-05-02 worked example** (`Reviews/QPB_v1.6.x_Requirements_Review_Worked_Example_2026-05-02.md`) as a semi-scripted acceptance walkthrough through the new protocol.
- **Worker self-Council:** manifest write-back correctness; interview-artifact gate compliance; supersession completeness.

Gate: walkthrough produces stage-appropriate questions and durable corrections; self-Council SHIP. **Track 1 complete.**

---

# Track 2 — Precision (independent; parallelizable with Track 1)

## Phase 5 — Slice 3: NFR discovery + FP-audit core (Features A + B)

Carried from the 2026-05-24 plan in substance; Design §3-§4 are the spec.

- **Feature A:** `nfr_class` + mandatory `acceptance_criterion`/`verification_method` in `schemas.md` + manifests (backward-compatible; functional REQs unchanged). **Manifest record-shape divergence — resolved 2026-07-20: tolerate, do not normalize.** The three benchmark manifests carry three different record shapes while all declaring `schema_version: 1.5.8` (chi: `text`, no `title`; express: `title`/`tier`/`conditions_of_satisfaction`/`specificity`; virtio: `title`/`tier_label`/`source`/`formal_doc_refs`, no CoS). `nfr_class` and the mandatory NFR fields must be **additive and shape-tolerant** — read defensively, never assume a sibling field exists, never rewrite an existing record's shape. A normalization pass is out of scope for v1.6.0; derivation of core classes (security, reliability, performance) with evidence tracing; the grounding rule (advisory/CVE with no derived-NFR violation → `KNOWN-ISSUE`); categorization-tier state confirmed in code before extending (incl. the B-13 reconcile note); gate FAILs aspirational NFRs (mutation-bitten). NFR sections render into the Feature C architecture (or the pre-C render if Track 2 lands first — the render slot degrades gracefully in both directions).
- **Feature B:** the fresh-context FP-audit pass post-triage / pre-finalization; core rubric (reachability, applicability incl. CVE version-range, source-of-truth, requirements-traceability); security highest-scrutiny; verdicts CONFIRMED / DEMOTED / RECLASSIFIED-KNOWN-ISSUE / UNCERTAIN with preserved transcript; independence sealed and verified; the `confirmed-open (integration-harness-required)` disposition admissible only on FP-audit CONFIRM; new dispositions narrated via the 090v verdict-explanation framework.

Tests: gate tests for NFR fields; derivation fixture (OpenFGA contextual-tuple restriction → derived REQ-SEC with acceptance criterion); FP-audit fixtures (BUG-003 → DEMOTED, BUG-006 → DEMOTED/RECLASSIFIED, BUG-009 → RECLASSIFIED-KNOWN-ISSUE, BUG-001/002/004 → CONFIRMED); one non-security demotion fixture (generality).

Gate to Phase 6: fixtures green; independence verified (auditor demonstrably lacks skill/writeup context).

## Phase 6 — Slice 3 acceptance: the OpenFGA re-run

- Re-run Mode-A against the preserved OpenFGA fixture tree with NFR discovery + FP-audit active. **⚠ Resolve OD-5 (the HIGH-precision bar) before this gate.**
- Acceptance: BUG-003/006/009 cannot stand as confirmed HIGH; BUG-001/002/004 still surface; precision ≥ bar; no genuine finding suppressed. Run output + audit transcripts preserved as acceptance evidence.

## Phase 7 — Slice 4 breadth + precision Council

- Remaining NFR classes (usability, portability, maintainability, interop); full FP-audit rubric (design-intent, compensation, severity-justification); per-run precision metrics.
- **Nested 3×3 Council** (per Design §13 item 4): NFR derivation testability, FP-audit independence (the fabrication-tell check), grounding rule, OpenFGA regression. Standard acceptance checks on responses (real source reads, three inner verdicts per outer file, convergence flags).

Gate: Council Ship within 3 cycles or HALT + recalibrate. **Track 2 complete.**

---

## Phase 8 — Release v1.6.0 (both tracks complete)

- Version stamps from the single version source (SKILL.md frontmatter per v1.5.10 consolidation); channel package versions.
- README + CHANGELOG: v1.6.0 framed as the requirements release — coherent contract-checked specs, the fitness-for-purpose validation interview, NFR grounding + FP-audit precision, with the regeneration + OpenFGA results as headlines.
- **⚠ Resolve OD-8 (090j disposition)** and reflect it in the release notes.
- Whole-surface umbrella Council; then the standard close-out sequence per `DEVELOPMENT_PROCESS.md` (Andrew tags; scripted publish gates; verify-before-claiming on every remote ref).

---

## Documented seam (from resolved OD-10)

The code-path Phase A–E pipeline (`references/requirements_pipeline.md`) and the skill-derivation four-pass (`bin/skill_derivation/`) both produce REQs under the `schemas.md` REQ record but via different machinery. v1.6.0 does **not** unify them. Implementers touching either side must apply Feature A's schema extension and Feature C's render contract to **both** producers' outputs (the render contract checks the rendered document, so it covers both mechanically; the derivation-prompt changes must be applied per-pipeline). Unification is deferred work with no assigned version.

## Out of scope (per Design §11)

Interview Dimensions 2/5/8 + QI-loop closure; Feature E (B-4 first point-release candidate); mechanical F-1 enumerators; F-3 cross-run diff; SPC (**v1.8.0** — renumbered from v1.7.0 on 2026-07-20; docs stale on two counts and need a rewrite, see Design §9); skill-surface routing; bug-report PR automation; Phase-6 structural enforcement.

## Risks and mitigations

- **Render contract over-fires on exotic-but-legitimate documents** (a repo where a singleton section is right, or 120-char titles are natural). Mitigation: singleton-justification escape hatch is part of the contract; title cap is a cap, not a style enforcer; regeneration fixture spans three different repo shapes.
- **Interview scope creep** (the protocol grows toward the full 8-dimension proposal mid-build). Mitigation: the MVP boundary is explicit in Design §6 ("Deferred from the proposal"); the self-Council's supersession/compliance charters check against it.
- **Write-back corrupts the manifest** (an operator correction lands mis-shaped). Mitigation: gate validates all post-session records; the mutation fixture pins the write-back path; re-render must pass the render contract after every session.
- **FP-audit too aggressive / not actually fresh-context / cost** — carried unchanged from the 2026-05-24 plan (acceptance oracle protects recall; independence is a phase-gate item; scope starts at HIGH/MED if cost bites).
- **Tracks collide at the render slot** (Track 2's NFR sections vs Track 1's architecture landing in either order). Mitigation: the NFR render slot is specified to degrade gracefully in both directions (Phase 5 work item); whichever lands second runs the other's fixture suite before merging.
