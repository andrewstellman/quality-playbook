# Quality Playbook v1.5.9 — Harness Skill Design

*Status: drafted 2026-06-06 (Cowork session). Revised 2026-06-06 post-Council review to adopt tick-based execution per operator direction. **Revised 2026-06-09 to replace the external scheduler entirely with in-session `ScheduleWakeup` polling** — the same mechanism the v1.5.7 watcher (`ai_context/WATCHER_PROMPT.md`) has used reliably for weeks. Prior drafts proposed an external scheduler (first Cowork's `mcp__scheduled-tasks` MCP, then a self-spawned Python sidecar daemon); both were superseded after empirical evidence — (a) the MCP is unavailable in build-agent sub-sessions and Cowork-locked anyway, (b) the daemon's fire mechanism (`claude --print`) hit the June 15 `claude -p` deprecation. The branch holding the daemon scaffolding is preserved as `archive/1.5.9-daemon-architecture`. Tick contract, state machine, idempotency invariants, heartbeat contract, and dispatch Mode 1 (Task subagent) are unchanged across both pivots; only the external-fire mechanism is replaced — this time with in-session polling that needs no external mechanism at all.*

*Revised 2026-06-10 to add the phase-identity source-of-truth contract — a single shared definition behind the `::QPB::` sentinel, the heartbeat, and `run_state.jsonl`, so the heartbeat's reported phase always matches the sentinel by construction — and to sequence it as a dedicated foundational step (Phase 1B.0) that lands after the 1A spike and before the rest of the heartbeat work. See "Phase-identity source of truth" under Architecture below, and Phase 1B.0 in the companion `QPB_v1.5.9_Harness_Skill_Implementation_Plan.md`.*

*Authored under explicit operator carve-out from the default "QPB source files are propose-don't-edit" rule.*

*Supersedes: `QPB_v1.5.9_Agent_Harness_Design.md` (deleted — that draft framed the design as a process-pool with paste-buffer launches, which was the wrong abstraction).*

*Council review: `~/Documents/QPB/reviews/v1.5.9_harness_skill_council/panelist_review.md`. Findings folded in below.*

---

## What this design is

The QPB test harness becomes a **skill**, not a Python program. Two skills cooperate:

- `quality-playbook-harness` — new skill. Orchestration logic lives in its `SKILL.md` as prose instructions. Any orchestration-capable agent (Claude Code, Codex, Copilot, eventually Cursor/Windsurf) loads it and follows it.
- `quality-playbook` — existing skill, modified to add a deterministic heartbeat contract. Workers (loaded with the QPB skill) emit heartbeat events to a known file so the harness can track progress.

**Tick-based execution via in-session polling.** The harness skill runs inside ONE operator Claude Code session (the operator pastes a bootstrap prompt into a fresh Claude Code session; that session becomes the harness orchestrator for the plan's duration). Each tick of the state machine runs as a single agent turn inside that session: read state from disk, advance any transitions that are ready, dispatch any new Task subagents, print a status summary, and call `ScheduleWakeup(now + N minutes)` to schedule the next tick. The session goes idle between ticks; `ScheduleWakeup` brings the agent back at the configured cadence.

This pattern — state machine on disk + idempotent stepper + `ScheduleWakeup` — dissolves the long-running-session concerns (context drift, sleep timeouts, accumulating conversation history) the way the v1.5.7 watcher does: each tick's prose is short and deterministic (run a Python script, parse its JSON output, dispatch a small number of Task calls, print a table, schedule next wakeup), so per-tick context growth is bounded. Heavy lifting — state-machine logic, heartbeat parsing, dispatch decisions, status table formatting — happens in `bin/qpb_harness_tick.py`, a deterministic Python script the agent invokes each tick. The agent's per-tick role is small and fixed; the script is where the work lives.

**Why `ScheduleWakeup`, not an external scheduler.** Two earlier drafts proposed external mechanisms — Cowork's `mcp__scheduled-tasks` MCP, then a self-spawned Python sidecar daemon firing `claude --print` — and both failed against deployment constraints. The MCP is unavailable outside Cowork-equipped top-level sessions (empirically confirmed across three build-agent sessions); the daemon's fire mechanism (`claude --print`) hits the June 15 `claude -p` deprecation. `ScheduleWakeup` has none of these problems: it's the same primitive the v1.5.7 watcher has been running reliably for weeks, it lives inside the operator's existing Claude Code session, and it has no external dependency at all. The trade-off — the operator's Claude Code session must stay open for the plan's duration — is the same constraint the v1.5.7 watcher already operates under and has not caused operational pain.

**Dispatch is Task-tool-only for MVP.** The harness dispatches workers via Claude Code's `Task` tool — fresh-context subagents within the orchestrator's session, returning short summaries per Council finding A-3 so orchestrator context stays bounded. Cross-CLI dispatch (Mode 2 in earlier drafts) and operator-manual dispatch (Mode 3) are deferred to v1.6+; the question of how a non-Claude-Code worker emits a heartbeat that the orchestrator's tick can observe needs more design work than v1.5.9 should absorb.

Communication between the harness and workers is folder-based for v1.5.9. Schemas are designed so they can later be wrapped in A2A Task envelopes if cross-machine or cross-org dispatch becomes a goal, but A2A transport is not implemented now.

This design retires the existing Python harness (`bin/harness/launcher.py`, `sentinel_reader.py`, the TUI, `subprocess_runner.py`, the substrate-immutability rule) once the skill validates against real benchmark plans.

---

## Goals

1. **Skill, not subprocess pool.** The harness is a `SKILL.md` that the operator's Claude Code session reads and acts on.
2. **No external scheduler.** `ScheduleWakeup` inside the orchestrator session is the cadence primitive. Same mechanism the v1.5.7 watcher uses; no MCP, no daemon, no `claude --print`, no cron, no external process.
3. **Deterministic heartbeat.** The QPB worker skill emits a structured heartbeat to a known file at deterministic moments. The harness reads heartbeats each tick to track progress and detect stalls.
4. **Tick-based execution.** Each tick runs as one agent turn: invoke `bin/qpb_harness_tick.py`, parse JSON output, dispatch any new Task subagents listed in the script's output, print the script's status table, call `ScheduleWakeup` for the next tick. Idempotency is mandatory — running the same tick twice in a row must be safe. Most state-machine logic lives in the Python script; the agent's prose role is small and fixed.
5. **Folder-based comm with A2A-ready schemas.** Filesystem transport for v1.5.9; schemas shaped so A2A migration is a transport swap, not a redesign.
6. **MVP host: Claude Code only.** `ScheduleWakeup` is Claude Code's primitive. Other host CLIs (Codex, Copilot) become a v1.6+ question — adding them requires either an equivalent polling primitive in that CLI or a different architecture for that host.
7. **No version-staging.** This is the architecture for v1.5.9. Not staged across releases. Not built in parts. MVP scope captured below.

---

## Non-goals

- Backwards compatibility with the existing Python harness CLI surface.
- A2A transport implementation.
- Cross-machine dispatch.
- Cross-CLI dispatch (Mode 2 in earlier drafts) — workers spawned via `copilot --print`, `codex ...`, etc. Deferred to v1.6+.
- Operator-manual dispatch (Mode 3 in earlier drafts) — redundant once the orchestrator runs in the operator's session.
- Cross-host scheduler (Codex, Copilot, etc.) — `ScheduleWakeup` is Claude-Code-specific for v1.5.9.
- Web UI or TUI beyond what the host CLI's conversation provides.

---

## Architecture

### The two skills

```
skills/quality-playbook-harness/
├── SKILL.md                       ← orchestration prose: invoke tick script, dispatch, print, ScheduleWakeup
├── schemas/
│   ├── plan.schema.json           ← reuses v1.5.7 plan format (Mode 1 entries only for MVP)
│   ├── job_manifest.schema.json
│   └── result.schema.json
└── references/
    ├── STATE_MACHINE.md           ← state transitions the tick script advances
    └── examples/
        └── small_plan.json
```

QPB skill changes:

```
skills/quality-playbook/
├── SKILL.md                       ← gains a "Heartbeat emission" section
├── scripts/
│   ├── qpb_phase.py               ← REFACTORED: still emits the ::QPB:: kind:"phase" sentinel, but its number→name table is extracted to the shared phase-identity definition below (it imports, never copies)
│   └── <phase-identity module>    ← NEW shared definition: phase number↔canonical-name table + "current phase" helpers. Single source of truth imported by qpb_phase.py, qpb_heartbeat.py, and the run-state writers. (Exact filename decided at implementation — not a contract yet.)
└── schemas/
    └── heartbeat.schema.json      ← single source of truth (harness references it from here)
```

Repo-level additions:

```
bin/
├── qpb_harness_tick.py            ← deterministic state-machine script invoked once per tick
└── qpb_heartbeat.py               ← worker-side heartbeat emit helper. NET-NEW on the 1.5.9 branch — the v1.5.7-era / daemon-arc version is NOT carried forward (it does not exist on this branch; see the Harness Skill Implementation Plan scope note (F) — reference-only prior art, rebuilt in Phase 1B). Reads phase identity from the shared definition above, never a private copy.
```

The harness skill's SKILL.md prose is small — roughly: "On invocation, run `python3 bin/qpb_harness_tick.py <run-dir>`. Parse its stdout as JSON. For each entry in `dispatch_list`, invoke the `Task` tool with the prompt the script supplies. Print the `status_table` field verbatim. Call `ScheduleWakeup(now + <next_tick_minutes> minutes)`. Exit." The state-machine logic is in the Python script, not in prose.

### Heartbeat emission via helper script

Per Council finding A-1 (heartbeat append mechanism collision), the QPB skill emits heartbeats via a helper script:

```
bin/qpb_heartbeat.py emit --phase <name> --step <name> --status <enum> [--message <text>]
```

The script does the atomic append in Python (write-temp-then-rename for whole-file writes, true append-only via `O_APPEND` for NDJSON). The QPB skill's prose collapses to "call this script when crossing a phase boundary, every ~3 min mid-phase, on any error, and at terminal." This sidesteps per-host-shell variation in `>>` semantics and reconciles with the main v1.5.9 Design §0.3 sentinel mechanism — the helper is the single mechanism, callable from any host that has Python.

Heartbeat line schema (one JSON per line):

```json
{
  "ts": "ISO8601 timestamp",
  "task_id": "uuid",
  "schema_version": "1",
  "phase": "Phase N name",
  "step": "specific step within the phase",
  "status": "STARTING | IN_PROGRESS | COMPLETED | FAILED",
  "message": "optional human-readable detail"
}
```

`schema_version` per Council finding C-3 (silent drift risk). Harness warns on version mismatch.

Terminal sentinel (last line):

```json
{
  "ts": "ISO8601",
  "task_id": "uuid",
  "schema_version": "1",
  "status": "COMPLETED | FAILED | ABANDONED",
  "result_file": "path to quality/SUMMARY.md or equivalent",
  "summary": "one-line outcome"
}
```

### Phase-identity source of truth — sentinel ↔ heartbeat ↔ run_state

The harness acts on the worker's *current phase*: the tick script reads the heartbeat to decide running / stalled / completed, and a heartbeat that reports the wrong phase makes the state machine act on the wrong fact. The worker already exposes its phase three ways — the `::QPB:: kind:"phase"` stdout sentinel (`bin/qpb_phase.py`), the `phase_start` / `phase_end` events in `quality/.../run_state.jsonl` (`run_state_lib.append_event`), and now the new `heartbeat.ndjson` `phase` field. If those three derive the phase from independent copies of the number→name table, they drift, and the heartbeat's phase silently stops matching the sentinel. The contract below makes the match hold *by construction*. ("Single source of truth" here means one shared definition that everyone reads — NOT one function that does everything; the emitters stay separate code.)

1. **One shared phase-identity definition.** The number→canonical-name table (`0:validation`, `1:exploration`, `2:generation`, `3:code-review`, `4:spec-audit`, `5:reconciliation`, `6:verification`) and the "what phase is this run in" helpers are extracted out of `qpb_phase.py` into a single shared module under the QPB skill's `scripts/`. `qpb_phase.py`, `qpb_heartbeat.py`, and the run-state writers all *import* it; no copy of the table exists anywhere else.

2. **`run_state.jsonl` is the canonical run position; the sentinel and the heartbeat are projections of it.** Neither the `::QPB::` sentinel nor `heartbeat.ndjson` ever computes a phase independently. A thin phase-transition facade, on a phase boundary, (a) appends the run-state event, (b) emits the `::QPB:: kind:"phase"` sentinel, and (c) — only when `HEARTBEAT_PATH` is set (i.e. the worker is running under the harness) — appends a heartbeat line, all keyed off the shared identity from (1). Separate code behind one facade, so a boundary can't update one surface and forget another.

3. **The mandatory ~3-min keepalive reads its phase from `run_state.jsonl`.** The keepalive is a mid-phase liveness ping — no boundary, no sentinel — so it can't be a side effect of a transition. It reads the current phase from the canonical run-state position and reports *that*, so even the ping's phase derives from the same truth and cannot drift from the sentinel.

4. **The `::QPB:: kind:"gate"` sentinel shares the envelope formatter only, not the phase identity.** `quality_gate.py`'s gate-verdict sentinel is a *result*, not a pipeline position, and `bin/run_playbook.py` (Mode B, which survives the harness deletion) parses it for the verdict. Unify only the one-line `::QPB:: {v:1,…}` envelope-writer so there's a single writer of that line shape; leave the gate's payload (`kind:"gate"`, `gate_result`) as its own emission. Same envelope source of truth, different payload — a deliberately lighter touch than the phase side.

This contract is implemented in **Phase 1B.0** (see `QPB_v1.5.9_Harness_Skill_Implementation_Plan.md`), sequenced first within 1B — after the 1A spike proves the tick loop, before the real `qpb_heartbeat.py`, the worker SKILL.md heartbeat section, and the gate invariants build on it. It is **not** in the 1A spike: the spike's stub worker emits a hardcoded `"phase": "stub"` and never exercises real phase identity, so this refactor would add shipped-skill blast radius the spike can't validate. The lockstep touch-points (install closure + drift test + `run_playbook` gate parsing) are enumerated in the sub-plan's Phase 1B.0 step.

### Inter-skill communication contract

All comm in `harness_runs/<ts>/`:

```
harness_runs/<ts>/
├── plan.json                      ← snapshot of the plan being executed
├── harness_status.json            ← state machine truth (harness writes; anyone reads)
├── queue/                         ← jobs not yet claimed
│   └── job-NNNNN.json
├── claimed/                       ← jobs in flight
│   ├── job-NNNNN.json
│   └── job-NNNNN.lock             ← worker.lock (PID + start time + cwd) per Council A-5
├── results/                       ← terminal sentinels
│   └── result-NNNNN.json
└── run-NN/                        ← one per plan entry
    ├── manifest.json
    ├── heartbeat.ndjson           ← worker appends here via qpb_heartbeat.py
    └── quality/                   ← QPB skill's normal output
```

### Tick-based execution model

Each tick is one agent turn inside the orchestrator's Claude Code session. The agent's prose role per tick is small and fixed; the work lives in `bin/qpb_harness_tick.py`.

**Per-tick sequence (the agent's prose):**

1. Run `python3 bin/qpb_harness_tick.py <run-dir>`. Capture stdout.
2. Parse the stdout as JSON. The script returns `{dispatch_list, status_table, next_tick_minutes, done, stop}`.
3. If `stop` is true (operator wrote a STOP file at the run-dir root): print status_table, do NOT call ScheduleWakeup, exit.
4. If `done` is true (all entries in results/): print the script's final summary, print status_table, do NOT call ScheduleWakeup, exit.
5. For each entry in `dispatch_list`: invoke the `Task` tool with the prompt the script supplies.
6. Print `status_table` verbatim (it's already formatted as ASCII; the agent just relays it to the operator's view).
7. Call `ScheduleWakeup(now + next_tick_minutes)`. End the agent turn.

**The Python script's role (`bin/qpb_harness_tick.py`):**

1. Read `harness_status.json`. Read `plan.json`. Build the authoritative current-state view from disk.
2. For each in-flight run: read the last N lines of `heartbeat.ndjson`. Determine current state (running / stalled / completed / failed).
3. Apply state transitions:
   - For each pending job in queue + free pool slot: emit a dispatch entry (path, worker prompt, task_id) to `dispatch_list` — the agent invokes Task per entry.
   - For each in-flight run with a terminal sentinel: move job manifest to `results/`.
   - For each in-flight run with stale heartbeat past `stall_threshold`: mark `STALLED`.
   - If all entries are in `results/`: set `done = true`, write final summary.
   - If `<run-dir>/STOP` exists: set `stop = true`.
4. Write updated `harness_status.json`.
5. Format the status table (ASCII, similar shape to the old harness's `--status` output).
6. Pick the next-tick cadence (default `tick_interval_minutes`; shorter when active work is in flight, longer when idle).
7. Exit, printing JSON to stdout.

**Idempotency is mandatory.** Every transition in the script checks "is this already done?" before applying. If the job is already in `claimed/`, don't re-emit a dispatch entry. If the result file is already present, don't re-move. Running the same tick twice in a row produces no observable change after the first.

**Loop-continuation discipline (NON-NEGOTIABLE).** Per the watcher prompt's pattern: every tick MUST end with either `ScheduleWakeup` OR a clean exit (STOP / done). Any tick that finishes without one of these silently terminates the polling loop. The harness SKILL.md prose makes this load-bearing by literally including a checklist at the end: "Did I call ScheduleWakeup OR was this a clean exit? If neither, call ScheduleWakeup now." Same failure mode as the watcher, same defense.

**Setup model.** On first invocation against a new plan, the agent runs `qpb_harness_tick.py --init <plan-path>` instead of `<run-dir>`. The script creates `harness_runs/<ISO timestamp>/` populated with plan.json + queue/ entries + initial harness_status.json. The agent then proceeds to step 5 above (dispatch + status + ScheduleWakeup) using the newly-created run-dir.

**Operator override.** The operator can ask the agent to "run another tick" at any time; the agent runs the tick script and re-schedules. The tick script's idempotency makes this safe.

**Self-disable.** When the script sets `done = true`, the agent prints the final summary and exits without calling ScheduleWakeup. The polling loop terminates cleanly.

**STOP semantics.** If the operator writes a `STOP` file at the run-dir root, the next tick observes it via the script, prints the final state, and exits without calling ScheduleWakeup. Same convention as the v1.5.7 watcher's `STOP` file at the runner root.

### Dispatch — Mode 1 only for MVP

The harness dispatches workers via Claude Code's `Task` tool. Each dispatched subagent receives a worker prompt that includes:

```
HEARTBEAT_PATH=<absolute path to run-NN/heartbeat.ndjson>
TASK_ID=<uuid>
RUN_DIR=<absolute path to run-NN/>
TARGET_REPO=<absolute path>
```

…as the literal first paragraph the subagent reads. Per Council A-2, all paths absolute, never derived from cwd. The subagent loads the QPB skill, runs the playbook on the target repo, emits heartbeats via `bin/qpb_heartbeat.py`.

Per Council A-3: the subagent prompt mandates *"return ONLY a short summary on completion — phase, last status, mtime age. Do NOT echo heartbeat content."* This caps the orchestrator's context growth across many ticks. The pool size default is 3 in-process subagents (configurable per plan); empirical subscription concurrency caps may lower this.

**Mode 2 (cross-CLI shell-out) and Mode 3 (operator-manual) are deferred to v1.6+.** Both have unresolved questions: Mode 2 needs a way for non-Claude-Code workers to emit observable heartbeats AND deals with shell-spawned process lifecycle the orchestrator doesn't naturally manage; Mode 3 is mostly redundant in the in-session model since the orchestrator IS the operator's session. The v1.5.9 plan schema accepts only `dispatch_mode: "subagent"` entries; future v1.6+ schema versions add Mode 2 with a different dispatch surface.

### A2A-ready schema shape

Schemas include `task_id` (UUID), `schema_version` (string), and avoid filesystem-specific load-bearing content. A future v1.6.x can wrap them in A2A Task envelopes by swapping transport. The exact A2A field mapping is captured in `references/A2A_MAPPING.md` (to be written during implementation) — for v1.5.9 the relevant claim is "schemas don't lock us out," not "we ship an A2A endpoint."

---

## Worked example

Operator opens Claude Code in the QPB repo and pastes the harness bootstrap prompt against a plan covering 3 repos (3 subagent entries, all Mode 1). `tick_interval_minutes: 10`.

**First tick (operator just pasted the prompt):**

- Agent reads the harness SKILL.md, then runs `qpb_harness_tick.py --init <plan-path>`.
- Script creates `harness_runs/2026-06-09T14-00-00/`, populates queue/ with 3 jobs, writes initial harness_status.json (`{queued: 3, claimed: 0, completed: 0}`), sets `done = false`.
- Pool size 3, queue has 3, all dispatchable now. Script emits 3 dispatch entries; agent invokes 3 `Task` calls in one agent message.
- Agent prints the status table:
  ```
  Run-Dir: 2026-06-09T14-00-00 (cycle 1)
  ─────────────────────────────────────────────────
  RUN  REPO              MODE    STATE       PHASE   LAST-HB
  01   /tmp/repo-a       subgnt  claimed     -       -
  02   /tmp/repo-b       subgnt  claimed     -       -
  03   /tmp/repo-c       subgnt  claimed     -       -
  ─────────────────────────────────────────────────
  Queue: 0  Claimed: 3  Completed: 0  Stalled: 0
  Next tick in 10 min
  ```
- Agent calls `ScheduleWakeup(now + 10 minutes)`. Agent turn ends.

**Tick 2 (10 min later, ScheduleWakeup fires):**

- Agent runs `qpb_harness_tick.py <run-dir>`.
- Script reads harness_status.json (3 claimed). Reads each run's heartbeat tail:
  - run-01: phase 2 IN_PROGRESS, mtime 1 min ago — healthy
  - run-02: phase 3 IN_PROGRESS, mtime 30 sec ago — healthy
  - run-03: phase 5 COMPLETED terminal — move manifest to results/
- Script updates harness_status.json (`{queued: 0, claimed: 2, completed: 1}`).
- No new dispatches (queue empty). Status table reflects new state.
- Agent prints status table, calls ScheduleWakeup, turn ends.

**Ticks 3..N:** same shape. Each is one agent turn, bounded prose, ScheduleWakeup at the end.

**Final tick:** all 3 entries in results/. Script sets `done = true`. Agent prints final summary + status table, does NOT call ScheduleWakeup, exits. Polling loop terminates.

**Estimated wall time:** ~30 min agent compute across the tick turns + however long the workers take.

If the operator wants immediate advancement at any point, they invoke the skill manually — same code path, same idempotency.

---

## Comparison to the previous Python harness

| Concern | Previous Python harness | Harness skill |
|---|---|---|
| Implementation | ~10K lines Python | `qpb_harness_tick.py` (~300-400 lines stdlib) + harness SKILL.md (~80-150 lines prose) + 4 schemas + 1 worker-side helper |
| Substrate immutability rule | Required | Not needed |
| Windows compat | 10+ followup fixes | stdlib Python only; cross-platform on day 1 |
| `claude -p` / `claude --print` dependency | Yes; June 15 forcing function | None — agent runs inside the operator's existing session |
| Polling primitive | Python event loop | `ScheduleWakeup` inside the orchestrator's Claude Code session — same as the v1.5.7 watcher |
| External scheduler | N/A | None — `ScheduleWakeup` is in-session |
| Long-running concerns | Subprocess pool, signals, encoding | Bounded — agent prose per tick is small; deterministic Python does the work; subagent returns are short summaries |
| TUI | Custom Python | Host CLI's conversation; status table printed each tick |
| Cross-CLI dispatch | Separate codepaths | Deferred to v1.6+ (Mode 1 / Task only for MVP) |
| Cross-machine future | Doesn't exist | A2A-ready schemas; transport swap is the remaining work |

---

## MVP scope

Initial build covers:

1. **`bin/qpb_harness_tick.py`** — deterministic Python state-machine script. Reads disk state, applies transitions, emits JSON output `{dispatch_list, status_table, next_tick_minutes, done, stop}`. Stdlib-only. ~300-400 lines.
2. **`bin/qpb_heartbeat.py`** — worker-side heartbeat emit helper. Single source of truth for NDJSON append discipline (Council A-1). Stdlib-only.
3. **`plugins/quality-playbook-harness/.claude-plugin/plugin.json`** + **`plugins/quality-playbook-harness/skills/quality-playbook-harness/SKILL.md`** — second plugin in the existing self-hosted marketplace. SKILL.md prose is short (the agent's per-tick role: run script, dispatch, print, ScheduleWakeup). ~80-150 lines.
4. **`plugins/quality-playbook-harness/skills/quality-playbook-harness/schemas/`** — plan, job_manifest, heartbeat (worker-side copy), result schemas.
5. **`plugins/quality-playbook-harness/skills/quality-playbook-harness/references/STATE_MACHINE.md`** — state transitions enumerated.
6. **`plugins/quality-playbook-harness/skills/quality-playbook-harness/references/BOOTSTRAP_PROMPT.md`** — the prompt the operator pastes into a fresh Claude Code session to invoke the harness against a plan. Same shape as `ai_context/WATCHER_PROMPT.md`; specialized for harness orchestration.
7. **`plugins/quality-playbook/skills/quality-playbook/SKILL.md`** — Heartbeat emission section added (worker side of the contract).
8. **`plugins/quality-playbook/skills/quality-playbook/schemas/heartbeat.schema.json`** — referenced by both skills; byte-identical to the harness-side copy.
9. **`quality_gate.py`** invariants for the new schemas (carries forward Council A-1 / C-3 / A-2).
10. **`bin/tests/test_qpb_harness_tick.py`** — unit tests for the state-machine script's transitions, idempotency, and JSON output shape.
11. **End-to-end validation:** harness skill orchestrating a 2-3 repo plan with all Mode 1 subagent dispatches. Validates the loop closes end-to-end — `ScheduleWakeup` cadence, state advancement, subagent context bounded, terminal exit clean.

**Foundational — Phase 1B.0, sequenced first within 1B (see `QPB_v1.5.9_Harness_Skill_Implementation_Plan.md`).** The phase-identity source-of-truth refactor + unified emission described under Architecture → "Phase-identity source of truth": one shared number→name module (extracted from `qpb_phase.py`), `run_state.jsonl` as canonical position, the phase-transition facade, the keepalive-reads-run-state rule, and the `kind:"gate"` envelope-only unification. The `qpb_heartbeat.py` helper, the worker SKILL.md heartbeat section, and the `quality_gate.py` invariants above all build on it, so it lands before them. Its blast radius — `INSTALL_CLOSURE` in `bin/qpb_validate.py`, `_bundle_files()` in `install_skill.py`, `_FLAT_LAYOUT_BUNDLED_BIN_FILES` in `run_state_lib.py`, `test_install_manifest_no_drift.py`, `test_phase_sentinel_109.py`, and `run_playbook.py`'s `::QPB:: kind:"gate"` parsing — is enumerated in the sub-plan's Phase 1B.0 step.

Out of scope for MVP, to figure out by building or defer:

- Mode 2 (cross-CLI shell-out) and Mode 3 (operator-manual) — deferred to v1.6+ entirely; the schema's `dispatch_mode` enum is locked to `"subagent"` for MVP.
- Multi-host scheduler (Codex, Copilot, etc.) — Claude Code only for MVP.
- A2A field mapping document — schemas designed forward-compatible; explicit A2A reference doc deferred.
- Sophisticated stall-detection (per-phase thresholds) — global 45 min + mandatory 3-min keepalive is the v1.5.9 default.

Existing Python harness (`bin/harness/`, `subprocess_runner.py`) gets deleted in the same release once the skill validates.

---

## Open questions

**Dissolved by in-session `ScheduleWakeup` architecture:**

- ~~#1 polling primitive viability~~ — `ScheduleWakeup` inside the orchestrator's Claude Code session. Same primitive the watcher uses.
- ~~#2 cross-CLI heartbeat path~~ — N/A in MVP, only Mode 1 (Task) is supported.
- ~~#4 Sonnet drift over long polling loops~~ — N/A; deterministic Python script handles per-tick state, agent prose is small and fixed.
- ~~#6 resume semantics~~ — every tick re-reads disk state; if the operator's Claude Code session crashes mid-run, restarting the bootstrap prompt resumes from disk state.
- ~~CC-1 main Design §0 conflict~~ — superseded with the in-session architecture.

**Resolved per Council (carried forward from original v1.5.9 review):**

- #5 stall threshold: 45 min global + mandatory 3-min keepalive in QPB heartbeat discipline.
- A-1 heartbeat append collision: `bin/qpb_heartbeat.py` helper as single mechanism.
- A-3 context bloat: subagents return short summaries only (per dispatch prompt); orchestrator agent's prose is small per tick by design.
- B-4 stall threshold default: 45 min + mandatory keepalive.
- C-3 schema drift: single source of truth in `quality-playbook/schemas/` + `schema_version` field.

**No longer applicable (Mode 2/3 deferred):**

- A-2 cross-CLI path handwaving — Mode 2 deferred; will need re-examination when Mode 2 lands in v1.6+.
- A-5 shell-out resume — Mode 2 deferred; same.
- B-1 cross-CLI auth — Mode 2 deferred; same.

**MVP-deferred — figure out by building:**

- #3 subscription concurrency caps for in-process Task subagents — measure empirically during MVP validation.
- #8 A2A schema specifics — designed forward-compatible, explicit mapping doc deferred.
- #9 SKILL.md edit scope on QPB skill — define during implementation.
- #10 test strategy — MVP is manual end-to-end + the unit tests above; CI integration for the helper + schemas.

---

## Risks

| Risk | Mitigation |
|---|---|
| Orchestrator agent forgets to call `ScheduleWakeup` → polling loop terminates silently | Hard-coded check in the SKILL.md prose: every tick ends with "Did I call ScheduleWakeup OR was this a clean exit? If neither, call ScheduleWakeup now." Same defense the v1.5.7 watcher uses. Operator restart spell: re-paste the bootstrap prompt. **ROOT-CAUSED 2026-06-12 (instruction-011 transcript forensics on 4 observed drops, incl. a previously-unnoticed 9h15m gap — all in the v1.5.9 runner worker, Claude Code 2.1.174): the wakeup primitive is RELIABLE — `scheduled_task_fire` events present at every scheduled time, 4/4. The failure is "Class C": the wakeup-RESUMED turn intermittently serializes its first tool call into the TEXT channel as literal `<invoke name="Bash">…` XML (prefixed by a stray token); when `stop_reason` is `end_turn` the host injects no retry and the loop dies silently — when it's `tool_use`, the host injects a malformed-call retry and the loop self-heals (4/4 survived). E7/compaction REFUTED (the session's single compaction postdates the last recovery; 0/4 drops follow one). Mitigations: (1) the FR-26a safety tick — an external `--once` tick is independent of the in-session turn and rescues every Class-C death within one safety interval, no detection logic; (2) candidate in-band fix: a Stop-hook (or host fix) that treats "assistant text containing `<invoke name=` + `end_turn` + no tool_use" as malformed and injects the existing retry — would convert every observed death into the self-heal path; (3) upstream issue FILED 2026-06-12: anthropics/claude-code#67945. Full forensics: `runner/1.5.9/outputs/011-loop-drop-self-forensics.md`.** |
| Orchestrator session context grows over many ticks → eventual context limit | Deterministic Python does the state work; agent prose per tick is small and fixed (~10-20 lines). Status table is a small ASCII snippet, not full heartbeat content. Subagent returns are short summaries per Council A-3. Empirical: the watcher pattern has held for weeks of continuous operation. |
| Operator's Claude Code session crashes mid-run | State is on disk; restart the bootstrap prompt and resume. The script re-reads disk state each tick; mid-run resume just means the next tick picks up where the last one left off. |
| Heartbeat append race | `bin/qpb_heartbeat.py` uses `O_APPEND`; one writer per run-NN/ directory; isolation by construction. |
| Subscription concurrency caps bite at pool > N | Plan-tunable pool_size; document empirical limit when found. |
| Stall threshold misfires on legitimate long phases | Mandatory 3-min keepalive emission makes 45-min threshold safe; per-phase override deferred to v1.5.11 (renumbered from v1.5.10 on 2026-06-11). |
| Idempotency bug ships → duplicate dispatch | Schema invariants + explicit "is this already done?" check in `qpb_harness_tick.py` for every transition; unit tests specifically test double-tick safety. |
| Plan size exceeds what one Claude Code session can hold | The script bounds context growth; in principle the orchestrator can run for hours. Hard empirical limit is unknown; v1.5.9 MVP plans should be small (3-5 entries) until evidence accumulates. Larger plans become a v1.6+ question. |

---

*End of design. Council review folded in per `~/Documents/QPB/reviews/v1.5.9_harness_skill_council/panelist_review.md`. Implementation begins after v1.5.8 ships.*
