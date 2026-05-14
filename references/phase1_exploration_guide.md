## Phase 1: Explore the Codebase (Write As You Go)

**v1.5.7 instrumentation:** Append `phase_start phase=1` to `quality/run_state.jsonl` now. After walking each exploration pattern, append `pattern_walked phase=1 pattern=N findings_count=K`. At phase end, cross-validate (`quality/EXPLORATION.md` ≥ 200 bytes with finding sections) then append `phase_end phase=1`. See "Run-state instrumentation" above.

> **Required references for this phase** — read these before proceeding:
> - `references/exploration_patterns.md` — seven bug-finding patterns to apply after open exploration

**First action: create run metadata.** Before any exploration, create the run metadata file:

```bash
mkdir -p quality/results
cat > "quality/results/run-$(date -u +%Y-%m-%dT%H-%M-%S).json" <<'METADATA'
{
  "schema_version": "1.0",
  "skill_version": "1.5.7",
  "project": "<repo-name>",
  "model": "<model-string>",
  "model_provider": "<provider>",
  "runner": "<tool>",
  "start_time": "<ISO-8601-UTC>",
  "end_time": null,
  "duration_minutes": null,
  "phases_completed": [],
  "iterations_completed": [],
  "bug_count": 0,
  "bug_severity": { "HIGH": 0, "MEDIUM": 0, "LOW": 0 },
  "gate_result": null,
  "gate_fail_count": null,
  "gate_warn_count": null,
  "notes": ""
}
METADATA
```

Fill in `project`, `model` (exact model string, e.g., `"claude-sonnet-4-6"`), `model_provider` (e.g., `"anthropic"`, `"openai"`, `"cursor"`), `runner` (e.g., `"claude-code"`, `"copilot-cli"`, `"cursor"`), and `start_time` (UTC ISO 8601). Update this file at the end of each phase — append the completed phase to `phases_completed` and update `bug_count`/`bug_severity` as bugs are confirmed. The final update after the terminal gate fills in `end_time`, `duration_minutes`, and `gate_result`.

**Second action: run v1.5.3 document ingest (before exploring any code).** A single stdlib-only module in `bin/` produces the authoritative documentation record that Phase 1 requirement derivation depends on:

1. **`python -m bin.reference_docs_ingest <target>`** — walks `reference_docs/` in the target repo once. Files under `reference_docs/cite/` are hashed and written to `quality/formal_docs_manifest.json` per `schemas.md` §4 and the §1.6 manifest wrapper. Files at the top level of `reference_docs/` are not written to the manifest but are available as Tier 4 context via `bin.reference_docs_ingest.load_tier4_context(<target>)`, which returns a sorted list of `(path, text)` tuples. If the ingest command fails (unsupported extension, non-UTF-8 bytes), stop the run and surface the stderr output to the user verbatim — ingest errors are actionable and must be fixed before exploration continues.

**No sidecar needed.** Folder placement is the flag: top-level `reference_docs/<name>.<ext>` files are Tier 4 context; files under `reference_docs/cite/<name>.<ext>` are citable sources. Tier 1 is the default for `cite/` contents; a file may override to Tier 2 with an optional in-file marker on the first non-blank line: `<!-- qpb-tier: 2 -->` (Markdown) or `# qpb-tier: 2` (plaintext). `README.md` under either folder is skipped.

**When `reference_docs/` is missing or empty**, Phase 1 MUST print this actionable message and proceed:

> Phase 1 found no documentation in reference_docs/. The playbook will proceed
> using only Tier 3 evidence (the source tree itself). For better results, drop
> plaintext documentation into:
>   reference_docs/            ← AI chats, design notes, retrospectives (Tier 4 context)
>   reference_docs/cite/       ← project specs, RFCs, API contracts (citable, byte-verified)
> See README.md "Step 1: Provide documentation" for details.

**Plaintext only — conversion happens outside the playbook.** Reference docs are `.txt` or `.md` only (schemas.md §2). PDFs, DOCX, HTML, etc. are rejected with an actionable conversion hint (`pdftotext`, `pandoc -t plain`, `lynx -dump`). Do NOT attempt to parse binary or formatted documents inside the skill — run the conversion outside and commit the plaintext.

Spend the first phase understanding the project. The quality playbook must be grounded in this specific codebase — not generic advice.

**Why explore first?** The most common failure in AI-generated quality playbooks is producing generic content — coverage targets that could apply to any project, scenarios that describe theoretical failures, tests that exercise language builtins instead of project code. Exploration prevents this by forcing every output to reference something real: a specific function, a specific schema, a specific defensive code pattern. If you can't point to where something lives in the code, you're guessing — and guesses produce quality playbooks nobody trusts.

**Scaling for large codebases:** For projects with more than ~50 source files, don't try to read everything. Focus exploration on the 3–5 core modules (the ones that handle the primary data flow, the most complex logic, and the most failure-prone operations). Read representative tests from each subsystem rather than every test file. The goal is depth on what matters, not breadth across everything.

**Depth over breadth (critical).** A narrow scope with function-level detail finds more bugs than a broad scope with subsystem-level summaries. For each core module you explore, identify the specific functions that implement critical behavior and document them by name, file path, and line number. Requirements derived from "the reset subsystem should handle errors" will not catch bugs. Requirements derived from "`vm_reset()` at `virtio_mmio.c:256` must poll the status register after writing zero" will. The difference between a useful exploration and a useless one is specificity — file paths, function names, line numbers, exact behavioral rules.

**Three-stage exploration: open first, then domain risks, then selected patterns.** Exploration has three stages, and the order matters:

1. **Open exploration (domain-driven).** Before applying any structured pattern, explore the codebase the way an experienced developer would: read the code, understand the architecture, identify risks based on your domain knowledge of what goes wrong in systems like this one. Ask yourself: "What would an expert in [this domain] check first?" For an HTTP library, that means redirect handling, header encoding, connection lifecycle. For a CLI framework, that means flag parsing, help generation, completion/validation consistency. For a serialization library, that means type coverage, round-trip fidelity, edge-case handling. Write concrete findings with file paths and line numbers. This stage must produce at least 8 concrete bug hypotheses or suspicious findings — not architectural observations, but specific "this code at file:line might be wrong because [reason]" findings. At least 4 must reference different modules or subsystems.

2. **Domain-knowledge risk analysis.** After open exploration, step back from the code and reason about what you know from training about systems like this one. This is the primary bug-hunting pass for library and framework codebases. Complete the Step 6 questions below using two sources — the code you just explored AND your domain knowledge of similar systems. Generate at least 5 ranked failure scenarios, each naming a specific function, file, and line, and explaining why a domain-specific edge case produces wrong behavior. You don't need to have observed these failures — you know from training that they happen to systems of this type. Write the results to the `## Quality Risks` section of EXPLORATION.md before proceeding to patterns.

   **What this stage must NOT produce:** A section that lists defensive patterns the code already has (things the code does RIGHT) is not a risk analysis. A section that lists risky modules without specific failure scenarios is not a risk analysis. A section that concludes "this is a mature, well-tested library so basic bugs are unlikely" is actively harmful — mature libraries have the most subtle bugs, precisely because the obvious ones were found years ago. The test: could a code reviewer read each scenario and immediately know what to check? If not, the scenario is too abstract.

3. **Pattern-driven exploration (selected, not exhaustive).** After open exploration and domain-risk analysis are written to disk, evaluate all seven analysis patterns from `exploration_patterns.md` using a pattern applicability matrix. For each pattern, assess whether it applies to this codebase and what it would target. Then select 3 to 4 patterns for deep-dive treatment — the highest-yield patterns for this specific codebase. The remaining patterns get a brief "not applicable" or "deferred" note with codebase-specific rationale. Do not produce deep sections for all seven patterns — depth on 3–4 beats shallow coverage of 7. Select 4 when a fourth pattern has clear applicability and would cover code areas not reached by the other three; default to 3 when in doubt.

   For each selected pattern deep dive, use the output format from the reference file and trace code paths across 2+ functions. The deep dives should pressure-test, refine, or extend the findings from the open exploration and risk analysis — not repeat them.

The Phase 1 completion gate checks for all three stages. The open exploration section, the quality risks section, the pattern applicability matrix, and the pattern deep-dive sections must all be present.

**Write incrementally — do not hold findings in memory.** This is the single most important execution rule in Phase 1. After you explore each subsystem or apply each pattern, **immediately append your findings to `quality/EXPLORATION.md` on disk before moving to the next subsystem or pattern.** Do not try to hold findings in working memory across multiple subsystems. The write-as-you-go discipline serves two purposes:

1. **Depth recovery.** If you explore the PCI interrupt routing subsystem and find suspicious code at `vp_find_vqs_intx()`, write that finding to EXPLORATION.md immediately. Then when you move to the admin queue subsystem, your working memory is free to go deep there. Without incremental writes, findings from the first subsystem compete with findings from the second, and both end up shallow.

2. **Nothing gets lost.** In v1.3.41 benchmarking, the model explored 8 pattern sections but wrote only 5–7 lines per section — perfectly uniform, perfectly shallow. Every section passed the gate but none went deep enough to find bugs that require tracing code paths across multiple functions. The model was trying to compose the entire EXPLORATION.md at the end, after reading everything, and could only recall the surface-level findings. Incremental writes prevent this.

**The rhythm is: read a subsystem → write findings to disk → read the next subsystem → append findings → repeat.** Each append should include specific function names, file paths, line numbers, and concrete bug hypotheses. A 5-line section that says "checked cross-implementation consistency, found one gap" is a gate-passing placeholder, not an exploration finding. A useful section traces a code path: "function A at file:line calls function B at file:line, which does X but not Y; compare with function C at file:line which does both X and Y."

**Mandatory consolidation step.** After all three stages (open exploration, quality risks, and selected pattern deep dives) are explored and written to EXPLORATION.md, add a final section: `## Candidate Bugs for Phase 2`. This section consolidates the strongest bug hypotheses from all earlier sections into a prioritized handoff list. For each candidate, include: the hypothesis, the specific file:line references, which stage surfaced it (open exploration, quality risks, or pattern), and what the code review should look for. This section is the bridge between exploration and artifact generation — it tells Phase 3 exactly where to focus. Minimum: 4 candidate bugs with file:line references — at least 2 from open exploration or quality risks, and at least 1 from a pattern deep dive. There is no maximum.

**Pre-flight: Scope declaration for large repositories**

Before exploring any source code, estimate scale: approximate source-file count (excluding tests, docs, and generated files), major subsystem count, and documentation volume. Note the count in PROGRESS.md.

- **Fewer than 200 source files:** Proceed with full exploration. The depth-vs-breadth guidance above still applies.
- **200–500 source files:** Declare your intended scope before exploring. Write a `## Scope declaration` section to PROGRESS.md naming the 3–5 subsystems you will cover, the expected file count for each, and which subsystems you are deferring with rationale. Then proceed with exploration of the declared scope only.
- **More than 500 source files:** Stop and write a mandatory scope declaration to PROGRESS.md before reading any source files. The scope declaration must include: (a) the subsystems covered in this run, (b) the subsystems explicitly deferred, (c) the exclusion rationale for each deferred subsystem, and (d) recommended subsystem scope for follow-on runs. Do not begin exploration until this is written. A scope declaration that covers "everything" is not valid for repositories above this threshold.

**Resuming a previous session:** If PROGRESS.md already exists and shows phases marked complete, read it first. Do not redo phases already marked complete — resume from the first phase marked incomplete. If a scope declaration is already written, honor it exactly. If the previous session's scope declaration deferred subsystems, do not expand scope to cover them unless this run is explicitly a follow-on for the deferred areas.

**Specification-primary repositories:** Some repositories ship a specification, configuration, or protocol document as their primary product, with executable code as supporting infrastructure. Examples: a skill definition with benchmark tooling, a schema registry with validation scripts, a pipeline config with orchestration helpers. When the primary product is a specification rather than executable code, derive requirements from the specification's internal consistency, completeness, and correctness — not just from the executable code paths. The specification is the thing users depend on; the tooling is secondary. If you find yourself writing 80%+ of requirements about helper scripts and <20% about the primary specification, you have the focus inverted.

### Step 0: Ask About Development History

Before exploring code, ask the user one question:

> "Do you have exported AI chat history from developing this project — Claude exports, Gemini takeouts, ChatGPT exports, Claude Code transcripts, or similar? If so, point me to the folder. The design discussions, incident reports, and quality decisions in those chats will make the generated quality playbook significantly better."

If the user provides a chat history folder:

1. **Scan for an index file first.** Look for files named `INDEX*`, `CONTEXT.md`, `README.md`, or similar navigation aids. If one exists, read it — it will tell you what's there and how to find things.
2. **Search for quality-relevant conversations.** Look for messages mentioning: quality, testing, coverage, bugs, failures, incidents, crashes, validation, retry, recovery, spec, fitness, audit, review. Also search for the project name.
3. **Extract design decisions and incident history.** The most valuable content is: (a) incident reports — what went wrong, how many records affected, how it was detected, (b) design discussions — why a particular approach was chosen, what alternatives were rejected, (c) quality framework discussions — coverage targets, testing philosophy, model review experiences, (d) cross-model feedback — where different AI models disagreed about the code.
4. **Don't try to read everything.** Chat histories can be enormous. Use the index to find the most relevant conversations, then search within those for quality-related content. 10 minutes of targeted searching beats 2 hours of exhaustive reading.

This context is gold. A chat history where the developer discussed "why we chose this concurrency model" or "the time we lost 1,693 records in production" transforms generic scenarios into authoritative ones.

If the user doesn't have chat history, proceed normally — the skill works without it, just with less context.

**Autonomous fallback:** When running in benchmark mode, via `bin/run_playbook.py` (benchmark runner, not shipped with the skill), or without user interaction (e.g., `--single-pass`), skip Step 0's question and proceed directly to Step 1. If chat history folders are visible in the project tree (e.g., `AI Chat History/`, `.chat_exports/`), scan them without asking. If no chat history is found, proceed — do not block waiting for a response that won't come.

### Step 1: Identify Domain, Stack, and Specifications

Read the README, existing documentation, and build config (`pyproject.toml` / `package.json` / `Cargo.toml`). Answer:

- What does this project do? (One sentence.)
- What language and key dependencies?
- What external systems does it talk to?
- What is the primary output?

**Find the specifications.** Specs are the source of truth for functional tests. Search in order: `AGENTS.md`/`CLAUDE.md` in root, `specs/`, `docs/`, `spec/`, `design/`, `architecture/`, `adr/`, then `.md` files in root. Record the paths.

**If no formal spec documents exist**, the skill still works — but you need to assemble requirements from other sources. In order of preference:

1. **Ask the user** — they often know the requirements even if they're not written down.
2. **README and inline documentation** — many projects embed requirements in their README, API docs, or code comments.
3. **Existing test suite** — tests are implicit specifications. If a test asserts `process(x) == y`, that's a requirement.
4. **Type signatures and validation rules** — schemas, type annotations, and validators define what the system accepts and rejects.
5. **Infer from code behavior** — as a last resort, read the code and infer what it's supposed to do. Mark these as *inferred requirements* in QUALITY.md and flag them for user confirmation.

When working from non-formal requirements, label each scenario and test with a **requirement tag** that includes a confidence tier and source:

- `[Req: formal — README §3]` — written by humans in a spec document. Authoritative.
- `[Req: user-confirmed — "must handle empty input"]` — stated by the user but not in a formal doc. Treat as authoritative.
- `[Req: inferred — from validate_input() behavior]` — deduced from code. Flag for user review.

Use this exact tag format in QUALITY.md scenarios, functional test documentation, and spec audit findings. It makes clear which requirements are authoritative and which need validation.

### Step 1b: Evaluate Documentation Depth

If `reference_docs/` exists, read every file in it before deciding which subsystems to focus on. For each document, classify its depth:

- **Deep** — contains internal contracts, safety invariants, concurrency models, defensive patterns, error handling details, or line-number-level source references. Suitable for deriving requirements.
- **Moderate** — covers architecture and API surface with some implementation detail. Useful for orientation but insufficient alone for requirement derivation.
- **Shallow** — API catalog, feature overview, or marketing-level summary. Lists what exists but not how it works, how it fails, or what contracts it enforces. **Not sufficient for scoping decisions.**

**The scoping rule:** Do not narrow the audit scope to only the subsystems that have deep documentation. If the most complex or most failure-prone module has only shallow documentation, that is a **documentation gap to flag in PROGRESS.md**, not a reason to skip the module. The highest-risk code with the thinnest documentation is where bugs hide — auditing only well-documented areas produces a safe-looking report that misses real defects.

When documentation is shallow for a high-risk area:

1. Note the gap explicitly in PROGRESS.md under a `## Documentation depth assessment` section.
2. Derive requirements from source code directly (doc comments, safety annotations, defensive patterns, existing tests) and tag them as `[Req: inferred — from source]`.
3. Flag the area for deeper documentation gathering in the completeness report.

Record the depth classification for each `reference_docs/` file in PROGRESS.md so reviewers can assess whether the documentation influenced the scope appropriately.

**Coverage commitment table:** After classifying all `reference_docs/` documents, produce this table in PROGRESS.md under the `## Documentation depth assessment` section:

| Document | Depth | Subsystem | Requirements commitment | If excluded: justification |
|----------|-------|-----------|------------------------|---------------------------|

For every **deep** document, map it to the subsystem it covers, then either commit to deriving requirements from it ("will cover in Phase 2") or provide a specific justification that names the tradeoff. A sentence like "out of scope for this run" is not sufficient — the justification must say *why*, e.g., "interpreter JIT is excluded because this run focuses on the parser/compiler/GC pipeline; separate run recommended."

**Gate:** A high-risk subsystem documented deeply in `reference_docs/` must not silently disappear from the requirements set. If a deep document has a "will cover" commitment but produces zero requirements by the end of Step 7, the requirements pipeline is incomplete — go back and derive requirements for the gap before proceeding to Phase 2 artifact generation.

### Step 2: Map the Architecture

List source directories and their purposes. Read the main entry point, trace execution flow. Identify:

- The 3–5 major subsystems
- The data flow (Input → Processing → Output)
- The most complex module
- The most fragile module

### Step 3: Read Existing Tests

Read the existing test files — all of them for small/medium projects, or a representative sample from each subsystem for large ones. Identify: test count, coverage patterns, gaps, and any coverage theater (tests that look good but don't catch real bugs).

**Critical: Record the import pattern.** How do existing tests import project modules? Every language has its own conventions (Python `sys.path` manipulation, Java/Scala package imports, TypeScript relative paths or aliases, Go package/module paths, Rust `use crate::` or `use myproject::`). You must use the exact same pattern in your functional tests — getting this wrong means every test fails with import/resolution errors. See `references/functional_tests.md` § "Import Pattern" for the full six-language matrix.

**Identify integration test runners.** Look for scripts or test files that exercise the system end-to-end against real external services (APIs, databases, etc.). Note their patterns — you'll need them for `RUN_INTEGRATION_TESTS.md`.

### Step 4: Read the Specifications

Walk each spec document section by section. For every section, ask: "What testable requirement does this state?" Record spec requirements without corresponding tests — these are the gaps the functional tests must close.

If using inferred requirements (from tests, types, or code behavior), tag each with its confidence tier using the `[Req: tier — source]` format defined in Step 1. Inferred requirements feed into QUALITY.md scenarios and should be flagged for user review in Phase 7.

### Step 4b: Read Function Signatures and Real Data

Before writing any test, you must know exactly how each function is called. For every module you identified in Step 2:

1. **Read the actual function signatures** — parameter names, types, defaults. Don't guess from usage context — read the function definition and any documentation (Python docstrings, Java/Scala Javadoc/ScalaDoc, TypeScript type annotations, Go godoc comments, Rust doc comments and type signatures).
2. **Read real data files** — If the project has items files, fixture files, config files, or sample data (in `pipelines/`, `fixtures/`, `test_data/`, `examples/`), read them. Your test fixtures must match the real data shape exactly.
3. **Read existing test fixtures** — How do existing tests create test data? Copy their patterns. If they build config dicts with specific keys, use those exact keys.
4. **Check library versions** — Check the project's dependency manifest (`requirements.txt`, `build.sbt`, `package.json`, `pom.xml`/`build.gradle`, `go.mod`, `Cargo.toml`) to see what's actually available. Don't write tests that depend on library features that aren't installed. If a dependency might be missing, use the test framework's skip mechanism — see `references/functional_tests.md` § "Library version awareness" for framework-specific examples.

Record a **function call map**: for each function you plan to test, write down its name, module, parameters, and what it returns. This map prevents the most common test failure: calling functions with wrong arguments.

### Step 5: Find the Skeletons

This is the most important step. Search for defensive code patterns — each one is evidence of a past failure or known risk.

**Why this matters:** Developers don't write `try/except` blocks, null checks, or retry logic for fun. Every piece of defensive code exists because someone got burned. A `try/except` around a JSON parse means malformed JSON happened in production. A null check on a field means that field was missing when it shouldn't have been. These patterns are the codebase whispering its history of failures. Each one becomes a fitness-to-purpose scenario and a boundary test.

**Read `references/defensive_patterns.md`** for the systematic search approach, grep patterns, and how to convert findings into fitness-to-purpose scenarios and boundary tests.

Minimum bar: at least 2–3 defensive patterns per core source file. If you find fewer, you're skimming — read function bodies, not just signatures.

### Step 5a: Trace State Machines

If the project has any kind of state management — status fields, lifecycle phases, workflow stages, mode flags — trace the state machine completely. This catches a category of bugs that defensive pattern analysis alone misses: states that exist but aren't handled.

**How to find state machines:** Search for status/state fields in models, enums, or constants (e.g., `status`, `state`, `phase`, `mode`). Search for guards that check status before allowing actions (e.g., `if status == "running"`, `match self.state`). Search for state transitions (assignments to status fields).

**For each state machine you find:**

1. **Enumerate all possible states.** Read the enum, the constants, or grep for every value the field is assigned. List them all.
2. **For each consumer of state** (UI handlers, API endpoints, control flow guards), check: does it handle every possible state? A `switch`/`match` without a meaningful default, or an `if/elif` chain that doesn't cover all states, is a gap.
3. **For each state transition**, check: can you reach every state? Are there states you can enter but never leave? Are there states that block operations that should be available?
4. **Record gaps as findings.** A status guard that allows action X for "running" but not for "stuck" is a real bug if the user needs to perform action X on stuck processes. A process that enters a terminal state but never triggers cleanup is a real bug.

**Why this matters:** State machine gaps produce bugs that are invisible during normal operation but surface under stress or edge conditions — exactly when you need the system to work. A batch processor that can't be killed when it's in "stuck" status, or a watcher that never self-terminates after all work completes, or a UI that refuses to resume a "pending" run, are all symptoms of incomplete state handling. These bugs don't show up in defensive pattern analysis because the code isn't defending against them — it's simply not handling them at all.

### Step 5b: Map Schema Types

If the project has a validation layer (Pydantic models in Python, JSON Schema, TypeScript interfaces/Zod schemas, Java Bean Validation annotations, Scala case class codecs), read the schema definitions now. For every field you found a defensive pattern for, record what the schema accepts vs. rejects.

**Read `references/schema_mapping.md`** for the mapping format and why this matters for writing valid boundary tests.

### Step 6: Domain-Knowledge Risk Analysis (Code + Domain Knowledge)

**This is the primary bug-hunting pass for library and framework codebases.** Complete it before selecting any structured patterns. Write the results to the `## Quality Risks` section of EXPLORATION.md immediately — do not hold them in memory.

Every project has a different failure profile. This step uses **two sources** — not just code exploration, but your training knowledge of what goes wrong in similar systems.

**From code exploration**, ask:
- What does "silently wrong" look like for this project?
- What external dependencies can change without warning?
- What looks simple but is actually complex?
- Where do cross-cutting concerns hide?

**From domain knowledge**, ask:
- "What goes wrong in systems like this?" — If it's an HTTP router, think about header parsing edge cases (quality values, token lists, case sensitivity), middleware ordering dependencies, and path normalization. If it's an HTTP client, think about redirect credential stripping, encoding detection, and connection state leaking. If it's a serialization library, think about null handling asymmetry, API surface consistency between direct methods and view wrappers, lazy evaluation caching bugs, and round-trip fidelity. If it's a web framework, think about response helper edge cases, configuration compilation chains, and middleware state isolation. If it's a batch processor, think about crash recovery, idempotency, silent data loss, state corruption. If it handles randomness or statistics, think about seeding, correlation, distribution bias.
- "What produces correct-looking output that is actually wrong?" — This is the most dangerous class of bug: output that passes all checks but is subtly corrupted. A response with a `200 OK` but the wrong `Content-Type`. A redirect that succeeds but leaks credentials. A deserialized object that has silently truncated values.
- "What happens at 10x scale that doesn't happen at 1x?" — Chunk boundaries, rate limits, timeout cascading, memory pressure.
- "What happens when this process is killed at the worst possible moment?" — Mid-write, mid-transaction, mid-batch-submission.
- "Where do two surfaces that should behave the same drift on edge inputs?" — Overloads, aliases, sync/async APIs, builder vs direct APIs, direct mutators vs live views/wrappers, stdlib-compatible wrappers vs framework-native surfaces. For Java/Kotlin: `add(null)` vs `asList().add(null)`, `put(key,null)` vs `asMap().put(key,null)`. For Python: constructor encoding vs mutator encoding, sync vs async client behavior.
- "What emits plausible output with subtly wrong metadata?" — Content type, charset, route pattern, ETag strength, byte count, auth/header/cookie propagation, status code, cache validators.
- "What standard grammar or list syntax is being parsed with ad hoc string logic?" — Quality values (`q=0`), comma-separated headers, digest challenges, MIME types with parameters, query strings, enum/keyword sets, cookie merging.
- "What edge-case inputs would a domain expert reach for?" — For HTTP code: `Accept-Encoding: gzip;q=0`, `Connection: keep-alive, Upgrade`, `Content-Type: application/problem+json`. For serialization code: `null` through different API surfaces, values at `Integer.MAX_VALUE + 1`, round-tripping through encode-then-decode. For routing code: overlapping patterns, mounted prefix propagation, same path with different methods.
- "What information does the user need before committing to an irreversible or expensive operation?" — Pre-run cost estimates, confirmation of scope (especially when fan-out or expansion will multiply the work), resource warnings. If the system can silently commit the user to hours of processing or significant cost without showing them what they're about to do, that's a missing safeguard. Search for operations that start long-running processes, submit batch jobs, or trigger expansion/fan-out — and check whether the user sees a preview, estimate, or confirmation with real numbers before the point of no return.
- "What happens when a long-running process finishes — does it actually stop?" — Polling loops, watchers, background threads, and daemon processes that run until completion should have explicit termination conditions. If the loop checks "is there more work?" but never checks "is all work done?", it will run forever after completion. This is especially common in batch processors and queue consumers.

Generate at least 5 ranked failure scenarios from this knowledge. You don't need to have observed these failures — you know from training that they happen to systems of this type. Write them as **specific bug hypotheses with file-path and line-number citations**, ranked by priority. Frame each as: "Because [code at file:line] does [X], a [domain-specific edge case] will produce [wrong behavior] instead of [correct behavior]." Then ground them in the actual code you explored: "Read persistence.py line ~340 (save_state): verify temp file + rename pattern."

**Anti-patterns that fail the gate:** A Quality Risks section that lists defensive patterns the code already has (things the code does right) is not a risk analysis — it is a reassurance exercise and will not find bugs. A section that lists risky modules without specific failure scenarios is not actionable. A section that concludes "this is a mature, well-tested library so basic bugs are unlikely" is actively harmful — mature libraries have the most subtle API-contract and edge-case bugs, precisely because the obvious ones were found years ago. The test: could a code reviewer read each scenario and immediately know what function to open and what input to test? If not, the scenario is too abstract.

### Step 7: Derive Testable Requirements

**Read `references/requirements_pipeline.md`** for the complete five-phase pipeline, domain checklist, and versioning protocol.

This is the most important step for the code review protocol. Everything found during exploration — specs, ChangeLog entries, config structs, source comments, chat history — gets distilled into a set of testable requirements that the code review will verify. The pipeline separates contract discovery from requirement derivation, uses file-based external memory, and includes mechanical verification with a completeness gate.

**Why this matters:** Structural code review catches about 65% of real defects. The remaining 35% are intent violations — absence bugs, cross-file contradictions, and design gaps. These are invisible to code reading because the code that IS there is correct. You need to know what the code is supposed to do, then check whether it does it. That's what testable requirements provide.

**The five-phase pipeline:**

1. **Phase A — Contract extraction.** Read all source files, list every behavioral contract. Write to `quality/CONTRACTS.md`. This is discovery — list everything, even if it seems obvious.
2. **Phase B — Requirement derivation.** Read CONTRACTS.md and documentation. Group related contracts, enrich with user intent, write formal requirements. Write REQ records to `quality/requirements_manifest.json` (source of truth) and render to `quality/REQUIREMENTS.md`. For each requirement, record the `tier` (1–5 per schemas.md §3.1) and — when `tier ∈ {1, 2}` — the `citation` block produced by `bin/reference_docs_ingest` invoking `bin/citation_verifier` per schemas.md §5.4 / §5.5. The LLM does not shell out to `citation_verifier` directly; the excerpt is a product of the ingest pipeline and is re-verified by `quality_gate.py` at gate time. For Tier 3 REQs (code-is-the-spec), cite the source `file:line` in the `description`; citations are for FORMAL_DOC references only and must not appear on Tier 3/4/5 REQs. The tier + citation pair creates the forward link in the traceability chain: reference_docs/cite → requirements → bugs → tests. See the tier/citation framing block later in this step for the full field list and the Tier-1-wins-over-Tier-2 rule.

   **Optional `Pattern:` field on REQs.** A requirement that needs a Phase 3
   compensation grid should declare its pattern class:

   - `Pattern: whitelist` — authoritative list of items, every site must handle
     each one.
   - `Pattern: parity` — symmetric operations that must match
     (encode↔decode, setup↔teardown).
   - `Pattern: compensation` — sites that must compensate for a shared gap.

   Missing the field means no grid. Setting an invalid value fails
   `quality_gate.py`.

   **Preservation rule (Phase 2).** While `Pattern:` is optional in the design
   sense (some REQs are single-site and need no grid), it is REQUIRED to
   preserve when the Phase-1 hypothesis already carried it. Phase 2 must
   transcribe `Pattern:` from EXPLORATION.md to `quality/REQUIREMENTS.md` and
   `quality/requirements_manifest.json` whenever present. Silent omission is a
   documented v1.4.5-regression vector — the Phase 5 cardinality gate cannot
   enforce coverage on a REQ it doesn't know is pattern-tagged. The gate's
   structural backstop (C13.7/Fix 2) cross-checks REQs that carry per-site UC
   references (`UC-N.a`/`UC-N.b` form emitted by Phase 1's Cartesian UC rule)
   and fails the gate if Pattern is missing on such a REQ.

   **Primary-source extraction rule for code-presence claims.** When writing a requirement that asserts specific constants, values, or labels are handled by a specific function (e.g., "the whitelist must preserve X, Y, and Z"), the requirement must distinguish between what the **spec says should be there** and what the **code actually contains**. Extract the actual contents from the code (case labels, map keys, if-else branches) and compare to the spec's list. If a constant appears in the spec but NOT in the code, write the requirement as "must handle X — **[NOT IN CODE]**: defined in header.h:NN but absent from function() at file.c:NN-NN." Do not write "must preserve X" without verifying X is actually preserved. This prevents a contamination chain where a requirement asserts code presence, the code review copies the assertion, the spec audit inherits it, and the triage accepts it — all without anyone reading the actual code. This exact chain was observed in v1.3.17 virtio testing: REQUIREMENTS.md asserted RING_RESET was preserved in a switch, the code review copied the list, three spec auditors inherited the claim, and the bug went undetected.
   **Mechanical verification artifact for dispatch functions (mandatory).** When a contract asserts that a function handles, preserves, or dispatches a set of named constants (feature bits, enum values, opcode tables, event types, handler registries), you must generate and execute a shell command or script that mechanically extracts the actual case labels/branches from the function body **before writing the contract line**. Save the raw output to `quality/mechanical/<function>_cases.txt`. The command must be a non-interactive pipeline (e.g., `awk` + `grep`) that cannot hallucinate — it reads file bytes and prints matches. Example:

   ```bash
   awk '/void vring_transport_features/,/^}$/' drivers/virtio/virtio_ring.c \
     | grep -E '^\s*case\s+' > quality/mechanical/vring_transport_features_cases.txt
   ```

   After execution, read the output file and use it as the sole source of truth for what the function handles. A contract line asserting "function preserves constant X" is **forbidden** unless `quality/mechanical/<function>_cases.txt` contains a matching `case X:` line. If a constant appears in a spec or header but NOT in the mechanical output, the contract must record it as absent: `"must handle X — **[NOT IN CODE]**: defined in header.h:NN but absent from function() per mechanical check."` Downstream artifacts (`REQUIREMENTS.md`, `RUN_SPEC_AUDIT.md`, code review) must cite the mechanical file path when referencing dispatch-function coverage — they may not replace the mechanical output with a hand-written list.

   **Mechanical artifact integrity check (mandatory).** For each mechanical extraction command, also append it to `quality/mechanical/verify.sh` as a verification step. The script must re-run the same extraction pipeline and diff the result against the saved file. Generate `verify.sh` with this structure:

   ```bash
   #!/bin/bash
   # Auto-generated: re-run mechanical extraction commands and verify saved artifacts
   set -euo pipefail
   FAIL=0
   
   # Verify <function>
   ACTUAL=$(awk '/void vring_transport_features/,/^}$/' drivers/virtio/virtio_ring.c | grep -nE '^\s*case\s+')
   SAVED=$(cat quality/mechanical/vring_transport_features_cases.txt)
   if [ "$ACTUAL" != "$SAVED" ]; then
     echo "MISMATCH: vring_transport_features_cases.txt"
     diff <(echo "$ACTUAL") <(echo "$SAVED") || true
     FAIL=1
   else
     echo "OK: vring_transport_features_cases.txt"
   fi
   
   exit $FAIL
   ```

   **Phase 6 must execute `bash quality/mechanical/verify.sh`** and the benchmark fails if any artifact mismatches. This catches a failure mode observed in v1.3.19: the model executed the extraction command but wrote its own expected output to the file instead of letting the shell redirect capture it, inserting a hallucinated `case VIRTIO_F_RING_RESET:` line that the real command does not produce. Re-running the same command in a separate step and diffing against the file detects this tampering.

   **Immediate integrity gate (mandatory, Phase 2a).** Run `bash quality/mechanical/verify.sh` **immediately** after writing each `*_cases.txt` file and **before** writing any contract, requirement, or prose artifact that cites the extraction. If exit code ≠ 0: stop, delete the failed `*_cases.txt`, re-run the extraction command with a fresh shell redirect (do not hand-edit the output), and re-verify. Do not advance to Phase 3/2c until verify.sh exits 0. Save verify.sh stdout and exit code to `quality/results/mechanical-verify.log` and `quality/results/mechanical-verify.exit` as durable receipt files. This gate exists because v1.3.23 showed that deferring verification to Phase 6 allows downstream artifacts (CONTRACTS.md, REQUIREMENTS.md, triage probes) to build on a forged extraction — the model reconciles a discrepancy between requirements and the artifact by corrupting the artifact instead of correcting the requirement.

   **Mechanical artifacts are immutable after extraction.** Once a `*_cases.txt` file has been written by the shell redirect and verified by `verify.sh`, it must not be modified, overwritten, or regenerated for the remainder of the run. If a downstream step discovers a discrepancy between the mechanical artifact and a requirement or contract, the requirement or contract is wrong — not the artifact. Fix the prose, not the extraction. This rule prevents the v1.3.23 failure mode where the model overwrote a correct extraction with fabricated content to match its own narrative.

   **Forbidden probe pattern (triage and verification).** Triage probes, verification probes, and audit assertions must not use `open('quality/mechanical/...')` or `cat quality/mechanical/...` as sole evidence for what a source file contains at a given line. To verify that function F handles constant C at line N, the probe must either: (a) read the source file directly (`open('drivers/virtio/virtio_ring.c')` with line-anchored assertions), or (b) re-execute the same extraction pipeline used by `verify.sh` and check its output. Reading the saved artifact proves only what the artifact says, not what the code says — this is circular verification. In v1.3.23, Probe C validated the forged artifact instead of the source code, passing with fabricated data.

   **Do not create an empty mechanical/ directory.** Only create `quality/mechanical/` if the project's contracts include dispatch functions, registries, or enumeration checks that require mechanical extraction. If no such contracts exist, skip the directory entirely and record in PROGRESS.md: `Mechanical verification: NOT APPLICABLE — no dispatch/registry/enumeration contracts in scope.` Creating an empty mechanical/ directory (or one without verify.sh) is non-conformant — it signals that extraction was attempted and abandoned. Decide before creating the directory: does this project have dispatch-function contracts? If no, don't `mkdir`. If yes, populate it fully.

   **Normative vs. descriptive split.** Requirements and contracts must use normative language ("must preserve," "should handle") for expected behavior. They may only use descriptive language ("preserves," "handles") when the mechanical verification artifact confirms the claim. A requirement that says "the implementation preserves VIRTIO_F_RING_RESET" without a confirming mechanical artifact is non-conformant — write "the implementation **must** preserve VIRTIO_F_RING_RESET" and cite the mechanical check result showing whether the constant is currently present or absent.

3. **Phase C — Coverage verification.** Cross-reference every contract against every requirement. Fix gaps. Loop up to 3 times until coverage reaches 100%. Write to `quality/COVERAGE_MATRIX.md`. The matrix must have **one row per requirement** (REQ-001, REQ-002, etc.) — not grouped ranges like "C-001 to C-007 | REQ-001, REQ-003". Grouped ranges make machine verification impossible and hide gaps.
4. **Phase D — Completeness check + self-refinement loop.** Apply the domain checklist, testability audit, and cross-requirement consistency check. Also verify that every deep document with a "will cover" commitment in the coverage commitment table has at least one requirement traced to it — if not, add requirements for the gap before continuing.

   Write to `quality/COMPLETENESS_REPORT.md` as a **baseline** completeness report (without a `## Verdict` section — the verdict is deferred to Phase 5 post-reconciliation, which produces the only verdict that counts for closure). Then run up to 3 self-refinement iterations: read the report, fix gaps, re-check. Short-circuit when fewer than 3 changes per iteration.
5. **Phase E — Narrative pass.** Add project overview (with overview validation gate), then derive use cases (with use case derivation gate). Both gates must pass before proceeding to category narratives, cross-cutting concerns, and final reordering. This sequencing prevents multi-pass loops where a failed late gate forces re-derivation. Reorder for top-down flow. Renumber sequentially.

**REQUIREMENTS.md must begin with a human-readable overview** that answers: What is this project? What does it do? Who are the actors (users, systems, hardware, protocols)? What are the highest-risk areas? This overview should be useful to someone who has never seen the project before. If the project is a library or driver where all actors are systems, describe the system actors (kernel maintainers, protocol peers, integrators, end-user developers) and their interactions. Do not start with raw scope metadata or HTML comments — lead with a plain-language description.

**Overview validation gate (mandatory).** After writing the overview, perform this self-check before proceeding to use case derivation:

> Does this overview describe the project the way its actual users would recognize it? Specifically:
> - Does it name the project's ecosystem role and real-world significance?
> - Does it identify who depends on it and for what?
> - Would a developer who uses this project daily say "yes, that's what it is and why it matters"?
> - For well-known projects, does it reflect publicly known adoption (e.g., Cobra → kubectl/Hugo/GitHub CLI; Express → millions of Node.js API servers; Zod → form validation/tRPC; Serde → the default Rust serialization layer)?

If the overview reads like it was written by someone who only read the source code and never used the software, revise it before proceeding. The overview sets the frame for everything downstream — feature-oriented use cases and internally focused requirements are symptoms of an overview that only describes the code, not the project.

**Use case derivation (mandatory, runs after overview gate).** Derive 5–7 use cases from the validated overview and gathered documentation, then validate them against the code. Each use case must:

- Describe a **real user outcome**, not a code feature. "Developer builds a CLI tool with nested subcommands, persistent flags, and shell completion" — not "Framework supports command trees."
- Name a **concrete actor** and what they are trying to accomplish. Actors include end-user developers, system administrators, kernel maintainers, protocol peers, integrators, and automated consumers.
- Be **recognizable to an actual user** of the software. For well-known projects, validate use cases against the model's own knowledge of the project, community docs, tutorials, and real-world adoption patterns.
- Connect to at least one requirement through testable conditions of satisfaction.

The pipeline should explicitly ask: "Based on this project's overview, gathered documentation, and known user base, what are the 5–7 most important things real users do with this software?" Derive use cases from that question — not from scanning the code and grouping features into categories.

**Use case validation against code:** After deriving use cases from the overview and docs, verify each one against the codebase. If a use case describes something the code doesn't actually support, revise or remove it. If the code supports an important user outcome that no use case covers, add one. The goal is use cases that are both user-recognizable AND code-grounded.

**Acceptance criteria span check (mandatory, runs after use case derivation).** After use cases are finalized and validated against code, check whether the conditions of satisfaction across all requirements collectively span the project's main behaviors:

> Do these acceptance criteria, taken together, cover the project? Is there a major user-facing behavior described in the overview or use cases that no requirement's conditions of satisfaction would catch if it broke?

For each use case, at least one requirement's conditions of satisfaction must be traceable to it, and at least one linked requirement must be `specific` (not `architectural-guidance`). Use cases with no linked specific requirements indicate a gap. When gaps are found, either: (a) add new requirements or sharpen existing conditions to cover the gap, or (b) revise the use case if it doesn't reflect what the requirements actually protect. Record the results of this check in the completeness report.

Follow the use cases with the individual requirements.

**v1.5.3 tier and citation scheme (schemas.md §3.1, §5).** Every REQ carries a `tier` integer 1–5 per `schemas.md` §3.1:

- **Tier 1** — project's own formal spec (a `FORMAL_DOC` record with `tier=1`; highest authority).
- **Tier 2** — external formal standard (RFC, W3C, ISO, published API contract — a `FORMAL_DOC` record with `tier=2`).
- **Tier 3** — source-of-truth code when no formal spec exists; the code IS the spec.
- **Tier 4** — informal documentation loaded by `bin/reference_docs_ingest.load_tier4_context` from top-level `reference_docs/` (AI chats, design notes, retrospectives).
- **Tier 5** — inferred from code behavior with no documentation backing.

For `tier ∈ {1, 2}`, the REQ also carries a `citation` block per `schemas.md` §5 with `document`, `document_sha256`, at least one of `section`/`line`, and a mechanically-extracted `citation_excerpt`. Do NOT write the excerpt by hand. The excerpt is produced at ingest time by `bin/reference_docs_ingest` invoking `bin/citation_verifier` per the deterministic algorithm in `schemas.md` §5.4 (with section resolution per §5.5) — the LLM consumes the excerpt from `formal_docs_manifest.json`; it never shells out to the verifier directly. Ingest-time extraction is how Layer 1 of the hallucination gate works. If you cannot cite a document in `quality/formal_docs_manifest.json` (with hash and locator), the REQ is at most Tier 3. `page`-only locators are diagnostic-only and are never sufficient.

**Tier-1-wins-over-Tier-2 rule.** When a project's own spec (Tier 1) and an external standard (Tier 2) contradict each other, record the REQ at Tier 1 citing the project's position. A project's documented deviation from an external standard is authoritative intent, not a defect — the `upstream-spec-issue` disposition applies only when the project's spec is silent on the conflict.

**Spec-Gap degradation (valid output state).** If `formal_docs_manifest.json` contains zero `FORMAL_DOC` records covering the project's own behavior, every REQ ends up at Tier 3/4/5 and the run degrades gracefully into a Spec Gap Analyzer. Report the meta-finding "0 Tier 1/2 requirements" in the completeness report as a metric, not a failure. Do NOT fabricate citations to make the tier distribution look richer — `quality_gate.py` re-invokes `bin/citation_verifier` (via `extract_excerpt`) per §5.4 at verification time and rejects any Tier 1/2 REQ whose `citation_excerpt` does not byte-equal the fresh extraction (schemas.md §10 invariant #11).

**`functional_section` is a required field.** Every REQ carries a short `functional_section` string (e.g., `"Authentication"`, `"Bus enumeration"`) that groups related REQs. This is LLM-derived from the code and documentation; there is no predefined ontology. Phase 2's rendering groups REQs under these sections (with a short intro paragraph per section) and the Phase 4 Council reviews the grouping for coherence. See `schemas.md` §6.1.

**Traceability is one-way: REQ → UC.** The REQ carries a `use_cases[]` list of UC-NN IDs. The UC record does NOT carry a `requirements[]` back-link — the reverse direction is derived at render time by querying REQ records for matching entries (schemas.md §7). Do not populate a `requirements[]` field on UC records.

**For each requirement, provide all of these fields:**

- **ID**: `REQ-NNN` (zero-padded three-digit sequence).
- **Title**: Short, one-line statement.
- **Tier**: Integer 1–5 per schemas.md §3.1.
- **Functional section**: Short LLM-derived string (see above).
- **Citation** (required when `tier ∈ {1, 2}`): produced by `bin/reference_docs_ingest` invoking `bin/citation_verifier`; never hand-authored and never invoked directly by the LLM. Shape per schemas.md §5.1.
- **Summary / Description**: State the requirement as a testable assertion: "X must satisfy Y" or "When A, the system must B".
- **User story**: Frame it from the caller's perspective: "As a [role] doing [action], I expect [behavior] **so that** [outcome]." The "so that" clause is mandatory — it forces you to articulate the intent behind the requirement.
- **Implementation note**: How the code achieves this requirement — the mechanism, the relevant code paths, the design choice.
- **Conditions of satisfaction**: Specific, testable scenarios that prove this requirement is met. Include the happy path, edge cases, and failure modes. Each individual contract from Phase A that was grouped into this requirement becomes a condition of satisfaction.
- **Alternative paths**: Multiple code paths, modes, or entry points that must all satisfy the requirement. Alternative paths are where bugs hide.
- **Use cases**: `use_cases[]` — list of `UC-NN` IDs this REQ participates in. One-way forward link.
- **References**: Cite the source — spec section, ChangeLog entry, config field definition, source comment, issue number, or domain knowledge. For Tier 1/2 REQs the `citation` block carries the authoritative locator; free-form references are supplementary.
- **Specificity**: **specific** (testable — must have conditions of satisfaction that a code reviewer can check against a specific code location or behavior; this is the default and counts toward coverage metrics) or **architectural-guidance** (not testable against individual code paths — covers cross-cutting properties like "remain lightweight and stdlib-compatible" or "no_std support"; informs the quality constitution but is not counted in coverage metrics; most projects should have 0–3 architectural-guidance requirements — more than 3 triggers the mandatory self-check below). The category "directional" is retired. Any requirement that would have been "directional" must either be made specific (with testable conditions) or explicitly classified as architectural-guidance.

  **Architectural-guidance self-check (mandatory, runs after requirement derivation).** Count the requirements tagged `architectural-guidance`. Apply both bounds:

  - **Maximum bound (>3):** If the count exceeds 3, stop and re-examine each one. For each, ask: "Can I add a testable condition of satisfaction that a code reviewer could verify against a specific code location?" If yes, reclassify it as `specific` and add the condition. Only requirements that genuinely cannot be verified against any specific code path should remain `architectural-guidance`. A final count above 3 requires an explicit justification per excess requirement explaining why it cannot be made specific.
  - **Minimum bound (0 on 15+ requirements):** If the total requirement count is 15 or more and the `architectural-guidance` count is 0, re-examine the requirements for cross-cutting design invariants. Libraries that span protocol layers, manage resource lifecycles, enforce ordering guarantees, or maintain compatibility contracts (e.g., "remain stdlib-compatible," "preserve no_std support," "maintain wire-format backward compatibility") typically have 1–3 architectural-guidance requirements. Write one sentence in the completeness report explaining why no requirement qualified as architectural-guidance, or reclassify the appropriate requirements.

  Record the count and any reclassifications in the completeness report.

**Do not cap the requirement count.** Derive as many as the project warrants. A small utility might have 20. A mature library might have 100+. The goal is completeness.

**Step 7a: Documentation-to-requirement reconciliation**

Re-read the coverage commitment table from PROGRESS.md. For each deep document you committed to covering ("will cover in Phase 2"), verify that at least one requirement traces to the subsystem it documents. If your requirements cover only some committed subsystems, add requirements for the gaps before completing Step 7.

For each subsystem, record one of the following in PROGRESS.md:
- the requirement IDs that cover it, or
- an explicit exclusion with rationale, risk acknowledgment, and recommended follow-up

A deep-documented subsystem with a "will cover" commitment and zero mapped requirements is a process failure, not a legitimate scope choice. Do not proceed to artifact generation until every commitment is satisfied or explicitly converted to a justified exclusion.

**Step 7b: Code-path → REQ reverse traceability audit (mandatory)**

**Timing: Execute Step 7a and 7b after Phase E completes** (i.e., after the overview validation gate, use case derivation, and acceptance criteria span check have all run). The audit depends on finalized requirements AND finalized use cases.

After requirements derivation is complete, run a reverse traceability audit. Forward traceability (gathered docs → requirements → bugs → tests) is already built into the pipeline. This step checks the reverse direction at code-path granularity: do significant code paths map back to requirement conditions? This is an audit activity — NOT a structural bidirectional link. (Structural traceability in v1.5.3 is one-way REQ → UC per `schemas.md` §7 and is enforced by schema; this audit checks code coverage against REQs, which is a separate concern.)

This operates at **path/branch/helper granularity**, not file level. File-level coverage was 100% in v1.3.13 and still missed two real bugs. The question is not "does this file map to some requirement?" but "does this significant branch map to a requirement clause that states what must be preserved here?"

**Scoped to four categories** (not an open-ended branch audit):

1. **Alternative paths already named in requirements.** If a requirement mentions fallback or alternative paths (e.g., "primary vs. degraded mode," "negotiated vs. default configuration," "sync vs. async"), each alternative must have an explicit **symmetry condition** — a statement of what invariant must hold across both paths. A requirement that says "the system handles both X and Y" without specifying what "handles" means for each is incomplete.

2. **Helpers that translate public constants into runtime behavior.** If a helper function whitelists, filters, or translates between defined constants and runtime behavior (e.g., feature flag gates, codec registry lookups, capability whitelist helpers), it must have a helper-specific requirement enumerating the expected preserved/translated values.

3. **Capability-negotiation and fallback logic.** Code paths where the system negotiates capabilities with an external peer (protocol version negotiation, feature detection, graceful degradation) must have requirements covering both the negotiated-up and negotiated-down paths.

4. **Functions named in prior BUGS.md, VERSION_HISTORY.md, or spec audit outputs.** If a previous run found a bug in a specific function, future runs must show explicit re-check evidence for that function ("known bug class sentinels"). This prevents the "lost requirement" regression class. If prior spec audit outputs exist in `quality/spec_audits/`, read them before running the sentinel check — cross-model findings from council reviews are a high-value source of known bug surfaces.

For each category, check whether the requirements contain specific conditions covering the identified paths. Orphaned paths — significant code paths without requirement coverage — trigger a "coverage gap" marker in the completeness report. These gaps must be resolved (by adding requirement conditions or by providing explicit justification) before the completeness report can declare requirements sufficient.

**Carry-forward rule:** When a prior run's REQUIREMENTS.md exists in the quality directory, the pipeline must read it and check whether any conditions from the prior version were dropped. If conditions were dropped, the pipeline must either: (a) re-derive them with updated justification, or (b) document why the condition is no longer relevant. Silent drops are not permitted — they are a direct cause of regressions where previously learned requirements are lost between runs.

**After the pipeline:** Phase 7 can generate `quality/REVIEW_REQUIREMENTS.md` (interactive review protocol) and `quality/REFINE_REQUIREMENTS.md` (refinement pass protocol). These are not Phase 2 artifacts — they support the Phase 7 interactive improvement paths. The user can review requirements interactively, run refinement passes with different models, and keep versioned backups of each iteration. See `references/requirements_pipeline.md` for the full versioning protocol and backup structure.

Record all requirements in a structured format. These feed directly into the code review protocol's verification and consistency passes.

### Checkpoint: Update PROGRESS.md after Phase 1

**v1.5.7 update — PROGRESS.md is now initialized at run start, not after Phase 1.** Per the "Run-state instrumentation" section earlier in this file, `quality/PROGRESS.md` and `quality/run_state.jsonl` are written before any phase work begins. By this point in Phase 1, both files already exist. This checkpoint is the **Phase 1 completion update** to PROGRESS.md, not the initialization.

The PROGRESS.md format combines the run-state header (Started / Benchmark / Lever / Runner / Playbook version), the phase checklist (now driven by `phase_start` / `phase_end` events from `quality/run_state.jsonl`), and the legacy content sections below (Run metadata, Artifact inventory, Cumulative BUG tracker, etc.) — they are complementary, not competing.

**Phase 1 completion action:** Mark Phase 1 as `[x]` in the phase checklist with summary stats (findings count, patterns walked); add the Phase 1 artifacts (EXPLORATION.md and any sub-artifacts) to the Artifact inventory. Append a `phase_end phase=1` event to `run_state.jsonl` per the cross-validation rules in the Run-state instrumentation section.

**Why PROGRESS.md exists:** In single-session runs, the agent holds context in memory. But context degrades over long sessions — findings from Phase 1 are forgotten by Phase 6, BUG counts drift, spec-audit bugs get orphaned because the closure check never saw them. PROGRESS.md solves this by making every phase write its state to disk. The agent reads it back before each phase, so it always has an accurate picture of what happened so far. As a side benefit, it makes the skill work correctly even if the run is split across multiple sessions.

**Checkpoint discipline for long runs:** After each requirements-pipeline phase (Contracts, Requirements, Coverage Matrix, Completeness, Narrative), update `quality/PROGRESS.md` with: completed phase, artifact paths, current scoped subsystems, remaining work, and exact resume point. This ensures a resumed session can continue from the last completed checkpoint without redoing work. Per v1.5.7, also append the corresponding `pass_started` / `pass_ended` events to `run_state.jsonl`.

**Timestamp discipline:** Write each phase completion entry to PROGRESS.md immediately when you finish that phase, before starting the next phase. Do not batch-write or back-fill timestamps after the fact. The timestamps are an audit trail — if Phase 2 shows a completion time earlier than Phase 1, a reviewer cannot verify that phases ran in the correct sequence. If you realize you forgot to write a checkpoint, write it now with an honest timestamp and a note explaining the gap.

The full PROGRESS.md format the v1.5.7-initialized file will have populated by Phase 1 completion includes the sections below (the agent-maintained deliverable template, retained because Phase 5+ gates depend on its Cumulative BUG tracker and Terminal Gate Verification sections):

**Two PROGRESS.md schemas exist in v1.5.7 — they are distinct, not in drift (v1.5.7 BUG-005 resolution):**

1. **Agent-maintained deliverable form** — the template below. The agent fills it in across Phase 1-5, and Phase 5 finalizes the `## Terminal Gate Verification` section. Phase 6's `check_terminal_gate` (`.github/skills/quality_gate/quality_gate.py`) and `check_version_stamps` enforce this form's sections (`## Terminal` heading, `Skill version:` field). This is the canonical final-deliverable schema.
2. **Automation snapshot form** — produced by `bin/run_state_lib.write_progress_md(quality_dir, events, current_phase)`. Documented in `references/run_state_schema.md` § "PROGRESS.md format". This is a status snapshot the runner can regenerate from `quality/run_state.jsonl` between events (useful for live-status views and resume-from-crash). It is NOT a substitute for the deliverable form below — calling it overwrites the file, so an agent that wants both forms in the same file must merge them or maintain the deliverable form separately.

Adopters using the canonical Mode-B runner (`bin/run_playbook.py`) maintain the deliverable form below. Adopters writing custom orchestrators that need a live status snapshot can additionally call `write_progress_md`, but must do so in a way that doesn't clobber the deliverable's BUG tracker + Terminal Gate sections (e.g., regenerate to a separate file like `quality/RUN_STATUS.md` instead).

```markdown
# Quality Playbook Progress

## Run metadata
Started: [date/time]
Project: [project name]
Skill version: [read from SKILL.md metadata using the reference file resolution order — must match exactly]
With docs: [yes/no]

## Phase completion
- [x] Phase 1: Exploration — completed [date/time]
- [ ] Phase 2: Artifact generation (QUALITY.md, REQUIREMENTS.md, tests, protocols, RUN_TDD_TESTS.md) — `AGENTS.md` is generated by the orchestrator after Phase 6, not here
- [ ] Phase 3: Code review + regression tests
- [ ] Phase 4: Spec audit + triage
- [ ] Phase 5: Post-review reconciliation + closure verification
- [ ] TDD logs: red-phase log for every confirmed bug, green-phase log for every bug with fix patch
- [ ] Phase 6: Verification benchmarks
- [ ] Phase 7: Present, Explore, Improve (interactive)

## Artifact inventory
| Artifact | Status | Path | Notes |
|----------|--------|------|-------|
| QUALITY.md | pending | | |
| REQUIREMENTS.md | pending | | |
| CONTRACTS.md | pending | | |
| COVERAGE_MATRIX.md | pending | | |
| COMPLETENESS_REPORT.md | pending | | |
| Functional tests | pending | | |
| RUN_CODE_REVIEW.md | pending | | |
| RUN_INTEGRATION_TESTS.md | pending | | |
| BUGS.md | pending | | |
| RUN_TDD_TESTS.md | pending | | |
| RUN_SPEC_AUDIT.md | pending | | |
| tdd-results.json | pending | quality/results/ | Structured TDD output |
| integration-results.json | pending | quality/results/ | Structured integration output |
| Bug writeups | pending | quality/writeups/ | One per TDD-verified bug |

## Cumulative BUG tracker
<!-- Every confirmed BUG from code review and spec audit goes here.
     Each entry tracks closure status: regression test reference or explicit exemption.
     The closure verification step reads this list to ensure nothing is orphaned. -->

| # | Source | File:Line | Description | Severity | Closure Status | Test/Exemption |
|---|--------|-----------|-------------|----------|----------------|----------------|
<!-- Closure Status values:
     - "confirmed open (xfail)" — bug exists, regression test confirms it, fix pending
       Language equivalents: Python "xfail", TypeScript/JS "test.fails", Go "t.Skip",
       Java "@Disabled", Rust "compile_fail" (for compile-time bugs). Use the
       language-appropriate term in parentheses, e.g. "confirmed open (@Disabled)"
     - "TDD verified (FAIL→PASS)" — full red-green cycle: test fails on unpatched, passes after fix patch
     - "fixed (test passes)" — bug fixed, regression test now passes, xfail marker removed
     - "exempt (reason)" — no regression test possible, reason documented -->


## Terminal Gate Verification
<!-- Filled in during Phase 5. Must match BUG tracker counts exactly. -->

## Exploration summary
[Brief notes on architecture, key modules, spec sources, defensive patterns found]
```

Update this file after every phase. The cumulative BUG tracker is the most important section — it ensures no finding is orphaned regardless of which phase produced it.

### Write exploration findings to disk

After initializing PROGRESS.md, write your full exploration findings to `quality/EXPLORATION.md`. This file captures everything you learned in Phase 1 so it can survive a context boundary (session break, multi-pass handoff, or long-run memory degradation). Structure it as:

```markdown
# Exploration Findings

## Domain and Stack
[Language, framework, build system, deployment target]

## Architecture
[Key modules with file paths, entry points, data flow, layering]

## Existing Tests
[Test framework, test count, coverage areas, gaps]

## Specifications
[What reference_docs/ contains, key spec sections, behavioral rules]

## Open Exploration Findings
[At least 8 concrete findings from domain-driven investigation.
Each must have a file path, line number, and specific bug hypothesis.
At least 4 must reference different modules or subsystems.
At least 3 must trace a behavior across 2+ functions.]

## Quality Risks
[At least 5 domain-driven failure scenarios ranked by priority.
Each must name a specific function, file, and line and explain the failure
mechanism using domain knowledge of what goes wrong in systems like this.
These are hypotheses, not confirmed bugs — they tell Phase 2 where to look.
Frame each as: "Because [code at file:line] does [X], a [domain-specific
edge case] will produce [wrong behavior] instead of [correct behavior]."
A section that lists defensive patterns the code already has does NOT belong here.]

## Skeletons and Dispatch
[State machines, dispatch tables, feature registries — with file:line citations]

## Pattern Applicability Matrix
| Pattern | Decision (`FULL` / `SKIP`) | Target modules | Why |
|---|---|---|---|
| Fallback and Degradation Path Parity | | | |
| Dispatcher Return-Value Correctness | | | |
| Cross-Implementation Consistency | | | |
| Enumeration and Representation Completeness | | | |
| API Surface Consistency | | | |
| Spec-Structured Parsing Fidelity | | | |

[3 to 4 patterns must be marked FULL. The rest are SKIP with codebase-specific rationale. Select 4 when a fourth pattern clearly applies and covers different code areas.]

## Pattern Deep Dive — [Pattern Name]
[Use the output format from `exploration_patterns.md`.
Trace the relevant code path across 2+ functions, implementations, or API surfaces.
Each deep dive should pressure-test, refine, or extend findings from the open
exploration and quality risks stages.]

## Pattern Deep Dive — [Pattern Name]
[Repeat for each selected FULL pattern. 3 to 4 deep-dive sections total.]

## Pattern Deep Dive — [Pattern Name]
[Third and final deep dive.]

## Candidate Bugs for Phase 2
[Consolidated from ALL earlier sections — open exploration, quality risks, AND patterns.
Minimum 4 candidates with file:line references. At least 2 from open exploration or
quality risks, at least 1 from a pattern deep dive. For each candidate include the
source stage and what the Phase 2 code review should inspect.]

## Derived Requirements
[REQ-001 through REQ-NNN, each with spec basis and tier]

## Derived Use Cases
[UC-01 through UC-NN, each with actor, trigger, expected outcome]

## Notes for Artifact Generation
[Anything the next phase needs to know — naming conventions, test patterns, framework quirks]

## Gate Self-Check
[Written by the Phase 1 gate. Each check 1–12 with PASS/FAIL and one-line evidence.
This section proves the gate was executed. Do not write this section until you have
actually verified each check against the file contents.]
```

**Minimum depth expectation:** EXPLORATION.md must contain at least 120 lines of substantive content — not padding or boilerplate headers, but actual findings (file paths, behavioral rules, derived requirements, architecture observations). A skeleton that lists section headers with one-line placeholders is not a valid handoff artifact. If the file is thinner than this, go back and add the detail Phase 2 will need.

**Re-read after writing (mandatory).** After writing EXPLORATION.md, explicitly read the file back from disk before proceeding to Phase 2. This serves two purposes: (1) it confirms the file was written correctly, and (2) it loads the structured findings into working memory for artifact generation. Do not skip this step and rely on what you remember writing — the "write then read" cycle is the context bridge.

This file is essential in all modes. In single-pass mode it forces the model to articulate specific findings (file paths, function names, line numbers) before generating artifacts. In multi-pass mode it is also the handoff artifact between passes. Either way, the write-then-read cycle is the quality gate for exploration depth.

**Phase 1 completion gate (mandatory — STOP HERE before Phase 2).** You MUST execute this gate before proceeding to Phase 2. This is not optional. Re-read `quality/EXPLORATION.md` from disk and run every check below. After checking, append a `## Gate Self-Check` section to the bottom of EXPLORATION.md that lists each check number (1–12) with PASS or FAIL and a one-line evidence note. If any check fails, fix EXPLORATION.md and re-run the gate. Do not proceed to Phase 2 until all checks pass AND the Gate Self-Check section is written to disk.

**Common gate-bypass failure mode:** In v1.3.43 benchmarking, two repos (chi, zod) produced EXPLORATION.md files with completely wrong section structure — sections like "Architecture summary", "Behavioral contracts", "Repository and architecture map" instead of the required sections. The model never ran the gate checks and proceeded directly to Phase 2, producing zero bugs. If your EXPLORATION.md does not contain sections with the EXACT titles listed below, it is non-conformant and must be rewritten before proceeding.

1. The file exists on disk and contains at least 120 lines of substantive content.
2. `quality/PROGRESS.md` exists and marks Phase 1 complete.
3. The Derived Requirements section contains at least one REQ-NNN with specific file paths and function names — not abstract subsystem descriptions.
4. A section titled **exactly** `## Open Exploration Findings` exists and contains at least 8 concrete bug hypotheses or suspicious findings, each with a file path and line number. These must come from domain-driven investigation, not just from applying patterns. At least 4 must reference different modules or subsystems.
5. **Open-exploration depth check:** At least 3 findings in `## Open Exploration Findings` must trace a behavior across 2 or more functions or 2 concrete code locations. A list of isolated single-function suspicions is not sufficient depth.
6. A section titled **exactly** `## Quality Risks` exists and contains at least 5 domain-driven failure scenarios ranked by priority. Each scenario must: (a) name a specific function, file, and line, (b) describe a domain-specific edge case or failure mode, and (c) explain why the code produces wrong behavior. These must come from domain knowledge about what goes wrong in systems like this one — not from structural analysis of the code alone. A section that lists defensive patterns the code already has (things the code does RIGHT) does not satisfy this gate. A section that lists risky modules without specific failure scenarios does not satisfy this gate. A section that concludes the library is mature and unlikely to have basic bugs does not satisfy this gate.
7. A section titled **exactly** `## Pattern Applicability Matrix` exists and evaluates all six patterns from `exploration_patterns.md`, marking each as `FULL` or `SKIP` with target modules and codebase-specific rationale.
8. Between 3 and 4 patterns (inclusive) are marked `FULL` in the applicability matrix.
9. There are between 3 and 4 sections (inclusive) whose titles begin with `## Pattern Deep Dive — `. Each must contain concrete file:line evidence, not just pattern-name placeholders. The count must match the number of `FULL` patterns in the matrix.
10. **Pattern depth check:** At least 2 of the pattern deep-dive sections must trace a code path across 2 or more functions. A section that says "function X at file:line has a gap" is a surface finding. A section that says "function X at file:line calls function Y at file:line, which does A but not B; compare with function Z which does both" is a depth finding.
11. A section titled **exactly** `## Candidate Bugs for Phase 2` exists and contains at least 4 prioritized bug hypotheses with file:line references, the stage that surfaced each one (open exploration, quality risks, or pattern), and what the code review should look for.
12. **Ensemble balance check:** At least 2 candidate bugs must originate from open exploration or quality risks, and at least 1 must originate from or be materially strengthened by a pattern deep dive. This ensures both domain-knowledge and structural-analysis findings flow into Phase 2.

Do not begin Phase 2 until all twelve checks pass AND the `## Gate Self-Check` section is written to EXPLORATION.md on disk. Phase 1 is your only chance to understand the codebase deeply. Every requirement you miss here is a bug you will not find in Phase 3. Invest the time.

**If you find yourself about to start Phase 2 without having written a Gate Self-Check section, STOP.** Go back and run the gate. This instruction exists because models reliably skip the gate when they feel confident about their exploration — and that confidence is precisely when bugs are missed.

**End-of-phase message (mandatory — print this after Phase 1 completes, then STOP):**

```
# Phase 1 Complete — Exploration

I've finished exploring the codebase and written my findings to `quality/EXPLORATION.md`.
[Summarize: how many candidate bugs, which subsystems explored, key risks identified.]

To continue to Phase 2 (Generate quality artifacts), say:

    Run quality playbook phase 2.

Or say "keep going" to continue automatically.
```

**After printing this message, STOP. Do not proceed to Phase 2 unless the user explicitly asks.**

---
