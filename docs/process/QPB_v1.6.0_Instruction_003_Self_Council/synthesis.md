# Instruction 003 self-Council — synthesis

**Feature:** v1.6.0 Feature D — the requirements validation interview (Phases 3–4),
plus F-2 (operator-confirmation source_type) and F-2a (cross-run durability).
**Charters (Design §13 item 3, + the added F-2a charter):** manifest write-back
correctness (A), interview-artifact gate compliance (B), supersession completeness (C),
F-2a durability with a mutation proof (D).
**Isolation:** each panelist in its own git worktree (runner hazard reported in 002).

## Verdict trajectory

| Panelist | Charter | Round 1 | Round 2 (closure) |
|----------|---------|---------|-------------------|
| A | manifest write-back | FIX-REQUIRED (1 P1, 3 P2) | **SHIP** |
| B | gate compliance | SHIP (4 P2) | **SHIP** |
| C | supersession | SHIP | *stands* (surface untouched) |
| D | F-2a durability | FIX-REQUIRED (1 P1, 3 P2) | **SHIP** |

**Round 2 outcome: unanimous SHIP, zero open findings.**

## The P1 — found independently by A and D

The F-2a append-only durability guarantee, the headline promise of the slice, was
**inert in every real run.** `check_operator_confirmations_append_only` enforced
append-only only inside `if prior_path.is_file():`, and nothing in production creates
`operator_confirmations.prior.jsonl` — only the test fixture did. So a re-derivation
that deleted or emptied the log PASSED the gate as "no interview has run," silently
destroying the operator's corrections, while the schema, the protocol, and Design §8
F-2a all claimed a truncating run fails. Two panelists reached this from different
charters (write-back vs. durability), which is the signal the isolated-charter design is
meant to produce.

**Fix (the mechanism the panelists' analysis pointed at): the manifest is the
cross-reference, needing no snapshot.** If `requirements_manifest.json` carries
operator-confirmation REQs, the durable log MUST exist and be non-empty; a run that
keeps the confirmed REQs but drops their backing now FAILs. The prefix-vs-snapshot check
is retained as a second mechanism for cross-run truncation. The protocol
(`requirements_interview.md`) and phase7 guide now instruct a re-derivation to snapshot
the log before rewriting `quality/` and to read the log and surface prior confirmations
at finalization — closing the "who creates the snapshot / who runs the read path" gap
both panelists named. Mutation-bitten from both charters: neutering either mechanism
turns the corresponding hole-test RED.

## P2s closed

Tautological correction-mutation test → real broken-write-back session (A);
one-directional schema/enum drift guard → bidirectional (A); five-moves tuple in three
copies → drift guard (A, B); substring-satisfiable Wiegers check → word-boundary
`_mentions()` (B); no FAIL-path coverage for `check_requirements_review` → 5-test class,
mutation-verified (B); gate shape-check accepted null/non-string → non-empty-string
type-check (B, D); dead+untested `run_state_lib.confirmations_append_only` → direct test
+ drift guard vs the gate mirror (D); schemas.md §9.5.2 "line count" → byte-prefix +
two-mechanism documentation (B, D).

## Residual (raised and closed in Round 2)

B noted the gate-level type-check fix was correct-by-inspection but lacked a committed
test driving the gate with a malformed record (only the writer was covered). Closed by
`test_gate_rejects_a_malformed_record_directly` (+ well-formed control), mutation-bitten.

## Not changed, by design

A's "re-render acceptance is somewhat circular": the interview has no production
renderer (Decision Record #7 — skill-protocol chat, no Python surface), so the fixture
renders through its own E.6 renumber and checks the result against the **real**
`check_render_contract`. The manifest↔render agreement A wanted is covered by the
separate `test_render_regeneration_fixture_v160` suite. Recorded rather than papered
over.

## State at filing

Full suite **2586 tests, 0 failures (14 skipped)**, Python 3.14.6. All mutation bites
restored via `shutil.copy2` from pristine snapshots, `__pycache__` purged between
mutate and restore, worktrees clean. Cleared to file; the operator lands the branch.
