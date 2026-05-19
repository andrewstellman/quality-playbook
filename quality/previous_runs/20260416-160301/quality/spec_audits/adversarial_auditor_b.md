# Spec Audit — Adversarial Iteration, Auditor B (User Experience)
<!-- Quality Playbook v1.4.1 — Adversarial Spec Audit — 2026-04-16 -->

**Role:** User Experience Auditor — checking whether the system produces artifacts that meet
user-facing quality expectations.
**Scope:** Adversarial iteration — focus on integration-results.json usability, demoted candidate
re-investigation from user perspective.

---

## Findings

### B-1: integration-results.json groups[].result values unvalidated — user trust gap

**Line:** quality_gate.sh:389-436 (absence)
**Classification:** MISSING
**Req:** formal — SKILL.md:1273, SKILL.md:1277

From a user's perspective: the gate passes as conformant an integration-results.json where
groups[].result contains non-canonical values like "passed" or "OK". A CI system reading this
artifact and checking `if result == "pass"` would fail silently (exact string match against wrong
value). The gate's green light provides false confidence.

SKILL.md:1273 explicitly defines valid result values AND says "Runner scripts and CI tools should
read the sidecar JSON for results rather than grepping the Markdown report." The gate should protect
the machine-readable contract that tools will depend on.

### B-2: integration-results.json uc_coverage values unvalidated

**Line:** quality_gate.sh:393 (uc_coverage key presence only)
**Classification:** MISSING
**Req:** formal — SKILL.md:1273

The distinction between "covered_fail" and "not_mapped" (per SKILL.md:1273) is called out as
important: "the first means the test exists but the code is broken; the second means the test is
missing." A user reading an incorrect uc_coverage value (e.g., "fail" instead of "covered_fail")
would draw the wrong conclusion about whether tests are missing or failing.

### B-3: integration-results.json summary sub-keys missing — silent data loss for automation

**Line:** quality_gate.sh:393 (summary root key check only)
**Classification:** MISSING
**Req:** formal — SKILL.md:1252-1255

Users expecting to aggregate results across runs by reading `summary.total_groups` and
`summary.passed` get no gate guarantee these fields exist. An integration-results.json with
`"summary": {"status": "ok"}` (wrong keys) passes gate validation but breaks any downstream
aggregation script. Compare with tdd-results.json where summary sub-keys ARE checked (weakly).

### B-4 (Re-confirmed from triage): Date staleness not checked for integration-results.json

**Line:** quality_gate.sh:402-421
**Classification:** MISSING
**Req:** inferred — consistency with tdd-results.json date validation

The gate validates date for both tdd-results.json AND integration-results.json — that's good.
However, neither check validates that the date is "recent" (within the past N days). A stale
artifact from 6 months ago passes date validation. This was dismissed in the baseline triage as
"Acceptable gap." From a user perspective, this remains a gap: a committed integration artifact
could be months old without gate detection. Not re-promoted — triage dismissal was correct.

### B-5: Phase 2 entry gate check #1 (120-line minimum) absent — user gets false confidence

**Line:** SKILL.md:897-904 (Phase 2 entry gate — check #1 absent)
**Classification:** DIVERGENT
**Req:** formal — SKILL.md:850

From a user's perspective: the Phase 1 gate "passed" message means Phase 2 will produce high-quality
artifacts. But if Phase 2 runs in a new session and the entry gate doesn't check the 120-line minimum,
a thin EXPLORATION.md (10 lines, just section titles) proceeds through Phase 2 producing shallow
requirements. Users trust the multi-phase architecture to catch this. The gap breaks that trust.

---

## Summary

| Finding | Classification | Req | Confidence | Disposition |
|---------|---------------|-----|-----------|-------------|
| B-1: groups[].result unvalidated | MISSING | formal | 2/3 (A+B) | NET-NEW BUG candidate |
| B-2: uc_coverage values unvalidated | MISSING | formal | 2/3 (A+B) | NET-NEW BUG candidate |
| B-3: summary sub-keys missing | MISSING | formal | 2/3 (A+B) | NET-NEW BUG candidate |
| B-4: Date staleness check absent | MISSING | inferred | 1/3 | Accepted gap — stays dismissed |
| B-5: Phase 2 entry check #1 absent | DIVERGENT | formal | 2/3 (A+B) | Extends BUG-M3 scope |
