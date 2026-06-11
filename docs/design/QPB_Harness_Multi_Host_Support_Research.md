# Harness Multi-Host Support — Research + Draft Plan

*Status: RESEARCH DRAFT, 2026-06-11 (Cowork session, web research same day — this space moves fast; re-verify before implementation). Not yet scoped to a release. Feeds two consumers: (a) the standalone harness's README "host support" section + its v0.x roadmap (v1.5.9 Phase 2B), and (b) the QPB-side Mode 2 / multi-host work already deferred to v1.6+ by `QPB_v1.5.9_Harness_Skill_Design.md`. Operator review required before any of this becomes plan-of-record.*

---

## What the harness actually requires from a host

Four capabilities, in increasing order of host-specificity:

1. **Run a shell command and capture stdout** (the tick script). Universal.
2. **Follow ~7 fixed prose steps and parse a small JSON.** Any model, any host. **Low-reasoning-model validation: Haiku 4.5 PASS (2026-06-11, run-dir `20260611T231408Z`)** — identical disk shape to the Sonnet passes: 5 autonomous ticks, 2 idle ticks rescheduled, staggered dispatch on the reap tick, 3/3 completed, clean `done` exit, zero re-prompts. Sonnet PASS ×3 prior. Two non-fatal Haiku deviations, both prose-hardening items for the standalone (see below): (a) it loaded the WRONG skill — invoked the `quality-playbook` worker skill via the Skill tool (printing the banner + plan narration) instead of reading the harness SKILL.md, then ran the loop correctly anyway because the bootstrap prompt itself carries the per-tick sequence; (b) mild extra narration between steps (never read heartbeats, never touched state — harmless). Related Sonnet observation from the same transcript: Sonnet burned ~60K subagent tokens on Explore calls just LOCATING the harness SKILL.md. **Hardening: the bootstrap prompt must carry the absolute SKILL.md path** (`<QPB_REPO>/plugins/quality-playbook-harness/skills/quality-playbook-harness/SKILL.md`) instead of naming the skill — removes both failure modes and the token waste. The redundancy that saved Haiku (bootstrap restates the per-tick sequence) is load-bearing; keep it in the standalone's bootstrap.
3. **Start workers that outlive the dispatching turn.** Claude Code: `Task` subagents + the spike-proven fact that `nohup`-detached processes survive the turn ending. Every host with shell access has the `nohup` path even without subagents.
4. **Re-entry at a cadence** (the wakeup). The only piece that is genuinely host-specific today (`ScheduleWakeup`).

**The degradation property that makes portability cheap:** disk is truth, every tick is idempotent and stateless, and ticks carry no session memory. Therefore the re-entry mechanism does not need to live inside the session — ANY trigger that causes ANY fresh agent invocation (or, in the limit, a plain script) to run one tick resumes the state machine correctly. The in-session wakeup is a convenience, not a dependency. This was demonstrated incidentally: pass-2/pass-3 of the spike resumed in a reused session, and the design's crash-recovery story ("re-paste the prompt") is the same property.

---

## The tier model

**Tier 1 — Native in-session orchestrator.** The host has both a scheduling primitive and subagent dispatch; the operator pastes one bootstrap and the session drives the plan to completion. Claude Code today (ScheduleWakeup + Task) — SHIPPED, validated. Candidate second host: **Copilot CLI**, which now has `/every` and `/after` scheduling (natural language or cron) plus subagents and a background-session harness — the closest published equivalent to ScheduleWakeup. Codex and Cursor have app/IDE-level scheduled Automations but in-session, prose-invokable scheduling is unverified.

**Tier 2 — Externally-nudged agent orchestrator.** No in-session wakeup needed: an OS scheduler (cron / launchd / Windows Task Scheduler — or the host's own Automations feature, e.g. Codex app Automations with cron syntax) fires a non-interactive one-tick invocation on a cadence: `codex exec --full-auto "<one-tick prompt>"`, `copilot --allow-all -p "<one-tick prompt>"`, `cursor agent --print --force "<one-tick prompt>"`. Each fire is a fresh session; disk state resumes it; the one-tick prompt is a condensed BOOTSTRAP_PROMPT that skips `--init` when the run-dir exists. Dispatch inside the tick: detached `nohup` workers via the host CLI (see Tier 2/3 dispatch below). Works on every host that has a non-interactive CLI — all four do.

**Tier 2.5 — Foreground ticker (the no-admin floor).** Operator decision 2026-06-11: the worst-case deployment MUST work — Windows, locked-down host, no admin rights, no cron/Task Scheduler/launchd access. The answer is a foreground loop instead of a scheduler: the operator opens a plain cmd/PowerShell/terminal window and runs `python harness_ticker.py <plan-or-run-dir>`, which loops — run one tick, spawn any dispatches, `time.sleep(tick_interval)`, repeat until `done`/`stop` — entirely in that process. No scheduler, no daemon, no elevation, no install beyond user-level Python. This is realistic and cheap (~30-50 lines, stdlib-only): the tick script is already a pure subprocess call, and dispatch becomes `subprocess.Popen` with platform-appropriate detach flags (`start_new_session=True` on POSIX; `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP` on Windows — or simply child processes, accepting that closing the window kills in-flight workers, which the docs state plainly). Constraint to document honestly: the window must stay open for the plan's duration — the same constraint the Tier-1 Claude Code session already has. The ticker is also the natural Tier-3 nudger run in loop mode, so it's one artifact serving two tiers.

**Tier 3 — Agentless orchestrator.** The orchestrator model is removed entirely: a thin nudger script (cron-fired, or the Tier 2.5 ticker in loop mode) runs the tick script and directly spawns each `dispatch_list` entry as a detached host-CLI subprocess. No orchestrator agent; workers are still agents. This is the limit case of "the agent only relays" — when the relay is mechanical enough, a script can do it. Keeps the tick script pure (read/transition/emit only); the nudger owns process spawning. Strong article beat: the same plan file runs under all four tiers.

---

## Cross-platform + no-admin requirements (operator, 2026-06-11)

Target: Windows / macOS / Linux, no admin privileges anywhere in the path.

- **Tick script + heartbeat helper:** already stdlib-only Python with `pathlib` — the right substrate. Verify the v1.5.7-era Windows disciplines carry to the NEW files: every `open(text=True)`/`subprocess.run(text=True)` site passes `encoding="utf-8", errors="replace"` (the 185/189/190 cp1252 hazard chain), and the 189/190 AUDIT sweep tests actually enumerate `bin/qpb_harness_tick.py` + `bin/qpb_heartbeat.py` (they predate these files and previously swept the now-deleted `bin/harness/**` — coverage gap likely).
- **Status table:** must stay pure ASCII (cp1252 console hazard — the 185 lesson).
- **Heartbeat appends on Windows:** `O_APPEND` semantics differ slightly from POSIX, but the single-writer-per-run-dir design makes them safe; keep the design constraint documented.
- **The demo stub must be Python, not bash.** The current stub plan's `worker_prompt` embeds a bash script — dead on a locked-down Windows box. Rewriting the stub as a small Python script (same STARTING → IN_PROGRESS×N → COMPLETED lifecycle, same heartbeat-helper calls) makes the demo cross-platform in one move. The standalone's example plan ships the Python stub.
- **Install path:** user-level only — `pip install --user` / npm with a user prefix; no global installs assumed. Python via the `py` launcher or a user install on Windows.
- **No-cron floor:** Tier 2.5 above.

---

## Edge-case register (2026-06-11 — triage into the standalone design)

| # | Edge case | Notes / disposition |
|---|---|---|
| E1 | **Concurrent ticks** — cron overlap (Tier 2/3) or operator manual tick racing a wakeup (Tier 1). Idempotency guards each transition, but two simultaneous tick PROCESSES have a TOCTOU window (both read `queued`, both emit the same dispatch). Impossible in single-session Tier 1; real under cron. | Mitigate: per-run-dir tick lockfile (`fcntl`/`msvcrt` — stdlib both platforms); skip tick if locked. Standalone v0.1 item. |
| E2 | **Sleep/hibernate mid-run** — laptop lid closes: wakeups don't fire while asleep; on resume, heartbeat ages are inflated (workers slept too) → false STALLED marks; possibly related to the 2026-06-11 observed silent loop-drop. | Mitigate: stall logic detects wall-clock jumps (last-tick timestamp gap >> cadence ⇒ treat HB ages as suspect for one tick). Document "keep the machine awake" as the simple rule. |
| E3 | **Paths with spaces / non-ASCII** — common in Windows user dirs. The worker_prompt path block, shell-dispatch command templates, and stub scripts must quote everything; non-ASCII paths re-raise the cp1252 hazard. | Quoting audit + a test plan with a spaced path. Python-stub move (above) eliminates most bash-quoting risk. |
| E4 | **Run-dir on a synced/network folder** (OneDrive, Dropbox, NFS) — sync daemons fight O_APPEND and atomic renames; file locks may not be advisory. | Document: run-dirs on local disk only. Cheap pre-flight warning if the path looks synced (e.g. contains `OneDrive`). |
| E5 | **STOP racing an in-flight dispatch** — STOP written between the script emitting `dispatch_list` and the agent dispatching: workers launch after the STOP intent. | Already-documented orphan semantics cover it; optionally the SKILL prose says "check for STOP in the tick output BEFORE dispatching" (the script already orders this; the race is only within one tick's agent turn). Low priority. |
| E6 | **Worker can't write heartbeat** (disk full, permissions) — worker runs fine but looks stalled → false STALLED. | Worker-side: heartbeat helper exits nonzero loudly; worker prose says abort-with-FAILED if heartbeats can't be written. Document. |
| E7 | **Session compaction** (Tier 1) — a very long Claude Code session compacts its context mid-plan; does the pending ScheduleWakeup survive compaction? Unknown — possible cause of the observed drop. | Empirical test; if wakeups die on compaction, the SKILL prose adds a post-compaction recovery line (the recap already restates the loop). |
| E8 | **Auth/limit expiry mid-plan** — subscription rate-limit or token expiry hours into a long plan; dispatch starts failing. | `AUTH_OR_LAUNCH_FAILED` already exists for launch failures; verify the path triggers cleanly on auth errors and the status table makes it obvious. |
| E9 | **Multiple concurrent plans** in one repo — two run-dirs, two orchestrator sessions. | Already safe by design (state is per-run-dir); document explicitly + note subscription concurrency stacking. |
| E10 | **DST / clock changes mid-run** — tick timestamps are UTC (good); ScheduleWakeup cadence is relative (good); cron entries in local time can skip/double an hour. | Document for Tier 2/3 cron users; relative-interval tiers immune. |

---

## Bootstrap-prompt hardening (from the 2026-06-11 model-tier tests; fix is worker-lane)

1. Step 1 must carry the **absolute SKILL.md path** (`<QPB_REPO>/plugins/quality-playbook-harness/skills/quality-playbook-harness/SKILL.md`) instead of naming the skill — Sonnet burned ~60K Explore-subagent tokens locating it; Haiku loaded the `quality-playbook` WORKER skill instead and never read the harness SKILL at all.
2. Add the negative guard: "do NOT invoke the `quality-playbook` skill — that is the worker's skill, not yours."
3. Keep the bootstrap's restatement of the per-tick sequence — that redundancy is what carried Haiku to a clean PASS despite (1).

---

## Per-host findings (2026-06-11 — verify empirically before claiming support)

| Capability | Claude Code | Copilot CLI | Codex CLI/app | Cursor CLI |
|---|---|---|---|---|
| Non-interactive invocation | `claude -p` (deprecated June 15 — NOT a dependency) | `copilot --allow-all -p` | `codex exec --full-auto` | `cursor agent --print --force` (`--output-format json` available) |
| In-session scheduling | **ScheduleWakeup** (shipped, validated) | **`/every`, `/after`** (cron or natural language) — Tier-1 candidate, prose-invokability unverified | App-level Automations (cron syntax, local or worktree); CLI-internal unverified | IDE/cloud Automations; CLI-internal unverified |
| Subagents | `Task`/`Agent` tool | Subagents + `/fleet` parallel fan-out | Subagents (app); CLI unverified | Subagents (≤10 parallel paid), async subagents, SDK |
| Background workers | Task + nohup proven | Background sessions (survive restarts, parallel) | Cloud tasks + Automations worktrees | Background Agents (isolated cloud VMs) |
| Skill/prose loading | plugin SKILL.md | `.github/skills/` | `AGENTS.md` + skills | `.cursor/` rules |
| Worker-side needs (shell + python3 for heartbeat) | ✓ | ✓ | ✓ | ✓ (cloud VMs: python3 available, paths differ — heartbeat file must be reachable by the orchestrator; cloud-VM workers likely need Tier-2 local dispatch instead) |

Dispatch command shapes are prior art: QPB's `runners.py` already wraps all four CLIs with the correct auto-approval flags.

---

## What changes in the artifact (mostly additive)

1. **Plan schema:** `dispatch_mode` enum gains `"shell"` alongside `"subagent"`; a shell entry carries a `worker_cmd` template (e.g. `nohup codex exec --full-auto {WORKER_PROMPT_FILE} ...`) with the same absolute-path placeholder block. `schema_version` bump covers drift (the C-3 guard already warns on mismatch). Worker prompts likely move to files for shell dispatch (arg-length + quoting safety) — `queue/job-NNNNN.prompt.txt`.
2. **Tick script:** unchanged for Tiers 1-2 (the agent or the one-tick prompt does dispatch). Tier 3 adds a separate `harness_nudge` script that runs the tick and spawns `dispatch_list` via subprocess — the tick script itself stays a pure state-machine stepper.
3. **Worker lifecycle for shell dispatch:** PID + start-time lock files in `claimed/` (the original Council A-5 finding, deferred with Mode 2) so stall detection can distinguish dead-process from slow-worker. Heartbeat-based stall detection is already host-agnostic.
4. **SKILL prose:** a host-support preamble — "on Claude Code use ScheduleWakeup; on Copilot CLI use /every; on other hosts use the cron recipe in README" — plus the already-landed Task/Agent dual naming generalized to "your session's subagent-dispatch tool."
5. **Auth pre-flight:** the state machine's `AUTH_OR_LAUNCH_FAILED` path already exists; shell dispatch needs a cheap pre-flight (`<cli> --version` / auth probe) per host before first dispatch — shape per the original B-1 Council finding.

---

## Empirical validation matrix

The stub plan (`testing/e2e_stub_plan.json` shape) is the universal test vehicle — its worker is plain bash + python3 and runs identically on every host. Per host × tier: same PASS criteria as item-11 (autonomous to done, ≥1 idle tick, staggered dispatch, clean exit; for Tier 2/3: every cron fire produces exactly one tick, no double-dispatch under overlapping fires — idempotency already guards this but verify under real cron).

Sequencing of experiments by expected cost: (1) Haiku-on-Claude-Code — in flight; (2) Copilot CLI Tier 1 (`/every` + subagents — if it holds, the SKILL prose generalizes with minimal change); (3) Tier 3 agentless on any host (cheap, pure scripting, biggest article payoff); (4) Codex/Cursor Tier 2 via their Automations.

---

## Draft phasing (operator decides; nothing here is committed)

- **Standalone v0.1 (rides v1.5.9 Phase 2):** Tier 1 Claude Code native + README documenting the tier model and a tested cron recipe for Tier 2 on one non-Claude host. Honest host-support table.
- **Standalone v0.2:** `"shell"` dispatch mode + `harness_nudge` (Tier 3) + Copilot CLI Tier 1 if the `/every` experiment passes.
- **QPB v1.6+:** Mode 2 adoption per the existing deferral, consuming whatever the standalone validates.

---

## Sources (2026-06-11)

- Codex: developers.openai.com/codex/cli (exec), developers.openai.com/codex/app/automations (cron-syntax Automations, worktrees, cloud triggers)
- Copilot CLI: github.blog changelog 2026-05-13 (CLI agent + sessions view), deepwiki github/copilot-cli (agent modes, subagents, `/every` `/after`), code.visualstudio.com/docs/copilot/agents/copilot-cli (background sessions, SDK monitoring)
- Cursor: cursor.com/docs/cli/using (`--print`, `--output-format json`), cursor.com/docs/subagents (≤10 parallel), Cursor 3.2+ async subagents, SDK announcement 2026-04-29
- Cross-host: QPB `bin/.../runners.py` (the four CLI invocation shapes + auto-approval flags, shipped since v1.5.7)
