# Code Review — Pass 1: Structural Review (Unfiltered Iteration)

<!-- Quality Playbook v1.4.1 — Unfiltered Iteration Code Review Pass 1 — 2026-04-16 -->

**Pass type:** Structural review — reading code, finding what looks wrong without requirements context.
**Source:** Unfiltered iteration exploration (EXPLORATION_ITER3.md)
**Files reviewed:** `quality_gate.sh`, `SKILL.md`

---

## quality_gate.sh

### Line 124: BUG — Functional test file existence check uses multi-pattern `ls` glob vulnerable to nullglob

```bash
if ls ${q}/test_functional.* ${q}/FunctionalSpec.* ${q}/FunctionalTest.* ${q}/functional.test.* &>/dev/null 2>&1; then
```

Under nullglob (default in zsh/macOS), all unmatched glob patterns expand to empty strings. `ls` receives zero arguments and lists the current working directory, exiting 0. The check spuriously passes. The `&>/dev/null 2>&1` is also redundant (double stderr redirect). **Expected:** FAIL when no test file exists. **Actual:** PASS (false positive under nullglob). This is the FILE EXISTENCE check — distinct from BUG-M12 at line 479 (extension detection) and BUG-M8's confirmed locations.

**REGRESSION TEST:** `test_BUG_U1_functional_test_existence_nullglob` in `quality/test_regression.sh`

### Lines 184, 188-194, 313: BUG — Bug ID regex `BUG-[0-9]+` never matches severity-prefixed IDs (`BUG-H1`, `BUG-M3`), silently bypassing all TDD/patch/writeup gate validation

**Line 184:**
```bash
correct_headings=$(grep -cE '^### BUG-[0-9]+' "${q}/BUGS.md" || true)
```
**Line 313:**
```bash
bug_ids=$(grep -oE 'BUG-[0-9]+' "${q}/BUGS.md" 2>/dev/null \
    | grep -E '^BUG-[0-9]+$' | sort -u -t'-' -k2,2n)
```

The Quality Playbook generates bugs with severity-prefixed IDs: `BUG-H1` (HIGH), `BUG-M3` (MEDIUM), `BUG-L6` (LOW). The regex `BUG-[0-9]+` requires a NUMERIC suffix. It never matches `BUG-H1`, `BUG-M3`, etc. Result: `bug_count=0` and `bug_ids=""` for all QFB self-audit runs.

Consequence: The `if [ "$bug_count" -gt 0 ]` gate at line 223 (TDD sidecar JSON), line 309 (TDD log files), line 564 (patches), and line 592 (writeups) are ALL skipped with "Zero bugs — ... not required." The gate provides ZERO validation assurance for any QFB self-audit run that uses severity-prefix IDs.

**Expected:** Gate validates TDD logs, patches, writeups for 15 confirmed bugs. **Actual:** Gate reports "Zero bugs" and skips all validation.

**REGRESSION TEST:** `test_BUG_U2_bug_id_regex_bypasses_severity_prefix` in `quality/test_regression.sh`

### Lines 188-194: INCOMPLETE — Wrong-heading format checks also use `BUG-[0-9]+` regex

```bash
wrong_headings=$(grep -E '^## BUG-[0-9]+' "${q}/BUGS.md" 2>/dev/null | grep -cvE '^### BUG-' || true)
deep_headings=$(grep -cE '^#{4,} BUG-[0-9]+' "${q}/BUGS.md" || true)
bold_headings=$(grep -cE '^\*\*BUG-[0-9]+' "${q}/BUGS.md" || true)
bullet_headings=$(grep -cE '^- BUG-[0-9]+' "${q}/BUGS.md" || true)
```

All four check variants use `BUG-[0-9]+`. None detect severity-prefix format bugs at wrong heading levels. If a run used `## BUG-H1` (wrong level), none of these checks would catch it. The heading format validation is entirely blind to severity-prefix IDs.

### Line 293-298: BUG — `red_phase`/`green_phase` JSON enum values not cross-validated against log file first-line tags

The gate validates log file first-line tags (`RED|GREEN|NOT_RUN|ERROR`) at lines 323-325 and 337-340. The gate validates JSON field PRESENCE at lines 239-248 but does NOT validate field VALUES for `red_phase` and `green_phase`. No code cross-validates the JSON phase values against log evidence.

**SKILL.md:1589 mandates:** "TDD sidecar-to-log consistency check (mandatory). For every bug entry in tdd-results.json, verify the corresponding log files exist and agree."

**Expected:** If `verdict: "TDD verified"` and `red.log` shows `RED` (fail), that's correct. If `verdict: "TDD verified"` and `red.log` shows `GREEN` (pass — meaning test passed on unpatched code, NOT a red phase), gate should FAIL.

**Actual:** Gate verifies the log tag format is valid but doesn't check consistency with the JSON verdict. Contradictory pairs (e.g., `"red_phase": "pass"` with a log showing `RED`) pass both checks.

**REGRESSION TEST:** `test_BUG_U3_red_phase_log_cross_validation` in `quality/test_regression.sh`

### Line 186-187: QUESTION — `wrong_headings` logic seems correct but is confusing

```bash
wrong_headings=$(grep -E '^## BUG-[0-9]+' "${q}/BUGS.md" 2>/dev/null | grep -cvE '^### BUG-' || true)
```

The nested grep logic is correct (filter `##` lines → count those NOT matching `###`) but the logic is hard to read and doesn't clearly communicate intent. Not a bug, but the code is more complex than it needs to be. A simpler version: `grep -cE '^## BUG-' "${q}/BUGS.md" 2>/dev/null || true`. Not flagging as BUG — flagging as QUESTION.

### Line 253-255: QUESTION — Wrong field name detector propagates BUG-H1 false positive (self-defeating)

```bash
for bad_field in bug_id bug_name status phase result; do
    if json_has_key "$json_file" "$bad_field"; then
        fail "non-canonical field '${bad_field}' found (use standard field names)"
    fi
done
```

`json_has_key` matches field names anywhere including string values (BUG-H1). If a bug's `notes` field says "the old `status` field was renamed to `verdict`", this check flags `status` as a non-canonical field, causing a false FAIL on a conformant file. This is already covered by BUG-H1's fix — flagging as QUESTION to document the propagation.

### Line 259-265: QUESTION — Summary key check propagates BUG-H1 false positive

```bash
for skey in total verified confirmed_open red_failed green_failed; do
    if json_has_key "$json_file" "$skey"; then
        pass "summary has '${skey}'"
```

If the file has a notes field mentioning "total confirmed_open count", `json_has_key "total"` returns true even if the actual summary object lacks the key. Already covered by BUG-H1 — flagging as QUESTION.

### Line 124: QUESTION — Redundant `&>/dev/null 2>&1` redirect

`&>/dev/null` redirects both stdout and stderr to /dev/null. `2>&1` then redirects stderr to stdout (which is already /dev/null). The second redirect is a no-op. This is cosmetic but confusing — a reader might think it's doing something additional.

---

## SKILL.md

### Lines 37-39 vs 376: BUG — MANDATORY FIRST ACTION has no autonomous-mode qualifier (BUG-REQ-008 confirmed)

Already tracked as the spec basis for REQ-008. The MANDATORY FIRST ACTION produces multi-paragraph user-facing prose in autonomous/benchmark mode that wastes context budget. This is an existing confirmed bug (REQ-008). Not a new bug.

### Line 1615: BUG — Spec example `### BUG-001` conflicts with established QFB naming convention `BUG-H1`

SKILL.md line 1615 specifies: "Each confirmed bug must use the heading level `### BUG-NNN` (e.g., `### BUG-001`)." The example `BUG-001` implies pure-numeric suffix format. But the Quality Playbook's own Phase 3 generates severity-prefixed IDs by convention. The spec is ambiguous — the heading LEVEL is specified (`###`) but the ID FORMAT example conflicts with established practice.

This is the SKILL.md side of CAND-U2. The gate enforces `BUG-[0-9]+` (matching the spec example) but the actual tool generates `BUG-H1` (contradicting the spec example).

### Lines 134-136 vs 1384-1386: BUG — Two incompatible tdd-results.json templates (BUG-L11 confirmed)

Already tracked as BUG-L11. Not a new finding.

---

## Combined Summary

| Source | Finding | Severity | Status |
|--------|---------|----------|--------|
| Pass 1, quality_gate.sh:124 | Functional test existence check ls-glob vulnerable to nullglob | MEDIUM | BUG |
| Pass 1, quality_gate.sh:184,313 | BUG-[0-9]+ regex silently bypasses severity-prefix IDs, gate provides zero assurance | HIGH | BUG |
| Pass 1, quality_gate.sh:293-298 | red_phase/green_phase JSON values not cross-validated against log tags | MEDIUM | BUG |
| Pass 1, quality_gate.sh:186-187 | wrong_headings logic confusing but correct | LOW | QUESTION |
| Pass 1, quality_gate.sh:253-255 | Wrong field detector propagates BUG-H1 false positive | LOW | QUESTION (covered by BUG-H1) |
| Pass 1, quality_gate.sh:259-265 | Summary key check propagates BUG-H1 false positive | LOW | QUESTION (covered by BUG-H1) |
| Pass 1, SKILL.md:1615 | BUG-001 example conflicts with BUG-H1 convention | HIGH | BUG (SKILL.md side of CAND-U2) |

**New BUGs confirmed in Pass 1:** 3 (line 124, lines 184/313, lines 293-298)
**Overall assessment: FIX FIRST** — two HIGH severity issues directly compromise gate integrity.
