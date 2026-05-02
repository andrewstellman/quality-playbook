# Quality Playbook v1.5.5 — Implementation Plan

*Companion to: `QPB_v1.5.5_Design.md`*
*Status: drafted 2026-05-02 immediately after v1.5.4 ship; implementation begins on the `1.5.5` branch.*
*Depends on: v1.5.4 shipped + tagged + pushed (commit `8ccd460`, tag `v1.5.4` at `7da201f`); benchmark archive operational at `repos/archive/`*

---

## Operating Principles

- **One AI session per calibration cycle.** The orchestrator session is long-running but stateless across crashes. State lives in the filesystem (`run_state.jsonl` + `PROGRESS.md`), not in any in-memory or external-process structure.
- **Validate before claiming.** Every `phase_end` event verifies its expected artifacts exist before being written. Cross-validation is mechanical (file-existence checks), not LLM-judged.
- **Discipline on `SKILL.md`.** Instrumentation prose lives in SKILL.md; the schema definition lives in `references/run_state_schema.md`. SKILL.md gets minimal additions — one or two sentences per phase boundary, not a verbose specification.
- **Each phase has a Council review.** Per CALIBRATION_PROTOCOL.md Mode 1, the implementing AI invokes the nested 3×3 Council via parallel sub-agents at each phase gate. No phase ships without it.
- **Schema versioned from day one.** `_index` event records `schema_version`. `1.5.5-pre.0` for the initial bring-up, `1.5.5` at release.
- **Autonomy ceiling at 3 iterations per cycle.** The orchestrator may iterate up to 3 times on a sub-lever before halting and asking the operator. Hard cap; no escape hatches.

---

## Phase 0 — v1.5.4 Stabilization Confirmation

Goal: confirm v1.5.4 is shipped, tagged, validated; the `1.5.5` branch is fresh from the v1.5.4 tag; `RELEASE_VERSION` bumped to `1.5.5-pre`. Disposition any v1.5.4 self-audit findings from the Codex bootstrap run on the fresh clone (in progress at `repos/quality-playbook-1.5.4-bootstrap/`).

Work items:
- v1.5.4 tag exists on origin (`refs/tags/v1.5.4` at `7da201f`) ✓
- main fast-forwarded to v1.5.4 (origin/main at `8ccd460`) ✓
- 1.5.5 branch created from v1.5.4 (origin/1.5.5 at `8ccd460`) ✓
- Bump `RELEASE_VERSION` in `bin/benchmark_lib.py`: `1.5.4` → `1.5.5-pre`
- Bump README version stamp: `1.5.4` → `1.5.5-pre` (with note that this is a pre-release marker)
- Codex bootstrap run on `repos/quality-playbook-1.5.4-bootstrap/` completes; any findings dispositioned (`fix-in-Phase-1`, `fix-deferred-to-v1.6.0`, or `won't-fix-with-rationale`).
- v1.5.4 cycle 1's missing pre-Pattern-7 baselines (chi-1.5.1, virtio-1.5.1, express-1.3.50) are dispositioned: either filled in as a side-effect of Phase 5's first cycle, or explicitly deferred.

Gate to Phase 1: all of the above confirmed; `1.5.5` branch is fresh; bootstrap findings have dispositions.

---

## Phase 1 — Run-State Schema + SKILL.md Instrumentation Core

Goal: define the run-state event taxonomy and PROGRESS.md format, instrument `SKILL.md` to write events at every meaningful state transition during a playbook run.

Work items:
- **Create `references/run_state_schema.md`** defining:
  - Required fields for every event (`ts`, `event`)
  - Per-run event types (with required + optional fields per type): `_index`, `run_start`, `phase_start`, `pattern_walked`, `pass_started`, `pass_ended`, `finding_logged`, `artifact_written`, `gate_check`, `phase_end`, `error`, `run_end`
  - Cycle-level event types: `_index`, `cycle_start`, `benchmark_start`, `lever_change_applied`, `lever_change_reverted`, `benchmark_end`, `cycle_end`
  - Schema version field convention (`schema_version` in `_index`)
  - Timestamp format (ISO 8601 with `Z` for UTC)
  - PROGRESS.md format spec (sections: header, phase checklist, recent events, artifacts produced)
- **Update `SKILL.md` with instrumentation points**, one per phase + key sub-events:
  - Phase 1 begins → write `_index` (if absent) + `run_start` + `phase_start phase=1`
  - Each pattern walked → `pattern_walked phase=1 pattern=N`
  - Phase 1 ends → `phase_end phase=1` (with cross-validation: `quality/EXPLORATION.md` exists)
  - Phase 2 begins → `phase_start phase=2`
  - Phase 2 ends → `phase_end phase=2` (cross-validation: `quality/EXPLORATION_MERGED.md` exists)
  - Phase 3 begins → `phase_start phase=3`
  - Phase 3 ends → `phase_end phase=3` (cross-validation: `quality/RUN_CODE_REVIEW.md` exists, bug writeups present)
  - Phase 4 begins → `phase_start phase=4`
  - Each pass starts/ends → `pass_started` / `pass_ended` for A/B/C/D
  - Phase 4 ends → `phase_end phase=4` (cross-validation: `quality/REQUIREMENTS.md` + `quality/COVERAGE_MATRIX.md` exist)
  - Phase 5 begins → `phase_start phase=5`
  - Phase 5 ends → `phase_end phase=5` (cross-validation: `quality/results/quality-gate.log` written)
  - Phase 6 begins → `phase_start phase=6`
  - Phase 6 ends → `phase_end phase=6` (cross-validation: `quality/BUGS.md` non-empty, `quality/INDEX.md` updated)
  - Run completes → `run_end status=success/failed`
- **Update `bin/run_playbook.py`** if it owns any phase-boundary writes (most instrumentation is prose-driven, but the orchestrator harness may write `run_start` / `run_end` directly when invoked via the harness rather than via direct AI execution).
- **Add unit tests in `bin/tests/`** for:
  - `_index` event always first line; schema_version present
  - JSON parseability of every event (each line valid JSON)
  - Required-fields enforcement per event type
  - Append-only invariant (events only added, never edited)
  - PROGRESS.md format conformance (header + phase list + recent events)

Test fixtures:
- A synthetic `quality/` subtree with a complete `run_state.jsonl` showing all event types
- A synthetic `quality/` subtree with a malformed event (extra/missing fields) — should fail validation

Deliverable: `references/run_state_schema.md` published; SKILL.md instrumented at every phase boundary; unit tests pass.

Council review: 3×3 nested panel on the schema design + SKILL.md edits. Specific lenses:
- Are event types granular enough? (challenge: should `gate_check` be one event or per-check?)
- Is the cross-validation set complete? (challenge: are there phase artifacts we're missing?)
- Does SKILL.md prose unambiguously tell the AI when to write each event? (challenge: ambiguity → silent skips)

Gate to Phase 2: schema + SKILL.md edits committed; Council ship verdict; unit tests pass; a manual smoke test (run playbook on one small target) produces a well-formed `run_state.jsonl` matching the schema.

---

## Phase 2 — Cross-Validation + Resume Semantics

Goal: make the AI verify each `phase_end` against artifacts before writing the event, and make the next session resume from the last valid state if the prior session crashed.

Work items:
- **Add cross-validation prose to SKILL.md** at each `phase_end` instrumentation point. Format: "before appending `phase_end phase=N`, verify [artifact list]. If any expected artifact is missing or empty, append an `error` event with `recoverable: true` and re-run [recovery action]."
  - Phase 1: `quality/EXPLORATION.md` exists, non-empty, contains at least one finding section.
  - Phase 2: `quality/EXPLORATION_MERGED.md` (or `quality/triage/*.md`) exists.
  - Phase 3: `quality/RUN_CODE_REVIEW.md` exists; `quality/writeups/BUG-*.md` count matches identified-bug count.
  - Phase 4: `quality/REQUIREMENTS.md` non-empty; `quality/COVERAGE_MATRIX.md` exists; pass artifacts (Pass A/B/C/D outputs in `quality/skill_derivation/` or equivalent) all present.
  - Phase 5: `quality/results/quality-gate.log` written; gate verdict captured.
  - Phase 6: `quality/BUGS.md` non-empty (≥1 BUG entry); `quality/INDEX.md` has `gate_verdict` field; `quality/results/quality-gate.log` includes the final verdict.
- **Add resume-discovery prose to SKILL.md** at the playbook entry point. The instructions tell the AI: "if `quality/run_state.jsonl` exists when the run starts, read it; find the last `phase_start` not followed by `phase_end`; verify that phase's artifacts; either catch up the events (if artifacts complete) or re-run the phase (if artifacts incomplete)."
- **Add `bin/run_state_lib.py`** with helper functions for AI-readable / human-readable use: `read_events(jsonl_path) -> list[dict]`, `last_in_progress_phase(events) -> int | None`, `validate_phase_artifacts(quality_dir, phase) -> tuple[bool, str]`. The library is callable from inside the AI session for cross-validation work and from the orchestrator for resume logic.
- **Unit tests in `bin/tests/`** covering:
  - Resume from clean run (no `run_state.jsonl` → start fresh)
  - Resume from partial Phase 4 (events show in-progress, artifacts complete → catch up events)
  - Resume from partial Phase 4 (events show in-progress, artifacts incomplete → re-run phase)
  - Cross-validation rejects empty BUGS.md as Phase 6 complete
  - `error` event with `recoverable: true` triggers re-run (manual integration test, document the procedure)

Deliverable: cross-validation rules instrumented in SKILL.md; resume logic instrumented; `bin/run_state_lib.py` library + tests; unit tests pass.

Council review: 3×3 panel on the cross-validation rules + resume semantics. Lenses:
- Are the validation checks tight enough to catch real failures? (challenge: an empty REQUIREMENTS.md — does our check catch that, or only a missing file?)
- Is the resume logic safe under all crash points? (challenge: crash mid-pattern_walked — does resume re-walk that pattern?)
- Is the "trust artifacts more than events" policy right? (challenge: what if both diverge and we can't tell which is correct?)

Gate to Phase 3: cross-validation + resume semantics committed; Council ship verdict; unit tests pass; integration smoke test (kill mid-Phase-4, restart, verify clean resumption) succeeds.

---

## Phase 3 — Autonomous Orchestrator

Goal: write the prompt template that lets one Claude Code session run a full calibration cycle end-to-end, using the Phase 1+2 substrate.

Work items:
- **Create `agents/calibration_orchestrator.md`** as the prompt template. Sections:
  - Role: "you are an autonomous calibration cycle orchestrator. Your job is to run a complete cycle from cycle_start to cycle_end without operator intervention beyond initial kickoff."
  - Inputs: cycle directory path, lever-under-test commit SHA, benchmark list, hypothesis statement.
  - Twelve-step procedure mapped from CALIBRATION_PROTOCOL.md (pre-flight; diagnose; lever change; pre-lever runs; apply; post-lever runs; cross-benchmark; deltas; audit + log + viz; report).
  - Per-step: which `run_state.jsonl` events to write at the cycle level (`benchmark_start`, `benchmark_end`, `lever_change_applied`, etc.).
  - Per-benchmark playbook invocation: spawn a sub-AI-session (via Cowork's Agent tool with `general-purpose` subagent_type, or as a Claude Code subprocess via the harness) for each playbook run.
  - Resume logic: read cycle's run_state.jsonl on start; pick up at the last incomplete event.
  - Iterate-cap: if the cycle's verdict is "iterate" and iteration count < 3, restart from the diagnose step with the new hypothesis; if iteration count >= 3, halt with `cycle_end verdict=halt-iterate-cap`.
- **Update CALIBRATION_PROTOCOL.md** to reference the new orchestrator template. Mode 1's "the executing AI walks Phase 1-3 inline" becomes "the executing AI invokes `agents/calibration_orchestrator.md`."
- **Add `bin/orchestrator_lib.py`** with helpers callable from inside the orchestrator AI session: `current_cycle_state()`, `next_action()`, `record_event()`. These wrap the run_state_lib at the cycle level.
- **Document the kickoff procedure** in `ai_context/CALIBRATION_PROTOCOL.md`: "to start a cycle, the operator runs `python3 -m bin.start_cycle <cycle-name> --lever <lever-id> --benchmarks chi-1.3.45,chi-1.5.1,...` which creates the cycle directory, writes the orchestrator prompt with substituted variables, and prints the Claude Code launch command."

Test fixtures:
- A "dry-run" cycle that skips the actual playbook spawn (mocks BUGS.md production) and verifies the orchestrator session writes all expected events
- A "kill-mid-cycle" test that halts the orchestrator after `benchmark_end` for benchmark 1 and confirms the next session resumes at benchmark 2

Deliverable: orchestrator template at `agents/calibration_orchestrator.md`; orchestrator lib + tests; CALIBRATION_PROTOCOL.md updated to reference the template; kickoff procedure documented.

Council review: 3×3 panel on the orchestrator design. Lenses:
- Does the orchestrator handle the "playbook session crashes mid-benchmark" case correctly? (challenge: orchestrator must detect crash, decide whether to retry or fail)
- Does the iterate-cap actually prevent runaway cycles? (challenge: nested iterate scenarios)
- Is the spawned-subprocess vs. spawned-AI-session decision correct? (challenge: token budget for orchestrator vs. task budget for playbook)

Gate to Phase 4: orchestrator template committed; Council ship verdict; dry-run + kill-mid-cycle tests pass.

---

## Phase 4 — Visualizations

Goal: produce four matplotlib visualizations from cycle data.

Work items:
- **Create `bin/visualize_calibration.py`**:
  - CLI: `python3 -m bin.visualize_calibration <cycle-dir>` produces all four PNGs into `<cycle-dir>/visualizations/`.
  - Per-bug × cycle heatmap: rows = bugs from across `repos/archive/<benchmark>/quality/previous_runs/<latest>/quality/BUGS.md` (the historical baselines), columns = cycles in chronological order from `Calibration Cycles/`, cells = green (found) / red (missed) / gray (unchanged) / white (not applicable). One PNG, organized by benchmark groups within rows.
  - Lever × benchmark heatmap: rows = lever pulls (from `docs/process/Lever_Calibration_Log.md` entries), columns = benchmarks (chi, virtio, express), cells = recall delta with color gradient (red negative, green positive). One PNG.
  - Recall trajectory chart: line plot, X = cycle ordinal, Y = recall (0.0-1.0), one line per benchmark, vertical dashed lines at lever-pull cycle boundaries with annotation. One PNG.
  - Lever interaction graph: emit Mermaid `graph LR` syntax representing observed positive/negative interactions between levers/patterns across cycles. Write `.mermaid` source file; if `mermaid-cli` is available on PATH, also produce rendered PNG; if not, emit a placeholder PNG noting "see lever_interaction.mermaid for source."
- **Inputs and outputs:**
  - Input 1: `Calibration Cycles/*/run_state.jsonl` (cycle history)
  - Input 2: `metrics/regression_replay/*/cell.json` (per-cycle recall data)
  - Input 3: `repos/archive/<benchmark>/quality/previous_runs/<latest>/quality/BUGS.md` (historical baselines for each benchmark)
  - Input 4: `docs/process/Lever_Calibration_Log.md` (per-cycle lever pulls)
  - Output: 4 PNGs + 1 .mermaid file in `<cycle-dir>/visualizations/`
- **Dependencies:** matplotlib, numpy. Document in `bin/visualize_calibration.py` module docstring. The script lives outside the playbook runner — separate invocation, not part of phase 1-6 execution.
- **Unit tests in `bin/tests/`** covering:
  - Reads `Calibration Cycles/2026-05-01-chi-1.3.45/` (the v1.5.4 cycle 1 data) and produces 4 valid PNGs
  - Handles missing inputs gracefully (only chi data → only chi rows in heatmaps; no virtio/express noise)
  - Mermaid source is parseable when `mermaid-cli` not available
- **Add `bin/visualize_calibration.py` to the orchestrator's cycle-close step** so each cycle's audit ends with viz regeneration.

Deliverable: `bin/visualize_calibration.py` runs against v1.5.4 cycle 1 data and produces 4 PNGs; orchestrator integration calls it at cycle close.

Council review: 3×3 panel on the visualization design. Lenses:
- Are the four visualizations the right four? (challenge: is the lever-interaction graph the most useful, or would a per-pattern attention-budget chart be more diagnostic?)
- Does the per-bug × cycle heatmap actually show displacement clearly? (challenge: with 30+ bugs across benchmarks, will the heatmap be readable?)
- Are the inputs the right inputs? (challenge: should the recall trajectory show variance bands from noise floor?)

Gate to Phase 5: visualizations committed; Council ship verdict; unit tests pass; v1.5.4 cycle 1 data renders to 4 valid PNGs.

---

## Phase 5 — First Calibration Cycle (Pattern 7 Displacement Recovery)

Goal: run the first end-to-end autonomous cycle using the v1.5.5 substrate. The cycle's purpose: recover Pattern 7's two displacement regressions (PathRewrite, AllowContentEncoding on chi-1.3.45) without losing Pattern 7's mount-context wins. This cycle simultaneously validates v1.5.5's substrate AND advances QPB's quality.

Work items:
- **Cycle setup:** create `Calibration Cycles/2026-05-XX-pattern7-displacement-recovery/` directory; write `cycle_start` event with hypothesis "Pattern 7's budget allocation displaces attention from patterns 1-6, missing PathRewrite + AllowContentEncoding bugs that v1.5.3 caught. Tuning the budget cap or pattern ordering should recover both losses without sacrificing mount-context wins."
- **Pre-flight (run by orchestrator):** verify v1.5.5 RELEASE_VERSION is on HEAD, working tree clean, benchmark archives present, claude CLI available.
- **Pre-lever runs:** orchestrator spawns playbook on chi-1.3.45 with current Pattern 7 setup. Result should reproduce v1.5.4 cycle 1's 6/10 = 0.60 recall (within noise). Plus pre-Pattern-7-equivalent runs on chi-1.5.1, virtio-1.5.1, express-1.3.50 to fill in the missing baselines from v1.5.4 cycle 1 (this step solves a v1.5.4 carry-forward gap as a side effect).
- **Lever pull (sub-lever candidate 1):** lower Pattern 7's budget cap from "3-5 highest-impact composition seams per pass" to "2-3 highest-impact composition seams per pass." Edit `references/exploration_patterns.md` Pattern 7 section. Commit; record `lever_change_applied` event.
- **Post-lever runs:** orchestrator runs all four benchmarks again with the updated pattern.
- **Cross-benchmark check:** verify chi-1.5.1 / virtio / express don't regress while chi-1.3.45 recovers PathRewrite + AllowContentEncoding.
- **Iterate up to 3 times if needed.** If sub-lever candidate 1 doesn't recover both losses without sacrificing wins, the orchestrator picks sub-lever candidate 2 (e.g., reorder Pattern 7 to run last) and re-runs. After 3 iterations, halt with `cycle_end verdict=halt-iterate-cap`.
- **Cycle close:** orchestrator writes audit at `Calibration Cycles/2026-05-XX/audit.md`, appends entry to `docs/process/Lever_Calibration_Log.md`, runs `bin/visualize_calibration.py`. Writes `cycle_end` event with verdict.
- **The cycle's verdict is a real outcome.** If a sub-lever recovers losses → ship the change as part of v1.5.5. If no sub-lever in 3 iterations recovers losses → the cycle's finding is "Pattern 7's displacement regressions are not budget-tunable in the obvious ways; deeper investigation deferred to v1.5.6 or v1.6.0." That's also a real result.

Test fixtures: none (this IS the test).

Deliverable: cycle audit + calibration-log entry + visualizations; sub-lever shipped (if found) or deferred (if not).

Council review: 3×3 panel on the cycle's verdict. Lenses:
- Is the sub-lever change well-targeted at the displacement regression? (challenge: does the budget cap actually control attention budget, or is the LLM ignoring it?)
- Are the cross-benchmark numbers honest? (challenge: are we comparing apples to apples — same lever_state, same runner, same RELEASE_VERSION?)
- Does the cycle's verdict accurately reflect the data? (challenge: confirmation bias on a cycle whose explicit goal is to find a recovery)

Gate to Phase 6: cycle audit landed; Council ship verdict on the cycle's outcome; v1.5.5 substrate validated end-to-end.

---

## Phase 6 — Mechanical Release

Goal: ship v1.5.5.

Work items:
- Bump `RELEASE_VERSION` to `1.5.5`.
- Update README version stamp + add "What's new in v1.5.5" section.
- Update `ai_context/IMPROVEMENT_LOOP.md` with v1.5.5's autonomous-loop substrate (orchestrator template, run-state instrumentation, visualization pipeline).
- Final test suite run.
- Commit, push, tag, push tag.
- Fast-forward main to v1.5.5 (analogous to v1.5.4's main fast-forward).
- Create `1.6.0` branch from `v1.5.5` tag.
- Push `1.6.0` branch.
- Verify origin via `git ls-remote`.

Deliverable: v1.5.5 tagged on origin; main at v1.5.5; 1.6.0 branch open from v1.5.5.

Gate to v1.6.0: all of the above verified; v1.5.5 release notes published.

---

## Risks and Mitigations

- **The orchestrator session times out.** Cowork's Agent tool has a long but finite session lifetime; Claude Code sessions can be longer but are still bounded. Mitigation: the resume-from-state design ensures partial progress isn't lost; a session that times out partway through gets resumed by the next session.
- **The first cycle finds no recovering sub-lever.** Honest outcome; document and defer. The substrate's success is independent of the cycle's outcome.
- **Cross-validation rejects valid completions.** If a phase produces an artifact in a non-canonical location, cross-validation fails the run incorrectly. Mitigation: Phase 1's smoke tests + Phase 2's integration tests catch this before Phase 5.
- **Schema gaps surface during orchestrator implementation.** Likely; document and bump schema_version mid-development. The schema versioning convention from Phase 1 protects against breaking changes.
- **Mermaid CLI not available during cycle runs.** Lever-interaction graph emits source-only. Document; don't make it a hard dependency. Operators can render manually if needed.

---

## Out-of-band carry-forward to v1.6.0

If anything in v1.5.5's design surfaces a v1.6.0-relevant question (e.g., "should the orchestrator also drive Requirements Review sessions?"), it goes into `docs/design/QPB_v1.6.0_Design.md`'s carry-forward section. Don't expand v1.5.5's scope to absorb it.
