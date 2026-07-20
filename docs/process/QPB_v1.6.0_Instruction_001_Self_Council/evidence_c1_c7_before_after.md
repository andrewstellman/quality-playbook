# C-1…C-7 before/after evidence — mechanically derived

*Instruction 001, v1.6.0 Track 1 Phase 2 acceptance oracle. Generated 2026-07-19 by
re-evaluating each defect class directly against the rendered documents and manifests,
independently of `quality_gate.check_render_contract` (so the gate is not its own witness).*

**Before** = `bin/tests/fixtures/render_contract_v160/<target>/quality/REQUIREMENTS.before.md`
(the preserved 2026-06-19 v1.5.8 render).
**After** = the same manifest re-rendered through the v1.6.0 render contract.

Fixture inputs at `repos/{chi,express,virtio}-1.5.8/quality/` were read-only throughout;
SHA-256 verified unchanged before and after the work.

## Per-defect measurements

| Measure | chi before → after | express before → after | virtio before → after |
|---|---|---|---|
| **C-1** tool-contract REQs in product spec | 8 → **0** | 8 → **0** | 8 → **0** |
| **C-2** identifier sequence broken (1=yes) | 1 → **0** | 1 → **0** | 1 → **0** |
| **C-3** unjustified singleton sections | 3 → **0** | 6 → **0** | 2 → **0** |
| **C-4** Overview present | False → **True** | False → **True** | True → True |
| **C-4** Cross-cutting present | False → **True** | False → **True** | True → True |
| **C-5** internals (HTML comments + provenance lines) | 2 → **0** | 1 → **0** | 1 → **0** |
| **C-6** titles > 120 chars | 7 → **0** | 1 → **0** | 3 → **0** |
| **C-6** titles with terminal period | 16 → **0** | 8 → **0** | 0 → 0 |
| **C-7** generator stamp | `v1.5.3` → **`v1.6.0`** | `v1.5.8` → `v1.6.0` | `v1.5.8` → `v1.6.0` |
| REQs rendered in product spec | 16 → 8 | 16 → 8 | 17 → 9 |
| Manifest record count | 16 → **16** | 16 → **16** | 17 → **17** |

The product-spec REQ count drops because the tool-contract REQs relocated to
`RUN_CONTRACT.md` (C-1 working as designed). The **manifest record count is unchanged** —
no requirement was added, dropped, merged, or weakened. Reference sets are byte-identical
across the renumber for all three targets.

## Gate verdicts

Running `check_render_contract` (twelve checks) on each document:

| Target | before | after |
|---|---|---|
| chi | 13 FAIL, 2 WARN | **0 FAIL, 1 WARN** |
| express | 12 FAIL, 2 WARN | **0 FAIL, 1 WARN** |
| virtio | 9 FAIL, 2 WARN | **0 FAIL, 1 WARN** |

The before-column is pinned by `test_before_documents_still_exhibit_the_defects` — if the
pre-v1.6.0 renders ever stop failing, the oracle is vacuous and that test fails.

### Provenance of these figures (corrected 2026-07-20, instruction 002 item 4)

The gate-verdict row first read **11 / 9 / 6 FAIL, 1 WARN**. Those numbers were
measured mid-instruction-001 and never regenerated against final gate behavior,
even though this file was committed at `8db8af3` — *after* the Phase-2 code
commits. Re-running `check_render_contract` against the `.before` fixtures with
current code gives **13 / 12 / 9**.

**The error direction was safe: actual detection is stronger than was reported,
not weaker.** No defect went unreported; the contract catches more than the
document claimed.

Composition of the delta, measured rather than assumed:

| Target | old | MP-1 (Actors + Traceability) | stamp | new |
|---|---|---|---|---|
| chi | 11 | +2 | — | 13 |
| express | 9 | +2 | +1 | 12 |
| virtio | 6 | +2 | +1 | 9 |

MP-1 is the §5.2 mandatory-part block added in self-Council round 3. The stamp
column needs explaining: round 1 measured the `.before` documents at
`skill_version=1.5.8`, where express's and virtio's stamps *matched* and passed;
the harness now holds the version at the fixture's `1.6.0`, so they mismatch and
fail. chi is unaffected because its `v1.5.3` stamp mismatched either way — which
is C-7 itself.

*This differs from instruction 002's account, which attributed the third
component to "a chi intro-prose FAIL". That FAIL was already inside the original
11; verified by re-running both bases.*

The WARN column moved 1 → 2 for the same reason a count in a living record always
moves: instruction 002 item 3 added the advisory glossary check. These figures
were therefore measured **after** items 1-3 landed, so they are stable as of
`0e75fd2` rather than stale on arrival.

**Failure class.** This is the same one the instruction-001 self-Council caught at
round 3, where a commit message asserted work that was never done: a figure
recorded once and never re-derived after the thing it measured changed. The
durable fix is not vigilance — it is that
`test_before_documents_still_exhibit_the_defects` pins the *property* (the before
documents must still fail) rather than the number, so the property cannot rot
even when a transcribed count does.

## Notes on what the numbers show

- **C-4 is the discriminating case.** virtio already had an Overview and Cross-cutting
  concerns; chi and express had neither — from the same pipeline, same skill version, same
  day. That is the "Phase E fires unpredictably" defect stated as a measurement, and it is
  why Phase E is now unconditional rather than merely imperative.
- **C-7 is likewise discriminating.** chi stamped `v1.5.3`; express and virtio stamped
  `v1.5.8` correctly on the same day. The cause was a hardcoded literal in the stamp
  template sitting ten lines above a rule telling the agent to read the version from
  SKILL.md frontmatter. chi copied the literal; the others followed the rule.
- **express is the C-1 and C-3 flagship**: 8 of its 16 REQs were QPB's own filing
  conventions, and six of its eight functional sections held exactly one REQ.
- The checks **discriminate rather than blanket-fail**: on the before-documents they PASS
  virtio's overview, cross-cutting section and stamp, and express's stamp and intro prose,
  while failing everything genuinely defective.
