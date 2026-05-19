# Exploration Findings — Iteration 2 (Gap Strategy)
<!-- Quality Playbook v1.4.1 — Gap Iteration — 2026-04-16 -->

## Strategy: gap
## Iteration: 2

---

## Coverage Map Summary

The baseline run (Iteration 1) explored these areas deeply:
- quality_gate.sh: JSON helper functions (json_has_key, json_str_val, json_key_count), array expansion, ls-glob, repo resolution fallbacks, Phase 0b seed discovery
- SKILL.md: Phase 1/2 gate consistency, Mandatory First Action, version references, Phase 0b spec
- Confirmed bugs: BUG-H1 through BUG-L11 (11 bugs total)

**NOT explored in baseline (identified gaps):**
1. Phase 7 (Present, Explore, Improve) — interactive phase completeness
2. Recheck Mode (SKILL.md ~lines 1918–2055) — full spec audit
3. integration-results.json recommendation enum — gate vs. SKILL.md spec
4. quality_gate.sh line 479: `ls ${q}/test_functional.*` — second ls-glob vulnerability
5. quality_gate.sh line 143: `ls ${q}/code_reviews/*.md` — third ls-glob
6. quality_gate.sh line 152–153: `ls ${q}/spec_audits/*triage*` — also ls-based
7. ai_context/TOOLKIT.md claims vs. SKILL.md spec
8. references/review_protocols.md template inconsistency with SKILL.md integration schema
9. integration-results.json per-group field validation in gate

---

## Gap Finding 1: `quality_gate.sh:479` — Second `ls`-glob Vulnerability (Same Pattern as BUG-M8)

**File:Line:** `quality_gate.sh:479`

**Observation:**
```bash
func_test=$(ls ${q}/test_functional.* 2>/dev/null | head -1)
reg_test=$(ls ${q}/test_regression.* 2>/dev/null | head -1)
```
This uses `ls` with unquoted glob patterns, capturing output via command substitution. Under `nullglob` (common zsh/macOS default), when `${q}/test_functional.*` matches nothing, the glob expands to empty and `ls` with no argument lists the current directory. `head -1` then returns the first line of the directory listing, making `func_test` non-empty — so the downstream `if [ -n "$func_test" ]` check at line 481 evaluates TRUE even when no functional test file exists. The gate then proceeds to language extension validation using a spurious filename, producing misleading extension mismatch errors.

**Cross-function trace:** 
- Line 479: `func_test=$(ls ${q}/test_functional.* 2>/dev/null | head -1)` → if nullglob + empty, ls lists CWD → head returns a CWD filename
- Line 481: `if [ -n "$func_test" ]` → TRUE (because CWD listing is non-empty)
- Line 482: `local ext="${func_test##*.}"` → extracts extension from a spurious filename
- Line 498: `if [ -n "$detected_lang" ]` → may validate extension of wrong file
- Line 513: passes or fails extension check for the wrong file, potentially FAILING when functional test exists at the right extension

**Bug hypothesis:** The same nullglob vulnerability identified in BUG-M8 manifests here at line 479. Unlike BUG-M8's counting failure (returns wrong count), this one produces a false non-empty string — making the gate check proceed with a wrong filename. The fix used for BUG-M8 (replacing `ls` glob with `find`) should be applied here too.

**Why not in baseline:** The baseline identified BUG-M8 at lines 152–153, 331, 567–568, 595 but the line 479 instance was NOT included in BUG-M8's scope. The code_reviews and spec_audits counting at lines 143, 152–153 were addressed; line 479 was not.

**Spec basis:** Same as BUG-M8 — REQ-002 (Tier 3), reliable artifact detection. The gate must correctly identify functional test files under all shell configurations.

---

## Gap Finding 2: `quality_gate.sh:143` — Directory Listing ls-glob (Third Vulnerability)

**File:Line:** `quality_gate.sh:143`

**Observation:**
```bash
if [ -d "${q}/code_reviews" ] && [ -n "$(ls ${q}/code_reviews/*.md 2>/dev/null)" ]; then
    pass "code_reviews/ has .md files"
else
    fail "code_reviews/ missing or empty"
fi
```
The pattern `ls ${q}/code_reviews/*.md 2>/dev/null` uses an unquoted glob. Under `nullglob`, when no `.md` files exist in `code_reviews/`, the glob expands to empty and `ls` lists the current directory. The command substitution `$(ls ...)` captures this CWD listing, making the `-n` (non-empty) check TRUE. The gate then passes (`pass "code_reviews/ has .md files"`) even when `code_reviews/` exists but is empty, because the CWD listing substitutes for the directory listing.

**Cross-function trace:**
- `[ -d "${q}/code_reviews" ]` — TRUE (directory exists but empty)
- `$(ls ${q}/code_reviews/*.md 2>/dev/null)` — nullglob expands glob to empty → `ls` lists CWD → non-empty output
- `[ -n "$(ls ...)" ]` — TRUE despite no `.md` files in code_reviews/
- `pass "code_reviews/ has .md files"` — false pass

**Bug hypothesis:** An agent that creates the `code_reviews/` directory but fails to write any `.md` files (a partial session) would pass this gate check under nullglob. Combined with the partial session detection rules (spec_audit.md), this means a partial run can silently pass gate checks that should catch it.

**Severity:** MEDIUM — affects partial session detection reliability.

---

## Gap Finding 3: `references/review_protocols.md:410` — Integration Test Protocol Template Uses Wrong Recommendation Enum Values

**File:Line:** `references/review_protocols.md:410`

**Observation:**
The integration test protocol template in `references/review_protocols.md` specifies the recommendation field as:
```
### Recommendation
[SHIP IT / FIX FIRST / NEEDS INVESTIGATION]
```
(line 410)

But `quality_gate.sh` at line 427 validates:
```bash
SHIP|"FIX BEFORE MERGE"|BLOCK) pass "recommendation '${rec}' is canonical" ;;
*) ... fail "recommendation '${rec}' is non-canonical (must be SHIP/FIX BEFORE MERGE/BLOCK)"
```

And SKILL.md at line 1273 states:
```
Valid `recommendation` values: `"SHIP"` (all groups pass), `"FIX BEFORE MERGE"` (failures in non-blocking groups), `"BLOCK"` (failures in critical groups).
```

**Discrepancy:**
| Location | Values |
|----------|--------|
| `references/review_protocols.md:410` | `SHIP IT`, `FIX FIRST`, `NEEDS INVESTIGATION` |
| `quality_gate.sh:427` | `SHIP`, `FIX BEFORE MERGE`, `BLOCK` |
| `SKILL.md:1273` (integration schema) | `SHIP`, `FIX BEFORE MERGE`, `BLOCK` |

An agent following `references/review_protocols.md`'s template and writing `"recommendation": "FIX FIRST"` into `integration-results.json` would fail the gate check at line 427 (`fail "recommendation 'FIX FIRST' is non-canonical"`). The agent was instructed by the reference file to use `FIX FIRST` but the gate requires `FIX BEFORE MERGE`.

**Cross-function trace:** Agent reads `references/review_protocols.md` → generates integration-results.json with `"recommendation": "FIX FIRST"` → gate validates at line 427 → FAIL with "non-canonical recommendation."

**Why this is a real bug:** The template in review_protocols.md is the old enum from the integration test protocol template (which uses human-readable prose labels). When the integration schema was formalized (sidecar JSON with machine-readable values), the template was updated in SKILL.md's File 4 template but NOT in `references/review_protocols.md`. The stale reference still uses the human-readable values.

**Severity:** MEDIUM — agents reading references/review_protocols.md (as instructed by SKILL.md) will generate gate-failing artifacts.

---

## Gap Finding 4: `SKILL.md:1965` — Recheck Mode Uses `schema_version: "1.0"` But All Other Schemas Use `"1.1"`

**File:Line:** `SKILL.md:1965` (recheck-results.json schema definition in Recheck Mode section)

**Observation:**
```json
{
  "schema_version": "1.0",
  "skill_version": "1.4.1",
  ...
}
```
The recheck-results.json schema at SKILL.md line 1965 uses `"schema_version": "1.0"`. But:
- `tdd-results.json` requires `schema_version: "1.1"` (SKILL.md line 1379, quality_gate.sh line 236)
- `integration-results.json` requires `schema_version: "1.1"` (SKILL.md line 1233, quality_gate.sh line 400)
- `references/verification.md` line 110 says: "Both sidecar JSON templates must use `schema_version: "1.1"`"

**Gap:** The `recheck-results.json` was introduced as `"1.0"` and never updated when all other schemas were bumped to `"1.1"`. The verification.md's rule "both sidecar JSON templates must use schema_version: 1.1" appears to refer only to tdd-results.json and integration-results.json (the "both" = those two), but the recheck schema was left at 1.0 creating an inconsistency.

**NOTE:** This was partially identified as BUG-L10 in the baseline, which said "recheck-results.json template uses schema_version '1.0' vs '1.1' everywhere else." Gap exploration confirms the finding with additional evidence: quality_gate.sh does NOT validate recheck-results.json at all — the gate has no checks for this file — so the version inconsistency propagates silently.

**Additional finding from gap exploration:** The gate has NO validation section for `recheck-results.json`. Unlike tdd-results.json (deep validation at lines 221-305) and integration-results.json (validation at lines 389-436), there is no `[Recheck Sidecar JSON]` section in the gate. This means a malformed recheck-results.json (wrong schema_version, missing fields, wrong status enum) passes all gate checks. The artifact contract table at SKILL.md lines 100-119 includes `recheck-results.json` as "When recheck runs" but the gate doesn't check it.

**Severity:** LOW (BUG-L10 already confirmed) / the gate omission is a new MEDIUM finding.

---

## Gap Finding 5: `quality_gate.sh` — Gate Has No Validation for `recheck-results.json`

**File:Line:** `quality_gate.sh` (entire file — absence finding)

**Observation:** Searched the full quality_gate.sh for any reference to `recheck`:
- No `[Recheck]` section exists
- No check for `quality/results/recheck-results.json`
- No validation of recheck status enum values (FIXED, PARTIALLY_FIXED, STILL_OPEN, INCONCLUSIVE)
- No check for `quality/results/recheck-summary.md`

The SKILL.md artifact contract table (line 117-118) lists both files as artifacts "When recheck runs." The gate validates every other conditional artifact (TDD logs: lines 307-387, integration JSON: lines 389-436, patches: lines 562-588, writeups: lines 590-623) but NOT recheck artifacts.

**Spec basis:** SKILL.md lines 117-118: "Recheck results (JSON): quality/results/recheck-results.json — When recheck runs / Recheck" and "Recheck summary (MD): quality/results/recheck-summary.md — When recheck runs / Recheck." These are documented artifact contracts. The gate's failure to validate them means recheck runs have no mechanical conformance check.

**Bug hypothesis:** An agent that runs recheck mode and produces a malformed or incomplete recheck-results.json would not be caught by the gate. Users relying on the gate for recheck validation would have false confidence.

**Severity:** MEDIUM — systematic gap between documented artifact contract and gate enforcement.

---

## Gap Finding 6: `SKILL.md:1108` — Code Review Combined Summary Specifies Wrong `recommendation` Enum Values

**File:Line:** `SKILL.md:1108` and `references/review_protocols.md:94`

**Observation:** 
The code review protocol's combined summary output format specifies:
```
- Overall assessment: SHIP IT / FIX FIRST / NEEDS DISCUSSION
```
(SKILL.md line 1108, references/review_protocols.md line 94)

However, these are human-readable prose values, not machine-readable enum values for the JSON schema. The integration-results.json `recommendation` field uses `SHIP / FIX BEFORE MERGE / BLOCK`. The code review combined summary is NOT a JSON artifact (it's a Markdown file), so this isn't a gate-enforcement bug — but it creates a naming inconsistency where:
- Code review assessment: `SHIP IT / FIX FIRST / NEEDS DISCUSSION`
- Integration results JSON: `SHIP / FIX BEFORE MERGE / BLOCK`
- Integration test protocol Markdown template: `SHIP IT / FIX FIRST / NEEDS INVESTIGATION`

Three different vocabularies for what is conceptually the same "go/no-go" decision. An agent following the code review template would write `FIX FIRST` in the Markdown summary but needs to write `FIX BEFORE MERGE` in the JSON artifact. The inconsistency creates confusion about the correct enum values and makes it harder to understand what values are canonical.

**Cross-function trace:** Agent generates code review (uses `FIX FIRST`) → Agent generates integration-results.json (should use `FIX BEFORE MERGE` per SKILL.md:1273) → if agent copies from code review assessment, writes wrong value → gate FAILs.

**Severity:** LOW — the code review summary is Markdown prose (no gate check), but it seeds incorrect vocabulary that can contaminate the JSON enum values.

---

## Gap Finding 7: `SKILL.md` Phase 7 — End-of-Phase Message Instruction Incomplete for Iteration Runs

**File:Line:** `SKILL.md` Phase 7 section (~lines 2057–2155)

**Observation:** The Phase 7 interactive phase includes an end-of-phase message template for baseline runs with a "Quick Start" block and "drill-down on demand" features. However, Phase 7 also generates the "suggested next iteration" message. 

The `references/iteration.md` Shared Rule 7 specifies that after Phase 6, the skill must print a suggested prompt for the next iteration. SKILL.md's Phase 6 section (~line 1793) says "Print the suggested next prompt to the user (mandatory, all runs)." But Phase 7 also has interactive iteration options — and the two sources give slightly different instructions:

- SKILL.md Phase 6 checkpoint: print suggestion, then STOP
- SKILL.md Phase 7 baseline message (~lines 1856-1890): print suggestion with "run all iterations" option, then STOP
- references/iteration.md Rule 7: print suggestion with exact format, then STOP

**Gap:** When running an iteration (not a baseline), what does Phase 7 show? The iteration end-of-phase message at SKILL.md ~lines 1892-1914 says "Summarize: N net-new bugs found in this iteration, total now at N. List new bug IDs with one-line summaries." But this is the end-of-iteration message, not the Phase 7 interactive menu. The spec is unclear about whether Phase 7 (the interactive exploration/improvement menu) runs after iterations or only after baselines.

**Bug hypothesis:** An agent running an iteration that reaches Phase 6 might skip Phase 7 entirely (because the end-of-iteration message says STOP), denying the user the interactive quality exploration interface. Or it might try to run Phase 7 when the iteration instructions say to stop.

**Severity:** LOW — affects interactive experience, not artifact correctness.

---

## Gap Finding 8: `ai_context/TOOLKIT.md` — Documents 6-Phase Pipeline but SKILL.md Has 7 Phases

**File:Line:** `ai_context/TOOLKIT.md:182-193`

**Observation:**
TOOLKIT.md at lines 182-193 documents the playbook as having 6 phases:
```
> - Phase 1 (Explore): Understand the codebase...
> - Phase 2 (Generate): Produce quality artifacts...
> - Phase 3 (Code Review): Three-pass review...
> - Phase 4 (Spec Audit): Three independent AI auditors...
> - Phase 5 (Reconciliation): Close the loop...
> - Phase 6 (Verify): Self-check benchmarks...
```

But SKILL.md's Phase Overview (lines 10-32) defines 8 phases: Phase 0 (Prior Run Analysis), Phase 1 (Explore), Phase 2 (Generate), Phase 3 (Code Review), Phase 4 (Spec Audit), Phase 5 (Reconciliation), Phase 6 (Verify), **Phase 7 (Present, Explore, Improve)**.

TOOLKIT.md is missing both Phase 0 and Phase 7. Phase 0 is important because it explains seed injection and convergence — users who read only TOOLKIT.md would not know about this.

**Cross-reference trace:** SKILL.md lines 10-32 → 8 phases including Phase 0 and Phase 7. TOOLKIT.md lines 182-193 → 6 phases, omitting Phase 0 and Phase 7.

**Severity:** LOW — TOOLKIT.md is documentation for users, not operational instructions for agents. The discrepancy misleads users but doesn't cause agents to behave incorrectly.

---

## Gap Finding 9: `quality_gate.sh:331` — Green-Phase Patch Detection ls-glob (BUG-M8 Scope Extension)

**File:Line:** `quality_gate.sh:331`

**Observation:**
```bash
if ls ${q}/patches/${bid}-fix*.patch &>/dev/null; then
```
This is one of the four BUG-M8 vulnerable locations. The baseline confirmed BUG-M8 covers lines 152-153, 331, 567-568, 595. But the patch fix for BUG-M8 (`quality/patches/BUG-M8-fix.patch`) should address all four locations. Let me verify the scope of the fix covers line 331 and line 595.

**Verification via baseline patch:** The BUG-M8 fix patch should replace `ls ${q}/patches/${bid}-fix*.patch` with `find "${q}/patches" -name "${bid}-fix*.patch" -print -quit 2>/dev/null | grep -q .`. If the fix covers all four locations, this is already resolved. If the fix patch misses line 331 or 595, this is an additional gap.

**Note:** This is a scope verification finding — BUG-M8 was confirmed to include line 331 in the baseline. Not a new bug, but a reminder that the fix patch must cover all four instances.

---

## Gap Finding 10: `quality_gate.sh:124` — Primary Functional Test File Detection ls-glob (BUG-M8 Self-Referential Manifestation Already Confirmed)

**File:Line:** `quality_gate.sh:123-124`

**Observation:**
```bash
if ls ${q}/test_functional.* ${q}/FunctionalSpec.* ${q}/FunctionalTest.* ${q}/functional.test.* &>/dev/null 2>&1; then
```
This was already confirmed as the BUG-M8 self-referential manifestation that causes the gate to FAIL on the quality-playbook self-audit (as documented in Phase 5/6 of the baseline). Benchmark 42 records this as the gate exit 1.

However, Gap Finding 1 (line 479) is DIFFERENT from this location. Line 479 is in the Test File Extension check (a different function), while line 124 is in the File Existence check. These are two different checks with the same vulnerability pattern. BUG-M8's fix patch covers line 124 (part of the original four locations), but line 479 was NOT in BUG-M8's scope.

**Confirmed: line 479 is a NEW bug candidate, separate from BUG-M8.**

---

## Summary: New Bug Candidates for Phase 2 (Gap Iteration)

### CAND-G1 (MEDIUM): `quality_gate.sh:479` — Test File Extension ls-glob produces false positive under nullglob
- **File:Line:** `quality_gate.sh:479`
- **Hypothesis:** `func_test=$(ls ${q}/test_functional.* 2>/dev/null | head -1)` under nullglob returns a CWD filename instead of empty, causing language extension validation to run on a spurious file and produce misleading FAIL/PASS results.
- **Different from BUG-M8:** BUG-M8's fix patches lines 124, 152-153, 331, 567-568, 595. Line 479 is NOT in BUG-M8's fix scope.

### CAND-G2 (MEDIUM): `quality_gate.sh:143` — Code reviews directory listing ls-glob produces false pass
- **File:Line:** `quality_gate.sh:143`
- **Hypothesis:** `ls ${q}/code_reviews/*.md 2>/dev/null` under nullglob returns non-empty output from CWD, making the gate pass "code_reviews/ has .md files" when the directory is empty.

### CAND-G3 (MEDIUM): `references/review_protocols.md:410` — Integration test template uses wrong recommendation enum values
- **File:Line:** `references/review_protocols.md:410`
- **Hypothesis:** Template specifies `SHIP IT / FIX FIRST / NEEDS INVESTIGATION` but gate requires `SHIP / FIX BEFORE MERGE / BLOCK`. An agent following the template produces a gate-failing artifact.

### CAND-G4 (MEDIUM): `quality_gate.sh` — No validation for recheck-results.json despite documented artifact contract
- **File:Line:** `quality_gate.sh` (entire file — absence)
- **Hypothesis:** Gate validates every other conditional artifact but not recheck artifacts. Malformed recheck-results.json passes all gate checks silently.

### CAND-G5 (LOW): `SKILL.md:1965` — recheck-results.json uses schema_version "1.0" (already BUG-L10; gate omission is new)
- **Note:** BUG-L10 confirmed. The gate omission (CAND-G4) is the new finding.

### CAND-G6 (LOW): `ai_context/TOOLKIT.md:182` — Phase count documentation is stale (6 phases vs 8 phases)
- **File:Line:** `ai_context/TOOLKIT.md:182-193`

---

## Derived Requirements (Gap Iteration)

**REQ-015: `quality_gate.sh` test file extension detection must not use ls-glob assignment**
- Spec basis: REQ-002 (reliable artifact detection), BUG-M8 pattern
- The `ls ${q}/test_functional.*` at line 479 must be replaced with `find`-based detection

**REQ-016: `quality_gate.sh` code_reviews directory detection must not use ls-glob**
- Spec basis: REQ-002, partial session detection (spec_audit.md)
- The `ls ${q}/code_reviews/*.md` at line 143 must be replaced with `find`-based detection

**REQ-017: All recommendation enum values must be consistent across all spec documents and gate**
- Spec basis: REQ-009 (consistency), REQ-011 (artifact traceability)
- `references/review_protocols.md` integration test template must use `SHIP / FIX BEFORE MERGE / BLOCK` not `SHIP IT / FIX FIRST / NEEDS INVESTIGATION`

**REQ-018: `quality_gate.sh` must validate recheck-results.json when it exists**
- Spec basis: SKILL.md artifact contract table (lines 117-118), benchmark 42 (gate must validate)
- The gate must check: schema_version, status enum values (FIXED/PARTIALLY_FIXED/STILL_OPEN/INCONCLUSIVE), required fields (id, severity, summary, status, evidence)
