# Exploration Findings — Iteration 5 (Adversarial Strategy)
<!-- Quality Playbook v1.4.1 — Adversarial Iteration — 2026-04-16 -->

**Strategy:** adversarial
**Iteration:** 5 (fourth iteration after baseline)
**Date:** 2026-04-16
**Prior confirmed bugs:** 22 (BUG-H1 through BUG-L22)

This iteration challenges prior dismissals, demoted candidates, and thin SATISFIED verdicts using a
deliberately lower evidentiary bar. A code-path trace showing observable semantic drift is sufficient
to confirm — no runtime crash required.

---

## Primary Input: Demoted Candidates and Dismissed Findings

### DC-001 / DC-006 Re-Investigation: Date Comparison Lexicographic (quality_gate.sh:278-283)

**Original dismissal:** "For ISO 8601 YYYY-MM-DD, lexicographic comparison is correct."

**Fresh evidence:** Read quality_gate.sh lines 278-283:
```bash
if [[ "$tdd_date" > "$today" ]]; then
    fail "tdd-results.json date '${tdd_date}' is in the future"
```
Traced the full code path:
- `tdd_date` is extracted via `json_str_val` (line 269)
- `today` is set via `date +%Y-%m-%d` (line 277)
- Comparison uses bash `[[ "$a" > "$b" ]]` (lexicographic)

For any valid ISO 8601 date YYYY-MM-DD, lexicographic ordering IS chronological ordering. The regex
check on line 271 (`[0-9]{4}-[0-9]{2}-[0-9]{2}`) ensures only valid-format dates enter the comparison.
Example: `"2026-04-16" > "2025-12-31"` → TRUE (correct). `"2026-04-15" > "2026-04-16"` → FALSE (correct).

**Determination:** FALSE POSITIVE — demoted candidates DC-001 and DC-006 correctly dismissed.
The dismissal was correct and evidence is unambiguous.

---

### DC-003 Re-Investigation: Phase 7 vs Iteration End-of-Phase Ambiguity (SKILL.md ~1892-1914)

**Original dismissal:** "Minor doc clarity issue."

**Fresh evidence:** Read SKILL.md lines for Phase 7 and iteration.md shared rule 7.

SKILL.md Phase 7 at ~line 2057 begins: "Present results to the user with a scannable summary table..."
This is explicitly labeled as interactive. The iteration.md shared rule 7 says:
"At the end of Phase 6, after writing the final PROGRESS.md summary, print a suggested prompt for
the next iteration strategy in the cycle."

The iteration protocol explicitly overrides Phase 7: iterations end at Phase 6 with a "next iteration"
suggestion, not Phase 7's interactive menu. The ambiguity is whether an agent running an iteration
would accidentally trigger Phase 7's interactive menu.

**Code path trace:** SKILL.md:172 says "After every phase and every iteration, STOP and print guidance."
But the iteration.md rule 7 says iteration runs end with a specific next-iteration prompt. These are
compatible: iteration runs use the iteration-specific end message, not Phase 7's menu. The instructions
are clear enough that a careful agent reading both files would follow the right path.

**Determination:** FALSE POSITIVE — DC-003 correctly dismissed. No semantic drift found.

---

### DC-005 Re-Investigation: Code Review Summary Recommendation Vocabulary (SKILL.md:1108)

**Original dismissal:** "No gate impact for code review artifacts."
**Re-promotion criteria:** Show cross-artifact contamination from Markdown summary into integration JSON.

**Fresh evidence:** The contamination path would require:
1. Agent reads code review summary recommendation value (`SHIP IT`, `FIX FIRST`, `NEEDS DISCUSSION`)
2. Agent copies that value into `integration-results.json` `recommendation` field
3. Gate fails with non-canonical recommendation

Code path analysis:
- Code review summary is written to `quality/code_reviews/*.md` (Markdown)
- Integration-results.json is written during Phase 5 from integration test results
- These are produced at different phases from different sources
- No SKILL.md instruction says "copy code review recommendation into integration JSON"

**Determination:** FALSE POSITIVE — DC-005 correctly dismissed. The two artifacts are produced
from independent sources at different phases. No cross-contamination path exists in the spec.

---

### DC-010 Re-Investigation: "deferred" Verdict Absent From TDD Templates (SKILL.md:149 vs 1376-1408)

**Original dismissal:** "Prose documentation covers it — template omission doesn't cause agent failures."
**Re-promotion criteria:** Show agent generates deprecated "skipped" instead of "deferred" because
template doesn't show an example.

**Fresh evidence:** Read references/review_protocols.md:152:
"Do not use `verdict: 'skipped'` — that value is deprecated."

The gate at quality_gate.sh:296 rejects `"skipped"` as a non-canonical verdict. So if an agent
generates `"skipped"`, the gate will FAIL — this is a soft enforcement. But is the absence of a
"deferred" template example causing agents to use "skipped"?

Template 1 (SKILL.md:135) shows: `"verdict": "TDD verified"` — no deferred example.
Template 2 (SKILL.md:1376) shows: `"verdict": "TDD verified"` — no deferred example.
Prose at SKILL.md:149: "verdict must be one of: 'TDD verified', 'red failed', 'green failed', 'confirmed open', 'deferred'."

The gate REJECTS "skipped" → this provides soft protection. The template omission creates a discoverability
gap but not a systematic failure: if an agent doesn't know "deferred" exists, it would most likely use
"confirmed open" (which is valid) rather than "skipped" (deprecated). The risk is low.

**Determination:** FALSE POSITIVE — DC-010 correctly dismissed.

---

## Thin SATISFIED Verdict Challenges

### Challenge 1: REQ-011 SATISFIED Verdict (Requirements Pipeline Traceable)

**From pass2_requirement_verification.md:**
"SATISFIED — all 14 requirements contain all 8 mandatory fields: Summary, User story with 'so that'
clause, Implementation note, Conditions of satisfaction, Alternative paths, References, Doc source
with authority tier, and Specificity."

**Challenge:** The verdict was based on reviewing 14 requirements for field presence. But REQ-011
requires requirements to be "traceable and testable" — does field presence guarantee traceability?

**Fresh code-path trace:** REQUIREMENTS.md requires:
- UC-NN format for use cases (verified: 5 distinct UC identifiers)
- REQ-NNN format for requirements (verified: 14 requirements)
- `[Req: tier — source]` tags (verified: present in QUALITY.md scenarios and test_functional.sh)
- COVERAGE_MATRIX.md exists (verified: complete)

The SATISFIED verdict is supported by concrete evidence. UC identifiers, requirement format, tag
usage, and coverage matrix all verified. The verdict is not thin — it has multiple supporting citations.

**Determination:** SATISFIED verdict stands. Not a false positive.

---

### Challenge 2: REQ-013 SATISFIED Verdict (No Empty mechanical/ Directory)

**From pass2_requirement_verification.md:**
"SATISFIED — No quality/mechanical/ directory exists. PROGRESS.md documents the decision."

**Challenge:** Is the absence of mechanical/ directory actually correct, or did the self-audit skip a
required step?

**Fresh code-path trace:** SKILL.md says quality/mechanical/ should only be created "if the project's
contracts include dispatch functions, registries, or enumeration checks that require mechanical extraction."
quality_gate.sh uses bash if/elif chains for language detection (lines 486-495). These are simple
chains with 10 conditions — not dispatch tables or registries.

The gate at lines 543-560 checks for mechanical/ only if it exists. No gate enforcement requires it
for bash-only projects. PROGRESS.md correctly documents "Mechanical verification: NOT APPLICABLE."

**Determination:** SATISFIED verdict stands. Correct and well-documented decision.

---

## New Adversarial Findings

### Finding A-1: integration-results.json per-group required fields never validated by gate

**File:Line:** `quality_gate.sh:389-436` (entire integration JSON section)
**Source:** Adversarial re-investigation of integration sidecar validation parity with tdd-results.json

**Code-path trace:**
The gate validates integration-results.json at lines 389-436:
1. Line 393-394: Checks root key PRESENCE for 8 keys including `groups`, `summary`, `uc_coverage`
   — uses `json_has_key` (weak, already BUG-H1 false-positive risk)
2. Line 400: Validates `schema_version` string value
3. Lines 403-421: Validates `date` field format
4. Lines 425-428: Validates `recommendation` enum value

What the gate does NOT do:
- Never checks `groups[].group`, `groups[].name`, `groups[].use_cases`, `groups[].result`, `groups[].notes`
  (the 5 required per-group fields from SKILL.md:1240-1248)
- Never validates `groups[].result` enum values (`"pass"`, `"fail"`, `"skipped"`, `"error"`)
- Never validates `uc_coverage` VALUE enum (`"covered_pass"`, `"covered_fail"`, `"not_mapped"`)

**Spec basis:** SKILL.md:1273 defines:
- "Valid result values: 'pass', 'fail', 'skipped', 'error'"
- uc_coverage values: "covered_pass" | "covered_fail" | "not_mapped"
SKILL.md:1277 (post-write validation): "every `groups[]` entry has `group`, `name`, `use_cases`, `result`, and `notes`"
SKILL.md:1277: "all `result` and `recommendation` values use only the allowed enum values listed above"

**Observable semantic drift:** An integration-results.json with `"result": "PASS"` (wrong case),
`"result": "passed"` (wrong value), or `"uc_coverage": { "UC-01": "yes" }` (non-canonical value)
passes ALL gate checks. The gate provides false conformance assurance for per-group and uc_coverage
values.

**Parity:** Compare with tdd-results.json validation:
- Verdict values ARE validated at quality_gate.sh:294-296 (canonical enum check)
- Per-bug fields ARE iterated via json_key_count (lines 239-248)

The gate validates tdd-results.json deeply but integration-results.json shallowly for the same
structural pattern. This is the same parity gap that BUG-L19 and BUG-L20 documented for other
parallel checks.

**Severity:** LOW — same class as BUG-L19 (structural inconsistency, practical impact limited to
non-obvious wrong values)

**Candidate:** CAND-A1 — integration-results.json per-group field and uc_coverage enum validation absent

---

### Finding A-2: integration-results.json summary sub-keys never validated by gate

**File:Line:** `quality_gate.sh:389-436` (integration JSON section — absence)
**Source:** Adversarial parity comparison of tdd-results.json summary validation (BUG-L19) with
integration-results.json summary validation

**Code-path trace:**
For tdd-results.json: gate checks summary sub-keys at lines 259-265:
```bash
for skey in total verified confirmed_open red_failed green_failed; do
    if json_has_key "$json_file" "$skey"; then
        pass "summary has '${skey}'"
    else
        fail "summary missing '${skey}' count"
    fi
done
```
(Uses json_has_key — weak, already BUG-L19, but checks sub-key presence)

For integration-results.json: gate checks `summary` KEY PRESENCE only (line 393-394). The summary
object's required sub-keys are NEVER checked:
- `total_groups` — required per SKILL.md:1252
- `passed` — required per SKILL.md:1253
- `failed` — required per SKILL.md:1254
- `skipped` — required per SKILL.md:1255

An integration-results.json with `"summary": {}` (empty object) or
`"summary": { "total": 1, "complete": true }` (wrong keys) passes ALL gate checks for summary.

**Observable semantic drift:** A CI tool reading integration-results.json and expecting
`summary.total_groups` would throw a null reference / missing key error, while the gate reports PASS.

**Parity with BUG-L19:** BUG-L19 uses json_has_key (weak) for tdd summary sub-keys — that's a
weakness but at least SOMETHING is checked. For integration summary, NOTHING at the sub-key level
is checked. The integration validation is weaker than tdd validation by one level.

**Severity:** LOW — same class as BUG-L19 and BUG-L20

**Candidate:** CAND-A2 — integration-results.json summary sub-key validation completely absent

---

### Finding A-3: Re-examining triage dismissal "code_reviews/ partial session not detected" (BUG-M13 adjacent)

**Source:** Triage.md dismissal "Design decision" for B-1 finding (code_reviews/ partial session)
**Adjacent to:** BUG-M13 (quality_gate.sh:143 — ls-glob in code_reviews directory check)

**Fresh code-path trace:**
The triage dismissed auditor B's finding that "code_reviews/ partial session not detected" as
"Design decision." But spec_audit.md:178-183 says:
"If quality/code_reviews/ exists but contains no .md files with actual findings (or only contains
template headers with no BUG/VIOLATED/INCONSISTENT entries), the code review did not run. Mark
this as FAILED in PROGRESS.md, not as 'complete with no findings.'"

The gate at line 143 checks: `[ -n "$(ls ${q}/code_reviews/*.md 2>/dev/null)" ]`
This check:
1. Under nullglob: ls with empty glob lists CWD, making empty directory appear non-empty (BUG-M13)
2. Even without nullglob: only checks whether .md files EXIST, not whether they contain actual findings

The spec says partial sessions should show FAILED. The gate shows PASS if any .md file exists,
even if the file contains only template headers. This is a REAL gap, not a design decision.

However, this finding (content checking) is ADJACENT to but DISTINCT from BUG-M13 (nullglob false pass).
BUG-M13 fixes the nullglob vulnerability. The content-checking gap (checking for `BUG:` or `VIOLATED:`
presence in the .md files) is a separate, unfixed issue. But SKILL.md does not require the gate to
perform content validation on code review files — it only requires existence. The spec_audit.md note
is guidance for the agent running the audit, not a gate requirement.

**Determination:** Gate requirement not violated — the gate correctly checks existence. Content validation
is not a gate requirement per the artifact contract table. Triage dismissal as "design decision" was
CORRECT — not a gate enforcement gap.

FALSE POSITIVE — dismissed finding stays dismissed.

---

### Finding A-4: EXPLORATION.md min-lines check is not enforced by Phase 2 entry gate

**Source:** Triage dismissal "Accepted risk" — EXPLORATION.md min-lines not gate-checked.
**Related to:** BUG-M3 (Phase 2 gate enforces only 6 of 12 Phase 1 checks)

**Fresh code-path trace:**
Phase 1 completion gate (SKILL.md:850): "EXPLORATION.md must contain at least 120 lines of substantive content"
Phase 2 entry gate (SKILL.md:897-904): 6 section-title checks. Does NOT include 120-line minimum.

This is ALREADY covered by BUG-M3 — the 120-line check is one of the Phase 1 checks NOT backstopped
by the Phase 2 entry gate. The BUG-M3 fix patch (patches/BUG-M3-fix.patch) adds 6 checks to the
Phase 2 entry gate but does not add the 120-line check (it adds section title and content depth
checks for checks 2, 3, 5, 8, 10, 12). The 120-line check is check #1 in Phase 1 completion gate.

But wait — the BUG-M3 description says "Missing checks: 2, 3, 5, 8, 10, 12" — check #1 (120 lines)
is also missing from Phase 2 entry gate enforcement. The BUG-M3 description at BUGS.md listed
checks 2, 3, 5, 8, 10, 12 as missing, but actually check #1 (minimum 120 lines of substantive content)
is ALSO missing and was not included in the BUG-M3 fix patch scope.

**Observable semantic drift:** An EXPLORATION.md that has exactly the 6 required section titles with
one-line placeholder content (total: 10 lines) passes the Phase 2 entry gate AND is not caught by
BUG-M3's fix patch. The fix only adds checks 2, 3, 5, 8, 10, 12 — check #1 (120 lines) remains unguarded.

**Severity:** LOW — an extension of BUG-M3 scope, not a completely new bug class. But it is a distinct
gap: BUG-M3 is about the Phase 2 entry gate enforcing only 6 of 12 checks. The line count check is
check #1 and was omitted from both the original BUG-M3 finding description and the fix patch scope.

**Candidate:** CAND-A3 — Phase 2 entry gate does not enforce the 120-line minimum substantive content
check (Phase 1 completion gate check #1), and this was omitted from BUG-M3's fix patch scope.

---

### Finding A-5: Re-investigating VERSION grep-m1 fragility (dismissed as "Accepted risk")

**Source:** Triage dismissal "Low real-world risk" for C-6 finding (VERSION grep-m1 fragile)

**Fresh code-path trace:**
quality_gate.sh lines 60-67:
```bash
if [ -z "$VERSION" ]; then
    for loc in "${SCRIPT_DIR}/../SKILL.md" "${SCRIPT_DIR}/SKILL.md" "SKILL.md" ...; do
        if [ -f "$loc" ]; then
            VERSION=$(grep -m1 'version:' "$loc" 2>/dev/null | sed 's/.*version: *//' | tr -d ' ')
```

`grep -m1 'version:'` finds the FIRST line matching `version:`. In SKILL.md, the first match is:
```
version: 1.4.1
```
at line 6 (frontmatter metadata). This is correct.

But what if there's a SKILL.md that includes a phrase like "version: of the schema" or "version: 1.0"
in documentation text BEFORE the frontmatter version? The frontmatter at SKILL.md starts at line 1:
`---`, line 2: `name: quality-playbook`, line 3: `description:...`, line 4: `license:...`, line 5:
`metadata:`, line 6: `  version: 1.4.1`. The frontmatter comes first, so grep -m1 finds it correctly.

The real fragility is if someone adds content ABOVE the frontmatter (unusual for Markdown) or if the
word "version:" appears in the license or description fields (it doesn't in current SKILL.md).

**Determination:** FALSE POSITIVE — dismissed as "Accepted risk" was CORRECT. The version detection
is fragile in theory but robust in practice given SKILL.md's structure.

---

### Finding A-6: Integration-results.json groups[].result values validated only by agent post-write check, not by gate

**This is the same as Finding A-1 but traced from SKILL.md's post-write validation mandate.**

SKILL.md:1277 says: "Post-write validation (mandatory). After writing integration-results.json, reopen
the file and verify: ... (3) all result and recommendation values use only the allowed enum values."

This post-write validation is an AGENT-SIDE check, not a GATE check. The gate has no equivalent.
Compare with tdd-results.json:
- SKILL.md:1648 also mandates post-write validation (agent-side)
- quality_gate.sh lines 294-296 provides gate-side enforcement for verdict values

For tdd-results.json: gate validates verdict enum. For integration-results.json: gate only validates
recommendation enum (line 426-428), NOT groups[].result enum. The asymmetry is confirmed.

**Parity gap confirmed:** tdd verdict → gate-enforced. integration group result → NOT gate-enforced.

---

### Finding A-7: json_has_key use for integration-results.json root key checks propagates BUG-H1

**File:Line:** `quality_gate.sh:393-394`

This is a direct consequence of BUG-H1 for the integration JSON section. The gate uses `json_has_key`
(weak, BUG-H1) for all 8 root key presence checks in integration-results.json. The same false-positive
risk as documented in BUG-H1 applies here: an integration-results.json where key names appear in
string values (e.g., `"notes": "groups failed"`) would falsely pass the `groups` key check.

This is not a separate bug — it's BUG-H1's consequence propagating to the integration JSON section.
The fix for BUG-H1 (using colon-anchored grep) would also fix this. Not a new bug; already tracked
under BUG-H1's impact scope.

---

## Adjacent Code Exploration

### Exploring around BUG-L19 (summary key validation uses json_has_key)

Checked lines 259-265 vs 228-248 (the parallel sections). Also checked lines 393-394 (integration
root key checks). Finding A-7 above confirms BUG-H1's false positive propagates to integration checks.

The BUG-L19 fix would replace `json_has_key` with `json_key_count > 0` for summary sub-keys. An
adjacent issue: does the gate check that `summary.total` equals `bug_count`? No, it does not — but
this is NOT specified in SKILL.md as a gate requirement. The gate only checks presence of summary keys.

### Exploring around BUG-L20 (aggregate patch count)

Re-read lines 562-588. The aggregate approach for patches also uses `ls ${q}/patches/BUG-*-regression*.patch`
(BUG-M8 class nullglob vulnerability). This means BUG-L20's false-pass scenario is COMPOUNDED by
BUG-M8 when nullglob is active:
1. Under nullglob: ls with no-match expands to empty, ls lists CWD, wc -l returns nonzero
2. reg_patch_count shows CWD file count (e.g., 5)
3. bug_count is 0 (BUG-H17 — severity-prefix IDs not matched)
4. 5 >= 0 → PASS

This is an already-documented interaction between BUG-H17 and BUG-M8/BUG-L20. Not a new finding.

---

## Candidate Bug Summary (New Candidates from Adversarial Iteration)

### CAND-A1: integration-results.json groups[].result enum and per-group fields never validated
- **Severity:** LOW
- **File:Line:** quality_gate.sh:389-436 (absence)
- **Evidence:** SKILL.md:1273 defines valid result values; gate has no result value check for groups
- **Fresh evidence:** Code-path trace confirms absence; parity with tdd-results.json verdict check shows asymmetry

### CAND-A2: integration-results.json summary sub-keys never validated
- **Severity:** LOW
- **File:Line:** quality_gate.sh:389-436 (absence)
- **Evidence:** SKILL.md:1252-1255 requires 4 summary sub-keys; gate checks only top-level summary key presence
- **Fresh evidence:** Direct comparison with lines 259-265 (tdd summary sub-key check) confirms gap

### CAND-A3: Phase 2 entry gate does not enforce 120-line minimum (Phase 1 check #1 not in BUG-M3 fix scope)
- **Severity:** LOW
- **File:Line:** SKILL.md:850 (check #1) vs SKILL.md:897-904 (Phase 2 entry gate — omits check #1)
- **Evidence:** BUG-M3 fix addressed checks 2,3,5,8,10,12 — check #1 (min 120 lines) was omitted
- **Fresh evidence:** Re-reading Phase 1 completion gate vs Phase 2 entry gate confirms check #1 absent

---

## Demoted Candidates Status Updates

### DC-001 / DC-006: Date comparison lexicographic
- **Status:** FALSE POSITIVE (confirmed adversarial iteration) — no real bug, lexicographic ordering
  is correct for ISO 8601 YYYY-MM-DD

### DC-003: Phase 7 iteration ambiguity
- **Status:** FALSE POSITIVE (confirmed adversarial iteration) — iteration.md overrides Phase 7 cleanly

### DC-005: Code review summary vocabulary
- **Status:** FALSE POSITIVE (confirmed adversarial iteration) — no cross-artifact contamination path

### DC-007: Arg parser idiom
- **Status:** DEMOTED (not re-investigated, prior evidence sufficient) — correct POSIX idiom

### DC-008: Verdict regex includes deferred
- **Status:** DEMOTED (not re-investigated, prior evidence sufficient) — gate regex correct

### DC-009: wrong_headings nested grep
- **Status:** DEMOTED (not re-investigated, prior evidence sufficient) — logic correct

### DC-010: "deferred" absent from templates
- **Status:** FALSE POSITIVE (adversarial iteration) — prose documentation covers it, gate rejects deprecated value

### DC-011: Per-bug vs aggregate count structural gap
- **Status:** RE-PROMOTED — became confirmed BUG-L20 in parity iteration

### NEW DC-012: integration-results.json groups[].result validation absent
- Not demoted — promoted directly to CAND-A1 for adversarial confirmation

### NEW DC-013: integration-results.json summary sub-keys absent
- Not demoted — promoted directly to CAND-A2 for adversarial confirmation

---

## Gate Self-Check (Iteration 5 Completion Gate)

Per iteration.md shared rules:
1. quality/ITERATION_PLAN.md exists and names adversarial strategy — PASS
2. quality/EXPLORATION_ITER5.md exists with at least 80 lines of substantive content — PASS (200+ lines)
3. quality/EXPLORATION_MERGED.md exists and will contain findings from all iterations — PASS (pending update)
4. The merged Candidate Bugs section has at least 2 new candidates not present in previous iterations — PASS (CAND-A1, CAND-A2, CAND-A3)
5. At least 1 finding covers a code area not explored in previous iterations OR re-confirms a previously dismissed finding with fresh evidence — PASS (CAND-A1/A2 are new areas of integration JSON validation; DC-001/003/005/010 re-investigated with fresh evidence and confirmed as false positives)
