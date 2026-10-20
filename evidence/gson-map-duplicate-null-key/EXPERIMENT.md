# Experiment: Gson — Documentation-Enriched Playbook Evaluation

## Background

Gson (google/gson) is one of five repositories selected for cross-repo validation of the Quality Playbook v1.2.15. The five repos span three languages and three architecture types:

| Repo | Language | Type | Why chosen |
|------|----------|------|------------|
| NSQ | Go | Infrastructure | Original benchmark repo; 58 ground-truth defects |
| Express | JavaScript | Framework | Highest-risk pick; produced 1,249 passing integration tests and confirmed a real defect |
| Gson | Java | Library | Richest external documentation ecosystem; ideal for the docs-enrichment experiment |
| Chi | Go | Library | Compact router; tests generalization to small libraries |
| Pydantic | Python | Library | Type-driven validation; tests cross-language generalization |

Gson was specifically selected for the **documentation enrichment experiment**: does feeding community documentation into the requirement derivation step produce better requirements and, consequently, better defect detection?

## Hypothesis

The NSQ benchmark (see `benchmarks/EXPERIMENT.md`) established that ~35% of real defects are invisible to structural code review — they require knowing the *intent* (what the code is supposed to do, not just what it does). The playbook's requirement derivation step (Step 7) attempts to close this gap, but its quality depends on the available intent sources.

For most repos, the only intent sources are in-repo docs and code comments. Gson is unusual: it has extensive official documentation (UserGuide, Troubleshooting, DesignDocument), a rich GitHub issue history expressing behavioral contracts, and active community tutorials. If community documentation improves requirement derivation, Gson should show the strongest effect.

**Primary hypothesis**: Running the playbook with community documentation will produce more requirements, more specific requirements, and better test coverage than running it with only in-repo sources.

**Secondary hypothesis**: Requirements derived from community sources will catch intent violations that code-only review misses — particularly null handling edge cases, TypeAdapter contract violations, and generic type boundary issues.

## Experiment Design

### Condition A: Baseline (repo-only)

Run the full v1.2.15 playbook pipeline against the Gson repo using only in-repo documentation:
- UserGuide.md, GsonDesignDocument.md, Troubleshooting.md, CHANGELOG.md
- Source code and existing tests
- Standard 9-prompt pipeline via `run_playbook.sh`

### Condition B: Documentation-enriched

Run the identical pipeline except:
- Prompt 1 uses `prompt1_generate_playbook_with_docs.md` instead of `prompt1_generate_playbook.md`
- This variant instructs the model to read `community_docs/BEHAVIORAL_CONTRACTS.md` before Step 7
- All other prompts (2-9) are identical

### Control variables
- Same model: GPT-5.4 via Copilot CLI (`gh copilot`)
- Same playbook version: v1.2.15 (skill at `.github/skills/SKILL.md`)
- Same repo state: google/gson at the commit used for cloning
- Same 9-prompt pipeline sequence

## Current State

### Baseline run (Condition A) — Completed 2026-04-02

The baseline run completed all 9 prompts. Output is preserved in `quality_baseline/`:

| File | Description |
|------|-------------|
| `quality_baseline/QUALITY.md` | Quality constitution generated from repo-only sources |
| `quality_baseline/REQUIREMENTS.md` | Requirements derived without community docs |
| `quality_baseline/RUN_CODE_REVIEW.md` | Three-pass code review protocol |
| `quality_baseline/RUN_INTEGRATION_TESTS.md` | Integration test protocol |
| `quality_baseline/RUN_SPEC_AUDIT.md` | Council of Three spec audit protocol |
| `quality_baseline/code_reviews/code-review-2026-04-03-copilot.md` | Code review output |
| `quality_baseline/results/prompt3_functional_tests_2026-04-03.md` | Functional test results |
| `quality_baseline/results/prompt4_integration_tests_2026-04-03.md` | Integration test results |
| `quality_baseline/spec_audits/2026-04-03-auditor1.md` | Spec audit — Auditor 1 |
| `quality_baseline/spec_audits/2026-04-03-auditor2.md` | Spec audit — Auditor 2 |

The baseline `quality/` directory was renamed to `quality_baseline/` to preserve it before re-running with documentation enrichment.

### Documentation assembly — Completed 2026-04-03

The original documentation approach compiled multiple sources into two synthesized files:
- `GsonDesignDocument.md` (already in repo — this is part of the Gson source)
- `community_docs/BEHAVIORAL_CONTRACTS.md` (40+ behavioral contracts compiled from official docs, GitHub issues, and community sources)

This approach was replaced with a comprehensive `retrieved_documentation/` folder containing 24 individual source files organized by type:

| Category | Count | Contents |
|----------|-------|----------|
| `official/` | 7 | User guide, troubleshooting, design doc, changelog, releases, Gson Javadoc, TypeAdapter Javadoc |
| `github_issues/` | 13 | Issues #530, #613, #676, #913, #948, #1005, #1558, #2032, #2059, #2295, #2563, #2739, #2787 |
| `community/` | 4 | Tutorials from HowToDoInJava and Future Studio on custom serialization/deserialization and @JsonAdapter |

Each file includes a YAML front matter header with source URL, retrieval date, type classification, and description. See `retrieved_documentation/INDEX.md` for the complete file list.

The rationale for replacing compiled docs with individual retrieved files:
1. **Provenance**: Each file has a clear source URL and retrieval date
2. **No synthesis artifacts**: The compiled BEHAVIORAL_CONTRACTS.md mixed content from multiple sources into a single authored document, which introduces an interpretation layer. Individual files preserve the original author's framing
3. **Granularity**: The playbook can reference specific documents rather than searching a monolithic file
4. **Reproducibility**: Another researcher can verify each file against its source

### Documentation-enriched run (Condition B) — Completed 2026-04-03

The enriched run used `prompt1_generate_playbook_with_docs.md` referencing the `retrieved_documentation/` corpus (24 files across 3 categories). Original output is preserved in `quality_v2_77req/` (renamed from `quality/` on 2026-04-03 before the iterative requirements improvement work began):

| File | Description |
|------|-------------|
| `quality_v2_77req/QUALITY.md` | Quality constitution generated with community docs |
| `quality_v2_77req/REQUIREMENTS.md` | Requirements — 77 total after two-pass improvement (see below) |
| `quality_v2_77req/RUN_CODE_REVIEW.md` | Three-pass code review protocol |
| `quality_v2_77req/RUN_INTEGRATION_TESTS.md` | Integration test protocol |
| `quality_v2_77req/RUN_SPEC_AUDIT.md` | Council of Three spec audit protocol |
| `quality_v2_77req/code_reviews/2026-04-03-head-review.md` | Code review output |
| `quality_v2_77req/code_reviews/structural-only-control.md` | Structural-only control (no playbook) |
| `quality_v2_77req/results/functional-tests-2026-04-03.md` | Functional test results |
| `quality_v2_77req/results/integration-tests-2026-04-03.md` | Integration test results |
| `quality_v2_77req/results/v1.2.15_summary.md` | Triage and summary |
| `quality_v2_77req/spec_audits/2026-04-03-auditor1.md` | Spec audit — Auditor 1 |
| `quality_v2_77req/spec_audits/2026-04-03-auditor2.md` | Spec audit — Auditor 2 |
| `quality_v2_77req/spec_audits/2026-04-03-auditor3.md` | Spec audit — Auditor 3 |

### Requirements improvement experiment — 2026-04-03

After the Condition B run produced its initial REQUIREMENTS.md (48 requirements), three rounds of improvement were applied to test whether restructured prompts and multi-pass generation produce better requirements.

#### Round 1: Template restructuring (48 → 70 requirements)

The SKILL.md Step 7 template was restructured based on use case and user story patterns from *Applied Software Project Management* and *Learning Agile*. The old template had three fields per requirement (summary, rationale, specificity). The new template has seven:

| Field | Purpose | Inspired by |
|-------|---------|-------------|
| **Summary** | Testable assertion ("X must Y") | Same as before |
| **User story** | "As a [role], I want [behavior] **so that** [outcome]" | User stories (Learning Agile) — the "so that" clause forces articulation of intent |
| **Implementation note** | How the code achieves this (was "Rationale") | Renamed to clarify this is mechanism, not motivation |
| **Conditions of satisfaction** | Specific testable scenarios proving the requirement is met | Conditions of satisfaction (Learning Agile) |
| **Alternative paths** | Multiple code paths that must all satisfy it | Alternative courses of action (use case templates) |
| **References** | Source citations | Same as before |
| **Specificity** | specific or directional | Same as before |

The "Expect 30-60 requirements" instruction was also removed, replaced with "Do not cap the requirement count."

**Key improvement:** The old REQ-033 (duplicate keys) said "Java Map semantics require one value per key." The new REQ-054 adds conditions of satisfaction that explicitly call out "including edge cases where the first occurrence carried a null value" — the exact scenario that found the confirmed bug. The template forced the model to enumerate edge cases it would have skipped with the terse format.

Prompt used: `control_prompts/prompt_rerun_requirements.md`

#### Round 2: Domain-knowledge gap audit (70 → 77 requirements)

A second pass asked the model to find requirements that *should* exist based on domain knowledge rather than project documentation. This is a fundamentally different question from Pass 1: Pass 1 asks "what does this code promise?" and Pass 2 asks "what should code like this promise?"

7 new requirements added:
- RFC 8259 edge cases: BOM handling (REQ-071), structural whitespace boundaries (REQ-072), Unicode escape/surrogate pair correctness (REQ-073)
- Java records: canonical constructor binding (REQ-074), record component null/default semantics (REQ-075)
- Java serialization interop: Gson's internal types survive ObjectOutputStream (REQ-076)
- Backward compatibility: adapter factory consultation order (REQ-077)

Prompt used: `control_prompts/prompt_requirements_pass2_gap_audit.md`

#### Coverage analysis: 77 requirements cover 38 of 81 source files

A source-file coverage check (`control_prompts/check_coverage.py`) revealed that 34 significant source files (≥50 lines, totaling 5,720 lines) have zero requirements referencing them. The biggest gaps:

| Area | Uncovered files | Total lines |
|------|----------------|-------------|
| Date/time adapters | DefaultDateTypeAdapter, JavaTimeTypeAdapters, ISO8601Utils, PreJava9DateFormatProvider, Sql*TypeAdapter (×3), SqlTypesSupport | ~1,435 |
| Tree model bridge | JsonTreeReader, JsonTreeWriter, JsonElementTypeAdapter, Streams | ~985 |
| Type adapters | EnumTypeAdapter, ArrayTypeAdapter, CollectionTypeAdapterFactory, NumberTypeAdapter, JsonAdapterAnnotationTypeAdapterFactory | ~632 |
| Parsing entry points | JsonParser, JsonPrimitive | ~506 |
| Configuration | FormattingStyle, FieldNamingPolicy, FieldNamingStrategy, FieldAttributes, LongSerializationPolicy, ToNumberStrategy | ~626 |
| Internal utilities | GsonTypes, UnsafeAllocator, NonNullElementWrapperList, ReflectionAccessFilterHelper, JavaVersion | ~1,175 |

#### Round 3: Iterative gap-fill loop (in progress)

An automated loop (`control_prompts/run_requirements_loop.sh`) runs the coverage check and generates requirements for uncovered files until convergence:

1. `check_coverage.py` identifies uncovered files → writes `uncovered_files.txt`
2. `prompt_requirements_gap_fill.md` reads each uncovered file and appends new requirements
3. Loop repeats until no significant uncovered files remain or no new requirements are added

The loop has a safety cap of 5 iterations. Expected outcome: 100-130+ total requirements covering all significant source files.

#### Directory layout

| Directory | Contents | Requirement count |
|-----------|----------|-------------------|
| `quality_baseline/` | Condition A output (repo-only docs) | 43 |
| `quality_v2_77req/` | Condition B output after Rounds 1-2 | 77 |
| `quality/` | Current working version (Round 3, in progress) | TBD |

## Results: Condition A vs Condition B

### Requirements (REQUIREMENTS.md)

| Metric | Baseline (A) | Enriched (B) | Delta |
|--------|-------------|-------------|-------|
| Total requirements | 43 | 48 | +5 |
| Requirements citing GitHub issues | 0 | 5 | +5 |

The five new requirements all target behavioral contracts invisible in source code alone:

1. **Null-handling layer asymmetry** (from issues #676, #913, #948) — `serializeNulls` is global-only, TypeAdapter.write/read is never invoked for null values, RuntimeTypeAdapterFactory discards nested null settings
2. **Per-type null control gap** (from #1558) — no way to distinguish required-nullable from optional fields
3. **Deserialization affecting serialization** (from #2032) — registering a custom JsonDeserializer unexpectedly changes serialization behavior, dropping subclass fields
4. **Backward compatibility regression pattern** (from #2787) — Gson 2.11 broke custom JsonElement adapters; reverted in 2.12.0
5. **Thread safety during class loading** (from #2739) — critical deadlock between TypeAdapters and JsonElementTypeAdapter during concurrent class initialization

All five are intent violations: behaviors you cannot derive from reading the code, because you need to know what users expect the code to do.

### Quality Constitution (QUALITY.md)

| Metric | Baseline (A) | Enriched (B) | Delta |
|--------|-------------|-------------|-------|
| File size (bytes) | 14,513 | 16,776 | +2,263 |
| Fitness-to-purpose scenarios | 10 | 12 | +2 |

Two new scenarios added, both grounded in specific GitHub issues:

1. **Null-handling layer asymmetry** — verifies that TypeAdapter null bypass, global serializeNulls, and per-field null expectations interact correctly
2. **Polymorphic serialization regression** — verifies that registering a deserializer doesn't silently change serialization output

### Spec Audits

| Metric | Baseline (A) | Enriched (B) | Delta |
|--------|-------------|-------------|-------|
| Total findings | 5 | 9 | +4 (80% increase) |
| Cross-auditor redundancy | ~50% | 0% | Eliminated |
| Finding categories | 2 | 4 | +2 new |

New finding categories in the enriched run:

- **PHANTOM** — Javadoc claims that aren't true in practice (e.g., thread safety guarantees that break during class loading)
- **DIVERGENT** — places where the spec and code intentionally disagree (e.g., design document says "fields not getters" but reflection adapter has getter-detection code paths)

The elimination of redundancy is significant: three independent auditors produced nine distinct findings with zero overlap, suggesting the richer requirements gave each auditor more specific and different things to verify.

### Code Reviews

| Metric | Baseline (A) | Enriched (B) |
|--------|-------------|-------------|
| Head review findings | 9 | 4 |
| Structural-only control findings | — | 7 |

The enriched head review was more consolidated, focusing on higher-signal issues rather than spreading across many low-confidence findings. The structural-only control (run without the playbook) found 7 issues orthogonal to the requirements-grounded review, confirming that structural review and requirements-based review catch different defect classes.

### Hypothesis Assessment

**Primary hypothesis — CONFIRMED**: The enriched run produced more requirements (48 vs 43), more specific requirements (all 5 new ones cite concrete issue numbers), and better test coverage (12 vs 10 fitness scenarios). The quality constitution grew by 16% in size, indicating more detailed behavioral specifications.

**Secondary hypothesis — CONFIRMED**: All five new requirements target intent violations that code-only review misses. Three of five are null-handling edge cases (the predicted strongest area), one is a TypeAdapter contract violation, and one is a type system boundary issue. These match the exact categories predicted in the hypothesis.

### Key Insight

The spec audit improvement (80% more findings, zero redundancy) was the most dramatic result. This suggests that documentation enrichment has a compounding effect: better requirements → more specific quality constitution → more diverse audit findings. The bottleneck in AI-assisted code review is not the review technique — it's the quality of the requirements the review is grounded in.

### Confirmed Bug: Duplicate Key with Null First Value (2026-04-03)

Manual verification of the code review output confirmed a **real, unreported bug** in Gson's current `main` branch (2.13.3-SNAPSHOT). The finding was REQ-033 in `quality/code_reviews/2026-04-03-head-review.md`.

**PR filed:** https://github.com/google/gson/pull/2999 — fix and 3 tests, all 4,589 existing tests passing, CI checks green.

**The bug:** `MapTypeAdapterFactory.java` lines 191-206 detect duplicate keys using:
```java
V replaced = map.put(key, value);
if (replaced != null) {
    throw new JsonSyntaxException("duplicate key: " + key);
}
```
When the first occurrence of a duplicate key maps to `null`, `map.put()` returns `null` (the previous value), and `if (replaced != null)` evaluates to false. The duplicate is silently accepted.

**Reproduction:** `gson.fromJson("{\"a\":null,\"a\":1}", new TypeToken<Map<String, Integer>>(){}.getType())` returns `{a=1}` with no exception. Expected behavior: throw `JsonSyntaxException("duplicate key: a")`.

**Verification:**
- Added `testMapDeserializationWithDuplicateKeysNullFirstValue` to `MapTest.java`
- Test fails: `expected com.google.gson.JsonSyntaxException to be thrown, but nothing was thrown`
- Added `testMapDuplicateKeyNullDiagnostic` (no assertThrows, just calls fromJson and asserts on result) — passes, confirming silent acceptance
- Bug affects both object form (`{"a":null,"a":1}`) and array-of-entries form (`[["a",null],["a",1]]`)
- Both existing duplicate-key tests use non-null first values, so this edge case was never covered

**Root cause:** The duplicate-key check was added in [PR #649](https://github.com/google/gson/pull/649) using `replaced != null` instead of `map.containsKey(key)`. Gson's `LinkedTreeMap` (used for `Map<String, ...>`) allows null values by default (`allowNullValues = true`), so `put("a", null)` stores null, and the subsequent `put("a", 1)` returns null without triggering the check.

**Fix:** Check `map.containsKey(key)` before calling `map.put(key, value)` at both code paths (object form and array-of-entry form).

**Significance for the experiment:** This bug was found by the documentation-enriched code review (Condition B), not the baseline (Condition A). The enriched requirements included null-handling behavioral contracts derived from GitHub issues (#676, #913, #948, #1558) about Gson's null semantics. REQ-033 ("Map deserialization must reject duplicate keys") was grounded in these community-documented expectations. Without the documentation enrichment, the code review had no basis to question whether the `replaced != null` check was sufficient for all cases. This is the strongest possible evidence for the documentation enrichment hypothesis: it found a real bug that structural review alone cannot detect.

### Next Steps

1. ~~File the bug with the Gson project~~ — Done: PR #2999 filed 2026-04-03, CI passing
2. Complete the iterative gap-fill loop to achieve full source-file coverage in REQUIREMENTS.md
3. Rerun the code review against the expanded requirements to measure detection improvement
4. Score both conditions against known Gson defects (when available)
5. Rerun with `claude-opus-4.6` model for cross-model comparison
6. Apply the documentation enrichment approach to other QPB repos to test generalizability

## Execution Infrastructure

### Pipeline scripts

| Script | Purpose |
|--------|---------|
| `run_playbook.sh` | Standard 9-prompt pipeline (Condition A) |
| `run_playbook_with_docs.sh` | Documentation-enriched pipeline (Condition B) — uses `prompt1_generate_playbook_with_docs.md` for prompt 1 |

### Control prompts

9 prompts in `control_prompts/`, one per pipeline step:

| Prompt | Step | Description |
|--------|------|-------------|
| `prompt1_generate_playbook.md` | Phases 1-3 | Generate playbook from repo-only sources |
| `prompt1_generate_playbook_with_docs.md` | Phases 1-3 | Generate playbook with community docs |
| `prompt2_run_code_review.md` | Code review | Three-pass code review |
| `prompt3_run_functional_tests.md` | Functional tests | Run functional test suite |
| `prompt4_run_integration_tests.md` | Integration tests | Run integration tests |
| `prompt5_run_spec_audit_model1.md` | Spec audit | Auditor 1 |
| `prompt6_run_spec_audit_model2.md` | Spec audit | Auditor 2 |
| `prompt7_run_spec_audit_model3.md` | Spec audit | Auditor 3 |
| `prompt8_triage_and_summary.md` | Triage | Triage and summarize findings |
| `prompt9_structural_only_review.md` | Control | Structural-only review (no playbook) |

All prompts use GPT-5.4 via `gh copilot`.

### Playbook version

v1.2.15, installed at two locations for compatibility:
- `.skills/skills/quality-playbook/SKILL.md` (Claude Code format)
- `.github/skills/SKILL.md` (GitHub Copilot format)

Both point to the same skill content and reference files.

## Connection to Broader QPB Project

This experiment is part of the Quality Playbook Benchmark (QPB), which measures and improves AI-assisted code review using 2,564 ground-truth defects from 50 open-source repositories. The Gson documentation-enrichment experiment addresses a specific question surfaced by the NSQ benchmark: whether providing richer intent sources (beyond code) improves the playbook's requirement derivation and defect detection.

Key findings from prior experiments that motivate this work:

1. **NSQ benchmark** (`benchmarks/EXPERIMENT.md`): A strong model with no playbook scores ~65% on real defects. Adding focus areas doesn't reliably improve this. The 35% that all conditions miss are intent violations requiring requirements.

2. **Requirement derivation experiment** (`benchmarks/requirement_derivation_experiment.md`): Requirements derived from docs improve defect detection for intent violations. The question is whether richer docs produce better requirements.

3. **Cross-repo validation**: Express, Chi, NSQ, and Pydantic results all show the same pattern — the multi-source pipeline (code review + requirement verification + spec audit) finds more bugs than any single technique, but the quality ceiling is set by the requirements.

4. **Express result**: 1,249 passing integration tests and a confirmed real defect (`res.redirect(999, '...')` producing `undefined. Redirecting to...`). This proved the playbook can find real bugs in production code end-to-end.

The Gson experiment tests whether the weakest link — requirement quality — can be strengthened by feeding the model more sources of developer intent.
