# Pass 3: Cross-Requirement Consistency — quality-playbook

<!-- Quality Playbook v1.4.1 — Phase 3 Code Review — 2026-04-16 -->

This pass compares pairs of requirements that reference the same field, function, or policy. For each pair, it checks whether their constraints are mutually consistent.

---

#### Shared Concept: JSON Validation Helpers (json_has_key, json_str_val, json_key_count)

**Requirements**: REQ-001, REQ-007

**What REQ-001 claims**: `json_has_key()` must verify the key appears as an actual JSON key (preceding `:`), not merely as a substring of a string value.

**What REQ-007 claims**: `json_str_val()` must return a distinguishable signal when the key exists but has a non-string value, so callers can generate accurate error messages.

**Consistency**: CONSISTENT

**Code evidence**:
- REQ-001: `quality_gate.sh:77` — `grep -q "\"${key}\"" "$file"` (missing colon anchor — violates REQ-001)
- REQ-007: `quality_gate.sh:81-85` — `grep -o "\"${key}\"[[:space:]]*:[[:space:]]*\"[^\"]*\""` (returns empty for non-string — violates REQ-007)

**Analysis**: Both requirements address deficiencies in the JSON validation helpers, but they address different failure modes. REQ-001 is about false positives (key found when it shouldn't be). REQ-007 is about uninformative errors (can't distinguish absent from wrong type). These requirements do not contradict each other — fixing REQ-001 (add colon anchor to `json_has_key`) does not affect REQ-007 (return sentinel from `json_str_val`). Both can be fixed independently without conflict.

---

#### Shared Concept: REPO_DIRS and all checks depending on correct paths

**Requirements**: REQ-002, REQ-009, REQ-012

**What REQ-002 claims**: The `resolved` array reconstruction at line 697 must preserve spaces in paths.

**What REQ-009 claims**: Generated artifact version stamps must match SKILL.md frontmatter; gate must FAIL when any artifact has a wrong version stamp.

**What REQ-012 claims**: When VERSION is empty and `--all` is specified, gate must emit a clear error, not a silent no-op.

**Consistency**: CONSISTENT but with compounding failure modes

**Code evidence**:
- REQ-002: `quality_gate.sh:697` — unquoted array expansion
- REQ-009: `quality_gate.sh:625-649` — version stamp checks run inside `check_repo()`
- REQ-012: `quality_gate.sh:678` — `--all` glob `*-"${VERSION}"/`

**Analysis**: These requirements are consistent — none contradicts another. However, they compound: if BUG-H2 (REQ-002) corrupts REPO_DIRS for space-containing paths, then all downstream checks including REQ-009's version stamp checks run against wrong paths. REQ-009 may then produce a spurious PASS (version check skipped because the path doesn't exist) rather than a correct FAIL (version mismatch found). The three requirements are independent in specification but interact in execution: fixing REQ-002 is a prerequisite for REQ-009 working correctly on space-containing paths.

**Impact**: On macOS with paths containing spaces, REQ-009's version stamp enforcement is silently bypassed, creating a false sense of conformance.

---

#### Shared Concept: Phase Gate Completeness (Phase 1 → Phase 2 enforcement)

**Requirements**: REQ-003, REQ-010

**What REQ-003 claims**: The Phase 2 entry gate must enforce all 12 Phase 1 checks, or explicitly document accepted risk.

**What REQ-010 claims**: EXPLORATION.md must contain ≥120 substantive lines, ≥8 concrete findings, ≥5 domain risks, 3-4 FULL patterns before Phase 2 may begin.

**Consistency**: INCONSISTENT

**Code evidence**:
- REQ-003: `SKILL.md:897-904` — Phase 2 entry gate checks for 6 section title presences only
- REQ-010: `SKILL.md:847-862` — Phase 1 completion gate checks for substantive content (120+ lines, 8+ findings, etc.)

**Analysis**: REQ-010 specifies what EXPLORATION.md must contain (substantive content). REQ-003 specifies that Phase 2 must not start unless those substantive content requirements are met. But the Phase 2 entry gate only verifies section title presence, not content depth. An EXPLORATION.md with the correct 6 section titles but fewer than 120 lines, only 3 findings, and only 1 FULL pattern passes the Phase 2 entry gate while violating REQ-010. The two requirements are mutually inconsistent in their enforcement: REQ-010 specifies stricter preconditions than REQ-003's current enforcement mechanism ensures. Fixing REQ-003 (adding all 12 checks to Phase 2 gate) would automatically enforce REQ-010.

**Impact**: Phase 2 can produce artifacts from shallow exploration that lack function-level detail, causing Phase 3 code review to miss requirement-violation bugs.

---

#### Shared Concept: Artifact Contract vs Gate Enforcement

**Requirements**: REQ-004, REQ-009

**What REQ-004 claims**: Gate must FAIL when bugs exist but `quality/test_regression.*` file is absent.

**What REQ-009 claims**: All generated artifacts (including test files) must have version stamps matching SKILL.md frontmatter; gate must FAIL on mismatch.

**Consistency**: CONSISTENT but with enforcement gap interaction

**Code evidence**:
- REQ-004: `quality_gate.sh:562-588` — checks patches but not test file existence
- REQ-009: `quality_gate.sh:625-649` — checks PROGRESS.md and tdd-results.json version stamps; does not check `test_regression.*` stamp

**Analysis**: These requirements address different aspects of the same artifact (`test_regression.*`) and are not in conflict. However, there is a compounding gap: REQ-004 says the file must exist; REQ-009 says if it exists, its version stamp must match. Since REQ-004's existence check is absent from the gate, REQ-009's version check for this file is also absent. Both requirements are violated together in the same code region. Fixing REQ-004 (add existence check) would enable REQ-009 to be enforced for `test_regression.*` files.

---

#### Shared Concept: Phase 0 / Phase 0b Activation Conditions

**Requirements**: REQ-005, REQ-003

**What REQ-005 claims**: Phase 0b must activate when `previous_runs/` exists but is empty (not only when absent).

**What REQ-003 claims**: Phase 2 entry gate must enforce all 12 Phase 1 checks.

**Consistency**: CONSISTENT but independent

**Code evidence**:
- REQ-005: `SKILL.md:271,295-297` — Phase 0a/0b logic
- REQ-003: `SKILL.md:897-904` — Phase 2 entry gate

**Analysis**: REQ-005 and REQ-003 address different phases (Phase 0 vs Phase 1/2 boundary) and do not interact. Fixing Phase 0b activation does not affect Phase 2 gate completeness, and fixing Phase 2 gate does not affect Phase 0b. They are independent specification gaps in different phase boundaries. No inconsistency.

---

#### Shared Concept: Version Consistency (SKILL.md internal vs generated artifacts)

**Requirements**: REQ-006, REQ-009

**What REQ-006 claims**: Every hardcoded version string in SKILL.md must match `metadata.version`. A mechanical check must detect any discrepancy within SKILL.md itself.

**What REQ-009 claims**: Every generated artifact must include a version stamp matching `metadata.version`. Gate must FAIL on mismatch.

**Consistency**: INCONSISTENT — complementary requirements with different scopes

**Code evidence**:
- REQ-006: SKILL.md lines 6, 39, 129, 156, 915, 922, 1056, 1966 — all `1.4.1`; no mechanical check exists
- REQ-009: `quality_gate.sh:625-649` — gate checks generated artifact stamps

**Analysis**: REQ-006 covers SKILL.md-internal consistency (source specification). REQ-009 covers generated artifact stamps (outputs). They address different things: REQ-006 ensures the specification itself is internally consistent; REQ-009 ensures the artifacts generated FROM the specification carry the right version. However, they are connected: if REQ-006 fails (a stale JSON example in SKILL.md at line 129 carries `1.3.27`), agents following that example will generate artifacts stamped `1.3.27`, which then fails REQ-009 at the gate. REQ-009 would catch the downstream consequence of REQ-006 failure. The two requirements are not contradictory — they form a chain. But they are inconsistently enforced: REQ-009 has gate enforcement (partial), REQ-006 has no enforcement.

**Impact**: A version bump that updates frontmatter but leaves JSON examples stale produces gate failures (REQ-009) but no specification-level warning (REQ-006). The failure is caught eventually but without pointing to the root cause (stale JSON example).

---

#### Shared Concept: Empty VERSION and --all Mode

**Requirements**: REQ-012, REQ-002

**What REQ-012 claims**: When VERSION is empty and `--all` mode is used, gate must emit a clear error naming VERSION as the failure cause.

**What REQ-002 claims**: Repo paths with spaces must be preserved through array reconstruction.

**Consistency**: CONSISTENT but with interaction in --all mode

**Code evidence**:
- REQ-012: `quality_gate.sh:678` — `for dir in "${SCRIPT_DIR}/"*-"${VERSION}"/;`
- REQ-002: `quality_gate.sh:697` — `REPO_DIRS=(${resolved[@]+"${resolved[@]}"})` (only applies to non-`--all` mode)

**Analysis**: REQ-002's array reconstruction bug at line 697 only applies to the `else` branch at lines 685-698, when `CHECK_ALL=false` and a named repo list is provided. When `--all` is true, the array is populated at lines 678-679 using a glob expansion that is properly quoted (`"${SCRIPT_DIR}/"*-"${VERSION}"/`). So BUG-H2 and REQ-012's empty-VERSION gap are in non-overlapping code branches. They do not interact. Both are independent violations.

---

#### Shared Concept: Mechanical Verification Applicability

**Requirements**: REQ-013, REQ-003

**What REQ-013 claims**: `quality/mechanical/` must only exist when contracts include dispatch functions; must not be created for projects without such contracts.

**What REQ-003 claims**: Phase 2 entry gate must enforce all 12 Phase 1 checks.

**Consistency**: CONSISTENT

**Code evidence**:
- REQ-013: `SKILL.md:~578` — "Do not create an empty mechanical/ directory"
- REQ-003: `SKILL.md:897-904` — Phase 2 entry gate
- `quality_gate.sh:543-560` — mechanical verification check: only runs if `quality/mechanical/` directory exists

**Analysis**: The gate's mechanical check is conditional on the directory existing (line 545: `if [ -d "${q}/mechanical" ]`). If the directory is absent, the gate emits `INFO: No mechanical/ directory` and passes. This is consistent with REQ-013 — when mechanical verification is not applicable, the gate does not require it. REQ-003 does not reference mechanical verification. No inconsistency between these requirements.

---

## Combined Summary

| Source | Finding | Severity | Status |
|--------|---------|----------|--------|
| Pass 1, quality_gate.sh:77 | `json_has_key` false positives from string values | HIGH | BUG |
| Pass 1, quality_gate.sh:81-85 | `json_str_val` silent empty for non-string values | LOW | BUG |
| Pass 1, quality_gate.sh:88-91 | `json_key_count` comment misleading (can match in strings) | LOW | BUG |
| Pass 1, quality_gate.sh:124 | Unquoted glob for functional test detection | LOW | BUG |
| Pass 1, quality_gate.sh:686,697 | Unquoted array expansion corrupts paths with spaces | HIGH | BUG |
| Pass 1, SKILL.md:37/376 | Mandatory First Action lacks autonomous-mode qualifier | MEDIUM | BUG |
| Pass 1, SKILL.md:271/295-297 | Phase 0b skips when previous_runs/ exists but empty | MEDIUM | BUG |
| Pass 1, SKILL.md:897-904 | Phase 2 entry gate enforces only 6 of 12 Phase 1 checks | MEDIUM | BUG |
| Pass 2, REQ-001 | json_has_key matches string values | HIGH | VIOLATED |
| Pass 2, REQ-002 | Array reconstruction corrupts space-containing paths | HIGH | VIOLATED |
| Pass 2, REQ-003 | Phase 2 gate incomplete (6 of 12 checks) | MEDIUM | VIOLATED |
| Pass 2, REQ-004 | Gate does not check test_regression.* existence | MEDIUM | VIOLATED |
| Pass 2, REQ-005 | Phase 0b empty-dir edge case | MEDIUM | VIOLATED |
| Pass 2, REQ-007 | json_str_val misleading for non-string values | LOW | VIOLATED |
| Pass 2, REQ-008 | Mandatory First Action missing autonomous-mode qualifier | MEDIUM | VIOLATED |
| Pass 2, REQ-012 | Empty VERSION produces ambiguous usage message | MEDIUM | VIOLATED |
| Pass 2, REQ-014 | Functional test detection uses ls vs find inconsistency | LOW | VIOLATED |
| Pass 3, REQ-003 vs REQ-010 | Phase gate enforcement inconsistency | MEDIUM | INCONSISTENT |
| Pass 3, REQ-006 vs REQ-009 | Version enforcement chain — no internal SKILL.md check | LOW | INCONSISTENT |

**Total findings:**
- Pass 1: 8 confirmed BUGs, 3 QUESTIONs, 1 INCOMPLETE
- Pass 2: 9 VIOLATED, 3 PARTIALLY SATISFIED, 2 SATISFIED
- Pass 3: 2 INCONSISTENT pairs, 6 CONSISTENT pairs

**Overall assessment: FIX FIRST**

Two HIGH severity bugs (BUG-H1: json_has_key false positives; BUG-H2: path space corruption) directly compromise the gate's reliability. All five MEDIUM bugs (Phase 2 gate completeness, test_regression.* enforcement, Phase 0b empty-dir, Mandatory First Action scope, empty VERSION message) are specification/enforcement gaps that reduce the system's correctness. The two LOWs (json_str_val, version references) are latent risks that do not cause incorrect verdicts in normal operation.
