# Gap Auditor 1 Notes
> Model: gpt-5.4
> Date: 2026-04-28 · Project: quality-playbook

1. `phase2_prompt()` through `phase6_prompt()` still hardcode `.github/skills/...` instead of reusing the documented fallback list. This is a real portability drift under REQ-009.
2. `benchmark_lib.SKILL_INSTALL_LOCATIONS` and `resolve_target_dirs()` still teach an outdated or incomplete support matrix, including a missing nested Copilot warning path. This is a real repository-side detection drift under REQ-010.
3. `agents/quality-playbook-claude.agent.md` still reverses flat vs nested Copilot order relative to the live skill and general orchestrator. This is a real shipped-doc divergence under REQ-010.
