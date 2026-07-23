# Instruction 027 — render labeled-slot format contracts: self-Council synthesis

**Terminal verdict: unanimous SHIP** across all three charters, zero FIX-REQUIRED.

The final simplification (Fable Q4). Feature C's render-contract gate had four
checks that mechanized a prose-QUALITY judgment as a hard FAIL — the same smell as
the advisory floor. `_render_rationale_present` had already false-FAILed two
well-formed specs (chi's bare "so", virtio's "Rationale:" label), and its own
comment admitted "every widening misses the next valid phrasing." Fable rejected a
plain FAIL→WARN downgrade as too weak and prescribed **labeled-slot format
contracts**: the generation guide requires a labeled slot; the gate FAILs on the
slot's ABSENCE (structural — a label is a literal string); the slot's content
quality goes to the interview + readability rubric. Because it changes gate FAIL
behavior, a full 3-charter self-Council ran (each panelist in its own worktree
reset to `c5e068d`, each running the gate and mutation-biting).

## The conversions
1. **Organizing principle + rationale → one labeled slot** `Organizing principle:
   <name> — Rationale: <text>`; gate FAILs only on label absent / name empty /
   rationale empty. Deleted the 27-alternation `_RENDER_RATIONALE_CONNECTOR_RE`,
   the `≥2-sentences-of-≥4-words` arithmetic (`_render_rationale_present` +
   `_RENDER_SENTENCE_SPLIT_RE` + `_RENDER_RATIONALE_MIN_WORDS`), and the
   prose-phrasing `_RENDER_PRINCIPLE_RE`.
2. **Singleton justification → labeled `Standalone rationale: <why>` slot**; FAIL
   on absence only. Deleted the keyword scan of the justification's content.
3. **Section overview → presence, not length:** `len(intro) >= 40` → `bool(intro)`.
   Deleted the 40-char magic threshold.
4. **Generation guide + pipeline E.5** updated so the generator emits the slots.

## Charters + verdicts

- **A — The gate keeps its teeth: SHIP.** An absent slot / singleton justification
  / section overview each still FAILs *structurally* (empty-name FAILs too; short
  overview passes). Each teeth is mutation-confirmed load-bearing (neutering it
  reddens the suite), and all three checks call `fail()`, not `warn()` — a
  generator skipping a slot cannot pass silently.

- **B — No phrasing/length/quality judgment remains: SHIP.** All five deleted
  symbols are gone (referenced only in the test's own absence-assertion). Terse,
  weak ("it seemed reasonable"), bare-"so", 1-char-overview, and
  nonsense-content-singleton slots all pass 0 FAIL, as do the two recorded
  false-FAIL cases (chi's "so", virtio's "Rationale:" label). No residual
  content/length/phrasing predicate survives.

- **C — The generator emits the slots + no scope creep + no regression: SHIP.**
  The generation guide (and pipeline E.5) require exactly the slots the gate
  checks, proven consistent by building the guide's own example through the gate
  (it passes). The chi/express/virtio golden fixtures were **not** hand-edited —
  the recorded principle-gap FAIL was only re-worded in `EXPECTED_FIXTURE_FAILS` +
  the assertion (a recorded-expectation update, the fixture-discipline invariant).
  The diff touches only the render region + guide/pipeline + tests; the other gate
  checks (C-1..C-7, F-1, glossary, sequential-id) and Feature G/H are untouched;
  all suite failures are environmental.

## The fixtures the contract change required
The render-contract test fixtures (clean/use-case/flattened/single-section), the
`OrganizingPrinciple` + `C3` tests, and the interview-fixture rendered spec were
migrated to the slot format with reversal comments — a format migration, not a
pass-tweak. The chi/express/virtio regeneration golden files still predate the
selection pass, so their recorded principle-gap FAIL persists (re-worded); their
true regeneration remains a separate run (a standing carry-forward).

## Verification
Full suite **2781 / 0 / 14**, Python 3.14.6. Reviewed commit `c5e068d`.

**Terminal verdict: SHIP.** The render contract keeps its structural teeth (an
absent slot / justification / overview still FAILs) while every phrasing, length,
and quality judgment is deleted — the chi "so" and virtio "Rationale:" false-FAILs
are gone, and quality moves to the interview + readability rubric. **This completes
the simplification sweep (instructions 023–027).**
