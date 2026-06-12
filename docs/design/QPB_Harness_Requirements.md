# Agent Harness — Requirements Document

*Status: v1.0 DRAFT, 2026-06-11 (Cowork session). Consolidates every design decision from the v1.5.9 harness arc into one requirements document: the harness design docs, the capability-ladder decisions, the multi-host research, the edge-case register, and the empirical evidence from the validation runs. Product name TBD (operator decision, deadline: before first standalone publish) — this document says "the harness" throughout and renames with the product. Lives in QPB's `docs/design/` until extraction; travels to the standalone repo as its founding requirements doc.*

*Sources of record: `QPB_v1.5.9_Design.md` Part 2 (decisions + capability ladder), `QPB_v1.5.9_Harness_Skill_Design.md` (architecture), `QPB_Harness_Multi_Host_Support_Research.md` (tiers, cross-platform, edge register), validation evidence in `spike/v1.5.9_phase_1A/spike-evidence.md` and the item-11/Haiku run records.*

---

## 1. Overview

The harness is a batch orchestrator for AI coding agents that runs **inside the operator's existing agent session** — or, degraded gracefully, inside a plain terminal window — with no server, no daemon, no framework, no API keys beyond the session the operator already has, and no admin rights.

Its architecture inverts the usual orchestration-framework shape. Frameworks put the intelligence in external infrastructure and treat the model as a worker. The harness puts **all the determinism in a small stdlib Python script** (the tick engine: a disk-truth state machine advanced one idempotent tick at a time) and uses the agent only as a relay that can wake on a schedule and start workers. The agent never decides anything; the script is the state machine; disk is the database; crash-recovery is "run one tick."

A **plan** (JSON) lists jobs — each an opaque worker prompt plus a target — with a pool size and tick cadence. Workers report progress by appending heartbeat lines to a known file. Each tick: read disk, reap finished workers, dispatch queued jobs into free pool slots, detect stalls, print a status table, schedule the next tick. When everything is terminal, the loop ends itself.

**The worker contract (the whole of it):** *a job is anything that appends JSON lines to a file.* A line at start, a line every so often, a terminal line at the end — single-line JSON, one writer per file. The `status` enum is the only field the harness interprets; everything else is decoration it displays but never reads. The worker doesn't have to be an AI: a shell script, a make target, a CI job, or a human with `echo >>` all qualify; the heartbeat helper is a convenience SDK, not a requirement. The contract deliberately honors **Postel's law** — *be conservative in what the harness emits, liberal in what it accepts*: a worker that never writes, dies mid-run, or writes garbage degrades to a visible STALLED/failed row in the status table, never to a wedged state machine, and a malformed line is skipped (and warned about), never fatal. Heartbeats are how a worker earns "running" and "completed"; silence is handled.

The harness was built as the Quality Playbook's test harness (replacing a ~10K-line Python subprocess harness, deleted 2026-06-11) but the core is payload-agnostic — the validated end-to-end runs orchestrated stub workers with zero QPB involvement. It ships two ways: a standalone repo + pip/npm packages (canonical upstream), and a vendored copy inside QPB with a lineage note.

**Empirical grounding (all 2026-06-11):** three Sonnet validation passes + one Haiku 4.5 pass (low-reasoning-model bet confirmed), multi-entry pool run with staggered dispatch, agent-honored STOP, detached workers surviving dispatch turns (pgrep-verified), and two observed in-the-wild silent loop-drops in a long-idle watcher session — which is exactly why the capability ladder and the printed-command floor exist.

## 2. Actors

- **Operator** — the human who writes the plan, starts the harness, and reads the results. May be on a locked-down corporate machine.
- **Orchestrator agent** — the AI session (Claude Code today; Copilot CLI candidate) that runs the tick loop at cadence rung 1. Optional below rung 1.
- **Ticker** — the foreground/`--once` Python script that replaces the orchestrator agent at cadence rungs 3-4 (and serves rung 2 as the cron target).
- **Worker** — the dispatched agent (subagent or detached host-CLI process) that does one job and reports via heartbeats.
- **Host scheduler** — ScheduleWakeup / `/every` / cron / launchd / Task Scheduler / host Automations, whichever exists.

## 3. User stories

1. As a QPB operator, I want to run quality audits across several repos overnight from one pasted prompt, so multi-repo benchmarking doesn't need my attention between start and finish.
2. As an operator, I want to watch progress in a status table each tick, so I know what's running, queued, finished, or stalled without reading log files.
3. As an operator, I want to halt a run by dropping a STOP file, so I never have to interrupt or kill an agent mid-thought.
4. As an operator whose session crashed (or whose wakeup silently died), I want to resume by running one command against the existing run directory, so no work is lost and nothing double-runs.
5. As a developer on a locked-down Windows machine with no admin rights and no cron, I want to open PowerShell and run one Python script that drives the whole plan, so the worst-case environment is still fully supported.
6. As a Codex/Copilot/Cursor user, I want my workers dispatched through my own CLI, so the harness isn't Claude-only.
7. As a budget-conscious user, I want the orchestration to work on a small/cheap model, so I can spend the capable-model budget on the workers.
8. As a first-time adopter, I want `pip install` + one pasted prompt to show me a complete 3-job pool run in ~20 minutes with no API spend beyond my session, so I can evaluate the thesis in one sitting.
9. As a maintainer, I want every run to leave a complete disk record, so any run can be audited after the fact without chat scrollback.
10. As the article's reader, I want the README to tell me honestly which hosts/rungs are verified versus designed, so I can trust the claims.

## 4. Use cases (Applied Software Project Management format)

### UC-1: Run a multi-job plan natively (cadence 1 + dispatch 1)

**Summary:** The operator pastes the bootstrap prompt into a fresh agent session; the session drives the plan to completion autonomously.
**Rationale:** The headline workflow — zero infrastructure, one paste.
**Users:** Operator, orchestrator agent, workers.
**Preconditions:** Plan JSON exists and validates; the session's host has a scheduling primitive and a subagent tool; run-dir parent is on local disk.
**Basic course of events:**
1. Operator pastes the bootstrap (with the plan path) into a fresh session.
2. Agent probes its tooling, announces the selected rungs (cadence 1, dispatch 1), reads the harness SKILL by absolute path.
3. Agent runs `--init`; the tick engine scaffolds the run-dir and queues all entries.
4. Agent runs tick 1; the engine emits dispatch entries up to pool_size; agent launches each worker subagent with its prompt verbatim; workers return one-line acknowledgments and run detached.
5. Agent prints the status table verbatim and schedules the next tick.
6. On each wakeup the agent runs one tick; the engine reaps terminal heartbeats into results, back-fills free pool slots from the queue (staggered dispatch), and updates the table. Idle ticks still reschedule.
7. When all entries are terminal the engine reports `done`; the agent prints the final table and exits without rescheduling.
**Alternative paths:** (a) A wakeup silently fails to fire → operator's next message (or the printed ticker command) resumes the loop from disk (see UC-4). (b) A worker stalls past the threshold → engine marks STALLED; the table shows it; operator decides. (c) A dispatch fails auth → entry goes AUTH_OR_LAUNCH_FAILED, run continues.
**Postconditions:** Run-dir contains final `harness_status.json` (`done: true`), one result record and full heartbeat file per entry; session idle; no further wakeups.

### UC-2: Monitor a run in progress

**Summary:** The operator reads per-tick status tables (or the disk) to understand run state.
**Rationale:** Observability without log spelunking; the table is the UI.
**Users:** Operator.
**Preconditions:** A run is in flight.
**Basic course of events:**
1. Each tick prints the ASCII table: per-run state, phase, last heartbeat status and age; queue/claimed/running/stalled/completed/failed counts; next-tick time.
2. The operator reads it in the session (or any tier's stdout) — or inspects `harness_status.json` and heartbeat tails directly, since disk is truth.
**Alternative paths:** Operator asks the agent to "run another tick now" — safe by idempotency; only the cycle counter changes if nothing advanced.
**Postconditions:** None (read-only).

### UC-3: Halt a run early

**Summary:** The operator drops a STOP file; the next tick halts the loop cleanly.
**Rationale:** Deterministic, race-free shutdown that never interrupts the agent mid-action.
**Users:** Operator, orchestrator agent/ticker.
**Preconditions:** Run in flight; operator can write to the run-dir.
**Basic course of events:**
1. Operator creates `<run-dir>/STOP`.
2. The next tick observes it; the engine reports `stop: true` and mutates nothing (the stop tick is fully read-only — not even the cycle counter changes).
3. The agent/ticker prints the table, states STOP detected, and exits without rescheduling.
**Alternative paths:** STOP written after the final reap → run already `done`; STOP is inert. In-flight detached workers continue to their own terminal states (documented orphan semantics; no kill in this release).
**Postconditions:** Loop terminated; state untouched from the last completed tick; run resumable by deleting STOP and ticking.

### UC-4: Resume after a crash or silent loop-drop

**Summary:** Any fresh session — or the ticker — resumes an interrupted run from disk.
**Rationale:** Two silent wakeup-drops were observed in the wild on 2026-06-11; recovery must be one action.
**Users:** Operator, any fresh orchestrator agent or the ticker.
**Preconditions:** A run-dir with non-terminal state exists.
**Basic course of events:**
1. Operator notices the loop stopped (no new ticks).
2. Operator re-pastes the bootstrap in any session pointing at the existing RUN_DIR (skip `--init`) — or runs the printed `harness_ticker.py --once <run-dir>` command.
3. The tick engine reads disk and continues exactly where the run left off; idempotency guarantees nothing double-dispatches.
**Alternative paths:** Machine slept/hibernated → heartbeat ages are inflated; the wall-clock-jump guard treats ages as suspect for one tick instead of false-STALLING.
**Postconditions:** Loop running again; at most one cycle increment beyond the interruption point; zero duplicated work.

### UC-5: Run on a locked-down host (cadence 3 + dispatch 2 — the floor that must work)

**Summary:** On Windows/macOS/Linux with no admin rights and no scheduler access, the operator runs the plan from one terminal window with the foreground ticker.
**Rationale:** Operator-set worst case (2026-06-11): corporate locked-down Windows must be first-class.
**Users:** Operator, ticker, workers (detached host-CLI processes).
**Preconditions:** User-level Python 3; at least one agent CLI on PATH and authenticated; plan entries use `dispatch_mode: "shell"` with `worker_cmd` templates.
**Basic course of events:**
1. Operator opens cmd/PowerShell/terminal — no elevation.
2. Operator runs `python harness_ticker.py <plan-or-run-dir>`.
3. The ticker loops: run one tick; for each dispatch entry, write the worker prompt to a file and spawn the host CLI detached (platform-appropriate flags), recording PID + start time in the claim lock; print the table; sleep `tick_interval`; repeat.
4. On `done`, the ticker prints the final table and exits.
**Alternative paths:** (a) Operator closes the window → in-flight child workers may die (documented); rerunning the ticker resumes and re-detects state from heartbeats/PID locks. (b) CLI auth fails pre-flight → entry marked AUTH_OR_LAUNCH_FAILED with an actionable message. (c) No scheduler AND the operator can't keep a window open → UC-6 or UC-7.
**Postconditions:** Same disk record as UC-1 — the run artifacts are tier-invariant.

### UC-6: Scheduled run via cron or host automations (cadence 2 + dispatch 2)

**Summary:** An OS scheduler (or Codex-style Automations) fires one tick per cadence interval; no window stays open.
**Rationale:** Long/overnight plans on hosts where a scheduler is available; survives logouts.
**Users:** Operator, host scheduler, ticker (`--once`), workers.
**Preconditions:** Scheduler rights; plan uses shell dispatch; run-dir initialized.
**Basic course of events:**
1. Operator installs the printed one-line schedule entry (`harness_ticker.py --once <run-dir>` at the tick cadence).
2. Each fire executes exactly one tick (the per-run-dir lockfile makes overlapping fires skip cleanly).
3. Operator removes the schedule entry after `done` (or the entry self-reports done and exits instantly thereafter — idempotent and cheap).
**Alternative paths:** DST/local-time cron quirks documented; relative-interval rungs immune.
**Postconditions:** Same disk record; schedule entry removable at leisure.

### UC-7: Manual-tick floor (cadence 4)

**Summary:** With no scheduler, no ticker loop, and no agent session, the operator advances the run by hand, one printed command at a time.
**Rationale:** The harness must never strand a run: every failure path prints the exact next command.
**Users:** Operator.
**Preconditions:** A run-dir exists; user-level Python.
**Basic course of events:**
1. Any failure of a higher rung prints: "to continue this run, execute: `python3 <abs>/harness_ticker.py --once <run-dir>`".
2. The operator runs it whenever convenient; each invocation is one safe tick.
3. Repeat until the output reports done.
**Alternative paths:** Operator over-ticks — harmless (cycle-only diffs).
**Postconditions:** Same disk record; cadence is whatever the operator made it.

### UC-8: Install and run the demo (adopter first contact)

**Summary:** A new user installs from pip or npm and watches a complete 3-job pool run in ~20 minutes.
**Rationale:** The downloadable artifact is the article's proof; the demo IS the thesis experienced.
**Users:** Operator (first-time), orchestrator agent or ticker, Python stub workers.
**Preconditions:** User-level install (`pip install --user <name>` / `npm install <name>`); a Claude Code session OR just Python (the demo runs at any rung).
**Basic course of events:**
1. Operator installs the package and locates the example plan (Python stub workers — cross-platform, no API spend).
2. Operator pastes the bootstrap (rung 1) or runs the ticker (rung 3).
3. The demo exhibits: pool-limited dispatch, genuine idle ticks, staggered dispatch when the first stub finishes, heartbeat-driven reaps, clean self-termination — in ~20 minutes.
**Alternative paths:** Locked-down host → the demo works identically at rung 3 (that's the point).
**Postconditions:** The user has seen every architectural claim demonstrated on their own machine.

## 5. Functional requirements

**Plan & configuration**
- FR-1: A plan is a single JSON file: `tick_interval_minutes`, `pool_size`, `stall_threshold_minutes`, `launch_grace_minutes`, `entries[]`.
- FR-2: Each entry: `task_id` (UUID), `target_repo` (absolute), `dispatch_mode` (`"subagent"` | `"shell"`), and a `worker_prompt` (subagent) or `worker_cmd` template + prompt-file (shell). All schemas carry `schema_version`; consumers warn on mismatch.
- FR-3: Worker prompts/commands receive the absolute-path placeholder block (`{HEARTBEAT_PATH}`, `{TASK_ID}`, `{RUN_DIR}`, `{TARGET_REPO}`); nothing is ever derived from cwd.

**Tick engine (state machine)**
- FR-4: All state lives on disk in a per-run directory (`plan.json` snapshot, `harness_status.json`, `queue/`, `claimed/`, `results/`, per-entry `run-NN/` with `heartbeat.ndjson`). Disk is the single source of truth.
- FR-5: One tick = read disk → apply transitions (reap terminals → dispatch into free slots → stall checks → done/stop detection) → write state atomically (write-temp-rename) → emit `{dispatch_list, status_table, next_tick_minutes, done, stop}` as JSON on stdout.
- FR-6: Every transition is idempotent; a double tick changes only the `cycle` counter (the deliberate idle-tick witness — a true empty diff is impossible by design).
- FR-7: Pool semantics: at most `pool_size` non-terminal dispatched entries; freed slots are back-filled from the queue in the same tick (staggered dispatch).
- FR-8: Stall detection: heartbeat age > threshold ⇒ STALLED; `launch_grace_minutes` before first heartbeat; mandatory worker keepalives make the global threshold safe; a wall-clock jump (tick gap ≫ cadence) suppresses stall marking for one tick (E2).
- FR-9: The reap transition verifies the claimed job record; an externally-missing claim is recorded as an anomaly, never fabricated success.
- FR-10: A `STOP` file at the run-dir root makes the next tick fully read-only: report `stop: true`, change nothing (not even `cycle`).
- FR-11: When all entries are terminal the engine reports `done: true`; terminal ticks suppress the next-tick line in the table.
- FR-12: A per-run-dir lockfile serializes concurrent tick processes (`fcntl`/`msvcrt`); a locked tick skips with a message (E1).
- FR-13: `--init <plan>` scaffolds a new timestamped run-dir and queues all entries; re-running a tick against any existing run-dir resumes it.

**Dispatch**
- FR-14 (subagent mode): the orchestrator launches one subagent per dispatch entry, prompt verbatim, via its session's subagent tool (`Task`/`Agent` — prose names both); the worker's return contract is a single summary line; workers never echo heartbeat content.
- FR-15 (shell mode): the dispatching tier writes the prompt to a file and spawns the host CLI detached (POSIX `start_new_session`; Windows `DETACHED_PROCESS|CREATE_NEW_PROCESS_GROUP`), recording PID + start time in the claim lock for dead-vs-slow stall discrimination (A-5).
- FR-16: A cheap per-CLI auth/availability pre-flight runs before first shell dispatch; failures mark the entry `AUTH_OR_LAUNCH_FAILED` with an actionable message rather than silently stalling.
- FR-17: The orchestrating tier dispatches exactly what `dispatch_list` names — never more, never on its own initiative.

**Heartbeat contract**
- FR-18: Workers append single-line JSON records (`ts`, `task_id`, `schema_version`, `status` ∈ STARTING|IN_PROGRESS|COMPLETED|FAILED|ABANDONED, plus optional `label`, `message`, `data`) to their heartbeat file; terminal records carry `result_file` + `summary`. **`status` is the ONLY field the harness interprets** (it drives the state machine). `label` is a short free-form string displayed verbatim in the status table (column: ACTIVITY; truncated to width; ASCII-sanitized for display, raw preserved on disk) — this replaces the QPB-specific `phase`/`step` pair. `message` is longer human-facing detail. `data` is an opaque JSON object the harness never reads — the structure escape hatch and the A2A migration path. (QPB's vendored integration sets `label` from its own phase identity; that coupling never enters the generic core.)
- FR-19: A stdlib helper CLI performs all appends (`emit` / `keepalive` / `terminal`): JSON-encodes every value (no printf interpolation), opens with `O_APPEND`, one writer per run directory. The helper is optional — any conformant appender qualifies (Postel: the harness is liberal in what it accepts; malformed lines are skipped with a warning, never fatal).
- FR-20: **Specifiable heartbeat file.** By default the harness assigns `{HEARTBEAT_PATH}` inside the run-dir; a plan entry MAY instead declare `heartbeat_path` (absolute) to point the harness at a file the job already writes — supporting pre-existing tools/jobs with their own status-file location, with no change to the job. The run-dir result/manifest layout is unaffected.
- FR-21: If a heartbeat cannot be written, the helper exits nonzero loudly and worker guidance is to abort with FAILED (E6) — a silent worker must never look healthy.
- FR-21a: **No model-transcribed paths, ever.** Every harness-known path a worker needs (`{HEARTBEAT_PATH}`, `{TASK_ID}`, `{RUN_DIR}`, `{TARGET_REPO}`, and any helper/bin location e.g. `{HARNESS_BIN}`) is mechanically substituted by the tick engine before dispatch — a worker prompt must never ask a model to copy or substitute a literal path itself. Evidence: 2026-06-12 Haiku run `20260612T005833Z`, where the one hand-copied path in a stub script was transcribed as `/Users/anthropic/...` (username hallucinated), silently killing every heartbeat while the job "completed" invisibly — caught by launch grace, diagnosed only by script diff.
- FR-21b: When the engine marks an entry `AUTH_OR_LAUNCH_FAILED`, the status record and table carry a diagnostic hint ("no heartbeat received within launch grace — check worker-side launch: auth, helper availability, paths"), because the bucket covers more causes than auth. Long state names must not overflow the table column (fixed-width or abbreviated display).

**Cadence & degradation (the capability ladder)**
- FR-22: At startup an orchestrating agent probes its own tooling and announces the selected cadence + dispatch rungs.
- FR-23: Cadence rungs, preferred high to low: (1) in-session scheduling primitive; (2) OS/host scheduler firing `--once` ticks; (3) foreground ticker loop; (4) manual ticks. Rungs 2-4 require shell dispatch.
- FR-24: The ticker provides rungs 3-4: loop mode (tick → spawn → sleep) and `--once`; stdlib-only.
- FR-25: Every scheduling-failure path — at every rung — prints the exact next command (absolute paths filled in) to continue the run in another window. No run is ever stranded without printed instructions.
- FR-26: Loop-continuation discipline: every non-terminal tick ends with a reschedule (or its rung's equivalent); idle is not done; the only clean exits are `done` and `stop`.
- FR-26a: **Safety tick (recommended deployment pattern, documented in README + STATE_MACHINE.md).** Because ticks are idempotent and the E1 lockfile serializes concurrent tick processes, redundant ticking is safe by construction — so a rung-1 (in-session timer) run SHOULD be paired with a low-frequency external safety tick (cron/scheduler/second-terminal ticker running `--once` at ~3× the plan cadence) against the same run-dir. While the in-session timer is alive, safety ticks are cycle-only no-ops; if the timer dies silently, the safety tick rescues the run within one safety interval with no detection logic and no operator nudge. Rationale: in-session scheduled tasks are session-scoped and empirically fragile in long sessions (4+ silent drops observed in the v1.5.9 runner watcher, 2026-06-11/12; ScheduleWakeup subsystem has known rough edges upstream); the harness treats rung-1 timers as fallible rather than trusting them.

**Observability & evidence**
- FR-27: The status table is pure ASCII, printed verbatim by the relaying tier, and shows per-run state/phase/last-heartbeat/age plus aggregate counts.
- FR-28: A completed run's directory is a self-sufficient audit record: final status, every heartbeat line, every result record, the plan snapshot.
- FR-29: Pre-flight warns when the run-dir path looks like a synced folder (OneDrive/Dropbox patterns) (E4).

**Distribution**
- FR-30: Shipped as a standalone repo (canonical upstream) + pip and npm packages installable user-level; QPB carries a vendored copy with a lineage note and a drift test pinned to an upstream release.
- FR-31: The package includes the example plan with cross-platform Python stub workers — the ~20-minute zero-API-spend demo (UC-8) — runnable at rung 1 or rung 3.
- FR-32: The plugin layout (plugin.json + marketplace.json) qualifies for Claude-marketplace submission; both the harness and QPB plugins are submitted.
- FR-33: Publishes are gated: clean-clone cold-build, built-artifact end-to-end test in a throwaway environment, dry-run before any live upload (QPB's publish-safety discipline verbatim).

## 6. Nonfunctional requirements

- NFR-1 **Cross-platform:** Windows, macOS, Linux — equal support; no platform-conditional features in the core.
- NFR-2 **No privileges:** no admin/root anywhere — install, run, schedule (rung 3 exists precisely for the no-scheduler case).
- NFR-3 **Zero runtime dependencies:** tick engine, ticker, and heartbeat helper are Python stdlib only. The only external requirements are user-level Python 3 and (for agent workers) a host CLI.
- NFR-4 **Model-tier tolerance:** orchestration must work on low-reasoning models — all decisions live in the deterministic script; the agent's per-tick role is ~7 fixed steps. Evidence: Haiku 4.5 clean loop (2026-06-11); prose carries absolute paths and dual tool-names because small models will not search or infer.
- NFR-5 **Bounded context:** per-tick agent prose is small and fixed; worker returns are one line; the orchestrator's context grows O(ticks), not O(work). No long-lived in-context state.
- NFR-6 **Determinism & idempotency:** same disk state ⇒ same tick outcome; re-entry is always safe (the property every rung of the ladder leans on).
- NFR-7 **Encoding safety:** all text I/O is `encoding="utf-8", errors="replace"` for external content; console output is ASCII-safe (cp1252 hazard); enforced by AST sweep tests with mutation-verified pins.
- NFR-8 **Reliability through degradation, honestly stated:** wakeup primitives are known to drop silently (observed twice, 2026-06-11); the design treats every rung as fallible and makes recovery one printed command. Docs state the window-stays-open and orphan-on-STOP semantics plainly.
- NFR-9 **Auditability:** any run reconstructable from its run-dir alone — no chat scrollback required.
- NFR-10 **Run-dirs on local disk** (synced/network folders unsupported, warned).
- NFR-11 **Security posture:** no network calls of its own, no telemetry, no shell-out except the operator-declared `worker_cmd` templates; prompt-files avoid shell-quoting injection surfaces; Apache-2.0.
- NFR-12 **Honest host-support claims:** the README's support table distinguishes VERIFIED (evidence-linked) from DESIGNED (unverified) per host/rung. No claim ships without a validation-matrix run behind it.
- NFR-13 **Tick cost:** a tick is sub-second script execution; idle ticks are cheap by design so over-polling is always safe.

## 7. Constraints & assumptions

- C-1: One writer per heartbeat file (per run-NN/) — concurrency safety derives from layout, not locking.
- C-2: In-session subagents do not survive their session's turn ending in externally-ticked contexts — hence the cadence/dispatch coupling rule.
- C-3: The orchestrator session (rung 1) or ticker window (rung 3) must stay open for the plan's duration; rung 2 has no such constraint.
- C-4: Workers must be able to run the heartbeat helper (user-level Python 3 on their host).
- C-5: In-session autonomous loops have a host-side fragility that is NOT the timer: per the 2026-06-12 Class-C forensics, wakeups fired 4/4 reliably, but the wakeup-resumed model turn intermittently mis-serializes its first tool call into the text channel and dies silently on `end_turn`. Compaction/E7 was refuted as a cause (0/4). Treat every rung-1 resumed turn as fallible; the FR-26a safety tick is the standing mitigation, independent of root cause.

## 8. Out of scope (this release)

Kill semantics for in-flight workers on STOP (documented orphan behavior); per-phase stall thresholds; A2A/cross-machine transport (schemas are A2A-ready by carrying `task_id`/`schema_version`); full Codex/Cursor per-host validation matrices (v0.2); harness resume/iterate strategies (QPB v1.5.11 B-3); the silent-drop watchdog (`--max-quiet`) beyond the printed-command recovery; orchestrator-side telemetry/dashboards (the table and the disk are the UI).

## 9. Validation evidence map

| Claim | Evidence |
|---|---|
| Autonomous multi-tick loop, idle ticks survive | Spike PASS ×3 passes (Sonnet), `spike-evidence.md` |
| Pool + staggered dispatch + multi-entry | Item-11 E2E, run-dir `20260611T191325Z` records |
| Low-reasoning-model orchestration | Haiku 4.5 run `20260611T231408Z` (re-test in flight) |
| Detached workers outlive dispatch turn | Instruction-003 dry-run (pgrep + heartbeat evidence) |
| Agent honors STOP from prose | Spike pass 3 (STOP mtime vs tick time, state untouched) |
| Idempotency / cycle-only re-tick | 002 smoke + 003 dry-run + unit suite (mutation-verified) |
| Encoding/cp1252 safety | 007/008 AST sweeps, mutation-verified incl. independent orchestrator re-run |
| In-session loops can die silently (NOT the timer: Class-C resumed-turn tool-call mis-serialization; wakeups fired 4/4; E7/compaction refuted) | Instruction-011 transcript forensics, 4 drops root-caused with quoted evidence (`runner/1.5.9/outputs/011-loop-drop-self-forensics.md`); ladder + FR-26a safety-tick rationale |
| Cadence 2/3/4, shell dispatch, Windows floor | PENDING — Phase 2B build + item-11-style validation matrix |

---

*End of requirements v1.0 DRAFT. Maintained alongside the design docs; renames with the product. Functional/nonfunctional numbering is the stable reference for instructions, tests, and the eventual README.*
