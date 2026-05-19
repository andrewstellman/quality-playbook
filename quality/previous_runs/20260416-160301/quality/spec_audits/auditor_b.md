# Auditor B Report — User Experience Auditor

<!-- Quality Playbook v1.4.1 — Phase 4 Spec Audit — 2026-04-16 -->

**Auditor role:** User Experience — does the system actually work as described? Gaps between what documentation promises and what code delivers.

---

## Pre-Audit Docs Validation

No `docs_gathered/` directory. Auditors relied on in-repo specifications and code only.

**Verifying TOOLKIT.md claims against SKILL.md:**

**Claim:** TOOLKIT.md line 48: "After all six phases, the key output files are: `quality/BUGS.md`, `quality/PROGRESS.md`, `quality/results/tdd-results.json`..."
- Verification: SKILL.md artifact contract table (lines 88-119) lists these. Gate checks them. CONSISTENT.

**Claim:** TOOLKIT.md line 113: `claude -p "..." --dangerously-skip-permissions`
- Verification: This is the benchmark runner invocation. The "autonomous fallback" in SKILL.md line 376 handles this case. CONSISTENT.

**Claim:** TOOLKIT.md line 127: `gh copilot -p "..." --model gpt-5.4 --yolo`
- Verification: SKILL.md does not reference `gpt-5.4` by name anywhere. TOOLKIT.md references a model name that may be stale. Low severity — model names change.

---

## quality_gate.sh

### Finding B-1 (NET-NEW)

- **Lines 143-145:** UNDOCUMENTED [Req: inferred — SKILL.md artifact contract] The gate checks `code_reviews/` directory for `.md` files using an unquoted `ls` glob, which has undefined behavior when no `.md` files exist.
  ```bash
  if [ -d "${q}/code_reviews" ] && [ -n "$(ls ${q}/code_reviews/*.md 2>/dev/null)" ]; then
  ```
  Under bash with `nullglob` disabled (default), `ls ${q}/code_reviews/*.md` when no `.md` files exist expands the glob literally and `ls` produces an error. The `2>/dev/null` suppresses this, so `$(ls ...)` returns empty string. This works correctly. HOWEVER: if the directory exists but has only non-`.md` files (e.g., a `README` without extension), the gate passes with `fail "code_reviews/ missing or empty"` because the literal glob expands to a non-existent path. This is functionally correct but relies on error suppression and could behave differently under `failglob`.
  
  More importantly: the gate does NOT check that code reviews contain actual BUG/VIOLATED/INCONSISTENT entries — it only checks for `.md` file existence. This means a partial code review session (a template with section headers but no findings) passes the gate. The `spec_audit.md` reference file explicitly states: "If `quality/code_reviews/` exists but contains no `.md` files with actual findings... the code review did not run. Mark this as FAILED in PROGRESS.md, not as 'complete with no findings.'" SKILL.md does not implement this check in the gate.

### Finding B-2 (NET-NEW)

- **Lines 156-173:** DIVERGENT [Req: Tier 1 — SKILL.md line 1548] The gate checks for triage_probes.sh OR mechanical/verify.sh with probe annotations, but SKILL.md Phase 4 (line 1319) says probes must appear in "either appended to `quality/mechanical/verify.sh` or written to a dedicated `quality/spec_audits/triage_probes.sh`".
  Gate lines 160-173:
  ```bash
  if [ -f "${q}/spec_audits/triage_probes.sh" ]; then
      has_probes=true
  elif [ -f "${q}/mechanical/verify.sh" ] && grep -q 'probe\|triage\|auditor' "${q}/mechanical/verify.sh"; then
      has_probes=true
  fi
  ```
  The gate in `--general` mode issues a WARN rather than FAIL when no probes exist (line 168-171). SKILL.md Phase 4 says "Triage evidence must be written to disk... The gate checks for the existence of probe assertions in the triage output; a triage report that says 'verification probe confirms...' without a corresponding assertion in an executable file is non-conformant." The `--general` mode WARN rather than FAIL means the probe requirement is not enforced in general mode. For developer use cases (UC-01, UC-03), this weakens the quality guarantee.

### Finding B-3 (NET-NEW CANDIDATE)

- **Lines 277-284:** DIVERGENT [Req: Tier 2 — REQ-009] The date validation for tdd-results.json at lines 272-290 checks that the date is not in the future. But SKILL.md Phase 5 at line 1416 says: "Use the actual date of this session (e.g., '2026-04-12'), not the template placeholder 'YYYY-MM-DD'." The gate correctly rejects `YYYY-MM-DD` placeholder. However, there is no check that the date matches the skill run date within a reasonable window. A run from 6 months ago with an old date would pass the gate's non-future check. This is a minor gap: dates in the past are accepted without any staleness check.

### Finding B-4 (NET-NEW)

- **Lines 143-145 vs 595-596:** UNDOCUMENTED [Req: inferred] Multiple counting operations use `ls | wc -l` pattern which is known to be fragile for files with newlines in names and produces incorrect counts when globs match no files under some shell configurations.
  ```bash
  triage_count=$(ls ${q}/spec_audits/*triage* 2>/dev/null | wc -l | tr -d ' ')
  ```
  Under bash with `nullglob`, `ls` receives no arguments and lists the current directory, producing a non-zero count that is not the count of triage files. The `2>/dev/null` suppresses the error but does not prevent the wrong-directory listing. This is the more serious variant of the unquoted glob issue: `ls *triage*` with nullglob expands to empty, so `ls` lists `.` and `wc -l` returns the line count of the current directory listing. For a directory with 15 entries, `triage_count` would be 15, causing `[ "$triage_count" -gt 0 ]` to incorrectly PASS even when no triage file exists.
  
  **This is a net-new confirmed bug candidate**: the `2>/dev/null` suppresses the `ls: cannot access '*triage*': No such file or directory` message but does not prevent `ls` from running with no glob arguments in some shells, which then outputs current-directory contents.

### Finding B-5 (NET-NEW CANDIDATE)

- **SKILL.md lines 61-67:** PHANTOM [Req: Tier 2 — REQ-009] The artifact contract (SKILL.md lines 88-119) says EXPLORATION.md is "Required: Yes" and created in Phase 1. But the gate's file existence check at quality_gate.sh lines 135-140 checks `EXPLORATION.md` separately:
  ```bash
  if [ -f "${q}/EXPLORATION.md" ]; then
      pass "EXPLORATION.md exists"
  else
      fail "EXPLORATION.md missing"
  fi
  ```
  The gate passes if `EXPLORATION.md` is an empty file (0 bytes). SKILL.md Phase 1 requires at least 120 lines of substantive content. The gate does not enforce this minimum content threshold. An agent that creates an empty `EXPLORATION.md` to pass the gate would produce an artifact that passes the gate check but violates the spec's 120-line minimum requirement.

---

## SKILL.md

### Finding B-6 (NET-NEW CANDIDATE)

- **SKILL.md line 376 vs SKILL.md line 37:** DIVERGENT [Req: Tier 2 — REQ-008] "MANDATORY FIRST ACTION" has no cross-reference to autonomous fallback at line 376.
  SKILL.md line 37-40: "MANDATORY FIRST ACTION: After reading and understanding the plan above, print the following message to the user..."
  SKILL.md line 376: "Autonomous fallback: When running in benchmark mode... skip Step 0's question and proceed directly to Step 1."
  The autonomous fallback explicitly covers "Step 0" (ask about development history) but does NOT explicitly cover the "MANDATORY FIRST ACTION" print step at line 37. An agent in benchmark mode might correctly skip Step 0's question but still print the "Quality Playbook v1.4.1" banner because the Mandatory First Action rule does not include a "skip in autonomous mode" qualifier. This is confirmed BUG already identified as BUG-L8 in the requirements (REQ-008), independently flagged.

### Finding B-7 (NET-NEW)

- **SKILL.md line 1966 vs lines 122-148:** DIVERGENT [Req: Tier 1 — SKILL.md line 1416] Recheck mode schema example at line 1966 uses `"schema_version": "1.0"` while the canonical examples and gate enforce `"1.1"`.
  The artifact contract at SKILL.md lines 122-148 shows both `tdd-results.json` and `integration-results.json` with `"schema_version": "1.1"`. Recheck introduces a third JSON artifact (`recheck-results.json`) with `"schema_version": "1.0"`. There is no migration note or explanation of why recheck uses `1.0`. From a user perspective, running `quality_gate.sh` after a recheck and finding a `schema_version: "1.0"` file would suggest an outdated artifact — even if it is intentionally versioned at `1.0`. The gate does NOT check `recheck-results.json` at all, so users get no mechanical verification of recheck output conformance.

### Finding B-8 (NET-NEW CANDIDATE)

- **SKILL.md line 1420-1421:** DIVERGENT [Req: Tier 1] `"verdict": "skipped"` is listed as deprecated in SKILL.md ("this value is deprecated; use 'confirmed open'"), but quality_gate.sh verdict enum validation at lines 294-298 allows `"deferred"` but NOT `"skipped"`:
  ```bash
  grep -cvE '^(TDD verified|red failed|green failed|confirmed open|deferred)$'
  ```
  This means `"skipped"` would cause a gate FAIL (it is not in the allowed enum). The deprecation warning in SKILL.md is effectively already an enforcement — the gate would reject it regardless. But the spec says "deprecated" as if it might still be accepted. From a user perspective, generating `"skipped"` based on the deprecation warning (rather than an outright prohibition) would cause a gate FAIL without a clear error message. The gate just reports "non-canonical verdict value(s)" without saying which value or why.

### Finding B-9 (NET-NEW CANDIDATE)

- **SKILL.md line 1100-1104 vs line 1546-1548:** DIVERGENT Fix patch documentation in Phase 3 vs Phase 4 has inconsistent requirements.
  Phase 3 (line 1100-1104): "Every confirmed bug must have either: A `quality/patches/BUG-NNN-fix.patch` that passes the validation gate above, OR An explicit justification in BUGS.md explaining why no fix patch is provided."
  Phase 4 completion gate (line 1546-1548): No equivalent "fix patch or justification" requirement mentioned. Spec audit bugs discovered in Phase 4 could be confirmed without a fix patch AND without a justification, and no gate would catch this. The Phase 3 mandate applies explicitly to Phase 3 code review bugs — Phase 4 net-new bugs may be treated as not requiring fix patches or justifications.

---

## ai_context/TOOLKIT.md

### Finding B-10 (NET-NEW CANDIDATE)

- **TOOLKIT.md line 113:** UNDOCUMENTED TOOLKIT.md describes using `--dangerously-skip-permissions` for Claude Code. This is a production recommendation in the reference documentation. DEVELOPMENT_CONTEXT.md (the maintainer-facing doc) at lines 111-112 references the same flag. SKILL.md itself (line 376) references "benchmark mode" and "run_playbook.sh" as the autonomous invocation pattern. There is no warning in TOOLKIT.md that `--dangerously-skip-permissions` allows the agent to execute arbitrary shell commands including potentially destructive ones. The playbook's source-code-boundary rule (SKILL.md line 1027) says "the playbook must never modify files outside `quality/`" but this is an instruction to the agent, not enforced by the shell. A user following TOOLKIT.md's "Quick start" with `--dangerously-skip-permissions` has no sandbox. This is a documentation gap — the user-facing docs should mention the risk. Not a code bug but a user experience gap.

---

## Summary of New Findings

| ID | Location | Type | Net-New? | Severity |
|----|----------|------|----------|---------|
| B-1 | quality_gate.sh:143-145 | UNDOCUMENTED | YES | LOW |
| B-2 | quality_gate.sh:168-171 | DIVERGENT | YES | LOW |
| B-3 | quality_gate.sh:272-290 | DIVERGENT | YES | LOW |
| B-4 | quality_gate.sh:152-153 | UNDOCUMENTED (nullglob) | **YES** | MEDIUM |
| B-5 | quality_gate.sh:135-140 | MISSING | YES | LOW |
| B-6 | SKILL.md:37 vs 376 | DIVERGENT (REQ-008) | No (BUG-L8 class) | LOW |
| B-7 | SKILL.md:1966 | DIVERGENT | YES | LOW |
| B-8 | SKILL.md:1420 | DIVERGENT | YES | LOW |
| B-9 | SKILL.md:1100 vs 1547 | DIVERGENT | YES | LOW |
| B-10 | TOOLKIT.md:113 | UNDOCUMENTED | YES | LOW |
