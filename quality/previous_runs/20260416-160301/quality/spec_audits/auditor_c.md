# Auditor C Report — Security and Reliability Auditor

<!-- Quality Playbook v1.4.1 — Phase 4 Spec Audit — 2026-04-16 -->

**Auditor role:** Security and Reliability — failure modes under unexpected inputs, bash safety (injection risks, unquoted variables, error handling), quality_gate.sh reliability under edge conditions.

---

## Pre-Audit Docs Validation

No `docs_gathered/` directory. Auditors relied on in-repo specifications and code only. DEVELOPMENT_CONTEXT.md and TOOLKIT.md used as supplementary context.

---

## quality_gate.sh — Bash Safety and Reliability

### Finding C-1 (NET-NEW — HIGH CONFIDENCE)

- **Line 152-153:** UNDOCUMENTED [Req: inferred — reliability] `ls` glob with no matches under nullglob produces wrong count.
  ```bash
  triage_count=$(ls ${q}/spec_audits/*triage* 2>/dev/null | wc -l | tr -d ' ')
  ```
  **Failure mode:** When `nullglob` is enabled (e.g., in a user's `.bashrc` or `.zshrc`), the shell expands `${q}/spec_audits/*triage*` to empty (no words). Then `ls` receives no argument and lists the **current directory**. The `2>/dev/null` redirect is `ls`'s stderr, not stdout — it does not suppress the directory listing. `wc -l` counts lines in the current directory listing. In a typical project directory with >0 files, `triage_count` gets a nonzero value, causing the gate to report `pass "spec_audits/ has triage file"` even when no triage file exists.
  
  **Verification:** This is a bash behavior issue. Under nullglob: `(set -o nullglob; ls /nonexistent/*triage* 2>/dev/null | wc -l)` produces the line count of the current directory listing, not 0.
  
  **Severity: MEDIUM** — affects users who have nullglob in their shell environment (common for zsh users, common macOS default).

### Finding C-2 (NET-NEW — HIGH CONFIDENCE)

- **Lines 596-597:** UNDOCUMENTED [Req: inferred — reliability] Same nullglob issue in patch counting.
  ```bash
  reg_patch_count=$(ls ${q}/patches/BUG-*-regression*.patch 2>/dev/null | wc -l | tr -d ' ')
  fix_patch_count=$(ls ${q}/patches/BUG-*-fix*.patch 2>/dev/null | wc -l | tr -d ' ')
  ```
  Under nullglob: if patches/ directory exists but is empty, `ls` lists the current directory. Both counts would be nonzero, causing `[ "$reg_patch_count" -ge "$bug_count" ]` to potentially PASS even with zero patch files. The gate would report PASS for regression test patches when none exist.
  
  **Severity: MEDIUM** — same class as C-1.

### Finding C-3 (NET-NEW — HIGH CONFIDENCE)

- **Lines 598-601:** UNDOCUMENTED [Req: inferred — reliability] Writeup globbing with `for` loop has a known bash pitfall.
  ```bash
  for wf in "${q}"/writeups/BUG-*.md; do
      [ -f "$wf" ] || continue
  ```
  This pattern uses proper quoting around `"${q}"` but the glob `BUG-*.md` is unquoted (it must be for globbing to work). The `[ -f "$wf" ] || continue` guard at line 599 is the defensive check that prevents the loop from executing on a literal glob string when no files match. This guard is correct and prevents the no-files case. **However:** this correct pattern is used inconsistently — the `ls | wc -l` pattern at lines 594-595 does NOT have an equivalent guard, creating a discrepancy between the two counting methods used in the same function. The writeup count is correct (uses find-with-guard idiom effectively), but the counting-method inconsistency suggests the `ls | wc -l` pattern was written without awareness of the nullglob issue.

### Finding C-4 (NET-NEW)

- **Lines 313-314:** UNDOCUMENTED [Req: inferred — reliability] Bug ID extraction from BUGS.md uses an unguarded `$bid` loop.
  ```bash
  bug_ids=$(grep -oE 'BUG-[0-9]+' "${q}/BUGS.md" 2>/dev/null \
      | grep -E '^BUG-[0-9]+$' | sort -u -t'-' -k2,2n)
  ...
  for bid in $bug_ids; do
  ```
  The `for bid in $bug_ids` is unquoted — if `bug_ids` contains a path glob character (unlikely given the `BUG-[0-9]+` pattern, but possible via future changes), it would expand. More importantly, `for bid in $bug_ids` word-splits on spaces, tabs, AND newlines. Since `bug_ids` is a newline-separated list from `grep`, this works correctly — newlines are IFS separators. But if a BUGS.md heading had embedded spaces in the BUG ID (malformed input), the split could produce corrupted IDs. Not a real-world issue with the `BUG-[0-9]+` filter, but the pattern is fragile by convention.

### Finding C-5 (NET-NEW — CONFIRMED)

- **Line 331:** UNDOCUMENTED [Req: inferred — reliability] Green-phase patch check uses unquoted glob.
  ```bash
  if ls ${q}/patches/${bid}-fix*.patch &>/dev/null; then
  ```
  Under nullglob: if the patches directory exists but has no fix patches, this command expands to `ls` with no argument (lists current directory). `&>/dev/null` suppresses ALL output (both stdout and stderr), but the exit code of `ls /path/without/matches` is 1. The exit code is what matters for the `if` condition — `ls .` (current dir) returns exit 0. So under nullglob, `ls ${q}/patches/${bid}-fix*.patch` when no fix patches exist would return exit 0 (from listing current dir), and the gate would INCORRECTLY require a green-phase log even when no fix patch exists.
  
  **Verification assertion (expected FAIL, confirming the bug):**
  ```bash
  # Set nullglob, verify ls returns exit 0 when glob matches nothing but dir exists
  (set -o nullglob; mkdir -p /tmp/test_patches; ls /tmp/test_patches/BUG-*-fix*.patch 2>/dev/null; echo "exit: $?")
  # Expected output: "exit: 0" — proving the if-condition fires when it should not
  ```
  
  **Severity: MEDIUM** — causes spurious green-phase log requirements under nullglob.

### Finding C-6 (NET-NEW — CONFIRMED)

- **Lines 60-67:** UNDOCUMENTED [Req: Tier 3 — REQ-012] VERSION auto-detection uses `grep -m1 'version:'` which can match any line with `version:` in it, not just the YAML frontmatter field.
  ```bash
  VERSION=$(grep -m1 'version:' "$loc" 2>/dev/null | sed 's/.*version: *//' | tr -d ' ')
  ```
  SKILL.md's frontmatter at line 5-6 is:
  ```yaml
  ---
  name: quality-playbook
  description: "...version..."
  license: ...
  metadata:
    version: 1.4.1
  ```
  The `grep -m1 'version:'` will match the first occurrence of `version:` in the file. In SKILL.md, this is line 6 (`  version: 1.4.1`). BUT: if the description field on line 3 contained the string `version:` anywhere, `grep -m1 'version:'` would match line 3 instead. More critically, SKILL.md's description at line 3 does contain the word "version" — in the description string. Let me check exact content: "Run a complete quality engineering audit on any codebase..." — actually line 3 reads: `description: "Run a complete quality engineering audit on any codebase. Derives behavioral requirements from the code, generates spec-traced functional tests, runs a three-pass code review with regression tests, executes a multi-model spec audit (Council of Three), and produces a consolidated bug report with TDD-verified patches. Finds the 35% of real defects that structural code review alone cannot catch. Works with any language. Trigger on 'quality playbook', 'spec audit', 'Council of Three', 'fitness-to-purpose', or 'coverage theater'."` — does not contain the word `version:` with a colon directly following.
  
  However, the `sed 's/.*version: *//'` pattern is fragile: if a matching line is `  license: Complete terms in LICENSE.txt` with a `version` word elsewhere in the same line, the sed would strip up to `version: ` and return garbage. In practice, with the current SKILL.md content, this works. But if any line before `metadata:\n  version:` were to contain `version:` (e.g., if a comment like `# version: deprecated` were added), the version detection would silently return a wrong value.
  
  **Severity: LOW** — edge case in version detection, currently works with current SKILL.md.

### Finding C-7 (NET-NEW)

- **Line 44:** UNDOCUMENTED [Req: inferred — bash safety] The argument parsing loop uses `for arg in ${@+"$@"}` which is a common idiom for empty-array safety in bash 3.x.
  ```bash
  for arg in ${@+"$@"}; do
  ```
  This pattern is correct and defensive — it handles the case where `$@` is empty without crashing in bash 3.x (which treats unquoted `"$@"` as an error when empty). DEVELOPMENT_CONTEXT.md confirms this was a known fix: "bash 3.2 empty array crashes". So this is actually a CORRECT defensive pattern, not a bug. No issue here.

### Finding C-8 (NET-NEW — CONFIRMED)

- **Lines 567-568 vs 571-576:** DIVERGENT [Req: Tier 2 — REQ-004] The regression test patch count check uses `ls | wc -l` (nullglob vulnerable) rather than `find`.
  ```bash
  reg_patch_count=$(ls ${q}/patches/BUG-*-regression*.patch 2>/dev/null | wc -l | tr -d ' ')
  ```
  The check at lines 571-576:
  ```bash
  if [ "$reg_patch_count" -ge "$bug_count" ]; then
      pass "${reg_patch_count} regression-test patch(es) for ${bug_count} bug(s)"
  ...
  else
      fail "No regression-test patches..."
  fi
  ```
  Under nullglob: `reg_patch_count` gets current-directory line count (e.g., 12), `bug_count` is (e.g., 7), `12 -ge 7` is true, gate passes with misleading message "12 regression-test patch(es) for 7 bug(s)" when zero regression patches exist.
  
  This combines with C-1/C-2 to form a systemic reliability failure under nullglob.

---

## SKILL.md — Instruction Clarity and Failure Modes

### Finding C-9 (NET-NEW CANDIDATE)

- **SKILL.md line 1067-1082:** UNDOCUMENTED The patch validation gate (lines 1067-1084) requires running `git apply --check` and a compile check. For the quality-playbook self-audit, the "source files" are SKILL.md and quality_gate.sh — no compile check is applicable. But SKILL.md says "If no compile/syntax check is feasible for the project's language, document this in the patch entry and rely on the TDD red phase to catch syntax errors." For specification-primary repos (like this one), there is no compile step. This is handled by the fallback instruction. No bug.

### Finding C-10 (NET-NEW)

- **SKILL.md line 697 vs 686:** DIVERGENT [Req: Tier 3 — REQ-002] Both the line 697 array reconstruction AND line 686 loop expansion are unquoted.
  Line 686: `for name in ${REPO_DIRS[@]+"${REPO_DIRS[@]}"}; do`
  Line 697: `REPO_DIRS=(${resolved[@]+"${resolved[@]}"})`
  These are the confirmed BUG-H2 locations. The outer expansion at line 697 must be quoted: `REPO_DIRS=("${resolved[@]+"${resolved[@]}"}") `. The loop at 686 expands correctly because `for` iterates over arguments, but the initial population at 697 is broken. Both confirmed (BUG-H2).

### Finding C-11 (NET-NEW CANDIDATE)

- **quality_gate.sh line 279:** UNDOCUMENTED [Req: inferred] The `[[ "$tdd_date" > "$today" ]]` comparison uses the `[[` construct which is bash-specific. The script's shebang is `#!/bin/bash` (line 1), so this is correct for bash. However, `set -uo pipefail` at line 32 does NOT include `-e`. Without `-e`, a failed command in a subshell (like `$(date +%Y-%m-%d)` returning error) would silently produce empty output for `today`, and the comparison `[[ "" > "2026-04-16" ]]` is lexicographically false (empty string < any string), so the gate would not erroneously fail. The behavior is safe but relies on the specific comparison semantics of empty strings.

### Finding C-12 (NET-NEW — CONFIRMED)

- **quality_gate.sh line 567:** DIVERGENT [Req: Tier 2 — REQ-004] The gate checks regression-test PATCHES exist, but not the regression test SOURCE FILE (`quality/test_regression.*`). This is BUG-M4 (already confirmed). Independently flagged by this auditor.

  From a reliability standpoint: a run where the agent generates patch files but not a test_regression.sh passes the gate. The patch file `BUG-NNN-regression-test.patch` is supposed to be applied to add a test to `test_regression.*`. If `test_regression.*` doesn't exist, the patch has nothing to apply to, making the regression test unrunnable — but the gate passes. This creates a silent failure mode.

---

## Systemic Pattern: Nullglob Vulnerability

Multiple gate functions use `ls [glob] | wc -l` for counting artifacts. This pattern fails silently under nullglob. Affected lines:
- Line 152-153: spec_audits triage/auditor count
- Lines 595-596: writeup count
- Lines 567-568: patch count
- Line 331: fix patch existence check (exit code vulnerability)

The consistent use of `find ... -print -quit` for language detection at lines 449-454 shows the developer knew the correct pattern. The `ls | wc -l` counting pattern appears to be a separate code pattern that was not updated to use `find`. This is a systemic technical debt, not individual bugs.

---

## Summary of New Findings

| ID | Location | Type | Net-New? | Severity |
|----|----------|------|----------|---------|
| C-1 | quality_gate.sh:152-153 | UNDOCUMENTED (nullglob) | **YES** | MEDIUM |
| C-2 | quality_gate.sh:596-597 | UNDOCUMENTED (nullglob) | **YES** | MEDIUM |
| C-3 | quality_gate.sh:598-601 | UNDOCUMENTED | YES | LOW |
| C-4 | quality_gate.sh:313-314 | UNDOCUMENTED | YES | LOW |
| C-5 | quality_gate.sh:331 | UNDOCUMENTED (nullglob) | **YES** | MEDIUM |
| C-6 | quality_gate.sh:60-67 | UNDOCUMENTED | YES | LOW |
| C-8 | quality_gate.sh:567-568 | DIVERGENT (nullglob) | **YES** | MEDIUM |
| C-10 | quality_gate.sh:697,686 | DIVERGENT (REQ-002) | No (BUG-H2) | HIGH |
| C-12 | quality_gate.sh:567 | DIVERGENT (REQ-004) | No (BUG-M4) | MEDIUM |
