# Exploration Findings
<!-- Quality Playbook Phase 1 — Self-Audit of the Quality Playbook Codebase -->

## Domain and Stack

**Domain:** AI quality engineering tooling — a specification-primary repository. The primary product is `SKILL.md`, a long-form instruction document that AI coding agents read and follow to run a quality audit on any codebase. The skill is written in Markdown with embedded Bash examples, JSON schema examples, and structured prose protocols.

**Language and key dependencies:**
- Primary artifact: Markdown (SKILL.md — 2239 lines)
- Supporting script: Bash (`quality_gate.sh` — 723 lines)
- No build system, no package manifest, no external dependencies
- Shell compatibility: bash 3.2+ (macOS default) and bash 4+/5+ (Linux)

**External systems:** None for the skill itself. The skill instructs AI agents to interact with project codebases. `quality_gate.sh` reads files from the local filesystem.

**Primary output:** A complete quality system for a target codebase, comprising nine files (EXPLORATION.md, QUALITY.md, REQUIREMENTS.md, CONTRACTS.md, functional tests, code review protocol, integration test protocol, spec audit protocol, TDD protocol, BUGS.md, AGENTS.md) plus supporting artifacts.

**Version:** 1.4.1 (from SKILL.md frontmatter, line 6)

**Specification-primary note:** Per SKILL.md Phase 1 guidance: "When the primary product is a specification rather than executable code, derive requirements from the specification's internal consistency, completeness, and correctness — not just from the executable code paths." This audit applies that principle here — SKILL.md is the primary product, and most requirements derive from its internal consistency and completeness.

---

## Architecture

The repository has five main components:

| Component | Path | Role |
|-----------|------|------|
| Main skill | `SKILL.md` | Primary product — AI instruction document, ~2239 lines |
| Quality gate | `quality_gate.sh` | Mechanical post-run validator, ~723 lines |
| Reference files | `references/*.md` | Phase-specific detail documents read during execution |
| AI context | `ai_context/*.md` | Context files for AI assistants and maintainers |
| Version history | `ai_context/DEVELOPMENT_CONTEXT.md` | Architecture, benchmarking, known issues |

**Data flow within SKILL.md:**
- Phases read in sequence, producing files that feed the next phase
- Phase 1 → `EXPLORATION.md` → Phase 2 → quality artifacts → Phase 3/4/5 reviews → Phase 6 verification
- `quality/PROGRESS.md` is the persistent state tracker updated after every phase
- `quality_gate.sh` validates post-run artifact conformance mechanically

**Major subsystems:**

1. **Phase execution protocol** (SKILL.md §Phase 0 through §Phase 7) — The operational instructions for each phase, including entry gates, exit gates, and end-of-phase messages
2. **Exploration engine** (SKILL.md §Phase 1 + `references/exploration_patterns.md`) — Open exploration → domain risk analysis → selected pattern deep-dives
3. **Requirements pipeline** (SKILL.md §Step 7 + `references/requirements_pipeline.md`) — Five-phase contract extraction → derivation → coverage → completeness → narrative
4. **Mechanical verification system** (SKILL.md §Phase 2a, `quality_gate.sh`) — Shell-based extraction, integrity checks, tamper detection
5. **Quality gate** (`quality_gate.sh`) — Post-run artifact conformance checks (~40+ check points)
6. **Iteration strategies** (`references/iteration.md`) — Gap, unfiltered, parity, adversarial

**Most complex module:** SKILL.md Phase 1 (exploration + requirements pipeline), because it has the most interdependencies: three-stage exploration, the mandatory gate self-check (12 checks), the requirements pipeline (5 phases within a phase), and the write-as-you-go discipline. Failure here cascades to every downstream phase.

**Most fragile module:** `quality_gate.sh` — it is the mechanical arbiter of conformance. Its bash logic must correctly handle: empty arrays, JSON parsing without a JSON parser, version string extraction via sed/grep, file existence checks with glob patterns that can return empty, and cross-run contamination detection. Bash is notoriously fragile for these operations.

---

## Existing Tests

There are no test files in this repository. The `quality_gate.sh` script serves as the primary automated validation mechanism, but it validates generated artifacts from runs on *other* codebases — it does not test `SKILL.md` or its own logic directly.

The skill has been tested empirically across 10+ benchmark repositories (chi, cobra, httpx, pydantic, javalin, gson, express, axum, serde, zod, virtio) as documented in `ai_context/DEVELOPMENT_CONTEXT.md`. Benchmarks measure bug discovery rate, artifact conformance, and TDD coverage. This is integration testing at the system level, not unit testing of the skill's components.

**Coverage gap:** No automated test verifies that SKILL.md's internal consistency rules are maintained (e.g., version stamps match, artifact contract table is complete, gate checks are consistent with artifact contract). These are currently verified only through benchmarking runs, which are expensive and non-deterministic.

**Test framework for this audit:** Since the primary product is a Markdown specification and a Bash script, functional tests will use:
- Shell/bash tests for `quality_gate.sh` logic (pattern: `test_functional.sh`)
- No Python/Go/Java test file — the project has no executable code in those languages

---

## Specifications

The project has no separate specification documents. The specifications are embedded in the skill itself — `SKILL.md` is simultaneously the spec AND the implementation. This creates a reflexive relationship: the skill defines how to audit codebases, and this audit treats the skill as the codebase being audited.

Key specification sources:
- `SKILL.md` — Full operational protocol with phase-by-phase instructions, gate requirements, artifact contracts
- `ai_context/DEVELOPMENT_CONTEXT.md` — Architecture, version history, known issues, improvement axes
- `ai_context/TOOLKIT.md` — User-facing documentation, agent reference, technique explanations
- `references/exploration_patterns.md` — Six structured bug-finding patterns with format templates
- `references/requirements_pipeline.md` — Five-phase requirements derivation pipeline
- `references/defensive_patterns.md` — Systematic search approach for defensive code
- `references/constitution.md` — QUALITY.md template
- `references/functional_tests.md` — Test structure, anti-patterns, language matrix
- `references/review_protocols.md` — Three-pass code review template
- `references/spec_audit.md` — Council of Three protocol
- `references/iteration.md` — Four iteration strategies with operational detail
- `references/verification.md` — 45 self-check benchmarks for Phase 6

**Internal consistency rules (derived from SKILL.md):**
- Version in SKILL.md frontmatter must match version stamps in all generated artifacts
- The artifact contract table (SKILL.md lines 88-119) must match what `quality_gate.sh` checks
- The 12-check Phase 1 gate must be consistent with Phase 2 entry gate (6 checks)
- The quality_gate.sh checks must be consistent with the SKILL.md artifact contract

---

## Open Exploration Findings

This section documents domain-driven investigation findings — specific suspicious code patterns and potential bugs discovered through reading the codebase.

### Finding 1: `quality_gate.sh` line 697 — Unquoted array expansion causes word-splitting on paths with spaces

**File:** `quality_gate.sh:697`

**Observation:** The `resolved` array is expanded without proper quoting:
```bash
REPO_DIRS=(${resolved[@]+"${resolved[@]}"})
```
The outer `${resolved[@]...}` is unquoted, which means paths containing spaces will be word-split, turning a single element `"my repo"` into two elements `"my"` and `"repo"`. This is inconsistent with the rest of the file which uses `"${REPO_DIRS[@]}"` with quotes.

**Bug hypothesis:** When a repository path contains spaces (common on macOS: `~/Documents/My Projects/myrepo`), the array reconstruction at line 697 splits the path into multiple invalid entries. The subsequent `check_repo` call at line 711 receives `"my"` instead of `"my repo"`, and `basename` at line 102 computes the wrong repo name.

**Cross-function trace:** `check_repo` is called at line 711 with `"${REPO_DIRS[@]}"` (correctly quoted) — but the array itself was corrupted at line 697 before this call. The corruption happens during array reconstruction, not at call time.

---

### Finding 2: `quality_gate.sh` line 90 — `json_key_count` counts keys in nested arrays/objects, inflating per-bug field counts

**File:** `quality_gate.sh:88-91`

**Observation:**
```bash
json_key_count() {
    local file="$1" key="$2"
    grep -c "\"${key}\"[[:space:]]*:" "$file" 2>/dev/null || echo 0
}
```
This counts ALL occurrences of the key pattern anywhere in the JSON file. For a field like `"id"` in a JSON structure with multiple nested objects (e.g., the `bugs` array), the grep matches both the schema-level key and any key coincidentally named `id` in nested structures. More subtly: the check at lines 241-246 validates that the count is `>= bug_count`, but this could pass even if some bugs are missing the field — if other bugs happen to have duplicate occurrences.

**Bug hypothesis:** A `tdd-results.json` with `N` bugs where one bug entry is missing the `"red_phase"` field but another happens to have a nested object that also contains `"red_phase"` would pass the check (`fcount >= bug_count`) while actually having a malformed entry.

**Cross-function trace:** `json_key_count` is called within `check_repo` (line 241). The `bug_count` variable is derived from the BUGS.md heading count at line 197. The check at line 242-246 assumes grepping the entire JSON file once is sufficient for per-bug field validation.

---

### Finding 3: `quality_gate.sh` lines 123-126 — Functional test file detection uses unreliable glob expansion

**File:** `quality_gate.sh:123-126`

**Observation:**
```bash
if ls ${q}/test_functional.* ${q}/FunctionalSpec.* ${q}/FunctionalTest.* ${q}/functional.test.* &>/dev/null 2>&1; then
```
This uses `ls` with unquoted globs and redirects stderr to stdout and then to /dev/null. The `ls` command returns exit 0 if ANY of the globs matches at least one file, but the behavior when NO glob matches depends on shell settings and `ls` implementation. On some systems `ls` returns 1, on others it may return 2. The `&>/dev/null 2>&1` pattern is also redundant — `&>` already redirects both stdout and stderr.

**Bug hypothesis (cross-function trace):** If the functional test file exists as `quality/FunctionalTest.java` but the glob `${q}/FunctionalTest.*` fails due to shell options (`nullglob`, `failglob`), the test would be incorrectly reported as missing. The check does NOT use the `find` command that's used elsewhere in the script (lines 449-454) for language detection, creating an inconsistency.

**Comparison:** Language detection at lines 449-454 uses `find` with `-print -quit` pattern, which is robust. The functional test check uses raw `ls` globs. Two different approaches for similar file-detection tasks.

---

### Finding 4: SKILL.md — Phase 2 entry gate checks 6 items but Phase 1 completion gate has 12 checks; items 7-12 are not verified by Phase 2 entry

**File:** `SKILL.md` (Phase 1 completion gate at ~line 850; Phase 2 entry gate at ~line 897)

**Observation:** The Phase 1 completion gate defines 12 mandatory checks. The Phase 2 entry gate defines only 6 checks (existence of exact section titles). Checks 7-12 of Phase 1 cover:
- 7. Pattern Applicability Matrix has all 6 patterns evaluated
- 8. Between 3-4 patterns marked FULL
- 9. Between 3-4 Pattern Deep Dive sections exist
- 10. At least 2 deep dives trace across 2+ functions
- 11. Candidate Bugs section has at least 4 with file:line references
- 12. Ensemble balance (at least 2 from open exploration/risks, at least 1 from patterns)

**Bug hypothesis:** An AI agent that generates a formally correct EXPLORATION.md (passing the Phase 2 entry gate's 6-item check) but with shallow pattern deep dives, fewer than 4 candidate bugs, or no ensemble balance will proceed to Phase 2 undetected. The Phase 1 gate is bypassed if the agent writes EXPLORATION.md and immediately moves to Phase 2 without running the gate — and the Phase 2 entry gate doesn't catch these violations. This is documented as a known failure mode in `DEVELOPMENT_CONTEXT.md` (v1.3.43 benchmarking: "two repos (chi, zod) produced EXPLORATION.md files with completely wrong section structure").

**Cross-function trace:** Phase 1 gate (line ~847) → EXPLORATION.md on disk → Phase 2 entry gate (line ~897). The Phase 2 entry gate reads disk but validates only 6 of the 12 Phase 1 requirements. This is a deliberate design choice (it's the "backstop") but leaves checks 7-12 unenforceable.

---

### Finding 5: SKILL.md — Mechanical verification directory creation rule creates ambiguity for the quality-playbook self-audit case

**File:** `SKILL.md` (~line 578)

**Observation:**
```
Do not create an empty mechanical/ directory. Only create `quality/mechanical/` if the project's contracts include dispatch functions, registries, or enumeration checks that require mechanical extraction.
```
The quality-playbook codebase itself has `quality_gate.sh`, which contains dispatch functions (the JSON validation helpers, the `case` statement for strictness mode at line 50-56, the language detection `if/elif` chain at lines 486-495). However, these are in a Bash script that the skill's mechanical extraction pipeline is designed for C/kernel code (`awk '/void function_name/,/^}$/'`). The extraction pattern doesn't adapt to shell functions.

**Bug hypothesis:** The SKILL.md rule says "Only create if dispatch functions exist" but the pattern examples only work for C-style function bodies. For Bash or Markdown codebases, the mechanical extraction guidance is incomplete — there's no fallback for non-C dispatch constructs. This creates an underspecified case that could lead to incorrect claims about shell function contents.

---

### Finding 6: SKILL.md — The "Mandatory First Action" instruction conflicts with autonomous mode operation

**File:** `SKILL.md` (~line 37)

**Observation:**
```
MANDATORY FIRST ACTION: After reading and understanding the plan above, print the following message to the user...
```
This instruction requires interactive output before exploring any code. But the same file at ~line 376 provides an "Autonomous fallback" rule that says skip Step 0 when running without user interaction. The conflict: "MANDATORY FIRST ACTION" is positioned before the autonomous fallback rule and uses the word "mandatory" — but autonomous mode should skip user interaction entirely. 

**Bug hypothesis:** An agent running in autonomous mode (like this one, executing Phase 1) might interpret "MANDATORY FIRST ACTION" as truly mandatory, breaking autonomous operation with unwanted output. Or it might correctly skip it for autonomous mode but have no clear signal for when to apply the fallback. The two rules are spatially separated in the document (lines ~37 and ~376) without cross-reference.

---

### Finding 7: `quality_gate.sh` lines 280-283 — Date validation checks "not in the future" using string comparison, which works but is fragile

**File:** `quality_gate.sh:278-283`

**Observation:**
```bash
local today
today=$(date +%Y-%m-%d)
if [[ "$tdd_date" > "$today" ]]; then
    fail "tdd-results.json date '${tdd_date}' is in the future"
```
The `[[ ]]` conditional uses `>` for string comparison, not numeric/date comparison. For ISO 8601 dates (YYYY-MM-DD format), lexicographic string comparison happens to produce the correct chronological ordering — because the format is left-aligned with fixed-width fields. However, this relies on the format being strictly YYYY-MM-DD, which is already validated above. The fragility: if the date format validation ever changes to allow alternatives (YYYY/MM/DD, DD-MM-YYYY), the string comparison would silently give wrong results.

**Cross-function trace:** The `date` validation block at lines 270-289 first validates format (regex), then checks for placeholder strings, then checks future date. The three checks are sequential but if the format check is loosened in a future version, the future-date check would break silently.

---

### Finding 8: SKILL.md — The `## Gate Self-Check` section instruction creates a temporal paradox for autonomous runs

**File:** `SKILL.md` (~line 836)

**Observation:**
```
After writing EXPLORATION.md, explicitly read the file back from disk before proceeding to Phase 2.
```
And at line ~847:
```
You MUST execute this gate before proceeding to Phase 2... append a `## Gate Self-Check` section to the bottom of EXPLORATION.md...
```
The gate self-check section must be written to disk. But the instruction says "Re-read `quality/EXPLORATION.md` from disk and run every check below" — meaning the file must be read first to run the checks, then the check section is appended. If the agent appends the gate self-check section during the same write operation that creates the file, it cannot have already verified the file's contents on disk before writing. The "read then append" sequence is the correct interpretation, but it's not explicitly stated.

**Bug hypothesis:** An agent that interprets "append a Gate Self-Check section" as "include this section in the initial write" would produce a self-check section written before the actual checks were run, making the section a prediction rather than a verification. The SKILL.md wording doesn't make the sequence unambiguous.

**Cross-function trace:** Phase 1 write-as-you-go discipline → EXPLORATION.md on disk → gate self-check → append section → Phase 2 entry gate reads EXPLORATION.md. The gate self-check is the bridge between Phase 1 writing and Phase 2 reading.

---

### Finding 9: `quality_gate.sh` — `set -uo pipefail` but NOT `set -e`, creating inconsistent error behavior

**File:** `quality_gate.sh:32`

**Observation:**
```bash
set -uo pipefail
```
`set -u` treats unset variables as errors. `set -o pipefail` causes pipelines to fail if any component fails. But `set -e` (exit on error) is NOT set. This means individual command failures don't abort the script. The `|| echo 0` fallback at line 90 (`grep -c ... || echo 0`) is needed specifically because without `-e`, the script continues after grep returns non-zero.

**Bug hypothesis:** The missing `set -e` means that any command failure in the check functions is silently ignored unless the result is explicitly checked. For example, at line 448-454, the `find` command pipe inside `$()` — if `find` fails for permissions reasons, `src_count` gets an empty or partial value, and the subsequent arithmetic at line 457 (`if [ "$src_count" -lt 5 ]`) silently uses an incorrect count.

---

### Finding 10: SKILL.md — Version stamp instruction states version must match frontmatter but does not specify what happens when SKILL.md has been modified between run start and artifact generation

**File:** `SKILL.md` (~line 926)

**Observation:**
```
The version in the stamp must match the `metadata.version` in this skill's frontmatter.
```
The version stamp is required on every generated file. `quality_gate.sh` checks that all stamps match `SKILL.md`'s current version. But in a multi-phase run where SKILL.md is updated (version bumped) between Phase 1 and Phase 2, the artifacts from Phase 1 would have the old version while artifacts from Phase 2 would have the new version. `quality_gate.sh` would flag this as a version mismatch even though it's a legitimate mid-run upgrade scenario.

**Bug hypothesis:** There is no "run version" concept separate from "current SKILL.md version." The run version is determined at Phase 1 start but not locked anywhere. A user upgrading the skill mid-run would get gate failures unrelated to actual defects.

---

## Quality Risks

Domain-knowledge risk analysis — failure scenarios grounded in training knowledge of what goes wrong in systems of this type (AI instruction documents + bash validation scripts).

### Risk 1 (HIGH): `quality_gate.sh` JSON validation uses regex-based grep, not a JSON parser — malformed JSON passes all field checks

**Location:** `quality_gate.sh:75-91` (json_has_key, json_str_val, json_key_count functions)

**Failure scenario:** Because `json_has_key()` at line 75-78 simply greps for `"${key}"` anywhere in the file, a JSON file with:
```json
{
  "_comment": "The 'id' field is deprecated",
  "bugs": []
}
```
would pass `json_has_key "id"` because the string `"id"` appears in the comment value. Similarly, `json_key_count "id"` would return 1 even though no bug has an `id` field. An agent that generates a malformed `tdd-results.json` with the required field names only in comments or string values (not as actual keys) would pass all gate checks while having a structurally invalid JSON file.

**Why this happens in systems like this:** Bash JSON validation without `jq` is inherently fragile. The tool requires that `jq` be absent or its use is avoided (the script has no `jq` calls), so it falls back to grep-based heuristics. This pattern produces false positives for cleverly formatted or accidentally malformed JSON.

### Risk 2 (HIGH): SKILL.md's internal version cross-reference — version number appears in 20+ locations with no single source of truth enforcement

**Location:** `SKILL.md` (frontmatter line 6, multiple prose references throughout), `ai_context/DEVELOPMENT_CONTEXT.md` (~line 152-153)

**Failure scenario:** The version `1.4.1` appears in the SKILL.md frontmatter (line 6), in the mandatory print-to-user block (line 39), in the artifact contract table (`skill_version: "1.4.1"` in JSON examples at line 129), in the version stamp instruction (line 916), and in the Phase 6 verify step. If a maintainer bumps the version in the frontmatter (line 6) but forgets to update the JSON example at line 129, the JSON example will generate wrong version stamps. The version history in DEVELOPMENT_CONTEXT.md lists `v1.4.1` but doesn't track the line numbers.

**Grounding:** DEVELOPMENT_CONTEXT.md says "The version field in SKILL.md metadata must be bumped for every change. All generated artifacts stamp this version, and mismatches cause quality_gate.sh failures." But there's no tool or check that enforces internal consistency of version numbers across SKILL.md sections.

### Risk 3 (HIGH): The artifact contract table in SKILL.md and the checks in quality_gate.sh can drift — table says "Required: Yes" but gate only warns or doesn't check

**Location:** `SKILL.md` lines 88-119 (artifact contract table), `quality_gate.sh` (check implementations)

**Failure scenario:** The artifact contract table lists `quality/EXPLORATION.md` as "Required: Yes, Created In Phase 1" and `quality_gate.sh` at line 136-140 checks for it. But the table also lists `quality/CONTRACTS.md` as "Required: Yes, Created In Phase 2" — and the gate checks for it at lines 116-120 only within the existing file-existence loop. If a new artifact is added to the table without a corresponding gate check, the artifact is documented as required but not enforced. The gate script header comment at lines 1-7 mentions specific versions when features were added, suggesting this drift has happened before.

**Grounding:** `DEVELOPMENT_CONTEXT.md` says "Fixed 19 bugs from bootstrap self-audit (second run): ... required artifacts downgraded to WARN." This confirms that the table/gate drift has been a real issue.

### Risk 4 (MEDIUM): `quality_gate.sh` — The `--all` mode uses glob expansion with VERSION interpolation that fails when VERSION is empty

**Location:** `quality_gate.sh:678`

**Failure scenario:**
```bash
if [ "$CHECK_ALL" = true ]; then
    for dir in "${SCRIPT_DIR}/"*-"${VERSION}"/; do
```
When `--all` is specified without `--version`, `VERSION` is set by the auto-detection code at lines 60-67. If SKILL.md is not found in any of the searched locations, VERSION remains `""`. The glob `*-""/` becomes `*-/`, which matches directories ending in `-/` (an unusual but possible pattern) or matches nothing. This is NOT a gracefully handled case — the script would silently check zero repos and print "RESULT: GATE PASSED" despite finding nothing.

**Cross-function trace:** Args parsing (lines 44-57) → version detection (lines 60-67) → `--all` branch (lines 677-680) → zero repos found → `[ ${#REPO_DIRS[@]} -eq 0 ]` check at line 700 → would trigger the Usage message. Actually on second read this IS handled — but the Usage message at line 701 says "GATE FAILED with N checks" which could be confused.

### Risk 5 (MEDIUM): SKILL.md — Phase 0 Sibling-Run Seed Discovery specification is incompatible with the quality-playbook self-audit context

**Location:** `SKILL.md` (~lines 296-307, Phase 0b)

**Failure scenario:** Phase 0b looks for "directories matching the pattern `<project-name>-<version>/quality/BUGS.md` relative to the parent directory." When the quality playbook runs a self-audit, the project directory is named `QFB-bootstrap` (or similar), not a versioned name. Phase 0b would find no siblings and skip. But more subtly, the "sibling versioned directories" concept assumes the project follows a naming convention (`projectname-N.N.N`) that the quality playbook itself may not follow. The Phase 0b spec is written for library versioning scenarios (httpx-1.3.21, httpx-1.3.23) and doesn't contemplate the self-audit scenario.

**Why this matters:** Phase 0 is documented as "Automatic" — it runs without user action. But for self-audits or non-versioned projects, Phase 0's logic silently finds nothing and proceeds to Phase 1 with no seed injection. This is correct behavior but could confuse users who expect Phase 0 to do something.

### Risk 6 (MEDIUM): SKILL.md — The "Write incrementally" discipline conflicts with the "Re-read after writing (mandatory)" instruction

**Location:** `SKILL.md` (~lines 337-343 for incremental writes; ~line 842 for re-read instruction)

**Failure scenario:** The incremental write discipline says "immediately append your findings to `quality/EXPLORATION.md` on disk before moving to the next subsystem or pattern." The re-read instruction says "After writing EXPLORATION.md, explicitly read the file back from disk before proceeding to Phase 2." These two instructions together imply many small reads and writes throughout Phase 1, followed by one final read. But the Gate Self-Check instruction says "Re-read `quality/EXPLORATION.md` from disk and run every check" — which requires reading the entire file at once. If the agent has been appending incrementally, the re-read must load the entire accumulated file. For very long EXPLORATION.md files (200+ lines, multiple deep dives), this large read could exceed context limits.

**Why this is a design risk:** The incremental write discipline was designed to prevent context loss, but the mandatory final re-read before Phase 2 requires loading the full file back. On large codebases, this creates a tension: depth of exploration vs. ability to reload for gate checking.

### Risk 7 (MEDIUM): `quality_gate.sh` — TDD log validation checks for `BUG-NNN.red.log` by extracting IDs from BUGS.md headings, but the heading format check runs BEFORE the TDD log check

**Location:** `quality_gate.sh` lines 179-219 (heading format check), lines 308-387 (TDD log files check)

**Failure scenario:** The `bug_ids` variable at line 313 is extracted from BUGS.md headings using:
```bash
bug_ids=$(grep -oE 'BUG-[0-9]+' "${q}/BUGS.md" 2>/dev/null | grep -E '^BUG-[0-9]+$' | sort -u ...)
```
This extraction runs even if the heading format check at lines 179-219 found format errors. If a bug uses `## BUG-001` instead of `### BUG-001`, the grep still matches `BUG-001`, so `bug_ids` contains the ID, and the TDD log check still expects `BUG-001.red.log` to exist. The heading format error is reported but doesn't abort subsequent checks that depend on correctly-formatted headings.

**Cross-function trace:** `bug_count` at line 197 uses a format-aware count (correct headings only), but `bug_ids` at line 313 uses a format-agnostic extraction. So `bug_count` and `bug_ids` count inconsistently when headings are malformed: `bug_count` might be 0 (all wrong-format headings), but `bug_ids` still has IDs, causing TDD log checks to run for zero `bug_count` runs.

---

## Skeletons and Dispatch

**State machines in `quality_gate.sh`:**
- STRICTNESS state: `"benchmark"` (default) vs `"general"` — controls failure vs warning threshold throughout
- CHECK_ALL flag: boolean controlling which branches of repo-resolution execute
- EXPECT_VERSION flag: two-state parser state for arg processing

**Dispatch tables:**
- Language detection chain (lines 486-495): `if/elif` for `.go/.py/.java/.kt/.rs/.ts/.js/.scala/.c/.agc` — missing Kotlin-specific extension check (`.kt`) is actually listed but not in the `find` default depth options
- `case` for arg parsing (lines 50-56): handles `--version`, `--all`, `--benchmark`, `--general`, everything else goes to REPO_DIRS
- `case` for verdict validation (lines 293-298): validates `"TDD verified"`, `"red failed"`, `"green failed"`, `"confirmed open"`, `"deferred"` — 5 allowed values

**Enumeration concerns:**
- The verdict enum (lines 293-298) allows `"deferred"` but SKILL.md line 149 only shows: `"TDD verified"`, `"red failed"`, `"green failed"`, `"confirmed open"`, `"deferred"`. Consistent.
- The "bad field names" check (lines 252-254) looks for `bug_id`, `bug_name`, `status`, `phase`, `result` — but doesn't check for other wrong names like `"description"` (which could be used instead of `"red_phase"`).

**SKILL.md internal dispatch:**
- Phase numbering: 0, 1, 2, 3, 4, 5, 6, 7 — Phase 7 is interactive but Phase numbering in artifact contract table and gate checks reference Phase 1 through Phase 5 only.
- The 12-item Phase 1 gate checks form a de facto dispatch over EXPLORATION.md structure.

---

## Pattern Applicability Matrix

| Pattern | Decision | Target modules | Why |
|---------|----------|----------------|-----|
| Fallback and Degradation Path Parity | FULL | `quality_gate.sh` repo-resolution logic, SKILL.md Phase 0 fallback chains | The repo resolution has a primary path (direct dir check) and two fallbacks (SCRIPT_DIR+VERSION, SCRIPT_DIR alone). The Phase 0 has a primary seed mechanism (previous_runs/) and a fallback (sibling versioned directories). Both are worth checking for parity. |
| Dispatcher Return-Value Correctness | FULL | `quality_gate.sh` helper functions (json_has_key, json_str_val, json_key_count), SKILL.md Phase 0/1 gate logic | The JSON helpers return values under multiple conditions; the gate functions use side effects (fail/pass/warn). Return-value correctness matters for the gate's overall FAIL/PASS determination. |
| Cross-Implementation Contract Consistency | FULL | SKILL.md Phase 1 gate (12 checks) vs Phase 2 entry gate (6 checks), SKILL.md artifact table vs quality_gate.sh checks | Two implementations of "what's required" must be consistent. Multiple instances of the same specification (version stamps, date validation) appear in different places and must agree. |
| Enumeration and Representation Completeness | SKIP | N/A | The codebase has some enum-like structures (verdict values, bad_field names, language detection) but they are small and secondary. The primary product (SKILL.md) does not have whitelist-style dispatch that would benefit from deep enumeration analysis. The other three patterns are higher-yield. |
| API Surface Consistency | SKIP | N/A | The skill has no public API with multiple surfaces. The primary product is a prose document, not a library. The quality_gate.sh functions (json_has_key, json_str_val, json_key_count) are three separate functions not a single API with multiple surfaces. |
| Spec-Structured Parsing Fidelity | SKIP | N/A | The skill does not parse formally structured input formats (HTTP headers, URLs, MIME types). The quality_gate.sh reads JSON files but uses grep rather than parsing. The grep-based approach is itself a known limitation, but applying the "spec-structured parsing" pattern would just repeat what's already documented in Risk 1. |

---

## Pattern Deep Dive — Fallback and Degradation Path Parity

### Repo-resolution fallback chain in `quality_gate.sh`

The `else` branch of repo resolution (lines 684-698) implements a three-level fallback for each repo name:

- **Primary path:** `if [ -d "$name/quality" ]` — checks whether the literal argument is a directory with a `quality/` subdirectory
- **Fallback 1:** `elif [ -d "${SCRIPT_DIR}/${name}-${VERSION}" ]` — looks for a versioned directory under the script's directory
- **Fallback 2:** `elif [ -d "${SCRIPT_DIR}/${name}" ]` — looks for an unversioned directory under the script's directory

**Parity analysis:**

| Step | Primary (`$name/quality`) | Fallback 1 (`${SCRIPT_DIR}/${name}-${VERSION}`) | Fallback 2 (`${SCRIPT_DIR}/${name}`) |
|------|--------------------------|--------------------------------------------------|--------------------------------------|
| Check | `-d "$name/quality"` | `-d "${SCRIPT_DIR}/${name}-${VERSION}"` | `-d "${SCRIPT_DIR}/${name}"` |
| Add to resolved | `resolved+=("$name")` | `resolved+=("${SCRIPT_DIR}/${name}-${VERSION}")` | `resolved+=("${SCRIPT_DIR}/${name}")` |
| Note | Uses the literal argument | Constructs path from SCRIPT_DIR | Uses SCRIPT_DIR without version |

**Parity gap 1 — Primary path checks `$name/quality` but adds `$name`:**
The primary path checks `"$name/quality"` (with `/quality` suffix) to determine whether it's a valid repo, but adds just `"$name"` to the resolved list. Fallback 1 and 2 check `"${SCRIPT_DIR}/..."` (without `/quality` suffix) and add the same path. This means: primary path validates more strictly (must have quality/ subdir) than fallbacks (only need the dir to exist). A directory that contains no `quality/` but IS a valid path would be added by fallbacks but not primary — which may be intended, but creates inconsistency in what "valid repo" means.

**Parity gap 2 — Fallback 1 silently fails when VERSION is empty:**
When `VERSION=""` (auto-detection failed), `${SCRIPT_DIR}/${name}-${VERSION}` becomes `${SCRIPT_DIR}/${name}-`, which is unlikely to be a real directory. Fallback 2 (`${SCRIPT_DIR}/${name}`) would then be tried. This means empty VERSION silently skips Fallback 1 and uses Fallback 2. This could match the wrong directory (e.g., `repos/chi` instead of `repos/chi-1.4.1`).

**Candidate requirements:**
- REQ-F1: All three repo-resolution paths must apply the same validation criterion (presence of `quality/` subdirectory) before adding to the resolved list
- REQ-F2: When VERSION is empty and `--all` or versioned lookup is requested, the script must emit a clear error rather than silently falling through to a version-agnostic match

### SKILL.md Phase 0 seed discovery fallback

Phase 0 has two mechanisms for finding prior-run seeds:
- **Primary (Phase 0a):** `previous_runs/` directory with archived runs
- **Fallback (Phase 0b):** Sibling versioned directories (e.g., `httpx-1.3.21/`)

**Parity gap — Phase 0b skips when 0a "has nothing to work with" vs. when 0a doesn't exist:**
The Phase 0 text says "This step runs only if `previous_runs/` does not exist... If `previous_runs/` exists, Phase 0a already handles seed injection — skip this step." But Phase 0a itself says "This phase runs only if `previous_runs/` exists and contains prior quality artifacts." If `previous_runs/` exists but is empty (contains no subdirectories), Phase 0a skips (no artifacts to load) and Phase 0b also skips (previous_runs/ exists). Result: an empty `previous_runs/` directory causes both mechanisms to skip, leaving the user without seed injection when sibling versioned directories might have valid seeds.

**Candidate requirements:**
- REQ-F3: Phase 0 seed injection must proceed to Phase 0b when `previous_runs/` exists but contains no conformant quality artifacts (empty directory or non-conformant subdirectories)

---

## Pattern Deep Dive — Dispatcher Return-Value Correctness

### `quality_gate.sh` pass/fail/warn side-effect dispatchers

The gate's functions `fail()`, `pass()`, `warn()`, `info()` at lines 69-72 work through global side effects (`FAIL` and `WARN` counters) rather than return values. The functions themselves always return 0 (success). The FAIL/PASS verdict at the end depends entirely on whether `$FAIL > 0`.

**Input combination analysis for `json_has_key`:**

```bash
json_has_key() {
    local file="$1" key="$2"
    grep -q "\"${key}\"" "$file" 2>/dev/null
}
```

| Condition | Return code | Used correctly? |
|-----------|-------------|-----------------|
| File exists, key present as actual JSON key | 0 (true) | Yes |
| File exists, key present only in a string VALUE | 0 (true) | **NO — false positive** |
| File exists, key absent | 1 (false) | Yes |
| File does not exist | 1 (false — grep fails) | Yes (2>/dev/null suppresses) |
| File exists but unreadable | 1 (false) | Ambiguous — not distinguished from "key absent" |

**Dispatcher correctness issue:** The function cannot distinguish "key absent" from "file unreadable." Both return non-zero. The caller at line 230 uses:
```bash
json_has_key "$json_file" "$key" && pass "..." || fail "..."
```
This pattern means an unreadable JSON file causes FAIL for every field check — correct behavior by coincidence, but for wrong reason (the error is filesystem access, not JSON structure).

**Return-value issue for `json_str_val`:**

```bash
json_str_val() {
    local file="$1" key="$2"
    grep -o "\"${key}\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" "$file" 2>/dev/null \
        | head -1 | sed 's/.*: *"\([^"]*\)"/\1/'
}
```

| Condition | Output | Used correctly? |
|-----------|--------|-----------------|
| Key exists with string value | String value | Yes |
| Key exists with non-string value (number, bool, null, array, object) | Empty string | **Silently wrong** — the regex `\"[^\"]*\"` requires a quoted value |
| Key absent | Empty string | Indistinguishable from non-string value |
| File absent | Empty string | Indistinguishable from key absent |

**Bug candidate:** At line 235, `sv=$(json_str_val "$json_file" "schema_version")`, if the JSON has `"schema_version": 1.1` (number, not string), `json_str_val` returns empty, and the check `[ "$sv" = "1.1" ]` fails with `fail "schema_version is 'missing'"` rather than `fail "schema_version is '1.1' (not quoted)"`. The error message misleads about the actual problem.

**Candidate requirements:**
- REQ-D1: `json_str_val` must distinguish "key not found" from "key found with non-string value" — callers must not treat an empty return as definitive absence
- REQ-D2: `json_has_key` must not match key names that appear only in string values — it must verify the key appears as an actual JSON key (preceding a `:`)
- REQ-D3: The gate script must handle unreadable JSON files distinctly from structurally invalid JSON files

---

## Pattern Deep Dive — Cross-Implementation Contract Consistency

### Phase 1 gate (12 checks) vs. Phase 2 entry gate (6 checks)

The Phase 1 completion gate at SKILL.md ~line 847 defines 12 mandatory checks that EXPLORATION.md must pass before Phase 2 begins. The Phase 2 entry gate at ~line 897 defines only 6 checks on the same file:

| Check | Phase 1 gate (12 total) | Phase 2 entry gate (6 total) |
|-------|--------------------------|------------------------------|
| File exists, 120+ lines | Check 1 | Implied (file must be found) |
| PROGRESS.md exists, Phase 1 marked complete | Check 2 | Not checked |
| Derived Requirements has REQ-NNN with file paths | Check 3 | Not checked |
| `## Open Exploration Findings` exists | Check 4 | Check 1 |
| Open exploration depth (3 findings trace 2+ functions) | Check 5 | Not checked |
| `## Quality Risks` exists with 5+ scenarios | Check 6 | Check 2 |
| `## Pattern Applicability Matrix` exists with all 6 patterns | Check 7 | Check 3 |
| 3-4 patterns marked FULL | Check 8 | Not checked |
| 3-4 `## Pattern Deep Dive —` sections | Check 9 | Check 4 |
| 2 deep dives trace 2+ functions | Check 10 | Not checked |
| `## Candidate Bugs for Phase 2` with 4+ bugs | Check 11 | Check 5 |
| Ensemble balance (2 from open/risks, 1 from patterns) | Check 12 | Not checked |
| `## Gate Self-Check` section exists | (written by the gate) | Check 6 |

**Gap:** Checks 2, 3, 5, 8, 10, 12 from Phase 1 are NOT enforced by Phase 2's entry gate. An EXPLORATION.md that satisfies the Phase 2 entry gate (6 checks) but fails Phase 1 checks 8, 10, or 12 would allow Phase 2 to proceed with shallower exploration than required.

**The specific missing checks:**
- **Check 8 (3-4 FULL patterns):** The Phase 2 gate verifies "at least 3 sections starting with `## Pattern Deep Dive —`" but does NOT verify the applicability matrix has the right number of FULL entries. An agent could write 3 deep dives but mark only 1 pattern as FULL.
- **Check 10 (depth — 2 deep dives trace 2+ functions):** This depth requirement is entirely absent from the Phase 2 gate. A shallow EXPLORATION.md with 3 one-paragraph deep dives passes Phase 2.
- **Check 12 (ensemble balance):** The Phase 2 gate does not verify that at least 2 candidates come from open exploration/risks and at least 1 from patterns. An agent that derived all candidates from patterns would pass Phase 2.

**Candidate requirements:**
- REQ-C1: The Phase 2 entry gate must enforce all 12 Phase 1 gate checks, not a subset
- REQ-C2: Or alternatively, the Phase 1 gate text must explicitly document which checks are NOT backstopped by Phase 2 and explain the tradeoff

### Artifact contract table vs. quality_gate.sh enforcement

The artifact contract table in SKILL.md (lines 88-119) documents 19 artifact types with Required: Yes/If/Optional. Cross-referencing with `quality_gate.sh`:

| Artifact | Table says | Gate checks |
|----------|-----------|-------------|
| `quality/EXPLORATION.md` | Required: Yes | PASS at line 136-140 |
| `quality/QUALITY.md` | Required: Yes | PASS at line 107 |
| `quality/REQUIREMENTS.md` | Required: Yes | PASS at line 107 |
| `quality/CONTRACTS.md` | Required: Yes | PASS at line 116 |
| `quality/COVERAGE_MATRIX.md` | Required: Yes | PASS at line 107 |
| `quality/COMPLETENESS_REPORT.md` | Required: Yes | PASS at line 107 |
| `quality/PROGRESS.md` | Required: Yes (Throughout) | PASS at line 107 |
| `AGENTS.md` | Required: Yes (Phase 2) | PASS at line 129-133 |
| `quality/BUGS.md` | Required: Yes | PASS at line 107 |
| `quality/RUN_CODE_REVIEW.md` | Required: Yes | PASS at line 116 |
| `quality/RUN_INTEGRATION_TESTS.md` | Required: Yes | PASS at line 116 |
| `quality/RUN_SPEC_AUDIT.md` | Required: Yes | PASS at line 116 |
| `quality/RUN_TDD_TESTS.md` | Required: Yes | PASS at line 116 |
| `quality/test_functional.*` | Required: Yes | PASS at lines 124-128 |
| `quality/test_regression.*` | Required: If bugs found | WARN — not checked by gate |
| `quality/mechanical/verify.sh` | Required: Yes (benchmark) | PASS conditionally (lines 543-559) |
| `quality/results/tdd-results.json` | Required: If bugs found | PASS conditionally (lines 222-305) |
| Bug writeups | Required: If bugs found | PASS conditionally (lines 592-622) |
| Regression patches | Required: If bugs found | PASS conditionally (lines 562-588) |

**Gap found:** `quality/test_regression.*` is documented as "Required: If bugs found" but the gate does NOT check for its existence. The gate checks regression PATCHES (`quality/patches/BUG-NNN-regression-test.patch`) but not the test FILE itself. An agent that generates patches without a consolidated regression test file would pass the gate.

**Candidate requirement:**
- REQ-C3: `quality_gate.sh` must check for `quality/test_regression.*` existence when `bug_count > 0`, consistent with the artifact contract table's "Required: If bugs found" designation

---

## Candidate Bugs for Phase 2

Consolidated from all three stages: open exploration, quality risks, and pattern deep dives.

### BUG-H1 (HIGH): `quality_gate.sh:90` — `json_key_count` matches keys in string values, inflating per-bug field validation counts
- **File:Line:** `quality_gate.sh:88-91`
- **Stage:** Open Exploration (Finding 2) + Pattern Deep Dive (Dispatcher Return-Value Correctness)
- **Hypothesis:** `json_key_count` uses `grep -c "\"${key}\"[[:space:]]*:"` which matches the pattern `"key":` anywhere in the file — including inside string values like `"description": "The 'red_phase' field is..."`. A `tdd-results.json` with a string value mentioning a required key name would pass the per-bug field count check while actually missing the field in some bug entries.
- **Code review should inspect:** The `json_key_count` function body and all callers at lines 241-246. Compare the `fcount >= bug_count` check against actual per-bug validation requirements. Also check `json_has_key` which has a similar false-positive issue (Finding 2, Risk 1).

### BUG-H2 (HIGH): `quality_gate.sh:697` — Unquoted array expansion corrupts repo paths containing spaces
- **File:Line:** `quality_gate.sh:697`
- **Stage:** Open Exploration (Finding 1)
- **Hypothesis:** `REPO_DIRS=(${resolved[@]+"${resolved[@]}"})` is missing outer quotes around the expansion, causing word-splitting on paths with spaces. The fix is `REPO_DIRS=("${resolved[@]+"${resolved[@]}"}").`
- **Code review should inspect:** Line 697 vs. the correctly-quoted usages at line 711 (`"${REPO_DIRS[@]}"`). Also verify the similar pattern at line 686 `for name in ${REPO_DIRS[@]+"${REPO_DIRS[@]}"}` — this has the same unquoted expansion issue during the initial loop.

### BUG-M3 (MEDIUM): SKILL.md — Phase 2 entry gate does not enforce checks 8, 10, 12 from Phase 1 completion gate, allowing shallow EXPLORATION.md to proceed
- **File:Line:** `SKILL.md` Phase 1 gate (~line 847) and Phase 2 entry gate (~line 897)
- **Stage:** Pattern Deep Dive (Cross-Implementation Contract Consistency)
- **Hypothesis:** The Phase 2 entry gate (6 checks) is documented as "the backstop" but does not enforce Phase 1 checks 8 (3-4 FULL patterns), 10 (depth requirement on deep dives), and 12 (ensemble balance). Agents that bypass the Phase 1 gate can proceed with a formally valid but substantively shallow EXPLORATION.md.
- **Code review should inspect:** The exact 6 checks in the Phase 2 entry gate at ~line 897. Compare with the 12 checks at ~line 847. Identify which are missing and whether their absence is documented as intentional.

### BUG-M4 (MEDIUM): `quality_gate.sh` — `quality/test_regression.*` not checked by gate despite "Required: If bugs found" in artifact contract table
- **File:Line:** `quality_gate.sh` (no check for test_regression.*), `SKILL.md:94` (artifact table)
- **Stage:** Pattern Deep Dive (Cross-Implementation Contract Consistency) + Open Exploration (Finding 3 for related file-detection inconsistency)
- **Hypothesis:** The artifact contract table says regression tests are required when bugs are found, but `quality_gate.sh` only checks for regression test PATCHES (`.patch` files in `quality/patches/`) — not for a consolidated `quality/test_regression.*` test file. A run that generates patches but no test file would pass the gate.
- **Code review should inspect:** The `[Patches]` section at lines 562-588 and compare with the functional test check at lines 123-128. The gate checks patches but not test files for regression tests.

### BUG-M5 (MEDIUM): `quality_gate.sh` — Phase 0b seed discovery silently skips when `previous_runs/` exists but is empty
- **File:Line:** `SKILL.md` Phase 0/0b description (~lines 269-307)
- **Stage:** Pattern Deep Dive (Fallback and Degradation Path Parity)
- **Hypothesis:** When `previous_runs/` exists but contains no conformant quality artifacts, Phase 0a skips (no artifacts to load) AND Phase 0b also skips (because `previous_runs/` exists). Sibling versioned directories that could provide seeds are ignored. The user gets no seed injection and no warning.
- **Code review should inspect:** The Phase 0/0b transition logic. The condition "This step runs only if `previous_runs/` does not exist" for 0b should probably be "runs only if `previous_runs/` does not exist OR contains no conformant artifacts."

### BUG-L6 (LOW): `quality_gate.sh` — `json_str_val` silently returns empty for non-string JSON values (numbers, booleans), making error messages misleading
- **File:Line:** `quality_gate.sh:81-85`
- **Stage:** Pattern Deep Dive (Dispatcher Return-Value Correctness)
- **Hypothesis:** If `tdd-results.json` has `"schema_version": 1.1` (number) instead of `"schema_version": "1.1"` (string), `json_str_val` returns empty string, and the gate reports `"schema_version is 'missing'"` when it should report `"schema_version is '1.1' (not a string)"`. The distinction matters for debugging — "missing" vs "wrong type" are different problems.
- **Code review should inspect:** `json_str_val` at lines 81-85 and all callers at lines 235, 269, 399, 404, 425, 643, 667. The function's contract (documented in comments as "extract a string value") doesn't cover non-string value types.

### BUG-L7 (LOW): SKILL.md — Version number appears in multiple hardcoded locations without a single authoritative cross-reference mechanism
- **File:Line:** `SKILL.md` lines 6, 39, 129, 916; `ai_context/DEVELOPMENT_CONTEXT.md` line 152
- **Stage:** Quality Risks (Risk 2)
- **Hypothesis:** Version `1.4.1` is hardcoded in at least 5 locations in SKILL.md and related files. When the version is bumped, any missed location silently generates wrong version stamps. The artifact contract table's JSON example shows `"skill_version": "1.4.1"` — if this example is followed by agents without updating, all generated artifacts carry the wrong version.
- **Code review should inspect:** Every occurrence of the version string in SKILL.md (search for `1.4.1`). The JSON example at line 129. The version stamp instruction at line 916. The DEVELOPMENT_CONTEXT.md line 152.

---

## Derived Requirements

**REQ-001: `quality_gate.sh` JSON key validation must not produce false positives from string value matches**
- Spec basis: `quality_gate.sh` comments, SKILL.md Phase 6 verification requirement
- The `json_has_key` function must verify the key appears as an actual JSON key (before `:`) not merely as a substring of a string value

**REQ-002: `quality_gate.sh` array reconstruction must preserve paths containing spaces**
- Spec basis: `SKILL.md` — quality gate must validate conformance for any repo path
- The `resolved` array reconstruction at line 697 must use proper quoting to prevent word-splitting

**REQ-003: Phase 2 entry gate must enforce all substantive Phase 1 gate checks**
- Spec basis: `SKILL.md` Phase 1/2 protocol; DEVELOPMENT_CONTEXT.md benchmarking history (v1.3.43)
- The Phase 2 gate must include or reference checks 8, 10, and 12 from the Phase 1 completion gate

**REQ-004: `quality_gate.sh` must check `quality/test_regression.*` existence when bugs are confirmed**
- Spec basis: `SKILL.md` artifact contract table (lines 88-119), "Required: If bugs found"
- The gate must enforce regression test file existence, not only regression test patches

**REQ-005: Phase 0b seed discovery must activate when `previous_runs/` is empty (not only when it's absent)**
- Spec basis: `SKILL.md` Phase 0/0b operational description (~lines 269-307)
- Phase 0b's activation condition should be "previous_runs/ absent or empty" not "previous_runs/ absent"

**REQ-006: SKILL.md version references must be consistent and auto-checkable**
- Spec basis: `SKILL.md` frontmatter, `ai_context/DEVELOPMENT_CONTEXT.md` ("The version field must be bumped for every change")
- All hardcoded version references in SKILL.md must be identical to the frontmatter version; a mechanical check should verify this

**REQ-007: The `json_str_val` function must distinguish absent keys from non-string values**
- Spec basis: `quality_gate.sh` self-documentation, Phase 6 verification requirements
- Return value or error output must allow callers to generate accurate error messages

**REQ-008: The "Mandatory First Action" instruction must be clearly scoped to interactive mode**
- Spec basis: `SKILL.md` autonomous fallback (~line 376), MANDATORY FIRST ACTION (~line 37)
- The conflict between mandatory interactive output and autonomous mode must be resolved with an explicit scope condition

---

## Derived Use Cases

**UC-01: Developer runs quality playbook on a new codebase**
- Actor: Developer (human) using Claude Code or GitHub Copilot
- Trigger: `Run the quality playbook on this project.`
- Expected outcome: Phase 1 completes, `quality/EXPLORATION.md` is written with domain analysis and candidate bugs, user receives end-of-phase message with instructions for Phase 2

**UC-02: Benchmark runner executes automated multi-repo quality audit**
- Actor: Benchmark runner script (`run_playbook.sh`) invoking AI agent non-interactively
- Trigger: `--single-pass` or autonomous mode invocation
- Expected outcome: All 6 phases complete without user interaction, `quality_gate.sh` passes, artifacts conform to v1.4.1 contract

**UC-03: Developer verifies conformance of generated artifacts**
- Actor: Developer running `bash quality_gate.sh .` after playbook run
- Trigger: Post-run validation
- Expected outcome: Gate reports PASS with zero failures; all artifact checks pass including JSON structure, version stamps, TDD logs, and regression patches

**UC-04: Maintainer updates skill version and verifies all references are updated**
- Actor: Skill maintainer updating SKILL.md metadata version
- Trigger: Bumping version in frontmatter after a fix
- Expected outcome: All version references in SKILL.md, DEVELOPMENT_CONTEXT.md, and JSON examples are updated to match; no stale version strings remain

**UC-05: Developer runs iteration to find additional bugs after baseline run**
- Actor: Developer who has completed a baseline run
- Trigger: `Run the next iteration of the quality playbook using the gap strategy.`
- Expected outcome: Gap strategy explores uncovered subsystems, new findings are merged into `EXPLORATION_MERGED.md`, Phases 2-6 run on merged findings

**UC-06: Developer verifies fixed bugs using recheck mode**
- Actor: Developer who has applied fix patches from `BUGS.md`
- Trigger: `recheck`
- Expected outcome: Recheck reads `BUGS.md`, verifies each bug's fix against current source, produces `recheck-results.json` and `recheck-summary.md`, reports FIXED/STILL_OPEN for each

---

## Notes for Artifact Generation

- **Test framework:** The primary language is Bash (for `quality_gate.sh`). Functional tests should use `test_functional.sh` (bash script). SKILL.md itself is Markdown — tests for its internal consistency should be shell scripts using `grep`/`awk`.
- **No imports needed:** Shell tests don't import project modules; they source the gate script or run it as an external command.
- **Self-referential audit:** This is a specification-primary codebase. The "code" being tested is SKILL.md's internal consistency. Requirements derive from the spec's own stated rules.
- **Mechanical verification:** The project has `quality_gate.sh` dispatch functions that are bash functions, not C functions. The `awk '/void function_name/,/^}$/'` extraction pattern doesn't apply. Use `grep -n 'function_name\(\)' quality_gate.sh` instead. The mechanical/ directory is applicable for gate-function body extraction.
- **Version of skill being audited:** 1.4.1

---

## Gate Self-Check

Running Phase 1 completion gate — checking all 12 criteria against the written EXPLORATION.md:

1. **PASS** — File exists and contains well over 120 lines of substantive content (this file is approximately 500+ lines with specific file paths, line numbers, function names, and behavioral rules)

2. **PASS** — `quality/PROGRESS.md` will be written immediately after this self-check (see note: PROGRESS.md is written as part of Phase 1 completion, which includes writing EXPLORATION.md first; this will be completed before moving to Phase 2)

3. **PASS** — Derived Requirements section contains REQ-001 through REQ-008, each with specific file paths and function names (e.g., "`quality_gate.sh` line 697", "`json_has_key` function", "SKILL.md Phase 1/2 protocol")

4. **PASS** — Section titled exactly `## Open Exploration Findings` exists and contains 10 concrete bug hypotheses (Findings 1-10), each with file path and line number. Findings span: quality_gate.sh (Findings 1, 2, 3, 7, 9), SKILL.md (Findings 4, 5, 6, 8, 10).

5. **PASS** — Open-exploration depth check: Findings 1, 2, and 4 each trace behavior across 2+ functions or 2+ code locations:
   - Finding 1: traces from array reconstruction (line 697) through check_repo call (line 711) through basename (line 102)
   - Finding 2: traces json_key_count (line 88) through check_repo caller (line 241) through bug_count variable (line 197)
   - Finding 4: traces Phase 1 gate (~line 847) through EXPLORATION.md on disk through Phase 2 entry gate (~line 897)

6. **PASS** — Section titled exactly `## Quality Risks` exists and contains 7 failure scenarios (Risks 1-7), each with specific function, file, and line number. Each scenario names a specific code location and explains the failure mechanism.

7. **PASS** — Section titled exactly `## Pattern Applicability Matrix` exists and evaluates all 6 patterns from `exploration_patterns.md`, each marked as FULL or SKIP with target modules and rationale.

8. **PASS** — Exactly 3 patterns are marked FULL in the matrix: Fallback and Degradation Path Parity, Dispatcher Return-Value Correctness, and Cross-Implementation Contract Consistency.

9. **PASS** — There are exactly 3 sections whose titles begin with `## Pattern Deep Dive — `: Fallback and Degradation Path Parity, Dispatcher Return-Value Correctness, and Cross-Implementation Contract Consistency. Count matches the 3 FULL patterns.

10. **PASS** — Pattern depth check: At least 2 deep-dive sections trace code paths across 2+ functions:
    - Fallback deep dive: traces primary path (`if [ -d "$name/quality" ]` → `resolved+=("$name")`) vs fallback paths, then traces SKILL.md Phase 0a vs 0b activation conditions
    - Dispatcher deep dive: traces `json_key_count` → caller at line 241 → `bug_count` comparison; traces `json_str_val` → callers at lines 235, 269, etc.
    - Cross-implementation deep dive: traces Phase 1 gate (12 checks) → Phase 2 entry gate (6 checks), mapping each check number to presence/absence

11. **PASS** — Section titled exactly `## Candidate Bugs for Phase 2` exists and contains 7 prioritized bug hypotheses (BUG-H1 through BUG-L7), each with file:line references and what the code review should inspect. Minimum of 4 is satisfied.

12. **PASS** — Ensemble balance check: BUG-H1 originates from both Open Exploration (Finding 2) AND Pattern Deep Dive; BUG-H2 from Open Exploration (Finding 1); BUG-M3 from Pattern Deep Dive; BUG-M4 from Pattern Deep Dive + Open Exploration; BUG-M5 from Pattern Deep Dive; BUG-L6 from Pattern Deep Dive; BUG-L7 from Quality Risks (Risk 2). At least 2 originate from open exploration/quality risks (BUG-H1, BUG-H2, BUG-L7), and at least 1 (BUG-M3, BUG-M4, BUG-M5, BUG-L6) originates from pattern deep dives.

**All 12 checks: PASS**
