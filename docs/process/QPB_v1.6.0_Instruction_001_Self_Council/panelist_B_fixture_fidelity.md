VERDICT: FIX-REQUIRED

# Panelist B — Regeneration-fixture fidelity against C-1..C-7

Commits under review: 71b1a81, d8d4229, edc5cec
Charter: regeneration-fixture fidelity (Design §1.2 defect classes, §5 acceptance oracle)
Repo: /Users/andrewstellman/Documents/QPB (branch 1.6.0)

## Summary

The mechanical half of this work is genuinely good. Input provenance is clean, C-1 relocation is
complete and verified record-by-record, the C-6 retitling preserved normative content in the
*render*, cross-references were correctly chased through the renumber map, and all three targets
converge on the eight-part architecture. I verified these by reading the documents, not by trusting
the gate.

The prose half does not hold. The virtio coverage-and-gaps statement asserts a scope fact that is
false against the actual checkout, and it is false in the direction that conceals the largest
uncovered surface — in the one artifact whose entire stated purpose (F-1, Design:178) is to be an
honest gap disclosure played back to the operator in interview Stage 1. That is the fabrication
class the charter names as P0. Two secondary grounding defects and one real manifest-fidelity
weakening follow.

I verified pristine inputs were not modified: `REQUIREMENTS.before.md` and
`requirements_manifest.before.json` are byte-identical to `repos/{chi,express,virtio}-1.5.8/quality/`
for all three targets. The read-only claim in the commit message holds.

---

## P0

### P0-1 — Fabricated scope claim in virtio's coverage-and-gaps statement

`bin/tests/fixtures/render_contract_v160/virtio/quality/REQUIREMENTS.md:42-45`:

> The derivation knowingly did **not** cover: the per-device drivers that sit above this layer
> (virtio-net, -blk, -scsi and friends are **outside the checkout entirely**, so nothing constrains
> how they consume these contracts)

This is false. The checkout contains eight per-device driver files:
`repos/virtio-1.5.8/drivers/virtio/{virtio_balloon.c, virtio_mem.c, virtio_input.c,
virtio_rtc_arm.c, virtio_rtc_class.c, virtio_rtc_driver.c, virtio_rtc_ptp.c, virtio_dma_buf.c}`.

The run's own Phase 1 artifact says so explicitly —
`repos/virtio-1.5.8/quality/EXPLORATION.md:7-9`: *"a transport-abstraction core (`virtio.c`,
`virtio_ring.c`) plus four transport backends (PCI-modern, PCI-legacy, MMIO, vDPA) **and several
device drivers (balloon, mem, input, rtc)**."* None of those files appears in any REQ's
`references` in either manifest (grep of `requirements_manifest.json` for
`virtio_balloon|virtio_mem|virtio_input|virtio_rtc` returns zero hits).

So the single largest in-scope, zero-coverage surface in the target is described to the operator as
out-of-scope-by-construction. The statement picks three drivers that happen to be absent
(net/blk/scsi) and generalizes them into a claim about "the per-device drivers", which converts a
real, actionable gap into a non-gap. It is also imprecise even on its own terms: `virtio_net.h`,
`virtio_blk.h` and `virtio_scsi.h` headers *are* in the checkout
(`repos/virtio-1.5.8/include/{linux,uapi/linux}/`).

Why this is P0 and not P2: F-1's designed consumer is the Stage-1 interview question *"here's what I
believe I did not cover — intentional?"* (Design:155, :178). An operator answering that question
against this statement is being told not to look at balloon/mem/input/rtc. A gap statement that
mis-scopes the gap is worse than no gap statement, and this ships as the reference exemplar that
future runs are calibrated against. The charter is explicit: fabricated prose in a shipped fixture
is a P0.

Fix: state the gap truthfully — the per-device drivers (balloon, mem, input, rtc) are present in the
checkout and were deliberately not turned into REQs because the run scoped to the transport-core
contracts; net/blk/scsi are genuinely absent.

---

## P1

### P1-1 — chi's regenerated render *introduces* derivation-internal pass-name vocabulary (C-5 regression)

`bin/tests/fixtures/render_contract_v160/chi/quality/REQUIREMENTS.md:6`:

> `Version: v2.0 · Pipeline: contract-extraction v2 with narrative pass`

Three problems compound here:

1. **This line is not in chi's input.** `chi/quality/REQUIREMENTS.before.md:1-9` has no `Pipeline:`
   line. The regeneration *added* it — apparently borrowed from
   `virtio/quality/REQUIREMENTS.before.md:8`, which carries exactly this string.
2. **The virtio render correctly strips it** (`virtio/quality/REQUIREMENTS.md:1-8` has no
   `Pipeline:` line). So the fixture is internally inconsistent about the same defect class across
   two targets — precisely the C-4-style unpredictability this release exists to eliminate.
3. **It is the thing C-5 forbids.** Design §5.3 check 4 (Design:134) specifies the deny-list is
   "seeded with `Asymmetry-promotion`, `cluster:`, **pass names**". "contract-extraction v2 with
   narrative pass" is a pass name. The gate misses it because `_RENDER_INTERNAL_VOCAB`
   (`plugins/quality-playbook/skills/quality-playbook/scripts/quality_gate.py:6839-6844`) contains
   only `Asymmetry-promotion`, `cluster:`, `pre_narrative`, `REQUIREMENTS_pre_narrative` — the
   design's "pass names" seed was not actually implemented.

So one of the seven defect classes the oracle certifies as absent is present in a regenerated
fixture, and the mechanical check that was supposed to catch it is under-seeded. Both the fixture
and the deny-list need fixing.

Related, lower confidence: `virtio/quality/REQUIREMENTS.md:105-106` retains verbatim
`5. (Asymmetry: "modern PCI compensates via vp_transport_features; MMIO and vDPA rely entirely on
vring_transport_features and compensate for nothing.")`. The parenthesised-quoted-string shape reads
as a preserved manifest field rather than a condition of satisfaction, and it is the same
`Asymmetry` metadata the deny-list targets in its `Asymmetry-promotion` form. Judgment call, but it
should either become a plain sentence or move to the manifest.

### P1-2 — Manifest titles were rewritten, weakening the source of truth; the invariant test does not check them

`ManifestUnchangedInvariantTests` docstring
(`bin/tests/test_render_regeneration_fixture_v160.py:240-247`) claims: *"same records, renumbered
only… `requirements_manifest.json` for a fixed input is unchanged modulo the renumber map."* The
commit message repeats it. **This is false of the fixture it guards.**

Diffing before/after manifests record-by-record (matched on reference tuple / text, so renumbering
does not confound): `title` changed on **every retitled REQ across all three targets** (chi via
`text`-keyed records: unchanged; express: 16/16 titles rewritten; virtio: 8 titles rewritten), and
`functional_section` changed on chi (5 records) and express (8 records).

Retitling is defensible per Design §5.4 — but it is a *pipeline* change, not presentation, and the
design's own verification clause (Design:144(c)) and Feature B's dependency contract (Design:97 —
*"the FP-audit's requirements-traceability check consumes the manifest, not the rendered document —
so Feature C's render changes cannot perturb it"*) both assume the manifest is untouched. It was
touched.

Worse, content was **lost from the manifest** even where the render preserved it. Concrete case,
express REQ-001:

- before `title`: `res.cookie must not emit a Max-Age that contradicts a future Expires`
- after `title`: `res.cookie Max-Age and Expires directives that agree`
- after `conditions_of_satisfaction`: **unchanged** — does not contain the displaced sentence
  (verified: `'contradicts a future' in cos` → `False`)
- after render (`express/quality/REQUIREMENTS.md:109`): *does* append the displaced sentence

So the normative "must not emit a Max-Age that contradicts a future Expires" survives only in the
rendered prose and was dropped from the declared source of truth. Same shape for virtio REQ-001,
where `(28..41)` and `that vring_transport_features cannot enumerate` live only in the render's
CoS.1 — the virtio manifest has no conditions field at all. A manifest-consuming reader (the
FP-audit) sees a weaker requirement than a document-reading reader. That is the "WEAKENED" case the
charter asks about, and Phase E forbids it.

The invariant test cannot catch this because it checks only: record count, the sorted multiset of
reference lists, id density, and manifest-ids == rendered-ids. It never inspects `title`,
`functional_section`, `conditions_of_satisfaction`, `implementation`, `tier`, or `use_cases`, and it
never pairs a before-record to its after-record — so it compares *collections*, not *records*.

Fix: either (a) fold displaced normative text into the manifest's CoS as well as the render, and
extend the invariant test to pair records and assert per-field preservation of `use_cases` and CoS;
or (b) retitle the docstring/commit claim to what is actually true ("records preserved; titles and
sections intentionally re-derived per §5.4") and state the Feature B seam explicitly. Silently
over-claiming an invariant that the test does not enforce is the worse of the two failure modes.

### P1-3 — The "regeneration" fixture is a golden file, not a regeneration

No renderer exists in these three commits. `git show --stat` across 71b1a81/d8d4229/edc5cec shows
changes only to reference/prompt markdown, `quality_gate.py`, and tests — no render code. Nothing in
`test_render_regeneration_fixture_v160.py` re-renders anything; `_run_render_contract`
(`:70-81`) only *validates* the already-committed `REQUIREMENTS.md`.

Design §5 verification (b) (Design:144) says *"re-render the chi, express, and virtio manifests
through the new renderer"*. What landed is: an LLM hand-authored three documents, and the checker
those same commits introduced passes them. That is a self-consistent pair, not an oracle. The
concrete consequence: a regression in `references/phase2_generation_guide.md` — the actual
"renderer" in QPB's agent architecture, and the thing 71b1a81 spent its whole diff on — cannot fail
this suite. The fixture pins output; nothing pins the generating contract that produced it.

I accept this may be an intended architectural consequence of the renderer being an agent rather
than code. But then the docstring at `:1-8` and `:14` ("re-rendered through the v1.6.0 contract")
overstates what is mechanized, and the gap should be recorded — the oracle is reproducible only by
re-running an LLM, which is exactly the unpredictability C-4 was filed against.

---

## P2

### P2-1 — chi cites a `docgen` tree that does not exist in the target

`chi/quality/REQUIREMENTS.md:62`: *"No requirements were derived for the `docgen` or example
trees."* `repos/chi-1.5.8/` contains `_examples/` but no `docgen` directory or file
(`find … -name "*docgen*"` → empty). go-chi/docgen is a separate repository. Ungroundable claim
about the audited tree; smaller than P0-1 because it over-states a gap rather than concealing one,
but it is still an invented artifact in a shipped exemplar.

### P2-2 — chi's skimmed-middleware list reads exhaustive and is about one third of the remainder

`chi/quality/REQUIREMENTS.md:56-59` says *"It did **not** turn the remaining middleware into
requirements: the logging, request-ID, recoverer, throttling, timeout, and profiler middleware were
skimmed…"*. All six named files exist (`logger.go`, `request_id.go`, `recoverer.go`, `throttle.go`,
`timeout.go`, `profiler.go`) — grounded. But `repos/chi-1.5.8/middleware/` holds ~29 non-test files;
the un-REQ'd remainder also includes `basic_auth.go`, `clean_path.go`, `content_encoding.go`,
`content_type.go`, `heartbeat.go`, `nocache.go`, `request_size.go`, `route_headers.go`,
`sunset.go`, `terminal.go`, `wrap_writer.go`, `maybe.go`, `value.go`. The sentence's grammar
("the remaining middleware: <list>") asserts the list is the remainder. Same honesty-of-gaps class
as P0-1, milder. Note `clean_path.go` is a *path-manipulation* middleware — squarely in REQ-001's
stated theme — and is silently absent.

### P2-3 — `test_before_documents_still_exhibit_the_defects` is a real vacuity guard but coarse

`bin/tests/test_render_regeneration_fixture_v160.py:155-170`. It is real — it stages into a temp
tree, runs the live contract against the `.before` documents, and would go red if they stopped
failing. Good, and the staging (vs. in-place swap) plus
`test_fixture_files_are_not_mutated_by_the_test_run` (`:328-348`) is careful work.

But the assertion is `assertGreater(fails, 0)` — one surviving failure anywhere keeps it green. The
oracle it guards is per-defect ("C-1..C-7 all absent"), and nothing here maps an assertion to a
named defect class except C-1 (`ToolContractSplitTests`, `:173-237`). If five of the seven checks
were gutted, chi's stale `v1.5.3` stamp alone would still produce `fails > 0` and this test would
pass. Recommend asserting the *set of failing check names* per target against a recorded expectation
— that makes it a per-defect bite and documents which defects each benchmark actually exhibited.

Same shape, weaker: `test_regenerated_documents_emit_no_advisory_warnings` (`:148-153`) claims in its
docstring to pin F-1 presence, but `warns == 0` also holds if the F-1 check never fires.

### P2-4 — `test_fixture_spans_three_distinct_repo_shapes` is a tautology

`:130-131` is `assertEqual(len(set(TARGETS)), 3)` — it asserts a three-element tuple of distinct
strings has three distinct strings. It tests nothing about repo shapes and cannot fail short of
someone editing the tuple.

On the underlying question (charter item 4) the answer is nonetheless **yes, genuinely three
shapes**, and this is a real strength of the work: Go router / JS framework / C kernel subsystem;
three *different manifest record schemas* (chi keys on `text` + `pattern`; express on `title` +
`implementation` + `conditions_of_satisfaction` + `specificity`; virtio on `title` + `tier_label` +
`source` + `formal_doc_refs`); 8/8/9 product REQs; different before-defect profiles (chi alone
exhibits C-7 and the `Asymmetry-promotion` C-5 form; express alone exhibits six-way C-3 degeneracy;
virtio alone already had Overview + Cross-cutting). The contract is not tuned to one document.

Two caveats worth recording. (a) All three renders converge on exactly three functional sections and
an identical eight-heading skeleton — plausible given the contract, but a mild tell of
optimize-to-the-checker. (b) No target exercises the §5.2 singleton-justification escape hatch or
the §5.2 item-5 NFR-section slot, so those contract branches are unexercised by the oracle.

---

## What I verified as sound (recorded so the fixes above are not over-read)

- **Input integrity.** All six `.before` artifacts byte-identical to `repos/*-1.5.8/quality/`.
- **C-1 — complete, verified per record.** Each target has exactly 8 `quality/`-only-reference REQs;
  all 8 appear as `### REQ-NNN:` in `RUN_CONTRACT.md` and none in `REQUIREMENTS.md`. Relocated, not
  dropped.
- **C-2 — sequential in document order** in all three renders (chi 001-008, express 001-008, virtio
  001-009).
- **C-3 — real merges, no REQ lost.** express went from six singleton sections to three sections of
  2-3; record count 16→16 with no text added or dropped.
- **C-4 — Overview + Actors + Cross-cutting present in all three**, where before only virtio had
  Overview/Cross-cutting.
- **C-5 — HTML comments gone** (0 occurrences in all three); virtio UC-2's `<!-- cluster:
  heterogeneous -->` removed; chi's `Asymmetry-promotion:` block removed; virtio's Gate-1/Gate-2
  derivation vocabulary in the Use-cases preamble rewritten into reader-facing prose that faithfully
  restates the same distinction. (Subject to P1-1.)
- **C-6 — the flagship is handled correctly.** chi before-REQ-004 → after-REQ-002
  (`chi/quality/REQUIREMENTS.md:115-124`): the divergence narration *"`Find` … does NOT perform the
  wildcard-URLParam reset — so a `Find` … leaves a stale `*` URLParam"* is restated as intended
  behavior *"`Find` must perform both effects … so that a `Find` against a mounted route leaves no
  stale `*` URLParam behind"*, with **both citations preserved verbatim** (`mux.go:383` and
  `mux.go:309-322`). This is exactly what the commit message claims.
- **C-7 — stamp reads v1.6.0** in all three (chi's input said v1.5.3).
- **Renumber map is internally consistent — I chased every cross-reference in virtio**, the target
  with the most reordering (before→after: 003→005, 004→006, 005→003, 006→004). Cross-cutting
  concerns updated correctly at `:249` ("REQ-001, REQ-002, and REQ-003 form a grid"), `:255-257`
  ("REQ-005 (reset) and REQ-006 (interrupt return)"), `:261-262` ("REQ-004 documents that legacy
  intentionally skips FEATURES_OK"); UC-1.a postcondition `:282-283` ("see UC-5 / REQ-003");
  UC-4.b `:337` ("reference for REQ-006"); traceability appendix `:361-371` consistent throughout.
  No stale pointer found.
- **References preserved exactly** — reference multiset identical before/after on all three targets;
  no citation added, dropped, or altered.
- **Much of the new prose is well grounded.** virtio's overview is largely carried from its input;
  its "largest and most intricate file" claim about `virtio_ring.c` is supported by the cited line
  ranges (~3532 vs ~565/~307); its admin-VQ/SR-IOV gap is honest (`virtio_pci_admin_legacy_io.c` and
  `virtio_pci_admin.h` are present but un-REQ'd); express's `History.md:15` citation and its
  self-critical *"This derivation is thin, and the operator should read it as thin"*
  (`express/quality/REQUIREMENTS.md:53-54`) are exactly the honesty F-1 is asking for. The problem is
  localized, not systemic — which is why it is fixable rather than disqualifying.

---

## Per-cell judgment (7 defects × 3 targets)

| | chi | express | virtio |
|---|---|---|---|
| C-1 tool contamination | ABSENT | ABSENT | ABSENT |
| C-2 scrambled ids | ABSENT | ABSENT | ABSENT |
| C-3 degenerate sections | ABSENT | ABSENT | ABSENT |
| C-4 narrative inconsistency | ABSENT | ABSENT | ABSENT |
| C-5 pipeline internals | **PRESENT** (`:6`, P1-1) | ABSENT | ABSENT (borderline `:105-106`) |
| C-6 bug-shaped REQs | ABSENT in render; **weakened in manifest** (P1-2) | ABSENT in render; **weakened in manifest** (P1-2) | ABSENT in render; **weakened in manifest** (P1-2) |
| C-7 stale stamp | ABSENT | ABSENT | ABSENT |

19 of 21 cells clean. C-5/chi fails outright. C-6 passes the document but fails the manifest on all
three.

---

## Verdict

**FIX-REQUIRED.**

Blocking: **P0-1** (fabricated virtio scope claim) and **P1-1** (C-5 present in chi's regenerated
render, plus the under-seeded deny-list that let it through). Both are defects in the artifact that
is supposed to *be* the proof that the defect classes are gone.

Also required before this can be called the acceptance oracle: **P1-2** — either restore the
displaced normative text to the manifest and pair-and-field-check it in
`ManifestUnchangedInvariantTests`, or correct the docstring and commit claim to stop asserting an
invariant that neither the fixture nor the test upholds. An over-claimed invariant on the artifact
the FP-audit consumes is the kind of thing that is cheap now and expensive in Slice 3.

P1-3 and the P2s I would accept as recorded follow-ups rather than blockers, provided P1-3's
limitation is written down somewhere the next reader will find it.

The engineering underneath this is careful — the temp-tree staging, the read-only input discipline,
the citation preservation, the cross-reference chase through the renumber map. The failure is
confined to LLM-authored prose making claims about a codebase, which is precisely where the charter
predicted it would be.
