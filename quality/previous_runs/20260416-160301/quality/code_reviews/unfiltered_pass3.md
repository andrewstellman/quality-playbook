# Code Review — Pass 3: Cross-Requirement Consistency (Unfiltered Iteration)

<!-- Quality Playbook v1.4.1 — Unfiltered Iteration Code Review Pass 3 — 2026-04-16 -->

**Pass type:** Cross-requirement consistency — pairs of requirements sharing fields, constants, or policies.
**Source:** Unfiltered iteration — checking consistency between new requirements (REQ-019 to REQ-021) and existing ones.

---

## Shared Concept: ls-glob Detection Pattern (REQ-014 vs REQ-015 vs REQ-016 vs REQ-019)

**Requirements:** REQ-014 (functional test detection consistency), REQ-015 (extension detection — find-based), REQ-016 (code_reviews detection — find-based), REQ-019 (functional test existence — find-based)

**What REQ-014 claims:** "quality_gate.sh must use a consistent file-detection method across all artifact checks. Using ls globs for functional test detection while using find for language detection creates an inconsistency."

**What REQ-015 claims:** "Line 479 ls-glob must be replaced with find-based detection" (extension detection — already confirmed as BUG-M12)

**What REQ-016 claims:** "Line 143 ls-glob must be replaced with find-based detection" (code_reviews directory — already confirmed as BUG-M13)

**What REQ-019 claims:** "Line 124 ls-glob must be replaced with find-based detection" (file existence check — new finding CAND-U1)

**Consistency:** CONSISTENT — all four requirements agree on the same constraint (find-based detection throughout). The difference is which specific lines they target. They are additive, not contradictory.

**Code evidence:**
- Line 124: `ls` glob — VIOLATED (REQ-019)
- Line 143: `ls` glob — VIOLATED (REQ-016, BUG-M13)
- Line 479: `ls` glob — VIOLATED (REQ-015, BUG-M12)
- Lines 449-454: `find` — compliant
- Lines 486-495: `find` — compliant

**Analysis:** The pattern of violations is consistent: ls-glob is used in checking artifact existence, find is used in language detection. The fix for all ls-glob instances is the same pattern (`find ... -print -quit | grep -q .`). A unified fix patch should cover lines 124, 143, 479, and the BUG-M8 locations (152-153, 331, 567-568, 595) to establish full consistency.

---

## Shared Concept: Bug ID Format (REQ-020 vs SKILL.md:1615 vs BUGS.md conventions)

**Requirements:** REQ-020 (heading regex must match severity-prefix IDs)

**What REQ-020 claims:** "The regex `^### BUG-[0-9]+` must be extended to match severity-prefixed IDs used by the QFB."

**What SKILL.md:1615 claims:** "Each confirmed bug must use the heading level `### BUG-NNN` (e.g., `### BUG-001`)." The example implies numeric-only format.

**What QFB practice claims (from generated BUGS.md):** Bugs are named `BUG-H1`, `BUG-M3`, `BUG-L6` — severity-prefix format derived from Phase 1 severity assessment.

**Consistency:** INCONSISTENT — the spec example (`BUG-001`), the gate regex (`BUG-[0-9]+`), and actual QFB output (`BUG-H1`) are in three-way conflict. The spec says one format, the gate enforces that format, but the tool generates a different format.

**Impact:** Every QFB self-audit run that uses severity-prefix IDs produces BUGS.md entries that the gate cannot count. `bug_count=0` causes the gate to skip ALL TDD log, patch, and writeup validation — the gate provides zero quality assurance for this entire artifact class.

**Code evidence:**
- `quality_gate.sh:184` — `grep -cE '^### BUG-[0-9]+'` — enforces numeric format
- `SKILL.md:1615` — `### BUG-NNN (e.g., BUG-001)` — specifies numeric format
- `quality/BUGS.md` — `### BUG-H1`, `### BUG-M3`, etc. — uses severity-prefix format
- `quality/results/tdd-results.json` — `"id": "BUG-H1"` — severity-prefix in JSON too

**Resolution needed:** Either (a) change SKILL.md:1615 to show both formats and update the gate regex to match both, or (b) standardize QFB output to always use numeric IDs. Option (a) is less disruptive to existing runs.

---

## Shared Concept: TDD Verification Evidence (REQ-021 vs SKILL.md:1589 "TDD sidecar-to-log consistency check")

**Requirements:** REQ-021 (cross-validate JSON phase values against log tags)

**What REQ-021 claims:** Gate must cross-validate `red_phase`/`green_phase` JSON values against log file first-line tags.

**What SKILL.md:1589 claims:** "TDD sidecar-to-log consistency check (mandatory). If tdd-results.json contains a bug with `verdict: 'TDD verified'`, then `BUG-NNN.red.log` must exist with first line `RED` and `BUG-NNN.green.log` must exist with first line `GREEN`. If the sidecar claims 'TDD verified' but no red-phase log exists, the verdict is unsubstantiated."

**What the gate implements (quality_gate.sh:307-387):** Validates that log files EXIST and have valid first-line tags. Does NOT check that the tag is consistent with the JSON verdict.

**Consistency:** INCONSISTENT — SKILL.md mandates cross-validation but the gate only validates log existence and tag format independently. The gate's implementation does not fulfill the SKILL.md-mandated consistency check.

**Impact:** An agent can write `"verdict": "TDD verified"` in tdd-results.json while the actual log file shows `RED` on the first line (which means the test failed, indicating the bug was NOT verified fixed, just confirmed open). The gate would pass this contradiction. This undermines the purpose of the TDD verification phase.

---

## Shared Concept: Recheck Schema Consistency (REQ-018 vs SKILL.md:1965)

**Requirements:** REQ-018 (gate must validate recheck-results.json)

**What REQ-018 claims:** "Status enum: must be one of FIXED, PARTIALLY_FIXED, STILL_OPEN, INCONCLUSIVE (4 values). Schema_version must be '1.1' (consistent with other sidecar JSON files)."

**What SKILL.md:1965 specifies:** `"schema_version": "1.0"` in the recheck template.

**What SKILL.md:1984-1990 specifies for summary keys:** Lowercase (`fixed`, `partially_fixed`, `still_open`, `inconclusive`)

**What SKILL.md:1953 specifies for status values:** Uppercase (`FIXED`, `PARTIALLY_FIXED`, `STILL_OPEN`, `INCONCLUSIVE`)

**Consistency:** INCONSISTENT — the recheck schema has an internal case inconsistency (uppercase enum values vs lowercase summary keys) and an external schema_version inconsistency (`"1.0"` vs `"1.1"` used everywhere else). REQ-018 correctly identifies both but the spec itself must be updated before the gate can enforce consistently.

---

## Combined Summary

| Shared Concept | Requirements | Consistency | Impact |
|----------------|-------------|-------------|--------|
| ls-glob detection | REQ-014, REQ-015, REQ-016, REQ-019 | CONSISTENT | Additive requirements, same fix pattern |
| Bug ID format | REQ-020, SKILL.md:1615, QFB practice | INCONSISTENT | Gate bypasses all validation for severity-prefix IDs |
| TDD evidence cross-validation | REQ-021, SKILL.md:1589 | INCONSISTENT | Mandatory spec check not implemented in gate |
| Recheck schema | REQ-018, SKILL.md:1965 | INCONSISTENT | Schema version and case inconsistency within recheck spec |

**Net-new contradictions found in Pass 3:** 3 (Bug ID format three-way conflict, TDD evidence cross-validation gap, recheck schema internal inconsistency)

**Overall assessment: FIX FIRST** — the Bug ID format inconsistency is systemic, causing the gate to bypass all TDD/patch/writeup validation for standard QFB self-audit runs.
