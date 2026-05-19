# Pass 3: Cross-Requirement Consistency — Adversarial Iteration
<!-- Quality Playbook v1.4.1 — Adversarial Code Review Pass 3 — 2026-04-16 -->

**Scope:** Cross-requirement consistency for new adversarial requirements (REQ-026, REQ-027, REQ-028)
vs existing requirements. Also checks for contradictions introduced by demoted candidate resolutions.

---

## Shared Concept: integration-results.json validation depth

**Requirements:** REQ-026, REQ-027 (new adversarial) vs existing confirmed BUG-L19 (summary
sub-key validation), BUG-H1 (json_has_key false positive)

**What REQ-026 claims:** Gate must validate `groups[].result` enum values for integration-results.json.

**What REQ-027 claims:** Gate must validate `summary` sub-keys for integration-results.json.

**What existing BUG-L19 / confirmed implementation does:**
- tdd-results.json: summary sub-keys checked at lines 259-265 (via json_has_key — weak but present)
- integration-results.json: summary sub-keys NOT checked at all

**Consistency:** INCONSISTENT — the two parallel sidecar JSONs (tdd-results.json and
integration-results.json) are validated at different depths by the gate. Both have required summary
sub-keys defined in SKILL.md; only tdd-results.json's are checked.

**Code evidence:**
```bash
# tdd-results.json summary sub-key check (lines 259-265):
for skey in total verified confirmed_open red_failed green_failed; do
    if json_has_key "$json_file" "$skey"; then
        pass "summary has '${skey}'"
    else
        fail "summary missing '${skey}' count"
    fi
done

# integration-results.json summary validation (line 393-394):
for key in schema_version skill_version date project recommendation groups summary uc_coverage; do
    json_has_key "$ij" "$key" && pass "has '${key}'" || fail "missing key '${key}'"
done
# NO further validation of summary sub-keys
```

**Analysis:** The inconsistency is clear. SKILL.md:1252-1255 defines 4 required integration summary
sub-keys. The gate ignores them. This is the same asymmetry as BUG-L19 (which identified the
weak-validator problem for tdd summary sub-keys) but for a deeper structural gap: integration
summary has ZERO sub-key enforcement vs tdd's weak enforcement.

**Impact:** Tools consuming integration-results.json expecting `summary.total_groups` or
`summary.passed` get no gate guarantee these fields exist.

---

## Shared Concept: Validation gate coverage — SKILL.md post-write mandates vs gate enforcement

**Requirements:** REQ-026 (groups[].result enum), REQ-027 (summary sub-keys) vs
REQ-021 (TDD sidecar-to-log consistency — BUG-M18)

**What REQ-026 claims:** Gate must enforce enum values for integration groups[].result.

**What BUG-M18 established:** Gate validates JSON field PRESENCE but not cross-validation with logs.
This means the gate is consistently weak at semantic validation (value constraints, cross-artifact
consistency) while being strong at structural validation (key presence, schema_version value).

**Consistency:** CONSISTENT within the gate's weakness pattern — but INCONSISTENT with SKILL.md's
mandates, which require value-level validation in post-write checks (lines 1273, 1277).

**Analysis:** This confirms the pattern that SKILL.md mandates post-write validation for both sidecar
JSONs, but the gate only partially enforces these mandates:
- tdd verdict enum: gate enforces (lines 294-296)
- integration recommendation enum: gate enforces (lines 426-428)
- integration groups[].result enum: gate does NOT enforce (CAND-A1)
- integration uc_coverage value enum: gate does NOT enforce (CAND-A1)
- tdd red/green cross-validation: gate does NOT enforce (BUG-M18)

The enforcement is inconsistent across parallel value validation requirements.

---

## Shared Concept: Phase entry gate completeness pattern

**Requirements:** REQ-028 (Phase 2 entry gate missing check #1) vs REQ-003 (BUG-M3 — Phase 2 entry
gate enforces 6 of 12 Phase 1 checks)

**What REQ-003/BUG-M3 established:** Phase 2 entry gate checks 6 section titles, missing checks
2, 3, 5, 8, 10, 12.

**What REQ-028 claims:** Check #1 (120-line minimum) is also missing from Phase 2 entry gate AND
was omitted from BUG-M3's fix scope.

**Consistency:** CONSISTENT with BUG-M3 — both identify the same class of gap (Phase 2 entry gate
fails to backstop Phase 1 completion gate). REQ-028 extends BUG-M3 by identifying one additional
missing check. The two requirements do not contradict each other; REQ-028 is additive.

**Code evidence:** SKILL.md:897-904 lists 6 checks; SKILL.md:850 lists check #1; check #1 is absent
from the Phase 2 gate. The BUG-M3 fix patch adds checks 2, 3, 5, 8, 10, 12 but not check #1.
After fix patch applied, an EXPLORATION.md with 6 section titles and 10 lines total still passes
Phase 2 entry gate.

---

## Summary

| Shared Concept | Requirements | Consistency | Impact |
|----------------|-------------|-------------|--------|
| Integration sidecar summary sub-keys | REQ-027 vs BUG-L19 | INCONSISTENT | Integration sub-keys unvalidated |
| Validation gate coverage depth | REQ-026 vs REQ-021/BUG-M18 | CONSISTENT within weakness | Pattern: gate weak at semantic validation |
| Phase entry gate completeness | REQ-028 vs REQ-003/BUG-M3 | CONSISTENT (additive) | Check #1 still missing after BUG-M3 fix |

**Confirmed new bugs from consistency analysis:**
- CAND-A1 (BUG-L23): integration groups[].result enum + per-group fields absent from gate validation
- CAND-A2 (BUG-L24): integration summary sub-keys absent from gate validation
- CAND-A3 (BUG-L25): Phase 2 entry gate check #1 (120-line min) missing even after BUG-M3 fix

**Overall assessment: FIX FIRST** — 3 net-new bugs confirmed, all LOW severity, all in the same
"incomplete validation" class as existing confirmed bugs.
