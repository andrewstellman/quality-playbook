# Quality Playbook — Agent Guide

This file helps AI coding agents work on this repository. Read it first.

## What this repo is

The Quality Playbook is a skill for AI coding agents that explores any codebase from scratch and finds real bugs. It generates nine quality artifacts including a consolidated bug report with regression test patches, fix patches, and TDD red/green verification. It works with any language (Python, Java, Go, Rust, TypeScript, C, etc.) and any AI coding agent (Claude Code, GitHub Copilot, Cursor). v1.5.3 adds a skill-as-code surface (project-type classifier; four-pass generate-then-verify pipeline; skill-divergence taxonomy with internal-prose / prose-to-code / execution categories; skill-project gate enforcement) so the same divergence model that finds defects in code can find defects in AI skills — see `previous_runs/v1.5.3/` for the bootstrap evidence.

## Key files

| File | Purpose | When to read |
|------|---------|-------------|
| `SKILL.md` | Full operational instructions for running the playbook | When executing the playbook on a target repo |
| `references/iteration.md` | Iteration strategy reference (gap, unfiltered, parity, adversarial) | When running iteration mode |
| `quality_gate.py` | Mechanical validation script | After playbook completes, to validate artifacts |
| `references/*.md` | Phase-specific reference files (review protocols, spec audit, etc.) | During specific phases as directed by SKILL.md |
| `bin/skill_derivation/` | Phase 3 four-pass derivation pipeline + Phase 4 divergence detection (Skill / Hybrid projects only) | When working on the v1.5.3 skill-as-code surface |
| `bin/skill_derivation/runners.py` | LLM runner abstraction — four concrete runners: `ClaudeRunner` (`claude --print`), `CopilotRunner` (the GitHub Copilot CLI — new standalone `copilot -p` with deprecated `gh copilot --prompt` extension as grace-period fallback per v1.5.7 089f; routed via `bin/copilot_resolver.py`), `CodexRunner` (`codex exec --full-auto`, codex-cli 0.125+), `CursorRunner` (`cursor agent --print --force`, cursor-cli 3.1.10+) | When adding a new LLM backend or tuning subprocess invocation |
| `bin/copilot_resolver.py` | v1.5.7 089f — Copilot CLI resolver. Detects which CLI is on PATH (preferring the new standalone `copilot` over the deprecated `gh copilot` extension), emits the correct argv shape (flag mapping shimmed: `--allow-all` ↔ `--yolo`), and raises `CopilotCLIUnavailable` with platform-aware remediation when neither is available. All five Copilot CLI subprocess sites route through it. | When adjusting Copilot CLI detection or adding a new install route |
| `bin/council_config.py` | v1.5.7 D6 — Council roster defaults + override resolver. Default members: `claude-opus-4.7`, `gpt-5.5`, `claude-sonnet-4.6`. Override precedence: `--council-roster` CLI flag > `~/.qpb/config.json` (or `$XDG_CONFIG_HOME/qpb/config.json`) > defaults. See `references/runners_and_models.md` for adopter-facing override docs. | When adjusting the Council roster or debugging Council availability |
| `bin/qpb_config.py` | v1.5.7 D6 — `python3 -m bin.qpb_config show|set|unset <key>` manages `~/.qpb/config.json`. | When showing/setting the adopter's Council override |
| `ai_context/TOOLKIT.md` | User-facing interactive documentation | When helping a user set up or run the playbook |
| `ai_context/DEVELOPMENT_CONTEXT.md` | Maintainer context (architecture, benchmarking, known issues) | When working on the skill itself |
| `agents/quality-playbook.agent.md` | Orchestrator agent (Copilot / general format). **AUTOMATION ONLY — NOT for interactive sessions.** Spawns a sub-agent per phase, hiding per-step output from the operator's chat. Use only for headless CI / batch contexts where per-phase context-window isolation is necessary. For interactive coding sessions (Claude Code, Cursor, Copilot UI, Codex desktop), do NOT read this file — read `SKILL.md` and execute Mode A directly; your chat IS the witness trail. | Automated batch invocation only — never for an operator-watched interactive session |
| `agents/quality-playbook-claude.agent.md` | Orchestrator agent (Claude Code format). **AUTOMATION ONLY — NOT for interactive sessions.** Same automation-only constraint as the row above. The 2026-05-16 express opus-4.6 Mode-A run reproduced the failure mode this constraint prevents: an interactive Claude Code session spawned this orchestrator, the sub-skill hid the gate invocation from the parent's witness chat, and a PASS verdict was fabricated against an actual 14-FAIL gate. For interactive sessions: read `SKILL.md`, execute Mode A in your own context. | Automated batch invocation only — never for an operator-watched interactive session |

### Where logs go (v1.5.7+ centralized layout)

Per-run logs land under `<target>/quality/logs/<run-id>/` where `<run-id>` is the run's UTC ISO-8601 compact timestamp (`YYYYMMDDTHHMMSSZ`). This is the v1.5.7 D3 deliverable — replaces the v1.5.6 scattered layout (parent-dir log files + top-level `quality/control_prompts/`) with one centralized directory per run. Pass `--logs-flat` (or set `QPB_LOGS_LEGACY=1`) to preserve the v1.5.6 scattered layout for tooling that depends on the old paths. `references/run_state_schema.md` is the canonical schema doc for the centralized layout's `run_id` / `log_layout` discriminator fields on the `run_start` event.

When a Phase 2 gate-failure preservation triggers (v1.5.7 D1), the entire failed `quality/` tree is renamed to `<repo_dir>/quality.gate-failed-<UTC-ts>/` and a fresh `quality/` is created. The preserved directory carries its own `logs/<run-id>/` subtree with the failure logs.

## Installing the skill

Copy the skill into your AI coding tool's skill directory in the target repo. Run these commands from your target repo root, with `$QPB` pointing at your local quality-playbook clone (`export QPB=/path/to/quality-playbook`).

**GitHub Copilot:**
```bash
mkdir -p .github/skills/references
mkdir -p .github/skills/phase_prompts
mkdir -p .github/skills/agents
mkdir -p .github/skills/bin
# v1.5.8 instruction 209: source paths now nest through
# plugins/quality-playbook/skills/quality-playbook/ (standard
# self-hosted marketplace plugin layout); the cp DESTINATIONS at
# .github/skills/... are unchanged (the adopter-target layout is
# frozen).
QPB_SKILL_SRC="$QPB"/plugins/quality-playbook/skills/quality-playbook
cp "$QPB_SKILL_SRC"/SKILL.md .github/skills/SKILL.md
cp "$QPB_SKILL_SRC"/scripts/quality_gate.py .github/skills/quality_gate.py
cp "$QPB_SKILL_SRC"/references/* .github/skills/references/
cp "$QPB_SKILL_SRC"/phase_prompts/*.md .github/skills/phase_prompts/
# v1.5.6: agents/*.md needed by README Step 4's `claude --agent agents/...` invocation.
cp "$QPB_SKILL_SRC"/agents/*.md .github/skills/agents/
# v1.5.7 088 (A-29): the bin/ closure required for Mode A walkthroughs
# to resolve every module SKILL.md + phase_prompts hard-reference.
# This list is MIRRORED from install_skill.py::_bundle_files() and
# pinned by test_install_skill_bundle_completeness::
# test_agents_md_cp_blocks_match_bundle. DO NOT add/remove a module
# here without updating _bundle_files() in lockstep (drift recreates
# the A-26 ship-blocker via this doc-sanctioned alternate path).
cp "$QPB_SKILL_SRC"/scripts/__init__.py                          .github/skills/bin/__init__.py
cp "$QPB_SKILL_SRC"/scripts/_purpose.py                          .github/skills/bin/_purpose.py
cp "$QPB_SKILL_SRC"/scripts/archive_lib.py                       .github/skills/bin/archive_lib.py
cp "$QPB_SKILL_SRC"/scripts/benchmark_lib.py                     .github/skills/bin/benchmark_lib.py
cp "$QPB_SKILL_SRC"/scripts/citation_verifier.py                 .github/skills/bin/citation_verifier.py
cp "$QPB_SKILL_SRC"/scripts/council_config.py                    .github/skills/bin/council_config.py
cp "$QPB_SKILL_SRC"/scripts/council_semantic_check.py            .github/skills/bin/council_semantic_check.py
cp "$QPB_SKILL_SRC"/scripts/migrate_v1_5_0_layout.py             .github/skills/bin/migrate_v1_5_0_layout.py
cp "$QPB_SKILL_SRC"/scripts/qpb_config.py                        .github/skills/bin/qpb_config.py
cp "$QPB_SKILL_SRC"/scripts/quality_playbook.py                  .github/skills/bin/quality_playbook.py
cp "$QPB_SKILL_SRC"/scripts/reference_docs_ingest.py             .github/skills/bin/reference_docs_ingest.py
cp "$QPB_SKILL_SRC"/scripts/role_map.py                          .github/skills/bin/role_map.py
cp "$QPB_SKILL_SRC"/scripts/run_state_lib.py                     .github/skills/bin/run_state_lib.py
cp "$QPB_SKILL_SRC"/scripts/validate_phase_artifacts.py          .github/skills/bin/validate_phase_artifacts.py
cp "$QPB_SKILL_SRC"/scripts/qpb_validate.py                      .github/skills/bin/qpb_validate.py
cp "$QPB_SKILL_SRC"/scripts/qpb_phase.py                         .github/skills/bin/qpb_phase.py
# v1.5.2+: single reference_docs/ tree at the target repo root.
# Place adopter docs here — citable specs/RFCs in reference_docs/cite/.
# (v1.5.7 090h retired informal_docs/; reference_docs/ is the sole
# adopter doc location. docs_gathered/ is benchmark-tooling only and
# is NOT ingested by an adopter install.)
mkdir -p reference_docs reference_docs/cite
# v1.5.7 (087): sentinel file for the tracked-directory negation rule
# (without it run_playbook.py's pre-flight aborts "Required sentinel
# files missing"; install_skill.py creates this too).
mkdir -p quality
echo "# Run Index" > quality/RUN_INDEX.md
# Optional: append suggested .gitignore rules for adopters.
cat "$QPB_SKILL_SRC"/skill-template.gitignore >> .gitignore
```

**Claude Code:**
```bash
mkdir -p .claude/skills/quality-playbook/references
mkdir -p .claude/skills/quality-playbook/phase_prompts
mkdir -p .claude/skills/quality-playbook/agents
mkdir -p .claude/skills/quality-playbook/bin
# v1.5.8 instruction 209: source paths nest through plugins/quality-playbook/skills/quality-playbook/
# (standard self-hosted marketplace plugin layout).
QPB_SKILL_SRC="$QPB"/plugins/quality-playbook/skills/quality-playbook
cp "$QPB_SKILL_SRC"/SKILL.md .claude/skills/quality-playbook/SKILL.md
cp "$QPB_SKILL_SRC"/scripts/quality_gate.py .claude/skills/quality-playbook/quality_gate.py
cp "$QPB_SKILL_SRC"/references/* .claude/skills/quality-playbook/references/
cp "$QPB_SKILL_SRC"/phase_prompts/*.md .claude/skills/quality-playbook/phase_prompts/
# v1.5.6: agents/*.md needed by README Step 4's `claude --agent agents/...` invocation.
cp "$QPB_SKILL_SRC"/agents/*.md .claude/skills/quality-playbook/agents/
# v1.5.7 088 (A-29): the bin/ closure required for Mode A walkthroughs
# to resolve every module SKILL.md + phase_prompts hard-reference.
# This list is MIRRORED from install_skill.py::_bundle_files() and
# pinned by test_install_skill_bundle_completeness::
# test_agents_md_cp_blocks_match_bundle. DO NOT add/remove a module
# here without updating _bundle_files() in lockstep (drift recreates
# the A-26 ship-blocker via this doc-sanctioned alternate path).
cp "$QPB_SKILL_SRC"/scripts/__init__.py                  .claude/skills/quality-playbook/bin/__init__.py
cp "$QPB_SKILL_SRC"/scripts/_purpose.py                  .claude/skills/quality-playbook/bin/_purpose.py
cp "$QPB_SKILL_SRC"/scripts/archive_lib.py               .claude/skills/quality-playbook/bin/archive_lib.py
cp "$QPB_SKILL_SRC"/scripts/benchmark_lib.py             .claude/skills/quality-playbook/bin/benchmark_lib.py
cp "$QPB_SKILL_SRC"/scripts/citation_verifier.py         .claude/skills/quality-playbook/bin/citation_verifier.py
cp "$QPB_SKILL_SRC"/scripts/council_config.py            .claude/skills/quality-playbook/bin/council_config.py
cp "$QPB_SKILL_SRC"/scripts/council_semantic_check.py    .claude/skills/quality-playbook/bin/council_semantic_check.py
cp "$QPB_SKILL_SRC"/scripts/migrate_v1_5_0_layout.py     .claude/skills/quality-playbook/bin/migrate_v1_5_0_layout.py
cp "$QPB_SKILL_SRC"/scripts/qpb_config.py                .claude/skills/quality-playbook/bin/qpb_config.py
cp "$QPB_SKILL_SRC"/scripts/quality_playbook.py          .claude/skills/quality-playbook/bin/quality_playbook.py
cp "$QPB_SKILL_SRC"/scripts/reference_docs_ingest.py     .claude/skills/quality-playbook/bin/reference_docs_ingest.py
cp "$QPB_SKILL_SRC"/scripts/role_map.py                  .claude/skills/quality-playbook/bin/role_map.py
cp "$QPB_SKILL_SRC"/scripts/run_state_lib.py             .claude/skills/quality-playbook/bin/run_state_lib.py
cp "$QPB_SKILL_SRC"/scripts/validate_phase_artifacts.py  .claude/skills/quality-playbook/bin/validate_phase_artifacts.py
cp "$QPB_SKILL_SRC"/scripts/qpb_validate.py              .claude/skills/quality-playbook/bin/qpb_validate.py
# v1.5.2+: single reference_docs/ tree at the target repo root.
# Place adopter docs here — citable specs/RFCs in reference_docs/cite/.
# (v1.5.7 090h retired informal_docs/; reference_docs/ is the sole
# adopter doc location. docs_gathered/ is benchmark-tooling only and
# is NOT ingested by an adopter install.)
mkdir -p reference_docs reference_docs/cite
# v1.5.7 (087): sentinel file for the tracked-directory negation rule
# (without it run_playbook.py's pre-flight aborts "Required sentinel
# files missing"; install_skill.py creates this too).
mkdir -p quality
echo "# Run Index" > quality/RUN_INDEX.md
cat "$QPB_SKILL_SRC"/skill-template.gitignore >> .gitignore
```

Then tell your AI tool:
```
Run the quality playbook on this project.
```

## Installing the Quality Playbook into a target repo (AI-agent-driven)

This is the canonical install procedure when an AI coding agent (Claude Code, Cursor, etc.) is doing the install on the operator's behalf. Use it instead of the manual `cp` commands above unless the operator asks for the manual flow. For AI-agent installs, prefer `--into <target-repo>` so the script scans the operator's repo rather than the QPB clone. For operator-direct installs, either run with `--into <target-repo>` from the QPB clone or run with no flag from inside the target repo root and let cwd auto-detection resolve the install path.

1. Confirm the operator's target repo (e.g., `~/Documents/myrepo`) and determine which AI tool will use the project, in priority order:

   (a) **Use what the operator told you.** If the original request named a tool ("Install QPB for Cursor in this project"), use that.

   (b) **Use your own identity** if you can confidently identify yourself as the AI tool that will use the project — e.g., you ARE Cursor running in a Cursor session, you ARE Claude Code, you ARE GitHub Copilot. When you take this path, be transparent with the operator: tell them "I'll install for <tool> since this is a <tool> session" so they can correct if they're targeting a different tool than the one you're running in (an operator using Cursor right now might still want to install for Claude Code if their teammates use Claude Code on this project).

   (c) **ASK the operator** if neither (a) nor (b) applies (e.g., you're a generic orchestrator without a tool identity, or the project's target tool is genuinely ambiguous): "Which AI tool will use this project? (cursor, claude, copilot, continue, codex, windsurf, cline, or aider)" — before running the install. Don't guess.

   The script auto-detects any of the 8 known marker directories — `.claude/`, `.github/`, `.cursor/`, `.continue/`, `.codex/`, `.windsurf/`, `.cline/`, `.aider/` — and installs to the matching `<marker>/skills/quality-playbook/` subdirectory when that marker directory already exists in the target (the full set is `install_skill.py`'s `KNOWN_ENVIRONMENTS`). Once you know the tool via any of (a)/(b)/(c), pass `--ai-tool <name>` directly and skip the marker-detection step.
2. Confirm a clone of QPB is available locally. If not, instruct the operator to clone `https://github.com/andrewstellman/quality-playbook` and tell you the clone path. The script needs `bin/install_skill.py` accessible.
3. From inside the QPB clone, run `python3 -m bin.install_skill --into <path-to-target-repo>`. Replace `<path-to-target-repo>` with the operator's target. The script scans that path for the 8 known AI-tool markers (`.claude`, `.github`, `.cursor`, `.continue`, `.codex`, `.windsurf`, `.cline`, `.aider`) and installs to the matching skill subdirectory. Alternative invocations:
   - `python3 -m bin.install_skill --into <target> --ai-tool <name>` — **the canonical install when you know which AI tool the operator is using** (which you should, after Step 1's priority order: (a) operator-told, (b) self-identified, or (c) explicitly asked). `<name>` is one of `cursor`, `claude`, `copilot` (alias `github`), `continue`, `codex`, `windsurf`, `cline`, `aider` — the full 8-tool set `install_skill.py`'s `AI_TOOL_MAP` accepts. Bypasses marker auto-detection and installs to the canonical subdirectory for the named tool. The script creates the marker directory if it doesn't exist. **`--ai-tool` is the reliable path for any tool whose CLI doesn't pre-create a project marker directory** — Codex, Windsurf, Cline, and Aider don't, and Cursor/Copilot don't always create their config folder before first project open; bare `--into` auto-detection scans for an *existing* marker and so won't find those, whereas `--ai-tool <tool>` installs to the canonical subdirectory and creates the marker dir. You (the agent) supply `--ai-tool` here on the operator's behalf once you've resolved the tool via Step 1's priority order — the operator does NOT need to name their tool in the prompt; self-identifying it and passing the flag is your job, not theirs. **Prefer `--ai-tool` over `--target` whenever the tool is known** — `--target` is reserved for operator-specified custom install locations, not as a detection-failure fallback. Mutually exclusive with `--target`.
   - `python3 -m bin.install_skill --target /path/to/install` — explicit literal install path; use only when the operator wants a custom location. Mutually exclusive with `--ai-tool`.
   - `python3 -m bin.install_skill --verbose` — emits human-prose lines alongside the structured output, including a fuller install explainer at the start.
   - Default behavior (no `--force`) preserves operator-edited files as `<file>.operator-backup-<UTC-timestamp>` on re-install. Use `--force` only if the operator explicitly wants to discard prior edits.
4. Parse the structured output. Each line is `event=<name>(\s+key=value)*`. The first event is always `event=intro` (a one-time install explainer for adopters reading verbose output). For `--into`, the environment-resolution line is `event=detected_env_inside_target target=<target> env=.cursor install_path=<full-path>` (with the actual env and resolved install path). For `--ai-tool`, the line is `event=ai_tool_explicit ai_tool=<name> target=<base> marker=<marker-dir> install_path=<full-path> marker_created=<yes|no>`, where `<marker-dir>` is one of the 8 `KNOWN_ENVIRONMENTS` markers (`.cursor` / `.claude` / `.github` / `.continue` / `.codex` / `.windsurf` / `.cline` / `.aider`). Surface any `event=smoke_check status=failed` lines to the operator with the `detail=` field intact. **If `--into <target>` produces `event=detection_failed` followed by `event=install_complete status=failed reason=no_marker_directory_found`, you should already have the AI tool's name from Step 1's priority order (operator-told, self-identified, or explicitly asked) — re-run with `--ai-tool <name>`. If for some reason you don't have an answer from any of those paths, STOP and resolve Step 1's priority order before re-running.** Do NOT pick a default tool blindly without going through (a)/(b)/(c). The `event=install_complete` line carries a verbose three-option recovery block for direct human use; for AI-agent-driven installs, the answer is always to determine the tool via Step 1's priority order and pass `--ai-tool`.
5. On success (`event=install_complete status=success`), report to the operator: the install location (from the earlier `event=detected_env_inside_target`, `event=detected_env`, or `event=target_explicit` line); the next step — tell them they run it by saying *"Run the Quality Playbook on this project"* (they do NOT open the installed `SKILL.md` themselves — that's the file you, the agent, read to execute), and point them at the README's "How to use the Quality Playbook" section for phase/iteration options; any `status=backed_up` files so the operator can review their preserved edits.
6. On failure (`event=install_complete status=failed` or `status=partial`, or a non-zero exit code), report the failing event line and the suggested remediation. Do not retry without operator confirmation — re-running over a partial install can mask the original failure.
7. **After a successful install, end your reply by displaying the Quality Playbook attribution banner verbatim as the closing element of your response** (after your summary of what you did and any next-step pointers from step 5). This is the project's install-time attribution — surface it to the operator so they see project name, author, URL, tagline, and license at the moment they pull the skill in. The installer also writes the banner to stderr at the end of a successful run; embedding it here ensures the operator sees it even when your harness captures only stdout. On a failed install (step 6), skip the banner — don't crown a failed install with attribution.

   ```
   ================================================================================
     Quality Playbook -- by Andrew Stellman
     https://github.com/andrewstellman/quality-playbook

     AI code review is good. Quality engineering is better.
     Because code that looks right can still do the wrong thing.

     Licensed under the Apache License, Version 2.0
   ================================================================================
   ```

   Reproduce the banner exactly as written above — the test suite drift-guards this block against `bin/install_skill.py`'s constants so the two sources of truth stay in sync.

For the underlying script's full options, see `bin/install_skill.py --help`.

## Mode A entry sequence (interactive coding sessions)

**DO NOT invoke `bin/run_playbook.py` from inside your agent session.**
If the operator asked "Run the Quality Playbook on this project", they
expect YOU (the agent) to walk Phases 1-6 inline using the phase
prompts in `phase_prompts/`. The runner is for operators invoking from
a bare shell, or for the post-Phase-6 iteration handoff (the runner
will refuse with a clear error if you try). See SKILL.md §"When in
doubt, default to Mode A."

This rule exists because the 2026-05-18 copilot httpx run surfaced an
agent-initiated Mode A → Mode B handoff: copilot read the launch
prompt, honored the Phase 0 install+validate sequence correctly, then
invoked `bin.run_playbook --copilot --phase 1,2,3,4,5,6` on its own
initiative. The runner now refuses such invocations structurally (env-
var based, see `bin/run_playbook.py::_check_agent_context_or_refuse`);
this prose is the prose-level companion to the mechanical defense.

**"Run the Quality Playbook on this project" means the FULL six-phase pipeline + four iteration strategies — NOT Phase 1 only.** Some agents (notably Codex Desktop on the 2026-05-18 express run) have interpreted the operator's "Run the Quality Playbook" as a Phase-1-only request because they saw "Phase 1" mentioned first in SKILL.md / phase prompts. This is a misreading. The canonical interpretation:

- "Run the Quality Playbook on this project" → walk Phases 1 → 6 inline (per Mode A entry sequence), do NOT stop at any phase boundary, run all four iteration strategies (gap / unfiltered / parity / adversarial) after Phase 6
- "Run phases 1 to N of the Quality Playbook" → explicit subset; honor the N requested
- "Continue the Quality Playbook from phase N" → resume from phase N (the operator already ran prior phases)

Phase-1-only as a default is the v1.5.3 legacy invocation behavior, restored only via explicit `python3 -m bin.run_playbook --phase 1`. Mode A "Run the Quality Playbook" is the full pipeline.

**This is the canonical Phase 0 for any interactive Mode A run** (Claude Code, Cursor, Copilot UI, Codex desktop — any session where the operator watches your chat). SKILL.md's Mode A intro points here; this section is the full protocol. **Installing the skill into the target is a MANDATORY first action — not implicit in "run the playbook".**

(The Mode-A skill-load attribution banner — full canonical block, byte-for-byte matching `bin/_purpose.print_attribution_banner()` — is the SKILL.md MANDATORY FIRST ACTION; see SKILL.md, not here. v1.5.7 090m moved the directive to its real surface — 090k/090l's parallel directives here and in `phase_prompts/phase1.md` were redundant since SKILL.md is the file the agent reads at skill-load.)

1. **Read `SKILL.md` from this repo** (the QPB source clone) to learn the Mode A walkthrough.
2. **Install the skill into your target (validator-first — v1.5.7 077/077b/078)**: run the Phase 0 install validator. **Invocation form is install-location-aware (v1.5.7 090t):** resolve the install root (the directory containing the canonical `SKILL.md` via the install-location fallback list — `.claude/skills/quality-playbook/`, `.github/skills/quality-playbook/`, `.cursor/skills/quality-playbook/`, `.codex/skills/quality-playbook/`, etc., or the QPB clone itself for self-bootstrap), then run **`python3 <install_root>/bin/qpb_validate.py <target-repo>`**. For a clone-based install, `<install_root>` is your QPB clone path so the form is `python3 <qpb-clone>/bin/qpb_validate.py <target-repo>` (the pre-090t shape). For an `install_skill`-layout adopter (channel or manual install), `<install_root>` is the marker subdir — running bare `python3 bin/qpb_validate.py <target>` from the target repo root FAILS (no `bin/` at repo root; validator lives under the marker dir). This was the root cause of the 2026-05-25 Keto run4 first-probe failure. Paste every emitted `event=` line into chat verbatim, including the run-nonce. Branch on the outcome:
   - `event=validation_complete status=ok` → the install closure is intact; proceed.
   - `status=remediable` → run each `event=remediation_suggestion`'s `command` field verbatim, then re-run the validator. For a missing/partial install the validator emits the canonical platform-correct install command, `python3 -m bin.install_skill --into <target-repo> --ai-tool <your-tool>`. `<your-tool>` is one of the 10 canonical layouts: `cursor`, `claude`, `copilot`, `github`, `continue`, `codex`, `windsurf`, `cline`, `aider`; for an interactive Claude Code session use `--ai-tool claude`. Resolve `<your-tool>` via Step 1's priority order — operator-told > self-identified > ASK; never pick a default blindly.
   - `status=blocked` → resolve the named blocker (ambiguous `--ai-tool`, missing AI CLI, validator-invoked-from-clone) and re-run.
   **Do NOT proceed past Phase 0 until `event=validation_complete status=ok`.**

   **v1.5.7 090q — anti-scavenge guard (HALT on a Phase-0 you can't resolve).** If you have run the validator, applied each `event=remediation_suggestion`'s command verbatim, re-run the validator, and STILL cannot reach `event=validation_complete status=ok`, **HALT the run and report the validator's findings to the operator.** Do NOT:
   - search the filesystem for, or install from, **other QPB checkouts / source trees** (sibling `qpb-bootstrap-*`, a benchmark repo under `repos/`, any non-this-install source, etc.);
   - run `--force` reinstalls from a foreign source to "repair" the install;
   - fall back to a **different `run_playbook.py`** or a **Mode B harness from another checkout** to drive the run.

   This install is the one under test. If its Phase 0 won't pass, surface that — do not improvise a cross-repo repair or switch execution to a foreign tree. The 2026-05-24 Ory Keto run3 was contaminated exactly this way: a sandbox-restricted compile-cache write false-failed Phase 0 (closed by 090q Task A in `bin/qpb_validate.py`), Codex scavenged the operator's other QPB checkouts (`qpb-bootstrap-v157`, `httpx-1.5.7`, a full source tree), `--force`-reinstalled from each, and finally drove a Mode-B `run_playbook.py --codex` run from `../qpb-bootstrap-v157/` — abandoning the channel-installed skill entirely. The run then tested neither the channel install nor the v1.5.7 artifact. **A failed Phase 0 is a signal to report, not a license to scavenge.** **Why the validator, not a raw install command:** it deterministically checks the full install closure (47 bundled files + scaffolding + environment) and emits the platform-correct remediation, replacing the diffuse prose install instruction that the 2026-05-17 httpx + install-path runs followed wrong three different ways. **Why the install runs from the clone:** `python3 -m bin.install_skill` resolves `bin/` as a Python package, which only exists in the QPB clone — running from the target fails with `ModuleNotFoundError: No module named 'bin'`; if you cannot `cd` into the clone, use `PYTHONPATH=<qpb-clone> python3 -m bin.install_skill --into <target-repo> --ai-tool <your-tool>`. A clean install puts `SKILL.md` + `bin/` + `references/` + `phase_prompts/` + `agents/` at the canonical install location for your tool (e.g. `.claude/skills/quality-playbook/` for Claude Code, `.github/skills/quality-playbook/` for Copilot).
3. **`cd` into the target and read the INSTALLED `SKILL.md`** (`<target>/<marker>/skills/quality-playbook/SKILL.md`) — that, NOT the QPB source clone's SKILL.md, is the canonical one you execute Phases 1-6 from. The installed tree is where the Phase 2/5/6 validators (`bin/validate_phase_artifacts.py`) and the Phase 6 gate (`quality_gate.py`) live at canonical locations.
4. **Execute Phases 1-6 per the installed SKILL.md** (Mode A walkthrough). Phase 6 verification is delegated to a fresh-context auditor sub-agent per the A-13-hybrid exception (see `phase_prompts/phase6.md` + `phase_prompts/phase6_auditor.md`). The gate verdict is **three-state** (v1.5.7 089c F15): `RESULT: GATE PASSED` → emit State B/S; `RESULT: GATE PASSED WITH CLEANUP NEEDED — N audit record-keeping gap(s)` → emit **State CN** (a legitimate, non-blocking outcome — the bug findings stand; only the audit trail has gaps); `RESULT: GATE FAILED — N substantive issue(s) must be fixed` → FAIL. Map the auditor verdict and the State P6 "What just happened" emit per the three-state rule in `phase_prompts/phase6.md` and the State templates in `references/what_just_happened.md`. You may NOT claim PASS or PASS WITH CLEANUP NEEDED when there are any substantive FAILs.

**Why this is non-negotiable.** Without the install step the Phase 2/5/6 validators and the Phase 6 gate are not at canonical locations — your run silently bypasses all artifact-contract enforcement (A-14/A-15/A-16). The **2026-05-17 httpx run reproduced exactly this failure mode**: the agent, told only "read SKILL.md and run the playbook", worked from the QPB source clone without installing into the target → validators unreachable → Phase 2 manifests entirely absent (A-19) → the gate would have failed 29 checks but the agent claimed pass. Phase 0 install is what makes the enforcement reachable.

## Canonical adopter invocations

| Host CLI | Interactive | Non-interactive (auto-approval) |
|---|---|---|
| Claude Code | `claude --dangerously-skip-permissions --model X` (operator types prompt) | `claude --dangerously-skip-permissions --model X -p "<prompt>"` |
| Copilot CLI — new (`copilot`) | `copilot --model X` (operator types prompt) | `copilot --model X --allow-all -p "<prompt>"` |
| Copilot CLI — legacy (`gh copilot`, deprecated 2025-10-25; works during grace period) | `gh copilot --model X` (operator types prompt; per-command approvals) | `gh copilot --model X --yolo --prompt "<prompt>"` |
| codex CLI (Mode B subprocess only) | n/a (invoked by `bin/run_playbook.py --codex`) | `codex exec --full-auto -m X -c model_reasoning_effort='"medium"' "<prompt>"` |
| codex desktop | open via desktop app, paste prompt in chat | n/a |

The `--allow-all` / `--yolo` / `--dangerously-skip-permissions` / `--full-auto` flag is the auto-approval signal. Omitting it in non-interactive mode causes the host CLI to silently deny filesystem operations, which produces cascading failures (install denied → playbook can't run → agent may fabricate verdicts rather than HALT). Always use the documented flag for non-interactive runs. (v1.5.7 089b F12 — surfaced 2026-05-18: chi via `gh copilot --prompt` without `--yolo` hit ~30 permission-denied ops then a fabricated Phase 6 PASS. The new standalone `copilot` CLI per 089f uses `--allow-all` as the canonical spelling; it also accepts `--yolo` as an alias.)

## Repository layout

```
AGENTS.md                ← you are here
SKILL.md                 ← the skill (operational instructions)
quality_gate.py          ← artifact validation script
LICENSE.txt
references/              ← phase-specific reference documents
agents/
  quality-playbook.agent.md       ← orchestrator agent (Copilot / general)
  quality-playbook-claude.agent.md ← orchestrator agent (Claude Code)
ai_context/
  TOOLKIT.md             ← interactive documentation for users
  DEVELOPMENT_CONTEXT.md ← development context for maintainers
bin/skill_derivation/    ← v1.5.3 four-pass derivation + divergence detection
previous_runs/v1.5.3/    ← v1.5.3 bootstrap evidence (curated REQUIREMENTS.md + Phase 3/4 artifacts)
```

## Conventions

- **Don't edit skill files without backups.** Copy to `.bak` before modifying SKILL.md or any reference file.
- **Bump the version** in SKILL.md metadata for every change. Generated artifacts stamp this version.
- **Test changes** on at least 2 benchmark repos before committing.
- **Update ai_context/ files** if your change affects users or maintainers.
