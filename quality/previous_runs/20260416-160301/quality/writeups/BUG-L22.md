# BUG-L22: SEED_CHECKS.md Absent from Artifact Contract Table
<!-- Quality Playbook v1.4.1 — Bug Writeup — 2026-04-16 -->

## Summary

SKILL.md contains a self-contradiction: the artifact contract table at lines 88-119 is declared "the canonical list — any artifact not listed here should not be gate-enforced," but `quality/SEED_CHECKS.md` is required by the Phase 5 artifact file-existence gate (line 1641) and is not in the table. An agent reading the table to understand what artifacts to create would not know to create SEED_CHECKS.md. An agent following the Phase 5 gate would fail after a Phase 0b run if the file wasn't created.

## Spec Reference

REQ-025 (Tier 3): "SEED_CHECKS.md must be added to the artifact contract table (SKILL.md:88-119) with condition 'If Phase 0b ran' — the table is declared canonical and must reflect all conditionally required artifacts."

SKILL.md line 85-88: "The quality gate (quality_gate.sh) validates these artifacts. If the gate checks for it, this skill must instruct its creation. **This is the canonical list** — any artifact not listed here should not be gate-enforced, and any gate check should trace to an artifact listed here."

SKILL.md line 1641: "If Phase 0 or 0b ran: `quality/SEED_CHECKS.md` exists as a standalone file (not inlined in PROGRESS.md)"

## The Code

```markdown
# SKILL.md:85-88 — The table's canonical claim
The quality gate (quality_gate.sh) validates these artifacts. If the gate checks for it, this
skill must instruct its creation. This is the canonical list — any artifact not listed here
should not be gate-enforced, and any gate check should trace to an artifact listed here.
```

The table at lines 88-119 has 18 rows — none include SEED_CHECKS.md. Yet Phase 5 requires it conditionally.

## Observable Consequence

When Phase 0b runs (sibling-repo seed discovery), the Phase 5 artifact file-existence gate (SKILL.md:1641) requires SEED_CHECKS.md. An agent that followed only the artifact contract table (the declared authoritative source) would not create this file. The Phase 5 gate would then fail with "SEED_CHECKS.md missing." The agent would be confused because the canonical table said nothing about this file. Additionally, quality_gate.sh does not check for SEED_CHECKS.md — consistent with the table's silence, but creating a gap in automated gate enforcement.

## The Fix

```diff
--- a/SKILL.md
+++ b/SKILL.md
@@ Lines 88-119 (artifact contract table) @@
 | AI bootstrap | `AGENTS.md` | Yes | Phase 2 |
+| Phase 0 seed list | `quality/SEED_CHECKS.md` | If Phase 0 or 0b ran | Phase 0a/0b |
 | Bug writeups | `quality/writeups/BUG-NNN.md` | If bugs found | Phase 5 |
```

This adds SEED_CHECKS.md to the canonical artifact contract table with its condition, resolving the self-contradiction between the table's canonical claim and Phase 5's gate requirement. A future version should also add gate enforcement in quality_gate.sh (conditional on detecting that Phase 0b ran).
