# Instruction 008 self-Council — synthesis

**Scope:** v1.6.0 — make the F-1 coverage-and-gaps statement salient in the generation guide.
A prominence fix (the third instance of the marker-format/heading-hierarchy pattern), **not**
an enforcement change.
**Panel:** a single focused panelist per the instruction, worktree-isolated. Charter: the
prominence change + confirming the check severity is unchanged + the Stage-1 consistency.

## Verdict: SHIP (single panel, zero fix rounds)

- **Prominence + worked example (item 1):** the "Coverage-and-gaps statement (F-1)" subsection
  now opens with "Mandatory content of the Overview on every run, regardless of target size"
  (Design §5.2 item 2), carries a fenced worked example showing a literal `## Overview` with a
  "Coverage and known gaps:" paragraph (covered surfaces / deliberately-not-turned-into-REQs /
  files skimmed / surfaces out of reach, with rationale), and states plainly that "fully
  covered"/omitted is the failure it prevents (honest gaps beat a false clean bill). Labelled
  like its sibling subsections.
- **Severity UNCHANGED (item 2, the critical constraint):** `git show 5fb24ec --stat` confirms
  exactly one file changed — `references/phase2_generation_guide.md` — no code. The gate's F-1
  block (`quality_gate.py:7891-7922`) calls `warn(...)` for both the empty-statement and
  missing-statement branches; no `fail(...)` exists in the block. Still advisory-only (Design §8).
- **Produced/consumed consistency (item 3):** `requirements_interview.md` Stage 1 plays back the
  Overview coverage-and-gaps statement verbatim as its gap-question source; the guide produces
  exactly that. No drift.
- **No gate-trip:** the worked example is fenced prose in a reference doc, parsed by no check;
  doc-drift / reference-resolves / token-ceiling guards all green.

Full suite **2609 tests, 0 failures (14 skipped)**, Python 3.14.6. Nothing under-done. Cleared
to file.

## Recorded for the orchestrator (out of scope, per the instruction)

1. **Phase-0 double-marker block** — a target with both `.claude` and `.github` markers returns
   `status=blocked` and forces an `--ai-tool` disambiguation round-trip. Expected, but recurring.
2. **Phase-2 validator requires `bugs_manifest.json`** (and citation/formal-docs manifests) at
   Phase 2, though the prose calls those Phase 3–5 artifacts. Agents write empty wrappers; the
   prose/validator mismatch is real.
3. **chi RUN_CONTRACT tool-split (C-1)** — a partial (API-cut-off) chi run showed
   `RUN_CONTRACT.md: missing 1 tool-contract REQ(s): REQ-031`. Unconfirmed; needs a clean chi run
   to tell whether it is a real defect or an interrupted-re-render artifact.
