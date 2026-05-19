# Exploration Findings — Iteration 4 (Parity Strategy)
<!-- Quality Playbook v1.4.1 — Iteration 4: Parity — 2026-04-16 -->

**Strategy:** parity — cross-path comparison and diffing
**Iteration:** 4 (after baseline, gap, unfiltered)
**Date:** 2026-04-16
**Prior confirmed bugs:** 18 (BUG-H1 through BUG-M18)

The parity strategy systematically enumerates parallel implementations of the same contract and diffs them for inconsistencies. This iteration identifies 6 parallel groups and traces 8 pairwise comparisons.

---

## Parallel Group PG-1: JSON Helper Functions — Parallel Validation Patterns

Three JSON helper functions in quality_gate.sh serve parallel purposes — they all extract or validate data from a JSON file. They should handle edge cases consistently.

### PG-1 Function Inventory

**`json_has_key` (lines 75-78):**
```bash
json_has_key() {
    local file="$1" key="$2"
    grep -q "\"${key}\"" "$file" 2>/dev/null
}
```
Checks for key presence. Returns exit 0 if the quoted key string appears anywhere in the file.

**`json_str_val` (lines 81-85):**
```bash
json_str_val() {
    local file="$1" key="$2"
    grep -o "\"${key}\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" "$file" 2>/dev/null \
        | head -1 | sed 's/.*: *"\([^"]*\)"/\1/'
}
```
Extracts string value. Returns the value if key has a string value, empty string if key is absent or has a non-string value.

**`json_key_count` (lines 88-91):**
```bash
json_key_count() {
    local file="$1" key="$2"
    grep -c "\"${key}\"[[:space:]]*:" "$file" 2>/dev/null || echo 0
}
```
Counts key occurrences. Uses a stricter pattern than `json_has_key` — requires the key to be followed by `:`.

### Comparison 1: `json_has_key` vs `json_key_count` — error handling parity

**Error/exception parity:** Compare how each handles a missing or unreadable file.

- `json_has_key`: `grep -q ... 2>/dev/null` — returns exit 1 on missing file (correct: key not found)
- `json_key_count`: `grep -c ... 2>/dev/null || echo 0` — the `|| echo 0` fallback outputs "0" on any error, which is correct behavior
- `json_str_val`: `grep -o ... 2>/dev/null | head -1 | sed ...` — on missing file, grep outputs nothing, sed receives empty, returns empty string (correct)

**Assessment:** All three handle missing files correctly (different mechanisms, same result). No discrepancy.

**Capability/feature-bit parity:** Compare what format each requires the key to be in.

- `json_has_key`: `grep -q "\"${key}\""` — matches key name in ANY context (value, comment, anywhere)
- `json_key_count`: `grep -c "\"${key}\"[[:space:]]*:"` — matches key ONLY when followed by `:`
- `json_str_val`: `grep -o "\"${key}\"[[:space:]]*:[[:space:]]*\"[^\"]*\""` — matches key ONLY when followed by `:` and a string value

**DISCREPANCY FOUND (PG-1-D1):** `json_has_key` uses a weaker pattern than `json_key_count`. Two functions in the same file that both nominally answer "does this JSON contain key X?" have different matching semantics. `json_has_key` can return true when the key appears only in a string value (already confirmed as BUG-H1). But `json_key_count` uses the colon-anchor pattern that correctly limits matches to actual key positions. This means the gate uses a WEAK check (`json_has_key`) for boolean questions ("does this file have key X?") and a STRONG check (`json_key_count`) for counting ("how many times does key X appear?"). The semantic contract is inverted: the counting function is more correct than the existence function.

- `json_has_key` callers: lines 230, 253, 260 (root-key presence checks)
- `json_key_count` callers: lines 241 (per-bug field presence, comparing count to bug_count)

**Impact of PG-1-D1:** This is the same root cause as BUG-H1. However, parity analysis reveals an additional dimension: the inconsistency creates a situation where `json_key_count(...) > 0` is a STRONGER check than `json_has_key(...)`. A caller that wants to know if a key exists should call `json_key_count` and check for > 0, not call `json_has_key`. This is not obvious from the function names. The functions have parallel purposes but inconsistent semantics. Callers who use `json_has_key` for boolean existence checks get weaker guarantees than callers who happen to use `json_key_count`.

**Status:** Root cause is BUG-H1 (already confirmed). No new bug — but the parity analysis strengthens the case for BUG-H1's fix by showing the stronger pattern is already available in the same file.

### Comparison 2: Per-bug field check — `json_has_key` vs `json_key_count` for different checks

At lines 259-265, the gate checks that the `summary` object contains required sub-keys:
```bash
for skey in total verified confirmed_open red_failed green_failed; do
    if json_has_key "$json_file" "$skey"; then
        pass "summary has '${skey}'"
    else
        fail "summary missing '${skey}' count"
    fi
done
```

At lines 239-248, the gate checks that per-bug fields are present:
```bash
for field in id requirement red_phase green_phase verdict fix_patch_present writeup_path; do
    local fcount
    fcount=$(json_key_count "$json_file" "$field")
    if [ "$fcount" -ge "$bug_count" ]; then
        pass "per-bug field '${field}' present (${fcount}x)"
    ...
done
```

**DISCREPANCY FOUND (PG-1-D2):** Two parallel "does this JSON contain required field X?" checks in the same function use different helpers with different semantics:
- Per-bug fields: `json_key_count` (strong — colon-anchored, count-verified)
- Summary sub-keys: `json_has_key` (weak — substring match, no colon anchor)

A `tdd-results.json` where `total` appears only in a string value (e.g., `"notes": "the total is 5 bugs"`) would pass the summary check via `json_has_key` even though no actual `total:` key exists in the summary object. The per-bug check would catch equivalent pollution via `json_key_count`, but the summary check would not.

**Severity:** LOW — The false positive risk is low in practice since the string `total` rarely appears in JSON text values. But the inconsistency is real: two parallel checks for required field presence use validators with different false-positive rates. The stronger validator (json_key_count) is used for per-bug fields; the weaker (json_has_key) is used for summary fields. This is backwards — summary fields are simpler to count (there's exactly one summary object) and would benefit less from count-based validation, while per-bug fields (where count matters) correctly use count-based validation. So the assignment of validators is actually inverted: count-based for per-bug (correct, counts matter), string-based for summary (incorrect, but risks are lower).

**New candidate bug:** CAND-P1 — Summary sub-key presence check uses `json_has_key` (weak) instead of `json_key_count` (strong), creating a consistency gap with the per-bug field check pattern.

---

## Parallel Group PG-2: Artifact Existence Checks — Detection Method Parity

Multiple detection methods are used throughout the gate for equivalent operations ("does artifact X exist with content?"). This group compares them.

### PG-2 Method Inventory

**Pattern A — `[ -f "${q}/${f}" ]` (lines 107-121):** Direct file existence test. Clean, shell-native, not vulnerable to nullglob. Used for BUGS.md, REQUIREMENTS.md, QUALITY.md, PROGRESS.md, COVERAGE_MATRIX.md, COMPLETENESS_REPORT.md, CONTRACTS.md, RUN_CODE_REVIEW.md, RUN_SPEC_AUDIT.md, RUN_INTEGRATION_TESTS.md, RUN_TDD_TESTS.md.

**Pattern B — `ls` glob (lines 124, 143, 152, 153, 331, 567-568, 595):** `ls ${path}/*glob* 2>/dev/null`. Vulnerable to nullglob. Already confirmed as BUG-M8, BUG-M12, BUG-M13, BUG-M16.

**Pattern C — `find ... -print -quit | grep -q .` (lines 449-454, 486-495):** find-based detection. Used for language detection and source file counting. Not vulnerable to nullglob. The robust pattern.

**Pattern D — `[ -f "$wf" ] || continue` guard inside a loop (line 598-600):**
```bash
for wf in "${q}"/writeups/BUG-*.md; do
    [ -f "$wf" ] || continue
    if grep -q '```diff' "$wf" 2>/dev/null; then
```
Hybrid pattern: glob expansion for iteration, file-existence guard to skip non-matching globs. Works correctly even under nullglob (when glob expands to nothing, the loop runs zero iterations; when glob expands to the literal pattern string under non-nullglob, the `[ -f "$wf" ]` guard catches it).

### Comparison 3: Writeup loop (Pattern D) vs Writeup count (Pattern B) — parallel paths for the same resource

At line 595, the gate first counts writeups using Pattern B (ls-glob):
```bash
writeup_count=$(ls ${q}/writeups/BUG-*.md 2>/dev/null | wc -l | tr -d ' ')
```

Then at lines 598-603, it validates individual writeup content using Pattern D (loop with guard):
```bash
for wf in "${q}"/writeups/BUG-*.md; do
    [ -f "$wf" ] || continue
    if grep -q '```diff' "$wf" 2>/dev/null; then
        writeup_diff_count=$((writeup_diff_count + 1))
    fi
done
```

**DISCREPANCY FOUND (PG-2-D1):** Two parallel operations on the same resource (writeup files) use different detection methods:
- Counting writeups: Pattern B (ls-glob, nullglob-vulnerable → BUG-M8 scope)
- Validating writeup content: Pattern D (loop + guard, nullglob-safe)

Under nullglob in an empty writeups/ directory:
- `writeup_count` via Pattern B: `ls` receives no args → lists CWD → nonzero count → `writeup_count` is wrong
- `writeup_diff_count` via Pattern D: glob expands to empty → loop runs zero iterations → `writeup_diff_count` stays 0

This produces a contradictory state: `writeup_count > 0` (wrong) and `writeup_diff_count = 0` (correct). The gate then executes:
```bash
if [ "$writeup_count" -ge "$bug_count" ]; then
    pass "${writeup_count} writeup(s) for ${bug_count} bug(s)"
```
...issuing a spurious PASS for writeup existence, then:
```bash
if [ "$writeup_diff_count" -ge "$writeup_count" ]; then
    pass "All ${writeup_diff_count} writeup(s) have inline fix diffs"
```
...comparing 0 to a nonzero wrong count, issuing a spurious FAIL (or a misleading comparison). The inconsistency between the two patterns produces a contradictory pair of PASS/FAIL results for the same set of files.

**Severity:** MEDIUM — already within BUG-M8 scope (line 595 is one of the vulnerable locations). But the parity analysis reveals the additional consequence: the writeup CONTENT check (diff presence) uses the correct pattern while the writeup EXISTENCE check uses the wrong pattern, causing contradictory results within the same `[Bug Writeups]` gate section.

**New candidate:** Strengthens BUG-M8 scope. Not a new separate bug, but a new consequence of the existing bug.

### Comparison 4: Patch existence (per-bug) vs Patch count (aggregate) — structural parity

**Per-bug green-phase check (lines 331-344):** Iterates bug IDs, checks each individually:
```bash
if ls ${q}/patches/${bid}-fix*.patch &>/dev/null; then
    green_expected=$((green_expected + 1))
    ...
fi
```

**Aggregate patch count (lines 566-568):** Counts all regression patches without per-bug iteration:
```bash
reg_patch_count=$(ls ${q}/patches/BUG-*-regression*.patch 2>/dev/null | wc -l | tr -d ' ')
fix_patch_count=$(ls ${q}/patches/BUG-*-fix*.patch 2>/dev/null | wc -l | tr -d ' ')
```

**Comparison sub-type: Iteration/collection parity.** The TDD log check iterates per-bug (correct — it can verify that EACH bug has a log). The patch count check counts in aggregate (incorrect — it verifies the COUNT matches but not that each specific bug has a patch).

**DISCREPANCY FOUND (PG-2-D2):** The TDD log section correctly iterates `bug_ids` to verify per-bug coverage. The patch section counts aggregates. This means:
- A run with 3 bugs but DIFFERENT patches (e.g., BUG-H1, BUG-M3, BUG-M3 duplicate) produces `reg_patch_count = 3` and passes, even though BUG-M4 has no patch.
- The TDD log section would catch this (iterating per bug), but the patch section wouldn't.

The inconsistency: patch checking uses aggregate counting while log checking uses per-bug iteration. These two checks enforce the same class of requirement ("every confirmed bug must have artifact X") but with different enforcement rigor.

**Severity:** LOW — in practice, patches are named with bug IDs, so duplicates are rare. But the structural inconsistency is a real design gap.

**New candidate bug:** CAND-P2 — Patch existence checking uses aggregate count (potentially allowing wrong-set patches to pass) while TDD log checking uses per-bug iteration (correct). These parallel checks should use the same per-bug iteration pattern.

---

## Parallel Group PG-3: TDD Log Checking vs. Patch Checking — Same Contract, Different Approaches

This group examines how two gate sections that enforce "every confirmed bug must have artifact X" differ in their implementation approach.

### Comparison 5: Red-log vs patch — iteration approach

**TDD Log section (lines 307-387):** Extracts `bug_ids` via grep, iterates per bug, checks each `BUG-NNN.red.log` individually. Also validates first-line tag per bug.

**Patch section (lines 562-588):** Does not iterate per bug. Uses aggregate `ls` glob counts. Compares total count to `bug_count`. Does not verify which specific bugs have patches.

**Identifier and index parity:** The log section uses per-bug IDs as the index. The patch section uses total count as the index. Both are indexing the same logical set (confirmed bugs with IDs), but via different mechanisms.

**Also note:** The TDD log section has the BUG-H17 vulnerability (bug_ids is empty when BUGS.md uses severity-prefix IDs — already confirmed). The patch section does NOT iterate bug_ids, so it's immune to BUG-H17's direct effect (but is vulnerable to BUG-M8's nullglob issue on the ls-glob).

**Finding PG-3-F1:** The two sections enforce the same contract (bug → artifact) with different implementation strategies that have different failure modes. The log section's failure mode is BUG-H17 (wrong regex). The patch section's failure mode is BUG-M8 (nullglob) + the per-bug identity gap noted in PG-2-D2. Neither implementation is fully robust, but they fail in different ways. A complete fix would require both sections to use the same per-bug iteration with find-based detection.

---

## Parallel Group PG-4: Phase Entry Gates vs. Phase Exit Gates

SKILL.md defines both "phase entry gates" (what must be true before a phase starts) and "phase exit gates" (what must be true before a phase ends). These are parallel constructs that should agree on what each phase requires.

### Comparison 6: Phase 1 exit gate vs. Phase 2 entry gate (already confirmed as BUG-M3)

Phase 1 exit gate (SKILL.md:847-862): 12 numbered checks.
Phase 2 entry gate (SKILL.md:897-904): 6 section-title checks.

This discrepancy is the root cause of BUG-M3. No new bug here, but confirms PG-4 as a fruitful group.

### Comparison 7: Phase 4 exit gate vs. Phase 5 entry gate

**Phase 4 exit gate (SKILL.md:1550):**
> "Phase 4 is not complete until a triage file exists at `quality/spec_audits/YYYY-MM-DD-triage.md` AND individual auditor reports exist."

**Phase 5 entry gate:** There is NO explicit Phase 5 entry gate section in SKILL.md. Phase 5 begins with:
> "Re-read `quality/PROGRESS.md` — specifically the cumulative BUG tracker. This is the authoritative list of all findings across both code review and spec audit."

**DISCREPANCY FOUND (PG-4-D1):** Phase 4 exit gate requires triage + auditor files, but Phase 5 has NO entry gate that verifies Phase 4 was completed. Phase 5 instructs the agent to read PROGRESS.md as its first action, but PROGRESS.md is a text file that agents update manually — an agent could write "Phase 4: complete" in PROGRESS.md without actually having run the spec audit. The Phase 5 instructions provide no mechanical backstop equivalent to the Phase 2 entry gate (which checks EXPLORATION.md for specific section titles).

**Comparison sub-type: Resource lifecycle parity.** Phase 1 creates EXPLORATION.md; Phase 2 verifies it mechanically before proceeding. Phase 4 creates triage and auditor files; Phase 5 does NOT mechanically verify they exist before proceeding. This is a lifecycle parity gap: the same "verify inputs exist" pattern is applied to Phase 2 but not Phase 5.

**Severity:** LOW — the SKILL.md Phase 5 does say "if Phase 3 and Phase 4 are not explicitly marked complete, the terminal gate fails" in the terminal gate section. But that check is at the END of Phase 5, not at the BEGINNING. An agent could run all of Phase 5 on incorrect inputs, then fail the terminal gate. The Phase 2 pattern (check inputs BEFORE proceeding) is more robust.

**New candidate bug:** CAND-P3 — Phase 5 has no entry gate that mechanically verifies Phase 4 artifacts (triage + auditor files) exist before proceeding. Compare with Phase 2 entry gate which verifies Phase 1 artifacts. The inconsistency allows Phase 5 to run on non-existent Phase 4 output.

### Comparison 8: Phase 4 completion gate naming requirement vs. gate check

**SKILL.md Phase 4 exit gate (line 1550):**
> "Phase 4 is not complete until a triage file exists at `quality/spec_audits/YYYY-MM-DD-triage.md`"

**quality_gate.sh spec_audits check (lines 151-155):**
```bash
triage_count=$(ls ${q}/spec_audits/*triage* 2>/dev/null | wc -l | tr -d ' ')
auditor_count=$(ls ${q}/spec_audits/*auditor* 2>/dev/null | wc -l | tr -d ' ')
```

The gate uses a wildcard glob `*triage*` that accepts ANY file containing "triage" in its name. The SKILL.md completion gate requires the specific pattern `YYYY-MM-DD-triage.md`. The gate does not enforce the date-prefix format required by SKILL.md.

**Identifier and index parity:** The spec says files must match `YYYY-MM-DD-triage.md`. The gate accepts `triage.md`, `any_triage_file.txt`, or even `not_a_triage_file_but_has_triage_in_path`. The naming requirement from SKILL.md is NOT enforced mechanically.

This is the root cause of the Phase 6 benchmark 31 FAIL noted in PROGRESS.md — the current run's `triage.md` (without date prefix) satisfies the gate's `*triage*` glob but not the SKILL.md naming requirement. Already connected to BUG-L9 (inconsistent auditor naming formats). This parity analysis confirms the gate's glob is not equivalent to the SKILL.md naming requirement — they agree on the "something must exist" constraint but disagree on the naming format constraint.

---

## Parallel Group PG-5: TDD-Results JSON — Two Templates vs. Gate Enforcement

SKILL.md contains two templates for `tdd-results.json` that serve the same purpose but have different field formats.

### Comparison 9: Template 1 vs Template 2 field format — already BUG-L11

Template 1 (lines 126-147): `"requirement": "UC-03: Description..."` and `"red_phase": "Regression test fails..."` (prose)
Template 2 (lines 1376-1408): `"requirement": "REQ-003"` and `"red_phase": "fail"` (enum)

The gate checks field PRESENCE at lines 239-248 using `json_key_count`. Neither template's value format is enforced by the gate.

**Capability/feature-bit parity:** Template 2 includes additional optional fields not in Template 1:
- `regression_patch` — template 2 only
- `fix_patch` — template 2 only
- `patch_gate_passed` — template 2 only
- `junit_red`, `junit_green`, `junit_available` — template 2 only
- `notes` — template 2 only

Gate validation (lines 239-248) does NOT check these optional fields. Gate validation DOES check `fix_patch_present` and `writeup_path`, which appear in both templates.

**Finding PG-5-F1:** The gate validates a subset of Template 1's fields and a subset of Template 2's fields. Neither template is fully enforced. An agent using Template 1 passes the gate but produces less informative output than Template 2. An agent using Template 2 passes the gate and produces all required fields. The gate's required field list (`id requirement red_phase green_phase verdict fix_patch_present writeup_path`) aligns with the fields that appear in BOTH templates, suggesting the gate was designed for the intersection — but SKILL.md presents them as two alternatives, not as a single canonical schema.

**Status:** Root cause is BUG-L11 (already confirmed). Parity analysis confirms the gate enforces the INTERSECTION of both templates, not either template fully.

### Comparison 10: Gate's verdict enum vs SKILL.md's verdict enum

**SKILL.md line 149:** `verdict must be one of: "TDD verified", "red failed", "green failed", "confirmed open", "deferred"`

**SKILL.md line 1424:** `Valid verdict values: "TDD verified" ... "confirmed open", "deferred". Do not use "skipped"`

**quality_gate.sh lines 294-298:**
```bash
bad_verdicts=$(grep -oE '"verdict"[[:space:]]*:[[:space:]]*"[^"]*"' "$json_file" 2>/dev/null \
    | sed 's/.*: *"\(.*\)"/\1/' \
    | grep -cvE '^(TDD verified|red failed|green failed|confirmed open|deferred)$' || true)
```

**Capability/feature-bit parity:** The gate regex matches exactly the five values from SKILL.md. Both sources agree. No discrepancy.

However, SKILL.md line 149 says `"deferred"` is valid, and SKILL.md line 1424 also says `"deferred"` is valid. But Template 1 at line 126-147 does NOT include `"deferred"` in its examples. Template 2 at lines 1376-1408 also does not show `"deferred"` in its template, only mentions it in prose.

**Finding PG-5-F2:** `"deferred"` verdict is documented in SKILL.md prose as valid (lines 149, 1424) and matched by the gate regex, but never shown in either template example. An agent following the templates would not know to use `"deferred"`. This is a template completeness gap — the templates should include a `"deferred"` example or explicitly mention it. This is a minor documentation inconsistency, not a code bug.

---

## Parallel Group PG-6: SKILL.md Artifact Contract Table vs. Gate's Checked Artifacts

The SKILL.md artifact contract table (lines 88-119) declares 18+ artifacts and their conditions. The gate checks a subset. This group compares them.

### Comparison 11: Required artifacts vs gate-enforced artifacts

**SKILL.md artifact contract (lines 88-119) — "Required: Yes" artifacts:**
1. Exploration findings (`quality/EXPLORATION.md`) — Yes
2. Quality constitution (`quality/QUALITY.md`) — Yes
3. Requirements (`quality/REQUIREMENTS.md`) — Yes
4. Behavioral contracts (`quality/CONTRACTS.md`) — Yes
5. Functional tests (`quality/test_functional.*`) — Yes
6. Code review protocol (`quality/RUN_CODE_REVIEW.md`) — Yes
7. Integration test protocol (`quality/RUN_INTEGRATION_TESTS.md`) — Yes
8. Spec audit protocol (`quality/RUN_SPEC_AUDIT.md`) — Yes
9. TDD verification protocol (`quality/RUN_TDD_TESTS.md`) — Yes
10. Bug tracker (`quality/BUGS.md`) — Yes
11. Coverage matrix (`quality/COVERAGE_MATRIX.md`) — Yes
12. Completeness report (`quality/COMPLETENESS_REPORT.md`) — Yes
13. Progress tracker (`quality/PROGRESS.md`) — Yes
14. AI bootstrap (`AGENTS.md`) — Yes

**Conditional artifacts ("If bugs found"):**
15. Regression tests (`quality/test_regression.*`) — If bugs found
16. Bug writeups (`quality/writeups/BUG-NNN.md`) — If bugs found
17. Regression patches (`quality/patches/BUG-NNN-regression-test.patch`) — If bugs found
18. TDD sidecar (`quality/results/tdd-results.json`) — If bugs found
19. TDD red-phase logs (`quality/results/BUG-NNN.red.log`) — If bugs found

**Gate checks at lines 107-177 and elsewhere:**
- Checks all 14 "Required: Yes" artifacts (lines 107-139)
- Checks code_reviews/*.md (line 143)
- Checks spec_audits/ triage + auditor (lines 151-155)
- Does NOT check CONTRACTS.md, COVERAGE_MATRIX.md, COMPLETENESS_REPORT.md as separate explicit checks
- (Wait — re-reading lines 107-121 — the gate loops over `BUGS.md REQUIREMENTS.md QUALITY.md PROGRESS.md COVERAGE_MATRIX.md COMPLETENESS_REPORT.md` in loop 1, then `CONTRACTS.md RUN_CODE_REVIEW.md RUN_SPEC_AUDIT.md RUN_INTEGRATION_TESTS.md RUN_TDD_TESTS.md` in loop 2)

After careful re-reading, the gate DOES check all 14 "Required: Yes" artifacts from the SKILL.md table. But there are notable gaps:

**DISCREPANCY FOUND (PG-6-D1):** `quality/test_regression.*` is "Required: If bugs found" per SKILL.md. BUG-M4 confirmed the gate doesn't check this. But also: the SKILL.md says `quality/TDD_TRACEABILITY.md` is "Required: If bugs have red-phase results" (line 107), and the gate DOES check this at line 377-384. Meanwhile, the gate does NOT check `quality/CONTRACTS.md` as "Required: Yes" — wait, re-reading line 116: the gate loops include CONTRACTS.md. Let me verify.

Reading lines 116-122: `for f in CONTRACTS.md RUN_CODE_REVIEW.md RUN_SPEC_AUDIT.md RUN_INTEGRATION_TESTS.md RUN_TDD_TESTS.md` — CONTRACTS.md IS checked.

**Confirmed gap after re-reading:** The gate does NOT check for `quality/COMPLETENESS_REPORT.md` — wait, line 107 loop: `for f in BUGS.md REQUIREMENTS.md QUALITY.md PROGRESS.md COVERAGE_MATRIX.md COMPLETENESS_REPORT.md` — it IS checked.

**Actual gap in PG-6:** `quality/test_regression.*` (confirmed BUG-M4), `quality/results/recheck-results.json` (confirmed BUG-M15), and `quality/SEED_CHECKS.md` (conditional — "If Phase 0 or 0b ran"). Let me check if SEED_CHECKS.md is in the SKILL.md artifact contract. Looking at SKILL.md line 1641: "If Phase 0 or 0b ran: `quality/SEED_CHECKS.md` exists as a standalone file." This is mentioned as an artifact requirement in Phase 5 but not in the artifact contract table at lines 88-119. This is a gap in the artifact contract table itself — SEED_CHECKS.md is required but not listed in the canonical table.

**New candidate bug:** CAND-P4 — `quality/SEED_CHECKS.md` is required when Phase 0b runs (per SKILL.md Phase 5 artifact file-existence gate at line 1641) but is NOT listed in the SKILL.md artifact contract table (lines 88-119) and NOT checked by the gate. The canonical artifact table is incomplete for this artifact.

---

## Comparison 12: Phase 0b activation vs. Phase 0a activation — resource lifecycle parity

**Phase 0a (SKILL.md ~line 271):** Activates when `previous_runs/` exists AND contains prior quality artifacts. Seeds from sibling runs.

**Phase 0b (SKILL.md ~line 295-297):** Activates when `previous_runs/` does NOT exist. Discovers via sibling directory.

**Lifecycle parity gap (already BUG-M5):** Empty `previous_runs/` directory causes both to skip. This is the confirmed BUG-M5. Parity confirms this is a resource lifecycle parity failure: the Phase 0a/0b "resource" (previous quality artifacts) is checked with inconsistent conditions that miss the empty-directory state.

---

## Candidate Bugs for Phase 2 — Parity Iteration

### CAND-P1: `quality_gate.sh:259-265` — Summary sub-key check uses `json_has_key` (weak) while per-bug field check uses `json_key_count` (strong)
- **File:Line:** `quality_gate.sh:259-265` vs `quality_gate.sh:239-248`
- **Hypothesis:** Two parallel "does JSON contain required field X?" checks use different validators. Summary checks use `json_has_key` (matches anywhere in file); per-bug checks use `json_key_count` (colon-anchored). A `tdd-results.json` where summary key names appear in string values would pass the summary check. The inconsistency means the gate applies different rigor to equivalent checks.
- **Severity:** LOW — in practice, false positives from `total`/`verified` appearing in string values are rare, but the structural inconsistency is real
- **Code review should inspect:** Lines 259-265 (summary check) vs lines 241-248 (per-bug field count). Fix: change summary sub-key check to use `json_key_count` for consistency.

### CAND-P2: `quality_gate.sh:562-588` — Patch existence uses aggregate count instead of per-bug iteration
- **File:Line:** `quality_gate.sh:562-588` vs `quality_gate.sh:316-345`
- **Hypothesis:** TDD log section iterates `bug_ids` per bug (verifying each bug has a log). Patch section counts aggregate patches (only verifying total count equals bug_count). A run with correct COUNT but wrong SET of patches (e.g., BUG-H1 has two regression patches, BUG-H2 has none) would pass the patch count but fail per-bug verification. The TDD log section would catch this correctly via iteration; the patch section would not.
- **Severity:** LOW — in practice, patches are named with specific bug IDs so duplicates are uncommon
- **Code review should inspect:** Lines 562-588 (patch count) vs lines 316-345 (log iteration). Fix: change patch section to iterate `bug_ids` like the log section does.

### CAND-P3: `SKILL.md` — Phase 5 has no entry gate that mechanically verifies Phase 4 artifacts before proceeding
- **File:Line:** `SKILL.md:1573-1590` (Phase 5 start) vs `SKILL.md:897-907` (Phase 2 entry gate)
- **Hypothesis:** Phase 2 has an explicit entry gate that verifies Phase 1 artifacts (EXPLORATION.md section titles) before proceeding. Phase 5 has no equivalent entry gate for Phase 4 artifacts (triage + auditor files). An agent could proceed through Phase 5 with no Phase 4 artifacts, only failing at the terminal gate after completing all Phase 5 work. The Phase 2 pattern (fail early) is better than the Phase 5 pattern (fail late).
- **Severity:** LOW — the terminal gate provides a backstop, but it fires late
- **Code review should inspect:** Phase 5 opening (SKILL.md:1573) vs Phase 2 opening (SKILL.md:897). Fix: add Phase 5 entry gate that checks for triage and auditor files before proceeding.

### CAND-P4: `SKILL.md:1641` vs `SKILL.md:88-119` — SEED_CHECKS.md required by Phase 5 gate but absent from canonical artifact contract table
- **File:Line:** `SKILL.md:1641` (Phase 5 artifact file-existence gate) vs `SKILL.md:88-119` (artifact contract table)
- **Hypothesis:** SKILL.md's Phase 5 artifact file-existence gate (line 1641) explicitly requires `quality/SEED_CHECKS.md` when Phase 0b ran. The canonical artifact contract table (lines 88-119), which is described as the "canonical list" for gate enforcement, does NOT include SEED_CHECKS.md. The gate script (quality_gate.sh) also does not check for it. Three sources (table, gate, gate script) are inconsistent with one source (Phase 5 prose). An agent auditing the artifact contract table would not know to create SEED_CHECKS.md. An agent following the Phase 5 closure gate would fail if SEED_CHECKS.md doesn't exist.
- **Severity:** LOW — only matters when Phase 0b runs, which is conditional
- **Code review should inspect:** Lines 88-119 (artifact contract table) vs line 1641 (Phase 5 gate). Fix: add SEED_CHECKS.md row to artifact contract table with condition "If Phase 0b ran."

---

## Summary of Parity Findings

| Group | Comparisons | Discrepancies | New Candidates |
|-------|-------------|---------------|----------------|
| PG-1: JSON helpers | 2 | 2 (PG-1-D1 = BUG-H1, PG-1-D2 = CAND-P1) | CAND-P1 |
| PG-2: Existence checks | 2 | 2 (PG-2-D1 = BUG-M8 scope, PG-2-D2 = CAND-P2) | CAND-P2 |
| PG-3: Log vs patch checks | 1 | PG-3-F1 (strengthens BUG-H17 context) | — |
| PG-4: Phase entry/exit gates | 2 | PG-4-D1 = CAND-P3, PG-4 confirms BUG-L9 | CAND-P3 |
| PG-5: TDD JSON templates | 2 | Confirm BUG-L11, minor PG-5-F2 | — |
| PG-6: Artifact contract vs gate | 1 | PG-6-D1 = CAND-P4 | CAND-P4 |

**Total:** 6 parallel groups, 10 comparisons, 6 discrepancy findings, 4 new candidate bugs

### Net-new candidates:
- **CAND-P1:** json_has_key vs json_key_count inconsistency in summary checks (LOW)
- **CAND-P2:** Patch existence uses aggregate count instead of per-bug iteration (LOW)
- **CAND-P3:** Phase 5 has no entry gate for Phase 4 artifacts (LOW)
- **CAND-P4:** SEED_CHECKS.md required by Phase 5 but absent from artifact contract table (LOW)

### Confirmed existing bugs strengthened by parity analysis:
- BUG-H1: json_has_key false positive — parity shows the STRONGER pattern (json_key_count with colon anchor) is already used nearby
- BUG-M3: Phase 1/2 gate mismatch — parity explains the structural pattern: exit gate rigor ≠ entry gate rigor
- BUG-M8: Writeup count (Pattern B) vs writeup loop (Pattern D) — two parallel paths on same resource produce contradictory results
- BUG-L9: Naming format check in gate (*triage* glob) vs naming requirement in SKILL.md (YYYY-MM-DD-triage.md)
- BUG-L11: Two templates produce two valid sidecar formats; gate enforces intersection

### Demoted candidates from parity exploration:
- DC-010: PG-5-F2 (`"deferred"` absent from templates) — documentation gap only, not a behavioral bug. Gate and SKILL.md prose agree; templates don't show an example. No agent failure mode.
- DC-011: PG-3-F1 (log vs patch use different iteration strategies) — the aggregate count in patch section is a WEAKER check but doesn't cause false passes in normal operation. Already partially captured by BUG-M4 (which covers the missing test_regression.* existence check) and BUG-M8 (nullglob). The iteration-vs-count discrepancy alone is a design gap, not a confirmed bug without evidence of actual incorrect pass.

---

## Derived Requirements (Parity Iteration)

**REQ-022: Gate summary sub-key checks must use `json_key_count` for consistency with per-bug field checks**
- Spec basis: Internal gate consistency; same "required JSON field presence" contract should use same enforcement pattern
- Lines 259-265: replace `json_has_key` calls with `json_key_count` checks > 0

**REQ-023: Patch existence check must iterate per-bug ID, not count aggregates**
- Spec basis: Same contract as TDD log check ("every confirmed bug must have artifact X")
- Lines 562-588: replace aggregate count with per-bug iteration matching lines 316-345 pattern

**REQ-024: Phase 5 must include an entry gate verifying Phase 4 artifacts before proceeding**
- Spec basis: Phase 2 entry gate pattern; fail-early is better than fail-late
- SKILL.md lines 1573+: add mandatory Phase 5 entry gate checking for triage + auditor files

**REQ-025: SEED_CHECKS.md must be added to the artifact contract table when Phase 0b runs**
- Spec basis: SKILL.md line 1641 requires SEED_CHECKS.md; table at lines 88-119 should reflect this
- Artifact contract table: add row for SEED_CHECKS.md with condition "If Phase 0b ran"
