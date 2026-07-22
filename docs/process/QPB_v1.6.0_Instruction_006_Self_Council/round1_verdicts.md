# Instruction 006 self-Council — Round 1 verdicts

Three charters per the instruction, each panelist in its own isolated git worktree.
Implementation reviewed: commit **`1728ef3`**.

**Outcome:** A SHIP (1 P2), B FIX-REQUIRED (1 P1), C SHIP (1 P2 — same as B's). Fixed in `2fb7857`.

---

## Panelist A — principle-agnostic render contract → SHIP (1 P2)

- **Check correct + presence-only.** `_render_organizing_principle_stated` sets `named` on a
  principle-declaration paragraph and `rationale` only within the *same* paragraph (no
  cross-paragraph "because" leak — probed). MP-4 is gated behind `if functional:`, never
  inspects *which* principle (row-4c split preserved).
- **Mutation bites (live, restored via shutil.copy2):** neuter "no principle" FAIL → 10 tests
  RED; neuter "no rationale" → 1 RED; neuter section-overview → 2 RED. The non-functional
  regression `test_non_functional_grouping_is_accepted` (`_use_case_organized_md`, a
  use-case-organized doc) genuinely PASSES the full unmutated contract — the headline proof.
- **Oracle reconcile sound, not weakened.** A injected a real C-2 defect (renumber REQ-002→099)
  into a fixture copy and confirmed the oracle FAILs on it — the allowlist admits only the
  principle gap. `_render_fail_lines` parsing verified exact. Staleness guard works.
- **AUDIT integrity:** 11 rows (MP-4 added), size guard green, MP-4 has a `test_mp4_*` bite.
- **P2 (non-blocking):** the detector regex required `organiz(ed|ing)` and missed bare-present
  "organize/group by". Matches the prescribed §E.5 template exactly, so no live pipeline gap.
  *(Closed in 2fb7857: widened to `organiz(?:e|es|ed|ing)` + `group(?:ed|s|ing)?`, false-positive
  probed, `test_principle_detector_accepts_bare_present_tense` added.)*

## Panelist B — selection pass across pipeline + generation guide, routing → FIX-REQUIRED (1 P1)

- **Six steps present + correct** in `requirements_pipeline.md` § E.5, correctly ahead of E.6;
  E.3/E.6 cross-references intact; gate anchors resolve.
- **Routing genuine:** `phase2_generation_guide.md` part 4 carries the full IEEE 830 menu +
  stated-principle + section-overview requirements INLINE, where the Phase 2 generator reads
  (via `phase_prompts/phase2.md`) — the instruction-004 routing lesson satisfied.
- **P1 (consistency):** `phase2_generation_guide.md:167` (rationale paragraph) and `:173`
  (normative "Order sections first (user-facing → infrastructure)…" inside "REQ identifiers and
  ordering") still stated the pre-006 rule as unconditional, contradicting the new item 4 two
  paragraphs above. The design source (`Design.md:137`) carries the *generalized* version; the
  guide was not brought in line at these two spots though the pipeline doc and interview were.
  *(Closed in 2fb7857: both rewritten to "most-relevant-to-the-primary-reader first"; skill-doc
  sweep confirms the only remaining mention is the deliberate "generalization of the old rule"
  reference.)*
- No reference cycle / drift-guard breakage; gate + docs agree on the row-4b requirement.

## Panelist C — interview integration + glossary reconcile → SHIP (1 P2 — same as B's P1)

- **Stage 1** plays back the organizing principle with the "right lens / would Z fit" framing,
  states a change is a `correct` move → re-group + re-render, placed BEFORE the coverage-gaps
  playback (matches the design's "cheapest here" rationale).
- **Stage 2** reads each section overview and validates the theme before descending;
  principle-agnostic ("in the document's order… under whatever organizing principle Stage 1
  settled"); elicitation questions byte-for-byte preserved.
- **Protocol otherwise intact** (diff touches only the two hunks); entry modes / five moves /
  F-2a untouched.
- **Glossary reconcile complete:** guide parts 1–9 match Design §5.2 order-for-order with glossary
  as part 9; the old "reader meets the vocabulary before the requirements" rationale is gone (grep:
  zero hits); `docs/design/` confirmed untouched. Numbering integrity verified.
- **P2 (same as B's P1):** the :167/:173 "user-facing → infrastructure" leftover — noted as
  unreferenced legacy prose. *(Closed in 2fb7857 with B's P1.)*
