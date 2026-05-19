# Code Review — Pass 2: Requirement Verification (Unfiltered Iteration)

<!-- Quality Playbook v1.4.1 — Unfiltered Iteration Code Review Pass 2 — 2026-04-16 -->

**Pass type:** Pure requirement verification — each new requirement checked against the code.
**Source:** REQ-019, REQ-020, REQ-021 (added in unfiltered iteration)
**Files reviewed:** `quality_gate.sh`, `SKILL.md`

---

## REQ-019: Gate Script Functional Test File Existence Check Must Use find, Not ls-glob

**Status:** VIOLATED

**Evidence:** `quality_gate.sh:124` — `if ls ${q}/test_functional.* ${q}/FunctionalSpec.* ${q}/FunctionalTest.* ${q}/functional.test.* &>/dev/null 2>&1; then`

**Analysis:** REQ-019 requires the functional test file existence check to use find-based detection (or equivalent) that does not exhibit the nullglob vulnerability. The current implementation uses `ls` with four unquoted glob patterns. Under nullglob, unmatched globs expand to empty, causing `ls` to list CWD and exit 0. The requirement is not satisfied — the code uses `ls`-glob, not find-based detection.

**Comparison with compliant pattern:** Lines 449-454 use `find "${repo_dir}" -maxdepth 3 ... -print -quit 2>/dev/null | grep -q .` — the correct pattern. Line 124 should use the same approach.

**Severity:** MEDIUM — on macOS/zsh with nullglob, conformant runs with test_functional.sh may fail the gate; non-conformant runs without test_functional.sh may pass.

---

## REQ-020: BUGS.md Heading Regex Must Match Severity-Prefixed Bug IDs

**Status:** VIOLATED

**Evidence:**
- `quality_gate.sh:184` — `correct_headings=$(grep -cE '^### BUG-[0-9]+' "${q}/BUGS.md" || true)`
- `quality_gate.sh:188` — `wrong_headings=$(grep -E '^## BUG-[0-9]+' ...)` 
- `quality_gate.sh:189` — `deep_headings=$(grep -cE '^#{4,} BUG-[0-9]+' ...)` 
- `quality_gate.sh:190` — `bold_headings=$(grep -cE '^\*\*BUG-[0-9]+' ...)`
- `quality_gate.sh:191` — `bullet_headings=$(grep -cE '^- BUG-[0-9]+' ...)`
- `quality_gate.sh:313` — `bug_ids=$(grep -oE 'BUG-[0-9]+' ...)` 

**Analysis:** REQ-020 requires the heading regex to match severity-prefixed IDs (`BUG-H1`, `BUG-M3`, `BUG-L6`). All six grep patterns use `BUG-[0-9]+` requiring a pure numeric suffix. None match `BUG-H1`, `BUG-M3`, `BUG-L6`. The requirement is VIOLATED. With 15 severity-prefixed bugs in BUGS.md: `correct_headings=0`, `bug_count=0`, `bug_ids=""`. All downstream validation (lines 223, 309, 564, 592) is skipped.

**Also violated in SKILL.md:** SKILL.md:1615 uses example `### BUG-001` (numeric format) but QFB generates `BUG-H1` (severity-prefix format). The spec example is ambiguous and contributes to the gate's wrong regex.

**Severity:** HIGH — gate provides zero validation for any run using QFB's established severity-prefix naming convention.

---

## REQ-021: Gate Must Cross-Validate tdd-results.json Phase Values Against Log File Tags

**Status:** VIOLATED

**Evidence:**
- `quality_gate.sh:239-248` — validates per-bug fields for PRESENCE only; no validation of `red_phase` or `green_phase` VALUES
- `quality_gate.sh:322-325` — validates log file first-line tag: `case "$red_tag" in RED|GREEN|NOT_RUN|ERROR) ;;`
- No code exists in quality_gate.sh that compares `json_str_val ... "red_phase"` with the log file tag for the same bug

**Analysis:** REQ-021 requires cross-validation between JSON `red_phase`/`green_phase` values and log file first-line tags. SKILL.md:1589 mandates this as "TDD sidecar-to-log consistency check (mandatory)." The gate validates JSON field PRESENCE (sufficient occurrences of key) but never extracts and validates the VALUE of `red_phase`. The log file tag is validated separately (format only). No intersection.

**Concrete path where violation occurs:** An agent writes `"verdict": "TDD verified"`, `"red_phase": "pass"`, and a `BUG-001.red.log` with first line `RED`. The gate:
1. Validates `red_phase` present (passes — key found)
2. Validates log tag: `RED` is in `RED|GREEN|NOT_RUN|ERROR` (passes)
3. Never compares `"pass"` with `RED` — no cross-check exists

**Severity:** MEDIUM — the TDD sidecar-to-log consistency check that SKILL.md mandates is entirely absent from the gate implementation.

---

## Previously Verified Requirements (Spot-Check Confirmation)

### REQ-001: JSON Key Presence Validation (BUG-H1)

**Status:** VIOLATED (confirmed in prior iterations, propagation documented in this iteration)

**New evidence from unfiltered iteration:** The propagation to summary key check (lines 259-265) and wrong-field detector (lines 253-255) was documented in EXPLORATION_ITER3.md Findings 6 and 7. Both checks call `json_has_key` which has the BUG-H1 false positive. This iteration's analysis adds concrete scenarios where both checks produce false positives on conformant files.

### REQ-002: Repo Path Array Reconstruction (BUG-H2)

**Status:** VIOLATED (confirmed in prior iterations)

**New evidence from unfiltered iteration:** EXPLORATION_ITER3.md Finding 5 traced the full path survival: arg parser correctly handles spaces → loop at line 686 correctly quotes `"$name"` → `resolved` array correctly stores the path → line 697 word-splits on the path when constructing `REPO_DIRS`. The path survives three steps but fails at the reconstruction.

---

## Combined Summary

| Requirement | Status | Evidence Location | Severity |
|-------------|--------|-------------------|----------|
| REQ-019 | VIOLATED | quality_gate.sh:124 | MEDIUM |
| REQ-020 | VIOLATED | quality_gate.sh:184,188-194,313 | HIGH |
| REQ-021 | VIOLATED | quality_gate.sh:239-248 (absence) vs SKILL.md:1589 | MEDIUM |
| REQ-001 | VIOLATED (propagation documented) | quality_gate.sh:253-255, 259-265 | HIGH |
| REQ-002 | VIOLATED (root cause traced) | quality_gate.sh:697 via 686→resolved→697 | HIGH |

**Pass 2 summary:** 3 new requirement violations confirmed (REQ-019, REQ-020, REQ-021). 2 existing violations have new supporting evidence. All 3 new violations have corresponding BUG candidates in EXPLORATION_ITER3.md.
