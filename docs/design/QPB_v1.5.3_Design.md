# Quality Playbook v1.5.3 — Design Document

*Status: design captured; v1.5.0/v1.5.1/v1.5.2 shipped; ready for implementation on the fresh 1.5.3 branch (post-misfire reset 2026-04-26).*
*Authored: April 2026 (status refreshed 2026-04-26)*
*Owner: Andrew Stellman*
*Depends on: `QPB_v1.5.0_Design.md` (divergence model, tier system, citation schema, disposition field), `QPB_v1.5.1_Design.md` (Phase 5 writeup hardening), `QPB_v1.5.2_Design.md` (bug-family amplification, operational polish)*

> **Where v1.5.3 sits in the arc.** v1.5.3 is the final feature release in the *quality control* half of QPB's quality-engineering project — after v1.5.3 ships, QPB can audit AI skills with the same operational rigor it audits code with. The next two releases (v1.5.4 + v1.6.0) shift to the *quality improvement* half: v1.5.4 builds the regression-replay measurement machinery, v1.6.0 begins continuous lever-pull improvement using that machinery. The QC/QI distinction and the SEI/Humphrey lineage are documented in `ai_context/IMPROVEMENT_LOOP.md`.

---

## Motivation

### The goal: teach QPB to audit AI skills, not just code

QPB v1.5.0 through v1.5.2 evolved against code projects — virtio, chi, cobra, express, httpx, gson. For that class of target the divergence model works: specifications live in `formal_docs/` as RFCs or design docs, implementation lives in source files, and a defect is a divergence between the two. When the target is an AI skill — SKILL.md plus reference files, no compiler, no runtime, no separate implementation — the model breaks because there is no separation. The specification and the implementation are the same artifact. The prose is the program.

v1.5.3 extends QPB to cover that case without disturbing the code path. Phase 0 gains a project-type classifier that decides whether the target is a Code project, a Skill project, or a Hybrid (like QPB itself — SKILL.md plus `bin/` Python plus `quality_gate.py`). For Code projects, nothing changes. For Skill and Hybrid projects, a skill-specific four-pass derivation pipeline generates requirements from SKILL.md's section tree rather than from a separation that doesn't exist.

### The Haiku experiment is the evidence

On 2026-04-19, Claude Haiku 4.5 was given `docs_gathered/` (14 MB of QPB's own design history) and the existing `quality/REQUIREMENTS.md`, and asked three questions: what does this system do, what are its major features, and how much of the system does REQUIREMENTS.md span. Haiku immediately named the gap — the existing REQUIREMENTS.md covers only the Python orchestration layer and explicitly omits SKILL.md, phase-specific references, and orchestrator agent prompts. Asked to produce a comprehensive document covering the entire skill, Haiku produced a 2,129-line file with 95 REQ references organized by phase, 10 use cases spanning all seven phases plus iteration modes and bootstrap self-audit, explicit coverage of SKILL.md sections and reference files.

QPB's own v1.4.5 self-audit, running its full six-phase procedure over the same codebase, produced 721 lines, 40 REQs, and was focused almost entirely on the Python infrastructure. The smaller, cheaper model with two simple prompts beat QPB's own procedure by nearly 3× on the dimension the procedure was designed to optimize. That's not a model-quality gap; it's a systemic gap in what the procedure is looking for.

The Haiku-generated document is preserved at `AI-Driven Development/Haiku QPB requirements analysis/REQUIREMENTS.md` and is the benchmark v1.5.3 measures itself against.

### Why this is systemic, not a model-quality problem

QPB's six-phase pipeline assumes the thing under review is source code: Phase 1 explores the codebase, Phase 2 generates requirements from documentation *about* the code, Phase 3 reviews the code, Phase 4 audits the spec against the code, Phase 5 reconciles, Phase 6 verifies. Each step's prompt language is tuned for that shape. Applied to a skill, Phase 1 misclassifies SKILL.md as "documentation" (an input) rather than "the thing being specified" (the artifact under review). The tier system assumes Tier 1 intent lives in external specs and Tier 3–5 lives in the source; for a skill, documented intent AND implementation live in the same prose, so the tier question has no natural answer. The requirements pipeline — contract extraction → requirement derivation → verification → completeness — produces plumbing-level REQs from code, not section-level REQs from prose.

Haiku succeeded on QPB's skill because the operator's explicit instruction ("cover the entire skill, including the skill definition") bypassed these implicit assumptions. A general-purpose user won't think to give that instruction, and shouldn't have to. For QPB to audit skills reliably, the classification has to happen mechanically before Phase 1 starts.

### Why a four-pass generate-then-verify pipeline

Two different failure modes need two different defenses, and mixing them loses both.

Coverage (recall) is the strength of the Haiku-style prompt: read the whole skill, produce comprehensive requirements organized by functional area. That prompt runs high-recall on purpose — it over-produces rather than under-produces, because anything it misses in a single pass doesn't get another chance. Citation discipline (precision) is the strength of v1.5.0's mechanical citation extractor: given a draft REQ, grep SKILL.md and references for supporting text, populate `citation_excerpt` only from mechanical extraction, reject REQs with no supporting text. That extractor runs high-precision on purpose — it refuses to hallucinate citations, even when the REQ "feels right."

Mixing them produces the v1.4.x failure mode in reverse: the Phase 2 prompt asks one model to both cover comprehensively and cite rigorously, the model hedges toward whichever feels safer (citation rigor), coverage drops. Separating the passes lets each do what it's best at. Pass A generates coverage. Pass B extracts citations mechanically. Pass C converts cited drafts to formal REQs. Pass D diffs Pass A's full draft list against Pass C's verified list and forces explicit rationale for anything that dropped. The architecture is the pipeline equivalent of generate-and-verify rather than generate-while-verifying.

### Disk is the ledger, not a performance optimization

Pass A over a 1,500-line SKILL.md plus reference files is the same shape of problem as the summarizer work over 14 MB of chat history: unbounded single-shot generation degrades into templated stub output or silently-skipped input regions once context pressure rises. The mechanical defense is per-section progress with disk as the ledger. Every pass writes incrementally; every pass has a cursor in a progress file; every pass can resume from the last cursor position after interruption or auto-compaction. This isn't an optimization — it's a correctness invariant for pipelines that operate over long inputs.

### The measurable outcome

Success for v1.5.3 is a QPB self-audit that produces requirements coverage comparable to Haiku's 2,129-line benchmark. Specifically: the v1.5.3 self-audit should produce at least 80 REQ references with per-phase organization, cover SKILL.md section-by-section, and explicitly span reference files. If the self-audit still produces 40-REQ Python-only output, the pipeline hasn't done what it was designed to do and needs tuning before shipping.

### What v1.5.3 is not

Not a replacement for the code path — it's additive, and Code projects continue to run through the v1.5.0 divergence pipeline unchanged. Not new LLM machinery — the four-pass pipeline reuses v1.5.0's mechanical citation extractor and schema machinery in different passes, rather than inventing new infrastructure. Not the bug-family amplification work (that's v1.5.2) or the operator-experience work (that sits between v1.5.0 and v1.5.3 in the scope-revision record). Not an attempt to generalize the classifier beyond Code / Skill / Hybrid — those three categories cover every target QPB has encountered, and expanding the taxonomy is a later-release problem if it's a problem at all.

---

## Purpose of This Document

v1.5.3 addresses a category QPB currently fails on: AI skills. The playbook does a good job finding defects in code projects (virtio, chi, httpx, etc.) but produces incomplete requirements when the thing being audited is itself an AI skill — a prose-structured artifact where instructions ARE the program.

This doc captures the gap, the root cause, and the design for fixing it. A companion file `QPB_v1.5.3_Implementation_Plan.md` covers execution.

---

## The Gap — Evidence

On 2026-04-19, a test session with Claude Haiku 4.5 demonstrated the problem concretely. Given `~/Documents/QPB/docs_gathered/` (14MB of design history) and the existing `~/Documents/QPB/quality/REQUIREMENTS.md`, Haiku was asked:

1. What does this system do?
2. What are its major features?
3. How much of the system does REQUIREMENTS.md span?

Haiku correctly identified that the existing REQUIREMENTS.md covers only the Python orchestration layer (`bin/run_playbook.py`, `quality_gate.py`, `benchmark_lib.py`) and explicitly names what's missing: "the skill definition itself (SKILL.md — ~1,500 lines, the operational playbook), phase-specific reference files, orchestrator agent prompts."

When then asked to produce a comprehensive requirements document covering the entire skill, Haiku produced a 2,129-line file with 95 REQ references organized by phase (REQ-101-130 for Phase 1, REQ-201-250 for Phase 2, etc.), 10 use cases spanning all seven phases plus iteration modes and bootstrap self-audit, explicit coverage of SKILL.md sections, and reference files.

By comparison, QPB's own v1.4.5 self-audit produced 721 lines, 40 REQ references, focused almost entirely on Python infrastructure.

**Conclusion:** a smaller, cheaper model (Haiku 4.5) with two simple prompts produced dramatically better skill requirements than QPB's own six-phase procedure produced when auditing itself. This is a systemic gap, not a model-quality issue.

The Haiku-generated document is preserved at `AI-Driven Development/Haiku QPB requirements analysis/REQUIREMENTS.md` and serves as the benchmark for v1.5.3 success.

---

## Root Cause — Why QPB Misses This on Itself

QPB's mental model assumes a clean separation:

- **Specifications** are inputs (documentation, RFCs, design docs)
- **Code** is the thing being evaluated
- **Defect** is a divergence between the two

This is correct for virtio (RFC-backed C code) or gson (Google's own spec vs. Java implementation). The v1.5.0 divergence-based defect model applies directly.

It breaks for AI skills because **SKILL.md is simultaneously the specification AND the executable.** There is no compiler. The AI agent reads the prose and behaves accordingly. The prose IS the program.

Concrete consequences of this misalignment in v1.4.x:

1. **Phase 1 exploration misclassifies SKILL.md.** It sees SKILL.md as "documentation" (an input to be consumed) rather than "the thing being specified" (the output under review). Requirements extraction treats the prose as a contract source, not as the artifact whose requirements are being derived.

2. **The tier system doesn't map cleanly.** Tiers 1–5 assume documented intent lives in `formal_docs/` and implementation lives in source files. For an AI skill, documented intent AND implementation both live in SKILL.md. The tier a REQ should carry depends on a project-type question QPB never asks.

3. **The five-phase requirements pipeline doesn't produce skill-shaped output.** Contract extraction → requirement derivation → verification → completeness → narrative works for extracting behavioral contracts from code+docs. It doesn't naturally produce "Phase 1 produces EXPLORATION.md with ≥8 concrete findings" from a section of SKILL.md prose.

Haiku succeeded because the user's explicit instruction — "cover the entire skill, including the skill definition" — bypassed these implicit assumptions. For v1.5.3, the classification must happen mechanically, not depend on a user thinking of it.

---

## Design — Project Type Classification

Before Phase 1 begins, QPB performs a lightweight classification of the project under audit. Three categories:

### Category 1: Code Project
Examples: virtio, chi, cobra, express, httpx, gson.

Signature: source code in conventional language (.c, .go, .js, .py, .java), optional `formal_docs/` with external specs or internal design docs, tests that exercise the source.

Treatment: v1.5.0 divergence model applies directly. Formal docs are Tier 1/2 inputs. Source code is the implementation under review. Requirements are derived from the intersection of documented intent and observed behavior.

### Category 2: Skill Project
Examples: a pure AI skill — SKILL.md plus reference files, no orchestrator code. (Hypothetical; most skills grow orchestration over time and become hybrid.)

Signature: SKILL.md at repository root, reference files in `references/` or similar, no substantial executable code. The "program" is prose.

Treatment: skill-specific derivation pipeline. SKILL.md sections ARE the requirements. Divergence is measured by running the skill and inspecting produced artifacts against what each section promised.

### Category 3: Hybrid Project
Examples: QPB itself — SKILL.md plus `bin/` Python orchestration plus `quality_gate.py`.

Signature: SKILL.md at root AND substantial executable code (orchestrators, validators, libraries).

Treatment: both divergence models apply. SKILL.md is a skill under skill rules; `bin/` and `quality_gate.py` are code under code rules. Requirements and use cases must span both. Cross-cutting REQs trace prose claims in SKILL.md to code behavior in the orchestrator.

### Classification Mechanism

Classification is a Phase 0 step. Heuristic:

- `SKILL.md` exists at repo root AND prose word count in SKILL.md exceeds code line count across the repo → Skill project
- `SKILL.md` exists at repo root AND substantial code exists alongside it → Hybrid project
- No `SKILL.md` at repo root → Code project

The heuristic is a starting point, not a contract. The Council of Three in Phase 4 re-verifies the classification and can override it with rationale.

The classification result is written to the run manifest and all downstream phases read it to choose derivation strategy.

---

## Design — Skill-Specific Derivation Pipeline

When classification is Skill or Hybrid, the requirements pipeline gets a skill-specific variant. The code pipeline still runs for the code portion of a Hybrid project.

### Architecture: Generate-Then-Verify

The skill pipeline uses a four-pass generate-then-verify architecture. The two halves of the problem — coverage breadth and citation precision — are different tasks with different failure modes, so each pass does what it's best at.

**Pass A (Naive Coverage).** A Haiku-style prompt: "Read the skill. Understand what it does. Produce a comprehensive requirements document organized by functional area with testable acceptance criteria." No citation rigor required. Output: draft REQ list with proposed source references ("I think this comes from the Phase 1 section of SKILL.md"). High recall, low precision — tolerates overreach because Pass B will filter.

Pass A is section-iterative for any skill above a small-input threshold (SKILL.md plus reference files exceeding a few hundred lines total). Rather than one prompt over the entire skill, Pass A walks the SKILL.md section tree in order, generating draft REQs for one section at a time, appending to a persistent drafts artifact, and advancing a section cursor. This is a direct response to the failure mode where single-shot generation over long inputs silently drops coverage on later sections under context pressure; the mechanical defense is per-section progress with disk as the ledger. See "Execution Discipline" below.

**Critical constraint:** Pass A can propose source references but CANNOT produce `citation_excerpt` values. Only Pass B is allowed to populate excerpts, and only by mechanical extraction. This prevents hallucinated citations from laundering through.

**Pass B (Citation Extraction).** For each draft REQ from Pass A, mechanically search SKILL.md and reference files for supporting text. Uses grep / structured parsing — not LLM judgment. Populates `citation_excerpt` where found. This is the same mechanical citation extractor v1.5.0 uses for code-project formal docs; no new machinery, repurposed machinery.

**Pass C (Formal REQ Production).** Convert each cited draft into a proper REQ record with tier, ID, full citation schema (per v1.5.0). Drafts with failed citation search either:
- Get rejected (no supporting text exists anywhere; probably a Pass A overreach)
- Get demoted to Tier 5 (inferred from behavior, not documented) with a note

**Pass D (Coverage Audit).** Diff Pass A's full draft list against Pass C's verified formal list. Draft REQs without formal equivalents need explicit rejection rationale. This catches the case where mechanical citation extraction missed something that should have been found — either the extractor needs a second try, or the Pass A item was an overreach, but the decision is explicit rather than silent.

This architecture means each pass does one thing well: Pass A brings coverage (the Haiku strength), Pass B brings mechanical citation discipline (the v1.5.0 strength), Pass C brings formal structure, Pass D brings accountability for what the earlier passes missed or dropped.

### Execution Discipline — Disk is the Ledger

A generate-then-verify pipeline is only as reliable as its per-pass persistence. When any pass runs long — Pass A against a multi-thousand-line SKILL.md plus reference files, Pass B mechanically searching every draft REQ, Pass C converting hundreds of cited drafts into formal records — it must survive interruption and LLM auto-compaction without losing coverage. Three invariants follow, and they are correctness constraints, not performance optimizations:

1. **Disk is the source of truth, not the model's working context.** Every pass writes its incremental output to a persistent artifact before advancing its cursor. The artifact — not the conversation history — is what the next pass reads. Intermediate artifacts are structured (JSONL for draft lists, JSON for progress state) so that downstream passes can resume without re-parsing unstructured prose.

2. **Each pass has a cursor and resumes from it.** Pass A iterates sections of SKILL.md and reference files; Pass B iterates Pass A drafts; Pass C iterates cited drafts; Pass D iterates the Pass A list for diff. Each iteration updates a progress file atomically (tmp + rename) *after* the unit of work lands on disk. Killing a pass mid-run and restarting it continues from the last cursor position, not from scratch.

3. **Compaction is routine, not exceptional.** Any LLM-driven pass prompt includes an explicit recovery procedure — re-read the pass instructions, read the progress file, verify continuity against the last-written artifact, resume from the cursor — because the prompt cannot assume its own working memory persists across an auto-compaction event.

The empirical basis for these invariants: prior summarizer work on a comparable-scale input (14MB of chat history, thousands of records per file) showed that unbounded single-shot LLM generation over large inputs degrades into templated stub output or silently-skipped input regions once context pressure rises. The only mechanical defense is per-unit progress with disk as the ledger. Pass A over a 1,500-line SKILL.md plus multiple reference files is structurally the same problem; the pipeline treats it as such from the start rather than discovering it under load.

### Why This Maps to Existing Infrastructure

For code projects, the existing Phase 1 exploration IS the naive coverage pass — it explores the codebase, identifies modules and risks, generates hypotheses. That implicit coverage pass is what the skill-project path was missing: because QPB classifies SKILL.md as "documentation" rather than "the thing being explored," exploration-style coverage never happened for skills.

Pass A is the skill-equivalent of Phase 1 exploration that code projects already have. For Hybrid projects, both explorations happen in parallel — code exploration for the `bin/` and `quality_gate.py`, skill exploration for SKILL.md and reference files.

### Section-to-REQ Example

SKILL.md section "Phase 1: Explore the Codebase" contains "write incremental findings to quality/EXPLORATION.md as each subsystem is explored."

After Pass A: draft REQ "Phase 1 must produce EXPLORATION.md" with proposed source reference "Phase 1 section."
After Pass B: mechanical extractor finds the exact sentence, populates `citation_excerpt`.
After Pass C:
```
REQ-101: Phase 1 produces quality/EXPLORATION.md
  tier: 1 (skill's own SKILL.md is the formal spec)
  source_type: skill-section
  skill_section: "Phase 1: Explore the Codebase"
  citation:
    document: SKILL.md
    section: "Phase 1: Explore the Codebase"
    line: <actual line number>
    citation_excerpt: "write incremental findings to quality/EXPLORATION.md as each subsystem is explored"
```

The tier-1 citation uses the v1.5.0 citation schema unchanged. `SKILL.md` becomes a Tier 1 formal doc when it's the thing being specified (Skill/Hybrid projects), which is a semantic but not structural change.

### Reference-File Coverage

Passes A through D also run over each reference file (`references/exploration_patterns.md`, `references/review_protocols.md`, etc.). Cross-references between SKILL.md and reference files are noted — if SKILL.md says "see exploration_patterns.md for details" and the reference file describes a different pattern than SKILL.md implies, that's an internal divergence (see below).

### Use Cases from Execution Modes

UCs come from the skill's documented execution modes, not invented from high-level user stories. For QPB, this produces use cases like:

- UC-01: Interactive user runs Phase 1
- UC-02: Interactive user continues to Phase 2
- UC-03: Benchmark operator runs non-interactively
- UC-04: Bootstrap self-audit
- UC-05: Iteration mode (gap strategy)
- (etc.)

Haiku's 10 UCs are a reasonable starting template for QPB's own case. For other skills, the equivalent comes from reading their SKILL.md for mode/trigger/protocol sections. The naive Pass A is also the right generator for UCs — same prompt style, same coverage bias.

### Completeness Audit

Every operational section of SKILL.md must produce at least one REQ after Pass D. Sections that produce zero REQs flag as a completeness gap — either the section is unnecessary prose (candidate for removal) or the derivation missed something.

This is the skill analog of "every code module should have requirements." It's a mechanical check enforceable by the quality gate.

### Narrative

Same as the code pipeline: consolidate into REQUIREMENTS.md with functional sections, use cases, traceability. The structure follows the skill's own organization (phase-by-phase) rather than being invented.

---

## Design — Divergence Verification for Skills

The v1.5.0 defect definition ("divergence between documented intent and code implementation") extends to three skill-specific categories:

### Category A: Internal Divergence

Within-prose contradictions. SKILL.md section X says "do Y." Reference file Z contradicts X. Or SKILL.md says the gate checks 45 items in one paragraph and 43 items in another.

Detectable statically by comparing citations across REQs. If two Tier 1 REQs with citations to the same document disagree, that's a bug with disposition `spec-fix` (one or both sections need to be updated).

### Category B: Prose-to-Code Divergence

SKILL.md prose makes a claim about code behavior. Code doesn't match.

Example: SKILL.md says "the quality gate runs 45 mechanical checks." `quality_gate.py` runs 43 checks. Either the prose is stale (`spec-fix`) or the code is incomplete (`code-fix`).

Detectable statically by mapping each prose claim about code to the code artifact that implements it. This is similar to citation verification in v1.5.0 but the "formal doc" and the "implementation" are within the same repo.

### Category C: Execution Divergence

SKILL.md says Phase 1 produces artifact X with properties Y. Actual benchmark runs produce X' or fail the gate checks that Y implies.

**Scope constraint (explicit, load-bearing):** execution divergence in v1.5.3 is detected by aggregating *existing `quality_gate.py` results across archived runs*, NOT by building a new LLM evaluation harness. The gate already mechanically evaluates each run — when EXPLORATION.md has < 120 lines, when artifact counts don't match, when required sections are missing, the gate already catches it. v1.5.3's job is to recognize patterns across multiple runs.

Three constraints on the execution divergence implementation:

1. **Consume, don't produce.** v1.5.3 reads existing gate outputs from archived runs. No new evaluation machinery. The gate already does the mechanical judgment.
2. **Pattern-match on structured results, not unstructured outputs.** Gate results are structured (check_id, pass/fail, rationale). Aggregating them across runs is a database query, not a parsing problem.
3. **Accept the semantic blind spot explicitly.** Failures that pass the gate but represent real skill violations (LLM ignored the spirit of an instruction while technically satisfying the line-count check) are out of scope. Catching them would require semantic evaluation, which IS the eval harness work. Explicitly parked for later.

What the check produces: bugs with `divergence_type = execution`, citing the SKILL.md promise, the gate check that implements it, and the set of archived runs where the gate failed. Example:

> BUG-X: SKILL.md Phase 1 promises "≥8 concrete findings" (REQ-109). Archived gate results show check `phase1_finding_count >= 8` failed in 3 of 5 runs (run-2026-03-22, run-2026-04-01, run-2026-04-15). Disposition: candidate `spec-fix` (instruction too vague) or `code-fix` (prose needs sharper guidance). Council decides.

Disposition for execution divergences:
- `code-fix` applies to the skill's prose (the agent correctly followed ambiguous prose; tighten the prose)
- `spec-fix` applies to the claim that was too optimistic
- `mis-read` applies when the agent misinterpreted clear prose (LLM failure, not skill failure)

Execution divergence is valuable because it catches real misalignment between what the skill promises and what agents deliver — but its reach is bounded by what the gate can mechanically check. The highest-impact improvements to this check come from making the gate more thorough, not from building new evaluation infrastructure.

---

## Success Criteria

v1.5.3 is successful if:

1. **QPB's self-audit matches the Haiku benchmark.** Running QPB v1.5.3 against itself produces requirements with coverage comparable to the Haiku-generated REQUIREMENTS.md — at least 10 use cases spanning all operational modes, REQs organized by phase covering each phase's artifacts and gates, explicit requirements for SKILL.md sections and reference files. The target is parity with Haiku's 95 REQ count (±20%), structured phase-by-phase.

   **Coverage diff test:** Pass A's full draft list run against QPB should be within 10% of Haiku's REQ count. Pass D (coverage audit) should produce an explicit rejection rationale for every draft REQ that didn't make it into the formal list — no silent drops. This is the falsifiable check on whether the generate-then-verify architecture actually delivers Haiku-level breadth.

2. **Project type classification is correct across the benchmark.** virtio, chi, cobra, express, httpx all classify as Code. QPB classifies as Hybrid. A pure-skill test fixture (create one if none exists) classifies as Skill.

3. **Execution divergence catches at least one real bug in QPB's own bootstrap history.** Across the archived `previous_runs/` directories, at least one "skill promises X, actual run produced X'" divergence exists. v1.5.3 should surface it.

4. **Cross-model consistency.** Running v1.5.3 against QPB with claude-opus, claude-sonnet, and copilot+gpt produces self-audits with comparable coverage (within 20% REQ count, same use case set).

5. **No regression on code projects.** The five code-project benchmark runs (virtio, chi, cobra, express, httpx) produce bug yields within ±10% of the v1.5.0 baseline.

---

## Provenance

### The Haiku demonstration (2026-04-19)

Andrew ran a session with claude-haiku-4-5-20251001 that exposed the gap. The full chat is preserved at `AI Chat History/Cowork-2026-04-19-Haiku QPB requirements analysis.md`. Key sequence:

1. First prompt asked Haiku to answer three questions about the system given docs_gathered and REQUIREMENTS.md. Haiku correctly identified the coverage gap: "What REQUIREMENTS.md does NOT cover: the skill definition itself (SKILL.md — ~1,500 lines, the operational playbook), phase-specific reference files, the orchestrator agent prompts and interactive execution paths."

2. Second prompt asked Haiku to generate a comprehensive REQUIREMENTS.md covering the entire skill, explicitly instructing it to "use the requirements documentation to understand the rationale and intent behind the features in the skill, and make sure the use cases completely reflect that intent."

3. Haiku produced a 2,129-line document with phase-organized REQs and 10 use cases — substantially more comprehensive than QPB's self-audit despite using a smaller model with a simple two-turn interaction.

### Andrew's reframing

Andrew's message introducing the problem: "The Quality Playbook does a great job with code, but it's still lacking for AI skills. The main problem is that it doesn't capture the actual skill requirements, even when provided the full skill source and a complete AI chat history."

The critical insight: if Haiku can do this with simple prompts, the limitation isn't model capability — it's the skill's own mental model not accommodating the skill-project case.

### Design conversation

The core design move — project type classification at Phase 0 — came from recognizing that the v1.5.0 tier system and divergence model assume spec-and-implementation are distinct artifacts. For AI skills they're not. The classification bifurcates the derivation pipeline so the right model is applied to the right project.

The three-category divergence taxonomy (internal, prose-to-code, execution) emerged from asking "where does a skill's documented intent actually fail?" Internal = prose contradicts itself. Prose-to-code = prose contradicts supporting code. Execution = prose contradicts what agents actually produce. All three are real and each requires different detection machinery.

---

## Out of Scope for v1.5.3

- Runtime skill validation (having QPB actually execute another skill and observe behavior in real time). Execution divergence in v1.5.3 uses archived prior runs, not live runs.
- Automatic skill repair (generating proposed fixes to SKILL.md prose). v1.5.3 detects and reports; repair is future work.
- Skill benchmarking infrastructure (comparing skills to each other on standardized tasks). Adjacent but separate.
- Non-markdown skill formats (skills written in YAML, structured prompts, etc.). v1.5.3 assumes markdown SKILL.md.
- **LLM evaluation harness for semantic divergence.** Detecting cases where the LLM technically satisfies a gate check but ignores the spirit of an instruction (e.g., produces generic reasoning when the prose demands domain-specific reasoning) requires semantic evaluation of LLM outputs. That's a distinct engineering discipline (parsing unstructured outputs, grading intermediate LLM thoughts, statistical reliability frameworks). v1.5.3 does NOT go there. Execution divergence stays bounded by what `quality_gate.py` mechanically checks. Semantic divergence is parked as a potential v1.6+ investigation or as a separate tool.

---

## Open Questions

These don't block v1.5.3 design but need answers during implementation:

1. **How many prior runs are needed for execution divergence to be statistically meaningful?** Lean: 3 minimum, with a confidence note when fewer.

2. **Should reference files each be a separate FORMAL_DOC, or consolidated as one under SKILL.md?** Lean: separate, because they have independent edit histories and can contradict each other.

3. **When SKILL.md is Tier 1 (its own formal spec), what authority resolves SKILL.md-vs-reference-file conflicts?** Lean: SKILL.md wins because it's the primary; reference files are supporting. Explicit precedence rule in `schemas.md`.

4. **Can the Hybrid case have mixed tier distributions (some REQs Tier 1 from SKILL.md, others Tier 1 from an external spec)?** Lean: yes. The tier depends on REQ origin, not project.

5. **What is the unit of iteration for Pass A, and how does it handle nested subsections?** Lean: top-level heading (`##` in SKILL.md) is the default iteration unit. Sections exceeding an implementation-defined line threshold (candidate: 300 lines) get split at the next heading level down. Meta sections (Why This Exists, Overview) and near-empty sections are skipped with an explicit skip-rationale line written to the drafts artifact so Pass D can account for every section even when it produced zero REQs.

6. **What triggers the section-iterative path versus single-shot Pass A?** Lean: any skill where SKILL.md plus reference files together exceed a threshold (candidate: 500 lines total). Smaller skills run Pass A single-shot and skip the cursor machinery. The threshold is tunable and logged in the run manifest.
