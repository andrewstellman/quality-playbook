# Quality Playbook v1.5.9 — Harness Skill Design

*Status: drafted 2026-06-06 (Cowork session). Revised 2026-06-06 post-Council review to adopt tick-based execution per operator direction. **Revised 2026-06-09 to replace the scheduled-tasks MCP scheduler with a self-spawned sidecar daemon** per operator direction — eliminates the Cowork-MCP vendor coupling and the sub-session MCP-propagation failure mode empirically observed across three independent build-agent sessions (211 / 211-followup-1 / 212 HALTs). The tick contract, state machine, idempotency invariants, dispatch modes, schemas, and heartbeat contract are unchanged; only the external-scheduler implementation is swapped.*

*Authored under explicit operator carve-out from the default "QPB source files are propose-don't-edit" rule.*

*Supersedes: `QPB_v1.5.9_Agent_Harness_Design.md` (deleted — that draft framed the design as a process-pool with paste-buffer launches, which was the wrong abstraction).*

*Council review: `~/Documents/QPB/reviews/v1.5.9_harness_skill_council/panelist_review.md`. Findings folded in below.*

---

## What this design is

The QPB test harness becomes a **skill**, not a Python program. Two skills cooperate:

- `quality-playbook-harness` — new skill. Orchestration logic lives in its `SKILL.md` as prose instructions. Any orchestration-capable agent (Claude Code, Codex, Copilot, eventually Cursor/Windsurf) loads it and follows it.
- `quality-playbook` — existing skill, modified to add a deterministic heartbeat contract. Workers (loaded with the QPB skill) emit heartbeat events to a known file so the harness can track progress.

**Tick-based execution.** The harness skill does NOT run as a long-lived polling loop. Each invocation executes exactly ONE tick of the state machine: read state from disk, advance any transitions that are ready, write state back to disk, exit. A **sidecar daemon** — a tiny Python background process the harness skill spawns on first-tick — fires the skill at the desired cadence (e.g., every 10 min). The daemon holds zero AI context; it is a dumb wakeup timer that invokes `claude --print` (or the equivalent for the host CLI) each tick. This pattern is well-trodden — state machine on disk + idempotent stepper + external scheduler — and dissolves the long-running-session concerns (context drift, sleep timeouts, accumulating conversation history) by construction. The daemon's "long-running" property does NOT have those failure modes because the daemon is not an AI context, just a clock.

**Why a self-spawned daemon, not the Cowork scheduled-tasks MCP.** An earlier (2026-06-06) draft used Cowork's `mcp__scheduled-tasks` as the external scheduler. Empirical validation (instructions 211, 211-followup-1, 212) confirmed three failure modes: (1) vendor lock — adopters running QPB through Codex, Copilot CLI, Cursor, or the bare `claude` CLI without Cowork have no access to the MCP; (2) sub-session topology — even within Anthropic's stack, sub-sessions spawned via the Task tool do not inherit the MCP, breaking the cross-CLI dispatch model; (3) bus factor — coupling the harness's autonomy story to one specific MCP server. The sidecar daemon eliminates all three: it depends only on Python (which is already required by the worker skill), runs anywhere the worker runs, and works identically in any session topology.

The harness skill can dispatch workers via the host CLI's subagent mechanism (Task tool in Claude Code), via shell-out to a different CLI (`copilot --model X`, `codex ...`, `claude ...`), or via operator-driven manual launch in a separate window. These can mix freely in one plan execution.

Communication between the harness and workers is folder-based for v1.5.9. Schemas are designed so they can later be wrapped in A2A Task envelopes if cross-machine or cross-org dispatch becomes a goal, but A2A transport is not implemented now.

This design retires the existing Python harness (`bin/harness/launcher.py`, `sentinel_reader.py`, the TUI, `subprocess_runner.py`, the substrate-immutability rule) once the skill validates against real benchmark plans. The June 15 `claude -p` deprecation is irrelevant because the skill never calls `claude -p` — it shells out to interactive CLIs that have their own auth.

---

## Goals

1. **Skill, not subprocess pool.** The harness is a `SKILL.md` that any orchestration-capable agent reads and acts on.
2. **Cross-CLI orchestration.** Harness in Claude Code can dispatch workers in Codex, Copilot, or another Claude Code instance.
3. **Deterministic heartbeat.** The QPB skill emits a structured heartbeat to a known file at deterministic moments. The harness reads heartbeats to track progress and detect stalls.
4. **Tick-based execution with a self-spawned sidecar daemon.** Each invocation runs exactly one tick: read state, advance, write state, exit. The harness skill spawns a detached Python daemon on first-tick that fires `claude --print` (or equivalent) at the configured cadence. Idempotency is mandatory — running the same tick twice in a row must be safe. The daemon has zero AI context (it is a dumb wakeup clock) so it does not exhibit the failure modes of long-running in-context loops.
5. **Folder-based comm with A2A-ready schemas.** Filesystem transport for v1.5.9; schemas shaped so A2A migration is a transport swap, not a redesign.
6. **No version-staging.** This is the architecture for v1.5.9. Not staged across releases. Not built in parts. MVP scope captured below.

---

## Non-goals

- Backwards compatibility with the existing Python harness CLI surface.
- A2A transport implementation.
- Cross-machine dispatch.
- Web UI or TUI beyond what the host CLI's conversation provides.

---

## Architecture

### The two skills

```
skills/quality-playbook-harness/
├── SKILL.md                       ← orchestration logic as prose (state-machine stepper)
├── schemas/
│   ├── plan.schema.json           ← reuses v1.5.7 plan format
│   ├── job_manifest.schema.json
│   └── result.schema.json
└── references/
    ├── DISPATCH_GUIDE.md          ← how to dispatch via Task / Bash / operator
    ├── STATE_MACHINE.md           ← state transitions the tick advances
    └── examples/
        └── small_plan.json
```

QPB skill changes:

```
skills/quality-playbook/
├── SKILL.md                       ← gains a "Heartbeat emission" section
└── schemas/
    └── heartbeat.schema.json      ← single source of truth (harness references it from here)
```

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

Each harness skill invocation is one tick. The tick's job:

1. Read `harness_status.json`. Read `plan.json`. Build the authoritative current-state view from disk.
2. For each in-flight run: read the last N lines of `heartbeat.ndjson`. Determine current state (running / stalled / completed / failed).
3. Apply available state transitions:
   - For each pending job in queue and free pool slot: dispatch one
   - For each in-flight run with a terminal sentinel: move job manifest to results/
   - For each in-flight run with stale heartbeat past `stall_threshold`: mark STALLED
   - For each completed plan: write final summary, write `done.marker` (the daemon exits on its next wake), remove PID file
4. Write updated `harness_status.json`.
5. Exit.

**Idempotency is mandatory.** Every transition checks "is this already done?" before applying. If the job is already in claimed/, don't re-dispatch. If the result file is already present, don't re-move. Running the same tick twice in a row produces no observable change after the first.

**Setup model.** On first invocation against a new plan, the harness skill spawns a sidecar daemon (`python3 bin/qpb_tick_daemon.py <run-dir>` via `subprocess.Popen` with platform-correct detachment flags — `os.setsid()` on Unix, `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP` on Windows). The daemon writes a PID file at `<run-dir>/daemon.pid` for lifecycle management. Cadence comes from the plan's `tick_interval_minutes` field (default: 10). The daemon survives the operator's session ending because it is detached from the terminal session.

**The daemon's responsibility is exactly one thing**: every `tick_interval_minutes`, invoke `claude --print --plugin-dir <harness-skill-path> -p "tick harness on run-dir <run-dir>"` (or the equivalent for whichever host CLI is configured for the plan). The daemon does NOT make state-machine decisions, does NOT read heartbeats, does NOT touch the queue/claimed/results directories. The harness skill — invoked fresh each tick — does all of that. The daemon is a clock with `subprocess.run` attached.

**Daemon lifecycle:**

1. **Spawn.** First-tick setup creates `<run-dir>/daemon.pid` (lock file via `O_EXCL`) and launches the daemon process. If the lock file already exists and the PID is alive, the harness skill refuses to start a second daemon for the same run-dir.
2. **Heartbeat.** The daemon writes `<run-dir>/daemon.heartbeat` (mtime updated each tick) so the harness skill can detect a dead daemon on subsequent operator-manual invocations.
3. **Self-disable.** When the harness skill detects all plan entries are in `results/`, it writes `<run-dir>/done.marker`. The daemon checks for this marker before each sleep cycle; when present, the daemon exits cleanly and removes the PID file.
4. **Crash recovery.** If the daemon dies unexpectedly (machine reboot, `kill -9`, OOM), the next operator invocation of the harness skill detects a stale `daemon.pid` (PID not running OR heartbeat older than 3 × `tick_interval_minutes`) and re-spawns the daemon. The state machine is unaffected — the daemon is just a clock; only the cadence of clock ticks is lost during the outage.

**Operator override.** The operator can invoke the harness skill manually at any time to force an immediate tick. Useful when something just changed and they don't want to wait for the next daemon fire. Falls out for free because the tick is idempotent and the daemon's wake/sleep loop is independent of operator invocations.

**Self-disable.** When all plan entries are in `results/` (success or failure), the final tick writes `done.marker`, the daemon exits on its next wake check, the PID file is removed, and the harness writes the run's final summary.

### Dispatch modes

Three supported modes, declared per-entry in the plan:

**Mode 1: in-process Task subagent (Claude Code).**

The tick dispatches by invoking the Task tool with a worker prompt that includes:

```
HEARTBEAT_PATH=<absolute path to run-NN/heartbeat.ndjson>
TASK_ID=<uuid>
RUN_DIR=<absolute path to run-NN/>
TARGET_REPO=<path>
```

…as the literal first paragraph the subagent reads. Per Council A-2, all paths absolute, never derived from cwd. Subagent loads the QPB skill, runs the playbook, emits heartbeats via `qpb_heartbeat.py`.

Per Council A-3: subagent prompt mandates "return ONLY a short summary on completion — phase, last status, mtime age. Do NOT echo heartbeat content." Caps in-process pool at ≤3 to keep orchestrator's context bounded across many ticks.

**Mode 2: cross-CLI shell-out.**

The tick dispatches by running:

```
cd <run-dir> && <cli-command> -p "$(cat worker_prompt.md)" > worker.log 2>&1 &
```

…where `<cli-command>` is `copilot --model X --allow-all`, `codex --model Y`, or similar. The worker_prompt.md is generated by the harness from a template, includes the same absolute path block as Mode 1.

Per Council B-1, before dispatching to any CLI, the harness runs a pre-flight auth check (`<cli> --version` + a tiny `<cli> -p "echo ok"` round-trip). Failure marks the dispatch entry `AUTH_FAILED` and skips it. If the dispatched worker doesn't write a STARTUP heartbeat within 60 sec, the next tick marks it `AUTH_OR_LAUNCH_FAILED` — distinct from STALLED.

**Mode 3: operator-manual dispatch.**

The tick writes the worker prompt to `<run-dir>/operator_prompt.md` and writes an "ACTION REQUIRED" banner to `harness_status.json` with a unique tag (`MANUAL_DISPATCH_NNN`). Operator opens a new window, pastes the prompt, includes the tag in a `<run-dir>/operator_started` file to acknowledge. Subsequent ticks detect the acknowledgment and proceed normally.

Mode 3 is intended for "watch this one run interactively," not as a scaling primitive. Document discouraged for pool > 2.

### A2A-ready schema shape

Schemas include `task_id` (UUID), `schema_version` (string), and avoid filesystem-specific load-bearing content. A future v1.6.x can wrap them in A2A Task envelopes by swapping transport. The exact A2A field mapping is captured in `references/A2A_MAPPING.md` (to be written during implementation) — for v1.5.9 the relevant claim is "schemas don't lock us out," not "we ship an A2A endpoint."

---

## Cross-CLI scenario (worked example)

Operator opens Claude Code in the QPB repo, invokes the harness skill with a plan covering 5 repos. The plan has mixed dispatch (2 subagent, 2 copilot, 1 codex). `tick_interval_minutes: 10`.

**First invocation (tick 1):**

- Skill spawns sidecar daemon that re-invokes the harness skill via `claude --print` every 10 min; daemon writes PID file at `<run-dir>/daemon.pid`
- Reads plan, validates, creates `harness_runs/2026-06-06T14-00-00/`, populates queue/ with 5 jobs
- Pool size 3, queue has 5, dispatches first 3 (one Task call with two subagent prompts in one message + one Bash backgrounded copilot)
- Updates harness_status.json: 3 claimed, 2 queued, 0 results
- Exits

**Tick 2 (10 min later, fires from daemon):**

- Fresh agent invocation, fresh context
- Reads harness_status.json: 3 claimed, 2 queued
- Reads each in-flight run's heartbeat tail
- Subagent #1: phase 2, IN_PROGRESS, recent — healthy
- Subagent #2: phase 7, COMPLETED terminal — move to results/, free pool slot
- Copilot shell-out: phase 1, IN_PROGRESS, recent — healthy
- Dispatches next queue entry (the codex shell-out) into the freed slot
- Updates harness_status.json: 3 claimed, 1 queued, 1 result
- Exits

**Ticks 3..N:** same shape. Each is bounded, fresh-context, advances the state machine by whatever's ready.

**Final tick:** all 5 plan entries in results/. Writes summary. Writes `done.marker` (daemon exits on next wake). Removes PID file. Exits.

If the operator wants immediate advancement at any point, they invoke the skill manually — same code path, same idempotency.

---

## Comparison to the previous Python harness

| Concern | Previous Python harness | Harness skill |
|---|---|---|
| Implementation | ~10K lines Python | One `SKILL.md` + 3-4 schemas + 1 helper script |
| Substrate immutability rule | Required | Not needed |
| Windows compat | 10+ followup fixes | Bash + Python; cross-platform on day 1 |
| `claude -p` dependency | Yes; June 15 forcing function | No |
| Polling primitive | Python event loop | Self-spawned sidecar daemon (dumb wakeup clock) |
| Long-running concerns | Subprocess pool, signals, encoding | None — tick-based |
| TUI | Custom Python | Host CLI's conversation; status file viewable separately |
| Cross-CLI dispatch | Separate codepaths | Native via dispatch modes |
| Cross-machine future | Doesn't exist | A2A-ready schemas |

---

## MVP scope

Initial build covers:

1. `skills/quality-playbook-harness/SKILL.md` — single-tick prose, three dispatch modes documented inline, idempotency rules. **No MCP-based fire mechanism**: the harness skill spawns a sidecar daemon via `subprocess.Popen` on first-tick.
2. `skills/quality-playbook-harness/schemas/` — plan, job_manifest, result schemas
3. `skills/quality-playbook-harness/references/STATE_MACHINE.md` — state transitions enumerated
4. `bin/qpb_heartbeat.py` — emit helper, single source of truth for append discipline (worker side)
5. `bin/qpb_tick_daemon.py` — sidecar wakeup daemon, cross-platform detached spawn, PID-file lock, heartbeat mtime, `done.marker` polling for clean exit (~100-150 lines stdlib only)
6. `bin/qpb_harness.py` — small operator-facing CLI: `qpb harness status` (list active daemons), `qpb harness stop <run-dir>` (signal-then-kill), `qpb harness gc` (sweep stale PID files)
7. `skills/quality-playbook/SKILL.md` — Heartbeat emission section added
8. `skills/quality-playbook/schemas/heartbeat.schema.json` — referenced by both skills
9. `quality_gate.py` invariants for new schemas + the daemon PID-file format
10. End-to-end validation: harness skill against a 2-3 repo plan with mixed dispatch (subagent + one shell-out). Runs in ANY session topology — no MCP required.

Out of scope for MVP, to figure out by building:

- Operator-manual dispatch UX polish (Mode 3 banner, tag correlation) — basic version ships, UX iteration in v1.5.10 if needed
- A2A field mapping document — schemas designed forward-compatible; explicit A2A reference doc deferred
- Sophisticated stall-detection (per-phase thresholds) — global 45 min + mandatory 3-min keepalive is the v1.5.9 default
- Test strategy automation — manual end-to-end validation for MVP; CI tests for the helper script and schemas

Existing Python harness (`bin/harness/`, `subprocess_runner.py`) gets deleted in the same release once the skill validates.

---

## Open questions

**Dissolved by tick-based architecture:**

- ~~#1 polling primitive viability~~ — sidecar daemon spawned by harness skill; daemon is a dumb wakeup clock with no AI context, eliminating the in-context polling failure modes (was previously the scheduled-tasks MCP; replaced 2026-06-09 due to vendor coupling + sub-session propagation failures)
- ~~#4 Sonnet drift over long polling loops~~ — N/A, no long loop
- ~~#6 resume semantics~~ — every tick is a resume

**Resolved per Council:**

- #2 cross-CLI heartbeat path: absolute paths in prompt body
- #5 stall threshold: 45 min global + mandatory 3-min keepalive in QPB heartbeat discipline
- C-1 polling primitive (Council BLOCKER): sidecar daemon (was scheduled-tasks MCP in the original Council resolution; replaced 2026-06-09 because empirical validation across 3 build-agent sessions confirmed the MCP isn't available outside Cowork-equipped top-level sessions — see § Why a self-spawned daemon, not the Cowork scheduled-tasks MCP)
- A-1 heartbeat append collision: `bin/qpb_heartbeat.py` helper as single mechanism
- A-2 cross-CLI path handwaving: absolute paths in prompt body
- A-3 context bloat: tick model eliminates; subagents return summaries only
- A-5 shell-out resume: worker.lock file with PID + start-time + cwd verification
- B-1 cross-CLI auth: pre-dispatch round-trip + STARTUP-heartbeat-within-60-sec check
- B-4 stall threshold default: 45 min + mandatory keepalive
- C-3 schema drift: single source of truth in `quality-playbook/schemas/` + `schema_version` field
- CC-1 main Design §0 conflict: this design supersedes main Design §0 substrate work; main Design §0 to be edited accordingly when this lands

**MVP-deferred — figure out by building:**

- #3 subscription concurrency caps — measure empirically during MVP validation
- #7 operator-manual dispatch UX — basic version ships, iterate after operator use
- #8 A2A schema specifics — designed forward-compatible, explicit mapping doc deferred
- #9 SKILL.md edit scope on QPB skill — define during implementation
- #10 test strategy — MVP is manual end-to-end; CI for helper + schemas

---

## Risks

| Risk | Mitigation |
|---|---|
| Sidecar daemon crashes mid-run (OS kill, OOM, machine reboot) | Daemon writes mtime-updated heartbeat file; next operator invocation of harness skill detects stale PID and re-spawns daemon. State machine is unaffected; only the cadence of ticks is lost during the outage. |
| Operator unaware a background process is running | First-tick output explicitly tells operator "spawned daemon PID N at <run-dir>/daemon.pid; stop it via `qpb harness stop <run-dir>` or kill the PID". `qpb harness status` lists active daemons across all `harness_runs/*/`. |
| Multiple harness skill invocations against same run-dir race to spawn daemons | PID file via `O_EXCL` open mode — second spawn detects lock and exits without action. Prevents daemon duplication. |
| Daemon left running after operator abandons a run | `qpb harness gc` command (or harness skill manual invocation with `--gc` flag) sweeps `harness_runs/*/daemon.pid`, identifies daemons whose run-dirs have `done.marker` or no recent worker activity, and terminates them. Documented as part of operator-facing maintenance. |
| Cross-CLI shell-outs hit auth quirks | Pre-dispatch auth check + startup-heartbeat-window detection |
| Heartbeat append race | `bin/qpb_heartbeat.py` uses `O_APPEND`; one writer per run-NN/ directory; isolation by construction |
| Subscription concurrency caps bite at pool > N | Plan-tunable pool_size; document empirical limit when found |
| Stall threshold misfires on legitimate long phases | Mandatory 3-min keepalive emission makes 45-min threshold safe; per-phase override deferred to v1.5.10 |
| Idempotency bug ships → duplicate dispatch | Schema invariants + explicit "is this already done?" check on every transition; MVP validation specifically tests double-tick safety |
| Operator misses Mode 3 ACTION REQUIRED banner | OS notification via osascript on Mac; tagged correlation file required to acknowledge |

---

*End of design. Council review folded in per `~/Documents/QPB/reviews/v1.5.9_harness_skill_council/panelist_review.md`. Implementation begins after v1.5.8 ships.*
