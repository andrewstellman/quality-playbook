# Output for 008-f1-gaps-statement-prominence.md
**Status:** completed

## Files created / changed
| Path | Note |
|------|------|
| `references/phase2_generation_guide.md` | Item 1: the "Coverage-and-gaps statement (F-1)" subsection gains a worked example (the literal shape inside the Overview), the explicit "mandatory Overview content on every run regardless of target size", and the "fully-covered/omitted is the failure it prevents" framing. Prominence only. |

No code changed — the F-1 check severity is untouched (work item 2).

## Commits made
- `5fb24ec` — v1.6.0 [instr 008]: make the F-1 coverage-and-gaps statement salient in the generation guide.
- `c46ae72` — v1.6.0 [instr 008]: tracked self-Council synthesis.
- `<this commit>` — runner: output for instruction 008.

## Acceptance criteria — pass/fail per item
| Criterion | Result |
|-----------|--------|
| Labelled subsection with a worked example | **PASS** — the F-1 subsection now shows a worked coverage-and-gaps paragraph inside a `## Overview` example, matching the marker-format / heading-hierarchy pattern. |
| Explicit: mandatory on every run regardless of size | **PASS** — stated at the top of the subsection (Design §5.2 item 2). |
| "Fully covered"/omitted = the failure it prevents | **PASS** — "a false clean bill is worse than an honest 'I did not get to X'". |
| Check severity UNCHANGED (still WARN) | **PASS** — `quality_gate.py` F-1 check uses `warn(...)` for both the missing and empty-statement branches; the commit touches only `references/phase2_generation_guide.md` (no code). |
| Stage-1 consistency (produced/consumed agree) | **PASS** — `requirements_interview.md` Stage 1 plays back the Overview coverage-and-gaps statement verbatim as its source; the guide produces it in the Overview. Agree. |
| Full suite + counts + Python version | **PASS** — `python3 -m unittest discover bin/tests` → **2609 tests, 0 failures, 13–14 skipped**, Python 3.14.6. |

## Council (if required)
**Verdict: SHIP** (single focused panel, per the instruction; zero fix rounds). Worktree-isolated.
Charter: the prominence change + confirming the check severity is unchanged + Stage-1 consistency.

The panelist confirmed: (1) the F-1 subsection now carries the worked example, the mandatory-on-
every-run statement, and the honest-gaps-beat-false-clean-bill framing, labelled like its sibling
subsections; (2) **severity UNCHANGED** — `git show 5fb24ec --stat` shows one file changed
(`references/phase2_generation_guide.md`, no code); the gate's F-1 block calls `warn(...)` for
both branches, no `fail(...)`; still advisory (Design §8); (3) the interview Stage-1 gap-playback
reads the Overview statement verbatim — produced/consumed sides agree; (4) the worked example is
fenced prose in a reference doc, parsed by no check, and trips no doc-drift / reference-resolves /
token-ceiling guard. Nothing under-done.

Artifacts: `RUNNER_ROOT/reviews/008_self_council/synthesis.md` (gitignored) and the tracked mirror
`docs/process/QPB_v1.6.0_Instruction_008_Self_Council/synthesis.md`.

## Notable observations

### The new subsection
The F-1 subsection already existed but was prose-only; it now carries a worked example showing a
good coverage-and-gaps paragraph in context (`## Overview` → "Coverage and known gaps: … covered
X … did NOT turn Y into requirements … Z not reached … N files treated as dependencies"), the
mandatory-on-every-run statement, and the "honest gaps beat a false clean bill" framing. This is
the third application of the same prominence pattern that fixed the marker format (004) and the
section/REQ heading hierarchy (007): a labelled subsection + a worked example, where prose alone
had let capable models omit the requirement.

### Severity is unchanged (the named constraint)
The gate WARNs on a missing or empty coverage-and-gaps statement and never FAILs (Design §8; same
advisory posture as the glossary). This commit changes only the reference doc — no gate code was
touched. F-1 remains advisory; this is a prominence change, not an enforcement change.

### Stage-1 consistency
The interview's Stage-1 gap-playback (`requirements_interview.md`) reads the Overview
coverage-and-gaps statement verbatim ("Then play back the coverage-and-gaps statement verbatim …
'here's what I believe I did NOT cover — intentional?'"). The generation guide produces exactly
that statement in the Overview. Produced and consumed sides agree; no drift.

### Recorded for the orchestrator (out of scope, not fixed here)
Per the instruction, three recurring frictions from the 2026-07-21 runs:
1. **Phase-0 double-marker block** — a target carrying both `.claude` and `.github` markers
   returns `status=blocked` and forces an `--ai-tool` disambiguation round-trip. Expected
   behaviour, but recurring friction.
2. **Phase-2 artifact validator requires `bugs_manifest.json`** (and citation/formal-docs
   manifests) to exist at Phase 2, though the prose describes those as Phase 3–5 artifacts. Agents
   work around it by writing empty wrappers; the prose/validator mismatch is real.
3. **chi RUN_CONTRACT tool-split (C-1)** — a partial (API-cut-off) chi run showed
   `RUN_CONTRACT.md: missing 1 tool-contract REQ(s): REQ-031`. Unconfirmed — seen on an
   interrupted run; a clean chi run is needed to tell whether it is a real tool-contract-split
   defect or an artifact of the interrupted re-render. Flagged, not fixed.

### Anything found underspecified or wrong
Nothing in §8 F-1 or §5.2 was wrong for this instruction. One small note: the F-1 subsection and
the glossary subsection now both carry the "advisory, WARN like the glossary" framing and a worked
example — they are the two advisory Overview-adjacent parts, and the guide treats them
consistently. No change needed; recorded for completeness.

## Next action expected from orchestrator
Land the instruction-008 commit on `1.6.0` (worker never pushes/merges). Consider the three
recorded frictions (Phase-0 double-marker, Phase-2 validator/prose mismatch, the unconfirmed chi
RUN_CONTRACT REQ-031 — needs a clean chi run). Track 2 remains out of scope.
