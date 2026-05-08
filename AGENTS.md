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
| `ai_context/TOOLKIT.md` | User-facing interactive documentation | When helping a user set up or run the playbook |
| `ai_context/DEVELOPMENT_CONTEXT.md` | Maintainer context (architecture, benchmarking, known issues) | When working on the skill itself |
| `agents/quality-playbook.agent.md` | Orchestrator agent (Copilot / general format) | When setting up automated phase-by-phase execution |
| `agents/quality-playbook-claude.agent.md` | Orchestrator agent (Claude Code format, uses sub-agents) | When running in Claude Code with automatic orchestration |

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

1. Confirm the operator's target repo (e.g., `~/Documents/myrepo`) and which AI tool they use. The script auto-detects `.claude/` → `.claude/skills/quality-playbook/`, `.github/` → `.github/skills/quality-playbook/`, `.cursor/` → `.cursor/skills/quality-playbook/`, `.continue/` → `.continue/skills/quality-playbook/`.
2. Confirm a clone of QPB is available locally. If not, instruct the operator to clone `https://github.com/andrewstellman/quality-playbook` and tell you the clone path. The script needs `bin/install_skill.py` accessible.
3. From inside the QPB clone, run `python3 -m bin.install_skill --into <path-to-target-repo>`. Replace `<path-to-target-repo>` with the operator's target. The script scans that path for known AI-tool markers (`.claude`, `.github`, `.cursor`, `.continue`) and installs to the matching skill subdirectory. Alternative invocations:
   - `python3 -m bin.install_skill --into <target> --ai-tool <name>` — **v1.5.6+ recommended fallback when auto-detection fails.** Bypass marker auto-detection and install to the canonical subdirectory for the named tool. `<name>` is one of `cursor`, `claude`, `copilot` (alias `github`), `continue`. The script creates the marker directory if it doesn't exist (Cursor and Copilot don't always create their config folder on first project open). Use this whenever the operator told you which tool they're using and `--into` alone fails with `event=detection_failed`.
   - `python3 -m bin.install_skill --target /path/to/install` — explicit literal install path; use only when the operator wants a custom location. Mutually exclusive with `--ai-tool`.
   - `python3 -m bin.install_skill --verbose` — emits human-prose lines alongside the structured output, including a fuller install explainer at the start.
   - Default behavior (no `--force`) preserves operator-edited files as `<file>.operator-backup-<UTC-timestamp>` on re-install. Use `--force` only if the operator explicitly wants to discard prior edits.
4. Parse the structured output. Each line is `event=<name>(\s+key=value)*`. The first event is always `event=intro` (a one-time install explainer for adopters reading verbose output). For `--into`, the environment-resolution line is `event=detected_env_inside_target target=<target> env=.cursor install_path=<full-path>` (with the actual env and resolved install path). For `--ai-tool`, the line is `event=ai_tool_explicit ai_tool=<name> target=<base> marker=<.cursor|.claude|.github|.continue> install_path=<full-path> marker_created=<yes|no>`. Surface any `event=smoke_check status=failed` lines to the operator with the `detail=` field intact. **If `--into <target>` produces `event=detection_failed` followed by `event=install_complete status=failed reason=no_marker_directory_found`, do NOT give up — re-run with `--ai-tool <name>` based on what the operator told you in Step 1.** The `event=install_complete` line carries a three-option recovery block in its prose explaining the same.
5. On success (`event=install_complete status=success`), report to the operator: the install location (from the earlier `event=detected_env_inside_target`, `event=detected_env`, or `event=target_explicit` line); the next step (point at the installed `SKILL.md` and the README's "How to use the Quality Playbook" section); any `status=backed_up` files so the operator can review their preserved edits.
6. On failure (`event=install_complete status=failed` or `status=partial`, or a non-zero exit code), report the failing event line and the suggested remediation. Do not retry without operator confirmation — re-running over a partial install can mask the original failure.

For the underlying script's full options, see `bin/install_skill.py --help`.

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
