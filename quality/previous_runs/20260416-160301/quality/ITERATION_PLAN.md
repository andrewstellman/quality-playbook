# Iteration Plan — Gap Strategy + Unfiltered Strategy
<!-- Quality Playbook v1.4.1 — Gap Iteration + Unfiltered Iteration — 2026-04-16 -->

**Strategy:** gap
**Iteration number:** 2 (first iteration after baseline)
**Date:** 2026-04-16

---

## Coverage Map (Baseline EXPLORATION.md)

Built by reading section headers and first 2–3 lines of each section.

| Section | Subsystems Covered | Findings | Depth |
|---------|-------------------|----------|-------|
| Domain and Stack | SKILL.md overview, quality_gate.sh summary, no external deps | Architecture baseline | Shallow |
| Architecture | 5 components: SKILL.md, quality_gate.sh, references/, ai_context/, version history | Data flow, major subsystems | Moderate |
| Existing Tests | Absence of tests; empirical benchmarking | No test coverage gap | Shallow |
| Specifications | Self-referential nature of SKILL.md | Internal consistency rules | Shallow |
| Open Exploration Findings | 10 findings: quality_gate.sh (lines 697, 88–91, 123–126, 278–283, 32), SKILL.md (Phase 2 gate, mechanical dir, Mandatory First Action, Gate Self-Check, version stamp) | 5 quality_gate.sh bugs, 5 SKILL.md spec gaps | Deep (function-level traces) |
| Quality Risks | 7 risks: JSON false positives, version cross-reference, artifact contract drift, --all MODE empty VERSION, Phase 0b context, incremental write tension, TDD log validation ordering | Risk analysis complete | Moderate–Deep |
| Pattern Applicability Matrix | 3 FULL (Fallback/Degradation, Dispatcher Return-Value, Cross-Implementation Consistency), 3 SKIP | Coverage of 6 patterns | Deep |
| Pattern Deep Dive — Fallback and Degradation Path Parity | Repo resolution (3-level fallback), Phase 0a/0b seed discovery | Multi-path analysis | Deep |
| Pattern Deep Dive — Dispatcher Return-Value Correctness | json_has_key, json_str_val, json_key_count return values | Input combination tables | Deep |
| Pattern Deep Dive — Cross-Implementation Contract Consistency | Phase 1 gate vs Phase 2 entry gate (12 vs 6 checks), artifact contract table vs gate checks | Cross-doc comparison | Deep |
| Candidate Bugs for Phase 2 | 7 bugs: BUG-H1, BUG-H2, BUG-M3, BUG-M4, BUG-M5, BUG-L6, BUG-L7 | 2 HIGH, 3 MEDIUM, 2 LOW | Deep |
| Derived Requirements | REQ-001 to REQ-008 | 8 requirements | Moderate |

---

## Gap Identification

### Subsystems NOT explored or explored shallowly:

1. **Phase 7 (Present, Explore, Improve)** — The interactive phase (SKILL.md ~lines 2057–2155) was NOT analyzed. Phase 7's requirements, interactive flows, and the "end-of-phase message" rules were not examined for spec completeness or correctness.

2. **Recheck Mode** — The recheck mode section (SKILL.md ~lines 1918–2055) was NOT analyzed in the baseline. This is a distinct execution mode with its own schema (`recheck-results.json` with `schema_version: "1.0"`), its own procedure, and its own spec contracts. The baseline bugs BUG-L10 identified the `schema_version: "1.0"` inconsistency but only shallowly — the full recheck spec was not audited.

3. **integration-results.json validation in quality_gate.sh** — The gate checks `integration-results.json` at lines 389–436. The baseline exploration covered TDD sidecar JSON in depth but only briefly mentioned integration JSON. The gate's integration JSON checks have NOT been audited for completeness against SKILL.md's integration schema spec.

4. **Benchmark 47 (test file extension)** — The `ls ${q}/test_functional.*` pattern at quality_gate.sh line 479 uses the same vulnerable `ls`-glob pattern as BUG-M8, but this instance was NOT confirmed as a separate bug in the baseline. The baseline noted it but it wasn't traced to its own bug report.

5. **The `ai_context/TOOLKIT.md` and `ai_context/DEVELOPMENT_CONTEXT.md` files** — These were listed as documentation but NOT explored for consistency with SKILL.md. TOOLKIT.md may contain claims that conflict with the current SKILL.md version. DEVELOPMENT_CONTEXT.md's "known issues" list was not cross-checked against confirmed bugs.

6. **Quality gate recommendation enum** — The gate checks that `recommendation` in `integration-results.json` uses canonical values (SHIP/FIX BEFORE MERGE/BLOCK), but SKILL.md's integration schema says `"SHIP IT"`, `"FIX FIRST"`, `"NEEDS INVESTIGATION"` — a different set! This was not analyzed.

7. **The `--all` mode behavior** — The `CHECK_ALL=true` branch (quality_gate.sh lines 677–680) was mentioned in Risk 4 but not deep-read. The glob `*-"${VERSION}"/` and the consequence of a missing VERSION were only partially traced.

8. **SKILL.md Phase 2 artifact generation instructions** — Specifically the integration-results.json schema and recommendation enum values defined in SKILL.md's file 4 (RUN_INTEGRATION_TESTS.md template) vs what quality_gate.sh checks.

---

## Targeted Deep-Read Plan

For the 3 thinnest/most gap-rich sections, I will do a targeted deep read:

1. **Recheck Mode (SKILL.md lines ~1918–2055)** — Read the full recheck spec, focusing on schema_version "1.0" vs "1.1", and whether the gate validates recheck artifacts.

2. **quality_gate.sh integration-results.json section (lines 389–436) vs SKILL.md recommendation enum** — Compare gate's accepted values with SKILL.md's generated protocol values.

3. **ai_context/TOOLKIT.md** — Read for claims about SKILL.md behavior that might conflict with current spec.

---

## Gap Exploration Focus Areas

- **Finding A:** Integration recommendation enum inconsistency (gate vs SKILL.md)
- **Finding B:** Recheck mode schema_version "1.0" inconsistency with SKILL.md spec
- **Finding C:** test_functional.* ls-glob in gate line 479 (same pattern as BUG-M8)
- **Finding D:** TOOLKIT.md/DEVELOPMENT_CONTEXT.md claims vs SKILL.md
- **Finding E:** Phase 7 end-of-phase message completeness
- **Finding F:** `--all` mode VERSION empty behavior
- **Finding G:** Integration-results.json per-group fields validation completeness in gate

---

## Parity Iteration Note (Iteration 4)

**Strategy:** parity
**Iteration number:** 4 (third iteration after baseline, following gap and unfiltered)
**Date:** 2026-04-16

**Prior findings from all prior iterations already confirmed:**
- BUG-H1 through BUG-M18 (18 confirmed bugs total)

**18 confirmed bugs total before this iteration**

**Approach:** Parity strategy — systematically enumerate parallel implementations of the same contract and diff them for inconsistencies. Looking for code paths that should behave the same way but don't. Findings will go to quality/EXPLORATION_ITER4.md.

### Parallel Groups Identified for Parity Comparison

**Group PG-1: JSON helper functions — parallel validation patterns**
- `json_has_key` (quality_gate.sh:75-78): grep for key name anywhere in file
- `json_str_val` (quality_gate.sh:81-85): grep for key with string value pattern
- `json_key_count` (quality_gate.sh:88-91): grep for key:value pairs with count
- Comparison: do they handle the same edge cases consistently? Missing keys, non-string values, nested values?

**Group PG-2: Artifact existence checks — multiple detection patterns in gate**
- File existence: `[ -f "${q}/${f}" ]` at lines 107-121 (for BUGS.md, REQUIREMENTS.md, etc.)
- Functional test existence: `ls` glob at line 124 (vulnerable — BUG-M16)
- code_reviews content: `ls` glob at line 143 (vulnerable — BUG-M13)
- spec_audits triage/auditor counts: `ls` glob at lines 152-153 (vulnerable — BUG-M8)
- Patches count: `ls` glob at lines 567-568 (vulnerable — BUG-M8)
- Writeups count: `ls` glob at line 595; but loop uses `[ -f "$wf" ]` guard at line 598
- Comparison: do all existence checks use consistent, robust patterns?

**Group PG-3: Per-bug TDD log checking vs. per-bug patch checking**
- TDD log check (lines 316-345): iterates `bug_ids`, uses `[ -f ... ]` for red/green logs
- Patch check (lines 566-568): counts ALL patches in patches/ dir using ls glob, not per-bug iteration
- Comparison: per-bug vs. aggregate counting — do they use the same pattern? Different patterns have different failure modes.

**Group PG-4: SKILL.md phase entry gates vs. phase exit gates**
- Phase 1 exit gate (SKILL.md:846-862): 12 numbered checks on EXPLORATION.md content
- Phase 2 entry gate (SKILL.md:897-904): only 6 section-title checks — already confirmed as BUG-M3
- Phase 4 exit gate (SKILL.md:1550): triage file + individual auditor files
- Phase 5 exit gate (SKILL.md:1609-1648): multiple mandatory checks
- Comparison: do exit gates from one phase match entry gates of the next?

**Group PG-5: tdd-results.json sidecar — two templates in SKILL.md**
- Template 1 (SKILL.md:126-147, artifact contract section): requirement as UC-NN, red/green as prose
- Template 2 (SKILL.md:1376-1408, Phase 5 section): requirement as REQ-NNN, red/green as enum values
- Gate validation (quality_gate.sh:239-265): checks field PRESENCE, not format
- Comparison: which template does the gate enforce? Are the templates consistent with each other?

**Group PG-6: SKILL.md's artifact contract table vs. quality_gate.sh's checked artifacts**
- SKILL.md artifact contract (lines 88-119): 18 rows including recheck artifacts
- Gate file existence checks (lines 107-177): checks ~11 artifacts
- Missing from gate: recheck-results.json, recheck-summary.md, TDD_TRACEABILITY.md
- Comparison: parity between what SKILL.md says is required and what gate actually enforces

---

## Unfiltered Iteration Note (Iteration 3)

**Strategy:** unfiltered
**Iteration number:** 3 (second iteration after baseline, following gap)
**Date:** 2026-04-16

**Prior findings from Iteration 2 (gap) already confirmed:**
- BUG-M12: quality_gate.sh:479 — ls-glob in test file extension detection
- BUG-M13: quality_gate.sh:143 — ls-glob in code_reviews directory check
- BUG-L14: references/review_protocols.md:410 — wrong recommendation enum values
- BUG-M15: quality_gate.sh (absence) — no recheck validation in gate

**15 confirmed bugs total (BUG-H1 through BUG-M15)**

**Approach:** Unfiltered strategy — pure domain-driven exploration with no structural constraints, no pattern templates, no applicability matrices. Exploring what a domain expert finds suspicious when reading the code fresh. Findings will go to quality/EXPLORATION_ITER3.md.

---

## Adversarial Iteration Note (Iteration 5)

**Strategy:** adversarial
**Iteration number:** 5 (fourth iteration after baseline, following gap + unfiltered + parity)
**Date:** 2026-04-16

**Prior confirmed bugs: 22 total (BUG-H1 through BUG-L22)**

**Approach:** Adversarial strategy — re-investigate what previous iterations dismissed, demoted, or marked SATISFIED with a lower evidentiary bar. A code-path trace showing semantic drift is sufficient to confirm. "Permissive behavior" is not automatically a design choice. Sources: (a) Demoted Candidates from EXPLORATION_MERGED.md, (b) triage.md dismissals, (c) pass2_requirement_verification.md SATISFIED verdicts, (d) adjacent code around confirmed bugs.

---

### (a) Demoted Candidates with Re-Promotion Criteria

| DC | Title | Source | Re-Promotion Criteria | Current Status |
|----|-------|--------|-----------------------|----------------|
| DC-001 | Date comparison lexicographic | Iter 1 | Show valid ISO 8601 date fails bash `>` comparison | DEMOTED — mathematically impossible for YYYY-MM-DD |
| DC-002 | Mechanical verification doesn't adapt to bash | Iter 1 | Show agent incorrectly creates mechanical/ for bash project | DEMOTED — design ambiguity, correct implementation |
| DC-003 | Phase 7 iteration vs baseline ambiguity | Iter 2 | Show iteration run shows Phase 7 menus incorrectly | DEMOTED — minor doc clarity |
| DC-004 | TOOLKIT.md stale phase count | Iter 2 | Show agent reads TOOLKIT.md as primary instruction, follows wrong 6-phase procedure | DEMOTED — TOOLKIT.md defers to SKILL.md explicitly |
| DC-005 | Code review summary vocabulary | Iter 2 | Show agent copies Markdown recommendation into integration JSON | DEMOTED — separate artifacts, no cross-contamination path |
| DC-006 | Date comparison lexicographic (Iter 3 re-eval) | Iter 1+3 | Same as DC-001 | DEMOTED confirmed false positive |
| DC-007 | Arg parser ${@+"$@"} idiom | Iter 3 | Show incorrect argument handling in real bash/zsh | DEMOTED — correct idiom |
| DC-008 | Verdict regex includes deferred | Iter 3 | Find verdict value spec says valid but gate rejects | DEMOTED — gate regex correct |
| DC-009 | wrong_headings nested grep | Iter 3 | Show specific input where nested grep gives wrong count | DEMOTED — logic correct for ## headings |
| DC-010 | "deferred" absent from templates | Iter 4 | Show agent generates deprecated "skipped" verdict due to template omission | DEMOTED — prose documentation covers it |
| DC-011 | Per-bug vs aggregate count structural gap | Iter 4 | Show reg_patch_count >= bug_count but specific bug missing patch | DEMOTED (promoted to BUG-L20) |

### (b) Additional Dismissed Triage Findings

From triage.md dismissals (baseline Phase 4):
- "code_reviews/ partial session not detected" — dismissed as "Design decision"
- "General mode WARN vs FAIL for probes" — dismissed as "Design decision"
- "Date staleness not checked" — dismissed as "Acceptable gap"
- "EXPLORATION.md min-lines not gate-checked" — dismissed as "Accepted risk"
- "Fix patch requirement Phase 3 vs Phase 4 gap" — dismissed as "Design gap — low severity"
- "VERSION grep-m1 fragile" — dismissed as "Accepted risk"

### (c) Candidates Not Promoted to Confirmed Bugs

From EXPLORATION.md candidate list: All promoted. From iterations 2-4: all 11 candidates became confirmed bugs.

### (d) Thin SATISFIED Verdicts from Pass 2

| Requirement | Status | Evidence Depth | Challenge |
|-------------|--------|----------------|-----------|
| REQ-011 | SATISFIED | Single citation to REQUIREMENTS.md lines 1-434 | Thin — "reviewed all 14 requirements" without per-requirement verification |
| REQ-013 | SATISFIED | Single citation to SKILL.md line 578 and PROGRESS.md | Moderate — checked that no mechanical/ directory exists |

---

### Key Adversarial Targets

**Target 1:** Re-examine integration-results.json validation in quality_gate.sh — per-group field validation and summary sub-key validation are absent. The parity iteration found tdd-results.json summary sub-keys (BUG-L19) but did NOT check the parallel integration-results.json summary sub-keys.

**Target 2:** Re-examine REQ-011 SATISFIED verdict — was the requirements pipeline verification genuinely thorough or did it rely on surface-level checks?

**Target 3:** Re-examine triage dismissal "code_reviews/ partial session not detected" — dismissed as design choice, but the spec_audit.md explicitly says partial sessions must produce FAILED gate entries. Is the code_reviews check at line 143 (already BUG-M13, nullglob) the root of this dismissed finding?

**Target 4:** Re-examine EXPLORATION.md min-lines not gate-checked (dismissed as "accepted risk"). The Phase 2 entry gate at SKILL.md:897-904 enforces 6 section title checks but not the 120-line minimum substantive content check. Is this the same as BUG-M3 or a distinct gap?

Findings will go to quality/EXPLORATION_ITER5.md.

