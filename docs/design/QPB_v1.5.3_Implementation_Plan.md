# Quality Playbook v1.5.3 — Implementation Plan

*Companion to: `QPB_v1.5.3_Design.md`*
*Status: refreshed 2026-04-26 — ready for implementation on the fresh 1.5.3 branch (post-misfire reset). Phase 0 reconciled to actual v1.5.1 + v1.5.2 deliverables.*
*Depends on: v1.5.0 complete (schemas.md, tier system, citation verification, disposition field); v1.5.1 complete (Phase 5 writeup hardening, challenge-gate reinforcement, enforce-writeup gate); v1.5.2 complete (bug-family amplification, operational polish, finalizer robustness, INDEX verdict mapping)*

> **Currency-refresh note (2026-04-26):** The earlier draft of this plan was renumbered from v1.5.2 on 2026-04-22 and carried stale Phase 0 references to a v1.5.1 "Phase 4 benchmark validation" surface that did not ship as named. v1.5.1 actually shipped as Phase 5 writeup-hardening (enforce-writeup gate, challenge-gate reinforcement, benchmark re-runs); v1.5.2 then shipped between v1.5.1 and this plan, delivering bug-family amplification, operational polish (challenge-gate iteration coverage, citation-stale invariant #3, finalizer robustness, Phase 6 INDEX verdict mapping). This refresh reconciles Phase 0 to that actual reality and makes the prerequisite state implementable from the fresh branch. Phases 1-8 below are unchanged from the original v1.5.3 design and remain authoritative.

This plan is deliberately more provisional than the v1.5.0 plan. v1.5.0's implementation surfaced the schema and citation-gate constraints v1.5.3 builds on; v1.5.1 and v1.5.2 together surface the writeup-discipline, bug-family, finalizer-robustness, and pacing characteristics of real end-to-end runs, which in turn inform how aggressive the per-pass progress machinery in Phase 3 of this plan needs to be.

---

## Operating Principles

- v1.5.3 builds on v1.5.0, v1.5.1, and v1.5.2, doesn't replace them. The code-project path remains primary; skill-project handling is additive.
- v1.5.3 is the final feature release in the QC half of QPB's quality-engineering arc. After v1.5.3 ships, QPB has a complete operational methodology for both code projects and AI-skill projects. v1.5.4 then builds the QI measurement infrastructure (regression replay machinery), and v1.6.0 begins continuous improvement using that infrastructure. See `IMPROVEMENT_LOOP.md` for the QC/QI distinction.
- Every phase produces a concrete deliverable that can be committed and benchmarked independently.
- The Haiku-generated REQUIREMENTS.md is the success benchmark throughout. At every phase, compare QPB's self-audit output against it. The benchmark is preserved at `~/Documents/AI-Driven Development/Haiku QPB requirements analysis/REQUIREMENTS.md` (2,129 lines, 95 REQ references, 10 use cases).
- No regression on code projects. The five code benchmark repos must continue to work.
- **Disk is the source of truth for every LLM-driven pass.** Any pass that generates requirements, extracts citations, or audits coverage writes its output incrementally to a persistent artifact and advances a cursor in a progress file before moving on. Passes are resumable: killing one mid-run and restarting it continues from the last cursor position, not from scratch. Pass prompts include explicit compaction-recovery instructions (re-read the pass spec, read the progress file, verify continuity against disk, resume from cursor) so that auto-compaction is routine rather than catastrophic. See Phase 3 "Per-pass execution protocol" for the mechanics. This principle is a correctness invariant for skill projects, whose SKILL.md inputs are long enough that single-shot generation degrades under context pressure.

---

## Phase 0 — v1.5.0 / v1.5.1 / v1.5.2 Stabilization Confirmation

Goal: confirm that v1.5.0, v1.5.1, and v1.5.2 are shipped, tagged, and validated against the code-project benchmark suite. v1.5.0's divergence model, tier system, and citation schema are in place; v1.5.1's Phase 5 writeup-hardening + challenge-gate reinforcement are in place; v1.5.2's bug-family amplification + finalizer robustness + INDEX verdict mapping are in place. Benchmark yields from the most recent runs of v1.5.2 against the pinned benchmarks are documented as the v1.5.3 baseline.

Work items:
- All v1.5.0, v1.5.1, and v1.5.2 phases complete per their respective implementation plans
- v1.5.0, v1.5.1, and v1.5.2 tagged and released to origin (`v1.5.0`, `v1.5.1`, `v1.5.2` tags exist on origin)
- Benchmark baselines captured under `previous_runs/v1.5.2/` for chi-1.5.1, virtio-1.5.1, express-1.5.1 — these are the regression baseline v1.5.3 code-project runs compare against
- Variance estimation runs accumulating in the background under `repos/replicate/` (the `v1.5.2_pinned_variance` plan with N=5 per pinned benchmark cell is the first σ data target; not blocking for v1.5.3 implementation but referenced by `IMPROVEMENT_LOOP.md` Stage A)
- The 1.5.3 branch on origin has been reset from main (post-2026-04-26 misfire) with no in-flight v1.5.3 commits beyond what this implementation plan authorizes

Gate to Phase 1: v1.5.2 tag exists on origin; chi/virtio/express benchmarks at v1.5.2 produce yields within ±10% of their v1.5.0 baseline; no pending v1.5.0/v1.5.1/v1.5.2 bugs without dispositions; `1.5.3` branch is fresh from main.

---

## Phase 1 — Project Type Classifier

Goal: implement the Phase 0 project-type classification step that determines Code / Skill / Hybrid.

Work items:
- Add a `classify_project.py` module (or equivalent) that runs before Phase 1
- Heuristic implementation:
  - Check for SKILL.md at repo root
  - Count SKILL.md prose word count vs. total code LOC across repo
  - Check for orchestrator markers (`bin/`, runners, validators)
- Output: `quality/project_type.json` with classification + confidence + rationale
- Classification is writable by the Phase 4 Council if the heuristic is wrong

Test fixtures needed:
- A pure Skill project (prose-only SKILL.md, no orchestrator). If none exists in the benchmark, create a minimal one. Candidate: a stripped-down version of one of the example skills in `AI-Driven Development/Articles/Research/` if any exist, otherwise a synthetic fixture.
- Verify all five code benchmarks classify as Code
- Verify QPB itself classifies as Hybrid

Deliverable: classifier module, project_type.json output, test fixtures, classification verified on entire benchmark suite.

Gate to Phase 2: classification is correct on all known-type projects (5 code, 1 skill fixture, 1 hybrid).

---

## Phase 2 — Schema Extensions

Goal: extend `schemas.md` (from v1.5.0) to support skill-specific concepts without breaking code-project usage.

Extensions needed:
- `REQ.source_type` field: {code-derived, skill-section, reference-file, execution-observation}
- `REQ.skill_section` field: populated when `source_type = skill-section`, names which SKILL.md section the REQ came from
- `BUG.divergence_type` field: {code-spec, internal-prose, prose-to-code, execution}
- `FORMAL_DOC.role` field: {external-spec, project-spec, skill-self-spec, skill-reference}
  - `skill-self-spec` applies when SKILL.md is its own formal document (Skill/Hybrid projects)
  - `skill-reference` applies to files like `exploration_patterns.md`

Precedence rule for Skill/Hybrid: when SKILL.md (skill-self-spec) and a reference file (skill-reference) conflict, SKILL.md wins. This is documented in `schemas.md` as an explicit precedence rule, not left implicit.

Deliverable: updated `schemas.md` with new fields, updated validation in quality gate, no regression on code-project runs.

Gate to Phase 3: all five code benchmark repos pass the updated gate with no changes to their artifacts.

---

## Phase 3 — Skill-Specific Derivation Pipeline (Generate-Then-Verify)

Goal: implement the four-pass derivation architecture for skill projects.

The pipeline separates coverage breadth (Pass A) from citation precision (Pass B–C) from accountability (Pass D). Each pass has a narrow, specific job and a clear contract with the next.

### Per-Pass Execution Protocol

Every pass in Phase 3 obeys the same execution protocol, defined once here and referenced from each pass spec below. This is the mechanical implementation of the "disk is source of truth" operating principle.

**Artifact layout.** For each run, Phase 3 creates a working directory under `quality/phase3/` (or the project's equivalent quality folder):

```
quality/phase3/
  pass_a_drafts.jsonl        # one draft REQ per line; appended as Pass A iterates
  pass_a_progress.json       # section cursor + status
  pass_b_citations.jsonl     # Pass A drafts annotated with citation_excerpt + citation_status
  pass_b_progress.json       # draft-idx cursor + status
  pass_c_formal.jsonl        # formal REQ records with v1.5.0 citation schema
  pass_c_progress.json       # citation-idx cursor + status
  pass_d_audit.json          # {promoted, rejected, demoted_to_tier_5} with rationale per draft
  pass_d_progress.json       # Pass A-idx cursor + status
```

All writes to JSONL files are append-only; all writes to progress.json files are atomic tmp-file-then-rename so the file is never observed in a half-written state.

**Progress file shape (per pass):**

```json
{
  "pass": "A" | "B" | "C" | "D",
  "unit": "section" | "draft" | "citation" | "audit-entry",
  "cursor": <integer; 0-based index of the next unprocessed unit>,
  "total": <integer or null; filled in once total is known>,
  "status": "running" | "paused" | "complete" | "blocked",
  "last_updated": "<ISO-8601 UTC>",
  "notes": "<free-form, optional; used for blocked or paused>"
}
```

The cursor always equals the idx of the next unit that still needs work. It advances only *after* the unit's output has been appended to the pass's JSONL artifact. Restarting a pass reads the progress file, reads the last record in the corresponding JSONL (verifying it matches `cursor - 1`), rolls the cursor back to match disk state on any discrepancy, and resumes. The verify-and-roll-back step is mandatory — stale progress files observed in practice (both in-house summarizer work and in field) always mean disk is further ahead than the progress file, never behind.

**Pass prompt recovery preamble.** Every LLM-driven pass prompt includes the following recovery procedure near the top, as a required block:

> If this session has experienced auto-compaction — you will see a conversation summary where recent tool-call history should be, or a continuation banner — do this before continuing:
> 1. Re-read the pass specification you were given. Do not try to reconstruct it from the compacted summary.
> 2. Read the pass's progress file (`pass_X_progress.json`).
> 3. Read the last record of the pass's JSONL artifact and confirm its idx equals `cursor - 1`. If not, roll the cursor back to match disk state and note the discrepancy.
> 4. Resume the per-unit workflow from the cursor.
> Disk is the source of truth. The conversation is not.

**Batch-size discipline.** Prompts process one unit at a time by default. Grouping multiple units into a single LLM call is permitted only where the unit size is small enough that the grouping cannot meaningfully shift context pressure — and even then, each unit's output is written individually before the next unit is read. No pass writes multiple units to disk in one shot; if that pattern emerges it indicates scripting drift and the pass should be re-scoped.

**Fail-loud thresholds.** Each pass records per-unit wall-clock time in the JSONL record. If observed throughput exceeds an implementation-defined ceiling (candidate: >5 units/minute for Pass A section processing), the pass halts and emits a diagnostic — this is the tripwire for the "scripting instead of summarizing" failure observed in prior summarizer work, where the LLM degrades into templated stub generation. The ceiling is calibrated per pass; the point is to have one, not to tune it perfectly in v1.5.3 Phase 3.

**Restart and idempotency.** A pass that completes cleanly updates its progress file to `status: "complete"` and records total unit count. Downstream passes refuse to start unless the upstream pass's progress shows `complete`. Re-running a completed pass is a no-op unless its artifact is explicitly cleared; this prevents accidental double-run coverage loss.

### Pass A — Naive Coverage

- Iteration unit: one SKILL.md top-level section (or reference-file top-level section) at a time. Pass A walks the section tree in document order, not all at once.
- Section enumeration step (first, before LLM work): parse SKILL.md and each reference file for top-level headings, emit `pass_a_sections.json` listing `{section_idx, document, heading, line_start, line_end, skip_reason}`. Meta sections (Why This Exists, Overview, acknowledgments) get `skip_reason` populated; Pass A still emits a drafts-artifact line for them with `skipped: true` so Pass D can account for every section.
- Section-split rule: any section exceeding the implementation-defined line threshold (candidate: 300 lines) gets split at the next heading level down and each subsection becomes its own iteration unit. This keeps per-unit prompt size bounded. Calibration note: the threshold is for instructional prose (SKILL.md and reference-file content), which is denser per line than generic documentation or code. Initial calibration should start lower rather than higher — a 150–200 line section of operational prose already contains more testable claims than most tuners will intuit from a line count alone. Tune upward if Pass A under-produces REQs per section, downward if it begins degrading into stub output.
- Per-section prompt modeled on the Haiku session: "Given this section of SKILL.md and the surrounding context, produce draft REQs covering every testable claim in the section. High recall; overreach is acceptable because Pass B will filter." The prompt includes the Per-Pass Execution Protocol recovery preamble.
- Output format: machine-parseable JSONL, one draft REQ per line, each with `draft_idx`, `section_idx`, `title`, `description`, `acceptance_criteria`, and `proposed_source_ref` (free-text like "Phase 1 section of SKILL.md"). One JSONL record per draft REQ; sections that legitimately produce zero REQs still emit a single `{section_idx, no_reqs: true, rationale: "..."}` line so Pass D can distinguish "skipped with reason" from "silently missed".
- **Constraint: Pass A MUST NOT produce `citation_excerpt` values.** It can propose source references but not excerpts. Enforced structurally in the output schema (no `citation_excerpt` field).
- **Execution protocol: section-iterative with cursor.** After processing each section, append its draft records to `pass_a_drafts.jsonl`, update `pass_a_progress.json` (cursor = next section_idx), and only then advance. Restart reads the progress file, verifies the last JSONL record's `section_idx` equals `cursor - 1`, and resumes from the cursor. Per-section wall-clock time is recorded; a section that produces more than the throughput ceiling triggers the fail-loud tripwire.
- For small skills (SKILL.md plus reference files below a threshold; candidate: 500 lines total), Pass A may run single-shot over the entire input and skip the cursor machinery. The single-shot-eligibility decision is made at section-enumeration time and logged in the run manifest.
- Prompt engineering: reuse language from the Haiku session that produced the 95-REQ output. Calibrate against Haiku's output structure, but scope each Haiku-style prompt to one section's worth of input.

### Pass B — Citation Extraction

- Iteration unit: one Pass A draft record at a time (driven by `draft_idx`). Pass B is mechanical, not LLM-driven, but still obeys the per-pass execution protocol so that a crash mid-extraction does not require re-running the whole corpus.
- For each draft REQ from Pass A, mechanically search SKILL.md and reference files for supporting text.
- Implementation: grep-based matching on the `acceptance_criteria` field, with fuzzy matching (stemming, tokenization) for robustness.
- Output: append one record to `pass_b_citations.jsonl` per draft, populating `citation_excerpt` where found with `citation_status = verified`; otherwise `citation_status = unverified`, flagged for Pass C to decide. Update `pass_b_progress.json` after each record.
- Reuse v1.5.0's citation extractor — no new machinery.

### Pass C — Formal REQ Production

- Iteration unit: one Pass B record at a time (driven by draft_idx). Output appended to `pass_c_formal.jsonl`; progress cursor updated after each record per the execution protocol.
- Convert each cited draft into a proper REQ record with tier, ID, full v1.5.0 citation schema.
- Disposition logic:
  - `citation_status = verified` → promote to Tier 1, full REQ record
  - `citation_status = unverified`, source is SKILL.md or reference file → Council review; either drafted Pass A overreach (reject) or citation extractor missed it (manual citation or second extraction attempt)
  - `citation_status = unverified`, claim is behavioral (not from any doc) → demote to Tier 5 (inferred), note that no documentation supports it

### Pass D — Coverage Audit

- Iteration unit: one Pass A draft record (by `draft_idx`) at a time. Pass D cross-references each draft against the Pass C formal list to classify it as promoted, rejected, or demoted, and records a rationale per draft. Cursor advances per draft.
- Produce a diff report: Pass A draft list vs. Pass C formal REQ list.
- Every Pass A draft that didn't make it to Pass C must have a recorded rejection rationale. No silent drops.
- Output: `pass_d_audit.json` (consolidated at end-of-pass) with three sections: `promoted` (A→C), `rejected` (with rationale), `demoted_to_tier_5` (with note). Intermediate per-draft decisions also flushed to `pass_d_progress.json.notes` so a crashed Pass D can resume.
- Also produce `pass_d_section_coverage.json`: for every section enumerated in Pass A, report how many drafts it produced, how many were promoted, and whether any drafts are still pending resolution. Any section with zero promoted REQs and no explicit skip-rationale is flagged as a completeness gap.
- Explicit-skip routing: sections that Pass A emitted with `skipped: true` or `no_reqs: true, rationale: "..."` are pre-dispositioned as `intentional-skip` in Pass D's output and excluded from the Council review queue by default. They remain visible in `pass_d_section_coverage.json` for audit, but they do not surface as items requiring human adjudication. The Council inbox stays scoped to items that actually need judgment: rejected drafts, Tier 5 demotions, weak rationales, and unflagged zero-REQ sections. A separate escalation flag exists for the implementer to force a skip into Council review if the rationale looks suspect on spot-check, but this is opt-in rather than default.
- Flagged for Phase 4 Council if rejection rationale is weak or rejection rate > 30%.

### Reference-File Coverage

- Passes A-D repeat over each file in `references/` (or equivalent)
- Cross-reference detection: where SKILL.md names a reference file, extract the reference's actual content and compare claims
- Contradictions flagged as internal divergences (handled in Phase 4 of this plan)

### Completeness Audit

- Every operational section of SKILL.md must produce at least one REQ after Pass D
- Meta sections (Why This Exists, Overview, etc.) are exempt — maintained in a small allowlist
- Orphan sections flagged for Phase 4 Council review

Tuning: distinguishing "operational" from "meta" sections requires prompt engineering. Iterate against QPB's own SKILL.md until orphan set matches human judgment.

Deliverable: four-pass skill-derivation code path with explicit output at each stage, applied to QPB's self-audit, compared to Haiku benchmark.

Gate to Phase 4:
- Pass A draft count within 10% of Haiku's REQ count (coverage parity check)
- Pass C formal REQ count within 50% of Haiku's 95 REQs (intermediate gate; full parity comes after Phase 4)
- Pass D rejection rate documented; every rejection has rationale
- Same 10 use cases covered as Haiku (may have different IDs)
- **All four passes are resumable**: a forced kill-and-restart at any point during Phase 3 continues from the last cursor position and produces byte-identical (or logically-equivalent) final artifacts compared to an uninterrupted run. Verified on QPB's own SKILL.md with at least one mid-pass kill per pass.
- **Every enumerated section has an accounted outcome in `pass_d_section_coverage.json`** — either REQs produced or an explicit skip-rationale. No silent section drops.
- Per-pass progress files reach `status: "complete"` at pass end; downstream passes refuse to start without this signal (verified by deliberately removing an upstream `complete` status and confirming Phase 3 refuses to advance).

---

## Phase 4 — Internal and Prose-to-Code Divergence Detection

Goal: implement static divergence checks for skills.

Work items:
- Internal divergence: for each pair of REQs citing the same document, check if their `citation_excerpt` content supports compatible claims. Contradictions flagged as bugs with disposition `spec-fix`.
- Prose-to-code divergence: for Hybrid projects, scan SKILL.md claims that reference code (e.g., "quality_gate.py runs 45 checks") and cross-check against the actual code. Tool: the Phase 4 Council gets the REQ + the referenced code region + asks "does the code match the prose claim?"
- Output: bugs with `divergence_type = internal-prose` or `prose-to-code`
- Dispositions populated by the Council, not auto-assigned

Test fixtures:
- A SKILL.md with a deliberate internal contradiction (two sections disagreeing on artifact count)
- A Hybrid project with a deliberate prose-to-code divergence

Deliverable: divergence detection implemented, verified on fixtures, verified on QPB's actual self-audit (may find real bugs).

Gate to Phase 5: fixtures correctly flagged; any real divergences found on QPB are triaged (either fixed or dispositioned as known/deferred).

---

## Phase 5 — Execution Divergence Infrastructure

Goal: implement the third divergence category — comparing SKILL.md promises against observed behavior in prior runs — by aggregating existing `quality_gate.py` results across archived runs.

**Scope boundary (strict):** this phase does NOT build an LLM evaluation harness. It does NOT parse unstructured LLM outputs, grade intermediate reasoning, or evaluate semantic quality. It consumes existing structured gate results and recognizes patterns across them. If the work starts drifting into "grading LLM outputs," stop and re-scope.

Work items:
- Gate result loader: read `quality_gate.py` output files from each archived run in `previous_runs/`
- REQ-to-gate-check mapper: for each skill REQ (derived in Phase 3 from SKILL.md sections), identify which gate check(s) implement it. Mapping is authored explicitly in the REQ record, not inferred.
- Pattern aggregator: for each REQ, count pass/fail rate of its associated gate checks across all archived runs
- Divergence reporter: flag REQs where the associated gate check failed in ≥1 of the last K runs (K = 5 by default)
- Output: bugs with `divergence_type = execution`, citing the SKILL.md REQ, the associated gate check, and the archived run IDs where the check failed

What this explicitly does NOT do:
- Does not parse LLM output prose for quality
- Does not re-run any archived runs
- Does not evaluate whether gate-passing runs are "actually good"
- Does not produce statistical confidence intervals on LLM behavior

Confidence handling: a REQ whose gate check failed in 1 of 5 runs is a lower-urgency flag than one that failed in 5 of 5. Failure count reported in the bug record. Gate does not auto-reject on low-failure-count findings but surfaces them for Council review.

Minimum run threshold: if fewer than 3 prior runs exist, execution divergence check runs with a confidence caveat in the bug record. With 0 prior runs, the check is skipped entirely.

Deliverable: execution divergence module scoped strictly to gate-result aggregation, tested against QPB's archived previous_runs, findings triaged.

Gate to Phase 6: at least one real execution divergence surfaced from QPB's bootstrap history (expected based on v1.4.x self-audits known to have had gate failures on skill-related checks).

---

## Phase 6 — Quality Gate Updates

Goal: quality_gate.py enforces skill-project requirements.

New checks to add:
- Skill/Hybrid projects: every operational SKILL.md section has at least one REQ citing it
- Skill/Hybrid projects: every reference file has at least one REQ or is explicitly marked as non-normative
- Hybrid projects: cross-cutting REQs that span SKILL.md and code both populate
- All projects: project_type.json exists and matches actual repo layout

Failure modes output specific file+section references so fixes don't require re-running the full playbook.

Deliverable: updated quality_gate.py, test fixtures for each new failure mode, no regression on code projects.

Gate to Phase 7: gate correctly flags deliberately-broken skill fixtures; all five code benchmarks still pass.

---

## Phase 7 — Full Benchmark Validation

Goal: run v1.5.3 against all five code benchmark repos AND against QPB itself (Hybrid) AND against the skill test fixture (pure Skill).

Expected outcomes:
- **Code projects** (virtio, chi, cobra, express, httpx): bug yields within ±10% of v1.5.0 baseline. No new false positives from skill-specific checks (they shouldn't fire).
- **QPB self-audit** (Hybrid): REQ count and structure at parity with Haiku benchmark (within ±20% of Haiku's 95 REQs, same 10 UCs in some form). Real skill-related bugs surfaced and triaged.
- **Pure skill fixture**: clean run. Section-to-REQ mapping produces expected structure.
- Cross-model consistency: repeating self-audit with claude-opus, claude-sonnet, copilot+gpt produces comparable coverage (within ±20% REQ count, same UC set).

Deliverable: comparison report across all 7 runs (5 code + QPB + skill fixture), cross-model report for self-audit, go/no-go decision for release.

Gate to release: all success criteria from design doc met; no unresolved regressions on code benchmarks.

---

## Phase 8 — Self-Audit Bootstrap

Goal: QPB v1.5.3 audits itself one more time with full v1.5.3 machinery, artifacts committed as bootstrap evidence.

Same pattern as v1.5.0 Phase 8. Any bugs found go to v1.5.3 backlog.

Deliverable: v1.5.3 self-audit complete, artifacts in `quality/` and archived to `previous_runs/v1.5.3/`.

Gate to release: self-audit completes cleanly OR any failures are explicitly dispositioned.

---

## Release

- Tag v1.5.3
- Update release notes citing the Haiku demonstration as originating evidence
- Document the project-type classification as the key v1.5.3 feature
- Start v1.5.3 backlog

---

## Parking Lot (deferred from v1.5.3)

- Runtime skill validation (executing another skill and observing in real time)
- Automatic skill repair (generating SKILL.md prose fixes)
- Skill-to-skill benchmarking
- Non-markdown skill formats (YAML, structured prompts)
- **Semantic execution divergence (LLM evaluation harness).** Catching cases where gate checks pass but the LLM ignored the spirit of an instruction. Requires building an eval harness — parsing unstructured LLM outputs, grading intermediate reasoning, computing statistical reliability. Out of scope for v1.5.3; revisit for v1.6+ or as a separate tool.

---

## Risk Register

| Risk | Likelihood | Mitigation |
|---|---|---|
| v1.5.0 schema doesn't cleanly extend for skill fields | Medium | Review schemas.md before Phase 2 starts; adjust v1.5.0 design if needed mid-flight |
| Classification heuristic misfires on edge-case repos | Medium | Council of Three can override; classification rationale logged for review |
| Section-to-REQ extraction produces too many REQs (explosion) | Medium | Completeness audit sets upper bound; Phase 4 Council prunes redundant REQs |
| Execution divergence has too few archived runs to be useful | Low for QPB (has bootstrap history); Medium for new projects | Document minimum run threshold; emit confidence caveat with low-N findings |
| Hybrid projects produce unwieldy REQUIREMENTS.md length | Medium | Functional section grouping (from v1.5.0) handles this; verify during Phase 7 |
| Cross-model inconsistency on skill derivation | Medium | Test with opus + sonnet + copilot+gpt explicitly in Phase 7; adjust prompts if variance too high |
| Single-shot Pass A over long skills silently drops coverage under context pressure | High for skills with >500 lines of input; empirically observed in prior summarizer work on comparable-scale inputs | Section-iterative Pass A with per-section cursor and compaction-recovery prompt preamble; throughput ceiling as fail-loud tripwire (see Phase 3 Per-Pass Execution Protocol) |
| Pass interrupted mid-run requires full restart, wasting cost and inviting inconsistency | Medium | Every pass writes intermediate artifacts and advances a progress cursor atomically; restart resumes from cursor. Gate to Phase 4 requires explicit kill-and-restart verification. |
| Progress file and on-disk artifact drift out of sync (progress lags writes or leads writes) | Medium; observed in prior summarizer work where batched progress updates lagged per-record writes | Progress cursor updates are atomic and required after every single unit of work, never in batches. Restart logic verifies last JSONL record matches `cursor - 1` and rolls the cursor back to disk state on discrepancy. |

---

## Open Questions to Resolve

These need answers during implementation but don't block planning:

1. (Phase 1) What's the exact threshold of "prose vs code" for Skill vs Hybrid? Lean: if SKILL.md word count > 2× code LOC, classify as Skill; otherwise Hybrid. Calibrate against real examples.
2. (Phase 3) Should section-to-REQ extraction happen in one pass or iteratively (first draft, then refine)? Lean: iterative, with a Council review between passes.
3. (Phase 4) How strict should "SKILL.md prose claim about code" detection be? Over-eager = false positives. Under-eager = missed bugs. Lean: tune against QPB's own known prose-code drift.
4. (Phase 5) Should execution divergence consume ALL prior runs or a sliding window? Lean: sliding window of last 5; older runs may reflect older skill versions.
5. (All phases) Is SKILL.md always the single Tier 1 source for a skill, or can a project designate external Tier 1 docs? Lean: project can designate; if project has a formal spec elsewhere (e.g., a published methodology paper), that's Tier 1 and SKILL.md is Tier 2 implementation. Uncommon but possible.

---

## Plan Revision Expectations

This plan is explicitly provisional. Revisit after v1.5.0 ships with:

- Any schema changes from v1.5.0 implementation that affect Phase 2 extensions
- Any orchestrator refactors that change where classification logic belongs
- Any Phase 4 Council changes that affect divergence detection integration
- Updated Haiku benchmark if the Haiku-generated REQUIREMENTS.md is refined based on v1.5.0 learnings
- Any new benchmark repos added during v1.5.0 work

The review pass should update this document in place (no separate revision log needed; git history captures changes).
