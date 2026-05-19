# QPB v1.5.3 Phase 3c — Live Self-Audit Run Summary

*Aggregate Pass D per-section accounting + council inbox count +
wall-clock for the live self-audit on QPB SKILL.md.*

*Generated: 2026-04-27 (Phase 3c live run, HEAD 6a0b074).*

## What this run produced

A complete `quality/phase3/` artifact set for QPB SKILL.md (1959
lines + 14 reference files):

```
pass_a_sections.json              # 125 sections enumerated
pass_a_drafts.jsonl               # 200 records (truncated from 1392)
pass_a_use_case_drafts.jsonl      # 15 UC drafts
pass_a_progress.json              # status=complete, cursor=125
pass_b_citations.jsonl            # 200 records (one per truncated draft)
pass_b_progress.json              # status=complete, cursor=200/200
pass_c_formal.jsonl               # 198 formal REQs
pass_c_formal_use_cases.jsonl     # 15 formal UCs (UC-PHASE3-01..15)
pass_c_progress.json              # status=complete, cursor=215/215
pass_d_audit.json                 # promoted/rejected/demoted
pass_d_section_coverage.json      # per-section accounting
pass_d_council_inbox.json         # 225 items needing review
pass_d_progress.json              # status=complete, cursor=198/198
HAIKU_COMPARISON.md               # parity assessment vs Haiku 78-REQ benchmark
RESUMABILITY_REPORT.md            # full 4-kill resumability report
SUMMARY.md                        # this document
```

## Section coverage

Per `pass_d_section_coverage.json`:

| Section kind | Total | With drafts in truncated set | Skipped (meta) |
|---|---:|---:|---:|
| Operational | 102 | 13 | n/a |
| Execution-mode | 10 | 2 | n/a |
| Meta | 13 | n/a | 13 |
| **Total** | **125** | **15** | **13** |

15 sections have drafts because the truncation kept only the first
200 Pass A drafts, which originated from sections 0–16 (the early
SKILL.md sections). The remaining 110 sections (cursor 17–124 in
the original 1392-draft Pass A output) produced drafts in the
untruncated Pass A but were excluded by the commit 2/4 truncation.

## Council inbox accounting

| Item type | Count | Source |
|---|---:|---|
| `rejected-draft` | 121 | Pass C disposition=needs-council-review |
| `weak-rationale` | 15 | Pass C formal UC records (each carries needs_council_review=true) |
| `zero-req-section` | 89 | operational sections with zero drafts and no skip-rationale (truncation-driven) |
| `tier-5-demotion` | 0 | (no Pass A draft hit the behavioral branch on QPB's Hybrid classification) |
| **Total** | **225** | |

## Audit accounting

Per `pass_d_audit.json`:

```
promoted_count: 77         (Pass C accepted = Tier 1 or Tier 2 verified)
rejected_count: 121        (Pass C needs-council-review)
demoted_count: 0           (no Pass A drafts routed to Tier 5)
rejection_rate: 0.611      (61.1%)
phase4_council_flag: true  (rejection rate > 30% threshold)
```

The phase4_council_flag firing means Phase 4's Council prompt
should expect the council inbox to be load-bearing for the spec
audit (rather than the formal REQs alone). The 121 rejected-draft
items dominate the inbox; Phase 4 Council's job is to adjudicate
each one.

## Source-type and tier distribution

Per `pass_c_formal.jsonl`:

| source_type | Count | Tier 1 | Tier 2 | Tier 5 |
|---|---:|---:|---:|---:|
| skill-section | 179 | 179 | 0 | 0 |
| reference-file | 19 | 0 | 19 | 0 |
| code-derived | 0 | 0 | 0 | 0 |
| execution-observation | 0 | 0 | 0 | 0 |
| **Total** | **198** | **179** | **19** | **0** |

Zero records carry `source_type: "execution-observation"` (Pass C
invariant #2 — reserved for Phase 4). Zero invariant #21
violations: every skill-section record has a non-empty
`skill_section`. Zero ND-2 guard hits: every Pass A draft had a
parseable `proposed_source_ref`, so the guard's council-review
path was not triggered.

## Use case derivation

15 formal UCs (`pass_c_formal_use_cases.jsonl`):

```
UC-PHASE3-01: User invokes playbook with default trigger phrase, only Phase 1 runs
UC-PHASE3-02: User explicitly advances through phases one at a time across sessions
UC-PHASE3-03: Phase 0 full continuation mode: prior runs exist with conformant artifacts
UC-PHASE3-04: Phase 0 skip: no prior runs exist
UC-PHASE3-05: Phase 0 partial skip: quality/runs/ exists but contains no conformant artifacts
UC-PHASE3-06: User runs Phase 3 code review and regression tests
UC-PHASE3-07: Full-council Phase 4 spec audit and triage with spot-check validation
UC-PHASE3-08: Phase 4 spec audit with incomplete council and enumeration or whitelist checks
UC-PHASE3-09: Run Phase 5 reconciliation and closure verification after Phase 4 completes
UC-PHASE3-10: Challenge gate rejects or downgrades false-positive bugs before reconciliation
UC-PHASE3-11: Execute Phase 6 incremental verification after reconciliation completes
UC-PHASE3-12: User verifies applied bug fixes using recheck mode
UC-PHASE3-13: User reviews generated artifacts and directs next steps after Phase 6 completes
UC-PHASE3-14: Agent executes the full four-strategy iteration cycle in recommended order
UC-PHASE3-15: Phase C: iterative contract coverage verification and gap remediation loop
```

Maps to 8 of Haiku's 10 UCs plus 5 sub-scenario UCs (see
`HAIKU_COMPARISON.md` for the full mapping). Two Haiku UCs
(UC-09 Benchmark Operator, UC-10 Bootstrap Self-Audit) did not
surface as standalone UCs — Phase 3d brief should expand
`EXECUTION_MODE_KEYWORDS` or accept these as Council-review
additions.

## Wall-clock breakdown

| Phase | Wall-clock | Notes |
|---|---|---|
| Pass A run 1 (cursor 0→12) | ~7 min | initial run; killed for Kill 1 |
| Pass A run 2 (cursor 12→39) | ~36 min | resumed after Kill 1; tripwire halt at section 39 |
| Pass A run 3 (cursor 39→44) | ~4 min | tripwire halt at section 44 (post-fix) |
| Pass A run 4 (cursor 44→125) | ~70 min | post-tripwire-fix completion |
| **Pass A subtotal** | **~117 min (≈2 hr)** | 4 starts due to Kill 1 + 2 tripwire halts |
| Pass B run 1 (cursor 0→19) | ~3 min (mostly setup) | killed for Kill 2 |
| Pass B run 2 (cursor 20→200) | ~52 min | resumed; truncated at idx 200 |
| **Pass B subtotal** | **~55 min** | including kill+resume overhead |
| Pass C run 1 (cursor 0→29) | ~3 sec | killed for Kill 3 |
| Pass C run 2 (cursor 30→215) | ~9 sec | resumed to completion |
| **Pass C subtotal** | **~12 sec** | mechanical, no LLM |
| Pass D | ~1 sec | atomic; mechanical |
| Allowlist tuning re-run (Pass D only) | ~1 sec | commit 3/4 |
| Downstream-refuses experiment | ~5 sec | refusal verified |
| **Total live-run wall-clock** | **~3 hours 15 min** | within the brief's 8-hour budget |

## Findings flagged for Phase 3d / Phase 4 brief authorship

### Finding 1 — Pass A draft count exceeds brief target by 14×

Pass A produced 1392 drafts on QPB; the brief targets 86–105.
The Pass A prompt's "extract every testable claim" instruction
is high-recall by design, and QPB's ~37,000 prose words across
SKILL.md + 14 reference files is much larger than the corpus
the brief was calibrated against. Phase 3d should either:

1. Tune the Pass A prompt for selectivity (e.g., "extract the
   3–5 most-testable claims per section" rather than "every
   testable claim"), targeting ~1 draft per section.
2. Or recalibrate the brief's 86–105 range against QPB's actual
   corpus shape.

### Finding 2 — Pass B's O(n×m) fuzzy search dominates wall-clock

`citation_search.find_best_match` runs SequenceMatcher.ratio()
against every (window-size, line-position) pair in the corpus,
which is O(n×m) per draft. On QPB with ~5000 source lines and
1392 drafts, projected wall-clock was ~7 hours. A token-overlap
pre-filter would cut to O(n) for the rejection cases and
SequenceMatcher only for the high-token-overlap candidates,
likely 5–10× speedup. Phase 3d should consider this optimization
as part of unblocking the full 1392-draft Pass B run.

### Finding 3 — Tripwire floor was over-tuned for SKILL.md

The original `MIN_PLAUSIBLE_ELAPSED_MS = 12_000` was calibrated
against 300+-line SKILL.md sections. Reference-file sub-sections
of 20–50 lines legitimately complete in 3–12s. Commit 2/4
lowered the floor to 2,500ms based on live-run evidence (sections
39 at 11890ms and 44 at 4542ms produced substantive drafts).
Phase 3d should leave the floor at 2.5s unless Phase 4 surfaces
new evidence.

### Finding 4 — META_SECTION_ALLOWLIST tuning surfaced 3 obvious additions

Commit 3/4 added "Purpose", "Template", and "Generated file
template" to the allowlist after live-run evidence. These are
descriptive/structural sections, not testable rules. The +3
entries reduced the post-tuning gap count from 94 to 89 (the
remainder is truncation-driven).

### Finding 5 — Haiku UC-09 (Benchmark) and UC-10 (Bootstrap) gap

QPB Pass A's `EXECUTION_MODE_KEYWORDS` matched 10 sections, all
of which produced UC drafts; but no UC drafts surfaced for
"benchmark operator" or "bootstrap self-audit" scenarios. Phase 3d
should expand `EXECUTION_MODE_KEYWORDS` (e.g., add "benchmark"
and tighten "bootstrap" matching) or accept these as Council
additions for Phase 4.

### Finding 6 — Pass C disposition table did not produce any Tier 5 demotions

Zero records routed to the Tier 5 (code-derived) branch on QPB's
Hybrid classification. The cause: `_is_behavioral_claim` returns
False whenever `proposed_source_ref` is non-empty, and the Pass A
prompt asks the LLM to always populate `proposed_source_ref`. So
in practice 0% of Pass C records hit the behavioral branch. This
is consistent with Phase 3b PHASE3B_SUMMARY.md observation B
("Pass A's `_is_behavioral_claim` heuristic in Pass C is
approximate"); the live run confirmed the practical impact:
**most unverified drafts route to council-review, not Tier 5
demotion.** Phase 4's Council should expect a council-inbox
heavy on `rejected-draft` items rather than `tier-5-demotion`.

### Finding 7 — `weak-rationale` ambiguity for UC items (Round 5 ND-3 confirmed)

The council inbox uses `item_type: "weak-rationale"` for both
genuinely-weak rejected drafts AND formal UCs (which always carry
`needs_council_review: true`). All 15 UC items carry
`weak-rationale`, alongside the 121 rejected-drafts (different
type). A Phase 4 reviewer reading the inbox needs to disambiguate
by `record-id field`: items with `uc_id` (UC-PHASE3-NN) are UCs
needing review; items without are weak-rationale REQs. Phase 4
brief should either rename the UC items to `uc-needs-review` or
document the disambiguation rule.

## Test counts (post-Phase-3c)

| Suite | Pre-Phase-3c | Post-Phase-3c | Delta |
|---|---:|---:|---:|
| `bin/tests/` | 586 | 596 | +10 (test_skill_derivation_main.py: 9; SkillSectionGuardTests: 1) |
| `.github/skills/quality_gate/tests/test_quality_gate.py` | 204 | 198 | -6 (TestSkillDerivationMainArgs moved to bin) |
| `.github/skills/quality_gate/tests/test_req_pattern.py` | 6 | 6 | 0 |
| **Total** | **796** | **800** | **+4** |

## What ships

The four Phase 3c commits (`97592ef`, `ca75a93`, `6a0b074`, plus
this commit 4/4) plus the Phase 3b foundations (8 commits +
PHASE3B_SUMMARY.md) constitute the Phase 3 surface ready for Round
6 Council review. Phase 3d (full Pass A + Pass B optimization +
the deferred 89-section coverage) and Phase 4 (consolidated
divergence detection + gate enforcement) are the explicit
follow-ups.
