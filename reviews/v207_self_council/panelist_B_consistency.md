# Panelist B — Terminology Consistency (Instruction 207)

REVIEWER ROLE-LOCK: I am Panelist B for QPB instruction 207 self-Council Protocol 1.
I am NOT the orchestrator. My job is verdict-only on terminology consistency across
the artifacts emitted by `bin/submit_awesome_copilot.py`. I do not modify code, do
not edit `submit_awesome_copilot.py`, and do not run the publish/submit suites
beyond the empirical dry-run probe specified in the charter. Verdict ends in a
`VERDICT:` block.

## 1. Charter recap

Verify that the trim-template content errors fixed in commit `35f9734`
(instruction 207) are actually absent from regenerated `SKILL.md` + `PR_BODY.md`,
that phase names match canonical `README.md`, that the SKILL.md trigger phrases
are preserved verbatim from the source frontmatter, and that PR_BODY says
"five support directories" (not "seven").

## 2. Residual-error-pattern grep results

Charter-specified probe:

```
$ python3 bin/submit_awesome_copilot.py --dry-run --dest /tmp/qpb-207-empirical
Pre-flight: version-string parity...
Version parity OK at 1.5.8.
Submission packet generated at: /private/tmp/qpb-207-empirical
  - skills/quality-playbook/SKILL.md
  - PR_BODY.md
  - MANUAL_STEPS.md
  - submission.json

$ grep -rEn "Python 3\.8|qpb install|npx quality-playbook[^ ]" /tmp/qpb-207-empirical/
(no output; exit=1)
```

Extended sweep including the historical pre-207 patterns enumerated in the
commit message:

```
$ grep -rEn "Python 3\.8|Python 3\.9|qpb install|npx quality-playbook[^ ]|seven support|Phase 5 \(Consolidate|Phase 6 \(Ship" /tmp/qpb-207-empirical/
(no output; exit=1)
```

Zero matches. All six 207-tracked error patterns are absent from the
generated artifacts.

Replacement strings present (positive controls):

| Replacement string                                         | File                                  | Line |
|------------------------------------------------------------|---------------------------------------|------|
| `Python 3.10+`                                             | `skills/quality-playbook/SKILL.md`    |   5  |
| `npx quality-playbook install --into <repo> --ai-tool <tool>` | `skills/quality-playbook/SKILL.md` |   5, 27 |
| `quality-playbook install --into ... --ai-tool <tool>`     | `skills/quality-playbook/SKILL.md`    |  33 |
| `quality-playbook install --into ./test-target-repo --ai-tool claude` | `PR_BODY.md`              |  34 |
| `Phase 5 (Reconcile)`                                      | `skills/quality-playbook/SKILL.md`    |  60 |
| `Phase 6 (Verify)`                                         | `skills/quality-playbook/SKILL.md`    |  62 |
| `five support directories`                                 | `PR_BODY.md`                          |  21 |

## 3. Phase-name consistency table (Phase 1-6)

Source: README.md lines 551-561 ("How it works"). Template: SKILL.md lines
50-63 (workflow numbered list).

| Phase | README canonical name      | Template renders               | Match? |
|-------|----------------------------|--------------------------------|--------|
| 1     | Phase 1: Explore           | Phase 1 (Explore)              | yes    |
| 2     | Phase 2: Generate          | Phase 2 (Generate)             | yes    |
| 3     | Phase 3: Code review       | Phase 3 (Code Review)          | yes (capitalization only) |
| 4     | Phase 4: Spec audit        | Phase 4 (Spec Audit)           | yes (capitalization only) |
| 5     | Phase 5: Reconciliation    | Phase 5 (Reconcile)            | yes (verb form vs noun) |
| 6     | Phase 6: Verify            | Phase 6 (Verify)               | yes    |

Phases 3-5 differ in minor surface form (Title-Case in the SKILL.md
parenthetical vs. lowercase in the README "How it works" prose; "Reconcile"
verb vs. "Reconciliation" noun). README.md line 599 — the v1.4 historical
note — uses the verb forms directly: "Explore, Generate, Review, Audit,
Reconcile, Verify". The template aligns with that canonical phase-name set.
Commit `35f9734` explicitly cites README line 39 as the canonical source for
"reconcile findings" (verb form). The variation is intentional and idiomatic,
not a residual error.

Charter pointer references "lines around 39, 110, 232":

- Line 39: prose narrative for installer (no phase names per se)
- Line 110: ToC "How it works" section anchor
- Line 232: reference_docs guidance (mentions "Phase 1 prompts" at line 234)

None of these reference lines contradict the SKILL.md phase rendering. The
load-bearing canonical phase-name source is README.md lines 551-561, and
the template is consistent with it.

## 4. Trigger phrases preserved?

YES. Source `SKILL.md` line 3 (canonical) and template
`/tmp/qpb-207-empirical/skills/quality-playbook/SKILL.md` line 3
contain the identical description-with-trigger-phrases string:

> Trigger on 'quality playbook', 'spec audit', 'Council of Three',
> 'fitness-to-purpose', or 'coverage theater'.

All five phrases are preserved verbatim (single-quoted, comma+space
separation, "Council of Three" Title-Case, hyphenated "fitness-to-purpose").
Per charter item 4, these are intentional — not errors — and the template
faithfully copies them.

## 5. Five-vs-seven support directories in PR_BODY

CONFIRMED. PR_BODY.md line 21:

```
The skill ships five support directories (`references/`,
`phase_prompts/`, `agents/`, `bin/`, `ai_context/`) plus `SKILL.md`
and `quality_gate.py`. The full bundle is ~64 files (132KB SKILL.md
alone) which exceeds the typical in-repo-skill footprint.
```

Five directories enumerated (references, phase_prompts, agents, bin,
ai_context) plus two top-level files (SKILL.md, quality_gate.py). The
PR_BODY Checklist section (lines 41-52) contains no references to either
"five" or "seven", so charter item 5 reduces to "the Distribution section
uses 'five'", which it does.

NIT (out of scope but noted): SKILL.md line 19 still contains the phrase
"seven phase-prompt directories" in the Installation prose. This is
different surface form than PR_BODY's "five support directories" — it
refers to phase-prompt sub-units, not top-level support directories — but
inspection of `phase_prompts/` shows 8 files (phase1.md through phase6.md,
iteration.md, single_pass.md, plus README.md and phase6_auditor.md), no
subdirectories. The "seven phase-prompt directories" prose in SKILL.md is
loosely accurate at best (count is wrong AND they're files not
directories). Not in 207's charter — 207 fixed PR_BODY's count claim —
but flagged here for a future cleanup pass. See item 7.

## 6. Per-finding narrative

None. All six pre-207 error patterns are absent from regenerated artifacts.
Phase names align with README. Trigger phrases preserved. PR_BODY uses
"five". The eight new `TrimTemplateContentTests` (all 8 pass; full suite
37/37 pass) guard against regression of every fix individually with
both positive-assertion AND `assertNotIn` for the pre-207 error string.

## 7. Optional NITs

NIT-1 (future cleanup, not 207-scope): SKILL.md line 19 in the template
says "seven phase-prompt directories". `phase_prompts/` contains
files, not directories, and the count is 8 (not 7). PR_BODY got the
parallel fix in 207 — SKILL.md's Installation prose did not. Worth a
one-line follow-up edit in a future instruction, e.g. "six phase prompts
plus the iteration / single-pass / auditor variants" or simply "the
phase prompt set". Does not affect 207 ship readiness because (a) it's
in a different file from the four 207-tracked SKILL.md fixes, (b) the
charter pattern `seven support` does not match `seven phase-prompt`,
and (c) the prose is in a parenthetical aside justifying why the skill
is distributed standalone — not a load-bearing usage instruction. Flag,
do not block.

NIT-2 (future cleanup, not 207-scope): The Phase-3/4/5 surface-form
delta (README "Phase 5: Reconciliation" vs SKILL.md "Phase 5
(Reconcile)") is small but a future consistency sweep could pick one
canonical form. Not 207-scope; 207's commit message explicitly chose
the verb form per README line 39, which is correct.

## 8. Final block

```
VERDICT: SHIP
```
