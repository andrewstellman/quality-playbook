# Benchmark Protocol

Last updated: 2026-05-06 (v1.5.6 cluster G refresh + cluster F.4 instruction-041-part-3 revision — clarifies the canonical 3 (or 4 with chi-1.5.1) calibration benchmarks for cycle work. The original 2026-05-02 v1.5.6 cycle ran on chi-1.3.45 + virtio-1.5.1 + express-1.3.50 (verdict REVERT; express post-lever data preserved per cell.json + cycle subdir verified at instruction 041 part 1). The chi-1.5.1 follow-on cycle is in-progress at v1.5.6 cluster F.2 (playbook subprocess spawned 2026-05-06T21:00:06Z). Cluster F.1 commit `ba64584` folded the 2026-05-02 cycle's operational learnings into `agents/calibration_orchestrator.md` — see that template's failure-modes section for the API-budget-exhausted recovery path, the reduced-scope option's three preconditions, and the mid-benchmark post-lever interruption failure mode.)

The playbook tunes against real repos. For tuning signals to be honest, each benchmark run has to start from the same blank slate — no prior findings, no sibling runs, no pre-existing `quality/` artifacts to anchor on. This file is the checklist.

## The contamination risk

Agents running the playbook are smart enough to look around. If a sibling directory next to the target contains a prior playbook run, the agent can read its `EXPLORATION.md`, `BUGS.md`, and `quality/` artifacts and reuse findings instead of discovering them independently. This defeats the benchmark.

Concretely, we have already observed Codex notice a sibling run on its own. Other agents (Claude Code, Copilot) will too.

## Run layout

```
repos/
  clean/              ← pristine sources, never modified, never run against directly
  runs/
    {target}-{version}-{runner}-{yyyymmdd-hhmmss}/
      {target}/       ← freshly copied from clean/, the only sibling in this dir
      run.log         ← captured stdout/stderr
      NOTES.md        ← optional: anything the operator wants to record
```

The target checkout lives **alone** inside its run directory. No other repos, no prior runs, no scratch files.

## Pre-run checklist

Before kicking off any benchmark run:

1. **Copy the target fresh from `repos/clean/`** into a new empty run directory under `repos/runs/`. Never run the playbook against `repos/clean/{target}` itself, and never against an existing run directory.
2. **Verify there are no siblings.** `ls` the run directory's parent should show only this run, not peer runs for the same target or other targets.
3. **Verify no pre-existing `quality/` folder** inside the target. If SKILL.md is installed, that's fine; the playbook expects it. But `quality/`, `EXPLORATION.md`, `BUGS.md`, etc. must not exist yet.
4. **Confirm SKILL.md version** in the target matches the version you intend to benchmark. `.github/skills/SKILL.md` is the canonical location.
5. **Seeds off.** The runner defaults to `--no-seeds`; if you invoke an agent directly, the prompt should not reference prior runs.

## During the run

- Capture stdout/stderr to `run.log` in the run directory.
- Do not add files to the run directory while the agent is working. Let it own the space.
- If the run hits a rate limit or other interruption, record that in `NOTES.md` — it's signal for capacity planning, not just a nuisance.

## Run-state instrumentation (v1.5.5+)

Starting in v1.5.5, the runner emits an append-only `quality/run_state.jsonl` event log alongside the existing artifacts. Each phase boundary writes a `phase_started` / `phase_completed` (or `phase_aborted`) event with timestamp, qpb version, runner, and exit code; phase-5 finalization additionally emits a `validation_result` event for each post-condition check the orchestrator ran. The full event taxonomy and field-presence invariants live at `references/run_state_schema.md`.

For benchmark consumers, the relevant cross-validation rules are:

- **Phase-artifact post-conditions.** `bin/run_state_lib.py:validate_phase_artifacts` is invoked at each phase boundary; a `phase_completed` event whose `validation_result.status` is `fail` means the phase produced an event but the artifact set was incomplete (e.g., a Phase 3 completion with no `BUGS.md`). For benchmark scoring, treat such cells as malformed and exclude from recall comparisons.
- **Source-edit guardrail (Phase 5).** `validate_no_source_edits` is wired into `bin/run_playbook.py:_finalize_iteration`; a `validation_result` event with `check="no_source_edits"` and `status="fail"` indicates the run modified files outside the per-target `quality/` tree during finalization. Such runs are tainted from a recall-comparison standpoint and should be re-run from a clean checkout.
- **Format invariants.** Every line in `run_state.jsonl` is a single JSON object with `event`, `phase`, `iso_ts`, and (where relevant) `qpb_version` / `runner` keys; readers should be tolerant of additional optional keys (forward compatibility) but reject lines missing the four required keys.

`bin/run_state_lib.py` ships read/parse helpers (`read_events`, `last_in_progress_phase`, `validate_run_state_file`) plus the writer side (`append_event`, `write_progress_md`); benchmark tooling that needs to consume the log should use these helpers rather than re-implementing the parser.

## After the run

Each run produces two kinds of data:

1. **Bugs found** — the direct quality signal. Compare against prior runs and cross-agent runs for the same target.
2. **Friction points** — places the agent paused, asked for clarification, or appeared to miss something the protocol should have caught. This is the tuning signal, and it feeds back into the two adjustable axes:
   - `references/exploration_patterns.md` — what requirements Phase 1 elicits
   - `references/defensive_patterns.md` — what defensive code the grep sweep surfaces

Capture friction in `NOTES.md` or in a dedicated `RUN_SUMMARY.md` inside `quality/`.

## Cross-agent runs

When running the same target in multiple agents (e.g., httpx in Codex while chi runs in Copilot), each agent gets its own run directory. Never share a run directory across agents — their artifact conventions differ, and one agent reading another's in-progress work is the worst kind of contamination.

## Calibration-cycle benchmark set

For calibration-cycle work (per `ai_context/CALIBRATION_PROTOCOL.md`), the canonical pinned-benchmark set is **chi**, **virtio**, and **express** — three repos with substantively different failure modes (Go HTTP routing, kernel-C transport variants, JavaScript parser laxity) so a regression that only manifests in one ecosystem is still observable. With **chi-1.5.1** added the canonical set extends to four (chi at both the v1.3.45 historical pin and the v1.5.1 modern pin). Each pinned benchmark has a documented historical bug count from a known QPB version that serves as the recall floor.

The v1.5.6 Pattern 7 displacement-recovery cycle's original 2026-05-02 run produced complete pre/post-lever cells for chi-1.3.45, virtio-1.5.1, AND express-1.3.50 (instruction 041 part 1 verified the express-1.3.50 post-lever cell.json and cycle subdir DO exist — the audit prose claiming "interrupted before producing a replayable cell snapshot" is stale, not the data; cluster F.4 audit refresh corrects this). chi-1.5.1 was the original time-budget deferral. The chi-1.5.1 follow-on cycle is in-progress at v1.5.6 cluster F.2 (playbook subprocess spawned 2026-05-06T21:00:06Z). The reduced scope did not weaken the cycle's REVERT verdict because the displacement-recovery story was concentrated on chi-1.3.45 and that benchmark produced a negative result.

## Current benchmark set

### Code targets (v1.5.0 divergence pipeline)

- **bootstrap** — the playbook against QPB itself, with gathered documentation seeding REQUIREMENTS.md (Hybrid project per Phase 0 classifier; runs both the v1.5.0 code path and the v1.5.3 skill-derivation path)
- **chi** (Go, ~74 source files) — baseline, well-understood
- **cobra** (Go) — second Go library for cross-project comparison
- **virtio** (C, kernel code) — systems-level coverage, defensive-code heavy
- **express** (JavaScript) — language diversity, web-framework shape
- **clean/casbin** (Go, v1.5.3 first-time target) — added to the v1.5.3 cross-target validation matrix

### Pure-Skill targets (v1.5.3 skill-derivation pipeline only)

- **anthropic-skills/skills/skill-creator** — meta-skill (485-line SKILL.md + references/schemas.md)
- **anthropic-skills/skills/pdf** — focused single-purpose skill (314-line SKILL.md, no references/)
- **anthropic-skills/skills/claude-api** — API skill (262-line SKILL.md, no references/)

These three classify as Skill (high confidence) under the v1.5.3
classifier; they exercise the four-pass skill-derivation pipeline
end-to-end without firing any of the v1.5.0 Code-project gates.

### Cross-version (optional)

- **quality-playbook-1.4.5** — older QPB self with SKILL.md present; useful for v1.5.3 Phase 4 internal-prose detection against an evolved spec

### Next batch candidates, not yet run

- **httpx** (Python, ~23 source files) — smallest, fastest feedback
- **serde** (Rust, ~58 source files) — closest size match to chi
- **gson** (Java, ~120 source files) — JVM coverage

Add rows here when new targets enter the benchmark.

## v1.5.3 skill-target run procedure

Skill / Hybrid targets use the v1.5.3 skill-derivation CLI rather
than `bin/run_playbook.py`:

```bash
# 1. Classify (writes <target>/quality/project_type.json)
python3 -m bin.classify_project --target <target> --write

# 2. Phase 3 four-pass derivation (Pass A LLM-driven; B/C/D mechanical)
python3 -m bin.skill_derivation --phase 3 --pass all --runner claude --pace-seconds 0 <target>

# 3. Phase 4 divergence detection (mechanical for A.1/A.2/B; Hybrid-only LLM for A.3)
python3 -m bin.skill_derivation --phase 4 --part all <target>

# 4. (Hybrid only) Phase 4 Part A.3 LLM-driven prose-to-code
python3 -m bin.skill_derivation --phase 4 --part a3 --runner claude --pace-seconds 0 <target>
```

**Runner choice (v1.5.3+).** Three LLM backends ship: `--runner
claude` (default; wraps `claude --print`), `--runner copilot`
(wraps `gh copilot --prompt`), and `--runner codex` (added
post-tag in commit `b6b31f2`; wraps `codex exec --full-auto`,
codex-cli 0.125+). For benchmark-cell isolation, the runner choice
should be recorded in the run directory's `NOTES.md` so future
analysis can attribute variance to the runner backend. Codex picks
its model from `~/.codex/config.toml` by default; pass
`--model gpt-5-codex` (or any model in the user's codex config)
to override.

Output artifacts land under `<target>/quality/phase3/` (the same
directory holds Phase 3 four-pass + Phase 4 divergence outputs).
The contamination-risk discipline above still applies — never run
against `repos/clean/<target>` directly; copy fresh into a run
directory under `repos/runs/`.
