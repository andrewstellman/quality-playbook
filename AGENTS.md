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
| `bin/skill_derivation/runners.py` | LLM runner abstraction — four concrete runners: `ClaudeRunner` (`claude --print`), `CopilotRunner` (`gh copilot --prompt`), `CodexRunner` (`codex exec --full-auto`, codex-cli 0.125+), `CursorRunner` (`cursor agent --print --force`, cursor-cli 3.1.10+) | When adding a new LLM backend or tuning subprocess invocation |
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
cp "$QPB"/SKILL.md .github/skills/SKILL.md
cp "$QPB"/.github/skills/quality_gate/quality_gate.py .github/skills/quality_gate.py
cp "$QPB"/references/* .github/skills/references/
cp "$QPB"/phase_prompts/*.md .github/skills/phase_prompts/
# v1.5.6: agents/*.md needed by README Step 4's `claude --agent agents/...` invocation.
cp "$QPB"/agents/*.md .github/skills/agents/
# v1.5.6 BUG-005: bin/citation_verifier.py needed for quality_gate.py's
# byte-equality citation check (without it, the gate falls back to a WARN path).
cp "$QPB"/bin/citation_verifier.py .github/skills/bin/citation_verifier.py
# v1.5.7 F-1: reference_docs_ingest.py + its dependency benchmark_lib.py are
# now part of the bundle (without them, Phase 1's `python -m bin.reference_docs_ingest`
# hits ModuleNotFoundError and the entire run hard-stops).
cp "$QPB"/bin/reference_docs_ingest.py .github/skills/bin/reference_docs_ingest.py
cp "$QPB"/bin/benchmark_lib.py .github/skills/bin/benchmark_lib.py
# v1.5.2+: single reference_docs/ tree at the target repo root.
mkdir -p reference_docs reference_docs/cite
# Optional: append suggested .gitignore rules for adopters.
cat "$QPB"/skill-template.gitignore >> .gitignore
```

**Claude Code:**
```bash
mkdir -p .claude/skills/quality-playbook/references
mkdir -p .claude/skills/quality-playbook/phase_prompts
mkdir -p .claude/skills/quality-playbook/agents
mkdir -p .claude/skills/quality-playbook/bin
cp "$QPB"/SKILL.md .claude/skills/quality-playbook/SKILL.md
cp "$QPB"/.github/skills/quality_gate/quality_gate.py .claude/skills/quality-playbook/quality_gate.py
cp "$QPB"/references/* .claude/skills/quality-playbook/references/
cp "$QPB"/phase_prompts/*.md .claude/skills/quality-playbook/phase_prompts/
# v1.5.6: agents/*.md needed by README Step 4's `claude --agent agents/...` invocation.
cp "$QPB"/agents/*.md .claude/skills/quality-playbook/agents/
# v1.5.6 BUG-005: bin/citation_verifier.py needed for quality_gate.py's
# byte-equality citation check (without it, the gate falls back to a WARN path).
cp "$QPB"/bin/citation_verifier.py .claude/skills/quality-playbook/bin/citation_verifier.py
# v1.5.7 F-1: reference_docs_ingest.py + its dependency benchmark_lib.py are
# now part of the bundle (without them, Phase 1's `python -m bin.reference_docs_ingest`
# hits ModuleNotFoundError and the entire run hard-stops).
cp "$QPB"/bin/reference_docs_ingest.py .claude/skills/quality-playbook/bin/reference_docs_ingest.py
cp "$QPB"/bin/benchmark_lib.py .claude/skills/quality-playbook/bin/benchmark_lib.py
# v1.5.2+: single reference_docs/ tree at the target repo root.
mkdir -p reference_docs reference_docs/cite
cat "$QPB"/skill-template.gitignore >> .gitignore
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

   (c) **ASK the operator** if neither (a) nor (b) applies (e.g., you're a generic orchestrator without a tool identity, or the project's target tool is genuinely ambiguous): "Which AI tool will use this project? (cursor, claude, copilot, or continue)" — before running the install. Don't guess.

   The script auto-detects `.claude/` → `.claude/skills/quality-playbook/`, `.github/` → `.github/skills/quality-playbook/`, `.cursor/` → `.cursor/skills/quality-playbook/`, `.continue/` → `.continue/skills/quality-playbook/` when those marker directories already exist. Once you know the tool via any of (a)/(b)/(c), pass `--ai-tool <name>` directly and skip the marker-detection step.
2. Confirm a clone of QPB is available locally. If not, instruct the operator to clone `https://github.com/andrewstellman/quality-playbook` and tell you the clone path. The script needs `bin/install_skill.py` accessible.
3. From inside the QPB clone, run `python3 -m bin.install_skill --into <path-to-target-repo>`. Replace `<path-to-target-repo>` with the operator's target. The script scans that path for known AI-tool markers (`.claude`, `.github`, `.cursor`, `.continue`) and installs to the matching skill subdirectory. Alternative invocations:
   - `python3 -m bin.install_skill --into <target> --ai-tool <name>` — **the canonical install when you know which AI tool the operator is using** (which you should, after Step 1's priority order: (a) operator-told, (b) self-identified, or (c) explicitly asked). `<name>` is one of `cursor`, `claude`, `copilot` (alias `github`), `continue`. Bypasses marker auto-detection and installs to the canonical subdirectory for the named tool. The script creates the marker directory if it doesn't exist (Cursor and Copilot don't always create their config folder on first project open). **Prefer `--ai-tool` over `--target` whenever the tool is known** — `--target` is reserved for operator-specified custom install locations, not as a detection-failure fallback. Mutually exclusive with `--target`.
   - `python3 -m bin.install_skill --target /path/to/install` — explicit literal install path; use only when the operator wants a custom location. Mutually exclusive with `--ai-tool`.
   - `python3 -m bin.install_skill --verbose` — emits human-prose lines alongside the structured output, including a fuller install explainer at the start.
   - Default behavior (no `--force`) preserves operator-edited files as `<file>.operator-backup-<UTC-timestamp>` on re-install. Use `--force` only if the operator explicitly wants to discard prior edits.
4. Parse the structured output. Each line is `event=<name>(\s+key=value)*`. The first event is always `event=intro` (a one-time install explainer for adopters reading verbose output). For `--into`, the environment-resolution line is `event=detected_env_inside_target target=<target> env=.cursor install_path=<full-path>` (with the actual env and resolved install path). For `--ai-tool`, the line is `event=ai_tool_explicit ai_tool=<name> target=<base> marker=<.cursor|.claude|.github|.continue> install_path=<full-path> marker_created=<yes|no>`. Surface any `event=smoke_check status=failed` lines to the operator with the `detail=` field intact. **If `--into <target>` produces `event=detection_failed` followed by `event=install_complete status=failed reason=no_marker_directory_found`, you should already have the AI tool's name from Step 1's priority order (operator-told, self-identified, or explicitly asked) — re-run with `--ai-tool <name>`. If for some reason you don't have an answer from any of those paths, STOP and resolve Step 1's priority order before re-running.** Do NOT pick a default tool blindly without going through (a)/(b)/(c). The `event=install_complete` line carries a verbose three-option recovery block for direct human use; for AI-agent-driven installs, the answer is always to determine the tool via Step 1's priority order and pass `--ai-tool`.
5. On success (`event=install_complete status=success`), report to the operator: the install location (from the earlier `event=detected_env_inside_target`, `event=detected_env`, or `event=target_explicit` line); the next step (point at the installed `SKILL.md` and the README's "How to use the Quality Playbook" section); any `status=backed_up` files so the operator can review their preserved edits.
6. On failure (`event=install_complete status=failed` or `status=partial`, or a non-zero exit code), report the failing event line and the suggested remediation. Do not retry without operator confirmation — re-running over a partial install can mask the original failure.

For the underlying script's full options, see `bin/install_skill.py --help`.

## Mode A entry sequence (interactive coding sessions)

**This is the canonical Phase 0 for any interactive Mode A run** (Claude Code, Cursor, Copilot UI, Codex desktop — any session where the operator watches your chat). SKILL.md's Mode A intro points here; this section is the full protocol. **Installing the skill into the target is a MANDATORY first action — not implicit in "run the playbook".**

1. **Read `SKILL.md` from this repo** (the QPB source clone) to learn the Mode A walkthrough.
2. **Install the skill into your target (validator-first — v1.5.7 077/077b/078)**: run the Phase 0 install validator, `python3 <qpb-clone>/bin/qpb_validate.py <target-repo>` (it also works from an installed location). Paste every emitted `event=` line into chat verbatim, including the run-nonce. Branch on the outcome:
   - `event=validation_complete status=ok` → the install closure is intact; proceed.
   - `status=remediable` → run each `event=remediation_suggestion`'s `command` field verbatim, then re-run the validator. For a missing/partial install the validator emits the canonical platform-correct install command, `python3 -m bin.install_skill --into <target-repo> --ai-tool <your-tool>`. `<your-tool>` is one of the 10 canonical layouts: `cursor`, `claude`, `copilot`, `github`, `continue`, `codex`, `windsurf`, `cline`, `aider`; for an interactive Claude Code session use `--ai-tool claude`. Resolve `<your-tool>` via Step 1's priority order — operator-told > self-identified > ASK; never pick a default blindly.
   - `status=blocked` → resolve the named blocker (ambiguous `--ai-tool`, missing AI CLI, validator-invoked-from-clone) and re-run.
   **Do NOT proceed past Phase 0 until `event=validation_complete status=ok`.** **Why the validator, not a raw install command:** it deterministically checks the full install closure (47 bundled files + scaffolding + environment) and emits the platform-correct remediation, replacing the diffuse prose install instruction that the 2026-05-17 httpx + install-path runs followed wrong three different ways. **Why the install runs from the clone:** `python3 -m bin.install_skill` resolves `bin/` as a Python package, which only exists in the QPB clone — running from the target fails with `ModuleNotFoundError: No module named 'bin'`; if you cannot `cd` into the clone, use `PYTHONPATH=<qpb-clone> python3 -m bin.install_skill --into <target-repo> --ai-tool <your-tool>`. A clean install puts `SKILL.md` + `bin/` + `references/` + `phase_prompts/` + `agents/` at the canonical install location for your tool (e.g. `.claude/skills/quality-playbook/` for Claude Code, `.github/skills/quality-playbook/` for Copilot).
3. **`cd` into the target and read the INSTALLED `SKILL.md`** (`<target>/<marker>/skills/quality-playbook/SKILL.md`) — that, NOT the QPB source clone's SKILL.md, is the canonical one you execute Phases 1-6 from. The installed tree is where the Phase 2/5/6 validators (`bin/validate_phase_artifacts.py`) and the Phase 6 gate (`quality_gate.py`) live at canonical locations.
4. **Execute Phases 1-6 per the installed SKILL.md** (Mode A walkthrough). Phase 6 verification is delegated to a fresh-context auditor sub-agent per the A-13-hybrid exception (see `phase_prompts/phase6.md` + `phase_prompts/phase6_auditor.md`).

**Why this is non-negotiable.** Without the install step the Phase 2/5/6 validators and the Phase 6 gate are not at canonical locations — your run silently bypasses all artifact-contract enforcement (A-14/A-15/A-16). The **2026-05-17 httpx run reproduced exactly this failure mode**: the agent, told only "read SKILL.md and run the playbook", worked from the QPB source clone without installing into the target → validators unreachable → Phase 2 manifests entirely absent (A-19) → the gate would have failed 29 checks but the agent claimed pass. Phase 0 install is what makes the enforcement reachable.

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
