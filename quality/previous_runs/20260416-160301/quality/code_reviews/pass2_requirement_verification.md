# Pass 2: Requirement Verification — quality-playbook

<!-- Quality Playbook v1.4.1 — Phase 3 Code Review — 2026-04-16 -->

For each requirement (REQ-001 through REQ-014), this pass gives a SATISFIED / VIOLATED / PARTIALLY SATISFIED / NOT ASSESSABLE verdict with specific code citation.

---

#### REQ-001: JSON Key Presence Validation Must Not Match String Values

**Status**: VIOLATED

**Evidence**: `quality_gate.sh:77` — `grep -q "\"${key}\"" "$file" 2>/dev/null`

**Analysis**: The requirement says `json_has_key()` must verify the key appears as an actual JSON key (preceding `:`), not merely as a substring of a string value. The current implementation uses `grep -q "\"${key}\""` which matches the key name anywhere in the file — including inside string values. A JSON file like `{"msg": "the 'id' field is required"}` returns true from `json_has_key "id"` even though `id` is not a key.

**Severity**: HIGH. The gate passes malformed artifact files as conformant. A tdd-results.json that contains the word "id" in any string value will pass the `id` key check even if no bug entry has an `id` field. This is a false PASS from the gate.

---

#### REQ-002: Repo Path Array Reconstruction Must Preserve Spaces

**Status**: VIOLATED

**Evidence**: `quality_gate.sh:697` — `REPO_DIRS=(${resolved[@]+"${resolved[@]}"})`

**Analysis**: The requirement specifies that a repo path containing spaces must appear as a single element in `REPO_DIRS` after reconstruction. The outer array assignment is unquoted: `REPO_DIRS=(${resolved[@]+...})`. Without outer quotes around the expansion, word-splitting occurs and a path like `/Users/joe/My Projects/repo` becomes two elements: `/Users/joe/My` and `Projects/repo`. The additional unquoted expansion at line 686 (`for name in ${REPO_DIRS[@]+"${REPO_DIRS[@]}"}`) also word-splits.

**Severity**: HIGH. On macOS (where `~/Documents/My Projects/` is a common path pattern), the gate silently checks a wrong path. All artifact checks run against a non-existent directory fragment, producing false-FAIL or false-PASS results.

---

#### REQ-003: Phase 2 Entry Gate Must Enforce All Substantive Phase 1 Checks

**Status**: VIOLATED

**Evidence**: `SKILL.md:897-904` — Phase 2 entry gate defines 6 checks. `SKILL.md:847-862` — Phase 1 completion gate defines 12 checks.

**Analysis**: Phase 2 entry gate checks only:
1. `## Open Exploration Findings` section title present
2. `## Quality Risks` section title present
3. `## Pattern Applicability Matrix` section title present
4. At least 3 `## Pattern Deep Dive — ` sections present
5. `## Candidate Bugs for Phase 2` section title present
6. `## Gate Self-Check` section present

Missing from Phase 2 gate: check 2 (PROGRESS.md marks Phase 1 complete), check 3 (Derived Requirements with file paths), check 5 (open-exploration depth — 3 findings trace 2+ functions), check 8 (3-4 FULL patterns), check 10 (depth — 2 deep dives trace 2+ functions), check 12 (ensemble balance). An EXPLORATION.md with only section title stubs satisfying the 6 title checks passes the Phase 2 gate even if the content is substantively empty.

**Severity**: MEDIUM. Shallow exploration produces abstract requirements that miss function-level bugs in Phase 3.

---

#### REQ-004: Gate Must Enforce Regression Test File When Bugs Exist

**Status**: VIOLATED

**Evidence**: `quality_gate.sh:562-588` — patches section. No check for `quality/test_regression.*` file existence.

**Analysis**: The requirement says the gate must FAIL when `bug_count > 0` and no `quality/test_regression.*` file exists. The gate at lines 562-588 checks for regression test PATCHES (`quality/patches/BUG-NNN-regression-test.patch`) but does not check for the regression test SOURCE FILE (`quality/test_regression.*`). The artifact contract at SKILL.md lines 88-119 explicitly designates both as "Required: If bugs found." The patch for the test and the test file itself are distinct artifacts — the patch is a diff that can be applied to create the test file, but the test file must also exist directly for CI execution.

Searching quality_gate.sh for `test_regression`: line 479-480 uses `ls ${q}/test_regression.* 2>/dev/null | head -1` to retrieve the extension for validation purposes, but this check is under the `[Test File Extension]` section and only validates the extension if the file happens to exist — it does not FAIL if the file is absent.

**Severity**: MEDIUM. The artifact contract is not mechanically enforced. A run that produces patches but no test file passes the gate.

---

#### REQ-005: Phase 0b Must Activate When previous_runs/ Exists But Is Empty

**Status**: VIOLATED

**Evidence**: `SKILL.md:271` — "This phase runs only if `previous_runs/` exists and contains prior quality artifacts." `SKILL.md:295-297` — "This step runs only if `previous_runs/` does not exist."

**Analysis**: When `previous_runs/` exists but is empty: Phase 0a skips (no artifacts to load), Phase 0b also skips (the directory exists, so the "does not exist" condition is false). The requirement says Phase 0b must run when `previous_runs/` exists but contains no conformant quality artifacts. This edge case produces a silent no-op: no seeds are loaded, no warning is emitted, and Phase 1 starts fresh as if no prior runs exist at all.

**Severity**: MEDIUM. Bug rediscovery failure: a developer who created `previous_runs/` expecting sibling-run seeds to be consulted will get no seeding and will not be warned.

---

#### REQ-006: All Version References in SKILL.md Must Match Frontmatter

**Status**: PARTIALLY SATISFIED

**Evidence**: `SKILL.md:6` — `version: 1.4.1`. Grep confirms identical version at lines 6, 39, 129, 156, 915, 922, 1056, 1966. All 8 occurrences match.

**Analysis**: The current state is consistent — all version references match the frontmatter value `1.4.1`. However, the requirement also says "a mechanical check must detect any discrepancy." No such check exists in `quality_gate.sh`. The gate checks version stamps in generated ARTIFACTS against SKILL.md frontmatter, but it does not check the internal consistency of version strings within SKILL.md itself. After a version bump, it is possible for a maintainer to update the frontmatter but miss one of the 8 inline occurrences (particularly the JSON example at line 129 or the patch example at line 1056), and no tool would catch it.

**Severity**: LOW (for current state). The specification gap is real but latent — it only becomes a HIGH issue when the next version bump happens.

---

#### REQ-007: json_str_val Must Distinguish Absent Keys from Non-String Values

**Status**: VIOLATED

**Evidence**: `quality_gate.sh:81-85` — `grep -o "\"${key}\"[[:space:]]*:[[:space:]]*\"[^\"]*\""` requires a quoted value. `quality_gate.sh:236` — caller reports `"schema_version is '${sv:-missing}'"`.

**Analysis**: For `"schema_version": 1.1` (a number), the regex fails to match and returns empty string. The caller at line 236 uses `${sv:-missing}` which substitutes `missing` for empty string, reporting `"schema_version is 'missing', expected '1.1'"` when the field exists as a number. A developer debugging this failure would look for a missing field when the actual problem is a wrong type. The requirement says the function must return a value distinguishable from empty string for non-string values.

**Severity**: LOW. Misleading error messages. No false positives or false negatives in gate verdicts — the gate still correctly reports FAIL. The impact is debugging difficulty, not gate correctness.

---

#### REQ-008: Mandatory First Action Must Be Scoped to Interactive Mode

**Status**: VIOLATED

**Evidence**: `SKILL.md:37-39` — `**MANDATORY FIRST ACTION:**` with no conditional qualifier. `SKILL.md:376` — autonomous fallback covers only Step 0's user question, 339 lines later, with no back-reference to the Mandatory First Action.

**Analysis**: The requirement says the Mandatory First Action section must contain either a conditional qualifier for interactive-only scope OR an explicit reference to the autonomous fallback rule. The current instruction says "After reading and understanding the plan above, print the following message to the user" unconditionally. An autonomous agent executing this instruction literally would print the version banner and explanation during benchmark runs, polluting automated output. The autonomous fallback at line 376 only mentions skipping "Step 0's question" and does not address the Mandatory First Action print.

**Severity**: MEDIUM. Benchmark runners parsing gate output would receive spurious model output before the gate begins.

---

#### REQ-009: Generated Artifact Version Stamps Must Match SKILL.md Frontmatter

**Status**: PARTIALLY SATISFIED

**Evidence**: `quality_gate.sh:625-649` — version stamp consistency checks. Lines 635-638 check PROGRESS.md, lines 641-645 check tdd-results.json skill_version.

**Analysis**: The gate does check version stamps for PROGRESS.md and tdd-results.json. However, it does not check the version stamp comment in Markdown artifact files (QUALITY.md, REQUIREMENTS.md, CONTRACTS.md, etc.). The generated artifacts currently carry `<!-- Quality Playbook v1.4.1 — generated 2026-04-16 -->` comments but there is no gate check that reads these comments and compares them to the frontmatter version. A stale REQUIREMENTS.md from a prior version would pass the gate. The JSON sidecar check is enforced; the Markdown artifact check is not.

**Severity**: LOW-MEDIUM. Gate partially enforces this requirement. A version-mismatch scenario where SKILL.md is updated and only the JSON sidecars are re-generated would not be caught for the Markdown files.

---

#### REQ-010: Phase 1 Exploration Must Produce Substantive Findings

**Status**: PARTIALLY SATISFIED

**Evidence**: `SKILL.md:847-862` — 12-check completion gate. `SKILL.md:897-904` — Phase 2 entry gate enforces only section title presence.

**Analysis**: The Phase 1 completion gate itself (lines 847-862) defines rigorous checks: at least 120 substantive lines, 8+ findings with file:line references, 5+ domain risks, 3-4 FULL patterns, etc. These checks are well-specified. However, the Phase 1 gate is enforced only at the end of Phase 1 — in multi-session mode where Phase 1 runs in one session and Phase 2 in a different session, Phase 2's entry gate (lines 897-904) only checks for 6 section titles. It cannot verify that the sections have substantive content (120+ lines, 8+ findings, etc.). This is the same issue as REQ-003 — Phase 2 entry gate is an incomplete backstop for Phase 1 completion gate.

**Severity**: MEDIUM (in multi-session mode). In single-session mode, Phase 1 completion gate runs immediately before Phase 2 and catches shallow exploration.

---

#### REQ-011: Requirements Pipeline Must Produce Traceable, Testable Requirements

**Status**: SATISFIED

**Evidence**: `quality/REQUIREMENTS.md` lines 1-434 — all 14 requirements contain all 8 mandatory fields: Summary, User story with "so that" clause, Implementation note, Conditions of satisfaction, Alternative paths, References, Doc source with authority tier, and Specificity. The file begins with a project overview and use cases (UC-01 through UC-05).

**Analysis**: Reviewed all 14 requirements against the mandatory fields checklist. All requirements have "so that" clauses in user stories. All use REQ-NNN format. All use cases use UC-NN format. REQUIREMENTS.md begins with prose overview, not raw metadata. Architectural-guidance requirements: 0 (all 14 are specific, testable). COVERAGE_MATRIX.md at `quality/COVERAGE_MATRIX.md` exists (confirmed in PROGRESS.md).

---

#### REQ-012: quality_gate.sh Must Handle Empty VERSION Gracefully

**Status**: VIOLATED

**Evidence**: `quality_gate.sh:60-67` — version detection loop. `quality_gate.sh:678` — `for dir in "${SCRIPT_DIR}/"*-"${VERSION}"/;`. `quality_gate.sh:700-702` — empty array triggers usage message.

**Analysis**: When VERSION remains empty, the glob at line 678 becomes `"${SCRIPT_DIR}/"*-""/` which is `*-/` — this matches nothing. The empty-array guard at line 700 triggers and prints "Usage: ..." followed by `exit 1`. The requirement says the gate must "emit a clear error message naming the failure (VERSION empty, SKILL.md not found)." The current output says "Usage: $0 [--version V] [--all | repo1 repo2 ... | .]" — which does not name the root cause (VERSION empty). A benchmark runner seeing this output would not know whether the gate failed due to VERSION being empty or due to an invalid command-line invocation.

**Severity**: MEDIUM. Benchmark automation difficulty — the error message is ambiguous about root cause.

---

#### REQ-013: Mechanical Verification Must Not Be Created for Non-Dispatch Contracts

**Status**: SATISFIED

**Evidence**: `SKILL.md:~line 578` — "Do not create an empty mechanical/ directory." PROGRESS.md — "Mechanical verification: NOT APPLICABLE — quality_gate.sh uses bash if/elif chains (not dispatch tables). No `quality/mechanical/` directory created."

**Analysis**: No `quality/mechanical/` directory exists. PROGRESS.md documents the decision at two locations: "Mechanical verification: NOT APPLICABLE" in the Phase 2 checkpoint section and in the exploration summary section. SKILL.md's instruction at line 578 is correctly followed. The gate at lines 543-560 checks for `quality/mechanical/` only if it exists — it does not require it when absent, consistent with the "not applicable" decision.

---

#### REQ-014: Gate Script Functional Test Detection Must Be Consistent

**Status**: VIOLATED

**Evidence**: `quality_gate.sh:124` — `ls ${q}/test_functional.* ... &>/dev/null 2>&1` (unquoted glob, ls-based). `quality_gate.sh:449-454` — `find ... -print -quit` (consistent, portable).

**Analysis**: Functional test detection uses `ls` with an unquoted glob, which is shell-option-dependent. Language detection uses `find` with `-print -quit`, which is consistent across shells. The two detection methods in the same script have different failure modes. Under `nullglob`, the unquoted glob in the functional test check would expand to empty, and `ls` with no arguments lists the current directory — a false PASS. The requirement says detection must return the same result across bash with nullglob enabled and disabled.

**Severity**: LOW-MEDIUM. Inconsistency is a latent bug — most environments don't set nullglob, so the ls-based check works in practice. But CI environments with stricter shell options (e.g., `set -f` for no globbing, or nullglob for cleaner scripting) would see different behavior.

---

## Summary

| Requirement | Status | Severity |
|-------------|--------|----------|
| REQ-001: JSON key presence validation | VIOLATED | HIGH |
| REQ-002: Repo path array reconstruction | VIOLATED | HIGH |
| REQ-003: Phase 2 entry gate completeness | VIOLATED | MEDIUM |
| REQ-004: Gate enforces regression test file | VIOLATED | MEDIUM |
| REQ-005: Phase 0b empty directory | VIOLATED | MEDIUM |
| REQ-006: Version references in SKILL.md | PARTIALLY SATISFIED | LOW |
| REQ-007: json_str_val non-string values | VIOLATED | LOW |
| REQ-008: Mandatory First Action scope | VIOLATED | MEDIUM |
| REQ-009: Generated artifact version stamps | PARTIALLY SATISFIED | LOW-MEDIUM |
| REQ-010: Phase 1 exploration substantive | PARTIALLY SATISFIED | MEDIUM |
| REQ-011: Requirements pipeline traceable | SATISFIED | — |
| REQ-012: Empty VERSION handling | VIOLATED | MEDIUM |
| REQ-013: No empty mechanical/ directory | SATISFIED | — |
| REQ-014: Functional test detection consistency | VIOLATED | LOW-MEDIUM |

**VIOLATED:** 9 requirements
**PARTIALLY SATISFIED:** 3 requirements
**SATISFIED:** 2 requirements
