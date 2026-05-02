# Gap Auditor 2 Notes
> Model: claude-opus-4.7
> Date: 2026-04-28 · Project: quality-playbook

1. The entry prompts were hardened, but the later-phase prompt family still assumes a flat Copilot install. That is the kind of success-shaped portability regression REQ-009 exists to catch.
2. Helper discovery and warning text are both operator-facing product surfaces. Their stale fallback ordering and missing nested path are enough to confirm BUG-009 even before a child run starts.
3. The Claude orchestrator should not teach a different Copilot precedence rule than `SKILL.md`; the reversed order is a small but real contract split and supports BUG-010.
