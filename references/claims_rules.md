# Claims Rules

Apply these rules to every claim QPB writes for a reader: `quality/BUGS.md` entries, `quality/writeups/BUG-NNN.md`, the "What just happened" block, README and benchmark text. A claim is any sentence that states a fact, a result, or a capability.

## Reader model

Maintainers and adopters read a QPB claim the way they read a bug report. They ask three questions: what happened, how often, and can I reproduce it?

## Two standards

- **Tangible.** The claim names a number, a `file:line`, a command, a test, or a deliverable.
- **Objective.** Ten engineers would agree on what the claim means. It passes or fails like a test.

## Rules

- **R1. Every claim has a measurable anchor.** "The parser drops the last byte of a 4096-byte chunk (`test_chunk_boundary` fails)" — not "the parser mishandles chunk boundaries."
- **R2. Name the thing.** Name the file, function, test, command, or RFC section. Do not gesture at "the config handling" or "the spec."
- **R3. Describe the behaviour or the action, not a feeling.** "`retry()` sleeps 0 ms on the first attempt" — not "retry logic is fragile."
- **R6. One idea per claim.** Split a sentence that carries two findings into two sentences.
- **R7. Never promise what the material cannot deliver.** If a patch was not run, do not say it fixes the bug; say it is proposed and untested.
- **R8. Numbers are real or framed as targets.** A real number names its source (a command, a log, a test run). A target says it is a target. A specific behavioural claim ("X does not do Y") must have been run before it is written.

## What not to use in bug reports, PRs, and issues

Do not write scenes or before/after storytelling ("Imagine a user who…", "Before this fix, life was hard…"). Maintainers read them as padding. Before/after is fine in README and benchmark claims when both numbers were measured.

## Flags that trigger a rewrite

- "significantly", "robust", "comprehensive", "critical", "seamless" with no anchor next to them.
- "ensure" when nothing checks it.
- "all" or "every" when the set is not enumerated.
- Any percentage without a source.

## Pre-output checklist

Run this silently before returning operator-facing text:

1. R1: each claim has an anchor.
2. R2: each claim names its thing.
3. R3: each claim describes behaviour or action.
4. R6: one idea per claim.
5. R7: nothing promised beyond what was run or read.
6. R8: each number has a source or is labelled a target.
7. No flag word is left unanchored.

Precedence: the caller's tone and voice rules win on tone. These rules win on claims.

Credit: adapted from a QA copywriting standard supplied by Andrew Stellman (2026-10-01).
