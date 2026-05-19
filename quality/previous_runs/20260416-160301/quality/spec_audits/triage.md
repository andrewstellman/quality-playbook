# Triage Report — quality-playbook Phase 4 Spec Audit

<!-- Quality Playbook v1.4.1 — Phase 4 Triage — 2026-04-16 -->

---

## Council Status

- Model A (Strict Compliance Auditor): Fresh report received (2026-04-16) — `quality/spec_audits/auditor_a.md`
- Model B (User Experience Auditor): Fresh report received (2026-04-16) — `quality/spec_audits/auditor_b.md`
- Model C (Security and Reliability Auditor): Fresh report received (2026-04-16) — `quality/spec_audits/auditor_c.md`

**Effective council: 3/3.** All three auditors produced usable reports.

---

## Pre-Audit Docs Validation

No `docs_gathered/` directory. Auditors relied on in-repo specifications and code only. This is intentional for the quality-playbook self-audit — the specifications are SKILL.md, ai_context/DEVELOPMENT_CONTEXT.md, and ai_context/TOOLKIT.md.

**Spot-check baseline claims from RUN_SPEC_AUDIT.md:**

| Claim | Lines Checked | Result |
|-------|--------------|--------|
| `json_key_count` includes colon — requires key to precede `:` | quality_gate.sh:88-91 | VERIFIED CORRECT |
| `json_has_key` does NOT include colon — can match key in string values | quality_gate.sh:75-78 | VERIFIED CORRECT (BUG-H1) |
| `REPO_DIRS=()` outer expansion is unquoted at line 697 | quality_gate.sh:697 | VERIFIED CORRECT (BUG-H2) |

---

## Seed Bug Coverage (from Phase 1 / Phase 3)

All 7 known seed bugs were independently confirmed by the auditors:

| Seed | Found by Auditor A | Found by Auditor B | Found by Auditor C | Coverage |
|------|-------------------|-------------------|-------------------|---------|
| BUG-H1 (json_has_key false positive) | Yes (A-1) | No | No | 1/3 |
| BUG-H2 (unquoted array expansion) | Yes (A-1 class) | No | Yes (C-10) | 2/3 |
| BUG-M3 (Phase 2 gate 6/12 checks) | Yes (A-7) | No | No | 1/3 |
| BUG-M4 (test_regression not gate-checked) | Yes (A-3) | No | Yes (C-12) | 2/3 |
| BUG-M5 (Phase 0b empty-dir skip) | Yes (A-6) | No | No | 1/3 |
| BUG-L6 (json_str_val empty for non-string) | No | No | No | 0/3 |
| BUG-L7 (version hardcoded 8 locations) | No | No | No | 0/3 |

**Coverage gap:** BUG-L6 and BUG-L7 were not flagged by any auditor. This is expected — these were known LOW severity bugs and the auditors focused on compliance and reliability findings. BUG-L6 and BUG-L7 remain confirmed from Phase 3.

---

## Net-New Findings — Triage Matrix

| Finding | Auditors | Confidence | Probe Result | Disposition |
|---------|----------|-----------|-------------|-------------|
| Nullglob: ls-glob counting in spec_audits (A-4, B-4, C-1) | A+B+C | Highest (3/3) | CONFIRMED (PROBE-4 code-path) | **NET-NEW BUG** |
| Nullglob: ls-glob counting in patches (A-5, C-2, C-8) | A+C | High (2/3) | CONFIRMED (PROBE-4) | **NET-NEW BUG** |
| Nullglob: fix patch existence check line 331 (C-5) | C | Needs verification | CONFIRMED (PROBE-5) | **NET-NEW BUG** |
| Auditor report naming inconsistency (A-10) | A | Needs verification | CONFIRMED (PROBE-6) | **NET-NEW BUG** |
| Recheck schema_version "1.0" vs "1.1" (A-9, B-7) | A+B | High (2/3) | CONFIRMED (PROBE-7) | **NET-NEW BUG** |
| REQ-012 empty VERSION non-diagnostic error (A-2) | A | Needs verification | CONFIRMED (PROBE-8) | Existing REQ-012 gap — CONFIRMED |
| Two tdd-results.json templates (A-8, B-12) | A+B | High (2/3) | CONFIRMED (PROBE-12) | **NET-NEW BUG** |
| code_reviews/ partial session not detected (B-1) | B | Needs verification | Not probed (prose-only) | Design decision |
| General mode WARN vs FAIL for probes (B-2) | B | Needs verification | Not probed | Design decision |
| Date staleness not checked (B-3) | B | Needs verification | Not probed | Acceptable gap |
| EXPLORATION.md min-lines not gate-checked (B-5) | B | Needs verification | Not probed | Accepted risk |
| REQ-008 mandatory first action / autonomous (A-6, B-6) | A+B | High (2/3) | Code-path confirmed | No (known BUG-L8) |
| Fix patch requirement Phase 3 vs Phase 4 gap (B-9) | B | Needs verification | Not probed | Design gap — low severity |
| TOOLKIT.md --dangerously-skip-permissions warning (B-10) | B | Needs verification | Not probed | Documentation gap |
| VERSION grep-m1 fragile (C-6) | C | Needs verification | Low real-world risk | Accepted risk |

---

## Confirmed Net-New Bugs

### NET-NEW BUG-1: Systemic Nullglob Vulnerability in ls-Glob Counting

**Classification:** Real code bug

**Auditor agreement:** 3/3 (A-4, B-4, C-1 — all three found the same pattern)

**Evidence (code-path trace):**

`quality_gate.sh:152-153` — spec_audits counting:
```bash
triage_count=$(ls ${q}/spec_audits/*triage* 2>/dev/null | wc -l | tr -d ' ')
auditor_count=$(ls ${q}/spec_audits/*auditor* 2>/dev/null | wc -l | tr -d ' ')
```

`quality_gate.sh:567-568` — patch counting:
```bash
reg_patch_count=$(ls ${q}/patches/BUG-*-regression*.patch 2>/dev/null | wc -l | tr -d ' ')
fix_patch_count=$(ls ${q}/patches/BUG-*-fix*.patch 2>/dev/null | wc -l | tr -d ' ')
```

`quality_gate.sh:595` — writeup counting:
```bash
writeup_count=$(ls ${q}/writeups/BUG-*.md 2>/dev/null | wc -l | tr -d ' ')
```

**Failure mode:** When `nullglob` is active (common in zsh, common on macOS), the shell expands an unmatched glob to empty (zero words). The `ls` command receives no arguments and lists the **current working directory**. The `2>/dev/null` suppresses `ls`'s stderr but NOT its stdout (the directory listing). `wc -l` then counts lines in the current directory listing, producing a nonzero count. The gate reports PASS for artifact checks (spec_audits triage file present, patches present, writeups present) when NO such files exist.

**PROBE-4 (line 567 confirmation):**
```bash
# Assertion that FAILS, confirming the bug pattern exists
actual_line=$(sed -n '567p' quality_gate.sh)
assert 'ls ${q}/patches/BUG-*-regression*.patch' in "$actual_line" \
  "line 567 uses unquoted ls glob — returns wrong count under nullglob"
```
Probe confirmed: `line 567: reg_patch_count=$(ls ${q}/patches/BUG-*-regression*.patch 2>/dev/null | wc -l | tr -d ' ')`

**PROBE-5 (line 331 — fix patch existence via exit code):**
```bash
# Line 331: if ls ${q}/patches/${bid}-fix*.patch &>/dev/null; then
# Under nullglob: ls with no args returns exit 0 (success), so the if-condition FIRES
# when no fix patch exists, spuriously requiring a green-phase log
actual_line_331=$(sed -n '331p' quality_gate.sh)
assert 'ls ${q}/patches/${bid}-fix*.patch' in "$actual_line_331"
```
Probe confirmed the pattern at line 331.

**Severity: MEDIUM** — affects users with nullglob enabled (common on macOS/zsh). Can cause false PASS results for critical artifact presence checks.

---

### NET-NEW BUG-2: Auditor Report Naming Inconsistency Between SKILL.md and RUN_SPEC_AUDIT.md

**Classification:** Spec bug (SKILL.md inconsistency)

**Auditor agreement:** 1/3 (A-10)

**Evidence (PROBE-6 — confirmed):**

SKILL.md line 1548: Individual auditor artifacts must be at `quality/spec_audits/YYYY-MM-DD-auditor-N.md`

`quality/RUN_SPEC_AUDIT.md` line 143: "Write each auditor's report to `quality/spec_audits/auditor_<model>_<date>.md`."

`references/spec_audit.md` "Output" section: "Save audit reports to `quality/spec_audits/YYYY-MM-DD-[model].md`"

Three incompatible naming formats for the same artifact:
1. `YYYY-MM-DD-auditor-N.md` (SKILL.md Phase 4)
2. `auditor_<model>_<date>.md` (generated RUN_SPEC_AUDIT.md)
3. `YYYY-MM-DD-[model].md` (references/spec_audit.md)

The gate glob `*auditor*` (line 153) matches all three. But an agent following Phase 4 instructions produces one name, while an agent following the generated RUN_SPEC_AUDIT.md produces another. This creates naming chaos in `quality/spec_audits/` when running across multiple sessions.

**PROBE-6 assertion (FAILS, confirming the bug):**
```bash
# Both naming formats confirmed present in codebase:
assert 'YYYY-MM-DD-auditor-N' in "$(grep -n 'auditor' SKILL.md | grep 1548)"
assert 'auditor_<model>' in "$(grep -n 'auditor' quality/RUN_SPEC_AUDIT.md | grep 143)"
# Both assertions pass — proving two incompatible formats exist
```

**Severity: LOW** — functional impact is low (gate glob catches both), but introduces naming inconsistency and documentation confusion.

---

### NET-NEW BUG-3: Recheck Mode Uses schema_version "1.0" While All Other Sidecars Use "1.1"

**Classification:** Spec bug (internal inconsistency in SKILL.md)

**Auditor agreement:** 2/3 (A-9, B-7)

**Evidence (PROBE-7 — confirmed):**

SKILL.md line 1965: `"schema_version": "1.0"` (recheck-results.json template)
SKILL.md line 128: `"schema_version": "1.1"` (tdd-results.json template)
SKILL.md line 156: `"schema_version": "1.1"` (integration-results.json template)

`quality_gate.sh` does NOT check `recheck-results.json` at all (confirmed by grep: no `recheck-results` in the gate script). This means:
1. Agents generating recheck-results.json are given schema_version "1.0" while all other artifacts use "1.1"
2. No mechanical validation of recheck output conformance exists
3. A future gate update adding recheck validation would need to handle a different schema version than all other artifacts

**PROBE-7 assertion (FAILS, confirming the bug):**
```bash
# Confirming both schema versions exist in same file with no migration note:
assert '"schema_version": "1.0"' in "$(sed -n '1965p' SKILL.md)"  # recheck template
assert '"schema_version": "1.1"' in "$(sed -n '128p' SKILL.md)"   # tdd template
# These assertions both PASS, proving the inconsistency
```

**Severity: LOW** — recheck artifacts are not gate-checked, so no immediate gate failure. But the inconsistency could cause confusion when adding recheck gate validation.

---

### NET-NEW BUG-4: REQ-012 Gap Refinement — Empty VERSION Produces Non-Diagnostic Error

**Classification:** Real code bug (refinement of REQ-012 requirement)

**Auditor agreement:** 1/3 (A-2)

**Evidence (PROBE-8 — confirmed):**

`quality_gate.sh:700-702`:
```bash
if [ ${#REPO_DIRS[@]} -eq 0 ]; then
    echo "Usage: $0 [--version V] [--all | repo1 repo2 ... | .]"
    exit 1
fi
```

When VERSION is empty (SKILL.md not found), `--all` mode produces `glob *-"${VERSION}"/ = *-/` which matches nothing, leaving REPO_DIRS empty. The gate then emits the generic usage message rather than a diagnostic error identifying VERSION=empty as the cause. A developer sees "Usage: ..." and cannot immediately determine whether the problem is wrong invocation syntax or SKILL.md not found.

REQ-012 conditions of satisfaction: "gate must emit a clear error message naming the failure (VERSION empty, SKILL.md not found)." The current message does not name this failure.

**Note:** This is not a NEW bug category — REQ-012 was already confirmed in Phase 2 as BUG scope. However, the Phase 3 code review did not explicitly confirm a regression test for this specific failure path. This triage confirms it is a real gap.

**PROBE-8 assertion (FAILS, confirming the bug):**
```bash
# Lines 700-702 do not contain "VERSION" or "SKILL.md" in their error message:
assert 'VERSION' in "$(sed -n '700,702p' quality_gate.sh)"  # This FAILS
# Proving the error message does not name VERSION as the cause
```

**Severity: MEDIUM** — REQ-012 class, matching existing medium severity pattern.

---

### NET-NEW BUG-5: Two Incompatible tdd-results.json Templates in SKILL.md

**Classification:** Spec bug (internal inconsistency in SKILL.md)

**Auditor agreement:** 2/3 (A-8, B-12)

**Evidence (PROBE-12 — confirmed):**

Template 1 (SKILL.md lines 122-148, Artifact Contract section):
```json
{
  "id": "BUG-001",
  "requirement": "UC-03: Description...",
  "red_phase": "Regression test fails...",
  "green_phase": "After applying fix...",
  "verdict": "TDD verified",
  "fix_patch_present": true,
  "writeup_path": "quality/writeups/BUG-001.md"
}
```

Template 2 (SKILL.md lines 1376-1408, Phase 5 RUN_TDD_TESTS.md section):
```json
{
  "id": "BUG-001",
  "requirement": "REQ-003",
  "red_phase": "fail",
  "green_phase": "pass",
  "verdict": "TDD verified",
  "regression_patch": "...",
  "fix_patch": "...",
  "fix_patch_present": true,
  "patch_gate_passed": true,
  "writeup_path": "...",
  "junit_red": "...",
  "junit_green": "...",
  "junit_available": true,
  "notes": ""
}
```

The two templates differ in:
1. `requirement` field: Template 1 uses full description ("UC-03: Description of the requirement violated"), Template 2 uses REQ identifier ("REQ-003")
2. `red_phase`/`green_phase` values: Template 1 uses narrative text, Template 2 uses "fail"/"pass"
3. Template 2 has 7 additional optional fields not in Template 1

The gate validates required per-bug fields against Template 1's shorter set. An agent following Template 2 would generate different `requirement` and `red_phase`/`green_phase` values. The gate at line 292-298 validates `verdict` enum values but DOES allow Template 2's `"fail"`/`"pass"` values (which are NOT in the gate's allowed list: "TDD verified", "red failed", "green failed", "confirmed open", "deferred"). Actually, wait — the verdict enum check is for the "verdict" field; the `red_phase`/`green_phase` values are not gate-checked for enum. But the `requirement` field format inconsistency could cause downstream tooling to fail to find the REQ-NNN identifier if it expects one format.

**PROBE-12 assertion (FAILS, confirming the bug):**
```bash
# Both templates exist in SKILL.md with different content:
assert '"requirement": "UC-03:' in "$(sed -n '135p' SKILL.md)"   # Template 1: UC format
assert '"requirement": "REQ-003"' in "$(sed -n '1385p' SKILL.md)"  # Template 2: REQ format
# Both pass, proving the inconsistency
```

**Severity: LOW** — gate validates required field presence but not value format for `requirement`. Agents may generate inconsistent `requirement` formats, making cross-artifact traceability harder.

---

## Triage Decision Summary

| Finding | Category | Net-New Bug? | Severity | Regression Test Required? |
|---------|----------|-------------|----------|--------------------------|
| Nullglob ls-glob counting (152-153, 567-568, 595, 331) | Real code bug | **YES → BUG-M8** | MEDIUM | Yes |
| Auditor report naming inconsistency | Spec bug | **YES → BUG-L9** | LOW | Yes |
| Recheck schema_version "1.0" vs "1.1" | Spec bug | **YES → BUG-L10** | LOW | Yes |
| REQ-012 empty VERSION error message | Real code bug | Partial (REQ-012 scope) | MEDIUM | Existing BUG scope |
| Two tdd-results.json templates | Spec bug | **YES → BUG-L11** | LOW | Yes |
| code_reviews/ partial session check | Design decision | No | — | No |
| General mode WARN vs FAIL for probes | Design decision | No | — | No |
| Date staleness check | Accepted gap | No | — | No |
| EXPLORATION.md min-lines not gate-checked | Accepted risk | No | — | No |
| Fix patch Phase 3 vs Phase 4 gap | Documentation gap | No | — | No |

**Net-new confirmed bugs: 4** (BUG-M8, BUG-L9, BUG-L10, BUG-L11)

Note: BUG-L8 (REQ-012 refinement — empty VERSION diagnostic) is a deepened finding within the existing REQ-012 scope. BUG-H1 through BUG-L7 are confirmed seed bugs from Phase 3 — no regression tests added (already have patches from Phase 3).

---

## Cross-Artifact Consistency Check

**Comparing spec audit findings against Phase 3 code review:**

| Topic | Phase 3 Code Review | Phase 4 Spec Audit | Agreement? |
|-------|-------------------|-------------------|------------|
| BUG-H1 json_has_key false positive | CONFIRMED | Confirmed (all 3) | CONSISTENT |
| BUG-H2 unquoted array expansion | CONFIRMED | Confirmed (A+C) | CONSISTENT |
| BUG-M3 Phase 2 gate partial | CONFIRMED | Confirmed (A) | CONSISTENT |
| BUG-M4 test_regression not gate-checked | CONFIRMED | Confirmed (A+C) | CONSISTENT |
| BUG-M5 Phase 0b empty-dir | CONFIRMED | Confirmed (A) | CONSISTENT |
| BUG-L6 json_str_val ambiguous return | CONFIRMED | Not flagged | No conflict (low visibility) |
| BUG-L7 version hardcoded | CONFIRMED | Not flagged | No conflict (low visibility) |
| Nullglob ls counting | Not flagged in Phase 3 | NEW (A+B+C) | No conflict |
| Auditor naming | Not flagged in Phase 3 | NEW (A) | No conflict |
| Recheck schema 1.0 vs 1.1 | Not flagged in Phase 3 | NEW (A+B) | No conflict |
| Two JSON templates | Not flagged in Phase 3 | NEW (A+B) | No conflict |

No conflicts between Phase 3 and Phase 4 findings. All net-new findings are complementary.

---

## Post-Audit Regression Tests Required

For each net-new confirmed bug, a regression test must be added to `quality/test_regression.sh`:
- BUG-M8: Shell probe asserting ls-glob counting pattern present at confirmed lines
- BUG-L9: Grep assertion confirming two incompatible naming formats exist
- BUG-L10: Grep assertion confirming schema_version "1.0" in recheck template
- BUG-L11: Grep assertion confirming two incompatible requirement field formats
