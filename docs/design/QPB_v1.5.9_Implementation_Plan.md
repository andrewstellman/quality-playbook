# Quality Playbook v1.5.9 — Implementation Plan (umbrella)

*Companion to: `QPB_v1.5.9_Design.md`. This is the v1.5.9 **umbrella** plan — it owns Phase 0 (branch hygiene), the SKILL.md-trim workstream (Phase 2), the release ship sequence (Phase 3), and the overall sequencing. The **harness-as-skill** workstream (Phase 1) has its own plan: `QPB_v1.5.9_Harness_Skill_Implementation_Plan.md` (companion to `QPB_v1.5.9_Harness_Skill_Design.md`), which is authoritative for all Phase 1 detail.*

*Status: drafted 2026-06-06, revised 2026-06-07 to match scoped-down design (two focus items: harness-as-skill + SKILL.md trim). **Revised 2026-06-09 to replace the external-scheduler architecture with in-session `ScheduleWakeup` polling** per the second architectural pivot (see `QPB_v1.5.9_Harness_Skill_Design.md` for the empirical rationale). Prior broader-scope phases moved to `QPB_v1.5.10_Implementation_Plan.md`.*

*Revised 2026-06-10: split the harness-as-skill workstream out into `QPB_v1.5.9_Harness_Skill_Implementation_Plan.md`, mirroring the design-doc split (the harness already had its own sub-design). Phase 1 below is now a pointer; the 1A spike, 1B.0 (phase-identity source of truth + unified emission), 1B, scope notes, and the harness work-items tracker all live in the harness sub-plan.*

*Authored under explicit operator carve-out from the default "QPB source files are propose-don't-edit" rule.*

---

## Operating Principles

- **Two independent workstreams** in v1.5.9. They can be implemented in parallel by different worker instructions, or serially in either order. They share no files.
- **Per-workstream Council review.** Each workstream gets its own Self-Council Protocol 1 review at completion. v1.5.9 doesn't ship until both reviews return SHIP.
- **Worker-lane edits** for all source changes (`SKILL.md`, `bin/`, `references/`, `.github/skills/`, schemas, tests). Cowork files instructions; worker implements; Council reviews.
- **No new orientation-doc edits** as part of v1.5.9 implementation. The methodology absorptions (defensive sweep, release close-out sequence) already landed during v1.5.8 close-out. v1.5.10 may surface more.

---

## Phase 0 — Branch hygiene

Before any v1.5.9 work begins:

- Fresh `1.5.9` branch from `main` exists locally and on origin (the rename of the prior daemon-architecture branch to `archive/1.5.9-daemon-architecture` should already be on origin).
- `v1.5.8` tag still on origin at the post-close-out HEAD.
- `main` clean and current.

If the archive branch hasn't been pushed yet, do that first.

---

## Phase 1 — Harness-as-skill (in-session `ScheduleWakeup` architecture)

**Detail lives in `QPB_v1.5.9_Harness_Skill_Implementation_Plan.md` — that sub-plan is authoritative for this phase.** It owns the 1A tracer-bullet spike (instruction 1), Phase 1B.0 (phase-identity source of truth + unified emission — foundational, filed first in 1B), Phase 1B production hardening (instruction 2), the 1A scope notes (A–H), the sub-Council, and the harness work-items tracker.

In brief: replace the Python subprocess harness with a `quality-playbook-harness` skill that runs inside the operator's Claude Code session and dispatches workers via the `Task` tool, driven by in-session `ScheduleWakeup` polling. The order within the phase is **1A spike → 1B.0 → rest of 1B**. The harness workstream is parallelizable with Phase 2 below.

---

## Phase 2 — SKILL.md trim

### Phase 2A — Audit current SKILL.md content

- Catalog every section in the current 1256-line SKILL.md by phase scope (Phase 1 only / Phase 2 only / cross-phase / contract-level)
- For each section, classify: STAYS in SKILL.md / MOVES to references / DUPLICATES existing reference (consolidate)
- Result: an audit table with file:line → destination

### Phase 2B — Mechanical extraction

- Move classified sections to `references/phase_<N>_*.md` files per the audit table
- Where target reference files already exist (`phase1_exploration_guide.md`, `phase2_generation_guide.md`, etc.), CONSOLIDATE — don't create duplicates
- Each extraction is a single commit per phase-N detail file, traceable to the audit table

### Phase 2C — SKILL.md restructure

- Replace extracted sections in SKILL.md with one-line `Read references/phase_N_<purpose>.md` directives
- Verify the trimmed SKILL.md still flows readably (the agent reads SKILL.md top-to-bottom; reference loads happen at phase boundaries)
- Final SKILL.md target: ~200-400 lines

### Phase 2D — Validator + token-ceiling update

- `quality_gate.py` gains the reference-resolves invariant
- `bin/tests/test_skill_md_size.py` ratchets the ceiling from 32K to ~12K (or whatever empirical post-trim size + a small buffer)
- Add a regression test that asserts `Read references/X.md` directives in SKILL.md all resolve

### Phase 2E — Benchmark regression run

- Standard 3-5 repo benchmark plan run against the trimmed SKILL.md
- Compare bug recall + REQUIREMENTS quality + Phase 6 verdict accuracy vs the pre-trim baseline
- If recall drops materially, identify which extracted reference content the agent isn't loading and either: (a) move it back to SKILL.md, or (b) strengthen the load directive

### Phase 2 Ship Gate

- Council Self-Review Protocol 1 with three panelists (audit-table completeness, mechanical-extraction correctness, recall-regression sufficiency)
- Trimmed SKILL.md passes the new validator + token-ceiling test
- Benchmark regression run shows no material recall degradation
- **awesome-copilot re-submission test:** regenerate the awesome-copilot packet WITHOUT the trim (ship the now-trimmed SKILL.md directly); confirm size is acceptable; submit PR
  - If awesome-copilot accepts → trim succeeded its primary goal
  - If awesome-copilot still rejects → diagnose and iterate

---

## Phase 3 — Release prep + ship

After both Phase 1 and Phase 2 ship gates return SHIP:

- Version stamps to `1.5.9` across `pyproject.toml`, `package.json`, `quality_playbook_cli/__init__.py`
- README.md + ai_context/TOOLKIT.md updates for any user-visible changes (the harness invocation flow IS different — operators set up scheduled tasks instead of running `qpb run-plan`)
- DEVELOPMENT_CONTEXT.md refresh
- CHANGELOG entry for 1.5.9
- Council umbrella review (full nested 9-perspective per `DEVELOPMENT_PROCESS.md` § Council protocol) before tag
- Tag + release close-out sequence per `DEVELOPMENT_PROCESS.md` § Release close-out sequence:
  1. Push 1.5.9 branch
  2. Tag move (initial tag at release-HEAD)
  3. Live publishes (pip + npm + awesome-copilot — using the now-trimmed SKILL.md directly)
  4. README + TOOLKIT install instruction updates (note any harness-as-skill operator workflow changes)
  5. DEVELOPMENT_CONTEXT refresh
  6. Any release-specific channel work (Claude Code marketplace metadata update for v1.5.9)
  7. Merge 1.5.9 → main
  8. Branch v1.5.10 off main

---

## Sequencing summary

```
Phase 0 (branch hygiene) ────────┐
                                 ↓
Phase 1 (harness-as-skill) ──────┐
                                 ├── Phase 3 (release ship) ─→ v1.5.9 tag
Phase 2 (SKILL.md trim) ─────────┘
```

Phase 1 and Phase 2 are parallelizable. Phase 3 waits for both. Within Phase 1 the order is **1A spike → 1B.0 (phase-identity source of truth) → rest of 1B** — see `QPB_v1.5.9_Harness_Skill_Implementation_Plan.md`.

---

## Council coordination notes

- Per-workstream Council reviews use Self-Council Protocol 1 (3 panelists each) — see `DEVELOPMENT_PROCESS.md` § Worker self-Council protocol.
- The Phase 1 Council can run AS the worker implementing the harness skill (the harness skill DESIGNED to validate itself this way per the sub-design). Phase 1B.0 additionally gets its own Self-Council because it refactors shipped instrumentation (see the harness sub-plan).
- The Phase 2 Council has new responsibility: **defensive-sweep charter** per the methodology section added during 207. Any panelist verifying content moves should ALSO grep the trimmed SKILL.md for the same defect class elsewhere. Example: if QPB pipeline Phase 1 (Explore) detail moves to `phase1_detail.md`, defensive sweep asks "is any other QPB Phase 1 (Explore) content still inlined in SKILL.md?" (Note: "Phase 1" here means the QPB audit pipeline's Explore phase — NOT v1.5.9 Phase 1, the harness workstream.)

---

## Open work-items tracker (umbrella — SKILL.md trim + release)

*Harness-workstream items live in `QPB_v1.5.9_Harness_Skill_Implementation_Plan.md`'s tracker. Item numbers below are **plan-local** (the harness plan numbers its own 1–11 separately) — always name the plan when cross-referencing a work item.*

| # | Item | Phase | Status |
|---|------|-------|--------|
| 1 | SKILL.md content audit | 2A | PENDING — Phase 2 workstream is independent and can run in parallel with the harness workstream |
| 2 | Mechanical content extraction | 2B | PENDING audit |
| 3 | SKILL.md restructure + reference directives | 2C | PENDING extraction |
| 4 | Reference-resolves validator | 2D | PENDING |
| 5 | Token-ceiling ratchet (32K → ~12K) | 2D | PENDING |
| 6 | Benchmark regression run | 2E | PENDING Phase 2 implementation |
| 7 | awesome-copilot re-submission with full canonical SKILL.md | 2 Ship Gate | PENDING Phase 2 |
| 8 | Release ship steps 1-8 | 3 | PENDING harness Ship Gate + Phase 2 Ship Gate |

---

*End of v1.5.9 umbrella Implementation Plan. Harness implementation detail in `QPB_v1.5.9_Harness_Skill_Implementation_Plan.md`. Design in `QPB_v1.5.9_Design.md`. Harness sub-design in `QPB_v1.5.9_Harness_Skill_Design.md`. v1.5.10 scope in `QPB_v1.5.10_Design.md` + `QPB_v1.5.10_Implementation_Plan.md`.*
