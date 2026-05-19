# Challenge Record: BUG-009

- Trigger: no-spec-basis
- Requirement: REQ-010
- Evidence reviewed: `SKILL.md:49-58`, `bin/benchmark_lib.py:42-47`, `bin/benchmark_lib.py:144-164`, `bin/run_playbook.py:592-597`
- Challenge: Is the helper tuple merely an internal preference that does not affect the product surface?
- Resolution: No. `detect_repo_skill_version()`, `find_installed_skill()`, and `resolve_target_dirs()` expose that tuple directly through displayed version selection and install-warning behavior.
**Verdict:** CONFIRMED
