# Auditor A Report — Strict Compliance Auditor

<!-- Quality Playbook v1.4.1 — Phase 4 Spec Audit — 2026-04-16 -->

**Auditor role:** Strict Compliance — letter-of-spec verification against REQUIREMENTS.md and SKILL.md artifact contract.

---

## Pre-Audit Docs Validation

No `docs_gathered/` directory. Auditors relied on in-repo specifications and code only.

**Spot-check baseline claims from RUN_SPEC_AUDIT.md:**

**Claim 1:** "`json_key_count` uses `grep -c "\"${key}\"[[:space:]]*:"` — includes colon, thus requires the key pattern to precede a colon."
- Actual lines 88-91:
  ```
  json_key_count() {
      local file="$1" key="$2"
      grep -c "\"${key}\"[[:space:]]*:" "$file" 2>/dev/null || echo 0
  }
  ```
- Result: CLAIM IS CORRECT — the function does include a colon. However, the pattern still can match `"id":` inside a larger string value like `"description": "the 'id': required"`. Partially mitigated but not fully safe.

**Claim 2:** "`json_has_key` uses `grep -q "\"${key}\""` — does NOT include colon."
- Actual lines 75-78: `grep -q "\"${key}\""` — no colon.
- Result: CLAIM IS CORRECT — this is BUG-H1 (already confirmed).

**Claim 3:** "`REPO_DIRS=(${resolved[@]+"${resolved[@]}"})` at line 697 is unquoted on the outer expansion."
- Actual line 697: `REPO_DIRS=(${resolved[@]+"${resolved[@]}"})`
- Result: CLAIM IS CORRECT — outer expansion is unquoted — this is BUG-H2 (already confirmed).

---

## quality_gate.sh

### Finding A-1

- **Line 124:** DIVERGENT [Req: Tier 3 — quality_gate.sh:123-126] Functional test detection uses `ls` glob; language detection uses `find`.
  Spec says (REQ-014): "Gate script functional test detection must be consistent." Code does: `ls ${q}/test_functional.* ${q}/FunctionalSpec.* ...` at line 124, but language detection at lines 449-454 uses `find ... -print -quit`. The inconsistency is confirmed present (BUG already known, but this auditor independently flags the non-conformance against REQ-014 as a letter-of-spec issue).

### Finding A-2

- **Line 700-702:** MISSING [Req: Tier 3 — REQ-012] Empty VERSION with `--all` mode produces a silent failure.
  Spec says (REQ-012): "When VERSION is empty and `--all` is specified: gate must emit a clear error message naming the failure (VERSION empty, SKILL.md not found)." Code does: at lines 700-702, when `REPO_DIRS` is empty, the gate emits `echo "Usage: ..."` then `exit 1`. This produces a generic usage message rather than a "VERSION empty, SKILL.md not found" diagnostic. The message does not distinguish empty-VERSION-caused failure from genuine usage error (no arguments given). This diverges from REQ-012's condition of satisfaction: "The empty-array message must be clearly distinguishable from a normal gate run that simply found no bugs."

### Finding A-3

- **Line 531-533:** DIVERGENT [Req: Tier 2 — REQ-004] Regression test file existence not enforced when bug_count > 0.
  Spec says (REQ-004): "Gate must FAIL when `bug_count > 0` and no `quality/test_regression.*` file exists." Code does: lines 479-480 set `reg_test=$(ls ${q}/test_regression.* 2>/dev/null | head -1)` — this is the file detection — but there is no subsequent gate check that says "if bug_count > 0 and reg_test is empty, fail." Lines 519-527 only validate the extension of the regression test if it exists. There is no enforcement of existence when bugs are present. This is BUG-M4 (already confirmed), but auditor independently reports it.

### Finding A-4

- **Lines 152-153:** UNDOCUMENTED [Req: inferred] Unquoted globs for spec_audits counting.
  ```bash
  triage_count=$(ls ${q}/spec_audits/*triage* 2>/dev/null | wc -l | tr -d ' ')
  auditor_count=$(ls ${q}/spec_audits/*auditor* 2>/dev/null | wc -l | tr -d ' ')
  ```
  These lines use unquoted globs with `ls`. SKILL.md artifact contract (line 116) specifies spec audit reports be named `quality/spec_audits/*auditor*.md` and `*triage*`. The detection works only when paths have no spaces. Under `nullglob` shell option, the pattern expands to empty and `wc -l` counts zero. REQ-014 establishes the principle of detection method consistency — the same fragility class as the functional test detection issue. However, REQ-014 specifically names functional test detection. NET-NEW finding: the spec audit count detection has the same fragility class, not previously captured.

### Finding A-5

- **Lines 595-596:** UNDOCUMENTED [Req: inferred] Writeup and patch counting use unquoted globs.
  ```bash
  writeup_count=$(ls ${q}/writeups/BUG-*.md 2>/dev/null | wc -l | tr -d ' ')
  reg_patch_count=$(ls ${q}/patches/BUG-*-regression*.patch 2>/dev/null | wc -l | tr -d ' ')
  ```
  Same unquoted glob pattern class. If `q` contains spaces (enabled by a fix to BUG-H2), these counting operations would break even after BUG-H2 is fixed. This creates a latent compound bug: fixing BUG-H2 (space in path) would expose all the unquoted glob counts. Not captured in REQUIREMENTS.md as a requirement, but is a systemic pattern.

---

## SKILL.md

### Finding A-6

- **Line 271 vs 295-297:** DIVERGENT [Req: Tier 2 — REQ-005] Phase 0b activation condition misses empty-directory case.
  Spec says (REQ-005): "Phase 0b seed discovery must run when `previous_runs/` exists but contains no conformant quality artifacts." Code (SKILL.md line 295-297) says: "This step runs only if `previous_runs/` does not exist." When `previous_runs/` exists but is empty, neither Phase 0a nor 0b activates. This is confirmed BUG-M5, independently flagged.

### Finding A-7

- **Line 897-904 vs 847-862:** DIVERGENT [Req: Tier 3 — REQ-003] Phase 2 entry gate checks 6 of 12 Phase 1 completion gate checks.
  Spec says (REQ-003): Phase 2 entry gate must enforce all 12 Phase 1 checks or document explicitly which are not backstopped. Phase 2 entry gate at line 897-904 checks 6 items. Phase 1 completion gate at lines 847-862 defines 12 checks. Missing: checks 2, 3, 5, 8, 10, 12. This is confirmed BUG-M3, independently flagged.

### Finding A-8 (NET-NEW CANDIDATE)

- **Lines 1374-1376 vs 122-148:** DIVERGENT [Req: Tier 2 — REQ-009] The SKILL.md TDD sidecar template (line 1374-1407) includes additional optional per-bug fields not present in the SKILL.md artifact contract section (lines 122-148).
  Spec says (SKILL.md lines 1410): "Optional per-bug fields (shown in the template above but not gate-checked): `regression_patch`, `fix_patch`, `patch_gate_passed`, `junit_red`, `junit_green`, `junit_available`, `notes`."
  But the artifact contract section canonical example at lines 122-148 shows a shorter template without those fields. The gate at quality_gate.sh lines 239-249 checks exactly the required per-bug fields. The discrepancy between the two SKILL.md templates could cause agents to use the abbreviated contract-section template and omit optional fields that are documented in the longer Phase 5 template. Not a gate-enforcement bug but a spec inconsistency that can confuse agents generating the JSON.

### Finding A-9 (NET-NEW CANDIDATE)

- **Line 1964-1990 vs line 122-148:** DIVERGENT [Req: Tier 2 — REQ-009] Recheck mode schema example at SKILL.md lines 1964-1990 uses `"schema_version": "1.0"` while all other sidecar schemas use `"1.1"`.
  ```json
  {
    "schema_version": "1.0",
    "skill_version": "1.4.1",
  ```
  The artifact contract section (SKILL.md lines 122-148) shows `"schema_version": "1.1"` for both `tdd-results.json` and `integration-results.json`. The recheck schema deliberately uses `"1.0"`. There is no documentation explaining why recheck uses a different schema version. This creates ambiguity: is this intentional versioning or an inconsistency? The gate at quality_gate.sh validates `"schema_version": "1.1"` for the TDD sidecar but does not check recheck-results.json at all (confirmed by grep — no `recheck-results` in quality_gate.sh). Low severity but a spec inconsistency worth flagging.

### Finding A-10 (NET-NEW CANDIDATE)

- **SKILL.md line 1548 vs SKILL.md line 116:** DIVERGENT Individual auditor report naming format is inconsistent between Phase 4 instructions and artifact contract.
  SKILL.md line 1548: "The spec audit must produce individual auditor report files at `quality/spec_audits/YYYY-MM-DD-auditor-N.md`"
  Artifact contract table at SKILL.md line 116: `quality/spec_audits/*auditor*.md`
  The gate at quality_gate.sh line 153 uses: `ls ${q}/spec_audits/*auditor*` — glob-based, matches either pattern.
  BUT `RUN_SPEC_AUDIT.md` output directory instruction (line 143): "Write each auditor's report to `quality/spec_audits/auditor_<model>_<date>.md`."
  Three different naming patterns exist:
  1. Phase 4 instructions: `YYYY-MM-DD-auditor-N.md`
  2. RUN_SPEC_AUDIT.md: `auditor_<model>_<date>.md`
  3. Artifact contract: `*auditor*.md`
  All three match the gate glob but agents see contradictory naming instructions. This could cause document proliferation or naming inconsistency.

---

## Summary of New Findings

| ID | Location | Type | Net-New? | Severity |
|----|----------|------|----------|---------|
| A-1 | quality_gate.sh:124 | DIVERGENT (REQ-014) | No (BUG-M4 class) | LOW |
| A-2 | quality_gate.sh:700-702 | MISSING (REQ-012) | Yes — refined version | MEDIUM |
| A-3 | quality_gate.sh:479-480 | DIVERGENT (REQ-004) | No (BUG-M4) | MEDIUM |
| A-4 | quality_gate.sh:152-153 | UNDOCUMENTED | **YES** | LOW |
| A-5 | quality_gate.sh:595-596 | UNDOCUMENTED | **YES** | LOW |
| A-6 | SKILL.md:295-297 | DIVERGENT (REQ-005) | No (BUG-M5) | MEDIUM |
| A-7 | SKILL.md:897-904 | DIVERGENT (REQ-003) | No (BUG-M3) | MEDIUM |
| A-8 | SKILL.md:1374-1407 | DIVERGENT (REQ-009) | **YES** | LOW |
| A-9 | SKILL.md:1964-1990 | DIVERGENT | **YES** | LOW |
| A-10 | SKILL.md:1548, RUN_SPEC_AUDIT.md:143 | DIVERGENT | **YES** | LOW |
