# Gap Iteration Code Review — quality-playbook

Date: 2026-04-28
Strategy: gap
Primary input: `quality/EXPLORATION_MERGED.md`

## Scope

This review targeted the areas the baseline explored only lightly:

1. Later-phase prompt generation in `bin/run_playbook.py`.
2. Repository-side SKILL discovery and warning behavior in `bin/benchmark_lib.py` and `bin/run_playbook.py`.
3. Orchestrator setup instructions in `agents/quality-playbook*.md`.

## Confirmed bugs

1. **BUG-008** — later-phase prompts still hardcode `.github/skills/SKILL.md` / `.github/skills/references/...` instead of using the documented fallback list.
2. **BUG-009** — repository-side helper discovery still uses an outdated path tuple and target-resolution warning text omits the nested Copilot path.
3. **BUG-010** — the Claude orchestrator agent reverses the flat-vs-nested Copilot fallback order relative to the live skill.

## Why these are real

- The live skill defines one canonical four-path order at `SKILL.md:49-58`.
- The entry prompts already honor that contract through `SKILL_FALLBACK_GUIDE`, proving the runner has an authoritative wording source.
- The later-phase prompts, helper tuple/warning text, and Claude orchestrator each diverge from that same contract in a way that can change which path a real run resolves.

## Recommended repair shape

1. Share one canonical path-list constant across prompt builders and helper detection.
2. Update the target-resolution warning to name all four supported paths.
3. Rewrite the Claude orchestrator setup list to match the live skill exactly.
