# Spec Audit Protocol: quality-playbook

<!-- Quality Playbook v1.4.1 — generated 2026-04-16 -->

## Council of Three — Definitive Audit Prompt

Give this prompt identically to three independent AI tools (e.g., Claude, GPT-4, Gemini).

---

**Context files to read:**

1. `SKILL.md` — Primary specification and product (2239 lines). This is simultaneously the spec AND the implementation — a Markdown AI instruction document.
2. `quality_gate.sh` — Mechanical post-run validator (723 lines, Bash).
3. `ai_context/DEVELOPMENT_CONTEXT.md` — Architecture, version history, known issues.
4. `ai_context/TOOLKIT.md` — User-facing documentation and technique explanations.
5. `quality/REQUIREMENTS.md` — Derived testable requirements (read this first to understand the expected behavior).

**Task:** Act as the Tester. Read the actual code in `quality_gate.sh` and the spec in `SKILL.md`, then compare them against the requirements in `quality/REQUIREMENTS.md`.

**Requirement confidence tiers:**
Requirements are tagged with `[Req: tier — source]`. Weight your findings by tier:
- **formal** — SKILL.md or requirements_pipeline.md canonical spec. Authoritative. Divergence is a real finding.
- **user-confirmed** — not applicable for this self-audit.
- **inferred** — deduced from quality_gate.sh source code behavior. Lower confidence. Report divergence as NEEDS REVIEW, not as a definitive defect.

**Rules:**
- ONLY list defects. Do not summarize what matches.
- For EVERY defect, cite specific file and line number(s). If you cannot cite a line number, do not include the finding.
- Before claiming missing, grep the codebase.
- Before claiming exists, read the actual function body.
- Classify each finding: MISSING / DIVERGENT / UNDOCUMENTED / PHANTOM
- For findings against inferred requirements, add: NEEDS REVIEW

**Defect classifications:**
- **MISSING** — Spec requires it, code doesn't implement it
- **DIVERGENT** — Both spec and code address it, but they disagree
- **UNDOCUMENTED** — Code does it, spec doesn't mention it
- **PHANTOM** — Spec describes it, but it's actually implemented differently than described

**Project-specific scrutiny areas:**

1. **`json_has_key()` at `quality_gate.sh:75-78`:** Read the exact regex. Does `grep -q "\"${key}\""` match the key name when it appears inside a string value? Compare with what REQ-001 requires.

2. **Array reconstruction at `quality_gate.sh:697`:** Read the exact line. Is `REPO_DIRS=(${resolved[@]+"${resolved[@]}"})` correctly quoted? Compare with how `check_repo` is called at line 711.

3. **Phase 2 entry gate in `SKILL.md`:** Find the Phase 2 entry gate (search for "Phase 2 entry gate" or "backstop"). Count the number of checks it enforces. Compare with the Phase 1 completion gate (12 checks). Identify which Phase 1 checks are NOT enforced by Phase 2.

4. **`quality/test_regression.*` gate check:** In `quality_gate.sh`, does a check exist that enforces `quality/test_regression.*` existence when `bug_count > 0`? Compare with the artifact contract table in SKILL.md lines 88-119.

5. **Phase 0b activation condition in `SKILL.md`:** Read Phase 0b (~line 297). What condition triggers Phase 0b? Does it activate when `previous_runs/` exists but is empty? Is this the intended behavior?

6. **`json_str_val()` at `quality_gate.sh:81-85`:** What does the function return when the key exists but has a non-string value (number, boolean)? Is this distinguishable from "key absent"? What error message does a caller produce?

7. **Version string occurrences in `SKILL.md`:** Find all occurrences of the version string (currently `1.4.1`). Are they all identical to the frontmatter `metadata.version`? Is the JSON example at approximately line 129 consistent with the frontmatter?

8. **"MANDATORY FIRST ACTION" vs autonomous fallback:** Find both instructions (lines ~37 and ~376). Is there a cross-reference? Does the Mandatory First Action include a qualifier for interactive-only scope?

9. **`set -e` absence in `quality_gate.sh:32`:** The script uses `set -uo pipefail` but not `set -e`. Identify any command failures that proceed silently and could produce a wrong PASS result.

10. **Functional test detection (lines 123-126) vs language detection (lines 449-454):** Does the functional test detection use the same method as language detection? If not, describe the difference and its risk.

**Output format:**

### [filename.ext]
- **Line NNN:** [MISSING / DIVERGENT / UNDOCUMENTED / PHANTOM] [Req: tier — source] Description.
  Spec says: [quote or reference]. Code does: [what actually happens].

---

## Pre-Audit Docs Validation

**No `docs_gathered/` directory.** Auditors rely on in-repo specifications and code only. Spec sources available:
- `SKILL.md` (primary spec and product)
- `ai_context/DEVELOPMENT_CONTEXT.md` (architecture/version history)
- `ai_context/TOOLKIT.md` (user-facing documentation)

**Spot-check baseline claims:**

1. **Claim:** "`json_key_count` uses `grep -c "\"${key}\"[[:space:]]*:"` — includes colon, thus requires the key pattern to precede a colon."
   - Verification: Read `quality_gate.sh:88-91` directly. Extract the grep argument.
   - Expected: The function does require a colon.

2. **Claim:** "`json_has_key` uses `grep -q "\"${key}\""` — does NOT include colon, can match key name in string values."
   - Verification: Read `quality_gate.sh:75-78` directly.
   - Expected: The function does NOT require a colon — this is BUG-H1.

3. **Claim:** "`REPO_DIRS=(${resolved[@]+"${resolved[@]}"})` at line 697 is unquoted on the outer expansion."
   - Verification: Read line 697 exactly.
   - Expected: The outer expansion lacks quotes — this is BUG-H2.

---

## Council Status Template

```markdown
## Council Status
- Model A: Fresh report received (YYYY-MM-DD)
- Model B: Fresh report received (YYYY-MM-DD)
- Model C: Fresh report received (YYYY-MM-DD)
```

---

## Triage Decision Matrix

| Confidence | Found By | Action |
|------------|----------|--------|
| Highest | All three | Almost certainly real — confirm and add to BUGS.md |
| High | Two of three | Likely real — verify and fix |
| Needs verification | One only | Deploy triage probe before confirming |

## Triage Probes

For each finding marked "Needs verification," write a shell triage probe:

```bash
# Probe for json_has_key false positive
echo '{"msg": "The id field is deprecated"}' > /tmp/test.json
# The key "id" appears only in a string value
source quality_gate.sh 2>/dev/null || true
json_has_key /tmp/test.json "id" && echo "CONFIRMED: FALSE POSITIVE" || echo "NOT REPRODUCED"
```

Write probes to `quality/spec_audits/triage_probes.sh`.

## Known Open Issues (Seed List from Phase 1)

The following bugs were confirmed in Phase 1 exploration. Auditors should find and report these independently. If an auditor does NOT flag a known seed bug, that is a coverage gap in their review.

| Bug ID | Location | Description |
|--------|----------|-------------|
| BUG-H1 | quality_gate.sh:75-78 | `json_has_key` matches keys in string values |
| BUG-H2 | quality_gate.sh:697 | Unquoted array expansion corrupts paths with spaces |
| BUG-M3 | SKILL.md Phase 1/2 gates | Phase 2 entry gate does not enforce checks 8, 10, 12 |
| BUG-M4 | quality_gate.sh + SKILL.md:94 | test_regression.* not checked by gate (note: revisit after Phase 3) |
| BUG-M5 | SKILL.md Phase 0/0b | Phase 0b skips when previous_runs/ exists but empty |
| BUG-L6 | quality_gate.sh:81-85 | json_str_val misleading error for non-string values |
| BUG-L7 | SKILL.md multiple lines | Version hardcoded in multiple locations |

## Output Directory

Write each auditor's report to `quality/spec_audits/auditor_<model>_<date>.md`.
Write the triage report to `quality/spec_audits/triage_<date>.md`.
