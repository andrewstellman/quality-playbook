# Quality Playbook v1.5.9 — Implementation Plan (umbrella)

*Companion to: `QPB_v1.5.9_Design.md`. This is the v1.5.9 **umbrella** plan — it owns Phase 0 (branch hygiene), the **standalone-distribution** workstream (Phase 2, replacing the SKILL.md trim which moved to `QPB_v1.5.10_Implementation_Plan.md` on 2026-06-11), the release ship sequence (Phase 3), and the overall sequencing. The **harness-as-skill** workstream (Phase 1) has its own plan: `QPB_v1.5.9_Harness_Skill_Implementation_Plan.md` (companion to `QPB_v1.5.9_Harness_Skill_Design.md`), authoritative for all Phase 1 detail — Phase 1 is COMPLETE as of 2026-06-11 (1A PASS, 1B.0 + 1B SHIP, item-11 E2E PASS).*

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

## Phase 2 — Standalone distribution

*The SKILL.md trim that previously occupied this phase moved intact to `QPB_v1.5.10_Implementation_Plan.md` (2026-06-11). Canonical design for this phase: `QPB_v1.5.9_Design.md` Part 2, including the THREE OPEN DECISIONS (name, repo model, first-release sequencing) that must settle with the operator BEFORE distribution instructions are filed.*

### Phase 2A — Decisions ~~(operator discussion in progress)~~ RESOLVED 2026-06-11 (name deferred with deadline)

- **Name: deferred until any time before the standalone's first publish** (registry-verify on choice; cascades into repo/packages/plugin/skill/CLI/article). Development proceeds name-free in the QPB vendored copy.
- **Repo model: resolved** — new repo at naming time, canonical upstream; QPB keeps the vendored copy under `plugins/` with a lineage note + drift test.
- **Sequencing: resolved** — QPB v1.5.9 tag waits for the standalone's first live publish; one close-out burst.
- **Capability ladder: resolved** — canonical text in `QPB_v1.5.9_Design.md` Part 2 (two axes: cadence 1-4, dispatch 1-2; cadence 2-4 imply shell dispatch; manual floor always prints the exact recovery command; the no-admin Windows worst case = cadence 3 + dispatch 2 and MUST work in the first release).

### Phase 2B — Generic-core development (in the QPB vendored copy; name-free; can start immediately)

- Genericized heartbeat helper for the standalone surface (`phase` as free string — no `phase_identity` / run-state coupling; QPB's `qpb_heartbeat.py` keeps its integration)
- Python demo stub replacing the bash stub in the example plan (cross-platform demo; bash is dead on locked-down Windows)
- `harness_ticker.py` — cadence rungs 3-4: foreground loop (tick → spawn → sleep) + `--once` manual mode; platform-appropriate detach flags; stdlib-only; "window stays open" documented
- Shell-dispatch mode — `dispatch_mode: "shell"` in the plan schema (schema_version bump), `worker_cmd` templates (invocation shapes from `runners.py` prior art), worker prompts as files (quoting/arg-length safety), PID + start-time lock files in `claimed/` (Council A-5), per-host auth pre-flight feeding `AUTH_OR_LAUNCH_FAILED`
- Capability-ladder prose in SKILL.md + BOOTSTRAP: probe own tooling, announce selected rung, degrade with printed exact commands (the generalized restart spell)
- Edge-case hardening: E1 per-run-dir tick lockfile (`fcntl`/`msvcrt`), E2 wall-clock-jump guard in stall logic, E4 synced-folder (OneDrive) pre-flight warning, E6 heartbeat-write-failure worker prose
- Cross-platform hygiene: ASCII tables + encoding disciplines already sweep-tested (007/008); extend to the new files as they land

### Phase 2B′ — Extraction (gated ONLY on the name decision)

- Scaffold the new repo from the vendored copy: README with the ladder decision tree + host-support table, thesis-forward, Apache-2.0; tests carried over
- Lineage notes both sides; drift test against the pinned upstream release
- Development in the new repo can use the orchestrator/worker runner pattern (the generalized `WATCHER_PROMPT.md` was built for this)

### Phase 2C — Packaging + publish gates

- pip + npm packages with publish scripts modeled on QPB's (`publish_pip.py` / `publish_npm.py` patterns)
- Mandatory per `DEVELOPMENT_PROCESS.md` § Distribution-channel publish safety: clean-clone cold-build test, built-artifact end-to-end test (install the wheel/tarball into a throwaway env and run the real demo), dry-run before any live publish

### Phase 2D — Marketplace submissions

- Submit the standalone harness plugin AND the Quality Playbook plugin to `anthropics/claude-plugins-official` via the plugin directory submission form (automated screening; optional "Anthropic Verified" review)
- Submissions are non-blocking for the tag unless decision 2A-3 says otherwise

### Phase 2E — Old harness deletion

- `rm -r bin/harness/` + its tests — the deletion gate (item-11 E2E PASS) is satisfied; the deletion plan was pre-announced in commit `5dbd1bf`

### Phase 2 Ship Gate

- Council review on the extracted standalone artifact before first live publish (Self-Council Protocol 1; charters: extraction completeness/genericization correctness, packaging/publish-gate integrity, README+demo fidelity)
- Both publish dry-runs clean; built-artifact end-to-end test passes
- Marketplace submissions filed (acceptance not required to tag unless 2A-3 decides otherwise)

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
  3. Live publishes — QPB pip + npm, PLUS the standalone harness package's first pip + npm publishes (its own repo/version; sequencing per decision 2A-3). No awesome-copilot this release (that rides the v1.5.10 trim).
  4. README + TOOLKIT install instruction updates (the harness invocation flow IS new — operators paste the bootstrap prompt instead of running the old Python harness; cross-link the standalone repo)
  5. DEVELOPMENT_CONTEXT refresh
  6. Release-specific channel work: Claude marketplace submissions for both plugins (Phase 2D) verified filed; self-hosted marketplace.json updated for v1.5.9
  7. Merge 1.5.9 → main
  8. Branch v1.5.10 off main

---

## Sequencing summary

```
Phase 0 (branch hygiene) ─→ Phase 1 (harness-as-skill — COMPLETE)
                                 ↓
                            Phase 2 (standalone distribution)
                                 ↓
                            Phase 3 (release ship) ─→ v1.5.9 tag
```

Phase 1 is complete (2026-06-11). Phase 2 is gated on the 2A operator decisions; Phase 3 waits for the Phase 2 ship gate. Within Phase 1 the order was **1A spike → 1B.0 (phase-identity source of truth) → rest of 1B** — see `QPB_v1.5.9_Harness_Skill_Implementation_Plan.md`.

---

## Council coordination notes

- Per-workstream Council reviews use Self-Council Protocol 1 (3 panelists each) — see `DEVELOPMENT_PROCESS.md` § Worker self-Council protocol.
- Phase 1's Councils are done: 1B.0 (phase-identity) and 1B (production hardening), both unanimous SHIP, artifacts under `runner/1.5.9/reviews/`.
- The Phase 2 Council reviews the extracted standalone artifact before first live publish (charters in the Phase 2 Ship Gate above). The defensive-sweep charter applies to the extraction: "is any QPB-specific coupling still present in the standalone copy?" and inversely "did the genericization accidentally change behavior the QPB-vendored copy relies on?"

---

## Open work-items tracker (umbrella — standalone distribution + release)

*Harness-workstream items live in `QPB_v1.5.9_Harness_Skill_Implementation_Plan.md`'s tracker (all 11 DONE). Item numbers below are **plan-local** — always name the plan when cross-referencing a work item. SKILL.md-trim items moved to `QPB_v1.5.10_Implementation_Plan.md`'s tracker.*

| # | Item | Phase | Status |
|---|------|-------|--------|
| 1 | Name decision + npm/PyPI/GitHub verification (cascades: repo/packages/plugin/skill/CLI/article) | 2A | **RESOLVED 2026-06-12: `wakecycle`** (selection record in Design Part 2). Final registry verification + the `{{NAME}}` cascade = instruction 013; extraction (item 9) unblocks on its PASS. |
| 2 | Repo-model + sequencing decisions | 2A | **RESOLVED 2026-06-11** — new repo at naming time, QPB vendors with lineage note + drift test; QPB tag waits for standalone first publish. Capability ladder canonicalized in Design Part 2. |
| 3 | Genericized heartbeat helper (free-string phase, no run-state coupling) | 2B | PENDING — unblocked, name-free |
| 4 | Python demo stub replacing the bash stub in the example plan | 2B | PENDING — unblocked |
| 5 | `harness_ticker.py` (cadence rungs 3-4: foreground loop + `--once` manual; detach flags; stdlib) | 2B | PENDING — unblocked |
| 6 | Shell-dispatch mode (schema `"shell"` + version bump; `worker_cmd` templates; prompt-files; A-5 PID locks; auth pre-flight) | 2B | PENDING — unblocked; REQUIRED for cadence rungs 2-4 incl. the no-admin floor |
| 7 | Capability-ladder prose in SKILL + BOOTSTRAP (probe / announce / degrade-with-printed-command) | 2B | PENDING — unblocked |
| 8 | Edge-case hardening E1 (tick lockfile), E2 (clock-jump guard), E4 (synced-folder warning), E6 (heartbeat-write-failure prose) | 2B | PENDING — unblocked |
| 9 | Extraction to the new repo (scaffold + README ladder/host table + lineage notes + drift test) | 2B′ | PENDING item 1 (name) ONLY |
| 10 | pip + npm packaging with publish gates (clean-clone cold-build + built-artifact E2E + dry-run) | 2C | PENDING 2B′ |
| 11 | Validation matrix: cadence-3 ticker (macOS + no-admin Windows-like), cadence-2 cron (≥1 host), manual floor, Copilot `/every` cadence-1 experiment, E7 compaction probe | 2B/2C | PENDING items 5-6; cadence-1 DONE (Sonnet ×3, Haiku ×1, Haiku re-test in flight) |
| 12 | Claude marketplace submissions (harness plugin + QPB plugin) | 2D | PENDING 2C |
| 13 | ~~Delete `bin/harness/`~~ | 2E | **DONE (`5b5eee3`)** |
| 14 | Release ship steps 1-8 (standalone first publish → QPB tag, one burst per 2A sequencing) | 3 | PENDING Phase 2 Ship Gate |

**Deferred out of v1.5.9 (recorded in Design Part 2):** first real-QPB-under-harness run + live-pipeline facade wiring (both → v1.5.10, riding the trim's benchmark run), full Codex/Cursor per-host matrices (standalone v0.2), A2A transport.

---

*End of v1.5.9 umbrella Implementation Plan. Harness implementation detail in `QPB_v1.5.9_Harness_Skill_Implementation_Plan.md`. Design in `QPB_v1.5.9_Design.md`. Harness sub-design in `QPB_v1.5.9_Harness_Skill_Design.md`. SKILL.md trim in `QPB_v1.5.10_Design.md` + `QPB_v1.5.10_Implementation_Plan.md`. Deferred broader scope in `QPB_v1.5.11_Design.md` + `QPB_v1.5.11_Implementation_Plan.md`.*
