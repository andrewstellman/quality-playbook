# arunner × QPB integration + regression test

Scaffolding for the v1.5.10 close-out check: a **regression test** (did the SKILL.md
trim/relocation break bug-finding?) that is simultaneously an **integration test**
(does arunner's FR-61–65 phase orchestration correctly drive QPB's phases?).

**`run_playbook` is not used — it is retired.** The vehicle is arunner-native via
**subagent dispatch** — the dispatch model arunner exists for: a Claude Code
orchestrator runs the plan and spawns **one subagent per QPB phase** (its Task tool),
with a deterministic exit-code gate (`validate_phase_artifacts`) between phases
(FR-63/64), in a `measurement: true` run. We do **not** shell `claude -p` per phase —
that is the retired `run_playbook` shape (see arunner `TOOLKIT.md` / `DEVELOPMENT_CONTEXT.md`).

## Files

- `plan.json` — the finalized arunner plan. **Proven `--check`-clean** against the
  FR-61–65 engine (`fr-61-65-impl`) on 2026-06-19 via a sandbox-path twin. Each QPB
  phase is a **`dispatch_mode: "subagent"` step** (FR-62 multi-step); the orchestrator
  spawns a subagent per phase. Each step's `worker_prompt_file` is a `*.subagent.md`
  file carrying the five reserved placeholders (`{HEARTBEAT_PATH}` etc.) + the
  STARTING/terminal heartbeat instructions + the rendered phase body; the engine
  substitutes the placeholders at dispatch (`str.replace`, so the phase JSON braces
  survive). Deterministic `validate_phase_artifacts` shell gate after phases 1 and 2;
  `measurement:true` (shell-only gates). `target_repo` paths are machine-local (assume
  `setup_repos.sh` produced `repos/<repo>-1.5.8`); **re-run
  `python3 arunner/engine/tick.py --check plan.json` locally** before any live run.
- `phase_prompts_rendered/phase{1,2,3}.md` — the **pre-rendered** phase bodies,
  produced via `run_playbook`'s `phaseN_prompt()` builders (all `{skill_fallback_guide}`
  / `{seed_instruction}` / `{role_taxonomy}` / doubled braces resolved; verified no
  `{ }` placeholders remain).
- `phase_prompts_rendered/phase{1,2,3}.subagent.md` — the above, wrapped with the
  arunner subagent placeholder header + heartbeat-emission instructions. These are what
  `plan.json` references.

## Authoritative spec

`runner/1.5.9/instructions/053-v1.5.10-integration-regression-test.md` — the worker
brief: build + `--check` (worker, deterministic), live run (operator/fresh Claude Code
instance), score with the regression-test scorer (`bin/regression_replay.py`)
measurement-only mode (NOT `--invoke-runner`), 3-panel Council.
