# Instruction 008 — v1.6.0: make the F-1 coverage-and-gaps statement salient in the generation guide

Small, single-purpose. The F-1 "coverage and known gaps" statement is omitted by many runs — a 2026-07-21 test saw it missing on chi, express, and an earlier bus-tracker run (WARN each), though a virtio run included it. It is advisory (WARN, never FAIL) and stays that way — this is a **prominence** fix, not an enforcement change. It matters because Feature D's Stage 1 plays the gaps statement back to the operator ("here's what I believe I did not cover — intentional?"); when it is missing, the interview loses its cheapest, highest-yield completeness probe.

## The pattern this follows
Two prior fixes had the same shape: the marker format (004) and the section/REQ heading hierarchy (007) were each *described in prose* in `phase2_generation_guide.md` but not *shown saliently*, and capable models omitted them until each got a labelled subsection with a worked example. F-1 is the third instance of the same root cause — the coverage-and-gaps requirement lives in a prose sentence under the Overview part, not as a labelled item with an example of what the statement looks like.

## Read first
- `references/phase2_generation_guide.md` § "Canonical document architecture" (the Overview part, item 2, which mentions the coverage-and-gaps statement) and § F-1 if present.
- `docs/design/QPB_v1.6.0_Design.md` §8 F-1 (advisory; WARN only) and the §5.2 Overview part.
- `plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py` — the F-1 WARN check (do NOT change its severity; it stays advisory).
- `ai_context/DEVELOPMENT_PROCESS.md`.

## Work items

### 1. Add a labelled, worked-example subsection for the coverage-and-gaps statement
In `references/phase2_generation_guide.md`, give the coverage-and-gaps statement its own labelled subsection (like the marker-format and heading-hierarchy subsections), with a **short worked example** showing the literal shape of a good gaps statement in the Overview — an honest "what was covered / what was deliberately not covered (areas explored but not turned into REQs, files skimmed, surfaces out of reach)" paragraph. Make explicit that it is **mandatory content of the Overview on every run regardless of target size** (Design §5.2 item 2), and that "100% covered" or an omitted statement is exactly the failure it exists to prevent (an honest gaps statement is more valuable than a false clean bill).

### 2. Do NOT change the check's severity
The gate WARNs on a missing/empty gaps statement and must keep doing so — never a FAIL (Design §8; the same advisory posture as the glossary). This instruction changes only the guide's prominence, not enforcement. Confirm the check is unchanged.

### 3. Consistency note
The gaps statement feeds Feature D Stage 1 (`references/requirements_interview.md`). Verify the interview's Stage-1 gap-playback still references the Overview gaps statement as its source, so the produced-and-consumed sides agree.

## Scope
Prominence of the F-1 instruction only. Do NOT change severity, do NOT touch Track 2, do NOT hand-edit fixtures.

## Also record (out of scope — for the orchestrator, do not fix here)
Two frictions recurred across every 2026-07-21 test run; note them in your output so the orchestrator can decide:
- **Phase-0 double-marker block** — a target carrying both `.claude` and `.github` markers returns `status=blocked` and forces an `--ai-tool` disambiguation round-trip. Expected behavior, but recurring friction.
- **Phase-2 artifact validator requires `bugs_manifest.json` (and citation/formal-docs manifests) to exist at Phase 2**, which the prose says are Phase 3–5 artifacts. Agents work around it by writing empty wrappers; the prose/validator mismatch is real.
- **chi RUN_CONTRACT tool-split (C-1):** an incomplete (API-cut-off) chi run showed `RUN_CONTRACT.md: missing 1 tool-contract REQ(s): REQ-031`. Unconfirmed — seen on a partial run; a clean chi run is needed to tell whether it is a real tool-contract-split defect or an artifact of the interrupted re-render. Flag, do not fix.

## Branch / commit / Council / output
- Branch **`1.6.0`**; pre-flight, `pre-flight-aborted` if wrong. Local commits only; never push/merge.
- A focused single-panel self-Council suffices (prominence change + confirming the check severity is unchanged). Artifacts under `RUNNER_ROOT/reviews/008_self_council/` + tracked copy under `docs/process/QPB_v1.6.0_Instruction_008_Self_Council/`.
- Verify the full suite; report counts + Python version.
- Output `outputs/008-f1-gaps-statement-prominence.md`: the new subsection, confirmation the check severity is unchanged (still WARN), the Stage-1 consistency check, and the recorded frictions above.
