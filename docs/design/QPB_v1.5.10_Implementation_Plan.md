# Quality Playbook v1.5.10 — Implementation Plan

*Companion to: `QPB_v1.5.10_Design.md`. Single workstream: the SKILL.md trim, moved verbatim from the v1.5.9 umbrella plan's Phase 2 on 2026-06-11 (operator decision: v1.5.9 refocused on the harness + standalone distribution). The phase letters below preserve the original 2A-2E structure for continuity with prior discussion; they are the whole release.*

*Authored under explicit operator carve-out from the default "QPB source files are propose-don't-edit" rule.*

---

## Phase 2A — Audit current SKILL.md content

- Catalog every section in the current SKILL.md by phase scope (Phase 1 only / Phase 2 only / cross-phase / contract-level)
- For each section, classify: STAYS in SKILL.md / MOVES to references / DUPLICATES existing reference (consolidate)
- Result: an audit table with file:line → destination

## Phase 2B — Mechanical extraction

- Move classified sections to `references/phase_<N>_*.md` files per the audit table
- Where target reference files already exist (`phase1_exploration_guide.md`, `phase2_generation_guide.md`, etc.), CONSOLIDATE — don't create duplicates
- Each extraction is a single commit per phase-N detail file, traceable to the audit table

## Phase 2C — SKILL.md restructure

- Replace extracted sections in SKILL.md with one-line `Read references/phase_N_<purpose>.md` directives
- Verify the trimmed SKILL.md still flows readably (the agent reads SKILL.md top-to-bottom; reference loads happen at phase boundaries)
- Final SKILL.md target: ~200-400 lines

## Phase 2D — Validator + token-ceiling update

- `quality_gate.py` gains the reference-resolves invariant
- `bin/tests/test_skill_md_size.py` ratchets the ceiling from 32K to ~12K (or whatever empirical post-trim size + a small buffer)
- Add a regression test that asserts `Read references/X.md` directives in SKILL.md all resolve

## Phase 2E — Benchmark regression run

- Standard 3-5 repo benchmark plan run against the trimmed SKILL.md (candidate substrate: the v1.5.9 harness skill — its first real multi-repo QPB workload)
- Compare bug recall + REQUIREMENTS quality + Phase 6 verdict accuracy vs the pre-trim baseline
- If recall drops materially, identify which extracted reference content the agent isn't loading and either: (a) move it back to SKILL.md, or (b) strengthen the load directive

## Ship Gate

- Council Self-Review Protocol 1 with three panelists (audit-table completeness, mechanical-extraction correctness, recall-regression sufficiency) + the defensive-sweep charter (see `DEVELOPMENT_PROCESS.md`). Note: "QPB Phase 1 (Explore)" in any sweep example means the audit pipeline's phase, not a release phase.
- Trimmed SKILL.md passes the new validator + token-ceiling test
- Benchmark regression run shows no material recall degradation
- **awesome-copilot re-submission test:** regenerate the packet shipping the now-trimmed canonical SKILL.md directly; submit PR; iterate if rejected
- Release prep: version stamps, CHANGELOG, README/TOOLKIT updates, Council umbrella review, tag + close-out per `DEVELOPMENT_PROCESS.md`

---

## Open work-items tracker

*Item numbers are plan-local — always name the plan when cross-referencing a work item.*

| # | Item | Phase | Status |
|---|------|-------|--------|
| 1 | SKILL.md content audit | 2A | PENDING — begins after v1.5.9 ships |
| 2 | Mechanical content extraction | 2B | PENDING audit |
| 3 | SKILL.md restructure + reference directives | 2C | PENDING extraction |
| 4 | Reference-resolves validator | 2D | PENDING |
| 5 | Token-ceiling ratchet (32K → ~12K) | 2D | PENDING |
| 6 | Benchmark regression run | 2E | PENDING implementation |
| 7 | awesome-copilot re-submission with full canonical SKILL.md | Ship Gate | PENDING |
| 8 | Release ship steps | Ship Gate | PENDING |

---

*End of v1.5.10 Implementation Plan. Design in `QPB_v1.5.10_Design.md`. Predecessor release in `QPB_v1.5.9_Design.md` + `QPB_v1.5.9_Implementation_Plan.md`. Successor backlog in `QPB_v1.5.11_Design.md` + `QPB_v1.5.11_Implementation_Plan.md`.*
