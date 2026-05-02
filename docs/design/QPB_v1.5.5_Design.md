# Quality Playbook v1.5.5 — Design Document

*Status: drafted 2026-05-02 immediately after v1.5.4 ship. Implementation begins on the `1.5.5` branch (created from `v1.5.4` tag at commit `8ccd460`).*
*Authored: 2026-05-02*
*Owner: Andrew Stellman*
*Depends on: v1.5.4 shipped (role map + Phase 5 regression-replay apparatus + Pattern 7 + ai_context/CALIBRATION_PROTOCOL.md + ai_context/DEVELOPMENT_PROCESS.md + docs/process/Lever_Calibration_Log.md)*

> **Where v1.5.5 sits in the arc.** v1.5.4 shipped the *measurement substrate* for continuous improvement (cell.json schema, recall computation, calibration protocol, first cycle). It also surfaced that the *orchestration substrate* — what actually runs a calibration cycle from end to end — is missing. The v1.5.4 cycle 1 was executed by a human-in-the-loop Cowork session with substantial manual coordination, and the autonomous-loop attempt halted on Cowork's sandbox runtime constraints (state-file UID locking, host-only paths, subprocess survival). v1.5.5 closes that gap. After v1.5.5, a single AI session can run a full calibration cycle — pre-lever baselines, lever change, post-lever measurement, cross-benchmark check, audit and log writeup — without operator intervention beyond the initial kickoff. v1.6.0 then begins on the QI-half feature work (Requirements Review) on top of an automated improvement loop substrate.

---

## Motivation

### v1.5.4 cycle 1 surfaced the orchestration gap

The Pattern 7 calibration cycle (chi-1.3.45, 2026-05-01) produced a real measured recall improvement (+0.20) and a clean Council review of the lever change. It also produced four cycle findings (C-1 through C-5 in `Calibration Cycles/2026-05-01-chi-1.3.45/audit.md`) where the protocol assumption broke down against the actual runtime:

- C-1: pre-flight check #3 fails for benchmark targets (`repos/` is gitignored).
- C-2: pinned-benchmark archive doesn't always have the version expected (express-1.5.1 missing → fallback to express-1.3.50).
- C-3: SKILL.md hardcoded "six bug-finding patterns"; without a follow-on edit, Pattern 7 was silently neutered.
- C-4: Cowork-environment cycles converge on argument-based validation by design (45 s bash-tool timeout precludes blocking on ~30-min playbook subprocess).
- C-5: cross-benchmark comparison shape mismatch (post-lever vs. historical baseline confounds lever effect with cross-version drift).

Beneath those: the cycle was executed by a Cowork session walking each step manually, with the operator (Andrew) coordinating between the AI session running Phase 1-3 reasoning and the operator's own host shell running playbook subprocesses. This worked for cycle 1 — but it does not scale to the multi-cycle calibration cadence the QI half (v1.6.0 onward) requires.

### The autonomous-loop attempt failed for runtime reasons, not design reasons

A scheduled-task-driven autonomous loop was set up after cycle 1 (state file `/tmp/qpb-loop-state.txt`, 15-min cron, stage machine A→F). It produced zero useful work before halting on three architectural mismatches (documented in `Calibration Cycles/2026-05-01-chi-1.3.45/audit.md` "Empirical-validation tick — HALTED"):

1. State file UID-locked across ticks (each scheduled tick gets a different sandbox UID).
2. Launch command used host-only paths (`/Users/...`); inside the sandbox, the QPB repo is at `/sessions/<session>/mnt/QPB`.
3. Background subprocesses don't outlive the 45 s tick.

These are properties of the scheduled-task runtime model, not bugs in the loop logic. The right answer is to *not use that runtime model* — automate the loop in a way that the AI session driving the loop is also the AI session doing the work.

### The right architecture: state IS the filesystem; one AI session runs the cycle

Replace the scheduled-task / external-state-file model with two principles:

1. **State is the filesystem.** Every meaningful event during a playbook run gets logged to `quality/run_state.jsonl` (machine-readable, append-only) and reflected in `quality/PROGRESS.md` (human-readable, atomically rewritten). Anyone (the AI itself, a sub-agent monitor, the operator, a future session) reading those files knows exactly where the run is. There is no separate state file in `/tmp/`, no lock file, no UID-locked artifact.
2. **One AI session runs the cycle.** A single Claude Code session loops through the cycle's benchmark list, runs each playbook end-to-end, applies the lever change between pre- and post-lever runs, computes deltas, writes the cycle audit and calibration-log entry. No scheduled tasks. No 45 s tick boundaries. The session is long-running but stateless across crashes — if it dies, the next session reads the state files and resumes.

Both principles are enabled by the file-tool layer the AI uses: `quality/` is in the bind-mounted workspace owned by the user; the file tools write through it without going through the per-tick UID-restricted bash-sandbox layer. No `/tmp/`, no UIDs, no locks.

### Why this is one release, not woven into v1.6.0

Three reasons v1.5.5 stands alone:

1. **The orchestration substrate is itself a deliverable.** Run-state instrumentation, cross-validation rules, resume semantics, and the orchestrator prompt are enough engineering work to deserve their own design, implementation, Council review, and tag. Bundling them into v1.6.0 alongside Requirements Review feature work would conflate substrate-building with substrate-using.
2. **v1.6.0's calibration cycles need this.** Requirements Review (the v1.6.0 headline feature) generates per-session defect data that feeds back into Phase 1/2 prompt-tuning calibration cycles. Those cycles need the autonomous orchestration v1.5.5 builds. Shipping v1.5.5 first means v1.6.0's calibration cycles run on a tested substrate rather than co-developed with one.
3. **The first test is sitting there.** v1.5.4's Pattern 7 cycle has a real, named open question — recover the PathRewrite + AllowContentEncoding displacement losses while preserving Pattern 7's wins. That's exactly the shape of test the autonomous loop is built for, and running it validates the v1.5.5 substrate on a target where the answer space is known.

---

## Scope

### Core deliverables

1. **Run-state instrumentation in `SKILL.md`** — the playbook prose tells the AI when and how to write events to `quality/run_state.jsonl` and rewrite `quality/PROGRESS.md`.
2. **Schema reference at `references/run_state_schema.md`** — defines the event taxonomy, fields per event type, validation rules, and the index-header convention.
3. **Cross-validation rules** — each `phase_end` event verifies the corresponding artifact exists and is well-formed before being written. Catch-and-recover: if the AI tries to claim phase completion without the artifact, the validation fails and the AI re-runs.
4. **Resume semantics** — when an AI session starts on a run directory with an existing `run_state.jsonl`, it reads the last event and resumes from there rather than restarting Phase 1.
5. **Cycle-level state** — `Calibration Cycles/<cycle>/run_state.jsonl` logs cycle-level events (cycle_start, benchmark_start, lever_change_applied, benchmark_end, cycle_end) so the orchestrator session can resume mid-cycle if it crashes.
6. **Autonomous orchestrator** — a self-contained prompt template at `agents/calibration_orchestrator.md` that one Claude Code session reads and executes to run an entire calibration cycle. The orchestrator session loops over the cycle's benchmark list, runs each playbook, applies the lever change at the right moment, and writes the cycle audit + calibration-log entry at the end.
7. **Four matplotlib visualizations** at `bin/visualize_calibration.py` generating PNGs into `Calibration Cycles/<cycle>/visualizations/`:
    - Per-bug × cycle heatmap (rows = historical bugs, columns = cycles, cells = found/missed). Direct view of the displacement story.
    - Lever × benchmark heatmap (rows = lever pulls, columns = benchmarks, cells = recall delta).
    - Recall trajectory chart (X = cycle, Y = recall, lines = benchmarks, annotations = lever pulls).
    - Lever interaction graph (nodes = levers/patterns, edges = positive/negative interactions). Hand-curated based on observed cycle data; emits Mermaid syntax that matplotlib renders via image conversion or as raw `.mermaid` for separate rendering.
8. **First calibration cycle** — Pattern 7 displacement recovery. Diagnose why PathRewrite and AllowContentEncoding were missed in v1.5.4 (most likely token-budget displacement); pull a sub-lever (budget cap tuning, pattern ordering, separate exploration pass for Pattern 7); measure recovery without losing Pattern 7's wins; iterate if needed.

### Operating principles

- **Discipline on `SKILL.md` edits.** SKILL.md gets edits to add the instrumentation prose. References to the new schema doc go in `references/`, not embedded in SKILL.md. Each instrumentation point is a single sentence in the appropriate phase section telling the AI to "append a `phase_start` event with `phase: 1` to `quality/run_state.jsonl` and rewrite `quality/PROGRESS.md`."
- **Schema versioning from day one.** `_index` event at the top of every `run_state.jsonl` records `schema_version`. Future schema bumps preserve backward compatibility (older files readable).
- **Every cycle is a commit.** Cycle audit, cell.json, calibration-log entry, visualization PNGs all land in one commit per cycle. Reproducible from the schema's perspective.
- **Validate before claiming.** A `phase_end` event with `bugs_md_path: "quality/BUGS.md"` is invalid if `quality/BUGS.md` doesn't exist or is empty. The AI is instructed to check before appending.

---

## Design

### Run-state event taxonomy

Every event is a single JSON object on its own line. Fields not listed for an event type are optional but should follow a consistent additional-field convention if used.

**Required for every event:** `ts` (ISO 8601 UTC), `event` (event-type string).

**Per-run events (`<benchmark>/quality/run_state.jsonl`):**

- `_index` — schema_version, event_types (list of all event types this run will use), benchmark, lever_state, started_at. Always the first line.
- `run_start` — benchmark, lever_state, runner (claude/codex/copilot), playbook_version (RELEASE_VERSION).
- `phase_start` — phase (1-6), started_at.
- `pattern_walked` — phase=1, pattern (1-7), findings_count, duration_seconds.
- `pass_started` / `pass_ended` — phase=4, pass (A/B/C/D), output_artifact (relative path).
- `finding_logged` — phase, finding_id, category (e.g., "skill-divergence", "code-bug", "missing-citation").
- `artifact_written` — relative_path, byte_size, line_count.
- `gate_check` — gate_name, verdict (pass/fail), reason (string).
- `phase_end` — phase, key_counts (dict, varies by phase), artifacts_produced (list of relative paths), duration_seconds.
- `error` — phase, message, recoverable (bool).
- `run_end` — status (success/aborted/failed), ended_at, total_findings.

**Cycle-level events (`Calibration Cycles/<cycle>/run_state.jsonl`):**

- `_index` — schema_version, event_types, cycle_name, lever_under_test, benchmarks (list).
- `cycle_start` — started_at, lever_under_test, hypothesis (string).
- `benchmark_start` — benchmark, lever_state (pre-lever / post-lever), started_at.
- `benchmark_end` — benchmark, lever_state, recall, bugs_found, bugs_missed (lists).
- `lever_change_applied` — lever, files_changed (list), commit_sha.
- `lever_change_reverted` — files_changed (list), commit_sha (or null if revert is uncommitted).
- `cycle_end` — verdict (ship/revert/iterate), recall_before, recall_after, delta, cross_benchmark_check (dict).

The taxonomy is granular by design — each meaningful state transition gets one event. Token cost per event is small (≤200 chars typical); observability gain is large.

### PROGRESS.md format

Atomic full rewrite each event. Markdown with checkbox list per phase, in-progress phase noted explicitly with start time, complete phases noted with duration and key counts.

```markdown
# QPB Run Progress

**Started:** 2026-05-15T14:32:01Z  **Benchmark:** chi-1.5.1  **Lever:** post-pattern7-displacement-fix-v1
**Runner:** claude  **Playbook version:** 1.5.5

## Phases

- [x] Phase 1 — Exploration (10:10, 12 findings, patterns 1-7 walked)
- [x] Phase 2 — Triage (0:42, 8 findings promoted)
- [x] Phase 3 — Investigation (15:31, 6 bugs identified)
- [x] Phase 4 — Skill-derivation (4 passes, 89 REQs produced)
- [ ] Phase 5 — Verification *(in progress, started 14:58:31Z)*
- [ ] Phase 6 — Release readiness

## Recent events

- 2026-05-15T14:58:31Z — phase_start phase=5
- 2026-05-15T14:58:30Z — phase_end phase=4 passes=[A,B,C,D] req_count=89
- 2026-05-15T14:42:11Z — phase_end phase=1 findings=12

## Artifacts produced

- quality/EXPLORATION.md (12,034 bytes)
- quality/REQUIREMENTS.md (28,891 bytes)
- quality/REQ_TRACEABILITY.md (3,022 bytes)
```

### Cross-validation rules

For each `phase_end` event, the AI is instructed to verify before appending:

- **Phase 1 phase_end** → `quality/EXPLORATION.md` exists, non-empty, contains at least one finding section.
- **Phase 2 phase_end** → `quality/EXPLORATION_MERGED.md` or equivalent triage artifact exists.
- **Phase 3 phase_end** → `quality/RUN_CODE_REVIEW.md` exists; bug writeups present per identified bugs.
- **Phase 4 phase_end** → `quality/REQUIREMENTS.md` + `quality/COVERAGE_MATRIX.md` exist; pass artifacts (Pass A/B/C/D outputs) all present.
- **Phase 5 phase_end** → `quality/results/quality-gate.log` written (the verification log).
- **Phase 6 phase_end** → `quality/BUGS.md` exists, non-empty, contains at least one BUG entry; `quality/INDEX.md` updated with gate verdict.
- **`run_end`** → all 6 phases have `phase_end` events; final BUGS.md count matches.

If validation fails, the AI logs an `error` event with `recoverable: true` and re-runs the failing phase (or fails the run with `run_end status=aborted` if recovery is impossible).

### Resume semantics

When an AI session starts on a run directory:

1. Check whether `quality/run_state.jsonl` exists. If absent: fresh run, start at `_index` + `run_start`.
2. If present: read all events, find the last `phase_start` not followed by a matching `phase_end`. That's the in-progress phase.
3. Verify the in-progress phase's expected artifacts (per cross-validation rules above). If complete artifacts present: append the `phase_end` event the prior session didn't get to write, then advance to the next phase. If artifacts incomplete: re-run that phase from scratch (the prior session left a partial state).
4. If all 6 `phase_end` events present but no `run_end`: append `run_end` and finalize.

The resume policy is: "trust the artifacts more than the events." If the events claim phase 4 done but REQUIREMENTS.md doesn't exist, the AI re-runs phase 4. If events stop mid-phase but the artifacts are complete, the AI catches up the events.

### Autonomous orchestrator

A new prompt template at `agents/calibration_orchestrator.md` guides one Claude Code session through a full calibration cycle. The orchestrator:

1. Reads `Calibration Cycles/<cycle>/run_state.jsonl` (creates if absent) and writes `cycle_start` if first run.
2. For each benchmark in the cycle's pinned list:
   a. Verifies the lever_state (revert Pattern 7 if doing pre-lever runs, restore if doing post-lever).
   b. Cleans the benchmark's `quality/` to a known starting state.
   c. Spawns the playbook on that benchmark via `python3 -m bin.run_playbook --claude --phase 1,2,3 repos/archive/<benchmark>` (or runs the underlying logic directly within the orchestrator session — both options preserved as flags).
   d. Polls the benchmark's `quality/run_state.jsonl` for completion.
   e. Reads the produced `quality/BUGS.md` and `quality/INDEX.md`, computes recall against historical baseline, appends `benchmark_end` event.
3. Between pre-lever and post-lever benchmark passes, applies the lever change as a commit (`lever_change_applied` event).
4. After all benchmarks complete: computes deltas, writes the cycle audit at `Calibration Cycles/<cycle>/audit.md`, appends a calibration-log entry to `docs/process/Lever_Calibration_Log.md`, generates the four visualizations, writes `cycle_end` event.
5. If the orchestrator session itself crashes mid-cycle: the next session reads `Calibration Cycles/<cycle>/run_state.jsonl`, finds where it stopped, resumes.

The orchestrator runs as a single Claude Code session, not a scheduled task. Long-running but stateless across crashes. The same AI doing the playbook work is also the orchestrator — no separation, no IPC.

### Visualizations

Static matplotlib script at `bin/visualize_calibration.py`. Reads `metrics/regression_replay/` for cell.json data and `Calibration Cycles/*/run_state.jsonl` for cycle history. Produces four PNGs per invocation.

**Per-bug × cycle heatmap.** Most useful for displacement story. Rows = historical bugs across all benchmarks (e.g., "chi-1.3.45/BUG-001 compression q=0", "chi-1.3.45/BUG-005 PathRewrite"); columns = cycles in chronological order; cells = found (green) / missed (red) / unchanged (gray) / not-applicable (white). A row that toggles green→red→green across cycles is a bug being clawed back and lost again — exactly the give-and-take Andrew identified.

**Lever × benchmark heatmap.** Rows = lever pulls (e.g., "Lever 1: Pattern 7 added"), columns = benchmarks (chi, virtio, express), cells = recall delta. Helps see which levers help which targets.

**Recall trajectory chart.** Time-series. X = cycle ordinal (1, 2, 3, ...), Y = recall (0.0-1.0), one line per benchmark, vertical-line annotations at lever-pull cycles.

**Lever interaction graph.** Nodes = levers/patterns, edges = positive (boosts) or negative (displaces). Hand-curated from cycle data — initially empty, populated by the orchestrator after each cycle based on observed deltas. Emits as Mermaid `graph LR` syntax; matplotlib script writes both `.mermaid` source and a rendered PNG (matplotlib doesn't render Mermaid natively; the script either shells out to mermaid-cli if available or emits the .mermaid for separate rendering).

Dependencies: matplotlib, numpy. Static, generated on demand. Outputs to `Calibration Cycles/<cycle>/visualizations/`. Not part of the playbook runner — separate `bin/visualize_calibration.py` invocation.

### First calibration cycle — Pattern 7 displacement recovery

The cycle that validates v1.5.5 on real work:

- **Hypothesis:** Pattern 7's two displacement regressions on chi-1.3.45 (PathRewrite, AllowContentEncoding) result from token-budget displacement — Pattern 7's exploration takes attention budget that previously caught those bugs via patterns 1-6.
- **Lever pull candidate:** budget cap tuning. The Pattern 7 prose currently says "3-5 highest-impact composition seams per pass." Possible adjustments: lower the cap to 2-3 (less Pattern 7 attention, more for other patterns); separate Pattern 7 into a pre-pass that doesn't compete with the others; reorder patterns so Pattern 7 runs last after others have written their findings.
- **Cycle structure:** pre-lever benchmark runs on chi-1.3.45 (current Pattern 7 setup); apply lever change; post-lever runs on chi-1.3.45 + chi-1.5.1 + virtio-1.5.1 + express-1.3.50. Compute deltas. Verify both PathRewrite and AllowContentEncoding return to "found" status while Pattern 7's mount-context wins (BUG-004, BUG-007, BUG-008, BUG-009) remain.
- **Iterate if needed.** If the first lever pull doesn't recover both losses without sacrificing Pattern 7 wins, the autonomous orchestrator iterates: try a different sub-lever, run again. Up to 3 iterations before manual intervention.

This cycle is the first real test of the v1.5.5 substrate. Success looks like: the orchestrator runs end-to-end without operator intervention, produces a cycle audit + calibration-log entry + visualizations, and either (a) ships a sub-lever that recovers displacement losses, or (b) reports that the substrate worked but no sub-lever recovered the losses (a real finding worth documenting).

---

## What v1.5.5 removes from v1.5.4

- The script-orchestrator approach (`bin/regression_replay.py`'s implicit assumption that a separate orchestration script drives cycles). v1.5.5 doesn't delete the script — it stays as a one-shot recall-computation utility — but the `run_replay()` orchestration entry point is deprecated in favor of AI-driven orchestration.
- The Cowork-environment escape clause in CALIBRATION_PROTOCOL.md (Mode 1 = autonomous via sub-agent fan-out for Council). v1.5.5's autonomous mode is now Mode 1, period. Mode 2 (operator-in-loop with `gh copilot`) remains for operator-driven manual cycles but is no longer the default.

## What stays from v1.5.4

- The `metrics/regression_replay/SCHEMA.md` cell.json schema — unchanged.
- `docs/process/Lever_Calibration_Log.md` — orchestrator writes new entries appending to it.
- The CALIBRATION_PROTOCOL.md 12 steps — orchestrator follows them, but mechanically (no operator pre-flight). Steps 1-12 become the prompt template at `agents/calibration_orchestrator.md`.
- The role-map architecture, Pattern 7, all v1.5.4 schema work — unchanged.

---

## Validation

v1.5.5 is validated by the first calibration cycle running end-to-end:

1. **Substrate works.** The orchestrator session starts, runs all benchmarks, applies the lever change, computes deltas, writes the cycle audit and calibration-log entry, generates visualizations. No operator intervention. No scheduled-task halts.
2. **Resume works.** A deliberate mid-cycle kill of the orchestrator session is recovered cleanly by the next session reading run_state.jsonl.
3. **Cross-validation works.** A deliberately incomplete `phase_end` (artifact missing) triggers the validation failure and re-run.
4. **Visualizations render.** All four PNGs produced from real cycle data; the per-bug × cycle heatmap shows the Pattern 7 displacement story visually.
5. **Test cycle ships or reverts honestly.** Pattern 7 displacement recovery either succeeds (sub-lever ships) or fails (substrate worked, no sub-lever found — that's also a real finding).

v1.5.5's success is the substrate, not a particular outcome from the test cycle.

---

## Out of Scope

- Requirements Review feature. That's v1.6.0.
- Multi-source informal-spec evidence weighing. v1.6.0 (Slice 2 of the Requirements Review proposal).
- Lessons-learned synthesis from defect logs. v1.6.0 (Slice 3).
- Modifying Pattern 7 itself beyond the budget-cap / ordering experiments. The Pattern 7 prose is a v1.5.4 artifact; v1.5.5 may tune its budget cap, but the pattern's substantive content is fixed.
- Removing `bin/regression_replay.py`. The script stays as a recall-computation utility; only its orchestration role transfers to the AI-driven orchestrator.
- Council protocol changes. Council-of-Three protocol unchanged; the orchestrator can invoke it in Mode 1 (sub-agent fan-out) or Mode 2 (operator-driven `gh copilot`) per CALIBRATION_PROTOCOL.md.

---

## Dependencies

- v1.5.4 shipped, tagged at `v1.5.4` (commit `8ccd460`).
- `1.5.5` branch created from `v1.5.4` tag (done 2026-05-02).
- `RELEASE_VERSION` bump to `1.5.5-pre` on the new branch as the first work-item commit.
- v1.5.4 cycle 1's existing artifacts (`Calibration Cycles/2026-05-01-chi-1.3.45/audit.md`, `metrics/regression_replay/20260501T231500Z/chi-1.3.45-1.3.45-all.json`, `docs/process/Lever_Calibration_Log.md`) — provide the historical data the visualizations and the displacement-recovery cycle reason about.
- v1.5.4 cycle 1's "missing pre-Pattern-7 baselines" gap on chi-1.5.1 / virtio-1.5.1 / express-1.3.50 — v1.5.5's first cycle fills the gap as a side effect of the displacement-recovery test.

---

## Open Questions

1. **Orchestrator session model: Claude Code or sub-agent inside Cowork?** The natural fit is a Claude Code session (long-running, host-side, has the bandwidth for ~30-min playbook subprocesses). But the prompt template lives in the QPB repo and could be invoked via Cowork's Agent tool with `general-purpose` subagent_type, which would let the user kick off cycles from a Cowork chat. Both should work; design picks Claude Code as default with Cowork sub-agent as a documented alternative.
2. **Iterate-cap for the first cycle.** If the displacement-recovery sub-lever doesn't recover both losses on the first pull, how many iterations before halting and asking the operator? Default 3, configurable per cycle.
3. **Visualization update cadence.** Are the four PNGs regenerated on every cycle, or only on operator demand? Default: regenerate on cycle close (every cycle). Cost is small; freshness is high.
4. **Mermaid rendering pipeline.** If `mermaid-cli` isn't installed, the lever-interaction graph emits `.mermaid` source only. Document this; don't make `mermaid-cli` a hard dependency.

These get resolved during the implementation Council review.
