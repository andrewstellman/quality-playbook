# Quality Playbook v1.5.9 — Implementation Plan

*Companion to: `QPB_v1.5.9_Design.md`*

*Status: drafted 2026-06-06, revised 2026-06-07 to match scoped-down design (two focus items: harness-as-skill + SKILL.md trim). **Revised 2026-06-09 to replace the external-scheduler architecture with in-session `ScheduleWakeup` polling** per the second architectural pivot (see `QPB_v1.5.9_Harness_Skill_Design.md` for the empirical rationale). Phase 1 is replanned from scratch on a fresh `1.5.9` branch from main; the prior daemon-architecture work (instructions 210, 211, 211-followup-1, 213) is preserved on `archive/1.5.9-daemon-architecture` and is NOT cherry-picked because the architectural mistakes were embedded throughout that scaffolding. Some artifacts are portable in spirit (the heartbeat schema, the worker-side qpb_heartbeat.py helper, the worker SKILL.md heartbeat section) but will be rebuilt in this branch under the new architecture rather than carried forward. Prior broader-scope phases moved to `QPB_v1.5.10_Implementation_Plan.md`.*

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

**Per `QPB_v1.5.9_Harness_Skill_Design.md` § MVP scope.** This phase has TWO instructions: an instruction-1 spike that empirically validates the riskiest assumption (prose-driven tick loop survives across `ScheduleWakeup` cadence with deterministic Python doing the state work), and an instruction-2 hardening that lands the production-shaped artifacts only AFTER the spike's empirical result. If the spike fails, instruction 2 changes shape based on what failed.

### Phase 1A — Tracer-bullet spike (instruction 1)

**The riskiest assumption being empirically tested:** *the orchestrator agent reliably runs `qpb_harness_tick.py`, parses its JSON output, dispatches the listed Task calls, prints the listed status table, calls ScheduleWakeup, and yields the agent turn — without doing extra stuff and without dropping the polling loop across multiple ticks.*

**Minimum scope to test it (≤ 300 lines added across all files):**

- A ~150-line `bin/qpb_harness_tick.py` that handles the minimum state machine: queued → claimed → completed. No stall detection, no failure subtypes, no Mode 2 plumbing.
- A ~80-line harness SKILL.md whose entire prose body is: run the script, parse JSON, dispatch each entry in `dispatch_list`, print `status_table`, call `ScheduleWakeup(now + 5 minutes)`, end turn.
- A `harness_plans/spike_validation.json` — 1 entry, Mode 1, against a small test target.
- A `BOOTSTRAP_PROMPT.md` modeled on `ai_context/WATCHER_PROMPT.md` — the operator pastes it into a fresh Claude Code session to invoke the harness.

**Validation run:**

- Operator pastes the bootstrap into a fresh Claude Code session.
- Observe 3-4 ticks fire on `ScheduleWakeup` cadence. After each tick, capture `harness_status.json`, the heartbeat tail for the dispatched run, and the agent's stdout (status table + ScheduleWakeup call).
- The script's `done` flag flips when the worker emits a terminal sentinel; agent prints final summary, does NOT call ScheduleWakeup, exits cleanly.
- Operator writes a STOP file during tick 2 of a separate mini-run to verify clean stop semantics.
- Forced re-tick (operator says "run another tick now") shows empty diff in harness_status.json — idempotency check.

**Possible outcomes:**
- **Spike succeeds:** the architectural premise holds. Phase 1B (hardening) is straightforward thickening of the production-shaped surface.
- **Spike fails:** the failure mode tells us specifically what needs to change. Possible: agent doesn't reliably invoke ScheduleWakeup → SKILL.md prose needs sharper structure; agent does extra reasoning between script calls → script needs to be smaller and stricter; subagent return contract leaks heartbeat content into orchestrator context → A-3 enforcement needs to be tighter. The script-and-prose are small enough that pivoting is cheap.

**Spike NOT subject to worker self-Council.** The artifact is ≤300 lines; Council is theater at this scale. The empirical result (the run output) is the verdict.

### Phase 1B — Production hardening (instruction 2)

Conditional on Phase 1A producing a successful spike. Only files after the spike's evidence is captured. Contents depend on what 1A learned. Likely shape:

- Expand `qpb_harness_tick.py` to handle full state machine: stall detection, AUTH_OR_LAUNCH_FAILED (if Mode 1 dispatch fails), terminal FAILED status, idempotency invariants, error logging.
- Expand harness SKILL.md prose with the loop-continuation discipline checklist verbatim (mirroring the watcher prompt's "EVERY tick MUST end with ScheduleWakeup" section).
- Build out the second plugin properly (`plugins/quality-playbook-harness/.claude-plugin/plugin.json`, marketplace.json catalog entry, schemas, references including STATE_MACHINE.md).
- Add `bin/tests/test_qpb_harness_tick.py` — stdlib-only unit tests for state-machine transitions, idempotency, JSON output shape, double-tick safety.
- Add `quality_gate.py` invariants for the schemas (carry forward Council A-1, C-3, A-2 disciplines from the original v1.5.9 review).
- Re-validate end-to-end against a 2-3 entry plan; capture evidence.

### Phase 1B sub-Council

After Phase 1B lands its commit:

- Worker self-Council Protocol 1 with three panelists: (A) state-machine correctness + idempotency, (B) SKILL.md prose reliability + ScheduleWakeup discipline, (C) cross-skill schema consistency + validator coverage.
- All Open Questions from the harness sub-design either resolved or explicitly MVP-deferred with documented rationale.
- End-to-end validation evidence captured in the worker's review-request file.
- `bin/harness/` Python code marked for deletion (commit message notes the deletion plan; actual `rm` happens after a buffer period to allow rollback).

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
| 1 | Tracer-bullet spike: minimal `qpb_harness_tick.py` + minimal harness SKILL.md + bootstrap prompt + 1-entry plan + empirical 3-4-tick validation | 1A | PENDING — first instruction filed against this branch |
| 2 | Production-shaped `qpb_harness_tick.py` (full state machine, idempotency, error handling) | 1B | PENDING — gated on spike result |
| 3 | Production harness SKILL.md prose (loop-continuation discipline, full status table, dispatch contract) | 1B | PENDING |
| 4 | Second-plugin scaffolding (`plugins/quality-playbook-harness/.claude-plugin/plugin.json` + marketplace.json catalog entry + schemas + references) | 1B | PENDING |
| 5 | `bin/qpb_heartbeat.py` worker-side helper | 1B | PENDING — re-build (the archive branch's version was sound but built on different scaffolding) |
| 6 | QPB worker SKILL.md heartbeat emission section | 1B | PENDING — re-add (same artifact as archive but on new branch) |
| 7 | Heartbeat schema byte-identical copies on both sides | 1B | PENDING |
| 8 | `quality_gate.py` invariants for harness schemas | 1B | PENDING |
| 9 | `bin/tests/test_qpb_harness_tick.py` — unit tests for state machine + idempotency | 1B | PENDING |
| 10 | End-to-end validation run with operator-driven 2-3 entry plan | 1B Ship Gate | PENDING |
| 11 | SKILL.md content audit | 2A | PENDING — Phase 2 workstream is independent and can run in parallel with Phase 1 |
| 12 | Mechanical content extraction | 2B | PENDING audit |
| 13 | SKILL.md restructure + reference directives | 2C | PENDING extraction |
| 14 | Reference-resolves validator | 2D | PENDING |
| 15 | Token-ceiling ratchet (32K → ~12K) | 2D | PENDING |
| 16 | Benchmark regression run | 2E | PENDING Phase 2 implementation |
| 17 | awesome-copilot re-submission with full canonical SKILL.md | 2 Ship Gate | PENDING Phase 2 |
| 18 | Release ship steps 1-8 | 3 | PENDING Phase 1B + Phase 2 ship gates |

**Note on the daemon-architecture archive.** Instructions 210, 211, 211-followup-1, and 213 landed on `archive/1.5.9-daemon-architecture`. They contain working artifacts (worker-side heartbeat helper, schemas, worker SKILL.md heartbeat prose, validators) that are conceptually portable to the new architecture. They are NOT cherry-picked because the architectural mistakes (MCP scheduler, then daemon scheduler) were embedded throughout that scaffolding and the cleaner path is to rebuild on the new substrate. Some prose and code patterns will be re-used in spirit; nothing is moved in literal form.

---

*End of v1.5.9 Implementation Plan. Design in `QPB_v1.5.9_Design.md`. Harness sub-design in `QPB_v1.5.9_Harness_Skill_Design.md`. v1.5.10 scope in `QPB_v1.5.10_Design.md` + `QPB_v1.5.10_Implementation_Plan.md`.*
