# Quality Playbook v1.5.9 — Implementation Plan

*Companion to: `QPB_v1.5.9_Design.md`*

*Status: drafted 2026-06-06, revised 2026-06-07 to match scoped-down design (two focus items: harness-as-skill + SKILL.md trim). **Revised 2026-06-09 to replace MCP-based scheduler with sidecar daemon** per operator direction (see `QPB_v1.5.9_Harness_Skill_Design.md` for the empirical rationale). Phase 1 sub-phases 1A-1C landed under instruction 210 with the MCP-based scheduler; this revision adds Phase 1E covering the daemon swap + adversarial coverage + B-1 roundtrip + Phase 1D end-to-end revalidation. Prior broader-scope phases moved to `QPB_v1.5.10_Implementation_Plan.md`.*

*Authored under explicit operator carve-out from the default "QPB source files are propose-don't-edit" rule.*

---

## Operating Principles

- **Two independent workstreams** in v1.5.9. They can be implemented in parallel by different worker instructions, or serially in either order. They share no files.
- **Per-workstream Council review.** Each workstream gets its own Self-Council Protocol 1 review at completion. v1.5.9 doesn't ship until both reviews return SHIP.
- **Worker-lane edits** for all source changes (`SKILL.md`, `bin/`, `references/`, `.github/skills/`, schemas, tests). Cowork files instructions; worker implements; Council reviews.
- **No new orientation-doc edits** as part of v1.5.9 implementation. The methodology absorptions (defensive sweep, release close-out sequence) already landed during v1.5.8 close-out. v1.5.10 may surface more.

---

## Phase 0 — v1.5.8 Stabilization Confirmation

Before any v1.5.9 work begins, confirm v1.5.8 has fully shipped:

- `v1.5.8` tag on origin, pointing at the post-close-out HEAD (currently `794ba1e` — may move to include 203/204/205/206/207 fixes per operator decision)
- `1.5.8` branch merged to `main`, pushed to origin
- pip + npm channels published (live on PyPI + npmjs) — already confirmed
- awesome-copilot PR opened OR explicitly deferred to v1.5.9 (the v1.5.9 SKILL.md trim affects this — see Phase 2)
- Claude Code plugin marketplace functional (`.claude-plugin/marketplace.json` on `main`)

If any of these are incomplete, finish them before starting v1.5.9 implementation.

**Worker instruction at start of v1.5.9:** `cd ~/Documents/QPB && git checkout main && git pull && git checkout -b 1.5.9 && git push -u origin 1.5.9`. Verify the new branch is on origin before any commits.

---

## Phase 1 — Harness-as-skill

**Per `QPB_v1.5.9_Harness_Skill_Design.md` § MVP scope.** This phase has its own internal sub-phasing, captured in the sub-design. Summary:

### Phase 1A — Scaffolding

- Create `skills/quality-playbook-harness/` directory with `SKILL.md`, `schemas/`, `references/` substructure
- Create `bin/qpb_heartbeat.py` helper (the canonical emit mechanism for the heartbeat contract)
- Define the 3-4 schemas (plan, job_manifest, heartbeat, result) per the sub-design
- Add `references/STATE_MACHINE.md` enumerating state transitions

### Phase 1B — QPB skill modifications

- Add "Heartbeat emission" section to `skills/quality-playbook/SKILL.md` (the worker side of the contract)
- Wire the heartbeat schema into `quality-playbook/schemas/heartbeat.schema.json` (single source of truth shared with harness skill)
- Update phase prompts to include heartbeat emission at phase boundaries
- This work is COORDINATED with Phase 2 (SKILL.md trim) — both edit `skills/quality-playbook/SKILL.md`. Sequencing: either land Phase 2 trim FIRST then add heartbeat to the trimmed version, or land Phase 1B's heartbeat first then trim around it. Operator picks sequence; worker proceeds in declared order.

### Phase 1C — Validator + invariant tests

- `quality_gate.py` invariants for the 4 new schemas
- Test for cross-skill schema consistency (the heartbeat schema in `quality-playbook-harness/schemas/` byte-matches the one in `quality-playbook/schemas/`)
- Test for the tick idempotency contract: running the same tick twice produces no observable change after the first

### Phase 1D — End-to-end validation (partial — operator-manual mode)

LANDED via instruction 211-followup-1 (commit `024e642`). Captures all F4-F14 evidence including the fresh-context restart that proves the disk-state-as-truth recovery premise. The MCP path was NOT validated because the build agent's session lacked `mcp__scheduled-tasks` — a structural gap confirmed across three independent build-agent sessions. This validation evidence carries forward as the operator-manual coverage; the daemon-based end-to-end validation lands as part of Phase 1E.

### Phase 1E — Daemon swap + B-1 + adversarial coverage + revalidation (REPLACES the MCP path validation that Phase 1D originally bundled)

Replaces the MCP-based scheduler with a self-spawned sidecar daemon and fills the remaining Phase 1 coverage gaps:

- Add `bin/qpb_tick_daemon.py` — cross-platform detached Python process, PID-file lock via `O_EXCL`, mtime-updated heartbeat file, `done.marker` polling for clean exit. Stdlib only. ~100-150 lines.
- Add `bin/qpb_harness.py` — operator-facing CLI: `status` (list active daemons), `stop <run-dir>` (signal-then-kill), `gc` (sweep stale PID files).
- Edit harness SKILL.md: replace § First-tick setup MCP-scheduled-task creation with daemon spawn; replace § Self-disable scheduled-task delete with `done.marker` write; **remove** the § Fallback: no-MCP operator-manual mode section added by 211-followup-1 (single mechanism now — no fallback needed); remove `mcp__scheduled-tasks` from frontmatter dependencies; remove the `update_scheduled_task` gap note.
- Edit STATE_MACHINE.md: remove MCP-specific transitions; add daemon crash → re-spawn invariant if it doesn't fall out of the existing state machine.
- Edit DISPATCH_GUIDE.md to reflect daemon-based first-tick.
- **G4 — B-1 cross-CLI `--print "echo ok"` roundtrip** (carried forward from 212): the full roundtrip auth check that 211-followup-1 only completed in `--version` form.
- **G5 — Transition #4 (AUTH_OR_LAUNCH_FAILED) adversarial trigger**: dispatch Mode 2 worker with broken `cli_command`, verify next tick marks job `failed`/`failure_subtype=AUTH_OR_LAUNCH_FAILED`.
- **G6 — Transition #2 (FAILED terminal) adversarial trigger**: dispatch worker that emits `terminal --status FAILED`, verify state machine handles it.
- **G7 — (stretch) Transition #3 (stall detection) adversarial trigger**: plan with `stall_threshold_minutes=1`, worker emits STARTING then nothing, verify `stalled` marking.
- End-to-end revalidation in daemon mode against a small benchmark plan (≥1 subagent + ≥1 cross-CLI). Capture daemon spawn evidence, automated tick firing, daemon self-exit on `done.marker`.
- Updated `quality_gate.py` invariants for the PID-file format and daemon-related state.
- Two new tests: `bin/tests/test_daemon_lifecycle.py` (spawn → heartbeat → done-marker exit → PID cleanup) + `bin/tests/test_daemon_crash_recovery.py` (kill daemon mid-run, verify next harness invocation re-spawns).

### Phase 1 Ship Gate

- Council Self-Review Protocol 1 with three panelists per the harness sub-design's panelist enumeration (architectural correctness, operational viability, prose reliability)
- All Open Questions from the sub-design either resolved or explicitly MVP-deferred with documented rationale
- End-to-end validation (operator-manual coverage from 211-followup-1 + daemon coverage from Phase 1E) captured in the worker's review-request file
- `bin/harness/` Python code marked for deletion (commit message notes the deletion plan; actual `rm` happens after a buffer period to allow rollback)

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
Phase 0 (v1.5.8 stabilization) ──┐
                                 ↓
Phase 1 (harness-as-skill) ──────┐
                                 ├── Phase 3 (release ship) ─→ v1.5.9 tag
Phase 2 (SKILL.md trim) ─────────┘
```

Phase 1 and Phase 2 are parallelizable. Phase 3 waits for both.

---

## Council coordination notes

- Per-workstream Council reviews use Self-Council Protocol 1 (3 panelists each) — see `DEVELOPMENT_PROCESS.md` § Worker self-Council protocol.
- The Phase 1 Council can run AS the worker implementing the harness skill (the harness skill DESIGNED to validate itself this way per the sub-design).
- The Phase 2 Council has new responsibility: **defensive-sweep charter** per the methodology section added during 207. Any panelist verifying content moves should ALSO grep the trimmed SKILL.md for the same defect class elsewhere. Example: if Phase 1 detail moves to `phase1_detail.md`, defensive sweep asks "is any other Phase 1 content still inlined in SKILL.md?"

---

## Open work-items tracker

| # | Item | Phase | Status |
|---|------|-------|--------|
| 1 | Harness skill scaffold + schemas | 1A | LANDED (instruction 210, commit `a19fc9a`) |
| 2 | `bin/qpb_heartbeat.py` helper | 1A | LANDED (210) |
| 3 | QPB SKILL.md heartbeat emission section | 1B | LANDED (210) |
| 4 | `quality_gate.py` schema invariants | 1C | LANDED (210) |
| 5 | End-to-end harness validation — operator-manual coverage | 1D | LANDED (instruction 211-followup-1, commit `024e642`) |
| 5b | `bin/qpb_tick_daemon.py` sidecar daemon | 1E | PENDING (instruction 213) |
| 5c | `bin/qpb_harness.py` operator CLI (status/stop/gc) | 1E | PENDING (213) |
| 5d | Harness SKILL.md daemon swap + remove no-MCP fallback prose | 1E | PENDING (213) |
| 5e | B-1 `--print "echo ok"` roundtrip | 1E | PENDING (213) |
| 5f | Adversarial transitions #2(FAILED), #3(stall), #4(AUTH_OR_LAUNCH_FAILED) | 1E | PENDING (213) |
| 5g | End-to-end validation in daemon mode | 1E | PENDING (213) |
| 5h | Daemon lifecycle + crash recovery tests | 1E | PENDING (213) |
| 6 | SKILL.md content audit | 2A | Pending — first concrete step of Phase 2 |
| 7 | Mechanical content extraction | 2B | Pending audit |
| 8 | SKILL.md restructure + reference directives | 2C | Pending extraction |
| 9 | Reference-resolves validator | 2D | Pending |
| 10 | Token-ceiling ratchet (32K → ~12K) | 2D | Pending |
| 11 | Benchmark regression run | 2E | Pending Phase 2 implementation |
| 12 | awesome-copilot re-submission with full canonical SKILL.md | 2 Ship Gate | Pending Phase 2 |
| 13 | Release ship steps 1-8 | 3 | Pending Phase 1E + Phase 2 ship gates |

---

*End of v1.5.9 Implementation Plan. Design in `QPB_v1.5.9_Design.md`. Harness sub-design in `QPB_v1.5.9_Harness_Skill_Design.md`. v1.5.10 scope in `QPB_v1.5.10_Design.md` + `QPB_v1.5.10_Implementation_Plan.md`.*
