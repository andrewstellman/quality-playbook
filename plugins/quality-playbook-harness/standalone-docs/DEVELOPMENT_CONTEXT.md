# Wakecycle — Development Context

*Read this once to bootstrap a fresh development chat to full context. It is
a projection of `docs/REQUIREMENTS.md` (the spec) plus the history and the
known issues. Where this and the requirements doc disagree, the requirements
doc wins.*

## Architecture in one screen

- **Tick contract.** One tick = read disk → apply transitions (reap terminal
  workers → dispatch queued jobs into free pool slots → stall/launch checks →
  done/stop detection) → write state atomically → emit
  `{dispatch_list, status_table, next_tick_minutes, done, stop}` on stdout.
  The orchestrating tier (agent or ticker) does exactly what `dispatch_list`
  says, prints the table, schedules the next tick. (FR-5)
- **State machine.** Per run: `queued → claimed → running → completed |
  failed`. `claimed`+no-heartbeat-past-launch-grace → `auth_or_launch_failed`
  (shown as `LAUNCH-FAIL`). `running/claimed`+stale-heartbeat → `stalled`
  (non-terminal, recoverable). Every transition is idempotent; a double tick
  changes only the `cycle` witness counter. A `STOP` file makes the next tick
  fully read-only. (FR-4..FR-13)
- **Heartbeat contract (schema v2).** Workers append single-line JSON: `ts`,
  `task_id`, `schema_version`, `status` (the only interpreted field), plus
  optional `label` (free string, shown in the ACTIVITY column), `message`,
  and an opaque `data` object the harness never reads; terminal lines carry
  `result_file` + `summary`. Postel: the reader still accepts v1
  (`phase`/`step`) lines; a malformed line is skipped with a warning, never
  fatal. (FR-18..FR-21b)
- **Capability ladder.** Two axes — cadence (1 in-session timer / 2 OS
  scheduler / 3 foreground ticker / 4 manual) × dispatch (1 in-session
  subagent / 2 detached shell). Rungs 2–4 require shell dispatch. The disk
  state machine is identical at every rung; the worst case (rung 3 + shell,
  locked-down Windows) must work. (FR-22..FR-26a)

## Design lineage (born in Quality Playbook v1.5.9)

All dates 2026:

1. **Spike (Phase 1A).** Proved the core patterns — atomic writes,
   state-guarded transitions, cycle-as-witness, STOP read-only, the
   `{dispatch_list,…}` shape — with 3 Sonnet autonomous-loop passes.
2. **Phase 1B / 1B.0.** The deterministic tick engine; one shared
   phase-identity table behind the sentinel/run-state/heartbeat so they agree
   by construction.
3. **The capability ladder (Part 2).** The cadence × dispatch decision and
   the no-admin floor; the printed-command degrade rule; the safety-tick
   pattern. Backed by multi-host research and an edge-case register.
4. **Phase 2B — the generic core.** Extracted the payload-agnostic heartbeat
   helper, the cross-platform demo stub, the foreground ticker, shell
   dispatch + PID locks, the concurrent-tick lockfile (E1) and wall-clock-jump
   guard (E2). Live no-admin-floor demo (2026-06-12).
5. **Generalization (instruction 010).** Heartbeat schema v2 (`label`/`data`
   replacing the QPB-specific `phase`/`step`), the mechanical `{HARNESS_BIN}`
   placeholder closing the transcription hazard (FR-21a), the specifiable
   `heartbeat_path` (FR-20), the `LAUNCH-FAIL` diagnostics (FR-21b). This is
   what makes the core repo-independent and ready to extract.

## Validation evidence map

| Claim | Status | Evidence |
|---|---|---|
| Autonomous multi-tick loop; idle ticks survive | VERIFIED | 3 Sonnet spike passes (`spike-evidence.md`) |
| Pool + staggered dispatch, multi-entry | VERIFIED | Item-11 E2E run-dir `20260611T191325Z` |
| Low-reasoning-model orchestration | VERIFIED | Haiku 4.5: one clean autonomous-loop pass + one observed failure path (2026-06-11) |
| Detached workers outlive the dispatch turn | VERIFIED | Instruction-003 dry-run (pgrep + heartbeat) |
| Agent honors STOP from prose | VERIFIED | Spike pass 3 (STOP mtime vs tick time, state untouched) |
| Idempotency / cycle-only re-tick | VERIFIED | Unit suite (mutation-verified) + 002/003 |
| Encoding / cp1252 safety | VERIFIED | AST sweeps, mutation-verified |
| No-admin floor (ticker, shell, macOS) | VERIFIED | Live demo 2026-06-12, independently reproduced |
| In-session loops can die silently (Class C) | ROOT-CAUSED | Instruction-011 transcript forensics, 4 drops (below) |
| Cadence 2 (cron), Windows/Linux ticker, Codex/Copilot/Cursor | DESIGNED | Unit-tested; cross-host matrix pending (v0.2) |

## Known platform issues

### Class C — silent in-session loop death (root-caused 2026-06-12)

The single most important operational fact. On Claude Code 2.1.174, an
in-session autonomous loop (rung 1) dropped 4 times in one session (gaps of
9h15m, 2h26m, 1h22m, 2h06m — one previously unnoticed).

- **The timer is reliable.** `scheduled_task_fire` events are present at every
  scheduled second — the wakeup fired 4/4. This is *not* a timer failure and
  *not* a "forgot to reschedule" prose failure (the prior tick always
  rescheduled — that's why the wakeup fired).
- **The failure is in the resumed turn.** It intermittently serializes its
  first tool call into the *text* channel as literal `<invoke name="…">…`
  markup (with a stray token prefix) instead of a structured tool call.
- **The retry asymmetry decides life or death.** When that text carries
  `stop_reason: tool_use`, the host detects a malformed call and injects a
  retry → the loop self-heals (4/4 of those survived). When it carries
  `stop_reason: end_turn`, the host sees a clean text completion, injects no
  retry, and the loop dies silently until a human nudges it (4/4 deaths).
- **Compaction is refuted.** The session's single compaction postdates the
  last recovery; 0/4 drops follow one (E7 disproven).
- **Model data (weak signal, not proof).** All 4 drops occurred in the
  v1.5.9 runner worker session, which ran on **Opus 4.8**; the (different,
  shorter) Sonnet and Haiku validation sessions did not surface this death.
  Absence in those runs is not proof of immunity — the sample is tiny and the
  failure is intermittent. Precautionary guidance until the upstream fix
  lands: **prefer a Sonnet-class model for long unattended rung-1 loops**,
  and in all cases deploy the safety tick (which fixes it regardless of
  model).
- **Mitigations.** (1) The **FR-26a safety tick** — an external `--once` tick
  is independent of the in-session turn and rescues every Class-C death
  within one safety interval, no detection logic. (2) Candidate in-band fix:
  a Stop-hook (or host fix) that treats "assistant text containing
  `<invoke name=` + `end_turn` + no tool_use" as malformed and injects the
  existing retry — would convert every observed death into the self-heal
  path. (3) Upstream: **anthropics/claude-code#67945** (filed 2026-06-12),
  related to the **#49747** issue family on scheduled-wakeup / resumed-turn
  reliability.
- Full forensics with quoted transcript evidence:
  `outputs/011-loop-drop-self-forensics.md` (in the QPB runner record).

### Lesser issues

- **Synced folders.** Run directories on OneDrive/Dropbox-style synced paths
  are unsupported; pre-flight warns (E4, FR-29, NFR-10). Use local disk.
- **Orphan-on-STOP.** STOP does not kill in-flight detached workers; they run
  to their own terminal states (documented; no kill semantics this release).
- **Window-stays-open.** Rungs 1 and 3 require the session/window to stay open
  for the run's duration (C-3); rung 2 (scheduler) does not.

## Deferred roadmap

- **v0.2:** native Copilot `/every` cadence; Codex/Cursor per-host validation
  matrices; shell-dispatch hardening; the cross-rung × cross-host validation
  matrix that turns DESIGNED cells into VERIFIED (NFR-12).
- **Later:** A2A / cross-machine transport (the schemas are already A2A-ready —
  every line carries `task_id` + `schema_version`); a `--max-quiet` watchdog
  beyond the printed-command recovery; per-phase stall thresholds.

## Development process

- **Verify, don't recall.** Every command/flag/field in docs and code is
  checked against the shipped source. The requirements doc is the spec; cite
  `FR/NFR/UC` numbers.
- **Council review on landed code.** Substantial changes get a multi-panelist
  review (independent fresh-context reviewers, each with a charter:
  technical accuracy, requirements traceability, adopter/honesty) that runs
  against the *committed* diff and iterates to a SHIP verdict before the work
  is reported. This has caught ship-blockers a single pass would have missed.
- **The orchestrator/worker runner pattern** is available for large multi-step
  work: a chat orchestrator files numbered instructions; a coding worker
  executes each and writes a matching output; disk is the record. (It is also
  how this repo's later instructions were executed — and where the Class-C
  drops were observed.)
- **Publish gates.** Releases are gated: clean-clone cold build, built-artifact
  end-to-end test in a throwaway environment, dry-run before any live upload
  (FR-33).

## Open questions

- Whether the in-band Class-C Stop-hook fix belongs in the harness or is
  purely an upstream host concern.
- The exact safety-tick cadence default to recommend (currently ~3× the plan
  cadence).
