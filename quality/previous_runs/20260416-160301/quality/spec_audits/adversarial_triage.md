# Triage Report — quality-playbook Adversarial Spec Audit
<!-- Quality Playbook v1.4.1 — Adversarial Triage — 2026-04-16 -->

---

## Council Status

- Model A (Strict Compliance Auditor): Fresh report received (2026-04-16) — `quality/spec_audits/adversarial_auditor_a.md`
- Model B (User Experience Auditor): Fresh report received (2026-04-16) — `quality/spec_audits/adversarial_auditor_b.md`
- Model C (Security/Reliability Auditor): Fresh report received (2026-04-16) — `quality/spec_audits/adversarial_auditor_c.md`

**Effective council: 3/3.** All three auditors produced usable reports.

---

## Pre-Audit Docs Validation

No `docs_gathered/` directory. Auditors relied on in-repo specifications and code only.

**Spot-check adversarial targets:**

| Claim | Lines Checked | Result |
|-------|--------------|--------|
| Gate validates integration groups[].result | quality_gate.sh:389-436 | VERIFIED ABSENT — no result enum check |
| Gate validates integration summary sub-keys | quality_gate.sh:393-394 | VERIFIED ABSENT — top-level key only |
| SKILL.md defines integration groups[].result valid values | SKILL.md:1273 | VERIFIED CORRECT — "pass", "fail", "skipped", "error" |
| Phase 2 entry gate checks 120-line minimum (check #1) | SKILL.md:897-904 | VERIFIED ABSENT — check #1 not in entry gate |

---

## Adversarial Demoted Candidate Re-Evaluation

| Demoted Candidate | Auditor Agreement | Re-Promotion Criteria Met? | Disposition |
|------------------|-------------------|---------------------------|-------------|
| DC-001/DC-006 (date comparison) | 0/3 re-promoted | No — ISO 8601 lexicographic ordering correct | FALSE POSITIVE confirmed |
| DC-003 (Phase 7 ambiguity) | 0/3 re-promoted | No — iteration.md override is clear | FALSE POSITIVE confirmed |
| DC-004 (TOOLKIT.md stale count) | 0/3 re-promoted | No — TOOLKIT.md defers to SKILL.md | FALSE POSITIVE confirmed |
| DC-005 (code review vocab) | 0/3 re-promoted | No — no cross-artifact contamination path | FALSE POSITIVE confirmed |
| DC-010 (deferred absent from template) | 0/3 re-promoted | No — gate rejects deprecated verdict | FALSE POSITIVE confirmed |

---

## Net-New Findings — Triage Matrix

| Finding | Auditors | Confidence | Probe Result | Disposition |
|---------|----------|-----------|-------------|-------------|
| integration groups[].result enum absent (A-1, B-1, C-1) | A+B+C | Highest (3/3) | CONFIRMED (PROBE-ADV1) | **NET-NEW BUG** |
| integration uc_coverage value enum absent (A-2, B-2) | A+B | High (2/3) | CONFIRMED (PROBE-ADV1) | **NET-NEW BUG** |
| integration summary sub-keys absent (A-3, B-3, C-2) | A+B+C | Highest (3/3) | CONFIRMED (PROBE-ADV2) | **NET-NEW BUG** |
| Phase 2 entry gate check #1 absent (A-4, B-5, C-3) | A+B+C | Highest (3/3) | CONFIRMED (PROBE-ADV3) | Extends BUG-M3 — **NET-NEW BUG** |
| Date staleness check absent (B-4) | B | Needs verification | Not probed — prior triage dismissal stands | Accepted gap |
| VERSION grep-m1 fragility (C-4) | C | Needs verification | Not probed — confirmed false positive | FALSE POSITIVE |

---

## Verification Probes

### PROBE-ADV1: groups[].result and uc_coverage enum validation absent

```bash
# Assertion that FAILS, confirming the gap (groups result enum not checked):
result_check=$(grep -n 'result.*pass\|result.*fail\|groups\[\]' quality_gate.sh | head -5)
echo "Result enum check in gate: ${result_check:-ABSENT}"
# Expected: ABSENT — confirms gate has no groups[].result enum validation

# Assertion that FAILS, confirming uc_coverage value validation absent:
uc_check=$(grep -n 'covered_pass\|covered_fail\|not_mapped' quality_gate.sh | head -5)
echo "UC coverage value check in gate: ${uc_check:-ABSENT}"
# Expected: ABSENT — confirms gate has no uc_coverage value enum validation
```

Actual result from reading quality_gate.sh: lines 389-436 contain NO grep for result enum values
or uc_coverage value enum. PROBE-ADV1: CONFIRMED — bug exists.

### PROBE-ADV2: integration summary sub-keys absent

```bash
# Compare integration summary validation (absent) with tdd summary validation (present):
tdd_summary=$(grep -n 'total\|verified\|confirmed_open\|red_failed\|green_failed' quality_gate.sh | grep -v '#')
int_summary=$(grep -n 'total_groups\|passed\|failed\|skipped' quality_gate.sh | grep -v '#')
echo "TDD summary sub-key checks: ${tdd_summary}"  # Should show lines 259-265
echo "Integration summary sub-key checks: ${int_summary}"  # Should be ABSENT
```

Actual result from reading quality_gate.sh: lines 259-265 show tdd summary sub-key loop. No
equivalent exists for integration summary. PROBE-ADV2: CONFIRMED — integration summary sub-keys
not validated.

### PROBE-ADV3: Phase 2 entry gate check #1 (120 lines) absent

```bash
# Confirm Phase 1 check #1 (120 lines) exists in Phase 1 gate:
phase1_check=$(grep -n '120' SKILL.md | head -5)
echo "Phase 1 check #1 in SKILL.md: ${phase1_check}"

# Confirm Phase 2 entry gate does NOT include 120-line check:
phase2_gate=$(grep -n 'entry gate' SKILL.md | head -5)
echo "Phase 2 entry gate location: ${phase2_gate}"
# Read SKILL.md:897-904 — 6 checks, none mention 120 lines
```

Actual result from reading SKILL.md: line 850 shows "at least 120 lines of substantive content."
Lines 897-904 show 6 section title checks — NO 120-line check. PROBE-ADV3: CONFIRMED — check #1
absent from Phase 2 entry gate.

---

## Confirmed Net-New Bugs

### NET-NEW BUG: integration-results.json groups[].result Enum and Per-Group Fields Not Validated

**Classification:** Real code bug

**Auditor agreement:** 3/3 (A-1, B-1, C-1 — all three found same pattern)

**Evidence:**
- SKILL.md:1273 defines valid result values: "pass", "fail", "skipped", "error"
- SKILL.md:1277 mandates post-write validation including all result values
- quality_gate.sh lines 389-436: NO check for groups[].result enum values
- Comparison: tdd-results.json verdict values ARE validated at lines 294-296

**Real-world failure:** An agent generating `"result": "PASS"` (uppercase — wrong) passes gate
validation but breaks CI tools checking `if result == "pass"`.

**Additional scope (2/3 auditors):** uc_coverage value enum also absent — the distinction between
"covered_fail" and "not_mapped" is important (SKILL.md:1273 explains why) but not enforced.

**Severity:** LOW — no false PASS for overall gate result, but provides false conformance assurance
for per-group field structure and enum values.

---

### NET-NEW BUG: integration-results.json summary Sub-Keys Not Validated

**Classification:** Real code bug

**Auditor agreement:** 3/3 (A-3, B-3, C-2)

**Evidence:**
- SKILL.md:1252-1255 defines 4 required summary sub-keys: total_groups, passed, failed, skipped
- quality_gate.sh: summary key PRESENCE checked at line 393, sub-keys NEVER checked
- tdd-results.json summary sub-keys ARE checked at lines 259-265 (via json_has_key — weak but present)
- Direct code comparison confirms asymmetry: tdd gets sub-key validation, integration does not

**Severity:** LOW — same class as BUG-L19 (summary sub-key validation asymmetry)

---

### NET-NEW BUG: Phase 2 Entry Gate Does Not Enforce 120-Line Minimum (Extends BUG-M3)

**Classification:** Real code bug (extends BUG-M3 scope)

**Auditor agreement:** 3/3 (A-4, B-5, C-3)

**Evidence:**
- SKILL.md:850 (Phase 1 completion gate check #1): "at least 120 lines of substantive content"
- SKILL.md:897-904 (Phase 2 entry gate): 6 section title checks, no 120-line check
- BUG-M3 fix patch adds checks 2, 3, 5, 8, 10, 12 — check #1 remains missing
- After BUG-M3 fix: EXPLORATION.md with 6 section title stubs (10 lines total) still passes Phase 2 entry gate

**Severity:** LOW — extends BUG-M3 in scope; same root cause (Phase 2 entry gate incomplete backstop)

---

## Confirmed Demoted Candidates (All FALSE POSITIVE — Stays Dismissed)

- DC-001/006: Date comparison — FALSE POSITIVE confirmed 0/3 auditors
- DC-003: Phase 7 ambiguity — FALSE POSITIVE confirmed 0/3 auditors
- DC-004: TOOLKIT.md stale count — FALSE POSITIVE confirmed 0/3 auditors
- DC-005: Code review vocab — FALSE POSITIVE confirmed 0/3 auditors
- DC-010: deferred template absent — FALSE POSITIVE confirmed 0/3 auditors
