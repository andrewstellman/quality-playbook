# Output — instruction 034: classifier bar is content-authority, not authorship provenance

**Status: complete. Unanimous SHIP across all three self-Council charters.**

Branch `1.6.0`. Implementation `ac30c60`, nine fix-up commits, head **`39bc78e`**.

| panelist | charter | rounds | findings closed | outcome |
|---|---|---|---|---|
| A | spec fidelity | 3 | 4 FIX-REQUIRED, 9 NIT | SHIP |
| B | regression safety | 3 | 6 FIX-REQUIRED, 5 NIT | SHIP |
| C | minimal surface / no mechanical over-reach | 3 | 3 FIX-REQUIRED, 6 NIT | SHIP |

**Suite: 3069 tests, 0 failures, 17 skipped. Python 3.14.6** (was 3055 at `ac30c60`;
+14). Three errors are environmental — `test_channel_install_e2e_090b` ×2 and
`test_full_build_publish_path_090f`, all venv / console-script install — verified
failing at `f87c87f` in a clean detached worktree during instruction 033 and
unchanged since.

Council artifacts: `runner/quality-playbook/reviews/v034_self_council/` (three
verdict files, every round retained). The directory is gitignored, as the
instruction specified `reviews/` only — no tracked copy was requested for 034,
unlike 033.

---

## Files changed

```
 bin/tests/test_content_authority_bar_034.py | 514 ++++++++++++++++++++++++++++
 references/phase1_exploration_guide.md      |  24 +-
 2 files changed, 534 insertions(+), 4 deletions(-)
```

**Zero lines of any script changed.** `git diff ac30c60~1..HEAD -- '*.py'`, excluding
the new test file, returns nothing. `doc_classification.py`,
`reference_docs_ingest.py`, `quality_gate.py` and `phase_prompts/phase1.md` have 0
commits in range — verified independently by panelist C.

- `references/phase1_exploration_guide.md` — six new paragraphs in the
  classification section (≈ lines 55–67), one new paragraph in Step 1b (≈ line 221),
  and three single-word edits (lines 43, 74, 512).
- `bin/tests/test_content_authority_bar_034.py` — new, 28 tests.

---

## The evidence, reproduced

The instruction said to reproduce it rather than take it on faith. All of it holds.

`repos/chi-1.6.0/quality/classification_reads.json`: **18 reads, all tier 4,
`zero_citable: true`.** Two are categorized `api-reference` — a *citable* category —
and demoted anyway:

> **13:** "Third-party API catalog, not chi's own **published** reference. …Given a
> confirmed inaccuracy on the first page checked, treating this as background…"
>
> **14:** "…**matches source at a summary level**…but compiled by an unnamed third
> party from 56 unspecified sources, **not chi's own maintainers** — background
> context, not an authoritative contract to cite against the code."

Document **14 settles it**: its own read records that the content matches the
source, so there is no accuracy concern and provenance is doing all the work.
Document 13's error is real — `chi.go:71` and `mux.go:100` show `Use()` returns
nothing, while the doc's lines 32 and 65 show `Use(...) Router`; `With()` at
`mux.go:236` is the one returning `Router` — but §8a says a spotted inaccuracy is a
Lane B cite, not a demotion.

Contrast `repos/express-accept`: **three `api-reference` docs at tier 2,
`lane=model-read`, `confirmation=unconfirmed`**, on the same third-party-compiled
provenance, down to its own `sources.md`. Same genre, same provenance, opposite
outcome.

---

## The guidance diff

Three of these were found by the Council, not by me; each is attributed.

**1 — the bar itself (task 1).** New paragraph, ≈ line 55:

> **The bar is content-authority, not authorship provenance.** The question is
> *"does this read as a precise, contract-shaped reference — concrete signatures,
> options, defaults, behavioral contracts?"*, **not** *"did the project's own
> maintainers write it?"* **Both halves have to hold**: the genre must be
> authoritative **and** the content must read as a contract. Content-authority
> removes the *provenance* question; it does not replace the *genre* one. A tutorial
> with precise code samples is still a tutorial. **But the genre is what a document
> is *for*, not what it is *titled* or *framed as*** — a title is not a genre, and
> that rule was deleted from the mechanical layer for a reason; do not reinstate it
> by hand. A file called a migration guide whose body states the exact current
> behavioral contracts is an `api-reference`. A file called `SPEC.md` that walks you
> through building something is a tutorial. Read the body, decide what the document
> is **for**, and only then ask whether that content is precise enough to quote.

The "both halves" clause is **A's F1**; the "genre is what it is *for*" companion is
**A's F4**, which found that F1's fix over-corrected into title-as-genre and would
have demoted a live express citable.

**2 — mixed documents (B's B-1).** Neither worked example above covers a body that
is genuinely *both*:

> **And when the body is genuinely both, the contract content decides it — upward.**
> …If a document contains a section a requirement could be written against — exact
> defaults, an options table, a stated behavioural change between versions — it is an
> `api-reference` and it goes to Lane B, even if most of its prose is showing you how
> to use the thing.

**3 — what promotion actually signs (B's B-7, corrected by C's C-1 and C-8):**

> **But be clear about what you are signing.** Citability is recorded per FILE, not
> per section: promoting a mixed document makes **the whole file** quotable at that
> tier … because the record carries only the path, the tier and the document hash,
> with no line range or section scope. So when you promote a mixed document, **name
> the contract section in your `reason`** … It is recorded on the document's record,
> where the requirements interview and Phase 4 can reach it. Note what it does
> **not** do: the end-of-Phase-1 show prints a fixed one-line reason and never your
> words, so a detail you leave only in the `reason` will not be on screen when the
> operator answers.

**4 — the back door (A's N6, promoted to a bold lede by C's C-5/C-9).**

**5 — the accuracy limit (A's N1, floored by B's B-4, extended by B's B-8,
reconciled with per-document isolation by C's C-4).**

**6 — the ambiguity line, narrowed (task 2).** Was:

> On genuine ambiguity, background — a missed grounding is recoverable, a false
> authoritative source poisons the derivation.

Now scoped to ambiguity **of genre**, with both defect readings disclaimed
explicitly, and the conservative direction preserved verbatim inside it.

**7 — depth is not a citation bar (A's F3).** New paragraph in Step 1b.

**8 — three single words.** `published` removed from the citable definition (A's F2
— the exact adjective in two chi demotion reasons), from the example `reason` string
(A's N8), and from the Tier-2 REQ scheme, where C's C-2 caught that my replacement
("a standardized API contract") was a *misfit* — none of the three live express
citables is standardized. Now "an external API contract".

---

## Acceptance criteria

| # | Criterion | Result |
|---|---|---|
| 1 | Guidance states: provenance is not the bar; the bar is content-authority; authoritative-genre-but-uncertain → Lane B `unconfirmed`; a spotted inaccuracy → Lane B | **PASS** — all four present, each pinned by a test |
| 2 | "On genuine ambiguity, background" scoped to genre ambiguity | **PASS** — and the preserved half pinned separately after B's bite deleted it silently |
| 3 | Regression fixture: compiled authoritative-genre reference, incl. a variant with a spotted inaccuracy, routes to Lane B (`llm` / `unconfirmed` / tier 1-2), non-vacuous | **PASS** — 28 tests; four non-vacuity controls; end-to-end to a byte-citable record |
| 4 | No regression: Lane C backstop unchanged; disclosure fires; express Lane B works; conservative direction holds | **PASS** — see below |
| 5 | Full suite green; `quality_gate.py` passes on a benchmark repo | **PASS with a caveat** — see below |

**Criterion 3 — the honest limit.** *The model's judgment itself cannot be
unit-tested.* The fixture pins the **mechanics**; the guidance text pins the
**judgment**. The text assertions are not a formality — the defect *was* the absence
of that text — but they detect **deletion, not contradiction**. C demonstrated this
directly: a bite that kept every pinned substring and wrote the provenance bar back
in by qualification passed 28/28. That limit is now recorded in the test file itself
rather than left for rediscovery.

**Criterion 4, verified by execution:**

```
Lane C w/ tier-1 authoritative read -> operator-confirmation-required | awaiting: 1
Lane B                              -> model-read / unconfirmed       | unconfirmed: 1
unread                              -> default-tier4 | zero_citable: True | unread: 1
```

B additionally drove seven Lane C probes (CVE id, GHSA id, two advisory hosts, both
combined, a real Go source file) through the real `rdi.ingest` — all
`operator-confirmation-required`, tier 4, no `FORMAL_DOC`, while a clean sibling in
the same corpus promoted to Lane B. Express replayed byte-identical to shipped: 3
citables, `unconfirmed_citable_count: 3`, all three reaching `FORMAL_DOC`.

**Criterion 5 — caveat stated plainly.** The full suite is green. `quality_gate.py`
runs clean and its classification checks fire correctly (express:
`unconfirmed_citable_count=3`, `awaiting_confirmation_count=5`). But all three
benchmark repos return `gate_result: FAIL` — for **unverified bugs in their own
recorded runs**, not for anything in this change. I verified the verdict and warning
count are **byte-identical with and without this edit**, and `quality_gate.py`
contains zero references to the guide. Reading criterion 5 as "the gate passes" would
be false; reading it as "the gate runs correctly and this change does not affect it"
is true and is what I claim.

---

## What the Council found

Twenty-two findings across nine rounds. The three that changed the shipped guidance
most:

- **A-F4** — my fix for A's own F1 over-corrected into title-as-genre and would have
  demoted `08_Migration_Guide_v4_to_v5.md`, a live express Lane B citable, against
  criterion 4. It also reinstated by hand the rule instruction 033 deleted from the
  mechanical layer.
- **B-1** — both worked examples covered a title/body *mismatch*; neither covered a
  body that is genuinely *both*. `07_Static_Files_Serving.md` is exactly that and is
  also a live citable. The live run's own reason had already argued against the guide
  reading: *"testable contract detail the lib/ code must match, **not just usage
  guidance**."*
- **B-7** — the mixed-document rule's load-bearing justification was **false about
  the mechanics**. Measured: promoting a mixed document yields `line_count: 269`,
  `byte_count` equal to the whole file, **no** scoping key of any kind, and
  `citation_excerpt` set to the document title.

### Four patterns

**1. An assertion not tied to the clause it named — six instances, all mine.** The
recurring defect was never the guidance's content; it was my fixture's text half. A
`*minor*` substring that matched an explanation instead of the rule; a fixed-width
window that stopped covering its own assertion when a sentence was inserted upstream;
worked examples unpinned; the Lane C signal never asserted at all; the conservative
direction unpinned while its narrowing was pinned; `candidate-spec` matching a
category list 60 lines away. It took **nine bites across three rounds** to work out.

**2. Each fix appended a clause to a load-bearing sentence, and arrived with a defect
the old text could not have had.** B-4 begat B-8. The B-7 paragraph begat B-11. C-1
begat C-8. B's rule: *when a fix adds prose to a rule, re-walk the cases the rule
already handled, not only the case that prompted the fix.*

**3. C's formulation, which is the sharpest thing this Council produced:**

> In a guidance-only change, the assertions that need executing are not the ones
> about the guidance — they are the ones the guidance makes about the code.

Three rounds produced three false claims about the machinery — B-7's, C-1's, C-8's —
each written by someone fixing the previous one, none catchable by reading.

**4. Inverted test sensitivity.** 14 of the 51 string assertions present when C
measured had made Markdown emphasis a CI-enforced contract on a file people will legitimately edit. Now emphasis-, dash-
and whitespace-insensitive, verified against a 12-case matrix: every typographic
change passes, every deletion and gutting fails, zero wrong-sensitivity cases.

### Did it grow too much? C's measurement, unsoftened

§8a's source paragraph is **276 words** — I re-measured that one exactly. The
classification section went **1693 → 2867 (+69%)** and the file 15491 → 16795, per
C's spans: roughly **4.5×**, across four rounds and six new paragraphs, with eight of
nine additions traceable to a task or a named finding.

*Re-measured independently:* on a narrower section span I get 757 → 1821 (**+140%**)
and the file at 15491 → 16783 (**+1292**). The section percentage is sensitive to
where you cut the section; the file-level delta agrees with C's to within 12 words,
which is the duplicate sentence C-9 removed after C measured. Both spans say the same
thing and neither says it grew a little.

C tested its own "you over-wrote this" conclusion by proposing to cut B-8's carve-out,
then checked `phase1.md`'s *"The show prints in every mode. The pause does not"*,
found the cut would ship a silent v4-against-v5 derivation on every unattended run,
and **withdrew its own finding**. Recorded here as a withdrawal, not a panelist
split — there is no disagreement between B and C on this.

> C's verdict on its own charter question: *"It grew a lot, almost all of it was
> earned, and I can only find fifty words to give back."*

### An operational finding

The first attempt at panelist B **stalled mid-bite and left the Lane C guard disabled
in the working tree** (`unacknowledged = []`). I caught it by diffing every file a
bite could touch, restored from the `HEAD` blob, purged 203 stale `.pyc` files, and
re-verified the guard *enforces* rather than that the line was back. Two rules came
out of it, and both held for the rest of the Council: **never hold a mutation across
more than one command**, and **never run the full suite with a mutation live** — the
stall happened during a ~95s full-suite run with the guard off.

Two bites of my own also passed for bad reasons: one whose anchor matched **zero**
occurrences, and one that matched in the **wrong location** (a bold occurrence in a
different paragraph than the bullet the test guards). Neither proves anything, and
both belong next to the anchor-uniqueness rule.

---

## Flagged, not fixed — out of 034's scope

1. **N5** — the guide still calls a self-classifying document *"a signal toward
   background"*, which §8a Revision rule 3 supersedes (Lane C: surfaced, neither
   obeyed nor suppressed). Pre-existing; both A and I judged it outside this
   instruction.
2. **N7** — the coverage-commitment table and the Step-7a gate key on **Deep**, so a
   Shallow Lane B cite carries no obligation to produce a requirement. Pre-existing
   asymmetry that this change makes more reachable. **Field trigger, so the follow-on
   has a test rather than a description:** a chi re-run producing Lane B `13`/`14`
   with zero Tier-1/2 requirements tracing to them.
3. **The demotion route added under A's N1** (pervasively-wrong / wrong-project /
   superseded-version, floored under B-4, extended under B-8, reconciled under C-4)
   **has no counterpart in §8a's text.** It is conservative and correctly framed, and
   B verified it is load-bearing on the unattended path — but it is a demotion route
   added to a paragraph whose purpose is limiting demotion routes, and it belongs in
   §8a on its next revision. Not this worker's to write.
