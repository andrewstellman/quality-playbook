# BUG-M18 Writeup: TDD Sidecar JSON Phase Values Not Cross-Validated Against Log Tags

**Severity**: MEDIUM
**File:Line**: `quality_gate.sh:239-248` (JSON presence check), `quality_gate.sh:307-387` (log validation)
**Requirement**: REQ-021

---

## Summary

`SKILL.md:1589` mandates a "TDD sidecar-to-log consistency check (mandatory)": for each bug with `"verdict": "TDD verified"`, the corresponding `BUG-NNN.red.log` must have first line `RED` and `BUG-NNN.green.log` must have first line `GREEN`. The gate validates JSON field PRESENCE (lines 239-248) and log tag FORMAT (lines 322-325) as two independent checks — but never compares them. A `tdd-results.json` with `"red_phase": "pass"` alongside a log file whose first line contradicts it passes all gate checks without any contradiction detected.

---

## Root Cause

The gate's TDD validation has two sections that should be connected but are not:

**Section 1 (lines 239-248): JSON field presence check**
```bash
for field in id requirement red_phase green_phase verdict fix_patch_present writeup_path; do
    if ! json_key_count "$field" "${tdd_file}" | grep -q '^[1-9]'; then
        fail "Bug ${bid}: tdd-results.json missing field '${field}'"
    fi
done
```
This confirms `red_phase` KEY EXISTS. It does not extract or examine the VALUE.

**Section 2 (lines 322-325): Log tag format check**
```bash
red_tag=$(head -1 "${q}/results/${bid}.red.log" 2>/dev/null | tr -d '[:space:]')
case "$red_tag" in
    RED|GREEN|NOT_RUN|ERROR) ;;
    *) red_bad_tag=$((red_bad_tag + 1)) ;;
esac
```
This confirms the tag is one of four valid values. It does not compare against the JSON phase value.

**The missing cross-validation (per SKILL.md:1589)**:
```bash
# Required but absent:
json_red_phase=$(json_str_val "red_phase" "${tdd_file}" "${bid}")
if [ "$json_red_phase" = "pass" ] && [ "$red_tag" != "RED" ]; then
    fail "Bug ${bid}: tdd-results.json red_phase='pass' but red.log tag is '${red_tag}' (expected RED)"
fi
```

---

## Fabrication Scenario

An agent writes:
```json
{
  "id": "BUG-H1",
  "red_phase": "Regression test confirms bug on unpatched code — RED",
  "green_phase": "Test passes after fix patch applied — GREEN",
  "verdict": "TDD verified"
}
```

With `BUG-H1.red.log` first line: `GREEN` (meaning: the test passed on unpatched code — the bug was NOT reproduced, invalidating the TDD claim).

Gate behavior (unpatched):
- JSON field presence check: `red_phase` key exists → PASS
- Log tag format check: `GREEN` is in `RED|GREEN|NOT_RUN|ERROR` → PASS
- No comparison of `"TDD verified"` claim vs `GREEN` tag contradiction
- Gate reports PASS for a fabricated TDD cycle

This undermines the entire purpose of TDD verification as a quality gate.

---

## Fix

Add cross-validation between JSON phase description and log tag, after the log existence check at lines 318-330. The fix requires:

1. Extract `red_phase` string value from `tdd-results.json` using `json_str_val`
2. If `verdict` is `"TDD verified"`, validate that `red_tag = RED` (bug confirmed reproducible on unpatched code)
3. If `verdict` is `"TDD verified"`, validate that `green_tag = GREEN` (bug resolved by fix patch)
4. Emit `fail` if any contradiction is detected

This fix is additive to the existing log section and does not require restructuring. See `quality/patches/BUG-M18-regression-test.patch` for the regression test.

Note: No fix patch is provided for the production code. The fix logic is specified in SKILL.md:1589 and the code change is straightforward but requires careful integration with the existing per-bug iteration loop.

---

## TDD Evidence

- **Red phase log**: `quality/results/BUG-M18.red.log` — first line `RED`
  - No cross-validation code found: `grep -A5 'red_phase|green_phase' quality_gate.sh | grep 'json_str_val'` → NO MATCH
  - `grep 'red_phase.*red_tag|red_tag.*red_phase' quality_gate.sh` → NO MATCH
  - Test exits 1 (FAIL) — confirms bug on unpatched code
- **Green phase log**: Not applicable (no fix patch — confirmed open)
- **Verdict**: confirmed open (fix requires non-trivial new code section)
- **Regression test**: `quality/patches/BUG-M18-regression-test.patch`
