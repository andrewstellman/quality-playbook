# Spec Audit — Auditor B: User Experience (Unfiltered Iteration)

<!-- Quality Playbook v1.4.1 — Unfiltered Iteration Spec Audit Auditor B — 2026-04-16 -->

**Role:** User Experience auditor — checking whether code delivers the experience promised to users.
**Focus:** What does the user SEE when they run quality_gate.sh? Are the error messages correct? Are failures silent?

## Pre-audit docs validation

No supplemental `docs_gathered/` exists. Factual baseline: SKILL.md v1.4.1 and quality_gate.sh source.

---

## quality_gate.sh — User-Visible Gate Behavior

### Lines 184-219: DIVERGENT [Req: inferred — from gate UX contract]
**User expects:** When they have 15 confirmed bugs in BUGS.md using `### BUG-H1` format, the gate processes and validates those bugs.

**What actually happens:** Gate reports `[BUGS.md Heading Format] PASS: Zero-bug run` because `grep -cE '^### BUG-[0-9]+'` returns 0 for severity-prefix IDs. User sees "PASS: Zero-bug run" when they have 15 bugs. This is profoundly misleading — the PASS message reassures the user that their run conformed when actually the gate performed no validation.

Subsequently, all TDD/patch/writeup sections report `INFO: Zero bugs — ... not required` — again misleading. The user cannot tell whether:
a) Their run genuinely found zero bugs, OR
b) Their bugs use severity-prefix IDs that the gate cannot recognize

**This is CAND-U2:** quality_gate.sh:184 — the regex failure silently undermines the gate's assurance.

### Line 124: DIVERGENT [Req: inferred — nullglob behavior]
**User expects:** Gate correctly detects whether functional test file exists.

**What actually happens (under nullglob):** `ls` lists CWD → exits 0 → gate says `PASS: functional test file exists` when none exists. Immediately after, line 479 may also give wrong results. User gets a PASS when they forgot to write tests.

The UX impact: the gate confirms "test file present" → user ships without realizing they have no functional tests → tests are "missing in production" but "present in gate output."

### Lines 239-248: MISSING [Req: formal — SKILL.md:1589]
**User expects:** If their tdd-results.json says a bug was "TDD verified" but the log files show otherwise, the gate alerts them.

**What actually happens:** Gate validates JSON field presence only. A tdd-results.json with `"verdict": "TDD verified"` and a `red.log` showing `RED` (meaning the test failed on unpatched code — correct for red phase) vs `"red_phase": "pass"` (contradicting the log) would pass all gate checks. The user sees no contradiction warning.

---

## SKILL.md — User Instructions vs Actual Behavior

### Line 1615: DIVERGENT [Req: formal — bug ID format spec]
**User expects:** Following SKILL.md's instruction to use `### BUG-NNN (e.g., BUG-001)` format will produce gate-passing artifacts.

**What actually happens:** The QFB itself (in its own self-audit) generates `BUG-H1`, `BUG-M3` format. A user following the spec example (`BUG-001`) would produce artifacts that the gate CAN parse. A user following QFB practice (`BUG-H1`) produces artifacts the gate cannot parse. Users who've read prior QFB run examples (including the self-audit) and follow that convention get silently wrong gate results.

---

## Summary

| Finding | Classification | Impact |
|---------|---------------|--------|
| quality_gate.sh:184,313 — silent zero-bug fallback | DIVERGENT | Gate reports PASS/INFO when it should report findings |
| quality_gate.sh:124 — false test file existence | DIVERGENT | Gate falsely confirms test file present |
| quality_gate.sh:239-248 — no phase value cross-check | MISSING | Contradiction between JSON and logs goes undetected |
| SKILL.md:1615 — example format mismatches practice | DIVERGENT | Users following practice get different gate behavior than spec |

**All 4 findings are net-new from unfiltered iteration or confirm unfiltered candidates.**
