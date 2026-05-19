# Pass 1: Structural Review — Adversarial Iteration
<!-- Quality Playbook v1.4.1 — Adversarial Code Review Pass 1 — 2026-04-16 -->

**Scope:** Adversarial structural review focused on integration-results.json validation section
(quality_gate.sh:389-436), adjacent code around CAND-A1/A2/A3 findings, and BUG-M3 extension.

---

## quality_gate.sh — Integration JSON Validation Section (lines 389-436)

**Line 393-394:** [BUG] Root key presence checks for integration-results.json use `json_has_key`
which matches key names anywhere in the file (BUG-H1 class). An integration-results.json with
`"notes": "groups skipped due to error"` would falsely pass the `groups` key check via substring match.
Expected: use `json_key_count` with colon anchor for definitive presence check.

**Lines 393-394 (absence of per-group validation):** [BUG] The gate checks 8 root keys but never
descends into `groups[]` array to validate per-group required fields. Specifically:
- `groups[].group` (integer) — required, never checked
- `groups[].name` (string) — required, never checked
- `groups[].use_cases` (array) — required, never checked
- `groups[].result` (enum) — required, never checked
- `groups[].notes` (string) — required, never checked

SKILL.md:1277 (post-write validation mandate) explicitly requires: "every `groups[]` entry has
`group`, `name`, `use_cases`, `result`, and `notes`." The gate provides no mechanical enforcement
of this mandate.

**Lines 393-394 (absence of uc_coverage value validation):** [BUG] The `uc_coverage` key is checked
for presence only. The value object's per-UC values are never validated against the enum
(`"covered_pass"`, `"covered_fail"`, `"not_mapped"`). SKILL.md:1273 defines these enum values.
An agent that writes `"uc_coverage": {"UC-01": true}` or `{"UC-01": "pass"}` (wrong values) passes
all gate checks.

**Lines 393-394 (absence of summary sub-key validation):** [BUG] The `summary` key is checked for
presence only. Required sub-keys `total_groups`, `passed`, `failed`, `skipped` (SKILL.md:1252-1255)
are never checked. Compare with tdd-results.json summary sub-key check at lines 259-265 which does
check sub-keys (albeit weakly via json_has_key per BUG-L19). The integration summary validation is
weaker by one level.

---

## quality_gate.sh — groups[].result Enum Validation (absence)

**Line 426-428:** [QUESTION] The gate validates `recommendation` enum for integration-results.json.
This is the ONLY integration field with value-level validation. By contrast, tdd-results.json has
verdict enum validation at lines 294-296. Why does the gate validate `recommendation` but not
`groups[].result`? This asymmetry is not documented as a design choice. Both fields have defined
enum values in SKILL.md. The omission of `groups[].result` validation appears to be a gap.

---

## SKILL.md — Phase 2 Entry Gate vs Phase 1 Completion Gate (BUG-M3 Extension)

**Line 897-904 (Phase 2 entry gate):** [BUG — EXTENDS BUG-M3] The Phase 2 entry gate checks for
6 section titles. Phase 1 completion gate check #1 (line 850: "at least 120 lines of substantive
content") is NOT checked in Phase 2 entry gate. BUG-M3's fix patch adds checks 2, 3, 5, 8, 10, 12
but NOT check #1. An EXPLORATION.md with exactly the 6 required section titles and placeholder
single-line content (total: ~15 lines) would:
- PASS the Phase 2 entry gate (6 section titles present)
- PASS BUG-M3's extended gate (adds checks 2, 3, 5, 8, 10, 12 for content depth)
- FAIL Phase 1 completion gate check #1 (< 120 lines)

The Phase 2 entry gate cannot protect against a thin EXPLORATION.md. Check #1 was omitted from
BUG-M3's description (which listed checks 2, 3, 5, 8, 10, 12 as missing) and from the fix patch.

---

## Summary

| Source | Finding | Severity | Status |
|--------|---------|----------|--------|
| Pass 1, quality_gate.sh:393-394 | BUG-H1 propagation to integration root key checks | LOW | BUG (propagated) |
| Pass 1, quality_gate.sh:389-436 | groups[].result enum never validated | LOW | BUG (CAND-A1) |
| Pass 1, quality_gate.sh:389-436 | uc_coverage value enum never validated | LOW | BUG (CAND-A1) |
| Pass 1, quality_gate.sh:389-436 | integration summary sub-keys never validated | LOW | BUG (CAND-A2) |
| Pass 1, SKILL.md:897-904 | Phase 2 entry gate omits check #1 (120 lines) | LOW | BUG (CAND-A3, extends BUG-M3) |

**Overall assessment: FIX FIRST** — 3 new confirmed structural bugs (CAND-A1, CAND-A2, CAND-A3).
All LOW severity and of the same class as BUG-L19, BUG-L20, BUG-M3 (already confirmed bugs).
The integration sidecar validation gap (CAND-A1, CAND-A2) is the most actionable finding.
