# Challenge Gate — Bug Validity Review

## Purpose

The challenge gate is a self-adversarial review that every confirmed bug must survive before receiving a writeup and regression test. It catches false positives, over-classified feature gaps, and findings where pattern-matching overrode common sense.

The gate can be invoked two ways:

1. **During a playbook run** — automatically applied to bugs matching trigger patterns (see below).
2. **Standalone** — pointed at a `quality/` directory from a prior run to challenge specific bugs. Example: `"Read quality/writeups/BUG-042.md and the source code it references. Run the challenge gate on this bug."`

## The two-round challenge

For each bug under review, run exactly two rounds. Each round uses a fresh sub-agent so the challenger has no investment in the finding.

### Round 1: "Does this strike you as a real bug?"

Provide the sub-agent with:
- The bug writeup (or BUGS.md entry if no writeup yet)
- The actual source code at the cited file:line (read it fresh — do not trust the writeup's code snippet)
- All comments within 10 lines above and below the cited location
- The project's README section on the relevant feature (if any)

Prompt the sub-agent:

> You are reviewing a bug report filed against an open-source project. Read the source code and the bug report below. Then answer: **does this strike you as a real bug?**
>
> **Before analyzing anything, apply common sense.** Step back from the details and ask yourself: if you showed this code and this bug report to a senior developer who has never seen either before, would they say "yes, that's a bug" — or would they say "that's obviously not a bug"? If the answer is obviously not a bug, say so immediately and explain why. Do not rationalize your way past a common-sense answer. The goal of this review is to catch findings where pattern-matching overrode judgment.
>
> Then consider:
> - Is the developer aware of this behavior? (Look for comments, TODO markers, design decision notes, WHY annotations, OODA references.)
> - Is this a documented limitation or intentional trade-off? (Check if other code paths handle this differently by design, not by accident.)
> - Would the project maintainer respond "that's not a bug, that's how it works" or "that's a known limitation we documented"?
> - Is the "expected behavior" in the bug report actually required by any spec, or is it the auditor's opinion about what the code should do?
> - Is this development scaffolding? Values with names like "change-me", "placeholder", "example", "default", "TODO" are not defects — they are self-documenting markers that exist to make the project buildable during development. A feature that is disabled by default and uses placeholder values is an incomplete feature, not a vulnerability.
>
> Give your honest assessment. If it's a real bug, say so and explain why. If it's not, say so and explain why. A finding can be "not a bug" even if the code could be improved — the question is whether a reasonable maintainer would accept this as a defect report.

### Round 2: Targeted follow-up

Based on the Round 1 response, generate a single pointed follow-up question. The goal is to stress-test whatever position the sub-agent took in Round 1.

**If Round 1 said "real bug":** The follow-up should challenge the finding from the maintainer's perspective. Use a fresh sub-agent with this framing:

> You are the maintainer of this project. A contributor filed this bug report. You wrote the code being criticized. Read the code, the bug report, and the Round 1 assessment below.
>
> Write the single most compelling argument for why this is NOT a bug. Consider: intentional design decisions, documented limitations, deployment context, common patterns in this language/framework, and whether the "expected behavior" is actually specified anywhere authoritative.
>
> Then, after making that argument, state whether you still believe it's a real bug or whether the argument convinced you it's not.

**If Round 1 said "not a bug":** The follow-up should challenge the dismissal. Use a fresh sub-agent with this framing:

> You are a security researcher reviewing this codebase. Another reviewer dismissed this finding as "not a bug." Read the code, the bug report, and the Round 1 dismissal below.
>
> Write the single most compelling argument for why this IS a real bug despite the dismissal. Consider: edge cases the dismissal didn't address, downstream consequences, what happens when the code interacts with other components, and whether "intentional" and "correct" are the same thing.
>
> Then, after making that argument, state whether you believe the finding should be confirmed or dismissed.

### Verdict

After both rounds, assign one of three verdicts:

- **CONFIRMED** — Both rounds agree it's a real bug, or Round 2's challenge failed to undermine Round 1's confirmation. The bug proceeds to writeup and regression test as normal.
- **DOWNGRADED** — The bug is real but the severity was inflated. Adjust severity and update the writeup. Common case: a CRITICAL that should be MEDIUM, or a security finding that's actually a code quality issue.
- **REJECTED** — The finding is not a bug. It's a documented design choice, intentional scaffolding, a known limitation, the auditor's opinion rather than a spec violation, or something that common sense says is obviously not a defect. Remove the bug ID. If useful, record it in a "Reviewed and dismissed" appendix in BUGS.md with the challenge reasoning.

Write the verdict and both rounds' reasoning to `quality/challenge/BUG-NNN-challenge.md`. This file is the audit trail — it shows reviewers that each finding was stress-tested.

## Auto-trigger patterns

During a playbook run, automatically apply the challenge gate to any bug matching one or more of these patterns. These patterns are where false positives concentrate:

| Pattern | Why it triggers | Example |
|---------|----------------|---------|
| **Security-class finding** (credential leak, auth bypass, injection) | Severity calibration auto-escalates these; the model is incentivized to defend them | BUG-041: "hardcoded JWT secret" that was a development placeholder |
| **Code contains design-decision comments at the cited location** | WHY comments, OODA references, TODO-with-explanation, or design decision docs within 10 lines of the cited code suggest the developer made a conscious choice | BUG-007/008: `// WHY-OODA81: Batch upload uses "default" workspace` |
| **The "expected behavior" has no spec basis** | Bug's spec_basis field says "code inconsistency" rather than citing a spec document, or the requirement was invented by the auditor (Tier 3 / REQ-NNN created during the run) | BUG-041: REQ-019 was created by the auditor, not derived from project docs |
| **Another code path handles the same concern differently** | If text_upload does X but file_upload doesn't, that might be a real inconsistency — or it might be intentional divergence. The challenge sorts out which. | BUG-001/002: text_upload merges source_ids, file_upload overwrites — challenge confirms this is a real bug because text_upload has an explicit fix comment |
| **The finding is about missing functionality rather than incorrect behavior** | "This handler doesn't do X" is often a feature gap, not a bug. The challenge checks whether X was ever promised. | BUG-009/029: batch upload "missing" graph writes that were never part of the batch upload's documented scope |

The pattern list is intentionally conservative — it triggers on categories with historically high false-positive rates. Bugs that don't match any pattern skip the challenge gate and proceed directly to writeup.

To add new patterns: append a row to the table above with the pattern description, the reasoning, and a concrete example from a prior run.

## Standalone invocation

When invoked standalone (not during a playbook run), the challenge gate:

1. Reads the specified bug writeup from `quality/writeups/BUG-NNN.md`
2. Reads the source code at the cited file:line (fresh read, not from the writeup)
3. Runs both rounds as described above
4. Writes the verdict to `quality/challenge/BUG-NNN-challenge.md`
5. If the verdict is REJECTED, suggests removing the bug from BUGS.md and tdd-results.json

Example prompt for standalone use:
```
Read the quality-playbook skill: walk the canonical ten install-layout fallback list to locate SKILL.md
(SKILL.md / .claude/skills/quality-playbook/SKILL.md / .github/skills/SKILL.md /
.cursor/skills/quality-playbook/SKILL.md / .continue/skills/quality-playbook/SKILL.md /
.github/skills/quality-playbook/SKILL.md / .codex/skills/quality-playbook/SKILL.md /
.windsurf/skills/quality-playbook/SKILL.md / .cline/skills/quality-playbook/SKILL.md /
.aider/skills/quality-playbook/SKILL.md), then load the adjacent references/challenge_gate.md
using the same fallback order. Run the challenge gate on BUG-042 using the writeup at
quality/writeups/BUG-042.md and the source code in this repo.
```

## Token budget

Each bug costs roughly 2 sub-agent calls. For a typical run with 5-10 auto-triggered bugs, that's 10-20 sub-agent calls. This is significantly cheaper than a full iteration cycle and catches the highest-value false positives.

For runs with many security findings (>15 auto-triggered), consider batching: run Round 1 on all triggered bugs first, then only run Round 2 on bugs where Round 1 was ambiguous or where the confidence was low.

---

## Precision guardrails — v1.5.7 instruction 090j

The 2026-05-23 OpenFGA Mode-A dogfood Council (instruction 090i) confirmed a precision failure: 0/3 HIGH-severity findings were real. BUG-003 missed an upstream `tryCache` guard at the SAME file, BUG-006 missed an upstream `userType` filter AND cited a CVE whose affected range doesn't include the audited version, BUG-009 was a verbatim CVE restatement with no in-tree defect. Three same-agent triage rules — D1, D2, D3 below — close those failure modes. They are **mandatory** before a candidate becomes a confirmed `BUG-NNN`. The mechanical gate enforces each rule against `quality/bugs_manifest.json`.

The full FP-audit sub-agent + first-class NFR-requirement derivation are reserved for v1.6.0. Within v1.5.7, these three same-agent rules are the precision band-aid.

### D1 — Reachability check (MANDATORY before confirming any bug)

Before a candidate becomes a confirmed `BUG-NNN`, perform a **reachability analysis**: search the cited code path for any **upstream guard, filter, early-return, or compensating mechanism** that would make the claimed defect unreachable. Capture the result on the manifest record as the field `reachability_analysis`. The field is non-empty-required when the record's `classification` is `bug` (the default) and `severity` is `HIGH` or `MEDIUM`; on `LOW` severity, absence is a WARN, not a FAIL.

**Two outcomes:**

- **Guard NOT found.** The defect is reachable. Quote the search result, then confirm — e.g. `Reachability: no upstream guard found in ±50 lines of cached_resolver.go:200; cache.Get reached unconditionally for all consistency preferences except where blocked downstream`.
- **Guard FOUND that makes the defect unreachable.** The candidate must be **demoted** (not confirmed as a bug) — record the demotion in the run's challenge log and DO NOT emit a `BUG-NNN`. This is exactly the BUG-003 case: the `tryCache` guard at `cached_resolver.go:169` short-circuits HIGHER_CONSISTENCY before the omitted-key issue can matter.

**Gate enforcement:** a confirmed `BUG-NNN` with severity HIGH or MEDIUM and no `reachability_analysis` field (or an empty string) is a **FAIL** in the v1.5.7 090j gate check `check_v1_5_7_090j_triage_precision`. LOW severity without the field is a WARN.

### D2 — KNOWN-ISSUE classification for advisory/CVE-only findings

A finding may only be a `BUG-NNN` if the specific code defect is **independently located and verified in the audited tree** (with D1's reachability analysis). A finding whose **sole basis is a gathered advisory/CVE/doc** — with no located in-tree code defect — must be classified `classification: known-issue`, not as a bug.

**Why:** advisories should be SURFACED to operators (they should upgrade), but they should NOT inflate the bug count or skew precision metrics. The BUG-009 case (CVE-2024-42473 restatement, no in-tree defect found) belongs in a separate `known-issue` category that the gate excludes from bug counts.

**Gate enforcement:** a record with `cve_reference` set AND `classification == "bug"` (or absent — default is `bug`) AND no `reachability_analysis` is a **FAIL** in the v1.5.7 090j gate check. The reachability analysis is the load-bearing evidence that the defect was independently located in the audited tree; its absence + a CVE citation is exactly the "advisory-only" failure mode.

### D3 — Tighter security-HIGH bar

A finding may not be rated **HIGH severity** on a **security / authorization-bypass** basis unless BOTH:

- **(a)** a **reachable code path** demonstrating the bypass is identified in the audited tree (see D1), AND
- **(b)** if the finding cites a CVE, the audited version is **verified to be within the CVE's affected range** — record this on the manifest as `cve_version_applies: true` (boolean; required when `cve_reference` is set).

Absent either, the security framing/severity must be **downgraded to MEDIUM or below** (or the finding reclassified `known-issue` per D2). This is the BUG-006 case: HIGH severity was assigned on a CVE-2025-48371 basis, but the audited v1.5.7 is OUTSIDE the affected range (`>=1.8.0`).

**Gate enforcement:** a record with `severity == "HIGH"` AND `cve_reference` set AND `cve_version_applies != true` (false, null, or missing) is a **FAIL** in the v1.5.7 090j gate check — unless the `reachability_analysis` text contains an explicit prose marker asserting the audited version is within the CVE's affected range (the gate accepts the prose as a fallback so adopters who write the analysis but forget the boolean aren't auto-failed).

### What 090j does NOT add

- **No fresh-context FP-audit sub-agent pass.** The Round-1/Round-2 challenge above is unchanged; 090j is same-agent triage rules. The fresh-context audit is reserved for v1.6.0.
- **No first-class NFR (non-functional requirement) derivation.** Also v1.6.0.
- **No new finding-class for "design observation."** BUG-005/007/008 from the OpenFGA run were 2:1-or-split design/observability/defensive observations, but 090j leaves them as `bug`-classified records — the precision win comes from D1/D2/D3, not from a new class. v1.6.0 may add an `observation` class.

### Worked example — the OpenFGA dogfood under 090j

Under the rules above:

- **BUG-003** (HIGH, cache key omits Consistency): the agent's D1 reachability analysis would have located the `tryCache` guard at `cached_resolver.go:169` — the candidate is **demoted, not confirmed**. If the agent forgets D1, the gate FAILs on missing `reachability_analysis` for a HIGH-severity bug.
- **BUG-006** (HIGH, contextual tuples + CVE-2025-48371): D1 would have located the `userType` filter at `check.go:1102` AND `validateCtxTupleInModel` at `request.go:91`. D3 would have caught the CVE version mismatch (v1.5.7 < 1.8.0 = `cve_version_applies: false`). Either rule alone catches the record — both together force a downgrade or reclassification.
- **BUG-009** (HIGH, CVE-2024-42473 restatement): under D2 the record must be `classification: known-issue`. The advisory is still surfaced to operators (they should upgrade to v1.5.9+), but the record is excluded from the bug count.
- **BUG-001/002/004** (the real bugs): each has an in-tree code defect and a reachable code path — D1's `reachability_analysis` is straightforward (e.g. `BUG-001`: *"no upstream non-empty guard at oidc.go:143-149; type assertion .(string) returns true for empty string; defect reaches authz.go:466-470"*). None cite a CVE, so D2 and D3 don't apply. **They pass clean under 090j's rules** — the precision wins come from filtering the FPs, not from rejecting legitimate findings.
