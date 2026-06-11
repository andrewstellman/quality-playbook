# Quality Playbook v1.5.9 — Harness Skill Implementation Plan

*Companion to: `QPB_v1.5.9_Harness_Skill_Design.md` (the harness sub-design) and `QPB_v1.5.9_Implementation_Plan.md` (the v1.5.9 umbrella plan, which owns Phase 0 branch hygiene, the SKILL.md-trim workstream, and the release ship sequence). This file owns the harness-as-skill workstream: Phase 1 (1A spike → 1B.0 → 1B).*

*Status: split out of `QPB_v1.5.9_Implementation_Plan.md` on 2026-06-10 to mirror the design-doc split — the harness already had its own sub-design (`QPB_v1.5.9_Harness_Skill_Design.md`); now it has its own sub-plan. Phase 1 content carried over verbatim. Architecture history: drafted 2026-06-06; revised 2026-06-09 to the in-session `ScheduleWakeup` polling architecture (the prior daemon-architecture work is preserved on `archive/1.5.9-daemon-architecture` and rebuilt-not-cherry-picked here — see scope note (F) and the daemon-archive note at the end); revised 2026-06-10 to add Phase 1B.0 (phase-identity source of truth + unified emission), sequenced first within 1B after the 1A spike.*

*Authored under explicit operator carve-out from the default "QPB source files are propose-don't-edit" rule.*

---

## Operating context

- This file owns the **harness-as-skill** workstream only (Phase 1: 1A spike → 1B.0 → 1B). Phase 0 (branch hygiene), the **SKILL.md-trim** workstream, the overall sequencing, and the **release ship** sequence live in the umbrella `QPB_v1.5.9_Implementation_Plan.md`.
- The two v1.5.9 workstreams are independent and share no files; either can ship first, both must ship before the tag.
- **Worker-lane edits** for all source changes (`SKILL.md`, `bin/`, `references/`, `.github/skills/`, schemas, tests). Cowork files instructions; the worker implements; Council reviews.
- **Per-workstream Council review** (Self-Council Protocol 1) at completion.

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
- Observe 3-4 ticks fire on `ScheduleWakeup` cadence, **including at least one idle tick** — a tick where the dispatched worker is still `IN_PROGRESS`, `harness_status.json` counts are unchanged from the prior tick, and the agent reschedules anyway (this is the watcher death mode the spike exists to test). After each tick, capture `harness_status.json` (incl. its `cycle` counter), the heartbeat tail for the dispatched run, and the agent's stdout (status table + ScheduleWakeup call).
- The script's `done` flag flips when the worker emits a terminal sentinel; agent prints final summary, does NOT call ScheduleWakeup, exits cleanly.
- Operator writes a STOP file during tick 2 of a separate mini-run to verify clean stop semantics.
- Forced re-tick (operator says "run another tick now") shows **no change in harness_status.json except the `cycle` counter** — idempotency check (no double-dispatch, no double-move, no state/count change). A true "empty diff" is impossible by design: `cycle` increments on every tick because it is the idle-tick witness. (Spike-confirmed: the implementation resolves this exactly so.)

**Possible outcomes (three-state — confirmed 2026-06-10; re-evaluate the whole framing after the spike runs):**
- **PASS:** the run reaches `done=true` autonomously (zero operator re-prompts) with ≥ 1 observed idle tick, the STOP mini-run halts cleanly, and the forced re-tick is a no-op. The architectural premise holds; Phase 1B is straightforward thickening of the production-shaped surface.
- **FAIL (assumption falsified):** any non-terminal tick ends without `ScheduleWakeup`, OR the loop needs an operator re-prompt to advance, OR it never reaches `done`. Strict: one dropped reschedule on a non-terminal tick = FAIL — that single drop IS the watcher death mode. The failure mode names the 1B fix (agent doesn't reliably invoke ScheduleWakeup → sharper SKILL.md structure; extra reasoning between script calls → smaller/stricter script; A-3 leak → tighter return contract). Script-and-prose are small enough that pivoting is cheap.
- **FIX-REQUIRED in 1B (core holds, secondary cracks):** the loop self-advances to `done` autonomously, but a secondary property misbehaves — idempotency re-tick mutates state, STOP doesn't halt cleanly, or the agent does extra reasoning yet still completes. Doesn't falsify the core loop; names a specific 1B hardening.

**Re-evaluate post-spike (operator, 2026-06-10).** This threshold and the PASS/FAIL framing itself are provisional. The spike's actual behavior may show the line is drawn wrong — e.g. a transient single miss that self-recovers on the next *scheduled* tick (no re-prompt) may warrant tolerance the strict rule doesn't yet allow. Revisit with the operator once the run output is in hand, before this hardens into the 1B acceptance contract.

**RESOLVED — PASS (2026-06-11).** Three validation passes on Sonnet (Claude Code 2.1.173): pass 1 — full autonomy, 4 ticks, 2 genuine idle ticks, clean self-termination on `done`, zero re-prompts; pass 2 — independent reproduction of the autonomy result (its STOP arrived post-completion, inconclusive on STOP only); pass 3 — agent-honored STOP: stop tick observed, halted without rescheduling, state untouched. Zero dropped reschedules across 9 non-terminal ticks, so the strict threshold required no tolerance and **stands as written for the 1B acceptance contract**. Full evidence: `spike/v1.5.9_phase_1A/spike-evidence.md` (incl. three non-blocking 1B observations: dispatch-tool naming Task-vs-Agent, terminal-tick status-table cosmetics, no kill semantics for in-flight workers on STOP).

**Spike NOT subject to worker self-Council.** The artifact is ≤300 lines; Council is theater at this scale. The empirical result (the run output) is the verdict.

#### Phase 1A scope notes — resolved decisions before the chat starts

These resolve specific gaps that would otherwise cost the implementing chat its first turn to re-derive.

**(A) `ScheduleWakeup` invocation.** It's documented empirically in `ai_context/WATCHER_PROMPT.md` — `ScheduleWakeup(now + N minutes)` — as the load-bearing primitive. The watcher has weeks of evidence it works inside Claude Code; how Claude Code recognizes and acts on the call is opaque from the prose, but it does. The spike SKILL.md prose uses the same form. **If the spike's first tick demonstrates that the primitive isn't being invoked correctly OR doesn't fire the next tick, that failure mode IS the spike's deliverable** — we'd discover empirically what the watcher has been relying on. Don't try to "verify" the primitive's existence in code before running the spike; the spike IS the verification.

**(B) Where the spike's files live.** The spike works in a temporary directory in the work tree, NOT in the production `plugins/quality-playbook-harness/...` paths. Suggested location: `spike/v1.5.9_phase_1A/` at the repo root. Contents: `qpb_harness_tick.py`, `harness-spike-SKILL.md` (NOT named `SKILL.md` to avoid plugin-discovery confusion if any tool scans for SKILL.md files), `spike_plan.json`, `BOOTSTRAP_PROMPT.md`, `spike-evidence.md`. The spike directory is committed ONLY if Phase 1A SHIPs; if it fails, the directory is preserved in the work tree as diagnostic context but not committed (or committed to a `archive/spike_v1.5.9_phase_1A_failed` branch for posterity). The production plugin layout (`plugins/quality-playbook-harness/...`) is built fresh in Phase 1B based on what the spike learned — not by promoting spike files in place.

**(C) Worker-side heartbeat for the spike.** The spike's worker emits heartbeats via plain bash, NOT via `qpb_heartbeat.py` (which doesn't exist on this branch and is a Phase 1B deliverable). **The worker must outlive its dispatch turn so the loop sees idle ticks (see (D)),** so the Task subagent launches a *detached* background process (`nohup … &`) and returns immediately with a one-line summary (per Council A-3 — no heartbeat content echoed). The detached process appends, append-only, to the absolute `HEARTBEAT_PATH`: one `STARTING` line, then an `IN_PROGRESS` line every few minutes for ~10–12 minutes, then a terminal `COMPLETED` line carrying `result_file`, and writes a one-line `result_file`. Each line is a single literal JSON object (`{"ts": …, "task_id": …, "schema_version": "1", "phase": "stub", "step": …, "status": …}`); the exact quoting/escaping is instruction 001's to settle. The harness tick script reads the tail via `Path.read_text().splitlines()[-N:]` — no schema validation, just a substring match on `STARTING` / `IN_PROGRESS` / `COMPLETED` to drive state transitions. Schemas and validators land in Phase 1B.

**(D) Stub worker, not real QPB — but it must produce an idle tick.** The spike's worker is a stub (no QPB on a real target). It emits `STARTING`, stays observably in progress across at least one full tick interval by emitting `IN_PROGRESS` lines over ~10–12 minutes from its detached background process (see (C)), then emits a terminal `COMPLETED` sentinel and writes a one-line `result_file`. **Why detached/long-lived rather than immediate-complete:** the riskiest piece of the architecture is the watcher death mode — a tick that finds nothing to advance and forgets to reschedule (`WATCHER_PROMPT.md`: *every* tick must end with `ScheduleWakeup`, including idle ticks). An immediate-complete stub finishes during its dispatch turn, so the loop never experiences an idle tick, and the spike would validate dispatch + reap + done while never exercising the one thing most likely to break. The detached, multi-tick stub is the minimum needed to make "the loop survives an idle tick" falsifiable. The spike still tests the orchestrator loop ONLY — real-QPB-under-Task validation (and how a long real run behaves under `Task`) lives in Phase 1B. Mixing the two questions in the spike conflates the failure surface.

**(E) Spike evidence capture format.** A single file `spike/v1.5.9_phase_1A/spike-evidence.md` with this structure:

```
# Phase 1A spike evidence

## Run setup
- date/time spike started, host CLI version, plan file path

## Tick 1
- Operator prompt that triggered tick 1 (the bootstrap)
- Agent's stdout, verbatim (status table, any tool calls, ScheduleWakeup call)
- `harness_status.json` AFTER tick 1 (incl. `cycle` counter; flag idle = worker IN_PROGRESS & counts unchanged from prior tick)
- `heartbeat.ndjson` contents AFTER tick 1
- Time of next-tick fire (observed)

## Tick 2
- (same shape)

## Tick 3..N
- (same shape)

## Idle-tick check
- Which tick(s) were idle (worker IN_PROGRESS, no state change) and confirmation each one still ended with ScheduleWakeup — this is the load-bearing observation

## Idempotency check
- Forced re-tick command + diff of harness_status.json (expect no change except the `cycle` counter)

## STOP semantics check
- STOP file write timing + observed tick behavior

## Verdict
- SHIP / FIX-REQUIRED with named failure mode
- If FIX-REQUIRED, specific recommendation for what to change in Phase 1B
```

No worker self-Council, no panelist files, no synthesis. The evidence file IS the artifact.

**(F) Archive branch is reference-only.** The implementing chat MAY run `git show archive/1.5.9-daemon-architecture:<path>` to read the daemon-arc's `bin/qpb_heartbeat.py` (clean stdlib implementation), heartbeat schema, worker SKILL.md heartbeat section, and `bin/tests/test_harness_*.py` patterns for reference. Pattern reuse — "the daemon arc's heartbeat helper used `O_APPEND` and `--mode-a-noop` for these reasons" — is fine and good. Literal cherry-pick (importing the file) is NOT — the daemon arc embedded architectural assumptions that don't apply to ScheduleWakeup. Reference the archive for prior art; rebuild for the new architecture.

**(G) Plan schema for the spike.** Single entry, three fields:

```json
{
  "tick_interval_minutes": 5,
  "entries": [
    {
      "task_id": "<uuid>",
      "target_repo": "<absolute path>",
      "dispatch_mode": "subagent",
      "worker_prompt": "<literal Task prompt with HEARTBEAT_PATH, TASK_ID, RUN_DIR, TARGET_REPO absolute-path block per Council A-2; launches the detached stub per (C)/(D)>"
    }
  ]
}
```

No `pool_size` (defaults to 1 for a one-entry plan). No `stall_threshold_minutes` (no stall detection in spike). No `early_warn_minutes`. No optional fields. Schema validation is not enforced — the harness tick script reads these fields directly via `json.load`.

**`cycle` and the state counts are runtime state, not plan input.** They live in the `harness_status.json` the tick script writes each tick — NOT in this plan-input schema. The `cycle` counter (already implied by the design's worked-example status table, e.g. `(cycle 1)`) is incremented once per tick and is the on-disk witness that multiple ticks fired; the PASS criterion's "≥ 1 idle tick / multi-tick advancement" is read off `cycle` + the unchanged counts + the `heartbeat.ndjson` `IN_PROGRESS` lines. No formal schema for `harness_status.json` in the spike (instruction 001's tick script owns its shape); a schema test for it is a 1B concern.

**(H) What "≤ 300 lines" counts.** Counts: `qpb_harness_tick.py`, `harness-spike-SKILL.md`, `spike_plan.json`, `BOOTSTRAP_PROMPT.md`, and `spike-evidence.md` cumulative. Does NOT count: the worker prompt's bash commands (literal strings inside the prompt count toward SKILL.md but not as separate files), evidence captures inside `spike-evidence.md` from the run (those are observed output, not authored lines). The ≤300 is a **target, not a hard gate** (operator, 2026-06-10): if the total approaches or exceeds it, that's a signal the spike may be over-shaped — the worker reports the cumulative line tally and flags it rather than blocking, and proceeds unless the overage looks structural (in which case stop and ask).

### Phase 1B.0 — Phase-identity source of truth + unified emission (foundational; filed first in 1B)

**Why this is its own step, and why it's first in 1B.** The whole agent-based harness acts on the worker's *current phase*: the tick script reads the heartbeat to decide running / stalled / completed. If the heartbeat's phase, the `::QPB::` sentinel, and the `run_state.jsonl` events derive their phase from independent copies of the number→name table, they drift, and a drifted heartbeat makes the state machine act on the wrong fact. So before any real heartbeat work lands, the phase identity must come from one shared definition that everyone reads. This is **not** in the 1A spike: the spike's stub worker emits a hardcoded `"phase": "stub"` and never exercises real phase identity, so folding it in would add shipped-skill blast radius the spike can't even validate (and would conflate the spike's single failure surface). It lands immediately after the spike proves the loop, and before the real `qpb_heartbeat.py`, the worker SKILL.md heartbeat section, and the gate invariants build on it.

**Decisions (2026-06-10 planning session — canonical text in `QPB_v1.5.9_Harness_Skill_Design.md` → "Phase-identity source of truth"):**

1. **One shared phase-identity definition.** Extract the number→canonical-name table (`0:validation … 6:verification`) and the "what phase is this run in" helpers out of `qpb_phase.py` into a single shared module under the QPB skill's `scripts/`. `qpb_phase.py` (sentinel emitter), `qpb_heartbeat.py` (new), and the run-state writers all *import* it. No copy of the table exists anywhere else. "Single source of truth" means one shared definition, not one function that does everything — the emitters stay separate code reading the same truth.

2. **`run_state.jsonl` is the canonical run position; the sentinel and the heartbeat are projections.** Neither the `::QPB::` sentinel nor `heartbeat.ndjson` computes a phase independently. A thin phase-transition facade, on a boundary, (a) appends the run-state event, (b) emits the `::QPB:: kind:"phase"` sentinel, and (c) — only when `HEARTBEAT_PATH` is set (worker running under the harness) — appends a heartbeat line, all keyed off the shared identity from (1). Separate code behind one facade.

3. **The mandatory ~3-min keepalive reads its phase from `run_state.jsonl`.** The keepalive is a mid-phase liveness ping with no boundary and no sentinel, so it can't be a side effect of a transition. It reads the current phase from run-state (the canonical position) and reports that — so even the ping's phase derives from the same truth and can't drift.

4. **The `::QPB:: kind:"gate"` sentinel shares the envelope formatter only, not the phase identity.** `quality_gate.py`'s gate-verdict sentinel is a *result*, not a pipeline position, and `bin/run_playbook.py` (Mode B, which survives the harness deletion) parses it for the verdict. Unify only the one-line `::QPB:: {v:1,…}` envelope-writer so there's a single writer of that line shape; leave the gate's payload (`kind:"gate"`, `gate_result`) as its own emission. Same envelope source of truth, different payload.

**Blast radius (touch in lockstep — `test_install_manifest_no_drift.py` fails loudly otherwise).** Extracting the phase-identity table and any rename of `qpb_phase.py` moves these together:

- `INSTALL_CLOSURE` in `bin/qpb_validate.py` (the Phase 0 validator's bundle manifest — currently pins `bin/qpb_phase.py`)
- `_bundle_files()` in `install_skill.py` (the installer bundle set)
- `_FLAT_LAYOUT_BUNDLED_BIN_FILES` in `run_state_lib.py` (flat-layout snapshot guardrail)
- `bin/tests/test_install_manifest_no_drift.py` (asserts the first three agree byte-for-byte)
- `bin/tests/test_phase_sentinel_109.py` (the `qpb_phase` unit tests)
- `bin/run_playbook.py` `::QPB:: kind:"gate"` parsing (verify the envelope-writer change leaves verdict-reading intact)

*Implementation finding (1B.0, d9c85a3): the actual radius for adding a bundled bin module is LARGER than the six items above — three more enumeration surfaces moved in lockstep: the `AGENTS.md` install `cp` recipes (both the `.github` and `.claude` layout blocks) and `repos/setup_repos.sh`'s benchmark-bundle copy. The test suite caught all three. Any future bundled-module addition should treat these nine surfaces as the lockstep set. Also verified during implementation: `run_playbook.py`'s verdict reader anchors on the `RESULT: GATE …` prose line and deliberately ignores the `::QPB::` sentinel (v1.5.7 109 fix), so the envelope unification carries no parsing risk.*

**Deliverable + gate.** The shared phase-identity module + the unified phase-transition facade + the keepalive-reads-run-state behavior, landed with the lockstep manifest/test updates, plus a regression test asserting that a `::QPB::` sentinel, a run-state `phase_start`, and a heartbeat line emitted for the same boundary all report the identical `(number, name)` pair. Own **Self-Council Protocol 1** review (three panelists: (A) phase-identity no-drift correctness, (B) run-state-as-canonical-position + facade correctness, (C) blast-radius / manifest / drift-test completeness) — because this refactors *shipped, adopter-facing, gate-relevant* instrumentation, a distinct blast radius from the harness-skill scaffolding.

### Phase 1B — Production hardening (instruction 2)

Conditional on Phase 1A producing a successful spike, and sequenced after Phase 1B.0 lands the shared phase-identity foundation. Only files after the spike's evidence is captured. Contents depend on what 1A learned. Likely shape:

- Expand `qpb_harness_tick.py` to handle full state machine: stall detection, AUTH_OR_LAUNCH_FAILED (if Mode 1 dispatch fails), terminal FAILED status, idempotency invariants, error logging.
- Expand harness SKILL.md prose with the loop-continuation discipline checklist verbatim (mirroring the watcher prompt's "EVERY tick MUST end with ScheduleWakeup" section).
- Build out the second plugin properly (`plugins/quality-playbook-harness/.claude-plugin/plugin.json`, marketplace.json catalog entry, schemas, references including STATE_MACHINE.md).
- Add `bin/tests/test_qpb_harness_tick.py` — stdlib-only unit tests for state-machine transitions, idempotency, JSON output shape, double-tick safety.
- Add `quality_gate.py` invariants for the schemas (carry forward Council A-1, C-3, A-2 disciplines from the original v1.5.9 review).
- Re-validate end-to-end against a 2-3 entry plan; capture evidence.

#### Phase 1A spike carry-forwards (logged 2026-06-11 from the spike dry-run + Council)

These came out of the 1A apparatus dry-run and the 3-panelist sub-agent Council (instruction 003; synthesis was in the gitignored `runner/1.5.9/reviews/003-spike-council/`, captured here so it survives). All are **non-blocking for the 1A spike** and become 1B requirements:

- **Settled, not a carry-forward — the Mode-1 dispatch premise holds.** The dry-run confirmed conclusively (real `pgrep` + heartbeat evidence) that a `nohup`-detached worker launched by a `Task` subagent **survives the subagent's turn ending** and keeps emitting heartbeats across many orchestrator ticks. No stub/worker-detachment rework is needed in 1B; the architecture's core "orchestrator observes worker via heartbeat across idle ticks" premise is mechanically sound.
- **JSON-encode injected values in the heartbeat emitter (Council B-F3/F4).** The spike stub builds heartbeat lines with bash `printf '%s'`, which is fragile: a `task_id` containing a literal `%` would be misread as a format specifier, and a value containing `"` or `\` would emit invalid JSON. Safe for the spike's UUID/clean-path inputs; **the production `qpb_heartbeat.py` (1B) MUST JSON-encode values rather than `printf` them.**
- **Guard the reap transition (Council A-F6).** The spike tick reap sets `state="completed"` even when the claimed job file is externally absent (benign at `POOL_SIZE=1` fixed-plan). Production multi-entry/multi-pool state machine should guard this transition.
- **Carry the loop-continuation discipline verbatim + reconcile prose (Council C-1/2/3/6).** The production harness SKILL.md must include the "EVERY tick ends with ScheduleWakeup OR a clean exit" discipline verbatim, and the minor step-ordering/STOP-phrasing desync between the spike's `BOOTSTRAP_PROMPT.md` and `harness-spike-SKILL.md` should be reconciled when promoting to the production SKILL.
- **Invocation hygiene (incidental).** Invoke the tick script directly (`python3 <path>/qpb_harness_tick.py <run-dir>`), never wrapped in an unquoted shell variable (zsh doesn't word-split it). The spike prompts already do this; preserve it in the production SKILL.

### Phase 1B sub-Council

After Phase 1B lands its commit:

- Worker self-Council Protocol 1 with three panelists: (A) state-machine correctness + idempotency, (B) SKILL.md prose reliability + ScheduleWakeup discipline, (C) cross-skill schema consistency + validator coverage.
- All Open Questions from the harness sub-design either resolved or explicitly MVP-deferred with documented rationale.
- End-to-end validation evidence captured in the worker's review-request file.
- `bin/harness/` Python code marked for deletion (commit message notes the deletion plan; actual `rm` happens after a buffer period to allow rollback).

---

## Harness sequencing

Within this workstream the order is **1A spike → 1B.0 (phase-identity source of truth) → rest of 1B**. 1B.0 is foundational — the real `qpb_heartbeat.py`, the worker SKILL.md heartbeat section, and the gate invariants all build on the shared phase-identity definition it lands. The harness workstream as a whole is parallelizable with the umbrella's SKILL.md-trim workstream; see the umbrella plan's sequencing summary.

---

## Open work-items (harness workstream)

*Item numbers are **plan-local** (the umbrella plan has its own 1–8 tracker for trim + release) — always name the plan when cross-referencing a work item.*

| # | Item | Phase | Status |
|---|------|-------|--------|
| 1 | Tracer-bullet spike: minimal `qpb_harness_tick.py` + minimal harness SKILL.md + bootstrap prompt + 1-entry plan + empirical 3-4-tick validation | 1A | **DONE — PASS (2026-06-11).** Three passes on Sonnet; zero dropped reschedules; agent-honored STOP. Evidence: `spike/v1.5.9_phase_1A/spike-evidence.md` |
| 2 | Production-shaped `qpb_harness_tick.py` (full state machine, idempotency, error handling) | 1B | **DONE (2026-06-11, `a1bbfdd` + `45278af` P2 hardening).** Orchestrator-side, not bundled. 20+ tests, pins mutation-verified. |
| 3 | Production harness SKILL.md prose (loop-continuation discipline, full status table, dispatch contract) | 1B | **DONE (2026-06-11, `00d5c6a`).** Loop discipline verbatim; Task/Agent dispatch naming; invocation hygiene; panelist B traced all exit paths leak-free. |
| 4 | Second-plugin scaffolding (`plugins/quality-playbook-harness/.claude-plugin/plugin.json` + marketplace.json catalog entry + schemas + references) | 1B | **DONE (2026-06-11, `00d5c6a`).** plugin.json + marketplace entry + 4 schemas + STATE_MACHINE.md + BOOTSTRAP_PROMPT.md + example plan. |
| 5 | **Phase-identity source of truth + unified emission**: shared number→name module (extracted from `qpb_phase.py`); `run_state.jsonl` as canonical position; thin facade emits run-state event + `::QPB::` sentinel + (under harness) heartbeat from one identity; ~3-min keepalive reads phase from run-state; `kind:"gate"` sentinel shares the envelope writer only. Lockstep: `INSTALL_CLOSURE` / `_bundle_files()` / `_FLAT_LAYOUT_BUNDLED_BIN_FILES` / `test_install_manifest_no_drift.py` / `test_phase_sentinel_109.py` / `run_playbook.py` gate parsing (+3 discovered surfaces, see blast-radius note). | 1B.0 | **DONE (2026-06-11, `d9c85a3`).** `phase_identity.py` single source; facade + keepalive landed; Council unanimous SHIP; cross-surface regression test mutation-verified (worker two axes + orchestrator independent re-run). Unblocks items 6/7/9. |
| 6 | `bin/qpb_heartbeat.py` worker-side helper (NET-NEW; reads phase identity from item 5's shared module, never a copy) | 1B | **DONE (2026-06-11, `ef925cd`).** JSON-encoded values (CF-1), O_APPEND, keepalive-reads-run-state, Mode-A no-op. Bundled — full 9-surface lockstep, closure count 59. |
| 7 | QPB worker SKILL.md heartbeat emission section (phase field sourced via item 5) | 1B | **DONE (2026-06-11, `ef925cd`).** Bounded additive section (keepalive/error/terminal under harness). Live-pipeline facade wiring deliberately deferred — exceeds docs-sanctioned 1B prose scope; candidate for a later step. |
| 8 | Heartbeat schema byte-identical copies on both sides | 1B | **DONE (2026-06-11, `ef925cd`).** Byte-identity test-pinned + mutation-verified (worker + orchestrator `cmp` re-check). |
| 9 | `quality_gate.py` invariants for harness schemas | 1B | **DONE (2026-06-11, `5dbd1bf`).** `check_heartbeat_sidecar`, non-blocking warn (C-3 / A-1); A-2 enforced dispatch-side. `bin/harness/` marked for deletion in same commit (not removed — gated on item 11). |
| 10 | `bin/tests/test_qpb_harness_tick.py` — unit tests for state machine + idempotency | 1B | **DONE (2026-06-11, `a1bbfdd`).** Hermetic (`QPB_HARNESS_NOW` / `QPB_HARNESS_RUNS_DIR`); stall/idempotency/reap-guard pins mutation-verified. |
| 11 | End-to-end validation run with operator-driven 2-3 entry plan | 1B Ship Gate | **DONE — PASS (2026-06-11).** 3-entry stub plan (`testing/e2e_stub_plan.json`), pool 2, Sonnet, run-dir `20260611T191325Z`: 5 ticks autonomous, ≥2 idle ticks rescheduled, **staggered dispatch observed** (run-03 dispatched on run-01's reap tick, stub launch times 19:13 vs 19:23 UTC), 3/3 completed with valid terminal sentinels, clean `done` exit with terminal-table cosmetics correct. Stubs exercised the real `qpb_heartbeat.py` end-to-end. **1B Ship Gate CLOSED — `bin/harness/` deletion unblocked.** |

**Note on the daemon-architecture archive.** Instructions 210, 211, 211-followup-1, and 213 landed on `archive/1.5.9-daemon-architecture`. They contain working artifacts (worker-side heartbeat helper, schemas, worker SKILL.md heartbeat prose, validators) that are conceptually portable to the new architecture. They are NOT cherry-picked because the architectural mistakes (MCP scheduler, then daemon scheduler) were embedded throughout that scaffolding and the cleaner path is to rebuild on the new substrate. Some prose and code patterns will be re-used in spirit; nothing is moved in literal form.

---

*End of Harness Skill Implementation Plan. Harness sub-design in `QPB_v1.5.9_Harness_Skill_Design.md`. v1.5.9 umbrella plan (Phase 0 + SKILL.md trim + release) in `QPB_v1.5.9_Implementation_Plan.md`. Umbrella design in `QPB_v1.5.9_Design.md`.*
