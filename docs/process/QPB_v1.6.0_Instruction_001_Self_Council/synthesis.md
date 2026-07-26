# Instruction 001 — worker self-Council synthesis

*v1.6.0 Track 1, Phase 2 acceptance (Feature C — spec organization & coherence).
Protocol: `ai_context/DEVELOPMENT_PROCESS.md` § "Worker self-Council protocol";
panel charters per `QPB_v1.6.0_Design.md` §13 item 2.*

**Rounds:** 6. Round 1 = three panelists with orthogonal charters, unanimous
FIX-REQUIRED. Rounds 2-6 = closure audits, each verifying the previous
round's fixes by execution rather than by reading the diff.

**Commits reviewed:** `71b1a81`, `d8d4229`, `edc5cec` (the work), then
`f9984ae`, `a95dcb5`, `3ef3a7e`, `b863deb`, `4255002`, `94c7e3d` (six fix
rounds).

**Round-by-round:**

| Round | Found |
|---|---|
| 1 | P0 fabricated coverage claim; `## Requirements` bypass (2 panelists, independently); vacuous manifest invariant; 2 archived GATE PASSED→FAILED flips; displaced title text lost from the manifest; incomplete defensive sweep |
| 2 | the bypass fix was half-applied and its regression test was *coincidentally green*; 3 regressions introduced by the round-1 fix, all over-firing |
| 3 | the re-pointed test **was never re-pointed** — the commit message claimed work not done; the three new mandatory-part checks had no bite at all; a fifth bypass (fenced headings) |
| 4 | a sixth bypass — the fence regex was backtick-only, closing-pair-required, not line-anchored; field *deletion* undetected; four substring-weak assertions |
| 5 | fence grammar confirmed closed across 19 shapes; two new bypasses — fence info-string polarity inversion, HTML block types 2 and 6; **and the diagnosis that ended the loop** |
| 6 | (final closure verification) |

---

## Panel

| Panelist | Charter | R1 verdict |
|---|---|---|
| A | render-contract correctness, incl. mutation coverage | FIX-REQUIRED |
| B | regeneration-fixture fidelity against C-1…C-7 | FIX-REQUIRED |
| C | regression safety on manifest semantics, blast radius | FIX-REQUIRED |

Each panelist ran as a separate subagent context with no exposure to the
implementer's reasoning trace, and each wrote its verdict to a file before
reporting — both required by the protocol, and the second because a verdict
that exists only in a stream can be lost.

---

## Where the panel agreed (highest confidence)

**The `## Requirements` bypass.** Panelists A and C found this
independently, from different charters. `requirements?` was in the
structural-heading pattern, so a document parking every REQ under a flat
`## Requirements` heading emptied the functional-section list and skipped
intro-prose, singleton and cross-cutting checks entirely — `FAIL=0` on
precisely the flat-list shape §5.2 exists to reject. Two panelists arriving
at the same hole by different routes is the strongest signal the panel
produced, and it was also the finding the worker went on to under-fix (see
"What the process caught about itself").

**Mutation coverage is genuine.** Panelist A verified the claim empirically
rather than on trust — 14 source mutations against `quality_gate.py`, all 14
caught, restore verified clean each round. No tautologies. Panelist C
independently confirmed the suite counts and hermeticity. This matters
because the whole render contract rests on those bites meaning something.

**Recall measurement is not broken.** Panelist C's charter headline. The
recall-baseline targets exit 1 both before and after the work; the new check
adds failures to trees that were already failing and does not perturb the
measurement corpus. Round 2 re-verified across all 59 archived trees: zero
flips in either direction after the version-gating fix.

---

## Where they diverged (judgment calls)

**Verdict category for the render checks.** Panelist A noted that C-6's
terminal-period rule and C-7's stamp check are record-keeping-shaped rather
than substantive, and could argue for `VERDICT_RECORD_KEEPING`. A concluded
`substantive` is defensible for the aggregate, and the worker kept it: a
document failing the render contract is not merely untidy, it is the defect
class this release exists to close.

**How much of the fixture's prose is exemplary.** Panelist B held new
LLM-authored prose to a fabrication standard and found one P0. The chi
render agent itself flagged that its coverage-and-gaps paragraph was
"inferred from the input's scope rather than read from it" — an honest
self-report that turned out to be the right worry, in a different file.

---

## Findings and disposition

### P0 — fabricated scope claim (Panelist B)

virtio's coverage-and-gaps statement said the per-device drivers "are
outside the checkout entirely". `virtio_balloon.c`, `virtio_mem.c`,
`virtio_input.c`, `virtio_dma_buf.c` and the `virtio_rtc_*.c` family are all
present in `drivers/virtio/`, and none is referenced by any REQ. The largest
**in-scope** zero-coverage surface was described to the operator as
out-of-scope.

This fails in the direction that matters most: F-1 exists to make thin
coverage visible, and it is played back to the operator in interview
Stage 1. A gaps statement that under-reports is worse than none, because it
manufactures false confidence. **Closed** — rewritten to name those files
and to separate them from virtio-net/-blk/-scsi, which genuinely are outside
the checkout. Round 2 verified every factual claim in the rewrite against
the checkout and found no new unsupported ones.

### P1 — six, all closed

1. **`## Requirements` bypass** (A, C). Structural-heading classification
   now requires a whole-heading match AND that the section hold no REQs; a
   structural part holding REQs no longer synthesizes a functional section;
   and a document with requirements but no functional section FAILs in its
   own right. Round 2 found the first attempt insufficient — see below.
2. **Inertness predicate was heading shape, not version** (C). `### REQ-NNN:`
   long predates v1.6.0; 49 archived trees carry it and two archived runs
   flipped GATE PASSED → GATE FAILED. Now gated on the run's own recorded
   skill version against a v1.6.0 floor. Both flips verified restored.
3. **Vacuous manifest invariant** (B, C). The invariant compared a *multiset*
   of reference-lists, which survives rotating every REQ's references onto
   the wrong record, and never compared any other field. Now pairs records
   through an explicit committed `renumber_map.json` and compares
   field-by-field against a documented mutable-field allowlist.
4. **Displaced title text lost from the manifest** (B). express and virtio
   rewrote titles without folding the displaced normative sentence into the
   manifest, so the FP-audit — which reads the manifest and never the
   render — saw a weaker requirement than a human reader. Folded into
   `conditions_of_satisfaction` on 25 records; round 2 verified 25/25
   preserve the original sentence verbatim with no corruption.
5. **Pass-name leak in the chi fixture** (B). `Pipeline: contract-extraction
   v2 with narrative pass` — a pass name, which §5.3 seeds the C-5 deny-list
   with but which was never implemented. Notably this leak came from the
   version-stamp template `71b1a81` itself had just written. Deny-list now
   covers pass names; the header line is gone from spec and fixture.
6. **Defensive sweep stopped one file short** (A). Five more
   `"skill_version": "1.5.x"` literals survived in agent-copied templates,
   one inside an executable heredoc and three feeding a blocking check.
   Because this defect class has now fired three times it earned an
   AUDIT-table sweep rather than a fourth point fix.

### Correctly deferred

- **The fixture is a golden file, not a live regeneration** (B). Nothing
  re-renders; the tests validate committed artifacts. A regression in the
  reference-doc prose cannot fail the suite. Sound to defer — building a
  deterministic renderer is an architectural addition the design does not
  call for. Reported to the orchestrator as the most consequential open
  question from this instruction.
- **The Plan's invariant wording** (C). "Unchanged modulo the renumber map"
  is contradicted by the design's own §5.2/§5.4. The honest invariant is
  recorded in the test docstring; the Plan is the Cowork-editable planning
  surface, so the worker reported rather than edited it.

---

## What the process caught about itself

Two things worth keeping, both about self-review failing in characteristic ways.

**The worker under-fixed the finding it was most confident about.** Panelist
A's P1 asked for two changes; the worker landed one, and the regression test
it wrote to pin the fix was *coincidentally green* — the fixture omitted
intro prose, so the test passed on an unrelated failure and would have
survived deleting the guard it existed to protect. Round 2 caught it by
constructing the bypass rather than reading the diff. A test that passes for
the wrong reason is worse than no test, because it reads as coverage to the
next person. This is the concrete argument for a closure round that
re-derives the exploit instead of checking the fix off a list.

**The fix round introduced three regressions of its own** — an over-broad
pass-name pattern that blocked a legitimate compiler-target REQ, an F-1
scoping change that WARNed on a correct document, and a half-applied
code-fence exemption. All three were over-firing, i.e. the fixes for
false negatives created false positives. The Implementation Plan names
render-contract over-firing as a top risk; that risk is realized during
*fix* rounds, not initial implementation.

**The AUDIT sweep out-performed the hand sweep.** The version-literal sweep
test, written to close Panelist A's finding, immediately found two further
instances that neither the worker nor three panelists had caught by hand.
On inspection those two were correctly *not* the same defect class and were
dispositioned as justified AUDIT rows — which is the pattern working as
designed: mechanical enumeration first, human judgment on each row second.

**A commit message asserted work that was never done.** Round 3 found that
`a95dcb5`'s message claimed the flat-shape bite had been re-pointed at an
intro-prose fixture. That commit touched two files and the test file was not
one of them. Deleting the guard the commit was written to add left the whole
suite green. This is the verify-before-claim rule failing inside the artifact
that is supposed to be the record — and it is worse than the original gap,
because a future reader had both a green test and an explicit claim telling
them the bypass was pinned. The prior message was left standing rather than
rewritten; the correction lives in the next commit.

**The loop, and how it ended.** The single most useful output of this Council
is round 5's diagnosis. Five consecutive rounds found a bypass in the same
component, and every fix was *correct about exactly the shape it had been
shown*:

> The exit condition isn't "cover the grammar", it's "check the model
> against an authority." Every bypass in rounds 3-5 was a gap between the
> gate's model of Markdown and Markdown itself.

Round 4 asked for the full fence grammar and got it — faithfully. Round 5
then found the same worker had hand-modelled one quarter of the HTML block
grammar in the very next commit. Enumerating harder was never going to
terminate, because the failure was not insufficient diligence; it was
hand-modelling a specification that already has a reference implementation.

The fix is `test_render_fence_differential_v160.py`: 34 constructs, both the
gate's model and `markdown_it` asked the same question, disagreement
reported with its direction (bypass vs false positive). It found two
disagreements on its first run. Two intentional divergences are enumerated
with justification and guarded by a test asserting no divergence may ever be
permissive, and another that fails when a row goes stale.

**Generalizable lesson.** When a check reimplements a specification that has
a reference implementation, differential-test against the reference. An
enumeration of shapes is only ever as complete as the last review round.

---

## Verdict

See `round3_closure.md` for the final closure verdict. Rounds 1 and 2 both
returned FIX-REQUIRED and both iterated in-branch before this synthesis, per
the protocol's requirement that the internal panel be the load-bearing first
quality gate rather than a formality run after filing.

## Artifacts

| File | Contents |
|---|---|
| `panelist_A_render_contract_correctness.md` | R1 charter A verdict |
| `panelist_B_fixture_fidelity.md` | R1 charter B verdict |
| `panelist_C_regression_safety.md` | R1 charter C verdict |
| `round2_verification.md` | closure audit of `f9984ae` |
| `round3_closure.md` | final closure check of `a95dcb5` |
| `evidence_c1_c7_before_after.md` | mechanical per-defect before/after table |

**Gitignore status:** this directory matches `.gitignore:82` (`reviews/`, a
bare pattern matching at any depth) and is therefore **untracked**. Per the
instruction's evidence-durability requirement, a consolidated tracked copy
is committed at `docs/process/QPB_v1.6.0_Instruction_001_Self_Council.md`.
