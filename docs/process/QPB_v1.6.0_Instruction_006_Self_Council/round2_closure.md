# Instruction 006 self-Council — closure rounds

Closure of the round-1 findings. Panelists A and C returned SHIP in round 1 and their P2s
were closed by the first fix round; Panelist B (selection-pass / routing) drove two fix
rounds before SHIP.

## Fix round 1 — `2fb7857`

- **B P1 (leftover ordering wording):** `phase2_generation_guide.md:167` and `:173` still
  stated the pre-006 "user-facing → infrastructure" rule as unconditional, contradicting the
  new principle-agnostic item 4. Both rewritten to "most-relevant-to-the-primary-reader
  first" (each framed as reducing to the old rule for a functional grouping).
- **A P2 (bare-present regex):** `_RENDER_PRINCIPLE_RE` widened to `organiz(?:e|es|ed|ing)` +
  `group(?:ed|s|ing)?`; false-positive probed; `test_principle_detector_accepts_bare_present_tense` added.
- **C P2:** the same :167/:173 leftover — closed with B's P1.

## Closure round 1 (B) — FIX-REQUIRED → fix round 2 `edce797`

B verified the two cited spots CLOSED but its independent sweep found a **third survivor**:
`phase_prompts/phase2.md:50` — the render-contract summary in the Phase 2 routing prompt the
executing agent reads first — stated "functional sections ordered user-facing→infrastructure
with ≥2 REQs each" as unconditional fact. The worker's earlier sweep missed it because it
grepped the *spaced* arrow while this spot used the *unspaced* arrow. Fixed: reframed to
"requirement sections organized by the principle you chose for this system (named with a
rationale, each carrying a unifying overview, ≥2 REQs, ordered most-relevant-to-the-primary-
reader first)", glossary added to the part list, "eight-part" count dropped; phase2 prompt
hash recomputed (12810 → 13004).

## Closure round 2 (B) — SHIP

B re-reviewed `edce797` with an exhaustive-sweep mandate: the phase2.md leftover is closed,
and a full skill-doc sweep (both arrow spellings + equivalent prose) tabulated every hit —
the only remaining "user-facing → infrastructure" mentions are the two **deliberate**
"generalization of the old rule" references (`phase2_generation_guide.md:167`,
`requirements_pipeline.md:357`); the "functional sections" hit is NFR ("non-functional
sections"), and the "eight-part" hits are the classifier's structural-heading count, all
unrelated. No survivor remains. Hash guard passes with no collateral drift; the six-step
selection pass and generation-guide item 4 are intact.

## Disposition

**Unanimous SHIP** (A SHIP; C SHIP; B SHIP after two fix rounds). Zero open findings.
Cleared to file. Worker never pushes/merges — the operator lands the branch.
