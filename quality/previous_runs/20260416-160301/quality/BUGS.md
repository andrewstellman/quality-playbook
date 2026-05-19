# Bug Report: quality-playbook

<!-- Quality Playbook v1.4.1 — Phase 3 Code Review — 2026-04-16 -->

Phase 3 code review confirmed all 7 Phase 1 candidate bugs. No additional bugs discovered beyond the candidates.

---

### BUG-H1

**File:Line**: `quality_gate.sh:75-78` (primary); callers at lines 230, 253, 260

**Description**: `json_has_key()` uses `grep -q "\"${key}\""` which matches the key name anywhere in the file, including inside string values. A JSON file like `{"msg": "the 'id' field is required"}` returns exit 0 (true) from `json_has_key "id"` even though `id` is not a JSON key. The gate then incorrectly passes conformance checks for required fields in `tdd-results.json` when those fields are mentioned only in string values.

**Severity**: HIGH

**Spec basis**: REQ-001 (Tier 3) — "json_has_key() must verify the key appears as an actual JSON key (preceding `:`), not merely as a substring of a string value anywhere in the file." Also violates the behavioral contract at CONTRACTS.md item 27: "`json_has_key` returns exit 0 (false positive) when the key name appears in a string VALUE rather than as a JSON key."

**Regression test**: `quality/patches/BUG-H1-regression-test.patch`

**Fix patch**: `quality/patches/BUG-H1-fix.patch`

---

### BUG-H2

**File:Line**: `quality_gate.sh:697` (outer unquoted assignment); `quality_gate.sh:686` (unquoted loop expansion)

**Description**: The array reconstruction `REPO_DIRS=(${resolved[@]+"${resolved[@]}"})` at line 697 is unquoted at the outer level. Word-splitting occurs before the array assignment, so a repo path like `/Users/joe/My Projects/my-repo` becomes two elements: `/Users/joe/My` and `Projects/my-repo`. Downstream, `check_repo` receives word fragments instead of the full path, causing all artifact checks to run against non-existent paths. The loop at line 686 has the same unquoted expansion.

**Severity**: HIGH

**Spec basis**: REQ-002 (Tier 3) — "A repo path containing one or more spaces must appear as a single element in REPO_DIRS after reconstruction at line 697." Common on macOS where `~/Documents/My Projects/` is a standard path pattern.

**Regression test**: `quality/patches/BUG-H2-regression-test.patch`

**Fix patch**: `quality/patches/BUG-H2-fix.patch`

---

### BUG-M3

**File:Line**: `SKILL.md:897-904` (Phase 2 entry gate) vs `SKILL.md:847-862` (Phase 1 completion gate)

**Description**: The Phase 2 entry gate enforces only 6 of the 12 Phase 1 completion gate checks. Missing checks: 2 (PROGRESS.md marks Phase 1 complete), 3 (Derived Requirements with file paths), 5 (open-exploration depth — 3 findings trace 2+ functions), 8 (3-4 FULL patterns), 10 (depth — 2 deep dives trace 2+ functions), 12 (ensemble balance). An EXPLORATION.md with the required section titles but substantively empty content passes the Phase 2 entry gate, allowing Phase 2 to proceed from shallow exploration.

**Severity**: MEDIUM

**Spec basis**: REQ-003 (Tier 3) — "The Phase 2 entry gate must either enforce all 12 Phase 1 completion gate checks, or explicitly document which checks are not backstopped." Also inconsistent with REQ-010 (Tier 1) which requires substantive content before Phase 2 begins.

**Regression test**: `quality/patches/BUG-M3-regression-test.patch`

**Fix patch**: `quality/patches/BUG-M3-fix.patch`

---

### BUG-M4

**File:Line**: `quality_gate.sh:476-533` (`[Test File Extension]` section); artifact contract at `SKILL.md:88-119`

**Description**: The gate checks for the existence of `quality/test_regression.*` only incidentally (in the extension check at line 479-480, where it reads the filename to validate the extension). It does not enforce existence as a gate condition when bugs are confirmed. The artifact contract at SKILL.md lines 88-119 designates `quality/test_regression.*` as "Required: If bugs found." The gate at lines 562-588 checks for regression test PATCHES (`quality/patches/BUG-NNN-regression-test.patch`) but not for the regression test SOURCE FILE. A run with confirmed bugs that produces patches but no `test_regression.*` file passes the gate, violating the artifact contract.

**Severity**: MEDIUM

**Spec basis**: REQ-004 (Tier 2) — "Gate must FAIL when `bug_count > 0` and no `quality/test_regression.*` file exists." Artifact contract table at SKILL.md line 94: `quality/test_regression.*` — "Required: If bugs found."

**Regression test**: `quality/patches/BUG-M4-regression-test.patch`

**Fix patch**: `quality/patches/BUG-M4-fix.patch`

---

### BUG-M5

**File:Line**: `SKILL.md:271` (Phase 0a activation), `SKILL.md:295-297` (Phase 0b activation)

**Description**: Phase 0a activates only when `previous_runs/` exists AND contains prior quality artifacts. Phase 0b activates only when `previous_runs/` does NOT exist. When `previous_runs/` exists but is empty: Phase 0a skips (no artifacts), Phase 0b also skips (directory exists). No seeding occurs and no warning is emitted. The developer who created an empty `previous_runs/` directory expecting sibling-run seed discovery gets silent no-op behavior instead.

**Severity**: MEDIUM

**Spec basis**: REQ-005 (Tier 2) — "Phase 0b seed discovery must run when `previous_runs/` exists but contains no conformant quality artifacts." Also documented in CONTRACTS.md item 14 as an `[ERROR]` contract: "This creates a gap: empty `previous_runs/` causes both Phase 0a and 0b to skip with no warning."

**Regression test**: `quality/patches/BUG-M5-regression-test.patch`

**Fix patch**: `quality/patches/BUG-M5-fix.patch`

---

### BUG-L6

**File:Line**: `quality_gate.sh:81-85` (`json_str_val` function); caller at line 236

**Description**: `json_str_val()` returns empty string for both "key absent" and "key exists with non-string value." When `schema_version` is a number (`"schema_version": 1.1`), the caller at line 236 reports `"schema_version is 'missing', expected '1.1'"` when the actual problem is a wrong type. A developer debugging this gate failure would search for a missing field when the field exists but has the wrong type.

**Severity**: LOW

**Spec basis**: REQ-007 (Tier 3) — "For `"schema_version": 1.1` (number) → return a value distinguishable from empty string indicating 'key exists, non-string value'." Behavioral contract CONTRACTS.md item 29: "`json_str_val` cannot distinguish 'key absent' from 'key with non-string value' — both return empty string."

**Regression test**: `quality/patches/BUG-L6-regression-test.patch`

**Fix patch**: `quality/patches/BUG-L6-fix.patch`

---

### BUG-L7

**File:Line**: `SKILL.md:6, 39, 129, 156, 915, 922, 1056, 1966` (8 occurrences of `1.4.1`)

**Description**: Version `1.4.1` appears in 8 hardcoded locations in SKILL.md without a mechanical cross-reference check. All 8 currently match, so no immediate bug exists. However, there is no tool or gate check that enforces SKILL.md-internal version consistency. A version bump that updates the frontmatter but misses one of the 8 inline occurrences (particularly the JSON examples at lines 129 and 1966 which agents copy verbatim) would cause agents to generate wrong-stamped artifacts without any warning from the gate.

**Severity**: LOW

**Spec basis**: REQ-006 (Tier 2) — "All occurrences of the version string in SKILL.md must equal `metadata.version`. A grep for any version string that differs from frontmatter must return empty." The "mechanical check" aspect is currently missing.

**Regression test**: `quality/patches/BUG-L7-regression-test.patch`

**Fix patch**: (none — fix is adding a grep check; no automated patch is appropriate for this specification-primary bug)

---

---

### BUG-M8

**File:Line**: `quality_gate.sh:152-153, 331, 567-568, 595`

**Description**: Multiple artifact-counting operations use the pattern `ls ${q}/path/*glob* 2>/dev/null | wc -l` with unquoted globs. Under `nullglob` shell option (active by default in many zsh configurations including macOS), an unmatched glob expands to empty words. The `ls` command then receives no arguments and lists the current working directory. The `2>/dev/null` suppresses only `ls`'s error output — it does NOT suppress stdout. `wc -l` counts lines in the current directory listing, producing a nonzero count even when no matching files exist. Affected artifact checks: spec_audits triage file presence (line 152), spec_audits auditor file presence (line 153), patch counting (lines 567-568), writeup counting (line 595). Additionally, line 331 uses `if ls ${q}/patches/${bid}-fix*.patch &>/dev/null` where `&>/dev/null` suppresses all output but under nullglob `ls` with no args returns exit code 0 (success), causing the gate to spuriously require a green-phase log even when no fix patch exists.

**Severity**: MEDIUM

**Spec basis**: REQ-002 (Tier 3) and REQ-014 (Tier 3) — consistent, reliable artifact detection across shell configurations. The gate uses `find ... -print -quit` for language detection at lines 449-454, showing the developer was aware of the robust pattern. The `ls | wc -l` pattern is a systemic technical debt in the counting operations.

**Regression test**: `quality/patches/BUG-M8-regression-test.patch`

**Fix patch**: `quality/patches/BUG-M8-fix.patch`

---

### BUG-L9

**File:Line**: `SKILL.md:1548`, `quality/RUN_SPEC_AUDIT.md:143`, `references/spec_audit.md` "Output" section

**Description**: Three incompatible naming formats are specified for individual auditor report files:
1. SKILL.md line 1548 (Phase 4 instructions): `quality/spec_audits/YYYY-MM-DD-auditor-N.md`
2. quality/RUN_SPEC_AUDIT.md line 143 (generated per-project protocol): `quality/spec_audits/auditor_<model>_<date>.md`
3. references/spec_audit.md "Output" section: `quality/spec_audits/YYYY-MM-DD-[model].md`

The gate glob `*auditor*` at quality_gate.sh line 153 matches all three patterns. However, an agent following Phase 4 instructions writes differently-named files than an agent following the generated RUN_SPEC_AUDIT.md. This creates naming inconsistency across runs and sessions, making artifact provenance hard to track. The current run uses `auditor_a.md`, `auditor_b.md`, `auditor_c.md` — matching the RUN_SPEC_AUDIT.md convention but not Phase 4's YYYY-MM-DD format.

**Severity**: LOW

**Spec basis**: REQ-011 (Tier 1) — requirements pipeline must produce traceable artifacts. Naming inconsistency reduces traceability. Spec bug — internal inconsistency between SKILL.md Phase 4 and the generated spec audit protocol.

**Regression test**: `quality/patches/BUG-L9-regression-test.patch`

**Fix patch**: (none — fix is standardizing naming format in SKILL.md and RUN_SPEC_AUDIT.md template)

---

### BUG-L10

**File:Line**: `SKILL.md:1965` (recheck template) vs `SKILL.md:128` (tdd template) vs `SKILL.md:156` (integration template)

**Description**: The recheck mode JSON artifact template at SKILL.md line 1965 uses `"schema_version": "1.0"` while all other sidecar JSON artifacts (tdd-results.json at line 128, integration-results.json at line 156) use `"schema_version": "1.1"`. There is no migration note or documentation explaining why recheck uses a different schema version. `quality_gate.sh` does not validate `recheck-results.json` at all (confirmed by grep — no `recheck-results` in the gate script), so there is no mechanical enforcement of conformance. From a user perspective: (1) if a future gate version adds recheck validation, it must handle a different schema version than all other artifacts; (2) agents generating recheck output see a "1.0" example in the context of a skill that otherwise uses "1.1" everywhere, creating ambiguity.

**Severity**: LOW

**Spec basis**: REQ-009 (Tier 2) — generated artifacts must include consistent version stamps. Schema version is part of the artifact conformance contract. Spec bug — recheck template uses a different schema version with no documented rationale.

**Regression test**: `quality/patches/BUG-L10-regression-test.patch`

**Fix patch**: (none — fix is either updating recheck template to use "1.1" or adding a documentation note explaining why "1.0" is intentional)

---

### BUG-L11

**File:Line**: `SKILL.md:135` (artifact contract template) vs `SKILL.md:1385` (Phase 5 RUN_TDD_TESTS.md template)

**Description**: Two incompatible tdd-results.json templates exist in SKILL.md. Template 1 (artifact contract section, lines 122-148) shows the `requirement` field as a full description: `"requirement": "UC-03: Description of the requirement violated"`. Template 2 (Phase 5 File 7, lines 1376-1408) shows: `"requirement": "REQ-003"`. Additionally, Template 1's `red_phase` and `green_phase` fields contain narrative text ("Regression test fails on unpatched code"), while Template 2's use enum values ("fail", "pass"). Template 2 also includes 7 optional fields not present in Template 1. An agent following Template 1 generates different JSON than an agent following Template 2. The gate validates required per-bug field PRESENCE but not VALUE FORMAT, so both pass the gate. However, downstream tools that expect the `requirement` field to contain a REQ-NNN identifier (for traceability) would fail on Template 1 output.

**Severity**: LOW

**Spec basis**: REQ-009 (Tier 2) — generated artifact version stamps must match. Spec bug — two templates in SKILL.md define different value formats for the same required JSON field.

**Regression test**: `quality/patches/BUG-L11-regression-test.patch`

**Fix patch**: (none — fix is standardizing the templates)

---

## Summary

| Bug ID | Severity | File | Status |
|--------|----------|------|--------|
| BUG-H1 | HIGH | quality_gate.sh:75-78 | Confirmed — regression test written |
| BUG-H2 | HIGH | quality_gate.sh:697,686 | Confirmed — regression test written |
| BUG-M3 | MEDIUM | SKILL.md:897-904 | Confirmed — regression test written |
| BUG-M4 | MEDIUM | quality_gate.sh:476-533 | Confirmed — regression test written |
| BUG-M5 | MEDIUM | SKILL.md:271,295-297 | Confirmed — regression test written |
| BUG-L6 | LOW | quality_gate.sh:81-85 | Confirmed — regression test written |
| BUG-L7 | LOW | SKILL.md:8 locations | Confirmed — regression test written |
| BUG-M8 | MEDIUM | quality_gate.sh:152-153,331,567-568,595 | Confirmed (Phase 4 Spec Audit) — regression test written |
| BUG-L9 | LOW | SKILL.md:1548, RUN_SPEC_AUDIT.md:143 | Confirmed (Phase 4 Spec Audit) — regression test written |
| BUG-L10 | LOW | SKILL.md:1965 | Confirmed (Phase 4 Spec Audit) — regression test written |
| BUG-L11 | LOW | SKILL.md:135 vs 1385 | Confirmed (Phase 4 Spec Audit) — regression test written |

| BUG-M12 | MEDIUM | quality_gate.sh:479 | Confirmed (Gap Iteration) — regression test written |
| BUG-M13 | MEDIUM | quality_gate.sh:143 | Confirmed (Gap Iteration) — regression test written |
| BUG-L14 | LOW | references/review_protocols.md:410 | Confirmed (Gap Iteration) — regression test written |
| BUG-M15 | MEDIUM | quality_gate.sh (absence) | Confirmed (Gap Iteration) — regression test written |

| BUG-M16 | MEDIUM | quality_gate.sh:124 | Confirmed (Unfiltered Iteration) — regression test written |
| BUG-H17 | HIGH | quality_gate.sh:184,313 | Confirmed (Unfiltered Iteration) — regression test written |
| BUG-M18 | MEDIUM | quality_gate.sh:239-248,307-387 | Confirmed (Unfiltered Iteration) — regression test written |

| BUG-L19 | LOW | quality_gate.sh:259-265 | Confirmed (Parity Iteration) — regression test written |
| BUG-L20 | LOW | quality_gate.sh:562-588 | Confirmed (Parity Iteration) — regression test written |
| BUG-L21 | LOW | SKILL.md:1573-1590 | Confirmed (Parity Iteration) — regression test written |
| BUG-L22 | LOW | SKILL.md:85-88 vs 1641 | Confirmed (Parity Iteration) — regression test written |

| BUG-L23 | LOW | quality_gate.sh:389-436 | Confirmed (Adversarial Iteration) — regression test written |
| BUG-L24 | LOW | quality_gate.sh:393-394 | Confirmed (Adversarial Iteration) — regression test written |
| BUG-L25 | LOW | SKILL.md:850 vs 897-904 | Confirmed (Adversarial Iteration) — regression test written |

**Total confirmed bugs: 25** (3 HIGH, 8 MEDIUM, 14 LOW)
**Phase 4 net-new bugs: 4** (BUG-M8, BUG-L9, BUG-L10, BUG-L11)
**Gap iteration net-new bugs: 4** (BUG-M12, BUG-M13, BUG-L14, BUG-M15)
**Unfiltered iteration net-new bugs: 3** (BUG-M16, BUG-H17, BUG-M18)
**Parity iteration net-new bugs: 4** (BUG-L19, BUG-L20, BUG-L21, BUG-L22)
**Adversarial iteration net-new bugs: 3** (BUG-L23, BUG-L24, BUG-L25)
**Phase 4 net-new bugs: 4** (BUG-M8, BUG-L9, BUG-L10, BUG-L11)
**Gap iteration net-new bugs: 4** (BUG-M12, BUG-M13, BUG-L14, BUG-M15)
**Unfiltered iteration net-new bugs: 3** (BUG-M16, BUG-H17, BUG-M18)
**Parity iteration net-new bugs: 4** (BUG-L19, BUG-L20, BUG-L21, BUG-L22)

---

<!-- Gap Iteration Bug Entries — 2026-04-16 -->

### BUG-M12

**File:Line**: `quality_gate.sh:479`

**Description**: `func_test=$(ls ${q}/test_functional.* 2>/dev/null | head -1)` uses an unquoted ls-glob to capture the functional test filename for extension detection. Under `nullglob` (common zsh/macOS default), when no `test_functional.*` file exists in `${q}`, the glob expands to empty and `ls` with no argument lists the current working directory. `head -1` then returns the first CWD entry, making `func_test` non-empty. The downstream check `if [ -n "$func_test" ]` at line 481 evaluates TRUE spuriously, and `local ext="${func_test##*.}"` at line 482 extracts an extension from the wrong file. This can produce incorrect FAIL results (wrong extension mismatch) when the actual test file has the correct extension, or incorrect PASS when no test file exists. The bug is the same nullglob vulnerability class as BUG-M8. Notably, lines 486–495 in the SAME function use `find ... -print -quit` (the correct approach) for language detection — the inconsistency is within 7 lines.

**Severity**: MEDIUM

**Spec basis**: REQ-015 (Tier 3) — "The ls glob at line 479 must be replaced with find-based detection. Same vulnerability class as BUG-M8 (nullglob)." Same pattern as BUG-M8 confirmed via gap iteration.

**Regression test**: `quality/patches/BUG-M12-regression-test.patch`

**Fix patch**: `quality/patches/BUG-M12-fix.patch`

---

### BUG-M13

**File:Line**: `quality_gate.sh:143`

**Description**: `[ -n "$(ls ${q}/code_reviews/*.md 2>/dev/null)" ]` uses an unquoted ls-glob to check whether code review files exist. Under `nullglob`, when `${q}/code_reviews/` exists but contains no `.md` files, the glob expands to empty and `ls` lists the current working directory. The command substitution captures the CWD listing, making `[ -n "..." ]` TRUE. The gate reports `pass "code_reviews/ has .md files"` even when the directory is empty. A partial session (code_reviews/ directory created but no reviews written) passes this check under nullglob, defeating the partial session detection purpose of the check. The consequence is that a playbook run that terminates after creating directories but before writing content appears conformant to the gate.

**Severity**: MEDIUM

**Spec basis**: REQ-016 (Tier 3) — "Gate must correctly detect whether code review files were written." Also impacts spec_audit.md partial session detection rule: "If quality/code_reviews/ exists but contains no .md files with actual findings, the code review did not run. Mark this as FAILED in PROGRESS.md."

**Regression test**: `quality/patches/BUG-M13-regression-test.patch`

**Fix patch**: `quality/patches/BUG-M13-fix.patch`

---

### BUG-L14

**File:Line**: `references/review_protocols.md:410`

**Description**: The integration test protocol template in `references/review_protocols.md` specifies the `recommendation` field as `[SHIP IT / FIX FIRST / NEEDS INVESTIGATION]` (line 410). This contradicts the canonical enum values established in `quality_gate.sh:427` (`SHIP|"FIX BEFORE MERGE"|BLOCK`) and `SKILL.md:1273` (`"SHIP"`, `"FIX BEFORE MERGE"`, `"BLOCK"`). An agent reading `references/review_protocols.md` (which is explicitly referenced by SKILL.md Phase 2's File 4 instructions as the source for integration test protocol generation) and following its template will write `"recommendation": "FIX FIRST"` or `"recommendation": "NEEDS INVESTIGATION"` into `integration-results.json`. The gate will then FAIL with: `recommendation 'FIX FIRST' is non-canonical (must be SHIP/FIX BEFORE MERGE/BLOCK)`. The old values are human-readable prose labels from when the integration protocol was a Markdown report; the canonical values are the machine-readable enum values required by the JSON schema. The reference file was not updated when the schema was formalized.

**Severity**: LOW

**Spec basis**: REQ-017 (Tier 1) — "All recommendation enum values must be consistent across SKILL.md, references/review_protocols.md, and quality_gate.sh." SKILL.md:1273 and quality_gate.sh:427 agree on the canonical values; the reference file does not.

**Regression test**: `quality/patches/BUG-L14-regression-test.patch`

**Fix patch**: `quality/patches/BUG-L14-fix.patch`

---

### BUG-M15

**File:Line**: `quality_gate.sh` (entire file — absence of recheck validation section)

**Description**: `quality_gate.sh` validates every documented conditional artifact — tdd-results.json (lines 221-305), TDD log files (lines 307-387), integration-results.json (lines 389-436), patches (lines 562-588), writeups (lines 590-623) — but has no validation section for `recheck-results.json` or `recheck-summary.md`. The SKILL.md artifact contract table (lines 117-118) documents both files as required artifacts "When recheck runs." A malformed or incomplete recheck run (wrong status enum values, missing required fields, wrong schema_version, or empty results array) produces no gate failures. This creates a silent quality gap: the gate provides strong conformance assurance for all other artifact types but zero assurance for recheck artifacts. The gate should check, when `recheck-results.json` exists: (1) required fields present (schema_version, skill_version, date, project, source_run, results, summary), (2) per-result fields (id, severity, status, evidence), (3) status enum values restricted to FIXED, PARTIALLY_FIXED, STILL_OPEN, INCONCLUSIVE, (4) summary consistency.

**Severity**: MEDIUM

**Spec basis**: REQ-018 (Tier 1) — "Gate must validate recheck-results.json when it exists." SKILL.md artifact contract table lines 117-118: both recheck artifacts documented as required when recheck runs.

**Regression test**: `quality/patches/BUG-M15-regression-test.patch`

**Fix patch**: `quality/patches/BUG-M15-fix.patch`

---

### BUG-M16

**File:Line**: `quality_gate.sh:124` (`[Functional Test File]` existence check)

**Description**: The functional test file existence check at line 124 uses an `ls`-glob pattern: `if ls ${q}/test_functional.* ${q}/FunctionalSpec.* ${q}/FunctionalTest.* ${q}/functional.test.* &>/dev/null 2>&1; then`. Under zsh/macOS default `nullglob` (or bash with `nullglob` set), an unmatched glob pattern expands to nothing, causing `ls` to receive no arguments and list the current working directory instead — which always succeeds (exit 0). The gate then reports `PASS: functional test file detected` when no test file exists at all. This is the same nullglob vulnerability class as BUG-M8 (lines 152-153, 331, 567-568, 595), BUG-M12 (line 479), and BUG-M13 (line 143), but at a previously unfixed location.

**Severity**: MEDIUM

**Spec basis**: REQ-019 (Tier 2) — "The functional test file existence check at `quality_gate.sh:124` must use `find`-based detection, not an `ls`-glob, to be immune to `nullglob` behavior." SKILL.md artifact contract documents `quality/test_functional.*` as a required artifact; a false-positive existence check undermines that requirement.

**Regression test**: `quality/patches/BUG-M16-regression-test.patch`

**Fix patch**: `quality/patches/BUG-M16-fix.patch`

---

### BUG-H17

**File:Line**: `quality_gate.sh:184` (bug count), `quality_gate.sh:313` (bug ID extraction)

**Description**: The gate counts BUGS.md bug headings with `grep -cE '^### BUG-[0-9]+'` (line 184) and extracts IDs with `grep -oE 'BUG-[0-9]+'` (line 313). The regex `BUG-[0-9]+` requires a purely numeric suffix. The QFB itself generates severity-prefixed IDs (`BUG-H1`, `BUG-M3`, `BUG-L6`) where the suffix is a letter followed by a number. For any BUGS.md using severity-prefix IDs, both regexes return 0/empty — the gate sets `bug_count=0` and `bug_ids=""`. Every subsequent validation section is conditioned on `bug_count > 0`: lines 223, 309, 564, and 592. All four sections output `INFO: Zero bugs — ... not required` and skip validation entirely. The gate reports PASS while having performed zero validation of TDD logs, patches, or writeups. This affects every standard QFB self-audit run, as Phase 3 generates severity-prefix IDs by design.

**Severity**: HIGH

**Spec basis**: REQ-020 (Tier 1) — "BUGS.md heading regex must match severity-prefixed bug IDs (`BUG-H1`, `BUG-M3`, `BUG-L6`) generated by QFB Phase 3." The consequence of this regex mismatch is complete bypass of the gate's artifact validation — all 45 benchmarks in `references/verification.md` go unverified for QFB-format runs.

**Regression test**: `quality/patches/BUG-H17-regression-test.patch`

**Fix patch**: `quality/patches/BUG-H17-fix.patch`

---

### BUG-M18

**File:Line**: `quality_gate.sh:239-248` (JSON field presence check), `quality_gate.sh:307-387` (log tag validation)

**Description**: `SKILL.md:1589` mandates a "TDD sidecar-to-log consistency check (mandatory)": if `tdd-results.json` contains a bug with `"verdict": "TDD verified"`, then `BUG-NNN.red.log` must have first line `RED` and `BUG-NNN.green.log` must have first line `GREEN`. The gate validates JSON field PRESENCE (lines 239-248 check that `red_phase`, `green_phase` keys exist) and log tag FORMAT (lines 322-325 check that first-line tags are one of `RED|GREEN|NOT_RUN|ERROR`) — but never compares them. A `tdd-results.json` with `"red_phase": "pass"` (implying success) alongside a `BUG-NNN.red.log` whose first line is `GREEN` (meaning the test passed on unpatched code — the bug could not be reproduced) passes all gate checks without any contradiction detected. An agent can fabricate a "TDD verified" verdict with inconsistent log evidence and the gate will not catch it.

**Severity**: MEDIUM

**Spec basis**: REQ-021 (Tier 2) — "Gate must cross-validate `tdd-results.json` `red_phase`/`green_phase` values against corresponding log file first-line tags, per SKILL.md:1589 'TDD sidecar-to-log consistency check (mandatory).'"

**Regression test**: `quality/patches/BUG-M18-regression-test.patch`

---

<!-- Parity Iteration Bug Entries — 2026-04-16 -->

### BUG-L19

**File:Line**: `quality_gate.sh:259-265` (summary sub-key check using `json_has_key`) vs `quality_gate.sh:239-248` (per-bug field check using `json_key_count`)

**Description**: The gate uses `json_has_key` to check required summary sub-keys (`total`, `verified`, `confirmed_open`, `red_failed`, `green_failed`) at lines 259-265, while using `json_key_count` for the parallel per-bug required field checks at lines 239-248. These are two parallel operations that answer the same logical question ("is this JSON key present?") but use validators with different matching semantics. `json_has_key` (line 77) uses `grep -q "\"${key}\""` which matches the key name anywhere in the file — inside string values, comments, or embedded text. `json_key_count` (line 90) uses `grep -c "\"${key}\"[[:space:]]*:"` which is colon-anchored and only matches actual JSON key positions. A `tdd-results.json` where summary key names appear in string values (e.g., `"notes": "total confirmed"`) passes the summary check spuriously via `json_has_key`, but the per-bug check using `json_key_count` would correctly reject equivalent pollution. The inconsistency means the gate applies weaker validation to summary keys than to per-bug keys, despite checking the same type of required field.

**Severity**: LOW

**Spec basis**: REQ-022 (Tier 3) — "Gate summary sub-key checks must use `json_key_count` for consistency with per-bug field checks — both enforce the same 'required JSON key present' contract and should use the same validator." The stronger validator (`json_key_count` with colon anchor) is already available and used 7 lines earlier in the same function.

**Regression test**: `quality/patches/BUG-L19-regression-test.patch`

**Fix patch**: `quality/patches/BUG-L19-fix.patch`

---

### BUG-L20

**File:Line**: `quality_gate.sh:562-588` (aggregate patch count) vs `quality_gate.sh:316-345` (per-bug TDD log iteration)

**Description**: The gate enforces two parallel contracts — "every confirmed bug must have a TDD log" (lines 316-345) and "every confirmed bug must have a regression-test patch" (lines 562-588) — using different implementation strategies with different correctness guarantees. The TDD log section iterates confirmed `bug_ids` extracted from BUGS.md, checking each individual bug by name (`[ -f "${q}/results/${bid}.red.log" ]`). The patch section counts ALL patches in the patches/ directory using an aggregate ls-glob (`ls ${q}/patches/BUG-*-regression*.patch 2>/dev/null | wc -l`) and compares the total count to `bug_count`. The aggregate approach cannot detect that a specific bug's patch is missing — only that the total count is wrong. Concrete false-pass scenario: 2 confirmed bugs (BUG-H1, BUG-M3); patches present are `BUG-H1-regression-test.patch` and `BUG-H1-regression-test-v2.patch` (duplicate); `BUG-M3-regression-test.patch` absent. `reg_patch_count = 2`, `bug_count = 2`, gate reports PASS. BUG-M3 has no patch.

**Severity**: LOW

**Spec basis**: REQ-023 (Tier 3) — "Patch existence check must iterate per-bug ID to match the per-bug iteration pattern used by TDD log checks — aggregate count allows wrong-set patches to produce false PASS." The per-bug iteration approach (already used at lines 316-345) is the correct pattern; the aggregate count approach at lines 562-588 is a weaker equivalent.

**Regression test**: `quality/patches/BUG-L20-regression-test.patch`

**Fix patch**: `quality/patches/BUG-L20-fix.patch`

---

### BUG-L21

**File:Line**: `SKILL.md:1573-1590` (Phase 5 opening — no entry gate) vs `SKILL.md:897-907` (Phase 2 entry gate)

**Description**: SKILL.md applies an entry gate pattern inconsistently across phases. Phase 2 has a mandatory entry gate that mechanically verifies Phase 1 artifacts before any Phase 2 work begins: "Before generating any artifacts, read quality/EXPLORATION.md from disk and verify ALL of the following exact section titles exist" (lines 897-904). This gate fires BEFORE Phase 2 work and checks mechanically generated content (EXPLORATION.md section titles). Phase 5 has no equivalent: it begins by reading PROGRESS.md (an agent-maintained text file) — "Re-read quality/PROGRESS.md — specifically the cumulative BUG tracker" (line 1581). The only Phase 4 completion check in Phase 5 is at the terminal gate (line 1611): "The terminal gate may run only if Phase 3 and Phase 4 are both complete, or explicitly marked skipped with rationale in PROGRESS.md." This fires at the END of Phase 5, not the beginning. An agent that writes "Phase 4 complete" in PROGRESS.md without running the spec audit can proceed through all of Phase 5 (reconciliation, TDD verification, closure reports) before the terminal gate reveals the problem — wasting all that work.

**Severity**: LOW

**Spec basis**: REQ-024 (Tier 3) — "Phase 5 must include an entry gate that mechanically verifies Phase 4 artifacts (triage file and individual auditor reports) exist before any Phase 5 work begins, mirroring the fail-early pattern of the Phase 2 entry gate." The inconsistency is a spec gap — SKILL.md should apply the same fail-early pattern it already uses for Phase 2.

**Regression test**: `quality/patches/BUG-L21-regression-test.patch`

**Fix patch**: (none — spec-primary fix needed in SKILL.md Phase 5 opening section)

---

### BUG-L22

**File:Line**: `SKILL.md:85-88` (artifact contract table canonical claim) vs `SKILL.md:1641` (Phase 5 gate requiring SEED_CHECKS.md)

**Description**: SKILL.md line 88 states: "This is the canonical list — any artifact not listed here should not be gate-enforced, and any gate check should trace to an artifact listed here." The artifact contract table at lines 88-119 has 18 rows; none include `quality/SEED_CHECKS.md`. However, SKILL.md line 1641 (Phase 5 artifact file-existence gate) explicitly requires: "If Phase 0 or 0b ran: quality/SEED_CHECKS.md exists as a standalone file (not inlined in PROGRESS.md)." These two SKILL.md statements are mutually contradictory: the table says SEED_CHECKS.md should NOT be gate-enforced (it's not in the canonical list), while Phase 5 says it MUST exist as a standalone file when Phase 0b runs. `quality_gate.sh` does not check for SEED_CHECKS.md, consistent with the table but violating Phase 5's requirement. An agent reading only the artifact contract table (the declared canonical source) would not know to create SEED_CHECKS.md. An agent following the Phase 5 gate would fail if the file doesn't exist after a Phase 0b run.

**Severity**: LOW

**Spec basis**: REQ-025 (Tier 3) — "SEED_CHECKS.md must be added to the artifact contract table (SKILL.md:88-119) with condition 'If Phase 0b ran' — the table is declared canonical and must reflect all conditionally required artifacts." This is a self-contradiction within SKILL.md: the table's canonical claim is false when Phase 0b runs.

**Regression test**: `quality/patches/BUG-L22-regression-test.patch`

**Fix patch**: (none — spec-primary fix needed in SKILL.md artifact contract table)

---

<!-- Adversarial Iteration Bug Entries — 2026-04-16 -->

### BUG-L23

**File:Line**: `quality_gate.sh:389-436` (entire integration JSON validation block — absence); `SKILL.md:1273` (enum spec)

**Description**: The gate validates `integration-results.json` root key presence (line 393-394, via `json_has_key`) and the `recommendation` field enum (lines 426-428), but never validates: (a) `groups[].result` enum values, (b) `groups[]` per-element required fields (`group`, `name`, `use_cases`, `result`, `notes`), or (c) `uc_coverage` value enum (`"covered_pass"`, `"covered_fail"`, `"not_mapped"`). SKILL.md:1273 defines valid result values as `"pass"`, `"fail"`, `"skipped"`, `"error"` and calls out the uc_coverage enum as important for downstream consumers. SKILL.md:1277 (post-write validation) mandates that agents verify "all `result` and `recommendation` values use only the allowed enum values" — but the gate provides no enforcement for result values.

Concrete false-pass scenario: An agent writes `"result": "PASS"` (uppercase, wrong value) in a group entry. Gate reports PASS on all integration checks. A CI tool reading `if result == "pass"` breaks silently. The gate's false conformance assurance misleads consumers.

**Severity**: LOW

**Spec basis**: REQ-026 (Tier 3, new) — "Gate must validate `integration-results.json` `groups[].result` enum values against canonical set ('pass', 'fail', 'skipped', 'error') per SKILL.md:1273, consistent with tdd-results.json verdict enum validation at quality_gate.sh:294-296." Parity with BUG-L19 (tdd summary sub-key weak validation) — same class: shallow validation where deep validation is required.

**Regression test**: `quality/patches/BUG-L23-regression-test.patch`

**Fix patch**: `quality/patches/BUG-L23-fix.patch`

---

### BUG-L24

**File:Line**: `quality_gate.sh:393-394` (integration summary root key check — no sub-key validation); `quality_gate.sh:259-265` (tdd summary sub-key check — present for contrast)

**Description**: The gate checks that `summary` exists as a key in `integration-results.json` (line 393-394, via `json_has_key`), but never validates the summary object's required sub-keys: `total_groups`, `passed`, `failed`, `skipped` (from SKILL.md:1252-1255). For `tdd-results.json`, the gate explicitly checks 5 summary sub-keys at lines 259-265 (via `json_has_key` — weak per BUG-L19, but at least present). The integration summary validation is weaker by one level: tdd gets sub-key presence checks (however weak), integration gets only top-level key presence.

Concrete false-pass scenario: An agent writes `"summary": {}` (empty) or `"summary": {"status": "ok"}` (wrong keys) in integration-results.json. Gate reports PASS for the integration summary check. Any downstream aggregation tool reading `summary.total_groups` or `summary.passed` fails with null-dereference / key-error.

**Severity**: LOW

**Spec basis**: REQ-027 (Tier 3, new) — "Gate must validate `integration-results.json` `summary` sub-keys (`total_groups`, `passed`, `failed`, `skipped`) per SKILL.md:1252-1255, consistent with tdd-results.json summary sub-key validation at quality_gate.sh:259-265." Parity gap — same contract, different enforcement depth.

**Regression test**: `quality/patches/BUG-L24-regression-test.patch`

**Fix patch**: `quality/patches/BUG-L24-fix.patch`

---

### BUG-L25

**File:Line**: `SKILL.md:850` (Phase 1 completion gate check #1: 120-line minimum) vs `SKILL.md:897-904` (Phase 2 entry gate — check #1 absent); `quality/patches/BUG-M3-fix.patch` (does not add check #1)

**Description**: The Phase 1 completion gate (SKILL.md:846-862) defines 12 numbered checks. Check #1 requires: "The file exists on disk and contains at least 120 lines of substantive content." The Phase 2 entry gate (SKILL.md:897-904) is the backstop for multi-session mode, enforcing Phase 1 completion gate requirements before Phase 2 begins. The Phase 2 entry gate enforces section titles (6 checks) but NOT check #1 (120-line minimum). BUG-M3 identified that the Phase 2 entry gate enforces only checks 1b,2,3,5,8,10,12 — and its fix patch adds checks 2, 3, 5, 8, 10, 12. However, BUG-M3's description and fix patch both omit check #1 (120 lines), which was implicitly included in the "backstop" intent but never explicitly listed in BUG-M3's scope.

After applying BUG-M3's fix patch, the Phase 2 entry gate still permits an EXPLORATION.md that has exactly 6 required section titles with single-line placeholder content (total: ~15 lines) — well below the 120-line minimum from check #1. This EXPLORATION.md passes Phase 2 entry gate even after BUG-M3's fix.

**Severity**: LOW

**Spec basis**: REQ-028 (Tier 3, new, extends REQ-003/BUG-M3) — "The Phase 2 entry gate must enforce Phase 1 completion gate check #1 (at least 120 lines of substantive content in EXPLORATION.md) in addition to the structural checks added by the BUG-M3 fix." The 120-line floor is the simplest mechanical guard against completely empty exploration artifacts.

**Regression test**: `quality/patches/BUG-L25-regression-test.patch`

**Fix patch**: `quality/patches/BUG-L25-fix.patch`
