# Challenge Record: BUG-010

- Trigger: no-spec-basis
- Requirement: REQ-010
- Evidence reviewed: `SKILL.md:49-58`, `agents/quality-playbook.agent.md:37-45`, `agents/quality-playbook-claude.agent.md:45-54`
- Challenge: Is the Claude orchestrator order difference too minor to count as a real product bug?
- Resolution: No. The agent file is a shipped operator-facing entry point with its own explicit ordered list. Reversing flat vs nested Copilot changes the documented first-hit semantics for that orchestrator surface.
**Verdict:** CONFIRMED
