# Benchmark Protocol

Last updated: 2026-05-14 (v1.5.7 ship — log layout centralized under `quality/logs/<run-id>/` per the per-cell tree; `--logs-flat` legacy flag preserves the v1.5.6 scattered layout for tooling that needs it. Phase 2 gate-failure artifact preservation lands at `quality.gate-failed-<UTC-timestamp>/` — benchmark cells that abort at Phase 2 now preserve the failed artifact set rather than wiping. See "Centralized log emission" and "Phase 2 abort preservation" sections below. Calibration-cycle benchmark set unchanged from v1.5.6.)

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

## Phase 4 Council multi-model contamination (model-comparison runs)

**Phase 4 (Spec Audit) uses a fixed Council roster regardless of `--model`.** The Council members are defined in `bin/council_config.py` (current v1.5.7 D6 6a roster: `claude-opus-4.7`, `gpt-5.5`, `claude-sonnet-4.6`) and audit each cell's artifacts independent of the runner's model selection. The roster can be overridden per-adopter via `~/.qpb/config.json` (D6 6c). For model-comparison or model-evaluation studies, this means a `--copilot --model X` run that completes Phase 4 produces `BUGS.md` output that mixes X's Phase 1-3 findings with the Council's audit findings. Phases 5 (Reconciliation) and 6 (Verify) build on the contaminated Phase 4 output; iteration strategies (gap, unfiltered, parity, adversarial) build on Phase 5 output and are likewise contaminated.

**For clean per-model cells, use `--benchmark-mode`** (v1.5.6 cluster 050+): constrains the run to phases 1-3 only, emits a clear banner at run start, and writes a `quality/RUN_MODE.md` marker so downstream tooling can filter for clean cells. The flag is mutually exclusive with `--full-run` / `--next-iteration` / `--strategy` / `--iterations` (those all consume Council-contaminated artifacts). Or pass `--phase 1,2,3` directly — same phase scope without the marker. Regardless of flag choice, the runner echoes the Council roster at Phase 4 entry as a defense-in-depth log signal so operators scanning logs see the model expansion explicitly.

The contamination was discovered mid-v1.5.5 model-comparison sweep after ~150 cells of data were collected; the data was discarded and the sweep restarted with `--phase 1,2,3`. The doc warning + flag prevent that recurrence.

## Run-state instrumentation (v1.5.5+)

Starting in v1.5.5, the runner emits an append-only `quality/run_state.jsonl` event log alongside the existing artifacts. The first line is always an `_index` event recording schema version and event taxonomy; the run is then bracketed by `run_start` and per-phase `phase_start` / `phase_end` events with timestamp, qpb version, runner, and target path. Phase 5 finalization emits `gate_check` events for each post-condition the orchestrator ran (with `verdict` of `pass` / `fail` / `warn` / `skip`); abort paths emit an `error` event with `recoverable: false`. The full event taxonomy and field-presence invariants live at `references/run_state_schema.md`.

For benchmark consumers, the relevant cross-validation rules are:

- **Phase-artifact post-conditions.** `bin/run_state_lib.py:validate_phase_artifacts` is invoked at each phase boundary and returns a `(bool, str)` outcome the orchestrator records via `gate_check` (or, when validation fails hard, an `error` event). A run that emits a `phase_end` event but whose paired `gate_check` for `phase_artifacts` reports `verdict: "fail"` means the phase produced an event but the artifact set was incomplete (e.g., a Phase 3 completion with no `BUGS.md`). For benchmark scoring, treat such cells as malformed and exclude from recall comparisons.
- **Source-edit guardrail (Phase 5).** `validate_no_source_edits` is wired into `bin/run_playbook.py:_finalize_iteration`; a `gate_check` event whose `gate_name` matches the no-source-edits check and whose `verdict` is `fail` indicates the run modified files outside the per-target `quality/` tree during finalization. Such runs are tainted from a recall-comparison standpoint and should be re-run from a clean checkout.
- **Format invariants.** Every line in `run_state.jsonl` is a single JSON object with `event` and `ts` (ISO 8601 UTC with `Z` suffix) as required keys; per-event-type required keys are listed in `references/run_state_schema.md`. Readers should be tolerant of additional optional keys (forward compatibility) but reject lines missing the universal required keys.

`bin/run_state_lib.py` ships read/parse helpers (`read_events`, `last_in_progress_phase`, `validate_run_state_file`) plus the writer side (`append_event`, `write_progress_md`); benchmark tooling that needs to consume the log should use these helpers rather than re-implementing the parser.

## Centralized log emission (v1.5.7+)

Starting in v1.5.7, all log emission for a single run lands under `<target>/quality/logs/<run-id>/` inside the per-target `quality/` tree. The per-cell directory is now the canonical "everything from this run" location: stdout/stderr, control prompts, run-state event log, gate output, finalization log. Benchmark cells become self-contained for archival purposes.

For benchmark sweeps that need the v1.5.6 scattered layout (driver logs in `/tmp`, `<parent>/<cell>-playbook-<ts>.log`, etc.), pass `--logs-flat` to `bin/run_playbook.py`. The flag preserves the older paths; the centralized layout is the default and the recommended choice for new sweeps.

`quality/logs/` is included in the suggested `.gitignore` template. Don't commit log content into the project repo — archive it alongside the cell instead.

## Phase 2 abort preservation (v1.5.7+)

When the Phase 2 gate aborts before producing the full artifact set, the rejected `quality/` directory is preserved as `quality.gate-failed-<UTC-timestamp>/` rather than wiped. For benchmark cells, this means an aborted Phase 2 cell still has the agent's outputs available for diagnostic inspection — the EXPLORATION.md, role map, and partial PROGRESS.md that triggered the abort are preserved.

Benchmark consumers scoring cells should treat the presence of a `quality.gate-failed-*/` directory as a Phase-2-abort signal (and exclude the cell from recall comparisons), while still being able to read what the agent produced for the post-mortem.

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

The v1.5.6 Pattern 7 displacement-recovery cycle's original 2026-05-02 run produced complete pre/post-lever cells for chi-1.3.45, virtio-1.5.1, AND express-1.3.50 (instruction 041 part 1 verified the express-1.3.50 post-lever cell.json and cycle subdir DO exist — the original "interrupted before producing a replayable cell snapshot" prose was reconciled in v1.5.6 fix-up 055). chi-1.5.1 was the original time-budget deferral. The v1.5.6 cluster F.2a follow-on chi-1.5.1 pre-lever run with claude-opus-4-7 produced 9/16 substantive recall against the v1.5.1 baseline; the cycle is closed at 3 of 4 benchmarks (chi-1.5.1 informs historical baseline understanding but is not a 4th cell in the per-benchmark recall table). The reduced scope did not weaken the cycle's REVERT verdict because the displacement-recovery story was concentrated on chi-1.3.45 and that benchmark produced a negative result.

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
(routes through `bin/copilot_resolver.py` per v1.5.7 089f — the
new standalone `copilot -p` with the deprecated `gh copilot
--prompt` extension as grace-period fallback), and `--runner
codex` (added post-tag in commit `b6b31f2`; wraps `codex exec
--full-auto`, codex-cli 0.125+). For benchmark-cell isolation, the runner choice
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

## Code-target run procedure

Code targets (and Hybrid code-path runs) use `bin/run_playbook.py`. Positional arguments are directory paths (relative or absolute) — the runner does no short-name resolution and no benchmark-folder lookup. Run from `repos/` so the working-copy directory names produced by `setup_repos.sh` (e.g. `chi-1.5.7`) can be passed as plain relative paths:

```bash
cd repos/
./setup_repos.sh chi cobra virtio                     # copy skill files into the three repo-based targets
python3 ../bin/run_playbook.py chi-1.5.7 cobra-1.5.7 virtio-1.5.7          # baseline runs (Copilot default)
python3 ../bin/run_playbook.py --claude chi-1.5.7 cobra-1.5.7 virtio-1.5.7 # baseline runs (Claude Code)
python3 ../bin/run_playbook.py --codex chi-1.5.7 cobra-1.5.7 virtio-1.5.7  # baseline runs (codex-cli, v1.5.3+)
python3 ../bin/run_playbook.py --next-iteration --strategy all chi-1.5.7 cobra-1.5.7 virtio-1.5.7  # full iteration cycle
```

**Bootstrap is invoked by passing the QPB repo root as an explicit target** — it doesn't go through `setup_repos.sh` because the QPB repo already has SKILL.md and references at their canonical locations:

```bash
python3 bin/run_playbook.py /path/to/QPB --phase all   # bootstrap: run on the QPB repo itself
```

**Post-089x note:** running `bin/run_playbook.py` with **no arguments at all no longer auto-starts the bootstrap self-audit** — a truly bare invocation prints the script's purpose banner and exits 0 (the 089x no-args-safe invariant). Note that passing flags *without* a positional target (e.g. `--phase all`) still defaults to the current directory (`args.targets = ["."]`), so always pass an explicit target for clarity and safety. The human-operator override `--operator-invoked` is available for driving a run from inside an agent terminal.

## Why bootstrap is a benchmark target

Bootstrap is the playbook running against the QPB repo itself. It's always included in the active benchmark set because:

1. **Self-referential edge cases.** The gate script validates its own artifacts. SKILL.md is both the instruction set and the subject under audit. Changes to rules about enum validation, heading format, or script-verified closure can break on the very script that enforces them — and only bootstrap catches that class of bug.
2. **Perfect verification.** We wrote the skill and the gate, so we can verify any finding against our own intent quickly. For other repos, we spot-check; for bootstrap, we can confirm every bug.
3. **Reproducibility.** The codebase is stable between runs (our own commits), so convergence trends cleanly across model/runner combinations.

Bootstrap artifacts live at `quality/` at the QPB repo root rather than under `repos/`. To run bootstrap, the agent treats the QPB root as the target directory; the existing `quality/` is the prior-run evidence (phase 0 seed source).

## Interpreting results

**Bug counts vary between runs.** The same skill on the same codebase produces different bug counts due to non-determinism in exploration. A single run isn't definitive. Compare across 5+ runs or use iteration cycles to compensate.

**Baseline vs. iteration yield.** Baseline typically finds 1-3 bugs per repo. Full iteration cycle (gap + unfiltered + parity + adversarial) multiplies by 3-4x. If a skill change doesn't improve baseline yield, it may still improve iteration yield or vice versa.

**Spot-check every new version.** After making skill changes, spot-check 3-5 bugs from the new version against actual source code. Verify the bug is real, the file:line is correct, and the regression test would actually fail. In v1.3.46 benchmarking, 15/15 spot-checked bugs were verified as real.

## Known agent behavior differences

| Agent | Exploration | TDD execution | Known issues |
|-------|------------|---------------|-------------|
| Claude Code / Opus | Strong | Reliable (creates red/green logs) | Expensive (~8% weekly per run) |
| Claude Code / Sonnet | Strong (25 bugs, 3 HIGH) | Reliable | Recommended default (~3% weekly per run) |
| Copilot / gpt-5.4 | Strong | Weak (skips log creation) | 54hr rate limit on heavy use |
| Cursor / Sonnet | Good | Weak first pass, follows up when asked | Workspace scope bleeds to siblings |
| Cursor / Codex 5.3 | Weak (zero bugs) | N/A | Insufficient reasoning depth |
| Codex CLI / `codex exec --full-auto` (v1.5.3+) | TBD — released as a runner option in commit `b6b31f2`; benchmark data accumulates as adopters use it | TBD | Standalone CLI (NOT the GitHub Copilot CLI — neither the new `copilot` nor the deprecated `gh copilot` extension); codex picks its model from `~/.codex/config.toml` unless `--model` overrides |

The v1.5.7 UX contract surfaces the **pass-process / fail-recall** failure mode (Cursor / Codex 5.3 row above; the "agent produces clean artifacts and passes gates while finding zero real bugs" case) directly in the agent's chat output via the mandatory `## What just happened` block emitted at every phase boundary (see SKILL.md cross-phase orientation-spine section + `references/what_just_happened.md` State S template). Adopters who hit this on a Cursor-Auto run now see plain-English framing like "Phases 1-2 produced real artifacts, but Phases 3-5 wrote stubs and zero bugs were confirmed. This is the documented pass-process / fail-recall failure mode — switch to a more capable model" rather than having to derive the same diagnosis from buried gate WARNs.

## Council reviews

For major skill changes, we run a council review: three different AI agents independently analyze the benchmark data, iteration logs, and bug quality, then propose improvements. The agents don't modify code — they write analysis documents.

Council review artifacts go in `council-reviews/`. Each review has:
- `COUNCIL_BRIEFING_VN.md` — data and questions for the council
- `COUNCIL_VN_PROMPTS.md` — prompts for each reviewer (must include "DO NOT modify any code")
- `{AGENT}_RESPONSE_VN.md` — each reviewer's analysis

(For the project's full Council-of-Three nested-panel protocol — roster, the `cd`-into-repo discipline, the nested-panel trigger header — see the workspace `CLAUDE.md` and `ai_context/DEVELOPMENT_PROCESS.md`.)
