# Requirements Validation Interview

*The fitness-for-purpose interview (v1.6.0 Feature D). This is a **skill-protocol
chat** — a protocol the agent follows in a normal session, not a Python program
and not a generated file. It supersedes the v1.5.7 review/refinement walkthrough
(`REVIEW_REQUIREMENTS.md` / `REFINE_REQUIREMENTS.md` / `REFINEMENT_HINTS.md`),
which are no longer generated.*

## What this is for

QPB verifies that code conforms to the derived requirements. It has never
validated that the derived requirements are **the right requirements** — the
missing link in the Juran chain. This interview closes it: the operator confirms,
corrects, and adds to the requirements against what the system is actually
*supposed* to do, and the corrections land in the manifest as first-class
evidence so the spec absorbs them coherently instead of accreting patch notes.

The interview walks the Feature C document architecture top-down. A coherent
document is a precondition — a progressive interview over a jumbled one is not
possible, which is why Feature C ships first.

**It is offered, never auto-started.** The **primary offer is at the Phase 2 →
Phase 3 boundary** — the moment the requirements are complete and before Phases
3–6 build tests, reviews, and audits on them (Design §6; operator decision
2026-07-21). Validating the spec *before* downstream work depends on it is the
whole point: a correction made at the end leaves every derived artifact built on
the un-corrected requirements. A run that declines gets **one reminder at
playbook-end** that validation is still available — discoverability without
moving the primary offer to the end. Either way the protocol only *points* the
operator here; it does not run unbidden. A validation interview the operator did
not ask for is an interruption, not a service.

## The vocabulary is the rubric's — do not invent a second one

Every question this interview asks is the operator-facing form of a dimension in
`docs/design/QPB_v1.6.0_Requirements_Readability_Rubric.md` (Karl Wiegers'
requirements quality attributes). The readability Council scores those dimensions
from the outside; the interview asks the operator the same questions from the
inside. One vocabulary, so the Phase 4 defect log, the Council scores, and this
interview all speak the same language.

| Interview stage | Rubric dimensions it validates |
|---|---|
| **Stage 1 — narrative** | Complete · Honest-about-gaps |
| **Stage 2 — sections & use cases** | Consistent · Correct (intended-vs-stated behavior) |
| **Stage 3 — per-REQ drill-down** | Unambiguous · Verifiable |

**Ground truth is the operator's intent and the project's documentation — never
its code.** The rubric's rule holds here too: reading source to check whether a
requirement is *stated verifiably* is fine; reading source to decide whether a
requirement is *correct* is circular. The operator is the authority on what the
system is supposed to do; that is the whole point of asking them.

## Entry modes (carried from the shipped walkthrough)

The old walkthrough's three modes carry over as entry modes; they change *who
drives*, not what is asked.

- **Guided** (was Mode 2). The agent walks the document top-down, Stage 1 → 2 → 3,
  asking every stage-appropriate question in order. Best for a thorough first
  review.
- **Self-guided** (was Mode 1). The operator picks where to look — "show me the
  redirect requirements", "just the Overview". The agent still asks the
  stage-appropriate questions for whatever the operator lands on. Best when the
  operator already knows which areas need scrutiny.
- **Cross-model** (was Mode 3). A different model family than the one that
  generated the requirements drives the interview, to counter self-enhancement
  bias. Highest-value on an agent-authored spec. Otherwise identical.

Ask which mode at the start; default to guided if the operator does not say.

## The three stages — broad strokes first, drill down on demand

**Depth is never pushed. Breadth-first by default.** Most fitness-for-purpose
defects — wrong system, wrong actor, missing area — surface in Stage 1, the
cheapest place to catch them. Descend only where a stage surfaced doubt or the
operator steers.

### Stage 1 — validate the narrative (Complete · Honest-about-gaps)

Play back the top of the document and ask whether it is right. Read the Overview,
actors & roles, and the section themes, then say, in the agent's own words:

> "Here's what I think this system is, who it serves, and its major behavioral
> areas: … Is that right?"

**Also play back the organizing principle** the derivation chose (Design §5.2 /
§6 Stage 1). The choice is a high-yield fitness-for-purpose question — a wrong
lens makes every section feel slightly off, and it is cheapest to correct here,
before Stage 2 descends into the sections:

> "I organized these requirements **by *user journey*** because this is a
> workflow system whose requirements cluster around the stages a user moves
> through — is that the right lens, or would grouping by *stakeholder* (or by
> *feature*, *mode*, …) fit how you think about this system?"

A change of organizing principle here is a **`correct`** move: it triggers a
re-group (reassign `functional_section`, rewrite the section overviews) and a
re-render through the Phase E selection pass, not a per-REQ edit. Record it like
any other correction so the new lens survives re-derivation.

Then play back the **coverage-and-gaps statement** verbatim and ask the Stage-1
gap question:

> "Here's what I believe I did **not** cover: … Is that intentional, or did I
> miss something that matters?"

This is where the F-1 statement earns its place: it converts silent thinness into
a prompt. An operator who says "no, the auth subsystem matters and you skipped it"
has just produced an **add** that no autonomous pass would have found.

**Stage-1 elicitation** — the artifact-category and artifact-shape questions
(highest-yield, drawn from `Requirements_Miss_Archeology.md`):

- **Artifact-category fit:** "Is this the *right kind* of thing to specify here?
  Is a judgment the requirement asks for actually a judgment, or is it something
  that should be settled mechanically?"
- **Artifact-shape:** "Does the shape of these requirements match what you'll do
  with them downstream? Are they stated as intended behavior, or as descriptions
  of what the code happens to do?"
- **Missing-area (Complete):** "What whole area of this system's behavior has no
  requirements here at all?"
- **Honest-about-gaps:** "Is the gaps statement accurate — does it claim something
  is out of scope that is actually in scope?" (The instruction-001 finding —
  virtio's "outside the checkout entirely" for files that were present — is the
  archetype. An inaccurate gaps statement is worse than none.)

### Stage 2 — validate sections and use cases (Consistent · Correct)

Per requirement section, in the document's order (most-relevant-to-the-primary-
reader first, under whatever organizing principle Stage 1 settled), read the
section's **section overview** — the paragraph stating the theme that unifies its
requirements under the chosen principle — and validate that theme *before*
descending into the section's requirements and use cases:

> "This section groups its requirements around X. Is that a real, coherent
> grouping for this system — and is X what the system is *supposed* to
> guarantee here?"

**Stage-2 elicitation** — terminology, identity, and dependency questions (the
worked-example classes and the self-encoding question):

- **Terminology disambiguation (Consistent):** "Is every load-bearing term
  defined and used one way? Does one word cover two concepts, or two words cover
  one?" (The pattern/lever confusion from the 2026-05-02 worked example: clear to
  those in the conversation, invisible to a cold reader. Rigorous clarity means
  every load-bearing term has a definition somewhere accessible — the glossary
  slot exists for exactly this.)
- **Identity / independence (Consistent):** "When this section quantifies
  something — 'all four transports', 'across N samples' — is each one actually
  independent, or is one of them double-counted?" (The chi-double-count catch:
  four benchmarks that were three distinct codebases.)
- **Dependency tracing (Correct/Complete):** "For each behavior this section
  requires, is every place that must change for it to actually hold enumerated?"
  (The six→seven hardcode: a change that *looks* complete, silently neutered by a
  stale count elsewhere.)
- **Judgment-vs-comparison:** "Does this requirement ask an implementer to
  *produce* a judgment, or to *compare* two things? A requirement that needs an
  opinion about what the code should do is generating opinions, not contracts."

### Stage 3 — per-REQ drill-down, operator-pulled (Unambiguous · Verifiable)

Individual REQs are examined **only** where Stage 1/2 surfaced doubt, or where the
operator asks. Never march through every REQ.

For a REQ under drill-down:

- **Unambiguous:** "Could two competent engineers build different things from
  this? Are there vague quantifiers — 'fast', 'appropriate', 'as needed' — or
  undefined terms?"
- **Verifiable:** "Could you write a test that objectively passes or fails on
  this? If not, it is not yet a requirement." (Weight this heaviest — QPB's later
  phases write real tests from these REQs, so an unverifiable REQ degrades
  everything after Phase 2.)
- **Outcome verification (Verifiable):** where a REQ carries a projection or a
  target, "does the measured result match the claim?" (Pattern 7 projected +0.40,
  measured +0.20 — the gap was real signal.)
- **Disjunction check:** "Does this state one required behavior, or does it offer
  a choice — 'rejects or clamps', 'X or document that not-X'? If it offers a
  choice, which one is required?" (This is the no-disjunction rule from the
  authoring surfaces, asked of the operator rather than the generator.)

## The five moves — the operator is always in control

At every stage the operator has five moves. **Confirm / correct / add** are the
substance; **drop / defer** keep the session honest.

- **Confirm.** "Yes, that's right." Recorded as evidence — see *Write-back* and
  F-2. A confirmation is not a no-op: it is the operator vouching for the
  requirement, and it is durable.
- **Correct.** "It should say …". The operator states what the requirement should
  be. This one move covers rewording, merging two REQs, splitting one into
  several, tightening prose — the derivation absorbs the correction and re-renders.
  (The proposal's six structural dispositions collapse into this; per-attribute
  disposition taxonomy was inspection-tool ceremony for an MVP.)
- **Add.** "You missed …". The operator names behavior the derivation did not
  capture. Becomes a new REQ record.
- **Drop.** "That's not a real requirement." The REQ is removed, with the reason
  recorded.
- **Defer.** "I don't know yet." Recorded as an open question, not forced to a
  resolution. Deferral is a legitimate answer; a session that pretends every
  requirement was resolved is lying.

## Write-back — the point of the whole feature

**Corrections and additions land in the manifest, not in a side file.** A
`correct` or `add` writes a new or updated REQ record to
`quality/requirements_manifest.json`, then the Feature C renderer re-renders
`REQUIREMENTS.md` from it. The spec absorbs the operator's intent coherently
instead of accreting a pile of patch notes the way the old REFINEMENT_HINTS.md
did.

Records touched in a session carry `source_type: operator-confirmation` with a
citation into the preserved transcript (F-2; the byte-citation machinery applies
unchanged — the transcript is the citable source).

A surgical re-derivation of a corrected REQ — re-run derivation for *that* REQ
with the operator's correction as new evidence — is in scope. Full
iterate-until-clean loop tooling is not; that waits.

**Renumber is the interview's terminal step, not a deferral** *(Design §6, added
2026-07-21).* An `add` (or a section move) inserts a REQ into the document
before its neighbours, so the raw IDs are momentarily out of document order.
**Do not ship that.** Run the Phase E.6 sequential renumber **once, as the final
step after all operator moves**, so the delivered `REQUIREMENTS.md` is REQ-001…N
in strict document order — the render contract FAILs a document whose IDs are
not ascending in document order (2026-07-21: chi/express/virtio all deferred the
renumber and shipped out-of-order IDs). The renumber updates **every id-carrying
cross-reference atomically** in the same pass: REQ records' `use_cases[]`, UC
records' `requirements[]`, BUG records' `requirement`, and `COVERAGE_MATRIX.md`
(the standard E.6 write-back).

*What the renumber does NOT need to touch:* `quality/operator_confirmations.jsonl`.
Those records are **content-keyed** (`req_title` + `conditions_of_satisfaction`),
deliberately **not** keyed on REQ id, precisely because E.6 renumbers every run
(F-2a below) — and the log is **append-only**, so its records are never rewritten
anyway. A confirmation resolves to its REQ by content after the renumber, not by
a stored id. So the renumber leaves the confirmations log untouched and every
confirmation still resolves.

**Durability across runs is F-2a**, and it is not optional. Every confirm /
correct / add also appends a record to `quality/operator_confirmations.jsonl`
(append-only; see F-2a below). The manifest is re-derived on every run; the
`.jsonl` is the only thing that survives to tell next week's run "the operator
already vouched for this."

## Artifacts

- **`quality/REQUIREMENTS_REVIEW.md`** — the defect log, organized **by Wiegers
  attribute and by move**. Every correct / add / drop / defer is one entry:
  the dimension it belongs to (Complete, Consistent, …), the move, the REQ, and
  the operator's words. Confirms are recorded as evidence, not defects. This is
  the same vocabulary the readability Council scores against, so a session's
  output is directly comparable to a Council run.

- **`quality/review_sessions/<TIMESTAMP>-<topic>.md`** — the session transcript,
  written **only behind an explicit operator save-gate.** Ask before saving; the
  transcript may contain things the operator said in confidence. It is the
  citable source for every `operator-confirmation` record, so if the operator
  declines to save it, the confirmations cite nothing and are not durable — tell
  the operator that trade-off when you ask.

- **`quality/operator_confirmations.jsonl`** — F-2a, below.

## F-2a — cross-run durability of operator confirmations

The hazard, plainly: an operator spends thirty minutes correcting a spec,
re-runs QPB next week, and the corrections are silently gone, because QPB
re-derives the manifest every run. F-2a is the cheap 80% that stops the silent
loss — it does **not** solve cross-run REQ identity, which is a separate hard
problem deferred with F-3.

- **`quality/operator_confirmations.jsonl` is append-only.** The derivation never
  rewrites or truncates it. The gate enforces this two ways: (a) if the manifest
  still carries `operator-confirmation` REQs, the log must be present and
  non-empty — a run that keeps the confirmed REQs but drops their durable backing
  FAILs, needing no snapshot; and (b) **a re-derivation MUST copy the log to
  `quality/operator_confirmations.prior.jsonl` before it rewrites `quality/`**,
  and the gate then proves the live file still has that snapshot as a byte prefix,
  catching truncation, overwrite, or reorder even across runs where the manifest
  no longer names the confirmed REQs. Without the snapshot, cross-run truncation
  is invisible to the gate — so writing it is not optional. This is the
  load-bearing invariant: the operator's work cannot be silently destroyed by a
  later run.
- **Each record carries the REQ's *content* at confirmation time** — the title
  and conditions of satisfaction, not merely an id — plus the operator's
  statement verbatim, an ISO date, and a citation into the saved transcript.
- **Not keyed on REQ id.** Phase E.6 renumbers every run, so this run's REQ-005 is
  not last run's REQ-005; an id is meaningless across runs. Later matching is
  content-based and **advisory**.
- **Read path — surface, never auto-merge.** Where a run finalizes the manifest,
  it reads the file and reports: *"N operator-confirmed requirements from prior
  sessions; K appear absent from this derivation"*, quoting the operator's
  original words. It does not re-apply them — automatic re-application would
  require exactly the cross-run identity resolution F-2a defers. The goal is to
  convert silent data loss into a prompt the operator can act on.

## Supersession

This protocol replaces the v1.5.7 review/refinement walkthrough entirely — one
system, not two. `quality/REVIEW_REQUIREMENTS.md`, `quality/REFINE_REQUIREMENTS.md`,
and `quality/REFINEMENT_HINTS.md` are **no longer generated**. Their
guided/self-guided/cross-model modes survive as this protocol's entry modes; the
rest is gone. Adopters who installed v1.5.7 may still have the old files on disk —
that is fine, they need no migration, and QPB neither reads nor rewrites them.

The behavioral difference that matters: the old cycle wrote feedback to a hints
file that a *separate refinement pass* then applied, with versioned backups. This
interview writes the operator's intent **straight to the manifest** (the source
of truth) and re-renders, so there is one write path and no drift between a hints
file and the spec.
