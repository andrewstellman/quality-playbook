# Code Review — Gap Iteration (2026-04-19)

## Scope

- `agents/quality-playbook.agent.md`
- `agents/quality-playbook-claude.agent.md`
- `pytest/__main__.py`
- `README.md` / `SKILL.md` contract references for those surfaces

## Pass 1 — Structural review

1. `agents/quality-playbook.agent.md:35-43` and `agents/quality-playbook-claude.agent.md:45-55` both omit repo-root `SKILL.md` from their setup search lists. The omission contradicts the documented source-checkout launch flow. **BUG-017**.
2. `agents/quality-playbook.agent.md:11-14` conflicts with `agents/quality-playbook.agent.md:77-81` on whether the orchestrator executes Phase 1 itself. **BUG-018**.
3. `pytest/__main__.py:16-34` always executes the suite and routes node IDs into `unittest` discovery. **BUG-019**.

## Pass 2 — Requirement verification

- **REQ-018:** violated by both orchestrator prompt files; repo-root `SKILL.md` is not listed.
- **REQ-019:** violated by the general orchestrator; role block and Mode 1 instructions disagree.
- **REQ-020:** violated by the local pytest shim; documented CLI forms are neither implemented nor rejected cleanly.

## Pass 3 — Cross-surface consistency

- README / prompt bootstrap contract drift confirms **BUG-017** is user-visible, not internal only.
- Prompt-role / mode drift confirms **BUG-018** is architectural, not just wording.
- `SKILL.md` / shim CLI drift confirms **BUG-019** affects documented TDD workflows.

## Confirmed bugs

| Bug | File:Line | Summary | Severity |
|---|---|---|---|
| BUG-017 | `agents/quality-playbook.agent.md:35-43`, `agents/quality-playbook-claude.agent.md:45-55` | source-checkout bootstrap omits repo-root `SKILL.md` | MEDIUM |
| BUG-018 | `agents/quality-playbook.agent.md:11-14`, `77-81` | general orchestrator contradicts its own phase ownership | MEDIUM |
| BUG-019 | `pytest/__main__.py:16-34` | local pytest shim mis-handles documented CLI forms | MEDIUM |
