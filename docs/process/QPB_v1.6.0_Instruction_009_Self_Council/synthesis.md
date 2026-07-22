# Self-Council synthesis — instruction 009 (organizing-principle check false positives)

**Verdict: SHIP** (unanimous, zero fix-required rounds; one non-blocking follow-up applied post-panel per Panelist A).

Reviewed code: branch `1.6.0`, commits `a88dc11` (check fix + tests) and `2b9229c`
(guide clarity). Post-panel fix-up `4a3cace` adds `\btherefore\b` per Panelist A's
recommendation (see "Applied after the panel" below). Three panelists, each in its
own isolated git worktree, each writing a full verdict to
`reviews/009_self_council/panelist_{A,B,C}_*.md`.

## Charters
- **A — rationale-detection robustness & correctness** (work item 1).
- **B — search-zone widening correctness & boundedness** (work item 2).
- **C — guide clarity, no-weakening, defensive sweep** (work item 3 + scope discipline).

## Where the panelists AGREE (highest confidence)
1. **The fix is correct and load-bearing.** All three independently reproduced the
   pre-fix false-FAILs by reverting/narrowing the source in their worktree (A: narrow
   connector + no structural arm → chi & virtio re-FAIL; B: `zone_end`→`first_section_offset`
   → express re-FAILs "no organizing principle stated"; C: reverting source makes
   `test_009_principle_buried_in_mid_section_is_not_accepted` genuinely assert-fail).
2. **All three real docs pass.** `repos/{chi,express,virtio}-t3/quality` go from FAIL=1
   to FAIL=0/WARN=0 on the organizing principle, verified by all three panelists directly.
3. **The required mutation bites hold.** Three real phrasings pass (chi bare "so", virtio
   "Rationale:" label, express single-sentence "because"); name-only "Organized by feature."
   FAILs; a connector-free multi-sentence rationale passes via the structural arm;
   name-plus-lone-ordering-note FAILs.
4. **The check was NOT weakened** (C, the load-bearing no-weakening charter): a document
   with no principle still FAILs; a named principle with no rationale still FAILs. Both
   negative cases constructed on the real harness and shown FAILing.
5. **The zone is properly bounded** (B, 15 adversarial probes): a principle buried below
   the first REQ of a mid-document section is not accepted; `zone_end` edge cases
   (`.index()`, `else _fs_end`, empty intro, single section) are crash-safe.
6. **The guide edit resolves the ambiguity** (C): the "top of the section list" phrasing
   that trapped express is now unambiguous, consistent with the check in the safe
   prescribe-narrow / accept-broad direction, worked example retained.
7. **Full render-contract suite green** (88 tests in the file; 2614 in the repo, 0 failures,
   14 skipped, Python 3.14.6), new `test_009_*` tests are non-tautological.

## Where they DIVERGE / judgment calls (all non-blocking)
- **A — over-permissiveness (structural arm):** a naming paragraph with any two substantive
  sentences passes even if those sentences don't strictly *justify* the choice. Bounded by
  the instruction's explicit "presence, not quality" scope (rationale quality is the Feature D
  interview + the Well-organized rubric, matrix row 4c). Accepted as designed.
- **A — under-permissiveness ("therefore"/em-dash single-sentence rationales):** fail-closed,
  zero real-doc impact. A recommended `\btherefore\b`. **Applied** (see below); the bare-em-dash
  single-sentence case remains fail-closed and is out of scope.
- **B — plural `## Organizing principles` placed *after* the first section is not honored**
  (the `\b` blocks it). Off-spec heading form (the guide documents the singular); a false
  FAIL on an off-spec shape, never a false PASS; top-placed principles are caught regardless.
  Not a defect.
- **C — defensive sweep:** the F-1 coverage-and-gaps check uses the same brittle fixed-keyword
  cue-list shape, and the principle *naming* regex (`_RENDER_PRINCIPLE_RE`) is still a fixed
  keyword list. Both are WARN-only or pre-existing (predate 009), not regressions this change
  introduces. **Recorded for the orchestrator; out of scope for 009.**

## Applied after the panel
Per Panelist A, `\btherefore\b` was added to `_RENDER_RATIONALE_CONNECTOR_RE` (commit
`4a3cace`), closing the flagged under-permissiveness gap. "therefore" is the same connector
family as the "thus, hence, in order to" set instruction 009 work item 1 enumerated, so this
completes the connector intent rather than expanding scope. The change is additive-only
(strictly more permissive on an under-permissive case): name-only and lone-ordering-note
still FAIL, the three real docs stay FAIL=0, the full suite stays green, and a new case in
`test_009_rationale_detection_is_structural_not_keyword` pins it.

## Logistics note
Each panelist's isolation worktree was created from a stale base predating the fix; all three
detected this via the role-lock discipline, confirmed `a88dc11`/`2b9229c` on branch `1.6.0`,
and reviewed the actual fix commit. Panelist review artifacts were written inside the
worktrees (the runner mailbox is gitignored and absent from the shared checkout) and copied
into `reviews/009_self_council/` here.

**Terminal verdict: SHIP.** No fix-required rounds; the one applied change is an
instruction-aligned additive improvement, not a fix to a defect the panel blocked on.
