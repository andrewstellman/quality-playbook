# Exploration - quality-playbook bootstrap self-audit

Resolved skill path: `SKILL.md`
Resolved references path: `references/`
Date: 2026-04-28

## Open Exploration Findings

### Domain and stack identification

- This repository is a specification-first quality engineering product: the primary deliverable is the Quality Playbook skill and its reference protocol, with Python tooling that operationalizes the six-phase workflow for benchmark and self-audit runs (`README.md:1-11`, `ai_context/DEVELOPMENT_CONTEXT.md:20-27`, `ai_context/DEVELOPMENT_CONTEXT.md:108-120`).
- The implementation stack is mostly Python 3.8+ standard library code under `bin/` and `.github/skills/quality_gate/`, plus Markdown skill/reference docs, shell setup helpers under `repos/`, and a local `pytest/` shim so tests can run without installing external packages (`ai_context/DEVELOPMENT_CONTEXT.md:20-27`, `ai_context/DEVELOPMENT_CONTEXT.md:80-106`).
- The repo should be treated as a Hybrid project, not a plain Python utility: `bin/classify_project.py` explicitly classifies targets as `Code`, `Skill`, or `Hybrid`, and the v1.5.3 development context calls out the skill-derivation pipeline as a first-class subsystem (`ai_context/DEVELOPMENT_CONTEXT.md:24-37`, `bin/classify_project.py:261-286`).
- `reference_docs/` is present but empty in this checkout, so the canonical formal-doc intake path contributed no usable documentation. Exploration therefore relied on Tier 3 source evidence plus supplemental bootstrap docs from `docs_gathered/` (`README.md:25-50`, `bin/reference_docs_ingest.py:270-300`, `docs_gathered/INDEX.md:1-37`).

### Architecture map

- **Skill/spec surface:** `SKILL.md`, `references/`, `schemas.md`, `agents/`, and `ai_context/` define the protocol, artifacts, and user/operator guidance. This is the product's intent surface and the source of many later gates (`SKILL.md:1-20`, `schemas.md:592-763`, `ai_context/DEVELOPMENT_CONTEXT.md:10-78`).
- **Runner/orchestration surface:** `bin/run_playbook.py` is the main dispatcher. It builds phase prompts, runs gate checks between phases, writes `quality/INDEX.md`, monitors `PROGRESS.md`, archives prior runs, and coordinates iteration strategies (`bin/run_playbook.py:621-723`, `bin/run_playbook.py:1152-1175`, `bin/run_playbook.py:1819-1905`, `bin/run_playbook.py:2235-2293`, `bin/run_playbook.py:2602-2698`).
- **Documentation/citation pipeline:** `bin/reference_docs_ingest.py` walks `reference_docs/` and writes `quality/formal_docs_manifest.json`; `bin/citation_verifier.py` provides the deterministic excerpt extraction used by both ingest and the gate (`bin/reference_docs_ingest.py:254-316`, `bin/citation_verifier.py:1-14`, `bin/citation_verifier.py:122-220`).
- **Project-type and skill-derivation surface:** `bin/classify_project.py` emits the Code/Skill/Hybrid classification record; `bin/skill_derivation/__main__.py` drives the v1.5.3 four-pass derivation and divergence workflow (`bin/classify_project.py:261-286`, `bin/tests/test_skill_derivation_main.py:1-18`).
- **Mechanical validation surface:** `.github/skills/quality_gate/quality_gate.py` is the post-run gate, including REQ pattern parsing, semantic-check enforcement, project-type consistency checks, and index validation (`.github/skills/quality_gate/quality_gate.py:1-20`, `.github/skills/quality_gate/quality_gate.py:52-77`, `.github/skills/quality_gate/quality_gate.py:2036-2145`, `.github/skills/quality_gate/quality_gate.py:3037-3064`).
- **Packaging/setup surface:** `repos/setup_repos.sh` copies the skill into benchmark targets, mirrors `docs_gathered/` into `reference_docs/`, and installs the top-level gate entry point. That script creates an important alternate install path from the direct bootstrap-at-repo-root flow (`repos/setup_repos.sh:195-220`, `docs_gathered/30_benchmark_protocol_and_self_audit.md:87-99`).

### Existing test inventory

- The development context documents two main test suites: `python3 -m unittest discover bin/tests` (runner + derivation modules) and `python3 -m unittest discover -s .github/skills/quality_gate/tests/ -p 'test_*.py'` (quality gate). The gate suite is explicitly documented as `unittest`-first because `pytest` has an import-shadowing issue there (`ai_context/DEVELOPMENT_CONTEXT.md:82-106`).
- Representative runner tests cover prompt construction, phase gate behavior, archiving, and CLI parsing (`bin/tests/test_run_playbook.py:15-180`).
- Representative ingest/citation tests cover empty-manifest behavior, tier markers, `reference_docs` top-level vs `cite/` semantics, and schema key correctness (`bin/tests/test_reference_docs_ingest.py:23-145`, `bin/tests/test_citation_verifier.py:54-173`).
- Representative progress/monitoring tests cover `PROGRESS.md` header extraction and monitoring cadence (`bin/tests/test_progress_monitor.py:30-120`).
- Representative skill-derivation tests cover CLI parsing and the four-pass orchestration path (`bin/tests/test_skill_derivation_main.py:36-140`).
- Measured during exploration: the repo currently contains 35 `bin/tests/test_*.py` files and 2 gate test files under `.github/skills/quality_gate/tests/`, with the development context describing the total suite as 662 `bin/tests` tests plus 221 gate tests at v1.5.3 (`ai_context/DEVELOPMENT_CONTEXT.md:38-39`, `ai_context/DEVELOPMENT_CONTEXT.md:62-67`, `ai_context/DEVELOPMENT_CONTEXT.md:82-91`).

### Specification summary

- The core user-visible contract is that the playbook derives intent from source plus documentation, writes phase outputs to disk, and uses those artifacts to drive code review, multi-model audit, and TDD verification (`README.md:1-11`, `docs_gathered/20_design_intent_the_35_percent_gap.md:18-46`, `docs_gathered/26_six_phase_orchestration.md:5-23`).
- The six-phase orchestration model depends on strict phase boundaries, artifact-based handoff, and non-negotiable gates between phases; Phase 1 exploration is the required input to every downstream artifact (`docs_gathered/26_six_phase_orchestration.md:5-23`, `docs_gathered/26_six_phase_orchestration.md:52-91`, `SKILL.md:1026-1044`).
- The requirements pipeline is treated as the heart of the system: downstream phases consume requirements rather than rediscovering code intent ad hoc (`docs_gathered/21_requirements_pipeline.md:5-18`, `docs_gathered/21_requirements_pipeline.md:35-79`).
- The anti-hallucination design is explicit: executed evidence outranks prose, byte-deterministic citation excerpts are reused between ingest and the gate, and source-inspection or mechanical artifacts are preferred to ungrounded reasoning (`docs_gathered/25_anti_hallucination_invariants.md:11-24`, `docs_gathered/25_anti_hallucination_invariants.md:39-63`, `bin/citation_verifier.py:1-14`).
- The bootstrap/self-audit docs say the repo root should be a valid benchmark target in its own right, but they also describe bootstrap as a special case with self-reference, curated docs, and direct-root execution rather than `setup_repos.sh` installation (`docs_gathered/30_benchmark_protocol_and_self_audit.md:79-107`).
- Documentation-state note for this run: the canonical `reference_docs/` path was empty, so there were no citable Tier 1/2 docs from that path. Supplemental `docs_gathered/` docs exist and are rich, but some are version-drifted compared with the current repo-root README/SKILL, so they are helpful context but not a clean authoritative spec (`docs_gathered/INDEX.md:1-37`, `docs_gathered/01_README_project.md:1-6`, `docs_gathered/29_improvement_axes_and_version_history.md:68-72`, `README.md:1-5`, `SKILL.md:1-13`).

### Skeleton/dispatch/state-machine analysis

- The dominant state machine is the phase lifecycle in `bin/run_playbook.py`: Phase 1 is the only unconditional entry; Phase 2 depends on `quality/EXPLORATION.md`; Phase 3 depends on the Phase 2 artifact set; later phases layer their own required-file checks or warnings (`bin/run_playbook.py:1152-1175`).
- A second state machine is the live-run/iteration lifecycle: `run_one_phased()` starts monitoring, optionally archives prior output, writes an `INDEX.md` stub, then advances through phase groups; `run_one_iterations()` appends heartbeat headers to `PROGRESS.md`, logs bug deltas, and finalizes each iteration (`bin/run_playbook.py:2235-2293`, `bin/run_playbook.py:2602-2698`).
- The citation pipeline is a deterministic decode -> locate -> excerpt -> verify state machine. `extract_excerpt()` enforces UTF-8 decoding, line/section locator rules, blank-anchor rejection, and byte-identical newline joining, while the gate re-runs extraction and compares the fresh excerpt to the stored one (`bin/citation_verifier.py:68-182`, `.github/skills/quality_gate/quality_gate.py:1818-1864`).
- The project-type surface is another dispatch boundary: classifier output can be `Code`, `Skill`, or `Hybrid`, and later v1.5.3 logic is supposed to use that fact when deciding what cross-cutting requirements and divergence checks apply (`bin/classify_project.py:261-286`, `.github/skills/quality_gate/quality_gate.py:3030-3034`).

### Concrete bug hypotheses

1. `bin/run_playbook.py:621-630` tells Phase 1 to read `reference_docs/`, but `docs_present()` still defines "has docs" entirely in terms of `docs_gathered/` (`bin/run_playbook.py:1552-1559`), and that legacy warning is emitted from three execution paths (`bin/run_playbook.py:2241-2246`, `bin/run_playbook.py:2314-2319`, `bin/run_playbook.py:2611-2616`). A target with populated `reference_docs/` but no `docs_gathered/` will still be told it is doing "code-only analysis."
2. The runner now has two competing documentation guards: a modern `reference_docs/` guard that correctly explains Tier 4 vs `cite/` semantics (`bin/run_playbook.py:1562-1622`) and the older `docs_gathered/` warning path (`bin/run_playbook.py:2241-2246`, `bin/run_playbook.py:2314-2319`, `bin/run_playbook.py:2611-2616`). This creates contradictory operator guidance on modern installs.
3. `SKILL.md:1026-1042` says the Phase 2 entry gate must verify exact `EXPLORATION.md` section titles and content thresholds, but `check_phase_gate()` only verifies existence plus `>= 120` lines for Phase 2 (`bin/run_playbook.py:1158-1165`). A malformed exploration file can pass the runner gate even when it violates the written skill contract.
4. The repo advertises Code/Skill/Hybrid classification as a v1.5.3 feature (`ai_context/DEVELOPMENT_CONTEXT.md:24-37`, `bin/classify_project.py:261-286`), but both `write_live_index_stub()` and `write_live_index_final()` still hardcode `target_project_type: "Code"` (`bin/run_playbook.py:1819-1831`, `bin/run_playbook.py:1888-1895`). This can poison `quality/INDEX.md` metadata for Skill or Hybrid targets.
5. `kill_recorded_processes()` correctly prefers PID files, but when none exist it falls back to `_pkill_fallback()` with generic patterns like `bin/run_playbook.py`, `claude -p`, and `gh copilot -p` (`bin/run_playbook.py:2836-2865`). On a shared workstation that can kill unrelated agent sessions that happen to match the same command line.
6. The curated bootstrap docs are drifted relative to the current shipping version: `docs_gathered/01_README_project.md:1-6` still says v1.5.0 and documents `docs_gathered/` as Step 1 input, while `docs_gathered/29_improvement_axes_and_version_history.md:68-72` still calls v1.5.1 current; the live root docs are v1.5.3 and reference `reference_docs/` instead (`README.md:15-50`, `SKILL.md:1-13`). A self-audit that trusts the curated pack over the live repo can derive stale requirements.
7. The gate promises byte-equality checking only when `bin/citation_verifier` is importable; otherwise it emits a warning and skips the check (`.github/skills/quality_gate/quality_gate.py:32-44`, `.github/skills/quality_gate/quality_gate.py:1823-1864`). At the same time, benchmark setup currently copies only the top-level `quality_gate.py` entry point into targets (`repos/setup_repos.sh:195-200`). That packaging path can silently degrade the Layer-1 anti-hallucination guarantee that the README promises for `reference_docs/cite/` (`README.md:39-42`).
8. The benchmark harness explicitly mirrors `docs_gathered/` into `reference_docs/` because the modern playbook no longer reads `docs_gathered/` directly (`repos/setup_repos.sh:202-220`), but the bootstrap protocol says the repo root itself is a direct benchmark target (`docs_gathered/30_benchmark_protocol_and_self_audit.md:87-99`). In this checkout, `docs_gathered/` is populated while `reference_docs/` is empty, so direct bootstrap and harness-installed bootstrap do not see the same documentation surface.
9. The same repo contains both a symlinked installed skill entry point (`.github/skills/SKILL.md`) and the repo-root `SKILL.md`, and they currently resolve to the same file. That is correct today, but it is a packaging invariant worth protecting because downstream installers and fallback resolution depend on those copies staying aligned (`SKILL.md:1-20`, `.github/skills/SKILL.md:1-20`).

## Quality Risks

1. **Documentation-source drift can reduce bug yield without obvious failure.** If the runner warns about missing `docs_gathered/` on a modern `reference_docs/` install, operators may ignore the wrong problem or assume the run is weaker than it really is (`bin/run_playbook.py:1552-1622`, `README.md:15-50`).
2. **Under-enforced Phase 2 gating can let malformed exploration propagate downstream.** Because the runner does not check for the exact required headings, later phases can consume incomplete analysis and still look superficially successful (`SKILL.md:1026-1042`, `bin/run_playbook.py:1158-1165`).
3. **Incorrect project-type metadata can suppress Hybrid/Skill-specific enforcement.** If `quality/INDEX.md` says `Code` for a Skill or Hybrid target, later review, audit, and archive consumers can reason from the wrong project shape (`bin/classify_project.py:261-286`, `bin/run_playbook.py:1819-1831`, `bin/run_playbook.py:1888-1895`).
4. **Soft-failing citation verification weakens the strongest anti-hallucination guarantee.** A WARN-only downgrade on missing `bin/citation_verifier` means a target can appear to support byte-verified citations while actually skipping the byte-equality check (`.github/skills/quality_gate/quality_gate.py:32-44`, `.github/skills/quality_gate/quality_gate.py:1823-1864`).
5. **Pattern-based process killing is unsafe in shared environments.** Cleanup that kills by substring instead of recorded PID is acceptable only as a last resort and is not scoped to the current run (`bin/run_playbook.py:2836-2865`).
6. **Bootstrap self-audit can bifurcate between direct-root and harness-installed runs.** One path sees `docs_gathered/`, the other sees mirrored `reference_docs/`, and the current root repo has only one of those populated (`repos/setup_repos.sh:202-220`, `docs_gathered/30_benchmark_protocol_and_self_audit.md:87-99`).
7. **Curated bootstrap docs can become a stale spec source.** Because the self-audit pack is intentionally concise and independent, it can lag behind live README/SKILL changes and seed outdated requirements into future self-audits (`docs_gathered/INDEX.md:17-37`, `docs_gathered/01_README_project.md:1-6`, `docs_gathered/29_improvement_axes_and_version_history.md:68-72`, `README.md:1-5`).

## Pattern Applicability Matrix

| Pattern | Status | Why it applies here |
| --- | --- | --- |
| Fallback and Degradation Path Parity | FULL | The repo maintains parallel documentation intake paths (`reference_docs/`, `docs_gathered/`, harness mirroring) and fallback cleanup paths (`PID` kill vs `pkill`). |
| Dispatcher Return-Value Correctness | PARTIAL | There are some state/dispatch functions, but the highest-yield issues are not return-code bugs; they are contract and gating mismatches. |
| Cross-Implementation Contract Consistency | FULL | The same logical contracts are implemented in multiple places: root docs vs installed docs, classifier output vs live index writing, skill text vs runner gates. |
| Enumeration and Representation Completeness | FULL | The repo maintains closed sets of required phase headings, REQ pattern values, and project-type classifications; omissions here are mechanically important. |
| API Surface Consistency | PARTIAL | There are multiple public surfaces (repo-root skill, installed skill, runner CLI, setup script), but the strongest issues collapse into cross-implementation parity rather than user-facing API argument drift. |
| Defensive / State-Machine Analysis | PARTIAL | The repo has meaningful state machines (phase gates, progress monitor, iteration lifecycle), but the clearest bug signals are around policy drift, not missed lifecycle states. |

## Pattern Deep Dive — Fallback and Degradation Path Parity

### Documentation intake paths

- **Primary path:** `reference_docs/` is the canonical Phase 1 documentation surface in the live README and prompt contract (`README.md:25-50`, `bin/run_playbook.py:621-630`).
- **Fallback/legacy path:** `docs_present()` still treats `docs_gathered/` as the signal for whether a run has docs at all (`bin/run_playbook.py:1552-1559`), and that warning is emitted in phased, single-pass, and iteration flows (`bin/run_playbook.py:2241-2246`, `bin/run_playbook.py:2314-2319`, `bin/run_playbook.py:2611-2616`).
- **Compensating harness path:** `repos/setup_repos.sh` explicitly mirrors `docs_gathered/` into `reference_docs/` because without that copy "the modern playbook doesn't look" at the curated docs (`repos/setup_repos.sh:202-220`).
- **Parity gap:** direct bootstrap-at-root runs and harness-installed runs do not traverse the same doc-intake path, so they can explore the same repo with different evidence.
- **Candidate requirements:** REQ-002 and REQ-008.

### Cleanup paths

- **Primary path:** `kill_recorded_processes()` prefers recorded PIDs from per-parent PID files (`bin/run_playbook.py:2807-2834`, `bin/run_playbook.py:2861-2875`).
- **Fallback path:** `_pkill_fallback()` kills by command-line substring when PID files are absent (`bin/run_playbook.py:2836-2865`).
- **Parity gap:** the primary path is run-scoped, but the fallback path is workstation-scoped.
- **Candidate requirements:** REQ-005.

## Pattern Deep Dive — Cross-Implementation Contract Consistency

### Project type as a cross-surface contract

- **Classification implementation:** `bin/classify_project.py` produces a structured record with `classification`, `rationale`, and supporting evidence (`bin/classify_project.py:261-286`).
- **Consumer implementation:** the gate runs project-type consistency checks for all projects (`.github/skills/quality_gate/quality_gate.py:3030-3034`).
- **Metadata writer implementation:** `bin/run_playbook.py` still writes `"Code"` into the live run index stub and final render regardless of classifier output (`bin/run_playbook.py:1819-1831`, `bin/run_playbook.py:1888-1895`).
- **Gap:** the repository has the concept of non-Code projects, but one of the main run metadata surfaces ignores it.
- **Candidate requirements:** REQ-004.

### Exploration gate as a cross-surface contract

- **Spec implementation:** `SKILL.md` defines the Phase 2 entry gate in terms of exact headings and minimum content shape (`SKILL.md:1026-1042`).
- **Runtime implementation:** `check_phase_gate()` only checks that `EXPLORATION.md` exists and is at least 120 lines long (`bin/run_playbook.py:1158-1165`).
- **Test implementation:** runner tests cover the missing-file case, but there is no matching enforcement test for the required headings contract (`bin/tests/test_run_playbook.py:116-130`).
- **Gap:** the written protocol and the executable gate are not enforcing the same artifact contract.
- **Candidate requirements:** REQ-003.

### Citation verification as a cross-surface contract

- **Spec implementation:** the README says files in `reference_docs/cite/` produce citable `FORMAL_DOC` records whose excerpts `quality_gate.py` byte-verifies (`README.md:39-42`).
- **Shared-library implementation:** `citation_verifier.py` is explicitly designed to be shared between ingest and the gate and promises byte-identical output (`bin/citation_verifier.py:1-14`).
- **Installed-gate implementation:** the gate skips byte-equality if `bin/citation_verifier` is unavailable on the install (`.github/skills/quality_gate/quality_gate.py:32-44`, `.github/skills/quality_gate/quality_gate.py:1823-1864`).
- **Gap:** the packaging story can break a cross-surface guarantee that the README presents as unconditional.
- **Candidate requirements:** REQ-006.

## Pattern Deep Dive — Enumeration and Representation Completeness

### Phase 2 gate headings are a closed set

- **Authoritative source:** `SKILL.md` enumerates the exact required headings for `quality/EXPLORATION.md` (`SKILL.md:1026-1042`).
- **Runtime representation:** `check_phase_gate()` currently reduces that contract to one file-exists check plus one line-count threshold (`bin/run_playbook.py:1158-1165`).
- **Missing entries:** the runtime gate does not represent the required headings `## Open Exploration Findings`, `## Quality Risks`, `## Pattern Applicability Matrix`, `## Candidate Bugs for Phase 2`, or `## Gate Self-Check` at all.
- **Candidate requirements:** REQ-003.

### Project-type values are a closed set

- **Authoritative source:** `bin/classify_project.py` and the development context describe `Code`, `Skill`, and `Hybrid` as supported classifications (`ai_context/DEVELOPMENT_CONTEXT.md:24-37`, `bin/classify_project.py:261-286`).
- **Runtime representation:** `write_live_index_stub()` and `write_live_index_final()` only ever write `Code` (`bin/run_playbook.py:1819-1831`, `bin/run_playbook.py:1888-1895`).
- **Missing entries:** `Skill` and `Hybrid` are absent from one of the core metadata emitters.
- **Candidate requirements:** REQ-004.

### Citation-verification install support is a closed set

- **Authoritative source:** the README's `reference_docs/cite/` contract implies that every citable install should be able to byte-verify stored excerpts (`README.md:39-42`).
- **Runtime representation:** the gate can only enforce that when `_CITATION_VERIFIER` imports successfully (`.github/skills/quality_gate/quality_gate.py:32-44`, `.github/skills/quality_gate/quality_gate.py:1823-1864`).
- **Missing install artifact:** `repos/setup_repos.sh` installs `quality_gate.py` but not the shared verifier module (`repos/setup_repos.sh:195-200`).
- **Candidate requirements:** REQ-006.

## Testable Requirements Derived

### REQ-001: Installed skill entry points must stay synchronized with the repo-root skill

- Description: Packaging must not allow the repo-root `SKILL.md` and installed `.github/skills/SKILL.md` entry point to drift, because skill-path fallback resolution depends on both representing the same instructions and version.
- References: `SKILL.md:1-20`; `.github/skills/SKILL.md:1-20`
- Pattern: parity
- Use cases: `UC-07`

### REQ-002: The runner must treat `reference_docs/` as the authoritative documentation input for Phase 1

- Description: Modern installs that provide `reference_docs/` should not receive "code-only" warnings just because `docs_gathered/` is absent; preflight messaging and exploration behavior must align with the canonical `reference_docs/` contract.
- References: `README.md:25-50`; `bin/run_playbook.py:621-630`; `bin/run_playbook.py:1552-1622`; `bin/reference_docs_ingest.py:270-300`
- Use cases: `UC-01`, `UC-02`

### REQ-003: Phase 2 entry gating must enforce the full `EXPLORATION.md` section contract, not just file length

- Description: A run must not advance beyond Phase 1 unless `quality/EXPLORATION.md` contains the exact headings and minimum content shape the skill requires, because later phases depend on those sections by name.
- References: `SKILL.md:1026-1042`; `bin/run_playbook.py:1152-1165`; `bin/tests/test_run_playbook.py:116-130`
- Use cases: `UC-01`, `UC-03`

### REQ-004: Live run metadata must preserve the actual Code/Skill/Hybrid project classification

- Description: Any run that computes project type must carry that value through to `quality/INDEX.md` and related metadata instead of defaulting every target to `Code`.
- References: `ai_context/DEVELOPMENT_CONTEXT.md:24-37`; `bin/classify_project.py:261-286`; `bin/run_playbook.py:1819-1831`; `bin/run_playbook.py:1888-1895`
- Use cases: `UC-03`, `UC-04`

### REQ-005: Cleanup paths must only terminate playbook-owned processes

- Description: Operator cleanup must remain scoped to recorded run workers; any fallback path must avoid killing unrelated Claude or Copilot processes on the same host.
- References: `bin/run_playbook.py:2807-2875`
- Use cases: `UC-06`

### REQ-006: Every installed citable-doc workflow must retain byte-equality citation verification

- Description: If the README advertises byte-verified citation excerpts for `reference_docs/cite/`, the installed gate package must include the verifier code needed to enforce that guarantee rather than downgrading it to a warning.
- References: `README.md:39-42`; `bin/citation_verifier.py:1-14`; `.github/skills/quality_gate/quality_gate.py:32-44`; `.github/skills/quality_gate/quality_gate.py:1823-1864`; `repos/setup_repos.sh:195-200`
- Use cases: `UC-05`

### REQ-007: Bootstrap self-audit docs must remain current with the live skill version and terminology

- Description: Curated bootstrap docs are allowed to compress context, but they must not describe an older current version or obsolete documentation path in a way that can mislead Phase 1 requirement derivation.
- References: `docs_gathered/01_README_project.md:1-29`; `docs_gathered/29_improvement_axes_and_version_history.md:68-72`; `README.md:1-5`; `README.md:15-50`; `SKILL.md:1-13`
- Use cases: `UC-02`

### REQ-008: Direct bootstrap and harness-installed bootstrap must expose the same documentation surface

- Description: Running the playbook against QPB at the repo root and running it through the benchmark harness should not change which documentation tree Phase 1 actually sees.
- References: `repos/setup_repos.sh:202-220`; `docs_gathered/30_benchmark_protocol_and_self_audit.md:87-99`; `docs_gathered/INDEX.md:1-37`
- Use cases: `UC-01`, `UC-02`

## Use Cases Derived

### UC-01: Operator explores a target with source-only evidence available

- Actors: benchmark operator, playbook runner
- Preconditions: the target has little or no usable `reference_docs/` content
- Flow:
  1. The operator runs Phase 1 against the target repository.
  2. The runner inspects the documentation tree and falls back to Tier 3 source evidence.
  3. The operator receives accurate messaging about the strength of the available evidence.
- Postconditions: `EXPLORATION.md` reflects the missing-docs condition without misreporting a modern install as "code-only" when docs are actually present elsewhere.

### UC-02: Maintainer runs the bootstrap self-audit against QPB itself

- Actors: QPB maintainer, playbook runner
- Preconditions: the repo root is the audit target and curated bootstrap docs exist
- Flow:
  1. The maintainer runs Phase 1 at the repo root.
  2. Phase 1 reads the live skill plus the curated bootstrap context.
  3. The maintainer expects the run to see the same documentation surface the harness-installed version would see.
- Postconditions: the self-audit is not biased by direct-root versus harness-installed documentation differences.

### UC-03: Runner initializes a phased run and hands off to later phases

- Actors: playbook runner, later-phase agent
- Preconditions: Phase 1 has started and later phases will read artifacts from disk
- Flow:
  1. The runner creates `quality/INDEX.md` and `quality/PROGRESS.md`.
  2. Phase 1 writes `quality/EXPLORATION.md`.
  3. Phase 2 reads the exploration artifact and enforces the required headings before generating downstream files.
- Postconditions: later phases consume a structurally valid exploration artifact and accurate run metadata.

### UC-04: Maintainer classifies a target as Code, Skill, or Hybrid

- Actors: maintainer, classifier, run metadata writer
- Preconditions: the target repo contains enough evidence for `bin/classify_project.py` to classify it
- Flow:
  1. The classifier emits a classification record.
  2. The runner writes live index metadata.
  3. Later tooling and the gate interpret the project according to that classification.
- Postconditions: the recorded project type matches the classifier output instead of silently collapsing to `Code`.

### UC-05: Auditor cites a `reference_docs/cite/` passage and expects byte-equal enforcement

- Actors: auditor, gate
- Preconditions: a REQ or BUG cites a `FORMAL_DOC` generated from `reference_docs/cite/`
- Flow:
  1. The ingest pipeline stores a deterministic citation excerpt.
  2. The gate re-runs excerpt extraction against the on-disk document bytes.
  3. The gate rejects any mismatch between stored excerpt and fresh extraction.
- Postconditions: Layer-1 citation verification is actually enforced on the installed target.

### UC-06: Operator terminates a stuck run safely

- Actors: benchmark operator, playbook runner
- Preconditions: a run is stuck or has left workers behind
- Flow:
  1. The operator invokes run cleanup.
  2. The runner reads the per-parent PID file and terminates only the recorded workers.
  3. Any fallback path remains scoped to the current run rather than generic agent command lines.
- Postconditions: the stuck run stops without affecting unrelated sessions on the same host.

### UC-07: Maintainer ships repo-root and installed skill copies together

<!-- cluster: heterogeneous -->

- Actors: skill maintainer, installer
- Preconditions: the repository root contains the canonical skill and the installed path is used by fallback resolution
- Flow:
  1. The maintainer updates the canonical `SKILL.md`.
  2. The installed `.github/skills/SKILL.md` resolves to the same content.
  3. A downstream agent can read either fallback path and receive equivalent instructions.
- Postconditions: packaging does not create version or instruction skew between canonical and installed skill entry points.

## Cartesian UC rule confirmation

1. For every REQ with `References`, I ran Gate 1 (path-suffix match).
2. I ran Gate 2 for every REQ that passed Gate 1. Only REQ-001 passed Gate 1 because `SKILL.md` and `.github/skills/SKILL.md` share the same path-suffix role; Gate 2 failed because the cited ranges are document frontmatter/heading text, not comparable function bodies.
3. No REQ passed both gates, so this exploration emitted no per-site `UC-N.a` / `UC-N.b` / `UC-N.c` records.
4. REQ-001 passed only Gate 1, so I kept a single umbrella use case and marked `UC-07` with `<!-- cluster: heterogeneous -->`.
5. REQ-002 through REQ-008 failed Gate 1, so I kept a single umbrella UC for each with no special Cartesian marking.
6. REQ-001 is the only Gate 1 pattern cluster in this exploration, and it carries `Pattern: parity`.

## Candidate Bugs for Phase 2

1. **[Open exploration] Legacy docs-source warning drift** - `docs_present()` and three runner call sites still warn on missing `docs_gathered/` even though the live Phase 1 contract uses `reference_docs/` (`bin/run_playbook.py:1552-1559`, `bin/run_playbook.py:2241-2246`, `bin/run_playbook.py:2314-2319`, `bin/run_playbook.py:2611-2616`, `bin/run_playbook.py:621-630`).
2. **[Open exploration] Phase 2 gate is under-enforced** - `check_phase_gate()` permits any `EXPLORATION.md` with at least 120 lines, ignoring the exact heading contract in `SKILL.md` (`SKILL.md:1026-1042`, `bin/run_playbook.py:1158-1165`).
3. **[Open exploration] Live index hardcodes the wrong project type** - run metadata still writes `Code` even though classifier output supports `Skill` and `Hybrid` (`bin/classify_project.py:261-286`, `bin/run_playbook.py:1819-1831`, `bin/run_playbook.py:1888-1895`).
4. **[Quality risk] Byte-equality citation verification can silently degrade on installed targets** - the gate warns and skips when `bin/citation_verifier` is absent, while setup currently installs only `quality_gate.py` into benchmark targets (`.github/skills/quality_gate/quality_gate.py:32-44`, `.github/skills/quality_gate/quality_gate.py:1823-1864`, `repos/setup_repos.sh:195-200`).
5. **[Pattern deep dive: Fallback and Degradation Path Parity] Direct bootstrap versus harness-installed bootstrap sees different docs** - the harness mirrors `docs_gathered/` into `reference_docs/`, but direct-root bootstrap does not (`repos/setup_repos.sh:202-220`, `docs_gathered/30_benchmark_protocol_and_self_audit.md:87-99`).
6. **[Quality risk] Cleanup fallback can kill unrelated sessions** - `_pkill_fallback()` is workstation-wide rather than run-scoped (`bin/run_playbook.py:2836-2865`).
7. **[Quality risk] Curated bootstrap docs are stale enough to mis-seed future requirements** - the docs pack still frames older releases and older documentation paths as current (`docs_gathered/01_README_project.md:1-29`, `docs_gathered/29_improvement_axes_and_version_history.md:68-72`, `README.md:1-5`, `README.md:15-50`).

## Gate Self-Check

- `quality/EXPLORATION.md` has more than 120 lines.
- Required exact headings present: `## Open Exploration Findings`, `## Quality Risks`, `## Pattern Applicability Matrix`, `## Candidate Bugs for Phase 2`, `## Gate Self-Check`.
- Pattern deep dives present: 3 (`Fallback and Degradation Path Parity`, `Cross-Implementation Contract Consistency`, `Enumeration and Representation Completeness`).
- Exactly 3 patterns are marked `FULL` in the applicability matrix.
- `## Open Exploration Findings` contains 9 concrete bug hypotheses, and at least 3 of them trace across multiple files/functions (findings 1, 3, 4, 6, 7, and 8 do).
- `## Candidate Bugs for Phase 2` includes multiple bugs from open exploration/risks and at least one sourced from a pattern deep dive.
- User-requested content included: domain and stack identification, architecture map, test inventory, specification summary, quality risks, skeleton/dispatch/state-machine analysis, REQ blocks, UC blocks, and Cartesian UC confirmation.
