# Gap Iteration Triage — quality-playbook

Date: 2026-04-28
Strategy: gap

| Bug | Auditor support | Verdict | Notes |
| --- | --- | --- | --- |
| BUG-008 | 2/2 direct | Confirmed | Later-phase prompt family still hardcodes flat Copilot paths. |
| BUG-009 | 2/2 direct | Confirmed | Helper tuple/warning text no longer matches the canonical four-path list. |
| BUG-010 | 2/2 direct | Confirmed | Claude orchestrator order disagrees with the live skill and generic orchestrator. |

## Triage notes

1. BUG-008 is a code-path trace issue, not a hypothetical: the later-phase prompts explicitly tell the child which files to read next.
2. BUG-009 is partly executable and partly UX-facing, but both surfaces derive from the same stale install-location tuple.
3. BUG-010 remains a separate low-severity bug because it is a shipped operator-facing agent surface with its own explicit ordered list.
