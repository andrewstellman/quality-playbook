# BUG-L21: Phase 5 Has No Entry Gate for Phase 4 Artifacts
<!-- Quality Playbook v1.4.1 — Bug Writeup — 2026-04-16 -->

## Summary

SKILL.md applies an entry gate pattern inconsistently across phases. Phase 2 has a mandatory "HARD STOP" entry gate that mechanically verifies Phase 1 artifacts before any Phase 2 work begins. Phase 5 has no equivalent — it starts by reading PROGRESS.md (agent-maintained prose) and only verifies Phase 4 completion at the terminal gate, at the END of Phase 5. This means an agent that skips Phase 4 can complete all of Phase 5 before discovering the problem, wasting the work.

## Spec Reference

REQ-024 (Tier 3): "Phase 5 must include an entry gate that mechanically verifies Phase 4 artifacts (triage file and individual auditor reports) exist before any Phase 5 work begins, mirroring the fail-early pattern of the Phase 2 entry gate."

SKILL.md line 897: "Phase 2 entry gate (mandatory — HARD STOP). Before generating any artifacts, read quality/EXPLORATION.md from disk and verify ALL of the following exact section titles exist."

## The Code

```markdown
# SKILL.md:897-907 — Phase 2: CORRECT fail-early pattern
**Phase 2 entry gate (mandatory — HARD STOP).** Before generating any artifacts, read
`quality/EXPLORATION.md` from disk and verify ALL of the following exact section titles exist
(grep or search — do not rely on memory):
1. `## Open Exploration Findings` — must exist verbatim
2. `## Quality Risks` — must exist verbatim
...
If the file does not exist, has fewer than 120 lines, or is missing ANY of these exact section
titles, STOP and go back to Phase 1.

# SKILL.md:1573-1590 — Phase 5: NO entry gate
**Required references for this phase:**
- `quality/PROGRESS.md` — cumulative BUG tracker (authoritative finding list)
...
Re-read `quality/PROGRESS.md` — specifically the cumulative BUG tracker.
```

Phase 5 reads PROGRESS.md (prose) but doesn't check for triage or auditor files. The only Phase 4 check is at the terminal gate (line 1611): "The terminal gate may run only if Phase 3 and Phase 4 are both complete, or explicitly marked skipped with rationale in PROGRESS.md." This fires AFTER all Phase 5 work.

## Observable Consequence

An agent that writes "Phase 4: complete" in PROGRESS.md without running the spec audit can proceed through all of Phase 5 — including TDD verification, writeup generation, closure reports — before the terminal gate reveals the problem. All that work must be redone after Phase 4 actually runs. The Phase 2 design prevents this scenario by checking inputs before starting.

## The Fix

```diff
--- a/SKILL.md
+++ b/SKILL.md
@@ Phase 5 opening (after "Required references" section) @@
+**Phase 5 entry gate (mandatory — verify Phase 4 is complete before proceeding).**
+Before beginning Phase 5 work, verify both:
+1. A triage file exists at `quality/spec_audits/` (any file matching `*triage*`)
+2. At least one individual auditor report exists at `quality/spec_audits/` (any file matching `*auditor*`)
+
+If either artifact is missing, STOP. Go back and complete Phase 4 before proceeding.
+Do not rely on PROGRESS.md checkbox — check the actual artifact files.
+This gate exists because the terminal gate (at the end of Phase 5) fires too late:
+an agent that skips Phase 4 completes all Phase 5 work before discovering the problem.
```

This adds a fail-early entry gate to Phase 5 that mechanically checks for Phase 4 artifact files, mirroring the Phase 2 entry gate pattern.
