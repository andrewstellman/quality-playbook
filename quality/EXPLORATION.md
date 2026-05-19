# Exploration Findings

## Domain and Stack

The repository is a hybrid product: a declarative AI skill (`SKILL.md`, `references/`, `phase_prompts/`, `agents/`) plus a standard-library Python tooling layer that installs, runs, validates, archives, and calibrates the playbook. The primary implementation language is Python 3.8+/3.9+ stdlib-only, with Markdown for skill/protocol content and a small amount of shell for benchmark setup.

The project’s primary output is not a library API; it is a repeatable quality-engineering workflow that emits artifacts into `quality/` and can also audit AI skills as “skill-as-code.” The runtime surfaces that matter most in this repo are:

- `SKILL.md` and `phase_prompts/*.md` for the declarative execution contract.
- `bin/run_playbook.py` for orchestration, prompt routing, gate sequencing, and iteration control.
- `bin/reference_docs_ingest.py` for `reference_docs/` ingest and `quality/formal_docs_manifest.json`.
- `bin/run_state_lib.py` for phase artifact validation and progress/run-state normalization.
- `bin/role_map.py` for Phase 1 file-role tagging, normalization, and activation of the skill-derivation pipeline.
- `bin/install_skill.py` for multi-environment installer behavior.
- `bin/archive_lib.py` and `bin/quality_playbook.py` for archival/indexing and operator-facing subcommands.
- `.github/skills/quality_gate/quality_gate.py` for the mechanical post-run gate.
- `bin/skill_derivation/*.py` for the v1.5.3+ hybrid divergence pipeline.

## Architecture

### Primary declarative surface

- `SKILL.md:24-36` defines the seven-phase contract and positions Phase 1 as the codebase-understanding step that drives everything downstream.
- `SKILL.md:576-1240` is the operative Phase 1 contract: documentation ingest, exploration stages, role-map production, requirements/use-case derivation, and the phase-completion gate.
- `phase_prompts/README.md:1-36` shows the runner/skill split: prompt bodies were externalized so UI-context and runner-driven modes share the same phase text.
- `references/*.md` provide the phase-specific pattern libraries and protocols the skill names explicitly.

### Orchestration and execution path

- `bin/run_playbook.py:831-927` centralizes the six-path install-location fallback guide and loads the externalized phase prompts.
- `bin/run_playbook.py:3254-3331` is the main phased runner path; it prints banners, warns about missing docs, archives previous runs, starts the progress monitor, and executes phase groups.
- `bin/run_playbook.py:3334-3360` is the single-pass / iteration entry path using the same warning and banner logic.
- `bin/quality_playbook.py:39-84` is the operator-facing subcommand dispatcher for archive, migrate, and semantic-check operations.

### Documentation and evidence pipeline

- `bin/reference_docs_ingest.py:189-309` walks `reference_docs/`, classifies top-level vs `cite/`, builds the formal-doc manifest, and exposes Tier 4 context through `load_tier4_context`.
- `bin/bootstrap_self_audit_docs.py:32-62` mirrors bootstrap docs from operator-local `docs_gathered/` into the repo-root `reference_docs/` scaffold for self-audit runs.
- `schemas.md` and `metrics/regression_replay/SCHEMA.md` act as schema contracts for the artifact layer and replay metrics.

### Gate and state-control layer

- `bin/run_state_lib.py:158-245` implements per-phase artifact validation and is the first mechanical backstop between phase transitions.
- `bin/role_map.py:285-338` validates Phase 1 role maps; `bin/role_map.py:759-838` normalizes mechanically derived `breakdown` and `summary` fields before Phase 2.
- `.github/skills/quality_gate.py:1-57` is the documented entrypoint script, while `.github/skills/quality_gate/quality_gate.py:32-62` soft-loads the citation verifier and implements the long mechanical gate.

### Hybrid skill/code divergence pipeline

- `bin/skill_derivation/__main__.py:78-174` is the CLI front door for Phase 3/4 derivation and divergence work.
- `bin/skill_derivation/sections.py:1-61` defines section enumeration rules, execution-mode classification, and cross-reference detection for skill prose.
- `bin/skill_derivation/runners.py:127-229` wraps Claude, Copilot, Codex, and Cursor subprocess runners for pass execution.

### Data-flow summary

1. The skill/prompt layer tells an AI agent what to do.
2. `bin/run_playbook.py` converts that contract into phase prompts, quality tree setup, and phase-group execution.
3. `bin/reference_docs_ingest.py`, `bin/role_map.py`, and `bin/run_state_lib.py` produce/validate the Phase 1 evidence substrate.
4. Phase 2+ artifacts are later checked by `.github/skills/quality_gate/quality_gate.py`.
5. `bin/archive_lib.py` snapshots the run and renders `INDEX.md` / `RUN_INDEX.md`.

## Existing Tests

The repo has a large stdlib-first automated test surface.

- `bin/tests/` contains 75 tracked test modules covering the runner, docs ingest, install flow, role-map logic, run-state validation, derivation passes, replay tooling, and prompt externalization.
- `.github/skills/quality_gate/tests/` contains the gate-specific suite plus challenge/fixture trees. The gate suite is documented as `unittest discover`-first because of the package/module import-shadowing constraint described in `.github/skills/quality_gate/tests/README.md`.
- `pytest/__init__.py` and `pytest/__main__.py` are a local shim so `python3 -m pytest` works without third-party installation.
- The tracked tree also contains 117 fixture/example files, including benchmark snapshots under `repos/` and gate/runner fixtures under `bin/tests/fixtures/` and `.github/skills/quality_gate/tests/fixtures/`.

Coverage focus, by inspection:

- Strong: install fallback order, prompt externalization, role-map normalization, reference-doc ingest edge cases, progress monitor races, runner argument handling, gate schema invariants.
- Weaker or currently missing by direct evidence:
  - Nested non-`cite/` subdirectories under `reference_docs/` as a Tier 4 ingest boundary.
  - Consistency between `docs_present()` and `_evaluate_documentation_state()` for cite-only, README-only, or binary-only trees.
  - Archive bug-count extraction against the canonical `### BUG-NNN: Title` heading form.
  - Bootstrap mirroring of `docs_gathered/cite/` into `reference_docs/cite/`.
  - Direct skill-mode validation of role maps before runner-side normalization.

## Specifications

### Reference docs used in this run

`reference_docs/` is populated with a curated bootstrap/self-audit corpus. The citable subdirectory is empty except for `.gitkeep`, so this run uses rich Tier 4 context but no active Tier 1/2 citable file.

Key Tier 4 inputs:

- `reference_docs/01_README_project.md`, `02_AGENTS.md`, `05_TOOLKIT.md`: user-facing install/run contract and adopter expectations.
- `reference_docs/03_DEVELOPMENT_CONTEXT.md`, `04_BENCHMARK_PROTOCOL.md`: maintainer architecture, benchmark methodology, and active constraints.
- `reference_docs/20-31_*.md`: topical synthesis documents for the 35% intent-gap thesis, the requirements pipeline, Council-of-Three, anti-hallucination invariants, iteration strategies, six-phase orchestration, TDD protocol, recheck, benchmark protocol, and known limitations.
- `reference_docs/50_Quality_Playbook_Patent_Review.md`: claims-level framing of the novel mechanisms.

### Inline specification sources

- `SKILL.md` is the primary behavioral spec for the playbook.
- `phase_prompts/phase1.md` is the operational restatement of the current Phase 1 contract for runner-driven execution.
- `schemas.md` is the formal schema contract for manifests, role maps, and downstream sidecars.
- `references/*.md` are phase-scoped secondary specs.

### Specification summary

- The repo promises a docs-aware, multi-phase quality workflow that can run either directly from the skill prose or via `bin/run_playbook.py`.
- Documentation handling is part of the product contract, not just a convenience: top-level `reference_docs/` files are Tier 4 context, `reference_docs/cite/` files are the citable formal-doc surface, and code-only mode is supposed to be observable and accurate.
- Hybrid-mode correctness depends on cross-surface consistency: install fallback order, documentation-state detection, role-map normalization, and gate expectations must agree across prose, runner code, and validators.

## Open Exploration Findings

1. `bin/run_playbook.py:1560-1575` (`docs_present`) disagrees with `bin/run_playbook.py:1661-1669` (`_evaluate_documentation_state`) on cite-only docs. A temp-tree repro with only `reference_docs/cite/spec.md` returns `docs_present == False` but `_evaluate_documentation_state == "with_docs"`, so the runner can emit a code-only warning even when Phase 1 correctly recognizes documentation.

2. `bin/run_playbook.py:1568-1574` treats any non-dot top-level file in `reference_docs/` or `docs_gathered/` as “docs present,” while `bin/run_playbook.py:1583-1595` only recognizes plaintext `.md`/`.txt` files and skips `README.md`. A repro with `reference_docs/README.md` alone yields `docs_present == True` but `_evaluate_documentation_state == "code_only"`. A repro with `reference_docs/spec.pdf` yields `docs_present == True` while `formal_docs_guard_banner()` still reports the tree as empty of valid docs. That is contradictory operator signaling across the same startup path.

3. `bin/reference_docs_ingest.py:90-94`, `189-227`, and `263-276` recurse the entire `reference_docs/` tree and classify every non-`cite/` file as Tier 4. A temp-tree repro with `reference_docs/nested/archive/notes.md` returns `[('reference_docs/nested/archive/notes.md', ...)]` from `load_tier4_context()`. The documented contract says top-level `reference_docs/<name>` files are Tier 4 context; nested archives should not silently join the prompt budget.

4. `bin/bootstrap_self_audit_docs.py:50-61` mirrors only top-level plaintext files from `docs_gathered/` into `reference_docs/`. It creates `reference_docs/cite/` but never copies any source-side `docs_gathered/cite/` subtree, so bootstrap mirroring can preserve Tier 4 context while dropping the citable formal-doc surface entirely.

5. `bin/run_state_lib.py:171-198` is much weaker than the Phase 1 completion contract in `SKILL.md:1204-1217`. A repro file with 120 lines, `## Domain and Stack`, and `## Open Exploration Findings` but no Quality Risks, no pattern matrix, and no candidate-bug section still returns `(True, "")` from `validate_phase_artifacts(..., 1)`. That means the mechanical phase boundary can advance after a structurally shallow exploration artifact.

6. `bin/archive_lib.py:69` and `321-338` parse bug sections using `_BUG_HEADING_PATTERN = ^###\\s+BUG-...\\s*$`, which does not match the canonical `### BUG-001: Title` format enforced elsewhere. A repro `BUGS.md` with two titled bug headings returns zero counts for every severity/disposition bucket. This directly threatens `INDEX.md` / `RUN_INDEX.md` accuracy and any calibration logic derived from archived bug totals.

7. `phase_prompts/phase1.md:59-69` explicitly tells Phase 1 writers to omit `breakdown` and `summary` from `quality/exploration_role_map.json`, while `bin/role_map.py:252` and `285-322` reject role maps missing those keys. The runner repairs this later via `bin/role_map.py:759-838`, but a direct skill-driven Phase 1 writeout is invalid until that runner-specific normalization step happens. That is a prose-to-code dependency leak.

8. `bin/tests/test_reference_docs_ingest.py:67-77` and `152-164` pin only top-level Tier 4 behavior, while no direct regression test covers nested non-`cite/` directories despite the implementation’s recursive walk. The test surface is therefore aligned with the prose, but the implementation is aligned with a broader runtime behavior. That makes the nested-ingest drift easy to preserve accidentally.

## Quality Risks

1. **Highest risk — documentation-state drift can mis-scope real runs.** Because `bin/run_playbook.py:1560-1575` and `1661-1669` use different predicates, a cite-only repo or a README/PDF-only repo can receive contradictory startup messages. In practice, an operator may believe the run is code-only when it is docs-backed, or docs-backed when it is actually code-only, which changes how they interpret requirements quality and bug confidence.

2. **Nested Tier 4 ingestion can silently blow the prompt budget.** Because `bin/reference_docs_ingest.py:90-94` and `263-276` recurse arbitrary nested directories, a repo that parks `_raw/`, archived chats, or historical snapshots under `reference_docs/` will feed that material into Phase 1 even though the documented contract frames top-level files as the Tier 4 surface. The likely failure mode is context pollution, not a loud error.

3. **The Phase 1 gate can certify shallow exploration.** Because `bin/run_state_lib.py:171-198` only checks file existence, line count, and one broad finding-header regex, a weak `EXPLORATION.md` can pass the mechanical phase boundary and poison every later phase with under-specified requirements and candidate bugs.

4. **Archive metadata can under-report benchmark quality.** Because `bin/archive_lib.py:69` rejects titled bug headings, the archive summary path can record zero bugs for a run whose `BUGS.md` is otherwise canonical. This distorts longitudinal replay metrics and can produce false “regression” or false “improvement” signals in the maintenance loop.

5. **Bootstrap self-audit may lose formal citations while appearing docs-backed.** Because `bin/bootstrap_self_audit_docs.py:50-61` mirrors only top-level files, bootstrap can end up with populated Tier 4 context and an empty `reference_docs/cite/`. That preserves narrative docs but downgrades the strongest citation-backed requirements the self-audit is supposed to exercise.

## Skeletons and Dispatch

The repo has several dispatch-heavy skeletons that are operationally important:

- **Install-path fallback skeleton:** `bin/run_playbook.py:831-838` defines the canonical skill-resolution order; `bin/benchmark_lib.py:52-59` mirrors it for helper resolution; `bin/tests/test_skill_resolution_order.py:31-42` locks the six-path order in tests.
- **Environment detection skeleton:** `bin/install_skill.py:43-64` maps AI-tool markers to install destinations; this is the installer’s primary state machine for environment selection.
- **Phase validation dispatcher:** `bin/run_state_lib.py:158-245` switches on phase number and decides which artifact set is sufficient to advance the run.
- **Archive summarization dispatcher:** `bin/archive_lib.py:321-373` routes archived content through bug counting, requirement tier counting, phase checklist extraction, and gate-verdict extraction.
- **Runner factory:** `bin/skill_derivation/runners.py` plus `bin/skill_derivation/__main__.py:109-173` dispatch among Claude/Copilot/Codex/Cursor subprocess wrappers.
- **Role taxonomy registry:** `bin/role_map.py:120-171` is the fixed taxonomy that activates or suppresses entire later-stage analyses.

These skeletons are load-bearing because the repo’s failure modes are often “surface disagreement” bugs: two dispatch tables or two fallback predicates disagree about what the system should do with the same input.

## Pattern Applicability Matrix

| Pattern | Decision (`FULL` / `SKIP`) | Target modules | Why |
|---|---|---|---|
| Fallback and Degradation Path Parity | `FULL` | `bin/run_playbook.py`, `bin/reference_docs_ingest.py`, `bin/bootstrap_self_audit_docs.py` | The repo relies heavily on fallback behavior: cite vs top-level docs, code-only vs docs-backed mode, root vs installed skill resolution. Parity failures are already visible. |
| Dispatcher Return-Value Correctness | `SKIP` | CLI entry points | There are CLI return-code paths, but they are lower-yield than the cross-surface contract drifts that dominate this repo. |
| Cross-Implementation Consistency | `FULL` | `SKILL.md`, `phase_prompts/phase1.md`, `bin/run_playbook.py`, `bin/run_state_lib.py`, `bin/benchmark_lib.py` | The repo ships the same contract across prose, prompts, helpers, and validators; consistency failures are a primary bug class here. |
| Enumeration and Representation Completeness | `FULL` | `bin/archive_lib.py`, `bin/role_map.py`, `bin/install_skill.py`, `bin/run_playbook.py` | Canonical lists and enum-like registries drive install fallback, role tags, bug parsing, and archive summaries. Missing or mismatched entries are high-value. |
| API Surface Consistency | `FULL` | `bin/run_playbook.py`, `bin/reference_docs_ingest.py`, `bin/bootstrap_self_audit_docs.py` | The same logical concept is exposed through multiple helper APIs (`docs_present`, `_evaluate_documentation_state`, `formal_docs_guard_banner`, ingest/mirror helpers), and they already diverge. |
| Spec-Structured Parsing Fidelity | `SKIP` | `bin/archive_lib.py`, schema parsers | Parsing bugs exist, but the core issue is not external grammar complexity; it is internal format drift and surface disagreement. |

## Pattern Deep Dive — Fallback and Degradation Path Parity

### Documentation-state startup path
- **Primary path:** `bin/run_playbook.py:_evaluate_documentation_state()` at `1661-1669` uses `_reference_docs_plaintext()` at `1583-1595` to decide whether the run is `code_only` or `with_docs`.
- **Fallback / adjacent path:** `bin/run_playbook.py:docs_present()` at `1560-1575` is used by `run_one_phased()` at `3268-3274`, `run_one_singlepass()` at `3341-3346`, and iteration startup at `3698-3703` to emit code-only warnings.
- **Parity gap:** the primary path treats cite-only docs as real docs and ignores README/binary noise; the warning path does not.
- **Candidate requirement:** REQ-001 and REQ-002 below.

### Bootstrap self-audit docs path
- **Primary path:** `bin/reference_docs_ingest.py:189-309` expects a meaningful split between top-level Tier 4 and `cite/` formal docs.
- **Fallback path:** `bin/bootstrap_self_audit_docs.py:50-61` mirrors only top-level files and creates an empty `cite/` directory.
- **Parity gap:** the mirroring helper does not preserve the ingest contract’s citable-surface distinction.
- **Candidate requirement:** REQ-004 below.

## Pattern Deep Dive — Cross-Implementation Consistency

### Phase 1 completion contract
- **Declarative contract:** `SKILL.md:1204-1217` requires exact Phase 1 sections, minimum findings counts, pattern-matrix coverage, and candidate-bug balance before Phase 2.
- **Runner prompt contract:** `phase_prompts/phase1.md:77-82` restates the required exploration payload and `phase_prompts/phase1.md:59-69` delegates `breakdown`/`summary` generation to the runner.
- **Mechanical validator:** `bin/run_state_lib.py:171-198` only checks file existence, line count, and the presence of one finding-section pattern.
- **Gap:** the execution boundary is materially weaker than the prose contract it is supposed to enforce.
- **Candidate requirement:** REQ-005 and REQ-007 below.

### Install / resolution order surface
- **Runtime fallback prose:** `bin/run_playbook.py:831-838`
- **Helper fallback list:** `bin/benchmark_lib.py:52-59`
- **Test oracle:** `bin/tests/test_skill_resolution_order.py:31-42`
- **Observation:** this surface is currently aligned and heavily tested, which makes it a good control example. The documentation-state and role-map surfaces are not held to the same level of cross-surface lockstep.

## Pattern Deep Dive — Enumeration and Representation Completeness

### Bug-heading extraction
- **Closed set / parser representation:** `bin/archive_lib.py:_BUG_HEADING_PATTERN` at `69`
- **Consumer path:** `_split_by_heading()` at `313-318` and `_extract_bug_counts()` at `321-338`
- **Authoritative source:** canonical BUG heading form used elsewhere, including `.github/skills/quality_gate/quality_gate.py:118` (`^###\\s+BUG-(\\d+):`) and the repo’s written protocols.
- **Missing representation:** titled bug headings are absent from the archive parser’s accepted set.
- **Candidate requirement:** REQ-006 below.

### Role-map schema surface
- **Authoritative source:** `phase_prompts/phase1.md:59-69` says Phase 1 writers output only `files[]` and `provenance`.
- **Validator expectation:** `bin/role_map.py:252` and `318-322` require `breakdown` and `summary` before validation.
- **Gap:** the validator’s required top-level key set is incomplete relative to the prompt contract unless runner-side normalization is always in play.
- **Candidate requirement:** REQ-007 below.

## Pattern Deep Dive — API Surface Consistency

### Documentation APIs
- **Surface A:** `docs_present()` at `bin/run_playbook.py:1560-1575`
- **Surface B:** `_evaluate_documentation_state()` at `1661-1669`
- **Surface C:** `formal_docs_guard_banner()` at `1598-1621`
- **Divergence:** A cite-only tree produces `False` / `with_docs` / no banner respectively; a README-only or PDF-only tree produces `True` / `code_only` / warning banner. These three APIs describe the same repository state but do not agree on the answer.
- **Candidate requirements:** REQ-001 and REQ-002 below.

### Ingest vs bootstrap mirror
- **Surface A:** `bin/reference_docs_ingest.py` expects a two-bucket reference-doc structure.
- **Surface B:** `bin/bootstrap_self_audit_docs.py` flattens the source set to Tier 4.
- **Divergence:** the helper that prepares bootstrap docs does not preserve the structure the ingest step expects.
- **Candidate requirement:** REQ-004 below.

## Candidate Bugs for Phase 2

1. **HIGH — cite-only docs trigger a false code-only warning**
   - Stage: open exploration + API Surface Consistency
   - Evidence: `bin/run_playbook.py:1560-1575`, `1583-1595`, `1661-1669`
   - Why it matters: operator messaging and confidence-tier interpretation diverge.
   - Review focus: unify `docs_present()` with the recognized-plaintext predicate used by `_evaluate_documentation_state()`.

2. **HIGH — nested `reference_docs/` archives are ingested as live Tier 4 context**
   - Stage: open exploration + Fallback Path Parity
   - Evidence: `bin/reference_docs_ingest.py:90-94`, `189-227`, `263-276`
   - Why it matters: historical/raw subtrees can pollute Phase 1 context and silently expand prompt budget.
   - Review focus: restrict Tier 4 ingest to top-level files unless the spec explicitly widens the contract.

3. **HIGH — Phase 1 gate can pass a structurally shallow exploration artifact**
   - Stage: open exploration + Cross-Implementation Consistency
   - Evidence: `SKILL.md:1204-1217`, `bin/run_state_lib.py:171-198`
   - Why it matters: later phases can proceed on an invalid `EXPLORATION.md`, causing low-recall runs that still look mechanically complete.
   - Review focus: strengthen `validate_phase_artifacts(..., 1)` to match the documented section/coverage contract.

4. **MEDIUM — archive summaries can record zero bugs for canonical `BUGS.md` files**
   - Stage: open exploration + Enumeration/Representation Completeness
   - Evidence: `bin/archive_lib.py:69`, `313-338`
   - Why it matters: benchmark/replay metrics and `INDEX.md` summaries become unreliable.
   - Review focus: accept the canonical titled `### BUG-NNN: Title` heading form and add a direct regression test.

5. **MEDIUM — bootstrap docs mirroring drops the citable doc bucket**
   - Stage: quality risks + API Surface Consistency
   - Evidence: `bin/bootstrap_self_audit_docs.py:50-61`, `bin/reference_docs_ingest.py:189-227`
   - Why it matters: self-audit runs can look docs-backed while silently losing the formal citation surface.
   - Review focus: mirror both top-level and `cite/` content with placement preserved.

6. **MEDIUM — direct Phase 1 role-map output is invalid until a runner-only repair step runs**
   - Stage: open exploration + Cross-Implementation Consistency
   - Evidence: `phase_prompts/phase1.md:59-69`, `bin/role_map.py:252`, `285-322`, `759-838`
   - Why it matters: the repo advertises both skill-direct and runner-driven execution modes, but this contract only works cleanly in the runner path.
   - Review focus: either make validation accept pre-normalization maps or normalize in every direct-execution path before validation.

## Derived Requirements

### REQ-001: Cite-only documentation must count as docs-backed input
- References: `bin/run_playbook.py:1560-1575`, `bin/run_playbook.py:1661-1669`
- Requirement: Any startup path that decides whether a run is docs-backed or code-only must treat `reference_docs/cite/*.md|*.txt` as valid documentation.
- Conditions of satisfaction:
  - A repo with only `reference_docs/cite/spec.md` is reported as docs-backed consistently across warnings, progress metadata, and runtime state.
  - No code-only warning is emitted for a cite-only documentation tree.

### REQ-002: Documentation warnings must use the same recognized-plaintext predicate as documentation-state evaluation
- References: `bin/run_playbook.py:1568-1574`, `bin/run_playbook.py:1583-1595`, `bin/run_playbook.py:1598-1621`
- Requirement: The operator-visible startup warning path must classify documentation using the same `.md`/`.txt` and README-skipping rules used by the documentation-state evaluator and formal-doc banner logic.
- Conditions of satisfaction:
  - `reference_docs/README.md` alone does not suppress a code-only warning.
  - `reference_docs/spec.pdf` alone does not count as docs present.
  - The three helper surfaces agree on cite-only, README-only, binary-only, and plaintext-top-level cases.

### REQ-003: Tier 4 ingest must be limited to the documented `reference_docs/` surface
- References: `bin/reference_docs_ingest.py:90-94`, `bin/reference_docs_ingest.py:189-227`, `bin/reference_docs_ingest.py:263-276`
- Requirement: Only top-level plaintext files under `reference_docs/` may be treated as Tier 4 context unless the documented contract is explicitly widened.
- Conditions of satisfaction:
  - Nested directories outside `reference_docs/cite/` are skipped or rejected deterministically.
  - `load_tier4_context()` returns only the intended top-level Tier 4 files.

### REQ-004: Bootstrap self-audit doc mirroring must preserve citable-vs-context placement
- References: `bin/bootstrap_self_audit_docs.py:50-61`
- Requirement: The bootstrap mirror helper must preserve the distinction between top-level Tier 4 files and `cite/` formal-doc files when copying source documentation into `reference_docs/`.
- Conditions of satisfaction:
  - A source-side citable doc lands in `reference_docs/cite/`, not flattened into the Tier 4 root.
  - The helper preserves `cite/` content rather than leaving only scaffolding.

### REQ-005: The Phase 1 mechanical gate must enforce the documented exploration structure
- References: `bin/run_state_lib.py:171-198`
- Requirement: Phase 1 artifact validation must reject `EXPLORATION.md` files that do not contain the documented mandatory sections and minimum analytical content for Open Exploration, Quality Risks, pattern analysis, and candidate bugs.
- Conditions of satisfaction:
  - A 120-line file with only one finding section is rejected.
  - The validator checks for the mandatory Phase 1 sections, not just line count.

### REQ-006: Archive bug counters must parse canonical BUG headings
- References: `bin/archive_lib.py:69`, `bin/archive_lib.py:313-338`
- Requirement: Archive/index summarization must count bugs from the canonical `### BUG-NNN: Title` heading form used by the rest of the playbook.
- Conditions of satisfaction:
  - `_extract_bug_counts()` recognizes titled bug headings.
  - Severity/disposition counts in `INDEX.md` and `RUN_INDEX.md` reflect canonical bug files.

### REQ-007: Role-map validation must not depend on a runner-only repair step
- References: `bin/role_map.py:252`, `bin/role_map.py:285-322`, `bin/role_map.py:759-838`
- Requirement: A freshly written Phase 1 role map must either validate directly or be normalized automatically on every execution path before validation occurs.
- Conditions of satisfaction:
  - Direct skill-mode outputs that omit `breakdown` and `summary` are normalized before validation, or the validator accepts the pre-normalized shape.
  - The direct and runner-driven paths converge on the same final on-disk schema.

### REQ-008: Role-map inventory must separate intrinsic source from prior playbook output
- References: `bin/role_map.py:120-171`, `phase_prompts/phase1.md:18-36`
- Requirement: Phase 1 inventory and downstream reasoning must continue to classify `quality/` and archived run artifacts as `playbook-output`, not intrinsic code or docs.
- Conditions of satisfaction:
  - Prior run artifacts do not inflate code/skill surface calculations.
  - Exploration scope notes remain explicit when the tracked tree is dominated by historical outputs.

## Derived Use Cases

### UC-01: Cite-only docs-backed run
- Actors: operator, `bin.run_playbook`
- Trigger: the repo contains `reference_docs/cite/` docs but no top-level Tier 4 file
- Preconditions: at least one plaintext file exists under `reference_docs/cite/`
- Flow:
  - Startup checks docs presence
  - Documentation-state evaluation reports `with_docs`
  - No code-only warning is emitted
- Expected outcome: the run is treated consistently as docs-backed

### UC-02: README-only or binary-only docs tree
- Actors: operator, `bin.run_playbook`
- Trigger: the repo contains only `reference_docs/README.md` or binary docs such as PDF
- Preconditions: no recognized plaintext documentation exists
- Flow:
  - Startup checks docs presence
  - Documentation-state evaluation reports `code_only`
  - Warning and banner both communicate that the run lacks recognized docs
- Expected outcome: operator-visible surfaces agree that the run is code-only

### UC-03: Tier 4 ingest of reference docs
- Actors: Phase 1 agent, `bin.reference_docs_ingest`
- Trigger: Phase 1 loads Tier 4 context
- Preconditions: `reference_docs/` contains top-level plaintext docs
- Flow:
  - Ingest enumerates the intended Tier 4 files
  - `load_tier4_context()` returns only the documented surface
- Expected outcome: nested archive folders do not silently enter the prompt

### UC-04: Bootstrap self-audit doc mirroring
- Actors: maintainer, `bin.bootstrap_self_audit_docs`
- Trigger: maintainer prepares repo-root `reference_docs/` for a self-audit run
- Preconditions: source bootstrap docs include both contextual and citable material
- Flow:
  - Helper mirrors both top-level docs and `cite/` docs
  - Resulting `reference_docs/` matches the source structure
- Expected outcome: self-audit preserves formal citation capability

### UC-05: Phase 1 completion gate
- Actors: runner, `bin.run_state_lib`
- Trigger: Phase 1 finishes and the runner validates artifacts
- Preconditions: `quality/EXPLORATION.md` exists
- Flow:
  - Validator checks mandatory sections and minimum analytical content
  - Invalid artifacts are rejected before Phase 2
- Expected outcome: only a structurally complete exploration can advance

### UC-06: Archived bug-summary generation
- Actors: `bin.archive_lib`, later auditors
- Trigger: a run is archived and `INDEX.md` / `RUN_INDEX.md` are rendered
- Preconditions: `BUGS.md` uses canonical bug headings
- Flow:
  - Archive parser extracts bug sections
  - Severity/disposition totals are rendered into the index payload
- Expected outcome: historical summaries match the actual bug file

### UC-07: Direct Phase 1 role-map writeout
- Actors: agent running the playbook directly, `bin.role_map`
- Trigger: Phase 1 writes `quality/exploration_role_map.json` without runner mediation
- Preconditions: the map contains `files[]` and `provenance`
- Flow:
  - Validation or normalization runs on the raw role map
  - Canonical `breakdown` and `summary` are added deterministically if needed
- Expected outcome: direct and runner-driven paths both produce valid role maps

### UC-08: Historical-output-heavy repository inventory
- Actors: Phase 1 agent, `bin.role_map`
- Trigger: the tracked tree contains many prior `quality/` artifacts
- Preconditions: `git ls-files` enumerates historical outputs alongside source
- Flow:
  - Phase 1 tags prior-run artifacts as `playbook-output`
  - Exploration scope focuses on the intrinsic code/prose surface
- Expected outcome: downstream analysis is not skewed by historical artifacts

## File-role tagging

`quality/exploration_role_map.json` was produced using `git ls-files` as the canonical enumeration source.

- `files_by_role`
  - `playbook-output`: 871
  - `fixture`: 117
  - `docs`: 60
  - `test`: 53
  - `code`: 41
  - `skill-prose`: 16
  - `skill-reference`: 16
  - `config`: 5
  - `skill-tool`: 2
  - `formal-spec`: 2
- `percentages`
  - `skill_share`: 1.62%
  - `code_share`: 2.17%
  - `tool_share`: 0.04%
  - `other_share`: 96.17%

Interpretation:

- By file count and by bytes, the tracked tree is dominated by prior playbook output and benchmark/example data rather than intrinsic source.
- The intrinsic active surface is comparatively small: `SKILL.md`, `references/`, `phase_prompts/`, `agents/`, roughly 40 source files under `bin/` / gate / shim code, and the corresponding test suites.
- No roles outside the documented taxonomy were needed.

## Cartesian UC rule confirmation

1. For every REQ with ≥2 References, I ran Gate 1 (path-suffix match).
2. For every REQ that passed Gate 1, I ran Gate 2 (function-level similarity).
3. Where both gates passed, I emitted per-site UCs (UC-N.a, UC-N.b, …).
4. Where only Gate 1 passed, I marked the cluster `<!-- cluster: heterogeneous -->`.
5. Where neither gate passed, I kept a single umbrella UC without marking.
6. For each REQ with a pattern match in Gate 1, I added `Pattern: whitelist|parity|compensation` to the REQ block.

Result for this run:

- No REQ used ≥2 references in distinct files with a qualifying shared path-suffix/function-role match, so no per-site UC expansion was required.
- All UCs remain single-site umbrella use cases.

## Notes for Artifact Generation

- Treat this repository as a hybrid target. The primary product is the skill/prose contract, but there is enough independent Python tooling that prose-to-code divergence is a first-class bug source.
- Do not use the deleted/tracked `quality/` tree as exploration evidence in later phases; it is historical playbook output, not the clean-run baseline.
- The highest-value Phase 2 artifact work should trace requirements around documentation-state handling, role-map normalization, archive/index accuracy, and Phase 1 gate enforcement.
- Because `reference_docs/cite/` is empty in the active tree, any citation-backed requirements will need either new formal docs or an explicit Tier 3/4 classification.

## Gate Self-Check

1. PASS — `quality/EXPLORATION.md` exists on disk and contains 438 lines of substantive content.
2. PASS — `quality/PROGRESS.md` exists and marks `- [x] Phase 1 - Explore`.
3. PASS — `## Derived Requirements` contains REQ-001 through REQ-008 with concrete file paths and functions such as `bin/run_playbook.py:docs_present()`, `_evaluate_documentation_state()`, and `bin/archive_lib.py:_extract_bug_counts()`.
4. PASS — `## Open Exploration Findings` exists verbatim and contains 8 concrete file:line hypotheses spanning `bin/run_playbook.py`, `bin/reference_docs_ingest.py`, `bin/bootstrap_self_audit_docs.py`, `bin/run_state_lib.py`, `bin/archive_lib.py`, and `phase_prompts/phase1.md`.
5. PASS — Open-exploration multi-location traces appear in findings 1, 2, 3, 4, 5, 6, and 7; each traces behavior across 2+ concrete code locations or functions.
6. PASS — `## Quality Risks` exists verbatim and contains 5 ranked domain-driven failure scenarios with specific file:line citations and failure mechanisms.
7. PASS — `## Pattern Applicability Matrix` exists verbatim and evaluates all 6 required patterns with explicit `FULL` or `SKIP` decisions, targets, and rationale.
8. PASS — Exactly 4 patterns are marked `FULL`, which is within the required 3–4 range.
9. PASS — There are 4 `## Pattern Deep Dive — ...` sections, matching the 4 `FULL` pattern selections.
10. PASS — At least 2 pattern deep dives trace multi-function paths: Fallback and Degradation Path Parity and API Surface Consistency each compare multiple functions/surfaces, and Cross-Implementation Consistency traces the prose/prompt/validator path.
11. PASS — `## Candidate Bugs for Phase 2` exists verbatim and contains 6 prioritized bug hypotheses with stage labels, file:line evidence, and review focus notes.
12. PASS — Ensemble balance holds: candidate bugs 1, 2, 3, 4, and 6 originate from open exploration or quality risks, and bugs 1, 2, 3, 4, 5, and 6 are also materially strengthened by pattern deep dives.
