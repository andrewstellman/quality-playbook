# Behavioral Contract Extraction

<!-- Quality Playbook v1.4.1 — generated 2026-04-16 -->

Generated: 2026-04-16
Source files analyzed: 14 (SKILL.md, quality_gate.sh, 12 references/*.md)
Total contracts extracted: 52

## Summary by category

- METHOD: 18
- NULL: 3
- CONFIG: 5
- ERROR: 7
- INVARIANT: 9
- COMPAT: 2
- ORDER: 3
- LIFECYCLE: 3
- THREAD: 0 (not applicable — single-process bash/AI instruction context)

---

## SKILL.md (24 contracts)

### Phase execution contracts

1. [INVARIANT] Phases execute in sequence (0 → 1 → 2 → 3 → 4 → 5 → 6 → 7). No phase may begin before all prior phase artifacts are written to disk. The phase handoff uses files, not memory.

2. [LIFECYCLE] Phase 1 writes `quality/EXPLORATION.md` and `quality/PROGRESS.md`. These files must exist before Phase 2 begins. Phase 2 reads them as its primary inputs.

3. [METHOD] Phase 1 completion gate: EXPLORATION.md must pass all 12 checks before Phase 2 may begin. A `## Gate Self-Check` section listing each check (1–12) with PASS/FAIL must be appended to EXPLORATION.md on disk.

4. [METHOD] Phase 2 entry gate: verifies 6 items from EXPLORATION.md before generating artifacts. This is a subset of the 12 Phase 1 gate checks. Checks 2, 3, 5, 8, 10, and 12 from Phase 1 are NOT enforced by the Phase 2 entry gate.

5. [INVARIANT] The version stamp in every generated artifact must match `metadata.version` in SKILL.md frontmatter. Mismatches cause quality_gate.sh failures.

6. [CONFIG] When running in autonomous/benchmark mode (invoked non-interactively or via `--single-pass`), the "Mandatory First Action" print instruction and Step 0 user interaction are skipped. The autonomous fallback is defined at ~line 376.

7. [INVARIANT] `quality/PROGRESS.md` must be updated after every phase. The cumulative BUG tracker tracks every confirmed bug across all phases.

### Artifact contract

8. [INVARIANT] The following artifacts are required for any complete run: `quality/EXPLORATION.md`, `quality/QUALITY.md`, `quality/REQUIREMENTS.md`, `quality/CONTRACTS.md`, `quality/test_functional.*`, `quality/RUN_CODE_REVIEW.md`, `quality/RUN_INTEGRATION_TESTS.md`, `quality/RUN_SPEC_AUDIT.md`, `quality/RUN_TDD_TESTS.md`, `quality/BUGS.md`, `quality/COVERAGE_MATRIX.md`, `quality/COMPLETENESS_REPORT.md`, `quality/PROGRESS.md`, `AGENTS.md`.

9. [INVARIANT] `quality/test_regression.*` is required when `bug_count > 0`. The artifact contract table at SKILL.md lines 88-119 designates this as "Required: If bugs found."

10. [INVARIANT] `quality/mechanical/verify.sh` is required when contracts include dispatch functions, registries, or enumeration checks requiring mechanical extraction. Must NOT be created for codebases without such contracts.

11. [LIFECYCLE] Sidecar JSON files (`tdd-results.json`, `integration-results.json`) must be written after their prerequisite artifacts. `tdd-results.json` must be written after all bug writeups exist. `integration-results.json` must be written after integration tests run.

### Phase 0 contracts

12. [CONFIG] Phase 0a activates only when `previous_runs/` exists AND contains prior quality artifacts (subdirectories with conformant BUGS.md). Empty `previous_runs/` causes Phase 0a to skip.

13. [CONFIG] Phase 0b activates only when `previous_runs/` does NOT exist. If `previous_runs/` exists but is empty, Phase 0b does NOT activate — sibling versioned directories are not consulted.

14. [ERROR] Phase 0b specification: "only if previous_runs/ does not exist." This creates a gap: empty `previous_runs/` causes both Phase 0a and 0b to skip with no warning.

### Requirements pipeline contracts

15. [METHOD] Requirements pipeline Phase A (contract extraction) must cover all source files within scope. For standard projects (≤300 source files), all files must be read.

16. [METHOD] Requirements pipeline Phase B (derivation): each requirement must include Summary, User story (with "so that" clause), Implementation note, Conditions of satisfaction, Alternative paths, References, Doc source (with authority tier), and Specificity classification.

17. [METHOD] REQUIREMENTS.md must begin with a human-readable project overview that names the project, ecosystem role, actors, and highest-risk areas.

18. [INVARIANT] Use case identifiers use format UC-NN. Requirement identifiers use format REQ-NNN. These must be consistent across all artifacts.

19. [INVARIANT] COVERAGE_MATRIX.md must have one row per requirement (REQ-001, REQ-002, etc.) — not grouped ranges.

20. [CONFIG] Architectural-guidance requirements: maximum 3. If count exceeds 3, each excess requirement must be either reclassified as specific (with testable conditions) or given explicit justification.

### Exploration contracts

21. [METHOD] Open exploration stage must produce at least 8 concrete bug hypotheses with file paths and line numbers. At least 4 must reference different modules or subsystems.

22. [METHOD] Pattern-driven exploration: evaluate all 6 patterns from `references/exploration_patterns.md`. Select 3–4 for full deep dives. Remaining patterns get a "SKIP" note with codebase-specific rationale.

23. [INVARIANT] Candidate Bugs section must contain at least 4 prioritized bugs with file:line references. At least 2 must originate from open exploration or quality risks. At least 1 must originate from a pattern deep dive.

24. [METHOD] Write exploration findings incrementally to disk, not batch at the end. Each subsystem's findings must be appended before moving to the next subsystem.

---

## quality_gate.sh (28 contracts)

### JSON validation helper contracts

25. [METHOD] `json_has_key(file, key)`: returns exit 0 if the pattern `"key"` appears anywhere in the file; exit 1 otherwise. Uses `grep -q`. Does NOT verify the key appears as an actual JSON key (preceding `:`).

26. [ERROR] `json_has_key` returns exit 1 for both "file does not exist" and "key not found" — these conditions are indistinguishable from the caller.

27. [ERROR] `json_has_key` returns exit 0 (false positive) when the key name appears in a string VALUE rather than as a JSON key. Example: `{"msg": "the 'id' field"}` passes `json_has_key "id"`.

28. [METHOD] `json_str_val(file, key)`: extracts a string value using `grep -o "\"key\"[[:space:]]*:[[:space:]]*\"[^\"]*\""`. Returns empty string for: key absent, key with non-string value (number/bool/null/object), file absent.

29. [ERROR] `json_str_val` cannot distinguish "key absent" from "key with non-string value" — both return empty string. Error messages generated by callers will be inaccurate for non-string values.

30. [METHOD] `json_key_count(file, key)`: counts all occurrences of `"key":` pattern in the file using `grep -c`. Returns 0 on error.

31. [ERROR] `json_key_count` counts matches in string values as well as actual JSON keys — the same false-positive issue as `json_has_key`, but quantitative.

### Gate execution contracts

32. [CONFIG] STRICTNESS mode: `"benchmark"` (default, strict — failures cause GATE FAILED) vs. `"general"` (warnings-only). Controlled by `--benchmark`/`--general` flags.

33. [CONFIG] `CHECK_ALL` flag: when true, the script resolves repos from SCRIPT_DIR+VERSION rather than command-line arguments. Activated by `--all`.

34. [METHOD] `fail(msg)`: increments global `$FAIL` counter, prints `[FAIL] msg`. Always returns exit 0.

35. [METHOD] `pass(msg)`: prints `[PASS] msg`. Does not modify global counters. Always returns exit 0.

36. [METHOD] `warn(msg)`: increments global `$WARN` counter, prints `[WARN] msg`. Always returns exit 0.

37. [ERROR] All of `fail()`, `pass()`, `warn()` return exit code 0. Return code cannot be used to distinguish outcomes — callers must read global counters.

### Repo resolution contracts

38. [METHOD] Primary path: checks `"$name/quality"` (with `/quality` suffix); adds just `"$name"` to resolved list. Validates more strictly than fallbacks.

39. [METHOD] Fallback 1: checks `"${SCRIPT_DIR}/${name}-${VERSION}"` (without `/quality` suffix); adds the constructed path. Silently produces a wrong match when VERSION is empty (path becomes `${SCRIPT_DIR}/${name}-`).

40. [METHOD] Fallback 2: checks `"${SCRIPT_DIR}/${name}"` (without `/quality` suffix). No version suffix.

41. [ERROR] Array reconstruction at line 697: `REPO_DIRS=(${resolved[@]+"${resolved[@]}"})`. The outer expansion is unquoted, causing word-splitting on paths with spaces. This corrupts the array for any repo path containing a space character.

42. [INVARIANT] After array reconstruction, `check_repo` is called with `"${REPO_DIRS[@]}"` (correctly quoted). But the array itself was corrupted by line 697 before this call.

43. [ERROR] When `CHECK_ALL=true` and VERSION is empty (auto-detection failed), the glob `*-"${VERSION}"/` becomes `*-/`, matching nothing. This causes zero repos to be checked. The empty-array guard at line 700 triggers the usage message.

### TDD log validation contracts

44. [METHOD] Bug IDs are extracted from BUGS.md headings using `grep -oE 'BUG-[0-9]+'`. This extraction is format-agnostic — it matches BUG-NNN regardless of heading level (`##` or `###`).

45. [ERROR] `bug_count` (line 197) uses a format-aware count (correct `### BUG-NNN` headings only), but `bug_ids` (line 313) uses format-agnostic extraction. When headings are malformed (wrong level), `bug_count` may be 0 while `bug_ids` still contains IDs, causing TDD log checks to run against what the counter thinks is a zero-bug run.

46. [METHOD] Date validation: checks ISO 8601 format (regex), checks for placeholder strings, checks that date is not in the future using lexicographic string comparison `[[ "$date" > "$today" ]]`. This works correctly for YYYY-MM-DD format only.

47. [ERROR] If date format validation is ever loosened (e.g., to accept YYYY/MM/DD), the `>` string comparison for future-date detection would silently produce wrong results.

### Functional test detection contract

48. [METHOD] Functional test detection at lines 123-126 uses `ls ${q}/test_functional.* ${q}/FunctionalSpec.* ...`. The glob is unquoted and the `&>/dev/null 2>&1` pattern is redundant (`&>` already redirects both streams).

49. [ERROR] Language detection at lines 449-454 uses `find` with `-print -quit` — robust. Functional test detection uses raw `ls` glob — fragile. Two different approaches for similar file-detection tasks create inconsistency.

50. [CONFIG] Script uses `set -uo pipefail` but NOT `set -e`. Individual command failures are not fatal. The `|| echo 0` fallback on grep commands is required because without `-e`, failed greps continue silently.

51. [ERROR] Without `set -e`, a failed `find` command in a subshell (e.g., permissions error) produces empty or partial output that subsequent arithmetic silently uses as 0.

52. [INVARIANT] `quality/mechanical/verify.sh` is checked conditionally (lines 543-559). The gate passes in benchmark mode only if the script exists and exits 0. In general mode, absence is a warning, not a failure.

---

## Contract coverage summary

| Source | Contracts | Categories |
|--------|-----------|------------|
| SKILL.md | 24 | INVARIANT, METHOD, CONFIG, LIFECYCLE, ERROR |
| quality_gate.sh | 28 | METHOD, ERROR, CONFIG, INVARIANT |
| **Total** | **52** | |
