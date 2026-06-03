# CI Integration

This document covers running QPB's `bin/run_playbook.py` from CI/CD
pipelines, where stdin is typically not a TTY.

## The TTY requirement

QPB v1.5.7+ requires `--operator-invoked` AND stdin-is-TTY to bypass
the agent-context refusal. This combination prevents AI agents from
fabricating the bypass (instruction 085, defense against the
2026-05-18 codex desktop bypass attempt: the agent read `--help`,
found `--operator-invoked`, and passed it proactively).

For CI pipelines where stdin is piped (no TTY), set the environment
variable `QPB_OPERATOR_NON_TTY_OVERRIDE=1` on the operator's CI step.
This grants the same bypass as TTY stdin.

## Example

GitHub Actions:

```yaml
- name: Run Quality Playbook
  env:
    QPB_OPERATOR_NON_TTY_OVERRIDE: "1"
  run: python3 -m bin.run_playbook --operator-invoked --full-run .
```

GitLab CI:

```yaml
qpb:
  variables:
    QPB_OPERATOR_NON_TTY_OVERRIDE: "1"
  script:
    - python3 -m bin.run_playbook --operator-invoked --full-run .
```

## Why this env var is documented HERE and not elsewhere

The TTY-isatty hardening (085) exists because AI agents (Codex
desktop, Claude Code, GitHub Copilot, etc.) read documentation to
find bypass flags. If `QPB_OPERATOR_NON_TTY_OVERRIDE` were documented
in SKILL.md, AGENTS.md, the `--help` text, or the refusal error
message, agents would learn it and use it — defeating the whole
point.

This document is intended for human operators wiring up CI. It is not
loaded by any agent's launch contract. Adopters reading CI setup docs
find it; agents reading the playbook entry contract do not.
