# Requirements Pipeline

## Overview

This document defines the five-phase requirements generation pipeline for Step 7 of the Quality Playbook. The pipeline separates contract discovery from requirement derivation, uses file-based external memory so the model doesn't need to hold everything in context simultaneously, and includes mechanical verification with a completeness gate.

**Why a pipeline?** Single-pass requirement generation runs out of attention after ~70 requirements because the model is simultaneously discovering contracts and writing formal requirements. Separating these into distinct phases with file-based handoffs produces significantly more complete coverage. In testing on Gson (81 source files, ~21K lines), single-pass produced 48 requirements; the pipeline produced 110.

## Files produced

| File | Purpose |
|------|---------|
| `quality/CONTRACTS.md` | Raw behavioral contracts extracted from source |
| `quality/REQUIREMENTS.md` | Testable requirements with narrative (the primary deliverable) |
| `quality/COVERAGE_MATRIX.md` | Contract-to-requirement traceability |
| `quality/COMPLETENESS_REPORT.md` | Final completeness assessment with verdict |
| `quality/VERSION_HISTORY.md` | Review log with version table and provenance |
| `quality/operator_confirmations.jsonl` | Append-only durable log of interview confirmations (Feature D / F-2a) |

Versioned backups go in `quality/history/vX.Y/`.

---

## Phase A: Extract behavioral contracts

**Input:** All source files in the project (or a scoped subsystem — see scaling check below).
**Output:** `quality/CONTRACTS.md`

### Scaling check

Before starting extraction, count the source files in the project (exclude tests, generated code, vendored dependencies, and build artifacts).

- **Standard project (≤300 source files):** Proceed normally — extract contracts from all files. Projects in this range have been tested end-to-end (e.g., Gson at ~81 source files produced 110 requirements with full coverage).
- **Large project (301–500 source files):** Focus on the 3–5 core subsystems identified in Phase 1, Step 2. Extract contracts from those modules and their internal dependencies. Note the scope in the CONTRACTS.md header so reviewers know what was covered.
- **Very large project (>500 source files):** Recommend that the user scope the pipeline to one subsystem at a time. Each subsystem gets its own pipeline run producing its own REQUIREMENTS.md, CONTRACTS.md, etc. Tell the user: "This project has N source files. For best results, run the requirements pipeline separately for each major subsystem (e.g., 'Generate requirements for the authentication module'). A single pipeline run across the full codebase will miss contracts due to context limits."

If the user explicitly asks for full-project scope on a large codebase, honor the request but warn that coverage will be thinner than subsystem-level runs.

### Scope breadth on the initial pass

On the first pipeline run, favor breadth over depth. Cover all major subsystems and modules rather than going deep on a few. The goal is a broad baseline that the self-refinement loop and the later validation interview can deepen. If you focus on 3 modules and skip 8 others, the completeness check can't find gaps in modules it never saw.

For projects with both a core library and supporting modules (middleware, plugins, adapters, extensions), include at least the core and the highest-risk supporting modules in Phase A. Note the scope in the CONTRACTS.md header so it's clear what was covered and what wasn't. Refinement passes can expand scope later, but the initial pass should cast the widest net the context window allows.

### Contract extraction

Read every source file (within scope) and list every behavioral contract it implements or should implement. A behavioral contract is any promise the code makes to its callers:

- **METHOD**: What a public method guarantees about return value, side effects, exceptions, thread safety
- **NULL**: What happens when null is passed, returned, or stored
- **CONFIG**: What effect a configuration option has at its boundaries
- **ERROR**: What exceptions are thrown, when, and with what diagnostic information
- **INVARIANT**: Properties that must always hold
- **COMPAT**: Behaviors preserved for backward compatibility
- **ORDER**: Whether output/iteration order is stable, documented, or undefined
- **LIFECYCLE**: Resource creation/cleanup, initialization sequencing
- **THREAD**: Thread-safety guarantees or requirements

### Contract extraction rules

- **Be thorough.** For a 200-line file, expect 5–15 contracts. For a 1000-line file, expect 20–40. If you're finding fewer than 3 contracts in a file with real logic, you're skipping things.
- **Include internal files.** Internal contracts matter because the public API depends on them.
- **Include "should exist" contracts** — things the code doesn't do but should based on its domain. These catch absence bugs.
- **Read the code, not just the Javadoc/docstrings.** When documentation and code disagree, list both.
- **This is discovery, not judgment.** List everything, even if it seems obvious.

### Output format

```
# Behavioral Contract Extraction
Generated: [date]
Source files analyzed: N
Total contracts extracted: N

## Summary by category
- METHOD: N
- NULL: N
- CONFIG: N
[etc.]

### path/to/file.ext (N contracts)

1. [METHOD] ClassName.methodName(): description of what it guarantees
2. [NULL] ClassName.methodName(): what happens when null is passed/returned
[etc.]
```

---

### Requirement heading format

All requirements in REQUIREMENTS.md must use the format `### REQ-NNN: Title` where NNN is a zero-padded three-digit number and Title is a short descriptive name. Do not use alternative formats like `### REQ-NNN — Title`, `### REQ-NNN. Title`, `**REQ-NNN**: Title`, or freeform headings without a number. Consistent formatting enables automated tooling to parse and cross-reference requirements.

*This rule is one leg of a three-way binding:* the same format, with a worked example, is authored in `references/phase2_generation_guide.md` § "Requirement heading format" (the doc the Phase 2 generator is routed to) and enforced by `_RENDER_REQ_HEADING_RE` in `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py` — where, per Design §5.3, a populated manifest whose render carries zero `### REQ-NNN:` headings now FAILs rather than skipping. The canonical marker is `### REQ-NNN:`; kept in sync with those two — an edit to one is incomplete without the others.

---

## Phase B: Derive requirements from contracts

**Input:** `quality/CONTRACTS.md`, project documentation, SKILL.md Step 7 template.
**Output:** `quality/REQUIREMENTS.md`

### How to work

**B.1 — Group related contracts.** Many contracts across different files serve the same behavioral requirement. Group them by behavioral concern, not by file. Don't merge unrelated contracts just because they're in the same file.

**B.2 — Enrich with intent.** For each group, find the user story from documentation: GitHub issues state what users expect, the user guide states intended behavior, troubleshooting docs reveal known edge cases, design docs explain design goals. The "so that" clause must come from understanding who cares and why.

**B.3 — Write requirements.** Use the 7-field template from SKILL.md Step 7. Conditions of satisfaction come from the individual contracts in the group — each contract becomes a condition of satisfaction.

**One required behavior per requirement — no disjunctive acceptance.** A requirement, and each of its conditions of satisfaction, states **one** required behavior. It does not offer the implementer a choice, and it does not accept documentation in place of behavior. Reject: "X, or document that not-X"; "rejects **or** clamps"; "acceptable only if documented" without naming where that documentation lives and what it must say; "…or the divergence must be explicitly specified." If genuine alternatives are acceptable, state the decision procedure that selects between them — which is again one required behavior. If the source is itself undecided about which branch is intended, that is a finding for the operator (the coverage-and-gaps statement or the validation interview), not a requirement; a requirement that encodes the derivation's uncertainty transfers it to every downstream test author and reviewer. *(v1.6.0 instruction 002/003: this rule lives on every surface that authors requirement text — `references/phase2_generation_guide.md`, both `bin/skill_derivation/prompts/pass_a_*.md`, and here. The distinction is semantic, not syntactic, so it is a prompt rule with no mechanical gate check: "returns 400 or 422 depending on which validator rejected the payload" is a good requirement and "rejects or clamps" is not, and no regex separates them.)*

**B.4 — Check for orphan contracts.** After writing all requirements, verify every contract in CONTRACTS.md is covered. Uncovered contracts become new requirements or get added to existing requirements' conditions of satisfaction.

### Rules

- **Do not cap the requirement count.** Write as many as the contracts warrant.
- **Every contract must map to at least one requirement.**
- **One requirement per distinct behavioral concern.** Don't merge "thread safety" with "null handling" just because they're in the same class.
- **Do not modify CONTRACTS.md.** Only read it.

---

## Phase C: Verify coverage (loop, max 3 iterations)

**Input:** `quality/CONTRACTS.md`, `quality/REQUIREMENTS.md`
**Output:** `quality/COVERAGE_MATRIX.md`, updated `quality/REQUIREMENTS.md`

For every contract in CONTRACTS.md, determine whether it is covered by a requirement. A contract is "covered" if a requirement's conditions of satisfaction explicitly test the behavior. A contract is NOT covered if it's only tangentially mentioned, implied but not stated, or if a different aspect of the same file is covered but this specific contract isn't.

### Output format

```
# Contract Coverage Matrix
Generated: [date]
Total contracts: N
Covered: N (percentage)
Uncovered: N (percentage)
Partially covered: N (percentage)

## Fully covered contracts
[file]: [contract summary] → REQ-NNN (conditions of satisfaction #M)

## Partially covered contracts
[file]: [contract summary] → REQ-NNN covers the general area but misses [specific aspect]

## Uncovered contracts
[file]: [contract summary] → No requirement addresses this behavior
```

After writing the matrix, fix gaps in REQUIREMENTS.md: add missing conditions to existing requirements or create new requirements. Report changes.

**Loop termination:** If uncovered count reaches 0, proceed to Phase D. Otherwise, regenerate the matrix and check again. Maximum 3 iterations.

---

## Phase D: Completeness check

**Input:** `quality/REQUIREMENTS.md`, `quality/CONTRACTS.md`, `quality/COVERAGE_MATRIX.md`, source tree.
**Output:** `quality/COMPLETENESS_REPORT.md`, updated `quality/REQUIREMENTS.md`

This is the final gate before the narrative pass. Run three checks:

### Check 1: Domain completeness

The following behavioral domains MUST have requirements. Check each one. This checklist is a minimum — if you notice a domain not listed that should have requirements for this project's domain, add it.

- [ ] **Null handling:** explicit null, absent fields, null keys, null values in collections
- [ ] **Type coercion:** string↔number, string↔boolean, number precision, overflow
- [ ] **Primitive vs wrapper:** primitive vs object null semantics during deserialization (for languages with this distinction)
- [ ] **Generic types:** erasure boundaries, wildcard handling, recursive generics (for languages with generics)
- [ ] **Thread safety:** concurrent access, publication safety, cache visibility
- [ ] **Error diagnostics:** exception types, path context, location information
- [ ] **Resource management:** stream closing, reader/writer lifecycle
- [ ] **Backward compatibility:** wire format stability, API behavioral stability
- [ ] **Security:** DoS protection (nesting depth, string length), injection prevention
- [ ] **Encoding:** Unicode, BOM, surrogate pairs, escape sequences
- [ ] **Date/time:** format precedence, timezone handling, precision
- [ ] **Collections:** arrays, lists, sets, maps, queues — empty, null elements, ordering
- [ ] **Enums:** name resolution, aliases, unknown values
- [ ] **Polymorphism:** runtime type vs declared type, adapter/handler delegation
- [ ] **Tree model / intermediate representation:** mutation semantics, deep copy structural independence, null normalization
- [ ] **Configuration:** builder immutability, instance isolation, option composition
- [ ] **Entry points:** every distinct public entry point must have its own contract — string-based, stream-based, tree-based, standalone parsing, multi-value parsing. If the library has N ways to start a read or write, there must be N sets of contracts.
- [ ] **Output escaping:** which characters are escaped by default, what disabling escaping changes, how builder-level and writer-level controls interact
- [ ] **Built-in type handler contracts:** for each built-in handler that processes a standard library type, state what it promises about format, precision, normalization, and round-trip fidelity. The requirement should specify the handler's promise, not just that a handler exists.
- [ ] **Field/property serialization ordering:** whether output order follows declaration order, inheritance order, alphabetical order, or is undefined. State whether ordering is a promised contract or merely observed behavior.
- [ ] **Identity contracts for public types:** `toString()`, `hashCode()`/`equals()` (or language equivalent) on public model types. These are behavioral contracts users depend on for comparison, logging, and collection key usage.
- [ ] **Input validation:** for every configuration field with domain constraints, state the valid range and whether validation exists.

For each domain, either cite the REQ-NNN numbers that cover it or flag it as a gap.

### Check 2: Testability audit

For each requirement, check whether its conditions of satisfaction are actually testable. Can a reviewer write a concrete test case from this condition? Is pass/fail unambiguous? Does the condition cover failure modes, not just the happy path?

### Check 3: Cross-requirement consistency

Check pairs of requirements that reference the same concept. Do ranges agree? Do null-handling rules agree? Do thread-safety guarantees conflict with lifecycle contracts? Do configuration defaults match across requirements?

### Check 4: Cross-artifact consistency (if code review or spec audit results exist)

If `quality/code_reviews/` or `quality/spec_audits/` contain results from a previous or current run, read them. For every finding with status VIOLATED, BUG, or INCONSISTENT, check whether the requirements address the behavioral concern that finding targets. If a code review found a bug in compression header parsing that the requirements don't cover, that's a completeness gap — add a requirement or conditions of satisfaction to close it.

**The completeness report cannot say COMPLETE if unaddressed findings exist.** If any VIOLATED/BUG/INCONSISTENT finding from code review or spec audit targets behavior not covered by requirements, the verdict must be INCOMPLETE with the specific gaps listed.

This check exists because earlier versions of the pipeline produced completeness reports that said "COMPLETE" while the code review in the same run found requirement violations. The completeness report must be consistent with all other quality artifacts.

### Post-review completeness refresh (mandatory)

**After the code review and spec audit are complete**, re-read `quality/COMPLETENESS_REPORT.md` and update it. The initial completeness report was written before the code review and spec audit ran, so it cannot reflect their findings. This refresh step reconciles the completeness verdict with the actual review results.

**Procedure:**
1. Read the combined summary from `quality/code_reviews/` — count VIOLATED and BUG findings.
2. Read the triage summary from `quality/spec_audits/` — count confirmed code bugs.
3. For each finding, check whether REQUIREMENTS.md has a requirement covering that behavior.
4. Append a `## Post-Review Reconciliation` section to COMPLETENESS_REPORT.md:

```
## Post-Review Reconciliation
Updated: [date]

### Code review findings: N VIOLATED, M BUG
- [finding summary] → covered by REQ-NNN / NOT COVERED (gap)
- ...

### Spec audit findings: N confirmed code bugs
- [finding summary] → covered by REQ-NNN / NOT COVERED (gap)
- ...

### Updated verdict
[COMPLETE if all findings are covered by requirements, INCOMPLETE if gaps remain]
```

5. If the original verdict was COMPLETE but unaddressed findings exist, change the verdict to INCOMPLETE.

### Resolving code review vs spec audit conflicts

When the code review and spec audit disagree about the same behavioral claim — one says BUG, the other says design choice or false positive — the reconciliation must resolve the conflict, not paper over it.

**Resolution procedure:**
1. Identify the factual claim at the center of the disagreement. What does the code actually do?
2. Deploy a verification probe: give a model the disputed claim and the relevant source code, and ask it to report ground truth. (See `spec_audit.md` § "The Verification Probe.")
3. Record the resolution in the Post-Review Reconciliation section:
   ```
   ### Conflicts resolved
   - [finding description]: Code review said [X], spec audit said [Y].
     Verification probe: [what the code actually does].
     Resolution: [BUG CONFIRMED / FALSE POSITIVE / DESIGN CHOICE]. [Explanation.]
   ```
4. If the resolution confirms a BUG, ensure it has a regression test. If the resolution overturns a BUG, clean up the regression test per `review_protocols.md` § "Cleaning up after spec audit reversals."

**Do not resolve conflicts by defaulting to one source.** Neither the code review nor the spec audit is automatically more authoritative — they use different methods (structural reading vs. spec comparison) and have different blind spots. The verification probe is the tiebreaker.

**This refresh is not optional.** A completeness report that predates the code review is a timestamp, not a quality gate. The refresh turns it into an actual reconciliation.

### Output format

```
# Completeness Report
Generated: [date]

## Domain coverage
[For each domain: COVERED (REQ-NNN, REQ-NNN) or GAP (description)]

## Testability issues
[For each vague requirement: REQ-NNN — condition N is not testable because...]

## Consistency issues
[For each conflict: REQ-NNN and REQ-NNN disagree about...]

## Cross-artifact gaps (if code review/spec audit results exist)
[For each unaddressed finding: finding summary → missing requirement or condition]

## Verdict
COMPLETE or INCOMPLETE with recommended actions
```

Then fix what you can: add requirements for domain gaps, sharpen vague conditions, resolve consistency issues, and close cross-artifact gaps.

**Important:** This is the final check. Be adversarial. Assume previous passes were imperfect. For each domain marked COVERED, verify that the cited requirements actually address the checklist item — don't just check the box.

### Self-refinement loop (max 3 iterations)

After the initial completeness check, run up to 3 refinement iterations to close the gaps Phase D identified:

1. **Read the completeness report.** Identify all GAP entries, testability issues, and consistency issues.
2. **Fix gaps in REQUIREMENTS.md.** For each GAP: add a new requirement using the 7-field template, or add conditions of satisfaction to an existing requirement. For testability issues: sharpen the condition. For consistency issues: resolve the conflict.
3. **Re-run all three checks** (domain completeness, testability audit, cross-requirement consistency). Write the updated results to COMPLETENESS_REPORT.md.
4. **Count the delta.** How many new requirements were added or existing requirements modified in this iteration?
5. **Short-circuit check:** If the delta is fewer than 3 changes, stop — you've hit diminishing returns. Proceed to Phase E.

**Why this works:** The initial completeness check identifies gaps but the model may not fix all of them in one pass, especially conceptual gaps where the model needs to re-read source files to understand what's missing. Each iteration shrinks the gap. Three iterations is enough to close the mechanical gaps; the remaining conceptual gaps are where cross-model audit and human review earn their keep.

**Why it has limits:** This is self-refinement — the same model checking its own work. It catches gaps the model can see once they're pointed out (uncovered domains, vague conditions, numeric inconsistencies) but won't catch blind spots the model doesn't recognize as gaps. That's by design. The review and refinement protocols exist for closing those deeper gaps with different models or human input.

After the loop completes (or short-circuits), proceed to Phase E.

---

## Phase E: Narrative pass

**Input:** `quality/REQUIREMENTS.md`, `quality/CONTRACTS.md`, project documentation, source tree.
**Output:** Restructured `quality/REQUIREMENTS.md`

**Before starting:** Save a backup: `cp quality/REQUIREMENTS.md quality/REQUIREMENTS_pre_narrative.md`

This phase transforms the specification into a guide. Add explanatory tissue so a new team member, code reviewer, or AI agent can read the document top-to-bottom and understand the software.

**Phase E is mandatory and unconditional (v1.6.0 Feature C).** It is not a polish pass to run when the target is large enough or time allows. Every step below runs on every run, at every target size. The rendered structure Phase E produces is the contract `references/phase2_generation_guide.md` specifies and the Phase 6 gate mechanically enforces — skipping E now FAILs the gate rather than shipping a flat list.

*Why this is now unconditional:* across the three 2026-06-19 benchmark runs, Phase E fired unpredictably — virtio rendered a project overview and cross-cutting concerns; chi and express rendered neither, from the same pipeline and the same skill version. Nothing detected the difference, because the gate validated the manifest and never looked at the rendered document. Unqualified imperatives with no enforcement are how that happens.

**Read `references/phase2_generation_guide.md` § "REQUIREMENTS.md render contract" before starting.** It carries the canonical eight-part document architecture; the steps below are how you get there.

### E.1 — Project overview (mandatory, top of document)

Write 400–600 words of connected prose explaining: what the software is, who uses it and why (primary personas and goals), how data flows through the major components, and the design philosophy (key architectural decisions and why they were made).

Mandatory on every run regardless of target size — a small target is exactly when the reader most needs to know what the derivation understood the system to be. Follow the overview with an **actors & roles** part naming who the requirements serve.

Close the overview with the **coverage-and-gaps statement**: what this derivation covered, and what it knowingly did not — areas explored but not turned into REQs, files skimmed, surfaces out of reach, and why. Be honest rather than flattering; the statement's value is that it makes thin coverage visible. It is advisory (WARN, never FAIL) and it is the opening move of the requirements validation interview.

### E.2 — Use cases (new, after overview)

Write 6–8 use cases in the style of Applied Software Project Management (Stellman & Greene). Each has:

- **Name**: Short descriptive name
- **Actor**: Who initiates it
- **Preconditions**: What must be true before this begins
- **Steps**: Numbered actor/system action sequence
- **Postconditions**: What is true on success
- **Alternative paths**: Variations and error cases
- **Requirements**: Which REQ-NNN numbers this use case exercises

Cover the major usage patterns. The use cases are the bridge between "what the software does" and "what the requirements specify."

### E.3 — Cross-cutting concerns (mandatory whenever there is more than one functional section)

Document architectural invariants that span multiple categories: threading model, null contract, error philosophy, backward compatibility strategy, configuration composition. Each references specific REQ-NNN numbers. Write as prose paragraphs.

Omit this part only when the document has exactly one functional section — with nothing to cut across, the part is meaningless. At two or more sections it is required, and the gate checks for it.

### E.4 — Category narratives (augment existing)

For each requirement category, add 2–4 sentences before the first requirement explaining what the category covers, how it relates to other categories, and what a reviewer should keep in mind.

### E.5 — Choose the organizing principle and order the sections (enforced)

*Revised v1.6.0 (instruction 006, Design §5.2 item 4 "Choosing the organizing principle").* The sections are **not** required to be "functional." There is no single right grouping — IEEE 830 §5.3 lists a menu of organizing principles and holds that the best one is system-dependent. A single mandated principle makes the derivation *slot* requirements into a fixed scheme rather than *decide* how this system's requirements should be organized (a 2026-07-21 `bus-tracker` smoke test mixed four grouping axes because of exactly this). So the derivation chooses the principle, states it, and lets the operator validate the choice in the Feature D interview. Run these six steps, ahead of the E.6 renumber:

1. **Assess the system.** What kind of thing is it? A workflow (favours use-case/journey grouping), a multi-actor system (user-class/stakeholder), a protocol or API surface (stimulus-response/interface), a capability library (feature), a stateful device (mode/state), a domain model (object/entity).
2. **Choose one organizing principle** from the IEEE 830 §5.3 menu: **feature/capability · use case/journey · user class/stakeholder · mode/state · object/entity · stimulus-response/interface · functional hierarchy · a justified combination.** Default to **feature** *only* when no principle clearly fits — the choice, and its rationale, must be stated even then.
3. **Regroup the requirement records** under that principle. Records do not change shape — only their `functional_section` assignment and the section grouping change. This is the same manifest write-back the E.6 renumber performs; extend it to the regrouping. **Propagate every section rename or merge to all records that name a section.** `functional_section` is carried on REQ records and — depending on the producing pipeline — on UC records too (the 2026-06-19 virtio run carried it on all 11 UCs; chi and express on none). A merge that updates only the REQ records leaves UC records naming a section that no longer exists; sweep both manifests for the old name.
4. **Write a section overview per section** (the E.4 category narrative): one short paragraph naming the theme that unifies that section's requirements under the chosen principle — *not* a restatement of its REQ titles. This is what Feature D Stage 2 validates section by section, and the render contract FAILs a section that lacks it.
5. **State the choice** at the top of the section list as a **labeled slot** (v1.6.0 instruction 027): a literal line *`Organizing principle: <name> — Rationale: <text>`* — e.g. *`Organizing principle: user journey — Rationale: this is a workflow system whose requirements cluster around the stages a user moves through.`* The render contract FAILs (structurally) if the slot is absent or its name/rationale is empty (Design §5.2 matrix row 4b); it checks the slot is *present and filled*, not the wording. It does **not** judge whether the choice is *optimal* — that is the Feature D interview (Stage 1) and the Phase 4 *Well-organized* rubric (row 4c).
6. **Order the sections most-relevant-to-the-primary-reader first** (the generalization of the old user-facing → infrastructure rule; for a functional grouping the two coincide), then hand off to E.6's sequential renumber.

Fold **singleton sections** while regrouping: a section holding one REQ either merges into a related section or carries a one-line justification for standing alone. Six single-REQ sections (the 2026-06-19 express shape) mean the grouping conveys nothing.

### E.6 — Renumber sequentially (enforced)

After reordering, renumber all requirements REQ-001 through REQ-NNN following **document order** — the first REQ appearing in the rendered document is REQ-001, with no gaps and no backtracking. Update all internal cross-references.

**Renumber the manifest in the same pass.** `requirements_manifest.json` and the rendered document must agree on every identifier; this is the one sanctioned case where the narrative pass writes back to the manifest. Update every cross-reference that carries a REQ id — REQ records' `use_cases[]`, UC records' `requirements[]`, BUG records' `requirement`, and COVERAGE_MATRIX.md — in the same pass, or the renumber corrupts traceability.

This step was already specified before v1.6.0 and demonstrably did not fire: chi rendered REQ-001/004/005, then 002, then 003/006. It contradicted the older "ordered by REQ id" rendering convention, so an agent following that convention produced scrambled identifiers *by doing what it was told*. That contradiction is now resolved in favor of document order, and the gate checks the result.

### E.7 — Split the tool contract out of the product spec (enforced)

Render every REQ whose `references[]` point exclusively into `quality/` to `quality/RUN_CONTRACT.md`, not to `quality/REQUIREMENTS.md`. These are QPB's own run-layout invariants, not requirements of the audited system. The records stay in the manifest unchanged — only the rendering destination differs. See `references/phase2_generation_guide.md` § "Split the product spec from the tool contract".

### E.8 — Select validation personas (Feature H, v1.6.0 instruction 013)

*Added v1.6.0 (Design §8b "Persona selection — chosen from a catalog, with anchors"). Structurally the E.5 pattern applied to validation lenses: a **menu with per-lens criteria**, a **recorded choice + justification**, and the operator validates the choice. Selection happens here, after the rendered spec exists and ahead of the persona runs (later Feature H slices spawn and merge the personas).* The chosen lenses each run the Feature D interview as a fresh-context domain-expert; before any run, select which lenses fit *this* system and record the choice:

1. **The menu.** `bin/persona_catalog.py` (`catalog()`) is the data-first catalog — a lens id, a `select_when` criterion, and whether it is anchored. The selectable lenses: **API/consumer-integrator** (a library / public API), **operator/SRE** (a deployed service), **data-privacy/compliance** (regulated data), **accessibility** (user-facing UI), **performance** (a hot path), **reliability/failure-mode** (distributed / must survive partial failure), **adopter/end-user** (users whose abandonment risks matter). Adding a lens is a data edit to the catalog.
2. **Two lenses are anchored — always selected, never skippable:** a **domain expert** (specialized per system from the Phase 1 domain + gathered docs, e.g. *"expert in Go HTTP routing and net/http"*) and a **security reviewer**. The anchor is **mechanical, not a prompt suggestion** — a system's own author under-weights security (the 3-persona self-test: the domain lens filed prompt-injection as a mere *candidate* while the anchored security lens *grounded* it). `persona_catalog.select_personas(proposed)` forces both anchors into the selected set regardless of what the derivation proposes, and drops any hallucinated (off-catalog) lens.
3. **Choose the additional lenses** that fit this system from the menu and **state why** each fits — exactly like stating the organizing-principle rationale. Default to no additional lens only when none clearly fits; the anchors are always present.
4. **Record the choice.** `persona_catalog.build_selection_manifest(selected)` produces a reviewable, content-keyed record (chosen lenses + justification + the domain specialization) so an operator can see which experts will validate the spec and why — the same "surface the choice" discipline as the organizing-principle statement and Feature G's classification manifest.

### E.9 — Run the persona validation pass (Feature H, v1.6.0 instruction 021)

*Added v1.6.0 (Design §8b guard 4 + Operator controls; §6 post-Phase-2 placement).* After the requirements finalize (this narrative pass is done) and **before Phases 3–6 build on them**, the pipeline runs the Feature H persona validation pass **automatically** — the same position as Feature D's human interview, except this runs by default (the human interview is opt-in; the agent persona pass is **opt-out**). It is a **remediator, not a gate**: it applies grounded fixes and surfaces them for review; it renders no verdict and blocks nothing.

**Off-switch (default enabled).** A run may disable Feature H entirely (parallel to the human interview being opt-in). When disabled, no personas are spawned, no `agent-validation` changes are written, and the pipeline proceeds on the base manifest.

**The composed step.** `bin/persona_apply.py` `run_feature_h(...)` composes the six modules into one pipeline step — it reimplements no guard:
1. **Select** (E.8): `persona_catalog.select_personas` — the anchored domain + security lenses plus any AI-selected lens.
2. **Stage + spawn (isolated).** `persona_orchestration.run_personas` stages each persona's declared inputs (the classified gathered docs + the rendered `REQUIREMENTS.md` + the rubric) into an isolated per-persona directory (prevention by absence — no impl tree, no secrets, no `operator_confirmations.jsonl`) and the **running agent spawns each persona as a fresh-context, tool-restricted sub-agent** via its Task/Agent tool (Read confined to the staging dir, no shell, no network — the instruction-019 pattern). Each persona descends the Feature D interview and emits a raw candidate diff-set.
3. **Ground** (guard 1): `persona_grounding.classify_diff_set` splits each move into grounded (cited + byte-verified through the citation gate + fit-for-this-system) vs candidate (surfaced, never applied; injection-shaped support is candidate-only even when it byte-verifies).
4. **Merge** (guard 3): union the grounded moves, surface conflicts (never auto-resolve), one terminal E.6 renumber.
5. **Apply + review summary** (guard 4): grounded moves are applied tagged `source_type: agent-validation` (each add carries the **`tier`** of its cited FORMAL_DOC — instruction 028) and flow into Phases 3–6; the **operator-visible review summary** is written to `quality/persona_review_summary.json` — every applied change with its grounding (its `req_id`s are **post-renumber**, instruction 028), plus the conflicts, the candidate bucket, and the maturity disclosure. The change is revertible (`persona_apply.revert`) and every `agent-validation` REQ stays distinguishable from an operator-confirmation downstream (guard 2).

6. **Disclose it to the operator** (instruction 031): the pass changed the operator's requirements, so the end-of-Phase-2 message has to say so. `persona_apply.persona_review_disclosure(review_summary)` renders the plain-language disclosure — expert reviewers ran, what they added / rewrote / removed / agreed with, what they raised that was NOT acted on, where every change and its backing is recorded, and that it can all be undone — for the State P2 block (`references/what_just_happened.md`). It returns `None` when the pass did not run, so a run with no expert review claims none. **The one order for this boundary is: requirements finalize → this pass → re-render `REQUIREMENTS.md` → emit the State P2 block, which carries the requirements-interview offer AND this disclosure together.** The interview offer therefore reaches the operator after the pass, deliberately: they walk the requirements as they now stand.
7. **Make the undo real** (instruction 031). The disclosure tells the operator they can undo the whole thing, so the pass persists the pre-pass manifest to `quality/requirements_manifest.pre_review.json` alongside the two artifacts above. On the operator's request, `persona_apply.revert_from_disk(<target_repo>)` restores `quality/requirements_manifest.json` from that snapshot (exact for adds, corrects and drops, because it is the whole prior manifest rather than a replay) and clears the review artifacts; **re-render `quality/REQUIREMENTS.md` from the restored manifest**, exactly as after the pass itself. Without the snapshot the promise was unkeepable: `revert()` restores from an in-memory field on a `PersonaPass` object that dies with the process that ran the pass, and a dropped requirement's text existed nowhere on disk. The in-process `revert(which=<ids>)` selective path has a known limitation (a `correct` retags the operator's own record, so naming that id deletes it rather than restoring its wording) — which is why the operator-facing undo offers the whole-pass restore only.

**Re-render after the pass (instruction 028).** `run_feature_h` writes the updated `quality/requirements_manifest.json` (the source of truth — the pass applied moves + the terminal E.6 renumber). Because `REQUIREMENTS.md` is AI-authored (the "Feature C renderer" is the agent — `requirements_interview.md` § Write-back), **re-render `quality/REQUIREMENTS.md` from the updated manifest after the persona pass**, exactly as the human-interview write-back does — otherwise the rendered spec silently lags the manifest and the applied agent-validation adds are invisible to a human reader.

The live sub-agent spawn is performed by the running agent (the harness substrate); `run_feature_h` orchestrates the composition. **Spawning these personas is a sanctioned exception to the no-sub-agent guardrail (v1.6.0 instruction 029; SKILL.md Mode A "EXCEPTION: the Feature H persona validation pass may spawn its personas", sibling to the Phase 6 verification exception).** The general no-sub-agent rule still holds for Phases 1–5, but this bounded, operator-visible validation pass — mandatory `persona_review_summary.json`, `agent-validation`-tagged + revertible, opt-out — is not a delegated phase and does not reopen the guardrail's failure modes. A faithful agent at this boundary runs the pass here; it does **not** disable Feature H over a perceived guardrail conflict. This step's guards are all mechanically verified; the empirical acceptance (personas re-surface real gaps under isolation) is instruction 019.

### Rules

- **Do not delete, merge, or weaken any existing requirement.** (Merging *sections* per E.5 is expected; merging requirements is not.)
- **Do not add new requirements in this pass.**
- **Write the overview and use cases from the user's perspective.**
- **Use cases must cite specific REQ numbers.**
- **Do not emit derivation internals into the rendered document** — no HTML comments, no `Asymmetry-promotion:` provenance lines, no cluster annotations, no internal pass vocabulary. That metadata belongs in the manifest.
- **Renumbering is the last step.** Anything that reorders content invalidates the numbers assigned before it.

---

## Versioning protocol

### Version scheme: major.minor

- **Major** bump: structural changes (new pipeline architecture, narrative pass added, major scope expansion). Bumped by the user.
- **Minor** bump: refinement passes, gap fills, sharpened conditions. Increments automatically on each pipeline run or refinement pass.

### VERSION_HISTORY.md

Maintain a version history file at `quality/VERSION_HISTORY.md`:

```markdown
# Requirements Version History

## Current version: vX.Y

| Version | Date | Model | Author | Reqs | Summary |
|---------|------|-------|--------|------|---------|
| v1.0 | YYYY-MM-DD | [model] | Quality Playbook | N | Initial pipeline generation |
| v1.1 | YYYY-MM-DD | [model] | [author] | N | [what changed] |

## Validation interview
[status from quality/REQUIREMENTS_REVIEW.md if a validation interview has run]
```

The **Author** column records provenance: "Quality Playbook" for automated pipeline runs, a person's name for manual edits, a model name for refinement passes.

### Backup protocol

Before each version change, copy all quality files to `quality/history/vX.Y/`:

```
quality/history/
├── v1.0/
│   ├── REQUIREMENTS.md
│   ├── CONTRACTS.md
│   ├── COVERAGE_MATRIX.md
│   └── COMPLETENESS_REPORT.md
├── v1.1/
│   └── ...
└── v2.0/
    └── ...
```

Each version folder is a complete snapshot. Users can diff any two versions.

### Version stamping

Two different version concepts land in the REQUIREMENTS.md header; do not conflate them.

1. **The skill version** — which QPB release produced this artifact. This is the mandatory attribution stamp specified in `references/phase2_generation_guide.md` § "Version stamp", read from SKILL.md `metadata.version`. The Phase 6 gate checks it. Every generated Markdown file carries it.
2. **The requirements-document version** (`vX.Y` above) — this document's own refinement generation, incremented by the minor-bump scheme described earlier in this section. It tracks how many refinement passes the *spec* has been through, and is unrelated to the QPB release.

Render the skill-version attribution stamp first (it is the gate-checked one), then the document-version metadata:

```markdown
# Behavioral Requirements — [Project Name]

> Generated by [Quality Playbook](https://github.com/andrewstellman/quality-playbook) v<SKILL_VERSION> — Andrew Stellman
> Date: YYYY-MM-DD · Project: [Project Name]

Requirements document version: vX.Y
```

`<SKILL_VERSION>` is a placeholder — substitute SKILL.md `metadata.version`, never a literal copied from this file.

**Do not name the pipeline or its passes in the rendered header.** The pre-v1.6.0 template emitted `Pipeline: contract-extraction v2 with narrative pass`; "contract-extraction v2" and "narrative pass" are QPB's internal names for its own derivation stages and mean nothing to the adopter reading the spec. They are derivation internals, and the render contract's C-5 check now rejects them (`references/phase2_generation_guide.md` § "Keep derivation internals out of the render").

---

## After the pipeline: the requirements validation interview

The pipeline produces a solid baseline, but AI derives requirements from the
code and the docs — it cannot know whether it captured the operator's actual
*intent*. That is what the validation interview is for.

**One protocol, `references/requirements_interview.md`.** It walks the rendered
document top-down — the narrative, then each section and its use cases, then
individual requirements on demand — and at every step the operator can
**confirm** (recorded as durable evidence), **correct**, or **add**. Corrections
write straight to `quality/requirements_manifest.json` and re-render, so the spec
absorbs the operator's intent coherently. Entry modes carry over from the
superseded walkthrough: guided, self-guided, and cross-model.

Confirmations survive re-derivation via the append-only
`quality/operator_confirmations.jsonl` (Feature D / F-2a), and the defect log
lands in `quality/REQUIREMENTS_REVIEW.md`, organized by the Wiegers attributes
the readability rubric scores against.

*Superseded (v1.6.0):* the `quality/REVIEW_REQUIREMENTS.md` /
`quality/REFINE_REQUIREMENTS.md` / `quality/REFINEMENT_HINTS.md` review-then-refine
cycle is gone — one interview that applies corrections as they are made, not a
review pass that writes hints for a separate refinement pass to consume.
