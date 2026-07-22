# Instruction 007 self-Council — synthesis

**Scope:** v1.6.0 Feature C — three structural defects a 2026-07-21 parallel Opus test
(chi/express/virtio) surfaced: well-organized documents whose section *structure* the render
contract could not parse, so it passed them. Section-hierarchy fail-closed, sequential-ID
ascending-order, interview terminal renumber.
**Charters:** (a) fail-closed section detection (MP-5) + flattened mutation + per-section
non-vacuity; (b) sequential-ascending-order check; (c) interview terminal-renumber + the
operator_confirmations reference-update.
**Isolation:** each panelist in its own git worktree.

## Verdict: unanimous SHIP (single round, zero fix rounds)

| Panelist | Charter | Verdict |
|----------|---------|---------|
| A | fail-closed section detection (MP-5) | **SHIP** |
| B | sequential-ascending-order ID check | **SHIP** |
| C | interview terminal-renumber + F-2a | **SHIP** |

## A — the real fix (MP-5)

`_render_product_section_count` correctly reuses the tool-contract exclusion; the `flattened`
predicate fires ONLY on the exact collapse-to-1 case (`manifest product sections >= 2 AND
len(functional) == 1`), no false positive on a genuine 3-vs-2 merge. Mutation-bitten: neutering
the FAIL turns exactly `test_mp5_fires_on_a_flattened_multi_section_render` RED (precise, no
collateral). The per-section non-vacuity proof is real (a nested doc missing one section's
overview FAILs, so the loop iterates both sections). The `not flattened` gate suppresses the
vacuous PASS. Golden chi/express/virtio fixtures confirmed to use H2 sections — unaffected, no
correction needed. AUDIT size 11→12 with the MP-5 row + bite.

## B — sequential-ID: already enforced (the worker's finding confirmed)

B independently reproduced express's exact `001..013, 035, 014..034` shape (set-complete, out
of ascending order) and ran the current contract: **FAIL** ("expected REQ-014 at position 14,
found REQ-035"). Check 1 (`numbers == expected` over document order) already enforces ascending
order, no-gaps, and start-at-1. Mutation-bitten: degrading it to `sorted(numbers) == expected`
(set-only) turns `SequentialIdOrderTests.test_out_of_order_but_set_complete_ids_fail` RED —
proving the new pin catches a regression. Edge cases (duplicates, start-above-1, single REQ,
gap+out-of-order) all verdict correctly. Flattening cannot mask it (`_render_req_headings`
captures every `### REQ-NNN:` in document order regardless of section nesting). **The
instruction's premise (express passed) does not reproduce against current code** — it predates
this check or conflated it with the flattening defect.

## C — terminal renumber + the F-2a contradiction (the worker is right to flag)

C adjudicated the crux: the operator-confirmation record has NO `req_id` field
(`_OPCONF_REQUIRED_FIELDS` / `_CONFIRMATION_REQUIRED_FIELDS` are byte-identical, no req_id;
schemas.md §9.5.1 states "Deliberately NOT keyed on REQ id … an id would be meaningless across
runs"). F-2a shipped in instruction 003 (`dd03e77`), predating 007 — not a premise invented to
dodge the ask. Instruction 007's "update operator_confirmations.jsonl req_id fields" is
factually wrong about the record shape; updating one would violate both the append-only
invariant (§9.5.2) and the deliberate not-id-keyed design (§9.5.1). **The worker's decision to
flag the false premise rather than invent a req_id field or break append-only is correct
engineering judgment.** The terminal-renumber protocol text is correct and consistent (renumber
once, terminally; updates the manifest's id cross-references atomically; leaves the content-keyed
confirmations untouched). The fixture is real (order-dependent: renumber=True → sequential;
renumber=False → "not sequential" FAIL; the confirmation resolves by content). One documented
pre-existing residual: content-key ambiguity if two REQs share identical title+CoS — already
advisory-only and deferred to F-3, correctly out of scope.

## Design findings surfaced (for the orchestrator)

1. Work item 3 (sequential-ID) is already satisfied by Check 1 — recommend §6/the instruction
   note that ascending document order is already enforced.
2. §6 should drop the "including operator_confirmations.jsonl req_id fields" clause — it
   contradicts §8 F-2a (content-keyed, append-only).
3. The §5.2 section/requirement H2/H3 *hierarchy* was assumed by the code but never stated —
   now added to the generation guide with a worked example; §5.2 should state it too.
4. F-1 coverage-and-gaps prominence: a labelled subsection + worked example (like the marker
   fix) is worth a follow-up — omitted by 2 of 3 runs.

## State at filing

Full suite **2609 tests, 0 failures (14 skipped)**, Python 3.14.6. All mutation bites restored
via `shutil.copy2`, `__pycache__` purged, worktrees clean. Cleared to file.
