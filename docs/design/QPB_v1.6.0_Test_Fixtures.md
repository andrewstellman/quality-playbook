# Quality Playbook v1.6.0 — Test Fixtures (NFR discovery + FP-audit)

*Companion to `QPB_v1.6.0_Design.md` and `QPB_v1.6.0_Implementation_Plan.md`.*
*Status: drafted 2026-05-24. Catalogs the known-input / known-answer cases that prove the v1.6.0 feature works. Fixture 1 is the primary acceptance oracle; Fixture 2 is a candidate synthetic negative fixture.*

---

## Why fixtures matter for v1.6.0

v1.6.0 adds two precision mechanisms: (A) the **NFR grounding rule** — a finding is only a `BUG` if it traces to a *derived* requirement and violates its acceptance criterion in the audited tree; and (B) the **fresh-context FP-audit** — re-checks each confirmed finding against the derived REQs (reachability / compensation / applicability / source-of-truth / design-intent / severity-justification / requirements-traceability).

The feature is only as good as its ability to resist **contamination**: a finding sourced from a *document* rather than a *located code defect*. The fixtures below are curated inputs whose correct answer is known, so a v1.6.0 build can be tested against them. Each fixture targets a distinct contamination genre.

---

## Fixture 1 (primary acceptance oracle) — the OpenFGA run

**Genre tested:** security-advisory contamination — advisory/CVE text restated as confirmed code bugs.

**Input:** the 2026-05-23 OpenFGA Mode-A dogfood, preserved read-only at `~/Documents/QPB/repos/openfpa-1.5.7/quality/` (BUGS.md, writeups, results logs) plus the cited `internal/`/`pkg/` source and `reference_docs/openfga-security-advisories.md`.

**Known-correct answer:**

- **BUG-003 / BUG-006 / BUG-009 must NOT survive as confirmed HIGH bugs** — demoted or reclassified by the audit (reachability guard for 003; no reachable path + CVE version-range n/a for 006; advisory-only restatement → KNOWN-ISSUE for 009), and/or never confirmed because they violate no derived NFR.
- **BUG-001 / BUG-002 / BUG-004 must still surface** — the genuine, code-located findings. Precision up without recall collapse.

This is the headline success criterion in the design doc (Success criterion #3). v1.6.0 is not done until a re-run comes out this way.

---

## Fixture 2 (candidate synthetic negative fixture) — process-prose-as-requirements

**Genre tested:** **process-narrative contamination** — prose that's *shaped* like requirements (MUST statements, acceptance-criterion-like sentences) but is actually process/orchestration guidance for humans, not a behavioral requirement of the QPB runtime code. This is a different genre from Fixture 1's security advisories, so it hardens the grounding rule against a class the OpenFGA fixture doesn't cover.

**Candidate input:** `~/Documents/AI-Driven Development/Quality Playbook/QPB_v1.6.x_Cowork_Bootstrap.md` (the orchestrator bootstrap doc), fed as gathered documentation for a QPB self-audit of the QPB repo.

**Known-correct answer:** **zero confirmed bugs traceable *only* to this doc.** The grounding rule must refuse to promote process prose into code requirements; the FP-audit's source-of-truth + applicability checks must catch anything that slips through.

**A hole in the feature looks like:** the build emits a bug whose only basis is a sentence in this doc.

### Full rationale (why this is a good adversarial input)

*The explanation below is preserved verbatim from the 2026-05-24 design conversation, so the next chat has the reasoning, not just the assertion.*

**What a "fixture" is here.** A fixture is a known input with a known-correct answer you keep around to test a feature. The OpenFGA run is already v1.6.0's primary fixture: feed that repo + its advisories, the correct answer is "BUG-003/006/009 must not survive as HIGH; 001/002/004 must." You re-run it to prove the feature works. This option makes the bootstrap doc a second, synthetic fixture that tests a different flavor of the same failure.

**Why this doc is a good adversarial input.** The OpenFGA fixture tests one contamination genre: security advisories getting restated as bugs. This doc tests a different genre: process prose that's shaped like requirements but isn't. Look at what's in it — sentences like "the audit sub-agent MUST get only the finding + cited source, NOT the writeup reasoning," or "you MUST verify before claiming shipped." Those are written in requirement-ish language (MUST, acceptance-criterion-shaped), but they're process rules for humans/orchestrators, not behavioral requirements of the QPB runtime code.

**The concrete failure it would catch.** Imagine a future QPB run ingests this doc as gathered documentation, then audits the QPB codebase. A naive agent could:

1. Derive a pseudo-requirement from the prose: *"REQ: the FP-audit sub-agent must not receive the writeup reasoning."*
2. Go hunting in `bin/` for whether that isolation holds.
3. Report a "bug" when it can't confirm it — even though the FP-audit doesn't exist in the audited tree yet (it's a v1.6.0 design aspiration, not shipped code).

That's a false positive sourced entirely from a doc — the exact BUG-009 class, just dressed in process language instead of CVE language.

**What pass/fail looks like.**

- *Correct v1.6.0 behavior:* zero confirmed bugs traceable only to this doc. The grounding rule refuses to promote process prose into code requirements; the FP-audit's source-of-truth + applicability checks catch anything that slips through ("this 'requirement' is a design-doc statement, not a located code defect / not present in the audited tree").
- *Hole in the feature:* the build emits a bug whose only basis is a sentence in this doc.

So you're deliberately handing v1.6.0 a curated, known-bad input and asserting the answer is "nothing." It hardens the grounding rule against a contamination genre the OpenFGA fixture doesn't cover.

**The honest caveat.** It's self-referential — a doc about QPB, fed to QPB, to audit QPB. A bit hall-of-mirrors. That doesn't hurt its value as a mechanism test (does the agent resist promoting non-requirement prose?), but it's why this doc should be used strictly as a test fixture, never as production gathered documentation for a real adopter audit.

### Open questions for this fixture (resolve when building the v1.6.0 test)

- Whether to use the bootstrap doc as-is, or to author a smaller purpose-built negative fixture distilled from it (fewer moving parts, less self-reference).
- How to assert "zero bugs traceable *only* to this doc" mechanically — e.g. tag findings with their source provenance and assert none has this doc as sole source.
- Whether to also seed one *true* code-requirement into the fixture (a sentence that genuinely maps to a real code contract) to confirm the audit doesn't over-correct into suppressing legitimate doc-grounded findings.
