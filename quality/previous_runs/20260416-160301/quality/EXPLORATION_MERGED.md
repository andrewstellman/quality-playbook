# Exploration Findings — Merged (All Iterations)
<!-- Quality Playbook v1.4.1 — Merged Exploration — 2026-04-16 -->

This file merges findings from all iterations. Each section is attributed to its source iteration and strategy.

---

## Domain and Stack

[Iteration 1] See `quality/EXPLORATION.md` §Domain and Stack for full coverage.

**Summary:** AI quality engineering tooling. SKILL.md (2239 lines, Markdown) is the primary product. Supporting script: Bash (quality_gate.sh, 723 lines). No build system, no package manifest, no external dependencies.

---

## Architecture

[Iteration 1] See `quality/EXPLORATION.md` §Architecture for full coverage.

**Summary:** Five main components: SKILL.md (primary product), quality_gate.sh (mechanical validator), references/ (12 reference files), ai_context/ (2 context files), version history.

---

## Open Exploration Findings

### [Iteration 1] Findings 1–10

Full coverage in `quality/EXPLORATION.md` §Open Exploration Findings.

Key findings from Iteration 1:
- Finding 1: quality_gate.sh:697 — unquoted array expansion (→ BUG-H2)
- Finding 2: quality_gate.sh:88-91 — json_key_count false positives (→ BUG-H1)
- Finding 3: quality_gate.sh:123-126 — functional test ls-glob (→ BUG-M8)
- Finding 4: SKILL.md Phase 2 gate vs Phase 1 gate (→ BUG-M3)
- Finding 5: SKILL.md mechanical verification ambiguity
- Finding 6: SKILL.md Mandatory First Action vs autonomous mode (→ BUG in REQ-008)
- Finding 7: quality_gate.sh:278-283 — date comparison uses string lexicographic comparison
- Finding 8: SKILL.md gate self-check temporal paradox
- Finding 9: quality_gate.sh — set -e missing
- Finding 10: SKILL.md version stamp mid-run upgrade scenario

### [Iteration 2: gap] Findings 1–10

Full coverage in `quality/EXPLORATION_ITER2.md`.

Key findings from Iteration 2 (Gap):
- Gap Finding 1: quality_gate.sh:479 — ls-glob in test file extension check (→ CAND-G1)
- Gap Finding 2: quality_gate.sh:143 — ls-glob in code_reviews directory check (→ CAND-G2)
- Gap Finding 3: references/review_protocols.md:410 — wrong recommendation enum (→ CAND-G3)
- Gap Finding 4: SKILL.md:1965 — recheck schema_version "1.0" inconsistency (reconfirms BUG-L10)
- Gap Finding 5: quality_gate.sh — no validation for recheck-results.json (→ CAND-G4)
- Gap Finding 6: SKILL.md:1108 — code review summary uses different recommendation vocabulary
- Gap Finding 7: SKILL.md Phase 7 — iteration vs baseline end-of-phase message ambiguity
- Gap Finding 8: TOOLKIT.md:182 — phase count stale (6 vs 8 phases)
- Gap Finding 9: quality_gate.sh:331 — BUG-M8 scope verification (already in BUG-M8)
- Gap Finding 10: Confirming line 479 is a NEW bug, separate from BUG-M8

---

## Quality Risks

### [Iteration 1] Risks 1–7

Full coverage in `quality/EXPLORATION.md` §Quality Risks.

Key risks:
- Risk 1 (HIGH): JSON validation false positives (→ BUG-H1)
- Risk 2 (HIGH): Version cross-reference 20+ locations (→ BUG-L7)
- Risk 3 (HIGH): Artifact contract table vs gate drift (→ BUG-M4, CAND-G4)
- Risk 4 (MEDIUM): --all mode with empty VERSION
- Risk 5 (MEDIUM): Phase 0b and self-audit context
- Risk 6 (MEDIUM): Incremental write vs re-read tension
- Risk 7 (MEDIUM): TDD log validation ordering

### [Iteration 2: gap] New Risk

**Risk 8 (MEDIUM):** references/review_protocols.md template uses stale recommendation enum values that produce gate-failing artifacts.

---

## Pattern Applicability Matrix

### [Iteration 1]

| Pattern | Decision |
|---------|----------|
| Fallback and Degradation Path Parity | FULL |
| Dispatcher Return-Value Correctness | FULL |
| Cross-Implementation Contract Consistency | FULL |
| Enumeration and Representation Completeness | SKIP |
| API Surface Consistency | SKIP |
| Spec-Structured Parsing Fidelity | SKIP |

---

## Pattern Deep Dives

### [Iteration 1] All three deep dives

Full coverage in `quality/EXPLORATION.md` §Pattern Deep Dives.

### [Iteration 2: gap] Cross-implementation consistency extension

Gap exploration applied Cross-Implementation Contract Consistency to previously uncovered contracts:
- SKILL.md integration-results.json schema (File 4 section) vs references/review_protocols.md template
- quality_gate.sh recommendation enum check vs SKILL.md's valid values
- quality_gate.sh ls-glob at line 479 vs find-based detection at lines 486–495

### [Iteration 4: parity] Cross-path comparison and diffing

Parity strategy — 6 parallel groups, 10 pairwise comparisons, 6 discrepancy findings. Key new areas explored:
- json_has_key vs json_key_count — same logical purpose (is key present?), different matching semantics; json_key_count uses colon-anchor (stronger), json_has_key does not (weaker, already BUG-H1). Summary sub-key check at lines 259-265 uses the weaker validator while per-bug check at lines 241-248 uses the stronger one.
- Writeup counting (ls glob at line 595, vulnerable) vs writeup content validation (loop with `[ -f ]` guard at lines 598-603, immune) — two parallel paths on same resource with inconsistent detection methods producing contradictory results under nullglob
- TDD log check (per-bug iteration, lines 316-345) vs patch check (aggregate count, lines 562-588) — same contract but different enforcement rigor; per-bug iteration can detect wrong-set; aggregate count cannot
- Phase 5 has no entry gate for Phase 4 artifacts (triage + auditor files), unlike Phase 2 which has an explicit entry gate for Phase 1 artifacts. Pattern inconsistency: fail-early at Phase 2, fail-late at Phase 5.
- SEED_CHECKS.md required by Phase 5 artifact file-existence gate (SKILL.md:1641) but absent from canonical artifact contract table (SKILL.md:88-119) and not checked by quality_gate.sh

### [Iteration 3: unfiltered] Pure domain-driven exploration

Unfiltered strategy — 20 concrete findings with file:line references. Key new areas explored:
- quality_gate.sh:124 — functional test file existence check (ls-glob vulnerability, line not in BUG-M8 fix scope)
- quality_gate.sh:184,313 — BUGS.md heading regex `BUG-[0-9]+` never matches QFB severity-prefix format (`BUG-H1`), causing 100% bypass of TDD/patch/writeup validation
- quality_gate.sh:293-298 vs 307-387 — `red_phase`/`green_phase` JSON values never cross-validated against log file first-line tags
- SKILL.md:1615 vs quality_gate.sh:184 — spec example says `BUG-001` format, gate enforces `BUG-[0-9]+`, but QFB generates `BUG-H1` — three-way conflict
- quality_gate.sh:259-265 — summary key check propagates BUG-H1 false positive
- quality_gate.sh:253-255 — wrong field name detector propagates BUG-H1 false positive (self-defeating)
- SKILL.md:1965 — recheck schema case inconsistency (uppercase status values, lowercase summary keys)

---

## Candidate Bugs for Phase 2 (Consolidated — All Iterations)

### [Iteration 1] BUG-H1: `quality_gate.sh:75-78` — json_has_key false positive from string value match
- **Confirmed:** YES (BUG-H1 in BUGS.md)
- **Stage:** Iteration 1 Open Exploration

### [Iteration 1] BUG-H2: `quality_gate.sh:697` — Unquoted array expansion corrupts repo paths with spaces
- **Confirmed:** YES (BUG-H2 in BUGS.md)
- **Stage:** Iteration 1 Open Exploration

### [Iteration 1] BUG-M3: SKILL.md — Phase 2 entry gate enforces only 6 of 12 Phase 1 checks
- **Confirmed:** YES (BUG-M3 in BUGS.md)
- **Stage:** Iteration 1 Pattern Deep Dive

### [Iteration 1] BUG-M4: `quality_gate.sh` — test_regression.* not checked by gate
- **Confirmed:** YES (BUG-M4 in BUGS.md)
- **Stage:** Iteration 1 Pattern Deep Dive

### [Iteration 1] BUG-M5: SKILL.md — Phase 0b skips when previous_runs/ exists but is empty
- **Confirmed:** YES (BUG-M5 in BUGS.md)
- **Stage:** Iteration 1 Pattern Deep Dive

### [Iteration 1] BUG-L6: `quality_gate.sh:81-85` — json_str_val silent empty for non-string values
- **Confirmed:** YES (BUG-L6 in BUGS.md)
- **Stage:** Iteration 1 Pattern Deep Dive

### [Iteration 1] BUG-L7: SKILL.md — Version hardcoded in 8+ locations
- **Confirmed:** YES (BUG-L7 in BUGS.md)
- **Stage:** Iteration 1 Quality Risks

### [Iteration 1, Phase 4 spec audit] BUG-M8: `quality_gate.sh` — systemic nullglob ls-glob counting
- **Confirmed:** YES (BUG-M8 in BUGS.md)
- **Stage:** Iteration 1 Spec Audit

### [Iteration 1, Phase 4 spec audit] BUG-L9: Three incompatible auditor naming formats
- **Confirmed:** YES (BUG-L9 in BUGS.md)
- **Stage:** Iteration 1 Spec Audit

### [Iteration 1, Phase 4 spec audit] BUG-L10: recheck-results.json uses schema_version "1.0"
- **Confirmed:** YES (BUG-L10 in BUGS.md)
- **Stage:** Iteration 1 Spec Audit

### [Iteration 1, Phase 4 spec audit] BUG-L11: Two incompatible tdd-results.json templates
- **Confirmed:** YES (BUG-L11 in BUGS.md)
- **Stage:** Iteration 1 Spec Audit

---

### NEW CANDIDATES FROM ITERATION 2 (gap):

### [Iteration 2: gap] CAND-G1: `quality_gate.sh:479` — ls-glob in test file extension detection produces false non-empty under nullglob
- **File:Line:** `quality_gate.sh:479`
- **Stage:** Iteration 2 Gap Finding 1
- **Hypothesis:** `func_test=$(ls ${q}/test_functional.* 2>/dev/null | head -1)` — under nullglob, the unmatched glob expands to empty, `ls` lists CWD, `head -1` returns a CWD filename. The downstream `if [ -n "$func_test" ]` at line 481 evaluates TRUE spuriously, causing language extension validation to run on a wrong file and produce misleading results.
- **Different from BUG-M8:** BUG-M8's fix patches lines 124, 152-153, 331, 567-568, 595. Line 479 is NOT in BUG-M8's fix scope.
- **Severity:** MEDIUM
- **Code review should inspect:** Line 479 vs. line 486 (find-based language detection in the same function). The inconsistency: fix uses `find` for language detection (line 486) but `ls` for test file detection (line 479) within the same function block.

### [Iteration 2: gap] CAND-G2: `quality_gate.sh:143` — ls-glob in code_reviews directory check produces false pass under nullglob
- **File:Line:** `quality_gate.sh:143`
- **Stage:** Iteration 2 Gap Finding 2
- **Hypothesis:** `[ -n "$(ls ${q}/code_reviews/*.md 2>/dev/null)" ]` — under nullglob, unmatched glob causes ls to list CWD, making the directory appear non-empty. A partial run that creates code_reviews/ but writes no content passes this check.
- **Severity:** MEDIUM
- **Code review should inspect:** Line 143 vs. line 486 (find-based detection). The directory listing check should use `find ${q}/code_reviews -name "*.md" -print -quit | grep -q .` instead.

### [Iteration 2: gap] CAND-G3: `references/review_protocols.md:410` — integration test template uses wrong recommendation enum values
- **File:Line:** `references/review_protocols.md:410`
- **Stage:** Iteration 2 Gap Finding 3
- **Hypothesis:** Template specifies `SHIP IT / FIX FIRST / NEEDS INVESTIGATION` but gate at line 427 requires `SHIP / FIX BEFORE MERGE / BLOCK` and SKILL.md line 1273 specifies the same. An agent following the reference file produces a gate-failing artifact.
- **Severity:** MEDIUM
- **Code review should inspect:** `references/review_protocols.md:410` vs. `quality_gate.sh:427` vs. `SKILL.md:1273`. All three must agree on the canonical enum values.

### [Iteration 2: gap] CAND-G4: `quality_gate.sh` — No validation for recheck-results.json despite documented artifact contract
- **File:Line:** `quality_gate.sh` (entire file — absence finding)
- **Stage:** Iteration 2 Gap Finding 5
- **Hypothesis:** The gate validates every conditional artifact (tdd-results.json, integration-results.json, patches, writeups) but has no section for recheck-results.json. A malformed recheck run produces no gate failures.
- **Severity:** MEDIUM
- **Code review should inspect:** The gate's check function end at ~line 673. Compare SKILL.md artifact contract table (lines 117-118) with gate coverage. The recheck artifacts are missing from gate enforcement.

---

### NEW CANDIDATES FROM ITERATION 3 (unfiltered):

### [Iteration 3: unfiltered] CAND-U1: `quality_gate.sh:124` — Functional test file existence check uses ls-glob vulnerable to nullglob, not covered by any prior fix
- **File:Line:** `quality_gate.sh:124`
- **Stage:** Iteration 3 Unfiltered Finding 1
- **Hypothesis:** `ls ${q}/test_functional.* ${q}/FunctionalSpec.* ${q}/FunctionalTest.* ${q}/functional.test.* &>/dev/null 2>&1` — under nullglob, all four unmatched globs expand to empty, `ls` receives no args, lists CWD, exits 0. Gate passes even when no functional test file exists. This is the FILE EXISTENCE check at line 124 — distinct from BUG-M8 (covers 152-153, 331, 567-568, 595), BUG-M12 (line 479), and BUG-M13 (line 143).
- **Severity:** MEDIUM
- **Code review should inspect:** Line 124 vs. `find`-based pattern used at lines 449-454. Same vulnerability class as confirmed bugs BUG-M8, BUG-M12, BUG-M13.

### [Iteration 3: unfiltered] CAND-U2: `quality_gate.sh:184,313` — BUGS.md heading regex `BUG-[0-9]+` never matches QFB severity-prefix IDs (`BUG-H1`), causing gate to treat all QFB-format runs as zero-bug and skip ALL TDD/patch/writeup validation
- **File:Line:** `quality_gate.sh:184` (heading check) and `quality_gate.sh:313` (bug_ids extraction for log check)
- **Stage:** Iteration 3 Unfiltered Finding 2+3
- **Hypothesis:** `grep -cE '^### BUG-[0-9]+'` at line 184 never matches `### BUG-H1` (severity prefix). Sets `bug_count=0`. `grep -oE 'BUG-[0-9]+'` at line 313 also never matches. All downstream checks gated on `bug_count > 0` (TDD logs, patches, writeups) are silently skipped. This means every QFB self-audit run gets ZERO gate validation on TDD/patch/writeup artifacts. The gate provides false assurance of zero bugs.
- **Severity:** HIGH
- **Code review should inspect:** Line 184 regex `^### BUG-[0-9]+` vs QFB naming convention `BUG-H1`, `BUG-M3`, `BUG-L6`. Cross-reference with SKILL.md:1615 spec example `### BUG-001` vs established naming convention used throughout all generated BUGS.md files.

### [Iteration 4: parity] CAND-P1: `quality_gate.sh:259-265` — Summary sub-key check uses `json_has_key` (weak) while per-bug check uses `json_key_count` (strong)
- **File:Line:** `quality_gate.sh:259-265` (summary check) vs `quality_gate.sh:239-248` (per-bug check)
- **Stage:** Iteration 4 Parity Group PG-1 Comparison 2
- **Hypothesis:** Two parallel required-field checks in the same gate section use validators with different false-positive rates. Summary keys checked with `json_has_key` (matches anywhere in file); per-bug fields checked with `json_key_count` (colon-anchored). The weaker check is applied to the simpler resource (summary has one set of keys) while the stronger check is applied to the complex resource (per-bug fields, where count matters). The structural inconsistency is real even if practical impact is low.
- **Severity:** LOW

### [Iteration 4: parity] CAND-P2: `quality_gate.sh:562-588` — Patch existence uses aggregate count instead of per-bug iteration
- **File:Line:** `quality_gate.sh:562-588` (patch count) vs `quality_gate.sh:316-345` (log per-bug iteration)
- **Stage:** Iteration 4 Parity Group PG-2 Comparison 4
- **Hypothesis:** TDD log section iterates `bug_ids` per bug, verifying each bug has a log. Patch section counts all patches in aggregate. A run with correct total count but wrong distribution (some bugs with multiple patches, some with none) passes the patch section but would fail per-bug log check. Structural inconsistency: same contract ("every confirmed bug must have artifact X") enforced with different rigor.
- **Severity:** LOW

### [Iteration 4: parity] CAND-P3: `SKILL.md:1573` — Phase 5 has no entry gate for Phase 4 artifacts
- **File:Line:** `SKILL.md:1573-1590` vs `SKILL.md:897-907`
- **Stage:** Iteration 4 Parity Group PG-4 Comparison 7
- **Hypothesis:** Phase 2 has a mandatory entry gate that verifies Phase 1 artifacts exist before proceeding. Phase 5 has no equivalent: it reads PROGRESS.md (an agent-maintained text file) but does not mechanically verify triage and auditor files exist. An agent could write "Phase 4: complete" without running the audit, then proceed through Phase 5, only failing at the terminal gate. The fail-early vs fail-late inconsistency between Phase 2 and Phase 5 is a design gap.
- **Severity:** LOW

### [Iteration 4: parity] CAND-P4: `SKILL.md:1641` vs `SKILL.md:88-119` — SEED_CHECKS.md absent from artifact contract table
- **File:Line:** `SKILL.md:1641` (Phase 5 artifact gate) vs `SKILL.md:88-119` (artifact contract table)
- **Stage:** Iteration 4 Parity Group PG-6
- **Hypothesis:** SKILL.md's Phase 5 artifact file-existence gate requires `quality/SEED_CHECKS.md` when Phase 0b runs. The canonical artifact contract table ("This is the canonical list — any artifact not listed here should not be gate-enforced") does NOT include SEED_CHECKS.md. The gate script also does not check for it. An agent reading only the table would not know to create this file. An agent following Phase 5 would fail if the file doesn't exist but would have no table-level guidance about it.
- **Severity:** LOW

### [Iteration 3: unfiltered] CAND-U3: `quality_gate.sh:307-387` — TDD sidecar JSON `red_phase`/`green_phase` values never cross-validated against log file first-line tags
- **File:Line:** `quality_gate.sh:307-387` (log tag validation) and `quality_gate.sh:239-248` (JSON field validation)
- **Stage:** Iteration 3 Unfiltered Finding 9
- **Hypothesis:** Gate validates JSON field `red_phase` for PRESENCE only (not value format). Gate validates log file first-line tag (RED/GREEN/NOT_RUN/ERROR) separately. No check compares them. A tdd-results.json claiming `"red_phase": "pass"` (green result) with a log file showing first line `RED` (red/fail) passes BOTH checks despite the contradiction. This undermines the TDD sidecar-to-log consistency check mandated by SKILL.md line 1589.
- **Severity:** MEDIUM
- **Code review should inspect:** Lines 307-387 (log tag validation) vs lines 239-248 (JSON field presence check). The gate verifies log tags and JSON field presence in separate sections with no cross-reference between them.

---

## Derived Requirements (All Iterations)

### [Iteration 1] REQ-001 through REQ-008

Full coverage in `quality/REQUIREMENTS.md`.

### [Iteration 2: gap] New Requirements

**REQ-015: `quality_gate.sh` test file extension detection must use find, not ls-glob**
- Spec basis: REQ-002 (reliable artifact detection), BUG-M8 fix pattern consistency
- Line 479: `func_test=$(ls ${q}/test_functional.* 2>/dev/null | head -1)` must be replaced with find-based detection

**REQ-016: `quality_gate.sh` code_reviews directory detection must use find, not ls-glob**
- Spec basis: REQ-002, partial session detection
- Line 143: `ls ${q}/code_reviews/*.md 2>/dev/null` must be replaced with find-based detection

**REQ-017: All recommendation enum values must be consistent across spec, reference files, and gate**
- Spec basis: REQ-009 (consistency), internal cross-reference consistency
- `references/review_protocols.md` must use canonical enum values matching SKILL.md:1273 and quality_gate.sh:427

**REQ-018: `quality_gate.sh` must validate recheck-results.json when recheck runs**
- Spec basis: SKILL.md artifact contract table (lines 117-118), benchmark completeness
- Gate must check required fields, valid status enum values, schema_version

### [Iteration 4: parity] New Requirements

**REQ-022: Gate summary sub-key checks must use `json_key_count` for consistency with per-bug field checks**
- Spec basis: Internal gate consistency; same "required JSON field presence" contract should use same enforcement pattern
- Lines 259-265: replace `json_has_key` with `json_key_count` checks > 0

**REQ-023: Patch existence check must iterate per-bug ID, not count aggregates**
- Spec basis: Same contract as TDD log check; every confirmed bug must have a named regression-test patch
- Lines 562-588: replace aggregate count with per-bug iteration matching lines 316-345 pattern

**REQ-024: Phase 5 must include an entry gate verifying Phase 4 artifacts before proceeding**
- Spec basis: Phase 2 entry gate pattern; fail-early is better than fail-late at the terminal gate
- SKILL.md: add mandatory Phase 5 entry gate that checks for triage + auditor files

**REQ-025: SEED_CHECKS.md must be added to the artifact contract table when Phase 0b runs**
- Spec basis: SKILL.md line 1641 requires SEED_CHECKS.md; artifact contract table at lines 88-119 must reflect all required artifacts
- Fix: add SEED_CHECKS.md row to artifact contract table with condition "If Phase 0b ran"

### [Iteration 3: unfiltered] New Requirements

**REQ-019: `quality_gate.sh` functional test file existence check must use find, not ls-glob**
- Spec basis: REQ-002 (reliable artifact detection), BUG-M8 fix pattern consistency
- Line 124: the file existence check must use `find`-based detection to avoid nullglob vulnerability

**REQ-020: `quality_gate.sh` BUGS.md heading regex must match severity-prefixed IDs (`BUG-H1`, `BUG-M3`, `BUG-L6`)**
- Spec basis: SKILL.md:1615 heading format requirement; QFB established naming convention
- The regex `^### BUG-[0-9]+` must be extended to match severity-prefixed IDs used by the QFB

**REQ-021: `quality_gate.sh` must cross-validate tdd-results.json `red_phase`/`green_phase` values against log file first-line tags**
- Spec basis: SKILL.md:1589 "TDD sidecar-to-log consistency check (mandatory)"
- Gate must verify that JSON phase values are consistent with log file evidence

---

## Demoted Candidates

### DC-001: `quality_gate.sh:278-283` — Date comparison uses string lexicographic comparison
- **Source:** Iteration 1, Open Exploration Finding 7
- **Dismissal reason:** For ISO 8601 dates (YYYY-MM-DD), lexicographic comparison correctly implements chronological ordering. The code works correctly in all practical cases. The fragility only manifests if the date format changes — and the format is validated by a regex check on the same line.
- **Code location:** `quality_gate.sh:278-283`
- **Re-promotion criteria:** Show that a valid ISO 8601 date string (passing the regex check) produces incorrect comparison results with `[[ "$a" > "$b" ]]` in bash. If a valid date could compare incorrectly, re-promote. If bash string comparison is definitively correct for all valid ISO 8601 YYYY-MM-DD dates (which it is), keep demoted.
- **Status:** DEMOTED — false positive risk, not a real bug for YYYY-MM-DD format

### DC-002: SKILL.md ~line 578 — Mechanical verification extraction pattern doesn't adapt to bash scripts
- **Source:** Iteration 1, Open Exploration Finding 5
- **Dismissal reason:** The SKILL.md rule says "Only create quality/mechanical/ if the project's contracts include dispatch functions, registries, or enumeration checks that require mechanical extraction." For bash-script projects, the guidance recommends NOT creating quality/mechanical/. The self-audit correctly documents "Mechanical verification: NOT APPLICABLE." This is by design.
- **Code location:** `SKILL.md:~578`
- **Re-promotion criteria:** Find an agent that incorrectly creates quality/mechanical/ for a bash-only project and fails verification benchmarks as a result. If this consistently happens due to the ambiguous guidance, re-promote.
- **Status:** DEMOTED — design ambiguity but correct implementation documented

### DC-003: SKILL.md — Phase 7 iteration vs baseline message ambiguity
- **Source:** Iteration 2 gap, Gap Finding 7
- **Dismissal reason:** The spec provides clear end-of-iteration messages that say STOP. Phase 7 is primarily for baseline runs. The iteration guidance in references/iteration.md provides a complete specification for iteration runs. The ambiguity is minor — an agent reading the iteration.md references will follow the correct path.
- **Code location:** `SKILL.md` ~lines 1892-1914, `references/iteration.md` shared rule 7
- **Re-promotion criteria:** Show that an iteration run incorrectly shows Phase 7 interactive menus (or fails to show them) in a way that harms the user experience. If the ambiguity causes systematic misuse, re-promote.
- **Status:** DEMOTED — minor doc clarity issue

### DC-004: `ai_context/TOOLKIT.md:182` — Phase count stale (6 vs 8 phases)
- **Source:** Iteration 2 gap, Gap Finding 8
- **Dismissal reason:** TOOLKIT.md is user-facing documentation, not operational instructions for agents. The agent reads SKILL.md, not TOOLKIT.md. A stale phase count in TOOLKIT.md misleads users but doesn't cause agent misbehavior.
- **Code location:** `ai_context/TOOLKIT.md:182-193`
- **Re-promotion criteria:** Show that an agent reading TOOLKIT.md as its primary instruction source (instead of SKILL.md) follows the wrong 6-phase procedure. If TOOLKIT.md is used as an agent instruction source, re-promote as MEDIUM.
- **Status:** DEMOTED — documentation staleness, not operational bug

### DC-005: SKILL.md:1108 — Code review summary uses different recommendation vocabulary
- **Source:** Iteration 2 gap, Gap Finding 6
- **Dismissal reason:** The code review combined summary is a Markdown file, not a JSON artifact. There is no gate check for the Markdown recommendation text. The vocabulary inconsistency (`FIX FIRST` vs `FIX BEFORE MERGE`) is confusing but doesn't cause gate failures for code review artifacts.
- **Code location:** `SKILL.md:1108`, `references/review_protocols.md:94`
- **Re-promotion criteria:** Show that an agent copies the Markdown summary's recommendation value into the integration-results.json recommendation field (i.e., the inconsistency causes cross-artifact contamination producing a gate-failing JSON artifact). If this cross-contamination is systematic, re-promote as MEDIUM.
- **Status:** DEMOTED — vocabulary inconsistency, no gate impact for code review artifacts

### DC-006: `quality_gate.sh:278-283` — Date comparison is lexicographic (Iteration 3 re-evaluation)
- **Source:** Iteration 1 (Finding 7), re-examined in Iteration 3 (Finding 15)
- **Dismissal reason:** ISO 8601 YYYY-MM-DD is guaranteed to sort correctly as strings. The validation regex ensures only valid YYYY-MM-DD dates enter the comparison. No edge case exists where a compliant date produces wrong comparison.
- **Code location:** `quality_gate.sh:278-283`
- **Re-promotion criteria:** Show a valid ISO 8601 date that passes the regex check but compares incorrectly with bash `>`. This cannot happen for YYYY-MM-DD format.
- **Status:** DEMOTED — false positive, confirmed false positive in Iteration 3

### DC-007: `quality_gate.sh:44` — Arg parser loop `${@+"$@"}` idiom (Iteration 3 trace)
- **Source:** Iteration 3 (Finding 5)
- **Dismissal reason:** The `${@+"$@"}` idiom is a correct POSIX portability pattern. In the arg parser context (line 44), it correctly handles empty `$@`. The real issue traced in Finding 5 is BUG-H2 at line 697 (already confirmed). The line 44 usage is correct and not buggy.
- **Code location:** `quality_gate.sh:44`
- **Re-promotion criteria:** Show that `${@+"$@"}` in the `for` loop at line 44 causes incorrect argument handling in a real bash/zsh scenario. Not the same as BUG-H2 at line 697.
- **Status:** DEMOTED — correct idiom, BUG-H2 covers the actual bug at line 697

### DC-008: `quality_gate.sh:293-298` — Verdict regex includes `deferred` (Iteration 3 check)
- **Source:** Iteration 3 (Finding 9)
- **Dismissal reason:** The gate regex `^(TDD verified|red failed|green failed|confirmed open|deferred)$` correctly includes all valid verdict values per SKILL.md line 149 and line 1424. The check was verified to match the spec.
- **Code location:** `quality_gate.sh:293-298`
- **Re-promotion criteria:** Find a verdict value that SKILL.md specifies as valid but the gate regex rejects. Currently no such value exists.
- **Status:** DEMOTED — gate regex is correct and complete

### DC-010: SKILL.md:~1424 — `"deferred"` verdict absent from tdd-results.json template examples
- **Source:** Iteration 4 parity, Group PG-5 Finding PG-5-F2
- **Dismissal reason:** `"deferred"` is documented in SKILL.md prose (lines 149, 1424) and matched by the gate regex (lines 294-298). Neither Template 1 nor Template 2 shows a `"deferred"` example, but agents reading the prose documentation know to use it. No agent failure mode is created by the template omission because the prose documentation is explicit.
- **Code location:** `SKILL.md:149, 1424` (prose) vs `SKILL.md:126-147, 1376-1408` (templates)
- **Re-promotion criteria:** Show that an agent generates `"verdict": "skipped"` (deprecated) instead of `"deferred"` because the template doesn't show a `"deferred"` example, and the gate accepts it incorrectly (the gate regex rejects `"skipped"`). If template absence systematically causes agents to use deprecated verdicts, re-promote as LOW.
- **Status:** DEMOTED — documentation completeness gap, not a behavioral bug

### DC-011: `quality_gate.sh:562-588` — Per-bug iteration vs aggregate count structural gap
- **Source:** Iteration 4 parity, Group PG-3 Finding PG-3-F1 and Group PG-2 Comparison 4
- **Dismissal reason:** The aggregate count approach for patches doesn't create false passes in normal operation because patches are named with specific bug IDs and duplicates are uncommon. The structural inconsistency (per-bug iteration for logs, aggregate count for patches) is a design gap but doesn't produce incorrect gate results for well-formed runs. CAND-P2 captures this but at LOW severity — insufficient evidence of actual incorrect gate behavior in realistic scenarios.
- **Code location:** `quality_gate.sh:562-588` (aggregate patch count) vs `quality_gate.sh:316-345` (per-bug log iteration)
- **Re-promotion criteria:** Show a realistic scenario where `reg_patch_count >= bug_count` but some confirmed bug has no regression-test patch. For example: two patches for BUG-H1 (accidental duplicate) and none for BUG-H2, with bug_count=2. If this produces a gate PASS, re-promote as MEDIUM (the gate gave false confidence that all bugs have patches).
- **Status:** DEMOTED — structural inconsistency confirmed, practical impact insufficient for confirmation without a concrete false-pass scenario

### DC-009: `quality_gate.sh:186-187` — `wrong_headings` nested grep always returns correct count
- **Source:** Iteration 3 (Finding 4)
- **Dismissal reason:** After full analysis, the nested grep logic at lines 186-187 correctly counts `## BUG-NNN` headings (two hashes). The logic is: filter lines starting with `## BUG-[0-9]+`, then count lines NOT starting with `### BUG-` — since all input lines start with `##`, none match `###`, so all are counted. This gives the correct count of double-hash headings. The deeper issue (BUG-[0-9]+ not matching BUG-H1) is covered by CAND-U2.
- **Code location:** `quality_gate.sh:186-187`
- **Re-promotion criteria:** Show a specific input where the nested grep produces wrong count for `## BUG-NNN` headings.
- **Status:** DEMOTED — logic is correct (the broader regex issue is CAND-U2)

---

## [Iteration 5: adversarial] New Findings

**Strategy:** adversarial — challenged prior dismissals and thin SATISFIED verdicts

### New Adversarial Candidates:

### [Iteration 5: adversarial] CAND-A1: `quality_gate.sh:389-436` — integration-results.json per-group fields and uc_coverage enum never validated
- **File:Line:** `quality_gate.sh:389-436` (absence — no per-group field or result enum validation)
- **Stage:** Iteration 5 Adversarial Finding A-1 (adjacent to BUG-L19 parity investigation)
- **Hypothesis:** The gate validates integration-results.json root key PRESENCE (via json_has_key) and recommendation enum, but never checks: (a) required per-group fields (`group`, `name`, `use_cases`, `result`, `notes`), (b) `groups[].result` enum values (`"pass"`, `"fail"`, `"skipped"`, `"error"`), or (c) `uc_coverage` value enum (`"covered_pass"`, `"covered_fail"`, `"not_mapped"`). SKILL.md:1273 defines these as required with specific enum values. A non-conformant integration-results.json with `"result": "PASS"` (wrong case) or `"uc_coverage": { "UC-01": "yes" }` passes all gate checks.
- **Parity:** tdd-results.json verdict values ARE validated (gate lines 294-296); integration groups[].result values are NOT. Same structural pattern, different enforcement rigor.
- **Severity:** LOW
- **Confirmed:** YES — see Phase 2 Phase 3 code review below

### [Iteration 5: adversarial] CAND-A2: `quality_gate.sh:389-436` — integration-results.json summary sub-keys never validated
- **File:Line:** `quality_gate.sh:393-394` (integration summary root key checked) vs lines 259-265 (tdd summary sub-keys checked)
- **Stage:** Iteration 5 Adversarial Finding A-2 (parity with BUG-L19)
- **Hypothesis:** The gate checks that `summary` exists in integration-results.json (line 393-394, via json_has_key), but never checks the summary object's required sub-keys: `total_groups`, `passed`, `failed`, `skipped` (from SKILL.md:1252-1255). For tdd-results.json, gate explicitly checks sub-keys `total`, `verified`, `confirmed_open`, `red_failed`, `green_failed` at lines 259-265. An integration-results.json with `"summary": {}` (empty) passes all gate checks.
- **Severity:** LOW
- **Confirmed:** YES

### [Iteration 5: adversarial] CAND-A3: SKILL.md:850 — Phase 2 entry gate does not enforce 120-line minimum (check #1 omitted from BUG-M3 fix scope)
- **File:Line:** `SKILL.md:850` (Phase 1 check #1: 120 lines) vs `SKILL.md:897-904` (Phase 2 entry gate — omits check #1)
- **Stage:** Iteration 5 Adversarial Finding A-3 (adjacent to BUG-M3)
- **Hypothesis:** BUG-M3 documented that Phase 2 entry gate enforces only 6 of 12 Phase 1 checks (missing checks 2, 3, 5, 8, 10, 12). Check #1 (minimum 120 lines of substantive content) is ALSO missing from Phase 2 entry gate enforcement AND was omitted from the BUG-M3 fix patch scope. An EXPLORATION.md with 6 required section title stubs (10 lines total) passes the Phase 2 entry gate even with BUG-M3's fix patch applied.
- **Severity:** LOW (extends BUG-M3 scope; same class)
- **Confirmed:** YES

### Demoted Candidates Re-Evaluated in Iteration 5:

- **DC-001 / DC-006:** FALSE POSITIVE (adversarial iteration) — date comparison is mathematically correct for ISO 8601 YYYY-MM-DD
- **DC-003:** FALSE POSITIVE (adversarial iteration) — Phase 7 vs iteration ambiguity: iteration.md provides clear override, no agent failure mode
- **DC-005:** FALSE POSITIVE (adversarial iteration) — no cross-artifact contamination path between code review summary and integration JSON
- **DC-010:** FALSE POSITIVE (adversarial iteration) — "deferred" template gap; gate rejects deprecated "skipped", prose docs cover it
- **DC-011:** RE-PROMOTED [Iteration 4: parity] — became BUG-L20
