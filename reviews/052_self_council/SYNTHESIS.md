# Instruction 052 — v1.5.10 repo-hygiene release — 3-panel self-Council synthesis

**Scope reviewed:** the complete A–E change, commits `20c7976..a3a5ca2` (9 commits) on branch `1.5.10`. Protocol 1, three independent adversarial panelists + a defensive-sweep charter folded into each.

**Outcome: UNANIMOUS SHIP (round 1).** No FIX-REQUIRED; only NITs (recorded below, none blocking).

## Verdicts
| Panel | Charter | Verdict |
|---|---|---|
| A | cleanup correctness (Phase A) + defensive sweep | **SHIP** |
| B | trim + reconciliation correctness (Phases B/C) + defensive sweep | **SHIP** |
| C | relocation + install-contract preservation (Phase D) + Phase-E + defensive sweep | **SHIP** |

## Panel A — cleanup (SHIP)
- Removed/gitignored paths (quality/ except quality/audits/, top-level previous_runs/, spike/, metrics/classifier_verification.log, .github/skills/quality_gate/) are gone from tracking; no live source/test reads them. `execution_gate_loader.load_archived_runs` takes a guarded param (not a hardcoded read); the `.github/skills/quality_gate/quality_gate.py` strings in divergence_* modules are literal adopter-provenance labels, not fs reads.
- **quality/audits/ carve-out PROVEN on a fresh clone**: `ls quality/` → only `audits`; test_192_audit_log + test_schemas_audit_191 → OK.
- Gate-suite PORT correct: test_quality_gate_gates.py 305 OK; the 2 repointed importers (test_phase_sentinel_109, test_run_playbook_gate_verdict_reader_109fix) pass; 2 green satellites pass; fixtures tracked as renames. No dangling import of any dropped/renamed module.
- Full suite: 2411, exactly the 3 known baseline README failures, no new.
- **NIT:** the 6 dropped satellites' failure is partly path-rot (collection-time import error from the obsolete `skills/quality-playbook/scripts` path) as well as genuine assertion drift; the commit message frames them as behavior-rotted. (Both are true — 090x's nats_run2 + verdict_taxonomy's check-category assertions genuinely fail against the current gate — but the path-rot is the immediate collection error.) Documented + history-retained + scoped to a future instruction; non-blocking.

## Panel B — trim + reconciliation (SHIP)
- All 6 sections moved with heading + `` See `references/X.md` `` pointer retained inline. Pinned-inline content confirmed present in SKILL.md: Phase-7 Canonical-treatment paragraph (NOT moved); 3 inverted-default-continue boundaries (≥3 floor held); zero old unconditional-STOP phrasing; AGENTS.md self-encoding string; Mode-A self-exec block; F21 asymmetry (test asserts on the headings, all passing).
- CONSOLIDATES are reconcile-not-append: run_state_schema.md is authoritative + schema_version refreshed to 1.5.8 (title + body, with rationale); spec_audit.md GAINED a labeled "Phase 4 operational rules" subsection (effective-council gating, pre-audit spot-checks, post-spec-audit regression, auditor artifacts, completion gate). Nothing lost; the Phase-4 13-check gate detail is genuinely redundant (lives in phase_prompts/phase1.md).
- No stale `SKILL.md:NNNN` self-refs remain. Phase C: ceiling 32000→20000 with rationale, live 18,478 < 20,000; reference-resolves validator + regression test present + clean.
- Per-commit --stat confirms genuine MOVES (SKILL.md loses lines, ref gains them), not copies. `--check-skill-references` PASS.
- **NIT:** a pre-existing `**Read \`references/iteration.md\`**` pointer (SKILL.md line 342) uses the older `Read` dialect; it predates this release and is NOT one of the 6 moved sections (the iteration-mode summary was not extracted). All 6 newly-created pointers use the single `See` form. Pre-existing cosmetic debt, non-blocking.

## Panel C — relocation + contract preservation (SHIP)
- Layout correct: root SKILL.md is a REAL file (81,641 bytes); in-tree are relative symlinks resolving to root (not dangling). `test_skill_resolution_order.py` UNCHANGED in the range — no canonical fallback list reordered.
- The source-side `_resolve_bundle_source_root` reorder (nested-209 → nested-208 → bare) is correct for all three cases (clone root → nested skill folder; skill folder → itself; pre-208/adopter → itself); traced directly.
- Build ships REAL files: stage() → real SKILL.md, content matches root, 28 real references, no symlinks. `_assert_staged_files_are_real` exists, is wired into stage(), and BITES when a symlink is planted (verified).
- Gate path-pins (C1): SCRIPT_DIR/../SKILL.md resolves through the symlink to root. Skill/Hybrid (C2): `_phase4_project_type_from_artifact_shape` returns None (defer to role map) for QPB root post-relocation — correct, not a defect (QPB genuinely is a skill at root now); returns "Code" only for code-shaped repos.
- Install E2E from the relocated layout delivers a real SKILL.md + 28 references.
- Phase-E mechanical confirmation is an acceptable ship-gate posture for a pure relocation/packaging release where every behavioral surface is covered deterministically; the live `--claude` recall regression is documented operator scope.
- **NIT:** the 3 baseline README failures (README drift: missing "Step 4" subsection + stale LAUNCH_PROMPT_LINES pins) predate the range (README last changed in v1.5.9; the 3 failing test files untouched here; reproduced identically against base `377896f`). Out of scope for v1.5.10; recommend an operator-scope README re-pin — not a ship blocker.

## Disposition
All NITs are non-blocking and recorded honestly in `outputs/052-v1.5.10-repo-hygiene.md`. No fixes required for SHIP. The release is the source work only; push/tag/version-stamp/CHANGELOG/awesome-copilot PR remain operator/orchestrator steps (out of worker scope), as does the live multi-repo `--claude` recall-regression benchmark.
