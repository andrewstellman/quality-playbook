# Quality Playbook v1.3.7 — Review Instructions

You are reviewing the output of the Quality Playbook v1.3.7, an AI coding skill that generates quality engineering infrastructure for a codebase. The skill was run against this repository and produced the artifacts in quality/.

Read the skill definition at .github/skills/SKILL.md and its references in .github/skills/references/, then review the generated quality/ directory for correctness and completeness.

## Bootstrap detection

If this repository's primary product is the quality playbook skill itself (i.e., SKILL.md is at the repo root and benchmark/ contains a defect dataset), this is a bootstrap run — the skill was pointed at its own repository. Pay special attention to whether the generated requirements focus on the skill's correctness (phase sequencing, template accuracy, reference file consistency) rather than on the benchmark tooling.

## Score two dimensions on a 1-10 scale

### Process compliance — Did the agent follow the skill's protocol?

- Phase sequencing (1 → 2 → 2b → 2c → 2d → 3)
- PROGRESS.md checkpoints written at each phase boundary
- Terminal Gate Verification section present in PROGRESS.md with explicit BUG count
- Metadata consistency check (requirement count matches across REQUIREMENTS.md header, PROGRESS.md, COVERAGE_MATRIX.md)
- With docs field accuracy (true if docs_gathered/ was read, false otherwise)
- Closure status for every finding (confirmed open, fixed, or exempt — no bare "open")
- Pre-audit docs validation (triage checked for project documentation section)

### Output quality — Are the artifacts useful and accurate?

- REQUIREMENTS.md: Do requirements reflect actual code behavior, not generic software qualities?
- CONTRACTS.md: Are behavioral contracts tied to real functions/methods in the codebase?
- Functional tests: Do they compile/run? Do they test real behavior, not mocks of themselves?
- Code reviews: Do they find real issues, or are they padding with style nits?
- Spec audit triage: Are findings genuinely new, or duplicates of code review findings?
- COMPLETENESS_REPORT.md: Does it cross-check code review findings against requirements?
- Terminal gate: Is the BUG count correct? Were all BUG- entries actually counted?

## Bug reporting

List any bugs found (using BUG-N format), categorized as:

- **Process bug**: The agent violated a skill instruction
- **Content bug**: A generated artifact contains incorrect information
- **Tooling bug**: A referenced file path, import, or command is wrong

## Summary

End with a 2-3 sentence summary of what v1.3.7 improved over previous versions and what still needs work.
