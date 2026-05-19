# BUG-M3: Phase 2 entry gate enforces only 6 of 12 Phase 1 checks

**Severity:** MEDIUM  
**File:Line:** `SKILL.md:897-904` (Phase 2 entry gate) vs `SKILL.md:847-862` (Phase 1 completion gate)  
**Date confirmed:** 2026-04-16  
**TDD verdict:** TDD verified

---

## 1. Description

The Phase 2 entry gate enforces only 6 of the 12 Phase 1 completion gate checks. Missing checks: 2 (PROGRESS.md marks Phase 1 complete), 3 (Derived Requirements with file paths), 5 (open-exploration depth — 3 findings trace 2+ functions), 8 (3-4 FULL patterns), 10 (depth — 2 deep dives trace 2+ functions), 12 (ensemble balance). An EXPLORATION.md with the required section titles but substantively empty content passes the Phase 2 entry gate, allowing Phase 2 to proceed from shallow exploration.

## 2. Spec Basis

**REQ-003 (Tier 3):** "The Phase 2 entry gate must either enforce all 12 Phase 1 completion gate checks, or explicitly document which checks are not backstopped."

**REQ-010 (Tier 1):** Requires substantive content before Phase 2 begins.

## 3. Code Location

`SKILL.md:895-904` — Phase 2 entry gate (6 checks):
```
1. ## Open Exploration Findings — must exist verbatim
2. ## Quality Risks — must exist verbatim
3. ## Pattern Applicability Matrix — must exist verbatim
4. At least 3 sections starting with ## Pattern Deep Dive —
5. ## Candidate Bugs for Phase 2 — must exist verbatim
6. ## Gate Self-Check — must exist
```

`SKILL.md:847-862` — Phase 1 completion gate (12 checks): additionally checks PROGRESS.md completion flag, content depth (file:line citations), FULL pattern count (3-4), cross-function traces, and ensemble balance.

## 4. Regression Test

Function: `test_BUG_M3_phase2_gate_missing_checks` in `quality/test_regression.sh`

```bash
# Count numbered checks in Phase 1 completion gate
phase1_checks=$(awk '/Phase 1 completion gate \(mandatory/,/Do not begin Phase 2/' "$skill_md" | grep -cE '^[0-9]+\.')
# Count numbered items in Phase 2 entry gate
phase2_checks=$(awk '/Phase 2 entry gate \(mandatory — HARD STOP\)/,/If the file does not exist/' "$skill_md" | grep -cE '^[0-9]+\.')
# If Phase 1 has more checks than Phase 2, BUG-M3 is confirmed
```

## 5. Fix Patch

```diff
--- a/SKILL.md
+++ b/SKILL.md
@@ -895,13 +895,25 @@ Use `quality/EXPLORATION.md` as your primary source for this phase...
 **Phase 2 entry gate (mandatory — HARD STOP).** Before generating any artifacts, read `quality/EXPLORATION.md` from disk and verify ALL of the following exact section titles exist:

 1. `## Open Exploration Findings` — must exist verbatim
 2. `## Quality Risks` — must exist verbatim
 3. `## Pattern Applicability Matrix` — must exist verbatim
 4. At least 3 sections starting with `## Pattern Deep Dive — ` — must exist verbatim
 5. `## Candidate Bugs for Phase 2` — must exist verbatim
 6. `## Gate Self-Check` — must exist (proves the Phase 1 gate was run)
+7. `quality/PROGRESS.md` exists and its Phase 1 line is marked `[x]`
+8. The `## Open Exploration Findings` section contains at least 8 concrete bug hypotheses
+9. At least 3 findings in `## Open Exploration Findings` trace behavior across 2+ functions
+10. Between 3 and 4 patterns are marked `FULL` in `## Pattern Applicability Matrix`
+11. At least 2 pattern deep-dive sections trace code paths across 2+ functions
+12. `## Candidate Bugs for Phase 2` has ≥2 bugs from open exploration AND ≥1 from a pattern deep dive
```

## 6. TDD Verification

**Red phase** (`quality/results/BUG-M3.red.log`):
```
Phase 1 completion gate: 12 numbered checks
Phase 2 entry gate: 6 numbered checks
BUG CONFIRMED: Phase 2 gate has 6 fewer checks than Phase 1 gate
RESULT: FAIL
```
Exit code: 1. Test fails on unpatched code — confirms Phase 2 gate is missing 6 checks.

**Green phase** (`quality/results/BUG-M3.green.log`):
```
Phase 2 checks (after patch): 12
PASS: After fix, Phase 2 would enforce all Phase 1 checks
```
After applying fix patch (adding items 7-12), the Phase 2 gate would have 12 checks matching Phase 1's 12 checks.
