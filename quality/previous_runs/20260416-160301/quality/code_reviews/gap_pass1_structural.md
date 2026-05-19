# Code Review — Gap Iteration Pass 1: Structural Review
<!-- Quality Playbook v1.4.1 — Gap Iteration Code Review — 2026-04-16 -->

## Bootstrap

Read before reviewing:
1. `quality/QUALITY.md` — quality constitution
2. `quality/REQUIREMENTS.md` — all 18 requirements (REQ-001 through REQ-018)
3. `quality/EXPLORATION_ITER2.md` — gap iteration findings
4. `quality/BUGS.md` — 11 already-confirmed bugs (do not re-find these)

## Pass 1: Structural Review

This pass focuses on the gap areas not covered by the baseline code review: quality_gate.sh lines 143, 479 (ls-glob extension detection), and the recommendation enum inconsistency in references/review_protocols.md.

---

### quality_gate.sh

#### Line 143: `ls ${q}/code_reviews/*.md 2>/dev/null` — ls-glob produces false positive under nullglob
- **Line 143:** **BUG** `[ -n "$(ls ${q}/code_reviews/*.md 2>/dev/null)" ]` — Under nullglob (zsh default on macOS), the glob `${q}/code_reviews/*.md` when no `.md` files exist expands to empty string, causing `ls` to receive no arguments and list the current working directory. The command substitution captures this CWD listing, making `[ -n "..." ]` TRUE. The gate passes `"code_reviews/ has .md files"` even when the directory is empty.
  - **Expected:** `[ -n "..." ]` should be FALSE when code_reviews/ contains no .md files
  - **Actual:** Under nullglob, `[ -n "$(ls ${q}/code_reviews/*.md 2>/dev/null)" ]` evaluates TRUE because ls lists CWD
  - **Impact:** A partial run (code_reviews/ created but empty) passes the gate check, giving false confidence
  - **REGRESSION TEST:** `test_BUG_G2_code_reviews_ls_glob_false_pass` in `quality/test_regression.sh`

#### Line 479: `func_test=$(ls ${q}/test_functional.* 2>/dev/null | head -1)` — ls-glob produces wrong filename under nullglob
- **Line 479:** **BUG** `func_test=$(ls ${q}/test_functional.* 2>/dev/null | head -1)` — Same nullglob vulnerability as BUG-M8. When `${q}/test_functional.*` matches nothing, the glob expands to empty under nullglob, `ls` lists CWD, and `head -1` captures the first CWD entry. `func_test` becomes non-empty (a CWD filename), causing `if [ -n "$func_test" ]` at line 481 to evaluate TRUE spuriously. The extension check at line 482 extracts the extension from a CWD filename (e.g., `.log`, `.sh`) instead of the actual test file.
  - **Expected:** `func_test` must be empty when no test_functional.* exists in `${q}`
  - **Actual:** Under nullglob, `func_test` contains a CWD filename
  - **Impact:** Extension validation runs on wrong file. Can produce FAIL (wrong extension) when actual test file has correct extension but nullglob caused wrong file to be selected.
  - **Comparison:** Lines 486–495 in the SAME function block use `find ... -print -quit 2>/dev/null | grep -q .` for language detection — the inconsistency is within 7 lines of the bug.
  - **REGRESSION TEST:** `test_BUG_G1_test_file_ext_ls_glob_false_positive` in `quality/test_regression.sh`

#### Line 152: `ls ${q}/spec_audits/*triage* 2>/dev/null | wc -l` — Previously confirmed as part of BUG-M8
- **ALREADY CONFIRMED as BUG-M8.** Not a new finding. The fix patch BUG-M8-fix.patch covers this location.

#### Line 331: `ls ${q}/patches/${bid}-fix*.patch &>/dev/null` — Previously confirmed as part of BUG-M8
- **ALREADY CONFIRMED as BUG-M8.** Not a new finding. Covered in fix patch.

---

### references/review_protocols.md

#### Line 410: `[SHIP IT / FIX FIRST / NEEDS INVESTIGATION]` — Wrong recommendation enum values
- **Line 410:** **BUG** The integration test protocol template's Reporting section specifies:
  ```
  ### Recommendation
  [SHIP IT / FIX FIRST / NEEDS INVESTIGATION]
  ```
  This contradicts:
  - `quality_gate.sh:427`: validates `SHIP|"FIX BEFORE MERGE"|BLOCK` and FAILs for other values
  - `SKILL.md:1273`: "Valid `recommendation` values: `"SHIP"`, `"FIX BEFORE MERGE"`, `"BLOCK"`"
  
  An agent reading `references/review_protocols.md` and following its template would write `"recommendation": "FIX FIRST"` or `"recommendation": "NEEDS INVESTIGATION"` into `integration-results.json`. The gate would then FAIL: `"recommendation 'FIX FIRST' is non-canonical (must be SHIP/FIX BEFORE MERGE/BLOCK)"`.
  
  - **Expected:** Template should specify: `SHIP / FIX BEFORE MERGE / BLOCK`
  - **Actual:** Template specifies: `SHIP IT / FIX FIRST / NEEDS INVESTIGATION`
  - **Impact:** Agents following this reference file systematically produce gate-failing integration-results.json artifacts.
  - **REGRESSION TEST:** `test_BUG_G3_recommendation_enum_inconsistency` in `quality/test_regression.sh`

---

### quality_gate.sh (structural scan of recheck validation gap)

#### Lines 389–673 (entire check_repo function): No recheck-results.json validation
- **INCOMPLETE** The check_repo function validates every documented conditional artifact: tdd-results.json (lines 221-305), TDD log files (307-387), integration-results.json (389-436), use cases (438-474), test file extension (476-533), terminal gate (535-541), mechanical (543-560), patches (562-588), writeups (590-623), version stamps (625-672). The SKILL.md artifact contract table documents recheck-results.json and recheck-summary.md as required when recheck runs, but no validation section exists for either file.
  - **Impact:** A malformed recheck run produces no gate failures. The artifact contract table's promise is not enforced.
  - **Note:** This is an absence bug — the code that should be there isn't. No specific line to cite.
  - **REGRESSION TEST:** `test_BUG_G4_no_recheck_validation` in `quality/test_regression.sh`

---

## Combined Summary (Pass 1)

| Finding | File:Line | Severity | Status |
|---------|-----------|----------|--------|
| ls-glob in code_reviews detection | quality_gate.sh:143 | MEDIUM | BUG (CAND-G2 confirmed) |
| ls-glob in test file extension detection | quality_gate.sh:479 | MEDIUM | BUG (CAND-G1 confirmed) |
| Wrong recommendation enum in template | references/review_protocols.md:410 | MEDIUM | BUG (CAND-G3 confirmed) |
| No recheck-results.json validation | quality_gate.sh (absence) | MEDIUM | INCOMPLETE (CAND-G4 confirmed) |

**Overall assessment:** FIX FIRST — 4 new bugs confirmed, all MEDIUM severity. The two ls-glob bugs (lines 143, 479) extend the nullglob vulnerability class already confirmed in BUG-M8. The recommendation enum inconsistency causes systematic gate failures for agents following references/review_protocols.md. The recheck validation gap means the gate does not enforce the full artifact contract.
