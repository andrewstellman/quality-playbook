# Iteration Plan — quality-playbook

Latest strategy: **adversarial** (Iteration 5)
Date: 2026-04-28
Resolved skill path: `SKILL.md` (repo root)
Resolved references path: `references/` (repo root)

---

## Iteration 5 — `adversarial` (current)

### Why this iteration

The first four iterations covered different angles: baseline (cross-surface drift), gap (install-location fallback), unfiltered (runtime/gate/audit code), and parity (cross-path comparison). Each enumerated more candidate findings than the orchestrator's downstream Phase 2–5 cycle promoted. The result is a large pool of "pending Phase 2 promotion" candidates plus a formal Demoted Candidates Manifest (DC-001 through DC-007) — exactly the failure mode the adversarial strategy targets.

This iteration uses the adversarial strategy from `references/iteration.md`: re-investigate dismissed/demoted findings with a deliberately lower evidentiary bar, then challenge SATISFIED verdicts in the Phase 3 code review.

### Lightweight previous-run scan (load order)

1. `quality/EXPLORATION_MERGED.md` — `## Demoted Candidates` section (DC-001 through DC-007) for the structured re-promotion criteria.
2. `quality/EXPLORATION_MERGED.md` — `## Candidate Bugs for Phase 2` (BUG-011 through BUG-027 are listed "pending Phase 2 promotion" but were never promoted to `quality/BUGS.md`).
3. `quality/BUGS.md` — confirmed bugs (BUG-001 through BUG-010) so we don't re-file them.
4. `quality/spec_audits/2026-04-28-triage.md` and `quality/spec_audits/2026-04-28-gap-triage.md` — dismissed findings absorbed into existing bugs.
5. `quality/code_reviews/2026-04-28-phase3-review.md` Pass 2 — SATISFIED verdicts with thin evidence (REQ-001 is the only SATISFIED requirement).

### Targets selected for adversarial re-investigation

**Pool A — unpromoted iteration candidates.** BUG-011 through BUG-027 are recorded in `EXPLORATION_MERGED.md` as "pending Phase 2 promotion" but never reached `quality/BUGS.md`. The orchestrator's cycle reported "0 net-new" after both unfiltered and parity iterations, so these candidates are de facto demoted. Re-investigate the highest-evidence candidates by reading the cited code directly:

- BUG-011: `bin/citation_verifier.py:244-266` path traversal (HIGH severity).
- BUG-012: `.github/skills/quality_gate.py:802-829` `bug_count` asymmetric arms (MEDIUM).
- BUG-013: `.github/skills/quality_gate.py:875-883` `>=` vs `==` (MEDIUM).
- BUG-014: `.github/skills/quality_gate.py:894-901` summary value sanity (MEDIUM).
- BUG-018: `bin/council_semantic_check.py::write_semantic_check` empty `reviews[]` ambiguity (MEDIUM).
- BUG-021: `bin/reference_docs_ingest.py::_iter_candidates` symlink boundary (MEDIUM).
- BUG-022 (F-1): phase prompts split PROGRESS.md authorship contract (LOW–MEDIUM).
- BUG-023 (F-2): Phase 5 prompt does not enumerate verdict / recommendation closed-sets (MEDIUM).
- BUG-025 (F-3): non-atomic JSON manifest writes (LOW–MEDIUM).
- BUG-026 (F-4): `run_timestamp` format incompatible with `extended_from_compact()` (LOW).

**Pool B — formal Demoted Candidates Manifest.** Re-read each of DC-001 through DC-007 with the re-promotion criteria from the manifest. Apply a lower evidentiary bar — observable semantic drift from a documented contract is sufficient even without a runtime crash.

**Pool C — SATISFIED verdicts.** Pass 2 of the Phase 3 code review marked REQ-001 SATISFIED with single-line evidence (`quality/mechanical/skill_entry_hashes.txt:1-2` — both entry points hash equal). Challenge whether the satisfaction holds across all four documented install paths, not just the two that the mechanical contract hashes today.

### Adversarial evidentiary bar

Per `references/iteration.md`:
- Code-path trace showing observable semantic drift is sufficient (no runtime crash needed).
- "Permissive behavior" is not automatically a design choice — check the spec / docs / API contract.
- Trace independently. Do not rely on the previous run's analysis.
- Make explicit CONFIRMED / FALSE-POSITIVE determinations with fresh evidence.
- Update Demoted Candidates Manifest entries: status to RE-PROMOTED or FALSE POSITIVE with attribution.

### Findings written to

`quality/EXPLORATION_ITER5.md`. Re-promoted findings are merged into `quality/EXPLORATION_MERGED.md` as new BUG-NNN candidates. The Demoted Candidates Manifest is updated in-place with status changes.

### Minimum output (per `references/iteration.md`)

- ≥80 lines of substantive content in `quality/EXPLORATION_ITER5.md`.
- ≥2 new candidates not present in previous iterations OR ≥1 finding re-confirms a previously dismissed candidate with fresh evidence.
- At least one explicit CONFIRMED / FALSE-POSITIVE determination per Pool A or Pool B target re-investigated.

---

## Iteration 4 — `parity` (historical)

### Why this iteration

The first three iterations covered different angles: the baseline ran the structured three-stage exploration (cross-surface drift), the gap iteration filled in install-location fallback coverage, and the unfiltered iteration drove pure domain-knowledge reads of the runtime, gate, and audit code. None of them systematically lined up *parallel* implementations of the same logical contract and diffed them against each other. That gap matters because the codebase ships several families of code paths that must behave identically — phase prompt builders, citation verifiers (Layer 1 vs Layer 2), agent orchestrators, multiple sidecar JSON writers, and the runtime gate vs the standalone `quality_gate.py`.

This iteration uses the parity strategy from `references/iteration.md`. It enumerates parallel groups, performs pairwise diffs against each comparison sub-type (resource lifecycle, allocation/context, identifier, capability, error/exception, iteration/collection), and only files findings where two paths drift from the same documented contract.

### Lightweight previous-run scan

Read `## Candidate Bugs for Phase 2` and `## Demoted Candidates` from `quality/EXPLORATION_MERGED.md` plus the heading list of `quality/BUGS.md`. The merged candidate set covers BUG-001 through BUG-010 (confirmed) and BUG-011 through BUG-021 (unfiltered candidates pending Phase 2 promotion). DC-001 through DC-004 are demoted candidates; this iteration intentionally avoids re-litigating them — that is the adversarial strategy's job.

### Parallel groups enumerated for this iteration

1. **Phase prompt family.** `phase1_prompt()` through `phase6_prompt()` and `iteration_prompt()` in `bin/run_playbook.py`. All seven prompts must honor the same install-location fallback contract, the same orchestrator-vs-iteration-work rule for PROGRESS.md, and the same artifact-naming conventions.
2. **Citation verification layers.** `bin/citation_verifier.py` (Layer 1 byte-equality) vs `bin/council_semantic_check.py` (Layer 2 semantic check). Both consume `quality/formal_docs_manifest.json`, both verify citations, both write structured outputs. Boundary checks, error reporting, and manifest schema use should match.
3. **Agent orchestrator briefs.** `agents/quality-playbook.agent.md`, `agents/quality-playbook-claude.agent.md`, `agents/quality-playbook-codex.agent.md` (and any other shipped orchestrator) — each must teach the same canonical four-path fallback order, the same six-phase plan, and the same iteration-mode contract.
4. **Quality gate vs runtime Phase 2 gate.** `.github/skills/quality_gate.py` (terminal gate) and `bin/run_playbook.py::check_phase_gate()` (runtime gate enforced before phase advance) both enforce Phase 2 contract slices. They should agree on the required heading set, the line/content thresholds, and the manifest invariants.
5. **Sidecar JSON writers.** `tdd-results.json`, `integration-results.json`, `recheck-results.json`, `formal_docs_manifest.json`, `requirements_manifest.json`, `use_cases_manifest.json`, `bugs_manifest.json`, `citation_semantic_check.json`. Each declares `schema_version` and `skill_version`, but the rigor (date hygiene, enum validation, summary sanity) varies.
6. **Setup vs cleanup paths.** `bin/run_playbook.py` start-of-run setup (PID file creation, run-metadata creation, archive prep) vs end-of-run cleanup (`_pkill_fallback`, archive close, run-metadata `end_time` update). Each resource acquired in setup must be released in cleanup.

### Comparison sub-type checklist (applied to every parallel group)

- Resource lifecycle parity (setup vs teardown coverage)
- Allocation/context parity (lock context, file-mode context, signal-handler context)
- Identifier and index parity (timestamps, run identifiers, manifest keys)
- Capability/feature-bit parity (which contract slices each path enforces)
- Error/exception parity (which path lets exceptions propagate vs swallows them)
- Iteration/collection parity (which collection each path iterates over)

### Minimum output (per `references/iteration.md`)

- At least 5 parallel groups enumerated (this plan lists 6).
- At least 8 pairwise comparisons traced with file:line references.
- At least 3 concrete discrepancy findings, each with both code paths cited and a contract source.

### Findings written to

`quality/EXPLORATION_ITER4.md`. Net-new candidate bugs are merged into `quality/EXPLORATION_MERGED.md`.

---

## Iteration 3 — `unfiltered` (historical)

### Why this iteration

The baseline (Iteration 1) found seven cross-surface drift bugs. The gap iteration (Iteration 2) added three install-location / fallback-list bugs. Both iterations were structured around the documented exploration template and primarily looked at documentation surfaces, install packaging, and skill-path enumeration consistency.

This iteration drops the structural scaffolding entirely. The goal is to read the runtime / orchestration code with no template constraints — entry points, error handling, JSON sidecar enforcement, time / timezone hygiene, regex parsing of LLM responses — and let domain expertise drive the bug hypotheses.

### Lightweight previous-run scan

Read only `## Candidate Bugs for Phase 2` from `quality/EXPLORATION_MERGED.md` and the heading list of `quality/BUGS.md`. The merged candidate set covers BUG-001 through BUG-010. Deliberately NOT loaded: full `EXPLORATION.md` and full `EXPLORATION_ITER2.md` — the unfiltered strategy requires an unanchored read.

### Search surface for this iteration

The previous two runs concentrated on:

- Documentation surfaces (`docs_gathered/`, `reference_docs/`, fallback paths)
- Skill-path enumeration consistency
- Install-time packaging in `repos/setup_repos.sh`

That left these high-leverage surfaces unread or only superficially covered:

1. **Quality gate enforcement code** (`.github/skills/quality_gate.py`, ~3153 lines) — only BUG-002 and BUG-005 touched it, and only via cross-references from elsewhere.
2. **Citation verification** (`bin/citation_verifier.py`, 330 lines) — Layer-1 byte-equality enforcement, never read deeply.
3. **Council semantic check** (`bin/council_semantic_check.py`, 646 lines) — Phase 4 Layer-2, not traced in baseline or gap.
4. **Reference docs ingest** (`bin/reference_docs_ingest.py`, 320 lines) — only behavior-as-described, not the actual file walk.
5. **Runner orchestration error / time hygiene** (`bin/run_playbook.py`, 3109 lines) — the iteration heartbeat plumbing, run-metadata lifecycle, and timestamp construction were not audited as a group.

### Bug hypothesis classes targeted

The unfiltered exploration drove from these domain-knowledge questions:

- Where does `Path(root) / user_supplied` allow `..` or absolute-path escapes? (path-traversal class)
- Where do counters used for cross-check comparisons silently miss a category? (off-by-one in enforcement class)
- Where is `>=` used in places where `==` is the actual contract? (over-permissive comparator class)
- Where does the gate check a JSON key for *presence* but never validate the *value*? (schema-shape-only validation class)
- Where does code mix `datetime.now()` (naive local) with `datetime.now(timezone.utc)` in the same artifact set? (timezone hygiene class)
- Where does a regex extract structured data from LLM output with greedy quantifiers? (greedy-parse class)
- Where do two semantically distinct outcomes produce the same on-disk shape? (output ambiguity class)
- Where does `is_file()` allow a symlink to escape the project tree? (filesystem boundary class)

The exploration findings are written to `quality/EXPLORATION_ITER3.md`. Net-new candidate bugs are merged into `quality/EXPLORATION_MERGED.md`.

---

## Iteration 2 — `gap` (historical)

### Coverage map from baseline EXPLORATION.md

| Baseline section | Main subsystems covered | Finding density | Depth |
| --- | --- | --- | --- |
| Open Exploration Findings | repo identity, runner, citation pipeline, setup script, bootstrap docs | high | medium |
| Quality Risks | docs intake drift, phase-gate drift, index metadata, citation verifier, cleanup safety | medium | shallow-to-medium |
| Pattern Deep Dive — Fallback and Degradation Path Parity | docs intake, cleanup fallback | medium | deep |
| Pattern Deep Dive — Cross-Implementation Contract Consistency | classifier vs index writers, skill gate vs runtime gate, citation install parity | medium | deep |
| Pattern Deep Dive — Enumeration and Representation Completeness | Phase 2 headings, project-type values, citation-verifier install surface | medium | medium |
| Testable Requirements Derived | REQ-001 through REQ-008 | high | summary only |
| Use Cases Derived | UC-01 through UC-07 | medium | summary only |
| Candidate Bugs for Phase 2 | baseline BUG-001 through BUG-007 candidates | medium | summary only |

### Thin / uncovered areas (gap)

1. **Later-phase prompt portability.** The baseline explored prompt generation only lightly. Phase 1 / single-pass / iteration prompt drift was previously hardened, but the phase-2-through-phase-6 prompt family was not traced against the documented install-location fallback contract.
2. **Repository-side install detection.** The baseline did not deeply inspect `bin/benchmark_lib.py` and `resolve_target_dirs()` warning text against the documented four-path fallback order or the alternate nested Copilot install path.
3. **Orchestrator path-order fidelity.** The baseline treated `agents/` as part of the product surface, but it did not trace the Claude orchestrator's explicit SKILL search order against the canonical order documented in `SKILL.md`.
4. **Iteration/progress coupling.** The baseline noted the iteration lifecycle but did not inspect whether progress-writing and later prompts remain compatible with the documented "orchestrator appends iteration sections; iteration work must not rewrite the phase tracker" contract.

### Targeted deep-reads selected for the gap pass

1. `bin/run_playbook.py` prompt builders and iteration prompt (`phase2_prompt()` through `phase6_prompt()`, `iteration_prompt()`).
2. `bin/benchmark_lib.py` install detection helpers plus `bin/run_playbook.py::resolve_target_dirs()`.
3. `agents/quality-playbook.agent.md` and `agents/quality-playbook-claude.agent.md` setup / fallback instructions.

### Gap-strategy exploration goal

Re-run Phase 1 exploration only on the install-location fallback surface:

- Verify that every generated prompt points operators to the same fallback list the skill documents.
- Verify that runtime helper code (`benchmark_lib`, target resolution warnings) walks the same list in the same order, including the nested Copilot install path.
- Verify that the orchestrator agent documents the same order, so repo-root, Claude, flat Copilot, and nested Copilot installs all receive the same instructions.

### Expected candidate classes (gap)

1. Prompt portability regressions in later phases.
2. Resolver / warning drift in benchmark helpers.
3. Orchestrator contract drift between agent docs and the live skill.
