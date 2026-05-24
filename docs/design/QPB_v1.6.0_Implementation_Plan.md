# Quality Playbook v1.6.0 — Implementation Plan

*Companion to: `QPB_v1.6.0_Design.md`*
*Status: reframed **2026-05-24** to the **NFR discovery + requirements-grounded FP-audit** feature. This supersedes the original "single lever pull" implementation plan (preserved at the bottom as historical context). Begins after v1.5.7 ships and clears a few clean new-repo runs.*
*Depends on: v1.5.7 published (pip + npm) and stable; the 090j triage band-aid in place (this feature supersedes it at the requirements level); the OpenFGA Mode-A run preserved at `repos/openfpa-1.5.7/quality/` as the regression fixture.*

> **What changed and why.** The pre-2026-05-24 plan below built v1.6.0 as a lever-pull workflow release. v1.6.0's canonical scope is now the **NFR discovery + requirements-grounded false-positive audit** feature, motivated by the 2026-05-23 OpenFGA precision failure (0/3 HIGH real, Council-confirmed in 090i). This plan is the sliced build plan for that feature. The lever-pull plan is preserved verbatim at the bottom for lineage.

---

## Operating Principles

- **The OpenFGA re-run is the acceptance oracle.** v1.6.0 is not done until a fresh Mode-A run against `repos/openfpa-1.5.7/` (or a re-cloned equivalent) demonstrates that BUG-003 / BUG-006 / BUG-009 cannot stand as confirmed HIGH bugs, while BUG-001 / BUG-002 / BUG-004 still surface. Precision up, recall held.
- **Two coupled pieces, built in dependency order.** (A) NFR discovery is the requirements-layer fix; (B) the fresh-context FP-audit is the catch-all precision gate. (A) lands first because the audit's requirements-traceability check depends on NFRs being derived.
- **The FP-audit is general, not security-only.** Word every prompt/rubric so the audit covers all finding classes (the failure mode — a finding the producing agent didn't independently re-check — is class-agnostic). Security is the highest-scrutiny tier, not a separate detector.
- **Independence is load-bearing.** The audit sub-agent must run fresh-context: no running skill, no phase prompts, no writeup reasoning — only finding + cited source + relevant derived REQ + rubric. If the audit can see the producing agent's rationalization, it inherits the bias that produced the FPs.
- **Source edits go through the diagnosis→Claude Code lane.** Per workspace CLAUDE.md, Cowork proposes diffs and hands them to the worker; this plan describes the *what*, the worker implements. `docs/design/` planning content (this file) is Cowork-editable.
- **Branch + ship discipline carries over from v1.5.7.** Fresh `1.6.0` branch from the v1.5.7 release tag as base; never push from the sandbox; verify any remote claim with `git ls-remote`.

---

## Phase 0 — v1.5.7 ship + run-series confirmation

Goal: confirm v1.5.7 is published and precision-stable enough that v1.6.0 has a clean base.

Work items:
- v1.5.7 tagged + published on PyPI and npm; the four-ref dance complete; `git ls-remote origin v1.5.7` confirms the tag.
- The 090j triage band-aid (reachability note / KNOWN-ISSUE classification / security-HIGH bar) is landed and its OpenFGA regression fixtures pass (003/006/009 not confirmable HIGH under the same-agent rules).
- A few clean Mode-A runs across new repos (language/channel matrix) — the run-series Andrew gates v1.6.0 start on.
- The OpenFGA run output is preserved read-only as the v1.6.0 regression fixture (BUGS.md, writeups, results logs, and the cited `internal/`/`pkg/` source).

Gate to Phase 1: v1.5.7 tag confirmed on origin; run-series clean; `1.6.0` branch cut fresh from the v1.5.7 tag (record base SHA).

---

## Phase 1 — Slice 1A: first-class NFR discovery (core classes)

Goal: QPB's Phase 1/2 derivation derives **security, reliability, performance** NFRs as first-class, testable REQs.

Work items (worker, via diagnosis→Claude Code lane):
- Extend the REQ record schema (`schemas.md` + the manifests) with an `nfr_class` tag and **mandatory** `acceptance_criterion` + `verification_method` fields for NFR REQs. Confirm backward-compat with existing functional REQ records (functional REQs unchanged).
- Extend the skill-derivation passes (Pass A/C in the skill-derivation pipeline) to derive NFR records for the core classes, each tracing to evidence (code / formal docs / exploration) the same way functional REQs do.
- Encode the **grounding rule**: an NFR finding is confirmable only if it traces to a derived NFR and demonstrates a violation of that NFR's acceptance criterion in the audited tree; an advisory/CVE with no derived-NFR violation is `KNOWN-ISSUE`, not `BUG`.
- Reconcile the categorization tier: confirm the current categorization implementation in code (the "Lever 6 categorization tier" withdraw/return history must be grounded in what's actually there) before extending it with `nfr_class`.
- Gate enforcement: `quality_gate.py` FAILs an NFR REQ that lacks an acceptance criterion or verification method (the "aspirational NFR" anti-pattern).

Tests:
- Gate test: NFR REQ missing acceptance criterion / verification method → FAIL; complete NFR REQ → PASS. Mutation-bite each.
- Derivation fixture: a security-relevant code path (e.g. the OpenFGA contextual-tuple type restriction) yields a derived `REQ-SEC` with an acceptance criterion, so a finding can be tested against it.

Gate to Phase 2: core-class NFR derivation lands; gate validates the new fields dual-env; SKILL.md token ceiling respected (rules in references/phase prompts, not SKILL.md).

---

## Phase 2 — Slice 1B: fresh-context requirements-grounded FP-audit

Goal: a QPB-spun fresh-context sub-agent pass that adversarially re-verifies each *confirmed* finding against the derived REQs — the productionized 090i shape.

Work items (worker, via diagnosis→Claude Code lane):
- Add the FP-audit pass after Phase 3/4 triage, at/before Phase 5 finalization, as a fresh-context pass over the confirmed finding set (analogous to the existing Phase-6 A-13 hybrid / Phase-4 Council fresh-context auditors, but a precision gate on *findings*, not artifacts).
- Implement the **Slice 1 rubric checks**: **reachability** (BUG-003 class), **applicability** (incl. CVE version-range — BUG-006 class), **source-of-truth** (located code defect vs advisory restatement → KNOWN-ISSUE — BUG-009 class), and **requirements-traceability** (violates a derived REQ — functional or NFR — or untethered). Security is highest-scrutiny: a HIGH security/auth-bypass finding needs a demonstrated reachable path + (if a CVE is cited) a verified version match, else downgrade/reclassify.
- Enforce **independence**: the sub-agent receives only finding + cited source + relevant derived REQ + compact rubric — NOT the running skill, phase prompts, or writeup reasoning. Document the invocation (which runner/model, how context is sealed).
- **Output**: per-finding verdict (CONFIRMED / DEMOTED / RECLASSIFIED-KNOWN-ISSUE / UNCERTAIN) with reasoning; the confirmed-bug set + precision metrics updated; the audit transcript preserved as a run artifact.

Tests:
- Fixtures from the OpenFGA findings: BUG-003 (reachable guard) → DEMOTED; BUG-006 (no reachable path + CVE n/a) → DEMOTED/RECLASSIFIED; BUG-009 (advisory-only) → RECLASSIFIED-KNOWN-ISSUE. BUG-001/002/004 → CONFIRMED (no over-firing).
- A non-security fixture (reachability or applicability FP in a functional/performance class) → DEMOTED, proving the audit is general.

Gate to Phase 3: FP-audit lands; fixtures pass; independence verified (the sub-agent demonstrably has no skill/writeup context); gate + bin/tests green dual-env.

---

## Phase 3 — Slice 1 acceptance: the OpenFGA re-run

Goal: prove the feature on the motivating case end-to-end.

Work items:
- Re-run QPB Mode-A against OpenFGA (re-clone v1.5.7-equivalent or use the preserved fixture tree) with NFR discovery + FP-audit active.
- Confirm the acceptance oracle: **BUG-003 / BUG-006 / BUG-009 cannot stand as confirmed HIGH bugs** (demoted/reclassified by the audit and/or never confirmed because they violate no derived NFR), **and BUG-001 / BUG-002 / BUG-004 still surface**.
- Record HIGH-severity precision against the defined bar (resolve the bar number — see design Open Questions — before this gate).
- Preserve the run output + audit transcripts as the v1.6.0 acceptance evidence.

Gate to Phase 4: acceptance oracle satisfied; precision ≥ bar; no genuine finding suppressed.

---

## Phase 4 — Council review (Slice 1 surface)

Goal: independent confirmation of the requirements-layer fix + the audit + the regression result.

Work items:
- Nested 3×3 Council (gpt-5.4 / gpt-5.3-codex / claude-sonnet-4.6, each spawning an inner panel), `cd ~/Documents/QPB` so reviewers read live source + the OpenFGA fixture, tee to `Reviews/v1.6.0_responses/`.
- Review scope: (1) NFR derivation produces testable REQs with acceptance criteria; the gate enforces it. (2) The FP-audit runs fresh-context (independence verified, not writeup-fed) and is general, not security-only. (3) The grounding rule routes advisory-only findings to KNOWN-ISSUE. (4) The OpenFGA regression comes out right (003/006/009 not HIGH; 001/002/004 surface) without suppressing genuine findings.
- Acceptance checks on the responses: real source reads (not handoff fabrication), three distinct inner verdicts per outer file, self-doubt-bias and suspicious-convergence flags per workspace CLAUDE.md.

Gate to Phase 5: Council verdict CLOSED/Ship within 3 cycles (else HALT + recalibrate); no blocking findings.

---

## Phase 5 — Slice 2: breadth + completeness

Goal: complete the NFR taxonomy and the FP-audit rubric.

Work items:
- Remaining NFR classes: usability, portability, maintainability, integration/interoperability — same first-class shape (acceptance criterion + verification method).
- Full FP-audit rubric: add **design-intent** (BUG-007/008 class — documented/intentional choice), **compensation** (handled elsewhere — cache/retry/default/validation), **severity-justification** (claimed severity matches a demonstrated impact path).
- Emit inspection/precision metrics per run.
- Tests + a Council pass on the Slice 2 surface.

Gate to Phase 6: full taxonomy + rubric land; metrics emitted; gate + bin/tests green; Council clean.

---

## Phase 6 — Release v1.6.0

Goal: tag and publish v1.6.0.

Work items:
- Version stamps: `bin/benchmark_lib.py::RELEASE_VERSION` → `"1.6.0"`; SKILL.md `version:` stamps; the channel package version (pip + npm) → 1.6.0.
- README + CHANGELOG: v1.6.0 entry framing it as the NFR-discovery + requirements-grounded FP-audit release, with the OpenFGA precision result as the headline.
- Decide the 090j disposition (design Open Question): retire the same-agent triage rules, retain them as a cheap first pass, or fold them into the FP-audit rubric — and reflect it in the release notes.
- Final whole-surface Council review.
- Tag `v1.6.0` on the `1.6.0` branch; publish to PyPI + npm; the four-ref dance; verify `git ls-remote origin v1.6.0` and the published package versions before claiming shipped.

Gate to release: tag confirmed on origin; packages live on both channels (verified, not assumed); Council verdict Ship; no blocking findings.

---

## Slice 3 — QI-loop closure (deferred, depends on calibration infra)

Not part of the v1.6.0 ship. FP-audit + NFR-derivation defect patterns feed calibration cycles (Phase 1/2 prompt tuning). Shares machinery with the Requirements Review proposal's Slice 3; sequence after the regression-replay/calibration infrastructure is operational. Tracked as a later v1.6.x item.

---

## Out of scope (defer)

- The interactive Requirements Review operator UX (the 8-dimension session) — repositioned later v1.6.x point release; it builds on v1.6.0's NFR discovery.
- Autonomous/continuous improvement scheduling (v1.7+).
- Control charts / SPC limits (needs ~20-30 stable observations).
- New levers, benchmark targets, or runners.

---

## Risks and Mitigations

- **Risk: NFR derivation over-fires — asserts aspirational NFRs with weak acceptance criteria, inflating REQ counts.** Mitigation: the gate FAILs an NFR REQ lacking a concrete acceptance criterion + verification method; the OpenFGA re-run guards against recall collapse.
- **Risk: the FP-audit is too aggressive and demotes genuine findings (BUG-001/002/004 class).** Mitigation: the acceptance oracle requires the genuine findings to still surface; tune the rubric toward "show the analysis" not "there must be no defect." Self-halt + recalibrate if legit findings are suppressed.
- **Risk: the audit sub-agent isn't actually fresh-context (leaks the writeup reasoning) and inherits the producing bias.** Mitigation: independence is a Phase 2 gate item — verify the sub-agent has no skill/phase-prompt/writeup context; a writeup-fed audit is a fabrication tell analogous to the cwd-sandbox Council failure.
- **Risk: cost/latency of a fresh-context pass over every confirmed finding.** Mitigation: scope decision in the design Open Questions (all findings vs HIGH/MED only, like 090j); start narrow, widen if cheap.
- **Risk: the categorization-tier reconciliation assumes a withdraw/return state that doesn't match code.** Mitigation: Phase 1 confirms the actual implementation in source before extending it.

---
---

# Historical context (superseded — preserved for lineage)

*The plan below is the original 2026-04-26 "single lever pull" implementation plan. It is no longer canonical; v1.6.0's scope is the NFR feature above. The lever-pull workflow goals were largely absorbed by v1.5.5/v1.5.6 (see the Design doc's superseded-framing section). Kept for reference.*

## (Superseded) Operating Principles

- v1.6.0 is **one lever pull, no more** — exactly one focused change to one of Levers 1-5's home files; multi-lever bundles defeat recall-delta attribution.
- The deliverable is the workflow, not the change; v1.6.0 establishes how v1.6.x releases work.
- The release is governed by the v1.5.4 apparatus (`bin/regression_replay.py` produces the justifying cell.json files).
- Cross-benchmark regression check is mandatory (no recall harm beyond σ on untargeted benchmarks).

## (Superseded) Phases 0–6

- **Phase 0** — v1.5.4 stabilization confirmation (tag on origin, regression_replay end-to-end, Lever_Calibration_Log with 3+ cycles, N≥5 cell, cross-version harness re-queue B-15).
- **Phase 1** — Select the lever pull (promote the best-evidenced calibration cycle; document in `QPB_v1.6.0_Selection_Rationale.md`).
- **Phase 2** — Pull the lever (focused commit on the lever's home file with calibration-cycle + cell.json references).
- **Phase 3** — Validate via regression replay (recall improvement >2σ; cross-benchmark regression check; cell.json under `metrics/regression_replay/`).
- **Phase 4** — Document the release template (`QPB_v1.6.x_Release_Template.md`; reference from IMPROVEMENT_LOOP.md).
- **Phase 5** — IMPROVEMENT_LOOP.md status update (mark Stage C operational; TTP review).
- **Phase 6** — Release (RELEASE_VERSION → 1.6.0; tag + push; verify via git ls-remote).

Council scope was 4 rounds (lever change in isolation; regression measurement; template + loop update; whole-release). Out-of-scope deferred: workflow automation, multi-lever releases, new benchmark targets, hard cadence requirements. Risk register covered misdiagnosed lever pulls (corrective v1.6.0.1), too-lax cross-benchmark check (tighten 2σ→1σ), over-rigid template, wrong cadence expectation, and fast diminishing returns (a feature, not a bug).
