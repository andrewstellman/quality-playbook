# Requirements: quality-playbook

<!-- Quality Playbook v1.4.1 — generated 2026-04-16 -->

## Project Overview

The **quality-playbook** is an AI skill that finds bugs that structural code review alone cannot catch — the 35% of real defects that require understanding what the code is *supposed* to do. It is authored by Andrew Stellman and published at https://github.com/andrewstellman/quality-playbook.

The skill is delivered as a single Markdown instruction document (`SKILL.md`, ~2239 lines) that AI coding agents (Claude Code, GitHub Copilot, and similar) read and follow to run a complete quality audit on any target codebase. Supporting infrastructure includes a bash post-run validator (`quality_gate.sh`, ~723 lines) and a library of reference documents (`references/*.md`) that the skill delegates to for phase-specific detail.

The playbook's core insight is that AI models exploring code without a quality specification produce generic findings that miss real bugs. By grounding exploration in domain knowledge, deriving testable requirements from what the code is supposed to do, and then verifying the code against those requirements in three independent passes, the playbook finds bugs invisible to any individual reviewer or model. In controlled experiments across 10+ benchmark repositories (chi, cobra, httpx, pydantic, javalin, gson, express, axum, serde, zod, virtio), the playbook has consistently found bugs that structural code review alone missed.

**Actors:**
- **Developers** using Claude Code or GitHub Copilot who invoke the playbook on their own codebases
- **Benchmark runners** (automated scripts running non-interactively with `--single-pass` or equivalent)
- **Skill maintainers** who update SKILL.md and must keep internal consistency
- **AI agents** following the instruction document — the agents are the primary executors of the skill

**Highest-risk areas:**
- `quality_gate.sh` JSON validation helpers — regex-based grep without a proper JSON parser creates false positives
- `quality_gate.sh` repo path handling — unquoted array expansion corrupts paths with spaces
- SKILL.md phase gate consistency — Phase 2 entry gate enforces only 6 of 12 Phase 1 checks
- SKILL.md artifact contract table vs. gate enforcement — documented requirements can drift from enforced ones
- Version stamp management — version number hardcoded in 5+ locations with no single source of truth

---

## Use Cases

### UC-01: Developer Runs Quality Audit on a New Codebase

**Actor:** Developer (human) using Claude Code or GitHub Copilot
**Trigger:** "Run the quality playbook on this project."
**Expected outcome:** The AI agent runs all 7 phases (or stops after Phase 1 in default mode), writes quality artifacts to `quality/`, and provides the developer with a bug report, functional tests, and protocols for ongoing review. The developer understands what defects were found, which are most severe, and how to continue with code review or spec audit.
**Conditions of satisfaction linked to:** REQ-001, REQ-002, REQ-003, REQ-005, REQ-006, REQ-008, REQ-009, REQ-010, REQ-011

### UC-02: Automated Benchmark Executes Full Multi-Repo Quality Audit

**Actor:** Benchmark runner script (non-interactive, autonomous mode)
**Trigger:** Non-interactive invocation with `--single-pass` or equivalent flag
**Expected outcome:** All 6 phases complete without user interaction. Generated artifacts conform to SKILL.md v1.4.1 contract. `quality_gate.sh` reports PASS with zero failures. Bug discovery rate meets baseline from prior benchmark runs.
**Conditions of satisfaction linked to:** REQ-006, REQ-007, REQ-008, REQ-009

### UC-03: Developer Verifies Conformance of Generated Artifacts

**Actor:** Developer running `bash quality_gate.sh .` after a playbook run
**Trigger:** Post-run validation
**Expected outcome:** Gate accurately reports PASS only when all artifacts are conformant — correct structure, valid JSON, matching version stamps, existing TDD logs for every confirmed bug. Gate accurately reports FAIL when artifacts are missing or malformed.
**Conditions of satisfaction linked to:** REQ-001, REQ-002, REQ-004, REQ-005, REQ-006, REQ-009

### UC-04: Maintainer Updates Skill Version

**Actor:** Skill maintainer bumping the version in SKILL.md frontmatter
**Trigger:** A fix or improvement warrants a version bump
**Expected outcome:** All version references in SKILL.md, DEVELOPMENT_CONTEXT.md, and JSON examples are updated to match. `quality_gate.sh` does not report version mismatches in subsequent runs. No stale version strings remain.
**Conditions of satisfaction linked to:** REQ-006

### UC-05: Developer Runs Iteration to Find Additional Bugs

**Actor:** Developer who has completed a baseline run
**Trigger:** "Run the next iteration of the quality playbook using the gap strategy."
**Expected outcome:** Gap strategy explores uncovered subsystems, new findings are merged with prior findings, phases 2–6 run on merged results. Net-new confirmed bugs go through TDD red-green cycle. Gate passes on the merged artifact set.
**Conditions of satisfaction linked to:** REQ-003, REQ-007, REQ-009, REQ-011

---

## Requirements

### REQ-001: JSON Key Presence Validation Must Not Match String Values

**Summary:** `json_has_key()` must verify the key appears as an actual JSON key (preceding `:`), not merely as a substring of a string value anywhere in the file.

**User story:** As a developer verifying generated artifact conformance, I expect `quality_gate.sh` to accurately detect missing required fields in `tdd-results.json`, so that a malformed artifact file does not silently pass the gate.

**Implementation note:** `json_has_key()` at `quality_gate.sh:75-78` uses `grep -q "\"${key}\""` — this matches the key name anywhere in the file, including inside string values. The correct pattern would require the key to be followed by a colon, anchored to a position that cannot be inside a string.

**Conditions of satisfaction:**
- A JSON file where the key name appears only inside a string value (e.g., `{"msg": "the 'id' field"}`) must return false from `json_has_key "id"`
- A JSON file where the key name appears as an actual key (e.g., `{"id": "BUG-001"}`) must return true
- A malformed `tdd-results.json` missing the `"id"` field from a bug entry must cause the gate to report FAIL, not PASS

**Alternative paths:**
- File does not exist → must return false (not true)
- File is unreadable → must return false (not true due to permissions error being indistinguishable from key absence)
- Key appears only in nested object string values → must return false

**References:** `quality_gate.sh:75-78`, EXPLORATION.md Finding 2, BUG-H1

**Doc source:** [Tier 3] quality_gate.sh:75-78 — `grep -q "\"${key}\""` — must match only JSON key positions

**Specificity:** specific

---

### REQ-002: Repo Path Array Reconstruction Must Preserve Spaces

**Summary:** The `resolved` array reconstruction at `quality_gate.sh:697` must use proper quoting so that repository paths containing spaces survive as single array elements.

**User story:** As a developer on macOS running `quality_gate.sh` on a project in a path containing spaces (e.g., `~/Documents/My Projects/my-repo`), I expect the gate to inspect the correct path, so that all artifact checks run against the actual project directory rather than a word-split fragment.

**Implementation note:** Line 697: `REPO_DIRS=(${resolved[@]+"${resolved[@]}"})`. The outer expansion is unquoted. The fix is `REPO_DIRS=("${resolved[@]+"${resolved[@]}"}") `. Also check line 686: `for name in ${REPO_DIRS[@]+"${REPO_DIRS[@]}"}` — same unquoted expansion.

**Conditions of satisfaction:**
- A repo path containing one or more spaces must appear as a single element in `REPO_DIRS` after reconstruction at line 697
- `basename` called on the resolved path must return the correct project name, not a word-split fragment
- `check_repo` must receive the full path as a single argument

**Alternative paths:**
- Path with no spaces → must work as before
- Path with multiple consecutive spaces → must be preserved
- Path with trailing space → must be handled without stripping

**References:** `quality_gate.sh:697`, `quality_gate.sh:686`, EXPLORATION.md Finding 1, BUG-H2

**Doc source:** [Tier 3] quality_gate.sh:697 — outer expansion `${resolved[@]...}` is unquoted — causes word-splitting

**Specificity:** specific

---

### REQ-003: Phase 2 Entry Gate Must Enforce All Substantive Phase 1 Checks

**Summary:** The Phase 2 entry gate must either enforce all 12 Phase 1 completion gate checks, or explicitly document which checks are not backstopped and explain the accepted risk.

**User story:** As a developer running the quality playbook, I expect Phase 2 to reject an EXPLORATION.md that is structurally complete but substantively shallow (e.g., only 1 pattern marked FULL, no cross-function depth traces, all candidates from pattern deep dives only), so that Phase 2 artifacts are grounded in thorough exploration.

**Implementation note:** Phase 1 gate at SKILL.md ~line 847 defines 12 checks. Phase 2 entry gate at ~line 897 defines 6 checks. Missing checks: 2 (PROGRESS.md marks Phase 1 complete), 3 (Derived Requirements with file paths), 5 (open-exploration depth — 3 findings trace 2+ functions), 8 (3-4 FULL patterns), 10 (depth — 2 deep dives trace 2+ functions), 12 (ensemble balance). This was observed as a failure mode in v1.3.43 benchmarking.

**Conditions of satisfaction:**
- An EXPLORATION.md with only 1 pattern marked FULL in the applicability matrix must not pass Phase 2 entry (fails check 8)
- An EXPLORATION.md where all Candidate Bugs originate from pattern deep dives (none from open exploration or quality risks) must not pass Phase 2 entry (fails check 12)
- OR: the Phase 1 gate section must explicitly document checks 2, 3, 5, 8, 10, 12 as "not backstopped by Phase 2 gate" with the accepted risk

**Alternative paths:**
- Single-session run where Phase 1 gate is run by the same agent → Phase 2 gate still serves as a backstop if agent skips the Phase 1 gate
- Multi-session run where Phase 1 and Phase 2 run in separate contexts → Phase 2 gate is the only enforcement mechanism

**References:** SKILL.md Phase 1 gate (~line 847), Phase 2 entry gate (~line 897), EXPLORATION.md Finding 4, BUG-M3

**Doc source:** [Tier 3] SKILL.md ~line 897 — Phase 2 entry gate checks only 6 of 12 Phase 1 requirements

**Specificity:** specific

---

### REQ-004: Gate Must Enforce Regression Test File When Bugs Exist

**Summary:** `quality_gate.sh` must check for the existence of `quality/test_regression.*` when `bug_count > 0`, consistent with the artifact contract table's "Required: If bugs found" designation.

**User story:** As a developer verifying run conformance, I expect the gate to report FAIL when bugs are confirmed (present in BUGS.md) but no regression test file exists in `quality/`, so that the artifact contract is enforced mechanically.

**Implementation note:** The gate at lines 562-588 checks for regression test PATCHES (`quality/patches/BUG-NNN-regression-test.patch`) but not for the test FILE (`quality/test_regression.*`). The artifact contract table at SKILL.md lines 88-119 documents both as required. The functional test detection pattern at lines 123-128 shows the existing approach for glob-based file detection.

**Conditions of satisfaction:**
- Gate must FAIL when `bug_count > 0` and no `quality/test_regression.*` file exists
- Gate must PASS when `bug_count > 0` and `quality/test_regression.*` exists (with correct content)
- Gate must PASS when `bug_count = 0` and no `quality/test_regression.*` file exists

**Alternative paths:**
- Bug present but not confirmed (no ### BUG-NNN heading in BUGS.md) → gate must not require test_regression.*
- Multiple bug entries → one test_regression.* file covers all

**References:** `quality_gate.sh` (lines 562-588), SKILL.md artifact contract table (lines 88-119), EXPLORATION.md Finding 3, BUG-M4

**Doc source:** [Tier 2] SKILL.md lines 88-119 — artifact contract table: `test_regression.*` Required: "If bugs found"

**Specificity:** specific

---

### REQ-005: Phase 0b Must Activate When previous_runs/ Exists But Is Empty

**Summary:** Phase 0b seed discovery must run when `previous_runs/` exists but contains no conformant quality artifacts (empty directory or subdirectories without valid BUGS.md), so that sibling versioned directories can provide seeds.

**User story:** As a developer who has created a `previous_runs/` directory but whose prior runs produced no conformant artifacts, I expect Phase 0b to still consult sibling versioned directories for seeds, so that the bug rediscovery failure class from v1.3.23 is prevented.

**Implementation note:** Current Phase 0 logic: Phase 0a activates when `previous_runs/` exists AND contains artifacts; Phase 0b activates when `previous_runs/` does NOT exist. When `previous_runs/` exists but is empty: Phase 0a skips (nothing to load), Phase 0b also skips (directory exists). Fix: Phase 0b activation condition should be "previous_runs/ does not exist OR contains no conformant quality artifacts."

**Conditions of satisfaction:**
- When `previous_runs/` exists and is empty: Phase 0b must run and consult sibling versioned directories
- When `previous_runs/` exists with conformant artifacts: Phase 0b must NOT run (Phase 0a handles seeding)
- When `previous_runs/` does not exist: Phase 0b runs (current behavior preserved)
- A warning must be emitted when Phase 0b finds sibling seeds that were previously unavailable

**Alternative paths:**
- `previous_runs/` exists with subdirectories that have corrupted (non-conformant) BUGS.md → treated as empty, Phase 0b activates

**References:** SKILL.md Phase 0/0b (~lines 269-307), EXPLORATION.md Pattern Deep Dive (Fallback Path Parity), BUG-M5

**Doc source:** [Tier 2] SKILL.md ~line 296 — "This step runs only if previous_runs/ does not exist" — misses empty-dir case

**Specificity:** specific

---

### REQ-006: All Version References in SKILL.md Must Match Frontmatter

**Summary:** Every hardcoded version string in SKILL.md must be identical to `metadata.version` in the frontmatter. A mechanical check must detect any discrepancy.

**User story:** As a skill maintainer bumping the version after a fix, I expect all version references to be updated consistently, so that generated artifacts carry the correct version stamp and `quality_gate.sh` does not report false version mismatches.

**Implementation note:** Version `1.4.1` appears at minimum in: frontmatter (line 6), mandatory print block (line 39), JSON example for tdd-results.json (line 129), version stamp instruction (~line 916), and integration-results.json example. The `quality_gate.sh` extracts the version from SKILL.md frontmatter and validates against all generated artifact stamps. If the JSON example at line 129 is stale, agents following it generate wrong stamps.

**Conditions of satisfaction:**
- All occurrences of the version string in SKILL.md must equal `metadata.version`
- A grep for any version string that differs from frontmatter must return empty
- DEVELOPMENT_CONTEXT.md's version reference must also match

**Alternative paths:**
- SKILL.md frontmatter updated but JSON example not updated → gate should detect mismatch in generated artifacts
- Version bumped in DEVELOPMENT_CONTEXT.md but not in SKILL.md → must be flagged

**References:** SKILL.md frontmatter (line 6), SKILL.md (line 39, 129, ~916), DEVELOPMENT_CONTEXT.md, EXPLORATION.md Risk 2, BUG-L7

**Doc source:** [Tier 2] ai_context/DEVELOPMENT_CONTEXT.md — "The version field must be bumped for every change. All generated artifacts stamp this version, and mismatches cause quality_gate.sh failures."

**Specificity:** specific

---

### REQ-007: json_str_val Must Distinguish Absent Keys from Non-String Values

**Summary:** `json_str_val()` must return a distinguishable signal when the key exists but has a non-string value (number, boolean, null, object, or array), so that callers can generate accurate error messages.

**User story:** As a developer debugging a gate failure on `tdd-results.json`, I expect the gate to report "schema_version is '1.1' (not a string)" rather than "schema_version is 'missing'" when the field exists but is not quoted, so that I know whether to add the field or change its type.

**Implementation note:** `json_str_val()` at `quality_gate.sh:81-85` regex requires `\"[^\"]*\"` (a quoted value). For `"schema_version": 1.1` (number), the regex fails to match and returns empty string. The caller at line 235 checks `[ "$sv" = "1.1" ]` and reports the field as missing. Fix options: (1) a second grep that checks for the key with any value, then branches on whether the value is quoted; (2) return a sentinel value like `__NOT_STRING__` for non-string values.

**Conditions of satisfaction:**
- For `"schema_version": "1.1"` → return `1.1`
- For `"schema_version": 1.1` (number) → return a value distinguishable from empty string indicating "key exists, non-string value"
- For a JSON file with no `schema_version` key → return empty string indicating "key absent"
- Error messages at call sites must accurately report the root cause

**Alternative paths:**
- Boolean value (`true`/`false`) → same as number case
- Null value → same as number case
- Nested object value → same as number case

**References:** `quality_gate.sh:81-85`, EXPLORATION.md Pattern Deep Dive (Dispatcher Return-Value Correctness), BUG-L6

**Doc source:** [Tier 3] quality_gate.sh:81-85 — regex `\"[^\"]*\"` requires quoted value — non-string values silently return empty

**Specificity:** specific

---

### REQ-008: Mandatory First Action Must Be Scoped to Interactive Mode

**Summary:** The "Mandatory First Action" instruction in SKILL.md must include an explicit qualifier limiting it to interactive mode, with a cross-reference to the autonomous fallback rule.

**User story:** As a benchmark runner invoking the quality playbook non-interactively, I expect the agent to skip the "print to user" step without ambiguity, so that automated runs do not produce unwanted output or break piped invocations.

**Implementation note:** "MANDATORY FIRST ACTION" at SKILL.md ~line 37 requires printing to the user before any exploration. The autonomous fallback at ~line 376 says to skip Step 0's question but does not explicitly address the Mandatory First Action. The two rules are ~339 lines apart with no cross-reference. Adding a parenthetical "(In interactive mode only)" or "(Skip in autonomous mode — see autonomous fallback below)" to the Mandatory First Action heading would resolve the ambiguity.

**Conditions of satisfaction:**
- The Mandatory First Action section must contain either a conditional qualifier for interactive-only scope OR an explicit reference to the autonomous fallback rule
- An autonomous-mode invocation must not produce user-facing print output from the Mandatory First Action
- An interactive-mode invocation must produce the print output with version and URL

**Alternative paths:**
- Claude Code interactive mode → print output is expected
- GitHub Copilot interactive mode → print output is expected
- Benchmark runner (`run_playbook.sh`) → skip print output
- Direct autonomous invocation without benchmark runner → must infer autonomous mode and skip

**References:** SKILL.md ~line 37, ~line 376, EXPLORATION.md Finding 6, BUG-L8 (low severity)

**Doc source:** [Tier 2] SKILL.md ~line 37 — "MANDATORY FIRST ACTION" precedes autonomous fallback rule at ~line 376 by 339 lines with no cross-reference

**Specificity:** specific

---

### REQ-009: Generated Artifact Version Stamps Must Match SKILL.md Frontmatter

**Summary:** Every generated artifact (QUALITY.md, REQUIREMENTS.md, CONTRACTS.md, test_functional.sh, RUN_CODE_REVIEW.md, RUN_INTEGRATION_TESTS.md, RUN_SPEC_AUDIT.md, RUN_TDD_TESTS.md, AGENTS.md, and all sidecar JSON files) must include a version stamp matching `metadata.version` from SKILL.md frontmatter.

**User story:** As a developer running `quality_gate.sh` on a playbook run's output, I expect the gate to verify that all artifacts carry the same version stamp, so that I can confirm the artifacts were generated by the version of the skill I intended to use.

**Implementation note:** `quality_gate.sh` extracts VERSION from SKILL.md frontmatter using sed, then checks version stamps in each generated artifact. The JSON sidecar examples in SKILL.md (lines 122-166) include `"skill_version"` fields — agents that copy these examples verbatim will generate wrong stamps if the examples are stale (REQ-006 interaction).

**Conditions of satisfaction:**
- All generated Markdown artifacts must contain the version stamp in their header comment or metadata
- `tdd-results.json` and `integration-results.json` must have `"skill_version"` matching SKILL.md frontmatter
- Gate must FAIL when any artifact has a version stamp differing from SKILL.md frontmatter

**Alternative paths:**
- SKILL.md not found by gate → gate must emit clear error, not silently proceed with empty VERSION
- Multi-phase run with SKILL.md updated between phases → artifacts from different phases carry different versions; gate must detect

**References:** SKILL.md ~line 916, quality_gate.sh version detection (lines 60-67), EXPLORATION.md Risk 2

**Doc source:** [Tier 2] SKILL.md ~line 916 — "The version in the stamp must match the metadata.version in this skill's frontmatter"

**Specificity:** specific

---

### REQ-010: Phase 1 Exploration Must Produce Substantive Findings

**Summary:** EXPLORATION.md must contain at least 120 lines of substantive content, at least 8 concrete bug hypotheses with file:line references, at least 5 domain-knowledge risk scenarios, and at least 3–4 pattern deep dives before Phase 2 may begin.

**User story:** As a developer who wants the quality playbook to find real bugs (not generic advice), I expect the exploration phase to produce specific findings grounded in this codebase's code, so that generated requirements catch intent violations rather than just structural anomalies.

**Implementation note:** The 12-check Phase 1 completion gate enforces this. The SKILL.md write-as-you-go discipline and the prohibition on "holding findings in memory" are the mechanisms. The v1.3.43 benchmark failure (chi, zod repos) was caused by agents that produced stub EXPLORATION.md files and skipped the gate.

**Conditions of satisfaction:**
- EXPLORATION.md has ≥120 lines of substantive content (not headers/boilerplate)
- `## Open Exploration Findings` section has ≥8 findings, each with file:line reference
- At least 4 findings reference different modules/subsystems
- At least 3 findings trace behavior across ≥2 functions or code locations
- `## Quality Risks` section has ≥5 domain-driven scenarios with specific file/function citations
- `## Pattern Applicability Matrix` evaluates all 6 patterns
- 3-4 patterns marked FULL; 3-4 Pattern Deep Dive sections exist
- At least 2 deep dives trace ≥2 functions
- `## Candidate Bugs for Phase 2` has ≥4 bugs with file:line, source stage, and review guidance
- Ensemble balance: ≥2 from open exploration/risks; ≥1 from pattern deep dive
- `## Gate Self-Check` section present and written after checks were run

**Alternative paths:**
- Single-session run → same requirements; no relaxation for context window limits
- Large codebase (>200 files) → scope declaration required, but depth requirements within scope are unchanged

**References:** SKILL.md Phase 1 completion gate (~lines 847-862), EXPLORATION.md methodology

**Doc source:** [Tier 1] SKILL.md ~lines 847-862 — 12 mandatory gate checks with exact pass criteria

**Specificity:** specific

---

### REQ-011: Requirements Pipeline Must Produce Traceable, Testable Requirements

**Summary:** REQUIREMENTS.md must be generated through the five-phase pipeline (Contracts → Derivation → Coverage → Completeness → Narrative) and each requirement must include all mandatory fields: Summary, User story (with "so that" clause), Implementation note, Conditions of satisfaction, Alternative paths, References, Doc source (with authority tier), and Specificity.

**User story:** As a developer running Phase 3 (code review) using REQUIREMENTS.md, I expect each requirement to specify testable conditions I can verify against specific code locations, so that the code review can catch intent violations rather than only structural anomalies.

**Implementation note:** REQUIREMENTS.md must begin with a human-readable project overview and use cases before individual requirements. The overview validation gate and use case derivation gate must both pass. Requirements use REQ-NNN identifiers; use cases use UC-NN identifiers. COVERAGE_MATRIX.md must have one row per requirement with no grouped ranges.

**Conditions of satisfaction:**
- Every requirement has all 8 mandatory fields
- Every user story contains a "so that" clause
- All requirement identifiers follow REQ-NNN format
- All use case identifiers follow UC-NN format
- REQUIREMENTS.md begins with a prose overview (not raw metadata)
- Architectural-guidance requirements: ≤3 total
- COVERAGE_MATRIX.md has one row per REQ-NNN (no grouped ranges)

**Alternative paths:**
- Self-referential audit (quality-playbook auditing itself) → requirements derive from SKILL.md's internal consistency rules, not from a separate spec document
- Refinement pass (Phase 7) → additional requirements may be added; all must be versioned in VERSION_HISTORY.md

**References:** SKILL.md Step 7, references/requirements_pipeline.md, EXPLORATION.md methodology notes

**Doc source:** [Tier 1] SKILL.md Step 7 — "The five-phase pipeline" and mandatory requirement fields

**Specificity:** specific

---

### REQ-012: quality_gate.sh Must Handle Empty VERSION Gracefully

**Summary:** When `quality_gate.sh` cannot detect the version from SKILL.md (VERSION remains empty), the script must emit a clear error rather than silently proceeding with malformed directory globs or empty version stamps.

**User story:** As a benchmark runner using `--all` mode without a `--version` flag, I expect the gate to fail clearly when SKILL.md cannot be found or parsed, so that I can diagnose the issue rather than getting a silent no-op (zero repos checked, gate reports PASS).

**Implementation note:** Version auto-detection at lines 60-67 walks a fixed list of paths. If none match, VERSION remains `""`. The `--all` glob at line 678 becomes `*-""/` → `*-/` → matches nothing. The empty-array guard at line 700 triggers a usage message with "GATE FAILED with N checks" — but N may be 0, which looks like a passing run with no work done.

**Conditions of satisfaction:**
- When VERSION is empty and `--all` is specified: gate must emit a clear error message naming the failure (VERSION empty, SKILL.md not found)
- The empty-array message must be clearly distinguishable from a normal gate run that simply found no bugs
- When VERSION is empty and a specific repo dir is given: gate must warn that version detection failed and stamps cannot be verified

**Alternative paths:**
- `--version` explicitly provided → no detection needed; use provided version
- SKILL.md found but `metadata.version` field absent → must emit clear parse error

**References:** `quality_gate.sh:60-67`, `quality_gate.sh:678-701`, EXPLORATION.md Risk 4

**Doc source:** [Tier 3] quality_gate.sh:678 — glob `*-"${VERSION}"/` silently matches nothing when VERSION is empty

**Specificity:** specific

---

### REQ-013: Mechanical Verification Must Not Be Created for Non-Dispatch Contracts

**Summary:** The `quality/mechanical/` directory must only be created when project contracts include dispatch functions, registries, or enumeration checks requiring mechanical extraction. For codebases without such contracts, the directory must not be created and PROGRESS.md must document the decision.

**User story:** As a developer reviewing Phase 2 artifacts, I expect to see a mechanical/ directory only when the project has dispatch-function contracts requiring mechanical extraction, so that an empty directory does not falsely signal that extraction was attempted and abandoned.

**Implementation note:** SKILL.md ~line 578 states: "Do not create an empty mechanical/ directory." The quality-playbook self-audit does not have C-style dispatch functions amenable to `awk`-based case-label extraction. Bash if/elif chains in quality_gate.sh are too short for mechanical extraction to add value. PROGRESS.md must document: "Mechanical verification: NOT APPLICABLE — no dispatch/registry/enumeration contracts in scope."

**Conditions of satisfaction:**
- For codebases without dispatch-function contracts: `quality/mechanical/` must not exist
- For codebases with dispatch-function contracts: `quality/mechanical/verify.sh` must exist and contain re-extraction commands
- PROGRESS.md must document the decision either way

**Alternative paths:**
- Ambiguous case (small Bash dispatch functions) → the decision is "not applicable" with rationale; no partial mechanical/ directory
- Contracts added later in the same run → if new contracts require mechanical extraction, create the directory and populate it fully before writing any contract citing those extractions

**References:** SKILL.md ~line 578, EXPLORATION.md mechanical verification note

**Doc source:** [Tier 1] SKILL.md ~line 578 — "Only create quality/mechanical/ if the project's contracts include dispatch functions, registries, or enumeration checks"

**Specificity:** specific

---

### REQ-014: Gate Script Functional Test Detection Must Be Consistent

**Summary:** `quality_gate.sh` must use a consistent file-detection method across all artifact checks. Using `ls` globs for functional test detection while using `find` for language detection creates an inconsistency that can produce different behaviors under different shell configurations.

**User story:** As a developer working across different shell environments (macOS zsh, Linux bash, CI containers), I expect the gate to detect functional test files reliably regardless of shell options (nullglob, failglob, etc.), so that conformant test files are not incorrectly reported as missing.

**Implementation note:** Functional test detection at lines 123-126 uses `ls ${q}/test_functional.* ...` — unquoted glob, fragile under shell options. Language detection at lines 449-454 uses `find ... -print -quit` — robust. The `&>/dev/null 2>&1` pattern at line 123 is redundant. Aligning functional test detection to use `find` (as language detection does) would resolve the inconsistency.

**Conditions of satisfaction:**
- Functional test detection must return the same result across bash with nullglob enabled and disabled
- Functional test detection must return the same result for `test_functional.sh`, `FunctionalSpec.scala`, `FunctionalTest.java`, and `functional.test.ts` files
- A conformant functional test file must never be incorrectly reported as missing

**Alternative paths:**
- Multiple functional test files (unlikely but possible) → gate must detect at least one
- Functional test file with unusual permissions → gate behavior must be defined (fail, not silently succeed)

**References:** `quality_gate.sh:123-126`, EXPLORATION.md Finding 3

**Doc source:** [Tier 3] quality_gate.sh:123-126 — `ls` glob for functional tests vs `find` for language detection

**Specificity:** specific

---

<!-- Gap Iteration additions — 2026-04-16 -->

### REQ-015: Gate Script Test File Extension Detection Must Use find, Not ls-glob

**Summary:** `quality_gate.sh` line 479 uses `ls ${q}/test_functional.* 2>/dev/null | head -1` to capture the functional test filename for extension detection. Under nullglob, this produces a spurious filename from the current directory, causing incorrect extension validation. The detection must use `find`-based detection consistent with the language detection at lines 486–495.

**User story:** As a developer running the quality gate in a zsh environment with nullglob enabled (common macOS default), I expect the test file extension check to correctly identify or not find functional test files, so that extension mismatch errors only occur when the test file has the wrong extension, not when the glob misbehaves.

**Implementation note:** Lines 486–495 in the same check_repo function use `find` with `-print -quit` for language detection. Line 479 uses `ls` glob for the exact same file-detection purpose. The inconsistency means extension validation can fire on a CWD filename rather than the actual test file. Fix: replace `ls ${q}/test_functional.* 2>/dev/null | head -1` with `find "${q}" -maxdepth 1 -name "test_functional.*" -print -quit 2>/dev/null` (and similar for test_regression.*).

**Conditions of satisfaction:**
- Under nullglob (zsh default), when no test_functional.* file exists: func_test variable must be empty
- Under nullglob, when test_functional.sh exists: func_test variable must contain the correct path
- The same result must occur with nullglob disabled (bash default)
- Extension validation must only run when func_test is a valid test file path (not a CWD entry)

**Alternative paths:**
- Multiple test_functional.* files → detection should return the first one found
- test_regression.* same fix applies at line 480

**References:** `quality_gate.sh:479`, BUG-M8 (same vulnerability class), EXPLORATION_ITER2.md Gap Finding 1

**Doc source:** [Tier 3] quality_gate.sh:479 — ls-glob captures CWD listing under nullglob

**Specificity:** specific

---

### REQ-016: Gate Script Code Reviews Directory Detection Must Use find, Not ls-glob

**Summary:** `quality_gate.sh` line 143 uses `ls ${q}/code_reviews/*.md 2>/dev/null` to detect code review files. Under nullglob, this produces a CWD listing instead of empty, making the check pass even when code_reviews/ exists but is empty. This allows partial runs (directory created but no reviews written) to pass gate checks.

**User story:** As a CI system running quality_gate.sh after a potentially partial playbook run, I expect the gate to correctly detect whether code review files were written to disk, so that a partial session (which creates directories but no review content) is correctly flagged as FAIL rather than silently passing.

**Implementation note:** The pattern `[ -n "$(ls ${q}/code_reviews/*.md 2>/dev/null)" ]` fails under nullglob — the unmatched glob expands to empty, ls lists CWD, and the command substitution is non-empty. Fix: `find "${q}/code_reviews" -maxdepth 1 -name "*.md" -print -quit 2>/dev/null | grep -q .`

**Conditions of satisfaction:**
- Under nullglob, when code_reviews/ exists but is empty: gate must FAIL "code_reviews/ missing or empty"
- Under nullglob, when code_reviews/ has .md files: gate must PASS
- Behavior must be identical with nullglob enabled and disabled

**References:** `quality_gate.sh:143`, BUG-M8 (same vulnerability class), EXPLORATION_ITER2.md Gap Finding 2

**Doc source:** [Tier 3] quality_gate.sh:143 — ls-glob for code_reviews/ detection

**Specificity:** specific

---

### REQ-017: Recommendation Enum Values Must Be Consistent Across All Spec Documents

**Summary:** The integration test recommendation enum values must be consistent across `references/review_protocols.md`, `SKILL.md`, and `quality_gate.sh`. Currently, `references/review_protocols.md` line 410 specifies `SHIP IT / FIX FIRST / NEEDS INVESTIGATION` but `quality_gate.sh` line 427 validates `SHIP / FIX BEFORE MERGE / BLOCK` (matching SKILL.md line 1273). An agent following the reference file produces gate-failing artifacts.

**User story:** As an AI agent generating integration-results.json by following the playbook instructions, I expect all instruction documents to specify the same canonical recommendation enum values, so that following any one document produces gate-conformant artifacts.

**Implementation note:** The canonical values per SKILL.md line 1273 and quality_gate.sh line 427 are: `"SHIP"`, `"FIX BEFORE MERGE"`, `"BLOCK"`. The `references/review_protocols.md` integration test template at line 410 uses the old human-readable vocabulary: `SHIP IT / FIX FIRST / NEEDS INVESTIGATION`. This must be updated to match the canonical values.

**Conditions of satisfaction:**
- `references/review_protocols.md:410` must use canonical enum values: `SHIP / FIX BEFORE MERGE / BLOCK`
- SKILL.md, references/review_protocols.md, and quality_gate.sh must all agree on the same three values
- An agent reading any reference document and following its template must produce gate-passing recommendation values

**References:** `references/review_protocols.md:410`, `quality_gate.sh:427`, `SKILL.md:1273`, EXPLORATION_ITER2.md Gap Finding 3

**Doc source:** [Tier 1] SKILL.md:1273 — canonical recommendation enum values

**Specificity:** specific

---

### REQ-018: Gate Script Must Validate recheck-results.json When Recheck Mode Runs

**Summary:** `quality_gate.sh` validates all documented conditional artifacts (tdd-results.json, integration-results.json, patches, writeups) but has no section for `recheck-results.json` or `recheck-summary.md`. The SKILL.md artifact contract table documents both files as required when recheck runs, but the gate enforces neither.

**User story:** As a developer who has run recheck mode and wants to verify the recheck artifacts are conformant, I expect quality_gate.sh to check that recheck-results.json contains valid status values, required fields, and correct schema_version, so that a malformed recheck run is caught mechanically rather than requiring manual inspection.

**Implementation note:** The gate should check recheck-results.json when it exists: (1) schema_version field must be present (2) status enum values must be one of FIXED, PARTIALLY_FIXED, STILL_OPEN, INCONCLUSIVE (3) required per-result fields: id, severity, status, evidence (4) summary fields: total, fixed, partially_fixed, still_open, inconclusive. Note: schema_version should be updated from "1.0" (current SKILL.md:1965) to "1.1" to match other sidecar JSON files (REQ-018 implies updating the SKILL.md spec as well as the gate).

**Conditions of satisfaction:**
- When recheck-results.json exists: gate checks schema_version, status enum values, required per-result fields
- When recheck-results.json is missing but recheck was not run: gate skips check with info message
- Status enum: must be one of FIXED, PARTIALLY_FIXED, STILL_OPEN, INCONCLUSIVE (4 values)
- Schema_version must be "1.1" (consistent with other sidecar JSON files)

**References:** `quality_gate.sh` (absence finding), `SKILL.md:1965`, `SKILL.md` artifact contract table lines 117-118, EXPLORATION_ITER2.md Gap Findings 4–5

**Doc source:** [Tier 1] SKILL.md artifact contract table — recheck-results.json documented as required when recheck runs

**Specificity:** specific

---

<!-- Unfiltered Iteration additions — 2026-04-16 -->

### REQ-019: Gate Script Functional Test File Existence Check Must Use find, Not ls-glob

**Summary:** `quality_gate.sh` line 124 uses `ls ${q}/test_functional.* ...` to check that a functional test file exists. Under nullglob, all unmatched globs expand to empty, `ls` lists the current working directory, and exits 0 — causing the gate to falsely pass the existence check even when no functional test file exists.

**User story:** As a developer running the quality gate in a zsh environment with nullglob enabled (common macOS default), I expect the functional test file existence check to correctly report FAIL when no functional test file exists, so that gate results are reliable.

**Implementation note:** Line 124: `ls ${q}/test_functional.* ${q}/FunctionalSpec.* ${q}/FunctionalTest.* ${q}/functional.test.* &>/dev/null 2>&1`. This is the FILE EXISTENCE check (distinct from BUG-M12's extension detection at line 479). Fix: replace with `find "${q}" -maxdepth 1 \( -name "test_functional.*" -o -name "FunctionalSpec.*" -o -name "FunctionalTest.*" -o -name "functional.test.*" \) -print -quit 2>/dev/null | grep -q .`

**Conditions of satisfaction:**
- Under nullglob, when no functional test file exists: gate must FAIL "functional test file missing"
- Under nullglob, when test_functional.sh exists: gate must PASS "functional test file exists"
- Same behavior with nullglob disabled

**References:** `quality_gate.sh:124`, BUG-M8 (same vulnerability class), BUG-M12 (line 479 — same issue, different line), EXPLORATION_ITER3.md Finding 1

**Doc source:** [Tier 3] quality_gate.sh:124 — ls-glob for functional test existence check, distinct from BUG-M8/M12 fix scopes

**Specificity:** specific

---

### REQ-020: BUGS.md Heading Regex Must Match Severity-Prefixed Bug IDs

**Summary:** `quality_gate.sh` line 184 uses `grep -cE '^### BUG-[0-9]+'` to count confirmed bugs. This regex never matches severity-prefixed IDs (`BUG-H1`, `BUG-M3`, `BUG-L6`) used by the Quality Playbook's own self-audit. When QFB-format IDs are used, `bug_count=0`, causing the gate to skip ALL TDD log, patch, and writeup validation — providing false assurance of zero bugs.

**User story:** As a developer running quality_gate.sh after a QFB self-audit run that used severity-prefixed bug IDs, I expect the gate to correctly count confirmed bugs and validate TDD logs, patches, and writeups, so that the gate provides meaningful quality assurance rather than silently bypassing all TDD/patch/writeup checks.

**Implementation note:** Line 184: `correct_headings=$(grep -cE '^### BUG-[0-9]+' ...)`. Also line 313: `bug_ids=$(grep -oE 'BUG-[0-9]+' ...)`. Both must be extended to match severity-prefix format. Fix: change regex to `^### BUG-[A-Z0-9]+` or `^### BUG-[A-Z]*[0-9]+` — matching both `BUG-001` (numeric) and `BUG-H1`, `BUG-M3`, `BUG-L6` (severity-prefix) formats. The spec example at SKILL.md:1615 says `### BUG-NNN` which must be clarified to include both formats.

**Conditions of satisfaction:**
- `grep -cE '^### BUG-[0-9]+'` must match `### BUG-001` (numeric format)
- Same or modified regex must also match `### BUG-H1`, `### BUG-M3`, `### BUG-L6` (severity-prefix format)
- When BUGS.md has 15 severity-prefixed bug entries: `bug_count` must be 15, not 0
- With `bug_count=15`: TDD log checks, patch checks, and writeup checks must all execute

**References:** `quality_gate.sh:184`, `quality_gate.sh:313`, `SKILL.md:1615`, EXPLORATION_ITER3.md Finding 2

**Doc source:** [Tier 3] quality_gate.sh:184 — regex `^### BUG-[0-9]+` excludes severity-prefix IDs used by QFB

**Specificity:** specific

---

### REQ-021: Gate Must Cross-Validate tdd-results.json Phase Values Against Log File Tags

**Summary:** `quality_gate.sh` validates the tdd-results.json `red_phase`/`green_phase` field PRESENCE but not their values. It validates log file first-line tags (RED/GREEN/NOT_RUN/ERROR) separately. No check compares the JSON values against log evidence, allowing contradictory sidecar/log pairs to pass.

**User story:** As a developer using tdd-results.json to understand TDD results, I expect the `red_phase` JSON value to be consistent with what the actual log file shows, so that `"red_phase": "pass"` with a log showing `RED` (which means the test failed, i.e., red phase) is detected and flagged as a contradiction.

**Implementation note:** JSON validates only PRESENCE of `red_phase` field (line 239-248). Log validates tag format (line 323-325: `RED|GREEN|NOT_RUN|ERROR`). No code compares them. Cross-validation would: for each bug with `verdict: "TDD verified"`, verify the log first line is `GREEN` (pass); for bugs with `verdict: "confirmed open"`, verify the log first line is `RED` (fail). Fix: add cross-validation when log and JSON are both present.

**Conditions of satisfaction:**
- Bug with `verdict: "TDD verified"` and red.log first line `GREEN`: gate must FAIL (TDD verified means red phase FAILED, not passed)
- Bug with `verdict: "confirmed open"` and red.log first line `GREEN`: gate must FAIL
- Bug with `verdict: "TDD verified"` and green.log first line `RED`: gate must FAIL
- Consistent pairs must PASS

**References:** `quality_gate.sh:239-248`, `quality_gate.sh:307-387`, `SKILL.md:1589`, EXPLORATION_ITER3.md Finding 9

**Doc source:** [Tier 1] SKILL.md:1589 — "TDD sidecar-to-log consistency check (mandatory)" — but gate doesn't enforce it

**Specificity:** specific

---

### REQ-022: Gate Summary Sub-Key Checks Must Use json_key_count for Consistency

**Summary:** The gate's TDD sidecar JSON validation uses `json_has_key` for summary sub-key checks (lines 259-265) but `json_key_count` for per-bug field checks (lines 239-248). These are parallel checks for required JSON field presence that should use the same validator to provide consistent guarantees.

**User story:** As a developer debugging a gate failure for "summary missing 'total' count", I expect the check to be as reliable as the per-bug field checks, so that a PASS result means the key genuinely exists as a JSON property and not just as a substring in a string value.

**Implementation note:** `json_has_key` uses `grep -q "\"${key}\""` (matches anywhere, including string values). `json_key_count` uses `grep -c "\"${key}\"[[:space:]]*:"` (colon-anchored, only matches JSON key positions). The per-bug check correctly uses the stronger pattern. The summary check should use the same pattern.

**Conditions of satisfaction:**
- Lines 259-265: use `json_key_count` (or equivalent colon-anchored check) instead of `json_has_key`
- A tdd-results.json where `"total"` appears only in a string value must FAIL the summary check

**References:** `quality_gate.sh:239-248`, `quality_gate.sh:259-265`, EXPLORATION_ITER4.md Group PG-1, BUG-L19

**Doc source:** [Tier 3] Internal gate consistency — same "required field present" contract should use same validator

**Specificity:** specific

---

### REQ-023: Patch Existence Check Must Iterate Per-Bug ID

**Summary:** The patch existence check at quality_gate.sh:562-588 uses aggregate ls-glob counting, while the TDD log check at lines 316-345 iterates per-bug ID. Both enforce the same contract ("every confirmed bug must have its artifact"), but at different levels of rigor. The patch check must use per-bug iteration to match the TDD log check pattern.

**User story:** As a developer who accidentally uploaded two regression-test patches for one bug and none for another, I expect the gate to detect that one bug's patch is missing rather than seeing a misleading PASS from matching total counts.

**Conditions of satisfaction:**
- Patch section iterates `bug_ids` per-bug, as lines 316-345 do for TDD logs
- A run with N bugs but patches for wrong bug IDs must FAIL
- Aggregate count approach replaced with per-bug find-based detection

**References:** `quality_gate.sh:316-345`, `quality_gate.sh:562-588`, EXPLORATION_ITER4.md Group PG-2, BUG-L20

**Doc source:** [Tier 3] Parallel enforcement contract — same "every bug must have artifact X" requirement, same enforcement pattern

**Specificity:** specific

---

### REQ-024: Phase 5 Must Include Entry Gate for Phase 4 Artifacts

**Summary:** Phase 2 has a mandatory "HARD STOP" entry gate that verifies Phase 1 artifacts mechanically before any Phase 2 work. Phase 5 has no equivalent — it proceeds based on PROGRESS.md prose and only checks Phase 4 completion at the terminal gate (at the end of Phase 5). The fail-early pattern must be applied consistently.

**User story:** As an agent beginning Phase 5, I expect to be stopped immediately if Phase 4 artifacts don't exist, so I don't complete all of Phase 5 only to fail at the terminal gate.

**Conditions of satisfaction:**
- SKILL.md Phase 5 opening includes a mandatory entry gate before any Phase 5 work
- Gate checks for triage file and auditor report files mechanically (not via PROGRESS.md checkbox)
- If artifacts are missing, STOP and redirect to Phase 4

**References:** `SKILL.md:897-907`, `SKILL.md:1573-1590`, EXPLORATION_ITER4.md Group PG-4, BUG-L21

**Doc source:** [Tier 3] Fail-early pattern consistency — Phase 2 applies it; Phase 5 should too

**Specificity:** specific

---

### REQ-025: SEED_CHECKS.md Must Be Added to Artifact Contract Table

**Summary:** SKILL.md's Phase 5 artifact file-existence gate (line 1641) requires quality/SEED_CHECKS.md when Phase 0 or 0b runs. The canonical artifact contract table (lines 88-119) does not include this artifact. The table is declared "canonical" — this self-contradiction must be resolved by adding SEED_CHECKS.md to the table.

**User story:** As an agent reading the artifact contract table to understand what files to create, I expect the table to be complete so I don't miss required artifacts like SEED_CHECKS.md.

**Conditions of satisfaction:**
- SEED_CHECKS.md added to artifact contract table with condition "If Phase 0 or 0b ran"
- Table's canonical claim is accurate — all required artifacts are listed
- quality_gate.sh may optionally add a check for SEED_CHECKS.md when Phase 0b is detected

**References:** `SKILL.md:85-119`, `SKILL.md:1641`, EXPLORATION_ITER4.md Group PG-6, BUG-L22

**Doc source:** [Formal] SKILL.md:88 — "This is the canonical list" contradicted by SKILL.md:1641 requirement

**Specificity:** specific


---

### REQ-026: Gate Must Validate integration-results.json groups[].result Enum Values

**Summary:** The quality gate validates `tdd-results.json` verdict values (at lines 294-296) against a defined enum ("TDD verified", "confirmed open") but performs NO equivalent validation for `integration-results.json` groups[].result values. SKILL.md:1273 explicitly defines the valid result enum as "pass", "fail", "skipped", "error". The gate must enforce this enum to provide machine-readable contract reliability.

**User story:** As a CI tool that reads integration-results.json and checks `if result == "pass"`, I expect the gate to have already validated that all groups[].result values are canonical, so a gate PASS means I can trust the field values — not just that the file exists.

**Implementation note:** Parallel to tdd verdict validation at lines 294-296. Additionally, SKILL.md:1273 defines uc_coverage value enum ("covered_pass", "covered_fail", "not_mapped") — these should also be validated for the same reasons.

**Conditions of satisfaction:**
- quality_gate.sh integration block validates each groups[].result against the four valid values
- An integration-results.json with groups[].result: "PASS" (wrong case) must FAIL the gate
- An integration-results.json with groups[].result: "OK" must FAIL the gate
- uc_coverage values validated against "covered_pass", "covered_fail", "not_mapped"

**References:** `quality_gate.sh:389-436`, `quality_gate.sh:294-296`, SKILL.md:1273, SKILL.md:1277, BUG-L23

**Doc source:** [Formal] SKILL.md:1273 — valid result values explicitly enumerated; SKILL.md:1277 — post-write validation mandated

**Specificity:** specific

---

### REQ-027: Gate Must Validate integration-results.json Summary Sub-Keys

**Summary:** The quality gate checks that `integration-results.json` has a `summary` key (line 393) but never validates the four required sub-keys: `total_groups`, `passed`, `failed`, `skipped` (SKILL.md:1252-1255). By contrast, `tdd-results.json` summary sub-keys are checked at lines 259-265. The integration summary must receive equivalent sub-key validation.

**User story:** As a developer writing an aggregation script that reads `summary.total_groups` from integration-results.json files across multiple runs, I expect the gate to guarantee these sub-keys exist, so I don't need to add defensive null checks for fields mandated by the spec.

**Implementation note:** Use `json_key_count` (colon-anchored) rather than `json_has_key` (substring match, BUG-L19 class). This is strictly better than the tdd sub-key pattern. Both BUG-L19 and BUG-L24 should be fixed together to achieve full consistency.

**Conditions of satisfaction:**
- Integration summary validation checks total_groups, passed, failed, skipped (all four sub-keys)
- Uses json_key_count for colon-anchored matching (stronger than json_has_key)
- An integration-results.json with "summary": {} must FAIL the gate
- An integration-results.json with "summary": {"status": "ok"} must FAIL the gate

**References:** `quality_gate.sh:393-394`, `quality_gate.sh:259-265`, SKILL.md:1252-1255, BUG-L24

**Doc source:** [Formal] SKILL.md:1252-1255 — integration summary schema defined with 4 mandatory sub-keys

**Specificity:** specific

---

### REQ-028: Phase 2 Entry Gate Must Enforce 120-Line Minimum (Extends REQ-003/BUG-M3)

**Summary:** SKILL.md's Phase 1 completion gate check #1 (line 850) requires "at least 120 lines of substantive content" in EXPLORATION.md. The Phase 2 entry gate (lines 897-904) is supposed to backstop Phase 1 requirements in new sessions. BUG-M3 identified missing checks 2,3,5,8,10,12 in the Phase 2 entry gate — the BUG-M3 fix adds those but NOT check #1. After BUG-M3's fix, a thin EXPLORATION.md (~15 lines) still passes Phase 2 entry gate.

**User story:** As an agent starting Phase 2 in a new session with a thin EXPLORATION.md, I expect the Phase 2 entry gate to catch the 120-line shortfall immediately (HARD STOP), not silently allow shallow requirements to propagate through Phase 2.

**Implementation note:** This is a spec-primary fix to SKILL.md:897-904. The 120-line check is check #1 in Phase 1 because it's the primary defense against thin exploration. Add it as check #1 (renumbering subsequent checks) to preserve the ordering logic.

**Conditions of satisfaction:**
- SKILL.md Phase 2 entry gate includes 120-line minimum as its first check
- An EXPLORATION.md with 6 section title stubs (~15 lines) triggers HARD STOP at Phase 2 entry gate
- BUG-M3 fix patch extended (or replacement patch created) to include this check
- The 12 Phase 1 checks and Phase 2 entry gate checks are fully aligned

**References:** SKILL.md:850, SKILL.md:897-904, quality/patches/BUG-M3-fix.patch, BUG-M3, BUG-L25

**Doc source:** [Formal] SKILL.md:846-862 — 12 Phase 1 completion gate checks (check #1: 120 lines); SKILL.md:897-904 — Phase 2 entry gate (no 120-line check)

**Specificity:** specific
