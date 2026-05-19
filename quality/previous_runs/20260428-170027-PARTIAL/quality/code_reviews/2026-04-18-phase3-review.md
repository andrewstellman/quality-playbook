# Code Review — Quality Playbook v1.4.5 Bootstrap Self-Audit
Date: 2026-04-18
Reviewers: Quality Playbook Phase 3 (bootstrap self-audit)
Scope: `bin/benchmark_lib.py` (350 lines), `bin/run_playbook.py` (1025 lines), `.github/skills/quality_gate/quality_gate.py` (1141 lines)

---

## Pass 1: Structural Review

Each observation records: file:line, observation, suspected defect class, proof path.

### benchmark_lib.py — Structural Observations

**OBS-01** `benchmark_lib.py:37`
`VERSION_PATTERN` accepts both bare `version:` and bold `**Version:**` forms via regex (`re.IGNORECASE`). The regex is correct and complete.
Suspected class: None (correct implementation). Proof: pattern `r"^\s*(?:version:|\*\*Version:\*\*)\s*([0-9]+(?:\.[0-9]+)+)\b"` covers both forms.

**OBS-02** `benchmark_lib.py:74-81` (`_read_version`)
Uses `VERSION_PATTERN.match(line)` — correctly delegates to the regex. Returns the captured group on match.
Suspected class: None (correct path). Proof: pattern match is case-insensitive.

**OBS-03** `benchmark_lib.py:90-116` (`skill_version`)
Uses `stripped.startswith("version:")` — case-sensitive, no regex. Misses the `**Version:**` bold form that `_read_version` handles. This function and `_read_version` are out of sync.
Suspected class: Logic error — version-parser divergence. CB-1 / BUG-001.
Proof: SKILL.md bold form `**Version:** 1.4.5` → `stripped = "**Version:** 1.4.5"` → `startswith("version:")` → False → loop continues until EOF → returns None.

**OBS-04** `benchmark_lib.py:39-43` (`SKILL_INSTALL_LOCATIONS`)
Tuple has 3 entries. SKILL.md §Locating reference files (lines 48-55) documents 4 install paths; `quality_gate.py:969-976` encodes all 4. The path `.github/skills/quality-playbook/SKILL.md` is absent from the library.
Suspected class: Incomplete closed-set — missing fourth install location. CB-2 / BUG-002.
Proof: `tuple` has indices 0-2; `quality_gate.py` has indices 0-3.

**OBS-05** `benchmark_lib.py:177-182` (`PROTECTED_PREFIXES`)
The tuple contains `"quality/"`, `"control_prompts/"`, `"previous_runs/"`, `"docs_gathered/"`. `AGENTS.md`, a SKILL.md-required artifact (lines 106, 122), lives at the project root and is not covered by any prefix.
Suspected class: Missing prefix — required artifact unprotected. CB-5 / BUG-005.
Proof: `"AGENTS.md".startswith(prefix)` is False for all four entries.

**OBS-06** `benchmark_lib.py:185-196` (`_parse_porcelain_path`)
After stripping arrow `->` (rename) the remainder is returned with `rest.strip()`. Git quotes paths with spaces: `' M "file name.md"'` → `rest = '"file name.md"'` → returned verbatim including quotes. Downstream `git checkout -- "file name.md"` fails because the shell receives the literal quote characters.
Suspected class: String handling — quoted paths passed raw. BUG-015.
Proof: `' M "file name.md"'[3:] = '"file name.md"'`; no quote-stripping code present.

**OBS-07** `benchmark_lib.py:204-250` (`cleanup_repo`)
Calls `_is_protected(path)` for each modified file before reverting. The protected check is prefix-based only; `AGENTS.md` passes through unprotected.
Suspected class: Consequence of BUG-005.
Proof: follows from OBS-05.

**OBS-08** `benchmark_lib.py:106`
`skill_version` uses `stripped.lstrip()` → `startswith("version:")`. The comparison is case-sensitive. A SKILL.md frontmatter with `Version: 1.4.5` (capital V but no bold markers) would also be silently rejected; only lowercase `version:` passes.
Suspected class: Hardening gap (case-sensitivity). Subissue of BUG-001.
Proof: `"Version: 1.4.5".startswith("version:")` → False.

### run_playbook.py — Structural Observations

**OBS-09** `run_playbook.py:451-457` (`check_phase_gate`, phase "2")
Threshold is 80 with `GATE WARN` — neither the number nor the severity matches SKILL.md:906 which mandates 120 and FAIL.
Suspected class: Threshold drift + severity mismatch. CB-3 / BUG-003.
Proof: `if line_count < 80: messages.append("GATE WARN ...")` → 85-line file passes silently.

**OBS-10** `run_playbook.py:459-463` (`check_phase_gate`, phase "3")
Checks only 4 artifacts: `REQUIREMENTS.md`, `QUALITY.md`, `CONTRACTS.md`, `RUN_CODE_REVIEW.md`. Phase 2 produces 9 required `.md` files plus functional tests. The gate is severely underspecified.
Suspected class: Incomplete gate — missing 5+ artifacts. CB-6 / BUG-006.
Proof: `["REQUIREMENTS.md", "QUALITY.md", "CONTRACTS.md", "RUN_CODE_REVIEW.md"]` — only 4 names checked.

**OBS-11** `run_playbook.py:560-562` (`docs_present`)
Uses `any(docs_dir.iterdir())`. `.DS_Store` alone satisfies the `any()` call, returning True. The documentation is not validated for content, extension, or non-zero size.
Suspected class: False-positive — noise files accepted. CB-7 / BUG-007.
Proof: `docs_gathered/.DS_Store` → `any(iterdir())` → True.

**OBS-12** `run_playbook.py:565-576` (`archive_previous_run`)
Sequence: `copytree(quality_dir, archive_dir)` → `rmtree(quality_dir)` → `rmtree(control_prompts_dir)`. Non-atomic: crash between steps 1 and 2 leaves both source and archive intact. Also, `control_prompts/` is deleted (step 3) rather than archived alongside `quality/`.
Suspected class: Non-atomic operation + lost diagnostic data. CB-4 / BUG-004.
Proof: Lines 573-576 shown; no temp dir, no rename (atomic POSIX move).

**OBS-13** `run_playbook.py:808-829` (`_pkill_fallback`)
Pattern list: `["bin/run_playbook.py", "claude -p", "claude --model"]`. Missing `"gh copilot -p"`. Copilot workers are orphaned after parent crash.
Suspected class: Incomplete kill pattern — copilot workers escape. CB-9 / BUG-009.
Proof: pattern list has 3 entries; no `gh copilot` string.

**OBS-14** `run_playbook.py:930-946` (`execute_run`, parallel path)
`print_suggested_next_command(args)` is called unconditionally when `failures > 0`. The signature `print_suggested_next_command(args)` takes no failure-count parameter, so it cannot suppress or reword the suggestion.
Suspected class: Missing control flow — failure-blind suggestion. CB-8 / BUG-008.
Proof: `if not suppress_suggestion: print_suggested_next_command(args)` — no `failures` guard.

**OBS-15** `run_playbook.py:217`
`version = lib.skill_version() if _is_bare_name(raw) else None`. When `skill_version()` returns None (because SKILL.md uses bold form), the subsequent error at line 234 says only "is not a directory" — no diagnostic that the version parser returned None and the version-append fallback was skipped.
Suspected class: Poor diagnostic — user cannot distinguish parser failure from path miss. REQ-005 / BUG-013 adjacency.
Proof: `run_playbook.py:234` emits generic message; no branch on `version is None`.

**OBS-16** `run_playbook.py:579-595` (`final_artifact_gaps`)
This function correctly checks 10 artifacts plus functional test existence. The Phase 3 gate (OBS-10) does not call or mirror this function. There is a gap between what the end-of-run checker verifies and what the Phase 3 entry gate requires.
Suspected class: Gate-gap asymmetry (consequence of BUG-006).
Proof: `check_phase_gate("3")` checks 4 files; `final_artifact_gaps` checks 10+.

**OBS-17** `run_playbook.py:486-494` (`command_for_runner`)
`command_for_runner("copilot", ...)` constructs `["gh", "copilot", "--yolo", ...]`. The runner correctly includes `--yolo` for copilot. No issues found here.
Suspected class: None (correct). Proof: copilot subcommand list present.

**OBS-18** `run_playbook.py:29-77`
`ALL_STRATEGIES = ["gap", "unfiltered", "parity", "adversarial"]` — correct; matches SKILL.md iteration reference. No drift.
Suspected class: None (correct). Proof: matches iteration.md §8-16.

**OBS-19** `run_playbook.py:161`
Phase set `VALID_PHASES = frozenset(["1","2","3","4","5","6"])` — correct. Six phases.
Suspected class: None (correct). Proof: Phase numbering consistent with SKILL.md.

### quality_gate.py — Structural Observations

**OBS-20** `quality_gate.py:156-173` (`validate_iso_date`)
Regex `\d{4}-\d{2}-\d{2}` is date-only. Full ISO 8601 datetime `2026-04-18T23:43:14Z` fails `re.fullmatch`, returns `"bad_format"`. Run-metadata sidecar `start_time` uses datetime form (SKILL.md:187).
Suspected class: Regex mismatch — datetime rejected. BUG-014.
Proof: `re.fullmatch(r"\d{4}-\d{2}-\d{2}", "2026-04-18T23:43:14Z")` → None → returns `"bad_format"`.

**OBS-21** `quality_gate.py:182-191` (`detect_skill_version`)
Uses `if "version:" in line` — substring anywhere on the line, no anchoring. A YAML key `description: "The version: 1.4.5 release"` matches before the real `version:` line is reached.
Suspected class: Substring match — false positive on description fields. BUG-013.
Proof: `"version:" in 'description: "version: 1.4.5 release"'` → True.

**OBS-22** `quality_gate.py:310-313` (EXPLORATION.md check in `check_file_existence`)
Only verifies that `EXPLORATION.md` exists. Does not parse the file for required section titles (`## Open Exploration Findings`, `## Quality Risks`, etc.) mandated by SKILL.md:914-929.
Suspected class: Insufficient check — structure ungated. CB-11 / BUG-011.
Proof: `if (q / "EXPLORATION.md").is_file(): pass_("EXPLORATION.md exists")` — no content parsing.

**OBS-23** `quality_gate.py:353-411` (`check_bugs_heading`, zero-bug sentinel)
`re.search(r"(No confirmed|zero|0 confirmed)", bugs_content)` — the word "zero" matches anywhere in prose. A BUGS.md reading "the zero analysis shows no problems" (with actual BUG headings missing) passes the zero-bug path.
Suspected class: Loose regex — free prose accepted as structured sentinel. CB-12 / BUG-012.
Proof: `re.search(r"(No confirmed|zero|0 confirmed)", "the zero analysis")` → match.

**OBS-24** `quality_gate.py:1027-1053` (`check_repo`)
Calls: `check_file_existence`, `check_bugs_heading`, `check_tdd_sidecar`, `check_tdd_logs`, `check_integration_sidecar`, `check_recheck_sidecar`, `check_use_cases`, `check_test_file_extension`, `check_terminal_gate`, `check_mechanical`, `check_patches`, `check_writeups`, `check_version_stamps`, `check_cross_run_contamination`. No call to `check_run_metadata`. Run-metadata JSON is never validated.
Suspected class: Missing check — entire sidecar class ungated. CB-10 / BUG-010.
Proof: Comment in provided source confirms "# NOTE: no check_run_metadata call here".

**OBS-25** `quality_gate.py:969-976` (install locations in gate)
Gate's local list has 4 entries including `.github/skills/quality-playbook/SKILL.md`. Library's `SKILL_INSTALL_LOCATIONS` has 3. These two closed sets diverge.
Suspected class: Consequence of BUG-002 — cross-module closed-set drift.
Proof: Count mismatch; gate's fourth entry absent in library.

---

## Pass 2: Requirement Verification

Each requirement is checked against the actual implementation. Evidence is drawn from the source code sections provided.

### REQ-001: Single canonical version-parser helper
**Verdict: VIOLATED**
`benchmark_lib._read_version` (line 74) uses `VERSION_PATTERN.match(line)` — correct. `benchmark_lib.skill_version` (line 106) uses case-sensitive `startswith("version:")` — misses bold form. `quality_gate.detect_skill_version` (line 182) uses substring `if "version:" in line` — no anchoring. Three parsers; three different behaviors. None delegate to `VERSION_PATTERN`.
Evidence: `stripped.startswith("version:")` at line 106 vs `VERSION_PATTERN.match(line)` at line 76.
→ **BUG-001** (HIGH)

### REQ-002: SKILL_INSTALL_LOCATIONS covers four paths
**Verdict: VIOLATED**
`SKILL_INSTALL_LOCATIONS` at lines 39-43 is a 3-tuple. Missing: `Path(".github") / "skills" / "quality-playbook" / "SKILL.md"`. SKILL.md:48-55 documents 4 paths; gate encodes 4.
Evidence: `SKILL_INSTALL_LOCATIONS = (Path(".github") / "skills" / "SKILL.md", Path(".claude") / "skills" / "quality-playbook" / "SKILL.md", Path("SKILL.md"),)` — 3 entries.
→ **BUG-002** (HIGH)

### REQ-003: Version parsers reject substring-only matches
**Verdict: VIOLATED**
`quality_gate.detect_skill_version` uses `if "version:" in line` — matches substring anywhere. `benchmark_lib._read_version` correctly uses `VERSION_PATTERN.match(line)` (anchored). `skill_version` uses `startswith("version:")` which is substring-at-start but not a full-line anchor. Only `_read_version` is fully correct.
Evidence: `if "version:" in line:` at `quality_gate.py:184` — no anchoring.
→ **BUG-013** (MEDIUM)

### REQ-004: Phase 1 line-count gate enforces 120 as FAIL
**Verdict: VIOLATED**
`check_phase_gate("2")` at line 455-457 uses threshold 80 with `GATE WARN` message. SKILL.md:906 requires 120 and FAIL.
Evidence: `if line_count < 80: messages.append(f"GATE WARN Phase 2: EXPLORATION.md is only {line_count} lines (expected 80+)")` — number is wrong (80 vs 120) and severity is wrong (WARN vs FAIL).
→ **BUG-003** (HIGH)

### REQ-005: Diagnostic for skipped version-append fallback
**Verdict: VIOLATED**
`run_playbook.py:217` computes `version = lib.skill_version() if _is_bare_name(raw) else None`. When `skill_version()` returns None, the error at line 234 says only `"{path} is not a directory"` with no mention that the version parser returned None or that the version-append fallback was skipped/attempted.
Evidence: Generic error message at line 234; no `version is None` branch.
→ **BUG-005** consequence; related to BUG-001.

### REQ-006: AGENTS.md is protected from silent cleanup reversion
**Verdict: VIOLATED**
`PROTECTED_PREFIXES` (line 177-182) has 4 entries; none cover `AGENTS.md`. The `_is_protected("AGENTS.md")` function returns False. Any tracked `AGENTS.md` modification is silently reverted by `cleanup_repo`.
Evidence: `any("AGENTS.md".startswith(p) for p in PROTECTED_PREFIXES)` → False.
→ **BUG-005** (MEDIUM)

### REQ-007: ISO 8601 validation matches field grammar
**Verdict: VIOLATED**
`validate_iso_date` uses `re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str)` — date-only. ISO 8601 datetimes like `2026-04-18T23:43:14Z` return `"bad_format"`. Run-metadata `start_time` / `end_time` fields use datetime form.
Evidence: `re.fullmatch(r"\d{4}-\d{2}-\d{2}", "2026-04-18T23:43:14Z")` → None → `"bad_format"`.
→ **BUG-014** (MEDIUM)

### REQ-008: check_run_metadata enforces run-metadata artifact
**Verdict: VIOLATED**
`check_repo` (lines 1027-1053) never calls `check_run_metadata`. No such function exists anywhere in `quality_gate.py`. Run-metadata JSON goes entirely unvalidated.
Evidence: Source comment: `# NOTE: no check_run_metadata call here`. `hasattr(quality_gate, "check_run_metadata")` → False.
→ **BUG-010** (LOW)

### REQ-009: archive_previous_run is atomic and preserves control_prompts
**Verdict: VIOLATED**
`archive_previous_run` (lines 565-576): (1) copies to archive then removes source — non-atomic, crash leaves both; (2) calls `rmtree(control_prompts_dir)` (line 576) to delete rather than archive `control_prompts/`.
Evidence: Lines 573-576: `shutil.copytree(quality_dir, archive_dir)` → `shutil.rmtree(quality_dir)` → `shutil.rmtree(control_prompts_dir)` — delete, not archive.
→ **BUG-004** (HIGH)

### REQ-010: Phase 3/4/5 gates require all prior artifacts
**Verdict: VIOLATED**
`check_phase_gate("3")` (lines 459-463) checks only 4 files. Phase 2 produces 9 `.md` artifacts plus functional tests and run-metadata. Five required artifacts (`COVERAGE_MATRIX.md`, `COMPLETENESS_REPORT.md`, `RUN_INTEGRATION_TESTS.md`, `RUN_SPEC_AUDIT.md`, `RUN_TDD_TESTS.md`) are not checked.
Evidence: `["REQUIREMENTS.md", "QUALITY.md", "CONTRACTS.md", "RUN_CODE_REVIEW.md"]` — 4 items.
→ **BUG-006** (MEDIUM)

### REQ-011: docs_present requires substantive documentation
**Verdict: VIOLATED**
`docs_present` (lines 560-562) uses `any(docs_dir.iterdir())` — True for `.DS_Store` alone or an empty file. No content, extension, or size check.
Evidence: `return docs_dir.is_dir() and any(docs_dir.iterdir())` — `iterdir()` yields `.DS_Store` → `any()` → True.
→ **BUG-007** (MEDIUM)

### REQ-012: Kill-path covers gh copilot workers
**Verdict: PARTIALLY SATISFIED**
`_pkill_fallback` (lines 808-829) has patterns for `bin/run_playbook.py`, `claude -p`, `claude --model`. Missing: `gh copilot -p`. Copilot workers are not killed by the fallback.
Evidence: `patterns = ["bin/run_playbook.py", "claude -p", "claude --model"]` — 3 entries; no `gh copilot`.
→ **BUG-009** (MEDIUM)

### REQ-013: quality_gate.py parses EXPLORATION.md for section titles
**Verdict: VIOLATED**
`check_file_existence` at lines 310-313 verifies existence only. No section-title parsing. An EXPLORATION.md missing `## Quality Risks` passes the gate.
Evidence: `if (q / "EXPLORATION.md").is_file(): pass_("EXPLORATION.md exists")` — existence check only.
→ **BUG-011** (LOW)

### REQ-014: Suggestion suppressed on run failure
**Verdict: VIOLATED**
`execute_run` (lines 930-946) calls `print_suggested_next_command(args)` unconditionally when `not suppress_suggestion`. The function has no failure-count parameter and cannot branch on failure.
Evidence: `if not suppress_suggestion: print_suggested_next_command(args)` — no `failures` guard.
→ **BUG-008** (MEDIUM)

### REQ-015: Zero-bug sentinel uses anchored structure
**Verdict: VIOLATED**
`check_bugs_heading` uses `re.search(r"(No confirmed|zero|0 confirmed)", bugs_content)`. The word "zero" matches free prose.
Evidence: `re.search(r"(No confirmed|zero|0 confirmed)", "the zero analysis shows no problems")` → match.
→ **BUG-012** (LOW)

### REQ-016: _parse_porcelain_path handles quoted paths
**Verdict: VIOLATED**
`_parse_porcelain_path` (lines 185-196) returns `rest.strip()` without removing Git's surrounding double-quotes. `' M "file name.md"'` → `'"file name.md"'` with quotes intact.
Evidence: No quote-stripping code in function body; returns `rest.strip()` only.
→ **BUG-015** (MEDIUM)

### REQ-017: Shared canonical source for closed sets
**Verdict: PARTIALLY SATISFIED**
`benchmark_lib.py` declares `SKILL_INSTALL_LOCATIONS` (3 entries) and `PROTECTED_PREFIXES` (4 entries). `quality_gate.py` re-declares install locations (4 entries) inline. `run_playbook.py` declares `ALL_STRATEGIES` and `VALID_PHASES` independently. No single canonical import exists. Drift is already present (BUG-002).
Evidence: Three separate source files with overlapping closed sets; no shared constants module.

---

## Pass 3: Cross-Requirement Consistency

### Interaction Pattern 1: Version Parser Divergence (REQ-001 × REQ-003 × REQ-002)

REQ-001 requires a single canonical parser. REQ-003 requires anchored matching. REQ-002 requires 4 install locations. These three interact: when `skill_version()` (the bare-name fallback path in `run_playbook.py:217`) returns None because SKILL.md uses the bold form, `resolve_target_dirs` silently skips the version-append fallback — so users with SKILL.md installed at `.github/skills/quality-playbook/SKILL.md` (the missing fourth path) get both BUG-001 (parser failure) and BUG-002 (path not tried) simultaneously. The combined failure produces a cryptic "not a directory" error with no diagnostic. REQ-005's diagnostic requirement (BUG-013 adjacent) compounds this: the error message doesn't even acknowledge the parser was involved.

Code evidence:
- `benchmark_lib.py:106`: `stripped.startswith("version:")` — bold form returns None
- `run_playbook.py:217`: `version = lib.skill_version() if _is_bare_name(raw) else None` — None propagates
- `run_playbook.py:234`: generic error emitted — no mention of parser failure

### Interaction Pattern 2: Archive + Protected Prefix Inconsistency (REQ-009 × REQ-006)

REQ-009 requires `control_prompts/` to be archived. REQ-006 requires `AGENTS.md` to survive cleanup. These interact: `archive_previous_run` (BUG-004) deletes `control_prompts/` (line 576) instead of archiving it. However, `PROTECTED_PREFIXES` (BUG-005) lists `control_prompts/` as protected — so `cleanup_repo` will refuse to revert files under `control_prompts/` during the session, but then `archive_previous_run` destroys the directory at the end of the run anyway. The protection is invalidated by the non-atomic archive. Additionally, `AGENTS.md` (not in `PROTECTED_PREFIXES`) is reverted mid-session by `cleanup_repo` before the archive even runs — a different failure mode that compounds with the archive loss.

Code evidence:
- `benchmark_lib.py:177-182`: `control_prompts/` is protected
- `run_playbook.py:576`: `shutil.rmtree(control_prompts_dir)` — deletes the protected directory
- `benchmark_lib.py:177-182`: `AGENTS.md` not in list → `_is_protected("AGENTS.md")` → False

### Interaction Pattern 3: Gate Checks vs Runner Gates (REQ-010 × REQ-013 × REQ-008)

REQ-010 requires Phase 3/4/5 gates to enforce all prior artifacts. REQ-013 requires EXPLORATION.md structure to be gated. REQ-008 requires run-metadata to be gated. These interact to produce a compounded ungated zone: the Phase 3 runner gate (BUG-006) checks only 4 artifacts; `check_file_existence` (BUG-011) checks EXPLORATION.md existence but not structure; `check_repo` (BUG-010) never calls `check_run_metadata`. A run can produce a thin EXPLORATION.md missing required sections, skip five Phase 2 artifacts, and omit the run-metadata JSON entirely — and pass both the runner gate and the quality gate without a single FAIL. The three bugs compose into a gap where the most critical structural defects in a run go undetected by all mechanical guards.

Code evidence:
- `run_playbook.py:459-463`: only 4 files checked
- `quality_gate.py:310-313`: existence only for EXPLORATION.md
- `quality_gate.py:1027-1053`: no `check_run_metadata` call

### Interaction Pattern 4: Closed-Set Drift (REQ-017 × REQ-002 × REQ-012)

REQ-017 requires a single canonical source for all closed sets. REQ-002 reveals a 3-vs-4 drift in install locations between `benchmark_lib.py` and `quality_gate.py`. REQ-012 reveals the kill pattern list is missing `gh copilot -p`. These are independent manifestations of the same architectural failure: closed sets are declared in multiple places and drift apart silently. The mechanical `verify.sh` checks some closed sets (strategies, protected prefixes, verdict enum) but does not diff install locations against SKILL.md. Adding the fourth install location to `benchmark_lib.py` would reduce the drift between library and gate, but without a single-source architecture (REQ-017), the next SKILL.md update will create new drift. BUG-002 and BUG-009 are both symptoms of this architectural gap.

Code evidence:
- `benchmark_lib.py:39-43`: 3-entry tuple
- `quality_gate.py:969-976`: 4-entry list (inferred from OBS-25 and gate source)
- `run_playbook.py:808-829`: patterns list missing `gh copilot -p`
- `quality/mechanical/verify.sh`: does not diff install-location count against SKILL.md

---

## Combined Summary

All 15 confirmed bugs from the three-pass review:

| BUG | Source | File:Line | Description | Severity | Requirements |
|-----|--------|-----------|-------------|----------|--------------|
| BUG-001 | CB-1 | benchmark_lib.py:106 | `skill_version()` case-sensitive startswith rejects bold form | HIGH | REQ-001 |
| BUG-002 | CB-2 | benchmark_lib.py:39-43 | `SKILL_INSTALL_LOCATIONS` missing 4th path | HIGH | REQ-002 |
| BUG-003 | CB-3 | run_playbook.py:455-457 | Phase 2 gate threshold 80 WARN vs 120 FAIL | HIGH | REQ-004 |
| BUG-004 | CB-4 | run_playbook.py:565-576 | archive_previous_run non-atomic; control_prompts/ deleted | HIGH | REQ-009 |
| BUG-005 | CB-5 | benchmark_lib.py:177-182 | PROTECTED_PREFIXES missing AGENTS.md | MEDIUM | REQ-006 |
| BUG-006 | CB-6 | run_playbook.py:459-463 | Phase 3 gate checks only 4 of 9 required artifacts | MEDIUM | REQ-010 |
| BUG-007 | CB-7 | run_playbook.py:560-562 | docs_present accepts .DS_Store / empty files | MEDIUM | REQ-011 |
| BUG-008 | CB-8 | run_playbook.py:930-946 | Iteration suggestion printed even on failure | MEDIUM | REQ-014 |
| BUG-009 | CB-9 | run_playbook.py:808-829 | _pkill_fallback missing gh copilot -p pattern | MEDIUM | REQ-012 |
| BUG-010 | CB-10 | quality_gate.py:1027-1053 | check_run_metadata never called | LOW | REQ-008 |
| BUG-011 | CB-11 | quality_gate.py:310-313 | EXPLORATION.md only checked for existence, not structure | LOW | REQ-013 |
| BUG-012 | CB-12 | quality_gate.py:397 | Zero-bug sentinel matches "zero" anywhere in prose | LOW | REQ-015 |
| BUG-013 | new | quality_gate.py:182-187 | detect_skill_version uses substring match, no anchor | MEDIUM | REQ-003 |
| BUG-014 | new | quality_gate.py:156-173 | validate_iso_date rejects valid ISO 8601 datetimes | MEDIUM | REQ-007 |
| BUG-015 | new | benchmark_lib.py:185-196 | _parse_porcelain_path returns quoted path with quotes | MEDIUM | REQ-016 |

**Severity distribution:** HIGH: 4, MEDIUM: 7, LOW: 4. Total: 15.

**Modules affected:** `benchmark_lib.py`: 4 bugs (BUG-001, BUG-002, BUG-005, BUG-015); `run_playbook.py`: 6 bugs (BUG-003, BUG-004, BUG-006, BUG-007, BUG-008, BUG-009); `quality_gate.py`: 5 bugs (BUG-010, BUG-011, BUG-012, BUG-013, BUG-014).
