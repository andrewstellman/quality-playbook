# BUG-L25: Phase 2 Entry Gate Omits 120-Line Minimum Check (Extends BUG-M3)
<!-- Quality Playbook v1.4.1 — Bug Writeup — 2026-04-16 -->

## Summary

SKILL.md's Phase 1 completion gate includes 12 checks; the first (SKILL.md:850) requires "at least 120 lines of substantive content" in EXPLORATION.md. The Phase 2 entry gate (SKILL.md:897-904) is supposed to backstop Phase 1 requirements when Phase 2 runs in a new session. BUG-M3 identified that checks 2, 3, 5, 8, 10, 12 were missing from the Phase 2 entry gate. The BUG-M3 fix patch adds those six checks — but check #1 (120-line minimum) remains absent. After applying the BUG-M3 fix, an EXPLORATION.md with six section title stubs (~15 lines total) still passes the Phase 2 entry gate, allowing Phase 2 to produce shallow requirements from thin exploration.

## Spec Reference

REQ-028 (Tier 3): "Phase 2 entry gate must enforce Phase 1 completion gate check #1 (at least 120 lines of substantive content in EXPLORATION.md). This extends REQ-003 (BUG-M3) — the BUG-M3 fix addresses checks 2,3,5,8,10,12 but not check #1."

SKILL.md:850 (Phase 1 completion gate, check #1): "The document has at least 120 lines of substantive content (not counting blank lines, headers, or list markers)."

SKILL.md:897-904 (Phase 2 entry gate): Lists 6 section title checks — ## Problem Context, ## Observable Symptoms, ## Root Cause Analysis, ## Scope and Impact, ## Constraints and Requirements, ## Open Questions. No line count minimum.

## The Code

```markdown
# SKILL.md:846-862 — Phase 1 completion gate (12 checks)
Phase 1 completion gate (mandatory — HARD STOP):
1. The document has at least 120 lines of substantive content
2. Contains section "## Problem Context" ...
3. Contains section "## Observable Symptoms" ...
[... 9 more checks ...]
```

```markdown
# SKILL.md:897-904 — Phase 2 entry gate (6 checks — check #1 ABSENT)
Phase 2 entry gate (mandatory — HARD STOP):
1. Contains section "## Problem Context"
2. Contains section "## Observable Symptoms"
3. Contains section "## Root Cause Analysis"
4. Contains section "## Scope and Impact"
5. Contains section "## Constraints and Requirements"
6. Contains section "## Open Questions"
```

The 6 section-title checks are checks 2-7 from Phase 1 (not an exact mapping), but the 120-line minimum (Phase 1 check #1) is absent in both the original Phase 2 entry gate and after BUG-M3's fix.

## Observable Consequence

Failure cascade:
1. Agent completes Phase 1 with a fully-developed 200-line EXPLORATION.md (Phase 1 gate passes).
2. New session: agent reads EXPLORATION.md section headings only (summarizes to ~15 lines).
3. Phase 2 entry gate: checks 6 section titles — all present — PASS.
4. Phase 2 proceeds with 15-line stub as its exploration basis.
5. Requirements are shallow (missing nuance from the 185 omitted lines).
6. Test cases miss edge cases.
7. Bugs escape to production.

The 120-line check is the primary defense against this cascade — it's check #1 in Phase 1 for a reason. Its absence from Phase 2 entry gate leaves the cascade path fully open.

## The Fix

Spec-primary fix: add check #1 to Phase 2 entry gate in SKILL.md:897-904.

```diff
--- a/SKILL.md
+++ b/SKILL.md
@@ Phase 2 entry gate (SKILL.md:897) @@
 Phase 2 entry gate (mandatory — HARD STOP):
-1. Contains section "## Problem Context"
+1. The document has at least 120 lines of substantive content (not counting blank lines, headers, or list markers)
+2. Contains section "## Problem Context"
-2. Contains section "## Observable Symptoms"
+3. Contains section "## Observable Symptoms"
-3. Contains section "## Root Cause Analysis"
+4. Contains section "## Root Cause Analysis"
-4. Contains section "## Scope and Impact"
+5. Contains section "## Scope and Impact"
-5. Contains section "## Constraints and Requirements"
+6. Contains section "## Constraints and Requirements"
-6. Contains section "## Open Questions"
+7. Contains section "## Open Questions"
```

No fix patch created — spec-primary fix. The BUG-M3 fix patch should be extended to also include this check when implemented.
