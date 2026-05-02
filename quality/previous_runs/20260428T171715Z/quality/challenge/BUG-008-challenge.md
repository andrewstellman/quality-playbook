# Challenge Record: BUG-008

- Trigger: no-spec-basis, missing-functionality
- Requirement: REQ-009
- Evidence reviewed: `SKILL.md:49-58`, `bin/run_playbook.py:613-618`, `bin/run_playbook.py:726-1090`
- Challenge: Could later-phase prompt path text be treated as advisory only, making the hardcoded flat layout a harmless documentation shortcut?
- Resolution: No. The prompt text is the executable brief the child agent reads before Phase 2 through Phase 6. Hardcoding `.github/skills/SKILL.md` and `.github/skills/references/...` changes what a real child tries to open.
**Verdict:** CONFIRMED
