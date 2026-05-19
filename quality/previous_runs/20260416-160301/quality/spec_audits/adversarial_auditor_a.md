# Spec Audit — Adversarial Iteration, Auditor A (Strict Compliance)
<!-- Quality Playbook v1.4.1 — Adversarial Spec Audit — 2026-04-16 -->

**Role:** Strict Compliance Auditor — checking whether code satisfies every documented contract.
**Scope:** Adversarial iteration — focus on integration-results.json validation, Phase 2 entry gate,
and demoted candidate re-examination.

---

## Findings

### A-1: integration-results.json `groups[].result` enum not validated by gate

**Line:** quality_gate.sh:389-436 (entire integration validation block — absence finding)
**Classification:** MISSING
**Req:** formal — SKILL.md:1273

SKILL.md:1273 specifies: "Valid result values: 'pass', 'fail', 'skipped', 'error'." The gate
validates the `recommendation` field enum (SHIP/FIX BEFORE MERGE/BLOCK) but has NO validation for
`groups[].result` enum values. An agent writing `"result": "PASSED"` or `"result": "ok"` would
produce a non-conformant artifact that passes gate validation.

Spec says: groups[].result must be one of "pass", "fail", "skipped", "error".
Code does: does not check — any string value passes.

### A-2: integration-results.json `uc_coverage` value enum not validated by gate

**Line:** quality_gate.sh:393 (uc_coverage key presence check only)
**Classification:** MISSING
**Req:** formal — SKILL.md:1273

SKILL.md:1273 defines uc_coverage values as one of "covered_pass", "covered_fail", "not_mapped".
The gate checks that `uc_coverage` KEY exists (via json_has_key) but never validates that each
UC identifier maps to one of the three allowed values. A uc_coverage with `{"UC-01": "yes"}` passes.

### A-3: integration-results.json summary sub-keys not validated

**Line:** quality_gate.sh:393 (summary key presence check — no sub-key validation)
**Classification:** MISSING
**Req:** formal — SKILL.md:1252-1255

SKILL.md:1251-1256 shows summary must have: `total_groups`, `passed`, `failed`, `skipped`.
Gate checks `summary` key presence only. Sub-key presence is not validated. Compare with
tdd-results.json at lines 259-265 where summary sub-keys ARE checked.

### A-4: Phase 2 entry gate omits check #1 from Phase 1 completion gate

**Line:** SKILL.md:897-904 (Phase 2 entry gate) vs SKILL.md:850 (check #1: 120 lines)
**Classification:** DIVERGENT
**Req:** formal — SKILL.md:846 "You MUST execute this gate before proceeding to Phase 2"

SKILL.md:846 says the Phase 1 completion gate is mandatory. The Phase 2 entry gate (lines 897-904)
is the backstop for multi-session mode. Check #1 (120 lines substantive) is listed in Phase 1 gate
but not in Phase 2 entry gate or in BUG-M3's fix patch scope. The gate backstop is incomplete.

Spec says: Phase 2 entry gate should backstop Phase 1 completion gate.
Code does: backstops checks 2, 3, 5, 8, 10, 12 (with BUG-M3 fix) but not check #1.

### A-5 (Re-confirmed from prior audits): integration-results.json root key checks use json_has_key

**Line:** quality_gate.sh:393-394
**Classification:** DIVERGENT
**Req:** inferred — REQ-026 from adversarial iteration

The integration JSON root key checks use `json_has_key` (weak, BUG-H1 class). Should use
`json_key_count` for consistency with per-bug field checks. This is the same weakness as BUG-L19
but for integration root keys.

---

## Summary

| Finding | Classification | Req | Confidence | Disposition |
|---------|---------------|-----|-----------|-------------|
| A-1: groups[].result enum absent | MISSING | formal | 1/3 | NET-NEW BUG candidate |
| A-2: uc_coverage value enum absent | MISSING | formal | 1/3 | NET-NEW BUG candidate |
| A-3: summary sub-keys absent | MISSING | formal | 1/3 | NET-NEW BUG candidate |
| A-4: Phase 2 entry gate check #1 | DIVERGENT | formal | 1/3 | Extends BUG-M3 scope |
| A-5: json_has_key for root keys | DIVERGENT | inferred | 1/3 | BUG-H1 propagation (known) |
