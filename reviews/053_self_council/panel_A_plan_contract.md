# Panel A — plan/contract correctness — VERDICT: SHIP

Independent adversarial review of the arunner×QPB integration+regression scaffolding (commit `a400cad`, branch `1.5.10`).

- **OK plan.json structure.** 3 entries (chi/virtio/express), every entry+step `dispatch_mode:"subagent"`; steps phase1→phase2→phase3; shell gates ONLY after phase1 and phase2 (phase3 terminal, no gate); each gate argv exactly `["python3","-m","bin.validate_phase_artifacts","{TARGET_REPO}","--phase","N"]` (N=1 after phase1, N=2 after phase2) → exit-code FR-64 fail-closed (correct for measurement). `measurement:true`, `pool_size:3`. `worker_prompt_file` → `phase_prompts_rendered/phaseN.subagent.md`.
- **OK target_repo paths exist.** All three absolute `repos/{chi,virtio,express}-1.5.8` exist.
- **OK pre-render fully resolved.** `phaseN.md` contain ZERO `{placeholder}` tokens — no `{skill_fallback_guide}`/`{seed_instruction}`/`{role_taxonomy}` residue. The only braces in phase3.md are literal domain enumerations (`{RING_RESET, ADMIN_VQ, …}`, `{PCI, MMIO, vDPA}`) — prose, not placeholders.
- **OK subagent prompts carry only the 5 reserved engine placeholders.** All three `phaseN.subagent.md` contain exactly `{HEARTBEAT_PATH} {TASK_ID} {RUN_DIR} {TARGET_REPO} {HARNESS_BIN}` + STARTING / IN_PROGRESS / terminal COMPLETED-FAILED heartbeat instructions.
- **OK `--check` clean.** `PYTHONPATH=…/arunner-fr61-65-impl python3 -m arunner.engine.tick --check plan.json` → `plan OK: plan.json -- no problems found`, **exit 0**.
- **OK no retired dispatch shape.** No `claude -p` / `claude --print` dispatch anywhere; the only `run_playbook` strings are disclaimers ("run_playbook is NOT used") in the `_README`/README.
- **NIT** stale `bin/run_playbook.py` references in phase1.md / phase1.subagent.md (lines ~24/34 and ~43/53) — used as the QPB-self-bug example + the `skill-tool` vs `code` role-map worked example; the file is absent from the targets. Pedagogical, never invoked; non-blocking. Worth a prompt-prose cleanup given the branch's run_playbook purge.

VERDICT: SHIP
