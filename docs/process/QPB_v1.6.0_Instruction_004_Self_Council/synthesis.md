# Instruction 004 self-Council — synthesis

**Scope:** v1.6.0 — close the render-format fail-open (Design §5.3) + move the validation
interview offer to the Phase 2 → Phase 3 boundary (Design §6), plus the marker-format
generator instruction and the three-doc binding.
**Charters (per the instruction):** (a) the fail-closed check incl. mutation bites and
the empty-manifest skip; (b) format-instruction correctness across the three bound docs;
(c) placement re-sequencing completeness.
**Isolation:** each panelist in its own git worktree (the 003 phantom-failure hazard).

## Verdict trajectory

| Panelist | Charter | Round 1 (`2c389d1`) | Round 2 (`cb3d966`) |
|----------|---------|---------------------|---------------------|
| A | fail-closed check | **SHIP** | *stands (surface untouched)* |
| B | format-doc correctness | SHIP (1 P2) | **SHIP** |
| C | placement completeness | FIX-REQUIRED (1 orphan) | **SHIP** |

**Round 2 outcome: unanimous SHIP, zero open findings.**

## The blocking finding (C)

One orphaned Phase-7-as-primary offer survived the re-sequencing:
`references/phase1_exploration_guide.md:510` still asserted "Phase 7 offers the
requirements validation interview … not a Phase 2 artifact" — the pre-reversal placement.
It was not in the instruction's named surface list, but it is read by the same agent that
runs the pipeline, so a stale primary-offer statement there is exactly the "offered only
at the end" case the charter forbids. Rewritten to the Phase 2→3 boundary; a full
skill-tree sweep confirmed it was the only survivor, and C's independent closure sweep of
nine surfaces confirmed all agree.

## The P2 (B)

The new worked-example prohibition list claimed `### REQ-7:` (un-padded) "turns the render
contract off" — but `_RENDER_REQ_HEADING_RE` (`REQ-(\d+)`) matches it and the sequential
check compares int values, so padding is invisible to the gate. The doc asserted an
enforcement the mechanism doesn't provide. Fixed by splitting the list into
contract-disabling forms (bold/em-dash/period) and read-but-nonconforming forms
(wrong-level WARN, un-padded convention), and stating plainly the gate does not enforce
padding. B's closure re-ran the regex and confirmed the doc now matches the mechanism
exactly.

## What A confirmed (no changes)

The fail-closed check is correct across every edge case (no-refs record → product;
tool-contract-only → skip; absent/malformed manifest → skip; populated + zero headings →
FAIL), mutation-bitten live (neutering the FAIL turns the bold-marker test RED), the
version-gate reorder correctly prevents retroactively failing pre-v1.6.0 archived runs,
and there are no false positives.

## Process finding surfaced (not the worker's to fix)

The design spec §5.3 and §6 are **uncommitted** in the working tree. The instruction said
to read them as the spec, but they exist only as uncommitted modifications to
`docs/design/QPB_v1.6.0_Design.md`, so the Round-1 panelists (reviewing committed state)
could not see them, and the doc internally contradicts itself (old placement language at
Design:174 / Plan:87 coexists with the new §6). The implementation is correct against the
working-tree spec; `docs/design/` is orchestrator-owned, so it is flagged for the
orchestrator to commit and reconcile.

## State at filing

Full suite **2592 tests, 0 failures (13–14 skipped)**, Python 3.14.6. All mutation bites
restored via `shutil.copy2`, `__pycache__` purged, worktrees clean. Cleared to file.
