# Unfiltered Exploration — Iteration 3

<!-- Quality Playbook v1.4.1 — Unfiltered Iteration 3 — 2026-04-16 -->

**Strategy:** unfiltered
**Date:** 2026-04-16
**Approach:** Pure domain-driven exploration, no structural constraints, no pattern matrices.

Reading the codebase as a domain expert would — following hunches, tracing suspicious paths, asking
"what would break if I did X?" rather than following a checklist.

---

## Finding 1: `quality_gate.sh:124` — The functional test file existence check uses `&>/dev/null 2>&1` which is redundant and masks behavior on some shells

**File:Line:** `quality_gate.sh:124`
**Bug hypothesis:** `if ls ${q}/test_functional.* ${q}/FunctionalSpec.* ${q}/FunctionalTest.* ${q}/functional.test.* &>/dev/null 2>&1; then`

This line has two redirection issues:
1. `&>/dev/null` redirects both stdout and stderr to /dev/null
2. `2>&1` then redirects stderr to wherever stdout currently points — but stdout is already /dev/null

In bash, `&>/dev/null 2>&1` is redundant (`2>&1` after `&>/dev/null` does nothing useful). More importantly: the `ls` is receiving four glob patterns, and on shells without `nullglob`, an unmatched glob expands to the literal pattern string. So `ls` receives four path arguments and will list any matching files OR fail with "No such file or directory" (exit 1) if none match. But here's the real issue: `ls` returns exit 0 if ANY of its arguments succeeds. So if `test_functional.sh` exists but `FunctionalSpec.*` doesn't, `ls` exits 0 anyway — but it prints to stdout and stderr which are both suppressed. This part works correctly by accident.

The actual problem: if `nullglob` is enabled, unmatched globs silently disappear. `ls` receives only the matched files. If none match, `ls` receives no arguments and lists the CURRENT DIRECTORY — always exits 0. So the gate passes even when no functional test file exists, if `nullglob` is enabled.

This is the SAME vulnerability class as BUG-M8, BUG-M12, BUG-M13. But this instance at line 124 is DISTINCT from the others. BUG-M8's fix patch covers lines 152-153, 331, 567-568, 595. BUG-M12 covers line 479. BUG-M13 covers line 143. Line 124 is NOT covered by any existing fix patch.

**Code path trace:**
- `check_repo()` called → line 124: `ls ${q}/test_functional.*...` → under nullglob → `ls` gets no args → lists CWD → exits 0
- Line 124 result: `pass "functional test file exists"` (WRONG — file doesn't exist)
- Later, line 479: `func_test=$(ls ${q}/test_functional.* 2>/dev/null | head -1)` → same bug (BUG-M12)
- So the gate reports two false passes: one for "exists" (line 124) and one for extension check (line 479)

**Severity:** MEDIUM (same class as BUG-M8, BUG-M13, BUG-M12)

---

## Finding 2: `quality_gate.sh:313-315` — `bug_ids` extraction uses `BUG-[0-9]+` regex but confirmed bugs use `BUG-H1/BUG-M3` format — causing 100% of TDD log checks to be silently skipped

**File:Line:** `quality_gate.sh:313-315`
**Bug hypothesis:**

```bash
bug_ids=$(grep -oE 'BUG-[0-9]+' "${q}/BUGS.md" 2>/dev/null \
    | grep -E '^BUG-[0-9]+$' | sort -u -t'-' -k2,2n)
```

This extracts bug IDs matching `BUG-[0-9]+` — purely numeric suffixes like `BUG-001`. But the entire Quality Playbook uses severity-prefixed IDs: `BUG-H1`, `BUG-M3`, `BUG-L6`. The `BUG-[0-9]+` regex NEVER matches `BUG-H1`, `BUG-M3`, etc. So `bug_ids` is always empty when the QFB format is used.

**Consequence traced through the code path:**
- Line 313: `bug_ids=$(grep -oE 'BUG-[0-9]+' ...)` → empty (no matches for BUG-H1 format)
- Line 316: `for bid in $bug_ids; do` → loop never executes (empty)
- Line 319: red-phase log check never runs → `red_found=0`, `red_missing=0`
- Line 348: `if [ "$red_missing" -eq 0 ] && [ "$red_found" -gt 0 ]` → `red_found` is 0 → goes to else
- Line 353: `fail "No red-phase logs found..."` — BUT WAIT. `red_found` is 0 AND `red_missing` is 0, so the first condition (`$red_missing -eq 0 && $red_found -gt 0`) is FALSE and the elif (`$red_found -gt 0`) is also FALSE...

Actually: line 348 checks `red_missing -eq 0 AND red_found -gt 0` → FALSE
Line 350 checks `red_found -gt 0` → also FALSE  
So falls through to line 352: `fail "No red-phase logs found"` — only if `red_found > 0`, but wait line 353 says: `else` — looking at the code again at lines 348-354:

```bash
if [ "$red_missing" -eq 0 ] && [ "$red_found" -gt 0 ]; then
    pass "All ${red_found} confirmed bug(s) have red-phase logs"
elif [ "$red_found" -gt 0 ]; then
    fail "${red_missing} confirmed bug(s) missing red-phase log"
else
    fail "No red-phase logs found (every confirmed bug needs quality/results/BUG-NNN.red.log)"
fi
```

When `bug_ids` is empty: `red_found=0`, `red_missing=0`. First `if` is FALSE (red_found NOT > 0). `elif` is also FALSE (red_found NOT > 0). Falls to `else`: `fail "No red-phase logs found"`.

BUT — the outer `if [ "$bug_count" -gt 0 ]` at line 309. `bug_count` is set from BUGS.md heading format check at line 196. For the QFB format (`BUG-H1`), `correct_headings=$(grep -cE '^### BUG-[0-9]+' ...)` = 0. So `bug_count=0`.

**Conclusion:** With QFB severity-prefixed IDs, BOTH `bug_count=0` AND `bug_ids` is empty. The TDD log file check at line 309 is gated by `bug_count > 0`. Since `bug_count=0`, the ENTIRE TDD log section is skipped with `info "Zero bugs — TDD log files not required"`. So when QFB IDs are used, the gate skips ALL TDD log validation. This means the gate provides ZERO assurance that TDD red/green logs exist.

This is a compound failure: the BUGS.md heading check (lines 182-219) uses `^### BUG-[0-9]+` which fails to match `BUG-H1`, setting `bug_count=0`. Then the TDD log check uses `bug_count=0` to skip all log validation. The entire TDD closure assurance is bypassed.

**This confirms and expands on the observation from PROGRESS.md Phase 6:** "Gate treats run as zero-bug because ID format `BUG-H1` doesn't match regex `BUG-[0-9]+`. TDD sidecar, patch, and writeup checks were skipped."

**Severity:** HIGH — this is the root cause underlying multiple gate bypass observations. The BUGS.md heading format validation at line 184 uses a regex that does NOT match the format that SKILL.md specifies and uses throughout.

---

## Finding 3: `SKILL.md:1615` — BUGS.md heading format spec says `### BUG-NNN` but no example or constraint prevents `BUG-H1` — creating the ID format confusion

**File:Line:** `SKILL.md:1615`
**Bug hypothesis:** SKILL.md Phase 5 terminal gate section specifies:

> "Each confirmed bug must use the heading level `### BUG-NNN` (e.g., `### BUG-001`). This is the canonical heading format..."

The example `### BUG-001` uses pure numeric suffix format. Yet the actual Quality Playbook runs consistently use `BUG-H1`, `BUG-M3`, `BUG-L6` format (severity-prefixed). The spec example at line 1615 directly contradicts the established naming convention used throughout all generated BUGS.md files in this self-audit.

**Code path trace (cross-file contract violation):**
- SKILL.md:1615: spec says `BUG-001` format, example shows `BUG-001`
- BUGS.md (Phase 3): generates `### BUG-H1`, `### BUG-M3` based on Phase 1 severity labels
- quality_gate.sh:184: validates with `grep -cE '^### BUG-[0-9]+'` — matches `BUG-001` but NOT `BUG-H1`
- Result: gate treats every QFB self-audit run as zero-bug run, bypassing all TDD/patch/writeup checks

**The contradiction:** SKILL.md generates bugs with severity codes (HIGH→H, MEDIUM→M, LOW→L), then the terminal gate spec says the format should be numeric-only, and the gate script enforces numeric-only — so every QFB run on itself that uses severity-prefixed IDs gets silently zero-bug treatment from the gate.

**Severity:** HIGH — this is the fundamental naming inconsistency that caused the systemic gate bypass identified in the Phase 6 benchmarks (benchmark 39 PARTIAL).

Note: This is related to but distinct from BUG-L9 (which covers inconsistent auditor naming formats). BUG-L9 is about spec audit file naming. This finding is about BUGS.md entry ID format and the gate's inability to validate it.

---

## Finding 4: `quality_gate.sh:186-187` — `wrong_headings` calculation uses nested grep that always returns 0

**File:Line:** `quality_gate.sh:186-187`
**Bug hypothesis:**

```bash
wrong_headings=$(grep -E '^## BUG-[0-9]+' "${q}/BUGS.md" 2>/dev/null | grep -cvE '^### BUG-' || true)
```

This is meant to count headings that use `## BUG-NNN` (two hashes) instead of `### BUG-NNN`. But the logic is self-contradicting:
1. `grep -E '^## BUG-[0-9]+'` — finds lines starting with exactly `## BUG-`
2. `grep -cvE '^### BUG-'` — counts lines that do NOT start with `### BUG-`

Since the input from step 1 already filters for lines starting with `## BUG-` (two hashes), and `^### BUG-` requires three hashes, NO output from step 1 can match `^### BUG-`. So `grep -cvE '^### BUG-'` will count ALL lines from step 1 (since none of them start with `### BUG-`). The result: `wrong_headings` equals the count of `## BUG-NNN` lines — which IS what was intended.

Wait — that's actually correct. Let me re-examine. The grep chain is: (lines matching `^## BUG-[0-9]+`) piped to (count of lines NOT matching `^### BUG-`). Since all input lines start with `##` (two hashes), none match `^### BUG-` (three hashes), so all are counted. This gives the correct count of `## BUG-NNN` headings.

However: there's a subtler issue. The first grep uses `^## BUG-[0-9]+` which INCLUDES lines matching `^### BUG-NNN` because `##` is a prefix of `###`. Wait no — `^## ` (two hashes space) vs `^### ` (three hashes space). The regex `^## BUG-` would match `## BUG-001` but NOT `### BUG-001` because `### ` starts with three hashes. So the filtering logic IS correct.

But: what about `BUG-H1` format? `grep -E '^## BUG-[0-9]+'` won't match `## BUG-H1` (because `H` is not `[0-9]`). So `wrong_headings` for the QFB format is 0 (correct, but for the wrong reason — wrong because no `## BUG-H1` exists either). The gate's heading validation entirely fails to detect QFB-format severity-prefixed IDs at ANY heading level.

**Actual bug:** Lines 188-194 check for `deep_headings`, `bold_headings`, `bullet_headings` using `BUG-[0-9]+` regex. None of these match `BUG-H1`. So when BUGS.md has `### BUG-H1` entries, ALL checks return 0, falling into the zero-bug path at line 205-212. The gate correctly notes "no ### BUG-NNN headings found" but doesn't FAIL — it either treats it as zero-bug or issues a WARN.

**Severity:** MEDIUM — the heading validation is fully blind to the severity-prefix format used by the QFB self-audit and likely by many QFB users.

---

## Finding 5: `quality_gate.sh:44` — Arg parser loop uses `for arg in ${@+"$@"}` which has a subtle quoting issue

**File:Line:** `quality_gate.sh:44`
**Bug hypothesis:**

```bash
for arg in ${@+"$@"}; do
```

The idiom `${@+"$@"}` expands to `"$@"` when `$#` is nonzero, and to nothing (empty) when `$#` is zero. This is a correct POSIX portability idiom for avoiding issues with `set -u` when `$@` is empty. However, in the `for` loop context, `for arg in "$@"` already handles the empty case correctly in bash (loop simply doesn't execute). The `${@+"$@"}` idiom is unnecessary in bash and its presence here creates a false impression of correctness.

The actual concern: when a repo path contains spaces, `${@+"$@"}` correctly preserves them because the inner expansion is `"$@"` (quoted). But the real issue comes at line 686:

```bash
for name in ${REPO_DIRS[@]+"${REPO_DIRS[@]}"}; do
```

This is analogous to the arg parser, but here the inner expansion `"${REPO_DIRS[@]}"` should expand to multiple quoted words. However, the outer `${...+"..."}` structure — when non-empty — expands to the literal result of evaluating `"${REPO_DIRS[@]}"` inside the braces. This might work correctly in bash 5.x but has known portability issues in bash 4.x and zsh.

**More importantly**: line 697:
```bash
REPO_DIRS=(${resolved[@]+"${resolved[@]}"})
```

This is the BUG-H2 location. The outer parens `(...)` perform word-splitting on the expansion. Even if `${resolved[@]+"${resolved[@]}"}` correctly expands to a list of quoted words, wrapping it in `(...)` without quoting causes word-splitting. Fix: `REPO_DIRS=("${resolved[@]+"${resolved[@]}"}}")` — but even this is tricky.

**Code path trace:** User runs `./quality_gate.sh "/Users/joe/My Repo"` → arg parser (line 44) correctly adds `"/Users/joe/My Repo"` to REPO_DIRS → line 686 loops over REPO_DIRS to resolve → line 687: `if [ -d "$name/quality" ]` where `$name` is correctly quoted → adds to `resolved` array → line 697: `REPO_DIRS=(${resolved[@]+"${resolved[@]}"})` — word-splits on space → `REPO_DIRS` becomes two elements: `/Users/joe/My` and `Repo/quality` doesn't exist → `check_repo "/Users/joe/My"` fails all checks.

This is BUG-H2 (already confirmed). The finding here adds trace detail about HOW the path survives the arg parser but breaks in the resolver.

**Severity:** Confirming BUG-H2's root cause — not a new bug, but additional code path evidence.

---

## Finding 6: `quality_gate.sh:259-265` — Summary key check uses `json_has_key` which has the BUG-H1 false positive — summary keys in string values pass the check

**File:Line:** `quality_gate.sh:259-265`
**Bug hypothesis:**

```bash
for skey in total verified confirmed_open red_failed green_failed; do
    if json_has_key "$json_file" "$skey"; then
        pass "summary has '${skey}'"
    else
        fail "summary missing '${skey}' count"
    fi
done
```

This calls `json_has_key` which (per BUG-H1) matches the key name ANYWHERE in the file, including inside string values. So a `tdd-results.json` that has a bug description mentioning "total confirmed_open cases" in a string value would pass all five summary key checks even if the actual `summary` object is malformed or missing.

**Code path trace:**
- Line 259: `json_has_key "$json_file" "total"` calls line 76: `grep -q '"total"' "$file"` 
- File contains `"evidence": "checking total confirmed_open issues..."` (string value)
- grep matches → returns exit 0 → `json_has_key` returns exit 0 → `pass "summary has 'total'"`
- Reality: summary object doesn't contain `"total"` as a key

This is the BUG-H1 false positive pattern propagated to the summary key validation. The summary check is the most critical check because it validates the structured reporting fields. A malformed summary passes if ANY string value in the file mentions the key names.

**Severity:** This is already BUG-H1 (the root cause). Adding a new finding about the specific propagation to summary validation. Strengthens the case for fixing BUG-H1 urgently.

---

## Finding 7: `quality_gate.sh:253-255` — "Wrong field names" check uses `json_has_key` which is itself buggy, producing false positives for false positive detection

**File:Line:** `quality_gate.sh:253-255`
**Bug hypothesis:**

```bash
for bad_field in bug_id bug_name status phase result; do
    if json_has_key "$json_file" "$bad_field"; then
        fail "non-canonical field '${bad_field}' found (use standard field names)"
    fi
done
```

This check is supposed to fail the gate when non-canonical field names are present. But `json_has_key` matches the name ANYWHERE in the file. If a bug's `notes` field contains text like "the old `status` field was renamed to `verdict`", the check for `status` matches the string in the notes and incorrectly fails the gate with `"non-canonical field 'status' found"`.

Even more insidious: if the `verdict` field description mentions "note: the old `bug_name` field is no longer used", `json_has_key` for `bug_name` returns true, causing a false FAIL. This makes the "wrong field" detection WORSE than not having it — the validator incorrectly fails conformant files.

**Code path trace:**
- Line 254: `json_has_key "$json_file" "status"` 
- tdd-results.json: `"notes": "previously this used a 'status' field"`
- `grep -q '"status"'` matches the string value containing `'status'`
- Returns exit 0 → gate FAILs with "non-canonical field 'status' found"
- Reality: the file IS conformant — `status` appears only in a notes string, not as a key

This is again BUG-H1 propagated. The false positive detection itself can produce false positives, creating a confusing situation where conformant JSON fails the gate.

**Severity:** This is BUG-H1 propagated (same root cause). Adding this finding to document the specific manifestation in the "wrong field" detector.

---

## Finding 8: `SKILL.md:135` vs `quality_gate.sh:239-248` — Template 1 uses `"requirement": "UC-03: ..."` but gate validates presence of `requirement` field without validating its FORMAT — gate passes both templates

**File:Line:** `SKILL.md:135` and `quality_gate.sh:239-248`
**Bug hypothesis:**

The gate at lines 239-248 validates that per-bug required fields exist using `json_key_count`:

```bash
for field in id requirement red_phase green_phase verdict fix_patch_present writeup_path; do
    local fcount
    fcount=$(json_key_count "$json_file" "$field")
    if [ "$fcount" -ge "$bug_count" ]; then
        pass "per-bug field '${field}' present (${fcount}x)"
    ...
```

This only checks that the field NAME exists (counting occurrences of `"requirement":` in the file). It does NOT validate that the `requirement` field's VALUE follows the REQ-NNN format vs UC-NN:Description format.

Template 1 (SKILL.md:135) uses: `"requirement": "UC-03: Description of the requirement violated"`
Template 2 (SKILL.md:1385) uses: `"requirement": "REQ-003"`

Both pass the gate's presence check. But downstream tools expecting `REQ-NNN` format would fail on Template 1 output, and tools expecting `UC-NN:` format would fail on Template 2 output. The gate's field-presence-only check provides false confidence that the output is interoperable.

This confirms and extends BUG-L11 (two incompatible templates). The gate does not help resolve the ambiguity — both formats pass.

**Severity:** This is BUG-L11 propagated to gate enforcement. Not a new bug, but documents the gap in gate validation.

---

## Finding 9: `quality_gate.sh:293-298` — Verdict enum validation uses `grep -cvE` but the OR-group in the regex is missing the `"deferred"` value added in v1.3.49

**File:Line:** `quality_gate.sh:293-298`
**Bug hypothesis:**

```bash
bad_verdicts=$(grep -oE '"verdict"[[:space:]]*:[[:space:]]*"[^"]*"' "$json_file" 2>/dev/null \
    | sed 's/.*: *"\(.*\)"/\1/' \
    | grep -cvE '^(TDD verified|red failed|green failed|confirmed open|deferred)$' || true)
```

Line 296: The regex `^(TDD verified|red failed|green failed|confirmed open|deferred)$` includes "deferred". But look at what SKILL.md line 149 specifies as valid verdicts:

> `verdict` must be one of: `"TDD verified"`, `"red failed"`, `"green failed"`, `"confirmed open"`, `"deferred"`

The gate regex at line 296 DOES include `deferred`. So this appears correct. But checking SKILL.md line 1424:

> Valid `verdict` values: `"TDD verified"` (FAIL→PASS), `"red failed"` (test passed on unpatched code — test doesn't detect the bug), `"green failed"` (test still fails after fix — fix is incomplete or patch is corrupt), `"confirmed open"` (red phase ran and confirmed the bug, no fix patch available), `"deferred"` (TDD cannot execute in this environment...)

Gate and spec agree. So no new bug here.

BUT: `"skipped"` — SKILL.md line 1421 says: `"verdict": "skipped"` — this value is deprecated; use `"confirmed open"` with `red_phase: "fail"` and `green_phase: "skipped"`. The gate's regex does NOT include `"skipped"`. So a file with `"verdict": "skipped"` would be flagged by the gate as non-canonical. This is the correct behavior.

However: The `red_phase` and `green_phase` valid values per SKILL.md line 1424 are: `"fail"`, `"pass"`, `"error"`, `"skipped"`. But the gate's TDD log first-line tag check (lines 323-325) validates: `RED|GREEN|NOT_RUN|ERROR`. These are DIFFERENT formats — the JSON field values and the log file first-line tags use DIFFERENT vocabularies.

**Code path trace:**
- tdd-results.json: `"red_phase": "fail"` (JSON value per SKILL.md spec)
- quality/results/BUG-001.red.log first line: `RED` (log file tag per gate enforcement, lines 323-325)
- Gate validates the LOG FILE tag (RED/GREEN/NOT_RUN/ERROR) separately from the JSON VALUE (fail/pass/error/skipped)
- No gate check validates that the JSON `red_phase` value is consistent with the log file's first-line tag
- A file with `"red_phase": "pass"` and a log with first line `RED` passes both checks, even though they contradict each other (sidecar says green phase passed, log says it was a red/fail)

**Severity:** MEDIUM — the sidecar JSON's `red_phase` value is never validated against the log file's tag, allowing contradictions between the JSON report and the log evidence. This undermines the TDD sidecar-to-log consistency check mandated by SKILL.md line 1589.

This is a NEW finding — the cross-field consistency between sidecar JSON values and log file tags.

---

## Finding 10: `SKILL.md:376` — Autonomous fallback applies to Phase 1 Step 0 only, but Mandatory First Action (lines 37-39) has no autonomous-mode qualifier

**File:Line:** `SKILL.md:37-39` and `SKILL.md:376`
**Bug hypothesis:**

SKILL.md line 37-38:
> **MANDATORY FIRST ACTION:** After reading and understanding the plan above, print the following message to the user, then explain the plan in your own words...

SKILL.md line 376:
> **Autonomous fallback:** When running in benchmark mode, via `run_playbook.sh` (benchmark runner), or without user interaction (e.g., `--single-pass`), skip Step 0's question and proceed directly to Step 1.

The autonomous fallback at line 376 only covers "Step 0: Ask About Development History." The MANDATORY FIRST ACTION at lines 37-39 has NO autonomous-mode qualifier. In benchmark/autonomous mode, agents print the mandatory first-action message to... nobody. The output is discarded (benchmark mode captures stdout but doesn't display it). This wastes context tokens on output that serves no purpose.

More critically: the "Mandatory First Action" instructs agents to "explain the plan in your own words" — this is a multi-paragraph output that in autonomous mode consumes context window that could be used for exploration depth. An agent in benchmark mode that faithfully follows the MANDATORY FIRST ACTION spends significant context generating user-facing prose before the first line of code is read.

This is BUG-REQ-008 (already confirmed) — "The conflict between mandatory interactive output and autonomous mode must be resolved with an explicit scope condition." This finding adds detail about the SPECIFIC costs: context waste and token budget drain in benchmark mode.

**Severity:** Confirming/expanding BUG-REQ-008 (not a new bug).

---

## Finding 11: `quality_gate.sh:331` — `ls ${q}/patches/${bid}-fix*.patch &>/dev/null` uses `ls` with unquoted glob that may expand to listing CWD under nullglob

**File:Line:** `quality_gate.sh:331`
**Bug hypothesis:**

```bash
if ls ${q}/patches/${bid}-fix*.patch &>/dev/null; then
```

This checks whether a fix patch exists for bug `$bid`. It uses `ls` with an unquoted glob. Under `nullglob`, an unmatched glob expands to empty, so `ls` receives no arguments and lists CWD — but `&>/dev/null` suppresses ALL output (both stdout and stderr). Under `nullglob`, `ls` with no args succeeds (exits 0). So this check evaluates TRUE even when no fix patch exists.

**Consequence:** When `nullglob` is active:
- No fix patch → `ls` lists CWD → exits 0 → condition TRUE
- Gate increments `green_expected` (line 343: `green_expected=$((green_expected + 1))`)  
- Gate then checks for `quality/results/${bid}.green.log` at line 333
- If green log doesn't exist: `fail "${green_missing} bug(s) with fix patches missing green-phase log"`

So under `nullglob`, the gate INCORRECTLY requires green-phase logs for bugs that have NO fix patch. This causes false FAIL results — bugs with no fix patch must still have green logs according to the gate.

This is in BUG-M8's description: "line 331 uses `if ls ${q}/patches/${bid}-fix*.patch &>/dev/null` where `&>/dev/null` suppresses all output but under nullglob `ls` with no args returns exit code 0 (success), causing the gate to spuriously require a green-phase log even when no fix patch exists." So this IS BUG-M8 and it IS documented. But is it in BUG-M8's fix patch?

**Checking:** BUG-M8's confirmed locations were: "lines 152-153, 331, 567-568, 595." Line 331 IS included in BUG-M8. So this is not a new bug — it's confirming BUG-M8's line 331 manifestation.

---

## Finding 12: `SKILL.md` Phase 4 — The "individual auditor artifacts" requirement specifies `YYYY-MM-DD-auditor-N.md` naming but no gate check enforces this naming pattern

**File:Line:** `SKILL.md:1548` and `quality_gate.sh:153`
**Bug hypothesis:**

SKILL.md line 1548:
> "The spec audit must produce individual auditor report files at `quality/spec_audits/YYYY-MM-DD-auditor-N.md`"

quality_gate.sh line 153:
```bash
auditor_count=$(ls ${q}/spec_audits/*auditor* 2>/dev/null | wc -l | tr -d ' ')
```

The gate checks for files matching `*auditor*` — which matches ANY file containing "auditor" in the name, including `auditor_a.md`, `auditor_b.md`, `2026-04-16-auditor-1.md`, `gap_auditor_a.md`, etc. All three naming conventions in BUG-L9 pass this check. The gate does NOT enforce the `YYYY-MM-DD-auditor-N.md` format.

Additionally, the glob `*auditor*` also matches `triage_probes.sh` if it contains "auditor" in its name (it doesn't in this case, but the pattern is permissive). More relevantly: `auditor_a.md` has been confirmed to pass this check even though it doesn't follow the required `YYYY-MM-DD-auditor-N.md` format.

This is BUG-L9 (already confirmed) — the naming inconsistency. This finding adds the gate-enforcement gap: the gate is too permissive in what it accepts.

**Severity:** This is BUG-L9 (already confirmed). Not a new bug.

---

## Finding 13: `quality_gate.sh:393-395` — Integration sidecar JSON validated for 8 required keys but SKILL.md specifies only 8 canonical keys with `uc_coverage` being frequently mis-generated

**File:Line:** `quality_gate.sh:393-395`
**Bug hypothesis:**

```bash
for key in schema_version skill_version date project recommendation groups summary uc_coverage; do
    json_has_key "$ij" "$key" && pass "has '${key}'" || fail "missing key '${key}'"
done
```

This checks 8 keys using `json_has_key` which (BUG-H1) matches key names in string values too. So a file containing `"notes": "uc_coverage was calculated as..."` passes the `uc_coverage` check even if the actual `uc_coverage` key is missing.

But more interesting: the spec at SKILL.md line 162-163:
> `uc_coverage` maps UC identifiers from REQUIREMENTS.md to coverage status.

The gate only checks that `uc_coverage` exists as a key — it doesn't validate the mapping format, the UC identifiers, or the coverage status values. A file with `"uc_coverage": "not calculated"` passes the gate. This means the uc_coverage field provides no audit assurance.

**Severity:** LOW — builds on BUG-H1. The `uc_coverage` validation gap is a weak check but not catastrophic.

---

## Finding 14: `SKILL.md` Phase 2 completion gate vs Phase 3 start — no gate checks that `REQUIREMENTS.md` contains REQ-NNN identifiers before code review begins

**File:Line:** `SKILL.md:1469-1474` (Phase 2 completion gate)
**Bug hypothesis:**

The Phase 2 completion gate (lines 1469-1474) verifies:
1. All core artifacts exist on disk
2. REQUIREMENTS.md contains requirements with "specific conditions of satisfaction referencing actual code"
3. If dispatch contracts exist: mechanical/verify.sh exists
4. PROGRESS.md marks Phase 2 complete

Condition 2 is: "requirements with specific conditions of satisfaction referencing actual code (file paths, function names, line numbers) — not abstract behavioral descriptions." This is a PROSE check — there's no mechanical enforcement. An agent can self-attest "REQUIREMENTS.md references file paths" without actually checking.

More importantly: the Phase 2 completion gate does NOT check that requirements use REQ-NNN identifiers. An agent could write REQUIREMENTS.md with bullet points and no REQ-NNN IDs, claim it passes the gate, and proceed to Phase 3. The code review's Pass 2 depends on REQ-NNN identifiers ("For each requirement REQ-N, check whether the code satisfies it"). If requirements lack identifiers, Pass 2 cannot properly trace findings.

**Severity:** LOW — a procedural gap in the Phase 2 completion gate. No new bug, but a documentation gap.

---

## Finding 15: `quality_gate.sh:278-283` — `tdd-results.json` date comparison `[[ "$tdd_date" > "$today" ]]` is lexicographic string comparison

**File:Line:** `quality_gate.sh:278-283`
**Bug hypothesis:**

```bash
local today
today=$(date +%Y-%m-%d)
if [[ "$tdd_date" > "$today" ]]; then
    fail "tdd-results.json date '${tdd_date}' is in the future"
```

For ISO 8601 YYYY-MM-DD format, lexicographic string comparison produces correct chronological ordering. However, there's an edge case: if `tdd_date` is, say, `2026-04-16` and `today` is `2026-04-16` (same day), `"$tdd_date" > "$today"` evaluates to FALSE — correctly passing. If `tdd_date` is `2026-04-17` (tomorrow) and today is `2026-04-16`, `"2026-04-17" > "2026-04-16"` — TRUE — correctly failing.

This appears correct for valid ISO 8601 dates. DC-001 from the demoted candidates already analyzed this: "For ISO 8601 dates (YYYY-MM-DD), lexicographic comparison correctly implements chronological ordering."

**Status:** Confirming DC-001 is correctly demoted. Not a new bug.

---

## Finding 16: `SKILL.md:897-904` Phase 2 entry gate — check 4 says "At least 3 sections starting with `## Pattern Deep Dive — `" but baseline run produced exactly 3, on the boundary

**File:Line:** `SKILL.md:897-904`
**Bug hypothesis:**

Phase 2 entry gate check 4: "At least 3 sections starting with `## Pattern Deep Dive — ` — must exist verbatim."

The Phase 1 instructions say: "Select 3 to 4 patterns for deep-dive treatment." Select 4 when warranted, "default to 3 when in doubt." The minimum required for the Phase 2 gate is 3.

If an agent selects exactly 3 patterns (the minimum) and writes 3 deep-dive sections, it passes the Phase 2 gate exactly at the boundary. But the Phase 1 gate check 8 says "3-4 FULL patterns" — also satisfied. This boundary condition is not a bug (3 is the defined minimum), but it illustrates how the gate is set at the minimum bar, making it possible to pass with minimal exploration depth.

**Status:** Not a new bug. Confirming that the spec is internally consistent (both gates require minimum 3 deep dives).

---

## Finding 17: `SKILL.md` Recheck Mode — `recheck-results.json` uses `schema_version: "1.0"` while the SKILL.md canonical examples template at line 165 uses `"SHIP"` not `"FIX BEFORE MERGE"` for recommendation

**File:Line:** `SKILL.md:1965`, `SKILL.md:158-166`
**Bug hypothesis (EXTENDED from BUG-L10):**

BUG-L10 identified that `recheck-results.json` uses `schema_version: "1.0"` while other artifacts use `"1.1"`. Looking more carefully at the recheck spec:

SKILL.md line 1953:
> Status values: FIXED, PARTIALLY_FIXED, STILL_OPEN, INCONCLUSIVE

The gate does NOT validate these status values (BUG-M15). But even more: the spec says "INCONCLUSIVE" (mixed case with underscores) while common patterns in similar systems use lowercase or hyphenated. If a future gate version adds recheck validation, it must know the exact expected enum values.

Additionally, the `recheck-results.json` `summary` object (lines 1984-1990):
```json
"summary": {
  "total": <N>,
  "fixed": <N>,
  "partially_fixed": <N>,
  "still_open": <N>,
  "inconclusive": <N>
}
```

The summary keys use LOWERCASE (`fixed`, `partially_fixed`) while the per-result `status` field uses UPPERCASE (`FIXED`, `PARTIALLY_FIXED`). This is an internal inconsistency within the recheck schema: the enum values and the summary keys are different cases for the same concepts.

**Severity:** LOW (extends BUG-L10) — the case inconsistency within the recheck schema is a latent bug. When BUG-M15 is fixed by adding gate validation, the gate will need to decide which case to validate.

---

## Finding 18: `quality_gate.sh:596-603` — The writeup `for` loop has a correct `[ -f "$wf" ] || continue` guard (unlike other ls-glob patterns) — but the COUNT at line 595 doesn't

**File:Line:** `quality_gate.sh:595-603`
**Bug hypothesis:**

```bash
writeup_count=$(ls ${q}/writeups/BUG-*.md 2>/dev/null | wc -l | tr -d ' ')
# Check each writeup for inline diff (section 6 requirement)
# Note: the [ -f "$wf" ] guard handles the case where the glob doesn't match
for wf in "${q}"/writeups/BUG-*.md; do
    [ -f "$wf" ] || continue
```

The `for wf in "${q}"/writeups/BUG-*.md` loop has a `[ -f "$wf" ] || continue` guard — this correctly handles the case where the glob doesn't match (the unexpanded glob literal is passed to `[ -f ]`, which returns false for a path containing `*`, so the loop skips). This is correct bash handling.

BUT: line 595 uses `ls ${q}/writeups/BUG-*.md 2>/dev/null | wc -l` — same nullglob vulnerability as BUG-M8. Under nullglob, unmatched glob → ls lists CWD → `wc -l` returns nonzero.

So the DIFF count (`writeup_diff_count`) is correctly computed via the guarded loop, but the TOTAL count (`writeup_count`) is incorrectly computed via the vulnerable ls-glob.

**Code path trace under nullglob, no writeups exist:**
- Line 595: `writeup_count=$(ls ${q}/writeups/BUG-*.md 2>/dev/null | wc -l)` → `ls` lists CWD → `wc -l` = N (some large number, e.g., 50)
- Line 598: `for wf in "${q}"/writeups/BUG-*.md` → glob expands to literal path with `*` under nullglob? Actually under nullglob in a `for` loop, unexpanded globs don't expand at all (unlike `ls`). So the loop runs with `wf = "${q}/writeups/BUG-*.md"` (the literal glob string)
- Line 599: `[ -f "${q}/writeups/BUG-*.md" ]` → FALSE (not a regular file) → `continue`
- `writeup_diff_count` stays 0

Result: `writeup_count` = 50 (from CWD listing), `writeup_diff_count` = 0.
- Line 605: `if [ "$writeup_count" -ge "$bug_count" ]` → 50 >= (some bug count) → TRUE → `pass "50 writeup(s) for N bug(s)"` (WRONG)
- Line 614-621: `if [ "$writeup_count" -gt 0 ]` → TRUE → inline diff check: `if [ "$writeup_diff_count" -ge "$writeup_count" ]` → 0 >= 50 → FALSE → `fail "Only 0/50 writeup(s) have inline fix diffs"`

So under nullglob with no writeups: gate incorrectly passes the writeup count (50 when 0 expected) and then incorrectly fails the diff check (0/50). Double false result.

This is an EXTENSION of BUG-M8 that was not in BUG-M8's fix scope (lines 152-153, 331, 567-568, 595). Wait — line 595 IS in BUG-M8's scope per the bug description: "Affected artifact checks: spec_audits triage file presence (line 152), spec_audits auditor file presence (line 153), patch counting (lines 567-568), writeup counting (line 595)."

So line 595 IS already in BUG-M8. But the fix patch... let me verify: BUG-M8 description says "lines 152-153, 331, 567-568, 595." Yes, line 595 is included. The inconsistency is that the writeup loop at lines 598-603 uses the correct pattern (for loop with file guard) while line 595 uses ls-glob. The fix for BUG-M8 at line 595 would replace the ls-glob with find — the loop is correct as-is.

**Status:** Confirming BUG-M8 scope includes line 595. Not a new finding, but adds analysis of the inconsistent pattern within the same function.

---

## Finding 19: Cross-file contract — `SKILL.md` Phase 5 mandates `quality_gate.sh` exits 0 before marking Phase 5 complete, but `quality_gate.sh` itself has the BUG-M8 nullglob vulnerability that causes false FAILs — creating a circular dependency

**File:Line:** `SKILL.md:1650` and `quality_gate.sh:124,595,153` (BUG-M8 locations)
**Bug hypothesis:**

SKILL.md line 1650 (Phase 5 closure gate):
> "Do not mark Phase 5 complete until `quality_gate.sh` exits 0."

But `quality_gate.sh` has BUG-M8: the nullglob vulnerability causes the gate to FAIL even when all artifacts are correctly present. Specifically:
- Line 124: `ls ${q}/test_functional.*...` → under nullglob, fails even when `test_functional.sh` exists
- Result: gate exits 1 with "functional test file missing"

So the Phase 5 closure mandate is IMPOSSIBLE to satisfy on systems where nullglob is active (macOS default zsh). An agent running in macOS/zsh environment:
1. Creates all required artifacts correctly
2. Runs `quality_gate.sh` → exits 1 due to BUG-M8 nullglob false fail
3. Phase 5 says "do not mark complete until gate exits 0"
4. Agent cannot mark Phase 5 complete
5. Or: agent ignores the failure (knowing it's BUG-M8) and marks complete anyway

This creates a Catch-22: the Phase 5 completion gate is enforced by a script that has a known bug causing false failures. The Quality Playbook's own self-audit demonstrates this: "Phase 5 Checkpoint: completed 2026-04-16" but "Quality gate closure: Gate exits 1 (1 FAIL) due to BUG-M8 self-referential manifestation."

**Severity:** This documents an emergent system-level failure: the combination of BUG-M8 and the Phase 5 closure mandate creates a situation where correct runs cannot complete their closure verification on affected systems.

---

## Finding 20: `quality_gate.sh` — The `--all` mode at line 678 uses `"${SCRIPT_DIR}/"*-"${VERSION}"/"` glob which fails silently when `VERSION` is empty

**File:Line:** `quality_gate.sh:677-680`
**Bug hypothesis:**

```bash
if [ "$CHECK_ALL" = true ]; then
    for dir in "${SCRIPT_DIR}/"*-"${VERSION}"/; do
        [ -d "$dir/quality" ] && REPO_DIRS+=("$dir")
    done
```

When `VERSION` is empty (no `--version` flag), the glob becomes `"${SCRIPT_DIR}/"*-""/` which expands to `${SCRIPT_DIR}/*-/` — a literal dash at the end with no version. No directories match this pattern (repo directories are named `reponame-1.3.27/`, not `reponame-/`). So `REPO_DIRS` remains empty and the gate proceeds to the `if [ ${#REPO_DIRS[@]} -eq 0 ]` check at line 700, printing usage and exiting 1.

This is CORRECT behavior (the gate fails with usage when no repos are found). BUT: the error message at line 701 says "Usage: $0 [--version V] [--all | repo1 repo2 ... | .]" — not "No repos found matching version ''". A user who forgot `--version` gets a generic usage message without understanding they need to specify a version.

More subtly: if a user runs `./quality_gate.sh --all --version 1.4.1` in a directory with no `*-1.4.1/` subdirectories, they get the same generic usage message. The error doesn't distinguish between "you forgot --version" and "no repos found for this version."

**Severity:** LOW — usability issue, not a correctness bug. Not a new confirmed bug but worth noting.

---

## Candidate Bugs Summary (Iteration 3 — Unfiltered)

New confirmed candidates not in previous iterations:

### CAND-U1: `quality_gate.sh:124` — Functional test file existence check uses ls-glob vulnerable to nullglob (same class as BUG-M8/M12/M13)
- **File:Line:** `quality_gate.sh:124`
- **Severity:** MEDIUM
- **Hypothesis:** Line 124 `ls ${q}/test_functional.* ${q}/FunctionalSpec.* ...` under nullglob → ls lists CWD → exits 0 → gate passes when no functional test file exists. NOT in BUG-M8 fix scope (which covers 152-153, 331, 567-568, 595). NOT in BUG-M12 fix scope (line 479). NOT in BUG-M13 fix scope (line 143).
- **Different from prior bugs:** BUG-M13 is at line 143 (code_reviews check), BUG-M12 is at line 479 (extension detection), BUG-M8 is at lines 152-153/331/567-568/595. Line 124 is the FILE EXISTENCE check, not covered by any prior fix patch.

### CAND-U2: `quality_gate.sh:184,313` — BUGS.md heading regex and bug_ids extraction both use `BUG-[0-9]+` which never matches QFB severity-prefix format (`BUG-H1`, `BUG-M3`, etc.), causing gate to treat all QFB self-audit runs as zero-bug runs and bypass TDD/patch/writeup validation
- **File:Line:** `quality_gate.sh:184` and `quality_gate.sh:313`
- **Severity:** HIGH
- **Hypothesis:** `grep -cE '^### BUG-[0-9]+'` at line 184 doesn't match `### BUG-H1`. Sets `bug_count=0`. All downstream checks (TDD logs, patches, writeups) gated on `bug_count > 0` are skipped. The gate silently provides zero quality assurance for runs using severity-prefix bug IDs.
- **Different from BUG-L9:** BUG-L9 is about auditor FILE NAMING formats. This is about BUG ENTRY ID formats and their impact on gate validation.

### CAND-U3: `quality_gate.sh:293-298` vs `quality_gate.sh:307-387` — TDD sidecar JSON `red_phase`/`green_phase` enum values are never cross-validated against log file first-line tags
- **File:Line:** `quality_gate.sh:307-387` (log validation) and `quality_gate.sh:239-248` (JSON field presence)
- **Severity:** MEDIUM
- **Hypothesis:** Gate validates JSON field `red_phase` only for PRESENCE (not value). Gate validates log file first-line tag (RED/GREEN/NOT_RUN/ERROR) separately. No check compares them. A file claiming `"red_phase": "pass"` with a log showing first line `RED` (meaning it was actually a fail/red) passes both checks despite contradiction.
- **Different from prior bugs:** This is a gap in cross-artifact consistency validation, not caught by any prior bug.

EOF
