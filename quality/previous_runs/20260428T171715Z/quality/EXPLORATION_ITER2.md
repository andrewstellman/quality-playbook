# Exploration Iteration 2 — gap strategy

Resolved skill path: `SKILL.md`
Resolved references path: `references/`
Date: 2026-04-28
Strategy: `gap`

## Open Exploration Findings

### Gap target 1 — later-phase prompt portability

- The documented install-location fallback order is explicit in the live skill: `SKILL.md`, `.claude/skills/quality-playbook/SKILL.md`, `.github/skills/SKILL.md`, `.github/skills/quality-playbook/SKILL.md` (`SKILL.md:49-58`).
- `bin/run_playbook.py` now centralizes that list in `SKILL_FALLBACK_GUIDE` and uses it in `phase1_prompt()`, `single_pass_prompt()`, and `iteration_prompt()` (`bin/run_playbook.py:613-618`, `bin/run_playbook.py:621-626`, `bin/run_playbook.py:1122-1134`).
- The Phase 2 through Phase 6 prompt builders do **not** use that shared guide. Each later prompt still tells the child agent to read `.github/skills/SKILL.md` directly, and several also hardcode `.github/skills/references/...` (`bin/run_playbook.py:726-752`, `bin/run_playbook.py:755-908`, `bin/run_playbook.py:911-964`, `bin/run_playbook.py:967-1088`).
- This means the portability fix landed only on the entry prompts. A run that starts from repo-root `SKILL.md` or a Claude install can complete Phase 1, but later phases are still instructed to pivot to a flat Copilot layout that may not exist.
- The drift is not just cosmetic path text. The later prompts tell the child which files to read before generating artifacts, code reviews, writeups, and verification output. If the named path is absent, the child starts from an incorrect or missing brief.
- Phase 5 compounds the issue by naming `.github/skills/SKILL.md` as the canonical location for the writeup template itself (`bin/run_playbook.py:974-980`), so a valid repo-root or Claude-layout run can fail exactly at the point where bug writeups are supposed to close the loop.
- Phase 6 repeats the same flat-path assumption when instructing the verifier to read the verification section (`bin/run_playbook.py:1089-1090`), so even the terminal benchmark phase is anchored to one install layout instead of the documented fallback list.

### Gap target 2 — repository-side SKILL discovery and warning behavior

- `bin/benchmark_lib.py` defines `SKILL_INSTALL_LOCATIONS` as `.github/skills/SKILL.md`, `.claude/skills/quality-playbook/SKILL.md`, `SKILL.md`, `.github/skills/quality-playbook/SKILL.md` (`bin/benchmark_lib.py:42-47`).
- That order diverges from the live skill's published order in two ways:
  1. repo-root `SKILL.md` is documented first but searched third;
  2. the nested Copilot path exists in the tuple but is treated as a last-resort add-on rather than part of the canonical four-path order.
- `find_installed_skill()` inherits that tuple unchanged and explicitly documents the old order in its docstring (`bin/benchmark_lib.py:153-164`).
- `detect_repo_skill_version()` also walks the same tuple (`bin/benchmark_lib.py:144-150`), so the version shown to operators can come from a flat installed copy even when the documented first hit is the repo-root skill.
- `run_playbook.resolve_target_dirs()` depends on `find_installed_skill()` to decide whether to warn, and its warning text names only three locations: flat Copilot, Claude, and repo root (`bin/run_playbook.py:592-597`).
- The nested Copilot path is omitted from the warning entirely, so a repo that installs the skill only at `.github/skills/quality-playbook/SKILL.md` can still receive a false "No SKILL.md found" warning even though the live skill explicitly treats that path as valid.
- This is a product-surface bug rather than a pure helper-library nit. Target resolution is the operator's first confirmation that the playbook is installed correctly; stale search order and stale warning text teach the wrong support matrix.

### Gap target 3 — orchestrator contract fidelity

- The general orchestrator agent documents the canonical order correctly: repo root, Claude, flat Copilot, nested Copilot (`agents/quality-playbook.agent.md:37-45`).
- The Claude-specific orchestrator does not. It lists repo root first, Claude second, **nested Copilot third**, and flat Copilot fourth (`agents/quality-playbook-claude.agent.md:45-54`).
- That reversal matters when both Copilot layouts are present or when an operator compares the Claude agent's instructions with the live skill. The agent file is supposed to be the operational brief for the orchestrator session; if it enumerates a different order, it teaches a different resolution rule.
- The inconsistency is especially visible because the repo now contains three path-order authorities:
  1. `SKILL.md` with the documented canonical order;
  2. `agents/quality-playbook.agent.md` matching that order;
  3. `agents/quality-playbook-claude.agent.md` reversing the two Copilot variants.
- The result is a split-brain install contract: the same shipped product gives different answers about which valid path wins.

### Gap target 4 — iteration/progress contract compatibility

- `iteration_prompt()` correctly reminds the child not to rewrite the phase tracker and to let the orchestrator append `## Iteration: ...` sections (`bin/run_playbook.py:1127-1134`).
- `_append_iteration_heartbeat()` is append-only and never rewrites the existing phase tracker (`bin/run_playbook.py:2388-2408`).
- The uncovered risk is therefore not the heartbeat writer itself; it is the later-phase prompt family and setup helpers, which still point iteration-phase children at one install layout even though the iteration prompt tells them to honor the full fallback contract.
- In other words, the progress-writing surface is now correct, but the file-resolution surface that iteration children follow after that reminder is still partially stale.

## Quality Risks

1. **Phase portability can still fail after a clean Phase 1.** The baseline entry prompt can resolve the right skill file, but later phases can still be redirected to `.github/skills/SKILL.md` and `.github/skills/references/...`, breaking repo-root or Claude-layout runs without changing the operator's original invocation.
2. **Operator trust in installation detection can drift silently.** A warning that omits the nested Copilot path or prefers a flat installed copy over the documented repo-root first-hit order can make a correct install look suspicious or make a stale copy look canonical.
3. **Different orchestrator documents can pick different valid paths.** When the generic orchestrator and the Claude orchestrator disagree on fallback order, the same repo can receive different instructions depending on which agent entry point is used.
4. **Iteration hardening can be partial and success-shaped.** The entry prompt and heartbeat rules can be correct while the phase-specific follow-on prompts still teach stale paths, making iteration runs look hardened while carrying a later-phase portability gap.

## Pattern Applicability Matrix

| Pattern | Status | Why it applies here |
| --- | --- | --- |
| Fallback and Degradation Path Parity | FULL | The same skill must resolve from four install locations, and the product currently has multiple independent helpers/docs that should all follow one order. |
| Cross-Implementation Contract Consistency | FULL | `SKILL.md`, `run_playbook.py`, `benchmark_lib.py`, and both orchestrator agents all describe or enforce the same resolution contract. |
| Enumeration and Representation Completeness | FULL | The fallback list is a closed set of four paths; omitting one path or swapping the documented order is a mechanically checkable divergence. |
| Defensive / State-Machine Analysis | PARTIAL | The iteration/progress surface is stateful, but the primary failure mode here is stale path-selection guidance rather than lifecycle logic. |
| API Surface Consistency | PARTIAL | Operators treat target resolution warnings and generated prompts as an API-like contract; the bug is that different surfaces advertise different supported layouts. |

## Pattern Deep Dive — Fallback and Degradation Path Parity

### Prompt family parity

- **Baseline-fixed paths:** `phase1_prompt()`, `single_pass_prompt()`, and `iteration_prompt()` use `SKILL_FALLBACK_GUIDE` (`bin/run_playbook.py:621-626`, `1122-1134`).
- **Later-phase paths:** `phase2_prompt()` through `phase6_prompt()` still hardcode `.github/skills/SKILL.md` and `.github/skills/references/...` (`bin/run_playbook.py:726-752`, `755-908`, `911-964`, `967-1090`).
- **Parity gap:** the runner's own prompts no longer form a coherent family. The safe path-resolution contract exists at run entry but is lost once the run advances.
- **Candidate requirement:** REQ-009.

### Helper / warning parity

- **Documented authority:** `SKILL.md` publishes one four-path order (`SKILL.md:49-58`).
- **Helper implementation:** `benchmark_lib.SKILL_INSTALL_LOCATIONS` searches a different order and treats nested Copilot as a trailing fallback (`bin/benchmark_lib.py:42-47`).
- **Operator-facing warning:** `resolve_target_dirs()` mentions only three locations and omits the nested Copilot path entirely (`bin/run_playbook.py:592-597`).
- **Parity gap:** the detection tuple, the helper docstring, and the warning message are not aligned with the skill's canonical fallback list.
- **Candidate requirement:** REQ-010.

### Orchestrator parity

- **Generic orchestrator:** matches the canonical order (`agents/quality-playbook.agent.md:37-45`).
- **Claude orchestrator:** reverses flat vs nested Copilot (`agents/quality-playbook-claude.agent.md:47-54`).
- **Parity gap:** the two shipped orchestrator entry points teach different first-hit semantics for the same support matrix.
- **Candidate requirement:** REQ-010.

## Pattern Deep Dive — Enumeration and Representation Completeness

### The fallback list is a closed set

- The live skill defines exactly four supported SKILL lookup paths (`SKILL.md:49-58`).
- Later-phase prompts currently mention only one of those paths (`bin/run_playbook.py:732`, `763`, `918`, `974`, `980`, `1089`).
- The target-resolution warning currently mentions only three paths (`bin/run_playbook.py:594-596`).
- The Claude orchestrator enumerates all four paths but orders the Copilot variants differently (`agents/quality-playbook-claude.agent.md:47-54`).
- These are closed-set defects: the problem is not vague "path confusion" but mechanically missing or re-ordered entries in a canonical four-path list.

## Testable Requirements Derived

### REQ-009: Every runner-generated phase prompt must honor the documented install-location fallback list

- **Summary:** Phase 2 through Phase 6 prompts must instruct child agents to resolve `SKILL.md` and `references/*.md` via the same four-path fallback list that Phase 1, single-pass, and iteration prompts now use.
- **References:** `SKILL.md:49-58`; `bin/run_playbook.py:613-618`; `bin/run_playbook.py:726-752`; `bin/run_playbook.py:755-908`; `bin/run_playbook.py:911-1090`

### REQ-010: Repository-side SKILL discovery surfaces must use the documented four-path order

- **Summary:** Helper discovery, operator-facing warnings, and shipped orchestrator docs must enumerate all four supported SKILL locations in the documented order: repo root, Claude, flat Copilot, nested Copilot.
- **References:** `SKILL.md:49-58`; `bin/benchmark_lib.py:42-47`; `bin/benchmark_lib.py:144-164`; `bin/run_playbook.py:592-597`; `agents/quality-playbook.agent.md:37-45`; `agents/quality-playbook-claude.agent.md:45-54`

## Use Cases Derived

### UC-08: Later-phase child agents continue a run from a non-flat install layout

- **Actor:** Later-phase AI agent
- **Preconditions:** Phase 1 already completed and the repo resolves the skill from repo root, Claude layout, or nested Copilot layout.
- **Steps:**
  1. Read the next-phase prompt emitted by `bin/run_playbook.py`.
  2. Resolve the skill file and reference files from the documented fallback list.
  3. Continue the run without needing a flat `.github/skills/` layout.
- **Postconditions:** Later phases inherit the same install-location contract that Phase 1 used.

### UC-09: Operator verifies installation on any documented skill layout

- **Actor:** Benchmark operator or orchestrator
- **Preconditions:** The target repo may expose only one of the four documented SKILL locations.
- **Steps:**
  1. Resolve the installed skill using helper code or orchestrator setup instructions.
  2. Compare the hit against the documented order.
  3. Warn only when all four supported paths are absent.
- **Postconditions:** Installation detection and warnings reflect the real support matrix rather than a stale subset.

## Candidate Bugs for Phase 2

1. **BUG-008 candidate — later-phase prompts still hardcode the flat Copilot layout.** `phase2_prompt()` through `phase6_prompt()` keep telling child agents to read `.github/skills/SKILL.md` and `.github/skills/references/...` even though the documented contract is the four-path fallback list (`bin/run_playbook.py:726-752`, `755-908`, `911-1090`; `SKILL.md:49-58`).
2. **BUG-009 candidate — repository-side skill detection still walks an outdated fallback list and warning text omits the nested Copilot path.** `SKILL_INSTALL_LOCATIONS`, `find_installed_skill()`, `detect_repo_skill_version()`, and `resolve_target_dirs()` do not match the canonical four-path order or full path set (`bin/benchmark_lib.py:42-47`, `144-164`; `bin/run_playbook.py:592-597`).
3. **BUG-010 candidate — the Claude orchestrator reverses the two Copilot fallback positions.** `agents/quality-playbook-claude.agent.md` teaches nested Copilot before flat Copilot, contradicting both `SKILL.md` and the generic orchestrator agent (`agents/quality-playbook-claude.agent.md:47-54`; `SKILL.md:49-58`; `agents/quality-playbook.agent.md:37-45`).

## Gate Self-Check

1. This iteration explored code areas the baseline only touched lightly: later-phase prompt builders, benchmark install detection helpers, and the orchestrator setup docs.
2. The findings are code-path-specific and cite concrete file:line evidence instead of restating generic "install drift."
3. The candidate set adds three new portability / detection defects not present in the baseline BUG tracker.
4. The new findings directly exercise the gap strategy: they target uncovered parts of the install-location fallback contract rather than re-reading the baseline docs-intake bugs.
