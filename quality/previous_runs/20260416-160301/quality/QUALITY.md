# Quality Constitution: quality-playbook

<!-- Quality Playbook v1.4.1 — generated 2026-04-16 -->

## Purpose

Quality for the quality-playbook is built in, not inspected in. The primary product — `SKILL.md` — is an AI instruction document. Every AI session that follows it must produce conformant, grounded artifacts. Quality is therefore embedded directly into the specification's internal consistency rules, the `quality_gate.sh` mechanical validator, and this quality playbook itself, so that any agent session inherits the same bar without needing to rediscover it.

Fitness for purpose here means: a quality playbook run on any codebase must produce a self-consistent set of artifacts — requirements traceable to exploration, tests traceable to requirements, and a gate score that reflects actual artifact conformance rather than superficial presence. The failure mode this guards against is **coverage theater**: an artifact set that looks complete but whose requirements are abstract, whose tests check language builtins rather than project behavior, and whose gate passes because the checks are too shallow to catch malformed JSON or misquoted arrays.

The upfront cost of this quality system is small compared to debugging a self-referential failure that silently passes all checks. A malfunctioning quality gate that reports PASS when bugs exist is worse than no gate at all — it creates false confidence. Building quality in at the specification level means maintainers catch version-stamp drift, JSON validation false positives, and gate-check gaps before they appear in published benchmark results.

## Coverage Targets

| Subsystem | Target | Why |
|-----------|--------|-----|
| `quality_gate.sh` JSON validation | 95% | BUG-H1: `json_key_count` matches keys in string values — inflating field counts without detecting missing fields in individual bug entries. Every JSON helper must be tested for false-positive and false-negative conditions. |
| `quality_gate.sh` repo resolution | 90% | BUG-H2: unquoted array expansion at line 697 corrupts paths with spaces. All three fallback paths (primary, Fallback 1, Fallback 2) must be tested with and without spaces. |
| SKILL.md phase gate consistency | 85% | BUG-M3: Phase 2 entry gate enforces only 6 of 12 Phase 1 gate checks. Shallow EXPLORATION.md files pass Phase 2 undetected. Gate consistency must be tested structurally. |
| SKILL.md artifact contract | 85% | BUG-M4: `test_regression.*` not checked by gate despite artifact contract table saying "Required: If bugs found." Contract/gate drift must be verified. |
| SKILL.md version consistency | 80% | BUG-L7: version `1.4.1` hardcoded in 5+ locations. A version bump that misses any location generates stale stamps in generated artifacts. |
| Phase 0 seed injection | 80% | BUG-M5: Phase 0b silently skips when `previous_runs/` exists but is empty — sibling seeds are lost. |

The rationale column is essential. All targets reference specific exploration findings with file:line evidence.

## Coverage Theater Prevention

Coverage theater for this project includes:

- **Asserting a section exists without checking its content depth.** The Phase 1 gate is satisfied by checking section titles. A test that only verifies `## Open Exploration Findings` appears in the file without verifying it has at least 8 concrete findings with file:line citations is theater.
- **Checking JSON field presence with grep instead of parsing.** `json_has_key "id"` returns true if the string `"id"` appears anywhere in the file — including in string values, comments, or nested objects. A test that accepts this as proof of a well-formed JSON is theater.
- **Asserting gate PASS on a minimal artifact set.** A test that creates stub QUALITY.md and REQUIREMENTS.md files and expects the gate to pass is testing that files exist, not that they are conformant.
- **Testing that a bash function returns exit code 0 without checking side effects.** The `fail()`, `pass()`, `warn()` functions in `quality_gate.sh` work through global counters, not return values. A test that captures the return code misses the actual contract.
- **Mock-based phase simulation.** A functional test that mocks SKILL.md sections or quality_gate.sh functions and then asserts the mock returns correctly is testing the mock, not the system.
- **Testing only the happy path for the quality gate.** The gate is designed to catch malformed artifacts — only testing conformant artifacts confirms the gate passes when it should, but not that it fails when it should.

## Fitness-to-Purpose Scenarios

### Scenario 1: JSON Key Validation False Positive

**Requirement tag:** [Req: inferred — quality_gate.sh:88-91]

**What happened:** `json_key_count()` at `quality_gate.sh:88-91` uses `grep -c "\"${key}\"[[:space:]]*:"` to count occurrences of a field across the entire `tdd-results.json` file. This regex matches the pattern `"key":` anywhere — including inside string values. A JSON file where a bug's `"red_phase"` description contains the text `"the 'id' field is deprecated"` would cause `json_key_count "id"` to return a count inflated by the string value match. With `N` bugs in the file, `fcount >= bug_count` could pass even when one bug entry is missing the field, if another bug's string value incidentally matches.

**The requirement:** `json_key_count` must not match key names that appear inside string values. For a file with `bug_count = 3`, the function must return exactly 3 only when each of 3 bug objects has the named field as an actual JSON key. REQ-001.

**How to verify:** Create a `tdd-results.json` with 2 bug entries where one entry's `"red_phase"` string value contains the text `"id"`. Assert that `json_key_count id tdd-results.json` returns 2 (not 3).

---

### Scenario 2: Space-in-Path Array Corruption

**Requirement tag:** [Req: inferred — quality_gate.sh:697]

**What happened:** At `quality_gate.sh:697`, the resolved array is reconstructed as `REPO_DIRS=(${resolved[@]+"${resolved[@]}"})`. The outer expansion is unquoted. A path like `"/Users/dev/My Projects/my-repo"` becomes two elements: `"/Users/dev/My"` and `"Projects/my-repo"`. The `check_repo` call at line 711 receives the mangled path, causing `basename` to compute the wrong repo name and all subsequent checks to run against a nonexistent directory — silently producing a false PASS or FAIL. On macOS, home directories under `~/Documents/` routinely contain spaces.

**The requirement:** All repo paths must survive the array reconstruction at line 697 intact. A path with spaces must appear as a single array element in `REPO_DIRS`. REQ-002.

**How to verify:** Call `quality_gate.sh` with a path argument containing a space (e.g., `/tmp/my repo/`). Assert that the gate inspects the concatenated path, not the word-split fragments.

---

### Scenario 3: Shallow EXPLORATION.md Bypasses Phase 2 Gate

**Requirement tag:** [Req: inferred — SKILL.md Phase 1/2 gate descriptions]

**What happened:** The Phase 1 completion gate at SKILL.md ~line 847 defines 12 checks. The Phase 2 entry gate at ~line 897 defines only 6. Checks 8 (3-4 FULL patterns), 10 (depth — 2 deep dives trace 2+ functions), and 12 (ensemble balance — 2 from open exploration, 1 from patterns) are not enforced by the Phase 2 gate. An agent that generates a formally correct EXPLORATION.md — correct section titles, correct candidate bug count, correct Gate Self-Check section — but with shallow one-paragraph deep dives and all candidates derived from patterns (not from open exploration or risk analysis) would proceed to Phase 2 undetected. This was observed in v1.3.43 benchmarking with two repos.

**The requirement:** The Phase 2 entry gate must either enforce all 12 Phase 1 gate checks, or explicitly document which checks are not backstopped and explain the accepted risk. REQ-003.

**How to verify:** Produce an EXPLORATION.md that passes the Phase 2 entry gate's 6 checks but fails Phase 1 check 8 (marks only 1 pattern as FULL). Assert that the spec documentation acknowledges this gap.

---

### Scenario 4: Regression Test File Not Enforced by Gate

**Requirement tag:** [Req: formal — SKILL.md lines 88-119 artifact contract table]

**What happened:** The SKILL.md artifact contract table at lines 88-119 lists `quality/test_regression.*` as "Required: If bugs found." The `quality_gate.sh` script checks for regression test PATCHES in `quality/patches/BUG-NNN-regression-test.patch` but does NOT check for the existence of `quality/test_regression.*`. An agent that generates patches without a consolidated regression test file would pass the gate despite violating the documented artifact contract. The table says required; the gate does not enforce it.

**The requirement:** `quality_gate.sh` must check for `quality/test_regression.*` when `bug_count > 0`, consistent with the artifact contract table. REQ-004.

**How to verify:** Run `quality_gate.sh` on a quality directory that has bugs in BUGS.md and patches in `quality/patches/` but no `quality/test_regression.*` file. Assert the gate reports FAIL for the missing regression test artifact.

---

### Scenario 5: Phase 0b Seed Discovery Silent Skip

**Requirement tag:** [Req: inferred — SKILL.md Phase 0/0b ~lines 269-307]

**What happened:** Phase 0a activates only when `previous_runs/` exists and contains prior quality artifacts. Phase 0b activates only when `previous_runs/` does NOT exist. When `previous_runs/` exists but is empty (no subdirectories with conformant artifacts), Phase 0a skips (nothing to load) and Phase 0b also skips (the directory exists). Sibling versioned directories that could provide seeds — e.g., `httpx-1.3.21/` — are never consulted. The user receives no seed injection and no warning. This was the failure class identified in v1.3.23 httpx benchmarking: the model explored different paths and missed the `Headers.__setitem__` non-ASCII encoding bug.

**The requirement:** Phase 0b's activation condition must be "previous_runs/ absent OR contains no conformant quality artifacts," not merely "previous_runs/ absent." REQ-005.

**How to verify:** Create a `previous_runs/` directory with no subdirectories alongside a sibling versioned directory containing a BUGS.md. Assert that Phase 0b runs seed discovery on the sibling.

---

### Scenario 6: Version Stamp Drift on Multi-Location Update

**Requirement tag:** [Req: formal — SKILL.md frontmatter + ai_context/DEVELOPMENT_CONTEXT.md]

**What happened:** The version `1.4.1` appears in at least 5 locations in SKILL.md: frontmatter (line 6), the mandatory print block (line 39), the JSON example for tdd-results.json (line 129), the version stamp instruction (~line 916), and the integration-results.json example. `DEVELOPMENT_CONTEXT.md` states: "The version field in SKILL.md metadata must be bumped for every change. All generated artifacts stamp this version, and mismatches cause quality_gate.sh failures." If a maintainer bumps the frontmatter version but forgets to update the JSON example at line 129, every generated artifact inherits the wrong version from the example and fails the gate — even though the SKILL.md is otherwise correct.

**The requirement:** All version references in SKILL.md must be identical to the frontmatter version. A mechanical check must verify this. REQ-006.

**How to verify:** Search SKILL.md for all occurrences of the version string. Assert they are all identical to the frontmatter `metadata.version` value.

---

### Scenario 7: `json_str_val` Misleading Error for Non-String Types

**Requirement tag:** [Req: inferred — quality_gate.sh:81-85]

**What happened:** `json_str_val()` at `quality_gate.sh:81-85` uses a regex that requires a quoted string value (`\"[^\"]*\"`). If the JSON has `"schema_version": 1.1` (a number, not a string), the regex does not match and the function returns empty string. The caller at line 235 receives empty string, and the check `[ "$sv" = "1.1" ]` fails with `fail "schema_version is 'missing'"` — reporting the wrong root cause. "Missing" and "wrong type" are different debugging signals.

**The requirement:** `json_str_val` must distinguish a truly absent key from a key with a non-string value, so that error messages accurately report the problem. REQ-007.

**How to verify:** Create a JSON file with `"schema_version": 1.1` (number) and call `json_str_val`. Assert the function returns a distinct signal for "non-string value" vs. "key absent."

---

### Scenario 8: Mandatory First Action Conflicts with Autonomous Mode

**Requirement tag:** [Req: inferred — SKILL.md ~line 37 vs ~line 376]

**What happened:** `SKILL.md` at ~line 37 states: "MANDATORY FIRST ACTION: After reading and understanding the plan above, print the following message to the user." The word "mandatory" appears before the autonomous fallback rule at ~line 376 which says "skip Step 0's question" in autonomous mode. An agent running non-interactively might interpret the "MANDATORY" instruction as truly mandatory (producing unwanted output and potentially breaking piped invocations), or it might apply the autonomous fallback to the wrong instruction set because the two rules are spatially separated by ~339 lines with no cross-reference.

**The requirement:** The "Mandatory First Action" instruction must be explicitly scoped to interactive mode, with a cross-reference to the autonomous fallback rule. REQ-008.

**How to verify:** Read SKILL.md and verify that the "Mandatory First Action" section contains either a conditional qualifier ("In interactive mode:") or an explicit reference to the autonomous fallback rule.

---

## AI Session Quality Discipline

1. Read `QUALITY.md`, `REQUIREMENTS.md`, and `AGENTS.md` before starting work.
2. Run `bash quality_gate.sh .` before marking any task complete.
3. Add functional tests for new behavior (not just happy path — include negative cases for every defensive pattern).
4. Update `QUALITY.md` if new failure modes are discovered during exploration. Never remove existing scenarios.
5. Output a Quality Compliance Checklist before ending a session.
6. All bash scripts must be tested with paths containing spaces.
7. All JSON validation logic must be tested for both false positives (key in string value) and false negatives (missing key).

## The Human Gate

The following require human judgment and cannot be automated:

- Whether an exploration found the *right* bugs for this codebase vs. superficially plausible but low-impact bugs
- Whether fitness-to-purpose scenarios accurately capture the real risk profile of a target codebase
- Whether QUALITY.md scenarios reflect domain expertise or only code-pattern analysis
- Security review of any patch that modifies JSON parsing or file path handling
- Backward compatibility decisions when changing artifact schemas
- Judgment calls on whether a SKILL.md instruction conflict produces an actual agent error vs. a recoverable ambiguity
