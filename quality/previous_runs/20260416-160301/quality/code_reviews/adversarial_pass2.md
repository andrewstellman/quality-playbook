# Pass 2: Requirement Verification — Adversarial Iteration
<!-- Quality Playbook v1.4.1 — Adversarial Code Review Pass 2 — 2026-04-16 -->

**Scope:** Adversarial requirement verification focused on thin SATISFIED verdicts and new
requirements REQ-022 through REQ-025 added in parity iteration. Also challenges the parity
iteration's new requirements against observed code.

---

## Re-verification of Thin SATISFIED Verdicts

### REQ-011: Requirements Pipeline Must Produce Traceable, Testable Requirements (re-challenge)

**Original verdict:** SATISFIED

**Re-verification evidence:**
- REQUIREMENTS.md has 14 requirements (REQ-001 through REQ-014 confirmed)
- Each has 8 mandatory fields (re-read REQUIREMENTS.md confirms field structure)
- COVERAGE_MATRIX.md exists (confirmed on disk)
- UC-01 through UC-05 use cases confirmed in REQUIREMENTS.md
- `[Req: tier — source]` tags present in QUALITY.md scenarios

**Analysis:** The SATISFIED verdict is correct. REQ-011 requires traceable, testable requirements
with proper field structure. All 14 requirements have UC identifiers, REQ-NNN format, authority tiers,
and testable conditions. The evidence base is multi-source. No evidence of false positive.

**Status: SATISFIED — verdict confirmed by adversarial re-verification**

---

### REQ-013: Mechanical Verification Must Not Be Created for Non-Dispatch Contracts (re-challenge)

**Original verdict:** SATISFIED

**Re-verification evidence:**
- `quality/mechanical/` directory does not exist (confirmed by PROGRESS.md and gate log)
- PROGRESS.md records "Mechanical verification: NOT APPLICABLE" in multiple phase entries
- quality_gate.sh:543-560 checks for mechanical/ only if it exists — does not require it for bash projects

**Analysis:** The SATISFIED verdict is correct. SKILL.md line 578 explicitly says "Do not create an
empty mechanical/ directory" for projects without dispatch-function contracts. quality_gate.sh's
if/elif chains are not dispatch tables requiring mechanical extraction.

**Status: SATISFIED — verdict confirmed by adversarial re-verification**

---

## New Requirements Verification (REQ-022 through REQ-025 from Parity Iteration)

### REQ-022: Gate Summary Sub-Key Checks Must Use json_key_count

**Status:** VIOLATED

**Evidence:** `quality_gate.sh:259-265` — `json_has_key` used for summary sub-key checks.
`quality_gate.sh:239-248` — `json_key_count` used for per-bug field checks.
Inconsistency confirmed by direct reading.

**Analysis:** BUG-L19 correctly identified this violation. The adversarial iteration confirms
REQ-022 is VIOLATED — unchanged from parity iteration finding.

---

### REQ-023: Patch Existence Check Must Iterate Per-Bug ID

**Status:** VIOLATED

**Evidence:** `quality_gate.sh:562-588` — aggregate count approach confirmed.
`quality_gate.sh:316-345` — per-bug iteration for logs.

**Analysis:** BUG-L20 correctly identified this violation. REQ-023 VIOLATED confirmed.

---

### REQ-024: Phase 5 Must Include Entry Gate for Phase 4 Artifacts

**Status:** VIOLATED

**Evidence:** `SKILL.md:1573-1590` (Phase 5 opening) — reads PROGRESS.md, not mechanical artifact check.
`SKILL.md:897-907` (Phase 2 entry gate) — mechanical section title verification.

**Analysis:** BUG-L21 correctly identified this violation. REQ-024 VIOLATED confirmed.

---

### REQ-025: SEED_CHECKS.md Must Be in Artifact Contract Table

**Status:** VIOLATED

**Evidence:** `SKILL.md:88-119` (artifact contract table) — no SEED_CHECKS.md row.
`SKILL.md:1641` — requires SEED_CHECKS.md when Phase 0b runs.

**Analysis:** BUG-L22 correctly identified this violation. REQ-025 VIOLATED confirmed.

---

## New Requirements from Adversarial Iteration (REQ-026, REQ-027, REQ-028)

### REQ-026: Gate Must Validate integration-results.json groups[].result Enum Values

**Status:** VIOLATED

**Evidence:** `quality_gate.sh:389-436` — no `groups[].result` enum check.
`SKILL.md:1273` — defines valid result values as "pass", "fail", "skipped", "error".

**Analysis:** The gate validates tdd-results.json verdict enum (lines 294-296) but has no equivalent
for integration-results.json groups[].result values. SKILL.md explicitly specifies the enum values
and the post-write validation mandate (line 1277) requires all result values to use only allowed values.
The gate provides no enforcement — any string passes as a result value.

**Severity:** LOW — same class as BUG-L19 (structural inconsistency, non-obvious wrong values)

---

### REQ-027: Gate Must Validate integration-results.json summary Sub-Keys

**Status:** VIOLATED

**Evidence:** `quality_gate.sh:393-394` — `summary` checked for presence only via `json_has_key`.
`quality_gate.sh:259-265` — tdd-results.json summary sub-keys checked (weakly via json_has_key).
`SKILL.md:1252-1255` — defines 4 required summary sub-keys: total_groups, passed, failed, skipped.

**Analysis:** For tdd-results.json, the gate at lines 259-265 checks 5 summary sub-keys (total,
verified, confirmed_open, red_failed, green_failed). For integration-results.json, the gate checks
only top-level key presence. The integration summary sub-keys (total_groups, passed, failed, skipped)
are never validated. An `integration-results.json` with `"summary": {}` (empty object) passes all
gate checks. Same parity gap class as BUG-L19.

**Severity:** LOW

---

### REQ-028: Phase 2 Entry Gate Must Enforce 120-Line Minimum Substantive Content (Extends REQ-003)

**Status:** VIOLATED (extends BUG-M3 / REQ-003)

**Evidence:** `SKILL.md:850` — Phase 1 completion gate check #1 requires 120 lines of substantive content.
`SKILL.md:897-904` — Phase 2 entry gate enforces 6 section title checks.
`quality/patches/BUG-M3-fix.patch` — adds checks 2, 3, 5, 8, 10, 12 but NOT check #1.

**Analysis:** BUG-M3's description listed the missing checks as "2, 3, 5, 8, 10, 12." Check #1
(minimum 120 lines) was also missing from Phase 2 entry gate enforcement but was not explicitly
listed in BUG-M3 and was not addressed by the fix patch. After BUG-M3's fix is applied, the Phase 2
entry gate still does not enforce check #1. This is a distinct (though related) gap: BUG-M3 addresses
the structural content checks (file paths, domain risks, pattern depth) while check #1 is the
raw line-count floor that prevents completely empty placeholder files.

**Severity:** LOW (extends BUG-M3 — same root cause of Phase 2 entry gate incompleteness)

---

## Summary

| Requirement | Status | Notes |
|-------------|--------|-------|
| REQ-011 (re-challenge) | SATISFIED | Adversarial re-verification confirms |
| REQ-013 (re-challenge) | SATISFIED | Adversarial re-verification confirms |
| REQ-022 | VIOLATED | BUG-L19 confirms |
| REQ-023 | VIOLATED | BUG-L20 confirms |
| REQ-024 | VIOLATED | BUG-L21 confirms |
| REQ-025 | VIOLATED | BUG-L22 confirms |
| REQ-026 (new) | VIOLATED | CAND-A1 — integration groups[].result enum absent |
| REQ-027 (new) | VIOLATED | CAND-A2 — integration summary sub-keys absent |
| REQ-028 (new) | VIOLATED | CAND-A3 — Phase 2 entry gate missing check #1 |

**Net-new violations:** REQ-026, REQ-027, REQ-028 — all LOW severity
