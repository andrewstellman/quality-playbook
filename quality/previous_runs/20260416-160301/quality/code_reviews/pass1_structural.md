# Pass 1: Structural Review — quality-playbook

<!-- Quality Playbook v1.4.1 — Phase 3 Code Review — 2026-04-16 -->

## Files Reviewed

- `quality_gate.sh` (723 lines, bash)
- `SKILL.md` (2239 lines, Markdown specification)

---

## quality_gate.sh

**Line 77:** BUG — `json_has_key` matches key name anywhere in file, not only as a JSON key.

```bash
grep -q "\"${key}\"" "$file" 2>/dev/null
```

The pattern `"key"` matches inside string values (e.g., `{"msg": "the 'id' field is required"}`), returning exit 0 (true) when the key is not actually present as a JSON key. The correct fix is to require the pattern to be followed by a colon: `grep -q "\"${key}\"[[:space:]]*:"`. This is the root cause of BUG-H1. Callers at lines 230, 253, 260 all depend on this function returning true only for actual JSON keys.

**Line 88-91:** BUG — `json_key_count` comment says "matches key: value pairs only" but this is only partially true.

```bash
json_key_count() {
    local file="$1" key="$2"
    grep -c "\"${key}\"[[:space:]]*:" "$file" 2>/dev/null || echo 0
}
```

The pattern `"key":` does require a colon (better than `json_has_key`), but it still matches when the key name appears inside a string value followed by a colon character in the text. Example: `{"description": "the 'id': required field"}` would match `json_key_count "id"` if the string value contains `"id":`. This inflates per-bug field counts in the TDD sidecar validation at lines 239–248. The comment at line 87 ("matches key: value pairs only") is misleading — it should say "matches `\"key\":` pattern, which can appear inside string values."

**Line 81-85:** BUG — `json_str_val` silently returns empty for non-string values.

```bash
json_str_val() {
    local file="$1" key="$2"
    grep -o "\"${key}\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" "$file" 2>/dev/null \
        | head -1 | sed 's/.*: *"\([^"]*\)"/\1/'
}
```

When the key exists but has a non-string value (e.g., `"schema_version": 1.1`), the regex requires a quoted value and fails to match. The function returns empty string, which is indistinguishable from "key absent." The caller at line 236 reports `"schema_version is 'missing'"` when the field exists as a number. This produces misleading error messages.

**Line 124:** BUG — Unquoted glob in `ls` command for functional test detection.

```bash
if ls ${q}/test_functional.* ${q}/FunctionalSpec.* ${q}/FunctionalTest.* ${q}/functional.test.* &>/dev/null 2>&1; then
```

The glob is unquoted, making behavior shell-option-dependent (nullglob, failglob). Under some shells, an unmatched glob expands to the literal string, causing `ls` to fail with "no such file" rather than returning non-zero cleanly. The `&>/dev/null 2>&1` at the end is also redundant (`&>` already redirects both stdout and stderr). Compare with language detection at lines 449–454 which correctly uses `find ... -print -quit` — consistent, portable, correct.

**Line 143:** BUG — Unquoted glob for code_reviews directory check.

```bash
if [ -d "${q}/code_reviews" ] && [ -n "$(ls ${q}/code_reviews/*.md 2>/dev/null)" ]; then
```

Unquoted glob — same shell-option sensitivity as line 124. Under `nullglob`, the glob expands to empty, `ls` runs with no argument and lists the current directory. Under default bash settings this is probably fine, but it is fragile.

**Line 152-153:** BUG — Unquoted globs for spec_audits counting.

```bash
triage_count=$(ls ${q}/spec_audits/*triage* 2>/dev/null | wc -l | tr -d ' ')
auditor_count=$(ls ${q}/spec_audits/*auditor* 2>/dev/null | wc -l | tr -d ' ')
```

Same unquoted glob pattern. If `q` contains spaces, the expansion breaks before `wc -l` sees the list. These lines are in the same functional path that processes `REPO_DIRS`, which is subject to the BUG-H2 space-corruption issue.

**Line 186:** QUESTION — `wrong_headings` count logic looks inverted.

```bash
wrong_headings=$(grep -E '^## BUG-[0-9]+' "${q}/BUGS.md" 2>/dev/null | grep -cvE '^### BUG-' || true)
```

The outer `grep -E '^## BUG-'` matches lines starting with `##`. The inner `grep -cvE '^### BUG-'` counts lines that do NOT match `### BUG-`. Since the outer grep already filtered to `^## BUG-`, no line in the pipe will ever start with `^### BUG-` (that requires three hashes, and the outer grep matched exactly two). So `grep -cvE '^### BUG-'` always returns the total count of lines from the outer grep — `wrong_headings` equals `grep -cE '^## BUG-' BUGS.md`. The inner grep pipe is a no-op. This is confusing and likely an unintentional complexity — the logic still produces correct results (## BUG- lines count as wrong), but the pipe is misleading.

**Line 278-283:** QUESTION — String comparison for date.

```bash
if [[ "$tdd_date" > "$today" ]]; then
    fail "tdd-results.json date '${tdd_date}' is in the future"
```

Lexicographic string comparison of ISO 8601 dates works correctly when dates follow the `YYYY-MM-DD` format (which is already validated by the prior regex check). This is intentional and correct for POSIX-sorted ISO 8601. No bug.

**Line 331:** BUG — Unquoted glob for green-phase log check.

```bash
if ls ${q}/patches/${bid}-fix*.patch &>/dev/null; then
```

Same pattern as lines 124/143/152/153 — unquoted glob. If `q` contains spaces, the path breaks.

**Line 567-568:** BUG — Unquoted globs for patch counting.

```bash
reg_patch_count=$(ls ${q}/patches/BUG-*-regression*.patch 2>/dev/null | wc -l | tr -d ' ')
fix_patch_count=$(ls ${q}/patches/BUG-*-fix*.patch 2>/dev/null | wc -l | tr -d ' ')
```

Same unquoted glob pattern with path-space fragility.

**Line 595:** BUG — Unquoted glob for writeup counting.

```bash
writeup_count=$(ls ${q}/writeups/BUG-*.md 2>/dev/null | wc -l | tr -d ' ')
```

Same unquoted glob pattern.

**Line 686:** BUG — Unquoted array expansion in repo resolution loop.

```bash
for name in ${REPO_DIRS[@]+"${REPO_DIRS[@]}"}; do
```

The expansion `${REPO_DIRS[@]+"${REPO_DIRS[@]}"}` is unquoted at the `for` statement level. A repo path like `/Users/joe/My Projects/my-repo` expands to four words: `/Users/joe/My`, `Projects/my-repo`, etc. This means the loop body processes word fragments rather than full paths.

**Line 697:** BUG (BUG-H2) — Unquoted array reconstruction.

```bash
REPO_DIRS=(${resolved[@]+"${resolved[@]}"})
```

The array assignment outer expansion is unquoted. `${resolved[@]+...}` expands to the array contents, but without outer quotes, word-splitting occurs before the array is initialized. A path containing spaces becomes multiple elements. The fix is `REPO_DIRS=("${resolved[@]+"${resolved[@]}"}") `.

**Line 678:** QUESTION — Empty VERSION glob in `--all` mode.

```bash
for dir in "${SCRIPT_DIR}/"*-"${VERSION}"/; do
```

When `VERSION` is empty (SKILL.md not found), this becomes `*-/` which matches nothing. The array stays empty, the guard at line 700 triggers and prints a usage message, but the exit code is 1 (from `exit 1` at line 702 after the usage line). In benchmark runners that parse exit codes, this looks like a gate failure — which is technically correct but the error message ("Usage: ...") is misleading for an empty VERSION case. REQ-012 covers this.

**Line 44:** INCOMPLETE — Arg parsing loop processes `$@` safely.

```bash
for arg in ${@+"$@"}; do
```

The `${@+"$@"}` idiom correctly handles the empty-args case with `set -u` active. This is correct bash idiom. No bug.

**Line 32:** QUESTION — `set -uo pipefail` without `-e`.

Without `set -e`, individual command failures within compound expressions (non-pipeline) are silently ignored. For example, if `grep` in `json_str_val` returns non-zero due to file permissions, the function returns empty string silently. This is the documented behavior at EXPLORATION.md Finding 5. The flag is missing intentionally (the script uses `|| echo 0` and `|| true` fallbacks throughout) but it means every command failure must be explicitly handled — and some are not (see `json_has_key` which has no fallback for permission errors).

---

## SKILL.md

**Line 37-39 vs Line 376:** BUG (BUG-M8, related to REQ-008) — "MANDATORY FIRST ACTION" has no autonomous-mode qualifier and no cross-reference to the autonomous fallback at line 376.

The heading says `MANDATORY FIRST ACTION` with no qualification. An autonomous agent reading this instruction in sequence encounters it before reaching line 376 (339 lines later). There is no pointer, cross-reference, or conditional qualifier. The autonomous fallback at line 376 only covers Step 0's user question — it does not explicitly say "also skip the Mandatory First Action print." An autonomous agent following the instruction literally would print the version banner during a benchmark run.

**Lines 295-297 vs 271-272:** BUG (BUG-M5) — Phase 0b activation condition is "previous_runs/ does not exist" but Phase 0a only activates when `previous_runs/` exists AND contains artifacts. When `previous_runs/` exists but is empty, both phases skip with no warning.

Phase 0: "This phase runs only if `previous_runs/` exists and contains prior quality artifacts" (line 271).
Phase 0b: "This step runs only if `previous_runs/` does not exist" (line 295-297).

The gap: empty `previous_runs/` → Phase 0a skips (no artifacts) → Phase 0b skips (directory exists) → no seeding. CONTRACTS.md item 14 correctly documents this as an `[ERROR]` contract, confirming it is known. The fix: Phase 0b should activate when `previous_runs/` does not exist OR when it contains no conformant artifacts.

**SKILL.md line 897 (Phase 2 entry gate) vs lines 847-862 (Phase 1 completion gate):** BUG (BUG-M3) — Phase 2 entry gate enforces 6 of 12 Phase 1 gate checks. Phase 1 checks NOT enforced by Phase 2 gate:

- Check 2: PROGRESS.md marks Phase 1 complete
- Check 3: Derived Requirements with file paths
- Check 5: Open-exploration depth (3 findings trace 2+ functions)
- Check 8: 3-4 patterns marked FULL
- Check 10: Depth — 2 deep dives trace 2+ functions
- Check 12: Ensemble balance

The Phase 2 entry gate at lines 899-904 only checks for 6 section title presences. An EXPLORATION.md that has the correct section titles but fails checks 2, 3, 5, 8, 10, and 12 passes the Phase 2 entry gate, enabling Phase 2 to proceed with shallow exploration findings.

**SKILL.md lines 6, 39, 129, 156, 915, 922, 1056, 1966:** QUESTION (BUG-L7) — Version string `1.4.1` appears in 8 locations in SKILL.md without a cross-reference consistency check.

All 8 occurrences match the frontmatter (verified by grep). However, there is no mechanical check that enforces this — a version bump would require manually finding and updating all 8 occurrences. REQ-006 documents this as a maintenance risk. No immediate bug in current state — all instances currently consistent.

**SKILL.md (no line cited — structural):** INCOMPLETE — The artifact contract table at lines 88-119 lists `quality/test_regression.*` as "Required: If bugs found" but there is no corresponding gate check in `quality_gate.sh` for the existence of the regression test FILE (only for regression test PATCHES). REQ-004 covers this. The gate at lines 562-588 checks for patch files but not for `quality/test_regression.*`.

---

## Summary of Pass 1 Structural Findings

| File | Line | Type | Description |
|------|------|------|-------------|
| quality_gate.sh | 77 | BUG | `json_has_key` matches string values, not only JSON keys |
| quality_gate.sh | 88-91 | BUG | `json_key_count` comment misleading; can still match inside strings |
| quality_gate.sh | 81-85 | BUG | `json_str_val` returns empty for non-string values, misleading errors |
| quality_gate.sh | 124 | BUG | Unquoted glob in `ls` for functional test detection (shell-option-sensitive) |
| quality_gate.sh | 143 | BUG | Unquoted glob in `ls` for code_reviews check |
| quality_gate.sh | 152-153 | BUG | Unquoted globs for spec_audits counting |
| quality_gate.sh | 186 | QUESTION | `wrong_headings` inner grep pipe is a no-op (produces correct result by coincidence) |
| quality_gate.sh | 278-283 | QUESTION | String date comparison — intentional and correct |
| quality_gate.sh | 331 | BUG | Unquoted glob for green-phase log check |
| quality_gate.sh | 567-568 | BUG | Unquoted globs for patch counting |
| quality_gate.sh | 595 | BUG | Unquoted glob for writeup counting |
| quality_gate.sh | 686 | BUG | Unquoted array expansion in repo resolution loop |
| quality_gate.sh | 697 | BUG | Unquoted array reconstruction corrupts paths with spaces (BUG-H2) |
| quality_gate.sh | 678 | QUESTION | Empty VERSION silently produces no-op glob in --all mode (REQ-012) |
| SKILL.md | 37-39/376 | BUG | Mandatory First Action lacks autonomous-mode qualifier/cross-ref (REQ-008) |
| SKILL.md | 271/295-297 | BUG | Phase 0b skips when previous_runs/ exists but empty (BUG-M5) |
| SKILL.md | 847-862/897-904 | BUG | Phase 2 entry gate enforces only 6 of 12 Phase 1 checks (BUG-M3) |
| SKILL.md | multiple | QUESTION | Version 1.4.1 in 8 locations, all consistent but no mechanical check (BUG-L7) |
| SKILL.md / quality_gate.sh | 88-119 / 562-588 | INCOMPLETE | test_regression.* file existence not checked by gate (BUG-M4) |
