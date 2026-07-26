# v1.6.0 instruction 001 — worker self-Council (tracked evidence copy)

*Feature C (spec organization & coherence), Track 1 Phase 2 acceptance.
Immutable process artifact per `ai_context/DEVELOPMENT_PROCESS.md` §
"Versioned artifacts".*

## Why this copy exists

The runner's review path — `runner/quality-playbook/reviews/001_self_council/` —
matches `.gitignore:82` (`reviews/`, a bare pattern matching at **any** depth),
so every artifact written there is untracked and would be lost to a clean
checkout. Instruction 001 called this out explicitly:

> **Evidence-durability requirement:** v1.5.10 lost per-item review evidence
> because the review path was gitignored. … If the path is ignored, say so
> explicitly in your output and also place the artifacts somewhere tracked.
> Do not report a Council verdict whose evidence cannot be found later.

The runner copies remain in place; this is the durable one. Both were verified
identical at the time of the commit that added this directory.

## Verdict

**SHIP**, at round 7, after six FIX-REQUIRED rounds. Two follow-ups round 7
recorded as non-blocking were closed afterwards in `aa4b4f6` rather than
handed over, because both were instances of the defect shape that had opened
each of the preceding four rounds.

## Contents

| File | What it is |
|---|---|
| `synthesis.md` | **Start here.** Panel, findings, dispositions, and what the process caught about itself |
| `evidence_c1_c7_before_after.md` | Mechanically derived per-defect before/after table for C-1…C-7 |
| `panelist_A_render_contract_correctness.md` | Round 1, charter A — render-contract correctness incl. mutation coverage |
| `panelist_B_fixture_fidelity.md` | Round 1, charter B — regeneration-fixture fidelity against C-1…C-7 |
| `panelist_C_regression_safety.md` | Round 1, charter C — regression safety on manifest semantics, blast radius |
| `round2_verification.md` … `round7_closure.md` | Closure audits, each verifying the previous round's fixes by execution |

## Commits under review

| SHA | Subject |
|---|---|
| `71b1a81` | the REQUIREMENTS.md render contract, specified |
| `d8d4229` | enforce the render contract in quality_gate.py |
| `edc5cec` | the regeneration fixture — Feature C acceptance oracle |
| `f9984ae` | close the self-Council findings (round 1) |
| `a95dcb5` | close the self-Council findings (round 2) |
| `3ef3a7e` | close the self-Council findings (round 3) |
| `b863deb` | close the self-Council findings (round 4) |
| `4255002` | extend the suppressed-region rule to HTML blocks |
| `94c7e3d` | close B-6/B-7 and end the loop with a differential test |
| `7296569` | close B-8 (HTML type 7) and generate the differential cases |
| `aa4b4f6` | model all seven HTML block types; restore the type-6 bite |

## The one thing worth reading if you read nothing else

Rounds 3 through 7 each found a bypass in the same component, and every fix
was *correct about exactly the shape it had been shown*. Round 5 named the
exit condition:

> The exit condition isn't "cover the grammar", it's "check the model
> against an authority." Every bypass in rounds 3-5 was a gap between the
> gate's model of Markdown and Markdown itself.

Round 6 then found the same pattern one level up — the differential test's
case list was hand-written from the same model it audits, so it inherited
that model's blind spots. Round 7 found it a level up again: generating the
cases in a single context let one construct backstop another, so 62 cases
had no discriminating power.

**Generalizable:** when a check reimplements a specification that has a
reference implementation, differential-test against the reference, generate
the corpus from the model's own constants, and vary the context each case
appears in. An enumeration of shapes is only ever as complete as the last
review round.
